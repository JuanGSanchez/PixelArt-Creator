"""Shared fixtures for the UI suite: headless platform + both-theme parametrise.

The ``theme`` fixture is ``autouse`` and parametrised over the light and dark
themes, so **every** test in ``tests/ui`` runs twice — once per theme — applying
the QSS via :func:`pixelart_creator.ui.theme.apply_theme` (REQ-P1-UI-025). The
offscreen Qt platform is forced before any ``QApplication`` is created (F11).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402  (must follow the platform env set above)
from PySide6.QtGui import QUndoStack  # noqa: E402

from pixelart_creator.logic.document import Document  # noqa: E402
from pixelart_creator.logic.palette import Palette  # noqa: E402
from pixelart_creator.ui.canvas_scene import CanvasScene  # noqa: E402
from pixelart_creator.ui.canvas_view import Canvas_View  # noqa: E402
from pixelart_creator.ui.theme import (  # noqa: E402
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    canvas_roles,
)
from pixelart_creator.ui.tools import PencilTool  # noqa: E402

#: A tiny deterministic palette used across the suite.
STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)
YELLOW = (240, 220, 40, 255)
CYAN = (0, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def pytest_configure(config: pytest.Config) -> None:
    """Guarantee the offscreen platform even if imported indirectly (F11)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(params=[THEME_LIGHT, THEME_DARK], autouse=True)
def theme(request: pytest.FixtureRequest, qapp) -> str:
    """Apply light/dark theme to the app; parametrises every test (025)."""
    name = request.param
    apply_theme(qapp, name)
    return name


@pytest.fixture
def make_document():
    """Factory returning a fresh :class:`Document` with the starter palette."""

    def _make(width: int = 64, height: int = 64) -> Document:
        return Document(width, height, palette=Palette(STARTER))

    return _make


@pytest.fixture
def make_scene(make_document, theme):
    """Factory building a :class:`CanvasScene` with theme-correct canvas roles."""

    def _make(width: int = 64, height: int = 64) -> CanvasScene:
        scene = CanvasScene(make_document(width, height))
        scene.set_background_roles(*canvas_roles(theme))
        return scene

    return _make


@pytest.fixture
def make_view(make_scene, qtbot):
    """Factory building a click-ready :class:`Canvas_View` bound to a fresh stack.

    Returns ``(view, scene, stack)``. The view is pinned so a viewport point
    ``(x, y)`` maps to scene pixel ``(x, y)`` and the pencil tool is active.
    """
    from tests.ui._ui_helpers import prepare_for_click

    def _make(width: int = 64, height: int = 64):
        scene = make_scene(width, height)
        stack = QUndoStack()
        view = Canvas_View(scene, stack)
        qtbot.addWidget(view)
        prepare_for_click(view)
        view.set_tool(PencilTool())
        view.set_active_color(BLUE)
        return view, scene, stack

    return _make
