# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Which heading of a guide page a link fragment names (zero Qt, S11).

A guide page may link to a heading of its own page or of another page, written as
a URL fragment (``#managing-frames``).  This module answers one question about such
a fragment, on the page's Markdown text and nothing else: which heading does it
name?  It does no I/O and imports no Qt, so the guide window and the check that
every shipped link resolves can both use it.

Two pure functions carry it:

* :func:`heading_slugs` gives the slug of every heading of a page, in document
  order.  The slug is the GitHub one: lower case; every character other than a
  letter of any script, a digit, ``-``, ``_`` or a space removed; each space turned
  into one ``-`` (runs are not collapsed, so ``a & b`` is ``a--b``); inline emphasis,
  code spans, links, images and HTML tags reduced to their text.  A slug that has
  been seen already is suffixed ``-1``, ``-2`` ... in document order, and a suffixed
  slug is never equal to another heading's slug, so every fragment names exactly one
  heading.
* :func:`heading_ordinal` gives the zero-based index, into that tuple, of the
  heading a fragment names, or ``None``.  ``None`` is the answer for every unknown
  case (a fragment that names nothing, an empty fragment, a page with no heading,
  an empty page); the function never raises and never falls back to the first
  heading.

The index is over all headings of every level, so
``heading_slugs(page)[heading_ordinal(page, f)] == f``.  A fragment names a heading
of the *English* page.  For a translated page the caller takes the ordinal from the
English text and uses the heading at the same index of the translation; a
translated page's own slugs are not the fragment.

Which lines are headings is a CommonMark subset: ATX headings (``#`` to ``######``,
at most three spaces of indent, a closing ``#`` run dropped) and setext headings
(text over ``===`` or ``---``).  A line inside a fenced block (an unclosed fence runs
to the end of the page), an indented code block or an HTML block is never a heading.
CRLF and LF pages give the same answer.  Headings inside block quotes and list items
are not modelled.
"""

from __future__ import annotations

import re
import unicodedata

from pixelart_creator.logic.constants import (
    GUIDE_MD_CODE_INDENT,
    GUIDE_MD_MAX_ATX_LEVEL,
    GUIDE_MD_MAX_INDENT,
    GUIDE_MD_MIN_FENCE,
    GUIDE_MD_MIN_THEMATIC,
    GUIDE_MD_TAB_STOP,
)

__all__ = ["heading_ordinal", "heading_slugs"]

_LINE_BREAK = re.compile(r"\r\n|\r|\n")
_INDENT = rf" {{0,{GUIDE_MD_MAX_INDENT}}}"

_ATX = re.compile(
    rf"^{_INDENT}(#{{1,{GUIDE_MD_MAX_ATX_LEVEL}}})(?:[ \t]+(.*?))?[ \t]*$"
)
_ATX_CLOSING = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
_SETEXT_UNDERLINE = re.compile(rf"^{_INDENT}(?:=+|-+)[ \t]*$")
_THEMATIC = re.compile(
    rf"^{_INDENT}([-*_])(?:[ \t]*\1){{{GUIDE_MD_MIN_THEMATIC - 1},}}[ \t]*$"
)
_FENCE_OPEN = re.compile(
    rf"^{_INDENT}(`{{{GUIDE_MD_MIN_FENCE},}}|~{{{GUIDE_MD_MIN_FENCE},}})(.*)$"
)
_FENCE_CLOSE = re.compile(
    rf"^{_INDENT}(`{{{GUIDE_MD_MIN_FENCE},}}|~{{{GUIDE_MD_MIN_FENCE},}})[ \t]*$"
)

_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|"
    "colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|"
    "form|frame|frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|legend|li|"
    "link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|section|"
    "source|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_ATTRIBUTES = (
    r"""(?:\s+[A-Za-z_:][\w.:-]*(?:\s*=\s*(?:[^\s"'=<>`]+|'[^']*'|"[^"]*"))?)*"""
)
#: HTML block starts: (start, end).  An end of ``None`` runs to the next blank line.
#: The last start (a lone complete tag) cannot interrupt a paragraph.
_HTML_BLOCKS: tuple[tuple[re.Pattern[str], re.Pattern[str] | None], ...] = (
    (
        re.compile(r"^<(?:script|pre|style|textarea)(?:\s|>|$)", re.IGNORECASE),
        re.compile(r"</(?:script|pre|style|textarea)>", re.IGNORECASE),
    ),
    (re.compile(r"^<!--"), re.compile(r"-->")),
    (re.compile(r"^<\?"), re.compile(r"\?>")),
    (re.compile(r"^<![A-Za-z]"), re.compile(r">")),
    (re.compile(r"^<!\[CDATA\["), re.compile(r"\]\]>")),
    (re.compile(rf"^</?(?:{_BLOCK_TAGS})(?:\s|/?>|$)", re.IGNORECASE), None),
    (
        re.compile(
            rf"^(?:<[A-Za-z][A-Za-z0-9-]*{_ATTRIBUTES}\s*/?>"
            r"|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$"
        ),
        None,
    ),
)
_LONE_TAG_BLOCK = len(_HTML_BLOCKS) - 1

_IMAGE_OR_LINK = re.compile(r"!?\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])")
_CODE_SPAN = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)")
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_EMPHASIS_UNDERSCORE = re.compile(r"(?<![^\W_])_+(?=[^\W_])|(?<=[^\W_])_+(?![^\W_])")
_SLUG_KEPT = "-_ "
_SLUG_KEPT_CATEGORIES = ("L", "M", "N")


def _indent_width(line: str) -> int:
    """Return the column at which ``line`` first has a non-blank character."""
    column = 0
    for char in line:
        if char == " ":
            column += 1
        elif char == "\t":
            column += GUIDE_MD_TAB_STOP - column % GUIDE_MD_TAB_STOP
        else:
            break
    return column


def _inline_text(source: str) -> str:
    """Reduce the inline markup of a heading's text to the text it shows."""
    text = _IMAGE_OR_LINK.sub(r"\1", source)
    parts = re.split(r"(`+.+?(?<!`)`+(?!`))", text)
    shown: list[str] = []
    for index, part in enumerate(parts):
        if index % 2:
            code = _CODE_SPAN.fullmatch(part)
            shown.append(code.group(2) if code else part)
        else:
            shown.append(_EMPHASIS_UNDERSCORE.sub("", _HTML_TAG.sub("", part)))
    return "".join(shown)


def _base_slug(source: str) -> str:
    """Return the slug of one heading's text before repeats are numbered."""
    kept = [
        char
        for char in _inline_text(source).lower()
        if char in _SLUG_KEPT
        or unicodedata.category(char).startswith(_SLUG_KEPT_CATEGORIES)
    ]
    return "".join(kept).replace(" ", "-")


def _heading_texts(markdown: str) -> list[str]:
    """Return the raw text of every heading of ``markdown``, in document order."""
    texts: list[str] = []
    paragraph: list[str] = []
    fence: tuple[str, int] | None = None
    html_end: re.Pattern[str] | None = None
    in_html = False
    for line in _LINE_BREAK.split(markdown):
        if fence is not None:
            closing = _FENCE_CLOSE.match(line)
            if (
                closing
                and closing.group(1)[0] == fence[0]
                and len(closing.group(1)) >= fence[1]
            ):
                fence = None
            continue
        if in_html:
            if html_end is None:
                in_html = bool(line.strip())
            elif html_end.search(line):
                in_html = False
            continue
        if not line.strip():
            paragraph = []
            continue
        width = _indent_width(line)
        if width >= GUIDE_MD_CODE_INDENT:
            if paragraph:
                paragraph.append(line.strip())
            continue
        opened = _FENCE_OPEN.match(line)
        if opened and not (opened.group(1)[0] == "`" and "`" in opened.group(2)):
            fence = (opened.group(1)[0], len(opened.group(1)))
            paragraph = []
            continue
        atx = _ATX.match(line)
        if atx:
            body = _ATX_CLOSING.sub("", atx.group(2) or "")
            texts.append(body.strip())
            paragraph = []
            continue
        if paragraph and _SETEXT_UNDERLINE.match(line):
            texts.append(" ".join(paragraph))
            paragraph = []
            continue
        if _THEMATIC.match(line):
            paragraph = []
            continue
        stripped = line.lstrip(" \t")
        for number, (start, end) in enumerate(_HTML_BLOCKS):
            if number == _LONE_TAG_BLOCK and paragraph:
                continue
            if start.match(stripped):
                in_html = end is None or not end.search(stripped)
                html_end = end
                break
        else:
            paragraph.append(line.strip())
            continue
        paragraph = []
    return texts


def heading_slugs(markdown: str) -> tuple[str, ...]:
    """Return the GitHub-style slug of every heading of ``markdown``.

    The slugs are in document order, over headings of every level and both kinds
    (ATX and setext).  A slug seen before is suffixed ``-1``, ``-2`` ... so that no
    two headings of the page share a slug, even when a heading's own text looks like
    a suffixed slug.  Lines in fenced blocks, indented code and HTML blocks are not
    headings.  An empty page, or one with no heading, gives ``()``.
    """
    counts: dict[str, int] = {}
    slugs: list[str] = []
    for text in _heading_texts(markdown):
        original = _base_slug(text)
        slug = original
        if original in counts:
            while slug in counts:
                counts[original] += 1
                slug = f"{original}-{counts[original]}"
        counts[slug] = 0
        slugs.append(slug)
    return tuple(slugs)


def heading_ordinal(markdown: str, fragment: str) -> int | None:
    """Return the zero-based index of the heading ``fragment`` names, or ``None``.

    ``fragment`` is a URL fragment; one leading ``#`` is ignored.  The index is into
    :func:`heading_slugs` of the same page, so a caller that holds the English page
    and its translation resolves a link by taking the ordinal from the English text
    and the heading at that index of the translation.  ``None`` is returned, and
    nothing is raised, when the fragment is empty or names no heading, and when the
    page is empty or has no heading; the first heading is never a default.
    """
    wanted = fragment[1:] if fragment.startswith("#") else fragment
    if not wanted:
        return None
    slugs = heading_slugs(markdown)
    return slugs.index(wanted) if wanted in slugs else None
