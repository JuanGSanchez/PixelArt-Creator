"""Tests for the OpenAI-compatible ``LLMPort`` adapter (Phase-14 14D, no Qt).

Keyless, network-free coverage of ``data/llm/openai_compatible.py`` and the shared
``data/llm/_base.py`` credential/config base (spec REQ-P14-DATA-004/-006/-007;
acceptance SC-P14-D004/-D006/-D007; skill ``llm-adapter-normalization`` steps 1/4/5).
The real network is NEVER touched and the real keyring is NEVER read:

* BUILD (SC-D004): ``post_json`` is monkeypatched to CAPTURE the outgoing
  ``/chat/completions`` request body + headers and return a canned reply — asserting the
  wire shape (``model``/``messages[]``/``tools[]``/``tool_choice:"auto"``/
  ``stream:false``, ``Authorization: Bearer``) with no real call;
* PARSE (SC-D004/-D005): captured/sample responses (content-only; content+tool_calls;
  parallel tool_calls; malformed) mapped through ``_parse_reply`` to a neutral
  ``AssistantReply`` — proving model-agnostic mapping WITHOUT a live call, incl. a
  Hypothesis round-trip;
* CREDENTIAL-GATING (SC-D006): ``is_configured`` reflects key presence; ``respond`` with
  no key raises ``LLMNotConfiguredError`` and attempts NO network; the key never appears
  in logs / stdout / repr / exceptions; the ``_base`` config defaults + lazy
  ``_load_key`` degradation;
* an ``assistant_live``-marked smoke test that is SKIPPED unless a real key+endpoint env
  is present (the only real-network test; deselected in CI).

Pure ``data`` unit — no Qt, no network, no real key.
"""

from __future__ import annotations

import json
import logging
import os

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data.llm import _base as base_mod
from pixelart_creator.data.llm import openai_compatible as mod
from pixelart_creator.data.llm.openai_compatible import (
    OpenAICompatibleAdapter,
    _parse_reply,
    _to_wire_messages,
    _to_wire_tools,
)
from pixelart_creator.data.llm.port import (
    LLMNotConfiguredError,
    LLMPort,
    LLMResponseError,
)
from pixelart_creator.data.llm.token_store import TokenStoreError
from pixelart_creator.logic.assistant import (
    AssistantReply,
    Conversation,
    Message,
    Role,
    ToolCall,
)
from pixelart_creator.logic.constants import (
    ASSISTANT_REQUEST_MAX_RETRIES,
    ASSISTANT_REQUEST_TIMEOUT_S,
)
from pixelart_creator.logic.tool_catalog import ToolDescriptor, build_tool_catalog

_SECRET = "sk-SUPER-SECRET-openai-key-do-not-log-abc123"


# --- fixtures --------------------------------------------------------------- #


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
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(mod, "post_json", fake_post_json)
    return box


@pytest.fixture
def adapter(monkeypatch):
    """A configured adapter whose key is injected (no keyring, no network)."""
    a = OpenAICompatibleAdapter(model="gpt-4o-mini")
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
    return a


def _convo(*messages: Message) -> Conversation:
    return Conversation(messages=tuple(messages))


# --- BUILD: request shaping (SC-D004) --------------------------------------- #


def test_adapter_is_an_llm_port():
    assert isinstance(OpenAICompatibleAdapter(model="m"), LLMPort)


def test_build_request_body_structure(captured, adapter):
    convo = _convo(
        Message(role=Role.SYSTEM, content="be helpful"),
        Message(role=Role.USER, content="recolour it"),
    )
    tools = build_tool_catalog()
    reply = adapter.respond(convo, tools)

    assert reply.is_final and reply.message.content == "ok"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    body = captured["body"]
    assert body["model"] == "gpt-4o-mini"
    assert body["tool_choice"] == "auto"
    assert body["stream"] is False
    # messages[] carries the neutral roles through.
    assert body["messages"] == [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "recolour it"},
    ]
    # tools[] is the OpenAI function wrapper over each descriptor.
    assert body["tools"]
    for entry in body["tools"]:
        assert entry["type"] == "function"
        assert set(entry["function"]) == {"name", "description", "parameters"}
        assert entry["function"]["parameters"]["type"] == "object"


def test_build_sets_bearer_auth_header(captured, adapter):
    adapter.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert captured["headers"]["Authorization"] == f"Bearer {_SECRET}"


def test_build_passes_configured_timeout_and_retries(captured, adapter):
    adapter.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert captured["timeout"] == ASSISTANT_REQUEST_TIMEOUT_S
    assert captured["retries"] == ASSISTANT_REQUEST_MAX_RETRIES


def test_build_omits_tools_key_when_no_tools(captured, adapter):
    adapter.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert "tools" not in captured["body"]


def test_build_custom_base_url_is_used(captured, monkeypatch):
    a = OpenAICompatibleAdapter(
        provider="ollama", base_url="http://localhost:11434/v1", model="llama3"
    )
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
    a.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert captured["url"] == "http://localhost:11434/v1/chat/completions"


# --- _to_wire_messages: tool-call turn positional id pairing ---------------- #


def test_to_wire_messages_pairs_synthetic_ids_positionally():
    convo = _convo(
        Message(role=Role.USER, content="do it"),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=(ToolCall(name="batch_recolour", arguments={"a": 1}),),
        ),
        Message(role=Role.TOOL, content="done", name="batch_recolour"),
    )
    wire = _to_wire_messages(convo)
    assert wire[0] == {"role": "user", "content": "do it"}
    assistant = wire[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"] is None  # empty narration -> None
    call = assistant["tool_calls"][0]
    assert call["type"] == "function"
    assert call["function"]["name"] == "batch_recolour"
    assert json.loads(call["function"]["arguments"]) == {"a": 1}
    # The tool result is paired to the assistant call's synthetic id.
    assert wire[2] == {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": "done",
    }


def test_to_wire_messages_uses_explicit_tool_call_id_when_present():
    convo = _convo(
        Message(role=Role.TOOL, content="r", tool_call_id="call_xyz", name="op"),
    )
    wire = _to_wire_messages(convo)
    assert wire[0]["tool_call_id"] == "call_xyz"


def test_to_wire_messages_assistant_with_narration_and_calls():
    convo = _convo(
        Message(
            role=Role.ASSISTANT,
            content="working on it",
            tool_calls=(ToolCall(name="procgen", arguments={}),),
        ),
    )
    wire = _to_wire_messages(convo)
    assert wire[0]["content"] == "working on it"


def test_to_wire_tools_empty_is_empty_list():
    assert _to_wire_tools(()) == []


def test_to_wire_tools_wraps_descriptor():
    desc = ToolDescriptor(name="foo", description="d", parameters={"type": "object"})
    assert _to_wire_tools((desc,)) == [
        {
            "type": "function",
            "function": {
                "name": "foo",
                "description": "d",
                "parameters": {"type": "object"},
            },
        }
    ]


# --- PARSE: response mapping (SC-D004/-D005) -------------------------------- #


def test_parse_content_only_is_final():
    reply = _parse_reply({"choices": [{"message": {"content": "hello there"}}]})
    assert reply.is_final
    assert reply.message.content == "hello there"
    assert reply.tool_calls == ()


def test_parse_missing_content_is_empty_final():
    reply = _parse_reply({"choices": [{"message": {}}]})
    assert reply.is_final
    assert reply.message.content == ""


def test_parse_single_tool_call():
    payload = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_0",
                            "type": "function",
                            "function": {
                                "name": "batch_recolour",
                                "arguments": '{"x": 1, "y": 2}',
                            },
                        }
                    ],
                }
            }
        ]
    }
    reply = _parse_reply(payload)
    assert not reply.is_final
    assert len(reply.tool_calls) == 1
    call = reply.tool_calls[0]
    assert call.name == "batch_recolour"
    assert dict(call.arguments) == {"x": 1, "y": 2}


def test_parse_content_and_tool_call_keeps_narration():
    payload = {
        "choices": [
            {
                "message": {
                    "content": "let me recolour",
                    "tool_calls": [
                        {
                            "function": {"name": "procgen", "arguments": "{}"},
                        }
                    ],
                }
            }
        ]
    }
    reply = _parse_reply(payload)
    assert reply.message.content == "let me recolour"
    assert reply.tool_calls[0].name == "procgen"


def test_parse_parallel_tool_calls():
    payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"function": {"name": "a", "arguments": '{"i": 1}'}},
                        {"function": {"name": "b", "arguments": '{"j": 2}'}},
                    ]
                }
            }
        ]
    }
    reply = _parse_reply(payload)
    assert [c.name for c in reply.tool_calls] == ["a", "b"]
    assert dict(reply.tool_calls[1].arguments) == {"j": 2}


def test_parse_arguments_already_object():
    # Some OpenAI-compat servers return arguments as an object, not a JSON string.
    payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [{"function": {"name": "a", "arguments": {"k": 3}}}]
                }
            }
        ]
    }
    reply = _parse_reply(payload)
    assert dict(reply.tool_calls[0].arguments) == {"k": 3}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": "not-an-object"}]},
        {"choices": [{"message": {"tool_calls": "not-a-list"}}]},
        {"choices": [{"message": {"tool_calls": ["not-an-object"]}}]},
        {"choices": [{"message": {"tool_calls": [{"function": {}}]}}]},
        {"choices": [{"message": {"tool_calls": [{"function": {"name": ""}}]}}]},
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "a", "arguments": "{not json"}}
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "a", "arguments": "[1, 2]"}}
                        ]
                    }
                }
            ]
        },
    ],
)
def test_parse_malformed_response_raises_llm_response_error(payload):
    with pytest.raises(LLMResponseError):
        _parse_reply(payload)


# --- PARSE property: any content/args round-trips to the neutral reply ------ #


@given(
    content=st.text(max_size=40),
    args=st.dictionaries(
        st.text(min_size=1, max_size=8),
        st.one_of(st.integers(), st.booleans(), st.text(max_size=8)),
        max_size=4,
    ),
)
def test_parse_tool_call_arguments_round_trip(content, args):
    payload = {
        "choices": [
            {
                "message": {
                    "content": content,
                    "tool_calls": [
                        {"function": {"name": "op", "arguments": json.dumps(args)}}
                    ],
                }
            }
        ]
    }
    reply = _parse_reply(payload)
    assert dict(reply.tool_calls[0].arguments) == args


# --- CREDENTIAL-GATING (SC-D006) -------------------------------------------- #


def test_is_configured_true_with_key(monkeypatch):
    a = OpenAICompatibleAdapter(model="m")
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
    assert a.is_configured() is True


def test_is_configured_false_without_key(monkeypatch):
    a = OpenAICompatibleAdapter(model="m")
    monkeypatch.setattr(a, "_load_key", lambda: None)
    assert a.is_configured() is False


def test_is_configured_false_without_endpoint(monkeypatch):
    a = OpenAICompatibleAdapter(base_url="", model="m")
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
    assert a.is_configured() is False


def test_respond_without_key_raises_not_configured_and_no_network(monkeypatch):
    a = OpenAICompatibleAdapter(model="m")
    monkeypatch.setattr(a, "_load_key", lambda: None)

    def _boom(*args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("post_json must not be called when unconfigured")

    monkeypatch.setattr(mod, "post_json", _boom)
    with pytest.raises(LLMNotConfiguredError):
        a.respond(_convo(Message(role=Role.USER, content="hi")), ())


def test_respond_without_endpoint_raises_not_configured(monkeypatch):
    a = OpenAICompatibleAdapter(base_url="", model="m")
    monkeypatch.setattr(a, "_load_key", lambda: _SECRET)
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


def test_not_configured_error_message_does_not_leak_key(monkeypatch):
    a = OpenAICompatibleAdapter(model="m")
    monkeypatch.setattr(a, "_load_key", lambda: None)
    with pytest.raises(LLMNotConfiguredError) as ei:
        a.respond(_convo(Message(role=Role.USER, content="hi")), ())
    assert _SECRET not in str(ei.value)


# --- shared _base config + lazy credential degradation ---------------------- #


def test_base_config_defaults():
    a = OpenAICompatibleAdapter(model="gpt-4o")
    assert a.provider == "openai"
    assert a._base_url == "https://api.openai.com/v1"
    assert a._model == "gpt-4o"
    assert a._timeout_s == ASSISTANT_REQUEST_TIMEOUT_S
    assert a._max_retries == ASSISTANT_REQUEST_MAX_RETRIES


def test_base_config_overrides():
    a = OpenAICompatibleAdapter(
        provider="p",
        base_url="https://x/v1/",  # trailing slash trimmed
        model="m",
        account="acct",
        timeout_s=3.5,
        max_retries=5,
    )
    assert a._base_url == "https://x/v1"
    assert a._timeout_s == 3.5
    assert a._max_retries == 5
    assert a._account == "acct"


def test_empty_base_url_preserved_not_stripped():
    a = OpenAICompatibleAdapter(base_url="", model="m")
    assert a._base_url == ""


def test_load_key_reads_token_store(monkeypatch):
    a = OpenAICompatibleAdapter(provider="openai", model="m", account="default")
    seen = {}

    def fake_load_token(provider, account):
        seen["args"] = (provider, account)
        return _SECRET

    monkeypatch.setattr(base_mod, "load_token", fake_load_token)
    assert a._load_key() == _SECRET
    assert seen["args"] == ("openai", "default")


def test_load_key_returns_none_when_token_absent(monkeypatch):
    a = OpenAICompatibleAdapter(model="m")
    monkeypatch.setattr(base_mod, "load_token", lambda p, acc: None)
    assert a._load_key() is None


def test_load_key_degrades_to_none_when_keyring_missing(monkeypatch):
    # A missing keyring backend (TokenStoreError) degrades to None, never a crash.
    a = OpenAICompatibleAdapter(model="m")

    def _raise(provider, account):
        raise TokenStoreError("keyring not installed")

    monkeypatch.setattr(base_mod, "load_token", _raise)
    assert a._load_key() is None
    assert a.is_configured() is False


# --- lazy import: data/llm imports with keyring absent ---------------------- #


def test_data_llm_imports_without_keyring(monkeypatch):
    import builtins
    import importlib
    import sys

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "keyring" or name.startswith("keyring."):
            raise ImportError("no keyring in this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "keyring", raising=False)
    monkeypatch.setattr(builtins, "__import__", _fake_import)

    # Re-importing the adapter modules must succeed with keyring unavailable
    # (the key is read lazily, at respond time only).
    importlib.reload(
        importlib.import_module("pixelart_creator.data.llm.openai_compatible")
    )
    a = OpenAICompatibleAdapter(model="m")  # construction touches no keyring
    assert a.provider == "openai"


# --- assistant_live: the ONLY real-network test (deselected/skipped) -------- #


@pytest.mark.assistant_live
def test_live_openai_smoke(monkeypatch):
    """A real round-trip IFF a key + endpoint env are present; else SKIP.

    Deselected in the default gate via ``-m "not assistant_live"``; and even when
    collected (no ``-m`` filter) it SKIPS unless both env vars are set, so the default
    run is network-free.
    """
    key = os.environ.get("PIXELART_ASSISTANT_LIVE_OPENAI_KEY")
    base_url = os.environ.get("PIXELART_ASSISTANT_LIVE_OPENAI_BASE_URL")
    model = os.environ.get("PIXELART_ASSISTANT_LIVE_OPENAI_MODEL", "gpt-4o-mini")
    if not (key and base_url):
        pytest.skip("assistant_live: no OpenAI key+endpoint env; deselected by default")
    a = OpenAICompatibleAdapter(base_url=base_url, model=model)
    monkeypatch.setattr(a, "_load_key", lambda: key)
    reply = a.respond(
        _convo(Message(role=Role.USER, content="Reply with the single word OK.")),
        (),
    )
    assert isinstance(reply, AssistantReply)
