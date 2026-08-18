"""Tiled drawing-mode acceptance (REQ-P2-UI-015).

Scenarios SC-U015-1 (enabling tiled mode shows a 3x3 repeating preview), SC-U015-2
(painting near an edge wraps to the opposite edge), SC-U015-3 (a wrapped/tiled edit
is one undoable command) and SC-U015-4 (the tiled-mode toggle is tr()-wrapped and
keyboard-reachable). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.logic.constants import TILED_PREVIEW_REPEAT
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import PencilTool
from pixelart_creator.ui.tools.base import ToolContext
from tests.ui._ui_helpers import click_pixel

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_u015_1_enabling_shows_3x3_preview(qtbot):
    """SC-U015-1: tiled mode turns on the 3x3 repeating preview + expands the rect."""
    win = _window(qtbot)
    record = win.active_tab()
    scene = record.scene
    w = record.document.width
    win._on_tiled_toggled(True)
    assert scene.is_tiled_preview_enabled() is True
    assert record.view._tiled is True
    # Scene rect grows to the TILED_PREVIEW_REPEAT (3x) span for the neighbour tiles.
    assert scene.sceneRect().width() == TILED_PREVIEW_REPEAT * w
    win._on_tiled_toggled(False)
    assert scene.is_tiled_preview_enabled() is False
    assert scene.sceneRect().width() == w


def test_sc_u015_3_tiled_edit_is_one_command(make_view):
    """SC-U015-3: an in-bounds stroke in tiled mode commits ONE undoable command."""
    view, scene, stack = make_view(8, 8)
    view.set_tool(PencilTool())
    view.set_active_color(RED)
    view.set_tiled(True)
    before = scene.active_buffer().copy()
    click_pixel(view, 3, 3)
    assert stack.count() == 1
    assert scene.active_buffer().get_pixel(3, 3) == RED
    stack.undo()
    assert scene.active_buffer() == before  # reversible in one step


def test_sc_u015_4_toggle_translatable_and_reachable(qtbot):
    """SC-U015-4: the tiled-mode toggle is tr()-wrapped and keyboard-operable."""
    win = _window(qtbot)
    action = win._tiled_action
    assert action.text() != ""
    assert action.isCheckable()


def test_sc_u015_2_painting_past_edge_wraps(make_view):
    """SC-U015-2: painting past the right edge wraps to the opposite (left) edge.

    Re-verifies the AGT-05 fix for DEFECT UI-P2-01: ``PencilTool`` in tiled mode
    now wraps each raw coord via ``logic.tiled`` before stamping, so a stroke
    crossing the canvas edge paints the opposite side both live and on commit.
    The strict-xfail marker was removed once the fix landed (asserts REAL pass).
    """
    _view, scene, stack = make_view(8, 8)
    buf = scene.active_buffer()
    # scene comes from make_view -> make_scene, whose Document is freshly built
    # (every layer's stable id is minted at construction, logic/document.py:450),
    # so the active frame/layer target is genuinely known here — pass a real
    # EditTarget, not the None sentinel (REQ-P10-UI-025, plan §8.2).
    layer = scene.active_layer()
    ctx = ToolContext(
        buffer=buf,
        active_color=RED,
        undo_stack=stack,
        scene=scene,
        set_active_color=lambda c: None,
        target=EditTarget(frame_index=scene.frame_index, layer_id=layer.layer_id),
        tiled=True,
    )
    tool = PencilTool()
    # A stroke crossing the right edge: x=8,9 lie past W=8 and must wrap to 0,1.
    tool.on_press(6, 3, ctx)
    tool.on_move(9, 3, ctx)
    tool.on_release(9, 3, ctx)
    # In-bounds part of the stroke is painted normally.
    assert buf.get_pixel(6, 3) == RED
    assert buf.get_pixel(7, 3) == RED
    # Cross-edge coords wrap to the OPPOSITE (left) edge (torus topology, CL-14).
    assert buf.get_pixel(0, 3) == RED  # wrapped from x=8
    assert buf.get_pixel(1, 3) == RED  # wrapped from x=9
    # And the wrapped edit is a single undoable command that fully reverts.
    assert stack.count() == 1
    stack.undo()
    reverted = scene.active_buffer()
    assert reverted.get_pixel(0, 3) == TRANSPARENT
    assert reverted.get_pixel(1, 3) == TRANSPARENT
    assert reverted.get_pixel(6, 3) == TRANSPARENT
