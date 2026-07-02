"""Internationalisation acceptance tests (REQ-P1-UI-021, -022).

Scenarios SC-UI-021-1 (LanguageManager installs a translator by locale, English
fallback), SC-UI-022-1 (changeEvent re-translates on LanguageChange). Both
themes. REQ-P1-UI-026 (no bare literals) is verified by AGT-07 `string_audit_check`
and referenced in the checklist rather than duplicated as a pytest here.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.main_window import Main_Window


def test_sc_ui_021_1_language_manager_installs_by_locale(qtbot, qapp):
    """SC-UI-021-1: install_from_locale installs a translator (English fallback)."""
    manager = LanguageManager(qapp)
    installed = manager.install_from_locale()
    assert installed in manager.available_languages()
    # With no .qm catalogues packaged yet, the manager degrades to English.
    assert manager.current_language() == installed
    assert FALLBACK_LANGUAGE in manager.available_languages()


def test_sc_ui_022_1_change_event_retranslates_on_language_change(qtbot):
    """SC-UI-022-1: a LanguageChange event re-sets tr()-wrapped visible text."""
    win = Main_Window()
    qtbot.addWidget(win)
    # Corrupt visible labels, then deliver LanguageChange: changeEvent must
    # re-set them from tr() without a restart (live retranslation, F5).
    win.setWindowTitle("XXX")
    win._file_menu.setTitle("XXX")
    QApplication.sendEvent(win, QEvent(QEvent.Type.LanguageChange))
    assert win.windowTitle() == "PixelArt Creator"
    assert win._file_menu.title() == "&File"


def test_sc_ui_022_1_palette_panel_retranslates(qtbot):
    """SC-UI-022-1 (panel): the palette panel re-sets its accessible name too."""
    win = Main_Window()
    qtbot.addWidget(win)
    win._palette_panel._list.setAccessibleName("XXX")
    QApplication.sendEvent(win._palette_panel, QEvent(QEvent.Type.LanguageChange))
    assert win._palette_panel._list.accessibleName() == "Colour palette"


def test_available_languages_discovers_catalogues(qtbot, qapp, tmp_path):
    """SC-UI-021-1 (discovery): a packaged pixelart_<code>.qm is offered as a language."""
    (tmp_path / "pixelart_es.qm").write_bytes(b"")  # placeholder catalogue (AGT-07)
    manager = LanguageManager(qapp, translations_dir=tmp_path)
    langs = manager.available_languages()
    assert FALLBACK_LANGUAGE in langs
    assert "es" in langs  # discovered from the translations dir


def test_set_language_missing_catalogue_falls_back(qtbot, qapp, tmp_path):
    """SC-UI-021-1 (fallback): loading an absent/invalid .qm degrades to English."""
    (tmp_path / "pixelart_es.qm").write_bytes(b"")  # not a loadable catalogue
    manager = LanguageManager(qapp, translations_dir=tmp_path)
    assert manager.set_language("es") is False
    assert manager.current_language() == FALLBACK_LANGUAGE
    assert manager.set_language(FALLBACK_LANGUAGE) is True


def test_sc_ui_021_2_default_dir_resolves_to_repo_i18n():
    """SC-UI-021-2 (A11Y/i18n fix): the default translations dir is the repo i18n/.

    Re-verifies the AGT-05 fix making the default resolve portably (no baked-in
    absolute path): the folder is named ``i18n`` and holds the es catalogue."""
    d = _default_translations_dir()
    assert d.name == "i18n"
    assert (d / "pixelart_es.qm").is_file()


def test_sc_ui_021_3_default_dir_manager_offers_es(qtbot, qapp):
    """SC-UI-021-2: a manager built with NO translations_dir discovers es."""
    manager = LanguageManager(qapp)  # default (portable) dir
    langs = manager.available_languages()
    assert FALLBACK_LANGUAGE in langs
    assert "es" in langs


def test_sc_ui_021_4_default_dir_loads_real_es_catalogue(qtbot, qapp):
    """SC-UI-021-2: the default-dir manager loads the real es .qm and translates."""
    manager = LanguageManager(qapp)  # default (portable) dir
    try:
        assert manager.set_language("es") is True
        assert manager.current_language() == "es"
        # Proof the real i18n/pixelart_es.qm content is active, not a stub.
        assert QCoreApplication.translate("Main_Window", "Untitled") == "Sin título"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)  # remove translator (no pollution)


def test_sc_ui_022_2_default_es_retranslates_live(qtbot):
    """SC-UI-022-2: installing the default es catalogue retranslates tr() text live.

    A document created while the es catalogue is active shows its translated
    title, proving the app-wide LanguageChange path drives live retranslation
    (no restart) off the portable default dir."""
    win = Main_Window()
    qtbot.addWidget(win)
    try:
        assert win._language_manager.set_language("es") is True
        win.new_document()
        index = win._tab_widget.currentIndex()
        assert win._tab_widget.tabText(index) == "Sin título"
    finally:
        win._language_manager.set_language(FALLBACK_LANGUAGE)
