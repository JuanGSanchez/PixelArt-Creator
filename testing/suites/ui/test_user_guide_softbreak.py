"""Soft line breaks in the real guide window (REQ-L10N-UI-014, the window layer).

The guide window shows a page's soft line breaks as one space, which is wrong
between Chinese or Japanese characters. The rule that decides lives in ``logic/``;
Qt decides what is finally shown, so this module checks the shown text through
``User_Guide_Dialog`` and reads it from the dialog's own view.

What judges a shown text is never the rule under test:

* a row of the scenarios carries its expected text, written here from the
  requirement's tables;
* a construct the rule must not touch (code, hard line breaks, paragraph breaks)
  is compared with what Qt shows for the same source without the rule;
* a shipped page is judged by a probe. A private-use sentinel is put at the start
  of each soft line break's next line, the page is rendered by Qt alone, and the
  two characters Qt shows on either side of the sentinel are read back and judged
  by the five clauses as this module restates them from the requirement (the
  Unicode data comes from ``unicodedata``, not from the product's tables). The
  decision is then compared with what the dialog shows at that same place. Every
  page validates the probe first (same blocks, same shown text without the
  sentinels, every sentinel found); a page that fails that fails, it is never
  skipped.

The trees are the TRACKED trees: discovered with ``git ls-files`` at the
repository root, so a tree that exists only in a working copy is printed and not
judged, and a module that cannot list files fails. ``REQUIRED_SC4_TREES`` and
``REQUIRED_CJ_TREES`` name the trees the module must find; the guard refuses a
tracked tree that is not listed and a listed tree that is not tracked.

Each control is seen to fail: the planted pages run the same check with the rule
bypassed and must name the page, the line and the clause. Both themes, offscreen.
"""

from __future__ import annotations

import difflib
import itertools
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
)

import pytest
from PySide6.QtGui import (
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
    QTextFormat,
)

import pixelart_creator.ui.user_guide as user_guide
from pixelart_creator.data.guide_content import load_manifest
from pixelart_creator.logic.guide_model import GuideModelError, build_model
from pixelart_creator.logic.guide_softbreak import SOFT_BREAK_JOINER, SoftBreakClause
from pixelart_creator.ui.user_guide import User_Guide_Dialog

# --------------------------------------------------------------------------- #
# The trees                                                                   #
# --------------------------------------------------------------------------- #

#: The tracked guide trees whose pages keep the space (Chinese and Japanese aside):
#: judged with the requirement's fourth scenario.
REQUIRED_SC4_TREES: Tuple[str, ...] = ("en", "es", "ko", "de", "fr", "ru")

#: The tracked Chinese and Japanese trees: judged with the fifth scenario. A tree
#: joins when it is committed; one that is only in a working copy is not judged.
REQUIRED_CJ_TREES: Tuple[str, ...] = ("ja",)

CJ_LOCALES = ("ja", "zh_CN")

_ROOT = Path(__file__).resolve().parents[3]
_TREE_REL = "pixelart_creator/userguide_content/content"

#: A private-use character of plane 15 that no shipped page holds.
SENTINEL = "\U000f0000"

#: The topic every shown page is opened as; the reader supplies the text.
_TOPIC = "animation-timeline"


def tracked_pages(root: Path) -> Dict[str, List[str]]:
    """Return ``{locale: [page path, ...]}`` of the Markdown pages git tracks.

    Uses ``git ls-files`` at ``root``; fails (never returns an empty answer) if git
    cannot list the files, so a missing repository is not read as "no trees".
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", f"{_TREE_REL}/"],
            capture_output=True,
            check=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"cannot list the tracked guide pages: {error}") from error
    pages: Dict[str, List[str]] = {}
    for raw in done.stdout.decode("utf-8").split("\0"):
        parts = raw.split("/")
        if len(parts) >= 2 and raw.endswith(".md"):
            locale = parts[len(_TREE_REL.split("/"))]
            pages.setdefault(locale, []).append(raw)
    return pages


def guard_problems(
    tracked: Dict[str, List[str]], sc4: Iterable[str], cj: Iterable[str]
) -> List[str]:
    """Return what is wrong with the listed trees against the tracked ones.

    A tracked tree must be listed and a listed tree must be tracked and non-empty,
    so the floors cannot drift from what ships. The two tuples may not overlap, and
    a Chinese or Japanese tree is listed only in the second.
    """
    problems: List[str] = []
    sc4, cj = tuple(sc4), tuple(cj)
    for locale in sc4:
        if locale in CJ_LOCALES:
            problems.append(f"{locale}: a Chinese or Japanese tree is in the SC4 list")
    for locale in cj:
        if locale not in CJ_LOCALES:
            problems.append(f"{locale}: not a Chinese or Japanese tree, in the CJ list")
    listed = set(sc4) | set(cj)
    for locale in sorted(listed):
        if not tracked.get(locale):
            problems.append(f"{locale}: listed but no tracked page")
    for locale in sorted(tracked):
        if tracked[locale] and locale not in listed:
            problems.append(f"{locale}: tracked but not listed")
    return problems


# --------------------------------------------------------------------------- #
# Showing a page                                                              #
# --------------------------------------------------------------------------- #


def show_page(qtbot, language: str, source: str) -> User_Guide_Dialog:
    """Return a guide dialog showing ``source`` as a page of ``language``.

    The reader hands ``source`` back for any reference and the language of the page
    is the folder of the reference the dialog resolves; it is asserted to be the
    language asked for.
    """
    refs: List[str] = []

    def reader(ref: str) -> str:
        refs.append(ref)
        return source

    dialog = User_Guide_Dialog(
        None,
        model=build_model(load_manifest()),
        reader=reader,
        content_locales=frozenset({"en", language}),
        locale_provider=lambda: language,
    )
    qtbot.addWidget(dialog)
    dialog.show_topic(_TOPIC)
    assert refs, "the reader was never asked for a page"
    assert f"/{language}/" in refs[-1], f"{refs[-1]!r} is not a {language} page"
    return dialog


def shown_text(dialog: User_Guide_Dialog) -> str:
    """Return the text the dialog's view shows, as Qt reports it."""
    return dialog._content_view.toPlainText()


def paragraphs(dialog: User_Guide_Dialog) -> List[str]:
    """Return the shown text of each non-empty block of the page."""
    document = dialog._content_view.document()
    out: List[str] = []
    block = document.begin()
    while block.isValid():
        if block.text():
            out.append(block.text())
        block = block.next()
    return out


def qt_alone(source: str) -> str:
    """Return what Qt shows for ``source`` with no rule applied."""
    document = QTextDocument()
    document.setMarkdown(source)
    return document.toPlainText()


def bypass_the_rule(monkeypatch) -> None:
    """Make the dialog show pages as if there were no rule (a planted copy)."""
    monkeypatch.setattr(
        user_guide,
        "apply_soft_break_rule",
        lambda text, language: SimpleNamespace(markdown=text),
    )


# --------------------------------------------------------------------------- #
# The five clauses, restated from the requirement                             #
# --------------------------------------------------------------------------- #

#: The marks clause 4 lists, per page language (the requirement's tenth scenario).
MARKS_ZH = tuple("、。，；：！？（）《》“”")
MARKS_JA = tuple("、。「」『』")
CLAUSE4_MARKS = {"zh_CN": MARKS_ZH, "ja": MARKS_JA}


def _is_emoji(char: str) -> bool:
    code = ord(char)
    return 0x1F000 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF


def _width_class(char: str) -> str:
    """Return the East Asian Width, with an Emoji of width W or N counted as A."""
    width = unicodedata.east_asian_width(char)
    if _is_emoji(char) and width in ("W", "N"):
        return "A"
    return width


def _hangul(char: str) -> bool:
    return "HANGUL" in unicodedata.name(char, "")


def _wide(char: str) -> bool:
    return _width_class(char) in ("F", "W", "H") and not _hangul(char)


def _ambiguous_symbol(char: str) -> bool:
    return _width_class(char) == "A" and unicodedata.category(char)[0] in ("P", "S")


def _latin_or_digit(char: str) -> bool:
    name = unicodedata.name(char, "")
    return ("LATIN" in name and "LETTER" in name) or unicodedata.category(char) == "Nd"


def clause_of(left: str, right: str, language: str) -> Optional[int]:
    """Return the first clause (1 to 4) removing the break, or ``None`` (clause 5)."""
    if "​" in (left, right):
        return 1
    if _wide(left) and _wide(right):
        return 2
    if language in CJ_LOCALES:
        if (_ambiguous_symbol(left) and _wide(right)) or (
            _ambiguous_symbol(right) and _wide(left)
        ):
            return 3
        marks = CLAUSE4_MARKS[language]
        if (left in marks and _latin_or_digit(right)) or (
            right in marks and _latin_or_digit(left)
        ):
            return 4
    return None


# --------------------------------------------------------------------------- #
# The probe                                                                   #
# --------------------------------------------------------------------------- #

#: First characters of a line that the sentinel must not precede: it would change
#: whether an emphasis run, a link, raw HTML, a reference or an escape starts there.
_DELIMITER_STARTS = frozenset("*_~`[<!&\\")

_BLOCK_START = re.compile(r"^(#|>|\||<|```|~~~)")
_LIST_MARKER = re.compile(r"^([-+*]|\d{1,9}[.)])(\s|$)")
_THEMATIC = re.compile(r"^([-*_])(\s*\1){2,}\s*$")
_SETEXT = re.compile(r"^(=+|-+)\s*$")


def _prose(line: str) -> bool:
    """Say whether ``line`` is plain paragraph text (no block start, no table cell)."""
    text = line.strip()
    if not text or "|" in text:
        return False
    if _BLOCK_START.match(text) or _THEMATIC.match(text) or _SETEXT.match(text):
        return False
    return not _LIST_MARKER.match(text)


def _prose_start(line: str) -> bool:
    """Say whether ``line`` may be the first line of a paragraph the probe reads."""
    text = line.strip()
    if not text or "|" in text:
        return False
    if _BLOCK_START.match(text) and not text.startswith(">"):
        return False
    return not (_THEMATIC.match(text) or _SETEXT.match(text))


@dataclass
class Break:
    """One soft line break the probe could read: its place and the characters at it."""

    line: int  # 1-based line of the text AFTER the break
    index: int  # index in Qt's own text of the character after the break space
    left: str
    right: str


@dataclass
class Probed:
    """The result of probing one page."""

    qt: str
    breaks: List[Break]
    skipped_in_code: int


def _eligible_breaks(lines: Sequence[str]) -> List[int]:
    """Return the indexes ``i`` such that a soft break lies between line i-1 and i."""
    found: List[int] = []
    fenced = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced or index == 0:
            continue
        previous = lines[index - 1]
        if previous != previous.rstrip("\n") or not _prose_start(previous):
            continue
        if (
            previous.endswith("  ")
            or previous.endswith("\\")
            or previous.endswith("\t")
        ):
            continue
        if _prose(line) and not previous.strip().startswith("#"):
            found.append(index)
    return found


def _in_code_span(lines: Sequence[str], index: int) -> bool:
    """Say whether the break before ``lines[index]`` lies inside an inline code span.

    Counted over the paragraph so far: an odd number of backticks is an open span.
    """
    ticks = 0
    for line in reversed(lines[:index]):
        if not line.strip():
            break
        ticks += line.count("`")
    return ticks % 2 == 1


def probe(source: str, page: str = "") -> Probed:
    """Probe ``source``: read the two characters Qt shows at each soft line break.

    Raises ``AssertionError`` naming ``page`` if the probe does not validate (the
    page holds the sentinel, the shown text changes when the sentinels are
    removed, or a sentinel is lost): such a page is never skipped.
    """
    assert SENTINEL not in source, f"{page}: the page holds the sentinel"
    lines = source.split("\n")
    marked = list(lines)
    wanted: List[int] = []
    skipped = 0
    for index in _eligible_breaks(lines):
        if _in_code_span(lines, index):
            skipped += 1
            continue
        indent = len(lines[index]) - len(lines[index].lstrip())
        if lines[index][indent : indent + 1] in _DELIMITER_STARTS:
            # A sentinel before a delimiter run changes whether the run can open.
            skipped += 1
            continue
        marked[index] = lines[index][:indent] + SENTINEL + lines[index][indent:]
        wanted.append(index)
    plain = QTextDocument()
    plain.setMarkdown(source)
    withs = QTextDocument()
    withs.setMarkdown("\n".join(marked))
    qt = plain.toPlainText()
    seeded = withs.toPlainText()
    assert plain.blockCount() == withs.blockCount(), (
        f"{page}: the sentinels change the block count "
        f"{plain.blockCount()} -> {withs.blockCount()}"
    )
    assert seeded.count(SENTINEL) == len(wanted), (
        f"{page}: {len(wanted)} sentinels inserted, "
        f"{seeded.count(SENTINEL)} found in the shown text"
    )
    assert seeded.replace(SENTINEL, "") == qt, f"{page}: the sentinels change the text"
    breaks: List[Break] = []
    removed = 0
    position = seeded.find(SENTINEL)
    for number, index in enumerate(wanted):
        assert position >= 0
        at = position - removed
        removed += 1
        assert at >= 2 and qt[at - 1] == " ", (
            f"{page}: line {index + 1}: the break is not shown as a space "
            f"({qt[max(at - 3, 0):at + 3]!r})"
        )
        breaks.append(Break(index + 1, at, qt[at - 2], qt[at]))
        position = seeded.find(SENTINEL, position + 1)
    return Probed(qt, breaks, skipped)


def _deleted_spaces_whole_text(
    before: str, after: str, page: str, offset: int = 0
) -> List[int]:
    """Return the indexes of ``before`` whose space ``after`` does not show.

    One ``difflib`` comparison of the two whole strings, so its cost grows faster
    than linearly with their length: on a page of a few thousand characters it is
    cheap, over all the pages of one test it is not (see ``_deleted_spaces``).
    ``offset`` is added to every index returned. Fails if ``after`` differs from
    ``before`` in any other way.
    """
    deleted: List[int] = []
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        assert tag == "delete" and before[i1:i2].strip() == "" and j1 == j2, (
            f"{page}: the dialog differs from Qt's text other than by a removed space: "
            f"{tag} {before[max(i1 - 6, 0) : i2 + 6]!r} -> "
            f"{after[max(j1 - 6, 0) : j2 + 6]!r}"
        )
        deleted.extend(range(offset + i1, offset + i2))
    return deleted


def _has_whitespace_beside(text: str, index: int) -> bool:
    """Return whether a whitespace character stands next to ``text[index]``."""
    return (index > 0 and text[index - 1].strip() == "") or (
        index + 1 < len(text) and text[index + 1].strip() == ""
    )


def _deleted_spaces(before: str, after: str, page: str) -> List[int]:
    """Return the indexes of ``before`` whose space ``after`` does not show.

    Fails if ``after`` differs from ``before`` in any other way. It answers exactly
    as ``_deleted_spaces_whole_text`` does, and is cheap only where that is safe.

    The fast path compares the two texts one block at a time: with equal numbers of
    line feeds every block of ``after`` must be its block of ``before`` less some
    blanks, and a block that is equal is not compared at all. Its answer is returned
    only if it is certain to be the whole-text answer, which it is when no deleted
    blank has another whitespace character beside it: then the deleted blanks are
    the only ones the texts allow, and which blank of a run is "the" deleted one is
    no choice, because there is no run. In every other case the whole texts are
    compared by ``_deleted_spaces_whole_text`` and its answer, or its refusal, is
    the answer: a run of blanks (difflib's choice among equal blanks, which decides
    the SC-4 verdict beside a zero width space), a blank on an otherwise empty line
    (the whole-text comparison refuses some such texts), a refusal of the fast path
    (so no text the whole-text comparison accepts is refused here) and unequal
    numbers of line feeds. On every tracked guide page the fast path answers, which
    takes the two heavy tests from about 70 s each to a few seconds.
    """
    if before == after:
        return []
    old, new = before.split("\n"), after.split("\n")
    if len(old) == len(new):
        fast: List[int] = []
        offset = 0
        try:
            for one, other in zip(old, new):
                if one != other:
                    fast.extend(_deleted_spaces_whole_text(one, other, page, offset))
                offset += len(one) + 1
        except AssertionError:
            fast = []
        else:
            if not any(_has_whitespace_beside(before, index) for index in fast):
                return fast
    return _deleted_spaces_whole_text(before, after, page)


@dataclass
class Verdict:
    """What the check found on one page."""

    page: str
    probed: int
    removed_by_clause: Counter
    kept: int
    findings: List[str]
    unprobed_removed: int
    skipped_in_code: int


def judge_page(page: str, language: str, source: str, shown: str) -> Verdict:
    """Compare ``shown`` with what the clauses decide at every soft break of ``source``.

    A removable break that is shown as a character, and a kept break that is not
    shown, are findings that name the page, the line and the clause. Every removed
    space that no probe covers must still be removable by the clauses.
    """
    probed = probe(source, page)
    deleted = set(_deleted_spaces(probed.qt, shown, page))
    findings: List[str] = []
    by_clause: Counter = Counter()
    kept = 0
    covered = set()
    for found in probed.breaks:
        space = found.index - 1
        covered.add(space)
        clause = clause_of(found.left, found.right, language)
        if clause is not None:
            by_clause[clause] += 1
        else:
            kept += 1
        if clause is not None and space not in deleted:
            findings.append(
                f"{page}:{found.line}: clause {clause} removes the break between "
                f"{found.left!r} and {found.right!r}, and it is shown as a character"
            )
        if clause is None and space in deleted:
            findings.append(
                f"{page}:{found.line}: no clause removes the break between "
                f"{found.left!r} and {found.right!r}, and it is not shown"
            )
    unprobed = 0
    for space in sorted(deleted - covered):
        unprobed += 1
        left, right = probed.qt[space - 1], probed.qt[space + 1]
        if clause_of(left, right, language) is None:
            findings.append(
                f"{page}: a space between {left!r} and {right!r} is not shown, "
                f"and no clause removes it"
            )
    return Verdict(
        page,
        len(probed.breaks),
        by_clause,
        kept,
        findings,
        unprobed,
        probed.skipped_in_code,
    )


def _read(path: str) -> str:
    return (_ROOT / path).read_bytes().decode("utf-8").replace("\r\n", "\n")


# --------------------------------------------------------------------------- #
# The scenarios' rows                                                         #
# --------------------------------------------------------------------------- #

#: SC-L10N-UI-014-1: a break between two Chinese or Japanese characters shows nothing.
ROWS_JOINED = [
    ("ja", "日本\n語", "日本語"),
    ("ja", "ファイル\nを開く", "ファイルを開く"),
    ("ja", "表示、\n編集", "表示、編集"),
    ("ja", "選択範囲を\n**移動**します", "選択範囲を移動します"),
    ("ja", "[レイヤー](layers.md)\nを選びます", "レイヤーを選びます"),
    ("ja", "日本 \n語", "日本語"),
    ("zh_CN", "图层\n面板", "图层面板"),
    ("zh_CN", "选择，\n然后", "选择，然后"),
    ("ja", "> 1 回のドロップで\n> 種類を混ぜる", "1 回のドロップで種類を混ぜる"),
    ("ja", "1. 選択範囲を\n   持ち上げます", "選択範囲を持ち上げます"),
]

#: SC-L10N-UI-014-2: every other soft line break is shown as one space.
ROWS_KEPT = [
    ("en", "Hello\nworld", "Hello world"),
    ("ru", "Слой\nвыбран", "Слой выбран"),
    ("ko", "레이어를\n선택합니다", "레이어를 선택합니다"),
    ("ja", "ストレートアルファの\nsource-over", "ストレートアルファの source-over"),
    ("ja", "**Delete**\nは同じ", "Delete は同じ"),
    ("ja", "バージョンを\n1 行", "バージョンを 1 行"),
    ("en", "Click “Save”\nand close", "Click “Save” and close"),
    ("en", "日本 —\n語", "日本 — 語"),
    ("ja", "選択 —\nCtrl キー", "選択 — Ctrl キー"),
    ("ja", "韓国語 “\n한국어”", "韓国語 “ 한국어”"),
    ("ko", "끝。\nCtrl 키", "끝。 Ctrl 키"),
    ("en", "表示、\nEdit", "表示、 Edit"),
    ("ja", "表示､\nEdit", "表示､ Edit"),
]

#: SC-L10N-UI-014-6: a break beside U+200B is not shown, and the U+200B stays.
ROWS_ZERO_WIDTH = [
    ("en", "word​\nbreak", "word​break"),
    ("en", "word\n​break", "word​break"),
    ("en", "word​ \nbreak", "word​break"),
    ("ko", "레이어를​\n선택합니다", "레이어를​선택합니다"),
    ("ja", "日本​\n語", "日本​語"),
]

#: SC-L10N-UI-014-7: ambiguous-width punctuation beside a wide character.
ROWS_AMBIGUOUS = [
    ("zh_CN", "选择\n“文件”菜单", "选择“文件”菜单"),
    ("zh_CN", "打开“文件”\n菜单", "打开“文件”菜单"),
    ("zh_CN", "正在保存…\n完成后", "正在保存…完成后"),
    ("ja", "**ありません** —\n現在のドキュメント", "ありません —現在のドキュメント"),
    ("ja", "「保存」→\n「閉じる」", "「保存」→「閉じる」"),
    ("ja", "下記※\n参照", "下記※参照"),
]

#: SC-L10N-UI-014-8: a clause-4 mark beside a Latin letter or a digit.
ROWS_MARK_AND_LATIN = [
    ("ja", "**パースグリッド**、\nPureRef 風の", "パースグリッド、PureRef 風の"),
    ("ja", "載せています。\n**Ctrl+Shift+E** は", "載せています。Ctrl+Shift+E は"),
    ("ja", "設定でき、\n4 つのモード", "設定でき、4 つのモード"),
    ("ja", "対象は PNG\n、GIF です", "対象は PNG、GIF です"),
    ("zh_CN", "支持 PNG、\nGIF 和", "支持 PNG、GIF 和"),
    ("zh_CN", "完成。\nPixelArt Creator 会", "完成。PixelArt Creator 会"),
    ("zh_CN", "版本 2\n。", "版本 2。"),
    ("zh_CN", "使用“\nCtrl”键", "使用“Ctrl”键"),
    ("zh_CN", "选择，\nCtrl 键", "选择，Ctrl 键"),
    ("ja", "キーは「\nCtrl+S」です", "キーは「Ctrl+S」です"),
]

#: SC-L10N-UI-014-9: an emoji counts as ambiguous width.
ROWS_EMOJI = [
    ("ja", "完了😀\n次へ", "完了😀次へ"),
    ("ja", "著作権 ©\n山田", "著作権 ©山田"),
    ("en", "完了😀\n次へ", "完了😀 次へ"),
    ("ja", "😀\n😀", "😀 😀"),
]

ALL_ROWS = (
    [("1", *row) for row in ROWS_JOINED]
    + [("2", *row) for row in ROWS_KEPT]
    + [("6", *row) for row in ROWS_ZERO_WIDTH]
    + [("7", *row) for row in ROWS_AMBIGUOUS]
    + [("8", *row) for row in ROWS_MARK_AND_LATIN]
    + [("9", *row) for row in ROWS_EMOJI]
)


@pytest.mark.parametrize(
    "scenario, language, source, expected",
    ALL_ROWS,
    ids=[f"{row[0]}-{row[1]}-{index}" for index, row in enumerate(ALL_ROWS)],
)
def test_a_paragraph_shows_what_the_scenario_says(
    qtbot, scenario, language, source, expected
):
    """REQ-L10N-UI-014 (SC-L10N-UI-014-1, -2, -6, -7, -8, -9): the shown paragraph.

    One page of one paragraph in the language's folder, shown through the guide
    window; the paragraph's shown text is the scenario's, character for character.
    """
    dialog = show_page(qtbot, language, source)
    assert paragraphs(dialog) == [expected], (
        f"scenario -{scenario}, {language}: {source!r} is shown as "
        f"{paragraphs(dialog)!r}, not {expected!r}"
    )


def test_the_rows_carry_their_controls_and_are_not_empty():
    """Control: a Korean row and an English row keep the space; no table is empty."""
    languages = {row[0] for row in ROWS_KEPT}
    assert {"ko", "en"} <= languages
    for rows in (
        ROWS_JOINED,
        ROWS_KEPT,
        ROWS_ZERO_WIDTH,
        ROWS_AMBIGUOUS,
        ROWS_MARK_AND_LATIN,
        ROWS_EMOJI,
    ):
        assert rows
    for _language, source, expected in ROWS_JOINED:
        assert "\n" in source and "\n" not in expected


@pytest.mark.parametrize(
    "scenario, language, source, expected",
    [
        row
        for row in ALL_ROWS
        if row[0] in ("1", "6", "7", "8") or row[3] == "完了😀次へ"
    ],
    ids=lambda value: None,
)
def test_with_the_rule_bypassed_the_joined_rows_fail(
    qtbot, monkeypatch, scenario, language, source, expected
):
    """Control: with the rule bypassed, a row that must be joined is shown spaced.

    The same page through the same dialog, with ``apply_soft_break_rule`` replaced
    by a function that returns the page unchanged, must not show the scenario's
    text, so the row cannot pass because nothing was removed.
    """
    bypass_the_rule(monkeypatch)
    dialog = show_page(qtbot, language, source)
    assert paragraphs(dialog) != [expected], f"{source!r} is joined without the rule"


# --------------------------------------------------------------------------- #
# SC-L10N-UI-014-3: what the rule must not touch                              #
# --------------------------------------------------------------------------- #

UNTOUCHED = [
    ("a code span", "`日本\n語`"),
    ("a fenced code block", "```\n日本\n語\n```"),
    ("an indented code block", "    日本\n    語"),
    ("two trailing spaces", "日本  \n語"),
    ("a backslash hard break", "日本\\\n語"),
    ("a paragraph break", "日本\n\n語"),
    ("a typed space", "日本 語"),
]


@pytest.mark.parametrize("label, source", UNTOUCHED, ids=[row[0] for row in UNTOUCHED])
def test_code_hard_breaks_and_paragraph_breaks_are_untouched(qtbot, label, source):
    """REQ-L10N-UI-014 (SC-L10N-UI-014-3): shown exactly as without the rule."""
    dialog = show_page(qtbot, "ja", source)
    assert shown_text(dialog) == qt_alone(source), label


# --------------------------------------------------------------------------- #
# SC-L10N-UI-014-10: every mark of clause 4, in its own language's pages      #
# --------------------------------------------------------------------------- #

MARK_CASES = [
    ("zh_CN", MARKS_ZH, ""),
    ("ja", MARKS_JA, ""),
    ("ja", tuple(m for m in MARKS_ZH if m not in MARKS_JA), " "),
    ("zh_CN", tuple(m for m in "、。「」『』" if m not in MARKS_ZH), " "),
]


@pytest.mark.parametrize(
    "language, marks, joiner",
    MARK_CASES,
    ids=["zh_CN-own", "ja-own", "ja-others", "zh_CN-others"],
)
def test_each_clause_4_mark_is_removed_only_in_its_own_language(
    qtbot, capsys, language, marks, joiner
):
    """REQ-L10N-UI-014 (SC-L10N-UI-014-10): four paragraphs for each mark, per language.

    For each mark M the page holds ``M\\nA``, ``A\\nM``, ``M\\n1`` and ``1\\nM``;
    each is shown with nothing between the two characters in a page whose language
    lists the mark, and with one space otherwise. The number of marks examined is
    printed and equals the marks of the list.
    """
    assert marks, "no mark to examine"
    pairs: List[Tuple[str, str, str]] = []
    for mark in marks:
        for other in ("A", "1"):
            pairs.append((f"{mark}\n{other}", mark, other))
            pairs.append((f"{other}\n{mark}", other, mark))
    source = "\n\n".join(item[0] for item in pairs)
    dialog = show_page(qtbot, language, source)
    expected = [f"{left}{joiner}{right}" for _src, left, right in pairs]
    assert paragraphs(dialog) == expected
    examined = len(pairs) // 4
    print(f"[soft breaks] {language}: marks examined {examined} of {len(marks)}")
    assert examined == len(marks)


# --------------------------------------------------------------------------- #
# The error path                                                              #
# --------------------------------------------------------------------------- #


def test_a_malformed_reference_shows_the_error_pane_and_raises_nothing(
    qtbot, monkeypatch
):
    """REQ-L10N-UI-014: with the page's language unreadable the pane says so, no crash.

    ``content_ref_locale`` is made to raise ``GuideModelError``; the dialog shows the
    "Could not load this topic" frame, never the page, and no exception escapes.
    """

    def raising(ref: str) -> str:
        raise GuideModelError("planted")

    monkeypatch.setattr(user_guide, "content_ref_locale", raising)
    dialog = show_page_without_language_check(qtbot, "ja", "日本\n語")
    assert "Could not load this topic" in shown_text(dialog)
    assert "日本" not in shown_text(dialog)


def show_page_without_language_check(qtbot, language: str, source: str):
    """Show ``source`` as a page of ``language`` without asking for its folder."""
    dialog = User_Guide_Dialog(
        None,
        model=build_model(load_manifest()),
        reader=lambda ref: source,
        content_locales=frozenset({"en", language}),
        locale_provider=lambda: language,
    )
    qtbot.addWidget(dialog)
    dialog.show_topic(_TOPIC)
    return dialog


# --------------------------------------------------------------------------- #
# The tracked trees: discovery, the guard, and the planted-tree control       #
# --------------------------------------------------------------------------- #


def test_the_listed_trees_are_the_tracked_trees(capsys):
    """The guard: every tracked tree is listed and every listed tree is tracked.

    A tree that exists only in a working copy is printed and not judged.
    """
    tracked = tracked_pages(_ROOT)
    on_disk = sorted(
        entry.name for entry in (_ROOT / _TREE_REL).iterdir() if entry.is_dir()
    )
    untracked = [name for name in on_disk if not tracked.get(name)]
    print(
        f"[soft breaks] tracked trees {sorted(tracked)}; "
        f"present but not tracked, not judged: {untracked}"
    )
    assert guard_problems(tracked, REQUIRED_SC4_TREES, REQUIRED_CJ_TREES) == []


def _git_repo(folder: Path, tracked: Dict[str, int], untracked: Dict[str, int]) -> None:
    """Make a repository at ``folder`` whose guide trees are as given (page counts)."""
    subprocess.run(["git", "-C", str(folder), "init", "-q"], check=True)
    for table, add in ((tracked, True), (untracked, False)):
        for locale, count in table.items():
            for number in range(count):
                path = folder / _TREE_REL / locale / f"page{number}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("text\n", encoding="utf-8")
                if add:
                    subprocess.run(
                        ["git", "-C", str(folder), "add", "-f", str(path)], check=True
                    )


def test_the_planted_trees_are_found_judged_and_refused(tmp_path):
    """Control: tracked trees are found, an untracked one is not, the guard refuses.

    A scratch repository holds tracked ``en`` and ``ja`` trees and an untracked
    ``zh_CN`` tree. Discovery returns the first two only; the guard accepts the
    listing that matches, and refuses a tracked tree that is not listed, a listed
    tree that is not tracked and a locale in the wrong list.
    """
    _git_repo(tmp_path, {"en": 2, "ja": 1}, {"zh_CN": 3})
    tracked = tracked_pages(tmp_path)
    assert {key: len(value) for key, value in tracked.items()} == {"en": 2, "ja": 1}
    assert guard_problems(tracked, ("en",), ("ja",)) == []
    assert any(
        "tracked but not listed" in p for p in guard_problems(tracked, ("en",), ())
    )
    assert any(
        "listed but no tracked page" in p
        for p in guard_problems(tracked, ("en",), ("ja", "zh_CN"))
    )
    assert any("SC4" in p for p in guard_problems(tracked, ("en", "ja"), ()))
    assert any("CJ list" in p for p in guard_problems(tracked, ("en",), ("ja", "en")))


def test_a_module_that_cannot_list_files_fails(tmp_path):
    """Control: no repository is a failure, never an empty list of trees."""
    with pytest.raises(RuntimeError):
        tracked_pages(tmp_path)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-014-4 and -5: the shipped trees                                  #
# --------------------------------------------------------------------------- #


def _shown_through_dialog(qtbot, language: str, source: str) -> str:
    return shown_text(show_page(qtbot, language, source))


def test_sc4_trees_show_the_same_text_except_beside_a_zero_width_space(qtbot, capsys):
    """REQ-L10N-UI-014 (SC-L10N-UI-014-4): outside ja and zh_CN only U+200B counts.

    For every page of every tracked en, es, de, fr, ru and ko page, the shown text
    with the rule differs from Qt's own text only by removed break spaces, each with
    U+200B on one side. Pages per language, breaks examined and removed are
    printed; for ko the breaks between two Hangul characters are counted and are
    non-zero.
    """
    tracked = tracked_pages(_ROOT)
    assert guard_problems(tracked, REQUIRED_SC4_TREES, REQUIRED_CJ_TREES) == []
    findings: List[str] = []
    lines: List[str] = []
    hangul_pairs = 0
    for locale in REQUIRED_SC4_TREES:
        pages = sorted(tracked[locale])
        assert pages, f"{locale}: no page"
        probed_total = removed_total = 0
        for path in pages:
            source = _read(path)
            shown = _shown_through_dialog(qtbot, locale, source)
            baseline = qt_alone(source)
            deleted = _deleted_spaces(baseline, shown, path)
            for space in deleted:
                if "​" not in (baseline[space - 1], baseline[space + 1]):
                    findings.append(
                        f"{path}: a break between {baseline[space - 1]!r} and "
                        f"{baseline[space + 1]!r} is not shown, no U+200B beside it"
                    )
            removed_total += len(deleted)
            found = probe(source, path)
            probed_total += len(found.breaks)
            if locale == "ko":
                hangul_pairs += sum(
                    1
                    for item in found.breaks
                    if _hangul(item.left) and _hangul(item.right)
                )
        lines.append(
            f"{locale}: {len(pages)} pages, {probed_total} breaks examined, "
            f"{removed_total} removed"
        )
    print(
        "[soft breaks] SC-4 " + "; ".join(lines) + f"; ko Hangul pairs {hangul_pairs}"
    )
    assert not findings, "\n".join(findings[:20])
    assert hangul_pairs > 0, "no break between two Hangul characters was examined"


def _check_cj_pages(
    qtbot, pages: Dict[str, Tuple[str, str]]
) -> Tuple[List[str], Counter]:
    """Judge ``{name: (language, source)}`` through the dialog: findings, counts."""
    findings: List[str] = []
    totals: Counter = Counter()
    for name, (language, source) in pages.items():
        shown = _shown_through_dialog(qtbot, language, source)
        verdict = judge_page(name, language, source, shown)
        findings.extend(verdict.findings)
        totals.update(verdict.removed_by_clause)
        totals["unprobed"] += verdict.unprobed_removed
    return findings, totals


def test_no_shipped_cj_page_shows_a_character_the_rule_removes(qtbot, capsys):
    """REQ-L10N-UI-014 (SC-L10N-UI-014-5): no removable break of a tracked page shows.

    The probe reads the two characters Qt shows at each soft break of each page of
    every listed Chinese or Japanese tree; the clauses, restated here, decide; the
    dialog's text must show nothing at each break they remove and a space at each
    break they keep. The number of breaks examined per clause is printed and the
    total is non-zero. A tree present only in a working copy is not judged.
    """
    tracked = tracked_pages(_ROOT)
    assert guard_problems(tracked, REQUIRED_SC4_TREES, REQUIRED_CJ_TREES) == []
    assert REQUIRED_CJ_TREES, "no Chinese or Japanese tree is listed"
    pages = {
        path: (locale, _read(path))
        for locale in REQUIRED_CJ_TREES
        for path in sorted(tracked[locale])
    }
    findings, totals = _check_cj_pages(qtbot, pages)
    per_clause = {clause: totals[clause] for clause in (1, 2, 3, 4)}
    total = sum(per_clause.values())
    print(
        f"[soft breaks] SC-5 trees {list(REQUIRED_CJ_TREES)}: {len(pages)} pages; "
        f"breaks removed by clause {per_clause}, total {total}; "
        f"removed spaces on lines the probe does not read: {totals['unprobed']}"
    )
    assert not findings, "\n".join(findings[:20])
    assert total > 0, "no removable soft break was examined"


PLANTED = [
    ("clause 2", "ja", "日本\n語", 2),
    ("clause 3", "ja", "「保存」→\n「閉じる」", 3),
    ("clause 4", "ja", "設定でき、\n4 つのモード", 4),
    ("clause 4 (zh_CN)", "zh_CN", "选择，\nCtrl 键", 4),
]


@pytest.mark.parametrize(
    "label, language, source, clause", PLANTED, ids=[row[0] for row in PLANTED]
)
def test_a_planted_page_whose_break_is_shown_as_a_space_is_named(
    qtbot, monkeypatch, label, language, source, clause
):
    """Control (always runs): with the rule bypassed the check fails and names it.

    A planted page for each of clauses 2, 3 and 4 is shown with the rule bypassed,
    so its break is a space; the same check as the shipped trees' must fail and name
    the page, the line and the clause. With the rule in place the same page passes.
    """
    name = f"planted-{label}.md"
    working = _check_cj_pages(qtbot, {name: (language, source)})[0]
    assert working == [], f"the planted page fails with the rule: {working}"
    bypass_the_rule(monkeypatch)
    findings, _ = _check_cj_pages(qtbot, {name: (language, source)})
    assert len(findings) == 1, findings
    assert name in findings[0] and f":{2}:" in findings[0]
    assert f"clause {clause}" in findings[0]


def test_a_kept_break_removed_is_named_too(qtbot, monkeypatch):
    """Control: a rule that removes a break no clause removes is a finding as well."""
    monkeypatch.setattr(
        user_guide,
        "apply_soft_break_rule",
        lambda text, language: SimpleNamespace(markdown=text.replace("\n", "")),
    )
    findings, _ = _check_cj_pages(
        qtbot, {"planted-kept.md": ("ja", "ストレートアルファの\nsource-over")}
    )
    assert len(findings) == 1 and "no clause removes" in findings[0], findings


def test_the_probe_refuses_a_page_it_cannot_validate():
    """Control: a page holding the sentinel fails validation and is not skipped."""
    with pytest.raises(AssertionError):
        probe(f"日本\n{SENTINEL}語", "planted.md")


#: (label, text Qt shows, text the dialog shows, the indexes deleted or ``None`` for
#: "refused"). A ``...`` in the last place means the choice among equal blanks is
#: difflib's: only agreement with the whole-text comparison is asserted there.
DELETED_SPACE_CASES = [
    ("equal texts", "ab cd\nef", "ab cd\nef", []),
    ("a space in the first block", "日本 語\nef", "日本語\nef", [2]),
    ("a space in the last block", "ab\ncd e", "ab\ncde", [5]),
    ("a space in every block", "a b\nc d\ne f", "ab\ncd\nef", [1, 5, 9]),
    ("a space beside a line feed", "a \nb", "a\nb", [1]),
    ("one of two blanks", "a  b", "a b", ...),
    ("a line feed deleted", "ab\ncd", "abcd", [2]),
    ("a character replaced", "ab\ncd", "ab\ncX", None),
    ("a character inserted", "ab\ncd", "ab\ncdX", None),
    ("a visible character deleted", "ab\ncd", "ab\nc", None),
    ("a zero width space deleted", "a\u200bb\ncd", "ab\ncd", None),
    ("a block's last character moved on", "a\nbc", "ab\nc", None),
    ("a line feed added", "ab\ncd", "ab\ncd\n", None),
    ("a space replaced by a letter", "a b\ncd", "aXb\ncd", None),
    # The classes in which the answer is a choice, or the whole-text comparison
    # slips: the blank of a run that is reported, a blank alone on its line, and a
    # block whose fast comparison is refused although the whole-text one accepts.
    ("a run of two blanks, one deleted", "  \n", " \n", "accepted"),
    ("a run of three blanks, two deleted", "   \n", " \n", "accepted"),
    ("a run after a line feed", "\n  a", "\n a", "accepted"),
    ("a run, a letter before and a line feed after", "a  a\n", "a a\n", "accepted"),
    ("a run, a line feed before and letters beside", "\na  aa", "\na aa", "accepted"),
    ("a run beside a zero width space", "\n  \u200b", "\n \u200b", "accepted"),
    (
        "a run, a zero width space after the line feed",
        "  \n\u200b",
        " \n\u200b",
        "accepted",
    ),
    ("a blank alone on its line, then text", "\n \n ", "\n\n ", None),
    ("a blank alone on its line, then a line feed", "\n \n\n", "\n\n\n", None),
    (
        "a block the fast comparison misaligns",
        "\u200b a\n\nb bb\nb",
        "\u200b a\n\nbbb\nb",
        "accepted",
    ),
]


def _finder_outcome(
    finder: Callable[[str, str, str], List[int]], before: str, after: str
) -> Optional[List[int]]:
    """Return what ``finder`` answers for the pair: its list, ``None`` if it refuses."""
    try:
        return finder(before, after, "planted.md")
    except AssertionError as error:
        assert "planted.md" in str(error), "a refusal that does not name the page"
        return None


@pytest.mark.parametrize(
    "label, before, after, expected",
    DELETED_SPACE_CASES,
    ids=[row[0] for row in DELETED_SPACE_CASES],
)
def test_the_deleted_space_finder_answers_as_the_whole_text_comparison_does(
    label, before, after, expected
):
    """Control (REQ-L10N-UI-014): the block-wise finder equals the whole-text one.

    The two heavy tests use ``_deleted_spaces``, which compares block by block; each
    pair here, the refused ones among them, gets the same answer from it as from
    ``_deleted_spaces_whole_text`` (the comparison it replaced), and the refused
    ones are refused with the page named, so a text that differs by more than
    blanks is never read as "only spaces removed".
    """
    fast = _finder_outcome(_deleted_spaces, before, after)
    whole = _finder_outcome(_deleted_spaces_whole_text, before, after)
    assert fast == whole, label
    if expected is None:
        assert fast is None, f"{label}: the pair is not refused"
    elif expected is Ellipsis:
        assert fast is not None and len(fast) == 1, label
    elif expected == "accepted":
        assert fast, f"{label}: the pair is refused or nothing is deleted"
    else:
        assert fast == expected, label


def test_the_deleted_space_finder_agrees_on_a_shipped_page(qtbot):
    """Control (REQ-L10N-UI-014): on a real Japanese page the two finders agree.

    The shortest tracked Japanese page, shown through the window: the block-wise
    finder returns the indexes of the whole-text one, and there are some (the page
    holds breaks the rule removes), so the agreement is not two empty lists.
    """
    page = min(tracked_pages(_ROOT)["ja"], key=lambda path: len(_read(path)))
    source = _read(page)
    shown = _shown_through_dialog(qtbot, "ja", source)
    baseline = qt_alone(source)
    found = _deleted_spaces(baseline, shown, page)
    assert found == _deleted_spaces_whole_text(baseline, shown, page)
    assert found, f"{page}: no break of the page is removed, nothing was compared"


def _finder_result(
    finder: Callable[[str, str, str], List[int]], before: str, after: str
) -> Tuple[str, object]:
    """Return what ``finder`` answers: ``("ok", indexes)`` or ``("refused", text)``."""
    try:
        return "ok", finder(before, after, "planted.md")
    except AssertionError as error:
        return "refused", str(error)


def _short_pairs() -> List[Tuple[str, str]]:
    """Return ``(before, after)`` for every ``before`` of at most four characters.

    The characters are a letter, a blank, a line feed and U+200B. For each
    ``before``: every ``after`` that is ``before`` less any set of its whitespace
    characters (a blank, a line feed), and every ``after`` that differs by one
    character replaced or inserted.
    """
    pairs = set()
    for length in range(1, 5):
        for chars in itertools.product(
            ("a", " ", "\n", "\N{ZERO WIDTH SPACE}"), repeat=length
        ):
            before = "".join(chars)
            gaps = [at for at, char in enumerate(before) if char.strip() == ""]
            for mask in range(1 << len(gaps)):
                dropped = {gaps[bit] for bit in range(len(gaps)) if mask >> bit & 1}
                kept = "".join(c for at, c in enumerate(before) if at not in dropped)
                pairs.add((before, kept))
            for at in range(len(before)):
                pairs.add((before, before[:at] + "X" + before[at + 1 :]))
            for at in range(len(before) + 1):
                pairs.add((before, before[:at] + "X" + before[at:]))
    return sorted(pairs)


def test_the_deleted_space_finder_equals_the_whole_text_one_on_every_short_pair():
    """Control (REQ-L10N-UI-014): the same answer on every short pair, run or not.

    For every ``before`` of up to four characters over a letter, a blank, a line
    feed and U+200B: every ``after`` that is ``before`` less any set of its blanks
    and line feeds, and every ``after`` with one character replaced or inserted
    (about four thousand pairs). Among them are the runs of blanks beside a line
    feed or a zero width space, in which the blank that is reported decides the
    SC-4 verdict, and a blank alone on its line. The block-wise finder and the
    whole-text one return the same indexes, or both refuse with the same text, on
    every pair, so no verdict can differ between them. The pairs the whole-text
    one accepts are counted, so the agreement is not refusals everywhere.
    """
    pairs = _short_pairs()
    accepted = runs = 0
    for before, after in pairs:
        whole = _finder_result(_deleted_spaces_whole_text, before, after)
        assert _finder_result(_deleted_spaces, before, after) == whole, (before, after)
        if whole[0] == "ok":
            accepted += 1
            runs += "  " in before and before != after
    assert len(pairs) > 4000, f"only {len(pairs)} pairs were compared"
    assert accepted > 1000, f"only {accepted} accepted pairs were compared"
    assert runs > 150, f"only {runs} pairs with a run of blanks were compared"


#: ``(label, text, the text the window is handed instead)``: a table whose header
#: cell holds only a blank, so Qt's text has a line with a blank and nothing else,
#: and the window loses that blank.
BLANK_ONLY_LINE_PAGES = [
    (
        "a blank cell, then an empty one",
        "| &nbsp; |  |\n|---|---|",
        "|  |  |\n|---|---|",
    ),
    (
        "a blank cell, then a blank one",
        "| &nbsp; | &nbsp; |\n|---|---|",
        "|  | &nbsp; |\n|---|---|",
    ),
]


@pytest.mark.parametrize(
    "label, source, handed",
    BLANK_ONLY_LINE_PAGES,
    ids=[row[0] for row in BLANK_ONLY_LINE_PAGES],
)
def test_a_blank_removed_from_a_line_of_one_blank_is_named_by_the_structure_check(
    qtbot, monkeypatch, label, source, handed
):
    """Control (REQ-L10N-UI-014): a line of one blank that loses it is a problem.

    Qt shows a table cell of ``&nbsp;`` as a line holding one blank. With the rule
    in place the page is shown as Qt shows it and the structure check is silent;
    with the window handed a text that loses that blank (a planted defect, not a
    break the rule removes) the check must name the page. The whole-text comparison
    refuses these two texts, and the structure check relies on that refusal: it
    allows removed blanks and compares nothing else about them.
    """
    name = f"planted-{label}.md"
    working = differential_problems(name, source, show_page(qtbot, "ja", source))
    assert working == [], f"the page fails with the rule: {working}"
    monkeypatch.setattr(
        user_guide,
        "apply_soft_break_rule",
        lambda text, language: SimpleNamespace(markdown=handed),
    )
    dialog = show_page(qtbot, "ja", source)
    assert shown_text(dialog) != qt_alone(source), "the plant changed nothing"
    problems = differential_problems(name, source, dialog)
    assert len(problems) == 1 and name in problems[0], problems


def test_the_clauses_restated_here_agree_with_the_requirement_on_literals():
    """Control: the restated clauses decide the requirement's examples, no product."""
    assert clause_of("本", "語", "ja") == 2
    assert clause_of("본", "語", "ja") is None
    assert clause_of("」", "語", "ja") in (2, 3)
    assert clause_of("、", "A", "ja") == 4
    assert clause_of("、", "A", "en") is None
    assert clause_of("，", "A", "ja") is None
    assert clause_of("，", "A", "zh_CN") == 4
    assert clause_of("d", "​", "en") == 1
    assert clause_of("😀", "次", "ja") == 3
    assert clause_of("😀", "次", "en") is None


# --------------------------------------------------------------------------- #
# The shown document, read character by character                             #
# --------------------------------------------------------------------------- #

#: What Qt itself writes into a copied fragment's HTML, and nothing else.
QT_FRAGMENT_COMMENTS = ["<!--StartFragment-->", "<!--EndFragment-->"]

_COMMENT = re.compile(r"<!--.*?-->", re.S)

Character = Tuple[str, Optional[tuple]]


def _format_of(fmt: QTextCharFormat) -> tuple:
    """Return what a character shows: bold, italic, strikeout, underline, fixed
    pitch, anchor, its target and whether it is an image."""
    return (
        fmt.fontWeight() >= 700,
        fmt.fontItalic(),
        fmt.fontStrikeOut(),
        fmt.fontUnderline(),
        fmt.fontFixedPitch(),
        fmt.isAnchor(),
        fmt.anchorHref(),
        fmt.isImageFormat(),
    )


def characters(document: QTextDocument) -> List[Character]:
    """Return every shown character with its format, a block end as ``("\\n", None)``.

    The last block's end is not listed, so the list lines up with ``toPlainText``.
    """
    found: List[Character] = []
    block = document.begin()
    while block.isValid():
        part = block.begin()
        while not part.atEnd():
            fragment = part.fragment()
            mark = _format_of(fragment.charFormat())
            found.extend((char, mark) for char in fragment.text())
            part += 1
        found.append(("\n", None))
        block = block.next()
    return found[:-1]


def block_signature(document: QTextDocument) -> List[tuple]:
    """Return the kind of every block: heading, indent, list, marker, code, quote."""
    kinds: List[tuple] = []
    block = document.begin()
    while block.isValid():
        form = block.blockFormat()
        kinds.append(
            (
                form.headingLevel(),
                form.indent(),
                block.textList() is not None,
                form.marker().value,
                form.nonBreakableLines(),
                form.property(QTextFormat.Property.BlockQuoteLevel),
            )
        )
        block = block.next()
    return kinds


def table_grids(document: QTextDocument) -> List[List[List[str]]]:
    """Return every table of the document as rows of cell texts."""
    grids: Dict[int, List[List[str]]] = {}
    block = document.begin()
    while block.isValid():
        table = QTextCursor(block).currentTable()
        if table is not None and table.firstPosition() not in grids:
            grid: List[List[str]] = []
            for row in range(table.rows()):
                cells: List[str] = []
                for column in range(table.columns()):
                    cell = table.cellAt(row, column)
                    cursor = cell.firstCursorPosition()
                    cursor.setPosition(
                        cell.lastCursorPosition().position(),
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    cells.append(cursor.selectedText())
                grid.append(cells)
            grids[table.firstPosition()] = grid
        block = block.next()
    return list(grids.values())


def qt_document(source: str) -> QTextDocument:
    """Return what Qt alone makes of ``source``, as a document."""
    document = QTextDocument()
    document.setMarkdown(source)
    return document


def intent_document(source: str, before: str) -> QTextDocument:
    """Return Qt's document for ``source`` with the break's one space deleted.

    ``before`` is the text Qt shows before the break; the character after it must
    be the space that shows the break.
    """
    document = qt_document(source)
    text = document.toPlainText()
    assert (
        text[len(before) : len(before) + 1] == " "
    ), f"the break is not shown as a space after {before!r}: {text!r}"
    cursor = QTextCursor(document)
    cursor.setPosition(len(before))
    cursor.deleteChar()
    return document


def comments_of(document: QTextDocument) -> List[str]:
    """Return the comments in the HTML of a copy of the whole document."""
    return _COMMENT.findall(QTextDocumentFragment(document).toHtml())


def _first_difference(left: Sequence, right: Sequence) -> str:
    """Say where two lists first differ, with the characters around it."""
    for index, (one, other) in enumerate(zip(left, right)):
        if one != other:
            return f"at {index}: expected {one!r}, shown {other!r}"
    return f"one list is longer ({len(left)} against {len(right)})"


def document_problems(expected: QTextDocument, shown: QTextDocument) -> List[str]:
    """Return how ``shown`` differs from ``expected`` in text, format and blocks."""
    problems: List[str] = []
    wanted, got = characters(expected), characters(shown)
    if wanted != got:
        problems.append(
            f"characters or formats differ ({_first_difference(wanted, got)}); "
            f"expected text {expected.toPlainText()!r}, shown {shown.toPlainText()!r}"
        )
    if block_signature(expected) != block_signature(shown):
        problems.append(
            f"blocks differ: {len(block_signature(expected))} expected, "
            f"{len(block_signature(shown))} shown"
        )
    wanted_tables, shown_tables = table_grids(expected), table_grids(shown)
    if wanted_tables != shown_tables:
        problems.append(
            f"tables differ: expected {wanted_tables}, shown {shown_tables}"
        )
    return problems


def copy_problems(shown: QTextDocument, expected: QTextDocument) -> List[str]:
    """Return what a copy of the shown document carries beyond Qt's own markers.

    The comments of a copy of the whole shown document must be Qt's own fragment
    markers, and the same ones that a copy of ``expected`` (what Qt makes of the
    source without any joiner) carries.
    """
    problems: List[str] = []
    if "<!--" in shown.toPlainText():
        problems.append("the shown text holds a comment")
    found = comments_of(shown)
    if any(comment not in QT_FRAGMENT_COMMENTS for comment in found):
        problems.append(f"the copy carries comments {found}")
    if found != comments_of(expected):
        problems.append(
            f"the copy's comments {found} are not those of Qt's own "
            f"{comments_of(expected)}"
        )
    return problems


@pytest.fixture
def rule_calls(monkeypatch) -> List[object]:
    """Record every result the dialog gets from the rule, and use the real rule."""
    results: List[object] = []
    real = getattr(user_guide, "apply_soft_break_rule", None)

    def spy(text: str, language: str):
        result = real(text, language)
        results.append(result)
        return result

    # A window that never asks the rule leaves ``results`` empty; the rows then fail
    # on what is shown, which is the reason that matters.
    monkeypatch.setattr(user_guide, "apply_soft_break_rule", spy, raising=False)
    return results


def plain_join(text: str, language: str):
    """Return a rule that removes every line ending beside a non-ASCII character.

    The naive rule the joiner exists to improve on: the line ending goes, whatever
    delimiter or bracket stands at the join, and nothing is placed there and
    nothing is kept.
    """
    join = re.compile(r"([^\x00-\x7f][*_~`)!\[(\]]*)\n([*_~`\[(!]*[^\x00-\x7f])")
    return SimpleNamespace(markdown=join.sub(r"\1\2", text), breaks=())


# --------------------------------------------------------------------------- #
# The join's render rows: what Qt shows for each construct at a join          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Render:
    """One row: a page of one soft break and what the window must show for it.

    ``joined`` rows must show Qt's text for the source with the break's space
    deleted, character for character in text, bold, italic, strikeout, underline,
    fixed pitch, anchor, target and image, and in the blocks. ``kept`` rows must show
    exactly what Qt shows for the source, and the break is reported undecided.
    ``joiner`` says whether the join places an invisible comment between the two
    characters.
    """

    name: str
    source: str
    kind: str
    before: str = ""
    joiner: bool = False


ZW = "​"

RENDER_ROWS: List[Render] = [
    Render("control: two wide characters", "日\n本", "joined", "日"),
    Render(
        "flanking: bold ends with a stop",
        "**移動。**\nを選ぶ",
        "joined",
        "移動。",
        True,
    ),
    Render("strikeout: closes at the join", "~~日~~\n本", "joined", "日", True),
    Render("two code spans meet", "`日`\n`本`", "joined", "日", True),
    Render("two double-backtick spans meet", "``日``\n``本``", "joined", "日", True),
    Render(
        "a single and a double code span meet", "`日`\n``本``", "joined", "日", True
    ),
    Render(
        "a literal backtick, then a span, by clause 1",
        f"日`\n``{ZW}本``",
        "joined",
        "日`",
        True,
    ),
    Render("a code span on one side only (before)", "`日`\n本", "joined", "日"),
    Render("a code span on one side only (after)", "日\n`本`", "joined", "日"),
    Render(
        "two references meet",
        "[日]\n[本]\n\n[日]: /a\n[本]: /b\n",
        "joined",
        "日",
        True,
    ),
    Render(
        "a reference then a parenthesis, by clause 1",
        f"[日{ZW}]\n(本)\n\n[日{ZW}]: /a\n",
        "joined",
        f"日{ZW}",
        True,
    ),
    Render(
        "a reference then a definition colon, by clause 1",
        f"[日{ZW}]\n: /x\n\n[日{ZW}]: /a\n",
        "joined",
        f"日{ZW}",
        True,
    ),
    Render("an inline link, then a link", "[日](/a)\n[本](/b)", "joined", "日"),
    Render(
        "a bang then a bracket, by clause 1",
        f"日!\n[{ZW}本](/x)",
        "joined",
        "日!",
        True,
    ),
    Render("an even backslash run, by clause 1", f"日\\\\\n{ZW}本", "joined", "日\\"),
    Render("an ampersand, by clause 1", f"日&\n{ZW}amp;", "joined", "日&"),
    Render("a less-than sign, by clause 1", f"日<\n{ZW}b>本", "joined", "日<"),
    Render("emphasis inside link text", "[*日*\n*本*](/x)", "joined", "日", True),
    Render("underline: ends with a stop", "_移動。_\nを選ぶ", "joined", "移動。", True),
    Render(
        "underline: a double underscore", "__移動。__\nを選ぶ", "joined", "移動。", True
    ),
    Render("underline: two runs meet", "_日_\n_本_", "joined", "日", True),
    Render("an inline destination completed", "[x](日\n本)", "kept"),
    Render("a URI autolink completed", "<http://日\n本>", "kept"),
    Render("raw HTML with an unquoted attribute", "<a href=日\n本>x", "kept"),
    Render("a label that gains a definition", "[日\n本]\n\n[日本]: /x\n", "kept"),
    Render("a label that loses its definition", "[日\n本]\n\n[日 本]: /x\n", "kept"),
    Render(
        "a bare address ending in a wide character",
        "https://example.com/日\n本",
        "kept",
    ),
    Render(
        "a bare www address ending in a wide character",
        "www.example.com/日\n本",
        "kept",
    ),
    Render("a bare address, then a full stop", "https://example.com/a\n。", "kept"),
    Render("a bare www address, then a comma", "www.example.com\n、日", "kept"),
    Render("an e-mail address, then a full stop", "a@example.com\n。", "kept"),
    Render("a full stop, then a bare address", "日。\nhttps://example.com", "kept"),
    Render("a full stop, then a bare www address", "日。\nwww.example.com", "kept"),
    Render("a full stop, then an e-mail address", "日。\na@example.com", "kept"),
    Render(
        "an address ending in a digit, then a stop", "https://example.com/1\n。", "kept"
    ),
    Render("a table header candidate", "a|日\n本|\n|-|-|\n", "kept"),
]


def render_problems(row: Render, dialog: User_Guide_Dialog) -> List[str]:
    """Return how the shown page differs from what the row says it must show."""
    shown = dialog._content_view.document()
    if row.kind == "joined":
        expected = intent_document(row.source, row.before)
    else:
        expected = qt_document(row.source)
    return document_problems(expected, shown) + copy_problems(shown, expected)


@pytest.mark.parametrize("row", RENDER_ROWS, ids=[row.name for row in RENDER_ROWS])
def test_a_join_shows_what_qt_shows_without_the_break(qtbot, rule_calls, row):
    """REQ-L10N-UI-014: each construct at a join shows the intent, or is left alone.

    The oracle is Qt: ``setMarkdown`` of the source with the one space at the break
    deleted (a joined row) or the source as it is (a kept row), compared per
    character on text, bold, italic, strikeout, underline, fixed pitch, anchor,
    target and image, and on the blocks. Neither the copied text nor a copy of the
    whole document carries a comment beyond Qt's own markers.
    """
    dialog = show_page(qtbot, "ja", row.source)
    assert render_problems(row, dialog) == []
    assert rule_calls, "the dialog did not ask the rule"
    result = rule_calls[-1]
    assert (SOFT_BREAK_JOINER in result.markdown) == row.joiner, (
        f"{row.name}: the join places a joiner it does not need"
        if not row.joiner
        else f"{row.name}: the join places no joiner where one is needed"
    )
    if row.kind == "kept":
        assert result.breaks, "a kept row reports no break"
        assert all(
            item.clause is SoftBreakClause.UNDECIDED for item in result.breaks
        ), [item.clause for item in result.breaks]


def test_the_render_rows_cover_every_class_and_carry_their_controls():
    """Control: the rows are not empty and hold both kinds, each in several classes."""
    kinds = Counter(row.kind for row in RENDER_ROWS)
    assert kinds["joined"] >= 15 and kinds["kept"] >= 10, kinds
    assert sum(row.joiner for row in RENDER_ROWS) >= 10
    assert len({row.name for row in RENDER_ROWS}) == len(RENDER_ROWS)
    for row in RENDER_ROWS:
        assert row.source.count("\n") >= 1
        assert (row.kind == "joined") == bool(row.before)


#: The strikeout row's plain join is harmless in Qt (measured), so the joiner is
#: placed there without being needed; every other joiner row fails without it.
NEEDS_THE_JOINER = [
    row for row in RENDER_ROWS if row.joiner and not row.name.startswith("strikeout")
]


@pytest.mark.parametrize("row", NEEDS_THE_JOINER, ids=lambda row: row.name)
def test_a_plain_join_fails_a_row_that_needs_the_joiner(qtbot, monkeypatch, row):
    """Control: with the naive rule the joined rows that need the joiner fail.

    The page shown through the same dialog with a rule that removes the line ending
    and places nothing: the row's own check must report it, so the row cannot pass
    because the join happened to be harmless.
    """
    monkeypatch.setattr(user_guide, "apply_soft_break_rule", plain_join, raising=False)
    dialog = show_page(qtbot, "ja", row.source)
    assert render_problems(row, dialog), f"{row.name}: a plain join passes the row"


def test_a_plain_join_passes_the_control_row_and_fails_a_kept_row(qtbot, monkeypatch):
    """Control: the naive rule is right for two wide characters and wrong for a link."""
    monkeypatch.setattr(user_guide, "apply_soft_break_rule", plain_join, raising=False)
    control = RENDER_ROWS[0]
    assert render_problems(control, show_page(qtbot, "ja", control.source)) == []
    kept = next(row for row in RENDER_ROWS if row.name.startswith("an inline dest"))
    assert render_problems(kept, show_page(qtbot, "ja", kept.source))


# --------------------------------------------------------------------------- #
# Qt's default dialect, and Qt's table model, as the rule relies on them      #
# --------------------------------------------------------------------------- #


def _hrefs(document: QTextDocument) -> List[str]:
    """Return the distinct link targets of the document, in order."""
    found: List[str] = []
    for _char, mark in characters(document):
        if mark and mark[5] and mark[6] not in found:
            found.append(mark[6])
    return found


DIALECT = [
    ("a bare address is linked", "https://example.com/a", ["https://example.com/a"]),
    ("a www address is linked", "www.example.com", ["http://www.example.com"]),
    ("an e-mail address is linked", "a@example.com", ["mailto:a@example.com"]),
    ("an address then a full stop is not linked", "https://example.com/a。", []),
    ("a www address then a full stop is not linked", "www.example.com。", []),
]


@pytest.mark.parametrize(
    "label, source, hrefs", DIALECT, ids=[row[0] for row in DIALECT]
)
def test_qts_dialect_links_what_the_rule_assumes(qtbot, label, source, hrefs):
    """REQ-L10N-UI-014: Qt's default dialect links bare addresses, as the rule rests on.

    A later Qt that changes this fails here, not as drift in a shipped page.
    """
    page = show_page(qtbot, "en", source)
    document = page._content_view.document()
    assert _hrefs(document) == hrefs, label
    assert document.toPlainText() == source


def test_qts_dialect_shows_underscore_as_underline_and_keeps_two_signs_literal(qtbot):
    """REQ-L10N-UI-014: ``_x_`` is underlined, not italic; ``$x$``, ``[[x]]`` stay."""
    page = show_page(qtbot, "en", "_x_")
    underlined = page._content_view.document()
    marks = [mark for _char, mark in characters(underlined) if mark]
    assert underlined.toPlainText() == "x"
    assert marks and all(mark[3] for mark in marks) and not any(m[1] for m in marks)
    for source in ("$x$", "[[x]]"):
        page = show_page(qtbot, "en", source)
        shown = page._content_view.document()
        assert shown.toPlainText() == source
        assert block_signature(shown) == block_signature(qt_document(source))


TABLE_MODEL = [
    ("a header of three cells over two", "a|b|c\n|-|-|\n", [[["a", "b"]]]),
    ("a header below a first line", "a\n|-|-|\n", [[["a", ""]]]),
    ("a header below a second line is no table", "x\na|b\n|-|-|\n", []),
    (
        "a heading is a body row",
        "a|b\n|-|-|\n# h\nx\ny\n\nx\ny\n",
        [[["a", "b"], ["# h", ""], ["x", ""], ["y", ""]]],
    ),
    (
        "a fence is a body row",
        "a|b\n|-|-|\n```\nx\ny\n\nx\ny\n",
        [[["a", "b"], ["```", ""], ["x", ""], ["y", ""]]],
    ),
    (
        "a list item ends the table",
        "a|b\n|-|-|\n- x\nx\ny\n\nx\ny\n",
        [[["a", "b"]]],
    ),
    (
        "a thematic break ends the table",
        "a|b\n|-|-|\n***\nx\ny\n\nx\ny\n",
        [[["a", "b"]]],
    ),
    (
        "a four-column indent ends the table",
        "a|b\n|-|-|\n    code\nx\ny\n\nx\ny\n",
        [[["a", "b"]]],
    ),
]


@pytest.mark.parametrize(
    "label, source, grids", TABLE_MODEL, ids=[row[0] for row in TABLE_MODEL]
)
def test_qts_table_model_is_what_the_rule_follows(qtbot, label, source, grids):
    """REQ-L10N-UI-014: where Qt starts and ends a table, as the rule follows it.

    A table starts only below a paragraph's first line and no cell count is compared
    (a header of three cells over a delimiter row of two is a table of two columns);
    a heading and a fence below a table are body rows; a list item, a thematic break
    and a four-column indent end it. A later Qt that changes any of it fails here.
    """
    page = show_page(qtbot, "en", source)
    document = page._content_view.document()
    shown = table_grids(document)
    if label == "a header below a first line":
        assert len(shown) == 1 and shown[0][0][0] == "a" and len(shown[0][0]) == 2
    else:
        assert shown == grids, label
    assert document.toPlainText() == qt_alone(source)


# --------------------------------------------------------------------------- #
# Tables through the window: what ends a table, what starts one               #
# --------------------------------------------------------------------------- #

#: (name, source, the source Qt must be left to show). ``None`` means the source
#: itself, byte for byte; the others lose only the break Qt shows inside a paragraph.
TABLE_ROWS = [
    ("T01 a delimiter row inside a paragraph", "日\n本\n|-|-|\n​語\n", None),
    ("T02 a header-shaped line above it", "a|日\n本|\n|-|-|\n​語\n", None),
    ("T03 a header candidate", "a|日\n本|\n|-|-|\n", None),
    ("T04 a table, then a ZW-led line", "a|b|c\n|-|-|\n​語\n", None),
    ("T05 a table, then two lines", "a|b|c\n|-|-|\n日\n本\n", None),
    ("T06 a one-line header, then two lines", "日\n|-|-|\n日\n本\n", None),
    ("T07 a header on a second line", "日\n本|\n|-|\n", None),
    (
        "T08 a second-line header, then two lines",
        "日\na|b\n|-|-|\n日\n本\n",
        "日\na|b\n|-|-|\n日本\n",
    ),
    ("T09 inside a quote", "> 日\n> 本|\n> |-|\n", None),
    ("T10 a heading below a table", "a|b\n|-|-|\n# h\n日\n本\n", None),
    (
        "T11 a fence below a table",
        "a|b\n|-|-|\n```\n日\n本\n\n日\n本\n",
        "a|b\n|-|-|\n```\n日\n本\n\n日本\n",
    ),
    (
        "T12 an indented line below a table",
        "a|b\n|-|-|\n    code\n日\n本\n",
        "a|b\n|-|-|\n    code\n日本\n",
    ),
    (
        "T13 a definition, then a header",
        "[a]: /x\nb|c\n|-|-|\n日\n本\n",
        "[a]: /x\nb|c\n|-|-|\n日本\n",
    ),
    (
        "T14 control: a table, a blank line, a paragraph",
        "a|b\n|-|-|\n日\n本\n\n日\n本\n",
        "a|b\n|-|-|\n日\n本\n\n日本\n",
    ),
    (
        "T15 control: a thematic break ends a table",
        "a|b\n|-|-|\n***\n日\n本\n",
        "a|b\n|-|-|\n***\n日本\n",
    ),
    ("T16 control: a plain pair", "日\n本\n", "日本\n"),
]


@pytest.mark.parametrize(
    "name, source, output", TABLE_ROWS, ids=[r[0] for r in TABLE_ROWS]
)
def test_a_table_is_shown_as_qt_shows_the_raw_source(qtbot, name, source, output):
    """REQ-L10N-UI-014: the tables Qt shows for the raw source are the ones shown.

    Each row goes through the window in a Japanese page. Its grids (rows, columns
    and every cell's text) are those of the raw source, and its shown text is what
    Qt shows for the output the row expects: the source itself, or the source with
    only the break that Qt shows inside a paragraph removed.
    """
    dialog = show_page(qtbot, "ja", source)
    shown = dialog._content_view.document()
    assert table_grids(shown) == table_grids(qt_document(source)), name
    expected_text = qt_alone(source if output is None else output)
    assert shown.toPlainText() == expected_text, name
    expected = qt_document(source if output is None else output)
    assert copy_problems(shown, expected) == []


@pytest.mark.parametrize(
    "name, source",
    [(row[0], row[1]) for row in TABLE_ROWS if row[2] is None],
    ids=[row[0] for row in TABLE_ROWS if row[2] is None],
)
def test_a_table_row_that_must_stay_is_shown_byte_for_byte(qtbot, name, source):
    """REQ-L10N-UI-014: a row the rule leaves alone shows what Qt shows without it."""
    page = show_page(qtbot, "ja", source)
    shown = page._content_view.document()
    assert document_problems(qt_document(source), shown) == [], name


def test_the_table_rows_are_sixteen_and_include_the_ones_that_damage_a_grid():
    """Control: the sixteen rows are all there, the damaging ones among them."""
    assert [row[0][:3] for row in TABLE_ROWS] == [f"T{n:02d}" for n in range(1, 17)]
    left = [row for row in TABLE_ROWS if row[2] is None]
    assert len(left) == 9


# --------------------------------------------------------------------------- #
# Entity references, kept as they are                                         #
# --------------------------------------------------------------------------- #

ENTITY_ROWS = [
    ("a name Qt does not decode, before", "日&Abreve;\n本"),
    ("a name Qt does not decode, after", "日\n&Abreve;本"),
    ("an ampersand reference, before", "日&amp;\n本"),
    ("an ampersand reference, after", "日\n&amp;本"),
]


@pytest.mark.parametrize(
    "label, source", ENTITY_ROWS, ids=[row[0] for row in ENTITY_ROWS]
)
def test_a_break_beside_a_reference_is_kept(qtbot, rule_calls, label, source):
    """REQ-L10N-UI-014: references are recognised, never decoded; their breaks stay.

    Qt decodes 250 of the 2,125 HTML5 names, so a reference's visible neighbour is
    not known to the rule: the break beside it is reported undecided and the shown
    text is Qt's own, break space included. Qt's own text is recorded here: an
    ``&Abreve;`` is shown literally and an ``&amp;`` as one ampersand.
    """
    dialog = show_page(qtbot, "ja", source)
    qt_text = qt_alone(source)
    if "Abreve" in source:
        assert "&Abreve;" in qt_text, qt_text
    else:
        assert "&" in qt_text and "&amp;" not in qt_text, qt_text
    assert shown_text(dialog) == qt_text, label
    assert rule_calls and rule_calls[-1].breaks
    assert all(
        item.clause is SoftBreakClause.UNDECIDED for item in rule_calls[-1].breaks
    )


# --------------------------------------------------------------------------- #
# Several joiners in one page; the copy                                       #
# --------------------------------------------------------------------------- #

#: (name, page, joiners the page needs). Every line ending of each page is a break
#: the rule removes, so each must lose its space and nothing else.
MULTI_JOINER = [
    ("two joiners in one paragraph", "**移動。**\nを選ぶ。**確認**\nをする", 2),
    (
        "three joiners mixing three delimiters",
        "**日本**\n語を。_移動。_\nして~~削除~~\nする",
        3,
    ),
    ("joiners in a list item", "- **移動。**\n  を選ぶ\n  ~~日~~\n  本", 3),
    ("joiners in a block quote", "> **移動。**\n> を選ぶ\n> _日_\n> 本", 3),
    ("a joiner, then inline keys", "**日本**\n語を<kbd>Ctrl</kbd>で選ぶ", 1),
    ("a joiner, then a link", "**日本**\n語を[保存](save.md)で選ぶ", 1),
]


@pytest.mark.parametrize(
    "name, source, joiners", MULTI_JOINER, ids=[row[0] for row in MULTI_JOINER]
)
def test_several_joiners_change_nothing_that_is_shown(
    qtbot, rule_calls, name, source, joiners
):
    """REQ-L10N-UI-014: joiners cost nothing that is shown, however many a page has.

    Against Qt's text for the unjoined source: the shown text is equal except for
    the removed spaces, one per joiner; every character's format and the blocks are
    equal; the shown text holds no literal markup; and a copy of the whole document
    carries no comment beyond Qt's own markers.
    """
    dialog = show_page(qtbot, "ja", source)
    problems = differential_problems(name, source, dialog)
    assert problems == [], "\n".join(problems)
    shown = dialog._content_view.document()
    removed = _deleted_spaces(qt_alone(source), shown.toPlainText(), name)
    assert len(removed) == source.count("\n"), (len(removed), source.count("\n"))
    for literal in ("**", "~~", "<!--"):
        assert literal not in shown.toPlainText(), literal
    assert copy_problems(shown, qt_document(source)) == []
    assert rule_calls, "the dialog did not ask the rule"
    assert rule_calls[-1].markdown.count(SOFT_BREAK_JOINER) == joiners


def test_a_plain_join_shows_literal_markup_and_the_copy_check_sees_a_comment(
    qtbot, monkeypatch
):
    """Control: a plain join shows ``**``, and a comment in a copy would be seen.

    The multi-joiner check must be able to fail: with the naive rule the bold run
    breaks and the markers are shown; and the comment finder returns every comment
    of an HTML text, so a joiner that leaked into a copy would not be missed.
    """
    monkeypatch.setattr(user_guide, "apply_soft_break_rule", plain_join, raising=False)
    source = MULTI_JOINER[0][1]
    dialog = show_page(qtbot, "ja", source)
    assert "**" in dialog._content_view.document().toPlainText()
    assert differential_problems("plain", source, dialog)
    assert _COMMENT.findall("<p>a<!--x-->b</p><!--StartFragment-->") == [
        "<!--x-->",
        "<!--StartFragment-->",
    ]


def test_the_copy_of_a_plain_page_carries_qts_own_markers_only(qtbot):
    """Control: a page with no joiner has exactly Qt's two fragment markers.

    And every multi-joiner page's copy holds the same comments as Qt's own copy of
    its unjoined source.
    """
    page = show_page(qtbot, "en", "Hello\nworld")
    shown = page._content_view.document()
    assert comments_of(shown) == QT_FRAGMENT_COMMENTS
    for _name, source, _joiners in MULTI_JOINER:
        page = show_page(qtbot, "ja", source)
        joined = page._content_view.document()
        assert comments_of(joined) == comments_of(qt_document(source))


# --------------------------------------------------------------------------- #
# The structural differential over every shipped page, and the scanner's      #
# candidates on the lines the probe does not read                             #
# --------------------------------------------------------------------------- #


def differential_problems(
    page: str, source: str, dialog: User_Guide_Dialog
) -> List[str]:
    """Compare the shown page with Qt alone, allowing only removed break spaces.

    The shown text may lack spaces Qt shows; everything else must be equal: every
    remaining character with its bold, italic, strikeout, underline, fixed pitch,
    anchor, target and image; the blocks and their kinds; the tables' shapes.
    """
    problems: List[str] = []
    baseline = qt_document(source)
    shown = dialog._content_view.document()
    try:
        deleted = set(
            _deleted_spaces(baseline.toPlainText(), shown.toPlainText(), page)
        )
    except AssertionError as error:
        return [str(error)]
    wanted = characters(baseline)
    if len(wanted) != len(baseline.toPlainText()):
        return [f"{page}: the character list does not line up with the text"]
    wanted = [item for index, item in enumerate(wanted) if index not in deleted]
    got = characters(shown)
    if wanted != got:
        problems.append(f"{page}: formats differ ({_first_difference(wanted, got)})")
    if block_signature(baseline) != block_signature(shown):
        problems.append(
            f"{page}: blocks differ "
            f"({len(block_signature(baseline))} against {len(block_signature(shown))})"
        )
    shape = [[len(row) for row in grid] for grid in table_grids(baseline)]
    if shape != [[len(row) for row in grid] for grid in table_grids(shown)]:
        problems.append(f"{page}: the tables' shapes differ")
    return problems


#: The pages the structural check always runs, flanking and joining cases included.
PLANTED_STRUCTURE = [
    ("flanking.md", "ja", "**移動。**\nを選ぶ"),
    ("backticks.md", "ja", "`日`\n`本`"),
    ("references.md", "ja", "[日]\n[本]\n\n[日]: /a\n[本]: /b\n"),
    ("underline.md", "ja", "_日_\n_本_"),
]


def test_the_structure_is_equal_on_every_shipped_page(qtbot, capsys):
    """REQ-L10N-UI-014: blocks, block kinds and formats equal Qt's on every page.

    Every page of every listed tree is shown through the window and compared with
    Qt alone, allowing only the removed break spaces: every character's bold, italic,
    strikeout, underline, fixed pitch, anchor, target and image, the blocks and their
    kinds, and the shapes of the tables. Pages per language are printed and are
    non-zero.
    """
    tracked = tracked_pages(_ROOT)
    assert guard_problems(tracked, REQUIRED_SC4_TREES, REQUIRED_CJ_TREES) == []
    findings: List[str] = []
    lines: List[str] = []
    for locale in REQUIRED_SC4_TREES + REQUIRED_CJ_TREES:
        pages = sorted(tracked[locale])
        assert pages, f"{locale}: no page"
        for path in pages:
            source = _read(path)
            dialog = show_page(qtbot, locale, source)
            findings.extend(differential_problems(path, source, dialog))
        lines.append(f"{locale} {len(pages)}")
    print("[soft breaks] structure equal on pages: " + "; ".join(lines))
    assert not findings, "\n".join(findings[:20])


@pytest.mark.parametrize(
    "name, language, source",
    PLANTED_STRUCTURE,
    ids=[row[0] for row in PLANTED_STRUCTURE],
)
def test_a_planted_page_keeps_its_structure_and_a_plain_join_does_not(
    qtbot, monkeypatch, name, language, source
):
    """Control (always runs): the structural check passes with the rule, fails without.

    The same page with the rule in place has Qt's structure; with the naive rule
    the check reports it, naming the page.
    """
    shown = show_page(qtbot, language, source)
    assert differential_problems(name, source, shown) == []
    monkeypatch.setattr(user_guide, "apply_soft_break_rule", plain_join, raising=False)
    found = differential_problems(name, source, show_page(qtbot, language, source))
    assert found and name in found[0], found


def _skipped_shape(line: str) -> bool:
    """Say whether a line has one of the shapes the probe never reads.

    Blank, fence, table row, a line that begins with ``<``, thematic and setext,
    seen through any block quote or list indentation.
    """
    text = re.sub(r"^(?:\s*>)*\s*", "", line)
    return (
        not text.strip()
        or text.startswith(("```", "~~~", "<"))
        or "|" in text
        or bool(_THEMATIC.match(text.strip()))
        or bool(_SETEXT.match(text.strip()))
    )


def test_the_rule_reports_no_candidate_on_a_line_the_probe_skips(
    qtbot, rule_calls, capsys
):
    """REQ-L10N-UI-014: the rule's own candidates are never on a line the probe skips.

    For every shipped page, each break the rule reports (the dialog's own call) is
    followed by a line; none of those lines may have a shape the probe leaves out
    (blank, fence, table row, ``<``, thematic, setext). The counts are printed and
    every listed tree has candidates.
    """
    tracked = tracked_pages(_ROOT)
    findings: List[str] = []
    totals: Dict[str, Tuple[int, int]] = {}
    for locale in REQUIRED_SC4_TREES + REQUIRED_CJ_TREES:
        reported = skipped = 0
        for path in sorted(tracked[locale]):
            source = _read(path)
            rule_calls.clear()
            show_page(qtbot, locale, source)
            assert rule_calls, f"{path}: the window did not ask the rule"
            lines = source.split("\n")
            for item in rule_calls[-1].breaks:
                reported += 1
                if item.line < len(lines) and _skipped_shape(lines[item.line]):
                    skipped += 1
                    findings.append(f"{path}:{item.line + 1}: {lines[item.line]!r}")
        totals[locale] = (reported, skipped)
    print(f"[soft breaks] rule candidates (reported, on skipped lines): {totals}")
    assert not findings, "\n".join(findings[:20])
    assert all(reported > 0 for reported, _ in totals.values()), totals
