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
from pixelart_creator.ui.guides_rulers_overlay import (
    Guides_Overlay,
    Guides_Rulers_Overlay,
)
from testing.suites.ui._ui_helpers import drag_path, viewport_point_for_pixel

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

    from testing.suites.ui._ui_helpers import press

    press(view, 10, 5)

    # Manually finish the release genuinely off-canvas: a scene point well
    # past the document's own right edge (never a raw viewport-space literal
    # like x=200 -- Canvas_View inflates its own scrollable rect by a pan
    # margin of half a viewport on every side, REQ-CGS-UI-009, so a
    # viewport-space literal's off-canvas-ness would depend on viewport size
    # rather than being guaranteed by construction). scene.sceneRect() is the
    # document's own untouched rect (F3); +20 scene units past its right edge
    # is unambiguously off-document regardless of pan-margin size.
    off_canvas_scene_pt = QPointF(scene.sceneRect().width() + 20.0, 5.0)
    release_vp = view.mapFromScene(off_canvas_scene_pt)
    pt = QPointF(release_vp.x(), release_vp.y())
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


def test_d11_drag_just_past_document_edge_removes_the_guide_via_public_remove_guide(
    make_view,
):
    """D-11 regression guard (REQ-CGS-UI-009): a release only ONE scene unit
    past the document's own edge must still count as off-canvas.

    The sibling test above releases the guide ``scene.sceneRect().width() +
    20`` -- comfortably outside the document, but that ``+20`` is still a
    FIXED offset, not a proof against every pan-margin size. ``Canvas_View``
    inflates its OWN scrollable rect (``self.sceneRect()``, distinct from the
    document's ``scene.sceneRect()``) by half a viewport in scene units on
    every side (``_apply_pan_margin``). If the drop-off-canvas check ever
    regressed back to reading that inflated view rect instead of
    ``_content_rect()`` (the document's own, untouched rect), a margin bigger
    than ``20`` scene units -- trivially reached by a wide-enough viewport --
    would make the buggy check still ``contains()`` the ``+20`` release
    point, so that sibling test's green would NOT be evidence the fix holds.

    Releasing just past the edge -- ``width + 1`` -- closes that gap: for the
    buggy inflated-rect check to wrongly call this point "still on canvas",
    the pan margin would have to be SMALLER than a single scene unit, which
    ``_apply_pan_margin`` (half a viewport, plus a pixel of rounding slack)
    never produces for any real viewport. So this assertion fails against an
    inflated ``self.sceneRect()`` check at any margin the view could
    plausibly compute, however large the window; only the semantic
    ``_content_rect()`` check makes it pass.
    """
    view, scene, guides = _rig(make_view)
    guide = guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)
    assert len(guides.overlay_item().guides()) == 1

    # Spy on the PUBLIC ``remove_guide`` itself (never private state) so the
    # removal is confirmed to go through that exact seam, not merely
    # inferred from the guides() outcome -- while still delegating to the
    # real implementation, so the guide is genuinely removed.
    calls: list = []
    real_remove_guide = Guides_Overlay.remove_guide

    def _spy_remove_guide(self, guide_arg):  # noqa: ANN001
        calls.append(guide_arg)
        return real_remove_guide(self, guide_arg)

    import unittest.mock as _mock

    with _mock.patch.object(Guides_Overlay, "remove_guide", _spy_remove_guide):
        # Start the drag on the guide, exactly as the sibling test does.
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent

        from testing.suites.ui._ui_helpers import press

        press(view, 10, 5)

        # Just past the document's own right edge -- +1 scene unit, not the
        # sibling's +20 (see docstring): the tightest release point that
        # still unambiguously counts as off-document (F3), immune to any
        # plausible pan-margin size rather than merely a margin under 20.
        off_canvas_scene_pt = QPointF(scene.sceneRect().width() + 1.0, 5.0)
        release_vp = view.mapFromScene(off_canvas_scene_pt)
        pt = QPointF(release_vp.x(), release_vp.y())
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
    assert calls == [guide], "removal did not go through the PUBLIC remove_guide"


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

    # Target document pixel (10, 5) -- where the guide was added -- via the
    # view's own CURRENT mapping (view.mapFromScene), never a hand-computed
    # offset; see _ui_helpers.viewport_point_for_pixel.
    point = viewport_point_for_pixel(view, 10, 5)
    pt = QPointF(point.x(), point.y())
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
