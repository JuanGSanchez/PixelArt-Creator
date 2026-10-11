# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The one seam to ``QSettings`` for the interface's appearance choices.

Style, mode, "Use system font", "Pixel-perfect interface" and the guide's pixel
font switch are remembered between launches (``REQ-VI-UI-002``). Every read and
write of them goes through this module, so the storage key names, the
fall-back-to-default rule for an unreadable stored value and the way the
settings object is built live in exactly one place.

The settings object is built with the **four-argument** constructor,
``QSettings(QSettings.defaultFormat(), UserScope, organisation, application)``.
The two-argument ``QSettings(organisation, application)`` is always the native
format (the Windows registry, a macOS property list) whatever
``QSettings.setDefaultFormat`` says, so it would bypass the test isolation that
redirects the default format to a temporary file (measured with a probe
of the settings back end). The functions here need no ``QApplication``: the scaling
preference is read before one exists (ADR-0072).

No widget, no domain logic (S11): plain values in, plain values out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from PySide6.QtCore import QCoreApplication, QSettings, Qt

from pixelart_creator.data import style_catalog

__all__ = [
    "Appearance_Settings",
    "open_settings",
    "load_appearance",
    "save_appearance",
    "rounding_policy_for",
]

#: Settings group that holds every appearance key.
SETTINGS_GROUP: Final[str] = "appearance"
KEY_STYLE: Final[str] = "style"
KEY_MODE: Final[str] = "mode"
KEY_USE_SYSTEM_FONT: Final[str] = "use_system_font"
KEY_PIXEL_PERFECT: Final[str] = "pixel_perfect_interface"
KEY_GUIDE_PIXEL_FONT: Final[str] = "guide_pixel_font"

#: Identity used when the application object has not named itself yet (a bare
#: process that reads the preference before ``QApplication`` exists). They are
#: the same strings ``ui/app.py`` hands to the application, so both resolve to
#: one store.
_FALLBACK_ORGANIZATION: Final[str] = "PixelArt Creator"
_FALLBACK_APPLICATION: Final[str] = "PixelArt Creator"

#: Defaults of the two switches (pixel-perfect is on by default; the bundled
#: face is on from the first launch, so "Use system font" is OFF).
DEFAULT_USE_SYSTEM_FONT: Final[bool] = False
DEFAULT_PIXEL_PERFECT: Final[bool] = True
DEFAULT_GUIDE_PIXEL_FONT: Final[bool] = False

_TRUE_TEXT: Final[frozenset[str]] = frozenset({"true", "1", "yes", "on"})
_FALSE_TEXT: Final[frozenset[str]] = frozenset({"false", "0", "no", "off"})


@dataclass(frozen=True)
class Appearance_Settings:
    """The remembered appearance choices (all fields always valid)."""

    style: str
    mode: str
    use_system_font: bool
    pixel_perfect: bool
    guide_pixel_font: bool


def default_appearance() -> Appearance_Settings:
    """Return the first-launch choices: the catalogue's default style and mode."""
    return Appearance_Settings(
        style=style_catalog.default_style(),
        mode=style_catalog.default_mode(),
        use_system_font=DEFAULT_USE_SYSTEM_FONT,
        pixel_perfect=DEFAULT_PIXEL_PERFECT,
        guide_pixel_font=DEFAULT_GUIDE_PIXEL_FONT,
    )


def open_settings() -> QSettings:
    """Return the application's settings store, in the default format.

    Uses the four-argument constructor (never ``QSettings(org, app)``, see the
    module docstring). The organisation and application names are the running
    application's when it has set them, else the fall-backs above.
    """
    organisation = QCoreApplication.organizationName() or _FALLBACK_ORGANIZATION
    application = QCoreApplication.applicationName() or _FALLBACK_APPLICATION
    return QSettings(
        QSettings.defaultFormat(),
        QSettings.Scope.UserScope,
        organisation,
        application,
    )


def _as_bool(raw: Any, default: bool) -> bool:
    """Read a stored switch: a bool, or the text an ini file keeps; else default."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        text = raw.strip().lower()
        if text in _TRUE_TEXT:
            return True
        if text in _FALSE_TEXT:
            return False
    return default


def _as_choice(raw: Any, allowed: tuple[str, ...], default: str) -> str:
    """Return ``raw`` when it is one of ``allowed``, else ``default``."""
    return raw if isinstance(raw, str) and raw in allowed else default


def load_appearance() -> Appearance_Settings:
    """Read the remembered choices; an unreadable value falls back to its default."""
    defaults = default_appearance()
    settings = open_settings()
    settings.beginGroup(SETTINGS_GROUP)
    try:
        return Appearance_Settings(
            style=_as_choice(
                settings.value(KEY_STYLE), style_catalog.style_ids(), defaults.style
            ),
            mode=_as_choice(
                settings.value(KEY_MODE), style_catalog.mode_ids(), defaults.mode
            ),
            use_system_font=_as_bool(
                settings.value(KEY_USE_SYSTEM_FONT), defaults.use_system_font
            ),
            pixel_perfect=_as_bool(
                settings.value(KEY_PIXEL_PERFECT), defaults.pixel_perfect
            ),
            guide_pixel_font=_as_bool(
                settings.value(KEY_GUIDE_PIXEL_FONT), defaults.guide_pixel_font
            ),
        )
    finally:
        settings.endGroup()


def save_appearance(appearance: Appearance_Settings) -> None:
    """Write every choice and flush the store."""
    settings = open_settings()
    settings.beginGroup(SETTINGS_GROUP)
    settings.setValue(KEY_STYLE, appearance.style)
    settings.setValue(KEY_MODE, appearance.mode)
    settings.setValue(KEY_USE_SYSTEM_FONT, appearance.use_system_font)
    settings.setValue(KEY_PIXEL_PERFECT, appearance.pixel_perfect)
    settings.setValue(KEY_GUIDE_PIXEL_FONT, appearance.guide_pixel_font)
    settings.endGroup()
    settings.sync()


def rounding_policy_for(pixel_perfect: bool) -> Qt.HighDpiScaleFactorRoundingPolicy:
    """Return the Qt scale-factor rounding policy for the preference.

    ``Round`` (125 % -> 100 %, 150 % -> 200 %) when "Pixel-perfect interface" is
    on; ``PassThrough`` (Qt 6's default, fractional factors kept) when it is off.
    """
    if pixel_perfect:
        return Qt.HighDpiScaleFactorRoundingPolicy.Round
    return Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
