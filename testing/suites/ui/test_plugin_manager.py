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
from testing.suites.ui._automation_helpers import (
    write_malformed_manifest,
    write_manifest,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _install(panel, monkeypatch, path) -> None:
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )
    panel._on_install()


_BULLET = "• "


def _bullet_lines(text: str) -> list:
    """Return the permission lines of a label: the lines that start with a bullet."""
    return [line for line in text.split("\n") if line.startswith(_BULLET)]


def _permission_names(text: str, members: list) -> dict:
    """Return ``{member: name}`` from the label of a plugin declaring ``members``.

    The lines come in the manifest's order, which is ``members``' order. Asserted
    here: one line per member, so a name is never read from the wrong line.
    """
    lines = _bullet_lines(text)
    assert len(lines) == len(members), f"{len(lines)} lines for {len(members)} members"
    return {m: line[len(_BULLET) :].strip() for m, line in zip(members, lines)}


def _permission_findings(text: str, declared: list, names: dict) -> list:
    """Return what is wrong with the permission lines shown for ``declared``.

    ``names`` is what each of the plugin host's permissions is named (read from the
    label of a plugin that declares them all). Exactly one line for each declared
    permission, in order and as that permission is named; the name of a permission
    that is not declared nowhere in the label; the names differ from one another and
    from every identifier alone, so a line stands for one permission, in words.
    """
    found = []
    identifiers = {member.value for member in Capability}
    for member, name in names.items():
        if not name or name in identifiers:
            found.append(f"{member.value!r} is named {name!r}: not in words")
    if len(set(names.values())) != len(names):
        found.append(f"two permissions share a name: {sorted(names.values())}")
    lines = _bullet_lines(text)
    wanted = [_BULLET + names[member] for member in declared]
    if lines != wanted:
        found.append(
            f"the lines shown are {lines!r}, one per declared one is {wanted!r}"
        )
    for member, name in names.items():
        if member not in declared and name in text:
            found.append(f"{member.value!r} is not declared but {name!r} is shown")
    for line in lines:
        if line[len(_BULLET) :].strip() in identifiers:
            found.append(f"the line {line!r} consists of an identifier alone")
            break
    return found


def test_sc_ui_005_discovery_is_inert_nothing_auto_enabled(qtbot):
    """SC-UI-005-1: a fresh plugin manager has enabled/run NOTHING (deny-by-default)."""
    win = _window(qtbot)
    assert win._plugin_manager_panel._handles == {}
    assert plugins.loaded_count() == 0


def _read_labels(panel, monkeypatch, tmp_path) -> tuple:
    """Return ``(names, text, declared)``: the host's names, then the label shown.

    A plugin declaring every permission the plugin host defines is installed first
    and its label read for the name of each permission (the reference); the plugin
    under test, declaring two, is installed after it and its label read. Both
    manifests are written to ``tmp_path``.
    """
    members = list(Capability)
    reference_manifest = write_manifest(
        tmp_path / "all.json",
        name="reference-plugin",
        capabilities=[member.value for member in members],
    )
    _install(panel, monkeypatch, reference_manifest)
    names = _permission_names(panel._permissions.text(), members)

    declared = [Capability.READ_DOCUMENT, Capability.REGISTER_COMMAND]
    manifest = write_manifest(
        tmp_path / "m.json", capabilities=[member.value for member in declared]
    )
    _install(panel, monkeypatch, manifest)
    return names, panel._permissions.text(), declared


def test_sc_ui_005_declared_permissions_shown_before_enable(
    qtbot, monkeypatch, tmp_path
):
    """SC-UI-005-1 + REQ-L10N-UI-016 clause 1: declared permissions are shown, in words.

    The label of the plugin selected shows one line for each permission the plugin
    declares, each naming the permission in words (the line a plugin that declares
    every permission gets for it), and none for a permission it does not declare;
    no line consists of an identifier alone. Whether a line also shows the
    identifier beside the name is the interface's choice, so it is not asserted.
    """
    win = _window(qtbot)
    panel = win._plugin_manager_panel
    names, text, declared = _read_labels(panel, monkeypatch, tmp_path)

    assert _permission_findings(text, declared, names) == []
    assert panel._enable_button.isEnabled()
    # Merely viewing the permissions does NOT enable/run the plugin.
    assert panel._handles == {}
    assert plugins.loaded_count() == 0


def test_sc_ui_005_the_listing_by_identifier_is_caught(qtbot, monkeypatch, tmp_path):
    """Control: the label listing identifiers alone fails the verdict, naming a line.

    The panel's listing is planted as it was (``• read_document``, one line per
    declared permission, the identifier alone); the real panel is driven as in the
    test above. The verdict must find the planted lines, naming the first.
    """
    monkeypatch.setattr(
        plugin_manager_panel.Plugin_Manager_Panel,
        "_format_capabilities",
        lambda self, manifest: "\n".join(
            f"{_BULLET}{capability.value}" for capability in manifest.capabilities
        ),
    )
    panel = _window(qtbot)._plugin_manager_panel
    names, text, declared = _read_labels(panel, monkeypatch, tmp_path)
    assert _bullet_lines(text) == ["• read_document", "• register_command"], text
    findings = _permission_findings(text, declared, names)
    assert findings, "the identifier listing was not found"
    assert any(
        "'• read_document' consists of an identifier alone" in f for f in findings
    )


def test_sc_ui_005_the_verdict_rejects_each_fault_of_a_listing():
    """Control: written with literals, so the product plays no part."""
    names = {
        Capability.READ_DOCUMENT: "Read it",
        Capability.WRITE_VIA_COMMAND: "Write it",
        Capability.REGISTER_COMMAND: "Add commands",
        Capability.REGISTER_PROCGEN: "Add generators",
    }
    declared = [Capability.READ_DOCUMENT, Capability.REGISTER_COMMAND]
    good = "• Read it\n• Add commands"
    assert _permission_findings(good, declared, names) == []
    # A line for a permission that is not declared.
    assert _permission_findings(good + "\n• Write it", declared, names)
    # A declared permission with no line.
    assert _permission_findings("• Read it", declared, names)
    # A line shown twice, and the lines in another order.
    assert _permission_findings("• Read it\n• Read it", declared, names)
    assert _permission_findings("• Add commands\n• Read it", declared, names)
    # An identifier alone.
    assert _permission_findings("• read_document\n• Add commands", declared, names)
    # Two permissions named alike.
    alike = {**names, Capability.REGISTER_COMMAND: "Read it"}
    assert _permission_findings("• Read it\n• Read it", declared, alike)
    # A name that is an identifier.
    named_by_identifier = {**names, Capability.READ_DOCUMENT: "read_document"}
    assert _permission_findings(
        "• read_document\n• Add commands", declared, named_by_identifier
    )


def test_sc_ui_005_enable_requires_explicit_consent_and_grants_exactly_declared(
    qtbot, monkeypatch, tmp_path, plugin_isolation
):
    """SC-UI-005-1: consent gates enabling; a grant is exactly the declared caps, no
    auto-run."""
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
