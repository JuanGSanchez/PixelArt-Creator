# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Plugin host — trusted-with-consent, default-deny, no auto-run (zero Qt, S11).

Realises ADR-0021's plugin model (REQ-P8-LOGIC-008/-009/-010): plugins are
discovered **inertly**, validated **defensively**, and — only after explicit
consent — handed a **capability object whose ONLY surface is the DSL command
registry** (:mod:`logic.scripting`). A plugin therefore cannot ``eval``/``exec``,
cannot import or reach ``ui/``, cannot touch the filesystem/network outside its
grants, and cannot mutate document state except through a registered reversible
command — every capability the plugin did not declare **and** was not granted is
**denied by default** (no silent bypass).

Honesty about strength (ADR-0021): because *loading* a Python
plugin is itself code execution, in-process capability injection is
**advisory-strength**, adequate only for **trusted, consent-installed** extensions.
This module therefore never *auto-loads* or *auto-runs* anything: :func:`discover`
is inert (no ``.load()``), and :func:`enable` mints the capability handle and, only
if the host passes the consent-gated ``activate`` callable, invokes it **under** the
capability. Untrusted-marketplace OS-isolation is deferred (Article XI).

Layering (plan §4.4 / ADR-0022): ``plugins`` imports ``scripting`` **one-way** (to
register/dispatch) + ``constants``; ``scripting`` never imports ``plugins`` (no
cycle). Zero Qt. No ``eval``/``exec``/``compile`` anywhere.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from importlib import metadata
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from pixelart_creator.logic import scripting
from pixelart_creator.logic.constants import MAX_PLUGINS_LOADED
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.macro import Op

__all__ = [
    "PluginError",
    "Capability",
    "PluginManifest",
    "PluginCapability",
    "PluginHandle",
    "ENTRY_POINT_GROUP",
    "PLUGIN_API_VERSION",
    "SUPPORTED_PLUGIN_API_VERSIONS",
    "validate_manifest",
    "discover",
    "enable",
    "loaded_count",
]

#: The entry-point group plugins register under (stdlib ``importlib.metadata``).
ENTRY_POINT_GROUP = "pixelart_creator.plugins"

#: Current plugin API version — module-local, format-intrinsic (ADR-0001 / BF-2).
PLUGIN_API_VERSION = "1"

#: Plugin API versions this build accepts (fail loudly on an unsupported one).
SUPPORTED_PLUGIN_API_VERSIONS: Tuple[str, ...] = (PLUGIN_API_VERSION,)


class PluginError(ValueError):
    """Raised on a malformed manifest, denied capability, or load-bound breach."""


class Capability(enum.Enum):
    """The module-local plugin capability vocabulary (enumerated, ADR-0001 / BF-2).

    Deliberately grants NO raw filesystem/network/UI capability (deny-by-default,
    ADR-0021): a plugin may only read the document, register DSL command/procgen
    factories, and write through the reversible-command path.
    """

    READ_DOCUMENT = "read_document"
    WRITE_VIA_COMMAND = "write_via_command"
    REGISTER_COMMAND = "register_command"
    REGISTER_PROCGEN = "register_procgen"


_CAPABILITY_BY_VALUE = {cap.value: cap for cap in Capability}


@dataclass(frozen=True)
class PluginManifest:
    """A plugin's declared identity + version + requested capabilities."""

    name: str
    version: str
    api_version: str
    capabilities: Tuple[Capability, ...]


def validate_manifest(data: Mapping[str, object]) -> PluginManifest:
    """Defensively parse a manifest dict into a :class:`PluginManifest` (IO-3 posture).

    Every field is type-checked; the ``api_version`` must be supported and each
    capability must be in the :class:`Capability` vocabulary. **Never** executes
    content. Used by :func:`enable` and by ``data.macro_io.load_manifest``.

    Raises:
        PluginError: On any malformed/unsupported/unknown field.
    """
    if not isinstance(data, Mapping):
        raise PluginError(f"manifest must be a mapping, got {data!r}")
    name = data.get("name")
    version = data.get("version")
    api_version = data.get("api_version")
    caps_raw = data.get("capabilities", [])
    if not isinstance(name, str) or not name:
        raise PluginError(f"manifest name must be a non-empty str, got {name!r}")
    if not isinstance(version, str) or not version:
        raise PluginError(f"manifest version must be a non-empty str, got {version!r}")
    if not isinstance(api_version, str):
        raise PluginError(f"manifest api_version must be a str, got {api_version!r}")
    if api_version not in SUPPORTED_PLUGIN_API_VERSIONS:
        raise PluginError(
            f"unsupported plugin api_version {api_version!r}; "
            f"supported: {SUPPORTED_PLUGIN_API_VERSIONS}"
        )
    if not isinstance(caps_raw, list):
        raise PluginError("manifest capabilities must be a list")
    capabilities: List[Capability] = []
    for entry in caps_raw:
        if not isinstance(entry, str) or entry not in _CAPABILITY_BY_VALUE:
            raise PluginError(f"unknown capability {entry!r}")
        capabilities.append(_CAPABILITY_BY_VALUE[entry])
    return PluginManifest(
        name=name,
        version=version,
        api_version=api_version,
        capabilities=tuple(capabilities),
    )


def discover() -> Tuple[PluginManifest, ...]:
    """Enumerate available plugins **inertly** (no load, no run — REQ-P8-LOGIC-008).

    Lists entry points in :data:`ENTRY_POINT_GROUP` using only ``importlib.metadata``
    (no ``.load()`` — *loading is code execution*), yielding a
    lightweight :class:`PluginManifest` per entry point (name + distribution version;
    no capabilities until the plugin's manifest is loaded defensively via
    ``data.macro_io.load_manifest`` and shown for consent before enable). Robust to
    the group being absent (returns an empty tuple).

    Returns:
        A tuple of inert :class:`PluginManifest` descriptors (capabilities empty).
    """
    try:
        entry_points = metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # very old importlib.metadata without the keyword API
        all_eps = metadata.entry_points()
        entry_points = all_eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[attr-defined]
    manifests: List[PluginManifest] = []
    for ep in entry_points:
        version = "0"
        dist = getattr(ep, "dist", None)
        if dist is not None and getattr(dist, "version", None):
            version = str(dist.version)
        manifests.append(
            PluginManifest(
                name=ep.name,
                version=version,
                api_version=PLUGIN_API_VERSION,
                capabilities=(),
            )
        )
    return tuple(manifests)


class PluginCapability:
    """The ONLY surface a plugin receives — a capability-gated view of the DSL.

    Exposes just the allow-listed command registry + dispatch (:mod:`logic.scripting`)
    and read access, each guarded by a granted :class:`Capability`. It holds **no**
    filesystem/network/UI handle, so a plugin given only this object cannot reach
    those layers; an operation whose capability was not granted raises
    :class:`PluginError` (deny-by-default, REQ-P8-LOGIC-010). Registered op-names are
    namespaced under the plugin (``"<plugin>.<op>"``) so a plugin cannot clobber a
    built-in, and are tracked for clean unregistration on disable.
    """

    __slots__ = ("_plugin_name", "_granted", "_registered")

    def __init__(self, plugin_name: str, granted: Set[Capability]) -> None:
        """Bind the capability object to a plugin name and its granted set."""
        self._plugin_name = plugin_name
        self._granted = frozenset(granted)
        self._registered: List[str] = []

    def _require(self, capability: Capability) -> None:
        if capability not in self._granted:
            raise PluginError(
                f"plugin {self._plugin_name!r} lacks capability {capability.value!r} "
                "(denied by default)"
            )

    @property
    def granted(self) -> Tuple[Capability, ...]:
        """The capabilities granted to this plugin (sorted by value)."""
        return tuple(sorted(self._granted, key=lambda c: c.value))

    @property
    def registered_ops(self) -> Tuple[str, ...]:
        """The op-names this plugin has registered (namespaced)."""
        return tuple(self._registered)

    def _qualify(self, name: str) -> str:
        if not isinstance(name, str) or not name:
            raise PluginError(f"op name must be a non-empty str, got {name!r}")
        return f"{self._plugin_name}.{name}"

    def register_command(
        self,
        name: str,
        factory: "scripting.CommandFactory",
        schema: "scripting.ParamSchema",
    ) -> str:
        """Register a DSL command factory (requires ``REGISTER_COMMAND``).

        Returns the namespaced op-name. Raises :class:`PluginError` if the
        capability was not granted.
        """
        self._require(Capability.REGISTER_COMMAND)
        qualified = self._qualify(name)
        try:
            scripting.register_command(qualified, factory, schema)
        except scripting.ScriptError as exc:
            raise PluginError(str(exc)) from exc
        self._registered.append(qualified)
        return qualified

    def register_procgen(
        self,
        name: str,
        factory: "scripting.CommandFactory",
        schema: "scripting.ParamSchema",
    ) -> str:
        """Register a procedural-generation command (requires ``REGISTER_PROCGEN``)."""
        self._require(Capability.REGISTER_PROCGEN)
        qualified = self._qualify(name)
        try:
            scripting.register_command(qualified, factory, schema)
        except scripting.ScriptError as exc:
            raise PluginError(str(exc)) from exc
        self._registered.append(qualified)
        return qualified

    def read_document(self, document: Document) -> Document:
        """Return the document for read access (requires ``READ_DOCUMENT``)."""
        self._require(Capability.READ_DOCUMENT)
        return document

    def run(self, document: Document, ops: Sequence[Op]) -> Command:
        """Dispatch DSL ops through the trusted path (needs ``WRITE_VIA_COMMAND``)."""
        self._require(Capability.WRITE_VIA_COMMAND)
        return scripting.dispatch(document, ops)

    def _release(self) -> None:
        """Unregister every op this plugin registered (called on disable)."""
        for qualified in list(self._registered):
            if scripting.is_registered(qualified):
                scripting.unregister_command(qualified)
        self._registered.clear()


#: Registry of currently enabled plugins (bounded by ``MAX_PLUGINS_LOADED``).
_LOADED: Dict[str, "PluginHandle"] = {}


class PluginHandle:
    """A live, enabled plugin: its manifest + capability object + disable hook."""

    __slots__ = ("manifest", "capability", "_active")

    def __init__(self, manifest: PluginManifest, capability: PluginCapability) -> None:
        """Hold an enabled plugin's manifest, capability object and active flag."""
        self.manifest = manifest
        self.capability = capability
        self._active = True

    @property
    def active(self) -> bool:
        """Whether this plugin is still enabled."""
        return self._active

    def disable(self) -> None:
        """Disable the plugin: unregister its ops and free its load slot (idempotent).

        Disabling is view/session state (not undoable, CL-8).
        """
        if not self._active:
            return
        self.capability._release()
        _LOADED.pop(self.manifest.name, None)
        self._active = False


def loaded_count() -> int:
    """Return the number of currently enabled plugins."""
    return len(_LOADED)


def enable(
    manifest: PluginManifest,
    granted: Set[Capability],
    *,
    activate: Optional[Callable[[PluginCapability], None]] = None,
) -> PluginHandle:
    """Enable a plugin under an explicit capability grant (deny-by-default).

    Validates the manifest defensively, enforces
    :data:`~pixelart_creator.logic.constants.MAX_PLUGINS_LOADED`, mints a
    capability object exposing ONLY the DSL API + granted caps, and — only if the
    consent-gated ``activate`` callable is supplied — invokes it **under** that
    capability (the "load" step; **no auto-run** otherwise). A plugin can neither
    reach ``ui/``/filesystem/network nor mutate outside a command (REQ-P8-LOGIC-009),
    and any ungranted capability is denied at use (REQ-P8-LOGIC-010).

    Args:
        manifest: The (already-parsed) plugin manifest.
        granted: The capabilities the user explicitly granted. Must be a subset of
            the manifest's declared capabilities (no granting the undeclared).
        activate: Optional consent-gated activation invoked with the capability.

    Returns:
        A :class:`PluginHandle` for the enabled plugin.

    Raises:
        PluginError: On a bad manifest, a grant exceeding the declared caps, the
            load bound, a duplicate enable, or an ``activate`` failure.
    """
    if not isinstance(manifest, PluginManifest):
        raise PluginError(f"enable needs a PluginManifest, got {manifest!r}")
    # Re-validate defensively (round-trips through the same allow-list).
    validate_manifest(
        {
            "name": manifest.name,
            "version": manifest.version,
            "api_version": manifest.api_version,
            "capabilities": [cap.value for cap in manifest.capabilities],
        }
    )
    if not isinstance(granted, (set, frozenset)):
        raise PluginError("granted capabilities must be a set")
    declared = set(manifest.capabilities)
    for cap in granted:
        if not isinstance(cap, Capability):
            raise PluginError(f"granted entry is not a Capability: {cap!r}")
        if cap not in declared:
            raise PluginError(
                f"cannot grant undeclared capability {cap.value!r} to "
                f"{manifest.name!r}"
            )
    if manifest.name in _LOADED:
        raise PluginError(f"plugin {manifest.name!r} is already enabled")
    if len(_LOADED) >= MAX_PLUGINS_LOADED:
        raise PluginError(
            f"cannot enable: at MAX_PLUGINS_LOADED ({MAX_PLUGINS_LOADED})"
        )
    capability = PluginCapability(manifest.name, set(granted))
    handle = PluginHandle(manifest, capability)
    _LOADED[manifest.name] = handle
    if activate is not None:
        try:
            activate(capability)
        except PluginError:
            handle.disable()
            raise
        except Exception as exc:  # noqa: BLE001 - normalise plugin faults, no crash
            handle.disable()
            raise PluginError(
                f"plugin {manifest.name!r} activation failed: {exc}"
            ) from exc
    return handle
