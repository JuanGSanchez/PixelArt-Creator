"""Tests for pixelart_creator.logic.tool_catalog — the safe tool-catalog facade.

Slice 14A (Phase-14 AI assistant). This is the *logic-layer* (zero Qt) proof that
the provider-neutral tool-catalog + JSON-schema introspection facade over the shipped
Phase-8 DSL registry (``logic.scripting``) is:

* **REQ-P14-LOGIC-001 / SC-L001-*** — a read-only enumeration of the allow-listed
  registry: one :class:`~pixelart_creator.logic.tool_catalog.ToolDescriptor` per
  registered op, tracking consent-gated namespaced plugin ops with no second list.
* **REQ-P14-LOGIC-002 / SC-L002-1** — each op is projected to a FAITHFUL,
  **non-widening** JSON-schema: the projection never permits an argument the shipped
  ``ParamSchema.validate`` would reject (property-tested with Hypothesis — the
  authoritative gate is ``validate``/``dispatch``, the schema is advisory).
* **REQ-P14-LOGIC-003 / SC-L003-*** — a tool-call maps 1:1 to an allow-listed
  :class:`~pixelart_creator.logic.macro.Op` executed **only** through the trusted
  :func:`~pixelart_creator.logic.scripting.dispatch`; an unknown op or invalid params
  raises :class:`~pixelart_creator.logic.scripting.ScriptError` and leaves the document
  **byte-identical** (validate-then-apply atomicity), while a valid call applies as one
  undoable group.
* **REQ-P14-LOGIC-008 / SC-L008-1** — a static source audit asserts there is no
  ``eval``/``exec``/``compile``/``__import__`` anywhere in the facade (Article VII by
  construction — model output is data mapped onto the allow-listed registry).

No Qt, no product-code changes. Property-based tests use the deterministic ``ci``
Hypothesis profile registered in ``tests/logic/conftest.py``.
"""

from __future__ import annotations

import ast
import inspect

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import scripting, tool_catalog
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command, GroupCommand
from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.logic.scripting import ParamSchema, ScriptError
from pixelart_creator.logic.tool_catalog import (
    SEED_PROPERTY,
    ToolCall,
    ToolCatalogError,
    ToolDescriptor,
    build_tool_catalog,
    execute_tool_call,
    param_schema_to_json_schema,
    to_op,
)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def _rgba_doc(width: int = 4, height: int = 4) -> Document:
    return Document(width, height, palette=Palette([RED, BLUE, (0, 255, 0, 255)]))


def _indexed_doc(width: int = 4, height: int = 4) -> Document:
    return Document(width, height, mode=ColorMode.INDEXED, palette=Palette([RED, BLUE]))


def _leaf_buffer(doc: Document):
    return iter_layers(doc.frames[0].layers)[0].buffer


def _doc_bytes(doc: Document) -> bytes:
    """A whole-document byte fingerprint via ``buffer.data.tobytes()``.

    Concatenates every leaf buffer of every frame so an atomicity assertion detects
    *any* partial pixel mutation (SC-L003-1/-2 — "document byte/state-identical").
    """
    chunks = [
        np.ascontiguousarray(layer.buffer.data).tobytes()
        for frame in doc.frames
        for layer in iter_layers(frame.layers)
    ]
    return b"".join(chunks)


# --------------------------------------------------------------------------- #
# SC-L001 — build_tool_catalog enumerates the allow-listed registry read-only  #
# --------------------------------------------------------------------------- #


def test_catalog_has_one_descriptor_per_registered_op():
    # SC-L001-1: one ToolDescriptor per registered op, in the registry's sorted order.
    catalog = build_tool_catalog()
    assert all(isinstance(d, ToolDescriptor) for d in catalog)
    names = [d.name for d in catalog]
    assert names == list(scripting.registered_ops())
    assert names == sorted(names)
    # Built-ins are present; there is no descriptor for a non-registered op.
    assert scripting.OP_BATCH_RECOLOUR in names
    assert scripting.OP_PROCGEN in names
    assert "delete_everything" not in names


def test_catalog_descriptor_has_name_description_and_json_schema_object():
    # SC-L001-1: each descriptor carries a name + human description + a JSON-schema
    # object dict for its parameters.
    catalog = build_tool_catalog()
    for descriptor in catalog:
        assert isinstance(descriptor.name, str) and descriptor.name
        assert isinstance(descriptor.description, str) and descriptor.description
        params = descriptor.parameters
        assert params["type"] == "object"
        assert isinstance(params["properties"], dict)
        assert isinstance(params["required"], list)
        assert isinstance(params["additionalProperties"], bool)


def test_catalog_procgen_schema_shape():
    # SC-L002-1: a representative op ("procgen") projects its ParamSchema faithfully:
    # required "algorithm" (string), the required seed (requires_seed), and the
    # allow_extra posture -> additionalProperties True.
    catalog = {d.name: d for d in build_tool_catalog()}
    procgen = catalog[scripting.OP_PROCGEN]
    params = procgen.parameters
    assert params["properties"]["algorithm"] == {"type": "string"}
    assert "algorithm" in params["required"]
    assert SEED_PROPERTY in params["required"]  # requires_seed -> seed required
    assert params["properties"][SEED_PROPERTY]["type"] == "integer"
    assert params["additionalProperties"] is True  # allow_extra
    # Description comes from the table, not the generic fallback.
    assert "generic" not in procgen.description.lower()
    assert "Registered pixel-art DSL operation" not in procgen.description


def test_catalog_batch_recolour_schema_shape():
    # SC-L002-1: batch_recolour has no required fields, does NOT require a seed, and
    # is strict (allow_extra False -> additionalProperties False).
    catalog = {d.name: d for d in build_tool_catalog()}
    batch = catalog[scripting.OP_BATCH_RECOLOUR]
    params = batch.parameters
    assert params["properties"]["targets"] == {"type": "array"}
    assert params["properties"]["frame_index"] == {"type": "integer"}
    assert params["properties"]["index_map"] == {"type": "array"}
    assert params["properties"]["color_map"] == {"type": "array"}
    assert params["required"] == []  # nothing required, seed not required
    assert SEED_PROPERTY not in params["required"]
    assert params["additionalProperties"] is False


def test_catalog_tracks_registered_plugin_op(registry_guard):
    # SC-L001-2: a consent-gated namespaced op appears with NO separate list; the
    # facade adds no new executable op / registration path (it reads the registry).
    def _noop_factory(document, params, seed):
        return GroupCommand([], label="noop")

    before = {d.name for d in build_tool_catalog()}
    assert "myplugin.stipple" not in before

    registry_guard.register_command("myplugin.stipple", _noop_factory, ParamSchema())
    after = build_tool_catalog()
    after_names = {d.name for d in after}
    assert "myplugin.stipple" in after_names
    assert after_names == before | {"myplugin.stipple"}

    plugin_descriptor = next(d for d in after if d.name == "myplugin.stipple")
    # No table entry -> the generic fallback description; still a valid JSON-schema.
    assert "myplugin.stipple" in plugin_descriptor.description
    assert plugin_descriptor.parameters["type"] == "object"


def test_catalog_reflects_unregistration(registry_guard):
    # SC-L001-1/-2: unregistering an op removes its descriptor — the catalog never
    # drifts from the live allow-list.
    def _noop_factory(document, params, seed):
        return GroupCommand([], label="noop")

    registry_guard.register_command("myplugin.temp", _noop_factory, ParamSchema())
    assert "myplugin.temp" in {d.name for d in build_tool_catalog()}
    registry_guard.unregister_command("myplugin.temp")
    assert "myplugin.temp" not in {d.name for d in build_tool_catalog()}


# --------------------------------------------------------------------------- #
# param_schema_to_json_schema — direct projection assertions (SC-L002-1)       #
# --------------------------------------------------------------------------- #


def test_projection_required_and_additional_properties_match_paramschema():
    # SC-L002-1 minimum: required fields match verbatim and additionalProperties
    # mirrors allow_extra (additionalProperties == allow_extra: allow_extra False =>
    # strict/no-extra, matching validate's "unknown param" rejection).
    schema = ParamSchema(
        fields={"a": str, "b": int}, required=("a",), allow_extra=False
    )
    projected = param_schema_to_json_schema(schema)
    assert projected["required"] == ["a"]
    assert projected["additionalProperties"] is False

    open_schema = ParamSchema(fields={"a": str}, allow_extra=True)
    assert param_schema_to_json_schema(open_schema)["additionalProperties"] is True


def test_projection_seed_property_presence_when_requires_seed():
    # SC-L002-1: the routed SEED_PROPERTY is always a typed integer property; it is
    # in `required` iff requires_seed.
    no_seed = param_schema_to_json_schema(ParamSchema(requires_seed=False))
    assert no_seed["properties"][SEED_PROPERTY]["type"] == "integer"
    assert SEED_PROPERTY not in no_seed["required"]

    seeded = param_schema_to_json_schema(ParamSchema(requires_seed=True))
    assert SEED_PROPERTY in seeded["required"]


def test_projection_bool_int_type_split():
    # SC-L002-1: the frozen type map keeps bool ("boolean") and int ("integer")
    # DISTINCT, mirroring ParamSchema.validate's explicit bad_bool rejection.
    projected = param_schema_to_json_schema(
        ParamSchema(fields={"flag": bool, "count": int})
    )
    assert projected["properties"]["flag"] == {"type": "boolean"}
    assert projected["properties"]["count"] == {"type": "integer"}


def test_projection_type_union_becomes_type_array():
    # A tuple union field projects to a JSON-schema type ARRAY (_project_type branch).
    projected = param_schema_to_json_schema(ParamSchema(fields={"x": (int, float)}))
    assert projected["properties"]["x"] == {"type": ["integer", "number"]}


def test_projection_all_scalar_types_mapped():
    # Exercise every entry of the frozen Python-type -> JSON-schema-type map.
    schema = ParamSchema(
        fields={
            "s": str,
            "i": int,
            "f": float,
            "b": bool,
            "arr": list,
            "obj": dict,
            "nul": type(None),
        }
    )
    props = param_schema_to_json_schema(schema)["properties"]
    assert props["s"] == {"type": "string"}
    assert props["i"] == {"type": "integer"}
    assert props["f"] == {"type": "number"}
    assert props["b"] == {"type": "boolean"}
    assert props["arr"] == {"type": "array"}
    assert props["obj"] == {"type": "object"}
    assert props["nul"] == {"type": "null"}


def test_projection_fails_loud_on_unmappable_type():
    # ToolCatalogError build-time fail-loud (non-widening guard): a field type with no
    # JSON-schema mapping must NOT silently emit an over-permissive schema.
    with pytest.raises(ToolCatalogError):
        param_schema_to_json_schema(ParamSchema(fields={"x": bytes}))


def test_build_catalog_fails_loud_on_unmappable_registered_op(registry_guard):
    # The fail-loud propagates through build_tool_catalog for a registered op whose
    # schema cannot be projected.
    def _noop_factory(document, params, seed):
        return GroupCommand([], label="noop")

    registry_guard.register_command(
        "test.unprojectable", _noop_factory, ParamSchema(fields={"x": bytes})
    )
    with pytest.raises(ToolCatalogError):
        build_tool_catalog()


def test_registered_schema_helper_raises_toolcatalogerror_on_miss():
    # The private introspection seam re-raises a registry miss as ToolCatalogError
    # (fail-loud consistency), not a raw ScriptError.
    with pytest.raises(ToolCatalogError):
        tool_catalog._registered_schema("definitely.not.registered")


# --------------------------------------------------------------------------- #
# SC-L002-1 — NON-WIDENING property: schema never accepts what validate rejects #
# --------------------------------------------------------------------------- #

# JSON-native value strategies keyed by the exact Python type the projection maps.
# Arguments arrive as JSON, so every generated value is JSON-native — the domain the
# projected schema actually describes.
_JSON_VALUE = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=8),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(st.text(max_size=6), children, max_size=3),
    ),
    max_leaves=5,
)

_STRATEGY_BY_TYPE = {
    str: st.text(max_size=8),
    int: st.integers(),
    float: st.floats(allow_nan=False, allow_infinity=False),
    bool: st.booleans(),
    list: st.lists(_JSON_VALUE, max_size=3),
    dict: st.dictionaries(st.text(max_size=6), _JSON_VALUE, max_size=3),
}

# Schemas the projection must never widen: both shipped built-ins plus a synthetic
# schema exercising a required field, a bool/int split, a type union, extras, seed.
_PROJECTION_SCHEMAS = [
    scripting.schema_for(scripting.OP_BATCH_RECOLOUR),
    scripting.schema_for(scripting.OP_PROCGEN),
    ParamSchema(
        fields={
            "i": int,
            "b": bool,
            "num": (int, float),
            "s": str,
            "arr": list,
            "obj": dict,
        },
        required=("i",),
        allow_extra=True,
        requires_seed=True,
    ),
]


def _value_for_type(expected):
    """A strategy producing a JSON-native value matching a ParamSchema field type."""
    members = expected if isinstance(expected, tuple) else (expected,)
    return st.one_of(*[_STRATEGY_BY_TYPE[member] for member in members])


@st.composite
def _schema_conforming_arguments(draw, schema: ParamSchema):
    """Draw a ToolCall.arguments dict that CONFORMS to ``schema``'s projected schema.

    Every declared field is included when required (else optionally); values match
    the field's projected type; extras are only added when allow_extra; the routed
    seed is an int, present when requires_seed (else optional).
    """
    args: dict = {}
    for name, expected in schema.fields.items():
        if name in schema.required or draw(st.booleans()):
            args[name] = draw(_value_for_type(expected))
    if schema.allow_extra:
        extra_key = st.text(max_size=6).filter(
            lambda k: k not in schema.fields and k != SEED_PROPERTY
        )
        args.update(draw(st.dictionaries(extra_key, _JSON_VALUE, max_size=3)))
    if schema.requires_seed or draw(st.booleans()):
        args[SEED_PROPERTY] = draw(st.integers())
    return args


def _json_type_of(value) -> str:
    """The JSON-schema type name of a JSON-native value (bool/int kept distinct)."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return "unknown"


def _json_schema_accepts(json_schema: dict, args: dict) -> bool:
    """Interpret the projected JSON-schema's required/type/additionalProperties.

    Whether ``args`` satisfy the projected schema as we read its constraints — the
    "would the schema accept it?" side of the non-widening property.
    """
    properties = json_schema["properties"]
    required = json_schema["required"]
    additional = json_schema["additionalProperties"]
    for name in required:
        if name not in args:
            return False
    for key, value in args.items():
        if key in properties:
            type_spec = properties[key]["type"]
            allowed = type_spec if isinstance(type_spec, list) else [type_spec]
            if _json_type_of(value) not in allowed:
                return False
        elif not additional:
            return False
    return True


@given(data=st.data())
def test_projection_is_never_wider_than_validate(data):
    # SC-L002-1: for any argument dict the PROJECTED schema accepts, the authoritative
    # ParamSchema.validate ALSO accepts (after seed routing). The schema is advisory
    # and only ever stricter; it never permits what validate would reject.
    index = data.draw(st.integers(min_value=0, max_value=len(_PROJECTION_SCHEMAS) - 1))
    schema = _PROJECTION_SCHEMAS[index]
    args = data.draw(_schema_conforming_arguments(schema))

    json_schema = param_schema_to_json_schema(schema)
    # Generator sanity: what we drew genuinely conforms to the projected schema.
    assert _json_schema_accepts(json_schema, args)

    # Route the seed exactly as the facade does, then hit the authoritative gate.
    op = to_op(ToolCall(name="probe", arguments=args))
    # Must NOT raise — schema-accepted implies validate-accepted (non-widening).
    schema.validate(op.params, op.seed)


# --------------------------------------------------------------------------- #
# to_op — pure data mapping (seed routing), no validation, no eval (SC-L003)   #
# --------------------------------------------------------------------------- #


def test_to_op_routes_seed_out_of_params():
    op = to_op(ToolCall("procgen", {"algorithm": "value_noise", SEED_PROPERTY: 7}))
    assert isinstance(op, Op)
    assert op.name == "procgen"
    assert op.params == {"algorithm": "value_noise"}
    assert SEED_PROPERTY not in op.params
    assert op.seed == 7


def test_to_op_seed_absent_is_none():
    op = to_op(ToolCall("batch_recolour", {"color_map": []}))
    assert op.seed is None
    assert op.params == {"color_map": []}


def test_to_op_default_arguments_is_empty_mapping():
    op = to_op(ToolCall("procgen"))
    assert op.params == {}
    assert op.seed is None


def test_to_op_rejects_non_mapping_arguments():
    # Defensive IO-3 guard: a malformed (non-mapping) arguments payload is a domain
    # error, rejected before it reaches dispatch.
    with pytest.raises(ScriptError):
        to_op(ToolCall("procgen", [1, 2, 3]))  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# SC-L003-3 — a valid tool-call applies as ONE undoable group via dispatch     #
# --------------------------------------------------------------------------- #


def test_execute_valid_tool_call_applies_as_one_undoable_group():
    # SC-L003-3: a valid registered tool-call applies as one already-applied
    # reversible GroupCommand and mutates the document like the equivalent dispatch.
    doc = _rgba_doc()
    buf = _leaf_buffer(doc)
    before = _doc_bytes(doc)
    call = ToolCall("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})

    cmd = execute_tool_call(doc, call)

    assert isinstance(cmd, GroupCommand)
    assert isinstance(cmd, Command)
    assert tuple(buf.data[0, 0]) == RED  # applied
    assert _doc_bytes(doc) != before
    cmd.undo()  # ONE undo reverts the whole group
    assert _doc_bytes(doc) == before
    cmd.execute()  # redo re-applies
    assert tuple(buf.data[0, 0]) == RED


def test_execute_matches_equivalent_direct_dispatch():
    # SC-L003-3: execute_tool_call mutates the document identically to dispatching the
    # equivalent Op directly through the trusted path (it IS that path).
    call = ToolCall("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})
    doc_tool = _rgba_doc()
    doc_direct = _rgba_doc()

    execute_tool_call(doc_tool, call)
    scripting.dispatch(doc_direct, [to_op(call)])

    assert _doc_bytes(doc_tool) == _doc_bytes(doc_direct)


def test_execute_valid_seeded_procgen_tool_call():
    # A valid seeded procgen tool-call applies reversibly via the trusted dispatch.
    doc = _rgba_doc()
    buf = _leaf_buffer(doc)
    before = _doc_bytes(doc)
    call = ToolCall(
        "procgen", {"algorithm": "value_noise", "frequency": 2, SEED_PROPERTY: 7}
    )
    before_pixels = buf.data.copy()
    cmd = execute_tool_call(doc, call)
    assert not np.array_equal(buf.data, before_pixels)  # procgen mutated the buffer
    assert _doc_bytes(doc) != before
    cmd.undo()
    assert _doc_bytes(doc) == before


# --------------------------------------------------------------------------- #
# SC-L003-1/-2 — WHITELIST + atomicity: rejection leaves the document unchanged #
# --------------------------------------------------------------------------- #


def test_execute_unknown_op_raises_scripterror_and_leaves_document_identical():
    # SC-L003-1 [WHITELIST-ENFORCEMENT]: a tool-call naming a non-registered op is
    # rejected by dispatch with ScriptError; the document is byte-identical (the LLM
    # has no path to an op outside the registry).
    doc = _rgba_doc()
    before = _doc_bytes(doc)
    assert not scripting.is_registered("delete_everything")
    with pytest.raises(ScriptError):
        execute_tool_call(doc, ToolCall("delete_everything", {}))
    assert _doc_bytes(doc) == before


def test_execute_missing_required_param_raises_and_leaves_document_identical():
    # SC-L003-2 [WHITELIST-ENFORCEMENT]: a registered op with a missing required arg
    # is rejected in dispatch's up-front validate phase; document byte-identical.
    doc = _rgba_doc()
    before = _doc_bytes(doc)
    # procgen with a seed but no required "algorithm".
    with pytest.raises(ScriptError):
        execute_tool_call(doc, ToolCall("procgen", {SEED_PROPERTY: 7}))
    assert _doc_bytes(doc) == before


def test_execute_wrong_type_param_raises_and_leaves_document_identical():
    # SC-L003-2: a type-mismatched arg (algorithm must be a str) is rejected; the
    # document stays byte-identical.
    doc = _rgba_doc()
    before = _doc_bytes(doc)
    with pytest.raises(ScriptError):
        execute_tool_call(doc, ToolCall("procgen", {"algorithm": 5, SEED_PROPERTY: 1}))
    assert _doc_bytes(doc) == before


def test_execute_unknown_param_on_strict_op_raises_and_leaves_document_identical():
    # SC-L003-2: an extra param on a strict (allow_extra False) op is rejected — the
    # projected additionalProperties:false is honoured by the authoritative validate.
    doc = _rgba_doc()
    before = _doc_bytes(doc)
    call = ToolCall(
        "batch_recolour",
        {"color_map": [[list(TRANSPARENT), list(RED)]], "bogus": 1},
    )
    with pytest.raises(ScriptError):
        execute_tool_call(doc, call)
    assert _doc_bytes(doc) == before


def test_execute_bad_seed_type_raises_and_leaves_document_identical():
    # A routed non-int seed is rejected by validate; document byte-identical.
    doc = _rgba_doc()
    before = _doc_bytes(doc)
    call = ToolCall("batch_recolour", {"color_map": [], SEED_PROPERTY: "not-an-int"})
    with pytest.raises(ScriptError):
        execute_tool_call(doc, call)
    assert _doc_bytes(doc) == before


def test_regression_rejected_tool_call_is_atomic_bytes_identical():
    # REGRESSION (SC-L003-1/-2 atomicity guarantee): after a rejected tool-call the
    # document buffer .tobytes() is IDENTICAL to before the call — no partial apply is
    # ever left behind on the assistant path. Guards the validate-then-apply invariant
    # for both an unknown-op and an invalid-param rejection over the raw bytes.
    doc = _indexed_doc()
    buf = _leaf_buffer(doc)
    before = buf.data.tobytes()

    with pytest.raises(ScriptError):
        execute_tool_call(doc, ToolCall("wipe_disk", {"target": "everything"}))
    assert buf.data.tobytes() == before

    with pytest.raises(ScriptError):
        execute_tool_call(doc, ToolCall("procgen", {SEED_PROPERTY: 3}))  # no algorithm
    assert buf.data.tobytes() == before


# --------------------------------------------------------------------------- #
# SC-L008-1 — ZERO eval/exec/compile/__import__ SOURCE AUDIT                    #
# --------------------------------------------------------------------------- #

_FORBIDDEN = {"eval", "exec", "compile", "__import__"}


def _forbidden_calls(module) -> list:
    """The forbidden builtin call-names invoked anywhere in ``module``'s source."""
    tree = ast.parse(inspect.getsource(module))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in _FORBIDDEN:
            found.append(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in _FORBIDDEN:
            found.append(func.attr)
    return found


def test_tool_catalog_has_no_eval_exec_compile_import_call():
    # SC-L008-1 [ZERO-EVAL/EXEC SOURCE AUDIT]: the facade is eval-free BY CONSTRUCTION —
    # model output is data mapped onto the allow-listed registry, no interpreter to
    # escape. The only textual hits are docstrings describing the invariant.
    assert _forbidden_calls(tool_catalog) == []
