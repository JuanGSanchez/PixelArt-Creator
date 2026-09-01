# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Headless, Qt-free CLI export driver (the ``pixelart-export`` entrypoint).

This is the automation entrypoint (REQ-P7-LOGIC-013, REQ-P7-DATA-003): it loads a
``.pixproj`` through the shipped defensive
:func:`~pixelart_creator.data.project_io.load_project` (IO-3 — every field
type/bounds-checked, malformed/unknown-version → ``ProjectIOError``, never
``eval``/``exec``), then drives the **same** pure
:func:`~pixelart_creator.logic.export.export_document` +
:func:`~pixelart_creator.data.export_io.write_export` path the GUI uses — so the
CLI output is byte-identical to the GUI export of the same document + parameters
(CLI==GUI, REQ-P7-UI-007). It imports only ``logic/`` + ``data/`` (zero Qt); it is
placed in ``data/`` so ``check_layering`` guards its Qt-freedom (ADR-0020, a
top-level ``cli/`` package would be an unscanned blind spot).

``pyproject`` wires ``pixelart-export = "pixelart_creator.data.export_cli:main"``
as a console script — that edit is **AGT-09's** (Article IX), not authored here.

Exit codes: ``0`` ok / ``1`` export-or-pack/write error / ``2`` bad args or
``ProjectIOError``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Optional, Sequence

from pixelart_creator.data.export_io import write_engine_preset, write_export
from pixelart_creator.data.project_io import ProjectIOError, load_project
from pixelart_creator.logic.atlas import AtlasError
from pixelart_creator.logic.export import (
    EnginePreset,
    ExportError,
    ExportFormat,
    ExportRequest,
    export_document,
)

__all__ = ["main", "build_parser"]

_EXIT_OK = 0
_EXIT_EXPORT_ERROR = 1
_EXIT_BAD_ARGS = 2

_FORMAT_BY_ARG: Dict[str, ExportFormat] = {f.value: f for f in ExportFormat}
_PRESET_BY_ARG: Dict[str, EnginePreset] = {p.value: p for p in EnginePreset}


def build_parser() -> argparse.ArgumentParser:
    """Build the ``pixelart-export`` argument parser (grammar per ADR-0020)."""
    parser = argparse.ArgumentParser(
        prog="pixelart-export",
        description="Headless PixelArt Creator export — byte-identical to the GUI.",
    )
    parser.add_argument("--input", required=True, help="input .pixproj path")
    parser.add_argument(
        "--format",
        required=True,
        choices=sorted(_FORMAT_BY_ARG),
        help="export format",
    )
    parser.add_argument(
        "--preset",
        choices=sorted(_PRESET_BY_ARG),
        default=EnginePreset.NONE.value,
        help="engine preset (default: none)",
    )
    parser.add_argument("--output", required=True, help="output image path")
    parser.add_argument("--columns", type=int, help="sprite-sheet columns")
    parser.add_argument("--padding", type=int, help="inter-sprite padding, px")
    parser.add_argument("--loop", type=int, help="GIF loop count (0 = forever)")
    parser.add_argument("--tag", help="frame tag name (default: whole document)")
    parser.add_argument(
        "--frame",
        type=int,
        default=0,
        help="frame index to export for PNG (default: 0, the first frame)",
    )
    parser.add_argument(
        "--max-dimension",
        type=int,
        help="maximum atlas dimension, px (default: MAX_ATLAS_DIMENSION)",
    )
    parser.add_argument(
        "--json",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="emit sprite-sheet/atlas JSON metadata (default: on)",
    )
    return parser


def _build_request(args: argparse.Namespace) -> ExportRequest:
    """Assemble an :class:`ExportRequest` from parsed args (constants for defaults)."""
    fmt = _FORMAT_BY_ARG[args.format]
    preset = _PRESET_BY_ARG[args.preset]
    fields: Dict[str, object] = {
        "fmt": fmt,
        "preset": preset,
        "emit_json": args.json,
        "frame_index": args.frame,
    }
    if args.columns is not None:
        fields["columns"] = args.columns
    if args.padding is not None:
        fields["padding"] = args.padding
    if args.loop is not None:
        fields["loop"] = args.loop
    if args.tag is not None:
        fields["tag"] = args.tag
    if args.max_dimension is not None:
        fields["max_dimension"] = args.max_dimension
    return ExportRequest(**fields)  # type: ignore[arg-type]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the headless export CLI; return the process exit code.

    Loads the ``.pixproj`` via IO-3, drives the shared
    :func:`~pixelart_creator.logic.export.export_document` +
    :func:`~pixelart_creator.data.export_io.write_export` path (and the engine
    preset, if requested), and maps failures to exit codes: ``0`` ok /
    ``1`` :class:`ExportError`/:class:`AtlasError`/write error /
    ``2`` bad args or :class:`ProjectIOError`.
    """
    parser = build_parser()
    args = parser.parse_args(argv)  # argparse exits 2 on a bad grammar itself.

    try:
        document = load_project(args.input)
    except ProjectIOError as exc:
        sys.stderr.write(f"pixelart-export: input error: {exc}\n")
        return _EXIT_BAD_ARGS

    try:
        request = _build_request(args)
        result = export_document(document, request)
    except (ExportError, AtlasError) as exc:
        sys.stderr.write(f"pixelart-export: export error: {exc}\n")
        return _EXIT_EXPORT_ERROR

    try:
        write_export(result, args.output)
        if request.preset is not EnginePreset.NONE and result.metadata is not None:
            write_engine_preset(request.preset, result.metadata, args.output)
    except OSError as exc:
        sys.stderr.write(f"pixelart-export: write error: {exc}\n")
        return _EXIT_EXPORT_ERROR

    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover - module CLI shim
    sys.exit(main())
