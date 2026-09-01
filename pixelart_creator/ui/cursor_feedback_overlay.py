"""Transient cursor-feedback overlay (REQ-IS-UI-024..026) — Qt only, presentation-only.

:class:`Cursor_Feedback_Overlay` is a small ``QWidget`` **child of a painting view's
``viewport()``**, never a ``QGraphicsItem`` on the scene (plan.md §3.3 RULING). That
placement makes ``REQ-IS-UI-026`` clause 2 — "neither square MUST be captured into an
export, a saved project, or a rendered frame" — a structural fact rather than a
discipline someone has to keep remembering: a viewport child is outside every
``QGraphicsScene.render()`` call by construction.

Two presentation events, nothing else:

* :meth:`show_colour` draws a square filled with the given colour **to the left of**
  the cursor (a colour change).
* :meth:`show_icon` draws a square containing the given icon **on top of** the cursor
  (a tool change).

Both share the same 24-logical-px, DPI-scaled edge, the same 10%-of-edge padding
(computed here, at the call site, from ``FEEDBACK_SQUARE_PX *
FEEDBACK_SQUARE_PAD_RATIO`` — the ``2.4`` value itself is never written down, plan.md
§3.3), and the same one-second show-then-fade animation. A second call **restarts**
the animation from the beginning rather than queueing behind the first
(``REQ-IS-UI-024``/``-025``); there is deliberately no queue, no stacking and no
notification-type registry (plan.md §3.3 "Extension point, named honestly").

**DPI scaling.** The square's *logical* size is set once, in logical px, on the
widget itself (``FEEDBACK_SQUARE_PX``). No ``devicePixelRatio()`` factor is applied by
hand: like ``Real_Size_Preview_Window`` (``ui/real_size_preview_window.py``), a plain
``QWidget`` is painted onto a backing store Qt itself scales by the screen's device
pixel ratio, so multiplying manually here would double-scale on HiDPI. That is what
makes the square's *device* size come out proportional to the *logical* size for free
(``SC-U024-3``).

**Cursor tracking without taking input.** The overlay never receives mouse events
itself (``WA_TransparentForMouseEvents``); instead it installs an event filter on the
host viewport and watches ``QEvent.MouseMove`` there, purely to reposition itself
while visible (``SC-U024-6``). The filter never consumes the event (always returns
``False``), so every click and move still reaches the widget underneath in full
(``SC-U024-7``).

**Deterministic animation (NFR-5).** The fade is a single ``QVariantAnimation`` over
opacity with three keyframes — held at ``1.0`` until the leading
``1 - FEEDBACK_FADE_TAIL_RATIO`` of the duration, then falling to ``0.0`` over the
final ``FEEDBACK_FADE_TAIL_RATIO``. ``QVariantAnimation.setCurrentTime(ms)`` can drive
it directly, with no ``start()`` and no wall-clock sleep, so a test can advance it to
an exact millisecond and assert the resulting opacity — the animation object is
exposed as the public attribute :attr:`animation` for exactly that purpose.

**Who decides which square.** This module answers "draw this square here for this
long"; it never answers "which square". ``ui/main_window.py`` already owns the
colour-change and tool-change events and decides *when* to call :meth:`show_colour` /
:meth:`show_icon` — including suppressing the call entirely during an active stroke
(``REQ-IS-UI-026`` clause 1). This widget holds no reference to a ``Favourites``, a
``Document``, a ``tool_id``, or any signal from either.

**Import allow-list (plan.md §3.3, load-bearing).** This module's import set is
*exactly* ``PySide6.QtCore``, ``PySide6.QtGui``, ``PySide6.QtWidgets`` plus one
``pixelart_creator.logic.constants`` import for the four feedback scalars — nothing
else, ever. ``check_layering`` cannot see a ``ui -> ui`` edge, so a second domain
import here is a back door that script cannot catch; task T-19 adds an AST-based test
that is the actual gate.
"""

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

from pixelart_creator.logic.constants import (
    FEEDBACK_DURATION_MS,
    FEEDBACK_FADE_TAIL_RATIO,
    FEEDBACK_SQUARE_PAD_RATIO,
    FEEDBACK_SQUARE_PX,
)

#: Progress fraction (0..1 of FEEDBACK_DURATION_MS) at which the fall to zero begins.
_FADE_START_PROGRESS = 1.0 - FEEDBACK_FADE_TAIL_RATIO


class Cursor_Feedback_Overlay(QWidget):
    """Draws the transient colour/tool feedback square over a painting viewport.

    Construct one per painting surface (``Canvas_View`` and ``Tilemap_Canvas`` each
    get their own instance over their own ``viewport()``); the constructor's only
    parameter is that viewport, so a third painting surface costs zero new classes
    (plan.md §3.3).
    """

    def __init__(self, viewport: QWidget) -> None:
        """Build the hidden overlay and wire it to track ``viewport``'s cursor.

        Makes the widget input-transparent and translucent, fixes it to the
        24-logical-px feedback square, sets its accessible name, builds the
        three-keyframe show-then-fade :attr:`animation` (started later by
        :meth:`_restart`), then enables mouse tracking on ``viewport`` and
        installs ``self`` as its event filter so cursor moves reposition the
        square (``SC-U024-6``). The overlay starts hidden.
        """
        super().__init__(viewport)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(self.tr("Cursor feedback"))

        self.setFixedSize(FEEDBACK_SQUARE_PX, FEEDBACK_SQUARE_PX)

        self._mode: str | None = None  # "colour" | "icon"
        self._color: QColor | None = None
        self._icon: QIcon | None = None
        self._opacity: float = 0.0
        self._cursor_pos: QPoint = QPoint(0, 0)

        self.animation = QVariantAnimation(self)
        self.animation.setDuration(FEEDBACK_DURATION_MS)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.setKeyValueAt(0.0, 1.0)
        self.animation.setKeyValueAt(_FADE_START_PROGRESS, 1.0)
        self.animation.setKeyValueAt(1.0, 0.0)
        self.animation.valueChanged.connect(self._on_opacity_changed)

        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)

        self.hide()

    # ------------------------------------------------------------------ #
    # Public API — the shell decides which square; this widget only draws it.
    # ------------------------------------------------------------------ #

    def show_colour(self, rgba: tuple[int, int, int, int]) -> None:
        """Show a square filled with ``rgba`` to the left of the cursor.

        Restarts the animation from the beginning if one is already in progress
        (``REQ-IS-UI-024``).
        """
        self._mode = "colour"
        self._color = QColor(*rgba)
        self._icon = None
        self._restart()

    def show_icon(self, icon: QIcon) -> None:
        """Show a square containing ``icon`` on top of the cursor.

        Restarts the animation from the beginning if one is already in progress
        (``REQ-IS-UI-025``).
        """
        self._mode = "icon"
        self._icon = icon
        self._color = None
        self._restart()

    # ------------------------------------------------------------------ #
    # i18n hook (F5/F6) — no visible text is drawn, but the accessible name is.
    # ------------------------------------------------------------------ #

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override name)
        """Re-set the accessible name on ``QEvent.LanguageChange`` (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self.setAccessibleName(self.tr("Cursor feedback"))
        super().changeEvent(event)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _restart(self) -> None:
        self.animation.stop()
        self.animation.setCurrentTime(0)
        self._opacity = 1.0
        self._position_at_cursor()
        self.show()
        self.raise_()
        self.update()
        self.animation.start()

    def _on_opacity_changed(self, value: object) -> None:
        self._opacity = float(value)  # type: ignore[arg-type]
        if self._opacity <= 0.0:
            self.hide()
        self.update()

    def _position_at_cursor(self) -> None:
        edge = FEEDBACK_SQUARE_PX
        pad = FEEDBACK_SQUARE_PX * FEEDBACK_SQUARE_PAD_RATIO
        cx, cy = self._cursor_pos.x(), self._cursor_pos.y()
        if self._mode == "colour":
            # To the left of the cursor: the square's right edge sits `pad` before it.
            x = cx - pad - edge
            y = cy - edge / 2
        else:
            # On top of the cursor: centred on it.
            x = cx - edge / 2
            y = cy - edge / 2
        self.move(round(x), round(y))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Track the host viewport's mouse moves and reposition while visible.

        Installed on the host viewport in :meth:`__init__`; never consumes
        the event (always returns ``False``), so every click and move still
        reaches the widget underneath in full (``SC-U024-7``).
        """
        if event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            self._cursor_pos = event.position().toPoint()
            if self.isVisible():
                self._position_at_cursor()
        return False  # never consume — the square takes no input (REQ-IS-UI-024)

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override name)
        """Fill or paint the feedback square at the current fade opacity."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setOpacity(self._opacity)
        rect = self.rect()
        if self._mode == "colour" and self._color is not None:
            painter.fillRect(rect, self._color)
        elif self._mode == "icon" and self._icon is not None:
            self._icon.paint(painter, rect)
        painter.end()
