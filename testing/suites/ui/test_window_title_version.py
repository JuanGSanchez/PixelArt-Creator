"""UI tests for REQ-AV-UI-001 — the main-window title carries the running version.

Plan §3.2: the title is composed as
``about_info.window_title(self.tr("PixelArt Creator"))`` -> ``"<translated name>
<version>"``, with the version read from ``pixelart_creator.__version__`` at the
time the title is SET (never bound at import time -- test-binding constraint C-3).
Every test in this module runs twice, once per theme, via the suite's autouse
``theme`` fixture (``testing/suites/ui/conftest.py``) -- title composition is
theme-invariant, so no test here adds its own theme parametrisation.

Red-first (NFR-5): at `a77b5c0` ``Main_Window._retranslate`` sets the window
title to the fixed translated literal "PixelArt Creator" only
(``main_window.py:5351-5352``) -- no version is composed in. Every assertion
below that checks for a version in the title therefore fails now for the
right reason (the feature is absent), not a harness/typo error.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QLocale

import pixelart_creator
from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE
from pixelart_creator.ui.main_window import Main_Window


@pytest.fixture(autouse=True)
def _english_start_language():
    """Force ``QLocale.system()`` to resolve to English before every test.

    ``testing/suites/ui/conftest.py`` already patches ``QLocale.system`` the
    same way, once, at collection time, for the whole UI suite -- so every
    ``Main_Window()`` built anywhere under this directory already starts in
    English regardless of the host OS locale. This machine's own Windows
    locale is ``es_ES`` (verified this session: a ``Main_Window`` built with
    the patch removed starts translated). This fixture repeats that same
    patch LOCALLY and EXPLICITLY in this file (autouse, no per-test opt-in
    needed), so every test here is provably independent of the conftest
    patch's continued presence too and matches CI's neutral/English runner
    regardless of which machine runs it (F11 / portability).
    """
    QLocale.system = staticmethod(  # type: ignore[method-assign]
        lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    )
    yield


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_av_ui_001_1_title_shows_the_running_version(qtbot, monkeypatch):
    """@C-2 / SC-AV-UI-001-1: the title reads "PixelArt Creator <version>".

    NFR-2 / CL-AV-12: the expected version is never a literal the test pins
    against the shipped value -- the test INSTALLS "0.3.1" itself, exactly as
    C-3 installs "9.9.9" below, so this assertion is against a value under the
    test's own control.
    """
    monkeypatch.setattr(pixelart_creator, "__version__", "0.3.1", raising=False)
    win = _window(qtbot)
    assert win.windowTitle() == "PixelArt Creator 0.3.1"


def test_sc_av_ui_001_2_title_is_not_hard_coded(qtbot, monkeypatch):
    """@C-3 / SC-AV-UI-001-2: replacing __version__ BEFORE construction changes
    the title.

    Test-binding constraint C-3: the version is looked up when the title is
    set, not copied/bound at import time -- so a monkeypatch applied before
    the window is built must already be visible in the title.
    """
    monkeypatch.setattr(pixelart_creator, "__version__", "9.9.9", raising=False)
    win = _window(qtbot)
    assert "9.9.9" in win.windowTitle()


def test_sc_av_ui_001_3_title_keeps_version_across_language_change(qtbot):
    """@C-4 / SC-AV-UI-001-3: the title keeps the version after switching to es.

    Reads the LIVE ``pixelart_creator.__version__`` attribute (CL-AV-12
    permits either an installed value or the live attribute here); nothing in
    this test hard-codes a version literal (NFR-2). The product name
    "PixelArt Creator" is its own message in the Spanish catalogue (measured
    fact, spec.md §1: it translates to itself), so the title is expected to
    still BEGIN with it even in Spanish.
    """
    win = _window(qtbot)
    try:
        assert win._language_manager.set_language("es") is True
        title = win.windowTitle()
        assert title.startswith("PixelArt Creator")
        assert title.endswith(pixelart_creator.__version__)
    finally:
        win._language_manager.set_language(FALLBACK_LANGUAGE)
