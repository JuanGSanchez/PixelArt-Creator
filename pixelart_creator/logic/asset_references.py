"""Per-project asset reference set and its two predicates (REQ-P11-UI-021, -DATA-010).

A project's reference set is what makes cross-project reuse (``REQ-P11-UI-021``) real
rather than presentational: every library asset a project uses is recorded as an
:class:`AssetReference` — **``asset_id`` -> ``content_hash``** (parent
``REQ-P11-DATA-005``'s resolution key) plus ``kind`` and ``last_known_name``, which are
**display-only labels**, never part of resolution. Resolving by a name or a path would
make a rename or a move break a reference; showing a stale label is merely a display
defect, so the loader never falls back to either (spec.md ``REQ-P11-UI-021``).

Two predicates are computed over these sets, and they stay **two** (plan §4.2) — the
brief's step-4 indicator and the parent ``REQ-P11-UI-007`` predicate answer different
questions and collapsing them would weaken a shipped requirement:

* :func:`resolve_states` / :func:`missing` — a **resolve** state, per reference, against
  one project's own local library.
* :func:`shared_ids` — a **multiplicity** state, per ``asset_id``, across the projects
  the application currently has **open**. "Not shared" is not a claim that no project
  anywhere references the asset — only that no other *open* project does (the honesty
  bound is part of the model, not a caveat about it).

This module also declares and registers ``phase-11-asset-ingress``'s own
:class:`~pixelart_creator.logic.project_prefs.PrefKey` (:data:`ASSET_LIBRARY_EDIT`,
``REQ-P11-DATA-010``) into the shared registry, **at import time** (module scope, not
inside a function) — the seam ``logic/project_prefs.py:97-112`` documents for exactly
this, over the any-size ``PrefDomain`` it types at ``:48``. ``logic/project_prefs.py``
itself is not edited. Registration at import time is load-bearing: an unregistered key
is silently dropped by ``data/project_io.py``'s ``"prefs"`` parser and absent from the
submenu ``ui/project_prefs_actions.py`` builds once at startup, in both cases with no
error — so every consumer that needs the key registered (``data/project_io.py``,
``ui/main_window.py``) imports this module at its own module scope, never lazily.

LAYER: logic/ — pure Python, ZERO Qt (S11). Enforced by
``main/scripts/check_layering.py``; the only Qt-dependent file outside ``ui/`` is
``ui/commands.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Dict, FrozenSet, Mapping, Optional, Tuple

from pixelart_creator.logic import project_prefs
from pixelart_creator.logic.asset_catalog import AssetCatalog, AssetKind
from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS
from pixelart_creator.logic.project_prefs import PrefKey

__all__ = [
    "AssetReferenceError",
    "AssetReference",
    "ReferenceSet",
    "resolve_states",
    "shared_ids",
    "missing",
    "ASSET_LIBRARY_EDIT",
    "STATE_RESOLVED",
    "STATE_EDITED",
    "STATE_MISSING",
    "reference_states",
    "edited_ids",
    "edit_tokens",
]


class AssetReferenceError(ValueError):
    """Raised for an invalid :class:`AssetReference` or :class:`ReferenceSet`."""


@dataclass(frozen=True)
class AssetReference:
    """One project's use of one library asset, identified by identity and content.

    Attributes:
        asset_id: The referenced asset's stable identity (a non-empty str). Part of the
            resolution key.
        content_hash: The content hash the reference was made against (a non-empty
            str). Part of the resolution key; deep hex-shape validation is a ``data/``
            concern (the untrusted-input boundary), mirroring
            :class:`~pixelart_creator.logic.asset_catalog.AssetDescriptor`.
        kind: The referenced asset's
            :class:`~pixelart_creator.logic.asset_catalog.AssetKind`. Display-only —
            never part of resolution.
        last_known_name: The asset's display name the last time this reference was
            resolved, or checked. Display-only fallback (spec.md's step 3): showing it
            stale is a display defect, resolving by it would be a correctness defect.
            Defaults to ``""`` (unknown).
    """

    asset_id: str
    content_hash: str
    kind: AssetKind
    last_known_name: str = ""

    def __post_init__(self) -> None:
        """Validate identity, hash, kind and the display-only name."""
        if not isinstance(self.asset_id, str) or not self.asset_id:
            raise AssetReferenceError(
                f"asset_id must be a non-empty str, got {self.asset_id!r}"
            )
        if not isinstance(self.content_hash, str) or not self.content_hash:
            raise AssetReferenceError(
                f"content_hash must be a non-empty str, got {self.content_hash!r}"
            )
        if not isinstance(self.kind, AssetKind):
            raise AssetReferenceError(f"kind must be an AssetKind, got {self.kind!r}")
        if not isinstance(self.last_known_name, str):
            raise AssetReferenceError(
                f"last_known_name must be a str, got {self.last_known_name!r}"
            )


@dataclass(frozen=True)
class ReferenceSet:
    """An immutable, ordered set of :class:`AssetReference` for one project.

    Mirrors :class:`~pixelart_creator.logic.asset_catalog.AssetCatalog`'s shape
    deliberately: unique ``asset_id`` s, deterministic (``asset_id``-sorted)
    enumeration order, and the same reused
    :data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS` bound — this slice
    mints no new constant for it (plan §4.2).

    Attributes:
        references: The set's members; unique ``asset_id`` s, ``<= MAX_CATALOG_ASSETS``.
    """

    references: Tuple[AssetReference, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate member types, ``asset_id`` uniqueness and count; normalise order."""
        references = tuple(self.references)
        if len(references) > MAX_CATALOG_ASSETS:
            raise AssetReferenceError(
                f"{len(references)} references exceeds MAX_CATALOG_ASSETS "
                f"({MAX_CATALOG_ASSETS})"
            )
        seen: set = set()
        for reference in references:
            if not isinstance(reference, AssetReference):
                raise AssetReferenceError(
                    f"expected an AssetReference, got {reference!r}"
                )
            if reference.asset_id in seen:
                raise AssetReferenceError(f"duplicate asset_id {reference.asset_id!r}")
            seen.add(reference.asset_id)
        ordered = tuple(sorted(references, key=lambda r: r.asset_id))
        object.__setattr__(self, "references", ordered)

    def add(self, reference: AssetReference) -> "ReferenceSet":
        """Return a **new** set with ``reference`` added (pure).

        Raises:
            AssetReferenceError: If ``reference`` is not an :class:`AssetReference`,
                its ``asset_id`` is already present, or adding would exceed
                :data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS`.
        """
        if not isinstance(reference, AssetReference):
            raise AssetReferenceError(f"expected an AssetReference, got {reference!r}")
        if any(r.asset_id == reference.asset_id for r in self.references):
            raise AssetReferenceError(
                f"asset_id {reference.asset_id!r} is already in the reference set"
            )
        if len(self.references) >= MAX_CATALOG_ASSETS:
            raise AssetReferenceError(
                f"reference set already at MAX_CATALOG_ASSETS ({MAX_CATALOG_ASSETS})"
            )
        return ReferenceSet(references=self.references + (reference,))

    def remove(self, asset_id: str) -> "ReferenceSet":
        """Return a **new** set with the reference for ``asset_id`` removed (pure).

        Raises:
            AssetReferenceError: If no reference has that ``asset_id``.
        """
        kept = tuple(r for r in self.references if r.asset_id != asset_id)
        if len(kept) == len(self.references):
            raise AssetReferenceError(f"no reference with asset_id {asset_id!r}")
        return ReferenceSet(references=kept)

    def get(self, asset_id: str) -> Optional[AssetReference]:
        """Return the reference for ``asset_id``, or ``None`` if absent.

        Never raises.
        """
        for reference in self.references:
            if reference.asset_id == asset_id:
                return reference
        return None

    def entries(self) -> Tuple[AssetReference, ...]:
        """Return all references in the deterministic (``asset_id``-sorted) order."""
        return self.references

    def asset_ids(self) -> FrozenSet[str]:
        """Return the set's ``asset_id`` s, order-independent."""
        return frozenset(reference.asset_id for reference in self.references)


def resolve_states(
    reference_set: ReferenceSet, local_catalog: AssetCatalog
) -> Mapping[str, bool]:
    """Return, per ``asset_id`` in ``reference_set``, whether it resolves locally.

    A reference **resolves** when ``local_catalog`` holds an entry whose ``asset_id``
    *and* ``content_hash`` both match — resolution by identity and content, never by a
    name or a path (``REQ-P11-UI-021``). This is the brief's step-4 *resolve* state,
    distinct from the multiplicity state :func:`shared_ids` computes (plan §4.2, "the
    two predicates stay two").

    Pure; performs no I/O.

    Args:
        reference_set: The project's reference set to resolve.
        local_catalog: The local library catalog to resolve against.

    Returns:
        A mapping of ``asset_id`` -> resolved (``True``/``False``), one entry per
        reference in ``reference_set``.
    """
    resolved: Dict[str, bool] = {}
    for reference in reference_set.entries():
        entry = local_catalog.get(reference.asset_id)
        resolved[reference.asset_id] = (
            entry is not None and entry.content_hash == reference.content_hash
        )
    return MappingProxyType(resolved)


def missing(reference_set: ReferenceSet, local_catalog: AssetCatalog) -> FrozenSet[str]:
    """Return the ``asset_id`` s in ``reference_set`` that do not resolve locally.

    The reference set's own unresolvable members (``REQ-P11-UI-021``'s "missing from
    library" state) — a project still opens and its resolvable assets still work when
    this set is non-empty; nothing is dropped or substituted on their account.

    Pure; performs no I/O.
    """
    states = resolve_states(reference_set, local_catalog)
    return frozenset(asset_id for asset_id, resolved in states.items() if not resolved)


#: A reference's ``asset_id`` resolves: the local catalog holds an entry whose
#: ``content_hash`` matches the reference's own (plan §3.11 (1)).
STATE_RESOLVED = "resolved"

#: A reference's ``asset_id`` is present in the local catalog, but the entry's
#: ``content_hash`` differs from the reference's own — the library asset has been
#: edited since this project's reference was made (``REQ-P11-UI-022``'s hash-mismatch
#: trigger; plan §3.11 (1)).
STATE_EDITED = "edited"

#: A reference's ``asset_id`` has no entry in the local catalog at all
#: (``REQ-P11-UI-021``: named and counted, never prompted; plan §3.11 (1)).
STATE_MISSING = "missing"


def reference_states(
    reference_set: ReferenceSet, local_catalog: AssetCatalog
) -> Mapping[str, str]:
    """Return, per ``asset_id`` in ``reference_set``, its three-state reading.

    A refinement of the boolean :func:`resolve_states` already computes from the
    identical pair of inputs (plan §3.11 (1b)): where that function collapses
    "absent from the catalog" and "present with a different ``content_hash``" into
    one ``False``, this function tells them apart as :data:`STATE_EDITED` and
    :data:`STATE_MISSING` respectively; a matching entry reads as
    :data:`STATE_RESOLVED`.

    Pure; performs no I/O, consults no revision store, no CAS — every result comes
    from the two arguments.

    Args:
        reference_set: The project's reference set to classify.
        local_catalog: The local library catalog to classify against.

    Returns:
        A mapping of ``asset_id`` -> one of :data:`STATE_RESOLVED`,
        :data:`STATE_EDITED`, :data:`STATE_MISSING`, one entry per reference in
        ``reference_set``.
    """
    states: Dict[str, str] = {}
    for reference in reference_set.entries():
        entry = local_catalog.get(reference.asset_id)
        if entry is None:
            states[reference.asset_id] = STATE_MISSING
        elif entry.content_hash == reference.content_hash:
            states[reference.asset_id] = STATE_RESOLVED
        else:
            states[reference.asset_id] = STATE_EDITED
    return MappingProxyType(states)


def edited_ids(
    reference_set: ReferenceSet, local_catalog: AssetCatalog
) -> FrozenSet[str]:
    """Return the ``asset_id`` s in :data:`STATE_EDITED` — present, but changed.

    A subset of :func:`missing`'s membership (plan §3.11 (1b)): every edited
    reference is also unresolved, so ``edited_ids(rs, cat) <= missing(rs, cat)``
    holds for every input. Drives ``REQ-P11-UI-022``'s prompt; a
    :data:`STATE_MISSING` reference is never included.

    Pure; performs no I/O.
    """
    states = reference_states(reference_set, local_catalog)
    return frozenset(
        asset_id for asset_id, state in states.items() if state == STATE_EDITED
    )


def edit_tokens(
    reference_set: ReferenceSet, local_catalog: AssetCatalog
) -> Mapping[str, str]:
    """Return, per :data:`STATE_EDITED` ``asset_id``, the library's current hash.

    Keyed exactly by :func:`edited_ids`'s membership; each value is the local
    catalog entry's **current** ``content_hash`` — the token
    ``Asset_Update_Prompt_Dialog.decide()`` uses to tell one edit from the next
    (plan §3.11 (1b), "why ``edit_tokens`` exists").

    Pure; performs no I/O.
    """
    tokens: Dict[str, str] = {}
    for asset_id in edited_ids(reference_set, local_catalog):
        entry = local_catalog.get(asset_id)
        assert entry is not None  # STATE_EDITED implies a catalog entry exists
        tokens[asset_id] = entry.content_hash
    return MappingProxyType(tokens)


def shared_ids(open_reference_sets: Mapping[str, ReferenceSet]) -> FrozenSet[str]:
    """Return the ``asset_id`` s referenced by more than one **open** project.

    The parent ``REQ-P11-UI-007`` multiplicity predicate: an ``asset_id`` counts as
    shared only against the reference sets in ``open_reference_sets`` — the projects
    the application currently has open, keyed by an opaque project identity the caller
    chooses. **The honesty bound is part of the model:** an ``asset_id`` absent from
    the result is not a claim that no project anywhere else references it, only that no
    other *open* project's set does — the alternative reading would need a library-side
    back-index that nothing in this slice builds (plan §4.2).

    Pure; performs no I/O.

    Args:
        open_reference_sets: Every currently open project's :class:`ReferenceSet`,
            keyed by that project's identity.

    Returns:
        The ``asset_id`` s present in more than one of ``open_reference_sets``' values.
    """
    counts: Dict[str, int] = {}
    for reference_set in open_reference_sets.values():
        for asset_id in reference_set.asset_ids():
            counts[asset_id] = counts.get(asset_id, 0) + 1
    return frozenset(asset_id for asset_id, count in counts.items() if count > 1)


#: This slice's preference (``REQ-P11-DATA-010``): what a project does when the library
#: asset behind one of its references has been edited (``REQ-P11-UI-022``). ``"ask"`` is
#: the default — absence reads as "ask me every time" — and the other two members are
#: the dialog's two remembered outcomes (``REQ-P11-UI-023``): always pick up the library
#: change, or always keep the version the project already references. Declared and
#: registered here, at import time, per this module's docstring and plan §3.4 (ruling
#: P11-R2) — never inside a function body.
ASSET_LIBRARY_EDIT = PrefKey(
    name="asset_library_edit",
    domain=frozenset({"ask", "always_pick_up", "always_keep_referenced"}),
    default="ask",
)
project_prefs.register(ASSET_LIBRARY_EDIT)
