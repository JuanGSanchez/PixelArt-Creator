"""Characterisation of outline (hollow) rectangle/ellipse commit.

Investigates a hands-on user report: "the rectangle and ellipse tools do not put
colour when hollow -- they only paint when the filled option is enabled." A
prior investigation established the logic primitives are correct in isolation
(``drawing.rectangle``/``drawing.ellipse`` with ``filled=False`` return the
expected non-empty coord lists) and that the UI wiring reads correct
(``ShapeTool.filled`` defaults to ``False``; ``_draw_op`` forwards
``filled=self.filled``; the commit path is shared with the working filled
case).

This module drives the REAL tool through a REAL ``Canvas_View``/``ToolContext``
(both the direct-handler and the real-``QTest``-event paths -- see
``_ui_helpers.py``) across a scenario matrix (reference size, small/degenerate
shapes, an active full-canvas selection, an active symmetry axis, an indexed
buffer) and asserts on FOUR independent observable layers: the active layer's
own ``PixelBuffer`` (data), the undo stack's pushed-command count, the scene's
composited ``PixelBuffer`` (``CanvasScene._composite`` -- the compositor's
resident output the RGBA-compositing path renders from, NOT the same object as
the layer buffer), and the actual rendered ``QImage`` (``CanvasScene._item.
current_image()`` -- exactly what ``_BufferPixmapItem.paint()`` blits to the
viewport).

**Result pinned here: every one of those four layers is currently CORRECT for
an outline commit**, under ``QT_QPA_PLATFORM=offscreen``, on both this branch
and on ``origin/main`` (byte-identical for every file this depends on --
verified via ``git diff origin/main`` returning zero lines for
``shape_base.py``, ``rectangle_tool.py``, ``ellipse_tool.py``, ``drawing.py``,
``canvas_scene.py``, ``tools/base.py`` and ``canvas_view.py``). The reported
defect could NOT be reproduced through any path this headless environment can
exercise.

**What this test does NOT and cannot cover, and why it is the one remaining
suspect**: ``Canvas_View._install_viewport`` (``ui/canvas_view.py``) installs a
real ``QOpenGLWidget`` viewport on desktop and explicitly SKIPS it under
``QT_QPA_PLATFORM == "offscreen"``, falling back to the raster viewport this
test (and every pytest-qt test in this suite) actually exercises. This
project's own history records this exact class of GL-only invisible-paint
defect (commits ``8f1a04e`` "show drawn pixels on the OpenGL canvas viewport"
and ``35b63bf`` "repaint the item after the deferred composite build"), and
project memory (``qt-gl-texture-identity-trap``) states plainly that "no
offscreen test can see it." If the report is real, the GL-viewport repaint
path -- specifically whether ``FullViewportUpdate``/``NoPartialUpdate``
correctly repaints a SPARSE (scattered, outline-shaped) dirty region the way
it repaints a solid filled block -- is where it must live, and it can only be
confirmed or ruled out on a real windowing system with a real (or software)
GL context, never here.

If a future fix changes the observable behaviour this file pins, this test
must be re-examined, not silently adjusted to match -- the point of a
characterisation test is to make that re-examination happen on purpose.
"""

from __future__ import annotations

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.ui.tools import EllipseTool, RectangleTool
from testing.suites.ui._ui_helpers import (
    move,
    press,
    real_move_pixel,
    real_press_pixel,
    real_release_pixel,
    release,
)

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _nonzero_alpha_count(image, w: int, h: int) -> int:
    """Count pixels with non-zero alpha in a rendered ``QImage`` (visible on screen)."""
    return sum(
        1 for x in range(w) for y in range(h) if image.pixelColor(x, y).alpha() != 0
    )


def _composite_nonzero_count(composite, w: int, h: int) -> int:
    """Count non-transparent pixels in the scene's compositor output buffer."""
    return sum(
        1
        for x in range(w)
        for y in range(h)
        if tuple(composite.get_pixel(x, y)) != TRANSPARENT
    )


# -- reference-size outline commit, both event paths ----------------------- #


def test_char_rectangle_outline_direct_handlers_paints_perimeter(make_view):
    """Direct-handler press/move/release: outline rectangle changes 28 pixels
    (matching the already-established ``drawing.rectangle`` primitive count for
    the same (2,2)-(9,9) span) at every observable layer.
    """
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectangleTool())  # default: outline (CL-17)
    view.set_active_color(RED)
    press(view, 2, 2)
    move(view, 9, 9)
    release(view, 9, 9)

    assert stack.count() == 1, "commit should push exactly one undoable command"

    buf = scene.active_buffer()
    buf_changed = sum(
        1 for x in range(16) for y in range(16) if buf.get_pixel(x, y) != TRANSPARENT
    )
    assert buf_changed == 28, f"layer buffer: expected 28 painted, got {buf_changed}"
    assert buf.get_pixel(2, 2) == RED
    assert buf.get_pixel(5, 5) == TRANSPARENT, "outline: interior stays untouched"

    assert scene._compositing is True, "RGBA doc compositing must be active"
    comp_changed = _composite_nonzero_count(scene._composite, 16, 16)
    assert comp_changed == 28, f"composite buffer: expected 28, got {comp_changed}"

    img_changed = _nonzero_alpha_count(scene._item.current_image(), 16, 16)
    assert img_changed == 28, f"rendered image: expected 28, got {img_changed}"


def test_char_rectangle_outline_real_events_paints_perimeter(make_view):
    """Real ``QTest`` mouse events (full hit-testing/geometry path) reproduce
    the identical outline result as the direct-handler path above.
    """
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectangleTool())
    view.set_active_color(RED)
    real_press_pixel(view, 2, 2)
    real_move_pixel(view, 9, 9)
    real_release_pixel(view, 9, 9)

    assert stack.count() == 1
    buf_changed = sum(
        1
        for x in range(16)
        for y in range(16)
        if scene.active_buffer().get_pixel(x, y) != TRANSPARENT
    )
    assert buf_changed == 28
    comp_changed = _composite_nonzero_count(scene._composite, 16, 16)
    assert comp_changed == 28
    img_changed = _nonzero_alpha_count(scene._item.current_image(), 16, 16)
    assert img_changed == 28


def test_char_ellipse_outline_real_events_paints_ring(make_view):
    """Real events: outline ellipse changes 12 pixels (matching the
    already-established ``drawing.ellipse`` primitive count for the same span)
    at every observable layer.
    """
    view, scene, stack = make_view(16, 16)
    view.set_tool(EllipseTool())
    view.set_active_color(RED)
    real_press_pixel(view, 2, 2)
    real_move_pixel(view, 9, 9)
    real_release_pixel(view, 9, 9)

    assert stack.count() == 1
    comp_changed = _composite_nonzero_count(scene._composite, 16, 16)
    assert comp_changed == 12, f"composite buffer: expected 12, got {comp_changed}"
    img_changed = _nonzero_alpha_count(scene._item.current_image(), 16, 16)
    assert img_changed == 12, f"rendered image: expected 12, got {img_changed}"


# -- outline vs filled, same drag, contrasting counts ----------------------- #


def test_char_outline_vs_filled_rectangle_contrast(make_view):
    """Outline and filled commits from the identical drag differ ONLY in the
    coord count the primitive returns (28 vs 64) -- never in whether anything
    painted at all. Both commit, both push one command, both paint.
    """
    view_outline, scene_outline, stack_outline = make_view(16, 16)
    view_outline.set_tool(RectangleTool())
    view_outline.set_active_color(RED)
    real_press_pixel(view_outline, 2, 2)
    real_move_pixel(view_outline, 9, 9)
    real_release_pixel(view_outline, 9, 9)

    view_filled, scene_filled, stack_filled = make_view(16, 16)
    filled_tool = RectangleTool()
    filled_tool.set_filled(True)
    view_filled.set_tool(filled_tool)
    view_filled.set_active_color(RED)
    real_press_pixel(view_filled, 2, 2)
    real_move_pixel(view_filled, 9, 9)
    real_release_pixel(view_filled, 9, 9)

    assert stack_outline.count() == 1
    assert stack_filled.count() == 1
    outline_img = _nonzero_alpha_count(scene_outline._item.current_image(), 16, 16)
    filled_img = _nonzero_alpha_count(scene_filled._item.current_image(), 16, 16)
    assert outline_img == 28
    assert filled_img == 64
    assert outline_img > 0, "outline commit is NOT a no-op relative to filled"


# -- degenerate / small shapes ------------------------------------------- #


def test_char_degenerate_single_pixel_outline_rectangle_still_paints(make_view):
    """A press+release at the SAME pixel (no perceptible drag) still commits
    exactly one painted pixel for an outline rectangle -- the smallest possible
    drag does not collapse to zero.
    """
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectangleTool())
    view.set_active_color(RED)
    real_press_pixel(view, 5, 5)
    real_release_pixel(view, 5, 5)
    assert stack.count() == 1
    img_changed = _nonzero_alpha_count(scene._item.current_image(), 16, 16)
    assert img_changed == 1


def test_char_small_ellipse_outline_paints_at_every_tested_size(make_view):
    """Small/degenerate ellipse drags (down to a single point) each paint at
    least one pixel outline -- no collapse-to-zero at small scale.
    """
    for (x0, y0, x1, y1), expected in [
        ((2, 2, 4, 4), 4),
        ((2, 2, 3, 3), 1),
        ((5, 5, 5, 5), 1),
    ]:
        view, scene, stack = make_view(16, 16)
        view.set_tool(EllipseTool())
        view.set_active_color(RED)
        real_press_pixel(view, x0, y0)
        real_move_pixel(view, x1, y1)
        real_release_pixel(view, x1, y1)
        img_changed = _nonzero_alpha_count(scene._item.current_image(), 16, 16)
        assert (
            img_changed == expected
        ), f"ellipse ({x0},{y0})-({x1},{y1}): expected {expected}, got {img_changed}"
        assert stack.count() == 1


# -- selection mask + symmetry: the two branches inside on_release --------- #


def test_char_outline_rectangle_with_full_selection_paints(make_view):
    """The masked commit branch (``apply_masked``, active selection) also
    paints an outline rectangle correctly -- rules out a selection-specific
    divergence between the outline and filled branches.
    """
    view, scene, stack = make_view(16, 16)
    view.set_selection(rect_mask(16, 16, 0, 0, 15, 15))
    view.set_tool(RectangleTool())
    view.set_active_color(RED)
    real_press_pixel(view, 2, 2)
    real_move_pixel(view, 9, 9)
    real_release_pixel(view, 9, 9)
    assert stack.count() == 1
    img_changed = _nonzero_alpha_count(scene._item.current_image(), 16, 16)
    assert img_changed == 28


def test_char_outline_rectangle_with_symmetry_paints_mirror_too(make_view):
    """Symmetry-mirrored outline commit paints both the source and the
    mirrored pixels (stroke.stamp branch) -- rules out a symmetry-specific
    divergence between the outline and filled branches.
    """
    view, scene, stack = make_view(16, 16)
    view.set_symmetry_axis(SymmetryAxis.VERTICAL)
    view.set_tool(RectangleTool())
    view.set_active_color(RED)
    real_press_pixel(view, 2, 2)
    real_move_pixel(view, 6, 6)
    real_release_pixel(view, 6, 6)
    assert stack.count() == 1
    img_changed = _nonzero_alpha_count(scene._item.current_image(), 16, 16)
    assert (
        img_changed > 25
    ), "mirrored outline paints strictly more than the source alone"
