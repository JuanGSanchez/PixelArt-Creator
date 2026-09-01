# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Headless, Qt-free assistant CLI driver (the ``pixelart-assistant`` entrypoint).

Part of the AI-assistant feature, Phase 14 (REQ-P14-DATA-008; ADR-0042 §2).
The headless embedding of the
model-agnostic AI assistant: it **mirrors the shipped** ``pixelart-run`` automation CLI
(:mod:`pixelart_creator.data.automation_cli`) so the assistant is drivable without a GUI
— in scripts, CI, or automation. It loads a ``.pixproj`` through the shipped defensive
:func:`~pixelart_creator.data.project_io.load_project` (IO-3 — never ``eval``/``exec``),
constructs an :class:`~pixelart_creator.data.llm.port.LLMPort` adapter (14D) from the
provider flags (or takes an **injected** backend — the fake adapter in CI, no key/
network), drives the **same** trusted 14C agentic loop
(:func:`~pixelart_creator.logic.assistant.run_turn`) with the 14A tool catalog against
the loaded document, and saves the result back through the shipped ``.pixproj`` path —
so a headless run is behaviour-identical to the GUI driving the same assistant turn
(CLI==GUI, the ``pixelart-run`` precedent). It imports only ``logic/`` + ``data/`` (zero
Qt) and lives in ``data/`` so ``check_layering`` guards its Qt-freedom (the
ADR-0020/0022 blind-spot lesson; a ``cli/`` sibling would be unscanned).

**Tiered safety, headless (ADR-0041 §2, ADR-0042 §2).** The loop's tiered gate is reused
verbatim: a **reversible** op auto-applies (undo-backed); a **destructive** op is
**gate-closed by default (deny)**. Passing ``--approve-destructive`` (alias ``--yes``)
supplies an approve-all :data:`~pixelart_creator.logic.assistant.ConfirmCallback`;
without it destructive ops are **declined and never executed** (reported via the loop's
``Role.TOOL`` result). When attached to a TTY (and the instruction did **not** come from
stdin), an interactive ``[y/N]`` prompt is offered per destructive action; the safe
default with no answer is still deny.

**Error-path atomicity (ADR-0041 §1 amendment).** On a mid-turn
:class:`~pixelart_creator.logic.assistant.AssistantError`, the CLI uses
:attr:`~pixelart_creator.logic.assistant.AssistantError.applied_commands` to **revert**
the in-memory document (``apply ∘ undo = identity``) and **does not save** a partially
mutated document — the on-disk result stays consistent (byte-identical to the input) and
the process exits non-zero with the error reported.

**Config seam (Qt-free).** The GUI dock reads its non-secret provider config from
``QSettings`` (Qt) via ``ui/provider_config_dialog.build_backend`` — unavailable here
(zero Qt). This CLI therefore takes ``--provider``/``--base-url``/``--model`` as flags
and mirrors that module's adapter-construction logic Qt-free; the API **key** is read
lazily from the shared OS keyring (:mod:`pixelart_creator.data.llm.token_store`) inside
the adapter, never passed on the command line. ``is_configured() == False`` (no key/
endpoint) → a clear "configure a provider/key first" message + a non-zero exit, no
network, no crash.

``pyproject`` wires ``pixelart-assistant =
"pixelart_creator.data.assistant_cli:main"`` as a console script — that edit
belongs to the packaging layer (Article IX), not here.

Exit codes: ``0`` ok / ``1`` runtime error (``AssistantError``/``LLMError``/write
error) / ``2`` bad args or a defensive load failure (``ProjectIOError``) / ``3`` not
configured (no provider endpoint + key).
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Optional, Sequence, TextIO

from pixelart_creator.data.llm.anthropic_translator import AnthropicTranslator
from pixelart_creator.data.llm.openai_compatible import OpenAICompatibleAdapter
from pixelart_creator.data.llm.port import LLMError, LLMPort
from pixelart_creator.data.project_io import (
    ProjectIOError,
    load_project,
    save_project,
)
from pixelart_creator.logic.assistant import (
    AssistantError,
    ChatBackend,
    ConfirmationRequest,
    ConfirmCallback,
    Conversation,
    Message,
    Role,
    deny_all,
    run_turn,
)
from pixelart_creator.logic.document import Document

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_RUNTIME_ERROR = 1
_EXIT_BAD_ARGS = 2
_EXIT_NOT_CONFIGURED = 3

#: Provider-kind identifiers — MIRROR ``ui/provider_config_dialog`` (which is Qt and
#: cannot be imported here): they double as the keyring service namespace segment
#: (``pixelart-creator:assistant:{provider}``) and the adapter's ``provider`` arg, so
#: the key the user stored via the dock is the key this CLI's adapter loads.
#: Module-local vocabulary (ADR-0001), not a numeric constant.
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"

#: The keyring account the single-user key is stored under (matches ``data/llm``'s
#: ``_DEFAULT_ACCOUNT`` + the dock's ``_ACCOUNT`` so the adapter loads the same key).
_DEFAULT_ACCOUNT = "default"

#: Default endpoints per provider kind (the user may override with ``--base-url``).
#: Mirrors the dock's ``_DEFAULT_BASE_URLS``.
_DEFAULT_BASE_URLS = {
    PROVIDER_OPENAI: "https://api.openai.com/v1",
    PROVIDER_ANTHROPIC: "https://api.anthropic.com",
}


def build_parser() -> argparse.ArgumentParser:
    """Build the ``pixelart-assistant`` argument parser (grammar per ADR-0042 §2)."""
    parser = argparse.ArgumentParser(
        prog="pixelart-assistant",
        description=(
            "Headless PixelArt Creator AI assistant (Qt-free; mirrors pixelart-run). "
            "Drives the agentic loop over a .pixproj and saves the result back."
        ),
    )
    parser.add_argument("--input", required=True, help="input .pixproj path")
    parser.add_argument("--output", required=True, help="output .pixproj path")
    parser.add_argument(
        "--prompt",
        default=None,
        help="the instruction for the assistant (read from stdin if omitted)",
    )
    parser.add_argument(
        "--system-prompt",
        default=None,
        help="optional system message seeding the conversation",
    )
    parser.add_argument(
        "--provider",
        default=PROVIDER_OPENAI,
        help=(
            f"provider kind: {PROVIDER_OPENAI!r} (OpenAI-compatible: OpenAI/Gemini/"
            f"Ollama/llama.cpp) or {PROVIDER_ANTHROPIC!r} (native Anthropic)"
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="provider endpoint base URL (defaults per provider kind)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="provider model name sent on every request",
    )
    parser.add_argument(
        "--account",
        default=_DEFAULT_ACCOUNT,
        help="keyring account the API key is stored under",
    )
    parser.add_argument(
        "--approve-destructive",
        "--yes",
        dest="approve_destructive",
        action="store_true",
        help=(
            "auto-approve DESTRUCTIVE tool-calls (gate-closed by default: without this "
            "flag destructive actions are declined and never executed)"
        ),
    )
    return parser


def _build_backend(
    provider: str,
    base_url: Optional[str],
    model: Optional[str],
    account: str,
) -> LLMPort:
    """Construct the matching ``data/llm`` adapter (mirrors the dock ``build_backend``).

    Anthropic uses the native translator; everything else uses the OpenAI-compatible
    client. Construction is cheap — the key is read lazily from the keyring at request
    time — so a "not configured" adapter (no key/endpoint) is still safe to build and
    simply reports ``is_configured() == False``.
    """
    resolved_base = base_url or _DEFAULT_BASE_URLS.get(
        provider, _DEFAULT_BASE_URLS[PROVIDER_OPENAI]
    )
    resolved_model = model or ""
    if provider == PROVIDER_ANTHROPIC:
        return AnthropicTranslator(
            provider=provider,
            base_url=resolved_base,
            model=resolved_model,
            account=account,
        )
    return OpenAICompatibleAdapter(
        provider=provider,
        base_url=resolved_base,
        model=resolved_model,
        account=account,
    )


def _approve_all(request: ConfirmationRequest) -> bool:  # noqa: ARG001 - protocol shape
    """Approve every destructive action; the :data:`ConfirmCallback` for ``--yes``."""
    return True


def _make_confirm(
    approve_destructive: bool,
    *,
    interactive: bool,
    in_stream: TextIO,
    err_stream: TextIO,
) -> ConfirmCallback:
    """Build the :data:`ConfirmCallback` for this run's tiered-safety posture.

    ``--approve-destructive``/``--yes`` → approve every destructive op. Otherwise, when
    ``interactive`` (attached to a TTY, instruction not taken from stdin), prompt
    ``[y/N]`` per destructive action on ``err_stream`` and read the answer from
    ``in_stream``. With neither, the gate stays **closed**
    (:func:`~pixelart_creator.logic.assistant.deny_all`) — destructive ops are declined
    and never executed (SC-D008-2).
    """
    if approve_destructive:
        return _approve_all
    if not interactive:
        return deny_all

    def _confirm(request: ConfirmationRequest) -> bool:
        err_stream.write(
            "pixelart-assistant: approve destructive action "
            f'"{request.tool_call.name}"? [y/N] '
        )
        err_stream.flush()
        answer = in_stream.readline().strip().lower()
        return answer in ("y", "yes")

    return _confirm


def _isatty(stream: TextIO) -> bool:
    """Return whether ``stream`` is an interactive TTY (defensive: never raises)."""
    try:
        return bool(stream.isatty())
    except (ValueError, OSError):  # pragma: no cover - closed/detached stream
        return False


def main(
    argv: Optional[Sequence[str]] = None,
    *,
    backend: Optional[ChatBackend] = None,
    load_document: Callable[[str], Document] = load_project,
    save_document: Callable[[Document, str], object] = save_project,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    """Run the headless assistant CLI; return the process exit code.

    Loads ``--input`` (IO-3), resolves the instruction (``--prompt`` or stdin),
    constructs (or uses the injected) backend, drives one bounded agentic turn with the
    tiered gate, saves ``--output`` on success, and maps failures to exit codes (``0``
    ok / ``1`` runtime-or-write error / ``2`` bad args or defensive load error / ``3``
    not configured). See the module docstring.

    The ``backend`` and ``load_document``/``save_document`` parameters are **injectable
    seams** (mirroring the dock's ``build_backend`` seam): the test suite
    passes a deterministic
    fake :class:`~pixelart_creator.logic.assistant.ChatBackend` (no key/network) and, if
    desired, in-memory document I/O, so the default-gate tests need no provider.

    Args:
        argv: CLI arguments (defaults to ``sys.argv[1:]``).
        backend: An injected backend; when ``None`` it is built from the provider flags.
        load_document: The ``.pixproj`` loader (defaults to the shipped defensive one).
        save_document: The ``.pixproj`` saver (defaults to the shipped saver).
        stdin/stdout/stderr: Injectable streams (default to the real process streams).
    """
    in_stream = sys.stdin if stdin is None else stdin
    out_stream = sys.stdout if stdout is None else stdout
    err_stream = sys.stderr if stderr is None else stderr

    parser = build_parser()
    args = parser.parse_args(argv)  # argparse exits 2 on a bad grammar itself.

    prompt_from_stdin = args.prompt is None
    instruction = (in_stream.read() if prompt_from_stdin else args.prompt).strip()
    if not instruction:
        err_stream.write(
            "pixelart-assistant: no instruction (use --prompt or pipe it on stdin)\n"
        )
        return _EXIT_BAD_ARGS

    try:
        document = load_document(args.input)
    except ProjectIOError as exc:
        err_stream.write(f"pixelart-assistant: input error: {exc}\n")
        return _EXIT_BAD_ARGS

    active_backend: ChatBackend = (
        backend
        if backend is not None
        else _build_backend(args.provider, args.base_url, args.model, args.account)
    )
    if not active_backend.is_configured():
        err_stream.write(
            "pixelart-assistant: no provider is configured — configure a provider "
            "endpoint + API key first (the assistant dock, or --provider/--base-url/"
            "--model + a stored key); nothing was run.\n"
        )
        return _EXIT_NOT_CONFIGURED

    interactive = (
        not args.approve_destructive and not prompt_from_stdin and _isatty(in_stream)
    )
    confirm = _make_confirm(
        args.approve_destructive,
        interactive=interactive,
        in_stream=in_stream,
        err_stream=err_stream,
    )

    conversation = Conversation()
    if args.system_prompt:
        conversation = conversation.append(
            Message(role=Role.SYSTEM, content=args.system_prompt)
        )
    conversation = conversation.append(Message(role=Role.USER, content=instruction))

    try:
        result = run_turn(document, conversation, active_backend, confirm=confirm)
    except AssistantError as exc:
        # Error-path atomicity (ADR-0041 §1): revert any partially-applied ops in
        # reverse so the in-memory document is byte-identical, and DO NOT save a
        # partially-mutated document — the on-disk result stays consistent.
        for command in reversed(exc.applied_commands):
            command.undo()
        err_stream.write(f"pixelart-assistant: assistant error: {exc}\n")
        return _EXIT_RUNTIME_ERROR
    except LLMError as exc:
        # A backend failure with no partial apply (a mid-turn failure after an apply is
        # wrapped as AssistantError above); nothing was mutated — do not save.
        err_stream.write(f"pixelart-assistant: provider error: {exc}\n")
        return _EXIT_RUNTIME_ERROR

    if result.reply.content:
        out_stream.write(result.reply.content + "\n")

    try:
        save_document(document, args.output)
    except OSError as exc:
        err_stream.write(f"pixelart-assistant: write error: {exc}\n")
        return _EXIT_RUNTIME_ERROR

    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover - module CLI shim
    sys.exit(main())
