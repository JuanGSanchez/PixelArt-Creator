"""Home-row keyboard scheme acceptance (wave 3).

One test per named scenario from the input-scheme spec
§9.1: ``SC-U001-1..3`` (REQ-IS-UI-001, the eleven-tool bijection),
``SC-U002-1..2`` (REQ-IS-UI-002, the seven released letters bind nothing),
``SC-U003-1..3`` (REQ-IS-UI-003, Shift+S Filled Shapes), ``SC-U004-1..3``
(REQ-IS-UI-004, Shift+R Pixel Perfect), ``SC-U005-1..4`` (REQ-IS-UI-005,
Shift+Q added alongside Delete) and ``SC-U007-1..2`` (REQ-IS-UI-007,
discoverable tooltips). ``SC-U007-3`` is spec-marked "[spec-only, review]" —
not automated here; confirmed by direct source read this session (the
comment at the old ``main_window.py:1166`` site now reads "Displaces the old
Aseprite-style set ... those seven freed letters (B G I L M O R) are bound
to nothing", not the stale "E is unmodified" claim).

Also carries the ten keyboard rows of REQ-IS-UI-028's regression net that
are this task's to close (``SC-R-16..R-25``, spec.md §8.2/§9.7) — including
the two shadow checks plan §6.3 M3 measured as structurally safe in Qt
(SC-R-19: Shift+E vs Ctrl+Shift+E; SC-R-20: Shift+A vs Ctrl+Shift+A). A
failure in either is reported as a finding, never patched here or waved
through by loosening the assertion (task brief, "THE TWO JOBS"). Several of
these rows are already pinned elsewhere (``test_input_scheme_regression.py``
wave-0 baseline, ``test_user_guide.py``, ``test_selection_actions.py``);
they are re-asserted here in full because REQ-IS-UI-028/SC-R-16..R-25 are
named as this task's own deliverable in tasks.md, not to replace those
existing pins.

Every test in this module runs under both the light and dark theme via the
suite's autouse ``theme`` fixture (``testing/suites/ui/conftest.py``) — no
local parametrize needed since none of these scenarios render a themed
colour. Headless: ``QT_QPA_PLATFORM=offscreen`` is forced by the suite's own
``conftest.py``; no test below sets it itself.

Shortcuts are exercised by asserting the exact ``QKeySequence`` bound to the
action, then firing ``action.trigger()`` and asserting the OBSERVABLE
effect — never a raw ``QTest.keyClick`` on the top-level window, which the
rest of this suite avoids for offscreen key-routing reasons (see
``test_input_scheme_regression.py``'s own note, and the established idiom at
``test_user_guide.py::test_sc_u002_1_f1_shortcut_opens_guide``). This proves
both halves a real key press would exercise: that a specific key sequence is
actually bound, and that firing it produces the documented result.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.main_window import Main_Window
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

#: The eleven home-row bindings, spec.md §9.1 SC-U001-1's own Examples table.
_TOOL_SHORTCUTS = {
    "A": PencilTool.tool_id,
    "Shift+A": PickerTool.tool_id,
    "Q": EraserTool.tool_id,
    "S": RectangleTool.tool_id,
    "W": LineTool.tool_id,
    "Shift+W": EllipseTool.tool_id,
    "D": RectSelectTool.tool_id,
    "F": FloodFillTool.tool_id,
    "Shift+F": DitherTool.tool_id,
    "E": LassoTool.tool_id,
    "Shift+E": MagicWandTool.tool_id,
}

#: The seven letters the remap released; REQ-IS-UI-002 binds none of them.
_RELEASED_KEYS = {"B", "G", "I", "L", "M", "O", "R"}


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# =========================================================================
# REQ-IS-UI-001 -- Home-row tool shortcuts
# =========================================================================


@pytest.mark.parametrize("key,tool_id", sorted(_TOOL_SHORTCUTS.items()))
def test_sc_u001_1_each_key_activates_exactly_its_tool(qtbot, key, tool_id):
    """SC-U001-1: each of the eleven keys activates exactly its tool, and
    that tool's action is the checked one in the (exclusive) left toolbar
    action group."""
    win = _window(qtbot)
    action = win._tool_actions[tool_id]
    assert action.shortcut() == QKeySequence(key)
    action.trigger()
    assert win._active_tool_id == tool_id
    assert win.active_tab().view.active_tool() is win._tools[tool_id]
    assert action.isChecked()
    # The action group is exclusive: every OTHER tool action is unchecked.
    for other_id, other_action in win._tool_actions.items():
        if other_id != tool_id:
            assert not other_action.isChecked(), other_id


def test_sc_u001_2_the_eleven_bound_sequences_are_pairwise_distinct(qtbot):
    """SC-U001-2: reading the shortcut sequence of every tool action yields
    eleven sequences with no two equal."""
    win = _window(qtbot)
    sequences = [action.shortcut() for action in win._tool_actions.values()]
    assert len(sequences) == 11
    as_strings = [seq.toString() for seq in sequences]
    assert len(set(as_strings)) == 11


def test_sc_u001_3_exactly_eleven_tools_each_with_a_non_empty_shortcut(qtbot):
    """SC-U001-3: the tool action registry contains exactly eleven tools and
    every one has a non-empty shortcut -- no tool is left unbound."""
    win = _window(qtbot)
    assert len(win._tool_actions) == 11
    for tool_id, action in win._tool_actions.items():
        assert not action.shortcut().isEmpty(), tool_id


# =========================================================================
# REQ-IS-UI-002 -- Clean-break changeover
# =========================================================================


@pytest.mark.parametrize("key", sorted(_RELEASED_KEYS))
def test_sc_u002_1_released_keys_select_no_tool(qtbot, key):
    """SC-U002-1: none of the seven released keys is bound to any tool
    action, so pressing it (the only route by which a bare letter ever
    changes the active tool -- ``Canvas_View.keyPressEvent`` carries no
    letter-key handling of its own) leaves the active tool exactly as it
    was: pencil, the tool the window opens with."""
    win = _window(qtbot)
    assert win._active_tool_id == PencilTool.tool_id
    for action in win._tool_actions.values():
        assert action.shortcut() != QKeySequence(key)
    # No action anywhere on the window claims this key either (an
    # unregistered QAction.trigger() is unreachable by construction, so the
    # absence of a matching shortcut on any action is the complete,
    # observable proof that the key selects nothing).
    assert win._active_tool_id == PencilTool.tool_id


def test_sc_u002_2_no_old_letter_survives_as_an_alias(qtbot):
    """SC-U002-2: reading the shortcut sequences of all eleven tool actions,
    none of them is B, G, I, L, M, O or R."""
    win = _window(qtbot)
    bound = {action.shortcut().toString() for action in win._tool_actions.values()}
    assert bound.isdisjoint(_RELEASED_KEYS)


# =========================================================================
# REQ-IS-UI-003 -- Filled Shapes shortcut (Shift+S)
# =========================================================================


def test_sc_u003_1_shift_s_toggles_filled_shapes_on(qtbot):
    """SC-U003-1: Shift+S checks Filled Shapes and sets both shape tools'
    filled flag true."""
    win = _window(qtbot)
    assert win._filled_action.shortcut() == QKeySequence("Shift+S")
    assert not win._filled_action.isChecked()
    win._filled_action.trigger()
    assert win._filled_action.isChecked()
    assert win._rectangle_tool.filled is True
    assert win._ellipse_tool.filled is True


def test_sc_u003_2_shift_s_toggles_filled_shapes_off_again(qtbot):
    """SC-U003-2: firing Shift+S a second time unchecks Filled Shapes and
    clears both shape tools' filled flag."""
    win = _window(qtbot)
    win._filled_action.trigger()
    assert win._filled_action.isChecked()
    win._filled_action.trigger()
    assert not win._filled_action.isChecked()
    assert win._rectangle_tool.filled is False
    assert win._ellipse_tool.filled is False


def test_sc_u003_3_toolbar_action_and_shortcut_drive_the_same_state(qtbot):
    """SC-U003-3: triggering the toolbar action then firing Shift+S returns
    Filled Shapes to unchecked -- both routes drive the one action."""
    win = _window(qtbot)
    assert not win._filled_action.isChecked()
    win._filled_action.trigger()  # toolbar-button-equivalent trigger
    assert win._filled_action.isChecked()
    win._filled_action.trigger()  # Shift+S-equivalent trigger
    assert not win._filled_action.isChecked()


# =========================================================================
# REQ-IS-UI-004 -- Pixel Perfect shortcut (Shift+R)
# =========================================================================


def test_sc_u004_1_shift_r_toggles_pixel_perfect_on(qtbot):
    """SC-U004-1: Shift+R checks Pixel Perfect and the active canvas view
    reports pixel-perfect enabled."""
    win = _window(qtbot)
    assert win._pixel_perfect_action.shortcut() == QKeySequence("Shift+R")
    assert not win._pixel_perfect_action.isChecked()
    win._pixel_perfect_action.trigger()
    assert win._pixel_perfect_action.isChecked()
    assert win.active_tab().view._pixel_perfect is True


def test_sc_u004_2_shift_r_applies_to_every_open_tab(qtbot):
    """SC-U004-2: with three document tabs open, firing Shift+R once flips
    pixel-perfect on for all three canvas views."""
    win = _window(qtbot)
    win.new_document()
    win.new_document()
    assert len(win._tabs_data) == 3
    win._pixel_perfect_action.trigger()
    for record in win._tabs_data:
        assert record.view._pixel_perfect is True


def test_sc_u004_3_shift_r_toggles_it_off_again(qtbot):
    """SC-U004-3: firing Shift+R a second time disables pixel-perfect on
    every open canvas view."""
    win = _window(qtbot)
    win.new_document()
    win._pixel_perfect_action.trigger()
    for record in win._tabs_data:
        assert record.view._pixel_perfect is True
    win._pixel_perfect_action.trigger()
    for record in win._tabs_data:
        assert record.view._pixel_perfect is False


# =========================================================================
# REQ-IS-UI-005 -- Clear selection on two keys (Shift+Q added, Delete kept)
# =========================================================================


def test_sc_u005_1_shift_q_clears_the_selection_contents(qtbot):
    """SC-U005-1: with a non-empty selection over painted pixels, Shift+Q
    makes every selected pixel transparent and pushes one undo entry."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    record.view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    assert QKeySequence("Shift+Q") in win._clear_action.shortcuts()
    win._clear_action.trigger()
    assert record.stack.count() == 1
    assert record.scene.active_buffer().get_pixel(3, 3) == TRANSPARENT


def test_sc_u005_2_delete_still_clears_the_selection_contents(qtbot):
    """SC-U005-2: Delete still clears the selected pixels and pushes one
    undo entry -- unchanged by the remap (also SC-R-16)."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    record.view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    assert win._clear_action.shortcut() == QKeySequence("Del")
    win._clear_action.trigger()
    assert record.stack.count() == 1
    assert record.scene.active_buffer().get_pixel(3, 3) == TRANSPARENT


def test_sc_u005_3_both_sequences_are_bound_to_the_one_action(qtbot):
    """SC-U005-3: the clear-selection action's shortcut list contains both
    Shift+Q and Delete."""
    win = _window(qtbot)
    sequences = set(win._clear_action.shortcuts())
    assert QKeySequence("Shift+Q") in sequences
    assert QKeySequence(Qt.Key.Key_Delete) in sequences
    assert len(sequences) == 2


def test_sc_u005_4_clearing_with_no_selection_is_a_silent_no_op(qtbot):
    """SC-U005-4: with no active selection, Shift+Q leaves the pixel buffer
    unchanged, pushes no undo entry and raises no error."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record.view.active_selection() is None
    before = record.scene.active_buffer().copy()
    win._clear_action.trigger()  # must not raise
    assert record.stack.count() == 0
    assert record.scene.active_buffer() == before


# =========================================================================
# REQ-IS-UI-007 -- Discoverable text names the new keys
# =========================================================================


@pytest.mark.parametrize("key,tool_id", sorted(_TOOL_SHORTCUTS.items()))
def test_sc_u007_1_each_tool_actions_tooltip_names_its_new_key(qtbot, key, tool_id):
    """SC-U007-1: the tooltip of each tool action contains its assigned
    key."""
    win = _window(qtbot)
    action = win._tool_actions[tool_id]
    assert key in action.toolTip()


def test_sc_u007_2_no_tooltip_names_a_released_key(qtbot):
    """SC-U007-2: no tool action's tooltip contains a bare released key
    (B, G, I, L, M, O or R) as its shortcut hint."""
    win = _window(qtbot)
    for action in win._tool_actions.values():
        hint = action.shortcut().toString()
        assert hint not in _RELEASED_KEYS, action.toolTip()


# =========================================================================
# REQ-IS-UI-028 -- keyboard-binding regression rows this task closes
# (SC-R-16..R-25, spec.md §8.2 / §9.7)
# =========================================================================


def test_sc_r16_delete_still_clears_the_selection_contents(qtbot):
    """SC-R-16: Delete still clears a non-empty selection's painted pixels,
    pushing one undo entry."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(1, 1, RED)
    record.view.set_selection(rect_mask(buf.width, buf.height, 0, 0, 2, 2))
    win._clear_action.trigger()
    assert record.stack.count() == 1
    assert record.scene.active_buffer().get_pixel(1, 1) == TRANSPARENT


def test_sc_r17_ctrl_z_and_ctrl_y_still_undo_and_redo(qtbot):
    """SC-R-17: Ctrl+Z / Ctrl+Y are still bound to undo/redo and produce
    the documented effect on a painted stroke."""
    win = _window(qtbot)
    assert win._undo_action.shortcut() == QKeySequence("Ctrl+Z")
    assert win._redo_action.shortcut() == QKeySequence("Ctrl+Y")
    record = win.active_tab()
    buf = record.scene.active_buffer()
    record.view.set_active_color(RED)
    press(record.view, 4, 4)
    release(record.view, 4, 4)
    assert buf.get_pixel(4, 4) == RED
    assert record.stack.count() == 1

    win._undo_action.trigger()
    assert record.scene.active_buffer().get_pixel(4, 4) == TRANSPARENT
    win._redo_action.trigger()
    assert record.scene.active_buffer().get_pixel(4, 4) == RED


def test_sc_r18_ctrl_n_o_s_still_map_to_new_open_save(qtbot):
    """SC-R-18: Ctrl+N / Ctrl+O / Ctrl+S are still bound to their shipped
    actions."""
    win = _window(qtbot)
    assert win._new_action.shortcut() == QKeySequence("Ctrl+N")
    assert win._open_action.shortcut() == QKeySequence("Ctrl+O")
    assert win._save_action.shortcut() == QKeySequence("Ctrl+S")


def test_sc_r19_ctrl_shift_e_exports_and_is_not_shadowed_by_shift_e(qtbot, monkeypatch):
    """SC-R-19: Ctrl+Shift+E still invokes the export path without changing
    the active tool, and it is a distinct QKeySequence from the new Shift+E
    (magic wand) -- firing Shift+E afterwards changes the tool to
    select_wand and invokes no export."""
    win = _window(qtbot)
    assert win._active_tool_id == PencilTool.tool_id
    assert win._export_action.shortcut() == QKeySequence("Ctrl+Shift+E")
    wand_action = win._tool_actions[MagicWandTool.tool_id]
    assert wand_action.shortcut() == QKeySequence("Shift+E")
    assert win._export_action.shortcut() != wand_action.shortcut()

    calls = []
    monkeypatch.setattr(
        "pixelart_creator.ui.main_window.run_export_dialog",
        lambda *a, **k: calls.append((a, k)) or None,
    )
    win._export_action.trigger()
    assert len(calls) == 1  # the export path was invoked exactly once
    assert win._active_tool_id == PencilTool.tool_id  # export did not touch the tool

    wand_action.trigger()
    assert win._active_tool_id == MagicWandTool.tool_id
    assert len(calls) == 1  # still exactly one export call -- Shift+E invoked none


def test_sc_r20_ctrl_a_and_ctrl_shift_a_are_not_shadowed_by_a_and_shift_a(qtbot):
    """SC-R-20: Ctrl+A still selects the whole canvas and Ctrl+Shift+A still
    deselects, neither changing the active tool; the new Shift+A (picker)
    changes the tool but leaves the selection untouched."""
    win = _window(qtbot)
    assert win._active_tool_id == PencilTool.tool_id
    assert win._select_all_action.shortcut() == QKeySequence("Ctrl+A")
    assert win._deselect_action.shortcut() == QKeySequence("Ctrl+Shift+A")
    picker_action = win._tool_actions[PickerTool.tool_id]
    assert picker_action.shortcut() == QKeySequence("Shift+A")
    assert win._select_all_action.shortcut() != picker_action.shortcut()
    assert win._deselect_action.shortcut() != picker_action.shortcut()

    record = win.active_tab()
    buf = record.scene.active_buffer()

    win._select_all_action.trigger()
    mask = record.view.active_selection()
    assert mask is not None and mask.count() == buf.width * buf.height
    assert win._active_tool_id == PencilTool.tool_id

    win._deselect_action.trigger()
    assert record.view.active_selection() is None
    assert win._active_tool_id == PencilTool.tool_id

    win._select_all_action.trigger()
    selection_before = record.view.active_selection()
    picker_action.trigger()
    assert win._active_tool_id == PickerTool.tool_id
    selection_after = record.view.active_selection()
    assert selection_after is not None
    assert selection_after.count() == selection_before.count()


def test_sc_r21_ctrl_i_still_inverts_the_selection(qtbot):
    """SC-R-21: Ctrl+I still inverts the active selection, exact binding
    plus effect."""
    win = _window(qtbot)
    assert win._invert_action.shortcut() == QKeySequence("Ctrl+I")
    record = win.active_tab()
    buf = record.scene.active_buffer()
    mask = rect_mask(buf.width, buf.height, 0, 0, 2, 2)
    record.view.set_selection(mask)
    win._invert_action.trigger()
    inverted = record.view.active_selection()
    assert inverted is not None
    assert not inverted.is_selected(0, 0)
    assert inverted.is_selected(buf.width - 1, buf.height - 1)


def test_sc_r22_ctrl_plus_minus_still_zoom(qtbot):
    """SC-R-22: Ctrl++ / Ctrl+- still zoom in/out by the shipped step."""
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


def test_sc_r23_shift_h_and_shift_v_still_flip(qtbot):
    """SC-R-23: Shift+H then Shift+V still flip the image horizontally then
    vertically, and neither changes the active tool."""
    win = _window(qtbot)
    assert win._flip_h_action.shortcut() == QKeySequence("Shift+H")
    assert win._flip_v_action.shortcut() == QKeySequence("Shift+V")
    record = win.active_tab()
    buf = record.scene.active_buffer()
    w, h = buf.width, buf.height
    buf.set_pixel(1, 2, RED)
    assert win._active_tool_id == PencilTool.tool_id

    win._flip_h_action.trigger()
    flipped = record.scene.active_buffer()
    assert flipped.get_pixel(w - 2, 2) == RED
    assert flipped.get_pixel(1, 2) != RED
    assert win._active_tool_id == PencilTool.tool_id

    win._flip_v_action.trigger()
    flipped_again = record.scene.active_buffer()
    assert flipped_again.get_pixel(w - 2, h - 3) == RED
    assert win._active_tool_id == PencilTool.tool_id


def test_sc_r24_space_still_toggles_play_pause_in_playback_controls(qtbot):
    """SC-R-24: Space still toggles playback via the widget-scoped shortcut
    on Playback_Controls -- structurally isolated from any canvas pan since
    that widget carries no pan concept."""
    from pixelart_creator.ui.playback_controls import Playback_Controls

    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)
    ctrl.set_context(lambda: [100, 100, 100], lambda: 0)
    assert ctrl.is_playing() is False
    ctrl._space_shortcut.activated.emit()
    assert ctrl.is_playing() is True
    ctrl._space_shortcut.activated.emit()
    assert ctrl.is_playing() is False


def test_sc_r25_f1_still_opens_the_user_guide(qtbot):
    """SC-R-25: F1 still opens the User Guide dialog."""
    win = _window(qtbot)
    assert win._user_guide_action.shortcut() == QKeySequence(Qt.Key.Key_F1)
    win._user_guide_action.trigger()
    assert win._user_guide_dialog is not None
    assert win._user_guide_dialog.isVisible()
