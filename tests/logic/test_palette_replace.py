"""Tests for pixelart_creator.logic.palette.Palette.replace (atomic bulk set).

Covers the drag-drop palette-load substrate (REQ-P7-DATA-001 / REQ-P7-UI-005,
plan §6): ``replace`` swaps all colours in place, keeping the same Palette object
so scene/panel/editor references stay valid, and validates up front so a bad or
oversized input leaves the palette untouched (atomicity). Maps to reversibility
SC-U005-4 (``apply ∘ undo = identity`` using a ``colors()`` snapshot).

Property-based invariants (Hypothesis) confirm the identity round-trip and the
object-identity guarantee over arbitrary valid colour lists.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.constants import MAX_PALETTE_SIZE
from pixelart_creator.logic.palette import Palette, PaletteError

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)

rgba_st = st.tuples(
    st.integers(0, 255), st.integers(0, 255), st.integers(0, 255), st.integers(0, 255)
)
palette_list_st = st.lists(rgba_st, min_size=0, max_size=32)


# --------------------------------------------------------------------------- #
# behaviour                                                                   #
# --------------------------------------------------------------------------- #


def test_replace_swaps_all_colours():
    pal = Palette([RED, GREEN])
    pal.replace([BLUE])
    assert pal.colors() == [BLUE]
    assert len(pal) == 1


def test_replace_preserves_object_identity():
    # Same Palette object -> held references (scene/panel/editor) stay valid.
    pal = Palette([RED])
    before = pal
    pal.replace([GREEN, BLUE])
    assert pal is before
    assert pal.colors() == [GREEN, BLUE]


def test_replace_with_empty_clears_palette():
    pal = Palette([RED, GREEN, BLUE])
    pal.replace([])
    assert len(pal) == 0
    assert pal.colors() == []


def test_replace_accepts_any_iterable():
    pal = Palette([RED])
    pal.replace(iter([GREEN, BLUE]))  # a one-shot iterator, not a list
    assert pal.colors() == [GREEN, BLUE]


def test_replace_at_ceiling_is_accepted():
    pal = Palette()
    colours = [(i % 256, 0, 0, 255) for i in range(MAX_PALETTE_SIZE)]
    pal.replace(colours)
    assert len(pal) == MAX_PALETTE_SIZE


# --------------------------------------------------------------------------- #
# reversibility — apply ∘ undo = identity (SC-U005-4)                          #
# --------------------------------------------------------------------------- #


def test_replace_then_restore_snapshot_is_identity():
    pal = Palette([RED, GREEN, BLUE])
    old_snapshot = pal.colors()  # the exact snapshot ui/commands captures
    pal.replace([BLUE, RED])
    assert pal.colors() == [BLUE, RED]
    pal.replace(old_snapshot)  # undo
    assert pal.colors() == old_snapshot == [RED, GREEN, BLUE]


# --------------------------------------------------------------------------- #
# atomicity — a failed replace leaves the palette untouched                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad",
    [
        [(0, 0, 0)],  # too few channels
        [(0, 0, 0, 0, 0)],  # too many channels
        [(300, 0, 0, 255)],  # channel out of range
        [(0, 0, 0, 255), "notacolour"],  # non-tuple element
        [(0, 0, 0, 255), (0, 0, -1, 255)],  # negative channel mid-list
    ],
)
def test_replace_rejects_invalid_colour_without_mutation(bad):
    pal = Palette([RED, GREEN])
    original = pal.colors()
    with pytest.raises(PaletteError):
        pal.replace(bad)
    assert pal.colors() == original  # untouched (atomic)


def test_replace_rejects_oversized_without_mutation():
    pal = Palette([RED])
    original = pal.colors()
    too_many = [(0, 0, 0, 255)] * (MAX_PALETTE_SIZE + 1)
    with pytest.raises(PaletteError):
        pal.replace(too_many)
    assert pal.colors() == original


def test_replace_rejects_invalid_element_late_in_iterable_atomically():
    # The bad element is the last one; nothing must have been applied.
    pal = Palette([RED, GREEN, BLUE])
    original = pal.colors()
    good_then_bad = [BLUE, GREEN, (0, 0, 0)]  # last is malformed
    with pytest.raises(PaletteError):
        pal.replace(good_then_bad)
    assert pal.colors() == original


# --------------------------------------------------------------------------- #
# property-based invariants (Hypothesis)                                       #
# --------------------------------------------------------------------------- #


@given(initial=palette_list_st, new=palette_list_st)
def test_replace_result_equals_new_colours_property(initial, new):
    pal = Palette(initial)
    pal.replace(new)
    assert pal.colors() == list(new)


@given(initial=palette_list_st, new=palette_list_st)
def test_replace_undo_is_identity_property(initial, new):
    pal = Palette(initial)
    snapshot = pal.colors()
    pal.replace(new)
    pal.replace(snapshot)
    assert pal.colors() == snapshot


@given(colours=palette_list_st)
def test_replace_keeps_object_identity_property(colours):
    pal = Palette([RED])
    original = pal
    pal.replace(colours)
    assert pal is original
