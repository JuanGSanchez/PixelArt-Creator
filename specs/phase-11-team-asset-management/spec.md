# Specification — Phase 11: Team & Asset Management

| Field | Value |
| --- | --- |
| Feature | `phase-11-team-asset-management` |
| Author | AGT-02 (Requirements) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION — COMPLETE (clarify ADJUDICATED).** No asset catalog, tagging, search/filter, asset-version-control, dependency-graph, or cross-project-reuse capability exists yet. The **tracked entities are already shipped and are REUSED, not re-authored**: Phase 5 `Frame` / `FrameTag` / named animations (`logic/animation.py`), Phase 6 `Tileset` / `Tilemap` (`logic/tileset.py`, `logic/tilemap.py`), the Phase 1 `Document` tree + `PixelBuffer` (DOC-1), the Phase 1/4/6 `data/project_io.py` defensive `.pixproj` serialiser (PIO-1), and the Phase 10 cloud/version-history/CRDT + `data/cloud/` storage backbone. This spec fixes the WHAT/WHY for **all 26 requirements in full**. The **four acceptance-changing scope questions (CL-P11-1..4)** that were SUSPENDED at first authoring have been **ADJUDICATED by the orchestrator, grounded in the Researcher report** (`docs/subagent-report-the-researcher-a37ee154-20260704T204011.md`); the answers are recorded in §10 and encoded into the eight previously-PENDING REQs (full acceptance + Gherkin + traceability). No requirement remains PENDING/BLOCKED. |
| REQ-ID range | `REQ-P11-DATA-001..007`, `REQ-P11-LOGIC-001..008`, `REQ-P11-UI-001..011` — **all 26 fully drafted (acceptance + Gherkin + trace).** Previously-PENDING, now finalised via §10 adjudication: DATA-004/-005/-006, LOGIC-005/-006, UI-004/-006/-007. |
| Layer scope | `pixelart_creator/data/` (asset-catalog store + metadata persistence + asset-version store + cross-project shared-asset store — **zero Qt**, defensive/validated) + `pixelart_creator/logic/` (asset descriptor model, tag model, pure search/filter query, dependency-graph model + break-detection, asset-version model — **zero Qt, headless, unit-testable**) + `pixelart_creator/ui/` (asset-library panel, tagging, search/filter, version browser, dependency-graph view, break-warning surface, cross-project-reuse UI — **the only Qt surface**). |
| Binds to (upstream, **shipped** — REUSED) | Phase 5 `logic/animation.py` (`Frame`, `FrameTag`, named animations — the animated entities cataloged); Phase 6 `logic/tileset.py` (`Tileset` — references a source-image `PixelBuffer`) + `logic/tilemap.py` (`Tilemap`); Phase 1 `logic/document.py` (`Document` tree + `PixelBuffer` — **DOC-1**, the sprite/raster subject); Phase 1/4/6 `data/project_io.py` (**PIO-1** — the defensive `.pixproj` serialiser, `ProjectIOError`, `_SUPPORTED_VERSIONS`, zlib+base64, `pathlib`, **no `eval`/`exec`** — the assets' canonical persisted form); Phase 10 `data/cloud/` + the version-history / CRDT / shared-project backbone (the candidate substrate for asset version control and cross-project/team reuse — **its use here is CL-1/CL-2/CL-3**). |
| Depends on (external) | The Researcher — Phase-11 grounding **LANDED** at `docs/subagent-report-the-researcher-a37ee154-20260704T204011.md`. It grounds all four §10 adjudications: catalog by **stable AssetId + sidecar** (not path); dependency graph as a **DAG** with **depends-on / dependents-of** queries; **content hashing** as the shared change-detection primitive; **content-addressable storage (CAS) + reference-not-copy** for reuse and revisions; **path-traversal defence via `resolve()` + containment** (Article VII). The concrete graph representation, hashing scheme, index strategy, and version wire format remain AGT-01 plan/ADR HOW (§8 DEP-R). |
| SDD phase | `specify` + `clarify` **COMPLETE** — CL-P11-1..4 adjudicated (§10), the eight gated REQs finalised (acceptance + Gherkin + trace), matrix fully covered. `sdd-plan` (AGT-01) is **UNBLOCKED**. |

---

## 1. Purpose (WHY)

The platform now ships a rich set of authored entities — sprites (`PixelBuffer` / `Document` layers),
animations (`Frame` / `FrameTag` / named animations, Phase 5), and tilesets/tilemaps (Phase 6) — plus a
cloud + version-history + collaboration backbone (Phase 10). What it lacks is a **studio-level way to
manage those entities as reusable assets**: to catalog them, tag them, find them by search/filter, keep
a version history of an individual asset's revisions, understand how assets depend on one another
(a tileset's source image is a sprite; an animation's frames are sprites), be **warned when changing one
asset breaks another that references it**, and **reuse an asset across projects without duplicating it**.

Roadmap Phase 11 — **Team & Asset Management** ("studio-level workflows") delivers this. Its ROADMAP
"Done means" is: *assets are cataloged with tags and retrievable by search/filter; version control
records asset revisions; the dependency graph (sprite → animation → tileset) is queryable and flags a
break when a referenced asset changes; assets reuse across projects without duplication.* A studio asset
library + dependency tracking is a **differentiator** — it exceeds Aseprite / Pro Motion NG / Pixelorama
(toward pipeline / DAM tooling). Phase 11 **depends on** Phase 6 tileset/tilemap + Phase 5 animation
(the entities tracked) and Phase 10 cloud/version-history (the shared-storage backbone).

**This phase had four genuinely acceptance-changing ambiguities. They are now ADJUDICATED** (orchestrator,
grounded in the Researcher report) and encoded into the eight gated REQs (§10 records each answer):
asset version control is a **HYBRID reusing Phase 10** — content-hash change detection + an append-only
**content-addressable asset-revision store**, NOT routed through the live-collab CRDT (CL-1); cross-project
reuse is a **content-addressable store + reference-not-copy** — bytes stored once by content hash, projects
**reference** by stable id/hash and never duplicate bytes, and export bundles the referenced blobs (CL-2 —
this is the precise meaning of "**without duplication**"); the asset library is **local-first, cloud
optional** — it works fully offline, and when a Phase-10 provider is connected the CAS/library **may** be
backed by Phase-10 shared storage behind an abstraction layer (CL-3); and break-detection is a **passive
flag on a reference-validation / query pass with triggered revalidation** — a broken reference (missing
target stable-id or content-hash mismatch) is flagged on query and in the dependency view and revalidated
on catalog change; live push-notification is a FUTURE enhancement, not core acceptance (CL-4).

The requirement-level WHAT for all 26 REQs is drafted **in full**, technology-neutral. The HOW — the
concrete graph representation, index strategy, hashing scheme, storage substrate, and version wire format —
remains downstream (AGT-01 plan/ADR, grounded by the landed Researcher report, §8 DEP-R).

## 2. Scope

**In scope now (WHAT) — fully drafted (unambiguous):**

- **Asset catalog (`data/`, Qt-free).** A persistent catalog of **asset entries**, each with a stable
  asset id, an asset **kind** (`sprite` / `animation` / `tileset` / `tilemap` / `palette`), a display
  name, and metadata, referencing a **shipped entity** — the catalog adds **no new serialisation of the
  asset payload itself**; the payload is the shipped `.pixproj`/PIO-1 form (REQ-P11-DATA-001, -007).
- **Tagging (`data/` + `logic/`).** Free-form tags attach to catalog entries and **persist**; tag edits
  are reversible/pure (REQ-P11-DATA-003, REQ-P11-LOGIC-002).
- **Search / filter (`logic/`, Qt-free).** A **pure, deterministic query** retrieves catalog entries by
  name, tag, and/or kind — the "retrievable by search/filter" done-means (REQ-P11-LOGIC-003).
- **Dependency-graph model — queryable (`logic/`, Qt-free).** A directed graph of asset→asset references
  (`sprite → animation → tileset`, `tileset → tilemap`) is **queryable** — given an asset, list what it
  depends on and what depends on it, via deterministic traversal, bounded against cycles/depth
  (REQ-P11-LOGIC-004). *(The break reaction is CL-4 = a passive flag on a reference-validation / query
  pass, REQ-P11-LOGIC-005 — the graph's **queryability** and the **break flag** are both drafted.)*
- **Untrusted asset metadata / imported catalogs — Article VII (`data/`).** Any asset metadata or
  imported catalog is **untrusted input**: schema-validated with strict size/depth/count caps,
  **`eval`/`exec`-free**, with **path-traversal defence** on every referenced asset path
  (REQ-P11-DATA-002).
- **Pure models + bounded numerics + batch posture (`logic/`).** The asset descriptor model
  (REQ-P11-LOGIC-001), the tag model (REQ-P11-LOGIC-002), the search/filter query (REQ-P11-LOGIC-003),
  the dependency-graph model (REQ-P11-LOGIC-004), named bounds in `logic/constants.py`
  (REQ-P11-LOGIC-007), and the **pure + bounded + not-on-the-per-frame-loop** posture (REQ-P11-LOGIC-008,
  Article VI). *(T11-X02: this line previously read "the **off-the-interactive-loop / batch** posture
  (REQ-P11-LOGIC-008, Article VI — asset ops are batch like Phases 7/8/10-A)" — wrong; unlike Phases
  7/8/10-A, Phase 11 shipped **no** worker and calls logic synchronously. See the correction note under
  REQ-P11-LOGIC-008.)*
- **`ui/` surfaces — fully drafted.** An **asset-library panel** (browse the catalog — REQ-P11-UI-001), a
  **tagging** UI (REQ-P11-UI-002), a **search/filter** UI (REQ-P11-UI-003), a **dependency-graph view**
  (visualise `sprite → animation → tileset` — REQ-P11-UI-005), and the a11y / both-themes / i18n /
  synchronous-completion gates (REQ-P11-UI-008/-009/-010/-011). *(T11-X02: the last gate previously read
  "stays-responsive" — see the correction note under REQ-P11-UI-011.)*

**In scope now (WHAT) — fully drafted (§10-adjudicated):**

- **Asset version control — append-only content-addressable revision store (`data/` + `logic/`).**
  *(CL-1 = HYBRID reusing Phase 10: content-hash change detection + an append-only CAS-backed
  asset-revision store; NOT routed through the live-collab CRDT.)* — REQ-P11-DATA-004, REQ-P11-LOGIC-006,
  UI-004.
- **Cross-project reuse without duplication — CAS + reference-not-copy (`data/`).** *(CL-2 =
  content-addressable store: bytes stored once by content hash; projects REFERENCE by stable id/hash,
  never duplicate bytes; export bundles the referenced blobs.)* — REQ-P11-DATA-005, UI-007.
- **Asset-library storage substrate — local-first, cloud optional (`data/`).** *(CL-3 = works fully
  offline/local; when a Phase-10 provider is connected the CAS/library MAY be backed by Phase-10 shared
  storage behind an abstraction layer that hides local-vs-cloud.)* — REQ-P11-DATA-006.
- **Break detection — passive flag on a reference-validation / query pass (`logic/` + `ui/`).** *(CL-4 =
  a broken reference (missing target stable-id or content-hash mismatch) is computed by a
  reference-validation pass, flagged on query + in the dependency view, and revalidated on catalog change;
  live push-notification is FUTURE, not core.)* — REQ-P11-LOGIC-005, UI-006.

**Out of scope (this phase):** see §6 Non-goals. Notably: re-authoring the tracked entities (Phase
5/6/1) or the `.pixproj` serialiser (PIO-1); the concrete graph representation / index strategy / hashing
scheme / storage substrate / version wire format (AGT-01/ADR HOW); identity / account / billing beyond
what Phase 10 already provides; no plan/tasks/code (AGT-01/03/05); no tests (AGT-04/06); no new technology
decided here (S8).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label + roadmap phase.
Feature-label taxonomy in §3.2. **All stories are drafted; the four formerly-gated stories (§3.1b) are now
`RESOLVED` via the §10 adjudications.**

### 3.1 User stories — fully drafted (unambiguous)

- **US-1 (Artist / asset-catalog).** As an artist, I want my sprites, animations, and tilesets **cataloged
  as named assets** so I can see and manage my studio's assets in one place. → REQ-P11-DATA-001, -007,
  REQ-P11-LOGIC-001, REQ-P11-UI-001 · `asset-catalog` · P11
- **US-2 (Artist / tagging).** As an artist, I want to **tag** assets (e.g. `hero`, `enemy`, `tileset-a`)
  so I can organise them by meaning, and have the tags persist. → REQ-P11-DATA-003, REQ-P11-LOGIC-002,
  REQ-P11-UI-002 · `tagging` · P11
- **US-3 (Artist / search-filter).** As an artist, I want to **search and filter** the catalog by name,
  tag, or kind so I can retrieve the right asset quickly. → REQ-P11-LOGIC-003, REQ-P11-UI-003 ·
  `search-filter` · P11
- **US-4 (Technical artist / dependency-query).** As a technical artist, I want the **dependency graph**
  (`sprite → animation → tileset`) to be **queryable** — for any asset, what it depends on and what
  depends on it — so I understand my asset pipeline. → REQ-P11-LOGIC-004, REQ-P11-UI-005 ·
  `dependency-graph` · P11
- **US-5 (Security-conscious user / untrusted-metadata).** As a user, I want imported asset metadata /
  catalogs treated as **untrusted input** — schema-validated, `eval`-free, path-traversal-safe — so a
  tampered catalog can never execute code or escape the project directory. → REQ-P11-DATA-002 ·
  `untrusted-metadata` · P11
- **US-6 (Any user / bounded-and-immediate).** As a user, I want asset operations (catalog scan, search,
  graph query) to be **bounded** and to **finish and show their result immediately when I trigger them**,
  with no half-finished state to manage. → REQ-P11-LOGIC-008, REQ-P11-UI-011 · `responsive-batch` · P11
  *(T11-X02, 2026-07-30: this story previously read "**US-6 (Any user / responsive-and-batch).** As a user,
  I want asset operations (catalog scan, search, graph query) to run as **batch work off the interactive
  loop** and keep the UI responsive." That described a worker mechanism Phase 11 never built — see the
  correction note under REQ-P11-LOGIC-008. The feature label `responsive-batch` is **retained verbatim**
  because it is part of the shared taxonomy other artifacts index on; it is now a misnomer, not a claim.)*
- **US-7 (Any user / a11y-theme-i18n).** As a keyboard / dark-mode / non-English user, I want the asset
  panels **keyboard-reachable, correct in both themes, fully translatable**. → REQ-P11-UI-008, -009, -010
  · `a11y`, `theming`, `i18n` · P11

### 3.1b User stories — §10-adjudicated (formerly gated; now drafted in full)

- **US-8 (Artist / asset-version-control).** As an artist, I want a **version history of an individual
  asset** so I can see and restore its prior revisions — recorded as immutable, content-hash-addressed
  revisions in an append-only store (CL-1). → REQ-P11-DATA-004, REQ-P11-LOGIC-006, REQ-P11-UI-004 ·
  `asset-versioning` · P11 · **RESOLVED CL-1**
- **US-9 (Studio / cross-project-reuse).** As a studio, I want to **reuse an asset across projects without
  duplicating it** — one payload stored once in the CAS, referenced by stable id/hash from many projects;
  export bundles the referenced blobs (CL-2). → REQ-P11-DATA-005, REQ-P11-UI-007 · `cross-project-reuse` ·
  P11 · **RESOLVED CL-2 / CL-3**
- **US-10 (Team / shared-asset-library).** As a team, I want the asset library to work **fully offline
  locally**, and — when a Phase-10 provider is connected — to be **backed by shared storage** so the whole
  team sees the same assets (CL-3, local-first / cloud-optional). → REQ-P11-DATA-006 · `shared-library` ·
  P11 · **RESOLVED CL-3**
- **US-11 (Technical artist / break-flagging).** As a technical artist, I want to **know when changing an
  asset breaks another that references it** — surfaced as a passive break flag on query and in the
  dependency view, revalidated on catalog change (CL-4). → REQ-P11-LOGIC-005, REQ-P11-UI-006 ·
  `break-detection` · P11 · **RESOLVED CL-4**

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase | Status |
| --- | --- | --- | --- |
| `asset-catalog` | Persistent catalog of named asset entries referencing shipped entities. | 11 | drafted |
| `tagging` | Free-form persisted tags on catalog entries; pure, reversible tag edits. | 11 | drafted |
| `search-filter` | Pure deterministic query over the catalog by name / tag / kind. | 11 | drafted |
| `dependency-graph` | Queryable directed graph of asset→asset references (`sprite→animation→tileset`). | 11 | drafted |
| `untrusted-metadata` | Asset metadata / imported catalogs are untrusted: validated, `eval`-free, path-safe. | 11 | drafted |
| `responsive-batch` | Asset ops are batch, off the per-frame loop; the UI never freezes. | 11 | drafted |
| `asset-versioning` | Immutable, content-hash-addressed revisions of an asset in an append-only CAS-backed store. | 11 | drafted (CL-1) |
| `cross-project-reuse` | CAS + reference-not-copy: one payload, many references; export bundles blobs. | 11 | drafted (CL-2) |
| `shared-library` | Local-first library; optionally backed by Phase-10 shared storage behind an abstraction layer. | 11 | drafted (CL-3) |
| `break-detection` | Passive break flag from a reference-validation / query pass; revalidated on catalog change. | 11 | drafted (CL-4) |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 11 | drafted |

---

## 4. Functional requirements — FULLY DRAFTED (unambiguous)

Each REQ carries `traces:` to a dossier `S-id`, a principle, a constitution article, and/or a
forward-inherited shipped primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a shipped callable is a **constraint**, not a HOW choice.

### `data/` — asset catalog + metadata (new, Qt-free, defensive)

#### REQ-P11-DATA-001 — Asset catalog: a persistent, retrievable set of named asset entries
`traces:` S6 (studio workflows), S7, Article XI, ROADMAP Phase-11 ("cataloged … retrievable")
`data/` maintains a **catalog** of **asset entries**. Each entry has a **stable asset id**, an asset
**kind** (`sprite` / `animation` / `tileset` / `tilemap` / `palette`), a **display name**, and a
metadata bag, and **references a shipped entity** (a `Document` layer / `PixelBuffer`, a Phase-5
`Frame`/animation, a Phase-6 `Tileset`/`Tilemap`, or a palette). Entries **persist** and are
**retrievable** by id and by enumeration. The catalog **references** the entity's canonical persisted
form; it adds **no new serialisation of the asset payload** (REQ-P11-DATA-007). *(The storage substrate is
CL-3 = local-first / cloud-optional, REQ-P11-DATA-006; the catalog **contract** here is
substrate-independent — it holds identically against the local store or the optional shared backend.)*
**Acceptance:** given N entities registered as assets, the catalog persists across sessions and
enumeration returns exactly those N entries with their id/kind/name/metadata intact; retrieval by a known
id returns the matching entry; retrieval by an unknown id yields a clean not-found result (never a crash).

#### REQ-P11-DATA-002 — Asset metadata / imported catalogs are untrusted input (Article VII)
`traces:` **PIO-1**, Article VII (§1 validate, §2 portable paths), S7
Any asset metadata written to, or **catalog imported from**, an external source is **untrusted input**:
it is **schema-validated** (field types + bounds), size/depth/count-capped
(`MAX_CATALOG_ASSETS`, `MAX_TAGS_PER_ASSET`, `MAX_TAG_BYTES`, `MAX_METADATA_BYTES` — REQ-P11-LOGIC-007),
**never** passed to `eval`/`exec`, and every **referenced asset path is path-traversal-defended**
(resolved and confirmed within the project/library root; `..` escapes and absolute-path escapes rejected)
and constructed portably (`pathlib`, Article VII §2). Malformed / oversized / escaping input → a domain
error (`ProjectIOError` or a `data/` subclass), surfaced to the user — never a crash or silent
corruption. Reuses the shipped PIO-1 defensive posture; does not fork it.
**Acceptance:** a catalog/metadata payload that is oversized, malformed, exceeds a cap, or references a
path escaping the library root is **rejected with a clear domain error**; no such payload reaches
`eval`/`exec`; no referenced path resolves outside the library root.

#### REQ-P11-DATA-003 — Tags attach to assets and persist
`traces:` S6, ROADMAP Phase-11 ("cataloged with tags"), Article XI
A catalog entry carries a set of **tags** (free-form labels). Tags **persist** with the entry across
sessions; adding/removing a tag updates the persisted set. Tag count per asset and tag byte-length are
bounded (`MAX_TAGS_PER_ASSET`, `MAX_TAG_BYTES` — REQ-P11-LOGIC-007). Tag payloads are untrusted input
(REQ-P11-DATA-002).
**Acceptance:** tags added to an asset are present on reload; a removed tag is absent on reload; exceeding
the tag count/length bound raises a domain error rather than truncating silently.

#### REQ-P11-DATA-007 — Assets reuse the shipped `.pixproj`/PIO-1 form; no re-serialisation
`traces:` **PIO-1**, **DOC-1**, Article I (no re-implementation), Article VII
The asset payload's canonical persisted form is the **shipped `.pixproj`/PIO-1 serialisation** (and the
shipped entity models it carries — `Frame`/`Tileset`/`Tilemap`/`PixelBuffer`). The catalog **composes**
PIO-1 to load/store an asset's bytes and **does not define a new payload format** for the asset content
itself (a catalog **index/metadata** schema is a `data/` structure over references, not a fork of the
payload format). A cataloged asset loaded back reconstructs an **equivalent** shipped entity via PIO-1,
validated defensively (REQ-P11-DATA-002).
**Acceptance:** an asset stored and re-loaded through the catalog reconstructs an equivalent shipped
entity via PIO-1; the catalog introduces no second serialiser for the payload; `check_layering` confirms
the catalog is Qt-free `data/`.

### `logic/` — asset / tag / search / dependency models (new, Qt-free)

#### REQ-P11-LOGIC-001 — Asset descriptor model is pure and references a shipped entity
`traces:` P2 (determinism), S11, Article I, Article X (forward-inherited entities)
A pure, Qt-free **asset descriptor** models a catalog entry: id + kind + name + tag set + metadata +
a **reference** to the shipped entity it describes (`sprite` → `PixelBuffer`/layer, `animation` →
Phase-5 `Frame`/named animation, `tileset` → Phase-6 `Tileset`, `tilemap` → `Tilemap`, `palette` →
palette). The model is deterministic, unit-testable, and has no Qt / wall-clock / randomness / locale
dependence.
**Acceptance:** constructing a descriptor for each supported kind yields a deterministic, comparable value
with its reference resolvable to the shipped entity; no Qt import (`check_layering` passes).

#### REQ-P11-LOGIC-002 — Tag model + tagging operations are pure (and reversible)
`traces:` P2, S11, **HIS-1** (reversible-op path), Article I
Tag membership is a pure model; **add-tag** and **remove-tag** are **reversible operations** expressed in
`logic/` (do/undo capturing minimal prior state) so `ui/commands.py` can wrap them as `QUndoCommand`s —
the `logic/` layer stays Qt-free (reuses the shipped `history` reversible-op pattern, HIS-1). Tagging is
deterministic and idempotent (adding a present tag / removing an absent tag is a no-op).
**Acceptance:** add-tag then undo returns the exact prior tag set; remove-tag then undo restores it;
adding a duplicate tag is a no-op; the model imports no Qt.

#### REQ-P11-LOGIC-003 — Search / filter is a pure deterministic query
`traces:` P2 (determinism), S11, ROADMAP Phase-11 ("retrievable by search/filter")
Retrieving catalog entries by **name substring**, **tag(s)**, and/or **kind** is a **pure, deterministic
function** of the catalog snapshot and the query — same catalog + same query ⇒ **identical, stably
ordered** result set. Filters compose (name AND tag AND kind); an empty query returns the full catalog in
a stable order; no wall-clock / randomness / locale-dependent ordering.
**Acceptance:** a query by tag returns exactly the entries carrying that tag in a stable order; combined
name+tag+kind filters return the intersection; the same query over the same catalog is byte-identical
across runs.

#### REQ-P11-LOGIC-004 — Dependency graph is a queryable directed model
`traces:` P2, S11, Article I, ROADMAP Phase-11 ("dependency graph … is queryable")
Asset→asset references form a **directed graph** (`sprite → animation` via frame references;
`sprite → tileset` via the tileset's source image; `tileset → tilemap` via tile links). The model is
**queryable**: for any asset it returns its **direct dependencies** (what it references) and its
**dependents** (what references it), and supports deterministic transitive traversal. Traversal is
**cycle-safe** and **depth-bounded** (`MAX_DEPENDENCY_DEPTH` — REQ-P11-LOGIC-007); a cycle is detected and
reported, never an infinite loop. The graph is pure, Qt-free, and deterministic.
**Acceptance:** given `sprite S → animation A → (S is a frame)` and `S → tileset T → tilemap M`, querying
dependents of `S` returns `{A, T}` (and transitively `M`); querying dependencies of `M` returns `{T}` and
transitively `{S}`; a reference cycle is detected and reported (no hang); traversal is deterministic.
*(What the graph **does when a referenced asset changes** is CL-4 = a passive break flag on the
reference-validation / query pass, REQ-P11-LOGIC-005 — built on this queryable model.)*

#### REQ-P11-LOGIC-007 — Bounded numerics & defaults (single source, Article II)
`traces:` Article II, Article VII, S12
The asset layer enforces named bounds/defaults defined once in `logic/constants.py` — candidates:
`MAX_CATALOG_ASSETS`, `MAX_TAGS_PER_ASSET`, `MAX_TAG_BYTES`, `MAX_METADATA_BYTES`, `MAX_DEPENDENCY_DEPTH`,
and — now that version control + CAS reuse are adjudicated in (CL-1/CL-2) — `MAX_ASSET_VERSIONS` and the
CAS blob-size cap (`MAX_BLOB_BYTES`). Exceeding a bound raises a domain error rather than degrading
silently; no numeric literals appear in `logic/`/`data/`/`ui/`. **Concrete values are an AGT-01/ADR HOW.**
**Acceptance:** every Phase-11 tuning value is a named constant in `logic/constants.py` (grep finds no
literal at call sites); exceeding any bound raises a domain error.

#### REQ-P11-LOGIC-008 — Asset operations are pure, bounded, and off the per-frame render loop (Article VI)
`traces:` Article VI, S1, S12

> **T11-X02 RE-ADJUDICATION (2026-07-30) — this requirement previously over-promised a mechanism that
> does not exist in the product.** Following the analyze-gate retrofit precedent
> (`specs/phase-1-ui-canvas/traceability.md` §"Notes for `sdd-analyze`"), it is **corrected in place, not
> deleted**, so the history stays auditable.
>
> **Its previous title read:** *"Asset operations are batch, off the interactive render loop (Article VI)"*.
> **Its previous statement read:**
> *"Catalog scan/build, search/filter, tagging, and dependency-graph query are **batch/background**
> operations **not on the per-frame render loop** — like Phase-7 export, Phase-8 automation, and Phase-10
> Slice-A cloud sync, the 16 ms `FRAME_BUDGET_MS` does **not** gate the operation itself; instead the
> contract is that these operations keep the **UI responsive** (REQ-P11-UI-011)."*
> **Its previous acceptance read:** *"a catalog/search/graph operation over a large catalog does not block
> the GUI thread; no Phase-11 operation is asserted against the 16 ms per-frame budget."*
>
> **Why that was wrong.** The words *"batch/background"* and *"does not block the GUI thread"* assert an
> off-GUI-thread execution mechanism. **No such mechanism was ever built for Phase 11.** A search for
> `QThread`, `QThreadPool`, `QRunnable`, `threading` and `concurrent.futures` across
> `pixelart_creator/` returns **zero** hits in any Phase-11 asset or dependency module. The pattern is not
> missing from the project — the same search finds worker modules for other phases
> (`ui/export_worker.py`, `ui/automation_worker.py`, `ui/cloud_worker.py`, `ui/realtime_worker.py`,
> `ui/assistant_worker.py`) — Phase 11 simply calls into `logic`/`data` **synchronously**, and its own
> module docstrings say so outright: `ui/asset_library_actions.py` ("they run **synchronously on the GUI
> thread with no worker thread, timer, or poller**"), `ui/asset_library_panel.py` /
> `ui/asset_search_panel.py` / `ui/asset_tagging_panel.py` / `ui/dependency_graph_view.py` /
> `ui/asset_reuse_panel.py` ("All work is synchronous over the in-memory catalog — no worker thread /
> timer"). The `ui/asset_worker.py` module that `plan.md` §7 names **does not exist on disk**.
> The requirement is therefore restated to the behaviour that actually shipped. It is **weakened, and that
> is deliberate**: an artifact promising a mechanism the code does not have is worse than a weaker true one.
>
> **The off-GUI-thread ambition is not abandoned — it is reclassified as FUTURE WORK, not a Phase-11
> requirement.** See §6 "Non-goals" (FW-P11-1) below; it needs a new REQ-ID in a future phase, a measured
> latency justification, and a worker module. Nothing in this correction authorises dropping it.

Catalog scan/build, search/filter, tagging, and dependency-graph query are **pure, deterministic,
Qt-free** operations in `logic/`/`data/`, invoked **synchronously by the caller** and **bounded by named
constants** in `logic/constants.py` — `MAX_CATALOG_ASSETS` (65536), `MAX_TAGS_PER_ASSET` (64),
`MAX_DEPENDENCY_DEPTH` (64) — so every one of them terminates in finite work over an immutable in-memory
value; exceeding a bound raises a domain error rather than degrading or running unbounded. They are **not
invoked from the per-frame render path**: each runs only in response to a user action, and Phase 11 adds
no timer, poller or paint-path call site. The 16 ms `FRAME_BUDGET_MS` therefore does **not** gate them, and
**no per-frame time threshold is asserted here** — no such measurement was ever taken for Phase 11, so
stating one would be an invented number. *(If a large-catalog dependency-graph **render** ever needs
per-frame assessment, that is an AGT-10 flag, §8 DEP-3, not a Phase-11 acceptance change.)*
**Acceptance:** every Phase-11 asset/graph operation is pure and deterministic (identical input ⇒
byte-identical result), imports no Qt (`check_layering` passes), and raises a domain error rather than
proceeding once a named bound (`MAX_CATALOG_ASSETS` / `MAX_TAGS_PER_ASSET` / `MAX_DEPENDENCY_DEPTH`) is
exceeded; no Phase-11 operation is invoked from a paint/timer path, and none is asserted against the 16 ms
per-frame budget.

### `ui/` — asset library, tagging, search, dependency view (new; only Qt)

#### REQ-P11-UI-001 — Asset-library panel (browse the catalog)
`traces:` REQ-P11-DATA-001, REQ-P11-LOGIC-001, S6, Article V
The UI presents an **asset-library panel** listing catalog entries with their kind, name, and tags,
driving the `logic/`/`data/` catalog (no domain logic in the widget). The panel updates when the catalog
changes. Translatable labels; errors surfaced (not swallowed). a11y + both themes + i18n apply
(REQ-P11-UI-008/-009/-010).
**Acceptance:** the panel lists exactly the catalog's entries with correct kind/name/tags; adding/removing
an asset updates the panel; the widget contains no domain logic (binds to `logic/`).

#### REQ-P11-UI-002 — Tagging UI (add / remove tags)
`traces:` REQ-P11-DATA-003, REQ-P11-LOGIC-002, Article V
The UI lets the user **add and remove tags** on a selected asset; edits are undoable (wrap the reversible
`logic/` op, REQ-P11-LOGIC-002) and persist (REQ-P11-DATA-003). Translatable labels. a11y + both themes +
i18n apply.
**Acceptance:** adding/removing a tag reflects in the panel and persists; the edit is undoable via the
shared undo stack; tag input over the length/count bound is rejected with a translatable message.

#### REQ-P11-UI-003 — Search / filter UI
`traces:` REQ-P11-LOGIC-003, Article V
The UI provides **search (by name) and filter (by tag / kind)** controls that drive the pure query
(REQ-P11-LOGIC-003) and show the matching entries. Clearing the query restores the full list.
Translatable labels. a11y + both themes + i18n apply.
**Acceptance:** typing a name substring narrows the list to matches; selecting a tag/kind filter narrows
correctly; combined filters intersect; clearing restores the full catalog; results match
REQ-P11-LOGIC-003.

#### REQ-P11-UI-005 — Dependency-graph view
`traces:` REQ-P11-LOGIC-004, S6, Article V
The UI **visualises the dependency graph** (`sprite → animation → tileset`, `tileset → tilemap`) for the
catalog / a selected asset — showing what an asset depends on and what depends on it (from the queryable
model, REQ-P11-LOGIC-004). Translatable labels. a11y + both themes + i18n apply. *(The passive break
indicator on this view is CL-4, REQ-P11-UI-006 — both the visualisation and the break flag are drafted.)*
**Acceptance:** selecting an asset shows its direct dependencies and dependents matching
REQ-P11-LOGIC-004; a cycle is shown without hanging the view; both themes render correctly.

#### REQ-P11-UI-008 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive Phase-11 control (library list, tag add/remove, search/filter inputs, dependency-graph
view, and — once adjudicated — version browser / reuse / break surfaces) exposes an accessible name and,
where non-obvious, a description; is keyboard-reachable in a logical order; shows a visible focus
indicator. Verified by AGT-06 (`a11y-audit`).
**Acceptance:** `a11y-audit` reports no missing accessible name / unreachable control / invisible focus on
the Phase-11 surfaces.

#### REQ-P11-UI-009 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The asset-library panel, tagging UI, search/filter UI, and dependency-graph view render correctly in both
light and dark themes; colours are defined once by role, never hard-coded per widget. Both themes are
test-verified (AGT-06 pytest-qt).
**Acceptance:** every Phase-11 surface renders correctly in both themes; no per-widget hard-coded colour.

#### REQ-P11-UI-010 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 11 (panel labels/columns, tag controls, search/filter labels,
graph node/edge labels, status/error messages) is wrapped in `tr()` / `translate()`; none is a bare
literal. Hand-built widgets re-set text on `QEvent.LanguageChange`. Verified by `string_audit_check`
(AGT-07); an unwrapped string is blocking.
**Acceptance:** `string_audit_check` finds no unwrapped user-visible string in the Phase-11 `ui/` files.

#### REQ-P11-UI-011 — Asset operations complete synchronously on the GUI thread, with no worker to manage *(NFR, Article VI posture)*
`traces:` REQ-P11-LOGIC-008, Article VI, S1

> **T11-X02 RE-ADJUDICATION (2026-07-30) — this requirement previously over-promised a mechanism that
> does not exist in the product.** Corrected in place, not deleted (same precedent and same evidence as
> REQ-P11-LOGIC-008 above; read that correction note for the full search result).
>
> **Its previous title read:** *"Asset operations keep the UI responsive (NFR, Article VI posture)"*.
> **Its previous statement read:**
> *"A catalog scan/build, search, tagging, or dependency-graph query **does not freeze the UI** — it runs
> off the GUI thread where the work is non-trivial and the app stays responsive (progress/cancel where a
> long operation warrants it). Whether it runs on a worker thread/executor is an AGT-01/AGT-10 HOW; this
> REQ fixes the observable **stays-responsive** contract."*
> **Its previous acceptance read:** *"a catalog/search/graph operation over a large catalog leaves the UI
> responsive (no freeze); the operation is not gated by the 16 ms per-frame budget."*
>
> **Why that was wrong.** Three claims in it are false of the shipped code: nothing "runs off the GUI
> thread" (no `QThread`/`QThreadPool`/`QRunnable`/`threading`/`concurrent.futures` anywhere in the
> Phase-11 asset and dependency modules), **no progress or cancel affordance was built**, and therefore no
> "does not freeze / stays responsive" guarantee exists to verify. What shipped is the opposite posture,
> stated in the modules' own docstrings: every library / tagging / search / graph / version / reuse
> operation is a synchronous in-memory call on the GUI thread with no worker, timer or poller.
> This requirement is **weakened deliberately**; the off-GUI-thread capability is recorded as **future
> work (FW-P11-1, §6)** and still needs its own REQ-ID, a measurement, and a worker module.

A catalog scan/build, search, tagging, dependency-graph, version or reuse operation is invoked
**synchronously on the GUI thread** and **completes within that single call**, before control returns to
the Qt event loop: the panel re-reads and repaints from the returned immutable value, so there is no
intermediate/partial state, no progress or cancel affordance, and **nothing to tear down** — no Phase-11
panel or session owns a worker thread, timer or poller, and none needs a `shutdown_*` path (which is also
why the cross-thread GC-of-Qt-C++ teardown hazard cannot arise on this surface). The work each call
performs is bounded by the named constants in REQ-P11-LOGIC-008. **Stated plainly and as the accepted
consequence:** because the call is synchronous, an operation over a catalog at the upper end of
`MAX_CATALOG_ASSETS` blocks the GUI thread for its duration. **No responsiveness threshold and no latency
figure is asserted here** — none was ever measured for Phase 11, and an unmeasured number is an open
question, not a requirement.
**Acceptance:** the result of a Phase-11 panel operation is observable in the same call — a test asserts
the updated panel state immediately after the triggering input, with no `waitSignal`/`qWait`; no Phase-11
asset panel or session references `QThread`/`QThreadPool`/`QRunnable`/`threading`/`concurrent.futures` or
exposes a `shutdown_*` teardown path; and a window owning the asset panels disposes cleanly with no worker
shutdown step. The operation is not gated by the 16 ms per-frame budget.

## 4b. Functional requirements — §10-ADJUDICATED (finalised: full acceptance + Gherkin + trace)

> These eight requirements were SUSPENDED at first authoring. The four §10 clarifications are now
> **ADJUDICATED** (orchestrator, grounded in the landed Researcher report). Each REQ below carries the
> resolved WHAT + full acceptance criteria; the matching Gherkin lives in `acceptance.md` and the
> traceability rows are `covered`.

#### REQ-P11-DATA-004 — Asset version store: append-only, content-addressable revision store *(CL-1 = HYBRID / Phase-10 reuse)*
`traces:` S7, ROADMAP Phase-11 ("version control records asset revisions"), Article X (Phase-10 reuse), Article VII, Researcher §3/§4
Asset **revisions** are recorded in an **append-only, content-addressable revision store** so any prior
revision of an asset is retrievable. Each revision is an immutable descriptor `(asset_id, content_hash,
parent_hash, timestamp, author)`; the asset **bytes are stored once in the CAS keyed by their
`content_hash`** (writing an existing hash is a dedup no-op, Researcher §4). **Change detection is by
content hash** (equal canonicalized bytes ⇒ same hash ⇒ no new revision, Researcher §3.2), reusing the
**shipped Phase-10 content-hashing / CAS primitives** — NOT the live-collaboration CRDT (the CRDT remains
for concurrently-edited live documents only; whole-asset binary revisions do not route through it). The
store is untrusted-input safe on load (REQ-P11-DATA-002): schema+caps validation and content-hash
verification on any blob fetched from the store (hash mismatch ⇒ reject). Substrate is local-first / cloud
optional (REQ-P11-DATA-006).
**Acceptance:** recording a revision appends an immutable descriptor keyed by `content_hash` and stores
the bytes once in the CAS; re-recording identical (canonicalized) bytes produces no new revision and no
duplicate blob (dedup no-op); a prior revision is retrievable by its content-hash / revision pointer and
its bytes verify against the recorded hash (a tampered blob whose hash mismatches is rejected); the store
is append-only (no revision is mutated or deleted in place); asset revisions never pass through the
live-collab CRDT (`check_layering` confirms the store is Qt-free `data/`).

#### REQ-P11-LOGIC-006 — Asset-version model (ordered, immutable, content-hash-addressed revision DAG) *(CL-1)*
`traces:` P2, S11, Article X (Phase-10 version model reuse), Phase-10 REQ-P10-LOGIC-003, Researcher §3
A pure, Qt-free model of an asset's revision history: an **ordered, immutable revision DAG** whose nodes
are revision descriptors carrying `content_hash` + `parent_hash` links (the Phase-10 version-history model
applied at **asset granularity**, reusing its content-hash primitive rather than introducing a new one).
The model exposes: the ordered history for an asset, the head revision, and a **content-hash comparison**
that reports whether two byte-states differ (the change signal that also gates break re-validation,
REQ-P11-LOGIC-005). Deterministic, no Qt / wall-clock / randomness / locale dependence.
**Acceptance:** constructing a revision history yields ordered immutable descriptors, each carrying a
`content_hash` and a parent link back to its predecessor (a DAG, no in-place mutation); a content-hash
comparison returns "unchanged" for identical canonicalized bytes (⇒ no new revision) and "changed"
otherwise; the model imports no Qt and has no CRDT dependency (`check_layering` passes); the same inputs
produce byte-identical history across runs.

#### REQ-P11-UI-004 — Asset version browser (view + restore revisions) *(CL-1)*
`traces:` REQ-P11-DATA-004, REQ-P11-LOGIC-006, Article V
The UI presents an asset's **revision history** (ordered, from the model REQ-P11-LOGIC-006) and lets the
user **inspect** a prior revision and **restore** it. A restore reinstates the selected revision's content
as a **new head revision** (append-only — history is preserved, never rewritten). The widget carries no
domain logic (binds to `logic/`/`data/`); errors are surfaced, not swallowed. Translatable labels; a11y +
both themes + i18n apply (REQ-P11-UI-008/-009/-010).
**Acceptance:** the browser lists an asset's revisions in order with their metadata (timestamp/author);
selecting a revision shows its content; restoring a prior revision reinstates that content as a new head
revision while the earlier revisions remain in the history (append-only); the widget contains no domain
logic; labels are translatable and both themes render correctly.

#### REQ-P11-DATA-005 — Cross-project reuse: CAS + reference-not-copy (no byte duplication) *(CL-2)*
`traces:` S6, ROADMAP Phase-11 ("assets reuse across projects without duplication"), Article VII, Researcher §4
An asset can be **referenced by more than one project without duplicating its payload**. Bytes are stored
**once** in the content-addressable store keyed by `content_hash`; each project holds a **reference**
(`asset_id` → `content_hash`), **never a byte copy** — this is the precise meaning of "without
duplication" (Researcher §4.1/§4.2). Because references are by stable id + content hash, moving/renaming an
asset does **not** break a reference (only a deleted id or a hash mismatch does — REQ-P11-LOGIC-005).
**Exporting a project resolves its reference set and bundles exactly the referenced blobs**, producing a
self-contained, portable artifact (Researcher §4.2). Any imported reference is untrusted input:
schema+caps validation and path-traversal defence (`resolve()` + containment within the library root,
Article VII / REQ-P11-DATA-002) apply.
**Acceptance:** an asset referenced by ≥2 projects stores its bytes exactly once in the CAS (a second
project referencing the same content is a dedup no-op — no duplicate blob); each project holds a reference
(`asset_id`→`content_hash`), not a copy of the payload; exporting a project bundles exactly the blobs its
references resolve to and the export opens self-contained; an imported reference whose path escapes the
library root or violates a cap is rejected with a domain error.

#### REQ-P11-DATA-006 — Asset-library storage substrate: local-first, cloud optional *(CL-3)*
`traces:` S7, Article I, Phase-10 `data/cloud/` backbone, Researcher §4.2/§6
The catalog + tags + versions + CAS blobs **work fully offline against a local store by default** (no
cloud requirement). When a **Phase-10 provider is connected**, the same CAS/library **MAY** be backed by
the **Phase-10 shared/cloud storage** (the "team" dimension) — an **abstraction layer hides local-vs-cloud**
so callers above the storage port are unchanged, and **nothing above the port names a specific provider**
(Article I / Phase-10 provider isolation). When cloud-backed, the Phase-10 provider-isolation +
untrusted-input + membership posture applies, and blobs fetched from the shared store are content-hash
verified (REQ-P11-DATA-004).
**Acceptance:** with no provider connected, the full catalog/tags/versions/CAS operate offline against the
local store; when a Phase-10 provider is connected, the identical library/CAS operations are served by the
shared backend transparently (the abstraction selects the backend; callers unchanged); no module above the
storage port names a specific provider (grep + `check_layering`); a cloud-fetched blob whose content hash
mismatches is rejected.

#### REQ-P11-LOGIC-005 — Break detection: passive flag from a reference-validation pass *(CL-4)*
`traces:` P2, S11, ROADMAP Phase-11 ("flags a break when a referenced asset changes"), Researcher §2, Article VI
A reference is **BROKEN** when its target `asset_id` is **absent** (deleted asset) or its recorded
dependency **content-hash no longer matches** the current target (Researcher §2.2). A pure, deterministic
**reference-validation pass** walks the dependency DAG and **flags** every incoming edge to a
missing/changed node; the flag is **surfaced on the dependency query result** (pull-based, not pushed) and
**recomputed on catalog change** (a triggered revalidation). **Content-hash gating** limits work to
dependents of nodes whose `content_hash` changed since the last pass (Researcher §2.3) — no full-graph
rescan. A valid reference is never falsely flagged. Live push-notification is explicitly a **FUTURE
enhancement, out of core acceptance**. Pure, Qt-free, off the per-frame loop (REQ-P11-LOGIC-008).
**Acceptance:** a reference whose target id is absent, or whose recorded dependency content-hash mismatches
the current target, is flagged BROKEN by the validation pass; the flag appears on the dependency query
result and is recomputed when the catalog changes; a reference to an unchanged, present target is never
flagged (no false positive); revalidation touches only dependents of changed nodes (content-hash gating);
the pass is pure/deterministic/pull-based (no event push) and imports no Qt (`check_layering` passes).

#### REQ-P11-UI-006 — Break-warning surface (passive indicator) *(CL-4)*
`traces:` REQ-P11-LOGIC-005, REQ-P11-UI-005, Article V
The UI **surfaces broken references as a passive indicator** on the dependency-graph view and/or the
library list, reflecting the reference-validation pass (REQ-P11-LOGIC-005); the indicator **refreshes when
the catalog changes** (triggered revalidation). It is a passive surface — **no live push alert** (that is a
FUTURE enhancement). The widget carries no domain logic (binds to `logic/`). Translatable labels; a11y +
both themes + i18n apply.
**Acceptance:** an asset with a broken reference shows a break indicator in the dependency-graph view
and/or library; the indicator matches the validation pass and refreshes after a catalog change; an asset
with only valid references shows no break indicator; the surface is passive (no push notification); the
widget contains no domain logic and both themes render correctly.

#### REQ-P11-UI-007 — Cross-project reuse UI (reference a shared asset, no copy) *(CL-2)*
`traces:` REQ-P11-DATA-005, Article V
The UI lets the user **reference an existing shared asset into a project** (adds a reference by
`asset_id`/`content_hash`, **not** a byte copy — REQ-P11-DATA-005) and **indicates when an asset is shared
/ referenced** across projects. The widget carries no domain logic (binds to `data/`/`logic/`); errors are
surfaced. Translatable labels; a11y + both themes + i18n apply.
**Acceptance:** referencing a shared asset into a project makes it appear in the project without
duplicating its payload (the reference is added; the CAS blob count is unchanged); the UI marks an asset
that is referenced by more than one project as shared; the widget contains no domain logic; labels are
translatable and both themes render correctly.

## 5. Non-functional requirements (constitution-tied acceptance)

Captured inline in §4: REQ-P11-DATA-002 (security / untrusted metadata + path-traversal, Article VII),
REQ-P11-LOGIC-007 (bounded numerics, Article II), REQ-P11-LOGIC-008 (pure + bounded + off the per-frame
loop, Article VI — **re-adjudicated T11-X02**; it previously read *"off the interactive loop / batch"*),
REQ-P11-UI-008 (a11y, Article V), REQ-P11-UI-009 (both themes, Article V), REQ-P11-UI-010
(i18n, Article V), REQ-P11-UI-011 (synchronous-on-the-GUI-thread, no worker to manage — **re-adjudicated
T11-X02**; it previously read *"stays-responsive"*). Article I (three-layer purity) governs the whole
phase: catalog/version/reuse stores are Qt-free `data/`; models are Qt-free `logic/`; the only Qt is
`ui/` (+ `ui/commands.py` for the tag-undo wrapper). Article IV (testing) and Article X (traceability)
apply per the matrix.

## 6. Non-goals (explicit; deferred)

- **FW-P11-1 — off-GUI-thread asset operations, with progress + cancel (FUTURE WORK, added by the T11-X02
  re-adjudication, 2026-07-30).** Phase 11 ships every asset operation **synchronously on the GUI thread**
  (REQ-P11-LOGIC-008 / REQ-P11-UI-011, as corrected). Moving catalog scan/build, search, dependency-graph
  query and the break-detection pass onto a worker (the `ui/export_worker.py` / `ui/automation_worker.py` /
  `ui/cloud_worker.py` / `ui/realtime_worker.py` / `ui/assistant_worker.py` precedent this project already
  uses elsewhere), with a progress + cancel affordance, is **recorded here as future work so the ambition
  is not lost** — it is explicitly **not** a Phase-11 requirement and was never built. Whoever takes it up
  must mint a **new REQ-ID in the owning future phase** (do not re-widen these two ids), and must first
  **measure** the synchronous latency at `MAX_CATALOG_ASSETS` — Phase 11 has no such measurement, so the
  threshold that would justify the work does not yet exist.
- **Re-authoring the tracked entities** (Phase 5 animation, Phase 6 tileset/tilemap, Phase 1
  `Document`/`PixelBuffer`) or the `.pixproj` serialiser (PIO-1) — Phase 11 **catalogs and references**
  them; it does not fork them (Article I).
- **The concrete graph representation / search index strategy / hashing scheme / storage substrate /
  version wire format** — AGT-01 plan/ADR HOW, grounded by the Researcher (§8 DEP-R).
- **Identity / account / billing / permission model beyond what Phase 10 already provides** — out of
  Phase 11 (the "team" surface reuses Phase-10 membership if CL-3 selects the cloud backbone).
- No plan/tasks (AGT-01); no logic/UI/data/test code (AGT-03/05/04/06); no new technology decided here (S8).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED:** Phase 5 `logic/animation.py` (`Frame`/`FrameTag`/named
  animations), Phase 6 `logic/tileset.py` + `logic/tilemap.py` (`Tileset`/`Tilemap`), Phase 1
  `logic/document.py` (`Document`/`PixelBuffer`, DOC-1), Phase 1/4/6 `data/project_io.py` (PIO-1), and the
  Phase 10 cloud/version-history/CRDT + `data/cloud/` backbone. Phase 11 **composes** these; it must not
  re-implement any of them (Article I).
- **The tracked entities define the dependency edges:** a `Tileset` **references a source-image
  `PixelBuffer`** (sprite→tileset), a named animation **references `Frame`s** built from sprites
  (sprite→animation), a `Tilemap` **references a `Tileset`** (tileset→tilemap) — this is the concrete
  `sprite → animation → tileset (→ tilemap)` graph the ROADMAP names.
- **Researcher grounding LANDED** (`docs/subagent-report-the-researcher-a37ee154-20260704T204011.md`). It
  grounded the orchestrator's §10 adjudications (stable-id catalog, dependency DAG, content-hash/CAS,
  reference-not-copy, path-traversal defence) and carries the HOW vocabulary into AGT-01's plan (§8 DEP-R).
- **Article VI posture:** all Phase-11 operations are **pure, bounded and synchronous, and none is invoked
  from the per-frame render path** (REQ-P11-LOGIC-008); no requirement re-enters the per-frame budget
  (unlike Phase-10 Slice-C). *(T11-X02, 2026-07-30: this line previously read "all Phase-11 operations are
  **batch/off-loop** (REQ-P11-LOGIC-008)". "Batch/off-loop" was read as off-GUI-thread and no such
  mechanism shipped — see the correction note under REQ-P11-LOGIC-008.)*

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

- **DEP-R (Researcher — LANDED, `docs/subagent-report-the-researcher-a37ee154-20260704T204011.md`):**
  grounds the §10 adjudications and supplies the HOW vocabulary AGT-01 carries into `sdd-plan` — catalog by
  **stable AssetId + sidecar** (§1); dependency **DAG** with depends-on / dependents-of queries + cycle
  handling (incremental topo-order or per-edge DFS re-check) (§2); **content hashing** as the CAS key +
  change detector (§3/§4); **CAS + reference-not-copy** for reuse and revisions (§4); path-traversal
  defence via `resolve()` + containment (§5). The exact graph representation, hash scheme, index strategy,
  and version wire format remain AGT-01 plan/ADR choices grounded on this report.
- **DEP-1 (AGT-01):** placement of the catalog / version / shared-asset stores under `data/` (and, if CL-3
  = cloud, behind the Phase-10 `data/cloud/` port family) + `check_layering`/`check_cycles` proof + any
  ADR (e.g. asset identity/hashing, graph model).
- **DEP-2 (AGT-01):** concrete constant values for REQ-P11-LOGIC-007.
- **DEP-3 (AGT-10, conditional):** only if a large-catalog dependency-graph **render** proves heavy —
  Phase-11 domain ops are not on the per-frame path (REQ-P11-LOGIC-008, as corrected by T11-X02: *not on
  the per-frame path*, **not** "off-loop" in the off-GUI-thread sense); this is a UI-render flag, not an
  acceptance change.

## 9. Traceability

See `specs/phase-11-team-asset-management/traceability.md` — REQ ↔ dossier S-id ↔ acceptance scenario ↔
(future) test. **All 26 REQs now carry a Gherkin scenario** (§ acceptance file) and a `covered` matrix
row; no row remains `PENDING`/`blocked`.

## 10. Clarifications — ADJUDICATED (recorded as category-1 sources; `sdd-plan` UNBLOCKED)

> These four questions were **acceptance-changing product/scope decisions** (SUSPENDED per A2-D2 at first
> authoring). They are now **ADJUDICATED by the orchestrator, grounded in the Researcher report**
> (`docs/subagent-report-the-researcher-a37ee154-20260704T204011.md`). Each answer below is a resolved
> **category-1 source**, encoded into the gated REQs (§4b) with full acceptance + Gherkin + traceability.

- **CL-P11-1 — Asset version control substrate. → RESOLVED: HYBRID reusing Phase 10.** Content-hash-based
  change detection + an **append-only, content-addressable asset-revision store**. Asset revisions are NOT
  routed through the live-collab CRDT (the CRDT remains for live documents only); the **shipped Phase-10
  content-hashing / CAS primitives are reused**. *(Encoded in REQ-P11-DATA-004, REQ-P11-LOGIC-006,
  REQ-P11-UI-004; also anchors REQ-P11-DATA-006.)*

- **CL-P11-2 — Cross-project reuse mechanism. → RESOLVED: content-addressable store + reference-not-copy.**
  Bytes stored **once**, addressed by content hash; projects **reference** assets by stable id/hash and
  **never duplicate bytes**; **export bundles the referenced blobs** for portability. This is the precise
  meaning of "reuse without duplication." *(Encoded in REQ-P11-DATA-005, REQ-P11-UI-007.)*

- **CL-P11-3 — Asset-library storage scope. → RESOLVED: local-first, cloud optional.** The library works
  fully **offline/local** with no cloud requirement; when a Phase-10 provider is connected, the CAS/library
  **MAY** be backed by Phase-10 shared storage. A **CAS abstraction layer hides local-vs-cloud**; nothing
  above the port names a provider. *(Encoded in REQ-P11-DATA-006; anchors the substrate of DATA-001/-004/
  -005.)*

- **CL-P11-4 — Break-detection semantics. → RESOLVED: passive flag on a validation / query pass +
  triggered revalidation.** A broken reference (missing target stable-id or content-hash mismatch) is
  computed by a **reference-validation pass** and **surfaced (flagged) on query and in the dependency
  view**; revalidation runs on catalog change. **Live push-notification is a FUTURE enhancement, NOT core
  acceptance.** *(Encoded in REQ-P11-LOGIC-005, REQ-P11-UI-006.)*

**Status:** all four adjudicated and encoded; the eight gated REQs are finalised (acceptance + Gherkin +
matrix). This spec is **COMPLETE** and `sdd-plan` (AGT-01) is **UNBLOCKED**.
