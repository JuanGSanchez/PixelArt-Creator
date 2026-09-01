# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Off-GUI-thread real-time transport worker + deterministic teardown (Slice C).

Phase-10 Slice C (REQ-P10-DATA-010, REQ-P10-UI-013; ADR-0027 §3/§7). The real-time
client drives the Qt-free
:class:`~pixelart_creator.data.cloud.transport.TransportPort` (a
:class:`~pixelart_creator.data.cloud.loopback_transport.LoopbackTransport` in CI, a
:class:`~pixelart_creator.data.cloud.ws_transport.WebSocketTransport` out of CI) on a
**window-owned background worker thread**, because a live WebSocket relay must be polled
and written continuously without ever blocking the GUI thread. This is the single most
dangerous teardown surface in the project — a live network worker (and, for the real
``websockets`` client, its socket) surviving into a later GC cycle is the recurring
PySide6 cross-thread ``GC``-of-``Qt-C++`` xdist native segfault. Every design choice
here exists to make that impossible:

* :class:`RealtimeWorkerSignals` is a GUI-thread-affine :class:`QObject` carrier. The
  worker thread only *emits* over it (auto/queued delivery); it constructs **no** Qt
  object and touches **no** ``Document``/scene off-thread. All remote-update → document
  mutation is marshalled onto the GUI thread by the consumer
  (:class:`~pixelart_creator.ui.realtime_actions.Realtime_Session`).
* the worker **constructs the transport inside the worker thread** (via an injected,
  Qt-free factory) so the port object is *only ever* touched on that one thread — the
  loopback hub's queues are not thread-safe, and confining every ``join``/``poll``/
  ``send``/``leave``/``close`` to the worker thread makes that a non-issue. The GUI
  thread hands outbound work over a :class:`queue.Queue`.
* :class:`Realtime_Client` exposes an idempotent, **event-loop-free**
  :meth:`Realtime_Client.shutdown_realtime` that signals the loop to stop, wakes the
  blocking poll, closes the connection + leaves the room **on the worker thread**, joins
  the worker thread with a **bounded** wait, then disconnects and releases the
  GUI-thread carrier so no still-queued emission has a slot to land on. A reconnectable
  :meth:`Realtime_Client.disconnect_realtime` stops the worker but keeps the carrier
  alive. ``shutdown_realtime`` is wired into ``MainWindow.shutdown_prewarm`` /
  ``closeEvent`` **first** (before the dependent overlay widgets), so no worker thread,
  socket, or transport survives teardown.

There is **no** ``eval`` / ``exec`` here: the worker only relays opaque framed bytes;
decode + validation happen in the pure ``logic/sync_protocol`` /
``logic/cloud_validation`` layer on the consuming side (Article VII).
"""

from __future__ import annotations

import queue
import threading
from typing import Callable, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from pixelart_creator.data.cloud.transport import TransportPort

#: Builds a fresh :class:`TransportPort` on connect, called **on the worker thread**.
#: Injectable so a test (or the out-of-CI WebSocket path) swaps the loopback transport
#: with no UI change — the port is the provider-agnostic seam (REQ-P10-DATA-007).
TransportFactory = Callable[[], TransportPort]

#: Poll cadence, seconds — how often the worker drains inbound frames when idle. A
#: presentation-loop timing (not a domain tuning value, so module-local): outbound sends
#: wake the loop immediately via the queue, so this only bounds inbound latency.
_POLL_INTERVAL_S = 0.03

#: Bounded wait for the worker thread to join on teardown, ms (presentation-only timing,
#: mirrors ``cloud_worker._CLOUD_SHUTDOWN_WAIT_MS``). Past this the daemon backstop
#: guarantees the thread cannot block interpreter exit.
_WORKER_JOIN_WAIT_MS = 5000

#: Sentinel pushed to the outbound queue to wake a blocking ``get`` on stop.
_STOP = object()


class RealtimeWorkerSignals(QObject):
    """GUI-thread-affine carrier for the real-time worker's signals (queued delivery).

    The worker thread emits over this carrier only; the connected slots run on the GUI
    thread (auto-connection across threads => queued), so the consumer applies remote
    updates where the ``Document`` and scene live (never off-thread).
    """

    #: ``(document_id, raw_frame_bytes)`` — one inbound, transport-validated framed
    #: message; the consumer routes it with ``sync_protocol.decode_message``.
    frameReceived = Signal(str, object)
    #: ``(connected,)`` — the worker joined (``True``) the document's relay.
    connectionChanged = Signal(bool)
    #: ``(message,)`` — the worker hit a transport error (surfaced, never a crash).
    failed = Signal(str)
    #: emitted once when the worker loop has fully exited (thread is ending).
    stopped = Signal()


def _run_worker(
    factory: TransportFactory,
    document_id: str,
    outbound: "queue.Queue[object]",
    stop: threading.Event,
    signals: RealtimeWorkerSignals,
) -> None:
    """Worker-thread entry point: own the transport, poll inbound, drain outbound.

    Builds the transport here (so it is only ever touched on this thread), joins the
    relay, then loops: drain the outbound queue (local updates/presence), poll inbound
    framed messages and emit them, and block briefly on the queue for the next outbound
    (waking immediately on a send or on stop). On any exit path it leaves the room and
    closes the connection, then emits :attr:`RealtimeWorkerSignals.stopped`.
    """
    transport: Optional[TransportPort] = None
    try:
        transport = factory()
        transport.join(document_id)
        signals.connectionChanged.emit(True)
        while not stop.is_set():
            _drain_outbound(transport, document_id, outbound, signals)
            if stop.is_set():
                break
            _poll_inbound(transport, document_id, signals)
            try:
                item = outbound.get(timeout=_POLL_INTERVAL_S)
            except queue.Empty:
                continue
            if item is _STOP:
                break
            _dispatch_one(transport, document_id, item, signals)
    except Exception as exc:  # noqa: BLE001 - deliberate worker backstop
        # Any transport/connect failure surfaces as a message; it never crashes the
        # app and never re-raises through Qt.
        signals.failed.emit(f"{type(exc).__name__}: {exc}")
    finally:
        _teardown_transport(transport, document_id)
        signals.stopped.emit()


def _drain_outbound(
    transport: TransportPort,
    document_id: str,
    outbound: "queue.Queue[object]",
    signals: RealtimeWorkerSignals,
) -> None:
    """Send every queued outbound item without blocking (non-blocking drain)."""
    while True:
        try:
            item = outbound.get_nowait()
        except queue.Empty:
            return
        if item is _STOP:
            return
        _dispatch_one(transport, document_id, item, signals)


def _dispatch_one(
    transport: TransportPort,
    document_id: str,
    item: object,
    signals: RealtimeWorkerSignals,
) -> None:
    """Send one outbound ``(kind, payload)`` item; surface a send error, keep going."""
    if not isinstance(item, tuple) or len(item) != 2:
        return
    kind, payload = item
    try:
        if kind == "update":
            transport.send_update(document_id, payload)
        elif kind == "presence":
            transport.send_presence(document_id, payload)
    except Exception as exc:  # noqa: BLE001 - a bad send must not kill the loop
        signals.failed.emit(f"{type(exc).__name__}: {exc}")


def _poll_inbound(
    transport: TransportPort,
    document_id: str,
    signals: RealtimeWorkerSignals,
) -> None:
    """Emit every inbound framed message for ``document_id`` (raw bytes)."""
    for frame in transport.poll(document_id):
        signals.frameReceived.emit(document_id, bytes(frame))


def _teardown_transport(transport: Optional[TransportPort], document_id: str) -> None:
    """Leave the relay + close the connection on the worker thread (best-effort)."""
    if transport is None:
        return
    try:
        transport.leave(document_id)
    except Exception:  # noqa: BLE001 - teardown is best-effort, never raises
        pass
    close = getattr(transport, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001 - teardown is best-effort, never raises
            pass


class Realtime_Client(QObject):
    """Owns the real-time worker thread, its carrier, and deterministic teardown.

    Re-emits the worker's carrier signals as its own so the consumer
    (:class:`~pixelart_creator.ui.realtime_actions.Realtime_Session`) binds to a stable
    surface. Connect / disconnect may happen repeatedly during a session
    (:meth:`connect_realtime` / :meth:`disconnect_realtime`); the window-teardown
    :meth:`shutdown_realtime` additionally releases the carrier.
    """

    #: ``(document_id, raw_frame_bytes)`` — one inbound framed message (GUI thread).
    frameReceived = Signal(str, object)
    #: ``(connected,)`` — the real-time connection state changed.
    connectionChanged = Signal(bool)
    #: ``(message,)`` — a transport error occurred (surfaced to the user).
    errorOccurred = Signal(str)

    def __init__(
        self,
        transport_factory: Optional[TransportFactory] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Create an inactive client bound to ``transport_factory`` (test seam)."""
        super().__init__(parent)
        self._factory: Optional[TransportFactory] = transport_factory
        self._signals: Optional[RealtimeWorkerSignals] = RealtimeWorkerSignals()
        self._signals.frameReceived.connect(self._on_frame)
        self._signals.connectionChanged.connect(self._on_connection_changed)
        self._signals.failed.connect(self._on_failed)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._outbound: "queue.Queue[object]" = queue.Queue()
        self._document_id: Optional[str] = None

    # -- queries ----------------------------------------------------------

    def is_active(self) -> bool:
        """Return whether a worker thread is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def set_transport_factory(self, factory: TransportFactory) -> None:
        """Set the transport factory used on the next :meth:`connect_realtime`."""
        self._factory = factory

    # -- connect / send ---------------------------------------------------

    def connect_realtime(self, document_id: str) -> None:
        """Start the worker thread joined to ``document_id`` (idempotent per session).

        A second call while already connected is a no-op. The transport is built on the
        worker thread from the injected factory, so ``ui/`` never touches a provider or
        socket object on the GUI thread. Requires a factory to have been supplied.
        """
        if self._signals is None or self.is_active():
            return
        if self._factory is None:
            self.errorOccurred.emit("no real-time transport configured")
            return
        self._document_id = document_id
        self._stop = threading.Event()
        self._outbound = queue.Queue()
        self._thread = threading.Thread(
            target=_run_worker,
            args=(
                self._factory,
                document_id,
                self._outbound,
                self._stop,
                self._signals,
            ),
            name="pixelart-realtime-worker",
            daemon=True,
        )
        self._thread.start()

    def send_update(self, blob: bytes) -> None:
        """Queue a CRDT-update ``blob`` for the worker thread to send (non-blocking)."""
        if self.is_active():
            self._outbound.put(("update", bytes(blob)))

    def send_presence(self, payload: bytes) -> None:
        """Queue an ephemeral presence ``payload`` for the worker to send."""
        if self.is_active():
            self._outbound.put(("presence", bytes(payload)))

    # -- teardown ---------------------------------------------------------

    def disconnect_realtime(self) -> None:
        """Stop the worker thread + close the transport, keeping the carrier alive.

        Idempotent and event-loop-free: signals the loop to stop, wakes the blocking
        poll, and **joins** the worker thread (bounded) so the transport is left/closed
        on that thread before it ends — no socket or worker survives. The carrier is
        kept so a later :meth:`connect_realtime` reuses it. Emits
        :attr:`connectionChanged` ``False``.
        """
        thread = self._thread
        if thread is not None:
            self._stop.set()
            self._outbound.put(_STOP)
            thread.join(_WORKER_JOIN_WAIT_MS / 1000.0)
            self._thread = None
            self._document_id = None
        self.connectionChanged.emit(False)

    def shutdown_realtime(self) -> None:
        """Deterministically tear the worker + carrier down (idempotent; window close).

        Stops + joins the worker thread via :meth:`disconnect_realtime` (so the live
        transport/socket is closed on the worker thread with a bounded wait — the
        PySide6 cross-thread GC-of-Qt-C++ segfault guard), then disconnects and releases
        the GUI-thread signal carrier so any still-queued emission has no slot to land
        on. Safe to call repeatedly — from ``MainWindow.shutdown_prewarm`` /
        ``closeEvent`` and from a test drain fixture.
        """
        self.disconnect_realtime()
        signals = self._signals
        if signals is not None:
            for signal, slot in (
                (signals.frameReceived, self._on_frame),
                (signals.connectionChanged, self._on_connection_changed),
                (signals.failed, self._on_failed),
            ):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
            self._signals = None

    # -- carrier relay ----------------------------------------------------

    def _on_frame(self, document_id: str, frame: object) -> None:
        self.frameReceived.emit(document_id, frame)

    def _on_connection_changed(self, connected: bool) -> None:
        self.connectionChanged.emit(connected)

    def _on_failed(self, message: str) -> None:
        self.errorOccurred.emit(message)


def make_loopback_factory() -> Tuple[object, TransportFactory]:
    """Build a ``(hub, factory)`` pair for a hermetic loopback real-time session (CI).

    The returned factory builds a fresh
    :class:`~pixelart_creator.data.cloud.loopback_transport.LoopbackTransport` on the
    shared hub each connect — deterministic, no network, no credentials. A test that
    needs two collaborators builds a second transport on the same ``hub``. Imported
    lazily so this module's import never pulls the loopback transport when the real
    WebSocket transport is used instead.
    """
    from pixelart_creator.data.cloud.loopback_transport import (
        LoopbackHub,
        LoopbackTransport,
    )

    hub = LoopbackHub()

    def factory() -> TransportPort:
        return LoopbackTransport(hub)

    return hub, factory
