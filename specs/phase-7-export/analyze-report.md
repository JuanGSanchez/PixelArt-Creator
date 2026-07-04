# Analyze Report (C1) — Phase 7: Export & Pipeline Integration

| Field | Value |
| --- | --- |
| Feature | `phase-7-export` |
| Author | Claude (AGT-01, Architecture) via `sdd-analyze` |
| Date | 2026-07-04 |
| Artifacts | `constitution.md`, `specs/phase-7-export/spec.md`, `specs/phase-7-export/plan.md`, `specs/phase-7-export/tasks.md` (all four present — gate satisfied) |
| Gate | **Article VIII (C1)** — no implement dispatch until this passes with zero unresolved findings |
| Verdict | **PASS** — 0 unresolved cross-artifact findings; 0 uncovered REQ-IDs |

---

## 1. Gate precondition

All four artifacts exist and are parseable (Error AN-E1/AN-E2 not triggered). Cross-artifact analysis
proceeds.

## 2. Coverage — every REQ-ID → plan module + ≥1 task + ≥1 acceptance scenario

**30 of 30 REQ-IDs covered (0 uncovered).** 13 LOGIC + 13 UI + 4 DATA.

### LOGIC (`logic/export.py`, `logic/atlas.py`, `logic/constants.py`)

| REQ | Plan module / surface | Task(s) | Scenario |
| --- | --- | --- | --- |
| LOGIC-001 | `export.flatten_frame` (CO-4) | T7A-02, T7A-06 | SC-L001-1 |
| LOGIC-002 | pipeline determinism (§2/§10) | T7A-05, T7A-06 | SC-L002-1 |
| LOGIC-003 | `export.encode_png` (ADR-0019) | T7A-03, T7A-06 | SC-L003-1 |
| LOGIC-004 | `export.encode_gif` (ADR-0019) | T7A-04, T7A-06 | SC-L004-1 |
| LOGIC-005 | `export.build_sprite_sheet` | T7B-01, T7B-04 | SC-L005-1 |
| LOGIC-006 | `atlas.pack_atlas` (CP-1) | T7B-02, T7B-04 | SC-L006-1 |
| LOGIC-007 | `export.build_metadata_json` | T7B-03, T7B-04 | SC-L007-1 |
| LOGIC-008 | `export.build_metadata_json` | T7B-03, T7B-04 | SC-L008-1 |
| LOGIC-009 | headless Qt-free engine (§3.4) | T7C-01, T7C-06 | SC-L009-1 |
| LOGIC-010 | `export.run_batch` | T7C-01, T7C-05 | SC-L010-1 |
| LOGIC-011 | layout (logic) + preset writers (data) | T7C-03, T7C-05 | SC-L011-1 |
| LOGIC-012 | `constants.py` bounds/defaults | T7A-01, T7A-05, T7A-06 | SC-L012-1 |
| LOGIC-013 | `data/export_cli.main` (CLI==GUI) | T7C-04, T7C-05 | SC-L013-1 |

### UI (`ui/export_dialog.py`, `batch_export_panel.py`, `export_worker.py`, `export_actions.py`)

| REQ | Plan module / surface | Task(s) | Scenario |
| --- | --- | --- | --- |
| UI-001 | `export_dialog` + `export_actions` | T7D-01, T7D-04 | SC-UI-001-1 |
| UI-002 | `export_dialog` GIF options | T7D-01, T7D-04 | SC-UI-002-1 |
| UI-003 | `export_dialog` sheet options | T7D-01, T7D-04 | SC-UI-003-1 |
| UI-004 | `export_dialog` atlas options + JSON | T7D-01, T7D-04 | SC-UI-004-1 |
| UI-005 | `batch_export_panel` | T7E-02, T7E-03 | SC-UI-005-1 |
| UI-006 | `export_dialog` preset selector | T7D-02, T7D-04 | SC-UI-006-1 |
| UI-007 | `export_worker` + parity test | T7E-03 | SC-UI-007-1 |
| UI-008 | `export_actions` error surfacing | T7D-03, T7D-04 | SC-UI-008-1 |
| UI-009 | non-destructive (no undo) | T7D-03, T7D-04 | SC-UI-009-1 |
| UI-010 | `export_worker` responsiveness (§7) | T7E-01, T7E-03, T7E-04 | SC-UI-010-1 |
| UI-011 | a11y gate (§10) | TG-03 | SC-UI-011-1 |
| UI-012 | both themes (§10) | T7D-04, TG-04 | SC-UI-012-1 |
| UI-013 | i18n (`tr()` + `changeEvent`) | TG-05 | SC-UI-013-1 |

### DATA (`data/export_io.py`, `data/export_cli.py`)

| REQ | Plan module / surface | Task(s) | Scenario |
| --- | --- | --- | --- |
| DATA-001 | `export_io.write_export` (exact bytes) | T7C-02, T7C-05 | SC-D001-1 |
| DATA-002 | `export_io.write_engine_preset` | T7C-03, T7C-05 | SC-D002-1 |
| DATA-003 | `export_cli` load via IO-3 | T7C-04, T7C-05 | SC-D003-1 |
| DATA-004 | `export_io` + `build_metadata_json` | T7C-02, T7C-05 | SC-D004-1 |

## 3. Consistency findings (drift / conflict / orphan)

- **spec ↔ constitution.** No conflict. Article I (three-layer purity) upheld: all encode/pack/
  serialise is Qt-free (`logic/`+`data/`); the CLI is placed in `data/` so `check_layering` guards its
  Qt-freedom (ADR-0020); export adds no `ui/commands.py` logic. Article II upheld: 8 new numerics in
  `constants.py`, names distinct from every shipped constant (`PNG_EXPORT_COMPRESS_LEVEL` ≠
  `PROJECT_ZLIB_LEVEL`); wire-format strings + enums intrinsic-local (ADR-0001/BF-2). Article VI: export
  is batch IO, **not** the 16 ms render loop — correctly scoped as a responsiveness NFR (spec CL-16,
  plan §7/§10); no conflict with the render-budget article. Article X: every REQ traces to an S-id /
  F-finding / forward-inherited primitive. Article VII: defensive IO-3 CLI load, bounds, portable paths.
- **plan ↔ spec fidelity.** No drift. The five DEP-2 HOW decisions are adjudicated in ADR-0017..0020
  and the observable contracts (byte-reproducible, coord/pixel round-trip, engine-ready re-import,
  CLI==GUI) are preserved. `REQ-P7-DATA-*` count = spec's allocated `-001..-004` (unchanged). The
  reused primitives named in the plan (`composite_stack` CO-4, `compactor.compact` CP-1 rotation-
  disabled, `quantize.median_cut`, `project_io.load_project` IO-3, `Document`/`Frame` FR-1/DOC-1,
  `PixelBuffer` PB-1) are all verified present in the shipped tree.
- **tasks ↔ plan completeness.** No gap, no orphan. Every task names a REQ-ID or an Article gate. The
  `pyproject` `[project.scripts]` entry (T7C-07) is correctly delegated to **AGT-09** (Article IX repo/
  pyproject ownership), out of AGT-01 authoring scope — flagged, not a coverage gap. TG-01/TG-02
  (STRUCTURE + this analyze) are AGT-01 gate tasks; TG-03/04/05 map to UI-011/012/013; TG-06/07 are
  ship-process tasks.
- **Ambiguity check.** No genuine blocking ambiguity surfaced. The four "scope risks" (canonical JSON
  schema, engine artifacts, APNG, Pillow/GIF options) were named HOW decisions the spec deferred to
  AGT-01; they are now adjudicated in ADRs and the acceptance criteria (phrased around the observable
  contract) are unchanged. No SUSPEND/escalate.

## 4. Layering / cycle scripts (Article I §4, run separately by AGT-01)

`python scripts/check_layering.py` → exit **0** (clean, 36 modules); `python scripts/check_cycles.py`
→ exit **0** (no cycles, 87 modules) on the shipped tree at plan time (2026-07-04). Planned Phase-7
edges are acyclic by construction (plan §3.4); AGT-03 re-runs both when 7A/7B/7C land (T7C-06).

**FINAL-GATE re-run (2026-07-04, AGT-01, shipped tree):** `python scripts/check_layering.py` → exit
**0** (clean, **40 modules**); `python scripts/check_cycles.py` → exit **0** (no cycles, **95
modules**). All new modules verified: `logic/{export,atlas}.py` + `data/{export_io,export_cli}.py`
are zero-Qt; `ui/{export_dialog,batch_export_panel,export_worker,export_actions}.py` are the only new
Qt importers. **CLI blind-spot resolved (ADR-0020):** `data/export_cli.py` is confirmed under `data/`
(NOT a `cli/` top-level sibling that `check_layering` would leave unscanned); it imports downward only
(`data → data`: `export_io`, `project_io`; `data → logic`: `export`, `atlas`; no `logic → data`, no
Qt, no `ui`) — so the CLI stays under the Qt-freedom guard that makes CLI==GUI byte-identity
structural.

## 6. D-1 defect fixes reflected (post-implementation, this session)

Two D-1 fixes landed after the plan; both are consistent with the governing ADRs + constitution:

- **Atlas 8K-ceiling clamp / `MAX_ATLAS_DIMENSION` 8192 → 7680.** `logic/atlas.pack_atlas` clamps the
  packing bound per-axis to the *buildable* `PixelBuffer` ceiling
  (`min(max_dimension, MAX_CANVAS_WIDTH=7680)` × `min(max_dimension, MAX_CANVAS_HEIGHT=4320)`) before
  delegating to `compactor.compact` (CP-1); the constant now equals `MAX_CANVAS_WIDTH`. A former 8192
  value exceeded the 7680 width ceiling, which would let a sheet be packed wider than any buildable
  buffer. This is the **conservative align-to-8K** choice: it upholds ADR-0020 ("atlas within bounds",
  Article VI 8K ceiling) and does not alter the ADR-0017 coord/pixel round-trip. Allowing
  larger-than-canvas atlas sheets would require a `PixelBuffer`-cap change + a new ADR (AGT-03 flag) —
  deliberately deferred (Article XI extensibility hook), not taken.
- **Export-worker `finally`-emit + broadened backstop (D-1a).** `ui/export_worker.py` emits its
  terminal signal (`batchFinished` + full-progress tick) from a `finally` block so it fires on every
  exit path (completion, per-target failure, cancel, or a signal-emit failure), with a broadened
  `except Exception` UI backstop around each target's `write_export`. This makes the off-thread worker
  exception-proof and is consistent with ADR-0020's deterministic-teardown requirement (no leaked
  runnable, no segfault under `-n auto`) — it adds no encoding logic to `ui/` and no `ui/commands.py`
  undo entry.

## 5. Gate verdict (Decision AN-D1)

Unresolved-findings list is **empty** → **Branch A: PASS**. The C1 gate is **OPEN**. The orchestrator
may proceed to dispatch implementation (Slices 7A → 7B → 7C → 7D → 7E) once the Researcher's landed
grounding + these artifacts are in hand. Each implementing task must leave `check_layering` /
`check_cycles` / quality / tests green (Article IX).
