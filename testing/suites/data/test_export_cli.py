"""Tests for pixelart_creator.data.export_cli (REQ-P7-DATA-003, REQ-P7-LOGIC-013).

The headless, Qt-free CLI driver: it loads a .pixproj via the defensive IO-3 path
and drives the SAME export_document + write_export path the GUI uses, so the CLI
output is byte-identical to the in-process (GUI-substrate) export (SC-L013-1 /
SC-D003-1). Argument grammar + exit-code contract: 0 ok / 1 export|write error /
2 bad args or ProjectIOError. Zero Qt; deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pixelart_creator.data.export_cli import build_parser, main
from pixelart_creator.data.export_io import write_export
from pixelart_creator.data.project_io import load_project, save_project
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import ExportFormat, ExportRequest, export_document

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def make_project(tmp_path: Path, colors=(RED, GREEN, BLUE)) -> Path:
    """Build + save a small multi-frame .pixproj, returning its path."""
    doc = Document(4, 4)
    doc.frames[0].layers[0].buffer.fill(colors[0])
    for color in colors[1:]:
        doc.add_frame().layers[0].buffer.fill(color)
    return save_project(doc, tmp_path / "proj.pixproj")


# --------------------------------------------------------------------------- #
# Exit code 0 — success                                                        #
# --------------------------------------------------------------------------- #


def test_cli_png_export_succeeds(tmp_path: Path) -> None:
    """REQ-P7-DATA-003: a valid PNG export returns exit 0 and writes the file."""
    proj = make_project(tmp_path)
    out = tmp_path / "sprite.png"
    code = main(["--input", str(proj), "--format", "png", "--output", str(out)])
    assert code == 0
    assert out.read_bytes()


def test_cli_sprite_sheet_with_options(tmp_path: Path) -> None:
    """REQ-P7-DATA-003: columns/padding/--no-json options drive the export."""
    proj = make_project(tmp_path)
    out = tmp_path / "sheet.png"
    code = main(
        [
            "--input",
            str(proj),
            "--format",
            "sprite-sheet",
            "--output",
            str(out),
            "--columns",
            "2",
            "--padding",
            "1",
            "--no-json",
        ]
    )
    assert code == 0
    assert out.exists()
    assert not out.with_suffix(".json").exists()  # --no-json suppressed metadata


def test_cli_gif_with_loop(tmp_path: Path) -> None:
    """REQ-P7-DATA-003: the --loop option is threaded into the GIF export."""
    proj = make_project(tmp_path)
    out = tmp_path / "anim.gif"
    code = main(
        ["--input", str(proj), "--format", "gif", "--output", str(out), "--loop", "3"]
    )
    assert code == 0
    assert out.read_bytes()


def test_cli_frame_flag_selects_that_frame(tmp_path: Path) -> None:
    """Regression test for C-01 — proven by reversion in the commit pass.

    The ``--frame`` CLI flag threads into ExportRequest.frame_index so the CLI
    exports the requested frame, not always frame 0.
    """
    proj = make_project(tmp_path, colors=(RED, GREEN, BLUE))
    out = tmp_path / "frame2.png"
    code = main(
        [
            "--input",
            str(proj),
            "--format",
            "png",
            "--output",
            str(out),
            "--frame",
            "2",
        ]
    )
    assert code == 0
    from io import BytesIO

    import numpy as np
    from PIL import Image

    decoded = np.asarray(Image.open(BytesIO(out.read_bytes())).convert("RGBA"))
    assert np.array_equal(decoded, np.full((4, 4, 4), BLUE, dtype=np.uint8))


def test_cli_frame_flag_out_of_range_exits_1(tmp_path: Path) -> None:
    """Regression test for C-01 — proven by reversion in the commit pass.

    An out-of-range ``--frame`` maps to the export-error exit code (1), not a
    silent frame-0 fallback or a crash.
    """
    proj = make_project(tmp_path, colors=(RED, GREEN))
    code = main(
        [
            "--input",
            str(proj),
            "--format",
            "png",
            "--output",
            str(tmp_path / "o.png"),
            "--frame",
            "9",
        ]
    )
    assert code == 1


def test_cli_engine_preset_writes_artifact(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: --preset unity writes the .meta artifact beside the image."""
    proj = make_project(tmp_path)
    out = tmp_path / "sheet.png"
    code = main(
        [
            "--input",
            str(proj),
            "--format",
            "sprite-sheet",
            "--output",
            str(out),
            "--preset",
            "unity",
        ]
    )
    assert code == 0
    assert Path(str(out) + ".meta").exists()


# --------------------------------------------------------------------------- #
# SC-L013-1 / SC-D003-1 — CLI == GUI byte-identity (the core guarantee)        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("fmt", ["png", "gif", "sprite-sheet", "atlas"])
def test_cli_output_is_byte_identical_to_direct_export(
    tmp_path: Path, fmt: str
) -> None:
    """SC-L013-1: CLI output equals the in-process export_document/write_export path.

    Both drive the identical pure engine over the identically-loaded document, so
    every produced file (image + JSON) is byte-for-byte equal.
    """
    proj = make_project(tmp_path)
    cli_out = tmp_path / f"cli.{fmt.split('-')[0]}"
    assert main(["--input", str(proj), "--format", fmt, "--output", str(cli_out)]) == 0

    # The GUI substrate: load the same file, call the shared path directly.
    doc = load_project(proj)
    result = export_document(doc, ExportRequest(fmt=ExportFormat(fmt)))
    direct_out = tmp_path / f"direct.{fmt.split('-')[0]}"
    write_export(result, direct_out)

    assert cli_out.read_bytes() == direct_out.read_bytes()
    if result.metadata_json is not None:
        assert (
            cli_out.with_suffix(".json").read_bytes()
            == direct_out.with_suffix(".json").read_bytes()
        )


def test_cli_max_dimension_parity_non_default(tmp_path: Path) -> None:
    """--max-dimension at a NON-default value is byte-identical CLI==GUI.

    Pairs with C-09 (the --max-dimension flag exists). A larger atlas needs a
    larger max-dimension bound, so this exercises a value that actually differs
    from MAX_ATLAS_DIMENSION and would have failed to pack under the default.
    """
    proj = make_project(tmp_path, colors=(RED, GREEN, BLUE))
    non_default = 64
    cli_out = tmp_path / "cli_atlas.png"
    code = main(
        [
            "--input",
            str(proj),
            "--format",
            "atlas",
            "--output",
            str(cli_out),
            "--max-dimension",
            str(non_default),
        ]
    )
    assert code == 0

    doc = load_project(proj)
    result = export_document(
        doc,
        ExportRequest(fmt=ExportFormat.ATLAS, max_dimension=non_default),
    )
    direct_out = tmp_path / "direct_atlas.png"
    write_export(result, direct_out)

    assert cli_out.read_bytes() == direct_out.read_bytes()
    assert (
        cli_out.with_suffix(".json").read_bytes()
        == direct_out.with_suffix(".json").read_bytes()
    )


# --------------------------------------------------------------------------- #
# Exit code 2 — bad args / ProjectIOError (defensive load)                     #
# --------------------------------------------------------------------------- #


def test_cli_missing_required_arg_exits_2(tmp_path: Path) -> None:
    """Argparse rejects a missing required argument with exit code 2."""
    with pytest.raises(SystemExit) as exc:
        main(["--format", "png", "--output", str(tmp_path / "o.png")])
    assert exc.value.code == 2


def test_cli_unknown_format_exits_2(tmp_path: Path) -> None:
    """Argparse rejects an out-of-vocabulary --format with exit code 2."""
    proj = make_project(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["--input", str(proj), "--format", "webp", "--output", "o"])
    assert exc.value.code == 2


def test_cli_malformed_project_exits_2(tmp_path: Path) -> None:
    """SC-D003-1: a malformed .pixproj raises ProjectIOError -> exit 2 (no crash)."""
    bad = tmp_path / "bad.pixproj"
    bad.write_text("{ not valid json", encoding="utf-8")
    code = main(
        ["--input", str(bad), "--format", "png", "--output", str(tmp_path / "o.png")]
    )
    assert code == 2


def test_cli_missing_project_exits_2(tmp_path: Path) -> None:
    """SC-D003-1: a missing input file is handled defensively (exit 2)."""
    missing = tmp_path / "does-not-exist.pixproj"
    code = main(
        [
            "--input",
            str(missing),
            "--format",
            "png",
            "--output",
            str(tmp_path / "o.png"),
        ]
    )
    assert code == 2


# --------------------------------------------------------------------------- #
# Exit code 1 — export / write error                                          #
# --------------------------------------------------------------------------- #


def test_cli_unknown_tag_exits_1(tmp_path: Path) -> None:
    """An export-domain error (unknown tag) maps to exit code 1."""
    proj = make_project(tmp_path)
    code = main(
        [
            "--input",
            str(proj),
            "--format",
            "gif",
            "--output",
            str(tmp_path / "o.gif"),
            "--tag",
            "nope",
        ]
    )
    assert code == 1


def test_cli_write_error_exits_1(tmp_path: Path) -> None:
    """An OSError while writing (output path is a directory) maps to exit 1."""
    proj = make_project(tmp_path)
    out_dir = tmp_path / "outdir"
    out_dir.mkdir()
    code = main(["--input", str(proj), "--format", "png", "--output", str(out_dir)])
    assert code == 1


# --------------------------------------------------------------------------- #
# Parser grammar                                                               #
# --------------------------------------------------------------------------- #


def test_build_parser_exposes_the_grammar() -> None:
    """The parser accepts the documented option grammar and defaults."""
    parser = build_parser()
    args = parser.parse_args(
        ["--input", "p.pixproj", "--format", "atlas", "--output", "out.png"]
    )
    assert args.input == "p.pixproj"
    assert args.format == "atlas"
    assert args.preset == "none"  # default
    assert args.json is True  # default on
    args2 = parser.parse_args(
        ["--input", "p", "--format", "png", "--output", "o", "--no-json"]
    )
    assert args2.json is False
