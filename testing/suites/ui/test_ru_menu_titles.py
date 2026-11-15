"""The six Russian top-level menu titles (REQ-L10N-UI-013, SC-L10N-UI-013-3).

The scenario has two halves, and every row of its table gets both:

* **The catalogue half.** The translation of the English title in context
  ``Main_Window`` (the spec's "MainWindow" read as the catalogue's own context
  name) equals the ruled Russian title. The value is read from ``pixelart_ru.ts``,
  the file itself, never from ``translate()``, so the product plays no part in the
  expected side. An entry that is missing, duplicated, unfinished or empty fails.
* **The shown half.** With Russian active, the text of that title in the menu bar
  is the ruled title followed by its English access key in brackets, for example
  ``Автоматика (&A)``. The window is built in English, so each menu bar entry is
  first found by its English source text; the same entry (same position) is then
  read after the window's own language manager switches to Russian.

The expected titles are literals copied from the scenario's table (round 21: the
user's ruling of 2026-11-15 replaced two of the earlier titles). The table is
written out once, here, and nothing derives it from the catalogue under test.

Both themes run, through the suite's autouse ``theme`` fixture. English is restored
after every case, so the cases are safe under ``-n auto``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Callable, Iterator, List, Tuple

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE, _default_translations_dir
from pixelart_creator.ui.main_window import Main_Window

#: The catalogue's own name for the main window's context.
_CONTEXT = "Main_Window"

#: The language of every row.
_RUSSIAN = "ru"

#: SC-L10N-UI-013-3's table: (English source, ruled title, text shown in the bar).
_ROWS: Tuple[Tuple[str, str, str], ...] = (
    ("&Automation", "Автоматика", "Автоматика (&A)"),
    ("&Image", "Рисунок", "Рисунок (&I)"),
    ("&Library", "Ресурсы", "Ресурсы (&L)"),
    ("Visual Ai&ds", "Утилиты", "Утилиты (&D)"),
    ("&Select", "Выделение", "Выделение (&S)"),
    ("Tile&map", "Тайлмэп", "Тайлмэп (&M)"),
)

#: The row ids pytest shows, by English source letter-for-letter.
_IDS = [row[0] for row in _ROWS]


def _catalogue_text(code: str, context: str, source: str) -> str:
    """Return the text the ``.ts`` file of ``code`` holds for (context, source).

    Read from the catalogue file itself. A missing, duplicated, unfinished or
    empty entry fails here, so the expected text is never a guess.
    """
    path = _default_translations_dir() / f"pixelart_{code}.ts"
    root = ET.parse(path).getroot()
    found = [
        message
        for scope in root.iter("context")
        if scope.findtext("name") == context
        for message in scope.iter("message")
        if message.findtext("source") == source
    ]
    assert len(found) == 1, f"{path.name}: {len(found)} entries for {source!r}"
    translation = found[0].find("translation")
    assert translation is not None and translation.text, f"{path.name}: no text"
    assert translation.get("type") != "unfinished", f"{path.name}: unfinished"
    return translation.text


def _bar_titles(window: Main_Window) -> List[str]:
    """Return the text of every title in ``window``'s menu bar, in order."""
    return [action.text() for action in window.menuBar().actions()]


def _bar_position(titles: List[str], source: str) -> int:
    """Return where ``source`` stands in ``titles``; fail unless it stands once."""
    hits = [index for index, text in enumerate(titles) if text == source]
    assert len(hits) == 1, f"{source!r} stands {len(hits)} times in {titles}"
    return hits[0]


@pytest.fixture
def make_window(qtbot, monkeypatch) -> Iterator[Callable[[], Main_Window]]:
    """Build English main windows; each one is returned to English in teardown."""
    built: List[Main_Window] = []

    def build() -> Main_Window:
        monkeypatch.setattr(
            QLocale, "system", staticmethod(lambda: QLocale(FALLBACK_LANGUAGE))
        )
        window = Main_Window()
        qtbot.addWidget(window)
        built.append(window)
        assert window._language_manager.current_language() == FALLBACK_LANGUAGE
        return window

    try:
        yield build
    finally:
        for window in built:
            window._language_manager.set_language(FALLBACK_LANGUAGE)
        QApplication.processEvents()


def test_the_table_has_the_six_rows_the_scenario_names():
    """SC-L10N-UI-013-3: six rows, each source and each title once (a known count)."""
    assert len(_ROWS) == 6
    assert len({row[0] for row in _ROWS}) == 6
    assert len({row[1] for row in _ROWS}) == 6
    for _source, title, shown in _ROWS:
        assert shown.startswith(f"{title} (&") and shown.endswith(")")


def test_the_catalogue_reader_fails_on_an_entry_that_is_not_there():
    """Control: the reader can fail. A title that is not in the catalogue is an error.

    Without this a reader that returned something for every source could not be told
    from one that read the file.
    """
    with pytest.raises(AssertionError, match="0 entries"):
        _catalogue_text(_RUSSIAN, _CONTEXT, "&No such menu title")
    with pytest.raises(AssertionError, match="0 entries"):
        _catalogue_text(_RUSSIAN, "No_Such_Context", "&Automation")


@pytest.mark.parametrize(("source", "title", "shown"), _ROWS, ids=_IDS)
def test_sc_l10n_ui_013_3_the_catalogue_holds_the_ruled_title(source, title, shown):
    """SC-L10N-UI-013-3: the Russian translation of the title is the ruled one."""
    assert _catalogue_text(_RUSSIAN, _CONTEXT, source) == title


@pytest.mark.parametrize(("source", "title", "shown"), _ROWS, ids=_IDS)
def test_sc_l10n_ui_013_3_the_menu_bar_shows_the_ruled_title(
    make_window, source, title, shown
):
    """SC-L10N-UI-013-3: with Russian active the bar's title reads ``<title> (&X)``.

    The window is built in English, where the entry is found by its source text and
    shows exactly that; the same position is then read in Russian. A known-true
    signal guards the case: the title changed, so the language really is in force.
    """
    window = make_window()
    english = _bar_titles(window)
    position = _bar_position(english, source)

    assert window._language_manager.set_language(_RUSSIAN) is True
    QApplication.processEvents()
    assert window._language_manager.current_language() == _RUSSIAN

    russian = _bar_titles(window)
    assert len(russian) == len(english), f"{english} became {russian}"
    assert russian[position] != source, "Russian is not in force on the menu bar"
    assert russian[position] == shown, f"{source!r} shows {russian[position]!r}"
