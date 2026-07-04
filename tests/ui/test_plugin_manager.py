"""Plugin manager — SC-UI-005-1 [SEC-facing] (REQ-P8-UI-005, -008).

The paramount plugin-consent security test (Article VII): discovery is inert (no
auto-enable / no auto-run); a plugin's declared capabilities are DISPLAYED before
enabling; enabling requires EXPLICIT consent and grants EXACTLY the declared
capabilities with no auto-run activation (deny-by-default); a non-consented /
ungranted capability is DENIED; and a malformed manifest surfaces a user-facing
error, never executed. A bypass here is a ship blocker. Headless; both themes.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

import pixelart_creator.ui.plugin_manager_panel as plugin_manager_panel
from pixelart_creator.logic import plugins
from pixelart_creator.logic.plugins import Capability, PluginError, PluginManifest
from pixelart_creator.logic.scripting import ParamSchema
from pixelart_creator.ui.main_window import Main_Window
from tests.ui._automation_helpers import write_malformed_manifest, write_manifest


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _install(panel, monkeypatch, path) -> None:
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )
    panel._on_install()


def test_sc_ui_005_discovery_is_inert_nothing_auto_enabled(qtbot):
    """SC-UI-005-1: a fresh plugin manager has enabled/run NOTHING (deny-by-default)."""
    win = _window(qtbot)
    assert win._plugin_manager_panel._handles == {}
    assert plugins.loaded_count() == 0


def test_sc_ui_005_declared_permissions_shown_before_enable(
    qtbot, monkeypatch, tmp_path
):
    """SC-UI-005-1: an installed plugin's declared permissions are shown before enable."""
    win = _window(qtbot)
    panel = win._plugin_manager_panel
    manifest = write_manifest(
        tmp_path / "m.json", capabilities=["read_document", "register_command"]
    )
    _install(panel, monkeypatch, manifest)

    text = panel._permissions.text()
    assert "read_document" in text and "register_command" in text
    assert panel._enable_button.isEnabled()
    # Merely viewing the permissions does NOT enable/run the plugin.
    assert panel._handles == {}
    assert plugins.loaded_count() == 0


def test_sc_ui_005_enable_requires_explicit_consent_and_grants_exactly_declared(
    qtbot, monkeypatch, tmp_path, plugin_isolation
):
    """SC-UI-005-1: consent gates enabling; a grant is exactly the declared caps, no auto-run."""
    win = _window(qtbot)
    panel = win._plugin_manager_panel
    manifest = write_manifest(
        tmp_path / "m.json", name="consent-plugin", capabilities=["read_document"]
    )
    _install(panel, monkeypatch, manifest)

    # DENY consent → the plugin is NOT enabled (deny-by-default, no auto-run).
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    panel._on_enable()
    assert "consent-plugin" not in panel._handles
    assert plugins.loaded_count() == 0

    # GRANT consent → enable called with EXACTLY the declared caps and NO activate.
    captured: dict = {}
    real_enable = plugins.enable

    def _spy(manifest_arg, granted, **kwargs):
        captured["granted"] = set(granted)
        captured["activate"] = kwargs.get("activate", "MISSING")
        return real_enable(manifest_arg, granted, **kwargs)

    monkeypatch.setattr(plugin_manager_panel, "enable", _spy)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    panel._on_enable()

    assert "consent-plugin" in panel._handles
    assert captured["granted"] == {Capability.READ_DOCUMENT}  # exactly declared
    # No auto-run: the panel supplies NO activate callable (sentinel "MISSING"
    # means the kwarg was never passed; None would also mean no activation).
    assert captured["activate"] in (None, "MISSING")


def test_sc_ui_005_ungranted_capability_is_denied(plugin_isolation):
    """SC-UI-005-1: a consent-enabled plugin cannot use an ungranted capability."""
    # Enabled with ONLY READ_DOCUMENT; attempting to register a command is denied.
    manifest = PluginManifest(
        name="limited",
        version="1.0",
        api_version="1",
        capabilities=(Capability.READ_DOCUMENT,),
    )
    handle = plugins.enable(manifest, {Capability.READ_DOCUMENT})
    try:
        with pytest.raises(PluginError):
            handle.capability.register_command("x", lambda *a: None, ParamSchema())
        # …and its op-name never entered the trusted allow-list (cannot run).
        assert (
            "limited.x"
            not in __import__(
                "pixelart_creator.logic.scripting", fromlist=["registered_ops"]
            ).registered_ops()
        )
    finally:
        handle.disable()


def test_sc_ui_005_malformed_manifest_surfaces_error_not_executed(
    qtbot, monkeypatch, tmp_path, mute_message_boxes
):
    """SC-UI-005-1: a malformed manifest is rejected gracefully (defensive, no exec)."""
    win = _window(qtbot)
    panel = win._plugin_manager_panel
    before = panel._list.count()

    bad = write_malformed_manifest(tmp_path / "bad.json")
    _install(panel, monkeypatch, bad)

    assert panel._list.count() == before  # rejected, nothing added
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)
    assert plugins.loaded_count() == 0
