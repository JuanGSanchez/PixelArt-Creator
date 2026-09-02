"""Automation error surfacing + ATOMICITY assessment — SC-UI-008-1 [SEC-facing].

REQ-P8-UI-008 / SC-UI-008-1 requires: a failing / bounded / denied automation
surfaces a user-facing error, no arbitrary code runs, and the document is left
UNCORRUPTED — the spec is explicit that a *partial run is rolled back*.

Single-op failures (unknown op, out-of-range procgen, runaway MAX_SCRIPT_OPS) meet
this: the failing op raises before it applies, nothing lands on the undo stack,
and the document is untouched — verified below.

The ATOMICITY nuance the UI layer flagged was a real defect: for a MULTI-op script where
op[0] applied and a later op failed, ``logic.scripting.dispatch`` raised WITHOUT
rolling back op[0], so the off-thread worker (which reverts only a returned
command) never reverted it — leaving op[0] applied on the live document, off the
undo stack. The implementation has since made dispatch ATOMIC (validate-all-up-front → one
GroupCommand → reverse-order rollback on failure): a failed multi-op dispatch now
leaves the document byte-identical, and a valid one is a single reversible command
(macro replay inherits it). The strict-xfail that pinned the defect has therefore
been REMOVED; the test below asserts the REAL atomic contract in both halves.
Headless; both themes.
"""

from __future__ import annotations

from pixelart_creator.logic.constants import MAX_SCRIPT_OPS
from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._automation_helpers import (
    GREEN,
    RED,
    arrays_equal,
    batch_recolour_op,
    buffer_of,
    paint,
    procgen_op,
    run_ops,
    unknown_op,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_008_unknown_op_surfaces_error_document_uncorrupted(
    qtbot, mute_message_boxes
):
    """SC-UI-008-1: an unknown op → graceful error, nothing lands, doc uncorrupted."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    initial = buffer_of(tab.document).copy()

    run_ops(qtbot, win, [unknown_op()])

    assert stack.count() == 0
    assert arrays_equal(buffer_of(tab.document), initial)
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)


def test_sc_ui_008_out_of_range_procgen_surfaces_error_uncorrupted(
    qtbot, mute_message_boxes
):
    """SC-UI-008-1: an out-of-range procgen → graceful error, document uncorrupted."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    initial = buffer_of(tab.document).copy()

    run_ops(qtbot, win, [procgen_op(seed=1, width=99999, height=99999)])

    assert stack.count() == 0
    assert arrays_equal(buffer_of(tab.document), initial)
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)


def test_sc_ui_008_runaway_script_hits_bound_gracefully(qtbot, mute_message_boxes):
    """SC-UI-008-1: a script above MAX_SCRIPT_OPS fails safely, document uncorrupted."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    initial = buffer_of(tab.document).copy()

    # The len bound is checked before any op applies (dispatch raises immediately).
    runaway = [procgen_op(seed=1)] * (int(MAX_SCRIPT_OPS) + 1)
    run_ops(qtbot, win, runaway)

    assert stack.count() == 0
    assert arrays_equal(buffer_of(tab.document), initial)
    assert any("MAX_SCRIPT_OPS" in text for _kind, _title, text in mute_message_boxes)


def test_sc_ui_008_multiop_script_failure_is_atomic(qtbot, mute_message_boxes):
    """SC-UI-008-1: a mid-script failure rolls back — the document stays uncorrupted.

    Post the atomic-dispatch fix, un-xfailed and asserting the REAL contract: a
    multi-op run whose later op fails must leave the document byte-identical to the
    pre-run state (no op applied off the undo stack) and push NOTHING onto the stack.
    """
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    paint(tab.document, RED)
    initial = buffer_of(tab.document).copy()

    # op0 (valid batch recolour RED→GREEN) would apply; op1 (unknown) fails. With
    # atomic dispatch the whole run is rejected, so op0 never lands on the document.
    run_ops(qtbot, win, [batch_recolour_op(src=RED, dst=GREEN), unknown_op()])

    assert stack.count() == 0  # a failed multi-op run pushes no command
    # Atomic contract: the partial run is rolled back → document == initial.
    assert arrays_equal(buffer_of(tab.document), initial)


def test_sc_ui_008_valid_multiop_run_is_one_undoable_step(qtbot, mute_message_boxes):
    """SC-UI-008-1: a VALID multi-op run lands as exactly one reversible command.

    The other half of the atomic-dispatch contract: when every op validates, the whole
    multi-op script is applied as one grouped :class:`AutomationCommand`, so a single
    undo restores the exact pre-run document (byte-identical).
    """
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    paint(tab.document, RED)
    initial = buffer_of(tab.document).copy()

    # Two valid ops: batch recolour RED→GREEN, then procgen writes noise into frame 0.
    run_ops(qtbot, win, [batch_recolour_op(src=RED, dst=GREEN), procgen_op(seed=7)])

    assert stack.count() == 1  # the whole multi-op run is ONE grouped command
    assert not arrays_equal(buffer_of(tab.document), initial)  # it actually mutated

    stack.undo()  # one undo reverses the entire run
    assert stack.index() == 0
    assert arrays_equal(buffer_of(tab.document), initial)
