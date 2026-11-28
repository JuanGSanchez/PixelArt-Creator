"""Every heading link the guide ships names a heading of its target page (zero Qt).

Scenario SC-L10N-UI-019-3 of REQ-L10N-UI-019 (and REQ-L10N-DATA-003, heading parity,
as used here).  A guide page may link to a heading, either of its own page
(``](#managing-frames)``) or of another page
(``](selection-and-transform.md#copy-instead-of-move-hold-ctrl)``).  The fragment
names a heading of the *English* target page; on a translated page the target is the
heading at the same position (the same zero-based index among the page's headings).
This check runs, Qt-free, over the eight guide trees and fails when

* a heading link's fragment names no heading of its English target page
  (the message names the tree, page, line and fragment);
* a translated target page has a different number of headings from its English page
  (the message names the page and says its headings are not in step with English);
* nothing was examined at all (the message says "nothing examined"), or a tree
  contributes no link.

Every link examined is printed with its tree, page, line, fragment, the heading it
names in the English target page and the heading at that position in the tree's own
page, followed by the number of links examined per tree.  Run with ``-s`` to see it.

A link is a *heading link* when it has a fragment, has no URL scheme, and the
fragment is not a topic id (a fragment equal to a topic id is a topic link, clause 5).

The planted controls run on a copy of the bundle under ``tmp_path``; the shipped
files are never written.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

import pytest

from pixelart_creator.data import guide_content
from pixelart_creator.logic.guide_anchors import heading_ordinal, heading_slugs
from pixelart_creator.logic.scope_floor import ScopeFloorError, require_non_empty_scope

#: The eight guide languages the product ships.
LANGUAGES: tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ko", "ja")
ENGLISH = "en"

_PAGE_SUFFIX = ".md"

# --------------------------------------------------------------------------- #
# link extraction                                                              #
# --------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_CODE_SPAN_RE = re.compile(r"(`+)(?:(?!\n[ \t]*\n).)+?(?<!`)\1(?!`)", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
#: The "](target" of an inline link; the link text may wrap over lines before it.
_TARGET_RE = re.compile(r"\]\(\s*<?([^)\s>]+)")
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


def _blank(match: re.Match[str]) -> str:
    """Replace a match with spaces, keeping its newlines (so line numbers hold)."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _without_code(text: str) -> str:
    """Blank fenced blocks, code spans and images, keeping every line number."""
    kept: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.split("\n"):
        match = _FENCE_RE.match(line)
        if fence is not None:
            if (
                match
                and match.group(1)[0] == fence[0]
                and len(match.group(1)) >= fence[1]
                and not match.group(2).strip()
            ):
                fence = None
            kept.append("")
            continue
        if match:
            fence = (match.group(1)[0], len(match.group(1)))
            kept.append("")
            continue
        kept.append(line)
    body = "\n".join(kept)
    body = _CODE_SPAN_RE.sub(_blank, body)
    return _IMAGE_RE.sub(_blank, body)


@dataclass(frozen=True)
class Link:
    """One inline link of a page: where it is and what it points at."""

    line: int
    path: str
    fragment: str


def extract_links(text: str) -> list[Link]:
    """Return every inline link of ``text`` that has a fragment, in order.

    ``line`` is the line of the closing ``](`` of the link (a link text may wrap).
    """
    body = _without_code(text)
    links: list[Link] = []
    for match in _TARGET_RE.finditer(body):
        target = match.group(1)
        path, _, fragment = target.partition("#")
        if not fragment:
            continue
        links.append(Link(body.count("\n", 0, match.start()) + 1, path, fragment))
    return links


def is_heading_link(link: Link, topic_ids: frozenset[str]) -> bool:
    """Return whether ``link`` names a heading (not a scheme link, not a topic id)."""
    if _SCHEME_RE.match(link.path):
        return False
    return link.fragment not in topic_ids


# --------------------------------------------------------------------------- #
# the check                                                                    #
# --------------------------------------------------------------------------- #


@dataclass
class LinkCheck:
    """The outcome of one run over a content root."""

    examined: dict[str, int] = field(default_factory=dict)
    printed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Links examined over every tree."""
        return sum(self.examined.values())

    @property
    def ok(self) -> bool:
        """True when nothing was found wrong (the run exits 0)."""
        return not self.problems


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def check_heading_links(
    content: Path, topic_ids: frozenset[str], languages: tuple[str, ...] = LANGUAGES
) -> LinkCheck:
    """Examine every heading link of every tree of ``content``."""
    result = LinkCheck()
    english_dir = content / ENGLISH
    unsteady: set[tuple[str, str]] = set()
    for tree in languages:
        folder = content / tree
        result.examined[tree] = 0
        if not folder.is_dir():
            result.problems.append(f"{tree}: the tree is missing from {content}")
            continue
        for page_file in sorted(folder.glob(f"*{_PAGE_SUFFIX}")):
            for link in extract_links(_read(page_file)):
                if not is_heading_link(link, topic_ids):
                    continue
                result.examined[tree] += 1
                _examine(
                    result, content, english_dir, tree, page_file.name, link, unsteady
                )
    for tree, count in result.examined.items():
        print(f"heading links examined: {tree}: {count}")
    for line in result.printed:
        print(line)
    if result.total == 0:
        try:
            require_non_empty_scope(
                "guide-heading-links", result.total, of="heading links", root=content
            )
        except ScopeFloorError as error:
            result.problems.append(f"nothing examined: {error}")
    else:
        for tree, count in result.examined.items():
            if count == 0 and (content / tree).is_dir():
                result.problems.append(
                    f"{tree}: no heading link examined (nothing examined)"
                )
    for problem in result.problems:
        print(f"PROBLEM {problem}")
    return result


def _examine(
    result: LinkCheck,
    content: Path,
    english_dir: Path,
    tree: str,
    page: str,
    link: Link,
    unsteady: set[tuple[str, str]],
) -> None:
    where = f"{tree}/{page} line {link.line} fragment #{link.fragment}"
    target = page if not link.path else Path(link.path).name
    if not target.endswith(_PAGE_SUFFIX):
        result.problems.append(f"{where}: the link target {link.path!r} is not a page")
        return
    english_file = english_dir / target
    if not english_file.is_file():
        result.problems.append(f"{where}: English target page {target} does not exist")
        return
    english_text = _read(english_file)
    ordinal = heading_ordinal(english_text, link.fragment)
    if ordinal is None:
        result.problems.append(
            f"{where}: names no heading of the English page {target}"
        )
        return
    english_slugs = heading_slugs(english_text)
    tree_file = content / tree / target
    if not tree_file.is_file():
        result.problems.append(f"{where}: the page {tree}/{target} does not exist")
        return
    tree_slugs = heading_slugs(_read(tree_file))
    if len(tree_slugs) != len(english_slugs):
        key = (tree, target)
        if key not in unsteady:
            unsteady.add(key)
            result.problems.append(
                f"{tree}/{target}: {len(tree_slugs)} headings, English has "
                f"{len(english_slugs)}: its headings are not in step with English"
            )
        return
    result.printed.append(
        f"{where} -> English {target} heading #{ordinal} {english_slugs[ordinal]!r}; "
        f"{tree} heading at that position {tree_slugs[ordinal]!r}"
    )


# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _bundle_content() -> Path:
    return Path(str(files("pixelart_creator") / "userguide_content" / "content"))


def _topic_ids() -> frozenset[str]:
    manifest = guide_content.load_manifest()
    return frozenset(
        topic.id for section in manifest.sections for topic in section.topics
    )


@pytest.fixture(scope="module")
def topic_ids() -> frozenset[str]:
    """The topic ids of the shipped manifest."""
    return _topic_ids()


@pytest.fixture()
def scratch(tmp_path: Path) -> Path:
    """A throw-away copy of the shipped content tree; the bundle is never written."""
    target = tmp_path / "content"
    shutil.copytree(_bundle_content(), target)
    return target


def _append(path: Path, text: str) -> None:
    path.write_bytes(path.read_bytes() + text.encode("utf-8"))


# --------------------------------------------------------------------------- #
# the shipped trees                                                            #
# --------------------------------------------------------------------------- #


class TestShippedTrees:
    """SC-L10N-UI-019-3, nothing planted."""

    def test_the_eight_trees_are_present(self) -> None:
        folders = {p.name for p in _bundle_content().iterdir() if p.is_dir()}
        assert set(LANGUAGES) <= folders

    def test_every_shipped_heading_link_names_a_heading_in_each_tree(
        self, topic_ids: frozenset[str]
    ) -> None:
        result = check_heading_links(_bundle_content(), topic_ids)
        assert result.problems == []
        assert result.ok

    def test_each_of_the_eight_trees_examines_a_non_zero_number_of_links(
        self, topic_ids: frozenset[str]
    ) -> None:
        result = check_heading_links(_bundle_content(), topic_ids)
        assert set(result.examined) == set(LANGUAGES)
        for tree in LANGUAGES:
            assert result.examined[tree] > 0, tree

    def test_every_tree_examines_the_same_number_of_links_as_english(
        self, topic_ids: frozenset[str]
    ) -> None:
        result = check_heading_links(_bundle_content(), topic_ids)
        assert {result.examined[tree] for tree in LANGUAGES} == {
            result.examined[ENGLISH]
        }

    def test_every_link_is_printed_with_the_heading_it_names(
        self, topic_ids: frozenset[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = check_heading_links(_bundle_content(), topic_ids)
        out = capsys.readouterr().out
        assert len(result.printed) == result.total
        for tree in LANGUAGES:
            assert f"heading links examined: {tree}: " in out
        assert "English animation-timeline.md heading #2 'managing-frames'" in out

    def test_the_english_tree_resolves_the_cross_page_link(
        self, topic_ids: frozenset[str]
    ) -> None:
        links = extract_links(
            _read(_bundle_content() / ENGLISH / "animation-timeline.md")
        )
        cross = [
            link
            for link in links
            if is_heading_link(link, topic_ids) and link.path.endswith(_PAGE_SUFFIX)
        ]
        assert [(link.path, link.fragment) for link in cross] == [
            ("selection-and-transform.md", "copy-instead-of-move-hold-ctrl")
        ]


# --------------------------------------------------------------------------- #
# link extraction, unit level                                                  #
# --------------------------------------------------------------------------- #


class TestExtractLinks:
    """What counts as a link, and on which line."""

    def test_same_page_fragment(self) -> None:
        assert extract_links("See [it](#managing-frames).\n") == [
            Link(1, "", "managing-frames")
        ]

    def test_cross_page_fragment(self) -> None:
        assert extract_links("[it](other.md#part)\n") == [Link(1, "other.md", "part")]

    def test_link_without_a_fragment_is_not_returned(self) -> None:
        assert extract_links("[it](other.md) and [x](https://example.org/)\n") == []

    def test_link_text_wrapping_over_lines_reports_the_line_of_the_target(self) -> None:
        assert extract_links("a\n[text that\nwraps](#frag)\n") == [Link(3, "", "frag")]

    def test_two_links_on_a_page_come_in_order(self) -> None:
        links = extract_links("[a](#one)\n\n[b](x.md#two)\n")
        assert [(link.line, link.fragment) for link in links] == [
            (1, "one"),
            (3, "two"),
        ]

    def test_fenced_block_is_ignored_and_keeps_the_line_count(self) -> None:
        text = "```\n[a](#hidden)\n```\n[b](#shown)\n"
        assert extract_links(text) == [Link(4, "", "shown")]

    def test_tilde_fenced_block_is_ignored_and_keeps_the_line_count(self) -> None:
        text = "~~~\n[a](#hidden)\n~~~\n[b](#shown)\n"
        assert extract_links(text) == [Link(4, "", "shown")]

    def test_code_span_is_ignored(self) -> None:
        assert extract_links("`[a](#hidden)` and [b](#shown)\n") == [
            Link(1, "", "shown")
        ]

    def test_image_is_ignored(self) -> None:
        assert extract_links("![alt](pic.png#hidden) [b](#shown)\n") == [
            Link(1, "", "shown")
        ]


class TestIsHeadingLink:
    """Which links the check examines."""

    IDS = frozenset({"layers", "colour-hub"})

    def test_same_page_fragment_is_a_heading_link(self) -> None:
        assert is_heading_link(Link(1, "", "managing-frames"), self.IDS)

    def test_cross_page_fragment_is_a_heading_link(self) -> None:
        assert is_heading_link(Link(1, "other.md", "part"), self.IDS)

    def test_fragment_equal_to_a_topic_id_is_a_topic_link(self) -> None:
        assert not is_heading_link(Link(1, "", "layers"), self.IDS)

    def test_a_topic_id_fragment_after_a_page_path_is_a_topic_link(self) -> None:
        assert not is_heading_link(Link(1, "other.md", "colour-hub"), self.IDS)

    def test_other_scheme_is_not_a_heading_link(self) -> None:
        assert not is_heading_link(
            Link(1, "https://example.org/", "managing-frames"), self.IDS
        )


# --------------------------------------------------------------------------- #
# the planted controls (scratch copy; SC-L10N-UI-019-3, rows 2 to 4)           #
# --------------------------------------------------------------------------- #


class TestPlantedControls:
    """Each planted defect fails, and is named, in a copy of the bundle."""

    def test_the_unplanted_copy_passes(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        assert check_heading_links(scratch, topic_ids).ok

    def test_a_fragment_that_names_no_heading_fails_naming_tree_page_line_fragment(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        page = scratch / "fr" / "animation-timeline.md"
        before = _read(page)
        _append(page, "\n[planted](#no-such-heading)\n")
        planted_line = _read(page).count("\n", 0, _read(page).rindex("](")) + 1
        result = check_heading_links(scratch, topic_ids)
        assert not result.ok
        expected = (
            f"fr/animation-timeline.md line {planted_line} fragment #no-such-heading"
        )
        assert any(expected in problem for problem in result.problems), result.problems
        assert len(result.problems) == 1
        assert _read(page).startswith(before)

    def test_a_cross_page_fragment_that_names_no_heading_fails(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        _append(
            scratch / "ja" / "animation-timeline.md",
            "\n[planted](selection-and-transform.md#no-such-heading)\n",
        )
        result = check_heading_links(scratch, topic_ids)
        assert any(
            "ja/animation-timeline.md" in problem
            and "#no-such-heading" in problem
            and "selection-and-transform.md" in problem
            for problem in result.problems
        ), result.problems

    def test_a_valid_planted_link_is_examined_and_passes(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        baseline = check_heading_links(scratch, topic_ids).examined["de"]
        _append(
            scratch / "de" / "animation-timeline.md",
            "\n[planted](selection-and-transform.md#copy-instead-of-move-hold-ctrl)\n",
        )
        result = check_heading_links(scratch, topic_ids)
        assert result.ok
        assert result.examined["de"] == baseline + 1

    def test_a_topic_id_fragment_is_not_examined(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        baseline = check_heading_links(scratch, topic_ids).examined["en"]
        topic = sorted(topic_ids)[0]
        _append(scratch / "en" / "animation-timeline.md", f"\n[planted](#{topic})\n")
        result = check_heading_links(scratch, topic_ids)
        assert result.ok
        assert result.examined["en"] == baseline

    def test_a_translated_page_one_heading_short_fails_naming_the_page(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        page = scratch / "ko" / "selection-and-transform.md"
        lines = _read(page).split("\n")
        last = max(i for i, line in enumerate(lines) if line.startswith("## "))
        lines[last] = lines[last][3:]
        page.write_bytes("\n".join(lines).encode("utf-8"))
        result = check_heading_links(scratch, topic_ids)
        assert not result.ok
        assert any(
            "ko/selection-and-transform.md" in problem
            and "not in step with English" in problem
            for problem in result.problems
        ), result.problems

    def test_a_translated_page_one_heading_longer_fails_naming_the_page(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        _append(scratch / "ru" / "animation-timeline.md", "\n## Extra\n")
        result = check_heading_links(scratch, topic_ids)
        assert any(
            "ru/animation-timeline.md" in problem
            and "not in step with English" in problem
            for problem in result.problems
        ), result.problems

    def test_a_tree_replaced_by_an_empty_folder_fails(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        shutil.rmtree(scratch / "zh_CN")
        (scratch / "zh_CN").mkdir()
        result = check_heading_links(scratch, topic_ids)
        assert not result.ok
        assert any(problem.startswith("zh_CN:") for problem in result.problems)

    def test_a_missing_tree_fails_naming_it(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        shutil.rmtree(scratch / "es")
        result = check_heading_links(scratch, topic_ids)
        assert any(problem.startswith("es:") for problem in result.problems)

    def test_a_translated_page_missing_from_a_tree_fails_naming_it(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        (scratch / "fr" / "selection-and-transform.md").unlink()
        result = check_heading_links(scratch, topic_ids)
        assert not result.ok
        assert any("fr/" in problem for problem in result.problems), result.problems

    def test_every_tree_replaced_by_an_empty_folder_says_nothing_examined(
        self, tmp_path: Path, topic_ids: frozenset[str]
    ) -> None:
        empty = tmp_path / "empty-content"
        for tree in LANGUAGES:
            (empty / tree).mkdir(parents=True)
        result = check_heading_links(empty, topic_ids)
        assert not result.ok
        assert result.total == 0
        assert any("nothing examined" in problem for problem in result.problems)

    def test_a_content_root_without_trees_says_nothing_examined(
        self, tmp_path: Path, topic_ids: frozenset[str]
    ) -> None:
        result = check_heading_links(tmp_path / "absent", topic_ids)
        assert not result.ok
        assert any("nothing examined" in problem for problem in result.problems)

    def test_the_shipped_bundle_is_untouched_by_the_controls(
        self, scratch: Path, topic_ids: frozenset[str]
    ) -> None:
        shipped = _bundle_content() / "fr" / "animation-timeline.md"
        before = shipped.read_bytes()
        _append(scratch / "fr" / "animation-timeline.md", "\n[x](#no-such-heading)\n")
        check_heading_links(scratch, topic_ids)
        assert shipped.read_bytes() == before
