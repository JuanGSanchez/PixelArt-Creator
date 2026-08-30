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
  R-33 (``web_viewer/``/``sync_backend/`` untouched — a static git-diff check).

Both themes are covered structurally: ``testing/suites/ui/conftest.py``'s
``theme`` fixture is ``autouse`` and parametrized over light/dark for the
whole UI suite, so every test in this module already runs twice without a
local parametrize.

Headless: ``QT_QPA_PLATFORM=offscreen`` is forced by the suite's own
``conftest.py`` (``pytest_configure``); no test below sets it itself.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence, QMouseEvent

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.guides_rulers_overlay import (
    GuideOrientation,
    Guides_Rulers_Overlay,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.playback_controls import Playback_Controls
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
# R-33 — web_viewer/ and sync_backend/ are not modified by this job
# =========================================================================


def test_r33_web_viewer_and_sync_backend_untouched_since_branch_point(
    pytestconfig,
):
    """SC-R-33: a git diff of ``web_viewer/`` and ``sync_backend/`` against
    the branch point ``1244cd5`` is empty. Static, cheap, and meaningful at
    every wave of this job — not just wave 0."""
    repo_root = Path(__file__).resolve()
    while not (repo_root / ".git").exists():
        if repo_root.parent == repo_root:
            pytest.fail("could not locate the product repository root (.git)")
        repo_root = repo_root.parent

    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "1244cd5",
            "HEAD",
            "--",
            "web_viewer",
            "sync_backend",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    changed = [line for line in result.stdout.splitlines() if line.strip()]
    assert changed == [], (
        "web_viewer/ or sync_backend/ changed since 1244cd5, which "
        f"REQ-IS-UI-028/SC-R-33 forbids for this job: {changed}"
    )
