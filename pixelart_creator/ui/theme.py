"""Light + dark QSS themes with a runtime switch (REQ-P1-UI-025; CL-13).

Colours are defined **once per role** for each theme (never hard-coded per
widget); the QSS is built by substituting the role palette into a single
template, and the canvas background/grid colours are exposed as :class:`QColor`
roles for :class:`~pixelart_creator.ui.canvas_scene.CanvasScene` (which paints
them outside QSS). Both themes keep the canvas checker/grid legible (025).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

THEME_LIGHT = "light"
THEME_DARK = "dark"

#: Cross-OS UI-font fallback chain (REQ-P13-UI-001, Researcher Q5). Defined
#: **once, by role** here (never per-widget): the UI names no specific family (the
#: QSS below carries no ``font-family`` and the app sets no :class:`QFont`), so each
#: OS already resolves its own default system UI font. This map is the belt-and-
#: braces guard for the single-OS families that a platform default *reports* as its
#: name (e.g. Windows "Segoe UI", macOS ".AppleSystemUIFont"/"Helvetica Neue"): if
#: such a family is ever requested on an OS that lacks it (a cross-OS project theme,
#: a future stylesheet, a canvas glyph label), Qt substitutes the first available
#: entry instead of rendering ``.notdef`` boxes. Where the named family exists (its
#: native OS) Qt uses it directly, so this changes nothing on the platform that owns
#: the font — it only adds a resolvable fallback on the others. The tail generics
#: are resolved by the Qt platform plugin to a present family on every OS.
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

#: Role palette per theme. Every role key exists in both themes (QT-D1) so no
#: widget ever needs a single-theme literal.
_ROLES: Dict[str, Dict[str, str]] = {
    THEME_LIGHT: {
        "background": "#f0f0f0",
        "surface": "#ffffff",
        "text": "#202020",
        # accent darkened so white accent_text meets WCAG AA (5.28:1, was 4.22).
        "accent": "#1f6fb2",
        "accent_text": "#ffffff",
        "border": "#c0c0c0",
        "focus": "#1f6fb2",
        "disabled_text": "#a0a0a0",
        "canvas_checker_light": "#ffffff",
        "canvas_checker_dark": "#c8c8c8",
        "canvas_grid": "#78787890",
    },
    THEME_DARK: {
        "background": "#2b2b2b",
        "surface": "#3c3f41",
        "text": "#e0e0e0",
        # accent darkened so white accent_text meets WCAG AA (4.92:1, was 3.34).
        "accent": "#2a72c0",
        "accent_text": "#ffffff",
        "border": "#555555",
        "focus": "#2a72c0",
        "disabled_text": "#707070",
        "canvas_checker_light": "#5a5a5a",
        "canvas_checker_dark": "#464646",
        "canvas_grid": "#a0a0a090",
    },
}

_QSS_TEMPLATE = """
QMainWindow, QWidget {{
    background-color: {background};
    color: {text};
}}
QMenuBar, QMenu {{
    background-color: {surface};
    color: {text};
}}
QMenuBar::item:selected, QMenu::item:selected {{
    background-color: {accent};
    color: {accent_text};
}}
QToolBar {{
    background-color: {surface};
    border: 1px solid {border};
    spacing: 4px;
}}
QToolButton, QPushButton {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    padding: 4px;
}}
QToolButton:checked, QPushButton:checked {{
    background-color: {accent};
    color: {accent_text};
}}
QToolButton:disabled, QPushButton:disabled {{
    color: {disabled_text};
}}
QTabWidget::pane {{
    border: 1px solid {border};
}}
QTabBar::tab {{
    background-color: {surface};
    color: {text};
    padding: 6px 12px;
    border: 1px solid {border};
}}
QTabBar::tab:selected {{
    background-color: {accent};
    color: {accent_text};
}}
QListWidget, QGraphicsView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
}}
*:focus {{
    border: 2px solid {focus};
}}
"""


def available_themes() -> List[str]:
    """Return the selectable theme names."""
    return [THEME_LIGHT, THEME_DARK]


def _roles(name: str) -> Dict[str, str]:
    if name not in _ROLES:
        raise ValueError(
            QCoreApplication.translate("theme", "unknown theme: %1").replace(
                "%1", str(name)
            )
        )
    return _ROLES[name]


def build_qss(name: str) -> str:
    """Return the QSS stylesheet for theme ``name`` (roles substituted once)."""
    return _QSS_TEMPLATE.format(**_roles(name))


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


def apply_theme(app: QApplication, name: str) -> None:
    """Apply theme ``name`` to the whole application (runtime switch, CL-13)."""
    app.setStyleSheet(build_qss(name))


def canvas_roles(name: str) -> Tuple[QColor, QColor, QColor]:
    """Return ``(checker_light, checker_dark, grid)`` :class:`QColor` for ``name``.

    The canvas paints its background/grid outside QSS, so these role colours are
    handed to the scene by the main window on every theme switch (QT-D2, 025).
    """
    roles = _roles(name)
    return (
        QColor(roles["canvas_checker_light"]),
        QColor(roles["canvas_checker_dark"]),
        QColor(roles["canvas_grid"]),
    )
