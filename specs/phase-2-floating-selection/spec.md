# Specification — Floating-Selection Move / Copy (REQ-NEW-C)

| Field | Value |
| --- | --- |
| Feature | `phase-2-floating-selection` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-03 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — extends shipped Phase-2 selection; no code exists for the floating-preview model yet |
| REQ-ID range | `REQ-P2-LOGIC-030..036`, `REQ-P2-UI-030..036` (dedicated sub-band; avoids collision with shipped `REQ-P2-*-001..015`) |
| User requirement | REQ-NEW-C (user-resolved, `docs/decisions-20260701.md` L172–184; USER directives 2026-07-02) |
| Layer scope | `pixelart_creator/logic/selection.py` (extend: floating-selection model + copy commit) + `pixelart_creator/ui/` (move-interaction controller, floating-preview overlay, key/tool-switch lifecycle) |
| Binds to (upstream) | `specs/phase-2-advanced-drawing/spec.md` (shipped `SelectionMask`, `rect_mask`/`lasso_mask`/`wand_mask`, `move_selection`, `apply_masked`, selection-overlay/move UI REQ-P2-UI-007); Phase-1 `logic/pixel_buffer.py`, `logic/history.py`; ADR-0008 (`Document.mode` authority) |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) → `sdd-tasks` |

---

## 1. Purpose (WHY)

Shipped Phase-2 gives an artist a `SelectionMask` (rectangle / lasso / magic-wand) and a
**destructive one-shot** cut-move (`logic/selection.move_selection`, REQ-P2-LOGIC-005 /
REQ-P2-UI-007): the move produces its reversible command immediately, so the underlying
pixels are rewritten the moment the selection is dragged.

REQ-NEW-C (user-resolved) upgrades this to the behaviour every mature pixel editor
(Aseprite, Pro Motion NG, Pixelorama, Krita) provides — a **floating selection**:

- Selecting a region and dragging it moves the region's **colours** as a **non-destructive
  floating preview**. The pixels *beneath* the floating selection are **not overwritten
  until the move is committed**.
- **DRAG = MOVE**: on lift, the origin region reads as cleared to transparent in the live
  preview; on commit the origin is written transparent and the colours are stamped at the
  destination.
- **MODIFIER (Ctrl) + DRAG = COPY**: the origin is kept intact and a copy floats;
  on commit only the destination is stamped. (Ctrl only — **not** Alt; an interior
  Alt-drag is the shipped selection-build SUBTRACT gesture — CL-F5.)
- Operates on the **active layer**.
- **ESC cancels** (restores the exact pre-move state); the move **commits on mouse-release,
  Enter, or tool-switch**.

This document specifies **WHAT** each behaviour must do and **WHY**, technology-neutral at
the requirement level. The HOW (the floating-item overlay class, how the preview composite
is painted into `QGraphicsScene`, event routing) belongs to `sdd-plan`/AGT-01, AGT-05 (UI),
AGT-10 (render), and AGT-03 (logic). Every committed move/copy is a **single reversible
command** wrapped as one `QUndoCommand` via `ui/commands.py` over `logic/history.py`
(Article I / S7); the domain logic stays Qt-free (Article I / S11).

## 2. Scope

**In scope (WHAT) — logic (`logic/selection.py`, Qt-free):**
- A **floating-selection model** that, at lift time, captures the masked pixel **colours**
  from a single source buffer (the active layer's buffer) plus the source `SelectionMask`
  and a live integer offset `(dx, dy)` — **without mutating the source buffer** (the float
  is a copy of the lifted colours).
- A **non-destructive preview composite**: given the floating selection, a base buffer, and
  the current offset, produce a preview buffer (base with the floated colours stamped at the
  offset; for MOVE the origin also reads vacated) **without mutating the base**. This is what
  the UI renders each frame.
- A **MOVE commit** builder: one reversible command that vacates the origin
  (transparent RGBA / index 0 indexed — CL-F2) and stamps the floated colours at the final
  offset, clipped to bounds. Semantically identical to the shipped `move_selection`.
- A **COPY commit** builder: one reversible command that stamps the floated colours at the
  final offset **without** vacating the origin, clipped to bounds.
- **Off-canvas clipping** at commit (CL-F1); **cancel** is a pure no-op on the buffer
  (CL-F6); the source is an existing non-empty `SelectionMask` from the shipped
  rect/lasso/wand builders (CL-F4).

**In scope (WHAT) — UI (`ui/`):**
- A **move interaction** on the active selection: press inside the active mask to lift the
  active layer's masked pixels into a floating selection and begin a drag; the canvas shows
  the floating preview following the cursor (non-destructive).
- **Mode affordance**: plain drag = MOVE (origin reads transparent in preview); **Ctrl**
  during the drag = COPY (origin stays intact; cursor/affordance signals copy).
- **Lifecycle**: commit on mouse-release, **Enter**, or **tool-switch** as exactly one
  undoable command; **ESC** cancels and restores the pre-move canvas exactly.
- Preview rendering is nearest-neighbour / anti-aliasing-off and legible in **both themes**;
  any new user-visible control is `tr()`-wrapped and keyboard-reachable.

**Out of scope (this feature):**
- Rotating/scaling the floating selection while it floats (that is the shipped transform
  path REQ-P2-LOGIC-010 applied after commit; free-transform-while-floating is deferred).
- A **move-all-layers** variant (CL-F3 — deferred; active-layer only here).
- Cross-document / cross-canvas drag of a floating selection (deferred).
- Multi-layer indexed compositing (ADR-0008: indexed documents are single-layer; the move
  operates on that one layer).
- No new technology choices (stack fixed by S8); no plan / tasks / code (AGT-01 / AGT-03 /
  AGT-05).

## 3. Story map & feature-label taxonomy

Extends the Phase-2 taxonomy (`selection`, `selection-ops`). New label: `floating-selection`
(P2).

### 3.1 User stories

- **US-F1 (Artist / float-move).** As an artist, I want to **drag a selected region and see
  its colours float as a live preview** without the pixels underneath being changed yet, so
  I can position it precisely before committing. →
  REQ-P2-LOGIC-030, -031, -032, REQ-P2-UI-030, -031, -033 · `floating-selection` · P2
- **US-F2 (Artist / float-copy).** As an artist, I want to **hold Ctrl while dragging**
  to leave the original in place and stamp a **copy** at the destination, so I can duplicate
  regions quickly. →
  REQ-P2-LOGIC-033, REQ-P2-UI-032 · `floating-selection` · P2
- **US-F3 (Artist / non-destructive).** As an artist, I want the pixels **beneath** the
  floating selection to stay untouched until I commit, so a move is safe to re-position or
  abandon. → REQ-P2-LOGIC-031, -034, REQ-P2-UI-030, -034 · `floating-selection` · P2
- **US-F4 (Artist / commit & cancel).** As an artist, I want the float to **commit on
  release / Enter / tool-switch** and **ESC to cancel** and restore exactly, so the
  interaction matches every editor I know. →
  REQ-P2-LOGIC-032, -033, -034, REQ-P2-UI-033, -034 · `floating-selection` · P2
- **US-F5 (Artist / off-canvas).** As an artist, I want to be able to drag a float partly
  off the canvas and have the off-canvas part discarded on commit, so I can push art to the
  edge without error. → REQ-P2-LOGIC-035, REQ-P2-UI-036 · `floating-selection` · P2
- **US-F6 (Artist / reversibility).** As an artist, I want a committed move or copy to be
  **one undoable step**. → REQ-P2-LOGIC-032, -033 (reversibility), REQ-P2-UI-035 ·
  `undo-redo` · P2 (extends P1)

### 3.2 Feature-label taxonomy (addition)

`floating-selection` — P2, aligned to REQ-NEW-C and the shipped `selection` / `selection-ops`
labels; extensible without renaming.

## 4. Functional requirements

Each REQ carries `traces:` to the dossier S-id(s) it realises and the user requirement
(REQ-NEW-C). Layer, owner agent, and acceptance scenarios are in `traceability.md`.

### 4.1 Logic layer (`REQ-P2-LOGIC-030..036`) — `logic/selection.py` (extend)

#### REQ-P2-LOGIC-030 — Floating-selection model (lift/float)
`traces:` S2 (region editing), S1 (per-pixel grid); REQ-NEW-C; builds on REQ-P2-LOGIC-001/-005
A floating-selection value (e.g. `FloatingSelection`) is created from a **source buffer**
and a non-empty `SelectionMask`, capturing (a) the **colours** of the masked pixels as an
independent copy, (b) the source mask, (c) a **mode** flag (`MOVE` / `COPY`), and (d) a live
integer offset `(dx, dy)` (initially `(0, 0)`). **Constructing the float does not mutate the
source buffer** — it is a snapshot of the lifted colours. An **empty** mask yields no float
(raises `SelectionError`, matching the Phase-1 domain-error convention, or a documented
no-float sentinel — AGT-01 to fix the exact contract). Zero Qt.

#### REQ-P2-LOGIC-031 — Non-destructive preview composite
`traces:` S2, S5 (canvas display); REQ-NEW-C
Given a floating selection, a **base buffer**, and the current offset, a pure function
returns a **preview buffer**: a copy of the base with the floated colours stamped at the
offset (clipped to bounds), and — for **MOVE** mode — the origin (the source-mask pixels)
read as **vacated** (transparent RGBA / index 0 indexed). For **COPY** mode the origin is
left intact. **The base buffer is never mutated.** Deterministic; identical input → identical
preview. Zero Qt. (This is the display substrate; the UI need not re-implement compositing.)

#### REQ-P2-LOGIC-032 — Move commit (drag = move)
`traces:` S2, S7 (reversible command, C1/F1); REQ-NEW-C; equivalent to shipped `move_selection`
Committing a **MOVE** floating selection at final offset `(dx, dy)` produces **one**
reversible command (a `history.PixelEdit` diff) that (a) fills the origin
mask pixels with transparent (RGBA) / index 0 (indexed) — CL-F2 — and (b) stamps the floated
colours at `(x+dx, y+dy)`, **clipped to bounds** (off-canvas destinations discarded, CL-F1).
This is semantically the shipped `selection.move_selection(buffer, mask, dx, dy)`; this
feature reuses it. Returned **unapplied** (push with `execute=True`); `apply ∘ undo =
identity`. A zero offset commit is an identity/no-op command (CL-F8).

#### REQ-P2-LOGIC-033 — Copy commit (modifier + drag = copy)
`traces:` S2, S7 (reversible command); REQ-NEW-C
Committing a **COPY** floating selection at final offset `(dx, dy)` produces **one**
reversible command that stamps the floated colours at `(x+dx, y+dy)`, **clipped to bounds**
(CL-F1), **without** vacating the origin (origin pixels are left unchanged). Returned
unapplied; `apply ∘ undo = identity`. This is a **new** builder (the shipped `move_selection`
always vacates; COPY must not). Deterministic; zero Qt.

#### REQ-P2-LOGIC-034 — Cancel is a non-destructive no-op
`traces:` S2; REQ-NEW-C
Cancelling a floating selection **before commit** leaves the source/base buffer
**byte-for-byte unchanged** and produces **no** command (nothing was ever written during the
float — REQ-P2-LOGIC-031 is copy-based). Restoration is therefore trivial and exact by
construction; no undo entry is created for a cancelled move.

#### REQ-P2-LOGIC-035 — Off-canvas clipping at commit
`traces:` S2, S5 (canvas bounds); REQ-NEW-C
During the float the offset may place part or all of the selection outside the buffer
bounds. On commit (MOVE or COPY), floated pixels whose destination `(x+dx, y+dy)` is
**out of bounds are discarded** (never wrap; reuse the `PixelBuffer.blit` / `move_selection`
`in_bounds` clip). For MOVE, the origin vacate still applies to the full in-bounds origin
region regardless of how far the float was dragged. Deterministic.

#### REQ-P2-LOGIC-036 — Single-buffer / mask-source contract
`traces:` S2; REQ-NEW-C; ADR-0008
The floating selection lifts from **exactly one** buffer and one `SelectionMask`. The mask
is produced by the shipped `rect_mask` / `lasso_mask` / `wand_mask` builders (CL-F4) — this
feature does not introduce a new selection shape. Mask dimensions must match the buffer
(reuses the `move_selection` dimension check → `SelectionError`). There is no multi-buffer /
multi-layer float (CL-F3); "active layer" selection is a UI concern (REQ-P2-UI-036). Zero Qt.

### 4.2 UI layer (`REQ-P2-UI-030..036`) — `ui/` (move interaction + floating overlay)

#### REQ-P2-UI-030 — Lift/float interaction
`traces:` S2, S5; REQ-NEW-C; extends REQ-P2-UI-007 (selection-overlay/move)
When a selection is active, pressing the primary button **inside** the active mask with the
selection/move tool **lifts** the active layer's masked pixels into a floating selection
(REQ-P2-LOGIC-030) and begins a drag. The canvas immediately shows the **floating preview**
(REQ-P2-LOGIC-031) following the cursor. The underlying pixels are **not yet modified**
(non-destructive). Pressing **outside** the mask does not lift (starts a new selection per
the shipped tools). Binds to logic only — no domain logic in the controller.

#### REQ-P2-UI-031 — Drag = move (origin reads transparent)
`traces:` S2, S5; REQ-NEW-C
Dragging **without** a modifier is MOVE: the live preview shows the **origin vacated**
(transparent) and the floated colours at the cursor offset. On commit this is the MOVE
command (REQ-P2-LOGIC-032). The offset tracks the cursor in integer pixel units.

#### REQ-P2-UI-032 — Modifier + drag = copy
`traces:` S2, S5; REQ-NEW-C
Holding **Ctrl** (and **only** Ctrl) during the drag switches the float to **COPY**: the live
preview shows the **origin intact** and a floated copy at the cursor offset; a cursor/affordance
(e.g. a "+" copy cursor) signals copy mode. On commit this is the COPY command
(REQ-P2-LOGIC-033). **Alt is not a copy modifier** — an interior Alt-drag is reserved for the
shipped selection-build SUBTRACT gesture (CL-4 / REQ-P2-UI-004). The Ctrl modifier is sampled
for the move gesture only and does **not** conflict with the selection-*build* combine
modifiers (CL-F5).

#### REQ-P2-UI-033 — Commit triggers (release / Enter / tool-switch)
`traces:` S2, S7; REQ-NEW-C
The floating selection **commits** on any of: primary-button **release**, **Enter/Return**,
or **switching tools**. Commit applies exactly **one** undoable command (MOVE →
REQ-P2-LOGIC-032; COPY → REQ-P2-LOGIC-033) via `ui/commands.py`. After commit the floating
state is cleared and the selection mask follows to the destination (Aseprite behaviour).

#### REQ-P2-UI-034 — ESC cancels and restores exactly
`traces:` S2; REQ-NEW-C
Pressing **ESC** while a float is active **cancels** it: the canvas returns to the exact
pre-move state and **no** undoable command is recorded (REQ-P2-LOGIC-034). The selection
mask returns to its pre-lift position.

#### REQ-P2-UI-035 — Reversibility, single command, render policy
`traces:` S2, S7 (C1/F1), S1 (nearest-neighbour); REQ-NEW-C
A committed move or copy is **one** undo step: undo restores the pre-move buffer exactly in
one action; redo re-applies. The floating preview renders **nearest-neighbour /
anti-aliasing-off** at any zoom (consistent with REQ-P2-UI-014) and is legible in **both
themes**. `apply ∘ undo = identity` for the committed command.

#### REQ-P2-UI-036 — Active-layer scope, off-canvas drag, a11y/i18n
`traces:` S2, S5; REQ-NEW-C; ADR-0008
The floating move affects **only the active layer** (CL-F3; on an indexed document that is
the single indexed layer, ADR-0008). The selection may be dragged **partly or fully
off-canvas**; on commit the off-canvas pixels are discarded (REQ-P2-LOGIC-035). Any new
user-visible control/label (e.g. a status hint) is `tr()`-wrapped and keyboard-reachable
with visible focus (Article V).

## 5. Non-functional requirements

- **NFR-1 (Purity, S11 / Article I).** The floating-selection model + preview composite +
  commit builders import **zero** Qt; only `ui/commands.py` and `ui/` touch Qt.
- **NFR-2 (Determinism, P2).** Preview composite and both commit builders produce identical
  output for identical input (test-asserted).
- **NFR-3 (Non-destructive, REQ-NEW-C core).** No source/base buffer byte changes during the
  float; the buffer changes **only** at commit. Cancel leaves the buffer untouched
  (test-asserted before/after equality).
- **NFR-4 (Reversibility).** `apply ∘ undo = identity` for both MOVE and COPY commits; each
  is exactly one `QUndoCommand`.
- **NFR-5 (No new colours).** A move/copy relocates existing pixel colours only; the
  committed output colour set ⊆ (source colours ∪ the vacate value). No colour is invented.
- **NFR-6 (Numerics, S12 / Article II).** Any new constant lives only in
  `logic/constants.py`; the vacate values reuse `color.TRANSPARENT` / index `0` (no new magic
  numbers — see §9).
- **NFR-7 (Coverage, S13 / Article IV).** ≥90 % line / ≥80 % branch per package; logic via
  pytest (+ Hypothesis for non-destructive/reversibility invariants), UI via pytest-qt in
  **both themes**, headless.
- **NFR-8 (a11y + i18n + both themes, Article V).** New strings `tr()`-wrapped; new widgets
  override `changeEvent`; controls keyboard-reachable with visible focus; the floating
  preview legible in both themes.
- **NFR-9 (Performance, S12 / Article VI).** The live floating preview holds
  `FRAME_BUDGET_MS = 16` at 8K (drag updates a bounded region, not the whole canvas);
  over-budget → an AGT-10 directive, never a relaxed budget.

## 6. Non-goals (explicit)

- No free-transform (rotate/scale/skew) of the floating selection while it floats (deferred;
  post-commit transforms use the shipped REQ-P2-LOGIC-010 path).
- No **move-all-layers** variant (CL-F3; active-layer only).
- No cross-document / cross-canvas float; no floating-selection persistence in `.pixproj`
  (a float is a transient editing state, committed or cancelled before save).
- No indexed multi-layer compositing (ADR-0008).
- No new selection shapes (reuses shipped rect/lasso/wand).
- No new technology choices (S8); no plan/tasks/code.

## 7. Dependencies

**On shipped Phase-2 (hard):**
- `logic/selection.py` — `SelectionMask` (mask model, `bounds`, `data`, dimension check),
  `rect_mask`/`lasso_mask`/`wand_mask` (the mask source, CL-F4), and **`move_selection`**
  (the MOVE commit is exactly this; REQ-P2-LOGIC-032 reuses it). REQ-P2-LOGIC-033 (COPY) is
  the new sibling builder.
- `ui/` selection overlay + move interaction (REQ-P2-UI-007) — the floating move extends the
  existing drag-inside-selection gesture; the marching-ants overlay follows the float.

**On Phase-1 (hard):**
- `logic/pixel_buffer.py` — `get_pixel`/`set_pixel`, `region`, `blit` (clip-to-bounds),
  `copy`, `in_bounds`, `ColorMode` — the lift snapshot, preview composite, and clipped stamp.
- `logic/history.py` — `PixelEdit` / `Command` reversible-op pattern; the commit builders
  return a `PixelEdit`.
- `logic/color.py` — `TRANSPARENT` = `(0,0,0,0)`, the RGBA vacate value (CL-F2).
- `ui/commands.py` — the `QUndoCommand` bridge wrapping each commit as one undo step.

**On architecture decisions (hard):**
- **ADR-0008** (`Document.mode` single authority) — governs the indexed vacate rule
  (CL-F2) and confirms indexed documents are **single-layer**, so the active-layer float
  (CL-F3) is well-defined for both modes.

**No Researcher dependency:** every capability composes shipped, in-repo primitives; the
floating-preview model is a straightforward non-destructive composite over `PixelBuffer`.

**Downstream:** AGT-01 (`sdd-plan` consumes this spec; fixes the empty-mask contract, the
`FloatingSelection` public surface, and UI event routing); AGT-06 (Gherkin → pytest-qt
acceptance tests); AGT-03/04 (logic + tests); AGT-05 (UI + pytest-qt); AGT-07 (i18n of any
new strings); AGT-10 (render/perf of the live float).

## 8. Recommended slicing (for the orchestrator)

Small feature; a single vertical slice is viable, but a logic→UI split mirrors Phase-2:

- **Slice F-A — Floating-selection LOGIC** (`REQ-P2-LOGIC-030..036`): extend
  `logic/selection.py` with the `FloatingSelection` model, the preview-composite function,
  and the COPY commit builder (MOVE reuses `move_selection`), + constants review + pytest
  (Hypothesis for the non-destructive & reversibility invariants). Ships first — UI binds to
  it.
- **Slice F-B — Floating-selection UI** (`REQ-P2-UI-030..036`): the move-interaction
  controller (lift on press-inside), the floating-preview overlay, the modifier→copy
  affordance, the commit-on-release/Enter/tool-switch + ESC-cancel lifecycle, + pytest-qt
  (both themes). Depends on F-A.

Final ordering is AGT-01/orchestrator's call.

## 9. New constants (for AGT-03 — Article II / S12)

No **new** numeric constant is required: the RGBA vacate value reuses `color.TRANSPARENT`,
the indexed vacate value is index `0` (already the `PixelBuffer` default fill and the shipped
`move_selection` / `_masked_transform_changes` convention — CL-F2). `SelectionError` is the
existing domain exception. If AGT-01 introduces a `FloatMode` enum (`MOVE`/`COPY`), it lives
module-local in `selection.py` (cf. `ColorMode` in `pixel_buffer.py`) — AGT-01 to rule on
placement.

## 10. Clarifications (sdd-clarify — resolved defaults, per authoring rule R5 / A2-D2 Branch B)

All open points are resolved with grounded defaults and recorded as category-1 decisions.
**No item required SUSPEND** — the indexed-vacate question (the only candidate) is resolvable
against the shipped model (see CL-F2).

- **CL-F1 — Off-canvas clipping.** The float **may** be dragged partly/fully off-canvas.
  On commit, floated pixels whose destination is out of bounds are **discarded** (never
  wrapped), reusing the `move_selection` / `PixelBuffer.blit` `in_bounds` clip. Grounded:
  shipped `move_selection` already clips via `in_bounds`; `blit` already clips. *(REQ-P2-
  LOGIC-035.)*
- **CL-F2 — Indexed-mode vacate value.** The vacated origin (MOVE) is filled **transparent =
  `color.TRANSPARENT` (0,0,0,0)** for RGBA and **index `0`** for INDEXED. Rationale: indexed
  buffers carry **no alpha channel**, so "transparent" is not literally expressible; index 0
  is the established background/vacate convention in this codebase — it is the `PixelBuffer`
  default fill, the `move_selection` fill (`fill = TRANSPARENT if RGBA else 0`), and the
  `transform._masked_transform_changes` vacate. ADR-0008 guarantees an indexed document is a
  **single indexed layer**, so the vacate is unambiguous. **Resolvable → default adopted, NOT
  suspended.** (If a future palette gains a designated transparent-index field, a later spec
  can override; today none exists.) *(REQ-P2-LOGIC-032.)*
- **CL-F3 — Multi-layer scope.** The float operates on the **active layer only** (default).
  A **move-all-layers** variant is **deferred** (out of scope §6). For an indexed document
  the active layer is the single indexed layer (ADR-0008). *(REQ-P2-UI-036, REQ-P2-LOGIC-036.)*
- **CL-F4 — Interaction with existing selection tools.** The floating move does **not**
  create a mask; it **lifts** whatever `SelectionMask` the shipped `rect_mask` / `lasso_mask`
  / `wand_mask` (REQ-P2-LOGIC-002..004) produced. Lift is triggered by pressing **inside**
  the active mask (REQ-P2-UI-030); pressing outside starts a new selection per the shipped
  tools. *(REQ-P2-LOGIC-036, REQ-P2-UI-030.)*
- **CL-F5 — Copy modifier & disambiguation (orchestrator-adjudicated).** **Ctrl only** held
  during the **move drag** = COPY. **Alt is NOT a copy modifier.** Rationale: an interior
  Alt-drag is the **shipped** Phase-2 selection-build SUBTRACT gesture (CL-4 /
  REQ-P2-UI-004 / SC-U004-2); routing Alt to float-copy regressed 4 shipped tests. Ctrl is
  free and idiomatic for copy-drag, so it is chosen. This modifier is sampled only for the
  *move* gesture (drag starting inside an existing selection).

  **Reconciliation — coexistence with the shipped CL-4 build gestures.** The shipped
  selection-*build* combine modifiers (CL-4 of the advanced-drawing spec) are **Shift = add**
  and **Alt = subtract**, applied while *drawing a new* rectangle/lasso. For a modifier held
  while pressing **inside an existing selection** the disambiguation is:
  - **Ctrl** = copy-float (this feature, REQ-P2-UI-032),
  - **Alt** = subtract (shipped build gesture, unchanged),
  - **no modifier** = lift / move (this feature, REQ-P2-UI-031).

  There is therefore **no modifier collision**: Ctrl (previously free) carries copy-float,
  Alt stays exclusively with the shipped subtract gesture. *(REQ-P2-UI-032; coexists with
  CL-4 / REQ-P2-UI-004.)*
- **CL-F6 — Commit / cancel lifecycle & non-destructiveness.** Commit on **mouse-release,
  Enter, or tool-switch**; **ESC** cancels (user-resolved). The preview is **non-destructive**
  (the base buffer is untouched during the float; only the commit command writes it), so
  cancel is a pure no-op and needs no snapshot restore. *(REQ-P2-UI-033, -034, REQ-P2-LOGIC-
  031, -034.)*
- **CL-F7 — Copy keeps origin in both modes.** COPY leaves the origin pixels unchanged in
  both RGBA and indexed modes (only the destination is stamped). *(REQ-P2-LOGIC-033.)*
- **CL-F8 — Zero-offset commit.** Committing at offset `(0,0)` is an **identity / no-op**
  command (no pixel change for MOVE — vacate then re-stamp the same pixels nets zero; no
  change for COPY). Recorded so a click-without-drag inside a selection does not create a
  spurious undo step. *(REQ-P2-LOGIC-032.)*

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour, phrased for **headless** testing (logic via pytest, UI
via pytest-qt in **both themes**). Non-destructiveness and reversibility are called out per
REQ-NEW-C. Scenario ↔ REQ ↔ (future) test mapping is in `traceability.md`.

### Feature: Floating-selection model / lift (REQ-P2-LOGIC-030)
```gherkin
Scenario: SC-L030-1 lifting captures the masked colours without mutating the source
  Given a buffer and a non-empty rectangle SelectionMask
  When I create a floating selection from them (MOVE)
  Then the float holds the masked pixel colours
  And the source buffer is byte-for-byte unchanged

Scenario: SC-L030-2 the float records its mode (MOVE vs COPY) and a zero initial offset
  Given a floating selection created in COPY mode
  Then its mode is COPY and its offset is (0, 0)

Scenario: SC-L030-3 lifting from an empty mask yields no float
  Given an empty SelectionMask
  When I attempt to create a floating selection
  Then SelectionError is raised (or the documented no-float sentinel is returned)

Scenario: SC-L030-4 a mask whose dimensions differ from the buffer raises SelectionError
```

### Feature: Non-destructive preview composite (REQ-P2-LOGIC-031)
```gherkin
Scenario: SC-L031-1 MOVE preview shows origin vacated and colours at the offset
  Given a MOVE floating selection at offset (dx, dy)
  When I build the preview over the base buffer
  Then the preview shows the origin mask pixels transparent
  And the floated colours stamped at (x+dx, y+dy)
  And the base buffer is NOT mutated

Scenario: SC-L031-2 COPY preview keeps the origin intact and adds the floated colours
  Given a COPY floating selection at offset (dx, dy)
  Then the preview shows the origin unchanged and the floated colours at the offset
  And the base buffer is NOT mutated

Scenario: SC-L031-3 the preview is deterministic for identical float + offset + base

Scenario: SC-L031-4 an off-canvas offset clips the previewed float to the visible bounds
```

### Feature: Move commit — drag = move (REQ-P2-LOGIC-032)
```gherkin
Scenario: SC-L032-1 committing a MOVE vacates the origin and stamps at the destination
  Given a MOVE floating selection at offset (dx, dy)
  When I commit
  Then the origin mask pixels are transparent (RGBA) / index 0 (indexed)
  And the floated colours appear at (x+dx, y+dy)

Scenario: SC-L032-2 REVERSIBILITY: commit then undo restores the buffer exactly (apply∘undo = identity)

Scenario: SC-L032-3 the MOVE commit is exactly ONE reversible command (a PixelEdit)

Scenario: SC-L032-4 a zero-offset MOVE commit is a no-op (no net pixel change) (CL-F8)

Scenario: SC-L032-5 INDEXED move vacates the origin with index 0 (CL-F2)
```

### Feature: Copy commit — modifier + drag = copy (REQ-P2-LOGIC-033)
```gherkin
Scenario: SC-L033-1 committing a COPY stamps at the destination and leaves the origin intact
  Given a COPY floating selection at offset (dx, dy)
  When I commit
  Then the origin mask pixels are unchanged
  And the floated colours also appear at (x+dx, y+dy)

Scenario: SC-L033-2 REVERSIBILITY: copy commit then undo restores the buffer exactly

Scenario: SC-L033-3 the COPY commit is exactly ONE reversible command

Scenario: SC-L033-4 COPY keeps the origin intact in indexed mode too (CL-F7)
```

### Feature: Cancel is non-destructive (REQ-P2-LOGIC-034)
```gherkin
Scenario: SC-L034-1 cancelling a float leaves the buffer byte-for-byte unchanged
  Given a MOVE or COPY floating selection dragged to some offset
  When I cancel before commit
  Then the source buffer equals its pre-lift state
  And no reversible command was produced
```

### Feature: Off-canvas clipping at commit (REQ-P2-LOGIC-035)
```gherkin
Scenario: SC-L035-1 floated pixels dragged off-canvas are discarded on commit (not wrapped)
  Given a float dragged so part of it lies outside the buffer bounds
  When I commit
  Then only in-bounds destination pixels are written; off-canvas pixels are dropped

Scenario: SC-L035-2 a MOVE dragged fully off-canvas still vacates the whole origin

Scenario: SC-L035-3 off-canvas clipping is deterministic
```

### Feature: Single-buffer / mask-source contract (REQ-P2-LOGIC-036)
```gherkin
Scenario: SC-L036-1 the float lifts from a mask produced by rect/lasso/wand builders (CL-F4)
  Examples: rect_mask | lasso_mask | wand_mask

Scenario: SC-L036-2 the float never spans more than one buffer (single-buffer contract)

Scenario: SC-L036-3 the model imports zero Qt (verified by check_layering, Article I) [spec-only]
```

### Feature: Lift/float interaction (REQ-P2-UI-030)
```gherkin
Scenario: SC-U030-1 pressing inside the active selection lifts a floating preview (both themes)
  Given an active selection on the active layer
  When I press inside the mask and begin dragging
  Then a floating preview appears and follows the cursor
  And the underlying pixels are NOT yet modified

Scenario: SC-U030-2 pressing outside the active selection does not lift (starts a new selection)
```

### Feature: Drag = move preview (REQ-P2-UI-031)
```gherkin
Scenario: SC-U031-1 dragging without a modifier previews the origin transparent and colours at the cursor

Scenario: SC-U031-2 the offset tracks the cursor in integer pixel units
```

### Feature: Modifier + drag = copy (REQ-P2-UI-032)
```gherkin
Scenario: SC-U032-1 holding Ctrl (only) during the drag previews a copy with the origin intact

Scenario: SC-U032-2 a copy-mode cursor/affordance signals COPY (both themes)

Scenario: SC-U032-3 an interior Alt-drag does NOT copy-float; Ctrl (copy) coexists with the shipped Alt=subtract build gesture (CL-F5)
```

### Feature: Commit triggers (REQ-P2-UI-033)
```gherkin
Scenario: SC-U033-1 releasing the mouse commits the float as exactly ONE undoable command

Scenario: SC-U033-2 pressing Enter commits the active float as ONE undoable command

Scenario: SC-U033-3 switching tools commits the active float as ONE undoable command

Scenario: SC-U033-4 after commit the selection mask follows to the destination
```

### Feature: ESC cancels and restores (REQ-P2-UI-034)
```gherkin
Scenario: SC-U034-1 pressing ESC during a float restores the pre-move canvas exactly

Scenario: SC-U034-2 a cancelled float records NO undo entry
```

### Feature: Reversibility / single command / render policy (REQ-P2-UI-035)
```gherkin
Scenario: SC-U035-1 undo after a committed move/copy restores the pre-move buffer in ONE step; redo re-applies

Scenario: SC-U035-2 the floating preview renders nearest-neighbour, anti-aliasing off, at any zoom

Scenario: SC-U035-3 the floating preview is legible in both light and dark themes
```

### Feature: Active-layer scope, off-canvas drag, a11y (REQ-P2-UI-036)
```gherkin
Scenario: SC-U036-1 the float modifies only the active layer (other layers untouched)

Scenario: SC-U036-2 the selection can be dragged partly off-canvas; off-canvas pixels are discarded on commit

Scenario: SC-U036-3 any new control/hint is tr()-wrapped and keyboard-reachable with visible focus (both themes)
```

---

## 12. Exit / status

- Forward pre-implementation spec authored for **REQ-NEW-C** (floating-selection move/copy),
  extending shipped Phase-2 selection.
- **14 REQ-IDs**: 7 LOGIC (`REQ-P2-LOGIC-030..036`) + 7 UI (`REQ-P2-UI-030..036`) — a
  dedicated sub-band, no collision with the shipped `REQ-P2-*-001..015`.
- **~37 Gherkin scenarios** (logic SC-L030..036 + UI SC-U030..036); every functional REQ has
  ≥1 scenario; traceability shows **0 uncovered** (`traceability.md`).
- **8 clarify decisions** (CL-F1..F8) recorded as category-1 defaults; **no SUSPEND** — the
  indexed-vacate point is resolvable against the shipped model + ADR-0008 (index 0).
- Non-destructiveness, reversibility, and off-canvas-clip acceptance included.
- Recommended slicing: **F-A logic → F-B UI** — §8.
- **STATUS: COMPLETED.**
