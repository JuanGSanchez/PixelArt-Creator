"""Magic-wand selection-tool acceptance (REQ-P2-UI-006).

Scenarios SC-U006-1 (a click selects the contiguous colour region as the active
mask) and SC-U006-2 (the tolerance control changes the selected extent). Both
themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.ui.tools import MagicWandTool
from testing.suites.ui._ui_helpers import click_pixel

RED = (230, 30, 30, 255)
NEAR_RED = (230, 30, 40, 255)  # differs from RED by 10 in the blue channel


def _fill_block(buf, x0, y0, x1, y1, color):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            buf.set_pixel(x, y, color)


def test_sc_u006_1_click_selects_contiguous_region(make_view):
    """SC-U006-1: a wand click selects the contiguous same-colour region only."""
    view, scene, _stack = make_view(16, 16)
    buf = scene.active_buffer()
    _fill_block(buf, 0, 0, 3, 3, RED)  # block A
    _fill_block(buf, 10, 10, 12, 12, RED)  # separate block B (same colour)
    tool = MagicWandTool()
    tool.set_tolerance(0)
    view.set_tool(tool)
    click_pixel(view, 1, 1)
    mask = view.active_selection()
    assert mask is not None
    assert mask.is_selected(2, 2)  # inside block A
    assert not mask.is_selected(11, 11)  # block B is not contiguous with A


def test_sc_u006_2_tolerance_changes_extent(make_view):
    """SC-U006-2: raising the tolerance includes an adjacent near-colour pixel."""
    view, scene, _stack = make_view(16, 16)
    buf = scene.active_buffer()
    _fill_block(buf, 0, 0, 3, 3, RED)
    buf.set_pixel(4, 0, NEAR_RED)  # a near-colour pixel adjacent to the block

    exact = MagicWandTool()
    exact.set_tolerance(0)
    view.set_tool(exact)
    click_pixel(view, 1, 0)
    tight = view.active_selection()
    assert tight is not None and not tight.is_selected(4, 0)

    view.clear_selection()
    loose = MagicWandTool()
    loose.set_tolerance(2000)  # squared-RGBA units; comfortably includes NEAR_RED
    view.set_tool(loose)
    click_pixel(view, 1, 0)
    wide = view.active_selection()
    assert wide is not None and wide.is_selected(4, 0)
    assert wide.count() > tight.count()


def test_t17_press_inside_existing_mask_does_not_lift(make_view):
    """A wand press inside an existing selection does NOT
    start a floating move — it (re)selects, per the ratified ``_allow_move``
    narrowing on :class:`~pixelart_creator.ui.tools.selection_base.SelectionTool`
    (``MagicWandTool._allow_move = False``, documented: "the wand's click always
    (re)selects rather than moving"). Contrast with the rect/lasso selection
    tools, whose in-mask press DOES lift a float (``test_floating_selection.py``).
    """
    view, scene, _stack = make_view(16, 16)
    buf = scene.active_buffer()
    _fill_block(buf, 0, 0, 3, 3, RED)
    view.set_tool(MagicWandTool())

    # An existing selection covering the same block the wand will click inside.
    from pixelart_creator.logic.selection import rect_mask

    view.set_selection(rect_mask(16, 16, 0, 0, 3, 3))

    controller = view.floating_controller()
    click_pixel(view, 1, 1)  # press+release inside the existing mask

    assert not controller.is_active()  # never lifted a float
    mask = view.active_selection()
    assert mask is not None
    assert mask.is_selected(2, 2)  # the wand's own contiguous-region selection


def test_t17_frame_select_commits_a_live_float(qtbot):
    """Switching the active (canvas-displayed) frame while a
    floating selection is live commits it as one command first — the shipped
    ``Main_Window._on_frame_selected`` calls ``record.view.commit_active_float()``
    before switching frames (mirrors the tool-switch / tab-switch commit
    triggers already proven in ``test_floating_selection.py``)."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from pixelart_creator.logic.selection import rect_mask
    from pixelart_creator.ui.main_window import Main_Window
    from pixelart_creator.ui.tools import RectSelectTool
    from testing.suites.ui._ui_helpers import prepare_for_click, viewport_point_for_pixel

    win = Main_Window()
    qtbot.addWidget(win)
    document = win.active_document()
    document.add_frame()  # a second frame to select into

    record = win.active_tab()
    view, scene, stack = record.view, record.scene, record.stack
    prepare_for_click(view)
    win._tool_actions[RectSelectTool.tool_id].trigger()
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))

    def _mev(etype, x, y, button, buttons):
        # Routed through the view's own CURRENT mapping (view.mapFromScene),
        # never a hand-computed offset -- see _ui_helpers.viewport_point_for_pixel.
        point = viewport_point_for_pixel(view, x, y)
        pt = QPointF(point.x(), point.y())
        return QMouseEvent(
            etype, pt, pt, button, buttons, Qt.KeyboardModifier.NoModifier
        )

    left = Qt.MouseButton.LeftButton
    view.mousePressEvent(_mev(QEvent.Type.MouseButtonPress, 3, 3, left, left))
    view.mouseMoveEvent(
        _mev(QEvent.Type.MouseMove, 7, 5, Qt.MouseButton.NoButton, left)
    )  # offset (4, 2), no release — the float is live

    controller = view.floating_controller()
    assert controller.is_active()

    win._on_frame_selected(1)  # switch frames -> must commit the live float first

    assert not controller.is_active()
    assert stack.count() == 1
    assert buf.get_pixel(6, 4) == RED  # stamped at (2,2)+(4,2)
