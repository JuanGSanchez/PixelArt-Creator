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

Scenarios: SC-CGS-UI-002-1, SC-CGS-UI-002-2, SC-CGS-UI-002-3.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QGraphicsView, QWidget

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
