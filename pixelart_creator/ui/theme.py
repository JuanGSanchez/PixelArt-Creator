# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Styles x modes, the app stylesheet and canvas roles (REQ-P1-UI-025; ADR-0069).

Colours are defined **once per role** in the shipped style data
(``pixelart_creator/themes/``, read through
:mod:`pixelart_creator.data.style_catalog`); nothing here carries a colour
literal. A *style* (``washi-kintsugi``, ``edo-night`` ...) times a *mode*
(``light``/``dark``) selects one role map. The functions keep their historic
positional shape: a mode name first, the style an optional second argument that
defaults to the catalogue's default style.

:func:`build_qss` composes the **one** application stylesheet: frames for the
full control set are ``border-image`` rules over PNG files generated at run
time from the role-indexed templates (:mod:`pixelart_creator.ui.theme_art_files`),
at the art scale S = :func:`art_scale` -- the highest whole-number
device-pixel ratio among all screens. There is **no** ``:focus`` rule (the focus
ring is an overlay, :mod:`pixelart_creator.ui.pixel_chrome`), **no**
``font-family``, **no** ``font-size``; the sole font declaration is
``QDockWidget { font-weight: bold; }``. The canvas background/grid colours are
exposed as :class:`QColor` roles for
:class:`~pixelart_creator.ui.canvas_scene.CanvasScene` (which paints them
outside QSS). Both modes keep the canvas checker/grid legible (025).
"""

from __future__ import annotations

import math
from typing import Dict, List, Mapping, Optional, Tuple

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QFont, QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication

from pixelart_creator.data import style_catalog
from pixelart_creator.ui.pixel_chrome import (
    SWATCH_PROPERTY,
    chrome_filter,
    set_active_theme,
)
from pixelart_creator.ui.theme_art_files import ArtSet, art_set

THEME_LIGHT = "light"
THEME_DARK = "dark"

STYLE_WASHI_KINTSUGI = "washi-kintsugi"
STYLE_EDO_NIGHT = "edo-night"
STYLE_ARCADE_KIKKO = "arcade-kikko"

# The defaults, read from ``themes/index.json`` (not typed here).
DEFAULT_STYLE: str = style_catalog.default_style()
DEFAULT_MODE: str = style_catalog.default_mode()

# Cross-OS UI-font fallback chain (REQ-P13-UI-001). Defined
# **once, by role** here (never per-widget): the UI names no specific family (the
# QSS below carries no ``font-family`` and the app sets no :class:`QFont`), so each
# OS already resolves its own default system UI font. This map is the belt-and-
# braces guard for the single-OS families that a platform default *reports* as its
# name (e.g. Windows "Segoe UI", macOS ".AppleSystemUIFont"/"Helvetica Neue"): if
# such a family is ever requested on an OS that lacks it (a cross-OS project theme,
# a future stylesheet, a canvas glyph label), Qt substitutes the first available
# entry instead of rendering ``.notdef`` boxes. Where the named family exists (its
# native OS) Qt uses it directly, so this changes nothing on the platform that owns
# the font — it only adds a resolvable fallback on the others. The tail generics
# are resolved by the Qt platform plugin to a present family on every OS.
_UI_FONT_FALLBACKS: Dict[str, List[str]] = {
    "Segoe UI": [
        "Helvetica Neue",
        "Cantarell",
        "Noto Sans",
        "DejaVu Sans",
        "sans-serif",
    ],
    ".AppleSystemUIFont": [
        "Segoe UI",
        "Cantarell",
        "Noto Sans",
        "DejaVu Sans",
        "sans-serif",
    ],
    "SF Pro Text": ["Segoe UI", "Cantarell", "Noto Sans", "DejaVu Sans", "sans-serif"],
    "Helvetica Neue": [
        "Segoe UI",
        "Cantarell",
        "Noto Sans",
        "DejaVu Sans",
        "sans-serif",
    ],
}

# Structural, not tuning (ADR-0001): a device-pixel ratio is whole when within
# this of an integer, so ``ceil`` never turns 2.0000000001 into 3.
_DPR_EPSILON = 1e-3
_MIN_ART_SCALE = 1
# Qt scales a stretched edge with a smooth filter that is exact only when one
# art pixel is at least this many device pixels; at 1 it can differ from the
# tiled picture by 1/255 in one channel. A rule whose frame is compared cell
# for cell stretches from this scale up (the dock body); the canvas and tab
# page frames are not compared that way and stretch at every scale.
_STRETCH_EXACT_MIN_SCALE = 2

# Stylesheet geometry in logical px. The frame widths come from the templates'
# own slices (``ArtSet.border_image``); these are the paddings and sub-control
# sizes the measured rules need.
_BUTTON_PADDING = "2px 4px"
_TAB_PADDING = "1px 6px"
_TAB_GAP_PX = 3
_TOOLBAR_SPACING_PX = 4
_DOCK_TITLE_PADDING = "1px 4px"
_FIELD_PADDING = "0px 2px"
_COMBO_PADDING = "0px 2px 0px 4px"
_SPIN_BUTTON_WIDTH_PX = 8
_SPIN_BUTTON_HEIGHT_PX = 6
_SPIN_TEXT_GAP_PX = 2
_COMBO_DROP_WIDTH_PX = 8
_CHECK_INDICATOR_PX = 14
_CHECK_CLEARANCE_PX = 4
_SLIDER_CLEARANCE_PX = 2
_MENU_ITEM_PADDING = "3px 18px 3px 22px"
_MENU_BAR_ITEM_PADDING = "3px 8px"
_MENU_INDICATOR_LEFT_PX = 4
_MENU_SEPARATOR_MARGIN = "2px 4px"
_HEADING_PADDING = "2px 6px"
_HEADER_PADDING = "2px 4px"
_ITEM_VIEWS = "QListView, QTreeView, QTableView"
_ITEM_VIEWS_ITEM_SELECTED = (
    "QListView::item:selected, QTreeView::item:selected, "
    "QTableView::item:selected, QComboBox QAbstractItemView::item:selected"
)
_TEXT_FIELDS = "QLineEdit, QTextEdit, QPlainTextEdit, QGraphicsView"


def available_themes() -> List[str]:
    """Return the selectable modes (``light``, ``dark``)."""
    return list(style_catalog.mode_ids())


def available_styles() -> List[str]:
    """Return the shipped style ids in menu order."""
    return list(style_catalog.style_ids())


def _roles(name: str, style: str = DEFAULT_STYLE) -> Dict[str, str]:
    """Return a copy of the role map of mode ``name`` in ``style``.

    Raises:
        ValueError: If the mode (or the style) is unknown.
    """
    try:
        return style_catalog.role_map(style, name)
    except style_catalog.StyleCatalogError:
        if style not in style_catalog.style_ids():
            raise ValueError(
                #: %1 is the internal style name that could not be found.
                QCoreApplication.translate("theme", "unknown style: %1").replace(
                    "%1", str(style)
                )
            ) from None
        raise ValueError(
            QCoreApplication.translate("theme", "unknown theme: %1").replace(
                "%1", str(name)
            )
        ) from None


def role_map(mode: str, style: str = DEFAULT_STYLE) -> Mapping[str, str]:
    """Return the role map (role key to colour text) of ``mode`` in ``style``."""
    return _roles(mode, style)


def role_colour(mode: str, role: str, style: str = DEFAULT_STYLE) -> QColor:
    """Return the colour of ``role`` in ``mode`` and ``style`` as a :class:`QColor`."""
    return QColor(_roles(mode, style)[role])


def art_scale() -> int:
    """Return the art scale: the highest whole-number DPR among all screens.

    ``max`` over :meth:`QGuiApplication.screens` of the ceiling of each screen's
    device-pixel ratio; ``1`` when there is no screen. Under a rounding policy
    every ratio is already whole, so the ceiling is the identity; under
    ``PassThrough`` it over-samples rather than under-samples, which is the
    measured lesser softness (ADR-0069 amendment).
    """
    screens = QGuiApplication.screens()
    if not screens:
        return _MIN_ART_SCALE
    return max(
        _MIN_ART_SCALE,
        max(math.ceil(s.devicePixelRatio() - _DPR_EPSILON) for s in screens),
    )


def _frame_rules(art: ArtSet, r: Mapping[str, str]) -> str:
    bi = art.border_image
    return f"""
QDockWidget {{
    font-weight: bold;
    color: {r["title_text"]};
    titlebar-close-icon: {art.url("glyph_close")};
    titlebar-normal-icon: {art.url("glyph_float")};
}}
QDockWidget::title {{
    {bi("dock_title")}
    padding: {_DOCK_TITLE_PADDING};
    text-align: left;
}}
QDockWidget::close-button, QDockWidget::float-button {{
    background: transparent;
    border: none;
    padding: 0px;
}}
QFrame#DockBody {{
    {bi("dock_body", large=art.scale >= _STRETCH_EXACT_MIN_SCALE)}
    background: transparent;
}}
QDialog {{
    {bi("dialog")}
}}
QLabel#dialogHeading {{
    {bi("heading")}
    background: transparent;
    color: {r["title_text"]};
    padding: {_HEADING_PADDING};
}}
QToolBar {{
    {bi("panel")}
    background: transparent;
    spacing: {_TOOLBAR_SPACING_PX}px;
}}
QTabWidget::pane {{
    {bi("panel", large=True)}
}}
"""


def _swatch_rules(r: Mapping[str, str]) -> str:
    """Exempt data-colour swatch buttons from the button frame (one stylesheet).

    A swatch shows the user's colour, which is data, not a theme role. The rules
    follow the framed ``QPushButton`` ones (the same specificity, so later wins)
    and restate each state so a hover or press keeps the plain outline;
    ``Swatch_Button.paintEvent`` paints the colour.
    """
    states = ("", ":hover", ":pressed", ":checked")
    selector = ", ".join(f'QPushButton[{SWATCH_PROPERTY}="true"]{s}' for s in states)
    return f"""{selector} {{
    border-image: none;
    border: 1px solid {r["border"]};
    background: transparent;
    color: {r["text"]};
}}
"""


def _button_rules(art: ArtSet, r: Mapping[str, str]) -> str:
    bi = art.border_image
    return f"""
QPushButton, QToolButton {{
    {bi("button_normal")}
    background: transparent;
    color: {r["text"]};
    padding: {_BUTTON_PADDING};
}}
QPushButton:hover, QToolButton:hover {{
    {bi("button_hover")}
}}
QPushButton:checked, QToolButton:checked {{
    {bi("button_checked")}
    color: {r["accent_text"]};
}}
QPushButton:pressed, QToolButton:pressed {{
    {bi("button_pressed")}
    color: {r["text"]};
}}
QTabBar::tab {{
    {bi("button_normal")}
    background: transparent;
    color: {r["text"]};
    padding: {_TAB_PADDING};
    margin: 0px {_TAB_GAP_PX}px 0px 0px;
}}
QTabBar::tab:hover {{
    {bi("button_hover")}
}}
QTabBar::tab:selected {{
    {bi("button_checked")}
    color: {r["accent_text"]};
}}
{_swatch_rules(r)}"""


def _field_rules(art: ArtSet, r: Mapping[str, str]) -> str:
    bi = art.border_image
    ring = art.slices("field")[0]
    sub = art.slices("subbutton")[0]
    arrow_w, arrow_h = art.size("arrow_up")
    arrow_dw, arrow_dh = art.size("arrow_down")
    spin_pad_right = _SPIN_BUTTON_WIDTH_PX + 2 * sub + ring + _SPIN_TEXT_GAP_PX
    return f"""
{_TEXT_FIELDS} {{
    {bi("field")}
    background-color: {r["surface"]};
    color: {r["text"]};
    selection-background-color: {r["accent"]};
    selection-color: {r["accent_text"]};
    padding: {_FIELD_PADDING};
}}
QGraphicsView {{
    {bi("field", large=True)}
}}
{_ITEM_VIEWS} {{
    {bi("field")}
    background-color: {r["surface"]};
    color: {r["text"]};
    selection-background-color: {r["accent"]};
    selection-color: {r["accent_text"]};
    outline: 0;
}}
{_ITEM_VIEWS_ITEM_SELECTED} {{
    background-color: {r["accent"]};
    color: {r["accent_text"]};
    border: 1px solid {r["accent_text"]};
}}
QHeaderView::section, QTableCornerButton::section {{
    background-color: {r["surface"]};
    color: {r["text"]};
    border: 1px solid {r["border"]};
    padding: {_HEADER_PADDING};
}}
QSpinBox, QDoubleSpinBox {{
    {bi("field")}
    background-color: {r["surface"]};
    color: {r["text"]};
    padding: 0px {spin_pad_right}px 0px {_SPIN_TEXT_GAP_PX}px;
}}
QSpinBox QLineEdit, QDoubleSpinBox QLineEdit, QComboBox QLineEdit {{
    background: transparent;
    border: none;
    border-image: none;
    padding: 0px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: {_SPIN_BUTTON_WIDTH_PX}px;
    height: {_SPIN_BUTTON_HEIGHT_PX}px;
    margin: {ring}px {ring}px 0px 0px;
    {bi("subbutton")}
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: {_SPIN_BUTTON_WIDTH_PX}px;
    height: {_SPIN_BUTTON_HEIGHT_PX}px;
    margin: 0px {ring}px {ring}px 0px;
    {bi("subbutton")}
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: {art.url("arrow_up")};
    width: {arrow_w}px;
    height: {arrow_h}px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: {art.url("arrow_down")};
    width: {arrow_dw}px;
    height: {arrow_dh}px;
}}
QComboBox {{
    {bi("field")}
    background-color: {r["surface"]};
    color: {r["text"]};
    padding: {_COMBO_PADDING};
}}
QComboBox::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: {_COMBO_DROP_WIDTH_PX}px;
    margin: {ring}px {ring}px {ring}px 0px;
    {bi("subbutton")}
}}
QComboBox::down-arrow {{
    image: {art.url("arrow_down")};
    width: {arrow_dw}px;
    height: {arrow_dh}px;
}}
QComboBox QAbstractItemView {{
    {bi("menu")}
    background-color: {r["surface"]};
    color: {r["text"]};
    selection-background-color: {r["accent"]};
    selection-color: {r["accent_text"]};
    outline: 0;
}}
QCheckBox {{
    padding: {_CHECK_CLEARANCE_PX}px;
}}
QCheckBox::indicator {{
    width: {_CHECK_INDICATOR_PX}px;
    height: {_CHECK_INDICATOR_PX}px;
}}
QCheckBox::indicator:unchecked, QCheckBox::indicator:indeterminate {{
    image: {art.url("check_off")};
}}
QCheckBox::indicator:checked {{
    image: {art.url("check_on")};
}}
"""


def _slider_scroll_rules(art: ArtSet) -> str:
    bi = art.border_image
    _, groove_h = art.size("slider_groove")
    g_top, _, g_bottom, _ = art.slices("slider_groove")
    groove_content = groove_h - g_top - g_bottom
    handle_w, handle_h = art.size("slider_handle")
    margin = -((handle_h - groove_content) // 2)
    bar_w = art.size("scroll_track")[0]
    handle_len = art.size("scroll_handle")[0]
    return f"""
QSlider:horizontal {{
    min-height: {handle_h + 2 * _SLIDER_CLEARANCE_PX}px;
}}
QSlider::groove:horizontal {{
    {bi("slider_groove")}
    height: {groove_content}px;
}}
QSlider::handle:horizontal {{
    image: {art.url("slider_handle")};
    width: {handle_w}px;
    margin: {margin}px 0px;
}}
QScrollBar:vertical {{
    width: {bar_w}px;
    margin: 0px;
    background: transparent;
    border: none;
}}
QScrollBar:horizontal {{
    height: {bar_w}px;
    margin: 0px;
    background: transparent;
    border: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    {bi("scroll_track")}
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    {bi("scroll_track", transpose=True)}
}}
QScrollBar::handle:vertical {{
    {bi("scroll_handle")}
    min-height: {handle_len}px;
}}
QScrollBar::handle:horizontal {{
    {bi("scroll_handle", transpose=True)}
    min-width: {handle_len}px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
    border: none;
    background: none;
}}
"""


def _menu_rules(art: ArtSet, r: Mapping[str, str]) -> str:
    bi = art.border_image
    return f"""
QMenuBar {{
    background-color: {r["surface"]};
    color: {r["text"]};
}}
QMenuBar::item {{
    background: transparent;
    border: 1px solid transparent;
    padding: {_MENU_BAR_ITEM_PADDING};
}}
QMenuBar::item:selected {{
    background-color: {r["accent"]};
    color: {r["accent_text"]};
    border: 1px solid {r["accent_text"]};
}}
QMenu {{
    {bi("menu")}
    background-color: {r["surface"]};
    color: {r["text"]};
}}
QMenu::item {{
    padding: {_MENU_ITEM_PADDING};
    border: 1px solid transparent;
}}
QMenu::item:selected {{
    background-color: {r["accent"]};
    color: {r["accent_text"]};
    border: 1px solid {r["accent_text"]};
}}
QMenu::item:disabled {{
    color: {r["disabled_text"]};
}}
QMenu::separator {{
    height: 1px;
    background: {r["border"]};
    margin: {_MENU_SEPARATOR_MARGIN};
}}
QMenu::indicator {{
    left: {_MENU_INDICATOR_LEFT_PX}px;
    width: {_CHECK_INDICATOR_PX}px;
    height: {_CHECK_INDICATOR_PX}px;
}}
QMenu::indicator:unchecked {{
    image: {art.url("check_off")};
}}
QMenu::indicator:checked {{
    image: {art.url("check_on")};
}}
QToolTip {{
    {bi("tooltip")}
    background-color: {r["hover"]};
    color: {r["text"]};
}}
"""


def build_qss(mode: str, style: str = DEFAULT_STYLE, *, scale: int = 1) -> str:
    """Return the one application stylesheet for ``mode`` in ``style`` at art ``scale``.

    Deterministic within a process: it depends on ``(mode, style, scale)`` and on
    the process's art directory (the PNG files the rules reference are written
    there on first use). Carries no ``:focus`` rule, no ``font-family`` and no
    ``font-size``; its only font declaration is ``QDockWidget { font-weight:
    bold; }``.

    Args:
        mode: ``light`` or ``dark``.
        style: A style id from :func:`available_styles`.
        scale: Device pixels per art pixel (see :func:`art_scale`).

    Raises:
        ValueError: If the mode or the style is unknown.
    """
    roles = _roles(mode, style)
    art = art_set(style, mode, scale)
    base = f"""
QMainWindow, QWidget {{
    background-color: {roles["background"]};
    color: {roles["text"]};
}}
"""
    disabled = f"""
QPushButton:disabled, QToolButton:disabled, QLabel:disabled, QCheckBox:disabled,
QTabBar::tab:disabled, QLineEdit:disabled, QComboBox:disabled {{
    color: {roles["disabled_text"]};
}}
"""
    return "".join(
        (
            base,
            _frame_rules(art, roles),
            _button_rules(art, roles),
            _field_rules(art, roles),
            _slider_scroll_rules(art),
            _menu_rules(art, roles),
            disabled,
        )
    )


def apply_font_fallbacks() -> None:
    """Register the cross-OS UI-font fallback chain once (REQ-P13-UI-001).

    Installs :meth:`QFont.insertSubstitutions` for each single-OS family in
    :data:`_UI_FONT_FALLBACKS`, so a family that is absent on the running OS
    (Windows "Segoe UI" on Linux, macOS ".AppleSystemUIFont" on Windows, …)
    degrades to the first resolvable entry rather than to ``.notdef`` boxes.
    This is the phase's **single, role-based** font-fallback seam (not a
    per-widget font): the app hard-codes no :class:`QFont` and the QSS names no
    ``font-family``, so on each OS Qt still resolves its own default system UI
    font — this only adds a portable fallback for the cross-OS case. Idempotent
    for practical purposes (called once at shell start, before the theme is
    applied); adds no absolute font size, so it leaves layout and the render
    budget untouched (Article VI).
    """
    for family, fallbacks in _UI_FONT_FALLBACKS.items():
        QFont.insertSubstitutions(family, fallbacks)


_applied: Dict[str, object] = {
    "mode": None,
    "style": None,
    "scale": None,
    "pinned": False,
}
_WATCH_PROPERTY = "_pixelScreenWatch"


def apply_theme(
    app: QApplication,
    mode: str,
    style: str = DEFAULT_STYLE,
    *,
    scale: Optional[int] = None,
) -> None:
    """Apply ``mode`` in ``style`` to the whole application (runtime switch).

    This single app-wide role-based stylesheet is also how every Phase-8
    automation panel renders correctly in both modes -- none of them carries a
    per-widget colour override (REQ-P8-UI-013). ``scale=None`` builds the art at
    :func:`art_scale`, and the sheet is rebuilt when a screen is added, removed
    or changes scale and the maximum differs (ADR-0069 amendment); an explicit
    ``scale`` pins it.
    """
    effective = art_scale() if scale is None else scale
    qss = build_qss(mode, style, scale=effective)
    set_active_theme(style, mode)
    chrome_filter(app)
    app.setStyleSheet(qss)
    _applied.update(mode=mode, style=style, scale=effective, pinned=scale is not None)
    _watch_screens(app)


def _on_screens_changed() -> None:
    """Rebuild the one stylesheet if the highest whole-number DPR changed."""
    app = QApplication.instance()
    mode, style = _applied["mode"], _applied["style"]
    if not isinstance(app, QApplication) or mode is None or _applied["pinned"]:
        return
    if art_scale() != _applied["scale"]:
        apply_theme(app, str(mode), str(style))


def _on_screen_added(screen: QScreen) -> None:
    screen.logicalDotsPerInchChanged.connect(_on_screens_changed)
    _on_screens_changed()


def _watch_screens(app: QApplication) -> None:
    """Connect the screen-change signals once per application."""
    if app.property(_WATCH_PROPERTY):
        return
    app.setProperty(_WATCH_PROPERTY, True)
    for screen in QGuiApplication.screens():
        screen.logicalDotsPerInchChanged.connect(_on_screens_changed)
    app.screenAdded.connect(_on_screen_added)
    app.screenRemoved.connect(_on_screens_changed)


def link_colour(name: str, style: str = DEFAULT_STYLE) -> QColor:
    """Return the link colour for mode ``name`` (ADR-0067 Part 2).

    Returns the existing ``text`` role -- no new role and no new hex value
    (Article V section 3: a colour is defined once, by role). Callers underline
    the anchor themselves as the non-colour cue (WCAG 1.4.1), since a link here
    looks the same colour as body text; the accent role and Qt's palette-default
    link colour are not suitable.
    """
    return QColor(_roles(name, style)["text"])


def canvas_roles(
    name: str, style: str = DEFAULT_STYLE
) -> Tuple[QColor, QColor, QColor]:
    """Return ``(checker_light, checker_dark, grid)`` :class:`QColor` for ``name``.

    The canvas paints its background/grid outside QSS, so these role colours are
    handed to the scene by the main window on every theme switch (QT-D2, 025).
    """
    roles = _roles(name, style)
    return (
        QColor(roles["canvas_checker_light"]),
        QColor(roles["canvas_checker_dark"]),
        QColor(roles["canvas_grid"]),
    )


def canvas_surface_roles(
    name: str, style: str = DEFAULT_STYLE
) -> Tuple[QColor, QColor]:
    """Return ``(workspace, border)`` :class:`QColor` for ``name`` (REQ-CGS-UI-005/006).

    ``workspace`` is the ground painted behind the document (flat -- no pattern,
    ever) and ``border`` outlines the document edge. Resolved through the same
    :func:`_roles` validator as :func:`canvas_roles` so an unknown theme name
    raises identically. A sibling of :func:`canvas_roles`, which keeps returning
    exactly three colours (it is unpacked positionally at call sites and in
    tests).
    """
    roles = _roles(name, style)
    return (
        QColor(roles["canvas_workspace"]),
        QColor(roles["canvas_border"]),
    )


def __getattr__(name: str) -> Dict[str, Dict[str, str]]:
    """Serve ``_ROLES`` (the default style's role maps by mode) for older callers."""
    if name == "_ROLES":
        return {mode: _roles(mode) for mode in available_themes()}
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
