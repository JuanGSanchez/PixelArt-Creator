"""Selection lifetime on tool entry (wave 5).

One test per named scenario in the input-scheme spec
§9.1 "Feature: Selection lifetime on tool change (REQ-IS-UI-029)":
``SC-U029-1..7``, plus the shape half of the regression scenario
``SC-R-32`` (REQ-IS-UI-028 / REQ-P2-LOGIC-006) that this same tool-change
handler (``Main_Window._on_tool_action``, ``main_window.py:3148-3172``)
must leave intact. (Line numbers re-verified 2026-08-31 against this
worktree's current ``main_window.py`` — they had drifted from an earlier
draft's citation due to unrelated concurrent edits elsewhere in that file
from other wave-5 tasks; the function's own content is unchanged.)

The shipped handler discards the active selection when the
**incoming** tool is one of ``{select_rect, select_lasso, select_wand}``
(``_SELECTION_ENTRY_TOOL_IDS``), strictly AFTER committing any live
floating move, and via the same no-undo-entry path the existing deselect
action uses (``record.view.clear_selection()``, pushes no ``QUndoCommand``).
Three normative properties are asserted SEPARATELY below, never folded into
one happy-path test, per REQ-IS-UI-029 and the task brief:

  1. ORDERING (``test_sc_u029_4_...``) — the float is committed before the
     clear; a wrong order could silently drop the user's in-progress move
     (e.g. a naive "discard the selection" that cancels a pending float
     instead of committing it) even though it does not, in the *shipped*
     handler, corrupt the pixel content either way — see that test's
     docstring for why the assertion still matters.
  2. NO UNDO ENTRY (``test_sc_u029_5_...``) — isolated from any floating
     move so a stack-count change can only come from the clear itself.
  3. MASK-CONSTRAINED DRAWING UNCHANGED (``test_sc_r32_...``) — see the
     PENCIL vs. RECTANGLE note below; this is the one that protects
     REQ-P2-LOGIC-006 from the blanket reading of "clear on tool change"
     that this job's own D-14 ruling deliberately narrowed.

PENCIL vs. RECTANGLE (a self-correction, recorded so it is auditable)
----------------------------------------------------------------------
The dispatch order for this task named the PENCIL for the mask-constrained
drawing check ("switch to the PENCIL, draw across the selection boundary,
assert the commit is CLIPPED"). Before writing that assertion it was PROBED
against the real, unmodified UI (a throwaway pytest module run inside this
same tree and deleted afterward — never committed): a ``Canvas_View`` with
``PencilTool`` active, an active selection mask over x∈[2,4], and a
horizontal drag from x=0 to x=8 through y=3. Result — **every pixel on the
stroke was painted, inside AND outside the mask**:

    PROBE inside(3,3): (230, 30, 30, 255)
    PROBE outside_left(0,3): (230, 30, 30, 255)
    PROBE outside_right(8,3): (230, 30, 30, 255)

``pixelart_creator/ui/tools/pencil.py`` imports neither
``logic.selection.apply_masked`` nor anything selection-related, and
``Canvas_View``'s mouse dispatch (``mousePressEvent``/``mouseMoveEvent`` in
``canvas_view.py``) never filters a coordinate by the active mask before
calling the tool. **The shipped PencilTool is not mask-constrained at all**
— that is pre-existing behaviour, wholly unrelated to this fix, and not a
defect this task's change touches.

The REQ this task's property protects — REQ-P2-LOGIC-006 — and its own
grounding in ``spec.md`` §5.2 cite ``tools/base.py:227`` (``ToolContext.
selection``) and **``tools/shape_base.py:8-10, :95``**, i.e. the shared
rectangle/ellipse ``ShapeTool`` controller, which DOES call
``logic.selection.apply_masked`` at commit
(``shape_base.py:101``). The existing regression pin for this exact
workflow — ``test_input_scheme_regression.py::
test_r32_selection_survives_a_real_tool_switch_to_a_non_selection_tool``
— and ``test_shape_mode.py::test_shape_commit_is_mask_constrained`` (cited
there, not duplicated) both exercise the RECTANGLE tool for the same
reason.

So ``test_sc_r32_...`` below uses the RECTANGLE tool, matching the REQ's
own grounding and the existing regression pin, and asserts through a REAL
``_on_tool_action`` dispatch (the exact function this fix changed) rather than
a hand-built substitute. Writing the check against PencilTool as literally
instructed would have produced a test that fails on unmodified, un-broken
code for a reason that has nothing to do with the fix — a false defect report
against the wrong tool. This substitution is reported to the dispatching
agent alongside this module.

Both themes are covered structurally: ``testing/suites/ui/conftest.py``'s
``theme`` fixture is ``autouse`` and parametrized over light/dark for the
whole UI suite, so every test below already runs twice without a local
parametrize — none of these scenarios render theme-dependent colour, so no
test asserts on it directly.

Headless: ``QT_QPA_PLATFORM=offscreen`` is forced by the suite's own
``conftest.py`` (``pytest_configure``); no test below sets it itself.

Shortcuts are exercised the same way the rest of this job's suites do
(``test_input_scheme_shortcuts.py``'s own note): the exact bound
``QKeySequence`` is asserted, then ``action.trigger()`` fires it and the
OBSERVABLE effect is asserted — never a raw ``QTest.keyClick`` on the
top-level window, which offscreen key-routing makes unreliable. ``trigger()``
is the same call both a real key press and a real toolbar click ultimately
make on the ``QAction`` (``test_r32_...``'s own note); ``test_sc_u029_7_...``
additionally drives the actual toolbar *widget* via ``qtbot.mouseClick`` for
full fidelity to its Gherkin's "from the left toolbar" clause.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import (
    LassoTool,
    MagicWandTool,
    PencilTool,
    RectangleTool,
    RectSelectTool,
)
from testing.suites.ui._ui_helpers import move, prepare_for_click, press, release

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)
TRANSPARENT = (0, 0, 0, 0)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _prep_move_selection(win):
    """Arm the active tab for a floating move: select_rect active, pinned view,
    a 3x3 selection (2,2)-(4,4) with a RED/GREEN/BLUE pattern inside it.
    Returns ``(record, view, scene, stack, buf)``."""
    record = win.active_tab()
    view, scene, stack = record.view, record.scene, record.stack
    prepare_for_click(view)
    win._tool_actions[RectSelectTool.tool_id].trigger()
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    buf.set_pixel(3, 3, GREEN)
    buf.set_pixel(4, 4, BLUE)
    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    return record, view, scene, stack, buf


# =========================================================================
# SC-U029-1 — entering a selection tool clears the selection
# =========================================================================


def test_sc_u029_1_entering_selection_tool_clears_the_selection(qtbot):
    """SC-U029-1: with a non-empty selection and pencil active, pressing D
    (select_rect's shortcut) both switches the tool AND discards the
    selection."""
    win = _window(qtbot)
    record = win.active_tab()
    view = record.view
    buf = record.scene.active_buffer()
    assert win._active_tool_id == PencilTool.tool_id  # the Gherkin's own Given

    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    assert view.active_selection() is not None

    action = win._tool_actions[RectSelectTool.tool_id]
    assert action.shortcut() == QKeySequence("D")  # proves D is really bound here
    action.trigger()  # "When I press D"

    assert win._active_tool_id == RectSelectTool.tool_id
    assert view.active_selection() is None


# =========================================================================
# SC-U029-2 — selection-tool-to-selection-tool switching also starts fresh
# =========================================================================


def test_sc_u029_2_selection_tool_to_selection_tool_also_clears(qtbot):
    """SC-U029-2: switching FROM one selection tool TO another also
    discards the selection — a selector always starts fresh."""
    win = _window(qtbot)
    record = win.active_tab()
    view = record.view
    buf = record.scene.active_buffer()

    win._tool_actions[RectSelectTool.tool_id].trigger()
    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    assert view.active_selection() is not None

    lasso_action = win._tool_actions[LassoTool.tool_id]
    assert lasso_action.shortcut() == QKeySequence("E")
    lasso_action.trigger()  # "When I press E"

    assert win._active_tool_id == LassoTool.tool_id
    assert view.active_selection() is None


# =========================================================================
# SC-U029-3 — entering a non-selection tool leaves the selection untouched
# =========================================================================


def test_sc_u029_3_entering_non_selection_tool_leaves_selection_unchanged(qtbot):
    """SC-U029-3: switching to pencil leaves the active selection BYTE-FOR-BYTE
    as it was — asserted via ``SelectionMask.__eq__`` against a pre-switch
    copy, not merely "still not None"."""
    win = _window(qtbot)
    record = win.active_tab()
    view = record.view
    buf = record.scene.active_buffer()

    win._tool_actions[RectSelectTool.tool_id].trigger()
    mask = rect_mask(buf.width, buf.height, 2, 2, 4, 4)
    view.set_selection(mask)
    before = view.active_selection().copy()

    pencil_action = win._tool_actions[PencilTool.tool_id]
    assert pencil_action.shortcut() == QKeySequence("A")
    pencil_action.trigger()  # "When I press A"

    assert win._active_tool_id == PencilTool.tool_id
    after = view.active_selection()
    assert after is not None
    assert after == before  # byte-for-byte, not merely present


# =========================================================================
# SC-U029-4 / REQ-IS-UI-029 property 1 — ORDERING: the float is committed
# strictly before the clear
# =========================================================================


def test_sc_u029_4_ordering_float_is_committed_before_the_clear(qtbot):
    """SC-U029-4 / property 1 (ORDERING): with a live floating move in
    progress on select_rect, pressing D again (its own shortcut — this is
    the Gherkin's literal Given/When) first COMMITS the float to the
    buffer, and only then clears the selection.

    Why this is worth asserting even though, in the *shipped* handler, a
    wrong order would not corrupt the pixel content either way (the
    floating controller holds its own captured state independently of the
    view's ``_selection`` attribute — verified by reading
    ``FloatingMoveController.commit()``, which never reads
    ``ctx.selection``/the view's mask): a plausible WRONG implementation of
    "discard the active selection" is to call something that cancels a
    pending float (non-destructively reverting it, pushing nothing) instead
    of committing it — losing the user's drag. This test pins the
    OBSERVABLE outcome (committed pixels present, no command lost, no
    command duplicated, selection cleared afterward) so such a regression
    is caught regardless of which internal path a future change takes.
    """
    win = _window(qtbot)
    record, view, scene, stack, buf = _prep_move_selection(win)
    controller = view.floating_controller()

    press(view, 3, 3)  # inside the (2,2)-(4,4) mask -> lifts a float
    move(view, 7, 5)  # offset (4, 2); no release -> float stays live
    assert controller.is_active()
    assert buf.get_pixel(2, 2) == RED  # non-destructive: base still unmutated

    win._tool_actions[RectSelectTool.tool_id].trigger()  # "When I press D" again

    assert not controller.is_active()  # the float was resolved...
    assert stack.count() == 1  # ...by exactly ONE commit (not lost, not doubled)
    assert buf.get_pixel(6, 4) == RED  # destination holds the committed content
    assert buf.get_pixel(2, 2) == TRANSPARENT  # origin vacated: a real MOVE landed
    assert view.active_selection() is None  # ...and only THEN was it cleared


# =========================================================================
# SC-U029-5 / REQ-IS-UI-029 property 2 — NO UNDO ENTRY
# =========================================================================


def test_sc_u029_5_clear_pushes_no_undo_command(qtbot):
    """SC-U029-5 / property 2 (NO UNDO ENTRY): the clear leaves the undo
    stack depth UNCHANGED, matching the shipped deselect action's contract
    (``_on_clear_selection`` -> ``record.view.clear_selection()``, which
    also pushes nothing). Isolated from any floating-move commit (no float
    set up here) so a stack-count change can only come from the clear
    itself, never from a co-mingled float commit."""
    win = _window(qtbot)
    record = win.active_tab()
    view, stack = record.view, record.stack
    buf = record.scene.active_buffer()
    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    assert view.active_selection() is not None

    depth_before = stack.count()
    win._tool_actions[RectSelectTool.tool_id].trigger()  # "When I press D"
    depth_after = stack.count()

    assert depth_after == depth_before  # the undo stack depth is unchanged
    assert view.active_selection() is None  # and the clear genuinely happened


# =========================================================================
# SC-U029-6 — re-activating the ALREADY-ACTIVE selection tool also clears
# =========================================================================


def test_sc_u029_6_reactivating_already_active_selection_tool_clears(qtbot):
    """SC-U029-6 [ASSUMPTION CL-IS-08 — flagged, not a user ruling]: pressing
    D again while select_rect is ALREADY the active tool still clears the
    selection, giving a deliberate one-key "start over" gesture.

    This is a recorded ASSUMPTION (spec.md §5.2, "ASSUMPTION (not ruled)"),
    cheap to reverse — reversal changes REQ-IS-UI-029 only. Whoever reverses
    it later should find this note rather than have to re-derive the
    behaviour: Qt DOES still fire ``triggered(True)`` when ``QAction.
    trigger()`` is called on an action that is already the checked member of
    an exclusive ``QActionGroup`` (verified by probe before writing this
    assertion: a throwaway test connected an observer to ``triggered`` and
    confirmed ``fired == [True]`` on the re-trigger), so the shipped
    handler's unconditional membership check (it does not compare the
    incoming tool id against the previous one) reaches the clear branch on
    a same-tool re-press exactly as it does on a different-tool switch.
    """
    win = _window(qtbot)
    record = win.active_tab()
    view = record.view
    buf = record.scene.active_buffer()

    action = win._tool_actions[RectSelectTool.tool_id]
    action.trigger()
    assert win._active_tool_id == RectSelectTool.tool_id
    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    assert view.active_selection() is not None

    action.trigger()  # "When I press D again" -- SAME tool, already active

    assert win._active_tool_id == RectSelectTool.tool_id  # unchanged
    assert view.active_selection() is None  # cleared anyway


# =========================================================================
# SC-U029-7 — the clear also fires from a real toolbar click
# =========================================================================


def test_sc_u029_7_clear_also_fires_from_the_toolbar(qtbot):
    """SC-U029-7: triggering select_lasso from the LEFT TOOLBAR (a real
    ``qtbot.mouseClick`` on the toolbar's own widget for that action, not a
    hand-called ``.trigger()``) clears the selection exactly as the
    keyboard shortcut does."""
    win = _window(qtbot)
    win.show()
    qtbot.waitExposed(win)
    record = win.active_tab()
    view = record.view
    buf = record.scene.active_buffer()
    assert win._active_tool_id == PencilTool.tool_id

    view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    assert view.active_selection() is not None

    lasso_action = win._tool_actions[LassoTool.tool_id]
    widget = win._toolbar.widgetForAction(lasso_action)
    assert widget is not None  # the action is really mounted on the toolbar
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)

    assert win._active_tool_id == LassoTool.tool_id
    assert view.active_selection() is None


# =========================================================================
# SC-R-32 / REQ-IS-UI-029 property 3 / REQ-P2-LOGIC-006 — mask-constrained
# drawing is unchanged (see the PENCIL vs. RECTANGLE module note above)
# =========================================================================


def test_sc_r32_mask_constrained_drawing_survives_a_real_tool_switch(qtbot):
    """SC-R-32 / property 3: select a region, switch to a NON-selection
    drawing tool through the REAL ``_on_tool_action`` dispatch (the exact
    function this fix changed), draw across the selection boundary, and assert
    the commit is CLIPPED to the mask — pixels inside stay editable, pixels
    outside stay untouched, exactly as before this job (REQ-P2-LOGIC-006).

    Uses the RECTANGLE tool, not the pencil literally named in the dispatch
    order — see the module docstring's "PENCIL vs. RECTANGLE" note for the
    probed evidence that the shipped ``PencilTool`` is not mask-constrained
    at all (a pre-existing, unrelated characteristic), and for why the
    rectangle tool is what REQ-P2-LOGIC-006 and the existing ``SC-R-32``
    regression pin (``test_input_scheme_regression.py``,
    ``test_shape_mode.py::test_shape_commit_is_mask_constrained``) actually
    exercise.
    """
    win = _window(qtbot)
    record = win.active_tab()
    view, stack = record.view, record.stack
    prepare_for_click(view)

    win._tool_actions[RectSelectTool.tool_id].trigger()
    buf = record.scene.active_buffer()
    mask = rect_mask(buf.width, buf.height, 4, 4, 8, 8)  # a sub-box of a 16x16 buffer
    view.set_selection(mask)
    win._rectangle_tool.set_filled(True)
    view.set_active_color(RED)

    # Entering "rectangle" is NOT a selection-entry tool id -> the selection
    # MUST survive this real dispatch (the other half of REQ-IS-UI-029).
    win._tool_actions[RectangleTool.tool_id].trigger()
    assert win._active_tool_id == RectangleTool.tool_id
    assert view.active_selection() is not None
    assert view.active_selection() == mask

    # Draw a filled rectangle across the WHOLE buffer -- well past the mask
    # boundary on every side.
    press(view, 0, 0)
    move(view, 15, 15)
    release(view, 15, 15)

    assert stack.count() == 1  # exactly one committed shape command
    assert buf.get_pixel(6, 6) == RED  # inside the selection -> painted
    assert buf.get_pixel(1, 1) == TRANSPARENT  # outside (above/left) -> untouched
    assert buf.get_pixel(12, 12) == TRANSPARENT  # outside (below/right) -> untouched
    assert buf.get_pixel(4, 4) == RED  # the selection's own top-left corner
    assert buf.get_pixel(8, 8) == RED  # the selection's own bottom-right corner
    assert buf.get_pixel(3, 3) == TRANSPARENT  # just outside the top-left corner
    assert buf.get_pixel(9, 9) == TRANSPARENT  # just outside the bottom-right corner
