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

**Amended 2026-08-31 (REQ-IS-UI-019/-020/-021/-022/-023, REQ-IS-UI-030 FIX,
D-19).** A single left click on a Favourites entry or a harmony/shade/tint
swatch now PAINTS (leg 2, :attr:`colorCommitted`) and leaves the active
colour unchanged; a double click, or ``Space``/``Return`` on a focused
swatch, ADOPTS (leg 1, :attr:`colorApplied`) and paints nothing. The two
gestures are wired to distinct signals throughout — never one slot shared
between ``itemClicked``/``itemActivated`` — so a double click can no longer
also fire the single-click path. The wheel pad is **not** a swatch and is
unchanged: its drag still streams :attr:`colorApplied` live and its release
still commits once. The completion handler, :meth:`Colour_Hub_Menu.
_on_pick_completed`, now commits the colour of the control that actually
completed the pick rather than always reading the wheel's (possibly stale)
colour — this was the shared root cause of both defects (`REQ-IS-UI-030`).
Separately, D-19: a right-click while the hub is already open now closes it
and does not reopen it — see :meth:`Colour_Hub_Menu.consume_just_closed`.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QHideEvent, QIcon, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
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
    """A list of persisted favourite colours with add / remove / reorder (S3a/S4).

    Two gestures, two distinct signals (REQ-IS-UI-019/-022, D-11):

    * :attr:`favouritePicked` — a single left click. PAINT-only.
    * :attr:`favouriteActivated` — a double left click, or ``Enter``/``Return``
      on the focused row (``QListWidget``'s native ``itemActivated``).
      ADOPT-only.

    ``QListWidget.itemClicked`` fires on every click, including the first
    half of a double click, so the single-click paint is deferred by the
    platform's double-click interval and cancelled if ``itemActivated``
    follows — the same disambiguation pattern used by the wheel's harmony
    swatches (``colour_wheel_widget.py``'s ``_SwatchButton``).
    """

    #: Single left click on a favourite — paint that colour, leave the wheel
    #: alone.
    favouritePicked = Signal(object)
    #: Double left click / Enter / Return on a favourite — adopt that colour
    #: into the wheel, paint nothing.
    favouriteActivated = Signal(object)
    #: Deprecated alias of :attr:`favouriteActivated`, kept for pre-2026-08-31
    #: callers of the pre-split single ``favouriteChosen`` signal. Emitted
    #: alongside :attr:`favouriteActivated` ONLY — never alongside
    #: :attr:`favouritePicked`, so it never resurrects the fused-gesture
    #: defect this split fixes (REQ-IS-UI-019). New code should connect
    #: :attr:`favouritePicked` / :attr:`favouriteActivated` directly.
    favouriteChosen = Signal(object)
    #: Emitted whenever the underlying model is mutated (so the shell persists it).
    favouritesChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the favourites list backed by an empty model."""
        super().__init__(parent)
        self._model = Favourites()
        self._pending_item: Optional[QListWidgetItem] = None
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._emit_pending_pick)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.itemClicked.connect(self._on_item_clicked)
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

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        # Defer: this click may turn out to be the first half of a double
        # click, in which case `_on_item_activated` below cancels it.
        self._pending_item = item
        self._click_timer.start(QApplication.doubleClickInterval())

    def _emit_pending_pick(self) -> None:
        item = self._pending_item
        self._pending_item = None
        if item is None:
            return
        color = item.data(Qt.ItemDataRole.UserRole)
        if color is not None:
            self.favouritePicked.emit(color)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        # Double click / Enter / Return: adopt, and cancel the deferred
        # single-click paint the first half of a double click scheduled.
        self._click_timer.stop()
        self._pending_item = None
        color = item.data(Qt.ItemDataRole.UserRole)
        if color is not None:
            self.favouriteActivated.emit(color)
            self.favouriteChosen.emit(color)  # deprecated alias, see above

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
    #: numeric spin's editingFinished, a single click on a harmony/shade/tint
    #: swatch, or a single click on a Favourites entry). A DOUBLE click / a
    #: keyboard activation on either swatch surface adopts instead and never
    #: reaches this signal (REQ-IS-UI-019/-020/-022, D-11). The shell
    #: (``ui/main_window.py``) uses this to run the active tool at the hub's
    #: anchor pixel as leg 2 (REQ-P3-UI-006 clauses 2-6).
    colorCommitted = Signal(object)
    #: Re-emitted when the Favourites model changes (so the shell persists it).
    favouritesChanged = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the popup hub (Favourites + wheel + explicit add button)."""
        super().__init__(parent)
        # A popup closes on an outside click and floats without a title bar.
        self.setWindowFlags(Qt.WindowType.Popup)

        self._favourites = Favourites_Panel(self)
        self._favourites.favouritePicked.connect(self._on_favourite_picked)
        self._favourites.favouriteActivated.connect(self._on_favourite_activated)
        self._favourites.favouritesChanged.connect(self.favouritesChanged)

        self._wheel = Colour_Wheel_Widget(self)
        self._wheel.colorPicked.connect(self._on_wheel_picked)
        self._wheel.swatchPicked.connect(self._on_pick_completed)
        self._pick_completion_targets = self._install_pick_completion_watchers()
        self._just_closed = False

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

    def consume_just_closed(self) -> bool:
        """Return True once if this hub closed during the current event turn.

        D-19: "right-click when this menu is already present must trigger
        its disappearance, like when left-clicking in the canvas." The hub
        is a ``Qt.WindowType.Popup``, so an outside click already closes it —
        but the SAME right-click then reaches the shell's seam hook, which
        would otherwise reopen the hub at the new anchor and make it appear
        never to dismiss. The shell (``_open_colour_hub``) calls this at the
        top of the reopen path and aborts if it returns True. The flag is
        cleared on the next event-loop turn (see :meth:`hideEvent`), so it
        only ever suppresses the reopen belonging to the click that closed
        it — a later, deliberate right-click is never affected.
        """
        was = self._just_closed
        self._just_closed = False
        return was

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802 (Qt override)
        """Flag a just-closed hub for one event-loop turn (D-19, see above)."""
        self._just_closed = True
        QTimer.singleShot(0, self._clear_just_closed)
        super().hideEvent(event)

    def _clear_just_closed(self) -> None:
        self._just_closed = False

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
    # to it directly would run the active tool once per sample, so a completed
    # pick is detected here, from the outside, off each control's own
    # release/edit-finish event rather than off the stream.
    #
    # A harmony/shade/tint swatch is different: its single click must commit
    # THAT SWATCH's own colour (REQ-IS-UI-020/-030), never the wheel's, and
    # must NOT adopt into the wheel — so it is wired directly off
    # ``Colour_Wheel_Widget.swatchPicked`` in ``__init__`` instead of through
    # this generic watcher, and is not one of ``targets`` below.

    def _install_pick_completion_watchers(self) -> List[QWidget]:
        """Wire the wheel's live-stream controls to a discrete completion signal.

        * the wheel pad and the value slider: a left mouse-button release, or
          a (non-autorepeat) ``KeyRelease`` of one of ``_WHEEL_NUDGE_KEYS`` —
          the pad's own keyboard-nudge keys, reused here for the (vertical)
          slider's arrow-key stepping too — caught via an installed event
          filter (:meth:`eventFilter` below);
        * each RGB/HSV numeric spin: ``editingFinished`` (Enter or focus-out),
          never ``valueChanged``, which fires per keystroke while typing.

        For all of the above, the wheel's own current colour IS the
        completing control's colour (REQ-IS-UI-030, REQ-IS-UI-021), so
        :meth:`_on_pick_completed` is called with no argument. Returns the
        widgets an event filter was installed on, kept referenced for the
        hub's lifetime (Qt keeps no reference of its own).
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

    def _on_pick_completed(self, color: Optional[RGBA] = None) -> None:
        """Emit :attr:`colorCommitted` for the completing control's own colour.

        REQ-IS-UI-030 (defect fix): the completing control's colour is
        committed, never a stale ``self._wheel.current_rgba()`` read for a
        control other than the one that actually completed the pick.

        Called with no argument for the wheel pad, the value slider and the
        RGB/HSV numeric entries — those set the wheel directly, so the
        wheel's current colour already IS the completing control's own
        colour (this is also how REQ-IS-UI-021's wheel-pad release is
        satisfied, by the same rule rather than by an exception). Called
        with an explicit ``color`` for a harmony/shade/tint swatch's single
        click (wired to :attr:`Colour_Wheel_Widget.swatchPicked`), whose own
        colour must be committed WITHOUT ever touching the wheel's state.
        """
        if color is None:
            color = self._wheel.current_rgba()
        self.colorCommitted.emit(color)

    # -- slots ------------------------------------------------------------

    def _on_wheel_picked(self, color: QColor) -> None:
        # Applies immediately to the active swatch; leg 1, never refused.
        self.colorApplied.emit(
            (color.red(), color.green(), color.blue(), color.alpha())
        )

    def _on_favourite_picked(self, color: RGBA) -> None:
        # Single click (REQ-IS-UI-019): paint-only, leg 2. The active colour
        # in the circle is deliberately left unchanged — no colorApplied.
        self.colorCommitted.emit(color)

    def _on_favourite_activated(self, color: RGBA) -> None:
        # Double click / Enter / Return (REQ-IS-UI-022): adopt-only, leg 1.
        # Paints nothing — no colorCommitted.
        self._wheel.set_color(QColor(*color))
        self.colorApplied.emit(color)

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
