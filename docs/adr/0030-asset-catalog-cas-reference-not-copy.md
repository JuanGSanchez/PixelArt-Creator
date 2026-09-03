# ADR-0030 — Asset catalog (stable AssetId + sidecar), content-addressable store, and reference-not-copy reuse

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-11-team-asset-management` (`REQ-P11-DATA-001/-004/-005/-007`, `REQ-P11-LOGIC-001/-006`) |
| Supersedes | — |
| Superseded by | — |
| Relates to | spec `specs/phase-11-team-asset-management/spec.md` §2/§4/§4b/§10 (CL-1/CL-2), prior internal research (an internal research note, outside this repository) §1/§3/§4, constitution Article I / II / VII / X / XI, ADR-0026 (cloud version envelope), ADR-0025 (sidecar-vs-embedded precedent) |

## Context

Phase 11 must catalog the already-shipped entities (Phase-1 `Document`/`PixelBuffer`, Phase-5
`Frame`/named animation, Phase-6 `Tileset`/`Tilemap`, palettes) as reusable **assets**, keep a
**version history** of each asset's revisions, and let an asset be **reused across projects without
duplicating its bytes** (spec ROADMAP "Done means"). CL-1 was adjudicated (version
control = **HYBRID reusing Phase 10**: content-hash change detection + append-only
content-addressable revision store, NOT the live-collab CRDT) and CL-2 (cross-project reuse = **CAS +
reference-not-copy**), grounded in prior research. This ADR fixes the HOW: the catalog identity
model, the content-hash primitive, the content-addressable store (CAS), the reference-not-copy
semantics + export, and the asset-revision DAG.

**Key finding on "reuse Phase 10" — the primitive does not yet exist.** A survey of the shipped tree
shows Phase 10 has **no content-hashing or content-addressable-storage primitive**:
`logic/version_history.py` keys versions by an **opaque `version_id` + `created_marker`**, not by a
content hash; `hashlib` appears only in `data/export_io.py` (deterministic filename digests) and
`data/cloud/auth.py` (PKCE `S256`). Therefore Phase 11 **introduces** the content-hash + CAS
primitives — it does not import a pre-existing one. "Reuse Phase 10" (CL-1) is honoured at the level of
**shape and pattern**, not a shared function: the asset-revision model reuses the *immutable,
ordered-history* shape of `logic/version_history.py` (append→new history, deterministic order, bounded,
`ValueError`-family error) applied at **asset granularity** with a `content_hash`+`parent_hash` DAG;
the storage substrate reuses the *provider-agnostic port + defensive untrusted-load* pattern of
`data/cloud/port.py`. This is called out so the implementation builds new modules rather than hunting for a
non-existent shared hasher.

## Decision

### 1. Catalog identity: stable `AssetId` + per-asset sidecar — never by path (REQ-P11-DATA-001, research §1)

- Every catalog entry carries a **stable `AssetId`** (a UUID string, stable for the asset's life,
  decoupled from filesystem path) — the Unity-GUID / Godot-UID role (research §1.1). All cross-asset
  references (dependency edges, cross-project references) are stored **as the `AssetId` + a pinned
  `content_hash`**, never as a path. A move/rename therefore does **not** break a reference (only a
  deleted id or a content-hash mismatch does — ADR-0031 / REQ-P11-LOGIC-005).
- The catalog record is a pure `logic/` dataclass (`AssetDescriptor`, REQ-P11-LOGIC-001):
  `asset_id`, `kind` (`AssetKind` enum — module-local vocabulary per ADR-0001), `name`,
  `tags: frozenset[str]`, `metadata: Mapping[str, scalar]`, `content_hash`, and an advisory `path`
  (display/fallback only). `path` is resolved **through** `asset_id`, never authoritative.
- Persistence is a **per-asset sidecar** (one small JSON record per asset, travelling with it — the
  common thread across Unity/Godot/Unreal, research §1.1; the ADR-0025 sidecar precedent) plus a
  catalog index. The catalog stores **references + metadata**, not a copy of the asset payload.

### 2. The asset payload reuses PIO-1 — no new payload serialiser (REQ-P11-DATA-007, Article I)

The asset **content** is persisted through the shipped `data/project_io.py` (PIO-1) `.pixproj`
serialiser and the shipped entity models it carries. The catalog composes PIO-1 to load/store an
asset's bytes and defines **no second serialiser for the payload**. The catalog index/sidecar schema
is a `data/` structure **over references**, not a fork of the payload format. A cataloged asset loaded
back reconstructs an **equivalent** shipped entity via PIO-1, validated defensively (Article VII, §5).

### 3. Content hash = the shared change-detector + CAS key (REQ-P11-DATA-004, research §3/§4)

- A new pure `logic/content_hash.py` computes a deterministic hash of **canonicalized asset bytes** via
  stdlib **`hashlib`** (SHA-256; already a project dependency-free stdlib, used in `export_io`/`auth`).
  `content_hash(blob: bytes) -> str` is the single primitive; equal canonicalized bytes ⇒ equal hash ⇒
  "unchanged" (no new revision, no dependent re-validation). No wall-clock / randomness / locale.
- Canonicalization is defined once (byte-exact serialisation of the PIO-1 payload) so the hash is
  stable across sessions and platforms — the deterministic "did this asset change?" signal that drives
  **both** revision creation (§6) and break re-validation (ADR-0031).

### 4. Content-addressable store (CAS): bytes stored once, keyed by hash (REQ-P11-DATA-004/-005, research §4)

- A new `data/asset_cas.py` `ContentAddressableStore` stores each asset's bytes **once** keyed by its
  `content_hash` (the Git-blob / IPFS-CID model, research §4.1). Writing an existing hash is a
  **dedup no-op**. Every blob is size-capped by `MAX_BLOB_BYTES` (Article VII); a fetched blob is
  **content-hash-verified** (recompute + compare) — a hash mismatch is rejected (tamper/corruption
  defence, research §5).
- The CAS composes a `BlobBackend` port (ADR-0032) so the same store runs against a local backend
  (default, offline) or an optional Phase-10-shared backend, transparently.

### 5. Reference-not-copy + export bundling (REQ-P11-DATA-005, research §4.2)

- A project **references** an asset by `(asset_id → content_hash)`, **never a byte copy** — this is the
  precise meaning of "reuse without duplication" (CL-2). Two projects referencing the same content
  share the single CAS blob (dedup no-op on the second reference).
- **Export** (`data/asset_export.py`) resolves a project's reference set and **bundles exactly the
  referenced blobs**, producing a self-contained, portable artifact (research §4.2). Day-to-day the
  project points into the shared/local CAS (deduped); export materialises a standalone copy.
- The reference is a lightweight catalog/sidecar record over `(asset_id, content_hash)` — **not** a
  `.pixproj` payload-format fork (consistent with §2 / REQ-P11-DATA-007). Whether the per-project
  reference set rides in the `.pixproj` or a companion sidecar is an implementation detail bound
  by "no new payload serialiser"; the sidecar carrier (ADR-0025 precedent) is the recommended default
  to avoid a schema bump.

### 6. Asset-version model: append-only, content-hash-addressed revision DAG (REQ-P11-DATA-004/LOGIC-006, CL-1)

- A new pure `logic/asset_version.py` models an asset's history as an **ordered, immutable revision
  DAG** — the *shape* of `logic/version_history.py` applied at asset granularity. A revision descriptor
  is `AssetRevision(asset_id, content_hash, parent_hash, created_marker, author)` (an opaque monotonic
  `created_marker`, never a clock read inside the pure module — the Phase-10 precedent). The model
  exposes the ordered history, the head revision, and a **content-hash comparison** ("changed" /
  "unchanged"). Bounded by `MAX_ASSET_VERSIONS`; `append` yields a *new* history (no in-place
  mutation). Deterministic, no Qt / CRDT dependency.
- The append-only revision **store** (`data/asset_revision_store.py`) records the immutable descriptors
  and stores each revision's bytes **once in the CAS** (§4). Re-recording identical canonicalized bytes
  is a dedup no-op (no new revision). A prior revision is retrievable and its bytes verify against the
  recorded hash. **Asset revisions never route through the live-collab CRDT** (the CRDT remains for
  concurrently-edited live documents only, CL-1); whole-asset binary revisions are content-hash
  snapshots.

### 7. Three-layer placement (Article I; `check_layering`/`check_cycles` must stay exit 0)

| Layer | Module | Responsibility | Qt |
| --- | --- | --- | --- |
| `logic/` | `content_hash.py` **(new)** | deterministic content hash over canonicalized bytes (stdlib `hashlib`); change-detector + CAS key | **zero** |
| `logic/` | `asset_catalog.py` **(new)** | `AssetKind` (module-local enum), `AssetDescriptor`, `AssetCatalog` (add/remove/get/enumerate) — pure | **zero** |
| `logic/` | `asset_version.py` **(new)** | immutable ordered revision DAG (`AssetRevision`/`AssetVersionHistory`) + hash comparison | **zero** |
| `data/` | `asset_cas.py` **(new)** | content-addressable blob store over a `BlobBackend`; write-once dedup; hash-verified fetch; `MAX_BLOB_BYTES` cap | **zero** |
| `data/` | `asset_catalog_io.py` **(new)** | catalog + per-asset sidecar persistence; composes PIO-1 for payloads (no new serialiser); schema+caps validation; path-traversal guard; `AssetCatalogError(ProjectIOError)` | **zero** |
| `data/` | `asset_revision_store.py` **(new)** | append-only revision store over `asset_cas`; immutable descriptors; NOT via CRDT | **zero** |
| `data/` | `asset_export.py` **(new)** | resolve a project's reference set → bundle referenced CAS blobs; import defence | **zero** |
| `ui/` | asset-library / version-browser / reuse surfaces | present the catalog/versions/reuse; bind to `logic/`+`data/`; no domain logic | Qt |

One-way edges only: `logic/asset_*` → `logic/{constants, content_hash}`; `data/asset_*` →
`logic/*` + `data/{project_io, asset_cas}` (+ `data/cloud/*` in the shared backend, ADR-0032); `ui/` →
`logic/`+`data/`. No `logic → data`, no `→ ui`/Qt, no cycle. Content-hash is a pure leaf over
`constants`.

## Alternatives Considered

- **Catalog assets by filesystem path.** Rejected — a move/rename would break every reference; the
  entire engine industry (Unity/Godot/Unreal) catalogs by stable id + sidecar for exactly this reason
  (research §1). Path is kept advisory only.
- **Route asset revisions through the Phase-10 live-collab CRDT (research §3.1 Option A).** Rejected
  per CL-1 — the CRDT is for fine-grained concurrent mutation of a live document; whole-asset binary
  snapshots do not need CRDT granularity and would bloat CRDT state. The append-only CAS revision DAG
  (Option B / hybrid) is simpler, immutable, and gives dedup for free.
- **Copy asset bytes into each referencing project.** Rejected per CL-2 — duplicates bytes, defeats
  "without duplication," and desyncs on edit. Reference-by-hash + export-bundles-blobs gives dedup +
  portability (research §4.2).
- **Define a new asset-payload serialiser.** Rejected (Article I / REQ-P11-DATA-007) — PIO-1 is the
  canonical payload form; the catalog is metadata/index over references, not a payload fork.
- **Reuse `logic/version_history.CloudVersion` directly for asset revisions.** Rejected — it keys by an
  opaque `version_id`, has no `content_hash`/`parent_hash` DAG, and carries cloud-envelope fields
  (`remote_revision_id`, `size_bytes` vs `MAX_CLOUD_PROJECT_BYTES`). The asset model reuses its
  *shape*, not its type, at asset granularity with content-hash addressing.

## Consequences

**Positive.** Stable-id + sidecar identity makes moves/renames non-breaking; the content-hash primitive
is one deterministic pure function driving revisions, dedup, and break-detection; CAS gives dedup +
portability for free; reference-not-copy realises "reuse without duplication" precisely; PIO-1 reuse
keeps one payload format (Article I); ~80 % of the surface is pure-logic and unit-testable (research
§6); the whole core runs fully offline and headless in CI.

**Negative / risk.** Phase 11 **introduces** the content-hash + CAS machinery (it is not a pre-existing
Phase-10 primitive) — a genuine new-code scope item, not a thin reuse. Canonicalization must be defined
byte-exactly or the hash is unstable across platforms/sessions (the implementation obligation; property-tested by
the test suite). Sidecar loss orphans an asset's identity (mitigated: sidecars are committed/bundled with the
asset, the engine-standard discipline). The reference carrier vs `.pixproj` decision is deferred to
the implementation within the "no new serialiser" bound.

## Grounding

- Spec §2 (in-scope catalog/CAS/reuse), §4 (DATA-001/-007, LOGIC-001), §4b (DATA-004/-005, LOGIC-006),
  §10 (CL-1/CL-2 adjudications); `acceptance.md` (catalog/versioning/reuse features); `traceability.md`.
- Prior internal research §1 (catalog by stable id + sidecar), §3 (content hashing; reuse-Phase-10 vs
  separate revision store; the hybrid), §4 (CAS + reference-not-copy + export bundling), §5 (untrusted
  input), §6 (feasibility: pure-logic core).
- Shipped tree: `logic/version_history.py` (opaque-id ordered-history *shape*, no content hash),
  `data/project_io.py` (PIO-1), `logic/{document,animation,tileset,tilemap}.py` (tracked entities),
  `hashlib` in `export_io`/`cloud/auth`. Constitution Article I/II/VII/X/XI. ADR-0025 (sidecar), ADR-0001
  (module-local vocabulary), ADR-0026 (cloud version envelope).
