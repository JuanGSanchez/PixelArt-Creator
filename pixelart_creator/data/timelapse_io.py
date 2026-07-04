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

Layering: ``data -> logic`` (imports ``logic.timelapse``) and ``data -> data``
(``TimelapseIOError`` extends ``project_io.ProjectIOError``); never ``logic -> data``.
Zero Qt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.constants import MAX_TIMELAPSE_FRAMES
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
]

FORMAT_NAME = "pixtimelapse"
FILE_SUFFIX = ".pixtimelapse"


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
