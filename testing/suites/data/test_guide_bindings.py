"""Check (b) — the in-app User Guide agrees with the binding registry (Qt-free).

The input-scheme task list. Covers ``REQ-IS-LOGIC-006``,
``REQ-IS-DATA-001..005``, ``-007``, ``-008``, ``REQ-IS-UI-028`` — Gherkin
``SC-D001-*`` .. ``SC-D008-*``, ``SC-R-31``.

**Authored against the registry, before the guide is rewritten.** This module depends
on the registry landing first, not on the guide rewrite — the two land in one
commit (group C14) precisely so this module cannot be shaped to fit whatever
the prose happens to say. It is legitimately RED until the guide rewrite lands.

Both directions are checked, independently, because either alone is
insufficient (a one-directional check lets the guide rot silently in the
direction nobody is watching):

* **registry -> guide**: every :data:`~pixelart_creator.logic.binding_registry.REGISTRY`
  row's ``literal`` occurs, verbatim, somewhere inside the combined Markdown text
  of the ``section_id`` the row names — an undocumented or misplaced binding
  fails. Matched generously (anywhere in the section's text, not only inside a
  table), on a word-boundary basis, so a correct rewrite in prose form still
  passes; only a genuinely absent/misplaced literal fails.
* **guide -> registry**: every first-column cell of a *recognised binding
  table* — a Markdown pipe table whose header row contains "Shortcut" or
  "Gesture" (case-insensitive; the vocabulary the project's own tables and
  the guide rewrite task already use) — must equal some registry ``literal``
  exactly. A stale/fictional documented shortcut fails. **This direction is
  intentionally scoped to recognised binding tables** — free Markdown prose is
  not scanned for shortcut-shaped tokens, because there is no reliable way to
  tell a shortcut token from ordinary text outside a table; this is a stated
  limitation, not an oversight (mirrors check (a)'s own disclosed gesture-scope
  note in ``test_binding_registry_reality.py``).

``description`` is never read here — ``binding_registry``'s own module
docstring is explicit that it is a non-authoritative developer hint and MUST
NEVER be asserted against by any check.

**Locale scope: this module reads the ``DEFAULT_GUIDE_LOCALE`` ("en") bundle
only.** Check (c) (``test_guide_locale_parity.py``) is what proves ``es``
carries the identical literal tokens (D-12); re-checking ``es`` here would
duplicate that check, not add coverage.

As with check (a), the comparison logic is kept separate from the real
product claim: :func:`check_registry_matches_guide` is pure and takes
already-read text, so it is exercised both against the real, unmodified
bundle (the actual claim) and against small local fixtures (the check's own
correctness) — never against a mutated copy of a real artefact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

import pytest

from pixelart_creator.data import guide_content
from pixelart_creator.logic import binding_registry
from pixelart_creator.logic.binding_registry import Binding
from pixelart_creator.logic.guide_model import DEFAULT_GUIDE_LOCALE, content_ref_path
from pixelart_creator.logic.scope_floor import ScopeFloorError, require_non_empty_scope

# ---------------------------------------------------------------------------
# Minimal Markdown pipe-table parsing (deliberately not a general Markdown
# parser: this project's guide tables are always a header row, a `---`
# separator row, and >=1 data rows, all pipe-delimited -- see every existing
# table under userguide_content/content/en/*.md).
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")
_EMPHASIS_CHARS = str.maketrans("", "", "*`_")

#: Header cell substrings that mark a table as a *binding table* for the
#: guide -> registry direction (case-insensitive). Matches the vocabulary
#: already used by the existing tables and by the guide rewrite task's own prose
#: ("documents the view gestures", "the four Ctrl frame gestures", the
#: existing `| Shortcut | Action |` shape).
_BINDING_HEADER_MARKERS = ("shortcut", "gesture")

#: A token boundary: start/end of string, or one of these characters. Lets a
#: literal like "A" or "S" match a bare/emphasised/table-cell occurrence
#: ("**A**", "| A |") without matching inside a longer word ("Save",
#: "Application") or inside a compound literal ("A" inside "Shift+A").
_BOUNDARY_CHARS = r"\s|*`()\[\],.:;"


def _split_row(line: str) -> list[str]:
    """Split one already-matched table row into stripped, unemphasised cells."""
    inner = _ROW_RE.match(line).group(1)
    return [
        cell.strip().translate(_EMPHASIS_CHARS).strip() for cell in inner.split("|")
    ]


def _is_separator_row(line: str) -> bool:
    m = _ROW_RE.match(line)
    if not m:
        return False
    cells = [c.strip() for c in m.group(1).split("|")]
    return bool(cells) and all(_SEPARATOR_CELL_RE.match(c) for c in cells)


def _parse_tables(text: str) -> list[list[list[str]]]:
    """Return every Markdown pipe table in ``text``.

    Each table is ``[header_cells, *data_row_cells]`` — the ``---`` separator
    row is recognised and dropped, never returned as data.
    """
    lines = text.splitlines()
    tables: list[list[list[str]]] = []
    i = 0
    n = len(lines)
    while i < n:
        if _ROW_RE.match(lines[i]) and i + 1 < n and _is_separator_row(lines[i + 1]):
            header = _split_row(lines[i])
            rows = [header]
            j = i + 2
            while j < n and _ROW_RE.match(lines[j]):
                rows.append(_split_row(lines[j]))
                j += 1
            tables.append(rows)
            i = j
        else:
            i += 1
    return tables


def _binding_table_first_column_cells(text: str) -> list[str]:
    """Return every data-row first-column cell of every *recognised binding
    table* in ``text`` (see the module docstring for the recognition rule).
    """
    cells: list[str] = []
    for table in _parse_tables(text):
        header = table[0]
        is_binding_table = any(
            marker in cell.lower()
            for cell in header
            for marker in _BINDING_HEADER_MARKERS
        )
        if not is_binding_table:
            continue
        for row in table[1:]:
            if row and row[0]:
                cells.append(row[0])
    return cells


def _literal_occurs(text: str, literal: str) -> bool:
    """True iff ``literal`` occurs verbatim in ``text`` at a token boundary.

    Deliberately not restricted to tables: a correct rewrite may document a
    binding in prose (e.g. "Press **F1**"), not only in a table cell. A
    boundary check (not a bare substring check) keeps "A" from matching
    inside "Save" or inside the compound literal "Shift+A".
    """
    pattern = re.compile(
        rf"(?:^|(?<=[{_BOUNDARY_CHARS}]))"
        rf"{re.escape(literal)}"
        rf"(?:$|(?=[{_BOUNDARY_CHARS}]))",
        re.MULTILINE,
    )
    return pattern.search(text) is not None


@dataclass(frozen=True)
class _GuideBindingCheckResult:
    """The outcome of one registry<->guide comparison (check (b))."""

    registry_entries_examined: int
    sections_examined: int
    binding_table_cells_examined: int
    missing_from_guide: tuple[str, ...]
    stale_in_guide: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """True iff both directions hold: nothing missing, nothing stale."""
        return not self.missing_from_guide and not self.stale_in_guide


def check_registry_matches_guide(
    rows: Sequence[Binding],
    section_text: Mapping[str, str],
) -> _GuideBindingCheckResult:
    """Check (b)'s comparison logic (``REQ-IS-LOGIC-006``): pure, reusable.

    Args:
        rows: The registry rows to check (``binding_registry.REGISTRY`` for
            the real product claim, or a small local fixture for the check's
            own correctness).
        section_text: ``section_id -> combined Markdown text`` for every
            guide section to examine (every topic belonging to that section,
            concatenated, for one locale).

    Calls :func:`require_non_empty_scope` FIRST (``REQ-IS-LOGIC-009``): an
    empty ``rows`` sequence raises :class:`ScopeFloorError` carrying
    ``"error: empty-scope"`` before any comparison is attempted.
    """
    require_non_empty_scope("registry-to-guide", len(rows), of="registry entries")

    missing: list[str] = []
    for row in rows:
        text = section_text.get(row.section_id, "")
        if not _literal_occurs(text, row.literal):
            missing.append(
                f"{row.binding_id} ({row.literal!r} not found in section "
                f"{row.section_id!r})"
            )

    registry_literals = {row.literal for row in rows}
    stale: list[str] = []
    cells_examined = 0
    for section_id, text in section_text.items():
        for cell in _binding_table_first_column_cells(text):
            cells_examined += 1
            if cell not in registry_literals:
                stale.append(f"{section_id}: {cell!r}")

    result = _GuideBindingCheckResult(
        registry_entries_examined=len(rows),
        sections_examined=len(section_text),
        binding_table_cells_examined=cells_examined,
        missing_from_guide=tuple(missing),
        stale_in_guide=tuple(stale),
    )
    matched = result.registry_entries_examined - len(result.missing_from_guide)
    cells_ok = result.binding_table_cells_examined - len(result.stale_in_guide)
    print(
        f"[check (b) -- registry-to-guide] {matched} of "
        f"{result.registry_entries_examined} registry entries matched across "
        f"{result.sections_examined} sections; {cells_ok} of "
        f"{result.binding_table_cells_examined} binding-table cells found in "
        "the registry."
    )
    return result


# ---------------------------------------------------------------------------
# Real-bundle text loading (data-layer only; zero Qt).
# ---------------------------------------------------------------------------


def _load_section_text(locale: str) -> dict[str, str]:
    """Read every section's combined Markdown text for ``locale`` from the
    real, committed guide bundle, via the shipped ``data.guide_content``
    reader (never a re-implemented path — the same reader the app uses).
    """
    manifest = guide_content.load_manifest()
    section_text: dict[str, str] = {}
    for section in manifest.sections:
        parts = []
        for topic in section.topics:
            ref = content_ref_path(topic.content_ref, locale)
            parts.append(guide_content.read_content(ref))
        section_text[section.id] = "\n".join(parts)
    return section_text


# ============================================================================
# The real product claim.
# ============================================================================


def test_registry_matches_the_real_guide_both_directions() -> None:
    """The actual claim: the shipped registry and the shipped ``en`` guide
    content agree, in both directions.

    Authored against ``REGISTRY`` before the guide rewrite lands — this is
    expected to be RED until that task lands (this module depends on the
    registry landing first, not the guide rewrite; the two share one commit, group C14).
    """
    section_text = _load_section_text(DEFAULT_GUIDE_LOCALE)
    result = check_registry_matches_guide(binding_registry.REGISTRY, section_text)
    assert result.ok, (
        "check (b) registry<->guide mismatch -- "
        f"missing from guide ({len(result.missing_from_guide)}): "
        f"{list(result.missing_from_guide)} -- "
        f"stale in guide ({len(result.stale_in_guide)}): "
        f"{list(result.stale_in_guide)}"
    )


# ============================================================================
# The check's own correctness -- local fixtures, never a mutated real bundle.
# ============================================================================


def _row(binding_id: str, literal: str, section_id: str = "app-basics") -> Binding:
    return Binding(
        binding_id=binding_id,
        kind="key",
        literal=literal,
        section_id=section_id,
        description="probe row",
    )


class TestDirectionRegistryToGuide:
    def test_literal_present_in_named_section_is_not_missing(self) -> None:
        rows = [_row("tool.pencil", "A", "app-basics")]
        text = {
            "app-basics": "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |"
        }
        result = check_registry_matches_guide(rows, text)
        assert result.missing_from_guide == ()

    def test_literal_absent_everywhere_is_missing(self) -> None:
        rows = [_row("tool.pencil", "A", "app-basics")]
        text = {"app-basics": "No shortcuts documented here at all."}
        result = check_registry_matches_guide(rows, text)
        assert len(result.missing_from_guide) == 1
        assert "tool.pencil" in result.missing_from_guide[0]

    def test_literal_present_only_in_wrong_section_is_still_missing(self) -> None:
        """A binding documented, but in the WRONG section, must fail -- check
        (b) asserts presence IN THE NAMED SECTION, not merely somewhere.
        """
        rows = [_row("tool.pencil", "A", "app-basics")]
        text = {
            "app-basics": "Nothing relevant here.",
            "canvas-and-view": "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |",
        }
        result = check_registry_matches_guide(rows, text)
        assert len(result.missing_from_guide) == 1

    def test_literal_matches_in_free_prose_not_only_in_a_table(self) -> None:
        rows = [_row("action.export", "Ctrl+Shift+E", "export-and-pipeline")]
        text = {"export-and-pipeline": "Press **Ctrl+Shift+E** to open Export."}
        result = check_registry_matches_guide(rows, text)
        assert result.missing_from_guide == ()

    def test_single_letter_literal_does_not_false_match_inside_a_word(self) -> None:
        rows = [_row("tool.pencil", "A", "app-basics")]
        text = {"app-basics": "Application Basics: Save your work often."}
        result = check_registry_matches_guide(rows, text)
        assert len(result.missing_from_guide) == 1

    def test_compound_literal_not_falsely_satisfied_by_its_own_substring(self) -> None:
        rows = [_row("tool.picker", "Shift+A", "app-basics")]
        text = {
            "app-basics": "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |"
        }
        result = check_registry_matches_guide(rows, text)
        assert len(result.missing_from_guide) == 1


class TestDirectionGuideToRegistry:
    def test_documented_shortcut_in_registry_is_not_stale(self) -> None:
        rows = [_row("tool.pencil", "A", "app-basics")]
        text = {
            "app-basics": "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |"
        }
        result = check_registry_matches_guide(rows, text)
        assert result.stale_in_guide == ()

    def test_documented_shortcut_absent_from_registry_is_stale(self) -> None:
        rows = [_row("tool.pencil", "A", "app-basics")]
        text = {
            "app-basics": (
                "| Shortcut | Action |\n| --- | --- |\n"
                "| **A** | Pencil |\n| **Z** | Ghost binding |"
            )
        }
        result = check_registry_matches_guide(rows, text)
        assert len(result.stale_in_guide) == 1
        assert "'Z'" in result.stale_in_guide[0]

    def test_non_binding_table_is_not_scanned_for_staleness(self) -> None:
        """A table whose header names neither 'Shortcut' nor 'Gesture' is
        out of scope for the guide->registry direction by design (the
        module docstring's stated limitation) -- a stray token there must
        not fail the check.
        """
        rows = [_row("tool.pencil", "A", "app-basics")]
        text = {
            "app-basics": (
                "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |\n\n"
                "| Mode | Behaviour |\n| --- | --- |\n| **Loop** | wraps |"
            )
        }
        result = check_registry_matches_guide(rows, text)
        assert result.stale_in_guide == ()

    def test_gesture_headed_table_is_also_scanned(self) -> None:
        rows = [_row("gesture.wheel.favourites", "Wheel", "canvas-and-view")]
        text = {
            "canvas-and-view": (
                "| Gesture | Result |\n| --- | --- |\n"
                "| **Wheel** | Steps favourites |\n"
                "| **Ctrl+wheel** | Unknown gesture |"
            )
        }
        result = check_registry_matches_guide(rows, text)
        assert len(result.stale_in_guide) == 1
        assert "Ctrl+wheel" in result.stale_in_guide[0]


class TestScopeFloor:
    def test_empty_registry_raises_scope_floor_error(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            check_registry_matches_guide([], {"app-basics": "anything"})
        assert excinfo.value.error == "empty-scope"
        assert "error: empty-scope" in str(excinfo.value)

    def test_a_run_that_finds_no_tables_and_no_rows_prints_the_error_object_not_a_verdict(
        self,
    ) -> None:
        """The scope-floor failure carries a printable error object -- the
        precise failure this project's tasks.md keeps calling out: a gate
        that examined nothing must never render as a clean pass.
        """
        with pytest.raises(ScopeFloorError) as excinfo:
            check_registry_matches_guide((), {})
        payload = excinfo.value.as_dict()
        assert payload["error"] == "empty-scope"
        assert payload["check"] == "registry-to-guide"


class TestTableParsingHelpers:
    def test_parse_tables_drops_the_separator_row(self) -> None:
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
        tables = _parse_tables(text)
        assert len(tables) == 1
        assert tables[0] == [["A", "B"], ["1", "2"], ["3", "4"]]

    def test_parse_tables_finds_multiple_tables_in_one_document(self) -> None:
        text = (
            "intro text\n\n"
            "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |\n\n"
            "some prose in between\n\n"
            "| Mode | Behaviour |\n| --- | --- |\n| Loop | wraps |"
        )
        tables = _parse_tables(text)
        assert len(tables) == 2

    def test_non_table_lines_with_pipes_but_no_separator_are_ignored(self) -> None:
        text = "not | a | table\nstill not one"
        assert _parse_tables(text) == []

    def test_clean_cell_strips_markdown_emphasis(self) -> None:
        text = "| Shortcut | Action |\n| --- | --- |\n| **Shift+A** | Picker |"
        tables = _parse_tables(text)
        assert tables[0][1][0] == "Shift+A"
