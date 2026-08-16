"""Tests for pixelart_creator.logic.palette_ops (cycling + swap + remap).

Covers REQ-P3-LOGIC-013 / -014 and the reversible builders (-017):

* ``cycle_palette`` rotates only the index range; cycling by ``len(range)`` is
  the identity (SC-L013-2); forward-then-backward is identity (SC-L013-3); a bad
  range raises PaletteError (SC-L013-4);
* ``swap_indices`` / ``remap_colors`` remap buffers deterministically
  (SC-L014-1/-4); out-of-range keys raise (SC-L014-3);
* ``make_swap_command`` / ``make_cycle_command`` are reversible — apply∘undo =
  identity (SC-L014-2, SC-L017-1).

Hypothesis: swap reversibility and cycle round-trip.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import history
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.palette_ops import (
    cycle_palette,
    make_cycle_command,
    make_swap_command,
    remap_colors,
    swap_indices,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import rect_mask

C0 = (0, 0, 0, 255)
C1 = (10, 10, 10, 255)
C2 = (20, 20, 20, 255)
C3 = (30, 30, 30, 255)
RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _indexed(rows):
    arr = np.array(rows, dtype=np.uint8)
    h, w = arr.shape
    buf = PixelBuffer(w, h, ColorMode.INDEXED)
    buf.data[:, :] = arr
    return buf


# -- cycle_palette (SC-L013) --------------------------------------------------


def test_cycle_rotates_only_range():
    # SC-L013-1: cycling by 1 rotates only the indices in the range.
    pal = Palette([C0, C1, C2, C3])
    out = cycle_palette(pal, 1, 3, 1)
    assert out.colors() == [C0, C3, C1, C2]


def test_cycle_by_len_is_identity():
    # SC-L013-2 (round-trip).
    pal = Palette([C0, C1, C2, C3])
    assert cycle_palette(pal, 0, 3, 4).colors() == pal.colors()
    assert cycle_palette(pal, 1, 2, 2).colors() == pal.colors()


def test_cycle_forward_then_backward_identity():
    # SC-L013-3.
    pal = Palette([C0, C1, C2, C3])
    forward = cycle_palette(pal, 0, 3, 2)
    back = cycle_palette(forward, 0, 3, -2)
    assert back.colors() == pal.colors()


def test_cycle_zero_step_is_identity():
    pal = Palette([C0, C1, C2, C3])
    assert cycle_palette(pal, 0, 3, 0).colors() == pal.colors()


@pytest.mark.parametrize(
    "start,end",
    [(-1, 2), (0, 4), (2, 1), (0, 3)],
)
def test_cycle_bad_range_raises(start, end):
    # SC-L013-4 (0,3 is valid for len 4 — replaced below); build a tiny palette.
    pal = Palette([C0, C1, C2])  # len 3 -> index 3 and reversed ranges are bad
    if 0 <= start <= end < len(pal):
        pytest.skip("range valid for this palette")
    with pytest.raises(PaletteError):
        cycle_palette(pal, start, end, 1)


def test_cycle_bad_index_type_raises():
    pal = Palette([C0, C1, C2])
    with pytest.raises(PaletteError):
        cycle_palette(pal, True, 2, 1)  # type: ignore[arg-type]
    with pytest.raises(PaletteError):
        cycle_palette(pal, 0, 2, "x")  # type: ignore[arg-type]


@given(step=st.integers(-20, 20))
def test_cycle_round_trip_property(step):
    pal = Palette([C0, C1, C2, C3])
    length = 4
    cycled = cycle_palette(pal, 0, 3, step)
    restored = cycle_palette(cycled, 0, 3, (length - (step % length)) % length)
    assert restored.colors() == pal.colors()


# -- swap_indices / remap_colors (SC-L014) ------------------------------------


def test_swap_indices_remaps():
    # SC-L014-1.
    buf = _indexed([[0, 1], [1, 2]])
    out = swap_indices(buf, {1: 0, 2: 1})
    assert out.data.tolist() == [[0, 0], [0, 1]]


def test_swap_indices_deterministic():
    # SC-L014-4.
    buf = _indexed([[0, 1], [2, 3]])
    a = swap_indices(buf, {0: 3, 3: 0})
    b = swap_indices(buf, {0: 3, 3: 0})
    assert np.array_equal(a.data, b.data)


def test_swap_indices_requires_indexed():
    with pytest.raises(PaletteError):
        swap_indices(PixelBuffer(2, 2, ColorMode.RGBA), {0: 1})


@pytest.mark.parametrize("mapping", [{-1: 0}, {0: 256}, {True: 1}])
def test_swap_indices_out_of_range_raises(mapping):
    # SC-L014-3.
    buf = _indexed([[0, 1], [1, 0]])
    with pytest.raises(PaletteError):
        swap_indices(buf, mapping)  # type: ignore[arg-type]


def test_remap_colors_remaps_rgba():
    buf = PixelBuffer(2, 1, ColorMode.RGBA)
    buf.set_pixel(0, 0, RED)
    buf.set_pixel(1, 0, BLUE)
    out = remap_colors(buf, {RED: BLUE})
    assert out.get_pixel(0, 0) == BLUE
    assert out.get_pixel(1, 0) == BLUE


def test_remap_colors_requires_rgba():
    with pytest.raises(PaletteError):
        remap_colors(PixelBuffer(2, 2, ColorMode.INDEXED), {RED: BLUE})


def test_remap_colors_rejects_non_rgba_mapping():
    buf = PixelBuffer(2, 1, ColorMode.RGBA)
    with pytest.raises(PaletteError):
        remap_colors(buf, {(1, 2, 3): BLUE})  # type: ignore[dict-item]


# -- make_swap_command / make_cycle_command (SC-L014-2, SC-L017-1) ------------


def test_make_swap_command_reversible():
    # SC-L014-2: the inverse remap restores the original buffer exactly.
    buf = _indexed([[0, 1], [1, 2]])
    before = buf.copy()
    cmd = make_swap_command(buf, {1: 0, 2: 1})
    assert isinstance(cmd, history.Command)
    cmd.execute()
    assert buf.data.tolist() == [[0, 0], [0, 1]]
    cmd.undo()
    assert buf == before


def test_make_swap_command_respects_mask():
    buf = _indexed([[1, 1], [1, 1]])
    mask = rect_mask(2, 2, 0, 0, 0, 0)  # only (0,0)
    cmd = make_swap_command(buf, {1: 2}, mask=mask)
    cmd.execute()
    assert buf.get_pixel(0, 0) == 2
    assert buf.get_pixel(1, 1) == 1


def test_make_cycle_command_reversible():
    buf = _indexed([[0, 1], [2, 0]])
    before = buf.copy()
    cmd = make_cycle_command(buf, 0, 2, 1)
    cmd.execute()
    cmd.undo()
    assert buf == before


def test_make_cycle_command_requires_indexed():
    with pytest.raises(PaletteError):
        make_cycle_command(PixelBuffer(2, 2, ColorMode.RGBA), 0, 1, 1)


def test_make_cycle_command_empty_range_raises():
    buf = _indexed([[0, 1], [2, 0]])
    with pytest.raises(PaletteError):
        make_cycle_command(buf, 2, 1, 1)


def test_make_cycle_command_bad_step_raises():
    buf = _indexed([[0, 1], [2, 0]])
    with pytest.raises(PaletteError):
        make_cycle_command(buf, 0, 2, "x")  # type: ignore[arg-type]


@given(
    a=st.integers(0, 5),
    b=st.integers(0, 5),
)
def test_swap_reversibility_property(a, b):
    # apply ∘ undo = identity for an arbitrary bijection {a<->b}.
    buf = _indexed([[a, b], [b, a]])
    before = buf.copy()
    cmd = make_swap_command(buf, {a: b, b: a})
    cmd.execute()
    cmd.undo()
    assert buf == before


# --------------------------------------------------------------------------- #
# T-04 — CYCLE_DEFAULT_FPS consumed by identity from constants                 #
# --------------------------------------------------------------------------- #


def test_cycle_default_fps_pinned_value():
    """The live colour-cycle preview's default rate is CYCLE_DEFAULT_FPS (=10),
    a named constant (S12) -- never an inlined magic number."""
    from pixelart_creator.logic.constants import CYCLE_DEFAULT_FPS

    assert CYCLE_DEFAULT_FPS == 10


def test_colour_cycling_panel_consumes_the_constant_by_identity():
    """The UI colour-cycling preview timer's tick interval is derived FROM
    ``constants.CYCLE_DEFAULT_FPS`` (imported, not a duplicated literal).

    ``ui/colour_cycling_panel.py`` is a Qt (QTimer) consumer and this package
    stays Qt-free (S11), so the file is read as plain text (no import, no Qt
    ever touched) to prove the module imports the named constant and derives
    its tick interval from it rather than hardcoding the FPS value.
    """
    from pathlib import Path

    panel_path = (
        Path(__file__).resolve().parents[2]
        / "pixelart_creator"
        / "ui"
        / "colour_cycling_panel.py"
    )
    src = panel_path.read_text(encoding="utf-8")
    assert "from pixelart_creator.logic.constants import CYCLE_DEFAULT_FPS" in src
    assert "1000 / CYCLE_DEFAULT_FPS" in src
