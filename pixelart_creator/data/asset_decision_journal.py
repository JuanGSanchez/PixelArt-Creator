"""Write-ahead journal for library-edit decisions (ADR-0062, ruling P11-R13).

`REQ-P11-DATA-010`'s durability half is answered here, not by writing the
project file. The user's 2026-08-22 ruling states plainly: *"user's decision
in the window, whether is tick or not, is automatically saved in the
preferences."* Writing the project file on a click would also write the
user's unsaved canvas work, which the ruling does not ask for and the user
would not expect (ADR-0062 §2, plan.md §3.15 (1)(3)). This module is the
**durability buffer** beside the project file: one record per absolute
project path, holding the admitted preference value and the per-edit
decision ledger, retired the moment the project file catches up
(``ProjectIOError`` load-bundle / save path — a ``data/`` write path, not
this one).

**The admitted-key list is the ruling's named extension point, and it is a
tuple, not an open door** (plan.md §3.15 (9)). A value under any other key
is ignored on read and refused on write; adding a second key later is the
one-line change that list is sized for, not a reason to build a generic
"prompt decision ledger" (ADR-0062 §5 — none is built here).

**Atomicity posture, stated exactly, not oversold:**

* **Guaranteed** — a completed write survives process death: the whole
  journal is re-serialised to a temp file, flushed, ``fsync``-ed and moved
  into place with :func:`os.replace` (the shipped
  :mod:`pixelart_creator.data.cloud.fake_adapter` pattern,
  ``data/cloud/fake_adapter.py:56-66``). A reader sees the whole previous
  journal or the whole new one, never a truncation.
* **Guaranteed** — nothing is ever remembered that the user did not choose;
  this module writes only what its caller passes it.
* **Not guaranteed, deliberately** — survival of a kill *during* the write:
  the decision is lost and the user is asked again at the next open, which
  is the safe failure, and it is the pre-ruling behaviour.
* **One place this is stricter than ruling P11-R1** (ADR-0059 §2): P11-R1
  tolerates a bare write for a shipped file written during an explicit save;
  this is a *new* file written on a mere *click*, so it gets temp-and-replace
  rather than that tolerance.

This module receives a :class:`~pathlib.Path` and never resolves one itself
(the caller — ``ui/`` — resolves the location via ``QStandardPaths``, beside
the favourites store it already resolves there); it imports no Qt and no
other ``data/`` module — the shipped
:mod:`pixelart_creator.data.favourites_io` contract (ADR-0004). Its error
type subclasses :class:`ValueError` **directly, not**
:class:`~pixelart_creator.data.project_io.ProjectIOError`: this is an
app-level store, not a project one, and that distinction is deliberate
(ADR-0062 §2; plan.md §3.15 (10)).

LAYER: data/ — zero Qt (S11). Imports only :mod:`pixelart_creator.logic.
asset_edit_decisions` and :mod:`pixelart_creator.logic.constants`. Enforced
by ``scripts/check_layering.py`` and ``scripts/check_cycles.py``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Union

from pixelart_creator.logic.asset_edit_decisions import (
    DECISION_DOMAIN,
    AssetEditDecisions,
)
from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS

__all__ = [
    "AssetDecisionJournalError",
    "FORMAT_NAME",
    "JOURNAL_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "JOURNAL_FILENAME",
    "load_journal",
    "write_record",
    "drop_record",
]

_PathLike = Union[str, "os.PathLike[str]"]

#: The journal-file format marker.
FORMAT_NAME = "pixdecisions"

#: Journal wire schema version.
JOURNAL_SCHEMA_VERSION: int = 1

#: Schema versions this build can load.
SUPPORTED_SCHEMA_VERSIONS = (JOURNAL_SCHEMA_VERSION,)

#: The journal filename, resolved by the caller under an app-config directory
#: (``ui/`` resolves it via ``QStandardPaths.AppConfigLocation``, beside the
#: favourites store it already resolves there).
JOURNAL_FILENAME = "asset-edit-decisions.json"

#: The admitted preference keys — deliberately exactly one entry
#: (plan.md §3.15 (9); ADR-0062 §5). NOT a general prompt-decision framework:
#: extending durability to a future preference is one entry added here, and
#: nothing else. A value under any other key is ignored on read and refused
#: on write.
_ADMITTED_PREF_KEYS = ("asset_library_edit",)


class AssetDecisionJournalError(ValueError):
    """Raised when the journal cannot be written, or is unreadable/malformed.

    Subclasses :class:`ValueError` directly — **not**
    :class:`~pixelart_creator.data.project_io.ProjectIOError` — because this
    is an app-level store, not a project one (ADR-0062 §2).
    """


def _fresh_envelope() -> Dict[str, Any]:
    """Return an empty, well-formed journal envelope."""
    return {
        "format": FORMAT_NAME,
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "projects": {},
    }


def _validate_edit_entry(entry: object, target: Path) -> Dict[str, str]:
    """Return a validated ``{"asset_id", "edit_token", "outcome"}`` dict.

    Raises:
        AssetDecisionJournalError: If ``entry`` is malformed.
    """
    if not isinstance(entry, dict):
        raise AssetDecisionJournalError(
            f"{target}: an edit entry must be a JSON object"
        )
    asset_id = entry.get("asset_id")
    edit_token = entry.get("edit_token")
    outcome = entry.get("outcome")
    if not isinstance(asset_id, str) or not asset_id:
        raise AssetDecisionJournalError(
            f"{target}: edit entry asset_id must be a non-empty string"
        )
    if not isinstance(edit_token, str) or not edit_token:
        raise AssetDecisionJournalError(
            f"{target}: edit entry edit_token must be a non-empty string"
        )
    if outcome not in DECISION_DOMAIN:
        raise AssetDecisionJournalError(
            f"{target}: edit entry outcome {outcome!r} is not in the outcome domain "
            f"{sorted(DECISION_DOMAIN)!r}"
        )
    return {"asset_id": asset_id, "edit_token": edit_token, "outcome": outcome}


def _validate_record(record: object, target: Path) -> Dict[str, Any]:
    """Return a validated ``{"prefs": {...}, "edits": [...]}`` record.

    An admitted-key filter is applied to ``"prefs"`` here — a value under any
    other key is silently dropped, per the ruling's read-side behaviour
    (plan.md §3.15 (9)).

    Raises:
        AssetDecisionJournalError: If ``record`` is malformed.
    """
    if not isinstance(record, dict):
        raise AssetDecisionJournalError(
            f"{target}: a project record must be a JSON object"
        )
    raw_prefs = record.get("prefs", {})
    if not isinstance(raw_prefs, dict):
        raise AssetDecisionJournalError(
            f"{target}: a record's prefs must be a JSON object"
        )
    prefs: Dict[str, str] = {}
    for key, value in raw_prefs.items():
        if key not in _ADMITTED_PREF_KEYS:
            continue
        if not isinstance(value, str) or not value:
            raise AssetDecisionJournalError(
                f"{target}: prefs value for {key!r} must be a non-empty string"
            )
        prefs[key] = value
    raw_edits = record.get("edits", [])
    if not isinstance(raw_edits, list):
        raise AssetDecisionJournalError(
            f"{target}: a record's edits must be a JSON array"
        )
    if len(raw_edits) > MAX_CATALOG_ASSETS:
        raise AssetDecisionJournalError(
            f"{target}: a record's edits exceed MAX_CATALOG_ASSETS "
            f"({MAX_CATALOG_ASSETS})"
        )
    edits = [_validate_edit_entry(entry, target) for entry in raw_edits]
    return {"prefs": prefs, "edits": edits}


def _read_envelope(target: Path) -> Dict[str, Any]:
    """Return the journal envelope at ``target``, or a fresh one if absent.

    Raises:
        AssetDecisionJournalError: If ``target`` exists but is unreadable or
            malformed.
    """
    if not target.exists():
        return _fresh_envelope()
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssetDecisionJournalError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssetDecisionJournalError(f"{target} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AssetDecisionJournalError(f"{target}: journal must be a JSON object")
    if payload.get("format") != FORMAT_NAME:
        raise AssetDecisionJournalError(f"{target}: not a {FORMAT_NAME} journal")
    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise AssetDecisionJournalError(
            f"{target}: unsupported schema_version {schema_version!r}"
        )
    projects = payload.get("projects")
    if not isinstance(projects, dict):
        raise AssetDecisionJournalError(f"{target}: 'projects' must be a JSON object")
    if len(projects) > MAX_CATALOG_ASSETS:
        raise AssetDecisionJournalError(
            f"{target}: exceeds MAX_CATALOG_ASSETS ({MAX_CATALOG_ASSETS}) "
            "project records"
        )
    for project_path in projects:
        if not isinstance(project_path, str) or not project_path:
            raise AssetDecisionJournalError(
                f"{target}: a project key must be a non-empty string"
            )
    return payload


def _write_envelope(target: Path, envelope: Mapping[str, Any]) -> None:
    """Write ``envelope`` to ``target`` atomically (temp + fsync + os.replace).

    Mirrors the shipped Windows-safe pattern of
    ``data/cloud/fake_adapter.py:56-66`` — an interrupted write never
    corrupts the last good file.

    Raises:
        AssetDecisionJournalError: If the file cannot be written.
    """
    data = json.dumps(envelope).encode("utf-8")
    tmp = target.with_name(target.name + ".tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    except OSError as exc:
        raise AssetDecisionJournalError(f"cannot write {target}: {exc}") from exc


def load_journal(path: _PathLike) -> Dict[str, Dict[str, Any]]:
    """Load every project record from the journal at ``path``.

    Returns a mapping ``absolute project path -> {"prefs": {...}, "edits":
    [...]}`` — **an absent file returns an empty mapping** (first-run
    friendly, mirroring :func:`pixelart_creator.data.favourites_io.
    load_favourites`). A value under a non-admitted ``"prefs"`` key is
    dropped rather than raised.

    Raises:
        AssetDecisionJournalError: If the file exists but is unreadable or
            malformed.
    """
    target = Path(path)
    envelope = _read_envelope(target)
    projects = envelope["projects"]
    return {
        project_path: _validate_record(record, target)
        for project_path, record in projects.items()
    }


def write_record(
    path: _PathLike,
    project_path: str,
    prefs_values: Mapping[str, str],
    decisions: AssetEditDecisions,
) -> None:
    """Read-modify-write ``path``'s journal, setting ``project_path``'s record.

    ``prefs_values`` must contain only admitted keys (:data:`
    _ADMITTED_PREF_KEYS`) — a non-admitted key is **refused**, not silently
    dropped, on write. ``decisions`` is serialised via
    :meth:`~pixelart_creator.logic.asset_edit_decisions.AssetEditDecisions.
    to_serializable`. The whole journal is re-serialised atomically
    (temp + fsync + ``os.replace``); a completed write survives process
    death, a kill mid-write loses only this decision (module docstring).

    Raises:
        AssetDecisionJournalError: If ``project_path`` is not a non-empty
            string, ``prefs_values`` carries a non-admitted key or a
            non-string value, ``decisions`` is not an
            :class:`AssetEditDecisions`, an existing journal is malformed, or
            the file cannot be written.
    """
    if not isinstance(project_path, str) or not project_path:
        raise AssetDecisionJournalError("project_path must be a non-empty string")
    for key, value in prefs_values.items():
        if key not in _ADMITTED_PREF_KEYS:
            raise AssetDecisionJournalError(
                f"{key!r} is not an admitted prefs key; only {_ADMITTED_PREF_KEYS} "
                "may be written"
            )
        if not isinstance(value, str) or not value:
            raise AssetDecisionJournalError(
                f"prefs value for {key!r} must be a non-empty string, got {value!r}"
            )
    if not isinstance(decisions, AssetEditDecisions):
        raise AssetDecisionJournalError(
            f"decisions must be an AssetEditDecisions, got {decisions!r}"
        )
    edits_payload = decisions.to_serializable()
    if len(edits_payload) > MAX_CATALOG_ASSETS:
        raise AssetDecisionJournalError(
            f"decisions exceed MAX_CATALOG_ASSETS ({MAX_CATALOG_ASSETS})"
        )

    target = Path(path)
    envelope = _read_envelope(target)
    projects = envelope["projects"]
    projects[project_path] = {"prefs": dict(prefs_values), "edits": edits_payload}
    if len(projects) > MAX_CATALOG_ASSETS:
        raise AssetDecisionJournalError(
            f"journal exceeds MAX_CATALOG_ASSETS ({MAX_CATALOG_ASSETS}) project records"
        )
    _write_envelope(target, envelope)


def drop_record(path: _PathLike, project_path: str) -> None:
    """Remove ``project_path``'s record from ``path``'s journal, if present.

    **A no-op, not an error, when the file is absent or carries no record for
    ``project_path``** — retire-on-save must be idempotent (ADR-0062 §2;
    plan.md §3.15 (3)(8)).

    Raises:
        AssetDecisionJournalError: If ``project_path`` is not a non-empty
            string, an existing journal is malformed, or the file cannot be
            written.
    """
    if not isinstance(project_path, str) or not project_path:
        raise AssetDecisionJournalError("project_path must be a non-empty string")
    target = Path(path)
    if not target.exists():
        return
    envelope = _read_envelope(target)
    projects = envelope["projects"]
    if project_path not in projects:
        return
    del projects[project_path]
    _write_envelope(target, envelope)
