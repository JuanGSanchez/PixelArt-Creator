"""Internationalisation acceptance tests (REQ-P1-UI-021, -022).

Scenarios SC-UI-021-1 (LanguageManager installs a translator by locale, English
fallback), SC-UI-022-1 (changeEvent re-translates on LanguageChange). Both
themes. REQ-P1-UI-026 (no bare literals) is verified by the localisation owner's
`string_audit_check` and referenced in the checklist rather than duplicated as a pytest
here.

SC-UI-021-1 covers the eight shipped catalogues (``en``, ``es``, ``fr``, ``de``,
``ru``, ``zh_CN``, ``ja``, ``ko``): a manager on the default directory offers exactly
those eight and installs each one in turn, and under each the real text of that
language's own ``.ts`` file appears. The eight codes are written below from the
requirement, not read from the product, so a language dropped from the product fails
the test and does not shrink it. ``PIXELART_I18N_CATALOGUE_DIR`` names a directory of
compiled ``.qm`` files to measure instead of the shipped ones; it exists to show these
cases fail against an incomplete set, and unset, the shipped ones are measured.

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

import os
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QLocale
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic import about_info
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

#: The eight shipped interface languages, in the selector order of REQ-L10N-UI-003.
EIGHT_LANGUAGES = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")

#: Names a directory of compiled catalogues to measure instead of the shipped ones.
CATALOGUE_DIR_ENV = "PIXELART_I18N_CATALOGUE_DIR"


def _catalogue_dir() -> Path:
    """Return the directory of compiled catalogues under test."""
    named = os.environ.get(CATALOGUE_DIR_ENV)
    return Path(named) if named else _default_translations_dir()


def _ts_translation(code: str, context: str, source: str) -> str:
    """Return one language's finished translation of a message, read from its ``.ts``.

    The shipped ``.ts`` is read with ElementTree, never through the product, so the
    expected text does not come from the code under test.
    """
    path = _default_translations_dir() / f"pixelart_{code}.ts"
    for ctx in ElementTree.parse(path).getroot().iter("context"):
        if ctx.findtext("name") != context:
            continue
        for message in ctx.iter("message"):
            if message.findtext("source") == source:
                translation = message.find("translation")
                assert translation is not None
                assert translation.get("type") != "unfinished", (code, source)
                return translation.text or ""
    raise AssertionError(f"{context}: {source!r} is not in {path.name}")


def test_sc_ui_021_1_language_manager_installs_by_locale(qtbot, qapp):
    """SC-UI-021-1: install_from_locale installs a translator (English fallback)."""
    manager = LanguageManager(qapp)
    installed = manager.install_from_locale()
    assert installed in manager.available_languages()
    # Eight catalogues are packaged. The suite pins the system locale to English
    # (see conftest.py), so the preferred languages are English and it is chosen.
    assert installed == FALLBACK_LANGUAGE
    assert manager.current_language() == installed
    assert FALLBACK_LANGUAGE in manager.available_languages()


def test_sc_ui_022_1_change_event_retranslates_on_language_change(qtbot):
    """SC-UI-022-1: a LanguageChange event re-sets tr()-wrapped visible text.

    Updated for REQ-AV-UI-001 (app-version): the title is now
    ``about_info.window_title(self.tr("PixelArt Creator"))``, i.e. the
    translated name PLUS the running version
    (``pixelart_creator.__version__``, read at set-time), not the bare
    name. The expected value is DERIVED from ``about_info.window_title``
    itself -- never a hard-coded version literal (NFR-2) -- so this
    oracle tracks the feature's own logic instead of re-pinning a version
    number that will drift at every release. The test's original intent is
    unchanged: corrupt the title, deliver ``LanguageChange``, and prove
    ``changeEvent`` re-sets it live without a restart (F5).
    """
    win = Main_Window()
    qtbot.addWidget(win)
    # Corrupt visible labels, then deliver LanguageChange: changeEvent must
    # re-set them from tr() without a restart (live retranslation, F5).
    win.setWindowTitle("XXX")
    win._file_menu.setTitle("XXX")
    QApplication.sendEvent(win, QEvent(QEvent.Type.LanguageChange))
    assert win.windowTitle() == about_info.window_title("PixelArt Creator")
    assert win._file_menu.title() == "&File"


def test_sc_ui_022_1_palette_panel_retranslates(qtbot):
    """SC-UI-022-1 (panel): the palette panel re-sets its accessible name too."""
    win = Main_Window()
    qtbot.addWidget(win)
    win._palette_panel._list.setAccessibleName("XXX")
    QApplication.sendEvent(win._palette_panel, QEvent(QEvent.Type.LanguageChange))
    assert win._palette_panel._list.accessibleName() == "Colour palette"


def test_available_languages_discovers_catalogues(qtbot, qapp, tmp_path):
    """SC-UI-021-1 (discovery): a packaged pixelart_<code>.qm is offered as a
    language."""
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


def test_sc_ui_021_5_default_dir_manager_offers_exactly_the_eight(qtbot, qapp):
    """SC-UI-021-1: a manager on the default directory offers the eight shipped
    languages, English first, and no other."""
    manager = LanguageManager(qapp, translations_dir=_catalogue_dir())
    langs = manager.available_languages()
    print(f"offered languages: {len(langs)} {langs}")
    assert langs[0] == FALLBACK_LANGUAGE
    assert len(langs) == 8
    assert sorted(langs) == sorted(EIGHT_LANGUAGES)


@pytest.mark.parametrize("code", EIGHT_LANGUAGES)
def test_sc_ui_021_6_each_of_the_eight_installs_and_translates(qtbot, qapp, code):
    """SC-UI-021-1: each shipped language installs from its own ``.qm`` and shows the
    text its own ``.ts`` gives, then leaves nothing installed.

    The expected text is that language's translation of "Untitled" in the
    ``Main_Window`` context, read from its ``.ts``; English shows the source.
    """
    manager = LanguageManager(qapp, translations_dir=_catalogue_dir())
    expected = (
        "Untitled"
        if code == FALLBACK_LANGUAGE
        else _ts_translation(code, "Main_Window", "Untitled")
    )
    try:
        assert manager.set_language(code) is True, f"pixelart_{code}.qm did not load"
        assert manager.current_language() == code
        shown = QCoreApplication.translate("Main_Window", "Untitled")
        print(f"{code}: Untitled -> {ascii(shown)}")
        assert shown == expected
        if code != FALLBACK_LANGUAGE:
            assert shown != "Untitled"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)
    assert QCoreApplication.translate("Main_Window", "Untitled") == "Untitled"


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


def test_sc_csd_u014_1_confirm_dialog_strings_are_tr_wrapped_and_placeheld(
    qtbot, english_on_a_spanish_system
):
    """SC-CSD-U014-1: the confirm dialog's title/message/button labels are all
    `tr()`-produced, and the projected size + target geometry are inserted via
    FORMAT PLACEHOLDERS (never a concatenated translated fragment + number).

    The size is the interface language's: English on an ``es_ES`` system reads
    "5.08 GiB", Qt's own English text, and not the system's "5,08 GiB"
    (REQ-L10N-UI-015).
    """
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
    assert QLocale("en").formattedDataSize(5_454_692_352) in message
    assert QLocale("es_ES").formattedDataSize(5_454_692_352) not in message
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
    return Path(__file__).resolve().parents[3]
