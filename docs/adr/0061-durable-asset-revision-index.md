# ADR-0061 — The asset revision history persists as a second index+sidecar pair, on the catalog's own convention, not a second serialiser

| Field | Value |
| --- | --- |
| Status | **Accepted** (landed on branch `feat-asset-ingress`, not yet merged) |
| Date | Decided 2026-08-22 (`phase-11-asset-ingress` plan §3.13 — ruling P11-R11, mid-execution finding); recorded 2026-08-22 |
| Author | Architecture |
| Feature | `phase-11-asset-ingress` (job `20260821-reachability-remediation`) — `REQ-P11-DATA-008`, `SC-P11-INGRESS-E2E-1`, `REQ-P11-UI-020` |
| Grounded by | `spec.md` §6 `SC-P11-INGRESS-E2E-1` (the frozen restart clause naming revisions explicitly); `REQ-P11-DATA-008`'s 2026-08-21 amendment (an index that is never saved or loaded fails the requirement even when the bytes are durable); `REQ-P11-UI-020` / `SC-P11-UI-018-1` (a real, ordered, non-empty history in the browser); Article VII (untrusted-input defence, path containment) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0059 (Ruling P11-R1 — the atomic write order this decision restates and, in one place, tightens), ADR-0051 (the one library root this decision opens no second location under), ADR-0030 §6 (the shipped catalog index+sidecar convention this decision re-uses rather than re-invents) |

## Context

`AssetRevisionStore` shipped with its history keyed in `self._histories`, a plain
`Dict[str, AssetVersionHistory]` — durable for the session, gone on restart. The CAS blobs the
histories point to were already durable, written through the same injected root as every other
asset byte, so the failure was narrow and specific: the *index that names them* had no save and no
load. `REQ-P11-DATA-008` had already decided this exact class of question once, for the catalog:
its 2026-08-21 amendment states that a restart able to fetch bytes by hash but listing nothing
because the library's own index was never saved or loaded fails the requirement, and that a row
marked satisfied on the byte half alone would be a false record. This is the second
index of exactly that shape.

The obligation is not inferred from that precedent alone. `spec.md` §6's frozen acceptance scenario
`SC-P11-INGRESS-E2E-1` ends: *"When the application is closed and started again / Then the asset
**and its revisions** are still present and hash-verified / And the number of stored blobs has not
grown."* The clause names revisions explicitly and separately from the asset, and `REQ-P11-UI-020`
together with `SC-P11-UI-018-1` require the version browser to show *"a real, ordered history"* with
*"at least one revision for the asset"* — true only inside the session that wrote it, while the
history lived in memory only.

**Narrowing the acceptance clause instead of building the durability was considered and rejected.**
That would be the honest remedy when a test has out-run its spec; here the test is *downstream* of
an approved, frozen scenario, so weakening it is an amendment to `SC-P11-INGRESS-E2E-1` that nothing
in the frozen inputs asks for, and it would make the clause redundant with the catalog-restart
scenario that already exists. The scenario stands; the store gets durable.

## Decision

### 1. Where it serialises — the same library root, two new names, no second location

The revision index and its sidecars sit beside the catalog's own index and sidecars, under the one
library root `ui/main_window._asset_root()` already resolves and injects (ADR-0051):

```
<root>/catalog.json               <- shipped: the catalog index (the commit point, ADR-0059 §2)
<root>/assets/<asset_id>.json     <- shipped: one catalog sidecar per entry
<root>/revisions.json             <- NEW: the revision index (this decision's commit point)
<root>/revisions/<asset_id>.json  <- NEW: one revision-history sidecar per asset
```

The new module, `data/asset_revision_io.py`, names the two files through its own exported
constants rather than a caller pasting a literal string: `INDEX_FILENAME = "revisions.json"`,
`REVISIONS_DIRNAME = "revisions"`, a format marker `FORMAT_NAME = "pixrevisions"`, and
`REVISIONS_SCHEMA_VERSION = "1"` with a `SUPPORTED_SCHEMA_VERSIONS` tuple built from it. Naming the
constants rather than the values is deliberate: the values can move without this record going
stale, the contract — an index plus per-id sidecars, versioned and format-marked — cannot.

`REQ-P11-DATA-008`'s "exactly one such location per machine" clause is preserved by construction:
this decision adds two names inside the one location ADR-0051 already resolves, not a second
location. `logic/asset_version.py` (`AssetRevision`, `AssetVersionHistory`) stays pure and is
imported by the new `data/` module; it imports nothing back. No `logic -> data` edge, no
`data -> ui` edge.

### 2. The atomic order — stated as ruling P11-R1's, stricter in exactly one place

The invariant is P11-R1's own words (ADR-0059 §2), extended by one line:

> **Guaranteed absolutely — no recorded revision without its bytes.** A revision enters the durable
> index only after that revision's bytes are durably stored and content-hash-addressable.
> **Not guaranteed, deliberately — the converse.** Bytes may exist that no catalog entry *and no
> revision record* names.

`AssetRevisionStore.record` (`pixelart_creator/data/asset_revision_store.py`) follows the shipped
CAS validate → dedup-observe → write-blob sequence unchanged (steps 1–3 are exactly P11-R1's), then:

4. **Writes this asset's revision sidecar, then commits the revision index last.**
   `<root>/revisions/<asset_id>.json` is written first; `<root>/revisions.json` is written second and
   is the commit point — `load_histories` takes its `asset_ids` list only from the index, so until
   the index lands, the new sidecar is invisible and the previous index is what loads. This is
   P11-R1 step 4's construction, applied to the second index.
5. **Adopts the new value in memory only after the durable commit** — and this is the one place
   the order is *stricter* than the catalog's. `AssetVersionHistory.append` is pure and returns a
   new value, so `record` computes `updated = history.append(revision)`, persists `updated` (step
   4), and only then assigns `self._histories[asset_id] = updated`. **This is the interesting
   contrast, not a restatement of P11-R1**: the shipped catalog path mutates `self._catalog` and
   only afterward calls `_persist()` (`ui/asset_library_actions.py:396`), so a catalog save that
   fails leaves memory ahead of disk. The revision store cannot do that, because
   `AssetVersionHistory` is immutable — there is no `self._histories[asset_id]` to mutate ahead of
   the write in the first place. The stricter order costs nothing here; it is available only
   because the value being committed is immutable, which the catalog's own mutable dict is not.
6. **An unbound store behaves exactly as it did before this decision.** With no root bound (`_root
   is None`), steps 4–5 collapse to the shipped in-memory assignment — every existing caller, test
   double and fixture that constructs `AssetRevisionStore(cas)` without binding a root is
   unaffected. That is the regression contract, and it is why the shipped 18-test suite over this
   module passes unmodified.

**The tolerated unreferenced blob is carried in unchanged.** Ruling P11-R1 (ADR-0059 §2) stands:
no removal capability is added by this decision either. On any failure at or after the blob write,
nothing is removed — the blob may remain unreferenced (bounded, invisible, reclaimed for free on
retry because `put` dedups), and a sidecar written but not indexed is superseded on the next
successful `record`, never read.

**"Merely opening the application creates nothing on disk" survives.** Binding a root loads or
reads empty and performs no `mkdir`; `<root>/revisions/` is created on demand only inside a genuine
`write_history` call, reachable only from `record`. An absent `<root>/revisions.json` loads as an
empty history map, not an error — the same disposition `Asset_Library_Session.bind_root` already
takes for an absent `catalog.json`.

### 3. The format — the shipped catalog convention, re-used element for element

`data/asset_catalog_io.py` already establishes, and `REQ-P11-DATA-001` already grounds, the
convention this decision adopts rather than re-invents: a JSON index naming ids, plus one JSON
sidecar per id, parsed with `json` only, count-capped, hash-validated, path-traversal-defended.
`data/asset_revision_io.py` reuses it directly — its own index caps `asset_ids` at
`MAX_CATALOG_ASSETS` (the same ceiling: at most one history per catalog entry), and per-history
bounds (`MAX_ASSET_VERSIONS`, the DAG-acyclicity rule) are enforced by the `logic/` model's own
`__post_init__`, so no second cap is invented anywhere in this decision.

**Three formats were rejected**, as the feature plan (§3.13(c)) records:

- **One whole-store file.** Rejected: `record` would rewrite every asset's history on every
  registration — O(catalog) I/O per ingress against an O(1) sidecar write — and it abandons the
  index-is-the-commit-point shape ADR-0059 §2 depends on.
- **Extending the catalog sidecar** with a `revisions` array. Rejected: it changes a shipped wire
  format that already round-trips and is tested, it couples a revision append to a catalog write
  through one file, and it would bump `CATALOG_SCHEMA_VERSION` — a compatibility event no
  requirement asks for.
- **A binary or compressed form.** Rejected: the payload is small, bounded metadata; the
  `.pixproj` zlib+base64 path exists for pixel buffers, and there are none here.

**One duplication is refused, and this is where.** The path-traversal defence —
`data/asset_catalog_io.py`'s `_safe_asset_id` and `_resolve_within` — is an Article VII security
control, and a security control that exists twice drifts. `data/asset_revision_io.py` therefore
imports the definition rather than copying it, which required promoting the two helpers to public
names in `data/asset_catalog_io.py`: `safe_asset_id` (was `_safe_asset_id`) and `resolve_within`
(was `_resolve_within`), with the underscore names kept as aliases so not one existing call site
moves. `tests/data/test_asset_catalog_io.py` passing unmodified is the regression contract for that
promotion, exactly as the feature plan records it.

**The extension point deliberately not built.** A dedicated `data/asset_library_paths.py` holding
the shared containment rules for every index under the root is the right shape *if a third index
appears* — the plan already names one candidate, a mark-and-sweep back-index over catalog entries,
recorded revisions and every open project's reference set. It is not built now: two callers do not
justify a shared module, the extraction stays cheap and reversible later, and building it today
would be buying room for work that does not exist.

### 4. The load-at-bind seam — the window, and why the window rather than the session

`ui/main_window.py`, immediately after constructing `AssetRevisionStore` and before
`bind_revision_store` and `Asset_Version_Browser.set_store`, calls:

```python
self._asset_revision_store.bind_root(self._asset_root())
```

`AssetRevisionStore.bind_root(root)` adopts whatever persists under an already-resolved root,
reading an absent index as empty, and every later `record` persists straight back to it — the same
idiom, same verb, same disposition as the shipped `Asset_Library_Session.bind_root`. The window is
the seam because the window is where the root is resolved (ADR-0051); the store itself resolves no
root of its own.

**This is the window, not the session, and it matters for exactly the reason a smaller seam would
seem plausible.** `Asset_Library_Session.bind_revision_store` takes the store *as given* and its
own docstring states it neither constructs nor resolves a root; making it bind the root as well
would give it a second, order-dependent responsibility (`bind_root` before `bind_revision_store`)
that contradicts its stated contract. It is not the constructor either — `AssetRevisionStore(cas)`
is built by tests and fixtures that must stay root-free, and a defaulted root parameter would make
durability the silent default in every one of them. And it is not "at startup" in the abstract:
there is exactly one line where the root is already resolved and the store already exists, and
naming that line is the whole ruling.

**Why the window is the window and not the session, restated as an honesty bound.** The seam binds
once, at construction, inside `Main_Window.__init__` — not per document, not per tab. A history
loaded at bind time is already populated by the time `Asset_Version_Browser.set_store` hands the
store over, because the browser reads `store.history(asset_id)` live; no change was needed there,
and none was made.

## What this decision does NOT make true

**An ADR claiming this slice made revision history crash-proof would be false, and this record does
not make that claim.** The index write is a single `Path.write_text`, exactly as ADR-0059 §2
already records for the catalog index — not a temp-file-plus-rename. A crash during that one write
can truncate `revisions.json`. What this decision actually guarantees is narrower and stated
precisely: a *clean* restart reloads every revision that was durably committed before the process
ended, and a revision is never visible in the index without its bytes already being
content-hash-addressable in the CAS. It does not guarantee survival of a write interrupted
mid-flight, and it does not add any transactional mechanism the catalog itself lacks.

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| One whole-store file for every asset's history | O(catalog) I/O per registration; abandons the index-is-the-commit-point shape |
| Extend the shipped catalog sidecar with a `revisions` array | Changes a tested wire format in place, couples two write paths through one file, forces an unneeded schema-version bump |
| Binary or compressed sidecar format | The payload is small bounded metadata; no pixel buffers are involved |
| Bind the root from `Asset_Library_Session.bind_revision_store` | Contradicts that method's own stated contract (it neither constructs nor resolves a root) and adds an order dependency |
| Default a root parameter on the `AssetRevisionStore` constructor | Makes durability the silent default for every root-free test and fixture in the tree |
| Copy the path-traversal helpers into the new module instead of promoting them | An Article VII security control that exists twice is a control that drifts |
| Build `data/asset_library_paths.py` now | Two callers do not justify a shared module; the extraction stays cheap if and when a third index appears |

## Consequences

**Accepted costs.** The library root now has two commit points (`catalog.json`, `revisions.json`)
instead of one, and a reader who wants "the durability story" must read both this record and
ADR-0059 §2. The index write remains a single `write_text`, so the truncation risk ADR-0059 already
accepted for the catalog now exists twice, in two files, for the same reason. `data/asset_catalog_io.py`
now exports two names it did not export before (`safe_asset_id`, `resolve_within`), widening its
public surface for a second caller inside `data/`.

**What this enables.** `REQ-P11-DATA-008` is now answered the same way for both indexes the
library maintains, closing the second half of `SC-P11-INGRESS-E2E-1`'s restart clause and making
`REQ-P11-UI-020`'s "real, ordered history" true across a restart rather than only within a session.
The immutable-value commit order (§2.5) is available as a pattern for any future durable index built
over an immutable model — cheaper than the catalog's mutate-then-persist shape, not because the
catalog was built carelessly, but because its underlying value is not immutable and this one is.

**What it constrains.** No future change may remove the sidecar-then-index ordering in `record`
without reopening this decision. No future change may add a removal API to the revision store or
its blobs without reopening ADR-0059 §2's rejected alternative (a) and its reasoning — this decision
adds none either. `data/asset_revision_io.py`'s two promoted helpers are the one definition of the
path-containment control for both indexes; a future third index must import them, not copy them.

**Ruling P11-R12 (§3.14 of the feature plan), noted and deliberately not given its own ADR.** That
ruling holds one per-tab session field (`_DocTab.registered_asset_id`) and returns a value that was
already computed; it buys no durable invariant and nothing on disk changes. Its whole effect is that
re-registering an already-registered document is now reachable, because the window remembers what
the tab was registered as. That sentence is its complete record here.

## Compliance

Quoted from the `feat-asset-ingress` worktree, this pass (2026-08-22), Python **3.13.13** (CI pins
3.12):

```
$ python scripts/check_layering.py --json
check_layering: clean (214 modules; 2 root module(s), 0 exempt top-level package(s), 0 unregistered)
exit 0
$ python scripts/check_cycles.py --json
{"cycles": [], "edges": 814, "modules": 216}
exit 0
```

The feature plan's own ruling (§3.13) predicted six new edges over one new module before the
remaining tasks landed: `data/asset_revision_io -> logic/asset_version`, `-> logic/content_hash`, `-> logic/constants`
(three `data -> logic`, permitted); `-> data/project_io`, `-> data/asset_catalog_io`, and
`data/asset_revision_store -> data/asset_revision_io` (three `data -> data`, permitted). Measured
this pass: **+5 edges from the serialiser and +1 from the store — six exactly**, matching the
prediction with no drift. Zero `logic -> data` edges, zero `ui -> data/asset_revision_io` edges —
the window touches only the store it already imports.

Behavioural coverage: `tests/data/` — 1252 passed, 2 skipped; `tests/logic/` — 2519 passed. The
shipped `tests/data/test_asset_catalog_io.py` (38 tests) and `tests/data/test_asset_revision_store.py`
(18 tests) both pass **unmodified**, which is the regression contract for the helper promotion (§3)
and for the unbound-store disposition (§2.6) respectively. This ADR does not itself re-run those
suites for this record; the counts above are quoted from the pass that produced this decision.

**What has no detector, stated rather than implied.** No script proves that a future edit reorders
`write_history` after `write_index` inside `record`, adds a removal API to the revision store, or
copies the path-containment helpers instead of importing them. Those are review invariants against
this ADR's Consequences section, not a gate that runs.

## What this record does not verify

- **The index write's atomicity is not proven, only bounded.** As stated above, `write_text` is not
  crash-safe against a truncated write; this record does not claim otherwise and no task in this
  slice builds a temp-file-plus-rename path for either index.
- **`bind_root` propagating a malformed durable index out of `Main_Window.__init__` unguarded** is
  not fixed here — it is the same disposition the shipped `Asset_Library_Session.bind_root` already
  has for a corrupt `catalog.json`, carried forward, not introduced.
- **`ui/main_window.py` is not read in full** for this record; only the construction/bind sequence
  around the injection point was read.
- **`AssetVersionHistory`'s behaviour under a hostile sidecar was reasoned from its `__post_init__`
  and from `data/asset_revision_io.py`'s own defensive parsing, not exercised against a crafted
  adversarial file as part of authoring this record.**
- **This record does not itself re-run `pytest`, `check_layering.py` or `check_cycles.py`** beyond
  the layering/cycle re-measurement quoted in Compliance; the 1252/2519 test counts are quoted from
  the pass that produced this decision, not re-verified by the documentation in this session.
