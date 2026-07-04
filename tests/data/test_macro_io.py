"""Tests for pixelart_creator.data.macro_io — defensive, eval-free .pixmacro I/O.

Security invariant #5 (REQ-P8-LOGIC-007, SC-L007-1): valid ``.pixmacro`` save→load
is round-trip IDENTICAL (so it replays to the identical result); malformed /
oversized / unknown-schema-version inputs raise a typed
``MacroIOError``/``PluginError`` — never crash, never ``eval``. ``MacroIOError``
extends the shipped ``ProjectIOError`` (IO-3 posture).
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data import macro_io
from pixelart_creator.data.macro_io import (
    FILE_SUFFIX,
    FORMAT_NAME,
    MacroIOError,
    deserialize,
    load_macro,
    load_manifest,
    save_macro,
    serialize,
)
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.macro import (
    MACRO_SCHEMA_VERSION,
    MIN_APP_VERSION,
    OP_API_VERSION,
    Macro,
    Op,
    record,
)
from pixelart_creator.logic.plugins import PluginError, PluginManifest


def _macro() -> Macro:
    return record(
        [
            Op("procgen", {"algorithm": "value_noise", "frequency": 3}, seed=42),
            Op(
                "batch_recolour",
                {"color_map": [[[0, 0, 0, 0], [255, 0, 0, 255]]], "frame_index": 0},
            ),
            Op("procgen", {"algorithm": "opensimplex"}, seed=None),
        ]
    )


# --------------------------------------------------------------------------- #
# Round-trip identity — SC-L007-1                                              #
# --------------------------------------------------------------------------- #


def test_macro_io_error_extends_project_io_error():
    assert issubclass(MacroIOError, ProjectIOError)


def test_save_load_round_trip_identical(tmp_path):
    macro = _macro()
    path = save_macro(macro, tmp_path / "job")
    assert path.suffix == FILE_SUFFIX
    loaded = load_macro(path)
    assert loaded == macro  # equal Macro → replays identically


def test_save_adds_suffix(tmp_path):
    path = save_macro(_macro(), tmp_path / "noext")
    assert path.name == "noext.pixmacro"


def test_serialize_deserialize_round_trip():
    macro = _macro()
    payload = serialize(macro)
    assert payload["format"] == FORMAT_NAME
    assert payload["schema_version"] == MACRO_SCHEMA_VERSION
    assert payload["ops"][0]["api_version"] == OP_API_VERSION
    assert deserialize(payload) == macro


def test_params_preserved_as_json_native(tmp_path):
    # No tuple/int-key drift: nested lists survive as lists.
    macro = record([Op("procgen", {"knobs": [[1, 2], [3, 4]]}, seed=1)])
    loaded = load_macro(save_macro(macro, tmp_path / "j"))
    assert loaded.ops[0].params == {"knobs": [[1, 2], [3, 4]]}


# --------------------------------------------------------------------------- #
# Serialisation guards                                                         #
# --------------------------------------------------------------------------- #


def test_serialize_rejects_non_macro():
    with pytest.raises(MacroIOError):
        serialize(object())  # type: ignore[arg-type]


def test_serialize_rejects_oversized(monkeypatch):
    monkeypatch.setattr(macro_io, "MAX_MACRO_STEPS", 1)
    macro = Macro(MACRO_SCHEMA_VERSION, MIN_APP_VERSION, (Op("x"), Op("y")))
    with pytest.raises(MacroIOError):
        serialize(macro)


def test_serialize_rejects_empty_op_name():
    macro = Macro(MACRO_SCHEMA_VERSION, MIN_APP_VERSION, (Op(""),))
    with pytest.raises(MacroIOError):
        serialize(macro)


def test_serialize_rejects_non_dict_params():
    macro = Macro(MACRO_SCHEMA_VERSION, MIN_APP_VERSION, (Op("x", params=[1]),))
    with pytest.raises(MacroIOError):
        serialize(macro)


def test_serialize_rejects_non_json_native_params():
    macro = Macro(MACRO_SCHEMA_VERSION, MIN_APP_VERSION, (Op("x", {"k": object()}),))
    with pytest.raises(MacroIOError):
        serialize(macro)


def test_serialize_rejects_bad_seed():
    macro = Macro(MACRO_SCHEMA_VERSION, MIN_APP_VERSION, (Op("x", seed=True),))
    with pytest.raises(MacroIOError):
        serialize(macro)


# --------------------------------------------------------------------------- #
# Defensive deserialisation — malformed / oversized / bad version              #
# --------------------------------------------------------------------------- #


def test_load_rejects_non_dict_root():
    with pytest.raises(MacroIOError):
        deserialize([1, 2, 3])  # type: ignore[arg-type]


def test_load_rejects_wrong_format():
    with pytest.raises(MacroIOError):
        deserialize({"format": "not-pixmacro"})


def test_load_rejects_unknown_schema_version():
    with pytest.raises(MacroIOError):
        deserialize({"format": FORMAT_NAME, "schema_version": "999", "ops": []})


def test_load_rejects_non_string_schema_version():
    with pytest.raises(MacroIOError):
        deserialize({"format": FORMAT_NAME, "schema_version": 1, "ops": []})


def test_load_rejects_non_string_min_app_version():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "min_app_version": 1,
                "ops": [],
            }
        )


def test_load_rejects_non_list_ops():
    with pytest.raises(MacroIOError):
        deserialize(
            {"format": FORMAT_NAME, "schema_version": MACRO_SCHEMA_VERSION, "ops": {}}
        )


def test_load_rejects_oversized_ops(monkeypatch):
    monkeypatch.setattr(macro_io, "MAX_MACRO_STEPS", 1)
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "a"}, {"op": "b"}],
            }
        )


def test_load_rejects_op_not_object():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": ["not-an-object"],
            }
        )


def test_load_rejects_empty_op_name():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": ""}],
            }
        )


def test_load_rejects_non_dict_op_params():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "x", "params": [1, 2]}],
            }
        )


def test_load_rejects_non_json_native_op_params():
    # A params value that is not JSON-native (a set) — json.loads would never
    # produce this, but a hostile in-process caller of deserialize might, so the
    # defensive check must reject it rather than pass it through.
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "x", "params": {"k": {1, 2}}}],
            }
        )


def test_load_rejects_non_string_param_keys():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "x", "params": {1: "v"}}],
            }
        )


def test_load_rejects_bad_seed():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "x", "seed": "not-int"}],
            }
        )


def test_load_rejects_bool_seed():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "x", "seed": True}],
            }
        )


def test_load_rejects_unsupported_op_api_version():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "x", "api_version": "999"}],
            }
        )


def test_load_rejects_non_string_op_api_version():
    with pytest.raises(MacroIOError):
        deserialize(
            {
                "format": FORMAT_NAME,
                "schema_version": MACRO_SCHEMA_VERSION,
                "ops": [{"op": "x", "api_version": 1}],
            }
        )


# --------------------------------------------------------------------------- #
# load_macro file-level errors                                                 #
# --------------------------------------------------------------------------- #


def test_load_macro_missing_file(tmp_path):
    with pytest.raises(MacroIOError):
        load_macro(tmp_path / "nope.pixmacro")


def test_load_macro_invalid_json(tmp_path):
    path = tmp_path / "bad.pixmacro"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(MacroIOError):
        load_macro(path)


# --------------------------------------------------------------------------- #
# load_manifest — defensive, delegates to the plugins allow-list               #
# --------------------------------------------------------------------------- #


def test_load_manifest_valid(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(
        json.dumps(
            {
                "name": "acme",
                "version": "1.0.0",
                "api_version": "1",
                "capabilities": ["read_document"],
            }
        ),
        encoding="utf-8",
    )
    manifest = load_manifest(path)
    assert isinstance(manifest, PluginManifest)
    assert manifest.name == "acme"


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(MacroIOError):
        load_manifest(tmp_path / "nope.json")


def test_load_manifest_invalid_json(tmp_path):
    path = tmp_path / "m.json"
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(MacroIOError):
        load_manifest(path)


def test_load_manifest_malformed_raises_plugin_error(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(
        json.dumps({"name": "", "version": "1", "api_version": "1"}), "utf-8"
    )
    with pytest.raises(PluginError):
        load_manifest(path)
