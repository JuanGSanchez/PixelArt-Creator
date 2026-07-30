# Plan — Floating-Selection Move / Copy (REQ-NEW-C)

| Field | Value |
| --- | --- |
| Feature | `phase-2-floating-selection` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-03 |
| SDD phase | `plan` (this doc) — over approved `spec.md` + `traceability.md` (AGT-02) |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VIII, X) |
| Grounds on | shipped `logic/selection.py` (`SelectionMask`, `move_selection`, `apply_masked`), `logic/history.py` (`Command`/`PixelEdit`), `logic/pixel_buffer.py`, `logic/color.py` (`TRANSPARENT`); `ui/tools/selection_base.py`, `ui/commands.py` (`LogicCommand`), `ui/canvas_scene.py` (`_SelectionOverlayItem`); ADR-0007 (region-scoped recomposite), ADR-0008 (mode authority) |
| New ADR | **ADR-0009** — non-destructive floating selection (this plan files it) |
| Researcher | **None** — no new stack/library/API; every capability composes shipped in-repo primitives (PL-D1 Branch B, cite spec §7 "No Researcher dependency") |
| Stack | Unchanged (S8): Python 3.12, NumPy, PySide6/Qt6. No new dependency. |

---

## 1. Architecture overview

The floating selection is a **non-destructive editing state**: at lift the masked
**colours** of the active-layer buffer are snapshotted; while the float is dragged the
underlying buffer is **never written**; only the commit produces a single reversible
`history.Command`. Two commit flavours: **MOVE** (vacate origin + stamp — the shipped
`move_selection`) and **COPY** (stamp only — a new sibling builder). ESC/cancel is a pure
no-op because nothing was ever written (spec CL-F6 / REQ-P2-LOGIC-034).

The design rests on one **load-bearing invariant** (ADR-0009 §D2): *because the base buffer
is never mutated during the float, the colours captured at lift equal the colours still in
the buffer at commit.* Therefore the preview uses the lifted snapshot, and the commit
builders re-read the live buffer — and the two are provably identical. This is what lets the
MOVE commit reuse the shipped `move_selection(buffer, mask, dx, dy)` verbatim (it reads
colours from `buffer` at commit) with **zero change** to shipped code.

Layer split (Article I / S11):

- **`logic/selection.py` (extend, Qt-free)** — the `FloatMode` enum, the `FloatingSelection`
  model, the `lift_selection` factory, the region-scoped `composite_preview`, the new
  `copy_selection` builder, and the `commit_floating` dispatcher. `move_selection` is
  **reused unchanged**.
- **`ui/` (Qt only)** — a floating-preview graphics item (`ui/canvas_scene.py`), a
  `FloatingMoveController` (`ui/tools/floating_move.py`) owning the lift→drag→commit/cancel
  lifecycle, input routing in `SelectionTool` / `Canvas_View` / `Main_Window`, and the undo
  wrapper — **reusing the existing `ui/commands.LogicCommand`** (no new command class).

### 1.1 Placement ruling (S11) — extend `logic/selection.py`, do NOT add `logic/floating_selection.py`

**Decision: extend `logic/selection.py`.** Justification (layer-audit):

1. **Cohesion / single domain.** The floating model is intrinsically coupled to
   `SelectionMask` and to `move_selection` (which already lives in `selection.py` and which
   MOVE reuses). The COPY builder is a literal sibling of `move_selection` (same signature,
   minus the vacate step); the preview composite operates on a `SelectionMask` + a
   `PixelBuffer`. Splitting these into a new module would fragment one domain across two files
   and add a `floating_selection → selection` import edge for no benefit.
2. **Precedent.** `FloatMode` follows the established *module-local enum* pattern —
   `ColorMode` in `pixel_buffer.py`, `SymmetryAxis` in `symmetry.py`, `BlendMode` in
   `blend.py` (STRUCTURE.md). Spec §9 and the AGT-02 handoff explicitly endorse module-local
   placement.
3. **No cycle risk.** All additions import only what `selection.py` already imports
   (`history`, `color.TRANSPARENT`, `pixel_buffer`, `numpy`). No new import edge; `check_cycles`
   stays clean.
4. **Traceability agreement.** `traceability.md` maps every `REQ-P2-LOGIC-030..036` to
   `logic/selection.py`.

`FloatingSelection` is the primary reason a split *could* be argued (it is a new class, not
just functions). It is rejected: the class is small (a lifted snapshot + mask + mode +
offset), it is the state object the sibling functions operate on, and the selection domain is
the correct home. (PL-D2 check: zero Qt in any addition; no magic number — `FloatMode` is an
enum, vacate reuses `color.TRANSPARENT` / index `0`; no `constants.py` change.)

---

## 2. Resolved handoff decisions (AGT-02 → AGT-01)

### PL-H1 — Empty-mask contract → **raise `SelectionError`** (not a sentinel)

`lift_selection` raises `SelectionError` on an empty mask (and on a dimension mismatch, reusing
`move_selection`'s check). Rationale: (a) consistency with the Phase-1 domain-error convention
and with `move_selection`, which already raises `SelectionError` on a bad mask; (b) in the UI,
lift is only ever attempted when a press lands **inside** a non-empty active mask
(`SelectionTool.on_press` already gates on `selection is not None and not selection.is_empty`),
so an empty mask at `lift_selection` is a genuine programming error, not a control-flow path —
an exception is correct, a sentinel would invite silent misuse. This satisfies SC-L030-3 (which
permits either) and SC-L030-4 (dimension mismatch → `SelectionError`).

### PL-H2 — `FloatMode` enum placement → **module-local in `logic/selection.py`**

```python
class FloatMode(enum.Enum):
    MOVE = "move"
    COPY = "copy"
```

Module-local, per PL-D of the module map (`ColorMode`/`SymmetryAxis`/`BlendMode` precedent).
Exported in `__all__`. No `constants.py` entry (it is not a numeric tuning value).

### PL-H3 — `FloatingSelection` public surface → **frozen (see §4.1)**

An immutable lifted snapshot with a mutable live offset. The snapshot is captured at
construction and never changes; only `set_offset` moves. This keeps the heavy pixel copy
one-shot (cheap per-mouse-move updates) while the offset tracks the cursor.

### PL-H4 — UI event routing coexisting with rect/lasso/wand build tools → **§5**

A press **inside** the active mask (no Shift/Alt build-combine intent) starts a float-move via
the new `FloatingMoveController`; a press **outside** (or with a build-combine gesture) runs
the shipped rect/lasso/wand build path. The float-move modifier (Ctrl/Alt = COPY) is sampled
**per mouse-move during the drag** and is disambiguated from the selection-**build** combine
modifiers (Shift=add / Alt=subtract), which apply only while *drawing a new* shape — a distinct
gesture that begins with a press *outside* an existing selection (CL-F5). See §5.2 for the
decision table.

### PL-H5 — COPY commit builder → **new `copy_selection` (§4.1); MOVE reuses `move_selection`**

MOVE = shipped `selection.move_selection(buffer, mask, dx, dy)` unchanged. COPY = a new
`copy_selection(buffer, mask, dx, dy)` identical except it omits the origin-vacate step.
`commit_floating(buffer, floating)` dispatches on `floating.mode` and passes `floating.offset`.

---

## 3. ADR-0009 (filed by this plan)

**ADR-0009 — Non-destructive floating selection: lifted-snapshot preview, region-scoped
composite, commit re-reads the live buffer.** Written to `docs/adr/0009-floating-selection-non-destructive-preview.md`.
Captures: (D1) the non-destructive-preview architecture; (D2) the snapshot ≡ commit-read
invariant that lets MOVE reuse `move_selection`; (D3) the region-scoped `composite_preview`
return contract (extends ADR-0007's region rule to the preview path — no full-canvas alloc per
mouse-move); (D4) COPY as a sibling builder; (D5) empty-mask → `SelectionError`; (D6) indexed
vacate defers to ADR-0008 / CL-F2 (index 0) — **no new decision**, cross-referenced only.

---

## 4. Logic layer — FROZEN interface contract (for AGT-03 / AGT-04)

All additions live in `pixelart_creator/logic/selection.py`. **Zero Qt.** Exceptions subclass
`ValueError` via the existing `SelectionError`. No `constants.py` change (NFR-6).

### 4.1 Public surface (frozen signatures)

```python
class FloatMode(enum.Enum):
    """Commit flavour of a floating selection (module-local, PL-H2)."""
    MOVE = "move"   # vacate origin + stamp (reuses move_selection)
    COPY = "copy"   # stamp only, origin intact (copy_selection)


class FloatingSelection:
    """A non-destructive lifted region of one buffer, floated at a live offset.

    Captures the masked pixel COLOURS as an independent snapshot at construction
    (the source buffer is never mutated), plus the source mask, a FloatMode, and a
    live integer offset (dx, dy). Zero Qt. REQ-P2-LOGIC-030.
    """
    # -- read-only properties --
    @property
    def mode(self) -> FloatMode: ...
    @property
    def offset(self) -> Tuple[int, int]: ...        # current (dx, dy)
    @property
    def width(self) -> int: ...                      # source buffer width
    @property
    def height(self) -> int: ...                     # source buffer height
    def mask(self) -> SelectionMask: ...             # independent copy of the source mask
    def bounds(self) -> Optional[Tuple[int,int,int,int]]:  # source mask bbox (x0,y0,x1,y1)
        ...
    # -- live offset (only mutable state) --
    def set_offset(self, dx: int, dy: int) -> None:  # raises SelectionError on non-int
        ...


def lift_selection(
    buffer: PixelBuffer, mask: SelectionMask, mode: FloatMode
) -> FloatingSelection:
    """Snapshot the masked colours of ``buffer`` into a FloatingSelection.

    Does NOT mutate ``buffer`` (non-destructive lift). REQ-P2-LOGIC-030, -036.

    Raises:
        SelectionError: if ``mask`` is empty (PL-H1); if mask dims != buffer dims;
            if ``mode`` is not a FloatMode.
    """


def composite_preview(
    floating: FloatingSelection,
    base: PixelBuffer,
    *,
    region: Optional[Tuple[int, int, int, int]] = None,
) -> PixelBuffer:
    """Return a preview buffer: ``base`` with the float applied (base NEVER mutated).

    MOVE: the origin mask pixels read VACATED (color.TRANSPARENT / index 0, CL-F2)
    and the floated colours are stamped at (x+dx, y+dy), clipped to bounds.
    COPY: the origin is left intact; floated colours stamped at the offset.

    region=None  -> a full-size copy of ``base`` with the float applied
                    (reference / test path; small canvases).
    region=(x,y,w,h) -> a REGION-SIZED buffer (numpy (h,w,4)/(h,w)) whose implied
                    scene origin is (x,y): element (i,j) = scene pixel (x+j, y+i).
                    Allocates only (h,w[,4]) — NEVER (height,width) (ADR-0007 T13
                    anti-pattern avoided). The UI drag path MUST use this form.
                    Raises SelectionError if the region is out of bounds or w<1/h<1
                    (validate, never clamp — P2 determinism).

    Deterministic: identical (floating, base, offset, region) -> identical output.
    REQ-P2-LOGIC-031, -035. Zero Qt.
    """


def move_selection(  # SHIPPED — REUSED UNCHANGED (REQ-P2-LOGIC-032)
    buffer: PixelBuffer, mask: SelectionMask, dx: int, dy: int
) -> history.Command: ...


def copy_selection(  # NEW sibling of move_selection (REQ-P2-LOGIC-033)
    buffer: PixelBuffer, mask: SelectionMask, dx: int, dy: int
) -> history.Command:
    """Stamp the masked colours at (dx, dy) WITHOUT vacating the origin.

    Reads colours from ``buffer`` at the masked coords and stamps at (x+dx, y+dy),
    clipped to bounds (off-canvas destinations discarded — CL-F1). Returns an
    UNAPPLIED history.PixelEdit (push with execute=True); apply then undo restores
    the buffer exactly. A zero-offset COPY is an identity/no-op command (CL-F8).

    Raises:
        SelectionError: on a mask/buffer dimension mismatch or non-int offsets.
    """


def commit_floating(
    buffer: PixelBuffer, floating: FloatingSelection
) -> history.Command:
    """Dispatch to move_selection (MOVE) or copy_selection (COPY) at the float's
    current offset. Returns the UNAPPLIED command. REQ-P2-LOGIC-032, -033.
    """
```

`__all__` gains: `FloatMode`, `FloatingSelection`, `lift_selection`, `composite_preview`,
`copy_selection`, `commit_floating`.

### 4.2 Contract notes / invariants (test targets for AGT-04)

- **Non-destructive (NFR-3, load-bearing):** `lift_selection` and `composite_preview` never
  write `buffer`/`base` (assert byte-for-byte equality before/after — SC-L030-1, SC-L031-1/-2).
- **Snapshot ≡ commit-read (ADR-0009 D2):** the colours a `FloatingSelection` holds equal
  `buffer`'s colours at the masked coords, for as long as the buffer is unmutated (the UI
  guarantees this — no other edit runs during a float). This is why `commit_floating` can read
  from `buffer` and still stamp the floated colours.
- **Cancel = no-op (REQ-P2-LOGIC-034):** there is **no** logic "cancel" function — cancelling
  is discarding the `FloatingSelection` object; the buffer was never touched (SC-L034-1). No
  undo entry.
- **Reversibility (NFR-4):** both `move_selection` and `copy_selection` return unapplied
  `PixelEdit`; `apply ∘ undo = identity` (SC-L032-2, SC-L033-2).
- **Off-canvas clip (CL-F1 / REQ-P2-LOGIC-035):** the commit builders discard out-of-bounds
  destinations via `in_bounds` (as `move_selection` already does); `composite_preview` clips
  the stamped region. A MOVE dragged fully off-canvas still vacates the whole in-bounds origin.
- **Indexed vacate (CL-F2 / ADR-0008):** MOVE vacate = `color.TRANSPARENT` (RGBA) / index `0`
  (indexed) — the shipped `move_selection` convention, unchanged (SC-L032-5, SC-L033-4).
- **Single-buffer / mask-source (REQ-P2-LOGIC-036):** one buffer + one `SelectionMask` from the
  shipped `rect_mask`/`lasso_mask`/`wand_mask`; dimension check → `SelectionError`.
- **Determinism (NFR-2):** `composite_preview`, `copy_selection` produce identical output for
  identical input (Hypothesis invariants: apply∘undo=identity; preview base-unchanged;
  no-new-colours NFR-5 — committed colour set ⊆ source colours ∪ vacate value).

### 4.3 Suggested internal storage (AGT-03 freedom; perf note)

To keep the snapshot memory-bounded and the region preview vectorised, store the lifted colours
as the **mask bounding-box sub-buffer** (`buffer.region(x0, y0, w, h)`) + the mask cropped to
that bbox + the bbox origin — not a full-canvas copy (a full 8K copy = 126 MB; the bbox is
typically tiny). `composite_preview(region=...)` then blits the bbox sub-buffer masked into the
requested region. Public surface above does not constrain this; it is the recommended shape.

---

## 5. UI layer — FROZEN seam (for AGT-05 / AGT-06)

Qt only. Binds to logic (`lift_selection`, `composite_preview`, `commit_floating`, `FloatMode`)
+ the undo stack. No domain math (Article I). Reuses `ui/commands.LogicCommand` — **no new
command class.**

### 5.1 Modules

| Module | Change | Responsibility | Binds to |
| --- | --- | --- | --- |
| `ui/canvas_scene.py` | extend | New `_FloatingPreviewItem(QGraphicsItem)` rendering the floated colours (nearest-neighbour, AA off, both themes) at the current offset, painting the `composite_preview` region image over the canvas pixmap (origin vacated for MOVE). New scene methods: `begin_floating(floating)`, `update_floating(floating, *, dirty_region)`, `end_floating()`. Reuses the existing `_SelectionOverlayItem.set_move_offset` for the marching-ants outline. | `selection.composite_preview` |
| `ui/tools/floating_move.py` | **new** | `FloatingMoveController`: owns one active float's lift→drag→commit/cancel lifecycle; single owner reachable from mouse, key, and tool-switch events. | `selection.lift_selection`/`composite_preview`/`commit_floating`/`FloatMode`, scene, `ui/commands.LogicCommand` |
| `ui/tools/selection_base.py` | extend | Replace the current inline destructive move (`_commit_move` → `move_selection` on release) with a **delegation** to `FloatingMoveController`: press-inside-mask → `controller.begin(...)`; drag → `controller.update(dx, dy, copy=<Ctrl/Alt>)`; release → `controller.commit()`. Build gestures (rect/lasso/wand) unchanged. | `FloatingMoveController` |
| `ui/canvas_view.py` | extend | Route `keyPressEvent`: **Enter/Return** → `controller.commit()`; **Escape** → `controller.cancel()`. NN/AA-off render policy already locked; the float preview inherits it. | controller |
| `ui/main_window.py` | extend | On **tool-switch**, if `controller.is_active()` → `controller.commit()` before activating the new tool (commit-on-tool-switch, REQ-P2-UI-033). Wire the controller into the per-document editing session. New `tr()` status hint (copy-mode) keyboard-reachable. | controller |
| `ui/commands.py` | **no change** | Reuse `LogicCommand(commit_floating(...), refresh, label)`. Confirmed sufficient (wraps any unapplied `history.Command`). | `history` |

`FloatingMoveController` frozen surface (indicative):

```python
class FloatingMoveController:
    def begin(self, buffer, mask, base_provider, scene, undo_stack, set_selection, label) -> None: ...
    def update(self, dx: int, dy: int, *, copy: bool) -> None: ...   # set offset + mode, region preview
    def commit(self) -> None: ...   # LogicCommand(commit_floating(buffer, float)); mask follows; clear
    def cancel(self) -> None: ...   # clear preview, restore outline, NO command (SC-U034-2)
    def is_active(self) -> bool: ...
```

### 5.2 Input-routing decision table (CL-F4 / CL-F5 — PL-H4)

| Gesture (press) | Modifier | Active mask? | Inside mask? | Action |
| --- | --- | --- | --- | --- |
| primary press | none | yes | **inside** | **Lift → float-move (MOVE)** (controller.begin) |
| primary press | **Ctrl or Alt** *(sampled during drag)* | yes | inside | float-move switches to **COPY** while held |
| primary press | none | yes | outside | shipped **build** path (new selection, replace) |
| primary press | **Shift** | yes | (build) | shipped build **add** combine |
| primary press | **Alt** | (build, press outside) | — | shipped build **subtract** combine |
| primary press | any | no active mask | — | shipped build path |

The copy modifier (Ctrl/Alt) is read **during the move drag** (a gesture that *began inside* an
existing selection); the build combine modifiers are read at a *build* press (a gesture that
begins by *drawing a new* shape, i.e. outside, or the wand). The two never overlap because they
belong to different gestures — CL-F5. During a float, Enter commits, ESC cancels, releasing
commits, switching tools commits.

### 5.3 Lifecycle (REQ-P2-UI-030..034)

1. **Lift** (press inside mask): `controller.begin` → `lift_selection(buffer, mask, MOVE)`;
   scene shows the floating preview (non-destructive); outline offset starts at (0,0).
2. **Drag** (`on_move`): `controller.update(dx, dy, copy=Ctrl|Alt)` → `float.set_offset`, set
   `FloatMode` (recreate float only if mode toggles — snapshot is mode-independent, so mode is
   just a flag on the same float), scene repaints **only the dirty region** (§6).
3. **Commit** (release / Enter / tool-switch): `commit_floating(buffer, float)` → push
   `LogicCommand`; the selection mask follows to the destination (`mask.translate(dx, dy)`,
   Aseprite behaviour, SC-U033-4); float cleared.
4. **Cancel** (ESC): discard the float; scene restores the pre-lift view; **no** command
   (SC-U034-1/-2). Because the buffer was never written, restore is a pure preview teardown.

Zero-offset commit → `commit_floating` returns an identity command; the controller must not
push a spurious undo step (CL-F8) — push only if the command has changes (`len(cmd) > 0` for a
`PixelEdit`), matching the shipped `_commit_move` `dx==0 and dy==0` guard.

---

## 6. Performance — region-scoped drag preview (for AGT-10 / AGT-05)

**Directive surface (ADR-0007-aligned, NFR-9 / Article VI, FRAME_BUDGET_MS = 16 at 8K):**

- The **live drag preview** (per mouse-move, the budget-critical path) MUST call
  `composite_preview(floating, base, region=dirty)` with a **bounded** `dirty` region and MUST
  NOT allocate a full-canvas buffer per move. This is the exact ADR-0007 T13 lesson: a
  full-canvas `PixelBuffer` alloc (~126 MB / ~140 ms at 8K) per frame blows the budget ~9×.
- `dirty` = clamp-to-bounds( bbox(origin) ∪ bbox(float @ previous offset) ∪ bbox(float @ new
  offset) ). The previous-offset region must be repainted (to erase the old float position) and
  the new region painted. The scene updates only that rectangle (`scene.update(dirtyRectF)` /
  region blit into the preview item).
- The **one-shot commit** may use a whole-region or `refresh_all` repaint (it is a single
  user-initiated action, not a per-frame budget item — consistent with ADR-0007's "budget item
  is the per-edit path"); a region-scoped commit refresh (union bbox) is preferred but not
  required.
- AGT-10 owns the measurement: `frame-profile` / `perf_profile` a drag at 8K with a large
  selection; an over-budget result yields an AGT-10 directive AGT-05 implements — the **budget
  is never relaxed** (Article VI §2). The resident buffers are never culled (F7); only the Qt
  preview repaint is region-scoped.

This plan freezes the **region-scoped `composite_preview` return contract** (§4.1) as the
architectural surface AGT-10 tunes against; AGT-10 owns the Qt-side viewport/update tuning.

---

## 7. Implementation strategy (order + slices)

Mirrors spec §8: **F-A logic → F-B UI** (F-B depends on F-A's frozen contract).

1. **F-A (logic, AGT-03 / AGT-04).** Extend `logic/selection.py`: `FloatMode`,
   `FloatingSelection`, `lift_selection`, `composite_preview` (region-scoped), `copy_selection`,
   `commit_floating`. `move_selection` untouched. No `constants.py` change. Tests: pytest +
   Hypothesis for the non-destructive & reversibility & determinism invariants (§4.2). F-A can
   start immediately — all dependencies are shipped.
2. **F-B (UI, AGT-05 / AGT-06).** New `ui/tools/floating_move.py`; extend `ui/canvas_scene.py`
   (`_FloatingPreviewItem` + scene methods); refactor `ui/tools/selection_base.py` move path to
   delegate to the controller; route Enter/ESC (`canvas_view`) + tool-switch (`main_window`);
   reuse `LogicCommand`. Tests: pytest-qt, both themes, headless (§5). Depends on F-A.

Reversible-op boundary: the **only** buffer mutation is at commit, via the logic command wrapped
in `LogicCommand` (one `QUndoCommand` per commit, C1/F1). Preview and cancel never mutate.

Render touchpoint handed to AGT-10: §6 (region-scoped drag preview; the `composite_preview
region=` contract).

---

## 8. Constitution compliance (self-check)

- **Article I (S11):** all logic additions are Qt-free; `check_layering` / `check_cycles` must
  stay `0` (run at analyze, §C1 gate). Only `ui/` + `ui/commands.py` touch Qt. No new import
  edge in logic (additions import only already-imported modules).
- **Article II (S12):** no magic number; `FloatMode` is an enum; vacate reuses
  `color.TRANSPARENT` / index `0`. No `constants.py` change (NFR-6).
- **Article IV (S13):** ≥90 % line / ≥80 % branch — F-A pytest+Hypothesis, F-B pytest-qt both
  themes (NFR-7).
- **Article V:** new copy-mode hint `tr()`-wrapped, keyboard-reachable, visible focus; float
  preview legible in both themes; NN/AA-off (NFR-8, REQ-P2-UI-035/-036).
- **Article VI:** 16 ms drag budget via region-scoped preview; over-budget → AGT-10 directive,
  never a relaxed budget (§6, NFR-9).
- **Article X:** every REQ traces to REQ-NEW-C + an S-id (`traceability.md`); no untraced work.
- **PL-D1:** no ungrounded stack choice (no Researcher). **PL-D2:** no Qt-in-logic / magic
  number — enforced above.

---

## 9. Exit

- Placement ruled: extend `logic/selection.py` (§1.1); UI in `ui/` with a new
  `ui/tools/floating_move.py` + `ui/canvas_scene.py` extension; undo via reused `LogicCommand`.
- Handoff items resolved: empty-mask → `SelectionError` (PL-H1); `FloatMode` module-local
  (PL-H2); `FloatingSelection` surface frozen (PL-H3 / §4.1); UI routing table (PL-H4 / §5.2);
  COPY builder specified, MOVE reuses `move_selection` (PL-H5).
- Interface contracts frozen for AGT-03 (§4) and AGT-05 (§5).
- ADR-0009 filed (§3).
- Perf directive surface handed to AGT-10 (§6).
- Consumed next by `sdd-tasks` (F-A/F-B) → `sdd-analyze` (C1 gate).
- **STATUS: COMPLETED.**
