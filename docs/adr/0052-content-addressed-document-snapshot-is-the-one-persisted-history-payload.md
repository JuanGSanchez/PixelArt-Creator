# ADR-0052 — The content-addressed document snapshot is the one persisted history payload

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-08-17 (the `phase-9` / `phase-10` / `phase-6` planning batch); **recorded 2026-08-19** |
| Author | AGT-01 (Architecture) |
| Feature | Cross-slice: `phase-9-timelapse-replay`, `phase-10-branch-diff`, `phase-6-mode-toggle-undo` |
| Grounded by | `REQ-P9-DATA-004`, `REQ-P9-LOGIC-013`; `REQ-P10-UI-025`; the phase-9 plan §2.1 and the phase-10 plan §2.1 (the op-persistence ruling, stated once in both); Article I / S11 (layer purity) |
| Owed by | `phase-10-branch-diff` **T24** (owner AGT-08) — see "Why this record is late" |
| Relates to | ADR-0028 (the CRDT convergence model whose op union is *not* extended here), ADR-0030 (content-addressed asset catalog — a different store, the same primitive), ADR-0025 (`.pixproj` v5, the serializer this reuses) |

## Context

Three slices planned in one batch each needed to persist *history* — a sequence of past
document states — and the batch required **one** serialization decision across them
rather than three:

- `phase-9-timelapse-replay` persists a recorded session (`.pixtimelapse`);
- `phase-6-mode-toggle-undo` persists a checkpoint before a destructive colour-mode
  conversion;
- `phase-10-branch-diff` reads a *live* branch op-log and persists nothing.

The obvious answer — reuse the CRDT operation vocabulary that already exists for realtime
sync — is not available, and the reason is a measured expressive limit rather than a
preference. `logic/convergence.py`'s `Operation` union is
`MetadataOp | LayerAttrOp | LayerOrderOp | RasterOp` (`:228`): one metadata key, four
layer attributes (`LAYER_ATTRS`, `:74`), a top-level frame reorder, and a raster tile. It
**cannot express** layer add/remove, frame add/remove, canvas resize, colour-mode
conversion, masks, groups, tilesets, tilemaps, frame tags or palette edits. A timelapse
built on it would look complete and silently omit whole classes of edit — which is exactly
what `REQ-P9-LOGIC-013` forbids ("a replay of a session … is not n copies of one image").

The remaining constraint is that the product must not acquire a **third** history
vocabulary. It already has two — the `QUndoStack` / `logic/history.Command` pattern and the
CRDT op model — and `logic/macro.py::Op` is a fourth-in-waiting that covers only the
scripted-op catalogue. Serialising arbitrary `QUndoCommand` subclasses is not an option
either: Qt provides nothing for it (research Finding 5, a negative finding from the
complete class reference).

So the real question was never "ops or snapshots" in the abstract. It was: *what is the
persisted form, and what stays unified across the two forms so that the product does not
grow a second encoding, a second fingerprint, and a second drift surface?*

## Decision

**We will persist history as a content-addressed document snapshot — `project_io.serialize`'s
own output with every encoded blob hoisted into a shared `{sha256hex: blob}` table — and this
is the single persisted history payload in the product; the convergence `Operation` union
remains the in-memory, unpersisted branch/CRDT form.**

Concretely:

1. **Two forms, and the boundary between them is persistence.** Convergence ops are the
   branch/CRDT form and are never written to disk (`phase-10-branch-diff` keeps its op-log in
   memory, session-scoped, bounded by the shipped `_MAX_OPS_PER_UPDATE = 4096`). The
   content-addressed document snapshot is the persisted form. No slice creates a third.

2. **The snapshot is `project_io`'s output, not a second encoding.** `data/snapshot_store.py`
   calls the **public** `data/project_io.serialize` / `deserialize` — which already cover every
   persisted field, defensively and `eval`-free — and hoists the already-encoded blob strings
   they emit into the shared table. `data/project_io.py` is **not modified**: not one line.

3. **Deduplication is at buffer granularity, because that is the granularity the product has.**
   Consecutive edits typically change one layer's buffer; every other buffer's encoded string
   is byte-identical across snapshots, hashes to the same key, and is stored once. `PixelBuffer`
   is a flat NumPy array, not tiled, so a finer granularity would be invented rather than
   exploited.

4. **What is unified across both forms is the encoding primitive and the fingerprint**, both
   already shipped: `base64(zlib(raw))` at `PROJECT_ZLIB_LEVEL` (`data/project_io.py:81-83`)
   and `logic/content_hash.content_hash`.

5. **The fingerprint is load-bearing, not decoration.** The research brief's clearest
   cross-source finding is Vim's `'undofile'`: a persisted history is safe to trust only if it
   can verify that the state it applies to has not diverged, and must **discard** rather than
   misapply on mismatch (official `undo.txt`). Every snapshot carries its content hash; a
   mismatch is refused with the first offending frame named (`REQ-P9-UI-019`(e)) — never
   partially played.

6. **`BLOB_KEYS` is declared, not derived.** `data/snapshot_store.py:66` declares
   `frozenset({"data", "source"})`, enumerated from `project_io`'s serialisers
   (`_serialise_buffer` emits `{"mode", "data"}`; `_serialise_tileset` emits `"source"`;
   `_encode_u32`-encoded tilemap chunks are emitted under `"data"` too). It is deliberately
   **not** exhaustively verified against every serialiser body — a drift-guard test is what
   makes a future `project_io` addition at an unlisted key cheap to catch.

## Alternatives considered

| Alternative | Why it was not chosen |
| --- | --- |
| **An operation-payload journal on the CRDT `Operation` union** | A measured expressive limit, not a preference: the union covers one metadata key, four layer attributes, a frame reorder and a raster tile (`logic/convergence.py:228`, `:74`). Layer/frame add-remove, canvas resize, mode conversion, masks, groups, tilesets, tilemaps, tags and palette edits have no representation, so the payload would look complete and be silently lossy. |
| **A `logic/macro.py::Op`-style journal** | Covers only the scripted-op catalogue, not every undoable command. Generalising it means serialising every `QUndoCommand` subclass, for which Qt provides nothing (research Finding 5). |
| **Periodic snapshots with interpolation between them** | Breaks `REQ-P9-LOGIC-013`, which requires *each* recorded frame to be its own state. |
| **Extracting a shared codec into `data/snapshot_codec.py`** | Would touch an 802-line, 5-format-version module for zero gain, and would invert the natural `snapshot_store -> project_io` dependency into a **cycle** (`snapshot_codec -> project_io` for its error class, against `project_io -> snapshot_codec`). |
| **A bespoke checkpoint sidecar format for `phase-6-mode-toggle-undo`** | A second snapshot format for one concept, in the same batch — a second drift surface bought for nothing. That slice's plan §2 chose this form explicitly for that reason. |
| **Persisting `phase-10`'s branch op-log** | Forbidden by that slice's own out-of-scope list, and it would put a second persisted history form in the product in direct collision with this one. |
| **A whole-document copy per committed command** | O(document) per stroke — roughly 126 MB of copying at 8K. |

## Consequences

**Accepted costs.** A snapshot is a *whole document*, so the payload's floor is the size of
one serialised project even when one pixel changed; deduplication makes the *marginal*
snapshot cheap but never the first one. `BLOB_KEYS` is a declared list that a future
`project_io` serialiser can silently outgrow — the cost is a drift-guard test that must be
kept honest, not a structural guarantee. And a mismatched fingerprint means a recording is
**refused**, not repaired: the user loses the tail of a replay rather than getting a wrong
one, which is the trade this decision deliberately takes.

**What this enables.** Any future feature needing "the document as it was" reuses
`snapshot_of` / `document_of` and inherits full field coverage, `.pixproj`'s defensive
parsing, the compression settings and the fingerprint discipline for free. Three consumers
already do: `data/timelapse_io.py` (schema 2/3, via `BLOB_KEYS`), `ui/timelapse_controls.py`
(`snapshot_of`) and `ui/timelapse_playback.py` (`document_of`). `phase-6`'s checkpoint store
is specified against this form and can land without a format decision of its own.

**What it constrains.**

- `data/project_io.py` stays unmodified by this concern; anything the snapshot needs is
  obtained through its **public** `serialize` / `deserialize`.
- `data/snapshot_store.py` imports `data.project_io` (`data -> data`) and
  `logic.content_hash` (`data -> logic`). The reverse edge is forbidden: a snapshot reaches
  `logic` only as a `Document`, never as bytes.
- No new persisted history format may be introduced without superseding this ADR.
- Extending `data/project_io.py` with a new blob-bearing key obliges a matching `BLOB_KEYS`
  entry.

## Compliance

The layering half has detectors, and they were **run** — not read — in the
`fix-adr-citations` worktree at `267d64a`:

```
$ python scripts/check_cycles.py --json
{ "cycles": [], "edges": 761, "modules": 209 }
exit 0
$ python scripts/check_layering.py --json
{ ..., "scanned": 207, "unregistered": [], "violations": [] }
exit 0
```

`snapshot_store`'s two edges (`-> data.project_io`, `-> logic.content_hash`) sit inside a
graph with zero cycles and zero layering violations, so the `data -> data` / `data -> logic`
shape fixed above is currently held.

The `BLOB_KEYS` drift guard is `tests/data/test_snapshot_store.py`; the round-trip and
fingerprint behaviour are covered by `tests/data/test_timelapse_io_schema2.py`,
`tests/data/test_timelapse_io_schema3.py` and `tests/logic/test_timelapse_cross_session.py`.

**What has no detector, stated rather than implied.** No script can tell that a *new*
persisted history format has been introduced elsewhere in the tree — "one persisted history
payload" is a review invariant, not a gate. That is accepted risk, recorded here so it is not
mistaken for coverage.

## What this record does not verify

- **`phase-6-mode-toggle-undo`'s checkpoint store has not shipped.** Its plan §2 selects this
  snapshot form, but no checkpoint module exists under `pixelart_creator/logic/` or
  `pixelart_creator/data/` at `267d64a`. The phase-6 consumer is therefore *specified*, not
  observed, and is written that way above.
- **Deduplication was not measured.** The buffer-granularity argument is read from the shipped
  module's own reasoning and from `PixelBuffer`'s flat-array shape; no snapshot-size ratio was
  taken for this record.
- **`BLOB_KEYS` was not re-derived against every `project_io` serialiser for this record.** The
  enumeration is quoted from the shipped module; the drift guard, not this ADR, is what keeps
  it true.

## Why this record is late

The decision was made on 2026-08-17 and its ADR was assigned to `phase-10-branch-diff` **T24**
(owner AGT-08), which was never executed while the code that cites it shipped. The number
`0052` is not chosen here: it is fixed by the citation already in the tree
(`pixelart_creator/data/snapshot_store.py:4`, "planned ADR-0052") and by three plans that name
it. Writing at the cited number rather than at `highest + 1` is the deliberate exception to the
adr-author numbering rule — the citations are the fixed points, and renumbering them would
break the trail this record exists to restore.
