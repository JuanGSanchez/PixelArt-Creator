# Tasks — Phase 4: Layer & Canvas System

| Field | Value |
| --- | --- |
| Feature | `phase-4-layer-canvas` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| Derived from | `specs/phase-4-layer-canvas/plan.md` §3–§10 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VII, VIII, X) |
| Scope | Full Phase-4 build, sliced **4A LOGIC → 4B DATA (`.pixproj` v2) → 4C UI**. Every REQ-P4-* (incl. the allocated REQ-P4-DATA-*) maps to ≥1 impl task + ≥1 test/verify task. |

Status legend: `todo` · `doing` · `done`.
Each task: **id · owner · target file(s) · predecessor · REQ/acceptance link · status.**

The C1 gate (`sdd-analyze`) is run over constitution/spec/plan/tasks as the pre-implement gate
(see `analyze-report.md`). Article VIII: no implement dispatch past a red gate; layering/cycles must
exit 0 at each slice boundary (Decision A1-D3; exit 2 → BLOCKED, A1-E3).

---

## Slice 4A — Layer & compositing LOGIC (`REQ-P4-LOGIC-001..015`) — Qt-free

### T1 — New constants → `logic/constants.py`
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/constants.py` · **Predecessor:** — (root)
- **Do:** Add, each with a source-citation comment (keep leaf, no intra-package imports):
  `DEFAULT_LAYER_OPACITY = 1.0` (CL-2), `MAX_LAYERS_PER_FRAME = 256` (CL-7, Article VII),
  `MAX_GROUP_NESTING_DEPTH = 8` (CL-6, Article VII). The `BlendMode` enum is a **vocabulary** and
  lives in `logic/blend.py` (T2, BF-2); blend-formula magic numbers are **intrinsic → local** to
  `blend.py` (plan §8, ADR-0001/0005) — none go here.
- **REQ/acceptance:** REQ-P4-LOGIC-015 / Article II; SC-L015-1 (bounds), SC-L015-2 (defaults).
- **Status:** todo

### T2 — `logic/blend.py` (BlendMode enum + separable modes + stack compositor)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/blend.py` · **Predecessor:** T1
- **Do:** Implement `BlendError(ValueError)`; the `BlendMode` enum with **exactly 12** members
  (LOGIC-001 — the W3C separable set: NORMAL + 11 non-normal separable; FU-13 corrected from 13,
  a double-count of normal); per-mode separable `blend_channel(mode, cb, cs)` on straight normalised 0..1 channels
  matching `docs/research-blend-modes.md` §1/§3 (multiply/screen/overlay=hard-light-swapped/darken/
  lighten/color-dodge/color-burn/hard-light/soft-light-W3C-D(Cb)/difference/exclusion; magic numbers
  intrinsic-local); `blend_pixels(mode, src, dst)` applying the §3 compositing step with **NORMAL
  delegating to `color.blend_over` exactly** (LOGIC-003); `blend_arrays(mode, src, dst, *, opacity,
  mask)` **vectorised** `(H,W,4)` uint8 (F7) — `opacity` scales src effective alpha (LOGIC-005),
  `mask` modulates it (LOGIC-012); `composite_stack(nodes, width, height, *, region=None)` flattening
  a bottom-to-top node list into ONE flat RGBA `PixelBuffer` (skips hidden = no-op LOGIC-006; honours
  opacity/order/mode LOGIC-004/005/007; flattens a group first then blends as one LOGIC-011; never
  mutates sources LOGIC-004; `region` scopes a dirty-rect recomposite ADR-0007). Consumes nodes via
  the structural `CompositeNode` Protocol — **must NOT import `document`** (PL-D2, cycle-free). Work
  in float32 straight alpha (ADR-0005). Zero Qt; typed; PEP-257 docstrings.
- **T13 AMENDMENT (ADR-0007 §Amendment T13; plan §6.1/§10) — MANDATORY for AGT-03:**
  - **D1 — no full-canvas allocation on the region path.** `region=None` returns a full-canvas
    `PixelBuffer(width,height)`; **`region=(x,y,w,h)` returns a REGION-SIZED `PixelBuffer(w,h)`**
    (shape `(h,w,4)`, implied scene origin `(x,y)`) and allocates only `(h,w,4)` — NOT the 126 MB
    full-canvas buffer that caused the ~140 ms / ~9× over-budget floor (SC-UI-015-1). Region in scene
    space, must lie fully within `(0,0,width,height)` with `w≥1,h≥1`; out-of-bounds/degenerate →
    `BlendError` (validate, do not silently clamp). See plan §6.1 for the exact coordinate contract.
  - **D5 — float32, not float64.** Use `np.float32` as the blend working dtype (ADR-0005 §Compliance
    note T13); the shipped path deviated to float64. Compliance correction, no behaviour change.
  - **D4 — cached group buffers + partial-stack recomposite (now required).** Cache each `LayerGroup`'s
    flattened intermediate and reuse it while its subtree is unchanged; invalidation contract is
    enforced in `document.py` (T3). Optionally cache the below-layer backdrop for partial-stack recomposite.
- **REQ/acceptance:** REQ-P4-LOGIC-001 (SC-L001-1), -002 (SC-L002-1 known-values, -002 determinism),
  -003 (SC-L003-1), -004 (SC-L004-1..3), -005 (SC-L005-1), -006 (SC-L006-1), -007 (SC-L007-1/-2),
  compositor side of -011 (SC-L011-1/-2), -012 (SC-L012-1/-2); **SC-UI-015-1 (region-path budget, T13 D1/D5)**.
- **Status:** todo

### T3 — `logic/document.py` extension (blend-mode attr + groups + masks + reference + smart + reversible ops + guards + bounds)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/document.py` · **Predecessor:** T1, T2
- **Do:** Extend `Layer` (additive; defaults keep every call site valid): `blend_mode: BlendMode =
  NORMAL`, `mask: Optional[PixelBuffer] = None`, `reference: bool = False`, `smart_source:
  Optional[Layer] = None`, and `effective_buffer()` (smart → source buffer read-only, else own
  buffer). Add `LayerGroup` node (ordered `children`, own opacity/visible/locked/blend_mode/mask;
  satisfies `blend.CompositeNode` via `children`). Implement reversible **attribute** ops
  (`set_layer_opacity/visible/locked/blend_mode` → `history.FunctionCommand`, LOGIC-008),
  **structural** ops (`make_add/remove/move/duplicate_layer_command`, `make_group/ungroup_command`
  → `history.Command`; removed-node op snapshots node+index+contents; last-layer refusal kept,
  LOGIC-009), and **group/mask/reference/smart** ops (`make_attach/detach_mask_command`,
  `make_set_reference_command`, `make_smart_layer_command`, LOGIC-012/013/014). Add
  `ensure_editable(layer)` raising `DocumentError` on a pixel-mutating op targeting a locked OR
  reference layer (LOGIC-010/013; opacity/visibility/mode/order stay changeable, CL-11). Enforce
  `MAX_LAYERS_PER_FRAME` + `MAX_GROUP_NESTING_DEPTH` (raise `DocumentError`) and default new nodes
  to `DEFAULT_LAYER_OPACITY` + `NORMAL` (LOGIC-015). `document` imports `blend.BlendMode` (one-way
  edge, PL-D2). Reuse `DocumentError`. Zero Qt; typed; docstrings.
- **T13 AMENDMENT (ADR-0007 §Amendment T13, D4) — MANDATORY group-cache invalidation contract:**
  any child edit / attribute / order / mask change on a node **invalidates the flattened cache of
  its `LayerGroup` and of every ancestor group up the whole chain** (a stale cache renders a wrong
  composite). The cache-invalidation hook fires from every reversible op above and its undo. Asserted
  by AGT-06 (SC-UI-012-2, composite-updates-on-edit).
- **REQ/acceptance:** REQ-P4-LOGIC-008 (SC-L008-1/-2), -009 (SC-L009-1..4), -010 (SC-L010-1),
  node side of -011 (SC-L011-3 depth), -012 (SC-L012-3), -013 (SC-L013-1), -014 (SC-L014-1),
  -015 (SC-L015-1/-2).
- **Status:** todo

### T4 — Logic tests (pytest + Hypothesis) for 4A
- **Owner:** AGT-04 · **Target:** `tests/logic/test_blend.py`, `tests/logic/test_document.py`
  (extend) · **Predecessor:** T2, T3
- **Do:** One test per SC-L001..015 scenario. **Blend:** each mode matches the grounded reference
  value on known inputs (SC-L002-1 — the research §3 table incl. the soft-light `D(Cb)` W3C-variant
  dataset guard); NORMAL == `color.blend_over` exactly (SC-L003-1). **Compositor:** flattens ordered
  stack (SC-L004-1); never mutates sources (SC-L004-2); z-order respected (SC-L004-3); opacity scales
  (SC-L005-1); hidden = removed (SC-L006-1); per-layer mode isolation (SC-L007-2); group
  composite-then-blend (SC-L011-1) + hidden group = removed subtree (SC-L011-2); mask modulation
  (SC-L012-1) + all-max mask == no mask (SC-L012-2) + mask edit leaves pixels intact (SC-L012-3).
  **Reversibility:** every attribute/structural/group/mask/reference/smart op `apply ∘ undo =
  identity` (SC-L008-*, SC-L009-*); locked/reference reject mutation (SC-L010-1, SC-L013-1); smart
  mirrors source (SC-L014-1); last-layer refusal (SC-L009-4); bounds (SC-L011-3, SC-L015-1);
  defaults (SC-L015-2). **Hypothesis** invariants: blend determinism (SC-L002-2); N NORMAL layers ==
  folded `blend_over` (SC-L007-1); reversibility (`apply∘undo`). Coverage gate ≥90 % line / ≥80 %
  branch; **invoke `python scripts/coverage_gate.py`** (P11). Deterministic/portable, headless.
- **REQ/acceptance:** Article IV (one test per criterion); SC-L001..015.
- **Status:** todo

### T5 — Slice-4A layering/cycle gate (AGT-01)
- **Owner:** AGT-01 · **Target:** `pixelart_creator/` · **Predecessor:** T4
- **Do:** **Invoke `python scripts/check_layering.py` and `python scripts/check_cycles.py`** — both
  must exit 0 (Article I; Decision A1-D3): `logic/blend.py` + the `document.py` extension import zero
  Qt and add no cycle — in particular the **one-way `document → blend` edge** with `blend` never
  importing `document` (PL-D2). Script exit 2 → BLOCKED (A1-E3).
- **REQ/acceptance:** Article I; PL-D2.
- **Status:** todo

## Slice 4B — `.pixproj` persistence DATA (`REQ-P4-DATA-001..005`) — Qt-free; depends on 4A

### T6 — `data/project_io.py` extension (schema v2: blend/opacity/visibility/lock + groups + masks + reference/smart; defensive load; v1 back-compat)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/data/project_io.py` · **Predecessor:** T3, T5
- **Do:** Bump `FORMAT_VERSION = 2` (ADR-0006). **Serialise:** per-node `blend_mode`
  (`BlendMode` value string), `opacity`, `visible`, `locked` (DATA-001); nested `LayerGroup` nodes
  with ordered children (DATA-002); a layer's `mask` buffer (compressed, geometry-validated,
  DATA-003); `reference` flag + smart-source link by a stable in-document ref (DATA-004).
  **Deserialise defensively** (validated, size/bounds-checked, no `eval`/`exec`, Article VII):
  reject malformed / oversized / out-of-bounds / dangling smart-ref / bad blend-mode string /
  over-`MAX_GROUP_NESTING_DEPTH` / over-`MAX_LAYERS_PER_FRAME` with `ProjectIOError`; and **read
  legacy v1 files** — `version == 1` loads flat layers as `NORMAL` blend, no groups/masks
  (DATA-005). Accept `version in {1, 2}`; reject others. Portable paths (`pathlib`). Zero Qt; typed.
- **REQ/acceptance:** REQ-P4-DATA-001..005 (plan §7 acceptance rows).
- **Status:** todo

### T7 — Data tests (pytest + Hypothesis) for 4B
- **Owner:** AGT-04 · **Target:** `tests/data/test_project_io.py` (extend) · **Predecessor:** T6
- **Do:** One test per DATA acceptance. **Round-trip** the full layer model — blend_mode / opacity /
  visible / locked (DATA-001); a grouped + nested tree preserving structure + child order (DATA-002);
  a masked layer, mask bytes identical (DATA-003); reference flag + smart-source link (DATA-004).
  **Defensive load:** malformed JSON, oversized payload, out-of-bounds geometry, unknown blend-mode
  string, over-depth nesting, dangling smart-ref each raise `ProjectIOError` (DATA-005, Article VII).
  **Back-compat:** a checked-in **v1 `.pixproj` fixture** loads (all `NORMAL`, no groups/masks) and
  re-saves as v2 (DATA-005). Hypothesis round-trip over random valid trees. Coverage ≥90/80; invoke
  `coverage_gate`. Headless, deterministic.
- **REQ/acceptance:** Article IV; REQ-P4-DATA-001..005.
- **Status:** todo

### T8 — Slice-4B layering/cycle gate (AGT-01)
- **Owner:** AGT-01 · **Target:** `pixelart_creator/` · **Predecessor:** T7
- **Do:** **Invoke `check_layering` + `check_cycles`** — both exit 0: `data/project_io.py` extension
  imports zero Qt and adds no cycle (`project_io → document → blend`, one-way). Exit 2 → BLOCKED.
- **REQ/acceptance:** Article I.
- **Status:** todo

## Slice 4C — Layer panel + canvas compositing UI (`REQ-P4-UI-001..018`) — depends on 4A(+4B) + stable Phase-1 UI

### T9 — Layer panel + controls + management actions
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/layer_panel.py`,
  `pixelart_creator/ui/main_window.py` (dock the panel) · **Predecessor:** T5 + stable Phase-1 UI
- **Do:** `Layer_Panel(QWidget)` listing the active frame's layers/groups **top-to-bottom, topmost
  first** (CL-3, UI-001) reflecting the `document` tree; per row: **opacity slider** 0–100 % ↔
  `Layer.opacity` (UI-002), **visibility toggle** (UI-003), **lock toggle** (UI-004), **blend-mode
  dropdown** listing the **12** `BlendMode` members (W3C separable set; FU-13 — was mis-stated as 13,
  a double-count of normal) with **tr()** labels (UI-005), **drag-to-reorder**
  incl. re-parent into/out of groups (UI-006); **add / remove / duplicate** actions (last-layer
  removal refused, UI-007); **group / ungroup** (UI-008); expandable group nodes; single-selection
  active layer. Each mutation delegates to a `document` op wrapped as **one** `QUndoCommand`
  (UI-013, via T12). `tr()`-wrapped strings + `changeEvent` retranslate (UI-018); accessible
  name/description + logical tab order + visible focus (UI-016); role-based colours, both themes
  (UI-017). No domain logic in the widget (Article I).
- **REQ/acceptance:** REQ-P4-UI-001 (SC-UI-001-1), -002 (SC-UI-002-1), -003 (SC-UI-003-1),
  -004 (SC-UI-004-1), -005 (SC-UI-005-1), -006 (SC-UI-006-1), -007 (SC-UI-007-1), -008 (SC-UI-008-1),
  -016/-017/-018 (build-time; verified T13/T15).
- **Status:** todo

### T10 — Mask / reference / smart-layer affordances
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/layer_panel.py` (extend) · **Predecessor:** T9
- **Do:** **Mask** affordance (UI-009): add mask, select-to-paint (paint tools modulate the mask
  buffer, not the layer pixels), remove; canvas recomposites with the mask modulating layer alpha.
  **Reference** affordance (UI-010): mark/clear reference; a reference layer stays visible in the
  composite and rejects paint (no-op). **Smart** affordance (UI-011, minimal CL-9): create a smart
  layer from a selected source; it mirrors the source, its own pixels are not directly editable.
  Each attach/remove/flag/create is **one** `QUndoCommand` (via T12). `tr()` + `changeEvent`,
  keyboard-reachable, both themes.
- **REQ/acceptance:** REQ-P4-UI-009 (SC-UI-009-1), -010 (SC-UI-010-1), -011 (SC-UI-011-1).
- **Status:** todo

### T11 — Canvas compositing + multi-canvas / artboard tabs
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/canvas_scene.py` (extend),
  `pixelart_creator/ui/main_window.py` (extend) · **Predecessor:** T5, T9
- **Do:** **Canvas compositing** (UI-012): the scene renders the **flattened composite** of the
  active frame's stack via `blend.composite_stack` (superseding the Phase-1 single-layer draw); an
  edit to any layer/attribute/order/group/mask updates the on-canvas composite for the **affected
  (dirty) region** only — `composite_stack(..., region=(x,y,w,h))` (ADR-0007, DEP-2). **T13 AMENDMENT
  (D1):** the region call returns a **region-sized `(h,w,4)` buffer** (implied origin `(x,y)`); the
  scene **blits it into its resident composite buffer at `(x,y)`** — `scene.data[y:y+h, x:x+w] =
  returned.data` — it does NOT receive a full-canvas buffer. Clamp the dirty rect to
  `(0,0,width,height)` before calling. Resident buffers never culled (F7). **D2/D3 (AGT-05, T13):**
  route attribute ops (opacity/visibility/lock/blend-mode) through a **viewport-clipped region
  recomposite**, NOT a whole-stack `refresh_all` (`region=None`); **debounce live opacity-drag** to
  one recomposite per frame (≤ FRAME_BUDGET_MS), the authoritative command firing on release.
  **Multi-canvas** (UI-014, CL-15): extend the Phase-1 document tabs so each
  tab owns its own layer tree + palette + `QUndoStack` + composite + scene rect; switching a tab
  makes it the active context; a layer op / undo in one tab never affects another (state isolation).
- **REQ/acceptance:** REQ-P4-UI-012 (SC-UI-012-1/-2), -014 (SC-UI-014-1/-2).
- **Status:** todo

### T12 — `ui/commands.py` wrappers (one QUndoCommand per layer op)
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/commands.py` (extend) · **Predecessor:** T9, T10, T11
- **Do:** One `QUndoCommand` wrapper per layer op (set opacity/visibility/lock/blend-mode, add/
  remove/duplicate/reorder, group/ungroup, attach/detach mask, set reference, create smart),
  **delegating to the `history.Command`** the `document` op returns (no domain math — Article I);
  push exactly one command onto the active document's `QUndoStack`; undo restores the exact prior
  tree state. Supplies only the Qt shell + dirty-rect recomposite signalling.
- **REQ/acceptance:** REQ-P4-UI-013 (SC-UI-013-1).
- **Status:** todo

### T13 — Recomposite frame-profile + conditional dirty-rect directive (AGT-10)
- **Owner:** AGT-10 · **Target:** perf directive → AGT-05 (`ui/canvas_scene.py`); `frame-profile` /
  `perf_profile` · **Predecessor:** T11
- **Do:** Run `perf_profile` on the **8K multi-layer recomposite** path (7680×4320, several layers,
  single-pixel edit → region recomposite). Assert ≤ `FRAME_BUDGET_MS = 16` recompositing only the
  dirty region (SC-UI-015-1). If over budget: issue an AGT-10 directive AGT-05 implements
  (dirty-rect scope, cached flattened group buffers per ADR-0007, `QOpenGLWidget` viewport,
  `setBspTreeDepth`) — budget **never** relaxed (Article VI §2). In-budget → closes no-op. Decision
  A1: conditional on an over-budget path.
- **T13 DONE — DIRECTIVE ISSUED (2026-07-02, `subagent-report-agt-10-rendering-performance-a4b1282f`).**
  Region path measured ~140 ms (~9× over) — FAIL. Root cause: full-canvas `PixelBuffer` alloc+fill
  floor. Directive → contract amendment (ADR-0007 §Amendment T13; this file T2/T3/T11): **D1** region-
  sized return (AGT-03), **D5** float32 (AGT-03), **D4** mandatory group cache + invalidation (AGT-03);
  **D2/D3** viewport-scoped attribute recomposite + opacity-drag debounce (AGT-05); **D6/D7**
  (QOpenGLWidget, setBspTreeDepth) DEFERRED. **RE-PROFILE required after D1 lands** to confirm a
  brush-sized dirty rect ≤ 16 ms (do NOT close SC-UI-015-1 until median ≤ 16 ms). AGT-10 also asks
  AGT-09/CI to extend `perf_profile` with a `--composite` mode (it currently profiles only `drawBackground`).
- **REQ/acceptance:** REQ-P4-UI-015 (SC-UI-015-1); Article VI; DEP-2; ADR-0007 (amended).
- **Status:** doing (directive issued; re-profile pending D1/D4/D5 + D2/D3)

### T14 — UI tests (pytest-qt, both themes, a11y, headless)
- **Owner:** AGT-06 · **Target:** `tests/ui/test_layer_panel.py`, `test_layer_masks.py`,
  `test_layer_reference_smart.py`, `test_canvas_composite.py`, `test_multi_canvas.py`,
  `test_layer_undo.py` · **Predecessor:** T9, T10, T11, T12
- **Do:** One pytest-qt test per SC-UI-001..014 scenario; qtbot; wait on signals; **both themes**;
  a11y (accessible name, keyboard reachability, focus visibility — SC-UI-016-1) via `a11y-audit`;
  headless (`QT_QPA_PLATFORM=offscreen`). Assert: panel lists top-to-bottom (SC-UI-001-1); each
  control sets the attribute + recomposites + pushes **exactly one** command (SC-UI-002..005);
  drag-reorder recomposites (SC-UI-006-1); add/remove/duplicate + last-layer refusal (SC-UI-007-1);
  group/ungroup reversible (SC-UI-008-1); mask/reference/smart affordances (SC-UI-009..011); canvas
  shows the **composite not one layer** (SC-UI-012-1) + edit updates it (SC-UI-012-2); **one
  undoable command per op** + exact undo (SC-UI-013-1); **multi-canvas isolation** (SC-UI-014-1/-2).
  Coverage ≥90/80; invoke `coverage_gate`.
- **REQ/acceptance:** Article IV + V; SC-UI-001..014, SC-UI-016-1, SC-UI-017-1.
- **Status:** todo

### T15 — i18n for Phase-4 strings
- **Owner:** AGT-07 · **Target:** `ui/` `.ts` catalogues (+ `string_audit_check`) · **Predecessor:** T9, T10, T11
- **Do:** Run `string_audit_check` (report unwrapped → AGT-05 fixes); extract wrapped strings with
  `pyside6-lupdate`; compile `.qm` with `lrelease`; confirm `changeEvent` retranslate on the layer
  panel + affordances + **blend-mode dropdown labels** (F5/F6). An unwrapped user-visible string is a
  blocking finding.
- **REQ/acceptance:** REQ-P4-UI-018 (SC-UI-018-1); Article V §2.
- **Status:** todo

### T16 — Slice-4C layering/cycle gate (AGT-01)
- **Owner:** AGT-01 · **Target:** `pixelart_creator/` · **Predecessor:** T14
- **Do:** **Invoke `check_layering` + `check_cycles`** — both exit 0: the new/extended `ui/` modules
  keep Qt inside `ui/` (`ui/commands.py` the sole bridge, LOGIC-013 path), `logic/`+`data/` stay
  Qt-free, no cycle introduced. Exit 2 → BLOCKED (A1-E3).
- **REQ/acceptance:** Article I; REQ-P4-UI-013 (Qt-free logic path).
- **Status:** todo

### T17 — Docs (usage + CHANGELOG + mkdocs + ADRs)
- **Owner:** AGT-08 · **Target:** `docs/` (usage pages, `CHANGELOG.md` Unreleased) · **Predecessor:** T14, T7
- **Do:** Document the layer & canvas system (blend modes, groups, masks, reference/smart layers,
  multi-canvas); add CHANGELOG Added entries keyed to REQ-P4-* (incl. REQ-P4-DATA-*); refresh mkdocs
  API pages from docstrings; run the pydocstyle gate. **ADR-0005** (blend working space + alpha
  convention), **ADR-0006** (`.pixproj` schema v2 + back-compat), **ADR-0007** (dirty-rect recomposite)
  are filed under `docs/adr/` by AGT-01 this session (§hand-off).
- **REQ/acceptance:** Article III §4 (docstrings); durable-docs coverage.
- **Status:** todo

### T18 — Commit(s), REQ-tagged, gate-green
- **Owner:** AGT-09 · **Target:** git (Conventional Commits) · **Predecessor:** T14, T15, T17
- **Do:** Commit 4A + 4B + 4C in gate-green increments (`feat(logic): …` / `feat(data): …` /
  `feat(ui): …`) carrying the governing REQ-P4-* / REQ-P4-DATA-* ids; each leaves quality + tests +
  coverage + layering + SDD gates green (Article IX). Human checkpoint before any push/tag.
- **REQ/acceptance:** Article IX.
- **Status:** todo

---

## Dependency graph

```
Slice 4A (Qt-free logic):
  T1 ─> T2 ─┐
            ├─> T3 ─> T4 ─> T5   (T3 needs T2 for BlendMode; T4 needs T2+T3)
  T1 ───────┘

Slice 4B (after T5):
  T3 + T5 ─> T6 ─> T7 ─> T8

Slice 4C (after T5; round-trip UI after T8; + stable Phase-1 UI):
  T5 ─> T9 ─┬─> T10 ─┐
            ├─> T11 ─┤
            └────────┼─> T12 ─> T14 ─> T16 ─┐
                     │          ├─────────────┼─> T17 ─> T18
              T11 ─> T13 (cond.)│             │
                     T15 ───────┘             │
```

Parallelisable after T5: Slice 4B (T6→T7→T8) and Slice 4C build (T9…) proceed in parallel; the
round-trip UI acceptance and docs depend on 4B (T8/T7). T13 fires the directive only if the
recomposite path is over budget. Slice 4C begins only after T5 (4A gate green) **and** a stable
Phase-1 UI substrate (document tabs + `ui/commands.py` + `ui/i18n.py` + palette panel).

## REQ → task coverage (every REQ-P4-* maps to ≥1 impl task + ≥1 test/verify task)

| REQ | Task(s) | | REQ | Task(s) |
| --- | --- | --- | --- | --- |
| REQ-P4-LOGIC-001 | T2, T4 | | REQ-P4-UI-001 | T9, T14 |
| REQ-P4-LOGIC-002 | T2, T4 | | REQ-P4-UI-002 | T9, T14 |
| REQ-P4-LOGIC-003 | T2, T4 | | REQ-P4-UI-003 | T9, T14 |
| REQ-P4-LOGIC-004 | T2, T4 | | REQ-P4-UI-004 | T9, T14 |
| REQ-P4-LOGIC-005 | T2, T4 | | REQ-P4-UI-005 | T9, T14 |
| REQ-P4-LOGIC-006 | T2, T4 | | REQ-P4-UI-006 | T9, T14 |
| REQ-P4-LOGIC-007 | T2, T4 | | REQ-P4-UI-007 | T9, T14 |
| REQ-P4-LOGIC-008 | T3, T4 | | REQ-P4-UI-008 | T9, T14 |
| REQ-P4-LOGIC-009 | T3, T4 | | REQ-P4-UI-009 | T10, T14 |
| REQ-P4-LOGIC-010 | T3, T4 | | REQ-P4-UI-010 | T10, T14 |
| REQ-P4-LOGIC-011 | T2, T3, T4 | | REQ-P4-UI-011 | T10, T14 |
| REQ-P4-LOGIC-012 | T2, T3, T4 | | REQ-P4-UI-012 | T11, T14 |
| REQ-P4-LOGIC-013 | T3, T4 | | REQ-P4-UI-013 | T12, T14 |
| REQ-P4-LOGIC-014 | T3, T4 | | REQ-P4-UI-014 | T11, T14 |
| REQ-P4-LOGIC-015 | T1, T3, T4 | | REQ-P4-UI-015 | T13, T14 |
| REQ-P4-DATA-001 | T6, T7 | | REQ-P4-UI-016 | T9, T10, T14 |
| REQ-P4-DATA-002 | T6, T7 | | REQ-P4-UI-017 | T9, T11, T14 |
| REQ-P4-DATA-003 | T6, T7 | | REQ-P4-UI-018 | T9, T15 |
| REQ-P4-DATA-004 | T6, T7 | | | |
| REQ-P4-DATA-005 | T6, T7 | | | |

All 38 REQ (15 LOGIC + 5 DATA + 18 UI) map to ≥1 implementation task **and** ≥1 test/verify task
(T4 logic / T7 data / T14 UI; T13 perf; T15 i18n). Cross-cutting: constants T1 (Art. II); layering
gates T5/T8/T16 (Art. I); perf T13 (Art. VI, conditional); i18n T15 + a11y/both-themes T14 (Art. V);
docs T17 (Art. III); commits T18 (Art. IX); `sdd-analyze` this session (Art. VIII).

## Hand-offs

- **AGT-08:** file **ADR-0005** (blend working space + straight-alpha convention, plan §5/§8),
  **ADR-0006** (`.pixproj` schema v2 + back-compat load, plan §7/§8), **ADR-0007** (dirty-rect
  region-scoped recomposite + cached group buffers, plan §10) under `docs/adr/` — authored by AGT-01
  this session; immutable acceptance for T2 (alpha convention), T6 (schema v2), T13 (recomposite).
- **AGT-02:** add a `REQ-P4-DATA-001..005` block to `traceability.md` (IDs + acceptance fixed in
  plan §7; owner AGT-04, tests `pending`). No LOGIC/UI REQ delta.
- **AGT-04:** the soft-light `D(Cb)` **W3C-variant** known-value test (plan §5) is acceptance-critical
  for T2/T4 (the most common blend bug); embed the research §3 reference values.
</content>
