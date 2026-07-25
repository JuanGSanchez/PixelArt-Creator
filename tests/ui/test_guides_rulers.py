"""Guides & rulers overlay acceptance tests (REQ-P9-UI-003).

Scenario SC-UI-003-1: the ruler shows a coordinate readout (from the pure
logic/guides tick+readout geometry) and the cursor snaps to a created guide via
the pure guide snap; the overlay computes no snap/tick geometry itself
(Article I). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF

from pixelart_creator.logic.constants import DEFAULT_SNAP_TOLERANCE_PX
from pixelart_creator.logic.guides import (
    Guide,
    GuideOrientation,
    coordinate_readout,
    screen_tolerance_to_doc,
    snap_guides,
)
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay


def _controller(make_view, w=64, h=64):
    view, scene, stack = make_view(w, h)
    controller = Guides_Rulers_Overlay(view, scene, QRectF(0, 0, w, h))
    controller.set_enabled(True)
    return controller, view, scene, stack


# --- SC-UI-003-1: cursor snaps to guides via the pure snap ------------------ #


def test_sc_ui_003_1_snap_delegates_to_logic_guide_snap(make_view):
    """SC-UI-003-1: controller.snap == logic.snap_guides for a created guide."""
    controller, view, _scene, _stack = _controller(make_view)
    item = controller.overlay_item()
    item.add_guide(GuideOrientation.VERTICAL, 20.0)
    zoom = view.zoom()  # 1.0 under prepare_for_click
    tol_doc = screen_tolerance_to_doc(DEFAULT_SNAP_TOLERANCE_PX, zoom)
    expected = snap_guides(22.0, 5.0, item.guides(), tol_doc)
    assert controller.snap(22.0, 5.0) == expected
    assert controller.snap(22.0, 5.0) == (20.0, 5.0)  # x snapped, y untouched


def test_sc_ui_003_1_no_snap_beyond_tolerance(make_view):
    """SC-UI-003-1: a cursor beyond tolerance is not snapped (x unchanged)."""
    controller, _view, _scene, _stack = _controller(make_view)
    controller.overlay_item().add_guide(GuideOrientation.VERTICAL, 20.0)
    # 40 is far outside the 8-doc-px tolerance of the guide at x=20.
    assert controller.snap(40.0, 5.0) == (40.0, 5.0)


def test_sc_ui_003_1_ruler_coordinate_readout_from_logic(make_view):
    """SC-UI-003-1: the ruler readout equals logic.coordinate_readout of the cursor."""
    controller, view, _scene, _stack = _controller(make_view)
    ruler = controller.horizontal_ruler()
    ruler.set_cursor_readout(30.0, 10.0)
    expected_x, _expected_y = coordinate_readout(30.0, 10.0, view.zoom(), (0.0, 0.0))
    assert ruler._cursor_doc == expected_x


def test_sc_ui_003_1_dragging_from_ruler_creates_a_guide(make_view):
    """SC-UI-003-1: the guide-creation signal wires a new guide onto the overlay."""
    controller, _view, _scene, _stack = _controller(make_view)
    ruler = controller.horizontal_ruler()
    before = len(controller.overlay_item().guides())
    ruler.guideCreationRequested.emit(GuideOrientation.HORIZONTAL, 12.0)
    guides = controller.overlay_item().guides()
    assert len(guides) == before + 1
    assert Guide(GuideOrientation.HORIZONTAL, 12.0) in guides


def test_sc_ui_003_1_toggle_shows_rulers_and_overlay(make_view):
    """SC-UI-003-1: enabling/disabling the aid toggles the overlay + rulers."""
    controller, _view, _scene, _stack = _controller(make_view)
    assert controller.is_enabled() is True
    assert controller.overlay_item().isVisible() is True
    # The QGraphicsItem flag is window-independent; rulers use isHidden() (which
    # is meaningful headless, unlike isVisible() that needs a shown top-level).
    assert controller.horizontal_ruler().isHidden() is False
    controller.set_enabled(False)
    assert controller.is_enabled() is False
    assert controller.overlay_item().isVisible() is False
    assert controller.horizontal_ruler().isHidden() is True
