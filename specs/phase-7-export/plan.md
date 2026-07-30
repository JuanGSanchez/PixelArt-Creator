# Plan — Phase 7: Export & Pipeline Integration

| Field | Value |
| --- | --- |
| Feature | `phase-7-export` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 7 before any `logic/export.py`, `logic/atlas.py`, `data/export_io.py`, `data/export_cli.py`, or export UI exists. The `PixelBuffer` source pixels (PB-1), `blend.composite_stack` (CO-4), the `Document → frames` tree + `Frame.duration_ms` (FR-1), the deterministic `logic/compactor.py` MaxRects packer (CP-1, rotation disabled), the shipped deterministic `logic/quantize.median_cut`, and the defensive `data/project_io.py` load (IO-3) are **shipped** and reused, not re-authored. |
| Over spec | `specs/phase-7-export/spec.md` (REQ-P7-LOGIC-001..013, REQ-P7-UI-001..013, REQ-P7-DATA-001..004) + `traceability.md` |
| Stack source | S8 (fixed) — no new technology. Domain internals (deterministic Pillow PNG/GIF options, the sprite-sheet/atlas JSON schema, Unity/Godot import-artifact conventions, APNG feasibility, MaxRects rotation semantics) are **grounded** by The Researcher (`docs/research-phase-7-export-20260704.md`, **landed**) → PL7-D1 Branch B (no RESEARCH REQUEST). |
| ADRs filed | **ADR-0017** (canonical sprite-sheet/atlas JSON: Aseprite-compatible Array layout, rotation-free, trim-off default, Phase-5 `frameTags`+`duration` map-in); **ADR-0018** (engine presets: Unity `.meta` pinned 2022.3 LTS + Godot `SpriteFrames.tres` pinned 4.2, rotation-free, deterministic); **ADR-0019** (raster encoder options + same-environment byte-reproducibility scope + APNG deferral + GIF fixed-shared-palette via `logic/quantize`); **ADR-0020** (export architecture: three-layer placement, shared pure engine, headless CLI in `data/` + `pyproject` console entrypoint, non-destructive contract) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-7 spec — the
**production-pipeline** milestone that turns the shipped compositing/packing/document primitives into
byte-reproducible **PNG / GIF / sprite-sheet / atlas + JSON** export, **batch**, **Unity/Godot engine
presets**, and a **headless CLI** whose output is byte-identical to the GUI. It maps every REQ to its
S11 layer, **freezes the public interface** of the new `logic/export.py`, `logic/atlas.py`,
`data/export_io.py`, and `data/export_cli.py` before implementation so the DATA and UI slices bind to
a stable contract, rules the five **DEP-2** HOW decisions (canonical JSON schema, engine-preset
artifacts, APNG scope, Pillow/GIF encoder options, CLI entrypoint/grammar) in
**ADR-0017/0018/0019/0020**, routes the **DEP-3** export-responsiveness NFR to AGT-10/AGT-05, places
all new numerics in `logic/constants.py` with names **distinct from every shipped constant** (Article
II / BF-1), and commits the layering so `check_layering`/`check_cycles` stay green (both exit `0` at
plan time — §11). It is decomposed into dependency-ordered work items in `tasks.md`.

No new stack/library/API is introduced (**PL7-D1 → Branch B**: the stack is fixed by S8; the Pillow
option set, GIF palette approach, JSON schema, engine-artifact conventions and MaxRects rotation
semantics are **grounded, not invented** — `docs/research-phase-7-export-20260704.md` has landed). The
`sdd-analyze` C1 gate is run over constitution/spec/plan/tasks as the pre-implement gate (Article
VIII; see `analyze-report.md`).

## 2. Stack / domain decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language / stack | Python 3.12+; Pillow (shipped dep, `Pillow>=10.0`) for raster encode; NumPy for buffers; stdlib `argparse`/`json` for the CLI | S8 |
| Flatten source | Each export image is a frame flattened via `blend.composite_stack` (CO-4) over `PixelBuffer` source pixels (PB-1); compositing is **not** re-implemented; **non-destructive** | REQ-P7-LOGIC-001; CO-4/PB-1 |
| PNG encode | Pillow `save(format="PNG", optimize=False, compress_level=PNG_EXPORT_COMPRESS_LEVEL)`; **no** `pnginfo`/`exif`/`icc_profile`/`dpi`/`tIME` → byte-reproducible | REQ-P7-LOGIC-003; ADR-0019; research §1.1, F-1 |
| GIF encode | Fixed shared palette via `logic/quantize.median_cut` (deterministic, reused) → per-frame `convert("P", dither=NONE)` → `save(save_all, duration=[duration_ms…], loop=GIF_DEFAULT_LOOP_COUNT, disposal=GIF_FRAME_DISPOSAL, optimize=False, palette=…)` | REQ-P7-LOGIC-004; ADR-0019; research §1.2, §4.4 |
| Animated format scope | **GIF** now; **APNG deferred** (Art. XI hook on the `ExportFormat` seam) | CL-8; ADR-0019; research Open-4 |
| Sprite-sheet layout | Deterministic **row-major grid**; columns default `DEFAULT_SPRITE_SHEET_COLUMNS`; inter-frame `DEFAULT_ATLAS_PADDING`; frame source = FR-1 sequence (whole doc or a tag) | REQ-P7-LOGIC-005; CL-5; ADR-0017 |
| Atlas packing | **Delegate to `compactor.compact` (CP-1)** — MaxRects BSSF, **rotation disabled**; non-overlapping; caller passes `MAX_ATLAS_DIMENSION`; unfit → `CompactionError` re-raised as `AtlasError` | REQ-P7-LOGIC-006; CL-4/CL-15; CP-1 |
| JSON schema | **Aseprite-compatible Array layout** (`frames[]` + `meta.frameTags[]`); `rotated` always `false`; trim OFF (`trimmed=false`, `spriteSourceSize==sourceSize`); Phase-5 `frame_tags`/`duration_ms` map in | REQ-P7-LOGIC-007/-008; ADR-0017; research Topic 2 |
| JSON determinism | `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",",":"))` over **integer** coords; no timestamp/`generated-on`; `meta.version` a fixed string | REQ-P7-LOGIC-008; ADR-0017/0019 |
| Engine presets | **Unity** → PNG + `.meta` YAML (pinned 2022.3 LTS, populated `spriteSheet.sprites[]`, y-up rect flip, Point filter, uncompressed); **Godot** → PNG + `SpriteFrames.tres` (pinned 4.2, `AtlasTexture` region per frame, animations from `frameTags`); both rotation-free, deterministic | REQ-P7-LOGIC-011, REQ-P7-DATA-002; ADR-0018; research Topic 3 |
| Byte-repro scope | **Same-environment** byte-identity (across runs + GUI/CLI); CI pins Pillow/zlib so the byte-diff is stable; cross-machine not promised | REQ-P7-LOGIC-002/-003/-004/-005; CL-3/CL-14; ADR-0019 |
| Batch | Ordered iteration over the **same pure per-target export**; each output byte-identical to its single export; bounded by `MAX_BATCH_TARGETS`; per-target failure isolated | REQ-P7-LOGIC-010; CL-10; ADR-0020 |
| CLI | Qt-free `data/export_cli.py`; `pyproject` console script `pixelart-export`; loads `.pixproj` via IO-3; drives the **same** `logic/export`+`data/export_io`; exit 0/1/2 | REQ-P7-LOGIC-013, REQ-P7-DATA-003; CL-11; ADR-0020 |
| CLI==GUI identity | Single shared pure engine in `logic/`+`data/` (zero Qt); the GUI adds no encode/layout logic; both call the identical functions → identical bytes | REQ-P7-LOGIC-009, REQ-P7-UI-007; ADR-0020 |
| Output write | `data/export_io.py` writes **exactly** the engine bytes + JSON (no re-encode) to **portable** paths (`pathlib`, `path_portability_check`); writes engine artifacts | REQ-P7-DATA-001/-002; IO-3; ADR-0020 |
| Reversibility | Export is **read-only / non-destructive**; **no `QUndoCommand`**, **no `ui/commands.py`** change | REQ-P7-UI-009; CL-12; ADR-0020 |
| Responsiveness | `ui/export_worker.py` runs the Qt-free engine on a `QThreadPool` worker with progress/cancel; **not** the 16 ms frame budget (export is batch IO) | REQ-P7-UI-010; DEP-3; §7; ADR-0020 |
| Testing | pytest + Hypothesis (logic/data, headless — byte-diff/round-trip/determinism), pytest-qt both themes (UI) | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-7 logic/data decision places Qt in `logic/` or `data/` (**PL7-D2 → Branch B held**). All
export dialogs / batch UI / preset selection / progress / the export worker live only in `ui/`; the
sole Qt file outside `ui/` remains `ui/commands.py`, and **export adds nothing to it** (it is not an
undoable command).

## 3. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`) and acyclic (verified §11). The new Qt-free
logic edges are `export → atlas`, `export → blend`, `export → document`, `atlas → compactor` (never
the reverse — §3.4).

### 3.1 New / extended `logic/` modules (Slices 7A/7B — pure, zero Qt)

| Module | Change | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | Add `DEFAULT_SPRITE_SHEET_COLUMNS`, `DEFAULT_ATLAS_PADDING`, `MAX_ATLAS_DIMENSION`, `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES`, `PNG_EXPORT_COMPRESS_LEVEL` (6, distinct from `PROJECT_ZLIB_LEVEL=9`), `GIF_DEFAULT_LOOP_COUNT` (0), `GIF_FRAME_DISPOSAL` (2) — leaf, no imports. **Names distinct from every shipped constant (BF-1).** | — | LOGIC-012 |
| `export.py` | **new** | `ExportFormat`/`EnginePreset` enums (module-local vocabulary, BF-2); `ExportRequest`/`ExportResult`/`SpriteRect`/`SheetMetadata` dataclasses; `flatten_frame` (CO-4, non-destructive); `encode_png` / `encode_gif` → byte-reproducible in-memory bytes (Pillow, ADR-0019); `build_sprite_sheet` (deterministic row-major); `build_metadata_json` (Aseprite Array, ADR-0017); `export_document` orchestrator; `run_batch` (ordered pure iteration). Bounds from constants; `ExportError`. Zero Qt. | `atlas`, `blend` (`composite_stack`), `document` (`Document`/`Frame`), `pixel_buffer`, `quantize` (`median_cut`), `animation` (`FrameTag`/`PlaybackMode` for tag→direction), `constants` | LOGIC-001..005, 008, 010, 011, 012 |
| `atlas.py` | **new** | `pack_atlas(sprites, *, padding, max_dimension) -> AtlasResult`: inflate rects by padding → **delegate to `compactor.compact` (CP-1)** → blit each sprite at its `Placement` (axis-aligned; CP-1 never rotates) → `AtlasResult(image, placements, width, height)`; unfit → `AtlasError` (wraps `CompactionError`). Does **not** re-implement packing. Zero Qt; no `document` import. | `compactor` (`compact`, `CompactionError`), `pixel_buffer`, `constants` | LOGIC-006, 007 |

`constants.py` stays a leaf. The Pillow enum values (`Dither.NONE`) + format strings, the Aseprite/
engine wire-format version strings, and the `ExportFormat`/`EnginePreset` enums are **module-local**
(ADR-0001 exemption / BF-2 enumerated vocabulary — the `BlendMode`/`PlaybackMode` precedent). The
metadata builder lives in `export.py` (not a separate module) so `atlas.py` never imports `export`
(no back-edge): `atlas` returns `Placement`-derived rects and `export` folds them into the one
Aseprite-JSON builder.

### 3.2 New / extended `data/` modules (Slice 7C — Qt-free I/O; DEP-2)

| Module | Change | Responsibility | Depends on | REQ |
| --- | --- | --- | --- | --- |
| `export_io.py` | **new** | Write the **exact** engine bytes + JSON to portable paths (`pathlib`, `path_portability_check`) with **no re-encode** (byte-reproducibility preserved through the write); build + write the **engine-preset artifacts** — Unity `.meta` (pinned 2022.3 LTS) + Godot `SpriteFrames.tres` (pinned 4.2) — from the `logic/`-computed layout/metadata (ADR-0018). Version strings module-local (ADR-0001). Zero Qt. | `logic/export` (`ExportResult`/`SheetMetadata`/`SpriteRect`), `logic/atlas` (`AtlasResult`), `constants` | DATA-001, 002, 004 |
| `export_cli.py` | **new** | Headless CLI driver (Qt-free): `argparse` grammar `pixelart-export --input … --format … [--preset …] --output … [--columns/--padding/--loop/--tag …]`; load `.pixproj` via **`project_io.load_project`** (IO-3, defensive); drive the **same** `logic/export`+`data/export_io`; exit 0 ok / 1 export-or-pack error / 2 bad-args-or-`ProjectIOError`. Placed in `data/` so `check_layering` guards its Qt-freedom (ADR-0020). | `logic/export`, `logic/document`, `data/project_io` (`load_project`, `ProjectIOError`), `data/export_io`, `constants` | DATA-003, LOGIC-013 |

The `pyproject` `[project.scripts]` entry `pixelart-export = "pixelart_creator.data.export_cli:main"`
is an **AGT-09** edit (repo/pyproject ownership, Article IX) — flagged in `tasks.md`, not authored
here.

### 3.3 New `ui/` modules (Slices 7D/7E — Qt only)

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `export_dialog.py` | **new** | `Export_Dialog(QDialog)`: format picker (PNG/GIF/sprite-sheet/atlas); per-format options (GIF frame-source/loop; sheet columns/rows/padding — defaults from constants, reject out-of-range; atlas padding/max-dim + JSON toggle); engine-preset selector (Unity/Godot); portable destination chooser; `tr()` + `changeEvent` retranslate. Drives `logic/export`+`data/export_io`. | `export`, `data/export_io`, `constants` | UI-001, 002, 003, 004, 006, 008, 011, 012, 013 |
| `batch_export_panel.py` | **new** | `Batch_Export_Panel(QWidget)`: select multiple targets/formats; one-action export via `export.run_batch`; per-target progress; a per-target failure reported without aborting the rest. | `export.run_batch`, `export_worker` | UI-005, 010, 013 |
| `export_worker.py` | **new** | `Export_Worker` (`QRunnable` on a scene/window-owned `QThreadPool`) + signals: calls the **Qt-free** `logic/export`+`data/export_io` off the GUI thread, emits progress/result/error over queued signals; cooperative cancel flag; **constructs no Qt off-thread** (Phase-5/6 warmer precedent). Implements the AGT-10 responsiveness directive (DEP-3). | `export`, `data/export_io` | UI-010 |
| `export_actions.py` | **new** | Menu/toolbar actions opening the dialog / batch panel; wires the destination + engine-preset selection; surfaces `ExportError`/`AtlasError`/`ProjectIOError` as user-facing messages (no crash, no partial file left as valid). `tr()` strings. | `export_dialog`, `batch_export_panel` | UI-001, 007, 008, 013 |
| `main_window.py` | extend | Add the Export menu + actions; hold the active document + chosen parameters (view state); wire the export dialog/batch panel/worker. **No new `ui/commands.py` logic** (export is non-destructive). | `document`, the new export UI | UI-001, 005, 009 |

### 3.4 Layering proof (PL7-D3 — cycle-free by construction)

New intra-`logic/` edges: `export → atlas`, `export → blend`, `export → document`,
`export → quantize`, `export → animation`, `atlas → compactor`. None of `atlas`/`export` imports
`ui/` or Qt; **no module imports `export`/`atlas` back** — they are *consumers* of the shipped models,
exactly as `blend.py`/`animation.py` avoid a `document` import. The metadata builder stays in
`export.py` so `atlas → export` never appears. `data/export_io` and `data/export_cli` import
**downward** (`data → logic`) and sideways (`data → data`: `export_cli → project_io`/`export_io`),
never `logic → data`. Resulting one-way chain:

```
ui/export_*  →  data/export_io   →  logic/export  →  logic/atlas   →  logic/compactor
             →  data/export_cli  →  data/project_io                →  logic/pixel_buffer
                                  →  logic/export  →  logic/blend   →  logic/color, logic/constants
                                                   →  logic/document, logic/quantize, logic/animation
```

No back-edge (`atlas/export → document`-importing-`export`, `logic → data`, or any
`logic/`/`data/` → `ui/`) exists. `check_layering` + `check_cycles` therefore stay `0` (verified §11
on the shipped tree; the planned edges are acyclic by design and re-verified when 7A/7B/7C land).

## 4. `logic/export.py` — frozen interface contract (Slices 7A/7B)

Frozen **before** implementation so 7C/7D bind to a stable surface. Qt-free. `ExportError` subclasses
`ValueError` (Phase-1 convention). `ExportFormat`/`EnginePreset` are module-local enumerated
vocabulary (BF-2).

```python
class ExportError(ValueError): ...

class ExportFormat(Enum):            # module-local vocabulary
    PNG; GIF; SPRITE_SHEET; ATLAS

class EnginePreset(Enum):
    NONE; UNITY; GODOT

@dataclass(frozen=True)
class SpriteRect:
    name: str
    x: int; y: int; w: int; h: int           # rect on the sheet/atlas (integers)
    source_w: int; source_h: int             # sourceSize (untrimmed)
    offset_x: int; offset_y: int             # spriteSourceSize offset (0 when trim off)
    duration_ms: int

@dataclass(frozen=True)
class SheetMetadata:
    image_name: str
    width: int; height: int
    frames: Tuple[SpriteRect, ...]
    tags: Tuple["TagInfo", ...]              # {name, from, to, direction} from FR-1 frame_tags

@dataclass(frozen=True)
class ExportRequest:
    fmt: ExportFormat
    preset: EnginePreset = EnginePreset.NONE
    columns: int = DEFAULT_SPRITE_SHEET_COLUMNS
    padding: int = DEFAULT_ATLAS_PADDING
    max_dimension: int = MAX_ATLAS_DIMENSION
    loop: int = GIF_DEFAULT_LOOP_COUNT
    tag: Optional[str] = None                # None = whole document
    emit_json: bool = True

@dataclass(frozen=True)
class ExportResult:
    image_bytes: bytes                       # PNG/GIF/sheet/atlas image, exact bytes
    image_name: str
    metadata_json: Optional[str]             # deterministic Aseprite JSON (sheet/atlas) or None
    metadata: Optional[SheetMetadata]        # structured form for the engine-preset writers

def flatten_frame(frame: Frame, width: int, height: int) -> PixelBuffer:
    """Flatten one frame's visible layer stack via blend.composite_stack (CO-4). Non-destructive
    (source buffers unchanged). REQ-P7-LOGIC-001."""

def encode_png(image: PixelBuffer) -> bytes:
    """Byte-reproducible PNG (ADR-0019: optimize=False, pinned compress_level, no volatile chunks).
    REQ-P7-LOGIC-003."""

def encode_gif(frames: Sequence[PixelBuffer], durations: Sequence[int], *,
               loop: int = GIF_DEFAULT_LOOP_COUNT) -> bytes:
    """Byte-reproducible animated GIF: fixed shared palette (quantize.median_cut), dither=NONE,
    per-frame duration from durations (FR-1). REQ-P7-LOGIC-004."""

def build_sprite_sheet(frames: Sequence[PixelBuffer], *, columns: int = DEFAULT_SPRITE_SHEET_COLUMNS,
                       padding: int = DEFAULT_ATLAS_PADDING) -> Tuple[PixelBuffer, SheetMetadata]:
    """Deterministic row-major grid; MAX_EXPORT_FRAMES bound (ExportError past it). REQ-P7-LOGIC-005."""

def build_metadata_json(meta: SheetMetadata) -> str:
    """Aseprite Array layout, sort_keys, fixed separators, integer coords, no timestamp
    (ADR-0017). REQ-P7-LOGIC-007/-008."""

def export_document(document: Document, request: ExportRequest) -> ExportResult:
    """The single shared pure orchestrator the GUI and CLI both call. Flatten (CO-4) → encode/lay out
    → build metadata. Deterministic (REQ-P7-LOGIC-002); Qt-free (REQ-P7-LOGIC-009)."""

def run_batch(document: Document, requests: Sequence[ExportRequest]) -> Tuple[ExportResult, ...]:
    """Ordered iteration over export_document; each result byte-identical to its single export;
    MAX_BATCH_TARGETS bound; per-target ExportError surfaced without corrupting others.
    REQ-P7-LOGIC-010."""
```

## 5. `logic/atlas.py` — frozen contract (Slice 7B)

```python
class AtlasError(ValueError): ...

@dataclass(frozen=True)
class AtlasResult:
    image: PixelBuffer
    placements: Tuple[SpriteRect, ...]       # rotated is ALWAYS false (CP-1 rotation disabled)
    width: int; height: int

def pack_atlas(sprites: Sequence[Tuple[str, PixelBuffer]], *,
               padding: int = DEFAULT_ATLAS_PADDING,
               max_dimension: int = MAX_ATLAS_DIMENSION) -> AtlasResult:
    """Inflate each sprite rect by `padding`, DELEGATE to compactor.compact (CP-1, MaxRects BSSF,
    rotation disabled) passing max_dimension explicitly (CP-1 imports no constants), blit each sprite
    at its Placement (axis-aligned). Placements are non-overlapping + within bounds; the JSON coords
    (built by export.build_metadata_json from these rects) MATCH the blitted pixels (REQ-P7-LOGIC-007).
    A set that cannot fit raises AtlasError wrapping compactor.CompactionError (REQ-P7-LOGIC-006 —
    never a silent overlap/truncation). Packing is NOT re-implemented (Article I)."""
```

**Notes.** `atlas.py` needs no `document`/Qt import (PL7-D3): it operates on `(id, PixelBuffer)`
sprites the orchestrator already flattened (CO-4), and delegates placement to CP-1. Because CP-1 has
no `allowFlip` and its `Placement` carries no rotation flag, every region is axis-aligned and the JSON
`rotated` field is a constant `false` (ADR-0017) — no rotation-derivation is needed.

## 6. `data/` contracts — output/artifact write (`export_io.py`) + CLI (`export_cli.py`)

```python
# data/export_io.py — writes exactly the engine bytes; Qt-free; portable paths
def write_export(result: ExportResult, out_path: PathLike) -> None:
    """Write result.image_bytes + (if present) result.metadata_json verbatim — NO re-encode
    (byte-reproducibility preserved, REQ-P7-DATA-001). pathlib; path_portability_check-clean."""

def write_engine_preset(preset: EnginePreset, meta: SheetMetadata, image_path: PathLike) -> None:
    """UNITY → a Unity 2022.3 .meta beside the PNG (Multiple sprite mode; populated
    spriteSheet.sprites[] with y-up rects, Point filter, uncompressed); GODOT → a Godot 4.2
    SpriteFrames .tres (AtlasTexture region per frame; animations grouped by frameTags). Deterministic,
    portable (REQ-P7-DATA-002, ADR-0018)."""

# data/export_cli.py — headless, Qt-free; the pyproject console entrypoint target
def main(argv: Optional[Sequence[str]] = None) -> int:
    """pixelart-export --input P.pixproj --format {png,gif,sprite-sheet,atlas} [--preset {unity,godot}]
    --output PATH [--columns N] [--padding N] [--loop N] [--tag NAME] [--json/--no-json].
    Load via project_io.load_project (IO-3, defensive → ProjectIOError); drive the SAME
    logic/export + data/export_io the GUI uses (REQ-P7-LOGIC-013 byte-identity). Exit 0 ok /
    1 ExportError|AtlasError / 2 bad-args|ProjectIOError."""
```

- **Output write (REQ-P7-DATA-001).** The file layer performs no transformation that could add
  nondeterminism — it writes the bytes the engine produced. Paths portable (`pathlib`), verified by
  `path_portability_check`.
- **Engine artifacts (REQ-P7-DATA-002, ADR-0018).** Built in `data/` from the `logic/`-computed
  `SheetMetadata` (the Phase-6 `tiled_io.py` precedent — a wire-format serialiser in `data/` over a
  `logic/` model); version strings are module-local format identifiers (ADR-0001).
- **CLI input (REQ-P7-DATA-003, IO-3).** The `.pixproj` load reuses `project_io.load_project`: every
  field type/bounds-checked, malformed/unknown-version → `ProjectIOError`, **never `eval`/`exec`**,
  portable paths. The loaded `Document` (DOC-1) is the same in-memory document the GUI's open produces
  — the precondition for CLI==GUI byte-identity (REQ-P7-LOGIC-013).
- **`pyproject` entry.** `[project.scripts]` `pixelart-export = "pixelart_creator.data.export_cli:main"`
  is an **AGT-09** edit (Article IX ownership), tracked as `TG-0x` in `tasks.md`.

## 7. Performance / responsiveness — DEP-3 routing to AGT-10/AGT-05 (ADR-0020 §Perf)

REQ-P7-UI-010 binds a **responsiveness** contract (progress + cancel, no freeze) for a large (up to
8K, 7680×4320) or big-batch export. Export is **batch IO, not the per-frame render loop** — the 16 ms
`FRAME_BUDGET_MS` (Article VI, the 8K canvas render budget) does **not** apply to export throughput
(CL-16). Architecture commitment:

1. **Off-GUI-thread export.** `ui/export_worker.py` runs the **Qt-free** `logic/export` +
   `data/export_io` on a window-owned `QThreadPool`; progress/result/error return over **queued
   GUI-thread signals**; a cooperative cancel flag interrupts between targets/frames. No Qt object is
   constructed off the GUI thread (the Phase-5 `composite_warmer` / Phase-6 chunk-warm precedent).
2. **The engine is thread-agnostic.** Because the pipeline is pure and Qt-free, "on a worker thread"
   is purely a `ui/` concern; the same functions run identically headless in the CLI.
3. **Ownership.** AGT-10 owns any responsiveness/throughput measurement + directive (a `perf_profile`
   scenario for a large/batch export if warranted); AGT-05 implements the worker; AGT-01 fixes the
   Qt-free-engine + worker seam (ADR-0020). The 16 ms canvas budget is **never** relaxed and is simply
   out of scope for export.

## 8. Constant placement (Article II / BF-1)

All in `logic/constants.py` (leaf). **New names are DISTINCT from every shipped constant** —
`PNG_EXPORT_COMPRESS_LEVEL` is explicitly distinct from the shipped `PROJECT_ZLIB_LEVEL=9`
(`.pixproj` pixel-data compression, a different concern):

| Constant | Value | Source |
| --- | --- | --- |
| `DEFAULT_SPRITE_SHEET_COLUMNS` | `8` | CL-5 (common sheet grid width); deterministic row-major layout |
| `DEFAULT_ATLAS_PADDING` | `0` | CL-15 (no inter-sprite gap by default; lossless, exact round-trip) |
| `MAX_ATLAS_DIMENSION` | `8192` | defensive bound (Article VII); ≥ 8K canvas; passed explicitly to `compactor.compact` (CP-1) |
| `MAX_BATCH_TARGETS` | `256` | defensive batch bound (Article VII; CL-10); parallels `MAX_LAYERS_PER_FRAME` |
| `MAX_EXPORT_FRAMES` | `4096` | frames per sheet/GIF; parallels the shipped `MAX_FRAMES=4096` |
| `PNG_EXPORT_COMPRESS_LEVEL` | `6` | ADR-0019; Pillow's documented default pinned explicitly (distinct from `PROJECT_ZLIB_LEVEL=9`) |
| `GIF_DEFAULT_LOOP_COUNT` | `0` | ADR-0019; 0 = loop forever (Aseprite/GIF norm) |
| `GIF_FRAME_DISPOSAL` | `2` | ADR-0019; restore-to-background — safe per-frame pixel-art default |

Pillow enum values (`Dither.NONE`) + format strings, the Aseprite/Unity/Godot wire-format version
strings, and the `ExportFormat`/`EnginePreset` enums stay **module-local** (ADR-0001 exemption / BF-2
enumerated vocabulary — the `BlendMode`/`PlaybackMode` precedent). The atlas caller passes
`MAX_ATLAS_DIMENSION` explicitly to `compactor.compact` (CP-1 imports no constants).

## 9. Implementation strategy — dependency-ordered slices

Logic-first vertical slices (detailed work items in `tasks.md`):

- **7A — raster + deterministic pipeline (logic)**: `constants.py` + `export.py` flatten/PNG/GIF +
  determinism backbone. REQ-P7-LOGIC-001, -002, -003, -004, -012. AGT-03 + AGT-04.
- **7B — sprite-sheet + atlas + JSON (logic)**: `export.build_sprite_sheet`/`build_metadata_json` +
  `atlas.py` (over CP-1). REQ-P7-LOGIC-005, -006, -007, -008. AGT-03 + AGT-04.
- **7C — presets + batch + headless CLI (logic/data)**: engine-preset artifacts + `run_batch` +
  `data/export_io.py` + `data/export_cli.py`; headless Qt-free assertion. REQ-P7-LOGIC-009, -010,
  -011, -013, REQ-P7-DATA-001, -002, -003, -004. AGT-03 + AGT-04 (+ AGT-09 pyproject entry).
- **7D — export UI (dialog, options, presets)**: `export_dialog.py` + `export_actions.py`.
  REQ-P7-UI-001..004, -006, -008, -009, -011..013. AGT-05 + AGT-06 + AGT-07.
- **7E — batch UI + headless parity + responsiveness**: `batch_export_panel.py` + `export_worker.py`;
  GUI==CLI byte-identity + responsiveness (DEP-3). REQ-P7-UI-005, -007, -010. AGT-05 + AGT-06 + AGT-10.

Reversibility boundary: export is **read-only** — **no** `history.Command`, **no** `QUndoCommand`,
**no** `ui/commands.py` change (CL-12). Progress/cancel/destination selection mutate no document state.

## 10. Constitution compliance (self-check)

- **I:** `export.py`/`atlas.py` + the `constants.py` extension are pure (zero Qt); `data/export_io.py`
  + `data/export_cli.py` are Qt-free I/O; all export dialogs/batch/worker in `ui/`; the CLI lives in
  `data/` so `check_layering` guards its Qt-freedom (ADR-0020); no `logic → data` edge; `export → atlas
  → compactor` one-way. Export adds **no** `ui/commands.py` logic.
- **II:** eight new numerics in `constants.py`, names distinct from every shipped constant (BF-1;
  `PNG_EXPORT_COMPRESS_LEVEL` ≠ `PROJECT_ZLIB_LEVEL`); Pillow/wire-format strings + enums
  intrinsic-local (ADR-0001/BF-2); atlas bounds passed explicitly to CP-1.
- **IV:** flatten-reuse (CO-4), pipeline determinism, PNG/GIF/sheet byte-reproducibility, atlas
  non-overlap + coordinate/pixel round-trip, deterministic metadata, batch==single, engine-ready
  presets, CLI==GUI byte-identity → each maps to a scenario → a headless pytest/Hypothesis test
  (logic/data) or pytest-qt test (UI, both themes). CI byte-diff gate (ADR-0019).
- **V:** REQ-P7-UI-011/-012/-013 are blocking gates on the export UI (a11y + both themes + full
  translatability).
- **VI:** REQ-P7-UI-010 binds a **responsiveness** contract (progress/cancel, no freeze); the 16 ms
  per-frame canvas budget does **not** apply to export (export is batch IO, not the render loop).
- **VII:** atlas/batch/frame bounds, the fit-or-`CompactionError` packer contract, the defensive
  validated `.pixproj` CLI load (IO-3); no `eval`/`exec`; portable paths (`path_portability_check`).
- **X:** every REQ traces to an S-id / F-finding / forward-inherited primitive (PB-1, CO-4, FR-1,
  CP-1, IO-3, DOC-1) in `traceability.md`.
- **XI:** deferring APNG, trim/extrusion, TexturePacker JSON, per-frame `AtlasTexture`, and additional
  engine versions (ADR-0017/0018/0019) adds capability later without weakening any article.

## 11. Layering / cycle verification

`python scripts/check_layering.py` → exit **0** (clean, 36 modules) and
`python scripts/check_cycles.py` → exit **0** (no cycles, 87 modules) on the shipped tree at plan time
(baseline, 2026-07-04). The planned edges (`export → atlas`, `export → blend`/`document`/`quantize`/
`animation`, `atlas → compactor`, `data/export_io → logic/export`/`atlas`, `data/export_cli →
data/project_io`/`export_io` + `logic/export`) are acyclic by construction (§3.4); both scripts are
re-run by AGT-03 when 7A/7B/7C land and gate the C1 analyze (Article I §4, VIII). See
`analyze-report.md` for the C1 verdict.

## 12. Decisions log

| # | Decision | Branch / choice | Rationale |
| --- | --- | --- | --- |
| PL7-D1 | Ungrounded stack/API choice? | **B (no)** | Stack fixed (S8); Pillow options, GIF palette, JSON schema, engine artifacts, MaxRects rotation grounded by landed `docs/research-phase-7-export-20260704.md`. No RESEARCH REQUEST. |
| PL7-D2 | Qt in `logic/`/`data/` or magic number outside `constants.py`? | **B (no)** | All export dialogs/batch/worker in `ui/`; eight numerics → `constants.py` (names distinct); Pillow/wire strings + enums intrinsic-local (ADR-0001/BF-2). |
| PL7-D3 | export/atlas layering | — | `export → atlas → compactor`, `export → blend`/`document`; neither imports `ui`/Qt; metadata builder in `export` so no `atlas → export` back-edge; no `logic → data` → acyclic. |
| PL7-D4 | Canonical JSON schema (DEP-2a) | **Aseprite Array** | Best pixel-art ecosystem fit; native Phase-5 `frameTags`+`duration`; rotation-free (matches CP-1); trim-off → exact round-trip; single test surface (ADR-0017). |
| PL7-D5 | Engine artifacts (DEP-2b) | Unity `.meta` (2022.3) + Godot `SpriteFrames.tres` (4.2) | Deterministic, in-repo-testable, 1:1 no-manual-fixup import; rotation-free; version-pinned to bound F-4/F-5 (ADR-0018). |
| PL7-D6 | APNG scope (DEP-2c) | **Deferred** | Not in ROADMAP scope (CL-8); GIF is the fixed animated format; `ExportFormat` seam left extensible (Art. XI) (ADR-0019). |
| PL7-D7 | Pillow/GIF options + byte-repro scope (DEP-2d) | Fixed option set; **same-environment** identity; GIF fixed shared palette via `logic/quantize` | Deterministic + honest (CL-14); reuses shipped quantiser; CI pins Pillow/zlib for a stable byte-diff (ADR-0019). |
| PL7-D8 | CLI entrypoint/grammar + placement (DEP-2e) | `data/export_cli.py` + `pyproject` console script `pixelart-export` | `check_layering` only guards `logic/`/`data/`; a `cli/` package would be an unscanned Qt blind spot; `data/` keeps the driver Qt-free-enforced (ADR-0020). |
| PL7-D9 | Responsiveness (DEP-3) | route to AGT-10/AGT-05 | Off-GUI-thread worker over the Qt-free engine (Phase-5/6 warmer precedent); progress/cancel; NOT the 16 ms budget (export is batch IO); budget never relaxed. |
| PL7-D10 | Reversibility (CL-12) | non-destructive; no `QUndoCommand` | Export reads, never edits; adds no `ui/commands.py` logic (ADR-0020, confirming AGT-02's note). |
