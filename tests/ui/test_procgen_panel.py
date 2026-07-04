"""Procedural-generation panel — SC-UI-007-1 (REQ-P8-UI-007, REQ-P8-LOGIC-012).

The procgen panel gathers an algorithm + seed + region and generates content as
ONE undoable command; the same seed + parameters reproduce an identical result,
and an out-of-range size is rejected gracefully. The size spins are clamped to
``MAX_PROCGEN_DIMENSION`` so the control cannot request an unbuildable size.
Headless; both themes.
"""

from __future__ import annotations

from pixelart_creator.logic.constants import MAX_PROCGEN_DIMENSION
from pixelart_creator.ui.main_window import Main_Window
from tests.ui._automation_helpers import (
    RUN_TIMEOUT_MS,
    arrays_equal,
    buffer_of,
    procgen_op,
    run_ops,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_007_procgen_is_undoable_and_seed_reproduces(qtbot):
    """SC-UI-007-1: procgen lands one undoable command; the same seed reproduces it."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    initial = buffer_of(tab.document).copy()

    panel = win._procgen_panel
    panel._seed_spin.setValue(7)
    panel._width_spin.setValue(64)
    panel._height_spin.setValue(64)
    with qtbot.waitSignal(
        win._automation_controller.runFinished, timeout=RUN_TIMEOUT_MS
    ):
        panel._on_generate()
    generated = buffer_of(tab.document).copy()

    assert stack.count() == 1
    assert not arrays_equal(initial, generated)
    stack.undo()
    assert arrays_equal(buffer_of(tab.document), initial)
    stack.redo()  # same seed → identical content re-applied
    assert arrays_equal(buffer_of(tab.document), generated)


def test_sc_ui_007_same_seed_reproduces_across_documents(qtbot):
    """SC-UI-007-1: same seed + params → identical output on two fresh documents."""
    win1 = _window(qtbot)
    run_ops(qtbot, win1, [procgen_op(seed=42)])
    win2 = _window(qtbot)
    run_ops(qtbot, win2, [procgen_op(seed=42)])
    assert arrays_equal(
        buffer_of(win1.active_document()), buffer_of(win2.active_document())
    )


def test_sc_ui_007_out_of_range_size_is_rejected_gracefully(qtbot, mute_message_boxes):
    """SC-UI-007-1: a region larger than the buffer is rejected; no edit, graceful error."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    initial = buffer_of(tab.document).copy()

    # 128×128 region on a 64×64 buffer → ProcgenError (region exceeds buffer).
    run_ops(qtbot, win, [procgen_op(seed=1, width=128, height=128)])

    assert stack.count() == 0
    assert arrays_equal(buffer_of(tab.document), initial)  # document uncorrupted
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)


def test_sc_ui_007_size_spins_clamped_to_max_procgen_dimension(qtbot):
    """SC-UI-007-1: the width/height spins cannot request > MAX_PROCGEN_DIMENSION."""
    win = _window(qtbot)
    panel = win._procgen_panel
    assert panel._width_spin.maximum() == int(MAX_PROCGEN_DIMENSION)
    assert panel._height_spin.maximum() == int(MAX_PROCGEN_DIMENSION)
