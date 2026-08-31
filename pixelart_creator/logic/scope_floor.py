"""The zero-scope floor every guide-enforcement check calls (zero Qt, S11).

This module exists to design out one specific, five-times-recorded defect on
this project: a check that examines fewer files than it thinks it does — or
none at all — and reports a clean pass, because "no findings" and "nothing
was scanned" render identically unless the scope size is stated and floored
(see the in-house template: ``check_layering``, ``check_cycles``,
``coverage_gate``, ``check_doc_references``, ``path_portability_check``).

:func:`require_non_empty_scope` is the shared, callable form of that floor
(``REQ-IS-LOGIC-009``): every one of the four guide-enforcement checks — (a)
registry-to-reality, (b) registry-to-guide, (c) ``en``/``es`` lockstep, (d)
gesture-to-proof-node links — imports and calls it before reporting a
verdict, so the dependency is provable by assertion (a test can import the
four check modules' source and grep for the call) rather than assumed by
review.

It distinguishes two failures that a bare "count is zero" check conflates,
because they have different fixes: a **missing root** — the directory or
bundle the check was supposed to read is not there at all, which is usually
a moved/renamed path — versus an **existing-but-empty** scope — the root is
there, but nothing inside it matched, which is usually a glob or table-shape
regression. Both are reported as the *error object itself*, printed in place
of a clean verdict line, never merely logged alongside one (a "clean" banner
over a scan of nothing is the precise misreading this module exists to
prevent).

Homed in the ``logic`` layer, next to the checks' other Qt-free grounding
(``logic/binding_registry.py``): both are pure, declarative, and used by
tests, not by the shipped application (Article I forbids Qt imports in
``logic/``, not use by tests).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

__all__ = [
    "ScopeFloorError",
    "require_non_empty_scope",
]

#: The error code for a root that does not exist at all (a moved/renamed
#: path). Distinct from :data:`_ERROR_EMPTY_SCOPE` because the fix differs:
#: this one is "the root moved", not "the scope is empty".
_ERROR_ROOT_NOT_FOUND = "root-not-found"

#: The error code for a root that exists but whose examined count is zero
#: (a glob stopped matching, a table shape changed, a bundle emptied).
_ERROR_EMPTY_SCOPE = "empty-scope"


class ScopeFloorError(ValueError):
    """Raised by :func:`require_non_empty_scope` when a check's scope is unsound.

    Carries the check name, what was being counted (``of``), the examined
    count (when the failure is ``empty-scope``) and the missing root path
    (when the failure is ``root-not-found``) as attributes — so a caller can
    print the **error object** (:meth:`as_dict`) instead of a clean verdict,
    per ``REQ-IS-LOGIC-009``. ``str(error)`` always contains the literal
    substring ``"error: <code>"`` (e.g. ``"error: empty-scope"``), so a test
    can assert on it without parsing the dict.

    Attributes:
        error: One of ``"root-not-found"`` or ``"empty-scope"``.
        check_name: The name of the check that raised (e.g.
            ``"registry-to-guide"``).
        of: What the check was counting (e.g. ``"registry entries"``).
        examined: The examined count that triggered ``"empty-scope"``, or
            ``None`` for a ``"root-not-found"`` failure.
        root: The missing root path that triggered ``"root-not-found"``, or
            ``None`` for an ``"empty-scope"`` failure.
    """

    def __init__(
        self,
        *,
        error: str,
        check_name: str,
        of: str,
        examined: int | None = None,
        root: str | None = None,
    ) -> None:
        self.error = error
        self.check_name = check_name
        self.of = of
        self.examined = examined
        self.root = root
        super().__init__(self._as_text())

    def as_dict(self) -> dict[str, Any]:
        """Return the error object to print INSTEAD of a clean verdict.

        Mirrors the in-house convention used by ``check_layering`` /
        ``path_portability_check`` (a JSON-serialisable ``{"error": ...}``
        payload), so a caller can ``print(json.dumps(exc.as_dict()))`` and
        get output shaped like every other gate on this project.
        """
        payload: dict[str, Any] = {
            "error": self.error,
            "check": self.check_name,
            "of": self.of,
        }
        if self.examined is not None:
            payload["examined"] = self.examined
        if self.root is not None:
            payload["root"] = self.root
        return payload

    def _as_text(self) -> str:
        parts = [
            f"error: {self.error}",
            f"check={self.check_name!r}",
            f"of={self.of!r}",
        ]
        if self.examined is not None:
            parts.append(f"examined={self.examined}")
        if self.root is not None:
            parts.append(f"root={self.root!r}")
        return " ".join(parts)


def require_non_empty_scope(
    check_name: str,
    examined: int,
    *,
    of: str,
    root: str | Path | None = None,
) -> None:
    """Raise unless the check actually examined something.

    This is the callable form of ``REQ-IS-LOGIC-009``: a gate that fails is
    visible; a gate that quietly narrows its own scope to nothing is not.
    Every one of the four guide-enforcement checks MUST call this before
    reporting a verdict, and MUST print the raised error object — not a
    clean pass line — when it raises.

    Args:
        check_name: The name of the calling check (e.g.
            ``"registry-to-reality"``, ``"registry-to-guide"``,
            ``"en-to-es-lockstep"``, ``"gesture-proof-node-links"``). Named
            in the raised error so a failure identifies which check went
            blind.
        examined: The number of items the check actually looked at (actions
            introspected, registry rows compared, content stems resolved,
            proof node ids collected — whatever ``of`` names). Zero or
            negative is a floor violation.
        of: What ``examined`` counts, for the error message and the
            denominator line the caller prints on success (e.g. ``"registry
            entries"``, ``"key bindings"``, ``"content stems"``).
        root: Optional. When given, the scope's root path (a directory or
            bundle root). If it does not exist, this raises
            :class:`ScopeFloorError` with ``error="root-not-found"`` —
            distinct from an existing-but-empty scope, because the fix is
            different (a moved/renamed path, not a stale glob). Checked
            before ``examined``, since a missing root explains a zero count
            more precisely than "empty scope" does.

    Raises:
        ScopeFloorError: If ``root`` is given and does not exist
            (``error="root-not-found"``), or if ``examined <= 0``
            (``error="empty-scope"``).
    """
    if root is not None and not Path(root).exists():
        raise ScopeFloorError(
            error=_ERROR_ROOT_NOT_FOUND,
            check_name=check_name,
            of=of,
            root=str(root),
        )
    if examined <= 0:
        raise ScopeFloorError(
            error=_ERROR_EMPTY_SCOPE,
            check_name=check_name,
            of=of,
            examined=examined,
        )
