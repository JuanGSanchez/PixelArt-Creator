"""Acceptance tests for the input-scheme catalogues (REQ-IS-BUILD-002).

Covers `SC-B002-1..3` for the eight strings the input-scheme work wrapped, extracted and
translated: "Cursor feedback", "Add Frame", "Remove Frame", "Fit to
&Content", the last-remaining-frame status notice, the two ``tool_icons``
``ToolGlyphError`` messages, and "unknown theme: %1". Every assertion below
resolves the REAL, compiled ``pixelart_es.qm`` through the production
``LanguageManager``/``QTranslator`` path -- never a string compared to
itself -- so a missing or empty ``es`` catalogue fails these tests outright
(``manager.set_language("es")`` returns ``False`` and the following
assertion raises, or the Spanish literal simply never appears).

``pixelart_en.ts`` is an IDENTITY catalogue for every message that carries no
count: the compiled ``pixelart_en.qm`` gives none of them a translation that
differs from its source text, and an app that shows the English source under
``en`` is correct, not a defect. The count-bearing messages
(REQ-L10N-UI-006) are the exception: they carry finished English singular and
plural forms, so the identity check is narrowed to the messages without a count
and a second check reads those forms instead. Each instrument is shown failing
against a catalogue it must reject (the Spanish one).

All eight compiled catalogues (``en``, ``es``, ``fr``, ``de``, ``ru``,
``zh_CN``, ``ja``, ``ko``) are asserted to load. The eight codes are written
here from the requirement, not read from the product. The Spanish literals
below are unchanged. ``PIXELART_I18N_CATALOGUE_DIR`` names a directory of
compiled ``.qm`` files to measure instead of the shipped ones; it exists to show
these cases fail against an incomplete or wrong set, and unset, the shipped
ones are measured. The ``.ts`` sources are always read from the shipped
directory.

Both themes run automatically via the suite's autouse, parametrised
``theme`` fixture (``testing/suites/ui/conftest.py``); none of these
assertions are theme-dependent (translation text, not colour/QSS), so no
test here requests ``theme`` explicitly -- the same reasoning already
recorded in ``test_cursor_feedback.py``'s module docstring.

D-12 / round-trip-untranslated: ``Shift+A`` is a key-name TOKEN, never
routed through ``tr()`` at all (``ui/main_window.py``'s tool tooltip
concatenates the translated label with the raw ``QKeySequence`` text
produced at runtime). The dedicated test below proves the installed ``es``
catalogue changes the label half and leaves the key-name half character-for-
character identical -- the two-sided guarantee D-12 rules on: a translated
modifier would neither match what the keyboard produces nor the binding
registry (``logic/binding_registry.py``) a later check compares the guide
against.
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path

import pytest
from PySide6.QtCore import QTranslator
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QWidget

from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui import tool_icons
from pixelart_creator.ui.cursor_feedback_overlay import Cursor_Feedback_Overlay
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.timeline_panel import Timeline_Panel
from pixelart_creator.ui.tools import PickerTool

# --------------------------------------------------------------------------- #
# Fixture: install the REAL es catalogue for one test, always revert          #
# --------------------------------------------------------------------------- #


@pytest.fixture
def es_language(qapp):
    """Install the real ``pixelart_es.qm`` for the test body, then revert.

    Asserts the load succeeded so a missing/corrupt catalogue fails at the
    fixture boundary rather than silently leaving the app on English, which
    would make every dependent assertion below a false pass.
    """
    manager = LanguageManager(qapp)
    installed = manager.set_language("es")
    assert installed is True, "the real pixelart_es.qm catalogue failed to load"
    try:
        yield manager
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 1. All eight compiled catalogues load                                       #
# --------------------------------------------------------------------------- #

#: The eight shipped interface languages, in the selector order of REQ-L10N-UI-003.
EIGHT_LANGUAGES = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")

#: Names a directory of compiled catalogues to measure instead of the shipped ones.
CATALOGUE_DIR_ENV = "PIXELART_I18N_CATALOGUE_DIR"

#: The English plural rule, written from the language and not from the product: the
#: first form for one, the second for every other count (zero included). Maps a count
#: to the index of the form that must be shown.
ENGLISH_FORM_FOR_COUNT = {0: 1, 1: 0, 2: 1, 5: 1}


@dataclass(frozen=True)
class _Message:
    """One message of ``pixelart_en.ts`` and, for a count-bearing one, its forms."""

    context: str
    source: str
    disambiguation: str | None
    numerus: bool
    forms: tuple[str, ...]

    @property
    def key(self) -> str:
        """Return a printable name for the message."""
        return f"{self.context}: {self.source}"


def _catalogue_dir() -> Path:
    """Return the directory of compiled catalogues under test."""
    named = os.environ.get(CATALOGUE_DIR_ENV)
    return Path(named) if named else _default_translations_dir()


def _load(code: str) -> QTranslator:
    """Return a plain translator loaded from ``pixelart_<code>.qm``, or fail."""
    directory = _catalogue_dir()
    translator = QTranslator()
    loaded = translator.load(f"pixelart_{code}", str(directory))
    assert loaded, f"pixelart_{code}.qm failed to load from {directory}"
    return translator


def _english_messages() -> list[_Message]:
    """Read every message of the shipped ``pixelart_en.ts`` with ElementTree."""
    path = _default_translations_dir() / "pixelart_en.ts"
    messages: list[_Message] = []
    for ctx in ElementTree.parse(path).getroot().iter("context"):
        name = ctx.findtext("name") or ""
        for message in ctx.iter("message"):
            forms = tuple(
                form.text or "" for form in message.iterfind("translation/numerusform")
            )
            source = message.findtext("source") or ""
            numerus = message.get("numerus") == "yes"
            comment = message.findtext("comment")
            messages.append(_Message(name, source, comment, numerus, forms))
    return messages


def _shown(translator: QTranslator, message: _Message, count: int = -1) -> str:
    """Return the text one compiled catalogue gives a message, or ``""`` on a miss."""
    text = translator.translate(
        message.context, message.source, message.disambiguation, count
    )
    return text or ""


def _identity_departures(
    translator: QTranslator, messages: list[_Message]
) -> list[str]:
    """Return the messages WITHOUT a count whose compiled text differs from the source.

    A miss (no compiled translation) is the source-text fallback and is identity.
    Fails when no message without a count is examined, because a verdict over
    nothing proves nothing.
    """
    plain = [message for message in messages if not message.numerus]
    if not plain:
        raise AssertionError("no message without a count was examined")
    return [
        message.key
        for message in plain
        if _shown(translator, message) not in ("", message.source)
    ]


def _form_problems(translator: QTranslator, messages: list[_Message]) -> list[str]:
    """Return the count-bearing messages shown with the wrong English form.

    Each message is asked for the counts of :data:`ENGLISH_FORM_FOR_COUNT`; the text
    shown must be the ``.ts`` form that the English rule picks, with ``%n`` replaced
    by the count. Fails when no count-bearing message is examined.
    """
    counted = [message for message in messages if message.numerus]
    if not counted:
        raise AssertionError("no count-bearing message was examined")
    problems: list[str] = []
    for message in counted:
        for count, index in ENGLISH_FORM_FOR_COUNT.items():
            expected = message.forms[index].replace("%n", str(count))
            shown = _shown(translator, message, count).replace("%n", str(count))
            if shown != expected:
                problems.append(f"{message.key} (n={count})")
    return problems


@pytest.mark.parametrize("code", EIGHT_LANGUAGES)
def test_req_is_build_002_every_shipped_qm_catalogue_loads(qapp, code):
    """REQ-IS-BUILD-002: each of the eight ``pixelart_<code>.qm`` files loads.

    Each compiled catalogue must load as a valid, non-empty ``.qm`` and have its
    ``.ts`` source beside it. ``en`` included: it is the identity catalogue for
    messages without a count and carries finished English forms for the rest, so
    it is not empty."""
    directory = _catalogue_dir()
    assert (directory / f"pixelart_{code}.qm").is_file()
    assert (_default_translations_dir() / f"pixelart_{code}.ts").is_file()
    translator = _load(code)
    print(f"{code}: loaded, empty={translator.isEmpty()}")
    assert translator.isEmpty() is False


def test_req_is_build_002_exactly_eight_catalogues_are_shipped(qapp):
    """REQ-IS-BUILD-002: the directory holds the eight compiled catalogues and no
    other, and a manager over it offers the same eight."""
    directory = _catalogue_dir()
    on_disk = sorted(
        path.stem.removeprefix("pixelart_") for path in directory.glob("pixelart_*.qm")
    )
    offered = LanguageManager(qapp, translations_dir=directory).available_languages()
    print(f"compiled on disk: {len(on_disk)} {on_disk}; offered: {len(offered)}")
    assert on_disk == sorted(EIGHT_LANGUAGES)
    assert sorted(offered) == sorted(EIGHT_LANGUAGES)
    assert offered[0] == FALLBACK_LANGUAGE


# --------------------------------------------------------------------------- #
# 1b. The English catalogue: identity for messages without a count, English   #
#     forms for the count-bearing ones (the identity claim, narrowed)         #
# --------------------------------------------------------------------------- #


def test_req_is_build_002_en_catalogue_is_identity_for_messages_without_a_count(qapp):
    """REQ-IS-BUILD-002: for every message of ``pixelart_en.ts`` that carries no
    count, ``pixelart_en.qm`` gives no text that differs from the source (the
    source-text fallback). Count-bearing messages are judged by the next test."""
    messages = _english_messages()
    plain = sum(1 for message in messages if not message.numerus)
    departures = _identity_departures(_load("en"), messages)
    print(
        f"en identity: {len(messages)} messages, {plain} without a count examined, "
        f"{len(departures)} differ from their source"
    )
    assert plain > 0
    assert not departures, ascii(departures[:5])


def test_req_is_build_002_en_catalogue_has_english_forms_for_count_messages(qapp):
    """REQ-L10N-UI-006 / REQ-IS-BUILD-002: every count-bearing message of
    ``pixelart_en.ts`` has two finished English forms, and ``pixelart_en.qm``
    shows the singular for one and the plural for zero, two and five."""
    messages = _english_messages()
    counted = [message for message in messages if message.numerus]
    for message in counted:
        assert len(message.forms) == 2 and all(message.forms), ascii(message.key)
    different = sum(1 for message in counted if message.forms[0] != message.forms[1])
    problems = _form_problems(_load("en"), messages)
    counts = sorted(ENGLISH_FORM_FOR_COUNT)
    print(
        f"en forms: {len(counted)} count-bearing messages, {different} with "
        f"two different forms, {len(problems)} problems over counts {counts}"
    )
    # A verdict that cannot tell the two forms apart proves nothing.
    assert different > 0
    assert not problems, ascii(problems[:5])


def test_the_identity_and_form_checks_reject_a_catalogue_that_translates(qapp):
    """Control: both instruments, run over the Spanish catalogue, report problems.

    Spanish translates the messages without a count and gives the count-bearing
    ones Spanish forms, so each check must fail; one that could not fail would say
    nothing when it passes. Each instrument also refuses to give a verdict over no
    message at all."""
    messages = _english_messages()
    spanish = _load("es")
    departures = _identity_departures(spanish, messages)
    problems = _form_problems(spanish, messages)
    print(f"control: es differs on {len(departures)}, wrong forms {len(problems)}")
    assert len(departures) > 0
    assert len(problems) > 0
    without_count = [message for message in messages if not message.numerus]
    with pytest.raises(AssertionError, match="no message without a count"):
        _identity_departures(spanish, [])
    with pytest.raises(AssertionError, match="no count-bearing message"):
        _form_problems(spanish, without_count)


# --------------------------------------------------------------------------- #
# 2. "Cursor feedback" -- Cursor_Feedback_Overlay accessible name             #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_cursor_feedback_accessible_name_resolves_under_es(qtbot, qapp):
    """SC-B002-1: the overlay's accessible name is "Retroalimentación del
    cursor" under the real es catalogue -- proven live: constructed under
    English (asserted first), THEN switched, not merely read once already-
    translated at construction time."""
    viewport = QWidget()
    qtbot.addWidget(viewport)
    overlay = Cursor_Feedback_Overlay(viewport)
    qtbot.addWidget(overlay)
    assert overlay.accessibleName() == "Cursor feedback"

    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        assert overlay.accessibleName() == "Retroalimentación del cursor"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 3. "Add Frame" / "Remove Frame" -- Timeline_Panel action text + tooltip,    #
#    and the pushed undo command's OWN label (self.tr() at push time)         #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_timeline_panel_frame_actions_resolve_under_es(
    qtbot, qapp, make_document
):
    """SC-B002-1: Add Frame / Remove Frame panel action text resolves under
    es and re-sets LIVE on an installed-translator LanguageChange (the panel
    is constructed under English first, proving the switch, not construction
    order, is what changes the text)."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    stack = QUndoStack()
    document = make_document()
    panel.set_context(document, stack, lambda: None)

    assert panel._add_action.text() == "Add Frame"
    assert panel._remove_action.text() == "Remove Frame"

    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        assert panel._add_action.text() == "Añadir fotograma"
        assert panel._remove_action.text() == "Eliminar fotograma"

        # The undoable command's own label is produced by self.tr() at PUSH
        # time (Timeline_Panel._on_add/_on_remove), not cached from
        # construction -- exercise the real push path, not the label alone.
        panel._on_add()
        assert stack.undoText() == "Añadir fotograma"
        panel._on_remove()
        assert stack.undoText() == "Eliminar fotograma"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_sc_b002_1_timeline_grid_view_remove_frame_context_resolves_under_es(
    qapp, es_language
):
    """SC-B002-1: ``Timeline_Grid_View``'s OWN "Remove Frame" catalogue entry
    (a separate context from ``Timeline_Panel``'s -- Ctrl+right-click on the
    grid pushes its own ``self.tr("Remove Frame")``, ``ui/timeline_grid_view.py``)
    resolves under es too. Uses the exact context Qt's moc generates for that
    class (its class name) -- the same lookup ``self.tr()`` performs
    internally -- rather than re-wiring the grid's document/stack binding
    just to read a label."""
    from PySide6.QtCore import QCoreApplication

    resolved = QCoreApplication.translate("Timeline_Grid_View", "Remove Frame")
    assert resolved == "Eliminar fotograma"


def test_sc_b002_1_main_window_canvas_add_frame_command_resolves_under_es(qtbot, qapp):
    """SC-B002-1: the Ctrl+left-click canvas add-frame path
    (``Main_Window._on_canvas_add_frame_requested``) pushes its OWN
    "Add Frame" catalogue entry (``ui/main_window.py`` context, distinct
    from ``Timeline_Panel``'s), and it resolves under es."""
    win = Main_Window()
    qtbot.addWidget(win)
    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        win._on_canvas_add_frame_requested()
        record = win.active_tab()
        assert record is not None
        assert record.stack.undoText() == "Añadir fotograma"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 4. "Fit to &Content" -- new View-menu entry, changeEvent/LanguageChange     #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_fit_content_action_retranslates_live_under_es(qtbot, qapp):
    """SC-B002-1 + Article V.2: the new View-menu "Fit to &Content" entry is
    re-set by ``changeEvent``/``LanguageChange`` -- constructed under
    English, THEN switched, proving the live re-set (not a string translated
    once at construction and never again, which would look correct in any
    test that never switches language, per the task brief)."""
    win = Main_Window()
    qtbot.addWidget(win)
    assert win._fit_content_action.text() == "Fit to &Content"

    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        assert win._fit_content_action.text() == "Ajustar al &contenido"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 5. Last-remaining-frame status notice                                       #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_last_frame_removal_notice_resolves_under_es(qtbot, qapp):
    """SC-B002-1: ``Main_Window._notify_last_frame_removal_refused``'s
    status-bar notice resolves under es. Transient (built fresh on every
    emission, like its ``_notify_layer_locked`` sibling), so es is installed
    BEFORE the call -- this is the same "re-resolve at call time" shape the
    existing ``test_d05_notice_retranslates_on_language_change`` proves for
    that sibling notice, not a persisted-label ``changeEvent`` re-set."""
    win = Main_Window()
    qtbot.addWidget(win)
    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        win._notify_last_frame_removal_refused()
        assert win.statusBar().currentMessage() == (
            "Este es el último fotograma restante; "
            "un documento debe conservar al menos uno."
        )
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


# --------------------------------------------------------------------------- #
# 6/7/8. tool_icons.ToolGlyphError messages + theme._roles "unknown theme"   #
# --------------------------------------------------------------------------- #


def test_sc_b002_1_unknown_tool_glyph_id_message_resolves_under_es(qapp, es_language):
    """SC-B002-1: ``tool_icons``' "unknown tool glyph id: %1" resolves under
    es with the bad id substituted after translation (``.replace("%1", ...)``,
    ``ui/tool_icons.py``)."""
    with pytest.raises(tool_icons.ToolGlyphError) as excinfo:
        tool_icons._glyph_resource("not-a-real-tool")
    assert (
        str(excinfo.value) == "id de glifo de herramienta desconocido: not-a-real-tool"
    )


def test_sc_b002_1_missing_tool_glyph_asset_message_resolves_under_es(
    qapp, es_language, monkeypatch, tmp_path
):
    """SC-B002-1: ``tool_icons``' "missing tool glyph asset for: %1" resolves
    under es. Forces the missing-asset branch (a KNOWN id, an EMPTY glyph
    root) by monkeypatching ``_glyphs_root`` to an empty ``tmp_path`` --
    never touching the real, shipped glyph assets."""
    monkeypatch.setattr(tool_icons, "_glyphs_root", lambda: tmp_path)
    with pytest.raises(tool_icons.ToolGlyphError) as excinfo:
        tool_icons._glyph_resource("pencil")
    assert str(excinfo.value) == "falta el recurso de glifo de herramienta para: pencil"


def test_sc_b002_1_unknown_theme_message_resolves_under_es_theme_context(
    qapp, es_language
):
    """SC-B002-1: ``ui/theme.py``'s "unknown theme: %1" (``theme`` context)
    resolves under es with the bad name substituted."""
    with pytest.raises(ValueError) as excinfo:
        theme_module._roles("not-a-real-theme")
    assert str(excinfo.value) == "tema desconocido: not-a-real-theme"


def test_sc_b002_1_unknown_theme_message_resolves_under_es_tool_icons_context(
    qapp, es_language
):
    """SC-B002-1: the SAME source text has a SECOND catalogue entry under the
    ``tool_icons`` context (``ui/tool_icons.py``'s ``_tint_colour``, reached
    through the public ``tool_icon()`` entry point) -- also resolves under
    es. Two distinct ``lupdate`` message locations for one English sentence,
    both must carry a translation, not just one."""
    with pytest.raises(tool_icons.ToolGlyphError) as excinfo:
        tool_icons.tool_icon("pencil", theme="not-a-real-theme")
    assert str(excinfo.value) == "tema desconocido: not-a-real-theme"


# --------------------------------------------------------------------------- #
# D-12: a key-name literal round-trips UNTRANSLATED                           #
# --------------------------------------------------------------------------- #


def test_d12_shift_a_key_literal_round_trips_untranslated_under_es(qtbot, qapp):
    """D-12: ``Shift+A`` (the picker tool's shortcut) must be ``Shift+A`` in
    Spanish too -- a translated modifier would match neither what the
    keyboard actually produces nor the binding registry a later check
    compares the guide against.

    The picker tool's tooltip concatenates the translated label with the
    RAW ``QKeySequence`` text (``ui/main_window.py``, never routed through
    ``tr()``). This test would FAIL if the es catalogue were absent -- the
    label half stays "Colour picker" (English) and the two assertions on
    the Spanish label text below fail outright -- so a missing catalogue
    cannot read as a pass here."""
    win = Main_Window()
    qtbot.addWidget(win)
    picker_action = win._tool_actions[PickerTool.tool_id]
    assert picker_action.shortcut().toString() == "Shift+A"
    en_tooltip = picker_action.toolTip()
    assert en_tooltip == "Colour picker (Shift+A)"

    manager = win._language_manager
    try:
        assert manager.set_language("es") is True
        qapp.processEvents()
        es_tooltip = picker_action.toolTip()
        # Proves the es catalogue is really active (fails if absent/empty):
        assert es_tooltip != en_tooltip
        assert "Selector de color" in es_tooltip
        # The key-name TOKEN is untouched -- untranslated, character for
        # character, exactly as ruling D-12 requires.
        assert "Shift+A" in es_tooltip
        assert es_tooltip == "Selector de color (Shift+A)"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)
