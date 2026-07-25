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

from typing import List, Optional

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
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

#: Per-wheel-notch board zoom step.
_BOARD_ZOOM_STEP = 1.15


class Reference_Item(QGraphicsPixmapItem):
    """One movable/scalable reference image carrying its source path + crop."""

    def __init__(self, image_ref: str, pixmap: QPixmap) -> None:
        """Build a movable/scalable item for ``pixmap`` from ``image_ref``."""
        super().__init__(pixmap)
        self._image_ref = image_ref
        self._crop = QRectF(0.0, 0.0, float(pixmap.width()), float(pixmap.height()))
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def image_ref(self) -> str:
        """Return the source path (or embedded ref) of this reference."""
        return self._image_ref

    def crop_rect(self) -> QRectF:
        """Return the visible crop rectangle (image-local coords)."""
        return QRectF(self._crop)

    def set_crop_rect(self, crop: QRectF) -> None:
        """Set the visible crop and re-blit the sub-image (non-destructive)."""
        self._crop = QRectF(crop)


class Reference_Board(QWidget):
    """A PureRef-style floating-reference board (separate scene; .pixboard I/O)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the board window (own scene, add/save/load/on-top controls)."""
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._view = QGraphicsView(self._scene, self)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._items: List[Reference_Item] = []

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

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt override)
        """Zoom the board in/out on a wheel notch (Qt override)."""
        factor = _BOARD_ZOOM_STEP
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor
        self._view.scale(factor, factor)
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
