"""Asset durability across a restart (REQ-P11-DATA-008 + the six-panel/revision
acceptance it is grouped with).

Scope, precisely (plan §0's placement ruling; this task's own scope-boundary note): this
module asserts **durability** of whatever gets registered — that a catalog entry, its
content and its within-session revision history behave correctly once bound to a real
on-disk root, and that a fresh set of session/store objects pointed at the **same** root
sees exactly what an earlier set left there. It does **not** assert *reachability* — that
the shipped application's own menu actions / signal wiring reach
``Asset_Library_Session.bind_content_store`` / ``bind_revision_store`` or the registration
actions themselves. That is a sibling module's job. This suite binds its own
``Asset_Library_Session`` + stores directly (the task's own "may bind ... in its own
fixture" allowance) and drives registration through
``Asset_Library_Session._register_new`` / ``._reregister`` — the exact orchestration
:meth:`~pixelart_creator.ui.asset_library_actions.Asset_Library_Session.
register_active_document` runs *after* the shared ``Asset_Register_Dialog`` is accepted.
Bypassing only the modal prompt itself keeps this module about durability, not about
driving that dialog (a sibling module's surface) — the existing suite already reaches into
underscore-prefixed methods this way (``test_asset_version_browser.py``'s ``_on_restore``).

**"Restart" is simulated exactly**: a fresh ``Asset_Library_Session`` +
``ContentAddressableStore`` (via the same production factory,
:func:`~pixelart_creator.data.asset_cas.default_content_store`) + ``AssetRevisionStore``,
newly constructed and bound to the **same** injected root — never the same Python objects
carried over. ``AssetRevisionStore`` keeps its history in an in-memory dict with no save/
load of its own (``data/asset_revision_store.py`` — confirmed by reading it this session):
only the catalog (via ``asset_catalog_io``) and the CAS blobs (via ``LocalBlobBackend``)
are durable, so every restart-crossing assertion below is scoped to catalog + content, and
every revision-history assertion (SC-P11-UI-020-*) is scoped to one session, exactly
matching what the Gherkin for each actually claims.

Every root used here is an **injected** ``tmp_path`` — never
:func:`~pixelart_creator.data.asset_storage.default_asset_root` (the real per-user
location). The module-scoped ``_confirm_real_root_untouched`` fixture below MEASURES this
(snapshots the real root before any test in this module runs, asserts it is unchanged
after), rather than assuming the placement ruling's caveat holds.

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture
(``testing/suites/ui/conftest.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from pixelart_creator.data.asset_cas import (
    ContentAddressableStore,
    default_content_store,
)
from pixelart_creator.data.asset_ingress import canonical_bytes
from pixelart_creator.data.asset_revision_store import AssetRevisionStore
from pixelart_creator.data.asset_storage import default_asset_root
from pixelart_creator.logic.asset_catalog import AssetKind
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.document import Document
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_library_panel import Asset_Library_Panel
from pixelart_creator.ui.asset_reuse_panel import Asset_Reuse_Panel
from pixelart_creator.ui.asset_search_panel import Asset_Search_Panel
from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel
from pixelart_creator.ui.asset_version_browser import Asset_Version_Browser
from pixelart_creator.ui.dependency_graph_view import Dependency_Graph_View

# --------------------------------------------------------------------------- #
# Placement-ruling isolation — MEASURED, not assumed (plan §0, O-1's caveat). #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module", autouse=True)
def _confirm_real_root_untouched():
    """Snapshot the REAL per-user asset root before this module runs; assert unchanged after.

    ``default_asset_root()`` only *computes* ``~/.pixelart_creator/assets`` (module
    docstring, confirmed by reading it this session) — this fixture never creates it,
    it only reads (``exists`` / ``iterdir``) to prove that every test in this module,
    which binds exclusively to injected ``tmp_path`` roots, left it exactly as found.
    """
    real_root = default_asset_root()
    existed_before = real_root.exists()
    before = sorted(p.name for p in real_root.iterdir()) if existed_before else None
    yield
    existed_after = real_root.exists()
    assert existed_after == existed_before, (
        f"a test in this module touched the REAL per-user asset root {real_root} — "
        "every root here must be an injected tmp_path"
    )
    if existed_after:
        after = sorted(p.name for p in real_root.iterdir())
        assert after == before, (
            f"the REAL per-user asset root {real_root} gained/lost entries during "
            "this module's run"
        )


def test_injected_roots_are_never_the_real_per_user_location(tmp_path):
    """The placement ruling's own caveat, confirmed structurally for every root used here.

    Every root this module binds a session to is a ``tmp_path`` descendant; none is, or
    contains, or is contained by, :func:`default_asset_root` — the real per-user location
    the shipped application resolves via ``Path.home()``.

    Checked twice: once on the raw ``Path`` values (catches a plain identity/containment
    bug outright) and once ``.resolve()``d (catches the same bug hiding behind a
    case-insensitive filesystem or a symlinked temp root — e.g. macOS's ``/tmp`` ->
    ``/private/tmp`` — where the raw strings would differ but the real, on-disk location
    would not).

    This deliberately does NOT assert that ``injected_root`` avoids ``Path.home()``
    altogether: a hosted CI runner's own temp root legitimately nests under the actor's
    home directory (``RUNNER_TEMP`` under ``/home/runner`` on the Ubuntu/macOS hosted
    runners), so "is it under home" is a fact about the CI environment, not about whether
    this is the real *per-user asset* location — that is the narrower, correct claim this
    test's name makes, and it is what every assertion below actually checks. An earlier
    version of this test also asserted the broader "not under Path.home() at all" claim as
    a proxy for the real one; that proxy held only by coincidence of the retired
    self-hosted Windows runner's temp path living outside the user's home directory, and
    it stopped holding the moment CI moved to hosted runners — it was never a true
    positive for a durability defect, so removing it in favour of the precise, resolved
    checks below is a strictly better test, not a widened tolerance.
    """
    real_root = default_asset_root()
    injected_root = tmp_path / "isolation_check_root"
    assert injected_root != real_root
    assert real_root not in injected_root.parents
    assert injected_root not in real_root.parents
    assert str(injected_root).startswith(str(tmp_path))

    resolved_injected = injected_root.resolve()
    resolved_real = real_root.resolve()
    assert resolved_injected != resolved_real
    assert resolved_real not in resolved_injected.parents
    assert resolved_injected not in resolved_real.parents


# --------------------------------------------------------------------------- #
# Fixture helpers                                                             #
# --------------------------------------------------------------------------- #


def _make_document(width: int = 4, height: int = 4) -> Document:
    """A document shape the application actually produces: one seeded "Background"
    layer (``Document.__init__``, ``logic/document.py``) — never the from_buffer/
    factory-default ``"Imported"`` shape no user can produce (a sibling task's ITEM-2
    consequence note; not this task's own concern, since it derives no dependency
    edge, but the same reachable-shape discipline costs nothing to keep here too).
    """
    return Document(width, height)


def _paint_distinct(document: Document, marker: int) -> None:
    """Mutate one pixel so ``document``'s canonical bytes differ from another's."""
    document.frames[0].layers[0].buffer.set_pixel(0, 0, (marker % 256, 0, 0, 255))


def _bound_session(root: Path):
    """A fresh ``(session, cas, revision_store)`` bound to ``root`` — one "process".

    Mirrors ``ui/main_window.py``'s own construction order exactly (``:819`` bind_root,
    ``:870`` ``default_content_store(root)``, ``:877-878`` bind_content_store /
    bind_revision_store) so this fixture's wiring is the production wiring, not an
    invented shortcut.
    """
    cas = default_content_store(root)
    revision_store = AssetRevisionStore(cas)
    session = Asset_Library_Session()
    session.bind_root(root)
    session.bind_content_store(cas)
    session.bind_revision_store(revision_store)
    return session, cas, revision_store


def _register(
    session: Asset_Library_Session, document: Document, *, name, kind, tags=()
):
    """Drive one first-time registration via the session's own post-dialog orchestration.

    Calls :meth:`Asset_Library_Session._register_new` directly — the exact code path
    ``register_active_document`` runs after ``Asset_Register_Dialog.exec()`` returns
    Accepted (module docstring). Returns ``(RegistrationOutcome, AssetDescriptor)``.
    """
    root, cas, revision_store = session._require_ingress_ready()
    return session._register_new(
        document,
        root,
        cas,
        revision_store,
        name=name,
        kind=kind,
        tags=tuple(tags),
        metadata=None,
    )


def _reregister(
    session: Asset_Library_Session, existing, document: Document, *, name, kind, tags=()
):
    """Drive one re-registration via the session's own post-dialog orchestration."""
    _root, _cas, revision_store = session._require_ingress_ready()
    return session._reregister(
        existing,
        document,
        revision_store,
        name=name,
        kind=kind,
        tags=tuple(tags),
    )


# --------------------------------------------------------------------------- #
# SC-P11-DATA-008-1 / -2 — the base durability + negative-space guarantees   #
# --------------------------------------------------------------------------- #


def test_sc_p11_data_008_1_registered_asset_survives_restart(tmp_path, qtbot):
    """A registered asset is listed after a restart, content retrievable + hash-verified."""
    root = tmp_path / "asset_root"
    session, _cas, _revision_store = _bound_session(root)
    document = _make_document()
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        _outcome, descriptor = _register(
            session, document, name="Hero", kind=AssetKind.SPRITE, tags=("hero",)
        )
    asset_id = descriptor.asset_id
    original_bytes = canonical_bytes(document)

    # "Restart": brand-new objects bound to the SAME root, nothing carried over.
    session2, cas2, _revision_store2 = _bound_session(root)

    restored = session2.catalog().get(asset_id)
    assert restored is not None
    assert restored.name == "Hero"
    assert restored.kind == AssetKind.SPRITE
    assert restored.tags == frozenset({"hero"})

    fetched = cas2.get(restored.content_hash)  # CAS.get() itself content-hash-verifies
    assert fetched == original_bytes
    assert (
        content_hash(fetched) == restored.content_hash
    )  # explicit, observable re-check


def test_sc_p11_data_008_2_opening_without_registering_creates_no_store_directory(
    tmp_path,
):
    """Opening (binding) and closing without registering anything creates NO store dir.

    Keeps ``REQ-P11-DATA-008``'s second clause honest: neither ``bind_root`` (reads only,
    confirmed by reading ``asset_library_actions.py`` this session) nor
    ``default_content_store``/``LocalBlobBackend.__init__`` (computes/stores a path,
    performs no ``mkdir`` — confirmed by reading ``asset_storage.py``) touches the
    filesystem; only a write (``put_blob`` / ``save_catalog``) would create ``root``.
    """
    root = tmp_path / "unregistered_root"
    assert not root.exists()

    session, cas, revision_store = _bound_session(root)  # "opens" the application
    del session, cas, revision_store  # "closes" it — nothing pending, nothing to flush

    assert not root.exists()


# --------------------------------------------------------------------------- #
# SC-P11-UI-018-1 / -2 — the six panels carry real content, from one source  #
# --------------------------------------------------------------------------- #


def _bind_six_panels(qtbot, session, cas, revision_store, asset_id):
    """Bind all six asset surfaces to ``session`` (this task's own fixture; five ``set_session``
    bindings plus the search panel's ``queryChanged -> set_query`` signal wiring, per the
    D2 re-scope: ``Asset_Search_Panel`` has no ``set_session`` of its own,
    ``main_window.py:829-831``).
    """
    library_panel = Asset_Library_Panel()
    qtbot.addWidget(library_panel)
    library_panel.set_session(session)

    tagging_panel = Asset_Tagging_Panel()
    qtbot.addWidget(tagging_panel)
    tagging_panel.set_session(session)
    tagging_panel.set_asset(asset_id)

    search_panel = Asset_Search_Panel()
    qtbot.addWidget(search_panel)
    search_panel.queryChanged.connect(library_panel.set_query)

    graph_view = Dependency_Graph_View()
    qtbot.addWidget(graph_view)
    graph_view.set_session(session)
    graph_view.set_asset(asset_id)  # scopes the view so a node shows with zero edges

    version_browser = Asset_Version_Browser()
    qtbot.addWidget(version_browser)
    version_browser.set_session(session)
    version_browser.set_store(revision_store)
    version_browser.set_asset(asset_id)

    reuse_panel = Asset_Reuse_Panel()
    qtbot.addWidget(reuse_panel)
    reuse_panel.set_session(session)
    reuse_panel.set_content_store(cas)

    return (
        library_panel,
        tagging_panel,
        search_panel,
        graph_view,
        version_browser,
        reuse_panel,
    )


def test_sc_p11_ui_018_1_one_registered_asset_appears_in_all_six_surfaces(
    tmp_path, qtbot
):
    """One registered asset appears, correctly, in every one of the six surfaces."""
    root = tmp_path / "six_panels_root"
    session, cas, revision_store = _bound_session(root)
    document = _make_document()
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        _outcome, descriptor = _register(
            session,
            document,
            name="Hero",
            kind=AssetKind.SPRITE,
            tags=("hero", "protagonist"),
        )
    asset_id = descriptor.asset_id

    (
        library_panel,
        tagging_panel,
        search_panel,
        graph_view,
        version_browser,
        reuse_panel,
    ) = _bind_six_panels(qtbot, session, cas, revision_store, asset_id)

    # 1. Asset_Library_Panel lists the asset with its kind and name.
    assert library_panel._tree.topLevelItemCount() == 1
    row = library_panel._tree.topLevelItem(0)
    assert row.text(0) == "Hero"
    assert "Sprite" in row.text(1)

    # 2. Asset_Tagging_Panel shows the tag set and accepts an edit to it.
    shown_tags = {
        tagging_panel._tag_list.item(i).text()
        for i in range(tagging_panel._tag_list.count())
    }
    assert shown_tags == {"hero", "protagonist"}
    tagging_panel._tag_edit.setText("boss")
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        qtbot.mouseClick(tagging_panel._add_button, Qt.MouseButton.LeftButton)
    assert "boss" in session.catalog().get(asset_id).tags

    # 3. Asset_Search_Panel returns the asset for a query matching its name, tag or kind.
    search_panel._name_edit.setText("Hero")
    assert library_panel._tree.topLevelItemCount() == 1
    search_panel.clear()
    search_panel._tag_edit.setText("boss")
    assert library_panel._tree.topLevelItemCount() == 1
    search_panel.clear()
    search_panel._kind_combo.setCurrentIndex(1)  # AssetKind.SPRITE, per _KIND_ORDER[0]
    assert library_panel._tree.topLevelItemCount() == 1
    search_panel.clear()

    # 4. Dependency_Graph_View shows a node for the asset.
    assert graph_view._tree.topLevelItemCount() == 1
    assert "Hero" in graph_view._tree.topLevelItem(0).text(0)

    # 5. Asset_Version_Browser lists at least one revision for the asset.
    assert version_browser._tree.topLevelItemCount() >= 1

    # 6. Asset_Reuse_Panel shows the asset with its reuse state.
    assert reuse_panel._tree.topLevelItemCount() == 1
    reuse_row = reuse_panel._tree.topLevelItem(0)
    assert reuse_row.text(0) == "Hero"
    assert reuse_row.text(2) == ""  # not shared — no project references it yet


def test_sc_p11_ui_018_2_the_six_surfaces_cannot_disagree(tmp_path, qtbot):
    """A tag added on the tagging panel propagates to library + search, unreopened."""
    root = tmp_path / "six_panels_root_2"
    session, cas, revision_store = _bound_session(root)
    document = _make_document()
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        _outcome, descriptor = _register(
            session, document, name="Hero", kind=AssetKind.SPRITE, tags=()
        )
    asset_id = descriptor.asset_id

    library_panel = Asset_Library_Panel()
    qtbot.addWidget(library_panel)
    library_panel.set_session(session)

    tagging_panel = Asset_Tagging_Panel()
    qtbot.addWidget(tagging_panel)
    tagging_panel.set_session(session)
    tagging_panel.set_asset(asset_id)

    search_panel = Asset_Search_Panel()
    qtbot.addWidget(search_panel)
    search_panel.queryChanged.connect(library_panel.set_query)

    # Every panel above is bound exactly once, before the edit below — the point of
    # this scenario is that NEITHER is reopened / re-bound for the propagation to hold.
    tagging_panel._tag_edit.setText("magic")
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        qtbot.mouseClick(tagging_panel._add_button, Qt.MouseButton.LeftButton)

    # Library shows the new tag without being reopened.
    assert library_panel._tree.topLevelItemCount() == 1
    assert "magic" in library_panel._tree.topLevelItem(0).text(2).split(", ")

    # Search returns the asset for a query on that tag.
    search_panel._tag_edit.setText("magic")
    assert library_panel._tree.topLevelItemCount() == 1
    assert library_panel._tree.topLevelItem(0).text(0) == "Hero"


# --------------------------------------------------------------------------- #
# SC-P11-UI-019-1 — N assets registered + tagged in one session, restart      #
# --------------------------------------------------------------------------- #

#: KNOWN CRASH, macOS only, INTERMITTENT — diagnosed here, ruled by the
#: user (2026-08-31, reaffirmed 2026-09-01): skip rather than let it kill the
#: xdist worker with no test outcome to record. First observed at commit
#: ``55c73a3`` — this file's own fix, tightening
#: ``test_injected_roots_are_never_the_real_per_user_location`` to assert the
#: real per-user-asset-location claim in place of a broad ``Path.home()``
#: proxy that had been failing early on macOS before that commit. Three
#: hosted runs, same leg (quality-gate, macos-latest): 33427869334 (head
#: ``e3bc50d``, before the fix — this test PASSED), 33432594426 (head
#: ``55c73a3``, the fix — SEGFAULT), 33437883062 (head ``331146a`` —
#: SEGFAULT again). Never reproduced on ubuntu or windows.
#: RE-MEASURED 2026-09-01 on hosted macOS run 33486412746 with this
#: ``skipif`` temporarily removed, under the THIRD condition — full suite,
#: ``-n auto``, test active — that had crashed twice before: 8394 passed, 9
#: skipped, 2 xfailed, **0 failed**, no crash. The module run alone (both
#: with and without xdist) also passed clean. So the fault did not reproduce
#: under any of the three conditions tried, including the exact one that
#: crashed on 33432594426 and 33437883062. This substantially weakens — it
#: does NOT confirm or refute — the theory that this test's own Qt teardown
#: is deterministically broken; it now reads as an INTERMITTENT, UNRESOLVED
#: fault, not a diagnosed defect with a known trigger. The marker stays
#: precisely because of that: ``main`` requires all CI checks with no
#: bypass, and a fault that fires unpredictably would block merges at
#: random with no override if left unskipped.
#: UNRESOLVED whether the fault is in the product's own Qt/PySide6 object
#: lifecycle (this test builds two full session/CAS/revision-store stacks via
#: ``_bound_session()`` plus an ``Asset_Tagging_Panel`` and an
#: ``Asset_Library_Panel``, none explicitly torn down before the next is
#: constructed) or in the offscreen-QPA / pytest-xdist harness itself. The
#: product/harness investigation belongs to a follow-up PR, tracked by a
#: GitHub issue filed separately (not by this agent). ``xfail`` is not used
#: here: a segmentation fault kills the worker process outright, so there is
#: no test outcome for pytest to mark as expected-failing — only ``skipif``
#: can express "do not run this on macOS" for a crash.
_MACOS_XDIST_SEGFAULT_SKIP_REASON = (
    "SC-P11-UI-019-1: segfaults the pytest-xdist worker on macOS only, "
    "INTERMITTENTLY — never reproduced on ubuntu or windows. First observed "
    "at commit 55c73a3 (this file's own fix, tightening "
    "test_injected_roots_are_never_the_real_per_user_location to assert the "
    "real per-user-asset-location claim instead of a broad Path.home() "
    "proxy that had been failing early on macOS before that commit): before "
    "that commit this test passed (hosted run 33427869334, head e3bc50d); "
    "at that commit (33432594426, head 55c73a3) and the next (33437883062, "
    "head 331146a) it segfaulted the worker instead. RE-MEASURED "
    "2026-09-01: hosted macOS run 33486412746 with this skipif temporarily "
    "removed did NOT reproduce the crash under any of three conditions, "
    "including the exact full-suite -n auto configuration that crashed "
    "twice before (8394 passed, 9 skipped, 2 xfailed, 0 failed, no crash). "
    "The fault is therefore INTERMITTENT and NOT reproducible on demand, "
    "which weakens but does not settle the theory that this test's own Qt "
    "teardown is deterministically broken — treat the cause as UNRESOLVED, "
    "not diagnosed. Whether the fault originates in the product's own "
    "Qt/PySide6 object lifecycle (this test builds two full "
    "session/CAS/revision-store stacks via _bound_session() plus an "
    "Asset_Tagging_Panel and an Asset_Library_Panel, none explicitly torn "
    "down before the next is constructed) or in the offscreen-QPA / "
    "pytest-xdist harness itself remains open — investigate in a follow-up "
    "PR before removing this marker. A GitHub issue has been filed "
    "separately (not by this agent). The marker stays despite the "
    "non-reproduction because main requires all CI checks with no bypass, "
    "and an intermittent segfault would otherwise block merges at random "
    "with no override. xfail cannot be used here: a segmentation fault "
    "kills the worker process outright, leaving no test outcome to mark as "
    "expected-failing."
)

_macos_xdist_segfault_skip = pytest.mark.skipif(
    condition=sys.platform == "darwin",
    reason=_MACOS_XDIST_SEGFAULT_SKIP_REASON,
)


@_macos_xdist_segfault_skip
def test_sc_p11_ui_019_1_library_repopulated_after_restart(tmp_path, qtbot):
    """N assets registered and tagged in one session are all present, intact, after a restart."""
    root = tmp_path / "n_assets_root"
    session, _cas, _revision_store = _bound_session(root)

    specs = (
        ("Hero", AssetKind.SPRITE, "hero"),
        ("Dungeon Tiles", AssetKind.TILESET, "dungeon"),
        ("Walk Cycle", AssetKind.ANIMATION, "walk"),
    )
    expected = {}
    for marker, (name, kind, tag) in enumerate(specs, start=1):
        document = _make_document()
        _paint_distinct(document, marker)
        with qtbot.waitSignal(session.catalogChanged, timeout=1000):
            _outcome, descriptor = _register(
                session, document, name=name, kind=kind, tags=()
            )
        expected[descriptor.asset_id] = (
            name,
            kind,
            frozenset({tag}),
            canonical_bytes(document),
        )

    tagging_panel = Asset_Tagging_Panel()
    qtbot.addWidget(tagging_panel)
    tagging_panel.set_session(session)
    for asset_id, (_name, _kind, tags, _blob) in expected.items():
        tagging_panel.set_asset(asset_id)
        tagging_panel._tag_edit.setText(next(iter(tags)))
        with qtbot.waitSignal(session.catalogChanged, timeout=1000):
            qtbot.mouseClick(tagging_panel._add_button, Qt.MouseButton.LeftButton)

    # "Restart": brand-new objects over the SAME root.
    session2, cas2, _revision_store2 = _bound_session(root)
    library_panel = Asset_Library_Panel()
    qtbot.addWidget(library_panel)
    library_panel.set_session(session2)

    assert library_panel._tree.topLevelItemCount() == len(specs)
    assert len(session2.catalog().entries()) == len(specs)
    for asset_id, (name, kind, tags, original_bytes) in expected.items():
        restored = session2.catalog().get(asset_id)
        assert restored is not None
        assert restored.name == name
        assert restored.kind == kind
        assert restored.tags == tags
        fetched = cas2.get(restored.content_hash)
        assert fetched == original_bytes


# --------------------------------------------------------------------------- #
# SC-P11-UI-020-1 / -2 — revisions over real content (one session; the store  #
# has no save/load of its own — see the module docstring)                    #
# --------------------------------------------------------------------------- #


def test_sc_p11_ui_020_1_changed_content_appends_a_revision_and_restores(
    tmp_path, qtbot
):
    """Changed content appends a 2nd revision; restoring the 1st brings back its content."""
    root = tmp_path / "revisions_root"
    session, cas, revision_store = _bound_session(root)

    doc_v1 = _make_document()
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        _outcome, descriptor = _register(
            session, doc_v1, name="Hero", kind=AssetKind.SPRITE, tags=()
        )
    asset_id = descriptor.asset_id
    v1_bytes = canonical_bytes(doc_v1)

    doc_v2 = _make_document()
    _paint_distinct(doc_v2, 1)
    existing = session.catalog().get(asset_id)
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        outcome2, _descriptor2 = _reregister(
            session, existing, doc_v2, name="Hero", kind=AssetKind.SPRITE, tags=()
        )
    assert outcome2.revision_recorded is True

    version_browser = Asset_Version_Browser()
    qtbot.addWidget(version_browser)
    version_browser.set_session(session)
    version_browser.set_store(revision_store)
    version_browser.set_asset(asset_id)

    before = revision_store.history(asset_id).revisions
    assert len(before) == 2
    assert before[0].content_hash != before[1].content_hash
    assert version_browser._tree.topLevelItemCount() == 2

    # Restore the earlier (v1) revision.
    version_browser._tree.setCurrentItem(version_browser._tree.topLevelItem(0))
    with qtbot.waitSignal(version_browser.revisionRestored, timeout=1000):
        version_browser._on_restore()

    current_hash = session.catalog().get(asset_id).content_hash
    restored_bytes = cas.get(current_hash)
    assert restored_bytes == v1_bytes

    # Both earlier revisions remain in the history (append-only restore).
    after = revision_store.history(asset_id).revisions
    assert len(after) == 3
    assert [r.content_hash for r in after[:2]] == [r.content_hash for r in before]


def test_sc_p11_ui_020_2_unchanged_content_appends_nothing(tmp_path, qtbot):
    """Registering identical content again appends no new revision (dedup no-op)."""
    root = tmp_path / "dedup_root"
    session, _cas, revision_store = _bound_session(root)

    document = _make_document()
    with qtbot.waitSignal(session.catalogChanged, timeout=1000):
        _outcome, descriptor = _register(
            session, document, name="Hero", kind=AssetKind.SPRITE, tags=()
        )
    asset_id = descriptor.asset_id
    before = revision_store.history(asset_id).revisions
    assert len(before) == 1

    existing = session.catalog().get(asset_id)
    outcome2, descriptor2 = _reregister(
        session, existing, document, name="Hero", kind=AssetKind.SPRITE, tags=()
    )
    assert outcome2.revision_recorded is False
    assert descriptor2 is existing  # _reregister returns the unchanged descriptor

    after = revision_store.history(asset_id).revisions
    assert len(after) == len(before) == 1
    assert after[0].content_hash == before[0].content_hash
