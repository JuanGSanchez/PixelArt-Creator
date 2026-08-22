"""T33 -- reachability of the library-edit prompt through ``Main_Window.open_document``
(phase-11-asset-ingress, job ``20260821-reachability-remediation``; ruling P11-R9,
``plan.md`` §3.11; DEV-40/DEV-40a chain).

``tests/ui/test_asset_update_prompt.py`` (T23) tests
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
``_isolate_app_config`` fixture (``tests/ui/conftest.py``) already redirects
``QStandardPaths.writableLocation`` (and therefore ``Main_Window._asset_root()``, which
reads ``AppLocalDataLocation``) to a per-test ``tmp_path`` subdirectory, so a bare
``Main_Window()`` built in any test here never touches the real per-user asset store. No
``.pixproj`` file or asset root here is ever a real user artifact; every one is
constructed fresh under ``tmp_path`` and discarded with it.

The prompt itself is driven through the same ``Asset_Update_Prompt_Dialog.exec``
monkeypatch idiom ``tests/ui/test_asset_update_prompt.py``'s own ``answer_prompt`` fixture
and T31's offscreen smoke script both use -- patched at the ``QDialog.exec`` boundary, so
``resolve_library_edits``/``open_document`` are never bypassed, only the blocking modal
loop headless Qt cannot drive with real input. This module's own ``answer_prompt`` records
each PRESENTED ``asset_id`` (not merely ``True``), so "the edited one only" is assertable
by identity, not just by count.

Headless (``QT_QPA_PLATFORM=offscreen``, forced by ``tests/ui/conftest.py``). Every test
here runs under BOTH the light and dark theme via the autouse ``theme`` fixture -- no
per-test parametrisation is needed for that.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from pixelart_creator.data import project_io
from pixelart_creator.logic.asset_catalog import AssetKind
from pixelart_creator.logic.asset_references import (
    ASSET_LIBRARY_EDIT,
    AssetReference,
    ReferenceSet,
)
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.document import Document
from pixelart_creator.ui.asset_update_prompt import Asset_Update_Prompt_Dialog
from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _register(win: Main_Window, document: Document, *, name: str, kind: AssetKind):
    """Register ``document`` through ``win``'s own, real, construction-bound session
    (mirrors ``tests/ui/test_asset_durability.py``'s own ``_register`` helper, here
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
    modal automation -- the same idiom as ``tests/ui/test_asset_update_prompt.py``'s
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
