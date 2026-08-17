"""Tests for the .pixtimelapse schema-2 (payload-carrying) manifest (T14,
REQ-P9-DATA-004; plan §4.1). Schema 1 stays untouched and unmodified
(tests/data/test_timelapse_io.py, REQ-P9-DATA-003) -- this module covers only
the additive ``*_payload`` functions. Zero Qt.

SC-D003-1 (a pre-slice fixture loads unchanged), SC-D003-2 (no playability
field, either form), SC-D004-1..5 (round trip incl. blobs; both versions
load; a pre-slice build's clean refusal of schema 2; the size-bound refusal;
malformed/truncated/fingerprint-mismatch rejections).
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data import project_io
from pixelart_creator.data import timelapse_io as tio
from pixelart_creator.data.snapshot_store import snapshot_of
from pixelart_creator.data.timelapse_io import TimelapseIOError
from pixelart_creator.logic import constants
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.timelapse import (
    SUPPORTED_SCHEMA_VERSIONS,
    TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
    TIMELAPSE_SCHEMA_VERSION,
    TimelapseFrame,
    TimelapseSession,
    new_session,
    record_frame,
    replay,
)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _document(pixel) -> Document:
    doc = Document(2, 2, palette=Palette([RED, BLUE]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, pixel)
    return doc


def _recorded_payload_session(pixels):
    """Build a session + snapshot/blob tables: one frame per pixel value in
    ``pixels``, each frame's document snapshotted (mirrors what a real
    Snapshot_Document_Provider recording would persist)."""
    session = new_session()
    snapshots = {}
    blobs = {}
    frames = []
    for command_id, pixel in enumerate(pixels):
        doc = _document(pixel)
        snapshot, doc_blobs = snapshot_of(doc)
        snapshot_id = f"snap-{command_id}"
        snapshots[snapshot_id] = snapshot
        blobs.update(doc_blobs)
        frames.append(
            TimelapseFrame(
                index=command_id, command_id=command_id, snapshot_id=snapshot_id
            )
        )
    session = TimelapseSession(
        schema_version=TIMELAPSE_PAYLOAD_SCHEMA_VERSION, frames=tuple(frames)
    )
    return session, snapshots, blobs


# --------------------------------------------------------------------------- #
# SC-D003-1 -- a pre-slice (schema-1) fixture loads unchanged                 #
# --------------------------------------------------------------------------- #


def test_pre_slice_schema1_fixture_loads_unchanged(tmp_path):
    schema1_payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_SCHEMA_VERSION,
        "frames": [{"index": 0, "command_id": 5}, {"index": 1, "command_id": 9}],
    }
    path = tmp_path / "pre-slice.pixtimelapse"
    path.write_text(json.dumps(schema1_payload), encoding="utf-8")

    loaded = tio.load_session(path)
    assert loaded.schema_version == TIMELAPSE_SCHEMA_VERSION
    assert [(f.index, f.command_id, f.snapshot_id) for f in loaded.frames] == [
        (0, 5, None),
        (1, 9, None),
    ]

    # It is never silently upgraded or re-tagged.
    assert tio.serialize(loaded)["schema_version"] == TIMELAPSE_SCHEMA_VERSION


def test_pre_slice_fixture_via_payload_loader_yields_empty_tables(tmp_path):
    # deserialize_payload accepts a schema-1 body too (SC-D004-2): it yields
    # empty snapshot/blob tables, never inventing a payload.
    schema1_payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_SCHEMA_VERSION,
        "frames": [{"index": 0, "command_id": 5}],
    }
    result = tio.deserialize_payload(schema1_payload)
    assert result.session.schema_version == TIMELAPSE_SCHEMA_VERSION
    assert result.snapshots == {}
    assert result.blobs == {}


# --------------------------------------------------------------------------- #
# SC-D003-2 -- playability is never a stored field                           #
# --------------------------------------------------------------------------- #


def test_schema1_serialised_shape_has_only_format_version_frames():
    s = record_frame(new_session(), command_id=1)
    payload = tio.serialize(s)
    assert set(payload.keys()) == {"format", "schema_version", "frames"}
    assert set(payload["frames"][0].keys()) == {"index", "command_id"}


def test_schema2_payload_carries_no_playability_field():
    session, snapshots, blobs = _recorded_payload_session([RED])
    payload = tio.serialize_payload(session, snapshots, blobs)
    for key in ("playable", "playability", "is_playable"):
        assert key not in payload
        for snap in payload["snapshots"].values():
            assert key not in snap


# --------------------------------------------------------------------------- #
# SC-D004-1 -- round trip including blobs; replays to the same sequence       #
# --------------------------------------------------------------------------- #


def test_payload_round_trips_including_blobs(tmp_path):
    session, snapshots, blobs = _recorded_payload_session([RED, BLUE, RED])
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")
    assert written.suffix == tio.FILE_SUFFIX

    loaded = tio.load_session_payload(written)
    assert loaded.session.schema_version == TIMELAPSE_PAYLOAD_SCHEMA_VERSION
    assert [f.snapshot_id for f in loaded.session.frames] == [
        "snap-0",
        "snap-1",
        "snap-2",
    ]
    assert loaded.blobs == blobs
    # The fingerprint key was stripped back off on load.
    for body in loaded.snapshots.values():
        assert "fingerprint" not in body


def test_payload_replays_to_the_recorded_sequence(tmp_path):
    session, snapshots, blobs = _recorded_payload_session([RED, BLUE])
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")
    loaded = tio.load_session_payload(written)

    def provider(frame):
        # Ruling B (plan §8.3): DocumentProvider is keyed by the frame
        # itself, never by its ordinal.
        from pixelart_creator.data.snapshot_store import document_of

        return document_of(loaded.snapshots[frame.snapshot_id], loaded.blobs)

    def renderer(document):
        return document.frames[0].layers[0].buffer.get_pixel(0, 0)

    frames = replay(loaded.session, provider, renderer)
    assert frames == (RED, BLUE)


# --------------------------------------------------------------------------- #
# SC-D004-2 -- both versions load, neither confused for the other             #
# --------------------------------------------------------------------------- #


def test_both_schema_versions_load_and_report_their_own_form(tmp_path):
    schema1 = new_session()
    schema1 = record_frame(schema1, command_id=1)
    session2, snapshots, blobs = _recorded_payload_session([RED])

    p1 = tio.save_session(schema1, tmp_path / "s1")
    p2 = tio.save_session_payload(session2, snapshots, blobs, tmp_path / "s2")

    loaded1 = tio.load_session_payload(p1)
    loaded2 = tio.load_session_payload(p2)
    assert loaded1.session.schema_version == TIMELAPSE_SCHEMA_VERSION
    assert loaded1.snapshots == {} and loaded1.blobs == {}
    assert loaded2.session.schema_version == TIMELAPSE_PAYLOAD_SCHEMA_VERSION
    assert loaded2.snapshots and loaded2.blobs


# --------------------------------------------------------------------------- #
# SC-D004-3 -- a pre-slice build refuses schema 2 cleanly                     #
# --------------------------------------------------------------------------- #


def test_unsupported_future_schema_version_is_refused():
    # Simulates what a pre-slice build's SUPPORTED_SCHEMA_VERSIONS check does
    # for schema 2: this build's own deserialize()/deserialize_payload() must
    # equally refuse a version it does not know, cleanly, never guessing.
    assert TIMELAPSE_PAYLOAD_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": "3",
        "frames": [],
    }
    with pytest.raises(TimelapseIOError):
        tio.deserialize(payload)
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload(payload)


# --------------------------------------------------------------------------- #
# Plan §8.1 (Ruling A, 2026-08-17 addendum) -- TIMELAPSE_PAYLOAD_MAX_BYTES is  #
# Optional[int] = None ("UNVALUED"), not sys.maxsize. Two obligations, both   #
# T14 (A1-t1, A1-t2). A1-t1 (the refusal is proven under a patched bound) is  #
# the tests immediately below -- each patches `tio.TIMELAPSE_PAYLOAD_MAX_BYTES`#
# (the name this module imports by), NEVER `logic.constants`'s, per the      #
# ruling's own warning that patching the wrong name lets the test pass for   #
# the wrong reason.                                                          #
# --------------------------------------------------------------------------- #


def test_payload_bound_is_unvalued_until_the_campaign():
    """(A1-t2, plan §8.1) Pins the UNVALUED state so a skipped T22 valuation
    is a visible, named, passing statement of that fact rather than a silent
    gap. **T22 MUST DELETE THIS TEST** when it values the constant and
    narrows its annotation to `int` -- this test's own removal is the
    review-visible proof the valuation happened (plan §8.1, "What this costs
    stated rather than hidden").

    Written against the RULED shape (`Optional[int] = None`); as of this
    session `logic/constants.py` still ships the REJECTED placeholder
    (`sys.maxsize`), so this assertion is expected to fail until AGT-03
    applies Ruling A -- reported, not silently adapted around (Decision
    A4-D3).
    """
    assert constants.TIMELAPSE_PAYLOAD_MAX_BYTES is None


# --------------------------------------------------------------------------- #
# SC-D004-4 -- oversized payload refused at record/save time, never truncated #
# --------------------------------------------------------------------------- #


def test_oversized_payload_refused_at_serialize_time(monkeypatch):
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    session, snapshots, blobs = _recorded_payload_session([RED])
    with pytest.raises(TimelapseIOError):
        tio.serialize_payload(session, snapshots, blobs)


def test_oversized_payload_refused_at_save_time_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    session, snapshots, blobs = _recorded_payload_session([RED])
    target = tmp_path / "toobig"
    with pytest.raises(TimelapseIOError):
        tio.save_session_payload(session, snapshots, blobs, target)
    assert not target.with_suffix(tio.FILE_SUFFIX).exists()


def test_oversized_payload_refused_at_load_time_by_size_on_disk(tmp_path, monkeypatch):
    session, snapshots, blobs = _recorded_payload_session([RED])
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    with pytest.raises(TimelapseIOError):
        tio.load_session_payload(written)


def test_payload_bound_is_read_from_a_named_constant():
    assert tio.TIMELAPSE_PAYLOAD_MAX_BYTES is constants.TIMELAPSE_PAYLOAD_MAX_BYTES


# --------------------------------------------------------------------------- #
# SC-D004-5 -- malformed / truncated / fingerprint-mismatch rejections        #
# --------------------------------------------------------------------------- #


def test_frame_referencing_unknown_snapshot_is_rejected():
    session, snapshots, blobs = _recorded_payload_session([RED])
    with pytest.raises(TimelapseIOError):
        tio.serialize_payload(session, {}, blobs)


def test_deserialize_payload_rejects_fingerprint_mismatch():
    session, snapshots, blobs = _recorded_payload_session([RED])
    payload = tio.serialize_payload(session, snapshots, blobs)
    snapshot_id = next(iter(payload["snapshots"]))
    payload["snapshots"][snapshot_id]["fingerprint"] = "0" * 64
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload(payload)


def test_deserialize_payload_rejects_missing_referenced_blob():
    session, snapshots, blobs = _recorded_payload_session([RED])
    payload = tio.serialize_payload(session, snapshots, blobs)
    payload["blobs"] = {}
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload(payload)


def test_deserialize_payload_rejects_frame_referencing_unknown_snapshot():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
        "frames": [{"index": 0, "command_id": 0, "snapshot": "does-not-exist"}],
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload(payload)


def test_deserialize_payload_rejects_snapshot_missing_fingerprint():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
        "frames": [],
        "snapshots": {"s": {"format": "pixproj"}},
        "blobs": {},
    }
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload(payload)


def test_deserialize_payload_rejects_non_dict_root():
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload("not a dict")


def test_deserialize_payload_rejects_truncated_frames_type():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
        "frames": "not a list",
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload(payload)


def test_load_session_payload_never_evals(tmp_path):
    path = tmp_path / "evil.pixtimelapse"
    path.write_text(
        json.dumps("__import__('os').system('echo pwned')"), encoding="utf-8"
    )
    with pytest.raises(TimelapseIOError):
        tio.load_session_payload(path)


def test_load_session_payload_rejects_invalid_json(tmp_path):
    path = tmp_path / "bad.pixtimelapse"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(TimelapseIOError):
        tio.load_session_payload(path)
