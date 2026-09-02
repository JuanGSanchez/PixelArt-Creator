"""Tests for pixelart_creator.logic.assistant (Phase-14, no Qt).

Covers the wire-neutral assistant vocabulary + the ``ChatBackend`` bridge
(ADR-0040 §2; spec REQ-P14-DATA-001; acceptance SC-D001-1):

* the value types ``Role`` / ``Message`` / ``Conversation`` / ``AssistantReply``
  behave as frozen, provider-neutral data containers;
* ``AssistantReply`` final vs tool-call shapes + the ``is_final`` discriminator;
* ``Conversation`` immutable append/extend;
* the ``ChatBackend`` Protocol is runtime-checkable and structurally satisfied by
  an object exposing ``respond`` + ``is_configured`` (so the 14C loop stays
  ``data/``-free — see also test_llm_port for the real ``LLMPort`` satisfaction);
* a ``Role.TOOL`` message carrying oversized/malicious content is inert DATA — the
  module executes nothing (Article VII).

Pure ``logic`` — this file imports NO Qt and NO ``data``.
"""

from __future__ import annotations

import dataclasses

import pytest

from pixelart_creator.logic.assistant import (
    AssistantReply,
    ChatBackend,
    Conversation,
    Message,
    Role,
    ToolCall,
    ToolDescriptor,
)

# --- Role: provider-neutral, str-backed ------------------------------------- #


def test_role_is_str_enum_with_wire_literals():
    assert Role.SYSTEM == "system"
    assert Role.USER == "user"
    assert Role.ASSISTANT == "assistant"
    assert Role.TOOL == "tool"
    # str subclass -> JSON-friendly, compares equal to its wire literal.
    assert isinstance(Role.USER, str)


def test_role_membership_is_exactly_four():
    assert {r.value for r in Role} == {"system", "user", "assistant", "tool"}


# --- Message: frozen, provider-neutral data container ----------------------- #


def test_message_is_frozen():
    m = Message(role=Role.USER, content="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.content = "mutated"  # type: ignore[misc]


def test_message_defaults():
    m = Message(role=Role.SYSTEM, content="sys")
    assert m.content == "sys"
    assert m.tool_calls == ()
    assert m.tool_call_id is None
    assert m.name is None


def test_message_tool_result_carries_ids():
    m = Message(
        role=Role.TOOL,
        content="result-text",
        tool_call_id="call-1",
        name="invert_selection",
    )
    assert m.role == Role.TOOL
    assert m.tool_call_id == "call-1"
    assert m.name == "invert_selection"


# --- Conversation: immutable append / extend -------------------------------- #


def test_conversation_defaults_empty():
    assert Conversation().messages == ()


def test_conversation_append_returns_new_instance():
    c0 = Conversation()
    m = Message(role=Role.USER, content="a")
    c1 = c0.append(m)
    assert c0.messages == ()  # original untouched (frozen, safe to share)
    assert c1.messages == (m,)
    assert c1 is not c0


def test_conversation_extend_preserves_order():
    c = Conversation().extend(
        [
            Message(role=Role.SYSTEM, content="s"),
            Message(role=Role.USER, content="u"),
        ]
    )
    assert [m.content for m in c.messages] == ["s", "u"]


def test_conversation_is_frozen():
    c = Conversation()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.messages = ()  # type: ignore[misc]


# --- AssistantReply: final vs tool-call shapes ------------------------------ #


def test_assistant_reply_final_is_final():
    r = AssistantReply.final("done")
    assert r.is_final is True
    assert r.tool_calls == ()
    assert r.message is not None
    assert r.message.role == Role.ASSISTANT
    assert r.message.content == "done"


def test_assistant_reply_calling_is_not_final():
    call = ToolCall(name="invert_selection", arguments={})
    r = AssistantReply.calling(call)
    assert r.is_final is False
    assert r.tool_calls == (call,)
    # No narration content -> no interim assistant message required.
    assert r.message is None


def test_assistant_reply_calling_with_narration_builds_message():
    call = ToolCall(name="fill", arguments={"colour": "#ff0000"})
    r = AssistantReply.calling(call, content="filling now")
    assert r.is_final is False
    assert r.tool_calls == (call,)
    assert r.message is not None
    assert r.message.content == "filling now"
    assert r.message.tool_calls == (call,)


def test_assistant_reply_multiple_tool_calls():
    c1 = ToolCall(name="fill", arguments={})
    c2 = ToolCall(name="invert_selection", arguments={})
    r = AssistantReply.calling(c1, c2)
    assert r.tool_calls == (c1, c2)
    assert r.is_final is False


def test_assistant_reply_is_frozen():
    r = AssistantReply.final("x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.message = None  # type: ignore[misc]


# --- ChatBackend Protocol: runtime-checkable, structurally satisfied -------- #


class _DummyBackend:
    """A minimal object exposing the two ChatBackend methods (no inheritance)."""

    def respond(self, conversation, tools):  # noqa: ANN001 - structural test
        return AssistantReply.final("ok")

    def is_configured(self) -> bool:
        return True


class _MissingMethodBackend:
    def respond(self, conversation, tools):  # noqa: ANN001 - structural test
        return AssistantReply.final("ok")

    # NO is_configured -> should NOT satisfy the Protocol.


def test_chatbackend_is_runtime_checkable_and_structurally_satisfied():
    # PEP 544 structural satisfaction WITHOUT inheriting ChatBackend.
    assert isinstance(_DummyBackend(), ChatBackend)


def test_chatbackend_rejects_object_missing_a_method():
    assert not isinstance(_MissingMethodBackend(), ChatBackend)
    assert not isinstance(object(), ChatBackend)


def test_dummy_backend_respond_returns_assistant_reply():
    reply = _DummyBackend().respond(
        Conversation(), (ToolDescriptor(name="noop", description="d", parameters={}),)
    )
    assert isinstance(reply, AssistantReply)
    assert reply.is_final is True


# --- Untrusted tool-result is inert DATA (Article VII) ---------------------- #


def test_tool_result_message_is_inert_data_no_execution(capsys):
    # An oversized / malicious tool-result payload is stored verbatim as data:
    # constructing the Message never evaluates or executes it.
    hostile = "__import__('os').system('echo PWNED')  # " + ("A" * 100_000)
    m = Message(role=Role.TOOL, content=hostile, tool_call_id="c", name="op")
    # Stored byte-for-byte; nothing ran.
    assert m.content == hostile
    assert "PWNED" not in capsys.readouterr().out


def test_assistant_module_contains_no_eval_or_exec():
    import pixelart_creator.logic.assistant as mod

    src = __import__("inspect").getsource(mod)
    for forbidden in ("eval(", "exec(", "compile(", "os.system", "subprocess"):
        assert forbidden not in src, f"unexpected {forbidden!r} in assistant.py"


# --------------------------------------------------------------------------- #
# Widen the zero-eval/exec audit to every Phase-14 assistant-path             #
# module (Article VII): source-text scan, no Qt ever imported (this file      #
# stays pure ``logic``). The ui/ modules are located by file path and their   #
# TEXT is scanned -- never imported, so no QApplication/widget is ever built. #
# --------------------------------------------------------------------------- #

import pathlib as _pathlib  # noqa: E402

_REPO_ROOT = _pathlib.Path(__file__).resolve().parents[3] / "pixelart_creator"

_ASSISTANT_PATH_MODULES = [
    _REPO_ROOT / "logic" / "assistant.py",
    _REPO_ROOT / "logic" / "tool_catalog.py",
    _REPO_ROOT / "data" / "llm" / "_base.py",
    _REPO_ROOT / "data" / "llm" / "_http.py",
    _REPO_ROOT / "data" / "llm" / "anthropic_translator.py",
    _REPO_ROOT / "data" / "llm" / "fake_adapter.py",
    _REPO_ROOT / "data" / "llm" / "openai_compatible.py",
    _REPO_ROOT / "data" / "llm" / "port.py",
    _REPO_ROOT / "data" / "llm" / "token_store.py",
    _REPO_ROOT / "data" / "assistant_cli.py",
    _REPO_ROOT / "ui" / "assistant_dock.py",
    _REPO_ROOT / "ui" / "assistant_worker.py",
    _REPO_ROOT / "ui" / "provider_config_dialog.py",
]

# Bare-name calls only (no preceding '.', letter, digit or underscore) -- so a
# Qt ``box.exec()`` (QDialog.exec, unrelated) is not a false positive, while a
# bare ``exec(...)`` / ``eval(...)`` (the actual dangerous builtin call) is
# still caught. Plain substring search (no regex, no backslash separators) so
# the path-portability scan never mistakes a pattern for a path literal.
_FORBIDDEN_EXECUTION_TOKENS = (
    "eval(",
    "exec(",
    "compile(",
    "os.system",
    "subprocess",
    "__import__(",
)


def _bare_token_hits(src: str, token: str) -> bool:
    """Whether ``token`` occurs in ``src`` as a bare (non-attribute) call."""
    start = 0
    while True:
        idx = src.find(token, start)
        if idx == -1:
            return False
        prev = src[idx - 1] if idx > 0 else ""
        if not (prev == "." or prev.isalnum() or prev == "_"):
            return True
        start = idx + 1


@pytest.mark.parametrize(
    "module_path", _ASSISTANT_PATH_MODULES, ids=lambda p: str(p.relative_to(_REPO_ROOT))
)
def test_assistant_path_module_contains_no_eval_or_exec(module_path):
    """No assistant-path module (logic / data / ui) ever calls eval/exec/compile
    or shells out -- Article VII, ADR-0040. Every path is present on disk."""
    assert module_path.is_file(), f"missing assistant-path module: {module_path}"
    src = module_path.read_text(encoding="utf-8")
    for token in _FORBIDDEN_EXECUTION_TOKENS:
        assert not _bare_token_hits(
            src, token
        ), f"unexpected bare {token!r} in {module_path.name}"
