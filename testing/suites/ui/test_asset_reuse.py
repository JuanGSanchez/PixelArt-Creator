"""Cross-project reuse acceptance (REQ-P11-UI-007, Gherkin: reuse without copying).

Slice 3: ``Asset_Reuse_Panel`` references an existing shared asset into a project by
``asset_id``/``content_hash`` — **never a byte copy** (reference-not-copy). The panel
holds NO domain logic (Article I / S11): a project's references are a pure ``logic``
``AssetCatalog`` of the *shared* descriptors, referencing is ``catalog.add`` of a
descriptor, and the CAS is only ``has()``-checked (a read) before referencing — the panel
NEVER calls ``ContentAddressableStore.put``, so the CAS blob count is unchanged across a
reference (the key acceptance). An asset referenced by more than one project is marked
Shared (a trivial count over the reference catalogs, not domain maths).

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture. The
panel is synchronous and worker-free, so a read-back assertion follows each call
immediately (the Slice-1/2 precedent).

The fixture stores two shared blobs (hero, dungeon) ONCE in the CAS and catalogs their
real content hashes, so referencing exercises the has()-check path with genuine hashes
and the blob-count assertion is meaningful.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_reuse_panel import (
    _COL_COUNT,
    _COL_NAME,
    _COL_SHARED,
    _ROLE_ASSET,
    Asset_Reuse_Panel,
)

_HERO = b"hero-shared-bytes"
_DUNGEON = b"dungeon-shared-bytes"
_H_HERO = content_hash(_HERO)
_H_DUNGEON = content_hash(_DUNGEON)


def _desc(asset_id, kind, name, content_hash_key):
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=content_hash_key,
    )


def _make_cas():
    """A CAS whose backend already holds the hero + dungeon blobs (stored once)."""
    backend = LocalBlobBackend()
    cas = ContentAddressableStore(backend)
    cas.put(_HERO)
    cas.put(_DUNGEON)
    return cas, backend


def _shared_catalog():
    return AssetCatalog(
        descriptors=(
            _desc("dungeon", AssetKind.TILESET, "Dungeon", _H_DUNGEON),
            _desc("hero", AssetKind.SPRITE, "Hero", _H_HERO),
        )
    )


@pytest.fixture
def panel(qtbot):
    """A bound ``Asset_Reuse_Panel`` over the shared library + a stocked CAS."""
    cas, backend = _make_cas()
    session = Asset_Library_Session(catalog=_shared_catalog())
    widget = Asset_Reuse_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget.set_content_store(cas)
    return widget, session, cas, backend


def _select_asset(widget, asset_id):
    """Select the shared-asset row whose stashed ``asset_id`` matches."""
    tree = widget._tree
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(_COL_NAME, _ROLE_ASSET) == asset_id:
            tree.setCurrentItem(item)
            return item
    raise AssertionError(f"no shared-asset row for {asset_id!r}")


def _row_by_asset(widget, asset_id):
    tree = widget._tree
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(_COL_NAME, _ROLE_ASSET) == asset_id:
            return item
    return None


# -- Criterion 4: reference references WITHOUT duplicating the payload --------- #


def test_reference_adds_a_reference_without_changing_the_cas_blob_count(panel, qtbot):
    """Referencing a shared asset leaves the CAS blob count UNCHANGED (the key acceptance).

    The panel only ``has()``-checks the shared content (a read) and adds a catalog
    reference by id/hash — it never ``put``s bytes, so no blob is duplicated.
    """
    widget, _session, _cas, backend = panel
    widget.add_project("P1")
    _select_asset(widget, "hero")
    blobs_before = len(backend._memory)
    with qtbot.waitSignal(widget.assetReferenced, timeout=1000) as blocker:
        widget._on_reference()
    # No byte copy: the CAS blob count is unchanged across the reference.
    assert len(backend._memory) == blobs_before
    assert blocker.args == ["hero", "P1"]
    # The project now holds a reference to hero (by id), and the shared blob is untouched.
    assert "hero" in widget.project_references("P1")


def test_reference_stores_reference_by_id_and_hash_not_a_copy(panel):
    """The reference the project holds is the shared descriptor (same id + content hash).

    Reference-not-copy: the project's reference catalog carries a descriptor whose
    ``asset_id``/``content_hash`` equal the shared descriptor's — a reference, not a
    duplicated payload.
    """
    widget, session, _cas, _backend = panel
    widget.add_project("P1")
    _select_asset(widget, "hero")
    widget._on_reference()
    project_catalog = widget._projects["P1"]
    referenced = project_catalog.get("hero")
    shared = session.catalog().get("hero")
    assert referenced is not None
    assert referenced.asset_id == shared.asset_id
    assert referenced.content_hash == shared.content_hash == _H_HERO


def test_reference_into_the_same_project_twice_is_surfaced_not_duplicated(panel):
    """A duplicate reference into one project surfaces a message; the count stays 1."""
    widget, _session, _cas, backend = panel
    widget.add_project("P1")
    _select_asset(widget, "hero")
    widget._on_reference()
    blobs_after_first = len(backend._memory)
    widget._on_reference()  # duplicate -> AssetCatalogModelError caught + surfaced
    assert widget.reference_count("hero") == 1
    assert len(backend._memory) == blobs_after_first  # still no new blob
    assert widget._status_label.text() != ""


def test_reference_missing_shared_bytes_is_rejected_translatably(qtbot):
    """Referencing an asset whose bytes are absent from the CAS is rejected (no reference).

    The descriptor's content hash is a valid hash never stored in the CAS, so the
    ``has()`` guard fails and the panel surfaces a translatable message without adding a
    reference.
    """
    cas, _backend = _make_cas()
    absent_hash = content_hash(b"never-stored")
    session = Asset_Library_Session(
        catalog=AssetCatalog(
            descriptors=(_desc("ghost", AssetKind.SPRITE, "Ghost", absent_hash),)
        )
    )
    widget = Asset_Reuse_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget.set_content_store(cas)
    widget.add_project("P1")
    _select_asset(widget, "ghost")
    widget._on_reference()
    assert widget.project_references("P1") == ()
    assert widget._status_label.text() != ""


# -- Criterion 5: an asset referenced by >1 project is marked Shared ----------- #


def test_asset_referenced_by_two_projects_is_marked_shared(panel):
    """Referencing hero into two projects marks its row Shared with a count of 2."""
    widget, _session, _cas, _backend = panel
    widget.add_project("P1")
    _select_asset(widget, "hero")
    widget._on_reference()
    widget.add_project("P2")
    _select_asset(widget, "hero")
    widget._on_reference()

    assert widget.reference_count("hero") == 2
    assert widget.is_shared("hero") is True
    row = _row_by_asset(widget, "hero")
    assert row.text(_COL_SHARED) == widget.tr("Shared")
    assert row.text(_COL_COUNT) == "2"


def test_asset_referenced_by_one_project_is_not_shared(panel):
    """An asset in a single project is NOT marked Shared (count 1, blank Shared cell)."""
    widget, _session, _cas, _backend = panel
    widget.add_project("P1")
    _select_asset(widget, "hero")
    widget._on_reference()
    assert widget.is_shared("hero") is False
    row = _row_by_asset(widget, "hero")
    assert row.text(_COL_SHARED) == ""
    assert row.text(_COL_COUNT) == "1"


def test_unreferenced_asset_shows_zero_count_and_no_shared(panel):
    """An asset referenced by no project shows a zero count and no Shared marker."""
    widget, _session, _cas, _backend = panel
    row = _row_by_asset(widget, "dungeon")
    assert widget.reference_count("dungeon") == 0
    assert row.text(_COL_SHARED) == ""
    assert row.text(_COL_COUNT) == "0"


# -- Criterion 6: no domain logic in the widget (binds to logic/data) --------- #


def test_shared_list_lists_exactly_the_session_catalog(panel):
    """The shared-asset list is exactly the session catalog's entries (binding)."""
    widget, session, _cas, _backend = panel
    listed = {
        widget._tree.topLevelItem(i).data(_COL_NAME, _ROLE_ASSET)
        for i in range(widget._tree.topLevelItemCount())
    }
    assert listed == {d.asset_id for d in session.catalog().entries()}


def test_reference_count_binds_to_the_project_reference_catalogs(panel):
    """``reference_count`` is a plain count over the logic AssetCatalog values."""
    widget, _session, _cas, _backend = panel
    widget.add_project("P1")
    widget.add_project("P2")
    _select_asset(widget, "hero")
    widget._on_reference()
    # The count equals the number of project catalogs whose get() resolves the id.
    manual = sum(1 for cat in widget._projects.values() if cat.get("hero") is not None)
    assert widget.reference_count("hero") == manual == 1


def test_shared_marker_refreshes_on_catalog_change(panel):
    """Adding an asset to the session catalog refreshes the shared-asset list (catalogChanged)."""
    widget, session, _cas, _backend = panel
    before = widget._tree.topLevelItemCount()
    session.add_descriptor(_desc("palette", AssetKind.PALETTE, "Sunset", _H_HERO))
    assert widget._tree.topLevelItemCount() == before + 1
    assert _row_by_asset(widget, "palette") is not None


# -- Guard branches: unbound / no-selection / no-project ---------------------- #


def test_reference_is_a_noop_without_a_session(qtbot):
    """An unbound reuse panel ignores a reference request (session-None guard)."""
    widget = Asset_Reuse_Panel()
    qtbot.addWidget(widget)
    widget.add_project("P1")
    widget._on_reference()  # must not raise


def test_reference_is_disabled_until_a_project_and_asset_are_selected(panel):
    """The Reference button enables only once both a project and an asset are chosen."""
    widget, _session, _cas, _backend = panel
    # No project yet -> disabled.
    assert not widget._reference_button.isEnabled()
    widget.add_project("P1")
    _select_asset(widget, "hero")
    assert widget._reference_button.isEnabled()


def test_reference_with_no_project_is_a_noop(panel):
    """With an asset selected but no project, referencing does nothing (no crash)."""
    widget, _session, _cas, _backend = panel
    _select_asset(widget, "hero")
    # current_project() is "" (no project added).
    widget._on_reference()
    assert widget.current_project() == ""


# -- Criterion 7: a11y (TG-05 Slice-3) ---------------------------------------- #


def test_reuse_controls_have_accessible_names(panel):
    """Every interactive reuse control carries a non-empty accessible name."""
    widget, _session, _cas, _backend = panel
    assert widget.accessibleName() != ""
    assert widget._project_combo.accessibleName() != ""
    assert widget._new_project_edit.accessibleName() != ""
    assert widget._add_project_button.accessibleName() != ""
    assert widget._tree.accessibleName() != ""
    assert widget._reference_button.accessibleName() != ""
    assert widget._status_label.accessibleName() != ""
    header = widget._tree.headerItem()
    assert all(header.text(c) != "" for c in range(widget._tree.columnCount()))


def test_reuse_controls_are_keyboard_reachable(panel):
    """Combo, new-project field, both buttons, and the tree accept keyboard focus."""
    from PySide6.QtCore import Qt

    widget, _session, _cas, _backend = panel
    for control in (
        widget._project_combo,
        widget._new_project_edit,
        widget._add_project_button,
        widget._tree,
        widget._reference_button,
    ):
        assert control.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert widget._tree.selectionMode() == widget._tree.SelectionMode.SingleSelection


def test_visible_focus_indicator_is_themed_for_the_reuse_panel():
    """A visible focus ring is themed once by role (``:focus`` QSS), both themes."""
    from PySide6.QtWidgets import QApplication

    assert ":focus" in QApplication.instance().styleSheet()


# -- Criterion 8: both themes render with role-based colours (no inline) ------ #


def test_reuse_panel_carries_no_inline_colour_and_lays_out_in_both_themes(panel, theme):
    """The panel + children carry no per-widget colour; role colours come from QSS.

    The autouse ``theme`` fixture runs this under BOTH light and dark; each widget's
    ``styleSheet`` is empty and the layout produces a valid size hint, so the panel reads
    legibly from the applied role palette in either theme.
    """
    widget, _session, _cas, _backend = panel
    for w in (
        widget,
        widget._project_combo,
        widget._new_project_edit,
        widget._add_project_button,
        widget._tree,
        widget._reference_button,
        widget._status_label,
        widget._project_label,
    ):
        assert w.styleSheet() == ""
    assert widget.sizeHint().isValid()


def test_reuse_panel_retranslates_on_language_change(panel):
    """The panel re-sets its tr() strings on ``QEvent.LanguageChange`` (F5)."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    widget, _session, _cas, _backend = panel
    QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))
    assert widget._tree.headerItem().text(0) != ""
    assert widget._add_project_button.text() != ""
    assert widget._reference_button.text() != ""
    assert widget._project_label.text() != ""
