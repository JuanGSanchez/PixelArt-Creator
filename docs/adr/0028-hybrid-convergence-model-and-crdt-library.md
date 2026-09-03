# ADR-0028 — Hybrid convergence model + CRDT library: tree/sequence CRDT for structure, tile/region-LWW for raster, and where the model lives (Slices B/C)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-10-cloud-collaboration` (Slices B/C) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0026 (cloud-port), ADR-0027 (sync-backend + transport) |

## Context

Collaboration (Slice B) and real-time (Slice C) require concurrent edits to a `.pixproj` to **converge
deterministically**. The spec adjudicated (CL-B5) a **HYBRID** model: a **sequence/tree CRDT for
STRUCTURED metadata** (layer tree, frame list, tilemap metadata) + **per-TILE/REGION last-writer-wins
(LWW) for RASTER pixel buffers**, ordered by a **logical-clock + site-id** tiebreak, commutative and
convergent (strong eventual consistency), scalable to 8K without per-pixel overhead, and enabling git-like
art branching (REQ-P10-LOGIC-006/-007). This reconciles the shipped `logic/history.py` command stream
(HIS-1) over the shipped `Document` (DOC-1). The concrete CRDT library, the raster tile-partition scheme,
and whether CRDT state rides inside the `.pixproj` envelope or a sidecar are HOW decisions deferred to this
ADR (spec BF-4). Prior research grounds the landscape (§4): sequence/tree CRDTs (Yjs/YATA via **pycrdt**,
or **Automerge**) for structure; **tile-partitioned LWW-Register** for raster; determinism via
logical-clock + site-id; Yjs = fastest with a built-in awareness/presence protocol; Automerge = git-like
branching/history "for free". This ADR rules the model's placement, the library, the raster partition, the
determinism contract, the branching model, and the CRDT-state persistence.

## Decision

### 1. Placement: the convergence model is pure/deterministic in `logic/` (Article I)

- **`logic/convergence.py`** (ZERO-Qt, pure) holds the HYBRID model: the structured-metadata CRDT wiring
  and the raster tile/region-LWW registers, both deterministic (no wall-clock, no randomness, no locale,
  order-stable iteration). It is the batch/off-loop Slice-B tier (REQ-P10-LOGIC-006, Article VI).
- **`logic/realtime_apply.py`** (ZERO-Qt, pure) is the Slice-C apply layer: it applies remote CRDT/OT
  updates to the local `Document` via the convergence model and supports git-like branching
  (REQ-P10-LOGIC-007). Its remote-patch apply **re-enters the 16 ms per-frame budget** — the Rendering & Performance
  FLAG-PERFRAME obligation (ADR-0027 §7).
- **`logic/cloud_validation.py`** (ZERO-Qt, pure) validates CRDT-update blobs/presence/comment payloads
  (schema + caps). Being pure `logic/`, all three are importable by **both** the client `data/cloud/`
  transport and the `sync_backend/` (ADR-0027 §4) — the backend reuses the validators/message schema
  without importing `data/`. `check_cycles` stays green: `logic/` never imports `data/`/`ui/`; the CRDT
  library and NumPy are third-party pure deps (allowed in `logic/`, like the shipped NumPy usage).

### 2. Library: pycrdt for the structured tree/sequence CRDT + presence (BF-4)

- **Structured metadata** (layer tree, frames, tilemap metadata) converges through **`pycrdt`** — the
  Python bindings to `y-crdt` / `yrs` (the Rust port of Yjs). Rationale (dispatch: prefer well-maintained
  libs): pycrdt is the best-maintained Python CRDT (the `y-crdt` org; used across the Jupyter real-time
  ecosystem), the fastest CRDT family (research §4.3), transport-agnostic (its encoded updates fit the
  `TransportPort`, ADR-0027 §3), and ships a built-in **awareness/presence** protocol for the ephemeral
  cursors/selection kept OUT of the persisted document (REQ-P10-UI-011/-013). It imposes **no Qt** and runs
  in ZERO-Qt `logic/`.
- **Raster pixel buffers** are **NOT** placed in a sequence CRDT (tombstone/metadata blow-up — research
  §4.2). They converge through our own **per-tile/region LWW-Register**, implemented in pure NumPy over the
  shipped buffer: the canvas is partitioned into `CRDT_TILE_SIZE_PX` tiles; each tile is an LWW-Register
  keyed by `(logical_clock, site_id)`. Concurrent edits to *different* tiles both survive; concurrent edits
  to the *same* tile resolve deterministically by the logical-clock + site-id tiebreak. This is our code,
  not the library's — it scales to 8K with no per-pixel CRDT metadata (spec 8K-scalable requirement).

### 3. Determinism + branching contract (REQ-P10-LOGIC-006/-007)

- **Total, reproducible determinism:** given the same operation set, all replicas converge to a
  **byte-identical `Document`** regardless of delivery order (strong eventual consistency), asserted by
  applying permuted operation orders and comparing (SC-L006-1). Tiebreaks are logical-clock + stable
  site-id; no wall-clock/random/locale.
- **Git-like branching (REQ-P10-LOGIC-007):** a branch is a **forked CRDT document** (a cloned pycrdt doc +
  a cloned tile-LWW register set). Concurrent edits on the branch and mainline **merge back conflict-free**
  by exchanging/applying CRDT updates (the CRDT converges — no manual conflict resolution); branch history
  is reconstructable from the ordered update log the backend persists (ADR-0027 §4). This satisfies the
  "clone → concurrent edit → merge" contract with pycrdt's convergence; **Automerge's native
  branch/diff/history is the documented fallback** if a richer diff/attribution UI is later required.

### 4. CRDT-state persistence: a sidecar, not inside `.pixproj` (BF-4)

CRDT structured-metadata state and the tile-LWW clocks live in a **sidecar** collaboration document
(per shared project), **not** embedded in the `.pixproj` (which stays the plain PIO-1 artwork sync unit —
REQ-P10-DATA-002, no schema bump). The `.pixproj` remains the materialised, human-openable artwork; the
sidecar carries the CRDT metadata the collaboration/real-time layers need. This mirrors the ADR-0025 /
ADR-0026 sidecar precedent (session/version artifacts kept out of the artwork file). Presence is ephemeral
and **never** persisted into either.

### 5. Constants (Article II, BF-3)

New named constants in `logic/constants.py` (values are architecture defaults; the implementation adds them, no literals):
`MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`, `MAX_COMMENTS_PER_PROJECT`, `MAX_CRDT_UPDATE_BYTES`,
`CRDT_TILE_SIZE_PX`. The backend's validation caps (ADR-0027 §6) reuse these same named bounds.

## Alternatives Considered

- **Automerge as the primary structured CRDT.** Strongly considered (native git-like branch/diff/history,
  research §4.6). Deferred to fallback: the `automerge-py` bindings are less consistently maintained than
  pycrdt, and the fork-doc + update-merge model over pycrdt already satisfies the branching contract
  (clone→edit→merge, conflict-free, reconstructable via the persisted update log). Kept as the documented
  escalation if native diff/attribution becomes a hard UI requirement.
- **A single CRDT over the whole `.pixproj` (structure + raster).** Rejected: sequence/tree CRDTs blow up
  on megabytes of raster (tombstones/metadata); the hybrid split is explicit research guidance.
- **Per-pixel LWW.** Rejected: not 8K-scalable (per-pixel CRDT metadata); tile/region partitioning is the
  documented way to scale LWW (research §4.2).
- **OT instead of CRDT.** Rejected: OT needs a central authoritative ordering server and has complex undo;
  CRDTs fit a local-first, offline-capable desktop app that syncs opportunistically (research §4.1).
- **Embedding CRDT state inside `.pixproj` (schema bump).** Rejected (BF-4): couples the artwork file to
  collaboration state and would fork PIO-1; a sidecar keeps `.pixproj` stable (REQ-P10-DATA-002).

## Consequences

**Positive.** Deterministic, commutative, 8K-scalable convergence with a clean split (well-maintained
pycrdt for structure + presence; our pure NumPy tile-LWW for raster); branching without manual conflict
resolution; the model is pure `logic/`, unit-testable headless over an in-memory transport and reusable by
the backend; `.pixproj` (PIO-1) is untouched. Determinism is directly assertable (permuted-order →
byte-identical `Document`).

**Negative / risk.** Two new runtime deps (`pycrdt`; `websockets` per ADR-0027) — a DevOps/architecture manifest
decision; prior research warns CRDT-lib APIs evolve, so **pin versions and re-verify the raster/binary
handling story before committing the tile-partition scheme**. The tile-LWW + tree-CRDT seam over the
shipped `Document`/`history` (HIS-1) is the main correctness risk — mitigated by the determinism/
commutativity property tests (SC-L006-1, SC-L007-1) which are the gate. Slice-C real-time apply carries the
Article VI per-frame risk (Rendering & Performance FLAG-PERFRAME).

## Grounding

- Spec §4b (REQ-P10-DATA-009, REQ-P10-LOGIC-006), §4c (REQ-P10-DATA-010, REQ-P10-LOGIC-007), §5 (Article VI
  split, Article II BF-3), §8 (BF-3, BF-4, FLAG-PERFRAME), §9 Article I/II/VI/VII, §10.2 (CL-B5), §11
  (SC-L006-1, SC-L007-1/-2, SC-D010-1); `traceability.md` HIS-1/DOC-1 forward traces, BF-3/BF-4.
- Prior research §4.1 (CRDT vs OT), §4.2 (which CRDT for which part; tile-partitioned LWW), §4.3 (pycrdt/yrs,
  Automerge), §4.4 (determinism / logical-clock + site-id), §4.5 (awareness/presence, transport), §4.6
  (Automerge git-like branching), §6 (in-memory-transport convergence tests).
- Shipped `logic/document.py` (DOC-1), `logic/history.py` (HIS-1), `logic/pixel_buffer.py` (NumPy buffer),
  `data/project_io.py` (PIO-1). Constitution Article I (pure logic/), II (constants), IV (deterministic
  headless tests), VI (per-frame split), VII (validated CRDT blobs), XI. ADR-0025/0026 (sidecar precedent),
  ADR-0027 (transport + backend reuse of pure validators).
