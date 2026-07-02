"""Main-window acceptance tests (REQ-P1-UI-011,-017..020).

Scenarios SC-UI-011-1 (exclusive tool selection), SC-UI-017-1 (toolbar selects
tool), SC-UI-018-1/-2 (palette order + single-select), SC-UI-019-1 (undo action
wired to the active stack), SC-UI-020-1/-2/-3 (new 64x64 / 8K / tab switch).
Both themes.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF

from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import FloodFillTool
from tests.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_011_1_tool_actions_are_exclusive(qtbot):
    """SC-UI-011-1: the tool actions are mutually exclusive (one active)."""
    win = _window(qtbot)
    win._tool_actions["pencil"].trigger()
    assert win._tool_actions["pencil"].isChecked() is True
    win._tool_actions["eraser"].trigger()
    assert win._tool_actions["eraser"].isChecked() is True
    assert win._tool_actions["pencil"].isChecked() is False


def test_sc_ui_017_1_toolbar_selects_active_tool(qtbot):
    """SC-UI-017-1: activating the fill action makes fill the active tool."""
    win = _window(qtbot)
    win._tool_actions["fill"].trigger()
    record = win.active_tab()
    assert isinstance(record.view.active_tool(), FloodFillTool)
    assert win._tool_actions["fill"].isChecked() is True


def test_sc_ui_018_1_palette_panel_shows_colours_in_index_order(qtbot):
    """SC-UI-018-1: the palette panel lists swatches in index order."""
    win = _window(qtbot)
    win._palette_panel.set_palette(Palette([RED, GREEN, BLUE]))
    listw = win._palette_panel._list
    from PySide6.QtCore import Qt

    shown = [
        listw.item(row).data(Qt.ItemDataRole.UserRole) for row in range(listw.count())
    ]
    assert shown == [RED, GREEN, BLUE]


def test_sc_ui_018_2_selecting_swatch_sets_active_colour(qtbot):
    """SC-UI-018-2: single-selecting a swatch sets the active colour."""
    win = _window(qtbot)
    win._palette_panel.set_palette(Palette([RED, GREEN, BLUE]))
    win._palette_panel.select_color(GREEN)
    assert win._palette_panel.selected_color() == GREEN
    assert len(win._palette_panel._list.selectedItems()) == 1  # single-select
    assert win._active_color == GREEN  # propagated to the active colour


def test_sc_ui_019_1_undo_action_wired_to_active_stack(qtbot):
    """SC-UI-019-1: the Edit>Undo action undoes on the active document's stack."""
    win = _window(qtbot)
    record = win.active_tab()
    prepare_for_click(record.view)
    record.view.set_active_color(BLUE)
    click_pixel(record.view, 3, 3)
    assert record.view._scene.active_buffer().get_pixel(3, 3) == BLUE
    assert record.stack.count() == 1
    win._undo_action.trigger()
    assert record.view._scene.active_buffer().get_pixel(3, 3) == (0, 0, 0, 0)


def test_sc_ui_020_1_new_document_defaults_to_64(qtbot):
    """SC-UI-020-1: a new document defaults to 64x64 RGBA in a new active tab."""
    win = _window(qtbot)
    before = win._tab_widget.count()
    doc = win.new_document()
    assert (doc.width, doc.height) == (64, 64)
    assert win._tab_widget.count() == before + 1
    assert win.active_document() is doc


def test_sc_ui_020_2_8k_document_supported(qtbot):
    """SC-UI-020-2: an 8K document opens and its scene rect is (0,0,7680,4320)."""
    win = _window(qtbot)
    win.new_document(7680, 4320)
    record = win.active_tab()
    assert record.scene.sceneRect() == QRectF(0, 0, 7680, 4320)


def test_sc_ui_020_3_tab_switch_changes_active_context(qtbot):
    """SC-UI-020-3: switching tabs makes that document's context active."""
    win = _window(qtbot)
    doc_a = win.new_document()
    a_index = win._tab_widget.currentIndex()
    a_stack = win.active_tab().stack
    win.new_document()  # doc B becomes active
    assert win.active_document() is not doc_a
    win._tab_widget.setCurrentIndex(a_index)
    assert win.active_document() is doc_a
    assert win._undo_group.activeStack() is a_stack
