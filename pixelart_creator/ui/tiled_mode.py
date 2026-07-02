"""Tiled-drawing mode wiring (REQ-P2-UI-015).

Single wiring point for the seamless-pattern tiled mode: it toggles the scene's
``TILED_PREVIEW_REPEAT`` x ``TILED_PREVIEW_REPEAT`` repeating preview (the same
arrangement ``logic.tiled.preview_tiling`` describes) and the view's torus-wrap
paint flag, so edits wrap across tile edges via ``logic.tiled.make_tiled_command``
(routed through the pencil controller). Presentation/wiring only — the wrap and
preview *data* live in ``logic/tiled`` (Article I / S11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pixelart_creator.logic.pixel_buffer import PixelBuffer
from pixelart_creator.logic.tiled import preview_tiling

if TYPE_CHECKING:  # avoid an import cycle at runtime (view imports tools -> base)
    from pixelart_creator.ui.canvas_scene import CanvasScene
    from pixelart_creator.ui.canvas_view import Canvas_View


def set_tiled_mode(scene: "CanvasScene", view: "Canvas_View", enabled: bool) -> None:
    """Enable/disable tiled mode on a scene + view pair.

    Turns on the scene's 3x3 repeating preview and the view's torus-wrap paint
    flag together, so both the preview and the committed edits agree.
    """
    scene.set_tiled_preview(enabled)
    view.set_tiled(enabled)


def build_preview(buffer: PixelBuffer) -> PixelBuffer:
    """Return the ``logic.tiled.preview_tiling`` arrangement of ``buffer``.

    Exposed for consumers/tests that want the repeating-tile buffer directly; the
    interactive scene renders the same arrangement without materialising the full
    (repeat x repeat) buffer at 8K (perf; AGT-10).
    """
    return preview_tiling(buffer)
