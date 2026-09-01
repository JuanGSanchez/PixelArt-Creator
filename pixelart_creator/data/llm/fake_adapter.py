# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
r"""Deterministic scripted fake LLM adapter — the CI contract (zero Qt, S11).

Part of the AI-assistant feature, Phase 14 (ADR-0040 §4; spec REQ-P14-DATA-002;
SC-D002-1). A fully functional
:class:`~pixelart_creator.data.llm.port.LLMPort` driven by a **scripted response
program** — no network, no provider key — so the **entire agentic contract** (the 14C
loop, tiered safety, whitelist enforcement, injection defence, and the 14D
model-agnostic parity test) is exercised **headlessly in CI, deterministically and
reproducibly** (Article IV). It is the **credential-optional** guarantee: CI never
needs a real key. The ``FakeCloudAdapter`` precedent.

**Scripting mechanism.** The adapter is constructed with an ordered
``script`` of :class:`~pixelart_creator.logic.assistant.AssistantReply` values. The
Nth call to :meth:`respond` returns the Nth scripted reply and advances an internal
cursor; the conversation passed on each call is recorded on :attr:`calls` for test
assertions. Because a reply is any ``AssistantReply``, a script can express:

* **final messages** (``AssistantReply.final("…")``);
* **scripted tool-calls** — reversible *and* destructive — via
  ``AssistantReply.calling(ToolCall(...), …)`` (the fake merely *emits* the call; the
  14C gate decides whether it may run — the fake enforces nothing);
* **malicious tool-result follow-ups** — after the loop feeds a (possibly hostile)
  ``Role.TOOL`` result back, the *next* scripted reply may request a non-whitelisted or
  destructive op, proving the 14C gate/whitelist rejects it (results are data);
* **multi-step sequences** — several tool-call turns then a final message;
* **OpenAI-shape vs Anthropic-shape parity** — the port is already normalized, so both
  shapes yield the *same* :class:`AssistantReply`\\ s. :attr:`shape` is a descriptive
  label letting the 14D parity test run the *same script* under each shape and assert
  identical loop behaviour (genuine model-agnosticism).

Determinism: a monotonic cursor, no wall-clock read, no randomness. When the script is
exhausted, :meth:`respond` raises
:class:`~pixelart_creator.data.llm.port.LLMResponseError` (a script that ends without a
final reply is a test-authoring error, surfaced loudly).
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from pixelart_creator.data.llm.port import LLMPort, LLMResponseError
from pixelart_creator.logic.assistant import (
    AssistantReply,
    Conversation,
    ToolDescriptor,
)

__all__ = ["FakeLLMAdapter"]

#: Descriptive provider-shape labels for the model-agnostic parity test (14D). The
#: port is already normalized, so these change no behaviour — they let the same script
#: be run "as OpenAI" and "as Anthropic" and asserted identical (ADR-0040 §4). Module-
#: local vocabulary (ADR-0001 / BF-2), not a numeric constant.
_OPENAI_SHAPE = "openai"
_ANTHROPIC_SHAPE = "anthropic"


class FakeLLMAdapter(LLMPort):
    """A deterministic, scripted :class:`LLMPort` (no network, no key)."""

    def __init__(
        self,
        script: Sequence[AssistantReply],
        *,
        shape: str = _OPENAI_SHAPE,
        configured: bool = True,
    ) -> None:
        """Create a scripted fake adapter.

        Args:
            script: The ordered replies returned one-per-:meth:`respond` call. Build
                them with :meth:`AssistantReply.final` /
                :meth:`AssistantReply.calling`.
            shape: A descriptive provider-shape label (``"openai"`` / ``"anthropic"``)
                for the model-agnostic parity test; changes no behaviour.
            configured: The provider-agnostic configured flag reported by
                :meth:`is_configured` (the fake needs no real credential).
        """
        self._script: Tuple[AssistantReply, ...] = tuple(script)
        self._shape = str(shape)
        self._configured = bool(configured)
        self._cursor = 0
        #: The conversation passed to each :meth:`respond` call, in order (for tests).
        self.calls: List[Conversation] = []

    @property
    def shape(self) -> str:
        """The descriptive provider-shape label (parity test; no behavioural effect)."""
        return self._shape

    @property
    def remaining(self) -> int:
        """How many scripted replies are still unconsumed."""
        return len(self._script) - self._cursor

    def reset(self) -> None:
        """Rewind the cursor and clear recorded calls (reuse the script anew)."""
        self._cursor = 0
        self.calls = []

    def respond(
        self, conversation: Conversation, tools: Sequence[ToolDescriptor]
    ) -> AssistantReply:
        """Return the next scripted reply; record ``conversation`` for assertions.

        Raises:
            LLMResponseError: If the script is exhausted (a script that never reaches a
                final reply — surfaced loudly rather than looping).
        """
        self.calls.append(conversation)
        if self._cursor >= len(self._script):
            raise LLMResponseError(
                "fake LLM script exhausted after "
                f"{self._cursor} reply(ies); scripted program is too short for this run"
            )
        reply = self._script[self._cursor]
        self._cursor += 1
        return reply

    def is_configured(self) -> bool:
        """Return the provider-agnostic configured flag (no credential involved)."""
        return self._configured
