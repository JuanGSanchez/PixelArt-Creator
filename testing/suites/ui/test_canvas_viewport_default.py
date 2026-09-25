"""Raster-by-default canvas viewport regression tests (A1/A2).

A GL-composited top-level surface was measured to present blank on an
affected desktop even though every widget still painted underneath (the
platform fault behind this fix). ``opengl_viewport_requested()``
(``pixelart_creator/ui/canvas_view.py``) is the single gate both
``Canvas_View._install_viewport`` and ``Tilemap_Canvas._install_viewport``
consult: raster unless the ``OPENGL_VIEWPORT_ENABLED`` flag or the
``OPENGL_VIEWPORT_ENV`` environment variable opts a session in.

A1 -- with no env var and the flag at its shipped default (``False``), the
gate returns ``False`` even when the offscreen early-return in
``_install_viewport`` is bypassed (``QGuiApplication.platformName()``
monkeypatched to a non-offscreen name): the gate is checked FIRST, so no GL
viewport is ever attempted regardless of platform. Both painting views
(``Canvas_View`` and ``Tilemap_Canvas``) therefore keep their default,
non-``QOpenGLWidget`` viewport.

A2 -- with ``PIXELART_OPENGL_VIEWPORT=1`` and the same platform bypass, the
gate returns ``True`` and ``Canvas_View`` really does install a
``QOpenGLWidget`` viewport, with ``FullViewportUpdate`` (Qt's own documented
requirement for a viewport that "does not support partial updates, such as
QOpenGLWidget" -- REQ-CGS-UI-002, ``test_canvas_viewport_update_mode.py``).
Skipped cleanly, with an explicit reason, when ``PySide6.QtOpenGLWidgets`` is
not importable on the running platform.

Both themes (the suite's autouse ``theme`` fixture); these tests do not
depend on theme, but the fixture runs every module in this suite twice
regardless, matching the project convention.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QGraphicsView

from pixelart_creator.logic import constants
from pixelart_creator.logic.constants import OPENGL_VIEWPORT_ENV
from pixelart_creator.ui.canvas_view import opengl_viewport_requested
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas

try:
    from PySide6.QtOpenGLWidgets import QOpenGLWidget  # noqa: F401 (importability probe)

    _HAS_QT_OPENGL_WIDGETS = True
except ImportError:  # pragma: no cover - depends on the platform's Qt build.
    _HAS_QT_OPENGL_WIDGETS = False


def _bypass_offscreen_platform_check(monkeypatch) -> None:
    """Make ``QGuiApplication.platformName()`` report a non-offscreen name.

    Both ``Canvas_View._install_viewport`` and ``Tilemap_Canvas._install_viewport``
    read the SAME ``PySide6.QtGui.QGuiApplication`` class, so patching it here
    affects both modules' checks -- there is exactly one platform name to fake.
    """
    monkeypatch.setattr(
        QGuiApplication, "platformName", staticmethod(lambda: "windows")
    )


# --------------------------------------------------------------------------- #
# A1 -- no env var, flag at its default: raster, even past the platform gate. #
# --------------------------------------------------------------------------- #


def test_a1_no_env_and_flag_off_gate_returns_false(monkeypatch):
    """A1 (gate): ``opengl_viewport_requested()`` is False with nothing set."""
    monkeypatch.delenv(OPENGL_VIEWPORT_ENV, raising=False)
    monkeypatch.setattr(constants, "OPENGL_VIEWPORT_ENABLED", False)

    assert opengl_viewport_requested() is False


def test_a1_canvas_view_viewport_is_not_gl_even_past_the_offscreen_gate(
    monkeypatch, make_view
):
    """A1: ``Canvas_View``'s viewport stays non-GL with no env var, even with
    the offscreen early-return bypassed -- the GL-request gate is checked
    FIRST in ``_install_viewport``, so a platform bypass alone never installs
    a GL viewport."""
    monkeypatch.delenv(OPENGL_VIEWPORT_ENV, raising=False)
    monkeypatch.setattr(constants, "OPENGL_VIEWPORT_ENABLED", False)
    _bypass_offscreen_platform_check(monkeypatch)
    assert opengl_viewport_requested() is False  # the gate this relies on

    view, _scene, _stack = make_view(8, 8)

    assert not view.viewport().inherits("QOpenGLWidget")


def test_a1_tilemap_canvas_viewport_is_not_gl_even_past_the_offscreen_gate(
    monkeypatch, qtbot
):
    """A1: ``Tilemap_Canvas`` mirrors ``Canvas_View`` exactly (same gate,
    same bypass)."""
    monkeypatch.delenv(OPENGL_VIEWPORT_ENV, raising=False)
    monkeypatch.setattr(constants, "OPENGL_VIEWPORT_ENABLED", False)
    _bypass_offscreen_platform_check(monkeypatch)
    assert opengl_viewport_requested() is False

    view = Tilemap_Canvas()
    qtbot.addWidget(view)

    assert not view.viewport().inherits("QOpenGLWidget")


# --------------------------------------------------------------------------- #
# A2 -- PIXELART_OPENGL_VIEWPORT=1 past the platform gate installs GL.       #
# --------------------------------------------------------------------------- #


def test_a2_env_flag_set_gate_returns_true(monkeypatch):
    """A2 (gate): setting the env var to ``"1"`` flips the gate to True."""
    monkeypatch.setattr(constants, "OPENGL_VIEWPORT_ENABLED", False)
    monkeypatch.setenv(OPENGL_VIEWPORT_ENV, "1")

    assert opengl_viewport_requested() is True


def test_a2_env_flag_set_installs_gl_viewport_with_full_update_mode(
    monkeypatch, make_view
):
    """A2: with the env var set AND the offscreen early-return bypassed,
    ``Canvas_View`` really installs a ``QOpenGLWidget`` viewport, kept at
    ``FullViewportUpdate`` (REQ-CGS-UI-002)."""
    if not _HAS_QT_OPENGL_WIDGETS:
        pytest.skip("PySide6.QtOpenGLWidgets is not importable on this platform")

    monkeypatch.setattr(constants, "OPENGL_VIEWPORT_ENABLED", False)
    monkeypatch.setenv(OPENGL_VIEWPORT_ENV, "1")
    _bypass_offscreen_platform_check(monkeypatch)
    assert opengl_viewport_requested() is True

    view, _scene, _stack = make_view(8, 8)

    assert view.viewport().inherits("QOpenGLWidget")
    assert (
        view.viewportUpdateMode() == QGraphicsView.ViewportUpdateMode.FullViewportUpdate
    )


@pytest.mark.parametrize("value", ["0", "true", ""])
def test_a2_falsy_env_values_keep_gl_disabled(monkeypatch, value):
    """A2 (value table): only the literal string ``"1"`` opts in -- ``"0"``,
    ``"true"`` and an empty string all keep the raster default."""
    monkeypatch.setattr(constants, "OPENGL_VIEWPORT_ENABLED", False)
    monkeypatch.setenv(OPENGL_VIEWPORT_ENV, value)

    assert opengl_viewport_requested() is False


def test_a2_enabled_flag_alone_requests_gl_with_no_env_var(monkeypatch):
    """A2 (flag path): ``OPENGL_VIEWPORT_ENABLED=True`` alone -- no env var --
    also requests GL (the two conditions are OR'd, per the docstring)."""
    monkeypatch.delenv(OPENGL_VIEWPORT_ENV, raising=False)
    monkeypatch.setattr(constants, "OPENGL_VIEWPORT_ENABLED", True)

    assert opengl_viewport_requested() is True
