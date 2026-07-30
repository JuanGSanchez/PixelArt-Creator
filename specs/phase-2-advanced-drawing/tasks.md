# Tasks — Phase 2: Advanced Drawing System

| Field | Value |
| --- | --- |
| Feature | `phase-2-advanced-drawing` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-02 |
| Derived from | `specs/phase-2-advanced-drawing/plan.md` §3–§8 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VIII, X) |
| Scope | Full Phase-2 build, sliced **2A LOGIC → 2B UI** (+ optional early shape micro-slice). Every REQ-P2-* maps to ≥1 task. |

Status legend: `todo` · `doing` · `done`.
Each task: **id · owner · target file(s) · predecessor · REQ/acceptance link · status.**

The C1 gate (`sdd-analyze`) is run over constitution/spec/plan/tasks as the pre-implement gate
(see analyze report). Article VIII: no implement dispatch past a red gate; layering/cycles must
exit 0 at each slice boundary.

---

## Slice 2A — Advanced-drawing LOGIC (`REQ-P2-LOGIC-001..015`) — Qt-free

### T1 — New constants → `logic/constants.py`
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/constants.py` · **Predecessor:** — (root)
- **Do:** Add, each with a source-citation comment (keep leaf, no intra-package imports):
  `ROTSPRITE_UPSCALE_FACTOR = 8`, `ROTSPRITE_SIMILARITY_THRESHOLD = 100`,
  `MAGIC_WAND_DEFAULT_TOLERANCE = 0`, `TILED_PREVIEW_REPEAT = 3`, `SCALE_MIN_FACTOR = 0.01`,
  `SCALE_MAX_FACTOR = 64.0`. (`SymmetryAxis` is module-local — T4, plan PL-D3.)
- **REQ/acceptance:** NFR-5 / Article II; SC-L013-5 (upscale factor from constants).
- **Status:** todo

### T2 — `logic/selection.py` (mask model + builders + ops + mask-constrained apply + move)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/selection.py` · **Predecessor:** T1
- **Do:** Implement `SelectionError(ValueError)`, `SelectionMask` (plan §6.1 surface), builders
  `rect_mask`/`lasso_mask` (even-odd scanline, auto-close)/`wand_mask` (reuse `flood_fill`
  contiguity + `color.distance_sq`; INDEXED exact, CL-16), `apply_masked` (CL-5), and
  `move_selection` (lift → transparent/index 0 vacated, CL-6; returns reversible `PixelEdit`).
  Zero Qt; typed; docstrings.
- **REQ/acceptance:** REQ-P2-LOGIC-001..006 (SC-L001..006), REQ-P2-LOGIC-010 (mask side);
  SC-L005-6 reversibility.
- **Status:** todo

### T3 — `logic/transform.py` (flip / rotate-90 / scale-NN + selection-aware + reversible builder)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/transform.py` · **Predecessor:** T1, T2
- **Do:** Implement `TransformError(ValueError)`, `flip_horizontal/vertical`,
  `rotate_90_cw/ccw` (W/H swap, CL-8), `scale_nearest` (NN only, CL-7; `SCALE_MIN/MAX_FACTOR`
  + non-positive → `TransformError`), and `make_transform_command` (whole-buffer dims-changing →
  `FunctionCommand`; same-dims / selection-region → `PixelEdit`; selection variant touches only
  masked pixels, plan §6.2/§7).
- **REQ/acceptance:** REQ-P2-LOGIC-007..010 (SC-L007..010); no-new-colours SC-L007-2/-008-4/
  -009-2/-5; reversibility SC-L010-3.
- **Status:** todo

### T4 — `logic/symmetry.py` (`SymmetryAxis` enum + `mirror`)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/symmetry.py` · **Predecessor:** T1
- **Do:** Module-local `SymmetryAxis(enum.Enum)` = NONE/VERTICAL/HORIZONTAL/BOTH/DIAGONAL
  (PL-D3); `mirror(x, y, axis, width, height, axis_pos=None)` → de-duplicated, in-bounds mirror
  set (VERTICAL `(W-1-x,y)`, HORIZONTAL `(x,H-1-y)`, BOTH 4-way, DIAGONAL main diagonal, NONE
  passthrough); `axis_pos` defaults to centre (CL-9). Zero Qt.
- **REQ/acceptance:** REQ-P2-LOGIC-011 (SC-L011-1..6).
- **Status:** todo

### T5 — `logic/pixel_perfect.py` (elbow-removal)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/pixel_perfect.py` · **Predecessor:** T1
- **Do:** `pixel_perfect(coords)` implementing the Aseprite rule (research Topic 2): drop the
  interior elbow pixel of every L-triple; endpoints untouched; idempotent; order-preserving;
  deterministic. Leaf module, zero Qt.
- **REQ/acceptance:** REQ-P2-LOGIC-012 (SC-L012-1..4).
- **Status:** todo

### T6 — `logic/rotsprite.py` (clean arbitrary-angle rotation) — the four pinned choices
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/rotsprite.py` · **Predecessor:** T1
- **Do:** `rotsprite(buffer, angle_degrees, *, pivot=None, fill=None)` per plan §5/§6.3:
  upscale ×`ROTSPRITE_UPSCALE_FACTOR` (three similarity-Scale2× passes,
  `distance_sq <= ROTSPRITE_SIMILARITY_THRESHOLD`) → offset search (lexicographic tie-break) →
  NN rotate+downscale → detail restore. **Pinned acceptance:** pivot = grid centre
  `((W-1)/2,(H-1)/2)`; OOB fill = transparent RGBA `(0,0,0,0)` / index 0; copy-only ⇒ output
  colour set ⊆ input; deterministic; 0°/360° identity. Plus `make_rotsprite_command`
  (`FunctionCommand`). Grounded by `docs/research-rotsprite-pixelperfect.md` + ADR-0002.
- **REQ/acceptance:** REQ-P2-LOGIC-013 (SC-L013-1..5); SC-L013-1 no-new-colours **acceptance-critical**.
- **Status:** todo

### T7 — `logic/tiled.py` (torus wrap + 3×3 preview + reversible wrapped edit)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/tiled.py` · **Predecessor:** T1
- **Do:** `wrap(x, y, w, h)` → `(x % W, y % H)` (handles negatives, CL-14); `preview_tiling(buffer,
  repeat=TILED_PREVIEW_REPEAT)` → 3×3 arrangement (CL-13); `make_tiled_command(buffer, operation)`
  → reversible `PixelEdit` of wrapped changed pixels. Zero Qt.
- **REQ/acceptance:** REQ-P2-LOGIC-014 (SC-L014-1..4); reversibility SC-L014-4.
- **Status:** todo

### T8 — Reversible-op integration audit (all 2A ops → `history.Command`)
- **Owner:** AGT-03 · **Target:** `logic/selection.py`, `transform.py`, `rotsprite.py`, `tiled.py`
  · **Predecessor:** T2, T3, T6, T7
- **Do:** Confirm every mutating op returns a `history.Command` (`PixelEdit` for same-dim diffs;
  `FunctionCommand` for dim-changing/whole-buffer replaces, plan §7) with `apply ∘ undo = identity`,
  and imports **zero Qt**. No new module — cross-cutting closure of REQ-P2-LOGIC-015.
- **REQ/acceptance:** REQ-P2-LOGIC-015 (SC-L015-1); SC-L015-2 (Qt-free, gate-verified at T10).
- **Status:** todo

### T9 — Logic tests (pytest + Hypothesis) for all 2A modules
- **Owner:** AGT-04 · **Target:** `tests/logic/test_selection.py`, `test_transform.py`,
  `test_symmetry.py`, `test_pixel_perfect.py`, `test_rotsprite.py`, `test_tiled.py`
  · **Predecessor:** T2, T3, T4, T5, T6, T7, T8
- **Do:** One test per SC-L001..015 scenario. **Hypothesis** invariants: mask op algebra
  (`invert∘invert`, combine identities), transform reversibility (`apply∘undo = identity`),
  RotSprite **no-new-colours** (output colour set ⊆ input) + 0°/360° identity + transparent-stays-
  transparent, tiled wrap `mod` identity, pixel-perfect idempotence. Coverage gate ≥90 % line /
  ≥80 % branch; **invoke `python scripts/coverage_gate.py`** (P11). Deterministic/portable.
- **REQ/acceptance:** Article IV (one test per criterion); NFR-2/-3/-4/-6.
- **Status:** todo

### T10 — Slice-2A layering/cycle gate (AGT-01)
- **Owner:** AGT-01 · **Target:** `pixelart_creator/` · **Predecessor:** T9
- **Do:** **Invoke `python scripts/check_layering.py` and `python scripts/check_cycles.py`** —
  both must exit 0 (Article I; Decision A1-D3): the six new `logic/` modules import zero Qt and
  add no cycle. Script exit 2 → BLOCKED (A1-E3). Confirms SC-L015-2 (Qt-free purity).
- **REQ/acceptance:** Article I; REQ-P2-LOGIC-015 (SC-L015-2).
- **Status:** todo

## Slice 2B — Advanced-drawing UI (`REQ-P2-UI-001..015`) — depends on 2A + stable Phase-1 UI

### T11 — Shape tools UI (optional early micro-slice)
- **Owner:** AGT-05 · **Target:** `ui/tools/rectangle_tool.py`, `ui/tools/ellipse_tool.py`,
  shape filled/outline option · **Predecessor:** Phase-1 UI substrate stable (PL-D4) — **no 2A dep**
- **Do:** Rectangle + ellipse tool controllers: live preview drag, commit-on-release as one
  `QUndoCommand` (via `ui/commands.py` + `record_edit` over `drawing.rectangle`/`ellipse`), active
  colour, shared filled/outline option (default **outline**, CL-17). tr()-wrapped;
  `changeEvent` retranslate; no domain logic in the widget.
- **REQ/acceptance:** REQ-P2-UI-001, -002, -003 (SC-U001..003); reversibility SC-U001-3/-002-3.
- **Status:** todo

### T12 — Selection tools + overlay + move
- **Owner:** AGT-05 · **Target:** `ui/tools/rect_select_tool.py`, `lasso_tool.py`,
  `magic_wand_tool.py`, `ui/selection_overlay.py` · **Predecessor:** T2, T11 (tool pattern)
- **Do:** Three selection tools (bind to `selection` builders; wand tolerance control default
  `MAGIC_WAND_DEFAULT_TOLERANCE`; combine modifiers Shift-add/Alt-subtract, CL-4); marching-ants
  overlay legible in **both themes**; drag-in-selection move → `selection.move_selection` as one
  `QUndoCommand`. tr()-wrapped; keyboard-reachable.
- **REQ/acceptance:** REQ-P2-UI-004..007 (SC-U004..007); reversibility SC-U007-3.
- **Status:** todo

### T13 — Transform + RotSprite actions/dialogs
- **Owner:** AGT-05 · **Target:** `ui/transform_dialog.py`, `ui/rotsprite_dialog.py`,
  `ui/main_window.py` (flip/rotate-90 actions) · **Predecessor:** T3, T6, T12 (selection target)
- **Do:** flip-H/V + rotate-90-CW/CCW actions; scale dialog (factor/target size, NN); RotSprite
  angle dialog + preview. Each applies to buffer or active selection (LOGIC-010) as one
  `QUndoCommand`. tr()-wrapped, keyboard-reachable, both themes. UI adds no colour of its own
  (no-new-colours surfaced only through logic behaviour).
- **REQ/acceptance:** REQ-P2-UI-009, -010 (SC-U009..010); no-new-colours SC-U009-2/-010-2.
- **Status:** todo

### T14 — Symmetry / pixel-perfect / tiled / grid-snap / AA-off UI
- **Owner:** AGT-05 · **Target:** `ui/symmetry_panel.py`, `ui/tiled_mode.py`,
  `ui/main_window.py` (selection-op actions + pixel-perfect + grid/snap + AA-off toggles),
  `ui/canvas_view.py`/`ui/canvas_scene.py` (AA-off render-hint lock, grid/snap) · **Predecessor:** T4, T5, T7, T12
- **Do:** `SymmetryAxis` selector → live mirrored strokes within one command (LOGIC-011);
  pixel-perfect pencil toggle routing through `pixel_perfect` (LOGIC-012); tiled-mode toggle +
  3×3 preview + wrapped edits (LOGIC-014); grid-overlay/snapping refinements; forced AA-off
  (render hints never enable antialias/smooth-pixmap-transform, CL-15) across canvas + all
  previews; selection-op actions (invert/clear/deselect/select-all). tr()-wrapped, keyboard-
  reachable, both themes.
- **REQ/acceptance:** REQ-P2-UI-008, -011, -012, -013, -014, -015 (SC-U008, U011..015);
  reversibility SC-U011-3/-015-3.
- **Status:** todo

### T15 — `ui/commands.py` QUndoCommand wrappers for all new ops
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/commands.py` · **Predecessor:** T8, T12, T13, T14
- **Do:** One `QUndoCommand` wrapper per new mutating op, delegating to the `history.Command`
  the logic returns (selection move, flip, rotate-90, scale, RotSprite, symmetry stroke,
  pixel-perfect stroke, tiled edit). No domain math in the bridge (S11); only Qt + dirty-rect
  signalling. Sole Qt file outside `ui/tools`/views.
- **REQ/acceptance:** REQ-P2-LOGIC-015 + all reversibility SC-U*-3 (one undoable step per op).
- **Status:** todo

### T16 — UI tests (pytest-qt, both themes, a11y, headless)
- **Owner:** AGT-06 · **Target:** `tests/ui/test_rectangle_tool.py`, `test_ellipse_tool.py`,
  `test_shape_mode.py`, `test_rect_select_tool.py`, `test_lasso_tool.py`, `test_magic_wand_tool.py`,
  `test_selection_overlay.py`, `test_selection_actions.py`, `test_transform_actions.py`,
  `test_rotsprite_action.py`, `test_symmetry.py`, `test_pixel_perfect.py`, `test_grid_snap.py`,
  `test_aa_off.py`, `test_tiled_mode.py` · **Predecessor:** T11, T12, T13, T14, T15
- **Do:** One pytest-qt test per SC-U001..015 scenario; qtbot; wait on signals; **both light and
  dark themes**; a11y (accessible name, keyboard reachability, focus visibility); headless
  `QT_QPA_PLATFORM=offscreen`. Coverage gate ≥90/80. Re-run `sdd-checklist` inputs.
- **REQ/acceptance:** Article IV + V; all SC-U* + reversibility/no-new-colours UI scenarios.
- **Status:** todo

### T17 — i18n extraction for new UI strings
- **Owner:** AGT-07 · **Target:** `ui/` `.ts` catalogues (+ `string_audit_check`) · **Predecessor:** T11, T12, T13, T14, T15
- **Do:** Run `string_audit_check` (report unwrapped strings → AGT-05 fixes); extract wrapped
  strings with `pyside6-lupdate`; compile `.qm`; confirm `changeEvent` retranslate on the new
  widgets (F5/F6).
- **REQ/acceptance:** Article V §2; NFR-7.
- **Status:** todo

### T18 — Perf directive (CONDITIONAL — only if a new perf-sensitive render path)
- **Owner:** AGT-10 · **Target:** perf directive → AGT-05 (`ui/selection_overlay.py`,
  `ui/tiled_mode.py`) · **Predecessor:** T12, T14
- **Do:** Run `perf_profile` on the two new render paths (selection-overlay redraw; tiled 3×3
  preview) at 8K. Only if over `FRAME_BUDGET_MS = 16`: issue a culling/dirty-rect/scene-rect
  directive AGT-05 implements — budget never relaxed (Article VI). If in-budget, task closes as
  no-op. Decision A1: conditional on a new perf path existing (plan §10).
- **REQ/acceptance:** Article VI; NFR-8.
- **Status:** todo (conditional)

### T19 — Docs (usage + CHANGELOG + mkdocs)
- **Owner:** AGT-08 · **Target:** `docs/` (usage pages, `CHANGELOG.md` Unreleased) · **Predecessor:** T16
- **Do:** Document the new tools/actions/toggles; add CHANGELOG Added entries keyed to REQ-IDs;
  refresh mkdocs API pages from docstrings; run pydocstyle gate. ADR-0002 (RotSprite pins) filed
  under `docs/adr/` (authored by AGT-01, §hand-off).
- **REQ/acceptance:** Article III §4 (docstrings); durable-docs coverage.
- **Status:** todo

### T20 — Commit(s), REQ-tagged, gate-green
- **Owner:** AGT-09 · **Target:** git (Conventional Commits) · **Predecessor:** T16, T17, T19 (+ T18 if triggered)
- **Do:** Commit 2A + 2B in gate-green increments (`feat(logic): …` / `feat(ui): …`) carrying the
  governing REQ-P2-* ids; each leaves quality + tests + coverage + layering + SDD gates green
  (Article IX). Human checkpoint before any push/tag.
- **REQ/acceptance:** Article IX.
- **Status:** todo

---

## Dependency graph

```
Slice 2A:
  T1 ─┬─> T2 ─┬─> T3 ─┐
      ├─> T4  │       ├─> T8 ─> T9 ─> T10
      ├─> T5  ├─> T6 ─┤
      └─> T7 ─┘       │
                (T2,T3,T6,T7 -> T8)

Slice 2B (after T10 + stable Phase-1 UI):
  T11 ─> T12 ─┬─> T13 ─┐
              └─> T14 ─┼─> T15 ─> T16 ─┬─> T19 ─> T20
                       │               │
              (T12,T14) ─> T18 ────────┘ (conditional)
                              T17 ──────────────────> T20
```

Parallelisable after T1: {T2, T4, T5, T7} (T3 needs T2; T6 independent of T2/T3). Slice 2B
begins only after T10 (2A gate green) **and** a stable Phase-1 UI substrate (PL-D4). T11 (shape
micro-slice) needs no 2A logic and may front-run. T18 fires only if a render path is over budget.

## REQ → task coverage (every REQ-P2-* maps to ≥1 task)

| REQ | Task(s) | | REQ | Task(s) |
| --- | --- | --- | --- | --- |
| REQ-P2-LOGIC-001 | T2, T9 | | REQ-P2-UI-001 | T11, T16 |
| REQ-P2-LOGIC-002 | T2, T9 | | REQ-P2-UI-002 | T11, T16 |
| REQ-P2-LOGIC-003 | T2, T9 | | REQ-P2-UI-003 | T11, T16 |
| REQ-P2-LOGIC-004 | T2, T9 | | REQ-P2-UI-004 | T12, T16 |
| REQ-P2-LOGIC-005 | T2, T9 | | REQ-P2-UI-005 | T12, T16 |
| REQ-P2-LOGIC-006 | T2, T9 | | REQ-P2-UI-006 | T12, T16 |
| REQ-P2-LOGIC-007 | T3, T9 | | REQ-P2-UI-007 | T12, T16 |
| REQ-P2-LOGIC-008 | T3, T9 | | REQ-P2-UI-008 | T14, T16 |
| REQ-P2-LOGIC-009 | T3, T9 | | REQ-P2-UI-009 | T13, T16 |
| REQ-P2-LOGIC-010 | T2, T3, T9 | | REQ-P2-UI-010 | T13, T16 |
| REQ-P2-LOGIC-011 | T4, T9 | | REQ-P2-UI-011 | T14, T16 |
| REQ-P2-LOGIC-012 | T5, T9 | | REQ-P2-UI-012 | T14, T16 |
| REQ-P2-LOGIC-013 | T6, T9 | | REQ-P2-UI-013 | T14, T16 |
| REQ-P2-LOGIC-014 | T7, T9 | | REQ-P2-UI-014 | T14, T16 |
| REQ-P2-LOGIC-015 | T8, T9, T10, T15 | | REQ-P2-UI-015 | T14, T16 |

All 30 REQ-P2-* map to ≥1 implementation task **and** ≥1 test task (T9 logic / T16 UI).
Cross-cutting: new constants T1 (Art. II); i18n T17 (Art. V); perf T18 (Art. VI, conditional);
gates T10 + this-session `sdd-analyze` (Art. I/VIII); commits T20 (Art. IX).

## Hand-offs

- **AGT-08:** file **ADR-0002** (RotSprite four pinned choices, plan §5) under `docs/adr/` —
  authored by AGT-01; immutable acceptance for T6.
- **AGT-02:** traceability matrix already lists all 30 REQ ↔ SC ↔ test targets; no delta needed
  (module paths in the matrix match this plan's §3.2).
