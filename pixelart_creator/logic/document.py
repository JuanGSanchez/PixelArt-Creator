"""Document model — the project state tree (zero Qt, S11).

Mirrors the Architecture state manager: ``Document -> frames[] -> layers[] ->
PixelBuffer`` plus a shared :class:`~pixelart_creator.logic.palette.Palette` and
metadata. Phase 1 uses a single frame with one or more layers; Phases 4/5 build
layer groups/blend-modes and the animation timeline on this same tree without
reshaping it.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pixelart_creator.logic.constants import DEFAULT_FRAME_DURATION_MS
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

#: Default animation frame duration (ms). Re-exported from
#: :mod:`pixelart_creator.logic.constants` (single source, S12) so existing
#: default-arg call sites and importers keep working.
__all__ = ["DEFAULT_FRAME_DURATION_MS", "DocumentError", "Layer", "Frame", "Document"]


class DocumentError(ValueError):
    """Raised on an invalid document structure or operation."""


class Layer:
    """A single named pixel layer with opacity / visibility / lock flags."""

    __slots__ = ("name", "buffer", "_opacity", "visible", "locked")

    def __init__(
        self,
        buffer: PixelBuffer,
        name: str = "Layer",
        *,
        opacity: float = 1.0,
        visible: bool = True,
        locked: bool = False,
    ) -> None:
        self.name = name
        self.buffer = buffer
        self.visible = visible
        self.locked = locked
        self._opacity = 1.0
        self.opacity = opacity  # validates via setter

    @property
    def opacity(self) -> float:
        """Layer opacity in ``0.0..1.0``."""
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise DocumentError(f"opacity must be a number, got {value!r}")
        if value < 0.0 or value > 1.0:
            raise DocumentError(f"opacity {value} out of range 0.0..1.0")
        self._opacity = float(value)

    def __repr__(self) -> str:
        return f"Layer({self.name!r}, {self.buffer!r})"


class Frame:
    """One animation frame: a stack of layers plus a display duration."""

    __slots__ = ("layers", "duration_ms")

    def __init__(
        self,
        layers: Optional[List[Layer]] = None,
        duration_ms: int = DEFAULT_FRAME_DURATION_MS,
    ) -> None:
        if duration_ms <= 0:
            raise DocumentError(f"frame duration must be positive, got {duration_ms}")
        self.layers: List[Layer] = list(layers) if layers else []
        self.duration_ms = duration_ms

    def __repr__(self) -> str:
        return f"Frame({len(self.layers)} layers, {self.duration_ms}ms)"


class Document:
    """A pixel-art project: canvas geometry, palette, and a frame/layer tree."""

    __slots__ = ("width", "height", "mode", "palette", "frames", "metadata")

    def __init__(
        self,
        width: int,
        height: int,
        *,
        mode: ColorMode = ColorMode.RGBA,
        palette: Optional[Palette] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Create a document with one frame holding one empty background layer."""
        base = PixelBuffer(width, height, mode)
        self.width = base.width
        self.height = base.height
        self.mode = mode
        self.palette = palette if palette is not None else Palette()
        self.metadata: Dict[str, str] = dict(metadata) if metadata else {}
        self.frames: List[Frame] = [Frame([Layer(base, "Background")])]

    # -- layer operations (operate on a chosen frame) --------------------

    def _check_frame(self, frame_index: int) -> Frame:
        if not 0 <= frame_index < len(self.frames):
            raise DocumentError(f"frame index {frame_index} out of range")
        return self.frames[frame_index]

    def add_layer(self, name: str = "Layer", *, frame_index: int = 0) -> Layer:
        """Append a new empty layer to a frame and return it."""
        frame = self._check_frame(frame_index)
        layer = Layer(PixelBuffer(self.width, self.height, self.mode), name)
        frame.layers.append(layer)
        return layer

    def remove_layer(self, layer_index: int, *, frame_index: int = 0) -> Layer:
        """Remove and return a layer; refuses to remove the last one."""
        frame = self._check_frame(frame_index)
        if len(frame.layers) <= 1:
            raise DocumentError("cannot remove the last layer of a frame")
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
        frame = Frame(
            [Layer(PixelBuffer(self.width, self.height, self.mode), "Layer")],
            duration_ms=duration_ms,
        )
        self.frames.append(frame)
        return frame

    def remove_frame(self, frame_index: int) -> Frame:
        """Remove and return a frame; refuses to remove the last one."""
        if len(self.frames) <= 1:
            raise DocumentError("cannot remove the last frame")
        self._check_frame(frame_index)
        return self.frames.pop(frame_index)

    # -- canvas operations ------------------------------------------------

    def resize_canvas(
        self, new_width: int, new_height: int, *, offset_x: int = 0, offset_y: int = 0
    ) -> None:
        """Resize every layer buffer in every frame (non-destructive crop/pad)."""
        for frame in self.frames:
            for layer in frame.layers:
                layer.buffer = layer.buffer.resize(
                    new_width, new_height, offset_x=offset_x, offset_y=offset_y
                )
        self.width = new_width
        self.height = new_height

    def __repr__(self) -> str:
        return (
            f"Document({self.width}x{self.height}, {self.mode.value}, "
            f"{len(self.frames)} frames)"
        )
