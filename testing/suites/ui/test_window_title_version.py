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
from PySide6.QtCore import QLocale, QTranslator

import pixelart_creator
from pixelart_creator.logic import about_info
from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE, _default_translations_dir
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
    this test hard-codes a version literal (NFR-2).

    Strengthened: "PixelArt Creator" happens to translate to itself
    in the shipped Spanish catalogue (measured fact, ``pixelart_creator/i18n/
    pixelart_es.ts``, context ``Main_Window``, source line
    ``main_window.py:5382``), so a bare ``windowTitle()`` string comparison
    taken *after* the switch cannot tell a genuine retranslation apart from
    ``_retranslate`` never having run at all -- both leave the identical text
    behind. To make the assertion a true positive/negative for retranslation:

    1. the title is CLEARED before switching, so it can only read back
       correct if ``Main_Window.changeEvent`` actually handled the posted
       ``QEvent.Type.LanguageChange`` and recomposed it;
    2. the expected text is derived from the REAL compiled catalogue (a live
       ``QTranslator`` load of the shipped ``.qm``, looked up by the same
       ``Main_Window`` context Qt uses for ``self.tr()`` there) composed
       through the production ``about_info.window_title`` -- never a literal
       (NFR-2 / CL-AV-12);
    3. ``qtbot.wait(10)`` -- runs a real Qt event loop for the given span,
       processing events -- is called straight after ``set_language`` because
       ``LanguageManager.set_language`` installs the translator via
       ``QCoreApplication.installTranslator``, which POSTS the
       ``LanguageChange`` event rather than delivering it synchronously; the
       observer-then-act ordering here is: switch language (post the event),
       THEN flush the queue, THEN read the now-settled title. Measured this
       session: ``qtbot.wait(0)`` is NOT enough here -- its zero-timeout
       ``QEventLoop`` races its own quit timer against the posted event and
       the title is still read back empty; a real event-processing span
       (``qtbot.wait(10)``, matching ``QApplication.processEvents()`` verified
       directly) is what actually flushes it.

    Proven red without step 3 (this session): with the ``qtbot.wait(10)``
    call removed entirely, the posted event is never delivered, ``_retranslate``
    never runs, and the title reads back as the cleared sentinel ``""`` -- the
    assertion fails for the right reason. Restored below; do not remove it.
    """
    win = _window(qtbot)

    # The catalogue's OWN compiled translation of the exact message
    # Main_Window.tr("PixelArt Creator") resolves to -- read from the real
    # shipped .qm via a live QTranslator, never a literal.
    translator = QTranslator()
    loaded = translator.load("pixelart_es", str(_default_translations_dir()))
    assert loaded, "shipped Spanish catalogue failed to load"
    translated_name = translator.translate("Main_Window", "PixelArt Creator")
    assert translated_name, "catalogue carries no Main_Window/PixelArt Creator message"

    expected_title = about_info.window_title(translated_name)

    # Clear the title first: only a genuine _retranslate() run can restore
    # it, so the read-back below cannot pass by coincidence of "PixelArt
    # Creator" translating to itself.
    win.setWindowTitle("")
    try:
        assert win._language_manager.set_language("es") is True
        qtbot.wait(10)  # flush the posted QEvent.LanguageChange
        title = win.windowTitle()
        assert title == expected_title
        assert title.endswith(pixelart_creator.__version__)
    finally:
        win._language_manager.set_language(FALLBACK_LANGUAGE)
        qtbot.wait(10)
