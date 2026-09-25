# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Runtime internationalisation manager (REQ-P1-UI-021, -022; F5/F6; REQ-AV-UI-012).

``LanguageManager`` selects the UI language from the system :class:`QLocale`
(falling back to English, CL-14), installs the matching :class:`QTranslator` on
the application, and can swap it at runtime. Installing/removing a translator
makes Qt post a :data:`QEvent.Type.LanguageChange` to every widget, which each
hand-built widget handles in ``changeEvent`` to re-set its ``tr()``-wrapped text
(live retranslation, no restart — F5).

The binary ``.qm`` catalogues are build output, compiled from the ``.ts``
source catalogues with ``pyside6-lrelease``; this module only discovers and
loads them, so it degrades gracefully to the built-in English source strings
when no catalogue is present.

A second, independent :class:`QTranslator` loads Qt's OWN ``qtbase_<code>.qm``
catalogue from :meth:`QLibraryInfo.path` (``LibraryPath.TranslationsPath``).
That catalogue is what translates text Qt itself generates -- the macOS
application-menu "About %1"/"Preferences..."/"Quit %1" and every standard
:class:`QDialogButtonBox` button -- none of which is covered by the
application's own ``pixelart_<code>.qm`` (ADR-0067 Part 4; REQ-AV-UI-012;
Researcher ``research-qt-aboutrole-macos.md`` F3-F5). It is installed and
removed alongside the application catalogue on every language switch. A
missing or unloadable Qt catalogue (e.g. a frozen build built before it
ships them) is logged as a warning and never changes what
:meth:`LanguageManager.set_language` returns -- the application's own
catalogue stays authoritative either way.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    QCoreApplication,
    QLibraryInfo,
    QLocale,
    QObject,
    QTranslator,
    Signal,
)

_LOGGER = logging.getLogger(__name__)

#: Language code used when no catalogue matches the locale (CL-14). English is
#: the source language of the ``tr()`` literals, so it needs no ``.qm`` file.
FALLBACK_LANGUAGE = "en"

#: Prefix of a compiled catalogue file, e.g. ``pixelart_es.qm`` (build output
#: of ``pyside6-lrelease``, not hand-authored).
_CATALOGUE_PREFIX = "pixelart_"
_CATALOGUE_SUFFIX = ".qm"


#: Package-internal catalogue folder name, sibling of this module inside
#: ``pixelart_creator`` (``pixelart_creator/i18n/``). It ships with the wheel
#: because it is inside the installed package (unlike the old repository-top-level
#: ``i18n/`` folder, which pip never installed -- B6).
_CATALOGUE_DIRNAME = "i18n"

#: Prefix of Qt's OWN base catalogue, e.g. ``qtbase_es.qm`` (shipped inside the
#: PySide6 wheel / the Qt install, never authored by this project -- ADR-0067
#: Part 4).
_QT_CATALOGUE_PREFIX = "qtbase_"


def _default_translations_dir() -> Path:
    """Return the directory holding the ``.qm``/``.ts`` catalogues.

    Resolved correctly BY CONSTRUCTION as a sibling of the ``pixelart_creator``
    package's ``ui`` subpackage: ``pixelart_creator/i18n/`` sits next to
    ``pixelart_creator/ui/`` (this module's own parent), so it is inside the
    installed package and ships with the wheel. Falls back to the legacy
    repository-top-level ``i18n/`` directory (three parents up from this file)
    for a stale checkout or an unusual layout where only that copy exists.
    """
    packaged = Path(__file__).resolve().parent.parent / _CATALOGUE_DIRNAME
    if packaged.is_dir():
        return packaged
    legacy = Path(__file__).resolve().parent.parent.parent / _CATALOGUE_DIRNAME
    if legacy.is_dir():
        return legacy
    return packaged


class LanguageManager(QObject):
    """Installs/swaps the application :class:`QTranslator` by language code.

    Args:
        app: The running application (``QApplication``/``QCoreApplication``)
            the translator is installed on.
        translations_dir: Directory holding ``pixelart_<code>.qm`` catalogues.
            Defaults to the package-internal ``i18n/`` folder (resolved portably).
        parent: Optional Qt parent.
    """

    #: Emitted with the newly active language code after a successful switch.
    languageChanged = Signal(str)

    def __init__(
        self,
        app: QCoreApplication,
        translations_dir: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Bind to `app` and resolve the translations dir, starting untranslated."""
        super().__init__(parent)
        self._app = app
        self._dir = (
            Path(translations_dir) if translations_dir else _default_translations_dir()
        )
        self._translator = QTranslator(self)
        self._qt_translator = QTranslator(self)
        self._qt_translator_installed = False
        self._current = FALLBACK_LANGUAGE

    # -- queries ----------------------------------------------------------

    def available_languages(self) -> List[str]:
        """Return the selectable language codes (English first, then found ``.qm``)."""
        codes = [FALLBACK_LANGUAGE]
        if self._dir.is_dir():
            for qm in sorted(
                self._dir.glob(f"{_CATALOGUE_PREFIX}*{_CATALOGUE_SUFFIX}")
            ):
                code = qm.stem[len(_CATALOGUE_PREFIX) :]
                if code and code not in codes:
                    codes.append(code)
        return codes

    def current_language(self) -> str:
        """Return the currently active language code."""
        return self._current

    # -- installation -----------------------------------------------------

    def install_from_locale(self) -> str:
        """Install the translator matching the system locale (fallback English).

        Returns:
            The language code actually installed.
        """
        available = self.available_languages()
        for candidate in QLocale.system().uiLanguages():
            code = candidate.replace("-", "_").split("_")[0]
            if code in available:
                self.set_language(code)
                return self._current
        self.set_language(FALLBACK_LANGUAGE)
        return self._current

    def set_language(self, code: str) -> bool:
        """Switch the UI language at runtime.

        Removes any active catalogue and, for a non-English code, loads and
        installs ``pixelart_<code>.qm``. Posting the translator change triggers
        the :data:`QEvent.Type.LanguageChange` that drives live retranslation.

        Args:
            code: Target language code (e.g. ``"en"``, ``"es"``).

        Returns:
            ``True`` if the requested language became active.
        """
        self._app.removeTranslator(self._translator)
        if code == FALLBACK_LANGUAGE:
            self._current = FALLBACK_LANGUAGE
            self._apply_qt_base_catalogue(self._current)
            self.languageChanged.emit(self._current)
            return True

        loaded = self._translator.load(f"{_CATALOGUE_PREFIX}{code}", str(self._dir))
        if not loaded:
            # No catalogue on disk yet: stay on the English source strings.
            self._current = FALLBACK_LANGUAGE
            self._apply_qt_base_catalogue(self._current)
            self.languageChanged.emit(self._current)
            return False

        self._app.installTranslator(self._translator)
        self._current = code
        self._apply_qt_base_catalogue(self._current)
        self.languageChanged.emit(self._current)
        return True

    # -- Qt's own base catalogue (ADR-0067 Part 4, REQ-AV-UI-012) ---------

    def _apply_qt_base_catalogue(self, code: str) -> None:
        """Swap Qt's own ``qtbase_<code>.qm`` alongside the app catalogue.

        Removes any previously installed Qt base translator first. For
        ``FALLBACK_LANGUAGE`` (English, the source language) nothing further
        is installed. For any other code, this loads ``qtbase_<code>`` from
        :meth:`QLibraryInfo.path` (``LibraryPath.TranslationsPath``) and
        installs it on success. A missing directory, a missing catalogue file,
        or any load failure is logged as a warning and left there -- it never
        raises and never changes :meth:`set_language`'s return value, because
        the application's own catalogue (``self._translator``) is already
        authoritative for every ``tr()``-wrapped string in this product.
        """
        if self._qt_translator_installed:
            self._app.removeTranslator(self._qt_translator)
            self._qt_translator_installed = False

        if code == FALLBACK_LANGUAGE:
            return

        qt_translations_dir = QLibraryInfo.path(
            QLibraryInfo.LibraryPath.TranslationsPath
        )
        loaded = self._qt_translator.load(
            f"{_QT_CATALOGUE_PREFIX}{code}", qt_translations_dir
        )
        if not loaded:
            # `_LOGGER.log(logging.WARNING, ...)` rather than `_LOGGER.warning(...)`:
            # the string-audit heuristic (`scripts/string_audit_check.py`) flags a
            # `.warning(<string literal>)` call as an unwrapped user-facing string
            # because `QMessageBox` happens to share that method name (see
            # `pixelart_creator/ui/app_icon.py`, this repository's existing
            # convention for this exact false positive) -- this is a diagnostic
            # log record, not UI text, so it takes the equivalent `.log(level, ...)`
            # form instead of being mis-wrapped in `tr()`.
            _LOGGER.log(
                logging.WARNING,
                "Qt base catalogue '%s%s' not found under %r; Qt-generated "
                "text (e.g. the macOS application menu, standard dialog "
                "buttons) stays in English for language %r.",
                _QT_CATALOGUE_PREFIX,
                code,
                qt_translations_dir,
                code,
            )
            return

        self._app.installTranslator(self._qt_translator)
        self._qt_translator_installed = True
