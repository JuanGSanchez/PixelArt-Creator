# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Two number-formatting rules of ``REQ-L10N-UI-015`` (zero Qt, S11).

* :func:`with_unit_space` joins a number and its unit with a no-break space in
  the languages that ask for it, whatever separator Qt's data used.
* :class:`LocaleDecimal` renders a fixed-point number with the formatting
  locale's decimal separator, so a translated message keeps its ``{2:.2f}``
  field unchanged.

The module reads no locale: callers pass the language and the decimal separator,
so the rules stay testable without Qt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pixelart_creator.logic.constants import (
    NO_BREAK_SPACE,
    NUMBER_UNIT_SEPARATORS,
    UNIT_NBSP_LANGUAGES,
)

__all__ = ["LocaleDecimal", "with_unit_space"]

_FIXED_POINT_SPEC = re.compile(r"\.([0-9]+)f")
_ASCII_POINT = "."


def with_unit_space(text: str, language: str) -> str:
    """Return ``text`` with U+00A0 between its last digit and the unit after it.

    Only in the languages of ``UNIT_NBSP_LANGUAGES``. The one character that
    follows the last digit is replaced when it is a space, a no-break space or a
    narrow no-break space and a unit follows it. Any other language, a text with
    no digit, and a text with no such separator come back unchanged. At most one
    character changes.

    Args:
        text: a figure and its unit, e.g. Qt's formatted data size.
        language: the active interface language code.

    Returns:
        The text, with the separator replaced where the rule applies.
    """
    if language not in UNIT_NBSP_LANGUAGES:
        return text
    last_digit = -1
    for index, char in enumerate(text):
        if char.isdecimal():
            last_digit = index
    separator = last_digit + 1
    if last_digit < 0 or separator + 1 >= len(text):
        return text
    if ord(text[separator]) not in NUMBER_UNIT_SEPARATORS:
        return text
    return text[:separator] + chr(NO_BREAK_SPACE) + text[separator + 1 :]


@dataclass(frozen=True)
class LocaleDecimal:
    """A number whose fixed-point rendering uses the locale's decimal separator.

    ``format(LocaleDecimal(x, ","), ".2f")`` equals ``format(x, ".2f")`` with the
    ``.`` replaced by ``,``. With ``"."`` the result equals ``format(x, spec)``.

    Attributes:
        value: the number to render.
        decimal_point: the separator that stands in for ``.``.
    """

    value: float
    decimal_point: str

    def __format__(self, format_spec: str) -> str:
        """Render ``value`` for a fixed-point spec (``.Nf``) with the locale's point.

        Raises:
            ValueError: when ``format_spec`` is not ``.`` + digits + ``f``; there
                is no fallback to another rendering.
        """
        if _FIXED_POINT_SPEC.fullmatch(format_spec) is None:
            raise ValueError(
                f"unsupported format spec {format_spec!r}: only '.Nf' is rendered"
            )
        return format(self.value, format_spec).replace(
            _ASCII_POINT, self.decimal_point, 1
        )
