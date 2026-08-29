"""Entry-point smoke tests for the shipped GUI launcher (REQ-P13-* / Slice 13D).

Phase-13 Slice 13D added a packaged entry point so ``python -m pixelart_creator``
launches the app. These tests cover the headless-testable seam
:func:`pixelart_creator.ui.app.create_app` and its :func:`~pixelart_creator.ui.app.main`
wrapper WITHOUT entering the Qt event loop:

* ``create_app([])`` returns a ``(QApplication, Main_Window)`` pair, the window is
  shown/visible, and the application + organisation identity is set.
* A second call REUSES the existing ``QApplication.instance()`` (identity), never
  constructing a second one.
* Importing :mod:`pixelart_creator.ui.app` and :mod:`pixelart_creator.__main__` has
  NO import-time side effect (no ``QApplication`` is created at import) and both
  expose ``main`` / ``create_app`` — the in-process check plus a fresh-interpreter
  subprocess proof (the session already owns a ``qapp`` in-process).
* ``main`` wires ``create_app`` -> ``app.exec()``: with ``exec`` monkeypatched to a
  no-op returning 0, ``main([])`` returns 0 and a window was created. ``main`` is
  NEVER called unpatched EXCEPT via the bounded smoke-exit hook below (it would
  otherwise block on the real event loop).
* The ``PIXELART_SMOKE_EXIT_MS`` self-exit hook (Slice 13D): with the env var set to
  a small POSITIVE integer, a REAL (unpatched) ``main()`` — run in a FRESH subprocess
  so a genuine ``exec()`` is exercised without poisoning pytest-qt's session event
  loop — launches, reaches the event loop, and self-quits via
  ``QTimer.singleShot(N, app.quit)``, exiting 0 without hanging (a bounded
  ``subprocess`` timeout is the fail-fast hang guard). With an INVALID value
  ("abc"/""/"0"/"-5") the value is parsed defensively (``int()`` in try/except) and NO
  early-quit timer is scheduled — proven WITHOUT a blocking ``exec`` by no-op'ing
  ``exec`` + spying ``QTimer.singleShot`` (no positive-delay timer is armed, and the
  bad value never raises).

Every ``Main_Window`` built here is auto-registered with the ``_LIVE_UI_INSTANCES``
teardown registry (conftest wraps ``Main_Window.__init__``), so the xdist teardown
drains + disposes it — no dangling window survives (the segfault-hygiene contract).
This is an entry-point launch smoke, not a widget-appearance test, so the both-theme
autouse fixture parametrises it but no per-theme assertion is made. Headless.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pixelart_creator import __main__ as main_module
from pixelart_creator.ui import app as app_module
from pixelart_creator.ui.app import (
    APPLICATION_NAME,
    ORGANIZATION_NAME,
    create_app,
    main,
)
from pixelart_creator.ui.main_window import Main_Window


def test_create_app_returns_visible_window_and_identity(qtbot):
    """create_app([]) yields (QApplication, shown Main_Window) with app identity set."""
    app, window = create_app([])
    # Register with qtbot like the sibling UI tests; the conftest __init__ wrap also
    # tracks ``window`` in ``_LIVE_UI_INSTANCES`` so teardown disposes it (no dangling
    # top-level widget — the segfault-hygiene contract).
    qtbot.addWidget(window)

    assert isinstance(app, QApplication)
    assert isinstance(window, Main_Window)
    # show() was called inside create_app; offscreen still reports visible.
    assert window.isVisible() is True
    assert app.applicationName() == APPLICATION_NAME == "PixelArt Creator"
    assert app.organizationName() == ORGANIZATION_NAME == "PixelArt Creator"


def test_create_app_reuses_existing_application_instance(qtbot):
    """A second create_app REUSES QApplication.instance() — no second app is built."""
    existing = QApplication.instance()
    assert existing is not None  # pytest-qt owns the session qapp

    app1, window1 = create_app([])
    qtbot.addWidget(window1)
    app2, window2 = create_app([])
    qtbot.addWidget(window2)

    # Same singleton QApplication throughout (identity, not just equality).
    assert app1 is existing
    assert app2 is existing
    assert app1 is app2
    # Each call constructs a distinct window over the shared app.
    assert window1 is not window2


def test_modules_expose_entry_points_without_import_side_effects():
    """Importing app + __main__ exposes create_app/main and adds no QApplication.

    In-process a QApplication already exists (the session ``qapp``), so this asserts
    the module SURFACE (callables) rather than instance()-is-None; the fresh-process
    test below proves the no-import-time-QApplication contract directly.
    """
    assert callable(app_module.create_app)
    assert callable(app_module.main)
    # __main__ re-exports the real launcher (the thin ``python -m`` shim).
    assert main_module.main is app_module.main
    assert main is app_module.main


def test_no_qapplication_created_at_import_time():
    """A fresh interpreter importing the modules creates NO QApplication (offscreen)."""
    code = (
        "import os;"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen');"
        "import pixelart_creator.ui.app as a;"
        "import pixelart_creator.__main__ as m;"
        "from PySide6.QtWidgets import QApplication;"
        "assert QApplication.instance() is None, 'import created a QApplication';"
        "assert callable(a.create_app) and callable(a.main);"
        "assert m.main is a.main;"
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"fresh-import check failed:\nstdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}"
    )
    assert "OK" in result.stdout


def test_main_wires_create_app_to_exec(qtbot, monkeypatch):
    """main([]) routes through create_app then app.exec(); exec no-op'd returns 0.

    ``main`` is proven to wire create_app -> exec WITHOUT running the real event loop
    by stubbing ``QApplication.exec``. The window ``create_app`` builds is captured via
    a spy on the factory so it can be qtbot-registered for the teardown drain.
    """
    built: list[Main_Window] = []
    real_create_app = app_module.create_app

    def _spy(argv=None):
        app, window = real_create_app(argv)
        built.append(window)
        return app, window

    monkeypatch.setattr(app_module, "create_app", _spy)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)

    rc = main([])

    assert rc == 0
    assert len(built) == 1  # create_app was invoked exactly once
    qtbot.addWidget(built[0])  # register the launched window for drain/dispose
    assert built[0].isVisible() is True


def test_smoke_exit_hook_runs_real_event_loop_and_self_quits():
    """PIXELART_SMOKE_EXIT_MS=150 -> a REAL main() launches, self-quits, exits 0.

    This is the KEY new test: it exercises the REAL ``app.exec()`` event loop (no
    ``exec`` stub). With the env var set to a small positive value ``main`` arms
    ``QTimer.singleShot(150, app.quit)`` before ``app.exec()``, so the loop starts, the
    app paints headlessly, the timer fires, ``app.quit()`` unwinds the loop, and
    ``exec()`` returns 0 — proving the launch-and-self-exit smoke path end to end.

    It runs in a FRESH interpreter subprocess (like
    ``test_no_qapplication_created_at_import_time``), NOT in-process, for two reasons:
    (1) it constructs a genuine, fully owned :class:`QApplication` and calls the REAL
    ``exec()`` on it — a stronger proof than reusing pytest-qt's session ``qapp``;
    (2) running the real ``exec()``/``quit()`` ON the shared session ``qapp`` would
    poison every subsequent ``qtbot.waitSignal`` loop on the same worker (a QEventLoop
    hazard — verified: it stalls later off-thread automation tests), so an in-process
    real run is NOT teardown-clean. The child's window and app die with the process, so
    nothing leaks back into the suite. This is a harness constraint, not a product
    defect: a packaged launch owns the process and exits after ``main``.

    HANG GUARD: ``subprocess.run(timeout=...)`` bounds the run — if the 150 ms self-quit
    timer were broken, ``exec()`` would block forever and the timeout kills the child
    and fails the test FAST rather than hanging the suite. A clean, fast ``SMOKE_RC=0``
    plus exit code 0 therefore proves the timer actually terminated a real event loop.
    """
    code = (
        "import os, sys;"
        "os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen');"
        "from pixelart_creator.ui.app import main;"
        "rc = main([]);"
        "print(f'SMOKE_RC={rc}');"
        "sys.exit(rc)"
    )
    child_env = dict(os.environ)
    child_env["QT_QPA_PLATFORM"] = "offscreen"
    child_env["PIXELART_SMOKE_EXIT_MS"] = "150"

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=child_env,
            timeout=60,  # >> 150 ms; a broken timer -> hung exec() -> fail fast here
        )
    except subprocess.TimeoutExpired as exc:  # the hook did not self-quit -> hard fail
        pytest.fail(
            "smoke-exit hook did NOT terminate the real event loop within 60s "
            f"(app.exec() hung; the singleShot(150, quit) is broken): {exc!r}"
        )

    assert result.returncode == 0, (
        f"real smoke launch did not exit 0:\nstdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}"
    )
    # main() reached and returned 0 from the real exec() (clean self-quit), not merely a
    # process that exited 0 for another reason.
    assert "SMOKE_RC=0" in result.stdout, (
        f"main() did not return 0 from the real event loop:\nstdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}"
    )


@pytest.mark.parametrize("bad_value", ["abc", "", "0", "-5"])
def test_smoke_exit_hook_defensive_parse_ignores_invalid_value(
    qtbot, monkeypatch, bad_value
):
    """An invalid PIXELART_SMOKE_EXIT_MS is swallowed: no early-quit timer, no crash.

    Non-integer ("abc"/""), zero ("0"), and negative ("-5") values must all leave the
    app in its normal indefinite run (no self-exit timer). Proven WITHOUT a blocking
    ``exec``: ``QApplication.exec`` is no-op'd to return 0 (as the sibling wiring test
    does) and ``QTimer.singleShot`` is spied. ``main`` must (a) NOT raise on the bad
    value — the ``int()`` parse is guarded — and (b) NOT arm any POSITIVE-delay timer
    (its ``smoke_exit_ms > 0`` branch stays false). The only ``singleShot`` reaching the
    spy is ``Main_Window``'s own ``singleShot(0, ...)`` deferred recovery hook (0 ms),
    so asserting no captured call has a positive delay isolates ``main``'s quit timer
    exactly. The spied ``singleShot`` also never actually schedules that recovery hook,
    keeping the no-op run side-effect-free. The window is registered for the drain.
    """
    built: list[Main_Window] = []
    real_create_app = app_module.create_app

    def _spy(argv=None):
        app, window = real_create_app(argv)
        built.append(window)
        return app, window

    scheduled: list[tuple[int, object]] = []

    def _record_single_shot(msec, callback):
        scheduled.append((msec, callback))

    monkeypatch.setattr(app_module, "create_app", _spy)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    monkeypatch.setattr(QTimer, "singleShot", staticmethod(_record_single_shot))
    monkeypatch.setenv("PIXELART_SMOKE_EXIT_MS", bad_value)

    # The bad value must be swallowed by the defensive int() parse, never propagate.
    try:
        rc = main([])
    except Exception as exc:  # noqa: BLE001 - any raise here is the defect under test
        pytest.fail(
            f"main() raised on invalid PIXELART_SMOKE_EXIT_MS={bad_value!r}: {exc!r}"
        )

    assert rc == 0  # normal run; exec no-op returned 0
    assert len(built) == 1
    # main scheduled NO early-quit: its quit timer would be singleShot(N>0, app.quit).
    # Only Main_Window's deferred recovery singleShot(0, ...) may appear (delay 0).
    assert all(msec <= 0 for msec, _cb in scheduled), (
        f"invalid value {bad_value!r} armed a positive-delay timer "
        f"(unexpected early-quit scheduled): {scheduled!r}"
    )
    qtbot.addWidget(built[0])  # register the launched window for drain/dispose
