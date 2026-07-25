"""Right-click colour hub: Favourites + wheel (REQ-P3-UI-003/-004/-006).

The **marquee S3/S4 colour hub**: a cursor-anchored contextual popup opened from
the Phase-1 ``Canvas_View.set_menu_hook`` seam (SC-U003-1). It hosts the two pick
paths — a persisted, user-managed :class:`Favourites_Panel` (add / remove /
reorder, SC-U004-1) and the
:class:`~pixelart_creator.ui.colour_wheel_widget.Colour_Wheel_Widget`
with its live harmonies (SC-U003-2). A pick from either path **applies
immediately** to the active swatch (SC-U006-1) via :attr:`colorApplied`; adding
the current colour to Favourites is an **explicit** button (SC-U006-4, CL-5).

The Favourites *model* and its JSON persistence are Qt-free ``logic``/``data``
concerns (:mod:`pixelart_creator.logic.favourites`,
:mod:`pixelart_creator.data.favourites_io`); this widget only views and edits the
model, and re-emits :attr:`favouritesChanged` so the shell can persist it (the
app-config path is resolved shell-side via ``QStandardPaths``, ADR-0004). A hub
pick sets the active paint colour — a tool-state change, **not** a buffer edit —
so it never touches the undo stack (REQ-P3-UI-006, T17). Strings are ``tr()``
-wrapped and re-set on :data:`QEvent.Type.LanguageChange` (F5); the hub is
keyboard-openable and navigable.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.color import RGBA, to_hex
from pixelart_creator.logic.favourites import Favourites, FavouritesError
from pixelart_creator.ui.colour_wheel_widget import Colour_Wheel_Widget

#: Edge of a Favourites swatch icon, px (presentation-only sizing).
_FAVOURITE_PX = 24


class Favourites_Panel(QWidget):
    """A list of persisted favourite colours with add / remove / reorder (S3a/S4)."""

    #: Emitted with an RGBA tuple when a favourite is chosen (click or Enter).
    favouriteChosen = Signal(object)
    #: Emitted whenever the underlying model is mutated (so the shell persists it).
    favouritesChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the favourites list backed by an empty model."""
        super().__init__(parent)
        self._model = Favourites()

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.itemClicked.connect(self._on_item_activated)
        self._list.itemActivated.connect(self._on_item_activated)

        self._remove_button = QPushButton(self)
        self._remove_button.clicked.connect(self._on_remove)
        self._up_button = QPushButton(self)
        self._up_button.clicked.connect(lambda: self._move(-1))
        self._down_button = QPushButton(self)
        self._down_button.clicked.connect(lambda: self._move(1))

        self._title = QLabel(self)

        buttons = QHBoxLayout()
        buttons.addWidget(self._up_button)
        buttons.addWidget(self._down_button)
        buttons.addWidget(self._remove_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._list)
        layout.addLayout(buttons)
        self._retranslate()

    # -- model wiring -----------------------------------------------------

    def set_model(self, model: Favourites) -> None:
        """Bind the panel to ``model`` and repopulate the list."""
        self._model = model
        self._refresh()

    def model(self) -> Favourites:
        """Return the bound :class:`Favourites` model."""
        return self._model

    def focus_widgets(self) -> List[QWidget]:
        """Return the interactive widgets in intended tab order (A11Y-COLHUB-2)."""
        return [self._list, self._up_button, self._down_button, self._remove_button]

    def add_favourite(self, color: RGBA) -> None:
        """Add ``color`` (explicit action); a duplicate or full list is a no-op.

        Emits :attr:`favouritesChanged` when the model actually grows.
        """
        before = len(self._model)
        try:
            self._model.add(color)
        except FavouritesError:
            return  # list full (FAVOURITES_MAX) — defensive no-op.
        if len(self._model) != before:
            self._refresh()
            self._select_color(color)
            self.favouritesChanged.emit()

    # -- internal ---------------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        for color in self._model.colors():
            item = QListWidgetItem()
            pixmap = QPixmap(_FAVOURITE_PX, _FAVOURITE_PX)
            pixmap.fill(QColor(*color))
            item.setIcon(QIcon(pixmap))
            hex_text = to_hex(color, with_alpha=False)
            item.setText(hex_text)
            item.setToolTip(hex_text)
            item.setData(Qt.ItemDataRole.UserRole, color)
            self._list.addItem(item)

    def _select_color(self, color: RGBA) -> None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == color:
                self._list.setCurrentRow(row)
                return

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        color = item.data(Qt.ItemDataRole.UserRole)
        if color is not None:
            self.favouriteChosen.emit(color)

    def _on_remove(self) -> None:
        row = self._list.currentRow()
        colors = self._model.colors()
        if not 0 <= row < len(colors):
            return
        self._model.remove(colors[row])
        self._refresh()
        self.favouritesChanged.emit()

    def _move(self, delta: int) -> None:
        row = self._list.currentRow()
        target = row + delta
        if not (0 <= row < len(self._model) and 0 <= target < len(self._model)):
            return
        self._model.move(row, target)
        self._refresh()
        self._list.setCurrentRow(target)
        self.favouritesChanged.emit()

    def _retranslate(self) -> None:
        self._title.setText(self.tr("Favourites"))
        self.setAccessibleName(self.tr("Favourites panel"))
        self._list.setAccessibleName(self.tr("Favourite colours"))
        self._remove_button.setText(self.tr("Remove"))
        self._up_button.setText(self.tr("Move Up"))
        self._down_button.setText(self.tr("Move Down"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Colour_Hub_Menu(QDialog):
    """Cursor-anchored colour hub hosting Favourites + the colour wheel."""

    #: Emitted with an RGBA tuple whenever a colour is picked (apply immediately).
    colorApplied = Signal(object)
    #: Re-emitted when the Favourites model changes (so the shell persists it).
    favouritesChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the popup hub (Favourites + wheel + explicit add button)."""
        super().__init__(parent)
        # A popup closes on an outside click and floats without a title bar.
        self.setWindowFlags(Qt.WindowType.Popup)

        self._favourites = Favourites_Panel(self)
        self._favourites.favouriteChosen.connect(self._on_favourite_chosen)
        self._favourites.favouritesChanged.connect(self.favouritesChanged)

        self._wheel = Colour_Wheel_Widget(self)
        self._wheel.colorPicked.connect(self._on_wheel_picked)

        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add_current)

        wheel_column = QVBoxLayout()
        wheel_column.addWidget(self._wheel)
        wheel_column.addWidget(self._add_button)

        layout = QHBoxLayout(self)
        layout.addWidget(self._favourites)
        layout.addLayout(wheel_column)
        self._apply_tab_order()
        self._retranslate()

    def _apply_tab_order(self) -> None:
        """Chain an explicit tab order across every interactive hub widget (A2).

        Favourites list + reorder/remove buttons, then the wheel pad, value
        slider, numeric entries and harmony swatches, then the explicit
        Add-to-Favourites button — so keyboard focus walks the hub predictably
        (A11Y-COLHUB-2)."""
        ordered: List[QWidget] = [
            *self._favourites.focus_widgets(),
            *self._wheel.focus_widgets(),
            self._add_button,
        ]
        for first, second in zip(ordered, ordered[1:]):
            self.setTabOrder(first, second)

    # -- public API -------------------------------------------------------

    def set_favourites_model(self, model: Favourites) -> None:
        """Bind the Favourites list to the shell's persisted model."""
        self._favourites.set_model(model)

    def favourites_model(self) -> Favourites:
        """Return the bound :class:`Favourites` model."""
        return self._favourites.model()

    def set_color(self, color: RGBA) -> None:
        """Seed the wheel with ``color`` (e.g. the current active swatch)."""
        self._wheel.set_color(QColor(*color))

    def current_rgba(self) -> RGBA:
        """Return the colour currently selected in the wheel."""
        return self._wheel.current_rgba()

    def popup_at(self, global_pos: QPoint) -> None:
        """Show the hub anchored at ``global_pos`` (the right-click position)."""
        self.move(global_pos)
        self.show()
        self._wheel.setFocus()

    # -- slots ------------------------------------------------------------

    def _on_wheel_picked(self, color: QColor) -> None:
        # Applies immediately to the active swatch; no undo entry (tool state).
        self.colorApplied.emit(
            (color.red(), color.green(), color.blue(), color.alpha())
        )

    def _on_favourite_chosen(self, color: RGBA) -> None:
        self._wheel.set_color(QColor(*color))
        self.colorApplied.emit(color)

    def _on_add_current(self) -> None:
        # Explicit save-to-Favourites, distinct from applying (SC-U006-4, CL-5).
        self._favourites.add_favourite(self._wheel.current_rgba())

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Colour Hub"))
        self.setAccessibleName(self.tr("Colour hub"))
        self._add_button.setText(self.tr("Add to Favourites"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__: List[str] = ["Favourites_Panel", "Colour_Hub_Menu"]
