# ADR-0023 — Visual-aids geometry & snap model: 2:1-dimetric isometric, direction-lock perspective, doc-coord guides/rulers, and real-size scale = screen_DPI / doc_PPI

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-9-visual-aids` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 9's defining acceptances are **tested-geometry contracts** (spec §1, §11; the 10 `[GEO]`
scenarios): a documented, invertible isometric transform + snap-to-nearest-vertex
(REQ-P9-LOGIC-001/-002); a deterministic perspective guide-line construction + snap-to-nearest-guide
within tolerance (REQ-P9-LOGIC-003/-004); a guide/ruler snap + tick computation (REQ-P9-LOGIC-005/-006);
and a real-size scale `f(document PPI, screen DPI)` (REQ-P9-LOGIC-007). The spec fixed each around its
**observable contract** and deferred the concrete math/defaults to architecture (DEP-2a/c/e/f, CL-2/CL-4/CL-14),
grounded by geometry-focused prior research (`docs/research-phase-9-visual-aids-20260704.md`, DEP-1). This
ADR rules those geometry HOW-decisions; the sister ADR-0024 rules the architecture/placement/persistence
and ADR-0025 the `.pixproj` schema. All geometry here is **pure `logic/`, zero Qt, unit-testable**
(Article I / S11) — the "tested geometry logic" the ROADMAP names.

The research's closed forms are honoured verbatim (its math is cross-checked against Pikuma [HIGH],
Clint Bellanger [MEDIUM] for isometric; Clip Studio / Procreate direction-lock rulers for perspective;
Aseprite for guides/rulers; Qt 6.11 `QScreen` docs [HIGH] for real-size). The transforms are standard
linear algebra; the test suite unit- and property-tests every one (the `[GEO]` rows).

## Decision

### 1. Isometric grid — 2:1 dimetric default, diamond layout, invertible transform + snap-to-vertex (REQ-P9-LOGIC-001/-002)

- **Default projection: 2:1 dimetric** (26.565° = `atan(0.5)`), `DEFAULT_ISO_GRID_RATIO = 2.0`
  (tile W:H). **True-isometric (30°)** stays a configurable ratio, not the default. Rationale
  (research §1.1, Recommendation Matrix): 2:1 is the pixel-art standard — integer math, crisp
  grid lines, no anti-alias fuzz; true-iso needs floating-point vertical steps (1.732 px). The
  transform contract does **not** change with the ratio, so exposing true-iso is additive.
- **Layout: diamond only** (research §1.6). Staggered needs a row-parity branch and is not cleanly
  invertible; if ever needed it is a *separate* function, never a parameter of the invertible core.
- **Transform (pure, invertible).** For tile width `W = tile_width`, `w = W/2`, `h = w / ratio`
  (so 2:1 ⇒ `h = W/4`... — expressed as half-height derived from the ratio), diamond world→screen:
  `sx = (i - j)·w + ox ; sy = (i + j)·h + oy`; inverse `i = sx'/(2w) + sy'/(2h)`,
  `j = sy'/(2h) - sx'/(2w)` (`sx' = sx - ox`, `sy' = sy - oy`). Round-trips exactly on lattice points
  (REQ-P9-LOGIC-001). The screen-origin `(ox, oy)` is part of `IsoGridConfig` (geometry stays
  origin-parametric; the `-w` top-corner blit offset is a *render* concern, kept out of the geometry —
  research Open-decision 1).
- **Snap-to-vertex.** `iso_snap_vertex` converts to continuous `(i, j)`, snaps to the nearest lattice
  point `round(i), round(j)`, and reprojects. **Tie-break (deterministic, REQ-P9-LOGIC-009):**
  round-half-up via `floor(v + 0.5)` on each axis, so a cursor exactly between vertices always resolves
  the same way. (Nearest-*cell* `floor(i), floor(j)` is offered for tile placement but the phase's snap
  contract is nearest-*vertex*, for line/guide drawing.)

### 2. Perspective grid — direction-lock-to-VP snap, 1-/2-/3-point, tolerance in doc-px (REQ-P9-LOGIC-003/-004)

- **Supported modes: 1-, 2-, and 3-point**, bounded by `MAX_PERSPECTIVE_VANISHING_POINTS = 3`. A
  `PerspectiveConfig` carries the mode, a horizon `y`, and the vanishing points; axis-lock families
  (screen-horizontal, screen-vertical) are modelled as **pseudo-VPs at infinity** carrying a fixed unit
  direction rather than a finite position (research §2.3).
- **Guide-line construction (render aid, deterministic).** `perspective_guide_lines(config, samples)`
  produces the fan of segments from evenly-spaced sample points on a reference edge toward each VP — a
  documented deterministic function of the config (REQ-P9-LOGIC-003). This is for *display*, not the
  snap primitive.
- **Snap contract: direction-lock to the nearest VP** (research §2.3, the tool-standard model in Clip
  Studio / Procreate). Given anchor `A` and cursor `C`, for each VP: `d = normalize(V − A)` (or the
  pseudo-VP's fixed unit `d`), `t = dot(C − A, d)`, `proj = A + t·d`, `err = ‖(C − A) − t·d‖`. Snap to
  the VP with the smallest `err` **iff `err ≤ tolerance`**; else **no snap** (returns `None`,
  REQ-P9-LOGIC-004). **Tie-break:** on equal `err`, the lowest VP index wins (deterministic). Degenerate
  `A == V` skips that VP. `tolerance` is in **document px** (see §3). The nearest-discrete-guide model
  (research §2.4) is *not* the default — direction-lock works freehand and is what commercial tools
  ship.
- **Default configuration** (DEP-2e): 2-point on the horizon is the default active mode; VPs are
  user-configurable (draggable in the UI); axis-lock pseudo-VPs are always available. These are
  render/UX defaults; the snap/construction contracts above are fixed regardless.

### 3. Guides & rulers — document-coordinate guides, screen-px÷zoom tolerance, nice-number ticks (REQ-P9-LOGIC-005/-006)

- **Guide model: document coordinates** (research §3.1, the Photoshop/Aseprite model). A guide is one
  scalar in doc space + an orientation (`HORIZONTAL` = a `y`, `VERTICAL` = an `x`); `GuideOrientation` is
  a **module-local enumerated vocabulary** (ADR-0001 / BF-2, the `BlendMode` precedent). Guide count is
  bounded by `MAX_GUIDES`.
- **Snap semantics: tolerance in screen px, applied in doc space.** `screen_tolerance_to_doc(tol_px,
  zoom) = tol_px / zoom` (research §3.2/§3.3), so perceived "stickiness" is constant at every zoom
  (`DEFAULT_SNAP_TOLERANCE_PX = 8`). `snap_guides(x, y, guides, tol_doc)` snaps **independently on each
  axis** to the nearest guide within `tol_doc`, unchanged if none. **Tie-break:** guides are considered
  in ascending `position`; on equal distance the lowest position wins (deterministic,
  REQ-P9-LOGIC-009).
- **Ruler ticks & readout (pure).** `ruler_ticks(doc_length, zoom, offset, axis_pixels)` uses a
  **nice-number ladder** `{1, 2, 5}·10ⁿ` choosing the smallest step with `step·zoom ≥
  min-label-spacing` (research §3.1); labels are **locale-independent** integer strings (no thousands
  separators, no locale formatting — REQ-P9-LOGIC-009). `coordinate_readout(sx, sy, zoom, offset)`
  returns the integer doc coordinate. Both are pure functions of the view parameters — unit-testable
  without Qt (REQ-P9-LOGIC-006).

### 4. Real-size scale — `screen_DPI / doc_PPI`, Qt applies DPR, manual-calibration fallback (REQ-P9-LOGIC-007)

- **Pure formula (logic/).** `real_size_scale(doc_ppi, screen_dpi) = screen_dpi / doc_ppi` — the
  device-independent screen-px-per-doc-px factor (research §4.1). Pure and deterministic; lives in
  `logic/preview.py`, **zero Qt**.
- **DPR handling — the highest-risk area (research §4.2, §10).** The scale is applied in
  **device-independent** Qt/`QGraphicsView` coordinates and **Qt applies `devicePixelRatio()`
  automatically**. `physicalDotsPerInch()` is *already* device-independent, so the UI must **NOT**
  multiply by DPR itself — doing so double-scales (2× too big on a 2× HiDPI display). The Qt DPI *query*
  (`QScreen.physicalDotsPerInch()`) lives in `ui/` (it is a Qt call); the *math* stays in
  `logic/preview.py`. Recompute on `QWindow.screenChanged` / `physicalDotSizeChanged` when the preview
  moves between monitors.
- **Manual-calibration fallback (shipped).** Because monitor EDID is frequently wrong/absent,
  `physicalDotsPerInch()` is unreliable; the UI ships a **manual on-screen-ruler calibration** (drag to
  match a real ruler / credit-card) that stores a measured screen DPI, which is fed to the *same* pure
  `real_size_scale`. This is the only reliable route to true real-size on arbitrary hardware
  (research §4.3, Recommendation Matrix). The calibrated DPI is a per-monitor UI/preview setting; the
  document's PPI is a document property (ADR-0025 / BF-3).

## Alternatives Considered

- **True-isometric (30°) as the default.** Rejected: needs floating-point vertical steps and fuzzy grid
  lines; not the pixel-art standard. Kept configurable via the ratio.
- **Staggered isometric layout.** Rejected for the core: row-parity branch is not cleanly invertible
  (research §1.6). A separate function if ever required.
- **Nearest-discrete-guide perspective snap (research §2.4).** Rejected as the default: only meaningful
  for a fixed visible fan; direction-lock works freehand and matches commercial tools. Available as an
  option if a snappable visible grid is later added.
- **Screen-space guides / fixed-px tolerance.** Rejected: breaks at zoom; the doc-coord guide +
  screen-px÷zoom tolerance keeps stickiness constant (research §3.3).
- **Manually applying DPR to the real-size scale.** Rejected: double-scales on HiDPI; Qt already applies
  it because `physicalDotsPerInch()` is device-independent (research §4.2, the highest-risk finding).
- **Locale-formatted ruler labels.** Rejected: violates determinism (REQ-P9-LOGIC-009); labels are bare
  integers.

## Consequences

**Positive.** Every snap/transform/scale is a pure, deterministic, invertible-where-claimed function with
a documented tie-break — directly unit- and property-testable by the test suite without any GUI (the `[GEO]`
backbone), and the *same* function the overlays call (REQ-P9-LOGIC-008). Choosing 2:1 dimetric vs
true-iso, the perspective default mode, or the snap tolerance changes **no** acceptance criterion. The
real-size scale is a one-line pure function; the DPR risk is contained by "let Qt apply DPR" + a manual
calibration fallback.

**Negative / risk.** The DPR/real-size interaction is version- and platform-sensitive and must be
verified empirically on a HiDPI **and** a fractional-scaling display before ship (research §10) —
flagged to the UI implementation/QA as the real-size DPI risk. Perspective math is grounded in art-tool behaviour,
not a formal geometry citation (research §10); the test suite must unit-test the projection equations. Snap
tie-breaks are conventions (round-half-up, lowest-index, lowest-position) — documented here so tests and
implementation agree.

## Grounding

- Spec `specs/phase-9-visual-aids/spec.md` §1–§2 (tested-geometry framing), §4
  (REQ-P9-LOGIC-001..007), §6 (non-goals — geometry model deferred to architecture/ADR), §8 (DEP-1/DEP-2,
  BF-1/BF-2), §9 Article I/II/IV, §10 CL-2/CL-4/CL-14, §11 SC-L001-1..L007-1; `traceability.md`
  DEP-1/DEP-2, `[GEO]` rows.
- Research `docs/research-phase-9-visual-aids-20260704.md` §1 (iso 2:1 vs true-iso; diamond; §1.3–1.5
  transform/inverse/snap), §2 (perspective VP model; §2.3 direction-lock snap), §3 (guides in doc
  coords; §3.2 snap_axis; §3.3 tolerance = screen-px÷zoom), §4 (real-size = screen_DPI/doc_PPI; §4.2
  DPR device-independence; §4.3 EDID unreliability + calibration), §8 Recommendation Matrix, §10
  Limitations.
- Shipped `logic/pixel_buffer.py` (PB-1), `logic/document.py` (DOC-1), `logic/blend.py`
  `composite_stack` (CO-4). Constitution Article I (three-layer purity — geometry out of `ui/`),
  Article II (numerics in `constants.py`), Article IV (each `[GEO]` contract → a test). ADR-0001
  (intrinsic-local vocabulary — `GuideOrientation`), ADR-0024 (architecture/placement this geometry
  lands in), ADR-0025 (`.pixproj` v5 + Document PPI, BF-3).
