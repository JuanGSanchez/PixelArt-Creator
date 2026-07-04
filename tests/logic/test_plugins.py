"""Tests for pixelart_creator.logic.plugins — manifest + discovery contract.

Covers REQ-P8-LOGIC-008 (versioned/declared-capability manifest contract;
malformed rejected; discovery is inert). The deny-by-default sandbox invariants
(REQ-P8-LOGIC-009/-010, security invariant #4) live in
``test_plugins_sandbox.py``.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic import plugins
from pixelart_creator.logic.plugins import (
    Capability,
    PluginError,
    PluginHandle,
    PluginManifest,
    discover,
    enable,
    validate_manifest,
)


def _manifest_data(**overrides):
    data = {
        "name": "acme.tool",
        "version": "1.2.3",
        "api_version": plugins.PLUGIN_API_VERSION,
        "capabilities": ["read_document", "write_via_command"],
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- #
# validate_manifest — defensive, allow-listed                                  #
# --------------------------------------------------------------------------- #


def test_validate_manifest_valid():
    manifest = validate_manifest(_manifest_data())
    assert isinstance(manifest, PluginManifest)
    assert manifest.name == "acme.tool"
    assert Capability.READ_DOCUMENT in manifest.capabilities
    assert Capability.WRITE_VIA_COMMAND in manifest.capabilities


def test_validate_manifest_defaults_empty_capabilities():
    manifest = validate_manifest(_manifest_data(capabilities=[]))
    assert manifest.capabilities == ()


def test_validate_manifest_rejects_non_mapping():
    with pytest.raises(PluginError):
        validate_manifest(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_validate_manifest_rejects_missing_name():
    with pytest.raises(PluginError):
        validate_manifest(_manifest_data(name=""))


def test_validate_manifest_rejects_missing_version():
    with pytest.raises(PluginError):
        validate_manifest(_manifest_data(version=123))


def test_validate_manifest_rejects_non_string_api_version():
    with pytest.raises(PluginError):
        validate_manifest(_manifest_data(api_version=1))


def test_validate_manifest_rejects_unsupported_api_version():
    with pytest.raises(PluginError):
        validate_manifest(_manifest_data(api_version="999"))


def test_validate_manifest_rejects_non_list_capabilities():
    with pytest.raises(PluginError):
        validate_manifest(_manifest_data(capabilities="read_document"))


def test_validate_manifest_rejects_unknown_capability():
    with pytest.raises(PluginError):
        validate_manifest(_manifest_data(capabilities=["launch_missiles"]))


def test_supported_api_versions_includes_current():
    assert plugins.PLUGIN_API_VERSION in plugins.SUPPORTED_PLUGIN_API_VERSIONS


# --------------------------------------------------------------------------- #
# discover — inert (no .load(), no auto-run) — REQ-P8-LOGIC-008                 #
# --------------------------------------------------------------------------- #


def test_discover_is_inert_and_returns_tuple():
    # Discovery must not import/run any plugin; in a clean env the group is absent,
    # so the result is an (empty) tuple and NOTHING was executed.
    result = discover()
    assert isinstance(result, tuple)
    for manifest in result:
        # Inert descriptors carry no capabilities until a manifest is loaded.
        assert manifest.capabilities == ()


def test_discover_robust_to_missing_group(monkeypatch):
    # If the modern keyword API raises TypeError (very old importlib.metadata),
    # discover falls back to the dict form and stays robust to the group's absence.
    def _entry_points(*args, **kwargs):
        if kwargs:  # the group= keyword call
            raise TypeError("no keyword API")
        return {}  # legacy dict form, group absent

    monkeypatch.setattr(plugins.metadata, "entry_points", _entry_points)
    assert discover() == ()


# --------------------------------------------------------------------------- #
# enable — the entry point (contract level; sandbox behaviour tested elsewhere) #
# --------------------------------------------------------------------------- #


def test_enable_returns_active_handle(plugins_guard):
    manifest = validate_manifest(_manifest_data())
    handle = enable(manifest, {Capability.READ_DOCUMENT})
    assert isinstance(handle, PluginHandle)
    assert handle.active
    assert plugins_guard.loaded_count() == 1
    handle.disable()
    assert not handle.active
    assert plugins_guard.loaded_count() == 0


def test_enable_does_not_auto_run(plugins_guard):
    # No-auto-run: enable without an ``activate`` callable executes NO plugin code,
    # so the capability has registered nothing.
    manifest = validate_manifest(_manifest_data())
    handle = enable(manifest, {Capability.READ_DOCUMENT})
    assert handle.capability.registered_ops == ()


def test_enable_invokes_consent_gated_activate(plugins_guard):
    seen = {}
    manifest = validate_manifest(_manifest_data())

    def _activate(cap):
        seen["cap"] = cap

    enable(manifest, {Capability.READ_DOCUMENT}, activate=_activate)
    assert "cap" in seen


def test_enable_rejects_non_manifest(plugins_guard):
    with pytest.raises(PluginError):
        enable({"name": "x"}, set())  # type: ignore[arg-type]


def test_enable_rejects_non_set_grant(plugins_guard):
    manifest = validate_manifest(_manifest_data())
    with pytest.raises(PluginError):
        enable(manifest, [Capability.READ_DOCUMENT])  # type: ignore[arg-type]


def test_enable_rejects_undeclared_grant(plugins_guard):
    # Cannot grant a capability the manifest did not declare.
    manifest = validate_manifest(_manifest_data(capabilities=["read_document"]))
    with pytest.raises(PluginError):
        enable(manifest, {Capability.REGISTER_COMMAND})


def test_enable_rejects_non_capability_grant_entry(plugins_guard):
    manifest = validate_manifest(_manifest_data())
    with pytest.raises(PluginError):
        enable(manifest, {"read_document"})  # type: ignore[arg-type]


def test_enable_rejects_duplicate(plugins_guard):
    manifest = validate_manifest(_manifest_data())
    enable(manifest, {Capability.READ_DOCUMENT})
    with pytest.raises(PluginError):
        enable(manifest, {Capability.READ_DOCUMENT})


def test_activate_failure_disables_and_normalises(plugins_guard):
    manifest = validate_manifest(_manifest_data())

    def _boom(cap):
        raise RuntimeError("plugin blew up")

    with pytest.raises(PluginError):
        enable(manifest, {Capability.READ_DOCUMENT}, activate=_boom)
    # The failed plugin freed its slot (no leak).
    assert plugins_guard.loaded_count() == 0


def test_activate_plugin_error_propagates_and_disables(plugins_guard):
    manifest = validate_manifest(_manifest_data())

    def _boom(cap):
        raise PluginError("explicit denial")

    with pytest.raises(PluginError):
        enable(manifest, {Capability.READ_DOCUMENT}, activate=_boom)
    assert plugins_guard.loaded_count() == 0


def test_disable_is_idempotent(plugins_guard):
    manifest = validate_manifest(_manifest_data())
    handle = enable(manifest, {Capability.READ_DOCUMENT})
    handle.disable()
    handle.disable()  # no error, still inactive
    assert not handle.active
