"""Internationalisation acceptance tests (REQ-P1-UI-021, -022).

Scenarios SC-UI-021-1 (LanguageManager installs a translator by locale, English
fallback), SC-UI-022-1 (changeEvent re-translates on LanguageChange). Both
themes. REQ-P1-UI-026 (no bare literals) is verified by the localisation owner's `string_audit_check`
and referenced in the checklist rather than duplicated as a pytest here.

SC-CSD-U014-1 (canvas-scale-defects REQ-CSD-UI-014) below adds
the two new whole-document-transform dialogs: every user-visible string is
`tr()`-wrapped, the projected size and target geometry arrive via FORMAT
PLACEHOLDERS (never a concatenated fragment + raw number), and each dialog
re-sets its texts on `QEvent.LanguageChange`. Pre-change: neither dialog class
exists at all (`git show HEAD:pixelart_creator/ui/document_transform_dialogs.py`
-> "exists on disk, but not in 'HEAD'"), so this whole scenario is a DEFECT
by non-existence, not merely by a failing assertion.
"""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import QCoreApplication, QEvent, QLocale
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.document_transform_dialogs import (
    Document_Transform_Confirm_Dialog,
    Document_Transform_Progress_Dialog,
)
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
    (tmp_path / "pixelart_es.qm").write_bytes(
        b""
    )  # placeholder catalogue (localisation)
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

    Re-verifies the UI fix making the default resolve portably (no baked-in
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


# =========================================================================== #
# SC-CSD-U014-1 (REQ-CSD-UI-014, DEFECT)                                      #
# =========================================================================== #


def test_sc_csd_u014_1_confirm_dialog_strings_are_tr_wrapped_and_placeheld(qtbot):
    """SC-CSD-U014-1: the confirm dialog's title/message/button labels are all
    `tr()`-produced, and the projected size + target geometry are inserted via
    FORMAT PLACEHOLDERS (never a concatenated translated fragment + number)."""
    dialog = Document_Transform_Confirm_Dialog(
        "Scale Canvas", 5_454_692_352, 7680, 4320
    )
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() != ""
    assert dialog._proceed.text() != ""
    assert dialog._decline.text() != ""
    message = dialog._message.text()
    assert message != ""
    # Placeholder substitution landed real values -- the operation label, the
    # target geometry and the QLocale-formatted size all appear as DISTINCT
    # substituted segments of one tr()-sourced template, never string-built
    # by gluing an untranslated number onto a fixed English phrase.
    assert "Scale Canvas" in message
    assert "7680" in message
    assert "4320" in message
    assert QLocale().formattedDataSize(5_454_692_352) in message
    # No stray, un-substituted placeholder survives into the shown text.
    for placeholder in ("%1", "%2", "%3", "%4"):
        assert placeholder not in message


def test_sc_csd_u014_1_progress_dialog_strings_are_tr_wrapped(qtbot):
    """SC-CSD-U014-1: the progress dialog's title/label/cancel text are all
    `tr()`-produced."""
    dialog = Document_Transform_Progress_Dialog("Rotate 90° CW", 7)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() != ""
    assert dialog._info.text() != ""
    assert "Rotate 90° CW" in dialog._info.text()
    assert dialog._cancel_button.text() != ""


def test_sc_csd_u014_1_confirm_dialog_retranslates_on_language_change(qtbot):
    """SC-CSD-U014-1: `QEvent.LanguageChange` re-sets EVERY text on the confirm
    dialog -- corrupted texts are restored to the real, tr()-sourced values,
    not merely re-drawn from the stale corrupted strings."""
    dialog = Document_Transform_Confirm_Dialog(
        "Scale Canvas", 5_454_692_352, 7680, 4320
    )
    qtbot.addWidget(dialog)
    real_title = dialog.windowTitle()
    real_message = dialog._message.text()
    real_proceed = dialog._proceed.text()
    real_decline = dialog._decline.text()

    dialog.setWindowTitle("XXX")
    dialog._message.setText("XXX")
    dialog._proceed.setText("XXX")
    dialog._decline.setText("XXX")
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))

    assert dialog.windowTitle() == real_title
    assert dialog._message.text() == real_message  # rebuilt from tr(), not "XXX"
    assert dialog._proceed.text() == real_proceed
    assert dialog._decline.text() == real_decline


def test_sc_csd_u014_1_progress_dialog_retranslates_on_language_change(qtbot):
    """SC-CSD-U014-1: `QEvent.LanguageChange` re-sets EVERY text on the
    progress dialog too -- each new dialog re-translates independently
    (SC-CSD-U014-1's own wording: "each dialog re-sets its texts")."""
    dialog = Document_Transform_Progress_Dialog("Scale Canvas", 7)
    qtbot.addWidget(dialog)
    real_title = dialog.windowTitle()
    real_info = dialog._info.text()
    real_cancel = dialog._cancel_button.text()

    dialog.setWindowTitle("XXX")
    dialog._info.setText("XXX")
    dialog._cancel_button.setText("XXX")
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))

    assert dialog.windowTitle() == real_title
    assert dialog._info.text() == real_info
    assert dialog._cancel_button.text() == real_cancel


def test_sc_csd_u014_1_string_audit_check_reports_no_unwrapped_string(qtbot):
    """SC-CSD-U014-1: `scripts/string_audit_check.py` reports NO unwrapped
    user-visible string in the new dialog module (run for real, not assumed)."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/string_audit_check.py",
            "pixelart_creator/ui/document_transform_dialogs.py",
        ],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"findings": []' in result.stdout


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[3]
