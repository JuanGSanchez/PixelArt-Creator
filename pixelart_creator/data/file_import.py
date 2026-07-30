"""Drag-drop file classification + shared import-error family (zero Qt, S11).

A pure, Qt-free helper for the drag-drop import feature (REQ-NEW-A). It answers
one question — *what kind of file is this path?* — by (case-insensitive) file
extension, and it homes the shared :class:`FileImportError` family so every
importer (palette here, image in ``ui/image_import``) rejects bad input with one
catchable base (REQ-DDI-DATA-005, ADR-0010).

``classify`` is a **pure predicate over the path string**: it performs no disk
I/O and imports only the standard library (plan §1.1). The extension sets are
*format identifiers*, not numeric tuning values, so they stay module-local here
rather than in ``logic/constants.py`` (ADR-0001 intrinsic-literal exemption;
this feature introduces no new numeric constant, plan §9).
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Dict, FrozenSet, Union

__all__ = [
    "IMAGE_EXTENSIONS",
    "PALETTE_EXTENSIONS",
    "PROJECT_EXTENSION",
    "PALETTE_FORMAT_BY_EXTENSION",
    "FileType",
    "FileImportError",
    "PaletteImportError",
    "ImageImportError",
    "classify",
]

#: Raster image extensions decoded (in ``ui/``) to an RGBA ``PixelBuffer``.
IMAGE_EXTENSIONS: FrozenSet[str] = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif"})

#: Text palette extensions parsed (Qt-free) by :func:`palette_import.load_palette`.
PALETTE_EXTENSIONS: FrozenSet[str] = frozenset({".gpl", ".hex", ".pal"})

#: The native project extension, loaded by ``data.project_io.load_project``.
PROJECT_EXTENSION: str = ".pixproj"

#: Maps a palette extension to the format id ``logic.palette_io.decode`` expects.
PALETTE_FORMAT_BY_EXTENSION: Dict[str, str] = {
    ".gpl": "gpl",
    ".hex": "hex",
    ".pal": "pal",
}


class FileType(enum.Enum):
    """The kind of file a dropped path resolves to (by extension)."""

    IMAGE = "image"
    PROJECT = "project"
    PALETTE = "palette"
    UNKNOWN = "unknown"


class FileImportError(ValueError):
    """Base for every drag-drop import rejection (REQ-DDI-DATA-005).

    The UI router catches this single family (plus the shipped
    ``ProjectIOError``) so one bad file surfaces a notice and never aborts the
    batch. Being a plain exception class it carries no Qt, so the whole family
    lives here in the Qt-free ``data/`` layer even though
    :class:`ImageImportError` is *raised* from ``ui/image_import`` (ADR-0010).
    """


class PaletteImportError(FileImportError):
    """Raised when a ``.gpl`` / ``.hex`` / ``.pal`` file cannot be imported."""


class ImageImportError(FileImportError):
    """Raised when an image file cannot be decoded to an RGBA buffer.

    Defined here (Qt-free) so it shares the :class:`FileImportError` base, but
    raised from ``ui/image_import.decode_image`` where ``QImage`` lives
    (Article I / ADR-0010).
    """


def classify(path: Union[str, "Path"]) -> FileType:
    """Classify ``path`` by its (case-insensitive) file extension.

    Pure and deterministic — no disk access. An extension outside the known
    image / project / palette sets returns :data:`FileType.UNKNOWN` (the UI
    surfaces a non-blocking notice rather than raising, REQ-DDI-UI-006).

    Args:
        path: A filesystem path (``str`` or :class:`pathlib.Path`).

    Returns:
        The :class:`FileType` the extension maps to.
    """
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    if suffix == PROJECT_EXTENSION:
        return FileType.PROJECT
    if suffix in PALETTE_EXTENSIONS:
        return FileType.PALETTE
    return FileType.UNKNOWN
