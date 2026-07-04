"""Headless, Qt-free automation CLI driver (the ``pixelart-run`` entrypoint).

The automation entrypoint (REQ-P8-LOGIC-014, REQ-P8-UI-010; ADR-0022 §3): it loads
a ``.pixproj`` through the shipped defensive
:func:`~pixelart_creator.data.project_io.load_project` (IO-3 — every field
type/bounds-checked, malformed/unknown-version → ``ProjectIOError``, never
``eval``/``exec``) and a ``.pixmacro`` through the defensive
:func:`~pixelart_creator.data.macro_io.load_macro`, then replays the macro through
the **same** trusted :func:`~pixelart_creator.logic.scripting.dispatch` the GUI
drives (via :func:`~pixelart_creator.logic.macro.replay`) — so the resulting
document is **state-identical** to the GUI running the same automation on the same
input (CLI==GUI). It imports only ``logic/`` + ``data/`` (zero Qt) and lives in
``data/`` so ``check_layering`` guards its Qt-freedom (the ADR-0020 lesson; a
top-level ``cli/`` package would be an unscanned blind spot).

Importing :mod:`logic.scripting` here wires the trusted dispatcher into
:mod:`logic.macro` (so ``replay`` works) and registers the built-in DSL ops.

``pyproject`` wires ``pixelart-run = "pixelart_creator.data.automation_cli:main"``
as a console script — that edit is **AGT-09's** (Article IX, T8D-04), not here.

Exit codes: ``0`` ok / ``1`` automation failure (``ScriptError``/``MacroError``/
``PluginError``/``BatchError``/``ProcgenError``/write error) / ``2`` bad args or a
defensive load failure (``ProjectIOError``/``MacroIOError``).
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from typing import Dict, List, Optional, Sequence

from pixelart_creator.data.macro_io import MacroIOError, load_macro
from pixelart_creator.data.project_io import (
    ProjectIOError,
    load_project,
    save_project,
)
from pixelart_creator.logic import scripting  # wires macro.replay dispatcher
from pixelart_creator.logic.batch_ops import BatchError
from pixelart_creator.logic.macro import Macro, MacroError, Op, replay
from pixelart_creator.logic.plugins import PluginError
from pixelart_creator.logic.procgen import ProcgenError

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_RUNTIME_ERROR = 1
_EXIT_BAD_ARGS = 2

#: Automation errors that map to the runtime-failure exit code (1).
_RUNTIME_ERRORS = (
    scripting.ScriptError,
    MacroError,
    PluginError,
    BatchError,
    ProcgenError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the ``pixelart-run`` argument parser (grammar per ADR-0022 §3)."""
    parser = argparse.ArgumentParser(
        prog="pixelart-run",
        description="Headless PixelArt Creator automation (state-identical to GUI).",
    )
    parser.add_argument("--input", required=True, help="input .pixproj path")
    parser.add_argument("--macro", required=True, help="macro .pixmacro path")
    parser.add_argument("--output", required=True, help="output .pixproj path")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="override the seed for ops that recorded none",
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="inject/override a macro param (repeatable)",
    )
    return parser


def _parse_params(raw: Sequence[str]) -> Dict[str, object]:
    """Parse ``KEY=VALUE`` overrides; VALUE is int if numeric else the raw string.

    Raises:
        ValueError: If an entry has no ``=`` separator.
    """
    overrides: Dict[str, object] = {}
    for entry in raw:
        if "=" not in entry:
            raise ValueError(f"--param must be KEY=VALUE, got {entry!r}")
        key, _, value = entry.partition("=")
        key = key.strip()
        if not key:
            raise ValueError(f"--param has an empty key: {entry!r}")
        try:
            overrides[key] = int(value)
        except ValueError:
            overrides[key] = value
    return overrides


def _apply_overrides(
    macro: Macro, seed: Optional[int], overrides: Dict[str, object]
) -> Macro:
    """Return a copy of ``macro`` with CLI ``--seed``/``--param`` overrides applied.

    ``--seed`` fills in ops whose recorded seed is ``None`` (recorded seeds win, so
    replay stays deterministic); ``--param`` values are merged into each op's params.
    """
    if seed is None and not overrides:
        return macro
    new_ops: List[Op] = []
    for op in macro.ops:
        params = dict(op.params)
        params.update(overrides)
        new_seed = op.seed if op.seed is not None else seed
        new_ops.append(dataclasses.replace(op, params=params, seed=new_seed))
    return dataclasses.replace(macro, ops=tuple(new_ops))


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the headless automation CLI; return the process exit code.

    Loads ``--input`` (IO-3) + ``--macro`` (defensive), applies ``--seed``/``--param``
    overrides, replays through the shared trusted dispatcher, writes ``--output``,
    and maps failures to exit codes (``0`` ok / ``1`` automation-or-write error /
    ``2`` bad args or defensive load error). See the module docstring.
    """
    parser = build_parser()
    args = parser.parse_args(argv)  # argparse exits 2 on a bad grammar itself.

    try:
        overrides = _parse_params(args.param)
    except ValueError as exc:
        sys.stderr.write(f"pixelart-run: bad --param: {exc}\n")
        return _EXIT_BAD_ARGS

    try:
        document = load_project(args.input)
    except ProjectIOError as exc:
        sys.stderr.write(f"pixelart-run: input error: {exc}\n")
        return _EXIT_BAD_ARGS

    try:
        macro = load_macro(args.macro)
    except MacroIOError as exc:
        sys.stderr.write(f"pixelart-run: macro error: {exc}\n")
        return _EXIT_BAD_ARGS

    try:
        macro = _apply_overrides(macro, args.seed, overrides)
        replay(document, macro)
    except _RUNTIME_ERRORS as exc:
        sys.stderr.write(f"pixelart-run: automation error: {exc}\n")
        return _EXIT_RUNTIME_ERROR

    try:
        save_project(document, args.output)
    except OSError as exc:
        sys.stderr.write(f"pixelart-run: write error: {exc}\n")
        return _EXIT_RUNTIME_ERROR

    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover - module CLI shim
    sys.exit(main())
