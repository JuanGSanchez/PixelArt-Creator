"""Phase-6 tileset editor UI acceptance tests (REQ-P6-UI-001/-002/-003).

pytest-qt, headless (``QT_QPA_PLATFORM=offscreen``), both light and dark themes
via the autouse ``theme`` fixture in ``conftest.py`` (REQ-P6-UI-016). One test per
acceptance criterion, driving :class:`Tileset_Editor_Panel` bound to the frozen
``logic/tileset`` API. Domain rules live in ``logic/`` — these assert the UI
*behaviour*: slice display + selection (SC-UI-001-1), reversible re-slice +
rejection (SC-UI-002-1), reversible source-tile edit that linked instances see
live (SC-UI-003-1), plus a11y names (REQ-P6-UI-015).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tileset import Tileset
from pixelart_creator.ui import tileset_editor_panel as tep_module
from pixelart_creator.ui.tileset_editor_panel import Tileset_Editor_Panel

BLUE = (0, 0, 255, 255)


def _panel(qtbot, tileset, stack=None, on_changed=None):
    stack = stack if stack is not None else QUndoStack()
    panel = Tileset_Editor_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tileset, stack, on_changed)
    return panel, stack


def test_sc_ui_001_1_editor_shows_sliced_tiles_and_selects_one(
    qtbot, make_tilemap_setup
):
    """SC-UI-001-1: the grid shows row-major tiles; a click sets the active tile.

    A 4x2 source yields 8 tiles laid out by row-major id; selecting a tile emits
    ``activeTileChanged`` with its global gid and is view state (no undo).
    """
    tileset, _tilemap = make_tilemap_setup(cols=4, rows=2)
    panel, stack = _panel(qtbot, tileset)

    assert panel._grid.count() == 8  # 4x2 deterministic slice
    # Row-major id layout: item i carries global gid first_gid + i (UserRole = 256).
    for i in range(8):
        assert panel._grid.item(i).data(256) == tileset.first_gid + i

    with qtbot.waitSignal(panel.activeTileChanged, timeout=1000) as blocker:
        panel._grid.setCurrentRow(2)
    assert blocker.args == [tileset.first_gid + 2]
    assert panel.active_gid() == tileset.first_gid + 2
    # Selection is view state (CL-13): nothing pushed onto the undo stack.
    assert stack.index() == 0


def test_sc_ui_002_1_reslice_is_one_undoable_command(qtbot, make_tilemap_setup):
    """SC-UI-002-1: re-slicing pushes exactly one command; undo restores geometry."""
    tileset, _tilemap = make_tilemap_setup(cols=4, rows=2, tile=16)
    panel, stack = _panel(qtbot, tileset)

    panel._width_spin.setValue(8)
    panel._height_spin.setValue(8)
    panel._margin_spin.setValue(0)
    panel._spacing_spin.setValue(0)
    panel._on_reslice()

    assert stack.index() == 1  # exactly one QUndoCommand
    assert (tileset.tile_width, tileset.tile_height) == (8, 8)
    assert panel._grid.count() == tileset.tile_count  # grid rebuilt to new slice

    stack.undo()
    assert (tileset.tile_width, tileset.tile_height) == (16, 16)


def test_sc_ui_002_1_out_of_range_slice_is_rejected(
    qtbot, monkeypatch, make_tilemap_setup
):
    """SC-UI-002-1: an over-`MAX_TILESET_TILES` slice is rejected (warn, no command)."""
    # A large source so tile 1x1 would exceed MAX_TILESET_TILES (65536).
    source = PixelBuffer(300, 300, ColorMode.RGBA)
    tileset = Tileset(source, tile_width=16, tile_height=16, first_gid=1)
    panel, stack = _panel(qtbot, tileset)

    warnings = []
    monkeypatch.setattr(
        tep_module.QMessageBox,
        "warning",
        lambda *a, **k: warnings.append(a),
    )
    panel._width_spin.setValue(1)
    panel._height_spin.setValue(1)
    panel._on_reslice()

    assert warnings, "an out-of-range slice must surface a user-facing warning"
    assert stack.index() == 0  # rejected -> no command pushed
    assert (tileset.tile_width, tileset.tile_height) == (16, 16)  # unchanged


def test_sc_ui_003_1_source_tile_edit_is_one_command_seen_by_readers(
    qtbot, monkeypatch, make_tilemap_setup
):
    """SC-UI-003-1: painting a source tile is one command every reader then sees.

    Because tiles are live source regions (PB-1), the edit is the single source of
    truth: ``tile_pixels`` and any placed tilemap instance render the new colour
    after ``redo`` and the old colour after ``undo`` — with the canvas-refresh hook
    (``on_changed``) fired so linked instances repaint (REQ-P6-LOGIC-006).
    """

    class _FakeDialog:
        def __init__(self, tile, color, index, parent=None):
            self._edited = tile.copy()

        def exec(self):
            self._edited.data[:, :] = BLUE
            return QDialog.DialogCode.Accepted

        def edited_buffer(self):
            return self._edited

    monkeypatch.setattr(tep_module, "Tile_Edit_Dialog", _FakeDialog)

    tileset, tilemap = make_tilemap_setup(cols=4, rows=2)
    refreshed = []
    panel, stack = _panel(qtbot, tileset, on_changed=lambda: refreshed.append(True))
    # Place a linked instance of tile local-id 0 (gid 1) so we can prove propagation.
    tilemap.make_stamp_command(0, 5, 5, tileset.first_gid).execute()
    before = tilemap.render_region(5 * 16, 5 * 16, 16, 16).data.copy()

    panel._grid.setCurrentRow(0)
    panel._on_edit_tile()

    assert stack.index() == 1  # exactly one QUndoCommand
    assert refreshed  # canvas-refresh hook fired (linked instances repaint)
    # Reader sees the edit: the source tile and the placed instance are now blue.
    assert np.all(tileset.tile_pixels(0).data == np.array(BLUE, dtype=np.uint8))
    after = tilemap.render_region(5 * 16, 5 * 16, 16, 16).data
    assert not np.array_equal(before, after)
    assert np.all(after == np.array(BLUE, dtype=np.uint8))

    stack.undo()
    restored = tilemap.render_region(5 * 16, 5 * 16, 16, 16).data
    assert np.array_equal(restored, before)  # undo restores the exact prior pixels


def test_sc_ui_015_tileset_controls_expose_accessible_names(qtbot, make_tilemap_setup):
    """REQ-P6-UI-015: every tileset control exposes a non-empty accessible name."""
    tileset, _tilemap = make_tilemap_setup()
    panel, _stack = _panel(qtbot, tileset)

    assert panel.accessibleName() != ""
    assert panel._grid.accessibleName() != ""
    for spin in (
        panel._width_spin,
        panel._height_spin,
        panel._margin_spin,
        panel._spacing_spin,
    ):
        assert spin.accessibleName() != ""
    assert panel._apply_button.accessibleName() != ""
    assert panel._edit_button.accessibleName() != ""
