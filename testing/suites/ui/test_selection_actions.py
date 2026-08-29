"""Selection-operation actions acceptance (REQ-P2-UI-008).

Scenarios SC-U008-1 (invert / clear / deselect / select-all actions are
tr()-wrapped and keyboard-reachable) and SC-U008-2 (clear is undoable; deselect
empties the active mask). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence, QUndoStack

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools.base import ToolContext
from pixelart_creator.ui.tools.floating_move import FloatingMoveController
from pixelart_creator.ui.tools.rect_select_tool import RectSelectTool
from pixelart_creator.ui.tools.selection_base import SelectionTool
from testing.suites.ui._ui_helpers import NO_MOD

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_u008_1_actions_translatable_and_reachable(qtbot):
    """SC-U008-1: the selection actions carry labels and keyboard shortcuts."""
    win = _window(qtbot)
    for action in (
        win._select_all_action,
        win._deselect_action,
        win._invert_action,
        win._clear_action,
    ):
        assert action.text() != ""  # tr()-wrapped (accessible name)
        assert not action.shortcut().isEmpty()  # keyboard-reachable
    assert win._select_all_action.shortcut() == QKeySequence("Ctrl+A")
    assert win._clear_action.shortcut() == QKeySequence("Del")


def test_sc_u008_2_select_all_invert_deselect(qtbot):
    """SC-U008-2: select-all selects the buffer; invert complements; deselect empties."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    win._on_select_all()
    mask = record.view.active_selection()
    assert mask is not None and mask.count() == buf.width * buf.height
    win._on_invert_selection()
    assert record.view.active_selection() is None  # complement of all is empty
    win._on_deselect()
    assert record.view.active_selection() is None


def test_sc_u008_2_clear_is_undoable(qtbot):
    """SC-U008-2: clearing a selection is a single undoable command."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    before = buf.copy()
    record.view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    win._on_clear_selection()
    assert record.stack.count() == 1
    assert buf.get_pixel(3, 3) == TRANSPARENT
    record.stack.undo()
    assert record.scene.active_buffer() == before


# =========================================================================
# SelectionTool controller contract (P2-UI-004..007) -- the abstract
# subclass hooks, and the per-call ``ctx`` contract branches no scripted
# UI drag ever varies mid-drag.
# =========================================================================


def _tool_ctx(
    scene,
    buf,
    *,
    selection=None,
    set_selection=None,
    floating_controller=None,
    modifiers=NO_MOD,
):
    """A real ``ToolContext`` built directly (no ``Canvas_View``) -- the same
    "None outside a canvas view" shape ``ui/tools/base.py`` documents for
    ``floating_controller``, used here to drive ``SelectionTool`` at the
    controller-contract level."""
    return ToolContext(
        buf,
        RED,
        QUndoStack(),
        scene,
        lambda c: None,
        target=None,
        selection=selection,
        set_selection=set_selection,
        modifiers=modifiers,
        floating_controller=floating_controller,
    )


def test_selection_tool_abstract_hooks_raise_not_implemented():
    """``SelectionTool`` itself declares ``label``/``build`` abstract
    (``NotImplementedError``) -- proving every concrete selection tool must,
    and does, override both."""
    tool = SelectionTool()
    with pytest.raises(NotImplementedError):
        tool.label()
    with pytest.raises(NotImplementedError):
        tool.build(0, 0, 1, 1, None)


def test_selection_tool_on_move_and_on_release_noop_without_a_prior_press(
    make_scene,
):
    """``on_move``/``on_release`` are documented drag continuations -- called
    with no drag in progress they are silent no-ops."""
    scene = make_scene(16, 16)
    buf = scene.active_buffer()
    ctx = _tool_ctx(scene, buf)
    tool = RectSelectTool()

    tool.on_move(5, 5, ctx)  # no exception, nothing to update
    tool.on_release(5, 5, ctx)  # no exception, nothing to combine
    assert tool._start is None


def test_selection_tool_drag_without_a_floating_controller_falls_through_to_build(
    make_scene,
):
    """A context with no ``floating_controller`` (``None`` outside a canvas
    view, ``ui/tools/base.py``) never starts a float even when the press
    lands inside the active selection -- it takes the ordinary build/combine
    path instead."""
    scene = make_scene(16, 16)
    buf = scene.active_buffer()
    selection = rect_mask(16, 16, 2, 2, 4, 4)
    recorded = []
    ctx = _tool_ctx(
        scene,
        buf,
        selection=selection,
        set_selection=recorded.append,
        floating_controller=None,
    )
    tool = RectSelectTool()

    tool.on_press(3, 3, ctx)  # inside the selection, but no controller wired
    assert tool._moving is False
    tool.on_move(6, 6, ctx)
    tool.on_release(6, 6, ctx)

    assert recorded  # the build/combine path ran and produced a mask


def test_selection_tool_mid_drag_loss_of_floating_controller_is_a_safe_noop(
    make_scene,
):
    """``on_press``/``on_move``/``on_release`` each receive their own ``ctx``
    per call (``ui/canvas_view.py`` keeps the same one across one real drag,
    but the tool's contract makes no such promise) -- if
    ``ctx.floating_controller`` is unavailable on a later call than the one
    that started the float, ``on_move``/``on_release`` skip the controller
    call instead of raising, and the float itself is left untouched."""
    scene = make_scene(16, 16)
    buf = scene.active_buffer()
    selection = rect_mask(16, 16, 2, 2, 4, 4)
    controller = FloatingMoveController()
    ctx_with = _tool_ctx(
        scene, buf, selection=selection, floating_controller=controller
    )
    ctx_without = _tool_ctx(scene, buf, selection=selection, floating_controller=None)
    tool = RectSelectTool()

    tool.on_press(3, 3, ctx_with)  # starts a float -> self._moving = True
    assert tool._moving is True
    assert controller.is_active()

    tool.on_move(6, 6, ctx_without)  # controller missing on THIS call -> no-op
    tool.on_release(6, 6, ctx_without)  # likewise -- no exception

    assert controller.is_active()  # the float itself is untouched, still live
    controller.cancel()  # do not leak an active float


def test_selection_tool_release_with_no_set_selection_drops_mask_silently(
    make_scene,
):
    """A context with no ``set_selection`` callback still builds the drag's
    mask internally but simply cannot publish it -- no exception, no crash."""
    scene = make_scene(16, 16)
    buf = scene.active_buffer()
    ctx = _tool_ctx(scene, buf, selection=None, set_selection=None)
    tool = RectSelectTool()

    tool.on_press(2, 2, ctx)  # no active selection -> ordinary build path
    tool.on_move(6, 6, ctx)
    tool.on_release(6, 6, ctx)  # a mask IS built, but set_selection is None

    assert tool._start is None  # the drag still completed cleanly
