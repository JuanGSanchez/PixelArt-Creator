"""Hardware palette-constraint presets (REQ-P3-UI-009).

``Palette_Constraint_Panel`` offers NES / Game Boy preset buttons that constrain
the active buffer (or the active selection) onto the hardware reference palette as
**one** undoable command. The reference palettes come from
:mod:`pixelart_creator.logic.hardware_palette` and the mapping from
:func:`pixelart_creator.logic.quantize.make_constraint_command` — all maths live in
``logic/`` (Article I / S11); this panel only chooses a preset, calls the builder,
and wraps the returned reversible command in one
:class:`~pixelart_creator.ui.commands.LogicCommand` (SC-U009-1/-2). It binds to the
shell through a supplied context provider so it never reaches into document state
itself. Strings are ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (F5); the presets are keyboard-reachable and
legible in both themes.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from pixelart_creator.logic.palette import Palette

#: Preset identifiers routed back to the shell (which owns the logic call).
PRESET_NES = "nes"
PRESET_GAME_BOY = "game_boy"


class Palette_Constraint_Panel(QWidget):
    """NES / Game Boy constraint preset buttons."""

    #: Emitted with a preset id (``PRESET_NES`` / ``PRESET_GAME_BOY``) on click.
    constraintRequested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the preset buttons."""
        super().__init__(parent)
        self._title = QLabel(self)
        self._nes_button = QPushButton(self)
        self._nes_button.clicked.connect(
            lambda: self.constraintRequested.emit(PRESET_NES)
        )
        self._gb_button = QPushButton(self)
        self._gb_button.clicked.connect(
            lambda: self.constraintRequested.emit(PRESET_GAME_BOY)
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._nes_button)
        layout.addWidget(self._gb_button)
        layout.addStretch(1)
        self._retranslate()

    def _retranslate(self) -> None:
        self._title.setText(self.tr("Constrain to Hardware Palette"))
        self.setAccessibleName(self.tr("Palette constraint presets"))
        self._nes_button.setText(self.tr("Constrain to NES"))
        self._gb_button.setText(self.tr("Constrain to Game Boy"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


def preset_palette(preset: str) -> Optional[Palette]:
    """Return the reference :class:`Palette` for ``preset`` (or ``None``).

    Thin lookup into :mod:`pixelart_creator.logic.hardware_palette`; kept here so
    the shell resolves a preset id to its logic palette without embedding the
    mapping in the widget's signal wiring.
    """
    from pixelart_creator.logic.hardware_palette import game_boy_palette, nes_palette

    providers: dict[str, Callable[[], Palette]] = {
        PRESET_NES: nes_palette,
        PRESET_GAME_BOY: game_boy_palette,
    }
    provider = providers.get(preset)
    return provider() if provider is not None else None


__all__ = [
    "Palette_Constraint_Panel",
    "preset_palette",
    "PRESET_NES",
    "PRESET_GAME_BOY",
]
