"""Phase-6 tile pixel-editor coverage (REQ-P6-UI-003 edit surface).

pytest-qt, headless, both themes (autouse fixture). Drives the embedded
``_Tile_Pixel_Editor`` (and ``Tile_Edit_Dialog``): left-click paints the active
colour, right-click erases, a drag continues painting, and the enlarged view paints
without error — for both RGBA and indexed tiles. This covers the widget behind the
one-``QUndoCommand`` source-tile edit whose result linked instances then render live.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.tileset_editor_panel import (
    Tile_Edit_Dialog,
    _Tile_Pixel_Editor,
)

RED = (230, 30, 30, 255)
_CELL = 20  # _EDIT_CELL_PX


def _press(widget, x, y, button):
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(x, y),
        button,
        button,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(ev)


def _drag(widget, x, y, button):
    ev = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(x, y),
        Qt.MouseButton.NoButton,
        button,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(ev)


def test_pixel_editor_paints_and_erases_rgba(qtbot, theme):
    """Left-click paints the active colour; right-click erases to transparent."""
    tile = PixelBuffer(8, 8, ColorMode.RGBA)
    editor = _Tile_Pixel_Editor(tile, RED, 0, None)
    qtbot.addWidget(editor)

    _press(editor, _CELL // 2, _CELL // 2, Qt.MouseButton.LeftButton)  # cell (0,0)
    assert tuple(editor.edited_buffer().data[0, 0]) == RED
    _press(editor, _CELL // 2, _CELL // 2, Qt.MouseButton.RightButton)  # erase (0,0)
    assert tuple(editor.edited_buffer().data[0, 0]) == (0, 0, 0, 0)
    # A left drag continues painting into the next cell.
    _drag(editor, _CELL + _CELL // 2, _CELL // 2, Qt.MouseButton.LeftButton)  # (1,0)
    assert tuple(editor.edited_buffer().data[0, 1]) == RED
    # Out-of-bounds coordinates are ignored (no crash).
    _press(editor, 9999, 9999, Qt.MouseButton.LeftButton)
    editor.grab()  # force paintEvent (nearest-neighbour, AA off)


def test_pixel_editor_indexed_tile_paints_index(qtbot, theme):
    """An indexed tile paints the active index (left) / index 0 (right erase)."""
    tile = PixelBuffer(4, 4, ColorMode.INDEXED)
    editor = _Tile_Pixel_Editor(tile, RED, 3, None)
    qtbot.addWidget(editor)
    _press(editor, _CELL // 2, _CELL // 2, Qt.MouseButton.LeftButton)
    assert int(editor.edited_buffer().data[0, 0]) == 3
    _drag(editor, _CELL // 2, _CELL // 2, Qt.MouseButton.RightButton)  # erase -> 0
    assert int(editor.edited_buffer().data[0, 0]) == 0
    editor.grab()  # indexed greyscale-ramp paint path


def test_tile_edit_dialog_returns_edited_buffer(qtbot, theme):
    """The dialog exposes the embedded editor's edited buffer (same mode/geometry)."""
    tile = PixelBuffer(6, 6, ColorMode.RGBA)
    dialog = Tile_Edit_Dialog(tile, RED, 0, None)
    qtbot.addWidget(dialog)
    out = dialog.edited_buffer()
    assert out.mode is ColorMode.RGBA
    assert (out.width, out.height) == (6, 6)
    assert np.array_equal(out.data, tile.data)  # untouched copy until painted
