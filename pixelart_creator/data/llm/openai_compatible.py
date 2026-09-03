# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Stdlib-``urllib`` OpenAI-compatible ``LLMPort`` adapter (zero Qt, S11).

Part of the AI-assistant feature, Phase 14 (skill ``llm-adapter-normalization``
steps 1/4/5; ADR-0040 §1/§3;
spec REQ-P14-DATA-004/-006/-007). The one
OpenAI-compatible core: it POSTs the provider-neutral conversation + tool catalog to
``{base_url}/chat/completions`` over stdlib ``urllib`` and maps the response back to the
neutral :class:`~pixelart_creator.logic.assistant.AssistantReply`. Because the
``/v1/chat/completions`` "tools" wire is the 2026 de-facto standard, this **single**
adapter covers OpenAI, Google Gemini's OpenAI-compat endpoint, Ollama, and local
llama.cpp — every named provider except native Anthropic (that is the sibling
:mod:`~pixelart_creator.data.llm.anthropic_translator`).

**Mapping-only (Article VII, C2).** The adapter translates neutral types ↔ the wire and
**executes nothing**: a returned tool-call becomes an inert neutral
:class:`~pixelart_creator.logic.tool_catalog.ToolCall` that the 14C loop gates and
dispatches through the trusted path; a tool RESULT carried back in the conversation is
inert data mapped onto a ``role:"tool"`` message. There is **no**
``eval``/``exec``/``compile``/``__import__`` anywhere, and no provider/HTTP/credential
type leaks above the port (REQ-P14-DATA-007).

**Non-streaming (14D).** :meth:`OpenAICompatibleAdapter.respond` sends ``stream: false``
and maps the single JSON body; SSE streaming is a deferred, orthogonal surface.
**Stdlib only** (no new dependency); the key is read lazily from the keyring at request
time and never logged. Layering: ``data → logic`` imports only; zero Qt.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

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

__all__ = ["OpenAICompatibleAdapter"]

#: Default OpenAI base URL (the concrete route ``/chat/completions`` is appended). A
#: user targeting Gemini-compat / Ollama / llama.cpp overrides this per-construction.
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_PROVIDER = "openai"

#: The wire ``tool_choice`` posture: let the model decide whether to call a tool. The
#: adapter passes messages through as-is (system-prompt authorship is the caller's).
_TOOL_CHOICE_AUTO = "auto"


def _to_wire_messages(conversation: Conversation) -> List[Dict[str, Any]]:
    """Map neutral messages → OpenAI ``messages[]`` (outbound; skill step 4).

    ``Role.SYSTEM``/``USER``/``ASSISTANT`` map to the wire role literal; an assistant
    tool-call turn carries ``tool_calls[]`` (each ``{"id","type":"function","function":
    {"name","arguments":<JSON string>}}``); a ``Role.TOOL`` result is a separate
    ``{"role":"tool","tool_call_id","content"}`` message.

    The neutral :class:`~pixelart_creator.logic.tool_catalog.ToolCall` carries no wire
    id (the frozen 14A/14B contract), so synthetic ids are assigned to an assistant
    tool-calls and paired **positionally** to the tool-result messages that immediately
    follow (the 14C loop appends exactly one ``Role.TOOL`` result per call, in order) —
    honouring the wire's id-pairing requirement without mutating the neutral types.
    """
    out: List[Dict[str, Any]] = []
    pending_ids: List[str] = []
    counter = 0
    for message in conversation.messages:
        if message.role is Role.TOOL:
            call_id = message.tool_call_id or (
                pending_ids.pop(0) if pending_ids else ""
            )
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": message.content,
                }
            )
            continue
        if message.role is Role.ASSISTANT and message.tool_calls:
            ids: List[str] = []
            wire_calls: List[Dict[str, Any]] = []
            for call in message.tool_calls:
                call_id = f"call_{counter}"
                counter += 1
                ids.append(call_id)
                wire_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(dict(call.arguments)),
                        },
                    }
                )
            pending_ids = ids
            out.append(
                {
                    "role": "assistant",
                    "content": message.content or None,
                    "tool_calls": wire_calls,
                }
            )
            continue
        out.append({"role": message.role.value, "content": message.content})
    return out


def _to_wire_tools(tools: Sequence[ToolDescriptor]) -> List[Dict[str, Any]]:
    """Map neutral tool descriptors → OpenAI ``tools[]`` (skill step 1).

    Each :class:`~pixelart_creator.logic.tool_catalog.ToolDescriptor` becomes
    ``{"type":"function","function":{"name","description","parameters":<the descriptor's
    JSON-schema>}}``. The 14A projection is already a JSON-schema object, wrapped as-is.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            },
        }
        for tool in tools
    ]


def _parse_reply(payload: Dict[str, Any]) -> AssistantReply:
    """Map an OpenAI ``choices[0].message`` body → a neutral reply (inbound; step 4).

    A message with no ``tool_calls`` → :meth:`AssistantReply.final`; one-or-more
    ``tool_calls`` (parallel supported) → :meth:`AssistantReply.calling`, each mapped
    to a neutral :class:`~pixelart_creator.logic.tool_catalog.ToolCall` (from
    ``function.name`` + ``json.loads(function.arguments)``). Any JSON/structural defect
    is normalized to :class:`~pixelart_creator.data.llm.port.LLMResponseError` (the
    untrusted-response boundary) — never a raw ``KeyError``/``JSONDecodeError``.
    """
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError("provider response missing choices[0].message") from exc
    if not isinstance(message, dict):
        raise LLMResponseError("provider choices[0].message is not an object")

    content = message.get("content") or ""
    raw_calls = message.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        raise LLMResponseError("provider tool_calls is not an array")
    if not raw_calls:
        return AssistantReply.final(str(content))

    calls: List[ToolCall] = []
    for raw in raw_calls:
        if not isinstance(raw, dict):
            raise LLMResponseError("a tool_call entry is not an object")
        function = raw.get("function") or {}
        name = function.get("name")
        if not isinstance(name, str) or not name:
            raise LLMResponseError("a tool_call is missing a function name")
        raw_args = function.get("arguments", "{}")
        try:
            arguments = (
                json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LLMResponseError(
                f"tool_call {name!r} arguments were not valid JSON"
            ) from exc
        if not isinstance(arguments, dict):
            raise LLMResponseError(
                f"tool_call {name!r} arguments did not decode to an object"
            )
        calls.append(ToolCall(name=name, arguments=arguments))
    return AssistantReply.calling(*calls, content=str(content))


class OpenAICompatibleAdapter(_HTTPLLMAdapter):
    """A real OpenAI-compatible :class:`~pixelart_creator.data.llm.port.LLMPort`.

    Covers OpenAI, Gemini's OpenAI-compat endpoint, Ollama, and llama.cpp via the
    ``base_url`` (skill Decision LA-D1 branch B). Construction is cheap (no network, no
    keyring); the key is read lazily at :meth:`respond` time.
    """

    def __init__(
        self,
        *,
        provider: str = _DEFAULT_PROVIDER,
        base_url: str = _DEFAULT_BASE_URL,
        model: str,
        **kwargs: Any,
    ) -> None:
        """Create the adapter (see the shared ``_HTTPLLMAdapter`` base)."""
        super().__init__(provider=provider, base_url=base_url, model=model, **kwargs)

    def respond(
        self, conversation: Conversation, tools: Sequence[ToolDescriptor]
    ) -> AssistantReply:
        """Send one non-streaming turn and map the reply (skill steps 1/4/5).

        Raises:
            LLMNotConfiguredError: If no endpoint or API key is configured.
            LLMResponseError: On any transport/HTTP/parse failure (normalized).
        """
        key = self._require_config()
        url = f"{self._base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {key}"}
        body: Dict[str, Any] = {
            "model": self._model,
            "messages": _to_wire_messages(conversation),
            "tool_choice": _TOOL_CHOICE_AUTO,
            "stream": False,
        }
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
