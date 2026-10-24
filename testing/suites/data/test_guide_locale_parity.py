"""Check (c) -- every guide language tree keeps step with English (REQ-L10N-DATA-003).

This module generalises the earlier English/Spanish lockstep check to **every
locale folder present** under ``userguide_content/content/``. It replaces that
check in place (same file, same role as check (c) of the guide-enforcement
family), so there is exactly one parity check and nothing contradicts it.

Scenarios: SC-L10N-DATA-003-1 (every English topic has a counterpart; the topic
and language counts are printed and non-zero), SC-L10N-DATA-003-2 (a Russian
folder lacking one topic fails, naming it) and SC-L10N-DATA-003-3 (binding-table
key tokens are byte-identical to English; key names stay literal in every
language).

Two views of the same rules, each selectable with ``-k``:

* **One case per locale** (case id = the locale code, e.g. ``-k ru``): stem
  bijection with English and with the manifest, ``meta.json`` id parity, and
  byte-identical binding-table tokens. Counts of topics and languages are printed
  by each case.
* **One case per topic file present** (case id = ``<locale>-<stem>``, e.g.
  ``-k ko-layers`` or ``-k ru``): the page's structure (heading levels, fenced
  blocks, images, link targets, code spans, binding-table tokens) against the
  English page. It can therefore be run on one batch of pages before a whole tree
  is complete. Each case prints the topics it examined; zero examined fails.

The English tree is the reference. ``en`` is enumerated as a case too (its files
must match the manifest), but it has no ``meta.json``: the manifest is its source.

Two requirements are written here but **held**, and each is switched on by flipping
one module-level constant in the commit that brings the content it asserts:

* ``EIGHT_LANGUAGE_FLOOR_ENFORCED`` (``False``): the language-count floor
  ``EXPECTED_LANGUAGE_COUNT`` (8). While ``False`` the floor in force is 1 (English
  alone), so the zero-examined guard still bites; every run prints ``HELD`` and how
  many of the eight were discovered. Flip to ``True`` in the commit that brings the
  eighth language.
* ``ES_META_REQUIRED`` (``False``): until the Spanish ``meta.json`` ships, the
  ``es`` case checks ``meta.json`` id parity only if the file is present and says so
  in its output. Flip to ``True`` in the commit that adds the file.

Every other discovered language (not ``en``, not ``es``) must carry a complete
``meta.json`` from the moment its folder exists.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data import guide_content
from pixelart_creator.logic.guide_model import (
    CONTENT_DIR_NAME,
    CONTENT_FILE_SUFFIX,
    DEFAULT_GUIDE_LOCALE,
    GuideSection,
    GuideTopic,
    Manifest,
)
from pixelart_creator.logic.scope_floor import ScopeFloorError, require_non_empty_scope

# ---------------------------------------------------------------------------
# Held requirements (see the module docstring for how each is switched on).
# ---------------------------------------------------------------------------

#: The number of guide languages the finished product ships (English included).
EXPECTED_LANGUAGE_COUNT = 8

#: Switch for the language-count floor. ``False`` holds it (floor in force = 1).
EIGHT_LANGUAGE_FLOOR_ENFORCED = False

#: Switch for the Spanish ``meta.json`` requirement. ``False`` makes it conditional.
ES_META_REQUIRED = False

#: The locale whose ``meta.json`` requirement is conditional until its file lands.
_META_CONDITIONAL_LOCALE = "es"

#: ``meta.json`` states reported by :func:`examine_locale`.
META_NOT_APPLICABLE = "not-applicable"
META_OK = "ok"
META_REQUIRED_MISSING = "required-but-missing"
META_CONDITIONAL_ABSENT = "conditional-and-absent"
META_INVALID = "invalid"

_META_FILE = guide_content.META_FILE_NAME
_NONE_DISCOVERED = "none-discovered"


def active_language_floor() -> int:
    """Return the language-count floor in force: 8 once enforced, else 1."""
    return EXPECTED_LANGUAGE_COUNT if EIGHT_LANGUAGE_FLOOR_ENFORCED else 1


def meta_is_required(locale: str) -> bool:
    """Return whether ``locale`` must ship a ``meta.json`` right now."""
    if locale == DEFAULT_GUIDE_LOCALE:
        return False
    if locale == _META_CONDITIONAL_LOCALE:
        return ES_META_REQUIRED
    return True


def check_language_floor(discovered: int, floor: int) -> str | None:
    """Return a failure message when fewer than ``floor`` languages were found."""
    if discovered >= floor:
        return None
    return f"{discovered} guide language(s) discovered, the floor is {floor}"


# ---------------------------------------------------------------------------
# Minimal Markdown pipe-table parsing (binding-table tokens).
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")
_EMPHASIS_CHARS = str.maketrans("", "", "*`_")

#: English-only recognition markers, applied to the English table only. The
#: translated table is paired positionally, never recognised by its own header
#: (which is translated).
_BINDING_HEADER_MARKERS = ("shortcut", "gesture")


def _split_row(line: str) -> list[str]:
    match = _ROW_RE.match(line)
    assert match is not None
    return [
        cell.strip().translate(_EMPHASIS_CHARS).strip()
        for cell in match.group(1).split("|")
    ]


def _is_separator_row(line: str) -> bool:
    match = _ROW_RE.match(line)
    if not match:
        return False
    cells = [c.strip() for c in match.group(1).split("|")]
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(c) for c in cells)


def _parse_tables(text: str) -> list[list[list[str]]]:
    lines = text.splitlines()
    tables: list[list[list[str]]] = []
    i = 0
    n = len(lines)
    while i < n:
        if _ROW_RE.match(lines[i]) and i + 1 < n and _is_separator_row(lines[i + 1]):
            rows = [_split_row(lines[i])]
            j = i + 2
            while j < n and _ROW_RE.match(lines[j]):
                rows.append(_split_row(lines[j]))
                j += 1
            tables.append(rows)
            i = j
        else:
            i += 1
    return tables


def _is_binding_table(header: Sequence[str]) -> bool:
    return any(
        marker in cell.lower() for cell in header for marker in _BINDING_HEADER_MARKERS
    )


@dataclass(frozen=True)
class TokenResult:
    """Outcome of comparing binding-table tokens across a set of pages."""

    stems_examined: int
    tables_compared: int
    structural_mismatches: tuple[str, ...]
    token_mismatches: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True when no structural or token mismatch was found."""
        return not (self.structural_mismatches or self.token_mismatches)


def check_token_lockstep(
    stem_text_pairs: Mapping[str, tuple[str, str]], locale: str = "translation"
) -> TokenResult:
    """Compare every English binding-table first column with ``locale``'s.

    Args:
        stem_text_pairs: ``stem -> (english_text, translated_text)``.
        locale: Only used to word the mismatch messages.

    Raises:
        ScopeFloorError: If ``stem_text_pairs`` is empty (nothing was examined).
    """
    require_non_empty_scope(
        "guide-locale-token-lockstep", len(stem_text_pairs), of="content stems"
    )
    structural: list[str] = []
    token: list[str] = []
    compared = 0
    for stem, (en_text, tr_text) in sorted(stem_text_pairs.items()):
        en_tables = _parse_tables(en_text)
        tr_tables = _parse_tables(tr_text)
        if len(en_tables) != len(tr_tables):
            structural.append(
                f"{stem}: en has {len(en_tables)} table(s), {locale} has "
                f"{len(tr_tables)} -- cannot pair positionally"
            )
            continue
        for index, (en_table, tr_table) in enumerate(zip(en_tables, tr_tables)):
            if not _is_binding_table(en_table[0]):
                continue
            en_cells = [row[0] for row in en_table[1:] if row and row[0]]
            tr_cells = [row[0] for row in tr_table[1:] if row and row[0]]
            if len(en_cells) != len(tr_cells):
                structural.append(
                    f"{stem}: table {index} has {len(en_cells)} en row(s) "
                    f"vs {len(tr_cells)} {locale} row(s)"
                )
                continue
            compared += 1
            for row_index, (en_cell, tr_cell) in enumerate(zip(en_cells, tr_cells)):
                if en_cell != tr_cell:
                    token.append(
                        f"{stem}: table {index} row {row_index}: "
                        f"en={en_cell!r} != {locale}={tr_cell!r}"
                    )
    return TokenResult(
        stems_examined=len(stem_text_pairs),
        tables_compared=compared,
        structural_mismatches=tuple(structural),
        token_mismatches=tuple(token),
    )


# ---------------------------------------------------------------------------
# Page structure: headings, fenced blocks, images, links, code spans.
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_HEADING_RE = re.compile(r"^(#{1,6})(?:\s|$)")
#: A code span may wrap across lines (CommonMark) but never across a blank line.
_CODE_SPAN_RE = re.compile(r"(`+)((?:(?!\n[ \t]*\n).)+?)(?<!`)\1(?!`)", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)[^)]*\)")
_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)[^)]*\)")
#: A code span that is a key literal: a modifier chain (``Ctrl+Z``) or an F-key.
#: Key names stay literal in every language, so these must survive translation.
_KEY_SPAN_RE = re.compile(r"^(?:[A-Za-z]+\+)+\S+$|^F[0-9]{1,2}$")


@dataclass(frozen=True)
class PageStructure:
    """The structural skeleton of one Markdown page."""

    heading_levels: tuple[int, ...]
    fence_infos: tuple[str, ...]
    image_targets: tuple[str, ...]
    link_files: tuple[str, ...]
    key_spans: tuple[tuple[str, int], ...]
    code_span_count: int
    stray_backticks: int


def parse_structure(text: str) -> PageStructure:
    """Return the :class:`PageStructure` of ``text`` (fenced blocks are opaque)."""
    headings: list[int] = []
    fences: list[str] = []
    prose: list[str] = []
    open_fence: tuple[str, int] | None = None
    for line in text.splitlines():
        match = _FENCE_RE.match(line)
        if open_fence is not None:
            if (
                match
                and match.group(1)[0] == open_fence[0]
                and len(match.group(1)) >= open_fence[1]
                and not match.group(2).strip()
            ):
                open_fence = None
            continue
        if match:
            open_fence = (match.group(1)[0], len(match.group(1)))
            fences.append(match.group(2).strip())
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            headings.append(len(heading.group(1)))
        prose.append(line)
    body = "\n".join(prose)
    spans = [" ".join(m.group(2).split()) for m in _CODE_SPAN_RE.finditer(body)]
    without_spans = _CODE_SPAN_RE.sub(" ", body)
    images = _IMAGE_RE.findall(without_spans)
    links = [target.split("#", 1)[0] for target in _LINK_RE.findall(without_spans)]
    key_counts = Counter(span for span in spans if _KEY_SPAN_RE.match(span))
    return PageStructure(
        heading_levels=tuple(headings),
        fence_infos=tuple(fences),
        image_targets=tuple(images),
        link_files=tuple(links),
        key_spans=tuple(sorted(key_counts.items())),
        code_span_count=len(spans),
        stray_backticks=without_spans.count("`"),
    )


def compare_structure(english: PageStructure, translated: PageStructure) -> list[str]:
    """Return one message per way ``translated`` departs from ``english``."""
    problems: list[str] = []
    if english.heading_levels != translated.heading_levels:
        problems.append(
            f"heading levels differ: en {list(english.heading_levels)} "
            f"vs {list(translated.heading_levels)}"
        )
    if english.fence_infos != translated.fence_infos:
        problems.append(
            f"fenced blocks differ: en {list(english.fence_infos)} "
            f"vs {list(translated.fence_infos)}"
        )
    if english.image_targets != translated.image_targets:
        problems.append(
            f"image references differ: en {list(english.image_targets)} "
            f"vs {list(translated.image_targets)}"
        )
    if english.link_files != translated.link_files:
        problems.append(
            f"link targets differ: en {list(english.link_files)} "
            f"vs {list(translated.link_files)}"
        )
    missing = Counter(dict(english.key_spans)) - Counter(dict(translated.key_spans))
    if missing:
        problems.append(f"key-literal code spans lost in translation: {dict(missing)}")
    if english.code_span_count and not translated.code_span_count:
        problems.append("the page lost every code span")
    if english.stray_backticks != translated.stray_backticks:
        problems.append(
            f"unbalanced backticks: en {english.stray_backticks} stray, "
            f"translation {translated.stray_backticks}"
        )
    return problems


# ---------------------------------------------------------------------------
# Tree access (Traversable roots, so a fixture directory works like the bundle).
# ---------------------------------------------------------------------------


def discover_locales(root: Traversable) -> tuple[str, ...]:
    """Return every locale folder under ``root/content``, sorted."""
    content = root / CONTENT_DIR_NAME
    if not content.is_dir():
        return ()
    return tuple(sorted(c.name for c in content.iterdir() if c.is_dir()))


def list_stems(root: Traversable, locale: str) -> frozenset[str]:
    """Return every page stem on disk for ``locale`` (orphans included)."""
    folder = root / CONTENT_DIR_NAME / locale
    if not folder.is_dir():
        return frozenset()
    return frozenset(
        c.name[: -len(CONTENT_FILE_SUFFIX)]
        for c in folder.iterdir()
        if c.is_file() and c.name.endswith(CONTENT_FILE_SUFFIX)
    )


def read_page(root: Traversable, locale: str, stem: str) -> str:
    """Return the UTF-8 text of ``content/<locale>/<stem>.md``."""
    node = root / CONTENT_DIR_NAME / locale / (stem + CONTENT_FILE_SUFFIX)
    return node.read_bytes().decode("utf-8")


def manifest_stems(manifest: Manifest) -> frozenset[str]:
    """Return the content stems the manifest declares."""
    return frozenset(
        topic.content_ref for section in manifest.sections for topic in section.topics
    )


# ---------------------------------------------------------------------------
# meta.json id parity.
# ---------------------------------------------------------------------------


def check_meta(
    root: Traversable, locale: str, manifest: Manifest
) -> tuple[str, tuple[str, ...]]:
    """Return ``(state, problems)`` for ``locale``'s ``meta.json``.

    ``state`` is one of the ``META_*`` constants. Id parity means the file's
    section ids and topic ids equal the manifest's: an unknown id and a missing id
    are both problems, each named.
    """
    if locale == DEFAULT_GUIDE_LOCALE:
        return META_NOT_APPLICABLE, ()
    node = root / CONTENT_DIR_NAME / locale / _META_FILE
    if not node.is_file():
        if meta_is_required(locale):
            return META_REQUIRED_MISSING, (
                f"{locale}/{_META_FILE} is required and missing",
            )
        return META_CONDITIONAL_ABSENT, ()
    try:
        data = json.loads(node.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return META_INVALID, (f"{locale}/{_META_FILE} is unreadable: {exc}",)
    if not isinstance(data, dict):
        return META_INVALID, (f"{locale}/{_META_FILE} root is not an object",)
    problems: list[str] = []
    if data.get("locale") != locale:
        problems.append(
            f"{_META_FILE} declares locale {data.get('locale')!r}, folder is {locale!r}"
        )
    for group, expected in (
        ("sections", {s.id for s in manifest.sections}),
        ("topics", {t.id for s in manifest.sections for t in s.topics}),
    ):
        entries = data.get(group)
        if not isinstance(entries, dict):
            problems.append(f"{_META_FILE} '{group}' is not an object")
            continue
        for item_id in sorted(expected - set(entries)):
            problems.append(f"{_META_FILE} {group} lacks id {item_id!r}")
        for item_id in sorted(set(entries) - expected):
            problems.append(f"{_META_FILE} {group} has unknown id {item_id!r}")
        for item_id, entry in sorted(entries.items()):
            if not isinstance(entry, dict):
                problems.append(f"{_META_FILE} {group}[{item_id!r}] is not an object")
    return (META_INVALID if problems else META_OK), tuple(problems)


# ---------------------------------------------------------------------------
# The per-locale examination.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocaleReport:
    """Everything the parity check found for one locale folder."""

    locale: str
    languages: int
    manifest_topics: int
    present_stems: int
    missing: tuple[str, ...]
    orphans: tuple[str, ...]
    meta_state: str
    meta_problems: tuple[str, ...]
    tokens: TokenResult | None = None
    problems: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        """True when the folder is complete and in step with English."""
        return not self.problems

    def summary(self) -> str:
        """Return the printable one-line account of what was examined."""
        tables = self.tokens.tables_compared if self.tokens else 0
        meta = {
            META_CONDITIONAL_ABSENT: (
                f"{self.locale}/{_META_FILE} not present yet; its requirement is "
                "conditional for this language until the file ships, so only the "
                "page set and the tokens were checked"
            ),
            META_NOT_APPLICABLE: "no meta.json (the manifest is the source)",
            META_OK: f"{_META_FILE} ids in parity",
        }.get(self.meta_state, f"{_META_FILE} {self.meta_state}")
        return (
            f"[parity {self.locale}] languages discovered: {self.languages}; "
            f"topics in manifest: {self.manifest_topics}; pages in "
            f"{self.locale}: {self.present_stems}; missing: {len(self.missing)}; "
            f"orphaned: {len(self.orphans)}; binding tables compared: {tables}; "
            f"{meta}."
        )


def examine_locale(
    root: Traversable, manifest: Manifest, locale: str, languages: int
) -> LocaleReport:
    """Examine ``content/<locale>`` against the English tree and the manifest.

    Raises:
        ScopeFloorError: If the manifest declares no topics.
    """
    wanted = manifest_stems(manifest)
    require_non_empty_scope("guide-locale-parity", len(wanted), of="manifest topics")
    present = list_stems(root, locale)
    missing = tuple(sorted(wanted - present))
    orphans = tuple(sorted(present - wanted))
    problems: list[str] = []
    problems.extend(f"{locale}: no page for topic {stem!r}" for stem in missing)
    problems.extend(
        f"{locale}: page {stem!r} is not in the manifest" for stem in orphans
    )
    state, meta_problems = check_meta(root, locale, manifest)
    problems.extend(f"{locale}: {m}" for m in meta_problems)
    tokens: TokenResult | None = None
    if locale != DEFAULT_GUIDE_LOCALE:
        english = list_stems(root, DEFAULT_GUIDE_LOCALE)
        pairs = {
            stem: (
                read_page(root, DEFAULT_GUIDE_LOCALE, stem),
                read_page(root, locale, stem),
            )
            for stem in sorted(present & english & wanted)
        }
        if pairs:
            tokens = check_token_lockstep(pairs, locale)
            problems.extend(f"{locale}: {m}" for m in tokens.structural_mismatches)
            problems.extend(f"{locale}: {m}" for m in tokens.token_mismatches)
    return LocaleReport(
        locale=locale,
        languages=languages,
        manifest_topics=len(wanted),
        present_stems=len(present),
        missing=missing,
        orphans=orphans,
        meta_state=state,
        meta_problems=meta_problems,
        tokens=tokens,
        problems=tuple(problems),
    )


def examine_page(root: Traversable, locale: str, stem: str) -> list[str]:
    """Return the structural problems of ``locale``'s page against English."""
    english_node = (
        root / CONTENT_DIR_NAME / DEFAULT_GUIDE_LOCALE / (stem + CONTENT_FILE_SUFFIX)
    )
    if not english_node.is_file():
        return [f"{locale}/{stem}: no English page to compare with"]
    english = read_page(root, DEFAULT_GUIDE_LOCALE, stem)
    translated = read_page(root, locale, stem)
    problems = [
        f"{locale}/{stem}: {m}"
        for m in compare_structure(
            parse_structure(english), parse_structure(translated)
        )
    ]
    if not translated.strip():
        problems.append(f"{locale}/{stem}: the page is empty")
    pair = {stem: (english, translated)}
    result = check_token_lockstep(pair, locale)
    problems.extend(f"{locale}/{m}" for m in result.structural_mismatches)
    problems.extend(f"{locale}/{m}" for m in result.token_mismatches)
    return problems


# ---------------------------------------------------------------------------
# Parametrisation: one case per locale, one per topic file present.
# ---------------------------------------------------------------------------


def locale_params(locales: Iterable[str]) -> list:
    """Return one ``pytest.param`` per locale, id = the locale code.

    An empty discovery yields one sentinel case that fails, never an empty
    (silently skipped) parameter set.
    """
    found = list(locales)
    if not found:
        return [pytest.param(_NONE_DISCOVERED, id=_NONE_DISCOVERED)]
    return [pytest.param(code, id=code) for code in found]


def topic_params(root: Traversable, locales: Iterable[str]) -> list:
    """Return one ``pytest.param`` per translated page, id ``<locale>-<stem>``."""
    cases = [
        (code, stem)
        for code in locales
        if code != DEFAULT_GUIDE_LOCALE
        for stem in sorted(list_stems(root, code))
    ]
    if not cases:
        return [pytest.param(_NONE_DISCOVERED, "", id=_NONE_DISCOVERED)]
    return [pytest.param(code, stem, id=f"{code}-{stem}") for code, stem in cases]


_ROOT = guide_content.bundle_root()
_LOCALES = discover_locales(_ROOT)
_LOCALE_PARAMS = locale_params(_LOCALES)
_TOPIC_PARAMS = topic_params(_ROOT, _LOCALES)


# ============================================================================
# The real product claims.
# ============================================================================


@pytest.mark.parametrize("locale", _LOCALE_PARAMS)
def test_locale_tree_is_complete_and_in_step_with_english(locale: str) -> None:
    """One case per locale folder present (SC-L10N-DATA-003-1 and -3)."""
    if locale == _NONE_DISCOVERED:
        pytest.fail("no locale folder was discovered under content/ -- 0 examined")
    report = examine_locale(
        _ROOT, guide_content.load_manifest(), locale, languages=len(_LOCALES)
    )
    print(report.summary())
    assert report.manifest_topics > 0 and report.languages > 0
    assert report.ok, "guide tree out of step with English:\n  " + "\n  ".join(
        report.problems
    )


@pytest.mark.parametrize(("locale", "stem"), _TOPIC_PARAMS)
def test_topic_page_has_the_structure_of_its_english_page(
    locale: str, stem: str
) -> None:
    """One case per translated page present; selectable by language and stem."""
    if locale == _NONE_DISCOVERED:
        pytest.fail("no translated topic file was discovered -- 0 topics examined")
    problems = examine_page(_ROOT, locale, stem)
    print(f"[structure {locale}-{stem}] topics examined: 1; problems: {len(problems)}")
    assert not problems, "page departs from the English structure:\n  " + "\n  ".join(
        problems
    )


def test_structural_test_examines_at_least_one_topic() -> None:
    """The structural cases above are not an empty set (zero examined fails)."""
    cases = [p for p in _TOPIC_PARAMS if p.values[0] != _NONE_DISCOVERED]
    languages = {p.values[0] for p in cases}
    print(
        f"[structure] topics examined: {len(cases)}; "
        f"translated languages: {len(languages)}"
    )
    assert cases, "zero topic files examined"


def test_language_floor_in_force_is_met_by_the_bundle() -> None:
    """The eight-language floor: written, held until the eighth language lands."""
    floor = active_language_floor()
    held = "ENFORCED" if EIGHT_LANGUAGE_FLOOR_ENFORCED else "HELD"
    print(
        f"[language floor] {held}: {len(_LOCALES)} of {EXPECTED_LANGUAGE_COUNT} "
        f"languages discovered ({', '.join(_LOCALES)}); floor in force: {floor}"
    )
    failure = check_language_floor(len(_LOCALES), floor)
    assert failure is None, failure


# ============================================================================
# The checks' own correctness -- local fixtures, never the real bundle mutated.
# ============================================================================

_THIS = sys.modules[__name__]

_EN_PAGE = (
    "# Title\n\nSee [layers](layers.md#top) and press `Ctrl+Z`.\n\n"
    "| Shortcut | Action |\n| --- | --- |\n| **Ctrl+Z** | Undo |\n"
)
_TR_PAGE = (
    "# Titulo\n\nVea [capas](layers.md#arriba) y pulse `Ctrl+Z`.\n\n"
    "| Atajo | Accion |\n| --- | --- |\n| **Ctrl+Z** | Deshacer |\n"
)


def _manifest(*stems: str) -> Manifest:
    topics = tuple(
        GuideTopic(id=s, title=s.title(), content_ref=s, keywords=(), summary=s)
        for s in stems
    )
    return Manifest(
        schema_version=1,
        default_locale="en",
        sections=(GuideSection(id="sec", title="Sec", topics=topics),),
    )


def _meta_json(locale: str, topic_ids: Iterable[str], extra: Iterable[str] = ()) -> str:
    ids = [*topic_ids, *extra]
    return json.dumps(
        {
            "schema_version": 1,
            "locale": locale,
            "sections": {"sec": {"title": "S"}},
            "topics": {i: {"title": "T"} for i in ids},
        }
    )


def _write_tree(
    root: Path,
    pages: Mapping[str, Mapping[str, str]],
    metas: Mapping[str, str] | None = None,
) -> Path:
    for locale, files in pages.items():
        folder = root / CONTENT_DIR_NAME / locale
        folder.mkdir(parents=True, exist_ok=True)
        for stem, text in files.items():
            (folder / (stem + CONTENT_FILE_SUFFIX)).write_text(text, encoding="utf-8")
    for locale, text in (metas or {}).items():
        (root / CONTENT_DIR_NAME / locale / _META_FILE).write_text(text, "utf-8")
    return root


class TestRussianFolderMissingOneTopic:
    """SC-L10N-DATA-003-2: a third language is checked, not skipped."""

    def test_missing_russian_topic_fails_naming_it(self, tmp_path: Path) -> None:
        manifest = _manifest("layers", "colour-hub")
        root = _write_tree(
            tmp_path,
            {
                "en": {"layers": _EN_PAGE, "colour-hub": _EN_PAGE},
                "ru": {"layers": _TR_PAGE},
            },
            {"ru": _meta_json("ru", ["layers", "colour-hub"])},
        )
        report = examine_locale(root, manifest, "ru", languages=2)
        assert not report.ok
        assert report.missing == ("colour-hub",)
        assert any("ru" in p and "colour-hub" in p for p in report.problems)

    def test_the_failing_assertion_message_names_the_topic(
        self, tmp_path: Path
    ) -> None:
        manifest = _manifest("layers", "colour-hub")
        root = _write_tree(
            tmp_path,
            {
                "en": {"layers": _EN_PAGE, "colour-hub": _EN_PAGE},
                "ru": {"layers": _TR_PAGE},
            },
            {"ru": _meta_json("ru", ["layers", "colour-hub"])},
        )
        report = examine_locale(root, manifest, "ru", languages=2)
        with pytest.raises(AssertionError, match="colour-hub"):
            assert report.ok, "\n".join(report.problems)

    def test_complete_russian_folder_passes(self, tmp_path: Path) -> None:
        manifest = _manifest("layers")
        root = _write_tree(
            tmp_path,
            {"en": {"layers": _EN_PAGE}, "ru": {"layers": _TR_PAGE}},
            {"ru": _meta_json("ru", ["layers"])},
        )
        report = examine_locale(root, manifest, "ru", languages=2)
        assert report.ok, report.problems
        assert report.tokens is not None and report.tokens.tables_compared == 1

    def test_orphan_page_not_in_manifest_fails(self, tmp_path: Path) -> None:
        manifest = _manifest("layers")
        root = _write_tree(
            tmp_path,
            {
                "en": {"layers": _EN_PAGE},
                "ru": {"layers": _TR_PAGE, "extra": _TR_PAGE},
            },
            {"ru": _meta_json("ru", ["layers"])},
        )
        report = examine_locale(root, manifest, "ru", languages=2)
        assert report.orphans == ("extra",)
        assert not report.ok

    def test_translated_key_token_fails_the_locale(self, tmp_path: Path) -> None:
        manifest = _manifest("layers")
        bad = _TR_PAGE.replace("**Ctrl+Z**", "**Strg+Z**")
        root = _write_tree(
            tmp_path,
            {"en": {"layers": _EN_PAGE}, "ru": {"layers": bad}},
            {"ru": _meta_json("ru", ["layers"])},
        )
        report = examine_locale(root, manifest, "ru", languages=2)
        assert not report.ok
        assert any("Strg+Z" in p for p in report.problems)


class TestOnACopyOfTheRealBundle:
    """Negative controls on a COPY of the committed bundle (never the original)."""

    @staticmethod
    def _copy(tmp_path: Path) -> Path:
        dest = tmp_path / "bundle"
        shutil.copytree(str(_ROOT), dest, ignore=shutil.ignore_patterns("__pycache__"))
        return dest

    def test_copy_passes_before_any_damage(self, tmp_path: Path) -> None:
        copy = self._copy(tmp_path)
        report = examine_locale(
            copy, guide_content.load_manifest(), "es", len(_LOCALES)
        )
        assert report.ok, report.problems

    def test_deleting_one_translated_page_fails_naming_it(self, tmp_path: Path) -> None:
        copy = self._copy(tmp_path)
        (copy / CONTENT_DIR_NAME / "es" / "layers.md").unlink()
        report = examine_locale(
            copy, guide_content.load_manifest(), "es", len(_LOCALES)
        )
        assert not report.ok
        assert any("layers" in p for p in report.problems)

    def test_altering_one_key_token_fails(self, tmp_path: Path) -> None:
        copy = self._copy(tmp_path)
        page = copy / CONTENT_DIR_NAME / "es" / "app-basics.md"
        text = page.read_bytes().decode("utf-8")
        english = read_page(copy, DEFAULT_GUIDE_LOCALE, "app-basics")
        token = next(
            row[0]
            for table in _parse_tables(english)
            if _is_binding_table(table[0])
            for row in table[1:]
            if row[0]
        )
        lines = text.splitlines(keepends=True)
        cell = f"| **{token}** |"
        row = next(i for i, ln in enumerate(lines) if ln.startswith(cell))
        lines[row] = lines[row].replace(cell, f"| **{token}X** |", 1)
        page.write_bytes("".join(lines).encode("utf-8"))
        report = examine_locale(
            copy, guide_content.load_manifest(), "es", len(_LOCALES)
        )
        assert not report.ok
        assert any(token in p for p in report.problems)

    def test_dropping_a_heading_fails_the_page_structure(self, tmp_path: Path) -> None:
        copy = self._copy(tmp_path)
        page = copy / CONTENT_DIR_NAME / "es" / "layers.md"
        lines = page.read_bytes().decode("utf-8").splitlines(keepends=True)
        first = next(i for i, line in enumerate(lines) if line.startswith("#"))
        del lines[first]
        page.write_bytes("".join(lines).encode("utf-8"))
        problems = examine_page(copy, "es", "layers")
        assert any("heading levels" in p for p in problems)

    def test_an_added_language_folder_is_discovered_and_checked(
        self, tmp_path: Path
    ) -> None:
        copy = self._copy(tmp_path)
        (copy / CONTENT_DIR_NAME / "ru").mkdir()
        assert "ru" in discover_locales(copy)
        report = examine_locale(
            copy, guide_content.load_manifest(), "ru", len(discover_locales(copy))
        )
        assert not report.ok and len(report.missing) == 19
        assert report.languages == 3


class TestMetaRequirement:
    def test_other_language_without_meta_fails(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path, {"en": {"layers": _EN_PAGE}, "ru": {"layers": _TR_PAGE}}
        )
        report = examine_locale(root, _manifest("layers"), "ru", languages=2)
        assert report.meta_state == META_REQUIRED_MISSING
        assert not report.ok

    def test_es_without_meta_is_conditional_and_says_so(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path, {"en": {"layers": _EN_PAGE}, "es": {"layers": _TR_PAGE}}
        )
        report = examine_locale(root, _manifest("layers"), "es", languages=2)
        assert report.meta_state == META_CONDITIONAL_ABSENT
        assert report.ok
        assert "conditional" in report.summary()
        assert "not present yet" in report.summary()

    def test_es_without_meta_fails_once_the_requirement_is_switched_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_THIS, "ES_META_REQUIRED", True)
        root = _write_tree(
            tmp_path, {"en": {"layers": _EN_PAGE}, "es": {"layers": _TR_PAGE}}
        )
        report = examine_locale(root, _manifest("layers"), "es", languages=2)
        assert report.meta_state == META_REQUIRED_MISSING
        assert not report.ok

    def test_es_meta_present_is_checked_even_while_conditional(
        self, tmp_path: Path
    ) -> None:
        root = _write_tree(
            tmp_path,
            {"en": {"layers": _EN_PAGE}, "es": {"layers": _TR_PAGE}},
            {"es": _meta_json("es", [], extra=["ghost"])},
        )
        report = examine_locale(root, _manifest("layers"), "es", languages=2)
        assert report.meta_state == META_INVALID
        assert any("ghost" in p for p in report.problems)
        assert any("lacks id 'layers'" in p for p in report.problems)

    def test_meta_locale_mismatch_is_reported(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path,
            {"en": {"layers": _EN_PAGE}, "ru": {"layers": _TR_PAGE}},
            {"ru": _meta_json("de", ["layers"])},
        )
        state, problems = check_meta(root, "ru", _manifest("layers"))
        assert state == META_INVALID
        assert any("declares locale 'de'" in p for p in problems)

    @pytest.mark.parametrize(
        ("raw", "needle"),
        [
            ("{not json", "unreadable"),
            ("[]", "not an object"),
            ('{"locale": "ru", "sections": [], "topics": {}}', "'sections'"),
            (
                '{"locale": "ru", "sections": {"sec": 1}, "topics": {"layers": {}}}',
                "is not an object",
            ),
        ],
        ids=["bad-json", "root-list", "sections-list", "entry-scalar"],
    )
    def test_malformed_meta_is_invalid(
        self, tmp_path: Path, raw: str, needle: str
    ) -> None:
        root = _write_tree(
            tmp_path,
            {"en": {"layers": _EN_PAGE}, "ru": {"layers": _TR_PAGE}},
            {"ru": raw},
        )
        state, problems = check_meta(root, "ru", _manifest("layers"))
        assert state == META_INVALID
        assert any(needle in p for p in problems)

    def test_non_utf8_meta_is_invalid(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path, {"en": {"layers": _EN_PAGE}, "ru": {"layers": _TR_PAGE}}
        )
        (root / CONTENT_DIR_NAME / "ru" / _META_FILE).write_bytes(b"\xff\xfe\x00")
        state, _ = check_meta(root, "ru", _manifest("layers"))
        assert state == META_INVALID

    def test_english_has_no_meta_requirement(self, tmp_path: Path) -> None:
        root = _write_tree(tmp_path, {"en": {"layers": _EN_PAGE}})
        assert check_meta(root, "en", _manifest("layers")) == (META_NOT_APPLICABLE, ())
        report = examine_locale(root, _manifest("layers"), "en", languages=1)
        assert report.ok and report.tokens is None

    def test_meta_is_required_table(self) -> None:
        assert not meta_is_required("en")
        assert meta_is_required("ru")
        assert meta_is_required("ko")


class TestLanguageFloor:
    def test_floor_function_fails_below_and_passes_at_the_floor(self) -> None:
        assert check_language_floor(7, 8) is not None
        assert check_language_floor(8, 8) is None
        assert check_language_floor(9, 8) is None

    def test_floor_is_one_while_held(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_THIS, "EIGHT_LANGUAGE_FLOOR_ENFORCED", False)
        assert active_language_floor() == 1

    def test_floor_is_eight_once_switched_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_THIS, "EIGHT_LANGUAGE_FLOOR_ENFORCED", True)
        assert active_language_floor() == EXPECTED_LANGUAGE_COUNT == 8
        assert check_language_floor(2, active_language_floor()) is not None

    def test_held_floor_still_rejects_zero_languages(self) -> None:
        assert check_language_floor(0, 1) is not None


class TestDiscoveryAndParametrisation:
    def test_discover_locales_lists_folders_sorted(self, tmp_path: Path) -> None:
        root = _write_tree(tmp_path, {"ru": {}, "en": {}, "de": {}})
        assert discover_locales(root) == ("de", "en", "ru")

    def test_discover_locales_ignores_files_and_missing_content(
        self, tmp_path: Path
    ) -> None:
        assert discover_locales(tmp_path) == ()
        (tmp_path / CONTENT_DIR_NAME).mkdir()
        (tmp_path / CONTENT_DIR_NAME / "stray.txt").write_text("x")
        assert discover_locales(tmp_path) == ()

    def test_list_stems_ignores_non_markdown_and_missing_folder(
        self, tmp_path: Path
    ) -> None:
        root = _write_tree(tmp_path, {"ru": {"layers": "x"}}, {"ru": "{}"})
        assert list_stems(root, "ru") == frozenset({"layers"})
        assert list_stems(root, "xx") == frozenset()

    def test_locale_params_use_the_locale_code_as_id(self) -> None:
        params = locale_params(["de", "ru"])
        assert [p.id for p in params] == ["de", "ru"]

    def test_empty_discovery_yields_a_failing_sentinel_not_an_empty_set(self) -> None:
        params = locale_params([])
        assert len(params) == 1 and params[0].values == (_NONE_DISCOVERED,)

    def test_topic_params_id_is_locale_dash_stem_and_skips_english(
        self, tmp_path: Path
    ) -> None:
        root = _write_tree(
            tmp_path,
            {"en": {"layers": "x"}, "ru": {"layers": "x", "colour-hub": "x"}},
        )
        params = topic_params(root, ["en", "ru"])
        assert [p.id for p in params] == ["ru-colour-hub", "ru-layers"]

    def test_topic_params_with_nothing_translated_is_the_sentinel(
        self, tmp_path: Path
    ) -> None:
        root = _write_tree(tmp_path, {"en": {"layers": "x"}})
        params = topic_params(root, ["en"])
        assert len(params) == 1 and params[0].values[0] == _NONE_DISCOVERED

    def test_the_real_bundle_is_discovered_with_english(self) -> None:
        assert DEFAULT_GUIDE_LOCALE in _LOCALES
        assert any(p.id == DEFAULT_GUIDE_LOCALE for p in _LOCALE_PARAMS)

    def test_the_real_structural_cases_cover_every_translated_page(self) -> None:
        expected = sum(
            len(list_stems(_ROOT, code))
            for code in _LOCALES
            if code != DEFAULT_GUIDE_LOCALE
        )
        assert len([p for p in _TOPIC_PARAMS if p.values[0] != _NONE_DISCOVERED]) == (
            expected
        )


class TestPageStructure:
    def test_identical_structure_has_no_problems(self) -> None:
        assert (
            compare_structure(parse_structure(_EN_PAGE), parse_structure(_TR_PAGE))
            == []
        )

    def test_heading_level_change_is_reported(self) -> None:
        tr = _TR_PAGE.replace("# Titulo", "## Titulo")
        problems = compare_structure(parse_structure(_EN_PAGE), parse_structure(tr))
        assert any("heading levels" in p for p in problems)

    def test_missing_heading_is_reported(self) -> None:
        tr = _TR_PAGE.replace("# Titulo\n", "")
        problems = compare_structure(parse_structure(_EN_PAGE), parse_structure(tr))
        assert any("heading levels" in p for p in problems)

    def test_hash_line_inside_a_fence_is_not_a_heading(self) -> None:
        page = "# T\n\n```sh\n# comment\n```\n"
        assert parse_structure(page).heading_levels == (1,)

    def test_fence_marker_kinds_do_not_close_each_other(self) -> None:
        page = "~~~\n```\n# not a heading\n~~~\n# real\n"
        structure = parse_structure(page)
        assert structure.heading_levels == (1,)
        assert structure.fence_infos == ("",)

    def test_shorter_closing_fence_does_not_close(self) -> None:
        page = "````\n```\n# inside\n````\n# real\n"
        assert parse_structure(page).heading_levels == (1,)

    def test_closing_fence_with_text_does_not_close(self) -> None:
        page = "```\n``` not a close\n# inside\n```\n# real\n"
        assert parse_structure(page).heading_levels == (1,)

    def test_fenced_block_count_difference_is_reported(self) -> None:
        en = "# T\n\n```sh\nx\n```\n"
        problems = compare_structure(parse_structure(en), parse_structure("# T\n"))
        assert any("fenced blocks" in p for p in problems)

    def test_image_reference_difference_is_reported(self) -> None:
        en = "# T\n\n![alt](a.png)\n"
        tr = "# T\n\n![alt](b.png)\n"
        problems = compare_structure(parse_structure(en), parse_structure(tr))
        assert any("image references" in p for p in problems)

    def test_link_target_file_part_is_compared_not_the_anchor(self) -> None:
        en = "# T\n\n[a](x.md#one) and [b](#two)\n"
        same = "# T\n\n[a](x.md#uno) and [b](#dos)\n"
        other = "# T\n\n[a](y.md#uno) and [b](#dos)\n"
        assert compare_structure(parse_structure(en), parse_structure(same)) == []
        problems = compare_structure(parse_structure(en), parse_structure(other))
        assert any("link targets" in p for p in problems)

    def test_dropped_link_is_reported(self) -> None:
        en = "# T\n\n[a](x.md)\n"
        problems = compare_structure(parse_structure(en), parse_structure("# T\n"))
        assert any("link targets" in p for p in problems)

    def test_lost_key_literal_code_span_is_reported(self) -> None:
        en = "# T\n\nPress `Ctrl+Z` or `F5`.\n"
        tr = "# T\n\nPulse `Strg+Z` o `F5`.\n"
        problems = compare_structure(parse_structure(en), parse_structure(tr))
        assert any("Ctrl+Z" in p for p in problems)

    def test_translated_non_key_code_span_is_allowed(self) -> None:
        en = "# T\n\nName it `walk`.\n"
        tr = "# T\n\nLlamelo `caminar`.\n"
        assert compare_structure(parse_structure(en), parse_structure(tr)) == []

    def test_page_that_loses_every_code_span_is_reported(self) -> None:
        en = "# T\n\nName it `walk`.\n"
        problems = compare_structure(parse_structure(en), parse_structure("# T\n"))
        assert any("every code span" in p for p in problems)

    def test_unbalanced_backtick_is_reported(self) -> None:
        en = "# T\n\nName it `walk`.\n"
        tr = "# T\n\nLlamelo `caminar.\n"
        problems = compare_structure(parse_structure(en), parse_structure(tr))
        assert any("unbalanced backticks" in p for p in problems)

    def test_link_inside_a_code_span_is_not_a_link(self) -> None:
        assert parse_structure("`[a](x.md)`\n").link_files == ()

    def test_code_span_wrapped_across_lines_is_one_balanced_span(self) -> None:
        structure = parse_structure("see `old_index\n  new_index` here\n")
        assert structure.code_span_count == 1 and structure.stray_backticks == 0

    def test_backtick_does_not_pair_across_a_blank_line(self) -> None:
        structure = parse_structure("a `open\n\nclose` b\n")
        assert structure.code_span_count == 0 and structure.stray_backticks == 2

    def test_double_backtick_span_is_one_span(self) -> None:
        structure = parse_structure("a ``x ` y`` b\n")
        assert structure.code_span_count == 1 and structure.stray_backticks == 0


class TestExaminePage:
    def test_matching_page_has_no_problems(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path, {"en": {"layers": _EN_PAGE}, "ru": {"layers": _TR_PAGE}}
        )
        assert examine_page(root, "ru", "layers") == []

    def test_page_without_english_counterpart_is_named(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path, {"en": {"layers": _EN_PAGE}, "ru": {"ghost": _TR_PAGE}}
        )
        problems = examine_page(root, "ru", "ghost")
        assert problems == ["ru/ghost: no English page to compare with"]

    def test_empty_translated_page_is_reported(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path, {"en": {"layers": _EN_PAGE}, "ru": {"layers": "  \n"}}
        )
        problems = examine_page(root, "ru", "layers")
        assert any("empty" in p for p in problems)

    def test_changed_token_in_one_page_is_reported(self, tmp_path: Path) -> None:
        root = _write_tree(
            tmp_path,
            {
                "en": {"layers": _EN_PAGE},
                "ru": {"layers": _TR_PAGE.replace("**Ctrl+Z**", "**Strg+Z**")},
            },
        )
        problems = examine_page(root, "ru", "layers")
        assert any("Strg+Z" in p for p in problems)


class TestTokenLockstep:
    def test_identical_tokens_pass_and_are_counted(self) -> None:
        result = check_token_lockstep({"layers": (_EN_PAGE, _TR_PAGE)})
        assert result.ok and result.tables_compared == 1

    def test_translated_key_literal_is_a_token_mismatch(self) -> None:
        en = "| Shortcut | Action |\n| --- | --- |\n| **Space** | Play |"
        tr = "| Atajo | Accion |\n| --- | --- |\n| **Espacio** | Reproducir |"
        result = check_token_lockstep({"app-basics": (en, tr)}, "es")
        assert not result.ok
        assert any("Espacio" in m for m in result.token_mismatches)

    def test_non_binding_table_is_not_scanned(self) -> None:
        en = "| Mode | Behaviour |\n| --- | --- |\n| **Loop** | wraps |"
        tr = "| Modo | Comportamiento |\n| --- | --- |\n| **Bucle** | envuelve |"
        result = check_token_lockstep({"animation-timeline": (en, tr)})
        assert result.ok and result.tables_compared == 0

    def test_differing_table_count_is_structural(self) -> None:
        en = (
            "| Shortcut | Action |\n| --- | --- |\n| **A** | x |\n\n"
            "| Mode | B |\n| --- | --- |\n| **L** | y |"
        )
        tr = "| Atajo | Accion |\n| --- | --- |\n| **A** | x |"
        result = check_token_lockstep({"s": (en, tr)})
        assert result.structural_mismatches and not result.token_mismatches

    def test_differing_row_count_is_structural(self) -> None:
        en = "| Shortcut | A |\n| --- | --- |\n| **A** | x |\n| **Q** | y |"
        tr = "| Atajo | A |\n| --- | --- |\n| **A** | x |"
        result = check_token_lockstep({"s": (en, tr)})
        assert result.structural_mismatches

    def test_translated_header_is_still_paired_by_position(self) -> None:
        en = "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |"
        tr = "| Atajo | Accion |\n| --- | --- |\n| **Z** | Lapiz |"
        result = check_token_lockstep({"s": (en, tr)})
        assert any("A" in m and "Z" in m for m in result.token_mismatches)

    def test_empty_scope_raises(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            check_token_lockstep({})
        assert excinfo.value.error == "empty-scope"
        assert excinfo.value.as_dict()["check"] == "guide-locale-token-lockstep"

    def test_empty_manifest_raises_for_a_locale(self, tmp_path: Path) -> None:
        root = _write_tree(tmp_path, {"en": {}, "ru": {}})
        with pytest.raises(ScopeFloorError) as excinfo:
            examine_locale(root, _manifest(), "ru", languages=2)
        assert excinfo.value.as_dict()["check"] == "guide-locale-parity"


class TestTableParsingHelpers:
    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            (["Shortcut", "Action"], True),
            (["Gesture", "Result"], True),
            (["Mode", "Behaviour"], False),
            (["Atajo", "Accion"], False),
        ],
        ids=["shortcut", "gesture", "unrelated", "translated-not-recognised"],
    )
    def test_binding_header_recognition(
        self, header: list[str], expected: bool
    ) -> None:
        assert _is_binding_table(header) is expected

    def test_separator_row_needs_a_pipe_row(self) -> None:
        assert not _is_separator_row("no pipes here")
        assert _is_separator_row("| :--- | ---: |")
        assert not _is_separator_row("| a | b |")


_TOKEN = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="+"
    ),
    min_size=1,
    max_size=8,
)


@given(tokens=st.lists(_TOKEN, min_size=1, max_size=6))
def test_parsed_first_column_round_trips_the_generated_tokens(
    tokens: list[str],
) -> None:
    table = "| Shortcut | Action |\n| --- | --- |\n" + "".join(
        f"| **{t}** | do |\n" for t in tokens
    )
    parsed = _parse_tables(table)
    assert len(parsed) == 1 and _is_binding_table(parsed[0][0])
    assert [row[0] for row in parsed[0][1:]] == tokens


@given(tokens=st.lists(_TOKEN, min_size=1, max_size=6))
def test_a_page_compared_with_itself_never_mismatches(tokens: list[str]) -> None:
    page = "# T\n\n| Shortcut | Action |\n| --- | --- |\n" + "".join(
        f"| `{t}` | do |\n" for t in tokens
    )
    assert check_token_lockstep({"s": (page, page)}).ok
    assert compare_structure(parse_structure(page), parse_structure(page)) == []
