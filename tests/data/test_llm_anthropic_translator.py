"""Tests for the native-Anthropic ``LLMPort`` translator (Phase-14 14D, no Qt).

Keyless, network-free coverage of ``data/llm/anthropic_translator.py`` (spec
REQ-P14-DATA-005/-006/-007; acceptance SC-P14-D005/-D006/-D007; skill
``llm-adapter-normalization`` steps 3/4/5). The real network is NEVER touched and the
real keyring is NEVER read — ``post_json`` and ``_load_key`` are monkeypatched.

Covered:

* BUILD (SC-D005): the native ``/v1/messages`` body — ``model``/``max_tokens``/
  ``messages[]``, top-level ``system``, flat ``tools[]`` with ``input_schema`` (no
  ``function`` wrapper), and the ``x-api-key`` + ``anthropic-version`` headers (NOT
  ``Authorization: Bearer``);
* the four structural deltas of ``_to_wire`` — system lifted top-level, ``tool_use``
  blocks, results-first ``tool_result`` collapse, positional synthetic-id pairing;
* PARSE (SC-D005): ``tool_use`` content blocks -> neutral ``ToolCall`` (``input``
  already an object), text concatenation, malformed-block rejection to
  ``LLMResponseError``;
* CREDENTIAL-GATING (SC-D006): ``respond`` with no key raises ``LLMNotConfiguredError``
  and attempts no network; the key never leaks to logs/stdout/repr;
* ``max_tokens`` default (``ASSISTANT_MAX_OUTPUT_TOKENS``) + override;
* an ``assistant_live``-marked smoke test skipped unless a real key+endpoint env exists.

Pure ``data`` unit — no Qt, no network, no real key.
"""

from __future__ import annotations

import logging
import os

import pytest

from pixelart_creator.data.llm import anthropic_translator as mod
from pixelart_creator.data.llm.anthropic_translator import (
    AnthropicTranslator,
    _parse_reply,
    _to_wire,
    _to_wire_tools,
)
from pixelart_creator.data.llm.port import (
    LLMNotConfiguredError,
    LLMPort,
    LLMResponseError,
)
from pixelart_creator.logic.assistant import (
    AssistantReply,
    Conversation,
    Message,
    Role,
    ToolCall,
)
from pixelart_creator.logic.constants import ASSISTANT_MAX_OUTPUT_TOKENS
from pixelart_creator.logic.tool_catalog import ToolDescriptor, build_tool_catalog

_SECRET = "sk-ant-SUPER-SECRET-key-do-not-log-xyz789"


@pytest.fixture
def captured(monkeypatch):
    """Capture the outgoing ``post_json`` call; return a canned final response."""
    box: dict = {}

    def fake_post_json(url, headers, body, *, timeout, retries):
        box["url"] = url
        box["headers"] = dict(headers)
        box["body"] = body
        box["timeout"] = timeout
        box["retries"] = retries
        return {"content": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(mod, "post_json", fake_post_json)
    return box


@pytest.fixture
def adapter(monkeypatch):
    a = AnthropicTranslator(model="claude-3-5-sonnet")
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
    return a


def _convo(*messages: Message) -> Conversation:
    return Conversation(messages=tuple(messages))


# --- BUILD: native request shaping (SC-D005) -------------------------------- #


def test_adapter_is_an_llm_port():
    assert isinstance(AnthropicTranslator(model="m"), LLMPort)


def test_build_native_request_body_and_headers(captured, adapter):
    convo = _convo(
        Message(role=Role.SYSTEM, content="be terse"),
        Message(role=Role.USER, content="recolour it"),
    )
    tools = build_tool_catalog()
    reply = adapter.respond(convo, tools)

    assert reply.is_final and reply.message.content == "ok"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"

    body = captured["body"]
    assert body["model"] == "claude-3-5-sonnet"
    assert body["max_tokens"] == ASSISTANT_MAX_OUTPUT_TOKENS
    assert body["system"] == "be terse"  # lifted top-level (no system message role)
    assert body["messages"] == [{"role": "user", "content": "recolour it"}]

    # tools[] is FLAT: name/description/input_schema, no function/parameters wrapper.
    assert body["tools"]
    for entry in body["tools"]:
        assert set(entry) == {"name", "description", "input_schema"}
        assert entry["input_schema"]["type"] == "object"

    # x-api-key + anthropic-version, NOT Authorization: Bearer.
    headers = captured["headers"]
    assert headers["x-api-key"] == _SECRET
    assert headers["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in headers


def test_build_omits_system_when_no_system_message(captured, adapter):
    adapter.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert "system" not in captured["body"]


def test_build_omits_tools_when_none(captured, adapter):
    adapter.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert "tools" not in captured["body"]


def test_max_tokens_default_and_override(captured, monkeypatch):
    a = AnthropicTranslator(model="m", max_tokens=256)
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
    a.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert captured["body"]["max_tokens"] == 256


# --- _to_wire: the four structural deltas ----------------------------------- #


def test_to_wire_lifts_multiple_system_messages():
    convo = _convo(
        Message(role=Role.SYSTEM, content="one"),
        Message(role=Role.SYSTEM, content="two"),
        Message(role=Role.USER, content="hi"),
    )
    system, messages = _to_wire(convo)
    assert system == "one\n\ntwo"
    assert messages == [{"role": "user", "content": "hi"}]


def test_to_wire_no_system_returns_none():
    system, _ = _to_wire(_convo(Message(role=Role.USER, content="hi")))
    assert system is None


def test_to_wire_empty_system_message_is_dropped():
    # An empty-content system message contributes nothing to the top-level system.
    system, messages = _to_wire(
        _convo(
            Message(role=Role.SYSTEM, content=""),
            Message(role=Role.USER, content="hi"),
        )
    )
    assert system is None
    assert messages == [{"role": "user", "content": "hi"}]


def test_to_wire_assistant_tool_use_blocks_with_narration():
    convo = _convo(
        Message(
            role=Role.ASSISTANT,
            content="working",
            tool_calls=(ToolCall(name="batch_recolour", arguments={"a": 1}),),
        ),
    )
    _, messages = _to_wire(convo)
    blocks = messages[0]["content"]
    assert blocks[0] == {"type": "text", "text": "working"}
    assert blocks[1]["type"] == "tool_use"
    assert blocks[1]["name"] == "batch_recolour"
    assert blocks[1]["input"] == {"a": 1}
    assert blocks[1]["id"].startswith("toolu_")


def test_to_wire_plain_assistant_message():
    _, messages = _to_wire(_convo(Message(role=Role.ASSISTANT, content="done")))
    assert messages[0] == {"role": "assistant", "content": "done"}


def test_to_wire_tool_results_collapse_results_first_user_message():
    convo = _convo(
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=(
                ToolCall(name="a", arguments={}),
                ToolCall(name="b", arguments={}),
            ),
        ),
        Message(role=Role.TOOL, content="ra", name="a"),
        Message(role=Role.TOOL, content="rb", name="b"),
    )
    _, messages = _to_wire(convo)
    # The assistant turn, then ONE user message leading with tool_result blocks.
    assistant_blocks = messages[0]["content"]
    ids = [b["id"] for b in assistant_blocks if b["type"] == "tool_use"]
    result_msg = messages[1]
    assert result_msg["role"] == "user"
    result_blocks = result_msg["content"]
    assert [b["type"] for b in result_blocks] == ["tool_result", "tool_result"]
    # Positional id pairing: the results reference the assistant call ids in order.
    assert [b["tool_use_id"] for b in result_blocks] == ids
    assert [b["content"] for b in result_blocks] == ["ra", "rb"]


def test_to_wire_tool_result_uses_explicit_id_when_present():
    convo = _convo(
        Message(role=Role.TOOL, content="r", tool_call_id="toolu_explicit", name="a"),
    )
    _, messages = _to_wire(convo)
    assert messages[0]["content"][0]["tool_use_id"] == "toolu_explicit"


def test_to_wire_tools_flat_input_schema():
    desc = ToolDescriptor(name="foo", description="d", parameters={"type": "object"})
    assert _to_wire_tools((desc,)) == [
        {"name": "foo", "description": "d", "input_schema": {"type": "object"}}
    ]


def test_to_wire_tools_empty():
    assert _to_wire_tools(()) == []


# --- PARSE: response mapping (SC-D005) -------------------------------------- #


def test_parse_text_only_is_final():
    reply = _parse_reply({"content": [{"type": "text", "text": "hello there"}]})
    assert reply.is_final
    assert reply.message.content == "hello there"


def test_parse_empty_content_is_empty_final():
    reply = _parse_reply({"content": []})
    assert reply.is_final
    assert reply.message.content == ""


def test_parse_tool_use_block():
    reply = _parse_reply(
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_0",
                    "name": "batch_recolour",
                    "input": {"x": 1, "y": 2},
                }
            ]
        }
    )
    assert not reply.is_final
    call = reply.tool_calls[0]
    assert call.name == "batch_recolour"
    assert dict(call.arguments) == {"x": 1, "y": 2}


def test_parse_mixed_text_and_tool_use():
    reply = _parse_reply(
        {
            "content": [
                {"type": "text", "text": "let me "},
                {"type": "text", "text": "recolour"},
                {"type": "tool_use", "id": "t", "name": "procgen", "input": {}},
            ]
        }
    )
    assert reply.message.content == "let me recolour"
    assert reply.tool_calls[0].name == "procgen"


def test_parse_multiple_tool_use_blocks():
    reply = _parse_reply(
        {
            "content": [
                {"type": "tool_use", "id": "t0", "name": "a", "input": {"i": 1}},
                {"type": "tool_use", "id": "t1", "name": "b", "input": {"j": 2}},
            ]
        }
    )
    assert [c.name for c in reply.tool_calls] == ["a", "b"]
    assert dict(reply.tool_calls[1].arguments) == {"j": 2}


def test_parse_tool_use_missing_input_defaults_empty():
    reply = _parse_reply({"content": [{"type": "tool_use", "id": "t", "name": "a"}]})
    assert dict(reply.tool_calls[0].arguments) == {}


@pytest.mark.parametrize(
    "payload",
    [
        {"content": "not-a-list"},
        {},
        {"content": ["not-an-object"]},
        {"content": [{"type": "tool_use", "id": "t", "input": {}}]},  # no name
        {"content": [{"type": "tool_use", "id": "t", "name": ""}]},  # empty name
        {"content": [{"type": "tool_use", "id": "t", "name": "a", "input": "nope"}]},
    ],
)
def test_parse_malformed_response_raises(payload):
    with pytest.raises(LLMResponseError):
        _parse_reply(payload)


def test_parse_ignores_unknown_block_types():
    # Unknown block kinds (e.g. a future "thinking" block) are skipped, not fatal.
    reply = _parse_reply(
        {"content": [{"type": "thinking", "text": "…"}, {"type": "text", "text": "hi"}]}
    )
    assert reply.message.content == "hi"


# --- CREDENTIAL-GATING (SC-D006) -------------------------------------------- #


def test_is_configured_reflects_key(monkeypatch):
    a = AnthropicTranslator(model="m")
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
    assert a.is_configured() is True
    monkeypatch.setattr(a, "_load_key", lambda: None)
    assert a.is_configured() is False


def test_respond_without_key_raises_and_no_network(monkeypatch):
    a = AnthropicTranslator(model="m")
    monkeypatch.setattr(a, "_load_key", lambda: None)

    def _boom(*args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("post_json must not be called when unconfigured")

    monkeypatch.setattr(mod, "post_json", _boom)
    with pytest.raises(LLMNotConfiguredError):
        a.respond(_convo(Message(role=Role.USER, content="hi")), ())


def test_key_never_leaks_to_logs_stdout_or_repr(captured, adapter, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    adapter.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert _SECRET not in caplog.text
    out = capsys.readouterr()
    assert _SECRET not in out.out
    assert _SECRET not in out.err
    assert _SECRET not in repr(adapter)
    assert _SECRET not in str(vars(adapter))


# --- assistant_live: the ONLY real-network test (deselected/skipped) -------- #


@pytest.mark.assistant_live
def test_live_anthropic_smoke(monkeypatch):
    """A real round-trip IFF a key + endpoint env are present; else SKIP."""
    key = os.environ.get("PIXELART_ASSISTANT_LIVE_ANTHROPIC_KEY")
    base_url = os.environ.get(
        "PIXELART_ASSISTANT_LIVE_ANTHROPIC_BASE_URL", "https://api.anthropic.com"
    )
    model = os.environ.get(
        "PIXELART_ASSISTANT_LIVE_ANTHROPIC_MODEL", "claude-3-5-haiku-latest"
    )
    if not key:
        pytest.skip("assistant_live: no Anthropic key env; deselected by default")
    a = AnthropicTranslator(base_url=base_url, model=model, max_tokens=16)
    monkeypatch.setattr(a, "_load_key", lambda: key)
    reply = a.respond(
        _convo(Message(role=Role.USER, content="Reply with the single word OK.")),
        (),
    )
    assert isinstance(reply, AssistantReply)
