"""Canvas navigation + seam acceptance tests (REQ-P1-UI-004,-005,-007,-008).

Scenarios SC-UI-004-1/-2 (+ presets/ZOOM_MAX), SC-UI-005-1/-2, SC-UI-007-3,
SC-UI-008-1/-2. Both themes via the autouse fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QTransform, QWheelEvent

from pixelart_creator.logic.constants import (
    SCALE_FACTOR,
    ZOOM_MAX,
    ZOOM_PRESET_STOPS,
)
from tests.ui._ui_helpers import (
    LEFT,
    MIDDLE,
    RIGHT,
    prepare_for_click,
    press,
    press_space,
    release,
)

# -- REQ-P1-UI-004 (zoom) -------------------------------------------------


def test_sc_ui_004_1_zoom_clamped_to_range(make_view):
    """SC-UI-004-1: zoom clamps to [fit .. ZOOM_MAX]."""
    view, _scene, _stack = make_view(1024, 1024)
    view.set_zoom(ZOOM_MAX * 100.0)
    assert view.zoom() == pytest.approx(ZOOM_MAX)
    fit = view._fit_zoom()
    view.set_zoom(fit / 1000.0)
    assert view.zoom() == pytest.approx(fit)
    assert view.zoom() >= fit


def test_sc_ui_004_2_wheel_notch_scales_by_step(make_view):
    """SC-UI-004-2: one wheel notch scales zoom by the SCALE_FACTOR step."""
    view, _scene, _stack = make_view(1024, 1024)
    view.set_zoom(4.0)  # well within [fit .. ZOOM_MAX]
    start = view.zoom()
    wheel = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),  # positive angle delta => zoom in
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    view.wheelEvent(wheel)
    assert view.zoom() == pytest.approx(start * (1.0 + SCALE_FACTOR))


def test_sc_ui_004_presets_and_zoom_max(make_view):
    """SC-UI-004 (presets): keyboard zoom snaps to preset stops up to ZOOM_MAX."""
    view, _scene, _stack = make_view(1024, 1024)
    view.set_zoom(1.0)
    view.zoom_in()
    assert view.zoom() == pytest.approx(ZOOM_PRESET_STOPS[1])  # 1.0 -> 2.0
    view.zoom_out()
    assert view.zoom() == pytest.approx(ZOOM_PRESET_STOPS[0])  # 2.0 -> 1.0
    view.set_zoom(ZOOM_MAX)
    view.zoom_in()  # already at the ceiling
    assert view.zoom() == pytest.approx(ZOOM_MAX)


def test_sc_ui_004_zoom_changed_signal(make_view, qtbot):
    """A zoom change emits zoomChanged with the new scale (observable, -004)."""
    view, _scene, _stack = make_view(1024, 1024)
    with qtbot.waitSignal(view.zoomChanged, timeout=1000) as blocker:
        view.set_zoom(8.0)
    assert blocker.args[0] == pytest.approx(8.0)


# -- REQ-P1-UI-005 (pan) --------------------------------------------------


def _mouse(view, etype, x, y, button, buttons):
    pt = QPointF(x, y)
    return QMouseEvent(etype, pt, pt, button, buttons, Qt.KeyboardModifier.NoModifier)


def test_sc_ui_005_1_middle_drag_pans_without_painting(make_view):
    """SC-UI-005-1: middle-drag pans; no pixel changes, no command pushed."""
    view, scene, stack = make_view(64, 64)
    before = scene.active_buffer().copy()
    press(view, 10, 10, MIDDLE)
    assert view._panning is True  # pan engaged, not a paint
    view.mouseMoveEvent(
        _mouse(view, QEvent.Type.MouseMove, 20, 20, Qt.MouseButton.NoButton, MIDDLE)
    )
    release(view, 20, 20, MIDDLE)
    assert view._panning is False
    assert scene.active_buffer() == before
    assert stack.count() == 0


def test_sc_ui_005_2_space_left_drag_pans_without_painting(make_view):
    """SC-UI-005-2: Space+left-drag pans; nothing is painted."""
    view, scene, stack = make_view(64, 64)
    before = scene.active_buffer().copy()
    press_space(view)
    press(view, 5, 5, LEFT)
    assert view._panning is True  # Space modifier turns left-drag into a pan
    release(view, 15, 15, LEFT)
    assert scene.active_buffer() == before
    assert stack.count() == 0


# -- REQ-P1-UI-007 (snapping) --------------------------------------------


def test_sc_ui_007_3_snapping_floors_to_whole_pixel(make_view):
    """SC-UI-007-3: a sub-pixel scene point resolves to the floored pixel."""
    view, _scene, _stack = make_view(64, 64)
    prepare_for_click(view)
    view.setTransform(QTransform().scale(10, 10))  # 1 buffer px = 10 device px
    view.horizontalScrollBar().setValue(0)  # pin origin after re-ranging
    view.verticalScrollBar().setValue(0)
    # Viewport (105, 75) -> scene (10.5, 7.5) -> floored pixel (10, 7).
    evt = _mouse(view, QEvent.Type.MouseButtonPress, 105, 75, LEFT, LEFT)
    assert view._pixel_at(evt) == (10, 7)


# -- REQ-P1-UI-008 (right-click seam) ------------------------------------


def test_sc_ui_008_1_right_click_dispatches_with_coord(make_view, qtbot):
    """SC-UI-008-1: right-click invokes the menu hook once with the pixel."""
    view, _scene, _stack = make_view(64, 64)
    calls = []
    view.set_menu_hook(lambda x, y: calls.append((x, y)))
    with qtbot.waitSignal(view.rightClicked, timeout=1000) as blocker:
        press(view, 9, 9, RIGHT)
    assert blocker.args == [9, 9]
    assert calls == [(9, 9)]


class _FakeAction:
    """Records an action's text + enabled flag without a real QAction/menu."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._enabled = True

    def setEnabled(self, value: bool) -> None:  # noqa: N802 (Qt API shape)
        self._enabled = value

    def isEnabled(self) -> bool:  # noqa: N802
        return self._enabled

    def text(self) -> str:
        return self._text


class _FakeMenu:
    """A no-exec stand-in for QMenu so the placeholder path never blocks."""

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


def test_sc_ui_008_2_default_hook_shows_placeholder_only(make_view, monkeypatch):
    """SC-UI-008-2: the Phase-1 default hook shows a placeholder, no colour hub."""
    view, _scene, _stack = make_view(64, 64)
    _FakeMenu.instances.clear()
    # Replace the QMenu the view module builds so the modal exec is a no-op.
    monkeypatch.setattr("pixelart_creator.ui.canvas_view.QMenu", _FakeMenu)
    press(view, 3, 3, RIGHT)  # no hook registered -> placeholder path
    assert _FakeMenu.instances, "the placeholder menu was not created"
    menu = _FakeMenu.instances[-1]
    actions = menu.actions()
    assert len(actions) == 1  # a single placeholder entry
    assert actions[0].isEnabled() is False  # non-interactive placeholder
    text = actions[0].text().lower()
    assert "wheel" not in text and "favourite" not in text and "favorite" not in text
