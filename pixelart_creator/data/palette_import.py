"""Palette path loader for drag-drop import (zero Qt, S11).

Bridges a filesystem path to the shipped, defensive palette parser: reads UTF-8
text with :mod:`pathlib`, dispatches format by extension
(:data:`~pixelart_creator.data.file_import.PALETTE_FORMAT_BY_EXTENSION`), and
delegates all grammar handling to
:func:`pixelart_creator.logic.palette_io.decode` — no re-implementation of the
``.gpl`` / ``.hex`` / ``.pal`` grammars (plan §2.2). The bounds
(``MAX_PALETTE_SIZE``) and the no-``eval``/``exec`` guarantee are inherited from
that parser.

Every failure mode — unreadable path, non-UTF-8 bytes, unknown extension,
malformed/oversized content, or an empty (zero-colour) result — is normalised to
:class:`~pixelart_creator.data.file_import.PaletteImportError` so the UI catches
one family (REQ-P7-DATA-001, -005; ADR-0010).
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from pixelart_creator.data.file_import import (
    PALETTE_FORMAT_BY_EXTENSION,
    PaletteImportError,
)
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.palette_io import PaletteIOError, decode

__all__ = ["load_palette"]


def load_palette(path: Union[str, "Path"]) -> Palette:
    """Read a ``.gpl`` / ``.hex`` / ``.pal`` file and parse it to a Palette.

    Qt-free. The format is chosen by the file extension; parsing is delegated to
    the shipped :func:`pixelart_creator.logic.palette_io.decode`. Each format's
    channel order is honoured by that parser (GIMP / JASC RGB opaque, hex list
    via ``from_hex``).

    Args:
        path: Path to a text palette file.

    Returns:
        The decoded, ordered :class:`~pixelart_creator.logic.palette.Palette`.

    Raises:
        PaletteImportError: If the extension is not a known palette format, the
            file cannot be read (missing / permission / non-UTF-8 bytes), the
            content is malformed or exceeds ``MAX_PALETTE_SIZE``, or it yields no
            colours (empty palette).
    """
    resolved = Path(path)
    fmt = PALETTE_FORMAT_BY_EXTENSION.get(resolved.suffix.lower())
    if fmt is None:
        raise PaletteImportError(
            f"{resolved.name!r} is not a supported palette format; expected "
            f"one of {sorted(PALETTE_FORMAT_BY_EXTENSION)}"
        )

    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PaletteImportError(
            f"cannot read palette {resolved.name!r}: {exc}"
        ) from exc

    try:
        palette = decode(text, fmt)
    except PaletteIOError as exc:
        raise PaletteImportError(f"invalid palette {resolved.name!r}: {exc}") from exc

    if len(palette) == 0:
        raise PaletteImportError(f"palette {resolved.name!r} contains no colours")

    return palette
