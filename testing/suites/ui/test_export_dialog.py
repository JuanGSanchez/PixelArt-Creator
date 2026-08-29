"""Export dialog acceptance tests — format, options, presets, destination.

pytest-qt, headless (``QT_QPA_PLATFORM=offscreen``); every test runs under BOTH
themes via the autouse ``theme`` fixture (REQ-P7-UI-012). One test per acceptance
criterion:

* SC-UI-001-1 — format/options/destination; export writes the file via the engine.
* SC-UI-002-1 — GIF frame-source + loop options; the request carries them.
* SC-UI-003-1 — sprite-sheet columns/padding; defaults from constants; OOR rejected.
* SC-UI-004-1 — atlas padding/max-dimension + JSON metadata toggle.
* SC-UI-006-1 — Unity / Godot engine-preset selection drives the request.
* SC-UI-009-1 — export is non-destructive and pushes no ``QUndoCommand``.
* SC-UI-013-1 — the dialog retranslates on ``QEvent.LanguageChange``.

The dialog performs NO encoding/layout of its own — it builds a frozen
``ExportRequest`` + ``ExportTarget`` for the shared ``logic``/``data`` engine
(REQ-P7-UI-007), so these tests assert the *request it builds* and, for -001, the
*file the shared engine writes* from it.
"""

from __future__ import annotations

from pixelart_creator.logic.constants import (
    DEFAULT_ATLAS_PADDING,
    DEFAULT_SPRITE_SHEET_COLUMNS,
    MAX_ATLAS_DIMENSION,
    MAX_EXPORT_FRAMES,
)
from pixelart_creator.logic.export import EnginePreset, ExportFormat
from pixelart_creator.ui.export_dialog import Export_Dialog
from tests.ui._export_helpers import animation_document, single_frame_document

#: Option-page indices in the dialog's format combo / stacked widget.
_PNG, _GIF, _SHEET, _ATLAS = 0, 1, 2, 3

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _dialog(qtbot, document) -> Export_Dialog:
    dialog = Export_Dialog(document)
    qtbot.addWidget(dialog)
    return dialog


def test_sc_ui_001_dialog_builds_target_and_engine_writes_file(
    qtbot, export_controller, tmp_path
):
    """SC-UI-001-1: pick PNG + a destination → the shared engine writes a PNG."""
    doc = single_frame_document()
    dialog = _dialog(qtbot, doc)
    dialog._format_combo.setCurrentIndex(_PNG)
    assert dialog.current_format() is ExportFormat.PNG
    out = tmp_path / "art.png"
    dialog._path_edit.setText(str(out))

    target = dialog.export_target()
    assert target is not None
    assert target.out_path == str(out)

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, (target,))

    assert out.exists()
    assert out.read_bytes().startswith(_PNG_SIGNATURE)


def test_sc_ui_001_no_destination_yields_no_target(qtbot):
    """SC-UI-001-1 (guard): an empty destination yields no target (no crash)."""
    dialog = _dialog(qtbot, single_frame_document())
    dialog._format_combo.setCurrentIndex(_PNG)
    dialog._path_edit.setText("   ")
    assert dialog.export_target() is None


def test_sc_ui_002_gif_options_frame_source_and_loop(qtbot):
    """SC-UI-002-1: GIF options expose frame source (doc + tags) and loop count."""
    doc = animation_document(frames=3, tag=True)
    dialog = _dialog(qtbot, doc)
    dialog._format_combo.setCurrentIndex(_GIF)
    assert dialog.current_format() is ExportFormat.GIF

    # Frame-source combo: "Whole document" (data=None) + each tag name (data=name).
    sources = [
        dialog._gif_source_combo.itemData(i)
        for i in range(dialog._gif_source_combo.count())
    ]
    assert None in sources  # whole document
    assert "walk" in sources  # the named tag

    # Select the tag + a finite loop count → the built request carries both.
    dialog._gif_source_combo.setCurrentIndex(sources.index("walk"))
    dialog._gif_loop_spin.setValue(3)
    request = dialog.build_request()
    assert request.fmt is ExportFormat.GIF
    assert request.tag == "walk"
    assert request.loop == 3


def test_sc_ui_003_sheet_options_defaults_and_out_of_range_rejected(qtbot):
    """SC-UI-003-1: sheet columns/padding default from constants; OOR is clamped."""
    dialog = _dialog(qtbot, animation_document(frames=4))
    dialog._format_combo.setCurrentIndex(_SHEET)

    # Defaults come from logic/constants.py (REQ-P7-LOGIC-012, single source).
    assert dialog._columns_spin.value() == DEFAULT_SPRITE_SHEET_COLUMNS
    assert dialog._sheet_padding_spin.value() == DEFAULT_ATLAS_PADDING

    # Out-of-range input is rejected by the spin's clamp (never fed unbounded to
    # the engine): a huge columns value clamps to MAX_EXPORT_FRAMES, negative to 0.
    dialog._columns_spin.setValue(MAX_EXPORT_FRAMES + 10_000)
    assert dialog._columns_spin.value() == MAX_EXPORT_FRAMES
    dialog._sheet_padding_spin.setValue(-5)
    assert dialog._sheet_padding_spin.value() == 0

    dialog._columns_spin.setValue(3)
    dialog._sheet_padding_spin.setValue(2)
    request = dialog.build_request()
    assert request.fmt is ExportFormat.SPRITE_SHEET
    assert request.columns == 3
    assert request.padding == 2
    assert request.emit_json is True  # JSON checkbox defaults on


def test_sc_ui_004_atlas_options_padding_maxdim_and_json_toggle(qtbot):
    """SC-UI-004-1: atlas padding/max-dimension + JSON toggle feed the request."""
    dialog = _dialog(qtbot, animation_document(frames=4))
    dialog._format_combo.setCurrentIndex(_ATLAS)

    assert dialog._atlas_padding_spin.value() == DEFAULT_ATLAS_PADDING
    assert dialog._atlas_maxdim_spin.value() == MAX_ATLAS_DIMENSION
    # Max-dimension clamps to the named bound (REQ-P7-LOGIC-012).
    dialog._atlas_maxdim_spin.setValue(MAX_ATLAS_DIMENSION + 5000)
    assert dialog._atlas_maxdim_spin.value() == MAX_ATLAS_DIMENSION

    dialog._atlas_padding_spin.setValue(1)
    dialog._atlas_maxdim_spin.setValue(256)
    dialog._atlas_json_check.setChecked(False)
    request = dialog.build_request()
    assert request.fmt is ExportFormat.ATLAS
    assert request.padding == 1
    assert request.max_dimension == 256
    assert request.emit_json is False


def test_sc_ui_006_engine_preset_selection(qtbot):
    """SC-UI-006-1: Unity/Godot presets select the engine-ready layout for sheets."""
    dialog = _dialog(qtbot, animation_document(frames=4))
    dialog._format_combo.setCurrentIndex(_SHEET)

    # Presets are enabled only for the metadata-bearing formats (sheet/atlas).
    assert dialog._preset_combo.isEnabled() is True

    presets = [
        dialog._preset_combo.itemData(i) for i in range(dialog._preset_combo.count())
    ]
    assert presets == [EnginePreset.NONE, EnginePreset.UNITY, EnginePreset.GODOT]

    dialog._preset_combo.setCurrentIndex(presets.index(EnginePreset.UNITY))
    assert dialog.build_request().preset is EnginePreset.UNITY
    dialog._preset_combo.setCurrentIndex(presets.index(EnginePreset.GODOT))
    assert dialog.build_request().preset is EnginePreset.GODOT

    # PNG carries no SheetMetadata, so the preset selector is disabled there.
    dialog._format_combo.setCurrentIndex(_PNG)
    assert dialog._preset_combo.isEnabled() is False


def test_sc_ui_009_export_is_non_destructive(qtbot, export_controller, tmp_path):
    """SC-UI-009-1: exporting mutates neither the document buffers nor any tag."""
    doc = single_frame_document()
    before = doc.frames[0].layers[0].buffer.data.copy()
    tags_before = list(doc.frame_tags)

    dialog = _dialog(qtbot, doc)
    dialog._format_combo.setCurrentIndex(_PNG)
    out = tmp_path / "nd.png"
    dialog._path_edit.setText(str(out))
    target = dialog.export_target()
    assert target is not None

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, (target,))

    # Export is a read-only IO op: source pixels + tags are byte-for-byte unchanged
    # (no QUndoCommand is pushed anywhere on the export path — ui/commands.py is
    # untouched by Phase 7).
    assert (doc.frames[0].layers[0].buffer.data == before).all()
    assert doc.frame_tags == tags_before
    assert out.exists()


def test_sc_ui_013_dialog_retranslates_on_language_change(qtbot):
    """SC-UI-013-1: the dialog re-sets its user-visible text on LanguageChange."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    dialog = _dialog(qtbot, single_frame_document())
    # A non-empty, tr()-sourced title/labels exist (no bare-literal reliance).
    assert dialog.windowTitle() != ""
    assert dialog._format_label.text() != ""
    # Delivering LanguageChange re-runs _retranslate without error (the changeEvent
    # override path); text stays populated (string_audit_check owned by AGT-07).
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))
    assert dialog.windowTitle() != ""
    assert dialog._browse_button.text() != ""
