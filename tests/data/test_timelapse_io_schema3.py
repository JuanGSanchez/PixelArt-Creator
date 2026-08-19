"""Tests for the .pixtimelapse schema-3 (identity-bearing) manifest (T40,
Q-21, REQ-P9-DATA-005; plan §10.3). Schema 1 stays untouched
(``tests/data/test_timelapse_io.py``'s 13 shipped tests, REQ-P9-DATA-003,
are not touched by this file and stay green). Schema 2 is read-only legacy
(``tests/data/test_timelapse_io_schema2.py``, T47) -- this module covers the
identity-bearing form and the refusal of identity-less payloads. Zero Qt.

SC-D005-1 (round-trips identities exactly; two identical-content frames
still carry distinct identities), SC-D005-2 (a schema-2 file loads, is not
played, its command_ids are never read as identities), SC-D005-3 (schema-1
is untouched by the identity change and refuses for its own reason,
NO_PAYLOAD, never NO_IDENTITY), SC-D005-4 (missing/duplicated/unresolvable
identities raise TimelapseIdentityError; nothing inferred, regenerated or
renumbered to make a file load).

Every test ends in an assertion on every branch it reaches (spec §0b.2): no
``return``, ``skip`` or bare ``pass`` inside a conditional stands in for an
assertion here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelart_creator.data import timelapse_io as tio
from pixelart_creator.data.snapshot_store import document_of, snapshot_of
from pixelart_creator.data.timelapse_io import (
    TimelapseIdentityError,
    TimelapseIOError,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.timelapse import (
    TIMELAPSE_IDENTITY_SCHEMA_VERSION,
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
GREEN = (0, 255, 0, 255)

#: The T47 fixture (a payload-carrying file written before this amendment,
#: carrying no stable identity) -- SC-D005-2's own scenario, and nothing a
#: post-amendment build can create anymore (serialize_payload refuses to
#: emit schema 2). Reused here rather than duplicated.
_LEGACY_SCHEMA2_FIXTURE = (
    Path(__file__).parent / "fixtures" / "timelapse_schema2_legacy.pixtimelapse"
)

_RECORDING_ID = "deadd00ddeadd00ddeadd00ddeadd00d"


def _frame_id(command_id) -> str:
    return f"{_RECORDING_ID}:{command_id}"


def _document(pixel) -> Document:
    doc = Document(2, 2, palette=Palette([RED, BLUE, GREEN]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, pixel)
    return doc


def _recorded_identity_session(pixels):
    """Build an identity-bearing (schema-3) session + snapshot/blob tables,
    one frame per pixel value -- mirrors what ``ui/timelapse_controls.py``
    (T34) now always persists."""
    snapshots = {}
    blobs = {}
    frames = []
    for command_id, pixel in enumerate(pixels):
        snapshot, doc_blobs = snapshot_of(_document(pixel))
        snapshot_id = f"snap-{command_id}"
        snapshots[snapshot_id] = snapshot
        blobs.update(doc_blobs)
        frames.append(
            TimelapseFrame(
                index=command_id,
                command_id=command_id,
                snapshot_id=snapshot_id,
                frame_id=_frame_id(command_id),
            )
        )
    session = TimelapseSession(
        schema_version=TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        frames=tuple(frames),
        recording_id=_RECORDING_ID,
    )
    return session, snapshots, blobs


def _provider_from_payload(payload):
    def provider(frame: TimelapseFrame):
        return document_of(payload.snapshots[frame.snapshot_id], payload.blobs)

    return provider


def _pixel_renderer(document):
    return document.frames[0].layers[0].buffer.get_pixel(0, 0)


# --------------------------------------------------------------------------- #
# SC-D005-1 -- a saved recording round-trips its frame identities exactly     #
# --------------------------------------------------------------------------- #


def test_round_trip_preserves_identities_in_order(tmp_path):
    pixels = [RED, BLUE, GREEN]
    session, snapshots, blobs = _recorded_identity_session(pixels)
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")

    loaded = tio.load_session_payload(written)
    assert [f.frame_id for f in loaded.session.frames] == [
        _frame_id(i) for i in range(len(pixels))
    ]
    assert loaded.session.recording_id == _RECORDING_ID


def test_each_loaded_frame_resolves_to_the_content_it_recorded(tmp_path):
    pixels = [RED, BLUE, GREEN]
    session, snapshots, blobs = _recorded_identity_session(pixels)
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")

    loaded = tio.load_session_payload(written)
    frames = replay(loaded.session, _provider_from_payload(loaded), _pixel_renderer)
    assert frames == tuple(pixels)


def test_two_frames_with_identical_content_still_carry_distinct_identities(tmp_path):
    # The assertion that separates this mechanism from a content digest
    # (SC-D005-1, plan §10.1): RED recorded twice still yields two frames.
    pixels = [RED, RED]
    session, snapshots, blobs = _recorded_identity_session(pixels)
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")

    loaded = tio.load_session_payload(written)
    ids = [f.frame_id for f in loaded.session.frames]
    assert len(ids) == 2
    assert ids[0] != ids[1]
    frames = replay(loaded.session, _provider_from_payload(loaded), _pixel_renderer)
    assert frames == (RED, RED)


# --------------------------------------------------------------------------- #
# SC-D005-2 -- a payload-carrying recording written before this amendment is  #
# refused, not reinterpreted                                                  #
# --------------------------------------------------------------------------- #


def test_schema2_file_loads_as_a_readable_record():
    loaded = tio.load_session_payload(_LEGACY_SCHEMA2_FIXTURE)
    assert loaded.session.schema_version == TIMELAPSE_PAYLOAD_SCHEMA_VERSION
    assert len(loaded.session.frames) == 3


def test_schema2_frames_carry_no_identity():
    loaded = tio.load_session_payload(_LEGACY_SCHEMA2_FIXTURE)
    assert all(f.frame_id is None for f in loaded.session.frames)


def test_schema2_command_ids_are_never_read_as_identities():
    loaded = tio.load_session_payload(_LEGACY_SCHEMA2_FIXTURE)
    loaded_frame_ids = {f.frame_id for f in loaded.session.frames}
    stored_command_ids = {f.command_id for f in loaded.session.frames}
    # frame_id is None for every frame -- command_id values (0, 1, 2) are
    # never promoted into the identity slot by any inference.
    assert loaded_frame_ids == {None}
    assert not (loaded_frame_ids & {str(c) for c in stored_command_ids})


def test_schema2_session_reports_no_identity_blocker():
    from pixelart_creator.logic.timelapse import (
        ReconstructionBlocker,
        ReconstructionExtent,
        ReconstructionSubstrate,
        reconstructability,
    )

    loaded = tio.load_session_payload(_LEGACY_SCHEMA2_FIXTURE)
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.SNAPSHOT,
        reachable_snapshot_ids=frozenset(loaded.snapshots),
    )
    verdict = reconstructability(loaded.session, extent)
    assert verdict.ok is False
    assert verdict.blocker is ReconstructionBlocker.NO_IDENTITY


def test_schema2_payload_with_a_hand_added_identity_key_is_still_read_as_schema2():
    # Discrimination is by the schema_version STRING ALONE (plan §10.3),
    # never by sniffing for an "identity" key -- a hand-edited schema-2
    # file that grew an "identity" field must still be refused as schema 2,
    # not silently promoted to schema-3 treatment.
    raw = json.loads(_LEGACY_SCHEMA2_FIXTURE.read_text(encoding="utf-8"))
    raw["frames"][0]["identity"] = "not-a-real-identity"
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(raw)


# --------------------------------------------------------------------------- #
# SC-D005-3 -- the schema-1 form is not touched by the identity change        #
# --------------------------------------------------------------------------- #


def test_schema1_session_is_equal_to_its_pre_amendment_shape(tmp_path):
    session = new_session()
    session = record_frame(session, command_id=5)
    session = record_frame(session, command_id=9)
    written = tio.save_session(session, tmp_path / "s1")

    loaded = tio.load_session(written)
    assert loaded == session


def test_schema1_frames_carry_exactly_index_and_command_id_no_identity_field(
    tmp_path,
):
    session = record_frame(new_session(), command_id=3)
    written = tio.save_session(session, tmp_path / "s1")
    raw = json.loads(written.read_text(encoding="utf-8"))
    assert set(raw["frames"][0].keys()) == {"index", "command_id"}
    assert "recording_id" not in raw


def test_schema1_refuses_for_no_payload_not_no_identity():
    # SC-D005-3's precedence (T33): a schema-1 frame has neither a snapshot
    # nor an identity and must refuse for its OWN reason.
    from pixelart_creator.logic.timelapse import (
        ReconstructionBlocker,
        ReconstructionExtent,
        ReconstructionSubstrate,
        reconstructability,
    )

    session = record_frame(new_session(), command_id=0)
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.SNAPSHOT, reachable_snapshot_ids=frozenset()
    )
    verdict = reconstructability(session, extent)
    assert verdict.ok is False
    assert verdict.blocker is ReconstructionBlocker.NO_PAYLOAD
    assert verdict.blocker is not ReconstructionBlocker.NO_IDENTITY


# --------------------------------------------------------------------------- #
# SC-D005-4 -- missing, duplicated or unresolvable identities are rejected    #
# defensively                                                                 #
# --------------------------------------------------------------------------- #


def test_missing_identity_at_schema3_raises_identity_error():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        "recording_id": _RECORDING_ID,
        "frames": [{"index": 0, "command_id": 0}],  # no "identity" key
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


def test_duplicated_identity_at_schema3_raises_identity_error():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        "recording_id": _RECORDING_ID,
        "frames": [
            {"index": 0, "command_id": 0, "identity": _frame_id(0)},
            {"index": 1, "command_id": 1, "identity": _frame_id(0)},
        ],
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


def test_identity_not_matching_the_pattern_raises_identity_error():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        "recording_id": _RECORDING_ID,
        "frames": [{"index": 0, "command_id": 0, "identity": "not-hex-shaped"}],
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


def test_identity_not_prefixed_by_the_root_recording_id_raises_identity_error():
    other_recording = "0" * 32
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        "recording_id": _RECORDING_ID,
        "frames": [{"index": 0, "command_id": 0, "identity": f"{other_recording}:0"}],
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


def test_missing_root_recording_id_at_schema3_raises_identity_error():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        # no "recording_id" key
        "frames": [{"index": 0, "command_id": 0, "identity": _frame_id(0)}],
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


def test_identity_field_on_schema1_or_schema2_is_rejected():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_SCHEMA_VERSION,
        "frames": [{"index": 0, "command_id": 0, "identity": _frame_id(0)}],
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


def test_recording_id_field_on_schema1_or_schema2_is_rejected():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
        "recording_id": _RECORDING_ID,
        "frames": [],
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


def test_invalid_payload_changes_nothing_on_disk(tmp_path):
    session, snapshots, blobs = _recorded_identity_session([RED])
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")
    before = written.read_bytes()

    raw = json.loads(written.read_text(encoding="utf-8"))
    raw["frames"][0]["identity"] = "not-hex-shaped"  # corrupt a copy, not the file
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(raw)

    after = written.read_bytes()
    assert before == after  # the on-disk file was never touched


def test_nothing_is_inferred_regenerated_or_renumbered_to_load_a_bad_file(tmp_path):
    # A missing identity is REFUSED, never synthesised from the frame's
    # index or command_id, however plausible that substitution might look.
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        "recording_id": _RECORDING_ID,
        "frames": [{"index": 0, "command_id": 0, "identity": None}],
        "snapshots": {},
        "blobs": {},
    }
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(payload)


# --------------------------------------------------------------------------- #
# serialize_payload refuses to emit schema 2; discrimination is by version    #
# string alone, never by key sniffing                                         #
# --------------------------------------------------------------------------- #


def test_serialize_payload_refuses_to_emit_schema2():
    session = TimelapseSession(
        schema_version=TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
        frames=(TimelapseFrame(index=0, command_id=0, snapshot_id="s"),),
    )
    with pytest.raises(TimelapseIOError):
        tio.serialize_payload(session, {"s": {"format": "pixproj"}}, {})


def test_serialize_payload_refuses_to_emit_schema1():
    session = record_frame(new_session(), command_id=0)
    with pytest.raises(TimelapseIOError):
        tio.serialize_payload(session, {}, {})


def test_schema3_file_that_lost_its_identities_raises_rather_than_reading_as_schema2(
    tmp_path,
):
    # Discrimination is by the schema_version STRING ALONE (plan §10.3): a
    # truncated/hand-edited schema-3 file that lost its "identity" fields
    # must RAISE, never be silently demoted to a permissive schema-2 read --
    # that demotion is Q-21's defect re-entering through the loader.
    session, snapshots, blobs = _recorded_identity_session([RED, BLUE])
    written = tio.save_session_payload(session, snapshots, blobs, tmp_path / "p")
    raw = json.loads(written.read_text(encoding="utf-8"))
    for frame in raw["frames"]:
        del frame["identity"]
    with pytest.raises(TimelapseIdentityError):
        tio.deserialize_payload(raw)
