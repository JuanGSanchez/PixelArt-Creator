"""Tests for pixelart_creator.logic.macro — record / deterministic replay.

Covers REQ-P8-LOGIC-004 (record = ordered reversible ops, not a pixel diff),
-005 (**deterministic identical replay** — security invariant #3), -006 (replay
is one undoable grouped command), and -013 (MAX_MACRO_STEPS). Importing
``logic.scripting`` wires the trusted dispatcher into ``macro`` (dependency
injection), so ``replay`` runs through the one allow-listed path.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import scripting  # wires macro.set_dispatcher
from pixelart_creator.logic.constants import MAX_MACRO_STEPS
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command, GroupCommand
from pixelart_creator.logic.macro import (
    MACRO_SCHEMA_VERSION,
    MIN_APP_VERSION,
    Macro,
    MacroError,
    Op,
    get_dispatcher,
    record,
    replay,
)
from pixelart_creator.logic.palette import Palette

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def _doc(width: int = 6, height: int = 6) -> Document:
    return Document(width, height, palette=Palette([RED, BLUE, (0, 255, 0, 255)]))


def _leaf(doc: Document):
    return iter_layers(doc.frames[0].layers)[0].buffer


def _doc_hash(doc: Document) -> str:
    """SHA-256 over every leaf buffer of every frame — a whole-document fingerprint."""
    digest = hashlib.sha256()
    for frame in doc.frames:
        for layer in iter_layers(frame.layers):
            digest.update(np.ascontiguousarray(layer.buffer.data).tobytes())
    return digest.hexdigest()


# --------------------------------------------------------------------------- #
# Op / Macro data model                                                        #
# --------------------------------------------------------------------------- #


def test_op_defaults():
    op = Op("procgen")
    assert op.name == "procgen"
    assert op.params == {}
    assert op.seed is None


def test_op_and_macro_are_frozen():
    op = Op("procgen", {"a": 1}, seed=2)
    with pytest.raises(Exception):
        op.name = "other"  # type: ignore[misc]
    macro = Macro(MACRO_SCHEMA_VERSION, MIN_APP_VERSION, (op,))
    with pytest.raises(Exception):
        macro.ops = ()  # type: ignore[misc]


def test_op_equality_supports_round_trip_identity():
    assert Op("procgen", {"a": [1, 2]}, seed=5) == Op("procgen", {"a": [1, 2]}, seed=5)


# --------------------------------------------------------------------------- #
# record — REQ-P8-LOGIC-004                                                     #
# --------------------------------------------------------------------------- #


def test_record_captures_ordered_ops():
    ops = [Op("procgen", {"algorithm": "value_noise"}, seed=1), Op("batch_recolour")]
    macro = record(ops)
    assert macro.ops == tuple(ops)
    assert macro.schema_version == MACRO_SCHEMA_VERSION
    assert macro.min_app_version == MIN_APP_VERSION


def test_record_rejects_non_op():
    with pytest.raises(MacroError):
        record([Op("x"), "not-an-op"])  # type: ignore[list-item]


def test_record_enforces_max_macro_steps(monkeypatch):
    import pixelart_creator.logic.macro as macro_mod

    monkeypatch.setattr(macro_mod, "MAX_MACRO_STEPS", 2)
    with pytest.raises(MacroError):
        record([Op("batch_recolour") for _ in range(3)])


def test_max_macro_steps_single_sourced():
    import pixelart_creator.logic.macro as macro_mod

    assert macro_mod.MAX_MACRO_STEPS is MAX_MACRO_STEPS


# --------------------------------------------------------------------------- #
# replay — grouping, versioning, errors (REQ-P8-LOGIC-006)                      #
# --------------------------------------------------------------------------- #


def test_dispatcher_is_wired_by_scripting_import():
    # Importing scripting injects the trusted dispatcher (no macro→scripting edge).
    assert get_dispatcher() is scripting.dispatch


def test_replay_returns_one_undoable_group_command():
    doc = _doc()
    buf = _leaf(doc)
    before = buf.data.copy()
    macro = record(
        [Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})]
    )
    cmd = replay(doc, macro)
    assert isinstance(cmd, (GroupCommand, Command))
    assert tuple(buf.data[0, 0]) == RED
    cmd.undo()  # one undo reverts the whole replay
    assert np.array_equal(buf.data, before)


def test_replay_rejects_non_macro():
    with pytest.raises(MacroError):
        replay(_doc(), object())  # type: ignore[arg-type]


def test_replay_rejects_unsupported_schema_version():
    doc = _doc()
    bad = Macro("999", MIN_APP_VERSION, (Op("batch_recolour"),))
    with pytest.raises(MacroError):
        replay(doc, bad)


def test_get_dispatcher_raises_when_unset(monkeypatch):
    import pixelart_creator.logic.macro as macro_mod

    monkeypatch.setattr(macro_mod, "_dispatcher", None)
    with pytest.raises(MacroError):
        macro_mod.get_dispatcher()


# --------------------------------------------------------------------------- #
# SECURITY INVARIANT #3 — deterministic identical replay (REQ-P8-LOGIC-005)     #
# --------------------------------------------------------------------------- #


def _run_and_snapshot(macro: Macro, width: int = 6, height: int = 6) -> np.ndarray:
    """Replay ``macro`` on a fresh document and return the leaf-buffer bytes."""
    doc = _doc(width, height)
    replay(doc, macro)
    return _leaf(doc).data.copy()


def test_replay_is_deterministic_and_identical():
    # SC-L005-1: record a macro (incl. a seeded procgen op), replay on a fresh copy
    # of the same starting document twice → byte-IDENTICAL result.
    macro = record(
        [
            Op("procgen", {"algorithm": "opensimplex", "frequency": 3}, seed=42),
            Op("batch_recolour", {"color_map": [[list(RED), list(BLUE)]]}),
        ]
    )
    first = _run_and_snapshot(macro)
    second = _run_and_snapshot(macro)
    assert np.array_equal(first, second)


def test_replay_matches_original_dispatch_run():
    # The original run (via dispatch) and a replay of its recorded macro on a fresh
    # identical document produce the same state — CLI==GUI / record==replay parity.
    ops = [Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=9)]
    original_doc = _doc()
    scripting.dispatch(original_doc, ops)
    original = _leaf(original_doc).data.copy()

    replayed = _run_and_snapshot(record(ops))
    assert np.array_equal(original, replayed)


def test_same_seed_identical_different_seed_differs():
    # Sanity: same seed → identical procgen output; different seed → different.
    a = _run_and_snapshot(record([Op("procgen", {"algorithm": "value_noise"}, seed=1)]))
    a2 = _run_and_snapshot(
        record([Op("procgen", {"algorithm": "value_noise"}, seed=1)])
    )
    b = _run_and_snapshot(record([Op("procgen", {"algorithm": "value_noise"}, seed=2)]))
    assert np.array_equal(a, a2)
    assert not np.array_equal(a, b)


# --------------------------------------------------------------------------- #
# Hypothesis — property: replay of a random allow-listed macro is deterministic #
# --------------------------------------------------------------------------- #

_ALGORITHMS = ("value_noise", "gradient_noise", "opensimplex", "cellular_automata")


@st.composite
def _procgen_op(draw) -> Op:
    algorithm = draw(st.sampled_from(_ALGORITHMS))
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))
    params = {"algorithm": algorithm, "frequency": draw(st.integers(1, 4))}
    return Op("procgen", params, seed=seed)


@st.composite
def _recolour_op(draw) -> Op:
    def _rgba():
        return [draw(st.integers(0, 255)) for _ in range(4)]

    return Op("batch_recolour", {"color_map": [[_rgba(), _rgba()]]})


@given(ops=st.lists(st.one_of(_procgen_op(), _recolour_op()), min_size=0, max_size=5))
def test_property_replay_is_reproducible(ops):
    # Over random macros of allow-listed ops: replaying the same macro on two fresh
    # copies of the same document yields identical state (REQ-P8-LOGIC-005).
    macro = record(ops)
    assert np.array_equal(_run_and_snapshot(macro), _run_and_snapshot(macro))


# --------------------------------------------------------------------------- #
# ATOMIC REPLAY — replay inherits dispatch's all-or-nothing contract           #
# (REQ-P8-UI-008 / SC-UI-008-1, AGT-03 Phase-8 fix). A macro whose op-list      #
# contains an invalid op must leave the Document byte-IDENTICAL; a valid macro  #
# replays as ONE reversible group (a single undo reverts every op).            #
# --------------------------------------------------------------------------- #


def test_replay_invalid_op_leaves_document_identical():
    # macro = [valid procgen op, unknown op]. replay routes through the atomic
    # dispatcher → raises and the document is byte-identical (no partial mutation).
    doc = _doc()
    before = _doc_hash(doc)
    macro = record(
        [
            Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=7),
            Op("does_not_exist", {}),
        ]
    )
    with pytest.raises(scripting.ScriptError):
        replay(doc, macro)
    assert _doc_hash(doc) == before


def test_replay_invalid_op_not_last_leaves_document_identical():
    # Invalid op in the MIDDLE of the macro → still fully unchanged.
    doc = _doc()
    before = _doc_hash(doc)
    macro = record(
        [
            Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=7),
            Op("does_not_exist", {}),
            Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
        ]
    )
    with pytest.raises(scripting.ScriptError):
        replay(doc, macro)
    assert _doc_hash(doc) == before


def test_replay_valid_multiop_is_one_reversible_group_single_undo():
    # A fully-valid multi-op macro replays as ONE reversible group: a single undo
    # reverts ALL ops; redo re-applies all (whole-document assertion).
    doc = _doc()
    before = _doc_hash(doc)
    macro = record(
        [
            Op("procgen", {"algorithm": "value_noise", "frequency": 2}, seed=7),
            Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]}),
        ]
    )
    cmd = replay(doc, macro)
    assert isinstance(cmd, (GroupCommand, Command))
    after = _doc_hash(doc)
    assert after != before
    cmd.undo()  # ONE undo reverts the whole replay
    assert _doc_hash(doc) == before
    cmd.execute()  # ONE redo re-applies the whole replay
    assert _doc_hash(doc) == after
