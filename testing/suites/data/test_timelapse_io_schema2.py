"""Tests for the .pixtimelapse schema-2 (payload-carrying) manifest (T14,
REQ-P9-DATA-004; plan §4.1). Schema 1 stays untouched and unmodified
(testing/suites/data/test_timelapse_io.py, REQ-P9-DATA-003) -- this module covers only
the additive ``*_payload`` functions. Zero Qt.

SC-D003-1 (a pre-slice fixture loads unchanged), SC-D003-2 (no playability
field, either form), SC-D004-1..5 (round trip incl. blobs; both versions
load; a pre-slice build's clean refusal of schema 2; the size-bound refusal;
malformed/truncated/fingerprint-mismatch rejections).

**Re-keyed 2026-08-18 (Q-21, T33/T35/T47) onto the stable frame identity**
(REQ-P9-LOGIC-022, REQ-P9-DATA-005). ``serialize_payload``/
``save_session_payload`` now write **only** schema 3 (identity-bearing) and
raise ``TimelapseIOError`` if handed a schema-2 session -- schema 2 is
read-only legacy (a build that could still *emit* it could still *create*
the identity-less population REQ-P9-DATA-005 exists to stop creating).
**Substitutions this re-keying made (old assertion -> new assertion), listed
per the T47 done-when -- no assertion below was deleted:**

1. ``test_schema2_payload_carries_no_playability_field`` -- OLD: built a
   schema-2 session and called ``tio.serialize_payload`` directly (now
   refused). NEW: the assertion (no ``"playable"``/``"playability"``/
   ``"is_playable"`` key, top-level or per-snapshot) is unchanged, made
   against a **freshly serialised schema-3 (identity-bearing) payload**
   instead -- SC-D003-2 names "the payload-carrying form" generically, and
   schema 3 is what that form now IS.
2. ``test_payload_round_trips_including_blobs`` /
   ``test_payload_replays_to_the_recorded_sequence`` /
   ``test_both_schema_versions_load_and_report_their_own_form`` -- OLD: each
   called ``tio.save_session_payload`` on a freshly built schema-2 session
   (now refused). NEW: each reads
   ``testing/suites/data/fixtures/timelapse_schema2_legacy.pixtimelapse`` -- a
   **committed, read-only fixture** (provenance below) -- instead of writing
   one at test time; every original assertion (round-trips its frames and
   blobs, replays to the recorded pixel sequence, loads and reports its own
   schema version) is made against the loaded fixture, unchanged in
   substance. Per T47's own instruction, these gain **nothing** about
   identity -- that is T40's file (``test_timelapse_io_schema3.py``).
3. ``test_refusal_fires_above_the_shipped_bound`` /
   ``test_refusal_does_not_fire_below_the_shipped_bound`` /
   ``test_oversized_payload_refused_at_serialize_time`` /
   ``test_oversized_payload_refused_at_save_time_writes_nothing`` /
   ``test_oversized_payload_refused_at_load_time_by_size_on_disk`` /
   ``test_frame_referencing_unknown_snapshot_is_rejected`` /
   ``test_deserialize_payload_rejects_fingerprint_mismatch`` /
   ``test_deserialize_payload_rejects_missing_referenced_blob`` -- OLD: all
   built their session through ``_recorded_payload_session``, which
   constructed a **schema-2** session. Every one of these tests calls
   ``tio.serialize_payload``/``save_session_payload`` and asserts
   ``pytest.raises(TimelapseIOError)`` -- and since schema-2 now raises
   ``TimelapseIOError`` at the very first check (before the size/fingerprint/
   blob logic these tests actually name is ever reached), **four of these
   eight were passing already, but for the wrong reason** -- a
   schema-version refusal masquerading as the payload-bound or
   fingerprint-or-blob refusal the test claims to prove (the exact
   "returns/passes without asserting the real branch" shape spec §0b.2
   warns against, just via mis-directed generic exception type rather than
   a swallowed one). NEW: ``_recorded_payload_session`` is re-keyed to build
   an **identity-bearing (schema-3)** session (every frame carrying a
   ``frame_id``, the session carrying a ``recording_id``) -- the same shape
   ``ui/timelapse_controls.py`` (T34) now always produces -- so
   ``serialize_payload`` passes the schema gate and each test's
   ``pytest.raises`` is again reached by, and therefore actually proves, the
   specific size/fingerprint/blob-completeness branch it names.

**Fixture provenance (``testing/suites/data/fixtures/timelapse_schema2_legacy.pixtimelapse``,
substitution #2).** Generated once, at authoring time, by constructing the
identical wire shape ``serialize_payload`` produced for schema 2 **before**
Q-21 (three frames over a 2x2 document, pixels RED/BLUE/RED, one
content-hash-stamped snapshot per frame) using the still-available
``snapshot_of``/``content_hash``/``canonical_json_bytes`` helpers directly --
not through ``tio.serialize_payload`` itself, since that API now refuses to
produce this shape. It is committed read-only and never regenerated to make
a test pass (the fixture-integrity rule): it stands in for "a payload-
carrying file already on disk from before this amendment" (SC-D005-2's own
scenario), which is exactly what these three tests need and what nothing in
a post-amendment build can create for them anymore.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelart_creator.data import timelapse_io as tio
from pixelart_creator.data.snapshot_store import snapshot_of
from pixelart_creator.data.timelapse_io import (
    TimelapseIOError,
    TimelapsePayloadTooLargeError,
)
from pixelart_creator.logic import constants
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.timelapse import (
    SUPPORTED_SCHEMA_VERSIONS,
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

#: The committed, read-only schema-2 fixture (module docstring, substitution
#: #2 / provenance note) -- three frames, pixels RED/BLUE/RED.
_LEGACY_SCHEMA2_FIXTURE = (
    Path(__file__).parent / "fixtures" / "timelapse_schema2_legacy.pixtimelapse"
)

#: A fixed, 32-lowercase-hex-char per-module recording id (Q-21, T47
#: re-key) -- matches the shape `data/timelapse_io.py` validates.
_RECORDING_ID = "beadbeadbeadbeadbeadbeadbeadbead"


def _frame_id(command_id) -> str:
    return f"{_RECORDING_ID}:{command_id}"


def _document(pixel) -> Document:
    doc = Document(2, 2, palette=Palette([RED, BLUE]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, pixel)
    return doc


def _recorded_payload_session(pixels):
    """Build an **identity-bearing (schema-3)** session + snapshot/blob
    tables: one frame per pixel value in ``pixels``, each frame's document
    snapshotted (mirrors what a real Snapshot_Document_Provider recording
    would persist) AND carrying its own ``frame_id`` (mirrors what
    ``ui/timelapse_controls.py``, T34, now always mints). **Re-keyed
    2026-08-18 (T47, module docstring substitution #3)**: this helper used
    to build a schema-2 session, which ``serialize_payload`` now refuses
    outright -- every caller of this helper needs to reach the
    size/fingerprint/blob logic *past* the schema gate, which only a
    schema-3 session can do.
    """
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
    # Substitution #1 (module docstring): made against a freshly serialised
    # schema-3 payload -- serialize_payload can no longer emit schema 2, and
    # SC-D003-2 names "the payload-carrying form" generically.
    session, snapshots, blobs = _recorded_payload_session([RED])
    payload = tio.serialize_payload(session, snapshots, blobs)
    for key in ("playable", "playability", "is_playable"):
        assert key not in payload
        for snap in payload["snapshots"].values():
            assert key not in snap


# --------------------------------------------------------------------------- #
# SC-D004-1 -- round trip including blobs; replays to the same sequence       #
# Substitution #2 (module docstring): read from the committed legacy schema- #
# 2 fixture instead of writing one at test time (serialize_payload refuses   #
# schema 2 now) -- every original assertion is unchanged in substance.       #
# --------------------------------------------------------------------------- #


def test_payload_round_trips_including_blobs():
    raw = json.loads(_LEGACY_SCHEMA2_FIXTURE.read_text(encoding="utf-8"))
    loaded = tio.load_session_payload(_LEGACY_SCHEMA2_FIXTURE)
    assert loaded.session.schema_version == TIMELAPSE_PAYLOAD_SCHEMA_VERSION
    assert [f.snapshot_id for f in loaded.session.frames] == [
        "snap-0",
        "snap-1",
        "snap-2",
    ]
    assert loaded.blobs == raw["blobs"]
    # The fingerprint key was stripped back off on load.
    for body in loaded.snapshots.values():
        assert "fingerprint" not in body


def test_payload_replays_to_the_recorded_sequence():
    loaded = tio.load_session_payload(_LEGACY_SCHEMA2_FIXTURE)

    def provider(frame):
        # Ruling B (plan §8.3): DocumentProvider is keyed by the frame
        # itself, never by its ordinal.
        from pixelart_creator.data.snapshot_store import document_of

        return document_of(loaded.snapshots[frame.snapshot_id], loaded.blobs)

    def renderer(document):
        return document.frames[0].layers[0].buffer.get_pixel(0, 0)

    frames = replay(loaded.session, provider, renderer)
    # The fixture's own recorded pixels (provenance note, module docstring).
    assert frames == (RED, BLUE, RED)


# --------------------------------------------------------------------------- #
# SC-D004-2 -- both versions load, neither confused for the other             #
# --------------------------------------------------------------------------- #


def test_both_schema_versions_load_and_report_their_own_form(tmp_path):
    schema1 = new_session()
    schema1 = record_frame(schema1, command_id=1)

    p1 = tio.save_session(schema1, tmp_path / "s1")
    # Substitution #2: p2 is the committed legacy fixture, never written
    # fresh -- save_session_payload can no longer produce schema 2.
    p2 = _LEGACY_SCHEMA2_FIXTURE

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
    # Substitution (module docstring is silent on this one because it is not
    # part of the numbered list above -- named here instead): the ORIGINAL
    # probe used "3" as a stand-in unsupported future version. Schema "3" is
    # now REAL and SUPPORTED (TIMELAPSE_IDENTITY_SCHEMA_VERSION, Q-21) -- an
    # assertion that "3" is refused would now be simply false, not a defect
    # this file is testing. "4" is used instead as the genuinely unknown
    # future version; the schema-2 refusal-by-a-pre-slice-build half of
    # SC-D004-3 is unaffected (schema 2 is still supported for read, just
    # never written again).
    assert TIMELAPSE_PAYLOAD_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS
    assert TIMELAPSE_IDENTITY_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": "4",
        "frames": [],
    }
    with pytest.raises(TimelapseIOError):
        tio.deserialize(payload)
    with pytest.raises(TimelapseIOError):
        tio.deserialize_payload(payload)


# --------------------------------------------------------------------------- #
# Plan §9.2 (T21/T22, 2026-08-18) -- TIMELAPSE_PAYLOAD_MAX_BYTES is now VALUED #
# at 45_145_168 bytes (int, no longer Optional). The pin that held the honest #
# "unvalued" claim (test_payload_bound_is_unvalued_until_the_campaign) is     #
# deleted here -- its own removal is the review-visible proof the valuation   #
# happened (plan §8.1). What replaces it is the SHIPPED bound's contract: the #
# refusal fires above it, never below it, and raises the narrow subclass      #
# (`TimelapsePayloadTooLargeError`) rather than the generic `TimelapseIOError`#
# so a caller can distinguish "too large" from "malformed" by type alone.     #
#                                                                              #
# The real bound (~43.05 MiB) is too large to construct an honest over-size   #
# payload in a unit test, so the tests below still patch                     #
# `tio.TIMELAPSE_PAYLOAD_MAX_BYTES` (the name this module imports by, NEVER   #
# `logic.constants`'s -- a from-import means patching the constants name      #
# would not be seen through this module and the test would pass for the      #
# wrong reason) -- kept exactly per plan §8.1's warning, now applied to a     #
# valued bound instead of an unvalued one.                                    #
#                                                                              #
# **T49 (this session, 2026-08-18): repointed onto the schema-3 anchor.**     #
# `constants.py`'s `TIMELAPSE_PAYLOAD_MAX_BYTES` now derives from P4's        #
# freshly measured schema-3 figure -- `2_821_573` bytes at 1280x720 / 256     #
# frames (T43 re-measurement campaign, largest of its four points; see        #
# `design-docs/reports/perf-timelapse-payload-campaign-schema3-20260818.md`   #
# §3) -- extended by the unchanged `* (MAX_TIMELAPSE_FRAMES // 256)` frame-cap #
# ratio: `2_821_573 * (4096 // 256) == 45_145_168`. The schema-3 anchor is a  #
# FRESH measurement on a freshly generated fixture, not the old schema-2      #
# anchor plus any fixed per-byte cost of the new schema -- the two anchors    #
# are not directly comparable, and the movement between them must not be     #
# read as identity or schema 3 making payloads larger by that margin.         #
# --------------------------------------------------------------------------- #


def test_payload_bound_is_valued_at_the_measured_campaign_derivation():
    """(T22, plan §9.2; repointed T49) The bound is a real int, derived from
    P4's measured schema-3 payload size extended to the shipped frame cap:
    ``2_821_573 * (4096 // 256) == 45_145_168`` bytes. Asserts the derivation
    itself, not just the literal: if this fails, the constant moved without
    the measure -> value -> write chain (T43 -> T44 -> T45's shape) being
    re-run in the same review as whatever changed
    ``data/timelapse_io.py``'s serialised bytes -- re-run that chain rather
    than patching either side's arithmetic (Article II; constants.py's
    ANCHOR INVARIANT note on this constant).
    """
    measured_schema3_anchor_bytes = 2_821_573
    frame_cap_ratio = constants.MAX_TIMELAPSE_FRAMES // 256
    expected = measured_schema3_anchor_bytes * frame_cap_ratio
    assert expected == 45_145_168
    assert constants.TIMELAPSE_PAYLOAD_MAX_BYTES == expected, (
        "TIMELAPSE_PAYLOAD_MAX_BYTES no longer matches its derivation "
        f"({measured_schema3_anchor_bytes} * {frame_cap_ratio} = {expected}). "
        "The shipped constant moved without a fresh measure -> value -> "
        "write chain: re-run the T43-style re-measurement campaign against "
        "the current data/timelapse_io.py serialisation, re-value this "
        "constant from that measurement, and re-write both in the same "
        "unit of review as whatever changed the serialised bytes -- do not "
        "patch the arithmetic by hand."
    )
    assert isinstance(constants.TIMELAPSE_PAYLOAD_MAX_BYTES, int)


def test_refusal_fires_above_the_shipped_bound(monkeypatch):
    """The refusal actually fires once a payload exceeds the (patched, see
    module header) bound, and raises the narrow
    :class:`TimelapsePayloadTooLargeError` -- not just any
    :class:`TimelapseIOError` -- so callers can tell "too large" apart from
    "malformed" without parsing the message. **Re-keyed onto a schema-3
    session (T47, module docstring substitution #3)** -- with the old
    schema-2 session this raised too, but from the schema gate, never
    reaching the size check this test names.
    """
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    session, snapshots, blobs = _recorded_payload_session([RED])
    with pytest.raises(TimelapsePayloadTooLargeError):
        tio.serialize_payload(session, snapshots, blobs)


def test_refusal_does_not_fire_below_the_shipped_bound(monkeypatch):
    """A payload strictly under the (patched) bound serializes cleanly --
    the refusal is a genuine boundary check, not an always-raise stub.
    Re-keyed onto a schema-3 session (substitution #3): the old schema-2
    session could never reach this "serializes cleanly" branch at all once
    T35 landed, since serialize_payload now refuses it unconditionally.
    """
    session, snapshots, blobs = _recorded_payload_session([RED])
    exact_size = len(json.dumps(tio.serialize_payload(session, snapshots, blobs)))
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", exact_size + 1)
    payload = tio.serialize_payload(session, snapshots, blobs)
    assert payload["schema_version"] == TIMELAPSE_IDENTITY_SCHEMA_VERSION


# --------------------------------------------------------------------------- #
# SC-D004-4 -- oversized payload refused at record/save time, never truncated #
# --------------------------------------------------------------------------- #


def test_oversized_payload_refused_at_serialize_time(monkeypatch):
    # Re-keyed onto a schema-3 session (substitution #3): with the old
    # schema-2 session this passed already, but for the wrong reason -- the
    # schema gate fired before the size check the test claims to prove ever
    # ran. It now genuinely proves the size refusal.
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    session, snapshots, blobs = _recorded_payload_session([RED])
    with pytest.raises(TimelapsePayloadTooLargeError):
        tio.serialize_payload(session, snapshots, blobs)


def test_oversized_payload_refused_at_save_time_writes_nothing(tmp_path, monkeypatch):
    # Re-keyed onto a schema-3 session (substitution #3, same defect as
    # above: this passed before for the wrong reason).
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    session, snapshots, blobs = _recorded_payload_session([RED])
    target = tmp_path / "toobig"
    with pytest.raises(TimelapsePayloadTooLargeError):
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
    # Re-keyed onto a schema-3 session (substitution #3, same
    # wrong-reason-pass defect as the bound tests above).
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
