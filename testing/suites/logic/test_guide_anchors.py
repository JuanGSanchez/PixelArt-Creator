"""Tests for pixelart_creator.logic.guide_anchors (zero Qt) -- REQ-L10N-UI-019.

The module answers one question: which heading of a guide page's Markdown does a
URL fragment name?  Two pure functions carry it:

* ``heading_slugs(markdown) -> tuple[str, ...]`` -- the GitHub-style slug of every
  heading of the page, in document order;
* ``heading_ordinal(markdown, fragment) -> int | None`` -- the zero-based index, into
  that tuple, of the heading the fragment names, or ``None``.

Behaviours fixed here (each is a test below):

* **The slug rule.**  Lower case; punctuation other than ``-`` and ``_`` removed;
  each space becomes one ``-`` (runs are not collapsed, so ``a & b`` is ``a--b``);
  letters of any script are kept; inline emphasis, code spans, links and images are
  reduced to their text; a repeated slug is suffixed ``-1``, ``-2`` ... and a
  suffixed slug never equals another heading's slug.
* **Which lines are headings.**  ATX (``#`` to ``######``, at most three spaces of
  indent, closing ``#`` run dropped) and setext (text over ``===`` or ``---``);
  none inside a fenced block (unclosed fences run to the end of the page), an
  indented block or an HTML block; CRLF and LF pages give the same answer.
* **The ordinal.**  Zero-based, over all headings of every level, so that
  ``heading_slugs(page)[heading_ordinal(page, f)] == f``.  A single leading ``#`` on
  the fragment is ignored.  ``None`` for a fragment that names nothing, an empty
  fragment, a page with no heading and an empty page: never an exception and never
  a first-heading default (REQ-L10N-UI-019 clause 4).
* **Translated pages (clause 3).**  The fragment names a heading of the *English*
  page.  The ordinal is computed on English; on a translated page the target is the
  heading at that same index.  A translated page's own slugs are not the fragment.
* **The five links the guide ships**, resolved on the real English pages.

The function is Qt-free and imports only the standard library and
``pixelart_creator.logic.constants``.
"""

from __future__ import annotations

import ast
import importlib.util
import string
import sys
from importlib.resources import files
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import guide_anchors
from pixelart_creator.logic.guide_anchors import heading_ordinal, heading_slugs

# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #


def _page(*lines: str) -> str:
    """Join ``lines`` into a page (LF, trailing newline)."""
    return "\n".join(lines) + "\n"


def _english_page(stem: str) -> str:
    """Return the shipped English guide page ``stem`` as text (read-only)."""
    root = files("pixelart_creator") / "userguide_content" / "content" / "en"
    return (root / f"{stem}.md").read_text(encoding="utf-8")


#: A small English page with one heading of each kind used below.
_ENGLISH = _page(
    "# Frames and layers",
    "",
    "Intro text.",
    "",
    "## Managing frames",
    "",
    "Body.",
    "",
    "## Project confirmations",
    "",
    "### Details",
)

#: The same page translated: same structure, translated headings.
_SPANISH = _page(
    "# Fotogramas y capas",
    "",
    "Texto de introduccion.",
    "",
    "## Gestion de fotogramas",
    "",
    "Cuerpo.",
    "",
    "## Confirmaciones del proyecto",
    "",
    "### Detalles",
)


# --------------------------------------------------------------------------- #
# heading_slugs: the slug rule                                                 #
# --------------------------------------------------------------------------- #


class TestHeadingSlugsRule:
    """The slug of a single heading."""

    def test_returns_a_tuple_of_str(self) -> None:
        result = heading_slugs("# One\n\n## Two\n")
        assert isinstance(result, tuple)
        assert all(isinstance(slug, str) for slug in result)

    def test_lower_cases(self) -> None:
        assert heading_slugs("# Managing FRAMES\n") == ("managing-frames",)

    def test_spaces_become_hyphens(self) -> None:
        assert heading_slugs("# a b c\n") == ("a-b-c",)

    def test_keeps_hyphen_and_underscore(self) -> None:
        assert heading_slugs("# well-known snake_case\n") == ("well-known-snake_case",)

    def test_keeps_digits(self) -> None:
        assert heading_slugs("# Step 2 of 3\n") == ("step-2-of-3",)

    @pytest.mark.parametrize(
        ("heading", "slug"),
        [
            ("Panning vs. building a selection", "panning-vs-building-a-selection"),
            ("Copy instead of move: hold Ctrl", "copy-instead-of-move-hold-ctrl"),
            ("Frame tags (named animations)", "frame-tags-named-animations"),
            (
                "Undo, redo and what is *not* undoable",
                "undo-redo-and-what-is-not-undoable",
            ),
            ("Why? Because!", "why-because"),
            ("100% done", "100-done"),
        ],
    )
    def test_removes_punctuation(self, heading: str, slug: str) -> None:
        assert heading_slugs(f"# {heading}\n") == (slug,)

    def test_removed_punctuation_between_spaces_leaves_two_hyphens(self) -> None:
        # Spaces are converted one for one; the removed '&' leaves "  " -> "--".
        assert heading_slugs("# Selection & floating move/copy\n") == (
            "selection--floating-movecopy",
        )

    def test_keeps_letters_of_other_scripts_lowercased(self) -> None:
        assert heading_slugs("# Gestion de Fotogramas Ñandú\n") == (
            "gestion-de-fotogramas-ñandú",
        )
        assert heading_slugs("# Управление кадрами\n") == ("управление-кадрами",)
        assert heading_slugs("# フレームの管理\n") == ("フレームの管理",)

    def test_emphasis_is_reduced_to_its_text(self) -> None:
        assert heading_slugs("# The *foo* and **bar** and _baz_\n") == (
            "the-foo-and-bar-and-baz",
        )

    def test_underscore_inside_a_word_is_not_emphasis(self) -> None:
        assert heading_slugs("# snake_case name\n") == ("snake_case-name",)

    def test_code_span_is_reduced_to_its_text(self) -> None:
        assert heading_slugs("# Press `Ctrl+C` now\n") == ("press-ctrlc-now",)

    def test_link_is_reduced_to_its_text(self) -> None:
        assert heading_slugs("# See [the guide](other.md#part) now\n") == (
            "see-the-guide-now",
        )

    def test_image_target_is_not_part_of_the_slug(self) -> None:
        slugs = heading_slugs("# Logo ![alt](pics/logo.png) here\n")
        assert len(slugs) == 1
        assert "pics" not in slugs[0]
        assert "png" not in slugs[0]


# --------------------------------------------------------------------------- #
# heading_slugs: repeated headings                                             #
# --------------------------------------------------------------------------- #


class TestHeadingSlugsRepeated:
    """A repeated slug is suffixed -1, -2, ... in document order."""

    def test_second_and_third_occurrences_are_suffixed(self) -> None:
        page = _page("# Notes", "", "## Notes", "", "### Notes")
        assert heading_slugs(page) == ("notes", "notes-1", "notes-2")

    def test_repeat_is_found_across_heading_levels_and_kinds(self) -> None:
        page = _page("Notes", "=====", "", "## Notes")
        assert heading_slugs(page) == ("notes", "notes-1")

    def test_repeat_counts_by_slug_not_by_raw_text(self) -> None:
        page = _page("# Notes!", "", "# *Notes*", "", "# NOTES")
        assert heading_slugs(page) == ("notes", "notes-1", "notes-2")

    def test_a_suffixed_slug_never_equals_another_heading_slug(self) -> None:
        # A heading literally titled "A-1" keeps its slug apart from the second "A".
        page = _page("# A", "", "# A", "", "# A-1")
        slugs = heading_slugs(page)
        assert slugs[:2] == ("a", "a-1")
        assert len(set(slugs)) == 3
        assert slugs == ("a", "a-1", "a-1-1")

    def test_heading_literally_titled_with_a_suffix_comes_first(self) -> None:
        page = _page("# A-1", "", "# A", "", "# A")
        slugs = heading_slugs(page)
        assert slugs[0] == "a-1"
        assert slugs[1] == "a"
        assert len(set(slugs)) == 3


# --------------------------------------------------------------------------- #
# heading_slugs: which lines are headings                                      #
# --------------------------------------------------------------------------- #


class TestHeadingSlugsRecognition:
    """ATX and setext headings count; code, indented code and HTML do not."""

    def test_empty_page_has_no_slugs(self) -> None:
        assert heading_slugs("") == ()

    def test_page_without_headings_has_no_slugs(self) -> None:
        assert heading_slugs("Just text.\n\nMore text.\n") == ()

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_atx_levels_one_to_six_count(self, level: int) -> None:
        assert heading_slugs(f"{'#' * level} Title\n") == ("title",)

    def test_seven_hashes_is_not_a_heading(self) -> None:
        assert heading_slugs("####### Title\n") == ()

    def test_hash_without_space_is_not_a_heading(self) -> None:
        assert heading_slugs("#hashtag\n") == ()

    @pytest.mark.parametrize("indent", [1, 2, 3])
    def test_up_to_three_spaces_of_indent_still_count(self, indent: int) -> None:
        assert heading_slugs(f"{' ' * indent}## Title\n") == ("title",)

    def test_closing_hash_run_is_not_part_of_the_slug(self) -> None:
        assert heading_slugs("## Title ##\n") == ("title",)

    def test_trailing_spaces_are_not_part_of_the_slug(self) -> None:
        assert heading_slugs("## Title   \n") == ("title",)

    def test_setext_level_one_counts(self) -> None:
        assert heading_slugs("Title\n=====\n") == ("title",)

    def test_setext_level_two_counts(self) -> None:
        assert heading_slugs("Sub title\n---------\n") == ("sub-title",)

    def test_thematic_break_after_a_blank_line_is_not_a_heading(self) -> None:
        assert heading_slugs("Some text.\n\n---\n\nMore text.\n") == ()

    def test_atx_and_setext_keep_document_order(self) -> None:
        page = _page(
            "First", "=====", "", "## Second", "", "Third", "-----", "", "# Fourth"
        )
        assert heading_slugs(page) == ("first", "second", "third", "fourth")

    def test_backtick_fence_hides_headings(self) -> None:
        page = _page("# Real", "", "```", "# not a heading", "```", "", "## Also real")
        assert heading_slugs(page) == ("real", "also-real")

    def test_fence_with_info_string_hides_headings(self) -> None:
        page = _page("```python", "# comment line", "```", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_tilde_fence_hides_headings(self) -> None:
        page = _page("~~~", "# not a heading", "~~~", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_longer_closing_fence_closes(self) -> None:
        page = _page("```", "# hidden", "`````", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_shorter_fence_inside_a_fence_does_not_close_it(self) -> None:
        page = _page("````", "```", "# hidden", "```", "````", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_unclosed_fence_hides_the_rest_of_the_page(self) -> None:
        page = _page("# Real", "", "```", "# hidden", "", "## hidden too")
        assert heading_slugs(page) == ("real",)

    def test_setext_underline_inside_a_fence_makes_no_heading(self) -> None:
        page = _page("```", "text", "=====", "```", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_indented_code_hides_headings(self) -> None:
        page = _page("# Real", "", "    # code, not a heading", "", "## Also real")
        assert heading_slugs(page) == ("real", "also-real")

    def test_indented_code_at_the_start_of_the_page_hides_headings(self) -> None:
        page = _page("    # code", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_tab_indented_code_hides_headings(self) -> None:
        page = _page("# Real", "", "\t# code", "", "## Also real")
        assert heading_slugs(page) == ("real", "also-real")

    def test_html_comment_hides_headings(self) -> None:
        page = _page("<!--", "# hidden", "-->", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_html_block_hides_headings_until_the_blank_line(self) -> None:
        page = _page("<div>", "# hidden", "</div>", "", "# Real")
        assert heading_slugs(page) == ("real",)

    def test_heading_after_the_html_block_counts(self) -> None:
        page = _page("<div>", "x", "</div>", "", "# Real", "", "## Also real")
        assert heading_slugs(page) == ("real", "also-real")

    def test_crlf_page_gives_the_same_slugs_as_lf(self) -> None:
        page = _page(
            "# One", "", "Two", "---", "", "```", "# hidden", "```", "", "# One"
        )
        assert heading_slugs(page.replace("\n", "\r\n")) == heading_slugs(page)
        assert heading_slugs(page) == ("one", "two", "one-1")

    def test_result_is_deterministic(self) -> None:
        assert heading_slugs(_ENGLISH) == heading_slugs(_ENGLISH)


# --------------------------------------------------------------------------- #
# heading_ordinal                                                              #
# --------------------------------------------------------------------------- #


class TestHeadingOrdinal:
    """The zero-based index of the heading a fragment names."""

    def test_names_the_first_heading(self) -> None:
        assert heading_ordinal(_ENGLISH, "frames-and-layers") == 0

    def test_names_a_later_heading_by_its_position_among_all_headings(self) -> None:
        assert heading_ordinal(_ENGLISH, "managing-frames") == 1
        assert heading_ordinal(_ENGLISH, "project-confirmations") == 2
        assert heading_ordinal(_ENGLISH, "details") == 3

    def test_ordinal_indexes_heading_slugs(self) -> None:
        slugs = heading_slugs(_ENGLISH)
        for index, slug in enumerate(slugs):
            assert heading_ordinal(_ENGLISH, slug) == index

    def test_a_single_leading_hash_is_ignored(self) -> None:
        assert heading_ordinal(_ENGLISH, "#managing-frames") == 1
        assert heading_ordinal(_ENGLISH, "#managing-frames") == heading_ordinal(
            _ENGLISH, "managing-frames"
        )

    def test_result_is_an_int(self) -> None:
        result = heading_ordinal(_ENGLISH, "managing-frames")
        assert isinstance(result, int)
        assert not isinstance(result, bool)

    def test_fragment_that_names_no_heading_is_none(self) -> None:
        assert heading_ordinal(_ENGLISH, "no-such-heading") is None
        assert heading_ordinal(_ENGLISH, "#no-such-heading") is None

    def test_unknown_fragment_does_not_default_to_the_first_heading(self) -> None:
        assert heading_ordinal(_ENGLISH, "no-such-heading") != 0

    def test_empty_fragment_is_none(self) -> None:
        assert heading_ordinal(_ENGLISH, "") is None

    def test_lone_hash_fragment_is_none(self) -> None:
        assert heading_ordinal(_ENGLISH, "#") is None

    def test_empty_fragment_is_none_even_when_a_heading_has_no_text(self) -> None:
        page = _page("# Intro", "", "##", "", "## Next")
        assert heading_ordinal(page, "") is None
        assert heading_ordinal(page, "#") is None

    def test_empty_page_is_none(self) -> None:
        assert heading_ordinal("", "managing-frames") is None
        assert heading_ordinal("", "") is None

    def test_page_without_headings_is_none(self) -> None:
        assert heading_ordinal("Only text.\n", "managing-frames") is None

    def test_partial_slug_does_not_match(self) -> None:
        assert heading_ordinal(_ENGLISH, "managing") is None
        assert heading_ordinal(_ENGLISH, "managing-frames-extra") is None

    def test_repeated_heading_first_is_the_plain_slug(self) -> None:
        page = _page("# Intro", "", "## Notes", "", "## Other", "", "## Notes")
        assert heading_ordinal(page, "notes") == 1

    def test_repeated_heading_later_occurrences_use_the_suffix(self) -> None:
        page = _page(
            "# Intro", "", "## Notes", "", "## Other", "", "## Notes", "", "## Notes"
        )
        assert heading_ordinal(page, "notes-1") == 3
        assert heading_ordinal(page, "notes-2") == 4
        assert heading_ordinal(page, "notes-3") is None

    def test_fragment_naming_only_a_heading_inside_a_fence_is_none(self) -> None:
        page = _page("# Real", "", "```", "# Hidden", "```")
        assert heading_ordinal(page, "hidden") is None
        assert heading_ordinal(page, "real") == 0

    def test_ordinal_ignores_hidden_lines_when_counting(self) -> None:
        page = _page("# A", "", "```", "# hidden", "```", "", "    # code", "", "## B")
        assert heading_ordinal(page, "b") == 1

    def test_setext_heading_is_named_and_counted(self) -> None:
        page = _page("# One", "", "Two", "---", "", "## Three")
        assert heading_ordinal(page, "two") == 1
        assert heading_ordinal(page, "three") == 2

    def test_input_is_not_modified_and_calls_are_repeatable(self) -> None:
        before = _ENGLISH
        first = heading_ordinal(_ENGLISH, "managing-frames")
        second = heading_ordinal(_ENGLISH, "managing-frames")
        assert first == second
        assert _ENGLISH == before


class TestTranslatedPages:
    """REQ-L10N-UI-019 clause 3: the fragment names the English heading."""

    def test_pages_are_in_step(self) -> None:
        assert len(heading_slugs(_ENGLISH)) == len(heading_slugs(_SPANISH)) == 4

    def test_the_english_fragment_resolves_on_the_english_page(self) -> None:
        assert heading_ordinal(_ENGLISH, "managing-frames") == 1

    def test_the_target_on_the_translated_page_is_the_heading_at_the_same_index(
        self,
    ) -> None:
        ordinal = heading_ordinal(_ENGLISH, "project-confirmations")
        assert ordinal is not None
        translated = heading_slugs(_SPANISH)
        assert translated[ordinal] == "confirmaciones-del-proyecto"

    def test_the_english_fragment_does_not_resolve_on_the_translated_text(self) -> None:
        # The translated page's own slugs are not the fragment: the caller must
        # take the ordinal from the English source, never from the translation.
        assert heading_ordinal(_SPANISH, "managing-frames") is None
        assert heading_ordinal(_SPANISH, "project-confirmations") is None

    def test_the_translated_slug_resolves_on_the_translated_page_to_the_same_index(
        self,
    ) -> None:
        assert heading_ordinal(_SPANISH, "confirmaciones-del-proyecto") == (
            heading_ordinal(_ENGLISH, "project-confirmations")
        )

    def test_a_translated_heading_that_equals_an_english_slug_does_not_move_the_target(
        self,
    ) -> None:
        # The counterpart is found by position, not by text: even when the
        # translated page happens to carry the English slug at another index, the
        # English ordinal is what the caller uses.
        shuffled = _page("# Managing frames", "", "## A", "", "## B", "", "### C")
        ordinal = heading_ordinal(_ENGLISH, "managing-frames")
        assert ordinal == 1
        assert heading_slugs(shuffled)[ordinal] == "a"


# --------------------------------------------------------------------------- #
# the five links the guide ships, on the real English pages                    #
# --------------------------------------------------------------------------- #

#: (page stem, fragment, expected zero-based ordinal, heading it names).  The
#: expected ordinals were counted by hand from the page's headings, not by the
#: function: animation-timeline.md has 13 headings (title first); selection-and-
#: transform.md has 11.
_SHIPPED_LINKS = [
    ("animation-timeline", "managing-frames", 2, "Managing frames"),
    ("animation-timeline", "project-confirmations", 8, "Project confirmations"),
    (
        "selection-and-transform",
        "panning-vs-building-a-selection",
        2,
        "Panning vs. building a selection",
    ),
    (
        "selection-and-transform",
        "copy-instead-of-move-hold-ctrl",
        5,
        "Copy instead of move: hold Ctrl",
    ),
]


class TestShippedFragmentsOnTheRealEnglishPages:
    """The fragments the eight guide trees ship resolve on the English pages."""

    @pytest.mark.parametrize(
        ("stem", "fragment", "expected", "heading"), _SHIPPED_LINKS
    )
    def test_fragment_resolves_to_the_named_heading(
        self, stem: str, fragment: str, expected: int, heading: str
    ) -> None:
        page = _english_page(stem)
        ordinal = heading_ordinal(page, fragment)
        print(f"{stem}.md #{fragment} -> ordinal {ordinal} ({heading!r})")
        assert ordinal == expected

    def test_the_link_with_a_leading_hash_resolves_the_same(self) -> None:
        page = _english_page("animation-timeline")
        assert heading_ordinal(page, "#managing-frames") == 2

    def test_real_pages_heading_counts(self) -> None:
        assert len(heading_slugs(_english_page("animation-timeline"))) == 13
        assert len(heading_slugs(_english_page("selection-and-transform"))) == 11

    def test_the_title_slug_of_the_selection_page_keeps_both_hyphens(self) -> None:
        slugs = heading_slugs(_english_page("selection-and-transform"))
        assert slugs[0] == "selection--floating-movecopy"

    def test_every_heading_of_both_pages_round_trips(self) -> None:
        for stem in ("animation-timeline", "selection-and-transform"):
            page = _english_page(stem)
            slugs = heading_slugs(page)
            assert len(set(slugs)) == len(slugs)
            for index, slug in enumerate(slugs):
                assert heading_ordinal(page, slug) == index

    def test_a_fragment_that_names_no_heading_of_the_real_page_is_none(self) -> None:
        page = _english_page("animation-timeline")
        assert heading_ordinal(page, "no-such-heading") is None
        # A heading of the OTHER page is not a heading of this one.
        assert heading_ordinal(page, "copy-instead-of-move-hold-ctrl") is None


# --------------------------------------------------------------------------- #
# the module's declared shape                                                  #
# --------------------------------------------------------------------------- #


class TestModuleShape:
    """Qt-free; imports only the standard library and logic/constants.py."""

    def _imported_modules(self) -> set[str]:
        origin = importlib.util.find_spec("pixelart_creator.logic.guide_anchors")
        assert origin is not None and origin.origin is not None
        tree = ast.parse(Path(origin.origin).read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, "relative imports are not allowed here"
                assert node.module is not None
                names.add(node.module)
        return names

    def test_imports_nothing_but_the_stdlib_and_logic_constants(self) -> None:
        allowed_project = {"pixelart_creator.logic.constants"}
        for name in self._imported_modules():
            if name in allowed_project:
                continue
            assert name.split(".")[0] in sys.stdlib_module_names, name

    def test_does_not_import_qt_or_the_ui_layer(self) -> None:
        for name in self._imported_modules():
            assert not name.startswith(("PySide6", "PyQt", "shiboken"))
            assert not name.startswith("pixelart_creator.ui")

    def test_public_functions_are_documented(self) -> None:
        assert guide_anchors.heading_slugs.__doc__
        assert guide_anchors.heading_ordinal.__doc__
        assert guide_anchors.__doc__


# --------------------------------------------------------------------------- #
# properties                                                                   #
# --------------------------------------------------------------------------- #

_WORD = st.text(alphabet=string.ascii_letters, min_size=1, max_size=8)
#: Heading text: words joined by single spaces.  Letters only, so a suffixed slug
#: ("a-1") can never be produced by a heading's own text.
_HEADING_TEXT = st.lists(_WORD, min_size=1, max_size=4).map(" ".join)
_HEADING = st.tuples(st.integers(min_value=1, max_value=6), _HEADING_TEXT)
_PARAGRAPH = st.lists(_WORD, min_size=1, max_size=6).map(" ".join)


def _model_slugs(texts: list[str]) -> tuple[str, ...]:
    """Independent oracle for letters-and-spaces headings."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for text in texts:
        base = text.lower().replace(" ", "-")
        count = seen.get(base, 0)
        seen[base] = count + 1
        out.append(base if count == 0 else f"{base}-{count}")
    return tuple(out)


def _build_page(headings: list[tuple[int, str]], paragraphs: list[str]) -> str:
    lines: list[str] = []
    for index, (level, text) in enumerate(headings):
        lines += [f"{'#' * level} {text}", ""]
        lines += [paragraphs[index % len(paragraphs)], ""]
    return "\n".join(lines)


@given(
    headings=st.lists(_HEADING, min_size=0, max_size=12),
    paragraphs=st.lists(_PARAGRAPH, min_size=1, max_size=3),
)
def test_slugs_match_the_model_and_ignore_levels_and_paragraphs(
    headings: list[tuple[int, str]], paragraphs: list[str]
) -> None:
    page = _build_page(headings, paragraphs)
    assert heading_slugs(page) == _model_slugs([text for _, text in headings])


@given(
    headings=st.lists(_HEADING, min_size=1, max_size=12),
    paragraphs=st.lists(_PARAGRAPH, min_size=1, max_size=3),
)
def test_every_slug_round_trips_through_the_ordinal(
    headings: list[tuple[int, str]], paragraphs: list[str]
) -> None:
    page = _build_page(headings, paragraphs)
    slugs = heading_slugs(page)
    assert len(slugs) == len(headings)
    assert len(set(slugs)) == len(slugs)
    for index, slug in enumerate(slugs):
        assert heading_ordinal(page, slug) == index
        assert heading_ordinal(page, "#" + slug) == index
        assert slugs[index] == slug


@given(
    headings=st.lists(_HEADING, min_size=0, max_size=8),
    paragraphs=st.lists(_PARAGRAPH, min_size=1, max_size=3),
    fragment=_WORD,
)
def test_a_fragment_outside_the_slugs_is_none(
    headings: list[tuple[int, str]], paragraphs: list[str], fragment: str
) -> None:
    page = _build_page(headings, paragraphs)
    if fragment.lower() in heading_slugs(page):
        return
    assert heading_ordinal(page, fragment.lower()) is None


@given(
    headings=st.lists(_HEADING, min_size=1, max_size=8),
    paragraphs=st.lists(_PARAGRAPH, min_size=1, max_size=3),
    hidden=st.lists(_HEADING_TEXT, min_size=1, max_size=3),
    position=st.integers(min_value=0, max_value=8),
)
def test_a_fenced_block_never_changes_the_slugs(
    headings: list[tuple[int, str]],
    paragraphs: list[str],
    hidden: list[str],
    position: int,
) -> None:
    page = _build_page(headings, paragraphs)
    blocks = page.split("\n\n")
    fenced = "```\n" + "\n".join(f"# {text}" for text in hidden) + "\n```"
    blocks.insert(min(position, len(blocks)), fenced)
    assert heading_slugs("\n\n".join(blocks)) == heading_slugs(page)


@given(
    headings=st.lists(_HEADING, min_size=0, max_size=8),
    paragraphs=st.lists(_PARAGRAPH, min_size=1, max_size=3),
)
def test_line_ending_style_does_not_matter(
    headings: list[tuple[int, str]], paragraphs: list[str]
) -> None:
    page = _build_page(headings, paragraphs)
    assert heading_slugs(page.replace("\n", "\r\n")) == heading_slugs(page)
