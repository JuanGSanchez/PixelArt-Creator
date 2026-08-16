"""T-15 (AGT-06 audit) — viewport tile-culling contract AT the 8K scene size.

``test_canvas_scene.py::test_sc_ui_003_1_draw_background_only_exposed_rect``
proves the exposed-rect cull on a small (64x64) scene. This module drives the
SAME ``CanvasScene.drawBackground`` with a small exposed rect on a scene sized
to the actual S1 ceiling (``MAX_CANVAS_WIDTH`` x ``MAX_CANVAS_HEIGHT``,
7680x4320) and counts the tiles actually painted (``QPainter.fillRect`` calls
via ``_paint_checker_tiles``) against the full-scene tile count — proving the
cull holds at the real 8K scale, not just as a small-canvas proxy (F2/F3, S1).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from pixelart_creator.logic.constants import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    TILE_BUFFER,
    TILE_SIZE,
)


def test_t15_8k_scene_paints_far_fewer_tiles_than_the_full_scene(
    make_scene, monkeypatch
):
    """T-15: a small exposed rect on an 8K scene paints << the full-scene tile count."""
    scene = make_scene(MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)

    painted: list[QRectF] = []
    original_fill_rect = QPainter.fillRect

    def _counting_fill_rect(self, rect, colour):
        painted.append(rect)
        return original_fill_rect(self, rect, colour)

    monkeypatch.setattr(QPainter, "fillRect", _counting_fill_rect)

    # A small on-screen exposed rect (one modest viewport's worth), well inside
    # the 8K scene bounds — the culling scenario a real zoomed-in view exercises.
    exposed = QRectF(4000, 2000, 200, 150)
    image = QImage(64, 64, QImage.Format.Format_RGBA8888)
    painter = QPainter(image)
    scene.drawBackground(painter, exposed)
    painter.end()

    painted_tiles = len(painted)
    full_scene_tiles = math.ceil(MAX_CANVAS_WIDTH / TILE_SIZE) * math.ceil(
        MAX_CANVAS_HEIGHT / TILE_SIZE
    )

    # The exact tile count the exposed-rect loop should paint (TILE_BUFFER ring
    # included), independent of the scene's own size (F2's contract).
    expected = (math.ceil(exposed.right() / TILE_SIZE) + TILE_BUFFER) - (
        math.floor(exposed.left() / TILE_SIZE) - TILE_BUFFER
    )
    expected *= (math.ceil(exposed.bottom() / TILE_SIZE) + TILE_BUFFER) - (
        math.floor(exposed.top() / TILE_SIZE) - TILE_BUFFER
    )
    assert painted_tiles == expected

    # The load-bearing contract: painted tiles are a vanishing fraction of the
    # full 8K scene's tile count (culling holds AT the real S1 ceiling).
    assert painted_tiles < full_scene_tiles / 100
    assert full_scene_tiles > 1000  # sanity: the 8K scene really is large
