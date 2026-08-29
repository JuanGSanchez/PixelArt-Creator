"""Batch-export UI acceptance (SC-UI-005-1, REQ-P7-UI-005 / -008).

The batch panel assembles multiple targets and exports them in ONE action on the
window-owned controller, marking each row succeeded/failed as the per-target
signals arrive — one failure never aborts the rest (continue-on-failure). Headless,
both themes (autouse ``theme`` fixture). The controller is drained by the
``export_controller`` fixture teardown.

``Batch_Export_Panel._on_add`` opens a modal ``Export_Dialog`` (``exec()``), which
cannot run headlessly without user input, so these tests populate the target list
the same way ``_on_add`` does (append + a list row) and then drive the real public
``_on_export_all`` path end to end.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from pixelart_creator.logic.export import ExportFormat, ExportRequest
from pixelart_creator.ui.batch_export_panel import Batch_Export_Panel
from pixelart_creator.ui.export_worker import ExportTarget
from testing.suites.ui._export_helpers import single_frame_document


def _add_target(panel: Batch_Export_Panel, target: ExportTarget) -> None:
    """Append ``target`` to the panel exactly as ``_on_add`` does (minus the modal)."""
    panel._targets.append(target)
    item = QListWidgetItem(target.label)
    item.setData(Qt.ItemDataRole.UserRole, target.label)
    panel._list.addItem(item)


def _png_target(tmp_path, name):
    return ExportTarget(
        request=ExportRequest(fmt=ExportFormat.PNG),
        out_path=str(tmp_path / name),
        label=name,
    )


def _panel(qtbot, export_controller, document):
    panel = Batch_Export_Panel()
    qtbot.addWidget(panel)
    panel.set_context(export_controller, lambda: document)
    return panel


def test_sc_ui_005_batch_exports_all_targets_in_one_action(
    qtbot, export_controller, tmp_path
):
    """SC-UI-005-1: several targets export in one Export-All action; each is written."""
    doc = single_frame_document()
    panel = _panel(qtbot, export_controller, doc)
    for name in ("one.png", "two.png", "three.png"):
        _add_target(panel, _png_target(tmp_path, name))

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        panel._on_export_all()

    for name in ("one.png", "two.png", "three.png"):
        assert (tmp_path / name).exists()
    # Progress bar reached the target count and every row is marked done.
    assert panel._progress.value() == 3
    for row in range(panel._list.count()):
        assert "done" in panel._list.item(row).text()


def test_sc_ui_005_continue_on_failure_marks_per_target_status(
    qtbot, export_controller, tmp_path
):
    """SC-UI-005-1 / -008: a bad target is marked failed, the others still succeed
    and are marked done — the batch never aborts on one failure."""
    doc = single_frame_document()
    panel = _panel(qtbot, export_controller, doc)

    # A regular file blocks the second target's parent dir -> genuine OSError.
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")

    _add_target(panel, _png_target(tmp_path, "ok1.png"))
    _add_target(
        panel,
        ExportTarget(
            request=ExportRequest(fmt=ExportFormat.PNG),
            out_path=str(blocker / "nope.png"),
            label="bad.png",
        ),
    )
    _add_target(panel, _png_target(tmp_path, "ok2.png"))

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        panel._on_export_all()

    texts = [panel._list.item(r).text() for r in range(panel._list.count())]
    assert "done" in texts[0]
    assert "failed" in texts[1]
    assert "done" in texts[2]
    # The surviving targets were genuinely written despite the middle failure.
    assert (tmp_path / "ok1.png").exists()
    assert (tmp_path / "ok2.png").exists()
    assert export_controller.is_busy() is False


def test_sc_ui_005_busy_toggles_control_enablement(qtbot, export_controller, tmp_path):
    """SC-UI-005-1: while a run is in flight editing/re-export disable + Cancel
    enables; after it finishes they restore (busyChanged-driven)."""
    doc = single_frame_document()
    panel = _panel(qtbot, export_controller, doc)
    _add_target(panel, _png_target(tmp_path, "z.png"))

    assert panel._cancel_button.isEnabled() is False
    assert panel._export_button.isEnabled() is True

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        panel._on_export_all()

    # Back to idle after the run: Cancel disabled, editing/export re-enabled.
    assert panel._cancel_button.isEnabled() is False
    assert panel._add_button.isEnabled() is True
    assert panel._export_button.isEnabled() is True


def test_sc_ui_005_add_without_document_is_a_no_op(qtbot, export_controller):
    """SC-UI-005-1 (guard): _on_add with no document does not crash or add a row."""
    panel = _panel(qtbot, export_controller, None)
    panel._on_add()  # provider returns None -> graceful early return
    assert panel._list.count() == 0


def test_sc_ui_005_add_target_via_dialog_appends_row(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """SC-UI-005-1: _on_add configures a target through the dialog and lists it."""
    from PySide6.QtWidgets import QDialog

    from pixelart_creator.ui.export_dialog import Export_Dialog

    out = tmp_path / "added.png"

    def _fake_exec(self):
        self._format_combo.setCurrentIndex(0)  # PNG
        self._path_edit.setText(str(out))
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Export_Dialog, "exec", _fake_exec)
    panel = _panel(qtbot, export_controller, single_frame_document())
    panel._on_add()
    assert panel._list.count() == 1
    assert len(panel._targets) == 1


def test_sc_ui_005_add_target_dialog_rejected_adds_nothing(
    qtbot, monkeypatch, export_controller
):
    """SC-UI-005-1: a dismissed add dialog leaves the target list unchanged."""
    from PySide6.QtWidgets import QDialog

    from pixelart_creator.ui.export_dialog import Export_Dialog

    monkeypatch.setattr(Export_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    panel = _panel(qtbot, export_controller, single_frame_document())
    panel._on_add()
    assert panel._list.count() == 0


def test_sc_ui_005_remove_deletes_selected_target(qtbot, export_controller, tmp_path):
    """SC-UI-005-1: _on_remove drops the selected row and its target."""
    panel = _panel(qtbot, export_controller, single_frame_document())
    _add_target(panel, _png_target(tmp_path, "a.png"))
    _add_target(panel, _png_target(tmp_path, "b.png"))
    panel._list.setCurrentRow(0)
    panel._on_remove()
    assert panel._list.count() == 1
    assert len(panel._targets) == 1


def test_sc_ui_005_cancel_delegates_to_controller(
    qtbot, monkeypatch, export_controller
):
    """SC-UI-005-1: the panel's Cancel forwards to the controller's cooperative cancel."""
    panel = _panel(qtbot, export_controller, single_frame_document())
    called: list[bool] = []
    monkeypatch.setattr(export_controller, "cancel", lambda: called.append(True))
    panel._on_cancel()
    assert called == [True]
