"""NES + Game Boy hardware-palette reference data (zero Qt, S11).

Exposes the fixed reference colour sets for the **NES** (Nintendo Entertainment
System, RP2C02 PPU) and the original **Game Boy** (DMG-01) as new, independent
:class:`~pixelart_creator.logic.palette.Palette` copies, consumed by the
palette-constraint feature (:mod:`~pixelart_creator.logic.quantize`).

Placement & sourcing (ADR-0003):

* The colour tables are **module-local immutable tuples** (``_NES_COLORS``,
  ``_GAME_BOY_COLORS``) — reference *data*, not tuning scalars, so they live here
  rather than in ``constants.py`` (Article II) and are not runtime-loaded assets.
* **Game Boy** = the community-standard DMG green LUT ``#9BBC0F / #8BAC0F /
  #306230 / #0F380F`` (research ``docs/research-phase3-colour.md`` Topic 4.2;
  Pan Docs define only 2-bit indices + a greenscale tint, so these hex triplets
  are the widely-cited *rendering* of that tint — consensus).
* **NES** = the NESdev wiki-canonical ``2C02G_wiki.pal`` 64-entry composite
  decode (research Topic 4.1). The 2C02 emits an analog NTSC signal with **no
  single canonical RGB palette** (≈54 distinct colours across 64 indices); this
  is one *named, referenced* decode, not invented RGB (P1). Source:
  https://www.nesdev.org/wiki/PPU_palettes.

REQ-P3-LOGIC-008 (SC-L008-1..3).
"""

from __future__ import annotations

from typing import Tuple

from pixelart_creator.logic.color import RGBA, from_hex
from pixelart_creator.logic.palette import Palette

__all__ = ["nes_palette", "game_boy_palette"]

# Game Boy DMG 4-shade green palette (lightest → darkest), research Topic 4.2.
_GAME_BOY_COLORS: Tuple[RGBA, ...] = (
    from_hex("#9BBC0F"),
    from_hex("#8BAC0F"),
    from_hex("#306230"),
    from_hex("#0F380F"),
)

# NES 2C02G_wiki.pal composite decode, 64 entries index $00..$3F (NESdev wiki).
# Reference data — a named decode, not a canonical hardware RGB spec (ADR-0003).
_NES_HEX: Tuple[str, ...] = (
    "#626262",
    "#002E98",
    "#0C11C2",
    "#3B00C2",
    "#650098",
    "#7D004E",
    "#7D0000",
    "#651900",
    "#3B3600",
    "#0C4F00",
    "#005B00",
    "#005900",
    "#004058",
    "#000000",
    "#000000",
    "#000000",
    "#ABABAB",
    "#0064F4",
    "#353CFF",
    "#761BFF",
    "#AE0AF4",
    "#CF0C8F",
    "#CF231C",
    "#AE4700",
    "#766F00",
    "#359000",
    "#00A100",
    "#009E1C",
    "#00888F",
    "#000000",
    "#000000",
    "#000000",
    "#FFFFFF",
    "#4AA5FF",
    "#8574FF",
    "#C155FF",
    "#F543FF",
    "#FF49C7",
    "#FF635B",
    "#F58900",
    "#C1AF00",
    "#85D200",
    "#4AE400",
    "#24E162",
    "#24CCD5",
    "#4E4E4E",
    "#000000",
    "#000000",
    "#FFFFFF",
    "#B4D8FF",
    "#CACAFF",
    "#E3BCFF",
    "#F9B2FF",
    "#FFB4E5",
    "#FFBFB4",
    "#F9D08A",
    "#E3E166",
    "#CAEE66",
    "#B4F462",
    "#A5F1A5",
    "#A5EEE1",
    "#B4B4B4",
    "#000000",
    "#000000",
)
_NES_COLORS: Tuple[RGBA, ...] = tuple(from_hex(h) for h in _NES_HEX)


def nes_palette() -> Palette:
    """Return a new, independent :class:`Palette` of the 64 NES colours.

    Each call builds a fresh copy from the immutable module-local tuple; callers
    can never mutate the reference data (SC-L008-3).
    """
    return Palette(_NES_COLORS)


def game_boy_palette() -> Palette:
    """Return a new, independent :class:`Palette` of the 4 Game Boy DMG shades.

    Each call builds a fresh copy from the immutable module-local tuple
    (SC-L008-2, SC-L008-3).
    """
    return Palette(_GAME_BOY_COLORS)
