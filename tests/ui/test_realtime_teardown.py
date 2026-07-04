"""WS-worker teardown / segfault gate (Phase-10 Slice C — THE critical check).

Slice C adds the project's highest-risk native-segfault surface: an off-GUI-thread
real-time transport worker (a ``data/cloud`` ``TransportPort`` poll loop on a
``threading.Thread`` + a GUI-thread-affine ``QObject`` carrier). If that worker thread,
its transport socket, or its connected carrier survives into a later garbage-collection
cycle, PySide6 cross-thread-GCs a live Qt C++ object and the interpreter crashes natively
(the recurring xdist ``worker 'gwN' crashed`` segfault — worse here with a live socket).

This module proves the teardown contract rigorously:

* ``Main_Window.shutdown_prewarm`` (called by ``closeEvent``) invokes
  ``Realtime_Session.shutdown()`` -> ``Realtime_Client.shutdown_realtime()`` **FIRST**,
  before the dependent tab scenes / live-cursor overlays are torn down;
* after teardown NO real-time worker thread survives, the client's ``_thread`` is
  ``None`` and its GUI-thread carrier is released (``_signals is None``);
* an explicit **regression assertion**: after the window is disposed and GC runs, there
  is no live ``pixelart-realtime-worker`` thread anywhere in the process;
* the client uses a plain ``threading.Thread`` + ``queue.Queue`` (NO client-side asyncio
  event loop — the asyncio loop lives only in the out-of-layer backend, never imported by
  ``ui/``);
* ``shutdown_prewarm`` is idempotent (a second call is a safe no-op).

Every test runs under BOTH themes via the autouse ``theme`` fixture. NOTE: the conftest
drain fixture ALSO drains + disposes every tracked ``Realtime_Session`` / ``Main_Window``,
so these tests double as the guard that that wiring works.
"""

from __future__ import annotations

import gc
import threading

import shiboken6

from pixelart_creator.data.cloud.loopback_transport import (
    LoopbackHub,
    LoopbackTransport,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.realtime_actions import Realtime_Session

_WORKER_NAME = "pixelart-realtime-worker"


def _live_worker_threads():
    """Return every live real-time worker thread in the process (should be empty)."""
    return [t for t in threading.enumerate() if t.name == _WORKER_NAME and t.is_alive()]


# --------------------------------------------------------------------------- #
# Standalone session: connect over loopback, then deterministic teardown.       #
# --------------------------------------------------------------------------- #


def test_standalone_session_shutdown_joins_worker_and_releases_carrier(qtbot):
    """``shutdown()`` stops+joins the worker and releases the GUI-thread carrier."""
    hub = LoopbackHub()
    session = Realtime_Session(lambda: LoopbackTransport(hub), site_id=1)
    with qtbot.waitSignal(session.connectionChanged, timeout=3000):
        session.connect_realtime("doc", "alice")

    client = session.client()
    assert client._thread is not None  # a worker thread is running
    assert isinstance(client._thread, threading.Thread)  # threading, NOT asyncio
    assert session.is_connected() is True

    session.shutdown()

    assert session.is_connected() is False
    assert client._thread is None  # joined + cleared
    assert client._signals is None  # carrier disconnected + released
    assert _live_worker_threads() == []  # no worker survives


def test_standalone_session_shutdown_is_idempotent(qtbot):
    """A second ``shutdown()`` on an already-torn-down session is a safe no-op."""
    hub = LoopbackHub()
    session = Realtime_Session(lambda: LoopbackTransport(hub), site_id=1)
    with qtbot.waitSignal(session.connectionChanged, timeout=3000):
        session.connect_realtime("doc", "alice")
    session.shutdown()
    session.shutdown()  # must not raise
    assert session.client()._thread is None


def test_disconnect_reconnect_keeps_carrier_alive(qtbot):
    """``disconnect_realtime`` stops the worker but keeps the carrier for reconnect."""
    hub = LoopbackHub()
    session = Realtime_Session(lambda: LoopbackTransport(hub), site_id=1)
    with qtbot.waitSignal(session.connectionChanged, timeout=3000):
        session.connect_realtime("doc", "alice")
    with qtbot.waitSignal(session.connectionChanged, timeout=3000):
        session.disconnect_realtime()
    assert session.client()._thread is None
    assert session.client()._signals is not None  # carrier still alive
    # Reconnect works on the same client.
    with qtbot.waitSignal(session.connectionChanged, timeout=3000):
        session.connect_realtime("doc", "alice")
    assert session.is_connected() is True
    session.shutdown()
    assert _live_worker_threads() == []


# --------------------------------------------------------------------------- #
# Main_Window: teardown ordering + disposal regression.                         #
# --------------------------------------------------------------------------- #


def test_shutdown_prewarm_stops_realtime_before_dependent_teardown(qtbot, monkeypatch):
    """``shutdown_prewarm`` shuts the real-time worker down BEFORE the tab scenes."""
    win = Main_Window()
    qtbot.addWidget(win)

    order: list[str] = []
    real_rt_shutdown = win._realtime_session.shutdown
    real_scene_shutdown = win.active_tab().scene.shutdown_prewarm

    def _wrapped_rt() -> None:
        order.append("realtime")
        real_rt_shutdown()

    def _wrapped_scene() -> None:
        order.append("scene")
        real_scene_shutdown()

    monkeypatch.setattr(win._realtime_session, "shutdown", _wrapped_rt)
    monkeypatch.setattr(win.active_tab().scene, "shutdown_prewarm", _wrapped_scene)

    win.shutdown_prewarm()

    assert order, "neither teardown ran"
    assert order[0] == "realtime", f"real-time must stop first, got {order}"
    assert "scene" in order
    assert order.index("realtime") < order.index("scene")


def test_window_shutdown_prewarm_is_idempotent(qtbot):
    """Calling ``shutdown_prewarm`` twice is a safe no-op (closeEvent + fixture)."""
    win = Main_Window()
    qtbot.addWidget(win)
    win.shutdown_prewarm()
    win.shutdown_prewarm()  # must not raise
    assert win._realtime_session.is_connected() is False


def test_no_realtime_worker_survives_window_disposal(qtbot):
    """After connect -> shutdown -> dispose -> GC, no worker thread survives (regression).

    The explicit segfault-gate assertion: a live real-time worker connected through the
    window must be fully joined by ``shutdown_prewarm`` (the ``closeEvent`` path) and
    leave NO worker thread / socket / carrier alive into the GC that follows disposal.
    """
    win = Main_Window()
    hub = LoopbackHub()
    win._realtime_session.set_transport_factory(lambda: LoopbackTransport(hub))
    record = win.active_tab()
    win._realtime_session.set_document(record.document)

    with qtbot.waitSignal(win._realtime_session.connectionChanged, timeout=3000):
        win._realtime_session.connect_realtime("doc", "alice")
    assert win._realtime_session.is_connected() is True

    # closeEvent path: shutdown_prewarm stops + joins the worker FIRST.
    win.shutdown_prewarm()
    assert win._realtime_session.is_connected() is False
    assert win._realtime_session.client()._thread is None

    # Dispose the C++ window synchronously, then collect. The worker was already joined,
    # so no thread / socket / carrier is torn across the GC (the segfault guard).
    if shiboken6.isValid(win):
        shiboken6.delete(win)
    gc.collect()

    assert _live_worker_threads() == []
