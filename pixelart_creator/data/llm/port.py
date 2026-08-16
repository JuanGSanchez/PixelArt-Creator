r"""The one model-agnostic LLM port — provider-neutral chat/tool-calling (zero Qt, S11).

Phase-14 Slice 14B (ADR-0040 §1/§3; spec REQ-P14-DATA-001/-007). Defines the **single**
provider-agnostic :class:`LLMPort` ABC every adapter implements — the deterministic
fake adapter (14B) and, later, the real stdlib-``urllib`` OpenAI-compatible client and
the native-Anthropic translator (14D) — plus the port's own :class:`LLMError` family.

**Provider-agnostic by construction (REQ-P14-DATA-007, mirrors ``CloudPort``).** The
one core verb is
``respond(conversation, tools) -> AssistantReply``: given an ordered
:class:`~pixelart_creator.logic.assistant.Conversation` and the available
:class:`~pixelart_creator.logic.tool_catalog.ToolDescriptor`\\ s, return either a final
assistant message or one-or-more tool-calls
(:class:`~pixelart_creator.logic.assistant.AssistantReply`). The signatures name **no**
provider and carry **no** provider SDK type, HTTP/``urllib`` type, or credential type —
those live only inside the concrete adapters. Capability/configuration differences are
surfaced through a provider-agnostic :meth:`LLMPort.is_configured` (default ``False``;
``ui/`` never sees a key — the ``CloudPort.is_connected`` precedent). Adding a provider
is adding an adapter; nothing above the port changes (Article XI).

**The layering bridge (ADR-0040 §2).** ``respond`` structurally satisfies the
``logic``-side :class:`~pixelart_creator.logic.assistant.ChatBackend` Protocol, so the
14C loop (typed against ``ChatBackend``) drives an injected ``LLMPort`` **without any
``logic → data`` import**. This module imports the value types from ``logic`` (a
``data → logic`` edge, allowed). Zero Qt; no ``ui`` import.

**Article VII.** The port only talks to the (fake, here) model; it executes **nothing**
and contains **no** ``eval``/``exec``/``compile``/``__import__``. A tool result carried
back in the conversation is plain data (a ``Role.TOOL`` message); bounding it and
whitelisting tool-calls is the 14C loop's trusted-dispatch responsibility, not the
port's.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from pixelart_creator.logic.assistant import AssistantReply, Conversation
from pixelart_creator.logic.tool_catalog import ToolDescriptor

__all__ = [
    "LLMError",
    "LLMNotConfiguredError",
    "LLMResponseError",
    "LLMPort",
]


class LLMError(ValueError):
    """Base of the LLM port's own exception family (provider-agnostic).

    Mirrors ``CloudError`` (a ``ValueError`` subclass). No provider-specific exception
    ever surfaces above the port; adapters normalize their transport/provider failures
    into this family (REQ-P14-DATA-007).
    """


class LLMNotConfiguredError(LLMError):
    """Raised when a request is attempted against an unconfigured adapter.

    The credential-optional posture (REQ-P14-DATA-006): a missing key/endpoint is a
    clear "not configured" state, never a crash. Callers prefer probing
    :meth:`LLMPort.is_configured` first and degrading gracefully.
    """


class LLMResponseError(LLMError):
    """Raised when a provider response cannot be normalized to a reply.

    The untrusted-response boundary: a malformed/oversized/unparseable provider payload
    is rejected here rather than propagated as a raw transport/JSON error. The fake
    adapter raises it when its scripted program is exhausted.
    """


class LLMPort(ABC):
    """The one provider-agnostic LLM interface (ADR-0040 §1/§3).

    Every adapter (the fake adapter; later, the real OpenAI-compatible + Anthropic
    adapters) subclasses this. It speaks only the normalized ``logic`` value types; no
    provider/HTTP/credential type appears in its signatures. Because :meth:`respond`
    and :meth:`is_configured` match the
    :class:`~pixelart_creator.logic.assistant.ChatBackend` Protocol, an ``LLMPort``
    instance is a valid backend for the 14C loop.
    """

    @abstractmethod
    def respond(
        self, conversation: Conversation, tools: Sequence[ToolDescriptor]
    ) -> AssistantReply:
        """Return the model's reply for one turn (final message or tool-call(s)).

        Args:
            conversation: The ordered conversation so far (system/user/assistant/tool
                messages). Tool-result messages are untrusted data (Article VII).
            tools: The available provider-neutral tool descriptors (the 14A catalog
                projection). The adapter wraps these per provider; the caller need not.

        Returns:
            One :class:`~pixelart_creator.logic.assistant.AssistantReply` — either a
            final assistant message or one-or-more tool-calls for the loop to gate and
            dispatch.

        Raises:
            LLMNotConfiguredError: If the adapter has no usable configuration.
            LLMResponseError: If the provider response cannot be normalized.
        """

    def is_configured(self) -> bool:
        """Whether this adapter is ready to serve requests (provider-agnostic).

        Default ``False``; concrete adapters override. No credential is exposed — the
        ``CloudPort.is_connected`` precedent (REQ-P14-DATA-006/-007). ``ui/`` uses this
        to degrade to a clear "not configured" state.
        """
        return False
