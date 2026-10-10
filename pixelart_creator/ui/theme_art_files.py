# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Runtime-generated pixel-chrome art: PNG files and images (ADR-0069).

The Qt half of the pixel chrome's art pipeline. The Qt-free half
(:mod:`pixelart_creator.logic.theme_art`) composes a role-indexed template to a
size and colours it from a role map at an integer scale; this module

* writes the coloured templates the **one application stylesheet** references
  (:class:`ArtSet`) into a per-process temporary directory that is removed at
  exit (:func:`art_root`), and
* hands out :class:`~PySide6.QtGui.QImage` objects of composed templates to the
  overlay widgets in :mod:`pixelart_creator.ui.pixel_chrome`, which paint at
  their own widget's whole-number device-pixel ratio (:func:`template_image`).

One art pixel is one logical pixel; an image carries ``scale`` device pixels per
art pixel. In the stylesheet ``border-width`` is the slice count (logical px)
and the ``border-image`` slice numbers are ``slice * scale`` (image px) --
:meth:`ArtSet.border_image` writes both from the one slice definition, so they
can never disagree. Paths are emitted as ``url("<forward slashes>")``: quoted
and forward-slashed, the only form measured to resolve in every directory name
(spaces, non-ASCII, ``'``, ``&``, ``%``, brackets, ``;``, ``#``).

No colour literal lives here: every colour is a role resolved by the caller's
role map (Article V.3). No domain logic (S11): composing and colouring is
``logic/theme_art.py``.
"""

from __future__ import annotations

import atexit
import functools
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

import numpy as np
from PySide6.QtGui import QImage

from pixelart_creator.data import style_catalog
from pixelart_creator.logic import theme_art
from pixelart_creator.logic.theme_art import RoleGrid, Slices, Template

__all__ = [
    "ArtSet",
    "art_root",
    "art_set",
    "reset_art",
    "template_image",
    "transposed",
    "grid_image",
]

_ART_DIR_PREFIX = "pixelart-creator-art-"
_TRANSPOSED_SUFFIX = "_t"
_RGBA_CHANNELS = 4
_TEMPLATE_IMAGE_CACHE = 256

_state: Dict[str, object] = {"root": None, "owned": False}
_sets: Dict[Tuple[str, str, int], "ArtSet"] = {}


def _cleanup() -> None:
    root = _state.get("root")
    if _state.get("owned") and isinstance(root, Path):
        shutil.rmtree(root, ignore_errors=True)


atexit.register(_cleanup)


def art_root() -> Path:
    """Return this process's art directory, creating it on first use.

    The directory is a fresh temporary directory (``tempfile.mkdtemp``, so it
    honours ``TMP``/``TEMP``) removed when the interpreter exits. A directory
    installed with :func:`reset_art` is used as given and is **not** removed.
    """
    root = _state.get("root")
    if isinstance(root, Path):
        return root
    created = Path(tempfile.mkdtemp(prefix=_ART_DIR_PREFIX))
    _state["root"] = created
    _state["owned"] = True
    return created


def reset_art(root: Optional[Path] = None) -> None:
    """Forget every generated set; optionally redirect the art directory.

    Used by tests (for instance to render the art under a directory whose path
    contains a space and a non-ASCII character). An owned temporary directory
    that is being replaced is removed now; a directory passed in by the caller
    is never removed by the product.

    Args:
        root: The directory to write to from now on, created if missing;
            ``None`` returns to a fresh per-process temporary directory.
    """
    _cleanup()
    _sets.clear()
    template_image.cache_clear()
    if root is None:
        _state["root"] = None
        _state["owned"] = False
        return
    root.mkdir(parents=True, exist_ok=True)
    _state["root"] = root
    _state["owned"] = False


def transposed(template: Template) -> Template:
    """Return ``template`` with rows and columns exchanged (horizontal variant).

    The horizontal scroll bar uses the transpose of the vertical templates; the
    slices swap with the axes.
    """
    grid = template.grid
    rows = tuple(
        "".join(grid.rows[y][x] for y in range(grid.height)) for x in range(grid.width)
    )
    s = template.slices
    return Template(
        name=template.name + _TRANSPOSED_SUFFIX,
        grid=RoleGrid(rows=rows, legend=grid.legend),
        slices=Slices(left=s.top, top=s.left, right=s.bottom, bottom=s.right),
        kind=template.kind,
        qss_hint=template.qss_hint,
    )


def grid_image(grid: RoleGrid, role_map: Mapping[str, str], scale: int) -> QImage:
    """Return ``grid`` coloured from ``role_map`` at ``scale`` as an RGBA image.

    The image's ``devicePixelRatio`` is left at 1: callers that paint it set
    the ratio themselves.
    """
    buf = theme_art.render(grid, role_map, scale)
    data = np.ascontiguousarray(buf.data)
    height, width = data.shape[0], data.shape[1]
    return QImage(
        data.data, width, height, width * _RGBA_CHANNELS, QImage.Format.Format_RGBA8888
    ).copy()


@functools.lru_cache(maxsize=_TEMPLATE_IMAGE_CACHE)
def template_image(
    style: str,
    mode: str,
    name: str,
    width: int,
    height: int,
    scale: int,
    flip_h: bool = False,
    flip_v: bool = False,
) -> QImage:
    """Return template ``name`` composed to ``width`` x ``height`` art pixels.

    Args:
        style: The style id.
        mode: The mode id.
        name: The template name.
        width: Target width in art pixels (``0`` = the template's native width).
        height: Target height in art pixels (``0`` = native).
        scale: Device pixels per art pixel (the caller's own widget ratio).
        flip_h: Mirror left-right (ornaments on the right-hand corners).
        flip_v: Mirror top-bottom (ornaments on the bottom corners).

    Raises:
        pixelart_creator.logic.theme_art.ThemeArtError: If the target size
            cannot be composed (smaller than the slices, or no middle to
            repeat).
    """
    template = style_catalog.template_set(style).get(name)
    roles = style_catalog.role_map(style, mode)
    grid = template.grid
    if template.slices.is_zero and not (width or height):
        composed = grid
    else:
        composed = theme_art.compose(
            template, width or grid.width, height or grid.height
        )
    image = grid_image(composed, roles, scale)
    if flip_h or flip_v:
        image = image.mirrored(flip_h, flip_v)
    return image


class ArtSet:
    """The PNG files of one ``(style, mode, scale)`` and their QSS fragments."""

    def __init__(self, root: Path, style: str, mode: str, scale: int) -> None:
        """Bind the set to its folder; files are written on first use.

        Raises:
            pixelart_creator.data.style_catalog.StyleCatalogError: If the
                style or the mode is unknown.
            pixelart_creator.logic.theme_art.ThemeArtError: If ``scale`` is
                not a whole number >= 1.
        """
        if not isinstance(scale, int) or isinstance(scale, bool) or scale < 1:
            raise theme_art.ThemeArtError(f"scale must be an int >= 1, got {scale!r}")
        self.style = style
        self.mode = mode
        self.scale = scale
        self._templates = style_catalog.template_set(style)
        self._roles = style_catalog.role_map(style, mode)
        self._dir = root / style / mode / f"s{scale}"
        self._written: Dict[str, Path] = {}

    def _template(self, name: str, flipped_axes: bool) -> Template:
        template = self._templates.get(name)
        return transposed(template) if flipped_axes else template

    def path(self, name: str, *, transpose: bool = False) -> Path:
        """Return the PNG path of template ``name``, writing it if needed.

        Raises:
            pixelart_creator.logic.theme_art.ThemeArtError: On an unknown
                template or a write failure.
        """
        key = name + (_TRANSPOSED_SUFFIX if transpose else "")
        cached = self._written.get(key)
        if cached is not None:
            return cached
        template = self._template(name, transpose)
        image = grid_image(template.grid, self._roles, self.scale)
        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._dir / f"{key}.png"
        if not image.save(str(target)):
            raise theme_art.ThemeArtError(f"cannot write the art file {target}")
        self._written[key] = target
        return target

    def url(self, name: str, *, transpose: bool = False) -> str:
        """Return ``url("<path>")`` for template ``name`` (quoted, forward slashes)."""
        return f'url("{self.path(name, transpose=transpose).as_posix()}")'

    def size(self, name: str, *, transpose: bool = False) -> Tuple[int, int]:
        """Return the template's ``(width, height)`` in art (logical) pixels."""
        grid = self._template(name, transpose).grid
        return (grid.width, grid.height)

    def slices(
        self, name: str, *, transpose: bool = False
    ) -> Tuple[int, int, int, int]:
        """Return the slices in CSS order ``(top, right, bottom, left)`` (art px)."""
        s = self._template(name, transpose).slices
        return (s.top, s.right, s.bottom, s.left)

    def border_image(self, name: str, *, transpose: bool = False) -> str:
        """Return the ``border-image`` and ``border-width`` declarations of ``name``.

        ``border-width`` is the slice count in logical px; the image slice
        numbers are that count times the art scale (image px).
        """
        top, right, bottom, left = self.slices(name, transpose=transpose)
        s = self.scale
        return (
            f"border-image: {self.url(name, transpose=transpose)} "
            f"{top * s} {right * s} {bottom * s} {left * s} repeat repeat; "
            f"border-width: {top}px {right}px {bottom}px {left}px;"
        )


def art_set(style: str, mode: str, scale: int) -> ArtSet:
    """Return the cached :class:`ArtSet` for ``(style, mode, scale)``."""
    key = (style, mode, scale)
    found = _sets.get(key)
    if found is None:
        found = ArtSet(art_root(), style, mode, scale)
        _sets[key] = found
    return found
