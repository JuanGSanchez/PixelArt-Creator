# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
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

**Schema 3 — stable frame identity (Q-21, REQ-P9-DATA-005; DEP-12e; plan
§10.3), also additive.** ``TIMELAPSE_IDENTITY_SCHEMA_VERSION`` (``"3"``) is a
new wire version, not a reshaped ``"2"``: schema 2 has never shipped, but two
frame shapes under one version string is the exact misparse the version rules
exist to prevent. **Schema 2 becomes read-only legacy**: ``serialize_payload``
now writes **only** ``"3"`` and raises :class:`TimelapseIOError` if asked to
emit any other version — a build that could still *write* the identity-less
form could still *create* the population ``REQ-P9-DATA-005`` exists to stop
creating. A schema-2 file already on disk still **loads**, as a readable
record with every frame's ``frame_id`` set to ``None``; it never **plays**
(blocked by ``NO_IDENTITY``, ``REQ-P9-UI-019``(f)); it is never migrated,
upgraded, re-tagged, or repaired by inference (§0b.1). **Discrimination
between the three forms is by the ``schema_version`` string ALONE** — never
by sniffing for the presence of an ``"identity"`` key, because a truncated or
hand-edited file would then select whichever branch is more permissive and a
schema-3 file that lost its identities would be silently demoted to a
schema-2 read, which is Q-21's defect re-entering through the loader. At
``"3"``, every frame's ``"identity"`` and the root ``"recording_id"`` are
**required**; at ``"1"`` and ``"2"`` an ``"identity"``/``"recording_id"`` is
**rejected**. Each identity is checked to be a non-empty ``str``, at most
:data:`~pixelart_creator.logic.constants.TIMELAPSE_FRAME_ID_MAX_LEN`,
matching ``^[0-9a-f]{32}:[0-9]+$``, prefixed by the root ``recording_id``, and
**pairwise distinct** within the payload — any violation raises
:class:`TimelapseIdentityError`, a :class:`TimelapseIOError` subclass so
``ui/`` can discriminate **by type**, exactly as
:class:`TimelapsePayloadTooLargeError` does, while every existing
``pytest.raises(TimelapseIOError)`` still holds. **The opacity rule's one
stated exception**: this shape validation is untrusted-input checking under
Article VII, confined to this module, and it derives nothing — no order, no
position, no successor, no age.

Layering: ``data -> logic`` (imports ``logic.timelapse``, ``logic.content_hash``,
``logic.constants``) and ``data -> data`` (``TimelapseIOError`` extends
``project_io.ProjectIOError``; schema-2/3 support imports ``data.snapshot_store``
for ``BLOB_KEYS``, mirroring the shipped ``snapshot_store -> project_io`` edge);
never ``logic -> data``. Zero Qt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, Set, Union

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.data.snapshot_store import BLOB_KEYS
from pixelart_creator.logic.constants import (
    MAX_TIMELAPSE_FRAMES,
    TIMELAPSE_FRAME_ID_MAX_LEN,
    TIMELAPSE_PAYLOAD_MAX_BYTES,
)
from pixelart_creator.logic.content_hash import (
    canonical_json_bytes,
    content_hash,
    is_valid_hash,
)
from pixelart_creator.logic.timelapse import (
    SUPPORTED_SCHEMA_VERSIONS,
    TIMELAPSE_IDENTITY_SCHEMA_VERSION,
    TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
    TimelapseError,
    TimelapseFrame,
    TimelapseSession,
)

__all__ = [
    "TimelapseIOError",
    "TimelapsePayloadTooLargeError",
    "TimelapseIdentityError",
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

#: The shape an on-disk schema-3 frame identity must match (Article VII;
#: REQ-P9-DATA-005; plan §10.3): 32 lowercase hex chars (the
#: :data:`~pixelart_creator.logic.constants.TIMELAPSE_RECORDING_ID_BYTES`-byte
#: ``recording_id`` half), a ``":"`` separator, and a decimal ordinal.
_FRAME_ID_PATTERN = re.compile(r"^[0-9a-f]{32}:[0-9]+$")

FORMAT_NAME = "pixtimelapse"
FILE_SUFFIX = ".pixtimelapse"

#: The key a snapshot's stamped fingerprint is stored under (plan §2.1, §4.1).
_FINGERPRINT_KEY = "fingerprint"


class TimelapseIOError(ProjectIOError):
    """Raised when a timelapse session cannot be serialised or is malformed."""


class TimelapsePayloadTooLargeError(TimelapseIOError):
    """Raised when a schema-2 payload exceeds :data:`TIMELAPSE_PAYLOAD_MAX_BYTES`.

    A named subclass (not a message string) so ``ui/`` (T28) can distinguish
    an oversize refusal from a malformed/truncated payload **by type** rather
    than by parsing English (plan §8.4, amended 2026-08-18 F-7). Subclassing
    :class:`TimelapseIOError` keeps every existing
    ``pytest.raises(TimelapseIOError)`` assertion valid — an oversize refusal
    still is-a ``TimelapseIOError``. Raised by both
    :func:`serialize_payload` (record/save time) and
    :func:`load_session_payload` (open time). Never write or truncate on this
    path — the payload is refused whole (REQ-P9-DATA-004).
    """


class TimelapseIdentityError(TimelapseIOError):
    """Raised when a schema-3 frame identity is missing, malformed, or reused.

    A named subclass (Q-21, REQ-P9-DATA-005; plan §10.3), not a message
    string, so ``ui/`` can discriminate an identity violation from any other
    malformed-payload cause **by type**, exactly as
    :class:`TimelapsePayloadTooLargeError` does. Every existing
    ``pytest.raises(TimelapseIOError)`` assertion stays valid — an identity
    violation still is-a ``TimelapseIOError``. Covers: a missing, non-``str``,
    empty, or over-length identity; one that does not match
    ``^[0-9a-f]{32}:[0-9]+$``; one not prefixed by the payload's own root
    ``recording_id``; two frames sharing one identity; and an
    ``"identity"``/``"recording_id"`` field present where schema 1 or 2
    forbids it. Nothing is inferred, regenerated or renumbered to make a file
    load (``SC-D005-4``).
    """


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
    size = len(json.dumps(payload).encode("utf-8"))
    if size > TIMELAPSE_PAYLOAD_MAX_BYTES:
        raise TimelapsePayloadTooLargeError(
            f"payload is {size} bytes, exceeds TIMELAPSE_PAYLOAD_MAX_BYTES "
            f"({TIMELAPSE_PAYLOAD_MAX_BYTES})"
        )


def serialize_payload(
    session: TimelapseSession,
    snapshots: Dict[str, Dict[str, Any]],
    blobs: Dict[str, str],
) -> Dict[str, Any]:
    """Serialise an identity-bearing (schema-3) payload: frames + snapshots + blobs.

    **Writes only** ``schema_version == TIMELAPSE_IDENTITY_SCHEMA_VERSION``
    (Q-21, REQ-P9-DATA-005; plan §10.3): schema 2 is now read-only legacy, and
    a build that could still *emit* it could still *create* the
    identity-less population this requirement exists to stop creating.
    ``snapshots`` maps a snapshot id (a caller-chosen stable key, e.g. the
    content hash :func:`pixelart_creator.data.snapshot_store.snapshot_of`'s
    output would be keyed by) to a ``project_io.serialize``-shaped dict with
    blob strings already hoisted to content-hash references. Each is stamped
    here with its own ``"fingerprint"`` — ``content_hash(canonical_json_bytes(...))``
    of the body, computed **before** the stamp is added. Never truncates: the
    whole payload is refused, whole, when it exceeds
    :data:`TIMELAPSE_PAYLOAD_MAX_BYTES` (plan §9.2).

    Raises:
        TimelapseIOError: If ``session`` is not a :class:`TimelapseSession`,
            ``session.schema_version`` is not
            :data:`~pixelart_creator.logic.timelapse.TIMELAPSE_IDENTITY_SCHEMA_VERSION`,
            ``session.recording_id`` is not a non-empty ``str``, a frame
            carries no ``frame_id``, a frame's ``snapshot_id`` has no entry
            in ``snapshots``, or a snapshot body is not a JSON object.
        TimelapsePayloadTooLargeError: If the resulting payload exceeds
            :data:`TIMELAPSE_PAYLOAD_MAX_BYTES` — a
            :class:`TimelapseIOError` subclass, distinguishable by type
            (plan §8.4, T8 amendment).
    """
    if not isinstance(session, TimelapseSession):
        raise TimelapseIOError(f"expected a TimelapseSession, got {session!r}")
    _require(
        session.schema_version == TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        "serialize_payload writes only schema_version "
        f"{TIMELAPSE_IDENTITY_SCHEMA_VERSION!r} (identity-bearing); got "
        f"{session.schema_version!r} — schema "
        f"{TIMELAPSE_PAYLOAD_SCHEMA_VERSION!r} is read-only legacy and is "
        "never written again (Q-21, REQ-P9-DATA-005)",
    )
    _require(
        isinstance(session.recording_id, str) and bool(session.recording_id),
        "an identity-bearing session must carry a non-empty recording_id",
    )
    frames_out = []
    for frame in session.frames:
        _require(
            frame.frame_id is not None,
            f"frame {frame.index} carries no identity; every frame in a "
            f"schema-{TIMELAPSE_IDENTITY_SCHEMA_VERSION} session requires one",
        )
        entry: Dict[str, Any] = {
            "index": frame.index,
            "command_id": frame.command_id,
            "identity": frame.frame_id,
        }
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
        "recording_id": session.recording_id,
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
    """Reconstruct a :class:`TimelapsePayload` from a parsed payload manifest dict.

    Every field is type/bounds/version-checked; each snapshot's stamped
    fingerprint is recomputed and compared, and every blob-hash string it
    references (:data:`BLOB_KEYS`) must resolve in ``blobs``. Frames are
    checked **in recorded order**, so the first mismatch or missing reference
    encountered names the first offending frame. A malformed, truncated, or
    fingerprint-mismatched payload raises :class:`TimelapseIOError` and nothing
    is partially returned. Accepts schema ``"1"``, ``"2"`` or ``"3"`` — a
    schema-1 payload (no ``"snapshots"``/``"blobs"`` keys) yields empty
    tables; a schema-2 payload yields frames with ``frame_id=None`` (it loads
    as a readable record and never plays, ``NO_IDENTITY``); a schema-3
    payload's frame identities are validated below.

    **Discrimination is by the ``schema_version`` string ALONE** (Q-21, plan
    §10.3) — this function never infers the form from which optional keys
    happen to be present, because a truncated or hand-edited schema-3 file
    that lost its ``"identity"`` fields would then be silently read as
    schema 2, which is the defect Q-21 exists to close.

    Raises:
        TimelapseIOError: On any structural, bounds, version, fingerprint or
            blob-completeness failure.
        TimelapseIdentityError: If a schema-3 frame identity (or the root
            ``recording_id``) is missing, malformed, or reused, or a
            schema-1/2 payload carries an ``"identity"``/``"recording_id"``
            it must not.
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
    is_identity_bearing = schema_version == TIMELAPSE_IDENTITY_SCHEMA_VERSION

    recording_id: Any = None
    if is_identity_bearing:
        recording_id = payload.get("recording_id")
        if not (isinstance(recording_id, str) and recording_id):
            raise TimelapseIdentityError(
                f"a schema-{TIMELAPSE_IDENTITY_SCHEMA_VERSION} payload must "
                "carry a non-empty root recording_id"
            )
    else:
        if "recording_id" in payload:
            raise TimelapseIdentityError(
                f"schema_version {schema_version!r} must not carry a "
                f"recording_id (only schema {TIMELAPSE_IDENTITY_SCHEMA_VERSION!r} "
                "does)"
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
    seen_identities: Set[str] = set()
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
        identity_raw = entry.get("identity")
        if is_identity_bearing:
            if not (isinstance(identity_raw, str) and identity_raw):
                raise TimelapseIdentityError(
                    f"frame {index} is missing its identity (required at "
                    f"schema {TIMELAPSE_IDENTITY_SCHEMA_VERSION!r})"
                )
            if len(identity_raw) > TIMELAPSE_FRAME_ID_MAX_LEN:
                raise TimelapseIdentityError(
                    f"frame {index} identity exceeds TIMELAPSE_FRAME_ID_MAX_LEN "
                    f"({TIMELAPSE_FRAME_ID_MAX_LEN})"
                )
            if not _FRAME_ID_PATTERN.match(identity_raw) or not identity_raw.startswith(
                f"{recording_id}:"
            ):
                raise TimelapseIdentityError(
                    f"frame {index} identity {identity_raw!r} is malformed or "
                    f"does not belong to recording {recording_id!r}"
                )
            if identity_raw in seen_identities:
                raise TimelapseIdentityError(
                    f"frame {index} identity {identity_raw!r} duplicates an "
                    "earlier frame in this payload"
                )
            seen_identities.add(identity_raw)
        elif identity_raw is not None:
            raise TimelapseIdentityError(
                f"frame {index} carries an identity but schema_version "
                f"{schema_version!r} does not support one"
            )
        try:
            frames.append(
                TimelapseFrame(
                    index=index,
                    command_id=command_id,
                    snapshot_id=snapshot_id,
                    frame_id=identity_raw,
                )
            )
        except TimelapseError as exc:
            raise TimelapseIOError(f"invalid timelapse frame {index}: {exc}") from exc
    try:
        session = TimelapseSession(
            schema_version=schema_version,
            frames=tuple(frames),
            recording_id=recording_id,
        )
    except TimelapseError as exc:
        raise TimelapseIOError(f"invalid timelapse session: {exc}") from exc
    return TimelapsePayload(session=session, snapshots=snapshots, blobs=blobs)


def load_session_payload(path: Union[str, Path]) -> TimelapsePayload:
    """Read and validate a ``.pixtimelapse`` manifest into a :class:`TimelapsePayload`.

    A file whose size on disk already exceeds :data:`TIMELAPSE_PAYLOAD_MAX_BYTES`
    is refused, as :class:`TimelapsePayloadTooLargeError`, before it is even
    parsed (plan §9.2). Accepts either schema version (see
    :func:`deserialize_payload`).
    """
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise TimelapseIOError(f"cannot read {target}: {exc}") from exc
    text_size = len(text.encode("utf-8"))
    if text_size > TIMELAPSE_PAYLOAD_MAX_BYTES:
        raise TimelapsePayloadTooLargeError(
            f"{target} exceeds TIMELAPSE_PAYLOAD_MAX_BYTES "
            f"({TIMELAPSE_PAYLOAD_MAX_BYTES})"
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TimelapseIOError(f"{target} is not valid JSON: {exc}") from exc
    return deserialize_payload(payload)
