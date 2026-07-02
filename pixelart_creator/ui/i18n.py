"""Runtime internationalisation manager (REQ-P1-UI-021, -022; F5/F6).

``LanguageManager`` selects the UI language from the system :class:`QLocale`
(falling back to English, CL-14), installs the matching :class:`QTranslator` on
the application, and can swap it at runtime. Installing/removing a translator
makes Qt post a :data:`QEvent.Type.LanguageChange` to every widget, which each
hand-built widget handles in ``changeEvent`` to re-set its ``tr()``-wrapped text
(live retranslation, no restart — F5).

The binary ``.qm`` catalogues are produced by AGT-07 (``ts-qm-build``); this
module only discovers and loads them, so it degrades gracefully to the built-in
English source strings when no catalogue is present.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QCoreApplication, QLocale, QObject, QTranslator, Signal

#: Language code used when no catalogue matches the locale (CL-14). English is
#: the source language of the ``tr()`` literals, so it needs no ``.qm`` file.
FALLBACK_LANGUAGE = "en"

#: Prefix of a compiled catalogue file, e.g. ``pixelart_es.qm`` (AGT-07 output).
_CATALOGUE_PREFIX = "pixelart_"
_CATALOGUE_SUFFIX = ".qm"


def _default_translations_dir() -> Path:
    """Return the repository ``i18n/`` directory holding the ``.qm`` catalogues.

    Derived portably from this file's location (``pixelart_creator/ui/i18n.py``)
    by walking up to the repository root, so no absolute path is baked in.
    """
    return Path(__file__).resolve().parent.parent.parent / "i18n"


class LanguageManager(QObject):
    """Installs/swaps the application :class:`QTranslator` by language code.

    Args:
        app: The running application (``QApplication``/``QCoreApplication``)
            the translator is installed on.
        translations_dir: Directory holding ``pixelart_<code>.qm`` catalogues.
            Defaults to the repository ``i18n/`` folder (resolved portably).
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
        super().__init__(parent)
        self._app = app
        self._dir = (
            Path(translations_dir) if translations_dir else _default_translations_dir()
        )
        self._translator = QTranslator(self)
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
            self.languageChanged.emit(self._current)
            return True

        loaded = self._translator.load(f"{_CATALOGUE_PREFIX}{code}", str(self._dir))
        if not loaded:
            # No catalogue on disk yet: stay on the English source strings.
            self._current = FALLBACK_LANGUAGE
            self.languageChanged.emit(self._current)
            return False

        self._app.installTranslator(self._translator)
        self._current = code
        self.languageChanged.emit(self._current)
        return True
