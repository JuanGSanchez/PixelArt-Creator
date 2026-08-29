"""Viewport update-mode regression tests (REQ-CGS-UI-002).

Qt 6 documents ``FullViewportUpdate`` as "the preferred update mode for
viewports that do not support partial updates, such as QOpenGLWidget", and
``MinimalViewportUpdate`` as "QGraphicsView's default mode" — Qt does not
switch the mode for you when a GL viewport is installed. ``Canvas_View``
installs a ``QOpenGLWidget`` viewport on any real desktop (``_install_viewport``,
``pixelart_creator/ui/canvas_view.py``) while every drawing tool commits
through a *partial* ``refresh_rect`` -> ``_item.update(rect)``. Asking a
viewport Qt documents as unable to perform partial updates to perform nothing
but partial updates is why pencil/eraser/line strokes went invisible in the
field while a whole-item ``refresh_all`` (rectangle-selection drag) still
rendered.

These tests call the production route directly — ``view.setViewport(...)`` is
exactly what ``Canvas_View._install_viewport`` calls — so no mode-decision seam
is mocked or monkeypatched.

The module also carries the REQ-CGS-UI-001 acceptance tests (added T4,
job ``20260825-canvas-grid-semantics``): a pencil dab, an eraser stroke and a
committed line, each driven through its real tool controller — a genuine
``QTest`` press/move/release delivered to ``Canvas_View.viewport()``, running
``Tool.on_press``/``on_move``/``on_release`` and pushing through the view's own
(recording-wrapped) ``QUndoStack`` exactly as a user gesture would, never a
direct write to a ``PixelBuffer`` — after which the **view** is rendered to a
``QImage`` and the expected colour is asserted present at the expected
position with no further input delivered first. A fourth test then drags a
rectangle selection (whose commit path is the *whole-item* ``refresh_all``,
not the drawing tools' *partial* ``refresh_rect``) and asserts that none of
the three already-visible edits changes as a result — nothing was waiting on
that drag to "catch up" and become visible.

**Scope limitation, stated rather than papered over**: ``QWidget.render()`` —
what every REQ-CGS-UI-001 test below calls, via ``view.viewport().render(...)``
— always takes Qt's **raster** rendering path; it does not exercise a live
``QOpenGLWidget`` viewport's actual swap/update behaviour, which is the one
Qt reserves ``FullViewportUpdate`` for and the one this whole defect lived in.
These tests therefore prove the dirty-rect commit path puts the right pixel on
the rendered viewport in this harness; they do **not** prove a real GL
viewport flushed it to a real screen. ``REQ-CGS-UI-002`` (the three tests
above) is the named, assertable proxy for that half — it establishes,
headlessly, that a ``QOpenGLWidget`` viewport really does get
``FullViewportUpdate`` — and ``REQ-CGS-UI-001`` closes only when **both** this
module's suites pass **plus** confirmation from a real desktop build (the
spec's own words: "This holds on the build the user runs, not only on the
build the tests run").

Scenarios: SC-CGS-UI-001-1, SC-CGS-UI-001-2, SC-CGS-UI-001-3, SC-CGS-UI-001-4,
SC-CGS-UI-002-1, SC-CGS-UI-002-2, SC-CGS-UI-002-3.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QGraphicsView, QWidget

from pixelart_creator.ui.tools import EraserTool, LineTool, PencilTool, RectSelectTool
from tests.ui._ui_helpers import (
    prepare_for_click,
    real_click_pixel,
    real_move_pixel,
    real_press_pixel,
    real_release_pixel,
    viewport_point_for_pixel,
)

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget

    _HAS_QT_OPENGL_WIDGETS = True
except ImportError:  # pragma: no cover - depends on the platform's Qt build.
    _HAS_QT_OPENGL_WIDGETS = False


def test_sc_cgs_ui_002_1_gl_viewport_sets_full_update_mode(make_view):
    """SC-CGS-UI-002-1: installing a QOpenGLWidget viewport switches the view
    to FullViewportUpdate — the mode Qt documents as required for a viewport
    that "does not support partial updates, such as QOpenGLWidget".
    """
    if not _HAS_QT_OPENGL_WIDGETS:
        pytest.skip("PySide6.QtOpenGLWidgets is not importable on this platform")

    view, _scene, _stack = make_view(64, 64)

    view.setViewport(QOpenGLWidget())  # the exact call _install_viewport makes

    assert view.viewport().inherits("QOpenGLWidget")
    assert (
        view.viewportUpdateMode() == QGraphicsView.ViewportUpdateMode.FullViewportUpdate
    )


def test_sc_cgs_ui_002_2_raster_viewport_keeps_minimal_update_mode(make_view):
    """SC-CGS-UI-002-2: the raster fallback (a plain QWidget viewport, as used
    headless/offscreen or on any GL failure) keeps QGraphicsView's own default,
    MinimalViewportUpdate — this is existing, already-correct behaviour.
    """
    view, _scene, _stack = make_view(64, 64)

    view.setViewport(QWidget())  # the raster fallback _install_viewport keeps

    assert not view.viewport().inherits("QOpenGLWidget")
    assert (
        view.viewportUpdateMode()
        == QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
    )


def test_sc_cgs_ui_002_3_full_update_mode_asserted_without_a_gl_context(make_view):
    """SC-CGS-UI-002-3: assertion 1 holds without ever instantiating a real
    OpenGL context. Measured at the anchor: under QT_QPA_PLATFORM=offscreen,
    QOpenGLWidget is constructible, setViewport(...) succeeds, and
    QOpenGLWidget().context() is None both before and after installation — so
    the FullViewportUpdate requirement is provably a *mode* decision, never
    contingent on a live GL context existing in this headless run.
    """
    if not _HAS_QT_OPENGL_WIDGETS:
        pytest.skip("PySide6.QtOpenGLWidgets is not importable on this platform")

    view, _scene, _stack = make_view(64, 64)
    gl_widget = QOpenGLWidget()
    assert gl_widget.context() is None  # no GL context before installation

    view.setViewport(gl_widget)

    assert view.viewport().context() is None  # still no GL context after
    assert (
        view.viewportUpdateMode() == QGraphicsView.ViewportUpdateMode.FullViewportUpdate
    )


# --------------------------------------------------------------------------- #
# REQ-CGS-UI-001 — an edit reaches the rendered viewport, driven through the  #
# real tool controller (SC-CGS-UI-001-1..4). See the module docstring for the #
# raster-path scope limitation these tests carry.                             #
# --------------------------------------------------------------------------- #

#: Small enough to keep the render/sample loop cheap, large enough to hold
#: every coordinate these tests touch (the highest is (14, 13)).
_DOC_SIZE = 16
#: Deliberately larger than the document — the verified-working combination:
#: a 16x16 document in a 320x320 view at zoom 1.0 renders headlessly (measured
#: for this task). The extra room past the document edge is unused margin.
_VIEWPORT_SIZE = 320

#: One colour per tool, each far from either theme's checker tones
#: (``#ffffff``/``#c8c8c8`` light, ``#5a5a5a``/``#464646`` dark — see
#: ``ui/theme.py``), so a rendered pixel can never be mistaken for an
#: unpainted background pixel.
_PENCIL_COLOR = (250, 10, 200, 255)
_ERASER_PAINT_COLOR = (10, 200, 20, 255)
_LINE_COLOR = (20, 80, 250, 255)


def _prepared_cgs_view(make_view, qtbot):
    """Build a ``Canvas_View`` sized/shown/pinned like the harness self-tests.

    Mirrors ``test_real_event_harness.py``'s ``_prepared_view``: real geometry
    is required for a real ``QTest`` event to hit-test correctly under
    ``QT_QPA_PLATFORM=offscreen``. ``prepare_for_click`` (re-applied after the
    resize) pins zoom=1.0 and guarantees the document is reachable, but makes
    NO promise that viewport point ``(x, y)`` equals document pixel ``(x, y)``
    — ``Canvas_View`` inflates its own scene rect by a pan margin
    (``_apply_pan_margin``, REQ-CGS-UI-009), which gives it a negative origin.
    Every real click below and every pixel sample in :func:`_sample` therefore
    goes through the view's own CURRENT mapping
    (``_ui_helpers.viewport_point_for_pixel`` / ``view.mapFromScene``), never a
    hand-computed offset. No tool is armed here; each test selects its own.
    """
    view, scene, stack = make_view(_DOC_SIZE, _DOC_SIZE)
    view.resize(_VIEWPORT_SIZE, _VIEWPORT_SIZE)
    view.show()
    qtbot.waitExposed(view)
    prepare_for_click(view)
    return view, scene, stack


def _render_viewport(view) -> QImage:
    """Render ``view``'s viewport widget to a ``QImage``.

    This is the RASTER path (see the module docstring's scope limitation):
    ``QWidget.render()`` never exercises a live ``QOpenGLWidget`` viewport's
    own swap/update behaviour headlessly, only Qt's raster paint path.
    """
    image = QImage(view.viewport().size(), QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    view.viewport().render(image)
    return image


def _sample(image: QImage, view, x: int, y: int):
    """Sample ``image`` (a rendered viewport) at document pixel ``(x, y)``.

    Located via the view's own CURRENT mapping (``viewport_point_for_pixel`` /
    ``view.mapFromScene``) — never the raw ``(x, y)`` — since ``image`` is a
    render of the viewport, whose pixel (0, 0) is not document pixel (0, 0)
    once the pan margin gives the view's scene rect a negative origin.
    """
    point = viewport_point_for_pixel(view, x, y)
    return image.pixelColor(point.x(), point.y())


def test_sc_cgs_ui_001_1_pencil_dab_visible_without_further_input(make_view, qtbot):
    """SC-CGS-UI-001-1 / REQ-CGS-UI-001: a pencil dab, made through the tool
    controller — a real press+release delivered to the viewport, running
    ``PencilTool.on_press``/``on_release`` and pushing one command through the
    view's own undo stack — is present in the rendered viewport with no
    further input delivered first.
    """
    view, _scene, stack = _prepared_cgs_view(make_view, qtbot)
    view.set_tool(PencilTool())
    view.set_active_color(_PENCIL_COLOR)
    target = (2, 2)
    before_count = stack.count()

    real_click_pixel(view, *target)  # PencilTool.on_press then .on_release

    assert stack.count() == before_count + 1  # one undoable command was pushed

    image = _render_viewport(view)  # <-- no further input delivered first

    assert _sample(image, view, *target).getRgb() == _PENCIL_COLOR


def test_sc_cgs_ui_001_2_eraser_stroke_clears_visibly_without_further_input(
    make_view, qtbot
):
    """SC-CGS-UI-001-2 / REQ-CGS-UI-001: erasing part of a painted region,
    through ``EraserTool`` (a ``PencilTool`` subclass, REQ-P1-UI-013) driven by
    a real press+release, clears on screen with no further input delivered
    first — the erased pixel returns to exactly what it rendered as before it
    was ever painted, while its untouched neighbours stay painted.
    """
    view, _scene, stack = _prepared_cgs_view(make_view, qtbot)
    row_y = 6
    region = [(2, row_y), (3, row_y), (4, row_y)]
    erased = (3, row_y)
    base_before_paint = _sample(_render_viewport(view), view, *erased).getRgb()

    view.set_tool(PencilTool())
    view.set_active_color(_ERASER_PAINT_COLOR)
    for x, y in region:
        real_click_pixel(view, x, y)  # PencilTool paints the region

    painted = _render_viewport(view)
    for x, y in region:
        assert _sample(painted, view, x, y).getRgb() == _ERASER_PAINT_COLOR

    view.set_tool(EraserTool())
    before_count = stack.count()

    real_click_pixel(view, *erased)  # EraserTool.on_press then .on_release

    assert stack.count() == before_count + 1  # one undoable command was pushed

    image = _render_viewport(view)  # <-- no further input delivered first

    assert _sample(image, view, *erased).getRgb() == base_before_paint
    assert _sample(image, view, *erased).getRgb() != _ERASER_PAINT_COLOR
    # Only the middle pixel of the region was erased -- the rest is untouched.
    assert _sample(image, view, 2, row_y).getRgb() == _ERASER_PAINT_COLOR
    assert _sample(image, view, 4, row_y).getRgb() == _ERASER_PAINT_COLOR


def test_sc_cgs_ui_001_3_committed_line_visible_without_further_input(make_view, qtbot):
    """SC-CGS-UI-001-3 / REQ-CGS-UI-001: a line committed through ``LineTool``
    (press, drag, release — the drag only previews, mutating nothing; release
    pushes the one committed stroke command, CL-11) is present in full in the
    rendered viewport with no further input delivered first.
    """
    view, _scene, stack = _prepared_cgs_view(make_view, qtbot)
    view.set_tool(LineTool())
    view.set_active_color(_LINE_COLOR)
    start, mid, end = (1, 10), (3, 10), (6, 10)
    before_count = stack.count()

    real_press_pixel(view, *start)  # LineTool.on_press: preview only
    real_move_pixel(view, *mid)  # LineTool.on_move: preview only
    real_release_pixel(view, *end)  # LineTool.on_release: commits the stroke

    assert stack.count() == before_count + 1  # one undoable command was pushed

    image = _render_viewport(view)  # <-- no further input delivered first

    for x in range(start[0], end[0] + 1):
        assert _sample(image, view, x, start[1]).getRgb() == _LINE_COLOR


def test_sc_cgs_ui_001_4_selection_drag_reveals_nothing_that_was_hidden(
    make_view, qtbot
):
    """SC-CGS-UI-001-4 / REQ-CGS-UI-001: with a pencil dab, an eraser stroke and
    a line each already made — and each already independently verified visible
    with no further input, by the three tests above — dragging a rectangle
    selection over an UNRELATED area must not make any of them visible for the
    first time: none of them needed the selection drag's whole-item
    ``refresh_all`` to appear at all. Every one of the three edited positions
    renders identically before and after the drag; the drag is entitled to
    change only its own marching-ants overlay, which lives away from every
    sampled position below.
    """
    view, _scene, _stack = _prepared_cgs_view(make_view, qtbot)

    view.set_tool(PencilTool())
    view.set_active_color(_PENCIL_COLOR)
    pencil_px = (2, 2)
    real_click_pixel(view, *pencil_px)

    row_y = 6
    view.set_active_color(_ERASER_PAINT_COLOR)
    for x, y in ((2, row_y), (3, row_y), (4, row_y)):
        real_click_pixel(view, x, y)
    view.set_tool(EraserTool())
    erased_px = (3, row_y)
    real_click_pixel(view, *erased_px)

    view.set_tool(LineTool())
    view.set_active_color(_LINE_COLOR)
    real_press_pixel(view, 1, 10)
    real_move_pixel(view, 3, 10)
    real_release_pixel(view, 6, 10)
    line_px = (3, 10)

    sampled = [pencil_px, erased_px, line_px]
    before = _render_viewport(view)
    # Each edit is independently already visible, exactly as tests -1/-2/-3
    # established, BEFORE the selection drag that is this test's own subject.
    assert _sample(before, view, *pencil_px).getRgb() == _PENCIL_COLOR
    assert _sample(before, view, *erased_px).getRgb() != _ERASER_PAINT_COLOR
    assert _sample(before, view, *line_px).getRgb() == _LINE_COLOR
    before_values = [_sample(before, view, x, y).getRgb() for x, y in sampled]

    view.set_tool(RectSelectTool())
    view.set_active_color(_PENCIL_COLOR)
    # Well clear of every sampled position above (max sampled x=4, y=10).
    real_press_pixel(view, 10, 10)
    real_move_pixel(view, 12, 11)
    real_release_pixel(view, 14, 13)

    assert view.active_selection() is not None  # the drag was a real gesture

    after = _render_viewport(view)
    after_values = [_sample(after, view, x, y).getRgb() for x, y in sampled]

    assert after_values == before_values  # nothing became visible for the first time
