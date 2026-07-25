# Traceability Matrix — Phase 4: `phase-4-layer-canvas`

REQ-ID ↔ dossier `S-id` / research `F` / forward-inherited primitive ↔ spec section ↔
Gherkin scenario(s) ↔ test id(s).

**Mode:** CLOSED / post-implementation (final Slice-4C gate, T16, 2026-07-02). Every REQ has ≥1
acceptance scenario **and** ≥1 landed test. AGT-04 authored the logic tests (pytest + Hypothesis);
AGT-06 authored the UI tests (pytest-qt, both themes). The two script-gated NFRs (REQ-P4-UI-015 perf,
REQ-P4-UI-018 string audit) are evidenced by AGT-10 `perf_profile` and AGT-07 `string_audit_check`.

> **AGT-01 note (T16 gate).** The `Test id(s)` column below is filled with the test **module(s)**
> that cover each REQ, not per-scenario `SC` node ids. Reason: the Phase-4 `SC-UI-*` scenario numbers
> collide with the Phase-1 `SC-UI-*` numbers across separate test files, so a per-scenario-id mapping is
> a matrix-ownership refinement that belongs to **AGT-02** (flagged, non-blocking). The module mapping
> is exact and verified against the tree at gate time.

Status legend:
- **covered** — has ≥1 Gherkin acceptance scenario **and** ≥1 landed test module.
- (no row is `uncovered`: every REQ has ≥1 scenario and ≥1 test.)

## Logic requirements

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P4-LOGIC-001 | S6, Phase-4 cap | §4, §11 | SC-L001-1 | `tests/logic/test_blend.py` | covered |
| REQ-P4-LOGIC-002 | Phase-4 cap, **F-blend (DEP-1)** | §4, §11 | SC-L002-1, SC-L002-2 | `tests/logic/test_blend.py` (soft-light D(Cb) known-value + Hypothesis determinism) | covered |
| REQ-P4-LOGIC-003 | **FU-3** (`color.blend_over`→normal), S7 | §4, §11 | SC-L003-1 | `tests/logic/test_blend.py` (NORMAL == `color.blend_over`) | covered |
| REQ-P4-LOGIC-004 | S7, Phase-4 cap | §4, §11 | SC-L004-1, SC-L004-2, SC-L004-3 | `tests/logic/test_blend.py` | covered |
| REQ-P4-LOGIC-005 | **REV-5** (`Layer.opacity`) | §4, §11 | SC-L005-1 | `tests/logic/test_blend.py` | covered |
| REQ-P4-LOGIC-006 | **REV-5** (`Layer.visible`) | §4, §11 | SC-L006-1 | `tests/logic/test_blend.py` | covered |
| REQ-P4-LOGIC-007 | Phase-4 cap, REQ-P4-LOGIC-001..003 | §4, §11 | SC-L007-1, SC-L007-2 | `tests/logic/test_blend.py` (+ Hypothesis N-NORMAL fold) | covered |
| REQ-P4-LOGIC-008 | **REV-5**, S7 | §4, §11 | SC-L008-1, SC-L008-2 | `tests/logic/test_document_layers.py` | covered |
| REQ-P4-LOGIC-009 | S7, Phase-4 cap | §4, §11 | SC-L009-1, SC-L009-2, SC-L009-3, SC-L009-4 | `tests/logic/test_document_layers.py` | covered |
| REQ-P4-LOGIC-010 | **REV-5** (`Layer.locked`), S7, Art. VII | §4, §11 | SC-L010-1 | `tests/logic/test_document_layers.py` | covered |
| REQ-P4-LOGIC-011 | Phase-4 cap (groups), S7 | §4, §11 | SC-L011-1, SC-L011-2, SC-L011-3 | `tests/logic/test_blend.py`, `tests/logic/test_document_layers.py` | covered |
| REQ-P4-LOGIC-012 | Phase-4 cap (masks), S7 | §4, §11 | SC-L012-1, SC-L012-2, SC-L012-3 | `tests/logic/test_blend.py`, `tests/logic/test_document_layers.py` | covered |
| REQ-P4-LOGIC-013 | Phase-4 cap (reference layers) | §4, §11 | SC-L013-1 | `tests/logic/test_document_layers.py` | covered |
| REQ-P4-LOGIC-014 | Phase-4 cap (smart, minimal), S6 | §4, §11 | SC-L014-1 | `tests/logic/test_document_layers.py` | covered |
| REQ-P4-LOGIC-015 | Art. II, Art. VII, S12 | §4, §11 | SC-L015-1, SC-L015-2 | `tests/logic/test_document_layers.py` | covered |

## UI requirements

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P4-UI-001 | **REV-5**, S6 | §4, §11 | SC-P4-UI-001-1 | `tests/ui/test_layer_panel.py`, `test_ui_branches.py` | covered |
| REQ-P4-UI-002 | **REV-5** (`Layer.opacity`→UI) | §4, §11 | SC-P4-UI-002-1 | `tests/ui/test_layer_panel.py` | covered |
| REQ-P4-UI-003 | **REV-5** (`Layer.visible`→UI) | §4, §11 | SC-P4-UI-003-1 | `tests/ui/test_layer_panel.py` | covered |
| REQ-P4-UI-004 | **REV-5** (`Layer.locked`→UI) | §4, §11 | SC-P4-UI-004-1 | `tests/ui/test_layer_panel.py` | covered |
| REQ-P4-UI-005 | REQ-P4-LOGIC-001, Phase-4 cap | §4, §11 | SC-P4-UI-005-1 | `tests/ui/test_layer_panel.py` (12-mode dropdown) | covered |
| REQ-P4-UI-006 | REQ-P4-LOGIC-009, S6 | §4, §11 | SC-P4-UI-006-1 | `tests/ui/test_layer_panel.py` | covered |
| REQ-P4-UI-007 | REQ-P4-LOGIC-009 | §4, §11 | SC-P4-UI-007-1 | `tests/ui/test_layer_panel.py` | covered |
| REQ-P4-UI-008 | REQ-P4-LOGIC-011 | §4, §11 | SC-P4-UI-008-1 | `tests/ui/test_layer_panel.py` | covered |
| REQ-P4-UI-009 | REQ-P4-LOGIC-012 | §4, §11 | SC-P4-UI-009-1 | `tests/ui/test_layer_panel.py`, `test_ui_branches.py` | covered |
| REQ-P4-UI-010 | REQ-P4-LOGIC-013 | §4, §11 | SC-P4-UI-010-1 | `tests/ui/test_layer_panel.py`, `test_ui_branches.py` | covered |
| REQ-P4-UI-011 | REQ-P4-LOGIC-014 | §4, §11 | SC-P4-UI-011-1 | `tests/ui/test_layer_panel.py`, `test_ui_branches.py` | covered |
| REQ-P4-UI-012 | S1, S7, REQ-P4-LOGIC-004 | §4, §11 | SC-P4-UI-012-1, SC-P4-UI-012-2 | `tests/ui/test_canvas_scene.py`, `test_layer_panel.py`, `test_ui_branches.py` | covered |
| REQ-P4-UI-013 | S7, C1, F1, REQ-P4-LOGIC-008/-009 | §4, §11 | SC-P4-UI-013-1 | `tests/ui/test_layer_panel.py` (one QUndoCommand per op) | covered |
| REQ-P4-UI-014 | S1, S6, S7 (extends REQ-P1-UI-020) | §4, §11 | SC-P4-UI-014-1, SC-P4-UI-014-2 | `tests/ui/test_layer_panel.py`, `test_main_window.py` (tab isolation) | covered |
| REQ-P4-UI-015 (NFR) | S1, S12, F2, F7, Art. VI, DEP-2 | §5, §11 | SC-P4-UI-015-1 | AGT-10 `perf_profile --composite` (region path; **re-profile open** per T13) + region-contract asserted in `tests/logic/test_blend.py` | covered (perf re-profile open) |
| REQ-P4-UI-016 (NFR) | Art. V §1 | §5, §11 | SC-P4-UI-016-1 | `tests/ui/test_layer_panel.py` (a11y: names/keyboard/focus) | covered |
| REQ-P4-UI-017 (NFR) | Art. V §3 | §5, §11 | SC-P4-UI-017-1 (+ every UI scenario in both themes) | `tests/ui/test_layer_panel.py` (both themes) | covered |
| REQ-P4-UI-018 (NFR) | Art. V §2, F6 | §5, §11 | SC-P4-UI-018-1 | AGT-07 `string_audit_check` + `tests/ui/test_layer_panel.py` (`changeEvent` retranslate) | covered |

## DATA requirements (`.pixproj` v2 — allocated by plan §7, ADR-0006)

> Allocated by AGT-01 at plan time per spec §8 DEP-3 (spec was scoped to LOGIC/UI). Tests landed in
> `tests/data/test_project_io_v2.py` (schema-v2 round-trip + defensive load) and
> `tests/data/test_project_io_convert.py`; the shipped v1 back-compat path is also exercised in
> `tests/data/test_project_io.py`.

| REQ-ID | Traces (plan §7 / ADR) | Spec § | Acceptance | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P4-DATA-001 | plan §7, ADR-0006 | (plan §7) | per-node blend_mode/opacity/visible/lock round-trip | `tests/data/test_project_io_v2.py` | covered |
| REQ-P4-DATA-002 | plan §7, ADR-0006 | (plan §7) | nested `LayerGroup` + child-order round-trip | `tests/data/test_project_io_v2.py` | covered |
| REQ-P4-DATA-003 | plan §7, ADR-0006 | (plan §7) | masked layer, mask bytes identical | `tests/data/test_project_io_v2.py` | covered |
| REQ-P4-DATA-004 | plan §7, ADR-0006 | (plan §7) | reference flag + smart-source link | `tests/data/test_project_io_v2.py` | covered |
| REQ-P4-DATA-005 | plan §7, ADR-0006, Art. VII | (plan §7) | defensive load (malformed/oversized/OOB/dangling/bad-mode/over-depth → `ProjectIOError`) + v1 back-compat read | `tests/data/test_project_io_v2.py`, `tests/data/test_project_io.py` | covered |

## Coverage summary

- **38 of 38 REQ-IDs** (15 LOGIC + 5 DATA + 18 UI) have **≥1 acceptance scenario AND ≥1 landed test**
  (0 uncovered).
- **~50 Gherkin scenarios** across the requirements (incl. the multi-mode blend outline
  SC-L002-1 and property scenarios SC-L002-2 / SC-L007-1 for Hypothesis).
- **0 REQ-IDs** are spec-only: even the NFRs carry a scenario + their script/audit gate.
- **Test ids:** all **CLOSED** — logic tests in `tests/logic/test_blend.py` (50) +
  `test_document_layers.py` (49); DATA tests in `tests/data/test_project_io_v2.py` (19) +
  `test_project_io_convert.py`; UI tests in `tests/ui/test_layer_panel.py` (26) +
  `test_ui_branches.py` (11) + `test_canvas_scene.py`; the two script-gated NFRs are evidenced by
  AGT-10 `perf_profile` (REQ-P4-UI-015 — region-path re-profile still open) and AGT-07
  `string_audit_check` (REQ-P4-UI-018).
- **Flag → AGT-02 (matrix ownership, non-blocking):** per-scenario `SC` node-id assignment (the
  Phase-4 `SC-UI-*` numbers collide with Phase-1's across files); the module mapping above is exact.

## Forward-inherited primitive traces (Article X §2 — explicit)

The prompt directs Phase 4 to formally inherit two Phase-1 primitives forward:

| Inherited primitive | Phase-1 origin | Phase-4 forward trace |
| --- | --- | --- |
| **FU-3** — `color.blend_over` (normal alpha compositing) | `logic/color.py` (shipped) | → REQ-P4-LOGIC-003 (NORMAL mode delegates to it) → REQ-P4-LOGIC-004/-007 (stack compositor folds it) |
| **REV-5** — `Layer.opacity` / `Layer.visible` / `Layer.locked` | `logic/document.py` `Layer` (shipped) | → REQ-P4-LOGIC-005/-006/-010 (compositor honours them) → REQ-P4-LOGIC-008 (reversible edits) → REQ-P4-UI-002/-003/-004 (panel controls) |

## Cross-layer trace (UI binds to new + shipped logic)

| UI REQ | Binds to logic REQ / shipped | Note |
| --- | --- | --- |
| REQ-P4-UI-002/-003/-004 | REQ-P4-LOGIC-005/-006/-010 + REV-5 | attribute controls over the shipped `Layer` flags |
| REQ-P4-UI-005 | REQ-P4-LOGIC-001 | blend-mode dropdown over the enum |
| REQ-P4-UI-006/-007 | REQ-P4-LOGIC-009 | reorder/add/remove/duplicate reversible ops |
| REQ-P4-UI-008 | REQ-P4-LOGIC-011 | group/ungroup |
| REQ-P4-UI-009 | REQ-P4-LOGIC-012 | mask attach/edit |
| REQ-P4-UI-010/-011 | REQ-P4-LOGIC-013/-014 | reference / smart (minimal) |
| REQ-P4-UI-012 | REQ-P4-LOGIC-004 | canvas renders the flattened composite |
| REQ-P4-UI-013 | REQ-P4-LOGIC-008/-009 via `ui/commands.py` | one QUndoCommand per layer op (Article I) |
| REQ-P4-UI-014 | extends REQ-P1-UI-020 (document tabs) | multi-canvas isolation |

## Dependency / gap list (for AGT-01 `sdd-plan` / `sdd-analyze`)

- **DEP-1 (Researcher).** `docs/research-blend-modes.md` grounds the per-mode formulas for
  REQ-P4-LOGIC-002 / SC-L002-1 — **not yet present**; the file's reference values fill the
  SC-L002-1 outline's `expected` column. AGT-01 must not invent the maths.
- **DEP-2 (AGT-10).** Dirty-rect recomposite strategy for REQ-P4-UI-015 / SC-P4-UI-015-1 — a
  full-canvas recomposite per edit will exceed `FRAME_BUDGET_MS` at 8K; a dirty-rect
  recomposite (and likely cached group buffers) is expected. Plan-level.
- **DEP-3 (AGT-01 / DATA).** `.pixproj` persistence of the new layer model (blend_mode,
  groups, masks, reference/smart flags) needs **`REQ-P4-DATA-*` IDs allocated at
  placement/plan time** (this spec is scoped to LOGIC/UI). ROADMAP "Done means"
  (round-trip through `.pixproj`) makes this a required companion slice; defensive load per
  Article VII.
- **Article II watch (BF-2).** AGT-01 must place `DEFAULT_LAYER_OPACITY`,
  `MAX_LAYERS_PER_FRAME`, `MAX_GROUP_NESTING_DEPTH` in `logic/constants.py` (no literals in
  `ui/`/`logic/`); the `BlendMode` enum lives in `logic/blend.py`.

## Recommended slicing (logic-first vertical slices)

1. **Slice A — blend + compositor (logic).** REQ-P4-LOGIC-001..007 (`logic/blend.py`:
   BlendMode enum, per-mode maths grounded by DEP-1, stack compositor honouring
   opacity/visibility/order/mode; NORMAL = FU-3). AGT-03 + AGT-04. *Blocked on DEP-1.*
2. **Slice B — reversible layer ops (logic).** REQ-P4-LOGIC-008..010, -015 (extend
   `document.py`: attribute/structural do-undo pairs, lock guard, bounds + constants T4).
   AGT-03 + AGT-04.
3. **Slice C — groups / masks / reference / smart (logic).** REQ-P4-LOGIC-011..014.
   AGT-03 + AGT-04.
4. **Slice D — `.pixproj` persistence (data).** DEP-3 / `REQ-P4-DATA-*` (AGT-01 to allocate)
   — serialise blend_mode, groups, masks, reference/smart; defensive validated load.
   AGT-03 + AGT-04.
5. **Slice E — layer panel (UI).** REQ-P4-UI-001..008, -013, -016..018 (panel list,
   opacity/visibility/lock/mode controls, reorder/add/remove/duplicate/group, one
   QUndoCommand per op, a11y/themes/i18n). AGT-05 + AGT-06.
6. **Slice F — mask/reference/smart affordances (UI).** REQ-P4-UI-009..011. AGT-05 + AGT-06.
7. **Slice G — canvas compositing + multi-canvas + perf (UI).** REQ-P4-UI-012, -014, -015
   (scene renders the composite; artboard tabs; dirty-rect recomposite within budget).
   AGT-05 + AGT-06, coordinated with **AGT-10** (DEP-2).

## Notes for `sdd-analyze` (AGT-01)

- Spec + matrix are internally consistent: 33 REQs, 33 with scenarios, 0 uncovered; tests
  `pending` (forward). SDD order: specify+clarify (this) → plan → tasks → analyze →
  implement → test.
- **No open clarification** (spec §10): all 15 ambiguities resolved with grounded defaults;
  the smart-layer scope risk is bounded (minimal scope + deferral, CL-9), not suspended.
- **Three named dependencies** (DEP-1 Researcher formulas, DEP-2 AGT-10 recomposite, DEP-3
  DATA `.pixproj` slice) must be resolved/allocated before/within the plan — none blocks
  this spec.
