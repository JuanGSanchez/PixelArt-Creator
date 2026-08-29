"""Lasso selection-tool acceptance (REQ-P2-UI-005).

Scenarios SC-U005-1 (a freehand drag sets an auto-closed lasso selection) and
SC-U005-2 (the freehand path preview is visible during the drag). Both themes via
the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGraphicsPolygonItem

from pixelart_creator.ui.tools import LassoTool
from testing.suites.ui._ui_helpers import move, press, release


def test_sc_u005_1_drag_sets_autoclosed_lasso(make_view):
    """SC-U005-1: a freehand triangular drag fills its interior (auto-closed)."""
    view, _scene, _stack = make_view(16, 16)
    view.set_tool(LassoTool())
    # A triangle traced freehand; the path auto-closes last -> first vertex.
    press(view, 2, 2)
    move(view, 10, 2)
    move(view, 6, 10)
    release(view, 6, 10)
    mask = view.active_selection()
    assert mask is not None
    assert not mask.is_empty
    assert mask.is_selected(6, 5)  # an interior pixel is filled
    assert not mask.is_selected(0, 0)  # a clearly-outside pixel is not


def test_sc_u005_2_path_preview_visible_during_drag(make_view):
    """SC-U005-2: the freehand path preview is visible during the drag."""
    view, scene, _stack = make_view(16, 16)
    view.set_tool(LassoTool())
    press(view, 2, 2)
    move(view, 8, 3)
    move(view, 5, 9)
    # A polygon preview item exists mid-drag (cleared on release/commit).
    assert isinstance(scene._shape_preview, QGraphicsPolygonItem)
    release(view, 5, 9)
    assert scene._shape_preview is None
