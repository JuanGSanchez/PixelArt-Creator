"""The user guide in eight languages, as the user meets it in the guide window.

What is covered, by scenario id (the six-interface-languages feature):

* **SC-L10N-UI-007-1** a Japanese content tree holds every topic except
  "Layers": with Japanese active, opening "Layers" shows the English page and
  no "Could not load this topic" text, and every other topic is shown in
  Japanese;
* **SC-L10N-UI-007-2** a Spanish content tree that lacks one topic gets the same
  per-topic fallback: the English page, no error, and the other topics Spanish;
* **SC-L10N-UI-008-1** with Korean active, every section and topic title in the
  table of contents is its recorded Korean title (the file the titles are
  recorded in is named, and the number of titles examined is printed and is
  non-zero);
* **SC-L10N-UI-008-2** with French active, searching the guide for the French
  title word of the Layers topic finds Layers, and so does the English keyword
  "layer";
* **SC-L10N-UI-001-3** a guide window open on a topic with English active shows
  that topic from the German content after the language is switched to Deutsch,
  in the same window, and from the English content again after the switch back.

Every window is the application's own ``Main_Window`` opened to its own guide
entry, and every language is chosen through the real Language-menu entry, so the
locale the guide follows is the one the application holds. The two fallback
scenarios run over fixture trees built under the test's temporary directory and
swapped in for the bundle root; the committed content bundle is only read, never
written.

The expected values do not come from the code under test. The titles a language
records are read as JSON straight from ``manifest.json`` and
``content/<language>/meta.json``, and the heading a page must show is the first
line of the Markdown file of that language, read from the file system.

Instruments and their controls. A check that reports "nothing wrong" is only
worth something if it would have reported a failure, so each one is shown
failing:

* the "no load error" assertions of the two fallback scenarios against a tree in
  which the page is missing from English too, where the error sentence must
  appear (in the active language or in English);
* the Korean table of contents against the English one, which must differ from
  the Korean record;
* the French word against English, where it must find nothing, so that finding
  Layers under French is the French metadata's doing;
* the German re-render against the heading the same window showed before the
  switch, which must be the English one and not the German one.

Both modes. The window restores the stored mode at construction and ignores the
suite's own, so the mode under test is planted in the store and read back from
the window (``open_window`` asserts it).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication

import pixelart_creator
from pixelart_creator.data import guide_content
from pixelart_creator.ui import app_font, i18n
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import (
    DEFAULT_STYLE,
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
)
from pixelart_creator.ui.user_guide import User_Guide_Dialog
from testing.suites.ui.conftest import assert_settings_isolated
from testing.suites.ui.test_app_font import choose_language, open_guide, open_window

#: The committed content bundle, located from the package, read and never written.
BUNDLE: Path = Path(pixelart_creator.__file__).resolve().parent / "userguide_content"

#: The Qt translation context of the guide window's own texts, and the source text
#: of the sentence it puts in front of a content-load failure.
GUIDE_CONTEXT = "User_Guide_Dialog"
LOAD_ERROR_SOURCE = "Could not load this topic:\n\n%1"

#: The French word of the Layers topic's title that the scenario searches for.
FRENCH_LAYERS_WORD = "calques"

#: One section of a table of contents as read from the window: its title, and the
#: titles of its topics in order.
Row = Tuple[str, List[str]]


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def theme(qapp) -> str:
    """Replace the suite's two-way ``theme`` fixture with one known starting sheet.

    A ``Main_Window`` restores the *stored* combination and ignores this one; the
    modes under test are parametrised below (``mode``) and planted in the store
    instead.
    """
    apply_theme(qapp, THEME_LIGHT, DEFAULT_STYLE)
    return THEME_LIGHT


@pytest.fixture(autouse=True)
def _store_is_isolated(settings_store: Path) -> Path:
    """Fail BEFORE any write if the settings store is not the temporary one."""
    assert_settings_isolated(settings_store)
    return settings_store


@pytest.fixture(autouse=True)
def _leave_the_font_as_found(qapp) -> Iterator[None]:
    """Put the application font back after the test, whatever the test did to it."""
    yield
    qapp.setFont(app_font._target_font(False))


@pytest.fixture(params=[THEME_LIGHT, THEME_DARK])
def mode(request: pytest.FixtureRequest) -> str:
    """Light, then Dark: the mode planted in the store and read back from the window."""
    chosen: str = request.param
    return chosen


@pytest.fixture
def open_main(qtbot, mode: str) -> Iterator[Callable[[], Main_Window]]:
    """Return a function that opens an English main window in the mode under test.

    Every window it opened is put back to English when the test ends, so no
    catalogue is left installed for the next test.
    """
    windows: List[Main_Window] = []

    def _open() -> Main_Window:
        window = open_window(qtbot, mode)
        windows.append(window)
        assert i18n.current_ui_language() == "en", "the window did not start in English"
        return window

    yield _open
    for window in windows:
        if shiboken6.isValid(window):
            window._language_manager.set_language("en")


# --------------------------------------------------------------------------- #
# Reading the records                                                          #
# --------------------------------------------------------------------------- #


def say(capsys: pytest.CaptureFixture[str], text: str) -> None:
    """Print a line that reaches the terminal even without ``-s``.

    A line the stream's encoding cannot hold is written with the character it
    cannot hold escaped, never dropped and never written twice.
    """
    line = f"\n[guide] {text}"
    with capsys.disabled():
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", None) or "ascii"
            print(
                line.encode(encoding, "backslashreplace").decode(encoding), flush=True
            )


def read_json(path: Path) -> Dict[str, Any]:
    """Read ``path`` as UTF-8 JSON, straight from the file system."""
    data = json.loads(path.read_bytes().decode("utf-8"))
    assert isinstance(data, dict), f"{path} is not a JSON object"
    return data


def manifest() -> Dict[str, Any]:
    """The English manifest of the committed bundle."""
    return read_json(BUNDLE / "manifest.json")


def topic_stems() -> List[str]:
    """The content stem of every topic of the manifest, in order."""
    return [
        str(topic["content"])
        for section in manifest()["sections"]
        for topic in section["topics"]
    ]


def recorded_toc(language: str) -> Tuple[List[Row], Path]:
    """Return the table of contents ``language`` records, and the file it is in.

    English is recorded in the manifest, every other language in its own
    ``meta.json``. A title the record lacks fails here, naming it: a window that
    fell back to English for it could otherwise never be told from one that read
    the record.
    """
    source = manifest()
    if language == "en":
        rows = [
            (
                str(section["title"]),
                [str(topic["title"]) for topic in section["topics"]],
            )
            for section in source["sections"]
        ]
        return rows, BUNDLE / "manifest.json"
    path = BUNDLE / "content" / language / "meta.json"
    meta = read_json(path)
    rows = []
    for section in source["sections"]:
        sections = meta["sections"]
        assert section["id"] in sections, f"{path} records no title for {section['id']}"
        topics: List[str] = []
        for topic in section["topics"]:
            assert (
                topic["id"] in meta["topics"]
            ), f"{path} records no title for {topic['id']}"
            topics.append(str(meta["topics"][topic["id"]]["title"]))
        rows.append((str(sections[section["id"]]["title"]), topics))
    return rows, path


def recorded_topic_title(language: str, topic_id: str) -> Tuple[str, Path]:
    """Return the title ``language`` records for one topic, and the file it is in."""
    path = BUNDLE / "content" / language / "meta.json"
    topics = read_json(path)["topics"]
    assert topic_id in topics, f"{path} records no title for {topic_id}"
    return str(topics[topic_id]["title"]), path


def page_heading(language: str, stem: str) -> str:
    """The first-level heading of ``content/<language>/<stem>.md``, from the file."""
    path = BUNDLE / "content" / language / f"{stem}.md"
    first = path.read_bytes().decode("utf-8").splitlines()[0]
    assert first.startswith("# "), f"{path} does not start with a first-level heading"
    heading = first[2:].strip()
    assert (
        heading and "*" not in heading and "`" not in heading
    ), f"{path}: the heading carries markup, so its text is not what the pane shows"
    return heading


# --------------------------------------------------------------------------- #
# Reading the window                                                           #
# --------------------------------------------------------------------------- #


def toc_rows(dialog: User_Guide_Dialog) -> List[Row]:
    """The table of contents the window shows: each section and its topics."""
    tree = dialog._toc_tree
    rows: List[Row] = []
    for index in range(tree.topLevelItemCount()):
        section = tree.topLevelItem(index)
        assert section is not None
        rows.append(
            (
                section.text(0),
                [section.child(child).text(0) for child in range(section.childCount())],
            )
        )
    return rows


def shown_heading(dialog: User_Guide_Dialog) -> str:
    """The text of the first first-level heading the page pane shows."""
    block = dialog._content_view.document().begin()
    while block.isValid():
        if block.blockFormat().headingLevel() == 1:
            return str(block.text())
        block = block.next()
    return ""


def result_ids(dialog: User_Guide_Dialog) -> List[str]:
    """The topic ids of the search results the window lists."""
    results = dialog._results_list
    return [
        str(results.item(row).data(Qt.ItemDataRole.UserRole))
        for row in range(results.count())
    ]


def load_error_frames() -> Tuple[str, str]:
    """The sentence in front of a load failure, in English and as installed now."""
    english = LOAD_ERROR_SOURCE.split("%1")[0].strip()
    installed = (
        QCoreApplication.translate(GUIDE_CONTEXT, LOAD_ERROR_SOURCE)
        .split("%1")[0]
        .strip()
    )
    assert (
        english and installed
    ), "the load-error sentence is empty, so it proves nothing"
    return english, installed


def open_the_guide(win: Main_Window, qtbot) -> User_Guide_Dialog:
    """Open the guide from the window's own entry point, shown and settled."""
    win._on_user_guide()
    dialog = win._user_guide_dialog
    assert isinstance(dialog, User_Guide_Dialog)
    dialog.resize(900, 700)
    dialog.show()
    qtbot.waitExposed(dialog)
    QApplication.processEvents()
    return dialog


# --------------------------------------------------------------------------- #
# Fixture trees                                                                #
# --------------------------------------------------------------------------- #


def build_tree(
    root: Path,
    language: str,
    *,
    language_lacks: Optional[str] = None,
    english_lacks: Optional[str] = None,
) -> List[str]:
    """Build a content bundle under ``root`` holding English and ``language``.

    The manifest and the language's ``meta.json`` are byte copies of the committed
    ones. Every topic gets a one-line page per language, tagged so a page can be
    told from its other-language twin. ``language_lacks`` leaves one topic out of
    the language's folder, ``english_lacks`` one out of the English folder.
    Returns the content stems of the topics, in order.
    """
    stems = topic_stems()
    root.mkdir(parents=True)
    (root / "manifest.json").write_bytes((BUNDLE / "manifest.json").read_bytes())
    for code, lacks in (("en", english_lacks), (language, language_lacks)):
        folder = root / "content" / code
        folder.mkdir(parents=True)
        for stem in stems:
            if stem == lacks:
                continue
            text = f"# Page {stem}\n\nBODY-{code}-{stem}\n"
            (folder / f"{stem}.md").write_bytes(text.encode("utf-8"))
    meta = BUNDLE / "content" / language / "meta.json"
    (root / "content" / language / "meta.json").write_bytes(meta.read_bytes())
    return stems


def use_tree(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Make the guide's reader take ``root`` for the bundle, for this test only."""
    monkeypatch.setattr(guide_content, "bundle_root", lambda: root)


def open_topic(dialog: User_Guide_Dialog, topic_id: str) -> str:
    """Select ``topic_id`` in the table of contents as a click does; return the page."""
    dialog._toc_tree.setCurrentItem(dialog._toc_items[topic_id])
    QApplication.processEvents()
    assert dialog.current_topic_id() == topic_id
    return str(dialog._content_view.toPlainText())


def check_per_topic_fallback(
    win: Main_Window,
    qtbot,
    capsys: pytest.CaptureFixture[str],
    stems: List[str],
    language: str,
    missing: str,
) -> None:
    """Open every topic with ``language`` active and judge each page.

    The topic ``missing`` must show the English page and every other topic the
    page of ``language``; no page may show the load-error sentence in either
    form.
    """
    choose_language(win, language)
    dialog = open_the_guide(win, qtbot)
    english_frame, installed_frame = load_error_frames()
    topics = [topic.id for topic in dialog._model.topics()] if dialog._model else []
    assert topics == stems, "the guide did not take the fixture tree"
    fell_back: List[str] = []
    for stem in stems:
        page = open_topic(dialog, stem)
        assert english_frame not in page, f"{stem}: the English load-error text shows"
        assert installed_frame not in page, f"{stem}: the load-error text shows"
        if stem == missing:
            assert f"BODY-en-{stem}" in page, f"{stem}: the English page is not shown"
            assert f"BODY-{language}-{stem}" not in page
            fell_back.append(stem)
        else:
            assert f"BODY-{language}-{stem}" in page, f"{stem}: not shown in {language}"
            assert f"BODY-en-{stem}" not in page
    assert fell_back == [missing]
    say(
        capsys,
        f"{language}: {len(stems)} topics opened, {len(fell_back)} fell back to "
        f"English ({', '.join(fell_back)}), {len(stems) - len(fell_back)} shown in "
        f"{language}; no load-error text on any page",
    )


# --------------------------------------------------------------------------- #
# SC-L10N-UI-007-1, SC-L10N-UI-007-2: per-topic fallback                       #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_007_1_missing_japanese_topic_falls_back_for_that_topic_only(
    open_main, qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """SC-L10N-UI-007-1: "Layers" is English, every other topic Japanese, no error."""
    win = open_main()
    stems = build_tree(tmp_path / "bundle", "ja", language_lacks="layers")
    use_tree(monkeypatch, tmp_path / "bundle")
    check_per_topic_fallback(win, qtbot, capsys, stems, "ja", "layers")


def test_sc_l10n_ui_007_2_spanish_gets_the_same_per_topic_fallback(
    open_main, qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """SC-L10N-UI-007-2: a Spanish tree missing one topic shows its English page."""
    win = open_main()
    stems = build_tree(tmp_path / "bundle", "es", language_lacks="colour-hub")
    use_tree(monkeypatch, tmp_path / "bundle")
    check_per_topic_fallback(win, qtbot, capsys, stems, "es", "colour-hub")


@pytest.mark.parametrize("language", ["ja", "es"])
def test_control_a_page_missing_from_english_too_shows_the_load_error(
    open_main,
    qtbot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    language: str,
) -> None:
    """Control of SC-L10N-UI-007-1 and -2: the check would see a load error.

    The page is missing from the language and from English, so there is nothing to
    fall back to. The error sentence must then be on the page: the same assertion
    that is "absent" in the scenarios is "present" here.
    """
    win = open_main()
    build_tree(
        tmp_path / "bundle",
        language,
        language_lacks="layers",
        english_lacks="layers",
    )
    use_tree(monkeypatch, tmp_path / "bundle")
    choose_language(win, language)
    dialog = open_the_guide(win, qtbot)
    page = open_topic(dialog, "layers")
    english_frame, installed_frame = load_error_frames()
    assert (
        english_frame in page or installed_frame in page
    ), f"a page with no source shows no load-error sentence: {page!r}"
    assert f"BODY-{language}-layers" not in page and "BODY-en-layers" not in page
    say(capsys, f"control {language}: the load-error sentence is shown for a lost page")


# --------------------------------------------------------------------------- #
# SC-L10N-UI-008-1: the table of contents in the active language               #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_008_1_korean_table_of_contents_equals_the_recorded_titles(
    open_main, qtbot, capsys
) -> None:
    """SC-L10N-UI-008-1: every section and topic title is its recorded Korean title."""
    expected, record = recorded_toc("ko")
    win = open_main()
    choose_language(win, "ko")
    dialog = open_the_guide(win, qtbot)
    shown = toc_rows(dialog)
    sections = len(expected)
    topics = sum(len(titles) for _title, titles in expected)
    examined = sections + topics
    assert examined > 0, "no title was examined"
    assert shown == expected
    say(
        capsys,
        f"ko: {examined} titles examined ({sections} sections, {topics} topics), "
        f"all equal to the record in {record.relative_to(BUNDLE.parent.parent)}",
    )


def test_control_the_english_table_of_contents_is_not_the_korean_record(
    open_main, qtbot
) -> None:
    """Control of SC-L10N-UI-008-1: the check fails for a table that is not Korean."""
    korean, _ = recorded_toc("ko")
    english, _ = recorded_toc("en")
    assert (
        english != korean
    ), "the two records are the same, so the check proves nothing"
    win = open_main()
    dialog = open_the_guide(win, qtbot)
    assert toc_rows(dialog) == english
    assert toc_rows(dialog) != korean


# --------------------------------------------------------------------------- #
# SC-L10N-UI-008-2: search by the local word and by the English keyword        #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_008_2_french_search_finds_layers_by_french_word_and_by_layer(
    open_main, qtbot, capsys
) -> None:
    """SC-L10N-UI-008-2: "calques" and "layer" both list the Layers topic in French."""
    layers_title, record = recorded_topic_title("fr", "layers")
    assert (
        FRENCH_LAYERS_WORD in layers_title.lower()
    ), f"{record} records {layers_title!r} for Layers, which lacks the word"
    win = open_main()
    choose_language(win, "fr")
    dialog = open_the_guide(win, qtbot)
    found: Dict[str, List[str]] = {}
    for term in (FRENCH_LAYERS_WORD, "layer"):
        dialog._search_edit.setText(term)
        QApplication.processEvents()
        assert dialog._left_stack.currentWidget() is dialog._results_list
        found[term] = result_ids(dialog)
        assert "layers" in found[term], f"searching {term!r} did not list Layers"
        titles = [
            dialog._results_list.item(row).text()
            for row in range(dialog._results_list.count())
        ]
        assert layers_title in titles, f"the result is not titled in French: {titles}"
    # Opening the result opens the page in French.
    row = result_ids(dialog).index("layers")
    dialog._results_list.setCurrentRow(row)
    QApplication.processEvents()
    assert dialog.current_topic_id() == "layers"
    assert shown_heading(dialog) == page_heading("fr", "layers")
    say(
        capsys,
        f"fr: {FRENCH_LAYERS_WORD!r} -> {len(found[FRENCH_LAYERS_WORD])} results and "
        f"'layer' -> {len(found['layer'])} results, Layers among both; "
        f"its title in the results is the one recorded in "
        f"{record.relative_to(BUNDLE.parent.parent)}",
    )


def test_control_the_french_word_finds_nothing_under_english(open_main, qtbot) -> None:
    """Control of SC-L10N-UI-008-2: the French word is local, "layer" is not.

    With English active the French word lists no topic, so Layers found under
    French is the French metadata's doing and not a word the English index holds.
    """
    win = open_main()
    dialog = open_the_guide(win, qtbot)
    dialog._search_edit.setText(FRENCH_LAYERS_WORD)
    QApplication.processEvents()
    assert result_ids(dialog) == []
    dialog._search_edit.setText("layer")
    QApplication.processEvents()
    assert "layers" in result_ids(dialog)


# --------------------------------------------------------------------------- #
# SC-L10N-UI-001-3: an open guide follows a language switch                    #
# --------------------------------------------------------------------------- #


def test_sc_l10n_ui_001_3_open_guide_rerenders_in_german_after_a_switch(
    open_main, qtbot, capsys
) -> None:
    """SC-L10N-UI-001-3: the open topic is re-rendered from the German content."""
    english_heading = page_heading("en", "layers")
    german_heading = page_heading("de", "layers")
    assert english_heading != german_heading
    german_toc, _ = recorded_toc("de")
    english_toc, _ = recorded_toc("en")
    win = open_main()
    dialog = open_guide(win, qtbot, "layers")
    assert shown_heading(dialog) == english_heading, "the control state is not English"
    assert shown_heading(dialog) != german_heading
    assert toc_rows(dialog) == english_toc
    pane = dialog._content_view
    # The observer is connected before the switch that triggers it.
    with qtbot.waitSignal(pane.textChanged, timeout=2000):
        choose_language(win, "de")
    assert win._user_guide_dialog is dialog, "the switch replaced the window"
    assert dialog.current_topic_id() == "layers", "the switch moved the topic"
    assert shown_heading(dialog) == german_heading
    assert toc_rows(dialog) == german_toc
    assert dialog.windowTitle() == QCoreApplication.translate(
        GUIDE_CONTEXT, "User Guide"
    )
    assert dialog.windowTitle() != "User Guide"
    # And back: the same window follows the switch to English too.
    with qtbot.waitSignal(pane.textChanged, timeout=2000):
        choose_language(win, "en")
    assert shown_heading(dialog) == english_heading
    assert toc_rows(dialog) == english_toc
    say(
        capsys,
        f"de: the open window changed from {english_heading!r} to "
        f"{german_heading!r} on the switch, "
        f"{sum(len(t) + 1 for _s, t in german_toc)} titles in the German "
        f"table of contents, and back to English",
    )
