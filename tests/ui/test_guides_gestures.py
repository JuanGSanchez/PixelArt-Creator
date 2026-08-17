"""D-11 acceptance: guide drag-to-move + both removal gestures
(REQ-P9-UI-003, ``Canvas_View`` + ``Guides_Overlay``).

The audit finding (CF-27): only guide *creation* existed; nothing moved or
removed a placed guide. This proves, through the real ``Canvas_View`` mouse
dispatch (never calling ``Guides_Overlay.move_guide``/``remove_guide``
directly), that: (1) dragging an existing guide replaces the frozen
``Guide`` at its new position; (2) dragging a guide off the canvas removes
it via the PUBLIC ``remove_guide``; (3) the right-click context action also
removes it via the same PUBLIC method. Both themes via the autouse ``theme``
fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF

from pixelart_creator.logic.guides import GuideOrientation
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay
from tests.ui._ui_helpers import drag_path

_RECT64 = QRectF(0, 0, 64, 64)


def _rig(make_view):
    view, scene, stack = make_view(64, 64)
    guides = Guides_Rulers_Overlay(view, scene, _RECT64)
    guides.set_enabled(True)
    view.set_guides_overlay(guides)
    return view, scene, guides


def test_d11_drag_moves_the_guide_to_its_new_position(make_view):
    """D-11: dragging an existing guide replaces it with one at the new position
    (``Guide`` is frozen — the overlay's ``move_guide`` remove-then-adds)."""
    view, scene, guides = _rig(make_view)
    original = guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)

    # Press ON the guide (within its snap tolerance) starts the drag, not a
    # paint stroke — Canvas_View._hit_test_guide takes over the gesture.
    drag_path(view, [(10, 5), (25, 5)])

    remaining = guides.overlay_item().guides()
    assert len(remaining) == 1
    assert remaining[0] is not original  # a NEW Guide instance (frozen -> replaced)
    assert remaining[0].position == 25.0
    assert remaining[0].orientation is GuideOrientation.VERTICAL


def test_d11_drag_off_canvas_removes_the_guide_via_public_remove_guide(make_view):
    """D-11: dragging a guide past the scene bounds removes it (public seam)."""
    view, scene, guides = _rig(make_view)
    guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)
    assert len(guides.overlay_item().guides()) == 1

    # Start the drag on the guide, then finish the release far outside the
    # scene rect (below) rather than via drag_path's own release, since the
    # helper only accepts in-bounds pixel coordinates.
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from tests.ui._ui_helpers import press

    press(view, 10, 5)

    # Manually finish the release far outside the scene rect (x=200 > width 64).
    pt = QPointF(200.0, 5.0)
    evt = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        pt,
        pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseReleaseEvent(evt)

    assert guides.overlay_item().guides() == ()


class _FakeSignal:
    """A minimal stand-in for a Qt signal: records connected slots, fires them."""

    def __init__(self) -> None:
        self._slots: list = []

    def connect(self, fn) -> None:  # noqa: ANN001
        self._slots.append(fn)

    def emit(self) -> None:
        for fn in self._slots:
            fn()


class _FakeAction:
    """Records an action's text/enabled flag + a real ``triggered`` connect/emit."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._enabled = True
        self.triggered = _FakeSignal()

    def setEnabled(self, value: bool) -> None:  # noqa: N802 (Qt API shape)
        self._enabled = value

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def text(self) -> str:
        return self._text

    def trigger(self) -> None:
        self.triggered.emit()


class _FakeMenu:
    """A no-exec ``QMenu`` stand-in (the established pattern in
    ``test_canvas_view.py::_FakeMenu``) so the modal ``exec()`` never blocks
    headless — patching ``QMenu.exec`` directly does NOT reliably intercept
    the underlying C++ call and hangs; replacing the class reference the
    module uses does."""

    instances: list = []

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        self._actions: list = []
        _FakeMenu.instances.append(self)

    def addAction(self, text):  # noqa: N802, ANN001
        action = _FakeAction(text)
        self._actions.append(action)
        return action

    def actions(self):
        return list(self._actions)

    def exec(self, *args, **kwargs):  # noqa: A003
        return None  # never enters a modal loop


def test_d11_context_action_removes_the_guide_via_public_remove_guide(
    make_view, monkeypatch
):
    """D-11: the right-click "Remove guide" context action also reaches the
    PUBLIC ``remove_guide`` — the alternative to drag-off-canvas."""
    view, scene, guides = _rig(make_view)
    guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)
    assert len(guides.overlay_item().guides()) == 1

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.canvas_view.QMenu", _FakeMenu)

    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    pt = QPointF(10.0, 5.0)
    evt = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pt,
        pt,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(evt)

    assert _FakeMenu.instances, "the guide context menu was not built"
    menu = _FakeMenu.instances[-1]
    actions = menu.actions()
    assert len(actions) == 1
    assert actions[0].text() == "Remove guide"
    assert actions[0].isEnabled() is True

    actions[0].trigger()

    assert guides.overlay_item().guides() == ()
