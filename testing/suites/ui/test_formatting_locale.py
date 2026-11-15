"""Numbers and sizes follow the interface language (REQ-L10N-UI-015).

When the interface language is set, the app takes one formatting locale for the
numbers it formats: the system's own locale when that locale is in the active
interface language, otherwise the locale of the active interface language. The
three kinds of number the requirement names are read here from what the user
sees: the data size in the cost confirmation, the scale in the real-size
preview's label, and the decimals of the numeric input fields.

Where the expected values come from. The requirement's own figures are quoted as
written: "506,25", one U+00A0 and "Mio" for French, "506.25 MiB" for English.
For every other language the figure is Qt's own data-size formatting of that
language (``QLocale(<code>).formattedDataSize``), and the one character between
the number and the unit in French and Russian is U+00A0. Nothing is taken from
the code under test: the rule for the unit space is rebuilt below from the
requirement's sentence, so a regression in the product's rule cannot move the
expectation with it.

How the system locale is set. The language manager reads the system locale
through one seam (its ``system_locale`` argument; by default ``QLocale.system()``
looked up at the moment of use). The manager-level rows pass the seam directly.
The window-level rows replace ``QLocale.system`` for the length of the test,
before the window is built, which is the same seam. A real operating system's
locale cannot be set from a test on Windows, so the one row that must read the
REAL system locale (it is never changed) runs in a fresh interpreter, where no
suite fixture has replaced anything.

Which language is active. A window starts in the language the injected system
locale selects; every row sets the language it needs and every window or manager
is put back to English when the row ends. Rows that switch language build their
own window; none calls ``QAction.menu()``.

Both themes (the autouse ``theme`` fixture), offscreen.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDoubleSpinBox,
    QGraphicsScene,
    QWidget,
)

import pixelart_creator
from pixelart_creator.logic.constants import (
    DOCUMENT_TRANSFORM_CONFIRM_BYTES,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)
from pixelart_creator.logic.doc_transform import projected_peak_bytes
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import ExportFormat, ExportRequest
from pixelart_creator.logic.grids import (
    IsoGridConfig,
    PerspectiveConfig,
    VanishingPoint,
)
from pixelart_creator.ui.document_transform_dialogs import (
    Document_Transform_Confirm_Dialog,
)
from pixelart_creator.ui.export_worker import ExportTarget
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    current_formatting_locale,
)
from pixelart_creator.ui.iso_grid_dialog import Iso_Grid_Dialog
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.real_size_preview_window import (
    Real_Size_Calibration_Dialog,
    Real_Size_Preview_Window,
)
from pixelart_creator.ui.rotsprite_dialog import RotSprite_Dialog
from pixelart_creator.ui.transform_dialog import Scale_Dialog
from pixelart_creator.ui.vanishing_point_dialog import Vanishing_Point_Dialog
from testing.suites.ui._export_helpers import animation_document

# --------------------------------------------------------------------------- #
# The oracle                                                                  #
# --------------------------------------------------------------------------- #

#: The eight languages of the finished product, English included.
EIGHT: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "ja", "ko", "zh_CN")

#: The requirement's measured figure: the cost confirmation for this many bytes.
FIGURE_BYTES = 530_841_600

#: The languages whose data size carries one U+00A0 before the unit.
NO_BREAK_LANGUAGES = ("fr", "ru")

NO_BREAK_SPACE = " "

#: A system locale whose language is none of the eight.
OUTSIDE_THE_EIGHT = "sv_SE"

#: The system locale of the measured case.
SPANISH_SYSTEM = "es_ES"

#: One non-integer value that lies inside the range of every decimal field.
SAMPLE_VALUE = 1.5

#: The value typed into a field, with the decimal separator left to the test.
TYPED_WHOLE, TYPED_FRACTION = "2", "5"

PACKAGE_DIR = Path(inspect.getfile(pixelart_creator)).resolve().parent
UI_DIR = PACKAGE_DIR / "ui"


def qt_data_size(language: str, size: int) -> str:
    """Qt's own data-size text of ``size`` for ``language``'s locale."""
    return QLocale(language).formattedDataSize(size)


def with_no_break_space(text: str) -> str:
    """Return ``text`` with one U+00A0 between the number and the unit.

    Rebuilt from the requirement's sentence ("exactly one U+00A0 between the
    number and the unit"): the number is everything up to its last digit, the
    unit is the letters after it, and whatever separated them (a plain space,
    a narrow no-break space, a no-break space, or nothing) is replaced.
    """
    match = re.fullmatch(r"(.*\d)[\s  ]*(\D+)", text)
    assert match is not None, f"no number and unit in {text!r}"
    return f"{match.group(1)}{NO_BREAK_SPACE}{match.group(2)}"


def expected_figure(language: str, size: int) -> str:
    """The data-size text the requirement expects under ``language``."""
    text = qt_data_size(language, size)
    return with_no_break_space(text) if language in NO_BREAK_LANGUAGES else text


def figure_problems(message: str, language: str, size: int) -> List[str]:
    """Return what is wrong with the figure in ``message`` under ``language``.

    A pure verdict, so the controls can decide it on literals. The figure must
    be present as the requirement expects it; and where Qt's own text differs
    from the expected one only in the character before the unit, the unexpected
    form must be absent.
    """
    problems: List[str] = []
    want = expected_figure(language, size)
    if want not in message:
        problems.append(f"{want!r} is not in {message!r}")
    own = qt_data_size(language, size)
    if own != want and own in message:
        problems.append(f"Qt's own text {own!r} (not the required spacing) is shown")
    return problems


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def make_manager(qapp) -> Iterator[Callable[[str], LanguageManager]]:
    """Build language managers whose system locale is injected through the seam."""
    made: List[LanguageManager] = []

    def make(system: str) -> LanguageManager:
        manager = LanguageManager(qapp, system_locale=lambda: QLocale(system))
        made.append(manager)
        return manager

    try:
        yield make
    finally:
        for manager in reversed(made):
            manager.set_language(FALLBACK_LANGUAGE)


@pytest.fixture
def make_window(qtbot, monkeypatch) -> Iterator[Callable[[str], Main_Window]]:
    """Build a window whose language manager reads the given system locale."""
    made: List[Main_Window] = []

    def make(system: str) -> Main_Window:
        monkeypatch.setattr(
            QLocale, "system", staticmethod(lambda: QLocale(system)), raising=True
        )
        window = Main_Window()
        qtbot.addWidget(window)
        made.append(window)
        return window

    try:
        yield make
    finally:
        for window in reversed(made):
            window._language_manager.set_language(FALLBACK_LANGUAGE)


def confirmation_message(window: Main_Window, size: int, qtbot) -> str:
    """Open the cost confirmation for ``size`` bytes; return its message text."""
    dialog = Document_Transform_Confirm_Dialog(
        "Scale Canvas", size, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT, window
    )
    qtbot.addWidget(dialog)
    return dialog._message.text()


# --------------------------------------------------------------------------- #
# SC-L10N-UI-015-1: setting the language sets the formatting locale           #
# --------------------------------------------------------------------------- #

#: (system, language, formatting): the scenario's examples, then two more
#: rows where the system's language is not the interface language.
FORMATTING_ROWS = [
    ("es_ES", "es", "es_ES"),
    ("es_ES", "fr", "fr"),
    ("es_ES", "en", "en"),
    ("en_GB", "en", "en_GB"),
    ("fr_CA", "fr", "fr_CA"),
    ("zh_TW", "zh_CN", "zh_CN"),
    ("ja_JP", "ko", "ko"),
    ("pt_BR", "en", "en"),
    ("de_DE", "ja", "ja"),
]


@pytest.mark.parametrize(("system", "language", "formatting"), FORMATTING_ROWS)
def test_sc_l10n_ui_015_1_setting_the_language_sets_the_formatting_locale(
    make_manager, system, language, formatting
):
    """SC-L10N-UI-015-1: each (system, language) row gives its formatting locale."""
    manager = make_manager(system)
    seen: List[Tuple[str, str]] = []
    manager.languageChanged.connect(
        lambda code: seen.append((code, current_formatting_locale().name()))
    )

    assert manager.set_language(language) is True

    expected = QLocale(formatting).name()
    assert manager.formatting_locale().name() == expected
    assert current_formatting_locale().name() == expected
    # A slot connected to the change already reads the new value.
    assert seen == [(language, expected)]


def test_sc_l10n_ui_015_1_a_missing_catalogue_falls_back_to_english(make_manager):
    """SC-L10N-UI-015-1: a language with no catalogue leaves English and its locale."""
    manager = make_manager(SPANISH_SYSTEM)
    assert manager.set_language("xx") is False
    assert manager.current_language() == FALLBACK_LANGUAGE
    assert manager.formatting_locale().name() == QLocale("en").name()


def test_sc_l10n_ui_015_1_the_module_function_follows_eight_switches(make_manager):
    """SC-L10N-UI-015-1: after each of eight switches the shared reader agrees."""
    manager = make_manager(SPANISH_SYSTEM)
    examined = 0
    for language in EIGHT:
        assert manager.set_language(language) is True
        want = QLocale(SPANISH_SYSTEM if language == "es" else language).name()
        assert manager.formatting_locale().name() == want
        assert current_formatting_locale().name() == want
        examined += 1
    print(f"SC-L10N-UI-015-1: {examined} of {len(EIGHT)} languages examined")
    assert examined == len(EIGHT)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-015-2 and -3: the data size in the cost confirmation              #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_015_2_french_on_a_spanish_system(make_window, qtbot):
    """SC-L10N-UI-015-2: French on es_ES shows "506,25", U+00A0, "Mio"."""
    window = make_window(SPANISH_SYSTEM)
    assert window._language_manager.set_language("fr") is True

    message = confirmation_message(window, FIGURE_BYTES, qtbot)

    assert f"506,25{NO_BREAK_SPACE}Mio" in message
    assert "506.25 MiB" not in message
    assert "506.25" not in message


def test_sc_l10n_ui_015_2_the_flip_prompt_uses_the_same_figure(
    make_window, qtbot, monkeypatch
):
    """SC-L10N-UI-015-2: the real flip action's prompt reads the French figure too."""
    window = make_window(SPANISH_SYSTEM)
    assert window._language_manager.set_language("fr") is True
    document = Document(MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    document.add_layer(frame_index=0)
    document.add_layer(frame_index=0)  # three layers: above the threshold
    projected = projected_peak_bytes(document, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    assert projected > DOCUMENT_TRANSFORM_CONFIRM_BYTES
    record = window.active_tab()
    record.document = document
    record.scene.set_document(document)
    record.view.clear_selection()
    shown: List[Document_Transform_Confirm_Dialog] = []
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: shown.append(self) or 0,
    )

    window._on_flip_horizontal()

    assert len(shown) == 1
    message = shown[0]._message.text()
    assert figure_problems(message, "fr", projected) == []
    assert NO_BREAK_SPACE in message


def test_sc_l10n_ui_015_3_no_system_format_leaks_into_any_language(make_window, qtbot):
    """SC-L10N-UI-015-3: with a system outside the eight, each language is its own.

    The figure equals that language's own Qt formatting; in French and Russian
    the one character before the unit is U+00A0. The number of languages
    examined, 8, is printed.
    """
    window = make_window(OUTSIDE_THE_EIGHT)
    manager = window._language_manager
    problems: List[str] = []
    examined: List[str] = []
    for language in EIGHT:
        assert manager.set_language(language) is True, language
        message = confirmation_message(window, FIGURE_BYTES, qtbot)
        problems += [
            f"{language}: {problem}"
            for problem in figure_problems(message, language, FIGURE_BYTES)
        ]
        examined.append(language)
    print(f"SC-L10N-UI-015-3: {len(examined)} of {len(EIGHT)} languages examined")
    assert examined == list(EIGHT)
    assert problems == []


def test_sc_l10n_ui_015_3_the_fr_and_ru_texts_carry_u00a0_before_the_unit(
    make_window, qtbot
):
    """SC-L10N-UI-015-3: in fr and ru the character before the unit is U+00A0."""
    window = make_window(OUTSIDE_THE_EIGHT)
    for language in NO_BREAK_LANGUAGES:
        assert window._language_manager.set_language(language) is True
        message = confirmation_message(window, FIGURE_BYTES, qtbot)
        unit = re.search(r"506,25(.)(Mio|MiB)", message)
        assert unit is not None, f"{language}: no figure in {message!r}"
        assert unit.group(1) == NO_BREAK_SPACE, language


def test_the_figure_verdict_accepts_the_required_text_and_rejects_the_rest():
    """The verdict of the data-size rows: the controls, decided on literals."""
    good_fr = f"up to 506,25{NO_BREAK_SPACE}Mio of memory"
    assert figure_problems(good_fr, "fr", FIGURE_BYTES) == []
    # French with Qt's plain space is the defect the requirement names.
    assert figure_problems("up to 506,25 Mio of memory", "fr", FIGURE_BYTES)
    # Russian likewise.
    assert figure_problems("до 506,25 MiB", "ru", FIGURE_BYTES)
    assert figure_problems(f"до 506,25{NO_BREAK_SPACE}MiB", "ru", FIGURE_BYTES) == []
    # The English figure inside a French sentence is the measured defect.
    assert figure_problems("up to 506.25 MiB of memory", "fr", FIGURE_BYTES)
    # English keeps Qt's own text, plain space included.
    assert figure_problems("up to 506.25 MiB of memory", "en", FIGURE_BYTES) == []
    assert figure_problems(f"up to 506.25{NO_BREAK_SPACE}MiB", "en", FIGURE_BYTES)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-015-4: the locale the system reports is never changed             #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_015_4_the_default_locale_and_the_startup_match_hold(make_manager):
    """SC-L10N-UI-015-4: eight switches change neither Qt's default nor the match."""
    manager = make_manager(SPANISH_SYSTEM)
    default_before = QLocale().name()
    system_before = QLocale.system().name()
    assert manager.install_from_locale(None) == "es"

    switched = 0
    for language in EIGHT:
        assert manager.set_language(language) is True
        switched += 1
        assert QLocale().name() == default_before, f"after {language}"
        assert QLocale.system().name() == system_before, f"after {language}"
        # The startup match of the system's preferred-language list gives the
        # language it gave before the first switch.
        assert manager.install_from_locale(None) == "es", f"after {language}"
    assert switched == len(EIGHT)


def _real_system_probe() -> Dict[str, object]:
    """Run eight switches in a fresh interpreter and return what it observed.

    No fixture of this suite has replaced ``QLocale.system`` there, so it reads
    the real locale of the machine. The package is imported from the same tree
    as the running tests.
    """
    code = """
import json, sys
sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication
app = QApplication([])
import pixelart_creator.ui.i18n as i18n
default_before, system_before = QLocale().name(), QLocale.system().name()
no_manager = i18n.current_formatting_locale().name()
manager = i18n.LanguageManager(app)
rows = []
for code in sys.argv[2:]:
    manager.set_language(code)
    rows.append({
        "code": code,
        "default": QLocale().name(),
        "system": QLocale.system().name(),
        "formatting": manager.formatting_locale().name(),
        "shared": i18n.current_formatting_locale().name(),
        "formatting_language": QLocale(
            manager.formatting_locale().name()
        ).language().name,
        "code_language": QLocale(code).language().name,
    })
print(json.dumps({"default": default_before, "system": system_before,
                  "no_manager": no_manager, "rows": rows}))
"""
    root = str(PACKAGE_DIR.parent)
    done = subprocess.run(
        [sys.executable, "-I", "-c", code, root, *EIGHT],
        capture_output=True,
        text=True,
        timeout=120,
        env={**_clean_env(), "QT_QPA_PLATFORM": "offscreen"},
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def _clean_env() -> Dict[str, str]:
    """The environment a probe interpreter needs, nothing of the suite's own."""
    import os

    keep = ("SYSTEMROOT", "PATH", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG")
    return {name: os.environ[name] for name in keep if name in os.environ}


def test_sc_l10n_ui_015_4_the_real_system_locale_is_never_changed():
    """SC-L10N-UI-015-4: in a fresh interpreter the real locale survives 8 switches."""
    seen = _real_system_probe()
    rows = seen["rows"]
    assert [row["code"] for row in rows] == list(EIGHT)
    # Qt's default locale equals the real system locale before any switch, and
    # before any manager exists the shared reader gives that default.
    assert seen["default"] == seen["system"]
    assert seen["no_manager"] == seen["default"]
    for row in rows:
        assert row["system"] == seen["system"], row
        assert row["default"] == seen["default"], row
        assert row["shared"] == row["formatting"], row
        # Whatever this machine's locale is, the formatting locale is in the
        # interface language.
        assert row["formatting_language"] == row["code_language"], row


# --------------------------------------------------------------------------- #
# SC-L10N-UI-015-5: a live switch                                              #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_015_5_a_live_switch_reaches_the_next_figure_and_field(
    make_window, qtbot
):
    """SC-L10N-UI-015-5: French then English: next figure and next field follow."""
    window = make_window(SPANISH_SYSTEM)
    manager = window._language_manager
    assert manager.set_language("fr") is True
    first = confirmation_message(window, FIGURE_BYTES, qtbot)
    assert f"506,25{NO_BREAK_SPACE}Mio" in first

    assert manager.set_language("en") is True

    second = confirmation_message(window, FIGURE_BYTES, qtbot)
    assert "506.25 MiB" in second
    assert "506,25" not in second
    field = RotSprite_Dialog(lambda angle: None, window)
    qtbot.addWidget(field)
    field._angle.setValue(SAMPLE_VALUE)
    assert field._angle.text().startswith("1.5")
    assert "," not in field._angle.text()


def test_sc_l10n_ui_015_5_an_open_confirmation_follows_the_switch(make_window, qtbot):
    """SC-L10N-UI-015-5: a confirmation already open re-reads its figure on a switch."""
    window = make_window(SPANISH_SYSTEM)
    manager = window._language_manager
    assert manager.set_language("fr") is True
    dialog = Document_Transform_Confirm_Dialog(
        "Scale Canvas", FIGURE_BYTES, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT, window
    )
    qtbot.addWidget(dialog)
    assert f"506,25{NO_BREAK_SPACE}Mio" in dialog._message.text()

    assert manager.set_language("en") is True
    QApplication.processEvents()

    assert "506.25 MiB" in dialog._message.text()
    assert "506,25" not in dialog._message.text()


# --------------------------------------------------------------------------- #
# SC-L10N-UI-015-6: the real-size preview's scale                              #
# --------------------------------------------------------------------------- #


def _scale_text(window: Main_Window, qtbot) -> str:
    """The preview's status label with a scale of 1.5 (96 PPI document, 144 DPI)."""
    preview = Real_Size_Preview_Window(QGraphicsScene(window), 96.0, window)
    qtbot.addWidget(preview)
    preview.set_manual_dpi(144.0)
    assert preview.current_scale() == SAMPLE_VALUE
    return preview._status.text()


def test_sc_l10n_ui_015_6_the_scale_uses_a_comma_in_french(make_window, qtbot):
    """SC-L10N-UI-015-6: French on es_ES shows the scale 1.5 as "1,50"."""
    window = make_window(SPANISH_SYSTEM)
    assert window._language_manager.set_language("fr") is True

    text = _scale_text(window, qtbot)

    assert "1,50×" in text
    assert "1.50" not in text


def test_sc_l10n_ui_015_6_the_scale_follows_each_language(make_window, qtbot):
    """SC-L10N-UI-015-6: in every language the scale uses its decimal separator."""
    window = make_window(OUTSIDE_THE_EIGHT)
    problems: List[str] = []
    for language in EIGHT:
        assert window._language_manager.set_language(language) is True
        point = QLocale(language).decimalPoint()
        text = _scale_text(window, qtbot)
        if f"1{point}50×" not in text:
            problems.append(f"{language}: no '1{point}50×' in {text!r}")
    assert problems == []


# --------------------------------------------------------------------------- #
# SC-L10N-UI-015-7: every numeric input field                                  #
# --------------------------------------------------------------------------- #


def _perspective() -> PerspectiveConfig:
    return PerspectiveConfig(
        mode=2,
        vanishing_points=(
            VanishingPoint(position=(1.0, 2.0)),
            VanishingPoint(position=(3.0, 4.0)),
        ),
        horizon_y=10.0,
    )


#: The dialogs that hold the app's decimal fields, each built as the app builds it.
FIELD_DIALOGS: Dict[str, Tuple[type, Callable[[QWidget], QDialog]]] = {
    "iso grid": (
        Iso_Grid_Dialog,
        lambda parent: Iso_Grid_Dialog(
            IsoGridConfig(tile_width=40, ratio=1.2, origin=(1.0, 2.0)), parent
        ),
    ),
    "calibration": (
        Real_Size_Calibration_Dialog,
        lambda parent: Real_Size_Calibration_Dialog(parent),
    ),
    "rotsprite": (
        RotSprite_Dialog,
        lambda parent: RotSprite_Dialog(lambda angle: None, parent),
    ),
    "scale": (Scale_Dialog, lambda parent: Scale_Dialog(16, 16, parent)),
    "vanishing points": (
        Vanishing_Point_Dialog,
        lambda parent: Vanishing_Point_Dialog(_perspective(), parent),
    ),
}


def _decimal_fields(window, qtbot) -> List[Tuple[str, QDoubleSpinBox]]:
    """Open each dialog and return every decimal field in it, with its dialog name."""
    fields: List[Tuple[str, QDoubleSpinBox]] = []
    for name, (_cls, build) in FIELD_DIALOGS.items():
        dialog = build(window)
        qtbot.addWidget(dialog)
        fields += [(name, spin) for spin in dialog.findChildren(QDoubleSpinBox)]
    return fields


def test_sc_l10n_ui_015_7_every_decimal_field_uses_the_formatting_locale(
    make_window, qtbot
):
    """SC-L10N-UI-015-7: French on es_ES: each field shows "," and accepts ",".

    The number of fields examined is printed and is non-zero.
    """
    window = make_window(SPANISH_SYSTEM)
    assert window._language_manager.set_language("fr") is True
    fields = _decimal_fields(window, qtbot)
    print(f"SC-L10N-UI-015-7: {len(fields)} decimal fields examined")
    assert len(fields) > 0

    problems: List[str] = []
    for name, spin in fields:
        label = f"{name}/{spin.objectName() or type(spin).__name__}"
        if not spin.minimum() <= SAMPLE_VALUE <= spin.maximum():
            problems.append(f"{label}: {SAMPLE_VALUE} is outside its range")
            continue
        if spin.locale().name() != QLocale("fr").name():
            problems.append(f"{label}: locale {spin.locale().name()}")
        spin.setValue(SAMPLE_VALUE)
        if not spin.text().startswith("1,5"):
            problems.append(f"{label}: shows {spin.text()!r}, not 1,5...")
        spin.lineEdit().selectAll()
        QTest.keyClicks(spin.lineEdit(), f"{TYPED_WHOLE},{TYPED_FRACTION}")
        spin.interpretText()
        if spin.value() != float(f"{TYPED_WHOLE}.{TYPED_FRACTION}"):
            problems.append(f"{label}: typing 2,5 gave {spin.value()}")
    assert problems == []


def test_sc_l10n_ui_015_7_the_fields_are_those_the_source_constructs(
    make_window, qtbot
):
    """SC-L10N-UI-015-7: the dialogs opened are every file that builds a field."""
    walked = {Path(inspect.getfile(cls)).name for cls, _ in FIELD_DIALOGS.values()}
    constructing = {
        path.name
        for path in UI_DIR.rglob("*.py")
        if double_spin_constructions(path.read_text(encoding="utf-8")) > 0
    }
    assert constructing == walked, (
        "a file builds a decimal field that the rows above do not open: "
        f"{sorted(constructing - walked)}"
    )


def double_spin_constructions(source: str) -> int:
    """Count the ``QDoubleSpinBox(...)`` constructions in ``source``."""
    return sum(
        1
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and _called_name(node) == "QDoubleSpinBox"
    )


def _called_name(call: ast.Call) -> Optional[str]:
    """The simple name a call is made through (``f`` or ``mod.f``)."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def spin_boxes_without_formatting_locale(source: str) -> List[str]:
    """Return a line for each decimal field that never gets the formatting locale.

    A construction passes only when it is assigned to a name or an attribute and,
    in the same function, ``<that same target>.setLocale(current_formatting_locale())``
    is called (as a bare name or through a module).
    """
    tree = ast.parse(source)
    parents: Dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    problems: List[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _called_name(node) == "QDoubleSpinBox"):
            continue
        assign = parents.get(node)
        function = assign
        while function is not None and not isinstance(
            function, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            function = parents.get(function)
        if not (isinstance(assign, ast.Assign) and len(assign.targets) == 1):
            problems.append(f"line {node.lineno}: not assigned to one target")
            continue
        if function is None:
            problems.append(f"line {node.lineno}: built outside a function")
            continue
        target = ast.unparse(assign.targets[0])
        if not any(
            _sets_formatting_locale(call, target) for call in ast.walk(function)
        ):
            problems.append(f"line {node.lineno}: setLocale(...) is never called on it")
    return problems


def _sets_formatting_locale(node: ast.AST, target_text: str) -> bool:
    """Whether ``node`` is ``<target>.setLocale(current_formatting_locale())``."""
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "setLocale"
        and ast.unparse(node.func.value) == target_text
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Call)
    ):
        return False
    return _called_name(node.args[0]) == "current_formatting_locale"


def test_sc_l10n_ui_015_7_every_decimal_field_construction_sets_the_locale():
    """SC-L10N-UI-015-7: in ui/, each QDoubleSpinBox gets the formatting locale.

    Walks the source of every module of ``ui/``; the count is printed and is
    non-zero.
    """
    total = 0
    problems: List[str] = []
    for path in sorted(UI_DIR.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        total += double_spin_constructions(source)
        problems += [
            f"{path.name} {problem}"
            for problem in spin_boxes_without_formatting_locale(source)
        ]
    print(f"SC-L10N-UI-015-7: {total} QDoubleSpinBox constructions in ui/")
    assert total > 0
    assert problems == []


_PLANTED_GOOD = """
import pixelart_creator.ui.i18n as i18n
class Dialog:
    def __init__(self):
        self._angle = QDoubleSpinBox(self)
        self._angle.setLocale(i18n.current_formatting_locale())
"""
_PLANTED_BARE = """
class Dialog:
    def __init__(self):
        self._angle = QDoubleSpinBox(self)
"""
_PLANTED_OTHER_OBJECT = """
class Dialog:
    def __init__(self):
        self._angle = QDoubleSpinBox(self)
        self._other.setLocale(current_formatting_locale())
"""
_PLANTED_OTHER_LOCALE = """
class Dialog:
    def __init__(self):
        self._angle = QDoubleSpinBox(self)
        self._angle.setLocale(QLocale())
"""
_PLANTED_OTHER_FUNCTION = """
class Dialog:
    def __init__(self):
        self._angle = QDoubleSpinBox(self)
    def later(self):
        self._angle.setLocale(current_formatting_locale())
"""


def test_the_spin_box_walk_accepts_a_set_locale_and_fails_on_each_planted_gap():
    """The controls of the walk: it passes the good source and fails on five gaps."""
    assert spin_boxes_without_formatting_locale(_PLANTED_GOOD) == []
    assert double_spin_constructions(_PLANTED_GOOD) == 1
    for planted in (
        _PLANTED_BARE,
        _PLANTED_OTHER_OBJECT,
        _PLANTED_OTHER_LOCALE,
        _PLANTED_OTHER_FUNCTION,
    ):
        assert spin_boxes_without_formatting_locale(planted), planted


# --------------------------------------------------------------------------- #
# SC-L10N-UI-015-8: an exported file does not depend on the formatting locale  #
# --------------------------------------------------------------------------- #


def _export_under(
    language: str, system: str, out_dir: Path, make_window, qtbot
) -> Tuple[str, Dict[str, bytes]]:
    """Export one document from a window set to ``language``; return its files."""
    window = make_window(system)
    assert window._language_manager.set_language(language) is True
    formatting = current_formatting_locale().name()
    document = animation_document(frames=3, width=12, height=12)
    out_dir.mkdir()
    targets = (
        ExportTarget(ExportRequest(ExportFormat.PNG), str(out_dir / "one.png")),
        ExportTarget(
            ExportRequest(ExportFormat.ATLAS, padding=1), str(out_dir / "atlas.png")
        ),
    )
    controller = window._export_controller
    with qtbot.waitSignal(controller.batchFinished, timeout=15000):
        controller.submit(document, targets)
    return formatting, {path.name: path.read_bytes() for path in out_dir.iterdir()}


def test_sc_l10n_ui_015_8_an_export_is_byte_identical_under_two_locales(
    make_window, qtbot, tmp_path
):
    """SC-L10N-UI-015-8: one document exported under fr and under en is the same."""
    fr_locale, fr_files = _export_under(
        "fr", SPANISH_SYSTEM, tmp_path / "fr", make_window, qtbot
    )
    en_locale, en_files = _export_under(
        "en", SPANISH_SYSTEM, tmp_path / "en", make_window, qtbot
    )

    # The two runs really did format under different locales.
    assert fr_locale == QLocale("fr").name()
    assert en_locale == QLocale("en").name()
    # Both wrote the image files and the atlas' JSON sidecar.
    assert sorted(fr_files) == ["atlas.json", "atlas.png", "one.png"]
    assert sorted(en_files) == sorted(fr_files)
    for name in fr_files:
        assert fr_files[name], name
        assert fr_files[name] == en_files[name], f"{name} differs between fr and en"


# --------------------------------------------------------------------------- #
# The seam itself: one reader, no dialog, no application-wide default          #
# --------------------------------------------------------------------------- #


def qt_calls(source: str, owner: str, name: str) -> int:
    """Count ``owner.name(...)`` calls in ``source``."""
    return sum(
        1
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == owner
    )


def imported_modules(source: str) -> List[str]:
    """Every module name an import statement of ``source`` names."""
    names: List[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
            names += [f"{node.module}.{alias.name}" for alias in node.names]
    return names


def test_the_language_manager_has_one_reader_of_the_system_locale():
    """The seam: ``i18n.py`` calls ``QLocale.system()`` once, and imports no dialog."""
    source = (UI_DIR / "i18n.py").read_text(encoding="utf-8")
    assert qt_calls(source, "QLocale", "system") == 1
    assert [name for name in imported_modules(source) if "dialog" in name.lower()] == []


def test_no_module_sets_an_application_wide_default_locale():
    """SC-L10N-UI-015-4: nothing in the package calls ``QLocale.setDefault``."""
    offenders = [
        path.relative_to(PACKAGE_DIR).as_posix()
        for path in sorted(PACKAGE_DIR.rglob("*.py"))
        if qt_calls(path.read_text(encoding="utf-8"), "QLocale", "setDefault") > 0
    ]
    assert offenders == []


def test_the_default_locale_scan_finds_a_planted_call():
    """The control of the scan above: a source that sets the default is found."""
    planted = "from PySide6.QtCore import QLocale\nQLocale.setDefault(QLocale('fr'))\n"
    assert qt_calls(planted, "QLocale", "setDefault") == 1
    assert qt_calls("x = QLocale('fr')\n", "QLocale", "setDefault") == 0
    assert qt_calls("QLocale.system()\n", "QLocale", "system") == 1
