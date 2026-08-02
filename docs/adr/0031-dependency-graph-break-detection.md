# ADR-0031 — Asset dependency graph (DAG) and passive break-detection model

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-11-team-asset-management` (`REQ-P11-LOGIC-004/-005`, `REQ-P11-UI-005/-006`) |
| Supersedes | — |
| Superseded by | — |
| Relates to | spec `specs/phase-11-team-asset-management/spec.md` §2/§4/§4b/§10 (CL-4), Researcher report §2, constitution Article I / II / VI / VII, ADR-0030 (content hash / catalog) |

## Context

The ROADMAP "Done means" requires the dependency graph (`sprite → animation → tileset (→ tilemap)`) to
be **queryable** and to **flag a break when a referenced asset changes**. The tracked entities already
define the edges: a `Tileset` references a source-image `PixelBuffer` (sprite→tileset), a named
animation references `Frame`s built from sprites (sprite→animation), a `Tilemap` references a `Tileset`
(tileset→tilemap). CL-4 was adjudicated: break detection is a **passive flag on a reference-validation
/ query pass with triggered revalidation** — a broken reference (missing target `AssetId` or
content-hash mismatch) is flagged on query and in the dependency view and recomputed on catalog change;
live push-notification is a FUTURE enhancement, not core. This ADR fixes the graph representation, the
query model, the cycle-handling, and the break-detection pass.

## Decision

### 1. Representation: a directed graph, queried both directions (REQ-P11-LOGIC-004, Researcher §2.1)

- A new pure `logic/dependency_graph.py` models assets as **nodes keyed by `AssetId`** and references
  as **directed edges** (`animation --uses--> sprite`, `tileset --uses--> sprite`,
  `tilemap --uses--> tileset`). Each edge records the **pinned dependency `content_hash`** of the
  target at the time the edge was recorded (the break-detection input, §3).
- Two canonical queries (the Unreal Reference-Viewer shape, Researcher §2.1):
  - `dependencies_of(asset_id)` — outgoing edges: what the asset needs.
  - `dependents_of(asset_id)` — incoming edges: what breaks if the asset changes/moves/deletes.
  Both support **deterministic transitive traversal** (stable, sorted iteration order).

### 2. Cycles + depth: DAG-enforced, bounded, never a hang (REQ-P11-LOGIC-004, Researcher §2.3)

- The `sprite → animation → tileset → tilemap` chain is a **DAG**. Traversal is **cycle-safe** (DFS
  with a white/grey/black recursion-stack colouring — a back-edge is detected and **reported**, never
  an infinite loop) and **depth-bounded** by `MAX_DEPENDENCY_DEPTH` (Article II/VII). For typical
  project scales a per-edge DFS re-check on add suffices (Researcher §2.3 explicitly notes incremental
  topological ordering, Bender–Fineman–Gilbert–Tarjan, is an optimisation for large graphs, not a
  requirement); AGT-03 may add incremental cycle detection later behind the same query surface without
  an acceptance change.

### 3. Break detection: content-hash-gated reference-validation pass (REQ-P11-LOGIC-005, CL-4, Researcher §2.2/§2.3)

- A pure, deterministic `logic/break_detection.py` **reference-validation pass** walks the graph and
  flags an edge **BROKEN** when its target `AssetId` is **absent** (deleted asset) **or** its recorded
  dependency `content_hash` no longer matches the current target's content hash (Researcher §2.2). A
  valid, present, unchanged reference is **never** flagged (no false positive).
- The flag is **pull-based**: it is surfaced on the dependency **query result** and in the dependency
  **view** — never pushed as an event (live push-notification is FUTURE, CL-4). It is **recomputed on
  catalog change** (triggered revalidation).
- **Content-hash gating** limits work to dependents of nodes whose `content_hash` changed since the
  last pass (Researcher §2.3) — no full-graph rescan. The content-hash comparison is the ADR-0030
  primitive (`logic/content_hash.py`), the same signal that gates revision creation.

### 4. Three-layer placement (Article I) + performance posture (Article VI)

| Layer | Module | Responsibility | Qt |
| --- | --- | --- | --- |
| `logic/` | `dependency_graph.py` **(new)** | DAG of `AssetId` nodes + hash-pinned edges; `dependencies_of` / `dependents_of`; cycle-safe, depth-bounded traversal; `DependencyGraphError` | **zero** |
| `logic/` | `break_detection.py` **(new)** | pure content-hash-gated reference-validation pass → per-edge BROKEN flags; pull-based; `BreakDetectionError` | **zero** |
| `ui/` | dependency-graph view + break-warning surface | visualise depends-on/dependents; passive break indicator refreshed on catalog change; no domain logic | Qt |

- Edges: `dependency_graph → constants`; `break_detection → {dependency_graph, content_hash,
  constants}`. Both pure leaves reaching only downward. No `logic → data`, no `→ ui`, no cycle.
- **Article VI:** graph build, query, and the validation pass are **batch / off the interactive
  per-frame loop** (REQ-P11-LOGIC-008) — like Phases 7/8/10-A, the 16 ms `FRAME_BUDGET_MS` does not
  gate the domain op; the contract is stays-responsive (REQ-P11-UI-011), met by running non-trivial
  work off the GUI thread. **No AGT-10 per-frame directive is required for the domain model.**
  **Conditional flag (DEP-3):** *only if* a large-catalog dependency-graph **render** proves heavy
  interactively does AGT-10 assess the view's paint path (`frame-profile`) — a UI-render concern, not a
  Phase-11 acceptance change (spec §8 DEP-3).

## Alternatives Considered

- **Push-based live break alerts.** Deferred per CL-4 — a passive pull flag on query + triggered
  revalidation is the core contract; push notification is a FUTURE enhancement.
- **Full-graph rescan on every change.** Rejected — content-hash gating (revalidate only dependents of
  changed nodes) is the standard CAS "hash = change detector" trick (Researcher §2.3) and avoids O(N)
  rescans.
- **Store edges by path / resolve at walk time.** Rejected — edges are `AssetId` + pinned
  `content_hash` (ADR-0030) so a move/rename is not a break; only a deleted id or a hash change is
  (Researcher §2.2).
- **Incremental topological ordering (BFGT) now.** Deferred — a per-edge DFS re-check suffices at
  project scale (Researcher §2.3); the incremental algorithm is an optimisation addable behind the same
  query surface later (Article XI).

## Consequences

**Positive.** Both-direction queries answer "what does this need?" and "what breaks if I change it?";
cycles are detected and reported, never hung; break-detection is a pure, deterministic, false-positive-free
pass gated by the content-hash signal; the whole model is fixture-driven and unit-testable with zero Qt
(Researcher §6); moves/renames never break (id + hash edges).

**Negative / risk.** Pull-based flags mean a break surfaces on the next query/catalog-change, not
instantly (accepted per CL-4). A very large catalog graph *view* may need an AGT-10 render assessment
(DEP-3, conditional) — the domain model itself stays off-loop. Content-hash gating requires the graph
to track a per-node last-seen hash (a small bookkeeping cost, bounded by `MAX_CATALOG_ASSETS`).

## Grounding

- Spec §2 (dependency-graph in scope), §4 (LOGIC-004), §4b (LOGIC-005, CL-4), §8 (DEP-3), §10 (CL-4);
  `acceptance.md` ("Dependency graph is queryable", "Break detection — passive flag …");
  `traceability.md`.
- Researcher report §2 (graph model; depends-on/dependents-of; break = missing id or hash mismatch;
  content-hash gating; cycle detection / incremental topo-order as optimisation).
- Constitution Article I (layering), II (`MAX_DEPENDENCY_DEPTH`), VI (batch/off-loop; conditional
  render flag), VII (bounded traversal). ADR-0030 (content-hash primitive + `AssetId` edges).
