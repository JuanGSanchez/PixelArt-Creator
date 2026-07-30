# Traceability Matrix — Phase 7: `phase-7-export`

REQ-ID ↔ dossier `S-id` / research `F` / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) ↔ test id(s).

**Mode:** SHIPPED / POST-IMPLEMENTATION (updated at the Phase-7 FINAL architecture gate, AGT-01,
2026-07-04). Every REQ has **≥1 acceptance scenario AND ≥1 passing test in a shipped module**;
implementation landed in `logic/{export,atlas}.py`, `data/{export_io,export_cli}.py`, and the `ui/`
export modules. Test modules verified present + collecting: `tests/logic/{test_export,test_atlas}.py`
(53 + 21), `tests/data/{test_export_io,test_export_cli}.py` (14 + 15) = **103 logic+data**; the 8
`tests/ui/test_export_*.py` modules = **76 UI** (both themes parametrised). The two script-gated NFRs
(REQ-P7-UI-010 responsiveness, REQ-P7-UI-013 string audit) carry a behavioural pytest-qt scenario
**plus** script evidence at ship (AGT-07 `string_audit_check`; responsiveness is an off-thread worker
assertion, not the 16 ms canvas budget — see §5 of the spec).

Status legend:
- **covered (shipped)** — has ≥1 Gherkin acceptance scenario in `spec.md §11` AND ≥1 passing test in
  a shipped module (named in the Test id(s) column).
- (no REQ is `uncovered`: every REQ has ≥1 scenario + ≥1 test. **0 uncovered**.)

## Logic requirements (`logic/export.py` + `logic/atlas.py` new; `logic/constants.py` extend)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P7-LOGIC-001 | **CO-4** (`composite_stack`), **PB-1**, S6, S7 | §4, §11 | SC-L001-1 | `tests/logic/test_export.py` (flatten via CO-4; non-destructive) | covered (shipped) |
| REQ-P7-LOGIC-002 | P2, S6, Phase-7 cap | §4, §11 | SC-L002-1 | `tests/logic/test_export.py` (pure/deterministic pipeline; no time/random/locale) | covered (shipped) |
| REQ-P7-LOGIC-003 | P2, Phase-7 cap, S6 | §4, §11 | SC-L003-1 | `tests/logic/test_export.py` (PNG byte-reproducible) | covered (shipped) |
| REQ-P7-LOGIC-004 | **FR-1** (`frames`/`duration_ms`), P2, Phase-7 cap | §4, §11 | SC-L004-1 | `tests/logic/test_export.py` (animated GIF byte-reproducible; durations) | covered (shipped) |
| REQ-P7-LOGIC-005 | **FR-1**, P2, Phase-7 cap | §4, §11 | SC-L005-1 | `tests/logic/test_export.py` (sprite-sheet deterministic + byte-reproducible) | covered (shipped) |
| REQ-P7-LOGIC-006 | **CP-1** (`compactor.compact` MaxRects, F8), Phase-7 cap, P2 | §4, §11 | SC-L006-1 | `tests/logic/test_atlas.py` (non-overlap via CP-1; unfit → AtlasError wrapping CompactionError; 8K-ceiling guard) | covered (shipped) |
| REQ-P7-LOGIC-007 | **CP-1**, Phase-7 cap, P2 | §4, §11 | SC-L007-1 | `tests/logic/test_atlas.py` (JSON coords ↔ packed-image pixel round-trip) | covered (shipped) |
| REQ-P7-LOGIC-008 | **IO-3**, P2, Phase-7 cap | §4, §11 | SC-L008-1 | `tests/logic/test_export.py` (metadata deterministic + complete) | covered (shipped) |
| REQ-P7-LOGIC-009 | Article I, S11, Phase-7 cap | §4, §11 | SC-L009-1 | `tests/logic/test_export.py` + `tests/ui/test_export_parity.py` + `check_layering`/`check_cycles` exit 0 (Qt-free; no event loop) | covered (shipped) |
| REQ-P7-LOGIC-010 | Phase-7 cap (batch), P2, S6 | §4, §11 | SC-L010-1 | `tests/logic/test_export.py` (`run_batch`: each batch output == single export) | covered (shipped) |
| REQ-P7-LOGIC-011 | Phase-7 cap (presets), F8 landscape, S6 | §4, §11 | SC-L011-1 | `tests/logic/test_export.py` layout + `tests/data/test_export_io.py` (Unity/Godot engine-ready) | covered (shipped) |
| REQ-P7-LOGIC-012 | Article II, Article VII, S12 | §4, §11 | SC-L012-1 | `tests/logic/test_export.py` + `tests/logic/test_atlas.py` (bounds enforced; defaults from constants; MAX_ATLAS_DIMENSION per-axis clamp) | covered (shipped) |
| REQ-P7-LOGIC-013 | **IO-3**, **DOC-1**, Phase-7 cap (CLI), P2, S11 | §4, §11 | SC-L013-1 | `tests/data/test_export_cli.py` + `tests/ui/test_export_parity.py` (CLI==GUI byte-identity for a fixed .pixproj) | covered (shipped) |

## UI requirements (`ui/` export dialogs / options / batch / preset selection)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P7-UI-001 | REQ-P7-LOGIC-001, -003 | §4, §11 | SC-UI-001-1 | `tests/ui/test_export_dialog.py` + `tests/ui/test_export_actions.py` (format/options/destination) | covered (shipped) |
| REQ-P7-UI-002 | REQ-P7-LOGIC-004 | §4, §11 | SC-UI-002-1 | `tests/ui/test_export_dialog.py` (GIF frame-source/loop; durations honoured) | covered (shipped) |
| REQ-P7-UI-003 | REQ-P7-LOGIC-005 | §4, §11 | SC-UI-003-1 | `tests/ui/test_export_dialog.py` (sheet columns/rows/padding; reject OOR) | covered (shipped) |
| REQ-P7-UI-004 | REQ-P7-LOGIC-006, -007, REQ-P7-DATA-004 | §4, §11 | SC-UI-004-1 | `tests/ui/test_export_dialog.py` (atlas padding/max-dim + metadata toggle) | covered (shipped) |
| REQ-P7-UI-005 | REQ-P7-LOGIC-010 | §4, §11 | SC-UI-005-1 | `tests/ui/test_export_batch_ui.py` (multi-target one action; per-target progress/failure) | covered (shipped) |
| REQ-P7-UI-006 | REQ-P7-LOGIC-011, REQ-P7-DATA-002 | §4, §11 | SC-UI-006-1 | `tests/ui/test_export_dialog.py` (Unity/Godot preset selection) | covered (shipped) |
| REQ-P7-UI-007 | REQ-P7-LOGIC-009, -013, P2 | §4, §11 | SC-UI-007-1 | `tests/ui/test_export_parity.py` (GUI export == CLI export byte-for-byte) | covered (shipped) |
| REQ-P7-UI-008 | Article VII, REQ-P7-LOGIC-006 | §4, §11 | SC-UI-008-1 | `tests/ui/test_export_actions.py` + `tests/ui/test_export_dialog.py` (unfit atlas / unwritable path → graceful error) | covered (shipped) |
| REQ-P7-UI-009 | S7, C1, CL-12 | §4, §11 | SC-UI-009-1 | `tests/ui/test_export_actions.py` (non-destructive; no QUndoCommand — verified 0 export refs in `ui/commands.py`) | covered (shipped) |
| REQ-P7-UI-010 (NFR) | S1, S12, Article VI, DEP-3 | §5, §11 | SC-UI-010-1 | `tests/ui/test_export_responsive.py` + `tests/ui/test_export_worker_invariant.py` + `tests/ui/test_export_teardown.py` (off-thread; cancel; deterministic teardown, no segfault under -n auto) | covered (shipped) |
| REQ-P7-UI-011 (NFR) | Article V §1 | §5, §11 | SC-UI-011-1 | `tests/ui/test_export_a11y.py` (accessible names / keyboard / focus) | covered (shipped) |
| REQ-P7-UI-012 (NFR) | Article V §3 | §5, §11 | SC-UI-012-1 (+ every UI scenario in both themes) | both-theme `[light]`/`[dark]` fixtures across the 8 `tests/ui/test_export_*.py` modules | covered (shipped) |
| REQ-P7-UI-013 (NFR) | Article V §2, F6 | §5, §11 | SC-UI-013-1 | tr()-wrapped export UI + `changeEvent` retranslate (across `tests/ui/test_export_*.py`); AGT-07 `string_audit_check` clean; `i18n/es.qm` (509) | covered (shipped) |

## DATA requirements (`data/` output/artifact serialisation + CLI input load)

> DEP-2 (unresolved, AGT-01 plan/ADR): (a) canonical sprite-sheet/atlas **JSON schema** (Aseprite vs
> TexturePacker vs both); (b) exact **engine-preset artifacts** (Unity `.meta`/JSON; Godot
> `SpriteFrames`/`.tres`/`AtlasTexture`); (c) whether **APNG** is a Phase-7 format; (d) specific
> **Pillow options** + GIF palette reduction (must be deterministic); (e) **CLI entrypoint
> location/grammar**. Observable contracts (byte-reproducible; coord/pixel round-trip; engine-ready
> re-import; CLI==GUI) are fixed regardless. Final `REQ-P7-DATA-*` count may be refined at plan.

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P7-DATA-001 | **IO-3** (`project_io` pattern), Article VII §2, Phase-7 cap | §4, §11 | SC-D001-1 | `tests/data/test_export_io.py` (portable write of exact engine bytes + JSON; no re-encode) | covered (shipped) |
| REQ-P7-DATA-002 | REQ-P7-LOGIC-011, **IO-3**, Phase-7 cap | §4, §11 | SC-D002-1 | `tests/data/test_export_io.py` (Unity/Godot artifacts: deterministic, portable) | covered (shipped) |
| REQ-P7-DATA-003 | Article VII, **IO-3**, **DOC-1** | §4, §11 | SC-D003-1 | `tests/data/test_export_cli.py` (defensive .pixproj load; malformed → ProjectIOError; == GUI Document) | covered (shipped) |
| REQ-P7-DATA-004 | REQ-P7-LOGIC-007, -008, **IO-3**, P2 | §4, §11 | SC-D004-1 | `tests/data/test_export_io.py` (written JSON valid + re-importable; coord/pixel round-trip) | covered (shipped) |

## Coverage summary

- **30 of 30 REQ-IDs** (13 LOGIC + 13 UI + 4 DATA) have **≥1 acceptance scenario AND ≥1 passing test
  in a shipped module** (**0 uncovered**). Implementation + tests are **SHIPPED**.
- **30 Gherkin scenarios** across the requirements, incl. the reproducibility scenarios SC-L003-1 /
  SC-L004-1 / SC-L005-1, the atlas non-overlap + coordinate/pixel round-trip SC-L006-1 / SC-L007-1,
  and the CLI==GUI byte-identity SC-L013-1 / SC-UI-007-1.
- **Shipped test modules** (verified present + collecting at the final gate, 2026-07-04):
  `tests/logic/test_export.py` (53), `tests/logic/test_atlas.py` (21),
  `tests/data/test_export_io.py` (14), `tests/data/test_export_cli.py` (15) = **103 logic+data**;
  `tests/ui/{test_export_dialog,test_export_worker_invariant,test_export_batch_ui,test_export_parity,test_export_responsive,test_export_teardown,test_export_a11y,test_export_actions}.py`
  = **76 UI**. (`tests/ui/_export_helpers.py` is a shared fixture module, not a test module.)
- SDD order complete: specify+clarify → plan → tasks → analyze → implement → test → **final gate (this
  update)**. Logic/data tests by AGT-04 (headless), UI tests by AGT-06 (both themes).
- The NFRs: REQ-P7-UI-013 (i18n) carries `string_audit_check` script evidence at ship; REQ-P7-UI-010
  (responsiveness) is a behavioural pytest-qt assertion (event processing / cancel during export) —
  **not** the 16 ms canvas frame budget, which does not apply to batch export (spec §5).

## Forward-inherited primitive traces (Article X §2 — explicit)

The prompt directs Phase 7 to formally reflect what it inherits forward vs. builds new:

| Inherited primitive | Origin | Phase-7 forward trace |
| --- | --- | --- |
| **PB-1** — `PixelBuffer` (`.data` / `.region`) — the source pixels | `logic/pixel_buffer.py` (Phase 1, shipped) | → REQ-P7-LOGIC-001 (source pixels flattened for export) |
| **CO-4** — `blend.composite_stack` (ordered layer-stack flatten) | `logic/blend.py` (Phase 4, shipped) | → REQ-P7-LOGIC-001 (each export image is a flattened frame; compositing not re-implemented) |
| **FR-1** — `Document → frames` + `Frame.duration_ms` | `logic/document.py` (Phase 1/5, shipped) | → REQ-P7-LOGIC-004 (animated GIF from frames + durations) → REQ-P7-LOGIC-005 (sprite-sheet frame source) |
| **CP-1** — `compactor.compact(rects,max_w,max_h) -> Packing` (deterministic MaxRects BSSF, rotation off; `Placement`, `CompactionError`) | `logic/compactor.py` (F8/FIX-13, shipped) | → REQ-P7-LOGIC-006 (non-overlapping atlas packing) → REQ-P7-LOGIC-007 (placements are the JSON coords) → REQ-P7-LOGIC-012 (caller passes `MAX_ATLAS_DIMENSION`; compactor imports no constants) |
| **IO-3** — `data/project_io.py` defensive-load pattern (`ProjectIOError`, `_SUPPORTED_VERSIONS`, type/bounds checks, no `eval`, `pathlib`) | `data/project_io.py` (Phase 1/4, shipped) | → REQ-P7-DATA-003 (CLI input load) → REQ-P7-LOGIC-008 / REQ-P7-DATA-004 (metadata patterns) → REQ-P7-DATA-001 (portable serialisation) |
| **DOC-1** — the `Document` tree | `logic/document.py` (Phase 1, shipped) | → REQ-P7-LOGIC-013 / REQ-P7-DATA-003 (the export subject; CLI Document == GUI Document) |

## Cross-layer trace (UI binds to new logic / DATA)

| UI REQ | Binds to logic/data REQ / shipped | Note |
| --- | --- | --- |
| REQ-P7-UI-001 | REQ-P7-LOGIC-001/-003 | export dialog drives the logic/data engine |
| REQ-P7-UI-002 | REQ-P7-LOGIC-004 | GIF options; per-frame durations honoured |
| REQ-P7-UI-003 | REQ-P7-LOGIC-005 | sprite-sheet grid options |
| REQ-P7-UI-004 | REQ-P7-LOGIC-006/-007, REQ-P7-DATA-004 | atlas options + matching JSON metadata |
| REQ-P7-UI-005 | REQ-P7-LOGIC-010 | batch UI over the deterministic batch driver |
| REQ-P7-UI-006 | REQ-P7-LOGIC-011, REQ-P7-DATA-002 | engine-preset selection + artifacts |
| REQ-P7-UI-007 | REQ-P7-LOGIC-009/-013 | GUI export == CLI export (same pure engine) |
| REQ-P7-UI-008 | REQ-P7-LOGIC-006 (CompactionError) | graceful export-error surfacing |
| REQ-P7-UI-009 | — (read-only IO; no `ui/commands.py`) | export is non-destructive, no undo entry |

## Dependency / gap list (for AGT-01 `sdd-plan` / `sdd-analyze`)

- **DEP-1 (Researcher).** `docs/research-phase7-export.md` grounds deterministic Pillow PNG/GIF
  encoder options, the sprite-sheet/atlas JSON schema landscape (Aseprite vs TexturePacker),
  Unity/Godot import-artifact conventions, and APNG feasibility — **concurrent / being produced in
  parallel** (feeds AGT-01). AGT-01 must not invent these; the observable contracts + export-parity
  defaults (spec §10) are fixed regardless.
- **DEP-2 (AGT-01 / plan/ADR).** (a) canonical JSON schema; (b) engine-preset artifact set; (c) APNG
  scope; (d) specific Pillow options + GIF palette reduction (deterministic); (e) CLI entrypoint
  location/grammar. Each is a HOW decision; the observable contracts (byte-reproducible; coord/pixel
  round-trip; engine-ready re-import; CLI==GUI) are fixed. Final `REQ-P7-DATA-*` count may be refined.
- **DEP-3 (AGT-01 / AGT-10).** Worker-thread vs GUI-thread export for REQ-P7-UI-010 responsiveness —
  the pure engine is thread-agnostic (Qt-free). Plan-level; export is **not** the 16 ms render loop.
- **Article II watch (BF-1).** AGT-01 must place `DEFAULT_SPRITE_SHEET_COLUMNS`,
  `DEFAULT_ATLAS_PADDING`, `MAX_ATLAS_DIMENSION`, `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES` in
  `logic/constants.py` (no literals); the atlas caller passes `MAX_ATLAS_DIMENSION` explicitly to
  `compactor.compact` (CP-1 imports no constants).
- **Article I watch (BF-2).** All encoding/packing/serialising must be Qt-free (`logic/`+`data/`) and
  the CLI entrypoint must import no Qt — this purity is what makes CLI==GUI byte-identity hold
  (REQ-P7-LOGIC-009). Export adds **no** `ui/commands.py` logic (not an undoable command).

## Recommended slicing (logic-first vertical slices)

1. **Slice A — flatten + PNG + deterministic pipeline (logic).** REQ-P7-LOGIC-001, -002, -003, -012
   (`logic/export.py`: CO-4 flatten, byte-reproducible PNG, determinism backbone, constants).
   AGT-03 + AGT-04.
2. **Slice B — GIF + sprite-sheet (logic).** REQ-P7-LOGIC-004, -005 (animated GIF from FR-1 frames;
   deterministic sheet layout). AGT-01 fixes Pillow/GIF options (DEP-2), grounded by the Researcher
   (DEP-1). AGT-03 + AGT-04.
3. **Slice C — texture atlas + metadata (logic).** REQ-P7-LOGIC-006, -007, -008 (`logic/atlas.py`
   over CP-1; coord/pixel round-trip; deterministic metadata). AGT-01 fixes the JSON schema (DEP-2).
   AGT-03 + AGT-04.
4. **Slice D — batch + presets + headless CLI (logic/data).** REQ-P7-LOGIC-009, -010, -011, -013,
   REQ-P7-DATA-002, -003 (headless engine, batch driver, Unity/Godot presets, CLI entrypoint + input
   load). AGT-01 fixes engine artifacts + CLI grammar (DEP-2). AGT-03 + AGT-04.
5. **Slice E — output serialisation (data).** REQ-P7-DATA-001, -004 (portable write of engine bytes +
   JSON; valid re-importable metadata). AGT-03 + AGT-04.
6. **Slice F — export UI (dialogs, options, presets).** REQ-P7-UI-001..004, -006, -008, -009,
   -011..013. AGT-05 + AGT-06.
7. **Slice G — batch UI + headless parity + responsiveness.** REQ-P7-UI-005, -007, -010 (coordinated
   with AGT-10, DEP-3). AGT-05 + AGT-06 + AGT-10.

## Notes for `sdd-analyze` (AGT-01)

- Spec + matrix are internally consistent: 30 REQs, 30 with scenarios, 0 uncovered; tests `pending`
  (forward). SDD order: specify+clarify (this) → plan → tasks → analyze → implement → test.
- **No open clarification** (spec §10): all 17 ambiguities resolved with grounded defaults; the JSON
  schema / engine artifacts / APNG / Pillow-options scope risks are named HOW decisions (DEP-1/DEP-2),
  not suspended, and every export-format REQ is phrased around the observable contract so those
  choices do not change acceptance.
- **Three named dependencies** (DEP-1 Researcher grounding, DEP-2 AGT-01 plan/ADR, DEP-3 AGT-01/AGT-10
  responsiveness) must be resolved/allocated before/within the plan — none blocks this spec.
