"""Tests for pixelart_creator.data.timelapse_io — .pixtimelapse persistence.

REQ-P9-DATA-001 (SC-L010-1): save_session -> load_session round-trips a
TimelapseSession to an equal session (same schema, same ordered frames) so it
replays identically. Defensive load (IO-3): malformed / unknown-version /
oversized / mistyped manifests raise TimelapseIOError (never eval, never crash).
Zero Qt.
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data import timelapse_io as tio
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.data.timelapse_io import TimelapseIOError
from pixelart_creator.logic import constants
from pixelart_creator.logic.timelapse import (
    TIMELAPSE_SCHEMA_VERSION,
    TimelapseFrame,
    TimelapseSession,
    new_session,
    record_frame,
)


def _session(n: int) -> TimelapseSession:
    s = new_session()
    for cid in range(n):
        s = record_frame(s, command_id=cid * 10)
    return s


# --------------------------------------------------------------------------- #
# Round-trip identity                                                          #
# --------------------------------------------------------------------------- #


def test_save_then_load_round_trips(tmp_path):
    session = _session(3)
    written = tio.save_session(session, tmp_path / "s")
    assert written.suffix == tio.FILE_SUFFIX
    assert written.exists()
    loaded = tio.load_session(written)
    assert loaded == session
    assert loaded.schema_version == TIMELAPSE_SCHEMA_VERSION
    assert [(f.index, f.command_id) for f in loaded.frames] == [
        (0, 0),
        (1, 10),
        (2, 20),
    ]


def test_empty_session_round_trips(tmp_path):
    session = new_session()
    loaded = tio.load_session(tio.save_session(session, tmp_path / "empty"))
    assert loaded == session
    assert loaded.frames == ()


def test_save_keeps_existing_suffix(tmp_path):
    written = tio.save_session(_session(1), tmp_path / "keep.pixtimelapse")
    assert written.name == "keep.pixtimelapse"


def test_save_accepts_str_path(tmp_path):
    written = tio.save_session(_session(1), str(tmp_path / "s"))
    assert written.exists()


def test_serialize_shape():
    payload = tio.serialize(_session(2))
    assert payload["format"] == tio.FORMAT_NAME
    assert payload["schema_version"] == TIMELAPSE_SCHEMA_VERSION
    assert payload["frames"] == [
        {"index": 0, "command_id": 0},
        {"index": 1, "command_id": 10},
    ]


def test_serialize_rejects_non_session():
    with pytest.raises(TimelapseIOError):
        tio.serialize({"not": "a session"})  # type: ignore[arg-type]


def test_error_is_a_project_io_error():
    # IO-3: the domain error extends the shared ProjectIOError family.
    assert issubclass(TimelapseIOError, ProjectIOError)


# --------------------------------------------------------------------------- #
# Defensive deserialise                                                        #
# --------------------------------------------------------------------------- #


def _valid_payload():
    return {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_SCHEMA_VERSION,
        "frames": [{"index": 0, "command_id": 5}],
    }


def test_deserialize_accepts_valid_payload():
    session = tio.deserialize(_valid_payload())
    assert session.frames[0].command_id == 5


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: "not a dict",
        lambda p: p.pop("format"),
        lambda p: p.update(format="other"),
        lambda p: p.pop("schema_version"),
        lambda p: p.update(schema_version=1),
        lambda p: p.update(schema_version="999"),  # unsupported version
        lambda p: p.update(frames="not a list"),
        lambda p: p.update(frames=[{"index": 0}]),  # missing command_id
        lambda p: p.update(frames=[{"index": 0, "command_id": "x"}]),  # bad type
        lambda p: p.update(frames=[{"index": 0, "command_id": True}]),  # bool
        lambda p: p.update(frames=[{"index": -1, "command_id": 0}]),  # negative
        lambda p: p.update(frames=[{"index": 1, "command_id": 0}]),  # non-contiguous
        lambda p: p.update(frames=["not a dict"]),
    ],
)
def test_deserialize_rejects_malformed(mutate):
    payload = _valid_payload()
    mutated = mutate(payload)
    target = mutated if mutated is not None else payload
    with pytest.raises(TimelapseIOError):
        tio.deserialize(target)


def test_deserialize_rejects_oversized_frame_list():
    payload = {
        "format": tio.FORMAT_NAME,
        "schema_version": TIMELAPSE_SCHEMA_VERSION,
        "frames": [
            {"index": k, "command_id": k}
            for k in range(constants.MAX_TIMELAPSE_FRAMES + 1)
        ],
    }
    with pytest.raises(TimelapseIOError):
        tio.deserialize(payload)


def test_load_rejects_invalid_json(tmp_path):
    path = tmp_path / "bad.pixtimelapse"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(TimelapseIOError):
        tio.load_session(path)


def test_load_rejects_missing_file(tmp_path):
    with pytest.raises(TimelapseIOError):
        tio.load_session(tmp_path / "nope.pixtimelapse")


def test_load_never_evals_payload(tmp_path):
    # Article VII: content is JSON-parsed, never eval'd. A JSON string that looks
    # like code is simply "not a JSON object" -> a typed error, no execution.
    path = tmp_path / "evil.pixtimelapse"
    path.write_text(
        json.dumps("__import__('os').system('echo pwned')"), encoding="utf-8"
    )
    with pytest.raises(TimelapseIOError):
        tio.load_session(path)
