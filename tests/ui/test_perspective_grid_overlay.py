"""Perspective grid overlay acceptance tests (REQ-P9-UI-005).

Scenario SC-UI-005-1: the overlay renders guide lines from the pure construction
and the cursor snaps to the nearest guide within tolerance via the pure snap
(no snap beyond tolerance); the overlay computes no geometry of its own
(Article I). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPicture
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from pixelart_creator.logic.grids import (
    PerspectiveConfig,
    VanishingPoint,
    perspective_snap,
)
from pixelart_creator.ui.perspective_grid_overlay import Perspective_Grid_Overlay


def _config():
    # One finite VP on a mid-canvas horizon (a simple 1-point setup).
    return PerspectiveConfig(
        mode=1,
        vanishing_points=(VanishingPoint(position=(50.0, 50.0)),),
        horizon_y=50.0,
    )


def _overlay(rect=(0, 0, 100, 100)):
    cfg = _config()
    return Perspective_Grid_Overlay(QRectF(*rect), cfg), cfg


# --- SC-UI-005-1: snap delegates to the pure logic geometry ----------------- #


def test_sc_ui_005_1_snap_within_tolerance_delegates_to_logic():
    """SC-UI-005-1: overlay.snap == logic.perspective_snap when within tolerance."""
    overlay, cfg = _overlay()
    anchor = (0.0, 0.0)
    # A cursor near the anchor->VP ray, within a generous tolerance.
    result = overlay.snap(24.0, 26.0, anchor, 50.0)
    assert result == perspective_snap(24.0, 26.0, anchor, cfg, 50.0)
    assert result is not None


def test_sc_ui_005_1_no_snap_beyond_tolerance():
    """SC-UI-005-1: beyond tolerance the overlay returns None (no snap)."""
    overlay, cfg = _overlay()
    anchor = (0.0, 0.0)
    # Far from every vanishing line, tiny tolerance -> no snap.
    result = overlay.snap(0.0, 90.0, anchor, 0.5)
    assert result is None
    assert result == perspective_snap(0.0, 90.0, anchor, cfg, 0.5)


def test_sc_ui_005_1_snap_is_deterministic():
    """SC-UI-005-1: repeating the same snap yields the identical result."""
    overlay, _cfg = _overlay()
    anchor = (10.0, 10.0)
    first = overlay.snap(30.0, 31.0, anchor, 40.0)
    assert overlay.snap(30.0, 31.0, anchor, 40.0) == first


def test_sc_ui_005_1_renders_guide_lines():
    """SC-UI-005-1: paint strokes the guide fan + horizon (draw calls > 0)."""
    overlay, _cfg = _overlay()
    picture = QPicture()
    painter = QPainter(picture)
    option = QStyleOptionGraphicsItem()
    option.exposedRect = QRectF(0, 0, 100, 100)
    overlay.paint(painter, option, None)
    painter.end()
    assert not picture.boundingRect().isNull()


def test_sc_ui_005_1_set_config_reroutes_snap():
    """SC-UI-005-1: replacing the config reroutes snap to the new construction."""
    overlay, _cfg = _overlay()
    new_cfg = PerspectiveConfig(
        mode=1,
        vanishing_points=(VanishingPoint(position=(80.0, 20.0)),),
        horizon_y=20.0,
    )
    overlay.set_config(new_cfg)
    assert overlay.config() is new_cfg
    anchor = (0.0, 0.0)
    assert overlay.snap(40.0, 10.0, anchor, 50.0) == perspective_snap(
        40.0, 10.0, anchor, new_cfg, 50.0
    )
