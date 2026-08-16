"""Batch recolour panel — recolour many targets in one action (REQ-P8-UI-006).

``Batch_Recolour_Panel`` lets the user assemble a recolour **mapping** (an index
remap for indexed buffers, or an RGBA colour remap) and apply it across the
active frame's layers as **one** batch. The mapping is emitted as a single DSL
``batch_recolour`` :class:`~pixelart_creator.logic.macro.Op`; the host dispatches
it through the trusted engine on the off-GUI-thread worker, where
:func:`pixelart_creator.logic.batch_ops.make_batch_recolour_command` composes the
shipped ``palette_ops`` across every target as **one transactional reversible
command** (each per-target output identical to the single equivalent op, and a
per-target failure isolated — REQ-P8-LOGIC-011). The whole batch is one undoable
action (REQ-P8-UI-009); a failure surfaces a graceful error (REQ-P8-UI-008).

Presentation + wiring only (S11): the recolour maths and transactional
composition live entirely in ``logic.batch_ops`` — this panel only gathers the
mapping and relays it. There is **no ``eval``/``exec``** here. Every user-visible
string is ``tr()``-wrapped with a ``changeEvent`` retranslate (REQ-P8-UI-014) and
every control carries an accessible name (REQ-P8-UI-012).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.scripting import OP_BATCH_RECOLOUR
from pixelart_creator.ui.automation_worker import STAGE_COMPLETE, STAGE_RUNNING

#: Combo indices for the mapping mode (module-local UI enumeration).
_MODE_INDEX = 0
_MODE_COLOUR = 1

#: Upper bound for the index spin boxes — the widest palette a buffer can address
#: (a display range for the spin control, not a domain tuning value).
_MAX_INDEX = 255


class Batch_Recolour_Panel(QWidget):
    """Assemble an index / colour remap and apply it as one batch recolour."""

    #: ``(ops, label)`` — the host should dispatch the ``batch_recolour`` op on the
    #: worker as one undoable grouped command (REQ-P8-UI-006/-009).
    automationRequested = Signal(object, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the mode selector, pair editor, pair list and apply control."""
        super().__init__(parent)
        #: Each pair is ``(src, dst)`` — ints for index mode, RGBA tuples for
        #: colour mode. Kept parallel to the visible list.
        self._pairs: List[tuple] = []

        self._mode_label = QLabel(self)
        self._mode_combo = QComboBox(self)
        self._mode_combo.addItem("", _MODE_INDEX)
        self._mode_combo.addItem("", _MODE_COLOUR)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._frame_label = QLabel(self)
        self._frame_spin = QSpinBox(self)
        self._frame_spin.setMinimum(0)
        self._frame_spin.setMaximum(0)

        # Index-mode editor.
        self._src_index = QSpinBox(self)
        self._src_index.setRange(0, _MAX_INDEX)
        self._dst_index = QSpinBox(self)
        self._dst_index.setRange(0, _MAX_INDEX)

        # Colour-mode editor.
        self._src_colour = (0, 0, 0, 255)
        self._dst_colour = (255, 255, 255, 255)
        self._src_colour_button = QPushButton(self)
        self._src_colour_button.clicked.connect(self._pick_src_colour)
        self._dst_colour_button = QPushButton(self)
        self._dst_colour_button.clicked.connect(self._pick_dst_colour)

        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add_pair)
        self._remove_button = QPushButton(self)
        self._remove_button.clicked.connect(self._on_remove_pair)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self._apply_button = QPushButton(self)
        self._apply_button.clicked.connect(self._on_apply)

        # Per-target automation progress (D-06): a dedicated QGroupBox keeps this
        # a visually distinct region from the mapping controls above it (the
        # user's "clear element boundaries" directive) with no widget-level
        # colour override — the box chrome + text render from the app's
        # role-based theme (qss-theming), same as every other control here.
        self._progress_stage_token = ""
        self._progress_group = QGroupBox(self)
        self._progress_status = QLabel(self._progress_group)
        self._progress_bar = QProgressBar(self._progress_group)
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        progress_layout = QVBoxLayout(self._progress_group)
        progress_layout.addWidget(self._progress_status)
        progress_layout.addWidget(self._progress_bar)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self._mode_label)
        mode_row.addWidget(self._mode_combo, 1)
        frame_row = QHBoxLayout()
        frame_row.addWidget(self._frame_label)
        frame_row.addWidget(self._frame_spin, 1)
        index_row = QHBoxLayout()
        index_row.addWidget(self._src_index)
        index_row.addWidget(self._dst_index)
        colour_row = QHBoxLayout()
        colour_row.addWidget(self._src_colour_button)
        colour_row.addWidget(self._dst_colour_button)
        pair_row = QHBoxLayout()
        pair_row.addWidget(self._add_button)
        pair_row.addWidget(self._remove_button)

        layout = QVBoxLayout(self)
        layout.addLayout(mode_row)
        layout.addLayout(frame_row)
        layout.addLayout(index_row)
        layout.addLayout(colour_row)
        layout.addLayout(pair_row)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._apply_button)
        layout.addWidget(self._progress_group)

        self._retranslate()
        self._on_mode_changed()

    # -- automation progress (D-06) ----------------------------------------

    def set_target_progress(self, index: int, count: int, stage: str) -> None:
        """Reflect the automation worker's per-target progress on the bar.

        Bound (by the host) to ``Automation_Controller.targetProgress`` — this
        panel computes no domain value; it only echoes ``index``/``count`` onto
        the bar and maps the plain ``stage`` token to a translated label (S11).
        """
        total = max(1, int(count))
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(max(0, min(int(index), total)))
        self._progress_stage_token = stage
        self._progress_status.setText(self._stage_text(stage))

    def _stage_text(self, stage: str) -> str:
        if stage == STAGE_RUNNING:
            return self.tr("Running…")
        if stage == STAGE_COMPLETE:
            return self.tr("Done")
        return self.tr("Idle")

    # -- context ----------------------------------------------------------

    def set_frame_count(self, count: int) -> None:
        """Bound the frame selector to the active document's frame count."""
        self._frame_spin.setMaximum(max(0, count - 1))

    # -- mode -------------------------------------------------------------

    def _mode(self) -> int:
        return int(self._mode_combo.currentData())

    def _on_mode_changed(self) -> None:
        """Show the editor matching the mapping mode; a mode switch clears pairs."""
        is_index = self._mode() == _MODE_INDEX
        self._src_index.setVisible(is_index)
        self._dst_index.setVisible(is_index)
        self._src_colour_button.setVisible(not is_index)
        self._dst_colour_button.setVisible(not is_index)
        self._pairs.clear()
        self._list.clear()

    # -- colour picking ---------------------------------------------------

    def _pick_src_colour(self) -> None:
        self._src_colour = self._pick_colour(self._src_colour)
        self._refresh_colour_buttons()

    def _pick_dst_colour(self) -> None:
        self._dst_colour = self._pick_colour(self._dst_colour)
        self._refresh_colour_buttons()

    def _pick_colour(self, current: tuple) -> tuple:
        initial = QColor(*current)
        chosen = QColorDialog.getColor(
            initial,
            self,
            self.tr("Pick a colour"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not chosen.isValid():
            return current
        return (chosen.red(), chosen.green(), chosen.blue(), chosen.alpha())

    def _refresh_colour_buttons(self) -> None:
        self._src_colour_button.setText(
            self.tr("From: %1").replace("%1", self._hex(self._src_colour))
        )
        self._dst_colour_button.setText(
            self.tr("To: %1").replace("%1", self._hex(self._dst_colour))
        )

    @staticmethod
    def _hex(colour: tuple) -> str:
        r, g, b, a = colour
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"

    # -- pair editing -----------------------------------------------------

    def _on_add_pair(self) -> None:
        """Append the current src→dst pair to the mapping."""
        pair: tuple
        text = self.tr("%1 → %2")
        if self._mode() == _MODE_INDEX:
            pair = (self._src_index.value(), self._dst_index.value())
            text = text.replace("%1", str(pair[0])).replace("%2", str(pair[1]))
        else:
            pair = (self._src_colour, self._dst_colour)
            text = text.replace("%1", self._hex(pair[0]))
            text = text.replace("%2", self._hex(pair[1]))
        self._pairs.append(pair)
        item = QListWidgetItem(text)
        self._list.addItem(item)

    def _on_remove_pair(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._pairs):
            self._pairs.pop(row)
            self._list.takeItem(row)

    # -- apply ------------------------------------------------------------

    def _on_apply(self) -> None:
        """Build the ``batch_recolour`` op and request the host dispatch it."""
        if not self._pairs:
            return
        params: dict = {"frame_index": self._frame_spin.value()}
        if self._mode() == _MODE_INDEX:
            params["index_map"] = [[int(s), int(d)] for s, d in self._pairs]
        else:
            params["color_map"] = [[list(src), list(dst)] for src, dst in self._pairs]
        op = Op(name=OP_BATCH_RECOLOUR, params=params)
        self.automationRequested.emit([op], self.tr("Batch Recolour"))

    # -- enablement -------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable Apply while an automation run is in flight.

        Also resets the progress bar to idle when a run ends (D-06); while a run
        starts, the bar is left at its pre-run state until the first
        ``targetProgress`` signal arrives (deterministic — no estimate is drawn).
        """
        self._apply_button.setEnabled(not busy)
        if not busy:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(0)
            self._progress_stage_token = ""
            self._progress_status.setText(self._stage_text(""))

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._mode_label.setText(self.tr("Mapping:"))
        self._mode_combo.setItemText(_MODE_INDEX, self.tr("Index remap"))
        self._mode_combo.setItemText(_MODE_COLOUR, self.tr("Colour remap"))
        self._frame_label.setText(self.tr("Frame:"))
        self._add_button.setText(self.tr("Add Pair"))
        self._remove_button.setText(self.tr("Remove"))
        self._apply_button.setText(self.tr("Apply Batch Recolour"))
        self._refresh_colour_buttons()
        self.setAccessibleName(self.tr("Batch recolour"))
        self._mode_combo.setAccessibleName(self.tr("Recolour mapping mode"))
        self._frame_spin.setAccessibleName(self.tr("Target frame index"))
        self._src_index.setAccessibleName(self.tr("Source palette index"))
        self._dst_index.setAccessibleName(self.tr("Destination palette index"))
        self._src_colour_button.setAccessibleName(self.tr("Pick source colour"))
        self._dst_colour_button.setAccessibleName(self.tr("Pick destination colour"))
        self._list.setAccessibleName(self.tr("Recolour mapping pairs"))
        self._add_button.setAccessibleName(self.tr("Add a recolour pair"))
        self._remove_button.setAccessibleName(self.tr("Remove the selected pair"))
        self._apply_button.setAccessibleName(self.tr("Apply the batch recolour"))
        self._progress_group.setTitle(self.tr("Progress"))
        self._progress_bar.setAccessibleName(self.tr("Batch recolour progress"))
        self._progress_status.setText(self._stage_text(self._progress_stage_token))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the batch-recolour strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
