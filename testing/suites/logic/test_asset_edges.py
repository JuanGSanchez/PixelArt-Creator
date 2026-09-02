"""Unit tests for :mod:`pixelart_creator.logic.asset_edges` (S11, no Qt).

Covers ``REQ-P11-LOGIC-010`` (ruling **P11-R8**, plan §3.10): the pure
hash-matching half (``edges_for``) and the per-kind reference-candidate
rule (``candidates_of``, ruling P11-R6), **re-pointed onto the
content-only ``reference_key`` mechanism** (``reference_bytes`` /
``candidate_keys``).

This module deliberately proves the pipeline **end to end** —
``candidate_keys`` -> ``edges_for`` — for all three named relationships
(tileset->sprite, animation->sprites, tilemap->tileset), because a suite
that only ever asserts an empty edge set is indistinguishable from the
CF-34 defect this slice exists to close (non-vacuity). It also proves the
**rename invariance** ruling P11-R8 exists to buy: a sprite registered
under a **user-produced** layer name (the image-import shape) is still
found as a tileset's dependency — and proves that invariance is a genuine
regression test by reproducing the pre-fix (content-hash-matching)
semantics through a controlled, fully-reverted defect injection
(``monkeypatch``), never by mutating shipped code on disk.

Importing ``data.asset_ingress.canonical_bytes`` here (a ``data/`` module,
inside ``testing/suites/logic/``) is deliberate and required to prove the
pipeline end to end: a catalog entry's ``content_hash`` (still recorded on every
produced edge, ruling P11-R8) can only be derived through the *real*
canonical-bytes pairing a production registration would use, not a
hand-rolled stand-in that could silently drift from it. No Qt import
anywhere in this file.
"""

from __future__ import annotations

from typing import Tuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.data.asset_ingress import canonical_bytes
from pixelart_creator.logic.animation import FrameTag
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_edges import (
    AssetEdgesError,
    candidate_keys,
    candidates_of,
    edges_for,
    reference_bytes,
)
from pixelart_creator.logic.asset_extract import descriptor_for
from pixelart_creator.logic.blend import BlendMode
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.dependency_graph import DependencyEdge
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import flatten_frame
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import Tilemap
from pixelart_creator.logic.tileset import Tileset

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)

#: The only kinds ``reference_bytes`` is defined for — mirrors
#: ``data/asset_ingress._REFERENCE_TARGET_KINDS`` (ruling P11-R8).
_REFERENCE_TARGET_KINDS = (AssetKind.SPRITE, AssetKind.TILESET)


def _reference_key_for(document: Document, kind: AssetKind) -> str:
    """Return ``document``'s ``reference_key`` for ``kind``, degrading to ``""``.

    Mirrors exactly what ``data/asset_ingress._reference_key_for`` computes
    — expressed here over ``logic/`` names only (no ``data/`` import
    needed for this half), so a test built on this helper is proving the
    real per-kind rule, not a stand-in for it.
    """
    if kind not in _REFERENCE_TARGET_KINDS:
        return ""
    try:
        return content_hash(reference_bytes(document, kind))
    except AssetEdgesError:
        return ""


def _register(
    document: Document,
    *,
    asset_id: str,
    name: str,
    kind: AssetKind,
    catalog: AssetCatalog,
) -> Tuple[AssetDescriptor, AssetCatalog]:
    """Register ``document`` into ``catalog`` through the real canonical pairing.

    Mirrors exactly what ``data/asset_ingress.register`` hashes, keys and
    stores (``canonical_bytes`` -> ``reference_key`` -> ``descriptor_for``),
    so a test built on this helper is proving the real pipeline, not
    a stand-in for it.
    """
    blob = canonical_bytes(document)
    reference_key = _reference_key_for(document, kind)
    descriptor = descriptor_for(
        blob, asset_id=asset_id, name=name, kind=kind, reference_key=reference_key
    )
    return descriptor, catalog.add(descriptor)


def _derive(
    document: Document,
    kind: AssetKind,
    descriptor: AssetDescriptor,
    catalog: AssetCatalog,
) -> Tuple[DependencyEdge, ...]:
    """Run the exact recipe the production ``_derive_and_emit_edges`` call performs.

    ``candidate_keys`` is the direct replacement for the pre-fix
    ``tuple(canonical_bytes(d) for d in candidates_of(...))`` recipe — see
    :func:`_derive_pre_fix` below for that superseded recipe, kept only for
    the regression proof.
    """
    content = candidate_keys(document, kind)
    return edges_for(descriptor, content, catalog)


def _derive_pre_fix(
    document: Document,
    kind: AssetKind,
    descriptor: AssetDescriptor,
    catalog: AssetCatalog,
) -> Tuple[DependencyEdge, ...]:
    """Reproduce the **pre-fix** derivation recipe exactly (regression proof only).

    Ruling P11-R6's original recipe: whole-project canonical bytes per
    candidate, matched against ``entry.content_hash``. Used **only** by
    ``test_rename_invariance_regression_proof`` below, together with a
    monkeypatch of ``AssetDescriptor.reference_key`` (see that test), to
    reproduce the exact defect P11-R8 closes through the real ``edges_for``
    code path — never by hand-simulating a result.
    """
    content = tuple(canonical_bytes(d) for d in candidates_of(document, kind))
    return edges_for(descriptor, content, catalog)


# --------------------------------------------------------------------------- #
# Non-vacuity: one positive derived edge per relationship, end to end          #
# --------------------------------------------------------------------------- #


def test_tileset_to_sprite_positive_edge_end_to_end() -> None:
    """A tileset's source-image sprite, once registered, is a found dependency."""
    sprite_buf = PixelBuffer(8, 8, ColorMode.RGBA, fill=RED)
    sprite_doc = Document.from_buffer(sprite_buf)  # default name "Imported"
    catalog = AssetCatalog()
    sprite_descriptor, catalog = _register(
        sprite_doc,
        asset_id="sprite-1",
        name="Source",
        kind=AssetKind.SPRITE,
        catalog=catalog,
    )

    tileset = Tileset(sprite_buf, tile_width=4, tile_height=4, name="TS")
    tileset_doc = Document(sprite_buf.width, sprite_buf.height, mode=sprite_buf.mode)
    tileset_doc.tilesets.append(tileset)
    tileset_descriptor, catalog = _register(
        tileset_doc,
        asset_id="tileset-1",
        name="Tiles",
        kind=AssetKind.TILESET,
        catalog=catalog,
    )

    edges = _derive(tileset_doc, AssetKind.TILESET, tileset_descriptor, catalog)

    assert edges == (
        DependencyEdge(
            source_id="tileset-1",
            target_id="sprite-1",
            pinned_hash=sprite_descriptor.content_hash,
        ),
    )


def test_animation_to_sprites_positive_edge_end_to_end() -> None:
    """A named animation's flattened frame, once registered as a sprite, is found."""
    anim_doc = Document(6, 6, mode=ColorMode.RGBA)
    anim_doc.frame_tags.append(FrameTag("Walk", 0, 0))
    composite = flatten_frame(anim_doc.frames[0], anim_doc.width, anim_doc.height)
    sprite_doc = Document.from_buffer(composite)  # matches candidates_of's own wrapping

    catalog = AssetCatalog()
    sprite_descriptor, catalog = _register(
        sprite_doc,
        asset_id="sprite-2",
        name="Frame0",
        kind=AssetKind.SPRITE,
        catalog=catalog,
    )
    anim_descriptor, catalog = _register(
        anim_doc,
        asset_id="anim-1",
        name="Walk",
        kind=AssetKind.ANIMATION,
        catalog=catalog,
    )

    edges = _derive(anim_doc, AssetKind.ANIMATION, anim_descriptor, catalog)

    assert edges == (
        DependencyEdge(
            source_id="anim-1",
            target_id="sprite-2",
            pinned_hash=sprite_descriptor.content_hash,
        ),
    )


def test_tilemap_to_tileset_positive_edge_end_to_end() -> None:
    """A tilemap's attached tileset, once registered the same shape, is found.

    Builds the tileset-candidate document via ``candidates_of`` itself (the
    exact shape ``_tileset_document`` produces) rather than reproducing that
    private helper — proving the registered TILESET asset and the derived
    candidate are byte-identical because they come from the same function,
    the honest form of this assertion given ``_tileset_document`` has no
    other shipped precedent (prior investigation §6).
    """
    tile_buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=BLUE)
    tileset = Tileset(tile_buf, tile_width=4, tile_height=4, name="MapTiles")
    tilemap = Tilemap(name="Level1", tile_width=4, tile_height=4)
    tilemap.tilesets.append(tileset)

    tilemap_doc = Document(16, 16, mode=ColorMode.RGBA)
    tilemap_doc.tilemaps.append(tilemap)
    # Required precondition (prior investigation §4, second finding): project_io.serialize
    # raises unless a tilemap's referenced tileset is ALSO in document.tilesets.
    tilemap_doc.tilesets.append(tileset)

    catalog = AssetCatalog()
    candidates = candidates_of(tilemap_doc, AssetKind.TILEMAP)
    assert len(candidates) == 1
    tileset_descriptor, catalog = _register(
        candidates[0],
        asset_id="tileset-2",
        name="MapTiles",
        kind=AssetKind.TILESET,
        catalog=catalog,
    )
    tilemap_descriptor, catalog = _register(
        tilemap_doc,
        asset_id="tilemap-1",
        name="Level1",
        kind=AssetKind.TILEMAP,
        catalog=catalog,
    )

    edges = _derive(tilemap_doc, AssetKind.TILEMAP, tilemap_descriptor, catalog)

    assert edges == (
        DependencyEdge(
            source_id="tilemap-1",
            target_id="tileset-2",
            pinned_hash=tileset_descriptor.content_hash,
        ),
    )


# --------------------------------------------------------------------------- #
# Rename invariance — the Item-2 fix, proven and pinned as a regression       #
# --------------------------------------------------------------------------- #


def test_rename_invariance_image_import_shape_edge_still_found() -> None:
    """The image-import shape is a fixture, not an afterthought.

    A sprite registered from a document whose layer carries a
    **user-produced** name — ``Document.from_buffer(buffer, name=Path(path).stem)``,
    ``ui/main_window.py:2007`` — is still found as a tileset's dependency.
    This is exactly the shape a prior live smoke run showed derived **zero**
    edges before this ruling (plan §3.10's measured table, row 1); this test
    pins the fixed outcome as the standing behaviour.
    """
    sprite_buf = PixelBuffer(8, 8, ColorMode.RGBA, fill=RED)
    sprite_doc = Document.from_buffer(sprite_buf, name="hero")  # image-import shape
    catalog = AssetCatalog()
    sprite_descriptor, catalog = _register(
        sprite_doc,
        asset_id="sprite-rename",
        name="Source",
        kind=AssetKind.SPRITE,
        catalog=catalog,
    )

    tileset = Tileset(sprite_buf, tile_width=4, tile_height=4, name="TS")
    tileset_doc = Document(sprite_buf.width, sprite_buf.height, mode=sprite_buf.mode)
    tileset_doc.tilesets.append(tileset)
    tileset_descriptor, catalog = _register(
        tileset_doc,
        asset_id="tileset-rename",
        name="Tiles",
        kind=AssetKind.TILESET,
        catalog=catalog,
    )

    edges = _derive(tileset_doc, AssetKind.TILESET, tileset_descriptor, catalog)

    assert edges == (
        DependencyEdge(
            source_id="tileset-rename",
            target_id="sprite-rename",
            pinned_hash=sprite_descriptor.content_hash,
        ),
    )


def test_rename_invariance_new_document_background_shape_edge_still_found() -> None:
    """The ``Document()`` shape (seeded layer ``"Background"``,
    ``logic/document.py:461``, corrected 2026-08-21) is a fixture, not an
    afterthought either — plan §3.10's measured table, row 2, also derived
    **zero** edges before this ruling.
    """
    sprite_buf = PixelBuffer(6, 6, ColorMode.RGBA, fill=RED)
    sprite_doc = Document(sprite_buf.width, sprite_buf.height, mode=sprite_buf.mode)
    assert sprite_doc.frames[0].layers[0].name == "Background"  # the seeded name
    sprite_doc.frames[0].layers[0].buffer = sprite_buf
    catalog = AssetCatalog()
    sprite_descriptor, catalog = _register(
        sprite_doc,
        asset_id="sprite-bg",
        name="Source",
        kind=AssetKind.SPRITE,
        catalog=catalog,
    )

    tileset = Tileset(sprite_buf, tile_width=3, tile_height=3, name="TS")
    tileset_doc = Document(sprite_buf.width, sprite_buf.height, mode=sprite_buf.mode)
    tileset_doc.tilesets.append(tileset)
    tileset_descriptor, catalog = _register(
        tileset_doc,
        asset_id="tileset-bg",
        name="Tiles",
        kind=AssetKind.TILESET,
        catalog=catalog,
    )

    edges = _derive(tileset_doc, AssetKind.TILESET, tileset_descriptor, catalog)

    assert edges == (
        DependencyEdge(
            source_id="tileset-bg",
            target_id="sprite-bg",
            pinned_hash=sprite_descriptor.content_hash,
        ),
    )


def test_rename_invariance_regression_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proves the invariance test above is a
    REGRESSION test, not a tautology, by showing the *same* scenario fails
    under the pre-fix matching semantics and passes under the shipped ones.

    **Method (disclosed per binding call 2).** The whole
    phase-11 stack is uncommitted (no pre-fix commit exists to check out),
    so the pre-fix code path is reproduced by a **controlled, fully-reverted
    defect injection**: ``AssetDescriptor.reference_key`` is monkeypatched to
    a ``property`` that reads ``content_hash`` instead — the exact matching
    field the pre-fix ``edges_for`` used (``entry.content_hash``) — for the
    duration of this test only (``monkeypatch`` reverts it unconditionally at
    teardown, pass or fail). This exercises the real, shipped ``edges_for``
    code unmodified; only the *field* it reads through the patched
    descriptor is swapped, and only for this test's process. No product file
    on disk is touched.

    ``_derive_pre_fix`` additionally reproduces the pre-fix **candidate**
    recipe (whole-project ``canonical_bytes`` per candidate, ruling P11-R6),
    since that is the recipe that was paired with content-hash matching
    before P11-R8.

    Both outcomes are asserted in the same test, in this order:
    1. The shipped code (unpatched) finds the edge — sanity, real code.
    2. The patched, pre-fix semantics find **no** edge over the identical
       scenario — the regression this test exists to catch, reproduced live.
    """
    sprite_buf = PixelBuffer(8, 8, ColorMode.RGBA, fill=RED)
    sprite_doc = Document.from_buffer(sprite_buf, name="hero")  # image-import shape
    catalog = AssetCatalog()
    sprite_descriptor, catalog = _register(
        sprite_doc,
        asset_id="sprite-proof",
        name="Source",
        kind=AssetKind.SPRITE,
        catalog=catalog,
    )

    tileset = Tileset(sprite_buf, tile_width=4, tile_height=4, name="TS")
    tileset_doc = Document(sprite_buf.width, sprite_buf.height, mode=sprite_buf.mode)
    tileset_doc.tilesets.append(tileset)
    tileset_descriptor, catalog = _register(
        tileset_doc,
        asset_id="tileset-proof",
        name="Tiles",
        kind=AssetKind.TILESET,
        catalog=catalog,
    )

    # 1. Shipped code (unpatched): the edge IS found.
    fixed_edges = _derive(tileset_doc, AssetKind.TILESET, tileset_descriptor, catalog)
    assert fixed_edges == (
        DependencyEdge(
            source_id="tileset-proof",
            target_id="sprite-proof",
            pinned_hash=sprite_descriptor.content_hash,
        ),
    )

    # 2. Pre-fix semantics, injected: the SAME scenario finds NO edge.
    monkeypatch.setattr(
        AssetDescriptor,
        "reference_key",
        property(lambda self: self.content_hash),
    )
    pre_fix_edges = _derive_pre_fix(
        tileset_doc, AssetKind.TILESET, tileset_descriptor, catalog
    )
    assert pre_fix_edges == ()  # the defect this ruling closes, reproduced live


# --------------------------------------------------------------------------- #
# edges_for — hash matching over already-computed reference-candidate keys    #
# --------------------------------------------------------------------------- #


def _descriptor(
    asset_id: str,
    content_hash_: str,
    kind: AssetKind = AssetKind.SPRITE,
    reference_key: str = None,  # type: ignore[assignment]
) -> AssetDescriptor:
    """Build a bare catalog-entry descriptor for ``edges_for``'s own unit tests.

    ``reference_key`` defaults to ``content_hash_`` — most of this section's
    tests exercise ``edges_for``'s matching/dedup/determinism behaviour in
    the abstract (not the full registration pipeline), where the two values
    coinciding is the simplest faithful stand-in for "this entry's reference
    key is known and equals the candidate's digest". Tests that need the two
    fields to genuinely differ pass ``reference_key``
    explicitly.
    """
    if reference_key is None:
        reference_key = content_hash_
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name="X",
        content_hash=content_hash_,
        reference_key=reference_key,
    )


def test_empty_content_yields_empty_edge_set_no_error() -> None:
    descriptor = _descriptor("src-1", "a" * 64)
    assert edges_for(descriptor, [], AssetCatalog()) == ()


def test_unmatched_candidate_yields_empty_edge_set_no_error() -> None:
    descriptor = _descriptor("src-1", "a" * 64)
    catalog = AssetCatalog(descriptors=(_descriptor("other", "b" * 64),))
    assert edges_for(descriptor, [b"never registered"], catalog) == ()


def test_matched_candidate_yields_one_edge_pinned_to_target_hash() -> None:
    blob = b"the referenced content"
    digest = content_hash(blob)
    target = _descriptor("target-1", digest)
    descriptor = _descriptor("src-1", "a" * 64)
    catalog = AssetCatalog(descriptors=(target,))

    edges = edges_for(descriptor, [blob], catalog)

    assert edges == (
        DependencyEdge(source_id="src-1", target_id="target-1", pinned_hash=digest),
    )


def test_duplicate_candidates_dedup_to_one_edge() -> None:
    blob = b"the referenced content, twice"
    digest = content_hash(blob)
    target = _descriptor("target-1", digest)
    descriptor = _descriptor("src-1", "a" * 64)
    catalog = AssetCatalog(descriptors=(target,))

    edges = edges_for(descriptor, [blob, blob], catalog)

    assert edges == (
        DependencyEdge(source_id="src-1", target_id="target-1", pinned_hash=digest),
    )


def test_self_reference_candidate_is_skipped_not_raised() -> None:
    blob = b"content that happens to be its own"
    digest = content_hash(blob)
    # The referencing descriptor is ALREADY in the catalog under its own id,
    # and its own reference key matches the candidate blob.
    self_entry = _descriptor("src-1", digest)
    catalog = AssetCatalog(descriptors=(self_entry,))

    edges = edges_for(self_entry, [blob], catalog)

    assert edges == ()  # a self-edge would be a 1-cycle; skipped, not raised


def test_malformed_candidate_raises_asset_edges_error() -> None:
    descriptor = _descriptor("src-1", "a" * 64)
    with pytest.raises(AssetEdgesError):
        edges_for(descriptor, ["not bytes"], AssetCatalog())  # type: ignore[list-item]


def test_edges_for_is_deterministic_across_repeat_calls() -> None:
    blob = b"stable content"
    digest = content_hash(blob)
    target = _descriptor("target-1", digest)
    descriptor = _descriptor("src-1", "a" * 64)
    catalog = AssetCatalog(descriptors=(target,))

    first = edges_for(descriptor, [blob], catalog)
    second = edges_for(descriptor, [blob], catalog)

    assert first == second


# --------------------------------------------------------------------------- #
# edges_for — reference_key decides the match, but the                      #
#             edge stays pinned to content_hash (the ruling narrows what is  #
#             matched, never what is recorded)                               #
# --------------------------------------------------------------------------- #


def test_edges_for_skips_entry_whose_reference_key_is_empty() -> None:
    """An entry with a matching ``content_hash`` but an *unknown* (``""``)
    ``reference_key`` must never match — proves the matched field is
    ``reference_key``, not ``content_hash``."""
    blob = b"content whose digest would match content_hash, not reference_key"
    digest = content_hash(blob)
    target = AssetDescriptor(
        asset_id="target-1",
        kind=AssetKind.SPRITE,
        name="X",
        content_hash=digest,  # coincides with the candidate digest
        reference_key="",  # unknown -> must never match (ruling P11-R8)
    )
    descriptor = _descriptor("src-1", "a" * 64)
    catalog = AssetCatalog(descriptors=(target,))

    assert edges_for(descriptor, [blob], catalog) == ()


def test_edges_for_pins_edge_to_content_hash_not_reference_key() -> None:
    """A produced edge's ``pinned_hash`` is the matched entry's
    ``content_hash`` even when it differs from the ``reference_key`` that
    decided the match — the ruling narrows *what is matched*, never *what
    is recorded*."""
    blob = b"reference-candidate bytes"
    ref_digest = content_hash(blob)
    stored_hash = content_hash(b"the stored project bytes, unrelated content")
    target = AssetDescriptor(
        asset_id="target-1",
        kind=AssetKind.SPRITE,
        name="X",
        content_hash=stored_hash,
        reference_key=ref_digest,
    )
    descriptor = _descriptor("src-1", "a" * 64)
    catalog = AssetCatalog(descriptors=(target,))

    edges = edges_for(descriptor, [blob], catalog)

    assert edges == (
        DependencyEdge(
            source_id="src-1", target_id="target-1", pinned_hash=stored_hash
        ),
    )


# --------------------------------------------------------------------------- #
# edges_for — property: any matching candidate produces exactly one edge      #
#             pinned to the matched entry, deterministically (Hypothesis)     #
# --------------------------------------------------------------------------- #


@given(blob=st.binary(min_size=1, max_size=64))
@settings(max_examples=50)
def test_matching_candidate_edge_property(blob: bytes) -> None:
    digest = content_hash(blob)
    target = _descriptor("target-fixed", digest)
    descriptor = _descriptor("src-fixed", "c" * 64)
    catalog = AssetCatalog(descriptors=(target,))

    first = edges_for(descriptor, [blob], catalog)
    second = edges_for(descriptor, [blob], catalog)

    assert first == second  # determinism, for every generated blob
    assert first == (
        DependencyEdge(
            source_id="src-fixed", target_id="target-fixed", pinned_hash=digest
        ),
    )


@given(blobs=st.lists(st.binary(min_size=1, max_size=32), min_size=0, max_size=10))
@settings(max_examples=50)
def test_edges_for_never_errors_on_unregistered_bytes(blobs) -> None:
    """No candidate in an EMPTY catalog can ever match — always empty, never raises."""
    descriptor = _descriptor("src-fixed", "c" * 64)
    result = edges_for(descriptor, blobs, AssetCatalog())
    assert result == ()
    assert edges_for(descriptor, blobs, AssetCatalog()) == result  # determinism


# --------------------------------------------------------------------------- #
# candidates_of — per-kind extraction rule                                    #
# --------------------------------------------------------------------------- #


def test_candidates_of_tileset_returns_source_sprite_document() -> None:
    buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    tileset = Tileset(buf, tile_width=4, tile_height=4)
    doc = Document(4, 4, mode=ColorMode.RGBA)
    doc.tilesets.append(tileset)

    candidates = candidates_of(doc, AssetKind.TILESET)

    assert len(candidates) == 1
    assert candidates[0].frames[0].layers[0].buffer is buf  # type: ignore[union-attr]


def test_candidates_of_animation_returns_flattened_frame_documents() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    doc.frame_tags.append(FrameTag("Idle", 0, 0))

    candidates = candidates_of(doc, AssetKind.ANIMATION)

    assert len(candidates) == 1
    assert isinstance(candidates[0], Document)
    assert (candidates[0].width, candidates[0].height) == (4, 4)


def test_candidates_of_tilemap_returns_tileset_documents() -> None:
    buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=BLUE)
    tileset = Tileset(buf, tile_width=4, tile_height=4)
    tilemap = Tilemap(name="Map", tile_width=4, tile_height=4)
    tilemap.tilesets.append(tileset)
    doc = Document(8, 8, mode=ColorMode.RGBA)
    doc.tilemaps.append(tilemap)

    candidates = candidates_of(doc, AssetKind.TILEMAP)

    assert len(candidates) == 1
    assert candidates[0].tilesets == [tileset]


@pytest.mark.parametrize("kind", [AssetKind.SPRITE, AssetKind.PALETTE])
def test_candidates_of_sprite_and_palette_return_empty_no_error(
    kind: AssetKind,
) -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    assert candidates_of(doc, kind) == ()


def test_candidates_of_tileset_less_document_returns_empty() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    assert candidates_of(doc, AssetKind.TILESET) == ()


def test_candidates_of_tagless_document_returns_empty() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    assert candidates_of(doc, AssetKind.ANIMATION) == ()


def test_candidates_of_tileset_less_tilemap_returns_empty() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    doc.tilemaps.append(Tilemap(name="Empty", tile_width=4, tile_height=4))
    assert candidates_of(doc, AssetKind.TILEMAP) == ()


def test_candidates_of_rejects_non_document() -> None:
    with pytest.raises(AssetEdgesError):
        candidates_of("not a document", AssetKind.SPRITE)  # type: ignore[arg-type]


def test_candidates_of_rejects_non_asset_kind() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    with pytest.raises(AssetEdgesError):
        candidates_of(doc, "tileset")  # type: ignore[arg-type]


def test_candidates_of_multiple_tilesets_preserves_list_order() -> None:
    buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=BLUE)
    tileset_a = Tileset(buf_a, tile_width=4, tile_height=4, name="A")
    tileset_b = Tileset(buf_b, tile_width=4, tile_height=4, name="B")
    doc = Document(4, 4, mode=ColorMode.RGBA)
    doc.tilesets.extend([tileset_a, tileset_b])

    candidates = candidates_of(doc, AssetKind.TILESET)

    assert [
        c.frames[0].layers[0].buffer for c in candidates  # type: ignore[union-attr]
    ] == [buf_a, buf_b]


def test_candidates_of_is_deterministic_across_repeat_calls() -> None:
    buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    tileset = Tileset(buf, tile_width=4, tile_height=4)
    doc = Document(4, 4, mode=ColorMode.RGBA)
    doc.tilesets.append(tileset)

    first = [canonical_bytes(d) for d in candidates_of(doc, AssetKind.TILESET)]
    second = [canonical_bytes(d) for d in candidates_of(doc, AssetKind.TILESET)]

    assert first == second
    assert len(first) == 1


def test_candidates_of_animation_frame_order_ascending() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    # Add two more frames so the tag spans three distinct frames, 0..2.
    doc.frames.append(doc.frames[0].__class__(list(doc.frames[0].layers)))
    doc.frames.append(doc.frames[0].__class__(list(doc.frames[0].layers)))
    doc.frame_tags.append(FrameTag("Run", 0, 2))

    candidates = candidates_of(doc, AssetKind.ANIMATION)

    assert len(candidates) == 3  # one candidate per frame in the tag, in order


# --------------------------------------------------------------------------- #
# reference_bytes / candidate_keys — content-only keying                     #
# (ruling P11-R8)                                                             #
# --------------------------------------------------------------------------- #


def test_reference_bytes_rejects_non_document() -> None:
    with pytest.raises(AssetEdgesError):
        reference_bytes("not a document", AssetKind.SPRITE)  # type: ignore[arg-type]


def test_reference_bytes_rejects_non_asset_kind() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    with pytest.raises(AssetEdgesError):
        reference_bytes(doc, "sprite")  # type: ignore[arg-type]


def test_reference_bytes_rejects_animation_and_tilemap_kinds() -> None:
    """Only SPRITE and TILESET are ever reference *targets* (plan §3.10)."""
    doc = Document(4, 4, mode=ColorMode.RGBA)
    with pytest.raises(AssetEdgesError):
        reference_bytes(doc, AssetKind.ANIMATION)
    with pytest.raises(AssetEdgesError):
        reference_bytes(doc, AssetKind.TILEMAP)
    with pytest.raises(AssetEdgesError):
        reference_bytes(doc, AssetKind.PALETTE)


def test_reference_bytes_tileset_rejects_ambiguous_zero_or_many_tilesets() -> None:
    doc_zero = Document(4, 4, mode=ColorMode.RGBA)
    with pytest.raises(AssetEdgesError):
        reference_bytes(doc_zero, AssetKind.TILESET)

    buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=BLUE)
    doc_many = Document(4, 4, mode=ColorMode.RGBA)
    doc_many.tilesets.extend(
        [
            Tileset(buf_a, tile_width=4, tile_height=4, name="A"),
            Tileset(buf_b, tile_width=4, tile_height=4, name="B"),
        ]
    )
    with pytest.raises(AssetEdgesError):
        reference_bytes(doc_many, AssetKind.TILESET)


def test_reference_bytes_is_deterministic_and_pure() -> None:
    buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc = Document.from_buffer(buf)
    first = reference_bytes(doc, AssetKind.SPRITE)
    second = reference_bytes(doc, AssetKind.SPRITE)
    assert first == second
    assert isinstance(first, bytes)


def test_reference_bytes_sprite_ignores_layer_name() -> None:
    """Layer name never affects the reference bytes."""
    buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_a = Document.from_buffer(buf, name="hero")
    doc_b = Document.from_buffer(buf, name="totally-different-name")
    assert reference_bytes(doc_a, AssetKind.SPRITE) == reference_bytes(
        doc_b, AssetKind.SPRITE
    )


def test_reference_bytes_sprite_ignores_ppi_and_metadata() -> None:
    """Ppi/metadata (document-level, never read by
    ``reference_bytes``) never affect the reference bytes."""
    buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_a = Document.from_buffer(buf_a, name="hero")

    buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_b = Document.from_buffer(buf_b, name="hero", ppi=300.0)
    doc_b.metadata["author"] = "someone"

    assert reference_bytes(doc_a, AssetKind.SPRITE) == reference_bytes(
        doc_b, AssetKind.SPRITE
    )


def test_reference_bytes_sprite_single_layer_ignores_blend_mode() -> None:
    """For the single-layer shape every SPRITE
    registration actually builds (``Document.from_buffer``), the layer's
    blend mode composites against a fully transparent background and so
    never changes the resulting pixels."""
    buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_a = Document.from_buffer(buf_a, name="hero")

    buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_b = Document.from_buffer(buf_b, name="hero")
    doc_b.frames[0].layers[0].blend_mode = BlendMode.MULTIPLY

    assert reference_bytes(doc_a, AssetKind.SPRITE) == reference_bytes(
        doc_b, AssetKind.SPRITE
    )


def test_reference_bytes_sprite_ignores_opacity() -> None:
    """Two documents differing only in layer opacity
    produce identical reference bytes.

    Historical defect: ``reference_bytes``'s SPRITE branch previously
    flattened via ``export.flatten_frame`` -> ``blend.composite_stack``
    over the document's real layer objects, so ``Layer.opacity`` leaked
    into the composited bytes and this test failed (pinned here as
    ``xfail(strict=True)`` pending the fix). The fix routes
    through a presentation-normalised copy of the layer stack
    (``_reference_layers``) that pins opacity/blend-mode/mask to their
    identity values before compositing, so this now passes as a plain
    test — no marker."""
    buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_a = Document.from_buffer(buf_a, name="hero")

    buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_b = Document.from_buffer(buf_b, name="hero")
    doc_b.frames[0].layers[0].opacity = 0.4

    assert reference_bytes(doc_a, AssetKind.SPRITE) == reference_bytes(
        doc_b, AssetKind.SPRITE
    )


def test_reference_bytes_sprite_sensitive_to_one_pixel_difference() -> None:
    """A one-pixel difference DOES change the bytes."""
    buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_a = Document.from_buffer(buf_a)

    buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    buf_b.set_pixel(0, 0, BLUE)
    doc_b = Document.from_buffer(buf_b)

    assert reference_bytes(doc_a, AssetKind.SPRITE) != reference_bytes(
        doc_b, AssetKind.SPRITE
    )


def test_reference_bytes_sprite_sensitive_to_geometry_difference() -> None:
    """A geometry difference DOES change the bytes."""
    doc_a = Document.from_buffer(PixelBuffer(4, 4, ColorMode.RGBA, fill=RED))
    doc_b = Document.from_buffer(PixelBuffer(4, 5, ColorMode.RGBA, fill=RED))

    assert reference_bytes(doc_a, AssetKind.SPRITE) != reference_bytes(
        doc_b, AssetKind.SPRITE
    )


def test_reference_bytes_tileset_sensitive_to_tile_grid_difference() -> None:
    """TILESET branch: two tilesets sliced from the
    SAME source image but with a different tile grid must hash differently
    (this module's own rationale, ``reference_bytes`` docstring)."""
    source = PixelBuffer(8, 8, ColorMode.RGBA, fill=RED)
    doc_a = Document(8, 8, mode=ColorMode.RGBA)
    doc_a.tilesets.append(Tileset(source, tile_width=4, tile_height=4, name="A"))

    doc_b = Document(8, 8, mode=ColorMode.RGBA)
    doc_b.tilesets.append(Tileset(source, tile_width=2, tile_height=2, name="B"))

    assert reference_bytes(doc_a, AssetKind.TILESET) != reference_bytes(
        doc_b, AssetKind.TILESET
    )


def test_reference_bytes_tileset_ignores_first_gid() -> None:
    """``first_gid`` is a tilemap-placement detail, deliberately excluded
    (this module's own rationale) — two byte-identical tilesets with
    different ``first_gid`` must hash the same."""
    source = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_a = Document(4, 4, mode=ColorMode.RGBA)
    doc_a.tilesets.append(
        Tileset(source, tile_width=4, tile_height=4, name="A", first_gid=1)
    )
    doc_b = Document(4, 4, mode=ColorMode.RGBA)
    doc_b.tilesets.append(
        Tileset(source, tile_width=4, tile_height=4, name="A", first_gid=99)
    )

    assert reference_bytes(doc_a, AssetKind.TILESET) == reference_bytes(
        doc_b, AssetKind.TILESET
    )


def test_reference_bytes_tileset_never_reads_document_layer_state() -> None:
    """The TILESET branch reads only ``document.tilesets[0].source`` and the
    tile grid — never any document ``Frame``/``Layer`` state at all, so it is
    trivially invariant to layer name/opacity/blend/mask/ppi/metadata."""
    source = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc_a = Document(4, 4, mode=ColorMode.RGBA)
    doc_a.tilesets.append(Tileset(source, tile_width=4, tile_height=4, name="A"))

    doc_b = Document(4, 4, mode=ColorMode.RGBA)
    doc_b.frames[0].layers[0].opacity = 0.1
    doc_b.frames[0].layers[0].blend_mode = BlendMode.MULTIPLY
    doc_b.metadata["author"] = "someone"
    doc_b.tilesets.append(Tileset(source, tile_width=4, tile_height=4, name="A"))

    assert reference_bytes(doc_a, AssetKind.TILESET) == reference_bytes(
        doc_b, AssetKind.TILESET
    )


def test_candidate_keys_rejects_non_document() -> None:
    with pytest.raises(AssetEdgesError):
        candidate_keys("not a document", AssetKind.SPRITE)  # type: ignore[arg-type]


def test_candidate_keys_stays_in_step_with_candidates_of() -> None:
    """``candidate_keys`` returns one key per candidate
    ``candidates_of`` names — the two stay in step."""
    buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=BLUE)
    doc = Document(4, 4, mode=ColorMode.RGBA)
    doc.tilesets.extend(
        [
            Tileset(buf_a, tile_width=4, tile_height=4, name="A"),
            Tileset(buf_b, tile_width=4, tile_height=4, name="B"),
        ]
    )

    candidates = candidates_of(doc, AssetKind.TILESET)
    keys = candidate_keys(doc, AssetKind.TILESET)

    assert len(keys) == len(candidates)
    assert keys == tuple(
        reference_bytes(candidate, AssetKind.SPRITE) for candidate in candidates
    )


def test_candidate_keys_empty_for_kind_with_no_candidates() -> None:
    doc = Document(4, 4, mode=ColorMode.RGBA)
    assert candidate_keys(doc, AssetKind.SPRITE) == ()
    assert candidate_keys(doc, AssetKind.TILESET) == ()


def test_candidate_keys_is_deterministic_across_repeat_calls() -> None:
    buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc = Document(4, 4, mode=ColorMode.RGBA)
    doc.tilesets.append(Tileset(buf, tile_width=4, tile_height=4))

    first = candidate_keys(doc, AssetKind.TILESET)
    second = candidate_keys(doc, AssetKind.TILESET)

    assert first == second


@given(
    # Alpha pinned to 255 (fully opaque): standard alpha compositing (this
    # module's flatten_frame -> composite_stack) canonicalises RGB away when
    # alpha is 0 (a transparent pixel's colour is unobservable in the
    # composite), which is a genuine, well-known property of compositing —
    # not something this property should be probing — so it is excluded
    # rather than producing a spurious "pixel differs but bytes equal" case.
    fill_a=st.tuples(*[st.integers(min_value=0, max_value=255)] * 3, st.just(255)),
    fill_b=st.tuples(*[st.integers(min_value=0, max_value=255)] * 3, st.just(255)),
    name_a=st.text(min_size=1, max_size=12),
    name_b=st.text(min_size=1, max_size=12),
)
@settings(max_examples=50)
def test_reference_bytes_sprite_property_pixel_equality_iff_key_equality(
    fill_a, fill_b, name_a, name_b
) -> None:
    """Property: two single-layer, fully-opaque SPRITE documents produce
    EQUAL reference bytes if and only if their pixels are equal —
    independent of the layer name generated for each."""
    buf_a = PixelBuffer(3, 3, ColorMode.RGBA, fill=fill_a)
    buf_b = PixelBuffer(3, 3, ColorMode.RGBA, fill=fill_b)
    doc_a = Document.from_buffer(buf_a, name=name_a)
    doc_b = Document.from_buffer(buf_b, name=name_b)

    equal_bytes = reference_bytes(doc_a, AssetKind.SPRITE) == reference_bytes(
        doc_b, AssetKind.SPRITE
    )
    equal_pixels = fill_a == fill_b

    assert equal_bytes == equal_pixels


# --------------------------------------------------------------------------- #
# candidates_of -> candidate_keys -> edges_for: already-canonical contract    #
# --------------------------------------------------------------------------- #


def test_raw_non_reference_bytes_for_same_content_match_nothing() -> None:
    """``content`` must be already-computed reference-candidate keys — raw
    pixel bytes never match.

    Pins the contract this module's docstring states: hashing a candidate's
    raw (non-canonicalised) representation instead of routing it through
    :func:`candidate_keys` is exactly the silent-failure mode this task
    exists to catch, so it must reliably miss, not accidentally match.
    """
    sprite_buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    sprite_doc = Document.from_buffer(sprite_buf)
    catalog = AssetCatalog()
    _sprite_descriptor, catalog = _register(
        sprite_doc,
        asset_id="sprite-4",
        name="Source",
        kind=AssetKind.SPRITE,
        catalog=catalog,
    )

    tileset = Tileset(sprite_buf, tile_width=4, tile_height=4)
    tileset_doc = Document(sprite_buf.width, sprite_buf.height, mode=sprite_buf.mode)
    tileset_doc.tilesets.append(tileset)
    tileset_descriptor, catalog = _register(
        tileset_doc,
        asset_id="tileset-4",
        name="Tiles",
        kind=AssetKind.TILESET,
        catalog=catalog,
    )

    # Raw, non-canonicalised bytes for the same pixel content (the buffer's
    # own NumPy backing), NOT routed through candidate_keys/reference_bytes.
    raw = sprite_buf.data.tobytes()
    edges = edges_for(tileset_descriptor, [raw], catalog)

    assert edges == ()  # matches nothing — the reference-bytes contract holds
