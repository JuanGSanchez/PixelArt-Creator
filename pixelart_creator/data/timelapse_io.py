"""Read/write the ``.pixtimelapse`` session manifest (zero Qt, S11; DEP-4).

Defensive, ``eval``-free (de)serialisation of a
:class:`~pixelart_creator.logic.timelapse.TimelapseSession`, reusing the
``data.project_io`` IO-3 posture (REQ-P9-DATA-001; ADR-0025 §2): the on-disk format
is plain JSON — ``schema_version`` plus an ordered ``{index, command_id}`` frame
manifest (the command references, **not** inline pixel data — frames re-render on
replay, ADR-0024 §2). **Every field is type/bounds/version-checked on load**, a
malformed / out-of-bounds / unknown-``schema_version`` document raises
:class:`TimelapseIOError`, and content is **never** passed to ``eval``/``exec``.
Paths are built with :mod:`pathlib` for portability (``path_portability_check``).

Round-trip identity (the acceptance gate, SC-L010-1): a saved-then-reloaded session
is an **equal** :class:`TimelapseSession` (same schema, same ordered frames) and so
**replays to the identical frame sequence**.

**Schema 2 (D-12, plan §4.1) is additive, in new functions.** ``serialize`` /
``deserialize`` / ``save_session`` / ``load_session`` above are **untouched** — a
schema-1 file is read byte-identically through them, exactly as it always was,
and is never silently upgraded or re-tagged (REQ-P9-DATA-003). A schema-2
payload — frames that reference a :class:`TimelapsePayload` snapshot table plus
a shared, content-addressed blob table (``data/snapshot_store.py``) — is
produced and consumed through the new ``*_payload`` functions below, each
snapshot stamped with a ``content_hash(canonical_json_bytes(...))``
fingerprint that is recomputed and checked on load: a mismatch, like a missing
blob or a malformed/truncated/oversized payload, raises
:class:`TimelapseIOError` and changes nothing (Article VII; plan §2.1, the Vim
``'undofile'`` grounding — discard rather than misapply on divergence).
Playability is **computed, never a stored field** (REQ-P9-DATA-003): this
module records completeness and fingerprint validity; whether a given session
is playable is a caller (``ui/``) decision.

Layering: ``data -> logic`` (imports ``logic.timelapse``, ``logic.content_hash``)
and ``data -> data`` (``TimelapseIOError`` extends ``project_io.ProjectIOError``;
schema-2 support imports ``data.snapshot_store`` for ``BLOB_KEYS``, mirroring the
shipped ``snapshot_store -> project_io`` edge); never ``logic -> data``. Zero Qt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, Union

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.data.snapshot_store import BLOB_KEYS
from pixelart_creator.logic.constants import (
    MAX_TIMELAPSE_FRAMES,
    TIMELAPSE_PAYLOAD_MAX_BYTES,
)
from pixelart_creator.logic.content_hash import (
    canonical_json_bytes,
    content_hash,
    is_valid_hash,
)
from pixelart_creator.logic.timelapse import (
    SUPPORTED_SCHEMA_VERSIONS,
    TimelapseError,
    TimelapseFrame,
    TimelapseSession,
)

__all__ = [
    "TimelapseIOError",
    "FORMAT_NAME",
    "FILE_SUFFIX",
    "serialize",
    "deserialize",
    "save_session",
    "load_session",
    "TimelapsePayload",
    "serialize_payload",
    "save_session_payload",
    "deserialize_payload",
    "load_session_payload",
]

FORMAT_NAME = "pixtimelapse"
FILE_SUFFIX = ".pixtimelapse"

#: The key a snapshot's stamped fingerprint is stored under (plan §2.1, §4.1).
_FINGERPRINT_KEY = "fingerprint"


class TimelapseIOError(ProjectIOError):
    """Raised when a timelapse session cannot be serialised or is malformed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TimelapseIOError(message)


def _get_int(mapping: Any, key: str) -> int:
    _require(isinstance(mapping, dict), "expected a JSON object")
    _require(key in mapping, f"missing required key {key!r}")
    value = mapping[key]
    _require(
        isinstance(value, int) and not isinstance(value, bool),
        f"key {key!r} must be an int",
    )
    return value


# --------------------------------------------------------------------------- #
# Serialisation                                                               #
# --------------------------------------------------------------------------- #


def serialize(session: TimelapseSession) -> Dict[str, Any]:
    """Serialise a :class:`TimelapseSession` to a plain JSON-ready dict."""
    if not isinstance(session, TimelapseSession):
        raise TimelapseIOError(f"expected a TimelapseSession, got {session!r}")
    return {
        "format": FORMAT_NAME,
        "schema_version": session.schema_version,
        "frames": [
            {"index": frame.index, "command_id": frame.command_id}
            for frame in session.frames
        ],
    }


def save_session(session: TimelapseSession, path: Union[str, Path]) -> Path:
    """Serialise ``session`` and write it to ``path`` (adds ``.pixtimelapse``)."""
    target = Path(path)
    if target.suffix != FILE_SUFFIX:
        target = target.with_suffix(FILE_SUFFIX)
    payload = serialize(session)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Deserialisation (defensive)                                                 #
# --------------------------------------------------------------------------- #


def deserialize(payload: Dict[str, Any]) -> TimelapseSession:
    """Reconstruct a :class:`TimelapseSession` from a parsed manifest dict.

    Raises:
        TimelapseIOError: If the root, ``schema_version``, or any frame is missing,
            mistyped, out of bounds, or the version is unsupported.
    """
    _require(isinstance(payload, dict), "timelapse root must be a JSON object")
    _require(payload.get("format") == FORMAT_NAME, "not a pixtimelapse manifest")
    schema_version: Any = payload.get("schema_version")
    _require(isinstance(schema_version, str), "schema_version must be a string")
    _require(
        schema_version in SUPPORTED_SCHEMA_VERSIONS,
        f"unsupported timelapse schema_version {schema_version!r}; "
        f"supported: {SUPPORTED_SCHEMA_VERSIONS}",
    )
    frames_raw: Any = payload.get("frames")
    _require(isinstance(frames_raw, list), "frames must be a list")
    _require(
        len(frames_raw) <= MAX_TIMELAPSE_FRAMES,
        f"frames exceeds MAX_TIMELAPSE_FRAMES ({MAX_TIMELAPSE_FRAMES})",
    )
    frames = []
    for entry in frames_raw:
        _require(isinstance(entry, dict), "each frame must be a JSON object")
        index = _get_int(entry, "index")
        command_id = _get_int(entry, "command_id")
        try:
            frames.append(TimelapseFrame(index=index, command_id=command_id))
        except TimelapseError as exc:  # negative index/command_id
            raise TimelapseIOError(f"invalid timelapse frame: {exc}") from exc
    try:
        return TimelapseSession(schema_version=schema_version, frames=tuple(frames))
    except TimelapseError as exc:  # non-contiguous index / over-bound
        raise TimelapseIOError(f"invalid timelapse session: {exc}") from exc


def load_session(path: Union[str, Path]) -> TimelapseSession:
    """Read and validate a ``.pixtimelapse`` manifest into a session."""
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise TimelapseIOError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TimelapseIOError(f"{target} is not valid JSON: {exc}") from exc
    return deserialize(payload)


# --------------------------------------------------------------------------- #
# Schema 2 — payload-bearing sessions (D-12, additive; plan §4.1)             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TimelapsePayload:
    """A schema-2 ``.pixtimelapse`` payload: the session plus its snapshot/blob tables.

    Attributes:
        session: The command-manifest session; each frame carrying a
            ``"snapshot"`` entry in the file has the matching
            ``TimelapseFrame.snapshot_id`` set.
        snapshots: ``{snapshot_id: project_io.serialize-shaped dict}`` — blob
            strings hoisted to content-hash references
            (:data:`pixelart_creator.data.snapshot_store.BLOB_KEYS`), with the
            stamped ``"fingerprint"`` key **stripped** (it has already been
            verified against ``content_hash(canonical_json_bytes(...))`` of the
            rest of the body on load).
        blobs: ``{sha256hex: base64(zlib(raw))}`` — shared, deduplicated
            pixel/array payloads referenced from ``snapshots``.
    """

    session: TimelapseSession
    snapshots: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blobs: Dict[str, str] = field(default_factory=dict)


def _snapshot_fingerprint(snapshot_body: Dict[str, Any]) -> str:
    """Return the fingerprint of a snapshot body (excludes the ``fingerprint`` key)."""
    return content_hash(canonical_json_bytes(snapshot_body))


def _iter_blob_refs(node: Any) -> Iterator[str]:
    """Yield every blob-hash string at a :data:`BLOB_KEYS` key, recursively."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in BLOB_KEYS and isinstance(value, str):
                yield value
            else:
                yield from _iter_blob_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_blob_refs(item)


def _require_payload_size(payload: Dict[str, Any]) -> None:
    if TIMELAPSE_PAYLOAD_MAX_BYTES is None:
        return  # declared UNVALUED (plan §8.1) — no bound is configured, so no size
        # refusal is possible. NOT a permissive limit; T22 removes this arm.
    size = len(json.dumps(payload).encode("utf-8"))
    _require(
        size <= TIMELAPSE_PAYLOAD_MAX_BYTES,
        f"payload is {size} bytes, exceeds TIMELAPSE_PAYLOAD_MAX_BYTES "
        f"({TIMELAPSE_PAYLOAD_MAX_BYTES})",
    )


def serialize_payload(
    session: TimelapseSession,
    snapshots: Dict[str, Dict[str, Any]],
    blobs: Dict[str, str],
) -> Dict[str, Any]:
    """Serialise a schema-2 payload: frames + a fingerprinted snapshot table + blobs.

    ``snapshots`` maps a snapshot id (a caller-chosen stable key, e.g. the
    content hash :func:`pixelart_creator.data.snapshot_store.snapshot_of`'s
    output would be keyed by) to a ``project_io.serialize``-shaped dict with
    blob strings already hoisted to content-hash references. Each is stamped
    here with its own ``"fingerprint"`` — ``content_hash(canonical_json_bytes(...))``
    of the body, computed **before** the stamp is added. Never truncates: the
    whole payload is refused, whole, when it is too large — **while**
    :data:`TIMELAPSE_PAYLOAD_MAX_BYTES` **is unvalued (``None``, plan §8.1),
    no size refusal is performed at all**, which is the declared unvalued
    state, not a permissive limit.

    Raises:
        TimelapseIOError: If ``session`` is not a :class:`TimelapseSession`, a
            frame's ``snapshot_id`` has no entry in ``snapshots``, a snapshot
            body is not a JSON object, or — once
            :data:`TIMELAPSE_PAYLOAD_MAX_BYTES` is valued — the resulting
            payload exceeds it.
    """
    if not isinstance(session, TimelapseSession):
        raise TimelapseIOError(f"expected a TimelapseSession, got {session!r}")
    frames_out = []
    for frame in session.frames:
        entry: Dict[str, Any] = {"index": frame.index, "command_id": frame.command_id}
        if frame.snapshot_id is not None:
            _require(
                frame.snapshot_id in snapshots,
                f"frame {frame.index} references unknown snapshot "
                f"{frame.snapshot_id!r}",
            )
            entry["snapshot"] = frame.snapshot_id
        frames_out.append(entry)
    snapshots_out: Dict[str, Any] = {}
    for snapshot_id, body in snapshots.items():
        _require(
            isinstance(body, dict), f"snapshot {snapshot_id!r} must be a JSON object"
        )
        stamped = dict(body)
        stamped[_FINGERPRINT_KEY] = _snapshot_fingerprint(body)
        snapshots_out[snapshot_id] = stamped
    payload: Dict[str, Any] = {
        "format": FORMAT_NAME,
        "schema_version": session.schema_version,
        "frames": frames_out,
        "snapshots": snapshots_out,
        "blobs": dict(blobs),
    }
    _require_payload_size(payload)
    return payload


def save_session_payload(
    session: TimelapseSession,
    snapshots: Dict[str, Dict[str, Any]],
    blobs: Dict[str, str],
    path: Union[str, Path],
) -> Path:
    """Serialise a schema-2 payload and write it to ``path`` (adds ``.pixtimelapse``).

    Refuses (raises, writes nothing) rather than truncates a too-large payload
    (REQ-P9-DATA-004).
    """
    target = Path(path)
    if target.suffix != FILE_SUFFIX:
        target = target.with_suffix(FILE_SUFFIX)
    payload = serialize_payload(session, snapshots, blobs)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def deserialize_payload(payload: Dict[str, Any]) -> TimelapsePayload:
    """Reconstruct a :class:`TimelapsePayload` from a parsed schema-2 manifest dict.

    Every field is type/bounds/version-checked; each snapshot's stamped
    fingerprint is recomputed and compared, and every blob-hash string it
    references (:data:`BLOB_KEYS`) must resolve in ``blobs``. Frames are
    checked **in recorded order**, so the first mismatch or missing reference
    encountered names the first offending frame. A malformed, truncated, or
    fingerprint-mismatched payload raises :class:`TimelapseIOError` and nothing
    is partially returned. Accepts either schema version — a schema-1 payload
    (no ``"snapshots"``/``"blobs"`` keys) yields empty tables.

    Raises:
        TimelapseIOError: On any structural, bounds, version, fingerprint or
            blob-completeness failure.
    """
    _require(isinstance(payload, dict), "timelapse root must be a JSON object")
    _require(payload.get("format") == FORMAT_NAME, "not a pixtimelapse manifest")
    schema_version: Any = payload.get("schema_version")
    _require(isinstance(schema_version, str), "schema_version must be a string")
    _require(
        schema_version in SUPPORTED_SCHEMA_VERSIONS,
        f"unsupported timelapse schema_version {schema_version!r}; "
        f"supported: {SUPPORTED_SCHEMA_VERSIONS}",
    )

    blobs_raw = payload.get("blobs", {})
    _require(isinstance(blobs_raw, dict), "blobs must be an object")
    blobs: Dict[str, str] = {}
    for key, value in blobs_raw.items():
        _require(
            isinstance(key, str) and is_valid_hash(key), f"invalid blob key {key!r}"
        )
        _require(isinstance(value, str), f"blob {key!r} must be a base64 string")
        blobs[key] = value

    snapshots_raw = payload.get("snapshots", {})
    _require(isinstance(snapshots_raw, dict), "snapshots must be an object")
    snapshots: Dict[str, Dict[str, Any]] = {}
    for snapshot_id, body in snapshots_raw.items():
        _require(isinstance(snapshot_id, str), "snapshot id must be a string")
        _require(
            isinstance(body, dict), f"snapshot {snapshot_id!r} must be a JSON object"
        )
        _require(
            _FINGERPRINT_KEY in body and isinstance(body[_FINGERPRINT_KEY], str),
            f"snapshot {snapshot_id!r} is missing its fingerprint",
        )
        declared = body[_FINGERPRINT_KEY]
        stripped = {k: v for k, v in body.items() if k != _FINGERPRINT_KEY}
        actual = _snapshot_fingerprint(stripped)
        _require(
            declared == actual,
            f"snapshot {snapshot_id!r} fingerprint mismatch "
            f"(declared {declared!r}, computed {actual!r})",
        )
        for blob_ref in _iter_blob_refs(stripped):
            _require(
                blob_ref in blobs,
                f"snapshot {snapshot_id!r} references missing blob {blob_ref!r}",
            )
        snapshots[snapshot_id] = stripped

    frames_raw: Any = payload.get("frames")
    _require(isinstance(frames_raw, list), "frames must be a list")
    _require(
        len(frames_raw) <= MAX_TIMELAPSE_FRAMES,
        f"frames exceeds MAX_TIMELAPSE_FRAMES ({MAX_TIMELAPSE_FRAMES})",
    )
    frames = []
    for entry in frames_raw:
        _require(isinstance(entry, dict), "each frame must be a JSON object")
        index = _get_int(entry, "index")
        command_id = _get_int(entry, "command_id")
        snapshot_id = entry.get("snapshot")
        if snapshot_id is not None:
            _require(
                isinstance(snapshot_id, str) and snapshot_id in snapshots,
                f"frame {index} references unknown snapshot {snapshot_id!r}",
            )
        try:
            frames.append(
                TimelapseFrame(
                    index=index, command_id=command_id, snapshot_id=snapshot_id
                )
            )
        except TimelapseError as exc:
            raise TimelapseIOError(f"invalid timelapse frame {index}: {exc}") from exc
    try:
        session = TimelapseSession(schema_version=schema_version, frames=tuple(frames))
    except TimelapseError as exc:
        raise TimelapseIOError(f"invalid timelapse session: {exc}") from exc
    return TimelapsePayload(session=session, snapshots=snapshots, blobs=blobs)


def load_session_payload(path: Union[str, Path]) -> TimelapsePayload:
    """Read and validate a ``.pixtimelapse`` manifest into a :class:`TimelapsePayload`.

    A file whose size on disk already exceeds :data:`TIMELAPSE_PAYLOAD_MAX_BYTES`
    is refused before it is even parsed — **while that bound is unvalued
    (``None``, plan §8.1), no size refusal is performed here at all**, which
    is the declared unvalued state, not a permissive limit. Accepts either
    schema version (see :func:`deserialize_payload`).
    """
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise TimelapseIOError(f"cannot read {target}: {exc}") from exc
    if TIMELAPSE_PAYLOAD_MAX_BYTES is None:
        pass  # declared UNVALUED (plan §8.1) — no bound is configured, so no size
        # refusal is possible. NOT a permissive limit; T22 removes this arm.
    else:
        _require(
            len(text.encode("utf-8")) <= TIMELAPSE_PAYLOAD_MAX_BYTES,
            f"{target} exceeds TIMELAPSE_PAYLOAD_MAX_BYTES "
            f"({TIMELAPSE_PAYLOAD_MAX_BYTES})",
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TimelapseIOError(f"{target} is not valid JSON: {exc}") from exc
    return deserialize_payload(payload)
