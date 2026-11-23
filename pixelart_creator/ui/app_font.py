# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The bundled pixel typeface: registration, application and the system-font switch.

Nifen Art (Regular and Bold, one 12 px em) is the interface font
(``REQ-VI-UI-013``). This module is the one place that

* registers the bundled font files with Qt (Nifen Art, Regular and Bold, and the
  six Nifen Art CJK files), logging and degrading to the platform font when a
  file cannot be read (``REQ-VI-BUILD-006``);
* gives the application font, and each platform per-class font it puts back, the
  family chain of the active language, through :func:`chain_font`
  (``REQ-L10N-UI-009`` to ``-012``);
* captures the platform's own default font once, before the application first
  changes it, so "Use system font" can restore exactly that font without the
  application ever naming a platform family (``REQ-VI-UI-016``);
* builds the interface font: Nifen Art at its em size, no smoothing, no hinting
  adjustments (``REQ-VI-UI-014``);
* installs the family substitutions that let a character Nifen Art lacks be
  drawn from the platform's fallback fonts, character by character
  (``REQ-VI-UI-015``);
* applies the chosen font to the whole application, and re-applies it when
  Qt has put the platform's per-class fonts back.

Why the font is applied *after* the style sheet. The platform theme gives a few
widget classes a font of their own (on Windows: item views, menus, the menu
bar, the status bar, tool tips, dock titles). ``QApplication.setFont`` clears
those entries, but the first ``QApplication.setStyleSheet`` (which installs the
style-sheet style) and every ``setStyle`` write them back. An item view then
draws its rows in the platform font, anti-aliased with the platform's
sub-pixel (ClearType) text, which shows up as blue and yellow colour fringes
around every glyph. Applying the font after the style sheet, and checking it
again after each theme change, keeps those entries cleared. The check is
:func:`ensure_interface_font`.

Why combo boxes get a point-sized copy of the interface font on Windows 11. Qt's
``windows11`` style sizes the drop-down arrow and the popup of a combo box from
``widget.font().pointSize()``. The interface font is set by pixel size, so that
is ``-1`` and Qt reports ``QFont::setPointSize: Point size <= 0 (-1)`` the first
time a combo box is measured or opened. :func:`_combo_point_font` hands
``QComboBox`` a font that is the same font at the same size in points, which
resolves to the same pixel size, so nothing is drawn differently and Qt is given
a size it can use.

The module binds to no domain logic (S11): it is Qt font plumbing only.
"""

from __future__ import annotations

import functools
import itertools
import logging
import operator
from collections.abc import Sequence
from importlib import resources
from typing import Dict, Final, FrozenSet, List, Optional, Tuple

from PySide6.QtCore import QByteArray, QLocale
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QFontMetrics, QRawFont
from PySide6.QtWidgets import QApplication, QWidget

import pixelart_creator.logic.constants as logic_constants
import pixelart_creator.logic.font_chain as font_chain
import pixelart_creator.logic.language_names as language_names
import pixelart_creator.ui.i18n as i18n
from pixelart_creator.ui.theme import _UI_FONT_FALLBACKS

__all__ = [
    "NIFEN_ART_FAMILY",
    "NIFEN_ART_EM_PX",
    "register_app_fonts",
    "nifen_art_available",
    "capture_platform_font",
    "platform_default_font",
    "interface_font",
    "role_base_font",
    "install_font_substitutions",
    "apply_interface_font",
    "prepare_interface_font",
    "ensure_interface_font",
    "resolved_family",
    "round_to_em",
    "primary_holds_cjk",
    "chain_font",
    "chained_font",
]

_LOGGER = logging.getLogger(__name__)

#: The family name the bundled font files register under.
NIFEN_ART_FAMILY: Final[str] = "Nifen Art"

#: The typeface's em size in logical pixels. Every legible size is a whole
#: multiple of it (``REQ-VI-UI-014``); the interface font is exactly one em.
NIFEN_ART_EM_PX: Final[int] = 12

#: Package data holding the font files (``pixelart_creator/fonts/``).
_FONT_PACKAGE: Final[str] = "pixelart_creator"
_FONT_SUBDIR: Final[str] = "fonts"
_FONT_FILES: Final[Tuple[str, ...]] = (
    "NifenArt-Regular.ttf",
    "NifenArt-Bold.ttf",
    "NifenArtCJKJP-Regular.ttf",
    "NifenArtCJKJP-Bold.ttf",
    "NifenArtCJKSC-Regular.ttf",
    "NifenArtCJKSC-Bold.ttf",
    "NifenArtCJKKR-Regular.ttf",
    "NifenArtCJKKR-Bold.ttf",
)

#: Widget classes the platform theme may give a font of their own. The names are
#: the ones Qt keys its per-class font table by.
_PLATFORM_CLASS_FONTS: Final[Tuple[str, ...]] = (
    "QAbstractItemView",
    "QListView",
    "QHeaderView",
    "QMenu",
    "QMenuBar",
    "QStatusBar",
    "QTipLabel",
    "QDockWidgetTitle",
    "QMdiSubWindowTitleBar",
    "QTitleBar",
    "QMessageBoxLabel",
    "QLabel",
    "QPushButton",
    "QToolButton",
    "QCheckBox",
    "QRadioButton",
    "QComboLineEdit",
    "QComboMenuItem",
)

#: The class Qt's ``windows11`` style reads a point size from (see the module
#: docstring), and the name that style reports.
_COMBO_CLASS: Final[str] = "QComboBox"
_WINDOWS11_STYLE: Final[str] = "windows11"

#: Registered application-font ids, in :data:`_FONT_FILES` order.
_registered_ids: List[int] = []
#: The platform's default font and per-class fonts, captured once.
_platform: Dict[str, object] = {"font": None, "classes": None, "style": None}
_substitutions_installed = False
#: ``primary_holds_cjk`` answers, by (family, registered-font count).
_holds_cjk_cache: Dict[Tuple[str, int], bool] = {}

#: The style-strategy flags a family-list tag may be built from, in the order the
#: table below lists them. All four were kept on Linux, Windows and macOS; they
#: name the choice between outline and bitmap fonts or the size to match, so on an
#: outline face they select nothing different, yet Qt's font cache keys on them.
_CHAIN_TAG_FLAGS: Final[Tuple[QFont.StyleStrategy, ...]] = (
    QFont.StyleStrategy.PreferMatch,
    QFont.StyleStrategy.PreferQuality,
    QFont.StyleStrategy.PreferOutline,
    QFont.StyleStrategy.ForceOutline,
)

#: One entry per tag: the non-empty combinations of :data:`_CHAIN_TAG_FLAGS`,
#: fewest flags first and, within one size, in the order of the flags above. Tag
#: ``n`` (counted from one) is entry ``n - 1``. The length is the capacity of
#: :data:`_CHAIN_TAG_REGISTRY`.
_CHAIN_TAG_STRATEGIES: Final[Tuple[QFont.StyleStrategy, ...]] = tuple(
    functools.reduce(operator.or_, combination)
    for combination in itertools.chain.from_iterable(
        itertools.combinations(_CHAIN_TAG_FLAGS, size)
        for size in range(len(_CHAIN_TAG_FLAGS) + 1)
    )
    if combination
)

#: Every flag any tag uses; cleared from a base font before its tag is set.
_CHAIN_TAG_MASK: Final[QFont.StyleStrategy] = functools.reduce(
    operator.or_, _CHAIN_TAG_FLAGS
)

#: The module's one registry of chain tags (see :func:`chain_font`).
_CHAIN_TAG_REGISTRY: Final[font_chain.ChainTagRegistry] = font_chain.ChainTagRegistry(
    len(_CHAIN_TAG_STRATEGIES)
)


def _font_bytes(file_name: str) -> Optional[bytes]:
    """Return the bytes of a bundled font file, or ``None`` when unreadable."""
    try:
        node = resources.files(_FONT_PACKAGE) / _FONT_SUBDIR / file_name
        return node.read_bytes()
    except (OSError, ModuleNotFoundError, FileNotFoundError) as exc:
        _LOGGER.log(logging.WARNING, "bundled font %s unreadable: %s", file_name, exc)
        return None


def _still_registered() -> bool:
    """Return whether every id in :data:`_registered_ids` is still valid."""
    return bool(_registered_ids) and all(
        QFontDatabase.applicationFontFamilies(font_id) for font_id in _registered_ids
    )


def register_app_fonts() -> bool:
    """Register the bundled font files; return whether Nifen Art is usable.

    The files are the two Nifen Art files and the six Nifen Art CJK files (the
    Japanese, Simplified Chinese and Korean families, Regular and Bold). A file
    that is missing, unreadable or rejected by Qt is logged and skipped;
    nothing is raised, so a damaged install keeps the platform font instead of
    stopping the application (the same degrade as ``app_icon``). Safe to call
    more than once: a registration that is still valid is not repeated.
    """
    if _still_registered():
        return nifen_art_available()
    _registered_ids.clear()
    for file_name in _FONT_FILES:
        data = _font_bytes(file_name)
        if data is None:
            continue
        font_id = QFontDatabase.addApplicationFontFromData(QByteArray(data))
        if font_id < 0:
            _LOGGER.log(logging.WARNING, "Qt rejected the bundled font %s", file_name)
            continue
        _registered_ids.append(font_id)
    return nifen_art_available()


def nifen_art_available() -> bool:
    """Return whether the Nifen Art family is registered with Qt."""
    return any(
        NIFEN_ART_FAMILY in QFontDatabase.applicationFontFamilies(font_id)
        for font_id in _registered_ids
    )


def _class_font(name: str) -> QFont:
    """Return the font Qt gives widgets of class ``name``.

    PySide6 takes the class name as ``str`` at run time although its type stubs
    declare ``bytes``.
    """
    return QApplication.font(name)  # type: ignore[call-overload]


def capture_platform_font() -> QFont:
    """Capture the platform's default fonts once, before the first change.

    The first call wins: it stores the application font and the per-class
    fonts exactly as the platform gave them. Later calls return the stored
    font. Call it right after the application object exists.
    """
    if _platform["font"] is None:
        font = QApplication.font()
        _platform["font"] = QFont(font)
        _platform["style"] = QApplication.style().objectName()
        classes: Dict[str, QFont] = {}
        for name in _PLATFORM_CLASS_FONTS:
            class_font = _class_font(name)
            if class_font != font:
                classes[name] = QFont(class_font)
        _platform["classes"] = classes
    return platform_default_font()


def platform_default_font() -> QFont:
    """Return a copy of the platform's default font (captured on first use)."""
    stored = _platform["font"]
    if not isinstance(stored, QFont):
        return capture_platform_font()
    return QFont(stored)


def _nifen_font() -> QFont:
    """Return the Nifen Art base font: one family, one em, no smoothing, no hinting."""
    font = QFont(NIFEN_ART_FAMILY)
    font.setPixelSize(NIFEN_ART_EM_PX)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def interface_font() -> QFont:
    """Return the interface font: Nifen Art, one em, no smoothing, no hinting.

    The font carries the family chain of the language now active (Nifen Art, then
    the Han family of the right form, then the Hangul family), built by
    :func:`_chained`. Nifen Art holds no Han and no Hangul character (the frozen
    face, asserted by the font checks), so the chain is the one with the CJK families
    behind it and no measurement is needed.
    """
    return _chained(_nifen_font(), primary_holds=False)


def role_base_font(use_system_font: bool, class_name: str) -> QFont:
    """Return the font a widget class's chain is built from, before any chain.

    In: ``use_system_font`` as the appearance preference holds it, and the Qt
    class name of the widget (``"QMenu"``).

    Out: a copy that carries one family and no chain tag. In the platform-font
    mode (also when Nifen Art is not registered) it is the font the platform gave
    that class, or the platform's default font when it gave the class none of its
    own; otherwise it is the Nifen Art base font. Its family is therefore the
    role's primary family, which ``family()`` of the application's or a widget's
    font is not once a chain is applied.
    """
    stored = platform_default_font()
    if _uses_platform_font(use_system_font):
        classes = _platform["classes"]
        if isinstance(classes, dict) and class_name in classes:
            return QFont(classes[class_name])
        return stored
    return _nifen_font()


def install_font_substitutions() -> None:
    """Let characters Nifen Art lacks fall back to the platform's fonts.

    The substitution list is the platform's own default family (taken from the
    captured snapshot, never named here) followed by the application's existing
    cross-platform fallback chain. Installed once per process.
    """
    global _substitutions_installed
    if _substitutions_installed:
        return
    chain: List[str] = [platform_default_font().family()]
    for fallbacks in _UI_FONT_FALLBACKS.values():
        for family in fallbacks:
            if family not in chain:
                chain.append(family)
    QFont.insertSubstitutions(NIFEN_ART_FAMILY, chain)
    _substitutions_installed = True


def chain_font(base: QFont, families: Sequence[str]) -> QFont:
    """Return a copy of ``base`` that draws with the family list ``families``.

    The one place in ``ui/`` where a family list is put on a font. Qt's font cache
    does not tell two fonts apart by the families after the first, so a list of
    two or more families also gets a tag (from :data:`_CHAIN_TAG_REGISTRY`)
    carried in the style strategy: every tag flag is cleared from the base's
    strategy first, so a base that already carried one cannot mask the tag, and
    then the list's flags are set. A one-family list has no later families to
    share and gets no flag.

    When more lists share the first family than there are tags, a warning names
    the family and the list and the result is the first family alone, with no
    flag: degraded and visible, and never an untagged list, which would hand its
    later families to any one-family font of the same first family.

    Raises:
        ValueError: ``families`` is empty.
    """
    font = QFont(base)
    font.setFamilies(list(families))
    strategy = font.styleStrategy() & ~_CHAIN_TAG_MASK
    try:
        tag = _CHAIN_TAG_REGISTRY.tag_for(families)
    except font_chain.ChainTagsExhausted as exc:
        _LOGGER.log(
            logging.WARNING,
            "no chain tag left for %r, drawing %r alone instead of %s",
            exc.family,
            families[0],
            list(families),
        )
        font.setFamilies([families[0]])
        tag = None
    if tag is not None:
        strategy |= _CHAIN_TAG_STRATEGIES[tag - 1]
    font.setStyleStrategy(strategy)
    return font


@functools.lru_cache(maxsize=None)
def _cjk_code_points(families: Tuple[str, ...]) -> FrozenSet[int]:
    """Return the Han and Hangul code points the families ``families`` hold.

    Cached by the names, so the answer changes when a face gets registered (the
    key then names more families) and is otherwise computed once.
    """
    held: set[int] = set()
    for family in families:
        raw = QRawFont.fromFont(chain_font(QFont(), (family,)))
        for first, last in (
            *logic_constants.HAN_RANGES,
            *logic_constants.HANGUL_RANGES,
        ):
            held.update(
                code_point
                for code_point in range(first, last + 1)
                if raw.supportsCharacter(code_point)
            )
    return frozenset(held)


def primary_holds_cjk(family: str) -> bool:
    """Return whether ``family`` alone would draw a shipped Han or Hangul character.

    The code points tested are the ones the registered bundled CJK families hold,
    so "holds" means "would steal a shipped character", not "holds some Han". The
    family is measured on its own with font merging off (no fallback family can
    answer for it). Before those faces are registered the set is empty and the
    answer is false, which is right: nothing shipped can be stolen yet.
    """
    present = set(QFontDatabase.families())
    shipped = tuple(
        name
        for name in (
            font_chain.CJK_SC_FAMILY,
            font_chain.CJK_JP_FAMILY,
            font_chain.CJK_HANGUL_FAMILY,
        )
        if name in present
    )
    held = _cjk_code_points(shipped)
    if not held:
        return False
    probe = chain_font(QFont(), (family,))
    probe.setStyleStrategy(probe.styleStrategy() | QFont.StyleStrategy.NoFontMerging)
    metrics = QFontMetrics(probe)
    return any(metrics.inFontUcs4(code_point) for code_point in sorted(held))


def _holds_cjk(family: str) -> bool:
    """Return :func:`primary_holds_cjk` for ``family``, measured once per state.

    The key is the family and the number of registered application fonts, so the
    answer is measured again when a face gets registered and is otherwise reused
    (every captured per-class font asks, on every application of the font).
    """
    key = (family, len(_registered_ids))
    if key not in _holds_cjk_cache:
        _holds_cjk_cache[key] = primary_holds_cjk(family)
    return _holds_cjk_cache[key]


def _chain_language() -> str:
    """Return the active interface language code, or English for an unknown one."""
    code = i18n.current_ui_language()
    if code not in language_names.ENDONYMS:
        return i18n.FALLBACK_LANGUAGE
    return code


def _chained(font: QFont, primary_holds: Optional[bool] = None) -> QFont:
    """Return ``font`` drawn with the family chain of the active language.

    The primary is the family of ``font``. ``primary_holds`` is the caller's
    answer to "does the primary draw a shipped Han or Hangul character"; ``None``
    measures it. The list comes from :func:`font_chain.family_chain` (the active
    interface language and the system language decide the Han form) and is put on
    the font by :func:`chain_font`, the one place a family list is set.
    """
    primary = font.family()
    holds = _holds_cjk(primary) if primary_holds is None else primary_holds
    families = font_chain.family_chain(
        primary, _chain_language(), QLocale.system().name(), holds
    )
    return chain_font(font, families)


def chained_font(font: QFont) -> QFont:
    """Return ``font`` drawn with the family chain of the active language.

    The public entry for callers outside this module (the guide's page font): the
    primary is measured, and the list is put on the font by :func:`chain_font`.

    In: a base font that carries one family, as :func:`platform_default_font` or
    a captured per-class font gives it. The function is not specified for a font
    that already carries a chain.

    Out: a copy; ``font`` is not mutated. Its families are the list the product's
    logic gives for the base's family under the active interface language and
    font mode: the CJK form family first when :func:`primary_holds_cjk` is true
    for that family, the family first otherwise. The style strategy carries the
    list's allocated tag, put there by :func:`chain_font` only. Equal inputs
    under the same language and mode give equal fonts (``QFont.__eq__``).

    This function never calls ``setFamilies`` or ``setFamily`` and never
    constructs a ``QFont`` from a family name.

    When the tags are exhausted the result is :func:`chain_font`'s, unchanged:
    the first family alone, with no tag flag.
    """
    return _chained(font)


def _uses_platform_font(use_system_font: bool) -> bool:
    """Return whether the platform's font (not Nifen Art) is the base font."""
    return use_system_font or not nifen_art_available()


def _target_font(use_system_font: bool) -> QFont:
    """Return the application font the preference asks for, with its chain."""
    if _uses_platform_font(use_system_font):
        return _chained(platform_default_font())
    return interface_font()


def _combo_needs_point_font() -> bool:
    """Return whether the platform style needs a point size for combo boxes.

    True when the style the application started with was Qt's ``windows11``
    style (read once, before a style sheet wraps it). Every other style leaves
    the interface font exactly as it is.
    """
    return _platform["style"] == _WINDOWS11_STYLE


def _combo_point_font() -> QFont:
    """Return the interface font with its size expressed in points.

    The point size is what :class:`QFontInfo` reports for the pixel-sized
    interface font, so it resolves back to the same pixel size; family, style
    strategy and hinting are the interface font's own.
    """
    font = interface_font()
    font.setPointSizeF(QFontInfo(font).pointSizeF())
    return font


def _set_combo_font(app: QApplication, font: QFont) -> None:
    """Give combo boxes ``font`` (the class name is ``str`` at run time)."""
    app.setFont(font, _COMBO_CLASS)  # type: ignore[arg-type]


def _combo_font_in_place() -> bool:
    """Return whether combo boxes already get the point-sized interface font."""
    return _class_font(_COMBO_CLASS).pointSizeF() > 0


def apply_interface_font(app: QApplication, use_system_font: bool) -> str:
    """Apply the interface font (or the platform font) to the whole application.

    Nifen Art when ``use_system_font`` is off and the family registered; the
    captured platform font otherwise (with the platform's per-class fonts put
    back, so the result is what the platform gave before the application first
    changed anything). Returns the family now in effect.
    """
    install_font_substitutions()
    font = _target_font(use_system_font)
    app.setFont(font)
    if _uses_platform_font(use_system_font):
        classes = _platform["classes"]
        if isinstance(classes, dict):
            for name, class_font in classes.items():
                app.setFont(_chained(class_font), name)
        if _combo_needs_point_font():
            _set_combo_font(app, font)
    elif _combo_needs_point_font():
        _set_combo_font(app, _combo_point_font())
    # Widgets that already exist keep the font the style sheet gave them when it
    # was installed; setting the same sheet again re-resolves their fonts from
    # the (now clean) per-class table.
    sheet = app.styleSheet()
    if sheet:
        app.setStyleSheet(sheet)
    return app.font().family()


def prepare_interface_font(app: QApplication, use_system_font: bool) -> str:
    """Register, capture and apply the interface font before a window exists.

    Qt tells a top-level window that already exists about an application font
    change only once the event loop runs. A window built first would keep the
    platform font and give it to every child, and on a platform with no
    per-class fonts (Linux, offscreen) nothing would put it right. Call this
    before constructing the first window; :func:`ensure_interface_font` still
    runs after each style sheet. Returns the family now in effect.
    """
    register_app_fonts()
    capture_platform_font()
    return apply_interface_font(app, use_system_font)


def _class_fonts_follow_application() -> bool:
    """Return whether no per-class font differs from the application font."""
    base = QApplication.font()
    return all(_class_font(name) == base for name in _PLATFORM_CLASS_FONTS)


def ensure_interface_font(app: QApplication, use_system_font: bool) -> None:
    """Re-apply the font only when Qt has changed it behind our back.

    Cheap enough to call after every theme change: nothing is touched when the
    application font is the wanted one and, for Nifen Art, no per-class font
    has come back.
    """
    wanted = _target_font(use_system_font)
    if app.font() != wanted:
        apply_interface_font(app, use_system_font)
        return
    nifen = not _uses_platform_font(use_system_font)
    if nifen and not _class_fonts_follow_application():
        apply_interface_font(app, use_system_font)
        return
    if nifen and _combo_needs_point_font() and not _combo_font_in_place():
        apply_interface_font(app, use_system_font)


def resolved_family(widget: QWidget) -> str:
    """Return the family the widget's font actually resolves to."""
    return QFontInfo(widget.font()).family()


def round_to_em(pixels: float) -> int:
    """Round a pixel size to the nearest whole multiple of the em (at least one)."""
    multiples = int(pixels / NIFEN_ART_EM_PX + 0.5)
    return max(1, multiples) * NIFEN_ART_EM_PX
