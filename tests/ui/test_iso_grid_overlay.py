"""Isometric grid overlay acceptance tests (REQ-P9-UI-004).

Scenario SC-UI-004-1: the overlay renders from the pure logic/grids transform and
the cursor snaps to the nearest vertex via the pure snap (the overlay computes no
geometry of its own — Article I). Plus the DIR-1 LOD paint-skip gate and DIR-2
exposed-rect cull (REQ-P9-UI-011 render-budget lever). Both themes via the autouse
``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPicture, QTransform
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from pixelart_creator.logic.constants import ISO_GRID_MIN_ON_SCREEN_EDGE_PX
from pixelart_creator.logic.grids import IsoGridConfig, iso_snap_vertex
from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay


def _overlay(tile_width=32, rect=(0, 0, 100, 100)):
    cfg = IsoGridConfig(tile_width=tile_width)
    return Iso_Grid_Overlay(QRectF(*rect), cfg), cfg


def _paint_to_picture(overlay, scale, exposed):
    """Paint the overlay through a QPicture at ``scale`` and return the picture.

    A QPicture records paint primitives, so ``boundingRect().isNull()`` is True iff
    the overlay issued zero draw calls — a precise probe for the LOD paint-skip."""
    picture = QPicture()
    painter = QPainter(picture)
    painter.setWorldTransform(QTransform.fromScale(scale, scale))
    option = QStyleOptionGraphicsItem()
    option.exposedRect = QRectF(*exposed)
    overlay.paint(painter, option, None)
    painter.end()
    return picture


# --- SC-UI-004-1: snap delegates to the pure logic geometry ----------------- #


def test_sc_ui_004_1_snap_delegates_to_logic_vertex():
    """SC-UI-004-1: overlay.snap == logic.iso_snap_vertex (no UI-side geometry)."""
    overlay, cfg = _overlay(tile_width=32)
    for sx, sy in [(0.0, 0.0), (13.3, 7.1), (48.0, 25.0), (-9.0, 100.0)]:
        assert overlay.snap(sx, sy) == iso_snap_vertex(sx, sy, cfg)


def test_sc_ui_004_1_snap_is_deterministic():
    """SC-UI-004-1: repeated snap of the same cursor returns the identical vertex."""
    overlay, _cfg = _overlay(tile_width=32)
    first = overlay.snap(21.7, 9.4)
    assert overlay.snap(21.7, 9.4) == first


def test_sc_ui_004_1_set_config_reroutes_snap():
    """SC-UI-004-1: replacing the config reroutes snap to the new pure transform."""
    overlay, _cfg = _overlay(tile_width=32)
    new_cfg = IsoGridConfig(tile_width=64)
    overlay.set_config(new_cfg)
    assert overlay.config() is new_cfg
    assert overlay.snap(30.0, 30.0) == iso_snap_vertex(30.0, 30.0, new_cfg)


# --- REQ-P9-UI-011 / DIR-1: LOD paint-skip gate ----------------------------- #


def test_iso_lod_skips_paint_below_threshold():
    """DIR-1: paint() early-returns (0 draw calls) when tile edge < the min px.

    tile_width=32, scale=0.5 -> on-screen edge 16 px < ISO_GRID_MIN_ON_SCREEN_EDGE_PX
    (32) -> the lattice is too dense to read, so the overlay paints nothing."""
    overlay, _cfg = _overlay(tile_width=32)
    assert 32 * 0.5 < ISO_GRID_MIN_ON_SCREEN_EDGE_PX  # premise of the gate
    picture = _paint_to_picture(overlay, scale=0.5, exposed=(0, 0, 100, 100))
    assert (
        picture.boundingRect().isNull()
    ), "expected zero draw calls below the LOD gate"


def test_iso_draws_above_threshold():
    """DIR-1: above the LOD gate the overlay strokes the lattice (draw calls > 0)."""
    overlay, _cfg = _overlay(tile_width=32)
    assert 32 * 2.0 >= ISO_GRID_MIN_ON_SCREEN_EDGE_PX
    picture = _paint_to_picture(overlay, scale=2.0, exposed=(0, 0, 100, 100))
    assert not picture.boundingRect().isNull(), "expected the lattice to be drawn"


def test_iso_exposed_rect_cull_honored():
    """DIR-2: an exposedRect disjoint from the item rect culls to zero draws.

    The overlay intersects exposedRect with its own rect; an exposed viewport that
    does not overlap the document produces an empty region and paints nothing —
    proving rasterisation is clipped to the exposed rect."""
    overlay, _cfg = _overlay(tile_width=32, rect=(0, 0, 100, 100))
    # Above the LOD gate, but the exposed viewport is entirely outside the doc rect.
    picture = _paint_to_picture(overlay, scale=2.0, exposed=(1000, 1000, 10, 10))
    assert (
        picture.boundingRect().isNull()
    ), "exposed-rect cull must skip off-screen area"
