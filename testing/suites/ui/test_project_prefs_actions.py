"""Project confirmations submenu acceptance tests (
REQ-P5-UI-033's restorability half, ADR-0056).

``build_project_prefs_menu`` is the **restore path** for a suppressed
per-project confirmation (REQ-P5-UI-033: "the suppression must always be
recoverable ... a reachable, discoverable control ... not the suppressed
dialog itself"). Tested at the module's own public seam
(``document_provider`` / ``on_changed`` callables) — the narrowest surface
that proves the contract without needing a full ``Main_Window``. Both themes
run via the autouse ``theme`` fixture.

The label cases at the end of the module prove REQ-L10N-UI-001's menu-item
clause for the entries this menu builds from the preference registry: each entry
shows its catalogue translation in every shipped language, and no registered
confirmation key reaches the screen as a raw identifier.
"""

from __future__ import annotations

import importlib
import xml.etree.ElementTree as ET
from typing import Callable, Dict, Iterator, List, Tuple, cast

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QAction, QUndoStack
from PySide6.QtWidgets import QMenu

from pixelart_creator.logic import project_prefs
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.project_prefs import CONFIRM_CEL_OVERWRITE
from pixelart_creator.ui.cel_overwrite_dialog import Cel_Overwrite_Dialog
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.project_prefs_actions import build_project_prefs_menu

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _make_doc() -> Document:
    return Document(64, 64, palette=Palette(STARTER))


def test_menu_has_one_entry_for_the_registered_key(qtbot):
    """One checkable action per ``logic/project_prefs.REGISTRY`` key, this
    slice's own ``confirm_cel_overwrite`` among them."""
    doc = _make_doc()
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)

    names = {a.data() for a in menu.actions()}
    assert CONFIRM_CEL_OVERWRITE.name in names
    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)
    assert action.isCheckable()
    assert action.text() != ""


def test_menu_is_findable_without_triggering_an_overwrite(qtbot):
    """SC-UI-033-9: the restore control is reachable/discoverable — it can be
    built, inspected and shown without any drag/drop ever occurring, and it
    is a menu action, not the suppressed dialog itself."""
    doc = _make_doc()
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)

    assert menu.accessibleName() != ""
    assert menu.title() != ""
    assert not isinstance(menu, Cel_Overwrite_Dialog)
    # No drag was driven, no dialog was ever constructed, yet the menu and
    # its entry exist and are inspectable — reachability does not require an
    # overwrite to have happened.


def test_action_shows_current_state_default_unchecked(qtbot):
    """A freshly-defaulted document's entry reads unchecked (nothing to
    restore) and enabled."""
    doc = _make_doc()
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)
    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)

    menu.aboutToShow.emit()

    assert action.isChecked() is False
    assert action.isEnabled() is True


def test_action_shows_current_state_suppressed(qtbot):
    """A document whose confirmation is suppressed shows the entry checked —
    "the current state" the requirement asks for."""
    doc = _make_doc()
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)
    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)

    menu.aboutToShow.emit()

    assert action.isChecked() is True


def test_action_disabled_when_no_document(qtbot):
    """With no active document the entry is disabled and unchecked, never a
    silent no-op that looks available."""
    holder: dict = {"doc": None}
    menu = build_project_prefs_menu(lambda: holder["doc"], lambda: None)
    qtbot.addWidget(menu)
    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)

    menu.aboutToShow.emit()

    assert action.isEnabled() is False
    assert action.isChecked() is False


def test_activating_the_action_restores_the_default_and_calls_back(qtbot):
    """SC-UI-033-9: activating the restore control sets the preference back
    to its declared default ("ask") and invokes the caller's on_changed hook
    — this is the path that makes the suppressed confirmation ask again,
    reached from a control that is NOT the suppressed dialog."""
    doc = _make_doc()
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    calls: List[bool] = []
    menu = build_project_prefs_menu(lambda: doc, lambda: calls.append(True))
    qtbot.addWidget(menu)
    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)

    action.trigger()

    assert doc.prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"
    assert calls == [True]


def test_restoring_the_preference_pushes_no_undo_command(qtbot):
    """SC-D004-3 (as observed from the UI restore path): setting the
    preference back is not document content — no QUndoCommand exists to
    push, and the caller's stack (if any) is untouched by this seam."""
    doc = _make_doc()
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    stack = QUndoStack()  # never handed to build_project_prefs_menu at all
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)
    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)

    action.trigger()

    assert stack.count() == 0


def test_menu_retranslates_on_language_change(qtbot):
    """A LanguageChange event re-sets the submenu's title and entry labels
    without raising."""
    from PySide6.QtCore import QEvent

    doc = _make_doc()
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)

    menu.changeEvent(QEvent(QEvent.Type.LanguageChange))

    assert menu.title() != ""
    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)
    assert action.text() != ""


def test_unknown_future_key_gets_a_fallback_label_not_a_crash(qtbot):
    """A preference key registered later by another slice (through
    ``logic/project_prefs.register``) renders with a readable fallback label
    rather than raising — this module must not need to know every claimant's
    key by name (plan §3.3)."""
    from pixelart_creator.logic.project_prefs import REGISTRY, PrefKey

    doc = _make_doc()
    extra = PrefKey(name="_test_future_pref", domain=frozenset({"a", "b"}), default="a")
    added = extra.name not in REGISTRY
    if added:
        REGISTRY[extra.name] = extra
    try:
        menu = build_project_prefs_menu(lambda: doc, lambda: None)
        qtbot.addWidget(menu)
        action = next(a for a in menu.actions() if a.data() == extra.name)
        assert action.text() != ""
    finally:
        if added:
            del REGISTRY[extra.name]


# --------------------------------------------------------------------------- #
# Labels: every registered confirmation key shows words, in every language.   #
# --------------------------------------------------------------------------- #

#: The registered key whose entry used to fall through to the generic
#: ``Confirm: %1`` template with the key's own name as the argument. It is
#: spelled out here, not imported: the oracle must not be the code under test.
_FLOATING_KEY = "confirm_floating_overwrite"

#: The catalogue message the entry reuses (the overwrite dialog's accessible
#: name): the context and the source text, as the ``.ts`` files hold them.
_OVERWRITE_CONTEXT = "Overwrite_Confirm_Dialog"
_OVERWRITE_SOURCE = "Overwrite existing pixels confirmation"

#: A key no label branch knows. The detector must flag its entry (the control).
_PLANTED_KEY = "_test_planted_raw_key"

#: The number of languages the finished product ships (English included).
EXPECTED_LANGUAGE_COUNT = 8

#: Switch for the language-count floor. ``False`` holds it: the floor in force is
#: 1, so the zero-examined guard still bites and every run prints ``HELD`` and how
#: many of the eight were discovered. The commit that brings the eighth catalogue
#: flips it to ``True``.
EIGHT_LANGUAGE_FLOOR_ENFORCED = False

#: A minimum on the product keys the every-key case examines (the denominator).
_MIN_PRODUCT_KEYS = 3


def _discover_languages() -> Tuple[str, ...]:
    """Return the languages the app itself offers, English first."""
    manager = LanguageManager(cast(QCoreApplication, QCoreApplication.instance()))
    return tuple(manager.available_languages())


#: The languages the app discovers (a ``pixelart_<code>.qm`` beside English).
LANGUAGES = _discover_languages()


def _language_floor() -> int:
    """Return the language-count floor in force: 8 once enforced, else 1."""
    return EXPECTED_LANGUAGE_COUNT if EIGHT_LANGUAGE_FLOOR_ENFORCED else 1


def _catalogue_translation(code: str, context: str, source: str) -> str:
    """Return the text the ``.ts`` file of ``code`` holds for (context, source).

    Read from the catalogue file itself, never from ``translate()``. English has
    no translation and shows the source. A missing, duplicated, unfinished or
    empty entry fails here, so the expected text is never a guess.
    """
    if code == FALLBACK_LANGUAGE:
        return source
    path = _default_translations_dir() / f"pixelart_{code}.ts"
    root = ET.parse(path).getroot()
    found = [
        message
        for scope in root.iter("context")
        if scope.findtext("name") == context
        for message in scope.iter("message")
        if message.findtext("source") == source
    ]
    assert len(found) == 1, f"{path.name}: {len(found)} entries for {context!r}"
    translation = found[0].find("translation")
    assert translation is not None and translation.text, f"{path.name}: no text"
    assert translation.get("type") != "unfinished", f"{path.name}: unfinished"
    return translation.text


def _shows_raw_key_name(text: str, key_name: str) -> bool:
    """Return ``True`` when ``text`` shows ``key_name`` as an identifier.

    Case-insensitive, in both renderings the generic fallback can produce: the
    name as written (``confirm_floating_overwrite``) and with each underscore
    replaced by a space (``confirm floating overwrite``).
    """
    lowered = text.lower()
    return key_name.lower() in lowered or key_name.replace("_", " ").lower() in lowered


def _entry_for(menu: QMenu, key_name: str) -> QAction:
    """Return the one menu entry whose ``data()`` is ``key_name``."""
    matches = [a for a in menu.actions() if a.data() == key_name]
    assert len(matches) == 1, f"{len(matches)} entries carry the key {key_name!r}"
    return matches[0]


def _register_floating_overwrite() -> None:
    """Make sure the floating-overwrite key is registered, and prove it.

    Importing the tool module registers the key as a side effect. Asserting it
    afterwards is the known-true precondition: a case cannot pass on a key that
    is not in the registry.
    """
    importlib.import_module("pixelart_creator.ui.tools.floating_move")
    assert _FLOATING_KEY in project_prefs.REGISTRY


@pytest.fixture
def language(qapp) -> Iterator[Callable[[str], None]]:
    """Install a language through the app's own manager; restore English after.

    The restore runs in teardown even when the case fails, so a translator never
    leaks into another case on the same worker (safe under ``-n auto``).
    """
    manager = LanguageManager(qapp)

    def install(code: str) -> None:
        assert manager.set_language(code) is True, f"{code!r} did not load"
        assert manager.current_language() == code

    try:
        yield install
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_the_app_discovers_its_languages():
    """REQ-L10N-UI-001: the per-language cases have something to run over.

    Prints the count, and the state of the eight-language floor. Zero is a
    failure, never a pass over an empty set.
    """
    floor = _language_floor()
    state = "ENFORCED" if EIGHT_LANGUAGE_FLOOR_ENFORCED else "HELD"
    print(
        f"languages discovered: {len(LANGUAGES)} {sorted(LANGUAGES)}; "
        f"floor {floor} ({state}, expected at ship: {EXPECTED_LANGUAGE_COUNT})"
    )
    assert len(LANGUAGES) > 0, "no language was discovered"
    assert FALLBACK_LANGUAGE in LANGUAGES
    assert len(LANGUAGES) >= floor, (
        f"discovered {len(LANGUAGES)} languages {sorted(LANGUAGES)}, "
        f"the floor in force is {floor}"
    )


@pytest.mark.parametrize("code", LANGUAGES)
def test_floating_overwrite_item_shows_the_catalogue_translation(qtbot, language, code):
    """REQ-L10N-UI-001: the item reads the catalogue's words, never its key name.

    In each discovered language the entry for ``confirm_floating_overwrite`` has
    exactly the text that language's ``.ts`` holds for the reused message. For
    every language but English that text differs from the English source (the
    signal that a translator really is installed), and in no language does the
    entry show the key's name, as written or with underscores as spaces.
    """
    _register_floating_overwrite()
    expected = _catalogue_translation(code, _OVERWRITE_CONTEXT, _OVERWRITE_SOURCE)
    if code != FALLBACK_LANGUAGE:
        assert expected != _OVERWRITE_SOURCE, f"{code}: the catalogue is not translated"
    language(code)

    menu = build_project_prefs_menu(_make_doc, lambda: None)
    qtbot.addWidget(menu)
    text = _entry_for(menu, _FLOATING_KEY).text()

    assert not _shows_raw_key_name(
        text, _FLOATING_KEY
    ), f"{code}: the {_FLOATING_KEY} entry shows the key name: {text!r}"
    assert text == expected, (
        f"{code}: the {_FLOATING_KEY} entry shows {text!r}, "
        f"the catalogue holds {expected!r}"
    )
    if code != FALLBACK_LANGUAGE:
        assert text != _OVERWRITE_SOURCE, f"{code}: shows the English source"


def test_every_product_key_has_a_label_of_its_own(qtbot, language):
    """REQ-L10N-UI-001: no registered confirmation key reaches the screen raw.

    In English, with the main window module imported (it registers the product
    keys), every key the product registers has an entry whose text shows neither
    the key's name nor that name with underscores as spaces, and no two keys
    share a label. Keys a test registers (``_test_`` prefix) are not product keys.
    """
    importlib.import_module("pixelart_creator.ui.main_window")
    language(FALLBACK_LANGUAGE)
    names = sorted(n for n in project_prefs.REGISTRY if not n.startswith("_test_"))
    print(f"product keys examined: {len(names)} {names}")
    assert len(names) >= _MIN_PRODUCT_KEYS, f"only {len(names)} product keys: {names}"
    assert _FLOATING_KEY in names

    menu = build_project_prefs_menu(_make_doc, lambda: None)
    qtbot.addWidget(menu)
    texts: Dict[str, str] = {name: _entry_for(menu, name).text() for name in names}

    raw = {n: t for n, t in texts.items() if _shows_raw_key_name(t, n)}
    assert not raw, f"keys shown as raw identifiers: {raw}"
    labels = list(texts.values())
    assert len(set(labels)) == len(labels), f"two keys share a label: {texts}"


def test_the_raw_name_detector_flags_a_key_with_no_label(qtbot, language):
    """Control: the detector the label cases rely on fires on a known-bad entry.

    ``_test_planted_raw_key`` has no label branch, so its entry falls back to the
    generic template with the key's name. The detector must flag that text. It
    must also stay quiet on plain words and on both raw renderings it is built to
    catch, written out as literals so the product plays no part in that half.
    Without the first check the negative assertions above could pass because the
    detector sees nothing; without the second, because it flags everything.
    """
    language(FALLBACK_LANGUAGE)
    planted = project_prefs.PrefKey(
        name=_PLANTED_KEY, domain=frozenset({"a", "b"}), default="a"
    )
    assert _PLANTED_KEY not in project_prefs.REGISTRY
    project_prefs.REGISTRY[_PLANTED_KEY] = planted
    try:
        menu = build_project_prefs_menu(_make_doc, lambda: None)
        qtbot.addWidget(menu)
        planted_text = _entry_for(menu, _PLANTED_KEY).text()
    finally:
        del project_prefs.REGISTRY[_PLANTED_KEY]

    assert _shows_raw_key_name(
        planted_text, _PLANTED_KEY
    ), f"the detector missed a raw key name: {planted_text!r}"
    assert not _shows_raw_key_name(_OVERWRITE_SOURCE, _FLOATING_KEY)
    assert _shows_raw_key_name("Confirm: confirm floating overwrite", _FLOATING_KEY)
    assert _shows_raw_key_name("CONFIRM_FLOATING_OVERWRITE", _FLOATING_KEY)
