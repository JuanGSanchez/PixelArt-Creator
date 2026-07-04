"""Procedural-generation panel — seeded, deterministic content (REQ-P8-UI-007).

``Procgen_Panel`` lets the user choose a generation **algorithm**, a **seed** and
region / noise parameters, and generate content into the active document. The
request is emitted as a single DSL ``procgen``
:class:`~pixelart_creator.logic.macro.Op` carrying the seed; the host dispatches
it through the trusted engine on the off-GUI-thread worker, where
:func:`pixelart_creator.logic.procgen.make_procgen_command` writes the content
through a reversible command (PB-1) — the **same seed + parameters always yields
the same output** (REQ-P8-LOGIC-012) and the generation is one undoable action
(REQ-P8-UI-009). An out-of-range size is rejected by the engine and surfaces a
graceful error (REQ-P8-UI-008); the size spin boxes are also clamped to
``MAX_PROCGEN_DIMENSION`` so the control cannot request an unbuildable size.

Presentation + wiring only (S11): every generator's maths lives in
``logic.procgen`` — this panel only gathers parameters and relays them. There is
**no ``eval``/``exec``** here. Every user-visible string is ``tr()``-wrapped with
a ``changeEvent`` retranslate (REQ-P8-UI-014) and every control carries an
accessible name + unit (REQ-P8-UI-012).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.constants import (
    DEFAULT_PROCGEN_SEED,
    MAX_PROCGEN_DIMENSION,
)
from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.procgen import ALGORITHMS
from pixelart_creator.logic.scripting import OP_PROCGEN

#: Largest seed the spin box offers (a display range for the control; the engine
#: accepts any int seed). 2**31 - 1 keeps the value in the Qt spin box's int range.
_MAX_SEED = 2**31 - 1


class Procgen_Panel(QWidget):
    """Choose an algorithm + seed + region and generate content (undoable)."""

    #: ``(ops, label)`` — the host should dispatch the ``procgen`` op on the worker
    #: as one undoable grouped command (REQ-P8-UI-007/-009).
    automationRequested = Signal(object, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the algorithm / seed / region / noise parameter form."""
        super().__init__(parent)

        self._algorithm_combo = QComboBox(self)
        for algorithm in ALGORITHMS:
            # The id is the engine's algorithm token (data); the visible label is
            # translated in _retranslate. Store the token in the item data.
            self._algorithm_combo.addItem(algorithm, algorithm)

        self._seed_spin = QSpinBox(self)
        self._seed_spin.setRange(0, _MAX_SEED)
        self._seed_spin.setValue(int(DEFAULT_PROCGEN_SEED))

        self._width_spin = QSpinBox(self)
        self._width_spin.setRange(1, int(MAX_PROCGEN_DIMENSION))
        self._width_spin.setValue(64)
        self._width_spin.setSuffix(self.tr(" px"))
        self._height_spin = QSpinBox(self)
        self._height_spin.setRange(1, int(MAX_PROCGEN_DIMENSION))
        self._height_spin.setValue(64)
        self._height_spin.setSuffix(self.tr(" px"))

        self._frequency_spin = QSpinBox(self)
        self._frequency_spin.setRange(1, 256)
        self._frequency_spin.setValue(4)
        self._octaves_spin = QSpinBox(self)
        self._octaves_spin.setRange(1, 12)
        self._octaves_spin.setValue(1)

        # Explicit label widgets (retranslated below) keep each form row's caption
        # addressable without QFormLayout.labelForField's loose QWidget return type.
        self._algorithm_label = QLabel(self)
        self._seed_label = QLabel(self)
        self._width_label = QLabel(self)
        self._height_label = QLabel(self)
        self._frequency_label = QLabel(self)
        self._octaves_label = QLabel(self)

        self._form = QFormLayout()
        self._form.addRow(self._algorithm_label, self._algorithm_combo)
        self._form.addRow(self._seed_label, self._seed_spin)
        self._form.addRow(self._width_label, self._width_spin)
        self._form.addRow(self._height_label, self._height_spin)
        self._form.addRow(self._frequency_label, self._frequency_spin)
        self._form.addRow(self._octaves_label, self._octaves_spin)

        self._generate_button = QPushButton(self)
        self._generate_button.clicked.connect(self._on_generate)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addWidget(self._generate_button)

        self._retranslate()

    # -- generate ---------------------------------------------------------

    def _on_generate(self) -> None:
        """Build the ``procgen`` op (with its seed) and request the host run it."""
        algorithm = self._algorithm_combo.currentData()
        params: dict = {
            "algorithm": algorithm,
            "width": self._width_spin.value(),
            "height": self._height_spin.value(),
            "frequency": self._frequency_spin.value(),
            "octaves": self._octaves_spin.value(),
        }
        op = Op(name=OP_PROCGEN, params=params, seed=self._seed_spin.value())
        self.automationRequested.emit([op], self.tr("Procedural Generation"))

    # -- enablement -------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable Generate while an automation run is in flight."""
        self._generate_button.setEnabled(not busy)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        # Human-readable, translated labels mapped to each engine algorithm token.
        labels = {
            "value_noise": self.tr("Value noise"),
            "gradient_noise": self.tr("Gradient noise"),
            "opensimplex": self.tr("OpenSimplex noise"),
            "cellular_automata": self.tr("Cellular automata"),
            "dithered_gradient": self.tr("Dithered gradient"),
        }
        for row in range(self._algorithm_combo.count()):
            token = self._algorithm_combo.itemData(row)
            self._algorithm_combo.setItemText(row, labels.get(token, token))

        self._algorithm_label.setText(self.tr("Algorithm"))
        self._seed_label.setText(self.tr("Seed"))
        self._width_label.setText(self.tr("Width"))
        self._height_label.setText(self.tr("Height"))
        self._frequency_label.setText(self.tr("Frequency"))
        self._octaves_label.setText(self.tr("Octaves"))
        self._width_spin.setSuffix(self.tr(" px"))
        self._height_spin.setSuffix(self.tr(" px"))
        self._generate_button.setText(self.tr("Generate"))

        self.setAccessibleName(self.tr("Procedural generation"))
        self._algorithm_combo.setAccessibleName(self.tr("Generation algorithm"))
        self._seed_spin.setAccessibleName(self.tr("Random seed"))
        self._width_spin.setAccessibleName(self.tr("Output width in pixels"))
        self._height_spin.setAccessibleName(self.tr("Output height in pixels"))
        self._frequency_spin.setAccessibleName(self.tr("Noise base frequency"))
        self._octaves_spin.setAccessibleName(self.tr("Noise octaves"))
        self._generate_button.setAccessibleName(self.tr("Generate content"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the procgen strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
