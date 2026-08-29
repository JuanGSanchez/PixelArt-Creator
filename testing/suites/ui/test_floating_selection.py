"""Floating-selection move/copy UI acceptance (REQ-P2-UI-030..036).

One test per acceptance criterion for Slice F-B (tasks FB-T1..T7), driving the
real :class:`~pixelart_creator.ui.canvas_view.Canvas_View` /
:class:`~pixelart_creator.ui.canvas_scene.CanvasScene` /
:class:`~pixelart_creator.ui.main_window.Main_Window` headlessly
(``QT_QPA_PLATFORM=offscreen``). Every test runs under **both** themes via the
autouse ``theme`` fixture in ``conftest.py``.

Mapping (spec §11 Gherkin ↔ REQ ↔ task):

- FB-T1 / REQ-P2-UI-030 — lift on press-inside (SC-U030-1); press-outside builds
  a new selection (SC-U030-2).
- FB-T2 / REQ-P2-UI-031 — drag = MOVE, non-destructive preview (SC-U031-1);
  offset tracks the cursor in integer pixels (SC-U031-2).
- FB-T3 / REQ-P2-UI-032 — Ctrl-only drag = COPY, origin intact (SC-U032-1; CL-F5
  reconciled to Ctrl only, whether Ctrl is held from the lift or applied mid-drag);
  copy-mode affordance (SC-U032-2); Ctrl copies as ONE command without touching the
  CL-4 combine, while an Alt interior drag stays the shipped subtract (SC-U032-3).
- FB-T4 / REQ-P2-UI-033 — release / Enter / tool-switch / tab-switch each commit
  ONE command (SC-U033-1..3); mask follows to destination (SC-U033-4).
- FB-T5 / REQ-P2-UI-034 — ESC restores exactly (SC-U034-1); no undo entry, mask
  returns (SC-U034-2).
- FB-T6 / REQ-P2-UI-035 — one-step undo/redo (SC-U035-1); NN/AA-off preview
  (SC-U035-2); legible in both themes (SC-U035-3).
- FB-T7 / REQ-P2-UI-036 — active-layer scope (SC-U036-1); off-canvas discard on
  commit (SC-U036-2); a11y hint tr()-wrapped + keyboard-reachable + visible focus
  (SC-U036-3).

The base buffer is asserted **byte-for-byte unchanged during a float** and only
mutated at commit — the core REQ-NEW-C non-destructive contract. Preview content
correctness lives in the logic suite (AGT-04); here we verify the UI observable
surface: controller state, the scene overlay geometry/visibility, the committed
buffer, the undo stack, and the a11y/theme wiring.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QUndoStack
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.constants import CHECKER_CELL_PX
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.overwrite_confirm_dialog import Overwrite_Confirm_Dialog
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tools import PencilTool, RectSelectTool
from pixelart_creator.ui.tools.floating_move import CONFIRM_FLOATING_OVERWRITE
from testing.suites.ui._ui_helpers import prepare_for_click, viewport_point_for_pixel

LEFT = Qt.MouseButton.LeftButton
NO_BTN = Qt.MouseButton.NoButton
NO_MOD = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
ALT = Qt.KeyboardModifier.AltModifier

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)
YELLOW = (240, 220, 40, 255)
TRANSPARENT = (0, 0, 0, 0)

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


# -- event helpers (modifier-carrying; the shared _ui_helpers force NoModifier) --
#
# Routed through the ONE shared coordinate source, viewport_point_for_pixel
# (view.mapFromScene), exactly like every helper in _ui_helpers.py -- never a
# hand-computed offset. This used to build the position as
# QPointF(x + 0.2, y + 0.2) and assume viewport (x, y) == scene pixel (x, y);
# that stopped holding once Canvas_View began inflating its own scene rect by
# a pan margin (REQ-CGS-UI-009), which gives the view's scrollable rect a
# negative origin. See _ui_helpers.prepare_for_click's docstring for the full
# measurement.


def _mev(view, etype, x, y, button, buttons, mod) -> QMouseEvent:
    point = viewport_point_for_pixel(view, x, y)
    pt = QPointF(point.x(), point.y())
    return QMouseEvent(etype, pt, pt, button, buttons, mod)


def press(view, x, y, mod=NO_MOD) -> None:
    view.mousePressEvent(
        _mev(view, QEvent.Type.MouseButtonPress, x, y, LEFT, LEFT, mod)
    )


def move(view, x, y, mod=NO_MOD) -> None:
    view.mouseMoveEvent(_mev(view, QEvent.Type.MouseMove, x, y, NO_BTN, LEFT, mod))


def release(view, x, y, mod=NO_MOD) -> None:
    view.mouseReleaseEvent(
        _mev(view, QEvent.Type.MouseButtonRelease, x, y, LEFT, NO_BTN, mod)
    )


def key(view, keycode, mod=NO_MOD) -> None:
    view.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, keycode, mod))


def _non_transparent(buf) -> int:
    """Count pixels with a non-zero alpha (RGBA buffer)."""
    return int(np.count_nonzero(buf.data[:, :, 3]))


# -- fixtures / builders ---------------------------------------------------


def _make_move_view(make_scene, qtbot, w=16, h=16):
    """A pinned view with the rect-select tool, a 3x3 selection (2,2)-(4,4) and a
    distinctive RED/GREEN/BLUE pattern inside it. Returns (view, scene, stack, buf)."""
    scene = make_scene(w, h)
    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    prepare_for_click(view)
    view.set_tool(RectSelectTool())
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    buf.set_pixel(3, 3, GREEN)
    buf.set_pixel(4, 4, BLUE)
    view.set_selection(rect_mask(w, h, 2, 2, 4, 4))
    return view, scene, stack, buf


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _prep_window_move(win):
    """Arm the active tab's view for a floating move: rect-select tool, pinned,
    a 3x3 selection with a RED pattern. Returns (view, scene, stack, buf)."""
    record = win.active_tab()
    view, scene, stack = record.view, record.scene, record.stack
    prepare_for_click(view)
    win._tool_actions[RectSelectTool.tool_id].trigger()
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    buf.set_pixel(3, 3, GREEN)
    buf.set_pixel(4, 4, BLUE)
    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    return view, scene, stack, buf


# =========================================================================
# FB-T1 / REQ-P2-UI-030 — lift/float interaction
# =========================================================================


def test_sc_u030_1_press_inside_lifts_nondestructive_preview(make_scene, qtbot):
    """SC-U030-1: pressing inside the mask lifts a floating preview that follows
    the cursor; the underlying pixels are NOT yet modified."""
    view, scene, _stack, buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()
    before = buf.copy()

    press(view, 3, 3)  # inside the (2,2)-(4,4) mask
    assert controller.is_active()

    move(view, 8, 8)  # drag by (5, 5)
    assert buf == before  # non-destructive: base untouched during the float

    # The floated-colours preview follows the cursor: origin bbox (2,2,4,4)
    # shifted by (5,5) -> destination top-left (7,7), size 3x3.
    rect = scene._float_item.boundingRect()
    assert scene._float_item.isVisible()
    assert (rect.left(), rect.top(), rect.width(), rect.height()) == (7, 7, 3, 3)

    controller.cancel()  # do not leak an active float


def test_sc_u030_2_press_outside_starts_new_selection(make_scene, qtbot):
    """SC-U030-2: pressing outside the active mask does not lift — it starts a new
    selection through the shipped build path."""
    view, _scene, _stack, _buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()

    press(view, 10, 10)  # outside the (2,2)-(4,4) mask
    assert not controller.is_active()
    move(view, 12, 12)
    release(view, 12, 12)

    assert not controller.is_active()
    mask = view.active_selection()
    assert mask is not None
    assert mask.bounds() == (10, 10, 12, 12)  # a fresh selection was built


# =========================================================================
# FB-T2 / REQ-P2-UI-031 — drag = move preview
# =========================================================================


def test_sc_u031_1_drag_previews_move_nondestructive(make_scene, qtbot):
    """SC-U031-1: a modifier-free drag is MOVE — the origin reads vacated (a
    dedicated origin overlay) and colours float at the offset, non-destructively."""
    view, scene, _stack, buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()
    before = buf.copy()

    press(view, 3, 3)
    move(view, 6, 5)  # offset (3, 2)

    assert controller.is_active() and not controller.is_copy()  # MOVE
    assert buf == before  # non-destructive
    assert scene._origin_shown  # MOVE shows the vacated-origin overlay
    rect = scene._float_item.boundingRect()  # dest bbox (5,4)-(7,6)
    assert (rect.left(), rect.top(), rect.width(), rect.height()) == (5, 4, 3, 3)

    controller.cancel()


def test_sc_u031_2_offset_tracks_cursor_in_integer_pixels(make_scene, qtbot):
    """SC-U031-2: the live offset tracks the cursor in integer pixel units — the
    marching-ants overlay shift and the committed destination both prove it."""
    view, scene, stack, buf = _make_move_view(make_scene, qtbot)

    press(view, 3, 3)
    move(view, 8, 6)  # cursor delta (5, 3)
    assert scene._selection_overlay._offset == (5, 3)

    release(view, 8, 6)  # commit at offset (5, 3)
    assert stack.count() == 1
    assert buf.get_pixel(7, 5) == RED  # RED at (2,2) moved to (7,5)
    assert buf.get_pixel(2, 2) == TRANSPARENT  # origin vacated


# =========================================================================
# FB-T3 / REQ-P2-UI-032 — modifier + drag = copy
# =========================================================================


@pytest.mark.parametrize(
    "ctrl_at_press", [True, False], ids=["ctrl-at-press", "ctrl-mid-drag"]
)
def test_sc_u032_1_ctrl_drag_previews_copy_origin_intact(
    make_scene, qtbot, ctrl_at_press
):
    """SC-U032-1 (CL-F5, Ctrl-only): holding **Ctrl** during the drag switches to
    COPY — whether Ctrl is held from the initial lift or applied mid-float (the live
    modifier re-sample). The origin stays intact (no vacate overlay) and the base is
    untouched pre-commit. Alt is NOT a copy trigger (it is the CL-4 subtract)."""
    view, scene, _stack, buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()
    before = buf.copy()

    press(view, 3, 3, mod=CTRL if ctrl_at_press else NO_MOD)
    move(view, 7, 3, mod=CTRL)  # offset (4, 0), Ctrl (copy) held during the drag

    assert controller.is_active() and controller.is_copy()  # COPY
    assert buf == before  # non-destructive
    assert not scene._origin_shown  # COPY keeps the origin — no vacate overlay

    controller.cancel()


def test_sc_u032_2_copy_mode_affordance_signals_copy(qtbot):
    """SC-U032-2: the copy-mode affordance (the status-bar hint) signals COPY while
    a copy float is active, and reverts to the move hint otherwise."""
    win = _window(qtbot)
    view, _scene, _stack, _buf = _prep_window_move(win)

    press(view, 3, 3)
    move(view, 7, 3, mod=CTRL)
    # isHidden() reflects the explicit hide flag independent of the (unshown)
    # window, unlike isVisible() which needs the whole hierarchy on screen.
    assert not win._float_hint.isHidden()
    assert "Copying" in win._float_hint.text()

    move(view, 7, 3, mod=NO_MOD)  # drop the modifier mid-drag -> back to MOVE
    assert "Moving" in win._float_hint.text()

    view.floating_controller().cancel()
    assert win._float_hint.isHidden()  # hint hides when no float is active


def test_sc_u032_3_ctrl_copy_commits_one_command_origin_intact(make_scene, qtbot):
    """SC-U032-3 (CL-F5, Ctrl-only): a Ctrl in-selection drag COPIES — it commits
    exactly ONE pixel-copy command (not a selection combine edit), keeps the origin
    intact and stamps the copy at the destination. The Alt interior drag is NOT copy;
    it remains the shipped CL-4 subtract, verified in test_rect_select_tool.py — so
    the earlier build-subtract collision no longer exists."""
    view, _scene, stack, buf = _make_move_view(make_scene, qtbot)

    press(view, 3, 3)
    move(view, 6, 2, mod=CTRL)  # offset (3, -1), Ctrl (copy) held
    release(view, 6, 2, mod=CTRL)

    assert stack.count() == 1  # ONE pixel-copy command, not a selection edit
    assert buf.get_pixel(2, 2) == RED  # origin intact (a copy, not a subtract/move)
    assert buf.get_pixel(5, 1) == RED  # copied to (2,2)+(3,-1)


# =========================================================================
# FB-T4 / REQ-P2-UI-033 — commit triggers
# =========================================================================


def test_sc_u033_1_release_commits_one_command(make_scene, qtbot):
    """SC-U033-1: releasing the mouse commits the float as exactly ONE undoable
    command (a MOVE: origin vacated + colours stamped at the destination)."""
    view, _scene, stack, buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()

    press(view, 3, 3)
    move(view, 7, 5)  # offset (4, 2)
    release(view, 7, 5)

    assert stack.count() == 1
    assert not controller.is_active()
    assert buf.get_pixel(2, 2) == TRANSPARENT  # origin vacated
    assert buf.get_pixel(6, 4) == RED  # stamped at (2,2)+(4,2)


def test_sc_u033_2_enter_commits_one_command(make_scene, qtbot):
    """SC-U033-2: pressing Enter commits the active float as ONE command."""
    view, _scene, stack, buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()

    press(view, 3, 3)
    move(view, 7, 5)  # offset (4, 2), no release
    assert controller.is_active()

    key(view, Qt.Key.Key_Return)
    assert not controller.is_active()
    assert stack.count() == 1
    assert buf.get_pixel(6, 4) == RED


def test_sc_u033_3_tool_switch_commits_one_command(qtbot):
    """SC-U033-3: switching tools commits the active float as ONE command."""
    win = _window(qtbot)
    view, _scene, stack, buf = _prep_window_move(win)
    controller = view.floating_controller()

    press(view, 3, 3)
    move(view, 7, 5)  # offset (4, 2), no release
    assert controller.is_active()

    win._tool_actions[PencilTool.tool_id].trigger()  # tool-switch commits first
    assert not controller.is_active()
    assert stack.count() == 1
    assert buf.get_pixel(6, 4) == RED


def test_sc_u033_3_tab_switch_commits_one_command(qtbot):
    """SC-U033-3 (tab variant): switching document tabs commits the leaving float."""
    win = _window(qtbot)
    view, _scene, stack, buf = _prep_window_move(win)
    controller = view.floating_controller()

    press(view, 3, 3)
    move(view, 7, 5)  # offset (4, 2), no release
    assert controller.is_active()

    win.new_document()  # opens + switches to a new tab -> commits the old float
    assert not controller.is_active()
    assert stack.count() == 1
    assert buf.get_pixel(6, 4) == RED


def test_sc_u033_4_mask_follows_to_destination(make_scene, qtbot):
    """SC-U033-4: after commit the selection mask follows to the destination."""
    view, _scene, _stack, _buf = _make_move_view(make_scene, qtbot)

    press(view, 3, 3)
    move(view, 7, 5)  # offset (4, 2)
    release(view, 7, 5)

    mask = view.active_selection()
    assert mask is not None
    assert mask.bounds() == (6, 4, 8, 6)  # (2,2,4,4) shifted by (4,2)


# =========================================================================
# FB-T5 / REQ-P2-UI-034 — ESC cancels and restores
# =========================================================================


def test_sc_u034_1_esc_restores_pre_move_state_exactly(make_scene, qtbot):
    """SC-U034-1: pressing ESC during a float restores the pre-move canvas exactly
    and records NO undoable command."""
    view, _scene, stack, buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()
    before = buf.copy()

    press(view, 3, 3)
    move(view, 9, 7)  # offset (6, 4)
    assert controller.is_active()

    key(view, Qt.Key.Key_Escape)
    assert not controller.is_active()
    assert buf == before  # byte-for-byte unchanged
    assert stack.count() == 0  # no command produced


def test_sc_u034_2_cancel_returns_mask_and_records_no_undo(make_scene, qtbot):
    """SC-U034-2: a cancelled float records NO undo entry and the mask returns to
    its pre-lift position (the ants offset resets to zero)."""
    view, scene, stack, _buf = _make_move_view(make_scene, qtbot)

    press(view, 3, 3)
    move(view, 9, 7)
    key(view, Qt.Key.Key_Escape)

    assert stack.count() == 0
    assert scene._selection_overlay._offset == (0, 0)  # mask outline back home
    mask = view.active_selection()
    assert mask is not None and mask.bounds() == (2, 2, 4, 4)  # unmoved


# =========================================================================
# FB-T6 / REQ-P2-UI-035 — reversibility, single command, render policy
# =========================================================================


def test_sc_u035_1_undo_restores_in_one_step_redo_reapplies(make_scene, qtbot):
    """SC-U035-1: undo after a committed move restores the pre-move buffer in ONE
    step; redo re-applies (apply then undo = identity)."""
    view, _scene, stack, buf = _make_move_view(make_scene, qtbot)
    before = buf.copy()

    press(view, 3, 3)
    move(view, 7, 5)
    release(view, 7, 5)
    after = buf.copy()
    assert stack.count() == 1
    assert after != before

    stack.undo()
    assert buf == before  # exact restore in one step
    stack.redo()
    assert buf == after  # redo re-applies


def test_sc_u035_2_preview_renders_nearest_neighbour_aa_off(make_scene, qtbot):
    """SC-U035-2: the floating preview renders nearest-neighbour / AA-off at any
    zoom — the view keeps both hints disabled and the float item is present."""
    view, scene, _stack, _buf = _make_move_view(make_scene, qtbot)

    press(view, 3, 3)  # lift at identity zoom (pinned coordinate mapping)
    move(view, 6, 6)
    view.set_zoom(8.0)  # a high zoom must not enable smoothing on the live float

    hints = view.renderHints()
    assert not (hints & QPainter.RenderHint.Antialiasing)
    assert not (hints & QPainter.RenderHint.SmoothPixmapTransform)
    assert scene._float_item.isVisible()

    view.floating_controller().cancel()


def test_sc_u035_3_preview_legible_in_both_themes(make_scene, qtbot, theme):
    """SC-U035-3: the floating preview is legible in both themes — its checker
    colours come from the active theme's canvas roles (role-based, not
    hard-coded). Superseded mechanism: ``_FloatingPreviewItem`` used to hold
    its own private ``_checker_light``/``_checker_dark`` QColor pair; it now
    receives the scene's shared ``_CheckerBrush`` + canvas rect
    (``set_roles(checker, canvas_rect)``) instead of two colours
    (canvas-grid-semantics job, REQ-CGS-UI-003/-004). This asserts the SAME
    intent through the new surface: the float's checker is the identical
    brush instance the scene itself paints with (agreement by construction,
    not coincidence — at least as strong as the predecessor's equality
    check), that brush's texture is built from the active theme's roles, and
    the float's checker stays bounded to the same document canvas rect
    (REQ-CGS-UI-004, both float + origin layers)."""
    view, scene, _stack, _buf = _make_move_view(make_scene, qtbot)
    light, dark, _grid = canvas_roles(theme)

    press(view, 3, 3)
    move(view, 6, 6)

    assert scene._float_item.isVisible()
    # The overlay's checker roles track the theme (both float + origin layers):
    # both share the SAME _CheckerBrush instance the scene paints with.
    assert scene._float_item._checker is scene._checker_brush
    assert scene._origin_item._checker is scene._checker_brush
    # That shared brush's texture is built from the active theme's own roles.
    texture_image = scene._checker_brush.texture.texture().toImage()
    assert texture_image.pixelColor(0, 0) == QColor(light)
    assert texture_image.pixelColor(CHECKER_CELL_PX, 0) == QColor(dark)
    # And it stays bounded to the same document canvas rect as the scene.
    canvas_rect = QRectF(0, 0, scene._document.width, scene._document.height)
    assert scene._float_item._canvas_rect == canvas_rect
    assert scene._origin_item._canvas_rect == canvas_rect

    view.floating_controller().cancel()


# =========================================================================
# FB-T7 / REQ-P2-UI-036 — active-layer scope, off-canvas, a11y
# =========================================================================


def test_sc_u036_1_float_modifies_only_the_active_layer(qtbot, theme):
    """SC-U036-1: the floating move affects ONLY the active layer — other layers
    stay untouched."""
    doc = Document(16, 16, palette=Palette(STARTER))
    scene = CanvasScene(doc)
    scene.set_background_roles(*canvas_roles(theme))
    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    prepare_for_click(view)
    view.set_tool(RectSelectTool())

    # The scene's active layer is the move target; a second layer must stay
    # untouched. Capture the active layer, then add the other layer.
    active = scene.active_buffer()
    active.set_pixel(2, 2, RED)
    other = doc.add_layer("other")
    other.buffer.set_pixel(2, 2, YELLOW)  # a pixel on the non-active layer
    other_before = other.buffer.copy()
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))

    press(view, 3, 3)
    move(view, 7, 5)
    release(view, 7, 5)

    assert other.buffer == other_before  # other layer untouched
    assert active.get_pixel(6, 4) == RED  # active layer received the move
    assert active.get_pixel(2, 2) == TRANSPARENT


def test_sc_u036_2_off_canvas_pixels_discarded_on_commit(make_scene, qtbot):
    """SC-U036-2: dragging partly off-canvas discards the out-of-bounds destination
    pixels on commit (clipped, never wrapped); the whole origin still vacates."""
    view, _scene, stack, buf = _make_move_view(make_scene, qtbot)

    # offset (13, 0): dest xs 15/16/17 -> only x=15 stays in a 16-wide buffer.
    press(view, 3, 3)
    move(view, 16, 3)
    release(view, 16, 3)

    assert stack.count() == 1
    assert buf.get_pixel(15, 2) == RED  # RED at (2,2) clipped-in at (15,2)
    assert buf.get_pixel(2, 2) == TRANSPARENT  # whole origin vacated
    assert buf.get_pixel(3, 3) == TRANSPARENT
    assert buf.get_pixel(4, 4) == TRANSPARENT
    # GREEN (dest 16,3) and BLUE (dest 17,4) fell off-canvas and were dropped,
    # never wrapped — only the single clipped-in RED survives.
    assert _non_transparent(buf) == 1


def test_sc_u036_3_a11y_hint_translatable_keyboard_reachable_focus_visible(
    qtbot, theme
):
    """SC-U036-3: the floating-selection status hint is tr()-wrapped with an
    accessible name; commit/cancel are keyboard-reachable; focus is visible."""
    win = _window(qtbot)
    view, _scene, stack, _buf = _prep_window_move(win)

    # Accessible name present on the status hint (announced by assistive tech).
    assert win._float_hint.accessibleName() == "Floating selection status"

    # Keyboard reachability: the canvas takes strong focus and Enter commits.
    assert view.focusPolicy() == Qt.FocusPolicy.StrongFocus
    press(view, 3, 3)
    move(view, 7, 5)
    assert win._float_hint.text() != ""  # tr()-wrapped hint text shown
    key(view, Qt.Key.Key_Return)
    assert stack.count() == 1  # committed from the keyboard alone

    # Escape is likewise keyboard-reachable (cancel a fresh float).
    buf = _scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    press(view, 3, 3)
    move(view, 8, 8)
    key(view, Qt.Key.Key_Escape)
    assert not view.floating_controller().is_active()

    # A visible focus indicator is themed once by role (a :focus QSS rule).
    assert ":focus" in QApplication.instance().styleSheet()


# =========================================================================
# FloatingMoveController direct API contract (no Canvas_View)
# =========================================================================
#
# ``begin``/``update``/``commit``/``cancel`` are exercised above exclusively
# through a real ``Canvas_View`` (mouse/key events on ``SelectionTool``'s
# in-mask press). Two of the controller's own documented guarantees are
# never reached that way and are proven directly here instead:
#
# - "Returns False when there is no active, non-empty selection under the
#   cursor" (:meth:`begin`'s docstring) -- unreachable through
#   ``SelectionTool.on_press`` because that caller's own ``inside`` gate
#   (``ui/tools/selection_base.py``) already filters out exactly this case
#   before ``controller.begin`` is ever called; it is a real, separately
#   documented contract of the controller class itself, so it is exercised
#   by calling ``begin`` directly.
# - "Idempotent when no float is active" (:meth:`commit`'s docstring, and
#   the equivalent guarantee on :meth:`update`/:meth:`cancel`) -- unreachable
#   through the UI because every UI path that can call ``update``/``commit``/
#   ``cancel`` first requires a live float (``self._moving`` on
#   ``SelectionTool``, or a key/tool-switch handler that checks
#   ``controller.is_active()`` first).
#
# A bare ``FloatingMoveController()`` is never wired to a view, so its
# ``state_changed`` observer stays ``None`` throughout (matching
# ``ui/tools/base.py``'s own ``ToolContext.floating_controller`` docstring:
# "``None`` outside a canvas view") -- every call below therefore also
# exercises ``_notify``'s skip-when-unobserved branch as a side effect.


def _lift_ctx(scene, buf, selection, *, set_selection=None, undo_stack=None):
    """A minimal object structurally satisfying ``floating_move.LiftContext``."""
    from types import SimpleNamespace

    return SimpleNamespace(
        selection=selection,
        buffer=buf,
        scene=scene,
        undo_stack=undo_stack if undo_stack is not None else QUndoStack(),
        set_selection=set_selection,
        target=None,
    )


def test_begin_returns_false_and_does_not_lift_when_no_active_selection(make_scene):
    """``begin`` returns False -- no float started -- when the selection is
    None, empty, or the point is outside it (REQ-P2-UI-030's documented
    fall-through to the build tools), proven directly against the
    controller's own guard."""
    from pixelart_creator.logic.selection import SelectionMask
    from pixelart_creator.ui.tools.floating_move import FloatingMoveController

    scene = make_scene(16, 16)
    buf = scene.active_buffer()
    controller = FloatingMoveController()

    assert controller.begin(3, 3, _lift_ctx(scene, buf, None), label="x") is False
    assert not controller.is_active()

    empty = SelectionMask(16, 16)
    assert empty.is_empty
    assert controller.begin(3, 3, _lift_ctx(scene, buf, empty), label="x") is False
    assert not controller.is_active()

    mask = rect_mask(16, 16, 2, 2, 4, 4)
    assert controller.begin(10, 10, _lift_ctx(scene, buf, mask), label="x") is False
    assert not controller.is_active()


def test_update_commit_cancel_are_idempotent_with_no_active_float(make_scene):
    """``update``/``commit``/``cancel`` are documented no-ops when no float is
    active -- proven directly against a bare, unwired controller."""
    from pixelart_creator.ui.tools.floating_move import FloatingMoveController

    controller = FloatingMoveController()

    controller.update(3, 3, copy=False)  # no exception, no state change
    assert not controller.is_active()

    controller.commit()  # no exception
    assert not controller.is_active()

    controller.cancel()  # no exception
    assert not controller.is_active()


def test_commit_without_a_set_selection_callback_drops_the_mask_silently(make_scene):
    """A caller that provides no ``set_selection`` callback (a bare/non-view
    context, e.g. a read-only preview -- ``LiftContext.set_selection`` is
    documented ``Optional``) still commits the move as one command; it simply
    cannot follow the mask to the destination."""
    from pixelart_creator.ui.tools.floating_move import FloatingMoveController

    scene = make_scene(16, 16)
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    mask = rect_mask(16, 16, 2, 2, 2, 2)
    controller = FloatingMoveController()
    stack = QUndoStack()

    started = controller.begin(
        2,
        2,
        _lift_ctx(scene, buf, mask, set_selection=None, undo_stack=stack),
        label="x",
    )
    assert started
    controller.update(3, 3, copy=False)
    controller.commit()

    assert stack.count() == 1
    assert buf.get_pixel(5, 5) == RED  # (2,2) + offset (3,3)


# =========================================================================
# Overwrite confirmation before a floating commit (REQ-P2-UI-037,
# REQ-P2-LOGIC-037, REQ-P2-DATA-030 -- Q-19 ruling, ``27f0106``).
# =========================================================================
#
# Two layers, mirroring ``test_cel_overwrite_dialog.py``'s own two-part
# shape:
#
# 1. ``Overwrite_Confirm_Dialog`` itself, standalone and unpatched.
# 2. The full commit-gate flow through ``FloatingMoveController``, with
#    ``Overwrite_Confirm_Dialog.exec`` monkeypatched to answer immediately
#    (the same headless-modal pattern ``test_cel_overwrite_dialog.py`` uses).


def test_overwrite_dialog_default_state_and_accessible_names(qtbot):
    """The dialog opens with "Don't ask again" unticked and every interactive
    part carrying a non-empty accessible name."""
    dialog = Overwrite_Confirm_Dialog()
    qtbot.addWidget(dialog)

    assert dialog.dont_ask_again() is False
    assert dialog.accessibleName() != ""
    assert dialog._message.accessibleName() != ""
    assert dialog._dont_ask.accessibleName() != ""
    assert dialog._dont_ask.text() != ""
    assert dialog.windowTitle() != ""


def test_overwrite_dialog_is_keyboard_reachable_and_modal(qtbot):
    """The dialog is modal (blocking, cancellable) and its controls are real
    focusable widgets, not painted-only."""
    dialog = Overwrite_Confirm_Dialog()
    qtbot.addWidget(dialog)

    assert dialog.isModal()
    assert dialog._dont_ask.focusPolicy() != Qt.FocusPolicy.NoFocus
    yes = dialog._buttons.button(dialog._buttons.StandardButton.Yes)
    cancel = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)
    assert yes is not None and cancel is not None
    assert yes.text() != "" and cancel.text() != ""


def test_overwrite_dialog_cancel_returns_rejected(qtbot):
    """Clicking Cancel rejects the dialog."""
    dialog = Overwrite_Confirm_Dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    cancel = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)

    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        qtbot.mouseClick(cancel, LEFT)

    assert dialog.result() == dialog.DialogCode.Rejected


def test_overwrite_dialog_yes_returns_accepted(qtbot):
    """Clicking the overwrite (Yes) button accepts the dialog."""
    dialog = Overwrite_Confirm_Dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    yes = dialog._buttons.button(dialog._buttons.StandardButton.Yes)

    with qtbot.waitSignal(dialog.accepted, timeout=1000):
        qtbot.mouseClick(yes, LEFT)

    assert dialog.result() == dialog.DialogCode.Accepted


def test_overwrite_dialog_retranslates_on_language_change(qtbot):
    """A LanguageChange event re-sets every user-visible string without
    raising, and the accessible names stay non-empty."""
    dialog = Overwrite_Confirm_Dialog()
    qtbot.addWidget(dialog)

    dialog.changeEvent(QEvent(QEvent.Type.LanguageChange))

    assert dialog.windowTitle() != ""
    assert dialog.accessibleName() != ""
    assert dialog._dont_ask.text() != ""


def test_overwrite_dialog_retranslate_tolerates_missing_standard_buttons(
    qtbot, monkeypatch
):
    """The defensive ``is not None`` guards around the Yes/Cancel buttons in
    ``_retranslate`` must not assume ``QDialogButtonBox.button()`` always
    resolves both standard buttons -- proven by forcing ``button()`` to
    report neither found, which must degrade gracefully rather than raise."""
    dialog = Overwrite_Confirm_Dialog()
    qtbot.addWidget(dialog)
    monkeypatch.setattr(dialog._buttons, "button", lambda *a, **k: None)

    dialog._retranslate()  # must not raise

    assert dialog.windowTitle() != ""
    assert dialog._dont_ask.text() != ""


@pytest.fixture
def answer_overwrite_dialog(monkeypatch):
    """Patch ``Overwrite_Confirm_Dialog.exec`` to answer immediately (headless
    modal automation -- the dialog's own behaviour is proven, unpatched,
    above). Returns a controller: ``answer_overwrite_dialog(accept=True,
    dont_ask=False)``; records every simulated presentation."""
    calls: list = []
    state = {"accept": True, "dont_ask": False}

    def _fake_exec(self):
        calls.append(True)
        self._dont_ask.setChecked(state["dont_ask"])
        if state["accept"]:
            self.accept()
            return self.DialogCode.Accepted
        self.reject()
        return self.DialogCode.Rejected

    monkeypatch.setattr(Overwrite_Confirm_Dialog, "exec", _fake_exec)

    def _configure(*, accept: bool, dont_ask: bool = False) -> list:
        state["accept"] = accept
        state["dont_ask"] = dont_ask
        return calls

    return _configure


def _make_move_view_occupied_destination(make_scene, qtbot, offset=(5, 5)):
    """Like :func:`_make_move_view`, but the drag destination already carries
    a non-origin pixel, so ``destination_is_empty`` is False and the
    confirmation gate fires."""
    view, scene, stack, buf = _make_move_view(make_scene, qtbot)
    ox, oy = offset
    dx, dy = 2 + ox, 2 + oy  # outside the (2,2)-(4,4) origin mask
    buf.set_pixel(dx, dy, YELLOW)
    return view, scene, stack, buf


def test_sc_ui_037_1_occupied_destination_confirmed_before_anything_applied(
    make_scene, qtbot, answer_overwrite_dialog
):
    """REQ-P2-UI-037: committing a MOVE onto an occupied destination presents
    the confirmation before anything is applied."""
    view, scene, stack, buf = _make_move_view_occupied_destination(make_scene, qtbot)
    presented = answer_overwrite_dialog(accept=False)
    before_count = stack.count()
    before_buf = buf.copy()

    press(view, 3, 3)
    move(view, 8, 8)  # offset (5, 5) -> destination overlaps the marked pixel
    release(view, 8, 8)

    assert presented == [True]
    assert stack.count() == before_count
    assert buf == before_buf  # nothing applied while confirming/cancel

    view.floating_controller().cancel()  # do not leak an active float


def test_sc_ui_037_2_cancel_leaves_float_active_not_esc_semantics(
    make_scene, qtbot, answer_overwrite_dialog
):
    """Cancelling the confirmation is NOT the same as ESC (REQ-P2-UI-034): the
    float stays lifted at its current offset, still movable, no command
    pushed -- a further ESC still abandons it cleanly."""
    view, scene, stack, buf = _make_move_view_occupied_destination(make_scene, qtbot)
    controller = view.floating_controller()
    answer_overwrite_dialog(accept=False)

    press(view, 3, 3)
    move(view, 8, 8)
    release(view, 8, 8)  # declined

    assert controller.is_active()  # still floating -- NOT abandoned
    assert stack.count() == 0

    key(view, Qt.Key.Key_Escape)  # a further ESC still cancels it cleanly
    assert not controller.is_active()
    assert stack.count() == 0


def test_sc_ui_037_3_confirming_commits_one_command_undo_restores(
    make_scene, qtbot, answer_overwrite_dialog
):
    """Confirming proceeds through the SAME single commit path -- exactly one
    reversible command, undo restores the destination's prior content."""
    view, scene, stack, buf = _make_move_view_occupied_destination(make_scene, qtbot)
    answer_overwrite_dialog(accept=True)
    before = buf.copy()

    press(view, 3, 3)
    move(view, 8, 8)
    release(view, 8, 8)

    assert stack.count() == 1
    assert buf.get_pixel(7, 7) == RED  # RED at (2,2) moved to (7,7)
    stack.undo()
    assert buf == before


def test_sc_ui_037_4_empty_destination_is_not_confirmed_at_all(
    make_scene, qtbot, answer_overwrite_dialog
):
    """An empty destination applies directly -- REQ-P2-LOGIC-037's fast path
    -- no confirmation presented at all."""
    view, scene, stack, buf = _make_move_view(make_scene, qtbot)  # no occupied dest
    presented = answer_overwrite_dialog(accept=True)

    press(view, 3, 3)
    move(view, 8, 8)
    release(view, 8, 8)

    assert presented == []  # never shown
    assert stack.count() == 1


def test_sc_ui_037_5_dont_ask_again_suppresses_for_the_rest_of_the_project(
    make_scene, qtbot, answer_overwrite_dialog
):
    """Ticking "Don't ask again" and confirming suppresses future prompts for
    this project; a second occupied commit in the SAME project no longer
    presents the dialog, and remains exactly one command."""
    view, scene, stack, buf = _make_move_view_occupied_destination(make_scene, qtbot)
    presented = answer_overwrite_dialog(accept=True, dont_ask=True)

    press(view, 3, 3)
    move(view, 8, 8)
    release(view, 8, 8)
    assert presented == [True]
    assert scene._document.prefs.get(CONFIRM_FLOATING_OVERWRITE) == "suppressed"

    # A second, independent occupied-destination move in the same project.
    buf.set_pixel(1, 1, RED)
    buf.set_pixel(10, 10, YELLOW)  # a fresh occupied destination
    view.set_selection(rect_mask(buf.width, buf.height, 0, 0, 1, 1))
    before_count = stack.count()

    press(view, 0, 0)
    move(view, 9, 9)  # offset (9, 9): (1,1) -> (10,10), occupied
    release(view, 9, 9)

    assert presented == [True]  # unchanged -- not presented a second time
    assert stack.count() == before_count + 1


def test_sc_ui_037_6_ticking_then_cancelling_records_nothing(
    make_scene, qtbot, answer_overwrite_dialog
):
    """Ticking "Don't ask again" and then cancelling persists nothing (Q-19);
    the next occupied commit still presents the confirmation."""
    view, scene, stack, buf = _make_move_view_occupied_destination(make_scene, qtbot)
    presented = answer_overwrite_dialog(accept=False, dont_ask=True)

    press(view, 3, 3)
    move(view, 8, 8)
    release(view, 8, 8)

    assert presented == [True]
    assert scene._document.prefs.get(CONFIRM_FLOATING_OVERWRITE) == "ask"

    view.floating_controller().cancel()  # do not leak an active float


def test_sc_ui_037_7_suppression_belongs_to_one_project(
    make_scene, qtbot, answer_overwrite_dialog
):
    """Suppressing the confirmation in one scene's document does not affect a
    second, independent scene's document."""
    view1, scene1, _stack1, _buf1 = _make_move_view_occupied_destination(
        make_scene, qtbot
    )
    _view2, scene2, _stack2, _buf2 = _make_move_view_occupied_destination(
        make_scene, qtbot
    )
    answer_overwrite_dialog(accept=True, dont_ask=True)

    press(view1, 3, 3)
    move(view1, 8, 8)
    release(view1, 8, 8)

    assert scene1._document.prefs.get(CONFIRM_FLOATING_OVERWRITE) == "suppressed"
    assert scene2._document.prefs.get(CONFIRM_FLOATING_OVERWRITE) == "ask"


# =========================================================================
# Canvas_View's key handling around a live float (REQ-P2-UI-033/-034) --
# the "neither Enter/Return nor Escape" / "release key isn't Space" arms no
# scripted drag+Enter/Escape sequence above ever takes.
# =========================================================================


def test_key_press_other_than_enter_escape_does_not_affect_an_active_float(
    make_scene, qtbot
):
    """A key press that is neither Enter/Return nor Escape while a float is
    active is inert to the float -- neither committed nor cancelled -- and
    falls through to the base ``QGraphicsView.keyPressEvent`` handler."""
    view, _scene, stack, _buf = _make_move_view(make_scene, qtbot)
    controller = view.floating_controller()

    press(view, 3, 3)
    move(view, 6, 5)
    assert controller.is_active()

    key(view, Qt.Key.Key_A)  # neither Enter/Return nor Escape

    assert controller.is_active()  # untouched -- no commit, no cancel
    assert stack.count() == 0

    controller.cancel()  # do not leak an active float


def test_key_release_other_than_space_falls_through(make_scene, qtbot):
    """A key release that is not Space leaves the pan modifier untouched and
    still reaches the base ``QGraphicsView.keyReleaseEvent`` handler."""
    view, _scene, _stack, _buf = _make_move_view(make_scene, qtbot)

    view.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_A, NO_MOD))
    # No exception raised; the Space-only pan-modifier branch was skipped.
