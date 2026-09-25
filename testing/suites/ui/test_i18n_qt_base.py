"""UI test for REQ-AV-UI-012 (Qt's own catalogues installed) -- Qt's own base catalogue.

The maintainer answered "install" (2026-09-24): ``LanguageManager`` is to
install a SECOND :class:`~PySide6.QtCore.QTranslator` holding Qt's own
``qtbase_<code>.qm`` catalogue alongside the app catalogue, so Qt-GENERATED
text (the macOS application-menu "About %1", and every standard
:class:`~PySide6.QtWidgets.QDialogButtonBox` button) is Spanish in Spanish
sessions too (plan §2, Researcher F3-F5).

Grounding probe, this session (CPython 3.13.13, PySide6 6.11.1 / Qt 6.11.1,
``QT_QPA_PLATFORM=offscreen``, Windows): the SHIPPED PySide6 wheel already
carries ``qtbase_es.qm`` at ``QLibraryInfo.path(TranslationsPath)``, and
loading + installing it directly (bypassing ``LanguageManager`` entirely)
DOES translate ``QCoreApplication.translate("MAC_APPLICATION_MENU", "About
%1")`` to "Acerca de %1" and a ``QDialogButtonBox`` Cancel button to
"Cancelar" -- reproducing the plan's own probe exactly. A failure in the
tests below is therefore the FEATURE's absence (``LanguageManager`` does not
install this second translator yet), never an environment gap.

Run red before the base-catalogue install is implemented: ``LanguageManager``
today installs only the app catalogue, so switching to "es" leaves Qt's own
strings in English.
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale
from PySide6.QtWidgets import QDialogButtonBox

from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE, LanguageManager


@pytest.fixture(autouse=True)
def _english_start_language():
    """Force ``QLocale.system()`` to resolve to English before every test.

    Every ``LanguageManager`` here is built fresh with an explicit
    ``set_language("es")``/``set_language(FALLBACK_LANGUAGE)`` call, never
    through ``install_from_locale()``, so this module's own assertions do
    not currently depend on the host OS locale either. The fixture is added
    anyway, matching the other three sibling UI test files (``test_about_dialog.py``,
    ``test_window_title_version.py``, ``test_about_catalogue.py``) and this
    suite's own ``conftest.py`` patch, so the whole slice of tests is
    uniformly, explicitly locale-independent (F11 / portability) rather than
    leaving one file's independence implicit.
    """
    QLocale.system = staticmethod(  # type: ignore[method-assign]
        lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
    )
    yield


def test_qt_base_catalogue_translates_mac_application_menu_and_reverts(qtbot, qapp):
    """After ``set_language("es")`` Qt's own MAC_APPLICATION_MENU text is
    Spanish; switching back to "en" reverts it to English."""
    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        translated = QCoreApplication.translate("MAC_APPLICATION_MENU", "About %1")
        assert translated == "Acerca de %1"

        assert manager.set_language(FALLBACK_LANGUAGE) is True
        reverted = QCoreApplication.translate("MAC_APPLICATION_MENU", "About %1")
        assert reverted == "About %1"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_qt_base_catalogue_translates_a_standard_dialog_button(qtbot, qapp):
    """The deliberate side effect this suite asserts: a
    :class:`QDialogButtonBox` standard Cancel button reads in Spanish once
    Qt's own base catalogue is active (proof the SECOND translator, not just
    the app one, is installed)."""
    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        qtbot.addWidget(box)
        button = box.button(QDialogButtonBox.StandardButton.Cancel)
        assert button.text() == "Cancelar"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_qt_base_catalogue_missing_directory_degrades_with_a_warning(
    qtbot, qapp, tmp_path, monkeypatch, caplog
):
    """With the Qt translations path pointed at an EMPTY directory,
    ``set_language("es")`` still returns ``True``, the APP catalogue is still
    active, and a warning is logged -- with no exception.

    ``QLibraryInfo.path`` is the literal API the plan names for locating
    Qt's own catalogues (plan §2's Qt-catalogue stack-decision row); it is a
    Qt class staticmethod, confirmed monkeypatchable at the class level this
    session (a plain ``monkeypatch.setattr`` swap, verified to both take
    effect and to restore cleanly).
    """
    monkeypatch.setattr(
        QLibraryInfo, "path", staticmethod(lambda *_a, **_k: str(tmp_path))
    )
    manager = LanguageManager(qapp)
    try:
        with caplog.at_level(logging.WARNING):
            result = manager.set_language("es")
        assert result is True
        assert manager.current_language() == "es"
        # The APP catalogue is unaffected by the missing Qt catalogue.
        assert QCoreApplication.translate("Main_Window", "Untitled") == "Sin título"
        assert any(record.levelno >= logging.WARNING for record in caplog.records), (
            "expected a warning to be logged for the missing qtbase catalogue "
            f"directory; got: {[r.message for r in caplog.records]!r}"
        )
    finally:
        manager.set_language(FALLBACK_LANGUAGE)
