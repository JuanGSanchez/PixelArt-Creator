# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""QImage-backed image decode → RGBA ``PixelBuffer`` (Qt lives here; ADR-0010).

The drag-drop import feature must turn a dropped ``.png`` / ``.jpg`` /
``.jpeg`` / ``.bmp`` / ``.gif`` into an RGBA
:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer`.
ADR-0010 fixes the decode backend as **QImage** (no new dependency)
and rules that — being Qt — it must live in ``ui/`` (Article I / S11). This module
is the *only* new Qt consumer for the feature: it decodes with QImage, normalises to a
packed ``Format_RGBA8888`` ``(H, W, 4)`` uint8 array (honouring ``bytesPerLine()`` to
strip 32-bit scanline padding), bounds-checks the dimensions, and hands a plain
``PixelBuffer`` down to ``logic/`` — **no** Qt object crosses the layer boundary.

Every load / format / bounds failure is raised as
:class:`~pixelart_creator.data.file_import.ImageImportError` (defined Qt-free in
``data/`` so the whole import-error family shares one base the UI router catches —
REQ-DDI-DATA-005, ADR-0010).
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
import numpy.typing as npt
from PySide6.QtGui import QImage

from pixelart_creator.data.file_import import ImageImportError
from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

__all__ = ["decode_image"]

#: Bytes per RGBA pixel in ``Format_RGBA8888`` (intrinsic to the pixel layout, not
#: a domain tuning value — ADR-0001 intrinsic-literal exemption).
_RGBA_BYTES = 4


def decode_image(path: Union[str, Path]) -> PixelBuffer:
    """Decode an image file into an RGBA :class:`PixelBuffer` (REQ-DDI-DATA-002).

    Reads ``path`` with :class:`QImage`, converts to packed
    ``QImage.Format.Format_RGBA8888`` (deterministic R, G, B, A byte order across
    platforms), strips any 32-bit scanline padding via ``bytesPerLine()``, and
    copies the pixels into an owned :class:`PixelBuffer` in
    :data:`ColorMode.RGBA`. A multi-frame ``.gif`` yields its **first** frame
    (QImage's default); paletted / indexed sources are expanded to RGBA by the
    format conversion (CL-A3).

    The dimensions are bounds-checked against ``MAX_CANVAS_WIDTH`` /
    ``MAX_CANVAS_HEIGHT`` **before** any buffer allocation — an oversized image is
    rejected, never truncated (NFR-4, ADR-0010).

    Args:
        path: Filesystem path to a raster image.

    Returns:
        A new RGBA :class:`PixelBuffer` sized to the source image.

    Raises:
        ImageImportError: If the file cannot be loaded / decoded, has no pixels,
            or exceeds the canvas bounds. The buffer copy is defensive — any
            unexpected extraction failure is re-raised as ``ImageImportError`` so
            a bad file surfaces a notice and never crashes the app (NFR-9).
    """
    source = str(path)
    image = QImage(source)
    if image.isNull():
        raise ImageImportError(f"could not decode image: {source}")

    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull():
        raise ImageImportError(f"could not convert image to RGBA: {source}")

    width = int(image.width())
    height = int(image.height())
    if width <= 0 or height <= 0:
        raise ImageImportError(f"image has no pixels: {source}")
    if width > MAX_CANVAS_WIDTH or height > MAX_CANVAS_HEIGHT:
        raise ImageImportError(
            f"image {width}x{height} exceeds the maximum "
            f"{MAX_CANVAS_WIDTH}x{MAX_CANVAS_HEIGHT}: {source}"
        )

    try:
        rgba = _to_packed_rgba(image, width, height)
        buffer = PixelBuffer(width, height, ColorMode.RGBA)
        buffer.data[:, :] = rgba
    except (ValueError, RuntimeError) as exc:  # defensive: never crash on a drop
        raise ImageImportError(f"could not read image pixels: {source}") from exc
    return buffer


def _to_packed_rgba(image: QImage, width: int, height: int) -> npt.NDArray[np.uint8]:
    """Copy QImage scanlines into a packed ``(H, W, 4)`` uint8 array (stride-safe).

    QImage scanlines are at least 32-bit aligned, so ``bytesPerLine()`` (the
    stride) may exceed ``width * 4``. This slices each row down to the used
    ``width * 4`` bytes before reshaping, so the result is a contiguous packed
    RGBA array with no row padding — the layout :class:`PixelBuffer` stores
    (ADR-0010 stride discipline).
    """
    stride = int(image.bytesPerLine())
    row_bytes = width * _RGBA_BYTES
    flat = np.frombuffer(image.constBits(), dtype=np.uint8, count=stride * height)
    padded = flat.reshape(height, stride)
    packed = padded[:, :row_bytes].reshape(height, width, _RGBA_BYTES)
    # ascontiguousarray detaches from the QImage's buffer so the returned array
    # (and the PixelBuffer copied from it) outlives the QImage safely.
    return np.ascontiguousarray(packed)
