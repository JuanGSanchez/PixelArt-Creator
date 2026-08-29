"""Tests for the in-memory loopback transport (Phase-10 Slice C, no Qt).

Covers REQ-P10-DATA-010: the client real-time transport port exercised hermetically in
CI over :class:`~pixelart_creator.data.cloud.loopback_transport.LoopbackHub` — no
network, no credentials. Proves the relay contract:

* an update sent by one client is relayed to the document's OTHER subscribers, never
  echoed to the sender;
* a late-joining client receives the persisted UPDATE backlog but NOT the (ephemeral)
  presence stream — presence-exclusion;
* every published frame is validated at the boundary (``sync_protocol.decode_message``);
  a malformed frame is rejected (Article VII) and never relayed;
* two clients exchanging updates over the loopback converge to the same document.
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data.cloud.loopback_transport import (
    LoopbackHub,
    LoopbackTransport,
)
from pixelart_creator.data.cloud.port import serialize_project
from pixelart_creator.data.cloud.transport import TransportError
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.cloud_validation import CloudValidationError
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX, MAX_CRDT_UPDATE_BYTES
from pixelart_creator.logic.convergence import MetadataOp, RasterOp, converge
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.realtime_apply import (
    RealtimeState,
    apply_remote,
    decode_update,
    encode_update,
)

TILE = CRDT_TILE_SIZE_PX
DOC = "doc-1"


def _solid_tile(value):
    return bytes([value]) * (TILE * TILE * 4)


def _presence_bytes(member_id="alice"):
    return json.dumps({"member_id": member_id}).encode("utf-8")


def _semantic_metadata(doc):
    """Order-independent metadata fingerprint (see realtime property-test note)."""
    return tuple(sorted(doc.metadata.items()))


# --------------------------------------------------------------------------- #
# Relay + self-exclusion.
# --------------------------------------------------------------------------- #


def test_update_relays_to_other_client_not_the_sender():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    b = LoopbackTransport(hub)
    a.join(DOC)
    b.join(DOC)

    blob = encode_update([MetadataOp("title", "shared", 1, 0)])
    a.send_update(DOC, blob)

    assert a.poll(DOC) == ()  # sender never receives its own update
    frames = b.poll(DOC)
    assert len(frames) == 1
    message = sync_protocol.decode_message(frames[0])
    assert message.kind is sync_protocol.ControlKind.UPDATE
    assert message.blob == blob


def test_distinct_client_ids():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    b = LoopbackTransport(hub)
    assert a.client_id != b.client_id


def test_poll_clears_the_queue():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    b = LoopbackTransport(hub)
    a.join(DOC)
    b.join(DOC)
    a.send_update(DOC, encode_update([MetadataOp("k", "v", 1, 0)]))
    assert len(b.poll(DOC)) == 1
    assert b.poll(DOC) == ()  # drained


def test_poll_unjoined_document_is_empty():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    assert a.poll("never-joined") == ()


# --------------------------------------------------------------------------- #
# Backlog on late join + presence-exclusion.
# --------------------------------------------------------------------------- #


def test_late_joiner_receives_update_backlog():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    a.join(DOC)
    blob = encode_update([MetadataOp("k", "v", 1, 0)])
    a.send_update(DOC, blob)

    late = LoopbackTransport(hub)
    late.join(DOC)  # subscribes AFTER the update was published
    frames = late.poll(DOC)
    assert len(frames) == 1
    assert sync_protocol.decode_message(frames[0]).blob == blob


def test_presence_relays_but_is_not_persisted_and_excludes_sender():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    b = LoopbackTransport(hub)
    a.join(DOC)
    b.join(DOC)

    a.send_presence(DOC, _presence_bytes("alice"))
    assert a.poll(DOC) == ()  # sender excluded from its own presence
    b_frames = b.poll(DOC)
    assert len(b_frames) == 1
    assert sync_protocol.decode_message(b_frames[0]).kind is (
        sync_protocol.ControlKind.PRESENCE
    )

    # A late joiner gets NO presence backlog (presence is ephemeral, never persisted).
    late = LoopbackTransport(hub)
    late.join(DOC)
    assert late.poll(DOC) == ()


def test_leave_stops_delivery():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    b = LoopbackTransport(hub)
    a.join(DOC)
    b.join(DOC)
    b.leave(DOC)
    a.send_update(DOC, encode_update([MetadataOp("k", "v", 1, 0)]))
    assert b.poll(DOC) == ()


def test_leave_unjoined_document_is_a_noop():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    a.leave("never-joined")  # must not raise


# --------------------------------------------------------------------------- #
# Article VII — untrusted-input validation at the boundary.
# --------------------------------------------------------------------------- #


def test_send_update_rejects_oversized_blob():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    a.join(DOC)
    with pytest.raises(CloudValidationError):
        a.send_update(DOC, b"x" * (MAX_CRDT_UPDATE_BYTES + 1))


def test_send_presence_rejects_non_bytes():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    a.join(DOC)
    with pytest.raises(TransportError):
        a.send_presence(DOC, {"member_id": "alice"})  # type: ignore[arg-type]


def test_send_presence_rejects_invalid_json():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    a.join(DOC)
    with pytest.raises(CloudValidationError):
        a.send_presence(DOC, b"\xff\xfe not json")


def test_send_presence_rejects_missing_member_id():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    a.join(DOC)
    with pytest.raises(CloudValidationError):
        a.send_presence(DOC, json.dumps({"cursor": {"x": 1}}).encode("utf-8"))


def test_hub_publish_rejects_malformed_frame_and_never_relays_it():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    b = LoopbackTransport(hub)
    a.join(DOC)
    b.join(DOC)
    with pytest.raises(CloudValidationError):
        hub.publish(a.client_id, b"garbage-not-a-frame")
    assert b.poll(DOC) == ()  # nothing was relayed


# --------------------------------------------------------------------------- #
# Convergence over the loopback relay.
# --------------------------------------------------------------------------- #


def _apply_inbound(doc, transport, state):
    for frame in transport.poll(DOC):
        message = sync_protocol.decode_message(frame)
        if message.kind is sync_protocol.ControlKind.UPDATE:
            apply_remote(doc, message.blob, site_id=0, state=state)


def test_two_clients_exchanging_updates_converge():
    base = Document(2 * TILE, TILE)
    base.add_layer("L2")

    hub = LoopbackHub()
    ta = LoopbackTransport(hub)
    tb = LoopbackTransport(hub)
    ta.join(DOC)
    tb.join(DOC)

    doc_a = converge(base, [], site_id=1)  # independent deep copies of the same base
    doc_b = converge(base, [], site_id=2)
    state_a = RealtimeState()
    state_b = RealtimeState()

    ops_a = [
        MetadataOp("title", "from-a", 1, 1),
        RasterOp(0, 1, 0, 0, _solid_tile(0x11), TILE, TILE, 5, 1),
    ]
    ops_b = [
        MetadataOp("author", "from-b", 1, 2),
        RasterOp(0, 1, 1, 0, _solid_tile(0x22), TILE, TILE, 5, 2),
    ]

    # Each client applies its own edits locally and publishes them.
    blob_a = encode_update(ops_a)
    blob_b = encode_update(ops_b)
    apply_remote(doc_a, blob_a, site_id=1, state=state_a)
    apply_remote(doc_b, blob_b, site_id=2, state=state_b)
    ta.send_update(DOC, blob_a)
    tb.send_update(DOC, blob_b)

    # Each client applies the other's relayed update.
    _apply_inbound(doc_a, ta, state_a)
    _apply_inbound(doc_b, tb, state_b)

    # Both metadata keys and both raster tiles survived on both replicas.
    assert _semantic_metadata(doc_a) == _semantic_metadata(doc_b)
    assert doc_a.metadata == {"title": "from-a", "author": "from-b"}
    for doc in (doc_a, doc_b):
        arr = doc.frames[0].layers[0].buffer.data
        assert (arr[0:TILE, 0:TILE] == 0x11).all()
        assert (arr[0:TILE, TILE : 2 * TILE] == 0x22).all()


def test_decode_update_round_trips_a_relayed_blob():
    hub = LoopbackHub()
    a = LoopbackTransport(hub)
    b = LoopbackTransport(hub)
    a.join(DOC)
    b.join(DOC)
    ops = (MetadataOp("k", "v", 1, 0),)
    a.send_update(DOC, encode_update(list(ops)))
    frame = b.poll(DOC)[0]
    assert decode_update(sync_protocol.decode_message(frame).blob) == ops
