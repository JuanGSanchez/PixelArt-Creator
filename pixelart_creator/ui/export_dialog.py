"""Export dialog — format, per-format options, engine preset, destination.

``Export_Dialog`` is the Qt front-end over the frozen, Qt-free export engine
(``logic/export`` + ``data/export_io``): it lets the user pick a **format**
(PNG / GIF / sprite-sheet / atlas), set that format's **options**, choose an
**engine preset** (Unity / Godot), and pick a portable **destination path**
(REQ-P7-UI-001..004, -006). It builds a frozen :class:`ExportRequest` +
:class:`ExportTarget` and hands them back to the caller — it performs **no**
encoding / layout logic of its own, so the GUI export is byte-identical to the
CLI export (REQ-P7-UI-007). Defaults come from ``logic/constants.py`` and
out-of-range values are bounded by the spin ranges (REQ-P7-UI-003, -012). Every
user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate
(REQ-P7-UI-013); every control carries an accessible name (REQ-P7-UI-011).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.constants import (
    DEFAULT_ATLAS_PADDING,
    DEFAULT_SPRITE_SHEET_COLUMNS,
    GIF_DEFAULT_LOOP_COUNT,
    MAX_ATLAS_DIMENSION,
    MAX_EXPORT_FRAMES,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import (
    EnginePreset,
    ExportFormat,
    ExportRequest,
)
from pixelart_creator.ui.export_worker import ExportTarget

#: Presentation-only spin bounds (UI clamps; the logic layer re-validates, S12).
_MAX_PADDING = 1024
_MAX_LOOP = 65535


class Export_Dialog(QDialog):
    """Collect an :class:`ExportTarget` (format + options + destination path)."""

    def __init__(
        self,
        document: Document,
        parent: Optional[QWidget] = None,
        frame_index: int = 0,
    ) -> None:
        """Build the dialog bound to ``document`` (used only to list frame tags).

        ``frame_index`` is the caller's currently-active frame (CF-18); a PNG
        export request is built against it instead of always frame 0.
        """
        super().__init__(parent)
        self._document = document
        self._frame_index = frame_index

        self._format_combo = QComboBox(self)
        # Value = the frozen ExportFormat enum member (module-local vocabulary).
        self._format_combo.addItem("", ExportFormat.PNG)
        self._format_combo.addItem("", ExportFormat.GIF)
        self._format_combo.addItem("", ExportFormat.SPRITE_SHEET)
        self._format_combo.addItem("", ExportFormat.ATLAS)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)

        self._preset_combo = QComboBox(self)
        self._preset_combo.addItem("", EnginePreset.NONE)
        self._preset_combo.addItem("", EnginePreset.UNITY)
        self._preset_combo.addItem("", EnginePreset.GODOT)

        # Per-format option pages in a stack, indexed by the format combo.
        self._options = QStackedWidget(self)
        self._png_page = self._build_png_page()
        self._gif_page = self._build_gif_page()
        self._sheet_page = self._build_sheet_page()
        self._atlas_page = self._build_atlas_page()
        for page in (
            self._png_page,
            self._gif_page,
            self._sheet_page,
            self._atlas_page,
        ):
            self._options.addWidget(page)

        # Portable destination chooser.
        self._path_edit = QLineEdit(self)
        self._browse_button = QPushButton(self)
        self._browse_button.clicked.connect(self._on_browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(self._browse_button)

        # T7-A (ruling P11-R7, REQ-P11-UI-014): the export flow's own opt-in into
        # the asset library. Unchecked by default so the export's existing default
        # behaviour (write the file, touch nothing else) is unchanged; the window
        # (ui/main_window.py) performs the registration only after this export
        # actually succeeds, never from this dialog (export runs off-thread).
        self._register_check = QCheckBox(self)

        self._format_label = QLabel(self)
        self._preset_label = QLabel(self)
        self._path_label = QLabel(self)

        form = QFormLayout()
        form.addRow(self._format_label, self._format_combo)
        form.addRow(self._preset_label, self._preset_combo)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._options)
        layout.addWidget(self._path_label)
        layout.addLayout(path_row)
        layout.addWidget(self._register_check)
        layout.addWidget(self._buttons)

        self._on_format_changed(0)
        self._retranslate()

    # -- option pages -----------------------------------------------------

    def _build_png_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        self._png_note = QLabel(page)
        self._png_note.setWordWrap(True)
        layout.addWidget(self._png_note)
        return page

    def _build_gif_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        # Frame source: whole document (data=None) or a named tag (data=name).
        self._gif_source_combo = QComboBox(page)
        self._gif_source_label = QLabel(page)
        self._gif_loop_spin = QSpinBox(page)
        self._gif_loop_spin.setRange(0, _MAX_LOOP)
        self._gif_loop_spin.setValue(GIF_DEFAULT_LOOP_COUNT)
        self._gif_loop_label = QLabel(page)
        self._gif_loop_hint = QLabel(page)
        self._gif_loop_hint.setWordWrap(True)
        form.addRow(self._gif_source_label, self._gif_source_combo)
        form.addRow(self._gif_loop_label, self._gif_loop_spin)
        form.addRow(self._gif_loop_hint)
        return page

    def _build_sheet_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self._columns_spin = QSpinBox(page)
        self._columns_spin.setRange(1, MAX_EXPORT_FRAMES)
        self._columns_spin.setValue(DEFAULT_SPRITE_SHEET_COLUMNS)
        self._columns_label = QLabel(page)
        self._sheet_padding_spin = QSpinBox(page)
        self._sheet_padding_spin.setRange(0, _MAX_PADDING)
        self._sheet_padding_spin.setValue(DEFAULT_ATLAS_PADDING)
        self._sheet_padding_label = QLabel(page)
        self._sheet_json_check = QCheckBox(page)
        self._sheet_json_check.setChecked(True)
        form.addRow(self._columns_label, self._columns_spin)
        form.addRow(self._sheet_padding_label, self._sheet_padding_spin)
        form.addRow(self._sheet_json_check)
        return page

    def _build_atlas_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        self._atlas_padding_spin = QSpinBox(page)
        self._atlas_padding_spin.setRange(0, _MAX_PADDING)
        self._atlas_padding_spin.setValue(DEFAULT_ATLAS_PADDING)
        self._atlas_padding_label = QLabel(page)
        self._atlas_maxdim_spin = QSpinBox(page)
        self._atlas_maxdim_spin.setRange(1, MAX_ATLAS_DIMENSION)
        self._atlas_maxdim_spin.setValue(MAX_ATLAS_DIMENSION)
        self._atlas_maxdim_label = QLabel(page)
        self._atlas_json_check = QCheckBox(page)
        self._atlas_json_check.setChecked(True)
        form.addRow(self._atlas_padding_label, self._atlas_padding_spin)
        form.addRow(self._atlas_maxdim_label, self._atlas_maxdim_spin)
        form.addRow(self._atlas_json_check)
        return page

    # -- public API -------------------------------------------------------

    def current_format(self) -> ExportFormat:
        """Return the selected :class:`ExportFormat`."""
        return self._format_combo.currentData()

    def build_request(self) -> ExportRequest:
        """Build the frozen :class:`ExportRequest` from the current selections.

        The engine preset only affects sprite-sheet / atlas metadata, so it is
        applied only for those formats (it is a no-op for PNG / GIF, which carry
        no ``SheetMetadata``).
        """
        fmt = self.current_format()
        if fmt is ExportFormat.GIF:
            return ExportRequest(
                fmt=fmt,
                loop=self._gif_loop_spin.value(),
                tag=self._gif_source_combo.currentData(),
            )
        if fmt is ExportFormat.SPRITE_SHEET:
            return ExportRequest(
                fmt=fmt,
                preset=self._preset_combo.currentData(),
                columns=self._columns_spin.value(),
                padding=self._sheet_padding_spin.value(),
                emit_json=self._sheet_json_check.isChecked(),
            )
        if fmt is ExportFormat.ATLAS:
            return ExportRequest(
                fmt=fmt,
                preset=self._preset_combo.currentData(),
                padding=self._atlas_padding_spin.value(),
                max_dimension=self._atlas_maxdim_spin.value(),
                emit_json=self._atlas_json_check.isChecked(),
            )
        return ExportRequest(fmt=fmt, frame_index=self._frame_index)

    def destination_path(self) -> str:
        """Return the chosen destination path (trimmed; may be empty)."""
        return self._path_edit.text().strip()

    def export_target(self) -> Optional[ExportTarget]:
        """Return the configured :class:`ExportTarget`, or ``None`` if no path."""
        path = self.destination_path()
        if not path:
            return None
        request = self.build_request()
        label = (
            self.tr("%1 → %2")
            .replace("%1", self._format_combo.currentText())
            .replace("%2", Path(path).name)
        )
        return ExportTarget(request=request, out_path=path, label=label)

    def register_on_export(self) -> bool:
        """Return whether the user opted to also add this export to the library.

        REQ-P11-UI-014, T7-A: calling this is the only way the caller learns
        the opt-in was taken — the dialog itself performs no registration.
        """
        return self._register_check.isChecked()

    # -- slots ------------------------------------------------------------

    def _on_format_changed(self, index: int) -> None:
        """Show the matching option page and enable presets only for sheet/atlas."""
        self._options.setCurrentIndex(index)
        fmt = self._format_combo.currentData()
        presets_apply = fmt in (ExportFormat.SPRITE_SHEET, ExportFormat.ATLAS)
        self._preset_combo.setEnabled(presets_apply)
        if fmt is ExportFormat.GIF:
            self._reload_frame_sources()

    def _reload_frame_sources(self) -> None:
        """Populate the GIF frame-source combo: whole document + each frame tag."""
        self._gif_source_combo.clear()
        self._gif_source_combo.addItem(self.tr("Whole document"), None)
        for tag in self._document.frame_tags:
            self._gif_source_combo.addItem(tag.name, tag.name)

    def _on_browse(self) -> None:
        """Prompt for a portable destination path with a per-format filter."""
        fmt = self.current_format()
        if fmt is ExportFormat.GIF:
            file_filter = self.tr("Animated GIF (*.gif)")
        else:
            file_filter = self.tr("PNG image (*.png)")
        path, _selected = QFileDialog.getSaveFileName(
            self, self.tr("Export To"), self._path_edit.text(), file_filter
        )
        if path:
            self._path_edit.setText(path)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Export"))
        self._format_label.setText(self.tr("Format"))
        self._preset_label.setText(self.tr("Engine preset"))
        self._path_label.setText(self.tr("Destination"))
        self._browse_button.setText(self.tr("Browse…"))
        self._register_check.setText(self.tr("Also add to the asset library"))

        self._format_combo.setItemText(0, self.tr("PNG image"))
        self._format_combo.setItemText(1, self.tr("Animated GIF"))
        self._format_combo.setItemText(2, self.tr("Sprite sheet"))
        self._format_combo.setItemText(3, self.tr("Texture atlas"))
        self._preset_combo.setItemText(0, self.tr("None"))
        self._preset_combo.setItemText(1, self.tr("Unity"))
        self._preset_combo.setItemText(2, self.tr("Godot"))

        self._png_note.setText(
            self.tr("Exports the first frame as a flattened PNG image.")
        )
        self._gif_source_label.setText(self.tr("Frames"))
        self._gif_loop_label.setText(self.tr("Loop count"))
        self._gif_loop_hint.setText(self.tr("Loop count (0 = loop forever)."))
        self._columns_label.setText(self.tr("Columns"))
        self._sheet_padding_label.setText(self.tr("Padding (px)"))
        self._sheet_json_check.setText(self.tr("Write JSON metadata"))
        self._atlas_padding_label.setText(self.tr("Padding (px)"))
        self._atlas_maxdim_label.setText(self.tr("Max dimension (px)"))
        self._atlas_json_check.setText(self.tr("Write JSON metadata"))

        # Accessible names on every interactive control (REQ-P7-UI-011).
        self._format_combo.setAccessibleName(self.tr("Export format"))
        self._preset_combo.setAccessibleName(self.tr("Engine preset"))
        self._path_edit.setAccessibleName(self.tr("Destination path"))
        self._browse_button.setAccessibleName(self.tr("Browse for destination"))
        self._register_check.setAccessibleName(
            self.tr("Also add this export to the asset library")
        )
        self._gif_source_combo.setAccessibleName(self.tr("GIF frame source"))
        self._gif_loop_spin.setAccessibleName(self.tr("GIF loop count"))
        self._columns_spin.setAccessibleName(self.tr("Sprite-sheet columns"))
        self._sheet_padding_spin.setAccessibleName(self.tr("Sprite-sheet padding"))
        self._sheet_json_check.setAccessibleName(self.tr("Write sprite-sheet JSON"))
        self._atlas_padding_spin.setAccessibleName(self.tr("Atlas padding"))
        self._atlas_maxdim_spin.setAccessibleName(self.tr("Atlas max dimension"))
        self._atlas_json_check.setAccessibleName(self.tr("Write atlas JSON"))
        # Refresh the (dynamic) frame-source list so its default label retranslates.
        if self.current_format() is ExportFormat.GIF:
            self._reload_frame_sources()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the export dialog strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
