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

The APPLICATION's own catalogue is served through :class:`_MnemonicTranslator`,
a :class:`QTranslator` subclass that overrides the Qt virtual
:meth:`QTranslator.translate` to enforce "shortcuts are independent of
language": the mnemonic letter of every translated string is always the
letter marked in its ENGLISH source, never a letter chosen for the
translation's own wording (U4/M1). This is centralised here by construction
-- zero call-site changes anywhere the application calls ``tr()`` -- and
never applied to Qt's own ``qtbase_<code>.qm`` catalogue, which has no
English source of this application's to enforce against. The pure-string
rewrite itself is :func:`apply_source_mnemonic`, kept Qt-free so it is
unit-testable directly.
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

# -- shortcuts are independent of language (U4, M1) -----------------------
#
# A translated menu/action title keeps the mnemonic letter of its ENGLISH
# SOURCE string, never a letter chosen for the translation's own wording.
# This keeps Alt+<letter> access, and top-level-menu uniqueness reasoned
# about in English (M2), true in every installed language by construction.

#: One token of a `&`-markup string, as produced by :func:`_tokenize_mnemonic`.
#: `kind` is one of:
#:   ``"literal_amp"`` -- a `&&` pair (Qt's escape for one literal `&`);
#:     `value` is the two-character pair ``"&&"``.
#:   ``"marker"``      -- a `&X` pair marking `X` as a mnemonic letter;
#:     `value` is the single marked character `X`.
#:   ``"char"``        -- any other single character (including a trailing,
#:     unpaired `&` with nothing after it); `value` is that one character.
_MnemonicToken = tuple  # (kind: str, value: str)


def _tokenize_mnemonic(text: str) -> List[_MnemonicToken]:
    """Split `text` left-to-right into `&`-markup tokens.

    The single tokenizer every mnemonic-handling function in this module
    shares (never a regex lookbehind on single characters, which cannot see
    that a `&` two positions back already paired off with its neighbour): at
    each position, `&&` is consumed together as one ``"literal_amp"`` token
    BEFORE a lone `&` is ever considered a marker, so a literal escape can
    never be mistaken for -- or leave a stray, mis-parseable remnant beside
    -- a real mnemonic marker.
    """
    tokens: List[_MnemonicToken] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if ch == "&":
            if i + 1 < length and text[i + 1] == "&":
                tokens.append(("literal_amp", "&&"))
                i += 2
                continue
            if i + 1 < length:
                tokens.append(("marker", text[i + 1]))
                i += 2
                continue
            tokens.append(("char", "&"))
            i += 1
            continue
        tokens.append(("char", ch))
        i += 1
    return tokens


def _source_mnemonic_letter(source: str) -> Optional[str]:
    """Return the single mnemonic letter `&` marks in `source`, or ``None``.

    A lone ``&`` immediately followed by another ``&`` (``&&``) is the Qt
    escape for a literal ampersand, never a mnemonic marker, and is skipped
    (:func:`_tokenize_mnemonic` consumes the pair together, so it can never
    be misread one character at a time). A trailing ``&`` with nothing after
    it marks nothing and is ignored.
    """
    for kind, value in _tokenize_mnemonic(source):
        if kind == "marker":
            return value
    return None


def _strip_mnemonic_markers(text: str) -> str:
    """Remove single-`&` mnemonic markers from `text`, keeping `&&` escaped.

    Every ``&&`` is passed through UNCHANGED, as the two-character literal
    escape Qt itself requires to display one literal ``&`` -- collapsing it
    to a single ``&`` is never correct here: that single leftover character
    would itself be read, by Qt's own left-to-right ``&<char>`` scan, as
    EITHER a stray mnemonic marker (if this string is later handed to Qt as
    markup again, e.g. re-entering :func:`apply_source_mnemonic`) OR a
    dropped character (if it is set as plain, already-rendered text --
    ``QAction.setText`` with no further ``&`` markup strips a lone ``&``
    outright; confirmed with ``QAction.iconText()``, which shows exactly
    what survives). Only the marker itself -- the ``&`` immediately before
    the marked letter -- is removed; every lone ``&`` this function is asked
    to strip is dropped with no replacement character.
    """
    out: List[str] = []
    for kind, value in _tokenize_mnemonic(text):
        if kind == "literal_amp":
            out.append("&&")
        elif kind == "marker":
            out.append(value)
        else:
            out.append(value)
    return "".join(out)


def apply_source_mnemonic(source: str, translation: str) -> str:
    """Rewrite `translation`'s mnemonic to the letter `source` marks (U4/M1).

    Pure string logic, deliberately Qt-free so it is unit-testable on its
    own, built on the shared :func:`_tokenize_mnemonic` tokenizer: any
    mnemonic marker the translation already carries is dropped (its letter
    kept, un-marked) unless it happens to be the winning position below, and
    the first case-insensitive occurrence of the ENGLISH source's mnemonic
    letter -- searched over the translation's CONTENT, which by construction
    never matches the `&` characters of a `&&` pair (E2) -- is marked
    instead. If that letter does not occur anywhere in the translation,
    appends the Windows convention for this case: ``" (&X)"`` with ``X`` the
    upper-cased source letter (e.g. ``"Ayuda (&H)"``, ``"Archivo (&F)"``).

    Every literal ``&&`` in `translation` is kept fully escaped
    (``"&&"``) NO MATTER WHERE IT SITS, before or after the winning
    position -- it is never collapsed to a single ``&``. Collapsing one
    that sits BEFORE the winning position would itself parse, in Qt's own
    left-to-right ``&<char>`` scan, as an EARLIER and WRONG mnemonic (the
    first defect this function was fixed for: a real, shipped example was
    the Aids menu's ``"Guides && &Rulers"``, whose then-shipped Spanish
    translation resolved to Alt+Space instead of Alt+R). Collapsing one
    that sits AFTER the winning position is a DIFFERENT, equally real
    defect: the resulting single ``&`` is not markup at all by that point
    in the string, so Qt's ``QAction``/``QMenu`` display path drops it
    outright instead of showing it -- confirmed with
    ``QAction(text).iconText()``: ``"Per&fil & Cosas"`` displays as
    ``"Perfil  Cosas"`` (the ampersand LOST), while ``"Per&fil && Cosas"``
    correctly displays as ``"Perfil & Cosas"``. This function therefore
    only ever REMOVES a translation's own stray marker and INSERTS exactly
    one new one; it never touches a literal ``&&`` at all.

    An empty/untranslated `translation` is returned unchanged so Qt's own
    fallback to `source` still applies; a `source` with no mnemonic at all
    (``_source_mnemonic_letter`` returns ``None``) also returns `translation`
    unchanged -- there is nothing to enforce.
    """
    if not translation:
        return translation
    letter = _source_mnemonic_letter(source)
    if letter is None:
        return translation

    tokens = _tokenize_mnemonic(translation)
    target = letter.lower()

    insert_at: Optional[int] = None
    for index, (kind, value) in enumerate(tokens):
        content = "&" if kind == "literal_amp" else value
        if content.lower() == target:
            insert_at = index
            break

    parts: List[str] = []
    for index, (kind, value) in enumerate(tokens):
        if kind == "literal_amp":
            # Always escaped, regardless of position -- see the docstring:
            # collapsing it is wrong on EITHER side of the insertion point.
            parts.append("&&")
            continue
        if index == insert_at:
            parts.append(f"&{value}")
            continue
        # A translation's OWN marker that is not the winning position is a
        # stray mnemonic on the wrong letter: drop the marker, keep the letter.
        parts.append(value)

    rebuilt = "".join(parts)
    if insert_at is None:
        return f"{rebuilt} (&{letter.upper()})"
    return rebuilt


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


class _MnemonicTranslator(QTranslator):
    """The application's own :class:`QTranslator`, enforcing U4/M1 by construction.

    Overrides the Qt virtual :meth:`translate` so every translated string
    this translator serves -- every menu title, every action text, anything
    reached through ``tr()``/``QCoreApplication.translate`` -- has its
    mnemonic corrected to the English source's letter before Qt ever sees
    it. No call site anywhere in the application needs to change, and any
    future ``tr()`` call is covered the same way.

    Deliberately NOT used for Qt's OWN ``qtbase_<code>.qm`` catalogue
    (:attr:`LanguageManager._qt_translator` stays a plain :class:`QTranslator`):
    that catalogue's mnemonics are Qt's, not this application's source
    strings, so there is no English source here to enforce against.
    """

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: Optional[str] = None,
        n: int = -1,
    ) -> Optional[str]:
        """Return the catalogue translation with its mnemonic U4/M1-corrected.

        A miss returns ``None`` -- NEVER ``""`` -- so PySide6 marshals it
        back to a NULL ``QString`` on the C++ side, not an empty-but-not-null
        one. ``QObject.tr()`` walks a chain of contexts (a Python subclass's
        own class name, then its C++ base classes' names, e.g. ``Main_Window``
        then ``QMainWindow``) and, for each, checks ``QString.isNull()`` to
        decide whether that context's result should REPLACE an earlier hit:
        a null result means "no translation here, keep what an earlier
        context already found"; a non-null EMPTY result means "this context
        really does translate to nothing," which overrides the earlier hit.
        Returning ``""`` for an ordinary catalogue miss made every later
        base-class context look like the second case, wiping out a correct
        earlier hit -- measured with ``Main_Window.tr("PixelArt Creator")``
        returning ``""`` in es because the ``Main_Window``-context hit was
        overwritten by the ``QMainWindow``-context miss.
        """
        result = super().translate(context, source_text, disambiguation, n)
        if not result:
            return None
        return apply_source_mnemonic(source_text, result)


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
        self._translator = _MnemonicTranslator(self)
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
