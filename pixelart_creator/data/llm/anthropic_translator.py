# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Stdlib-``urllib`` native-Anthropic translator ``LLMPort`` adapter (zero Qt, S11).

Part of the AI-assistant feature, Phase 14 (skill ``llm-adapter-normalization``
steps 3/4/5; ADR-0040 §1/§3;
spec REQ-P14-DATA-005/-006/-007; Researcher ``ad2616c7`` R1.4/R1.5). Anthropic is the
sole named provider whose wire differs **structurally** from the OpenAI-compatible core
(:mod:`~pixelart_creator.data.llm.openai_compatible`), so this thin translator maps the
SAME neutral :class:`~pixelart_creator.logic.assistant` types onto the native Messages
API (``{base_url}/v1/messages``) and back — proving the port is genuinely
model-agnostic: the same 14C loop, tool catalog, and tiered gate drive it unchanged.

The four structural deltas it absorbs (R1.4):

* **Tool def** — flat ``{name, description, input_schema}`` (no ``function`` wrapper;
  ``input_schema`` not ``parameters``).
* **Model tool call** — a ``{"type":"tool_use","id","name","input"}`` content block
  (``input`` is an already-parsed object — no ``json.loads``).
* **Result feedback** — a ``{"role":"user"}`` message whose content array **leads** with
  ``{"type":"tool_result","tool_use_id",…}`` blocks (results-first, free text after).
* **Auth** — ``x-api-key`` + ``anthropic-version`` headers (NOT ``Authorization:
  Bearer``); ``system`` is a top-level request field, not a message.

**Mapping-only (Article VII, C2):** no execution, no ``eval``/``exec``; a returned
``tool_use`` becomes an inert neutral
:class:`~pixelart_creator.logic.tool_catalog.ToolCall` the 14C loop gates. Non-streaming
(14D). Stdlib only; key read lazily at request time and never logged; no provider/HTTP/
credential type leaks above the port (REQ-P14-DATA-007).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from pixelart_creator.data.llm._base import _HTTPLLMAdapter
from pixelart_creator.data.llm._http import post_json
from pixelart_creator.data.llm.port import LLMResponseError
from pixelart_creator.logic.assistant import (
    AssistantReply,
    Conversation,
    Role,
    ToolCall,
    ToolDescriptor,
)
from pixelart_creator.logic.constants import ASSISTANT_MAX_OUTPUT_TOKENS

__all__ = ["AnthropicTranslator"]

#: Default native-Anthropic base URL (the route ``/v1/messages`` is appended).
_DEFAULT_BASE_URL = "https://api.anthropic.com"
_DEFAULT_PROVIDER = "anthropic"

#: Required ``anthropic-version`` request header value (a wire-format string identifier,
#: module-local vocabulary per ADR-0001 — NOT a numeric constant, Article II).
_ANTHROPIC_VERSION = "2023-06-01"


def _to_wire(
    conversation: Conversation,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Map neutral messages → (top-level ``system``, Anthropic ``messages[]``); step 4.

    ``Role.SYSTEM`` messages are lifted into the top-level ``system`` string (Anthropic
    has no system *message* role). ``Role.USER`` → a user message; ``Role.ASSISTANT``
    with tool-calls → an assistant message whose content array carries optional text
    then ``tool_use`` blocks; a run of consecutive ``Role.TOOL`` results collapses into
    ``role:"user"`` message whose content **leads** with ``tool_result`` blocks
    (results-first). Synthetic ids pair an assistant turn's ``tool_use`` blocks to the
    following ``tool_result`` blocks positionally (the neutral
    :class:`~pixelart_creator.logic.tool_catalog.ToolCall` carries no wire id).
    """
    system_parts: List[str] = []
    messages: List[Dict[str, Any]] = []
    pending_ids: List[str] = []
    counter = 0
    items = conversation.messages
    index = 0
    total = len(items)
    while index < total:
        message = items[index]
        if message.role is Role.SYSTEM:
            if message.content:
                system_parts.append(message.content)
            index += 1
            continue
        if message.role is Role.USER:
            messages.append({"role": "user", "content": message.content})
            index += 1
            continue
        if message.role is Role.ASSISTANT:
            if message.tool_calls:
                blocks: List[Dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                ids: List[str] = []
                for call in message.tool_calls:
                    call_id = f"toolu_{counter}"
                    counter += 1
                    ids.append(call_id)
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call_id,
                            "name": call.name,
                            "input": dict(call.arguments),
                        }
                    )
                pending_ids = ids
                messages.append({"role": "assistant", "content": blocks})
            else:
                messages.append({"role": "assistant", "content": message.content})
            index += 1
            continue
        # Role.TOOL — collapse a consecutive run into one results-first user message.
        result_blocks: List[Dict[str, Any]] = []
        while index < total and items[index].role is Role.TOOL:
            tool_message = items[index]
            call_id = tool_message.tool_call_id or (
                pending_ids.pop(0) if pending_ids else ""
            )
            result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": tool_message.content,
                }
            )
            index += 1
        messages.append({"role": "user", "content": result_blocks})
    system = "\n\n".join(system_parts) if system_parts else None
    return system, messages


def _to_wire_tools(tools: Sequence[ToolDescriptor]) -> List[Dict[str, Any]]:
    """Map neutral tool descriptors → Anthropic ``tools[]`` (flat ``input_schema``)."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": dict(tool.parameters),
        }
        for tool in tools
    ]


def _parse_reply(payload: Dict[str, Any]) -> AssistantReply:
    """Map an Anthropic Messages ``content`` block array → a neutral reply (step 4).

    Concatenates ``text`` blocks for the narration; each ``tool_use`` block becomes a
    neutral :class:`~pixelart_creator.logic.tool_catalog.ToolCall` (``input`` is already
    an object — no ``json.loads``). Any structural defect is normalized to
    :class:`~pixelart_creator.data.llm.port.LLMResponseError`.
    """
    content_blocks = payload.get("content")
    if not isinstance(content_blocks, list):
        raise LLMResponseError("provider response content is not an array")

    text_parts: List[str] = []
    calls: List[ToolCall] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            raise LLMResponseError("a content block is not an object")
        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(str(block.get("text", "")))
        elif block_type == "tool_use":
            name = block.get("name")
            if not isinstance(name, str) or not name:
                raise LLMResponseError("a tool_use block is missing a name")
            arguments = block.get("input", {})
            if not isinstance(arguments, dict):
                raise LLMResponseError(f"tool_use {name!r} input is not an object")
            calls.append(ToolCall(name=name, arguments=arguments))
    content = "".join(text_parts)
    if calls:
        return AssistantReply.calling(*calls, content=content)
    return AssistantReply.final(content)


class AnthropicTranslator(_HTTPLLMAdapter):
    """A real native-Anthropic :class:`~pixelart_creator.data.llm.port.LLMPort`.

    The thin structural translator behind the same port (skill Decision LA-D1 branch A).
    Construction is cheap (no network, no keyring); the key is read lazily at
    :meth:`respond` time.
    """

    def __init__(
        self,
        *,
        provider: str = _DEFAULT_PROVIDER,
        base_url: str = _DEFAULT_BASE_URL,
        model: str,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        """Create the adapter.

        Args:
            max_tokens: The required Anthropic ``max_tokens`` request field; defaults to
                :data:`~pixelart_creator.logic.constants.ASSISTANT_MAX_OUTPUT_TOKENS`.
            (Other args: see
            :class:`~pixelart_creator.data.llm._base._HTTPLLMAdapter`.)
        """
        super().__init__(provider=provider, base_url=base_url, model=model, **kwargs)
        self._max_tokens: int = (
            ASSISTANT_MAX_OUTPUT_TOKENS if max_tokens is None else max_tokens
        )

    def respond(
        self, conversation: Conversation, tools: Sequence[ToolDescriptor]
    ) -> AssistantReply:
        """Send one non-streaming Messages turn and map the reply (steps 3/4/5).

        Raises:
            LLMNotConfiguredError: If no endpoint or API key is configured.
            LLMResponseError: On any transport/HTTP/parse failure (normalized).
        """
        key = self._require_config()
        url = f"{self._base_url}/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        system, messages = _to_wire(conversation)
        body: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system
        wire_tools = _to_wire_tools(tools)
        if wire_tools:
            body["tools"] = wire_tools
        payload = post_json(
            url,
            headers,
            body,
            timeout=self._timeout_s,
            retries=self._max_retries,
        )
        return _parse_reply(payload)
