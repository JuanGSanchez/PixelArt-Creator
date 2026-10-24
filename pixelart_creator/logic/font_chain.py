# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Font family lists for the interface text, and the tags that keep them apart.

Zero Qt (S11): the module composes plain tuples of family names, and ``ui/``
puts them on a font. Two rules shape everything here.

**Rule 1, precedence.** Qt draws each character with the *first* family of the
list that holds it. The bundled CJK families can therefore draw a Han or Hangul
character only if no family placed before them holds that character. A caller
that has measured that its primary family *does* hold shipped Han or Hangul
characters (typically the operating system's UI font on a Chinese, Japanese or
Korean machine) says so with ``primary_holds_cjk``, and the CJK families then go
first. Otherwise the primary leads and the bundled faces follow it. The only
other family that can precede the CJK families is ``Nifen Art``, which holds
none of those characters. So no family ahead of the CJK families is ever one
the caller declared CJK-holding. That follows from the construction in
:func:`family_chain`, and no later check is needed.

**Rule 2, the cache key.** Qt's font cache does not tell two fonts apart by the
families after the first one. Measured: a font whose list has the same first
family, pixel size, weight and other cached attributes as an earlier font is
drawn with the *earlier* font's later families. So the Simplified and the
Japanese form of one chain, which share their first family, would draw each
other's Han characters. A caller breaks the tie by giving every list of two or
more families a small tag (carried in an attribute that is part of the cache
key and does not change rendering). :class:`ChainTagRegistry` hands the tags
out. It gives the same list the same tag, gives two different lists behind one
first family different tags, and allocates each first family independently.
The mirror of the sharing is real as well: a one-family font drawn *after* an
untagged longer list with the same first family takes that list's later
families. So a longer list is never left untagged, and a one-family list, which
has no later families to share, gets no tag (``None``) and uses no capacity.
The length of the later families plays no part in the allocation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import pixelart_creator.logic.language_names as language_names

__all__ = [
    "CJK_HANGUL_FAMILY",
    "CJK_JP_FAMILY",
    "CJK_SC_FAMILY",
    "NIFEN_ART_FAMILY",
    "ChainTagRegistry",
    "ChainTagsExhausted",
    "family_chain",
    "label_chain",
]

NIFEN_ART_FAMILY: Final[str] = "Nifen Art"
"""The bundled Latin pixel face; it holds no Han and no Hangul character."""

CJK_SC_FAMILY: Final[str] = "Nifen Art CJK SC"
"""The bundled Han family drawn in the Simplified Chinese forms."""

CJK_JP_FAMILY: Final[str] = "Nifen Art CJK JP"
"""The bundled Han family drawn in the Japanese forms (it also holds kana)."""

CJK_HANGUL_FAMILY: Final[str] = "Nifen Art CJK KR"
"""The bundled Hangul family."""

_JAPANESE: Final[str] = "ja"
_CHINESE_SIMPLIFIED: Final[str] = "zh_CN"
_TAG_SEPARATORS: Final[tuple[str, ...]] = ("-", "_")


class ChainTagsExhausted(RuntimeError):
    """More distinct family lists share one first family than there are tags."""

    def __init__(self, family: str, capacity: int) -> None:
        """Record the first ``family`` and the ``capacity`` that ran out."""
        super().__init__(
            f"no chain tag left for first family {family!r}: "
            f"{capacity} lists already use them"
        )
        self.family = family
        self.capacity = capacity


def _primary_subtag(language: str) -> str:
    """Return the lower-case language subtag of a tag such as ``ja_JP``."""
    text = language.strip().lower()
    for separator in _TAG_SEPARATORS:
        text = text.replace(separator, " ")
    head, *_ = text.split() or [""]
    return head


def _han_form_family(ui_language: str, system_language: str) -> str:
    """Pick the Han family: ``ja`` gives JP, ``zh_CN`` gives SC, else the system's."""
    if ui_language == _JAPANESE:
        return CJK_JP_FAMILY
    if ui_language == _CHINESE_SIMPLIFIED:
        return CJK_SC_FAMILY
    if _primary_subtag(system_language) == _JAPANESE:
        return CJK_JP_FAMILY
    return CJK_SC_FAMILY


def _without_repeats(families: Sequence[str]) -> tuple[str, ...]:
    """Keep the first of any family named twice (names compared case-insensitively)."""
    seen: set[str] = set()
    kept: list[str] = []
    for family in families:
        key = family.casefold()
        if key not in seen:
            seen.add(key)
            kept.append(family)
    return tuple(kept)


def family_chain(
    role_primary: str,
    ui_language: str,
    system_language: str,
    primary_holds_cjk: bool,
) -> tuple[str, ...]:
    """Return the ordered family list for a role's text.

    ``role_primary`` is the role's own family (``Nifen Art`` in the pixel-font
    mode, the platform family otherwise). ``ui_language`` is a shipped catalogue
    code and ``system_language`` any language tag of the machine (``ja``,
    ``ja_JP``, ``ja-JP``). ``primary_holds_cjk`` is the caller's measurement of
    whether the primary family would draw a shipped Han or Hangul character.

    With ``primary_holds_cjk`` false the order is the primary, ``Nifen Art``, the
    Han family of the right form, the Hangul family. With it true the two CJK
    families come first, then the primary, then ``Nifen Art``. When the primary
    is ``Nifen Art`` itself it is not listed twice. The Han form is Japanese for
    ``ja``, Simplified for ``zh_CN``, and for any other interface language the
    system language's form (Japanese if it is Japanese, else Simplified).

    Raises:
        ValueError: ``role_primary`` is empty.
        language_names.UnknownLanguageError: ``ui_language`` is not a shipped code.
    """
    if not role_primary.strip():
        raise ValueError("role_primary must name a family")
    if ui_language not in language_names.ENDONYMS:
        raise language_names.UnknownLanguageError(
            f"not a shipped language code: {ui_language!r}"
        )
    han = _han_form_family(ui_language, system_language)
    if primary_holds_cjk:
        return _without_repeats(
            (han, CJK_HANGUL_FAMILY, role_primary, NIFEN_ART_FAMILY)
        )
    return _without_repeats((role_primary, NIFEN_ART_FAMILY, han, CJK_HANGUL_FAMILY))


def label_chain(
    role_primary: str, label_language: str, primary_holds_cjk: bool
) -> tuple[str, ...]:
    """Return the family list for a fixed label written in ``label_language``.

    The label keeps its own language's Han form whatever language is active, so
    this is :func:`family_chain` with the label's language as both languages.
    """
    return family_chain(role_primary, label_language, label_language, primary_holds_cjk)


class ChainTagRegistry:
    """Hand out small integer tags that keep family lists apart in the font cache.

    One registry belongs to the caller (there is none at module level). The
    ``capacity`` is the number of distinct tags the caller can carry on a font,
    so it is passed in, not chosen here.
    """

    def __init__(self, capacity: int) -> None:
        """Create an empty registry able to tag ``capacity`` lists per first family.

        Raises:
            ValueError: ``capacity`` is negative.
        """
        if capacity < 0:
            raise ValueError("capacity must not be negative")
        self._capacity = capacity
        self._by_first: dict[str, dict[tuple[str, ...], int]] = {}

    def tag_for(self, families: Sequence[str]) -> int | None:
        """Return the tag of a family list, allocating one on first sight.

        A list of two or more families gets a tag from ``1`` to ``capacity``: the
        same list (names compared case-insensitively) always gets the same tag,
        and different lists behind one first family get different tags. A list
        of one family has no later families to share, so it gets ``None`` and
        spends no capacity.

        Raises:
            ValueError: ``families`` is empty.
            TypeError: ``families`` is a single string, not a sequence of names.
            ChainTagsExhausted: more than ``capacity`` lists share this first
                family; the error names it.
        """
        if isinstance(families, str):
            raise TypeError("families must be a sequence of family names")
        if not families:
            raise ValueError("families must not be empty")
        first, *rest = families
        if not rest:
            return None
        key = tuple(family.casefold() for family in families)
        table = self._by_first.setdefault(first.casefold(), {})
        known = table.get(key)
        if known is not None:
            return known
        if len(table) >= self._capacity:
            raise ChainTagsExhausted(first, self._capacity)
        tag = len(table) + 1
        table[key] = tag
        return tag
