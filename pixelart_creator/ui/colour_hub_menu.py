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
app-config path is resolved shell-side via ``QStandardPaths``, ADR-0004).

**Amended 2026-08-24 (UR-HUBFILL-1/-2).** A hub pick still sets the active paint
colour immediately (:attr:`colorApplied`, tool state, never an undo entry on its
own) — but a **COMPLETED** pick now ALSO emits :attr:`colorCommitted`, which the
shell (``ui/main_window.py``) uses to run the active colour-writing tool at the
hub's anchor pixel as **one** undoable command (REQ-P3-UI-006 leg 2). The premise
that a hub pick "never touches the undo stack" is reversed for a completed pick;
this module stays Qt-plumbing only — the run/guard/undo decision lives in
``ui/canvas_view.py``'s ``run_tool_at`` and ``ui/main_window.py``. Strings are
``tr()``-wrapped and re-set on :data:`QEvent.Type.LanguageChange` (F5); the hub
is keyboard-openable and navigable.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.color import RGBA, to_hex
from pixelart_creator.logic.favourites import Favourites, FavouritesError
from pixelart_creator.ui.colour_wheel_widget import Colour_Wheel_Widget

#: Edge of a Favourites swatch icon, px (presentation-only sizing).
_FAVOURITE_PX = 24

#: Keys that nudge the wheel pad's hue/saturation (``_WheelPad.keyPressEvent``);
#: a KeyRelease for one of these is a discrete, already-completed pick (REQ-P3-
#: UI-006 leg 2), unlike Tab/other keys the pad never acts on.
_WHEEL_NUDGE_KEYS = frozenset(
    {Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down}
)


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
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Colour_Hub_Menu(QDialog):
    """Cursor-anchored colour hub hosting Favourites + the colour wheel."""

    #: Emitted with an RGBA tuple whenever a colour is picked (apply immediately,
    #: leg 1 — the live preview stream; never refused, REQ-P3-UI-006 clause 1).
    colorApplied = Signal(object)
    #: Emitted with an RGBA tuple on a COMPLETED pick only — one emission per
    #: discrete gesture (a wheel-drag release, a keyboard nudge release, a
    #: numeric spin's editingFinished, a swatch click, or a favourite chosen).
    #: The shell (``ui/main_window.py``) uses this to run the active tool at
    #: the hub's anchor pixel as leg 2 (REQ-P3-UI-006 clauses 2-6).
    colorCommitted = Signal(object)
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
        self._pick_completion_targets = self._install_pick_completion_watchers()

        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add_current)

        self._pick_note = QLabel(self)
        self._pick_note.setWordWrap(True)

        wheel_column = QVBoxLayout()
        wheel_column.addWidget(self._wheel)
        wheel_column.addWidget(self._pick_note)
        wheel_column.addWidget(self._add_button)

        layout = QHBoxLayout(self)
        layout.addWidget(self._favourites)
        layout.addLayout(wheel_column)
        self._apply_tab_order()
        self._retranslate()
        self.set_pick_surface_visible(True)

    def _apply_tab_order(self) -> None:
        """Chain an explicit tab order across every interactive hub widget (A2).

        Favourites list + reorder/remove buttons, then the wheel pad, value
        slider, numeric entries and harmony swatches, then the explicit
        Add-to-Favourites button — so keyboard focus walks the hub predictably
        (A11Y-COLHUB-2).
        """
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

    def set_pick_surface_visible(self, visible: bool) -> None:
        """Show/hide the wheel + numeric + harmony surface (REQ-P3-UI-006 clause 7).

        Favourites and Add-to-Favourites stay visible regardless (CL-5) — only
        the colour wheel, its value slider, numeric entries and harmony
        swatches are tool-conditional: hidden for the six tools that do not
        write the active colour to the buffer (eraser, the three selection
        tools, picker, dither — CL-18), with a one-line ``tr()``-wrapped
        explanation shown in their place (SC-U006-13). The shell decides
        ``visible`` from the active tool id; this widget stays Qt-plumbing
        only and makes no tool-identity decision itself.
        """
        self._wheel.setVisible(visible)
        self._pick_note.setVisible(not visible)

    # -- pick-completion detection -----------------------------------------
    #
    # ``Colour_Wheel_Widget.colorPicked`` is a live preview stream (SC-U006-10 /
    # REQ-P3-UI-006 clause 3): it fires on every wheel-drag mouse-move sample
    # and on every numeric-spin/value-slider change. Binding the tool-run leg
    # to it directly would run the active tool once per sample. This hub may
    # not edit ``colour_wheel_widget.py`` (outside this dispatch's write
    # targets), so a completed pick is detected here, from the outside, off
    # each control's own release/edit-finish event rather than off the stream.

    def _install_pick_completion_watchers(self) -> List[QWidget]:
        """Wire the wheel's live-stream controls to a discrete completion signal.

        * the wheel pad and the value slider: a left mouse-button release, or
          a (non-autorepeat) ``KeyRelease`` of one of ``_WHEEL_NUDGE_KEYS`` —
          the pad's own keyboard-nudge keys, reused here for the (vertical)
          slider's arrow-key stepping too — caught via an installed event
          filter (:meth:`eventFilter` below);
        * each RGB/HSV numeric spin: ``editingFinished`` (Enter or focus-out),
          never ``valueChanged``, which fires per keystroke while typing;
        * each harmony/shade/tint swatch button: ``clicked`` — already one
          atomic gesture with no drag to debounce.
        Returns the widgets an event filter was installed on, kept referenced
        for the hub's lifetime (Qt keeps no reference of its own).
        """
        targets: List[QWidget] = []
        wheel_pad = self._find_wheel_pad()
        if wheel_pad is not None:
            targets.append(wheel_pad)
        targets.extend(self._wheel.findChildren(QSlider))
        for widget in targets:
            widget.installEventFilter(self)
        for spin in self._wheel.findChildren(QSpinBox):
            spin.editingFinished.connect(self._on_pick_completed)
        for button in self._wheel.findChildren(QAbstractButton):
            button.clicked.connect(self._on_pick_completed)
        return targets

    def _find_wheel_pad(self) -> Optional[QWidget]:
        """Locate the wheel's hue/saturation pad without importing its class.

        ``_WheelPad`` is module-private in ``colour_wheel_widget.py``, so it
        is identified structurally — the one child carrying a public-named
        ``hueSatPicked`` signal — rather than by reaching for a private class
        name this module has no licence to depend on.
        """
        for child in self._wheel.findChildren(QWidget):
            if hasattr(child, "hueSatPicked"):
                return child
        return None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Detect a completed wheel-pad/value-slider pick (see the block above)."""
        if (
            isinstance(event, QMouseEvent)
            and event.type() == QEvent.Type.MouseButtonRelease
        ):
            if event.button() == Qt.MouseButton.LeftButton:
                self._on_pick_completed()
        elif isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyRelease:
            if not event.isAutoRepeat() and event.key() in _WHEEL_NUDGE_KEYS:
                self._on_pick_completed()
        return super().eventFilter(obj, event)

    def _on_pick_completed(self) -> None:
        """Emit :attr:`colorCommitted` for the wheel's current colour (leg 2)."""
        self.colorCommitted.emit(self._wheel.current_rgba())

    # -- slots ------------------------------------------------------------

    def _on_wheel_picked(self, color: QColor) -> None:
        # Applies immediately to the active swatch; leg 1, never refused.
        self.colorApplied.emit(
            (color.red(), color.green(), color.blue(), color.alpha())
        )

    def _on_favourite_chosen(self, color: RGBA) -> None:
        # A favourite activation is itself one discrete, already-completed
        # pick (SC-U006-2) — both legs fire; the shell gates leg 2's tool run
        # on the active tool (SC-U006-13: no tool for the six non-consuming
        # tools, even though this hub emits colorCommitted uniformly here).
        self._wheel.set_color(QColor(*color))
        self.colorApplied.emit(color)
        self.colorCommitted.emit(color)

    def _on_add_current(self) -> None:
        # Explicit save-to-Favourites, distinct from applying (SC-U006-4, CL-5).
        self._favourites.add_favourite(self._wheel.current_rgba())

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Colour Hub"))
        self.setAccessibleName(self.tr("Colour hub"))
        self._add_button.setText(self.tr("Add to Favourites"))
        self._pick_note.setText(
            self.tr(
                "This tool does not paint the active colour, so the colour "
                "wheel is hidden here."
            )
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__: List[str] = ["Favourites_Panel", "Colour_Hub_Menu"]
