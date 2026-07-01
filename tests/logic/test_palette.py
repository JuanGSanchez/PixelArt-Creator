"""Tests for pixelart_creator.logic.palette."""

from __future__ import annotations

import pytest

from pixelart_creator.logic.palette import MAX_PALETTE_SIZE, Palette, PaletteError

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def test_construct_and_len_iter():
    pal = Palette([RED, GREEN])
    assert len(pal) == 2
    assert list(pal) == [RED, GREEN]


def test_append_returns_index_and_get():
    pal = Palette()
    assert pal.append(RED) == 0
    assert pal.append(GREEN) == 1
    assert pal.get(1) == GREEN


def test_append_rejects_non_rgba():
    pal = Palette()
    with pytest.raises(PaletteError):
        pal.append((1, 2, 3))  # type: ignore[arg-type]


def test_set_replaces():
    pal = Palette([RED])
    pal.set(0, BLUE)
    assert pal.get(0) == BLUE


@pytest.mark.parametrize("bad", [-1, 5, True, "x"])
def test_get_bad_index(bad):
    pal = Palette([RED])
    with pytest.raises(PaletteError):
        pal.get(bad)  # type: ignore[arg-type]


def test_remove_at_shifts():
    pal = Palette([RED, GREEN, BLUE])
    assert pal.remove_at(1) == GREEN
    assert list(pal) == [RED, BLUE]


def test_move_reorders():
    pal = Palette([RED, GREEN, BLUE])
    pal.move(0, 2)
    assert list(pal) == [GREEN, BLUE, RED]


def test_move_bad_target():
    pal = Palette([RED, GREEN])
    with pytest.raises(PaletteError):
        pal.move(0, 9)
    with pytest.raises(PaletteError):
        pal.move(0, True)  # type: ignore[arg-type]


def test_index_of_exact_and_missing():
    pal = Palette([RED, GREEN])
    assert pal.index_of(GREEN) == 1
    assert pal.index_of(BLUE) is None


def test_nearest_index_ties_to_lower():
    pal = Palette([RED, GREEN])
    # Equidistant seed -> lower index wins.
    assert pal.nearest_index(RED) == 0
    assert pal.nearest_index((10, 250, 10, 255)) == 1


def test_nearest_index_empty_raises():
    with pytest.raises(PaletteError):
        Palette().nearest_index(RED)


def test_full_palette_rejects_append():
    pal = Palette([(i, 0, 0, 255) for i in range(MAX_PALETTE_SIZE)])
    with pytest.raises(PaletteError):
        pal.append(GREEN)


def test_copy_is_independent_and_eq():
    pal = Palette([RED])
    clone = pal.copy()
    assert clone == pal
    clone.append(GREEN)
    assert clone != pal
    assert pal.colors() == [RED]


def test_eq_notimplemented_for_other_type():
    assert (Palette([RED]) == "x") is False


def test_repr_contains_class_name():
    assert "Palette" in repr(Palette([RED]))
