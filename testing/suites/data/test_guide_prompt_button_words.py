"""Guide pages naming the unsaved-changes prompt's buttons use the catalogue's words.

Scenario SC-L10N-UI-005-3 of ``REQ-L10N-UI-005`` clause 4 (zero Qt).
The prompt shown when a project is dropped onto a
document with unsaved changes has three buttons, ``Save``, ``Discard`` and
``Cancel`` (context ``Main_Window``).  The guide quotes them; clause 4 says the
guides quote the catalogue, not a platform's word and not an older draft's.

How the places are found
------------------------
* **English.**  Every English page that names the unsaved-changes prompt (it
  contains the phrase "unsaved changes") is scanned for the three words in
  emphasis (``**Save / Discard / Cancel**`` split at the slashes, or one bold
  word that opens a table row).  Every hit is printed as page, line, word.  A guard
  also lists every English occurrence of "Discard" in emphasis or in quotation marks
  and fails on any whose section :data:`ENGLISH_SECTION_TABLE` does not classify as
  this prompt (context ``Main_Window``) or as another named control (the recovery
  prompt, context ``Recovery_Prompt``).
* **Translated pages.**  The places are the same structural positions as the English
  ones: the same page file, the section at the same heading position, and inside it
  either the bold run with three slash-separated parts (part by index) or the bold
  first cell of a table row (row by index).  The word found there must equal that
  catalogue's finished translation of the button the English place names, read from
  ``pixelart_<lang>.ts`` in context ``Main_Window``.

A language whose three entries are all still ``unfinished`` is reported "not yet
comparable": skipped by name and counted, never passed.  The places examined are
printed per language and must be non-zero.  Run with ``-s`` to see the prints.

The planted controls run on a scratch copy of the content under ``tmp_path`` (the
shipped pages are never written): a page planted with another word for Discard fails
naming page, line and word, and a page aligned to the catalogue's word passes.
"""

from __future__ import annotations

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pytest


def say(text: str) -> None:
    """Print ``text`` so a console that cannot encode it never fails the test."""
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, "backslashreplace").decode(encoding))


#: The eight guide languages the product ships.
LANGUAGES: tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ko", "ja")
ENGLISH = "en"

#: The three buttons of the unsaved-changes prompt, in the order the prompt shows them.
BUTTON_ROLES: tuple[str, ...] = ("Save", "Discard", "Cancel")
DISCARD = "Discard"

#: The catalogue context that holds the prompt's buttons.
PROMPT_CONTEXT = "Main_Window"
#: The context of the recovery prompt's own Discard button (another named control).
RECOVERY_CONTEXT = "Recovery_Prompt"

#: The phrase that marks an English page as naming the unsaved-changes prompt.
PROMPT_PHRASE = "unsaved changes"

#: English section heading text -> the control a button word in that section names.
#: Keyed by (page, heading text); anything else carrying the word fails the guard.
ENGLISH_SECTION_TABLE: dict[tuple[str, str], str] = {
    (
        "drag-drop-import.md",
        "Drop a `.pixproj` → open the project (with a save guard)",
    ): PROMPT_CONTEXT,
    (
        "cloud-and-collaboration.md",
        "The recovery prompt on restart",
    ): RECOVERY_CONTEXT,
}

#: The translation types that mean "not finished" in a Qt ``.ts`` file.
_UNFINISHED_TYPES = frozenset({"unfinished", "vanished", "obsolete"})

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_DIR = _REPO_ROOT / "pixelart_creator"
_CONTENT_DIR = _PACKAGE_DIR / "userguide_content" / "content"
_I18N_DIR = _PACKAGE_DIR / "i18n"

_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)[ \t#]*$")
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.DOTALL)
_SLASH_RE = re.compile(r"\s*/\s*")
_QUOTE_RES = (
    re.compile(r"“[^”\n]{1,80}”"),
    re.compile(r'"[^"\n]{1,80}"'),
)
_DISCARD_WORD_RE = re.compile(r"\bdiscard\b", re.IGNORECASE)
_CJK = "".join(
    chr(c) for c in (0x3000, 0x2D, 0x9FFF, 0xAC00, 0x2D, 0xD7AF, 0xFF00, 0x2D, 0xFFEF)
)
_BREAK = "[ " + chr(9) + "]*" + chr(10) + "[ " + chr(9) + "]*"
_CJK_BREAK_RE = re.compile("(?<=[" + _CJK + "])" + _BREAK + "(?=[" + _CJK + "])")
_SPACE_RE = re.compile(r"\s+")


# --------------------------------------------------------------------------- #
# value types                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Run:
    """One bold run of a page: where it starts, its heading, its text and its form."""

    page: str
    line: int
    section: int
    heading: str
    text: str
    in_table_cell: bool
    parts: tuple[tuple[str, int], ...]  # (normalised part, line of the part)


@dataclass(frozen=True)
class Place:
    """An English place that names one of the prompt's buttons."""

    page: str
    section: int
    kind: str  # "prose" (index = part) or "cell" (index = table row)
    index: int
    role: str


@dataclass(frozen=True)
class Row:
    """One place whose word differs from the catalogue's (or one structural fault)."""

    language: str
    page: str
    line: int
    word: str
    expected: str

    def __str__(self) -> str:
        return (
            f"{self.language}: {self.page}:{self.line}: {self.word!r}"
            f" (expected {self.expected})"
        )


@dataclass(frozen=True)
class Examined:
    """The outcome of comparing one language's guide pages with its catalogue."""

    language: str
    places: tuple[tuple[str, int, str], ...]  # (page, line, word) per place examined
    rows: tuple[Row, ...]


class NotYetComparable(Exception):
    """The language's three prompt entries are all still ``unfinished``."""


# --------------------------------------------------------------------------- #
# page parsing                                                                 #
# --------------------------------------------------------------------------- #


def _normalise(text: str) -> str:
    """Join a soft-wrapped run the way a reader sees it (no space between CJK)."""
    text = _CJK_BREAK_RE.sub("", text)
    return _SPACE_RE.sub(" ", text).strip()


def _read_lines(path: Path) -> list[str]:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")


def _paragraphs(lines: list[str]) -> list[tuple[list[int], int, str]]:
    """Group a page's lines: (line numbers, section index, heading text) per block.

    Returns tuples of ``(line_numbers, section, heading)``; fenced lines are skipped,
    every table line is a block of its own, and a heading starts a new section.
    """
    blocks: list[tuple[list[int], int, str]] = []
    section = -1
    heading = ""
    current: list[int] = []
    fence = ""

    def flush() -> None:
        nonlocal current
        if current:
            blocks.append((current, section, heading))
        current = []

    for number, text in enumerate(lines, start=1):
        fence_match = _FENCE_RE.match(text)
        if fence_match:
            marker = fence_match.group(1)[0]
            if not fence:
                flush()
                fence = marker
            elif fence == marker:
                fence = ""
            continue
        if fence:
            continue
        heading_match = _HEADING_RE.match(text)
        if heading_match:
            flush()
            section += 1
            heading = heading_match.group(1)
            continue
        if not text.strip():
            flush()
            continue
        if text.lstrip().startswith("|"):
            flush()
            current = [number]
            flush()
            continue
        current.append(number)
    flush()
    return blocks


def parse_runs(path: Path) -> list[Run]:
    """Every bold run of the page, with its section, line and slash-split parts."""
    lines = _read_lines(path)
    runs: list[Run] = []
    for numbers, section, heading in _paragraphs(lines):
        joined = "\n".join(lines[n - 1] for n in numbers)
        for match in _BOLD_RE.finditer(joined):
            offset = match.start(1)
            first = numbers[joined[:offset].count("\n")]
            raw = match.group(1)
            parts: list[tuple[str, int]] = []
            cursor = 0
            for piece in _SLASH_RE.split(raw):
                at = raw.index(piece, cursor) if piece else cursor
                cursor = at + len(piece)
                line = numbers[joined[: offset + at].count("\n")]
                parts.append((_normalise(piece), line))
            column = offset - (joined.rfind("\n", 0, offset) + 1)
            before_run = lines[first - 1][: max(column - 2, 0)]
            in_cell = (
                lines[first - 1].lstrip().startswith("|") and before_run.strip() == "|"
            )
            runs.append(
                Run(
                    page=path.name,
                    line=first,
                    section=section,
                    heading=heading,
                    text=_normalise(raw),
                    in_table_cell=in_cell,
                    parts=tuple(parts),
                )
            )
    return runs


def _table_rows(path: Path) -> list[tuple[int, int, str, str]]:
    """Table body rows of the page: (section, line, first-cell bold text, rest)."""
    lines = _read_lines(path)
    rows: list[tuple[int, int, str, str]] = []
    for numbers, section, _heading in _paragraphs(lines):
        text = lines[numbers[0] - 1].strip()
        if not text.startswith("|") or len(numbers) != 1:
            continue
        cells = [c.strip() for c in text.strip("|").split("|")]
        if len(cells) < 2:
            continue
        match = re.fullmatch(r"\*\*(.+)\*\*", cells[0])
        if match:
            rows.append((section, numbers[0], _normalise(match.group(1)), cells[1]))
    return rows


# --------------------------------------------------------------------------- #
# the English places and their guard                                           #
# --------------------------------------------------------------------------- #


def _english_pages(content: Path) -> list[Path]:
    return sorted((content / ENGLISH).glob("*.md"))


def english_places(content: Path) -> tuple[list[Place], list[str], list[str]]:
    """Find the English places; return (places, printed hits, guard failures)."""
    places: list[Place] = []
    printed: list[str] = []
    failures: list[str] = []
    for page in _english_pages(content):
        text = page.read_bytes().decode("utf-8")
        names_prompt = PROMPT_PHRASE in text.lower()
        runs = parse_runs(page)
        lines = _read_lines(page)

        # the guard: every "Discard" in emphasis or quotation is classified
        seen: set[tuple[int, str]] = set()
        occurrences: list[tuple[int, str, str]] = []
        for run in runs:
            for part, line in run.parts:
                if _DISCARD_WORD_RE.search(part):
                    occurrences.append((line, part, run.heading))
        for number, line_text in enumerate(lines, start=1):
            for quote_re in _QUOTE_RES:
                for quoted in quote_re.finditer(line_text):
                    if _DISCARD_WORD_RE.search(quoted.group(0)):
                        heading = _heading_of(lines, number)
                        occurrences.append((number, quoted.group(0), heading))
        for line, word, heading in occurrences:
            if (line, word) in seen:
                continue
            seen.add((line, word))
            if (page.name, heading) not in ENGLISH_SECTION_TABLE:
                failures.append(
                    f"{page.name}:{line}: {word!r} (Discard in emphasis or"
                    f" quotation) is classified neither as the prompt's button"
                    f" nor as another named control (section {heading!r})"
                )

        # the places: exact button words in emphasis on a page naming the prompt
        if not names_prompt:
            continue
        row_order: dict[int, int] = {}
        for run in runs:
            hits = [(p, ln) for p, ln in run.parts if p in BUTTON_ROLES]
            if not hits:
                continue
            kind = "prose" if len(run.parts) == len(BUTTON_ROLES) else "cell"
            if kind == "cell" and not run.in_table_cell:
                continue
            for part, line in hits:
                printed.append(f"{page.name}:{line}: {part}")
                control = ENGLISH_SECTION_TABLE.get((page.name, run.heading))
                if control is None:
                    failures.append(
                        f"{page.name}:{line}: {part!r} names a prompt button on a"
                        f" page about unsaved changes, in section {run.heading!r},"
                        " which the table does not classify"
                    )
                elif control == PROMPT_CONTEXT:
                    if kind == "prose":
                        index = [p for p, _ in run.parts].index(part)
                    else:
                        index = row_order.get(run.section, 0)
                        row_order[run.section] = index + 1
                    places.append(Place(page.name, run.section, kind, index, part))
    return places, printed, failures


def _heading_of(lines: list[str], number: int) -> str:
    """The heading text of the section holding ``lines[number - 1]``."""
    for block_numbers, _section, heading in _paragraphs(lines):
        if number in block_numbers:
            return heading
    return ""


# --------------------------------------------------------------------------- #
# the catalogue                                                                #
# --------------------------------------------------------------------------- #


def catalogue_words(language: str, i18n: Path = _I18N_DIR) -> dict[str, str]:
    """The finished translation of each button, from ``pixelart_<language>.ts``.

    English has no translations: its words are the source strings themselves.
    Raises :class:`NotYetComparable` when all three entries are unfinished and
    ``AssertionError`` when only some are (an inconsistent catalogue).
    """
    if language == ENGLISH:
        return {role: role for role in BUTTON_ROLES}
    root = ET.parse(i18n / f"pixelart_{language}.ts").getroot()
    found: dict[str, list[tuple[str, bool]]] = {r: [] for r in BUTTON_ROLES}
    for context in root.iter("context"):
        if context.findtext("name") != PROMPT_CONTEXT:
            continue
        for message in context.iter("message"):
            source = message.findtext("source")
            if source in found:
                node = message.find("translation")
                assert node is not None
                done = node.get("type") not in _UNFINISHED_TYPES and bool(
                    (node.text or "").strip()
                )
                found[str(source)].append(((node.text or "").strip(), done))
    for role, entries in found.items():
        assert entries, f"{language}: no {role!r} entry in context {PROMPT_CONTEXT}"
    finished = {r: [t for t, d in e if d] for r, e in found.items()}
    if not any(finished.values()):
        raise NotYetComparable(language)
    words: dict[str, str] = {}
    for role, translations in finished.items():
        assert len(set(translations)) == 1, (
            f"{language}: the {role!r} entry of {PROMPT_CONTEXT} is unfinished or"
            f" ambiguous ({translations})"
        )
        words[role] = translations[0]
    return words


# --------------------------------------------------------------------------- #
# the comparison                                                               #
# --------------------------------------------------------------------------- #


def compare_language(
    language: str, content: Path = _CONTENT_DIR, i18n: Path = _I18N_DIR
) -> Examined:
    """Compare one language's pages with its catalogue; raise if not comparable."""
    words = catalogue_words(language, i18n)
    places, _printed, failures = english_places(content)
    assert not failures, "\n".join(failures)
    assert places, "no English place found: nothing to compare"
    examined: list[tuple[str, int, str]] = []
    rows: list[Row] = []
    for page_name in sorted({p.page for p in places}):
        page = content / language / page_name
        if not page.is_file():
            rows.append(Row(language, page_name, 0, "(page missing)", "the page"))
            continue
        runs = parse_runs(page)
        table = _table_rows(page)
        for place in [p for p in places if p.page == page_name]:
            found = _counterpart(place, runs, table)
            expected = words[place.role]
            if found is None:
                rows.append(Row(language, page_name, 0, "(no counterpart)", expected))
                continue
            word, line = found
            examined.append((page_name, line, word))
            if word != expected:
                rows.append(Row(language, page_name, line, word, expected))
    return Examined(language, tuple(examined), tuple(rows))


def _counterpart(
    place: Place, runs: list[Run], table: list[tuple[int, int, str, str]]
) -> tuple[str, int] | None:
    """The word and line at the translated page's same structural position."""
    if place.kind == "prose":
        for run in runs:
            if run.section == place.section and len(run.parts) == len(BUTTON_ROLES):
                return run.parts[place.index]
        return None
    rows = [r for r in table if r[0] == place.section]
    if place.index >= len(rows):
        return None
    _section, line, first, _rest = rows[place.index]
    return first, line


# --------------------------------------------------------------------------- #
# English                                                                      #
# --------------------------------------------------------------------------- #


class TestEnglishPlaces:
    """The English side: the places found, printed, and the Discard guard."""

    def test_english_places_are_found_and_printed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        places, printed, failures = english_places(_CONTENT_DIR)
        with capsys.disabled():
            say("\nEnglish hits (page:line: word):")
            for hit in printed:
                say(f"  {hit}")
            say(f"English places on this prompt: {len(places)}")
        assert not failures, "\n".join(failures)
        assert len(places) == 2 * len(BUTTON_ROLES)
        assert {p.role for p in places} == set(BUTTON_ROLES)

    def test_discard_guard_fails_on_an_unclassified_occurrence(
        self, tmp_path: Path
    ) -> None:
        content = tmp_path / "content"
        shutil.copytree(_CONTENT_DIR / ENGLISH, content / ENGLISH)
        page = content / ENGLISH / "visual-aids.md"
        page.write_bytes(
            page.read_bytes() + b"\n## Elsewhere\n\nPress **Discard** here.\n"
        )
        _places, _printed, failures = english_places(content)
        assert any("visual-aids.md" in f and "'Discard'" in f for f in failures)


# --------------------------------------------------------------------------- #
# every language against its catalogue                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("language", LANGUAGES)
def test_guide_words_equal_the_catalogue(
    language: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Each prompt-button place of the guide equals the catalogue's translation."""
    try:
        result = compare_language(language)
    except NotYetComparable:
        with capsys.disabled():
            say(f"[{language}] not yet comparable: the three entries are unfinished")
        pytest.skip(f"{language}: not yet comparable (three entries unfinished)")
    with capsys.disabled():
        say(f"\n[{language}] places examined: {len(result.places)}")
        for page, line, word in result.places:
            say(f"  {page}:{line}: {word}")
        say(f"[{language}] rows that differ: {len(result.rows)}")
        for row in result.rows:
            say(f"  {row}")
    assert result.places, f"{language}: no place examined"
    assert not result.rows, "\n".join(str(r) for r in result.rows)


def test_not_yet_comparable_languages_are_counted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The languages skipped as not yet comparable are named and counted."""
    skipped: list[str] = []
    for language in LANGUAGES:
        try:
            catalogue_words(language)
        except NotYetComparable:
            skipped.append(language)
    with capsys.disabled():
        say(f"\nnot yet comparable: {len(skipped)} {skipped}")
    assert len(skipped) < len(LANGUAGES) - 1, "no translated language is comparable"


# --------------------------------------------------------------------------- #
# planted controls (scratch copies; the shipped pages are never written)        #
# --------------------------------------------------------------------------- #

PLANTED_WORD = "PLANTED"
TRANSLATED = tuple(lang for lang in LANGUAGES if lang != ENGLISH)


def _scratch(tmp_path: Path, language: str) -> Path:
    content = tmp_path / "content"
    for tree in (ENGLISH, language):
        shutil.copytree(_CONTENT_DIR / tree, content / tree)
    return content


def _rewrite_line(page: Path, line: int, old: str, new: str) -> None:
    lines = _read_lines(page)
    assert old in lines[line - 1], (page.name, line, old)
    lines[line - 1] = lines[line - 1].replace(old, new, 1)
    page.write_bytes("\n".join(lines).encode("utf-8"))


def _discard_places(result: Examined, words: dict[str, str]) -> list[tuple[int, str]]:
    """The (line, found word) of the places that name the Discard button."""
    return [
        (line, word)
        for _page, line, word in result.places
        if word == words[DISCARD] or word not in words.values()
    ]


@pytest.mark.parametrize("language", TRANSLATED)
def test_planted_word_for_discard_fails_naming_page_line_word(
    language: str, tmp_path: Path
) -> None:
    try:
        words = catalogue_words(language)
    except NotYetComparable:
        pytest.skip(f"{language}: not yet comparable")
    content = _scratch(tmp_path, language)
    page = content / language / "drag-drop-import.md"
    before = compare_language(language, content)
    for line, word in _discard_places(before, words):
        _rewrite_line(page, line, word, PLANTED_WORD)
    after = compare_language(language, content)
    planted = [r for r in after.rows if r.word == PLANTED_WORD]
    assert len(planted) == 2
    assert all(r.page == "drag-drop-import.md" and r.line > 0 for r in planted)
    assert all(r.expected == words[DISCARD] for r in planted)


@pytest.mark.parametrize("language", TRANSLATED)
def test_page_aligned_to_the_catalogue_word_passes(
    language: str, tmp_path: Path
) -> None:
    """The control that turns green: Discard places set to the catalogue's word."""
    try:
        catalogue_words(language)
    except NotYetComparable:
        pytest.skip(f"{language}: not yet comparable")
    content = _scratch(tmp_path, language)
    page = content / language / "drag-drop-import.md"
    for _ in range(3):  # each rewrite can move nothing; re-read until stable
        result = compare_language(language, content)
        if not result.rows:
            break
        for row in result.rows:
            _rewrite_line(page, row.line, row.word, row.expected)
    final = compare_language(language, content)
    assert not final.rows, "\n".join(str(r) for r in final.rows)
    assert len(final.places) == 2 * len(BUTTON_ROLES)


def test_missing_translated_page_is_reported(tmp_path: Path) -> None:
    content = _scratch(tmp_path, "de")
    (content / "de" / "drag-drop-import.md").unlink()
    result = compare_language("de", content)
    assert [r.word for r in result.rows] == ["(page missing)"]
