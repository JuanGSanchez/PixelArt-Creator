# ADR-0020 — Export architecture: three-layer placement, shared pure engine, headless CLI entrypoint, non-destructive contract

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-7-export` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 7's byte-identity guarantee (GUI export == CLI export, REQ-P7-LOGIC-009/-013, REQ-P7-UI-007)
holds only if the GUI dialogs and the headless CLI both drive **one** pure, deterministic, Qt-free
export engine (Article I). Architecture must rule (DEP-2, spec §8 BF-2):

1. **File placement** of the export encoders (PNG/GIF/APNG), the sprite-sheet/atlas packer + JSON
   emitter, the engine-preset writers, the shared orchestrator, and the CLI driver under the
   three-layer rule (Article I / S11), reusing `compactor.compact` (CP-1), `blend.composite_stack`
   (CO-4), `Document → frames` (FR-1/DOC-1), and the `project_io.py` defensive load (IO-3), with **no
   `logic → Qt`** import and **no new import cycle**.
2. **The CLI entrypoint's location + argument grammar** (spec §8, CL-11) — a console entrypoint in
   `pyproject` vs a module under the package — consistent with S11 (logic/data do the work; the CLI
   is a thin Qt-free headless driver).
3. **Reversibility:** confirm export adds **no** `ui/commands.py` undo logic (it is read-only IO,
   REQ-P7-UI-009 / CL-12).

A load-bearing fact about the enforcement tooling: `scripts/check_layering.py` only applies forbidden-
import rules to modules whose **top-level directory is `logic/` or `data/`** (and treats everything in
`ui/` as unrestricted). A **new top-level sibling package** (e.g. `pixelart_creator/cli/`) matches
**no** rule key and is therefore **not scanned** — it would be a layering blind spot where a stray Qt
import goes uncaught. The Qt-free CLI driver must live under a guarded layer.

## Decision

**Split the export system across the three layers so all encoding/packing/serialisation is Qt-free;
place the headless CLI driver inside `data/` (so `check_layering` keeps guarding it Qt-free); expose
the CLI as a `pyproject` console entrypoint; and add no `ui/commands.py` logic (export is
non-destructive).**

### Layer placement (Article I / S11)

- **`logic/export.py` (new, pure, zero Qt).** The export model + the deterministic pipeline: flatten
  a frame via `blend.composite_stack` (CO-4, non-destructive over `PixelBuffer` PB-1); encode a flat
  image to byte-reproducible **PNG** and a frame sequence to byte-reproducible **GIF** (Pillow →
  in-memory bytes, ADR-0019); lay out frames into a deterministic **sprite sheet**; build the
  Aseprite-JSON **metadata** (ADR-0017); the **export orchestrator** (`export_document`) and the
  **batch driver** (`run_batch`, an ordered iteration over the same pure per-target export). Encoders
  produce **in-memory bytes** — the pure engine owns the byte stream (the CLI==GUI substrate).
- **`logic/atlas.py` (new, pure, zero Qt).** Texture-atlas layout by **delegating to
  `compactor.compact` (CP-1)** — packing is never re-implemented; non-overlapping, within bounds; an
  unfit set surfaces `compactor.CompactionError` re-raised as the domain `AtlasError`; blits each
  sprite at its `Placement` into the packed buffer; regions are axis-aligned (CP-1 never rotates).
- **`logic/constants.py` (extend).** `DEFAULT_SPRITE_SHEET_COLUMNS`, `DEFAULT_ATLAS_PADDING`,
  `MAX_ATLAS_DIMENSION`, `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES` (+ the ADR-0019 encoder constants).
  The atlas caller passes `MAX_ATLAS_DIMENSION` **explicitly** to `compactor.compact` (CP-1 imports
  no constants). Names distinct from all shipped constants (Article II / BF-1).
- **`data/export_io.py` (new, Qt-free I/O).** Writes the **exact** deterministic bytes + JSON to
  portable paths (`pathlib`, `path_portability_check`) with **no re-encode** (REQ-P7-DATA-001);
  builds + writes the **engine-preset artifacts** (Unity `.meta`, Godot `SpriteFrames.tres`,
  ADR-0018) from the `logic/`-computed layout/metadata — the Phase-6 `data/tiled_io.py` precedent
  (a wire-format serialiser in `data/` over a `logic/`-computed model).
- **`data/export_cli.py` (new, Qt-free headless driver).** Parses arguments (stdlib `argparse`),
  loads the input `.pixproj` via the **defensive `project_io.load_project`** (IO-3, REQ-P7-DATA-003),
  drives the **same** `logic/export` orchestrator + `data/export_io` writer the GUI uses. It lives in
  `data/` (not a new `cli/` package) **specifically so `check_layering` keeps enforcing its Qt-
  freedom** — a `data/` module is forbidden from importing Qt or `ui/`. This is the placement ruling.
- **`ui/` (new, Qt only).** `export_dialog.py` (format picker + PNG/GIF/sheet/atlas options + engine-
  preset selector + destination chooser), `batch_export_panel.py` (multi-target one-action UI +
  per-target progress/failure), `export_actions.py` (menu/action wiring), and `export_worker.py` (the
  off-GUI-thread `QThreadPool` runner + progress/cancel signals — the DEP-3 responsiveness seam). The
  GUI adds **no** encoding/layout logic — it calls the identical `logic/`+`data/` functions the CLI
  calls (REQ-P7-UI-007). The **sole Qt file outside `ui/` remains `ui/commands.py`**, and export adds
  nothing to it.

### Layering (acyclic — verified §Grounding, gate `0`)

New one-way edges: `logic/export → logic/{atlas, blend, document, pixel_buffer, quantize,
constants}`, `logic/atlas → logic/{compactor, pixel_buffer, constants}`, `data/export_io →
logic/{export, atlas, document, constants}`, `data/export_cli → {logic/export, logic/document,
data/project_io, data/export_io, logic/constants}`, and the `ui/` export modules →
`logic/export` + `data/export_io`. None of `atlas`/`export` imports Qt or `ui/`; no module imports
`export`/`atlas` back (they are consumers of the shipped models, mirroring how `blend`/`animation`
avoid a `document` import). `data → logic` and `data → data` are permitted; `logic → data` never
appears. Acyclic by construction.

### CLI entrypoint + grammar (CL-11)

- **`pyproject` console script:** `[project.scripts]` →
  `pixelart-export = "pixelart_creator.data.export_cli:main"` (DevOps owns the pyproject edit).
- **Grammar:** `pixelart-export --input PROJECT.pixproj --format {png,gif,sprite-sheet,atlas}
  [--preset {unity,godot}] --output PATH [--columns N] [--padding N] [--loop N] [--tag NAME]
  [--json/--no-json]`. **Exit codes:** `0` success; `1` export/pack failure (`ExportError`/
  `AtlasError`); `2` bad arguments or defensive load failure (`ProjectIOError`). Because `main`
  loads via IO-3 and drives the same pure engine, its bytes equal the GUI's for the same input +
  parameters (REQ-P7-LOGIC-013).

### Reversibility (REQ-P7-UI-009 / CL-12)

Export is a **read-only IO operation**: it reads the document (flatten via CO-4 is non-destructive —
source buffers/frames/layers/tags unchanged) and writes files. It pushes **no `QUndoCommand`** and
adds **no** logic to `ui/commands.py`. Confirmed and fixed here.

## Alternatives Considered

- **CLI in a new `pixelart_creator/cli/` package.** Rejected: `check_layering.py` only guards
  `logic/`/`data/` top-level dirs — a `cli/` sibling is unscanned, so a stray `import PySide6` there
  would pass the gate. Placing the driver in `data/` keeps it under the Qt-free guard, which is the
  whole point of the CLI==GUI purity argument (REQ-P7-LOGIC-009).
- **CLI in `logic/`.** Rejected: argument parsing + reading a `.pixproj` from disk + writing files is
  IO/orchestration, not pure domain logic; `data/` (I/O + persistence) is the right layer and already
  hosts `project_io`.
- **Encoders in `data/` (bytes produced at the write boundary).** Rejected: producing the
  deterministic byte stream *is* the engine's computation and must be identical for GUI and CLI;
  keeping encode in `logic/export.py` (bytes) and `data/` as a pure byte-writer makes
  REQ-P7-DATA-001 ("write exactly the engine's bytes, no re-encode") structural.
- **A standalone `logic/sprite_metadata.py` shared by sheet + atlas.** Rejected as unnecessary
  module sprawl: the metadata builder lives in `logic/export.py`; `logic/atlas.py` returns
  `Placement`-derived rects that `export.py` folds into the one Aseprite-JSON builder (avoids an
  `atlas → export` back-edge).
- **Export as an undoable command.** Rejected: export mutates nothing (CL-12); modelling it as a
  `QUndoCommand` would be a false undo entry (Article I §2 keeps `ui/commands.py` for real mutations).

## Consequences

**Positive.** One pure Qt-free engine drives both GUI and CLI → byte-identity is structural, not
coincidental; the CLI driver stays under `check_layering`'s Qt-freedom guard; the encode/write split
makes "write exactly the engine bytes" enforceable; no false undo entry; layering stays acyclic and
green. The console entrypoint gives studios a scriptable `pixelart-export` with clean exit codes.

**Negative / risk.** Hosting a CLI driver in `data/` slightly stretches the "I/O + persistence"
framing (mitigated: a CLI *is* command-line IO, and the alternative — an unguarded `cli/` package —
is worse for Article I). The `ui/export_worker.py` off-thread runner must call only the Qt-free engine
and construct no Qt off the GUI thread (the Phase-5/6 warmer precedent); Rendering & Performance owns the responsiveness
directive (DEP-3), the UI implementation implements it. The new pyproject `[project.scripts]` entry is DevOps's edit
(out of architecture scope — flagged in tasks).

**Post-implementation note (atlas bounds, D-1 fix, 2026-07-04).** `MAX_ATLAS_DIMENSION` was aligned to
the *buildable* 8K ceiling — `MAX_ATLAS_DIMENSION = MAX_CANVAS_WIDTH = 7680` — and `logic/atlas.pack_atlas`
clamps the packing bound **per-axis** to `min(max_dimension, MAX_CANVAS_WIDTH)` × `min(max_dimension,
MAX_CANVAS_HEIGHT=4320)` before delegating to `compactor.compact` (CP-1). A former `8192` value exceeded
the 7680 width ceiling and would let a sheet be packed wider than any buildable `PixelBuffer`. The
conservative **align-to-8K** choice upholds "atlas within bounds" + the Article VI 8K ceiling and leaves
the ADR-0017 coord/pixel round-trip unchanged. Allowing larger-than-canvas atlas sheets would require a
`PixelBuffer`-cap change + a new ADR (the implementation flag) — deliberately deferred (Article XI hook), not taken.

## Grounding

- Spec `specs/phase-7-export/spec.md` §2 (layer scope), §4 (REQ-P7-LOGIC-009/-010/-013,
  REQ-P7-DATA-001/-002/-003), §7 (NEW vs REUSED; export not undoable), §8 DEP-2/DEP-3/BF-1/BF-2, §9
  Article I/VI, §10 CL-11/CL-12; `traceability.md` DEP-2/DEP-3, Article I/II watch.
- Research `docs/research-phase-7-export-20260704.md` Topic 4 (§6 single shared pure-Python code path
  = GUI==CLI; headless = no display), Topic 5 (CP-1 reuse).
- Shipped `scripts/check_layering.py` (only `logic`/`data` keys are enforced — `FORBIDDEN` map),
  `logic/compactor.py` (CP-1), `logic/blend.py` (CO-4), `logic/document.py` (FR-1/DOC-1),
  `logic/quantize.py`, `data/project_io.py` (IO-3), `ui/commands.py` (sole outside-`ui/` Qt file).
- Constitution Article I (three-layer purity + acyclic + the `ui/commands.py`-only exemption), II
  (constants + explicit atlas bounds), VI (export is batch IO, not the 16 ms render loop — DEP-3
  responsiveness), VII (defensive `.pixproj` load, portable paths), IX (pyproject/CI owned by DevOps);
  ADR-0017/0018/0019 (schema / presets / encoder options this architecture hosts).
