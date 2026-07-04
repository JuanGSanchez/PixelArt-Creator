# Plan — Phase 11: Team & Asset Management

| Field | Value |
| --- | --- |
| Feature | `phase-11-team-asset-management` |
| Author | Claude (AGT-01, Architecture) via `sdd-plan` |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, **VI**, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 11 before any `logic/{content_hash,asset_catalog,asset_tags,asset_query,dependency_graph,break_detection,asset_version}.py`, `data/{asset_storage,asset_cas,asset_catalog_io,asset_revision_store,asset_shared_backend,asset_export}.py`, or asset-management UI exists. The **shipped** tracked entities are **REUSED, not re-authored**: Phase-1 `logic/document.py` (`Document`/`PixelBuffer`, DOC-1) + `data/project_io.py` (PIO-1), Phase-5 `logic/animation.py` (`Frame`/`FrameTag`/named animations), Phase-6 `logic/tileset.py` + `logic/tilemap.py` (`Tileset`/`Tilemap`), and Phase-10 `data/cloud/` shared storage + `logic/version_history.py` (the *shape* precedent). |
| Over spec | `specs/phase-11-team-asset-management/spec.md` (26 REQ: `REQ-P11-DATA-001..007`, `REQ-P11-LOGIC-001..008`, `REQ-P11-UI-001..011`) + `acceptance.md` + `traceability.md`. §10 clarifications **ADJUDICATED** (CL-P11-1..4); 0 PENDING rows. |
| Stack source | S8 (fixed) — Python 3.12+, stdlib + NumPy (shipped). **NO new runtime dependency**: content hashing uses stdlib **`hashlib`** (already used in `data/export_io.py` + `data/cloud/auth.py`). No AGT-09 manifest change required (PL11-D5). |
| Grounding | The Researcher — `docs/subagent-report-the-researcher-a37ee154-20260704T204011.md` (LANDED). Grounds every §10 adjudication. No RESEARCH REQUEST needed (PL11-D1 Branch B). |
| ADRs filed | **ADR-0030** (asset catalog by stable `AssetId` + sidecar; content-hash primitive; content-addressable store; reference-not-copy + export; asset-revision DAG — and the honest ruling that Phase 11 **introduces** content-hash/CAS, reusing the Phase-10 *shape*, not a pre-existing primitive); **ADR-0031** (dependency graph DAG + depends-on/dependents-of + content-hash-gated break-detection pass + cycle handling); **ADR-0032** (local-first / cloud-optional `BlobBackend` abstraction; optional Phase-10 shared-storage backing; provider isolation) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-11 spec — the
**studio-level asset-management** milestone: catalog the shipped entities as reusable assets with tags
and search/filter; keep a content-hash-addressed version history per asset; make the dependency graph
(`sprite → animation → tileset → tilemap`) queryable with a passive break flag; and reuse assets across
projects without duplicating bytes — while keeping the client's three-layer purity intact and the whole
local core hermetically CI-testable with **no network, no credentials, and no new dependency**. It maps
every REQ to its S11 layer, **freezes the public interface** of the new `logic/` models and `data/`
stores before implementation, rules the DEP-1/DEP-R HOW decisions in **ADR-0030 / ADR-0031 / ADR-0032**,
places the seven new numerics in `logic/constants.py` with names distinct from every shipped constant
(Article II / BF-1), and confirms the **Article VI posture** (all Phase-11 domain ops are batch/off the
per-frame loop; no AGT-10 per-frame directive is required — a large-catalog graph *render* is a
conditional UI-only flag, DEP-3). It is decomposed **slice-by-slice** in `tasks.md`, each an
independently gate-green, CI-green shippable increment.

**Central honesty ruling (ADR-0030 §Context).** The shipped tree has **no** content-hashing or CAS
primitive: `logic/version_history.py` keys by an opaque `version_id`, not a content hash. Phase 11
therefore **introduces** `logic/content_hash.py` + `data/asset_cas.py`. "Reuse Phase 10" (CL-1) is
honoured at the level of **shape/pattern** — the asset-revision model reuses the immutable-ordered-history
shape of `version_history.py` at asset granularity; the storage layer reuses the provider-agnostic port
+ defensive-load pattern of `data/cloud/port.py`. AGT-03 builds new modules; it does not import a
non-existent shared hasher.

## 2. The identity + provider-isolation invariants (Article I + VII — CENTRAL; ADR-0030/0032)

> **(a) Assets are identified by a stable `AssetId` and referenced by `(AssetId, content_hash)` — never
> by path.** A move/rename is not a break; only a deleted id or a content-hash mismatch is (ADR-0031).
> **(b) No provider SDK type, credential/token type, HTTP/network type, or `data/cloud/` type appears
> above the `BlobBackend` port** — the library is local-first and provider-agnostic; the optional
> Phase-10 shared backing is one `BlobBackend` implementation, selected transparently (ADR-0032).
> **(c) The asset payload is the shipped PIO-1 `.pixproj` form — the catalog adds NO new payload
> serialiser** (Article I / REQ-P11-DATA-007); the catalog/sidecar is metadata/index over references.
> **(d) All imported catalogs/metadata/references are untrusted input** — schema+caps validated,
> `eval`/`exec`-free, path-traversal-defended (`resolve()` + containment), content-hash-verified on
> fetch (Article VII / REQ-P11-DATA-002).

Realised **structurally**: the new `logic/` models are pure leaves over `constants` (+ `content_hash`);
the new `data/` stores compose PIO-1 and a `BlobBackend`; the optional shared backend composes the
existing governed `data/cloud/` subpackage. `check_layering`/`check_cycles` stay exit 0 (§11) — **no new
layering rule is needed** (unlike Phase 10's `sync_backend`): everything lands inside the existing three
layers.

## 3. Stack / domain decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language / stack | Python 3.12+; stdlib + NumPy (shipped); reuse `document`/`animation`/`tileset`/`tilemap` (entities), `project_io` (PIO-1), `data/cloud/` (shared storage) | S8 |
| Content hash | stdlib **`hashlib`** SHA-256 over **canonicalized** asset bytes; one pure `content_hash(blob)->str`; equal bytes ⇒ equal hash ⇒ "unchanged" | REQ-P11-DATA-004; ADR-0030 §3; Researcher §3.2 |
| Catalog identity | stable **`AssetId`** (UUID) + **per-asset sidecar**; references stored as `(AssetId, content_hash)`; `path` advisory only | REQ-P11-DATA-001; ADR-0030 §1; Researcher §1 |
| Asset payload | shipped **PIO-1** `.pixproj` (composed); **no new payload serialiser**; catalog = index/metadata over references | REQ-P11-DATA-007; ADR-0030 §2; Article I |
| Tags | pure tag model; **reversible** add/remove as a do/undo pair (HIS-1 pattern) wrapped by `ui/commands.py`; idempotent | REQ-P11-DATA-003, REQ-P11-LOGIC-002; Researcher §1.2 |
| Search / filter | pure deterministic query `f(catalog snapshot, query)` → stably-ordered set (name substring AND tag AND kind); empty query → full catalog | REQ-P11-LOGIC-003; ADR-0030; Researcher §1.3 |
| CAS + reuse | content-addressable store keyed by hash; **write-once dedup**; projects **reference** `(AssetId→hash)`, never copy bytes; **export bundles referenced blobs** | REQ-P11-DATA-005; ADR-0030 §4/§5; Researcher §4 |
| Version control | append-only **content-addressable revision store** + immutable ordered **revision DAG** at asset granularity (`content_hash`+`parent_hash`); **NOT** via the live-collab CRDT | REQ-P11-DATA-004, REQ-P11-LOGIC-006; ADR-0030 §6; Researcher §3.1 (hybrid) |
| Dependency graph | directed **DAG** of `AssetId` nodes + hash-pinned edges; `dependencies_of`/`dependents_of`; cycle-safe (white/grey/black DFS) + depth-bounded (`MAX_DEPENDENCY_DEPTH`) | REQ-P11-LOGIC-004; ADR-0031 §1/§2; Researcher §2.1/§2.3 |
| Break detection | pure **content-hash-gated reference-validation pass** → per-edge BROKEN flag (missing id or hash mismatch); **pull-based**, recomputed on catalog change; no push | REQ-P11-LOGIC-005; ADR-0031 §3; Researcher §2.2/§2.3; CL-4 |
| Storage substrate | **local-first, cloud optional**: one `BlobBackend` port; `LocalBlobBackend` default (offline); `SharedBlobBackend` composes Phase-10 `data/cloud/` when a provider is connected; nothing above the port names a provider | REQ-P11-DATA-006; ADR-0032; CL-3; Researcher §4.2/§6 |
| Untrusted input | catalog/sidecar/reference schema+caps validation; path-traversal defence (`resolve()`+containment); **never `eval`/`exec`**; content-hash-verify fetched blobs | REQ-P11-DATA-002; ADR-0030 §5/ADR-0032 §3; Researcher §5 |
| Responsiveness | asset ops batch/off the GUI thread (a `ui/asset_worker.py`, the Phase-7/8/10 worker precedent); progress/cancel where warranted | REQ-P11-UI-011; Article VI |
| **Article VI** | **all Phase-11 domain ops off the per-frame loop** (batch); 16 ms `FRAME_BUDGET_MS` does not gate them; **NO AGT-10 per-frame directive required** — a large-catalog graph *render* is a conditional UI-only flag (DEP-3) | REQ-P11-LOGIC-008, REQ-P11-UI-011; spec §8 DEP-3 |
| Bounds | 7 named constants in `logic/constants.py`; exceeding → domain error | REQ-P11-LOGIC-007; Article II/VII; §8 |
| Testing | pytest + Hypothesis (logic/data headless — CAS dedup, canonical-hash determinism, graph queries, break pass, tag do/undo, query determinism; property tests over permuted inputs), pytest-qt both themes (UI); local core needs **no** network/creds | S8, Article IV; Researcher §6 |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-11 logic/data decision places Qt in `logic/`/`data/` (**PL11-D2 → Branch B held**). All asset
UI lives in `ui/`; the sole Qt file outside `ui/` remains `ui/commands.py` — extended this phase with a
**tag add/remove `QUndoCommand` wrapper** (the one new undoable operation, wrapping the pure
`logic/asset_tags` do/undo pair; PL11-D3).

## 4. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`; `data/` → `logic/` + `data/` siblings) and
acyclic (verified §11). No `logic → data`, no `logic`/`data` → `ui`/Qt.

### 4.1 New `logic/` modules (pure, zero Qt)

| Module | Responsibility | Depends on (intra) | REQ | Slice |
| --- | --- | --- | --- | --- |
| `constants.py` *(extend)* | Add 7 asset numerics (leaf, no imports). **Names distinct from every shipped constant (BF-1).** | — | LOGIC-007 | 1/2/3 |
| `content_hash.py` **(new)** | `content_hash(blob: bytes) -> str` (stdlib `hashlib` SHA-256 over canonicalized bytes); `same_content(a, b) -> bool`; deterministic. `ContentHashError`. | `constants` | DATA-004, LOGIC-006 | 1 |
| `asset_catalog.py` **(new)** | `AssetKind` (module-local enum), `AssetDescriptor` (id/kind/name/tags/metadata/content_hash/path), `AssetCatalog` (add/remove/get/enumerate) — pure, deterministic. `AssetCatalogModelError`. | `constants`, `content_hash` | DATA-001, LOGIC-001 | 1 |
| `asset_tags.py` **(new)** | Pure tag membership + **reversible** `make_add_tag`/`make_remove_tag` → do/undo pair (minimal prior state); idempotent; bounded by `MAX_TAGS_PER_ASSET`/`MAX_TAG_BYTES`. `AssetTagError`. | `constants` | LOGIC-002, DATA-003 | 1 |
| `asset_query.py` **(new)** | Pure deterministic `query(catalog, name=None, tags=(), kind=None)` → stably-ordered entries; filters intersect; empty → full catalog. `AssetQueryError`. | `asset_catalog`, `constants` | LOGIC-003 | 1 |
| `dependency_graph.py` **(new)** | `DependencyGraph` of `AssetId` nodes + hash-pinned edges; `dependencies_of`/`dependents_of`; cycle-safe + depth-bounded (`MAX_DEPENDENCY_DEPTH`). `DependencyGraphError`. | `constants` | LOGIC-004 | 2 |
| `break_detection.py` **(new)** | Pure content-hash-gated reference-validation pass → per-edge BROKEN flags; pull-based; recomputed on change. `BreakDetectionError`. | `dependency_graph`, `content_hash`, `constants` | LOGIC-005 | 2 |
| `asset_version.py` **(new)** | `AssetRevision` (asset_id/content_hash/parent_hash/created_marker/author) + `AssetVersionHistory` (ordered, immutable; `append`→new; head; hash comparison; ≤ `MAX_ASSET_VERSIONS`). `AssetVersionError`. | `constants`, `content_hash` | LOGIC-006 | 3 |

`constants.py` stays a leaf. `AssetKind` is **module-local** enumerated vocabulary (ADR-0001 precedent).
All new `logic/` modules reach only `constants`/`content_hash` — pure downward leaves, **no
`logic → data`**, no cycle.

### 4.2 New `data/` modules (Qt-free I/O + persistence)

| Module | Responsibility | Depends on | REQ | Slice |
| --- | --- | --- | --- | --- |
| `asset_storage.py` **(new)** | `BlobBackend` ABC (`put_blob`/`get_blob`/`has_blob` by content_hash) + `LocalBlobBackend` (offline default); the local-vs-cloud seam. `AssetStorageError`. Zero Qt. | `logic/constants` | DATA-006 | 1 |
| `asset_cas.py` **(new)** | `ContentAddressableStore` over a `BlobBackend`; write-once dedup; `MAX_BLOB_BYTES` cap; content-hash-verify on fetch (mismatch → reject). `CasError`. Zero Qt. | `logic/content_hash`, `logic/constants`, `asset_storage` | DATA-004, 005 | 1 |
| `asset_catalog_io.py` **(new)** | Catalog + per-asset **sidecar** persistence (stable `AssetId`); composes **PIO-1** for payloads (no new serialiser); schema+caps validation; **path-traversal guard** (`resolve()`+containment); `AssetCatalogError(ProjectIOError)`. Zero Qt. | `data/project_io`, `logic/asset_catalog`, `logic/constants` | DATA-001, 002, 003, 007 | 1 |
| `asset_revision_store.py` **(new)** | Append-only content-addressable **revision store**; stores bytes once via `asset_cas`; immutable descriptors; hash-verified fetch; **append-only** (no in-place mutate/delete); NOT via CRDT. `AssetRevisionStoreError`. Zero Qt. | `asset_cas`, `logic/asset_version`, `logic/constants` | DATA-004 | 3 |
| `asset_shared_backend.py` **(new)** | `SharedBlobBackend(BlobBackend)` composing **Phase-10 `data/cloud/`** shared storage — optional cloud backing behind the SAME port; hash-verified fetch; **no provider type above the port**. Zero Qt. | `data/cloud/*`, `asset_storage`, `logic/content_hash`, `logic/constants` | DATA-006 | 3 |
| `asset_export.py` **(new)** | Resolve a project's reference set → **bundle exactly the referenced CAS blobs** into a self-contained artifact; import defence (path-traversal + caps). `AssetExportError(ProjectIOError)`. Zero Qt. | `asset_cas`, `asset_catalog_io`, `logic/constants` | DATA-005 | 3 |

`AssetCatalogError`/`AssetExportError` subclass `ProjectIOError` (PIO-1 family, so a caller may catch
either). All `data/` edges point **down** into `logic/` + `data/` siblings (+ the existing `data/cloud/`);
**no `data → ui`/Qt**, no cycle.

### 4.3 New `ui/` modules (Qt only)

| Module | Responsibility | REQ | Slice |
| --- | --- | --- | --- |
| `asset_library_panel.py` **(new)** | `Asset_Library_Panel` — browse catalog entries (kind/name/tags); updates on catalog change; binds to `logic/`+`data/`, no domain logic. `tr()` + `changeEvent`. | UI-001 | 1 |
| `asset_tagging_panel.py` **(new)** | `Asset_Tagging_Panel` — add/remove tags; **undoable** via the shared undo stack (wraps `logic/asset_tags` do/undo through `ui/commands.py`); bound-exceeded → translatable error. | UI-002 | 1 |
| `asset_search_panel.py` **(new)** | `Asset_Search_Panel` — search (name) + filter (tag/kind) driving the pure query; clearing restores full list. | UI-003 | 1 |
| `commands.py` *(extend)* | Add `AddTagCommand`/`RemoveTagCommand` `QUndoCommand` wrappers over the pure `logic/asset_tags` do/undo pair (the one new undoable op; PL11-D3). | UI-002 | 1 |
| `asset_worker.py` **(new)** | Off-GUI-thread runner for catalog scan/build, search, graph query so the UI never freezes (Phase-7/8/10 worker precedent). | UI-011 | 1 |
| `dependency_graph_view.py` **(new)** | `Dependency_Graph_View` — visualise depends-on/dependents for a selected asset; cycle shown without hang. | UI-005 | 2 |
| `break_warning_surface` (in `dependency_graph_view.py` / `asset_library_panel.py`) | Passive break indicator reflecting the validation pass; refreshes on catalog change; no push. | UI-006 | 2 |
| `asset_version_browser.py` **(new)** | `Asset_Version_Browser` — list revisions (ordered, metadata); inspect + **restore** (reinstates as a new head; append-only). | UI-004 | 3 |
| `asset_reuse_panel.py` **(new)** | `Asset_Reuse_Panel` — reference a shared asset into a project (reference, not copy); mark shared/referenced assets. | UI-007 | 3 |

Every `ui/` module wraps user-visible strings in `tr()`/`translate()` and overrides `changeEvent()` to
retranslate on `QEvent.LanguageChange` (REQ-P11-UI-010); a11y names/focus (UI-008) and both-theme
role-based colours (UI-009) apply to every surface.

### 4.4 Layering — no new rule needed (contrast with Phase 10)

Unlike Phase 10 (which added the out-of-layer `sync_backend/`), **every Phase-11 module lands inside the
existing three layers**. `data/cloud/` is already a governed `data/` subpackage (zero Qt). Therefore
`scripts/check_layering.py` / `scripts/check_cycles.py` need **no edit** — the new modules are governed
by the existing rules. Baseline is clean (§11); each new module must keep it green.

## 5. Frozen interface contracts (Slices 1/2/3)

Frozen **before** implementation so downstream slices bind to a stable, Qt-free surface. Exceptions
subclass `ValueError` (Phase-1 convention); `AssetCatalogError`/`AssetExportError` subclass
`ProjectIOError` (PIO-1 family). `AssetKind` is module-local (ADR-0001). Pure functions are
deterministic (no wall-clock/random/locale; `created_marker` is an opaque input, the Phase-10 precedent).

```python
# logic/content_hash.py — the content-hash primitive (zero Qt; Slice 1)
class ContentHashError(ValueError): ...
def content_hash(blob: bytes) -> str:
    """Deterministic SHA-256 hex over canonicalized asset bytes (stdlib hashlib). REQ-P11-DATA-004."""
def same_content(a: bytes, b: bytes) -> bool:
    """content_hash(a) == content_hash(b); the 'unchanged' change-detector. REQ-P11-LOGIC-006."""

# logic/asset_catalog.py — pure catalog model (zero Qt; Slice 1)
class AssetCatalogModelError(ValueError): ...
class AssetKind(Enum): SPRITE; ANIMATION; TILESET; TILEMAP; PALETTE   # module-local (ADR-0001)
@dataclass(frozen=True)
class AssetDescriptor:
    asset_id: str; kind: AssetKind; name: str
    content_hash: str
    tags: frozenset[str] = frozenset()
    metadata: Mapping[str, object] = MappingProxyType({})
    path: Optional[str] = None                # advisory/display only; resolved via asset_id
class AssetCatalog:
    def add(self, entry: AssetDescriptor) -> "AssetCatalog": ...     # <= MAX_CATALOG_ASSETS
    def remove(self, asset_id: str) -> "AssetCatalog": ...
    def get(self, asset_id: str) -> Optional[AssetDescriptor]: ...   # clean not-found (None), never crash
    def entries(self) -> Tuple[AssetDescriptor, ...]: ...            # deterministic order

# logic/asset_tags.py — reversible tag ops (zero Qt; Slice 1)
class AssetTagError(ValueError): ...
def make_add_tag(entry: AssetDescriptor, tag: str) -> Tuple[Callable[[], AssetDescriptor], Callable[[], AssetDescriptor]]:
    """(do, undo) pair; do adds tag (idempotent), undo restores prior tag set. Bounded by
    MAX_TAGS_PER_ASSET/MAX_TAG_BYTES. ui/commands.py wraps as QUndoCommand. REQ-P11-LOGIC-002."""
def make_remove_tag(entry: AssetDescriptor, tag: str) -> Tuple[Callable[[], AssetDescriptor], Callable[[], AssetDescriptor]]: ...

# logic/asset_query.py — pure search/filter (zero Qt; Slice 1)
class AssetQueryError(ValueError): ...
def query(catalog: AssetCatalog, *, name: Optional[str] = None,
          tags: Sequence[str] = (), kind: Optional[AssetKind] = None) -> Tuple[AssetDescriptor, ...]:
    """Stably-ordered intersection of name-substring AND tag(s) AND kind; empty query -> full catalog;
    byte-identical across runs. REQ-P11-LOGIC-003."""

# logic/dependency_graph.py — queryable DAG (zero Qt; Slice 2)
class DependencyGraphError(ValueError): ...
@dataclass(frozen=True)
class DependencyEdge: source_id: str; target_id: str; pinned_hash: str
class DependencyGraph:
    def add_edge(self, edge: DependencyEdge) -> "DependencyGraph": ...   # rejects a cycle-inducing edge
    def dependencies_of(self, asset_id: str, *, transitive: bool = False) -> Tuple[str, ...]: ...
    def dependents_of(self, asset_id: str, *, transitive: bool = False) -> Tuple[str, ...]: ...
    # cycle-safe (white/grey/black DFS -> reported, never hung), depth-bounded by MAX_DEPENDENCY_DEPTH.

# logic/break_detection.py — content-hash-gated validation pass (zero Qt; Slice 2)
class BreakDetectionError(ValueError): ...
@dataclass(frozen=True)
class BrokenReference: source_id: str; target_id: str; reason: str   # "missing" | "hash-mismatch"
def find_broken(graph: DependencyGraph, catalog: AssetCatalog,
                *, changed_ids: Optional[Set[str]] = None) -> Tuple[BrokenReference, ...]:
    """Flag edges to a missing target_id or a hash-mismatched target; pull-based; changed_ids gates
    revalidation to dependents of changed nodes; never false-positive. REQ-P11-LOGIC-005."""

# logic/asset_version.py — immutable revision DAG at asset granularity (zero Qt; Slice 3)
class AssetVersionError(ValueError): ...
@dataclass(frozen=True)
class AssetRevision:
    asset_id: str; content_hash: str; created_marker: int
    parent_hash: Optional[str] = None; author: Optional[str] = None
@dataclass(frozen=True)
class AssetVersionHistory:
    revisions: Tuple[AssetRevision, ...]                              # <= MAX_ASSET_VERSIONS
    def append(self, r: AssetRevision) -> "AssetVersionHistory": ...  # new history; > cap -> AssetVersionError
    def head(self) -> AssetRevision: ...

# data/asset_storage.py — the BlobBackend port + local backend (zero Qt; Slice 1)
class AssetStorageError(ValueError): ...
class BlobBackend(ABC):
    @abstractmethod
    def put_blob(self, content_hash: str, blob: bytes) -> None: ...   # write-once/dedup; no provider type
    @abstractmethod
    def get_blob(self, content_hash: str) -> bytes: ...
    @abstractmethod
    def has_blob(self, content_hash: str) -> bool: ...
class LocalBlobBackend(BlobBackend): ...                              # offline default (local-FS/in-memory)

# data/asset_cas.py — content-addressable store over a BlobBackend (zero Qt; Slice 1)
class CasError(ValueError): ...
class ContentAddressableStore:
    def __init__(self, backend: Optional[BlobBackend] = None) -> None: ...   # LocalBlobBackend default
    def put(self, blob: bytes) -> str: ...          # -> content_hash; existing hash = dedup no-op; <= MAX_BLOB_BYTES
    def get(self, content_hash: str) -> bytes: ...   # content-hash-verified; mismatch -> CasError

# data/asset_catalog_io.py — catalog + sidecar persistence (zero Qt; Slice 1)
class AssetCatalogError(ProjectIOError): ...         # PIO-1 family; untrusted-load defence
def save_catalog(catalog: AssetCatalog, root: Path) -> None: ...     # per-asset sidecar; composes PIO-1
def load_catalog(root: Path) -> AssetCatalog: ...    # schema+caps validated; path-traversal-guarded; no eval/exec

# data/asset_shared_backend.py — optional Phase-10 cloud backing (zero Qt; Slice 3)
class SharedBlobBackend(BlobBackend): ...            # composes data/cloud/ shared storage; hash-verified fetch

# data/asset_export.py — reference-set bundling (zero Qt; Slice 3)
class AssetExportError(ProjectIOError): ...
def export_project_assets(reference_ids: Sequence[str], catalog: AssetCatalog,
                          cas: ContentAddressableStore, out: Path) -> None:
    """Resolve references -> bundle exactly the referenced CAS blobs; self-contained. REQ-P11-DATA-005."""
```

## 6. `data/` contract notes

- **Payload = PIO-1, no new serialiser (REQ-P11-DATA-007).** `asset_catalog_io` composes
  `data/project_io` for the asset bytes; the sidecar/index schema is metadata over references only.
- **Untrusted catalog/metadata/reference (REQ-P11-DATA-002).** Schema + caps (`MAX_CATALOG_ASSETS`,
  `MAX_TAGS_PER_ASSET`, `MAX_TAG_BYTES`, `MAX_METADATA_BYTES`, `MAX_BLOB_BYTES`); **path-traversal
  defence** (`resolved = (root / candidate).resolve()`, then `resolved.relative_to(root)` /
  `os.path.commonpath`); **never `eval`/`exec`**; malformed/oversized/escaping → domain error.
- **CAS integrity (REQ-P11-DATA-004/-005).** `put` dedups by hash; `get` recomputes + verifies the hash
  (mismatch → `CasError`) — tamper/corruption defence on both local and shared backends.
- **Append-only revisions (REQ-P11-DATA-004).** `asset_revision_store` never mutates/deletes a revision
  in place; a restore appends a new head; asset revisions never route through the CRDT.
- **Provider isolation (REQ-P11-DATA-006).** `SharedBlobBackend` is the only module that touches
  `data/cloud/`; nothing above `BlobBackend` names a provider (grep + `check_layering`).

## 7. Performance / render budget — Article VI posture (no per-frame re-entry)

- **All Phase-11 domain ops are batch / off the interactive per-frame loop** (REQ-P11-LOGIC-008): catalog
  scan/build, search/filter, tagging, dependency-graph query, break-detection pass, revision record, and
  export run off the GUI thread (`ui/asset_worker.py`); the 16 ms `FRAME_BUDGET_MS` does **not** gate
  them. The contract is **stays-responsive** (REQ-P11-UI-011), verified behaviourally (no freeze).
- **No REQUIRED AGT-10 directive** (contrast Phase-10 Slice C). **Conditional flag (DEP-3):** *only if* a
  large-catalog dependency-graph **render** (the `Dependency_Graph_View` paint path) proves heavy
  interactively does AGT-10 assess it with `frame-profile` — a UI-render concern, not a Phase-11
  acceptance change (spec §8 DEP-3). The domain model stays off-loop regardless.

## 8. Constant placement (Article II / BF-1)

All in `logic/constants.py` (leaf). **New names DISTINCT from every shipped constant.** Values are
AGT-01 defaults (DEP-2), re-verifiable at implementation time; the two AGT-02-flagged bounds
(`MAX_ASSET_VERSIONS`, `MAX_BLOB_BYTES`) are set here.

| Constant | Value | Source / Slice |
| --- | --- | --- |
| `MAX_CATALOG_ASSETS` | `65536` | catalog-size cap (Article VII; parallels `MAX_TILESET_TILES` scale) — Slice 1 |
| `MAX_TAGS_PER_ASSET` | `64` | per-asset tag cap (Article VII; parallels `FAVOURITES_MAX`=64) — Slice 1 |
| `MAX_TAG_BYTES` | `128` | per-tag UTF-8 byte cap (Article VII; short label) — Slice 1 |
| `MAX_METADATA_BYTES` | `4096` | per-asset metadata byte cap (Article VII; parallels `MAX_COMMENT_BYTES`=4096) — Slice 1 |
| `MAX_DEPENDENCY_DEPTH` | `64` | dependency-traversal depth bound (Article VII; cycle/depth guard) — Slice 2 |
| `MAX_ASSET_VERSIONS` | `256` | per-asset revision-history cap (Article VII; AGT-02-flagged; DISTINCT from `MAX_CLOUD_VERSIONS`=100, a different concern) — Slice 3 |
| `MAX_BLOB_BYTES` | `268435456` | per-CAS-blob ceiling, 256 MiB (Article VII; AGT-02-flagged; parallels `MAX_CLOUD_PROJECT_BYTES` — 8K RGBA resident ≈126 MB + headroom) — Slice 1 |

`AssetKind` stays **module-local** enumerated vocabulary (ADR-0001). Note the DISTINCT-name rule:
`MAX_ASSET_VERSIONS` (asset-revision cap) ≠ the shipped `MAX_CLOUD_VERSIONS` (cloud project-version cap);
`MAX_BLOB_BYTES` (CAS blob) shares the *value* of `MAX_CLOUD_PROJECT_BYTES` but is a distinct named
concern.

## 9. Implementation strategy — slice-by-slice (each independently gate-green / CI-green)

Detailed work items in `tasks.md`. **Adjusted from the spec/task literal "UI in Slice 3": each slice
ships its own logic + data + UI so it is a genuinely shippable, gate-green increment** (the task
explicitly permits adjusting to keep shippable increments). Per-slice flow: **AGT-03 logic/data +
AGT-04 tests → AGT-05 ui + AGT-06 QA/a11y + AGT-07 i18n → AGT-08 docs → AGT-01 final gate →
AGT-09 commit.**

- **Slice 1 — Local catalog core (content-hash + CAS/dedup + catalog(stable-id+sidecar) + tagging +
  search/filter + library/tagging/search UI):** the fully-local, fully-testable, highest-value core.
  - **1 (logic):** `constants` (Slice-1 subset) + `content_hash` + `asset_catalog` + `asset_tags` +
    `asset_query`. REQ-P11-LOGIC-001/-002/-003/-007/-008.
  - **1 (data):** `asset_storage` (`BlobBackend`+`LocalBlobBackend`) + `asset_cas` + `asset_catalog_io`.
    REQ-P11-DATA-001/-002/-003/-005(dedup/reference core)/-006(local)/-007.
  - **1 (ui):** `asset_library_panel` + `asset_tagging_panel` (+ `ui/commands.py` tag undo) +
    `asset_search_panel` + `asset_worker`. REQ-P11-UI-001/-002/-003/-008/-009/-010/-011.
  - **Ship gate 1:** CAS dedup + canonical-hash determinism + catalog round-trip (PIO-1) + tag
    persist/undo + query determinism green in CI; layering/cycles exit 0; a11y + both themes + i18n
    green. → **cleared to AGT-03/AGT-04.**
- **Slice 2 — Dependency graph + break detection (+ graph view + break surface):**
  - **2 (logic):** `dependency_graph` + `break_detection`. REQ-P11-LOGIC-004/-005.
  - **2 (ui):** `dependency_graph_view` + passive break indicator. REQ-P11-UI-005/-006.
- **Slice 3 — Versioning + cross-project reuse + cloud-optional backing (+ version browser + reuse UI):**
  - **3 (logic):** `asset_version`. REQ-P11-LOGIC-006.
  - **3 (data):** `asset_revision_store` + `asset_shared_backend` + `asset_export`.
    REQ-P11-DATA-004/-005(export)/-006(cloud).
  - **3 (ui):** `asset_version_browser` + `asset_reuse_panel`. REQ-P11-UI-004/-007.

Reversibility boundary: only **tag add/remove** is undoable (PL11-D3, `ui/commands.py`); catalog
scan/version/reuse/export are session/library state and push no `QUndoCommand`.

## 10. Constitution compliance (self-check)

- **I:** catalog/CAS/revision/reuse stores in ZERO-Qt `data/`; hash/catalog/tag/query/graph/break/version
  models in ZERO-Qt `logic/`; all asset UI in `ui/`; the one Qt file outside `ui/` remains
  `ui/commands.py` (extended with the tag-undo wrapper). No `logic → data`; **no new layering rule**
  (everything inside the three layers); baseline verified exit 0 (§11).
- **II:** 7 new constants in `constants.py`, names distinct from every shipped constant (BF-1); `AssetKind`
  intrinsic-local (ADR-0001).
- **III:** Black/isort/flake8/mypy-strict for `logic/`+`data/`; typed frozen contracts (§5).
- **IV:** the whole Slice-1 core + Slice-2 graph/break + Slice-3 versioning/reuse are CI-testable
  **headless with no network/creds** (local backend + fixtures); property tests (canonical-hash
  determinism, CAS dedup, query determinism, permuted-order graph queries, tag do/undo). Only the
  optional `SharedBlobBackend` live path reuses Phase-10's out-of-CI provider marker. Coverage ≥90/80.
- **V:** REQ-P11-UI-008/-009/-010 (a11y + both themes + i18n) are blocking gates across every Slice's UI;
  UI-011 stays-responsive verified behaviourally.
- **VI:** **all Phase-11 domain ops off the per-frame loop**; 16 ms budget never gates them; **no REQUIRED
  AGT-10 directive** — a large-catalog graph *render* is the only conditional UI flag (DEP-3).
- **VII — CENTRAL:** imported catalogs/metadata/references untrusted → schema+caps, path-traversal
  defence (`resolve()`+containment), content-hash-verify on fetch, **never `eval`/`exec`**; bounded
  numerics (§8); portable paths (`path_portability_check`); PIO-1 defensive-load reuse.
- **VIII:** this plan + `analyze-report.md` are the pre-implement gate; dispatch held until C1 PASS.
- **X:** every REQ traces to an S-id / principle / article / forward-inherited primitive (PIO-1, DOC-1,
  HIS-1, Phase-5/6 entities, Phase-10 `data/cloud/`) in `traceability.md` (26 REQ).
- **XI:** the `BlobBackend` port is the extension seam (a new backend = a new implementation, no caller
  change); a new asset `kind` / dependency edge type / localised UI layers on without weakening any
  article.

## 11. Layering / cycle verification

At plan time on the shipped tree (baseline 2026-07-04):
- `python scripts/check_layering.py --root pixelart_creator` → exit **0** (clean, **158 modules**).
- `python scripts/check_cycles.py --root pixelart_creator` → exit **0** (no cycles, **159 modules**).

The planned Phase-11 edges (§4) are acyclic by construction and land entirely inside the existing three
layers — **no `check_layering`/`check_cycles` rule edit is required** (contrast Phase 10's `sync_backend`
rule). AGT-03 re-runs both invocations as each slice lands (per-slice gate task). See `analyze-report.md`
for the C1 verdict.

## 12. Decisions log

| # | Decision | Branch / choice | Rationale |
| --- | --- | --- | --- |
| PL11-D1 | Ungrounded stack/API choice? | **B (no)** | Stack fixed (S8); catalog/CAS/graph/break/reuse all grounded by the landed Researcher report. No RESEARCH REQUEST. |
| PL11-D2 | Qt in `logic/`/`data/` or magic number outside `constants.py`? | **B (no)** | All UI in `ui/`; 7 numerics → `constants.py` (distinct names); `AssetKind` intrinsic-local (ADR-0001). |
| PL11-D3 | Reversibility surface | **Tag add/remove is the one new undoable op → `ui/commands.py` wrapper over `logic/asset_tags` do/undo** | REQ-P11-LOGIC-002/UI-002 (HIS-1 reversible-op pattern); catalog/version/reuse/export are non-undoable library state. |
| PL11-D4 | "Reuse Phase-10 content-hash/CAS" | **Introduce `content_hash`+`asset_cas`; reuse Phase-10 SHAPE/pattern, not a pre-existing primitive** | No content-hash/CAS exists in Phase 10 (`version_history` keys by opaque id); honesty ruling for AGT-03 (ADR-0030 §Context). |
| PL11-D5 | New runtime dependency? | **B (no)** | Content hashing = stdlib `hashlib` (already used in `export_io`/`cloud/auth`); no AGT-09 manifest change. |
| PL11-D6 | Layering-rule update? | **B (no)** | Everything lands inside the existing three layers (`data/cloud/` already governed); no `sync_backend`-style rule; baseline exit 0 unchanged. |
| PL11-D7 | Storage substrate (CL-3) | **Local-first default; optional Phase-10-shared backing behind one `BlobBackend` port** | Works fully offline; cloud is one backend impl, provider-agnostic above the port (ADR-0032). |
| PL11-D8 | Version substrate (CL-1) | **Append-only content-addressable revision DAG at asset granularity; NOT the CRDT** | Immutable snapshots + dedup; CRDT stays for live docs (ADR-0030 §6; Researcher §3.1 hybrid). |
| PL11-D9 | Reuse mechanism (CL-2) | **CAS + reference-not-copy `(AssetId→hash)`; export bundles referenced blobs** | Dedup + portability; the precise meaning of "without duplication" (ADR-0030 §4/§5). |
| PL11-D10 | Break semantics (CL-4) | **Passive content-hash-gated reference-validation pass; pull-based; recomputed on change** | Missing id / hash mismatch flagged on query + view; push is FUTURE (ADR-0031 §3). |
| PL11-D11 | Article VI (DEP-3) | **All domain ops off-loop; NO REQUIRED AGT-10 directive; graph render = conditional UI flag** | No per-frame re-entry (unlike Phase-10 Slice C); render flag only if the view proves heavy (spec §8 DEP-3). |
