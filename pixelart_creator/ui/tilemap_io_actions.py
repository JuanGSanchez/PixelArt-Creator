# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tiled JSON import/export UI actions (part of Phase 6).

Thin Qt front-end over ``data/tiled_io``: a **file dialog** + a defensive call
that surfaces the typed :class:`~pixelart_creator.data.project_io.ProjectIOError`
(zstd / ``.tsx`` / out-of-range gid / malformed JSON) as a user-facing
:class:`QMessageBox` — **never** a crash (REQ-P6-UI-011/-012, SC-UI-012-1). All
serialisation, validation and round-trip logic lives in ``data/tiled_io`` (Qt-free,
Article I / S11); this module only chooses a portable path and reports errors.
Dialog / error strings are ``tr()``-wrapped so the localisation layer can extract them
(REQ-P6-UI-017).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.data.tiled_io import read_tiled_json, write_tiled_json
from pixelart_creator.logic.tilemap import Tilemap

#: Tiled JSON file filter (format identifier, not a translated string).
_TILED_FILTER = "Tiled JSON (*.tmj *.json)"


def export_tilemap_dialog(parent: QWidget, tilemap: Tilemap) -> Optional[str]:
    """Prompt for a path and export ``tilemap`` to Tiled JSON (REQ-P6-UI-011).

    Returns the written path on success, or ``None`` if cancelled or on a
    reported error (surfaced as a warning box, never a crash).
    """
    path, _selected = QFileDialog.getSaveFileName(
        parent,
        QCoreApplication.translate("tilemap_io", "Export Tiled Map"),
        "",
        _TILED_FILTER,
    )
    if not path:
        return None
    try:
        written = write_tiled_json(path, tilemap)
    except (ProjectIOError, OSError) as exc:
        QMessageBox.warning(
            parent,
            QCoreApplication.translate("tilemap_io", "Export failed"),
            QCoreApplication.translate(
                "tilemap_io", "Could not export the map: %1"
            ).replace("%1", str(exc)),
        )
        return None
    return str(written)


def import_tilemap_dialog(parent: QWidget) -> Optional[Tilemap]:
    """Prompt for a Tiled JSON file and import it (REQ-P6-UI-012).

    Returns the reconstructed :class:`Tilemap` on success, or ``None`` if
    cancelled or on a reported error. A malformed / unsupported file surfaces a
    warning box (defensive load, SC-UI-012-1) — never a crash.
    """
    path, _selected = QFileDialog.getOpenFileName(
        parent,
        QCoreApplication.translate("tilemap_io", "Import Tiled Map"),
        "",
        _TILED_FILTER,
    )
    if not path:
        return None
    try:
        return read_tiled_json(path)
    except (ProjectIOError, OSError) as exc:
        QMessageBox.warning(
            parent,
            QCoreApplication.translate("tilemap_io", "Import failed"),
            QCoreApplication.translate(
                "tilemap_io", "Could not import the map: %1"
            ).replace("%1", str(exc)),
        )
        return None
