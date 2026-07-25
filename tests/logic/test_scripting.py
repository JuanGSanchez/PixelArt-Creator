"""Tests for pixelart_creator.logic.scripting — the trusted DSL dispatcher.

Covers REQ-P8-LOGIC-001 (edits only via reversible commands / no back-door
mutation), -002 (Qt-free single engine for GUI + CLI), and -013 (bounds from
``logic.constants``). The paramount no-``eval``/``exec`` security invariant
(REQ-P8-LOGIC-003) lives in ``test_scripting_security.py``.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from pixelart_creator.logic import scripting
from pixelart_creator.logic.constants import MAX_SCRIPT_OPS
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command, FunctionCommand, GroupCommand
from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def _rgba_doc(width: int = 4, height: int = 4) -> Document:
    return Document(width, height, palette=Palette([RED, BLUE, (0, 255, 0, 255)]))


def _indexed_doc(width: int = 4, height: int = 4) -> Document:
    return Document(width, height, mode=ColorMode.INDEXED, palette=Palette([RED, BLUE]))


def _leaf_buffer(doc: Document):
    return iter_layers(doc.frames[0].layers)[0].buffer


def _doc_hash(doc: Document) -> str:
    """SHA-256 over every leaf buffer of every frame — a whole-document fingerprint.

    Captures the complete pixel state so an atomicity assertion detects *any*
    partial mutation (not just pixel [0, 0]) if the all-or-nothing contract slips.
    """
    digest = hashlib.sha256()
    for frame in doc.frames:
        for layer in iter_layers(frame.layers):
            digest.update(np.ascontiguousarray(layer.buffer.data).tobytes())
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# ParamSchema — defensive validation (IO-3 posture)                            #
# --------------------------------------------------------------------------- #


def test_param_schema_accepts_valid_params():
    schema = scripting.ParamSchema(fields={"n": int, "name": str}, required=("n",))
    assert schema.validate({"n": 3, "name": "x"}, None) == {"n": 3, "name": "x"}


def test_param_schema_rejects_non_mapping():
    with pytest.raises(scripting.ScriptError):
        scripting.ParamSchema().validate([1, 2, 3], None)  # type: ignore[arg-type]


def test_param_schema_rejects_missing_required():
    schema = scripting.ParamSchema(fields={"n": int}, required=("n",))
    with pytest.raises(scripting.ScriptError):
        schema.validate({}, None)


def test_param_schema_rejects_unknown_param():
    schema = scripting.ParamSchema(fields={"n": int})
    with pytest.raises(scripting.ScriptError):
        schema.validate({"other": 1}, None)


def test_param_schema_rejects_type_mismatch():
    schema = scripting.ParamSchema(fields={"n": int})
    with pytest.raises(scripting.ScriptError):
        schema.validate({"n": "not-an-int"}, None)


def test_param_schema_rejects_bool_for_int():
    # bool is a subclass of int; the schema must reject it for an int field.
    schema = scripting.ParamSchema(fields={"n": int})
    with pytest.raises(scripting.ScriptError):
        schema.validate({"n": True}, None)


def test_param_schema_rejects_non_string_key():
    schema = scripting.ParamSchema(allow_extra=True)
    with pytest.raises(scripting.ScriptError):
        schema.validate({1: "x"}, None)  # type: ignore[dict-item]


def test_param_schema_allow_extra_requires_json_native():
    schema = scripting.ParamSchema(allow_extra=True)
    with pytest.raises(scripting.ScriptError):
        schema.validate({"extra": object()}, None)


def test_param_schema_allow_extra_accepts_json_native():
    schema = scripting.ParamSchema(allow_extra=True)
    out = schema.validate({"extra": [1, 2, {"k": "v"}]}, None)
    assert out == {"extra": [1, 2, {"k": "v"}]}


def test_param_schema_requires_seed():
    schema = scripting.ParamSchema(requires_seed=True)
    with pytest.raises(scripting.ScriptError):
        schema.validate({}, None)
    assert schema.validate({}, 7) == {}


def test_param_schema_rejects_non_int_seed():
    schema = scripting.ParamSchema()
    with pytest.raises(scripting.ScriptError):
        schema.validate({}, "5")  # type: ignore[arg-type]
    with pytest.raises(scripting.ScriptError):
        schema.validate({}, True)


# --------------------------------------------------------------------------- #
# register / unregister / introspection                                        #
# --------------------------------------------------------------------------- #


def test_builtin_ops_registered():
    assert scripting.is_registered(scripting.OP_BATCH_RECOLOUR)
    assert scripting.is_registered(scripting.OP_PROCGEN)
    assert scripting.OP_BATCH_RECOLOUR in scripting.registered_ops()
    assert scripting.OP_PROCGEN in scripting.registered_ops()


def test_registered_ops_is_sorted_tuple():
    ops = scripting.registered_ops()
    assert isinstance(ops, tuple)
    assert list(ops) == sorted(ops)


def test_register_and_unregister_roundtrip(registry_guard):
    schema = scripting.ParamSchema()

    def _factory(doc, params, seed):
        return GroupCommand([], label="noop")

    registry_guard.register_command("test.noop", _factory, schema)
    assert registry_guard.is_registered("test.noop")
    registry_guard.unregister_command("test.noop")
    assert not registry_guard.is_registered("test.noop")


def test_register_rejects_empty_name(registry_guard):
    with pytest.raises(scripting.ScriptError):
        registry_guard.register_command(
            "", lambda d, p, s: None, scripting.ParamSchema()
        )


def test_register_rejects_duplicate(registry_guard):
    with pytest.raises(scripting.ScriptError):
        registry_guard.register_command(
            scripting.OP_PROCGEN, lambda d, p, s: None, scripting.ParamSchema()
        )


def test_register_rejects_non_callable_factory(registry_guard):
    with pytest.raises(scripting.ScriptError):
        registry_guard.register_command("test.x", 123, scripting.ParamSchema())


def test_register_rejects_bad_schema(registry_guard):
    with pytest.raises(scripting.ScriptError):
        registry_guard.register_command("test.x", lambda d, p, s: None, object())


def test_unregister_unknown_raises():
    with pytest.raises(scripting.ScriptError):
        scripting.unregister_command("never.registered")


# --------------------------------------------------------------------------- #
# dispatch — SC-L001: an edit is applied only through a reversible Command      #
# --------------------------------------------------------------------------- #


def test_dispatch_returns_group_command():
    doc = _rgba_doc()
    cmd = scripting.dispatch(doc, [])
    assert isinstance(cmd, GroupCommand)
    assert isinstance(cmd, Command)


def test_dispatch_applies_and_is_reversible():
    # SC-L001-1 / REQ-P8-LOGIC-001: the scripted edit is a Command and
    # apply ∘ undo == identity — the ONLY mutation path.
    doc = _rgba_doc()
    buf = _leaf_buffer(doc)
    before = buf.data.copy()
    cmd = scripting.dispatch(
        doc, [Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})]
    )
    # The whole buffer became RED (transparent → red) — the edit was applied.
    assert tuple(buf.data[0, 0]) == RED
    assert not np.array_equal(buf.data, before)
    cmd.undo()
    assert np.array_equal(buf.data, before)
    cmd.execute()  # redo
    assert tuple(buf.data[0, 0]) == RED


def test_dispatch_orders_ops_and_groups_children():
    doc = _rgba_doc()
    buf = _leaf_buffer(doc)
    cmd = scripting.dispatch(
        doc,
        [
            Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
            Op("batch_recolour", {"color_map": [[list(RED), list(BLUE)]]}),
        ],
    )
    assert tuple(buf.data[0, 0]) == BLUE  # second op saw the first's effect
    assert isinstance(cmd, GroupCommand)
    assert len(cmd) == 2
    cmd.undo()
    assert tuple(buf.data[0, 0]) == TRANSPARENT


def test_dispatch_rejects_non_op_step():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, ["not-an-op"])  # type: ignore[list-item]


def test_dispatch_rejects_unknown_op():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("nonexistent_op", {})])


def test_dispatch_enforces_max_script_ops(monkeypatch):
    # REQ-P8-LOGIC-013: the per-run bound comes from logic.constants.
    monkeypatch.setattr(scripting, "MAX_SCRIPT_OPS", 2)
    doc = _rgba_doc()
    ops = [Op("batch_recolour", {"color_map": []})] * 3
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, ops)


def test_max_script_ops_constant_single_sourced():
    assert scripting.MAX_SCRIPT_OPS is MAX_SCRIPT_OPS


# --------------------------------------------------------------------------- #
# batch_recolour built-in factory param resolution                            #
# --------------------------------------------------------------------------- #


def test_batch_recolour_targets_by_layer_id():
    doc = _rgba_doc()
    layer = iter_layers(doc.frames[0].layers)[0]
    cmd = scripting.dispatch(
        doc,
        [
            Op(
                "batch_recolour",
                {
                    "targets": [layer.layer_id],
                    "color_map": [[list(TRANSPARENT), list(RED)]],
                },
            )
        ],
    )
    assert tuple(layer.buffer.data[0, 0]) == RED
    cmd.undo()


def test_batch_recolour_rejects_bad_frame_index_type():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("batch_recolour", {"frame_index": True})])


def test_batch_recolour_rejects_out_of_range_frame_index():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("batch_recolour", {"frame_index": 9})])


def test_batch_recolour_rejects_non_list_targets():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(
            doc, [Op("batch_recolour", {"targets": {}, "color_map": []})]
        )


def test_batch_recolour_rejects_unknown_layer_id():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(
            doc,
            [Op("batch_recolour", {"targets": [99999], "color_map": []})],
        )


def test_batch_recolour_requires_exactly_one_mapping():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("batch_recolour", {})])  # neither
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(
            doc,
            [Op("batch_recolour", {"index_map": [[0, 1]], "color_map": []})],
        )  # both


def test_batch_recolour_index_map_on_indexed_doc():
    doc = _indexed_doc()
    buf = _leaf_buffer(doc)
    cmd = scripting.dispatch(doc, [Op("batch_recolour", {"index_map": [[0, 1]]})])
    assert int(buf.data[0, 0]) == 1
    cmd.undo()
    assert int(buf.data[0, 0]) == 0


def test_batch_recolour_malformed_index_map():
    doc = _indexed_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("batch_recolour", {"index_map": [["a", "b"]]})])


def test_batch_recolour_index_map_not_list():
    doc = _indexed_doc()
    with pytest.raises(scripting.ScriptError):
        # schema field type is list; a str trips the schema first.
        scripting.dispatch(doc, [Op("batch_recolour", {"index_map": "x"})])


def test_batch_recolour_malformed_colour_length():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(
            doc, [Op("batch_recolour", {"color_map": [[[0, 0, 0], [1, 1, 1]]]})]
        )


def test_batch_recolour_normalises_batch_error():
    # An index_map on an RGBA target: batch_ops raises BatchError, normalised to
    # ScriptError by the built-in factory.
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("batch_recolour", {"index_map": [[0, 1]]})])


# --------------------------------------------------------------------------- #
# procgen built-in factory                                                     #
# --------------------------------------------------------------------------- #


def test_procgen_op_requires_seed():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("procgen", {"algorithm": "value_noise"})])


def test_procgen_op_requires_algorithm_param():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        # missing required 'algorithm'
        scripting.dispatch(doc, [Op("procgen", {}, seed=1)])


def test_procgen_op_rejects_non_string_algorithm():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("procgen", {"algorithm": 5}, seed=1)])


def test_procgen_op_applies_reversibly():
    doc = _rgba_doc()
    buf = _leaf_buffer(doc)
    before = buf.data.copy()
    cmd = scripting.dispatch(
        doc, [Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=7)]
    )
    assert not np.array_equal(buf.data, before)
    cmd.undo()
    assert np.array_equal(buf.data, before)


def test_procgen_op_normalises_procgen_error():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, [Op("procgen", {"algorithm": "no_such_algo"}, seed=1)])


# --------------------------------------------------------------------------- #
# Defensive re-checks in the built-in factory helpers (white-box).             #
# These guards sit BEHIND the ParamSchema — the schema rejects the same bad    #
# inputs first via dispatch — so they are exercised by calling the helpers     #
# directly, proving the engine stays defensive even if a caller bypasses the   #
# schema (defence in depth, IO-3 posture).                                     #
# --------------------------------------------------------------------------- #


def test_resolve_targets_rejects_bad_frame_index_type_directly():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting._resolve_recolour_targets(doc, {"frame_index": True})


def test_resolve_targets_rejects_non_list_targets_directly():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting._resolve_recolour_targets(doc, {"targets": {}})


def test_mapping_rejects_non_list_index_map_directly():
    with pytest.raises(scripting.ScriptError):
        scripting._mapping_from_params({"index_map": "x"})


def test_mapping_rejects_non_list_color_map_directly():
    with pytest.raises(scripting.ScriptError):
        scripting._mapping_from_params({"color_map": "x"})


def test_procgen_factory_rejects_non_string_algorithm_directly():
    doc = _rgba_doc()
    with pytest.raises(scripting.ScriptError):
        scripting._procgen_factory(doc, {"algorithm": 5}, 1)


# --------------------------------------------------------------------------- #
# ATOMIC DISPATCH — REQ-P8-UI-008 / SC-UI-008-1 (AGT-03 Phase-8 fix)            #
#                                                                              #
# The invariant: dispatch either yields ONE complete reversible GroupCommand   #
# (success) or raises with the Document byte/state-IDENTICAL to before the     #
# call — never a partial mutation off the undo stack. Phase 1 validates the    #
# whole op list up front (zero mutation); Phase 2 applies as one group and     #
# rolls back (undo, reverse order) any applied sub-commands if a later op fails.#
# --------------------------------------------------------------------------- #


def test_dispatch_atomic_invalid_last_op_leaves_document_identical():
    # AGT-06 reproduction: [valid procgen op, unknown op]. Phase-1 validation
    # rejects op[1] before op[0] is ever built or applied → NO partial mutation.
    doc = _rgba_doc()
    before = _doc_hash(doc)
    ops = [
        Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=7),
        Op("does_not_exist", {}),
    ]
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, ops)
    assert _doc_hash(doc) == before  # document byte-identical to before the call


def test_dispatch_atomic_invalid_op_not_last_leaves_document_identical():
    # Invalid op in the MIDDLE ([valid, invalid, valid]) → still fully unchanged;
    # the trailing valid op must never be applied either.
    doc = _rgba_doc()
    before = _doc_hash(doc)
    ops = [
        Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=7),
        Op("does_not_exist", {}),
        Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
    ]
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, ops)
    assert _doc_hash(doc) == before


def test_dispatch_atomic_invalid_params_mid_list_leaves_document_identical():
    # A schema-invalid (but registered) op mid-list is also caught in Phase 1 →
    # the preceding valid op is never applied.
    doc = _rgba_doc()
    before = _doc_hash(doc)
    ops = [
        Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
        Op("procgen", {"algorithm": 5}, seed=1),  # algorithm must be a str
        Op("batch_recolour", {"color_map": [[list(RED), list(BLUE)]]}),
    ]
    with pytest.raises(scripting.ScriptError):
        scripting.dispatch(doc, ops)
    assert _doc_hash(doc) == before


def test_dispatch_atomic_midapplication_factory_failure_rolls_back(registry_guard):
    # Phase-2 failure path: an op that PASSES validation but whose factory raises
    # during application. The already-applied earlier op must be rolled back so the
    # document is left exactly as it started.
    doc = _rgba_doc()
    before = _doc_hash(doc)

    def _boom_factory(document, params, seed):
        raise RuntimeError("factory blew up during application")

    registry_guard.register_command(
        "test.boom_factory", _boom_factory, scripting.ParamSchema()
    )
    ops = [
        Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
        Op("test.boom_factory", {}),
    ]
    with pytest.raises(RuntimeError):
        scripting.dispatch(doc, ops)
    assert _doc_hash(doc) == before


def test_dispatch_atomic_midapplication_execute_failure_rolls_back_reverse(
    registry_guard,
):
    # Phase-2 failure path where an op's command.execute() raises AFTER earlier ops
    # applied: assert the applied sub-commands are undone in REVERSE order and the
    # document is left byte-identical.
    doc = _rgba_doc()
    buf = _leaf_buffer(doc)
    before = _doc_hash(doc)
    undo_order: list[str] = []

    def _record_factory(document, params, seed):
        tag = params["tag"]

        def _do() -> None:
            buf.set_pixel(0, 0, RED)

        def _undo() -> None:
            undo_order.append(tag)
            buf.set_pixel(0, 0, TRANSPARENT)

        return FunctionCommand(_do, _undo, label=f"rec-{tag}")

    def _boom_execute_factory(document, params, seed):
        def _do() -> None:
            raise RuntimeError("execute blew up")

        return FunctionCommand(_do, lambda: None, label="boom-exec")

    rec_schema = scripting.ParamSchema(fields={"tag": str}, required=("tag",))
    registry_guard.register_command("test.rec", _record_factory, rec_schema)
    registry_guard.register_command(
        "test.boom_execute", _boom_execute_factory, scripting.ParamSchema()
    )

    ops = [
        Op("test.rec", {"tag": "A"}),
        Op("test.rec", {"tag": "B"}),
        Op("test.boom_execute", {}),
    ]
    with pytest.raises(RuntimeError):
        scripting.dispatch(doc, ops)
    # A applied, then B; boom's execute raised → rollback undoes B then A (reverse).
    assert undo_order == ["B", "A"]
    assert _doc_hash(doc) == before


def test_dispatch_valid_multiop_is_one_reversible_group_single_undo():
    # SUCCESS path: a fully-valid multi-op script applies as ONE reversible group.
    # A SINGLE undo reverts ALL ops; redo re-applies all — whole-document assertion.
    doc = _rgba_doc()
    before = _doc_hash(doc)
    ops = [
        Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=7),
        Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
        Op("batch_recolour", {"color_map": [[list(RED), list(BLUE)]]}),
    ]
    cmd = scripting.dispatch(doc, ops)
    assert isinstance(cmd, GroupCommand)
    assert len(cmd) == 3
    after = _doc_hash(doc)
    assert after != before  # the group applied
    cmd.undo()  # ONE undo reverts every op
    assert _doc_hash(doc) == before
    cmd.execute()  # ONE redo re-applies every op
    assert _doc_hash(doc) == after


def test_dispatch_group_with_seeded_procgen_replays_identically():
    # Determinism preserved through the atomic group: the same seeded multi-op
    # script dispatched on two fresh documents yields a byte-identical result.
    ops = [
        Op("procgen", {"algorithm": "value_noise", "frequency": 3}, seed=123),
        Op("batch_recolour", {"color_map": [[list(RED), list(BLUE)]]}),
    ]
    doc_a = _rgba_doc()
    doc_b = _rgba_doc()
    scripting.dispatch(doc_a, ops)
    scripting.dispatch(doc_b, ops)
    assert _doc_hash(doc_a) == _doc_hash(doc_b)
