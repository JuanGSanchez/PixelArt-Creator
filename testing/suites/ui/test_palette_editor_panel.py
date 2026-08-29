"""Palette-editor panel acceptance tests (REQ-P3-UI-001).

One test per acceptance criterion for :class:`Palette_Editor_Panel`:

* SC-U001-1 add / remove / reorder update the bound palette in place.
* SC-U001-2 each mutation is exactly ONE undoable command; undo restores the
  prior palette exactly.
* SC-U001-3 the controls are tr()-wrapped and keyboard-reachable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.palette_editor_panel import Palette_Editor_Panel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]
RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)


@pytest.fixture
def editor(qtbot):
    """A bound editor: ``(panel, palette, stack, changed_calls)``."""
    panel = Palette_Editor_Panel()
    qtbot.addWidget(panel)
    palette = Palette(STARTER)
    stack = QUndoStack()
    changed: list = []
    panel.set_context(palette, stack, lambda: changed.append(True))
    return panel, palette, stack, changed


# -- SC-U001-1 (add / remove / reorder update the palette) ---------------------


def test_sc_u001_1_add_appends_the_active_colour(editor):
    """SC-U001-1: Add appends the active colour to the bound palette."""
    panel, palette, _stack, _changed = editor
    panel.set_active_color(GREEN)
    panel._on_add()
    assert palette.colors()[-1] == GREEN
    assert len(palette) == len(STARTER) + 1


def test_sc_u001_1_remove_deletes_the_selected_swatch(editor):
    """SC-U001-1: Remove deletes the selected palette entry."""
    panel, palette, _stack, _changed = editor
    panel._list.setCurrentRow(1)  # the white swatch
    panel._on_remove()
    assert (255, 255, 255, 255) not in palette.colors()
    assert len(palette) == len(STARTER) - 1


def test_sc_u001_1_reorder_moves_a_swatch_in_place(editor):
    """SC-U001-1: Move Down reorders the palette (binds to reorder)."""
    panel, palette, _stack, _changed = editor
    panel._list.setCurrentRow(0)  # black at index 0
    panel._on_move(1)  # move it down one
    assert palette.colors()[1] == (0, 0, 0, 255)
    assert palette.colors()[0] == (255, 255, 255, 255)


# -- SC-U001-2 (one undoable command; undo restores the prior palette) ---------


def test_sc_u001_2_add_is_one_undoable_command(editor):
    """SC-U001-2: Add pushes exactly one command; undo restores the palette."""
    panel, palette, stack, _changed = editor
    before = palette.colors()
    panel.set_active_color(RED)
    panel._on_add()
    assert stack.count() == 1
    stack.undo()
    assert palette.colors() == before


def test_sc_u001_2_remove_undo_restores_exactly(editor):
    """SC-U001-2: undo of a remove restores the exact prior palette."""
    panel, palette, stack, _changed = editor
    before = palette.colors()
    panel._list.setCurrentRow(2)
    panel._on_remove()
    assert stack.count() == 1
    stack.undo()
    assert palette.colors() == before


def test_sc_u001_2_reorder_undo_restores_exactly(editor):
    """SC-U001-2: undo of a reorder restores the exact prior palette."""
    panel, palette, stack, _changed = editor
    before = palette.colors()
    panel._list.setCurrentRow(0)
    panel._on_move(1)
    assert stack.count() == 1
    stack.undo()
    assert palette.colors() == before


# -- SC-U001-3 (tr()-wrapped, keyboard-reachable, both themes) -----------------


def test_sc_u001_3_controls_are_labelled_and_keyboard_reachable(editor):
    """SC-U001-3: every action carries a translated label + is focusable."""
    panel, _palette, _stack, _changed = editor
    for button in (
        panel._add_button,
        panel._remove_button,
        panel._up_button,
        panel._down_button,
        panel._import_button,
        panel._export_button,
    ):
        assert button.text() != ""
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert panel.accessibleName() != ""
    assert panel._list.accessibleName() != ""


# -- guard / edge-path coverage (defensive branches) ---------------------------


def test_add_when_full_warns_and_pushes_nothing(qtbot, monkeypatch):
    """A full palette rejects Add with a warning and adds no command."""
    from PySide6.QtWidgets import QMessageBox

    from pixelart_creator.logic.palette import MAX_PALETTE_SIZE

    panel = Palette_Editor_Panel()
    qtbot.addWidget(panel)
    full = Palette([(i, 0, 0, 255) for i in range(MAX_PALETTE_SIZE)])
    stack = QUndoStack()
    panel.set_context(full, stack, lambda: None)
    warned: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )
    panel.set_active_color((5, 5, 5, 255))
    panel._on_add()
    assert warned
    assert stack.count() == 0


def test_replace_all_swaps_palette_as_one_command(editor):
    """replace_all loads a whole palette as a single reversible command."""
    panel, palette, stack, _changed = editor
    before = palette.colors()
    panel.replace_all([(1, 2, 3, 255), (4, 5, 6, 255)], "Load")
    assert stack.count() == 1
    assert palette.colors() == [(1, 2, 3, 255), (4, 5, 6, 255)]
    stack.undo()
    assert palette.colors() == before


def test_rows_moved_reorder_pushes_one_command(editor):
    """A completed drag-drop reorder (rowsMoved) commits one reversible command."""
    panel, palette, stack, _changed = editor
    # Reorder the list widget items, then fire the model's rowsMoved slot.
    item = panel._list.takeItem(0)
    panel._list.insertItem(2, item)
    panel._on_rows_moved()
    assert stack.count() == 1
    assert palette.colors()[2] == (0, 0, 0, 255)


def test_unbound_panel_mutations_are_safe_no_ops(qtbot):
    """An unbound editor swallows every mutation without raising."""
    panel = Palette_Editor_Panel()
    qtbot.addWidget(panel)
    panel._on_add()
    panel._on_remove()
    panel._on_move(1)
    panel.replace_all([(0, 0, 0, 255)], "x")
    assert panel.selected_color() is None


def test_export_import_cancelled_dialog_is_no_op(editor, monkeypatch):
    """Cancelling the file dialog (empty path) leaves the palette untouched."""
    panel, palette, stack, _changed = editor
    monkeypatch.setattr(
        "pixelart_creator.ui.palette_editor_panel.QFileDialog.getSaveFileName",
        lambda *a, **k: ("", ""),
    )
    monkeypatch.setattr(
        "pixelart_creator.ui.palette_editor_panel.QFileDialog.getOpenFileName",
        lambda *a, **k: ("", ""),
    )
    panel._on_export()
    panel._on_import()
    assert stack.count() == 0


def test_fmt_for_resolves_suffix_and_falls_back(editor):
    """_fmt_for maps a known suffix to its token and falls back to hex."""
    panel, _palette, _stack, _changed = editor
    assert panel._fmt_for("palette.gpl", "") == "gpl"
    assert panel._fmt_for("palette.pal", "") == "pal"
    assert panel._fmt_for("palette.unknown", "") == "hex"
