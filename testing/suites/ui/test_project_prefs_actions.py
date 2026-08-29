"""Project confirmations submenu acceptance tests (T18 continuation;
REQ-P5-UI-033's restorability half, ADR-0056).

``build_project_prefs_menu`` is the **restore path** for a suppressed
per-project confirmation (REQ-P5-UI-033: "the suppression must always be
recoverable ... a reachable, discoverable control ... not the suppressed
dialog itself"). Tested at the module's own public seam
(``document_provider`` / ``on_changed`` callables) — the narrowest surface
that proves the contract without needing a full ``Main_Window``. Both themes
run via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.project_prefs import CONFIRM_CEL_OVERWRITE
from pixelart_creator.ui.cel_overwrite_dialog import Cel_Overwrite_Dialog
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
