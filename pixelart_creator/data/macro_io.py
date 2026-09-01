# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Read/write the ``.pixmacro`` macro format + plugin manifests (zero Qt, S11).

Defensive, ``eval``-free (de)serialisation reusing the ``data.project_io`` IO-3
posture (REQ-P8-LOGIC-007; ADR-0022 §1): the on-disk format is plain JSON; **every
field is type/bounds/version-checked on load**, a malformed/out-of-bounds/unknown
-version document raises :class:`MacroIOError`, and content is **never** passed to
``eval``/``exec``/``compile``. Paths are built with :mod:`pathlib` for portability
(``path_portability_check``).

Round-trip identity (the acceptance gate, SC-L007-1): because a DSL
:class:`~pixelart_creator.logic.macro.Op`'s ``params`` are JSON-native by
construction (dict of str→ int/float/str/bool/None/list), ``save_macro`` then
``load_macro`` yields an **equal** :class:`~pixelart_creator.logic.macro.Macro`,
which therefore replays to the identical result.

Layering: ``data → logic`` (imports ``logic.macro`` + ``logic.plugins``) and
``data → data`` (``MacroIOError`` extends ``project_io.ProjectIOError``); never
``logic → data``. Zero Qt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.constants import MAX_MACRO_STEPS
from pixelart_creator.logic.macro import (
    MIN_APP_VERSION,
    OP_API_VERSION,
    SUPPORTED_API_VERSIONS,
    SUPPORTED_SCHEMA_VERSIONS,
    Macro,
    Op,
)
from pixelart_creator.logic.plugins import PluginManifest, validate_manifest

__all__ = [
    "MacroIOError",
    "FORMAT_NAME",
    "FILE_SUFFIX",
    "save_macro",
    "load_macro",
    "load_manifest",
]

FORMAT_NAME = "pixmacro"
FILE_SUFFIX = ".pixmacro"

#: JSON-native scalar types permitted in a serialised op's params.
_JSON_SCALAR = (int, float, str, bool, type(None))


class MacroIOError(ProjectIOError):
    """Raised when a macro/manifest cannot be serialised or is malformed on load."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MacroIOError(message)


def _is_json_native(value: Any) -> bool:
    """Whether ``value`` is JSON-native (guards round-trip identity + no surprises)."""
    if isinstance(value, _JSON_SCALAR):
        return True
    if isinstance(value, list):
        return all(_is_json_native(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_json_native(v) for k, v in value.items())
    return False


# --------------------------------------------------------------------------- #
# Serialisation                                                               #
# --------------------------------------------------------------------------- #


def _serialise_op(op: Op) -> Dict[str, Any]:
    if not isinstance(op.name, str) or not op.name:
        raise MacroIOError(f"op name must be a non-empty str, got {op.name!r}")
    if not isinstance(op.params, dict):
        raise MacroIOError("op params must be a dict")
    if not _is_json_native(op.params):
        raise MacroIOError(f"op {op.name!r} has non-JSON-native params")
    if op.seed is not None and (
        not isinstance(op.seed, int) or isinstance(op.seed, bool)
    ):
        raise MacroIOError(f"op seed must be an int or null, got {op.seed!r}")
    return {
        "op": op.name,
        "params": dict(op.params),
        "seed": op.seed,
        "api_version": OP_API_VERSION,
    }


def serialize(macro: Macro) -> Dict[str, Any]:
    """Serialise a :class:`Macro` to a plain JSON-ready dict (``.pixmacro`` schema)."""
    if not isinstance(macro, Macro):
        raise MacroIOError(f"expected a Macro, got {macro!r}")
    if len(macro.ops) > MAX_MACRO_STEPS:
        raise MacroIOError(f"macro exceeds MAX_MACRO_STEPS ({MAX_MACRO_STEPS})")
    return {
        "format": FORMAT_NAME,
        "schema_version": macro.schema_version,
        "min_app_version": macro.min_app_version,
        "ops": [_serialise_op(op) for op in macro.ops],
    }


def save_macro(macro: Macro, path: Union[str, Path]) -> Path:
    """Serialise ``macro`` and write it to ``path`` (adds ``.pixmacro``).

    Raises:
        MacroIOError: If the macro is malformed / not JSON-serialisable.
    """
    target = Path(path)
    if target.suffix != FILE_SUFFIX:
        target = target.with_suffix(FILE_SUFFIX)
    try:
        payload = json.dumps(serialize(macro))
    except (TypeError, ValueError) as exc:
        raise MacroIOError(f"cannot serialise macro: {exc}") from exc
    target.write_text(payload, encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Deserialisation (defensive, eval-free)                                      #
# --------------------------------------------------------------------------- #


def _parse_op(data: Any) -> Op:
    _require(isinstance(data, dict), "each op must be a JSON object")
    name = data.get("op")
    _require(isinstance(name, str) and bool(name), "op 'op' must be a non-empty str")
    params = data.get("params", {})
    _require(isinstance(params, dict), "op 'params' must be a JSON object")
    _require(
        all(isinstance(k, str) for k in params) and _is_json_native(params),
        "op 'params' must be JSON-native with string keys",
    )
    seed = data.get("seed")
    _require(
        seed is None or (isinstance(seed, int) and not isinstance(seed, bool)),
        "op 'seed' must be an int or null",
    )
    api_version = data.get("api_version", OP_API_VERSION)
    _require(isinstance(api_version, str), "op 'api_version' must be a str")
    _require(
        api_version in SUPPORTED_API_VERSIONS,
        f"unsupported op api_version {api_version!r}; "
        f"supported: {SUPPORTED_API_VERSIONS}",
    )
    return Op(name=name, params=dict(params), seed=seed)


def deserialize(payload: Dict[str, Any]) -> Macro:
    """Reconstruct a :class:`Macro` from a parsed ``.pixmacro`` dict (defensive).

    Raises:
        MacroIOError: If any field is missing, mistyped, out of bounds, or of an
            unknown/unsupported version. **Never** ``eval``/``exec``.
    """
    _require(isinstance(payload, dict), "macro root must be a JSON object")
    _require(payload.get("format") == FORMAT_NAME, "not a pixmacro file")
    schema_version = payload.get("schema_version")
    if (
        not isinstance(schema_version, str)
        or schema_version not in SUPPORTED_SCHEMA_VERSIONS
    ):
        raise MacroIOError(
            f"unsupported schema_version {schema_version!r}; "
            f"supported: {SUPPORTED_SCHEMA_VERSIONS}"
        )
    min_app_version = payload.get("min_app_version", MIN_APP_VERSION)
    if not isinstance(min_app_version, str):
        raise MacroIOError("min_app_version must be a str")
    ops_raw = payload.get("ops")
    if not isinstance(ops_raw, list):
        raise MacroIOError("macro 'ops' must be a list")
    if len(ops_raw) > MAX_MACRO_STEPS:
        raise MacroIOError(f"macro exceeds MAX_MACRO_STEPS ({MAX_MACRO_STEPS})")
    ops = tuple(_parse_op(entry) for entry in ops_raw)
    return Macro(
        schema_version=schema_version,
        min_app_version=min_app_version,
        ops=ops,
    )


def load_macro(path: Union[str, Path]) -> Macro:
    """Read and validate a ``.pixmacro`` file into a :class:`Macro` (eval-free).

    Raises:
        MacroIOError: If the file cannot be read, is not valid JSON, or is
            malformed / of an unsupported version.
    """
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise MacroIOError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MacroIOError(f"{target} is not valid JSON: {exc}") from exc
    return deserialize(payload)


def load_manifest(path: Union[str, Path]) -> PluginManifest:
    """Read and validate a plugin manifest JSON into a :class:`PluginManifest`.

    Same defensive posture as :func:`load_macro`: parse JSON, hand to the
    ``logic.plugins`` allow-list validator; malformed/unsupported → error, never
    ``eval``/``exec``.

    Raises:
        MacroIOError: If the file cannot be read or is not valid JSON.
        PluginError: If the manifest is malformed/unsupported (from
            ``logic.plugins.validate_manifest``).
    """
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise MacroIOError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MacroIOError(f"{target} is not valid JSON: {exc}") from exc
    return validate_manifest(payload)
