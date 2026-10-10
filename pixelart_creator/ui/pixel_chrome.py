# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The pixel chrome's painted parts: focus ring, ornaments, pattern, dock frame.

Everything the one application stylesheet (:mod:`pixelart_creator.ui.theme`)
cannot carry is painted here (ADR-0069 decisions 3, 5, 6, 7):

* :class:`Focus_Ring_Widget` -- a transparent overlay child, shown on FocusIn and
  hidden on FocusOut by the application-level :class:`Pixel_Chrome_Filter`
  (the stylesheet carries **no** ``:focus`` rule). Hover, pressed and checked
  fills show through it; a tab bar's ring is refitted to the current tab on
  ``currentChanged``, because arrow-key traversal sends no focus event.
* :class:`Ornament_Widget` -- a corner sprite overlay (the template is the
  top-left master, mirrored for the other corners), placed by the same filter.
* :class:`Pattern_Area_Widget` -- paints the faint pattern in ``paintEvent`` with
  its children's rectangles (plus ``PATTERN_CHILD_CLEARANCE_PX``) clipped out, so
  the pattern never sits under text. It is meant for two empty areas only and
  never for the canvas workspace.
* :class:`Swatch_Button` -- a push button that shows a *data* colour (a tint, a
  tag colour). It is exempt from the framed ``QPushButton`` rule through a
  property selector in the one stylesheet and paints its colour itself.
* :func:`install_dock_frame` / :func:`dock_content` -- the ``DockBody`` frame a
  docked panel is wrapped in (a plain widget does not inset its content by a
  ``border-image``; a ``QFrame`` does).

Overlays compose at their **own widget's** whole-number device-pixel ratio, so
they are exact on every screen independently of the stylesheet's art scale.
No ``QGraphicsEffect``, no OpenGL surface, no translucent top-level (NFR-2).
Colours are roles of the active ``(style, mode)``, set by
:func:`set_active_theme`; none is written here. No domain logic (S11).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPixmap, QRegion
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFrame,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSlider,
    QTabBar,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data import style_catalog
from pixelart_creator.logic.constants import PATTERN_CHILD_CLEARANCE_PX
from pixelart_creator.logic.theme_art import ThemeArtError
from pixelart_creator.ui.theme_art_files import grid_image, template_image

__all__ = [
    "DOCK_BODY_OBJECT_NAME",
    "CORNER_TOP_LEFT",
    "CORNER_TOP_RIGHT",
    "CORNER_BOTTOM_LEFT",
    "CORNER_BOTTOM_RIGHT",
    "DOCK_CORNERS",
    "DIALOG_CORNERS",
    "Focus_Ring_Widget",
    "Ornament_Widget",
    "Pattern_Area_Widget",
    "Swatch_Button",
    "SWATCH_PROPERTY",
    "Pixel_Chrome_Filter",
    "chrome_filter",
    "set_active_theme",
    "active_style",
    "active_mode",
    "install_dock_frame",
    "dock_content",
    "install_ornaments",
    "widget_scale",
]

#: Object name of the frame a docked panel is wrapped in (stylesheet rule target).
DOCK_BODY_OBJECT_NAME = "DockBody"

CORNER_TOP_LEFT = "top-left"
CORNER_TOP_RIGHT = "top-right"
CORNER_BOTTOM_LEFT = "bottom-left"
CORNER_BOTTOM_RIGHT = "bottom-right"
#: Docked docks carry the two bottom corners only (ADR-0069 decision 6).
DOCK_CORNERS: Tuple[str, ...] = (CORNER_BOTTOM_LEFT, CORNER_BOTTOM_RIGHT)
#: Dialogs carry all four corners.
DIALOG_CORNERS: Tuple[str, ...] = (
    CORNER_TOP_LEFT,
    CORNER_TOP_RIGHT,
    CORNER_BOTTOM_LEFT,
    CORNER_BOTTOM_RIGHT,
)

# Template names are data (templates.json); these are the ones the painted
# parts address directly.
_ORNAMENT_TEMPLATE = "ornament"
_RING_BUTTON_KEY = "button_normal"
_RING_FIELD_KEY = "field"
_FRAME_FOR_DOCK = "dock_body"
_FRAME_FOR_DIALOG = "dialog"
_PATTERN_GROUND_ROLE = "background"

# Names of the dynamic properties that mark a widget the filter acts on.
_RING_HOST_PROPERTY = "_pixelRingHost"
_ORNAMENT_HOST_PROPERTY = "_pixelOrnamentHost"

# Structural, not tuning: a device-pixel ratio is whole when within this of an
# integer (guards ``ceil`` against 2.0000000001).
_DPR_EPSILON = 1e-3
_MIN_SCALE = 1

_BUTTON_TYPES = (QPushButton, QToolButton, QTabBar)
_FIELD_TYPES = (
    QLineEdit,
    QAbstractSpinBox,
    QComboBox,
    QAbstractItemView,
    QTextEdit,
    QPlainTextEdit,
    QSlider,
    QCheckBox,
    QRadioButton,
    QGraphicsView,
)
_WATCHED = frozenset(
    {
        QEvent.Type.FocusIn,
        QEvent.Type.FocusOut,
        QEvent.Type.Resize,
        QEvent.Type.Show,
        QEvent.Type.ParentChange,
    }
)

#: Dynamic property that marks a data-colour swatch button; the stylesheet's
#: ``QPushButton[pixelSwatch="true"]`` rules exempt it from the button frame.
SWATCH_PROPERTY = "pixelSwatch"
_LABEL_FOCUS_INTERACTION = (
    Qt.TextInteractionFlag.LinksAccessibleByKeyboard
    | Qt.TextInteractionFlag.TextSelectableByKeyboard
    | Qt.TextInteractionFlag.TextSelectableByMouse
)
_SWATCH_MIN_WIDTH_PX = 32
_SWATCH_INSET_PX = 4

_active: Dict[str, Optional[str]] = {"style": None, "mode": None}


def active_style() -> str:
    """Return the style the painted parts draw in (the default until set)."""
    return _active["style"] or style_catalog.default_style()


def active_mode() -> str:
    """Return the mode the painted parts draw in (the default until set)."""
    return _active["mode"] or style_catalog.default_mode()


def widget_scale(widget: QWidget) -> int:
    """Return the whole-number device-pixel ratio ``widget`` paints at (>= 1)."""
    return max(_MIN_SCALE, math.ceil(widget.devicePixelRatioF() - _DPR_EPSILON))


def set_active_theme(style: str, mode: str) -> None:
    """Record the active ``(style, mode)`` and repaint every painted part."""
    _active["style"] = style
    _active["mode"] = mode
    _pattern_pixmaps.clear()
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    for widget in app.allWidgets():
        if isinstance(widget, Ornament_Widget):
            widget.refresh()
        if isinstance(
            widget, (Focus_Ring_Widget, Ornament_Widget, Pattern_Area_Widget)
        ):
            widget.update()


class Focus_Ring_Widget(QWidget):
    """Transparent overlay that paints the focus ring over a framed control."""

    def __init__(self, parent: QWidget) -> None:
        """Create the ring hidden, mouse-transparent, with no system background."""
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._template = ""
        self.hide()

    def fit(self, rect: QRect, template: str) -> None:
        """Size the ring to ``rect`` (parent coordinates) and show it on top.

        Args:
            rect: The rectangle to cover, in the parent's coordinates.
            template: The ring template name (``focus_ring`` ...).
        """
        self._template = template
        self.setGeometry(rect)
        self.raise_()
        self.show()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the composed ring template at this widget's own scale."""
        if not self._template:
            return
        scale = widget_scale(self)
        try:
            image = template_image(
                active_style(),
                active_mode(),
                self._template,
                self.width(),
                self.height(),
                scale,
            )
        except ThemeArtError:
            return  # too small to carry a ring: draw nothing rather than a smear
        painter = QPainter(self)
        painter.drawImage(self.rect(), image)
        painter.end()


class Ornament_Widget(QWidget):
    """Corner sprite overlay; the template is the top-left master, mirrored."""

    def __init__(self, parent: QWidget, corner: str, frame_template: str) -> None:
        """Create the ornament for ``corner`` of ``parent``.

        Args:
            parent: The dock or dialog the ornament decorates.
            corner: One of the ``CORNER_*`` constants.
            frame_template: The frame template whose ring count is the inset
                (``dock_body`` for docks, ``dialog`` for dialogs).
        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._corner = corner
        self._frame = frame_template
        self.refresh()

    def refresh(self) -> None:
        """Re-read the sprite size of the active style and re-place."""
        template = style_catalog.template_set(active_style()).get(_ORNAMENT_TEMPLATE)
        self.setFixedSize(template.grid.width, template.grid.height)
        self.place()

    def corner(self) -> str:
        """Return the corner this ornament sits in."""
        return self._corner

    def place(self) -> None:
        """Move to the corner of the parent, inside the frame's rings, on top."""
        parent = self.parentWidget()
        if parent is None:
            return
        slices = style_catalog.template_set(active_style()).get(self._frame).slices
        top = self._corner in (CORNER_TOP_LEFT, CORNER_TOP_RIGHT)
        left = self._corner in (CORNER_TOP_LEFT, CORNER_BOTTOM_LEFT)
        inset_x = slices.left if left else slices.right
        inset_y = slices.top if top else slices.bottom
        x = inset_x if left else parent.width() - inset_x - self.width()
        y = inset_y if top else parent.height() - inset_y - self.height()
        self.move(x, y)
        floating = isinstance(parent, QDockWidget) and parent.isFloating()
        self.setVisible(not floating)
        self.raise_()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the mirrored sprite at this widget's own scale."""
        image = template_image(
            active_style(),
            active_mode(),
            _ORNAMENT_TEMPLATE,
            0,
            0,
            widget_scale(self),
            self._corner in (CORNER_TOP_RIGHT, CORNER_BOTTOM_RIGHT),
            self._corner in (CORNER_BOTTOM_LEFT, CORNER_BOTTOM_RIGHT),
        )
        painter = QPainter(self)
        painter.drawImage(self.rect(), image)
        painter.end()


_pattern_pixmaps: Dict[Tuple[str, str, int], QPixmap] = {}


def _pattern_pixmap(scale: int) -> QPixmap:
    """Return the pattern tile of the active theme at ``scale`` (cached)."""
    style, mode = active_style(), active_mode()
    key = (style, mode, scale)
    found = _pattern_pixmaps.get(key)
    if found is None:
        roles = style_catalog.role_map(style, mode)
        grid = style_catalog.template_set(style).pattern.grid
        found = QPixmap.fromImage(grid_image(grid, roles, scale))
        found.setDevicePixelRatio(scale)
        _pattern_pixmaps[key] = found
    return found


class Pattern_Area_Widget(QWidget):
    """An empty area that shows the faint pattern, never under its children."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Create the area; it expands into the space its container leaves."""
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def clip_region(self) -> QRegion:
        """Return the region the pattern may occupy (children clipped out)."""
        region = QRegion(self.rect())
        clearance = PATTERN_CHILD_CLEARANCE_PX
        for child in self.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            if child.isVisibleTo(self):
                grown = child.geometry().adjusted(
                    -clearance, -clearance, clearance, clearance
                )
                region = region.subtracted(QRegion(grown))
        return region

    def paintEvent(self, event: QPaintEvent) -> None:
        """Fill the ground, then tile the pattern inside :meth:`clip_region`."""
        roles = style_catalog.role_map(active_style(), active_mode())
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(roles[_PATTERN_GROUND_ROLE]))
        painter.setClipRegion(self.clip_region())
        painter.drawTiledPixmap(self.rect(), _pattern_pixmap(widget_scale(self)))
        painter.end()


class Swatch_Button(QPushButton):
    """A push button that shows a data colour the user chose (not a theme colour).

    The application stylesheet frames every ``QPushButton`` with an opaque
    ``border-image``, which would hide a per-widget fill. This button carries the
    :data:`SWATCH_PROPERTY` marker instead, so the stylesheet draws it as a plain
    ``border``-role outline (no ``border-image``) and :meth:`paintEvent` fills a
    block with the data colour over it. The colour is data, so it is the one
    colour here that is not a theme role.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Create the button with the swatch marker and a minimum width."""
        super().__init__(parent)
        self.setProperty(SWATCH_PROPERTY, True)
        self.setMinimumWidth(_SWATCH_MIN_WIDTH_PX)
        self._swatch = QColor()

    def set_swatch(self, colour: QColor) -> None:
        """Set the data colour shown and repaint."""
        self._swatch = QColor(colour)
        self.update()

    def swatch(self) -> QColor:
        """Return the data colour shown."""
        return QColor(self._swatch)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Fill the colour block, then draw the outline and label over it."""
        if self._swatch.isValid():
            inset = _SWATCH_INSET_PX
            painter = QPainter(self)
            painter.fillRect(
                self.rect().adjusted(inset, inset, -inset, -inset), self._swatch
            )
            painter.end()
        super().paintEvent(event)


def _framed_target(widget: QWidget) -> QWidget:
    """Return the control that carries the frame ``widget`` is part of."""
    if isinstance(widget, QLineEdit):
        parent = widget.parentWidget()
        if isinstance(parent, (QAbstractSpinBox, QComboBox)):
            return parent
    return widget


def _takes_keyboard_focus(widget: QWidget) -> bool:
    """Return whether ``widget`` is a focus target the overlay rings.

    Any widget with a focus policy other than ``NoFocus``. A label counts only
    when its text is interactive by keyboard or selectable (a link reachable by
    Tab, copyable text); the default mouse-only link flag does not count:
    that is what makes a label a control; a plain label that merely carries a
    focus policy has nothing to ring.
    """
    if widget.focusPolicy() == Qt.FocusPolicy.NoFocus:
        return False
    if isinstance(widget, QLabel):
        return bool(widget.textInteractionFlags() & _LABEL_FOCUS_INTERACTION)
    return True


def _wears_ring(widget: QWidget) -> bool:
    """Return whether ``widget`` is a control the focus overlay rings."""
    return isinstance(widget, _BUTTON_TYPES + _FIELD_TYPES) or _takes_keyboard_focus(
        widget
    )


def _ring_template_name(target: QWidget) -> Optional[str]:
    """Return the ring template for ``target`` (``None`` = no ring)."""
    if isinstance(target, _BUTTON_TYPES):
        key = _RING_BUTTON_KEY
    elif isinstance(target, _FIELD_TYPES) or _takes_keyboard_focus(target):
        key = _RING_FIELD_KEY
    else:
        return None
    if target.window().windowFlags() & Qt.WindowType.Popup == Qt.WindowType.Popup:
        return None
    return style_catalog.template_set(active_style()).focus_rings.get(key)


def _ring_of(target: QWidget) -> Optional[Focus_Ring_Widget]:
    return target.findChild(
        Focus_Ring_Widget, options=Qt.FindChildOption.FindDirectChildrenOnly
    )


def _ring_rect(target: QWidget) -> QRect:
    if isinstance(target, QTabBar) and target.currentIndex() >= 0:
        return target.tabRect(target.currentIndex())
    return target.rect()


class Pixel_Chrome_Filter(QObject):
    """Application event filter: focus rings and ornament placement."""

    def _show_ring(self, target: QWidget) -> None:
        template = _ring_template_name(target)
        if template is None:
            return
        ring = _ring_of(target)
        if ring is None:
            ring = Focus_Ring_Widget(target)
            target.setProperty(_RING_HOST_PROPERTY, True)
            if isinstance(target, QTabBar):
                target.currentChanged.connect(self._on_tab_changed)
        ring.fit(_ring_rect(target), template)

    def _refit(self, target: QWidget) -> None:
        ring = _ring_of(target)
        template = _ring_template_name(target)
        if ring is not None and ring.isVisible() and template is not None:
            ring.fit(_ring_rect(target), template)

    def _on_tab_changed(self, _index: int) -> None:
        sender = self.sender()
        if isinstance(sender, QTabBar):
            self._refit(sender)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """React to focus, resize, show and re-parent events; never consume one."""
        kind = event.type()
        if kind not in _WATCHED or not isinstance(watched, QWidget):
            return False
        if kind == QEvent.Type.FocusIn:
            if _wears_ring(watched):
                self._show_ring(_framed_target(watched))
        elif kind == QEvent.Type.FocusOut:
            if _wears_ring(watched):
                ring = _ring_of(_framed_target(watched))
                if ring is not None:
                    ring.hide()
        else:
            if watched.property(_RING_HOST_PROPERTY):
                self._refit(watched)
            if watched.property(_ORNAMENT_HOST_PROPERTY):
                for ornament in watched.findChildren(
                    Ornament_Widget, options=Qt.FindChildOption.FindDirectChildrenOnly
                ):
                    ornament.place()
        return False


def chrome_filter(app: QApplication) -> Pixel_Chrome_Filter:
    """Return the application's one :class:`Pixel_Chrome_Filter` (installed once)."""
    found = app.findChild(Pixel_Chrome_Filter)
    if found is None:
        found = Pixel_Chrome_Filter(app)
        app.installEventFilter(found)
    return found


def install_ornaments(
    host: QWidget, corners: Tuple[str, ...], *, dialog: bool = False
) -> List[Ornament_Widget]:
    """Attach corner ornaments to ``host`` (a dock or a dialog) and place them.

    Args:
        host: The widget to decorate.
        corners: The ``CORNER_*`` constants to decorate (``DOCK_CORNERS`` or
            ``DIALOG_CORNERS``).
        dialog: ``True`` for a dialog (inset from the ``dialog`` frame's
            rings), ``False`` for a dock (the ``dock_body`` frame's).

    Returns:
        The ornaments created; the application filter keeps them placed.
    """
    frame = _FRAME_FOR_DIALOG if dialog else _FRAME_FOR_DOCK
    host.setProperty(_ORNAMENT_HOST_PROPERTY, True)
    made = [Ornament_Widget(host, corner, frame) for corner in corners]
    for ornament in made:
        ornament.place()
    return made


def install_dock_frame(dock: QDockWidget) -> QFrame:
    """Wrap ``dock``'s content in the ``DockBody`` frame (idempotent).

    Call this at every dock-creation site after ``setWidget``. The content
    keeps its identity; reach it with :func:`dock_content`, never
    ``dock.widget()``.

    Returns:
        The ``DockBody`` frame (now ``dock.widget()``).
    """
    current = dock.widget()
    if isinstance(current, QFrame) and current.objectName() == DOCK_BODY_OBJECT_NAME:
        return current
    body = QFrame()
    body.setObjectName(DOCK_BODY_OBJECT_NAME)
    layout = QVBoxLayout(body)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    hidden = current is not None and current.isHidden()
    dock.setWidget(body)
    if current is not None:
        layout.addWidget(current)
        current.setHidden(hidden)
    return body


def dock_content(dock: QDockWidget) -> Optional[QWidget]:
    """Return the panel inside ``dock``, whether or not it is wrapped."""
    widget = dock.widget()
    if isinstance(widget, QFrame) and widget.objectName() == DOCK_BODY_OBJECT_NAME:
        layout = widget.layout()
        item = layout.itemAt(0) if layout is not None else None
        return item.widget() if item is not None else None
    return widget
