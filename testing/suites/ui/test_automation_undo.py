"""One grouped QUndoCommand per automation edit — SC-UI-009-1 (REQ-P8-UI-009).

Every automation EDIT — script run, macro replay, batch recolour, procgen — is
pushed as exactly ONE grouped ``AutomationCommand`` and one undo restores the
prior state. Recording start/stop, plugin enable/disable, and selection are
view/session state and push NO undo command (CL-8). Headless; both themes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._automation_helpers import (
    GREEN,
    RED,
    batch_recolour_op,
    macro_of,
    paint,
    procgen_op,
    replay,
    run_ops,
    write_manifest,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_009_each_edit_is_exactly_one_grouped_command(qtbot):
    """SC-UI-009-1: script / batch / procgen / replay each push exactly one command."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    paint(tab.document, RED)
    assert stack.count() == 0

    run_ops(qtbot, win, [procgen_op(seed=7)])
    assert stack.count() == 1  # procgen edit
    run_ops(qtbot, win, [batch_recolour_op(src=RED, dst=GREEN)])
    assert stack.count() == 2  # batch recolour edit
    replay(qtbot, win, macro_of(procgen_op(seed=3)))
    assert stack.count() == 3  # macro replay edit

    # Undo pops exactly one edit at a time (each is one grouped command).
    stack.undo()
    assert stack.index() == 2
    stack.undo()
    assert stack.index() == 1


def test_sc_ui_009_recording_and_selection_push_no_command(qtbot):
    """SC-UI-009-1: recording start/stop and macro selection are view state (no undo)."""
    win = _window(qtbot)
    stack = win.active_tab().stack
    controls = win._macro_controls

    controls._record_button.setChecked(True)
    assert stack.count() == 0
    controls._record_button.setChecked(False)
    assert stack.count() == 0

    controls._add_macro(macro_of(procgen_op(seed=1)), "m")  # add + select
    controls._list.setCurrentRow(0)
    assert stack.count() == 0


def test_sc_ui_009_plugin_enable_disable_push_no_command(
    qtbot, monkeypatch, tmp_path, plugin_isolation
):
    """SC-UI-009-1: enabling/disabling a plugin is view state and pushes no undo command."""
    win = _window(qtbot)
    stack = win.active_tab().stack
    panel = win._plugin_manager_panel

    manifest = write_manifest(
        tmp_path / "m.json", name="undo-noop-plugin", capabilities=["read_document"]
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(manifest), "")),
    )
    panel._on_install()
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    panel._on_enable()
    assert "undo-noop-plugin" in panel._handles
    assert stack.count() == 0  # enable is view state — no undo entry

    panel._on_disable()
    assert "undo-noop-plugin" not in panel._handles
    assert stack.count() == 0  # disable is view state — no undo entry
