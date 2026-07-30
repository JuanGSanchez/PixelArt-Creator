# Traceability Matrix — Phase 6: `phase-6-tilemap`

REQ-ID ↔ dossier `S-id` / research `F` / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) ↔ test id(s).

**Mode:** POST-IMPLEMENTATION / SHIPPED (updated at the Phase-6 final architecture gate, AGT-01,
2026-07-03). Every REQ has **≥1 acceptance scenario AND both a shipped implementation and ≥1 passing
test** (logic+data 1386 tests; UI QA SHIP-READY; perf loop-back CLOSED ≤16 ms; i18n + docs green).
The "Test id(s)" column names the **real shipped test module(s)**. The two script-gated NFRs
(REQ-P6-UI-014 perf, REQ-P6-UI-017 string audit) carry a behavioural test **plus** script evidence:
AGT-10 `perf_profile --tilemap` (two-part gate) and AGT-07 `string_audit_check`.

Status legend:
- **covered** — has ≥1 Gherkin acceptance scenario, a shipped implementation, and ≥1 passing test.
- (no row is `uncovered`: every REQ has ≥1 scenario + impl + test. 0 uncovered.)

## Logic requirements (`logic/tileset.py` + `logic/tilemap.py` new; `logic/document.py` extend)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P6-LOGIC-001 | S6, Phase-6 cap | §4, §11 | SC-L001-1, SC-L001-2 | `test_tileset.py` (slice grid + invalid params) | covered |
| REQ-P6-LOGIC-002 | **PB-1** (`region`/`blit`), Phase-6 cap | §4, §11 | SC-L002-1 | `test_tileset.py` (tile derives from `region`; ColorMode inherit) | covered |
| REQ-P6-LOGIC-003 | Phase-6 cap, S6, P2 | §4, §11 | SC-L003-1, SC-L003-2 | `test_tileset.py` (row-major ids; global gid / first-gid) | covered |
| REQ-P6-LOGIC-004 | **PB-1**, Phase-6 cap, S7 | §4, §11 | SC-L004-1 | `test_tileset.py` (reversible source-tile edit seen by all readers) | covered |
| REQ-P6-LOGIC-005 | S6, Phase-6 cap | §4, §11 | SC-L005-1 | `test_tilemap.py` (linked instance: gid + flip, no pixel copy; empty = gid 0) | covered |
| REQ-P6-LOGIC-006 | **PB-1**, Phase-6 cap (tile-linking), S6 | §4, §11 | SC-L006-1 | `test_tilemap.py` (source-tile edit propagates to all instances) | covered |
| REQ-P6-LOGIC-007 | **HIS-1** (command pattern), S7 | §4, §11 | SC-L007-1, SC-L007-2 | `test_tilemap.py` (reversible stamp/erase/fill; unknown-gid reject) | covered |
| REQ-P6-LOGIC-008 | S6, Phase-6 cap, S7 | §4, §11 | SC-L008-1 | `test_tilemap.py` (reversible layer add/remove/reorder/visibility; MAX bound) | covered |
| REQ-P6-LOGIC-009 | S6, Phase-6 cap, Art. VII | §4, §11 | SC-L009-1 | `test_tilemap.py` (arbitrary/negative coords, sparse, empty read) | covered |
| REQ-P6-LOGIC-010 | Phase-6 cap (auto-tiling), **F-tilemap (DEP-1)**, P2 | §4, §11 | SC-L010-1 | `test_autotile.py` (deterministic 256→47 LUT resolution) | covered |
| REQ-P6-LOGIC-011 | Phase-6 cap (auto-tiling), S7, P2 | §4, §11 | SC-L011-1 | `test_autotile.py` + `test_tilemap.py` (auto-tile reversible; logical placement preserved, neighbour re-resolve captured) | covered |
| REQ-P6-LOGIC-012 | **HIS-1**, S7, C1 | §4, §11 | SC-L012-1 | `test_tilemap.py` + `test_document_tilemap.py` (all mutations + attach/detach do/undo; view state not reversible) | covered |
| REQ-P6-LOGIC-013 | **PB-1**, **CO-4** (`composite_stack`), S7 | §4, §11 | SC-L013-1 | `test_tilemap.py` + `test_tilemap_render_vectorised.py` (resolve instances + composite via CO-4; vectorised, non-destructive) | covered |
| REQ-P6-LOGIC-014 | Art. II, Art. VII, S12 | §4, §11 | SC-L014-1, SC-L014-2 | `test_tileset.py` / `test_tilemap.py` (bounds enforced; defaults from constants; ≠ TILE_SIZE) | covered |

## UI requirements (`ui/` tileset editor / tilemap canvas / tools / layers / auto-tile / I/O actions)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P6-UI-001 | REQ-P6-LOGIC-001, -003 | §4, §11 | SC-UI-001-1 | `test_tileset_editor.py` (slice display + select) | covered |
| REQ-P6-UI-002 | REQ-P6-LOGIC-001, -014 | §4, §11 | SC-UI-002-1 | `test_tileset_editor.py` (slicing config re-slice + reject) | covered |
| REQ-P6-UI-003 | REQ-P6-LOGIC-004, -006 | §4, §11 | SC-UI-003-1 | `test_tileset_editor.py` + `test_tileset_pixel_editor.py` (edit source tile → instances update; one command) | covered |
| REQ-P6-UI-004 | REQ-P6-LOGIC-013, S1 | §4, §11 | SC-UI-004-1 | `test_tilemap_canvas.py` (composited layer stack render) | covered |
| REQ-P6-UI-005 | REQ-P6-LOGIC-005, -007 | §4, §11 | SC-UI-005-1 | `test_tilemap_canvas.py` + `test_tilemap_canvas_interaction.py` (stamp = one command, linked instance) | covered |
| REQ-P6-UI-006 | REQ-P6-LOGIC-007 | §4, §11 | SC-UI-006-1 | `test_tilemap_canvas_interaction.py` (erase = one command; undo restores) | covered |
| REQ-P6-UI-007 | REQ-P6-LOGIC-007 | §4, §11 | SC-UI-007-1 | `test_tilemap_canvas_interaction.py` + `test_tilemap_paint_edges.py` (rectangle-fill = one command) | covered |
| REQ-P6-UI-008 | REQ-P6-LOGIC-008 | §4, §11 | SC-UI-008-1 | `test_tilemap_layers.py` (layer add/remove/reorder/hide, one command each) | covered |
| REQ-P6-UI-009 | REQ-P6-LOGIC-010, -011 | §4, §11 | SC-UI-009-1 | `test_tilemap_canvas.py` (auto-tile on stamp; single undoable command) | covered |
| REQ-P6-UI-010 | REQ-P6-LOGIC-009 | §4, §11 | SC-UI-010-1 | `test_tilemap_canvas.py` (pan into empty space + stamp; nav no command) | covered |
| REQ-P6-UI-011 | REQ-P6-DATA-001 | §4, §11 | SC-UI-011-1 | `test_tilemap_io_actions.py` (export writes Tiled JSON, portable path) | covered |
| REQ-P6-UI-012 | REQ-P6-DATA-002, -003 | §4, §11 | SC-UI-012-1 | `test_tilemap_io_actions.py` (import reconstructs; malformed → graceful error) | covered |
| REQ-P6-UI-013 | S7, C1, F1, REQ-P6-LOGIC-007/-008/-012 | §4, §11 | SC-UI-013-1 | `test_tilemap_canvas.py` + `test_tilemap_guards.py` + `test_tilemap_trivial_guards.py` (one command per edit; view ops none) | covered |
| REQ-P6-UI-014 (NFR) | S1, S12, F2, F7, Art. VI, DEP-3 | §5, §11 | SC-UI-014-1 | `test_tilemap_chunk_cache.py` + `test_tilemap_teardown.py` (per-chunk cache/`chunk_version` viewport redraw + deterministic warm teardown); AGT-10 `perf_profile --tilemap` two-part gate (loop-back CLOSED ≤16 ms) | covered |
| REQ-P6-UI-015 (NFR) | Art. V §1 | §5, §11 | SC-UI-015-1 | `test_tileset_editor.py` / `test_tilemap_canvas.py` (accessible names / keyboard / focus) | covered |
| REQ-P6-UI-016 (NFR) | Art. V §3 | §5, §11 | SC-UI-016-1 (+ every UI scenario in both themes) | both-theme fixtures across the UI test modules | covered |
| REQ-P6-UI-017 (NFR) | Art. V §2, F6 | §5, §11 | SC-UI-017-1 | tr()-wrapped panels + `changeEvent` retranslate; AGT-07 `string_audit_check` (i18n done) | covered |

## DATA requirements (`data/` Tiled JSON I/O + native `.pixproj` persistence)

> DEP-2 (unresolved, AGT-01 plan/ADR): (a) Tiled JSON **encoding set** (CSV vs base64+zlib layer
> data; embedded vs external tileset), (b) **`.pixproj` schema-version** for tilemap persistence.
> Back-compat read of tilemap-less projects is required either way (REQ-P6-DATA-004). Final
> `REQ-P6-DATA-*` count may be refined at plan time; this spec allocates `-001..-004`.

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P6-DATA-001 | **IO-3** (`project_io` pattern), S6/S7, Phase-6 cap | §4, §11 | SC-D001-1 | `test_tiled_io.py` (valid Tiled JSON export) | covered |
| REQ-P6-DATA-002 | **IO-3**, S7, Phase-6 cap, P2 | §4, §11 | SC-D002-1 | `test_tiled_io.py` (export→import lossless round-trip) | covered |
| REQ-P6-DATA-003 | Art. VII, **IO-3** | §4, §11 | SC-D003-1 | `test_tiled_io.py` (defensive load: bounds/gid/size/orientation → `ProjectIOError`) | covered |
| REQ-P6-DATA-004 | **IO-3**, **DOC-1**, S7, Phase-6 cap | §4, §11 | SC-D004-1 | `test_project_io_tilemap.py` (native round-trip + tilemap-less back-compat) | covered |

## Coverage summary

- **35 of 35 REQ-IDs** (14 LOGIC + 17 UI + 4 DATA) have **≥1 acceptance scenario + a shipped
  implementation + ≥1 passing test** (**0 uncovered**).
- **~28 Gherkin scenarios** across the requirements, incl. the determinism scenarios SC-L003-1 /
  SC-L010-1 and the lossless round-trip SC-D002-1.
- **Tests are SHIPPED and green** (logic+data 1386 tests; UI QA SHIP-READY after S2+S3 fixes). Real
  shipped modules — logic/data (AGT-04): `tests/logic/{test_autotile,test_tileset,test_tilemap,`
  `test_document_tilemap,test_tilemap_render_vectorised}.py`,
  `tests/data/{test_tiled_io,test_project_io_tilemap}.py`; UI (AGT-06, both themes):
  `tests/ui/{test_tileset_editor,test_tileset_pixel_editor,test_tilemap_canvas,`
  `test_tilemap_canvas_interaction,test_tilemap_layers,test_tilemap_io_actions,test_tilemap_window,`
  `test_tilemap_chunk_cache,test_tilemap_teardown,test_tilemap_guards,test_tilemap_trivial_guards,`
  `test_tilemap_paint_edges}.py`.
- The two NFRs (UI-014 perf, UI-017 string audit) carry behavioural tests **plus** script evidence:
  AGT-10 `perf_profile --tilemap` (two-part gate, loop-back CLOSED ≤16 ms) / AGT-07
  `string_audit_check` (i18n done).

## Forward-inherited primitive traces (Article X §2 — explicit)

The prompt directs Phase 6 to formally reflect what it inherits forward vs. builds new:

| Inherited primitive | Origin | Phase-6 forward trace |
| --- | --- | --- |
| **PB-1** — `PixelBuffer.region(x,y,w,h)` / `.blit(src,dx,dy,blend=)` / `.data` | `logic/pixel_buffer.py` (Phase 1, shipped) | → REQ-P6-LOGIC-002 (*tiles are source-image regions*) → REQ-P6-LOGIC-004/-006 (source-tile edit propagation) → REQ-P6-LOGIC-013 (stamping/blit in render) |
| **CM-1** — `ColorMode` (RGBA / INDEXED) | `logic/pixel_buffer.py` (Phase 1, shipped) | → REQ-P6-LOGIC-002 (tiles inherit the source ColorMode) → REQ-P6-LOGIC-014 (CL-15) |
| **HIS-1** — `history.Command` / `FunctionCommand` / `History` | `logic/history.py` (Phase 1, shipped) | → REQ-P6-LOGIC-007/-012 (reversible stamp/erase/fill/layer/auto-tile ops) → REQ-P6-UI-013 (one `QUndoCommand` per edit) |
| **CO-4** — `blend.composite_stack` (ordered layer-stack flatten) | `logic/blend.py` (Phase 4, shipped) | → REQ-P6-LOGIC-013 (multi-layer tilemap flatten delegates to it) |
| **IO-3** — `data/project_io.py` defensive-load pattern (`ProjectIOError`, `_SUPPORTED_VERSIONS`, type/bounds checks, no `eval`, `pathlib`) | `data/project_io.py` (Phase 1/4, shipped) | → REQ-P6-DATA-001/-002/-003 (Tiled JSON export/round-trip/defensive load) → REQ-P6-DATA-004 (native persistence reuses the pattern) |
| **DOC-1** — the `Document` tree | `logic/document.py` (Phase 1, shipped) | → REQ-P6-DATA-004 (tileset/tilemap collection attaches to the document for native round-trip) |

## Cross-layer trace (UI binds to new logic / DATA)

| UI REQ | Binds to logic/data REQ / shipped | Note |
| --- | --- | --- |
| REQ-P6-UI-001/-002/-003 | REQ-P6-LOGIC-001/-003/-004/-006 | tileset editor over slicing + source-tile edit propagation |
| REQ-P6-UI-004 | REQ-P6-LOGIC-013 (PB-1 / CO-4) | canvas renders the composited map |
| REQ-P6-UI-005/-006/-007 | REQ-P6-LOGIC-005/-007 | stamp / erase / rectangle-fill of linked instances |
| REQ-P6-UI-008 | REQ-P6-LOGIC-008 | tilemap layer management |
| REQ-P6-UI-009 | REQ-P6-LOGIC-010/-011 | auto-tile toggle over deterministic/reversible resolution |
| REQ-P6-UI-010 | REQ-P6-LOGIC-009 | infinite-map navigation |
| REQ-P6-UI-011/-012 | REQ-P6-DATA-001/-002/-003 | export/import Tiled JSON |
| REQ-P6-UI-013 | REQ-P6-LOGIC-007/-008/-012 via `ui/commands.py` | one `QUndoCommand` per edit (Article I) |

## Dependency / gap list (for AGT-01 `sdd-plan` / `sdd-analyze`)

- **DEP-1 (Researcher).** `docs/research-phase6-tilemap.md` grounds the auto-tiling algorithm family
  (blob-47 vs Wang/terrain) + neighbourhood convention, the Tiled JSON encoding set, and
  infinite-map chunking conventions — **concurrent / not-yet-present**. AGT-01 must not invent these;
  the observable contract + Tiled-parity defaults (spec §10) are fixed regardless.
- **DEP-2 (AGT-01 / plan/ADR).** (a) auto-tile algorithm family + neighbourhood; (b) Tiled JSON
  encoding set (CSV vs base64+zlib; embedded vs external tileset); (c) infinite-map chunking scheme;
  (d) `.pixproj` schema-version for tilemap persistence (bump vs additive; back-compat required,
  REQ-P6-DATA-004). Final `REQ-P6-DATA-*` count may be refined at plan.
- **DEP-3 (AGT-10).** Viewport tile-culling + dirty-rect recomposite for REQ-P6-UI-014 / SC-UI-014-1
  — resolving every cell of a (possibly infinite) 8K map per frame will exceed `FRAME_BUDGET_MS`.
  Plan-level.
- **Article II watch (BF-2).** AGT-01 must place `DEFAULT_TILE_WIDTH/HEIGHT`,
  `DEFAULT_TILE_MARGIN/SPACING`, `MAX_TILE_DIMENSION`, `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS` in
  `logic/constants.py` (no literals); the shipped `TILE_SIZE` (64, viewport-culling) is **distinct**
  and must not be reused as the tileset tile dimension.

## Recommended slicing (logic-first vertical slices)

1. **Slice A — tileset (logic).** REQ-P6-LOGIC-001..004, -014 (`logic/tileset.py`: slicing,
   id↔region, source-tile edit, constants). AGT-03 + AGT-04.
2. **Slice B — tilemap model + reversible ops (logic).** REQ-P6-LOGIC-005..008, -012 (`logic/tilemap.py`:
   linked instances, stamp/erase/fill, layers, reversibility). AGT-03 + AGT-04.
3. **Slice C — infinite maps + auto-tiling + render (logic).** REQ-P6-LOGIC-009..011, -013.
   AGT-01 fixes the auto-tile family + chunking (DEP-2), grounded by the Researcher (DEP-1).
   AGT-03 + AGT-04.
4. **Slice D — Tiled JSON I/O + native persistence (data).** REQ-P6-DATA-001..004 (export /
   round-trip / defensive load / `.pixproj` persistence). AGT-01 fixes the encoding set + schema
   version (DEP-2). AGT-03 + AGT-04.
5. **Slice E — tileset editor + slicing UI.** REQ-P6-UI-001..003, -013, -015..017. AGT-05 + AGT-06.
6. **Slice F — tilemap canvas + stamping + layers + auto-tile + infinite nav.** REQ-P6-UI-004..010,
   -014 (coordinated with **AGT-10**, DEP-3). AGT-05 + AGT-06 + AGT-10.
7. **Slice G — import/export UI.** REQ-P6-UI-011, -012. AGT-05 + AGT-06.

## Notes for `sdd-analyze` (AGT-01)

- Spec + matrix are internally consistent: 35 REQs, 35 with scenarios, 0 uncovered; tests
  `pending` (forward). SDD order: specify+clarify (this) → plan → tasks → analyze → implement → test.
- **No open clarification** (spec §10): all 16 ambiguities resolved with grounded defaults; the
  auto-tile family / JSON encoding / chunking scope risks are named HOW decisions (DEP-1/DEP-2), not
  suspended, and the observable contracts are fixed.
- **Three named dependencies** (DEP-1 Researcher grounding, DEP-2 AGT-01 plan/ADR, DEP-3 AGT-10
  recomposite) must be resolved/allocated before/within the plan — none blocks this spec.
