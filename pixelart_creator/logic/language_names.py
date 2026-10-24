# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Language self-names (endonyms) and the language-selector order (zero Qt, S11).

The selector labels each shipped language with its own name, the same whatever
language the interface is in (``REQ-L10N-UI-003``). A language's name is data, like
a file name: it is **not** translatable text, so it is neither wrapped in ``tr()``
nor offered to translators. The table and the order live here, once; a shipped
language with no entry here raises instead of showing its raw code.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from types import MappingProxyType

__all__ = [
    "ENDONYMS",
    "SELECTOR_ORDER",
    "UnknownLanguageError",
    "selector_entries",
]


class UnknownLanguageError(ValueError):
    """A discovered language code has no endonym, so it cannot be labelled."""


ENDONYMS: Mapping[str, str] = MappingProxyType(
    {
        "en": "English",
        "es": "Español",
        "fr": "Français",
        "de": "Deutsch",
        "ru": "Русский",
        "zh_CN": "简体中文",
        "ja": "日本語",
        "ko": "한국어",
    }
)
"""Catalogue code -> the language's own name, byte-exact to ``REQ-L10N-UI-003``."""

SELECTOR_ORDER: tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")
"""Catalogue codes in the order the selector shows them (``REQ-L10N-UI-003``)."""


def selector_entries(available: Collection[str]) -> tuple[tuple[str, str], ...]:
    """Return ``(code, endonym)`` pairs for ``available``, in selector order.

    Codes in :data:`SELECTOR_ORDER` come first, in that order; a code of that
    list that is not in ``available`` is left out.

    Raises:
        UnknownLanguageError: ``available`` holds a code with no endonym, so a raw
            code can never reach the menu.
    """
    unknown = sorted(set(available) - ENDONYMS.keys())
    if unknown:
        raise UnknownLanguageError(
            "no endonym for language code(s): " + ", ".join(unknown)
        )
    present = set(available)
    return tuple((code, ENDONYMS[code]) for code in SELECTOR_ORDER if code in present)
