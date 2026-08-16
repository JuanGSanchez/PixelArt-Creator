"""T-03: direct contract tests for ``pixelart_creator.ui.image_import.decode_image``
(REQ-DDI-DATA-002, ADR-0010).

``decode_image`` is a Qt (QImage) consumer and therefore lives in ``ui/`` per
ADR-0010 -- but its CONTRACT (bounds-check before allocation, oversize/corrupt
-> ``ImageImportError``, paletted/indexed source expanded to RGBA, JPEG
decodes) is drivable entirely headlessly, with no widget ever constructed. It
had ZERO test coverage before this module. Placed under ``tests/data/`` (not
``tests/logic/``) because it imports a QImage-dependent module; every test
here runs under ``QT_QPA_PLATFORM=offscreen`` (set by the harness / CI, and
defensively re-asserted below) so it is headless and portable.

Zero widgets constructed; deterministic; every temp artifact lives under
``tmp_path``.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

pytest.importorskip("PySide6.QtGui", reason="PySide6 not installed")

# decode_image needs a real (headless) Qt platform plugin to construct QImage.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402

from pixelart_creator.data.file_import import ImageImportError  # noqa: E402
from pixelart_creator.logic.pixel_buffer import ColorMode  # noqa: E402
from pixelart_creator.ui import image_import  # noqa: E402
from pixelart_creator.ui.image_import import decode_image  # noqa: E402

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)


def _save_rgba_png(path, w, h, color) -> None:
    Image.new("RGBA", (w, h), color).save(path)


# --------------------------------------------------------------------------- #
# Corrupt / undecodable input                                                  #
# --------------------------------------------------------------------------- #


def test_decode_image_rejects_corrupt_file(tmp_path):
    bad = tmp_path / "corrupt.png"
    bad.write_bytes(b"not a real image, just garbage bytes" * 4)
    with pytest.raises(ImageImportError, match="could not decode"):
        decode_image(bad)


def test_decode_image_rejects_missing_file(tmp_path):
    missing = tmp_path / "does-not-exist.png"
    with pytest.raises(ImageImportError, match="could not decode"):
        decode_image(missing)


# --------------------------------------------------------------------------- #
# Oversize input — rejected BEFORE any buffer allocation                       #
# --------------------------------------------------------------------------- #


def test_decode_image_rejects_oversize_before_allocation(tmp_path, monkeypatch):
    # Patch the bound constants the module itself reads, to a tiny ceiling, so
    # the test proves the reject-before-allocate contract without allocating a
    # multi-gigabyte fixture image. A perfectly ordinary 4x4 PNG is now
    # "oversize" relative to the patched bound.
    monkeypatch.setattr(image_import, "MAX_CANVAS_WIDTH", 2)
    monkeypatch.setattr(image_import, "MAX_CANVAS_HEIGHT", 2)
    path = tmp_path / "oversize.png"
    _save_rgba_png(path, 4, 4, RED)
    with pytest.raises(ImageImportError, match="exceeds the maximum"):
        decode_image(path)


# --------------------------------------------------------------------------- #
# JPEG decode                                                                  #
# --------------------------------------------------------------------------- #


def test_decode_image_decodes_jpeg(tmp_path):
    path = tmp_path / "photo.jpeg"
    Image.new("RGB", (8, 6), (10, 200, 30)).save(path, format="JPEG", quality=95)
    buffer = decode_image(path)
    assert buffer.mode is ColorMode.RGBA
    assert (buffer.width, buffer.height) == (8, 6)
    # JPEG is lossy: colour drift is expected, but every pixel stays opaque and
    # close to the source green-ish colour (broad tolerance, not exact bytes).
    assert np.all(buffer.data[:, :, 3] == 255)
    mean = buffer.data[:, :, :3].astype(np.int32).mean(axis=(0, 1))
    assert abs(mean[1] - 200) < 40  # green channel dominates


# --------------------------------------------------------------------------- #
# Paletted / indexed PNG -> expanded to RGBA (CL-A3)                           #
# --------------------------------------------------------------------------- #


def test_decode_image_converts_paletted_png_to_rgba(tmp_path):
    path = tmp_path / "paletted.png"
    img = Image.new("P", (4, 3))
    palette = [0, 0, 0] * 256
    palette[3 * 5 : 3 * 5 + 3] = [255, 0, 0]  # index 5 -> red
    img.putpalette(palette)
    img.putdata([5] * (4 * 3))  # every pixel uses index 5
    img.save(path)

    buffer = decode_image(path)
    assert buffer.mode is ColorMode.RGBA
    assert (buffer.width, buffer.height) == (4, 3)
    assert np.array_equal(buffer.data, np.full((3, 4, 4), RED, dtype=np.uint8))
