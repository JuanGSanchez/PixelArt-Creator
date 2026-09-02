"""Library-edit prompt, its memory, and its restore control
(phase-11-asset-ingress; REQ-P11-UI-022, -023, -024).

Unblocked by ruling P11-R2 (plan §3.4): the domain-size-driven renderer in
``ui/project_prefs_actions.py`` can now show the current REMEMBERED OUTCOME
of a three-value preference, distinguishing *always pick up the change* from
*always keep the referenced version* -- not merely "checked". Every test that
touches the submenu asserts at that level of discrimination; a bare
"checked" assertion is never written here.

Two production seams are exercised, both at the narrowest surface that
proves the contract without needing a full ``Main_Window`` (mirroring
``test_project_prefs_actions.py`` and ``test_cel_overwrite_dialog.py`` Part
1 in this same tree):

- :meth:`Asset_Update_Prompt_Dialog.decide` -- the ask-or-remember flow
  (SC-P11-UI-022-*, SC-P11-UI-023-*).
- ``build_project_prefs_menu`` -- the restore/switch control
  (SC-P11-UI-024-*).

**Scope boundary, disclosed rather than assumed (investigated this
session, not asserted from memory):** ``Asset_Update_Prompt_Dialog.decide()``
takes only an ``asset_id`` and a display name -- it carries no notion of
*which edit* of that asset is being asked about, and its own module
docstring names this as an unbuilt, flagged gap ("the per-asset don't ask
again for THIS edit ... is not built here"). No production caller (checked:
no reference in ``ui/asset_reuse_panel.py``, ``ui/main_window.py``, or
anywhere else in ``pixelart_creator/``) invokes ``decide()`` at all yet, so
there is no reachable place to observe "the SAME edit" versus "a further
edit" as anything other than "any two calls". Probed empirically this
session (offscreen, ephemeral script, discarded): calling ``decide()`` twice
with identical arguments and no suppression set shows the dialog BOTH
times. SC-P11-UI-022-3's "that same edit does not ask again" clause is
therefore NOT satisfied by the shipped code as it stands -- asserted
directly below (test expected to fail; reported as a finding, not patched
here per Article I / the QA/product boundary). SC-P11-UI-022-2's
"reference resolves to the edited content" and "A's earlier version is
still listed in its revision history" clauses describe an effect this
dialog does not itself perform (no ``ReferenceSet`` mutation, no
``AssetRevisionStore`` call anywhere in ``asset_update_prompt.py``) -- only
the DECISION this module is responsible for (``decide()``'s returned
outcome) is asserted for those scenario ids; the downstream effect is
outside this module's reachable surface and is not independently exercised
here.

Both themes run via the autouse ``theme`` fixture (``testing/suites/ui/conftest.py``).
"""

from __future__ import annotations

import pathlib
from typing import List

import pytest
from PySide6.QtCore import Qt

from pixelart_creator.logic.asset_references import ASSET_LIBRARY_EDIT
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.project_prefs import ProjectPrefs
from pixelart_creator.ui.asset_update_prompt import (
    OUTCOME_KEEP,
    OUTCOME_PICK_UP,
    Asset_Update_Prompt_Dialog,
)
from pixelart_creator.ui.project_prefs_actions import (
    build_project_prefs_menu,
    value_label_for,
)

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _prefs() -> ProjectPrefs:
    return ProjectPrefs()


def _make_doc() -> Document:
    return Document(64, 64, palette=Palette(STARTER))


def _submenu_actions(menu, key_name: str):
    """Return the nested submenu's own actions for ``key_name``."""
    entry = next(a for a in menu.actions() if a.data() == key_name)
    submenu = entry.menu()
    assert submenu is not None
    return submenu.actions()


@pytest.fixture
def answer_prompt(monkeypatch):
    """Patch ``Asset_Update_Prompt_Dialog.exec`` to answer immediately
    (headless modal automation -- same pattern as this tree's own
    ``answer_dialog`` fixture in ``test_cel_overwrite_dialog.py``; the
    dialog's own click-driven behaviour is proven unpatched in
    ``test_sc_p11_ui_022_1_...`` below). Returns a controller:
    ``answer_prompt(action="pick_up" | "keep" | "dismiss", dont_ask=False)``;
    the returned list records every simulated presentation.
    """
    calls: List[bool] = []
    state = {"action": "keep", "dont_ask": False}

    def _fake_exec(self):
        calls.append(True)
        self._dont_ask.setChecked(state["dont_ask"])
        if state["action"] == "pick_up":
            self._on_pick_up()
        elif state["action"] == "keep":
            self._on_keep()
        else:
            self.reject()
        return self.result()

    monkeypatch.setattr(Asset_Update_Prompt_Dialog, "exec", _fake_exec)

    def _configure(*, action: str, dont_ask: bool = False) -> List[bool]:
        state["action"] = action
        state["dont_ask"] = dont_ask
        return calls

    return _configure


# --------------------------------------------------------------------------- #
# REQ-P11-UI-022 -- the ask itself                                            #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_022_1_user_is_asked_and_nothing_changed_yet(qtbot):
    """SC-P11-UI-022-1: the user is asked, and nothing has changed yet.

    Driven as a real click (qtbot.mouseClick), with the ``decided`` signal
    observer connected BEFORE the triggering action.
    """
    dialog = Asset_Update_Prompt_Dialog()
    qtbot.addWidget(dialog)
    dialog.set_asset("asset-1", "Sprite A")
    dialog.show()

    # Before any answer: the safe "nothing decided" default -- P's reference
    # has not been touched.
    assert dialog.outcome() == OUTCOME_KEEP
    assert dialog.decided_explicitly() is False

    with qtbot.waitSignal(dialog.decided, timeout=1000):
        qtbot.mouseClick(dialog._pick_up_button, Qt.MouseButton.LeftButton)

    assert dialog.decided_explicitly() is True
    assert dialog.outcome() == OUTCOME_PICK_UP


def test_sc_p11_ui_022_2_picking_up_is_the_resolved_decision(qtbot, answer_prompt):
    """SC-P11-UI-022-2: choosing to pick up the change resolves that decision.

    Scope note (module docstring above): the reference-set update and the
    revision-history retention this scenario also names are performed by a
    CALLER of ``decide()``, and no such caller exists in the shipped code --
    only the decision ``decide()`` itself is responsible for is asserted.
    """
    prefs = _prefs()
    presented = answer_prompt(action="pick_up")

    outcome, prefs = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)

    assert presented == [True]
    assert outcome == OUTCOME_PICK_UP
    # Checkbox untouched -> no suppression recorded; a real one-off pick-up.
    assert prefs.get(ASSET_LIBRARY_EDIT) == "ask"


def test_sc_p11_ui_022_3_keeping_the_referenced_version_changes_nothing(
    qtbot, answer_prompt
):
    """SC-P11-UI-022-3: keeping the referenced version changes nothing (the
    preference stays at its default, no suppression is recorded) -- AND, per
    the scenario's own text, "that same edit does not ask again".

    The first block below is this module's own, shipped contract and is
    expected to pass. The second block asserts the scenario's "does not ask
    again" clause verbatim against a second, identical ``decide()`` call and
    is EXPECTED TO FAIL -- see the module docstring's finding: ``decide()``
    carries no per-edit memory and re-prompts on every unsuppressed call.
    This is reported as a product-behaviour finding, not patched here.
    """
    prefs = _prefs()
    presented = answer_prompt(action="keep")

    outcome, prefs = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)

    assert presented == [True]
    assert outcome == OUTCOME_KEEP
    assert prefs.get(ASSET_LIBRARY_EDIT) == "ask"

    # -- SC-P11-UI-022-3's own clause: "that same edit does not ask again" --
    presented.clear()
    Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)
    assert presented == [], (
        "FINDING: REQ-P11-UI-022's 'that same edit does not ask again' "
        "clause is not satisfied -- decide() re-presented the dialog for an "
        "identical (asset_id, display_name) pair with no suppression set. "
        "decide() has no per-edit identity/state; see asset_update_prompt.py's "
        "own module docstring boundary note. Report to the UI/implementation owners; not "
        "fixed here."
    )


def test_sc_p11_ui_022_4_a_further_edit_asks_again(qtbot, answer_prompt):
    """SC-P11-UI-022-4: a further edit asks again.

    Scope note: ``decide()`` has no edit-identity parameter (SC-022-3's
    finding above), so "a further edit" is modelled as the only input that
    CAN vary between calls in the shipped API -- a different asset_id. This
    demonstrates the general "unsuppressed -> always asks" behaviour; it does
    not, and cannot, prove that a repeated edit of the SAME asset is told
    apart from a fresh one (the shipped code cannot do that -- SC-022-3).
    """
    prefs = _prefs()
    presented = answer_prompt(action="keep")

    _, prefs = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)
    presented.clear()
    outcome, prefs = Asset_Update_Prompt_Dialog.decide("asset-2", "Sprite B", prefs)

    assert presented == [True]
    assert outcome == OUTCOME_KEEP


def test_sc_p11_ui_022_5_dismissing_keeps_the_referenced_version(qtbot, answer_prompt):
    """SC-P11-UI-022-5: dismissing the prompt without choosing keeps the
    referenced version and records no preference at all."""
    prefs = _prefs()
    presented = answer_prompt(action="dismiss")

    outcome, prefs2 = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)

    assert presented == [True]
    assert outcome == OUTCOME_KEEP
    assert prefs2.get(ASSET_LIBRARY_EDIT) == "ask"
    assert prefs2 == prefs  # nothing recorded -- not even a no-op write


# --------------------------------------------------------------------------- #
# REQ-P11-UI-023 -- "Don't ask again", remembered per project                 #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_023_1_suppression_remembers_pick_up(qtbot, answer_prompt):
    """SC-P11-UI-023-1: ticking "Don't ask again" with "pick up the change"
    chosen suppresses the next edit's dialog and picks up the change."""
    prefs = _prefs()
    presented = answer_prompt(action="pick_up", dont_ask=True)

    outcome, prefs = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)
    assert presented == [True]
    assert prefs.get(ASSET_LIBRARY_EDIT) == "always_pick_up"

    presented.clear()
    outcome2, prefs = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)
    assert presented == []  # no dialog the second time
    assert outcome2 == OUTCOME_PICK_UP


def test_sc_p11_ui_023_2_suppression_remembers_keep(qtbot, answer_prompt):
    """SC-P11-UI-023-2: suppression can remember "keep the referenced
    version" just as well -- the two outcomes are equally real."""
    prefs = _prefs()
    presented = answer_prompt(action="keep", dont_ask=True)

    outcome, prefs = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)
    assert presented == [True]
    assert prefs.get(ASSET_LIBRARY_EDIT) == "always_keep_referenced"

    presented.clear()
    outcome2, prefs = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)
    assert presented == []
    assert outcome2 == OUTCOME_KEEP


def test_sc_p11_ui_023_3_the_memory_belongs_to_one_project(qtbot, answer_prompt):
    """SC-P11-UI-023-3: suppressing in project P1's prefs leaves a different
    project P2's (independent ``ProjectPrefs``) prompt un-suppressed."""
    p1 = _prefs()
    presented = answer_prompt(action="pick_up", dont_ask=True)
    _, p1 = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", p1)
    assert p1.get(ASSET_LIBRARY_EDIT) == "always_pick_up"

    p2 = _prefs()
    presented.clear()
    Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", p2)
    assert presented == [True]  # P2 still asks
    assert p2.get(ASSET_LIBRARY_EDIT) == "ask"


def test_sc_p11_ui_023_4_ticking_without_choosing_records_nothing(qtbot, answer_prompt):
    """SC-P11-UI-023-4: ticking "Don't ask again" and then dismissing without
    choosing records no preference; the next edit in that project asks
    again."""
    prefs = _prefs()
    presented = answer_prompt(action="dismiss", dont_ask=True)

    outcome, prefs2 = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs)
    assert presented == [True]
    assert outcome == OUTCOME_KEEP
    assert prefs2.get(ASSET_LIBRARY_EDIT) == "ask"

    presented.clear()
    Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", prefs2)
    assert presented == [True]  # asks again


# --------------------------------------------------------------------------- #
# REQ-P11-UI-024 -- the suppression is always recoverable                    #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_024_1_the_remembered_outcome_is_visible_and_restorable(qtbot):
    """SC-P11-UI-024-1: a reachable, discoverable control shows the current
    remembered outcome, distinguishing *always keep the referenced version*
    from *always pick up* (not merely "checked") -- and is not the suppressed
    prompt itself, findable without triggering a library-side edit."""
    doc = _make_doc()
    doc.prefs = doc.prefs.with_value(ASSET_LIBRARY_EDIT, "always_keep_referenced")
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)

    # Findable without triggering an edit: building/inspecting the menu never
    # constructs the suppressed prompt itself.
    assert not isinstance(menu, Asset_Update_Prompt_Dialog)
    for action in menu.actions():
        assert not isinstance(action, Asset_Update_Prompt_Dialog)

    menu.aboutToShow.emit()

    actions = _submenu_actions(menu, ASSET_LIBRARY_EDIT.name)
    checked = [a for a in actions if a.isChecked()]
    assert len(checked) == 1
    assert checked[0].data() == (ASSET_LIBRARY_EDIT.name, "always_keep_referenced")
    assert checked[0].text() == value_label_for(
        ASSET_LIBRARY_EDIT, "always_keep_referenced"
    )
    # The OTHER non-default outcome is visibly distinguished, not merely
    # "unchecked like everything else" -- it carries its own, different label.
    pick_up_action = next(a for a in actions if a.data()[1] == "always_pick_up")
    assert pick_up_action.isChecked() is False
    assert pick_up_action.text() != checked[0].text()

    ask_action = next(a for a in actions if a.data()[1] == "ask")
    ask_action.trigger()
    assert doc.prefs.get(ASSET_LIBRARY_EDIT) == "ask"


def test_sc_p11_ui_024_2_turning_back_to_ask_restores_the_prompt(qtbot, answer_prompt):
    """SC-P11-UI-024-2: setting the control back to "ask me" makes the next
    library-side edit in that project present the prompt again."""
    doc = _make_doc()
    doc.prefs = doc.prefs.with_value(ASSET_LIBRARY_EDIT, "always_pick_up")
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)
    menu.aboutToShow.emit()
    ask_action = next(
        a
        for a in _submenu_actions(menu, ASSET_LIBRARY_EDIT.name)
        if a.data()[1] == "ask"
    )

    ask_action.trigger()
    assert doc.prefs.get(ASSET_LIBRARY_EDIT) == "ask"

    presented = answer_prompt(action="keep")
    Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", doc.prefs)
    assert presented == [True]


def test_sc_p11_ui_024_3_switching_remembered_outcomes_takes_effect_without_a_dialog(
    qtbot, answer_prompt
):
    """SC-P11-UI-024-3: switching which outcome is remembered (via the
    submenu, no dialog involved in the switch itself) changes the NEXT
    edit's handling, without a dialog -- the surface distinguishes the two
    non-default outcomes rather than just "checked"."""
    doc = _make_doc()
    doc.prefs = doc.prefs.with_value(ASSET_LIBRARY_EDIT, "always_keep_referenced")
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)
    menu.aboutToShow.emit()
    pick_up_action = next(
        a
        for a in _submenu_actions(menu, ASSET_LIBRARY_EDIT.name)
        if a.data()[1] == "always_pick_up"
    )

    pick_up_action.trigger()  # the switch itself presents no dialog
    assert doc.prefs.get(ASSET_LIBRARY_EDIT) == "always_pick_up"

    presented = answer_prompt(action="keep")  # would win if the switch were ignored
    outcome, _ = Asset_Update_Prompt_Dialog.decide("asset-1", "Sprite A", doc.prefs)
    assert presented == []  # no dialog
    assert outcome == OUTCOME_PICK_UP  # the NEW remembered outcome, not the old one


def test_sc_p11_ui_024_4_ready_for_the_future_settings_dialog_no_second_one_here(
    qtbot,
):
    """SC-P11-UI-024-4: when phase-6's REQ-P6-UI-039 project-settings dialog
    exists, this preference is reachable there and this slice introduces no
    second settings dialog of its own.

    Scope note: no ``ui/project_settings_dialog.py`` (or any *settings_dialog*
    module) exists anywhere in this tree yet -- checked this session, glob
    below -- so the scenario's own "Given the project-settings dialog ...
    exists" precondition cannot be driven live this increment. What IS
    assertable, and what plan §3.4 argues satisfies the clause "by
    construction": the same registry-rendering seam (``value_label_for``)
    this slice's submenu uses is exported at module level for that future
    dialog to reuse rather than duplicate, and this slice ships no second
    settings-dialog module.
    """
    import pixelart_creator.ui.project_prefs_actions as ppa

    assert value_label_for(ASSET_LIBRARY_EDIT, "ask") != ""
    assert value_label_for(ASSET_LIBRARY_EDIT, "always_pick_up") != ""
    assert value_label_for(ASSET_LIBRARY_EDIT, "always_keep_referenced") != ""
    assert value_label_for(ASSET_LIBRARY_EDIT, "always_pick_up") != value_label_for(
        ASSET_LIBRARY_EDIT, "always_keep_referenced"
    )

    ui_dir = pathlib.Path(ppa.__file__).parent
    assert list(ui_dir.glob("*settings_dialog*.py")) == []


# --------------------------------------------------------------------------- #
# Cross-phase regression contract (this task's own "Additionally assert" clause) #
# --------------------------------------------------------------------------- #


def test_phase5_key_still_renders_as_a_single_checkable_entry(qtbot):
    """Cross-phase regression (plan §3.4): the phase-5
    ``confirm_cel_overwrite`` key is UNTOUCHED by this slice's renderer
    extension -- it still renders as a single checkable ``QAction`` (not a
    submenu) whose activation restores its default. This test file asserts
    it directly, in ADDITION to running (not editing)
    ``testing/suites/ui/test_project_prefs_actions.py`` unmodified, per the task's own
    instruction and P11-R2's regression obligation.
    """
    from pixelart_creator.logic.project_prefs import CONFIRM_CEL_OVERWRITE

    doc = _make_doc()
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    menu = build_project_prefs_menu(lambda: doc, lambda: None)
    qtbot.addWidget(menu)
    menu.aboutToShow.emit()

    action = next(a for a in menu.actions() if a.data() == CONFIRM_CEL_OVERWRITE.name)
    # A single checkable action, not a submenu -- the two-member domain keeps
    # the shipped binary rendering byte-for-byte.
    assert action.menu() is None
    assert action.isCheckable()
    assert action.isChecked() is True

    action.trigger()
    assert doc.prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"
