"""Model-agnostic parity across the two real adapters + the fake (Phase-14 14D, no Qt).

The SC-D005-1 proof that the port is genuinely provider-agnostic: EQUIVALENT scripted
inputs, mapped through the OpenAI-compatible ``_parse_reply``, the Anthropic
``_parse_reply``, and produced directly by the deterministic fake, yield EQUIVALENT
neutral ``AssistantReply`` structures — the 14C loop cannot tell the providers apart
(spec REQ-P14-DATA-005/-007; skill ``llm-adapter-normalization``; ADR-0040 §4). The fake
adapter's ``shape`` label is the parity anchor: the same script under ``shape="openai"``
and ``shape="anthropic"`` must behave identically (the label changes no behaviour).

No network, no key — this is the keyless build/parse parity, not a live call. A
Hypothesis property drives the cross-provider mapping over generated content + tool-call
inputs.

Pure ``data`` unit — no Qt, no network, no real key.
"""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data.llm import FakeLLMAdapter
from pixelart_creator.data.llm.anthropic_translator import (
    _parse_reply as anthropic_parse,
)
from pixelart_creator.data.llm.openai_compatible import _parse_reply as openai_parse
from pixelart_creator.logic.assistant import (
    AssistantReply,
    Conversation,
    Message,
    Role,
    ToolCall,
    ToolDescriptor,
)

_TOOLS = (ToolDescriptor(name="noop", description="d", parameters={}),)


# --- normalisation helper: a comparable view of any neutral reply ----------- #


def _norm(reply: AssistantReply):
    """Reduce a reply to (is_final, content, [(name, args)]) for equality."""
    content = reply.message.content if reply.message is not None else ""
    calls = [(c.name, dict(c.arguments)) for c in reply.tool_calls]
    return (reply.is_final, content, calls)


# --- equivalent-wire builders for each provider ----------------------------- #


def _openai_wire(content, calls):
    message = {"content": content}
    if calls:
        message["tool_calls"] = [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
            for i, (name, args) in enumerate(calls)
        ]
    return {"choices": [{"message": message}]}


def _anthropic_wire(content, calls):
    blocks = []
    if content:
        blocks.append({"type": "text", "text": content})
    for i, (name, args) in enumerate(calls):
        blocks.append(
            {"type": "tool_use", "id": f"toolu_{i}", "name": name, "input": args}
        )
    return {"content": blocks}


def _fake_reply(content, calls):
    if calls:
        return AssistantReply.calling(
            *(ToolCall(name=n, arguments=a) for n, a in calls), content=content
        )
    return AssistantReply.final(content)


# --- SC-D005-1: the fake's shape label is behaviour-neutral (parity anchor) --- #


def test_fake_shape_label_does_not_change_the_reply():
    script = [
        AssistantReply.calling(
            ToolCall(name="batch_recolour", arguments={"x": 1}), content="hi"
        )
    ]
    oai = FakeLLMAdapter(script, shape="openai")
    anth = FakeLLMAdapter(script, shape="anthropic")
    assert oai.shape != anth.shape  # the label differs …
    # … but the produced neutral reply is identical (the loop can't tell them apart).
    r_oai = oai.respond(Conversation(), _TOOLS)
    r_anth = anth.respond(Conversation(), _TOOLS)
    assert _norm(r_oai) == _norm(r_anth)


# --- cross-provider parity for hand-picked equivalent inputs ---------------- #


def test_content_only_parity_across_providers():
    content, calls = "hello world", []
    got = {
        "openai": _norm(openai_parse(_openai_wire(content, calls))),
        "anthropic": _norm(anthropic_parse(_anthropic_wire(content, calls))),
        "fake": _norm(_fake_reply(content, calls)),
    }
    assert got["openai"] == got["anthropic"] == got["fake"]


def test_single_tool_call_parity_across_providers():
    content, calls = "on it", [("batch_recolour", {"x": 1, "y": 2})]
    got = {
        "openai": _norm(openai_parse(_openai_wire(content, calls))),
        "anthropic": _norm(anthropic_parse(_anthropic_wire(content, calls))),
        "fake": _norm(_fake_reply(content, calls)),
    }
    assert got["openai"] == got["anthropic"] == got["fake"]
    assert got["fake"][2] == [("batch_recolour", {"x": 1, "y": 2})]


def test_parallel_tool_calls_parity_across_providers():
    content = ""
    calls = [("a", {"i": 1}), ("b", {"j": 2})]
    o = _norm(openai_parse(_openai_wire(content, calls)))
    a = _norm(anthropic_parse(_anthropic_wire(content, calls)))
    f = _norm(_fake_reply(content, calls))
    assert o == a == f
    assert [name for name, _ in o[2]] == ["a", "b"]


# --- Hypothesis: parity holds for any generated content + tool calls -------- #

_json_scalar = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.booleans(),
    st.text(max_size=8),
)
_args = st.dictionaries(st.text(min_size=1, max_size=6), _json_scalar, max_size=3)
_calls = st.lists(
    st.tuples(st.text(min_size=1, max_size=6), _args),
    max_size=3,
)


@given(content=st.text(max_size=30), calls=_calls)
def test_parity_property_across_all_three(content, calls):
    o = _norm(openai_parse(_openai_wire(content, calls)))
    a = _norm(anthropic_parse(_anthropic_wire(content, calls)))
    f = _norm(_fake_reply(content, calls))
    assert o == a == f


# --- the equivalent script drives run_turn identically (loop-level parity) --- #


def test_equivalent_scripts_run_turn_identically_regardless_of_shape():
    from pixelart_creator.logic.assistant import run_turn
    from pixelart_creator.logic.document import Document

    def _script():
        return [AssistantReply.final("done, nothing to change")]

    conv0 = Conversation().append(Message(role=Role.USER, content="hello"))

    result_openai = run_turn(
        Document(8, 8), conv0, FakeLLMAdapter(_script(), shape="openai")
    )
    result_anthropic = run_turn(
        Document(8, 8), conv0, FakeLLMAdapter(_script(), shape="anthropic")
    )
    assert result_openai.reply.content == result_anthropic.reply.content
    assert len(result_openai.conversation.messages) == len(
        result_anthropic.conversation.messages
    )
