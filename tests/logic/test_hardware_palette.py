"""Tests for pixelart_creator.logic.hardware_palette (NES + Game Boy data).

Covers REQ-P3-LOGIC-008 (SC-L008-1..3): the NES palette exposes its fixed 64
entries, the Game Boy palette its 4 DMG shades, and each accessor returns a new,
independent :class:`Palette` copy that cannot mutate the module-local reference.
"""

from __future__ import annotations

from pixelart_creator.logic.color import from_hex, is_rgba
from pixelart_creator.logic.hardware_palette import game_boy_palette, nes_palette
from pixelart_creator.logic.palette import Palette

# The four community-standard DMG green shades (lightest → darkest).
GB_HEX = ["#9BBC0F", "#8BAC0F", "#306230", "#0F380F"]


def test_nes_palette_exposes_64_entries():
    # SC-L008-1.
    pal = nes_palette()
    assert isinstance(pal, Palette)
    assert len(pal) == 64
    assert all(is_rgba(c) for c in pal.colors())


def test_nes_first_entry_is_grey():
    # The 2C02G_wiki.pal decode opens with #626262 (index $00).
    assert nes_palette().get(0) == from_hex("#626262")


def test_game_boy_palette_has_four_shades():
    # SC-L008-2.
    pal = game_boy_palette()
    assert len(pal) == 4
    assert pal.colors() == [from_hex(h) for h in GB_HEX]


def test_reference_palettes_are_independent_copies():
    # SC-L008-3: mutating one returned palette never affects the reference or a
    # subsequent call (each call is a fresh, independent copy).
    first = game_boy_palette()
    first.append((1, 2, 3, 255))
    second = game_boy_palette()
    assert len(second) == 4
    assert second.colors() == [from_hex(h) for h in GB_HEX]

    nes_first = nes_palette()
    nes_first.remove_at(0)
    assert len(nes_palette()) == 64


def test_nes_and_gb_are_distinct():
    assert nes_palette().colors() != game_boy_palette().colors()
