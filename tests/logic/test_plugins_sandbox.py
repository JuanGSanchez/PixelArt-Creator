"""Security invariant #4 — a plugin cannot bypass the layer boundaries.

Covers REQ-P8-LOGIC-009 (a plugin acts ONLY through the capability/DSL API — no
``ui/`` reach, no ungranted filesystem/network, no direct mutation) and -010
(deny-by-default capability; ``MAX_PLUGINS_LOADED`` enforced). SC-L009-1 /
SC-L010-1. The ``PluginCapability`` object is the ONLY surface a plugin receives.
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.logic import plugins, scripting
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.plugins import (
    Capability,
    PluginCapability,
    PluginError,
    validate_manifest,
)

RED = (255, 0, 0, 255)
TRANSPARENT = (0, 0, 0, 0)


def _manifest(caps):
    return validate_manifest(
        {
            "name": "sandbox.plug",
            "version": "1.0.0",
            "api_version": plugins.PLUGIN_API_VERSION,
            "capabilities": list(caps),
        }
    )


def _doc():
    return Document(4, 4, palette=Palette([RED]))


# --------------------------------------------------------------------------- #
# The capability object is the ONLY surface — no fs/net/ui handle              #
# --------------------------------------------------------------------------- #


def test_capability_exposes_no_filesystem_or_ui_handle():
    cap = PluginCapability("p", {Capability.READ_DOCUMENT})
    # __slots__ pins the surface: no open/socket/import/ui attributes exist.
    for forbidden in ("open", "socket", "system", "import_module", "ui", "os"):
        assert not hasattr(cap, forbidden)
    # Only the allow-listed DSL methods are present.
    for allowed in ("register_command", "register_procgen", "read_document", "run"):
        assert hasattr(cap, allowed)


def test_capability_has_slots_cannot_add_attributes():
    cap = PluginCapability("p", {Capability.READ_DOCUMENT})
    with pytest.raises(AttributeError):
        cap.backdoor = lambda: None  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Deny-by-default — an ungranted capability raises (REQ-P8-LOGIC-010)           #
# --------------------------------------------------------------------------- #


def test_ungranted_register_command_denied():
    cap = PluginCapability("p", set())  # nothing granted
    with pytest.raises(PluginError):
        cap.register_command("op", lambda d, p, s: None, scripting.ParamSchema())


def test_ungranted_register_procgen_denied():
    cap = PluginCapability("p", set())
    with pytest.raises(PluginError):
        cap.register_procgen("gen", lambda d, p, s: None, scripting.ParamSchema())


def test_ungranted_read_document_denied():
    cap = PluginCapability("p", set())
    with pytest.raises(PluginError):
        cap.read_document(_doc())


def test_ungranted_run_denied():
    cap = PluginCapability("p", set())
    with pytest.raises(PluginError):
        cap.run(_doc(), [Op("batch_recolour", {"color_map": []})])


def test_granted_read_document_returns_document():
    doc = _doc()
    cap = PluginCapability("p", {Capability.READ_DOCUMENT})
    assert cap.read_document(doc) is doc


def test_granted_capabilities_are_reported_sorted():
    cap = PluginCapability(
        "p", {Capability.WRITE_VIA_COMMAND, Capability.READ_DOCUMENT}
    )
    values = [c.value for c in cap.granted]
    assert values == sorted(values)


# --------------------------------------------------------------------------- #
# A plugin edits ONLY through the reversible-command path (REQ-P8-LOGIC-009)     #
# --------------------------------------------------------------------------- #


def test_plugin_run_edits_only_via_reversible_command(registry_guard):
    doc = _doc()
    buf = iter_layers(doc.frames[0].layers)[0].buffer
    before = buf.data.copy()
    cap = PluginCapability("p", {Capability.WRITE_VIA_COMMAND})
    cmd = cap.run(
        doc, [Op("batch_recolour", {"color_map": [[list(TRANSPARENT), list(RED)]]})]
    )
    # The ONLY way a plugin mutated the doc was a reversible Command it can undo.
    assert isinstance(cmd, Command)
    assert tuple(buf.data[0, 0]) == RED
    cmd.undo()
    assert np.array_equal(buf.data, before)


def test_plugin_registered_op_is_namespaced(registry_guard):
    cap = PluginCapability("acme", {Capability.REGISTER_COMMAND})
    qualified = cap.register_command(
        "myop", lambda d, p, s: None, scripting.ParamSchema()
    )
    assert qualified == "acme.myop"  # cannot clobber a built-in
    assert scripting.is_registered("acme.myop")
    assert "acme.myop" in cap.registered_ops


def test_plugin_register_rejects_empty_name(registry_guard):
    cap = PluginCapability("acme", {Capability.REGISTER_COMMAND})
    with pytest.raises(PluginError):
        cap.register_command("", lambda d, p, s: None, scripting.ParamSchema())


def test_plugin_register_duplicate_normalised_to_plugin_error(registry_guard):
    cap = PluginCapability("acme", {Capability.REGISTER_COMMAND})
    cap.register_command("dup", lambda d, p, s: None, scripting.ParamSchema())
    with pytest.raises(PluginError):
        cap.register_command("dup", lambda d, p, s: None, scripting.ParamSchema())


def test_procgen_register_duplicate_normalised(registry_guard):
    cap = PluginCapability("acme", {Capability.REGISTER_PROCGEN})
    cap.register_procgen("g", lambda d, p, s: None, scripting.ParamSchema())
    with pytest.raises(PluginError):
        cap.register_procgen("g", lambda d, p, s: None, scripting.ParamSchema())


def test_disable_unregisters_plugin_ops(plugins_guard, registry_guard):
    manifest = _manifest(["register_command"])
    registered = {}

    def _activate(cap):
        registered["name"] = cap.register_command(
            "op", lambda d, p, s: None, scripting.ParamSchema()
        )

    handle = plugins_guard.enable(
        manifest, {Capability.REGISTER_COMMAND}, activate=_activate
    )
    assert scripting.is_registered(registered["name"])
    handle.disable()
    # Disabling frees the slot AND unregisters the plugin's ops (no leak).
    assert not scripting.is_registered(registered["name"])


# --------------------------------------------------------------------------- #
# MAX_PLUGINS_LOADED enforced (REQ-P8-LOGIC-010 / -013)                          #
# --------------------------------------------------------------------------- #


def test_max_plugins_loaded_enforced(plugins_guard, monkeypatch):
    monkeypatch.setattr(plugins, "MAX_PLUGINS_LOADED", 2)
    handles = []
    for i in range(2):
        m = validate_manifest(
            {
                "name": f"plug.{i}",
                "version": "1.0.0",
                "api_version": plugins.PLUGIN_API_VERSION,
                "capabilities": ["read_document"],
            }
        )
        handles.append(plugins_guard.enable(m, {Capability.READ_DOCUMENT}))
    assert plugins_guard.loaded_count() == 2
    # The 3rd exceeds the bound.
    third = validate_manifest(
        {
            "name": "plug.overflow",
            "version": "1.0.0",
            "api_version": plugins.PLUGIN_API_VERSION,
            "capabilities": ["read_document"],
        }
    )
    with pytest.raises(PluginError):
        plugins_guard.enable(third, {Capability.READ_DOCUMENT})
