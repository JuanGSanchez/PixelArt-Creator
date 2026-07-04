"""Script runner panel — run a data-driven DSL script (REQ-P8-UI-004).

``Script_Runner_Panel`` lets a power user author a **data-driven DSL script** — a
JSON array of ``{"name": ..., "params": {...}, "seed": ...}`` steps — and run it
against the active document. The script is **data, never code** (Article VII):
this panel only parses the JSON text into
:class:`~pixelart_creator.logic.macro.Op` objects and hands them to the host,
which dispatches them through the trusted, allow-listed
:func:`pixelart_creator.logic.scripting.dispatch` on the off-GUI-thread worker;
scripted edits appear as **undoable commands** (REQ-P8-UI-009) and a failing or
unknown-op script surfaces a **graceful error** (REQ-P8-UI-008). There is **no
``eval``/``exec``** — ``json.loads`` parses inert data and the dispatcher rejects
any op-name not in its registry.

Presentation + wiring only (S11): no engine logic lives here. Every user-visible
string is ``tr()``-wrapped with a ``changeEvent`` retranslate (REQ-P8-UI-014) and
every control carries an accessible name (REQ-P8-UI-012).
"""

from __future__ import annotations

import json
from typing import List, Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.macro import Op

#: A compact, copy-pasteable example so the empty editor is self-documenting.
_PLACEHOLDER = (
    "[\n"
    '  {"name": "procgen",\n'
    '   "params": {"algorithm": "value_noise", "width": 64, "height": 64},\n'
    '   "seed": 7}\n'
    "]"
)


class Script_Runner_Panel(QWidget):
    """Author + run a JSON DSL script against the active document."""

    #: ``(ops, label)`` — the host should dispatch these DSL ops on the worker as
    #: one undoable grouped command (REQ-P8-UI-004/-009).
    automationRequested = Signal(object, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the script editor + run control with an example placeholder."""
        super().__init__(parent)

        self._label = QLabel(self)
        self._editor = QPlainTextEdit(self)
        self._editor.setPlaceholderText(_PLACEHOLDER)
        self._run_button = QPushButton(self)
        self._run_button.clicked.connect(self._on_run)

        run_row = QHBoxLayout()
        run_row.addStretch(1)
        run_row.addWidget(self._run_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._editor, 1)
        layout.addLayout(run_row)

        self._retranslate()

    # -- run --------------------------------------------------------------

    def _parse_ops(self, text: str) -> List[Op]:
        """Parse the JSON DSL text into :class:`Op` steps (inert data, no exec).

        Raises:
            ValueError: On invalid JSON or a malformed step (surfaced as a
                user-facing error; the trusted dispatcher performs the
                authoritative op-name / param validation).
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(self.tr("Invalid JSON: %1").replace("%1", str(exc)))
        if not isinstance(data, list):
            raise ValueError(self.tr("A script must be a JSON array of steps."))
        ops: List[Op] = []
        for entry in data:
            if not isinstance(entry, dict) or "name" not in entry:
                raise ValueError(
                    self.tr("Each step needs a 'name' and optional 'params'/'seed'.")
                )
            name = entry.get("name")
            params = entry.get("params", {})
            seed = entry.get("seed")
            if not isinstance(name, str):
                raise ValueError(self.tr("Step 'name' must be a string."))
            if not isinstance(params, dict):
                raise ValueError(self.tr("Step 'params' must be an object."))
            ops.append(Op(name=name, params=params, seed=seed))
        return ops

    def _on_run(self) -> None:
        """Parse the editor text and request the host dispatch it (undoable)."""
        text = self._editor.toPlainText().strip()
        if not text:
            return
        try:
            ops = self._parse_ops(text)
        except ValueError as exc:
            QMessageBox.warning(self, self.tr("Script Error"), str(exc))
            return
        if not ops:
            return
        self.automationRequested.emit(ops, self.tr("Run Script"))

    # -- enablement -------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable Run while an automation run is in flight."""
        self._run_button.setEnabled(not busy)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._label.setText(self.tr("DSL script (JSON list of steps):"))
        self._run_button.setText(self.tr("Run Script"))
        self.setAccessibleName(self.tr("Script runner"))
        self._editor.setAccessibleName(self.tr("Script source"))
        self._run_button.setAccessibleName(self.tr("Run the script"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the script-runner strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
