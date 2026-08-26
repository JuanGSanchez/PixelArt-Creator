"""UI tests for REQ-CGS-UI-012 (frame-thumbnail downscale fidelity).

``Timeline_Panel`` builds each frame-strip cell's thumbnail by downscaling the
composited frame to ``_THUMBNAIL_EDGE = 48`` with
``Qt.TransformationMode.FastTransformation`` -- nearest-neighbour point
sampling, no smoothing. A default 64px frame minified to 48 is a 0.75 scale,
so 48 destination rows can sample at most 48 of 64 source rows: one row in
four and one column in four are never sampled by ANY destination pixel. A
sparse single-pixel dab sitting on one of those dropped rows/columns silently
vanishes from its own thumbnail.

The three scenarios below satisfy ``SC-CGS-UI-012-1..3``:

* ``-1``/``-2`` prove the thumbnail defect using coordinates *derived* from the
  shipped downscale itself (never a hard-coded literal) -- see
  ``unsampled_source_coords`` below for the method.
* ``-3`` points the OTHER way: the same batch that teaches the thumbnail to
  smooth must never be read as licence to smooth the CANVAS. A thumbnail
  exists to be recognised; a canvas exists to be authored pixel-for-pixel, at
  every zoom -- this is re-asserted at 100% and at 6400% (``ZOOM_MAX``).

Scope note (AGT-06): this is a UI/integration test only -- the compositor
(``logic.blend.composite_stack``) and the pixel buffer are AGT-04's logic
tests; this file only drives the shipped ``Timeline_Panel`` / ``Canvas_View``
surfaces headlessly and asserts on their observable output (the displayed
cell icon, the view's own render hints). Canvases are modest (64x64) -- never
8K. Both themes run via the autouse ``theme`` fixture in ``conftest.py``.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest
from PySide6.QtGui import QImage, QPainter, QUndoStack

from pixelart_creator.logic.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    ZOOM_MAX,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.timeline_panel import _THUMBNAIL_EDGE, Timeline_Panel

STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
]

#: High-contrast background/dab pair so any real anti-aliased resample (the
#: eventual fix) leaves an unmistakable footprint, while a nearest-neighbour
#: point sample either reproduces the dab exactly or drops it completely.
_BACKGROUND = (10, 10, 10, 255)
_DAB = (255, 255, 255, 255)


# --------------------------------------------------------------------------- #
# Helpers -- drive the SHIPPED panel, never reimplement its downscale.        #
# --------------------------------------------------------------------------- #


def _thumbnail_image_for(qtbot, doc: Document) -> QImage:
    """Bind a real ``Timeline_Panel`` to ``doc`` and return frame 0's cell icon.

    Goes through the panel's public path -- ``set_context`` (which internally
    calls ``rebuild()``) exactly as the shipped strip does on document open --
    then reads the resulting ``QListWidgetItem``'s icon: the actually-displayed
    thumbnail, not a reimplementation of ``Timeline_Panel._thumbnail``.
    """
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, stack, lambda: None)
    icon = panel._strip.item(0).icon()
    return icon.pixmap(_THUMBNAIL_EDGE, _THUMBNAIL_EDGE).toImage()


def _solid_document(edge: int, fill: Tuple[int, int, int, int]) -> Document:
    """A single-frame RGBA document of ``edge`` x ``edge``, filled solid."""
    doc = Document(edge, edge, palette=Palette(STARTER))
    doc.frames[0].layers[0].buffer.fill(fill)
    return doc


def _images_differ(a: QImage, b: QImage) -> bool:
    """Return ``True`` if any pixel differs between two same-size images."""
    assert (a.width(), a.height()) == (b.width(), b.height())
    for y in range(a.height()):
        for x in range(a.width()):
            if a.pixelColor(x, y) != b.pixelColor(x, y):
                return True
    return False


@pytest.fixture
def unsampled_source_coords(qtbot) -> List[Tuple[int, int]]:
    """DERIVE which 64px source coordinates the shipped downscale never samples.

    Method (per REQ-CGS-UI-012's derivation obligation -- this is exercised
    empirically, never hard-coded):

    1. Build a ``DEFAULT_CANVAS_WIDTH`` x ``DEFAULT_CANVAS_HEIGHT`` document
       whose every source pixel ``(x, y)`` encodes its own coordinate: red
       channel = ``x``, green channel = ``y`` (alpha opaque, so
       ``composite_stack`` passes each value through unchanged for this
       single opaque layer).
    2. Run it through the real shipped path -- ``Timeline_Panel.set_context``
       -> ``rebuild()`` -> ``_thumbnail()`` -> ``QImage.scaled(48, 48,
       KeepAspectRatio, FastTransformation)`` -- via ``_thumbnail_image_for``.
    3. Decode every SURVIVING output pixel's red/green channel back to the
       exact source column/row it was sampled from. The source indices that
       never appear in that surviving set, for either axis, are the indices
       NO destination pixel ever samples -- regardless of what is drawn at
       that column/row, it cannot appear in the thumbnail.
    4. Intersect the never-sampled columns with the never-sampled rows so
       each returned coordinate is unsampled on BOTH axes at once (the
       clearest instance of "one row in four and one column in four are
       never sampled").

    If the shipped downscale turns out to sample every source index -- i.e.
    no unsampled coordinate exists -- that contradicts the 0.75-scale
    arithmetic in REQ-CGS-UI-012's defect narrative, and this fixture fails
    loudly as a FINDING rather than forcing a coordinate to fit.
    """
    edge = DEFAULT_CANVAS_WIDTH
    assert edge == DEFAULT_CANVAS_HEIGHT, "derivation assumes a square probe canvas"

    probe = Document(edge, edge, palette=Palette(STARTER))
    buf = probe.frames[0].layers[0].buffer
    for y in range(edge):
        for x in range(edge):
            buf.set_pixel(x, y, (x, y, 0, 255))

    image = _thumbnail_image_for(qtbot, probe)
    assert (image.width(), image.height()) == (_THUMBNAIL_EDGE, _THUMBNAIL_EDGE), (
        "probe thumbnail was not the expected _THUMBNAIL_EDGE square -- "
        f"got {image.width()}x{image.height()}"
    )

    used_x, used_y = set(), set()
    for oy in range(image.height()):
        for ox in range(image.width()):
            color = image.pixelColor(ox, oy)
            used_x.add(color.red())
            used_y.add(color.green())

    unsampled_x = sorted(set(range(edge)) - used_x)
    unsampled_y = sorted(set(range(edge)) - used_y)
    coords = [(u, u) for u in sorted(set(unsampled_x) & set(unsampled_y))]

    if not coords:
        pytest.fail(
            "FINDING: the shipped downscale (source="
            f"{edge}x{edge}, edge={_THUMBNAIL_EDGE}) sampled every source "
            f"index -- used_x={sorted(used_x)} used_y={sorted(used_y)} "
            f"(unsampled_x={unsampled_x} unsampled_y={unsampled_y}). This "
            "contradicts the 0.75-scale arithmetic in REQ-CGS-UI-012's defect "
            "narrative -- report as a finding, do not force a coordinate."
        )
    return coords


# --------------------------------------------------------------------------- #
# SC-CGS-UI-012-1/-2 -- the thumbnail must show a dab the FastTransformation  #
# point-sample downscale currently drops.                                    #
# --------------------------------------------------------------------------- #


def test_sc_cgs_ui_012_1_dab_at_derived_unsampled_coord_is_present(
    qtbot, unsampled_source_coords
):
    """SC-CGS-UI-012-1: a dab at a DERIVED unsampled coordinate is present.

    ``unsampled_source_coords[0]`` is the first coordinate the
    ``unsampled_source_coords`` fixture measured -- via the shipped downscale
    itself -- to never be sampled by any of the 48 destination pixels on
    either axis. Proven to fail against the unfixed
    ``Qt.TransformationMode.FastTransformation`` path (recorded verbatim in
    the AGT-06 report).
    """
    x0, y0 = unsampled_source_coords[0]
    edge = DEFAULT_CANVAS_WIDTH

    baseline = _solid_document(edge, _BACKGROUND)
    dabbed = _solid_document(edge, _BACKGROUND)
    dabbed.frames[0].layers[0].buffer.set_pixel(x0, y0, _DAB)

    baseline_thumb = _thumbnail_image_for(qtbot, baseline)
    dabbed_thumb = _thumbnail_image_for(qtbot, dabbed)

    assert _images_differ(baseline_thumb, dabbed_thumb), (
        f"a dab at derived-unsampled source ({x0}, {y0}) left NO trace in the "
        f"{_THUMBNAIL_EDGE}px frame thumbnail -- the FastTransformation "
        "point-sample downscale dropped it entirely (REQ-CGS-UI-012)."
    )


def test_sc_cgs_ui_012_2_every_derived_unsampled_coord_is_present(
    qtbot, unsampled_source_coords
):
    """SC-CGS-UI-012-2: a dab at EACH derived unsampled coordinate is present.

    Stops ``-012-1``'s coordinate from being read as a lucky pick: every
    coordinate the ``unsampled_source_coords`` fixture measured must show up
    in the thumbnail once the defect is fixed.
    """
    edge = DEFAULT_CANVAS_WIDTH
    baseline = _solid_document(edge, _BACKGROUND)
    baseline_thumb = _thumbnail_image_for(qtbot, baseline)

    missing: List[Tuple[int, int]] = []
    for x, y in unsampled_source_coords:
        doc = _solid_document(edge, _BACKGROUND)
        doc.frames[0].layers[0].buffer.set_pixel(x, y, _DAB)
        thumb = _thumbnail_image_for(qtbot, doc)
        if not _images_differ(baseline_thumb, thumb):
            missing.append((x, y))

    assert not missing, (
        f"{len(missing)} of {len(unsampled_source_coords)} derived-unsampled "
        f"coordinates left no trace in the frame thumbnail: {missing} "
        "(REQ-CGS-UI-012)."
    )


# --------------------------------------------------------------------------- #
# SC-CGS-UI-012-3 -- the CANVAS must stay nearest-neighbour, no smoothing,   #
# at both 100% and 6400% zoom. This points the OTHER way from -1/-2: the     #
# thumbnail gets smoothing, the canvas never does.                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("zoom_scale", [1.0, ZOOM_MAX], ids=["100pct", "6400pct"])
def test_sc_cgs_ui_012_3_canvas_never_smooths_at_100_or_6400_percent(
    qtbot, make_view, zoom_scale
):
    """SC-CGS-UI-012-3: the canvas renders with NO smoothing at 100%/6400%.

    ``make_view`` (``tests/ui/conftest.py``) builds a click-ready
    ``Canvas_View`` bound to a fresh 64x64 document. Setting the zoom to
    1.0 (100%) and to ``ZOOM_MAX`` (6400%) in turn and re-checking the
    view's own render hints proves the thumbnail-smoothing fix carries no
    licence to soften the canvas at any zoom -- it stays nearest-neighbour
    (``Antialiasing`` off, ``SmoothPixmapTransform`` off) throughout.
    """
    view, _scene, _stack = make_view()

    view.set_zoom(zoom_scale)
    assert view.zoom() == pytest.approx(zoom_scale)

    hints = view.renderHints()
    assert not (hints & QPainter.RenderHint.Antialiasing), (
        f"Canvas_View has Antialiasing ON at zoom={zoom_scale} -- the canvas "
        "must stay nearest-neighbour at every zoom (REQ-CGS-UI-012 must never "
        "be read as licence to smooth the canvas)."
    )
    assert not (hints & QPainter.RenderHint.SmoothPixmapTransform), (
        f"Canvas_View has SmoothPixmapTransform ON at zoom={zoom_scale} -- the "
        "canvas must stay nearest-neighbour at every zoom (REQ-CGS-UI-012 must "
        "never be read as licence to smooth the canvas)."
    )
