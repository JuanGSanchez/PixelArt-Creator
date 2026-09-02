# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Assistant conversation value types + the ``ChatBackend`` bridge (zero Qt, S11).

Part of the AI-assistant feature, Phase 14 (ADR-0040 §2; spec REQ-P14-DATA-001).
This module single-sources the **wire-neutral vocabulary** the model-agnostic
assistant speaks — the normalized,
pure-``logic`` value types (:class:`Role`, :class:`Message`, :class:`Conversation`,
:class:`AssistantReply`) and the PEP 544 :class:`ChatBackend` **Protocol** the (14C)
agentic loop is typed against.

**The layering bridge (ADR-0040 §2, CENTRAL).** The agentic loop lives in ``logic/``
but must call an LLM adapter that lives in ``data/llm/``. ``logic/`` must not import
``data/`` (Article I). Resolution: the loop depends only on the ``ChatBackend``
*Protocol* defined here and receives a concrete backend by **dependency injection**.
``data/llm/port.py``'s :class:`~pixelart_creator.data.llm.port.LLMPort` (a ``data →
logic`` import, allowed) **structurally satisfies** ``ChatBackend`` — so the vocabulary
is single-sourced in ``logic/``, the loop stays ``data/``-free, and adapters are
injected. No ``logic → data`` edge, no cycle.

:class:`~pixelart_creator.logic.tool_catalog.ToolCall` and
:class:`~pixelart_creator.logic.tool_catalog.ToolDescriptor` are the FROZEN 14A
tool-schema contract (ADR-0039); they are re-exported here so callers have one import
site for the whole assistant vocabulary. A **tool result** fed back to the model is a
:class:`Message` with :attr:`Role.TOOL` — plain **data**; the port never executes it
and the type enables no privilege escalation (Article VII; execution is the 14C loop's
trusted-dispatch path through 14A only).

**Slice scope.** This module now carries BOTH the 14B value types + ``ChatBackend``
Protocol **and** the 14C security core (ADR-0041): the bounded agentic loop
(:func:`run_turn` / :class:`AssistantSession`), the tiered-reversibility gate
(:class:`Reversibility` / :data:`REVERSIBLE_OPS` / :func:`classify_op`), and the
prompt-injection / untrusted-tool-result defence (:func:`bound_tool_result` + the named
caps in :mod:`~pixelart_creator.logic.constants`). It imports only ``logic`` leaves
(``tool_catalog``, ``scripting``, ``document``, ``history``, ``constants``) — **no**
``data/`` import (the LLM adapter is injected as a :class:`ChatBackend`, ADR-0040 §2)
and **zero Qt**. There is **no** ``eval``/``exec``/``compile``/``__import__`` anywhere:
model output is *data* (:class:`Message` / :class:`ToolCall`) and the ONLY execution
path is :func:`~pixelart_creator.logic.tool_catalog.execute_tool_call` → the shipped
allow-listed trusted dispatch (Article VII, REQ-P14-LOGIC-008).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Callable,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from pixelart_creator.logic import scripting
from pixelart_creator.logic.constants import (
    MAX_ASSISTANT_TURNS,
    MAX_CONVERSATION_MESSAGES,
    MAX_TOOL_CALLS_PER_TURN,
    MAX_TOOL_RESULT_BYTES,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.tool_catalog import (
    ToolCall,
    ToolDescriptor,
    build_tool_catalog,
    execute_tool_call,
)

__all__ = [
    "Role",
    "Message",
    "Conversation",
    "AssistantReply",
    "ChatBackend",
    "ToolCall",
    "ToolDescriptor",
    "AssistantError",
    "Reversibility",
    "REVERSIBLE_OPS",
    "classify_op",
    "ConfirmationRequest",
    "ConfirmCallback",
    "deny_all",
    "bound_tool_result",
    "TurnResult",
    "run_turn",
    "AssistantSession",
]


class Role(str, Enum):
    """The author of a :class:`Message`, provider-neutral (ADR-0040 §2).

    Maps onto every provider's role vocabulary: ``SYSTEM``/``USER``/``ASSISTANT`` are
    universal; ``TOOL`` is the result of a tool-call fed back to the model (OpenAI's
    ``role="tool"`` message, Anthropic's ``tool_result`` content block — the adapter
    translates). Subclasses ``str`` so a role is JSON-friendly and compares equal to
    its wire literal.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class Message:
    """One normalized, immutable conversation message (provider-neutral).

    A single value type covers every role. Which fields are meaningful depends on
    :attr:`role`:

    * ``SYSTEM``/``USER`` — :attr:`content` only.
    * ``ASSISTANT`` — :attr:`content` (a final natural-language reply) and/or
      :attr:`tool_calls` (the model requesting one-or-more tool invocations).
    * ``TOOL`` — a tool **result** fed back to the model: :attr:`content` is the
      (untrusted, to be bounded by the 14C loop) result text, :attr:`tool_call_id`
      identifies which :class:`ToolCall` it answers, and :attr:`name` is the op name.

    The type is a pure data container; it holds no provider/HTTP/credential detail and
    performs no execution (Article VII — a tool result is data, never a privilege).
    """

    role: Role
    content: str = ""
    #: For ``ASSISTANT`` messages: the tool-calls the model requested this turn.
    tool_calls: Tuple[ToolCall, ...] = ()
    #: For ``TOOL`` messages: the id of the tool-call this result answers (if any).
    tool_call_id: Optional[str] = None
    #: For ``TOOL`` messages: the op name the result came from (if any).
    name: Optional[str] = None


@dataclass(frozen=True)
class Conversation:
    r"""An ordered, immutable sequence of :class:`Message`\\ s (provider-neutral).

    The unit the port receives on every turn (:meth:`ChatBackend.respond`). Mutation
    returns a *new* ``Conversation`` (frozen — deterministic, safe to share), mirroring
    the immutable-history idiom elsewhere in ``logic/``.
    """

    messages: Tuple[Message, ...] = ()

    def append(self, message: Message) -> "Conversation":
        """Return a new conversation with ``message`` appended."""
        return Conversation(messages=self.messages + (message,))

    def extend(self, messages: Sequence[Message]) -> "Conversation":
        """Return a new conversation with ``messages`` appended in order."""
        return Conversation(messages=self.messages + tuple(messages))


@dataclass(frozen=True)
class AssistantReply:
    """The port's normalized reply for one turn (ADR-0040 §2/§3).

    Exactly one of two shapes, per the model-agnostic contract: either a **final
    assistant message** (:attr:`tool_calls` empty, :attr:`is_final` true) or a request
    for **one-or-more tool-calls** (:attr:`tool_calls` non-empty). :attr:`message` may
    accompany tool-calls as the model's interim narration; it is never required for a
    tool-call turn.
    """

    message: Optional[Message] = None
    tool_calls: Tuple[ToolCall, ...] = field(default_factory=tuple)

    @property
    def is_final(self) -> bool:
        """Whether this reply is a final answer (no tool-calls requested)."""
        return not self.tool_calls

    @classmethod
    def final(cls, content: str) -> "AssistantReply":
        """Build a final-answer reply carrying an assistant :class:`Message`."""
        return cls(message=Message(role=Role.ASSISTANT, content=content))

    @classmethod
    def calling(cls, *calls: ToolCall, content: str = "") -> "AssistantReply":
        """Build a tool-call reply requesting ``calls`` (with optional narration)."""
        message = (
            Message(role=Role.ASSISTANT, content=content, tool_calls=tuple(calls))
            if content
            else None
        )
        return cls(message=message, tool_calls=tuple(calls))


@runtime_checkable
class ChatBackend(Protocol):
    """The abstraction the (14C) agentic loop is typed against (ADR-0040 §2).

    Structural (PEP 544) — any object exposing these two methods is a backend, so
    ``data/llm/``'s :class:`~pixelart_creator.data.llm.port.LLMPort` satisfies it
    without ``logic/`` importing ``data/``. The loop receives a backend by dependency
    injection and never names a provider.
    """

    def respond(
        self, conversation: Conversation, tools: Sequence[ToolDescriptor]
    ) -> AssistantReply:
        """Given the conversation + tools, return one :class:`AssistantReply`."""
        ...

    def is_configured(self) -> bool:
        """Whether the backend is ready to serve requests (no credential exposed)."""
        ...


# ==========================================================================================
# The security core: agentic loop + tiered-safety gate + injection defence
# (ADR-0041; spec REQ-P14-LOGIC-004/-005/-006/-007/-008). Everything below is pure
# ``logic`` — deterministic given a fixed ``ChatBackend``, zero Qt, no ``data/`` import,
# no ``eval``/``exec``/``compile``/``__import__``.
# ==========================================================================================


class AssistantError(ValueError):
    """Raised on a bounded-loop breach (Article II/VII bounded-halt, ADR-0041 §1/§4).

    A domain error (``ValueError`` subclass, the ``ScriptError``/``LLMError`` precedent)
    raised when a numeric bound is exceeded — too many turns
    (:data:`~pixelart_creator.logic.constants.MAX_ASSISTANT_TURNS`), too many tool-calls
    in one turn (:data:`~pixelart_creator.logic.constants.MAX_TOOL_CALLS_PER_TURN`), or
    a
    transcript past :data:`~pixelart_creator.logic.constants.MAX_CONVERSATION_MESSAGES`.
    It is the bounded-halt signal (SC-L005-2): the loop terminates loudly rather than
    looping unbounded or degrading silently.

    It is **not** raised for a rejected/declined tool-call — an unknown/forbidden op, an
    op with invalid args, or a destructive op the caller declined is surfaced as a
    ``Role.TOOL`` result message (data) fed back into the conversation, and the loop
    continues (the document is left byte/state-identical for a rejected op, SC-L006-1).

    **Turn atomicity — the error-path partial-apply contract (ADR-0041 §1 amendment).**
    A turn is atomic: on error it must be as revertable as a single rejected tool-call
    (which already leaves the document byte-identical, SC-L006-1). If a turn applies
    ≥1 reversible tool-call command and *then* fails mid-turn — a later bound breach, a
    transcript overflow, an ``LLMError`` from the injected backend, or any other error
    raised after a partial apply — :func:`run_turn` guarantees the failure surfaces as
    an ``AssistantError`` whose :attr:`applied_commands` holds the **ordered tuple of
    already-applied** :class:`~pixelart_creator.logic.history.Command` objects. This is
    the SINGLE, consistent handle the caller uses to make the turn atomic: revert them
    in reverse (``apply ∘ undo = identity`` → byte-identical), or record them as one
    undo step. :func:`run_turn` does **not** auto-revert — it only exposes the handle;
    the caller decides revert-vs-record. When a non-``AssistantError`` (e.g. an
    ``LLMError``) is raised mid-turn *after* a partial apply, it is wrapped in an
    ``AssistantError`` carrying both the original cause (``__cause__``, via ``raise …
    from``) and :attr:`applied_commands`, so the caller has exactly one error type to
    catch and one attribute to read. :attr:`applied_commands` defaults to the empty
    tuple — for a breach with no prior apply (and thus nothing to revert), and on the
    success path it is irrelevant (:class:`TurnResult` carries the commands instead).
    """

    def __init__(
        self, *args: object, applied_commands: Tuple[Command, ...] = ()
    ) -> None:
        """Build the error, optionally carrying the turn's applied commands.

        Args:
            *args: The usual ``ValueError`` message args.
            applied_commands: The ordered, already-applied undoable commands the failing
                turn produced before it errored (empty when nothing had been applied).
        """
        super().__init__(*args)
        #: The ordered tuple of undoable commands applied before the turn failed; the
        #: caller reverts/records these to keep the turn atomic (see class docstring).
        self.applied_commands: Tuple[Command, ...] = tuple(applied_commands)


# ------------------------------------------------------------------------------------------
# Tiered safety — reversibility classification (DEP-3, FROZEN) (REQ-P14-LOGIC-004)
# ------------------------------------------------------------------------------------------


class Reversibility(Enum):
    """The safety tier of a tool-call (module-local vocabulary, ADR-0001/BF-2).

    Not a numeric constant — an enumerated policy vocabulary (the ``BlendMode``/
    ``PlaybackMode`` precedent). Drives the tiered gate (ADR-0041 §2): a
    :attr:`REVERSIBLE` op **auto-runs** (undo-backed, no prompt); a :attr:`DESTRUCTIVE`
    op is **gate-closed** — it requires explicit caller confirmation before dispatch.
    """

    REVERSIBLE = "reversible"
    DESTRUCTIVE = "destructive"


#: The explicit, source-auditable allow-list of op-names classified :attr:`REVERSIBLE`
#: (ADR-0041 §2, FROZEN). An op earns membership ONLY by proving its
#: :func:`~pixelart_creator.logic.scripting.dispatch` result is a single, cleanly
#: undoable :class:`~pixelart_creator.logic.history.GroupCommand` on the shipped HIS-1
#: undo stack. The two shipped built-ins qualify — ``batch_recolour`` and ``procgen``
#: both apply as one reversible group (verified by SC-L003-3 / SC-L004-1). Everything
#: NOT in this set (unknown/future built-ins, and every namespaced plugin op
#: ``"<plugin>.<op>"``) is DESTRUCTIVE by default — the gate-defaults-closed posture
#: (Article VIII): a genuinely destructive op added later cannot silently auto-run by
#: omission. Extending this set is a one-line, reviewed, tested change.
REVERSIBLE_OPS: frozenset[str] = frozenset(
    {scripting.OP_BATCH_RECOLOUR, scripting.OP_PROCGEN}
)


def classify_op(name: str) -> Reversibility:
    """Classify an op-name into its safety tier (pure, deterministic, logic-level).

    The reversibility-classification mechanism (DEP-3, ADR-0041 §2) — never the prompt,
    never the model's discretion. An op-name in :data:`REVERSIBLE_OPS` is
    :attr:`Reversibility.REVERSIBLE`; **everything else is
    :attr:`Reversibility.DESTRUCTIVE` by default** (the fail-safe, gate-defaults-closed
    posture — SC-L004-2). Source-auditable and trivially unit-testable.

    Args:
        name: The op-name from an incoming :class:`ToolCall` (built-in or namespaced
            plugin op, or an entirely unknown name).

    Returns:
        :attr:`Reversibility.REVERSIBLE` iff ``name`` is in the allow-list, else
        :attr:`Reversibility.DESTRUCTIVE`.
    """
    return (
        Reversibility.REVERSIBLE
        if name in REVERSIBLE_OPS
        else Reversibility.DESTRUCTIVE
    )


# ------------------------------------------------------------------------------------------
# The data-level pending-confirmation protocol (ADR-0041 §2; SC-L004-2/-3, SC-D008-2)
# ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfirmationRequest:
    """A pending destructive action presented to the caller for approve/deny (data).

    The **data-level** confirmation protocol (ADR-0041 §2): when the tiered gate meets a
    :attr:`Reversibility.DESTRUCTIVE` tool-call, the loop does **not** execute it; it
    hands this immutable request to the injected :data:`ConfirmCallback` and dispatches
    **only** if the callback returns ``True``. The confirm surface (the 14E dock's
    confirm/cancel dialog, the 14F CLI's ``--yes``/prompt affordance) reads
    :attr:`tool_call` to **name the exact action** to the user and renders the gate's
    decision — it can never *relax* it (confirming an op the gate never withheld, or
    escalating a reversible op, is not expressible). :attr:`reversibility` is always
    :attr:`Reversibility.DESTRUCTIVE` (a request is raised for no other tier).
    """

    tool_call: ToolCall
    reversibility: Reversibility


#: The caller's approve/deny decision for a pending destructive action. Given a
#: :class:`ConfirmationRequest`, return ``True`` to approve dispatch, ``False`` to
#: decline. This is the **signal into the loop** (ADR-0041 §2) — a UI confirm in 14E, an
#: explicit ``--yes``/confirm affordance in the 14F CLI — never a prompt asking the
#: model
#: to behave. It is invoked at most once per destructive call, before any dispatch.
ConfirmCallback = Callable[[ConfirmationRequest], bool]


def deny_all(request: ConfirmationRequest) -> bool:  # noqa: ARG001 - protocol shape
    """Decline every destructive action; the default :data:`ConfirmCallback`.

    The gate-defaults-closed default (Article VIII, ADR-0041 §2): a loop driven without
    an explicit confirm decision NEVER auto-runs a destructive op — it declines it
    safely. A caller that wants destructive ops to run MUST supply a real
    :data:`ConfirmCallback` (a UI confirm, a CLI ``--yes``).
    """
    return False


# ------------------------------------------------------------------------------------------
# Prompt-injection / untrusted-tool-result defence (REQ-P14-LOGIC-006)
# ------------------------------------------------------------------------------------------


def bound_tool_result(text: str) -> str:
    """Bound one untrusted tool-result to :data:`MAX_TOOL_RESULT_BYTES` (ADR-0041 §3).

    A tool-result fed back to the model is **untrusted input** (the prompt-injection
    surface — OWASP LLM 2026 #1). This truncates ``text`` to a UTF-8-safe prefix no
    longer than :data:`~pixelart_creator.logic.constants.MAX_TOOL_RESULT_BYTES`
    **bytes**
    (decoding with ``errors="ignore"`` so a split multi-byte char at the boundary is
    dropped, never emitted malformed), so an oversized/malicious result can never
    exhaust
    memory/context (SC-L006-3). The returned string is guaranteed ``<=
    MAX_TOOL_RESULT_BYTES``
    bytes when UTF-8-encoded.

    Bounding is the **secondary** defence; the primary is structural — a result is inert
    data (a ``Role.TOOL`` :class:`Message`) with no execution path, so no result content
    can invoke a non-whitelisted op or bypass the tiered gate (§below; SC-L006-1/-2).

    Args:
        text: The candidate tool-result content (a dispatch summary, an error string, or
            any content carried back).

    Returns:
        ``text`` unchanged if already within bound, else its UTF-8-safe truncated
        prefix.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_TOOL_RESULT_BYTES:
        return text
    return encoded[:MAX_TOOL_RESULT_BYTES].decode("utf-8", errors="ignore")


def _tool_result_message(call: ToolCall, text: str) -> Message:
    """Build a bounded, untrusted ``Role.TOOL`` result message for ``call`` (data).

    Every result re-entering the conversation is bounded by :func:`bound_tool_result`.
    The message carries the op :attr:`~Message.name` so the model/transcript can pair it
    with the call; it holds NO privilege — it is data the next
    :meth:`ChatBackend.respond`
    reads, never an instruction the loop obeys.
    """
    return Message(role=Role.TOOL, content=bound_tool_result(text), name=call.name)


# ------------------------------------------------------------------------------------------
# The bounded agentic loop (REQ-P14-LOGIC-005) + turn result
# ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnResult:
    """The outcome of one bounded :func:`run_turn` (immutable, provider-neutral).

    Carries the full updated :attr:`conversation` transcript (user + assistant + bounded
    tool-result messages), the terminating :attr:`reply` (the final assistant
    :class:`Message`), and the ordered :attr:`commands` — the already-applied, undoable
    :class:`~pixelart_creator.logic.history.Command` groups produced by every op the
    loop
    ran this turn. The caller pushes each command onto its undo stack (the 14E dock
    wraps
    each as one ``QUndoCommand``; the 14F CLI saves the mutated document); a turn that
    ran
    no op has an empty :attr:`commands`.
    """

    conversation: Conversation
    reply: Message
    commands: Tuple[Command, ...] = ()


def _guard_transcript(conversation: Conversation) -> None:
    """Raise :class:`AssistantError` if the transcript exceeds its bound (SC-L005-2)."""
    if len(conversation.messages) > MAX_CONVERSATION_MESSAGES:
        raise AssistantError(
            "conversation message budget exceeded "
            f"({len(conversation.messages)} > {MAX_CONVERSATION_MESSAGES})"
        )


def _handle_tool_call(
    document: Document, call: ToolCall, confirm: ConfirmCallback
) -> Tuple[Message, Optional[Command]]:
    r"""Validate + gate + (maybe) dispatch ONE tool-call; return (result-msg, command).

    The full per-call gate (ADR-0041 §2/§3), in order:

    1. **Validate against the 14A catalog.** If ``call.name`` is not a registered
       allow-listed op (an unknown/forbidden tool — e.g. a follow-up ``wipe_disk``
       injected via a hostile tool-result), it is **rejected safely and never
       executed**:
       an error :class:`Message` is returned and the document is byte/state-identical
       (SC-L006-1). No confirmation is even sought for a tool that cannot exist.
    2. **Tiered classify** (:func:`classify_op`). A :attr:`Reversibility.DESTRUCTIVE`
       call is **gate-closed**: a :class:`ConfirmationRequest` is handed to ``confirm``;
       on deny the op is **not** dispatched (neither applied nor silently skipped past
       the
       gate) — a "declined" result is returned (SC-L004-2, SC-L006-2). A
       :attr:`Reversibility.REVERSIBLE` call auto-runs without prompting (SC-L004-1).
    3. **Dispatch** the permitted call **only** through the trusted
       :func:`~pixelart_creator.logic.tool_catalog.execute_tool_call` (the single
       allow-listed execution path — Article VII). A
       :class:`~pixelart_creator.logic.scripting.ScriptError` (invalid/extra/mistyped
       args, bad seed) is caught and surfaced as a bounded error result with the
       document
       left byte/state-identical (validate-then-apply atomicity) — SC-L003-1/-2.

    Returns:
        A ``(Role.TOOL`` result :class:`Message`, applied
        :class:`~pixelart_creator.logic.history.Command` or ``None``\\ ) pair. The
        command
        is non-``None`` **iff** an op actually applied.
    """
    if not scripting.is_registered(call.name):
        return (
            _tool_result_message(
                call,
                f'Rejected: "{call.name}" is not an available tool; nothing was run.',
            ),
            None,
        )

    if classify_op(call.name) is Reversibility.DESTRUCTIVE:
        request = ConfirmationRequest(
            tool_call=call, reversibility=Reversibility.DESTRUCTIVE
        )
        if not confirm(request):
            return (
                _tool_result_message(
                    call,
                    f'The action "{call.name}" was declined and was not run.',
                ),
                None,
            )

    try:
        command = execute_tool_call(document, call)
    except scripting.ScriptError as exc:
        return (
            _tool_result_message(call, f'Rejected "{call.name}": {exc}'),
            None,
        )
    return (
        _tool_result_message(call, f'Applied "{call.name}" (reversible, undoable).'),
        command,
    )


def run_turn(
    document: Document,
    conversation: Conversation,
    backend: ChatBackend,
    *,
    confirm: ConfirmCallback = deny_all,
    tools: Optional[Sequence[ToolDescriptor]] = None,
) -> TurnResult:
    """Drive one bounded agentic turn to a final assistant message (ADR-0041 §1).

    The pure, deterministic (given a fixed ``backend``) engine of the assistant. It
    presents ``conversation`` + the 14A tool catalog to the injected ``backend``, and on
    each returned tool-call applies the tiered gate then the trusted dispatch, feeding
    every result back as an untrusted, bounded ``Role.TOOL`` message — iterating until a
    final assistant message or a numeric bound is hit. It is **batch/off the 16 ms
    render
    loop** (Article VI; a model round-trip is not frame-gated).

    Injection resistance (SC-L006-*): a tool-result is inert data — the ONLY way an op
    runs is a subsequent ``AssistantReply.tool_calls``, and EVERY such call re-runs the
    full validate + classify + confirm + dispatch gate in :func:`_handle_tool_call`. No
    result content can invoke a non-whitelisted op or bypass the tiered gate; privilege
    is
    a property of the registry + gate in ``logic/``, never of conversation content.

    Args:
        document: The subject document (mutated in place by each applied op).
        conversation: The transcript so far, INCLUDING the user's new message (the
        caller
            / :class:`AssistantSession` appends it before calling).
        backend: The injected :class:`ChatBackend` (a ``data/llm`` ``LLMPort``, or the
            fake adapter in CI) — the loop never names a provider (ADR-0040 §2).
        confirm: The :data:`ConfirmCallback` consulted for every DESTRUCTIVE tool-call;
            defaults to :func:`deny_all` (gate-closed — destructive ops are declined
            unless the caller supplies a real decision).
        tools: The tool descriptors to present; defaults to a fresh
            :func:`~pixelart_creator.logic.tool_catalog.build_tool_catalog` (the current
            allow-list, incl. enabled plugin ops).

    Returns:
        A :class:`TurnResult` with the updated transcript, the final assistant message,
        and the ordered applied undoable commands.

    Raises:
        AssistantError: On a bounded breach — more than
            :data:`~pixelart_creator.logic.constants.MAX_ASSISTANT_TURNS` turns without
            a
            final message, a turn requesting more than
            :data:`~pixelart_creator.logic.constants.MAX_TOOL_CALLS_PER_TURN`
            tool-calls,
            or a transcript past
            :data:`~pixelart_creator.logic.constants.MAX_CONVERSATION_MESSAGES`
            (bounded-halt — SC-L005-2). **Error-path atomicity contract (ADR-0041 §1
            amendment):** if ≥1 reversible tool-call command was applied before the turn
            failed — for ANY reason, including a bound breach, a transcript overflow, or
            an ``LLMError`` propagated from ``backend.respond`` — the raised error is an
            ``AssistantError`` whose :attr:`AssistantError.applied_commands` holds the
            ordered tuple of already-applied
            :class:`~pixelart_creator.logic.history.Command` objects, so the caller can
            revert them (restore byte-identical) or record them as one undo step. A
            non-``AssistantError`` cause is wrapped (its original exception preserved as
            ``__cause__``) so the caller has ONE type to catch and ONE attribute to
            read. This function never auto-reverts — it only guarantees the handle is
            exposed; the caller decides revert-vs-record. When NO command had applied,
            the original error propagates unchanged (behaviour-neutral) and there is
            nothing to revert. The success path is unaffected (commands ride on
            :class:`TurnResult`, not the error).
    """
    catalog: Tuple[ToolDescriptor, ...] = (
        build_tool_catalog() if tools is None else tuple(tools)
    )
    commands: List[Command] = []

    try:
        for _turn in range(MAX_ASSISTANT_TURNS):
            _guard_transcript(conversation)
            reply = backend.respond(conversation, catalog)

            assistant_msg = reply.message or Message(
                role=Role.ASSISTANT, content="", tool_calls=reply.tool_calls
            )
            conversation = conversation.append(assistant_msg)
            _guard_transcript(conversation)

            if reply.is_final:
                return TurnResult(
                    conversation=conversation,
                    reply=assistant_msg,
                    commands=tuple(commands),
                )

            calls = reply.tool_calls
            if len(calls) > MAX_TOOL_CALLS_PER_TURN:
                raise AssistantError(
                    "tool-call budget exceeded "
                    f"({len(calls)} > {MAX_TOOL_CALLS_PER_TURN})"
                )

            for call in calls:
                result_msg, command = _handle_tool_call(document, call, confirm)
                conversation = conversation.append(result_msg)
                _guard_transcript(conversation)
                if command is not None:
                    commands.append(command)

        raise AssistantError(
            f"assistant turn budget exceeded ({MAX_ASSISTANT_TURNS} turns without a "
            "final reply)"
        )
    except AssistantError as exc:
        # A bounded-halt (our own domain breach). If ops already applied this turn,
        # attach them so the caller can revert/record and keep the turn atomic
        # (ADR-0041 §1 amendment); the success return above is never reached here.
        if commands:
            exc.applied_commands = tuple(commands)
        raise
    except (
        Exception
    ) as exc:  # noqa: BLE001 - surface partial apply on ANY mid-turn error
        # A non-AssistantError raised mid-turn (e.g. an LLMError from backend.respond,
        # or any unexpected error after a tool-call applied). When ops already applied,
        # wrap in the single AssistantError type the caller catches, preserving the
        # original cause (__cause__) and exposing applied_commands so the turn stays
        # atomic. With nothing applied there is nothing to revert — propagate raw
        # (behaviour-neutral: the pre-fix error and type are unchanged).
        if commands:
            raise AssistantError(
                str(exc) or type(exc).__name__,
                applied_commands=tuple(commands),
            ) from exc
        raise


class AssistantSession:
    """Stateful driver over :func:`run_turn` — manages one conversation across turns.

    Owns the growing :class:`Conversation` (REQ-P14-LOGIC-005 session-state management)
    so
    a caller sends successive user messages without threading the transcript by hand. It
    is a thin, pure wrapper: it holds the injected :class:`ChatBackend` (never a
    provider),
    the optional fixed tool catalog, and the running conversation; each :meth:`send`
    appends the user message, runs one bounded turn, stores the result, and returns it.
    Zero Qt; deterministic given a fixed backend.
    """

    def __init__(
        self,
        backend: ChatBackend,
        *,
        tools: Optional[Sequence[ToolDescriptor]] = None,
        system_prompt: Optional[str] = None,
    ) -> None:
        """Create a session over ``backend``.

        Args:
            backend: The injected :class:`ChatBackend` (an ``LLMPort`` / the fake
            adapter).
            tools: An optional fixed tool catalog to present every turn; when ``None``,
                each turn rebuilds the current allow-list via ``build_tool_catalog``.
            system_prompt: An optional system message seeding the transcript.
        """
        self._backend = backend
        self._tools: Optional[Tuple[ToolDescriptor, ...]] = (
            None if tools is None else tuple(tools)
        )
        conversation = Conversation()
        if system_prompt:
            conversation = conversation.append(
                Message(role=Role.SYSTEM, content=system_prompt)
            )
        self._initial = conversation
        self._conversation = conversation

    @property
    def backend(self) -> ChatBackend:
        """The injected backend driving this session (never a provider)."""
        return self._backend

    @property
    def conversation(self) -> Conversation:
        """The current immutable transcript."""
        return self._conversation

    def reset(self) -> None:
        """Rewind to the initial transcript (retaining any seeded system message)."""
        self._conversation = self._initial

    def send(
        self,
        document: Document,
        user_text: str,
        *,
        confirm: ConfirmCallback = deny_all,
    ) -> TurnResult:
        """Append ``user_text``, run one bounded turn, store + return its result.

        Args:
            document: The subject document (mutated in place by applied ops).
            user_text: The user's message for this turn.
            confirm: The :data:`ConfirmCallback` for destructive ops (default
                :func:`deny_all` — gate-closed).

        Returns:
            The :class:`TurnResult`; :attr:`AssistantSession.conversation` is advanced
            to
            its transcript.

        Raises:
            AssistantError: On a bounded breach or any mid-turn failure (see
                :func:`run_turn`). Per the error-path atomicity contract, if the turn
                had applied ≥1 command before failing, the raised ``AssistantError``
                exposes them via :attr:`AssistantError.applied_commands` for the caller
                to revert/record. On error the session's :attr:`conversation` is **not**
                advanced (it stays at the pre-turn transcript), mirroring the document's
                revert-to-clean atomicity.
        """
        conversation = self._conversation.append(
            Message(role=Role.USER, content=user_text)
        )
        result = run_turn(
            document,
            conversation,
            self._backend,
            confirm=confirm,
            tools=self._tools,
        )
        self._conversation = result.conversation
        return result
