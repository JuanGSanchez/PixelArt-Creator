"""The real-time message with no transport is shown wholly in the interface language.

REQ-L10N-UI-017: when the user starts real-time collaboration and no real-time
transport is configured, the status bar shows the message in the active language,
both its frame (English source ``Real-time: {msg}``) and its reason (English source
``no real-time transport configured``). On the shipped product this is what every
start gives, because no transport factory is supplied anywhere.

What a row reads is what the user reads: the window is the real ``Main_Window``,
the language is chosen from its Language menu, the action is its real
``Start Real-time...`` entry (the member-id question it asks first is answered by a
planted ``QInputDialog.getText``), and the text is read back from the status bar.
No transport factory is given to the session, so the reason is the one the
requirement names.

The oracle is never the code under test. For English the expected text is the two
source messages, which must nevertheless be messages of ``pixelart_en.ts``. For any
other language it is read from that language's own ``.ts`` file: exactly one entry
for each message in its context (``Main_Window`` for the frame, ``Realtime_Client``
for the reason), finished, with a text, and the frame carrying its ``{msg}`` once.
The status bar must equal the frame with the reason in place of ``{msg}``, and in no
language but English may it contain the English reason.

* SC-L10N-UI-017-1: each of the eight languages, the number examined (8) printed;
* SC-L10N-UI-017-2: after a live switch (English to Japanese, then two further
  switches) the next message is in the new language, so a reason cached by an earlier
  message fails.

Controls: a worker that shows its reason untranslated (what the audit measured: the
English reason in a Japanese status bar) and one that caches the reason of the first
message are each caught; the verdict decides literal messages; the oracle refuses an
unfinished entry. Both themes (light and dark), offscreen.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QInputDialog, QMenu, QStatusBar

from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.realtime_actions import Realtime_Session
from pixelart_creator.ui.realtime_worker import Realtime_Client

# --------------------------------------------------------------------------- #
# The oracle                                                                  #
# --------------------------------------------------------------------------- #

#: The languages the finished product ships (English included), the way the
#: requirement counts them.
EXPECTED_LANGUAGE_COUNT = 8
LANGUAGES: Tuple[str, ...] = ("en", "es", "fr", "de", "ru", "zh_CN", "ko", "ja")
NON_ENGLISH = tuple(code for code in LANGUAGES if code != FALLBACK_LANGUAGE)

#: The two source messages of the requirement, each with the catalogue context the
#: interface looks it up in.
FRAME_CONTEXT = "Main_Window"
FRAME_SOURCE = "Real-time: {msg}"
REASON_CONTEXT = "Realtime_Client"
REASON_SOURCE = "no real-time transport configured"

#: The placeholder of the frame, and the English label of the action chosen.
PLACEHOLDER = "{msg}"
START_LABEL = "Start Real-time…"

#: The interface's own name for Japanese, the language the scenario selects.
JAPANESE_NAME = "日本語"


def catalogue_text(
    code: str, context: str, source: str, directory: Optional[Path] = None
) -> str:
    """Return the text the interface must show for ``source`` in language ``code``.

    English has no translation and shows its source, which must be a message of
    ``pixelart_en.ts``. Any other language is read from its own ``.ts``: exactly one
    entry in the context, finished, with a text.
    """
    folder = directory if directory is not None else _default_translations_dir()
    path = folder / f"pixelart_{code}.ts"
    root = ET.parse(path).getroot()
    found = [
        message
        for scope in root.iter("context")
        if scope.findtext("name") == context
        for message in scope.iter("message")
        if message.findtext("source") == source
    ]
    assert len(found) == 1, f"{path.name}: {len(found)} entries for {source!r}"
    if code == FALLBACK_LANGUAGE:
        return source
    translation = found[0].find("translation")
    assert translation is not None and translation.text, f"{path.name}: no text"
    assert translation.get("type") != "unfinished", f"{path.name}: unfinished"
    return translation.text


@dataclass(frozen=True)
class Expected:
    """What the status bar must show in one language."""

    code: str
    frame: str
    reason: str

    @property
    def message(self) -> str:
        """The frame with the reason in place of its placeholder."""
        return self.frame.replace(PLACEHOLDER, self.reason)


def expected_for(code: str, directory: Optional[Path] = None) -> Expected:
    """Read the frame and the reason of ``code`` from its catalogue."""
    frame = catalogue_text(code, FRAME_CONTEXT, FRAME_SOURCE, directory)
    reason = catalogue_text(code, REASON_CONTEXT, REASON_SOURCE, directory)
    assert frame.count(PLACEHOLDER) == 1, f"{code}: the frame {frame!r} has no {{msg}}"
    return Expected(code, frame, reason)


def message_problems(shown: str, expected: Expected) -> List[str]:
    """Return what is wrong with the ``shown`` status bar text; empty is a pass.

    The verdict of every row about the text: it equals the frame with the reason in
    place of ``{msg}``, and outside English it holds no trace of the English reason.
    A pure function, so the controls decide it on literals.
    """
    problems: List[str] = []
    if shown != expected.message:
        problems.append(
            f"[{expected.code}] the status bar shows {shown!r}, the catalogue's "
            f"frame with its reason is {expected.message!r}"
        )
    if expected.code != FALLBACK_LANGUAGE and REASON_SOURCE in shown:
        problems.append(f"[{expected.code}] the English reason is shown: {shown!r}")
    return problems


# --------------------------------------------------------------------------- #
# The window under test                                                       #
# --------------------------------------------------------------------------- #


def _actions_of(menu: QMenu) -> Iterator[QAction]:
    """Yield every action under ``menu``, entering its submenus."""
    for action in menu.actions():
        yield action
        sub = action.menu()
        if isinstance(sub, QMenu):
            yield from _actions_of(sub)


def _all_actions(window: Main_Window) -> List[QAction]:
    """Return every action reachable from the window's menu bar."""
    found: List[QAction] = []
    for top in window.menuBar().actions():
        found.append(top)
        menu = top.menu()
        if isinstance(menu, QMenu):
            found.extend(_actions_of(menu))
    return found


@dataclass
class Bench:
    """The real window, its Language menu entries and its ``Start Real-time...``."""

    qtbot: Any
    window: Main_Window
    manager: LanguageManager
    session: Realtime_Session
    bar: QStatusBar
    languages: Dict[str, QAction]
    start_action: QAction
    asked: List[Tuple[str, str]]

    def select(self, code: str) -> None:
        """Choose language ``code`` from the Language menu, as the user does."""
        self.languages[code].trigger()
        assert self.manager.current_language() == code, f"{code!r} was not selected"

    def start(self) -> Tuple[str, List[Any]]:
        """Choose Start Real-time; return the status bar text and the signal args.

        The observer is connected before the action is triggered. The signal is the
        session's ``errorOccurred(message, is_failure)``, which the window turns into
        the status bar text.
        """
        self.bar.clearMessage()
        before = len(self.asked)
        with self.qtbot.waitSignal(self.session.errorOccurred, timeout=1000) as blocker:
            self.start_action.trigger()
        assert len(self.asked) == before + 1, "the member id was not asked once"
        assert not self.session.client().is_active(), "a worker was started"
        return self.bar.currentMessage(), list(blocker.args or [])


@pytest.fixture
def bench(qtbot, mute_message_boxes, monkeypatch) -> Iterator[Bench]:
    """A window with no transport factory; English is restored afterwards."""
    asked: List[Tuple[str, str]] = []

    def member_id(parent: object, title: str, label: str, *args: Any, **kwargs: Any):
        asked.append((title, label))
        return "alice", True

    monkeypatch.setattr(QInputDialog, "getText", member_id)
    window = Main_Window()
    qtbot.addWidget(window)
    manager = window.findChildren(LanguageManager)[0]
    sessions = window.findChildren(Realtime_Session)
    assert len(sessions) == 1, f"{len(sessions)} real-time sessions"
    assert manager.current_language() == FALLBACK_LANGUAGE

    actions = _all_actions(window)
    languages = {
        a.data(): a
        for a in actions
        if isinstance(a.data(), str) and a.data() in LANGUAGES
    }
    assert sorted(languages) == sorted(LANGUAGES), sorted(languages)
    starts = [a for a in actions if a.text().replace("&", "") == START_LABEL]
    assert len(starts) == 1, f"{len(starts)} actions are labelled {START_LABEL!r}"
    try:
        yield Bench(
            qtbot,
            window,
            manager,
            sessions[0],
            window.statusBar(),
            languages,
            starts[0],
            asked,
        )
    finally:
        manager.set_language(FALLBACK_LANGUAGE)
        assert (
            mute_message_boxes == []
        ), f"a message box was raised: {mute_message_boxes}"


def start_in(bench: Bench, code: str) -> Tuple[str, Expected]:
    """Select ``code``, choose Start and return the text with what it must be."""
    expected = expected_for(code)
    bench.select(code)
    shown, args = bench.start()
    assert args == [expected.reason, False], (
        f"[{code}] the session reported {args!r}, the catalogue's reason is "
        f"{expected.reason!r} (not a failure)"
    )
    return shown, expected


# --------------------------------------------------------------------------- #
# SC-L10N-UI-017-1: each language                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("code", LANGUAGES)
def test_sc_l10n_ui_017_1_the_status_bar_is_the_catalogue_frame_with_its_reason(
    bench, code
):
    """SC-L10N-UI-017-1: no transport configured, Start gives the frame and reason.

    With ``code`` active and no transport factory, choosing Start Real-time...
    leaves the status bar equal to that catalogue's translation of
    ``Real-time: {msg}`` with its translation of the reason in place of ``{msg}``;
    outside English it holds no English reason.
    """
    shown, expected = start_in(bench, code)
    assert message_problems(shown, expected) == []


@pytest.mark.parametrize("code", NON_ENGLISH)
def test_sc_l10n_ui_017_1_the_frame_and_the_reason_are_finished_in_the_seven(code):
    """SC-L10N-UI-017-1: neither message is ``unfinished`` or English in the seven.

    The reading is the oracle's own (one entry per message, in its context, finished,
    with a text); on top of it the reason's translation is not its English source and
    the frame still carries its placeholder once.
    """
    expected = expected_for(code)
    assert expected.reason != REASON_SOURCE, f"{code}: the reason is its English source"
    assert REASON_SOURCE not in expected.message
    assert expected.frame != FRAME_SOURCE, f"{code}: the frame is its English source"


def test_sc_l10n_ui_017_1_the_english_start_entry_is_the_one_chosen(bench):
    """SC-L10N-UI-017-1: the action the rows trigger is the menu's Start Real-time."""
    assert bench.start_action.text().replace("&", "") == START_LABEL
    shown, expected = start_in(bench, FALLBACK_LANGUAGE)
    assert shown == "Real-time: no real-time transport configured"
    assert message_problems(shown, expected) == []


def test_sc_l10n_ui_017_1_the_languages_examined_are_printed(bench, capsys):
    """SC-L10N-UI-017-1: the run says how many of the eight languages it examined.

    Every language is examined in one window, one live switch after another, and the
    count is read from what was examined, never from a constant.
    """
    examined: List[str] = []
    for code in LANGUAGES:
        shown, expected = start_in(bench, code)
        assert message_problems(shown, expected) == []
        examined.append(code)
    line = (
        f"languages examined: {len(examined)} of {EXPECTED_LANGUAGE_COUNT} {examined}; "
        f"the reason {REASON_SOURCE!r} in the frame {FRAME_SOURCE!r}"
    )
    print(line)
    with capsys.disabled():
        print(f"[real-time message] {line}")
    assert len(examined) == EXPECTED_LANGUAGE_COUNT == 8
    assert examined == list(LANGUAGES)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-017-2: after a live switch                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("first", "second"),
    [("en", "ja"), ("ja", "de"), ("de", "en")],
)
def test_sc_l10n_ui_017_2_the_next_message_after_a_switch_is_in_the_new_language(
    bench, first, second
):
    """SC-L10N-UI-017-2: select the new language, choose Start, read the new language.

    The first pair is the scenario's own: English, then 日本語 chosen from the
    Language menu by its name. The other two switch between non-English languages and
    back to English, so a reason kept from an earlier message cannot pass: the second
    message is the second language's and never the first's.
    """
    before, before_expected = start_in(bench, first)
    assert message_problems(before, before_expected) == []
    if second == "ja":
        assert bench.languages["ja"].text() == JAPANESE_NAME
    after, after_expected = start_in(bench, second)
    assert message_problems(after, after_expected) == []
    assert after != before, f"the message did not change with the switch: {after!r}"
    assert before_expected.reason not in after, (
        f"the reason of {first!r} is still shown after the switch to {second!r}: "
        f"{after!r}"
    )


# --------------------------------------------------------------------------- #
# Controls: the rows can fail                                                 #
# --------------------------------------------------------------------------- #


def test_the_verdict_accepts_the_catalogue_message_and_rejects_each_fault():
    """Control: ``message_problems`` decides literal status bar texts correctly."""
    ja = Expected(
        "ja", "リアルタイム: {msg}", "リアルタイムの通信手段が設定されていません"
    )
    en = Expected("en", FRAME_SOURCE, REASON_SOURCE)
    assert message_problems(ja.message, ja) == []
    assert message_problems("Real-time: no real-time transport configured", en) == []
    english_reason = ja.frame.replace(PLACEHOLDER, REASON_SOURCE)
    assert any("English reason" in p for p in message_problems(english_reason, ja))
    assert message_problems(ja.message + " ", ja), "a trailing space passed"
    assert message_problems(ja.message[:-1], ja), "a truncated text passed"
    failure_only = "Real-time. " + REASON_SOURCE
    assert message_problems(failure_only, en), "the failure-only frame passed"
    assert message_problems("", ja), "an empty status bar passed"
    assert message_problems(en.message, ja), "the English message passed in ja"


def test_the_oracle_refuses_an_unfinished_entry(tmp_path):
    """Control: a catalogue whose reason is ``unfinished`` is refused, and named.

    A scratch copy of the Japanese catalogue is written under ``tmp_path`` with the
    reason's translation marked unfinished (and a second with it emptied); the
    shipped file is never written.
    """
    source = _default_translations_dir() / "pixelart_ja.ts"
    text = source.read_text(encoding="utf-8")
    reason = "リアルタイムの通信手段が設定されていません"
    good = f"<translation>{reason}</translation>"
    assert text.count(good) == 1, "the Japanese reason's entry was not found once"
    copies = {
        "unfinished": f'<translation type="unfinished">{reason}</translation>',
        "empty": '<translation type="unfinished"></translation>',
    }
    for name, replacement in copies.items():
        folder = tmp_path / name
        folder.mkdir()
        (folder / "pixelart_ja.ts").write_text(
            text.replace(good, replacement), encoding="utf-8"
        )
        with pytest.raises(AssertionError, match="unfinished|no text"):
            expected_for("ja", folder)
    expected_for("ja")  # the shipped catalogue still passes


def test_a_reason_shown_untranslated_is_caught(bench, monkeypatch):
    """Control: the worker's reason shown as its English source fails the verdict.

    The planted ``tr`` returns the source, which is what the audit measured before
    the reason was translatable: a Japanese frame around the English reason.
    """
    monkeypatch.setattr(Realtime_Client, "tr", lambda self, text, *args, **kwargs: text)
    expected = expected_for("ja")
    bench.select("ja")
    shown, args = bench.start()
    assert shown == expected.frame.replace(PLACEHOLDER, REASON_SOURCE), shown
    problems = message_problems(shown, expected)
    assert problems, "an English reason in a Japanese status bar passed"
    assert any("English reason" in p for p in problems), problems


def test_a_reason_kept_from_the_first_message_is_caught(bench, monkeypatch):
    """Control: a reason cached by an earlier message fails the switch row.

    The planted ``tr`` keeps the first answer for each text, as a reason translated at
    construction would; the first message is English, so the one after the switch to
    Japanese still carries the English reason.
    """
    kept: Dict[str, str] = {}

    def caching(self: Realtime_Client, text: str, *args: Any, **kwargs: Any) -> str:
        if text not in kept:
            kept[text] = QCoreApplication.translate(
                "Realtime_Client", text, *args, **kwargs
            )
        return kept[text]

    monkeypatch.setattr(Realtime_Client, "tr", caching)
    first, first_expected = start_in_unchecked(bench, "en")
    assert message_problems(first, first_expected) == []
    second, second_expected = start_in_unchecked(bench, "ja")
    problems = message_problems(second, second_expected)
    assert problems, "a reason kept from the English message passed after the switch"
    assert REASON_SOURCE in second, second


def start_in_unchecked(bench: Bench, code: str) -> Tuple[str, Expected]:
    """Like ``start_in``, without comparing the signal's reason (for the controls)."""
    expected = expected_for(code)
    bench.select(code)
    shown, _args = bench.start()
    return shown, expected
