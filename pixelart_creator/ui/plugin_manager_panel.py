# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Plugin manager panel — deny-by-default, consent-gated (REQ-P8-UI-005, -008).

``Plugin_Manager_Panel`` surfaces the frozen, trusted-with-consent plugin host
(:mod:`pixelart_creator.logic.plugins`): it **lists** discovered plugins
(discovery is inert — no load, no run), lets the user **add a plugin manifest**
(loaded defensively, ``eval``-free, via
:func:`pixelart_creator.data.macro_io.load_manifest`), **displays the declared
capabilities / permissions BEFORE the plugin is enabled**, and enables a plugin
**only** on an explicit consent action (deny-by-default, **no auto-run** —
REQ-P8-LOGIC-008/-009/-010). Enabling grants exactly the plugin's declared
capabilities and hands it the capability object that is its ONLY surface (it
cannot reach ``ui/`` / the filesystem / the network, and cannot mutate outside a
reversible command); a denied or failed enable surfaces a **user-facing error**,
never a silent boundary crossing (REQ-P8-UI-008). Enable / disable is
view/session state and pushes **no** undo command (CL-8).

Presentation + wiring only (S11): the sandbox, capability enforcement and
manifest validation all live in ``logic.plugins`` — this panel only shows the
declared permissions and relays the user's consent. There is **no
``eval``/``exec``** here. Every user-visible string is ``tr()``-wrapped with a
``changeEvent`` retranslate (REQ-P8-UI-014) and every control carries an
accessible name (REQ-P8-UI-012).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.macro_io import MacroIOError, load_manifest
from pixelart_creator.logic.plugins import (
    PluginError,
    PluginHandle,
    PluginManifest,
    discover,
    enable,
)


class Plugin_Manager_Panel(QWidget):
    """List, inspect, enable (with consent) and disable plugins."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the plugin list + permission display + install/enable controls."""
        super().__init__(parent)
        #: Enabled plugin handles keyed by plugin name (view/session state).
        self._handles: Dict[str, PluginHandle] = {}

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.currentItemChanged.connect(self._on_selection_changed)

        self._permissions_title = QLabel(self)
        self._permissions = QLabel(self)
        self._permissions.setWordWrap(True)
        self._permissions.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self._refresh_button = QPushButton(self)
        self._refresh_button.clicked.connect(self._on_refresh)
        self._install_button = QPushButton(self)
        self._install_button.clicked.connect(self._on_install)
        self._enable_button = QPushButton(self)
        self._enable_button.clicked.connect(self._on_enable)
        self._disable_button = QPushButton(self)
        self._disable_button.clicked.connect(self._on_disable)

        top_row = QHBoxLayout()
        top_row.addWidget(self._refresh_button)
        top_row.addWidget(self._install_button)
        action_row = QHBoxLayout()
        action_row.addWidget(self._enable_button)
        action_row.addWidget(self._disable_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._permissions_title)
        layout.addWidget(self._permissions)
        layout.addLayout(action_row)

        self._retranslate()
        self._on_refresh()
        self._update_permissions()

    # -- discovery / install (inert; no auto-run) -------------------------

    def _on_refresh(self) -> None:
        """List discovered plugins inertly (no ``.load()``, no run — LOGIC-008).

        Preserves any manifests the user already installed (they carry declared
        capabilities); discovery only contributes inert descriptors whose
        capabilities are empty until their manifest is installed.
        """
        installed: Dict[str, PluginManifest] = {}
        for row in range(self._list.count()):
            manifest = self._manifest_at(row)
            if manifest is not None and manifest.capabilities:
                installed[manifest.name] = manifest
        self._list.clear()
        for manifest in installed.values():
            self._add_manifest_item(manifest)
        for manifest in discover():
            if manifest.name not in installed:
                self._add_manifest_item(manifest)
        self._update_permissions()

    def _on_install(self) -> None:
        """Add a plugin by loading its manifest defensively (eval-free, IO-3).

        A malformed / unsupported-version manifest raises
        :class:`MacroIOError` / :class:`PluginError` and is reported — never
        executed (REQ-P8-UI-008).
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Add Plugin Manifest"),
            "",
            self.tr("Manifest files (*.json)"),
        )
        if not path:
            return
        try:
            manifest = load_manifest(path)
        except (MacroIOError, PluginError, OSError) as exc:
            QMessageBox.warning(self, self.tr("Install Failed"), str(exc))
            return
        self._add_manifest_item(manifest, source=Path(path).name)
        self._update_permissions()

    # -- consent-gated enable / disable (view state, no undo — CL-8) ------

    def _on_enable(self) -> None:
        """Enable the selected plugin after explicit, informed consent.

        Shows the declared capabilities and requires the user to confirm; on
        confirmation, grants exactly those capabilities (deny-by-default) via
        ``logic.plugins.enable`` with **no** auto-run activation. A denied / failed
        enable surfaces a user-facing error (REQ-P8-UI-008).
        """
        manifest = self._selected_manifest()
        if manifest is None:
            return
        if manifest.name in self._handles:
            return
        if not manifest.capabilities:
            QMessageBox.information(
                self,
                self.tr("No Manifest"),
                self.tr(
                    "This plugin has no loaded manifest. Use Add Manifest to load "
                    "its declared permissions before enabling it."
                ),
            )
            return
        confirmed = QMessageBox.question(
            self,
            self.tr("Enable Plugin"),
            self.tr(
                "Enable %1 and grant it these permissions?\n\n%2\n\n"
                "The plugin runs sandboxed and can only edit through reversible "
                "commands. It cannot reach the UI, filesystem, or network."
            )
            .replace("%1", manifest.name)
            .replace("%2", self._format_capabilities(manifest)),
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            handle = enable(manifest, set(manifest.capabilities))
        except PluginError as exc:
            QMessageBox.warning(self, self.tr("Enable Failed"), str(exc))
            return
        self._handles[manifest.name] = handle
        self._mark_status()
        self._update_permissions()

    def _on_disable(self) -> None:
        """Disable the selected plugin (unregisters its ops; view state, no undo)."""
        manifest = self._selected_manifest()
        if manifest is None:
            return
        handle = self._handles.pop(manifest.name, None)
        if handle is not None:
            handle.disable()
        self._mark_status()
        self._update_permissions()

    # -- list helpers -----------------------------------------------------

    def _add_manifest_item(self, manifest: PluginManifest, source: str = "") -> None:
        item = QListWidgetItem(self._row_label(manifest, source))
        item.setData(Qt.ItemDataRole.UserRole, manifest)
        self._list.addItem(item)
        self._list.setCurrentItem(item)

    def _row_label(self, manifest: PluginManifest, source: str = "") -> str:
        enabled = manifest.name in self._handles
        state = self.tr("enabled") if enabled else self.tr("disabled")
        base = self.tr("%1 v%2 — %3")
        base = base.replace("%1", manifest.name)
        base = base.replace("%2", manifest.version)
        return base.replace("%3", state)

    def _manifest_at(self, row: int) -> Optional[PluginManifest]:
        item = self._list.item(row)
        if item is None:
            return None
        manifest = item.data(Qt.ItemDataRole.UserRole)
        return manifest if isinstance(manifest, PluginManifest) else None

    def _selected_manifest(self) -> Optional[PluginManifest]:
        item = self._list.currentItem()
        if item is None:
            return None
        manifest = item.data(Qt.ItemDataRole.UserRole)
        return manifest if isinstance(manifest, PluginManifest) else None

    def _mark_status(self) -> None:
        """Refresh every row's enabled/disabled label."""
        for row in range(self._list.count()):
            manifest = self._manifest_at(row)
            item = self._list.item(row)
            if manifest is not None and item is not None:
                item.setText(self._row_label(manifest))

    def _format_capabilities(self, manifest: PluginManifest) -> str:
        if not manifest.capabilities:
            return self.tr("(no manifest loaded — permissions unknown)")
        return "\n".join(f"• {cap.value}" for cap in manifest.capabilities)

    # -- permission display (BEFORE enable — REQ-P8-UI-005) ---------------

    def _on_selection_changed(self) -> None:
        self._update_permissions()

    def _update_permissions(self) -> None:
        manifest = self._selected_manifest()
        enabled = manifest is not None and manifest.name in self._handles
        if manifest is None:
            self._permissions.setText(
                self.tr("Select a plugin to view its permissions.")
            )
        else:
            self._permissions.setText(self._format_capabilities(manifest))
        self._enable_button.setEnabled(manifest is not None and not enabled)
        self._disable_button.setEnabled(enabled)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._refresh_button.setText(self.tr("Refresh"))
        self._install_button.setText(self.tr("Add Manifest…"))
        self._enable_button.setText(self.tr("Enable"))
        self._disable_button.setText(self.tr("Disable"))
        self._permissions_title.setText(self.tr("Declared permissions:"))
        self.setAccessibleName(self.tr("Plugin manager"))
        self._list.setAccessibleName(self.tr("Discovered and installed plugins"))
        self._permissions.setAccessibleName(self.tr("Selected plugin permissions"))
        self._refresh_button.setAccessibleName(self.tr("Refresh the plugin list"))
        self._install_button.setAccessibleName(self.tr("Add a plugin manifest"))
        self._enable_button.setAccessibleName(self.tr("Enable the selected plugin"))
        self._disable_button.setAccessibleName(self.tr("Disable the selected plugin"))
        self._mark_status()
        self._update_permissions()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the plugin-manager strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
