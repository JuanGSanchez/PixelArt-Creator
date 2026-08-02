# ADR-0009 — Non-destructive floating selection: lifted-snapshot preview, region-scoped composite, commit re-reads the live buffer

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-03 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-2-floating-selection` (REQ-NEW-C floating-selection move/copy) |
| Supersedes | — |
| Superseded by | — |
| Grounds on | ADR-0007 (region-scoped recomposite; resident buffers never culled), ADR-0008 (`Document.mode` single authority; indexed = single layer / index-0 vacate); shipped `logic/selection.move_selection`; spec `specs/phase-2-floating-selection/spec.md` §2/§10 (CL-F1..F8), plan `plan.md` §1–§6 |

## Context

REQ-NEW-C upgrades the shipped **destructive one-shot** cut-move
(`logic/selection.move_selection`, which rewrites pixels the moment the selection is dragged)
to a **floating selection**: dragging a selected region shows its colours as a live preview
while the pixels *beneath* stay untouched until the move is **committed**; a modifier turns the
move into a copy; ESC cancels with an exact restore; commit is one undoable step
(release / Enter / tool-switch).

Two architectural questions must be settled before implementation so AGT-03 (logic) and AGT-05
(UI) bind to a stable contract:

1. **How is the preview non-destructive, and how does the commit stay reversible and reuse the
   shipped `move_selection`?** A naive design would write the move destructively and snapshot
   the whole buffer to undo — heavy and duplicative of the shipped command.
2. **How is the live drag preview kept within the 8K frame budget (FRAME_BUDGET_MS = 16,
   Article VI)?** A preview that recomputes/allocates the whole canvas per mouse-move is the
   exact anti-pattern ADR-0007 (T13 amendment) measured at ~140 ms / ~9× over budget.

## Decision

### D1 — Non-destructive preview via a lifted colour snapshot; the base buffer is never written during the float

`lift_selection(buffer, mask, mode)` captures the masked pixel **colours** as an independent
snapshot and returns a `FloatingSelection` (mask + `FloatMode` + live `(dx, dy)` offset).
`composite_preview(floating, base, *, region=None)` returns a **new** preview buffer (base with
the float applied; origin vacated for MOVE, intact for COPY) and **never mutates `base`**. The
only buffer mutation in the whole feature is at **commit**. Cancel is therefore a pure no-op —
nothing to restore, no undo entry (spec CL-F6 / REQ-P2-LOGIC-034).

### D2 — The snapshot ≡ commit-read invariant (load-bearing; lets MOVE reuse `move_selection`)

Because the base buffer is never written during the float, the colours captured at lift are
**identical** to the colours still in the buffer at commit. Therefore the commit builders may
re-read the live buffer, and the shipped `move_selection(buffer, mask, dx, dy)` is reused
**verbatim** for the MOVE commit (it reads colours from `buffer`, vacates the origin, stamps at
the offset, returns an unapplied reversible `PixelEdit`; `apply ∘ undo = identity`). No shipped
code changes. The UI guarantees the invariant: no other edit runs while a float is active.

### D3 — Region-scoped `composite_preview` return contract (extends ADR-0007 to the preview path)

`composite_preview(floating, base, *, region=None)`:

- `region=None` → a full-size copy of `base` with the float applied (reference / test path;
  small canvases).
- `region=(x, y, w, h)` → a **region-sized** buffer (numpy `(h, w, 4)` / `(h, w)`), implied
  scene origin `(x, y)`, element `(i, j)` = scene pixel `(x+j, y+i)`. It allocates only
  `(h, w[, 4])`, **never** `(height, width)`. Out-of-bounds or degenerate (`w<1`/`h<1`) region
  → `SelectionError` (validate, never clamp — P2 determinism, mirroring ADR-0007's `BlendError`
  rule for `composite_stack`).

The **UI drag path MUST use the `region=` form** so a per-mouse-move preview costs its dirty
rect, not the canvas — the direct application of ADR-0007's T13 lesson (no full-canvas alloc per
frame). AGT-10 owns the Qt-side measurement/tuning; the budget is never relaxed (Article VI §2).

### D4 — COPY is a sibling builder; the mode flag lives on the float

`copy_selection(buffer, mask, dx, dy)` is identical to `move_selection` **minus** the
origin-vacate step (stamp at the offset, clip off-canvas, return an unapplied `PixelEdit`).
`commit_floating(buffer, floating)` dispatches on `floating.mode` (`FloatMode.MOVE`/`COPY`) at
the float's current offset. A zero-offset commit is an identity/no-op command (CL-F8) so a
click-without-drag creates no spurious undo step.

### D5 — Empty-mask contract → raise `SelectionError`

`lift_selection` raises `SelectionError` on an empty mask (and on a dimension mismatch, reusing
`move_selection`'s check). The UI only attempts a lift when a press lands inside a non-empty
active mask, so an empty mask at `lift_selection` is a programming error, not a control-flow
path — consistent with the Phase-1 domain-error convention and `move_selection`.

### D6 — Indexed vacate defers to ADR-0008 / CL-F2 (no new decision)

The MOVE vacate value is `color.TRANSPARENT` (RGBA) / index `0` (indexed) — the shipped
`move_selection` convention, unchanged. ADR-0008 guarantees an indexed document is a single
indexed layer, so the active-layer float is well-defined in both modes. Recorded here only for
cross-reference; this ADR makes no new mode/vacate decision.

## Alternatives considered

- **Destructive move + whole-buffer snapshot for undo.** Rejected: mutates during drag
  (defeats "non-destructive"), and a whole-buffer snapshot at 8K is 126 MB per float vs the
  minimal `PixelEdit` diff the shipped command already produces.
- **New `logic/floating_selection.py` module.** Rejected (plan §1.1): the model is intrinsically
  coupled to `SelectionMask` + `move_selection` in `selection.py`; a split fragments one domain
  and adds an import edge for no benefit. `FloatMode` follows the module-local enum precedent.
- **Full-canvas `composite_preview` return every mouse-move.** Rejected: the ADR-0007 T13
  anti-pattern (~140 ms / ~9× over budget at 8K). The `region=` return is the fix.
- **`FloatingSelection.commit(buffer)` method (OO).** Rejected in favour of free-function
  builders + a `commit_floating` dispatcher, to reuse `move_selection` verbatim and keep the
  commit path symmetric with the shipped selection API and independently testable.

## Consequences

**Positive.** MOVE reuses shipped, tested `move_selection` with zero change; the only new logic
is `FloatingSelection` + `lift_selection` + `composite_preview` + `copy_selection` +
`commit_floating`. Cancel is trivially exact (no restore). The region-scoped preview contract
gives AGT-10 a defined tuning surface and keeps the 16 ms budget reachable. No `constants.py`
change; no new dependency; layering stays acyclic (additions import only what `selection.py`
already imports).

**Negative / risk.** The snapshot ≡ commit-read invariant (D2) depends on nothing mutating the
buffer during a float — the UI must ensure a float is committed/cancelled before any other edit
(enforced by commit-on-tool-switch and single-active-interaction). Cache-safety for a
composited RGBA layer at commit follows the existing `LogicCommand` refresh path. The
region-preview dirty-rect union (old float bbox ∪ new float bbox ∪ origin bbox) must be computed
correctly by AGT-05 or the old float position will ghost; asserted by AGT-06.

## Grounding

- Spec `specs/phase-2-floating-selection/spec.md` §2 (in-scope logic/UI), §4.1/§4.2 (REQ-P2-
  LOGIC-030..036 / UI-030..036), §5 (NFR-1..9), §10 (CL-F1..F8); `traceability.md`.
- Plan `specs/phase-2-floating-selection/plan.md` §1.1 (placement), §2 (handoff resolutions),
  §4 (frozen logic contract), §5 (UI seam), §6 (perf directive).
- ADR-0007 (region-scoped recomposite; T13 full-canvas-alloc anti-pattern; budget never
  relaxed). ADR-0008 (mode authority; index-0 vacate; indexed = single layer).
- Shipped `logic/selection.move_selection` (destructive cut-move: lift + vacate + restamp,
  clipped, unapplied `PixelEdit`), `logic/history.PixelEdit`, `logic/pixel_buffer` (`region`/
  `blit`/`in_bounds`/`copy`), `logic/color.TRANSPARENT`.
- Constitution Article I (three-layer purity; `check_layering`/`check_cycles` gate),
  Article II (constants), Article VI (16 ms / 8K; over-budget → AGT-10 directive).
