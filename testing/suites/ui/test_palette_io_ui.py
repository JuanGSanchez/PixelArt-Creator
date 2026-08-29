"""Palette import/export UI acceptance tests (REQ-P3-UI-002).

One test per acceptance criterion for the import/export actions on
:class:`Palette_Editor_Panel` (the thin disk I/O living in the UI over the
Qt-free ``logic/palette_io`` encode/decode):

* SC-U002-1 exporting then importing round-trips the palette.
* SC-U002-2 a malformed imported file surfaces a user-facing error, no crash.
* SC-U002-3 the import/export actions are tr()-wrapped and keyboard-reachable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QMessageBox

from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.palette_editor_panel import Palette_Editor_Panel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


@pytest.fixture
def editor(qtbot):
    """A bound editor ``(panel, palette, stack)``."""
    panel = Palette_Editor_Panel()
    qtbot.addWidget(panel)
    palette = Palette(STARTER)
    stack = QUndoStack()
    panel.set_context(palette, stack, lambda: None)
    return panel, palette, stack


# -- SC-U002-1 (export then import round-trips the palette) --------------------


def test_sc_u002_1_export_then_import_round_trips(editor, tmp_path, monkeypatch):
    """SC-U002-1: export to .gpl then import reproduces the palette."""
    panel, palette, _stack = editor
    target = tmp_path / "roundtrip.gpl"

    monkeypatch.setattr(
        "pixelart_creator.ui.palette_editor_panel.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(target), "GIMP palette (*.gpl)"),
    )
    panel._on_export()
    assert target.exists()

    # Mutate then re-import: the imported palette must equal the exported one.
    panel.set_active_color((7, 8, 9, 255))
    panel._on_add()
    monkeypatch.setattr(
        "pixelart_creator.ui.palette_editor_panel.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(target), "GIMP palette (*.gpl)"),
    )
    panel._on_import()
    assert palette.colors() == STARTER


# -- SC-U002-2 (malformed file surfaces an error, never crashes) ---------------


def test_sc_u002_2_malformed_import_surfaces_error_no_crash(
    editor, tmp_path, monkeypatch
):
    """SC-U002-2: a garbage file warns the user and leaves the palette intact."""
    panel, palette, _stack = editor
    bad = tmp_path / "broken.gpl"
    bad.write_text("this is not a palette \x00\x01", encoding="utf-8")
    before = palette.colors()

    warned: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        "pixelart_creator.ui.palette_editor_panel.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(bad), "GIMP palette (*.gpl)"),
    )
    panel._on_import()  # must not raise
    assert warned, "a malformed import did not surface a user-facing warning"
    assert palette.colors() == before


def test_sc_u002_2_missing_file_surfaces_error_no_crash(editor, monkeypatch):
    """SC-U002-2: importing a non-existent path warns rather than crashing."""
    panel, palette, _stack = editor
    before = palette.colors()
    warned: list = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        "pixelart_creator.ui.palette_editor_panel.QFileDialog.getOpenFileName",
        lambda *a, **k: ("/no/such/palette.gpl", "GIMP palette (*.gpl)"),
    )
    panel._on_import()
    assert warned
    assert palette.colors() == before


# -- SC-U002-3 (actions tr()-wrapped + keyboard-reachable, both themes) --------


def test_sc_u002_3_import_export_actions_labelled_and_focusable(editor):
    """SC-U002-3: import/export buttons carry labels and take keyboard focus."""
    panel, _palette, _stack = editor
    for button in (panel._import_button, panel._export_button):
        assert button.text() != ""
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
