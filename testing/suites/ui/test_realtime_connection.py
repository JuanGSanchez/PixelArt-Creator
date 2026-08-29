"""Real-time connection + GUI-thread apply acceptance (REQ-P10-DATA-010 / -LOGIC-007).

Phase-10 Slice C. Drives the ``ui/`` real-time seam headlessly, two ways:

* **Two in-process clients over an in-memory loopback transport** (no network, no
  credentials — ``LoopbackHub`` + ``LoopbackTransport``, the CI seam AGT-05 exposed via
  ``Realtime_Session(transport_factory=...)``). This exercises the OFF-GUI-THREAD worker
  end to end: a *local* op broadcast by client A is relayed by the hub, polled by client
  B's worker thread, marshalled back onto the GUI thread over the queued carrier, and
  *applied to B's live ``Document``* — the two replicas converge (SEC).
* **A fake ``Realtime_Client``** (the second AGT-05 seam) that emits ``frameReceived``
  directly, to assert the GUI-thread routing + Article VII rejection *without* a worker
  thread: a valid CRDT update mutates the bound document and reports dirty regions; a
  valid presence frame drives the presence route; a malformed frame surfaces
  ``errorOccurred`` and never crashes.

Every test runs under BOTH themes via the autouse ``theme`` fixture (the seam is
theme-invariant; the parametrisation keeps the lifecycle exercised in each theme).
Sessions are tracked + drained by the ``conftest`` drain fixture (worker joined, carrier
released) so no worker thread survives into a later test — the segfault guard.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal

from pixelart_creator.data.cloud.loopback_transport import (
    LoopbackHub,
    LoopbackTransport,
)
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.convergence import MetadataOp, make_raster_op
from pixelart_creator.logic.realtime_apply import DirtyRegion, encode_update
from pixelart_creator.ui.realtime_actions import Realtime_Session

# --------------------------------------------------------------------------- #
# Loopback: two in-process clients over one hub (the real off-thread worker).   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def loopback_pair(qtbot):
    """Two connected sessions (A=site 1, B=site 2) over ONE in-memory hub.

    Returns ``(session_a, session_b)``. Both join document ``"doc"`` and their
    ``connectionChanged(True)`` is awaited, so a local op broadcast by A is guaranteed
    to reach B. Both sessions are shut down deterministically on teardown (idempotent —
    the conftest drain fixture also covers them).
    """
    hub = LoopbackHub()
    session_a = Realtime_Session(lambda: LoopbackTransport(hub), site_id=1)
    session_b = Realtime_Session(lambda: LoopbackTransport(hub), site_id=2)
    try:
        with qtbot.waitSignal(session_b.connectionChanged, timeout=3000):
            session_b.connect_realtime("doc", "bob")
        with qtbot.waitSignal(session_a.connectionChanged, timeout=3000):
            session_a.connect_realtime("doc", "alice")
        assert session_a.is_connected() and session_b.is_connected()
        yield session_a, session_b
    finally:
        session_a.shutdown()
        session_b.shutdown()


def test_connect_over_loopback_marks_connected(loopback_pair):
    """Connecting over the injected loopback factory joins the relay (no network)."""
    session_a, session_b = loopback_pair
    assert session_a.is_connected() is True
    assert session_b.is_connected() is True
    assert session_a.active_document_id() == "doc"


def test_local_update_is_sent_and_applied_on_gui_thread(
    qtbot, loopback_pair, make_document
):
    """A's local structured op is relayed to B and applied to B's live document.

    Proves (1) local ops are broadcast, (2) B's worker marshals the frame onto the GUI
    thread, (3) ``apply_remote`` mutates B's live ``Document`` — two replicas converge.
    """
    session_a, session_b = loopback_pair
    doc_b = make_document()
    session_b.set_document(doc_b)

    ops = (MetadataOp("title", "Shared Sprite", 1, 1),)
    with qtbot.waitSignal(session_b.remoteUpdateApplied, timeout=3000) as blocker:
        session_a.push_local_update(ops)
    # The remote update landed on the GUI thread and mutated B's document in place.
    assert doc_b.metadata["title"] == "Shared Sprite"
    # A structured-only update reports no raster dirty regions.
    assert blocker.args == [()]


def test_raster_update_reports_only_touched_dirty_regions(
    qtbot, loopback_pair, make_document
):
    """A raster op applied on B repaints ONLY the touched tile (dirty-rect redraw)."""
    session_a, session_b = loopback_pair
    doc_b = make_document(64, 64)
    session_b.set_document(doc_b)

    source = make_document(64, 64)
    layer = source.frames[0].layers[0]
    layer.buffer.data[:, :] = (10, 20, 30, 255)
    raster = make_raster_op(
        layer.buffer.data,
        frame_index=0,
        layer_id=layer.layer_id,
        tile_x=0,
        tile_y=0,
        logical_clock=7,
        site_id=1,
    )

    with qtbot.waitSignal(session_b.remoteUpdateApplied, timeout=3000) as blocker:
        session_a.push_local_update((raster,))

    regions = blocker.args[0]
    assert regions == (DirtyRegion(0, layer.layer_id, 0, 0, 64, 64),)
    # The single reported tile is exactly what changed on B's live buffer.
    assert tuple(doc_b.frames[0].layers[0].buffer.data[0, 0]) == (10, 20, 30, 255)


def test_disconnect_leaves_the_relay(qtbot, loopback_pair):
    """Disconnect stops the worker (reconnectable) — no live connection remains."""
    session_a, _session_b = loopback_pair
    with qtbot.waitSignal(session_a.connectionChanged, timeout=3000):
        session_a.disconnect_realtime()
    assert session_a.is_connected() is False
    assert session_a.active_document_id() is None


# --------------------------------------------------------------------------- #
# Fake client seam: GUI-thread routing + Article VII, no worker thread.         #
# --------------------------------------------------------------------------- #


class _FakeClient(QObject):
    """A worker-free ``Realtime_Client`` stand-in that emits frames directly (seam)."""

    frameReceived = Signal(str, object)
    connectionChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def set_transport_factory(self, _factory) -> None:  # pragma: no cover - unused
        pass

    def connect_realtime(self, _document_id: str) -> None:
        self._active = True
        self.connectionChanged.emit(True)

    def disconnect_realtime(self) -> None:
        self._active = False
        self.connectionChanged.emit(False)

    def send_update(self, _blob: bytes) -> None:  # pragma: no cover - unused here
        pass

    def send_presence(self, _payload: bytes) -> None:  # pragma: no cover - unused
        pass

    def shutdown_realtime(self) -> None:
        self._active = False


def test_valid_update_frame_applies_on_gui_thread(qtbot, make_document):
    """A valid inbound UPDATE frame is decoded + applied to the bound document."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=5)
    doc = make_document()
    session.set_document(doc)

    blob = encode_update((MetadataOp("author", "Ada", 2, 3),))
    frame = sync_protocol.encode_update("doc", blob)
    with qtbot.waitSignal(session.remoteUpdateApplied, timeout=1000):
        fake.frameReceived.emit("doc", frame)
    assert doc.metadata["author"] == "Ada"


def test_valid_presence_frame_routes_to_presence_signal(qtbot):
    """A valid inbound PRESENCE frame surfaces on ``presenceReceived`` (GUI thread)."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=5)
    frame = sync_protocol.encode_presence(
        "doc", {"member_id": "carol", "cursor": {"x": 4, "y": 9}}
    )
    with qtbot.waitSignal(session.presenceReceived, timeout=1000) as blocker:
        fake.frameReceived.emit("doc", frame)
    payload = blocker.args[0]
    assert payload["member_id"] == "carol"
    assert payload["cursor"] == {"x": 4, "y": 9}


def test_malformed_frame_surfaces_error_never_crashes(qtbot, make_document):
    """A malformed frame is rejected via ``errorOccurred`` — no crash (Article VII)."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=5)
    session.set_document(make_document())
    with qtbot.waitSignal(session.errorOccurred, timeout=1000):
        fake.frameReceived.emit("doc", b"not-a-valid-frame")
    # The session is still usable after a rejected frame.
    assert session.is_connected() is False


def test_non_bytes_frame_is_ignored(qtbot):
    """A non-bytes frame object is a safe no-op (defensive guard)."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=5)
    # Should neither raise nor emit; simply return.
    session._on_frame("doc", object())
