# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Map the system's preferred languages to a shipped UI language (zero Qt, S11).

Implements the table of ``REQ-L10N-UI-002``. The system's preferred-language
list is walked in its own order and the first entry that maps to a shipped
language wins; when none does, English is installed. Hyphen and underscore
separators are equivalent, letter case is ignored, and a script or territory
subtag does not prevent a match. Chinese is the one language whose script
matters: Simplified (``zh``, ``zh_CN``, ``zh_SG``, ``zh-Hans*``) maps to
``zh_CN``; Traditional (``zh-Hant*``, ``zh_TW``, ``zh_HK``, ``zh_MO``) maps to
nothing shipped, so such an entry is skipped like any other unshipped language.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

__all__ = ["match_ui_language"]

_FALLBACK = "en"
_CHINESE = "zh"
_SIMPLIFIED_CODE = "zh_CN"
_TRADITIONAL_SCRIPT = "hant"
_TRADITIONAL_TERRITORIES = frozenset({"tw", "hk", "mo"})
_SIMPLIFIED_SCRIPT = "hans"
_SEPARATOR = "_"
_ENCODING_MARK = "."
_MODIFIER_MARK = "@"


def _subtags(entry: str) -> list[str]:
    """Return ``entry`` lower-cased, split on ``-``/``_``, sans encoding/modifier."""
    text = entry.strip().partition(_ENCODING_MARK)[0].partition(_MODIFIER_MARK)[0]
    tags = text.lower().replace("-", _SEPARATOR).split(_SEPARATOR)
    return [tag for tag in tags if tag]


def _map_chinese(rest: list[str], lookup: dict[str, str]) -> str | None:
    """Return the shipped code for a Chinese entry's script/territory, or ``None``."""
    if _TRADITIONAL_SCRIPT in rest:
        return None
    if _SIMPLIFIED_SCRIPT not in rest and any(
        tag in _TRADITIONAL_TERRITORIES for tag in rest
    ):
        return None
    return lookup.get(_SIMPLIFIED_CODE.lower())


def _map_entry(entry: str, lookup: dict[str, str]) -> str | None:
    """Return the shipped code one system entry maps to, or ``None``."""
    parts = _subtags(entry)
    if not parts:
        return None
    language, *rest = parts
    if language == _CHINESE:
        return _map_chinese(rest, lookup)
    for part in rest:
        found = lookup.get(language + _SEPARATOR + part)
        if found is not None:
            return found
    return lookup.get(language)


def match_ui_language(preferred: Sequence[str], available: Collection[str]) -> str:
    """Return the shipped language code for the system's ``preferred`` languages.

    Args:
        preferred: system language tags, most preferred first (``fr_FR``,
            ``zh-Hans-CN``, ...), with either separator and any case.
        available: the catalogue codes that ship (``en``, ``zh_CN``, ...).

    Returns:
        The code of the first entry that maps to a code in ``available``; ``"en"``
        when no entry does.
    """
    lookup = {code.lower(): code for code in available}
    for entry in preferred:
        found = _map_entry(entry, lookup)
        if found is not None:
            return found
    return _FALLBACK
