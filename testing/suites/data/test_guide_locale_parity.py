"""Check (c) — ``en`` and ``es`` keep step, both structurally and per token.

``design-docs/specs/input-scheme/tasks.md`` T-29. Covers ``REQ-IS-LOGIC-007``
— Gherkin ``SC-D001-*`` .. ``SC-D008-*``, ``SC-R-31``, and D-12 (key names stay
literal and untranslated).

**Authored against the registry / the bundle's own structure, before the
guide is rewritten.** Shares tasks.md T-29 with ``test_guide_bindings.py``
(check (b)); both depend on T-32, not T-28, and land in the same commit
(group C14). It is legitimately RED wherever the two locales already diverge
today.

Three sub-checks, each independently scoped and independently floored:

1. **Every manifest content stem resolves in BOTH locales** — a manifest
   entry with no ``en`` file, or no ``es`` file, fails.
2. **``en/*.md`` <-> ``es/*.md`` is a bijection, in both directions** — an
   ``en`` file with no ``es`` counterpart fails; an ``es`` file with no ``en``
   counterpart fails. Checked directly against the two content directories,
   not only against the manifest, so an orphaned file neither side declares
   is still caught.
3. **Every shortcut token in an ``en`` binding table appears, byte-for-byte
   identical, in its ``es`` counterpart** (D-12: a key literal like
   ``"Shift+A"`` is a token, not translatable prose, and MUST NOT be
   translated). A *binding table* is recognised the same way check (b)
   recognises one in ``en`` — a header cell containing "Shortcut" or
   "Gesture" (case-insensitive) — but the ``es`` table headers are
   themselves TRANSLATED ("Atajo", "Gesto": confirmed by reading the shipped
   ``es`` content, e.g. ``content/es/app-basics.md``), so an English-header
   heuristic cannot be reused on the ``es`` side. Instead this sub-check
   pairs tables **positionally**: table *i* of the ``es`` document is
   compared against table *i* of the ``en`` document whenever the ``en``
   table at that position is a recognised binding table. A differing table
   count between the two locales for the same stem is itself a failure (the
   structures have diverged), reported distinctly from a token mismatch.

Locale scope is exactly the inverse of check (b): check (b) reads ``en``
only and leaves ``es`` to this module; this module never asserts a token
against the registry directly (that is check (b)'s job) — it only asserts
``en`` and ``es`` agree with EACH OTHER.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

import pytest

from pixelart_creator.data import guide_content
from pixelart_creator.logic.guide_model import CONTENT_FILE_SUFFIX, content_ref_path
from pixelart_creator.logic.scope_floor import ScopeFloorError, require_non_empty_scope

# ---------------------------------------------------------------------------
# Minimal Markdown pipe-table parsing (same shape as test_guide_bindings.py's
# parser; duplicated deliberately -- checks (b) and (c) are graded and must
# be readable independently, not via a shared private import).
# ---------------------------------------------------------------------------

_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")
_EMPHASIS_CHARS = str.maketrans("", "", "*`_")

#: English-only recognition markers -- deliberate: see the module docstring.
#: Applied to the ``en`` table only; the paired ``es`` table is identified
#: positionally, never by translating this list.
_BINDING_HEADER_MARKERS = ("shortcut", "gesture")


def _split_row(line: str) -> list[str]:
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


def _is_binding_table(header: Sequence[str]) -> bool:
    return any(
        marker in cell.lower() for cell in header for marker in _BINDING_HEADER_MARKERS
    )


# ---------------------------------------------------------------------------
# Sub-check 1 + 2: stem resolution + en<->es bijection.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StemParityResult:
    stems_examined: int
    manifest_missing_en: tuple[str, ...]
    manifest_missing_es: tuple[str, ...]
    en_only: tuple[str, ...]
    es_only: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (
            self.manifest_missing_en
            or self.manifest_missing_es
            or self.en_only
            or self.es_only
        )


def check_stem_parity(
    manifest_stems: frozenset[str],
    en_stems: frozenset[str],
    es_stems: frozenset[str],
) -> _StemParityResult:
    """Sub-checks 1 + 2 (``REQ-IS-LOGIC-007``): pure, set-based, reusable.

    Calls :func:`require_non_empty_scope` first on ``manifest_stems``
    (``REQ-IS-LOGIC-009``): an empty manifest raises before any comparison.
    """
    require_non_empty_scope(
        "en-to-es-lockstep-stems", len(manifest_stems), of="content stems"
    )
    result = _StemParityResult(
        stems_examined=len(manifest_stems),
        manifest_missing_en=tuple(sorted(manifest_stems - en_stems)),
        manifest_missing_es=tuple(sorted(manifest_stems - es_stems)),
        en_only=tuple(sorted(en_stems - es_stems)),
        es_only=tuple(sorted(es_stems - en_stems)),
    )
    locales_examined = len({"en", "es"})
    print(
        f"[check (c) -- stem parity] {result.stems_examined} stems checked "
        f"in {locales_examined} locales; "
        f"{len(result.manifest_missing_en)} missing from en, "
        f"{len(result.manifest_missing_es)} missing from es, "
        f"{len(result.en_only)} en-only, {len(result.es_only)} es-only."
    )
    return result


# ---------------------------------------------------------------------------
# Sub-check 3: per-token lockstep between en and es binding tables.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _TokenLockstepResult:
    stems_examined: int
    structural_mismatches: tuple[str, ...]
    token_mismatches: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (self.structural_mismatches or self.token_mismatches)


def check_shortcut_token_lockstep(
    stem_text_pairs: Mapping[str, tuple[str, str]],
) -> _TokenLockstepResult:
    """Sub-check 3 (``REQ-IS-LOGIC-007``, D-12): pure, reusable.

    Args:
        stem_text_pairs: ``stem -> (en_text, es_text)`` for every content
            stem to examine.

    Calls :func:`require_non_empty_scope` first (``REQ-IS-LOGIC-009``).
    """
    require_non_empty_scope(
        "en-to-es-lockstep-tokens", len(stem_text_pairs), of="content stems"
    )
    structural: list[str] = []
    token: list[str] = []
    for stem, (en_text, es_text) in stem_text_pairs.items():
        en_tables = _parse_tables(en_text)
        es_tables = _parse_tables(es_text)
        if len(en_tables) != len(es_tables):
            structural.append(
                f"{stem}: en has {len(en_tables)} table(s), es has "
                f"{len(es_tables)} -- cannot pair positionally"
            )
            continue
        for index, (en_table, es_table) in enumerate(zip(en_tables, es_tables)):
            if not _is_binding_table(en_table[0]):
                continue
            en_cells = [row[0] for row in en_table[1:] if row and row[0]]
            es_cells = [row[0] for row in es_table[1:] if row and row[0]]
            if len(en_cells) != len(es_cells):
                structural.append(
                    f"{stem}: table {index} has {len(en_cells)} en row(s) "
                    f"vs {len(es_cells)} es row(s)"
                )
                continue
            for row_index, (en_cell, es_cell) in enumerate(zip(en_cells, es_cells)):
                if en_cell != es_cell:
                    token.append(
                        f"{stem}: table {index} row {row_index}: "
                        f"en={en_cell!r} != es={es_cell!r}"
                    )
    result = _TokenLockstepResult(
        stems_examined=len(stem_text_pairs),
        structural_mismatches=tuple(structural),
        token_mismatches=tuple(token),
    )
    print(
        f"[check (c) -- token lockstep] {result.stems_examined} stems "
        f"checked in 2 locales; {len(result.structural_mismatches)} "
        f"structural mismatch(es), {len(result.token_mismatches)} token "
        "mismatch(es)."
    )
    return result


# ---------------------------------------------------------------------------
# Real-bundle loading (data-layer only; zero Qt).
# ---------------------------------------------------------------------------


def _list_stems(locale: str) -> frozenset[str]:
    """List every content stem actually present on disk for ``locale``,
    via the real bundle root (never a re-implemented manifest-driven path
    -- this is what makes sub-check 2 catch an orphaned file the manifest
    never mentions).
    """
    content_dir = guide_content.bundle_root() / "content" / locale
    return frozenset(
        child.name[: -len(CONTENT_FILE_SUFFIX)]
        for child in content_dir.iterdir()
        if child.is_file() and child.name.endswith(CONTENT_FILE_SUFFIX)
    )


def _manifest_stems() -> frozenset[str]:
    manifest = guide_content.load_manifest()
    return frozenset(
        topic.content_ref for section in manifest.sections for topic in section.topics
    )


def _stem_text_pairs() -> dict[str, tuple[str, str]]:
    stems = _manifest_stems()
    pairs: dict[str, tuple[str, str]] = {}
    for stem in stems:
        en_ref = content_ref_path(stem, "en")
        es_ref = content_ref_path(stem, "es")
        try:
            en_text = guide_content.read_content(en_ref)
            es_text = guide_content.read_content(es_ref)
        except guide_content.GuideContentError:
            # Sub-check 1 (test_stems_resolve_in_both_locales) is the one
            # that reports a missing file; skip pairing it here rather than
            # crash this sub-check on the same gap.
            continue
        pairs[stem] = (en_text, es_text)
    return pairs


# ============================================================================
# The real product claims.
# ============================================================================


def test_every_manifest_stem_resolves_in_both_locales_and_dirs_are_a_bijection() -> (
    None
):
    result = check_stem_parity(_manifest_stems(), _list_stems("en"), _list_stems("es"))
    assert result.ok, (
        "check (c) stem parity mismatch -- "
        f"manifest stems missing from en: {list(result.manifest_missing_en)} -- "
        f"manifest stems missing from es: {list(result.manifest_missing_es)} -- "
        f"en-only files (no es counterpart): {list(result.en_only)} -- "
        f"es-only files (no en counterpart): {list(result.es_only)}"
    )


def test_every_shortcut_token_in_en_binding_tables_matches_es_identically() -> None:
    """Authored against the registry's D-12 ruling before T-28 rewrites the
    guide -- expected RED wherever an existing en/es table pair already
    diverges (see this task's report for what it finds today).
    """
    result = check_shortcut_token_lockstep(_stem_text_pairs())
    assert result.ok, (
        "check (c) token lockstep mismatch -- "
        f"structural: {list(result.structural_mismatches)} -- "
        f"token: {list(result.token_mismatches)}"
    )


# ============================================================================
# The checks' own correctness -- local fixtures, never a mutated real bundle.
# ============================================================================


class TestStemParity:
    def test_all_three_sets_equal_is_ok(self) -> None:
        stems = frozenset({"app-basics", "layers"})
        result = check_stem_parity(stems, stems, stems)
        assert result.ok

    def test_manifest_stem_missing_from_en_fails(self) -> None:
        result = check_stem_parity(
            frozenset({"app-basics", "layers"}),
            frozenset({"layers"}),
            frozenset({"app-basics", "layers"}),
        )
        assert result.manifest_missing_en == ("app-basics",)
        assert not result.ok

    def test_manifest_stem_missing_from_es_fails(self) -> None:
        result = check_stem_parity(
            frozenset({"app-basics"}),
            frozenset({"app-basics"}),
            frozenset(),
        )
        assert result.manifest_missing_es == ("app-basics",)
        assert not result.ok

    def test_en_only_file_with_no_es_counterpart_fails(self) -> None:
        result = check_stem_parity(
            frozenset({"app-basics"}),
            frozenset({"app-basics", "orphan"}),
            frozenset({"app-basics"}),
        )
        assert result.en_only == ("orphan",)
        assert not result.ok

    def test_es_only_file_with_no_en_counterpart_fails(self) -> None:
        result = check_stem_parity(
            frozenset({"app-basics"}),
            frozenset({"app-basics"}),
            frozenset({"app-basics", "huerfano"}),
        )
        assert result.es_only == ("huerfano",)
        assert not result.ok

    def test_empty_manifest_raises_scope_floor_error(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            check_stem_parity(frozenset(), frozenset(), frozenset())
        assert excinfo.value.error == "empty-scope"
        assert excinfo.value.as_dict()["check"] == "en-to-es-lockstep-stems"


class TestTokenLockstep:
    def test_identical_tables_in_both_locales_is_ok(self) -> None:
        en = "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |"
        es = "| Atajo | Acción |\n| --- | --- |\n| **A** | Lápiz |"
        result = check_shortcut_token_lockstep({"app-basics": (en, es)})
        assert result.ok

    def test_translated_key_literal_is_a_token_mismatch(self) -> None:
        """D-12: a key literal must stay untranslated. 'Espacio' for
        'Space' in the same table position is exactly the defect this
        sub-check exists to catch.
        """
        en = "| Shortcut | Action |\n| --- | --- |\n| **Space** | Play/pause |"
        es = "| Atajo | Acción |\n| --- | --- |\n| **Espacio** | Reproducir |"
        result = check_shortcut_token_lockstep({"app-basics": (en, es)})
        assert not result.ok
        assert any("Espacio" in m for m in result.token_mismatches)

    def test_non_binding_table_is_not_scanned_for_token_lockstep(self) -> None:
        en = "| Mode | Behaviour |\n| --- | --- |\n| **Loop** | wraps |"
        es = "| Modo | Comportamiento |\n| --- | --- |\n| **Bucle** | envuelve |"
        result = check_shortcut_token_lockstep({"animation-timeline": (en, es)})
        assert result.ok

    def test_differing_table_count_is_a_structural_mismatch_not_a_token_one(
        self,
    ) -> None:
        en = (
            "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |\n\n"
            "| Mode | Behaviour |\n| --- | --- |\n| **Loop** | wraps |"
        )
        es = "| Atajo | Acción |\n| --- | --- |\n| **A** | Lápiz |"
        result = check_shortcut_token_lockstep({"app-basics": (en, es)})
        assert not result.ok
        assert result.structural_mismatches
        assert not result.token_mismatches

    def test_differing_row_count_within_a_binding_table_is_structural(self) -> None:
        en = (
            "| Shortcut | Action |\n| --- | --- |\n"
            "| **A** | Pencil |\n| **Q** | Eraser |"
        )
        es = "| Atajo | Acción |\n| --- | --- |\n| **A** | Lápiz |"
        result = check_shortcut_token_lockstep({"app-basics": (en, es)})
        assert not result.ok
        assert result.structural_mismatches

    def test_es_header_translated_still_paired_positionally(self) -> None:
        """The recognition marker list is English-only by design; this
        proves the es table is still checked (paired by position against
        the en table), not skipped because its own header says 'Atajo'.
        """
        en = "| Shortcut | Action |\n| --- | --- |\n| **A** | Pencil |"
        es = "| Atajo | Acción |\n| --- | --- |\n| **Z** | Lápiz |"
        result = check_shortcut_token_lockstep({"app-basics": (en, es)})
        assert not result.ok
        assert any("A" in m and "Z" in m for m in result.token_mismatches)

    def test_empty_scope_raises_scope_floor_error(self) -> None:
        with pytest.raises(ScopeFloorError) as excinfo:
            check_shortcut_token_lockstep({})
        assert excinfo.value.error == "empty-scope"
        assert excinfo.value.as_dict()["check"] == "en-to-es-lockstep-tokens"


class TestTableParsingHelpers:
    def test_is_binding_table_recognises_shortcut_header(self) -> None:
        assert _is_binding_table(["Shortcut", "Action"])

    def test_is_binding_table_recognises_gesture_header(self) -> None:
        assert _is_binding_table(["Gesture", "Result"])

    def test_is_binding_table_rejects_unrelated_header(self) -> None:
        assert not _is_binding_table(["Mode", "Behaviour"])

    def test_is_binding_table_does_not_recognise_translated_spanish_header(
        self,
    ) -> None:
        """Documents the exact limitation the module docstring names: the
        Spanish header itself is never a recognition signal.
        """
        assert not _is_binding_table(["Atajo", "Acción"])
