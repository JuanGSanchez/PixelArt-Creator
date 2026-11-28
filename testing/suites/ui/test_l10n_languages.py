"""The eight interface languages at the application level: start-up and selector.

What is covered, by scenario id (the six-interface-languages feature):

* **SC-L10N-UI-001-1** exactly eight interface languages are available, and the
  count printed is 8;
* **SC-L10N-UI-001-2** on one live main window every language is chosen in turn
  through the real selector entry and then English again: after each choice the
  File menu title is that language's translation of ``&File``, nothing is raised
  and the interface ends in English;
* **SC-L10N-UI-002-1, -002-2, -002-3** the start-up language chosen from an
  injected preferred-language list on the real application with the real
  catalogues, nothing patched globally: the 15 single-entry rows, the first-match
  row and the six Traditional-script rows (``["zh_TW", "fr_FR"]`` starts in
  French; the sixth row ``["zh-Hant-CN", "ko"]`` starts in Korean);
* **SC-L10N-UI-003-1, -003-2** the selector shows the eight endonyms, byte for
  byte, in the user's order, under each of the eight active languages, and no
  entry is a raw language code;
* **SC-L10N-UI-012-2, at the application level** the family list each selector
  entry carries: the Simplified entry holds the Simplified-form family and not
  the Japanese-form one, the Japanese entry the reverse, in both font modes; with
  "Use system font" on and a Han-capable platform family forced both CJK families
  precede the platform family in each entry's list, and with a Han-free one the
  platform family stays first. Whether each Han character is really drawn from
  the right face is read at glyph level, in the glyph-level suite, not here;
* **REQ-L10N-UI-003** the entries are reachable from the keyboard, the active
  entry shows a focus indication, and each entry is named by its endonym;
* **REQ-L10N-UI-009 to -012, the family-list tag at the application level** each
  selector entry's font, the interface font and the guide page font carry exactly
  the tag flags their list was allocated (read through the product's registry and
  table, never restated here); where the Simplified and the Japanese labels share
  a first family their tags differ; the interface font follows the form on a live
  ``zh_CN`` -> ``ja`` -> ``zh_CN`` switch; and a walk over every font the
  application holds finds every list of two or more families tagged and no
  one-family font carrying a tag flag.

This module is the application-level evidence for the reading of Article V
section 2 that the plan states: a language's self-name is data, the same in every
language, not translatable text. The labels are compared as UTF-8 bytes under all
eight active languages, and no shipped catalogue offers any of them for
translation.

Every window is built from the state a just-started process is in, with the style
and mode planted in the isolated settings store and read back from the window, so
every selector and font check runs in both modes of every style (six
combinations). The start-up rows and the catalogue checks need no window and run
once.

Instruments and their controls. A check that reports "nothing wrong" is only worth
something if it would have reported a failure, so each one is shown failing:

* the six start-up rows against a stand-in that stops at the first
  Traditional-script entry;
* the "tags differ" check against a ``chain_font`` that applies no tag;
* the font walk against a widget given a bare ``setFamilies`` list;
* the process-locale guard against a changed default locale and against a language
  left installed.

The platform family is forced, never measured: the offscreen platform cannot
answer whether a family holds Han characters, so the answer is injected and the
platform's own font is replaced by a named stand-in for the length of the test. No
test here reads a glyph run, so the order in which Qt returns the runs of a
multi-run layout plays no part. The system locale and the default locale are never
patched by this module, and a guard fails any test that leaves either, or the
active language, changed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QLocale, QPoint, Qt, QTranslator
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QWidget

import pixelart_creator.ui.main_window as main_window_module
from pixelart_creator.logic import font_chain, locale_match
from pixelart_creator.ui import app_font, i18n
from pixelart_creator.ui.i18n import LanguageManager, apply_source_mnemonic
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import DEFAULT_STYLE, THEME_LIGHT, apply_theme
from testing.suites.ui.conftest import assert_settings_isolated
from testing.suites.ui.test_app_font import (
    allocated_tag_bits,
    chain_problems,
    choose_language,
    inject_platform_font,
    open_guide,
    open_window,
    tag_bits,
)
from testing.suites.ui.test_theme import _COMBO_IDS, COMBOS, Combo

#: The eight shipped language codes, in the order the selector shows them.
CODES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")

#: The eight endonyms of the selector, in the same order, as the requirement
#: spells them. Compared as UTF-8 bytes.
ENDONYMS: Tuple[str, ...] = (
    "English",
    "Español",
    "Français",
    "Deutsch",
    "Русский",
    "简体中文",
    "日本語",
    "한국어",
)

#: The three bundled CJK families, by the names they register under.
SC_FAMILY = "Nifen Art CJK SC"
JP_FAMILY = "Nifen Art CJK JP"
KR_FAMILY = "Nifen Art CJK KR"
CJK_FAMILIES = (SC_FAMILY, JP_FAMILY, KR_FAMILY)

#: The bundled Latin pixel family.
NIFEN = app_font.NIFEN_ART_FAMILY

#: Named stand-ins for the platform's own family when it is forced.
HAN_FREE_PLATFORM = "Probe Platform Latin"
HAN_CAPABLE_PLATFORM = "Probe Platform Han"

#: One Language-menu entry as read from the window: its code, its label as UTF-8
#: bytes, its family list and its chain-tag bits.
Shown = Tuple[str, bytes, Tuple[str, ...], int]

#: One font the application holds, with a label that names where it was found.
Held = Tuple[str, QFont]

#: SC-L10N-UI-002-1 (rows 1 to 6 are the job's own, the rest follow the user's
#: rulings on the Chinese script).
STARTUP_ROWS: List[Tuple[str, str]] = [
    ("fr_FR", "fr"),
    ("de_DE", "de"),
    ("ru_RU", "ru"),
    ("zh_CN", "zh_CN"),
    ("ko_KR", "ko"),
    ("ja_JP", "ja"),
    ("zh-Hans-CN", "zh_CN"),
    ("zh", "zh_CN"),
    ("fr-CA", "fr"),
    ("de_CH", "de"),
    ("zh_SG", "zh_CN"),
    ("zh_TW", "en"),
    ("zh-Hant-HK", "en"),
    ("pt_BR", "en"),
    ("zh-Hans-TW", "zh_CN"),
]

#: SC-L10N-UI-002-2: the first preference that maps wins.
FIRST_MATCH_ROW: Tuple[List[str], str] = (["it_IT", "ja_JP", "fr_FR"], "ja")

#: SC-L10N-UI-002-3: a Traditional-script entry is skipped, never a stop.
SKIP_ROWS: List[Tuple[List[str], str]] = [
    (["zh_TW", "fr_FR"], "fr"),
    (["zh-Hant", "ja_JP"], "ja"),
    (["zh-HK", "de_DE"], "de"),
    (["zh_MO", "pt_BR"], "en"),
    (["zh-Hant-TW", "zh_CN"], "zh_CN"),
    (["zh-Hant-CN", "ko"], "ko"),
]

#: A Traditional-script tag, as the stand-in of the start-up control reads it.
_TRADITIONAL = re.compile(r"zh[-_](?:tw|hk|mo|hant)", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture with one known starting sheet.

    A ``Main_Window`` restores the stored combination and ignores this one; the
    combinations under test are parametrised below (``combo``) and planted in the
    store instead.
    """
    apply_theme(qapp, THEME_LIGHT, DEFAULT_STYLE)
    return THEME_LIGHT


@pytest.fixture(autouse=True)
def _store_is_isolated(settings_store: Path) -> Path:
    """Fail BEFORE any write if the settings store is not the temporary one."""
    assert_settings_isolated(settings_store)
    return settings_store


@pytest.fixture(autouse=True)
def _leave_the_font_as_found(qapp) -> Iterator[None]:
    """Put the application font back after the test, whatever the test did to it."""
    yield
    qapp.setFont(app_font._target_font(False))


@pytest.fixture(autouse=True)
def _process_locale_unchanged(qapp) -> Iterator[None]:
    """Fail a test that leaves the process locale or the active language changed."""
    before = locale_state()
    system_before = QLocale.system
    yield
    leaks = locale_leaks(before, system_before)
    assert not leaks, "the test left the process locale changed: " + "; ".join(leaks)


@pytest.fixture(params=COMBOS, ids=_COMBO_IDS)
def combo(request: pytest.FixtureRequest) -> Combo:
    """One style x mode combination (six)."""
    chosen: Combo = request.param
    return chosen


@pytest.fixture(params=[False, True], ids=["nifen", "system-font"])
def system_font(request: pytest.FixtureRequest) -> bool:
    """The font mode a window starts in: Nifen Art, then "Use system font"."""
    chosen: bool = request.param
    return chosen


@pytest.fixture(params=[False, True], ids=["forced-family-only", "bundled-faces-too"])
def bundled_detected(request: pytest.FixtureRequest) -> bool:
    """Which answer the injected detector gives for the three bundled CJK faces.

    ``False``: only the forced platform family is answered True, so the detector
    says False for every bundled face. ``True``: the three bundled faces are
    answered True as well, which is what the real detector says for faces that
    hold Han. A fix that held under one answer only would fail under the other.
    """
    chosen: bool = request.param
    return chosen


@pytest.fixture
def platform_snapshot_kept() -> Iterator[None]:
    """Put the product's platform snapshot back after a test that injects into it."""
    app_font.capture_platform_font()
    saved = dict(app_font._platform)
    yield
    app_font._platform.update(saved)


@pytest.fixture
def english_afterwards() -> Iterator[List[Main_Window]]:
    """Put every window given to the list back to English when the test ends."""
    windows: List[Main_Window] = []
    yield windows
    for window in windows:
        if shiboken6.isValid(window):
            window._language_manager.set_language("en")


@pytest.fixture
def manager(qapp) -> Iterator[LanguageManager]:
    """The application's manager for a test with no window, English again afterwards."""
    started = LanguageManager(qapp)
    started.set_language("en")
    try:
        yield started
    finally:
        started.set_language("en")


@pytest.fixture
def force_cjk_holders(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Sequence[str]], None]:
    """Return a function that injects which families hold Han or Hangul.

    Every family named is answered True and every other False, in the product's
    own detector as the application font and the selector entries call it, with
    the answers cached by the font module cleared. Undone with the test.
    """

    def _force(families: Sequence[str]) -> None:
        held = frozenset(families)

        def holds(family: str) -> bool:
            return family in held

        monkeypatch.setattr(app_font, "primary_holds_cjk", holds)
        monkeypatch.setattr(main_window_module, "primary_holds_cjk", holds)
        monkeypatch.setattr(app_font, "_holds_cjk_cache", {})

    return _force


@pytest.fixture
def start_window(
    qtbot,
    english_afterwards: List[Main_Window],
    platform_snapshot_kept: None,
    force_cjk_holders: Callable[[Sequence[str]], None],
) -> Callable[..., Main_Window]:
    """Return a function that opens a main window from a just-started process.

    The platform's own family is replaced by a named stand-in that holds no Han
    character (or one that does, when ``han_capable`` is set) and the detector is
    told so, then the window is built in the font mode asked for and read back.
    """

    def _start(
        chosen: Combo,
        *,
        system_font: bool = False,
        han_capable: bool = False,
        bundled_hold_han: bool = False,
    ) -> Main_Window:
        family = HAN_CAPABLE_PLATFORM if han_capable else HAN_FREE_PLATFORM
        inject_platform_font(family)
        holders: List[str] = [family] if han_capable else []
        if bundled_hold_han:
            holders.extend(CJK_FAMILIES)
        force_cjk_holders(holders)
        window = open_window(
            qtbot, chosen.mode, chosen.style, use_system_font=system_font
        )
        english_afterwards.append(window)
        assert window.use_system_font() == system_font
        return window

    return _start


# --------------------------------------------------------------------------- #
# What is read: the process locale, the catalogues, the selector, the fonts     #
# --------------------------------------------------------------------------- #


def say(capsys: pytest.CaptureFixture, text: str) -> None:
    """Print a line that reaches the terminal even without ``-s``.

    The line never raises on a character the stream's encoding cannot hold: the
    first try prints it as it is, and only on ``UnicodeEncodeError`` is it written
    again with the character it cannot hold as its escape.
    """
    line = f"\n[l10n] {text}"
    with capsys.disabled():
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", None) or "ascii"
            kept = line.encode(encoding, "backslashreplace").decode(encoding)
            print(kept, flush=True)


def locale_state() -> Dict[str, str]:
    """Return what makes up the process locale and the active interface language."""
    return {
        "default locale": QLocale().name(),
        "system locale": QLocale.system().name(),
        "interface language": i18n.current_ui_language(),
        "File title as the application translates it": QCoreApplication.translate(
            "Main_Window", "&File"
        ),
    }


def locale_leaks(before: Dict[str, str], system_before: object) -> List[str]:
    """Return how the process locale now differs from ``before``, one line each.

    ``system_before`` is ``QLocale.system`` as it was at the moment ``before`` was
    taken. The attribute is compared with that object by identity, never by its
    ``id``, so a replacement made after the snapshot is named, and one made by
    something else earlier in the process is not charged to the test that follows.
    """
    after = locale_state()
    leaks = [
        f"{name}: {before[name]!r} became {after[name]!r}"
        for name in before
        if before[name] != after[name]
    ]
    if QLocale.system is not system_before:
        leaks.append("QLocale.system was replaced")
    return leaks


def catalogue_file_title(code: str) -> str:
    """Return the File menu title the catalogue of ``code`` gives, read independently.

    A plain translator loads the compiled catalogue and is asked for the
    translation of ``&File`` in the window's context; the access key is then fixed
    to the English source's letter by the product's pure function, which is what
    every title in every language goes through. English is the source text.
    """
    if code == "en":
        return "&File"
    translator = QTranslator()
    folder = i18n._default_translations_dir()
    assert translator.load(f"pixelart_{code}", str(folder)), f"no catalogue for {code}"
    raw = translator.translate("Main_Window", "&File")
    assert raw, f"the {code} catalogue has no translation of &File"
    return apply_source_mnemonic("&File", raw)


def startup_problems(
    started: LanguageManager, preferred: Sequence[str], expected: str
) -> List[str]:
    """Start the application from ``preferred`` and return what is wrong with it.

    The list is handed to the manager, never read from the system, and the real
    catalogue is installed on the real application: the language chosen, the
    language the manager reports, and the File title the application now
    translates to must all be ``expected``'s.
    """
    problems: List[str] = []
    installed = started.install_from_locale(list(preferred))
    if installed != expected:
        problems.append(
            f"{list(preferred)}: installed {installed!r}, wanted {expected!r}"
        )
    if started.current_language() != expected:
        problems.append(
            f"{list(preferred)}: the manager reports {started.current_language()!r}, "
            f"wanted {expected!r}"
        )
    live = QCoreApplication.translate("Main_Window", "&File")
    if live != catalogue_file_title(expected):
        problems.append(
            f"{list(preferred)}: the application translates &File to {live!r}, "
            f"wanted {catalogue_file_title(expected)!r}"
        )
    return problems


def selector_snapshot(win: Main_Window) -> List[Shown]:
    """Return each Language entry's code, label bytes, family list and tag bits."""
    return [
        (
            code,
            action.text().encode("utf-8"),
            tuple(action.font().families()),
            tag_bits(action.font()),
        )
        for code, action in win._language_entry_actions
    ]


def selector_problems(shown: Sequence[Shown]) -> List[str]:
    """Return what is wrong with the selector's labels and Han forms.

    The entries are the eight in the user's order, each label equals its endonym
    as bytes, none is a raw language code, the Simplified entry holds the
    Simplified-form family and not the Japanese one, and the Japanese entry the
    reverse.
    """
    problems: List[str] = []
    codes = [code for code, _text, _families, _bits in shown]
    if codes != list(CODES):
        problems.append(f"the entries are {codes}, wanted {list(CODES)}")
    texts = [text for _code, text, _families, _bits in shown]
    wanted = [label.encode("utf-8") for label in ENDONYMS]
    if texts != wanted:
        problems.append(f"the label bytes are {texts}, wanted {wanted}")
    for _code, text, _families, _bits in shown:
        if text.decode("utf-8") in CODES:
            problems.append(f"an entry is the raw language code {text!r}")
    families = {code: fams for code, _text, fams, _bits in shown}
    simplified = families.get("zh_CN", ())
    japanese = families.get("ja", ())
    if SC_FAMILY not in simplified or JP_FAMILY in simplified:
        problems.append(
            f"the Simplified entry wants {SC_FAMILY!r} and not {JP_FAMILY!r}, "
            f"got {list(simplified)}"
        )
    if JP_FAMILY not in japanese or SC_FAMILY in japanese:
        problems.append(
            f"the Japanese entry wants {JP_FAMILY!r} and not {SC_FAMILY!r}, "
            f"got {list(japanese)}"
        )
    return problems


def tags_differ_problems(win: Main_Window) -> List[str]:
    """Return what is wrong with the tags of the two Han labels' fonts.

    The Simplified and the Japanese label share a first family in the Nifen mode
    and with a Han-free platform family, so Qt's font cache could not tell their
    lists apart without a tag: they must share a first family and carry different
    tag bits.
    """
    fonts = {code: action.font() for code, action in win._language_entry_actions}
    simplified, japanese = fonts["zh_CN"], fonts["ja"]
    first_simplified = simplified.families()[0]
    first_japanese = japanese.families()[0]
    if first_simplified != first_japanese:
        return [
            f"the two labels do not share a first family: {first_simplified!r} and "
            f"{first_japanese!r}"
        ]
    if tag_bits(simplified) == tag_bits(japanese):
        return [
            f"the two labels share the first family {first_simplified!r} and carry "
            f"the same tag bits {tag_bits(simplified):#x}"
        ]
    return []


def held_fonts(win: Main_Window, dialog: Any) -> List[Held]:
    """Return every font the application holds, each with where it was found.

    The application font and each per-class font the font module restores, every
    widget's font under the main window and under the guide window, the guide
    page's own default font, and every action's font in the window's menus.
    """
    held: List[Held] = [("application font", QFont(QApplication.font()))]
    for name in app_font._PLATFORM_CLASS_FONTS:
        held.append((f"class font {name}", app_font._class_font(name)))
    for root in (win, dialog):
        for widget in [root, *root.findChildren(QWidget)]:
            held.append(
                (
                    f"{type(widget).__name__}[{widget.objectName()}] "
                    f"in {type(root).__name__}",
                    widget.font(),
                )
            )
    held.append(("guide page font", dialog._content_view.document().defaultFont()))
    seen: set[Any] = set()
    actions = list(win.findChildren(QAction))
    for menu in win.findChildren(QMenu):
        actions.extend(menu.actions())
    for action in actions:
        pointer = shiboken6.getCppPointer(action)[0]
        if pointer in seen:
            continue
        seen.add(pointer)
        held.append((f"action '{action.text()}'", action.font()))
    return held


def walk_problems(held: Sequence[Held]) -> List[str]:
    """Return what is wrong with the tag of each font in ``held``.

    A font with two or more families must carry exactly the tag its list was
    allocated, read through the product's registry and table, and never no tag; a
    font with one family must carry no flag of the table.
    """
    problems: List[str] = []
    for label, font in held:
        families = list(font.families()) or [font.family()]
        bits = tag_bits(font)
        if len(families) >= 2:
            allocated = allocated_tag_bits(families)
            if bits == 0:
                problems.append(f"{label}: untagged chain {families}")
            elif bits != allocated:
                problems.append(
                    f"{label}: {families} carries tag bits {bits:#x}, the allocated "
                    f"tag is {allocated:#x}"
                )
        elif bits != 0:
            problems.append(
                f"{label}: one-family font {families} carries tag {bits:#x}"
            )
    return problems


def lists_per_first_family(held: Sequence[Held]) -> Dict[str, List[Tuple[str, ...]]]:
    """Return, for each first family, the distinct family lists the fonts carry."""
    table: Dict[str, List[Tuple[str, ...]]] = {}
    for _label, font in held:
        families = tuple(font.families()) or (font.family(),)
        bucket = table.setdefault(families[0], [])
        if families not in bucket:
            bucket.append(families)
    return table


def platform_order_problems(
    label: str, families: Sequence[str], platform: str
) -> List[str]:
    """Return what is wrong with ``families`` as a Han-capable platform list.

    The platform family must be in the list, the Hangul family and at least one Han
    family must be in it, and every bundled CJK family must come before the
    platform family.
    """
    if platform not in families:
        return [f"{label}: {platform!r} is not in the list {list(families)}"]
    problems: List[str] = []
    place = list(families).index(platform)
    cjk = [family for family in families if family in CJK_FAMILIES]
    if KR_FAMILY not in cjk or len(cjk) < 2:
        problems.append(f"{label}: the CJK families are {cjk} in {list(families)}")
    behind = [family for family in cjk if list(families).index(family) > place]
    if behind:
        problems.append(f"{label}: {behind} follow {platform!r} in {list(families)}")
    return problems


def entry_lists(win: Main_Window) -> Dict[str, Tuple[str, ...]]:
    """Return each Language entry's family list, by language code."""
    return {
        code: tuple(action.font().families())
        for code, action in win._language_entry_actions
    }


def state_problems(held: Sequence[Held], *, system: bool, language: str) -> List[str]:
    """Return what is wrong with the application font and every held font's tag."""
    primary = HAN_FREE_PLATFORM if system else NIFEN
    problems = chain_problems(
        "application font", QApplication.font(), primary, language
    )
    return problems + walk_problems(held)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-001-1, -001-2: the eight languages, switched live                  #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_001_1_exactly_eight_languages_are_available(
    capsys, manager: LanguageManager
) -> None:
    """SC-L10N-UI-001-1: the set is the eight codes, there are eight, and it is printed.

    The manager lists the languages from the compiled catalogues next to the
    package; the folder itself must hold exactly eight of them.
    """
    available = manager.available_languages()
    assert set(available) == set(CODES), available
    assert len(available) == 8, available
    folder = i18n._default_translations_dir()
    shipped = sorted(path.name for path in folder.glob("pixelart_*.qm"))
    assert shipped == sorted(f"pixelart_{code}.qm" for code in CODES), shipped
    say(capsys, f"available interface languages: {len(available)} {sorted(available)}")


def test_sc_l10n_ui_001_2_every_language_switches_live_and_ends_in_english(
    qtbot, capsys, combo: Combo, start_window
) -> None:
    """SC-L10N-UI-001-2: each language in turn, then English, through the real entry.

    One window opens in English; each of the eight languages is chosen through its
    Language-menu entry (the entry is triggered, as the keyboard and assistive
    technology do), the change signal names the chosen code, and the File menu
    title is that language's translation of ``&File`` read from the catalogue by a
    plain translator. A non-English title differs from the English source, so the
    check cannot pass on an untranslated window. English is chosen last and the
    window ends in it.
    """
    win = start_window(combo)
    manager = win._language_manager
    entries = dict(win._language_entry_actions)
    assert list(entries) == list(CODES), list(entries)
    assert manager.current_language() == "en"
    assert win._file_menu.title() == "&File"
    steps = list(CODES) + ["en"]
    for number, code in enumerate(steps, start=1):
        where = f"step {number} of {len(steps)}: {code}"
        with qtbot.waitSignal(manager.languageChanged, timeout=2000) as heard:
            entries[code].trigger()
        QApplication.processEvents()
        assert heard.args == [code], where
        assert manager.current_language() == code, where
        title = win._file_menu.title()
        assert title == catalogue_file_title(code), f"{where}: File title {title!r}"
        if code != "en":
            assert title != "&File", f"{where}: the window is still in English"
    assert manager.current_language() == "en"
    assert win._file_menu.title() == "&File"
    say(capsys, f"[{combo.label()}] {len(steps)} selections, interface ends in English")


# --------------------------------------------------------------------------- #
# SC-L10N-UI-002-1, -002-2, -002-3: the start-up language                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("system", "installed"), STARTUP_ROWS, ids=[row[0] for row in STARTUP_ROWS]
)
def test_sc_l10n_ui_002_1_the_system_locale_selects_the_startup_language(
    manager: LanguageManager, system: str, installed: str
) -> None:
    """SC-L10N-UI-002-1: a single preferred entry selects the language of its row."""
    problems = startup_problems(manager, [system], installed)
    assert not problems, "\n".join(problems)


def test_sc_l10n_ui_002_2_the_first_matching_preference_wins(
    manager: LanguageManager,
) -> None:
    """SC-L10N-UI-002-2: ``it_IT`` maps to nothing, so ``ja_JP`` is the one chosen."""
    preferred, installed = FIRST_MATCH_ROW
    problems = startup_problems(manager, preferred, installed)
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize(
    ("preferred", "installed"),
    SKIP_ROWS,
    ids=[f"{first}+{second}" for (first, second), _ in SKIP_ROWS],
)
def test_sc_l10n_ui_002_3_a_traditional_script_entry_is_skipped_in_the_walk(
    manager: LanguageManager, preferred: List[str], installed: str
) -> None:
    """SC-L10N-UI-002-3: a Traditional-script entry is skipped, never a stop.

    The user's ruling of 2026-10-24: a Traditional-script entry maps to no shipped
    language and is skipped like ``it_IT``, so the next entry decides. The first
    row, ``["zh_TW", "fr_FR"]``, starts the application in French; the last,
    ``["zh-Hant-CN", "ko"]``, in Korean because the Traditional script decides
    over the mainland territory.
    """
    problems = startup_problems(manager, preferred, installed)
    assert not problems, "\n".join(problems)


def test_sc_l10n_ui_002_3_control_a_walk_that_stops_at_a_traditional_entry_fails(
    capsys, manager: LanguageManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: a matcher that returns English at a Traditional entry fails the rows.

    The stand-in is installed for this test only. The same check that passes on
    the product's matcher must fail the rows whose Traditional entry is followed
    by a language, and the ``["zh_TW", "fr_FR"]`` row must be among them.
    """
    real = locale_match.match_ui_language

    def stops_at_a_traditional_entry(
        preferred: Sequence[str], available: Sequence[str]
    ) -> str:
        for tag in preferred:
            if _TRADITIONAL.match(tag):
                return "en"
        return real(preferred, available)

    monkeypatch.setattr(locale_match, "match_ui_language", stops_at_a_traditional_entry)
    failed: List[str] = []
    failed_rows = 0
    for preferred, installed in SKIP_ROWS:
        found = startup_problems(manager, preferred, installed)
        failed_rows += 1 if found else 0
        failed.extend(found)
    assert any("zh_TW" in line and "'fr'" in line for line in failed), failed
    assert 1 <= failed_rows <= len(SKIP_ROWS), failed_rows
    say(capsys, f"control: the stand-in fails {failed_rows} of {len(SKIP_ROWS)} rows")
    say(capsys, f"control: {len(failed)} problem lines in those rows")
    say(capsys, f"control, first failure: {failed[0]}")


def test_sc_l10n_ui_002_3_the_window_starts_in_french_after_a_traditional_entry(
    qtbot, capsys, combo: Combo, start_window
) -> None:
    """SC-L10N-UI-002-3, on a window: ``["zh_TW", "fr_FR"]`` starts in French.

    The list is injected into the window's own manager, as a start from the system
    would hand it, and the window's File menu is French. The selector labels do not
    move with the language.
    """
    win = start_window(combo)
    labels = [text for _code, text, _families, _bits in selector_snapshot(win)]
    installed = win._language_manager.install_from_locale(["zh_TW", "fr_FR"])
    QApplication.processEvents()
    assert installed == "fr"
    assert win._language_manager.current_language() == "fr"
    assert win._file_menu.title() == catalogue_file_title("fr")
    after = [text for _code, text, _families, _bits in selector_snapshot(win)]
    assert after == labels
    say(capsys, f"[{combo.label()}] a Traditional entry then French starts in French")


# --------------------------------------------------------------------------- #
# SC-L10N-UI-003-1, -003-2: the endonyms                                        #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_003_1_the_selector_shows_the_eight_endonyms_in_order(
    capsys, combo: Combo, start_window
) -> None:
    """SC-L10N-UI-003-1: the menu's own entries are the eight endonyms, in order."""
    win = start_window(combo)
    menu_labels = [
        action.text().encode("utf-8")
        for action in win._language_menu.actions()
        if not action.isSeparator()
    ]
    assert menu_labels == [label.encode("utf-8") for label in ENDONYMS], menu_labels
    problems = selector_problems(selector_snapshot(win))
    assert not problems, "\n".join(problems)
    say(capsys, f"[{combo.label()}] selector entries: {len(menu_labels)}")


def test_sc_l10n_ui_003_2_the_labels_do_not_change_with_the_interface_language(
    capsys, combo: Combo, system_font: bool, start_window
) -> None:
    """SC-L10N-UI-003-2 and SC-L10N-UI-012-2 (application level), in both font modes.

    Under each of the eight active languages the labels are byte-identical to the
    eight endonyms, no entry is a raw code, the Simplified entry's families hold
    the Simplified-form family and not the Japanese one and the Japanese entry's
    the reverse, and the whole snapshot (labels, family lists, tag bits) is the one
    the first language showed. Each language is proved active by its File title.
    """
    win = start_window(combo, system_font=system_font)
    first: Optional[List[Shown]] = None
    for code in CODES:
        choose_language(win, code)
        assert win._file_menu.title() == catalogue_file_title(code), code
        shown = selector_snapshot(win)
        problems = selector_problems(shown)
        assert not problems, f"under {code}:\n  " + "\n  ".join(problems)
        if first is None:
            first = shown
        assert shown == first, f"the selector changed under {code}"
    mode = "system-font" if system_font else "nifen"
    say(
        capsys,
        f"[{combo.label()}/{mode}] {len(CODES)} languages examined, "
        f"{len(CODES)} labels each, byte-identical",
    )


def test_req_l10n_ui_003_no_catalogue_offers_an_endonym_for_translation(
    capsys,
) -> None:
    """REQ-L10N-UI-003: the self-names are not catalogue messages in any language.

    The source catalogues next to the compiled ones are read as bytes: none holds
    an endonym as a message source or as a translation, so no translator is ever
    offered one and the labels can only be the same in every language.
    """
    folder = i18n._default_translations_dir()
    offered: List[str] = []
    files = 0
    for code in CODES:
        data = (folder / f"pixelart_{code}.ts").read_bytes()
        files += 1
        for label in ENDONYMS:
            text = label.encode("utf-8")
            if b"<source>" + text + b"</source>" in data:
                offered.append(f"{code}: {label} as a source")
            if re.search(rb"<translation[^>]*>" + re.escape(text) + rb"</", data):
                offered.append(f"{code}: {label} as a translation")
    assert not offered, offered
    say(capsys, f"{files} source catalogues, {len(ENDONYMS)} endonyms, none offered")


# --------------------------------------------------------------------------- #
# The selector from the keyboard, with its focus indication and its names       #
# --------------------------------------------------------------------------- #


def test_req_l10n_ui_003_the_selector_is_keyboard_reachable_shows_focus_and_is_named(
    qtbot, capsys, combo: Combo, start_window
) -> None:
    """REQ-L10N-UI-003: the entries are reachable by keyboard and show where they are.

    The Language menu is opened and walked with the Down key: the active entry
    visits the eight entries in the user's order, and for each the entry's row
    looks different when it is active from when its neighbour is (the focus
    indication, in this style and mode). Up twice and Return then chooses
    Simplified Chinese through the keyboard. Each entry is named by its endonym:
    the label a menu entry reports to assistive technology is its text.
    """
    win = start_window(combo)
    menu = win._language_menu
    entries = dict(win._language_entry_actions)
    manager = win._language_manager
    menu.popup(win.mapToGlobal(QPoint(8, 8)))
    try:
        qtbot.waitExposed(menu)
        visited: List[str] = []
        images: List[Any] = []
        rects: List[Any] = []
        for _ in CODES:
            qtbot.keyClick(menu, Qt.Key.Key_Down)
            QApplication.processEvents()
            active = menu.activeAction()
            assert active is not None, f"Down reached nothing after {visited}"
            visited.append(active.data())
            rects.append(menu.actionGeometry(active))
            images.append(menu.grab().toImage())
        assert visited == list(CODES), visited
        for index, rect in enumerate(rects):
            other = images[index + 1] if index + 1 < len(images) else images[index - 1]
            assert images[index].copy(rect) != other.copy(rect), (
                f"{visited[index]}: the row looks the same active and inactive "
                f"in {combo.label()}"
            )
        qtbot.keyClick(menu, Qt.Key.Key_Up)
        qtbot.keyClick(menu, Qt.Key.Key_Up)
        chosen = menu.activeAction()
        assert chosen is not None and chosen.data() == "zh_CN"
        with qtbot.waitSignal(manager.languageChanged, timeout=2000) as heard:
            qtbot.keyClick(menu, Qt.Key.Key_Return)
        assert heard.args == ["zh_CN"]
        assert manager.current_language() == "zh_CN"
    finally:
        menu.hide()
    names = [entries[code].text() for code in CODES]
    assert names == list(ENDONYMS), names
    say(capsys, f"[{combo.label()}] {len(CODES)} entries reached by keyboard")


# --------------------------------------------------------------------------- #
# SC-L10N-UI-012-2 at the application level: "Use system font" and the platform  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "han_capable", [False, True], ids=["han-free-platform", "han-capable-platform"]
)
def test_req_l10n_ui_012_system_font_order_follows_what_the_platform_holds(
    capsys, combo: Combo, han_capable: bool, start_window
) -> None:
    """REQ-L10N-UI-012: with "Use system font" on, the platform decides the order.

    A Han-capable platform family is forced: in each entry's list both CJK families
    (the entry's Han family and the Hangul one) precede the platform family, and
    the application font itself shows the same order. A Han-free platform family
    is forced: the platform family stays first in every entry's list and in the
    application font, with the CJK families behind it. Each entry still holds the
    right Han form and not the other.
    """
    platform = HAN_CAPABLE_PLATFORM if han_capable else HAN_FREE_PLATFORM
    win = start_window(combo, system_font=True, han_capable=han_capable)
    ui_list = list(QApplication.font().families())
    assert platform in ui_list, ui_list
    problems = selector_problems(selector_snapshot(win))
    for code, action in win._language_entry_actions:
        families = list(action.font().families())
        cjk = [family for family in families if family in CJK_FAMILIES]
        if platform not in families:
            problems.append(f"{code}: {platform!r} is not in the list {families}")
            continue
        place = families.index(platform)
        if KR_FAMILY not in cjk or len(cjk) < 2:
            problems.append(f"{code}: the CJK families are {cjk} in {families}")
        if han_capable:
            behind = [family for family in cjk if families.index(family) > place]
            if behind:
                problems.append(f"{code}: {behind} follow {platform!r} in {families}")
        else:
            if families[0] != platform:
                problems.append(f"{code}: {platform!r} is not first in {families}")
    if han_capable:
        if ui_list.index(platform) < ui_list.index(KR_FAMILY):
            problems.append(f"the application font puts {platform!r} first: {ui_list}")
    elif ui_list[0] != platform:
        problems.append(f"the application font does not start with {platform!r}")
    assert not problems, "\n  ".join(problems)
    say(
        capsys,
        f"[{combo.label()}] {platform!r}: {len(win._language_entry_actions)} entries, "
        f"first entry {list(win._language_entry_actions[0][1].font().families())}",
    )


def test_req_l10n_ui_012_han_capable_order_with_the_detector_true_for_bundled_faces(
    capsys, combo: Combo, start_window
) -> None:
    """REQ-L10N-UI-012: the Han-capable order, the detector true for bundled faces.

    The same order check as above, with the injected detector answering True for
    the forced platform family and for the three bundled CJK faces, the answer the
    real detector gives for faces that hold Han. A selector that put the platform
    family first only while the detector said False for a bundled face would pass
    the check above and fail here. The platform family's place is read first, then
    the Han forms.
    """
    platform = HAN_CAPABLE_PLATFORM
    win = start_window(combo, system_font=True, han_capable=True, bundled_hold_han=True)
    problems: List[str] = []
    for code, families in entry_lists(win).items():
        problems += platform_order_problems(code, families, platform)
    problems += platform_order_problems(
        "the application font", list(QApplication.font().families()), platform
    )
    problems += selector_problems(selector_snapshot(win))
    assert not problems, "\n  ".join(problems)
    say(capsys, f"[{combo.label()}] {platform!r}: {len(entry_lists(win))} entries")


def test_req_l10n_ui_012_entry_lists_do_not_follow_the_active_language_with_system_font(
    capsys, combo: Combo, bundled_detected: bool, start_window
) -> None:
    """REQ-L10N-UI-012: with system font on, the entries ignore the active language.

    A Han-capable platform family is forced and "Use system font" is on. Under each
    of the eight active languages, chosen through the real entry, every entry's
    family list is the list it had under the first language: the labels are drawn in
    their own language's forms whatever language is active. The Simplified entry
    holds the Simplified-form family and not the Japanese one, the Japanese entry
    the reverse. Run under both answers of the detector for the bundled faces.
    """
    win = start_window(
        combo, system_font=True, han_capable=True, bundled_hold_han=bundled_detected
    )
    lists: Dict[str, Dict[str, Tuple[str, ...]]] = {}
    forms: List[str] = []
    for code in CODES:
        choose_language(win, code)
        lists[code] = entry_lists(win)
        forms += [
            f"under {code}: {line}"
            for line in selector_problems(selector_snapshot(win))
        ]
    first = lists[CODES[0]]
    changes: List[str] = []
    for code in CODES[1:]:
        for entry, families in lists[code].items():
            if families != first[entry]:
                changes.append(
                    f"the {entry} entry's list changes with the active language: "
                    f"{list(families)} under {code}, {list(first[entry])} under "
                    f"{CODES[0]}"
                )
    problems = changes + forms
    assert not problems, "\n  ".join(problems)
    say(
        capsys,
        f"[{combo.label()}] {len(CODES)} languages, {len(first)} entries, "
        "one list each",
    )


def test_req_l10n_ui_012_the_ui_font_holds_the_platform_family_after_both_cjk_families(
    capsys, combo: Combo, bundled_detected: bool, start_window
) -> None:
    """REQ-L10N-UI-012: the interface font, Han-capable platform, system font on.

    The true column's UI row (the plan's table): both CJK families, then the
    platform family. Read under each of the eight active languages and under both
    answers of the detector for the bundled faces. A measurement of whether the
    interface font has the selector entries' fault of taking the first family of a
    font that may already be a chain.
    """
    win = start_window(
        combo, system_font=True, han_capable=True, bundled_hold_han=bundled_detected
    )
    problems: List[str] = []
    for code in CODES:
        choose_language(win, code)
        problems += platform_order_problems(
            f"under {code}, the UI font",
            list(QApplication.font().families()),
            HAN_CAPABLE_PLATFORM,
        )
    assert not problems, "\n  ".join(problems)
    say(capsys, f"[{combo.label()}] the UI font under {len(CODES)} languages")


def test_req_l10n_ui_012_the_guide_page_font_holds_the_platform_family_after_both_cjk(
    qtbot, capsys, combo: Combo, bundled_detected: bool, start_window
) -> None:
    """REQ-L10N-UI-012: the guide page font, Han-capable platform, system font on.

    The true column's guide row (the plan's table): both CJK families, then the
    platform family. Read from the open guide's page font under each of the eight
    active languages and under both answers of the detector for the bundled faces.
    """
    win = start_window(
        combo, system_font=True, han_capable=True, bundled_hold_han=bundled_detected
    )
    dialog = open_guide(win, qtbot)
    problems: List[str] = []
    for code in CODES:
        choose_language(win, code)
        problems += platform_order_problems(
            f"under {code}, the guide page font",
            list(dialog._content_view.document().defaultFont().families()),
            HAN_CAPABLE_PLATFORM,
        )
    assert not problems, "\n  ".join(problems)
    say(capsys, f"[{combo.label()}] the guide page font under {len(CODES)} languages")


# --------------------------------------------------------------------------- #
# The tag at the application level                                              #
# --------------------------------------------------------------------------- #


def test_req_l10n_ui_012_every_entry_the_ui_font_and_the_page_font_carry_their_tag(
    qtbot, capsys, combo: Combo, system_font: bool, start_window
) -> None:
    """REQ-L10N-UI-012: each font carries exactly the tag its list was allocated.

    The eight selector entries, the interface font and the guide page font are
    each a list of two or more families whose tag bits equal the bits the
    product's own registry and table give that list. Each entry's list is the one
    the product's logic gives for its language and the role's primary family.
    """
    win = start_window(combo, system_font=system_font)
    dialog = open_guide(win, qtbot)
    primary = HAN_FREE_PLATFORM if system_font else NIFEN
    fonts: List[Held] = [
        ("interface font", QFont(QApplication.font())),
        ("guide page font", dialog._content_view.document().defaultFont()),
    ]
    problems: List[str] = []
    for code, action in win._language_entry_actions:
        font = action.font()
        fonts.append((f"selector entry {code}", font))
        want = font_chain.label_chain(primary, code, False)
        if tuple(font.families()) != want:
            problems.append(
                f"entry {code}: {list(font.families())}, wanted {list(want)}"
            )
    for label, font in fonts:
        families = list(font.families())
        if len(families) < 2:
            problems.append(f"{label}: not a chain: {families}")
            continue
        allocated = allocated_tag_bits(families)
        if allocated == 0 or tag_bits(font) != allocated:
            problems.append(
                f"{label}: tag bits {tag_bits(font):#x}, allocated {allocated:#x}"
            )
    assert not problems, "\n  ".join(problems)
    mode = "system-font" if system_font else "nifen"
    say(
        capsys,
        f"[{combo.label()}/{mode}] {len(fonts)} fonts carry their allocated tag",
    )


def test_req_l10n_ui_012_the_two_han_labels_that_share_a_first_family_differ_in_tag(
    capsys, combo: Combo, system_font: bool, start_window
) -> None:
    """REQ-L10N-UI-012: the two Han labels share a first family and differ in tag.

    In the Nifen mode and with a Han-free platform family forced, the two labels'
    lists begin with the same family, so only the tag keeps Qt's font cache from
    drawing one label's Han characters with the other's face.
    """
    win = start_window(combo, system_font=system_font)
    problems = tags_differ_problems(win)
    assert not problems, "\n".join(problems)
    fonts = {code: action.font() for code, action in win._language_entry_actions}
    mode = "system-font" if system_font else "nifen"
    say(
        capsys,
        f"[{combo.label()}/{mode}] first family {fonts['zh_CN'].families()[0]!r}, "
        f"tag bits {tag_bits(fonts['zh_CN']):#x} and {tag_bits(fonts['ja']):#x}",
    )


@pytest.mark.parametrize("system", [False, True], ids=["nifen", "system-font"])
def test_req_l10n_ui_012_control_chain_font_without_a_tag_fails_the_tags_differ_check(
    capsys, system: bool, start_window, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: with ``chain_font`` applying no tag, "tags differ" fails.

    The window passes the check first. The window's ``chain_font`` is then
    replaced, for this test only, by one that sets the list and clears every tag
    flag; the entries are rebuilt and the same check must fail, and its message is
    quoted.
    """
    win = start_window(Combo(DEFAULT_STYLE, THEME_LIGHT), system_font=system)
    assert tags_differ_problems(win) == []

    def chain_font_without_a_tag(base: QFont, families: Sequence[str]) -> QFont:
        font = QFont(base)
        font.setFamilies(list(families))
        font.setStyleStrategy(font.styleStrategy() & ~app_font._CHAIN_TAG_MASK)
        return font

    monkeypatch.setattr(main_window_module, "chain_font", chain_font_without_a_tag)
    win._apply_language_entry_fonts()
    problems = tags_differ_problems(win)
    assert problems, "the check passed with no tag applied"
    assert "same tag bits" in problems[0], problems
    say(capsys, f"control (system font {system}): {problems[0]}")


# --------------------------------------------------------------------------- #
# The interface font on a live switch                                           #
# --------------------------------------------------------------------------- #


def test_req_l10n_ui_012_the_ui_font_follows_the_form_on_a_live_zh_cn_ja_zh_cn_switch(
    qtbot, capsys, combo: Combo, system_font: bool, start_window
) -> None:
    """REQ-L10N-UI-012: families and tag of the UI font follow the form at each step.

    One window, the guide open, ``zh_CN`` -> ``ja`` -> ``zh_CN`` through the real
    entries: after each switch the interface font and the guide page font carry
    the list the product's logic gives for that language and the tag the product
    allocated to it, the form of ``ja`` differs from the form of ``zh_CN``, and
    returning to ``zh_CN`` returns the same list and tag.
    """
    win = start_window(combo, system_font=system_font)
    dialog = open_guide(win, qtbot)
    primary = HAN_FREE_PLATFORM if system_font else NIFEN
    seen: List[Tuple[Tuple[str, ...], int]] = []
    for code in ("zh_CN", "ja", "zh_CN"):
        choose_language(win, code)
        page = dialog._content_view.document().defaultFont()
        problems = chain_problems(
            f"[{code}] UI font", QApplication.font(), primary, code
        )
        problems += chain_problems(
            f"[{code}] guide page font", page, HAN_FREE_PLATFORM, code
        )
        assert not problems, "\n".join(problems)
        font = QApplication.font()
        seen.append((tuple(font.families()), tag_bits(font)))
    assert seen[0] != seen[1], seen
    assert seen[0] == seen[2], seen
    mode = "system-font" if system_font else "nifen"
    say(capsys, f"[{combo.label()}/{mode}] forms {[entry[0][-2] for entry in seen]}")


# --------------------------------------------------------------------------- #
# A walk over every font the application holds                                  #
# --------------------------------------------------------------------------- #


def test_req_l10n_ui_012_a_walk_over_every_font_the_application_holds(
    qtbot, capsys, combo: Combo, system_font: bool, start_window
) -> None:
    """REQ-L10N-UI-012: every list of two or more families is tagged, no other font is.

    After start-up in the font mode, after a "Use system font" toggle and after a
    live ``zh_CN`` -> ``ja`` -> ``zh_CN`` switch, every font the application holds
    is collected (the application font, each per-class font, every widget's font
    under the main window and the guide window, every action's font in the
    menus). Each font of two or more families must carry exactly the tag its list
    was allocated and never none; each one-family font must carry no flag of the
    table. The fonts examined are counted (more than none) and the lists per first
    family are printed.
    """
    win = start_window(combo, system_font=system_font)
    dialog = open_guide(win, qtbot)
    examined = 0
    lists: Dict[str, List[Tuple[str, ...]]] = {}

    def walk(step: str, *, system: bool, language: str) -> None:
        nonlocal examined
        held = held_fonts(win, dialog)
        assert held, f"[{step}] no font was collected"
        problems = state_problems(held, system=system, language=language)
        assert not problems, f"[{step}] {len(problems)} problems\n  " + "\n  ".join(
            problems[:20]
        )
        examined += len(held)
        for first, found in lists_per_first_family(held).items():
            known = lists.setdefault(first, [])
            known.extend(item for item in found if item not in known)

    walk("start-up", system=system_font, language="en")
    win.set_use_system_font(not system_font)
    QApplication.processEvents()
    walk("font toggle", system=not system_font, language="en")
    for code in ("zh_CN", "ja", "zh_CN"):
        choose_language(win, code)
        walk(f"switch to {code}", system=not system_font, language=code)
    assert examined > 0
    mode = "system-font" if system_font else "nifen"
    per_family = {first: len(found) for first, found in lists.items()}
    say(
        capsys,
        f"[{combo.label()}/{mode}] {examined} fonts examined; "
        f"lists per first family {per_family}",
    )


def test_req_l10n_ui_012_control_the_walk_reports_a_bare_family_list(
    qtbot, capsys, start_window
) -> None:
    """Control: a widget given a bare ``setFamilies`` list is reported by the walk.

    The walk is clean on the window first. Two labels are then given a font whose
    families are set with ``setFamilies`` alone, the first family and one other.
    The first has its style strategy set to the default, so the list carries no
    tag at all and the walk must name it an untagged chain. The second leaves the
    strategy alone, so a widget font takes it from its parent, the tag of the
    parent's list, and the walk must name it as carrying a tag other than the one
    its own list was allocated. Both reports are quoted.
    """
    win = start_window(Combo(DEFAULT_STYLE, THEME_LIGHT))
    dialog = open_guide(win, qtbot)
    assert walk_problems(held_fonts(win, dialog)) == []
    probe = QLabel("probe", win)
    probe.setObjectName("bare-family-list-probe")
    bare = QFont(NIFEN)
    bare.setFamilies([NIFEN, "Probe Other Family"])
    bare.setStyleStrategy(QFont.StyleStrategy.PreferDefault)
    probe.setFont(bare)
    inheriting = QLabel("probe", win)
    inheriting.setObjectName("inherited-tag-probe")
    inherited = QFont(NIFEN)
    inherited.setFamilies([NIFEN, "Probe Other Family"])
    inheriting.setFont(inherited)
    reported = walk_problems(held_fonts(win, dialog))
    untagged = [line for line in reported if "bare-family-list-probe" in line]
    mistagged = [line for line in reported if "inherited-tag-probe" in line]
    assert untagged and all("untagged chain" in line for line in untagged), reported
    assert mistagged and all("allocated tag" in line for line in mistagged), reported
    say(capsys, f"control, a list with no tag: {untagged[0]}")
    say(capsys, f"control, a list that took its parent's tag: {mistagged[0]}")


# --------------------------------------------------------------------------- #
# No test leaves the process locale changed                                     #
# --------------------------------------------------------------------------- #


def test_the_process_locale_guard_sees_a_changed_default_locale(
    capsys, manager: LanguageManager
) -> None:
    """Control: the guard names a changed default locale, and a language left installed.

    Both changes are made here and put back in a ``finally``: the default locale
    through ``QLocale.setDefault`` and the language through the manager. The guard's
    own report is quoted, and it is silent once both are put back.
    """
    before = locale_state()
    system_before = QLocale.system
    original = QLocale()
    try:
        QLocale.setDefault(QLocale("ja_JP"))
        changed = locale_leaks(before, system_before)
        assert any("default locale" in line for line in changed), changed
    finally:
        QLocale.setDefault(original)
    try:
        manager.set_language("fr")
        left = locale_leaks(before, system_before)
        assert any("interface language" in line for line in left), left
        assert any("File title" in line for line in left), left
    finally:
        manager.set_language("en")
    assert locale_leaks(before, system_before) == []
    say(capsys, f"control, a changed default locale: {changed[0]}")
    say(capsys, f"control, a language left installed: {left[0]}")


def test_the_process_locale_guard_sees_a_replaced_system_locale(capsys) -> None:
    """Control: the guard names a swap of ``QLocale.system`` made during the test.

    The attribute is replaced by a stand-in after the snapshot, the guard's report
    is quoted, and the original is put back in a ``finally``; the guard is silent
    once it is back. A swap that was already in place when the snapshot was taken
    is not this test's doing, so the guard stays silent for it too, and that
    stand-in is put back in a ``finally`` as well.
    """
    original = QLocale.system
    stand_in = staticmethod(lambda: QLocale("en_US"))
    before = locale_state()
    system_before = QLocale.system
    try:
        setattr(QLocale, "system", stand_in)
        replaced = locale_leaks(before, system_before)
        assert "QLocale.system was replaced" in replaced, replaced
    finally:
        setattr(QLocale, "system", staticmethod(original))
    assert QLocale.system is original
    assert locale_leaks(before, system_before) == []
    try:
        setattr(QLocale, "system", stand_in)
        already_replaced = locale_state()
        already_bound = QLocale.system
        assert locale_leaks(already_replaced, already_bound) == []
    finally:
        setattr(QLocale, "system", staticmethod(original))
    assert locale_leaks(before, system_before) == []
    say(capsys, f"control, a replaced QLocale.system: {'; '.join(replaced)}")


def test_a_startup_walk_over_all_rows_leaves_the_process_locale_unchanged(
    capsys, manager: LanguageManager
) -> None:
    """Every start-up row, run in one process, leaves the locale and language as found.

    The 22 rows are started one after the other on one manager; the default locale,
    the system locale and the active language are the same afterwards once English
    is chosen again, and ``QLocale.system`` is still the object it was when the test
    began.
    """
    before = locale_state()
    system_before = QLocale.system
    rows = (
        [([system], installed) for system, installed in STARTUP_ROWS]
        + [FIRST_MATCH_ROW]
        + SKIP_ROWS
    )
    for preferred, installed in rows:
        assert not startup_problems(manager, preferred, installed), preferred
    manager.set_language("en")
    assert locale_leaks(before, system_before) == []
    say(capsys, f"{len(rows)} start-up rows run, process locale unchanged")
