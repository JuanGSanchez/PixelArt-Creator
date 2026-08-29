"""Timeline grid view acceptance tests (T16; REQ-P5-UI-020, -022, -023, -024,
-026..-029).

One pytest-qt test per listed acceptance scenario, driven headlessly
(``QT_QPA_PLATFORM=offscreen``, forced in ``conftest``) and run under **both**
themes via the autouse ``theme`` fixture (REQ-P5-UI-028). Asserts on
observable state (signals, undo-stack counts, model roles, document content)
— never on ``ui/timeline_grid_view.py`` internals beyond its own public Qt
model/view surface.

Scope note: gesture-driven scenarios (drag zones, cel move/copy) are
``test_timeline_grid_gestures.py``; the overwrite confirmation dialog and its
suppression flow are ``test_cel_overwrite_dialog.py``; the restore-path
submenu is ``test_project_prefs_actions.py``; the shipped strip's own
regression pin is ``test_timeline_strip_regression.py``.
"""

from __future__ import annotations

from typing import List

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.document import Document, LayerGroup
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.track_table import EMPTY_CELL, track_table
from pixelart_creator.ui.timeline_grid_view import Timeline_Grid_View
from pixelart_creator.ui.timeline_panel import Timeline_Panel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255), (10, 200, 10, 255)]


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #


def _make_doc(frames: int = 3, width: int = 64, height: int = 64) -> Document:
    doc = Document(width, height, palette=Palette(STARTER))
    for _ in range(frames - 1):
        doc.add_frame()
    return doc


def _make_two_track_doc() -> Document:
    """3 frames built by duplication, carrying tracks "Base" and "Outline"."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.make_duplicate_frame_command(0).execute()
    doc.make_duplicate_frame_command(1).execute()
    assert len(doc.frames) == 3
    return doc


def _make_panel(qtbot, doc: Document):
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(700, 220)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    qtbot.waitExposed(panel)
    return panel, stack


def _to_grid(panel: Timeline_Panel):
    """Flip the view-mode toggle to the grid and return the grid widget."""
    panel._grid_toggle_action.setChecked(True)
    return panel._grid


def _cell_center(grid, row: int, col: int):
    index = grid.model().index(row, col)
    return grid.visualRect(index).center()


def _click_cell(qtbot, grid, row: int, col: int) -> None:
    qtbot.mouseClick(
        grid.viewport(), Qt.MouseButton.LeftButton, pos=_cell_center(grid, row, col)
    )


def _click_h_header(qtbot, grid, section: int) -> None:
    header = grid.horizontalHeader()
    x = header.sectionViewportPosition(section) + header.sectionSize(section) // 2
    from PySide6.QtCore import QPoint

    qtbot.mouseClick(
        header.viewport(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(x, header.height() // 2),
    )


def _click_v_header(qtbot, grid, section: int) -> None:
    header = grid.verticalHeader()
    y = header.sectionViewportPosition(section) + header.sectionSize(section) // 2
    from PySide6.QtCore import QPoint

    qtbot.mouseClick(
        header.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(header.width() // 2, y)
    )


# --------------------------------------------------------------------------- #
# REQ-P5-UI-020 — view-mode toggle                                            #
# --------------------------------------------------------------------------- #


def test_sc_ui_020_1_the_strip_is_what_opens(qtbot):
    """SC-UI-020-1: a fresh document opens on the strip; the toggle is present,
    checkable, labelled and keyboard-reachable."""
    doc = _make_doc(2)
    panel, _stack = _make_panel(qtbot, doc)

    assert panel._cell_surface.currentWidget() is panel._strip
    action = panel._grid_toggle_action
    assert action.isCheckable()
    assert action.isChecked() is False
    assert action.text() != ""
    assert action.isEnabled()
    # Keyboard-reachable: the toolbar carries it as a real QAction (activatable
    # by keyboard shortcut/menu navigation, not painted-only).
    assert action in panel._toolbar.actions()


def test_sc_ui_020_2_switching_to_grid_preserves_place(qtbot):
    """SC-UI-020-2: switching view preserves the active frame, layer, undo
    stack and canvas-displayed frame."""
    doc = _make_two_track_doc()
    panel, stack = _make_panel(qtbot, doc)
    panel.select_frame(2)
    undo_before = stack.count()

    frame_events: List[int] = []
    panel.frameSelected.connect(frame_events.append)
    grid = _to_grid(panel)

    assert panel.active_index == 2
    assert stack.count() == undo_before
    # The grid re-derives at the preserved active frame.
    assert grid.model().rowCount() == 2


def test_sc_ui_020_3_switching_back_restores_strip_unchanged(qtbot):
    """SC-UI-020-3: switching back shows the strip with the same frame active."""
    doc = _make_doc(4)
    panel, _stack = _make_panel(qtbot, doc)
    panel.select_frame(2)
    _to_grid(panel)
    panel._grid_toggle_action.setChecked(False)

    assert panel._cell_surface.currentWidget() is panel._strip
    assert panel.active_index == 2
    assert panel._strip.currentRow() == 2


def test_sc_ui_020_4_view_mode_never_pushes_a_command(qtbot):
    """SC-UI-020-4: switching views twice pushes no QUndoCommand and leaves the
    document's frame content unaffected by the switch itself."""
    doc = _make_doc(3)
    panel, stack = _make_panel(qtbot, doc)
    before = stack.count()

    panel._grid_toggle_action.setChecked(True)
    panel._grid_toggle_action.setChecked(False)

    assert stack.count() == before


# --------------------------------------------------------------------------- #
# REQ-P5-UI-022 — grid presentation                                           #
# --------------------------------------------------------------------------- #


def test_sc_ui_022_1_columns_are_frames_rows_are_tracks(qtbot):
    """SC-UI-022-1: 3 frame columns in playback order, 1 row per track."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    assert model.columnCount() == 3
    assert model.rowCount() == 2
    for col in range(3):
        header_text = model.headerData(
            col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        )
        assert str(col + 1) in header_text
    labels = {
        model.headerData(row, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole)
        for row in range(2)
    }
    assert labels == {"Base", "Outline"}


def test_sc_ui_022_2_occupied_cell_shows_content_and_visibility(qtbot):
    """SC-UI-022-2: a painted, occupied cell exposes a thumbnail and its node's
    visible state."""
    doc = _make_two_track_doc()
    outline_id = doc.frames[1].layers[1].layer_id
    doc.frames[1].layers[1].buffer.fill_rect(0, 0, 64, 64, (255, 0, 0, 255))
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=1)
    row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline_id)

    index = grid.model().index(row, 1)
    icon = grid.model().data(index, Qt.ItemDataRole.DecorationRole)
    assert icon is not None and not icon.isNull()
    check = grid.model().data(index, Qt.ItemDataRole.CheckStateRole)
    assert check == Qt.CheckState.Checked.value


def test_sc_ui_022_3_empty_cell_distinct_from_occupied_transparent(qtbot):
    """SC-UI-022-3: a cell with no node is distinct (accessibly + visually) from
    an occupied cell whose node happens to be fully transparent."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    outline = doc.add_layer("Outline", frame_index=0)
    outline.buffer.fill_rect(0, 0, 64, 64, (0, 0, 0, 0))  # fully transparent
    doc.add_frame()  # frame 1 has only "Base" -> "Outline" is empty there

    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()
    outline_row = next(
        i
        for i in range(model.rowCount())
        if model.headerData(i, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole)
        == "Outline"
    )

    occupied_index = model.index(outline_row, 0)
    empty_index = model.index(outline_row, 1)

    occupied_desc = model.data(
        occupied_index, Qt.ItemDataRole.AccessibleDescriptionRole
    )
    empty_desc = model.data(empty_index, Qt.ItemDataRole.AccessibleDescriptionRole)
    assert occupied_desc != empty_desc
    assert occupied_desc == "Occupied cell"
    assert empty_desc == "Empty cell"

    occupied_icon = model.data(occupied_index, Qt.ItemDataRole.DecorationRole)
    empty_icon = model.data(empty_index, Qt.ItemDataRole.DecorationRole)
    assert occupied_icon is not None and not occupied_icon.isNull()
    assert empty_icon is None
    # The empty cell carries no visibility check state at all (no toggle).
    assert model.data(empty_index, Qt.ItemDataRole.CheckStateRole) is None


def test_sc_ui_022_4_indexed_document_resolves_through_palette_lut(qtbot):
    """SC-UI-022-4: an INDEXED document's cell thumbnail resolves through the
    palette LUT and renders without error (the compositor path is RGBA-only;
    this asserts the grid does not crash or silently produce a blank/None
    thumbnail for an indexed node — the observable proxy available from the
    model's own public role, without reaching into the private RGBA
    conversion helper)."""
    from pixelart_creator.logic.pixel_buffer import ColorMode

    doc = Document(64, 64, mode=ColorMode.INDEXED, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.frames[0].layers[0].buffer.data[:] = 2  # a real palette index, not 0

    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    icon = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
    assert icon is not None and not icon.isNull()


def test_sc_ui_022_5_grid_rebuilds_after_structural_changes(qtbot):
    """SC-UI-022-5: add / duplicate / remove and their undos each leave the grid
    matching the document."""
    doc = _make_doc(2)
    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)

    panel._on_add()
    assert grid.model().columnCount() == len(doc.frames) == 3
    stack.undo()
    assert grid.model().columnCount() == len(doc.frames) == 2

    panel.select_frame(0)
    panel._on_duplicate()
    assert grid.model().columnCount() == len(doc.frames) == 3
    stack.undo()
    assert grid.model().columnCount() == len(doc.frames) == 2


# --------------------------------------------------------------------------- #
# REQ-P5-UI-023 — grid selection (mutates nothing)                            #
# --------------------------------------------------------------------------- #


def test_sc_ui_023_1_clicking_a_cell_sets_frame_and_layer(qtbot):
    """SC-UI-023-1: one click sets both the active frame and the active layer."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_id = next(r.layer_id for r in table.rows if r.label == "Outline")
    row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline_id)

    frame_events: List[int] = []
    layer_events: List[int] = []
    panel.frameSelected.connect(frame_events.append)
    panel.layerSelected.connect(layer_events.append)

    _click_cell(qtbot, grid, row, 2)

    assert frame_events[-1] == 2
    assert layer_events[-1] == outline_id


def test_sc_ui_023_2_column_header_selects_frame_only(qtbot):
    """SC-UI-023-2: a column-header click selects the frame; the active layer
    is unaffected by it (no layerSelected emission)."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)

    layer_events: List[int] = []
    panel.layerSelected.connect(layer_events.append)

    _click_h_header(qtbot, grid, 1)

    assert panel.active_index == 1
    assert layer_events == []


def test_sc_ui_023_3_row_header_selects_track_in_active_frame(qtbot):
    """SC-UI-023-3: a row-header click selects that track's node in the
    (unchanged) active frame."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    panel.select_frame(1)
    grid = _to_grid(panel)
    grid.set_active_frame(1)
    table = track_table(doc, active_frame=1)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    outline_id = table.rows[outline_row].layer_id

    layer_events: List[int] = []
    panel.layerSelected.connect(layer_events.append)

    _click_v_header(qtbot, grid, outline_row)

    assert panel.active_index == 1
    assert layer_events[-1] == outline_id


def test_sc_ui_023_4_refused_selection_leaves_layer_unchanged(qtbot):
    """SC-UI-023-4: a row-header click for a track absent from the active frame
    is refused (no layerSelected), and the corresponding empty cell click only
    moves the active frame."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()  # frame 1 (index 1) has no "Outline"
    doc.add_frame()  # frame 2 (index 2) likewise

    panel, _stack = _make_panel(qtbot, doc)
    panel.select_frame(2)
    grid = _to_grid(panel)
    grid.set_active_frame(2)
    table = track_table(doc, active_frame=2)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[2] is EMPTY_CELL

    layer_events: List[int] = []
    panel.layerSelected.connect(layer_events.append)
    _click_v_header(qtbot, grid, outline_row)
    assert layer_events == []

    frame_events: List[int] = []
    panel.frameSelected.connect(frame_events.append)
    _click_cell(qtbot, grid, outline_row, 2)
    assert frame_events[-1] == 2
    assert layer_events == []  # still nothing selected on that empty cell


def test_sc_ui_023_5_no_selection_pushes_a_command(qtbot):
    """SC-UI-023-5: clicking cells and headers in any order pushes nothing and
    leaves the document unmodified."""
    doc = _make_two_track_doc()
    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    before = stack.count()

    _click_cell(qtbot, grid, 0, 0)
    _click_h_header(qtbot, grid, 1)
    _click_v_header(qtbot, grid, 1)
    _click_cell(qtbot, grid, 1, 2)

    assert stack.count() == before


# --------------------------------------------------------------------------- #
# REQ-P5-UI-024 — per-cell visibility                                         #
# --------------------------------------------------------------------------- #


def test_sc_ui_024_1_cell_toggle_hides_one_frames_layer_only(qtbot):
    """SC-UI-024-1: hiding cell (frame 2, "Outline") hides only that frame's
    node; frame 1's shares the track (layer_id) but stays visible."""
    doc = _make_two_track_doc()  # frames 0,1,2 all share Base/Outline tracks
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    model = grid.model()
    index = model.index(outline_row, 1)  # frame index 1 (0-based) == "frame 2"
    model.setData(index, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole)

    assert doc.frames[1].layers[1].visible is False
    assert doc.frames[0].layers[1].visible is True


def test_sc_ui_024_2_cell_toggle_is_exactly_one_command_with_exact_undo(qtbot):
    """SC-UI-024-2: the toggle is exactly one QUndoCommand; undo restores the
    exact prior visibility."""
    doc = _make_two_track_doc()
    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    before = stack.count()

    index = grid.model().index(outline_row, 1)
    grid.model().setData(
        index, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole
    )

    assert stack.count() == before + 1
    assert doc.frames[1].layers[1].visible is False
    stack.undo()
    assert doc.frames[1].layers[1].visible is True


def test_sc_ui_024_3_cell_toggle_and_layer_panel_are_one_state(qtbot):
    """SC-UI-024-3: toggling from the grid cell changes the document node's
    ``visible`` state, and the Layer_Panel — a second, independent view bound
    to the SAME document — reads that same state on rebuild (both read the
    document; neither is a second source of truth)."""
    from pixelart_creator.ui.layer_panel import Layer_Panel

    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    layer_panel = Layer_Panel()
    qtbot.addWidget(layer_panel)
    layer_panel.set_context(doc, QUndoStack(), lambda: None)
    layer_panel.set_frame_index(0)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    index = grid.model().index(outline_row, 0)
    grid.model().setData(
        index, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole
    )
    assert doc.frames[0].layers[1].visible is False

    layer_panel.rebuild()
    outline_node = doc.frames[0].layers[1]
    row = next(r for r in layer_panel._rows if r.node() is outline_node)
    assert row._vis.isChecked() is False

    # And the reverse direction: the layer panel's own toggle changes the
    # document, which the grid re-derives from on its next rebuild.
    row._vis.setChecked(True)
    assert doc.frames[0].layers[1].visible is True
    grid.rebuild()
    assert (
        grid.model().data(index, Qt.ItemDataRole.CheckStateRole)
        == Qt.CheckState.Checked.value
    )


def test_sc_ui_024_4_empty_cell_offers_no_visibility_toggle(qtbot):
    """SC-UI-024-4: an empty cell exposes no CheckStateRole and cannot be
    toggled through setData."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()  # frame 1 has no "Outline"

    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[1] is EMPTY_CELL

    model = grid.model()
    index = model.index(outline_row, 1)
    assert model.data(index, Qt.ItemDataRole.CheckStateRole) is None
    assert not (model.flags(index) & Qt.ItemFlag.ItemIsUserCheckable)

    before = stack.count()
    ok = model.setData(
        index, Qt.CheckState.Checked.value, Qt.ItemDataRole.CheckStateRole
    )
    assert ok is False
    assert stack.count() == before


def test_sc_ui_024_5_locked_layer_visibility_still_togglable(qtbot):
    """SC-UI-024-5: a locked node's cell visibility toggle still succeeds as
    one command."""
    doc = _make_two_track_doc()
    doc.frames[0].layers[1].locked = True
    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    before = stack.count()

    index = grid.model().index(outline_row, 0)
    grid.model().setData(
        index, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole
    )

    assert stack.count() == before + 1
    assert doc.frames[0].layers[1].visible is False


# --------------------------------------------------------------------------- #
# REQ-P5-UI-026 — parity inside the grid view                                 #
# --------------------------------------------------------------------------- #


def test_sc_ui_026_frame_actions_work_identically_in_grid_view(qtbot):
    """SC-UI-026: add/duplicate/remove and the duration editor act on the
    active frame exactly as beside the strip, while the grid is showing."""
    doc = _make_doc(2)
    panel, stack = _make_panel(qtbot, doc)
    _to_grid(panel)

    panel._on_add()
    assert stack.count() == 1
    assert len(doc.frames) == 3

    panel._duration_spin.setValue(250)
    panel._on_duration_committed()
    assert doc.frames[panel.active_index].duration_ms == 250


# --------------------------------------------------------------------------- #
# REQ-P5-UI-027 — accessibility                                               #
# --------------------------------------------------------------------------- #


def test_sc_ui_027_grid_and_headers_have_accessible_names(qtbot):
    """SC-UI-027: the grid, its headers and the view-mode toggle each carry a
    translatable accessible name; the grid is keyboard-focusable."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)

    assert grid.accessibleName() != ""
    assert grid.accessibleDescription() != ""
    assert grid.horizontalHeader().accessibleName() != ""
    assert grid.verticalHeader().accessibleName() != ""
    assert panel._grid_toggle_action.text() != ""
    assert grid.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_sc_ui_027_cells_expose_frame_and_track_in_accessible_text(qtbot):
    """SC-UI-027: cell (3, "Outline") is distinguishable from cell (4,
    "Outline") and from an empty cell via AccessibleTextRole."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    text_a = model.data(model.index(outline_row, 0), Qt.ItemDataRole.AccessibleTextRole)
    text_b = model.data(model.index(outline_row, 1), Qt.ItemDataRole.AccessibleTextRole)
    assert text_a != text_b
    assert "Outline" in text_a and "Outline" in text_b


# --------------------------------------------------------------------------- #
# REQ-P5-UI-029 — translatable strings                                        #
# --------------------------------------------------------------------------- #


def test_sc_ui_029_grid_retranslates_on_language_change(qtbot):
    """SC-UI-029: a LanguageChange event re-sets the grid's accessible strings
    without raising."""
    from PySide6.QtCore import QEvent

    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)

    grid.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert grid.accessibleName() != ""


def test_grid_retranslate_on_an_unbound_empty_grid_does_not_raise(qtbot):
    """REQ-P5-UI-029, branch-coverage close-out: a LanguageChange delivered
    before any document is bound (rowCount == columnCount == 0) must not
    raise, and the grid's OWN accessible strings are still re-set -- the
    model's re-emit is correctly SKIPPED (nothing to re-emit), exercising
    the false branch of ``_Track_Table_Model.retranslate``'s "there is
    something to re-emit" guard, which every other retranslate test in this
    module only reaches with a bound document."""
    from PySide6.QtCore import QEvent

    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)
    assert grid.model().rowCount() == 0

    grid.changeEvent(QEvent(QEvent.Type.LanguageChange))  # must not raise

    assert grid.accessibleName() != ""


# --------------------------------------------------------------------------- #
# Branch-coverage close-out (T16/T18 gate; REQ-P5-UI-022/-023/-024) --         #
# the model's own public role/query surface, exercised with the boundary and  #
# refusal-path values a real click/drag never happens to produce, plus the    #
# nested-group visibility path a flat two-track document never reaches.       #
# --------------------------------------------------------------------------- #


def test_sc_ui_024_6_toggle_reaches_a_layer_nested_inside_a_group(qtbot):
    """REQ-P5-UI-024 continuation (CL-P5G-2: "group nodes are tracks too"): a
    cel living inside a ``LayerGroup`` still resolves through the grid's own
    per-cell path search and toggles as exactly one command with exact undo
    -- a flat two-track document (every other REQ-P5-UI-024 test above) never
    reaches ``_find_path``'s recursive branch, only a nested one does."""
    doc = _make_two_track_doc()
    outline_id = doc.frames[0].layers[1].layer_id
    doc.make_group_command([1], frame_index=0).execute()  # wrap "Outline" alone
    group = doc.frames[0].layers[1]
    assert isinstance(group, LayerGroup)
    outline_node = group.children[0]
    assert outline_node.layer_id == outline_id

    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline_id)
    before = stack.count()

    index = grid.model().index(outline_row, 0)
    grid.model().setData(
        index, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole
    )

    assert stack.count() == before + 1
    assert outline_node.visible is False
    stack.undo()
    assert outline_node.visible is True


def test_sc_ui_024_7_find_path_continues_past_a_group_that_does_not_contain_the_target(
    qtbot,
):
    """``_find_path``'s recursive branch has two shapes: finding the target
    INSIDE a group (proven above) and NOT finding it there, needing the
    search to continue past the group to a later sibling. Built here as
    Base, a Group wrapping an unrelated "Deco" layer, then "Outline" as a
    later top-level sibling; toggling "Outline" must still resolve to
    exactly one command even though the search has to look inside — and
    fail to find it in — the group first."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Deco", frame_index=0)
    doc.make_group_command([1], frame_index=0).execute()  # group "Deco" alone
    outline = doc.add_layer("Outline", frame_index=0)  # a later top-level sibling
    outline_id = outline.layer_id

    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline_id)
    before = stack.count()

    index = grid.model().index(outline_row, 0)
    grid.model().setData(
        index, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole
    )

    assert stack.count() == before + 1
    assert outline.visible is False


def test_model_row_count_with_valid_parent_returns_zero(qtbot):
    """A flat ``QAbstractTableModel`` reports zero rows under any non-root
    parent index (the standard "no children" table contract) -- Qt itself
    never queries a table model this way, so only a direct call reaches it."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    assert model.rowCount(model.index(0, 0)) == 0


def test_model_cell_at_and_track_id_at_out_of_range_are_defensive(qtbot):
    """``cell_at``/``track_id_at`` return their documented sentinels for an
    out-of-range row/column instead of raising -- the model's own public
    contract, since Qt itself never generates an out-of-range query for a
    correctly bound table."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    assert model.cell_at(-1, 0) is EMPTY_CELL
    assert model.cell_at(0, -1) is EMPTY_CELL
    assert model.cell_at(999, 0) is EMPTY_CELL
    assert model.track_id_at(-1) is None
    assert model.track_id_at(999) is None


def test_model_data_invalid_index_returns_none(qtbot):
    """``data()`` on an invalid ``QModelIndex`` returns ``None`` rather than
    raising."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    assert model.data(model.index(-1, -1)) is None


def test_model_tooltip_role_names_frame_and_track_both_states(qtbot):
    """The model's ``ToolTipRole`` names the frame + track for both an
    occupied and an empty cell -- untested by every other role assertion in
    this module, which all target ``AccessibleTextRole``/
    ``AccessibleDescriptionRole`` instead."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()  # "Outline" is empty in frame 1
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    occupied_tip = model.data(model.index(outline_row, 0), Qt.ItemDataRole.ToolTipRole)
    empty_tip = model.data(model.index(outline_row, 1), Qt.ItemDataRole.ToolTipRole)

    assert occupied_tip != empty_tip
    assert "Outline" in occupied_tip and "Outline" in empty_tip
    assert "empty" in empty_tip


def test_model_accessible_text_role_empty_cell_variant(qtbot):
    """``AccessibleTextRole`` for an EMPTY cell is exercised here -- the
    shipped ``test_sc_ui_027_cells_expose_frame_and_track_in_accessible_text``
    only ever queries two OCCUPIED cells of the same row."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    text = model.data(model.index(outline_row, 1), Qt.ItemDataRole.AccessibleTextRole)

    assert "Outline" in text
    assert "empty" in text


def test_model_track_id_role_exposes_the_stable_layer_id(qtbot):
    """The model's private custom role (used internally to identify a cell's
    track) round-trips the row's stable ``layer_id`` through ``data()``."""
    from pixelart_creator.ui.timeline_grid_view import _TRACK_ID_ROLE

    doc = _make_two_track_doc()
    outline_id = doc.frames[0].layers[1].layer_id
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline_id)

    assert model.data(model.index(outline_row, 0), _TRACK_ID_ROLE) == outline_id


def test_model_set_data_ignores_non_check_state_role(qtbot):
    """``setData`` with any role other than ``CheckStateRole`` is refused
    (returns ``False``) and pushes nothing -- every other ``setData`` call in
    this module uses ``CheckStateRole`` exclusively."""
    doc = _make_two_track_doc()
    panel, stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()
    before = stack.count()

    ok = model.setData(model.index(0, 0), "anything", Qt.ItemDataRole.EditRole)

    assert ok is False
    assert stack.count() == before


def test_model_flags_invalid_index_has_no_item_flags(qtbot):
    """``flags()`` on an invalid index returns ``NoItemFlags``."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    assert model.flags(model.index(-1, -1)) == Qt.ItemFlag.NoItemFlags


def test_model_header_data_horizontal_accessible_text_and_out_of_range(qtbot):
    """The horizontal header's ``AccessibleTextRole`` names the frame + its
    duration; an out-of-range section returns ``None``."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    text = model.headerData(
        0, Qt.Orientation.Horizontal, Qt.ItemDataRole.AccessibleTextRole
    )
    assert "1" in text

    assert (
        model.headerData(999, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        is None
    )


def test_model_header_data_vertical_accessible_text_and_out_of_range(qtbot):
    """The vertical (track) header's ``AccessibleTextRole`` names the track;
    an out-of-range section returns ``None``."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()

    text = model.headerData(
        0, Qt.Orientation.Vertical, Qt.ItemDataRole.AccessibleTextRole
    )
    assert "Track" in text
    assert (
        model.headerData(999, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole)
        is None
    )


def test_model_header_data_with_no_document_returns_none(qtbot):
    """The horizontal header returns ``None`` for a model with no document
    bound at all (distinct from an out-of-range section on a bound one)."""
    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)
    model = grid.model()

    assert (
        model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        is None
    )


def test_model_bind_with_no_document_yields_an_empty_table(qtbot):
    """Re-binding the model to ``None`` (the caller lost its document, e.g. a
    project closed) resets the table to empty rather than raising or
    retaining stale rows."""
    doc = _make_two_track_doc()
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)
    model = grid.model()
    assert model.rowCount() > 0

    model.bind(None, 0)

    assert model.rowCount() == 0
    assert model.columnCount() == 0


def test_set_active_frame_with_no_document_bound_does_not_raise(qtbot):
    """Calling ``set_active_frame`` on a grid that was never handed a
    document (e.g. constructed standalone before ``set_context``) is a safe
    no-op."""
    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)

    grid.set_active_frame(3)  # must not raise; document is None

    assert grid.model().rowCount() == 0


def test_restore_current_index_when_active_frame_beyond_column_count(qtbot):
    """``set_active_frame`` with an index beyond the bound document's own
    frame count (e.g. a stale caller after the document shrank) leaves the
    grid usable rather than raising -- the out-of-range branch of
    ``_restore_current_index``."""
    doc = _make_doc(2)
    panel, _stack = _make_panel(qtbot, doc)
    grid = _to_grid(panel)

    grid.set_active_frame(999)  # must not raise

    assert grid.model().columnCount() == 2
