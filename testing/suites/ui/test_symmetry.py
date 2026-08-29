"""Symmetry-mode acceptance (REQ-P2-UI-011).

Scenarios SC-U011-1 (selecting an axis makes freehand strokes paint their mirror(s)
live within one command), SC-U011-2 (the axis selector is tr()-wrapped,
keyboard-reachable, correct in both themes) and SC-U011-3 (undo removes the whole
mirrored stroke in one step). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.ui.symmetry_panel import Symmetry_Panel
from pixelart_creator.ui.tools import PencilTool
from tests.ui._ui_helpers import click_pixel

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def test_sc_u011_1_vertical_axis_mirrors_stroke_one_command(make_view):
    """SC-U011-1: with a vertical axis, a stroke paints its mirror in one command."""
    view, scene, stack = make_view(8, 8)
    view.set_tool(PencilTool())
    view.set_active_color(RED)
    view.set_symmetry_axis(SymmetryAxis.VERTICAL)
    click_pixel(view, 2, 3)
    buf = scene.active_buffer()
    assert buf.get_pixel(2, 3) == RED  # source
    assert buf.get_pixel(8 - 1 - 2, 3) == RED  # vertical mirror (W-1-x, y)
    assert stack.count() == 1  # source + mirror = ONE command


def test_sc_u011_3_undo_removes_whole_mirrored_stroke(make_view):
    """SC-U011-3: undo removes both the stroke and its mirror in one step."""
    view, scene, stack = make_view(8, 8)
    view.set_tool(PencilTool())
    view.set_active_color(RED)
    view.set_symmetry_axis(SymmetryAxis.VERTICAL)
    before = scene.active_buffer().copy()
    click_pixel(view, 2, 3)
    stack.undo()
    assert scene.active_buffer() == before


def test_sc_u011_2_axis_selector_translatable_and_reachable(qtbot):
    """SC-U011-2: the axis selector is tr()-wrapped and keyboard-reachable."""
    panel = Symmetry_Panel()
    qtbot.addWidget(panel)
    assert panel.accessibleName() != ""
    assert panel._combo.accessibleName() != ""
    assert panel._combo.focusPolicy() != Qt.FocusPolicy.NoFocus  # tab-reachable
    assert panel.selected_axis() is SymmetryAxis.NONE  # default off
    # Every axis option carries a translated label (no blank items).
    for row in range(panel._combo.count()):
        assert panel._combo.itemText(row) != ""
