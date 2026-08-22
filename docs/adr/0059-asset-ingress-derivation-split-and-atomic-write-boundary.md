# ADR-0059 — Asset ingress: the determinism split, the atomic write boundary, the derived-edge write path, the byte-store composition root, and the two identity keys

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-08-21 (`phase-11-asset-ingress` plan §3.2, §3.3, §3.5, §3.6, §3.10 — rulings P11-R1, P11-R3, P11-R4, P11-R8); recorded 2026-08-22 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-11-asset-ingress` (job `20260821-reachability-remediation`) — `REQ-P11-LOGIC-009`/`-010`, `REQ-P11-DATA-006`/`-007`/`-008`/`-009` |
| Grounded by | Article I §3 (`logic` may not import `data`); `REQ-P11-DATA-007` ("no second serialiser"); `REQ-P11-DATA-009` (the atomic write); `REQ-P11-LOGIC-010` (derived edges); `REQ-P11-DATA-008`'s OQ-A2-2 clause (shared/cloud-optional backing, wire-only, no new REQ id); the 2026-08-16 placement ruling (`ui/` names no backend) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0051 (the durable store root this factory composes over — carried in, not re-decided here), ADR-0058 (the reference identity this ADR's edge derivation must not be confused with), ADR-0056 (cited only, not extended) |

## Context

`phase-11-asset-ingress` needed four related decisions that a single "how does registration work"
question does not separate cleanly: where the canonical bytes, hash, descriptor and derived edges of
a registered asset each come from; what "atomic" means for a write that touches a content-addressable
store and a catalog index in sequence; how a session-owned derivation reaches a view that already
renders it; and where the optional shared/cloud-backed byte store gets composed. A fifth question
surfaced mid-execution: what "the same asset" means when matching a tileset or an animation back to
the sprite it was built from. All five are decided together here because each constrains the others —
the determinism split decides where `logic/` may compute; the atomic order decides when a derived
edge is even reachable; the identity-key split decides what the edge derivation actually matches on.

**The determinism split.** `REQ-P11-LOGIC-009` requires "canonical bytes, content hash and descriptor"
to be a pure, Qt-free, deterministic computation with no second serialiser. The canonical serialiser
already lives in `data/`, and `logic/` may not import `data/` (Article I §3) — so one module cannot
do all three without either becoming a second serialiser or crossing the layer boundary.

**The atomic write order — first written 2026-08-17, and it could not be implemented.** The original
order said to note whether a blob already existed via `ContentAddressableStore.has_blob` and to
remove the blob if the ingress had created it and a later step failed. Reading the actual modules
(not their docstrings) found that the CAS's method is named `has`, not `has_blob` — `has_blob` is a
method on the three-method `BlobBackend` port (`put_blob`/`get_blob`/`has_blob`) the CAS composes
over, a different class entirely — and that **no removal capability exists anywhere in the CAS
stack**: a repository-wide search for `delete`/`remove`/`discard`/`unlink`/`prune`/`evict` under
`data/` finds only the project-level `CloudPort.delete(project_id)` and the two token stores, nothing
on the blob path. The order as written named a method that belonged to the wrong class and a
capability that did not exist.

**The derived-edge write path.** `ui/dependency_graph_view.py`'s `show_edges` is the only production
writer of the view's own `set_graph`, and it had zero production callers — the cycle-rejection branch
and the passive cycle label it drives were tested but structurally unreachable, exactly the defect
class (DEV-30) this remediation job exists to close.

**The byte-store composition root.** `SharedBlobBackend` ships, implements the identical three-method
`BlobBackend` port `LocalBlobBackend` does, and is tested — with zero production importers.
`data/asset_cas.py`'s `default_content_store` had exactly one hard-coded backend choice in its whole
path: `return ContentAddressableStore(LocalBlobBackend(resolved_root))`.

**The identity-key question — found mid-execution, and worse than reported.** T8's `edges_for` was
built to match on whole-project canonical bytes (`canonical_json_bytes(project_io.serialize(document))`).
Reading the production shapes end to end (`register` → `candidates_of` → `canonical_bytes` →
`edges_for`) found that the only two document shapes a user can actually produce — `Document()`'s
seeded layer named `"Background"` and `Document.from_buffer`'s `name=Path(path).stem` from an
image import — never match `candidates_of`'s own reconstruction, which uses the factory default name
`"Imported"`. **Edge derivation was unreachable in the running application for all three relationships
it is supposed to derive**, not merely fragile for some future document shape — a user registering a
sprite and then a tileset built from it would see a dependency graph saying the tileset depends on
nothing, which is the exact user-visible defect (CF-34) the requirement exists to close.

## Decision

### 1. The determinism split (`REQ-P11-LOGIC-009`) — no second serialiser

**`data/asset_ingress.py` produces the canonical bytes with the shipped serialiser; `logic/asset_extract.py`
turns those bytes plus the user's chosen name/kind/tags into the descriptor and the hash.** The
observable behaviour is unchanged end to end — same source produces byte-identical bytes and the
identical hash, no dependence on wall-clock, randomness, locale or filesystem state — and no second
serialiser is introduced anywhere: `logic/` never encodes a document, it only hashes bytes `data/`
already produced. `check_layering` is what proves no Qt symbol and no `data` import reached
`logic/asset_extract.py`; this split is what makes that proof possible rather than aspirational.
`REQ-P11-LOGIC-009` was subsequently reworded (`spec.md:551-557`) to state explicitly that the
obligation binds the computation, not a single module — the split above is what that clause blesses.

### 2. The atomic write order — RULING P11-R1: no removal capability is added; an unreferenced blob is tolerated

**The invariant is restated to the one the substrate can actually keep:**

> **Guaranteed absolutely — no catalog entry without its bytes.** The catalog gains an entry only
> after that entry's bytes are durably stored and content-hash-addressable.
> **Not guaranteed, deliberately — the converse.** Bytes may exist that no catalog entry names.

The order, as landed and read directly from `data/asset_ingress.py`'s `register`:

```
pixelart_creator/data/asset_ingress.py:324    # --- Step 1: validate everything first, purely, in memory. ---
                                    :325           blob = canonical_bytes(document)
                                    :328-341        descriptor_for(...) / catalog.add(descriptor)
pixelart_creator/data/asset_ingress.py:348    # --- Step 2: dedup observation, before anything is written. ---
                                    :349           already_present = cas.has(descriptor.content_hash)
pixelart_creator/data/asset_ingress.py:351    # --- Step 3: write the blob (dedup no-op if already_present). ---
                                    :353           cas.put(blob)
pixelart_creator/data/asset_ingress.py:357    # --- Step 4: commit the catalog last — the index write is the commit. ---
                                    :359           save_catalog(new_catalog, root_path)
```

1. **Validate everything first** — schema, the named caps, the recorded hash against the actual
   bytes, and every path resolved and confirmed inside the library root. A rejection at this stage
   has written nothing.
2. **Observe `ContentAddressableStore.has(content_hash)` before writing** — the correct method name.
   **Its purpose is not rollback; it is the dedup observation** that lets the ingress report "this
   content is already in the library" and lets the same registration retried reclaim any orphaned
   blob for free (`put` dedups). It costs one lookup and no write.
3. **Write the blob** — `cas.put(blob)`, itself a dedup no-op on an existing hash.
4. **Commit the catalog last.** `save_catalog` writes each sidecar and then the index; `load_catalog`
   takes its entry list only from that index. **The index write is the commit point** — until it
   lands, the new entry is invisible and the previous catalog is what loads.
5. **On any failure at or after step 3, nothing is removed.** The blob may remain unreferenced, which
   is accepted and bounded: it is invisible to every surface (the index is the only enumerator), it
   costs at most one blob's worth of bytes, and the same registration retried reclaims it for free
   because `put` dedups.

**Why removal was rejected — three candidates, each on layering and reversibility grounds:**

- **(a) Widen the `BlobBackend` ABC with a removal method.** Rejected: it changes a published port
  contract every implementer must satisfy — `LocalBlobBackend`, `SharedBlobBackend`, the cloud path
  behind it, and every test double — to serve one caller's failure path. It is also unsafe by
  construction on a content-addressed, deduping store: a blob is shared by every catalog entry, every
  recorded revision and every project reference that hashes to it, and safe deletion needs a
  reference count that deliberately does not exist. A widened ABC is hard to withdraw; tolerating an
  orphan is a position that can be reversed at any time by adding a sweep.
- **(b) Re-order so the blob write is last.** Rejected as the *worse* failure: the hash is pure, so
  the catalog could commit first, and a subsequent failed blob write would leave a catalog entry
  whose bytes cannot be fetched — a visible, user-facing broken entry, worse than an invisible orphan.
- **(c) Stage the blob and commit by rename.** Rejected: it needs a stage/promote pair on the same
  ABC (the same port-contract widening as (a), with two methods instead of one), and it still does
  not close the window — catalog-committed-then-promote-failed is case (b) again.

**`ContentAddressableStore.has`, not `has_blob`, and no removal API exists on the day this ADR is
written** — `has_blob` names a `BlobBackend` method, a different class; the CAS's own three methods
are `put`/`get`/`has` (`data/asset_cas.py:68`, `:92`, `:125`, re-read in the worktree 2026-08-22 —
the plan's own citation of these at `:49/66/90/123` had already drifted by this pass). An ADR
describing a call to `has_blob` on the CAS, or to any removal API, would be false.

**A future capability, named rather than smuggled in.** Reclaiming an orphaned blob's space is a
mark-and-sweep over catalog entries, recorded revisions and every open project's reference set, run
deliberately and never per-ingress. That is where a reference count belongs. No task in this slice
builds it, and the slice does not create the pressure for it — an orphan only appears on a failed
write.

### 3. How derived edges reach the graph — RULING P11-R3: through `show_edges`, by signal, carrying the accumulated set

**The derived edges reach the session only through `Dependency_Graph_View.show_edges`, and they
travel by signal — the view is the write path, not `Asset_Library_Session`.**

- `Asset_Library_Session` (`ui/asset_library_actions.py`) declares `edgesDerived = Signal(object)` and
  emits it after a successful registration. It never calls `set_graph` and never imports the view:

  ```
  pixelart_creator/ui/asset_library_actions.py:224   edgesDerived = Signal(object)
  pixelart_creator/ui/asset_library_actions.py:957   content = candidate_keys(document, descriptor.kind)
  pixelart_creator/ui/asset_library_actions.py:959   self.edgesDerived.emit(tuple(self.graph().edges) + derived)
  ```
- `ui/main_window.py` connects the session's signal to the view's method:

  ```
  pixelart_creator/ui/main_window.py:861   self._asset_session.edgesDerived.connect(self._dependency_graph_view.show_edges)
  ```
- **The payload is the accumulated edge set, not only the newly derived edges.** `show_edges` replaces
  the graph outright, so a registration must emit the prior graph's edges plus what it just derived,
  or every registration would erase the edges derived before it.
- **A cycle does not roll the registration back.** If the accumulated set is cyclic, `show_edges` keeps
  the last good graph and surfaces the message passively — a label, not an exception. The catalog
  entry stands; the edges are reported, not applied. **Edge derivation is a post-commit presentation
  step, deliberately outside the atomic order in Decision 2** — the ingress has already committed by
  the time any edge is derived, so a cyclic derivation can never unwind a successful write.

**Why this inversion — a `ui/` view as the write path for library-derived state — is accepted rather
than moved into the session.** The alternative would edit a shipped, tested view/session pair to
relocate cycle handling that is already correct where it is, and would still leave the cycle surface
unreached. The cost is one signal hop; the benefit is that the shipped cycle-rejection behaviour
becomes executed code instead of a tested-but-unreachable branch — which a direct `session.set_graph(graph)`
call could not achieve, because `DependencyGraph` itself rejects a cyclic edge set at construction, so
a caller building the graph and calling `set_graph` directly would surface the rejection as an
exception in the ingress path instead of the passive report the acceptance requires.

### 4. Where the backend choice lives — RULING P11-R4: `default_content_store` is the composition root, and the composition is unconditional

`data/asset_cas.default_content_store` is the application's **composition root** for the byte store.
It takes the provider-agnostic `CloudPort` as an optional keyword and composes the shared backend
**unconditionally** — not behind an `if port is not None:` branch:

```
pixelart_creator/data/asset_cas.py:135-137
    def default_content_store(
        root: Optional[Path] = None, *, port: Optional[CloudPort] = None
    ) -> ContentAddressableStore:
pixelart_creator/data/asset_cas.py:185-188
        resolved_root = root if root is not None else default_asset_root()
        return ContentAddressableStore(
            SharedBlobBackend(port, local=LocalBlobBackend(resolved_root))
        )
```

- **`ui/` still names no backend.** The 2026-08-16 placement ruling forbids the presentation layer
  naming one, which forces this decision into `data/` and makes it a one-factory edit rather than a
  UI edit. `ui/main_window.py`'s call site — `default_content_store(self._asset_root())` — is
  unchanged, because `port` is keyword-optional.
- **Unconditional, not a branch, and this is the load-bearing choice.** A `port`-gated branch would
  leave the shared composition unexercised by every existing caller and every existing test until a
  provider is wired in a later slice — reproducing, one level deeper, the exact seam-with-no-caller
  condition this remediation job exists to remove. Composed unconditionally, `SharedBlobBackend`'s
  three methods are on the live path from the first run, and the only remaining move for a later
  slice is to pass a connected port.
- **With `port=None`, the store is behaviourally today's local-only store.** `put_blob` writes the
  local backend first and unconditionally, and touches the shared backing only while the port is
  connected; `get_blob` and `has_blob` are the same shape — a local hit short-circuits. Key validation
  is identical in both backends. **The one measured difference:** on a miss, `LocalBlobBackend.get_blob`
  raises `AssetStorageError` with an OS-error suffix, `SharedBlobBackend.get_blob` raises the same
  type with the same message stem but no suffix — no test in the tree asserts that message, so nothing
  breaks; it is recorded so a future test written against the local backend's exact wording is not
  written against this store's.
- **The stated limit.** This makes `SharedBlobBackend` production-live — its three methods are
  exercised from the first run — **not** cloud backing user-available. No caller passes a connected
  port until a later slice wires the provider; `spec.md`'s exclusion of the chooser, the indicator,
  the connect gesture and sync/progress reporting stands untouched. An ADR that reads as "cloud
  backing shipped in this slice" would be false.

**Rejected alternatives:**

- **(a) Let `ui/` pick the factory** — a shared factory when connected, the default factory when not.
  Rejected: it names no backend *class*, but it makes the presentation layer choose the substrate,
  which is the same decision under a different name.
- **(b) A new `data/asset_store_factory.py` composition-root module.** Rejected: the composition root
  already exists and is already imported by name; moving it buys a tidier home and costs dragging this
  edit into the same `ui/main_window.py` chain three other tasks were already queued against.
- **(c) Import `SharedBlobBackend` inside the function body**, to keep `asset_cas`'s module-level
  import surface unchanged. Rejected: a deferred import here would exist only to keep a coupling out
  of the layering scripts' view, and a coupling worth hiding from `check_cycles` is a coupling worth
  arguing about in the open.

**The coupling this buys, named.** `data/asset_cas` gains a module-scope edge to
`data/asset_shared_backend`, which imports `data/cloud/port`, which imports `data/project_io`; every
importer of the CAS now transitively pulls the cloud port and the project serialiser. This is legal
(`data -> data`, `data -> logic`) and cannot cycle, because `data/project_io` imports only `logic/`
modules.

### 5. Which bytes decide a reference — RULING P11-R8: `content_hash` and `reference_key` are two different keys, and neither is optional

**Two different questions were being asked with one key, and they are not the same question:**

| Question | Key | Where it is used |
|---|---|---|
| *Are these the same stored bytes?* | `content_hash` — `canonical_bytes(document)`, the CAS key | dedup, retrieval, change detection, revisions, the parent's reference model (`asset_id → content_hash`) |
| *Is this the same pictorial content?* | **`reference_key`** — content-only, presentation-free | edge derivation only (`REQ-P11-LOGIC-010`) |

`content_hash` keeps every meaning it already had and moves nowhere. `reference_key` is recorded
**beside** it on the descriptor at registration time, and edge derivation matches on it instead. A
layer's display name — part of a document's whole-project canonical bytes — legitimately changes
`content_hash`, which is exactly what made whole-project matching unreachable; it does not change
`reference_key`, so a renamed layer's derived edges survive the rename.

**Why the second key exists, stated rather than assumed.** `REQ-P11-LOGIC-010` states a pictorial
relation — "a tileset references its source-image sprite" — with no clause about document shape,
layer naming or serialisation. Matching on whole-project canonical bytes implemented a *stricter*
relation than the requirement states, and the strictness is what emptied the graph: measured against
the production shapes, `Document()`'s seeded layer (`"Background"`) and `Document.from_buffer`'s
imported-file layer (the file's stem) never equal `candidates_of`'s reconstruction default
(`"Imported"`), so no edge was ever derived for a document a user could actually produce.

**Two different names, and conflating them is the trap this ADR exists to prevent.** The spec's one
rename promise (`REQ-P11-UI-021`'s `SC-P11-UI-021-6`) is about a **library asset's display name** —
references resolve by `asset_id → content_hash` (ADR-0058), so renaming a library asset breaks no
project's reference. That promise is kept and untouched by everything in this decision. The name that
matters here is a **layer's** display name *inside* a document — part of that document's content, and
legitimately part of what changes `content_hash`. **Content-addressed identity is not weakened by
this decision.**

**Identity keys are recorded at registration and never recomputed at query time.** A registered
document's `reference_key` is computed once, by `register`, and stored on the descriptor:

```
pixelart_creator/data/asset_ingress.py:230   def _reference_key_for(document: Document, kind: AssetKind) -> str:
pixelart_creator/data/asset_ingress.py:328   reference_key = _reference_key_for(document, kind)
pixelart_creator/data/asset_ingress.py:338       reference_key=reference_key,   # into descriptor_for(...)
pixelart_creator/data/asset_ingress.py:452   reference_key = entry.get("reference_key", "")   # import path: additive, defaults to ""
```

**Only `SPRITE` and `TILESET` are ever reference *targets*.** `register` computes a `reference_key`
for those two kinds and records `""` for `ANIMATION`/`TILEMAP`/`PALETTE`, and for a `TILESET`
document holding zero or more than one tileset. Ambiguity degrades to "no edge," never to a wrong
edge — the same guard `edges_for` already carried before this ruling.

**Rejected: re-indexing at derivation time** — loading every catalog entry's blob, deserialising it
and computing its key on the fly instead of reading a stored field. Rejected on a measured bound:
`MAX_CATALOG_ASSETS = 65536`, so this would be up to 65,536 blob reads and project-format
deserialisations, on the GUI thread, per registration, to recompute a value that could have been
written once. **Identity keys are recorded, not recomputed.**

**The `reference_bytes` canonicalisation, amended after this ADR's rulings pass (DEV-38).** The
content-only key `reference_bytes(document, kind)` was originally implemented by compositing a
document's real layer stack through the shipped `composite_stack` — which honours each layer's real
opacity, blend mode and mask in addition to its pixels. That baked three presentation attributes into
a key this ruling requires to be presentation-free, so a document differing only in a single layer's
opacity produced a genuinely different `reference_key` — measured, opacity-only equality: `False` —
contradicting this ruling's own contract. The fix composites over a **presentation-normalised** copy
of the layer stack instead: every node's opacity pinned to the fully-opaque identity value, blend mode
pinned to the identity blend, and mask pinned to `None`, while `buffer`, `smart_source`, `children`
and `visible` — the pixel content and structural shape a content-only key must still be sensitive to
— pass through unchanged:

```
pixelart_creator/logic/asset_edges.py:381   def _reference_layers(nodes) -> List[LayerNode]:
    # presentation-normalised copy: opacity -> DEFAULT_LAYER_OPACITY, blend_mode -> NORMAL,
    # mask -> None; buffer / smart_source / children / visible carried over unchanged.
pixelart_creator/logic/asset_edges.py:434   def reference_bytes(document: Document, kind: AssetKind) -> bytes:
    # SPRITE: kind tag + geometry + colour mode + frame-0 layer stack composited via
    # composite_stack OVER _reference_layers(...) — NOT the real stack.
    # TILESET: unchanged by this fix — its canonicalisation reads PixelBuffer directly and
    # was never routed through composite_stack, so it never had the opacity/blend/mask leak.
```

**`reference_bytes` captures pictorial content only — names, opacity, blend mode and mask are
excluded by construction; geometry, colour mode, pixel content and structural shape (including
per-node `visible`) are not.** This is the current, landed semantics; an ADR describing the
pre-fix, opacity-sensitive shape would be false on the day it was written.

**Additive, and measured rather than hoped.** `data/asset_catalog_io._parse_descriptor` reads every
field through `payload.get(...)` and ignores unknown keys, so a sidecar written before this ruling
parses with `reference_key = ""`, and one written after it is readable by the current parser. An
imported artifact whose descriptors predate `reference_key` parses the same way (`entry.get("reference_key", "")`
at `data/asset_ingress.py:452`) — no crash, no adaptation, just the pre-ruling "no edge" behaviour.

**Rejected alternatives (selected; the full set is in plan §3.10):**

- **Document the whole-project-bytes shape as defined behaviour with a caller obligation** — rejected:
  the obligation would be "register every sprite from a `Document.from_buffer` call using the
  reconstruction's own default layer name," which no application path does and no user can be told to
  do; it would let a test construct a shape the app never constructs and call the requirement
  satisfied.
- **Carry the key in the descriptor's existing `metadata` bag** — rejected: `metadata` is
  caller/user-editable data; a computed identity a user can edit is not an identity.
- **Match on raw `PixelBuffer.data.tobytes()`** — rejected: raw buffer bytes carry no geometry, no
  colour mode and no framing, so two different documents can collide; `reference_bytes` is a named,
  deterministic canonicalisation, not a raw dump.
- **Normalise the registration path instead**, forcing every registered document through
  `Document.from_buffer` with a fixed name — rejected: it would silently rewrite the user's own
  document (their layer names) to force a hash match, and break on any multi-layer document.

## Alternatives considered (cross-cutting)

| Alternative | Why it was not chosen |
| --- | --- |
| Compute the descriptor/hash entirely in `data/`, alongside the serialiser | Rejected: the hash is domain identity, and AGT-04 must be able to test its determinism with no I/O — a `data/`-only computation could not be exercised Qt-free and I/O-free the way `REQ-P11-LOGIC-009` requires |
| Widen `BlobBackend` with a removal method (atomic order) | See Decision 2(a) — unsafe on a deduping store without a reference count, and hard to withdraw once shipped |
| Blob-write-last ordering (atomic order) | See Decision 2(b) — turns an invisible orphan into a visible, user-facing broken catalog entry |
| Call `session.set_graph(graph)` directly from ingress (edge write path) | Cannot pass the cycle-rejection acceptance: `DependencyGraph` rejects a cyclic edge set at construction, so the rejection would surface as an exception in the ingress path rather than the passive report the requirement asks for |
| `ui/` selects the store factory by connection state (backend composition) | Same substrate-choosing decision the placement ruling forbids, under a different name |
| Re-index reference keys at derivation time instead of recording them | Bounded at up to 65,536 blob reads and deserialisations per registration — identity keys are recorded, not recomputed |

## Consequences

**Accepted costs.** An unreferenced blob can persist indefinitely with no automatic reclamation; a
mark-and-sweep is named but not built. Edge derivation is a signal hop away from the commit rather
than inline with it, so a reader looking only at `register` will not find where edges come from.
`data/asset_cas` now transitively imports the cloud port and the project serialiser through
`SharedBlobBackend`, widening its import surface even though `port=None` behaves identically to
before. Every registered `SPRITE`/`TILESET` now carries two hashes with different invariants
(`content_hash` sensitive to presentation, `reference_key` deliberately blind to it), which is a
distinction a future maintainer must not collapse back into one field.

**What this enables.** The determinism split lets `REQ-P11-LOGIC-009` be tested Qt-free and I/O-free
while still guaranteeing no second serialiser exists. The atomic order makes "no catalog entry without
its bytes" an absolute guarantee instead of an aspiration that depended on a removal capability that
did not exist. The signal-based edge write path turns the shipped cycle-rejection UI from
tested-but-unreachable into executed code. The unconditional composition puts `SharedBlobBackend` on
the live path from the first run, so a later slice's only remaining move is to pass a connected port.
The `reference_key` split makes edge derivation reachable in the running application for the first
time, for all three relationships `REQ-P11-LOGIC-010` names.

**What it constrains.** No future task may add a removal method to `BlobBackend` without re-opening
Decision 2's rejected alternative (a) and its stated reasoning. No future caller may call
`Dependency_Graph_View.set_graph` directly from ingress code — edges must continue to travel by
`edgesDerived` → `show_edges`. `data/asset_cas.default_content_store`'s composition must stay
unconditional; a `port`-gated branch reintroduces the seam-with-no-caller defect this decision closes.
Edge derivation must continue to match on `reference_key`, never on `content_hash` or on raw pixel
bytes; and `reference_bytes` must stay presentation-free — any future canonicalisation change that
reads a layer's real opacity, blend mode or mask for this purpose reproduces the DEV-38 defect.

## Compliance

Quoted from the `feat-asset-ingress` worktree, this pass (2026-08-22):

```
$ python scripts/check_layering.py --root pixelart_creator --json
{ "scanned": 213, "unregistered": [], "violations": [] }
exit 0
$ python scripts/check_cycles.py --json
{ "cycles": [], "edges": 801, "modules": 215 }
exit 0
```

(Figures as last re-measured by T26's own pass at the P11-R7/P11-R8 amendment; this ADR does not
re-run the scripts and states so rather than re-asserting a number it did not itself produce.)

Zero violations and zero cycles mean no `logic -> data` edge exists — `logic/asset_extract.py` and
`logic/asset_edges.py` both receive bytes, never a path or a store — and the new edges this job's
passes introduce (`data/project_io -> logic/asset_references`, `ui/main_window -> logic/asset_references`,
`data/asset_cas -> data/asset_shared_backend`) are exactly the ones plan §3/§3.6 name, with no
additional edge appearing.

Behavioural coverage is AGT-04's determinism and edge-derivation suites and AGT-06's `SC-P11-UI-*`
pytest-qt suite, including the untrusted-input matrix for `REQ-P11-DATA-009` and the cycle-rejection
scenario for P11-R3; none of those suites was run to produce this record.

**What has no detector, stated rather than implied.** No script proves that a future edit reintroduces
a `has_blob`-shaped removal call on the CAS, calls `set_graph` directly from ingress code, adds a
`port`-gated branch to the factory, or reads a layer's real opacity/blend/mask back into
`reference_bytes`. Those are review invariants; the constraints in this ADR's Consequences section are
what a reviewer checks against, not a gate that runs.

## What this record does not verify

- **No test in this slice asserts that the factory composes the shared backend rather than the plain
  local backend** — the shipped factory test asserts behaviour (a `put` lands under the redirected
  root; `get` returns the bytes), which passes either way, so a silent revert to `LocalBlobBackend`
  would not be caught by it. This is a stated, accepted gap (plan §3.6), not a defect of this record.
- **The cloud branch of `SharedBlobBackend` remains unexercised** until a connected port is passed by
  a later slice; nothing in this job exercises it live.
- **Only `TILESET → SPRITE` was reproduced end to end for the `reference_key` fix**, in both
  directions of the result. The `ANIMATION` and `TILEMAP` relationships were not separately reproduced
  against a production shape; they use the same `_sprite_document` / `_tileset_document` wrappers, so
  the same conclusion follows by construction, but it is inferred here, not measured.
- **`data/asset_revision_store.py` and the full artifact-import path were not read in full** for this
  record. The one import-path behaviour cited above (`entry.get("reference_key", "")`) was read at its
  call site, not audited end to end.
- **This record does not re-run `pytest` or the coverage gate.** The gates quoted in Compliance are
  `check_layering`/`check_cycles` only.
