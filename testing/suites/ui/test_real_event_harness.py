"""Harness self-tests for the real-Qt-event helpers (``testing/suites/ui/_ui_helpers.py``).

Context (verified this session): every other module in
``testing/suites/ui`` that exercises ``Canvas_View`` drives it through
``view.mousePressEvent(...)``/``mouseMoveEvent``/``mouseReleaseEvent`` called
DIRECTLY (see ``_ui_helpers.press``/``release``/``click_pixel``). A direct
handler call bypasses viewport hit-testing, widget geometry, event filters,
overlay stacking and transform mapping -- exactly the layers a real mouse
click passes through and exactly where a reported "left-click does not paint"
defect could live invisibly. ``real_click_pixel``/``real_right_click_pixel``
(and friends) close that gap: they deliver an actual ``QTest`` mouse event to
``view.viewport()``, mapped from DOCUMENT pixel coordinates through the
view's own live ``mapFromScene``, and raise loudly instead of silently
clicking empty scene when the requested pixel is not visible.

These are HARNESS self-tests, not regression tests for the reported
paint/layout/zoom defects -- those land in a later wave once the fixes do.
Each test drives ``Canvas_View`` to a state it pins itself (explicit
``resize`` + ``show`` + ``prepare_for_click``, a document size and a paint
colour it chooses), never relying on ``Main_Window``'s pane width or on
whatever zoom the widget starts at, so this module stays correct while the
layout/zoom values are being changed concurrently elsewhere in this same
worktree (a different agent's work; not touched here). Both light and dark
theme run via the suite's autouse ``theme`` fixture, same as every other
module in this directory.
"""

from __future__ import annotations

import pytest

from pixelart_creator.ui.tools import PencilTool
from testing.suites.ui._ui_helpers import (
    ViewportTargetError,
    prepare_for_click,
    real_click_pixel,
    real_right_click_pixel,
    viewport_point_for_pixel,
)

# Deliberately larger than the document: leaves a visible strip of viewport
# space beyond the document's own pixels for the "outside document, inside
# viewport" scenario below.
DOC_SIZE = 64
VIEWPORT_SIZE = 200
PAINT_COLOR = (10, 20, 30, 255)


def _prepared_view(make_view, qtbot):
    """Build a ``Canvas_View`` driven to a known, self-contained state.

    Resizes + shows the widget (real geometry is required for a real Qt
    event to hit-test correctly under ``QT_QPA_PLATFORM=offscreen``), then
    pins zoom=1.0 + top-left alignment + zero scroll via
    ``prepare_for_click`` -- a fixed invariant of the helper module itself,
    not of any concurrently-changing product default -- and arms the pencil
    tool with a colour this test chooses.
    """
    view, scene, stack = make_view(DOC_SIZE, DOC_SIZE)
    view.resize(VIEWPORT_SIZE, VIEWPORT_SIZE)
    view.show()
    qtbot.waitExposed(view)
    prepare_for_click(view)  # zoom=1.0, AlignLeft|AlignTop, scroll (0, 0)
    view.set_tool(PencilTool())
    view.set_active_color(PAINT_COLOR)
    return view, scene, stack


def test_real_left_click_inside_document_paints_exactly_that_pixel(make_view, qtbot):
    """A real ``QTest`` click at a document pixel INSIDE the document paints it."""
    view, scene, stack = _prepared_view(make_view, qtbot)
    target = (10, 10)
    before_count = stack.count()

    real_click_pixel(view, *target)

    assert scene.active_buffer().get_pixel(*target) == PAINT_COLOR
    assert stack.count() == before_count + 1

    # Nothing was painted anywhere else on the same row/column edge (a loose
    # mapping bug would tend to paint the neighbour instead of the target).
    assert scene.active_buffer().get_pixel(target[0] + 1, target[1]) != PAINT_COLOR
    assert scene.active_buffer().get_pixel(target[0], target[1] + 1) != PAINT_COLOR


def test_real_left_click_outside_document_does_not_paint(make_view, qtbot):
    """A real ``QTest`` click at a document pixel OUTSIDE the document paints nothing.

    The target is chosen INSIDE the (larger) viewport but outside the
    (smaller) document, so ``viewport_point_for_pixel`` does not raise here --
    this exercises the product's own out-of-bounds paint guard
    (``logic.drawing._plot`` / ``PixelBuffer.in_bounds``), not the harness's
    visibility gate (that is the next test).
    """
    view, scene, stack = _prepared_view(make_view, qtbot)
    outside = (DOC_SIZE + 20, DOC_SIZE + 20)
    # Sanity check the premise: this point really is inside the viewport, so
    # a failure below is the product's guard, not a harness mis-measurement.
    viewport_point_for_pixel(view, *outside)
    before = scene.active_buffer().copy()
    before_count = stack.count()

    real_click_pixel(view, *outside)

    assert scene.active_buffer() == before
    assert stack.count() == before_count


def test_real_click_outside_viewport_raises_instead_of_misclicking(make_view, qtbot):
    """A document pixel not currently visible in the viewport fails loudly.

    This is the harness's own contract under test: silence (a click landing
    somewhere arbitrary and the assertion reading "nothing happened" as a
    pass) is exactly the failure mode this whole exercise exists to close.
    """
    view, scene, stack = _prepared_view(make_view, qtbot)
    far_outside = (VIEWPORT_SIZE + 500, VIEWPORT_SIZE + 500)
    before = scene.active_buffer().copy()
    before_count = stack.count()

    with pytest.raises(ViewportTargetError):
        real_click_pixel(view, *far_outside)

    # No event was ever delivered to the widget -- confirm the raise really
    # did pre-empt the click rather than deliver it and then also raise.
    assert scene.active_buffer() == before
    assert stack.count() == before_count


def test_real_right_click_dispatches_with_document_pixel(make_view, qtbot):
    """A real right-click reaches ``Canvas_View``'s menu hook with the clicked pixel.

    ``Canvas_View.mousePressEvent`` dispatches the right-click menu itself
    from the button branch (``_dispatch_menu``); it does not depend on the
    offscreen platform synthesizing a native ``QContextMenuEvent`` the way
    ``Timeline_Grid_View``'s item-view context menu does (see
    ``test_timeline_grid_gestures.py``'s documented ``QApplication.sendEvent``
    workaround for that different widget) -- so a real ``QTest`` right-click
    is expected to work here without any such workaround.
    """
    view, _scene, _stack = _prepared_view(make_view, qtbot)
    calls = []
    view.set_menu_hook(lambda x, y: calls.append((x, y)))
    target = (5, 7)

    # Observer connected BEFORE the triggering action.
    with qtbot.waitSignal(view.rightClicked, timeout=1000) as blocker:
        real_right_click_pixel(view, *target)

    assert blocker.args == [target[0], target[1]]
    assert calls == [target]
