# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Application identity facts, call-time version, and the About/title text.

Pure Python, Qt-free (Article I, S11). This is the single home of the app's
*identity facts* (product name, licence name, the three published addresses),
a call-time lookup of :data:`pixelart_creator.__version__` (never bound at
import time, REQ-AV-UI-001 / ADR-0067 Part 3), the platform facts the standard
library can supply (each one independently guarded, REQ-AV-UI-007), and the
pure composition of the one-line environment string and the window title.

``ui/about_dialog.py`` gathers the two facts that need Qt (the runtime Qt
version and the PySide6 version) and passes them into
:func:`compose_environment_line`; this module never imports PySide6, ``ui`` or
``data`` (design-docs/specs/app-version/plan.md section 3.2).
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Final, Optional

import pixelart_creator

APP_NAME: Final[str] = "PixelArt Creator"
"""The product name. A value element (CL-AV-5): never wrapped in ``tr()``."""

LICENCE_NAME: Final[str] = "Apache License 2.0"
"""The licence name shown in the About dialog. A value element."""

REPOSITORY_URL: Final[str] = "https://github.com/JuanGSanchez/PixelArt-Creator"
"""The project's source-code repository address."""

DOCUMENTATION_URL: Final[str] = "https://juangsanchez.github.io/PixelArt-Creator/"
"""The project's published documentation site address."""

RELEASES_URL: Final[str] = "https://github.com/JuanGSanchez/PixelArt-Creator/releases"
"""The project's releases page address."""

_ENVIRONMENT_LINE_SEPARATOR: Final[str] = "; "
"""Joins each ``"<label> <value>"`` segment of the composed environment line.

Punctuation, not wording (CL-AV-5): never translated."""

_ENVIRONMENT_LINE_LABEL_PYTHON: Final[str] = "Python"
"""Proper-name label for the Python-version segment. Never translated (CL-AV-5)."""

_ENVIRONMENT_LINE_LABEL_QT: Final[str] = "Qt"
"""Proper-name label for the Qt-version segment. Never translated (CL-AV-5)."""

_ENVIRONMENT_LINE_LABEL_PYSIDE: Final[str] = "PySide6"
"""Proper-name label for the PySide6-version segment. Never translated (CL-AV-5)."""


@dataclass(frozen=True)
class PlatformFacts:
    """The standard-library-derived platform facts, each independently guarded.

    Every field is ``None`` when the underlying :mod:`platform` call raised, or
    returned an empty string (REQ-AV-UI-007). The dataclass is frozen: a
    :class:`PlatformFacts` instance is a snapshot, never mutated in place.
    """

    os_name: Optional[str]
    os_version: Optional[str]
    python_version: Optional[str]


@dataclass(frozen=True)
class EnvironmentFacts:
    """Every fact :func:`compose_environment_line` needs, gathered by the caller.

    ``app_name`` is always known; every other field is ``Optional[str]`` and
    renders as the caller-supplied placeholder in :func:`compose_environment_line`
    when it is ``None`` or blank. ``qt_version`` and ``pyside_version`` are
    gathered in ``ui/about_dialog.py`` (the only facts that need Qt) and passed
    in here unchanged.
    """

    app_name: str
    app_version: Optional[str]
    os_name: Optional[str]
    os_version: Optional[str]
    python_version: Optional[str]
    qt_version: Optional[str]
    pyside_version: Optional[str]


def app_version() -> str:
    """Return the currently installed application version.

    Reads :data:`pixelart_creator.__version__` fresh on every call (never
    cached at import time), so a value changed after this module was imported
    is still observed (REQ-AV-UI-001, C-3; ADR-0067 Part 3). The rejected
    alternative, ``from pixelart_creator import __version__``, binds once at
    import time and cannot see such a change.
    """
    return pixelart_creator.__version__


def window_title(translated_name: str) -> str:
    """Compose the window title from the already-translated app name and version.

    Returns ``"<translated_name> <app_version()>"``. The version is read at
    call time via :func:`app_version`, so the title always reflects the
    currently installed version. Joining name and version here, outside
    ``tr()``, is deliberate (ADR-0067 Part 3): a product name followed by its
    version number is an identity pair, not a sentence, so no language
    reorders it and no translation can drop the version.
    """
    return f"{translated_name} {app_version()}"


def _clean_platform_fact(value: str) -> Optional[str]:
    """Return ``value``, or ``None`` when it is blank.

    Shared normalisation for every :func:`read_platform_facts` field: an empty
    string from :mod:`platform` (its own way of saying "undeterminable") is
    treated the same as a raised exception (REQ-AV-UI-007, OB-6).
    """
    return value if value else None


def _read_os_name() -> Optional[str]:
    """Return ``platform.system()``, or ``None`` on failure or blank."""
    try:
        return _clean_platform_fact(platform.system())
    except Exception:
        return None


def _read_os_version() -> Optional[str]:
    """Return ``platform.version()``, or ``None`` on failure or blank."""
    try:
        return _clean_platform_fact(platform.version())
    except Exception:
        return None


def _read_python_version() -> Optional[str]:
    """Return ``platform.python_version()``, or ``None`` on failure or blank."""
    try:
        return _clean_platform_fact(platform.python_version())
    except Exception:
        return None


def read_platform_facts() -> PlatformFacts:
    """Gather the OS name, OS version and Python version, each independently.

    Never raises (REQ-AV-UI-007): a call that fails, or returns an empty
    string, degrades that single field to ``None`` without affecting the
    other two. The OS-version fact is kept as the literal
    ``platform.version()`` value (plan.md R-6) rather than a friendlier
    platform-specific string.
    """
    return PlatformFacts(
        os_name=_read_os_name(),
        os_version=_read_os_version(),
        python_version=_read_python_version(),
    )


def _resolve_fact(value: Optional[str], unknown: str) -> str:
    """Return ``value``, or ``unknown`` when it is ``None`` or blank.

    Shared substitution rule for every slot of :func:`compose_environment_line`
    (REQ-AV-LOGIC-001, SC-AV-LOGIC-001-2): a missing fact never leaks past this
    point as ``None`` or ``""``.
    """
    return value if value else unknown


def compose_environment_line(facts: EnvironmentFacts, unknown: str) -> str:
    """Compose the one-line "app version; OS; Python; Qt; PySide6" summary.

    Always returns exactly one line (any CR/LF inside a fact is replaced by a
    space); each missing fact (``None`` or blank) renders as ``unknown`` in its
    own slot only, and this function never raises (REQ-AV-LOGIC-001,
    SC-AV-LOGIC-001-1/-2). The labels ``Python``, ``Qt`` and ``PySide6`` and the
    ``"; "`` separators are proper names and punctuation, not wording
    (CL-AV-5): this function never translates them. ``unknown`` is the
    caller's already-translated placeholder text (CL-AV-6).
    """
    segments = [
        f"{facts.app_name} {_resolve_fact(facts.app_version, unknown)}",
        f"{_resolve_fact(facts.os_name, unknown)} "
        f"{_resolve_fact(facts.os_version, unknown)}",
        f"{_ENVIRONMENT_LINE_LABEL_PYTHON} "
        f"{_resolve_fact(facts.python_version, unknown)}",
        f"{_ENVIRONMENT_LINE_LABEL_QT} {_resolve_fact(facts.qt_version, unknown)}",
        f"{_ENVIRONMENT_LINE_LABEL_PYSIDE} "
        f"{_resolve_fact(facts.pyside_version, unknown)}",
    ]
    line = _ENVIRONMENT_LINE_SEPARATOR.join(segments)
    return line.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
