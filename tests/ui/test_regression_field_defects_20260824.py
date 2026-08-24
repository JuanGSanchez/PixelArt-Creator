"""Regression suite for the 2026-08-24 field-reported UI defect batch.

Six defects were reported against the shipped application (surfaced by
``design-docs/auxiliary/probe-runtime-canvas-20260824.py`` for RC-1/-2/-3, and
by direct investigation for the runtime-width-drift and silent-refusal/colour-
hub defects below), all fixed in this worktree and PROVEN to fail on the
unfixed ``main`` tree by the same probe technique before this module was
written (see the AGT-06 report for the per-scenario fails-on-main /
passes-on-branch table; that proof used a throwaway cross-tree runner and is
not re-executed here — this module tests the FIXED tree only, the tree it
lives in):

1. **Layout** (RC-1, ``FIX 1``/``FIX 3`` in ``ui/main_window.py``): the
   central canvas pane took only ~10% of the window regardless of the docks'
   split -- the window was never given an explicit size, and the tabified
   workflow docks' uncapped content-derived minimum widths (up to 766 px)
   overrode any ratio.
2. **Startup fit** (RC-2, ``FIX 2``): the document did not fill the pane at
   launch and a centre click landed outside it.
3. **Zoom** (RC-3, ``FIX 3`` in ``ui/canvas_view.py`` / ``ui/tilemap_canvas.py``):
   the zoom clamp floor was a flat ``fit_zoom()``, so ``zoom_out()`` could
   RAISE the zoom and the ``1.0`` preset stop was unreachable for any document
   smaller than the viewport.
4. **Runtime width drift** (``FIX 4``): toggling the Real-Size Preview dock
   permanently stole width from the canvas (356 px measured) with no
   recovery on hide.
5. **Silent refusals** (``FIX 5``): an out-of-document click, a non-editable
   (locked/reference/smart) paint target, and a tilemap stamp with brush gid
   0 all failed with NO observable feedback -- no signal, no undo entry, no
   notice.
6. **Colour hub tool run** (REQ-P3-UI-006 leg 2, ``UR-HUBFILL-1/-2``): a
   completed hub pick must run the active (colour-consuming) tool at the
   anchor as exactly ONE undoable command -- naively wiring a wheel-DRAG's
   live ``colorPicked`` stream to a tool run would fire once per mouse-move
   sample instead.

Also authored here, per today's ruling and the ``traceability.md`` gap it
records: **SC-U007-5**, the negative leg for the STANDALONE shade-ramp picker
(``ui/shade_ramp_picker.py``, distinct from the colour hub) -- it must set the
active colour and run NO tool. This one is NOT a fix-regression: it was
confirmed (proof session) to already pass on the unfixed ``main`` tree too
(``ui/main_window.py``'s ``_on_ramp_picked`` is untouched by this batch) --
it closes a coverage gap, not a regression.

Two effects named in the dispatch order are named here and NOT tested by this
module because neither can be proven by a worktree comparison:

* the **locale-packaging fix** (``pyproject.toml`` ``[tool.setuptools.package-data]``
  now globs ``i18n/*.qm``/``i18n/*.ts`` under ``pixelart_creator/`` instead of the
  old repository-top-level ``i18n/`` folder pip never installed) only manifests
  from an INSTALLED wheel -- ``LanguageManager.available_languages()`` reports
  ``['en', 'es']`` from EITHER worktree's dev tree (verified this session),
  so a worktree-comparison test would pass on both trees and prove nothing.
  Verified by other means: reading the diff (the glob now matches the moved
  files, which are tracked in this worktree) and confirming
  ``ui/i18n.py``'s ``_default_translations_dir()`` resolves the new
  package-internal path first. A real proof needs ``pip wheel .`` (or
  ``python -m build``) plus inspecting the built wheel's file listing --
  no freezing/build toolchain is available in this session.
* the **deploy-spec changes** (``packaging/pysidedeploy-*.spec``, the same B6
  fix's ``--include-data-dir=pixelart_creator/i18n=pixelart_creator/i18n``
  Nuitka argument) can only be proven by an actual Nuitka standalone freeze,
  which is out of scope here for the same reason.

Uses the REAL-event harness (``tests/ui/_ui_helpers.py``'s ``real_click_pixel``
/ ``real_right_click_pixel`` / ``QTest`` calls) wherever a test drives a
widget through its actual viewport/geometry, per the reason every one of
these defects shipped green: the existing suite drove ``Canvas_View``
handlers directly (``view.mousePressEvent(...)``), bypassing viewport
hit-testing, widget geometry and transform mapping -- precisely where these
bugs lived. The direct-handler helpers stay valid unit tests elsewhere and
are untouched.

Every test runs under both the light and dark theme via the autouse ``theme``
fixture (``conftest.py``) -- no per-test action needed.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDockWidget, QToolBar

from pixelart_creator.logic.constants import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    ZOOM_MIN,
    ZOOM_PRESET_STOPS,
)
from pixelart_creator.logic.document import Document, Layer
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import Tilemap
from pixelart_creator.ui.app import create_app
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas
from pixelart_creator.ui.tools import EraserTool, FloodFillTool, PencilTool
from tests.ui._ui_helpers import (
    prepare_for_click,
    real_click_pixel,
)

BLACK = (0, 0, 0, 255)


def _settle(app: QApplication, iterations: int = 8) -> None:
    """Flush pending layout passes a bounded number of times (never hang)."""
    for _ in range(iterations):
        app.processEvents()


def _left_toolbar_width(win: Main_Window) -> int:
    """Sum the width of every visible VERTICAL toolbar (the fixed left tools bar).

    User ruling 2026-08-24: the 0.80 canvas-pane target is measured against
    the space that is NOT this fixed left toolbar, never against the whole
    window (the toolbar's own width is deliberately left untouched).
    """
    return sum(
        t.width()
        for t in win.findChildren(QToolBar)
        if t.isVisible() and t.orientation() == Qt.Orientation.Vertical
    )


def _launched_window(qtbot, width: int = 1600, height: int = 900) -> Main_Window:
    """Build a shown window via ``create_app`` and settle it at an explicit,
    realistic width (never the platform default -- the offscreen platform
    reports an 800x800 screen, where an 80/20 split is arithmetically
    impossible against the right docks' 220 px floor, FIX-1/-3's own cap).
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    win.resize(width, height)
    _settle(app)
    return win


# --------------------------------------------------------------------------- #
# 1. Layout (RC-1): the central canvas takes >= 0.80 of the non-toolbar width #
# --------------------------------------------------------------------------- #


def test_rc1_central_canvas_takes_at_least_080_of_non_toolbar_width(qtbot):
    """RC-1: after create_app + show(), at an explicit realistic width, the
    central canvas pane takes >= 0.80 of the width NOT claimed by the fixed
    left tools toolbar (user ruling: the toolbar's own footprint is excluded
    from the ratio by design, not a defect)."""
    win = _launched_window(qtbot)
    view = win.findChildren(Canvas_View)[0]

    toolbar_px = _left_toolbar_width(win)
    usable = max(1, win.width() - toolbar_px)
    ratio = view.width() / usable

    assert toolbar_px > 0  # sanity: the toolbar exists and was measured
    assert ratio >= 0.80, (
        f"canvas ratio {ratio:.3f} of the non-toolbar width {usable}px "
        f"(window={win.width()}, toolbar={toolbar_px}, canvas={view.width()})"
    )


# --------------------------------------------------------------------------- #
# 2. Startup fit (RC-2): document fills the pane; a centre click paints one   #
# --------------------------------------------------------------------------- #


def test_rc2_document_fills_pane_at_startup(qtbot):
    """RC-2: at pristine startup (no resize/zoom yet) the document covers
    >= 0.98 of the viewport's smaller dimension. Measured BEFORE any resize
    or zoom mutation -- an earlier revision of the diagnostic probe this
    module descends from measured this AFTER a resize and silently read a
    stale fit as current; see that probe's own ordering-rule comment."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    view = win.findChildren(Canvas_View)[0]
    scene = view.scene()
    buf = scene.active_buffer()
    vp = view.viewport()

    top_left = view.mapFromScene(QPointF(0, 0))
    bottom_right = view.mapFromScene(QPointF(float(buf.width), float(buf.height)))
    doc_px = min(
        abs(bottom_right.x() - top_left.x()), abs(bottom_right.y() - top_left.y())
    )
    vp_px = min(vp.width(), vp.height())
    coverage = doc_px / max(1, vp_px)

    assert coverage >= 0.98, f"document covers only {coverage:.3f} of the viewport"


def test_rc2_real_click_at_pane_centre_paints_exactly_one_pixel(qtbot):
    """RC-2: a REAL ``QTest`` click at the viewport centre, at pristine
    startup, paints exactly one pixel -- the observable proof that the pane
    centre is inside the document AND hittable through the real event path
    (not a direct handler call)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    view = win.findChildren(Canvas_View)[0]
    scene = view.scene()
    buf = scene.active_buffer()
    vp = view.viewport()
    centre = vp.rect().center()

    before = buf.data.copy()
    QTest.mouseClick(
        vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, centre
    )
    _settle(app)
    after = scene.active_buffer().data

    changed = np.count_nonzero(np.any(before != after, axis=-1))
    assert changed == 1, f"centre click painted {changed} pixels, expected exactly 1"


# --------------------------------------------------------------------------- #
# 3. Zoom (RC-3): startup zoom in clamp; zoom_out() decreases; every preset   #
#    stop reachable; the min(ZOOM_MIN, fit_zoom) rule for BOTH a small and    #
#    a large (8K) document.                                                  #
# --------------------------------------------------------------------------- #


def test_rc3_startup_zoom_is_within_its_own_clamp(qtbot):
    """RC-3: ``view.zoom()`` at startup must already satisfy ``_clamp_zoom``.

    On the unfixed code the startup zoom (1.0) sat BELOW its own clamp floor
    (a flat ``fit_zoom()`` > 1.0 for a 64x64 document in a large viewport).
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    view = win.findChildren(Canvas_View)[0]

    zoom = view.zoom()
    assert (
        abs(view._clamp_zoom(zoom) - zoom) < 1e-9
    ), f"startup zoom {zoom} is outside its own clamp {view._clamp_zoom(zoom)}"


def test_rc3_zoom_out_strictly_decreases(qtbot):
    """RC-3: ``zoom_out()`` must DECREASE the zoom (on the unfixed code it
    RAISED 1.0 -> 1.765625 because the clamp floor exceeded the current zoom)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    view = win.findChildren(Canvas_View)[0]

    before = view.zoom()
    view.zoom_out()
    after = view.zoom()
    assert after < before, f"zoom_out() did not decrease: {before} -> {after}"


def test_rc3_every_preset_stop_is_reachable_for_a_small_document(qtbot):
    """RC-3: every ``ZOOM_PRESET_STOPS`` value, including 1.0, is reachable.

    On the unfixed code the flat ``fit_zoom()`` floor for a small document
    made the 1.0 preset stop UNREACHABLE (fit_zoom > 1.0 for a viewport
    larger than the document)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    view = win.findChildren(Canvas_View)[0]

    reachable = [
        stop for stop in ZOOM_PRESET_STOPS if abs(view._clamp_zoom(stop) - stop) < 1e-9
    ]
    assert reachable == list(
        ZOOM_PRESET_STOPS
    ), f"only {reachable} of {list(ZOOM_PRESET_STOPS)} reachable"
    assert 1.0 in reachable  # the specific stop the field report named


def test_rc3_clamp_floor_is_min_zoom_min_and_fit_zoom_for_a_large_8k_document(qtbot):
    """RC-3: ``min(ZOOM_MIN, fit_zoom)`` must hold for a document LARGER than
    the ceiling of a normal viewport (the full 8K / 7680x4320 ceiling, S1).

    A flat ``ZOOM_MIN`` (1.0) floor would make the whole-grid view of such a
    document unreachable -- its own ``fit_zoom`` is well below 1.0. This is
    the user-required case a flat floor of EITHER kind would break.

    2026-08-24 CI incident (PR #27, ``quality-gate``): the original version of
    this test built a REAL ``Document(MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)`` --
    a ~133 MB RGBA buffer -- and ``CanvasScene.drawBackground``'s
    ``_ensure_composite()`` then allocated a second, equally large composite
    buffer on first paint. Under ``pytest -n auto`` (8 workers on the
    self-hosted Windows runner) this reproduced as a genuine worker crash
    (``Windows fatal exception: access violation`` inside
    ``CanvasScene.drawBackground``, confirmed on this module's own unfixed
    commit 2cbe05e via a throwaway detached worktree before this rewrite --
    see the AGT-06 report for the verbatim trace), not an assertion failure --
    the memory hypothesis in the dispatch order was CONFIRMED, not assumed.

    The rule under test -- ``_fit_zoom()``/``_clamp_zoom()``/``fit()`` in
    ``ui/canvas_view.py`` -- reads only ``self.sceneRect()`` (the QGraphicsView/
    QGraphicsScene rect) and the viewport size; none of the three touches
    ``_document`` or ``_composite`` (confirmed by reading the source). So the
    8K case is exercised here by forcing an 8K **scene rect** directly onto a
    genuinely small (64x64), cheap document's scene via the inherited
    ``QGraphicsScene.setSceneRect()`` -- never allocating an 8K pixel buffer at
    all -- which still proves the exact rule the user required: a document
    whose fit_zoom is below ZOOM_MIN must still be viewable as a whole grid.
    ``fit()`` -> ``set_zoom()`` still calls ``scene.recomposite_exposed()``;
    that is verified a no-op here (the ``_stale.isEmpty()`` premise asserted
    below) so forcing the scene rect never triggers a real 8K recomposite."""
    doc = Document(64, 64, mode=ColorMode.RGBA, palette=Palette([BLACK]))
    scene = CanvasScene(doc)
    from PySide6.QtGui import QUndoStack

    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    view.resize(800, 800)
    view.show()
    qtbot.waitExposed(view)

    # Premise: recomposite_exposed() (called by fit() below) is a documented
    # no-op while nothing is stale -- true for this untouched fresh scene, so
    # forcing the scene rect below cannot smuggle in a real 8K recomposite.
    assert scene._stale.isEmpty()
    scene.setSceneRect(0, 0, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)

    fit_zoom = view._fit_zoom()
    assert fit_zoom < ZOOM_MIN, (
        f"test premise invalid: 8K fit_zoom {fit_zoom} is not below ZOOM_MIN "
        f"{ZOOM_MIN}"
    )

    view.fit()
    assert (
        abs(view.zoom() - fit_zoom) < 1e-9
    ), f"whole-grid view not reachable: zoom={view.zoom()}, expected {fit_zoom}"
    # A request far below the floor still clamps to fit_zoom, not to ZOOM_MIN.
    assert abs(view._clamp_zoom(0.0001) - fit_zoom) < 1e-9


# --------------------------------------------------------------------------- #
# 4. Runtime width drift: toggling Real-Size Preview must not shrink the     #
#    canvas, and a user's manual drag survives the toggle.                   #
# --------------------------------------------------------------------------- #


def test_rc4_toggling_real_size_preview_does_not_shrink_the_canvas(qtbot):
    """Toggling the Real-Size Preview dock must not permanently steal canvas
    width (on the unfixed code this stole 356 px and never recovered).

    Asserts the ratio is already healthy BEFORE the toggle too: on the
    unfixed tree the right column is already saturated by an even larger
    uncapped panel (RC-1's own defect), which otherwise masks a further
    steal from the preview dock (both read the same pinned-low value, no
    visible extra drop) -- the acceptance contract bundles "the canvas is
    properly sized" AND "toggling the dock does not shrink it further"."""
    win = _launched_window(qtbot)
    app = QApplication.instance()
    view = win.findChildren(Canvas_View)[0]

    toolbar_px = _left_toolbar_width(win)
    usable = max(1, win.width() - toolbar_px)
    before = view.width()
    assert (
        before / usable >= 0.80
    ), f"canvas already below 0.80 before any toggle ({before / usable:.3f})"

    win._preview_aid_action.trigger()  # show Real-Size Preview
    _settle(app)
    shown = view.width()

    win._preview_aid_action.trigger()  # hide it again
    _settle(app)
    after = view.width()

    assert after >= before, (
        f"canvas width did not recover after hiding the dock: "
        f"{before} -> {shown} -> {after}"
    )


def test_rc4_a_manual_dock_drag_survives_the_preview_toggle(qtbot):
    """A user's manual drag of the dock splitter must survive an unrelated
    dock's show/hide round-trip (the same mechanism ``resizeDocks`` drives)."""
    win = _launched_window(qtbot)
    app = QApplication.instance()
    view = win.findChildren(Canvas_View)[0]
    before_drag = view.width()

    right_docks = [
        d
        for d in win.findChildren(QDockWidget)
        if win.dockWidgetArea(d) == Qt.DockWidgetArea.RightDockWidgetArea
        and d.isVisible()
    ]
    assert right_docks, "no right-hand docks found"

    custom_width = 340  # deliberately wider than the default ratio would give
    win.resizeDocks(
        right_docks, [custom_width] * len(right_docks), Qt.Orientation.Horizontal
    )
    _settle(app)
    dragged_width = view.width()
    assert (
        dragged_width < before_drag
    ), f"the simulated drag had no effect: {before_drag} -> {dragged_width}"

    win._preview_aid_action.trigger()  # show
    _settle(app)
    win._preview_aid_action.trigger()  # hide
    _settle(app)
    after_toggle_width = view.width()

    assert (
        abs(after_toggle_width - dragged_width) <= 5
    ), f"manual drag lost after toggle: {dragged_width} -> {after_toggle_width}"


# --------------------------------------------------------------------------- #
# 5. Silent refusals: out-of-document click; three non-editable classes;     #
#    tilemap zero-brush stamp.                                               #
# --------------------------------------------------------------------------- #


def test_fix5_out_of_document_click_rejects_visibly_no_undo_entry(qtbot, make_view):
    """A REAL click outside the document bounds emits ``outOfDocumentClickRejected``
    and creates no undo entry (previously silent)."""
    view, scene, stack = make_view(64, 64)
    view.resize(200, 200)
    view.show()
    qtbot.waitExposed(view)
    prepare_for_click(view)

    before_count = stack.count()
    outside = (84, 84)  # inside the 200x200 viewport, outside the 64x64 document

    # Observer connected BEFORE the triggering action.
    with qtbot.waitSignal(view.outOfDocumentClickRejected, timeout=1000):
        real_click_pixel(view, *outside)

    assert stack.count() == before_count


@pytest.mark.parametrize("non_editable_kind", ["locked", "reference", "smart"])
def test_fix5_non_editable_layer_rejects_visibly_no_undo_entry(
    qtbot, make_view, non_editable_kind
):
    """All three non-editable classes (REQ-P4-UI-004/-010; CF-11) refuse a
    real click with a rejection signal and no undo entry -- previously only
    ``locked`` was surfaced; ``reference``/``smart`` fell through silently."""
    view, scene, stack = make_view(64, 64)
    layer = scene._document.frames[0].layers[0]
    if non_editable_kind == "locked":
        layer.locked = True
        expected_signal = view.lockedLayerEditRejected
    elif non_editable_kind == "reference":
        layer.reference = True
        expected_signal = view.nonEditableLayerEditRejected
    else:
        # A GENUINE second layer, never a self-reference: effective_buffer()
        # walks the smart_source chain to render the composite, and a
        # self-referencing smart_source recurses forever (an unrecoverable
        # native stack overflow was caught during this module's own proof
        # run -- a real repaint reaches effective_buffer() even though the
        # click itself is rejected before ever calling it).
        source_layer = Layer(PixelBuffer(64, 64, ColorMode.RGBA), name="Source")
        layer.smart_source = source_layer
        expected_signal = view.nonEditableLayerEditRejected

    view.resize(200, 200)
    view.show()
    qtbot.waitExposed(view)
    prepare_for_click(view)

    before_count = stack.count()
    with qtbot.waitSignal(expected_signal, timeout=1000):
        real_click_pixel(view, 5, 5)

    assert stack.count() == before_count


def test_fix5_tilemap_zero_brush_stamp_emits_no_tileset_bound_signal(qtbot):
    """A stamp with brush gid 0 on a tilemap with NO tileset bound emits
    ``noTilesetBoundRejected`` instead of returning silently.

    2026-08-24 CI incident (PR #27): the original version of this test
    asserted a blocking ``QMessageBox.warning`` mute, which the product code
    has since replaced with a non-blocking signal (the modal hung a headless
    parallel worker with nothing to dismiss it). This asserts the SIGNAL --
    the canvas's actual contract -- not a side effect of the status-bar shell
    wiring ``main_window.py`` does with it. Kept distinct from
    ``noActiveBrushRejected`` (below): a stamp with NO tileset bound must
    never satisfy on the "select a tile" signal or vice versa, so each test
    connects to exactly one of the two and waits on it alone."""
    from PySide6.QtGui import QUndoStack

    tilemap = Tilemap(tile_width=16, tile_height=16)
    tilemap.make_add_layer_command(name="Layer 1").execute()
    canvas = Tilemap_Canvas()
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, QUndoStack(), None)

    # Observer connected BEFORE the triggering action.
    with qtbot.waitSignal(canvas.noTilesetBoundRejected, timeout=1000):
        canvas._apply_stamp(0, 0)  # brush_base_gid defaults to 0; no tileset bound


def test_fix5_tilemap_zero_brush_stamp_emits_no_active_brush_signal(
    qtbot, make_tilemap_setup
):
    """A stamp with brush gid 0 on a tilemap that HAS a tileset emits
    ``noActiveBrushRejected`` -- the distinct signal for the other gid-0 case
    (a tileset IS bound; no tile is selected as the active brush)."""
    from PySide6.QtGui import QUndoStack

    _tileset, tilemap = make_tilemap_setup()
    canvas = Tilemap_Canvas()
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, QUndoStack(), None)

    # Observer connected BEFORE the triggering action.
    with qtbot.waitSignal(canvas.noActiveBrushRejected, timeout=1000):
        canvas._apply_stamp(0, 0)  # brush_base_gid still defaults to 0


# --------------------------------------------------------------------------- #
# 6. Colour hub: one undo entry per completed pick (not one per drag         #
#    sample); non-consuming tools hide the pick surface and run no tool.     #
# --------------------------------------------------------------------------- #


def test_req_p3_ui_006_wheel_drag_produces_exactly_one_undo_entry(qtbot):
    """REQ-P3-UI-006 leg 2: a wheel-pad DRAG (press + several moves + release)
    must run the active colour-consuming tool exactly ONCE -- naively wiring
    the live ``colorPicked`` stream would run it once per mouse-move sample."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    record = win.active_tab()
    win._active_tool_id = FloodFillTool.tool_id
    record.view.set_tool(win._tools[FloodFillTool.tool_id])

    win._open_colour_hub(5, 5)
    before_count = record.stack.count()

    pad = win._colour_hub._wheel._wheel
    pad.resize(120, 120)
    pad.show()
    qtbot.waitExposed(pad)

    QTest.mousePress(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(60, 60)
    )
    QTest.mouseMove(pad, QPoint(65, 55))
    QTest.mouseMove(pad, QPoint(70, 50))
    QTest.mouseMove(pad, QPoint(75, 45))
    QTest.mouseRelease(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(75, 45)
    )
    _settle(app)

    assert record.stack.count() - before_count == 1, (
        f"drag produced {record.stack.count() - before_count} undo entries, "
        "expected exactly 1 (one press + 3 moves + 1 release)"
    )


def test_req_p3_ui_006_non_consuming_tool_hides_pick_surface(qtbot):
    """SC-U006-13: for a non-colour-writing tool (eraser, the three selection
    tools, picker, dither) the hub hides the wheel/value/numeric/harmony
    surface and shows the explanatory note in its place."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    record = win.active_tab()
    win._active_tool_id = EraserTool.tool_id
    record.view.set_tool(win._tools[EraserTool.tool_id])

    win._open_colour_hub(5, 5)

    assert win._colour_hub._wheel.isVisible() is False
    assert win._colour_hub._pick_note.isVisible() is True


def test_req_p3_ui_006_favourite_under_non_consuming_tool_sets_colour_runs_no_tool(
    qtbot,
):
    """SC-U006-13: even a Favourites activation (which emits ``colorCommitted``
    uniformly) must run NO tool while a non-consuming tool is active -- it
    still sets the active colour (leg 1, never refused)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    record = win.active_tab()
    win._active_tool_id = EraserTool.tool_id
    record.view.set_tool(win._tools[EraserTool.tool_id])

    win._open_colour_hub(5, 5)
    before_count = record.stack.count()

    target = (11, 22, 33, 255)
    win._colour_hub.favourites_model().add(target)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    listw = win._colour_hub._favourites._list
    item = next(
        listw.item(i)
        for i in range(listw.count())
        if listw.item(i).data(Qt.ItemDataRole.UserRole) == target
    )
    win._colour_hub._favourites._on_item_activated(item)
    _settle(app)

    assert win._active_color == target
    assert record.stack.count() == before_count


def test_req_p3_ui_006_consuming_tool_pencil_click_favourite_runs_exactly_once(
    qtbot,
):
    """A companion positive leg for a DIFFERENT colour-consuming tool
    (pencil): a completed Favourites pick under an active pencil runs the
    tool exactly once (leg 2), at the hub's anchor pixel."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    record = win.active_tab()
    win._active_tool_id = PencilTool.tool_id
    record.view.set_tool(win._tools[PencilTool.tool_id])

    win._open_colour_hub(6, 6)
    before_count = record.stack.count()

    target = (44, 55, 66, 255)
    win._colour_hub.favourites_model().add(target)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    listw = win._colour_hub._favourites._list
    item = next(
        listw.item(i)
        for i in range(listw.count())
        if listw.item(i).data(Qt.ItemDataRole.UserRole) == target
    )
    win._colour_hub._favourites._on_item_activated(item)
    _settle(app)

    assert win._active_color == target
    assert record.stack.count() - before_count == 1
    assert record.scene.active_buffer().get_pixel(6, 6) == target


# --------------------------------------------------------------------------- #
# SC-U007-5 (coverage gap, not a fix-regression -- see module docstring):    #
# the standalone shade-ramp picker sets the active colour and runs no tool.  #
# --------------------------------------------------------------------------- #


def test_sc_u007_5_shade_ramp_pick_sets_colour_runs_no_tool(qtbot):
    """SC-U007-5: activating a shade-ramp swatch sets the active colour and
    runs NO tool (``ui/main_window.py``'s ``_on_ramp_picked`` only ever calls
    ``_set_active_color`` + ``_palette_panel.select_color`` -- distinct from
    the colour hub's leg-2 tool run, and this had no test on disk)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    record = win.active_tab()
    win._active_tool_id = PencilTool.tool_id
    record.view.set_tool(win._tools[PencilTool.tool_id])
    before_colour = win._active_color
    before_count = record.stack.count()

    swatch = win._ramp_picker._tint[2]
    swatch.click()
    _settle(app)

    assert win._active_color != before_colour
    assert record.stack.count() == before_count
