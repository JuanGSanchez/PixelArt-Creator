"""Tool glyph resolver and runtime tinter (`REQ-IS-UI-027`, code half).

Resolves one of the eleven original, single-fill monochrome SVG tool glyphs
authored under ``pixelart_creator/icons/tools/`` (T-06, AGT-15) and returns it
as a theme-tinted :class:`~PySide6.QtGui.QIcon`.

Resolution follows the **same portable form** already shipped by
``pixelart_creator/data/guide_content.py`` — :func:`importlib.resources.files`
rooted at the top-level ``pixelart_creator`` package, walked down to
``icons/tools`` with the ``/`` operator. This needs **no** ``__init__.py``
under ``pixelart_creator/icons/`` — measured: adding one turns
``check_layering.py`` **exit 1** with ``UNREGISTERED top-level package
'icons'``, because that directory is package *data*, not a Python package.
Do **not** call ``resources.files("pixelart_creator.icons")`` — that dotted
form requires exactly the marker this module must not need.

Tinting fills the glyph's alpha silhouette with the active theme's ``text``
role colour (``ui/theme.py``) via
:attr:`QPainter.CompositionMode.CompositionMode_SourceIn` — draw the raster
glyph first (its alpha channel is the mask), switch to ``SourceIn``, then
flood-fill the destination rect with the tint colour so only the glyph's own
alpha shape receives it. This module carries **no colour literal** (Article
V.3): the only colour used is read from ``ui/theme.py``'s role palette through
its existing ``_roles()`` accessor (the same one :func:`canvas_roles` and
:func:`canvas_surface_roles` already use for their own role colours) — there
is no public "text role as QColor" accessor to add to, since editing
``theme.py`` is out of this task's write target.

This module binds to no domain logic — no harmony math, no blending math, no
file-format parsing (S11): it is Qt resource + paint plumbing only.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Final, Tuple

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from pixelart_creator.ui.theme import THEME_DARK, THEME_LIGHT, _roles

__all__ = ["TOOL_GLYPH_IDS", "ToolGlyphError", "tool_icon"]

#: The importable package the glyph bundle is shipped inside (package data),
#: matching ``data/guide_content.py``'s ``BUNDLE_PACKAGE`` convention.
_ICON_PACKAGE: Final[str] = "pixelart_creator"

#: Package-data subdirectory holding the eleven glyphs, relative to
#: :data:`_ICON_PACKAGE` (``pixelart_creator/icons/tools/``).
_ICON_SUBPATH: Final[Tuple[str, str]] = ("icons", "tools")

#: SVG file extension for a glyph resource.
_GLYPH_SUFFIX: Final[str] = ".svg"

#: Square render size, in device-independent pixels, for the rasterised glyph
#: and its tinted pixmap. One named constant, referenced everywhere a size is
#: needed in this module (S12) — this module owns no other size.
_ICON_RENDER_SIZE_PX: Final[int] = 24

#: The theme role whose colour tints every glyph (`ui/theme.py`'s role
#: palette; `text` exists in both themes, QT-D1).
_TINT_ROLE: Final[str] = "text"

#: The eleven shipped `tool_id`s, one per authored glyph stem
#: (`pixelart_creator/icons/tools/<id>.svg`) — the exact `tool_id` class
#: attributes carried by `ui/tools/*.py` (pencil, eraser, fill, line, picker,
#: rectangle, ellipse, select_rect, select_lasso, select_wand, dither). Kept
#: as a literal tuple here (not imported from each tool class) so this module
#: has no dependency on the tool-strategy classes themselves — only on the
#: glyph *ids* they happen to share.
TOOL_GLYPH_IDS: Final[Tuple[str, ...]] = (
    "pencil",
    "eraser",
    "fill",
    "line",
    "picker",
    "rectangle",
    "ellipse",
    "select_rect",
    "select_lasso",
    "select_wand",
    "dither",
)


class ToolGlyphError(ValueError):
    """Raised for an unknown ``tool_id`` or an unreadable/missing glyph asset.

    Subclasses ``ValueError`` (the repository's domain-exception convention,
    e.g. ``data/guide_content.py``'s ``GuideContentError``). This is the
    documented, predictable behaviour for an unknown id: :func:`tool_icon`
    never silently returns a null icon for a caller typo — it fails loud with
    a message naming the bad id, so a renamed/misspelled ``tool_id`` is caught
    at the call site rather than surfacing as a blank toolbar button.
    """


def _glyphs_root() -> "resources.abc.Traversable":
    """Return the traversable root of the shipped glyph bundle.

    Uses :func:`importlib.resources.files` rooted at the top-level
    ``pixelart_creator`` package — the same portable form
    ``data/guide_content.py.bundle_root()`` uses — so resolution works
    identically from an on-disk source tree, an installed wheel, or a zip
    import, and needs no ``__init__.py`` under ``icons/``.
    """
    root = resources.files(_ICON_PACKAGE)
    for segment in _ICON_SUBPATH:
        root = root / segment
    return root


def _glyph_resource(tool_id: str) -> "resources.abc.Traversable":
    """Return the traversable SVG resource for ``tool_id``.

    Raises :class:`ToolGlyphError` when ``tool_id`` is not one of
    :data:`TOOL_GLYPH_IDS`, or when the corresponding asset is missing — both
    cases are indistinguishable to a caller and both must fail loud rather
    than resolve to a blank icon.
    """
    if tool_id not in TOOL_GLYPH_IDS:
        raise ToolGlyphError(
            QCoreApplication.translate(
                "tool_icons", "unknown tool glyph id: %1"
            ).replace("%1", str(tool_id))
        )
    candidate = _glyphs_root() / f"{tool_id}{_GLYPH_SUFFIX}"
    if not candidate.is_file():
        raise ToolGlyphError(
            QCoreApplication.translate(
                "tool_icons", "missing tool glyph asset for: %1"
            ).replace("%1", str(tool_id))
        )
    return candidate


def _tint_colour(theme: str) -> QColor:
    """Return the ``text`` role :class:`QColor` for ``theme``.

    Reads through ``ui/theme.py``'s existing ``_roles()`` role-palette
    accessor — the same one :func:`~pixelart_creator.ui.theme.canvas_roles`
    and :func:`~pixelart_creator.ui.theme.canvas_surface_roles` already use —
    so an unknown theme name raises identically (``ValueError``) and no
    colour literal is written in this module (Article V.3).
    """
    if theme not in (THEME_LIGHT, THEME_DARK):
        raise ToolGlyphError(
            QCoreApplication.translate("tool_icons", "unknown theme: %1").replace(
                "%1", str(theme)
            )
        )
    return QColor(_roles(theme)[_TINT_ROLE])


@lru_cache(maxsize=None)
def _rasterised_glyph(tool_id: str) -> QPixmap:
    """Return the un-tinted, rasterised glyph pixmap for ``tool_id``.

    ``importlib.resources.as_file`` materialises the resource to a real
    filesystem path (transparently, even from a zip import) for the duration
    of the ``with`` block, and :class:`QIcon` rasterises the SVG through Qt's
    own SVG icon engine — no manual SVG parsing lives in this module. Cached
    per process: the eleven source glyphs never change at runtime.
    """
    resource = _glyph_resource(tool_id)
    with resources.as_file(resource) as path:
        pixmap = QIcon(str(path)).pixmap(_ICON_RENDER_SIZE_PX, _ICON_RENDER_SIZE_PX)
    return pixmap


def _tinted_pixmap(tool_id: str, colour: QColor) -> QPixmap:
    """Return ``tool_id``'s glyph tinted with ``colour`` via ``SourceIn``.

    Draws the rasterised glyph first (its alpha channel is the silhouette
    mask), then switches to ``CompositionMode_SourceIn`` and flood-fills the
    destination rect with ``colour`` — only the glyph's own alpha shape
    receives the fill, reproducing the transparent corner / tinted ink result
    the glyph author verified for this exact composition mode.
    """
    base = _rasterised_glyph(tool_id)
    tinted = QPixmap(base.size())
    tinted.fill(Qt.GlobalColor.transparent)

    painter = QPainter(tinted)
    try:
        painter.drawPixmap(0, 0, base)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), colour)
    finally:
        painter.end()
    return tinted


def tool_icon(tool_id: str, *, theme: str) -> QIcon:
    """Return the theme-tinted :class:`QIcon` for ``tool_id``.

    ``tool_id`` MUST be one of :data:`TOOL_GLYPH_IDS`; ``theme`` MUST be one
    of ``ui/theme.py``'s ``THEME_LIGHT`` / ``THEME_DARK``. Either mismatch
    raises :class:`ToolGlyphError` rather than returning a null/blank icon —
    the documented, predictable behaviour for an unknown id (`REQ-IS-UI-027`).
    """
    tinted = _tinted_pixmap(tool_id, _tint_colour(theme))
    return QIcon(tinted)
