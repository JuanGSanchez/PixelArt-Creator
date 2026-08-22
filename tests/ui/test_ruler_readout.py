"""Ruler cursor-coordinate readout acceptance tests (job REC-4/R-5/C-5, DEV-27).

Covers **REQ-P9-UI-003**'s live coordinate readout half specifically: before
this fix, ``Ruler_Strip.set_cursor_readout`` had zero production callers (the
DEV-27 finding) and its ``paintEvent`` never read the ``_cursor_doc`` field it
wrote. The fix installs a real ``QObject.eventFilter`` on the
``Canvas_View``'s viewport (``Guides_Rulers_Overlay.__init__`` ->
``view.viewport().installEventFilter(self)``); this module drives that exact
production path by delivering real ``QMouseEvent``/``QEvent.Leave`` events
THROUGH ``QApplication.sendEvent`` at the viewport (which is what dispatches
to installed event filters) -- not by calling ``Ruler_Strip.set_cursor_readout``
directly, which would prove nothing about the DEV-27 gap (a direct call was
already possible before the fix; the defect was that nothing production made
that call).

``Guides_Rulers_Overlay`` is constructed directly over a real, production
``Canvas_View`` from the shared ``make_view`` fixture -- the same pattern the
already-shipped ``tests/ui/test_guides_rulers.py`` uses; the class under test
IS the production class, so this is not a test double. Both themes run
automatically (the autouse ``theme`` fixture); the readout does not depend on
theme, only its pen colour does (unchanged by this fix).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.guides import coordinate_readout
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay

NO_MOD = Qt.KeyboardModifier.NoModifier
NO_BTN = Qt.MouseButton.NoButton


def _controller(make_view, w=64, h=64, enabled=True):
    view, scene, stack = make_view(w, h)
    controller = Guides_Rulers_Overlay(view, scene, QRectF(0, 0, w, h))
    controller.set_enabled(enabled)
    return controller, view, scene, stack


def _move_event(x: float, y: float) -> QMouseEvent:
    pt = QPointF(x, y)
    return QMouseEvent(QEvent.Type.MouseMove, pt, pt, NO_BTN, NO_BTN, NO_MOD)


# --------------------------------------------------------------------------- #
# C-5: cursor movement over the viewport feeds the readout (event filter)    #
# --------------------------------------------------------------------------- #


def test_c5_viewport_mouse_move_feeds_the_ruler_readout_via_event_filter(make_view):
    """REQ-P9-UI-003: a real mouse-move over the canvas viewport reaches
    ``Ruler_Strip.set_cursor_readout`` through the installed event filter --
    the production feed that did not exist before this fix (DEV-27)."""
    controller, view, _scene, _stack = _controller(make_view)
    h_ruler = controller.horizontal_ruler()
    v_ruler = controller.vertical_ruler()
    assert h_ruler._cursor_doc is None
    assert v_ruler._cursor_doc is None

    viewport = view.viewport()
    app = QApplication.instance()
    assert app is not None
    # prepare_for_click (applied by make_view) pins the view to identity
    # transform + zero pan, so viewport point (30, 10) maps to scene (30, 10).
    app.sendEvent(viewport, _move_event(30.4, 10.4))

    expected_x, expected_y = coordinate_readout(30.0, 10.0, view.zoom(), (0.0, 0.0))
    assert h_ruler._cursor_doc == expected_x
    assert v_ruler._cursor_doc == expected_y


def test_c5_ruler_paints_a_readout_marker_once_fed(make_view):
    """The readout is not just stored -- ``Ruler_Strip.paintEvent`` reads
    ``_cursor_doc`` and paints a marker; a ruler with no readout paints a
    different image than the same ruler once fed a real cursor position."""
    from PySide6.QtGui import QPixmap

    controller, view, _scene, _stack = _controller(make_view)
    h_ruler = controller.horizontal_ruler()
    h_ruler.resize(200, 20)

    before = QPixmap(h_ruler.size())
    h_ruler.render(before)

    viewport = view.viewport()
    QApplication.instance().sendEvent(viewport, _move_event(30.4, 10.4))
    assert h_ruler._cursor_doc is not None  # sanity: the feed landed

    after = QPixmap(h_ruler.size())
    h_ruler.render(after)

    assert after.toImage() != before.toImage()  # the marker actually painted


def test_c5_leave_event_clears_the_readout_via_event_filter(make_view):
    """A ``QEvent.Leave`` on the viewport clears the readout on both strips."""
    controller, view, _scene, _stack = _controller(make_view)
    h_ruler = controller.horizontal_ruler()
    v_ruler = controller.vertical_ruler()
    viewport = view.viewport()
    app = QApplication.instance()

    app.sendEvent(viewport, _move_event(15.4, 15.4))
    assert h_ruler._cursor_doc is not None
    assert v_ruler._cursor_doc is not None

    app.sendEvent(viewport, QEvent(QEvent.Type.Leave))
    assert h_ruler._cursor_doc is None
    assert v_ruler._cursor_doc is None


def test_c5_readout_feed_is_gated_on_the_aid_being_enabled(make_view):
    """When the guides/rulers aid is OFF, a viewport mouse-move feeds nothing
    (the filter's own ``self._enabled`` gate, ``guides_rulers_overlay.py``)."""
    controller, view, _scene, _stack = _controller(make_view, enabled=False)
    assert controller.is_enabled() is False
    h_ruler = controller.horizontal_ruler()

    QApplication.instance().sendEvent(view.viewport(), _move_event(30.4, 10.4))

    assert h_ruler._cursor_doc is None
