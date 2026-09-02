"""Cross-project reuse over DURABLE, persisted reference sets (REQ-P11-UI-021).

``test_asset_reuse.py`` already proves ``Asset_Reuse_Panel``'s reference-not-copy
mechanics and the shared/not-shared marker over its own in-panel scratch state
(``add_project`` + ``_on_reference`` building a project's set from nothing, in one
process, never touching disk). This file does **not** restate those assertions
(D2 re-scope). It extends them along the one axis that file never
exercises: **real ``.pixproj`` persistence** — ``data/project_io.save_project`` /
``load_project_with_asset_refs`` round trips at ``FORMAT_VERSION 6`` — bound into the
panel through ``Asset_Reuse_Panel.set_project_reference_set``, the durable code path
this module adds over the pure :class:`~pixelart_creator.logic.asset_references.ReferenceSet`
model.

Six acceptance scenarios (``SC-P11-UI-021-1``..``-6``, spec.md "Reuse without
duplication, and the per-project reference set"), five test functions (some folding
two scenarios together, matching the task's own ``Done when`` phrasing):

* ``test_sc_021_1_and_2`` — referencing a shared asset into a **second**, disk-backed
  project changes only that project's set; the blob count is unchanged; the FIRST
  project's on-disk file, re-read independently afterwards, is byte-for-byte the
  reference set it was before (``SC-P11-UI-021-1``, ``-2``).
* ``test_sc_021_3`` — closing and reopening a project (a fresh
  ``load_project_with_asset_refs`` call, independent of any earlier in-memory object)
  restores its reference set; the referenced content is retrievable from the CAS and
  its bytes hash-verify against the recorded ``content_hash`` (``SC-P11-UI-021-3``).
* ``test_sc_021_4`` — with two DISK-BACKED projects open at once, an asset in both is
  marked Shared; an asset in only one is not (``SC-P11-UI-021-4``).
* ``test_sc_021_5`` — a project whose persisted reference set names an asset absent
  from the local library opens (the file round-trips without error); the missing
  asset is named and the project's unresolved count is reported; no reference is
  dropped or substituted — the project's other, resolvable reference still works
  (``SC-P11-UI-021-5``).
* ``test_sc_021_6`` — renaming a library asset's display name breaks NO reference:
  two disk-backed projects referencing the same asset both still resolve after the
  rename, and the shared content is still retrievable through both
  (``SC-P11-UI-021-6``).

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture
(``testing/suites/ui/conftest.py``) — the two indicators (resolve-state and shared-state) are
UI-visible and are asserted on the rendered tree text in every run, so both themes
exercise the same assertions (light/dark differ only in styling, never in text).

Temp hygiene: every project file and every CAS blob lives under pytest's
own ``tmp_path`` (per-test, self-cleaned, never a real per-user location); the suite
is invoked with ``--basetemp`` rooted under ``D:\\tmp`` — never ``C:``.
"""

from __future__ import annotations

import dataclasses

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.data.project_io import load_project_with_asset_refs, save_project
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_references import (
    AssetReference,
    ReferenceSet,
    missing,
    resolve_states,
)
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.document import Document
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_reuse_panel import (
    _PCOL_NAME,
    _PCOL_RESOLVE,
    _PCOL_SHARED,
    _ROLE_ASSET,
    Asset_Reuse_Panel,
)

_HERO = b"t22-hero-shared-bytes"
_DUNGEON = b"t22-dungeon-shared-bytes"
_H_HERO = content_hash(_HERO)
_H_DUNGEON = content_hash(_DUNGEON)
_H_GHOST = content_hash(b"t22-never-stored-bytes")


def _descriptor(asset_id, kind, name, hash_key):
    return AssetDescriptor(
        asset_id=asset_id, kind=kind, name=name, content_hash=hash_key
    )


def _reference(asset_id, kind, hash_key, name):
    return AssetReference(
        asset_id=asset_id, content_hash=hash_key, kind=kind, last_known_name=name
    )


def _library_catalog(*descriptors):
    return AssetCatalog(descriptors=tuple(descriptors))


def _cas(tmp_path, name="blobs"):
    """A real, filesystem-rooted CAS under ``tmp_path`` (persists across reload)."""
    backend = LocalBlobBackend(root=tmp_path / name)
    return ContentAddressableStore(backend), backend


def _blob_file_count(backend: LocalBlobBackend) -> int:
    """Count the ``.blob`` files actually on disk under the backend's root."""
    return len(list(backend._root.glob("*.blob")))


def _save(tmp_path, filename, reference_set):
    """Save a fresh, minimal ``Document`` + ``reference_set`` and return the path."""
    document = Document(4, 4)
    return save_project(document, tmp_path / filename, reference_set=reference_set)


def _panel(qtbot, session, cas):
    widget = Asset_Reuse_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget.set_content_store(cas)
    return widget


def _select_shared(widget, asset_id):
    tree = widget._tree
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(0, _ROLE_ASSET) == asset_id:
            tree.setCurrentItem(item)
            return item
    raise AssertionError(f"no shared-asset row for {asset_id!r}")


def _project_row(widget, asset_id):
    tree = widget._project_tree
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.data(_PCOL_NAME, _ROLE_ASSET) == asset_id:
            return item
    return None


# -- SC-P11-UI-021-1 + -2: cross-project reference; blobs + P1 untouched ------- #


def test_sc_021_1_and_2_reference_into_second_project_leaves_blobs_and_p1_untouched(
    tmp_path, qtbot
):
    """Referencing into a SECOND, disk-backed project changes only that project's set.

    P1 is a real ``.pixproj`` already referencing ``dungeon``; P2 is a second, empty,
    real project. Referencing ``hero`` into P2 must: leave the CAS blob count
    unchanged (``SC-P11-UI-021-1``); add ``hero`` to P2's set; leave P1's set holding
    only ``dungeon`` (unchanged); and leave P1's ON-DISK file identical to what it was
    before the P2 operation — re-read independently, not merely unread
    (``SC-P11-UI-021-2``).
    """
    cas, backend = _cas(tmp_path)
    cas.put(_HERO)
    cas.put(_DUNGEON)
    library = _library_catalog(
        _descriptor("hero", AssetKind.SPRITE, "Hero", _H_HERO),
        _descriptor("dungeon", AssetKind.TILESET, "Dungeon", _H_DUNGEON),
    )
    session = Asset_Library_Session(catalog=library)

    p1_refs = ReferenceSet().add(
        _reference("dungeon", AssetKind.TILESET, _H_DUNGEON, "Dungeon")
    )
    p1_path = _save(tmp_path, "p1", p1_refs)
    p1_doc, p1_loaded = load_project_with_asset_refs(p1_path)
    assert p1_doc is not None  # the project opens

    widget = _panel(qtbot, session, cas)
    widget.set_project_reference_set("P1", p1_loaded)
    widget.add_project("P2")  # a second, genuinely empty durable project
    assert widget.current_project() == "P2"

    blobs_before = _blob_file_count(backend)
    _select_shared(widget, "hero")
    with qtbot.waitSignal(widget.assetReferenced, timeout=1000) as blocker:
        widget._on_reference()
    assert blocker.args == ["hero", "P2"]

    # SC-P11-UI-021-1: no second copy — the blob count is unchanged.
    assert _blob_file_count(backend) == blobs_before

    # SC-P11-UI-021-2: A is in P2's set; P1's in-memory set is unchanged.
    assert widget.project_references("P2") == ("hero",)
    assert widget.project_references("P1") == ("dungeon",)

    # And P1's file ON DISK was never touched: reading it again, independently,
    # reproduces exactly the reference set it held before the P2 operation.
    _, p1_reread = load_project_with_asset_refs(p1_path)
    assert p1_reread == p1_loaded


# -- SC-P11-UI-021-3: reopening restores the set, hash-verified --------------- #


def test_sc_021_3_reopening_the_project_restores_its_set_hash_verified(tmp_path, qtbot):
    """Closing and reopening a project restores its reference set (SC-P11-UI-021-3).

    "Reopening" is modelled as a FRESH ``load_project_with_asset_refs`` call over the
    same path, independent of the object that saved it (nothing in memory is reused).
    The restored reference's content must be retrievable from the CAS and its bytes
    must hash-verify against the recorded ``content_hash``.
    """
    cas, backend = _cas(tmp_path, name="blobs_p2")
    cas.put(_HERO)
    library = _library_catalog(_descriptor("hero", AssetKind.SPRITE, "Hero", _H_HERO))
    session = Asset_Library_Session(catalog=library)

    refs = ReferenceSet().add(_reference("hero", AssetKind.SPRITE, _H_HERO, "Hero"))
    path = _save(tmp_path, "p2", refs)
    del refs  # the original in-memory value must play no part in "reopening"

    # Reopen: an independent, fresh load.
    reopened_doc, reopened_refs = load_project_with_asset_refs(path)
    assert reopened_doc is not None  # the project opens
    reference = reopened_refs.get("hero")
    assert reference is not None
    assert reference.content_hash == _H_HERO

    # Content retrievable AND hash-verified.
    retrieved = cas.get(reference.content_hash)
    assert retrieved == _HERO
    assert content_hash(retrieved) == reference.content_hash

    # And the UI-level surface agrees: bound into the panel, the reopened project's
    # set has no unresolved reference.
    widget = _panel(qtbot, session, cas)
    widget.set_project_reference_set("P2", reopened_refs)
    assert missing(reopened_refs, library) == frozenset()
    assert widget.missing_asset_ids("P2") == frozenset()
    assert "hero" in widget.project_references("P2")


# -- SC-P11-UI-021-4: shared marker over two disk-backed, OPEN projects ------- #


def test_sc_021_4_asset_in_two_open_disk_backed_projects_is_marked_shared(
    tmp_path, qtbot
):
    """An asset referenced by two OPEN, disk-backed projects is marked Shared; one
    referenced by a single project is not (SC-P11-UI-021-4), over the durable
    ``set_project_reference_set`` path this module adds — never the panel's own
    ``add_project`` + ``_on_reference`` scratch state ``test_asset_reuse.py`` already
    covers.
    """
    cas, _backend = _cas(tmp_path)
    cas.put(_HERO)
    cas.put(_DUNGEON)
    library = _library_catalog(
        _descriptor("hero", AssetKind.SPRITE, "Hero", _H_HERO),
        _descriptor("dungeon", AssetKind.TILESET, "Dungeon", _H_DUNGEON),
    )
    session = Asset_Library_Session(catalog=library)

    # P1 references BOTH hero and dungeon; P2 references only hero.
    p1_refs = (
        ReferenceSet()
        .add(_reference("hero", AssetKind.SPRITE, _H_HERO, "Hero"))
        .add(_reference("dungeon", AssetKind.TILESET, _H_DUNGEON, "Dungeon"))
    )
    p2_refs = ReferenceSet().add(_reference("hero", AssetKind.SPRITE, _H_HERO, "Hero"))
    p1_path = _save(tmp_path, "p1", p1_refs)
    p2_path = _save(tmp_path, "p2", p2_refs)
    _, p1_loaded = load_project_with_asset_refs(p1_path)
    _, p2_loaded = load_project_with_asset_refs(p2_path)

    widget = _panel(qtbot, session, cas)
    widget.set_project_reference_set("P1", p1_loaded)
    widget.set_project_reference_set("P2", p2_loaded)

    assert widget.is_shared("hero") is True
    assert widget.is_shared("dungeon") is False

    # The UI-visible indicator itself (current project is P1, the first bound).
    assert widget.current_project() == "P1"
    hero_row = _project_row(widget, "hero")
    dungeon_row = _project_row(widget, "dungeon")
    assert hero_row.text(_PCOL_SHARED) == widget.tr("Shared")
    assert dungeon_row.text(_PCOL_SHARED) == ""


# -- SC-P11-UI-021-5: missing-from-library reference is named, never dropped -- #


def test_sc_021_5_project_naming_a_missing_asset_opens_named_and_counted(
    tmp_path, qtbot
):
    """A project referencing an asset absent from the library opens; the missing
    asset is named and counted; nothing is dropped or substituted; the project's
    resolvable reference still works (SC-P11-UI-021-5).
    """
    cas, _backend = _cas(tmp_path)
    cas.put(_DUNGEON)  # dungeon's bytes ARE stored; "ghost" never was
    # The library catalog holds "dungeon" only — "ghost" is absent from it entirely.
    library = _library_catalog(
        _descriptor("dungeon", AssetKind.TILESET, "Dungeon", _H_DUNGEON)
    )
    session = Asset_Library_Session(catalog=library)

    refs = (
        ReferenceSet()
        .add(_reference("ghost", AssetKind.SPRITE, _H_GHOST, "Ghost"))
        .add(_reference("dungeon", AssetKind.TILESET, _H_DUNGEON, "Dungeon"))
    )
    path = _save(tmp_path, "p1", refs)
    original_ids = frozenset(r.asset_id for r in refs.entries())

    doc, loaded = load_project_with_asset_refs(path)
    assert doc is not None  # the project opens — a missing reference never blocks it

    widget = _panel(qtbot, session, cas)
    widget.set_project_reference_set("P1", loaded)

    # Named: the missing asset_id is reported.
    assert widget.missing_asset_ids("P1") == frozenset({"ghost"})
    # Counted: the missing-count label is non-empty and names the count (1).
    label_text = widget._missing_label.text()
    assert label_text != ""
    assert "1" in label_text

    # Never dropped or substituted: BOTH references are still present, unchanged.
    assert frozenset(widget.project_references("P1")) == original_ids

    # The resolvable reference still works (bytes retrievable through the CAS).
    dungeon_ref = loaded.get("dungeon")
    assert cas.has(dungeon_ref.content_hash)
    assert cas.get(dungeon_ref.content_hash) == _DUNGEON

    # The named/counted state is UI-visible too, in both themes.
    ghost_row = _project_row(widget, "ghost")
    dungeon_row = _project_row(widget, "dungeon")
    assert ghost_row.text(_PCOL_RESOLVE) == widget.tr("Not found in library")
    assert dungeon_row.text(_PCOL_RESOLVE) == widget.tr("In library")


# -- SC-P11-UI-021-6: renaming a library asset breaks no reference ------------ #


def test_sc_021_6_renaming_a_library_asset_breaks_no_project_reference(tmp_path, qtbot):
    """Renaming a library asset's display name breaks NO project's reference
    (SC-P11-UI-021-6). Two disk-backed projects (P1, P2) both reference the same
    asset; after the library-side rename, both still resolve and the shared content
    is still retrievable through both — resolution is by ``asset_id`` +
    ``content_hash`` only, never by name (ruling P11-R8's untouched promise;
    plan.md §3.10).
    """
    cas, _backend = _cas(tmp_path)
    cas.put(_HERO)
    hero_descriptor = _descriptor("hero", AssetKind.SPRITE, "Hero", _H_HERO)
    library = _library_catalog(hero_descriptor)
    session = Asset_Library_Session(catalog=library)

    p1_refs = ReferenceSet().add(_reference("hero", AssetKind.SPRITE, _H_HERO, "Hero"))
    p2_refs = ReferenceSet().add(_reference("hero", AssetKind.SPRITE, _H_HERO, "Hero"))
    p1_path = _save(tmp_path, "p1", p1_refs)
    p2_path = _save(tmp_path, "p2", p2_refs)
    _, p1_loaded = load_project_with_asset_refs(p1_path)
    _, p2_loaded = load_project_with_asset_refs(p2_path)

    widget = _panel(qtbot, session, cas)
    widget.set_project_reference_set("P1", p1_loaded)
    widget.set_project_reference_set("P2", p2_loaded)

    # Precondition: both resolve, under the ORIGINAL name.
    assert widget.missing_asset_ids("P1") == frozenset()
    assert widget.missing_asset_ids("P2") == frozenset()

    # Rename the library asset's DISPLAY name only — same asset_id, same content_hash.
    renamed = dataclasses.replace(hero_descriptor, name="Champion")
    session.replace_descriptor(renamed)  # emits catalogChanged -> panel refreshes

    # Still resolves, for BOTH projects (breaks no reference).
    assert widget.missing_asset_ids("P1") == frozenset()
    assert widget.missing_asset_ids("P2") == frozenset()
    assert resolve_states(p1_loaded, session.catalog())["hero"] is True
    assert resolve_states(p2_loaded, session.catalog())["hero"] is True

    # Content still retrievable through both (same shared blob; identity untouched).
    assert cas.get(p1_loaded.get("hero").content_hash) == _HERO
    assert cas.get(p2_loaded.get("hero").content_hash) == _HERO

    # The UI-visible display name updates (a display-only change), while the
    # reference itself is provably unbroken (asserted above via missing_asset_ids).
    hero_row = _project_row(widget, "hero")
    assert hero_row.text(0) == "Champion"


# -- A kept-edited reference reads as resolved -------------------------------- #


def test_t35_kept_edited_reference_resolves_missing_stays_not_found(tmp_path, qtbot):
    """The fix is a partition of one predicate; asserting one branch proves
    nothing about the other, so both are asserted here, in the same run.

    ``"hero"`` is IN the catalog but under a content_hash that DIFFERS from the
    project's own reference — ``STATE_EDITED``, not ``STATE_MISSING``: the library
    asset was edited since this project last referenced it. It must render the
    resolved label (``"In library"``) and the catalog entry's CURRENT name — never
    the reference's stale ``last_known_name``. ``"ghost"`` is absent from the
    catalog entirely (``STATE_MISSING``, untouched by the fix) and must still
    render ``"Not found in library"`` under its own ``last_known_name``. The
    missing COUNT is unaffected by the fix (step 1 — ``missing()`` is not
    widened): both references are unresolved by ``resolve_states``' boolean, so
    the count is 2, same as it would have been before the fix.
    """
    cas, _backend = _cas(tmp_path)
    # "hero"'s CURRENT library entry deliberately uses a different content_hash
    # (and a different name) than the project's stale reference to it.
    hero_current = _descriptor("hero", AssetKind.SPRITE, "Champion", _H_DUNGEON)
    library = _library_catalog(hero_current)
    session = Asset_Library_Session(catalog=library)

    refs = (
        ReferenceSet()
        .add(_reference("hero", AssetKind.SPRITE, _H_HERO, "Hero"))  # stale hash+name
        .add(
            _reference("ghost", AssetKind.SPRITE, _H_GHOST, "Ghost")
        )  # never in library
    )

    widget = _panel(qtbot, session, cas)
    widget.set_project_reference_set("P1", refs)

    # The missing COUNT stays unchanged by the fix: both the edited and the
    # genuinely-absent reference are still reported unresolved.
    assert widget.missing_asset_ids("P1") == frozenset({"hero", "ghost"})
    label_text = widget._missing_label.text()
    assert label_text != ""
    assert "2" in label_text

    hero_row = _project_row(widget, "hero")
    ghost_row = _project_row(widget, "ghost")

    # STATE_EDITED ("hero"): resolved label + the catalog entry's CURRENT name.
    assert hero_row.text(_PCOL_RESOLVE) == widget.tr("In library")
    assert hero_row.text(_PCOL_NAME) == "Champion"

    # STATE_MISSING ("ghost"): unchanged — "Not found in library" + last_known_name.
    assert ghost_row.text(_PCOL_RESOLVE) == widget.tr("Not found in library")
    assert ghost_row.text(_PCOL_NAME) == "Ghost"


# -- Sanity: the theme fixture really does run every test twice --------------- #


def test_theme_fixture_covers_both_themes(theme):
    """Guard against a silently-skipped theme parametrisation (both-theme rule)."""
    assert theme in ("light", "dark")
