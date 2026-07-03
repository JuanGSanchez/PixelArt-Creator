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
from PySide6.QtCore import QLocale, QStandardPaths  # noqa: E402
from PySide6.QtGui import QUndoStack  # noqa: E402

# Pin the *system* locale to English for the whole UI suite so the tests run
# identically in CI and on any developer machine (F11 / portability). Qt reads
# the OS UI language for ``QLocale.system().uiLanguages()`` and ignores the
# LANG/LC_ALL env vars on Windows, so on a non-English host (e.g. es_ES)
# ``Main_Window`` would install a translated catalogue at construction and leak
# it onto the shared ``QApplication`` — polluting later tests that assert the
# English source strings. Replacing ``QLocale.system`` (patchable at the Python
# level) makes ``install_from_locale`` resolve to the English fallback exactly as
# CI's C/en environment does; the explicit ``es`` tests bypass this via
# ``set_language("es")`` and are unaffected.
QLocale.system = staticmethod(  # type: ignore[method-assign]
    lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
)

from pixelart_creator.logic.document import Document  # noqa: E402
from pixelart_creator.logic.palette import Palette  # noqa: E402
from pixelart_creator.ui.canvas_scene import CanvasScene  # noqa: E402
from pixelart_creator.ui.canvas_view import Canvas_View  # noqa: E402
from pixelart_creator.ui.main_window import Main_Window  # noqa: E402
from pixelart_creator.ui.theme import (  # noqa: E402
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    canvas_roles,
)
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas  # noqa: E402
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


@pytest.fixture(autouse=True)
def _isolate_app_config(monkeypatch, tmp_path):
    """Redirect the app-config dir to a per-test tmp path (xdist isolation, FU-20).

    ``Main_Window`` persists the Favourites list to the app-config directory
    (``QStandardPaths.AppConfigLocation``) and reads it back on construction;
    ~25 modules build a ``Main_Window``. Under ``pytest -n auto`` each xdist
    worker is a **separate process**, so every worker would read/write the ONE
    shared ``favourites.json`` concurrently — a torn-write race (intermittent
    ``FavouritesIOError``/``OSError``) that also pollutes the developer's real
    config. Pointing ``writableLocation`` at a unique per-test tmp dir isolates
    every worker and test while still exercising the real ``_favourites_path``
    resolution (so its coverage is preserved). ``tmp_path`` is unique per test
    and per worker, giving full on-disk isolation with no shared state.
    """
    cfg = tmp_path / "appconfig"
    cfg.mkdir()
    monkeypatch.setattr(
        QStandardPaths,
        "writableLocation",
        staticmethod(lambda *_a, **_k: str(cfg)),
    )


@pytest.fixture(autouse=True)
def _drain_prewarm_after_test():
    """Deterministically drain every off-thread pre-warm before GC (S1 blocker).

    Phase-5 wired an off-thread composite pre-warm (``composite_warmer``
    ``QThreadPool`` worker + a ``CompositeWarmSignals`` GUI-thread carrier) into
    ``CanvasScene``. If a test leaves a live worker thread or a still-connected
    carrier behind, a garbage-collection cycle during a *later* test's
    ``Main_Window()`` construction cross-thread-GCs Qt C++ objects and crashes
    PySide6 natively (the ``worker 'gwN' crashed`` segfault seen on CI run
    28663849512 at
    ``test_lazy_perf.py::test_lazy_analytics_new_document_with_hidden_dock_no_scan[dark]``).

    This autouse teardown runs after **every** UI test — with no per-test opt-in
    — and calls the deterministic, event-loop-free
    :meth:`CanvasScene.shutdown_prewarm` / :meth:`Main_Window.shutdown_prewarm`
    (AGT-05, uncommitted product fix) on **every** live scene and window still
    reachable, then forces a collection while all pools are drained and all
    carriers are disconnected. A ``Main_Window`` drains its own tabs' scenes and
    a scene reached both via its window and directly is drained twice; both APIs
    are idempotent, so that is safe. This covers the ``make_scene`` / ``make_view``
    factories AND the ~33 modules that build a ``CanvasScene`` / ``Main_Window``
    directly (e.g. ``test_lazy_perf.py`` line ~136) without editing any of them.
    """
    yield

    import gc

    # gc.get_objects() is the only net that reaches EVERY live instance,
    # however it was constructed (fixture, factory, or bare constructor),
    # without each test opting in. Idempotent + guarded, so double/partial
    # drains are harmless.
    #
    # Phase-6 (AGT-06): the tilemap canvas owns its OWN off-thread chunk warmer
    # (``_Tilemap_Scene`` QThreadPool + ``TilemapChunkWarmSignals`` carrier) — the
    # same PySide6 cross-thread-GC-of-Qt-C++ segfault class as the Phase-5 prewarm.
    # A ``Main_Window``'s tilemap canvas is drained by its ``shutdown_prewarm``
    # (it calls ``self._tilemap_canvas.shutdown_warm()``), so the Main_Window branch
    # already covers it. A test that builds a **standalone** ``Tilemap_Canvas`` (no
    # window) is NOT reached that way, so it is drained explicitly here via
    # ``shutdown_warm``. This makes the tilemap tests xdist-safe (``-n auto``) with
    # no per-test opt-in — no worker thread / connected carrier survives into a
    # later worker-process test's GC.
    for obj in gc.get_objects():
        if isinstance(obj, (Main_Window, CanvasScene)):
            try:
                obj.shutdown_prewarm()
            except (RuntimeError, AttributeError):
                # RuntimeError: underlying Qt C++ object already deleted.
                # AttributeError: instance from a __init__ that raised before
                # the warm attributes existed -> nothing live to drain.
                pass
        elif isinstance(obj, Tilemap_Canvas):
            try:
                obj.shutdown_warm()
            except (RuntimeError, AttributeError):
                pass

    # Collect NOW, while every pool is drained and every carrier disconnected,
    # so no worker thread / connected carrier survives into a later test where
    # the cross-thread GC-of-Qt-C++ segfault would otherwise fire.
    gc.collect()


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


# --------------------------------------------------------------------------- #
# Phase-6 tilemap builders (AGT-06). Pure-logic factories the UI binds to; no  #
# Qt is needed to construct them, so they exercise the frozen logic/data API   #
# exactly as the widgets do (Article I / S11).                                 #
# --------------------------------------------------------------------------- #


def _rgba_tileset_source(cols: int, rows: int, tile: int):
    """Return an RGBA source of ``cols x rows`` distinctly-coloured tiles."""
    from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

    src = PixelBuffer(cols * tile, rows * tile, ColorMode.RGBA)
    for r in range(rows):
        for c in range(cols):
            colour = ((c * 37 + 20) % 256, (r * 53 + 40) % 256, 90, 255)
            src.data[r * tile : (r + 1) * tile, c * tile : (c + 1) * tile] = colour
    return src


@pytest.fixture
def make_tilemap_setup():
    """Factory: ``(tileset, tilemap)`` with ``cols*rows`` tiles + ``layers`` layer(s).

    The tileset's ``first_gid`` is ``1`` (Tiled's first tileset) and it is attached
    to the tilemap's gid space, so gids ``1..cols*rows`` are stampable. Returns the
    logic objects the tileset editor / tilemap canvas / layer panel bind to.
    """
    from pixelart_creator.logic.tilemap import Tilemap
    from pixelart_creator.logic.tileset import Tileset

    def _make(cols: int = 4, rows: int = 2, tile: int = 16, layers: int = 1):
        source = _rgba_tileset_source(cols, rows, tile)
        tileset = Tileset(source, tile_width=tile, tile_height=tile, first_gid=1)
        tilemap = Tilemap(tile_width=tile, tile_height=tile)
        tilemap.make_attach_tileset_command(tileset).execute()
        for index in range(layers):
            tilemap.make_add_layer_command(name=f"Layer {index + 1}").execute()
        return tileset, tilemap

    return _make


@pytest.fixture
def make_blob_setup(make_tilemap_setup):
    """Factory: ``(tileset, tilemap)`` whose tileset holds a full 47-frame blob atlas.

    ``base_gid = 1`` and gids ``1..47`` all resolve, so the tilemap canvas can build
    a Blob-47 :class:`AutotileRuleset` (auto-tile acceptance, REQ-P6-UI-009).
    """

    def _make(tile: int = 16, layers: int = 1):
        # 7x7 = 49 tiles >= BLOB_TILE_COUNT (47); frames 1..47 all resolve.
        return make_tilemap_setup(cols=7, rows=7, tile=tile, layers=layers)

    return _make
