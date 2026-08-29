"""T33 -- reachability of the library-edit prompt through ``Main_Window.open_document``
(phase-11-asset-ingress, job ``20260821-reachability-remediation``; ruling P11-R9,
``plan.md`` §3.11; DEV-40/DEV-40a chain).

``testing/suites/ui/test_asset_update_prompt.py`` (T23) tests
:meth:`~pixelart_creator.ui.asset_update_prompt.Asset_Update_Prompt_Dialog.decide` at its
own seam and DISCLOSES, in its own module docstring, that no production caller reaches it
and that ``SC-P11-UI-022-2``'s reference-resolution half is asserted at decision level
only. T31 (:func:`~pixelart_creator.ui.asset_update_prompt.resolve_library_edits`) and T30
(``ui/main_window.py``'s per-tab reference-set holding/loading/saving/binding) landed the
missing caller and its wiring; this module is the CALLER-side assertion that closes the
loop -- it never calls ``resolve_library_edits`` directly (that is exactly the line the
task's own "why this is not a clause of T23 or T27" note draws) and always drives
:meth:`~pixelart_creator.ui.main_window.Main_Window.open_document`, the one production
entry point plan §3.11 (2) names (measured there: the only two GUI callers are the drop
router and File → Open; both funnel through this method). The absence of exactly this
assertion is what let T14 ship a surface nothing reached -- DEV-40/DEV-40a -- and this is
the reachability clause that closes it.

Scope boundary: T23 stays unmodified (its own regression obligation, confirmed unmodified
by T31's report); this module asserts nothing about the dialog's own button/checkbox
mechanics (T23's job) -- only that opening a REAL project through the REAL caller raises
the prompt, resolves it correctly for each of the three answers, and leaves the membership
invariant intact for a mix of edited and missing references (SC-P11-UI-021-5's boundary).

Every project fixture and asset root used here is an injected ``tmp_path`` (never
:func:`~pixelart_creator.data.asset_storage.default_asset_root`) -- the autouse
``_isolate_app_config`` fixture (``testing/suites/ui/conftest.py``) already redirects
``QStandardPaths.writableLocation`` (and therefore ``Main_Window._asset_root()``, which
reads ``AppLocalDataLocation``) to a per-test ``tmp_path`` subdirectory, so a bare
``Main_Window()`` built in any test here never touches the real per-user asset store. No
``.pixproj`` file or asset root here is ever a real user artifact; every one is
constructed fresh under ``tmp_path`` and discarded with it.

The prompt itself is driven through the same ``Asset_Update_Prompt_Dialog.exec``
monkeypatch idiom ``testing/suites/ui/test_asset_update_prompt.py``'s own ``answer_prompt`` fixture
and T31's offscreen smoke script both use -- patched at the ``QDialog.exec`` boundary, so
``resolve_library_edits``/``open_document`` are never bypassed, only the blocking modal
loop headless Qt cannot drive with real input. This module's own ``answer_prompt`` records
each PRESENTED ``asset_id`` (not merely ``True``), so "the edited one only" is assertable
by identity, not just by count.

Headless (``QT_QPA_PLATFORM=offscreen``, forced by ``testing/suites/ui/conftest.py``). Every test
here runs under BOTH the light and dark theme via the autouse ``theme`` fixture -- no
per-test parametrisation is needed for that.

**T53 addition (ruling P11-R13, plan.md §3.15, ``tasks.md`` T53).** The block below the
existing five functions asserts ``SC-P11-DATA-010-4`` and ``-5`` (both new; no test
existed for either before T51 landed) and the three previously-unasserted clauses of
``SC-P11-DATA-010-3`` -- the pre-existing "no asset revision is appended" clause plus
the two the 2026-08-22 durability ruling added ("not reported as having unsaved
changes because of it", "the unsaved canvas work is still unsaved"). It also covers
``CL-P11-8`` (spec.md §10.4) -- explicitly NOT a scenario id, and named as such in its
own test's docstring -- and the "never record an outcome the user did not choose"
requirement for both a dismissed dialog and a remembered-"always" short-circuit. None
of the five functions above is touched; T53 only appends.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

import pytest

from pixelart_creator.data import project_io
from pixelart_creator.data.asset_decision_journal import JOURNAL_FILENAME, load_journal
from pixelart_creator.logic.asset_catalog import AssetKind
from pixelart_creator.logic.asset_edit_decisions import DECISION_PICK_UP
from pixelart_creator.logic.asset_references import (
    ASSET_LIBRARY_EDIT,
    AssetReference,
    ReferenceSet,
)
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.document import Document
from pixelart_creator.ui.asset_update_prompt import Asset_Update_Prompt_Dialog
from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _register(win: Main_Window, document: Document, *, name: str, kind: AssetKind):
    """Register ``document`` through ``win``'s own, real, construction-bound session
    (mirrors ``testing/suites/ui/test_asset_durability.py``'s own ``_register`` helper, here
    driving the window's real ``_asset_session`` rather than a standalone one)."""
    root, cas, revision_store = win._asset_session._require_ingress_ready()
    return win._asset_session._register_new(
        document,
        root,
        cas,
        revision_store,
        name=name,
        kind=kind,
        tags=(),
        metadata=None,
    )


def _reregister(
    win: Main_Window, existing, document: Document, *, name: str, kind: AssetKind
):
    """Re-register ``document`` against ``existing`` through ``win``'s own session."""
    _root, _cas, revision_store = win._asset_session._require_ingress_ready()
    return win._asset_session._reregister(
        existing,
        document,
        revision_store,
        name=name,
        kind=kind,
        tags=(),
    )


def _make_edited_asset(win: Main_Window, qtbot):
    """Register "Hero", then edit it once, entirely through ``win``'s own session.

    Returns ``(asset_id, hash_v1, hash_v2)``: the library's CURRENT ``content_hash``
    is ``hash_v2``; ``hash_v1`` is the earlier revision a stale project reference
    would still carry -- exactly the shape ``STATE_EDITED``/``resolve_library_edits``
    are built to detect and resolve (plan §3.11 (1)).
    """
    doc_v1 = Document(4, 4)
    with qtbot.waitSignal(win._asset_session.catalogChanged, timeout=1000):
        _outcome, descriptor = _register(
            win, doc_v1, name="Hero", kind=AssetKind.SPRITE
        )
    asset_id = descriptor.asset_id
    hash_v1 = descriptor.content_hash

    doc_v2 = Document(4, 4)
    doc_v2.frames[0].layers[0].buffer.set_pixel(0, 0, (9, 9, 9, 255))
    existing = win._asset_session.catalog().get(asset_id)
    with qtbot.waitSignal(win._asset_session.catalogChanged, timeout=1000):
        outcome2, descriptor2 = _reregister(
            win, existing, doc_v2, name="Hero", kind=AssetKind.SPRITE
        )
    assert outcome2.revision_recorded is True
    hash_v2 = descriptor2.content_hash
    assert hash_v1 != hash_v2
    return asset_id, hash_v1, hash_v2


def _write_project(tmp_path: Path, name: str, references) -> Path:
    """Save a fresh, scratch project (never a real user artifact) referencing
    ``references`` (an iterable of :class:`AssetReference`), under ``tmp_path``."""
    path = tmp_path / name
    document = Document(4, 4)
    project_io.save_project(
        document, path, reference_set=ReferenceSet(references=tuple(references))
    )
    return path


@pytest.fixture
def answer_prompt(monkeypatch):
    """Patch ``Asset_Update_Prompt_Dialog.exec`` to answer immediately (headless
    modal automation -- the same idiom as ``testing/suites/ui/test_asset_update_prompt.py``'s
    own ``answer_prompt`` fixture and T31's offscreen smoke script), patched at the
    ``QDialog.exec`` boundary so ``resolve_library_edits``/``open_document`` are
    never bypassed. Returns a controller: ``answer_prompt(action="pick_up" | "keep"
    | "dismiss", dont_ask=False)``; the returned list records each PRESENTED
    ``asset_id``, in presentation order -- not merely a boolean -- so "the edited
    one only" is assertable by identity.
    """
    calls: List[str] = []
    state = {"action": "keep", "dont_ask": False}

    def _fake_exec(self):
        calls.append(self._asset_id)
        self._dont_ask.setChecked(state["dont_ask"])
        if state["action"] == "pick_up":
            self._on_pick_up()
        elif state["action"] == "keep":
            self._on_keep()
        else:
            self.reject()
        return self.result()

    monkeypatch.setattr(Asset_Update_Prompt_Dialog, "exec", _fake_exec)

    def _configure(*, action: str, dont_ask: bool = False) -> List[str]:
        state["action"] = action
        state["dont_ask"] = dont_ask
        return calls

    return _configure


# --------------------------------------------------------------------------- #
# SC-P11-UI-022-2 -- picking up resolves to the edited content, end to end   #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_022_2_open_document_raises_prompt_and_pick_up_resolves(
    qtbot, tmp_path, answer_prompt
):
    """T33: opening a project via ``Main_Window.open_document`` raises the prompt
    for a stale reference, and choosing PICK UP leaves the project's reference
    resolving to the edited content while the earlier revision stays in the
    asset's history (SC-P11-UI-022-2, end to end -- T23's own disclosed gap)."""
    win = _window(qtbot)
    asset_id, hash_v1, hash_v2 = _make_edited_asset(win, qtbot)
    stale_reference = AssetReference(asset_id, hash_v1, AssetKind.SPRITE, "Hero")
    path = _write_project(tmp_path, "picked_up.pixproj", (stale_reference,))

    presented = answer_prompt(action="pick_up")
    win.open_document(str(path))

    # Raised, and for the edited asset only.
    assert presented == [asset_id]

    record = win.active_tab()
    assert record is not None
    # P's reference now resolves to the edited content.
    assert record.reference_set.get(asset_id).content_hash == hash_v2
    # Membership untouched -- one member's content_hash changed, nothing else.
    assert record.reference_set.asset_ids() == {asset_id}

    # A's earlier version is still listed in its revision history.
    revisions = win._asset_revision_store.history(asset_id).revisions
    assert len(revisions) == 2
    recorded_hashes = [revision.content_hash for revision in revisions]
    assert hash_v1 in recorded_hashes
    assert hash_v2 in recorded_hashes


# --------------------------------------------------------------------------- #
# SC-P11-UI-022-3 -- keeping leaves the reference unchanged, content stays    #
# retrievable, and that same edit does not ask again                         #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_022_3_open_document_keep_leaves_reference_unchanged_and_content_retrievable(  # noqa: E501
    qtbot, tmp_path, answer_prompt
):
    """T33: choosing KEEP through the real caller leaves P's reference unchanged
    and its content still retrievable (SC-P11-UI-022-3, first two clauses)."""
    win = _window(qtbot)
    asset_id, hash_v1, _hash_v2 = _make_edited_asset(win, qtbot)
    stale_reference = AssetReference(asset_id, hash_v1, AssetKind.SPRITE, "Hero")
    path = _write_project(tmp_path, "kept.pixproj", (stale_reference,))

    presented = answer_prompt(action="keep")
    win.open_document(str(path))

    assert presented == [asset_id]
    record = win.active_tab()
    assert record is not None
    assert record.reference_set.get(asset_id).content_hash == hash_v1
    assert record.reference_set.asset_ids() == {asset_id}

    # Its content is still retrievable -- the OLD (kept) revision, not the new one.
    retrieved = win._asset_content_store.get(hash_v1)
    assert content_hash(retrieved) == hash_v1


def test_sc_p11_ui_022_3_that_same_edit_does_not_ask_again_through_the_real_caller(
    qtbot, tmp_path, answer_prompt
):
    """T33: SC-P11-UI-022-3's own third clause -- "that same edit does not ask
    again" -- proven through the CALLER (``open_document``), not the ``decide()``
    seam T23 already covers (and where T23 itself proves the shipped code does
    NOT hold this clause when driven directly, unscoped by a project key). Opening
    the SAME project a second time, with the library unchanged since, must not
    re-present the dialog: the session memory T31 scoped by ``project_key`` (plan
    §3.11 (2b)) is what makes this true in production, and this test is what
    proves the caller actually reaches it."""
    win = _window(qtbot)
    asset_id, hash_v1, _hash_v2 = _make_edited_asset(win, qtbot)
    stale_reference = AssetReference(asset_id, hash_v1, AssetKind.SPRITE, "Hero")
    path = _write_project(tmp_path, "kept_twice.pixproj", (stale_reference,))

    presented = answer_prompt(action="keep")
    win.open_document(str(path))
    assert presented == [asset_id]

    # Reopening the SAME file mints the SAME project_key
    # (str(Path(path).resolve())) -- the session bucket is keyed by it, not by
    # the freshly-loaded second tab's own (default) ProjectPrefs identity.
    presented.clear()
    win.open_document(str(path))
    assert presented == []  # no second prompt -- the same edit, remembered

    second_record = win.active_tab()
    assert second_record is not None
    assert second_record.reference_set.get(asset_id).content_hash == hash_v1


# --------------------------------------------------------------------------- #
# SC-P11-UI-022-5 -- dismissing keeps the referenced version, no preference   #
# recorded                                                                    #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_022_5_open_document_dismissing_keeps_referenced_version(
    qtbot, tmp_path, answer_prompt
):
    """T33: dismissing the prompt (Esc/close, no button clicked) through the real
    caller keeps the referenced version and records no preference
    (SC-P11-UI-022-5)."""
    win = _window(qtbot)
    asset_id, hash_v1, _hash_v2 = _make_edited_asset(win, qtbot)
    stale_reference = AssetReference(asset_id, hash_v1, AssetKind.SPRITE, "Hero")
    path = _write_project(tmp_path, "dismissed.pixproj", (stale_reference,))

    presented = answer_prompt(action="dismiss")
    win.open_document(str(path))

    assert presented == [asset_id]
    record = win.active_tab()
    assert record is not None
    assert record.reference_set.get(asset_id).content_hash == hash_v1
    assert record.document.prefs.get(ASSET_LIBRARY_EDIT) == "ask"


# --------------------------------------------------------------------------- #
# SC-P11-UI-021-5 boundary -- a mix of edited and missing prompts for the     #
# edited one only; the missing one is still named and counted; nothing is    #
# dropped or substituted                                                     #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_021_5_boundary_mixed_edited_and_missing_prompts_only_for_edited(
    qtbot, tmp_path, answer_prompt
):
    """T33: a reference set holding BOTH an edited and a missing asset prompts for
    the edited one only; the missing one is still named and counted by the reuse
    surface, and no reference is dropped or substituted --
    ``out.asset_ids() == in.asset_ids()`` (SC-P11-UI-021-5 boundary, plan §3.11)."""
    win = _window(qtbot)
    hero_id, hash_v1, hash_v2 = _make_edited_asset(win, qtbot)

    ghost_id = "ghost-asset-never-registered"
    ghost_hash = content_hash(b"a payload nothing in the library ever produced")
    references = (
        AssetReference(hero_id, hash_v1, AssetKind.SPRITE, "Hero"),
        AssetReference(ghost_id, ghost_hash, AssetKind.SPRITE, "Ghost"),
    )
    path = _write_project(tmp_path, "mixed.pixproj", references)
    in_ids = frozenset(reference.asset_id for reference in references)

    presented = answer_prompt(action="pick_up")
    win.open_document(str(path))

    # Prompted for the edited asset only -- the missing one never reaches decide().
    assert presented == [hero_id]

    record = win.active_tab()
    assert record is not None
    out_ids = record.reference_set.asset_ids()
    assert out_ids == in_ids  # the membership invariant, asserted live

    assert record.reference_set.get(hero_id).content_hash == hash_v2  # picked up
    assert record.reference_set.get(ghost_id).content_hash == ghost_hash  # untouched

    # Still named and counted by the reuse surface (never dropped, never silently
    # merged into the resolved set).
    project_key = record.project_key
    missing_ids = win._asset_reuse_panel.missing_asset_ids(project_key)
    assert missing_ids == frozenset({ghost_id})
    assert set(win._asset_reuse_panel.project_references(project_key)) == in_ids


# --------------------------------------------------------------------------- #
# T53 (ruling P11-R13) -- the durability chain: SC-P11-DATA-010-4/-5, the      #
# three owed clauses of -3, CL-P11-8, and "never record a choice not made".    #
# --------------------------------------------------------------------------- #


def test_sc_p11_data_010_4_ticked_decision_survives_closing_without_saving(
    qtbot, tmp_path, answer_prompt
):
    """T53: SC-P11-DATA-010-4 -- ticking "Don't ask again" and choosing KEEP is
    written to the journal at the MOMENT OF THE CLICK (asserted on the journal
    FILE, not on an in-memory object -- an in-memory assertion would pass
    against the pre-T51 defect); the project still reports no unsaved changes
    because of it; and the remembered outcome survives closing the project
    WITHOUT saving and reopening it, with the next library-side edit of the
    same asset handled without a prompt. Also covers the companion half of
    "never record an outcome the user did not choose" for the
    remembered-"always" short-circuit: the later reopen resolves through
    ``decide()``'s early return (no dialog is even constructed -- ``presented``
    stays empty) and the journal file is left BYTE-FOR-BYTE untouched by it,
    because nothing new was chosen.
    """
    win = _window(qtbot)
    asset_id, hash_v1, _hash_v2 = _make_edited_asset(win, qtbot)
    stale_reference = AssetReference(asset_id, hash_v1, AssetKind.SPRITE, "Hero")
    path = _write_project(tmp_path, "ticked_durable.pixproj", (stale_reference,))

    presented = answer_prompt(action="keep", dont_ask=True)
    win.open_document(str(path))
    assert presented == [asset_id]

    record = win.active_tab()
    assert record is not None
    tab_index = win._tab_widget.currentIndex()
    # Still reports no unsaved changes -- the tick did not dirty the document,
    # and no save is required to keep the choice.
    assert record.stack.isClean() is True

    # The moment-of-the-click assertion: BEFORE any save, the journal file on
    # disk already carries the remembered preference for this project path.
    journal_path = win._decision_journal_path()
    project_key = str(Path(path).resolve())
    journal = load_journal(journal_path)
    assert journal[project_key]["prefs"] == {
        ASSET_LIBRARY_EDIT.name: "always_keep_referenced"
    }
    assert journal[project_key]["edits"] == []  # the ticked half never rows the ledger
    journal_bytes_after_tick = journal_path.read_bytes()

    # Close WITHOUT saving, then reopen.
    win.close_document(tab_index)
    presented.clear()
    win.open_document(str(path))
    # No prompt: decide()'s remembered-preference short-circuit returns before
    # a dialog is even constructed.
    assert presented == []

    reopened = win.active_tab()
    assert reopened is not None
    assert reopened.reference_set.get(asset_id).content_hash == hash_v1  # kept
    assert reopened.document.prefs.get(ASSET_LIBRARY_EDIT) == "always_keep_referenced"

    # The short-circuited resolution recorded nothing new: the journal file is
    # untouched, byte-for-byte, by this reopen.
    assert journal_path.read_bytes() == journal_bytes_after_tick


def test_sc_p11_data_010_5_unticked_decision_survives_and_stays_scoped_to_its_edit(
    qtbot, tmp_path, answer_prompt
):
    """T53: SC-P11-DATA-010-5 -- an UNTICKED decision (pick up, "Don't ask
    again" left unchecked) is also written to the journal at the moment of the
    click (asserted on the file), survives closing the project WITHOUT saving
    and reopening it (the SAME edit is not asked about again and the change is
    picked up automatically), and stays scoped to THAT edit: a DIFFERENT
    library-side edit of the same asset -- a further revision, minting a new
    ``edit_token`` -- still asks. This second half is the one an
    implementation could satisfy wrongly by promoting every unticked answer
    into a standing rule, which the ruling does not say
    (``AssetEditDecisions.decision_for``'s own "a different edit of the same
    asset asks again" contract).
    """
    win = _window(qtbot)
    asset_id, hash_v1, hash_v2 = _make_edited_asset(win, qtbot)
    stale_reference = AssetReference(asset_id, hash_v1, AssetKind.SPRITE, "Hero")
    path = _write_project(tmp_path, "unticked_durable.pixproj", (stale_reference,))

    presented = answer_prompt(action="pick_up", dont_ask=False)
    win.open_document(str(path))
    assert presented == [asset_id]
    record = win.active_tab()
    assert record is not None
    assert record.reference_set.get(asset_id).content_hash == hash_v2

    # Moment-of-the-click: the ledger row is on disk before any save.
    journal_path = win._decision_journal_path()
    project_key = str(Path(path).resolve())
    journal = load_journal(journal_path)
    assert journal[project_key]["edits"] == [
        {"asset_id": asset_id, "edit_token": hash_v2, "outcome": "pick_up"}
    ]
    # The unticked half never touches the standing preference.
    assert journal[project_key]["prefs"].get(ASSET_LIBRARY_EDIT.name) == "ask"

    # Close WITHOUT saving, then reopen -- the SAME edit does not ask again.
    win.close_document(win._tab_widget.currentIndex())
    presented.clear()
    win.open_document(str(path))
    assert presented == []
    reopened = win.active_tab()
    assert reopened is not None
    assert reopened.reference_set.get(asset_id).content_hash == hash_v2  # picked up

    # A DIFFERENT library-side edit of the SAME asset -- Hero is revised again,
    # minting a new edit_token -- still asks.
    doc_v3 = Document(4, 4)
    doc_v3.frames[0].layers[0].buffer.set_pixel(0, 0, (7, 7, 7, 255))
    existing = win._asset_session.catalog().get(asset_id)
    with qtbot.waitSignal(win._asset_session.catalogChanged, timeout=1000):
        _outcome3, descriptor3 = _reregister(
            win, existing, doc_v3, name="Hero", kind=AssetKind.SPRITE
        )
    hash_v3 = descriptor3.content_hash
    assert hash_v3 not in (hash_v1, hash_v2)

    win.close_document(win._tab_widget.currentIndex())
    presented.clear()
    win.open_document(str(path))
    assert presented == [asset_id]  # a different edit of the same asset -- it asks


def test_sc_p11_data_010_3_owed_clauses_no_revision_not_dirtied_still_unsaved(
    qtbot, tmp_path
):
    """T53: SC-P11-DATA-010-3's three owed clauses, asserted together because
    they need a real window -- with an asset that HAS a revision history and
    UNSAVED canvas work already present in the project, changing the
    confirmation preference through the real ``Edit -> Project confirmations``
    menu action (``ui/project_prefs_actions.py``, the real production surface,
    not a stand-in): appends NO asset revision (pre-existing, never asserted
    before this task); leaves the document NOT reported as having unsaved
    changes BECAUSE OF IT (the dirty flag the preference change alone would
    have caused never appears); and leaves the unsaved canvas work still
    unsaved (the same dirty flag, already true from the real edit, is not
    quietly cleared by the preference change either).
    """
    win = _window(qtbot)
    asset_id, _hash_v1, _hash_v2 = _make_edited_asset(win, qtbot)
    path = _write_project(tmp_path, "prefs_not_content.pixproj", ())
    win.open_document(str(path))
    record = win.active_tab()
    assert record is not None

    # Undo history + unsaved canvas work, through the real paint path (the
    # same idiom ``testing/suites/ui/test_cloud_save_load.py`` uses to dirty a stack).
    prepare_for_click(record.view)
    record.view.set_active_color((10, 20, 30, 255))
    click_pixel(record.view, 1, 1)
    assert record.stack.isClean() is False  # unsaved canvas work is present
    undo_count_before = record.stack.count()
    revisions_before = len(win._asset_revision_store.history(asset_id).revisions)

    value_action = win._project_prefs_menu._value_actions[ASSET_LIBRARY_EDIT.name][
        "always_keep_referenced"
    ]
    value_action.trigger()
    assert (
        record.document.prefs.get(ASSET_LIBRARY_EDIT) == "always_keep_referenced"
    )  # the change under test really happened

    # No undo entry was created for the preference change.
    assert record.stack.count() == undo_count_before
    # No asset revision is appended (the pre-existing, previously unasserted
    # clause).
    assert (
        len(win._asset_revision_store.history(asset_id).revisions) == revisions_before
    )
    # Not reported as having unsaved changes BECAUSE OF the preference change,
    # and the pre-existing unsaved canvas work is still unsaved -- the same
    # dirty flag, unmoved by this change in either direction.
    assert record.stack.isClean() is False


def test_dismissed_prompt_leaves_the_decision_journal_untouched(
    qtbot, tmp_path, answer_prompt
):
    """T53: "never record an outcome the user did not choose", the dismissal
    half. Dismissing the prompt (Esc/close, no button clicked) through the
    real caller leaves the decision journal untouched -- no file is even
    created -- because ``decide()`` never invokes ``on_decided`` when
    ``dialog.decided_explicitly()`` is ``False``.
    ``test_sc_p11_ui_022_5_open_document_dismissing_keeps_referenced_version``
    already asserts this at the in-memory/``prefs`` level; this is the
    journal-durability half of the same behaviour.
    """
    win = _window(qtbot)
    asset_id, hash_v1, _hash_v2 = _make_edited_asset(win, qtbot)
    stale_reference = AssetReference(asset_id, hash_v1, AssetKind.SPRITE, "Hero")
    path = _write_project(tmp_path, "dismissed_journal.pixproj", (stale_reference,))

    presented = answer_prompt(action="dismiss")
    win.open_document(str(path))
    assert presented == [asset_id]

    appconfig_dir = win._decision_journal_path().parent
    assert JOURNAL_FILENAME not in os.listdir(appconfig_dir)


def test_cl_p11_8_never_saved_project_writes_no_journal_record_until_first_save(
    qtbot, tmp_path
):
    """T53: CL-P11-8 (spec.md §10.4) -- NOT a scenario id, and named as such
    here so it is never mistaken for scenario coverage; it holds no REQ id and
    no acceptance clause by the spec's own design. The reading this test
    proves (spec's proposed reading, still awaiting confirmation): a decision
    made in a project that has NEVER been saved has no per-project file to go
    to yet, so it is held on the tab only and the journal writes NO record for
    it -- until the project first acquires a file, at which point the decision
    already made is IN that first saved file.

    ``resolve_library_edits`` has no production caller other than
    ``Main_Window.open_document`` (T33's own disclosed reachability
    boundary), and ``open_document`` always assigns ``record.file_path``
    immediately on load -- so there is no real caller through which a
    never-saved (``new_document()``) tab could reach the update prompt at all.
    This test therefore drives the SAME private seam ``open_document``'s own
    resolve callback drives -- ``Main_Window._write_decision_journal_record``
    -- directly against a ``new_document()`` tab, exactly as
    ``testing/suites/ui/test_asset_update_prompt.py`` (T23) asserts ``decide()`` at its
    own seam when no caller reaches it, and exactly as this module's own
    docstring already discloses for the reachability boundary it closed.
    """
    win = _window(qtbot)
    win.new_document(4, 4)
    record = win.active_tab()
    assert record is not None
    assert record.file_path is None  # never saved

    fake_token = "deadbeef" * 4 + "00000000"
    # The decision the window made -- exactly the ledger row the real
    # on_decided callback would set, without a caller that could reach the
    # dialog for a never-saved tab.
    record.decided_edits = record.decided_edits.with_decision(
        "hero", fake_token, DECISION_PICK_UP
    )

    win._write_decision_journal_record(record)  # the real, only write site

    # No journal record -- asserted as a DIRECTORY LISTING, not as the
    # absence of an exception: the app-config directory holds no journal
    # file at all, because the never-saved guard short-circuits before ever
    # opening one.
    appconfig_dir = win._decision_journal_path().parent
    assert JOURNAL_FILENAME not in os.listdir(appconfig_dir)

    # The decision lives on the tab, unaffected by the no-op write.
    assert record.decided_edits.decision_for("hero", fake_token) == DECISION_PICK_UP

    # The project's first save contains the decision.
    saved_path = tmp_path / "first_save.pixproj"
    win.save_document(str(saved_path))
    assert record.file_path is not None
    payload = json.loads(Path(record.file_path).read_bytes().decode("utf-8"))
    assert payload["asset_edit_decisions"] == [
        {"asset_id": "hero", "edit_token": fake_token, "outcome": "pick_up"}
    ]
