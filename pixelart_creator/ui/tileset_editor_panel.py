"""Tileset editor panel — slice, select and edit source tiles (Slice 6E).

``Tileset_Editor_Panel`` shows a :class:`~pixelart_creator.logic.tileset.Tileset`'s
source image sliced into its **row-major** tile grid (REQ-P6-UI-001), lets the
user **select** the active tile for stamping (view state, no undo — CL-13,
emitted as :data:`activeTileChanged`), **re-slice** the grid via tile
size / margin / spacing spin-boxes (REQ-P6-UI-002, one
:class:`~pixelart_creator.ui.commands.TilesetCommand` wrapping
``make_reslice_command``), and **paint into a source tile** (REQ-P6-UI-003, one
``TilesetCommand`` wrapping ``make_edit_tile_command``) so every placed instance
of that tile updates live (REQ-P6-LOGIC-006).

All domain rules (slice bounds, tile geometry, reversibility) live in
``logic/tileset`` (Article I / S11); this panel only binds to that API, wraps its
returned commands, and renders thumbnails. Every user-visible string is
``tr()``-wrapped and re-set on :data:`QEvent.Type.LanguageChange`
(REQ-P6-UI-017); controls carry accessible names, are keyboard reachable
(REQ-P6-UI-015) and theme by role (REQ-P6-UI-016).
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QMouseEvent, QPainter, QPixmap, QUndoStack
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import (
    DEFAULT_TILE_HEIGHT,
    DEFAULT_TILE_MARGIN,
    DEFAULT_TILE_SPACING,
    DEFAULT_TILE_WIDTH,
    MAX_TILE_DIMENSION,
)
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tileset import Tileset, TilesetError
from pixelart_creator.ui.commands import TilesetCommand

#: Thumbnail edge (px) for a tile swatch in the grid list (presentation-only,
#: not a domain tuning value — cf. Palette_Panel's swatch size).
_THUMB_PX = 40

#: On-screen pixel size of one tile pixel in the tile editor dialog.
_EDIT_CELL_PX = 20


def _buffer_to_qimage(buffer: PixelBuffer) -> QImage:
    """Return an owned RGBA :class:`QImage` copy of ``buffer`` (RGBA tiles).

    Indexed tiles (rare — the tilemap render seam requires RGBA sources) are
    shown as a greyscale ramp of their index so a thumbnail still renders.
    ``QImage.copy()`` detaches from the NumPy memory.
    """
    if buffer.mode is ColorMode.RGBA:
        data = np.ascontiguousarray(buffer.data)
    else:
        idx = np.clip(buffer.data, 0, 255).astype(np.uint8)
        rgb = np.repeat(idx[:, :, None], 3, axis=2)
        alpha = np.full((*idx.shape, 1), 255, dtype=np.uint8)
        data = np.ascontiguousarray(np.concatenate([rgb, alpha], axis=2))
    height, width = int(data.shape[0]), int(data.shape[1])
    image = QImage(
        data.data, width, height, data.strides[0], QImage.Format.Format_RGBA8888
    )
    return image.copy()


class _Tile_Pixel_Editor(QWidget):
    """An enlarged, click-to-paint editable view of one tile's pixels.

    Holds an editable RGBA/indexed copy of the tile; left-click paints the active
    colour (or index), right-click erases (transparent / index 0). The result is
    read back by :class:`Tile_Edit_Dialog` and handed to
    ``make_edit_tile_command`` — no domain logic lives here.
    """

    def __init__(
        self, tile: PixelBuffer, color: RGBA, index: int, parent: Optional[QWidget]
    ) -> None:
        """Seed the editor with a copy of ``tile`` and the active colour/index."""
        super().__init__(parent)
        self._buffer = tile.copy()
        self._color = color
        self._index = int(index)
        self.setFixedSize(
            QSize(
                self._buffer.width * _EDIT_CELL_PX,
                self._buffer.height * _EDIT_CELL_PX,
            )
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(self.tr("Tile pixel editor"))
        self.setAccessibleDescription(
            self.tr("Left-click to paint, right-click to erase")
        )

    def edited_buffer(self) -> PixelBuffer:
        """Return the edited tile buffer (same mode/geometry as the source tile)."""
        return self._buffer

    def _paint_cell(self, event: QMouseEvent, erase: bool) -> None:
        col = int(event.position().x()) // _EDIT_CELL_PX
        row = int(event.position().y()) // _EDIT_CELL_PX
        if not (0 <= col < self._buffer.width and 0 <= row < self._buffer.height):
            return
        if self._buffer.mode is ColorMode.RGBA:
            value = (0, 0, 0, 0) if erase else self._color
            self._buffer.data[row, col] = value
        else:
            self._buffer.data[row, col] = 0 if erase else self._index
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Paint (left) or erase (right) the clicked pixel."""
        self._paint_cell(event, event.button() == Qt.MouseButton.RightButton)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Continue painting/erasing while a button is held."""
        buttons = event.buttons()
        if buttons & Qt.MouseButton.LeftButton:
            self._paint_cell(event, False)
        elif buttons & Qt.MouseButton.RightButton:
            self._paint_cell(event, True)

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        """Draw the tile pixels scaled up, nearest-neighbour, AA off."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        image = _buffer_to_qimage(self._buffer)
        painter.drawImage(self.rect(), image)
        painter.end()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Re-set the accessible strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self.setAccessibleName(self.tr("Tile pixel editor"))
            self.setAccessibleDescription(
                self.tr("Left-click to paint, right-click to erase")
            )
        super().changeEvent(event)


class Tile_Edit_Dialog(QDialog):
    """Modal editor for one source tile's pixels (REQ-P6-UI-003)."""

    def __init__(
        self,
        tile: PixelBuffer,
        color: RGBA,
        index: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the tile editor seeded from ``tile`` + the active colour/index."""
        super().__init__(parent)
        self._editor = _Tile_Pixel_Editor(tile, color, index, self)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self._editor)
        layout.addWidget(self._buttons)
        self._retranslate()

    def edited_buffer(self) -> PixelBuffer:
        """Return the edited tile buffer from the embedded pixel editor."""
        return self._editor.edited_buffer()

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Edit Tile"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Re-translate the dialog title on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Tileset_Editor_Panel(QWidget):
    """Sliced-tile grid + slicing config + source-tile edit for one tileset."""

    #: Emitted with the selected tile's **global gid** (view state, no undo).
    activeTileChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the slicing spin-boxes, tile grid and edit button (empty)."""
        super().__init__(parent)
        self._tileset: Optional[Tileset] = None
        self._stack: Optional[QUndoStack] = None
        self._on_changed: Optional[Callable[[], None]] = None
        self._active_color: RGBA = (0, 0, 0, 255)
        self._active_index: int = 0

        self._width_spin = self._make_dim_spin(DEFAULT_TILE_WIDTH, minimum=1)
        self._height_spin = self._make_dim_spin(DEFAULT_TILE_HEIGHT, minimum=1)
        self._margin_spin = self._make_dim_spin(DEFAULT_TILE_MARGIN, minimum=0)
        self._spacing_spin = self._make_dim_spin(DEFAULT_TILE_SPACING, minimum=0)

        self._form = QFormLayout()
        self._width_label = QLabel(self)
        self._height_label = QLabel(self)
        self._margin_label = QLabel(self)
        self._spacing_label = QLabel(self)
        self._form.addRow(self._width_label, self._width_spin)
        self._form.addRow(self._height_label, self._height_spin)
        self._form.addRow(self._margin_label, self._margin_spin)
        self._form.addRow(self._spacing_label, self._spacing_spin)

        self._apply_button = QPushButton(self)
        self._apply_button.clicked.connect(self._on_reslice)
        self._edit_button = QPushButton(self)
        self._edit_button.clicked.connect(self._on_edit_tile)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self._apply_button)
        button_row.addWidget(self._edit_button)

        self._grid = QListWidget(self)
        self._grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._grid.setMovement(QListWidget.Movement.Static)
        self._grid.setIconSize(QSize(_THUMB_PX, _THUMB_PX))
        self._grid.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._grid.currentRowChanged.connect(self._on_tile_selected)
        self._grid.itemDoubleClicked.connect(lambda _item: self._on_edit_tile())

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addLayout(button_row)
        layout.addWidget(self._grid, 1)

        self._retranslate()
        self._update_actions()

    # -- context ----------------------------------------------------------

    def set_context(
        self,
        tileset: Optional[Tileset],
        stack: Optional[QUndoStack],
        on_changed: Optional[Callable[[], None]],
    ) -> None:
        """Bind the panel to a tileset + its undo stack + a canvas-refresh hook.

        ``on_changed`` is invoked by a :class:`TilesetCommand` after a re-slice /
        tile edit (and its undo/redo) so any tilemap canvas showing linked
        instances repaints (REQ-P6-UI-003). ``None`` clears the panel.
        """
        self._tileset = tileset
        self._stack = stack
        self._on_changed = on_changed
        if tileset is not None:
            self._width_spin.setValue(tileset.tile_width)
            self._height_spin.setValue(tileset.tile_height)
            self._margin_spin.setValue(tileset.margin)
            self._spacing_spin.setValue(tileset.spacing)
        self.rebuild()

    def set_active_color(self, color: RGBA) -> None:
        """Set the colour painted into a source tile in the tile editor."""
        self._active_color = color

    def set_active_index(self, index: int) -> None:
        """Set the palette index painted into an indexed source tile."""
        self._active_index = int(index)

    def active_gid(self) -> Optional[int]:
        """Return the selected tile's global gid, or ``None``."""
        if self._tileset is None:
            return None
        row = self._grid.currentRow()
        if not 0 <= row < self._tileset.tile_count:
            return None
        return self._tileset.first_gid + row

    # -- grid -------------------------------------------------------------

    def rebuild(self) -> None:
        """Rebuild the tile-thumbnail grid from the tileset (row-major ids)."""
        self._grid.clear()
        tileset = self._tileset
        if tileset is not None:
            for local_id in range(tileset.tile_count):
                item = QListWidgetItem()
                item.setIcon(self._tile_icon(tileset, local_id))
                item.setData(Qt.ItemDataRole.UserRole, tileset.first_gid + local_id)
                item.setToolTip(self.tr("Tile %1").replace("%1", str(local_id)))
                self._grid.addItem(item)
        self._update_actions()

    def _tile_icon(self, tileset: Tileset, local_id: int) -> QIcon:
        image = _buffer_to_qimage(tileset.tile_pixels(local_id))
        pixmap = QPixmap.fromImage(image).scaled(
            _THUMB_PX,
            _THUMB_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        return QIcon(pixmap)

    # -- actions ----------------------------------------------------------

    def _make_dim_spin(self, value: int, *, minimum: int) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(minimum, MAX_TILE_DIMENSION)
        spin.setValue(value)
        return spin

    def _push(self, command: Command, label: str) -> None:
        if self._stack is None:
            return
        self._stack.push(TilesetCommand(command, self._refresh, label))

    def _refresh(self) -> None:
        self.rebuild()
        if self._on_changed is not None:
            self._on_changed()

    def _on_reslice(self) -> None:
        tileset = self._tileset
        if tileset is None:
            return
        try:
            command = tileset.make_reslice_command(
                tile_width=self._width_spin.value(),
                tile_height=self._height_spin.value(),
                margin=self._margin_spin.value(),
                spacing=self._spacing_spin.value(),
            )
        except TilesetError as exc:
            self._warn(self.tr("Re-slice Tileset"), str(exc))
            return
        self._push(command, self.tr("Re-slice Tileset"))

    def _on_edit_tile(self) -> None:
        tileset = self._tileset
        if tileset is None:
            return
        row = self._grid.currentRow()
        if not 0 <= row < tileset.tile_count:
            return
        dialog = Tile_Edit_Dialog(
            tileset.tile_pixels(row), self._active_color, self._active_index, self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            command = tileset.make_edit_tile_command(row, dialog.edited_buffer())
        except TilesetError as exc:
            self._warn(self.tr("Edit Tile"), str(exc))
            return
        self._push(command, self.tr("Edit Tile"))

    def _on_tile_selected(self, row: int) -> None:
        gid = self.active_gid()
        if gid is not None:
            self.activeTileChanged.emit(gid)
        self._update_actions()

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _update_actions(self) -> None:
        has_tileset = self._tileset is not None
        has_sel = self.active_gid() is not None
        self._apply_button.setEnabled(has_tileset)
        self._edit_button.setEnabled(has_sel)
        for spin in (
            self._width_spin,
            self._height_spin,
            self._margin_spin,
            self._spacing_spin,
        ):
            spin.setEnabled(has_tileset)

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Tileset editor panel"))
        self._width_label.setText(self.tr("Tile width"))
        self._height_label.setText(self.tr("Tile height"))
        self._margin_label.setText(self.tr("Margin"))
        self._spacing_label.setText(self.tr("Spacing"))
        self._width_spin.setSuffix(self.tr(" px"))
        self._height_spin.setSuffix(self.tr(" px"))
        self._margin_spin.setSuffix(self.tr(" px"))
        self._spacing_spin.setSuffix(self.tr(" px"))
        self._width_spin.setAccessibleName(self.tr("Tile width"))
        self._height_spin.setAccessibleName(self.tr("Tile height"))
        self._margin_spin.setAccessibleName(self.tr("Tile margin"))
        self._spacing_spin.setAccessibleName(self.tr("Tile spacing"))
        self._apply_button.setText(self.tr("Re-slice"))
        self._apply_button.setToolTip(self.tr("Re-slice the source image"))
        self._apply_button.setAccessibleName(self.tr("Re-slice tileset"))
        self._edit_button.setText(self.tr("Edit Tile…"))
        self._edit_button.setToolTip(self.tr("Paint into the selected source tile"))
        self._edit_button.setAccessibleName(self.tr("Edit selected tile"))
        self._grid.setAccessibleName(self.tr("Tileset tiles"))
        self._grid.setAccessibleDescription(
            self.tr("Sliced tiles in row-major order; click to select for stamping")
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Re-translate the panel strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
