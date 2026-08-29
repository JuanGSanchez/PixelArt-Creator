"""Tests for logic.history.GroupCommand — the Phase-8 grouping primitive.

Covers REQ-P8-LOGIC-006 / REQ-P8-UI-009 support: a macro replay / script run /
batch is returned as one composite reversible command. Asserts
``apply ∘ undo == identity`` for grouped commands and that undo runs children in
reverse order (so the group is a single, correct reversible step).
"""

from __future__ import annotations

import numpy as np

from pixelart_creator.logic.history import Command, FunctionCommand, GroupCommand
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def test_group_command_is_a_command():
    assert issubclass(GroupCommand, Command)


def test_group_apply_undo_identity_on_buffer():
    buf = PixelBuffer(2, 2, ColorMode.RGBA)
    before = buf.data.copy()  # transparent
    c1 = FunctionCommand(lambda: buf.fill(RED), lambda: buf.fill((0, 0, 0, 0)))
    c2 = FunctionCommand(lambda: buf.fill(BLUE), lambda: buf.fill(RED))
    group = GroupCommand([c1, c2], label="script")
    group.execute()
    assert tuple(buf.data[0, 0]) == BLUE
    group.undo()  # runs c2.undo then c1.undo → back to transparent
    assert np.array_equal(buf.data, before)


def test_group_undo_runs_children_in_reverse():
    order = []
    c1 = FunctionCommand(lambda: order.append("do1"), lambda: order.append("undo1"))
    c2 = FunctionCommand(lambda: order.append("do2"), lambda: order.append("undo2"))
    group = GroupCommand([c1, c2])
    group.execute()
    group.undo()
    assert order == ["do1", "do2", "undo2", "undo1"]


def test_group_len_and_commands_view():
    c1 = FunctionCommand(lambda: None, lambda: None)
    c2 = FunctionCommand(lambda: None, lambda: None)
    group = GroupCommand([c1, c2])
    assert len(group) == 2
    assert group.commands == (c1, c2)


def test_empty_group_is_noop():
    group = GroupCommand([])
    group.execute()
    group.undo()
    assert len(group) == 0
