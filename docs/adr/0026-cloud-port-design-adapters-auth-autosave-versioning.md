# ADR-0026 — Cloud-port design: the one `data/cloud/` port, adapter contract, keyring auth, atomic autosave/recovery, and cloud version model (Slice A)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-10-cloud-collaboration` (Slice A) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0027 (sync-backend placement + real-time), ADR-0028 (hybrid convergence + CRDT lib) |

## Context

Phase-10 Slice A adds a cloud-sync layer over the **shipped** `.pixproj` (PIO-1 — `data/project_io.py`:
defensive `eval`-free load, `ProjectIOError`, `_SUPPORTED_VERSIONS = 1..5`, zlib+base64 payloads,
`pathlib`). The spec fixes the observable contracts (one provider-agnostic port; `.pixproj` round-trip;
ordered version history; autosave/recovery surviving an unclean restart; a fully-testable fake adapter;
untrusted-cloud-data defence; provider isolation) and defers the HOW to this ADR (spec DEP-2, BF-1, BF-2;
§10.2 CL-B2/CL-B3). The Researcher grounds the shape (report
`docs/subagent-report-the-researcher-a80a5c6a-20260704T102747.md`): Drive v3 / Graph / Dropbox v2 share
auth/upload/download/list/revisions/change-tracking with capability differences (revision naming,
retention, count caps, per-file vs whole-drive change feeds) modelled as an **opaque cursor**; desktop
auth = Authorization Code + **PKCE (S256)** over a loopback redirect (RFC 8252/7636) with **Device Grant**
(RFC 8628) fallback and **OS-keyring** token storage; autosave/recovery = **atomic temp-write + fsync +
`os.replace` + a sidecar recovery journal** discovered on restart.

This ADR rules: (1) the one port's verb set + normalized types + capability model + exception family;
(2) the adapter contract and which adapters ship in CI vs credential-gated; (3) auth + keyring token
isolation and the ZERO-Qt boundary; (4) the crash-safe autosave/recovery mechanism; (5) the cloud version
model + remote-revision mapping (BF-2); (6) untrusted-cloud-data defence (Article VII). It resolves
CL-B2 (fake adapter in CI; real providers out-of-CI) and CL-B3 (OS keyring inside the adapter).

## Decision

### 1. One port, normalized types, opaque cursor (REQ-P10-DATA-001, -007)

`pixelart_creator/data/cloud/port.py` defines **one** abstract `CloudPort` (ABC) — a ZERO-Qt `data/`
module — with a bounded verb set over an **opaque project blob** (a `.pixproj`'s bytes) keyed by a
provider-agnostic `project_id`:

- `put(project_id, blob, *, parent_version=None) -> CloudVersion` — store a new version (optimistic
  concurrency via `parent_version` where the provider supports it).
- `get(project_id, version_id) -> bytes` — fetch a specific version's bytes.
- `list_versions(project_id) -> tuple[CloudVersion, ...]` — ordered history (stable order).
- `latest(project_id) -> CloudVersion`.
- `delete(project_id) -> None`.
- `put_recovery(project_id, blob) -> None` / `get_recovery(project_id) -> bytes | None` — the
  autosave/recovery slot, **distinct** from the explicit version history.
- `capabilities() -> CloudCapabilities`.

All types are **normalized in the port** — no provider field leaks upward: `CloudVersion(version_id: str,
ordinal: int, created_marker: int, size_bytes: int, is_pinned: bool, parent_version_id: str | None,
remote_revision_id: str | None)`; `CloudCapabilities(supports_named_revisions, supports_revision_delete,
max_versions_per_call, change_feed_scope, supports_optimistic_concurrency)`; change tracking is an
**opaque `Cursor`** the port persists and replays (unifies Drive changes-token / Graph `deltaLink` /
Dropbox folder-cursor — Researcher §1.3). No provider SDK type, HTTP type, credential type, or
provider-specific exception appears in the port's public signatures, in `logic/`, or in `ui/`.

### 2. Adapter contract; fake adapter in CI, real providers out-of-CI (REQ-P10-DATA-005, CL-B2)

- **`data/cloud/fake_adapter.py`** — a local-filesystem / in-memory adapter implements the **whole** port
  (put/get/list/latest/delete/recovery + capabilities). It is the fixed, deterministic Slice-A deliverable
  and exercises the entire contract (round-trip, version history, autosave/recovery, defensive load,
  provider isolation) **headless in CI with no network and no credentials** (Article IV).
- **`data/cloud/providers/{drive,onedrive,dropbox}.py`** — real adapters implement the **same** `CloudPort`
  behind the same interface. They are **credential-gated / manually verified and OUT of the CI gate**
  (marked with an integration flag, `pytest.mark.cloud_live`, skipped by default). Adding a provider is
  adding an adapter — nothing above the port changes (REQ-P10-DATA-007, Article XI). The capability
  differences (Drive `keepForever` pins, Dropbox 100-revision cap, per-file vs whole-drive change scope)
  are surfaced through `CloudCapabilities`, never leaked as provider fields.

### 3. Auth + keyring token isolation; ZERO-Qt boundary (REQ-P10-DATA-008, CL-B3, Article VII §3)

- **`data/cloud/auth.py`** (ZERO-Qt) holds the pure, unit-testable **PKCE** crypto (`code_verifier` →
  `S256` `code_challenge`), the **loopback HTTP listener** (RFC 8252: `http://127.0.0.1:{random_port}`,
  opened only for the auth request), the token exchange/refresh, and the **Device Grant** (RFC 8628)
  fallback. Only **launching the system browser / showing the device code** is delegated to `ui/` — never
  an embedded webview.
- **`data/cloud/token_store.py`** (ZERO-Qt) wraps the **`keyring`** library (Windows Credential Locker /
  macOS Keychain / Linux Secret Service), keyed by `provider + account`. Tokens are acquired, stored, and
  used **entirely inside `data/cloud/`** — **never** in `logic/`/`ui/`, **never committed**, **never**
  written to a `.pixproj` or a log. The port exposes only a provider-agnostic `is_connected()` notion;
  `ui/` never receives a raw token. Keying scheme (CL-B3 HOW): service name
  `pixelart-creator:cloud:{provider}`, username = the provider account id; only the **refresh token**
  (and optionally a short-lived access token) is stored.

### 4. Crash-safe autosave / recovery (REQ-P10-DATA-004, REQ-P10-LOGIC-002)

- **Atomic local write:** the autosave path writes to a temp file in the target directory →
  `flush` + `os.fsync` → `os.replace` over the target (cross-platform atomic rename; Windows-safe —
  Researcher §3.1). An interrupted autosave never corrupts the last good file.
- **Sidecar recovery journal:** the working `.pixproj` is autosaved to a discoverable sidecar
  (`<recovery_dir>/<project_id>.pixproj~` + a small journal record) via `put_recovery`. On startup the app
  scans the recovery dir; a recovery **newer than the last explicit save** is offered for restore
  (REQ-P10-UI-003), **without** overwriting the user's last explicit version until they choose. The
  sidecar is deleted on a clean save/close.
- **Pure policy:** *when* to autosave is `logic/autosave.py::should_autosave(dirty, elapsed_ticks,
  last_autosave_marker, interval_ms)` — a pure, deterministic function (elapsed time is an **input**, not
  read from a wall clock), unit-testable without Qt (REQ-P10-LOGIC-002). Interval = `AUTOSAVE_INTERVAL_MS`.

### 5. Cloud version model + remote-revision mapping (BF-2, REQ-P10-DATA-003, REQ-P10-LOGIC-003)

- Each `put` appends a new `CloudVersion` to an **ordered, immutable** history (`logic/version_history.py`
  — appending yields a new ordered tuple, deterministic iteration, bounded by `MAX_CLOUD_VERSIONS`). The
  `.pixproj` bytes are transported **as-is** — the cloud layer adds **no new serialisation format**
  (REQ-P10-DATA-002); PIO-1 is composed, not forked (Article I).
- **BF-2 resolved:** a cloud version is a small **metadata envelope** *around* the `.pixproj` bytes
  (`version_id`, `ordinal`, `parent_version_id`, `created_marker`, `size_bytes`, `remote_revision_id`),
  stored alongside — **not** inside — the `.pixproj` (the artwork file is unchanged; no `.pixproj` schema
  bump this slice). A local `local_version_id → remote_revision_id` map reconciles with provider
  `list_revisions` (Researcher §3.3); providers prune auto-revisions, so a durable version is pinned where
  `supports_named_revisions` (Drive `keepForever`).

### 6. Untrusted-cloud-data defence (REQ-P10-DATA-006, Article VII)

A `.pixproj` (or version/recovery blob) fetched from **any** source is untrusted: `.pixproj` bytes are
validated through the shipped PIO-1 defensive path (type/bounds-checked, size-validated against
`MAX_CLOUD_PROJECT_BYTES`, unknown/malformed/oversized → `ProjectIOError` or a `data/cloud/` subclass
`CloudDataError`), **never `eval`/`exec`**. Non-`.pixproj` payloads introduced by later slices
(membership/comment/presence/CRDT) are validated by the **pure** `logic/cloud_validation.py`
(schema + strict size/depth/dimension/byte caps) so the same validators can be reused by the backend
(ADR-0027). Bounds are named constants (Article II): `AUTOSAVE_INTERVAL_MS`, `MAX_CLOUD_VERSIONS`,
`MAX_CLOUD_PROJECT_BYTES`, `CLOUD_RETRY_LIMIT` (BF-1).

## Alternatives Considered

- **A serialiser per provider / a cloud-specific format.** Rejected: violates Article I (fork of PIO-1);
  the `.pixproj` is the atomic sync unit (REQ-P10-DATA-002).
- **Encrypted-file token store instead of the OS keyring.** Rejected for the default: the OS keyring is
  the Researcher's grounded default (§2.3), OS-managed and encrypted at rest; CL-B3 adjudicated keyring.
  An encrypted-file fallback stays possible behind the same `token_store` seam.
- **Versioning in-place (overwrite) instead of an ordered history.** Rejected: version history is a fixed
  capability (REQ-P10-DATA-003); the envelope model preserves ordered, retrievable, restorable versions.
- **Version metadata embedded inside the `.pixproj`.** Rejected (BF-2): couples save cadence and bloats
  the artwork file; the sidecar envelope keeps `.pixproj` stable (the ADR-0025 timelapse-sidecar precedent).
- **Shipping live provider adapters in CI.** Rejected (CL-B2): a local-first desktop cannot hermetically
  CI-test live OAuth; the fake adapter gives deterministic coverage, real adapters are integration-gated.
- **Auth via an embedded webview.** Rejected: RFC 8252 mandates the external system browser.

## Consequences

**Positive.** One clean ZERO-Qt port; providers are swappable (Article XI); the whole Slice-A contract is
deterministically CI-testable via the fake adapter with no network/credentials; tokens are OS-managed and
isolated in `data/cloud/`; autosave is crash-safe; `.pixproj` (PIO-1) is reused untouched; untrusted-cloud
data cannot execute code or crash the app. `check_layering` keeps `data/cloud/` Qt-free with no provider
leak above the port.

**Negative / risk.** Modelling every provider's capability differences behind one port is the main design
risk (Researcher: re-verify field schemas/limits at implementation time — Drive rev `v3-rev20260322`);
mitigated by `CloudCapabilities` + the fake adapter fixing the contract. Real-provider adapters carry
out-of-CI drift risk (mitigated: integration-flagged, manually verified). The keyring dependency adds a
runtime dep (`keyring`) — an AGT-09/AGT-01 manifest decision (Article VII implications: OS-managed secrets,
no plaintext).

## Grounding

- Spec `specs/phase-10-cloud-collaboration/spec.md` §4 (REQ-P10-DATA-001..008), §7, §9 Article I/VII,
  §10.1 (CL-1..CL-8), §10.2 (CL-B2/CL-B3), §11 (SC-D001-1..006-1, SC-L002-1..005-1); `traceability.md`
  DEP-2, BF-1, BF-2, PIO-1/DOC-1 forward traces.
- Researcher `docs/subagent-report-the-researcher-a80a5c6a-20260704T102747.md` §1 (provider port + opaque
  cursor + capabilities), §2 (PKCE/loopback RFC 8252/7636, Device Grant RFC 8628, `keyring`), §3 (atomic
  write + `os.replace` + sidecar recovery, revision mapping), §5 (untrusted JSON, no eval/exec, caps), §6
  (~70% offline-testable).
- Shipped `data/project_io.py` (PIO-1; `_SUPPORTED_VERSIONS`), `logic/document.py` (DOC-1). Constitution
  Article I (three-layer purity), II (constants), IV (fake adapter → CI), VII (untrusted input, no secrets),
  XI (port as extension seam). ADR-0025 (sidecar-vs-embedded precedent), ADR-0001 (module-local vocabulary).
