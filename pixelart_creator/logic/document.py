"""Document model — the project state tree (zero Qt, S11).

Mirrors the Architecture state manager: ``Document -> frames[] -> layers[] ->
PixelBuffer`` plus a shared :class:`~pixelart_creator.logic.palette.Palette` and
metadata. Phase 1 uses a single frame with one or more layers; Phases 4/5 build
layer groups/blend-modes and the animation timeline on this same tree without
reshaping it.
"""

from __future__ import annotations

import math
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from pixelart_creator.logic import palette_ops
from pixelart_creator.logic.animation import (
    AnimationError,
    FrameTag,
    PlaybackMode,
    clamp_tag_range,
    validate_tag_range,
)
from pixelart_creator.logic.blend import BlendMode, composite_stack
from pixelart_creator.logic.color import ColorError, from_hex
from pixelart_creator.logic.constants import (
    DEFAULT_DOCUMENT_PPI,
    DEFAULT_FRAME_DURATION_MS,
    DEFAULT_LAYER_OPACITY,
    MAX_FRAMES,
    MAX_GROUP_NESTING_DEPTH,
    MAX_LAYERS_PER_FRAME,
)
from pixelart_creator.logic.edit_trace import (
    EditTrace,
    LayerAttrTrace,
    LayerAttrValue,
    LayerOrderTrace,
    MetadataTrace,
)
from pixelart_creator.logic.history import Command, FunctionCommand
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.project_prefs import ProjectPrefs
from pixelart_creator.logic.tilemap import Tilemap
from pixelart_creator.logic.tileset import Tileset

#: Default animation frame duration (ms). Re-exported from
#: :mod:`pixelart_creator.logic.constants` (single source, S12) so existing
#: default-arg call sites and importers keep working.
__all__ = [
    "DEFAULT_FRAME_DURATION_MS",
    "DocumentError",
    "Layer",
    "LayerGroup",
    "LayerNode",
    "LayerRef",
    "Frame",
    "FrameTag",
    "PlaybackMode",
    "Document",
    "Tileset",
    "Tilemap",
    "iter_layers",
]

#: Address of a node in a frame tree: a top-level index, or a path of indices
#: descending through nested groups (``[i, j, k]`` -> ``layers[i].children[j]
#: .children[k]``).
LayerRef = Union[int, Sequence[int]]


class DocumentError(ValueError):
    """Raised on an invalid document structure or operation."""


class _TracedCommand(FunctionCommand):
    """A :class:`FunctionCommand` that reports a fixed :meth:`edit_trace` (T8/T9/T10).

    ``REQ-P10-UI-025``: the four op classes' commands describe their own change
    at build time (the new value / resulting order is already known then), so
    the trace is computed once and returned as-is on every call — additive,
    Qt-free, no clock, no site id (plan §3.1, §3.2).
    """

    __slots__ = ("_trace",)

    def __init__(
        self,
        do: Callable[[], None],
        undo: Callable[[], None],
        *,
        label: str,
        trace: Tuple[EditTrace, ...],
    ) -> None:
        """Wrap ``do``/``undo`` as a :class:`FunctionCommand`, carrying ``trace``."""
        super().__init__(do, undo, label=label)
        self._trace = trace

    def edit_trace(self) -> Tuple[EditTrace, ...]:
        """Return the fixed trace this command was built with."""
        return self._trace


def _validate_opacity(value: float) -> float:
    """Validate and coerce an opacity to a ``float`` in ``0.0..1.0``."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise DocumentError(f"opacity must be a number, got {value!r}")
    if value < 0.0 or value > 1.0:
        raise DocumentError(f"opacity {value} out of range 0.0..1.0")
    return float(value)


def _validate_blend_mode(value: BlendMode) -> BlendMode:
    if not isinstance(value, BlendMode):
        raise DocumentError(f"blend_mode must be a BlendMode, got {value!r}")
    return value


def _validate_ppi(value: float) -> float:
    """Validate and coerce a document PPI to a finite ``float`` ``> 0`` (BF-3).

    Real-size preview needs a positive, finite pixels-per-inch (ADR-0025 §1;
    REQ-P9-LOGIC-007); ``0``, negative, NaN or infinity is rejected.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DocumentError(f"ppi must be a number, got {value!r}")
    if not math.isfinite(value) or value <= 0.0:
        raise DocumentError(f"ppi must be finite and > 0, got {value}")
    return float(value)


class Layer:
    """A single named pixel layer with compositing attributes.

    Satisfies :class:`~pixelart_creator.logic.blend.CompositeNode` as a leaf.
    """

    __slots__ = (
        "name",
        "buffer",
        "_opacity",
        "visible",
        "locked",
        "_blend_mode",
        "mask",
        "reference",
        "smart_source",
        "layer_id",
    )

    def __init__(
        self,
        buffer: PixelBuffer,
        name: str = "Layer",
        *,
        opacity: float = DEFAULT_LAYER_OPACITY,
        visible: bool = True,
        locked: bool = False,
        blend_mode: BlendMode = BlendMode.NORMAL,
        mask: Optional[PixelBuffer] = None,
        reference: bool = False,
        smart_source: Optional["Layer"] = None,
        layer_id: int = 0,
    ) -> None:
        """Initialise a layer from a buffer plus optional compositing attributes.

        ``layer_id`` is a stable cross-frame track identifier (research Q4
        caveat); ``0`` means "unminted" — :class:`Document` mints a positive id
        via :meth:`Document._assign_ids`. Additive, so existing call sites that
        omit it are unaffected.
        """
        self.name = name
        self.buffer = buffer
        self.visible = visible
        self.locked = locked
        self.mask = mask
        self.reference = reference
        self.smart_source = smart_source
        self.layer_id = layer_id
        self._opacity = DEFAULT_LAYER_OPACITY
        self._blend_mode = BlendMode.NORMAL
        self.opacity = opacity  # validates via setter
        self.blend_mode = blend_mode  # validates via setter

    @property
    def opacity(self) -> float:
        """Layer opacity in ``0.0..1.0``."""
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        self._opacity = _validate_opacity(value)

    @property
    def blend_mode(self) -> BlendMode:
        """The layer's :class:`~pixelart_creator.logic.blend.BlendMode`."""
        return self._blend_mode

    @blend_mode.setter
    def blend_mode(self, value: BlendMode) -> None:
        self._blend_mode = _validate_blend_mode(value)

    def effective_buffer(self) -> PixelBuffer:
        """Return the buffer this layer contributes to the composite.

        A smart layer mirrors its source's *current* pixels read-only
        (LOGIC-014); an ordinary layer contributes its own buffer.
        """
        if self.smart_source is not None:
            return self.smart_source.effective_buffer()
        return self.buffer

    def __repr__(self) -> str:
        """Return a debug representation naming the layer and its buffer."""
        return f"Layer({self.name!r}, {self.buffer!r})"


class LayerGroup:
    """A group node: ordered children composited then blended as one (LOGIC-011).

    Satisfies :class:`~pixelart_creator.logic.blend.CompositeNode` as a group
    (detected by its ``children`` attribute); carries its own compositing
    attributes applied to the flattened subtree.
    """

    __slots__ = (
        "name",
        "children",
        "_opacity",
        "visible",
        "locked",
        "_blend_mode",
        "mask",
        "reference",
        "layer_id",
        "_composite_cache",
    )

    def __init__(
        self,
        name: str = "Group",
        children: Optional[List["LayerNode"]] = None,
        *,
        opacity: float = DEFAULT_LAYER_OPACITY,
        visible: bool = True,
        locked: bool = False,
        blend_mode: BlendMode = BlendMode.NORMAL,
        mask: Optional[PixelBuffer] = None,
        reference: bool = False,
        layer_id: int = 0,
    ) -> None:
        """Initialise a group from optional children plus compositing attributes.

        ``layer_id`` is the stable cross-frame track id (``0`` = unminted; see
        :class:`Layer`).
        """
        self.name = name
        self.children: List["LayerNode"] = list(children) if children else []
        self.visible = visible
        self.locked = locked
        self.mask = mask
        self.reference = reference
        self.layer_id = layer_id
        self._opacity = DEFAULT_LAYER_OPACITY
        self._blend_mode = BlendMode.NORMAL
        self.opacity = opacity
        self.blend_mode = blend_mode
        #: Transient single-entry MRU of this group's flattened children,
        #: ``(region_key, ndarray)``, written by ``blend._flatten_group`` (D4).
        #: NEVER serialised — ``data/project_io.py`` lists persisted fields
        #: explicitly and does not touch it; a fresh/loaded group starts
        #: uncached. Invalidated up the ancestor chain on any mutating op.
        self._composite_cache: Optional[Tuple[Tuple[int, int, int, int], Any]] = None

    @property
    def opacity(self) -> float:
        """Group opacity in ``0.0..1.0``."""
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        self._opacity = _validate_opacity(value)

    @property
    def blend_mode(self) -> BlendMode:
        """The group's :class:`~pixelart_creator.logic.blend.BlendMode`."""
        return self._blend_mode

    @blend_mode.setter
    def blend_mode(self, value: BlendMode) -> None:
        self._blend_mode = _validate_blend_mode(value)

    def __repr__(self) -> str:
        """Return a debug representation naming the group and its child count."""
        return f"LayerGroup({self.name!r}, {len(self.children)} children)"


#: A node in the frame layer tree — a leaf :class:`Layer` or a :class:`LayerGroup`.
LayerNode = Union[Layer, LayerGroup]


def iter_layers(nodes: Sequence["LayerNode"]) -> "List[Layer]":
    """Depth-first list of every :class:`Layer` leaf under ``nodes``.

    Flattens groups so callers that only care about pixel layers (colour
    analytics, export, canvas paint) can ignore the group structure.
    """
    out: List[Layer] = []
    for node in nodes:
        if isinstance(node, LayerGroup):
            out.extend(iter_layers(node.children))
        else:
            out.append(node)
    return out


#: Backwards-compatible private alias (pre-Phase-4 internal name).
_iter_layers = iter_layers


def _group_depth(node: "LayerNode") -> int:
    """Nesting depth of ``node``: ``0`` for a leaf, ``1 + max child depth``."""
    if isinstance(node, LayerGroup):
        return 1 + max((_group_depth(c) for c in node.children), default=0)
    return 0


# --------------------------------------------------------------------------- #
# Group-cache invalidation (D4 — ADR-0007 §Amendment (T13))                    #
# --------------------------------------------------------------------------- #


def _group_chain(
    nodes: List["LayerNode"], target: List["LayerNode"], acc: List["LayerGroup"]
) -> bool:
    """Collect into ``acc`` the ancestor groups owning ``target`` (root→owner).

    Descends ``nodes`` for the group whose ``children`` list *is* ``target``,
    appending each :class:`LayerGroup` on the path. Returns ``True`` and leaves
    ``acc`` = ``[outermost, …, immediate owner]`` once found; ``[]`` when
    ``target`` is a top-level list (no owning group).
    """
    if nodes is target:
        return True
    for node in nodes:
        if isinstance(node, LayerGroup):
            acc.append(node)
            if _group_chain(node.children, target, acc):
                return True
            acc.pop()
    return False


def _clear_caches(groups: Iterable["LayerGroup"]) -> None:
    """Drop the cached flattened intermediate of each group (D4)."""
    for group in groups:
        group._composite_cache = None


def _invalidate_all_caches(nodes: Sequence["LayerNode"]) -> None:
    """Drop every group cache in a subtree (geometry / bulk change)."""
    for node in nodes:
        if isinstance(node, LayerGroup):
            node._composite_cache = None
            _invalidate_all_caches(node.children)


class Frame:
    """One animation frame: a tree of layers/groups plus a display duration."""

    __slots__ = ("layers", "duration_ms")

    def __init__(
        self,
        layers: Optional[List["LayerNode"]] = None,
        duration_ms: int = DEFAULT_FRAME_DURATION_MS,
    ) -> None:
        """Initialise a frame from an optional node list and display duration."""
        if duration_ms <= 0:
            raise DocumentError(f"frame duration must be positive, got {duration_ms}")
        self.layers: List["LayerNode"] = list(layers) if layers else []
        self.duration_ms = duration_ms

    def __repr__(self) -> str:
        """Return a debug representation with the frame's layer count and duration."""
        return f"Frame({len(self.layers)} layers, {self.duration_ms}ms)"


class Document:
    """A pixel-art project: canvas geometry, palette, and a frame/layer tree."""

    __slots__ = (
        "width",
        "height",
        "mode",
        "palette",
        "frames",
        "metadata",
        "frame_tags",
        "tilesets",
        "tilemaps",
        "ppi",
        "_next_layer_id",
        "prefs",
    )

    def __init__(
        self,
        width: int,
        height: int,
        *,
        mode: ColorMode = ColorMode.RGBA,
        palette: Optional[Palette] = None,
        metadata: Optional[Dict[str, str]] = None,
        ppi: float = DEFAULT_DOCUMENT_PPI,
        prefs: Optional[ProjectPrefs] = None,
    ) -> None:
        """Create a document with one frame holding one empty background layer.

        ``ppi`` is the document's real-size pixels-per-inch (BF-3, ADR-0025 §1;
        default :data:`DEFAULT_DOCUMENT_PPI`), validated ``> 0``/finite; it is a
        first-class document property consumed by ``logic/preview.real_size_scale``
        and persisted in ``.pixproj`` v5.

        ``prefs`` is the per-project confirmation-preference snapshot
        (``REQ-P5-DATA-004``, ADR-0056): a preference, not document content —
        setting it never pushes a :class:`~pixelart_creator.logic.history.Command`
        and it plays no part in document equality/dirty tracking. Defaults to
        an all-defaults :class:`ProjectPrefs` when omitted, so every existing
        call site is unaffected.
        """
        base = PixelBuffer(width, height, mode)
        self.width = base.width
        self.height = base.height
        self.mode = mode
        self.palette = palette if palette is not None else Palette()
        self.metadata: Dict[str, str] = dict(metadata) if metadata else {}
        #: Real-size document resolution, pixels-per-inch (BF-3; REQ-P9-LOGIC-007).
        self.ppi: float = _validate_ppi(ppi)
        #: Per-project confirmation preferences (REQ-P5-DATA-004, ADR-0056);
        #: not document content (no undo command, no dirty-flag implication).
        self.prefs: ProjectPrefs = prefs if prefs is not None else ProjectPrefs()
        #: Ordered document-level frame tags (named animations, REQ-P5-LOGIC-009).
        self.frame_tags: List[FrameTag] = []
        #: Phase-6 tileset/tilemap collections (ADR-0016; empty by default so
        #: v1/v2/v3 projects load unchanged). Attach/detach are reversible ops.
        self.tilesets: List[Tileset] = []
        self.tilemaps: List[Tilemap] = []
        #: Monotonic stable-layer-id source (deterministic, P2); 0 = unminted.
        self._next_layer_id = 1
        self.frames: List[Frame] = [Frame([Layer(base, "Background")])]
        self._assign_ids(self.frames[0].layers)

    @classmethod
    def from_buffer(
        cls,
        buffer: PixelBuffer,
        *,
        palette: Optional[Palette] = None,
        name: str = "Imported",
        ppi: float = DEFAULT_DOCUMENT_PPI,
    ) -> "Document":
        """Build a single-frame RGBA document seeded by an existing buffer.

        The returned document has exactly one frame holding one layer whose
        buffer **is** ``buffer`` (same object, not a copy) — the factory the
        image-import path uses so a decoded RGBA :class:`PixelBuffer` (produced
        in ``ui/image_import``) becomes a new canvas tab without ``ui/`` reaching
        into the layer tree (plan §5, REQ-DDI-UI-003). Qt-free.

        Args:
            buffer: The RGBA source buffer; its geometry sizes the document.
            palette: Optional palette for the new document (empty if omitted).
            name: The name of the seeded background layer.
            ppi: Real-size pixels-per-inch (default :data:`DEFAULT_DOCUMENT_PPI`).

        Returns:
            A new :class:`Document` sized to ``buffer``.

        Raises:
            DocumentError: If ``buffer`` is not a :class:`PixelBuffer` or is not
                in :data:`ColorMode.RGBA`.
        """
        if not isinstance(buffer, PixelBuffer):
            raise DocumentError(f"from_buffer needs a PixelBuffer, got {buffer!r}")
        if buffer.mode is not ColorMode.RGBA:
            raise DocumentError(
                f"from_buffer requires an RGBA buffer, got {buffer.mode.value}"
            )
        document = cls(
            buffer.width,
            buffer.height,
            mode=ColorMode.RGBA,
            palette=palette,
            ppi=ppi,
        )
        document.frames = [Frame([Layer(buffer, name)])]
        document._assign_ids(document.frames[0].layers)
        return document

    # -- stable cross-frame layer identity (research Q4 caveat) ----------

    def _mint_id(self) -> int:
        """Return a fresh, monotonically increasing stable layer id (P2)."""
        new_id = self._next_layer_id
        self._next_layer_id += 1
        return new_id

    def _assign_ids(self, nodes: Sequence["LayerNode"]) -> None:
        """Mint stable ids for any node in the subtree whose id is unset (``0``)."""
        for node in nodes:
            if node.layer_id == 0:
                node.layer_id = self._mint_id()
            if isinstance(node, LayerGroup):
                self._assign_ids(node.children)

    # -- layer operations (operate on a chosen frame) --------------------

    def _check_frame(self, frame_index: int) -> Frame:
        if not 0 <= frame_index < len(self.frames):
            raise DocumentError(f"frame index {frame_index} out of range")
        return self.frames[frame_index]

    def _ensure_layer_removable(self, frame: Frame) -> None:
        """Raise unless ``frame`` has more than one top-level layer.

        The single owner of the "never remove a frame's last layer" invariant
        (CF-89 / D-25): both the raw mutator (:meth:`remove_layer`) and the
        reversible factory (:meth:`make_remove_layer_command`) call this one
        check, so a change to the rule cannot go caught by only one of their
        test suites.
        """
        if len(frame.layers) <= 1:
            raise DocumentError("cannot remove the last layer of a frame")

    def _ensure_frame_removable(self) -> None:
        """Raise unless the document has more than one frame.

        The single owner of the "never remove the document's last frame"
        invariant (CF-89 / D-25): both the raw mutator (:meth:`remove_frame`)
        and the reversible factory (:meth:`make_remove_frame_command`) call
        this one check.
        """
        if len(self.frames) <= 1:
            raise DocumentError("cannot remove the last frame")

    def add_layer(self, name: str = "Layer", *, frame_index: int = 0) -> Layer:
        """Append a new empty layer to a frame and return it."""
        frame = self._check_frame(frame_index)
        layer = Layer(PixelBuffer(self.width, self.height, self.mode), name)
        layer.layer_id = self._mint_id()
        frame.layers.append(layer)
        return layer

    def remove_layer(self, layer_index: int, *, frame_index: int = 0) -> "LayerNode":
        """Remove and return a top-level node; refuses to remove the last one."""
        frame = self._check_frame(frame_index)
        self._ensure_layer_removable(frame)
        if not 0 <= layer_index < len(frame.layers):
            raise DocumentError(f"layer index {layer_index} out of range")
        return frame.layers.pop(layer_index)

    def move_layer(
        self, from_index: int, to_index: int, *, frame_index: int = 0
    ) -> None:
        """Reorder a layer within its frame (z-order)."""
        frame = self._check_frame(frame_index)
        n = len(frame.layers)
        if not (0 <= from_index < n) or not (0 <= to_index < n):
            raise DocumentError("layer index out of range")
        layer = frame.layers.pop(from_index)
        frame.layers.insert(to_index, layer)

    # -- frame operations -------------------------------------------------

    def add_frame(self, *, duration_ms: int = DEFAULT_FRAME_DURATION_MS) -> Frame:
        """Append a new frame with a single empty layer."""
        layer = Layer(PixelBuffer(self.width, self.height, self.mode), "Layer")
        layer.layer_id = self._mint_id()
        frame = Frame([layer], duration_ms=duration_ms)
        self.frames.append(frame)
        return frame

    def remove_frame(self, frame_index: int) -> Frame:
        """Remove and return a frame; refuses to remove the last one."""
        self._ensure_frame_removable()
        self._check_frame(frame_index)
        return self.frames.pop(frame_index)

    # -- reversible frame commands (return a history.Command) -------------

    def _clamp_all_tags(self) -> None:
        """Clamp every frame tag's range into the current frame count in place."""
        count = len(self.frames)
        for tag in self.frame_tags:
            clamped = clamp_tag_range(tag, count)
            tag.from_frame = clamped.from_frame
            tag.to_frame = clamped.to_frame

    def _with_tag_clamp(
        self,
        structural_do: "Callable[[], None]",
        structural_undo: "Callable[[], None]",
        label: str,
    ) -> Command:
        """Wrap a frame-structural op so tag ranges stay valid on do and undo.

        After ``structural_do`` changes the frame list, every tag range is
        clamped into the new frame count (REQ-P5-LOGIC-010); ``undo`` reverses the
        structural change **and** restores the exact prior tag ranges. The tag
        count/order is unchanged by add/remove-frame, so the saved ranges realign
        positionally.
        """
        saved = [(tag.from_frame, tag.to_frame) for tag in self.frame_tags]

        def _do() -> None:
            structural_do()
            self._clamp_all_tags()

        def _undo() -> None:
            structural_undo()
            for tag, (from_frame, to_frame) in zip(self.frame_tags, saved):
                tag.from_frame = from_frame
                tag.to_frame = to_frame

        return FunctionCommand(_do, _undo, label=label)

    def make_add_frame_command(
        self, *, after_index: int, duration_ms: int = DEFAULT_FRAME_DURATION_MS
    ) -> Command:
        """Build a command inserting a new empty-layer frame after ``after_index``.

        Implements REQ-P5-LOGIC-004: the new frame carries one empty layer and
        ``duration_ms`` and is inserted immediately after ``after_index``; undo
        removes exactly it. Bounded by ``MAX_FRAMES`` (REQ-P5-LOGIC-014).

        Raises:
            DocumentError: If ``after_index`` is out of range, the document is at
                ``MAX_FRAMES``, or ``duration_ms`` is not a positive int.
        """
        if not isinstance(after_index, int) or isinstance(after_index, bool):
            raise DocumentError(f"after_index must be an int, got {after_index!r}")
        if not 0 <= after_index < len(self.frames):
            raise DocumentError(f"after_index {after_index} out of range")
        if len(self.frames) >= MAX_FRAMES:
            raise DocumentError(f"document already at MAX_FRAMES ({MAX_FRAMES})")
        if (
            not isinstance(duration_ms, int)
            or isinstance(duration_ms, bool)
            or duration_ms <= 0
        ):
            raise DocumentError(
                f"frame duration must be a positive int, got {duration_ms!r}"
            )
        layer = Layer(PixelBuffer(self.width, self.height, self.mode), "Layer")
        layer.layer_id = self._mint_id()
        new_frame = Frame([layer], duration_ms=duration_ms)
        insert_at = after_index + 1

        def _do() -> None:
            self.frames.insert(insert_at, new_frame)

        def _undo() -> None:
            self.frames.remove(new_frame)

        return self._with_tag_clamp(_do, _undo, "add frame")

    def make_remove_frame_command(self, frame_index: int) -> Command:
        """Build a command removing a frame; refuses the last remaining frame.

        Implements REQ-P5-LOGIC-005: undo restores the removed frame at its prior
        index with its exact layer tree and ``duration_ms``; tag ranges are
        clamped on do and restored on undo (REQ-P5-LOGIC-010).

        Raises:
            DocumentError: If only one frame remains, or ``frame_index`` is out of
                range.
        """
        self._ensure_frame_removable()
        frame = self._check_frame(frame_index)

        def _do() -> None:
            self.frames.remove(frame)

        def _undo() -> None:
            self.frames.insert(frame_index, frame)

        return self._with_tag_clamp(_do, _undo, "remove frame")

    def make_move_frame_command(self, from_index: int, to_index: int) -> Command:
        """Build a command reordering a frame (REQ-P5-LOGIC-006, NEW op).

        Undo restores the exact prior order; layers and durations are untouched.

        Raises:
            DocumentError: If either index is out of range.
        """
        count = len(self.frames)
        if not 0 <= from_index < count:
            raise DocumentError(f"from_index {from_index} out of range")
        if not 0 <= to_index < count:
            raise DocumentError(f"to_index {to_index} out of range")
        frame = self.frames[from_index]

        def _do() -> None:
            self.frames.pop(from_index)
            self.frames.insert(to_index, frame)

        def _undo() -> None:
            self.frames.pop(to_index)
            self.frames.insert(from_index, frame)

        return FunctionCommand(_do, _undo, label="move frame")

    def make_duplicate_frame_command(self, frame_index: int) -> Command:
        """Build a command inserting a deep copy of a frame after it (NEW op).

        Implements REQ-P5-LOGIC-007: the copy's full layer tree is copied
        pixel-for-pixel with its ``duration_ms`` and is inserted immediately after
        the source; editing either never affects the other. The copy **preserves**
        its source layers' stable ``layer_id`` s (a duplicated frame shares the
        predecessor's layer *tracks*). Undo removes exactly the copy. Bounded by
        ``MAX_FRAMES``.

        Raises:
            DocumentError: If ``frame_index`` is out of range or the document is at
                ``MAX_FRAMES``.
        """
        frame = self._check_frame(frame_index)
        if len(self.frames) >= MAX_FRAMES:
            raise DocumentError(f"document already at MAX_FRAMES ({MAX_FRAMES})")
        copy_layers = [_copy_node(node, new_ids=False) for node in frame.layers]
        copy = Frame(copy_layers, duration_ms=frame.duration_ms)
        insert_at = frame_index + 1

        def _do() -> None:
            self.frames.insert(insert_at, copy)

        def _undo() -> None:
            self.frames.remove(copy)

        return FunctionCommand(_do, _undo, label="duplicate frame")

    def make_set_frame_duration_command(
        self, frame_index: int, duration_ms: int
    ) -> Command:
        """Build a command setting a frame's ``duration_ms`` (REQ-P5-LOGIC-008).

        Captures the prior value; undo restores it exactly.

        Raises:
            DocumentError: If ``frame_index`` is out of range or ``duration_ms`` is
                not a positive int (never silently coerced).
        """
        frame = self._check_frame(frame_index)
        if (
            not isinstance(duration_ms, int)
            or isinstance(duration_ms, bool)
            or duration_ms <= 0
        ):
            raise DocumentError(
                f"frame duration must be a positive int, got {duration_ms!r}"
            )
        old_duration = frame.duration_ms

        def _do() -> None:
            frame.duration_ms = duration_ms

        def _undo() -> None:
            frame.duration_ms = old_duration

        return FunctionCommand(_do, _undo, label="set frame duration")

    # -- document-level frame tags + reversible ops (REQ-P5-LOGIC-009/010) --

    def _validate_tag_fields(
        self,
        name: str,
        from_frame: int,
        to_frame: int,
        mode: PlaybackMode,
        repeat: int,
        color: str,
    ) -> None:
        """Validate tag fields against the current frame count (build-time)."""
        if not isinstance(name, str):
            raise DocumentError(f"tag name must be a string, got {name!r}")
        if not isinstance(mode, PlaybackMode):
            raise DocumentError(f"tag mode must be a PlaybackMode, got {mode!r}")
        if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 0:
            raise DocumentError(
                f"tag repeat must be a non-negative int, got {repeat!r}"
            )
        if not isinstance(color, str):
            raise DocumentError(f"tag color must be a string, got {color!r}")
        try:
            from_hex(color)
        except ColorError as exc:
            raise DocumentError(f"invalid tag color {color!r}: {exc}") from exc
        try:
            validate_tag_range(from_frame, to_frame, len(self.frames))
        except AnimationError as exc:
            raise DocumentError(str(exc)) from exc

    def make_add_tag_command(
        self,
        name: str,
        from_frame: int,
        to_frame: int,
        *,
        mode: PlaybackMode = PlaybackMode.LOOP,
        repeat: int = 0,
        color: str = "#ff0000ff",
    ) -> Command:
        """Build a command appending a new :class:`FrameTag` (REQ-P5-LOGIC-009/010).

        The range is validated against the current frame count; undo removes the
        tag.

        Raises:
            DocumentError: On an inverted/out-of-range range, a non-PlaybackMode
                mode, a non-int/negative repeat, or a malformed colour.
        """
        self._validate_tag_fields(name, from_frame, to_frame, mode, repeat, color)
        tag = FrameTag(
            name, from_frame, to_frame, mode=mode, repeat=repeat, color=color
        )

        def _do() -> None:
            self.frame_tags.append(tag)

        def _undo() -> None:
            self.frame_tags.remove(tag)

        return FunctionCommand(_do, _undo, label="add tag")

    def make_edit_tag_command(
        self,
        tag_index: int,
        *,
        name: Optional[str] = None,
        from_frame: Optional[int] = None,
        to_frame: Optional[int] = None,
        mode: Optional[PlaybackMode] = None,
        repeat: Optional[int] = None,
        color: Optional[str] = None,
    ) -> Command:
        """Build a command editing a tag in place (REQ-P5-LOGIC-010).

        Only the supplied fields change; the result is validated. Undo restores
        the exact prior tag fields.

        Raises:
            DocumentError: If ``tag_index`` is out of range or the resulting tag
                is invalid.
        """
        if not 0 <= tag_index < len(self.frame_tags):
            raise DocumentError(f"tag index {tag_index} out of range")
        tag = self.frame_tags[tag_index]
        new_name = tag.name if name is None else name
        new_from = tag.from_frame if from_frame is None else from_frame
        new_to = tag.to_frame if to_frame is None else to_frame
        new_mode = tag.mode if mode is None else mode
        new_repeat = tag.repeat if repeat is None else repeat
        new_color = tag.color if color is None else color
        self._validate_tag_fields(
            new_name, new_from, new_to, new_mode, new_repeat, new_color
        )
        old = (
            tag.name,
            tag.from_frame,
            tag.to_frame,
            tag.mode,
            tag.repeat,
            tag.color,
        )

        def _do() -> None:
            tag.name = new_name
            tag.from_frame = new_from
            tag.to_frame = new_to
            tag.mode = new_mode
            tag.repeat = new_repeat
            tag.color = new_color

        def _undo() -> None:
            (
                tag.name,
                tag.from_frame,
                tag.to_frame,
                tag.mode,
                tag.repeat,
                tag.color,
            ) = old

        return FunctionCommand(_do, _undo, label="edit tag")

    def make_remove_tag_command(self, tag_index: int) -> Command:
        """Build a command deleting a tag (REQ-P5-LOGIC-010); undo restores it.

        Raises:
            DocumentError: If ``tag_index`` is out of range.
        """
        if not 0 <= tag_index < len(self.frame_tags):
            raise DocumentError(f"tag index {tag_index} out of range")
        tag = self.frame_tags[tag_index]

        def _do() -> None:
            del self.frame_tags[tag_index]

        def _undo() -> None:
            self.frame_tags.insert(tag_index, tag)

        return FunctionCommand(_do, _undo, label="remove tag")

    # -- reversible tileset / tilemap attach-detach (REQ-P6-LOGIC-012) ----

    def make_add_tileset_command(self, tileset: "Tileset") -> Command:
        """Build a command attaching a tileset to the document (REQ-P6-LOGIC-012).

        Undo detaches exactly it.

        Raises:
            DocumentError: If ``tileset`` is not a :class:`Tileset`.
        """
        if not isinstance(tileset, Tileset):
            raise DocumentError(f"expected a Tileset, got {tileset!r}")

        def _do() -> None:
            self.tilesets.append(tileset)

        def _undo() -> None:
            self.tilesets.remove(tileset)

        return FunctionCommand(_do, _undo, label="add tileset")

    def make_remove_tileset_command(self, tileset_index: int) -> Command:
        """Build a command detaching a tileset, restorable at its exact position.

        Raises:
            DocumentError: If ``tileset_index`` is out of range.
        """
        if not 0 <= tileset_index < len(self.tilesets):
            raise DocumentError(f"tileset index {tileset_index} out of range")
        tileset = self.tilesets[tileset_index]

        def _do() -> None:
            self.tilesets.remove(tileset)

        def _undo() -> None:
            self.tilesets.insert(tileset_index, tileset)

        return FunctionCommand(_do, _undo, label="remove tileset")

    def make_add_tilemap_command(self, tilemap: "Tilemap") -> Command:
        """Build a command attaching a tilemap to the document (REQ-P6-LOGIC-012).

        Undo detaches exactly it.

        Raises:
            DocumentError: If ``tilemap`` is not a :class:`Tilemap`.
        """
        if not isinstance(tilemap, Tilemap):
            raise DocumentError(f"expected a Tilemap, got {tilemap!r}")

        def _do() -> None:
            self.tilemaps.append(tilemap)

        def _undo() -> None:
            self.tilemaps.remove(tilemap)

        return FunctionCommand(_do, _undo, label="add tilemap")

    def make_remove_tilemap_command(self, tilemap_index: int) -> Command:
        """Build a command detaching a tilemap, restorable at its exact position.

        Raises:
            DocumentError: If ``tilemap_index`` is out of range.
        """
        if not 0 <= tilemap_index < len(self.tilemaps):
            raise DocumentError(f"tilemap index {tilemap_index} out of range")
        tilemap = self.tilemaps[tilemap_index]

        def _do() -> None:
            self.tilemaps.remove(tilemap)

        def _undo() -> None:
            self.tilemaps.insert(tilemap_index, tilemap)

        return FunctionCommand(_do, _undo, label="remove tilemap")

    # -- canvas operations ------------------------------------------------

    def resize_canvas(
        self, new_width: int, new_height: int, *, offset_x: int = 0, offset_y: int = 0
    ) -> None:
        """Resize every layer buffer in every frame (non-destructive crop/pad)."""
        for frame in self.frames:
            for layer in _iter_layers(frame.layers):
                layer.buffer = layer.buffer.resize(
                    new_width, new_height, offset_x=offset_x, offset_y=offset_y
                )
                if layer.mask is not None:
                    layer.mask = layer.mask.resize(
                        new_width, new_height, offset_x=offset_x, offset_y=offset_y
                    )
            _invalidate_all_caches(frame.layers)
        self.width = new_width
        self.height = new_height

    # -- node addressing (Phase-4 layer tree) -----------------------------

    def _resolve(
        self, frame: Frame, ref: LayerRef
    ) -> Tuple[List["LayerNode"], int, "LayerNode"]:
        """Return ``(container, index, node)`` for an existing node ``ref``.

        ``ref`` is a top-level index or a path of indices descending through
        nested groups.

        Raises:
            DocumentError: If ``ref`` addresses no existing node.
        """
        path = [ref] if isinstance(ref, int) else list(ref)
        if not path:
            raise DocumentError("empty layer reference")
        container: List["LayerNode"] = frame.layers
        node: Optional["LayerNode"] = None
        for depth, idx in enumerate(path):
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise DocumentError(
                    f"layer reference index must be an int, got {idx!r}"
                )
            if not 0 <= idx < len(container):
                raise DocumentError(f"layer reference {ref!r} out of range")
            node = container[idx]
            if depth < len(path) - 1:
                if not isinstance(node, LayerGroup):
                    raise DocumentError(f"layer reference {ref!r} descends into a leaf")
                container = node.children
        assert node is not None
        return container, path[-1], node

    def _container_and_index(
        self, frame: Frame, addr: LayerRef
    ) -> Tuple[List["LayerNode"], int]:
        """Return ``(container, insertion_index)`` for a destination ``addr``."""
        path = [addr] if isinstance(addr, int) else list(addr)
        if not path:
            raise DocumentError("empty destination reference")
        if len(path) == 1:
            return frame.layers, int(path[0])
        _container, _index, parent = self._resolve(frame, path[:-1])
        if not isinstance(parent, LayerGroup):
            raise DocumentError(f"destination {addr!r} parent is not a group")
        return parent.children, int(path[-1])

    def resolve_layer(self, ref: LayerRef, *, frame_index: int = 0) -> "LayerNode":
        """Return the node addressed by ``ref`` in ``frame_index``."""
        frame = self._check_frame(frame_index)
        return self._resolve(frame, ref)[2]

    def layer_count(self, *, frame_index: int = 0) -> int:
        """Return the number of :class:`Layer` leaves in a frame.

        The count is bounded by ``MAX_LAYERS_PER_FRAME``.
        """
        frame = self._check_frame(frame_index)
        return len(_iter_layers(frame.layers))

    # -- group-cache invalidation (D4) ------------------------------------

    def _chain_for_container(
        self, frame: Frame, container: List["LayerNode"]
    ) -> List["LayerGroup"]:
        """Ancestor groups owning ``container`` (root→owner); ``[]`` if top-level."""
        chain: List["LayerGroup"] = []
        _group_chain(frame.layers, container, chain)
        return chain

    def _invalidating(
        self, command: Command, groups: Sequence["LayerGroup"]
    ) -> Command:
        """Wrap ``command`` so it also clears ``groups`` caches on do **and** undo.

        Invalidation is MANDATORY and fires on both directions — an undo also
        changes the composite, so a stale cache would render wrongly
        (SC-UI-012-2, ADR-0007 §Amendment (T13) D4).
        """
        if not groups:
            return command
        cleared = tuple(groups)

        def _do() -> None:
            command.execute()
            _clear_caches(cleared)

        def _undo() -> None:
            command.undo()
            _clear_caches(cleared)

        return _TracedCommand(
            _do, _undo, label=command.label, trace=command.edit_trace()
        )

    def invalidate_caches(
        self, ref: Optional[LayerRef] = None, *, frame_index: int = 0
    ) -> None:
        """Invalidate cached group composites up the ancestor chain of ``ref``.

        The reversible layer ops in this module already self-invalidate; call
        this from the **pixel-edit** path (``ui/commands.py`` after a
        :class:`~pixelart_creator.logic.history.PixelEdit` on a layer inside a
        group) so the group cache cannot serve a stale flatten for the edited
        region. ``ref=None`` clears every group cache in the frame.
        """
        frame = self._check_frame(frame_index)
        if ref is None:
            _invalidate_all_caches(frame.layers)
            return
        container, _index, node = self._resolve(frame, ref)
        _clear_caches(self._chain_for_container(frame, container))
        if isinstance(node, LayerGroup):
            node._composite_cache = None

    # -- reversible attribute ops (return a history.Command) --------------

    def _attr_command(
        self,
        node: "LayerNode",
        attr: str,
        value: object,
        label: str,
        *,
        frame_index: Optional[int] = None,
    ) -> Command:
        """Build a reversible attribute-set command.

        When ``frame_index`` is given (only the call sites for ``name``,
        ``visible`` and ``locked`` pass it — the attrs
        :data:`~pixelart_creator.logic.convergence.LAYER_ATTRS` actually
        converges, task T8), the returned command reports a
        :class:`~pixelart_creator.logic.edit_trace.LayerAttrTrace` naming
        ``(frame_index, node.layer_id, attr, value)``. ``document.py`` cannot
        import ``logic/convergence.py`` to check membership directly —
        ``convergence.py`` already imports ``document.py``, and the reverse
        edge would close a two-module cycle (Article I §4) — so the call sites
        below encode the membership instead: ``opacity`` (not in T8's scope)
        and ``blend_mode`` (not in ``LAYER_ATTRS`` at all) omit ``frame_index``
        and keep the default, honest, empty trace.
        """
        old = getattr(node, attr)

        def _do() -> None:
            setattr(node, attr, value)

        def _undo() -> None:
            setattr(node, attr, old)

        if frame_index is not None:
            # Only call sites for LAYER_ATTRS-compatible attrs pass frame_index
            # (name/visible/locked), so ``value`` is always str/bool here.
            trace: Tuple[EditTrace, ...] = (
                LayerAttrTrace(
                    frame_index=frame_index,
                    layer_id=node.layer_id,
                    attr=attr,
                    value=cast(LayerAttrValue, value),
                ),
            )
            return _TracedCommand(_do, _undo, label=label, trace=trace)
        return FunctionCommand(_do, _undo, label=label)

    def set_layer_opacity(
        self, ref: LayerRef, value: float, *, frame_index: int = 0
    ) -> Command:
        """Reversibly set a node's opacity (LOGIC-008)."""
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        _validate_opacity(value)
        return self._invalidating(
            self._attr_command(node, "opacity", float(value), "set opacity"),
            self._chain_for_container(frame, container),
        )

    def make_set_metadata_command(self, key: str, value: str) -> Command:
        """Build a command reversibly setting ``self.metadata[key] = value`` (task T10).

        The metadata-setting command's op class (``REQ-P10-UI-025``): reports a
        :class:`~pixelart_creator.logic.edit_trace.MetadataTrace` naming
        ``(key, value)``. No reversible metadata-setting command existed
        before this task — ``Document.metadata`` was a plain dict, written
        directly with no undo support. After T7-T10 all four convergence op
        classes are reachable from a real, reversible edit.

        Raises:
            DocumentError: If ``key`` is not a non-empty ``str``.
        """
        if not isinstance(key, str) or not key:
            raise DocumentError(f"metadata key must be a non-empty str, got {key!r}")
        value = str(value)
        old = self.metadata.get(key)
        had_key = key in self.metadata

        def _do() -> None:
            self.metadata[key] = value

        def _undo() -> None:
            if had_key:
                self.metadata[key] = old  # type: ignore[assignment]
            else:
                self.metadata.pop(key, None)

        trace: Tuple[EditTrace, ...] = (MetadataTrace(key=key, value=value),)
        return _TracedCommand(_do, _undo, label="set metadata", trace=trace)

    def set_layer_name(
        self, ref: LayerRef, value: str, *, frame_index: int = 0
    ) -> Command:
        """Reversibly set a node's display name (LOGIC-008, task T8).

        The name setter's op class (``REQ-P10-UI-025``): ``name`` is one of
        :data:`~pixelart_creator.logic.convergence.LAYER_ATTRS`, so this is the
        fourth of the four commands task T8 wires to a
        :class:`~pixelart_creator.logic.edit_trace.LayerAttrTrace`. No
        reversible name-setting command existed before this task.
        """
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        return self._invalidating(
            self._attr_command(
                node, "name", str(value), "rename layer", frame_index=frame_index
            ),
            self._chain_for_container(frame, container),
        )

    def set_layer_visible(
        self, ref: LayerRef, value: bool, *, frame_index: int = 0
    ) -> Command:
        """Reversibly set a node's visibility (LOGIC-008)."""
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        return self._invalidating(
            self._attr_command(
                node,
                "visible",
                bool(value),
                "set visibility",
                frame_index=frame_index,
            ),
            self._chain_for_container(frame, container),
        )

    def set_layer_locked(
        self, ref: LayerRef, value: bool, *, frame_index: int = 0
    ) -> Command:
        """Reversibly set a node's lock flag (LOGIC-008/010)."""
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        return self._invalidating(
            self._attr_command(
                node, "locked", bool(value), "set lock", frame_index=frame_index
            ),
            self._chain_for_container(frame, container),
        )

    def set_layer_blend_mode(
        self, ref: LayerRef, mode: BlendMode, *, frame_index: int = 0
    ) -> Command:
        """Reversibly set a node's blend mode (LOGIC-008).

        ``blend_mode`` is not one of
        :data:`~pixelart_creator.logic.convergence.LAYER_ATTRS` — the structured
        convergence model does not converge it — so this command keeps the
        default, empty :meth:`~pixelart_creator.logic.history.Command.edit_trace`
        (task T8's own scope: only ``name``/``visible``/``locked`` are traced).
        """
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        _validate_blend_mode(mode)
        return self._invalidating(
            self._attr_command(node, "blend_mode", mode, "set blend mode"),
            self._chain_for_container(frame, container),
        )

    # -- reversible structural ops ----------------------------------------

    def _insert_command(
        self, container: List["LayerNode"], index: int, node: "LayerNode", label: str
    ) -> Command:
        def _do() -> None:
            container.insert(index, node)

        def _undo() -> None:
            _remove_by_identity(container, node)

        return FunctionCommand(_do, _undo, label=label)

    def make_add_layer_command(
        self,
        *,
        ref: Optional[LayerRef] = None,
        name: str = "Layer",
        frame_index: int = 0,
    ) -> Command:
        """Build a command inserting a new empty layer above ``ref`` (LOGIC-009).

        Raises:
            DocumentError: If the frame is already at ``MAX_LAYERS_PER_FRAME``.
        """
        frame = self._check_frame(frame_index)
        if len(_iter_layers(frame.layers)) >= MAX_LAYERS_PER_FRAME:
            raise DocumentError(
                f"frame already at MAX_LAYERS_PER_FRAME ({MAX_LAYERS_PER_FRAME})"
            )
        layer = Layer(PixelBuffer(self.width, self.height, self.mode), name)
        layer.layer_id = self._mint_id()
        if ref is None:
            container: List["LayerNode"] = frame.layers
            insert_index = len(frame.layers)
        else:
            container, index, _node = self._resolve(frame, ref)
            insert_index = index + 1
        return self._invalidating(
            self._insert_command(container, insert_index, layer, "add layer"),
            self._chain_for_container(frame, container),
        )

    def make_remove_layer_command(
        self, ref: LayerRef, *, frame_index: int = 0
    ) -> Command:
        """Build a command removing a node, restorable at its exact position.

        Implements LOGIC-009; refuses to remove the last remaining top-level
        node.
        """
        frame = self._check_frame(frame_index)
        container, index, node = self._resolve(frame, ref)
        if container is frame.layers:
            self._ensure_layer_removable(frame)

        def _do() -> None:
            _remove_by_identity(container, node)

        def _undo() -> None:
            container.insert(index, node)

        return self._invalidating(
            FunctionCommand(_do, _undo, label="remove layer"),
            self._chain_for_container(frame, container),
        )

    def make_move_layer_command(
        self, ref: LayerRef, to: LayerRef, *, frame_index: int = 0
    ) -> Command:
        """Build a command reordering / re-parenting a node (LOGIC-009).

        ``to`` addresses the destination container + insertion index (a
        top-level index, or a path whose last element is the index inside a
        target group).

        When the move is **top-level to top-level** (LOGIC-009 §T9), the
        returned command reports a
        :class:`~pixelart_creator.logic.edit_trace.LayerOrderTrace` naming the
        resulting ``(frame_index, order)``. A move into/out of a nested group
        is not expressible as ``LayerOrderOp`` (the convergence union orders
        only a frame's top level), so it keeps the default, honest, empty
        trace — an expressiveness gap the model already has, not one this
        task introduces.
        """
        frame = self._check_frame(frame_index)
        src_container, src_index, node = self._resolve(frame, ref)
        dst_container, dst_index = self._container_and_index(frame, to)
        if isinstance(node, LayerGroup) and _would_exceed_depth(
            dst_container, frame, node
        ):
            raise DocumentError(
                f"move exceeds MAX_GROUP_NESTING_DEPTH ({MAX_GROUP_NESTING_DEPTH})"
            )

        def _do() -> None:
            _remove_by_identity(src_container, node)
            dst_container.insert(dst_index, node)

        def _undo() -> None:
            _remove_by_identity(dst_container, node)
            src_container.insert(src_index, node)

        groups: List["LayerGroup"] = self._chain_for_container(frame, src_container)
        for group in self._chain_for_container(frame, dst_container):
            if group not in groups:
                groups.append(group)

        trace: Tuple[EditTrace, ...] = ()
        if src_container is frame.layers and dst_container is frame.layers:
            resulting = list(frame.layers)
            _remove_by_identity(resulting, node)
            resulting.insert(dst_index, node)
            trace = (
                LayerOrderTrace(
                    frame_index=frame_index,
                    order=tuple(n.layer_id for n in resulting),
                ),
            )
        return self._invalidating(
            _TracedCommand(_do, _undo, label="move layer", trace=trace), groups
        )

    def make_duplicate_layer_command(
        self, ref: LayerRef, *, frame_index: int = 0
    ) -> Command:
        """Build a command inserting a pixel-for-pixel copy above ``ref``.

        Implements LOGIC-009.

        Raises:
            DocumentError: If duplicating would exceed ``MAX_LAYERS_PER_FRAME``.
        """
        frame = self._check_frame(frame_index)
        container, index, node = self._resolve(frame, ref)
        copy = _copy_node(node, new_ids=True)
        if (
            len(_iter_layers(frame.layers)) + len(_iter_layers([copy]))
            > MAX_LAYERS_PER_FRAME
        ):
            raise DocumentError(
                f"duplicate exceeds MAX_LAYERS_PER_FRAME ({MAX_LAYERS_PER_FRAME})"
            )
        self._assign_ids([copy])
        return self._invalidating(
            self._insert_command(container, index + 1, copy, "duplicate layer"),
            self._chain_for_container(frame, container),
        )

    def make_group_command(
        self, refs: Sequence[LayerRef], *, name: str = "Group", frame_index: int = 0
    ) -> Command:
        """Build a command wrapping the selected top-level nodes in a new group.

        Implements LOGIC-011. All ``refs`` must be top-level nodes of the
        frame. The group is inserted
        at the lowest selected index; children keep their relative order.

        Raises:
            DocumentError: On an empty / non-top-level / out-of-range selection,
                or if grouping would exceed ``MAX_GROUP_NESTING_DEPTH``.
        """
        frame = self._check_frame(frame_index)
        if not refs:
            raise DocumentError("cannot group an empty selection")
        indices: List[int] = []
        for ref in refs:
            if not isinstance(ref, int) or isinstance(ref, bool):
                raise DocumentError("group only supports top-level layer indices")
            if not 0 <= ref < len(frame.layers):
                raise DocumentError(f"group reference {ref} out of range")
            indices.append(ref)
        indices = sorted(set(indices))
        selected = [frame.layers[i] for i in indices]
        group = LayerGroup(name, selected)
        if _group_depth(group) > MAX_GROUP_NESTING_DEPTH:
            raise DocumentError(
                f"group exceeds MAX_GROUP_NESTING_DEPTH ({MAX_GROUP_NESTING_DEPTH})"
            )
        insert_at = indices[0]

        def _do() -> None:
            for node in selected:
                _remove_by_identity(frame.layers, node)
            frame.layers.insert(insert_at, group)

        def _undo() -> None:
            _remove_by_identity(frame.layers, group)
            for i, node in zip(indices, selected):
                frame.layers.insert(i, node)

        return FunctionCommand(_do, _undo, label="group layers")

    def make_ungroup_command(self, ref: LayerRef, *, frame_index: int = 0) -> Command:
        """Build a command dissolving a group, promoting its children in place.

        Implements LOGIC-011.
        """
        frame = self._check_frame(frame_index)
        container, index, node = self._resolve(frame, ref)
        if not isinstance(node, LayerGroup):
            raise DocumentError("ungroup target is not a group")
        children = list(node.children)

        def _do() -> None:
            _remove_by_identity(container, node)
            for offset, child in enumerate(children):
                container.insert(index + offset, child)

        def _undo() -> None:
            for child in children:
                _remove_by_identity(container, child)
            container.insert(index, node)

        return self._invalidating(
            FunctionCommand(_do, _undo, label="ungroup layers"),
            self._chain_for_container(frame, container),
        )

    # -- reversible cross-frame cel operations (REQ-P5-LOGIC-016) ---------

    def make_move_cel_command(
        self,
        *,
        source_frame_index: int,
        source_track_id: int,
        dest_frame_index: int,
        dest_track_id: int,
    ) -> Command:
        """Build a command moving a cel between (frame, track) cells.

        Implements ``REQ-P5-LOGIC-016``'s move: the drawing on track
        ``source_track_id`` in frame ``source_frame_index`` is removed from
        its source cell and placed on track ``dest_track_id`` in frame
        ``dest_frame_index`` — the moved node keeps its own ``layer_id``
        (a cross-track move is a move, never a merge). After the move the
        source cell is **empty**, a first-class outcome
        (``logic/track_table.py``), never a blank layer. If the destination
        cell is occupied, its node is replaced and captured so undo restores
        it exactly; if it is empty, the moved node is appended to the
        destination frame's top-level layers. Exactly one reversible command;
        undo restores both cells' exact prior state.

        Args:
            source_frame_index: The source cel's frame index.
            source_track_id: The source cel's track (``layer_id``).
            dest_frame_index: The destination cell's frame index.
            dest_track_id: The destination cell's track (``layer_id``) — an
                existing track's id, exactly as read from
                ``logic/track_table.py``'s ``TrackRow.layer_id``.

        Returns:
            The reversible :class:`Command`.

        Raises:
            DocumentError: If either frame index is out of range, the source
                cell is empty, either endpoint node is a
                :class:`LayerGroup` (a cel is a leaf drawing), the move would
                leave the source frame with no top-level node at all (the
                shipped "never remove a frame's last layer" invariant,
                CF-89/D-25, applies to this removal exactly as it does to
                ``make_remove_layer_command``), the drop is onto the cel's
                own cell (refused totally, a no-op the caller must not
                push), or an empty destination would exceed
                ``MAX_LAYERS_PER_FRAME``.
        """
        if source_frame_index == dest_frame_index and source_track_id == dest_track_id:
            raise DocumentError("cannot move a cel onto its own cell")
        src_frame = self._check_frame(source_frame_index)
        dst_frame = self._check_frame(dest_frame_index)
        found = _find_by_track_id(src_frame.layers, source_track_id)
        if found is None:
            raise DocumentError(
                f"no cel on track {source_track_id} in frame {source_frame_index}"
            )
        src_container, src_index, node = found
        if isinstance(node, LayerGroup):
            raise DocumentError("cel move operates on a leaf drawing, not a group")
        if src_container is src_frame.layers:
            self._ensure_layer_removable(src_frame)

        dst_found = _find_by_track_id(dst_frame.layers, dest_track_id)
        prior: Optional["LayerNode"]
        if dst_found is not None:
            dst_container, dst_index, prior = dst_found
            if isinstance(prior, LayerGroup):
                raise DocumentError("destination cell holds a group, not a drawing")
        else:
            if len(_iter_layers(dst_frame.layers)) + 1 > MAX_LAYERS_PER_FRAME:
                raise DocumentError(
                    f"move exceeds MAX_LAYERS_PER_FRAME ({MAX_LAYERS_PER_FRAME})"
                )
            dst_container, dst_index, prior = (
                dst_frame.layers,
                len(dst_frame.layers),
                None,
            )

        def _do() -> None:
            _remove_by_identity(src_container, node)
            if prior is not None:
                _remove_by_identity(dst_container, prior)
            dst_container.insert(dst_index, node)

        def _undo() -> None:
            _remove_by_identity(dst_container, node)
            if prior is not None:
                dst_container.insert(dst_index, prior)
            src_container.insert(src_index, node)

        groups = self._chain_for_container(src_frame, src_container)
        for group in self._chain_for_container(dst_frame, dst_container):
            if group not in groups:
                groups.append(group)
        return self._invalidating(FunctionCommand(_do, _undo, label="move cel"), groups)

    def make_copy_cel_command(
        self,
        *,
        source_frame_index: int,
        source_track_id: int,
        dest_frame_index: int,
        dest_track_id: int,
    ) -> Command:
        """Build a command copying a cel to another (frame, track) cell.

        Implements ``REQ-P5-LOGIC-016``'s copy: the source cel is left
        untouched, and an **independent** deep copy (editing one never
        affects the other — the CL-9 linked-cel boundary stays deferred) is
        placed on track ``dest_track_id`` in frame ``dest_frame_index``.
        **The copy joins the destination track**: its ``layer_id`` is set to
        ``dest_track_id`` (an existing track, defined by shared
        ``layer_id`` — ``REQ-P5-LOGIC-015``), never a freshly minted id — the
        shipped ``make_add_layer_command`` mints a fresh id and is therefore
        not reusable here (plan §3.2). If the destination cell is occupied,
        its node is replaced and captured so undo restores it exactly; if it
        is empty, the copy is appended to the destination frame's top-level
        layers. Exactly one reversible command.

        Args:
            source_frame_index: The source cel's frame index.
            source_track_id: The source cel's track (``layer_id``).
            dest_frame_index: The destination cell's frame index.
            dest_track_id: The destination cell's track (``layer_id``) — an
                existing track's id, exactly as read from
                ``logic/track_table.py``'s ``TrackRow.layer_id``.

        Returns:
            The reversible :class:`Command`.

        Raises:
            DocumentError: If either frame index is out of range, the source
                cell is empty, either endpoint node is a
                :class:`LayerGroup`, the drop is onto the cel's own cell
                (refused totally), or an empty destination would exceed
                ``MAX_LAYERS_PER_FRAME``.
        """
        if source_frame_index == dest_frame_index and source_track_id == dest_track_id:
            raise DocumentError("cannot copy a cel onto its own cell")
        src_frame = self._check_frame(source_frame_index)
        dst_frame = self._check_frame(dest_frame_index)
        found = _find_by_track_id(src_frame.layers, source_track_id)
        if found is None:
            raise DocumentError(
                f"no cel on track {source_track_id} in frame {source_frame_index}"
            )
        _src_container, _src_index, node = found
        if isinstance(node, LayerGroup):
            raise DocumentError("cel copy operates on a leaf drawing, not a group")

        dst_found = _find_by_track_id(dst_frame.layers, dest_track_id)
        prior: Optional["LayerNode"]
        if dst_found is not None:
            dst_container, dst_index, prior = dst_found
            if isinstance(prior, LayerGroup):
                raise DocumentError("destination cell holds a group, not a drawing")
        else:
            if len(_iter_layers(dst_frame.layers)) + 1 > MAX_LAYERS_PER_FRAME:
                raise DocumentError(
                    f"copy exceeds MAX_LAYERS_PER_FRAME ({MAX_LAYERS_PER_FRAME})"
                )
            dst_container, dst_index, prior = (
                dst_frame.layers,
                len(dst_frame.layers),
                None,
            )

        copy_node = _copy_node(node, new_ids=False)
        copy_node.layer_id = dest_track_id  # joins the destination track

        def _do() -> None:
            if prior is not None:
                _remove_by_identity(dst_container, prior)
            dst_container.insert(dst_index, copy_node)

        def _undo() -> None:
            _remove_by_identity(dst_container, copy_node)
            if prior is not None:
                dst_container.insert(dst_index, prior)

        groups = self._chain_for_container(dst_frame, dst_container)
        return self._invalidating(FunctionCommand(_do, _undo, label="copy cel"), groups)

    def make_create_cel_command(
        self,
        *,
        frame_index: int,
        track_id: int,
        name: str = "Layer",
    ) -> Command:
        """Build a command creating a new cel in an empty (frame, track) cell.

        Implements ``REQ-P5-LOGIC-016``'s third entry point — the "create a
        cel here" affordance of ``REQ-P5-UI-031`` — as the same conceptual
        operation as :meth:`make_copy_cel_command` with an **empty prior
        state**: no source cel exists, so a fresh, empty
        :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` is placed
        on the existing track ``track_id`` in frame ``frame_index``. The new
        node **joins** ``track_id`` — its ``layer_id`` is set to the given,
        already-minted track id, exactly as a copy joins its destination
        track (plan §3.2) — it never mints a fresh id, so this is not
        reusable as :meth:`make_add_layer_command`, which always starts a
        new track. Exactly one reversible command; undo removes the created
        node and restores the cell to empty.

        Args:
            frame_index: The destination cel's frame index.
            track_id: The destination track's id (``layer_id``) — an
                existing track's id, exactly as read from
                ``logic/track_table.py``'s ``TrackRow.layer_id``.
            name: The new layer's display name.

        Returns:
            The reversible :class:`Command`.

        Raises:
            DocumentError: If ``frame_index`` is out of range, the target
                cell is already occupied (a first-class outcome that must be
                refused totally, never silently overwritten — overwriting a
                cel is ``make_move_cel_command`` / ``make_copy_cel_command``'s
                job, gated by ``REQ-P5-UI-033`` upstream), or creating the
                cel would exceed ``MAX_LAYERS_PER_FRAME``.
        """
        frame = self._check_frame(frame_index)
        if _find_by_track_id(frame.layers, track_id) is not None:
            raise DocumentError(
                f"track {track_id} already occupied in frame {frame_index}"
            )
        if len(_iter_layers(frame.layers)) >= MAX_LAYERS_PER_FRAME:
            raise DocumentError(
                f"create exceeds MAX_LAYERS_PER_FRAME ({MAX_LAYERS_PER_FRAME})"
            )
        layer = Layer(PixelBuffer(self.width, self.height, self.mode), name)
        layer.layer_id = track_id  # joins the existing track, never minted

        def _do() -> None:
            frame.layers.append(layer)

        def _undo() -> None:
            _remove_by_identity(frame.layers, layer)

        return self._invalidating(
            FunctionCommand(_do, _undo, label="create cel"),
            self._chain_for_container(frame, frame.layers),
        )

    # -- reversible mask / reference / smart ops --------------------------

    def make_attach_mask_command(
        self, ref: LayerRef, mask: PixelBuffer, *, frame_index: int = 0
    ) -> Command:
        """Build a command attaching ``mask`` to a node (LOGIC-012)."""
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        if not isinstance(mask, PixelBuffer):
            raise DocumentError(f"mask must be a PixelBuffer, got {mask!r}")
        if mask.width != self.width or mask.height != self.height:
            raise DocumentError("mask geometry must match the canvas")
        return self._invalidating(
            self._attr_command(node, "mask", mask, "attach mask"),
            self._chain_for_container(frame, container),
        )

    def make_detach_mask_command(
        self, ref: LayerRef, *, frame_index: int = 0
    ) -> Command:
        """Build a command detaching a node's mask (LOGIC-012)."""
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        return self._invalidating(
            self._attr_command(node, "mask", None, "detach mask"),
            self._chain_for_container(frame, container),
        )

    def make_set_reference_command(
        self, ref: LayerRef, value: bool, *, frame_index: int = 0
    ) -> Command:
        """Build a command toggling a node's reference flag (LOGIC-013)."""
        frame = self._check_frame(frame_index)
        container, _index, node = self._resolve(frame, ref)
        return self._invalidating(
            self._attr_command(node, "reference", bool(value), "set reference"),
            self._chain_for_container(frame, container),
        )

    def make_smart_layer_command(
        self, source_ref: LayerRef, *, name: str = "Smart", frame_index: int = 0
    ) -> Command:
        """Build a command inserting a smart layer above its source layer.

        The smart layer mirrors ``source_ref`` (LOGIC-014).

        Raises:
            DocumentError: If the source is a group, or the frame is at
                ``MAX_LAYERS_PER_FRAME``.
        """
        frame = self._check_frame(frame_index)
        container, index, node = self._resolve(frame, source_ref)
        if not isinstance(node, Layer):
            raise DocumentError("a smart layer can only mirror a leaf layer")
        if len(_iter_layers(frame.layers)) >= MAX_LAYERS_PER_FRAME:
            raise DocumentError(
                f"frame already at MAX_LAYERS_PER_FRAME ({MAX_LAYERS_PER_FRAME})"
            )
        smart = Layer(
            PixelBuffer(self.width, self.height, self.mode),
            name,
            smart_source=node,
        )
        smart.layer_id = self._mint_id()
        return self._invalidating(
            self._insert_command(container, index + 1, smart, "create smart layer"),
            self._chain_for_container(frame, container),
        )

    # -- colour-mode conversion (ADR-0008: Document is the single mode authority)

    def make_convert_to_indexed_command(
        self, palette: Palette, *, metric: str = "distance_sq"
    ) -> Command:
        """Build a reversible RGBA→INDEXED whole-document conversion (ADR-0008 D3/D4).

        Colour mode is document-wide, so this converts **every frame** and flips
        ``Document.mode`` to :data:`ColorMode.INDEXED` in one
        :class:`~pixelart_creator.logic.history.FunctionCommand` — the buffers and
        the mode never move independently, so persistence / compositor / UI can
        never observe a mixed-mode state (D1/D2). Pixel conversion is delegated to
        :func:`pixelart_creator.logic.palette_ops.to_indexed`.

        Per frame (enforcing the invariant *INDEXED frame = exactly one indexed
        layer*):

        - a **single leaf layer** is indexed in place (its buffer only), preserving
          its pixels exactly;
        - a **multi-layer / grouped** frame is **flattened** with
          :func:`pixelart_creator.logic.blend.composite_stack` to one RGBA buffer,
          then that flat buffer is indexed (D4 flatten-then-index).

        The result replaces each frame's whole ``layers`` list with a single
        :class:`Layer`. ``execute`` snapshots each ``frame.layers`` list reference
        and the prior ``Document.mode`` and swaps the lists wholesale — the original
        nodes are **never mutated** — so ``undo`` restores the full original tree
        (multi-layer RGBA, groups/masks/opacity/blend/references intact) exactly and
        ``apply ∘ undo = identity`` (REQ-P3-LOGIC-017). Returned **unapplied** for
        ``ui/commands.py`` to wrap as one ``QUndoCommand``.

        Raises:
            DocumentError: If the document is not currently RGBA.
            IndexedModeError: If a source buffer is not RGBA or ``metric`` is
                unknown.
            PaletteError: If ``palette`` is empty.
        """
        if self.mode is not ColorMode.RGBA:
            raise DocumentError(
                "convert-to-indexed requires an RGBA document, "
                f"got {self.mode.value}"
            )
        # Eager conversion so an invalid palette / metric / buffer raises at build
        # time (mirrors the module's build-time validation pattern).
        new_frame_layers: List[List["LayerNode"]] = []
        for frame in self.frames:
            nodes = frame.layers
            if len(nodes) == 1 and isinstance(nodes[0], Layer):
                source = nodes[0]
                indexed = palette_ops.to_indexed(source.buffer, palette, metric=metric)
                name = source.name
            else:
                flat = composite_stack(nodes, self.width, self.height)
                indexed = palette_ops.to_indexed(flat, palette, metric=metric)
                name = nodes[-1].name if nodes else "Layer"
            new_frame_layers.append([Layer(indexed, name)])
        for layers in new_frame_layers:
            self._assign_ids(layers)
        return self._make_mode_command(
            new_frame_layers, ColorMode.INDEXED, "convert to indexed"
        )

    def make_convert_to_rgba_command(self, palette: Palette) -> Command:
        """Build a reversible INDEXED→RGBA whole-document conversion (ADR-0008 D4).

        The inverse of :meth:`make_convert_to_indexed_command`: each frame's single
        indexed layer becomes one RGBA layer via
        :func:`pixelart_creator.logic.palette_ops.to_rgba`, and ``Document.mode``
        flips to :data:`ColorMode.RGBA` in the same
        :class:`~pixelart_creator.logic.history.FunctionCommand`. ``undo`` restores
        the indexed single-layer lists and ``mode = INDEXED`` exactly (list
        references swapped wholesale, originals never mutated). Returned
        **unapplied**.

        Raises:
            DocumentError: If the document is not currently indexed.
            IndexedModeError: If a source buffer is not indexed.
            PaletteError: If ``palette`` is empty or a buffer index is out of range.
        """
        if self.mode is not ColorMode.INDEXED:
            raise DocumentError(
                "convert-to-rgba requires an indexed document, "
                f"got {self.mode.value}"
            )
        new_frame_layers: List[List["LayerNode"]] = []
        for frame in self.frames:
            leaves = iter_layers(frame.layers)
            source = leaves[0]  # invariant: an indexed frame holds exactly one layer
            rgba_buffer = palette_ops.to_rgba(source.buffer, palette)
            new_frame_layers.append([Layer(rgba_buffer, source.name)])
        for layers in new_frame_layers:
            self._assign_ids(layers)
        return self._make_mode_command(
            new_frame_layers, ColorMode.RGBA, "convert to RGBA"
        )

    def _make_mode_command(
        self,
        new_frame_layers: List[List["LayerNode"]],
        new_mode: ColorMode,
        label: str,
    ) -> Command:
        """Assemble the reversible whole-document mode swap (ADR-0008 D3/D4).

        Snapshots each frame's current ``layers`` list reference and the prior
        ``Document.mode``; on ``execute`` swaps in ``new_frame_layers`` and sets
        ``new_mode``; on ``undo`` restores the saved lists and mode. Group caches
        are dropped on **both** directions since the whole tree is replaced (D4).
        """
        saved_frame_layers = [frame.layers for frame in self.frames]
        saved_mode = self.mode
        frames = self.frames

        def _do() -> None:
            for frame, new_layers in zip(frames, new_frame_layers):
                frame.layers = new_layers
            self.mode = new_mode

        def _undo() -> None:
            for frame, old_layers in zip(frames, saved_frame_layers):
                frame.layers = old_layers
                _invalidate_all_caches(frame.layers)
            self.mode = saved_mode

        return FunctionCommand(_do, _undo, label=label)

    def __repr__(self) -> str:
        """Return a debug representation of the document's geometry and frames."""
        return (
            f"Document({self.width}x{self.height}, {self.mode.value}, "
            f"{len(self.frames)} frames)"
        )


# --------------------------------------------------------------------------- #
# Module-level tree helpers                                                   #
# --------------------------------------------------------------------------- #


def _remove_by_identity(container: List["LayerNode"], node: "LayerNode") -> None:
    """Remove ``node`` from ``container`` by identity (not equality)."""
    for i, existing in enumerate(container):
        if existing is node:
            del container[i]
            return
    raise DocumentError("node is not in the expected container")


def _find_by_track_id(
    nodes: List["LayerNode"], track_id: int
) -> Optional[Tuple[List["LayerNode"], int, "LayerNode"]]:
    """Depth-first search of ``nodes`` for the node with ``layer_id == track_id``.

    Returns ``(container, index, node)`` for the owning list and position, or
    ``None`` if no node in the subtree carries that id. Used by the cross-frame
    cel operations (``REQ-P5-LOGIC-016``) to address a ``(frame, track)`` cell
    by track id rather than by structural path.
    """
    for index, node in enumerate(nodes):
        if node.layer_id == track_id:
            return nodes, index, node
        if isinstance(node, LayerGroup):
            found = _find_by_track_id(node.children, track_id)
            if found is not None:
                return found
    return None


def _copy_node(node: "LayerNode", *, new_ids: bool = True) -> "LayerNode":
    """Return a deep, independent copy of a layer / group node.

    With ``new_ids=True`` (layer duplication) the copy's ``layer_id`` is left
    unminted (``0``) for the :class:`Document` to assign a fresh track id; with
    ``new_ids=False`` (frame duplication) the copy **preserves** the source's
    ``layer_id`` so a duplicated frame shares its predecessor's layer *tracks*
    (research Q4 caveat, plan §5).
    """
    copy_id = 0 if new_ids else node.layer_id
    if isinstance(node, LayerGroup):
        return LayerGroup(
            node.name,
            [_copy_node(c, new_ids=new_ids) for c in node.children],
            opacity=node.opacity,
            visible=node.visible,
            locked=node.locked,
            blend_mode=node.blend_mode,
            mask=node.mask.copy() if node.mask is not None else None,
            reference=node.reference,
            layer_id=copy_id,
        )
    return Layer(
        node.buffer.copy(),
        node.name,
        opacity=node.opacity,
        visible=node.visible,
        locked=node.locked,
        blend_mode=node.blend_mode,
        mask=node.mask.copy() if node.mask is not None else None,
        reference=node.reference,
        smart_source=node.smart_source,
        layer_id=copy_id,
    )


def _would_exceed_depth(
    dst_container: List["LayerNode"], frame: Frame, node: "LayerNode"
) -> bool:
    """Return ``True`` if inserting ``node`` exceeds the nesting bound.

    Checks whether adding ``node`` to ``dst_container`` would push the frame
    past ``MAX_GROUP_NESTING_DEPTH``.
    """
    parent_depth = _container_depth(frame.layers, dst_container, 0)
    if parent_depth is None:
        return False
    return parent_depth + _group_depth(node) + 1 > MAX_GROUP_NESTING_DEPTH


def _container_depth(
    nodes: List["LayerNode"], target: List["LayerNode"], depth: int
) -> Optional[int]:
    """Depth of the group whose ``children`` list is ``target`` (0 = top level)."""
    if nodes is target:
        return depth
    for node in nodes:
        if isinstance(node, LayerGroup):
            found = _container_depth(node.children, target, depth + 1)
            if found is not None:
                return found
    return None
