# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Application (window/taskbar) icon loader.

Resolves the raster app-icon family committed under
``pixelart_creator/icons/app/`` (derived by
``scripts/derive_app_icons.py``, see that directory's
``CONSTRUCTION-TABLE.md``) and returns them as Qt objects for two callers:
:func:`app_icon` for :class:`~PySide6.QtWidgets.QApplication` /
:class:`~PySide6.QtWidgets.QMainWindow` window-icon wiring, and
:func:`guide_logo_image` for the in-app User Guide's document-resource mark.

Resolution follows the **same portable form** already shipped by
``pixelart_creator/ui/tool_icons.py`` and
``pixelart_creator/data/guide_content.py`` — :func:`importlib.resources.files`
rooted at the top-level ``pixelart_creator`` package, walked down to
``icons/app`` with the ``/`` operator. This needs **no** ``__init__.py``
under ``pixelart_creator/icons/`` — adding one turns ``check_layering.py``
**exit 1** with ``UNREGISTERED top-level package 'icons'``, because that
directory is package *data*, not a Python package. Do **not** call
``resources.files("pixelart_creator.icons")`` — that dotted form requires
exactly the marker this module must not need.

Only the **runtime size set** is loaded here — 16/24/32/48/64/128/256/512 px
(:data:`RUNTIME_ICON_SIZES_PX`). ``logo-source-64.png`` is the provenance
master (never loaded at runtime); ``app-icon-1024.png``,
``pixelart-creator.ico``, ``pixelart-creator.icns`` and
``pixelart-creator.png`` are packaging-only artifacts consumed by the build
toolchain, not by this loader.

Every size is decoded straight from bytes with
:meth:`QPixmap.loadFromData`/:meth:`QImage.loadFromData` — **never** via
``importlib.resources.as_file``'s temporary filesystem path handed to a
lazily-reading Qt object. A ``QIcon.addFile(path)`` (or a ``QIcon(path)`` kept
around past the ``with`` block) would be reading a path that can vanish the
moment the context manager exits when the package is a wheel/zip import; this
module never keeps such a path alive past the read.

Failure handling: a missing, unreadable, or undecodable asset is
logged through the standard library ``logging`` module (this repository's
existing logging path — see
``pixelart_creator/data/cloud/ws_transport.py``) and degrades to a **null**
:class:`QIcon` / ``None`` image. Nothing here ever raises — a broken icon
asset must never stop the application from starting. Every call site uses
``_LOGGER.log(logging.WARNING, ...)`` rather than ``_LOGGER.warning(...)``:
the string-audit heuristic (``scripts/string_audit_check.py``) flags a
``.warning(<string literal>)`` call as an unwrapped user-facing string
because :class:`~PySide6.QtWidgets.QMessageBox` happens to share that method
name — these are diagnostic log records, not UI text, so they take the
equivalent ``.log(level, ...)`` form instead of being mis-wrapped in ``tr()``.

This module binds to no domain logic — no harmony math, no blending math, no
file-format parsing (S11): it is Qt resource plumbing only.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib import resources
from typing import Final, Optional, Tuple

from PySide6.QtGui import QIcon, QImage, QPixmap

__all__ = ["RUNTIME_ICON_SIZES_PX", "app_icon", "guide_logo_image"]

_LOGGER = logging.getLogger(__name__)

#: The importable package the icon bundle is shipped inside (package data),
#: matching ``ui/tool_icons.py``'s ``_ICON_PACKAGE`` convention.
_ICON_PACKAGE: Final[str] = "pixelart_creator"

#: Package-data subdirectory holding the app-icon family, relative to
#: :data:`_ICON_PACKAGE` (``pixelart_creator/icons/app/``).
_ICON_SUBPATH: Final[Tuple[str, str]] = ("icons", "app")

#: The runtime size set (per ``CONSTRUCTION-TABLE.md``): every member a
#: :class:`QIcon` built by :func:`app_icon` carries, largest to smallest so
#: Qt/the OS can pick whichever fits without upscaling a smaller member.
#: ``app-icon-1024.png`` exists only to satisfy the ICNS container and is
#: deliberately excluded (packaging-only, see the module docstring).
RUNTIME_ICON_SIZES_PX: Final[Tuple[int, ...]] = (512, 256, 128, 64, 48, 32, 24, 16)

#: Filename stem shared by every runtime-size PNG (``app-icon-<size>.png``).
_RUNTIME_FILE_TEMPLATE: Final[str] = "app-icon-{size}.png"

#: The single asset the in-app User Guide embeds as its document resource
#: — reusing an already-shipped runtime member needs no new binary
#: under ``userguide_content/`` and no new package-data glob for the guide.
_GUIDE_LOGO_FILE_NAME: Final[str] = "app-icon-128.png"

#: ``QPixmap``/``QImage.loadFromData`` are called with the ``format``
#: argument omitted (every asset in this family is a PNG, per
#: ``CONSTRUCTION-TABLE.md``): Qt's own image-plugin sniffing already
#: identifies a PNG from its signature bytes, and measured against this
#: exact asset family, passing ``format=b"PNG"`` explicitly raises
#: ``ValueError`` from PySide6's overload resolution despite a matching
#: overload being listed -- omitting it is the form that actually works.


def _icons_root() -> "resources.abc.Traversable":
    """Return the traversable root of the shipped app-icon bundle.

    Uses :func:`importlib.resources.files` rooted at the top-level
    ``pixelart_creator`` package — the same portable form
    ``ui/tool_icons.py``/``data/guide_content.py`` use — so resolution works
    identically from an on-disk source tree, an installed wheel, or a zip
    import.
    """
    root = resources.files(_ICON_PACKAGE)
    for segment in _ICON_SUBPATH:
        root = root / segment
    return root


def _asset_bytes(file_name: str) -> Optional[bytes]:
    """Return the raw bytes of ``file_name`` under ``icons/app/``, or ``None``.

    Never raises: a missing file, an unreadable file, or any ``OSError``
    while reading is logged and reported as ``None``.
    """
    candidate = _icons_root() / file_name
    try:
        if not candidate.is_file():
            _LOGGER.log(logging.WARNING, "app icon asset missing: %s", file_name)
            return None
        return candidate.read_bytes()
    except OSError as exc:
        _LOGGER.log(
            logging.WARNING, "app icon asset unreadable: %s (%s)", file_name, exc
        )
        return None


@lru_cache(maxsize=None)
def app_icon() -> QIcon:
    """Return the app icon as one :class:`QIcon` carrying every runtime size.

    Each member of :data:`RUNTIME_ICON_SIZES_PX` is added as its own pixmap
    (:meth:`QIcon.addPixmap`) rather than a single file being scaled — Qt and
    the OS each then pick their own best member for a given context (title
    bar, taskbar, dock, alt-tab) instead of one raster being downscaled with
    a smoothing filter, which would blur this pixel-exact mark.

    Degrades to a **null** ``QIcon()`` if any runtime-size asset is
    missing, unreadable, or fails to decode — logged, never raised. Cached
    for the life of the process (built at most once).
    """
    icon = QIcon()
    for size in RUNTIME_ICON_SIZES_PX:
        file_name = _RUNTIME_FILE_TEMPLATE.format(size=size)
        data = _asset_bytes(file_name)
        if data is None:
            _LOGGER.log(
                logging.WARNING,
                "app icon family incomplete (missing %s); returning a null QIcon",
                file_name,
            )
            return QIcon()
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            _LOGGER.log(
                logging.WARNING, "app icon asset failed to decode: %s", file_name
            )
            return QIcon()
        icon.addPixmap(pixmap)
    return icon


@lru_cache(maxsize=None)
def guide_logo_image() -> Optional[QImage]:
    """Return the in-app User Guide's mark as an in-memory :class:`QImage`.

    Loads ``app-icon-128.png`` straight from bytes via
    :meth:`QImage.loadFromData` — no filesystem path is ever handed to the
    caller, so the guide dialog can register this image as a
    ``QTextDocument`` resource that survives past any temporary-extraction
    context — the same as :func:`app_icon`'s reasoning above.

    Returns ``None`` if the asset is missing, unreadable, or fails to
    decode — logged, never raised. The guide degrades to showing its content
    without the mark rather than failing to open.
    """
    data = _asset_bytes(_GUIDE_LOGO_FILE_NAME)
    if data is None:
        return None
    image = QImage()
    if not image.loadFromData(data):
        _LOGGER.log(
            logging.WARNING,
            "guide logo asset failed to decode: %s",
            _GUIDE_LOGO_FILE_NAME,
        )
        return None
    return image
