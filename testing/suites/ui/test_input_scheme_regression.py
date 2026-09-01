"""Regression net for the input-scheme remap — T-01, wave 0 (AGT-06).

Pins the behaviours ``design-docs/specs/input-scheme/spec.md`` §8 lists as
"must be proven unchanged" (rows R-1..R-34, scenarios ``SC-R-01..34``), on
**unmodified** ``be10b9c`` product code. Every test here must be green
BEFORE any wave-1+ product edit lands — a failure here is a wave-0 defect,
never "a discovery about the feature" (tasks.md §0 rule 2).

**This module does not re-test every row.** Per the task's own instruction,
a row already protected by an existing suite is CITED, not duplicated. The
full 34-row citation table (which rows are pinned here vs. which existing
file already pins them) lives in the AGT-06 subagent report for this task,
not in this docstring, so the map is not duplicated in two places that can
drift apart.

This module writes ONLY new coverage for the rows that had none, or had only
a partial/weak pin, when the branch's baseline
(``design-docs/auxiliary/baseline-input-scheme-20260830.md``) and a follow-up
suite read were taken:

  R-13 (guide creation, the untested half) · R-15 (the tilemap stamp keys,
  strengthened to per-key distinct assertions + tool/mode isolation) ·
  R-17/R-18/R-20/R-21/R-22 (exact keybinding VALUES, not just "non-empty") ·
  R-24 (Space toggles playback — zero coverage before this module) ·
  R-26 (the hub's tool gate, widened from 2 of 11 tool ids to all 11) ·
  R-32 (selection persists across a REAL tool-switch dispatch through
  ``Main_Window._on_tool_action`` — the exact function T-15 will change) ·
  R-33 (``web_viewer/``/``sync_backend/`` untouched — a static git-diff check;
  RETIRED 2026-09-01, see the comment where it used to live, near the tail
  of this module — the constraint was scoped to this job and PR #34 closed
  the job it protected).

**T-22 addendum (2026-08-31, wave 8, post-implementation).** T-21 (pointer
surface) landed with the D-16 amendment: plain wheel travels Favourites and
``Shift``+wheel zooms on all four scrollable surfaces, not only the two
painting surfaces D-2 originally scoped. T-22's own ``Satisfies:`` list names
seven rows (``SC-R-01,02,03,06,07,08,09``) for re-verification against the
now-implemented code. Five (R-1/R-2/R-3/R-8/R-9) were re-run this session
against the current branch head and are unaffected — their wave-0 citations
still hold and are not duplicated here. Two (R-6/R-7) needed fresh coverage:
D-16 explicitly INVERTS what "still zooms" means for the reference board and
an extra document view — "plain wheel" becomes "Shift+wheel" — and the
wave-0 citation for R-6 (``test_aids_edges.py::
test_reference_board_wheel_clear_and_always_on_top``) never carried a zoom
assertion to invert in the first place (confirmed directly, not assumed),
so the row's real content had no test proving it at all until now. R-7's own
wave-0 citation (``test_document_view_wheel_and_change_event``) WAS one of
the 12 measured, now-inverted regressions (T-22, in ``test_aids_edges.py``
itself) and remains its citation; the two tests below add the two clauses
neither prior test carried: the active colour stays unchanged, and (R-7) the
MAIN canvas's own zoom is unaffected by an extra view's independent zoom.

Both themes are covered structurally: ``testing/suites/ui/conftest.py``'s
``theme`` fixture is ``autouse`` and parametrized over light/dark for the
whole UI suite, so every test in this module already runs twice without a
local parametrize.

Headless: ``QT_QPA_PLATFORM=offscreen`` is forced by the suite's own
``conftest.py`` (``pytest_configure``); no test below sets it itself.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QMouseEvent, QWheelEvent

from pixelart_creator.logic.favourites import Favourites
from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.guides_rulers_overlay import (
    GuideOrientation,
    Guides_Rulers_Overlay,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.multi_view import Multi_View
from pixelart_creator.ui.playback_controls import Playback_Controls
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas
from pixelart_creator.ui.tools import (
    DitherTool,
    EllipseTool,
    EraserTool,
    FloodFillTool,
    LassoTool,
    LineTool,
    MagicWandTool,
    PencilTool,
    PickerTool,
    RectangleTool,
    RectSelectTool,
)
from testing.suites.ui._ui_helpers import press, release

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# =========================================================================
# R-13 — guides still behave as shipped: the CREATE half (SC-R-13)
# =========================================================================
# The existing net (``test_guides_gestures.py``) proves drag-off-canvas
# removal, drag-to-move and the right-click "Remove guide" menu entry — but
# nothing in the suite drives ``Ruler_Strip.guideCreationRequested`` through
# to an actual ``Guides_Overlay.add_guide`` call (``_ui_helpers`` wraps
# ``test_aids_edges.py``'s ``test_ruler_mouse_press_emits_guide_request``,
# which stops at the signal and never checks a guide was placed). This is
# the create-half gap, closed here on unmodified code.


def test_r13_ruler_press_creates_a_guide_via_the_public_wiring(make_view):
    """SC-R-13 (create half): a real left-press on the overlay's OWN
    vertical ruler strip adds a guide — through the exact signal
    connection ``Guides_Rulers_Overlay.__init__`` wires
    (``_v_ruler.guideCreationRequested -> _on_guide_requested ->
    Guides_Overlay.add_guide``), never a hand-built substitute."""
    view, scene, _stack = make_view(64, 64)
    guides = Guides_Rulers_Overlay(view, scene, QRectF(0, 0, 64, 64))
    guides.set_enabled(True)
    view.set_guides_overlay(guides)

    assert guides.overlay_item().guides() == ()

    guides._v_ruler.resize(20, 200)
    evt = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5.0, 40.0),
        QPointF(5.0, 40.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    guides._v_ruler.mousePressEvent(evt)

    placed = guides.overlay_item().guides()
    assert len(placed) == 1
    assert placed[0].orientation is GuideOrientation.VERTICAL


# =========================================================================
# R-15 — the tilemap stamp keys still work (SC-R-15), strengthened
# =========================================================================
# The existing ``test_flip_rotate_keys`` only asserts "some flag changed OR
# the brush gid is non-base" after all three keys — it cannot tell H from V
# from R, and never checks the widget's own tool state. This job touches
# ``tilemap_canvas.py`` (T-21), so a real per-key pin matters here.


def test_r15_h_v_r_stamp_keys_each_toggle_their_own_axis_only(
    qtbot, theme, make_tilemap_setup
):
    """SC-R-15: H flips horizontal only; V flips vertical only (H unchanged);
    R rotates (composes all three); the active stamping tool never changes."""
    tileset, tilemap = make_tilemap_setup()
    stack = _undo_stack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_active_layer(0)
    canvas.set_brush_gid(tileset.first_gid)

    tool_before = canvas.active_tool()
    flags_0 = canvas.stamp_flags()  # (h, v, d) — starts (False, False, False)
    assert flags_0 == (False, False, False)

    _key(canvas, Qt.Key.Key_H)
    flags_1 = canvas.stamp_flags()
    assert flags_1 == (True, False, False)  # only H toggled

    _key(canvas, Qt.Key.Key_V)
    flags_2 = canvas.stamp_flags()
    assert flags_2 == (True, True, False)  # only V toggled; H untouched

    _key(canvas, Qt.Key.Key_R)
    flags_3 = canvas.stamp_flags()
    assert flags_3 != flags_2  # rotate composed the flags into a new state

    assert canvas.active_tool() is tool_before  # no tool changed, per SC-R-15


def _undo_stack():
    from PySide6.QtGui import QUndoStack

    return QUndoStack()


def _key(canvas, key) -> None:
    canvas.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    )


# =========================================================================
# R-17, R-18, R-20, R-21, R-22 — exact keybinding VALUES (§8.2)
# =========================================================================
# The existing net (``test_a11y_theme.py``, ``test_selection_actions.py``)
# asserts several of these shortcuts are merely non-empty, not that they
# hold the SPECIFIC key combination the remap must not disturb. A remap
# that accidentally rebinds Ctrl+Z to something else would pass the
# non-empty check and still be a real regression. Follows the codebase's
# own established idiom (see ``test_sc_u002_1_f1_shortcut_opens_guide``):
# assert the exact ``QKeySequence``, then ``.trigger()`` the action and
# assert the OBSERVABLE effect — never a raw ``QTest.keyClick`` (avoided
# elsewhere in this suite for exactly the same offscreen-routing reasons).


def test_r17_ctrl_z_undo_and_ctrl_y_redo_exact_bindings_and_effect(qtbot):
    """SC-R-17: Ctrl+Z / Ctrl+Y are still undo/redo, by binding AND effect."""
    win = _window(qtbot)
    assert win._undo_action.shortcut() == QKeySequence("Ctrl+Z")
    assert win._redo_action.shortcut() == QKeySequence("Ctrl+Y")

    record = win.active_tab()
    buf = record.scene.active_buffer()
    record.view.set_active_color(RED)
    press(record.view, 2, 2)
    release(record.view, 2, 2)
    assert buf.get_pixel(2, 2) == RED
    assert record.stack.count() == 1

    win._undo_action.trigger()
    assert buf.get_pixel(2, 2) == TRANSPARENT
    win._redo_action.trigger()
    assert buf.get_pixel(2, 2) == RED


def test_r18_ctrl_n_o_s_exact_bindings(qtbot):
    """SC-R-18: Ctrl+N / Ctrl+O / Ctrl+S are still bound to new/open/save."""
    win = _window(qtbot)
    assert win._new_action.shortcut() == QKeySequence("Ctrl+N")
    assert win._open_action.shortcut() == QKeySequence("Ctrl+O")
    assert win._save_action.shortcut() == QKeySequence("Ctrl+S")


def test_r20_ctrl_shift_a_deselect_exact_binding_and_effect(qtbot):
    """SC-R-20 (testable half): Ctrl+Shift+A still deselects, exact binding.

    The OTHER half of SC-R-20 — that the NEW ``Shift+A`` (picker) does not
    shadow it — needs the post-remap binding to exist and is out of scope
    for a wave-0 pin on unmodified code; it is T-10's (tasks.md wave 3,
    ``SC-R-16..R-25``), run after the remap lands.
    """
    win = _window(qtbot)
    assert win._select_all_action.shortcut() == QKeySequence("Ctrl+A")
    assert win._deselect_action.shortcut() == QKeySequence("Ctrl+Shift+A")

    record = win.active_tab()
    buf = record.scene.active_buffer()
    win._select_all_action.trigger()
    assert record.view.active_selection() is not None
    win._deselect_action.trigger()
    assert record.view.active_selection() is None
    assert record.stack.count() == 0  # deselect pushes nothing (SC-R-20)
    assert buf is record.scene.active_buffer()  # no content mutation


def test_r21_ctrl_i_inverts_selection_exact_binding_and_effect(qtbot):
    """SC-R-21: Ctrl+I still inverts the selection, exact binding + effect."""
    win = _window(qtbot)
    assert win._invert_action.shortcut() == QKeySequence("Ctrl+I")

    record = win.active_tab()
    buf = record.scene.active_buffer()
    mask = rect_mask(buf.width, buf.height, 0, 0, 2, 2)
    record.view.set_selection(mask)
    win._invert_action.trigger()
    inverted = record.view.active_selection()
    assert inverted is not None
    assert not inverted.is_selected(0, 0)  # the original region is now excluded
    assert inverted.is_selected(buf.width - 1, buf.height - 1)


def test_r22_ctrl_plus_minus_zoom_exact_bindings_and_effect(qtbot):
    """SC-R-22: Ctrl++ / Ctrl+- still zoom in/out, exact binding + effect."""
    win = _window(qtbot)
    assert win._zoom_in_action.shortcut() == QKeySequence("Ctrl++")
    assert win._zoom_out_action.shortcut() == QKeySequence("Ctrl+-")

    record = win.active_tab()
    before = record.view.zoom()
    win._zoom_in_action.trigger()
    after_in = record.view.zoom()
    assert after_in > before
    win._zoom_out_action.trigger()
    after_out = record.view.zoom()
    assert after_out < after_in


# =========================================================================
# R-24 — Space still toggles play/pause in the playback controls (SC-R-24)
# =========================================================================
# Zero coverage today: no test in the suite exercises the widget-scoped
# ``QShortcut`` at ``playback_controls.py:114-116``.


def test_r24_space_toggles_play_pause_no_pan(qtbot):
    """SC-R-24: Space toggles playback via the widget-scoped shortcut, and
    (structurally, by construction) never engages a canvas pan — the
    shortcut lives on ``Playback_Controls`` alone, a widget with no pan
    concept at all."""
    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)
    ctrl.set_context(lambda: [100, 100, 100], lambda: 0)

    assert ctrl.is_playing() is False
    ctrl._space_shortcut.activated.emit()
    assert ctrl.is_playing() is True
    ctrl._space_shortcut.activated.emit()
    assert ctrl.is_playing() is False


# =========================================================================
# R-26 — the hub's tool gate is unchanged (SC-R-26), widened to all 11 ids
# =========================================================================
# The existing net proves the gate for exactly 2 of the 11 tool ids
# (pencil: runs; eraser: does not). SC-R-26's own Examples table names 7;
# the underlying set (``_COLOUR_CONSUMING_TOOL_IDS``) has 11 members total.
# This closes the gate to the FULL set, matching the source of truth
# exactly rather than a hand-picked subset.

_CONSUMING = {
    PencilTool.tool_id,
    FloodFillTool.tool_id,
    LineTool.tool_id,
    RectangleTool.tool_id,
    EllipseTool.tool_id,
}
_NON_CONSUMING = {
    EraserTool.tool_id,
    PickerTool.tool_id,
    DitherTool.tool_id,
    RectSelectTool.tool_id,
    LassoTool.tool_id,
    MagicWandTool.tool_id,
}


@pytest.mark.parametrize("tool_id", sorted(_CONSUMING))
def test_r26_colour_consuming_tool_runs_on_a_completed_pick(qtbot, tool_id):
    """SC-R-26: for each colour-consuming tool id, a completed hub pick runs
    the tool at the anchor — exactly one command, the anchor pixel painted."""
    win = _window(qtbot)
    record = win.active_tab()
    win._active_tool_id = tool_id
    record.view.set_tool(win._tools[tool_id])
    before = record.stack.count()

    win._open_colour_hub(3, 3)
    colour = (12, 34, 56, 255)
    win._on_hub_color_applied(colour)
    win._on_hub_color_committed(colour)

    assert win._active_color == colour
    assert record.stack.count() - before == 1


@pytest.mark.parametrize("tool_id", sorted(_NON_CONSUMING))
def test_r26_non_colour_consuming_tool_runs_no_tool_on_a_completed_pick(qtbot, tool_id):
    """SC-R-26: for each of the six non-colour-writing tool ids, a completed
    hub pick sets the active colour (leg 1, never refused) but runs NO
    tool — the undo stack does not grow."""
    win = _window(qtbot)
    record = win.active_tab()
    win._active_tool_id = tool_id
    record.view.set_tool(win._tools[tool_id])
    before = record.stack.count()

    win._open_colour_hub(3, 3)
    colour = (65, 43, 21, 255)
    win._on_hub_color_applied(colour)
    win._on_hub_color_committed(colour)

    assert win._active_color == colour  # leg 1: never refused
    assert record.stack.count() == before  # leg 2: refused for this tool


def test_r26_consuming_and_non_consuming_sets_are_exactly_the_shipped_eleven(qtbot):
    """The two parametrized sets above must reconcile to the SAME eleven
    ids ``_COLOUR_CONSUMING_TOOL_IDS`` (+ its complement) uses today — the
    denominator check that stops this test from silently under-covering a
    twelfth tool id introduced elsewhere."""
    win = _window(qtbot)
    assert _CONSUMING | _NON_CONSUMING == set(win._tool_actions)
    assert len(_CONSUMING) + len(_NON_CONSUMING) == 11
    assert len(_CONSUMING) == 5
    assert len(_NON_CONSUMING) == 6


# =========================================================================
# R-32 — mask-constrained drawing is unchanged (SC-R-32), the untested half
# =========================================================================
# ``test_shape_mode.py::test_shape_commit_is_mask_constrained`` already
# proves a shape commit clips to an active mask (cited, not duplicated).
# What it does NOT prove — because it drives the tool via
# ``view.set_tool()`` directly — is that the selection SURVIVES a real
# tool switch dispatched through ``Main_Window._on_tool_action``, which is
# the exact function T-15 (wave 4) is about to add a selection-CLEAR
# branch to. That survival, for a non-selection tool, is the part this
# job puts genuinely at risk and it has zero coverage today.


def test_r32_selection_survives_a_real_tool_switch_to_a_non_selection_tool(qtbot):
    """SC-R-32: switching to the rectangle tool via the real
    ``_on_tool_action`` dispatch leaves an active selection unchanged."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    mask = rect_mask(buf.width, buf.height, 2, 2, 4, 4)
    record.view.set_selection(mask)
    assert record.view.active_selection() is not None

    # Real dispatch: trigger the QAction, exactly as a click/shortcut would.
    win._tool_actions["rectangle"].trigger()

    assert win._active_tool_id == "rectangle"
    survived = record.view.active_selection()
    assert survived is not None
    assert survived.is_selected(3, 3)
    assert not survived.is_selected(0, 0)


# =========================================================================
# R-33 — RETIRED (2026-09-01, AGT-06). Was: web_viewer/ and sync_backend/
# are not modified by this job.
# =========================================================================
# R-33 was a scope constraint on the input-scheme job alone: a static
# `git diff 1244cd5 HEAD -- web_viewer sync_backend` asserted empty, to keep
# that job's edits out of two directories it had no business touching. It
# held for the whole of that job. PR #34 merged and the input-scheme job
# closed — R-33's job is done.
#
# The test outlived the job because it was pinned to a fixed commit with no
# expiry, which quietly turns a job-scoped constraint into a permanent
# freeze on web_viewer/ and sync_backend/: it now forbids ANY future change
# to those directories, by anyone, for any reason, forever — not just
# changes belonging to the input-scheme job. PR #44 (Apache-2.0 copyright
# headers on all 247 shipped files, including 3 under sync_backend/ and 2
# under web_viewer/) tripped it for exactly this reason: the diff it
# measures is real and its assertion was never wrong about the facts, but
# by 2026-09-01 the constraint it encodes no longer means anything — the
# job it protected shipped and closed. Per the maintainer's standing
# ruling, the shipped software is the reference and tests adapt to it
# unless a real bug is revealed; a copyright notice on owned source is not
# a bug.
#
# Removed rather than re-pinned to a newer commit: re-pinning defers the
# identical failure to the next legitimate change to either directory and
# keeps asserting a constraint that no longer describes anything true about
# the product. Not weakened into a vacuous form either (e.g. "diff is
# small", or filtering out header lines) — a test that cannot fail is worse
# than no test, because it still looks like coverage.
#
# If web_viewer/ or sync_backend/ ever need a real ongoing invariant (e.g.
# "no product code changes web_viewer/ without a matching web_viewer/tests/
# update"), that is a new, deliberately-scoped test written against a
# rolling condition — never another `git diff <fixed-commit> HEAD` freeze.


# =========================================================================
# T-22 -- SC-R-06 / SC-R-07 (D-16-inverted, REQ-IS-UI-028) -- see the module
# docstring's T-22 addendum for why R-1/R-2/R-3/R-8/R-9 need no new test.
# =========================================================================


def _shift_wheel(delta_y: int) -> QWheelEvent:
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_sc_r06_reference_board_still_zooms_now_under_shift_wheel(qtbot):
    """SC-R-06 (D-16-inverted): the reference board still zooms by its own
    step -- on ``Shift``+wheel now, not plain wheel -- and the active
    colour is unchanged (no ``colorPicked`` emission)."""
    board = Reference_Board()
    qtbot.addWidget(board)
    board.set_favourites_model(Favourites([(10, 20, 30, 255)]))
    picks: list = []
    board.colorPicked.connect(picks.append)
    before_zoom = board._view.transform().m11()

    board.wheelEvent(_shift_wheel(120))

    assert board._view.transform().m11() > before_zoom
    assert picks == []  # the active colour is unchanged


def test_sc_r07_extra_document_view_still_zooms_now_under_shift_wheel(qtbot, make_view):
    """SC-R-07 (D-16-inverted): an extra document view still zooms -- on
    ``Shift``+wheel now -- the MAIN canvas zoom is unaffected, and the
    active colour is unchanged."""
    view, scene, _stack = make_view(16, 16)
    main_zoom_before = view.zoom()
    before_colour = view.active_color()
    mv = Multi_View(scene)
    v = mv.open_view()
    qtbot.addWidget(v)

    v.wheelEvent(_shift_wheel(120))

    assert v.transform().m11() > 1.0
    assert view.zoom() == pytest.approx(main_zoom_before)
    assert view.active_color() == before_colour
    mv.close_all()
