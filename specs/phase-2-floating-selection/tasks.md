# Tasks — Floating-Selection Move / Copy (REQ-NEW-C)

| Field | Value |
| --- | --- |
| Feature | `phase-2-floating-selection` |
| Author | AGT-01 (Architecture) via `sdd-tasks` |
| Date | 2026-07-03 |
| Derived from | `plan.md` (§4 logic contract, §5 UI seam, §6 perf, §7 strategy); `spec.md`; `traceability.md` |
| Slices | **F-A logic** (AGT-03 impl / AGT-04 tests) → **F-B UI** (AGT-05 impl / AGT-06 tests). F-B depends on F-A's frozen contract. |
| Status legend | `todo` \| `doing` \| `done` |

> Every `REQ-P2-LOGIC-030..036` and `REQ-P2-UI-030..036` maps to ≥1 impl task **and** ≥1
> test/verify task (coverage matrix in §Coverage). One owner per task (TK-D1). Deterministic
> gate sub-steps invoke the standalone scripts (TK-D2).

---

## Slice F-A — Floating-selection LOGIC (`logic/selection.py`, Qt-free)

| ID | Description | Owner | Target file(s) | Depends on | REQ / Acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **FA-1** | Add module-local `FloatMode(enum.Enum)` (`MOVE`/`COPY`); export in `__all__`. No `constants.py` change (enum, not numeric — NFR-6). | AGT-03 | `logic/selection.py` | — | REQ-P2-LOGIC-030 (mode flag); PL-H2 | todo |
| **FA-2** | Implement `FloatingSelection` (immutable lifted colour snapshot + source mask + `FloatMode` + live `(dx,dy)` offset): props `mode`/`offset`/`width`/`height`, `mask()` (copy), `bounds()`, `set_offset(dx,dy)` (int-validated → `SelectionError`). Store colours as the mask-bbox sub-buffer (plan §4.3), **never** a full-canvas copy. | AGT-03 | `logic/selection.py` | FA-1 | REQ-P2-LOGIC-030; PL-H3 / plan §4.1 | todo |
| **FA-3** | Implement `lift_selection(buffer, mask, mode) -> FloatingSelection`: snapshot masked colours **without mutating** `buffer`; raise `SelectionError` on empty mask (PL-H1), dim mismatch (reuse `move_selection` check), or non-`FloatMode`. | AGT-03 | `logic/selection.py` | FA-2 | REQ-P2-LOGIC-030, -036 | todo |
| **FA-4** | Implement region-scoped `composite_preview(floating, base, *, region=None) -> PixelBuffer`: `base` never mutated; MOVE vacates origin (`TRANSPARENT`/index 0, CL-F2) + stamps at offset (clipped); COPY leaves origin intact. `region=None` → full-size; `region=(x,y,w,h)` → region-sized `(h,w[,4])` buffer, implied origin `(x,y)`, **no full-canvas alloc**; out-of-bounds/degenerate region → `SelectionError`. Deterministic. | AGT-03 | `logic/selection.py` | FA-2 | REQ-P2-LOGIC-031, -035; ADR-0009 D3 | todo |
| **FA-5** | Implement `copy_selection(buffer, mask, dx, dy) -> history.Command`: sibling of `move_selection` **without** the origin vacate; stamp at `(x+dx,y+dy)` clipped (CL-F1); return **unapplied** `PixelEdit`; zero-offset → identity (CL-F8); dim/int checks → `SelectionError`. | AGT-03 | `logic/selection.py` | FA-1 | REQ-P2-LOGIC-033, -035; CL-F7/F8 | todo |
| **FA-6** | Implement `commit_floating(buffer, floating) -> history.Command` dispatcher: MOVE → `move_selection(buffer, floating.mask(), *floating.offset)` (reuse shipped, unchanged); COPY → `copy_selection(...)`. Return unapplied. Update `__all__` with all new names. | AGT-03 | `logic/selection.py` | FA-3, FA-5 | REQ-P2-LOGIC-032, -033 | todo |
| **FA-7** | Confirm MOVE reuse: verify `move_selection` needs **no** change (D2 invariant) and REQ-P2-LOGIC-032 is satisfied by reuse; add regression coverage that `commit_floating(MOVE)` equals `move_selection`. | AGT-03 | `logic/selection.py` (no edit) | FA-6 | REQ-P2-LOGIC-032 | todo |
| **FA-T1** | Unit tests: lift snapshots colours; **source byte-for-byte unchanged** after lift; float records mode + offset (0,0); empty mask → `SelectionError`; dim mismatch → `SelectionError`. | AGT-04 | `tests/logic/test_selection.py` | FA-3 | REQ-P2-LOGIC-030 (SC-L030-1..4) | todo |
| **FA-T2** | Unit + Hypothesis tests: MOVE preview shows origin vacated + colours at offset; COPY preview keeps origin + adds colours; `base` **not mutated** (before/after equality); preview deterministic; off-canvas offset clips preview; region-sized return matches full-size slice. | AGT-04 | `tests/logic/test_selection.py` | FA-4 | REQ-P2-LOGIC-031, -035 (SC-L031-1..4) | todo |
| **FA-T3** | Unit + Hypothesis tests: MOVE commit vacates origin + stamps at destination; **reversibility** `apply∘undo=identity`; exactly ONE `PixelEdit`; zero-offset no-op (CL-F8); INDEXED vacate = index 0 (CL-F2). | AGT-04 | `tests/logic/test_selection.py` | FA-6, FA-7 | REQ-P2-LOGIC-032 (SC-L032-1..5) | todo |
| **FA-T4** | Unit + Hypothesis tests: COPY commit stamps at destination + origin **unchanged** (RGBA & indexed, CL-F7); reversibility; exactly ONE command; no-new-colours (NFR-5: output ⊆ source ∪ vacate). | AGT-04 | `tests/logic/test_selection.py` | FA-6 | REQ-P2-LOGIC-033 (SC-L033-1..4) | todo |
| **FA-T5** | Unit tests: cancel = discard float ⇒ buffer byte-for-byte unchanged + **no** command produced (no logic cancel fn; assert non-destructive invariant). | AGT-04 | `tests/logic/test_selection.py` | FA-3 | REQ-P2-LOGIC-034 (SC-L034-1) | todo |
| **FA-T6** | Unit tests: off-canvas clip on commit discards OOB destinations (never wraps); MOVE fully off-canvas still vacates whole origin; deterministic. | AGT-04 | `tests/logic/test_selection.py` | FA-6 | REQ-P2-LOGIC-035 (SC-L035-1..3) | todo |
| **FA-T7** | Unit tests: float lifts from `rect_mask`/`lasso_mask`/`wand_mask` (Examples); single-buffer contract; dim mismatch → `SelectionError`. Purity (SC-L036-3) is gate-enforced (see AN-1), no unit test. | AGT-04 | `tests/logic/test_selection.py` | FA-3 | REQ-P2-LOGIC-036 (SC-L036-1..2; -3 spec-only) | todo |

## Slice F-B — Floating-selection UI (`ui/`, Qt only) — depends on F-A

| ID | Description | Owner | Target file(s) | Depends on | REQ / Acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **FB-1** | New `_FloatingPreviewItem(QGraphicsItem)` in the scene: paints the `composite_preview` region image over the canvas pixmap (origin vacated for MOVE), **nearest-neighbour / AA-off**, legible **both themes**; z above pixmap, below marching-ants. Scene methods `begin_floating(floating)`, `update_floating(floating, *, dirty_region)`, `end_floating()`. | AGT-05 | `ui/canvas_scene.py` | FA-6 | REQ-P2-UI-030, -031, -035 | todo |
| **FB-2** | New `FloatingMoveController` (`ui/tools/floating_move.py`): owns one active float; `begin/update(copy=…)/commit/cancel/is_active`. `begin`→`lift_selection`; `update`→`set_offset` + `FloatMode` + region preview; `commit`→`LogicCommand(commit_floating(...), refresh, label)` push + mask follows to destination + clear (skip push if zero-change, CL-F8); `cancel`→teardown, **no** command. No domain math (Article I). | AGT-05 | `ui/tools/floating_move.py` | FB-1 | REQ-P2-UI-030, -031, -032, -033, -034, -035 | todo |
| **FB-3** | Refactor `SelectionTool` move path: press-inside-mask → `controller.begin`; `on_move` → `controller.update(dx,dy, copy=Ctrl\|Alt)`; `on_release` → `controller.commit`. Remove inline destructive `_commit_move`. Build gestures (rect/lasso/wand) unchanged; copy modifier disambiguated from build combine (CL-F5). | AGT-05 | `ui/tools/selection_base.py` | FB-2 | REQ-P2-UI-030, -031, -032, -033, -036 | todo |
| **FB-4** | Route `keyPressEvent` in the view: **Enter/Return** → `controller.commit()`; **Escape** → `controller.cancel()` (only while a float is active; else default). | AGT-05 | `ui/canvas_view.py` | FB-2 | REQ-P2-UI-033, -034 | todo |
| **FB-5** | On tool-switch, commit an active float before activating the new tool; wire the controller into the per-document editing session; add a `tr()`-wrapped copy-mode status hint (keyboard-reachable, visible focus, both themes). | AGT-05 | `ui/main_window.py` | FB-2 | REQ-P2-UI-032, -033, -036 | todo |
| **FB-6** | Confirm undo bridge reuse: `LogicCommand` wraps the unapplied `commit_floating` command as **one** `QUndoCommand`; **no new class** in `ui/commands.py` (verify sufficiency; edit only if a gap is found). | AGT-05 | `ui/commands.py` (verify; likely no edit) | FB-2 | REQ-P2-UI-035 | todo |
| **FB-7** | i18n: extract any new user-visible string (copy-mode hint) — audit + wrap `tr()`; add to `.ts` catalogue. | AGT-07 | `ui/main_window.py` (+ `.ts`) | FB-5 | REQ-P2-UI-036 (NFR-8) | todo |
| **FB-8** | Perf directive: profile a live drag at 8K with a large selection (`frame-profile`/`perf_profile`); confirm the region-scoped preview holds `FRAME_BUDGET_MS`; over-budget → issue an AGT-05 directive (dirty-rect union old∪new float bbox ∪ origin bbox; no full-canvas update). Budget never relaxed (Article VI). | AGT-10 | (profile report → AGT-05 directive) | FB-2 | NFR-9; ADR-0009 D3 / ADR-0007 | todo |
| **FB-T1** | pytest-qt (both themes, headless): press-inside lifts a floating preview that follows the cursor with underlying pixels **not modified** (SC-U030-1); press-outside starts a new selection (SC-U030-2). | AGT-06 | `tests/ui/test_floating_selection.py` | FB-3 | REQ-P2-UI-030 | todo |
| **FB-T2** | pytest-qt: drag-without-modifier previews origin transparent + colours at cursor (SC-U031-1); offset tracks cursor in integer pixels (SC-U031-2). | AGT-06 | `tests/ui/test_floating_selection.py` | FB-3 | REQ-P2-UI-031 | todo |
| **FB-T3** | pytest-qt (both themes): Ctrl **or** Alt during drag → COPY preview, origin intact (SC-U032-1); copy-mode cursor/affordance (SC-U032-2); modifier does **not** trigger build-subtract (SC-U032-3, CL-F5). | AGT-06 | `tests/ui/test_floating_selection.py` | FB-3, FB-5 | REQ-P2-UI-032 | todo |
| **FB-T4** | pytest-qt: release commits as exactly ONE undoable command (SC-U033-1); Enter commits (SC-U033-2); tool-switch commits (SC-U033-3); mask follows to destination after commit (SC-U033-4). | AGT-06 | `tests/ui/test_floating_selection.py` | FB-3, FB-4, FB-5 | REQ-P2-UI-033 | todo |
| **FB-T5** | pytest-qt: ESC during a float restores pre-move canvas exactly (SC-U034-1); cancelled float records **NO** undo entry (SC-U034-2); mask returns to pre-lift position. | AGT-06 | `tests/ui/test_floating_selection.py` | FB-4 | REQ-P2-UI-034 | todo |
| **FB-T6** | pytest-qt (both themes): undo after commit restores pre-move buffer in ONE step + redo re-applies (SC-U035-1); preview renders NN / AA-off at any zoom (SC-U035-2); preview legible both themes (SC-U035-3). | AGT-06 | `tests/ui/test_floating_selection.py`, `tests/ui/test_selection_overlay.py` | FB-1, FB-2 | REQ-P2-UI-035 | todo |
| **FB-T7** | pytest-qt: float modifies only the active layer, others untouched (SC-U036-1); drag partly off-canvas → OOB pixels discarded on commit (SC-U036-2); new control/hint `tr()`-wrapped + keyboard-reachable + visible focus, both themes (SC-U036-3). | AGT-06 | `tests/ui/test_floating_selection.py` | FB-3, FB-5, FB-7 | REQ-P2-UI-036 | todo |

## Gate

| ID | Description | Owner | Target | Depends on | Acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **AN-1** | C1 cross-artifact analyze gate: `sdd-analyze` over constitution/spec/plan/tasks; run `python scripts/check_layering.py` + `python scripts/check_cycles.py` (both exit 0 → Qt-free purity SC-L036-3, no cycles). Must be 0 unresolved before implement dispatch. | AGT-01 | analyze report | plan+tasks authored | Article I gate; SC-L036-3 | todo |

---

## Coverage — every REQ has ≥1 impl + ≥1 test/verify task

| REQ-ID | Impl task(s) | Test/verify task(s) |
| --- | --- | --- |
| REQ-P2-LOGIC-030 | FA-1, FA-2, FA-3 | FA-T1 |
| REQ-P2-LOGIC-031 | FA-4 | FA-T2 |
| REQ-P2-LOGIC-032 | FA-6, FA-7 (reuse `move_selection`) | FA-T3 |
| REQ-P2-LOGIC-033 | FA-5, FA-6 | FA-T4 |
| REQ-P2-LOGIC-034 | (non-destructive by construction — FA-3/FA-4) | FA-T5 |
| REQ-P2-LOGIC-035 | FA-4, FA-5 | FA-T2, FA-T6 |
| REQ-P2-LOGIC-036 | FA-3 | FA-T7 (+ AN-1 for SC-L036-3) |
| REQ-P2-UI-030 | FB-1, FB-2, FB-3 | FB-T1 |
| REQ-P2-UI-031 | FB-1, FB-2, FB-3 | FB-T2 |
| REQ-P2-UI-032 | FB-2, FB-3, FB-5 | FB-T3 |
| REQ-P2-UI-033 | FB-2, FB-3, FB-4, FB-5 | FB-T4 |
| REQ-P2-UI-034 | FB-2, FB-4 | FB-T5 |
| REQ-P2-UI-035 | FB-1, FB-2, FB-6 | FB-T6 |
| REQ-P2-UI-036 | FB-3, FB-5, FB-7 | FB-T7 |

## Notes for the orchestrator

- **F-A can start immediately** (all deps shipped). **F-B depends on F-A** (FB-* on FA-6).
- Reuse-first: MOVE = shipped `move_selection` unchanged; undo = shipped `LogicCommand`
  unchanged. Genuinely new: `FloatMode`, `FloatingSelection`, `lift_selection`,
  `composite_preview`, `copy_selection`, `commit_floating` (logic); `FloatingMoveController`,
  `_FloatingPreviewItem` (UI).
- No `constants.py` change (NFR-6); no `data/` change; no new dependency (S8).
- AN-1 (C1 gate) must pass with 0 unresolved before any implement dispatch (SDD gate A1-D2).
