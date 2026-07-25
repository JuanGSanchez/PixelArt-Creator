"""Macro model — data-driven DSL list + record / deterministic replay (zero Qt, S11).

A **macro is data**, never code (Article VII; ADR-0021): an ordered tuple of
:class:`Op` steps — ``{name, params, seed}`` — plus a versioned envelope. The
same artifact is a recorded macro, an authored script, and a CLI job (ADR-0022);
it is interpreted by the trusted dispatcher in :mod:`logic.scripting`, which maps
each ``name`` to an allow-listed reversible
:class:`~pixelart_creator.logic.history.Command` factory. **There is no
``eval``/``exec``/``compile`` anywhere on this path.**

Layering (plan §4.4 / ADR-0022 §6, FROZEN): this module owns the DSL *data types*
(``Op``, ``Macro``) and the record/replay entry points; it imports only
``history``, ``document`` and ``constants`` and **never imports ``scripting``**
(no back-edge). ``scripting`` imports *these* types (``scripting → macro``) and,
at its import time, injects its :func:`~pixelart_creator.logic.scripting.dispatch`
here via :func:`set_dispatcher` — so :func:`replay` runs through the one trusted
dispatcher without a module-level ``macro → scripting`` import (``check_cycles``
stays clean). This placement of ``Op`` (data model owner) rather than in
``scripting.py`` is the minimal way to honour the frozen acyclic edge; ``scripting``
re-exports ``Op`` so ``scripting.Op`` remains valid (see that module).

Determinism (REQ-P8-LOGIC-005): a replay is a pure function of
``(initial document, macro)`` — every stochastic op carries its recorded ``seed``,
and the built-in generators draw only from that seed; no wall-clock, no unseeded
RNG, no locale, no order-unstable iteration. Replaying the same macro on the same
initial document twice yields a state-identical document (the "replays to an
identical result" gate).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Optional, Sequence, Tuple

from pixelart_creator.logic.constants import MAX_MACRO_STEPS
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.history import Command

__all__ = [
    "MacroError",
    "Op",
    "Macro",
    "MACRO_SCHEMA_VERSION",
    "MIN_APP_VERSION",
    "OP_API_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "SUPPORTED_API_VERSIONS",
    "record",
    "replay",
    "set_dispatcher",
    "get_dispatcher",
]

#: Macro serialisation schema version — a module-local, format-intrinsic string
#: (ADR-0001 / BF-2 exemption, the ``BlendMode``/``PlaybackMode`` precedent). An
#: unknown/unsupported version fails loudly on load (``data.macro_io``).
MACRO_SCHEMA_VERSION: str = "1"

#: Minimum application version that can replay a macro written at the current
#: schema (Researcher Topic 2.5 — fail loudly across releases). Format-intrinsic.
MIN_APP_VERSION: str = "0.8.0"

#: Per-op API version stamped into a serialised macro so a v1 op replayed against
#: an incompatibly-changed op fails loudly rather than mis-replaying (ADR-0022 §1;
#: Researcher Topic 2.4). Format-intrinsic (validated by ``data.macro_io``).
OP_API_VERSION: str = "1"

#: Schema versions this build can load/replay.
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (MACRO_SCHEMA_VERSION,)

#: Per-op API versions this build can load/replay.
SUPPORTED_API_VERSIONS: Tuple[str, ...] = (OP_API_VERSION,)


class MacroError(ValueError):
    """Raised on an invalid macro, out-of-bounds step count, or replay failure."""


@dataclass(frozen=True)
class Op:
    """One DSL step: an allow-listed op ``name`` + resolved ``params`` + ``seed``.

    ``params`` MUST be JSON-native (``dict`` with ``str`` keys over ``int`` /
    ``float`` / ``str`` / ``bool`` / ``None`` / ``list`` / nested ``dict``) so a
    macro round-trips through ``data.macro_io`` to an **identical** :class:`Op`
    (no tuple/int-key drift). Colours and index maps are therefore carried as
    *lists* (e.g. ``[[r, g, b, a], ...]`` / ``[[src, dst], ...]``), which the
    built-in command factories convert on use. ``seed`` is required for any
    stochastic op (procedural generation) and captured so replay is deterministic
    (REQ-P8-LOGIC-005/-012).
    """

    name: str
    params: Mapping[str, object] = field(default_factory=dict)
    seed: Optional[int] = None


@dataclass(frozen=True)
class Macro:
    """A versioned, ordered DSL list — a recorded macro / script / CLI job."""

    schema_version: str
    min_app_version: str
    ops: Tuple[Op, ...]


#: The injected trusted dispatcher (set by ``logic.scripting`` at its import so
#: ``macro`` never imports ``scripting`` — no ``macro → scripting`` back-edge).
_Dispatch = Callable[[Document, Sequence[Op]], Command]
_dispatcher: Optional[_Dispatch] = None


def set_dispatcher(dispatcher: _Dispatch) -> None:
    """Register the trusted DSL dispatcher used by :func:`replay`.

    Called once by :mod:`logic.scripting` at import time (dependency injection —
    keeps the ``macro → scripting`` edge out of the import graph, plan §4.4). Not
    part of the public automation surface; the host imports ``scripting`` (which
    wires this) before replaying.
    """
    global _dispatcher
    _dispatcher = dispatcher


def get_dispatcher() -> _Dispatch:
    """Return the injected dispatcher, or raise if ``scripting`` was not imported.

    Raises:
        MacroError: If no dispatcher has been registered (import
            :mod:`pixelart_creator.logic.scripting` before replaying).
    """
    if _dispatcher is None:
        raise MacroError(
            "no DSL dispatcher registered; import pixelart_creator.logic.scripting "
            "before replaying a macro"
        )
    return _dispatcher


def record(ops: Iterable[Op]) -> Macro:
    """Capture an ordered :class:`Op` stream as a versioned :class:`Macro`.

    Records the *inputs* (each op's resolved params + captured seed), never a
    pixel diff (REQ-P8-LOGIC-004; Researcher Topic 2 — "capture inputs, not just
    operations"). The DSL ``Op`` is the recordable unit — a raw
    :class:`~pixelart_creator.logic.history.Command` is an opaque execute/undo
    pair with no recoverable op-name/params, so the session collects the ops it
    dispatched and passes them here (this is why the parameter is an ``Iterable``
    of :class:`Op`, not of ``Command`` — see the module docstring / report).

    Args:
        ops: The ordered DSL steps that were dispatched.

    Returns:
        A :class:`Macro` at the current schema, ready to serialise or replay.

    Raises:
        MacroError: If an item is not an :class:`Op`, or the step count exceeds
            :data:`~pixelart_creator.logic.constants.MAX_MACRO_STEPS`.
    """
    collected: list[Op] = []
    for step in ops:
        if not isinstance(step, Op):
            raise MacroError(f"macro step must be an Op, got {step!r}")
        collected.append(step)
        if len(collected) > MAX_MACRO_STEPS:
            raise MacroError(f"macro exceeds MAX_MACRO_STEPS ({MAX_MACRO_STEPS})")
    return Macro(
        schema_version=MACRO_SCHEMA_VERSION,
        min_app_version=MIN_APP_VERSION,
        ops=tuple(collected),
    )


def replay(document: Document, macro: Macro) -> Command:
    """Deterministically replay ``macro`` on ``document`` via the trusted dispatcher.

    Pure function of ``(document, macro)``: dispatches the ordered ops through
    :func:`~pixelart_creator.logic.scripting.dispatch` (the ONE trusted, allow-listed,
    ``eval``-free command path), applying each reversible command in order and
    returning **one grouped, already-applied**
    :class:`~pixelart_creator.logic.history.Command` (undoable — REQ-P8-LOGIC-006).
    Replaying the same macro on a fresh copy of the same initial document twice
    yields a state-identical result (REQ-P8-LOGIC-005) because every stochastic op
    carries its recorded ``seed`` and no wall-clock/unseeded-RNG/locale is used.

    Args:
        document: The subject document (mutated in place by the applied commands).
        macro: The recorded/loaded DSL list to replay.

    Returns:
        A grouped :class:`~pixelart_creator.logic.history.Command` for the whole
        replay (already applied; push with ``execute=False``).

    Raises:
        MacroError: If ``macro`` is not a :class:`Macro`, its schema is
            unsupported, or no dispatcher is registered.
        ScriptError: (from the dispatcher) on an unknown op, invalid params, or a
            bound breach.
    """
    if not isinstance(macro, Macro):
        raise MacroError(f"replay needs a Macro, got {macro!r}")
    if macro.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise MacroError(
            f"unsupported macro schema_version {macro.schema_version!r}; "
            f"supported: {SUPPORTED_SCHEMA_VERSIONS}"
        )
    dispatcher = get_dispatcher()
    return dispatcher(document, macro.ops)
