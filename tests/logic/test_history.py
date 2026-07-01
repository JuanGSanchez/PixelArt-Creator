"""Tests for pixelart_creator.logic.history."""

from __future__ import annotations

import pytest

from pixelart_creator.logic import drawing
from pixelart_creator.logic.history import (
    FunctionCommand,
    History,
    PixelEdit,
    record_edit,
)
from pixelart_creator.logic.pixel_buffer import PixelBuffer

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def test_pixel_edit_execute_and_undo():
    buf = PixelBuffer(2, 2)
    edit = PixelEdit(buf, [(0, 0, (0, 0, 0, 0), RED)])
    edit.execute()
    assert buf.get_pixel(0, 0) == RED
    edit.undo()
    assert buf.get_pixel(0, 0) == (0, 0, 0, 0)
    assert len(edit) == 1


def test_function_command():
    box = {"v": 0}
    cmd = FunctionCommand(
        lambda: box.__setitem__("v", 1), lambda: box.__setitem__("v", 0)
    )
    cmd.execute()
    assert box["v"] == 1
    cmd.undo()
    assert box["v"] == 0


def test_history_push_execute_undo_redo():
    buf = PixelBuffer(2, 2)
    hist = History()
    edit = PixelEdit(buf, [(0, 0, (0, 0, 0, 0), RED)])
    hist.push(edit)
    assert buf.get_pixel(0, 0) == RED
    assert hist.can_undo and not hist.can_redo
    hist.undo()
    assert buf.get_pixel(0, 0) == (0, 0, 0, 0)
    assert hist.can_redo
    hist.redo()
    assert buf.get_pixel(0, 0) == RED


def test_history_push_without_execute():
    buf = PixelBuffer(1, 1)
    buf.set_pixel(0, 0, RED)  # already applied
    hist = History()
    edit = PixelEdit(buf, [(0, 0, (0, 0, 0, 0), RED)])
    hist.push(edit, execute=False)
    assert buf.get_pixel(0, 0) == RED  # unchanged by push
    hist.undo()
    assert buf.get_pixel(0, 0) == (0, 0, 0, 0)


def test_new_push_clears_redo():
    buf = PixelBuffer(1, 1)
    hist = History()
    hist.push(PixelEdit(buf, [(0, 0, (0, 0, 0, 0), RED)]))
    hist.undo()
    assert hist.can_redo
    hist.push(PixelEdit(buf, [(0, 0, (0, 0, 0, 0), BLUE)]))
    assert not hist.can_redo


def test_undo_redo_empty_returns_none():
    hist = History()
    assert hist.undo() is None
    assert hist.redo() is None


def test_history_limit_drops_oldest():
    buf = PixelBuffer(1, 1)
    hist = History(limit=2)
    for _ in range(4):
        hist.push(PixelEdit(buf, [(0, 0, (0, 0, 0, 0), RED)]))
    assert hist.undo_depth == 2


def test_history_bad_limit():
    with pytest.raises(ValueError):
        History(limit=0)
    with pytest.raises(ValueError):
        History(limit=-1)


def test_clear():
    buf = PixelBuffer(1, 1)
    hist = History()
    hist.push(PixelEdit(buf, [(0, 0, (0, 0, 0, 0), RED)]))
    hist.undo()
    hist.clear()
    assert not hist.can_undo and not hist.can_redo
    assert hist.redo_depth == 0


def test_record_edit_captures_drawing_op():
    buf = PixelBuffer(8, 8)
    edit = record_edit(buf, lambda b: drawing.line(b, 0, 0, 3, 0, RED), label="line")
    assert buf.get_pixel(3, 0) == RED
    assert edit.label == "line"
    edit.undo()
    assert buf.get_pixel(3, 0) == (0, 0, 0, 0)


def test_record_edit_ignores_unchanged_pixels():
    buf = PixelBuffer(4, 4, fill=RED)
    # Drawing RED over RED changes nothing -> empty edit.
    edit = record_edit(buf, lambda b: drawing.line(b, 0, 0, 3, 0, RED))
    assert len(edit) == 0


def test_record_edit_roundtrip_via_history():
    buf = PixelBuffer(8, 8)
    hist = History()
    edit = record_edit(buf, lambda b: drawing.flood_fill(b, 0, 0, BLUE))
    hist.push(edit, execute=False)
    assert buf.get_pixel(5, 5) == BLUE
    hist.undo()
    assert buf.get_pixel(5, 5) == (0, 0, 0, 0)
