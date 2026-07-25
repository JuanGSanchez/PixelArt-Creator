"""GUI == CLI byte-identity at the UI level (SC-UI-007-1, REQ-P7-UI-007).

The core Phase-7 guarantee: a UI-driven export of a fixed document yields output
**byte-identical** to ``data/export_cli.main`` for the same document + options,
because both drive the identical pure ``export_document`` + ``write_export`` engine
and the GUI adds no encoding/layout of its own. Here the GUI path is the real
off-thread ``Export_Controller`` worker; the CLI path is ``export_cli.main`` called
in-process on the same document saved as a ``.pixproj`` (the installed
``pixelart-export`` console script is intentionally NOT relied upon — it is not
wired yet).

Headless, both themes (autouse ``theme`` fixture). Parametrised across the formats
whose bytes are byte-reproducible per the spec (PNG / sprite-sheet / atlas incl.
JSON sidecar); GIF is byte-reproducible too but slower, so a single PNG + a
sheet + an atlas already prove the no-divergence contract.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data import export_cli
from pixelart_creator.data.project_io import save_project
from pixelart_creator.logic.export import ExportFormat, ExportRequest
from pixelart_creator.ui.export_worker import ExportTarget
from tests.ui._export_helpers import animation_document, single_frame_document


def _gui_export(qtbot, export_controller, document, request, out_path):
    """Run the real off-thread GUI worker for one target; return when it finishes."""
    target = ExportTarget(request=request, out_path=str(out_path), label="parity")
    with qtbot.waitSignal(export_controller.batchFinished, timeout=10000):
        export_controller.submit(document, (target,))


@pytest.mark.parametrize(
    "fmt,cli_args_extra,doc_factory",
    [
        (ExportFormat.PNG, [], lambda: single_frame_document(24, 24)),
        (
            ExportFormat.SPRITE_SHEET,
            ["--columns", "2", "--padding", "1"],
            lambda: animation_document(frames=4, width=12, height=12),
        ),
        (
            ExportFormat.ATLAS,
            ["--padding", "1"],
            lambda: animation_document(frames=4, width=12, height=12),
        ),
    ],
)
def test_sc_ui_007_gui_export_is_byte_identical_to_cli(
    qtbot, export_controller, tmp_path, fmt, cli_args_extra, doc_factory
):
    """SC-UI-007-1: the GUI worker's output bytes == export_cli.main's, per format
    (image bytes AND the JSON sidecar for sheet/atlas)."""
    document = doc_factory()

    # Persist the exact same document the GUI holds, so the CLI loads an equivalent
    # in-memory Document (REQ-P7-DATA-003) and the two paths export the same input.
    pixproj = tmp_path / "doc.pixproj"
    save_project(document, pixproj)

    # --- GUI path (real off-thread controller/worker) ---
    gui_out = tmp_path / "gui.png"
    request = _request_for(fmt)
    _gui_export(qtbot, export_controller, document, request, gui_out)
    assert gui_out.exists()

    # --- CLI path (in-process; NOT the installed console script) ---
    cli_out = tmp_path / "cli.png"
    argv = [
        "--input",
        str(pixproj),
        "--format",
        fmt.value,
        "--output",
        str(cli_out),
        *cli_args_extra,
    ]
    assert export_cli.main(argv) == 0

    # Byte-identical image bytes (the Phase-7 headless-parity guarantee).
    assert gui_out.read_bytes() == cli_out.read_bytes()

    # …and the JSON sidecar for the metadata-bearing formats.
    if fmt in (ExportFormat.SPRITE_SHEET, ExportFormat.ATLAS):
        gui_json = gui_out.with_suffix(".json")
        cli_json = cli_out.with_suffix(".json")
        assert gui_json.exists() and cli_json.exists()
        assert gui_json.read_text(encoding="utf-8") == cli_json.read_text(
            encoding="utf-8"
        )


def _request_for(fmt: ExportFormat) -> ExportRequest:
    """Build the GUI-side request matching the CLI args for ``fmt``."""
    if fmt is ExportFormat.SPRITE_SHEET:
        return ExportRequest(fmt=fmt, columns=2, padding=1, emit_json=True)
    if fmt is ExportFormat.ATLAS:
        return ExportRequest(fmt=fmt, padding=1, emit_json=True)
    return ExportRequest(fmt=fmt)
