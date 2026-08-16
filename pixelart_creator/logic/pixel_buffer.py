"""Low-level pixel buffer — the RGBA / indexed core (zero Qt, S11).

:class:`PixelBuffer` is the raw storage every higher layer draws into. It wraps
a NumPy ``uint8`` array (F7): shape ``(H, W, 4)`` in :data:`ColorMode.RGBA`, or
``(H, W)`` of palette indices in :data:`ColorMode.INDEXED`. Coordinates are
``(x, y)`` with the origin at the top-left. All numeric bounds come from
``logic/constants.py`` (S12); there are no magic numbers here.
"""

from __future__ import annotations

import enum
from typing import Tuple, Union

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic.color import RGBA, TRANSPARENT, is_rgba, rgba
from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH

#: A pixel value: an RGBA tuple (RGBA mode) or a palette index (INDEXED mode).
PixelValue = Union[RGBA, int]


class ColorMode(enum.Enum):
    """Storage mode of a :class:`PixelBuffer`."""

    RGBA = "rgba"
    INDEXED = "indexed"


class PixelBufferError(ValueError):
    """Raised on invalid buffer geometry, coordinates, or pixel values."""


def _check_dimensions(width: int, height: int) -> Tuple[int, int]:
    for name, value, limit in (
        ("width", width, MAX_CANVAS_WIDTH),
        ("height", height, MAX_CANVAS_HEIGHT),
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            raise PixelBufferError(f"{name} must be an int, got {value!r}")
        if value <= 0:
            raise PixelBufferError(f"{name} must be positive, got {value}")
        if value > limit:
            raise PixelBufferError(f"{name} {value} exceeds maximum {limit}")
    return width, height


class PixelBuffer:
    """A mutable 2-D grid of pixels in RGBA or indexed mode."""

    __slots__ = ("_mode", "_data")

    def __init__(
        self,
        width: int,
        height: int,
        mode: ColorMode = ColorMode.RGBA,
        fill: Union[RGBA, int, None] = None,
    ) -> None:
        """Create a ``width`` x ``height`` buffer, optionally pre-filled.

        Args:
            width, height: Positive dimensions within the S12 canvas bounds.
            mode: RGBA or indexed storage.
            fill: Initial value — RGBA tuple (RGBA mode) or index (indexed mode).
                Defaults to transparent black / index 0.

        Raises:
            PixelBufferError: On invalid dimensions, mode, or fill value.
        """
        _check_dimensions(width, height)
        if not isinstance(mode, ColorMode):
            raise PixelBufferError(f"mode must be a ColorMode, got {mode!r}")
        self._mode = mode
        if mode is ColorMode.RGBA:
            self._data = np.zeros((height, width, 4), dtype=np.uint8)
            self.fill(TRANSPARENT if fill is None else fill)
        else:
            self._data = np.zeros((height, width), dtype=np.uint8)
            self.fill(0 if fill is None else fill)

    # -- geometry ---------------------------------------------------------

    @property
    def width(self) -> int:
        """Buffer width in pixels."""
        return int(self._data.shape[1])

    @property
    def height(self) -> int:
        """Buffer height in pixels."""
        return int(self._data.shape[0])

    @property
    def mode(self) -> ColorMode:
        """The storage mode of this buffer."""
        return self._mode

    @property
    def data(self) -> npt.NDArray[np.uint8]:
        """The backing NumPy array (mutable view — use with care)."""
        return self._data

    def in_bounds(self, x: int, y: int) -> bool:
        """Return ``True`` if ``(x, y)`` lies inside the buffer."""
        return 0 <= x < self.width and 0 <= y < self.height

    # -- validation helpers ----------------------------------------------

    def _check_coord(self, x: int, y: int) -> None:
        if not self.in_bounds(x, y):
            raise PixelBufferError(
                f"coordinate ({x}, {y}) out of bounds " f"{self.width}x{self.height}"
            )

    def _normalise_value(self, value: Union[RGBA, int]) -> Union[RGBA, int]:
        if self._mode is ColorMode.RGBA:
            if not is_rgba(value):
                raise PixelBufferError(
                    f"RGBA buffer needs an RGBA tuple, got {value!r}"
                )
            return rgba(*value)  # type: ignore[misc]
        if not isinstance(value, int) or isinstance(value, bool):
            raise PixelBufferError(f"indexed buffer needs an int index, got {value!r}")
        if value < 0 or value > 255:
            raise PixelBufferError(f"palette index {value} out of range 0..255")
        return value

    # -- pixel access -----------------------------------------------------

    def get_pixel(self, x: int, y: int) -> PixelValue:
        """Return the pixel at ``(x, y)`` — an RGBA tuple or an index."""
        self._check_coord(x, y)
        if self._mode is ColorMode.RGBA:
            r, g, b, a = (int(v) for v in self._data[y, x])
            return (r, g, b, a)
        return int(self._data[y, x])

    def set_pixel(self, x: int, y: int, value: Union[RGBA, int]) -> None:
        """Set the pixel at ``(x, y)``; raises on out-of-bounds coordinates."""
        self._check_coord(x, y)
        val = self._normalise_value(value)
        if self._mode is ColorMode.RGBA:
            self._data[y, x] = val
        else:
            self._data[y, x] = val

    # -- bulk operations --------------------------------------------------

    def fill(self, value: Union[RGBA, int]) -> None:
        """Fill the entire buffer with ``value``."""
        val = self._normalise_value(value)
        if self._mode is ColorMode.RGBA:
            self._data[:, :] = val
        else:
            self._data[:, :] = val

    def fill_rect(
        self, x: int, y: int, w: int, h: int, value: Union[RGBA, int]
    ) -> None:
        """Fill the axis-aligned rectangle, clipped to the buffer bounds."""
        if w <= 0 or h <= 0:
            return
        val = self._normalise_value(value)
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        if self._mode is ColorMode.RGBA:
            self._data[y0:y1, x0:x1] = val
        else:
            self._data[y0:y1, x0:x1] = val

    def region(self, x: int, y: int, w: int, h: int) -> "PixelBuffer":
        """Return a copy of the ``w`` x ``h`` sub-rectangle at ``(x, y)``.

        Raises:
            PixelBufferError: If the region is not fully inside the buffer.
        """
        if w <= 0 or h <= 0:
            raise PixelBufferError(f"region size must be positive, got {w}x{h}")
        if not self.in_bounds(x, y) or not self.in_bounds(x + w - 1, y + h - 1):
            raise PixelBufferError("region exceeds buffer bounds")
        out = PixelBuffer(w, h, self._mode)
        out._data[:, :] = self._data[y : y + h, x : x + w]
        return out

    def blit(
        self, source: "PixelBuffer", dx: int, dy: int, *, blend: bool = False
    ) -> None:
        """Paste ``source`` at ``(dx, dy)``, clipped to bounds.

        Args:
            source: A buffer of the same :class:`ColorMode`.
            dx, dy: Top-left destination coordinate.
            blend: If ``True`` (RGBA only), alpha-composite source over
                destination; otherwise overwrite.

        Raises:
            PixelBufferError: If modes differ, or ``blend`` is used on an
                indexed buffer.
        """
        if source._mode is not self._mode:
            raise PixelBufferError("blit requires matching colour modes")
        if blend and self._mode is not ColorMode.RGBA:
            raise PixelBufferError("blend is only defined for RGBA buffers")

        sx0 = max(0, -dx)
        sy0 = max(0, -dy)
        sx1 = min(source.width, self.width - dx)
        sy1 = min(source.height, self.height - dy)
        if sx0 >= sx1 or sy0 >= sy1:
            return
        dx0, dy0 = dx + sx0, dy + sy0
        dx1, dy1 = dx + sx1, dy + sy1

        if not blend:
            self._data[dy0:dy1, dx0:dx1] = source._data[sy0:sy1, sx0:sx1]
            return

        dst = self._data[dy0:dy1, dx0:dx1].astype(np.float64)
        src = source._data[sy0:sy1, sx0:sx1].astype(np.float64)
        sa = src[:, :, 3:4] / 255.0
        da = dst[:, :, 3:4] / 255.0
        out_a = sa + da * (1.0 - sa)
        safe_a = np.where(out_a > 0.0, out_a, 1.0)
        rgb = (src[:, :, :3] * sa + dst[:, :, :3] * da * (1.0 - sa)) / safe_a
        result = np.empty_like(dst)
        result[:, :, :3] = np.where(out_a > 0.0, rgb, 0.0)
        result[:, :, 3:4] = out_a * 255.0
        self._data[dy0:dy1, dx0:dx1] = np.clip(np.round(result), 0, 255).astype(
            np.uint8
        )

    # -- canvas operations ------------------------------------------------

    def resize(
        self,
        new_width: int,
        new_height: int,
        *,
        offset_x: int = 0,
        offset_y: int = 0,
        fill: Union[RGBA, int, None] = None,
    ) -> "PixelBuffer":
        """Return a resized copy (crop / pad), preserving existing pixels.

        The old content is placed at ``(offset_x, offset_y)`` in the new
        buffer. Areas outside the old content take ``fill`` (transparent /
        index 0 by default). This is a non-destructive canvas resize.
        """
        out = PixelBuffer(new_width, new_height, self._mode, fill=fill)
        out.blit(self, offset_x, offset_y)
        return out

    def copy(self) -> "PixelBuffer":
        """Return an independent deep copy."""
        out = PixelBuffer(self.width, self.height, self._mode)
        out._data[:, :] = self._data
        return out

    # -- comparison / serialisation --------------------------------------

    def __eq__(self, other: object) -> bool:
        """Return True if `other` is a PixelBuffer with the same mode and pixel data."""
        if not isinstance(other, PixelBuffer):
            return NotImplemented
        return self._mode is other._mode and np.array_equal(self._data, other._data)

    def __repr__(self) -> str:
        """Return a repr showing dimensions and colour mode."""
        return f"PixelBuffer({self.width}x{self.height}, {self._mode.value})"
