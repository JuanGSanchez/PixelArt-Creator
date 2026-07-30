# Plan — Phase 9: Visual Aids & UX

| Field | Value |
| --- | --- |
| Feature | `phase-9-visual-aids` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, **VI**, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 9 before any `logic/grids.py`, `logic/guides.py`, `logic/preview.py`, `logic/timelapse.py`, `data/timelapse_io.py`, `data/reference_board_io.py`, `.pixproj` v5 PPI extension, or visual-aids UI exists. The `Document` tree + stable `layer_id` (DOC-1), `PixelBuffer` (PB-1), `logic/history.py` reversible-command path (HIS-1), `blend.composite_stack` (CO-4), the Phase-4 multiple-canvas / artboard viewport/tab system (MC-4), and the defensive `data/project_io.py` load (IO-3) are **shipped** and reused, not re-authored. |
| Over spec | `specs/phase-9-visual-aids/spec.md` (REQ-P9-LOGIC-001..012, REQ-P9-UI-001..014) + `traceability.md`. **DEP-4 ratified §12: a `REQ-P9-DATA-*` prefix IS allocated** — `REQ-P9-DATA-001` (timelapse persistence) + `REQ-P9-DATA-002` (reference-board persistence), each formalising a persistence contract already fixed under REQ-P9-LOGIC-010 / REQ-P9-UI-006 (not acceptance-changing). Total: **28 REQ** (12 LOGIC + 14 UI + 2 DATA). |
| Stack source | S8 (fixed) — no new technology. Geometry math (isometric 2:1 dimetric, perspective direction-lock, guides/rulers, real-size DPI), timelapse cadence, reference-board landscape are **grounded** by The Researcher (`docs/research-phase-9-visual-aids-20260704.md`, **landed**) → PL9-D1 Branch B (no RESEARCH REQUEST). |
| ADRs filed | **ADR-0023** (geometry & snap model — 2:1-dimetric isometric transform+snap, direction-lock perspective, doc-coord guides/rulers + nice-number ticks, real-size scale = `screen_DPI/doc_PPI` + DPR handling + manual calibration); **ADR-0024** (architecture — multi-view over one shared scene, per-committed-command reproducible timelapse, PureRef-style reference board, `REQ-P9-DATA-*` allocation, three-layer placement + layering, 16 ms perf routing DEP-3); **ADR-0025** (`.pixproj` v5 `Document.ppi` + timelapse-session + `.pixboard` persistence formats, BF-3) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-9 spec — the **high-usability
visual-aids & UX** milestone that turns the shipped document / pixel / reversible-command / composite /
viewport primitives into a **real-size preview that mirrors edits live**, **guides & rulers**, **isometric
& perspective grids**, a **PureRef-style reference board**, **multi-view editing that stays in sync**, and
**reproducible timelapse recording** — while making the phase's defining property, **tested geometry
logic** (pure, deterministic, unit-testable snap/scale math), true *by construction*. It maps every REQ to
its S11 layer, **freezes the public interface** of the new `logic/grids.py`, `logic/guides.py`,
`logic/preview.py`, `logic/timelapse.py`, `data/timelapse_io.py`, and `data/reference_board_io.py` before
implementation so the DATA/UI slices bind to a stable contract, rules the six **DEP-2** HOW decisions in
**ADR-0023/0024/0025**, routes the **DEP-3** 16 ms render NFR to AGT-10/AGT-05, **ratifies DEP-4 by
allocating a `REQ-P9-DATA-*` prefix** (two DATA REQs), resolves the **BF-3** document-PPI data-model
addition (`.pixproj` v5), places the ten new numerics in `logic/constants.py` with names **distinct from
every shipped constant** (Article II / BF-1), and commits the layering so `check_layering`/`check_cycles`
stay green (both exit `0` at plan time — §11). It is decomposed into dependency-ordered work items in
`tasks.md`.

No new stack/library/API is introduced (**PL9-D1 → Branch B**: the stack is fixed by S8; the geometry
math, timelapse cadence, and reference-board landscape are **grounded, not invented** —
`docs/research-phase-9-visual-aids-20260704.md` has landed). The `sdd-analyze` C1 gate is run over
constitution/spec/plan/tasks as the pre-implement gate (Article VIII; see `analyze-report.md`).

## 2. The tested-geometry invariant (Article I + P2 — CENTRAL; ADR-0023)

> **Every snap / transform / scale / ruler-tick / timelapse-model result is a pure, deterministic function
> of its inputs — zero Qt, no wall-clock, no randomness, no locale-dependent formatting, no order-unstable
> iteration — so the SAME function the overlays call is the one AGT-04 unit- and property-tests without any
> GUI or event loop.**

This is the ROADMAP's "compute snap points from tested geometry logic," satisfied **structurally**:
`logic/grids.py`, `logic/guides.py`, `logic/preview.py`, and `logic/timelapse.py` import **no** Qt
(`check_layering`), and every public function has a documented deterministic tie-break (round-half-up for
iso vertices; lowest-VP-index for perspective; lowest-position for guides — ADR-0023 §1–§3). The
**rendering** — overlays, preview window, reference board, multi-view viewports, timelapse controls — lives
in `ui/` and *calls* the pure geometry; it re-implements **none** of it (Article I). Phase 9 adds **no**
`ui/commands.py` logic: visual aids are **non-destructive** (REQ-P9-UI-010) — only the shipped drawing
edits (HIS-1) mutate the document. AGT-04/AGT-06 test the invariants in §10.

## 3. Stack / domain decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language / stack | Python 3.12+; stdlib + NumPy (shipped); reuse `logic/blend` (CO-4), `logic/history` (HIS-1), `logic/document` (DOC-1), `data/project_io` (IO-3); no new dependency | S8 |
| Isometric default | **2:1 dimetric** (`DEFAULT_ISO_GRID_RATIO=2.0`), **diamond** layout; true-iso configurable; documented invertible transform `sx=(i−j)w+ox, sy=(i+j)h+oy` + inverse; snap→nearest vertex `round(i),round(j)` (tie-break round-half-up) | REQ-P9-LOGIC-001/-002; ADR-0023 §1; research §1 |
| Perspective | **Direction-lock-to-VP** snap (1-/2-/3-point, `MAX_PERSPECTIVE_VANISHING_POINTS=3`); deterministic guide-line construction from config; snap→nearest guide within tolerance else none (tie-break lowest VP index) | REQ-P9-LOGIC-003/-004; ADR-0023 §2; research §2.3 |
| Guides / rulers | Doc-coordinate guides (`GuideOrientation` module-local); tolerance = `screen_px ÷ zoom → doc_px` (`DEFAULT_SNAP_TOLERANCE_PX=8`); nice-number `{1,2,5}·10ⁿ` ruler ticks; locale-independent labels | REQ-P9-LOGIC-005/-006; ADR-0023 §3; research §3 |
| Real-size scale | `real_size_scale(doc_ppi, screen_dpi) = screen_dpi / doc_ppi` (pure logic/); **Qt applies DPR — do NOT multiply** (device-independent coords); manual on-screen-ruler calibration fallback; Qt DPI query in `ui/`, math in `logic/preview.py` | REQ-P9-LOGIC-007; ADR-0023 §4; research §4 (HIGHEST-RISK) |
| Document PPI (BF-3) | **First-class `Document.ppi: float`** (default `DEFAULT_DOCUMENT_PPI=72.0`); persisted via `.pixproj` **v5** (v1–v4 load unchanged → default); validated | REQ-P9-LOGIC-007; ADR-0025 §1; BF-3/CL-3 |
| Multi-view sync | **One shared `Document`** (DOC-1), one `QGraphicsScene`, **N `QGraphicsView`s** (`setScene(sameScene)`), per-view transform; `scene.changed` auto-repaints all; builds on MC-4 (not respecified); no per-view pixel copy | REQ-P9-LOGIC-012, REQ-P9-UI-007/-008; ADR-0024 §1; research §5 |
| Live mirror | An edit is one command on the shared document (HIS-1); preview + every view derive from it — no manual refresh; preview read-only | REQ-P9-UI-002; ADR-0024 §1; research §5.1 |
| Timelapse | **Per-committed-command**, **document-render** (CO-4), reproducible; model = ordered `{index, command_id}` manifest (not inline pixels); replay re-renders deterministically; `MAX_TIMELAPSE_FRAMES` | REQ-P9-LOGIC-010; ADR-0024 §2; research §6.1/6.2 |
| Timelapse encoding | **Deferred** (CL-16): Phase 9 ships the reproducible **sequence**; GIF export reuses Phase-7 `encode_gif` (later handoff); MP4/ffmpeg deferred (optional, consent) | spec §6; ADR-0024 §2; research §6.4 |
| Reference board | Separate `QGraphicsScene` of `QGraphicsPixmapItem`s (movable/scalable/croppable), infinite pan/zoom; **non-destructive** (never composites/exports/undoes); `MAX_REFERENCE_IMAGES`; UI + serialisation, **no** pure-core geometry | REQ-P9-UI-006; ADR-0024 §3; research §7 |
| Persistence | `data/timelapse_io.py` + `data/reference_board_io.py` — defensive `eval`-free IO-3 (de)serialise; round-trip gates; `TimelapseIOError`/`ReferenceBoardIOError(ProjectIOError)`; portable paths | REQ-P9-DATA-001/-002; ADR-0024 §4 / ADR-0025 §2/§3; IO-3 |
| `REQ-P9-DATA-*` prefix | **ALLOCATE** — `REQ-P9-DATA-001` (timelapse) + `REQ-P9-DATA-002` (reference board); each verbatim the spec's fixed persistence contract; not acceptance-changing (DEP-4) | ADR-0024 §4; PREFIX-NOTE; CL-15 |
| Non-destructive aids | Grids/guides/board/preview/views/recording push **no** `QUndoCommand`; Phase 9 adds no `ui/commands.py` logic; only HIS-1 drawing edits are undoable | REQ-P9-UI-010; CL-12; ADR-0024 §5 |
| Performance (16 ms) | **Article VI APPLIES** (overlays + views on the per-frame render loop): cache-backed overlays (`DeviceCoordinateCache`), `MinimalViewportUpdate`, tile-cull + dirty-rect per view; strategy owned by AGT-10 (DEP-3); budget never relaxed | REQ-P9-UI-011; ADR-0024 §6; research §5.3 |
| Bounds | 10 named constants in `logic/constants.py`; exceeding → domain error | REQ-P9-LOGIC-011; Article II/VII; §8 |
| Testing | pytest + Hypothesis (logic/data, headless — incl. the 10 `[GEO]` geometry tests), pytest-qt both themes (UI) | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-9 logic/data decision places Qt in `logic/` or `data/` (**PL9-D2 → Branch B held**). All overlays
/ preview window / reference board / multi-view viewports / timelapse controls live only in `ui/`; the sole
Qt file outside `ui/` remains `ui/commands.py` (**unchanged by Phase 9** — no new undoable aid).

## 4. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`) and acyclic (verified §11). The new Qt-free
logic edges are `grids → {constants}`, `guides → {constants}`, `preview → {constants}`,
`timelapse → {document, blend, history, constants}` — never the reverse, never `logic → data`, never
`logic`/`data` → `ui`/Qt (§4.4).

### 4.1 New / extended `logic/` modules (Slices 9A–9D — pure, zero Qt)

| Module | Change | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | Add the 10 visual-aids numerics (leaf, no imports). **Names distinct from every shipped constant (BF-1).** | — | LOGIC-011 |
| `grids.py` | **new** | Isometric transform (`iso_world_to_screen`/`iso_screen_to_world`, invertible, 2:1 dimetric default) + `iso_snap_vertex` (nearest lattice vertex, round-half-up tie-break); perspective `perspective_guide_lines` (deterministic construction) + `perspective_snap` (direction-lock to nearest VP within tolerance, else `None`; lowest-index tie-break). Clamps tile width to `[MIN_GRID_SPACING, MAX_GRID_SPACING]`; `MAX_PERSPECTIVE_VANISHING_POINTS`. `GridError`. Zero Qt. | `constants` | LOGIC-001, 002, 003, 004, 008, 009, 011 |
| `guides.py` | **new** | `snap_guides` (per-axis nearest guide within `tol_doc`, lowest-position tie-break) + `screen_tolerance_to_doc(tol_px, zoom)`; `ruler_ticks` (nice-number `{1,2,5}·10ⁿ`, locale-independent labels) + `coordinate_readout`. `GuideOrientation` (module-local), `Guide`, `MAX_GUIDES`. `GuideError`. Zero Qt. | `constants` | LOGIC-005, 006, 008, 009, 011 |
| `preview.py` | **new** | `real_size_scale(doc_ppi, screen_dpi) = screen_dpi / doc_ppi` — pure, deterministic; **no DPR math** (Qt applies it). `PreviewError`. Zero Qt. | `constants` | LOGIC-007, 008, 009 |
| `timelapse.py` | **new** | Reproducible session model: `TimelapseSession`(`schema_version` module-local; ordered `TimelapseFrame(index, command_id)` ≤ `MAX_TIMELAPSE_FRAMES`); `record_frame` (per-committed-command); `replay(session, document, renderer)` — deterministic re-render of each state via `composite_stack` (CO-4) over the HIS-1 history; no wall-clock/random/locale. `TimelapseError`. Zero Qt. | `document`, `blend`, `history`, `constants` | LOGIC-008, 009, 010, 011 |
| `document.py` | extend | Add first-class `ppi: float` field (`__slots__`+`__init__`, default `DEFAULT_DOCUMENT_PPI`, validated > 0/finite → `DocumentError`) for real-size scale (BF-3). No other change. | `constants` | LOGIC-007, 012 |

`constants.py` stays a leaf. `GuideOrientation` and the timelapse `schema_version` string are
**module-local** enumerated vocabulary / format-intrinsic (ADR-0001 / BF-2 — the `BlendMode`/`PlaybackMode`
precedent). `grids`/`guides`/`preview` are pure leaves over `constants`; only `timelapse` reaches shipped
`document`/`blend`/`history` (downward, no cycle).

### 4.2 New `data/` modules + `.pixproj` v5 (Slice 9E — Qt-free I/O; DEP-4)

| Module | Change | Responsibility | Depends on | REQ |
| --- | --- | --- | --- | --- |
| `timelapse_io.py` | **new** | Defensive `eval`-free (de)serialise of a `TimelapseSession` (`.pixtimelapse` sidecar JSON: `schema_version` + `{index, command_id}` manifest, **not** inline pixels) via IO-3: type/bounds-check; malformed/unknown-version → `TimelapseIOError`; **never `eval`/`exec`**; portable paths; **round-trip → identical replay**. Zero Qt. | `logic/timelapse`, `constants` | DATA-001 (⊇ LOGIC-010 persistence) |
| `reference_board_io.py` | **new** | Defensive `eval`-free (de)serialise of the board layout (`.pixboard` JSON: `schema_version` + board pan/zoom + ordered `{image (path or embedded), transform 6-float, crop, z_order}` ≤ `MAX_REFERENCE_IMAGES`) via IO-3: type/bounds-check; malformed → `ReferenceBoardIOError` (user-facing); **never `eval`/`exec`**; portable paths; non-destructive round-trip. A pure `data/` board-layout dataclass (no Qt). | `constants` | DATA-002 (⊇ UI-006 persistence) |
| `project_io.py` | extend | `.pixproj` **v5**: persist `Document.ppi`; v1–v4 load unchanged (absent → `DEFAULT_DOCUMENT_PPI`); out-of-range → `ProjectIOError`; `_SUPPORTED_VERSIONS` += 5. Regression: v1–v4 fixtures load byte-for-byte unchanged. | `logic/document`, `constants` | LOGIC-007 (PPI persistence) |

Both new serialisers reuse the `project_io.py` posture (IO-3). `TimelapseIOError`/`ReferenceBoardIOError`
subclass `ProjectIOError`. No `logic → data` edge.

### 4.3 New `ui/` modules (Slice 9F/9G/9H — Qt only)

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `real_size_preview_window.py` | **new** | `Real_Size_Preview_Window(QWidget)`: render the composited document (CO-4) at `real_size_scale` (adds **no** scaling math — Article I); mirror edits live (observes the shared document); read-only; the **Qt DPI query** (`QScreen.physicalDotsPerInch()`) + **manual on-screen-ruler calibration** live here; recompute on `screenChanged`; **do not multiply DPR**. `tr()` + `changeEvent`. | `preview.real_size_scale`, `blend`, `document` | UI-001, 002 |
| `guides_rulers_overlay.py` | **new** | `Guides_Rulers_Overlay`: create/move/remove guides; rulers show `coordinate_readout` + `ruler_ticks`; cursor snaps via `guides.snap_guides` (overlay computes **no** snap). Role-based colours; `tr()` + `changeEvent`. | `guides.*` | UI-003 |
| `iso_grid_overlay.py` | **new** | `Iso_Grid_Overlay`: render the iso grid from `grids.iso_world_to_screen`; snap cursor to nearest vertex via `grids.iso_snap_vertex`; bounded spacing. `DeviceCoordinateCache`. `tr()`. | `grids.*` | UI-004 |
| `perspective_grid_overlay.py` | **new** | `Perspective_Grid_Overlay`: render guide lines from `grids.perspective_guide_lines`; snap to nearest guide within tolerance via `grids.perspective_snap`; configurable VPs (≤ 3). `DeviceCoordinateCache`. `tr()`. | `grids.*` | UI-005 |
| `reference_board.py` | **new** | `Reference_Board(QWidget)` over a **separate** `QGraphicsScene`: add/arrange(move/resize)/zoom reference images (croppable); non-destructive; persist via `data/reference_board_io` (malformed → user-facing error). `tr()` + `changeEvent`. | `data/reference_board_io` | UI-006 |
| `multi_view.py` | **new** | `Multi_View` controller: open extra `QGraphicsView`(s) on the **shared** document scene (≤ `MAX_DOCUMENT_VIEWS`); per-view transform (independent zoom/pan); `scene.changed` auto-syncs content + preview; view titles `tr()`. Builds on MC-4. | `document` (shared scene) | UI-007, 008 |
| `timelapse_controls.py` | **new** | `Timelapse_Controls(QWidget)`: start/stop recording (view/session state, **no undo**); record one frame per committed command via `timelapse.record_frame`; save/load the session via `data/timelapse_io`; failed record → user-facing error. `tr()` + units + `changeEvent`. | `timelapse`, `data/timelapse_io` | UI-009 |
| `main_window.py` | extend | Add the View-Aids menu + dock/toggle the overlays, preview window, reference board, extra views, and timelapse controls; hold each view's local zoom/pan + chosen aid config (view state). **No `ui/commands.py` change** (aids non-destructive). | `document`, the new visual-aids UI | UI-001, 003, 010 |

### 4.4 Layering proof (PL9-D3 — cycle-free by construction)

New intra-`logic/` edges: `grids → {constants}`, `guides → {constants}`, `preview → {constants}`,
`timelapse → {document, blend, history, constants}`, `document → {constants}` (existing). `data/timelapse_io
→ {logic/timelapse, constants}`, `data/reference_board_io → {constants}`, `data/project_io → {logic/document,
constants}` (PPI field, no new edge). The `ui/` visual-aids modules import **downward**
(`ui → logic`+`data`) only. None of these imports `ui/` or Qt; no module imports a visual-aids module
**back**; `grids`/`guides`/`preview` are pure leaves; `timelapse` reaches only shipped downstream modules.
Resulting one-way chain:

```
ui/real_size_preview_window   →  logic/preview        →  logic/constants
ui/guides_rulers_overlay      →  logic/guides         →  logic/constants
ui/iso_grid_overlay           →  logic/grids          →  logic/constants
ui/perspective_grid_overlay   →  logic/grids
ui/reference_board            →  data/reference_board_io → logic/constants
ui/multi_view                 →  logic/document (shared scene)
ui/timelapse_controls         →  logic/timelapse      →  logic/{document, blend, history, constants}
                              →  data/timelapse_io    →  logic/timelapse
data/project_io (v5)          →  logic/document       →  logic/constants
```

No back-edge (`logic → data`, or any `logic`/`data` → `ui`) exists. `check_layering` + `check_cycles`
therefore stay `0` (verified §11 on the shipped tree; the planned edges are acyclic by design and re-run
when 9A–9E land).

## 5. Frozen interface contracts (Slices 9A–9E)

Frozen **before** implementation so 9E/9F/9G/9H bind to a stable surface. Qt-free. All new errors subclass
`ValueError` (Phase-1 convention); `TimelapseIOError`/`ReferenceBoardIOError` subclass `ProjectIOError`.
`GuideOrientation` + timelapse `schema_version` are module-local (BF-2). Every function is pure and
deterministic (tie-breaks documented — ADR-0023).

```python
# logic/grids.py — isometric transform+snap + perspective construction+snap (pure, zero Qt)
class GridError(ValueError): ...

@dataclass(frozen=True)
class IsoGridConfig:
    origin: Tuple[float, float]                  # (ox, oy) doc-space screen anchor of cell (0,0)
    tile_width: int                              # W px; clamped to [MIN_GRID_SPACING, MAX_GRID_SPACING]
    ratio: float = DEFAULT_ISO_GRID_RATIO        # tile W:H; 2.0 = 2:1 dimetric (true-iso configurable)

def iso_world_to_screen(i: float, j: float, config: IsoGridConfig) -> Tuple[float, float]:
    """Diamond: sx=(i-j)*w+ox, sy=(i+j)*h+oy (w=W/2, h=w/ratio). Pure. REQ-P9-LOGIC-001."""

def iso_screen_to_world(sx: float, sy: float, config: IsoGridConfig) -> Tuple[float, float]:
    """Inverse: i=sx'/(2w)+sy'/(2h), j=sy'/(2h)-sx'/(2w). Round-trips on lattice. REQ-P9-LOGIC-001."""

def iso_snap_vertex(sx: float, sy: float, config: IsoGridConfig) -> Tuple[float, float]:
    """Nearest lattice vertex: round-half-up floor(v+0.5) on (i,j) -> reproject. Deterministic tie-break.
    Pure, unit-testable. REQ-P9-LOGIC-002/-009."""

@dataclass(frozen=True)
class VanishingPoint:
    position: Optional[Tuple[float, float]]      # finite VP; None => axis-lock pseudo-VP at infinity
    direction: Optional[Tuple[float, float]] = None   # unit dir for a pseudo-VP

@dataclass(frozen=True)
class PerspectiveConfig:
    mode: int                                    # 1|2|3, <= MAX_PERSPECTIVE_VANISHING_POINTS
    vanishing_points: Tuple[VanishingPoint, ...]
    horizon_y: float

@dataclass(frozen=True)
class GuideLine:
    p0: Tuple[float, float]
    p1: Tuple[float, float]

def perspective_guide_lines(config: PerspectiveConfig, samples: int) -> Tuple[GuideLine, ...]:
    """Deterministic fan of guide segments per VP (render aid). REQ-P9-LOGIC-003."""

def perspective_snap(sx: float, sy: float, anchor: Tuple[float, float],
                     config: PerspectiveConfig, tolerance: float) -> Optional[Tuple[float, float]]:
    """Direction-lock: per VP d=norm(V-anchor) (or fixed dir), proj=anchor+dot(C-anchor,d)*d,
    err=|(C-anchor)-dot*d|. Return nearest proj if min err<=tolerance else None. Lowest-index tie-break;
    skip degenerate anchor==V. Pure. REQ-P9-LOGIC-004/-009."""

# logic/guides.py — guide/ruler snap + tick computation (pure, zero Qt)
class GuideError(ValueError): ...

class GuideOrientation(Enum):                    # module-local vocabulary (ADR-0001/BF-2)
    HORIZONTAL; VERTICAL

@dataclass(frozen=True)
class Guide:
    orientation: GuideOrientation
    position: float                              # doc coord (x for VERTICAL, y for HORIZONTAL)

def screen_tolerance_to_doc(tolerance_px: float, zoom: float) -> float:
    """tol_doc = tolerance_px / zoom (constant stickiness at all zooms). REQ-P9-LOGIC-005."""

def snap_guides(x: float, y: float, guides: Sequence[Guide], tolerance_doc: float) -> Tuple[float, float]:
    """Per-axis snap to nearest guide within tolerance_doc; unchanged if none. Guides considered in
    ascending position; equal-distance -> lowest position. Pure. > MAX_GUIDES -> GuideError.
    REQ-P9-LOGIC-005/-009/-011."""

@dataclass(frozen=True)
class RulerTick:
    position: float                              # doc coord
    label: str                                   # locale-independent integer string
    major: bool

def ruler_ticks(doc_length: float, zoom: float, offset: float, *, axis_pixels: int
                ) -> Tuple[RulerTick, ...]:
    """Nice-number {1,2,5}*10^n ladder: smallest step with step*zoom >= min label spacing. Pure of the
    view params. REQ-P9-LOGIC-006/-009."""

def coordinate_readout(sx: float, sy: float, zoom: float, offset: Tuple[float, float]) -> Tuple[int, int]:
    """Screen->doc integer coordinate readout. Deterministic. REQ-P9-LOGIC-006."""

# logic/preview.py — real-size scale (pure, zero Qt)
class PreviewError(ValueError): ...

def real_size_scale(doc_ppi: float, screen_dpi: float) -> float:
    """Device-independent screen-px per doc-px = screen_dpi / doc_ppi. Pure, deterministic. Qt applies DPR
    (DO NOT multiply here). doc_ppi<=0 or screen_dpi<=0 -> PreviewError. REQ-P9-LOGIC-007/-009."""

# logic/timelapse.py — reproducible per-command session model (pure, zero Qt)
class TimelapseError(ValueError): ...

@dataclass(frozen=True)
class TimelapseFrame:
    index: int                                   # ordinal
    command_id: int                              # stable id of the committed history command

@dataclass(frozen=True)
class TimelapseSession:
    schema_version: str                          # module-local format-intrinsic (ADR-0001)
    frames: Tuple[TimelapseFrame, ...]           # <= MAX_TIMELAPSE_FRAMES

def record_frame(session: TimelapseSession, command_id: int) -> TimelapseSession:
    """Append one frame per committed command (per-committed-command cadence). > MAX_TIMELAPSE_FRAMES ->
    TimelapseError. Pure (returns a new session). REQ-P9-LOGIC-010/-011."""

# renderer: a pure Document-state -> RGBA ndarray function (composite_stack, CO-4)
def replay(session: TimelapseSession, document: "Document",
           renderer: Callable[["Document"], "ndarray"]) -> Tuple["ndarray", ...]:
    """Deterministic replay: reconstruct each recorded state over the HIS-1 history and render it via the
    renderer (composite_stack, CO-4). Same session -> same frame sequence twice; no wall-clock/random/
    locale. REQ-P9-LOGIC-010/-009."""
```

```python
# data/timelapse_io.py — defensive eval-free (de)serialise (IO-3); Qt-free; portable paths
class TimelapseIOError(ProjectIOError): ...      # ProjectIOError family (IO-3)

def save_session(session: TimelapseSession, path: PathLike) -> None: ...
def load_session(path: PathLike) -> TimelapseSession:
    """Type/bounds-check every field; malformed/out-of-bounds/unknown schema_version -> TimelapseIOError;
    NEVER eval/exec. Round-trip -> identical replay. REQ-P9-DATA-001 (⊇ REQ-P9-LOGIC-010 persistence)."""

# data/reference_board_io.py — defensive eval-free (de)serialise (IO-3); Qt-free; portable paths
class ReferenceBoardIOError(ProjectIOError): ...

@dataclass(frozen=True)
class ReferenceImageEntry:
    image: str                                   # path reference OR embedded base64
    transform: Tuple[float, float, float, float, float, float]   # 2x3 affine
    crop: Tuple[float, float, float, float]      # x, y, w, h
    z_order: int

@dataclass(frozen=True)
class ReferenceBoardLayout:
    schema_version: str
    pan: Tuple[float, float]
    zoom: float
    images: Tuple[ReferenceImageEntry, ...]      # <= MAX_REFERENCE_IMAGES

def save_board(layout: ReferenceBoardLayout, path: PathLike) -> None: ...
def load_board(path: PathLike) -> ReferenceBoardLayout:
    """Type/bounds-check every field; malformed/unknown-version -> ReferenceBoardIOError (user-facing);
    NEVER eval/exec; portable paths. Non-destructive round-trip. REQ-P9-DATA-002 (⊇ REQ-P9-UI-006)."""
```

## 6. `data/` contract notes

- **Timelapse persistence (REQ-P9-DATA-001, IO-3).** `timelapse_io.py` reuses the `project_io` posture:
  every field validated, defensive rejection with `TimelapseIOError`, **never `eval`/`exec`**, `pathlib`
  portable paths (`path_portability_check`). Stores the command manifest (not pixels) so a
  saved-then-reloaded session **replays to the identical frame sequence** (round-trip gate, SC-L010-1).
- **Reference-board persistence (REQ-P9-DATA-002, IO-3).** `reference_board_io.py` round-trips a pure
  `ReferenceBoardLayout` dataclass; the UI maps it to `QGraphicsPixmapItem`s. Non-destructive; malformed →
  user-facing error, never a crash/execution.
- **`.pixproj` v5 PPI (REQ-P9-LOGIC-007, IO-3).** `project_io` gains a defensively-loaded `ppi` field;
  v1–v4 files load unchanged with `DEFAULT_DOCUMENT_PPI` (regression fixture mandatory). Not a new
  serialiser → **not** a DATA REQ (ADR-0025 §1).
- **`REQ-P9-DATA-*` prefix (DEP-4).** **ALLOCATED**: `REQ-P9-DATA-001` (timelapse) + `REQ-P9-DATA-002`
  (reference board), each verbatim the spec's fixed persistence contract (ADR-0024 §4). Traceability
  updated. Not acceptance-changing.

## 7. Performance / render budget — DEP-3 routing to AGT-10/AGT-05 (ADR-0024 §6)

REQ-P9-UI-011 binds the **16 ms `FRAME_BUDGET_MS`** (Article VI) to the grid/guide/perspective overlays,
the multi-view viewports, and the preview mirror **because these are on the per-frame render loop** — the
key distinction from the batch-work Phases 7–8 (CL-13). Architecture commitment (strategy owned by AGT-10):

1. **Cache-backed overlays.** Grid/guide/perspective overlays are `QGraphicsItem`s with
   `DeviceCoordinateCache` so pan/zoom does not re-rasterise them (research §5.3); overlay/guide colours
   role-based, legible over artwork in both themes (REQ-P9-UI-013).
2. **Dirty-rect multi-view.** `MinimalViewportUpdate`; each view repaints only its changed sub-rect via
   `item.update(changed_rect)`; tile-culling + dirty-rect partial redraw per view (the AGT-10
   render-strategy directive, DEP-3) so **N up-to-8K views** stay within budget.
3. **Responsive preview/timelapse.** The preview mirror + per-command timelapse capture are pure document
   renders (CO-4); whether long-running capture runs off the GUI thread is an AGT-01/AGT-10 HOW (the
   Phase-5/6/7/8 worker precedent). Phase 9 defers encoding, so capture is the per-command composite the
   views already need.
4. **Ownership.** AGT-10 owns the render/perf strategy + `perf_profile` on the 8K canvas; AGT-05
   implements; AGT-01 fixes the pure-geometry + shared-scene seam. **The 16 ms budget is never relaxed.**

## 8. Constant placement (Article II / BF-1)

All in `logic/constants.py` (leaf). **New names are DISTINCT from every shipped constant:**

| Constant | Value | Source |
| --- | --- | --- |
| `DEFAULT_ISO_GRID_RATIO` | `2.0` | 2:1 dimetric default (ADR-0023 §1; research §1.1) |
| `DEFAULT_SNAP_TOLERANCE_PX` | `8` | screen-px stickiness ÷ zoom (research §3.3) |
| `MIN_GRID_SPACING` | `2` | min iso tile width, px |
| `MAX_GRID_SPACING` | `1024` | max iso tile width, px |
| `MAX_GUIDES` | `256` | guide-count ceiling (parallels `MAX_BATCH_RECOLOUR_TARGETS=256`) |
| `MAX_PERSPECTIVE_VANISHING_POINTS` | `3` | 1-/2-/3-point (ADR-0023 §2) |
| `MAX_REFERENCE_IMAGES` | `256` | reference-board image ceiling |
| `MAX_TIMELAPSE_FRAMES` | `4096` | frame ceiling (parallels `MAX_MACRO_STEPS`/`MAX_FRAMES=4096`) |
| `MAX_DOCUMENT_VIEWS` | `8` | simultaneous views of one document |
| `DEFAULT_DOCUMENT_PPI` | `72.0` | default document PPI for real-size (BF-3) |

`GuideOrientation` and the timelapse `schema_version` string stay **module-local** enumerated vocabulary /
format-intrinsic (ADR-0001 / BF-2). `grids` clamps tile width to `[MIN_GRID_SPACING, MAX_GRID_SPACING]`.

## 9. Implementation strategy — dependency-ordered slices

Logic-first vertical slices (detailed work items in `tasks.md`):

- **9A — isometric + perspective geometry (logic)**: `constants.py` + `grids.py` (invertible iso
  transform + snap-to-vertex; perspective construction + direction-lock snap; purity/determinism/bounds).
  REQ-P9-LOGIC-001, -002, -003, -004, -008, -009, -011. AGT-03 + AGT-04 (incl. `[GEO]` SC-L001/-002/-003/-004
  + Hypothesis).
- **9B — guides/rulers + real-size scale + PPI data-model (logic)**: `guides.py` (snap + tolerance +
  ticks + readout) + `preview.py` (`real_size_scale`) + `document.ppi` field. REQ-P9-LOGIC-005, -006, -007,
  -012. AGT-03 + AGT-04 (`[GEO]` SC-L005/-006/-007).
- **9C — reproducible timelapse model (logic)**: `timelapse.py` (per-command session + deterministic
  replay). REQ-P9-LOGIC-010, -011. AGT-03 + AGT-04 (`[GEO]` SC-L010, determinism SC-L009).
- **9D — determinism/purity/single-source proof (logic)**: `check_layering`/`check_cycles`; the shared-doc
  single-source invariant (no per-view pixel copy). REQ-P9-LOGIC-008, -009, -012. AGT-03 + AGT-04.
- **9E — persistence (data)**: `timelapse_io.py` + `reference_board_io.py` + `.pixproj` v5 PPI extension.
  REQ-P9-DATA-001, -002; REQ-P9-LOGIC-007 (PPI persist). AGT-03 + AGT-04.
- **9F — preview window + overlays UI**: real-size preview (+ Qt DPI query + manual calibration),
  guides/rulers, iso + perspective overlays. REQ-P9-UI-001..005, -012, -013, -014. AGT-05 + AGT-06 + AGT-07.
- **9G — reference board + multi-view + timelapse UI**: reference board, extra views on the shared scene,
  timelapse controls. REQ-P9-UI-006, -007, -008, -009, -010, -012, -013, -014. AGT-05 + AGT-06 + AGT-07.
- **9H — render performance (16 ms with overlays + multi-view)**: REQ-P9-UI-011 (coordinated with AGT-10,
  DEP-3). AGT-05 + AGT-06 + AGT-10.

Reversibility boundary: **no** automation/aid is undoable — grids/guides/board/preview/views/recording are
view/session state and push no `QUndoCommand`; Phase 9 adds no `ui/commands.py` logic (CL-12). Only the
shipped HIS-1 drawing edits mutate the document.

## 10. Constitution compliance (self-check)

- **I:** `grids.py`/`guides.py`/`preview.py`/`timelapse.py` + the `constants.py`/`document.py` extensions
  are pure (zero Qt); `data/timelapse_io.py`/`reference_board_io.py`/`project_io.py` are Qt-free I/O; all
  overlays/preview/board/views/timelapse UI in `ui/`; no `logic → data` edge; `grids`/`guides`/`preview`
  pure leaves, `timelapse` downward-only. Phase 9 adds **no** `ui/commands.py` logic (aids non-destructive).
- **II:** ten new numerics in `constants.py`, names distinct from every shipped constant (BF-1);
  `GuideOrientation`/`schema_version` intrinsic-local (ADR-0001/BF-2).
- **IV:** invertible iso transform + snap-to-vertex, perspective construction + snap-to-guide-within-
  tolerance, guide snap, ruler ticks, real-size scale `f(PPI,DPI)`, determinism, reproducible timelapse,
  single-source live-mirror/multi-view-sync → each maps to a scenario → a headless pytest/Hypothesis test
  (the **10 `[GEO]`** rows drive dedicated AGT-04 geometry + property tests) or pytest-qt test (UI, both
  themes). Coverage gate ≥90/80.
- **V:** REQ-P9-UI-012/-013/-014 blocking gates on the visual-aids UI (a11y + both themes with role-based
  overlay/guide colours legible over artwork + full translatability).
- **VI — APPLIES THIS PHASE (unlike 7–8):** REQ-P9-UI-011 binds the 16 ms `FRAME_BUDGET_MS` to overlay +
  multi-view rendering (per-frame render loop); render/perf strategy is AGT-10's (DEP-3, §7); budget never
  relaxed.
- **VII:** timelapse + reference-board load defensive, validated, **`eval`-free** (IO-3; `TimelapseIOError`/
  `ReferenceBoardIOError`); `.pixproj` v5 defensive; malformed → user-facing error; bounded numerics
  (10 constants); portable paths (`path_portability_check`).
- **X:** every REQ traces to an S-id / F-finding / forward-inherited primitive (DOC-1, PB-1, HIS-1, CO-4,
  MC-4, IO-3) in `traceability.md` (28 REQ incl. the 2 allocated DATA REQs).
- **XI:** deferring timelapse video encoding (Phase-7 handoff), a hosted reference library / cloud sync
  (Phase 10, CL-16), staggered iso, and AI perspective inference adds capability later without weakening
  any article; the pure-geometry engine + the encoder-ready timelapse sequence are the extension seams.

## 11. Layering / cycle verification

`python scripts/check_layering.py` → exit **0** (clean, 47 modules) and `python scripts/check_cycles.py` →
exit **0** (no cycles, 108 modules) on the shipped tree at plan time (baseline, 2026-07-04). The planned
Phase-9 edges (`grids → {constants}`, `guides → {constants}`, `preview → {constants}`, `timelapse →
{document, blend, history, constants}`, `document → {constants}`, `data/timelapse_io → {logic/timelapse,
constants}`, `data/reference_board_io → {constants}`, `data/project_io → {logic/document, constants}`, and
the `ui/` visual-aids modules → `logic/`+`data/`) are acyclic by construction (§4.4); both scripts are
re-run by AGT-03 when 9A–9E land and gate the C1 analyze (Article I §4, VIII). See `analyze-report.md` for
the C1 verdict.

## 12. Decisions log

| # | Decision | Branch / choice | Rationale |
| --- | --- | --- | --- |
| PL9-D1 | Ungrounded stack/API choice? | **B (no)** | Stack fixed (S8); geometry math, timelapse cadence, reference-board landscape grounded by landed `docs/research-phase-9-visual-aids-20260704.md`. No RESEARCH REQUEST. |
| PL9-D2 | Qt in `logic/`/`data/` or magic number outside `constants.py`? | **B (no)** | All overlays/preview/board/views/timelapse in `ui/`; ten numerics → `constants.py` (names distinct); `GuideOrientation`/`schema_version` intrinsic-local (ADR-0001/BF-2). |
| PL9-D3 | grids/guides/preview/timelapse layering | — | `grids`/`guides`/`preview` pure leaves over `constants`; `timelapse` imports downward (`document`/`blend`/`history`); no `logic → data`, no `→ ui`/Qt → acyclic. |
| PL9-D4 | Isometric default (DEP-2a) | **2:1 dimetric, diamond; true-iso configurable** | Integer math, crisp lines, pixel-art standard (research §1.1); transform contract ratio-independent (ADR-0023 §1). |
| PL9-D5 | Perspective model (DEP-2e) | **Direction-lock-to-VP snap; 1-/2-/3-point; tolerance in doc-px** | Matches Clip Studio/Procreate; works freehand; dot-product math (research §2.3; ADR-0023 §2). |
| PL9-D6 | Guides/rulers (DEP-2f) | **Doc-coord guides; tol = screen-px÷zoom; nice-number ticks** | Photoshop/Aseprite model; constant stickiness (research §3; ADR-0023 §3). |
| PL9-D7 | Real-size / DPI (DEP-2c) | **`screen_DPI/doc_PPI`; Qt applies DPR (no manual mult); manual calibration fallback** | `physicalDotsPerInch` device-independent; manual DPR double-scales (research §4.2, HIGHEST-RISK); EDID unreliable → calibration (ADR-0023 §4). |
| PL9-D8 | Document PPI (BF-3) | **First-class `Document.ppi`; `.pixproj` v5; default 72.0** | Real-size is a document property; additive v5 (v1–v4 unchanged), the ADR-0006/0012/0016 precedent (ADR-0025 §1). |
| PL9-D9 | Timelapse (DEP-2b) | **Per-committed-command, document-render, reproducible; manifest not pixels; encoding deferred** | Deterministic, resolution-independent, UI-free (research §6.1/6.2); GIF reuse / MP4 deferred (§6.4; CL-16; ADR-0024 §2). |
| PL9-D10 | Reference board (DEP-2d) | **Separate scene of pixmap items; `.pixboard` {image, transform, crop, z-order}; non-destructive** | PureRef model; no pure-core geometry (research §7; ADR-0024 §3 / ADR-0025 §3). |
| PL9-D11 | `REQ-P9-DATA-*` prefix (DEP-4) | **ALLOCATE — DATA-001 (timelapse) + DATA-002 (reference board)** | Two distinct serialisers/formats; more clearly warranted than Phase-8's single one; verbatim the fixed spec contracts (not acceptance-changing; ADR-0024 §4). |
| PL9-D12 | Multi-view sync | one shared `Document` + one scene + N views | Qt shared-scene multi-view is free (`scene.changed` auto-repaint, research §5.1); builds on MC-4; no per-view copy (REQ-P9-LOGIC-012; ADR-0024 §1). |
| PL9-D13 | Performance (DEP-3) | route to AGT-10/AGT-05; **16 ms APPLIES** | Overlays + views on the per-frame render loop (unlike 7–8); cache-backed overlays + dirty-rect views; budget never relaxed (ADR-0024 §6). |
| PL9-D14 | Reversibility (CL-12) | aids push no `QUndoCommand`; no `ui/commands.py` change | Visual aids are view/session state; only HIS-1 drawing edits are undoable (mirrors Phase-4/5/6/8 view state). |
