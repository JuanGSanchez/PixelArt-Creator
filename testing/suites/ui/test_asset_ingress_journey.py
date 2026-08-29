"""T27 — the end-to-end journey the user ruled for (phase-11-asset-ingress).

Single source: ``design-docs/specs/phase-11-asset-ingress/spec.md`` §6,
``Feature: End-to-end acceptance`` / ``SC-P11-INGRESS-E2E-1``. This module
asserts the ONE scenario every sibling task asserts piecewise (T20/T21/T22)
composes: one asset, tracked through one continuous session, across all six
panels, a revision, a restore, and a restart.

**Driven through the shipped application's own command surface**, per the
task's own binding correction (``tasks.md`` T27): *register the active
document* — BOTH the first registration and the re-registration — is
triggered through the real ``_register_active_document_action`` ``QAction``
(T7-A's reachability route), never by calling
``Asset_Library_Session.register_active_document`` directly for either step
the Gherkin names. Selection propagates through the SAME signal cascade the
shipped ``Main_Window`` wires — ``Asset_Library_Panel.assetSelected`` fans out
to the tagging panel, the dependency-graph view and the version browser
(``main_window.py:848-849``, ``:868-869``, ``:911-912``) — so this module never
calls a panel's ``set_asset`` directly either; it selects the row in
``Asset_Library_Panel`` and lets the window's own wiring do the rest.
``Asset_Search_Panel`` has no ``set_session`` of its own (the D2 re-scope
wording correction the task carries): it is asserted **through its signal
path** — a query typed into it narrows ``Asset_Library_Panel`` via the shipped
``queryChanged -> Asset_Library_Panel.set_query`` connection
(``main_window.py:851-853``) — never by handing it a session.

One disclosed, evidence-grounded deviation from "always the command surface"
remains — not invented, explained where it occurs and summarised in the
report:

1. **The sprite pre-registration is SETUP, not the scenario's own step.** A
   derived edge is only non-vacuous when a SECOND, already-registered asset
   exists to reference (``edges_for`` matches a candidate's key against
   another catalog entry's ``reference_key`` — a document cannot reference
   itself). The task's own added dependency note names exactly this: T9-A
   exists so "Dependency_Graph_View shows its node and its derived edges" is
   not "vacuously satisfied by an empty set." T20 resolved the identical
   requirement the identical way (registering a sprite directly through the
   session, disclosed in its own module docstring) for the identical reason.
   The ONE registration the Gherkin actually narrates — "the user registers
   the active document as an asset" — is the tileset, and it alone is driven
   through the ``QAction``.

**History, kept rather than erased.** This module used to carry a SECOND
deviation here: the re-registration step had NO reachable command-surface
path in the shipped application — a genuine finding, not a test shortcut.
``Main_Window._on_register_active_document`` called
``self._asset_session.register_active_document(document, parent=self)`` with
no ``existing_asset_id`` — always ``None`` — so re-triggering the SAME
``QAction`` on a changed, already-registered document minted a brand-new,
distinct catalog entry, never a second revision of the existing one. That was
demonstrated directly, as its own passing characterisation test, by
``test_finding_register_active_document_action_cannot_reach_existing_asset_id``.
Because there was no UI affordance to reach it at all, the journey test below
used to call the session's own PUBLIC ``register_active_document(...,
existing_asset_id=...)`` for that one step, as a disclosed trust-boundary
shortcut.

**T43 (ruling P11-R12, DEV-43 finding 1) closed it.** ``Main_Window`` now
binds ``registered_asset_id`` to the active tab record and
``_on_register_active_document`` (``main_window.py:2753-2786``) reads that
binding and supplies it as ``existing_asset_id`` on every trigger after the
first successful one for that tab. ``register_active_document``'s
``existing_asset_id`` parameter (``asset_library_actions.py:754-786``) is no
longer an orphaned parameter as far as the shipped UI is concerned — it is
now reachable end-to-end, through the ``QAction``, exactly like every other
step. The API shortcut is therefore REMOVED below: the re-registration step
is now driven through ``_register_active_document_action.trigger()``, the
same as the first registration. The characterisation test that demonstrated
the old gap is renamed and inverted into
``test_p11_r12_register_active_document_action_reaches_existing_asset_id``,
the regression test for this fix — see its own docstring for the full
before/after.

**A third, load-bearing observation, asserted literally rather than smoothed
over — and now corrected in light of what closed it.** ``AssetRevisionStore``
(``data/asset_revision_store.py``) used to keep its per-asset history in a
plain in-memory ``dict`` (``self._histories``) with no save/load of its own —
confirmed by reading the module at the time. Only the catalog
(``asset_catalog_io``) and the CAS blobs were durable across a restart;
revision METADATA was not, and the Gherkin's restart clause — "the asset and
its revisions are still present and hash-verified" — was expected, on that
reading, to fail. **T40/T41's durable revision index fixed exactly this
gap**: ``AssetRevisionStore.bind_root`` now loads any persisted histories via
``data/asset_revision_io.load_histories``, and ``record`` persists every
recorded revision under that root (``asset_revision_store.py``'s own
``bind_root`` docstring). Revision metadata is durable across a restart now,
confirmed by re-reading the module this session, not assumed. The Gherkin's
restart clause is still asserted exactly as written — this module does not
weaken it either way, before or after the fix — and it is measured, this
session, to hold on the product's real behaviour.

Headless (``QT_QPA_PLATFORM=offscreen``, forced by ``testing/suites/ui/conftest.py``).
Both light and dark themes via the autouse ``theme`` fixture — no per-test
parametrisation needed. Every asset root is the per-test ``tmp_path`` the
autouse ``_isolate_app_config`` fixture points ``QStandardPaths`` at; every
``Main_Window`` built in this module (including the "restarted" one) resolves
to the SAME root because that redirection is fixed once per test, which is
exactly what makes the second window a faithful restart rather than another
machine (contrast T20's own use of the identical fixture to reach a
DIFFERENT, "another machine" root by monkeypatching ``_asset_root`` itself —
this module never does that).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tileset import Tileset
from pixelart_creator.ui.asset_register_dialog import Asset_Register_Dialog
from pixelart_creator.ui.main_window import Main_Window

RED = (255, 0, 0, 255)

# ``asset_register_dialog._KIND_ORDER`` combo-index mapping (matches
# ``test_asset_ingress_ui.py``'s own named constants, T20).
_KIND_SPRITE = 0
_KIND_TILESET = 2

_ROLE_ID = Qt.ItemDataRole.UserRole


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _accept_dialog(name: str, kind_index: int, tags: str = ""):
    """Return an ``Asset_Register_Dialog.exec`` replacement that fills + accepts.

    The same fake-exec idiom ``test_asset_ingress_ui.py`` (T20) and
    ``test_export_actions.py`` already use: the modal ``exec()`` cannot run
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
    """The same helper T20 uses — count of ``*.blob`` files under the asset root."""
    root = win._asset_root()
    return len(list(root.glob("*.blob"))) if root.exists() else 0


def _find_row(tree, asset_id: str, *, col: int = 0, role=_ROLE_ID):
    """Return the top-level ``QTreeWidgetItem`` whose ``role`` data at ``col``
    equals ``asset_id``, or ``None`` — a small helper needed because this
    module's catalog holds TWO entries (the setup sprite + the tracked asset)
    rather than T21's single-asset fixtures.
    """
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(col, role) == asset_id:
            return item
    return None


# --------------------------------------------------------------------------- #
# SC-P11-INGRESS-E2E-1 — the one continuous journey                          #
# --------------------------------------------------------------------------- #


def test_sc_p11_ingress_e2e_1_asset_goes_in_seen_everywhere_restored_reused(
    qtbot, monkeypatch
):
    """The full journey: register -> six panels -> revision -> restore -> restart.

    One test, one tracked asset ("Dungeon Tiles", a TILESET referencing a
    pre-registered "Hero Sprite" SPRITE so the derived-edge clause is
    non-vacuous), asserted continuously against the shipped
    :class:`~pixelart_creator.ui.main_window.Main_Window`.
    """
    win = _window(qtbot)
    session = win._asset_session

    # ---------------------------------------------------------------- #
    # SETUP (not a Gherkin step): a sprite the tracked tileset can      #
    # reference, registered directly through the session (T20's own,   #
    # identically-justified precedent — see module docstring point 1). #
    # ---------------------------------------------------------------- #
    sprite_buf = PixelBuffer(8, 8, ColorMode.RGBA, fill=RED)
    sprite_doc = Document.from_buffer(sprite_buf, name="hero")
    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Hero Sprite", _KIND_SPRITE)
    )
    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000) as b0:
        session.register_active_document(sprite_doc, parent=win)
    sprite_id = b0.args[0].asset_id

    # ---------------------------------------------------------------- #
    # STEP 1 (the Gherkin's own step): "the user registers the active  #
    # document as an asset" -- through the SHIPPED command surface     #
    # (T7-A), the whole point of this journey.                         #
    # ---------------------------------------------------------------- #
    tracked_doc = win.new_document(8, 8)  # becomes the active tab (T27 binding note)
    tileset = Tileset(sprite_buf, tile_width=4, tile_height=4, name="Tiles")
    tracked_doc.tilesets.append(tileset)
    assert win.active_document() is tracked_doc

    win._library_menu.aboutToShow.emit()  # refresh gating, the real user gesture
    assert win._register_active_document_action.isEnabled()

    monkeypatch.setattr(
        Asset_Register_Dialog,
        "exec",
        _accept_dialog("Dungeon Tiles", _KIND_TILESET, tags="dungeon, tiles"),
    )
    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000) as b1:
        win._register_active_document_action.trigger()
    asset_id = b1.args[0].asset_id
    assert asset_id != sprite_id

    entry = session.catalog().get(asset_id)
    assert entry is not None
    assert entry.name == "Dungeon Tiles"
    v1_hash = entry.content_hash

    # Non-vacuity (P11-R6/T9-A): the derived edge is REAL, not an empty set.
    assert session.graph().dependencies_of(asset_id) == (sprite_id,)
    assert session.graph().dependents_of(sprite_id) == (asset_id,)

    # Select the tracked asset in the library panel; the shipped signal
    # cascade (assetSelected) scopes tagging / graph / version-browser to it.
    library_panel = win._asset_library_panel
    row = _find_row(library_panel._tree, asset_id)
    assert row is not None, "the freshly-registered tileset is not listed"
    library_panel._tree.setCurrentItem(row)
    assert library_panel.current_asset_id() == asset_id

    # -- 1. Asset_Library_Panel lists it. --------------------------------
    assert library_panel._tree.topLevelItemCount() == 2  # sprite + tileset
    row = _find_row(library_panel._tree, asset_id)
    assert row.text(0) == "Dungeon Tiles"
    assert "Tileset" in row.text(1)

    # -- 2. Asset_Tagging_Panel shows its tags. --------------------------
    tagging_panel = win._asset_tagging_panel
    shown_tags = {
        tagging_panel._tag_list.item(i).text()
        for i in range(tagging_panel._tag_list.count())
    }
    assert shown_tags == {"dungeon", "tiles"}

    # -- 3. Asset_Search_Panel returns it for a matching query -- THROUGH  #
    #    THE SIGNAL PATH (queryChanged -> Asset_Library_Panel.set_query), #
    #    per the task's own binding correction: Asset_Search_Panel has no #
    #    set_session of its own. ------------------------------------------
    search_panel = win._asset_search_panel
    search_panel._name_edit.setText("Dungeon")
    assert library_panel._tree.topLevelItemCount() == 1
    assert library_panel._tree.topLevelItem(0).data(0, _ROLE_ID) == asset_id
    search_panel.clear()
    assert library_panel._tree.topLevelItemCount() == 2
    # Selection survives the narrow/widen round trip (the panel restores the
    # prior selection when it is still present, asset_library_panel.py's own
    # `_refresh` contract) -- confirmed, not assumed.
    assert library_panel.current_asset_id() == asset_id

    # -- 4. Dependency_Graph_View shows its node and its derived edges. --
    graph_view = win._dependency_graph_view
    assert graph_view.scope_asset_id() == asset_id
    assert graph_view._tree.topLevelItemCount() == 1
    node_item = graph_view._tree.topLevelItem(0)
    assert "Dungeon Tiles" in node_item.text(0)
    deps_group = node_item.child(0)  # "Dependencies (depends on)"
    assert deps_group.childCount() == 1
    assert "Hero Sprite" in deps_group.child(0).text(0)

    # -- 5. Asset_Version_Browser lists its first revision. --------------
    version_browser = win._asset_version_browser
    assert version_browser.current_asset_id() == asset_id
    assert version_browser._tree.topLevelItemCount() == 1

    # -- 6. Asset_Reuse_Panel shows its reuse state. ----------------------
    reuse_panel = win._asset_reuse_panel
    reuse_row = _find_row(reuse_panel._tree, asset_id)
    assert reuse_row is not None
    assert reuse_row.text(0) == "Dungeon Tiles"
    assert reuse_row.text(2) == ""  # not shared -- no open project references it

    # ------------------------------------------------------------------ #
    # STEP 2: "the user changes the document and registers it again for  #
    # the same asset" -- through the SAME `_register_active_document_    #
    # action` QAction as STEP 1 (module docstring: T43, ruling P11-R12,  #
    # closed the reachability gap this module used to characterise). The #
    # active tab's own `registered_asset_id` binding, written back when  #
    # STEP 1's trigger succeeded, is what lets THIS trigger reach         #
    # `existing_asset_id` and append a revision instead of minting a new  #
    # entry -- no session API shortcut is taken here any more.           #
    # ------------------------------------------------------------------ #
    tracked_doc.frames[0].layers[0].buffer.set_pixel(0, 0, (9, 9, 9, 255))
    monkeypatch.setattr(
        Asset_Register_Dialog,
        "exec",
        _accept_dialog("Dungeon Tiles", _KIND_TILESET, tags="dungeon, tiles"),
    )
    win._library_menu.aboutToShow.emit()  # refresh gating, the real user gesture
    assert win._register_active_document_action.isEnabled()
    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000) as b2:
        win._register_active_document_action.trigger()
    assert b2.args[0].asset_id == asset_id  # same entry, not a new one

    assert len(session.catalog().entries()) == 2  # no duplicate entry minted
    v2_hash = session.catalog().get(asset_id).content_hash
    assert v2_hash != v1_hash

    revisions = win._asset_revision_store.history(asset_id).revisions
    assert len(revisions) == 2
    assert revisions[0].content_hash == v1_hash
    assert revisions[1].content_hash == v2_hash
    assert version_browser._tree.topLevelItemCount() == 2  # auto-refreshed

    # The derived edge to the sprite survives the revision (the tileset's
    # OWN source buffer -- distinct from the mutated background layer --
    # is untouched).
    assert session.graph().dependencies_of(asset_id) == (sprite_id,)

    # ------------------------------------------------------------------ #
    # STEP 3: restore the first revision.                                #
    # ------------------------------------------------------------------ #
    version_browser._tree.setCurrentItem(version_browser._tree.topLevelItem(0))
    with qtbot.waitSignal(version_browser.revisionRestored, timeout=5000):
        version_browser._on_restore()

    current_hash = session.catalog().get(asset_id).content_hash
    assert current_hash == v1_hash
    restored_bytes = win._asset_content_store.get(current_hash)
    assert content_hash(restored_bytes) == current_hash

    after_restore = win._asset_revision_store.history(asset_id).revisions
    assert len(after_restore) == 3  # append-only restore
    assert [r.content_hash for r in after_restore[:2]] == [
        r.content_hash for r in revisions
    ]
    assert version_browser._tree.topLevelItemCount() == 3

    # ------------------------------------------------------------------ #
    # STEP 4: "the application is closed and started again".             #
    # A second Main_Window resolves the SAME root (the autouse            #
    # `_isolate_app_config` fixture fixes `_asset_root()` once per test), #
    # which is what makes this a faithful restart, not "another machine". #
    # ------------------------------------------------------------------ #
    blobs_before_restart = _blob_count(win)

    win2 = _window(qtbot)
    session2 = win2._asset_session

    entry2 = session2.catalog().get(asset_id)
    assert entry2 is not None
    assert entry2.content_hash == v1_hash  # the restored head, durable
    blob2 = win2._asset_content_store.get(entry2.content_hash)
    assert content_hash(blob2) == entry2.content_hash

    sprite_entry2 = session2.catalog().get(sprite_id)
    assert sprite_entry2 is not None

    assert _blob_count(win2) == blobs_before_restart  # no growth across restart

    # The Gherkin's own words: "the asset AND ITS REVISIONS are still
    # present and hash-verified". Asserted literally -- not narrowed to
    # "the asset's current content" -- because narrowing it would have
    # hidden exactly the gap this end-to-end test used to catch. History,
    # kept rather than erased: AssetRevisionStore used to keep its history
    # in a plain in-memory dict with no save/load of its own (confirmed by
    # reading data/asset_revision_store.py at the time), so this clause was
    # EXPECTED, on that reading, to fail here -- and it did, as its own
    # reported finding. T40/T41's durable revision index closed the gap:
    # AssetRevisionStore.bind_root now loads any persisted histories via
    # data/asset_revision_io.load_histories, and record() persists every
    # recorded revision under the bound root (confirmed by re-reading the
    # module this session). The assertion below is unchanged and unweakened
    # from what it always asserted -- it now passes on the product's real
    # behaviour, not on a narrowed clause.
    revisions2 = win2._asset_revision_store.history(asset_id).revisions
    assert len(revisions2) == 3, (
        "SC-P11-INGRESS-E2E-1's restart clause ('the asset and its "
        "revisions are still present and hash-verified') does not hold in "
        "the shipped application: a second Main_Window bound to the SAME "
        "durable root sees the catalog entry and its CURRENT content (both "
        "asserted above, and both correctly durable) but "
        f"{len(revisions2)} revisions were found for this asset_id, "
        "expected 3. This clause was a known, disclosed gap before T40/T41 "
        "added AssetRevisionStore.bind_root's persisted-history load "
        "(data/asset_revision_io.py) -- if it fails again here, that is a "
        "regression in that durability path, not a test defect, and is "
        "reported as a finding rather than patched around (AGT-06 owns no "
        "product code)."
    )


# --------------------------------------------------------------------------- #
# Regression test for ruling P11-R12 (T43, DEV-43 finding 1): the command     #
# surface CAN now re-register an existing asset through its own QAction --   #
# see module docstring for the closed finding's before/after.                #
# --------------------------------------------------------------------------- #


def test_p11_r12_register_active_document_action_reaches_existing_asset_id(
    qtbot, monkeypatch
):
    """Regression test for ruling P11-R12 -- the fix that closed a real gap.

    This test used to be
    ``test_finding_register_active_document_action_cannot_reach_existing_asset_id``,
    a passing characterisation of a real defect: triggering the SAME
    ``_register_active_document_action`` QAction twice on the SAME (changed)
    active document minted TWO DISTINCT catalog entries, never one asset with
    two revisions, because ``Main_Window._on_register_active_document`` never
    supplied ``existing_asset_id`` to
    ``Asset_Library_Session.register_active_document`` -- confirmed at the
    time by reading ``main_window.py`` and demonstrated directly by that
    test's own assertions (``second_id != first_id``, two catalog entries,
    one revision each).

    T43 closed it (ruling P11-R12): the active tab's own
    ``registered_asset_id`` binding, written back on every successful
    registration, is now read and supplied as ``existing_asset_id`` on the
    next trigger of the SAME QAction for the SAME tab. This module keeps the
    history rather than erasing it -- the assertions below are now the
    REGRESSION test for that fix, inverted from what they used to check: the
    identical two-trigger sequence must now mint ONE catalog entry with TWO
    ordered revisions carrying distinct content hashes, never two entries.
    """
    win = _window(qtbot)
    session = win._asset_session
    document = win.active_document()

    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Widget", _KIND_SPRITE)
    )
    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000) as b1:
        win._register_active_document_action.trigger()
    first_id = b1.args[0].asset_id
    assert len(win._asset_revision_store.history(first_id).revisions) == 1
    first_hash = session.catalog().get(first_id).content_hash

    # "The user changes the document" -- same live object, same active tab.
    document.frames[0].layers[0].buffer.set_pixel(0, 0, (7, 7, 7, 255))

    monkeypatch.setattr(
        Asset_Register_Dialog, "exec", _accept_dialog("Widget", _KIND_SPRITE)
    )
    with qtbot.waitSignal(session.registrationSucceeded, timeout=5000) as b2:
        win._register_active_document_action.trigger()
    second_id = b2.args[0].asset_id

    # The fixed behaviour: ONE asset, TWO ordered revisions with distinct
    # content hashes -- never a second, distinct catalog entry.
    assert second_id == first_id
    assert len(session.catalog().entries()) == 1
    revisions = win._asset_revision_store.history(first_id).revisions
    assert len(revisions) == 2
    second_hash = session.catalog().get(first_id).content_hash
    assert revisions[0].content_hash == first_hash
    assert revisions[1].content_hash == second_hash
    assert revisions[0].content_hash != revisions[1].content_hash
