"""Shared fixtures for the UI suite: headless platform + both-theme parametrise.

The ``theme`` fixture is ``autouse`` and parametrised over the light and dark
modes of the default style, so **every** test in ``testing/suites/ui`` runs twice —
once per mode — applying the QSS via :func:`pixelart_creator.ui.theme.apply_theme`
(REQ-P1-UI-025). The style x mode matrix is covered by ``test_theme.py``. The
offscreen Qt platform is forced before any ``QApplication`` is created (F11).
"""

from __future__ import annotations

import contextlib
import functools
import os
import shutil
import types
import weakref
from pathlib import Path
from typing import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402  (must follow the platform env set above)
from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QLocale,
    QSettings,
    QStandardPaths,
    Qt,
)
from PySide6.QtGui import QUndoStack  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

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
from pixelart_creator.ui.app import (  # noqa: E402
    APPLICATION_NAME,
    ORGANIZATION_NAME,
)
from pixelart_creator.ui.asset_library_panel import Asset_Library_Panel  # noqa: E402
from pixelart_creator.ui.asset_reuse_panel import Asset_Reuse_Panel  # noqa: E402
from pixelart_creator.ui.asset_search_panel import Asset_Search_Panel  # noqa: E402
from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel  # noqa: E402
from pixelart_creator.ui.asset_version_browser import (  # noqa: E402
    Asset_Version_Browser,
)
from pixelart_creator.ui.branching_panel import Branching_Panel  # noqa: E402
from pixelart_creator.ui.canvas_scene import CanvasScene  # noqa: E402
from pixelart_creator.ui.canvas_view import Canvas_View  # noqa: E402
from pixelart_creator.ui.comments_panel import Comments_Panel  # noqa: E402
from pixelart_creator.ui.dependency_graph_view import (  # noqa: E402
    Dependency_Graph_View,
)
from pixelart_creator.ui.guides_rulers_overlay import Ruler_Strip  # noqa: E402
from pixelart_creator.ui.live_cursors_overlay import (  # noqa: E402
    Live_Cursors_Overlay,
)
from pixelart_creator.ui.main_window import Main_Window  # noqa: E402
from pixelart_creator.ui.multi_view import Document_View  # noqa: E402
from pixelart_creator.ui.presence_panel import Presence_Panel  # noqa: E402
from pixelart_creator.ui.real_size_preview_window import (  # noqa: E402
    Real_Size_Preview_Window,
)
from pixelart_creator.ui.realtime_actions import Realtime_Session  # noqa: E402
from pixelart_creator.ui.recovery_prompt import Recovery_Prompt  # noqa: E402
from pixelart_creator.ui.reference_board import Reference_Board  # noqa: E402
from pixelart_creator.ui.shared_projects_panel import (  # noqa: E402
    Shared_Projects_Panel,
)
from pixelart_creator.ui.theme import (  # noqa: E402
    DEFAULT_STYLE,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    canvas_roles,
)
from pixelart_creator.ui.theme_art_files import reset_art  # noqa: E402
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas  # noqa: E402
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls  # noqa: E402
from pixelart_creator.ui.tools import PencilTool  # noqa: E402
from pixelart_creator.ui.user_guide import User_Guide_Dialog  # noqa: E402
from pixelart_creator.ui.version_history_browser import (  # noqa: E402
    Version_History_Browser,
)

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


# --------------------------------------------------------------------------- #
# Off-thread-warm teardown registry (S1 blocker; Phase-6 CI-regression fix).    #
#                                                                               #
# Every test that builds a ``Main_Window`` / ``CanvasScene`` / ``Tilemap_Canvas`` #
# must, on teardown, drain its off-thread warm pool + release its signal        #
# carrier so no live worker / connected carrier survives into a later test's GC #
# (the PySide6 cross-thread-GC-of-Qt-C++ segfault, Phase-5 contract) — AND the  #
# instance itself must be DISPOSED, not merely dereferenced. Headless (offscreen,#
# no running event loop) a standalone widget's ``deleteLater`` never fires, so   #
# ``QApplication`` keeps it in ``topLevelWidgets()`` and it (plus its scene, its #
# 128-MiB-capable chunk-pixmap cache, its ``QThreadPool`` and render buffers) is #
# NEVER collected. Across 2452 tests those instances accumulate monotonically.  #
#                                                                               #
# The previous teardown walked ``gc.get_objects()`` (the WHOLE heap) on EVERY   #
# test to find live instances, then ran a full ``gc.collect()``. Both costs     #
# scale with the live-object count, so as the leaked instances piled up the     #
# per-test teardown got progressively slower — the 6-11 min-per-3%-block tail   #
# that cancelled CI run 28685252881 at the 75-min cap. Coverage instrumentation #
# and two xdist workers amplified it.                                           #
#                                                                               #
# The fix: an EXPLICIT ``weakref.WeakSet`` registry populated at construction    #
# (by wrapping each class's ``__init__`` once, here in test infra — no product   #
# edit), so teardown iterates only the handful of instances that exist instead  #
# of the whole heap; and each tracked instance is deterministically drained,    #
# its chunk cache cleared, then ``deleteLater``-d with the deferred-delete queue #
# flushed synchronously — so the heap (and process memory) stays BOUNDED and    #
# the per-test teardown stays O(instances-this-test), i.e. flat. Draining before #
# disposal preserves the event-loop-free Phase-5 safety contract: every pool is #
# already drained and every carrier disconnected before anything is deleted, so #
# no worker thread is live across the (synchronous, non-re-entrant) deferred-    #
# delete flush.                                                                  #
# --------------------------------------------------------------------------- #

#: Live Main_Window / CanvasScene / Tilemap_Canvas instances awaiting teardown.
#: A WeakSet so a collected instance drops out on its own — the registry can
#: never itself pin an instance alive.
_LIVE_UI_INSTANCES: "weakref.WeakSet" = weakref.WeakSet()

#: Phase-9 standalone top-level widgets a test builds directly (and
#: ``qtbot.addWidget``-registers) that either connect to a **parent-less** QObject
#: the test owns — ``Timelapse_Controls.bind_undo_stack`` connects to a local test
#: ``QUndoStack`` — or hold a ``QGraphicsView`` on the shared document scene
#: (``Real_Size_Preview_Window`` / ``Document_View`` / ``Reference_Board``). Headless
#: (offscreen, no running event loop) qtbot's teardown ``deleteLater`` NEVER fires, so
#: such a widget survives the test with that connection still live; the orphan QObject
#: it bound is then GC-deleted (parent-less, no other ref) while the widget's C++
#: object is still alive, leaving a DANGLING connection. The next test that spins an
#: event loop (e.g. an automation ``qtbot.waitSignal``) flushes every accumulated
#: ``DeferredDelete`` at once and dereferences that freed sender — the PySide6
#: cross-thread/GC-of-Qt-C++ native segfault (CI run 28702019804, gw1, on
#: ``test_automation_errors.py::…multiop_script_failure_is_atomic[dark]``). Disposing
#: these SYNCHRONOUSLY (``shiboken6.delete``) BEFORE the per-test ``gc.collect`` below
#: removes the connection cleanly (deleting the receiver disconnects it), so the orphan
#: QObject is collected with no live receiver — the Phase-9 extension of the
#: ``Main_Window`` / ``Tilemap_Canvas`` disposal contract (the Phase-5 lesson).
_PHASE9_DISPOSABLE = (
    Timelapse_Controls,
    Real_Size_Preview_Window,
    Reference_Board,
    Document_View,
    # Phase-10 Slice A cloud dialogs. Both are parented ``QDialog``s that
    # own NO worker thread (the off-thread cloud work lives in ``Cloud_Controller``,
    # which is drained via ``Main_Window.shutdown_prewarm`` — see the drain fixture
    # below). But a test may build either dialog directly (parent-less, or over the
    # shared document scene), and headless (offscreen, no running event loop) its
    # ``deleteLater`` never fires, so ``QApplication`` keeps it in
    # ``topLevelWidgets()`` and it survives the test. Registering them here disposes
    # them SYNCHRONOUSLY (``shiboken6.delete``) at teardown exactly like the Phase-9
    # aids, so no cloud dialog accumulates across the 2450+ test suite and none
    # outlives the ``Main_Window`` whose controller was drained (the Phase-5/6/9
    # cross-thread-GC-of-Qt-C++ segfault-hygiene contract).
    Version_History_Browser,
    Recovery_Prompt,
    # Phase-10 Slice B collaboration panels. The three new dock panels are
    # top-level ``QWidget``s bound to a synchronous, worker-free
    # ``Collaboration_Session`` (Slice B is synchronous over the loopback adapter —
    # The UI implementation introduced NO off-thread worker, so there is no new drain/teardown
    # wiring). STILL, a test may build a panel directly (parent-less) + register it
    # with ``qtbot.addWidget``; headless (offscreen, no running event loop) that
    # widget's ``deleteLater`` never fires, so ``QApplication`` keeps it in
    # ``topLevelWidgets()`` and it survives the test. Registering them here disposes
    # them SYNCHRONOUSLY (``shiboken6.delete``) at teardown exactly like the Phase-9
    # aids + the Slice-A cloud dialogs, so no collaboration panel accumulates across
    # the suite under ``pytest -n auto`` (the Phase-5/6/9 disposal-hygiene contract,
    # here a regression guard even though no worker was added).
    Shared_Projects_Panel,
    Comments_Panel,
    Presence_Panel,
    # Phase-10 Slice C real-time + branching disposables. ``Branching_Panel``
    # is a top-level ``QWidget`` and ``Live_Cursors_Overlay`` is a per-tab
    # ``QGraphicsItem`` on the shared scene; a test may build either directly (a
    # parent-less panel, or an overlay not yet added to a tracked window's scene), and
    # headless (offscreen, no running event loop) its ``deleteLater`` never fires, so it
    # survives the test (a panel lingers in ``topLevelWidgets()``; a standalone overlay
    # is never collected). Registering them here disposes them SYNCHRONOUSLY
    # (``shiboken6.delete``, ``isValid``-guarded so a window-owned overlay already freed
    # by its scene is skipped) at teardown exactly like the Phase-9 aids + Slice-A/-B
    # surfaces — so no branching panel or cursor overlay accumulates across the suite
    # under ``pytest -n auto`` (the Phase-5/6/9 disposal-hygiene contract). Neither owns
    # a worker thread; the off-GUI-thread real-time worker lives in ``Realtime_Session``
    # (drained separately below, FIRST, exactly as ``Main_Window.shutdown_prewarm`` does).
    Branching_Panel,
    Live_Cursors_Overlay,
    # User Guide (REQ-UG-UI-*). ``User_Guide_Dialog`` is a read-only,
    # fully-offline ``QDialog`` that loads its content SYNCHRONOUSLY from the
    # committed ``userguide_content/`` bundle — the UI implementation introduced NO off-thread
    # worker, timer, or network client, so there is NO new drain/teardown wiring
    # (disposal only, no ``shutdown_*`` call). When opened from the Help menu it is
    # parented to ``Main_Window`` (disposed with it), but a guide test may build one
    # STANDALONE (parent-less, with an injected model/reader); headless (offscreen,
    # no running event loop) its ``deleteLater`` never fires, so ``QApplication``
    # keeps it in ``topLevelWidgets()`` and it survives the test. Registering it here
    # disposes it SYNCHRONOUSLY (``shiboken6.delete``) at teardown exactly like the
    # Phase-9 aids + the Slice-A/-B/-C surfaces — so no guide dialog accumulates
    # across the suite under ``pytest -n auto`` (the disposal-hygiene contract; here a
    # regression guard even though no worker was added).
    User_Guide_Dialog,
    # Phase-11 asset-library panels. The three new dock panels
    # (asset library / tagging / search-filter) are top-level ``QWidget``s bound to a
    # synchronous, worker-free ``Asset_Library_Session`` (browse/tag/search is
    # purely in-memory over the immutable ``AssetCatalog`` value — the UI implementation introduced NO
    # off-thread worker, timer, or poller, so there is NO new drain/shutdown wiring).
    # STILL, a test may build a panel directly (parent-less) + register it with
    # ``qtbot.addWidget``; headless (offscreen, no running event loop) that widget's
    # ``deleteLater`` never fires, so ``QApplication`` keeps it in ``topLevelWidgets()``
    # and it survives the test. Registering them here disposes them SYNCHRONOUSLY
    # (``shiboken6.delete``) at teardown exactly like the Phase-9 aids + the
    # Slice-A/-B/-C surfaces + the User Guide — so no asset panel accumulates across the
    # suite under ``pytest -n auto`` (the Phase-5/6/9 disposal-hygiene contract; here a
    # regression guard even though no worker was added). ``Asset_Library_Session`` is a
    # parent-owned ``QObject`` (no widget, no worker) disposed with its parent — nothing
    # to register.
    Asset_Library_Panel,
    Asset_Tagging_Panel,
    Asset_Search_Panel,
    # Phase-11 dependency-graph view. ``Dependency_Graph_View`` is a
    # top-level ``QWidget`` bound to the SAME synchronous, worker-free
    # ``Asset_Library_Session`` — but on ``set_session`` it connects to the session's
    # ``catalogChanged`` AND ``graphChanged`` signals (its passive break surface refreshes
    # on both). No off-GUI-thread worker, timer, or poller is added (graph/break
    # queries are microsecond in-memory calls over the immutable graph value — the UI implementation
    # kept them synchronous), so there is NO new drain/shutdown wiring. STILL, a test may
    # build the view directly (parent-less) + register it with ``qtbot.addWidget``;
    # headless (offscreen, no running event loop) its ``deleteLater`` never fires, so
    # ``QApplication`` keeps it in ``topLevelWidgets()`` and it survives the test with its
    # session signal connections live. Registering it here disposes it SYNCHRONOUSLY
    # (``shiboken6.delete``) at teardown exactly like the earlier asset panels — deleting
    # the receiver drops its ``catalogChanged`` / ``graphChanged`` connections cleanly, so
    # no dangling connection survives into a later test's event loop (the recurring
    # PySide6 cross-thread/GC-of-Qt-C++ xdist native-segfault guard; Phase-5/6/9 disposal
    # contract, here a regression guard even though no worker was added).
    Dependency_Graph_View,
    # Phase-11 version-browser + reuse panels. ``Asset_Version_Browser``
    # and ``Asset_Reuse_Panel`` are top-level ``QWidget``s bound to the SAME synchronous,
    # worker-free ``Asset_Library_Session`` (revision read/record + reference-not-
    # copy are microsecond in-memory / CAS calls — the UI implementation added NO off-thread worker,
    # timer, or poller, so there is NO new drain/shutdown wiring). On ``set_session`` the
    # version browser connects to the session's ``catalogChanged`` signal (so a restore's
    # ``replace_descriptor`` reflection reaches the other panels), and the reuse panel
    # connects to ``catalogChanged`` (its shared-asset list refreshes on catalog change).
    # A test may build either widget directly (parent-less) + register it with
    # ``qtbot.addWidget``; headless (offscreen, no running event loop) its ``deleteLater``
    # never fires, so ``QApplication`` keeps it in ``topLevelWidgets()`` and it survives
    # the test with its session signal connections live. Registering them here disposes
    # them SYNCHRONOUSLY (``shiboken6.delete``) at teardown exactly like the earlier
    # asset panels — deleting the receiver drops its ``catalogChanged`` connection cleanly,
    # so no dangling connection survives into a later test's event loop (the recurring
    # PySide6 cross-thread/GC-of-Qt-C++ xdist native-segfault guard; Phase-5/6/9 disposal
    # contract, here a regression guard even though no worker was added).
    Asset_Version_Browser,
    Asset_Reuse_Panel,
    # Phase-9 guides/rulers overlay (decision-batch D-08/D-09/D-11/D-28
    # test wave). ``Guides_Rulers_Overlay`` builds two standalone, parent-less
    # top-level ``Ruler_Strip`` ``QWidget``s (``horizontal_ruler``/
    # ``vertical_ruler``) — a test that constructs the overlay directly (over
    # an injected view/scene, the shipped pattern in ``test_guides_rulers.py``
    # / ``test_aids_edges.py`` and this wave's ``test_snap_precedence.py`` /
    # ``test_guides_gestures.py``) never parents them to a tracked window.
    # Headless (offscreen, no running event loop) their ``deleteLater`` never
    # fires, so each survives in ``QApplication.topLevelWidgets()`` with a
    # LIVE ``paintEvent`` override that dereferences the (possibly since-
    # disposed) ``Canvas_View`` it was built over. Under ``pytest -n auto``,
    # once enough of these accumulate on one xdist worker, a LATER unrelated
    # test's ``qtbot``-driven ``app.processEvents()`` flushes a queued repaint
    # on one of them and hits ``libshiboken: Internal C++ object (Canvas_View)
    # already deleted`` — observed this session (82 scattered ``ERROR``s
    # across unrelated files under ``-n auto`` once this wave's two new test
    # modules added enough additional standalone overlays to cross the
    # threshold; a baseline run without them showed ZERO such errors,
    # isolating the cause). Registering ``Ruler_Strip`` here disposes both
    # rulers SYNCHRONOUSLY (``shiboken6.delete``) at teardown exactly like the
    # Phase-9/10/11 surfaces above — the same disposal-hygiene contract,
    # applied to a widget class this test suite already constructed
    # standalone before this wave, not a new pattern.
    Ruler_Strip,
)


def _register_on_init(cls: type) -> None:
    """Wrap ``cls.__init__`` once so every new instance joins the teardown set."""
    original = cls.__init__
    if getattr(original, "_pac_registered", False):
        return  # already wrapped (idempotent across re-imports)

    @functools.wraps(original)
    def _wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        _LIVE_UI_INSTANCES.add(self)

    _wrapped._pac_registered = True  # type: ignore[attr-defined]
    cls.__init__ = _wrapped  # type: ignore[method-assign]


#: Phase-10 Slice C: the real-time session owns the ONLY off-GUI-thread network worker
#: added this slice (a ``data/cloud`` ``TransportPort`` poll loop on a
#: ``threading.Thread`` + a GUI-thread-affine carrier). A window-owned session is drained
#: by ``Main_Window.shutdown_prewarm`` (which calls ``_realtime_session.shutdown()``
#: FIRST — see main_window.py), but a test may build a STANDALONE ``Realtime_Session``
#: (over an injected loopback factory) and connect it; if its worker thread or connected
#: carrier survives into a later test's GC it triggers the recurring PySide6 cross-thread
#: GC-of-Qt-C++ xdist native segfault (worse here with a live socket). Tracking it here so
#: the drain fixture calls the idempotent, event-loop-free ``shutdown()`` on every live
#: session — joining the worker (bounded) + releasing the carrier — BEFORE any disposal.
_REALTIME_DISPOSABLE = (Realtime_Session,)


for _tracked_cls in (
    Main_Window,
    CanvasScene,
    Tilemap_Canvas,
    *_PHASE9_DISPOSABLE,
    *_REALTIME_DISPOSABLE,
):
    _register_on_init(_tracked_cls)


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


# --------------------------------------------------------------------------- #
# Settings-store isolation (ADR-0070 section 8, ADR-0072).                      #
#                                                                              #
# The appearance preferences (style, mode, the pixel-perfect scaling flag, ...) #
# are persisted through ``QSettings`` (group ``appearance``), and the scaling   #
# flag is READ BEFORE ``QApplication`` exists (ADR-0072). A test that reached    #
# the real store would read the developer's own choices and could write its     #
# own over them (Windows registry, a macOS plist, a Linux ``.conf``).           #
#                                                                              #
# Two traps are measured, not assumed:                                          #
#   * ``QSettings.setPath`` and ``setDefaultFormat`` are process-global and work #
#     with no application object, so they are applied before ``qapp`` is built.  #
#   * ``QSettings(org, app)`` -- the two-argument constructor -- is ALWAYS       #
#     ``NativeFormat``, whatever ``setDefaultFormat`` says. On Windows and macOS  #
#     that is the registry / ``CFPreferences``, which ``setPath`` cannot move.   #
#     The redirect therefore reaches only the constructors that take the default #
#     format: ``QSettings()`` and ``QSettings(QSettings.defaultFormat(), scope,  #
#     org, app)`` -- the one ``ui/appearance_settings.py`` must use.             #
# ``assert_settings_isolated`` is the guard: it fails, before anything is        #
# written, when the effective location is outside the redirected root.           #
# --------------------------------------------------------------------------- #

#: Every (format, scope) pair whose search path is pointed at the temp root.
_SETTINGS_PATH_SLOTS = tuple(
    (fmt, scope)
    for fmt in (QSettings.Format.NativeFormat, QSettings.Format.IniFormat)
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope)
)


def redirect_settings_store(root: Path) -> None:
    """Point every ``QSettings`` search path at ``root`` and name the application.

    Static and process-global: it needs no ``QApplication`` (so it also runs in a
    bare subprocess before one is built), and it is the single code path used by
    the autouse fixtures AND by the guard test's subprocess, so what the guard
    proves is what the suite runs under. The default format becomes ``IniFormat``
    (a file under ``root``) and the organisation/application names are those
    ``ui/app.py`` sets, so a name-less ``QSettings()`` resolves to the same file
    the product's would.
    """
    root.mkdir(parents=True, exist_ok=True)
    for fmt, scope in _SETTINGS_PATH_SLOTS:
        QSettings.setPath(fmt, scope, str(root))
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APPLICATION_NAME)


def settings_location_is_under(file_name: str, root: Path) -> bool:
    """Whether a ``QSettings.fileName()`` is a file inside ``root`` (symlink-safe)."""
    real_root = os.path.normcase(os.path.realpath(str(root)))
    real_file = os.path.normcase(os.path.realpath(file_name))
    try:
        return os.path.commonpath([real_root, real_file]) == real_root
    except ValueError:  # different drives / mixed absolute+relative: not inside
        return False


def assert_settings_isolated(root: Path) -> None:
    """Fail unless the production constructors resolve inside ``root`` (read-only).

    Checks the default format, then the file each constructor form would use:
    the exact form ``appearance_settings`` uses
    (``QSettings(QSettings.defaultFormat(), UserScope, org, app)``) and the
    name-less ``QSettings()``. Only ``fileName()`` / ``format()`` are read, so a
    failure here has written nothing anywhere.
    """
    assert QSettings.defaultFormat() == QSettings.Format.IniFormat, (
        "QSettings default format is "
        f"{QSettings.defaultFormat()!s}; the settings store is NOT isolated"
    )
    product_form = QSettings(
        QSettings.defaultFormat(),
        QSettings.Scope.UserScope,
        ORGANIZATION_NAME,
        APPLICATION_NAME,
    )
    for label, settings in (
        ("QSettings(defaultFormat, UserScope, org, app)", product_form),
        ("QSettings()", QSettings()),
    ):
        where = settings.fileName()
        assert where and settings_location_is_under(where, root), (
            f"{label} resolves to {where!r}, outside the isolated root {str(root)!r}"
            " -- the settings store is NOT isolated"
        )


@contextlib.contextmanager
def settings_store_scope(root: Path, fallback: Path) -> Iterator[Path]:
    """Redirect to ``root`` for the block, then clean up and fall back safely.

    On exit the directory ``root`` is deleted and the search paths are pointed at
    ``fallback`` (the session's own temp directory), never back at the real
    location, so anything that touches ``QSettings`` between two tests still lands
    in a temporary place.
    """
    redirect_settings_store(root)
    try:
        yield root
    finally:
        redirect_settings_store(fallback)
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def _settings_store_session(tmp_path_factory):
    """Redirect ``QSettings`` once per process, before ``qapp`` can be created.

    Session-scoped autouse fixtures are instantiated before the session-scoped
    ``qapp`` that pytest-qt builds on first use, so no ``QApplication`` exists when
    this runs (``app_existed_at_redirect`` records it; the guard test asserts it is
    ``False``). The original default format and application names are restored at
    session end.
    """
    app_existed = QCoreApplication.instance() is not None
    original = (
        QSettings.defaultFormat(),
        QCoreApplication.organizationName(),
        QCoreApplication.applicationName(),
    )
    root = tmp_path_factory.mktemp("qsettings-session")
    redirect_settings_store(root)
    yield types.SimpleNamespace(root=root, app_existed_at_redirect=app_existed)
    QSettings.setDefaultFormat(original[0])
    QCoreApplication.setOrganizationName(original[1])
    QCoreApplication.setApplicationName(original[2])


@pytest.fixture(autouse=True)
def settings_store(_settings_store_session, tmp_path) -> Iterator[Path]:
    """Give every UI test its own temporary ``QSettings`` location (autouse).

    ``tmp_path`` is unique per test and per xdist worker and lives under pytest's
    base temp (``--basetemp``, which ``testing/run`` takes from the configured test
    temp root). Yields the directory; it is deleted after the test.
    """
    with settings_store_scope(
        tmp_path / "qsettings", _settings_store_session.root
    ) as root:
        yield root


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

    Phase-6 added the same hazard class to the tilemap canvas (a scene-owned
    :class:`~PySide6.QtCore.QThreadPool` chunk warmer + a
    ``TilemapChunkWarmSignals`` carrier) plus a 128-MiB-capable chunk-pixmap cache.

    This autouse teardown runs after **every** UI test — with no per-test opt-in —
    and, walking ONLY the ``_LIVE_UI_INSTANCES`` registry (never ``gc.get_objects()``;
    see that registry's rationale), calls the deterministic, event-loop-free
    :meth:`CanvasScene.shutdown_prewarm` / :meth:`Main_Window.shutdown_prewarm` /
    :meth:`Tilemap_Canvas.shutdown_warm` on every instance the test created, releases
    each tilemap chunk cache, then deletes the tracked widgets and forces a single
    collection — all while every pool is drained and every carrier disconnected. A
    ``Main_Window`` drains its own tabs' scenes AND its shared tilemap canvas, so a
    scene reached both via its window and directly is drained twice; every API is
    idempotent, so that is safe. The registry is populated at construction, so this
    covers the ``make_scene`` / ``make_view`` / tilemap factories AND the modules that
    build a ``CanvasScene`` / ``Main_Window`` / ``Tilemap_Canvas`` directly (e.g.
    ``test_lazy_perf.py``) without editing any of them.
    """
    yield

    import gc

    # Iterate ONLY the tracked instances (the WeakSet registry), never the whole
    # heap: ``list(...)`` snapshots them so disposal below can mutate the set. Each
    # instance is drained first (pool cleared + carrier released) — idempotent and
    # guarded, so a double/partial drain is harmless — mirroring the Phase-5
    # deterministic, event-loop-free contract. A ``Main_Window`` drains its own
    # tabs' scenes AND its shared tilemap canvas via ``shutdown_prewarm``; a
    # standalone ``CanvasScene`` / ``Tilemap_Canvas`` is drained directly.
    tracked = list(_LIVE_UI_INSTANCES)
    # Drain the real-time worker(s) FIRST — mirroring ``Main_Window.shutdown_prewarm``,
    # which stops/joins the network worker + releases the carrier before every dependent
    # teardown (the live-socket segfault guard). ``shutdown()`` is idempotent + event-
    # loop-free, so a window-owned session (already drained by its window's
    # ``shutdown_prewarm`` if that ran) and a standalone one both drain safely here.
    for obj in tracked:
        if isinstance(obj, Realtime_Session):
            try:
                obj.shutdown()
            except (RuntimeError, AttributeError):
                pass
    for obj in tracked:
        try:
            if isinstance(obj, (Main_Window, CanvasScene)):
                obj.shutdown_prewarm()
            elif isinstance(obj, Tilemap_Canvas):
                obj.shutdown_warm()
        except (RuntimeError, AttributeError):
            # RuntimeError: underlying Qt C++ object already deleted.
            # AttributeError: instance from a __init__ that raised before the warm
            # attributes existed -> nothing live to drain.
            pass

    # Release the tilemap chunk-pixmap caches (up to 128 MiB of QPixmaps each) NOW,
    # while we still hold each canvas (the resident tileset/pixel data is untouched —
    # only derived pixmaps are dropped, Article VI §3).
    for obj in tracked:
        try:
            if isinstance(obj, Tilemap_Canvas):
                obj._scene._chunk_cache.clear()
        except (RuntimeError, AttributeError):
            pass

    # DISPOSE the tracked widgets deterministically. Headless (offscreen, no running
    # event loop) a widget's ``deleteLater`` never fires, so QApplication keeps every
    # standalone widget in ``topLevelWidgets()`` and it — plus its scene, its
    # QThreadPool and (for a tilemap) its chunk cache — is NEVER collected. Across
    # 2452 tests those instances pile up monotonically, and BOTH the per-test
    # ``gc.collect()`` (which walks every live container) and — before this fix — the
    # whole-heap ``gc.get_objects()`` sweep scale with that pile, producing the
    # progressive teardown-cost tail that cancelled CI at the 75-min cap.
    #
    # ``shiboken6.delete`` deletes the underlying C++ object SYNCHRONOUSLY and — being
    # scoped to exactly the tracked instances — never disturbs qtbot's own widgets or
    # any object still in flight (a whole-app ``sendPostedEvents(DeferredDelete)``
    # flush is NOT event-loop-free and could delete an object another fixture still
    # holds — observed to crash the worker natively). Deleting a parent deletes its
    # children, so a Main_Window-owned tilemap canvas may already be gone by the time
    # the loop reaches it; ``isValid`` guards that. Pools were drained + carriers
    # disconnected above, so nothing live is torn across the delete.
    import shiboken6

    for obj in tracked:
        if isinstance(
            obj,
            (Main_Window, Tilemap_Canvas, *_PHASE9_DISPOSABLE, *_REALTIME_DISPOSABLE),
        ):
            try:
                if shiboken6.isValid(obj):
                    shiboken6.delete(obj)
            except (RuntimeError, AttributeError):
                pass

    # Collect NOW, while every pool is drained and every carrier disconnected, so no
    # worker thread / connected carrier survives into a later test where the Phase-5
    # cross-thread-GC-of-Qt-C++ segfault would otherwise fire. With the tracked widgets
    # deleted and the caches released, the heap stays bounded, so this collect stays
    # cheap and the per-test teardown cost stays flat across the 2452-test suite.
    gc.collect()


def release_latched_modifiers(*, verify: bool = True) -> None:
    """Release any keyboard modifier Qt still reports as held; raise if it stays held.

    ``QApplication.keyboardModifiers()`` is not the state of a keyboard: it is the
    modifier set carried by the LAST mouse or key event the application processed,
    and it stays that way until another such event arrives. A ``QTest`` mouse or key
    event sent with a modifier -- ``qtbot.mouseRelease(..., ControlModifier, ...)``,
    ``qtbot.keyClick(w, Key_Z, ControlModifier)`` -- therefore leaves it latched after
    the gesture is over, on the offscreen platform, on Windows and on Linux alike
    (measured). ``sendEvent(QContextMenuEvent)`` and a direct handler call do NOT
    refresh it, so a later test that reads the modifiers without sending its own
    modified-or-unmodified mouse/key event first sees the previous test's Ctrl.
    ``Timeline_Grid_View._on_context_menu_requested`` is exactly such a reader (Ctrl
    + right-click removes a frame, so it builds no menu): on CI run 39849201731 the
    four "create cel" context-menu tests failed on one xdist worker because a Ctrl
    drag test had run on that worker just before them.

    Releasing Control with ``NoModifier`` is the one event that clears every latched
    modifier (measured for Ctrl and for Shift+Alt, set by mouse and by key events), and
    a fresh unshown widget is enough to deliver it. With ``verify`` (the default) the
    release is skipped when nothing is held and the post-condition is asserted: a
    platform where the release does not take effect must fail loudly here rather than
    hand the next test a modifier it did not ask for.

    ``verify=False`` sends the release unconditionally and asserts nothing. It is for
    a TEARDOWN, where ``QApplication.keyboardModifiers`` cannot be trusted: a test may
    have replaced it with a fake that reports Ctrl (``test_input_scheme_frames.py``
    does, to drive Ctrl+right-click) and its ``monkeypatch`` is undone only AFTER this
    fixture's teardown, because an earlier autouse fixture also requests it. The real
    state is released all the same; the next test's setup then verifies it.
    """
    if QApplication.instance() is None:
        return
    if verify and QApplication.keyboardModifiers() == Qt.KeyboardModifier.NoModifier:
        return
    QTest.keyRelease(QWidget(), Qt.Key.Key_Control, Qt.KeyboardModifier.NoModifier)
    if verify:
        held = QApplication.keyboardModifiers()
        assert (
            held == Qt.KeyboardModifier.NoModifier
        ), f"a keyboard modifier is still reported as held after releasing it: {held!r}"


@pytest.fixture(autouse=True)
def _no_latched_modifiers() -> Iterator[None]:
    """Start and end every UI test with no keyboard modifier latched (autouse).

    Before: a predecessor on the same xdist worker -- from ANY module, scheduling
    decides which -- may have ended on a modified ``QTest`` event. After: this test
    must not leak its own into whatever runs next, in or out of this directory.
    See :func:`release_latched_modifiers` for the mechanism and the evidence.

    It requests NO ``qapp`` on purpose. Autouse fixtures are ordered by NAME, and this
    one sorts before ``_settings_store_session``: a ``qapp`` dependency here would
    build the ``QApplication`` ahead of the ``QSettings`` redirect and fail
    ``test_req_vi_ui_002_redirect_was_applied_before_any_qapplication`` (measured).
    Without one, a process that has no application yet has no modifier to release and
    the helper returns; every later test finds the application ``theme`` built.
    """
    release_latched_modifiers()
    yield
    release_latched_modifiers(verify=False)


@pytest.fixture(scope="session", autouse=True)
def _art_root_session(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Write the generated pixel-chrome art under the test temp root.

    The one app stylesheet references PNG files the product writes at run time
    (``ui/theme_art_files.py``); by default they go to the system temp directory.
    The suite keeps every temp artifact under its configured root (the
    ``--basetemp`` the runner sets), so the art is redirected there for the session
    and left for pytest's own retention to remove. Each xdist worker has its own
    base temp, so no two workers share a directory.
    """
    root = tmp_path_factory.mktemp("pixelart-art")
    reset_art(root)
    yield root
    reset_art(None)


@pytest.fixture(params=[THEME_LIGHT, THEME_DARK], autouse=True)
def theme(request: pytest.FixtureRequest, qapp) -> str:
    """Apply light/dark of the canonical style to the app; parametrises every test (025).

    Two modes of the DEFAULT style, not the full style x mode matrix: a six-way
    run of every UI test would triple the suite for no theme-specific assertion
    (ADR-0070 decision 9). The theme-sensitive gates are
    parametrised over every combination explicitly in ``test_theme.py``.
    """
    name = request.param
    apply_theme(qapp, name, DEFAULT_STYLE)
    return name


@pytest.fixture
def make_document():
    """Factory returning a fresh :class:`Document` with the starter palette."""

    def _make(width: int = 64, height: int = 64) -> Document:
        return Document(width, height, palette=Palette(STARTER))

    return _make


@pytest.fixture
def export_controller():
    """Yield a standalone :class:`Export_Controller`, torn down deterministically.

    Phase-7 export tests that drive the worker directly build an
    :class:`~pixelart_creator.ui.export_worker.Export_Controller` that is NOT
    parented to a ``Main_Window``, so it is not reached by the ``_LIVE_UI_INSTANCES``
    drain fixture (which tracks ``Main_Window`` / ``CanvasScene`` / ``Tilemap_Canvas``
    only — a ``Main_Window``'s own controller IS drained via ``shutdown_prewarm``).
    This fixture guarantees the standalone controller's window-owned
    ``QThreadPool`` + signal carrier are drained + released via the idempotent,
    event-loop-free ``shutdown()`` even if the test body asserts and fails — so no
    export worker thread / connected carrier survives into a later test's GC (the
    Phase-5 cross-thread-GC-of-Qt-C++ segfault guard, under ``pytest -n auto``).
    """
    from pixelart_creator.ui.export_worker import Export_Controller

    controller = Export_Controller()
    try:
        yield controller
    finally:
        controller.shutdown()


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
    from testing.suites.ui._ui_helpers import prepare_for_click

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
# Phase-6 tilemap builders. Pure-logic factories the UI binds to; no        #
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


# --------------------------------------------------------------------------- #
# Phase-8 automation fixtures. The window-owned Automation_Controller          #
# is already reached by the ``_drain_prewarm_after_test`` fixture above, since  #
# ``Main_Window.shutdown_prewarm`` calls ``self._automation_controller`.        #
# ``shutdown()`` (main_window.py) — so a window-owned controller drains and     #
# releases its carrier at teardown exactly like the export controller. A        #
# STANDALONE controller built directly in a test (responsiveness / teardown) is #
# NOT parented to a tracked Main_Window, so it needs the dedicated fixture below #
# (mirroring ``export_controller``) to guarantee its window-owned QThreadPool +  #
# signal carrier are drained + released even if the test body asserts and fails #
# — no automation worker thread / connected carrier survives into a later test's #
# GC (the Phase-5 cross-thread-GC-of-Qt-C++ segfault guard, under pytest -n auto)#
# --------------------------------------------------------------------------- #


@pytest.fixture
def automation_controller():
    """Yield a standalone :class:`Automation_Controller`, torn down deterministically."""
    from pixelart_creator.ui.automation_worker import Automation_Controller

    controller = Automation_Controller()
    try:
        yield controller
    finally:
        controller.shutdown()


@pytest.fixture
def mute_message_boxes(monkeypatch):
    """Patch the blocking ``QMessageBox`` helpers so error surfacing never hangs.

    Automation error/consent flows raise a modal ``QMessageBox`` (warning /
    information / critical). Headless with no event loop these would block, so the
    fixture records every call and returns immediately. ``question`` is left to the
    individual test to control (the consent-gate assertion needs a definite answer).
    Returns the recorded ``(kind, title, text)`` calls for assertion.
    """
    from PySide6.QtWidgets import QMessageBox

    calls: list = []

    def _record(kind):
        def _fn(parent, title, text, *a, **k):
            calls.append((kind, title, text))
            return QMessageBox.StandardButton.Ok

        return staticmethod(_fn)

    monkeypatch.setattr(QMessageBox, "warning", _record("warning"))
    monkeypatch.setattr(QMessageBox, "information", _record("information"))
    monkeypatch.setattr(QMessageBox, "critical", _record("critical"))
    return calls


@pytest.fixture
def plugin_isolation():
    """Restore the process-global plugin/DSL registries after a plugin test.

    ``logic.plugins._LOADED`` and ``logic.scripting._REGISTRY`` are module-global.
    A plugin test that enables a plugin / registers an op must not leak that state
    into a later test (or a parallel xdist worker's later test). This fixture
    snapshots both, then on teardown disables any newly loaded plugin and
    unregisters any op not present before the test — leaving the built-in ops
    (``batch_recolour`` / ``procgen``) intact.
    """
    from pixelart_creator.logic import plugins, scripting

    loaded_before = set(plugins._LOADED)
    ops_before = set(scripting.registered_ops())
    try:
        yield
    finally:
        for name in list(plugins._LOADED):
            if name not in loaded_before:
                handle = plugins._LOADED.get(name)
                if handle is not None:
                    handle.disable()
        for op in scripting.registered_ops():
            if op not in ops_before:
                scripting.unregister_command(op)
