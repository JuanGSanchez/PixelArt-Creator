"""T-15 (AGT-06 audit) — viewport tile-culling contract AT the 8K scene size.

``test_canvas_scene.py::test_sc_ui_003_1_draw_background_only_exposed_rect``
proves the exposed-rect cull on a small (64x64) scene. This module drives the
SAME ``CanvasScene.drawBackground`` with a small exposed rect on a scene sized
to the actual S1 ceiling (``MAX_CANVAS_WIDTH`` x ``MAX_CANVAS_HEIGHT``,
7680x4320) -- proving the cull holds at the real 8K scale, not just as a
small-canvas proxy (F2/F3, S1).

INSTRUMENT SUPERSEDED, CONTRACT UNCHANGED (canvas-grid-semantics job,
traceability.md §2): this test used to COUNT ``QPainter.fillRect`` calls (one
per culled tile, under the old per-cell painter) as a proxy for painted area.
The checker background now paints through a cached texture ``QBrush`` in ONE
``fillRect`` per region (``_fill_checker``), so a call count no longer
measures anything a renderer could regress on -- it would pass even if
``drawBackground`` painted the entire 8K scene in a single call. No
requirement supersedes the CULL itself; only this test's instrument moved.
It now measures painted AREA directly and carries the original 1/100 bound
across unchanged: the union of every painted rectangle stays bounded by the
exposed rect (intersected with the document canvas) and is a vanishing
fraction of the full 8K scene's area.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH


def test_t15_8k_scene_paints_far_fewer_tiles_than_the_full_scene(
    make_scene, monkeypatch
):
    """T-15: a small exposed rect on an 8K scene paints << the full-scene area.

    The AREA union of everything ``drawBackground`` painted is (a) bounded by
    the exposed rect intersected with the document canvas -- independent of
    the scene's own size, matching the original cull contract -- and (b) a
    vanishing fraction (< 1/100, the bound carried across from the superseded
    call-count instrument) of the full 8K scene's area.
    """
    scene = make_scene(MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)

    painted: list[QRectF] = []
    original_fill_rect = QPainter.fillRect

    def _recording_fill_rect(self, rect, brush_or_colour):
        # QRectF(...) normalises a QRect argument too, so every fill -- exact
        # rect type aside -- lands in the same units for the area maths below.
        painted.append(QRectF(rect))
        return original_fill_rect(self, rect, brush_or_colour)

    monkeypatch.setattr(QPainter, "fillRect", _recording_fill_rect)

    # A small on-screen exposed rect (one modest viewport's worth), well inside
    # the 8K scene bounds -- the culling scenario a real zoomed-in view exercises.
    exposed = QRectF(4000, 2000, 200, 150)
    image = QImage(64, 64, QImage.Format.Format_RGBA8888)
    painter = QPainter(image)
    scene.drawBackground(painter, exposed)
    painter.end()

    assert painted, "drawBackground painted nothing to measure"

    canvas_rect = QRectF(0, 0, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    bound = exposed.intersected(canvas_rect)

    # Every painted rectangle stays inside the exposed rect ∩ canvas -- no
    # fill reaches past the area drawBackground was actually asked to paint,
    # regardless of the 8K scene's own size (F2's contract, carried across).
    tolerance = 1e-6
    for rect in painted:
        assert rect.left() >= bound.left() - tolerance
        assert rect.top() >= bound.top() - tolerance
        assert rect.right() <= bound.right() + tolerance
        assert rect.bottom() <= bound.bottom() + tolerance

    # Painted area: summing each rect's area is a safe UPPER bound on the true
    # painted union (rects may overlap, e.g. the workspace fill and the
    # checker fill here cover the same bound) -- it can only overstate the
    # cull's footprint, never understate it, so this assertion is at least as
    # strict as an exact union-area computation would be.
    painted_area = sum(r.width() * r.height() for r in painted)
    full_scene_area = float(MAX_CANVAS_WIDTH) * float(MAX_CANVAS_HEIGHT)

    # The load-bearing contract, carried across unchanged from the superseded
    # call-count instrument: painted area is a vanishing fraction of the full
    # 8K scene's area.
    assert painted_area < full_scene_area / 100
    assert full_scene_area > 1000  # sanity: the 8K scene really is large
