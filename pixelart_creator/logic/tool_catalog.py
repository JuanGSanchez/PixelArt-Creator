# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Safe tool-catalog + JSON-schema introspection over the DSL registry (zero Qt, S11).

**Article VII, by construction (ADR-0039).** This module is a *read-only*
introspection facade over the shipped Phase-8 allow-listed action surface
(:mod:`logic.scripting`). It enumerates the currently **registered** DSL ops and
projects each one to a provider-neutral **tool descriptor** — a ``name`` + a
human-readable ``description`` + a **JSON-schema** derived from the op's shipped
:class:`~pixelart_creator.logic.scripting.ParamSchema` — so an external LLM's
function-calling surface can *select* an op and *fill typed args* (the peer-reviewed
"action-selector" pattern, Researcher ``ad2616c7`` R5.1). It adds **no** new
executable op and **no** new registration path: an op is a tool **iff**
:func:`scripting.is_registered`, so built-ins **and** consent-gated, namespaced
plugin ops (``"<plugin>.<op>"``, PLG-1) are tracked automatically with no second
list to drift (REQ-P14-LOGIC-001).

The reverse direction (REQ-P14-LOGIC-003) maps an incoming, provider-normalized
tool-call — :class:`ToolCall` (``{name, arguments}``) — onto a single
:class:`~pixelart_creator.logic.macro.Op` and executes it **only** through the shipped
trusted :func:`~pixelart_creator.logic.scripting.dispatch`: the op-name is checked
against the allow-list and the params/seed against the op's ``ParamSchema``, applied
as one reversible :class:`~pixelart_creator.logic.history.GroupCommand`, rolled back
atomically on failure. **The projected JSON-schema is advisory to the model;
``ParamSchema.validate`` + ``dispatch`` remain the authoritative gate** — the
projection **never widens** what dispatch accepts (ADR-0039 §5). A tool-call naming a
non-registered op, or carrying invalid/mistyped params, raises
:class:`~pixelart_creator.logic.scripting.ScriptError` and leaves the document
**byte/state-identical** (the shipped Phase-1 validate-then-apply atomicity). **The
LLM has no path to any op outside the registry**, because enforcement lives in
``logic/``, not in the projection or the prompt. **There is no ``eval``/``exec``/
``compile``/``__import__`` anywhere on this path** — model output is data mapped to
allow-listed factories (REQ-P14-LOGIC-008).

Layering (plan §11 / ADR-0039 §1, FROZEN): a pure ``logic`` leaf importing only
``scripting`` (the registry + dispatch), ``macro`` (the ``Op`` data type), ``document``
and ``history`` (signature types). **Zero Qt; no ``data``/``ui`` import.** The
per-op description table is module-local vocabulary (ADR-0001 / BF-2), not a numeric
constant. This facade carries no numeric caps (those are the 14C assistant loop's,
``logic/constants.py``); it introduces no numeric literal (Article II).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple, Union, cast

from pixelart_creator.logic import scripting
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.scripting import ParamSchema, ScriptError

__all__ = [
    "ToolCatalogError",
    "ToolDescriptor",
    "ToolCall",
    "SEED_PROPERTY",
    "build_tool_catalog",
    "param_schema_to_json_schema",
    "to_op",
    "execute_tool_call",
]

#: The explicit JSON-schema property name the routed ``macro.Op.seed`` sibling is
#: surfaced under (ADR-0039 §3/§4). It is peeled back off :class:`ToolCall.arguments`
#: into ``Op.seed`` on the way to dispatch — never treated as a normal param field.
SEED_PROPERTY = "seed"

#: Python-type -> JSON-schema ``type`` name (ADR-0039 §3, FROZEN). Keyed by exact
#: type identity, so ``bool`` maps to ``"boolean"`` and ``int`` to ``"integer"``
#: independently (JSON-schema ``"integer"`` excludes booleans, mirroring
#: ``ParamSchema``'s explicit ``bad_bool`` rejection — a faithful, non-widening map).
_JSON_SCHEMA_TYPES: Mapping[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}

#: Human-readable per-op descriptions the model reads as the op's contract
#: (ADR-0039 §2). Module-local vocabulary (ADR-0001 / BF-2), NOT a constant — it is
#: not a numeric. An op absent from this table (e.g. a namespaced plugin op) falls
#: back to :func:`_describe`'s generic string, so the catalog never drifts.
_OP_DESCRIPTIONS: Mapping[str, str] = {
    scripting.OP_BATCH_RECOLOUR: (
        "Recolour pixels across one or more layers by mapping source palette "
        "indices or source RGBA colours to destination colours. Reversible and "
        "undo-backed."
    ),
    scripting.OP_PROCGEN: (
        "Generate procedural pixel content on the document using a named, seeded "
        "algorithm (algorithm-specific knobs are accepted). Reversible and "
        "undo-backed; requires an integer seed for deterministic replay."
    ),
}

#: Description for the routed ``seed`` property (ADR-0039 §3).
_SEED_DESCRIPTION = (
    "Optional integer random seed routed to the operation for deterministic, "
    "reproducible results; required for stochastic operations."
)


class ToolCatalogError(ValueError):
    """Raised when an op's ``ParamSchema`` cannot be faithfully projected.

    A guard for the ADR-0039 §5 non-widening invariant: if a (future)
    ``ParamSchema`` field carries a type with no JSON-schema mapping, the facade
    fails **loudly** here rather than emitting a schema that would out-permit
    ``ParamSchema.validate``. It is *not* the tool-call rejection error — an
    unknown/invalid tool-call is rejected by :func:`scripting.dispatch` with
    :class:`~pixelart_creator.logic.scripting.ScriptError`.
    """


@dataclass(frozen=True)
class ToolDescriptor:
    """A provider-neutral tool definition for LLM function-calling (ADR-0039 §2).

    ``parameters`` is a JSON-schema **object** dict — a faithful projection of the
    op's shipped :class:`~pixelart_creator.logic.scripting.ParamSchema` (see
    :func:`param_schema_to_json_schema`). The adapters (14D) wrap the *identical*
    ``parameters`` dict per provider; the dict itself is provider-agnostic.
    """

    name: str
    description: str
    parameters: Mapping[str, object]


@dataclass(frozen=True)
class ToolCall:
    """One provider-normalized tool-call: an op ``name`` + JSON ``arguments``.

    Produced by an adapter from a provider's function-call/tool-use payload
    (ADR-0039 §7) and mapped to a single :class:`~pixelart_creator.logic.macro.Op`
    by :func:`to_op`. ``arguments`` is a JSON object; a routed ``"seed"`` member (if
    present) becomes :attr:`Op.seed`, every other member becomes an ``Op.params``
    entry. It is executed **only** through the trusted dispatch
    (:func:`execute_tool_call`).
    """

    name: str
    arguments: Mapping[str, object] = field(default_factory=dict)


def _registered_schema(name: str) -> ParamSchema:
    """Return the shipped :class:`ParamSchema` for a registered op (read-only).

    Binds to the public :func:`scripting.schema_for` introspection seam (paired with
    ``registered_ops()``/``is_registered``), so the facade never reaches into the
    allow-list registry (read-only — ADR-0039 §1; spec REQ-P14-LOGIC-001). It mutates
    nothing and adds no registration path. A miss (``name`` absent from the registry —
    it should not be, callers pass names from :func:`scripting.registered_ops`) is
    re-raised as :class:`ToolCatalogError` for consistency with the projection's
    fail-loud contract rather than surfaced as a raw ``ScriptError``.

    Raises:
        ToolCatalogError: If ``name`` is not in the allow-list registry.
    """
    try:
        return scripting.schema_for(name)
    except ScriptError as exc:
        raise ToolCatalogError(f"op {name!r} is not in the DSL registry") from exc


def _describe(name: str) -> str:
    """Return the human-readable description for ``name`` (table, else generic)."""
    return _OP_DESCRIPTIONS.get(name, f'Registered pixel-art DSL operation "{name}".')


def _json_type_name(python_type: type) -> str:
    """Map one Python type to its JSON-schema type name (ADR-0039 §3).

    Raises:
        ToolCatalogError: If ``python_type`` has no JSON-schema mapping (would break
            the non-widening invariant — fail loudly, ADR-0039 §5 / Consequences).
    """
    try:
        return _JSON_SCHEMA_TYPES[python_type]
    except KeyError:
        raise ToolCatalogError(
            f"cannot project param type {python_type!r} to a JSON-schema type"
        ) from None


def _project_type(expected: Union[type, Tuple[type, ...]]) -> Union[str, List[str]]:
    """Project a ``ParamSchema`` field type (or tuple union) to a schema ``type``.

    A single type maps to a string; a tuple of accepted types maps to a JSON-schema
    type **array** (union), e.g. ``(int, float)`` -> ``["integer", "number"]``.
    """
    if isinstance(expected, tuple):
        return [_json_type_name(member) for member in expected]
    return _json_type_name(expected)


def param_schema_to_json_schema(schema: ParamSchema) -> Dict[str, object]:
    """Project a shipped :class:`ParamSchema` to the FROZEN JSON-schema subset.

    Faithful projection (ADR-0039 §3, DEP-2) — a provider-neutral JSON-Schema subset
    (compatible with draft-07 and 2020-12; **no** ``$schema`` key). The emitted object
    is ``{"type": "object", "properties": {...}, "required": [...],
    "additionalProperties": <bool>}`` where:

    * ``fields`` -> ``properties`` via the frozen type map (:func:`_project_type`);
    * ``required`` -> ``required`` verbatim;
    * ``allow_extra`` -> ``additionalProperties`` (``False`` = strict);
    * the routed ``"seed"`` sibling is always declared as an explicit integer
      property (typed + documented), and added to ``required`` **iff**
      ``requires_seed`` (ADR-0039 §3).

    **Non-widening invariant (ADR-0039 §5):** every keyword is derived from the same
    ``ParamSchema``, so ``{arguments this schema permits}`` (after seed routing) is a
    subset of ``{arguments ParamSchema.validate accepts}``. Where the projection is
    *stricter* (``additionalProperties: false``) that only helps the model, and
    ``dispatch`` remains the final arbiter. It never emits a keyword looser than
    ``validate``.

    Args:
        schema: The op's shipped defensive :class:`ParamSchema`.

    Returns:
        A JSON-schema object dict (the value of ``ToolDescriptor.parameters``).

    Raises:
        ToolCatalogError: If a field type has no JSON-schema mapping (fail loudly).
    """
    properties: Dict[str, object] = {}
    for field_name, expected in schema.fields.items():
        properties[field_name] = {"type": _project_type(expected)}

    # The seed is a sibling of params on macro.Op (never a param field). Declare it
    # explicitly so it is typed + documented, and route it back to Op.seed (to_op).
    # It is faithful: ParamSchema.validate accepts an int seed for ANY op; only its
    # *presence* is mandated when requires_seed is set (ADR-0039 §3/§4).
    properties[SEED_PROPERTY] = {
        "type": "integer",
        "description": _SEED_DESCRIPTION,
    }
    required: List[str] = list(schema.required)
    if schema.requires_seed:
        required.append(SEED_PROPERTY)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": schema.allow_extra,
    }


def build_tool_catalog() -> Tuple[ToolDescriptor, ...]:
    """Enumerate the allow-listed DSL registry as provider-neutral tool descriptors.

    Read-only over :func:`scripting.registered_ops` — one :class:`ToolDescriptor` per
    currently registered op, in the registry's sorted order. An op is a tool **iff**
    it is registered, so built-ins **and** consent-gated namespaced plugin ops
    (``"<plugin>.<op>"``, PLG-1) are tracked automatically; rebuilding after a plugin
    enables/disables reflects the change with no separate list to drift
    (REQ-P14-LOGIC-001; SC-L001-1/-2). Introduces **no** new executable op and **no**
    new registration path.

    Returns:
        The tuple of tool descriptors for the current allow-list.

    Raises:
        ToolCatalogError: If a registered op's ``ParamSchema`` cannot be projected.
    """
    return tuple(
        ToolDescriptor(
            name=name,
            description=_describe(name),
            parameters=param_schema_to_json_schema(_registered_schema(name)),
        )
        for name in scripting.registered_ops()
    )


def to_op(call: ToolCall) -> Op:
    """Map a provider tool-call onto a single :class:`~pixelart_creator.logic.macro.Op`.

    Deterministic mapping (ADR-0039 §4, FROZEN): the routed ``"seed"`` member is
    peeled off :attr:`ToolCall.arguments` into :attr:`Op.seed` (whatever
    ``allow_extra`` is), and every other member becomes an ``Op.params`` entry. No
    validation happens here — that is the trusted :func:`scripting.dispatch`'s job
    (:func:`execute_tool_call`); this is a pure data mapping (no ``eval``/``exec``).

    Args:
        call: The provider-normalized tool-call.

    Returns:
        The single :class:`~pixelart_creator.logic.macro.Op` the call denotes.

    Raises:
        ScriptError: If ``arguments`` is not a mapping (defensive IO-3 guard, so a
            malformed call is rejected as a domain error rather than crashing before
            it reaches the trusted dispatch).
    """
    arguments = call.arguments
    if not isinstance(arguments, Mapping):
        raise ScriptError(f"tool-call arguments must be a mapping, got {arguments!r}")
    seed = arguments.get(SEED_PROPERTY)
    params = {key: value for key, value in arguments.items() if key != SEED_PROPERTY}
    # `seed` is routed verbatim to Op.seed; scripting.dispatch's ParamSchema.validate
    # is the authority that it is an int (ADR-0039 §4) — cast is descriptive, not a
    # check (the projected schema is advisory; dispatch is the gate).
    return Op(name=call.name, params=params, seed=cast(Optional[int], seed))


def execute_tool_call(document: Document, call: ToolCall) -> Command:
    """Execute a tool-call **only** through the trusted dispatch (REQ-P14-LOGIC-003).

    Maps the call to one :class:`~pixelart_creator.logic.macro.Op` (:func:`to_op`) and
    runs it through the shipped :func:`scripting.dispatch` — the single validated
    path: the op-name is checked against the allow-list and the params/seed against
    the op's ``ParamSchema``, applied as one already-applied reversible
    :class:`~pixelart_creator.logic.history.GroupCommand`, rolled back atomically on
    failure. **The projected JSON-schema is advisory; this dispatch is the
    authoritative gate.**

    A tool-call naming a **non-registered / forbidden** op, or carrying
    **invalid/mistyped/extra** params, raises
    :class:`~pixelart_creator.logic.scripting.ScriptError` in dispatch's up-front
    validate phase, leaving the document **byte/state-identical** to before the call
    (no partial apply — SC-L003-1/-2). A valid call applies as one undoable group
    (SC-L003-3). The LLM has no path to any op outside ``_REGISTRY``.

    Args:
        document: The subject document (mutated in place on a valid call).
        call: The provider-normalized tool-call to execute.

    Returns:
        The grouped, already-applied
        :class:`~pixelart_creator.logic.history.Command` for the call (push with
        ``execute=False``; ``ui.commands`` wraps it as one ``QUndoCommand``).

    Raises:
        ScriptError: On an unknown op, invalid/extra params, a bad seed, or a
            per-run bound breach. On any such raise the document is unchanged.
    """
    op = to_op(call)
    return scripting.dispatch(document, [op])
