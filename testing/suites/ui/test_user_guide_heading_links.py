"""A guide link to a heading moves the view to that heading (REQ-L10N-UI-019).

The guide's pages hold links to a heading, of the same page (``#managing-frames``)
or of another page (``selection-and-transform.md#copy-instead-of-move-hold-ctrl``).
A fragment names a heading of the page's **English** source; on a translated page
the heading is its counterpart, found by position (REQ-L10N-DATA-003). Clicking
such a link shows the heading's block as the first line at the top of the view, or
shows the view at its maximum with that block in it; a fragment that names no
heading does nothing harmful.

The links are read from the rendered document (the anchors of the page the reader
sees) and clicked by emitting ``anchorClicked`` with the anchor's own URL, as the
browser does. The ordinal of the heading is counted on the English page by a small
reader written here, never by the code under test, and the block it names is found
in the page as rendered (``blockFormat().headingLevel() > 0``).

Placement is read from the view: the vertical scroll value against the top of the
heading block in the document's layout.

Both themes (the suite's ``theme`` fixture applies to every case), offscreen. The
scratch guide root of the absent-page case is a copy under ``tmp_path``; the real
guide content is only read.
"""

from __future__ import annotations

import io
import re
import shutil
import sys
from typing import Callable, Dict, List, Optional, TextIO, Tuple

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QTextBlock
from PySide6.QtWidgets import QApplication, QTextBrowser

import pixelart_creator.data.guide_content as guide_content
from pixelart_creator.data.guide_content import load_manifest, read_content
from pixelart_creator.logic.guide_model import (
    GuideModel,
    GuideTopic,
    build_model,
    content_ref_path,
)
from pixelart_creator.ui.user_guide import User_Guide_Dialog

LANGUAGES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ko", "ja")

#: The page the part-way cases open: long enough to scroll.
LONG_PAGE_CONTENT_REF = "animation-timeline"
OTHER_PAGE_CONTENT_REF = "selection-and-transform"

#: The pixel tolerance between a heading's top and the scroll value.
TOP_TOLERANCE_PX = 2


# --------------------------------------------------------------------------- #
# The oracle: the English page's headings, read here                          #
# --------------------------------------------------------------------------- #

_ATX = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def english_slugs(markdown: str) -> List[str]:
    """Return the slug of each ATX heading of an English page, in document order.

    Lower case, punctuation other than ``-`` and ``_`` removed, spaces to ``-``,
    inline emphasis, code and links reduced to their text, a repeated slug
    suffixed ``-1``, ``-2``. Headings inside fenced blocks are not headings.
    """
    slugs: List[str] = []
    counts: Dict[str, int] = {}
    fenced = False
    for line in markdown.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            continue
        match = None if fenced else _ATX.match(line)
        if match is None:
            continue
        text = _LINK.sub(r"\1", match.group(2)).replace("`", "").replace("*", "")
        slug = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        slugs.append(slug if count == 0 else f"{slug}-{count}")
    return slugs


def english_ordinal(content_ref: str, fragment: str) -> int:
    """Return the ordinal of the heading ``fragment`` names on an English page."""
    page = read_content(content_ref_path(content_ref, "en"))
    slugs = english_slugs(page)
    assert fragment in slugs, (
        f"{content_ref}: no English heading has the slug {fragment!r}; a fragment "
        "names an English heading and stays English in every tree"
    )
    return slugs.index(fragment)


# --------------------------------------------------------------------------- #
# The page as rendered                                                        #
# --------------------------------------------------------------------------- #


def heading_blocks(view: QTextBrowser) -> List[QTextBlock]:
    """Return the heading blocks of the page as rendered, in order."""
    found: List[QTextBlock] = []
    block = view.document().begin()
    while block.isValid():
        if block.blockFormat().headingLevel() > 0:
            found.append(block)
        block = block.next()
    return found


def anchors_of(view: QTextBrowser) -> List[str]:
    """Return the href of each link of the rendered page, in order."""
    hrefs: List[str] = []
    block = view.document().begin()
    while block.isValid():
        last: Optional[str] = None
        fragments = block.begin()
        while not fragments.atEnd():
            fmt = fragments.fragment().charFormat()
            if fmt.isAnchor():
                href = fmt.anchorHref()
                if href != last:
                    hrefs.append(href)
                last = href
            else:
                last = None
            fragments += 1
        block = block.next()
    return hrefs


def block_top(view: QTextBrowser, block: QTextBlock) -> float:
    """Return the top of ``block`` in the document's layout (the scroll coordinate)."""
    return float(view.document().documentLayout().blockBoundingRect(block).top())


def placement_findings(view: QTextBrowser, ordinal: int) -> List[str]:
    """Return what is wrong with where the heading of ``ordinal`` stands in the view.

    The heading's block is the first line at the top of the view, or the view is
    at its maximum with that block in view.
    """
    blocks = heading_blocks(view)
    if ordinal >= len(blocks):
        return [f"the page renders {len(blocks)} headings, none at ordinal {ordinal}"]
    top = block_top(view, blocks[ordinal])
    bar = view.verticalScrollBar()
    value, maximum = bar.value(), bar.maximum()
    if abs(value - top) <= TOP_TOLERANCE_PX:
        return []
    if value == maximum and value <= top <= value + view.viewport().height():
        return []
    return [
        f"heading {ordinal} ({blocks[ordinal].text()!r}) is at {top:.0f}, the view is "
        f"at {value} of {maximum}"
    ]


def scroll_part_way(view: QTextBrowser) -> int:
    """Scroll the view to the middle of its range; return the value."""
    bar = view.verticalScrollBar()
    assert bar.maximum() > 0, "the page is too short to scroll"
    bar.setValue(bar.maximum() // 2)
    return bar.value()


# --------------------------------------------------------------------------- #
# The window                                                                  #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def model() -> GuideModel:
    """The guide's own manifest model, read once."""
    return build_model(load_manifest())


def _topic_by_ref(model: GuideModel, content_ref: str) -> GuideTopic:
    matches = [topic for topic in model.topics() if topic.content_ref == content_ref]
    assert len(matches) == 1, f"{len(matches)} topics hold the page {content_ref!r}"
    return matches[0]


@pytest.fixture
def open_guide(qtbot) -> Callable[..., User_Guide_Dialog]:
    """Return a factory of guide windows in a language, shown and laid out."""

    def make(code: str, **kwargs) -> User_Guide_Dialog:
        dialog = User_Guide_Dialog(None, locale_provider=lambda: code, **kwargs)
        qtbot.addWidget(dialog)
        dialog.resize(900, 640)
        dialog.show()
        qtbot.waitExposed(dialog)
        return dialog

    return make


def show_page(
    dialog: User_Guide_Dialog, model: GuideModel, content_ref: str
) -> QTextBrowser:
    """Show a topic by its page and return the content view, laid out."""
    dialog.show_topic(_topic_by_ref(model, content_ref).id)
    QApplication.processEvents()
    view = dialog._content_view
    view.verticalScrollBar().setValue(0)
    return view


def click(view: QTextBrowser, href: str) -> None:
    """Click a link as the browser does: ``anchorClicked`` with the anchor's URL."""
    view.anchorClicked.emit(QUrl(href))
    QApplication.processEvents()


def heading_links(
    view: QTextBrowser, topic_ids: frozenset
) -> Tuple[List[str], List[str]]:
    """Return the ``(same-page, cross-page)`` heading links of the page shown.

    A heading link has a fragment that is not a topic id: ``#fragment`` is the
    same page's, ``<page>.md#fragment`` another page's.
    """
    same: List[str] = []
    cross: List[str] = []
    for href in anchors_of(view):
        url = QUrl(href)
        fragment = url.fragment()
        if not fragment or fragment in topic_ids or url.scheme():
            continue
        (cross if url.path().endswith(".md") else same).append(href)
    return same, cross


def page_text(open_guide, code: str, model: GuideModel, content_ref: str) -> str:
    """Return the text a reference window shows for a page in ``code`` (its own
    window)."""
    reference = open_guide(code)
    return show_page(reference, model, content_ref).toPlainText()


# --------------------------------------------------------------------------- #
# SC-L10N-UI-019-1: a link to a heading of the same page                      #
# --------------------------------------------------------------------------- #


def same_page_findings(
    code: str, page: str, href: str, view: QTextBrowser, before_text: str
) -> List[str]:
    """Click one same-page heading link and return what is wrong, naming page and
    fragment."""
    fragment = QUrl(href).fragment()
    ordinal = english_ordinal(page, fragment)
    click(view, href)
    found = placement_findings(view, ordinal)
    if view.toPlainText() != before_text:
        found.append("the page shown is not the same page")
    return [
        f"[{code}] page {page!r}, fragment {fragment!r}: {finding}" for finding in found
    ]


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_019_1_a_link_to_a_heading_of_the_same_page_moves_the_view_there(
    code, open_guide, model, capsys
):
    """SC-L10N-UI-019-1: each same-page heading link of the tree puts its heading at the
    top.

    Every such link of the language's tree is clicked; the heading it names (on a
    translated page, the block at the same position) is the first line at the top of
    the view, or the view is at its maximum with that block shown; the page is the
    same page. The number clicked is printed and is non-zero.
    """
    dialog = open_guide(code)
    topic_ids = frozenset(topic.id for topic in model.topics())
    findings: List[str] = []
    clicked = 0
    for topic in model.topics():
        view = show_page(dialog, model, topic.content_ref)
        same, _cross = heading_links(view, topic_ids)
        for href in same:
            view = show_page(dialog, model, topic.content_ref)
            clicked += 1
            findings += same_page_findings(
                code, topic.content_ref, href, view, view.toPlainText()
            )
    line = f"[heading links] {code}: same-page links clicked {clicked}"
    print(line)
    with capsys.disabled():
        print(line)
    assert clicked > 0
    assert not findings, "\n".join(findings)


def _ignoring_handler(self: User_Guide_Dialog, url: QUrl) -> None:
    """A link handler that ignores the fragment, as the window did before this
    requirement."""
    return None


def test_sc_l10n_ui_019_1_a_handler_that_ignores_the_fragment_fails(
    open_guide, model, monkeypatch
):
    """SC-L10N-UI-019-1: with the fragment ignored, the check fails and names page and
    fragment."""
    monkeypatch.setattr(User_Guide_Dialog, "_on_anchor_clicked", _ignoring_handler)
    dialog = open_guide("en")
    topic_ids = frozenset(topic.id for topic in model.topics())
    view = show_page(dialog, model, "animation-timeline")
    same, _cross = heading_links(view, topic_ids)
    assert same, "the page holds no same-page heading link to plant against"
    findings = same_page_findings(
        "en", "animation-timeline", same[0], view, view.toPlainText()
    )
    assert findings, "a handler that ignores the fragment passed"
    fragment = QUrl(same[0]).fragment()
    assert "animation-timeline" in findings[0] and fragment in findings[0]


# --------------------------------------------------------------------------- #
# SC-L10N-UI-019-2: a link to a heading of another page                        #
# --------------------------------------------------------------------------- #


def cross_page_findings(
    code: str,
    page: str,
    href: str,
    view: QTextBrowser,
    target_text: str,
    model: GuideModel,
) -> List[str]:
    """Click one cross-page heading link and return what is wrong, naming the link."""
    url = QUrl(href)
    stem = url.path().rsplit("/", 1)[-1][: -len(".md")]
    ordinal = english_ordinal(stem, url.fragment())
    click(view, href)
    found = placement_findings(view, ordinal)
    if view.toPlainText() != target_text:
        found.append("the page shown is not the target page")
    return [f"[{code}] link {href!r} on page {page!r}: {finding}" for finding in found]


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_019_2_a_link_to_a_heading_of_another_page_opens_that_page_there(
    code, open_guide, model, capsys
):
    """SC-L10N-UI-019-2: each cross-page heading link opens its page, in the language,
    at the heading.

    The page shown is the target in the language REQ-L10N-UI-007 resolves for it (the
    text a reference window shows for it) and its heading is placed as in
    SC-L10N-UI-019-1. The number clicked is printed and is non-zero.
    """
    dialog = open_guide(code)
    topic_ids = frozenset(topic.id for topic in model.topics())
    findings: List[str] = []
    clicked = 0
    for topic in model.topics():
        view = show_page(dialog, model, topic.content_ref)
        _same, cross = heading_links(view, topic_ids)
        for href in cross:
            stem = QUrl(href).path().rsplit("/", 1)[-1][: -len(".md")]
            target_text = page_text(open_guide, code, model, stem)
            view = show_page(dialog, model, topic.content_ref)
            clicked += 1
            findings += cross_page_findings(
                code, topic.content_ref, href, view, target_text, model
            )
    line = f"[heading links] {code}: cross-page links clicked {clicked}"
    print(line)
    with capsys.disabled():
        print(line)
    assert clicked > 0
    assert not findings, "\n".join(findings)


def _dropping_handler(self: User_Guide_Dialog, url: QUrl) -> None:
    """A link handler that opens the page and drops the fragment, as the window did
    before."""
    if url.path().endswith(".md"):
        stem = url.path().rsplit("/", 1)[-1][: -len(".md")]
        assert self._model is not None
        for topic in self._model.topics():
            if topic.content_ref == stem:
                self.show_topic(topic.id)
                return


def test_sc_l10n_ui_019_2_a_handler_that_drops_the_fragment_fails_naming_the_link(
    open_guide, model, monkeypatch
):
    """SC-L10N-UI-019-2: with the fragment dropped, the check fails and names the
    link."""
    monkeypatch.setattr(User_Guide_Dialog, "_on_anchor_clicked", _dropping_handler)
    dialog = open_guide("en")
    topic_ids = frozenset(topic.id for topic in model.topics())
    view = show_page(dialog, model, "animation-timeline")
    _same, cross = heading_links(view, topic_ids)
    assert cross, "the page holds no cross-page heading link to plant against"
    target = page_text(open_guide, "en", model, OTHER_PAGE_CONTENT_REF)
    view = show_page(dialog, model, "animation-timeline")
    findings = cross_page_findings(
        "en", "animation-timeline", cross[0], view, target, model
    )
    assert findings, "a handler that drops the fragment passed"
    assert cross[0] in findings[0]


def test_sc_l10n_ui_019_2_a_page_absent_from_a_translated_tree_shows_english(
    open_guide, model, monkeypatch, tmp_path
):
    """SC-L10N-UI-019-2: the target absent from the French tree opens as the English
    page, at its heading.

    The guide content is copied under ``tmp_path`` (the real content is not
    touched), the French copy of the target page is removed there, and the
    guide's root is pointed at the copy for this test only.
    """
    scratch = tmp_path / "guide-bundle"
    source = guide_content.bundle_root()
    shutil.copytree(str(source), str(scratch))
    absent = scratch / "content" / "fr" / f"{OTHER_PAGE_CONTENT_REF}.md"
    assert (
        absent.is_file()
    ), f"the French copy of {OTHER_PAGE_CONTENT_REF} is not there to remove"
    absent.unlink()
    monkeypatch.setattr(guide_content, "bundle_root", lambda: scratch)

    english_text = page_text(open_guide, "en", model, OTHER_PAGE_CONTENT_REF)
    dialog = open_guide("fr")
    topic_ids = frozenset(topic.id for topic in model.topics())
    view = show_page(dialog, model, LONG_PAGE_CONTENT_REF)
    _same, cross = heading_links(view, topic_ids)
    links = [href for href in cross if OTHER_PAGE_CONTENT_REF in href]
    assert links, "the French page holds no link to the removed page"
    findings = cross_page_findings(
        "fr", LONG_PAGE_CONTENT_REF, links[0], view, english_text, model
    )
    assert not findings, "\n".join(findings)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-019-4: a fragment that names no heading is harmless              #
# --------------------------------------------------------------------------- #


def _no_dialog_appeared(before: List[object], boxes: list) -> List[str]:
    """Return a finding if a message box was recorded or a top-level window appeared."""
    found: List[str] = []
    if boxes:
        found.append(f"a message box was shown: {boxes!r}")
    appeared = [
        w for w in QApplication.topLevelWidgets() if w.isVisible() and w not in before
    ]
    if appeared:
        found.append(f"a window appeared: {[type(w).__name__ for w in appeared]}")
    if QApplication.activeModalWidget() is not None:
        found.append("a modal dialog is open")
    return found


def test_sc_l10n_ui_019_4_a_same_page_fragment_naming_no_heading_does_not_move(
    open_guide, model, mute_message_boxes
):
    """SC-L10N-UI-019-4: ``#no-such-heading`` on the same page: same page, the view has
    not moved."""
    dialog = open_guide("en")
    view = show_page(dialog, model, LONG_PAGE_CONTENT_REF)
    value = scroll_part_way(view)
    text = view.toPlainText()
    before = list(QApplication.topLevelWidgets())
    mute_message_boxes.clear()
    click(view, "#no-such-heading")
    assert view.verticalScrollBar().value() == value
    assert view.toPlainText() == text and text.strip()
    assert _no_dialog_appeared(before, mute_message_boxes) == []


def test_sc_l10n_ui_019_4_a_cross_page_fragment_naming_no_heading_opens_the_top(
    open_guide, model, mute_message_boxes
):
    """SC-L10N-UI-019-4: ``<page>.md#no-such-heading``: that page is shown at its
    top."""
    reference = page_text(open_guide, "en", model, OTHER_PAGE_CONTENT_REF)
    dialog = open_guide("en")
    view = show_page(dialog, model, LONG_PAGE_CONTENT_REF)
    scroll_part_way(view)
    before = list(QApplication.topLevelWidgets())
    mute_message_boxes.clear()
    click(view, f"{OTHER_PAGE_CONTENT_REF}.md#no-such-heading")
    assert view.toPlainText() == reference and reference.strip()
    assert view.verticalScrollBar().value() == 0
    assert _no_dialog_appeared(before, mute_message_boxes) == []


def test_sc_l10n_ui_019_4_a_fragment_that_is_a_topic_id_still_opens_that_topic(
    open_guide, model, mute_message_boxes
):
    """SC-L10N-UI-019-4: a link whose fragment is a topic id shows that topic, as
    before."""
    target = _topic_by_ref(model, OTHER_PAGE_CONTENT_REF)
    reference = page_text(open_guide, "en", model, OTHER_PAGE_CONTENT_REF)
    dialog = open_guide("en")
    view = show_page(dialog, model, LONG_PAGE_CONTENT_REF)
    before = list(QApplication.topLevelWidgets())
    mute_message_boxes.clear()
    click(view, f"#{target.id}")
    assert view.toPlainText() == reference and reference.strip()
    assert _no_dialog_appeared(before, mute_message_boxes) == []


def test_sc_l10n_ui_019_4_a_link_with_another_scheme_does_not_navigate(
    open_guide, model, mute_message_boxes
):
    """SC-L10N-UI-019-4: ``https://example.org/#managing-frames`` leaves the window as
    it is."""
    dialog = open_guide("en")
    view = show_page(dialog, model, LONG_PAGE_CONTENT_REF)
    value = scroll_part_way(view)
    text = view.toPlainText()
    before = list(QApplication.topLevelWidgets())
    mute_message_boxes.clear()
    click(view, "https://example.org/#managing-frames")
    assert view.verticalScrollBar().value() == value
    assert view.toPlainText() == text and text.strip()
    assert _no_dialog_appeared(before, mute_message_boxes) == []


# --------------------------------------------------------------------------- #
# Reporting: the diagnostic line, whatever the output's encoding              #
# --------------------------------------------------------------------------- #


def write_line(line: str, stream: Optional[TextIO] = None) -> None:
    """Print ``line`` to ``stream`` (the current ``sys.stdout`` if none is given).

    A character the stream's encoding cannot hold is written as its backslash escape
    instead of raising, so the diagnostic line never decides a case. The text is
    encoded with the stream's own encoding and ``backslashreplace``, then printed;
    under a UTF-8 stream that is exactly what ``print`` writes.
    """
    target = sys.stdout if stream is None else stream
    encoding = getattr(target, "encoding", None) or "utf-8"
    print(line.encode(encoding, "backslashreplace").decode(encoding), file=target)


# --------------------------------------------------------------------------- #
# The ordinal guard                                                           #
# --------------------------------------------------------------------------- #


def test_the_reader_of_english_headings_agrees_with_the_rendered_pages(
    open_guide, model
):
    """Control of the oracle above: for every English page it counts what the window
    renders."""
    dialog = open_guide("en")
    mismatched: List[str] = []
    for topic in model.topics():
        view = show_page(dialog, model, topic.content_ref)
        counted = len(
            english_slugs(read_content(content_ref_path(topic.content_ref, "en")))
        )
        rendered = len(heading_blocks(view))
        if counted != rendered:
            mismatched.append(
                f"{topic.content_ref}: read {counted}, rendered {rendered}"
            )
    assert mismatched == []


def test_the_ordinal_guard_rendered_headings_equal_the_functions_count(
    open_guide, model, capsys
):
    """SC-L10N-UI-019-1 (ordinal guard): per page, rendered heading blocks equal
    ``len(heading_slugs(page))``.

    The count of each page is printed, and a mismatch fails naming the page, so
    a heading form Qt renders and the function misses (or the reverse) is found
    before it scrolls to the wrong place.
    """
    try:
        from pixelart_creator.logic.guide_anchors import heading_slugs
    except ImportError as failure:
        pytest.fail(
            f"logic/guide_anchors.py is not there to count the headings: {failure}"
        )
    dialog = open_guide("en")
    mismatched: List[str] = []
    lines: List[str] = []
    for topic in model.topics():
        view = show_page(dialog, model, topic.content_ref)
        counted = len(
            heading_slugs(read_content(content_ref_path(topic.content_ref, "en")))
        )
        rendered = len(heading_blocks(view))
        lines.append(f"{topic.content_ref}={rendered}")
        if counted != rendered:
            mismatched.append(
                f"{topic.content_ref}: counted {counted}, rendered {rendered}"
            )
    line = f"[heading links] english pages, rendered headings: {', '.join(lines)}"
    print(line)
    with capsys.disabled():
        write_line(line)
    assert lines
    assert mismatched == []


def test_the_placement_check_passes_a_heading_at_the_top_and_fails_one_elsewhere(
    open_guide, model
):
    """Control of the placement check: it is satisfied by the top, and fails off it."""
    dialog = open_guide("en")
    view = show_page(dialog, model, LONG_PAGE_CONTENT_REF)
    blocks = heading_blocks(view)
    assert len(blocks) >= 3
    bar = view.verticalScrollBar()
    bar.setValue(min(int(block_top(view, blocks[1])), bar.maximum()))
    if bar.value() < bar.maximum():
        assert placement_findings(view, 1) == []
    bar.setValue(0)
    assert placement_findings(view, 2), "a heading far from the top passed"
    assert placement_findings(view, len(blocks) + 5)


def test_the_page_models_in_every_language_hold_links_to_click(open_guide, model):
    """Control: every tree's rendered pages hold heading links, so the cases above
    click something."""
    topic_ids = frozenset(topic.id for topic in model.topics())
    for code in LANGUAGES:
        dialog = open_guide(code)
        total = 0
        for topic in model.topics():
            view = show_page(dialog, model, topic.content_ref)
            same, cross = heading_links(view, topic_ids)
            total += len(same) + len(cross)
        assert total > 0, f"{code}: no heading link in the rendered pages"


def test_the_diagnostic_line_is_written_whole_to_a_cp1252_stream():
    """SC-L10N-UI-019-1 (ordinal guard): a line holding Cyrillic, Han, Hangul and kana
    is written whole to a cp1252 stream, without raising.

    The stream is a text wrapper over a byte buffer, never the console. Each
    character cp1252 can hold (here the e acute and the euro sign) arrives
    unchanged; each one it cannot hold arrives as its backslash escape. The
    characters are spelled with escapes, so this file stays ASCII.
    """
    held = "[heading links] ru \u0416 zh \u8bfb ko \ud55c ja \u3042 fr \u00e9 \u20ac"
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, "cp1252", newline="\n", write_through=True)
    write_line(held, stream)
    written = buffer.getvalue()
    assert written == (
        b"[heading links] ru \\u0416 zh \\u8bfb ko \\ud55c ja \\u3042 fr "
        b"\xe9 \x80\n"
    )
    assert written.decode("cp1252").endswith("fr \u00e9 \u20ac\n")
