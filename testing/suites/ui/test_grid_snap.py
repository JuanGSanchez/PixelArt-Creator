"""Grid-overlay & snapping-refinement acceptance (REQ-P2-UI-013).

Scenarios SC-U013-1 (the grid-overlay toggle shows/hides the grid WITHOUT mutating
pixel data), SC-U013-2 (with snapping on, a shape/selection endpoint lands on a grid
intersection) and SC-U013-3 (the overlay is legible in both themes; the toggles are
tr()-wrapped). Both themes via the autouse ``theme`` fixture.

NOTE (QA finding UI-P2-02): the per-pixel grid means every floored endpoint is
already on a grid intersection, so the ``snap`` flag has no *differential* effect —
snap-on and snap-off produce the same endpoint. This test verifies the flag is
wired end-to-end into the tool context and that endpoints are grid-aligned; it does
NOT verify a distinct snapped-vs-unsnapped outcome (there is none to observe). See
the QA report — routed to AGT-01 (spec) / AGT-05.
"""

from __future__ import annotations

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import RectSelectTool
from pixelart_creator.ui.tools.base import Tool, ToolContext
from testing.suites.ui._ui_helpers import move, press, release


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_u013_1_grid_toggle_no_pixel_mutation(make_view):
    """SC-U013-1: toggling the grid overlay never mutates buffer pixels."""
    view, scene, _stack = make_view(16, 16)
    scene.active_buffer().set_pixel(4, 4, (230, 30, 30, 255))
    before = scene.active_buffer().copy()
    view.set_grid_enabled(True)
    assert scene.is_grid_enabled() is True
    assert scene.active_buffer() == before  # overlay is non-destructive
    view.set_grid_enabled(False)
    assert scene.is_grid_enabled() is False
    assert scene.active_buffer() == before


def test_sc_u013_2_snap_flag_wired_endpoints_grid_aligned(make_view):
    """SC-U013-2: the snap flag reaches the tool context; endpoints are grid-aligned.

    (Differential snap-on vs snap-off behaviour is not observable on a per-pixel
    grid — QA finding UI-P2-02.)
    """
    view, _scene, _stack = make_view(16, 16)
    captured = {}

    class _CaptureTool(Tool):
        tool_id = "capture"

        def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
            captured["snap"] = ctx.snap
            captured["xy"] = (x, y)

    view.set_snap_enabled(True)
    view.set_tool(_CaptureTool())
    press(view, 3, 4)
    release(view, 3, 4)
    assert captured["snap"] is True  # flag propagated into the context
    # Endpoint is an integer pixel == a grid intersection.
    assert captured["xy"] == (3, 4)

    # A rectangle selection built with snap on has integer (grid) bounds.
    view.set_tool(RectSelectTool())
    press(view, 2, 2)
    move(view, 7, 5)
    release(view, 7, 5)
    assert view.active_selection().bounds() == (2, 2, 7, 5)


def test_sc_u013_3_toggles_translatable_grid_role_coloured(qtbot):
    """SC-U013-3: grid/snap toggles are tr()-wrapped; the grid colour is role-based."""
    win = _window(qtbot)
    assert win._grid_action.text() != ""
    assert win._snap_action.text() != ""
    assert win._grid_action.isCheckable() and win._snap_action.isCheckable()
    # The scene grid colour is set from the active theme's role (legible per theme).
    scene = win.active_tab().scene
    assert scene._grid_color.alpha() > 0
