"""Per-edit library-decision ledger (`REQ-P11-DATA-010`, ADR-0062, ruling P11-R13).

The user's 2026-08-22 durability ruling states plainly: *"user's decision in the
window, whether is tick or not, is automatically saved in the preferences."* Both
branches of ``Asset_Update_Prompt_Dialog``'s choice are decisions. The **ticked**
half already has a durable home — the shipped per-project preference registry
(:mod:`pixelart_creator.logic.project_prefs`), unchanged by this module. The
**unticked** half has none, and cannot use one: it is per-**edit**, not
per-project, and :class:`~pixelart_creator.logic.project_prefs.PrefKey`'s
enumerated-string-domain shape cannot represent a *set* of decided edits
(``plan.md`` §3.15 (1)(4)). This module is that missing home.

An :class:`AssetEditDecisions` value holds one row per ``asset_id``, each row
pairing the ``edit_token`` the user's answer was decided against with the
outcome they chose. A new token superseding an old row reads as *nothing
decided* (:meth:`AssetEditDecisions.decision_for`) — the ledger is bounded by
the reference set, and a *different* edit of the same asset asks again, which
is the safe direction (ADR-0062 §1, plan.md §3.15 (3)(3)).

**This module is a leaf: it imports nothing from ``pixelart_creator``.** That is
a design constraint, not a coincidence — plan.md §3.15 (10) rests its "no cycle
can close" claim on it, exactly as :mod:`pixelart_creator.data.favourites_io`
already imports no ``data/`` module. Deep validation of untrusted input (e.g.
the hex shape of a content hash) is deliberately left to the ``data/`` layer at
the untrusted-input boundary, mirroring the boundary
:class:`~pixelart_creator.logic.asset_references.AssetReference` already draws
(``logic/asset_references.py:77-80``): this module validates only shape (str,
non-empty, in-domain), never the deep semantics of a token.

LAYER: logic/ — pure Python, ZERO Qt (S11), zero I/O, zero ``pixelart_creator``
imports. Enforced by ``main/scripts/check_layering.py`` and
``main/scripts/check_cycles.py``.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, Mapping, Optional, Tuple

__all__ = [
    "AssetEditDecisionsError",
    "DECISION_PICK_UP",
    "DECISION_KEEP",
    "DECISION_DOMAIN",
    "AssetEditDecisions",
]


class AssetEditDecisionsError(ValueError):
    """Raised for an invalid ``asset_id``, ``edit_token`` or out-of-domain outcome."""


#: The outcome domain's two members. Byte-identical to the values declared at
#: ``ui/asset_update_prompt.py:108-109`` (``OUTCOME_PICK_UP`` / ``OUTCOME_KEEP``)
#: — copied verbatim from that source per plan.md §3.15 (3)(4), not retyped from
#: memory. Those ``ui/`` names become aliases of these; no call site moves.
DECISION_PICK_UP = "pick_up"
DECISION_KEEP = "keep"

#: The outcome domain, declared once. Any future member is added here and
#: nowhere else.
DECISION_DOMAIN: FrozenSet[str] = frozenset({DECISION_PICK_UP, DECISION_KEEP})

#: One decided row: the token the decision was made against, and the outcome.
_DecisionRow = Tuple[str, str]


def _validate_asset_id(asset_id: object) -> str:
    """Return ``asset_id`` unchanged if it is a non-empty ``str``.

    Raises:
        AssetEditDecisionsError: If ``asset_id`` is not a non-empty ``str``.
    """
    if not isinstance(asset_id, str) or not asset_id:
        raise AssetEditDecisionsError(
            f"asset_id must be a non-empty str, got {asset_id!r}"
        )
    return asset_id


def _validate_edit_token(edit_token: object) -> str:
    """Return ``edit_token`` unchanged if it is a non-empty ``str``.

    No hex-shape check is performed here — deep validation of an untrusted
    token belongs to the ``data/`` layer, exactly as
    :class:`~pixelart_creator.logic.asset_references.AssetReference` leaves
    ``content_hash`` hex-shape validation to ``data/``
    (``logic/asset_references.py:77-80``).

    Raises:
        AssetEditDecisionsError: If ``edit_token`` is not a non-empty ``str``.
    """
    if not isinstance(edit_token, str) or not edit_token:
        raise AssetEditDecisionsError(
            f"edit_token must be a non-empty str, got {edit_token!r}"
        )
    return edit_token


def _validate_outcome(outcome: object) -> str:
    """Return ``outcome`` unchanged if it is a member of :data:`DECISION_DOMAIN`.

    Raises:
        AssetEditDecisionsError: If ``outcome`` is not in :data:`DECISION_DOMAIN`.
    """
    if outcome not in DECISION_DOMAIN:
        raise AssetEditDecisionsError(
            f"{outcome!r} is not in the outcome domain {sorted(DECISION_DOMAIN)!r}"
        )
    assert isinstance(outcome, str)  # narrowed by the membership test above
    return outcome


class AssetEditDecisions:
    """An immutable ledger of per-``asset_id`` library-edit decisions.

    One row per ``asset_id``, each row an ``(edit_token, outcome)`` pair — the
    token the outcome was decided against, and the outcome itself
    (:data:`DECISION_PICK_UP` or :data:`DECISION_KEEP`). Follows the shipped
    value shape of :class:`~pixelart_creator.logic.project_prefs.ProjectPrefs`
    (``logic/project_prefs.py:115-166``): built from an optional mapping,
    validated immediately so an invalid value can never exist, and mutated
    only by returning a new value.
    """

    __slots__ = ("_rows",)

    def __init__(self, rows: Optional[Mapping[str, Tuple[str, str]]] = None) -> None:
        """Build a ledger from an optional mapping of ``asset_id -> (token, outcome)``.

        Every row is validated immediately, so an invalid
        :class:`AssetEditDecisions` can never exist.

        Raises:
            AssetEditDecisionsError: If an ``asset_id`` is not a non-empty
                ``str``, an ``edit_token`` is not a non-empty ``str``, or an
                ``outcome`` is not in :data:`DECISION_DOMAIN`.
        """
        resolved: dict = {}
        for asset_id, row in (rows or {}).items():
            validated_id = _validate_asset_id(asset_id)
            edit_token, outcome = row
            resolved[validated_id] = (
                _validate_edit_token(edit_token),
                _validate_outcome(outcome),
            )
        self._rows: Mapping[str, _DecisionRow] = resolved

    def decision_for(self, asset_id: str, edit_token: str) -> Optional[str]:
        """Return the decided outcome for ``asset_id``, if it matches ``edit_token``.

        Returns ``None`` when no row exists for ``asset_id``, **or** when a row
        exists but its stored token differs from ``edit_token`` — a superseding
        token reads as *nothing decided*, which is the data-structure
        expression of "a different edit still asks" (``SC-P11-DATA-010-5``).

        Raises:
            AssetEditDecisionsError: If ``asset_id`` or ``edit_token`` is not a
                non-empty ``str``.
        """
        validated_id = _validate_asset_id(asset_id)
        validated_token = _validate_edit_token(edit_token)
        row = self._rows.get(validated_id)
        if row is None:
            return None
        stored_token, outcome = row
        if stored_token != validated_token:
            return None
        return outcome

    def with_decision(
        self, asset_id: str, edit_token: str, outcome: str
    ) -> "AssetEditDecisions":
        """Return a **new** ledger with ``asset_id``'s row set, replacing any prior row.

        Raises:
            AssetEditDecisionsError: If ``asset_id`` or ``edit_token`` is not a
                non-empty ``str``, or ``outcome`` is not in :data:`DECISION_DOMAIN`.
        """
        validated_id = _validate_asset_id(asset_id)
        validated_token = _validate_edit_token(edit_token)
        validated_outcome = _validate_outcome(outcome)
        updated = dict(self._rows)
        updated[validated_id] = (validated_token, validated_outcome)
        return AssetEditDecisions(updated)

    def merged_with(self, other: "AssetEditDecisions") -> "AssetEditDecisions":
        """Return a new ledger merging ``self`` with ``other``, ``other`` wins per row.

        This is the journal-over-file precedence of plan.md §3.15 (7): a
        journal record can only be non-empty if a decision was made after the
        last save, so it is never staler than the file it is merged over.

        Raises:
            AssetEditDecisionsError: If ``other`` is not an
                :class:`AssetEditDecisions`.
        """
        if not isinstance(other, AssetEditDecisions):
            raise AssetEditDecisionsError(
                f"expected an AssetEditDecisions, got {other!r}"
            )
        merged = dict(self._rows)
        merged.update(other._rows)
        return AssetEditDecisions(merged)

    def entries(self) -> Tuple[Tuple[str, str, str], ...]:
        """Return every ``(asset_id, edit_token, outcome)`` row, ``asset_id``-sorted."""
        return tuple(
            (asset_id, token, outcome)
            for asset_id, (token, outcome) in sorted(self._rows.items())
        )

    def to_serializable(self) -> list:
        """Return every row as a list of dicts, sorted by ``asset_id``.

        The sort makes the persisted bytes deterministic — the same shape
        :meth:`~pixelart_creator.logic.project_prefs.ProjectPrefs.to_mapping`
        gives the preference registry, adapted to this ledger's row shape.
        """
        return [
            {"asset_id": asset_id, "edit_token": token, "outcome": outcome}
            for asset_id, token, outcome in self.entries()
        ]

    def __eq__(self, other: object) -> bool:
        """Two ledgers are equal when their rows are equal."""
        if not isinstance(other, AssetEditDecisions):
            return NotImplemented
        return self._rows == other._rows

    def __repr__(self) -> str:
        """Return a debug representation showing every row."""
        return f"AssetEditDecisions({dict(self._rows)!r})"


def _iter_asset_ids(decisions: AssetEditDecisions) -> Iterable[str]:
    """Return every ``asset_id`` carried by ``decisions``, in ``asset_id``-sorted order.

    A small module-level convenience kept beside the class it reads, for a
    caller that only needs the key set (e.g. a bound-count check performed by
    ``data/`` at the untrusted-input boundary).
    """
    return (asset_id for asset_id, _, _ in decisions.entries())
