# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Per-project preference registry (zero Qt, S11 — ADR-0056).

Settles the four-claimant "per-project confirmation preference" decision once
(plan §3.3): each preference is declared as a :class:`PrefKey` — a name, an
**enumerated value domain** and a default — and a snapshot of resolved values
for one project is a :class:`ProjectPrefs`, where an unset key always reads as
its declared default (``absent -> default``).

The domain is a plain set of strings (:data:`PrefDomain`), so the same
mechanism represents both a two-value ("ask" / "suppressed") preference and a
three-value one without a code change — this slice ships
:data:`CONFIRM_CEL_OVERWRITE` (two values); ``phase-11-asset-ingress``'s
three-state preference (``REQ-P11-DATA-010``) is the mechanism's other shape,
added later by calling :func:`register` from its own module. This module adds
no key on their behalf and mints no id it does not own.

This is deliberately **not** a settings framework: no UI schema, no grouping,
no migration engine, no per-machine scope (plan §3.3) — persistence is
``data/project_io.py``'s job, and rendering the registry into a menu is
``ui/project_prefs_actions.py``'s. This module is pure, Qt-free and does
no I/O.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping, NamedTuple, Optional

__all__ = [
    "ProjectPrefsError",
    "PrefDomain",
    "PrefKey",
    "ProjectPrefs",
    "REGISTRY",
    "register",
    "get",
    "with_value",
    "CONFIRM_CEL_OVERWRITE",
]


class ProjectPrefsError(ValueError):
    """Raised for an unregistered preference key or an out-of-domain value."""


#: A preference's enumerated set of admissible string values. Any size is
#: valid — a boolean-shaped preference is a two-member domain, phase-11's is a
#: three-member one; the mechanism does not special-case either.
PrefDomain = FrozenSet[str]


class PrefKey(NamedTuple):
    """A declared preference: its unique name, its domain and its default.

    Values are strings, never a raw ``bool`` — the on-disk shape
    (``data/project_io.py``) is an enumerated string exactly like the domain
    it is validated against, so there is one representation end to end.
    """

    name: str
    domain: PrefDomain
    default: str

    def validate(self, value: str) -> str:
        """Return ``value`` unchanged if it lies in this key's domain.

        Raises:
            ProjectPrefsError: If ``value`` is not a member of :attr:`domain`.
        """
        if value not in self.domain:
            raise ProjectPrefsError(
                f"{value!r} is not in the domain of preference {self.name!r} "
                f"({sorted(self.domain)!r})"
            )
        return value


#: This slice's preference (``REQ-P5-DATA-004``): whether a timeline-grid cel
#: overwrite (``REQ-P5-UI-033``) asks for confirmation. ``"ask"`` is the
#: default — absence reads as "ask me" (spec §"REQ-P5-DATA-004"); ``"suppressed"``
#: records "Don't ask again" for the current project only.
CONFIRM_CEL_OVERWRITE = PrefKey(
    name="confirm_cel_overwrite",
    domain=frozenset({"ask", "suppressed"}),
    default="ask",
)

#: The registry: every declared preference key, addressable by name. A
#: **mutable** dict, deliberately — a later slice (``phase-11-asset-ingress``,
#: ``phase-6-mode-toggle-undo``, the canvas warning) adds its own key by
#: calling :func:`register` from its own module, never by editing this file
#: (tasks.md hand-offs: "it writes none of those three files").
REGISTRY: Dict[str, PrefKey] = {
    CONFIRM_CEL_OVERWRITE.name: CONFIRM_CEL_OVERWRITE,
}


def register(key: PrefKey) -> None:
    """Add ``key`` to :data:`REGISTRY` so its preference becomes resolvable.

    This is the seam a later slice uses to add a preference **key** without
    touching this module (plan §3.3, ADR-0056): construct a :class:`PrefKey`
    with its own enumerated domain and default, then call this function once
    at import time.

    Raises:
        ProjectPrefsError: If a key with the same name is already registered
            (a name collision between two slices is a defect to surface, not
            to silently overwrite).
    """
    if key.name in REGISTRY and REGISTRY[key.name] is not key:
        raise ProjectPrefsError(f"preference key {key.name!r} is already registered")
    REGISTRY[key.name] = key


class ProjectPrefs:
    """An immutable snapshot of resolved preference values for one project.

    ``absent -> default`` for every registered key: a key never explicitly set
    on this snapshot resolves to its :class:`PrefKey`'s ``default``. Like the
    rest of the logic layer's value objects it is not mutated in place —
    :meth:`with_value` returns a new snapshot.
    """

    __slots__ = ("_values",)

    def __init__(self, values: Optional[Mapping[str, str]] = None) -> None:
        """Build a snapshot from an optional mapping of explicitly-set values.

        Every value is validated against its key's domain immediately, so an
        invalid ``ProjectPrefs`` can never exist.

        Raises:
            ProjectPrefsError: If a key in ``values`` is not in
                :data:`REGISTRY`, or its value is outside that key's domain.
        """
        resolved: Dict[str, str] = {}
        for name, value in (values or {}).items():
            key = REGISTRY.get(name)
            if key is None:
                raise ProjectPrefsError(f"unknown preference key {name!r}")
            resolved[name] = key.validate(value)
        self._values: Dict[str, str] = resolved

    def get(self, key: PrefKey) -> str:
        """Return the resolved value for ``key`` — its set value, or its default."""
        return self._values.get(key.name, key.default)

    def with_value(self, key: PrefKey, value: str) -> "ProjectPrefs":
        """Return a new snapshot with ``key`` set to ``value``.

        Raises:
            ProjectPrefsError: If ``value`` is outside ``key``'s domain.
        """
        key.validate(value)
        updated = dict(self._values)
        updated[key.name] = value
        return ProjectPrefs(updated)

    def to_mapping(self) -> Dict[str, str]:
        """Return only the explicitly-set values (never a key's default).

        ``data/project_io.py`` serialises exactly this — a key resolving to
        its default because it was never set stays **absent** on disk.
        """
        return dict(self._values)

    def __eq__(self, other: object) -> bool:
        """Two snapshots are equal when their explicitly-set values are equal."""
        if not isinstance(other, ProjectPrefs):
            return NotImplemented
        return self._values == other._values

    def __repr__(self) -> str:
        """Return a debug representation showing only the explicitly-set values."""
        return f"ProjectPrefs({self._values!r})"


def get(prefs: ProjectPrefs, key: PrefKey) -> str:
    """Module-level convenience wrapping :meth:`ProjectPrefs.get`."""
    return prefs.get(key)


def with_value(prefs: ProjectPrefs, key: PrefKey, value: str) -> ProjectPrefs:
    """Module-level convenience wrapping :meth:`ProjectPrefs.with_value`."""
    return prefs.with_value(key, value)
