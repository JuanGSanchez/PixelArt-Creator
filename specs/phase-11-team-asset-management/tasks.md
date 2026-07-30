# Tasks — Phase 11: Team & Asset Management

| Field | Value |
| --- | --- |
| Feature | `phase-11-team-asset-management` |
| Author | AGT-01 (Architecture) via `sdd-tasks` |
| Date | 2026-07-04 |
| Over | `plan.md` — **slice-by-slice**, each an independently gate-green, CI-green shippable increment. Slice 1 (content-hash + CAS/dedup + catalog(stable-id+sidecar) + tagging + search/filter + library/tagging/search UI) → Slice 2 (dependency graph + break-detection + graph view + break surface) → Slice 3 (version control + cross-project reuse/export + optional cloud backing + version-browser + reuse UI). |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII). **NO implementation begins until C1 is green — this gate is the blocker.** Each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table: AGT-03 logic/data code, AGT-04
logic/data tests, AGT-05 UI code, AGT-06 UI/a11y/QA tests, AGT-07 string audit/i18n, AGT-08 docs, AGT-09
pyproject/CI/commits, AGT-01 architecture/analyze/gate. One owner per task; deterministic sub-steps name
their script. Every REQ maps to ≥1 impl + ≥1 test/verify task. Per-slice flow: **AGT-03 logic/data +
AGT-04 tests → AGT-05 ui + AGT-06 QA/a11y + AGT-07 i18n → AGT-08 docs → AGT-01 final gate → AGT-09
commit.**

---

## Slice 1 — Local catalog core (content-hash + CAS/dedup + catalog + tagging + search/filter + UI)

### 11-1-logic — content-hash / catalog / tag / query pure models (`logic/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-1-01 | Add the Slice-1 numerics (`MAX_CATALOG_ASSETS=65536`, `MAX_TAGS_PER_ASSET=64`, `MAX_TAG_BYTES=128`, `MAX_METADATA_BYTES=4096`, `MAX_BLOB_BYTES=268435456`) with citations. **Names DISTINCT from every shipped constant (BF-1).** | AGT-03 | `logic/constants.py` | — | LOGIC-007 / plan §8 | todo |
| T11-1-02 | `logic/content_hash.py` (new): `content_hash(blob)->str` (stdlib `hashlib` SHA-256 over canonicalized bytes), `same_content(a,b)`; deterministic (no wall-clock/random/locale); `ContentHashError`. **Define canonicalization byte-exactly.** Zero Qt. | AGT-03 | `logic/content_hash.py` | T11-1-01 | DATA-004 (primitive), LOGIC-006 / acceptance "content-hash comparison" | todo |
| T11-1-03 | `logic/asset_catalog.py` (new): `AssetKind` (module-local enum), `AssetDescriptor` (id/kind/name/tags/metadata/content_hash/path), `AssetCatalog` (add ≤ `MAX_CATALOG_ASSETS` / remove / get→None-on-miss / entries deterministic); pure; `AssetCatalogModelError`. Zero Qt. | AGT-03 | `logic/asset_catalog.py` | T11-1-02 | DATA-001, LOGIC-001 / "Asset catalog persistence and retrieval" | todo |
| T11-1-04 | `logic/asset_tags.py` (new): `make_add_tag`/`make_remove_tag` → pure (do, undo) pair capturing minimal prior state; idempotent (add present / remove absent = no-op); bounded by `MAX_TAGS_PER_ASSET`/`MAX_TAG_BYTES` → `AssetTagError`. Zero Qt (HIS-1 reversible-op pattern). | AGT-03 | `logic/asset_tags.py` | T11-1-01 | LOGIC-002, DATA-003 / "Tagging is reversible and idempotent" | todo |
| T11-1-05 | `logic/asset_query.py` (new): `query(catalog, name=None, tags=(), kind=None)` → stably-ordered intersection; empty query → full catalog; byte-identical across runs; `AssetQueryError`. Zero Qt. | AGT-03 | `logic/asset_query.py` | T11-1-03 | LOGIC-003 / "Search and filter over the catalog" | todo |
| T11-1-06 | Unit + property tests (headless): `content_hash` deterministic + `same_content` change-detector (identical canonicalized bytes → equal hash) [Hypothesis]; catalog add/remove/get(unknown→clean not-found)/enumerate deterministic + `MAX_CATALOG_ASSETS`; tag add/undo restores prior set, remove/undo restores, duplicate add no-op, bounds → error; query by tag / combined name+tag+kind intersect / empty→full / twice-same→identical; bounds from constants (no literals). | AGT-04 | `tests/logic/test_content_hash.py`, `test_asset_catalog.py`, `test_asset_tags.py`, `test_asset_query.py` | T11-1-05 | DATA-001, 003, 004(primitive), LOGIC-001, 002, 003, 006(hash), 007 | todo |

### 11-1-data — BlobBackend/CAS + catalog+sidecar persistence (`data/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-1-07 | `data/asset_storage.py` (new): `BlobBackend` ABC (`put_blob`/`get_blob`/`has_blob` by content_hash — **no provider type in signatures**) + `LocalBlobBackend` (local-FS/in-memory, offline default); `AssetStorageError`. Zero Qt. | AGT-03 | `data/asset_storage.py` | T11-1-02 | DATA-006 (local) / "library works fully offline" | todo |
| T11-1-08 | `data/asset_cas.py` (new): `ContentAddressableStore` over a `BlobBackend`; `put(blob)->hash` (existing hash = **dedup no-op**; > `MAX_BLOB_BYTES` → error); `get(hash)` **content-hash-verified** (mismatch → `CasError`). Zero Qt. | AGT-03 | `data/asset_cas.py` | T11-1-07 | DATA-004(CAS), 005(dedup/reference core) / "shared asset's bytes stored once" | todo |
| T11-1-09 | `data/asset_catalog_io.py` (new): catalog + per-asset **sidecar** persistence (stable `AssetId`); composes **PIO-1** for payloads (**no new serialiser**); schema+caps validation; **path-traversal guard** (`resolve()`+containment; `..`/absolute escape → error); **never `eval`/`exec`**; `AssetCatalogError(ProjectIOError)`. Zero Qt. | AGT-03 | `data/asset_catalog_io.py` | T11-1-08 | DATA-001, 002, 003, 007 / "Untrusted asset metadata …", round-trip | todo |
| T11-1-10 | Tests (headless, no network/creds): CAS dedup (2nd put of same content = no new blob) + hash-verified get + `MAX_BLOB_BYTES` reject; catalog save→load round-trip reconstructs equivalent entities via PIO-1 (no second serialiser); tags persist across reload; untrusted load (malformed/oversized/unknown → `AssetCatalogError`/`ProjectIOError`, no eval/exec) + path-traversal (`..`/absolute → rejected, nothing resolves outside root). | AGT-04 | `tests/data/test_asset_cas.py`, `test_asset_catalog_io.py`, `test_asset_untrusted.py`, `test_asset_paths.py` | T11-1-09 | DATA-001, 002, 003, 004, 005, 007 | todo |
| T11-1-11 | Run `check_layering --root pixelart_creator` + `check_cycles --root pixelart_creator`: confirm `content_hash`/`asset_catalog`/`asset_tags`/`asset_query` pure leaves over `constants`(+`content_hash`), `asset_storage`/`asset_cas`/`asset_catalog_io` Qt-free `data/`, no `logic → data`, no provider name above `BlobBackend`, no cycle. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T11-1-10 | DATA-007, LOGIC-001 / Article I / plan §11 | todo |

### 11-1-ui — asset library / tagging / search-filter (`ui/`, Qt only)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-1-12 | `ui/asset_worker.py` (new): off-GUI-thread runner for catalog scan/build + search + (later) graph query so the UI never freezes (Phase-7/8/10 worker precedent). `ui/asset_library_panel.py` (new): `Asset_Library_Panel` — list catalog entries (kind/name/tags); updates on catalog change; binds to `logic/`+`data/`, no domain logic. `tr()` + `changeEvent`. | AGT-05 | `ui/asset_worker.py`, `ui/asset_library_panel.py`, `ui/main_window.py` | T11-1-09 | UI-001, 011 / "Library panel reflects the catalog", "stays responsive" | todo |
| T11-1-13 | `ui/asset_tagging_panel.py` (new): `Asset_Tagging_Panel` — add/remove tags on the selected asset; **undoable** via the shared undo stack; bound-exceeded → translatable error. `ui/commands.py` (extend): `AddTagCommand`/`RemoveTagCommand` wrapping the pure `logic/asset_tags` (do, undo) pair. `tr()` + `changeEvent`. | AGT-05 | `ui/asset_tagging_panel.py`, `ui/commands.py` | T11-1-12 | UI-002 / "Tagging assets" (undoable, bounded) | todo |
| T11-1-14 | `ui/asset_search_panel.py` (new): `Asset_Search_Panel` — search (name) + filter (tag/kind) driving the pure `logic/asset_query.query`; clearing restores full list. `tr()` + `changeEvent`. | AGT-05 | `ui/asset_search_panel.py` | T11-1-12 | UI-003 / "Search and filter …" | todo |
| T11-1-15 | pytest-qt tests (both themes, offscreen): library panel lists exactly the catalog + updates on add/remove + no domain logic; tag add/remove reflects + persists + undoable via undo stack + bound → translatable message; search narrows by name, filter by tag/kind, combined intersect, clear restores; catalog/search op does not freeze the UI (off the per-frame loop). | AGT-06 | `tests/ui/test_asset_library_panel.py`, `test_asset_tagging.py`, `test_asset_search.py`, `test_asset_responsive.py` | T11-1-14 | UI-001, 002, 003, 011 | todo |

## Slice 2 — Dependency graph + break detection (+ graph view + break surface)

### 11-2-logic — dependency graph + break-detection pass (`logic/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-2-01 | Add the Slice-2 numeric (`MAX_DEPENDENCY_DEPTH=64`) with citation. **Name DISTINCT from every shipped constant.** | AGT-03 | `logic/constants.py` | Slice 1 done | LOGIC-007 / plan §8 | todo |
| T11-2-02 | `logic/dependency_graph.py` (new): `DependencyEdge(source_id, target_id, pinned_hash)`, `DependencyGraph` — `add_edge` (rejects a cycle-inducing edge), `dependencies_of`/`dependents_of` (direct + transitive, stable order); **cycle-safe** (white/grey/black DFS → reported, never hung) + **depth-bounded** `MAX_DEPENDENCY_DEPTH`; `DependencyGraphError`. Zero Qt. | AGT-03 | `logic/dependency_graph.py` | T11-2-01 | LOGIC-004 / "Dependency graph is queryable" | todo |
| T11-2-03 | `logic/break_detection.py` (new): `BrokenReference(source_id, target_id, reason)`, `find_broken(graph, catalog, changed_ids=None)` — flags edges to a **missing** target_id or a **hash-mismatched** target; pull-based; `changed_ids` gates revalidation to dependents of changed nodes; never false-positive; `BreakDetectionError`. Zero Qt. | AGT-03 | `logic/break_detection.py` | T11-2-02 | LOGIC-005 / "Break detection — passive flag …" | todo |
| T11-2-04 | Unit + property tests (headless): dependents/dependencies (direct + transitive) over the `sprite → animation → tileset → tilemap` fixture; cycle detected + reported (no hang); depth bound enforced; break pass flags missing id + hash mismatch, never false-positives an unchanged present target, revalidates only dependents of `changed_ids` (content-hash gating); determinism [Hypothesis, permuted edges]; bounds from constants. | AGT-04 | `tests/logic/test_dependency_graph.py`, `test_break_detection.py` | T11-2-03 | LOGIC-004, 005 | todo |

### 11-2-ui — dependency-graph view + break surface (`ui/`, Qt only)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-2-05 | `ui/dependency_graph_view.py` (new): `Dependency_Graph_View` — visualise depends-on/dependents for the catalog / a selected asset (from `logic/dependency_graph`); a cycle is shown without hanging the view. Runs queries via `ui/asset_worker`. `tr()` + `changeEvent`. | AGT-05 | `ui/dependency_graph_view.py` | T11-2-03 | UI-005 / "Dependency-graph view renders the query" | todo |
| T11-2-06 | Break-warning surface: a **passive** break indicator on `dependency_graph_view` and/or `asset_library_panel` reflecting `logic/break_detection.find_broken`; **refreshes on catalog change** (triggered revalidation); **no push notification**; no domain logic in the widget. `tr()`. | AGT-05 | `ui/dependency_graph_view.py`, `ui/asset_library_panel.py` | T11-2-05 | UI-006 / "UI surfaces breaks passively …" | todo |
| T11-2-07 | pytest-qt tests (both themes, offscreen): view shows direct deps + dependents matching the model; cycle shown without hang; broken-reference asset shows the passive indicator matching the pass + refreshes after a catalog change; valid-only asset shows none; no push; no domain logic in widget. | AGT-06 | `tests/ui/test_dependency_graph_view.py`, `test_break_warning.py` | T11-2-06 | UI-005, 006 | todo |
| T11-2-08 | **Conditional (DEP-3):** *only if* the graph-view paint path proves heavy on a large catalog, AGT-10 assesses it with `frame-profile` vs `FRAME_BUDGET_MS` and directs a UI-render optimisation (Phase-11 domain ops stay off-loop). Skipped if the view is not interactively heavy. | AGT-10 | perf directive → AGT-05 (if triggered) | T11-2-05 | (conditional) / plan §7, spec §8 DEP-3 | todo |

## Slice 3 — Version control + cross-project reuse/export + cloud-optional backing (+ version browser + reuse UI)

### 11-3-logic — asset-version model (`logic/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-3-01 | Add the Slice-3 numeric (`MAX_ASSET_VERSIONS=256`) with citation. **Name DISTINCT from the shipped `MAX_CLOUD_VERSIONS` (=100, a different concern).** | AGT-03 | `logic/constants.py` | Slice 2 done | LOGIC-007 / plan §8 | todo |
| T11-3-02 | `logic/asset_version.py` (new): `AssetRevision(asset_id, content_hash, created_marker, parent_hash, author)` (immutable) + `AssetVersionHistory` (ordered, immutable; `append`→new history; `head`; content-hash comparison; ≤ `MAX_ASSET_VERSIONS` → `AssetVersionError`); a DAG via `parent_hash`; deterministic, no CRDT. Zero Qt. | AGT-03 | `logic/asset_version.py` | T11-3-01 | LOGIC-006 / "version model is an ordered, immutable, content-hash-addressed DAG" | todo |
| T11-3-03 | Unit + property tests (headless): history yields ordered immutable descriptors with parent links (DAG, no in-place mutation); hash comparison "unchanged"/"changed"; ≤ `MAX_ASSET_VERSIONS`; no Qt / no CRDT dependency; byte-identical across runs [Hypothesis]. | AGT-04 | `tests/logic/test_asset_version.py` | T11-3-02 | LOGIC-006 | todo |

### 11-3-data — revision store + shared backend + export (`data/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-3-04 | `data/asset_revision_store.py` (new): append-only content-addressable **revision store**; stores bytes once via `asset_cas`; immutable descriptors keyed by content_hash; hash-verified fetch; **append-only** (no in-place mutate/delete); re-record identical bytes = dedup no-op (no new revision); **NOT via CRDT**; `AssetRevisionStoreError`. Zero Qt. | AGT-03 | `data/asset_revision_store.py` | T11-3-02 | DATA-004 / "Recording a revision …", "Identical bytes …", "prior revision retrievable and hash-verified", "revisions do not route through the CRDT" | todo |
| T11-3-05 | `data/asset_shared_backend.py` (new): `SharedBlobBackend(BlobBackend)` composing **Phase-10 `data/cloud/`** shared storage — optional cloud backing behind the SAME port; content-hash-verify on fetch (mismatch → reject); **no provider type above the port**; selected only when a provider is connected. Zero Qt. | AGT-03 | `data/asset_shared_backend.py` | Slice 1 (`asset_storage`) | DATA-006 (cloud) / "connected provider transparently backs the same operations", "cloud-fetched blobs are content-hash verified" | todo |
| T11-3-06 | `data/asset_export.py` (new): `export_project_assets(reference_ids, catalog, cas, out)` — resolve a project's reference set → **bundle exactly the referenced CAS blobs** into a self-contained artifact; import defence (path-traversal + caps); `AssetExportError(ProjectIOError)`. Zero Qt. | AGT-03 | `data/asset_export.py` | Slice 1 (`asset_cas`, `asset_catalog_io`) | DATA-005 / "Export bundles the referenced blobs", "imported reference is path-traversal-defended" | todo |
| T11-3-07 | Tests (headless, no network/creds): revision store append-only + dedup no-op on identical bytes + hash-verified fetch + tampered blob rejected + no CRDT path; `SharedBlobBackend` served transparently via the fake `data/cloud/` adapter + hash-verify (mismatch rejected) + no provider name above the port (`check_layering`); export bundles exactly the referenced blobs + opens self-contained + import path-traversal rejected. | AGT-04 | `tests/data/test_asset_revision_store.py`, `test_asset_shared_backend.py`, `test_asset_export.py` | T11-3-06 | DATA-004, 005, 006 | todo |
| T11-3-08 | Run `check_layering --root pixelart_creator` + `check_cycles --root pixelart_creator`: confirm `asset_revision_store`/`asset_shared_backend`/`asset_export` Qt-free `data/`, only `asset_shared_backend` touches `data/cloud/`, no provider name above `BlobBackend`, no `logic → data`, no cycle. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T11-3-07 | DATA-006 / Article I / plan §11 | todo |

### 11-3-ui — version browser + cross-project reuse (`ui/`, Qt only)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T11-3-09 | `ui/asset_version_browser.py` (new): `Asset_Version_Browser` — list an asset's revisions in order with metadata (timestamp/author); inspect a revision; **restore** reinstates it as a **new head** (append-only; earlier revisions remain); no domain logic; errors surfaced. `tr()` + `changeEvent`. | AGT-05 | `ui/asset_version_browser.py` | T11-3-04 | UI-004 / "Version browser restores a revision append-only" | todo |
| T11-3-10 | `ui/asset_reuse_panel.py` (new): `Asset_Reuse_Panel` — reference a shared asset into a project (adds a reference by `asset_id`/`content_hash`, **not** a byte copy; CAS blob count unchanged); marks an asset referenced by >1 project as shared; no domain logic. `tr()` + `changeEvent`. | AGT-05 | `ui/asset_reuse_panel.py` | T11-3-06 | UI-007 / "Reuse UI references a shared asset without copying" | todo |
| T11-3-11 | pytest-qt tests (both themes, offscreen): version browser lists revisions ordered + inspect + restore appends new head (history preserved); reuse panel references without duplicating payload (CAS blob count unchanged) + marks shared; no domain logic in widgets. | AGT-06 | `tests/ui/test_asset_version_browser.py`, `test_asset_reuse.py` | T11-3-10 | UI-004, 007 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-11 `logic/` models + `data/` stores + `ui/` surfaces (marked PLANNED per house convention). | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; zero unresolved findings before implement. | AGT-01 | `specs/phase-11-team-asset-management/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | Confirm **no `check_layering`/`check_cycles` rule edit needed** (everything inside the three layers; `data/cloud/` already governed); re-run both invocations → exit 0. | AGT-01 | `scripts/*` (invoke) | plan | Article I / plan §4.4/§11 | done |
| TG-04 | Manifest: **no new runtime dependency** (content hashing = stdlib `hashlib`); confirm no `pyproject.toml` change (PL11-D5). Register no new pytest marker (the optional `SharedBlobBackend` live path reuses the existing Phase-10 `cloud_live` marker). | AGT-09 | `pyproject.toml` (confirm no change) | plan | PL11-D5 / Article VII | todo |
| TG-05 | a11y audit (`a11y-audit`) across all Phase-11 controls (library list, tag add/remove, search/filter inputs, dependency-graph view, break surface, version browser, reuse panel): accessible names/descriptions, keyboard reachability + logical tab order, visible focus. | AGT-06 | `tests/ui/*` | T11-1-15, T11-2-07, T11-3-11 | UI-008 / "Accessibility audit passes" | todo |
| TG-06 | Both-theme render verification (role-based colours) across all Phase-11 UI (Slices 1+2+3). | AGT-06 | `tests/ui/*` | T11-1-15, T11-2-07, T11-3-11 | UI-009 / "Both themes render correctly" | todo |
| TG-07 | String audit (`string_audit_check`): zero unwrapped user-visible strings across all Phase-11 `ui/` (panel labels/columns, tag controls, search/filter labels, graph node/edge + break labels, version browser, reuse, status/errors); `changeEvent` retranslate on hand-built widgets. | AGT-07 | `ui/*.py` | T11-3-11 | UI-010 / "All user-visible strings translatable" | todo |
| TG-08 | CHANGELOG (`Unreleased`) entries for Phase-11 features tied to REQ-IDs, per slice. | AGT-08 | `docs/CHANGELOG.md` | Slice 1/2/3 impl+test done | Article IX | todo |
| TG-09 | `sdd-checklist` before ship: every REQ has a passing test; CAS dedup / canonical-hash determinism / catalog round-trip / tag do-undo / query determinism / graph queries / break pass / revision append-only / export self-contained / local-first + cloud-optional backing all green; both themes + a11y + i18n green; untrusted-input + path-traversal defence green; **no Phase-11 op gated by the 16 ms budget** (stays-responsive). | AGT-06 | checklist report | all impl+test done | Article IV/V/VI/VII | todo |
