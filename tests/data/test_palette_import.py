"""Tests for pixelart_creator.data.palette_import (load_palette).

Covers REQ-P7-DATA-001 (palette-file parser) and REQ-P7-DATA-005 (defensive
error contract) for the drag-drop import feature. Maps to Gherkin SC-D001-1..5:
valid ``.gpl`` / ``.hex`` / ``.pal`` parse to an ordered Palette (file order,
correct channels), and every failure mode (unknown extension, malformed content,
oversized, empty, unreadable, non-UTF-8/binary) is normalised to the single
catchable ``PaletteImportError``.

All fixtures are written under ``tmp_path`` (xdist-safe, portable). The grammar
itself lives in ``logic.palette_io``; these tests exercise the path→Palette
bridge and its error normalisation, not the grammar internals.
"""

from __future__ import annotations

import inspect

import pytest

from pixelart_creator.data import palette_import
from pixelart_creator.data.file_import import FileImportError, PaletteImportError
from pixelart_creator.data.palette_import import load_palette
from pixelart_creator.logic.constants import MAX_PALETTE_SIZE
from pixelart_creator.logic.palette import Palette

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSLUCENT = (10, 20, 30, 128)


# --------------------------------------------------------------------------- #
# fixture builders (tmp_path)                                                 #
# --------------------------------------------------------------------------- #


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _gpl(*rgb_rows, header=True, name="Sample"):
    lines = []
    if header:
        lines.append("GIMP Palette")
    lines += [f"Name: {name}", "Columns: 0", "# a comment", ""]
    lines += [f"{r} {g} {b}\tname{i}" for i, (r, g, b) in enumerate(rgb_rows)]
    return "\n".join(lines) + "\n"


def _pal(*rgb_rows):
    lines = ["JASC-PAL", "0100", str(len(rgb_rows))]
    lines += [f"{r} {g} {b}" for (r, g, b) in rgb_rows]
    return "\n".join(lines) + "\n"


def _hex(*lines):
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# valid parses (SC-D001-1/-2/-3) — ordered Palette, correct channels          #
# --------------------------------------------------------------------------- #


def test_load_valid_gpl_in_file_order(tmp_path):
    # SC-D001-1: N colour rows -> N opaque colours in file order.
    path = _write(tmp_path, "p.gpl", _gpl((255, 0, 0), (0, 255, 0), (0, 0, 255)))
    result = load_palette(path)
    assert isinstance(result, Palette)
    assert result.colors() == [RED, GREEN, BLUE]  # gpl is opaque (A=255)


def test_load_valid_hex_6_digit_in_file_order(tmp_path):
    # SC-D001-2: one RRGGBB per line, '#' optional -> RGB opaque, in order.
    path = _write(tmp_path, "p.hex", _hex("ff0000", "#00FF00", "0000ff"))
    assert load_palette(path).colors() == [RED, GREEN, BLUE]


def test_load_hex_8_digit_carries_alpha_last(tmp_path):
    # research 1.2: .hex 8-digit is RRGGBBAA (alpha last), not ARGB.
    path = _write(tmp_path, "p.hex", _hex("0a141e80"))
    assert load_palette(path).colors() == [TRANSLUCENT]


def test_load_valid_pal_declared_colours_in_order(tmp_path):
    # SC-D001-3: JASC-PAL header + count + rows -> opaque colours in order.
    path = _write(tmp_path, "p.pal", _pal((255, 0, 0), (0, 255, 0), (0, 0, 255)))
    assert load_palette(path).colors() == [RED, GREEN, BLUE]


def test_load_accepts_str_path(tmp_path):
    path = _write(tmp_path, "p.gpl", _gpl((1, 2, 3)))
    assert load_palette(str(path)).colors() == [(1, 2, 3, 255)]


def test_load_is_deterministic(tmp_path):
    # NFR-2: identical input -> identical output.
    path = _write(tmp_path, "p.hex", _hex("112233", "445566"))
    assert load_palette(path) == load_palette(path)


def test_gpl_skips_comments_columns_and_blank_lines(tmp_path):
    text = "\n".join(
        [
            "GIMP Palette",
            "Name: With Junk",
            "Columns: 16",
            "# leading comment",
            "",
            "   ",  # whitespace-only
            "255 0 0",
            "# mid comment",
            "0 0 255",
        ]
    )
    path = _write(tmp_path, "p.gpl", text)
    assert load_palette(path).colors() == [RED, BLUE]


def test_pal_at_ceiling_is_accepted(tmp_path):
    # Exactly MAX_PALETTE_SIZE colours is allowed (boundary).
    rows = [(i % 256, 0, 0) for i in range(MAX_PALETTE_SIZE)]
    path = _write(tmp_path, "p.pal", _pal(*rows))
    assert len(load_palette(path)) == MAX_PALETTE_SIZE


# --------------------------------------------------------------------------- #
# defensive errors — all -> PaletteImportError (SC-D001-4/-5, SC-D005-*)      #
# --------------------------------------------------------------------------- #


def test_unknown_extension_rejected_before_read(tmp_path):
    # Rejected on extension alone, even if the file exists.
    path = _write(tmp_path, "p.txt", "ff0000")
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_unsupported_palette_ext_aco_rejected(tmp_path):
    # Deferred binary format (CL-A6) is not a v1 palette format.
    path = _write(tmp_path, "p.aco", "whatever")
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_malformed_gpl_header_rejected(tmp_path):
    # SC-D001-4: wrong magic line.
    path = _write(tmp_path, "p.gpl", "NOT A PALETTE\n255 0 0\n")
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_malformed_gpl_non_integer_row_rejected(tmp_path):
    # SC-D001-4: non-numeric colour row.
    path = _write(tmp_path, "p.gpl", _gpl().rstrip("\n") + "\nxx yy zz\n")
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_gpl_out_of_range_channel_rejected(tmp_path):
    path = _write(tmp_path, "p.gpl", "GIMP Palette\n300 0 0\n")
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_malformed_pal_bad_count_rejected(tmp_path):
    path = _write(tmp_path, "p.pal", "JASC-PAL\n0100\nNOTANUMBER\n255 0 0\n")
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_malformed_hex_bad_token_rejected(tmp_path):
    path = _write(tmp_path, "p.hex", _hex("ff0000", "nothex!"))
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_oversized_palette_rejected_not_truncated(tmp_path):
    # SC-D001-5: > MAX_PALETTE_SIZE colours -> error (never silently truncated).
    text = _hex(*[f"{i % 256:02x}0000" for i in range(MAX_PALETTE_SIZE + 1)])
    path = _write(tmp_path, "big.hex", text)
    with pytest.raises(PaletteImportError):
        load_palette(path)


@pytest.mark.parametrize(
    "name, text",
    [
        ("empty.hex", ""),
        ("blank.hex", "\n   \n\n"),
        ("comments.hex", "# only\n# comments\n"),
    ],
)
def test_empty_palette_rejected(tmp_path, name, text):
    # A zero-colour result is an error, not an empty Palette.
    path = _write(tmp_path, name, text)
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(PaletteImportError):
        load_palette(tmp_path / "nope.gpl")


def test_binary_non_utf8_content_rejected(tmp_path):
    # A RIFF/binary .pal (non-UTF-8 bytes) -> UnicodeError -> PaletteImportError.
    path = tmp_path / "binary.pal"
    path.write_bytes(b"RIFF\x00\xff\xfe\x80\x81\x82PAL data\x00\x01")
    with pytest.raises(PaletteImportError):
        load_palette(path)


def test_every_failure_is_caught_by_the_shared_base(tmp_path):
    # SC-D005-3: PaletteImportError is a FileImportError.
    path = _write(tmp_path, "p.gpl", "junk\n")
    with pytest.raises(FileImportError):
        load_palette(path)


def test_no_eval_or_exec_in_loader_source():
    # SC-D005-2 (static): the loader never evals/execs file content.
    src = inspect.getsource(palette_import)
    assert "eval(" not in src
    assert "exec(" not in src
