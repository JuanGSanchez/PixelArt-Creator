"""Tests for pixelart_creator.data.assistant_cli — headless assistant CLI.

Covers REQ-P14-DATA-008 (SC-D008-1 / SC-D008-2): the Qt-free ``pixelart-assistant``
driver mirrors ``pixelart-run`` — it drives the SAME 14C agentic loop
(:func:`~pixelart_creator.logic.assistant.run_turn`) + trusted dispatch over a
``.pixproj`` and saves the result back through the shipped ``.pixproj`` path, with the
tiered-safety gate reused verbatim (reversible auto-applies; destructive is gate-closed
by default and only runs with ``--approve-destructive``/``--yes`` or an interactive
``y``). Everything is driven through the INJECTED fake adapter + temp-file document I/O
— no network, no real keyring, no Qt (mirrors ``testing/suites/data/test_automation_cli.py``).

Exit codes exercised: ``0`` ok / ``1`` runtime-or-write error / ``2`` bad args or a
defensive load failure / ``3`` not configured.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pytest import MonkeyPatch

from pixelart_creator.data import assistant_cli
from pixelart_creator.data.assistant_cli import build_parser, main
from pixelart_creator.data.llm.anthropic_translator import AnthropicTranslator
from pixelart_creator.data.llm.fake_adapter import FakeLLMAdapter
from pixelart_creator.data.llm.openai_compatible import OpenAICompatibleAdapter
from pixelart_creator.data.project_io import load_project, save_project
from pixelart_creator.logic import assistant
from pixelart_creator.logic.assistant import (
    AssistantReply,
    Role,
    ToolCall,
)
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.tool_catalog import execute_tool_call

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)
TRANSPARENT = (0, 0, 0, 0)


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #


def _doc() -> Document:
    """A fresh 6x6 document (single all-transparent layer)."""
    return Document(6, 6, palette=Palette([RED, BLUE, GREEN]))


def _leaf(doc: Document):
    """The document's first leaf pixel buffer."""
    return iter_layers(doc.frames[0].layers)[0].buffer


def _write_input(tmp_path) -> Path:
    """Write a fresh input .pixproj and return its path."""
    return save_project(_doc(), Path(tmp_path) / "in.pixproj")


def _recolour_call(dst=RED) -> ToolCall:
    """A reversible ``batch_recolour`` tool-call recolouring TRANSPARENT -> ``dst``."""
    return ToolCall(
        "batch_recolour",
        {"color_map": [[list(TRANSPARENT), list(dst)]]},
    )


def _fake(*replies, configured: bool = True) -> FakeLLMAdapter:
    """A scripted, deterministic fake backend (no key/network)."""
    return FakeLLMAdapter(list(replies), configured=configured)


class _FakeTTY(io.StringIO):
    """A stdin-like stream that reports as an interactive TTY (drives the prompt)."""

    def isatty(self) -> bool:  # noqa: D401 - trivial override
        return True


def _run(argv, backend, *, stdin=None):
    """Invoke ``main`` with an injected backend + captured out/err streams."""
    out = io.StringIO()
    err = io.StringIO()
    in_stream = io.StringIO("") if stdin is None else stdin
    rc = main(
        argv,
        backend=backend,
        stdin=in_stream,
        stdout=out,
        stderr=err,
    )
    return rc, out.getvalue(), err.getvalue()


def _base_argv(tmp_path, *, prompt="do it") -> list:
    """The minimal --input/--output/--prompt argv against a fresh input .pixproj."""
    input_path = _write_input(tmp_path)
    output_path = Path(tmp_path) / "out.pixproj"
    argv = [
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]
    if prompt is not None:
        argv += ["--prompt", prompt]
    return argv, input_path, output_path


# --------------------------------------------------------------------------- #
# parser + adapter construction seam                                           #
# --------------------------------------------------------------------------- #


def test_build_parser_requires_core_args():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])  # missing required --input/--output


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_build_backend_openai_kind():
    backend = assistant_cli._build_backend("openai", None, None, "default")
    assert isinstance(backend, OpenAICompatibleAdapter)


def test_build_backend_anthropic_kind():
    backend = assistant_cli._build_backend("anthropic", None, None, "default")
    assert isinstance(backend, AnthropicTranslator)


# --------------------------------------------------------------------------- #
# SC-D008-1 — reversible auto-apply + save (CLI == in-process parity)          #
# --------------------------------------------------------------------------- #


def test_reversible_auto_applies_and_saves(tmp_path):
    argv, _input_path, output_path = _base_argv(tmp_path)
    backend = _fake(
        AssistantReply.calling(_recolour_call(RED)),
        AssistantReply.final("Recoloured to red."),
    )
    rc, out, _err = _run(argv, backend)

    assert rc == 0
    assert output_path.exists()
    saved = load_project(output_path)
    # The reversible op auto-applied and the mutation was saved.
    assert np.array_equal(
        np.unique(_leaf(saved).data.reshape(-1, 4), axis=0),
        np.array([list(RED)], dtype=np.uint8),
    )
    assert "Recoloured to red." in out


def test_cli_result_identical_to_in_process_dispatch(tmp_path):
    # CLI == GUI parity (SC-D008-1): the CLI's saved output equals running the SAME
    # tool-call through the trusted dispatch in-process (the same engine).
    argv, input_path, output_path = _base_argv(tmp_path)
    backend = _fake(
        AssistantReply.calling(_recolour_call(BLUE)),
        AssistantReply.final("done"),
    )
    rc, _out, _err = _run(argv, backend)
    assert rc == 0
    cli_doc = load_project(output_path)

    ref_doc = load_project(input_path)
    execute_tool_call(ref_doc, _recolour_call(BLUE))

    assert np.array_equal(_leaf(cli_doc).data, _leaf(ref_doc).data)


def test_empty_reply_content_writes_nothing_to_stdout(tmp_path):
    # A final reply with empty content still succeeds and saves; nothing is echoed.
    argv, _input_path, output_path = _base_argv(tmp_path)
    backend = _fake(AssistantReply.final(""))
    rc, out, _err = _run(argv, backend)
    assert rc == 0
    assert out == ""
    assert output_path.exists()


def test_prompt_read_from_stdin(tmp_path):
    argv, _input_path, output_path = _base_argv(tmp_path, prompt=None)
    backend = _fake(
        AssistantReply.calling(_recolour_call(GREEN)),
        AssistantReply.final("ok"),
    )
    rc, _out, _err = _run(argv, backend, stdin=io.StringIO("please recolour\n"))
    assert rc == 0
    saved = load_project(output_path)
    assert np.array_equal(
        np.unique(_leaf(saved).data.reshape(-1, 4), axis=0),
        np.array([list(GREEN)], dtype=np.uint8),
    )


def test_system_prompt_seeds_conversation(tmp_path):
    argv, _input_path, _output_path = _base_argv(tmp_path)
    argv += ["--system-prompt", "You are a pixel artist."]
    backend = _fake(AssistantReply.final("hi"))
    rc, _out, _err = _run(argv, backend)
    assert rc == 0
    # The first message presented to the backend is the SYSTEM seed.
    first_conversation = backend.calls[0]
    assert first_conversation.messages[0].role == Role.SYSTEM
    assert first_conversation.messages[0].content == "You are a pixel artist."
    assert first_conversation.messages[1].role == Role.USER


# --------------------------------------------------------------------------- #
# SC-D008-2 — destructive gate-closed by default; runs only with the affordance #
# --------------------------------------------------------------------------- #


def test_destructive_default_deny_leaves_document_byte_identical(tmp_path, monkeypatch):
    # Force batch_recolour DESTRUCTIVE by emptying the reversible allow-list.
    monkeypatch.setattr(assistant, "REVERSIBLE_OPS", frozenset())
    argv, input_path, output_path = _base_argv(tmp_path)
    backend = _fake(
        AssistantReply.calling(_recolour_call(RED)),
        AssistantReply.final("done"),
    )
    rc, _out, _err = _run(argv, backend)

    assert rc == 0  # a declined op is not an error; the turn completes
    # The destructive op was DECLINED (not executed): saved output is byte-identical.
    assert output_path.read_bytes() == input_path.read_bytes()
    saved = load_project(output_path)
    assert np.array_equal(
        np.unique(_leaf(saved).data.reshape(-1, 4), axis=0),
        np.array([list(TRANSPARENT)], dtype=np.uint8),
    )


@pytest.mark.parametrize("flag", ["--approve-destructive", "--yes"])
def test_destructive_runs_with_approve_flag(tmp_path, monkeypatch, flag):
    monkeypatch.setattr(assistant, "REVERSIBLE_OPS", frozenset())
    argv, _input_path, output_path = _base_argv(tmp_path)
    argv.append(flag)
    backend = _fake(
        AssistantReply.calling(_recolour_call(RED)),
        AssistantReply.final("done"),
    )
    rc, _out, _err = _run(argv, backend)

    assert rc == 0
    saved = load_project(output_path)
    # WITH the affordance the destructive op executed and the mutation was saved.
    assert np.array_equal(
        np.unique(_leaf(saved).data.reshape(-1, 4), axis=0),
        np.array([list(RED)], dtype=np.uint8),
    )


def test_interactive_prompt_yes_approves(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "REVERSIBLE_OPS", frozenset())
    argv, _input_path, output_path = _base_argv(tmp_path)  # --prompt (not stdin)
    backend = _fake(
        AssistantReply.calling(_recolour_call(RED)),
        AssistantReply.final("done"),
    )
    rc, _out, err = _run(argv, backend, stdin=_FakeTTY("y\n"))

    assert rc == 0
    assert "approve destructive action" in err  # the [y/N] prompt was shown
    saved = load_project(output_path)
    assert np.array_equal(
        np.unique(_leaf(saved).data.reshape(-1, 4), axis=0),
        np.array([list(RED)], dtype=np.uint8),
    )


def test_interactive_prompt_no_declines(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "REVERSIBLE_OPS", frozenset())
    argv, input_path, output_path = _base_argv(tmp_path)
    backend = _fake(
        AssistantReply.calling(_recolour_call(RED)),
        AssistantReply.final("done"),
    )
    rc, _out, err = _run(argv, backend, stdin=_FakeTTY("n\n"))

    assert rc == 0
    assert "approve destructive action" in err
    # The interactive default-deny answer means the op did NOT run.
    assert output_path.read_bytes() == input_path.read_bytes()


# --------------------------------------------------------------------------- #
# error-path atomicity — exit 1, no partial save                              #
# --------------------------------------------------------------------------- #


def test_error_path_after_partial_apply_does_not_save(tmp_path):
    # A reversible op applies, then the script is exhausted mid-turn -> the loop
    # raises AssistantError (carrying the applied command); the CLI reverts in-memory
    # and DOES NOT save a partial document, exiting non-zero.
    argv, input_path, output_path = _base_argv(tmp_path)
    backend = _fake(AssistantReply.calling(_recolour_call(RED)))  # no final reply
    rc, _out, err = _run(argv, backend)

    assert rc == 1
    assert not output_path.exists()  # no partial document written
    # The input on disk is untouched.
    assert (
        input_path.read_bytes() == _write_input(Path(tempfile.mkdtemp())).read_bytes()
    )
    assert "assistant error" in err


def test_provider_error_no_apply_exits_one(tmp_path):
    # An empty script -> the first respond raises LLMResponseError with nothing applied
    # -> propagates as an LLMError -> exit 1, nothing saved.
    argv, _input_path, output_path = _base_argv(tmp_path)
    backend = _fake()  # empty script: first respond raises
    rc, _out, err = _run(argv, backend)

    assert rc == 1
    assert not output_path.exists()
    assert "provider error" in err


def test_write_error_exits_one(tmp_path):
    input_path = _write_input(tmp_path)
    unwritable = Path(tmp_path) / "no_such_dir" / "out.pixproj"  # missing parent
    argv = [
        "--input",
        str(input_path),
        "--output",
        str(unwritable),
        "--prompt",
        "do it",
    ]
    backend = _fake(AssistantReply.final("nothing to do"))
    rc, _out, err = _run(argv, backend)

    assert rc == 1
    assert "write error" in err


# --------------------------------------------------------------------------- #
# not-configured — exit 3, no network                                         #
# --------------------------------------------------------------------------- #


def test_not_configured_exits_three_no_network(tmp_path):
    argv, _input_path, output_path = _base_argv(tmp_path)
    backend = _fake(AssistantReply.final("unreached"), configured=False)
    rc, _out, err = _run(argv, backend)

    assert rc == 3
    assert "no provider is configured" in err
    # NO network / respond call was ever attempted (nothing consumed the script).
    assert backend.calls == []
    assert backend.remaining == 1
    assert not output_path.exists()


# --------------------------------------------------------------------------- #
# exit code 2 — bad args / defensive load / empty instruction                 #
# --------------------------------------------------------------------------- #


def test_missing_required_arg_exits_two():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_unloadable_project_exits_two(tmp_path):
    argv = [
        "--input",
        str(Path(tmp_path) / "does_not_exist.pixproj"),
        "--output",
        str(Path(tmp_path) / "out.pixproj"),
        "--prompt",
        "do it",
    ]
    backend = _fake(AssistantReply.final("unreached"))
    rc, _out, err = _run(argv, backend)
    assert rc == 2
    assert "input error" in err


def test_empty_instruction_exits_two(tmp_path):
    argv, _input_path, _output_path = _base_argv(tmp_path, prompt="   ")
    backend = _fake(AssistantReply.final("unreached"))
    rc, _out, err = _run(argv, backend)
    assert rc == 2
    assert "no instruction" in err


# --------------------------------------------------------------------------- #
# property-based — the destructive gate-closed security invariant             #
# --------------------------------------------------------------------------- #


@given(
    dst=st.tuples(
        st.integers(0, 255),
        st.integers(0, 255),
        st.integers(0, 255),
        st.integers(0, 255),
    )
)
def test_destructive_default_deny_invariant(dst):
    # For ANY forced-destructive recolour target, running WITHOUT the approve
    # affordance leaves the saved document byte-identical to the input (the op is
    # never executed). Function-scoped fixtures are avoided under @given: use a
    # MonkeyPatch context + a per-example temp dir.
    with MonkeyPatch.context() as mp, tempfile.TemporaryDirectory() as tmp:
        mp.setattr(assistant, "REVERSIBLE_OPS", frozenset())
        input_path = save_project(_doc(), Path(tmp) / "in.pixproj")
        output_path = Path(tmp) / "out.pixproj"
        backend = _fake(
            AssistantReply.calling(_recolour_call(dst)),
            AssistantReply.final("done"),
        )
        rc, _out, _err = _run(
            [
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--prompt",
                "recolour",
            ],
            backend,
        )
        assert rc == 0
        assert output_path.read_bytes() == input_path.read_bytes()
