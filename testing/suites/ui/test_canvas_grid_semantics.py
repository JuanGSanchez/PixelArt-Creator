"""Canvas ground/border surface-role acceptance tests (REQ-CGS-UI-005, -006).

The canvas gained two theme roles for the surface the document sits on:
``workspace`` (the ground painted behind the document) and ``border`` (the
document-edge outline) — today the canvas has neither, so a rendered view
after a dab shows only the two checker tones and the dab, with the checker
tiling straight past the document edge.

This module covers the ROLE half of REQ-CGS-UI-005/-006: that
:func:`~pixelart_creator.ui.theme.canvas_surface_roles` returns two colours
per theme, each distinct from the theme's own checker tones (and the border
distinct from the workspace too), and that a :class:`CanvasScene` handed the
roles via :meth:`~pixelart_creator.ui.canvas_scene.CanvasScene.set_surface_roles`
reports them back. Nothing paints these roles yet — that is a later task —
so no test here asserts on rendered pixels; every assertion targets the
roles themselves or the scene's stored state.

Every test runs under both light and dark themes via the autouse ``theme``
fixture in ``conftest.py`` (parametrised there; not looped by hand here).
This module is written to be extended by a later task in place, without
restructuring — add further ``test_req_cgs_ui_*`` functions below.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QTransform

from pixelart_creator.logic.constants import (
    CANVAS_BORDER_WIDTH_PX,
    CHECKER_CELL_PX,
    CHECKER_MIN_ON_SCREEN_EDGE_PX,
    ZOOM_MIN,
)
from pixelart_creator.ui.canvas_scene import _build_checker_brush, _fill_checker
from pixelart_creator.ui.theme import canvas_roles, canvas_surface_roles

# --------------------------------------------------------------------------- #
# REQ-CGS-UI-005 — canvas_surface_roles(theme) returns (workspace, border),   #
# with the workspace distinct from both checker tones of that theme.          #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_005_surface_roles_returns_two_colours(theme):
    """REQ-CGS-UI-005: canvas_surface_roles(theme) returns (workspace, border)."""
    roles = canvas_surface_roles(theme)
    assert len(roles) == 2
    workspace, border = roles
    assert isinstance(workspace, QColor)
    assert isinstance(border, QColor)


def test_req_cgs_ui_005_workspace_distinct_from_both_checker_tones(theme):
    """REQ-CGS-UI-005: the workspace colour equals neither checker tone.

    A workspace tone equal to a checker tone would make the ground invisible
    against that tile — this is a requirement, not taste, so it is asserted
    against the theme module's own checker values (never a hard-coded hex).
    """
    workspace, _border = canvas_surface_roles(theme)
    checker_light, checker_dark, _grid = canvas_roles(theme)
    assert workspace != checker_light
    assert workspace != checker_dark


# --------------------------------------------------------------------------- #
# REQ-CGS-UI-006 — the border colour equals neither the workspace nor either  #
# checker tone of that theme, and a scene given the roles reports them.       #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_006_border_distinct_from_workspace_and_both_checker_tones(theme):
    """REQ-CGS-UI-006: the border colour equals neither its neighbour colour.

    A border equal to the workspace or to either checker tone makes the
    boundary vanish against one side of itself — the exact class of defect
    this batch exists to fix, one layer down.
    """
    workspace, border = canvas_surface_roles(theme)
    checker_light, checker_dark, _grid = canvas_roles(theme)
    assert border != workspace
    assert border != checker_light
    assert border != checker_dark


def test_req_cgs_ui_006_scene_reports_the_roles_it_was_given(make_scene, theme):
    """REQ-CGS-UI-006: a scene handed the roles via set_surface_roles reports them.

    Asserts on the scene's own stored state, not on rendered pixels — nothing
    paints these roles yet (a later task clips the checker to the canvas rect
    and strokes the border). ``set_surface_roles`` stores no public accessor
    today, so this targets the same ``_workspace_color`` / ``_border_color``
    attributes the method itself sets, which is the only observable surface
    currently exposed for this state.
    """
    scene = make_scene(8, 8)
    workspace, border = canvas_surface_roles(theme)
    scene.set_surface_roles(workspace, border)
    assert scene._workspace_color == workspace
    assert scene._border_color == border


# --------------------------------------------------------------------------- #
# T12 — the rendering half of this batch: the checker is one document pixel   #
# per square, clipped to the canvas, on a flat workspace ground, with a       #
# cosmetic 1-device-px border painted last (REQ-CGS-UI-003/-004/-005/-006/    #
# -010). Every test below renders the real drawBackground/_fill_checker path  #
# to a QImage and asserts on the observed pixels -- never on implementation   #
# details. Scenario IDs are quoted where the task supplied one; two bullets   #
# ("exactly two colours inside the canvas" and "checker/preview alignment")   #
# were given no ID, so those two tests are named after the nearest REQ        #
# instead of inventing a scenario ID (never invent an acceptance criterion).  #
# --------------------------------------------------------------------------- #


def _rgb(colour: QColor) -> tuple[int, int, int]:
    """Return ``colour`` as a bare (r, g, b) tuple, ignoring alpha."""
    return (colour.red(), colour.green(), colour.blue())


def _themed_scene(make_scene, theme, width: int, height: int):
    """A ``make_scene`` scene with its surface roles set from ``theme``.

    ``make_scene`` only calls ``set_background_roles`` (checker + grid); it
    leaves the workspace/border at their scene-construction defaults, which
    are theme-INDEPENDENT and — for the light theme specifically — the
    default workspace (200, 200, 200) is numerically identical to the light
    theme's own checker-dark tone (#c8c8c8), which would collide with the
    every rendering assertion below. Every rendering test therefore builds
    its scene through this helper, never through ``make_scene`` alone.
    """
    scene = make_scene(width, height)
    scene.set_surface_roles(*canvas_surface_roles(theme))
    return scene


def _render_flat(scene, expose_w: int, expose_h: int) -> QImage:
    """Render ``scene``'s background at zoom 1 (identity transform)."""
    img = QImage(expose_w, expose_h, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    scene.drawBackground(painter, QRectF(0, 0, expose_w, expose_h))
    painter.end()
    return img


def _render_zoomed(scene, expose_w: float, expose_h: float, zoom: float) -> QImage:
    """Render ``scene``'s background with the painter's world transform scaled
    by ``zoom``, over a scene-space rect of ``expose_w`` x ``expose_h``.

    The device image is sized to match (``expose * zoom``, rounded), and the
    exposed rect always starts at the scene origin (0, 0) so there is never a
    translation to reason about alongside the scale -- exactly the alignment
    invariant this module pins directly further below.
    """
    device_w = round(expose_w * zoom)
    device_h = round(expose_h * zoom)
    img = QImage(device_w, device_h, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setWorldTransform(QTransform().scale(zoom, zoom))
    scene.drawBackground(painter, QRectF(0, 0, expose_w, expose_h))
    painter.end()
    return img


def _border_run_length(
    img: QImage,
    y: int,
    border_rgb: tuple[int, int, int],
    width: int,
    x_start: int = 0,
) -> int:
    """Length (device px) of the contiguous run of ``border_rgb`` on row ``y``,
    scanned over ``range(x_start, width)``.

    ``x_start`` defaults to 0 but every border-thickness test below passes 1:
    every one of those renders exposes the scene from the document's own
    origin, so device column 0 is always the document's LEFT-edge border
    pixel (also 1 device px, also cosmetic) -- a second, unrelated border run
    this helper would otherwise pick up right alongside the right-edge run
    under measurement, and the contiguity check below would then (correctly)
    reject the two disjoint runs as "not contiguous".

    Asserts contiguity itself (a non-contiguous match would mean the border
    bled somewhere it should not have, which is itself a defect worth failing
    loudly on rather than mis-measuring past).
    """
    idx = [x for x in range(x_start, width) if _rgb(img.pixelColor(x, y)) == border_rgb]
    assert idx, "border colour not found on the scanned row"
    assert idx == list(range(idx[0], idx[-1] + 1)), "border run is not contiguous"
    return len(idx)


# --------------------------------------------------------------------------- #
# SC-CGS-UI-003-1/-2 — alternation on every adjacent document pixel, both     #
# directions, at zoom 1; and one cell measures 8 device px at zoom 8, its     #
# edges on the document's own pixel boundaries.                              #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_003_alternation_both_directions_at_zoom_1(make_scene, theme):
    """SC-CGS-UI-003-1: the checker alternates on every adjacent document pixel
    in both directions at zoom 1 -- so the canvas is NOT one square, which is
    the exact field defect this batch fixes (TILE_SIZE=64 conflated with the
    checker period made a default 64x64 document read as a single cell).

    Sampled on an interior 6x6 block (margin 2 clear of the cosmetic border on
    every side), matching the margin convention already used for REQ-CGS-UI-003
    in ``test_canvas_scene.py``.
    """
    doc = 10
    scene = _themed_scene(make_scene, theme, doc, doc)
    scene.set_grid_enabled(False)
    img = _render_flat(scene, doc, doc)

    # Horizontal alternation: every adjacent pair on an interior row differs.
    row = 5
    for x in range(2, 7):
        assert img.pixelColor(x, row) != img.pixelColor(x + 1, row)

    # Vertical alternation: every adjacent pair on an interior column differs.
    col = 5
    for y in range(2, 7):
        assert img.pixelColor(col, y) != img.pixelColor(col, y + 1)

    # Not one square: more than one colour appears across the interior block.
    interior = {_rgb(img.pixelColor(x, y)) for x in range(2, 8) for y in range(2, 8)}
    assert len(interior) >= 2


def test_req_cgs_ui_003_cell_is_8_device_px_at_zoom_8(make_scene, theme):
    """SC-CGS-UI-003-2: one checker cell measures exactly 8 device px at zoom 8,
    and its edges sit on the document's own pixel boundaries -- document pixel
    x=1/2/3 map to device x=8/16/24 (``CHECKER_CELL_PX(1) * zoom(8)``), never a
    TILE_SIZE-derived value.
    """
    doc = 4
    zoom = 8.0
    scene = _themed_scene(make_scene, theme, doc, doc)
    scene.set_grid_enabled(False)  # isolate from the pixel-grid's own LOD gate
    img = _render_zoomed(scene, doc, doc, zoom)

    row = 16  # interior device row, clear of the top/bottom border stroke
    # Start at device column 1, not 0: the exposed rect starts at the scene
    # origin, which is also the document's own LEFT-edge border pixel (column
    # 0) -- unrelated to the checker-cell transitions this test measures.
    prev = img.pixelColor(1, row)
    transitions = []
    for x in range(2, img.width()):
        c = img.pixelColor(x, row)
        if c != prev:
            transitions.append(x)
            prev = c
    assert transitions == [8, 16, 24]


# --------------------------------------------------------------------------- #
# Fidelity assertion (REQ-CGS-UI-003, no scenario ID supplied) -- exactly two  #
# colours inside the canvas, catching any smoothing/AA creeping into the fill. #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_003_exactly_two_colours_inside_canvas(make_scene, theme):
    """Fidelity assertion: the canvas interior renders EXACTLY the theme's two
    checker tones -- no smoothing, no blended third colour -- across a whole
    interior block, not just a single sampled pair.
    """
    doc = 10
    scene = _themed_scene(make_scene, theme, doc, doc)
    scene.set_grid_enabled(False)
    img = _render_flat(scene, doc, doc)

    light = _rgb(scene._checker_light)
    dark = _rgb(scene._checker_dark)
    interior = {_rgb(img.pixelColor(x, y)) for x in range(2, 8) for y in range(2, 8)}
    assert interior == {light, dark}


# --------------------------------------------------------------------------- #
# SC-CGS-UI-004-1/-2 — no checker colour anywhere outside the document, incl. #
# when the document edge crosses the middle of the viewport.                  #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_004_no_checker_colour_outside_document(make_scene, theme):
    """SC-CGS-UI-004-1: past the document edge the checker never continues --
    every pixel outside a 6x6 document, within a viewport extending 4px past
    it on the right and bottom, is neither checker tone.
    """
    doc = 6
    scene = _themed_scene(make_scene, theme, doc, doc)
    scene.set_grid_enabled(False)
    expose = doc + 4
    img = _render_flat(scene, expose, expose)

    light = _rgb(scene._checker_light)
    dark = _rgb(scene._checker_dark)
    for x in range(expose):
        for y in range(expose):
            if x >= doc or y >= doc:
                colour = _rgb(img.pixelColor(x, y))
                assert colour != light
                assert colour != dark


def test_req_cgs_ui_004_no_checker_colour_when_edge_crosses_viewport_middle(
    make_scene, theme
):
    """SC-CGS-UI-004-2: with an 8x8 document rendered into a 16x16 viewport, the
    document's right and bottom edges sit exactly in the middle of the
    viewport in each direction -- past them, still no checker colour.
    """
    doc = 8
    scene = _themed_scene(make_scene, theme, doc, doc)
    scene.set_grid_enabled(False)
    viewport = doc * 2  # the document edge sits at the exact viewport middle
    img = _render_flat(scene, viewport, viewport)

    light = _rgb(scene._checker_light)
    dark = _rgb(scene._checker_dark)
    outside_has_content = False
    inside_has_checker = False
    for x in range(viewport):
        for y in range(viewport):
            colour = _rgb(img.pixelColor(x, y))
            if x >= doc or y >= doc:
                outside_has_content = True
                assert colour != light
                assert colour != dark
            elif colour in (light, dark):
                inside_has_checker = True
    assert outside_has_content  # the outside region was actually sampled
    assert inside_has_checker  # and the inside region actually has checker


# --------------------------------------------------------------------------- #
# SC-CGS-UI-005-1/-2 — every point outside the canvas is ONE colour, equal to #
# neither checker tone, per theme (both covered by the autouse theme         #
# fixture's light/dark parametrisation -- not hand-looped here).             #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_005_outside_canvas_is_uniform_workspace_colour(make_scene, theme):
    """SC-CGS-UI-005-1 (light) / SC-CGS-UI-005-2 (dark): every point clear of the
    document and its cosmetic border reads the single workspace colour, equal
    to neither checker tone of ``theme``.
    """
    doc = 6
    scene = _themed_scene(make_scene, theme, doc, doc)
    scene.set_grid_enabled(False)
    expose = doc + 6
    img = _render_flat(scene, expose, expose)

    workspace = _rgb(scene._workspace_color)
    light = _rgb(scene._checker_light)
    dark = _rgb(scene._checker_dark)
    assert workspace != light
    assert workspace != dark

    margin = 2  # clear of the cosmetic border stroke on the doc edge
    sampled = False
    for x in range(expose):
        for y in range(expose):
            if x >= doc + margin or y >= doc + margin:
                sampled = True
                assert _rgb(img.pixelColor(x, y)) == workspace
    assert sampled


# --------------------------------------------------------------------------- #
# SC-CGS-UI-006-1/-2/-3 — the cosmetic canvas border is exactly              #
# CANVAS_BORDER_WIDTH_PX (1) device px wide at 100% AND at 6400% zoom -- the  #
# same thickness at both, which is what "cosmetic" means. Same document and  #
# same edge (x=4) used at every zoom so the -3 comparison is meaningful.      #
# --------------------------------------------------------------------------- #

_BORDER_DOC = 4
_BORDER_EXPOSE_W = 8
_BORDER_EXPOSE_H = 4
_BORDER_DOC_ROW = 2  # interior document row, clear of the top/bottom border


def test_req_cgs_ui_006_border_one_device_px_at_100pct(make_scene, theme):
    """SC-CGS-UI-006-1: the border is exactly CANVAS_BORDER_WIDTH_PX device px
    wide at 100% zoom (zoom = 1.0)."""
    scene = _themed_scene(make_scene, theme, _BORDER_DOC, _BORDER_DOC)
    scene.set_grid_enabled(False)
    zoom = 1.0
    img = _render_zoomed(scene, _BORDER_EXPOSE_W, _BORDER_EXPOSE_H, zoom)
    border_rgb = _rgb(scene._border_color)
    y = round(_BORDER_DOC_ROW * zoom)
    width = round(_BORDER_EXPOSE_W * zoom)
    assert (
        _border_run_length(img, y, border_rgb, width, x_start=1)
        == CANVAS_BORDER_WIDTH_PX
    )


def test_req_cgs_ui_006_border_one_device_px_at_6400pct(make_scene, theme):
    """SC-CGS-UI-006-2: the border is still exactly CANVAS_BORDER_WIDTH_PX
    device px wide at 6400% zoom (zoom = 64.0) -- a cosmetic pen does not
    scale with the world transform."""
    scene = _themed_scene(make_scene, theme, _BORDER_DOC, _BORDER_DOC)
    scene.set_grid_enabled(False)
    zoom = 64.0
    img = _render_zoomed(scene, _BORDER_EXPOSE_W, _BORDER_EXPOSE_H, zoom)
    border_rgb = _rgb(scene._border_color)
    y = round(_BORDER_DOC_ROW * zoom + zoom / 2)  # middle of that document row's band
    width = round(_BORDER_EXPOSE_W * zoom)
    assert (
        _border_run_length(img, y, border_rgb, width, x_start=1)
        == CANVAS_BORDER_WIDTH_PX
    )


def test_req_cgs_ui_006_border_thickness_matches_across_zoom(make_scene, theme):
    """SC-CGS-UI-006-3: the border measures the SAME device-px thickness at
    100% and at 6400% -- the actual meaning of "cosmetic". Re-measures both
    independently (own scenes) rather than reusing the two tests above, so
    this test stands on its own evidence.
    """
    scene_lo = _themed_scene(make_scene, theme, _BORDER_DOC, _BORDER_DOC)
    scene_lo.set_grid_enabled(False)
    zoom_lo = 1.0
    img_lo = _render_zoomed(scene_lo, _BORDER_EXPOSE_W, _BORDER_EXPOSE_H, zoom_lo)
    border_rgb = _rgb(scene_lo._border_color)
    y_lo = round(_BORDER_DOC_ROW * zoom_lo)
    width_lo = round(_BORDER_EXPOSE_W * zoom_lo)
    len_lo = _border_run_length(img_lo, y_lo, border_rgb, width_lo, x_start=1)

    scene_hi = _themed_scene(make_scene, theme, _BORDER_DOC, _BORDER_DOC)
    scene_hi.set_grid_enabled(False)
    zoom_hi = 64.0
    img_hi = _render_zoomed(scene_hi, _BORDER_EXPOSE_W, _BORDER_EXPOSE_H, zoom_hi)
    y_hi = round(_BORDER_DOC_ROW * zoom_hi + zoom_hi / 2)
    width_hi = round(_BORDER_EXPOSE_W * zoom_hi)
    len_hi = _border_run_length(img_hi, y_hi, border_rgb, width_hi, x_start=1)

    assert len_lo == len_hi == CANVAS_BORDER_WIDTH_PX


# --------------------------------------------------------------------------- #
# Checker/preview alignment (REQ-CGS-UI-003/-005, no scenario ID supplied):   #
# a floating preview's own checker repaint must agree in parity with the      #
# canvas's own drawBackground checker across the region boundary.            #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_003_checker_preview_alignment_no_phase_shift(make_scene, theme):
    """A transparent floating-preview region repaints the checker via the same
    shared ``_checker_brush`` (``_FloatingPreviewItem.paint`` ->
    ``_fill_checker``) as ``CanvasScene.drawBackground`` itself. Every pixel
    under a fully transparent preview image must come out IDENTICAL to the
    baseline render with no preview shown -- proving the two paint sites agree
    on checker phase, with no seam at the region boundary.
    """
    doc = 8
    scene = _themed_scene(make_scene, theme, doc, doc)
    scene.set_grid_enabled(False)

    def _render():
        img = QImage(doc, doc, QImage.Format.Format_RGBA8888)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        scene.render(painter, QRectF(0, 0, doc, doc), QRectF(0, 0, doc, doc))
        painter.end()
        return img

    baseline = _render()

    region = QRectF(2, 2, 4, 4)
    transparent = QImage(4, 4, QImage.Format.Format_ARGB32)
    transparent.fill(Qt.GlobalColor.transparent)
    scene._float_item.set_preview(transparent, region)

    with_preview = _render()

    checked_any = False
    for x in range(2, 6):
        for y in range(2, 6):
            checked_any = True
            assert with_preview.pixelColor(x, y) == baseline.pixelColor(x, y)
    assert checked_any


def test_req_cgs_ui_003_checker_phase_never_repositioned_via_setpos():
    """The alignment invariant every rendering test above relies on: item
    coordinates equal scene coordinates throughout ``canvas_scene.py`` ONLY
    because no ``QGraphicsItem`` in this module is ever repositioned via
    ``setPos`` (a 1-unit translate would invert the checker parity against
    the canvas). Pinned directly by source inspection so a future ``setPos``
    call fails this test rather than silently shifting the checker.
    """
    import pixelart_creator.ui.canvas_scene as canvas_scene_module

    source = Path(canvas_scene_module.__file__).read_text(encoding="utf-8")
    assert "setPos" not in source


# --------------------------------------------------------------------------- #
# SC-CGS-UI-010-1/-2 — LOD: below the on-screen-edge floor the checker is a   #
# flat blend (no pattern); AT the floor (zoom == ZOOM_MIN, cell ==            #
# CHECKER_CELL_PX) it is still a pattern, never a blend. Unit-level via       #
# _fill_checker directly, with a hand-set world transform -- a QGraphicsView  #
# can no longer produce the below-floor case now that ZOOM_MIN clamps zoom to #
# 1:1, so zooming a view cannot exercise SC-CGS-UI-010-1 at all.              #
# --------------------------------------------------------------------------- #


def test_req_cgs_ui_010_below_lod_floor_blends_flat(theme):
    """SC-CGS-UI-010-1: below CHECKER_MIN_ON_SCREEN_EDGE_PX the checker is a
    single flat blend colour, never a pattern. ``scale`` is derived from the
    real constants (half the floor's on-screen cell edge, in device px) so
    this stays strictly below threshold regardless of the constants' actual
    values, never a bare hard-coded number.
    """
    checker_light, checker_dark, _grid = canvas_roles(theme)
    checker = _build_checker_brush(checker_light, checker_dark, CHECKER_CELL_PX)

    scale = (CHECKER_MIN_ON_SCREEN_EDGE_PX / CHECKER_CELL_PX) / 2
    cell_edge_px = checker.cell * scale
    assert cell_edge_px < CHECKER_MIN_ON_SCREEN_EDGE_PX  # precondition: below floor

    img = QImage(8, 8, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setWorldTransform(QTransform().scale(scale, scale))
    _fill_checker(painter, QRectF(0, 0, 16, 16), checker)
    painter.end()

    seen = {_rgb(img.pixelColor(x, y)) for x in range(8) for y in range(8)}
    blend = _rgb(checker.blend)
    light = _rgb(checker_light)
    dark = _rgb(checker_dark)
    assert seen == {blend}  # one flat colour, no pattern
    assert blend != light
    assert blend != dark


def test_req_cgs_ui_010_at_lod_floor_zoom_1_paints_pattern(theme):
    """SC-CGS-UI-010-2: AT the 1:1 zoom floor -- zoom == ZOOM_MIN (1.0), cell ==
    CHECKER_CELL_PX (1 device px), exactly CHECKER_MIN_ON_SCREEN_EDGE_PX -- the
    checker still renders a PATTERN, never a blend. This is the exact-boundary
    case the task calls out by name: a '<=' gate (or an earlier draft's 3.0
    floor) would blend here and silently repeal "one square is one document
    pixel" at the product's most common zoom. Asserted AT the floor, not near
    it -- a test at zoom 1.1 would pass under both the correct and the broken
    implementation and prove nothing.
    """
    # If either constant ever drifts this precondition fails loudly, rather
    # than silently exercising a near-floor case instead of the floor itself.
    assert CHECKER_CELL_PX * ZOOM_MIN == CHECKER_MIN_ON_SCREEN_EDGE_PX

    checker_light, checker_dark, _grid = canvas_roles(theme)
    checker = _build_checker_brush(checker_light, checker_dark, CHECKER_CELL_PX)

    zoom = ZOOM_MIN  # == 1.0, exactly the LOD floor -- not near it
    img = QImage(8, 8, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setWorldTransform(QTransform().scale(zoom, zoom))
    _fill_checker(painter, QRectF(0, 0, 8, 8), checker)
    painter.end()

    seen = {_rgb(img.pixelColor(x, y)) for x in range(8) for y in range(8)}
    light = _rgb(checker_light)
    dark = _rgb(checker_dark)
    blend = _rgb(checker.blend)
    assert seen == {light, dark}  # a pattern: both tones present, nothing else
    assert blend not in seen
