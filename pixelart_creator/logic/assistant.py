"""Assistant conversation value types + the ``ChatBackend`` bridge (zero Qt, S11).

Phase-14 Slice 14B (ADR-0040 §2; spec REQ-P14-DATA-001). This module single-sources
the **wire-neutral vocabulary** the model-agnostic assistant speaks — the normalized,
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

**Slice scope.** This 14B module carries the value types + ``ChatBackend`` Protocol
**only**. The bounded agentic loop, the tiered-reversibility gate, and the injection
defence (with their named caps in :mod:`~pixelart_creator.logic.constants`) land in
Slice 14C (ADR-0041) and *extend* this module. Zero Qt; imports only ``logic``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, Sequence, Tuple, runtime_checkable

from pixelart_creator.logic.tool_catalog import ToolCall, ToolDescriptor

__all__ = [
    "Role",
    "Message",
    "Conversation",
    "AssistantReply",
    "ChatBackend",
    "ToolCall",
    "ToolDescriptor",
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
    """An ordered, immutable sequence of :class:`Message`\\ s (provider-neutral).

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
