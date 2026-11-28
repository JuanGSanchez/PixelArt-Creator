"""The unsaved-changes prompt's buttons, in the app's language, on every platform.

REQ-L10N-UI-005: what Qt supplies on its own is shown in the active language. The
prompt a dropped project raises over an unsaved document (Save / Discard / Cancel)
is built from Qt's standard buttons, whose words Qt takes from the platform theme:
the same three buttons read differently on Windows, on macOS and on a GNOME
desktop. The application sets the three words itself, from its own catalogue
(context ``Main_Window``), so every platform shows the same words, in the language
chosen, and the user guide can quote them.

What each row asserts is read from the box the user sees, opened by the real
drop handler of the real window:

* the box has exactly three buttons, one per role (accept, destructive, reject),
  and each shows the catalogue's word for its action;
* with a translator planted for context ``QPlatformTheme`` (where Qt looks the
  theme's words up) that turns "Save", "Discard" and "Cancel" into a marker, no
  button shows the marker. A control shows the planted translator does reach a
  plain Qt box with standard buttons, so the row can fail;
* Save is the default (Enter), Escape is Cancel;
* the three outcomes: Save saves, then opens the dropped project; Discard opens it
  without saving; Cancel leaves everything as it was.

The words expected come from the requirement, never from the code under test. For
English they are the three words the user guide quotes. For any other language
they are read from that language's own ``.ts`` file, finished entries only.
All eight languages are examined, each row against that language's own catalogue
(an entry missing or ``unfinished`` fails the row), and the line printed says how
many of the eight were examined.

The box is found while the handler blocks in its modal loop, by a timer that reads
it and answers it, so the rows hold whether the handler uses a static
``QMessageBox`` call or builds the box itself. A watchdog closes a box that an
answer did not dismiss, so a failing row fails and does not hang.

Stated limit: the offscreen platform has no native alert. On macOS a message box
is a native ``NSAlert`` by default, whose Discard-role button reads "Don't Save"
from the platform theme, and on a GNOME desktop that button reads "Close without
Saving"; neither theme exists here, so what a button shows on those platforms is
not observed by any row. What is asserted is the necessary condition: the words
of the buttons come from the application, and a planted theme word never reaches
them. Both themes (light and dark), offscreen.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple

import pytest
from PySide6.QtCore import QMimeData, QObject, QPointF, Qt, QTimer, QTranslator, QUrl
from PySide6.QtGui import QDropEvent, QUndoCommand
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from pixelart_creator.data.project_io import FILE_SUFFIX
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.main_window import Main_Window

Role = QMessageBox.ButtonRole

# --------------------------------------------------------------------------- #
# The oracle                                                                  #
# --------------------------------------------------------------------------- #

#: The number of languages the finished product ships (English included).
EXPECTED_LANGUAGE_COUNT = 8

#: The languages examined: all eight. Each one's catalogue must hold the three
#: messages as finished entries, or its rows fail.
LANGUAGES_UNDER_TEST: Tuple[str, ...] = (
    FALLBACK_LANGUAGE,
    "es",
    "fr",
    "de",
    "ru",
    "zh_CN",
    "ko",
    "ja",
)

#: The context the three messages belong to, in the catalogue.
CATALOGUE_CONTEXT = "Main_Window"

#: The context Qt looks a standard button's word up in (the platform theme's
#: defaults), and the marker the planted translator answers with.
THEME_CONTEXT = "QPlatformTheme"
THEME_MARKER = "ZQX theme marker"

#: The three actions: the English source message each one is, and the role its
#: button must have. The roles are the requirement's own (the prompt's save is the
#: accepting action, discard the destructive one, cancel the rejecting one).
ACTIONS: Dict[str, Tuple[str, Role]] = {
    "save": ("Save", Role.AcceptRole),
    "discard": ("Discard", Role.DestructiveRole),
    "cancel": ("Cancel", Role.RejectRole),
}


def _catalogue_text(code: str, source: str) -> str:
    """Return the text the interface shows for ``source`` in language ``code``.

    English has no translation and shows its source. Any other language is read
    from its own ``.ts``: exactly one entry in the context, finished, with a text.
    """
    if code == FALLBACK_LANGUAGE:
        return source
    path = _default_translations_dir() / f"pixelart_{code}.ts"
    root = ET.parse(path).getroot()
    found = [
        message
        for scope in root.iter("context")
        if scope.findtext("name") == CATALOGUE_CONTEXT
        for message in scope.iter("message")
        if message.findtext("source") == source
    ]
    assert len(found) == 1, f"{path.name}: {len(found)} entries for {source!r}"
    translation = found[0].find("translation")
    assert translation is not None and translation.text, f"{path.name}: no text"
    assert translation.get("type") != "unfinished", f"{path.name}: unfinished"
    return translation.text


def expected_texts(code: str) -> Dict[str, str]:
    """Return, per action, the text its button must show in language ``code``."""
    return {
        name: _catalogue_text(code, source) for name, (source, _) in ACTIONS.items()
    }


# --------------------------------------------------------------------------- #
# Reading and answering the box                                               #
# --------------------------------------------------------------------------- #


@dataclass
class Prompt:
    """What a message box showed the moment it was opened."""

    title: str
    text: str
    buttons: List[Tuple[str, Role]]
    default: Optional[str]


def _open_boxes() -> List[QMessageBox]:
    """Return the message boxes that are on screen now."""
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if isinstance(widget, QMessageBox) and widget.isVisible()
    ]


def read_box(box: QMessageBox) -> Prompt:
    """Read a box as the user sees it: its words, each button's text and role."""
    default = box.defaultButton()
    return Prompt(
        title=box.windowTitle(),
        text=box.text(),
        buttons=[(button.text(), box.buttonRole(button)) for button in box.buttons()],
        default=default.text() if default is not None else None,
    )


def prompt_problems(prompt: Prompt, expected: Dict[str, str]) -> List[str]:
    """Return what is wrong with ``prompt`` against the expected button texts.

    The verdict function of every row about the words: it holds one button per
    role, each showing the expected text, and nothing else. An empty list is a
    pass. It is a pure function, so the controls decide it on literals.
    """
    problems: List[str] = []
    if len(prompt.buttons) != len(ACTIONS):
        problems.append(f"{len(prompt.buttons)} buttons, not {len(ACTIONS)}")
    for name, (_, role) in ACTIONS.items():
        shown = [text for text, found in prompt.buttons if found == role]
        if shown != [expected[name]]:
            problems.append(
                f"the {name} button (role {role.name}) shows {shown!r}, "
                f"not [{expected[name]!r}]"
            )
    for text, _ in prompt.buttons:
        if THEME_MARKER in text:
            problems.append(f"a button shows the platform theme's word: {text!r}")
    return problems


class _PromptDriver(QObject):
    """Find the box a handler opens, read it, answer it, and never hang.

    A timer polls for a box that is on screen and not yet answered; the first one
    is read, then ``respond`` is called with it. A box that stays on screen
    after its answer is closed by a watchdog, and ``stuck`` says so.
    """

    POLL_MS = 5
    WATCHDOG_MS = 8000

    def __init__(self, respond: Callable[[QMessageBox], None]) -> None:
        super().__init__()
        self._respond = respond
        self.prompts: List[Prompt] = []
        self.error: Optional[BaseException] = None
        self.stuck = False
        self._answered: List[QMessageBox] = []
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._started = 0.0

    def start(self) -> None:
        self._started = time.monotonic()
        self._poll_timer.start()

    def stop(self) -> None:
        self._poll_timer.stop()

    def _poll(self) -> None:
        boxes = _open_boxes()
        fresh = [b for b in boxes if not any(b is done for done in self._answered)]
        if fresh:
            box = fresh[0]
            self._answered.append(box)
            try:
                self.prompts.append(read_box(box))
                self._respond(box)
            except BaseException as exc:  # carried out of the Qt loop, then raised
                self.error = exc
                box.done(int(QMessageBox.StandardButton.Cancel))
            return
        if boxes and (time.monotonic() - self._started) * 1000 > self.WATCHDOG_MS:
            self.stuck = True
            for box in boxes:
                box.done(int(QMessageBox.StandardButton.Cancel))


@contextmanager
def answering(respond: Callable[[QMessageBox], None]) -> Iterator[_PromptDriver]:
    """Answer every box the body opens with ``respond``; check it afterwards."""
    driver = _PromptDriver(respond)
    driver.start()
    try:
        yield driver
    finally:
        driver.stop()
    if driver.error is not None:
        raise driver.error
    assert not driver.stuck, "a box stayed on screen after it was answered"


def click(role: Role) -> Callable[[QMessageBox], None]:
    """Answer a box by pressing its one button of ``role``."""

    def respond(box: QMessageBox) -> None:
        found = [b for b in box.buttons() if box.buttonRole(b) == role]
        assert len(found) == 1, f"{len(found)} buttons of role {role.name}"
        found[0].click()

    return respond


def press(key: Qt.Key) -> Callable[[QMessageBox], None]:
    """Answer a box by pressing a key on it."""

    def respond(box: QMessageBox) -> None:
        QTest.keyClick(box, key)

    return respond


# --------------------------------------------------------------------------- #
# The planted platform theme text                                             #
# --------------------------------------------------------------------------- #


class _ThemeMarkerTranslator(QTranslator):
    """Answer the platform theme's three words with a marker, nothing else."""

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: Optional[str] = None,
        n: int = -1,
    ) -> Optional[str]:
        if context == THEME_CONTEXT and source_text in {
            source for source, _ in ACTIONS.values()
        }:
            return THEME_MARKER
        return None


@pytest.fixture
def theme_words_planted(qapp) -> Iterator[None]:
    """Install the planted translator for the test; remove it afterwards."""
    translator = _ThemeMarkerTranslator()
    assert qapp.installTranslator(translator)
    try:
        yield
    finally:
        qapp.removeTranslator(translator)


# --------------------------------------------------------------------------- #
# The window under test                                                       #
# --------------------------------------------------------------------------- #


@pytest.fixture(params=["as the platform has them", "planted"])
def theme_words(request, qapp) -> Iterator[str]:
    """Run a row with the platform's own theme words, then with them planted.

    The first variant is whatever the host platform supplies; on a host whose
    theme words already equal the catalogue's it cannot tell the two sources
    apart, which is why every row also runs with the three theme words replaced
    by a marker: the one variant in which they can never agree.
    """
    if request.param != "planted":
        yield request.param
        return
    translator = _ThemeMarkerTranslator()
    assert qapp.installTranslator(translator)
    try:
        yield request.param
    finally:
        qapp.removeTranslator(translator)


@pytest.fixture(params=LANGUAGES_UNDER_TEST)
def code(request, qapp) -> Iterator[str]:
    """Install the language through the app's own manager; restore English after."""
    manager = LanguageManager(qapp)
    assert manager.set_language(request.param) is True, f"{request.param!r}"
    try:
        yield request.param
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


@dataclass
class Scene:
    """A window with an unsaved document and a project waiting to be dropped."""

    window: Main_Window
    project: Path
    save_target: Path
    kept: object
    tab_count: int
    save_dialog_calls: List[int]

    def drop(self) -> None:
        """Deliver the project as a file drop onto the window."""
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.project))])
        event = QDropEvent(
            QPointF(10, 10),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.window.dropEvent(event)
        del event  # the event borrows the mime; release it first

    def replaced(self) -> bool:
        """Whether the dropped project took the place of the unsaved document."""
        return (
            self.window.active_document() is not None
            and self.window.active_document() is not self.kept
            and self.window._tab_widget.count() == self.tab_count
        )

    def untouched(self) -> bool:
        """Whether the unsaved document is still the one on screen."""
        return (
            self.window.active_document() is self.kept
            and self.window._tab_widget.count() == self.tab_count
        )


@pytest.fixture
def scene(code, theme_words, qtbot, tmp_path, monkeypatch) -> Scene:
    """A window whose document has unsaved changes, and a project to drop on it."""
    window = Main_Window()
    qtbot.addWidget(window)
    project = tmp_path / f"dropped{FILE_SUFFIX}"
    window.save_document(str(project))  # the file the user drops
    tab = window.active_tab()
    assert tab is not None, "the window has no open document"
    tab.stack.push(QUndoCommand("edit"))  # unsaved changes now
    assert not tab.stack.isClean()
    save_target = tmp_path / f"saved{FILE_SUFFIX}"
    calls: List[int] = []

    def save_dialog(*args, **kwargs):
        calls.append(1)
        return str(save_target), ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", save_dialog)
    return Scene(
        window=window,
        project=project,
        save_target=save_target,
        kept=window.active_document(),
        tab_count=window._tab_widget.count(),
        save_dialog_calls=calls,
    )


# --------------------------------------------------------------------------- #
# The words, the roles                                                        #
# --------------------------------------------------------------------------- #


def test_the_prompt_opens_once_for_an_unsaved_document(scene, code):
    """REQ-L10N-UI-005: a dropped project over unsaved changes opens one prompt."""
    with answering(click(Role.RejectRole)) as driver:
        scene.drop()
    assert len(driver.prompts) == 1, f"{len(driver.prompts)} prompts were opened"


@pytest.mark.parametrize("action", list(ACTIONS))
def test_each_button_shows_the_catalogue_text_in_its_role(scene, code, action):
    """REQ-L10N-UI-005: one button per role, showing the catalogue's word."""
    expected = expected_texts(code)
    _, role = ACTIONS[action]
    with answering(click(Role.RejectRole)) as driver:
        scene.drop()
    assert driver.prompts, "no prompt was opened"
    shown = [text for text, found in driver.prompts[0].buttons if found == role]
    assert shown == [expected[action]], (
        f"language {code!r}: the {action} button (role {role.name}) shows "
        f"{shown!r}, the catalogue holds {expected[action]!r}"
    )


def test_the_prompt_has_exactly_three_buttons(scene, code):
    """REQ-L10N-UI-005: Save, Discard and Cancel, and no other button."""
    with answering(click(Role.RejectRole)) as driver:
        scene.drop()
    assert driver.prompts, "no prompt was opened"
    problems = prompt_problems(driver.prompts[0], expected_texts(code))
    assert not problems, "; ".join(problems)


def test_no_button_shows_the_platform_themes_word(scene, code, theme_words):
    """REQ-L10N-UI-005: a planted theme word never reaches the prompt's buttons.

    In the planted variant the translator answers the platform theme's context
    with a marker. The prompt's three buttons must still show the catalogue's
    words, wherever the platform would have supplied its own.
    """
    expected = expected_texts(code)
    with answering(click(Role.RejectRole)) as driver:
        scene.drop()
    assert driver.prompts, "no prompt was opened"
    prompt = driver.prompts[0]
    marked = [text for text, _ in prompt.buttons if THEME_MARKER in text]
    assert marked == [], f"a button shows the platform theme's word: {marked!r}"
    problems = prompt_problems(prompt, expected)
    assert not problems, "; ".join(problems)


# --------------------------------------------------------------------------- #
# The default, Escape, and the three outcomes                                 #
# --------------------------------------------------------------------------- #


def test_save_is_the_default_button(scene, code):
    """REQ-L10N-UI-005: the default button is the accepting one, Save."""
    with answering(click(Role.RejectRole)) as driver:
        scene.drop()
    assert driver.prompts, "no prompt was opened"
    assert driver.prompts[0].default == expected_texts(code)["save"]


def test_enter_answers_with_save(scene, code):
    """REQ-L10N-UI-005: Enter on the box saves, then opens the dropped project."""
    with answering(press(Qt.Key.Key_Return)):
        scene.drop()
    assert scene.save_dialog_calls == [1], "Enter did not ask where to save"
    assert scene.save_target.exists(), "Enter did not save the document"
    assert scene.replaced(), "the dropped project was not opened after saving"


def test_escape_answers_with_cancel(scene, code):
    """REQ-L10N-UI-005: Escape on the box cancels; nothing changes."""
    with answering(press(Qt.Key.Key_Escape)):
        scene.drop()
    assert scene.save_dialog_calls == [], "Escape asked where to save"
    assert not scene.save_target.exists(), "Escape saved the document"
    assert scene.untouched(), "Escape changed the open document or the tabs"


def test_save_saves_then_opens_the_dropped_project(scene, code):
    """REQ-L10N-UI-005: the Save button saves the document, then opens the drop."""
    with answering(click(Role.AcceptRole)):
        scene.drop()
    assert scene.save_dialog_calls == [1]
    assert scene.save_target.exists(), "Save did not write the document"
    assert scene.replaced(), "the dropped project was not opened after saving"


def test_discard_opens_the_dropped_project_without_saving(scene, code):
    """REQ-L10N-UI-005: the Discard button opens the drop and saves nothing."""
    with answering(click(Role.DestructiveRole)):
        scene.drop()
    assert scene.save_dialog_calls == [], "Discard asked where to save"
    assert not scene.save_target.exists(), "Discard saved the document"
    assert scene.replaced(), "the dropped project was not opened"


def test_cancel_changes_nothing(scene, code):
    """REQ-L10N-UI-005: the Cancel button leaves the document and tabs as they were."""
    with answering(click(Role.RejectRole)):
        scene.drop()
    assert scene.save_dialog_calls == [], "Cancel asked where to save"
    assert not scene.save_target.exists(), "Cancel saved the document"
    assert scene.untouched(), "Cancel changed the open document or the tabs"


# --------------------------------------------------------------------------- #
# Controls: the rows can fail                                                 #
# --------------------------------------------------------------------------- #


def _box_with_standard_buttons() -> QMessageBox:
    """Return a box built the way Qt builds one from its own standard buttons."""
    box = QMessageBox(
        QMessageBox.Icon.Warning,
        "Unsaved Changes",
        "text",
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel,
    )
    return box


def test_a_plain_qt_box_shows_the_planted_theme_word(qtbot, theme_words_planted):
    """Control: the planted translator reaches a box built from standard buttons.

    This is what the prompt showed before it took its words from the catalogue,
    and the reason the row about the theme's word can fail at all.
    """
    box = _box_with_standard_buttons()
    qtbot.addWidget(box)
    prompt = read_box(box)
    assert [text for text, _ in prompt.buttons] == [THEME_MARKER] * 3, prompt.buttons


def test_a_plain_qt_box_shows_qts_own_words_without_the_plant(qtbot):
    """Control: with nothing planted, a standard box shows no marker.

    Qt's own words are the platform's, so this only pins that the marker comes
    from the plant and from nothing else.
    """
    box = _box_with_standard_buttons()
    qtbot.addWidget(box)
    assert all(THEME_MARKER not in text for text, _ in read_box(box).buttons)


def test_the_verdict_accepts_the_catalogue_words_and_rejects_anything_else():
    """Control: the verdict function decides literal prompts correctly."""
    words = {"save": "Save", "discard": "Discard", "cancel": "Cancel"}
    good = [
        ("Save", Role.AcceptRole),
        ("Discard", Role.DestructiveRole),
        ("Cancel", Role.RejectRole),
    ]

    def verdict(buttons) -> List[str]:
        return prompt_problems(Prompt("t", "x", list(buttons), None), words)

    assert verdict(good) == []
    assert verdict([(THEME_MARKER, Role.AcceptRole)] + good[1:])  # theme word
    assert verdict([("Close without Saving", Role.DestructiveRole)] + good[:1])
    assert verdict([("Save", Role.DestructiveRole)] + good[1:]) != []  # wrong role
    assert verdict(good + [("Help", Role.HelpRole)])  # a fourth button
    assert verdict(good[:2])  # a missing button
    assert verdict([("Don't Save", Role.DestructiveRole)] + good[:1] + good[2:])


def test_the_driver_closes_a_box_that_its_answer_did_not_dismiss(qtbot):
    """Control: a box an answer leaves open is closed, and the row fails."""
    box = _box_with_standard_buttons()
    qtbot.addWidget(box)
    driver = _PromptDriver(lambda shown: None)  # an answer that does nothing
    driver.WATCHDOG_MS = 100
    driver.start()
    try:
        box.exec()
    finally:
        driver.stop()
    assert driver.stuck, "the watchdog did not notice the open box"
    assert not box.isVisible()


def test_the_languages_examined_are_printed(capsys):
    """REQ-L10N-UI-005: say how many of the eight languages these rows examined.

    Every language the product ships is examined: the count is 8 and the set is
    exactly the eight, so a language dropped from the rows fails here.
    """
    known = {"en", "fr", "de", "es", "ru", "ja", "ko", "zh_CN"}
    assert len(known) == EXPECTED_LANGUAGE_COUNT
    assert len(set(LANGUAGES_UNDER_TEST)) == len(LANGUAGES_UNDER_TEST)
    assert set(LANGUAGES_UNDER_TEST) == known, LANGUAGES_UNDER_TEST
    assert len(LANGUAGES_UNDER_TEST) == EXPECTED_LANGUAGE_COUNT == 8
    line = (
        f"languages examined: {len(LANGUAGES_UNDER_TEST)} of "
        f"{EXPECTED_LANGUAGE_COUNT} {list(LANGUAGES_UNDER_TEST)}"
    )
    print(line)
    with capsys.disabled():
        print(f"[unsaved prompt] {line}")
