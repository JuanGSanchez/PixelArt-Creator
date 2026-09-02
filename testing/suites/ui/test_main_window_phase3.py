"""Main-window workflow-wiring tests (branch coverage of slots).

These drive the shell slots that bind the Phase-3 palette workflows to the
Workflow-wiring logic — the happy paths plus the defensive guard / error branches that
the per-widget acceptance tests do not reach (cycle-apply, extract, swap guards,
mode-switch errors, mode-indicator refresh). Each op stays exactly one undoable
command; guards warn rather than crash. Both themes via the autouse fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.ui import main_window as mw
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.palette_constraint_panel import PRESET_NES


@pytest.fixture
def win(qtbot) -> Main_Window:
    window = Main_Window()
    qtbot.addWidget(window)
    return window


@pytest.fixture
def warn(monkeypatch):
    """Capture QMessageBox.warning calls."""
    calls: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: calls.append(a) or QMessageBox.StandardButton.Ok,
    )
    return calls


class _FakeExtractDialog:
    def __init__(self, palette, accepted=True):
        self._palette = palette
        self._accepted = accepted

    def __call__(self, parent=None):
        return self

    def exec(self):
        return int(
            QDialog.DialogCode.Accepted
            if self._accepted
            else QDialog.DialogCode.Rejected
        )

    def result_palette(self):
        return self._palette


class _FakeSwapDialog:
    def __init__(self, mapping, accepted=True):
        self._mapping = mapping
        self._accepted = accepted

    def __call__(self, max_index, parent=None):
        return self

    def exec(self):
        return int(
            QDialog.DialogCode.Accepted
            if self._accepted
            else QDialog.DialogCode.Rejected
        )

    def mapping(self):
        return dict(self._mapping)


# -- editor / ramp / dither-mode binding slots ---------------------------------


def test_editor_pick_sets_active_colour(win):
    """A pick in the editor list routes to the shell's active colour."""
    win._on_palette_selected_rgba((255, 255, 255, 255))
    assert win._active_color == (255, 255, 255, 255)


def test_dither_mode_combo_updates_tool(win):
    """Changing the dither-mode combo updates the tool's mode."""
    win._dither_mode_combo.setCurrentIndex(1)
    assert win._dither_tool.mode() == win._dither_mode_combo.currentData()


def test_palette_edited_refreshes_surfaces(win):
    """_on_palette_edited refreshes the palette surfaces for the active tab."""
    win._on_palette_edited()  # must not raise with an active tab


def test_ramp_picked_and_added(win):
    """Ramp pick sets the active colour; ramp add loads it as one command."""
    record = win.active_tab()
    win._on_ramp_picked((10, 20, 30, 255))
    assert win._active_color == (10, 20, 30, 255)
    before = record.stack.count()
    win._on_ramp_added([(1, 1, 1, 255), (2, 2, 2, 255)])
    assert record.stack.count() == before + 1


# -- constraint guard (unknown preset) -----------------------------------------


def test_constrain_unknown_preset_is_no_op(win):
    """An unknown constraint preset resolves to no palette and does nothing."""
    record = win.active_tab()
    before = record.stack.count()
    win._on_constrain("not-a-preset")
    assert record.stack.count() == before


# -- colour-cycling apply (commit + RGBA guard) --------------------------------


def test_cycle_apply_commits_on_indexed_as_one_command(win):
    """Committing a cycle on an indexed buffer pushes exactly one command."""
    record = win.active_tab()
    win._on_convert_to_indexed()
    before = record.stack.count()
    win._on_cycle_apply(0, 2, 1)
    assert record.stack.count() == before + 1


def test_cycle_apply_on_rgba_warns(win, warn):
    """Committing a cycle on an RGBA buffer warns and pushes nothing."""
    record = win.active_tab()
    before = record.stack.count()
    win._on_cycle_apply(0, 2, 1)
    assert warn
    assert record.stack.count() == before


# -- extract-from-image dialog wiring ------------------------------------------


def test_extract_accepted_loads_palette_into_editor(win, monkeypatch):
    """An accepted extract dialog loads its palette as one editor command."""
    record = win.active_tab()
    palette = Palette([(9, 9, 9, 255), (8, 8, 8, 255)])
    monkeypatch.setattr(mw, "Extract_Palette_Dialog", _FakeExtractDialog(palette))
    before = record.stack.count()
    win._on_extract_palette()
    assert record.stack.count() == before + 1
    assert record.document.palette.colors() == [(9, 9, 9, 255), (8, 8, 8, 255)]


def test_extract_cancelled_is_no_op(win, monkeypatch):
    """A cancelled extract dialog changes nothing."""
    record = win.active_tab()
    monkeypatch.setattr(
        mw,
        "Extract_Palette_Dialog",
        _FakeExtractDialog(Palette([(1, 1, 1, 255)]), accepted=False),
    )
    before = record.stack.count()
    win._on_extract_palette()
    assert record.stack.count() == before


# -- palette-swap guards -------------------------------------------------------


def test_swap_on_rgba_warns(win, warn):
    """Palette swap on an RGBA document warns rather than applying."""
    win._on_palette_swap()  # default doc is RGBA
    assert warn


def test_swap_empty_mapping_is_no_op(win, monkeypatch):
    """An empty remap on an indexed document pushes no command."""
    win._on_convert_to_indexed()
    record = win.active_tab()
    before = record.stack.count()
    monkeypatch.setattr(mw, "Palette_Swap_Dialog", _FakeSwapDialog({}))
    win._on_palette_swap()
    assert record.stack.count() == before


def test_swap_out_of_range_index_warns(win, warn, monkeypatch):
    """A remap referencing an out-of-range index surfaces an error, no crash."""
    win._on_convert_to_indexed()
    record = win.active_tab()
    before = record.stack.count()
    monkeypatch.setattr(mw, "Palette_Swap_Dialog", _FakeSwapDialog({0: 999}))
    win._on_palette_swap()
    assert warn
    assert record.stack.count() == before


# -- mode-switch error branches + indicator refresh ----------------------------


def test_convert_to_rgba_when_already_rgba_warns(win, warn):
    """Convert-to-RGBA on an already-RGBA buffer surfaces an error."""
    win._on_convert_to_rgba()
    assert warn


def test_convert_to_indexed_when_already_indexed_warns(win, warn):
    """Convert-to-indexed on an already-indexed buffer surfaces an error."""
    win._on_convert_to_indexed()
    warn.clear()
    win._on_convert_to_indexed()
    assert warn


def test_refresh_mode_ui_without_tab_disables_actions(win):
    """With no open document the convert actions are disabled (guard branch)."""
    win.close_document(0)
    win._refresh_mode_ui()
    assert not win._to_indexed_action.isEnabled()
    assert not win._to_rgba_action.isEnabled()
