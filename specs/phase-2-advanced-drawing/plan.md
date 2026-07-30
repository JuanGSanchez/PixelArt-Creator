# Plan — Phase 2: Advanced Drawing System

| Field | Value |
| --- | --- |
| Feature | `phase-2-advanced-drawing` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 2 before any Phase-2 code exists |
| Over spec | `specs/phase-2-advanced-drawing/spec.md` (REQ-P2-LOGIC-001..015, REQ-P2-UI-001..015) |
| Layer scope | `pixelart_creator/logic/` (new modules) + `pixelart_creator/ui/` (new tools/overlays/actions) |
| Stack source | S8 (fixed) — no new technology; RotSprite/pixel-perfect algorithms grounded by The Researcher (`docs/research-rotsprite-pixelperfect.md`) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-2 spec: it
maps every new capability to its S11 layer, freezes the public interface of the six new
`logic/` modules **before** implementation so the UI slice binds to a stable contract,
**pins the four unpublished RotSprite implementation choices deterministically** (from the
research report), and specifies the reversible-op boundary so every mutating operation is
exactly one `QUndoCommand` with zero Qt in `logic/`. It is decomposed into dependency-ordered
work items in `tasks.md`.

No new stack/library/API is introduced (Decision PL-D1 → Branch B for every item: the stack
is fixed by S8; the two algorithms are grounded, not invented). The `sdd-analyze` C1 gate is
run over constitution/spec/plan/tasks as the pre-implement gate (Article VIII).

## 2. Stack decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language | Python 3.12+ | S8 |
| Pixel storage | Reuse `PixelBuffer` (NumPy `uint8`, RGBA `(H,W,4)` / INDEXED `(H,W)`) | S8, F7, Phase-1 |
| Selection mask | NumPy `bool` array `(H,W)`, origin top-left | S8 (NumPy), F7 |
| Geometry | Even-odd scanline fill (lasso); Bresenham (`drawing.line`) for strokes | Phase-1 `drawing.py` |
| Colour match | Reuse `color.distance_sq` (magic-wand + RotSprite similarity) | Phase-1 `color.py`, CL-1/CL-16 |
| RotSprite | Upscale ×8 (three similarity-Scale2× passes) → offset search → NN rotate+downscale → detail restore | Research report Topic 1 |
| Pixel-perfect | Aseprite elbow-removal rule (verbatim from source) | Research report Topic 2 (high reliability) |
| Reversibility | Reuse `history.PixelEdit` / `FunctionCommand` / `record_edit`; `ui/commands.py` wraps as `QUndoCommand` | S7, C1, F1, Phase-1 |
| Testing | pytest + Hypothesis (logic), pytest-qt both themes (UI), headless | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`) | Article III |

No Phase-2 logic decision places Qt in `logic/`; GPU/render choices for previews/overlays
belong to AGT-10 + `ui/` (see §7).

## 3. Architecture — module → layer map (S11)

All six new source modules live in `logic/` with **zero Qt imports** (Article I); the UI
modules live in `ui/` and are the only Qt consumers. Dependency direction is one-way
(`ui/` → `logic/`) and acyclic. The Qt undo bridge for every new op is `ui/commands.py`
(the sole Qt file outside `ui/`, S11).

### 3.1 New `logic/` modules (Slice 2A — pure, zero Qt)

| Module | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- |
| `logic/selection.py` | `SelectionMask` boolean-region model + rect/lasso/wand builders + ops (invert/clear/translate/combine) + mask-constrained apply + floating move | `pixel_buffer`, `color`, `drawing`, `history` | 001–006, 010 (mask side) |
| `logic/transform.py` | `flip_horizontal/vertical`, `rotate_90_cw/ccw`, `scale_nearest`; whole-buffer or selection-aware; reversible builders | `pixel_buffer`, `selection`, `history`, `constants` | 007–010 |
| `logic/symmetry.py` | `SymmetryAxis` enum (module-local, PL-D3) + `mirror(x,y,axis,w,h,axis_pos=None)` → mirrored-coord set | `constants` (none numeric required) | 011 |
| `logic/pixel_perfect.py` | `pixel_perfect(coords)` elbow-removal → clean 1-px path | — (leaf; stdlib only) | 012 |
| `logic/rotsprite.py` | `rotsprite(buffer, angle_degrees, *, pivot=None, fill=None)` clean arbitrary-angle rotation, no new colours | `pixel_buffer`, `color`, `constants` | 013 |
| `logic/tiled.py` | `wrap(x,y,w,h)` torus wrap + `preview_tiling(...)` 3×3 arrangement + reversible wrapped edit | `pixel_buffer`, `history`, `constants` | 014 |

Reversible-op integration (REQ-P2-LOGIC-015) is a cross-cutting concern realised **inside**
these modules (each mutating op has a companion that returns a `history.Command`), not a
seventh module. `constants.py` stays a leaf (no intra-package imports) so no cycle is
introduced. `SymmetryAxis` lives **in `symmetry.py`** (see PL-D3).

### 3.2 New `ui/` modules (Slice 2B — PySide6; binds to 2A)

| Module (indicative) | Responsibility | Binds to (logic) | REQ |
| --- | --- | --- | --- |
| `ui/tools/rectangle_tool.py` | Rectangle shape tool: live preview drag, commit-on-release | `drawing.rectangle` | UI-001, 003 |
| `ui/tools/ellipse_tool.py` | Ellipse shape tool | `drawing.ellipse` | UI-002, 003 |
| `ui/tools/rect_select_tool.py` | Rectangle selection tool + combine modifiers | `selection` rect builder + ops | UI-004 |
| `ui/tools/lasso_tool.py` | Freehand lasso selection tool | `selection` lasso builder | UI-005 |
| `ui/tools/magic_wand_tool.py` | Magic-wand selection tool + tolerance control | `selection` wand builder | UI-006 |
| `ui/selection_overlay.py` | Marching-ants mask outline + drag-to-move interaction | `selection` move op | UI-007 |
| `ui/transform_dialog.py` | Scale dialog (factor / target size, NN) | `transform.scale_nearest` | UI-009 |
| `ui/rotsprite_dialog.py` | Angle input + preview for RotSprite | `rotsprite.rotsprite` | UI-010 |
| `ui/symmetry_panel.py` | `SymmetryAxis` selector; live mirrored strokes | `symmetry.mirror` | UI-011 |
| `ui/tiled_mode.py` | Tiled-mode toggle + 3×3 repeating preview | `tiled` wrap + preview | UI-015 |
| `ui/main_window.py` (extend) | Selection-op / transform / RotSprite actions; pixel-perfect + grid/snap + AA-off toggles | selection ops, transform, `pixel_perfect` | UI-008, 009, 012, 013 |
| `ui/canvas_view.py` / `ui/canvas_scene.py` (extend) | AA-off render-hint lock (all previews); grid/snap refinements | — (render policy) | UI-013, 014 |
| `ui/commands.py` (extend) | One `QUndoCommand` wrapper per new mutating op (delegates to `history.Command`) | `history`, all 2A ops | UI-001..015 reversibility, LOGIC-015 |

`ui/tools/` shape-tool option (filled/outline, UI-003) and the pixel-perfect toggle (UI-012)
are shared tool-controller options, not standalone modules.

## 4. Slicing (spec §8, ratified)

- **Slice 2A — LOGIC** (`REQ-P2-LOGIC-001..015`). All six Qt-free modules + new constants +
  new exceptions + reversible-op builders + pytest/Hypothesis coverage. **Ships first** — it
  is the substrate every non-shape UI control binds to. RotSprite (LOGIC-013) is grounded
  (research landed) and no longer gated; the rest of 2A does not depend on it and can proceed
  in parallel.
- **Slice 2B — UI** (`REQ-P2-UI-001..015`). Tool controllers, overlays, transform/RotSprite
  actions, symmetry/pixel-perfect/tiled/grid/AA toggles, `ui/commands.py` wrappers + pytest-qt
  (both themes) + i18n. **Depends on 2A** for every non-shape control, and on a **stable
  Phase-1 UI substrate** (`ui/commands.py`, canvas view/scene, tool-controller pattern —
  in-progress `[~]`; 2B must not start before it is stable, PL-D4).
- **Optional early micro-slice — Shape tools UI** (`REQ-P2-UI-001..003`). Binds only to
  already-shipped Phase-1 `drawing.rectangle`/`ellipse`; needs **no** new Phase-2 logic. May
  start immediately once the Phase-1 UI substrate is stable, in parallel with 2A (tasks T11).

## 5. RotSprite deterministic implementation choices — PINNED (research §Limitations)

The research report (`docs/research-rotsprite-pixelperfect.md`) confirms the four-stage
pipeline but flags **four choices left unpublished** by the secondary sources. AGT-01 pins
them here **deterministically**; they become AGT-03 acceptance (REQ-P2-LOGIC-013 / SC-L013-*)
and are recorded immutably in **ADR-0002**. The "no new colours" guarantee is independent of
these pins (the pipeline is copy-only), so pinning does not risk R2.

| # | Choice | **Pinned value / rule** | Grounding |
| --- | --- | --- | --- |
| 1 | **Similarity threshold** (the Scale2× "similar not equal" test) | `ROTSPRITE_SIMILARITY_THRESHOLD = 100`, applied as `color.distance_sq(a, b) <= ROTSPRITE_SIMILARITY_THRESHOLD` (squared-RGBA units, the **same metric** as `flood_fill`/magic-wand). ≈ a modest per-channel delta (√100 = 10 in one channel); merges near-duplicate/antialiased fringe but keeps distinct pixel-art palette entries (which typically differ by ≫10/channel) separate. INDEXED: exact index equality (threshold ignored), matching CL-16. | Research Topic 1 step 2 (similarity is the defining deviation); reuses Phase-1 `color.distance_sq` (CL-1/CL-16) |
| 2 | **Pivot convention** | Rotation about the **geometric centre of the pixel grid** = `((W-1)/2.0, (H-1)/2.0)` (centre-of-pixel convention). Output buffer is the **same `W×H`** as input. `pivot` param defaults to this; an explicit pivot is honoured for selection-region rotation. | Research Topic 1 §Pivot (image centre; convention was unpinned → fixed here) |
| 3 | **Offset-search tie-break** | Search offsets `(dx,dy)` over `0..(FACTOR-1) × 0..(FACTOR-1)` on the 8× image, minimising the sum of squared neighbour colour differences (non-boundary samples weighted). **On equal cost, choose the lexicographically smallest `(dx, dy)`** (dx ascending, then dy ascending), scan started from `(0,0)`. Deterministic. | Research Topic 1 step 3 (tie-break was unpinned → fixed here) |
| 4 | **Out-of-bounds fill** | Uncovered destination pixels are filled **transparent RGBA `(0, 0, 0, 0)`** (spec recommendation, R-report natural choice). INDEXED buffers fill **index `0`**. `fill` param defaults to this. | Research Topic 1 §OOB (spec §Scope; α=0 natural for RGBA) |

Determinism (NFR-2): all stages are integer / nearest-neighbour and copy-only; with the four
pins fixed, `rotsprite(buffer, angle)` is reproducible in NumPy. `0°`/`360°` returns an equal
buffer; a fully transparent input stays transparent (SC-L013-2/-3). The `×8` upscale uses
`ROTSPRITE_UPSCALE_FACTOR = 8` (SC-L013-5).

## 6. Interface contracts (frozen BEFORE implementation — `interface-contract`)

The public surface of each new `logic/` module is frozen here so Slice 2B binds to a stable
API. STRUCTURE.md is updated with the same surface (§9). Exceptions subclass `ValueError`
(Phase-1 convention). Full signatures below; the **three headline modules** (selection,
transform, rotsprite) are called out per the task.

### 6.1 `logic/selection.py` (REQ-P2-LOGIC-001..006, 010)

```python
class SelectionError(ValueError): ...

class SelectionMask:
    def __init__(self, width: int, height: int) -> None: ...          # invalid dims -> SelectionError
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def is_empty(self) -> bool: ...
    def is_selected(self, x: int, y: int) -> bool: ...                # out-of-bounds -> False
    def count(self) -> int: ...                                       # number of selected pixels
    def bounds(self) -> Optional[Tuple[int, int, int, int]]: ...      # (x0,y0,x1,y1) inclusive, or None if empty
    def data(self) -> "npt.NDArray[np.bool_]": ...                    # (H,W) bool view/copy
    def copy(self) -> "SelectionMask": ...
    def __eq__(self, other: object) -> bool: ...                      # value equality

    # ops (return new masks; in-bounds clipped)
    def invert(self) -> "SelectionMask": ...
    def cleared(self) -> "SelectionMask": ...                         # -> empty (deselect/clear)
    def translate(self, dx: int, dy: int) -> "SelectionMask": ...     # shift, clip off-buffer
    def combine(self, other: "SelectionMask", mode: str) -> "SelectionMask": ...  # 'replace'|'add'|'subtract'

# builders
def rect_mask(width: int, height: int, x0: int, y0: int, x1: int, y1: int) -> SelectionMask: ...
    # swapped corners normalised (drawing.rectangle convention); clipped; zero/neg -> empty
def lasso_mask(width: int, height: int, vertices: Sequence[Tuple[int, int]]) -> SelectionMask: ...
    # auto-closed last->first; even-odd scanline fill; <3 distinct pts -> traced pixels only
def wand_mask(buffer: PixelBuffer, x: int, y: int, *, tolerance: int = MAGIC_WAND_DEFAULT_TOLERANCE) -> SelectionMask: ...
    # contiguous colour region (reuses flood_fill contiguity + distance_sq); INDEXED exact (CL-16); OOB seed -> empty

# mask-constrained editing + floating move
def apply_masked(buffer: PixelBuffer,
                 operation: Callable[[PixelBuffer], List[Tuple[int, int]]],
                 mask: Optional[SelectionMask]) -> List[Tuple[int, int]]: ...
    # runs operation on a scratch, writes back ONLY masked coords (mask None => whole buffer, CL-5);
    # returns exactly the coords actually changed (for the reversible record)
def move_selection(buffer: PixelBuffer, mask: SelectionMask, dx: int, dy: int) -> "history.Command": ...
    # lifts masked pixels (vacated -> transparent / index 0, CL-6), re-stamps at offset; returns a
    # reversible PixelEdit; bad args -> SelectionError
```

### 6.2 `logic/transform.py` (REQ-P2-LOGIC-007..010)

```python
class TransformError(ValueError): ...

# pure transforms (whole buffer) -> new PixelBuffer; pure pixel permutation (flip/rotate) => no new colours
def flip_horizontal(buffer: PixelBuffer) -> PixelBuffer: ...
def flip_vertical(buffer: PixelBuffer) -> PixelBuffer: ...
def rotate_90_cw(buffer: PixelBuffer) -> PixelBuffer: ...    # non-square: W/H swap (CL-8)
def rotate_90_ccw(buffer: PixelBuffer) -> PixelBuffer: ...
def scale_nearest(buffer: PixelBuffer, new_width: int, new_height: int) -> PixelBuffer: ...
    # nearest-neighbour only (CL-7) => output colour set ⊆ input (R2); non-int factors map by floor;
    # target <=0 or outside SCALE_MIN/MAX_FACTOR bounds -> TransformError

# reversible builders (whole buffer OR active selection region, REQ-P2-LOGIC-010)
def make_transform_command(document_or_buffer_ref, transform: Callable[[PixelBuffer], PixelBuffer],
                           mask: Optional[SelectionMask] = None) -> "history.Command": ...
    # dimension-changing transforms (rotate-90 non-square, scale) -> FunctionCommand capturing the
    #   prior buffer (do/undo swap the buffer reference);
    # same-dimension transforms (flip; selection-region transforms) -> PixelEdit of changed coords;
    # selection variant transforms ONLY masked pixels, re-stamps, leaves unmasked untouched (SC-L010-1)
```

### 6.3 `logic/rotsprite.py` (REQ-P2-LOGIC-013)

```python
def rotsprite(buffer: PixelBuffer, angle_degrees: float, *,
              pivot: Optional[Tuple[float, float]] = None,
              fill: Optional[Union[RGBA, int]] = None) -> PixelBuffer: ...
    # clean arbitrary-angle rotation: upscale x ROTSPRITE_UPSCALE_FACTOR (three similarity-Scale2x
    #   passes, similarity via distance_sq <= ROTSPRITE_SIMILARITY_THRESHOLD) -> offset search
    #   (lexicographic tie-break) -> NN rotate + downscale -> detail restore.
    # pivot defaults to grid centre ((W-1)/2, (H-1)/2); fill defaults to transparent RGBA (0,0,0,0)
    #   / index 0. Output is W x H. angle 0/360 -> equal buffer. Copy-only => output colour set ⊆ input
    #   (R2, acceptance-critical). Deterministic for fixed (buffer, angle).
def make_rotsprite_command(document_or_buffer_ref, angle_degrees: float,
                           mask: Optional[SelectionMask] = None) -> "history.Command": ...
    # FunctionCommand capturing prior buffer (do/undo swap); selection variant rotates the masked region only
```

### 6.4 Helper modules (contract summary)

- **`logic/symmetry.py`** — `class SymmetryAxis(enum.Enum): NONE/VERTICAL/HORIZONTAL/BOTH/DIAGONAL`;
  `mirror(x: int, y: int, axis: SymmetryAxis, width: int, height: int, axis_pos: Optional[Tuple[int, int]] = None) -> set[Tuple[int, int]]`.
  Returns the source coord plus its mirror images, de-duplicated, clipped to bounds. `VERTICAL` →
  `(W-1-x, y)`; `HORIZONTAL` → `(x, H-1-y)`; `BOTH` → 4-way; `DIAGONAL` → across the main diagonal;
  `NONE` → `{(x,y)}`. `axis_pos` defaults to canvas centre (CL-9). Deterministic, zero Qt.
- **`logic/pixel_perfect.py`** — `pixel_perfect(coords: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]`.
  Drops the interior elbow pixel of every L-triple (the Aseprite rule, research Topic 2): drop `p[i]`
  when `p[i-1]` shares x-or-y with `p[i]` AND `p[i+1]` shares x-or-y with `p[i]` AND `p[i-1]`/`p[i+1]`
  share neither. Endpoints never removed; idempotent on a clean line; order-preserving; deterministic.
- **`logic/tiled.py`** — `wrap(x: int, y: int, width: int, height: int) -> Tuple[int, int]` → `(x % W, y % H)`
  (torus, CL-14, handles negatives); `preview_tiling(buffer: PixelBuffer, repeat: int = TILED_PREVIEW_REPEAT) -> PixelBuffer`
  → a `repeat×repeat` arrangement of the tile (default 3×3, CL-13);
  `make_tiled_command(buffer, operation) -> history.Command` → wraps a paint op's coords modulo `(W,H)`
  and returns a reversible `PixelEdit` of the wrapped changed pixels.

## 7. Reversible-op boundary (REQ-P2-LOGIC-015, S7/C1/F1)

Every Phase-2 **mutating** op is built as a Phase-1 reversible `history.Command` in `logic/`,
so `ui/commands.py` wraps it in **one** `QUndoCommand`. No Qt in the logic path (NFR-1;
verified by `check_layering`, SC-L015-2).

| Op class | Command kind | Rationale |
| --- | --- | --- |
| Selection move; mask-constrained edit; pixel-perfect stroke; tiled (wrapped) edit; flip; selection-region transforms | `PixelEdit` (via `record_edit` / explicit changes) | Same buffer dimensions; per-pixel `(x,y,old,new)` diff is exact and minimal |
| Rotate-90 whole-buffer (dims swap); scale-NN (dims change); RotSprite whole-buffer | `FunctionCommand` (do/undo swap a captured prior-buffer copy) | Dimension-changing / near-total rewrite — a whole-buffer snapshot is the correct minimal reversible unit |

Invariant `apply ∘ undo = identity` holds per op (NFR-3, SC-L015-1). The logic returns a
`Command`; `ui/commands.py` supplies the Qt `QUndoCommand` shell and document-dirty signalling
only (no domain math), exactly as the Phase-1 `PaintCommand` bridge does.

## 8. Constants & enum placement (Article II / S12) — AGT-01 rulings

New tuning values go to `logic/constants.py` with a source citation, imported by name (NFR-5).
`constants.py` stays a leaf.

| Constant | Value | Classification / ruling |
| --- | --- | --- |
| `ROTSPRITE_UPSCALE_FACTOR` | `8` | Tuning → `constants.py` (ROADMAP; research Topic 1) |
| `ROTSPRITE_SIMILARITY_THRESHOLD` | `100` | Tuning → `constants.py` (§5 pin #1; squared-RGBA `distance_sq` units) |
| `MAGIC_WAND_DEFAULT_TOLERANCE` | `0` | Tuning → `constants.py` (CL-1; parity with `flood_fill`) |
| `TILED_PREVIEW_REPEAT` | `3` | Tuning → `constants.py` (CL-13; 3×3 preview) |
| `SCALE_MIN_FACTOR` | `0.01` | Tuning → `constants.py`. **PL-D5 ruling: adopt** — bounds the scale op/dialog below; relying only on `MAX_CANVAS_*` would admit pathological near-zero factors |
| `SCALE_MAX_FACTOR` | `64.0` | Tuning → `constants.py`. Upper factor guard; hard pixel bound remains `MAX_CANVAS_WIDTH/HEIGHT` (enforced by `PixelBuffer`) |

- **PL-D3 ruling (`SymmetryAxis` enum placement):** **module-local in `logic/symmetry.py`**, not
  `constants.py`. Enums live with their module in this codebase (cf. `ColorMode` in `pixel_buffer.py`);
  `constants.py` holds numeric tuning values only. No cycle (symmetry imports nothing intra-package).
- **New domain exceptions:** `SelectionError` (in `selection.py`), `TransformError` (in `transform.py`),
  both subclass `ValueError` (Phase-1 convention: `ColorError`, `PaletteError`, `PixelBufferError`,
  `DocumentError`, `CompactionError`, `ProjectIOError`). No RotSprite/symmetry/tiled/pixel-perfect
  exception needed (they operate on validated buffers/coords; scale/selection errors cover invalid input).

## 9. STRUCTURE.md update

STRUCTURE.md is updated in this session (§3 map + §6 public surface) to list the six new
`logic/` modules under a "Phase-2 advanced-drawing — PLANNED" block and to mark the new `ui/`
modules under the `ui/` planned block. AGT-01 maintains it via the `interface-contract` skill.

## 10. Performance (Article VI / NFR-8)

Live shape/selection previews, live symmetry mirroring, and the tiled 3×3 preview must hold
`FRAME_BUDGET_MS = 16` at 8K. The selection-overlay redraw and the tiled 3×3 preview are the
two new **perf-sensitive render paths**; if a `perf_profile` measurement goes over budget,
AGT-10 issues a culling/dirty-rect/scene-rect directive that AGT-05 implements — the budget is
never relaxed (Article VI §2). The resident buffer and mask are never culled; only Qt rendering
is (Article VI §3). Task T18 is conditional on a new perf-sensitive path existing.

## 11. Verification (this session)

- `python scripts/check_layering.py` → `clean (11 modules)`, exit 0.
- `python scripts/check_cycles.py` → `no cycles (26 modules)`, exit 0.

No Phase-2 code exists yet, so both are expected clean; they re-run in Slice 2A (task T10)
after the logic modules land and before the C1 gate is re-affirmed for implement.

## 12. Exit / status

- plan.md authored over the approved spec; six new `logic/` modules + `ui/` modules mapped to
  their S11 layers; interface contracts frozen (§6); four RotSprite choices pinned
  deterministically (§5, → ADR-0002); reversible-op boundary specified (§7); constants + enum
  placement ruled (§8, PL-D3/PL-D5).
- Stack fully grounded (no RESEARCH REQUEST needed — S8 + landed research).
- Layering/cycle gates green (§11).
- Slicing ratified (2A logic → 2B UI + optional early shape micro-slice); RotSprite ungated.
- `sdd-analyze` C1 gate run over constitution/spec/plan/tasks (see analyze report).
- **STATUS: COMPLETED.**
