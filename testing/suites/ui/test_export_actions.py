"""Single-export front-end acceptance (REQ-P7-UI-001, -008, -009).

``run_export_dialog`` opens the modal ``Export_Dialog`` and submits one target to
the window-owned controller — the SAME off-thread engine path the batch UI and CLI
use. The modal ``exec()`` cannot run headlessly with user input, so these tests
monkeypatch ``Export_Dialog.exec`` (and the static ``QMessageBox`` helpers) to
exercise every branch: no document, dialog rejected, accepted-without-path, and the
happy submit path. Headless, both themes (autouse ``theme`` fixture).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from pixelart_creator.ui import export_actions
from pixelart_creator.ui.export_dialog import Export_Dialog
from testing.suites.ui._export_helpers import single_frame_document


def _parent(qtbot) -> QWidget:
    parent = QWidget()
    qtbot.addWidget(parent)
    return parent


def test_no_document_shows_notice_and_does_not_submit(
    qtbot, monkeypatch, export_controller
):
    """REQ-P7-UI-001 guard: no open document → an information notice, no export."""
    calls: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: calls.append("info")
    )
    export_actions.run_export_dialog(_parent(qtbot), None, export_controller)
    assert calls == ["info"]
    assert export_controller.is_busy() is False


def test_dialog_rejected_is_a_noop(qtbot, monkeypatch, export_controller):
    """A dismissed dialog submits nothing (no crash, stays idle)."""
    monkeypatch.setattr(Export_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    export_actions.run_export_dialog(
        _parent(qtbot), single_frame_document(), export_controller
    )
    assert export_controller.is_busy() is False


def test_accepted_without_path_warns(qtbot, monkeypatch, export_controller):
    """REQ-P7-UI-008: accepting with no destination → a warning, not a crash."""
    warned: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append("warn"))
    monkeypatch.setattr(Export_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    export_actions.run_export_dialog(
        _parent(qtbot), single_frame_document(), export_controller
    )
    assert warned == ["warn"]
    assert export_controller.is_busy() is False


def test_accepted_with_path_submits_to_controller(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """REQ-P7-UI-001: a configured target is submitted to the shared engine."""
    out = tmp_path / "single.png"

    def _fake_exec(self):
        self._format_combo.setCurrentIndex(0)  # PNG
        self._path_edit.setText(str(out))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Export_Dialog, "exec", _fake_exec)
    doc = single_frame_document()
    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_actions.run_export_dialog(_parent(qtbot), doc, export_controller)
    assert out.exists()


def test_t24_undo_stack_unchanged_across_a_full_export_run(
    qtbot, monkeypatch, tmp_path
):
    """T-24 (AGT-06 audit) — REQ-P7-UI-009 behavioural: a completed export run
    pushes NO ``QUndoCommand``. Driven at the ``Main_Window`` level (through the
    real ``_on_export`` -> off-thread ``Export_Controller`` -> ``batchFinished``
    path a user actually exercises) rather than a bare submission-only check, so
    the assertion covers the WHOLE run, not just the call into
    ``run_export_dialog``."""
    from pixelart_creator.ui.export_dialog import Export_Dialog
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    # A prior, unrelated undo entry so "unchanged" is a genuine before/after
    # equality, not a vacuous 0 == 0.
    record.scene.active_buffer().set_pixel(0, 0, (10, 20, 30, 255))
    record.view.set_active_color((10, 20, 30, 255))
    from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

    prepare_for_click(record.view)
    click_pixel(record.view, 1, 1)
    stack_count_before = record.stack.count()
    assert stack_count_before >= 1

    out = tmp_path / "t24_export.png"

    def _fake_exec(self):
        self._format_combo.setCurrentIndex(0)  # PNG
        self._path_edit.setText(str(out))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Export_Dialog, "exec", _fake_exec)
    with qtbot.waitSignal(win._export_controller.batchFinished, timeout=5000):
        win._on_export()

    assert out.exists()
    assert record.stack.count() == stack_count_before  # export pushed NO command
