# ADR-0032 — Local-first / cloud-optional asset-storage abstraction (`BlobBackend` port)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-11-team-asset-management` (`REQ-P11-DATA-006`; anchors `DATA-001/-004/-005`) |
| Supersedes | — |
| Superseded by | — |
| Relates to | spec `specs/phase-11-team-asset-management/spec.md` §4b/§10 (CL-3), prior internal research §4.2/§6, constitution Article I / VII, ADR-0026/0027 (Phase-10 provider isolation), ADR-0030 (CAS) |

## Context

CL-3 was adjudicated: the asset library is **local-first, cloud optional**. It must work **fully
offline against a local store by default** (no cloud requirement); when a **Phase-10 provider is
connected**, the same CAS/library **MAY** be backed by **Phase-10 shared storage** (the "team"
dimension), behind **an abstraction layer that hides local-vs-cloud** so callers above the port are
unchanged and **nothing above the port names a specific provider** (Phase-10 provider isolation,
Article I / ADR-0026). This ADR fixes that abstraction seam.

## Decision

### 1. One `BlobBackend` port; the CAS composes it (REQ-P11-DATA-006, Article I)

- A new `data/asset_storage.py` defines a single provider-agnostic **`BlobBackend` ABC** — the minimal
  content-addressable verb set: `put_blob(content_hash, blob) -> None` (write-once/dedup),
  `get_blob(content_hash) -> bytes`, `has_blob(content_hash) -> bool`. **No provider SDK type,
  credential/token type, HTTP/network type, or `data/cloud/` type appears in these signatures** — the
  Phase-10 provider-isolation invariant (ADR-0026 §1) extended to assets.
- The ADR-0030 `ContentAddressableStore`, the catalog store, and the revision store all sit **above**
  this port and are **unchanged** whether the backend is local or shared. The abstraction **selects**
  the backend; callers never branch on it.

### 2. `LocalBlobBackend` is the default (offline-first); `SharedBlobBackend` is optional (REQ-P11-DATA-006, CL-3)

- `LocalBlobBackend` (in `data/asset_storage.py`) — a local-FS / in-memory content-addressed backend;
  the **default**, requiring no cloud, no network, no credentials. This path ships fully on it and is
  CI-testable headlessly.
- `SharedBlobBackend` (in `data/asset_shared_backend.py`) — implements the **same
  `BlobBackend`** by composing the shipped Phase-10 `data/cloud/` shared storage
  (`shared_adapter` / `CloudPort`). It is selected **only when a Phase-10 provider is connected**;
  otherwise the local backend serves everything. When cloud-backed, the Phase-10 provider-isolation +
  untrusted-input + membership posture applies, and every fetched blob is **content-hash-verified**
  (ADR-0030 §4) — a mismatch is rejected.

### 3. Untrusted-input + path defence carry through (REQ-P11-DATA-002/-006, Article VII, research §5)

- Blobs fetched from **either** backend are content-hash-verified before use. Catalog/sidecar loads and
  imported references are schema+caps validated (`MAX_CATALOG_ASSETS`, `MAX_TAGS_PER_ASSET`,
  `MAX_TAG_BYTES`, `MAX_METADATA_BYTES`, `MAX_BLOB_BYTES`), **never** `eval`/`exec`'d, and every
  referenced path is **path-traversal-defended**: `resolved = (library_root / candidate).resolve()`
  then containment via `resolved.relative_to(library_root)` / `os.path.commonpath` — `..` escapes and
  absolute-path escapes rejected with a domain error (research §5; the shipped PIO-1 /
  `MAX_CLOUD_PROJECT_BYTES` defensive precedent).

### 4. Three-layer placement (Article I; `check_layering`/`check_cycles` must stay exit 0)

| Layer | Module | Responsibility | Qt |
| --- | --- | --- | --- |
| `data/` | `asset_storage.py` **(new)** | `BlobBackend` ABC + `LocalBlobBackend` (offline default); the local-vs-cloud seam; `AssetStorageError` | **zero** |
| `data/` | `asset_shared_backend.py` **(new)** | `SharedBlobBackend(BlobBackend)` composing `data/cloud/` shared storage; hash-verified fetch; **no provider type above the port** | **zero** |

- Edges point **down**: `asset_storage → logic/constants`; `asset_shared_backend →
  {data/cloud/*, data/asset_storage, logic/content_hash, logic/constants}`; `asset_cas` (ADR-0030)
  composes a `BlobBackend`. No `logic → data`, no `→ ui`/Qt. `data/cloud/` is an existing governed
  `data/` subpackage (zero Qt). No new layering rule is needed and no cycle is introduced (verified —
  baseline clean, 158 layering / 159 cycles, exit 0, 2026-07-04).
- **Grep guard:** no module above the port (`logic/`, `ui/`, and the CAS/catalog/revision stores) names
  a specific cloud provider or imports `data/cloud/providers/*` — enforced by review + `check_layering`
  (provider SDKs already confined to `data/cloud/providers/*` by ADR-0026).

## Alternatives Considered

- **Cloud-required library.** Rejected per CL-3 — the library must work fully offline; cloud is an
  optional team backing, selected only when a provider is connected.
- **Branch on local-vs-cloud in the catalog/CAS/UI.** Rejected (Article I) — the `BlobBackend` port
  hides the choice; callers are backend-agnostic, exactly as Phase-10 callers are provider-agnostic
  above `CloudPort`.
- **A new Phase-11 cloud provider port.** Rejected — the shipped Phase-10 `data/cloud/` shared storage
  is the substrate (Article X reuse); `SharedBlobBackend` composes it rather than duplicating provider
  plumbing.
- **Trust cloud-fetched blobs.** Rejected (Article VII) — content-hash verification on every fetch is
  the tamper/corruption defence (research §5), identical in kind to the PIO-1 untrusted-load posture.

## Consequences

**Positive.** The library is genuinely offline-first and CI-testable with no network/credentials; the
optional team dimension is a single new backend behind an unchanged port; provider isolation and
untrusted-input defence extend cleanly from Phase 10; adding a future backend is a new `BlobBackend`
implementation, no caller change (Article XI).

**Negative / risk.** `SharedBlobBackend` couples to the shipped `data/cloud/` surface; if that surface
changes, the backend adapts (the port above it does not). Content-hash verification on every fetch is a
small per-fetch cost (accepted — it is the tamper defence). Consistency/conflict semantics of a shared
CAS are bounded to Phase-10's model; Phase 11 adds no new consistency protocol (out of scope, spec §6).

## Grounding

- Spec §4b (DATA-006, CL-3), §10 (CL-3 adjudication); `acceptance.md` ("Asset-library storage
  substrate — local-first, cloud optional"); `traceability.md`.
- Prior internal research §4.2 (portability + shared-store backing), §6 (feasibility; wiring CAS into
  Phase-10 shared storage is the integration-tested seam), §5 (untrusted input / hash verification).
- Shipped tree: `data/cloud/{port,shared_adapter,fake_adapter}.py` (provider-agnostic port + fake
  adapter, zero Qt), provider SDKs confined to `data/cloud/providers/*`. Constitution Article I / VII,
  Article X (Phase-10 reuse), Article XI. ADR-0026 (provider isolation), ADR-0030 (CAS + content hash).
