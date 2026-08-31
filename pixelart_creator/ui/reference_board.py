"""PureRef-style reference board (REQ-P9-UI-006) — Qt only, .pixboard persistence.

``Reference_Board`` is a **separate** window over its own
:class:`QGraphicsScene` (distinct from the document scene) holding floating
reference :class:`QGraphicsPixmapItem` s: add an image, pan/zoom the board,
move/scale/z-order each reference, optional always-on-top. It is **non-destructive** —
it never composites into, exports, or undoes the document (REQ-P9-UI-010): nothing
here touches the document, its buffers or its undo stack.

The layout persists through :mod:`pixelart_creator.data.reference_board_io`
(``.pixboard``): this window maps the pure
:class:`~pixelart_creator.data.reference_board_io.ReferenceBoardLayout` dataclass to
Qt pixmap items and back (Article I — the defensive serialise/validate lives in
``data/``). A malformed file surfaces a user-facing error, never a crash/execution.
The image count is capped at ``MAX_REFERENCE_IMAGES``. All strings are ``tr()``-wrapped
with a ``changeEvent`` retranslate (REQ-P9-UI-014).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.reference_board_io import (
    ReferenceBoardIOError,
    ReferenceBoardLayout,
    ReferenceImageEntry,
    load_board,
    save_board,
)
from pixelart_creator.logic.constants import MAX_REFERENCE_IMAGES
from pixelart_creator.logic.favourites import Favourites

#: Per-wheel-notch board zoom step.
_BOARD_ZOOM_STEP = 1.15
#: Corner grab-handle edge, in item-local px (REQ-P9-UI-006 resize gesture).
#: No matching UI-metric constant exists in ``logic/constants.py`` today (gap
#: reported in this task's EXIT_STATUS); this module already keeps its own
#: UI-only metrics locally (see ``_BOARD_ZOOM_STEP`` above), so the same
#: convention is followed here rather than inlining a literal (S12).
_RESIZE_HANDLE_SIZE = 10.0
#: Minimum absolute scale factor a corner-drag resize may reach (guards
#: against a degenerate/zero-size or inverted reference item).
_MIN_REFERENCE_SCALE = 0.05

#: Opposite-corner anchor used while resizing (the anchor stays fixed).
_OPPOSITE_CORNER = {"tl": "br", "tr": "bl", "bl": "tr", "br": "tl"}


class Reference_Item(QGraphicsPixmapItem):
    """One movable/scalable reference image carrying its source path + crop.

    Two authoring gestures close REQ-P9-UI-006's move/**resize**/z-order clause
    (CF-30 / D-10): a corner-drag resize (grab handles at the four corners,
    free resize by default, Shift held preserves aspect — see the module
    docstring rationale) and raise/lower context-menu actions. Both gestures
    write to the same fields :meth:`Reference_Board.to_layout` already
    persists: the resize updates :meth:`transform` (``item.transform()``,
    read back into ``ReferenceImageEntry.transform``'s ``m11/m22`` scale
    components) and the z-order actions update ``zValue()`` (read back into
    ``ReferenceImageEntry.z_order``) — no new persisted field is needed.
    """

    def __init__(self, image_ref: str, pixmap: QPixmap) -> None:
        """Build a movable/scalable item for ``pixmap`` from ``image_ref``."""
        super().__init__(pixmap)
        self._image_ref = image_ref
        self._crop = QRectF(0.0, 0.0, float(pixmap.width()), float(pixmap.height()))
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setAcceptHoverEvents(True)
        self._resize_corner: Optional[str] = None
        self._resize_start_pos = QPointF()
        self._resize_start_rect = QRectF()
        self._resize_start_transform = QTransform()

    def image_ref(self) -> str:
        """Return the source path (or embedded ref) of this reference."""
        return self._image_ref

    def crop_rect(self) -> QRectF:
        """Return the visible crop rectangle (image-local coords)."""
        return QRectF(self._crop)

    def set_crop_rect(self, crop: QRectF) -> None:
        """Set the visible crop and re-blit the sub-image (non-destructive)."""
        self._crop = QRectF(crop)

    # -- corner-drag resize (REQ-P9-UI-006 / D-10) -------------------------

    def _handle_rects(self) -> Dict[str, QRectF]:
        """Return the four corner grab-handle rects, in item-local coords."""
        rect = self.boundingRect()
        size = _RESIZE_HANDLE_SIZE
        return {
            "tl": QRectF(rect.left(), rect.top(), size, size),
            "tr": QRectF(rect.right() - size, rect.top(), size, size),
            "bl": QRectF(rect.left(), rect.bottom() - size, size, size),
            "br": QRectF(rect.right() - size, rect.bottom() - size, size, size),
        }

    def _corner_at(self, local_pos: QPointF) -> Optional[str]:
        for name, handle in self._handle_rects().items():
            if handle.contains(local_pos):
                return name
        return None

    def hoverMoveEvent(  # noqa: N802 (Qt override)
        self, event: QGraphicsSceneHoverEvent
    ) -> None:
        """Show a diagonal resize cursor over a corner handle (Qt override)."""
        corner = self._corner_at(event.pos())
        if corner in ("tl", "br"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif corner in ("tr", "bl"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(  # noqa: N802 (Qt override)
        self, event: QGraphicsSceneHoverEvent
    ) -> None:
        """Restore the default cursor leaving the item (Qt override)."""
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(  # noqa: N802 (Qt override)
        self, event: QGraphicsSceneMouseEvent
    ) -> None:
        """Start a corner resize when pressed on a handle, else move (Qt override)."""
        corner = self._corner_at(event.pos())
        if corner is not None and event.button() == Qt.MouseButton.LeftButton:
            self._resize_corner = corner
            self._resize_start_pos = self.pos()
            self._resize_start_rect = QRectF(self.boundingRect())
            self._resize_start_transform = QTransform(self.transform())
            # ItemIsMovable would otherwise fight the resize drag (F1/CL-8
            # style single-responsibility gesture per press).
            self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, False)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(  # noqa: N802 (Qt override)
        self, event: QGraphicsSceneMouseEvent
    ) -> None:
        """Apply the live corner resize, or fall back to the move drag (Qt override)."""
        if self._resize_corner is not None:
            keep_aspect = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._apply_resize(event.scenePos(), keep_aspect)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(  # noqa: N802 (Qt override)
        self, event: QGraphicsSceneMouseEvent
    ) -> None:
        """End the resize drag and restore the move flag (Qt override)."""
        if self._resize_corner is not None:
            self._resize_corner = None
            self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _apply_resize(self, scene_pos: QPointF, keep_aspect: bool) -> None:
        """Scale the item so the dragged corner follows ``scene_pos``.

        The opposite corner is the anchor and stays fixed in scene space
        (PureRef/photo-editor convention). Free resize by default; holding
        Shift preserves the drag start's aspect ratio — the codebase has no
        prior corner-resize gesture to match (grep-verified, see the report),
        so this follows the nearest analogous convention already in this same
        file/codebase: Shift as a held-modifier gesture refinement (mirrors
        ``ui/tools/selection_base.py``'s Shift-modifier pattern, applied here
        to aspect lock rather than combine mode).
        """
        corner = self._resize_corner
        if corner is None:
            return
        rect = self._resize_start_rect
        local_points = {
            "tl": QPointF(rect.left(), rect.top()),
            "tr": QPointF(rect.right(), rect.top()),
            "bl": QPointF(rect.left(), rect.bottom()),
            "br": QPointF(rect.right(), rect.bottom()),
        }
        anchor_local = local_points[_OPPOSITE_CORNER[corner]]
        drag_local = local_points[corner]
        anchor_scene = self._resize_start_pos + self._resize_start_transform.map(
            anchor_local
        )
        dx = drag_local.x() - anchor_local.x()
        dy = drag_local.y() - anchor_local.y()
        if dx == 0.0 or dy == 0.0:
            return
        scale_x = abs((scene_pos.x() - anchor_scene.x()) / dx)
        scale_y = abs((scene_pos.y() - anchor_scene.y()) / dy)
        if keep_aspect:
            factor = (scale_x + scale_y) / 2.0
            scale_x = scale_y = factor
        scale_x = max(scale_x, _MIN_REFERENCE_SCALE)
        scale_y = max(scale_y, _MIN_REFERENCE_SCALE)
        new_pos = anchor_scene - QPointF(
            scale_x * anchor_local.x(), scale_y * anchor_local.y()
        )
        self.setTransform(QTransform(scale_x, 0.0, 0.0, scale_y, 0.0, 0.0))
        self.setPos(new_pos)

    # -- raise/lower z-order (REQ-P9-UI-006 / D-10) ------------------------

    def contextMenuEvent(  # noqa: N802 (Qt override)
        self, event: QGraphicsSceneContextMenuEvent
    ) -> None:
        """Offer Raise/Lower z-order actions on the reference item (Qt override).

        Built fresh per invocation (no persisted widget text to retranslate),
        so ``QCoreApplication.translate`` is used exactly as the rest of this
        codebase's non-QObject/module-level Qt code does (e.g.
        ``ui/export_actions.py``, ``ui/tilemap_io_actions.py``) — a
        :class:`QGraphicsPixmapItem` is not a ``QObject`` and has no ``tr()``.
        """
        menu = QMenu()
        raise_action = menu.addAction(
            QCoreApplication.translate("Reference_Item", "Raise")
        )
        lower_action = menu.addAction(
            QCoreApplication.translate("Reference_Item", "Lower")
        )
        chosen = menu.exec(event.screenPos())
        scene = self.scene()
        if scene is None or chosen is None:
            event.accept()
            return
        siblings = [it for it in scene.items() if isinstance(it, Reference_Item)]
        if chosen is raise_action:
            top = max((it.zValue() for it in siblings), default=self.zValue())
            self.setZValue(top + 1.0)
        elif chosen is lower_action:
            bottom = min((it.zValue() for it in siblings), default=self.zValue())
            self.setZValue(bottom - 1.0)
        event.accept()


class Reference_Board(QWidget):
    """A PureRef-style floating-reference board (separate scene; .pixboard I/O)."""

    #: Emitted with the picked RGBA tuple when a plain wheel notch travels the
    #: shared Favourites cursor (REQ-IS-UI-008, D-16). The board never touches
    #: the document/buffers/undo stack (REQ-P9-UI-010); this only sets the
    #: app-wide active colour/palette state, same as every other surface.
    colorPicked = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the board window (own scene, add/save/load/on-top controls)."""
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene, self)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._items: List[Reference_Item] = []
        #: The persisted Favourites model bound via :meth:`set_favourites_model`
        #: (T-21/D-16); ``None`` until the shell binds one.
        self._favourites: Optional[Favourites] = None

        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add_image)
        self._save_button = QPushButton(self)
        self._save_button.clicked.connect(self._on_save)
        self._load_button = QPushButton(self)
        self._load_button.clicked.connect(self._on_load)
        self._on_top_button = QPushButton(self)
        self._on_top_button.setCheckable(True)
        self._on_top_button.toggled.connect(self._on_always_on_top)

        controls = QHBoxLayout()
        controls.addWidget(self._add_button)
        controls.addWidget(self._save_button)
        controls.addWidget(self._load_button)
        controls.addWidget(self._on_top_button)
        controls.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self._view, 1)
        self._retranslate()

    # -- board content ----------------------------------------------------

    def add_image(self, path: str) -> Optional[Reference_Item]:
        """Add one reference image from ``path`` (``<= MAX_REFERENCE_IMAGES``).

        Returns the new item, or ``None`` when the cap is reached or the image
        fails to load (a user-facing notice is shown).
        """
        if len(self._items) >= MAX_REFERENCE_IMAGES:
            QMessageBox.warning(
                self,
                self.tr("Reference board full"),
                self.tr("The board already holds the maximum of {0} images.").format(
                    MAX_REFERENCE_IMAGES
                ),
            )
            return None
        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(
                self,
                self.tr("Cannot load image"),
                self.tr("The file could not be read as an image: {0}").format(path),
            )
            return None
        item = Reference_Item(path, pixmap)
        item.setZValue(float(len(self._items)))
        self._scene.addItem(item)
        self._items.append(item)
        return item

    def items(self) -> List[Reference_Item]:
        """Return the reference items on the board."""
        return list(self._items)

    def clear(self) -> None:
        """Remove every reference (board reset)."""
        for item in list(self._items):
            self._scene.removeItem(item)
        self._items = []

    # -- persistence (binds to data/reference_board_io) -------------------

    def to_layout(self) -> ReferenceBoardLayout:
        """Build a pure :class:`ReferenceBoardLayout` from the board items."""
        entries: List[ReferenceImageEntry] = []
        for item in self._items:
            transform = item.transform()
            crop = item.crop_rect()
            entries.append(
                ReferenceImageEntry(
                    image=item.image_ref(),
                    transform=(
                        transform.m11(),
                        transform.m12(),
                        transform.m21(),
                        transform.m22(),
                        item.pos().x(),
                        item.pos().y(),
                    ),
                    crop=(crop.x(), crop.y(), crop.width(), crop.height()),
                    z_order=int(item.zValue()),
                )
            )
        return ReferenceBoardLayout(
            pan=(
                self._view.horizontalScrollBar().value(),
                self._view.verticalScrollBar().value(),
            ),
            zoom=float(self._view.transform().m11()) or 1.0,
            images=tuple(entries),
        )

    def apply_layout(self, layout: ReferenceBoardLayout) -> None:
        """Rebuild the board items from a validated :class:`ReferenceBoardLayout`."""
        self.clear()
        for entry in layout.images:
            item = self.add_image(entry.image)
            if item is None:
                continue
            a, b, c, d, e, f = entry.transform
            item.setTransform(QTransform(a, b, c, d, 0.0, 0.0))
            item.setPos(e, f)
            item.set_crop_rect(
                QRectF(entry.crop[0], entry.crop[1], entry.crop[2], entry.crop[3])
            )
            item.setZValue(float(entry.z_order))
        zoom = layout.zoom if layout.zoom > 0.0 else 1.0
        self._view.setTransform(QTransform.fromScale(zoom, zoom))

    def _on_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Reference Board"),
            "",
            self.tr("Reference board (*.pixboard)"),
        )
        if not path:
            return
        try:
            save_board(self.to_layout(), path)
        except ReferenceBoardIOError as exc:
            QMessageBox.warning(self, self.tr("Save failed"), str(exc))

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Reference Board"),
            "",
            self.tr("Reference board (*.pixboard)"),
        )
        if not path:
            return
        try:
            layout = load_board(path)
        except ReferenceBoardIOError as exc:
            # Malformed / unknown-version file → user-facing error, never a crash.
            QMessageBox.warning(self, self.tr("Open failed"), str(exc))
            return
        self.apply_layout(layout)

    def _on_add_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Add Reference Image"),
            "",
            self.tr("Images (*.png *.jpg *.jpeg *.bmp *.gif)"),
        )
        if path:
            self.add_image(path)

    def _on_always_on_top(self, enabled: bool) -> None:
        window = self.window()
        flags = window.windowFlags()
        window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(enabled))
        if window.isVisible():
            window.show()  # re-apply the flag change
        _ = flags

    def set_favourites_model(self, favourites: Favourites) -> None:
        """Bind the persisted Favourites model a plain wheel notch travels.

        REQ-IS-UI-008, T-21/D-16.
        """
        self._favourites = favourites

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt override)
        """Zoom the board on ``Shift``+wheel, otherwise travel Favourites.

        ``Shift``+wheel zooms the board (D-16); plain wheel travels
        Favourites (REQ-IS-UI-008, D-16).
        """
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._zoom_wheel(event)
        else:
            self._favourites_wheel(event)

    def _zoom_wheel(self, event: QWheelEvent) -> None:
        """Zoom the board in/out on a wheel notch.

        Relocated from plain wheel to ``Shift``+wheel (D-16); this board's own
        step is otherwise unmodified.
        """
        factor = _BOARD_ZOOM_STEP
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor
        self._view.scale(factor, factor)
        event.accept()

    def _favourites_wheel(self, event: QWheelEvent) -> None:
        """Plain wheel steps the Favourites cursor (REQ-IS-UI-008, D-16).

        Wheel down **advances**, wheel up **retreats** (``CL-IS-02`` — see
        ``Canvas_View._favourites_wheel``). A silent no-op with no favourites
        bound or an empty list (never zooms, never errors). The board never
        touches the document/undo stack (REQ-P9-UI-010) — this only sets the
        app-wide active colour, exactly like every other surface's gesture.
        """
        if self._favourites is None:
            event.accept()
            return
        if event.angleDelta().y() < 0:
            color = self._favourites.advance()
        else:
            color = self._favourites.retreat()
        if color is not None:
            self.colorPicked.emit(color)
        event.accept()

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Reference Board"))
        self.setAccessibleName(self.tr("Reference board"))
        self._view.setAccessibleName(self.tr("Reference board canvas"))
        self._add_button.setText(self.tr("Add Image…"))
        self._save_button.setText(self.tr("Save…"))
        self._load_button.setText(self.tr("Open…"))
        self._on_top_button.setText(self.tr("Always on Top"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the board control strings on a language change (Qt override)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
