# Tasks — Phase 7: Export & Pipeline Integration

| Field | Value |
| --- | --- |
| Feature | `phase-7-export` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-04 |
| Over | `plan.md` (Slices 7A raster → 7B sheet/atlas → 7C presets/batch/CLI → 7D UI dialog → 7E batch UI/parity/perf) |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII); each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table (AGT-03 logic/data code,
AGT-04 logic/data tests, AGT-05 UI code, AGT-06 UI/a11y tests, AGT-07 string audit, AGT-10 perf,
AGT-08 docs, AGT-09 pyproject/CI/commits, AGT-01 architecture/analyze). One owner per task; deterministic
sub-steps name their script. Every REQ maps to ≥1 impl + ≥1 test/verify task.

---

## Slice 7A — raster + deterministic pipeline (`constants.py`, `export.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T7A-01 | Add the 8 Phase-7 numerics (`DEFAULT_SPRITE_SHEET_COLUMNS=8`, `DEFAULT_ATLAS_PADDING=0`, `MAX_ATLAS_DIMENSION=8192`, `MAX_BATCH_TARGETS=256`, `MAX_EXPORT_FRAMES=4096`, `PNG_EXPORT_COMPRESS_LEVEL=6`, `GIF_DEFAULT_LOOP_COUNT=0`, `GIF_FRAME_DISPOSAL=2`) with citations. **Names DISTINCT from every shipped constant (BF-1); `PNG_EXPORT_COMPRESS_LEVEL` ≠ `PROJECT_ZLIB_LEVEL=9`.** | AGT-03 | `logic/constants.py` | — | LOGIC-012 / SC-L012-1 / plan §8 | todo |
| T7A-02 | `logic/export.py` (new): `ExportFormat`/`EnginePreset` enums (module-local vocabulary); `SpriteRect`/`SheetMetadata`/`ExportRequest`/`ExportResult`/`TagInfo` dataclasses; `ExportError`. `flatten_frame` via `blend.composite_stack` (CO-4), **non-destructive** (source buffers byte-for-byte unchanged; compositing not re-implemented). Zero Qt. | AGT-03 | `logic/export.py` | T7A-01 | LOGIC-001 / SC-L001-1 | todo |
| T7A-03 | `encode_png` — byte-reproducible PNG (ADR-0019: `optimize=False`, `compress_level=PNG_EXPORT_COMPRESS_LEVEL`, no `pnginfo`/`exif`/`icc_profile`/`dpi`/`tIME`) → in-memory bytes. | AGT-03 | `logic/export.py` | T7A-02 | LOGIC-003 / SC-L003-1 | todo |
| T7A-04 | `encode_gif` — byte-reproducible animated GIF: fixed shared palette via `logic/quantize.median_cut` (reused, deterministic) → per-frame `convert("P", dither=NONE)` → `save(save_all, duration=[duration_ms…], loop, disposal, optimize=False, palette=…)`; single-frame source → single image. | AGT-03 | `logic/export.py` | T7A-03 | LOGIC-004 / SC-L004-1 | todo |
| T7A-05 | Determinism backbone: assert `export_document` stages use **no** wall-clock/randomness/locale/unordered iteration; frames iterated in explicit index order; `MAX_EXPORT_FRAMES` bound (ExportError past it). | AGT-03 | `logic/export.py` | T7A-04 | LOGIC-002, 012 / SC-L002-1, SC-L012-1 | todo |
| T7A-06 | Unit + property tests (headless): flatten == `composite_stack` + non-destructive; PNG byte-reproducible (export twice → `hashlib`-equal); GIF byte-reproducible + per-frame delays reflect `duration_ms`; pipeline pure/deterministic (no time/random/locale); bounds + defaults from constants. **CI byte-diff (F-1): no volatile PNG chunk.** | AGT-04 | `tests/logic/test_export.py` | T7A-05 | LOGIC-001, 002, 003, 004, 012 / SC-L001-1, L002-1, L003-1, L004-1, L012-1 | todo |

## Slice 7B — sprite-sheet + atlas + JSON metadata (`export.py`, `atlas.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T7B-01 | `build_sprite_sheet` — deterministic **row-major** grid (columns from `DEFAULT_SPRITE_SHEET_COLUMNS`, `DEFAULT_ATLAS_PADDING`); flat sheet image + `SheetMetadata`; encode byte-reproducibly (reuses `encode_png`). Identical inputs → identical sheet + bytes. | AGT-03 | `logic/export.py` | T7A-05 | LOGIC-005 / SC-L005-1 | todo |
| T7B-02 | `logic/atlas.py` (new): `pack_atlas(sprites, *, padding, max_dimension) -> AtlasResult`; inflate rects by padding → **delegate to `compactor.compact` (CP-1)** passing `max_dimension` explicitly (CP-1 imports no constants); blit each sprite at its `Placement` (axis-aligned); non-overlapping + within bounds; unfit → `AtlasError` wrapping `CompactionError`. Packing NOT re-implemented. Zero Qt; no `document` import. | AGT-03 | `logic/atlas.py` | T7A-01 | LOGIC-006 / SC-L006-1 | todo |
| T7B-03 | `build_metadata_json` — Aseprite Array layout (`frames[]` + `meta.frameTags[]`); `rotated` const `false`; trim off (`trimmed=false`, `spriteSourceSize==sourceSize`); Phase-5 `frame_tags`/`duration_ms` → `frameTags`/`duration`; `json.dumps(sort_keys, separators=(",",":"))`, integer coords, no timestamp (ADR-0017). Coords == blitted placements. | AGT-03 | `logic/export.py` | T7B-02 | LOGIC-007, 008 / SC-L007-1, SC-L008-1 | todo |
| T7B-04 | Tests: sheet deterministic + byte-reproducible + row-major; atlas non-overlap via CP-1 (pairwise rect-intersection) + unfit → `AtlasError`; JSON coord/pixel **round-trip** (crop each rect from the image == source pixels) via Hypothesis; metadata deterministic (byte-identical twice) + complete (every sprite described). | AGT-04 | `tests/logic/test_export.py`, `tests/logic/test_atlas.py` | T7B-03 | LOGIC-005, 006, 007, 008 / SC-L005-1, L006-1, L007-1, L008-1 | todo |

## Slice 7C — presets + batch + headless CLI (`export.py`, `data/export_io.py`, `data/export_cli.py`) — Qt-free

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T7C-01 | `export_document` orchestrator (single shared pure entrypoint the GUI + CLI both call) + `run_batch` (ordered iteration; each output byte-identical to its single export; `MAX_BATCH_TARGETS` bound; per-target failure isolated, other outputs uncorrupted). | AGT-03 | `logic/export.py` | T7B-03 | LOGIC-009, 010 / SC-L009-1, SC-L010-1 | todo |
| T7C-02 | `data/export_io.py` (new): `write_export` — write **exact** `image_bytes` + `metadata_json` verbatim (NO re-encode; byte-reproducibility preserved); portable paths (`pathlib`). Zero Qt. | AGT-03 | `data/export_io.py` | T7C-01 | DATA-001, 004 / SC-D001-1, SC-D004-1 | todo |
| T7C-03 | `data/export_io.py` engine-preset writers: `write_engine_preset(UNITY,…)` → Unity 2022.3 `.meta` (Multiple sprite mode; populated `spriteSheet.sprites[]`; y-up rect flip; Point filter; uncompressed); `write_engine_preset(GODOT,…)` → Godot 4.2 `SpriteFrames.tres` (`AtlasTexture` region per frame; animations from `frameTags`). Deterministic, portable, rotation-free (ADR-0018). Version strings module-local. | AGT-03 | `data/export_io.py` | T7C-02 | LOGIC-011, DATA-002 / SC-L011-1, SC-D002-1 | todo |
| T7C-04 | `data/export_cli.py` (new): `main(argv)` — `argparse` grammar (`--input/--format/--preset/--output/--columns/--padding/--loop/--tag/--json`); load `.pixproj` via **`project_io.load_project`** (IO-3 defensive → `ProjectIOError`); drive the SAME `logic/export`+`data/export_io`; exit 0 ok / 1 `ExportError`|`AtlasError` / 2 bad-args|`ProjectIOError`. Placed in `data/` (Qt-free, guarded by `check_layering`). | AGT-03 | `data/export_cli.py` | T7C-02 | LOGIC-013, DATA-003 / SC-L013-1, SC-D003-1 | todo |
| T7C-05 | Tests (headless): each batch output == its single export + per-target failure isolation; engine-preset artifacts written deterministically + portably (Unity/Godot golden-file); CLI==GUI byte-identity for a fixed `.pixproj` (`export_document` bytes == CLI-written bytes); defensive CLI load (malformed/out-of-bounds/unknown-version → `ProjectIOError`, valid == GUI `Document`); `path_portability_check` over new `data/` paths. | AGT-04 | `tests/logic/test_export.py`, `tests/data/test_export_io.py`, `tests/data/test_export_cli.py` | T7C-04 | LOGIC-009, 010, 011, 013, DATA-001..004 / SC-L009-1..L013-1, SC-D001-1..D004-1 | todo |
| T7C-06 | Run `python scripts/check_layering.py` + `python scripts/check_cycles.py`; confirm `export → atlas → compactor`, `export → blend`/`document`/`quantize`/`animation`, `data/export_io`/`export_cli` downward-only, all Qt-free, no `logic → data` edge, no cycle. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T7C-04 | Article I / plan §11 | todo |
| T7C-07 | Add the `pyproject` console entrypoint `[project.scripts]` `pixelart-export = "pixelart_creator.data.export_cli:main"`. **AGT-09 owns pyproject (Article IX).** | AGT-09 | `pyproject.toml` | T7C-04 | LOGIC-013 (entrypoint) | todo |

## Slice 7D — export UI (dialog, options, presets) — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T7D-01 | `Export_Dialog(QDialog)`: format picker (PNG/GIF/sprite-sheet/atlas) + per-format options (GIF frame-source/loop; sheet columns/rows/padding — defaults from constants, reject out-of-range; atlas padding/max-dim + JSON metadata toggle); portable destination chooser; `tr()` + `changeEvent` retranslate. Drives `logic/export`+`data/export_io` (no encode/layout logic of its own). | AGT-05 | `ui/export_dialog.py`, `ui/main_window.py` | T7C-06 | UI-001, 002, 003, 004, 013 / SC-UI-001-1..004-1 | todo |
| T7D-02 | Engine-preset selector (Unity/Godot) driving `write_engine_preset`; translatable labels. | AGT-05 | `ui/export_dialog.py` | T7D-01 | UI-006 / SC-UI-006-1 | todo |
| T7D-03 | `ui/export_actions.py`: Export menu/toolbar actions; surface `ExportError`/`AtlasError`/`ProjectIOError` + unwritable-path as **user-facing** errors (no crash, no partial/corrupt file left as valid); confirm export is **non-destructive** (no `QUndoCommand`, no `ui/commands.py` change). | AGT-05 | `ui/export_actions.py`, `ui/main_window.py` | T7D-01 | UI-008, 009 / SC-UI-008-1, SC-UI-009-1 | todo |
| T7D-04 | pytest-qt tests (both themes, offscreen): format/options/destination → file via engine; GIF options (frame source/loop; durations honoured); sheet options (columns/rows/padding; reject OOR); atlas options (padding/max-dim + JSON toggle; coords match); preset selection; graceful export error; non-destructive + no undo pushed. | AGT-06 | `tests/ui/test_export_dialog.py` | T7D-03 | UI-001..004, 006, 008, 009, 012, 013 / SC-UI-001-1..004-1, 006-1, 008-1, 009-1 | todo |

## Slice 7E — batch UI + headless parity + responsiveness — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T7E-01 | `ui/export_worker.py`: `Export_Worker(QRunnable)` on a window-owned `QThreadPool` + signals; calls the **Qt-free** `logic/export`+`data/export_io` off the GUI thread; progress/result/error over queued GUI-thread signals; cooperative cancel; **no Qt constructed off-thread** (Phase-5/6 warmer precedent). Implements the AGT-10 responsiveness directive (DEP-3). | AGT-05 | `ui/export_worker.py` | T7D-01 | UI-010 / SC-UI-010-1 | todo |
| T7E-02 | `Batch_Export_Panel(QWidget)`: select multiple targets/formats; one-action export via `export.run_batch` on the worker; per-target progress; per-target failure reported without aborting the rest. `tr()` + `changeEvent`. | AGT-05 | `ui/batch_export_panel.py`, `ui/main_window.py` | T7E-01 | UI-005, 013 / SC-UI-005-1 | todo |
| T7E-03 | pytest-qt tests (both themes): batch exports multiple targets in one action + per-target progress/failure isolation; **GUI export == CLI export byte-for-byte** (drive `export_document` via the GUI worker and via `data/export_cli.main`, assert identical bytes); UI stays responsive (processes events / cancel) during a large+batch export (behavioural — NOT the 16 ms budget). | AGT-06 | `tests/ui/test_export_batch_ui.py`, `tests/ui/test_export_parity.py` | T7E-02 | UI-005, 007, 010 / SC-UI-005-1, 007-1, 010-1 | todo |
| T7E-04 | (If warranted) responsiveness/throughput profile for a large (8K) / big-batch export; over-budget → an AGT-10 directive (chunked progress / worker tuning), **never** a 16 ms-budget claim (export is batch IO, not the render loop). | AGT-10 | `scripts/perf_profile.py` (invoke) | T7E-01 | UI-010 (NFR) / SC-UI-010-1 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-7 `export.py`/`atlas.py` + `constants.py` extension, the new `data/export_io.py`/`export_cli.py`, and the new `ui/` export modules (marked PLANNED per house convention). | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; zero unresolved findings before implement. | AGT-01 | `specs/phase-7-export/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | a11y audit (`a11y-audit`): accessible names/descriptions, keyboard reachability + logical tab order, visible focus on every export control (format picker, GIF/sheet/atlas option fields, preset selector, batch-target list, destination chooser, export/cancel buttons). | AGT-06 | `tests/ui/*` | T7D-04, T7E-03 | UI-011 / SC-UI-011-1 | todo |
| TG-04 | Both-theme render verification (role-based colours) across the export dialog / option panels / batch UI / progress + error surfaces. | AGT-06 | `tests/ui/*` | T7D-04, T7E-03 | UI-012 / SC-UI-012-1 | todo |
| TG-05 | String audit (`string_audit_check`): zero unwrapped user-visible strings (format names, option labels + units, preset names, batch labels, progress text, dialog titles, error messages); `changeEvent` retranslate on hand-built widgets. | AGT-07 | `ui/*.py` | T7D-03, T7E-02 | UI-013 / SC-UI-013-1 | todo |
| TG-06 | CHANGELOG (`Unreleased`) entries for Phase-7 features tied to REQ-IDs. | AGT-08 | `docs/CHANGELOG.md` | 7A/7B/7C/7D/7E done | Article IX | todo |
| TG-07 | `sdd-checklist` before ship: every REQ has a passing test; byte-repro + round-trip + CLI==GUI green; both themes + a11y + i18n gates green. | AGT-06 | checklist report | all impl+test done | Article IV/V | todo |
