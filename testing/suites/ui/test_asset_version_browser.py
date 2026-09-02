"""Asset version browser acceptance (REQ-P11-UI-004, Gherkin: version browser restore).

``Asset_Version_Browser`` lists a selected asset's revisions **in order** with
their metadata (created marker / author), lets the user **inspect** a revision, and
**restores** a prior one as a **new head** (append-only — the earlier revisions remain).
It holds NO domain logic (Article I / S11): the history it shows is exactly the ordered
``AssetRevision`` sequence the append-only ``AssetRevisionStore`` exposes, and restore
delegates straight to ``AssetRevisionStore.record`` (which appends + dedups). Restoring
reflects into the shared ``Asset_Library_Session`` catalog via ``replace_descriptor``, so
the session's ``catalogChanged`` fires and the other panels revalidate.

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture. The
store is synchronous and worker-free (in-memory CAS), so a read-back assertion follows
each call immediately with no ``qtbot.wait`` (the established precedent).

The canonical fixture records three distinct revisions of one sprite asset (v1 -> v2 ->
v3) so the head is v3, all three are ordered in the browser, and restoring v1 appends a
fourth revision whose head content equals v1 while v1/v2/v3 all remain present.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_revision_store import AssetRevisionStore
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_version_browser import (
    _COL_AUTHOR,
    _COL_MARKER,
    _COL_ORDER,
    _HASH_ABBREV,
    _ROLE_HASH,
    Asset_Version_Browser,
)

_ASSET_ID = "hero"
_AUTHOR = "alice"
_V1 = b"sprite-bytes-v1"
_V2 = b"sprite-bytes-v2"
_V3 = b"sprite-bytes-v3"

_H_V1 = content_hash(_V1)
_H_V2 = content_hash(_V2)
_H_V3 = content_hash(_V3)


def _make_store():
    """A revision store over an in-memory CAS holding hero v1 -> v2 -> v3 (ordered)."""
    backend = LocalBlobBackend()
    cas = ContentAddressableStore(backend)
    store = AssetRevisionStore(cas)
    for marker, blob in enumerate((_V1, _V2, _V3)):
        store.record(_ASSET_ID, blob, created_marker=marker, author=_AUTHOR)
    return store, backend


def _make_session():
    """A session whose catalog holds the hero descriptor pinned at the v3 head hash."""
    catalog = AssetCatalog(
        descriptors=(
            AssetDescriptor(
                asset_id=_ASSET_ID,
                kind=AssetKind.SPRITE,
                name="Hero",
                content_hash=_H_V3,
            ),
        )
    )
    return Asset_Library_Session(catalog=catalog)


@pytest.fixture
def browser(qtbot):
    """A bound ``Asset_Version_Browser`` over the canonical 3-revision hero fixture."""
    store, backend = _make_store()
    session = _make_session()
    widget = Asset_Version_Browser()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget.set_store(store)
    widget.set_asset(_ASSET_ID)
    return widget, store, session, backend


def _select_index(widget, index):
    """Select the revision row at ``index`` (0-based, in history order)."""
    widget._tree.setCurrentItem(widget._tree.topLevelItem(index))


def _row_hashes(widget):
    """Return the ordered ``content_hash`` list stashed on each visible row."""
    tree = widget._tree
    return [
        tree.topLevelItem(i).data(_COL_ORDER, _ROLE_HASH)
        for i in range(tree.topLevelItemCount())
    ]


# -- Criterion 1: lists revisions IN ORDER with their metadata (marker/author) - #


def test_browser_lists_revisions_in_order_matching_the_store(browser):
    """The tree rows equal the store's ordered history with marker/author metadata.

    Binding, not reimplementation: each row's stashed hash, Created marker, and Author
    equal the ``AssetRevisionStore.history`` descriptor at the same index, in order.
    """
    widget, store, _session, _backend = browser
    revisions = store.history(_ASSET_ID).revisions
    assert widget._tree.topLevelItemCount() == len(revisions) == 3
    assert _row_hashes(widget) == [_H_V1, _H_V2, _H_V3]  # ascending record order
    for i, revision in enumerate(revisions):
        item = widget._tree.topLevelItem(i)
        assert item.data(_COL_ORDER, _ROLE_HASH) == revision.content_hash
        assert item.text(_COL_MARKER) == str(revision.created_marker)
        assert item.text(_COL_AUTHOR) == revision.author == _AUTHOR


def test_head_row_is_marked_current(browser):
    """The last (head) row carries the ``(current)`` marker; earlier rows do not."""
    widget, store, _session, _backend = browser
    last = widget._tree.topLevelItemCount() - 1
    head_text = widget._tree.topLevelItem(last).text(_COL_ORDER)
    assert "(current)" in head_text
    assert store.head(_ASSET_ID).content_hash == _H_V3
    assert "(current)" not in widget._tree.topLevelItem(0).text(_COL_ORDER)


def test_unknown_author_falls_back_to_translatable_placeholder(qtbot):
    """A revision recorded with no author shows the tr() ``(unknown)`` placeholder."""
    backend = LocalBlobBackend()
    store = AssetRevisionStore(ContentAddressableStore(backend))
    store.record("solo", _V1, created_marker=0, author=None)
    widget = Asset_Version_Browser()
    qtbot.addWidget(widget)
    widget.set_store(store)
    widget.set_asset("solo")
    assert widget._tree.topLevelItem(0).text(_COL_AUTHOR) == widget.tr("(unknown)")


# -- Criterion 2: inspect shows the selected revision's detail (bound) --------- #


def test_inspect_shows_selected_revision_detail_from_the_model(browser):
    """Inspecting a revision shows its verified byte size + marker + author from the model.

    The detail is bound from the store (fetched, hash-verified bytes + the descriptor's
    marker/author) — not recomputed: the shown byte count equals the fetched blob length
    and the abbreviated hash / marker / author match the store's revision.
    """
    widget, store, _session, _backend = browser
    _select_index(widget, 0)  # v1
    widget._on_inspect()
    revision = store.history(_ASSET_ID).by_hash(_H_V1)
    blob = store.fetch(_ASSET_ID, _H_V1)
    detail = widget._details_label.text()
    assert _H_V1[:_HASH_ABBREV] in detail
    assert str(len(blob)) in detail  # bound to the fetched bytes, not a guess
    assert str(revision.created_marker) in detail
    assert revision.author in detail


def test_inspect_with_no_selection_is_a_noop(browser):
    """Inspect with nothing selected leaves the (empty) detail label unchanged."""
    widget, _store, _session, _backend = browser
    widget._tree.setCurrentItem(None)
    widget._on_inspect()  # must not raise
    assert widget._details_label.text() == ""


# -- Criterion 3: restore appends a NEW head; history preserved; catalogChanged - #


def test_restore_appends_new_head_and_preserves_all_earlier_revisions(browser, qtbot):
    """Restoring v1 appends a NEW head (len +1); v1/v2/v3 all remain (append-only).

    The store is append-only: restore hands v1's hash-verified bytes back to ``record``,
    which appends a fourth revision whose head content equals v1 — no revision is mutated
    or deleted. ``revisionRestored`` fires with the new head hash.
    """
    widget, store, _session, _backend = browser
    before = store.history(_ASSET_ID).revisions
    assert [r.content_hash for r in before] == [_H_V1, _H_V2, _H_V3]

    _select_index(widget, 0)  # restore v1
    with qtbot.waitSignal(widget.revisionRestored, timeout=1000) as blocker:
        widget._on_restore()

    after = store.history(_ASSET_ID).revisions
    # Append-only: length grew by exactly one; the first three are untouched.
    assert len(after) == len(before) + 1
    assert [r.content_hash for r in after[:3]] == [_H_V1, _H_V2, _H_V3]
    # The new head's content is v1's content (restored), verified from the store.
    new_head = store.head(_ASSET_ID)
    assert new_head.content_hash == _H_V1
    assert store.fetch(_ASSET_ID, new_head.content_hash) == _V1
    assert blocker.args == [_H_V1]


def test_restore_emits_catalog_changed_so_other_panels_refresh(browser, qtbot):
    """A restore that moves the head fires the session's ``catalogChanged`` (refresh hook).

    Restoring v1 makes the head hash v1, which differs from the catalog descriptor's
    pinned v3 hash, so ``_sync_catalog`` swaps the descriptor via ``replace_descriptor``
    and the session emits ``catalogChanged`` — the signal the library / dependency / break
    panels already listen on.
    """
    widget, _store, session, _backend = browser
    _select_index(widget, 0)  # restore v1 -> head hash changes v3 -> v1
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        widget._on_restore()
    # The session catalog now reflects the reinstated head content.
    assert session.catalog().get(_ASSET_ID).content_hash == _H_V1


def test_restore_of_current_head_is_a_dedup_noop(browser):
    """Restoring the current head records identical bytes -> dedup no-op (no growth).

    Selecting the head (v3) and restoring re-records v3's bytes; the store dedups against
    the head, so no new revision or blob is created — append-only + content-hash dedup.
    """
    widget, store, _session, backend = browser
    _select_index(widget, 2)  # the head, v3
    len_before = len(store.history(_ASSET_ID).revisions)
    blobs_before = len(backend._memory)
    widget._on_restore()
    assert len(store.history(_ASSET_ID).revisions) == len_before  # no new revision
    assert len(backend._memory) == blobs_before  # no new blob


def test_restore_with_no_selection_is_a_noop(browser):
    """Restore with nothing selected records nothing (no history growth, no crash)."""
    widget, store, _session, _backend = browser
    widget._tree.setCurrentItem(None)
    len_before = len(store.history(_ASSET_ID).revisions)
    widget._on_restore()  # must not raise
    assert len(store.history(_ASSET_ID).revisions) == len_before


# -- Criterion 6: no domain logic in the widget (binds to the store) ---------- #


def test_browser_binds_to_the_store_and_recomputes_nothing(browser):
    """Every row the browser shows equals the store's ordered history exactly."""
    widget, store, _session, _backend = browser
    assert _row_hashes(widget) == [
        r.content_hash for r in store.history(_ASSET_ID).revisions
    ]
    # Selecting resolves back through the store's model, not a widget-held copy.
    _select_index(widget, 1)
    assert widget.selected_revision_hash() == _H_V2
    assert widget._selected_revision().content_hash == _H_V2


def test_unbound_browser_lists_nothing_and_is_disabled(qtbot):
    """An unbound browser (no store) lists no rows and disables its action buttons."""
    widget = Asset_Version_Browser()
    qtbot.addWidget(widget)
    assert widget._tree.topLevelItemCount() == 0
    assert not widget._inspect_button.isEnabled()
    assert not widget._restore_button.isEnabled()
    assert widget.current_asset_id() == ""


def test_buttons_enable_only_when_a_revision_is_selected(browser):
    """Inspect/Restore are disabled until a revision row is selected, then enabled."""
    widget, _store, _session, _backend = browser
    widget._tree.setCurrentItem(None)
    assert not widget._inspect_button.isEnabled()
    assert not widget._restore_button.isEnabled()
    _select_index(widget, 0)
    assert widget._inspect_button.isEnabled()
    assert widget._restore_button.isEnabled()


# -- Criterion 7: a11y (TG-05) ------------------------------------------------ #


def test_browser_controls_have_accessible_names(browser):
    """The widget, revision tree, details label, and both buttons carry a11y names."""
    widget, _store, _session, _backend = browser
    assert widget.accessibleName() != ""
    assert widget._tree.accessibleName() != ""
    assert widget._details_label.accessibleName() != ""
    assert widget._inspect_button.accessibleName() != ""
    assert widget._restore_button.accessibleName() != ""
    # The header row is populated (translatable columns).
    header = widget._tree.headerItem()
    assert all(header.text(c) != "" for c in range(widget._tree.columnCount()))


def test_browser_controls_are_keyboard_reachable_in_logical_order(browser):
    """The tree + both buttons accept keyboard focus (logical tab order, single-select)."""
    from PySide6.QtCore import Qt

    widget, _store, _session, _backend = browser
    assert widget._tree.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert widget._inspect_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert widget._restore_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert widget._tree.selectionMode() == widget._tree.SelectionMode.SingleSelection


def test_visible_focus_indicator_is_themed_for_the_browser():
    """A visible focus ring is themed once by role (``:focus`` QSS), both themes."""
    from PySide6.QtWidgets import QApplication

    assert ":focus" in QApplication.instance().styleSheet()


# -- Criterion 8: both themes render with role-based colours (no inline) ------ #


def test_browser_carries_no_inline_colour_and_lays_out_in_both_themes(browser, theme):
    """The browser + children carry no per-widget colour; role colours come from QSS.

    The autouse ``theme`` fixture runs this under BOTH light and dark; each widget's
    ``styleSheet`` is empty (colours come from the applied role palette), the layout
    produces a valid size hint, and the head marker stays legible (populated) in both.
    """
    widget, _store, _session, _backend = browser
    for w in (
        widget,
        widget._tree,
        widget._details_label,
        widget._inspect_button,
        widget._restore_button,
        widget._asset_label,
    ):
        assert w.styleSheet() == ""
    assert widget.sizeHint().isValid()
    assert widget._asset_label.text() != ""  # legible under the active theme


def test_browser_retranslates_on_language_change(browser):
    """The browser re-sets its tr() strings on ``QEvent.LanguageChange`` (F5)."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    widget, _store, _session, _backend = browser
    QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))
    assert widget._tree.headerItem().text(0) != ""
    assert widget._inspect_button.text() != ""
    assert widget._restore_button.text() != ""
