"""T20 — the ingress-actions acceptance suite (phase-11-asset-ingress).

This is the slice's load-bearing test module: it carries the assertions that make
T7-A (registration reachability), T9-A (content-key edge derivation) and T10 +
DEV-37 (import/export reachability) provably reachable, not merely present as
dead code (CF-34's class of defect). Every test drives the **shipped**
:class:`~pixelart_creator.ui.main_window.Main_Window` — its real Library-menu
``QAction``\\ s and its real, construction-time-bound
:class:`~pixelart_creator.ui.asset_library_actions.Asset_Library_Session` — never
a test-constructed session with stores bound by the test itself, which is exactly
the shape that would hide the shipped defect (ruling P11-R7, plan §3.9).

Scope boundary (so this module is not read as duplicating a sibling task):
durability across a simulated "restart" is T21's job
(``tests/ui/test_asset_durability.py``); cross-project reuse and the two
resolve/shared indicators are T22's (``tests/ui/test_asset_reference_reuse.py``).
This module borrows the "two independently bound root" idiom for SC-P11-UI-015-1
and SC-P11-UI-016-2 only because those two scenarios are on **this** task's own
``Satisfies:`` line.

Design choices disclosed up front (never silently substituted):

- The P11-R3 cycle-route and P11-R6 non-vacuity assertions call
  ``Asset_Library_Session.register_active_document`` directly rather than
  through the ``QAction`` — the window's *production* session (bound exactly as
  the shipped app binds it) is still what is exercised, and the two dedicated
  reachability-clause tests below (present-in-menu, correctly-gated,
  fresh-window-does-not-raise) already prove the ``QAction`` -> session path
  independently. This keeps the edge-derivation tests about the derivation
  WIRING route, not about re-proving menu dispatch a second time.
- The cyclic edge for the P11-R3 test is produced by monkeypatching
  ``asset_library_actions.edges_for`` for exactly one registration, **after**
  two real, unmocked registrations already produced one real, positively
  matching derived edge (satisfying P11-R6's non-vacuity clause honestly).
  Domain-level cycles are not producible through the real three relationships
  (a sprite is always a leaf), so this is the only way to exercise the VIEW's
  rejection path without re-testing ``Dependency_Graph_View.show_edges`` itself
  (already unit-tested in ``test_dependency_graph_view.py``).
- SC-P11-UI-016-1's "exactly those assets" content check calls
  ``export_library_subset`` directly (still through the window's real session)
  rather than driving ``Asset_Library_Panel``'s list-selection UI, which has no
  public multi-select setter to drive deterministically; the export ACTION's
  own presence/gating is separately proven by the reachability-clause tests.
- Every asset-content shape used to prove a **positive** derived edge is a
  shape the running application actually produces (ruling P11-R8): the
  image-import shape (``Document.from_buffer(buffer, name=...)``) or the
  ``Document()`` shape (seeded layer ``"Background"``) — never
  ``Document.from_buffer(buffer)`` with the factory default name
  (``"Imported"``), which is the one shape no user can produce.

Headless (``QT_QPA_PLATFORM=offscreen``, forced by ``tests/ui/conftest.py``).
Every test in this module runs under BOTH the light and dark theme via the
autouse ``theme`` fixture — no per-test parametrisation is needed for that.
Every asset root used here is isolated by the autouse ``_isolate_app_config``
fixture (``tests/ui/conftest.py``), which redirects
``QStandardPaths.writableLocation`` to a per-test ``tmp_path`` subdirectory for
EVERY location kind, including the ``AppLocalDataLocation`` the shipped
``Main_Window._asset_root()`` resolves — so a bare ``Main_Window()`` built in
any test here never touches the real per-user asset store. Scenarios that need
a second, independent root explicitly monkeypatch ``Main_Window._asset_root``
to a distinct ``tmp_path`` subdirectory (disclosed at each use).
"""

from __future__ import annotations

import json

from PySide6.QtWidgets import QDialog

from pixelart_creator.data import project_io
from pixelart_creator.data.asset_ingress import ARTIFACT_SUFFIX, canonical_bytes
from pixelart_creator.logic.asset_catalog import AssetKind
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.dependency_graph import DependencyEdge
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.logic.tileset import Tileset
from pixelart_creator.ui.asset_register_dialog import Asset_Register_Dialog
from pixelart_creator.ui.export_dialog import Export_Dialog
from pixelart_creator.ui.main_window import Main_Window

RED = (255, 0, 0, 255)

# ``asset_register_dialog._KIND_ORDER`` combo-index mapping, named here so a
# reader never has to cross-reference the dialog module to know what "2" means.
_KIND_SPRITE = 0
_KIND_TILESET = 2


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _accept_dialog(name: str, kind_index: int, tags: str = ""):
    """Return an ``Asset_Register_Dialog.exec`` replacement that fills + accepts.

    Mirrors the existing ``Export_Dialog.exec`` fake-exec idiom already used in
    ``tests/ui/test_export_actions.py`` — the modal ``exec()`` cannot run
    headlessly with real user input, so the fields are set directly on the
    real, constructed dialog instance before returning ``Accepted``.
    """

    def _exec(self) -> QDialog.DialogCode:
        self._name_edit.setText(name)
        self._kind_combo.setCurrentIndex(kind_index)
        self._tags_edit.setText(tags)
        return QDialog.DialogCode.Accepted

    return _exec


def _blob_count(win: Main_Window) -> int:
    root = win._asset_root()
    return len(list(root.glob("*.blob"))) if root.exists() else 0


# --------------------------------------------------------------------------- #
# SC-P11-UI-012 — register the active document                                #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_012_1_register_active_document_creates_a_verified_entry(
    qtbot, monkeypatch
):
    """SC-P11-UI-012-1 + P11-R7 clause 4 (revision #1 now records)."""
    win = _window(qtbot)
    document = win.active_document()
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Hero", _KIND_SPRITE)
    )

    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker:
        win._register_active_document_action.trigger()

    outcome = blocker.args[0]
    entries = win._asset_session.catalog().entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.asset_id == outcome.asset_id and entry.asset_id != ""
    assert entry.name == "Hero"
    assert entry.kind == AssetKind.SPRITE
    assert entry.content_hash != ""

    # The entry's content is retrievable from the store and verifies against
    # its own recorded hash.
    blob = win._asset_content_store.get(entry.content_hash)
    assert content_hash(blob) == entry.content_hash
    assert blob == canonical_bytes(document)

    # P11-R7 clause 4: a first registration records revision #1.
    assert outcome.revision_recorded is True
    history = win._asset_revision_store.history(entry.asset_id)
    assert len(history.revisions) == 1


def test_sc_p11_ui_012_2_prompt_records_the_users_own_name_kind_and_tags(
    qtbot, monkeypatch
):
    """SC-P11-UI-012-2 (positive): exactly the typed name/kind/two tags land."""
    win = _window(qtbot)
    monkeypatch.setattr(
        Asset_Register_Dialog,
        "exec",
        _accept_dialog("My Tileset", _KIND_TILESET, tags="foo, bar"),
    )

    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker:
        win._register_active_document_action.trigger()

    entry = win._asset_session.catalog().get(blocker.args[0].asset_id)
    assert entry.name == "My Tileset"
    assert entry.kind == AssetKind.TILESET
    assert entry.tags == frozenset({"foo", "bar"})


def test_sc_p11_ui_012_2_empty_or_whitespace_name_is_refused_at_the_prompt(qtbot):
    """SC-P11-UI-012-2 (negative): an empty/whitespace name disables Accept
    and shows a translatable reason, at the dialog level (RP-3)."""
    dialog = Asset_Register_Dialog(None)
    qtbot.addWidget(dialog)
    ok_button = dialog._buttons.button(dialog._buttons.StandardButton.Ok)

    assert not ok_button.isEnabled()
    assert dialog._error_label.text() != ""

    dialog._name_edit.setText("   ")  # whitespace-only
    assert not ok_button.isEnabled()
    assert dialog._error_label.text() != ""

    dialog._name_edit.setText("Real Name")
    assert ok_button.isEnabled()
    assert dialog._error_label.text() == ""


def test_sc_p11_ui_012_3_cancelling_the_prompt_registers_nothing_and_reports_no_error(
    qtbot, monkeypatch
):
    """SC-P11-UI-012-3: cancel -> no entry, no blob, no revision, no error."""
    win = _window(qtbot)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected
    )
    entries_before = win._asset_session.catalog().entries()
    blobs_before = _blob_count(win)
    errors: list[str] = []
    win._asset_session.registrationFailed.connect(errors.append)

    with qtbot.waitSignal(win._asset_session.registrationCancelled, timeout=2000):
        win._register_active_document_action.trigger()

    assert win._asset_session.catalog().entries() == entries_before
    assert _blob_count(win) == blobs_before
    # "no revision has been appended": nothing was ever registered, so there is
    # no asset_id to check a revision history against — the catalog/blob
    # invariants above are what make that true, since AssetRevisionStore.record
    # is reached only from _register_new/_reregister, neither of which ran.
    assert errors == []  # no error is reported to the user


# --------------------------------------------------------------------------- #
# SC-P11-UI-013 — register the current selection                              #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_013_1_registering_a_selection_stores_the_selected_region_only(
    qtbot, monkeypatch
):
    """SC-P11-UI-013-1: the stored content is the selected region only."""
    win = _window(qtbot)
    record = win.active_tab()
    mask = rect_mask(record.document.width, record.document.height, 2, 2, 5, 5)
    record.view.set_selection(mask)
    win._library_menu.aboutToShow.emit()
    assert win._register_selection_action.isEnabled()

    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Crop", _KIND_SPRITE)
    )

    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker:
        win._register_selection_action.trigger()

    entry = win._asset_session.catalog().get(blocker.args[0].asset_id)
    blob = win._asset_content_store.get(entry.content_hash)
    restored = project_io.deserialize(json.loads(blob))
    # bounds (2,2)-(5,5) inclusive -> a 4x4 crop, not the whole 64x64 document.
    assert (restored.width, restored.height) == (4, 4)
    assert (restored.width, restored.height) != (
        record.document.width,
        record.document.height,
    )


def test_sc_p11_ui_013_2_registering_a_selection_is_refused_when_there_is_none(
    qtbot, monkeypatch
):
    """SC-P11-UI-013-2: unavailable/reports nothing; no prompt; catalog unchanged.

    ``QAction.trigger()`` on a DISABLED action is a genuine Qt no-op (verified
    this session -- a disabled action never emits ``triggered``, so a real
    click could never reach the handler either), which is the FIRST half of
    the Gherkin's OR clause proven directly below. The handler is then also
    called directly -- the same idiom a keyboard shortcut or another code path
    could still use -- to prove its own defensive "nothing to register" report
    independently of the QAction's enabled gate (the second half of the OR).
    """
    win = _window(qtbot)
    win._library_menu.aboutToShow.emit()
    assert not win._register_selection_action.isEnabled()  # unavailable (OR clause 1)

    exec_calls: list[int] = []

    def _spy_exec(self):
        exec_calls.append(1)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(Asset_Register_Dialog, "exec", _spy_exec)
    entries_before = win._asset_session.catalog().entries()

    with qtbot.waitSignal(
        win._asset_session.registrationFailed, timeout=2000
    ) as blocker:
        win._on_register_selection()  # OR clause 2: reports nothing to register

    assert exec_calls == []  # the registration prompt never appeared
    assert win._asset_session.catalog().entries() == entries_before
    assert blocker.args[0] != ""  # reports that there is nothing to register


# --------------------------------------------------------------------------- #
# SC-P11-UI-014 — the export flow's opt-in                                    #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_014_1_taking_the_opt_in_registers_the_source_document(
    qtbot, monkeypatch, tmp_path
):
    """SC-P11-UI-014-1: file written; entry hash == source's canonical hash;
    entry metadata records the export settings used for that run."""
    win = _window(qtbot)
    document = win.active_document()
    out = tmp_path / "opted_in.png"

    def _fake_export_exec(self):
        self._format_combo.setCurrentIndex(0)  # PNG
        self._path_edit.setText(str(out))
        self._register_check.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Export_Dialog, "exec", _fake_export_exec)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Exported Doc", _KIND_SPRITE)
    )

    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker:
        win._on_export()

    assert out.exists()
    entry = win._asset_session.catalog().get(blocker.args[0].asset_id)
    assert entry.content_hash == content_hash(canonical_bytes(document))
    assert entry.metadata.get("format") == "png"
    assert entry.metadata.get("out_path") == str(out)


def test_sc_p11_ui_014_2_export_without_opt_in_leaves_everything_unchanged(
    qtbot, monkeypatch, tmp_path
):
    """SC-P11-UI-014-2: file written; catalog/store/revision history unchanged."""
    win = _window(qtbot)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Pre-existing", _KIND_SPRITE)
    )
    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker:
        win._register_active_document_action.trigger()
    pre_id = blocker.args[0].asset_id
    entries_before = win._asset_session.catalog().entries()
    blobs_before = _blob_count(win)
    revisions_before = len(win._asset_revision_store.history(pre_id).revisions)

    out = tmp_path / "no_opt_in.png"

    def _fake_export_exec(self):
        self._format_combo.setCurrentIndex(0)
        self._path_edit.setText(str(out))
        # _register_check left UNCHECKED (default) -- the opt-in itself.
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Export_Dialog, "exec", _fake_export_exec)

    with qtbot.waitSignal(win._export_controller.batchFinished, timeout=5000):
        win._on_export()

    assert out.exists()  # the export itself still happened
    assert win._asset_session.catalog().entries() == entries_before
    assert _blob_count(win) == blobs_before
    assert len(win._asset_revision_store.history(pre_id).revisions) == revisions_before


def test_sc_p11_ui_014_3_no_second_payload_format_and_every_kind_is_one_of_five(
    qtbot, monkeypatch, tmp_path
):
    """SC-P11-UI-014-3: the stored blob differs from the exported file's own
    bytes (no second payload format), and every catalog kind is shipped."""
    win = _window(qtbot)
    out = tmp_path / "kind_check.png"

    def _fake_export_exec(self):
        self._format_combo.setCurrentIndex(0)
        self._path_edit.setText(str(out))
        self._register_check.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Export_Dialog, "exec", _fake_export_exec)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("K", _KIND_SPRITE)
    )

    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker:
        win._on_export()

    entry = win._asset_session.catalog().get(blocker.args[0].asset_id)
    stored_blob = win._asset_content_store.get(entry.content_hash)
    exported_bytes = out.read_bytes()
    assert stored_blob != exported_bytes
    for descriptor in win._asset_session.catalog().entries():
        assert descriptor.kind in AssetKind


def test_p11_r7_clause_3_cancelled_export_registers_nothing(qtbot, monkeypatch):
    """A cancelled export dialog never sets a pending registration."""
    win = _window(qtbot)
    monkeypatch.setattr(Export_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    entries_before = win._asset_session.catalog().entries()

    win._on_export()

    assert win._pending_export_registration is None
    assert win._asset_session.catalog().entries() == entries_before


def test_p11_r7_clause_3_failed_export_target_registers_nothing(qtbot):
    """A failed export target clears the pending request without registering
    (the production handler, invoked exactly as the off-thread controller's
    ``targetFailed`` signal would deliver it)."""
    win = _window(qtbot)
    from pixelart_creator.ui.export_actions import Export_Registration_Request

    win._pending_export_registration = Export_Registration_Request(
        document=win.active_document(), export_metadata={"format": "png"}
    )
    entries_before = win._asset_session.catalog().entries()
    successes: list[object] = []
    win._asset_session.registrationSucceeded.connect(successes.append)

    win._on_export_target_failed(0, "simulated engine failure")

    assert win._pending_export_registration is None
    assert successes == []
    assert win._asset_session.catalog().entries() == entries_before


# --------------------------------------------------------------------------- #
# SC-P11-UI-015 / -016 — import / export a library artifact                   #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_015_1_and_016_2_import_export_round_trip_with_identical_hashes(
    qtbot, monkeypatch, tmp_path
):
    """SC-P11-UI-015-1 (imported content retrievable+verified "after a restart")
    and SC-P11-UI-016-2 (identical content hashes on another, empty library).
    Also proves "import does not re-prompt" (RP-5, T10's own Done-when)."""
    win_a = _window(qtbot)
    exec_calls: list[int] = []
    real_exec = _accept_dialog("Roundtrip", _KIND_SPRITE)

    def _spy_exec(self):
        exec_calls.append(1)
        return real_exec(self)

    monkeypatch.setattr(Asset_Register_Dialog, "exec", _spy_exec)

    with qtbot.waitSignal(
        win_a._asset_session.registrationSucceeded, timeout=5000
    ) as blocker:
        win_a._register_active_document_action.trigger()
    entry_a = win_a._asset_session.catalog().get(blocker.args[0].asset_id)
    assert exec_calls == [1]

    artifact_path = tmp_path / f"roundtrip{ARTIFACT_SUFFIX}"
    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(artifact_path), "")),
    )
    # The export action's enablement is refreshed on tab-change/menu-open, not
    # on every catalog mutation -- open the menu (the real user gesture) so
    # the registration above is reflected before the click (QAction.trigger()
    # on a disabled action is a genuine Qt no-op, verified this session).
    win_a._library_menu.aboutToShow.emit()
    assert win_a._export_library_artifact_action.isEnabled()
    with qtbot.waitSignal(win_a._asset_session.libraryExportSucceeded, timeout=5000):
        win_a._export_library_artifact_action.trigger()
    assert artifact_path.exists()

    # "Another machine": a second Main_Window bound to a DISTINCT, empty root.
    root_b = tmp_path / "machine_b"
    monkeypatch.setattr(Main_Window, "_asset_root", lambda self: root_b)
    win_b = _window(qtbot)
    assert win_b._asset_session.catalog().entries() == ()

    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (str(artifact_path), "")),
    )
    with qtbot.waitSignal(win_b._asset_session.libraryImportSucceeded, timeout=5000):
        win_b._import_library_artifact_action.trigger()

    # Import never re-prompted (RP-5) -- the spy is untouched by the import.
    assert exec_calls == [1]

    entries_b = win_b._asset_session.catalog().entries()
    assert len(entries_b) == 1
    entry_b = entries_b[0]
    assert entry_b.content_hash == entry_a.content_hash
    blob_b = win_b._asset_content_store.get(entry_b.content_hash)
    assert content_hash(blob_b) == entry_b.content_hash
    assert blob_b == win_a._asset_content_store.get(entry_a.content_hash)


def test_sc_p11_ui_015_2_importing_already_stored_content_writes_no_second_blob(
    qtbot, monkeypatch, tmp_path
):
    """SC-P11-UI-015-2: a catalog entry is added; the blob count is unchanged
    because the content is already in the store (a distinct asset_id, same
    content_hash -- true content-level dedup, not an id collision)."""
    win_a = _window(qtbot)

    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("A", _KIND_SPRITE)
    )
    with qtbot.waitSignal(
        win_a._asset_session.registrationSucceeded, timeout=5000
    ) as blocker_a:
        win_a._register_active_document_action.trigger()
    entry_a = win_a._asset_session.catalog().get(blocker_a.args[0].asset_id)

    root_b = tmp_path / "machine_b_dup"
    monkeypatch.setattr(Main_Window, "_asset_root", lambda self: root_b)
    win_b = _window(qtbot)
    # A fresh default window's default document is deterministic (no
    # randomness/clock in Document/PixelBuffer/Palette construction) -- proved
    # here rather than assumed, so the dedup this test claims is genuine.
    assert (
        content_hash(canonical_bytes(win_b.active_document())) == entry_a.content_hash
    )

    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("B", _KIND_SPRITE)
    )
    with qtbot.waitSignal(
        win_b._asset_session.registrationSucceeded, timeout=5000
    ) as blocker_b:
        win_b._register_active_document_action.trigger()
    entry_b = win_b._asset_session.catalog().get(blocker_b.args[0].asset_id)
    assert entry_b.asset_id != entry_a.asset_id
    assert entry_b.content_hash == entry_a.content_hash  # same content, new id

    artifact_path = tmp_path / f"dup{ARTIFACT_SUFFIX}"
    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(artifact_path), "")),
    )
    win_b._library_menu.aboutToShow.emit()  # refresh gating after the registration
    assert win_b._export_library_artifact_action.isEnabled()
    with qtbot.waitSignal(win_b._asset_session.libraryExportSucceeded, timeout=5000):
        win_b._export_library_artifact_action.trigger()

    blobs_before = _blob_count(win_a)
    entries_before = len(win_a._asset_session.catalog().entries())

    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (str(artifact_path), "")),
    )
    with qtbot.waitSignal(win_a._asset_session.libraryImportSucceeded, timeout=5000):
        win_a._import_library_artifact_action.trigger()

    assert len(win_a._asset_session.catalog().entries()) == entries_before + 1
    assert _blob_count(win_a) == blobs_before  # no second blob written


def test_sc_p11_ui_016_1_export_produces_exactly_the_chosen_subset(
    qtbot, monkeypatch, tmp_path
):
    """SC-P11-UI-016-1: the artifact contains exactly the chosen assets'
    entries and exactly the blobs they resolve to (proved by importing it
    into a THIRD, independent empty library and checking membership)."""
    win = _window(qtbot)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Keep", _KIND_SPRITE)
    )
    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker1:
        win._register_active_document_action.trigger()
    keep_id = blocker1.args[0].asset_id

    other_doc = Document(16, 16)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Drop", _KIND_SPRITE)
    )
    with qtbot.waitSignal(
        win._asset_session.registrationSucceeded, timeout=5000
    ) as blocker2:
        win._asset_session.register_active_document(other_doc, parent=win)
    drop_id = blocker2.args[0].asset_id
    assert drop_id != keep_id

    out_path = tmp_path / f"subset{ARTIFACT_SUFFIX}"
    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **k: (str(out_path), "")),
    )
    with qtbot.waitSignal(win._asset_session.libraryExportSucceeded, timeout=5000):
        win._asset_session.export_library_subset([keep_id], parent=win)

    root_c = tmp_path / "machine_c"
    monkeypatch.setattr(Main_Window, "_asset_root", lambda self: root_c)
    win_c = _window(qtbot)
    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (str(out_path), "")),
    )
    with qtbot.waitSignal(win_c._asset_session.libraryImportSucceeded, timeout=5000):
        win_c._import_library_artifact_action.trigger()

    entries_c = win_c._asset_session.catalog().entries()
    ids_c = {e.asset_id for e in entries_c}
    assert ids_c == {keep_id}
    assert drop_id not in ids_c
    entry_c = entries_c[0]
    blob_c = win_c._asset_content_store.get(entry_c.content_hash)
    assert content_hash(blob_c) == entry_c.content_hash


# --------------------------------------------------------------------------- #
# SC-P11-UI-017 + the P11-R7 reachability clauses                             #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_017_1_every_ingress_action_is_reachable_and_correctly_gated(qtbot):
    """P11-R7 clause 1: every ingress action of this slice is present in the
    shipped command surface, reached through the window, and enabled/disabled
    according to whether it can run."""
    win = _window(qtbot)  # a document is open by default (Main_Window's own tab)
    actions = win._library_menu.actions()
    action_names = (
        "_register_active_document_action",
        "_register_selection_action",
        "_import_library_artifact_action",
        "_export_library_artifact_action",
        "_export_project_bundle_action",
        "_import_project_bundle_action",
    )
    for name in action_names:
        assert getattr(win, name) in actions, f"{name} missing from the Library menu"

    win._library_menu.aboutToShow.emit()
    assert win._register_active_document_action.isEnabled()  # a document is open
    assert not win._register_selection_action.isEnabled()  # no active selection
    assert win._import_library_artifact_action.isEnabled()  # session-only gate
    assert not win._export_library_artifact_action.isEnabled()  # empty catalog
    assert win._export_project_bundle_action.isEnabled()  # a document is open
    assert win._import_project_bundle_action.isEnabled()  # session-only gate

    # Close the only open document: the document-scoped actions disable.
    win._tab_widget.removeTab(0)
    win._library_menu.aboutToShow.emit()
    assert not win._register_active_document_action.isEnabled()
    assert not win._register_selection_action.isEnabled()
    assert not win._export_project_bundle_action.isEnabled()
    assert win._import_library_artifact_action.isEnabled()  # unaffected
    assert win._import_project_bundle_action.isEnabled()  # unaffected


def test_sc_p11_ui_017_2_a_failed_action_says_so_and_changes_nothing(
    qtbot, monkeypatch, tmp_path, mute_message_boxes
):
    """SC-P11-UI-017-2: a failed ingress action reports a translatable message
    and leaves the catalog/store unchanged (an untrusted, malformed artifact).

    ``mute_message_boxes``: the real ``_on_import_library_artifact`` path
    passes ``parent=self`` (the window) into ``Asset_Library_Session``'s own
    ``_report_import_failure``, which pops a real, blocking ``QMessageBox`` on
    top of the ``libraryImportFailed`` signal this test asserts on -- headless
    with no automated interaction that would hang forever, so it is muted
    (the shared idiom from ``tests/ui/conftest.py``).
    """
    win = _window(qtbot)
    bad_path = tmp_path / f"garbage{ARTIFACT_SUFFIX}"
    bad_path.write_bytes(b"not a valid pixassetartifact at all")
    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **k: (str(bad_path), "")),
    )
    entries_before = win._asset_session.catalog().entries()
    blobs_before = _blob_count(win)

    with qtbot.waitSignal(
        win._asset_session.libraryImportFailed, timeout=5000
    ) as blocker:
        win._import_library_artifact_action.trigger()

    message = blocker.args[0]
    assert isinstance(message, str) and message != ""
    assert win._asset_session.catalog().entries() == entries_before
    assert _blob_count(win) == blobs_before


def test_p11_r7_clause_2_fresh_window_bindings_reach_registration_without_ingress_error(
    qtbot, monkeypatch
):
    """P11-R7 clause 2, asserted through absence-failure: a registration on a
    FRESHLY CONSTRUCTED window (this test binds nothing itself) does not raise
    ``IngressError`` -- i.e. ``bind_content_store``/``bind_revision_store`` were
    already called, exactly as the shipped ``Main_Window.__init__`` does."""
    win = _window(qtbot)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Bound", _KIND_SPRITE)
    )
    failures: list[str] = []
    win._asset_session.registrationFailed.connect(failures.append)

    with qtbot.waitSignal(win._asset_session.registrationSucceeded, timeout=5000):
        win._register_active_document_action.trigger()

    assert failures == []  # in particular, never "... not bound yet"


# --------------------------------------------------------------------------- #
# P11-R3 (cycle route) + P11-R6 (non-vacuity) + P11-R8 (production shapes)    #
# --------------------------------------------------------------------------- #


def test_p11_r3_and_r6_real_derived_edge_then_cyclic_edges_hit_show_edges_rejection(
    qtbot, monkeypatch
):
    """One test, three rulings, because the second half needs the first half's
    real graph to close a cycle against:

    - P11-R6 non-vacuity: registering a sprite then a tileset built from it
      derives one REAL, positively matching edge end to end (via the shipped
      ``Asset_Library_Session.edgesDerived -> Dependency_Graph_View.show_edges``
      route -- this session is never handed a graph directly).
    - P11-R8: both documents are production shapes (image-import + the
      ``Document()`` seeded-"Background" shape), never the factory-default
      "Imported" shape.
    - P11-R3: a THIRD registration whose derived edges close a cycle against
      that real graph leaves the registration committed and unraised, the
      session's graph UNCHANGED, and the view's cycle label visible with a
      non-empty message -- the edges travelled through
      ``Dependency_Graph_View.show_edges``'s own rejection path, never
      ``session.set_graph`` (which would have raised ``DependencyGraphError``
      into the ingress path instead of degrading passively).
    """
    win = _window(qtbot)
    view = win._dependency_graph_view
    session = win._asset_session

    sprite_buf = PixelBuffer(8, 8, ColorMode.RGBA, fill=RED)
    sprite_doc = Document.from_buffer(sprite_buf, name="hero")  # image-import shape

    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Sprite", _KIND_SPRITE)
    )
    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000) as b1:
        session.register_active_document(sprite_doc, parent=win)
    sprite_id = b1.args[0].asset_id
    assert session.graph().edges == ()  # a bare sprite has no candidates
    assert not view._cycle_label.isVisibleTo(view)

    tileset = Tileset(sprite_buf, tile_width=4, tile_height=4, name="TS")
    tileset_doc = Document(sprite_buf.width, sprite_buf.height, mode=sprite_buf.mode)
    tileset_doc.tilesets.append(tileset)  # Document() shape -- seeded "Background"

    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Tileset", _KIND_TILESET)
    )
    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000) as b2:
        session.register_active_document(tileset_doc, parent=win)
    tileset_id = b2.args[0].asset_id
    tileset_entry = session.catalog().get(tileset_id)

    # -- P11-R6 non-vacuity: the graph query returns the edge AND the reverse
    #    dependent, through the real edgesDerived -> show_edges route. -------
    assert session.graph().dependencies_of(tileset_id) == (sprite_id,)
    assert session.graph().dependents_of(sprite_id) == (tileset_id,)
    good_graph = session.graph()
    assert not view._cycle_label.isVisibleTo(view)

    # -- P11-R3 cycle route: force the THIRD registration's derived edges to
    #    close a cycle, by patching only edges_for -- the UI WIRING under
    #    test, not the domain derivation rule (already proven real above and
    #    independently covered by tests/logic/test_asset_edges.py). ---------
    def _forced_cycle_edges(descriptor, content, catalog):
        return (
            DependencyEdge(
                source_id=sprite_id,
                target_id=tileset_id,
                pinned_hash=tileset_entry.content_hash,
            ),
        )

    monkeypatch.setattr(
        "pixelart_creator.ui.asset_library_actions.edges_for", _forced_cycle_edges
    )
    third_doc = Document(4, 4)
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Third", _KIND_SPRITE)
    )

    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000):
        session.register_active_document(third_doc, parent=win)

    # Committed and unraised: the third entry IS in the catalog.
    assert len(session.catalog().entries()) == 3
    # The session's graph is UNCHANGED from before this last registration --
    # a session.set_graph(...) implementation could not pass this (a cyclic
    # DependencyGraph raises at construction).
    assert session.graph() is good_graph
    assert session.graph().dependencies_of(tileset_id) == (sprite_id,)
    # The cycle label is visible with a non-empty message.
    assert view._cycle_label.isVisibleTo(view)
    assert view._cycle_label.text() != ""
    assert "cycle" in view._cycle_label.text().lower()
