"""Pure derivation of an asset's dependency edges (REQ-P11-LOGIC-010).

This module derives, over **values**, the direct :class:`DependencyEdge` s a
just-derived asset (its :class:`~pixelart_creator.logic.asset_catalog.AssetDescriptor`)
carries to the catalog entries it references — the three relationships
``design-docs/specs/phase-11-asset-ingress/tasks.md`` T8 names: a tileset →
its source-image sprite, a named animation → the sprites its frames are
built from, a tilemap → its tileset.

**Why matching, not an id field (plan risk R-3, discharged 2026-08-21).** None
of the three referencing domain shapes carries an asset id:
:class:`~pixelart_creator.logic.tileset.Tileset` holds a raw
:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` as its ``source``;
the tilemap → tileset relation runs through ``first_gid`` ranges over chunked
GID grids, not an id; :class:`~pixelart_creator.logic.animation.FrameTag`
indexes the *document's* frames, not a catalog asset. And
:class:`~pixelart_creator.logic.asset_catalog.AssetCatalog` exposes only
``get(asset_id)`` and ``entries()`` — there is no content-hash index. So the
**only** way to find a reference is to hash the referenced content and match
that hash, linearly, over ``catalog.entries()`` — bounded by
:data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS`.

**Why ``content`` is already-canonical bytes, not the domain object itself —
named, not guessed (the layering half of this task).** The canonical bytes
for *any* of the three referenced shapes (a ``PixelBuffer``'s pixels, a
frame's composited sprite, a tileset's serialised form) come only from the
same canonical serialiser an asset's own registration goes through — a
``data/`` concern (``data/project_io``, via ``data/asset_catalog_io`` /
``data/asset_ingress``, T3). ``logic/`` may not import ``data/`` (Article I
§3), so this module cannot reproduce that serialisation without becoming a
**second serialiser** — precisely the defect REQ-P11-DATA-007 forbids. This
module therefore takes each reference candidate as bytes **already**
canonicalised by its caller (the ``data/`` ingress boundary, or its ``ui/``
wiring), through the *same* path a candidate's own registration would have
used — one blob per direct reference the caller has identified from the
domain object (a tileset's ``source``; each ``FrameTag``'s referenced
frame(s); a tilemap's referenced tileset). Recognising *which* sub-object is
a reference candidate, for each of the three relationship kinds, is
therefore the caller's task (it holds the typed domain object); hashing each
candidate and matching it into the catalog — the part that is genuinely
kind-agnostic and pure — is this module's.

**The guard the parent requires:** a candidate whose hash matches no catalog
entry contributes **no edge and no error** — a reference to unregistered (or
never-to-be-registered) content degrades to "no edge", never a wrong one,
and a ``content`` sequence with no candidates at all (a source that
references nothing) yields an **empty edge set, no error**.

**[T8-B, ruling P11-R8, plan §3.10 — the Item-2 fix, amending the paragraph
above.]** Whole-project canonical bytes bake in the **layer display name**
(the caller's canonical serialiser round-trips the document *as the user
named its layers*), so matching on them derives **zero** edges for every
shape the running application actually produces. ``content`` is therefore no
longer the ``data/`` ingress boundary's canonical project bytes: it is
:func:`candidate_keys`'s **content-only** reference bytes
(:func:`reference_bytes` — geometry + colour mode + pixels, defined in this
module, never the layer name/opacity/blend mode/mask/ppi/palette/tags/
metadata), and :func:`edges_for` matches it against each catalog entry's
**``reference_key``** (not ``content_hash``, which keeps every meaning it had
and moves nowhere). This is a ``logic/``-only computation — no ``data/``
serialiser is reproduced, and REQ-P11-DATA-007 is not touched — because
:func:`reference_bytes` deliberately canonicalises less than PIO-1 does: it
never touches layer identity, blend state or metadata, only the pictorial
content those referencing shapes are built from.

LAYER: logic/ — pure Python, ZERO Qt (S11). Enforced by
``main/scripts/check_layering.py``; the only Qt-dependent file outside
``ui/`` is ``ui/commands.py``.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.blend import BlendMode, composite_stack
from pixelart_creator.logic.constants import DEFAULT_LAYER_OPACITY
from pixelart_creator.logic.content_hash import ContentHashError, content_hash
from pixelart_creator.logic.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphError,
)
from pixelart_creator.logic.document import Document, Layer, LayerGroup, LayerNode
from pixelart_creator.logic.export import flatten_frame
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tileset import Tileset

__all__ = [
    "AssetEdgesError",
    "edges_for",
    "candidates_of",
    "reference_bytes",
    "candidate_keys",
]


class AssetEdgesError(ValueError):
    """Base for every error this module raises.

    A module-specific base lets a caller catch this module's failures
    without catching everything, the same pattern
    :class:`~pixelart_creator.logic.asset_extract.AssetExtractError` uses.
    Wraps :class:`~pixelart_creator.logic.content_hash.ContentHashError` (a
    malformed candidate blob) and, defensively,
    :class:`~pixelart_creator.logic.dependency_graph.DependencyGraphError`
    (see :func:`edges_for`'s docstring for why the latter should be
    unreachable in practice).
    """


def edges_for(
    descriptor: AssetDescriptor,
    content: Sequence[bytes],
    catalog: AssetCatalog,
) -> Tuple[DependencyEdge, ...]:
    """Return the direct :class:`DependencyEdge` s ``descriptor`` carries into
    ``catalog``.

    For each blob in ``content`` — one reference-candidate key per direct
    reference candidate the caller identified on the registered domain
    object (:func:`candidate_keys`'s output: a tileset's source-image
    reference bytes; one blob per sprite a ``FrameTag`` covers; a tilemap's
    tileset reference bytes) — this function computes its content hash
    (:func:`~pixelart_creator.logic.content_hash.content_hash`, the single
    hashing primitive every content-hash consumer in this codebase goes
    through) and matches it **linearly** against ``catalog.entries()``'
    **``reference_key``** field (``AssetCatalog`` has no reference-key index,
    and none of the three referencing shapes carries an asset id — see the
    module docstring), **skipping any entry whose ``reference_key`` is
    ``""``** (ruling P11-R8, plan §3.10 — *unknown* never matches). A match
    yields one :class:`~pixelart_creator.logic.dependency_graph.DependencyEdge`
    from ``descriptor.asset_id`` (the referencing asset) to the matched
    entry's ``asset_id`` (the referenced asset), pinned to the matched
    entry's ``content_hash`` (the break-detection change-detector) — the
    edge stays keyed to the parent's ``asset_id -> content_hash`` reference
    model, which this ruling does not touch.

    A candidate that matches no catalog entry contributes **no edge and no
    error** — this is the guard that lets "references content that was
    never registered" degrade to "no edge" instead of a wrong one. An empty
    ``content`` (a source that references nothing) likewise yields an
    **empty edge set and no error**. A candidate that would match
    ``descriptor`` itself (a self-reference) is skipped rather than
    produced, since a self-edge is a 1-cycle
    (:class:`~pixelart_creator.logic.dependency_graph.DependencyEdge`'s own
    contract) and this function's job is to degrade a bad reference to "no
    edge", never to raise one.

    Duplicate candidates — two frames built from the same sprite, or the
    same source referenced twice — collapse to one edge: the result is
    routed through :class:`~pixelart_creator.logic.dependency_graph.DependencyGraph`,
    which de-duplicates identical ``(source_id, target_id)`` pairs
    (``pinned_hash`` is always identical for a duplicate here, since it is
    always the target entry's own ``content_hash``) and orders the result
    deterministically (``(source_id, target_id)``-sorted) — the same
    ordering guarantee every other query in this codebase gives, and what
    makes derivation from the same inputs byte-identical across runs.

    This function only ever derives a **single-source star** of edges (every
    edge's ``source_id`` is ``descriptor.asset_id``), so routing it through
    :class:`DependencyGraph` cannot itself close a multi-node cycle; the
    self-reference guard above removes the one topology (a 1-cycle) a
    single-source star could otherwise produce. Whether the *accumulated*
    graph (this asset's edges plus every edge derived by every earlier
    registration) is acyclic is **not** this function's concern — that is
    decided where the accumulated set is assembled and applied
    (``ui/dependency_graph_view.show_edges``, ruling P11-R3, plan §3.5): this
    function derives edges for one just-registered asset, over the catalog
    as it stood **before** that asset was added, and never rejects, retries
    or looks beyond that.

    Args:
        descriptor: The referencing asset's descriptor (already derived by
            :func:`~pixelart_creator.logic.asset_extract.descriptor_for`).
            Its ``asset_id`` is every returned edge's ``source_id``.
        content: The direct reference candidates, as already-computed
            reference-candidate keys (:func:`candidate_keys`'s output) —
            zero or more. Never re-serialised here (see the module
            docstring for why re-serialising would be a second serialiser).
        catalog: The catalog to match candidates against — the state
            **before** ``descriptor`` is added to it.

    Returns:
        The direct dependency edges, deterministic
        ``(source_id, target_id)``-sorted, zero or more.

    Raises:
        AssetEdgesError: If a ``content`` element is not ``bytes``/
            ``bytearray``, or (defensively; should be unreachable given the
            self-reference guard above) the derived edge set is internally
            inconsistent.
    """
    matched: List[DependencyEdge] = []
    for blob in content:
        try:
            digest = content_hash(blob)
        except ContentHashError as exc:
            raise AssetEdgesError(f"cannot hash reference candidate: {exc}") from exc
        for entry in catalog.entries():
            if entry.reference_key and entry.reference_key == digest:
                if entry.asset_id != descriptor.asset_id:
                    matched.append(
                        DependencyEdge(
                            source_id=descriptor.asset_id,
                            target_id=entry.asset_id,
                            pinned_hash=entry.content_hash,
                        )
                    )
                break
    try:
        return DependencyGraph(edges=tuple(matched)).edges
    except DependencyGraphError as exc:
        raise AssetEdgesError(
            f"derived edge set for {descriptor.asset_id!r} is inconsistent: {exc}"
        ) from exc


# --------------------------------------------------------------------------- #
# candidates_of — the per-kind reference-candidate rule (T8-A, ruling P11-R6) #
# --------------------------------------------------------------------------- #


def _sprite_document(buffer: PixelBuffer) -> Document:
    """Wrap ``buffer`` the same way any RGBA source becomes a ``SPRITE`` document.

    :meth:`Document.from_buffer` is the **only** shipped factory that turns a
    standalone :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` into a
    single-frame, single-layer :class:`Document` — the same shape a ``SPRITE``
    registration (``data/asset_ingress.register`` with ``kind=AssetKind.SPRITE``)
    would build from that buffer. Reusing it here (rather than composing an
    ad hoc ``Document`` by hand) is what lets a tileset's source image or an
    animation frame's flattened pixels match a *separately registered* sprite
    asset's canonical bytes byte-for-byte.
    """
    return Document.from_buffer(buffer)


def _tileset_document(tileset: Tileset) -> Document:
    """Wrap ``tileset`` the way a standalone ``TILESET`` registration would.

    **Unverified against a real caller (report, don't invent — T8-A's escape
    hatch).** Unlike :func:`_sprite_document`, no factory anywhere in this
    tree builds a "just this tileset" :class:`Document` today: a
    :class:`Tileset` is normally attached to an already-open working document
    (:meth:`Document.make_add_tileset_command`), never built standalone for
    registration. This function defines the **minimal, deterministic**
    candidate shape — a document sized to the tileset's own source image,
    carrying exactly that one tileset and nothing else — so a tilemap's
    reference to a tileset asset degrades to "no edge" rather than a wrong
    one when the shapes disagree. **Byte-identical agreement with whatever
    document a future tileset-registration path (T9 or its successor) builds
    is not proven here** — see this module's report for the finding; T17
    extends coverage once that caller exists.
    """
    document = Document(
        tileset.source.width, tileset.source.height, mode=tileset.source.mode
    )
    document.tilesets = [tileset]
    return document


def candidates_of(document: Document, kind: AssetKind) -> Tuple[Document, ...]:
    """Return ``document``'s direct reference candidates for ``kind``, purely.

    The per-kind extraction rule ``REQ-P11-LOGIC-010`` itself states (
    ``spec.md:576-578``): a ``TILESET`` document's candidate is its tileset's
    source-image sprite; an ``ANIMATION`` document's candidates are the
    sprites its named frame tags' frames flatten to; a ``TILEMAP`` document's
    candidates are its tilemaps' attached tilesets. ``SPRITE`` and ``PALETTE``
    documents reference nothing under this requirement and return ``()``.

    Each candidate is returned **wrapped as the ``Document`` it would itself
    have been registered as** (:func:`_sprite_document` /
    :func:`_tileset_document`) — never as the raw domain value — because the
    caller's next step (T9, ``data/asset_ingress.canonical_bytes``) only
    knows how to canonicalise a :class:`Document`; recognising *which*
    sub-object is a candidate is this function's job, not the caller's
    (ruling P11-R6, plan §3.8). This function performs **no I/O and no
    serialisation** — it returns values only; the caller canonicalises them.

    Order is deterministic and stable across repeat calls on the same
    ``document``: tilesets/tilemaps in their list order, frame tags in their
    list order, frames within a tag from ``from_frame`` to ``to_frame``
    ascending — the same iteration order :class:`Document` itself keeps
    (T17 tests this).

    Args:
        document: The just-registered (or about-to-be-registered) source —
            the same object the caller passed to ``register``/would pass to
            it.
        kind: The :class:`AssetKind` ``document`` was (or will be)
            registered as; selects which extraction rule runs.

    Returns:
        Zero or more reference-candidate documents, in the deterministic
        order above. A ``document`` whose relevant collection is empty (a
        tileset-less ``TILESET`` document, a tag-less ``ANIMATION``
        document, a tileset-less tilemap) returns ``()`` and raises nothing
        — the same degrade-to-no-edge guard :func:`edges_for` carries for an
        unmatched candidate.

    Raises:
        AssetEdgesError: If ``document`` is not a :class:`Document` or
            ``kind`` is not an :class:`AssetKind`.
    """
    if not isinstance(document, Document):
        raise AssetEdgesError(f"expected a Document, got {document!r}")
    if not isinstance(kind, AssetKind):
        raise AssetEdgesError(f"expected an AssetKind, got {kind!r}")

    if kind is AssetKind.TILESET:
        return tuple(_sprite_document(tileset.source) for tileset in document.tilesets)

    if kind is AssetKind.ANIMATION:
        candidates: List[Document] = []
        for tag in document.frame_tags:
            for frame_index in range(tag.from_frame, tag.to_frame + 1):
                frame = document.frames[frame_index]
                composite = flatten_frame(frame, document.width, document.height)
                candidates.append(_sprite_document(composite))
        return tuple(candidates)

    if kind is AssetKind.TILEMAP:
        tilemap_candidates: List[Document] = []
        for tilemap in document.tilemaps:
            for tileset in tilemap.tilesets:
                tilemap_candidates.append(_tileset_document(tileset))
        return tuple(tilemap_candidates)

    # SPRITE, PALETTE: no relationship REQ-P11-LOGIC-010 names for these
    # kinds — degrade to "references nothing", not an error.
    return ()


# --------------------------------------------------------------------------- #
# reference_bytes / candidate_keys — content-only keying (T8-B, ruling P11-R8)#
# --------------------------------------------------------------------------- #

#: Field separator for :func:`reference_bytes`'s header — never a byte that
#: can appear inside a decimal width/height/tile-grid component or an
#: ``AssetKind``/``ColorMode`` enum value (both are lowercase ASCII words),
#: so the header cannot be crafted to collide across two different
#: geometries. Not a numeric parameter (S12 governs numeric magnitudes, not
#: a structural delimiter byte), so it is not sourced from ``constants.py``.
_REFERENCE_HEADER_SEP = "|"


def _pack_reference(
    kind: AssetKind,
    width: int,
    height: int,
    mode: ColorMode,
    pixels: bytes,
    grid: Tuple[int, ...] = (),
) -> bytes:
    """Return the deterministic ``header + pixels`` bytes for one reference shape.

    The header records exactly the fields the module docstring's
    canonicalisation names — kind tag, geometry, colour mode, and (for a
    ``TILESET``) the tile grid — and nothing else: no layer name, opacity,
    blend mode, mask, ppi, palette, tags or metadata ever reach this
    function, because none of those are passed to it.
    """
    header = _REFERENCE_HEADER_SEP.join(
        [
            kind.value,
            str(width),
            str(height),
            mode.value,
            ",".join(str(component) for component in grid),
        ]
    )
    return header.encode("utf-8") + _REFERENCE_HEADER_SEP.encode("utf-8") + pixels


def _reference_layers(nodes: Sequence[LayerNode]) -> List[LayerNode]:
    """Return a presentation-normalised copy of a layer/group tree, recursively.

    **[DEV-38 fix, this task.]** :func:`composite_stack` (the shipped, single
    compositor — reused here, never re-implemented, per Article I) honours
    each node's ``opacity``, ``blend_mode`` and ``mask`` in addition to its
    pixel content (``blend.py:696``). Feeding it a document's *real* layer
    tree therefore bakes those three presentation attributes into the
    composite, which is exactly what T8-B's own contract forbids for
    ``reference_bytes`` ("NOT the layer name, opacity, blend mode, mask, ppi,
    palette, tags or metadata", plan §3.10 / `tasks.md`:460). This function
    builds a **new** tree of :class:`~pixelart_creator.logic.document.Layer`
    / :class:`~pixelart_creator.logic.document.LayerGroup` nodes — never
    mutating ``nodes`` or any buffer they hold — where every node's opacity is
    pinned to :data:`DEFAULT_LAYER_OPACITY` (fully opaque, the identity value
    for alpha compositing), ``blend_mode`` is pinned to
    :attr:`~pixelart_creator.logic.blend.BlendMode.NORMAL` (the identity
    blend — ``B(Cb, Cs) = Cs``, ``blend.py:139-140``) and ``mask`` is pinned
    to ``None`` (no additional per-pixel gating). ``buffer``,
    ``smart_source`` and ``children`` are carried over **unchanged** (never
    copied — read-only to the compositor) because they, and ``visible``,
    *are* the pictorial content: a hidden layer or a differently-painted
    buffer changes what the composite actually shows, which is precisely
    what a content-only key must still be sensitive to. ``name`` is dropped
    entirely (:class:`CompositeNode` never reads it, so it cannot affect the
    result either way).
    """
    normalised: List[LayerNode] = []
    for node in nodes:
        if isinstance(node, LayerGroup):
            normalised.append(
                LayerGroup(
                    children=_reference_layers(node.children),
                    opacity=DEFAULT_LAYER_OPACITY,
                    visible=node.visible,
                    blend_mode=BlendMode.NORMAL,
                    mask=None,
                )
            )
        else:
            normalised.append(
                Layer(
                    node.buffer,
                    opacity=DEFAULT_LAYER_OPACITY,
                    visible=node.visible,
                    blend_mode=BlendMode.NORMAL,
                    mask=None,
                    smart_source=node.smart_source,
                )
            )
    return normalised


def reference_bytes(document: Document, kind: AssetKind) -> bytes:
    """Return ``document``'s content-only reference bytes for ``kind``, purely.

    **The TILESET canonicalisation definition (this module's to define, per
    T8-B step 1 / ruling P11-R8) — UNCHANGED by this task.** Ruling P11-R8
    (plan §3.10) names the shape only in prose — "source + tile grid for a
    TILESET" — and leaves the exact byte layout to this task. Defined here
    as: the kind tag, the **source image's** geometry (``width``/``height``)
    and colour mode, the **tile grid** that carves that source into tiles
    (``tile_width``, ``tile_height``, ``margin``, ``spacing`` — in that
    order, comma-joined), then the source image's raw pixel bytes.
    **Rationale:** the tile grid is what makes two tilesets built from the
    *same* source image but sliced differently genuinely different pictorial
    content (a different set of tiles), so it belongs in a *content-only*
    key exactly as much as the pixels do; ``first_gid`` is deliberately
    excluded because it is a tilemap-placement detail of *this* tileset
    instance, not a property of what the tileset's tiles depict, and
    including it would make two byte-identical tilesets registered into
    different tilemaps hash differently for no pictorial reason. This
    definition reads a raw :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer`
    (``tileset.source``) directly — it was never routed through
    :func:`~pixelart_creator.logic.blend.composite_stack` and so never had an
    opacity/blend/mask leak to begin with; DEV-38 does not touch it.

    **The SPRITE canonicalisation definition — AMENDED, DEV-38 (this task).**
    A ``SPRITE``'s reference bytes are the kind tag, ``document``'s geometry
    and colour mode, then the pixel bytes of frame 0's layer stack composited
    through :func:`~pixelart_creator.logic.blend.composite_stack` **over a
    presentation-normalised copy of that stack** (:func:`_reference_layers`):
    every node's ``opacity`` forced to :data:`DEFAULT_LAYER_OPACITY`,
    ``blend_mode`` forced to ``NORMAL`` and ``mask`` forced to ``None``,
    while ``buffer``, ``smart_source``, ``children`` and ``visible`` — the
    pixel content and the structural shape that survive presentation changes
    — pass through untouched. The previous definition called
    ``export.flatten_frame`` directly, which composites over the layer
    stack's **real** opacity/blend-mode/mask (`blend.py:696`, LOGIC-005/-007/
    -012) — a document differing *only* in a single layer's opacity produced
    genuinely different reference bytes (measured, `subagent-report-agt-04-
    python-tester-a104edec-20260822T111623.md` §4: ``opacity-only equal:
    False``), contradicting this function's own docstring promise and T8-B's
    Done-when clause 3. Same "geometry + colour mode + pixels" shape as
    before, with no tile grid because a sprite has none — only *how* the
    pixels are produced changed.

    Pure, Qt-free, no I/O — matches this module's other functions.

    Args:
        document: The document to derive reference bytes from. For
            ``AssetKind.TILESET`` it must carry **exactly one** tileset (the
            same ambiguity guard :func:`~pixelart_creator.data.asset_ingress.register`
            applies before calling this function for a being-registered
            document; every candidate :func:`candidates_of` returns is
            already shaped this way).
        kind: Selects the canonicalisation rule. Only ``AssetKind.SPRITE``
            and ``AssetKind.TILESET`` are defined — the only two kinds
            ``REQ-P11-LOGIC-010`` ever treats as a reference *target*.

    Returns:
        Deterministic, content-only bytes: identical pictorial content (same
        geometry, colour mode, pixels, and — for a TILESET — the same tile
        grid) always yields identical bytes, and a layer's display name,
        opacity, blend mode, mask, ppi, palette, tags or metadata never
        affect the result.

    Raises:
        AssetEdgesError: If ``document`` is not a :class:`Document`, ``kind``
            is not ``SPRITE`` or ``TILESET``, or (``TILESET`` only)
            ``document`` does not carry exactly one tileset.
    """
    if not isinstance(document, Document):
        raise AssetEdgesError(f"expected a Document, got {document!r}")
    if not isinstance(kind, AssetKind):
        raise AssetEdgesError(f"expected an AssetKind, got {kind!r}")

    if kind is AssetKind.SPRITE:
        normalised_layers = _reference_layers(document.frames[0].layers)
        composite = composite_stack(normalised_layers, document.width, document.height)
        return _pack_reference(
            kind,
            composite.width,
            composite.height,
            composite.mode,
            composite.data.tobytes(),
        )

    if kind is AssetKind.TILESET:
        if len(document.tilesets) != 1:
            raise AssetEdgesError(
                "reference_bytes(kind=TILESET) requires exactly one tileset, "
                f"got {len(document.tilesets)}"
            )
        tileset = document.tilesets[0]
        source = tileset.source
        grid = (
            tileset.tile_width,
            tileset.tile_height,
            tileset.margin,
            tileset.spacing,
        )
        return _pack_reference(
            kind, source.width, source.height, source.mode, source.data.tobytes(), grid
        )

    raise AssetEdgesError(f"reference_bytes has no definition for kind {kind!r}")


def candidate_keys(document: Document, kind: AssetKind) -> Tuple[bytes, ...]:
    """Return ``document``'s reference-candidate keys for ``kind``, purely.

    Built **over** :func:`candidates_of` — T8-A's per-kind rule stays the
    single statement of "which sub-object is a candidate"; this function adds
    nothing of its own except turning each candidate :func:`candidates_of`
    already identified into its :func:`reference_bytes`. Re-expressing the
    per-kind rule here (instead of calling :func:`candidates_of`) would leave
    that function with no production caller — the exact dead-seam defect
    ruling P11-R8 exists to close (T8-B step 2).

    Every candidate :func:`candidates_of` returns is already wrapped as the
    shape its own :func:`reference_bytes` call needs: a ``TILEMAP``
    document's candidates are :func:`_tileset_document`-wrapped (one
    tileset), so they are keyed as ``AssetKind.TILESET``; a ``TILESET`` or
    ``ANIMATION`` document's candidates are :func:`_sprite_document`-wrapped,
    so they are keyed as ``AssetKind.SPRITE``.

    Args:
        document: The just-registered (or about-to-be-registered) source —
            the same argument :func:`candidates_of` takes.
        kind: The :class:`AssetKind` ``document`` was (or will be)
            registered as.

    Returns:
        Zero or more reference-candidate key bytes, in :func:`candidates_of`'s
        deterministic order. This is the direct replacement for the
        ``tuple(canonical_bytes(d) for d in candidates_of(...))`` recipe
        ruling P11-R6 named — ``ui/asset_library_actions._derive_and_emit_edges``
        (T9-A) calls this function instead.

    Raises:
        AssetEdgesError: Propagated from :func:`candidates_of` (bad
            ``document``/``kind``) or :func:`reference_bytes` (should be
            unreachable here, since every candidate is already correctly
            shaped for its target kind).
    """
    candidates = candidates_of(document, kind)
    target_kind = AssetKind.TILESET if kind is AssetKind.TILEMAP else AssetKind.SPRITE
    return tuple(reference_bytes(candidate, target_kind) for candidate in candidates)
