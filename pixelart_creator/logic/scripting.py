# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Data-driven command DSL + trusted dispatcher — the automation surface (zero Qt, S11).

**Article VII, by construction (ADR-0021):** the automation engine executes
**data** (a validated list of :class:`~pixelart_creator.logic.macro.Op` —
``{name, params, seed}``), never a language. There is **no ``eval`` / ``exec`` /
``compile`` / ``__import__`` of user input anywhere on this path** — there is no
interpreter to escape. The single trusted :func:`dispatch` validates each op-name
against an **allow-listed registry** and its params against the op's declared
:class:`ParamSchema`, constructs the reversible
:class:`~pixelart_creator.logic.history.Command` the factory returns, applies it,
and groups the run into one undoable
:class:`~pixelart_creator.logic.history.GroupCommand`. An op becomes executable
**only** by being registered (:func:`register_command`) — there is no back-door
mutation path (REQ-P8-LOGIC-001), and the same engine drives the GUI and the
headless CLI identically (REQ-P8-LOGIC-002/-014).

Layering (plan §4.4 / ADR-0022, FROZEN): ``scripting`` imports ``macro`` (its DSL
data types ``Op``/``Macro``), ``procgen`` and ``batch_ops`` (to register the
built-in ops), plus ``history``/``document``/``constants``. It is **not** imported
by ``macro`` (dependency-injected the other way — see below) and imports ``procgen``
/``batch_ops`` one-way (they never import ``scripting``); ``plugins`` imports
``scripting`` one-way. ``Op``/``Macro`` are re-exported here so ``scripting.Op`` is
valid even though they are *defined* in ``macro`` (the acyclic edge ``scripting →
macro``). At import, this module injects :func:`dispatch` into ``macro`` via
:func:`macro.set_dispatcher` so ``macro.replay`` runs through this one trusted path
without a ``macro → scripting`` back-edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple, Union

from pixelart_creator.logic import batch_ops, macro, procgen
from pixelart_creator.logic.batch_ops import ColorMapping, RecolourTarget
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import MAX_SCRIPT_OPS
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command, GroupCommand
from pixelart_creator.logic.macro import Macro, Op

__all__ = [
    "ScriptError",
    "Op",
    "Macro",
    "ParamSchema",
    "CommandFactory",
    "register_command",
    "unregister_command",
    "is_registered",
    "registered_ops",
    "schema_for",
    "dispatch",
    "OP_BATCH_RECOLOUR",
    "OP_PROCGEN",
]

#: Built-in DSL op names — module-local enumerated vocabulary (ADR-0001 / BF-2).
OP_BATCH_RECOLOUR = "batch_recolour"
OP_PROCGEN = "procgen"

#: A JSON-native scalar the DSL accepts as a param value.
_JSON_SCALAR = (int, float, str, bool, type(None))

#: A command factory: ``(document, validated_params, seed) -> reversible Command``.
CommandFactory = Callable[[Document, Mapping[str, object], Optional[int]], Command]


class ScriptError(ValueError):
    """Raised on an unknown op, invalid params, or a per-run bound breach."""


def _is_json_native(value: object) -> bool:
    """Whether ``value`` is JSON-native (so a recorded macro round-trips exactly)."""
    if isinstance(value, _JSON_SCALAR):
        return True
    if isinstance(value, list):
        return all(_is_json_native(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_json_native(v) for k, v in value.items())
    return False


@dataclass(frozen=True)
class ParamSchema:
    """A defensive, IO-3-style parameter schema for one registered op.

    ``fields`` maps a param name to its allowed type(s); ``required`` names the
    params that must be present. Unknown params are rejected unless
    ``allow_extra`` (used by ``procgen`` for algorithm-specific knobs), in which
    case each extra must still be JSON-native. ``requires_seed`` enforces a
    captured seed for stochastic ops (mandatory-seed determinism, ADR-0022 §1).
    """

    fields: Mapping[str, Union[type, Tuple[type, ...]]] = field(default_factory=dict)
    required: Tuple[str, ...] = ()
    allow_extra: bool = False
    requires_seed: bool = False

    def validate(
        self, params: Mapping[str, object], seed: Optional[int]
    ) -> Dict[str, object]:
        """Validate ``params``/``seed`` defensively; return a resolved copy.

        Raises:
            ScriptError: On a non-mapping, a missing required param, an unknown
                param (when ``allow_extra`` is off), a type mismatch, a
                non-JSON-native extra, or a missing required seed.
        """
        if not isinstance(params, Mapping):
            raise ScriptError(f"op params must be a mapping, got {params!r}")
        for name in self.required:
            if name not in params:
                raise ScriptError(f"missing required param {name!r}")
        for key, value in params.items():
            if not isinstance(key, str):
                raise ScriptError(f"param key must be a str, got {key!r}")
            if key in self.fields:
                expected = self.fields[key]
                bad_bool = expected is int and isinstance(value, bool)
                if not isinstance(value, expected) or bad_bool:
                    type_name = getattr(expected, "__name__", str(expected))
                    raise ScriptError(f"param {key!r} must be {type_name}")
            elif not self.allow_extra:
                raise ScriptError(f"unknown param {key!r}")
            elif not _is_json_native(value):
                raise ScriptError(f"param {key!r} is not JSON-native")
        if self.requires_seed and seed is None:
            raise ScriptError("this op requires a recorded seed")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            raise ScriptError(f"seed must be an int, got {seed!r}")
        return dict(params)


@dataclass(frozen=True)
class _RegisteredOp:
    factory: CommandFactory
    schema: ParamSchema


#: The allow-list: op-name -> trusted factory + schema. THE only way an op becomes
#: executable (REQ-P8-LOGIC-001). Populated with built-ins at import (below) and
#: extended by consent-gated plugins via the capability object (``logic.plugins``).
_REGISTRY: Dict[str, _RegisteredOp] = {}


def register_command(name: str, factory: CommandFactory, schema: ParamSchema) -> None:
    """Register a trusted op under ``name`` — the ONLY way an op becomes executable.

    Args:
        name: The DSL op-name (unique; a duplicate is rejected, no clobbering).
        factory: A callable returning a reversible ``Command`` for validated params.
        schema: The defensive :class:`ParamSchema` for the op's params.

    Raises:
        ScriptError: If ``name`` is invalid, already registered, or the arguments
            are the wrong type.
    """
    if not isinstance(name, str) or not name:
        raise ScriptError(f"op name must be a non-empty str, got {name!r}")
    if name in _REGISTRY:
        raise ScriptError(f"op {name!r} is already registered")
    if not callable(factory):
        raise ScriptError(f"factory for {name!r} must be callable")
    if not isinstance(schema, ParamSchema):
        raise ScriptError(f"schema for {name!r} must be a ParamSchema")
    _REGISTRY[name] = _RegisteredOp(factory=factory, schema=schema)


def unregister_command(name: str) -> None:
    """Remove a registered op (used when a plugin is disabled).

    Raises:
        ScriptError: If ``name`` is not registered.
    """
    if name not in _REGISTRY:
        raise ScriptError(f"op {name!r} is not registered")
    del _REGISTRY[name]


def is_registered(name: str) -> bool:
    """Whether ``name`` is an executable op in the allow-list."""
    return name in _REGISTRY


def registered_ops() -> Tuple[str, ...]:
    """Return the sorted tuple of currently registered op-names (introspection)."""
    return tuple(sorted(_REGISTRY))


def schema_for(name: str) -> ParamSchema:
    """Return the :class:`ParamSchema` of a registered op (read-only introspection).

    The public schema-introspection seam paired with :func:`registered_ops` /
    :func:`is_registered`: it exposes an op's declared param contract without
    reaching into the allow-list registry. It mutates nothing and adds no
    registration path — the returned :class:`ParamSchema` is frozen, and
    :func:`dispatch` remains the sole authority that validates + applies ops.

    Args:
        name: A DSL op-name (as returned by :func:`registered_ops`).

    Returns:
        The op's shipped defensive :class:`ParamSchema`.

    Raises:
        ScriptError: If ``name`` is not in the allow-list registry.
    """
    registered = _REGISTRY.get(name)
    if registered is None:
        raise ScriptError(f"op {name!r} is not registered")
    return registered.schema


def dispatch(
    document: Document,
    ops: Sequence[Op],
    on_target: Optional[Callable[[int, int], None]] = None,
) -> Command:
    """Validate + apply an ordered DSL ``ops`` list **atomically**; return one group.

    The single trusted interpreter (REQ-P8-LOGIC-001/-002/-003), guaranteeing the
    all-or-nothing dispatch contract (REQ-P8-UI-008 / SC-UI-008-1). It runs in two
    phases so a mid-run failure never leaves a partial mutation off the undo stack:

    * **Phase 1 — validate the ENTIRE op list up front, mutating nothing.** Every
      step must be an :class:`Op`, its ``name`` must resolve against the allow-list
      registry (an unknown op is a :class:`ScriptError`), and its params/seed must
      pass the op's :class:`ParamSchema` (defensive, IO-3-style). If any op is
      invalid the call raises here with the ``document`` **byte/state-identical to
      before the call** — nothing was applied (this is the ``[valid, unknown]``
      atomicity case).
    * **Phase 2 — apply every op as ONE reversible group.** The factories run in
      order and each command is applied immediately, so a later op sees the effect
      of an earlier one (deterministic, state-identical replay); building a
      command may legitimately depend on that applied state. If an op still fails
      here (unexpected — e.g. a document-dependent factory rejects live state), the
      already-applied sub-commands are **undone in reverse before the error is
      re-raised**, so the document is left exactly as it started.

    The result on success is one **already-applied**
    :class:`~pixelart_creator.logic.history.GroupCommand` (push with
    ``execute=False``; ``ui.commands`` wraps it as one ``QUndoCommand``, the CLI
    saves the mutated document). The invariant holds whether ``dispatch`` is called
    to APPLY the run or to BUILD-and-revert it (the off-thread worker's model): it
    either produces one complete group covering all ops, or raises with the
    document unchanged. **No input reaches ``eval``/``exec``** — ops are data mapped
    to allow-listed factories. :func:`~pixelart_creator.logic.macro.replay` routes
    through this same atomic path, so a failing op mid-replay leaves the doc intact.

    Args:
        document: The subject document (mutated in place by the applied commands).
        ops: The ordered DSL steps (``0..MAX_SCRIPT_OPS``).
        on_target: Optional per-target progress callback, additive and off by
            default (``None`` preserves prior behaviour exactly — no new UI/CLI
            caller is required to pass it). Invoked as ``on_target(index, total)``
            immediately after each op's command has been applied in Phase 2 —
            ``index`` is 1-based (``1..total``) and ``total`` is ``len(ops)``, so
            a 3-op run reports ``(1, 3)``, ``(2, 3)``, ``(3, 3)``. **A raising
            callback is caught and discarded, never re-raised and never treated
            as an op failure**: this dispatcher's error philosophy reserves
            ``except Exception`` + rollback for a *domain* factory/apply failure
            (Phase 2's own contract, above), and a progress observer is not part
            of that domain — letting an observer's bug trigger a rollback would
            undo an otherwise-successful op because of an unrelated UI concern,
            which is a worse defect than a dropped progress notification.

    Returns:
        A grouped, already-applied :class:`~pixelart_creator.logic.history.Command`.

    Raises:
        ScriptError: On ``> MAX_SCRIPT_OPS`` ops, a non-:class:`Op` step, an
            unknown op, or invalid params. On any such raise the document is
            unchanged (no partial application).
    """
    ops = list(ops)
    if len(ops) > MAX_SCRIPT_OPS:
        raise ScriptError(f"script exceeds MAX_SCRIPT_OPS ({MAX_SCRIPT_OPS})")

    # Phase 1 — validate the WHOLE list before touching the document. No factory
    # runs and no command is applied here, so any failure raises with the document
    # untouched (the AGT-06 [valid op, unknown op] partial-mutation defect).
    plan: list[Tuple[_RegisteredOp, Dict[str, object], Optional[int]]] = []
    for position, op in enumerate(ops):
        if not isinstance(op, Op):
            raise ScriptError(f"op {position} is not an Op: {op!r}")
        registered = _REGISTRY.get(op.name)
        if registered is None:
            raise ScriptError(f"unknown op {op.name!r} at position {position}")
        validated = registered.schema.validate(op.params, op.seed)
        plan.append((registered, validated, op.seed))

    # Phase 2 — apply every op as ONE atomic group. If any op fails during
    # application (despite passing Phase 1), roll back the already-applied
    # sub-commands in reverse so the document is left exactly as it started,
    # then re-raise — never a partial mutation left off the undo stack.
    applied: list[Command] = []
    total = len(plan)
    try:
        for index, (registered, validated, seed) in enumerate(plan, start=1):
            command = registered.factory(document, validated, seed)
            command.execute()
            applied.append(command)
            if on_target is not None:
                try:
                    on_target(index, total)
                except Exception:
                    pass
    except Exception:
        for command in reversed(applied):
            command.undo()
        raise
    return GroupCommand(applied, label="script")


# --------------------------------------------------------------------------- #
# Built-in DSL commands (T8C-03) — batch recolour + procedural generation      #
# --------------------------------------------------------------------------- #


def _resolve_recolour_targets(
    document: Document, params: Mapping[str, object]
) -> list[RecolourTarget]:
    """Resolve the ``targets`` param (layer_ids) to buffers, default all leaves."""
    frame_index = params.get("frame_index", 0)
    if not isinstance(frame_index, int) or isinstance(frame_index, bool):
        raise ScriptError(f"frame_index must be an int, got {frame_index!r}")
    if not 0 <= frame_index < len(document.frames):
        raise ScriptError(f"frame_index {frame_index} out of range")
    leaves = iter_layers(document.frames[frame_index].layers)
    layer_ids = params.get("targets")
    if layer_ids is None:
        return [RecolourTarget(layer.buffer, layer.name) for layer in leaves]
    if not isinstance(layer_ids, list):
        raise ScriptError("'targets' must be a list of layer_id ints")
    by_id = {layer.layer_id: layer for layer in leaves}
    resolved: list[RecolourTarget] = []
    for lid in layer_ids:
        if not isinstance(lid, int) or isinstance(lid, bool) or lid not in by_id:
            raise ScriptError(f"unknown target layer_id {lid!r}")
        layer = by_id[lid]
        resolved.append(RecolourTarget(layer.buffer, layer.name))
    return resolved


def _mapping_from_params(params: Mapping[str, object]) -> ColorMapping:
    """Build a :class:`ColorMapping` from JSON-native list params."""
    index_pairs = params.get("index_map")
    color_pairs = params.get("color_map")
    if (index_pairs is None) == (color_pairs is None):
        raise ScriptError("provide exactly one of 'index_map' or 'color_map'")
    if index_pairs is not None:
        if not isinstance(index_pairs, list):
            raise ScriptError("'index_map' must be a list of [src, dst] pairs")
        try:
            index_map = {int(src): int(dst) for src, dst in index_pairs}
        except (TypeError, ValueError) as exc:
            raise ScriptError(f"malformed index_map: {exc}") from exc
        return ColorMapping(index_map=index_map)
    if not isinstance(color_pairs, list):
        raise ScriptError("'color_map' must be a list of [src_rgba, dst_rgba] pairs")
    try:
        color_map = {_as_rgba(src): _as_rgba(dst) for src, dst in color_pairs}
    except (TypeError, ValueError) as exc:
        raise ScriptError(f"malformed color_map: {exc}") from exc
    return ColorMapping(color_map=color_map)


def _as_rgba(seq: object) -> RGBA:
    """Coerce a JSON list/tuple of 4 ints into an :data:`RGBA` (defensive)."""
    if not isinstance(seq, (list, tuple)) or len(seq) != 4:
        raise ScriptError(f"colour must be a 4-element [r,g,b,a], got {seq!r}")
    return (int(seq[0]), int(seq[1]), int(seq[2]), int(seq[3]))


def _batch_recolour_factory(
    document: Document, params: Mapping[str, object], seed: Optional[int]
) -> Command:
    """Built-in ``batch_recolour`` factory composing ``logic.batch_ops`` (PS-1)."""
    targets = _resolve_recolour_targets(document, params)
    mapping = _mapping_from_params(params)
    try:
        return batch_ops.make_batch_recolour_command(targets, mapping)
    except batch_ops.BatchError as exc:
        raise ScriptError(str(exc)) from exc


def _procgen_factory(
    document: Document, params: Mapping[str, object], seed: Optional[int]
) -> Command:
    """Built-in ``procgen`` factory composing ``logic.procgen`` (seeded, PB-1)."""
    algorithm = params.get("algorithm")
    if not isinstance(algorithm, str):
        raise ScriptError("procgen requires a string 'algorithm' param")
    gen_params = {k: v for k, v in params.items() if k != "algorithm"}
    effective_seed = seed if seed is not None else procgen.DEFAULT_PROCGEN_SEED
    try:
        return procgen.make_procgen_command(
            document,
            algorithm=algorithm,
            params=gen_params,
            seed=effective_seed,
        )
    except procgen.ProcgenError as exc:
        raise ScriptError(str(exc)) from exc


_BATCH_RECOLOUR_SCHEMA = ParamSchema(
    fields={
        "targets": list,
        "frame_index": int,
        "index_map": list,
        "color_map": list,
    },
    required=(),
    allow_extra=False,
    requires_seed=False,
)

_PROCGEN_SCHEMA = ParamSchema(
    fields={"algorithm": str},
    required=("algorithm",),
    allow_extra=True,  # algorithm-specific knobs (frequency, octaves, colours, …)
    requires_seed=True,  # mandatory recorded seed → deterministic replay
)


def _register_builtins() -> None:
    """Register the built-in ops (idempotent guard for re-import safety)."""
    if not is_registered(OP_BATCH_RECOLOUR):
        register_command(
            OP_BATCH_RECOLOUR, _batch_recolour_factory, _BATCH_RECOLOUR_SCHEMA
        )
    if not is_registered(OP_PROCGEN):
        register_command(OP_PROCGEN, _procgen_factory, _PROCGEN_SCHEMA)


_register_builtins()

# Inject THIS module's trusted dispatcher into ``macro`` so ``macro.replay`` runs
# through it without a ``macro → scripting`` import (plan §4.4 acyclic edge).
macro.set_dispatcher(dispatch)
