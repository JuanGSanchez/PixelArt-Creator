"""Slice-C edge + guard coverage (REQ-P10-UI-012/-013; Article VII surfaces).

Phase-10 Slice C. Exercises the defensive guards, error paths, and rarely-hit branches of
the real-time worker / session, the live-cursor overlay, and the branching panel/session
that the acceptance tests do not drive head-on — so the whole Slice-C ``ui/`` addition
clears the coverage gate (>=90% line / >=80% branch) and its untrusted-input / no-crash
posture is proven. Both themes via the autouse fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QRectF, Signal

from pixelart_creator.data.cloud.loopback_transport import (
    LoopbackHub,
    LoopbackTransport,
)
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.convergence import MetadataOp, RasterOp
from pixelart_creator.logic.realtime_apply import encode_update
from pixelart_creator.ui.branching_panel import Branching_Panel, Branching_Session
from pixelart_creator.ui.live_cursors_overlay import (
    Live_Cursors_Overlay,
    cursor_color_for,
)
from pixelart_creator.ui.realtime_actions import Realtime_Session
from pixelart_creator.ui.realtime_worker import (
    Realtime_Client,
    RealtimeWorkerSignals,
    _dispatch_one,
    _drain_outbound,
    _teardown_transport,
    make_loopback_factory,
)


class _FakeClient(QObject):
    """A worker-free client stand-in emitting frames directly (session seam)."""

    frameReceived = Signal(str, object)
    connectionChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._active = False
        self.updates: list[bytes] = []
        self.presences: list[bytes] = []

    def is_active(self) -> bool:
        return self._active

    def set_transport_factory(self, _f) -> None:
        pass

    def connect_realtime(self, _document_id: str) -> None:
        self._active = True
        self.connectionChanged.emit(True)

    def disconnect_realtime(self) -> None:
        self._active = False
        self.connectionChanged.emit(False)

    def send_update(self, blob: bytes) -> None:
        self.updates.append(blob)

    def send_presence(self, payload: bytes) -> None:
        self.presences.append(payload)

    def shutdown_realtime(self) -> None:
        self._active = False


# --------------------------------------------------------------------------- #
# Realtime_Session outbound + error paths (fake client, no worker).             #
# --------------------------------------------------------------------------- #


def test_push_local_update_broadcasts_when_active(qtbot, make_document):
    """An active session encodes + sends a local update through the client."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=1)
    session.connect_realtime("doc", "alice")
    session.set_document(make_document())
    session.push_local_update((MetadataOp("k", "v", 1, 1),))
    assert len(fake.updates) == 1


def test_push_local_update_noop_when_inactive():
    """A local update with no active connection is a no-op (nothing sent)."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=1)
    session.push_local_update((MetadataOp("k", "v", 1, 1),))
    assert fake.updates == []


def test_push_local_update_surfaces_encode_error(qtbot):
    """An unencodable op surfaces via ``errorOccurred`` (never a crash)."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=1)
    session.connect_realtime("doc", "alice")
    with qtbot.waitSignal(session.errorOccurred, timeout=1000):
        session.push_local_update([object()])  # type: ignore[list-item]
    assert fake.updates == []


def test_push_local_cursor_broadcasts_presence(qtbot):
    """An active session broadcasts an ephemeral presence payload for the local cursor."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=1)
    session.connect_realtime("doc", "alice")
    session.push_local_cursor(3, 4, selection={"x": 0, "y": 0, "width": 8, "height": 8})
    assert len(fake.presences) == 1


def test_push_local_cursor_noop_without_member(qtbot):
    """With no member id (no active session) a local cursor broadcast is a no-op."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=1)
    session.push_local_cursor(1, 1)
    assert fake.presences == []


def test_update_frame_without_document_is_ignored(qtbot):
    """A valid update frame with no bound document is a safe no-op (no emit)."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=1)
    # No set_document -> _apply_update returns early.
    frame = sync_protocol.encode_update(
        "doc", encode_update((MetadataOp("k", "v", 1, 1),))
    )
    fake.frameReceived.emit("doc", frame)  # must not raise / emit


def test_update_targeting_missing_layer_surfaces_error(qtbot, make_document):
    """A raster op targeting a non-existent layer surfaces ``errorOccurred``."""
    fake = _FakeClient()
    session = Realtime_Session(client=fake, site_id=1)
    session.set_document(make_document(64, 64))
    bad = RasterOp(0, 999, 0, 0, bytes(64 * 64 * 4), 64, 64, 1, 1)
    frame = sync_protocol.encode_update("doc", encode_update((bad,)))
    with qtbot.waitSignal(session.errorOccurred, timeout=1000):
        fake.frameReceived.emit("doc", frame)


# --------------------------------------------------------------------------- #
# Realtime worker: transport-factory failure + loopback factory.                #
# --------------------------------------------------------------------------- #


def test_worker_transport_failure_surfaces_error(qtbot):
    """A transport factory that raises surfaces ``errorOccurred`` (worker backstop)."""

    def _boom() -> LoopbackTransport:
        raise RuntimeError("transport unavailable")

    session = Realtime_Session(_boom, site_id=1)
    try:
        with qtbot.waitSignal(session.errorOccurred, timeout=3000):
            session.connect_realtime("doc", "alice")
    finally:
        session.shutdown()


def test_make_loopback_factory_builds_a_transport():
    """``make_loopback_factory`` returns a hub + a factory that builds transports."""
    hub, factory = make_loopback_factory()
    assert isinstance(hub, LoopbackHub)
    transport = factory()
    assert isinstance(transport, LoopbackTransport)


def test_client_connect_without_factory_surfaces_error(qtbot):
    """A client with no transport factory surfaces an error on connect (no thread)."""
    client = Realtime_Client()  # no factory
    with qtbot.waitSignal(client.errorOccurred, timeout=1000):
        client.connect_realtime("doc")
    assert client.is_active() is False


def test_client_send_when_inactive_is_noop():
    """Send helpers on an inactive client are safe no-ops."""
    client = Realtime_Client()
    client.send_update(b"x")  # inactive -> dropped
    client.send_presence(b"y")
    assert client.is_active() is False


# --------------------------------------------------------------------------- #
# Live_Cursors_Overlay edges.                                                   #
# --------------------------------------------------------------------------- #


def test_overlay_set_scene_rect_updates_bounds():
    """Tracking a new scene rect updates the overlay bounding rect."""
    overlay = Live_Cursors_Overlay(QRectF(0, 0, 64, 64))
    overlay.set_scene_rect(QRectF(0, 0, 256, 256))
    assert overlay.boundingRect() == QRectF(0, 0, 256, 256)


def test_overlay_remove_and_clear_when_empty_are_noops():
    """Removing/clearing an empty roster is a safe no-op."""
    overlay = Live_Cursors_Overlay(QRectF(0, 0, 64, 64))
    overlay.remove_cursor("nobody")
    overlay.clear()
    assert overlay.cursor_count() == 0


def test_overlay_presence_with_non_numeric_cursor_is_ignored():
    """A presence payload with non-numeric cursor coordinates is ignored (Article VII)."""
    overlay = Live_Cursors_Overlay(QRectF(0, 0, 64, 64))
    overlay.apply_presence({"member_id": "x", "cursor": {"x": "NaN", "y": None}})
    assert overlay.cursor_count() == 0


def test_overlay_presence_with_degenerate_selection_drops_selection():
    """A zero/negative-size selection is dropped but the cursor still renders."""
    overlay = Live_Cursors_Overlay(QRectF(0, 0, 64, 64))
    overlay.apply_presence(
        {
            "member_id": "x",
            "cursor": {"x": 1, "y": 1},
            "selection": {"x": 0, "y": 0, "width": 0, "height": 0},
        }
    )
    assert overlay.cursor_ids() == ("x",)


def test_cursor_color_is_stable_per_member():
    """A member keeps the same display colour across frames (deterministic hue)."""
    assert cursor_color_for("alice") == cursor_color_for("alice")


# --------------------------------------------------------------------------- #
# Branching session + panel guards.                                             #
# --------------------------------------------------------------------------- #


def test_set_base_document_none_clears_session(make_document):
    """Clearing the base document empties the branch set."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    session.set_base_document(None)
    assert session.has_base() is False
    assert session.branch_names() == ()


def test_record_on_active_mainline_is_noop(make_document):
    """Recording on the mainline (the base) is a no-op — no op-log grows."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.record_on_active((MetadataOp("k", "v", 1, 1),))  # active == mainline
    # Nothing to assert beyond no-raise; mainline carries no feature op-log.
    assert session.active_branch() == "mainline"


def test_switch_to_unknown_branch_raises(make_document):
    """Switching to an unknown branch raises a domain error."""
    from pixelart_creator.logic.realtime_apply import RealtimeError

    session = Branching_Session()
    session.set_base_document(make_document())
    with pytest.raises(RealtimeError):
        session.switch_to("ghost")


def test_merge_unknown_branch_raises(make_document):
    """Merging an unknown branch raises a domain error."""
    from pixelart_creator.logic.realtime_apply import RealtimeError

    session = Branching_Session()
    session.set_base_document(make_document())
    with pytest.raises(RealtimeError):
        session.merge_to_mainline("ghost")


def test_panel_on_new_without_session_shows_info(qtbot, mute_message_boxes):
    """New Branch with no bound session surfaces an info box, not a crash."""
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel._on_new()
    assert any(kind == "information" for kind, _t, _x in mute_message_boxes)


def test_panel_on_new_cancelled_dialog_is_noop(qtbot, make_document, monkeypatch):
    """Cancelling the New Branch dialog creates nothing."""
    from PySide6.QtWidgets import QInputDialog

    session = Branching_Session()
    session.set_base_document(make_document())
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel.set_session(session)
    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False))
    )
    panel._on_new()
    assert session.branch_names() == ("mainline",)


def test_panel_on_new_duplicate_warns(
    qtbot, make_document, monkeypatch, mute_message_boxes
):
    """A duplicate branch name surfaces a warning (domain error caught)."""
    from PySide6.QtWidgets import QInputDialog

    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel.set_session(session)
    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("feature", True))
    )
    panel._on_new()
    assert any(kind == "warning" for kind, _t, _x in mute_message_boxes)


def test_panel_switch_and_merge_without_session_are_noops(qtbot):
    """Switch/merge with no bound session return quietly."""
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel._on_switch()
    panel._on_merge()  # no session -> no-op, no crash


def test_panel_switch_and_merge_without_selection_are_noops(qtbot, make_document):
    """Switch/merge with no list selection return quietly."""
    session = Branching_Session()
    session.set_base_document(make_document())
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel.set_session(session)
    panel._list.clearSelection()
    panel._list.setCurrentRow(-1)
    panel._on_switch()
    panel._on_merge()


def test_panel_refresh_without_session_is_safe(qtbot):
    """Refreshing an unbound panel clears the list without a session (guard)."""
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel._refresh()
    assert panel._list.count() == 0


# --------------------------------------------------------------------------- #
# Realtime worker internal functions (unit, no thread) — send/teardown paths.   #
# --------------------------------------------------------------------------- #


class _FakeTransport:
    """A minimal ``TransportPort`` stand-in for the worker's send/teardown paths."""

    def __init__(self, *, fail_send=False, fail_leave=False, fail_close=False) -> None:
        self._fail_send = fail_send
        self._fail_leave = fail_leave
        self._fail_close = fail_close
        self.updates: list[bytes] = []
        self.presence: list[bytes] = []
        self.left = False
        self.closed = False

    def send_update(self, _doc: str, blob: bytes) -> None:
        if self._fail_send:
            raise RuntimeError("send failed")
        self.updates.append(blob)

    def send_presence(self, _doc: str, payload: bytes) -> None:
        if self._fail_send:
            raise RuntimeError("send failed")
        self.presence.append(payload)

    def leave(self, _doc: str) -> None:
        if self._fail_leave:
            raise RuntimeError("leave failed")
        self.left = True

    def close(self) -> None:
        if self._fail_close:
            raise RuntimeError("close failed")
        self.closed = True


def test_dispatch_one_sends_update_and_presence(qtbot):
    """``_dispatch_one`` routes update/presence tuples to the transport."""
    transport = _FakeTransport()
    signals = RealtimeWorkerSignals()
    _dispatch_one(transport, "doc", ("update", b"u"), signals)
    _dispatch_one(transport, "doc", ("presence", b"p"), signals)
    assert transport.updates == [b"u"]
    assert transport.presence == [b"p"]


def test_dispatch_one_ignores_malformed_item(qtbot):
    """A non-``(kind, payload)`` item is ignored (defensive guard)."""
    transport = _FakeTransport()
    signals = RealtimeWorkerSignals()
    _dispatch_one(transport, "doc", "not-a-tuple", signals)
    _dispatch_one(transport, "doc", ("update", b"u", "extra"), signals)
    assert transport.updates == []


def test_dispatch_one_send_error_emits_failed(qtbot):
    """A transport send error is surfaced via ``failed`` and never kills the loop."""
    transport = _FakeTransport(fail_send=True)
    signals = RealtimeWorkerSignals()
    with qtbot.waitSignal(signals.failed, timeout=1000):
        _dispatch_one(transport, "doc", ("update", b"u"), signals)


def test_drain_outbound_sends_then_stops_on_sentinel(qtbot):
    """``_drain_outbound`` sends queued items and stops at the ``_STOP`` sentinel."""
    import queue

    from pixelart_creator.ui.realtime_worker import _STOP

    transport = _FakeTransport()
    signals = RealtimeWorkerSignals()
    outbound: "queue.Queue[object]" = queue.Queue()
    outbound.put(("update", b"a"))
    outbound.put(_STOP)
    outbound.put(("update", b"b"))  # after the sentinel -> not sent this drain
    _drain_outbound(transport, "doc", outbound, signals)
    assert transport.updates == [b"a"]


def test_teardown_transport_none_is_noop():
    """Tearing down a ``None`` transport is a safe no-op."""
    _teardown_transport(None, "doc")  # must not raise


def test_teardown_transport_leaves_and_closes():
    """Normal teardown leaves the room and closes the connection."""
    transport = _FakeTransport()
    _teardown_transport(transport, "doc")
    assert transport.left is True
    assert transport.closed is True


def test_teardown_transport_swallows_leave_and_close_errors():
    """Teardown is best-effort: leave/close errors never propagate."""
    transport = _FakeTransport(fail_leave=True, fail_close=True)
    _teardown_transport(transport, "doc")  # must not raise


def test_client_connect_is_idempotent_and_sends_when_active(qtbot):
    """A second connect while active is a no-op; sends queue on the active client."""
    hub = LoopbackHub()
    client = Realtime_Client(lambda: LoopbackTransport(hub))
    with qtbot.waitSignal(client.connectionChanged, timeout=3000):
        client.connect_realtime("doc")
    client.connect_realtime("doc")  # already active -> no-op guard
    client.send_update(b"u")  # active -> queued
    client.send_presence(b'{"member_id":"a"}')  # active -> queued
    assert client.is_active() is True
    client.shutdown_realtime()
    assert client.is_active() is False
