# Analyze Report — Phase 4: Layer & Canvas System (C1 gate)

| Field | Value |
| --- | --- |
| Feature | `phase-4-layer-canvas` |
| Analyst | AGT-01 (Architecture) via `sdd-analyze` |
| Date | 2026-07-02 |
| Artifacts | `constitution.md` · `spec.md` · `plan.md` · `tasks.md` (all present) |
| Gate | Article VIII / C1 — pre-implement; defaults **closed** |

## 0. Gate precondition (Procedure step 1)

All four artifacts exist and are parseable. Gate not blocked by AN-E1/AN-E2.

## 1. Spec ↔ Constitution compliance (step 2)

| Article | Requirement | Spec / plan / tasks disposition | Verdict |
| --- | --- | --- | --- |
| I (three-layer purity) | logic/data zero Qt; `ui/commands.py` sole outside bridge | `logic/blend.py` + `document.py`/`constants.py` extensions Qt-free (plan §3.1); `data/project_io.py` Qt-free (§3.2); Qt only in `ui/` + `ui/commands.py` (§3.3/§10); **PL-D2** keeps `document → blend` one-way (blend never imports document); check_layering/cycles gates at T5/T8/T16 | PASS |
| II (constants) | tuning values in `constants.py`, imported by name | Plan §8 rules placement (T1 adds `DEFAULT_LAYER_OPACITY`, `MAX_LAYERS_PER_FRAME`, `MAX_GROUP_NESTING_DEPTH`); blend-formula magic numbers intrinsic-local (ADR-0001/0005); `BlendMode` enum = vocabulary → `blend.py` (BF-2); `FORMAT_VERSION` format-intrinsic → local (ADR-0006) | PASS |
| III (quality) | Black/isort/flake8/mypy; typed; docstrings | Plan §2; typed frozen contracts §6; enforced pre-commit/CI (AGT-09, T18); docstrings T2/T3/T6 | PASS |
| IV (testing) | ≥90/80, headless, one-per-criterion + regression | T4 (logic pytest+Hypothesis incl. soft-light W3C-D(Cb) dataset), T7 (data round-trip + defensive + v1 back-compat fixture), T14 (pytest-qt both themes + a11y); coverage_gate invoked | PASS |
| V (a11y/i18n/themes) | tr(), changeEvent, keyboard, both themes | UI tasks T9/T10 tr()+keyboard+changeEvent+focus; T14 both themes + a11y-audit; T15 i18n (string_audit + pyside6-lupdate); REQ-P4-UI-016/-017/-018 | PASS |
| VI (performance) | 16 ms/8K; over-budget → AGT-10 directive; buffer never culled | REQ-P4-UI-015; plan §10 + ADR-0007 (dirty-rect region-scoped composite + cached group buffers); T13 AGT-10 frame-profile, conditional directive; budget never relaxed; resident buffers never culled (F7) | PASS |
| VII (security) | defensive parse; portable paths; no eval/exec | `project_io` v2 defensive load (T6, ADR-0006): malformed/oversized/out-of-bounds/unknown-mode/over-depth/dangling-ref → `ProjectIOError`; pathlib; bounds `MAX_LAYERS_PER_FRAME`/`MAX_GROUP_NESTING_DEPTH` (LOGIC-015); lock/reference guard (LOGIC-010/013) | PASS |
| VIII (SDD gate) | analyze passes before implement | This report; no task dispatches implement past a red gate; gates T5/T8/T16 | PASS |
| X (REQ scheme + trace) | `REQ-P<n>-<LAYER>-<NNN>`; trace to S-id + criterion + test | 15 LOGIC + 18 UI (spec) + **5 DATA allocated** (plan §7, scheme-compliant `REQ-P4-DATA-001..005`); every REQ → task + test (tasks.md coverage table); `traceability.md` maps LOGIC/UI ↔ S-id/F/inherited ↔ SC ↔ test | PASS |

No constitution conflict (AN-D2 not triggered).

## 2. Plan ↔ Spec fidelity — drift check (step 2)

- **Modules:** spec §2 names `logic/blend.py` (new) + `document.py` (extend) + `ui/` panel/canvas
  + a DATA slice for `.pixproj`; plan §3 lists exactly these + the `constants.py` additions. **No
  drift.**
- **Blend-mode set:** spec REQ-P4-LOGIC-001 fixes exactly 13 members; plan §5 PL-D3 confirms the set
  == research's 12 separable modes + normal, and explicitly rules the four **non-separable** modes
  (hue/sat/color/luminosity) **out of scope** (research §2 marks them advanced/deferred; spec enum
  lists 13). **No drift** (the spec never enumerated the non-separable modes).
- **Normal = FU-3:** spec REQ-P4-LOGIC-003 requires NORMAL to delegate to `color.blend_over`; plan
  §5 + ADR-0005 pin the delegation. **No drift.**
- **Alpha convention:** the spec deferred the alpha convention to the plan (via DEP-1/research);
  plan §5 + ADR-0005 pin **straight (non-premultiplied) alpha, float32 0..1**, grounded verbatim in
  `docs/research-blend-modes.md` §0. Plan discharges the spec's plan-time dependency. **No drift.**
- **DEP-1 (formulas):** spec §8 flagged the research not-yet-present; it has **landed**
  (`docs/research-blend-modes.md`, COMPLETED, W3C), so plan §5 pins the per-mode formulas as AGT-03
  acceptance. **Discharged.**
- **DEP-2 (recomposite):** spec REQ-P4-UI-015 fixes the 16 ms budget and defers the strategy to
  AGT-10; plan §10 + ADR-0007 commit the architecture (region-scoped compositor API + cached group
  buffers) and assign AGT-10 the profiling + Qt-tuning directive (T13). **Consistent** (spec's
  own deferral honoured; AGT-01 fixes only the API-level commitment).
- **DEP-3 (DATA):** spec §8 directs AGT-01 to allocate `REQ-P4-DATA-*`; plan §7 allocates
  `REQ-P4-DATA-001..005` with acceptance rows and the schema-v2 decision (ADR-0006). **Discharged.**
- **Slicing:** spec §8 recommended fine slices; the dispatch collapses to 4A/4B/4C, and plan §4 ==
  tasks slice structure, preserving the logic-first order. **No drift.**
- **Clarifications:** all 15 spec §10 defaults are honoured (CL-2 default opacity/mode; CL-3 top-to-
  bottom; CL-4 bottom-to-top composite; CL-6/-7 bounds; CL-9 minimal smart; CL-10 mask model;
  CL-11 lock guards pixels only; CL-12 isolated group; CL-13 dirty-rect; CL-15 tab isolation). **No
  drift.**

## 3. Tasks ↔ Plan completeness + REQ coverage (steps 3–4)

- **REQ coverage:** all 38 REQ (15 `REQ-P4-LOGIC-*` + 5 `REQ-P4-DATA-*` + 18 `REQ-P4-UI-*`) appear
  in the plan (§3/§7) **and** in ≥1 implementation task **and** ≥1 test/verify task (tasks.md
  "REQ → task coverage" table). **No uncovered REQ.**
  - LOGIC: 001–007→T2; 008/009/010/013/014→T3; 011/012→T2+T3; 015→T1+T3. Tests: T4.
  - DATA: 001–005→T6. Tests: T7.
  - UI: 001–008→T9; 009–011→T10; 012/014→T11; 013→T12; 015→T13; 016/017/018→T9/T10/T11/T15. Tests:
    T14 (+ T13 perf, T15 i18n audit).
- **Orphan tasks:** none. Cross-cutting tasks each carry an acceptance link — T1 (Art. II / LOGIC-015),
  T5/T8/T16 (Art. I gates), T13 (Art. VI, conditional), T15 (Art. V i18n), T17 (Art. III docstrings +
  ADR filing), T18 (Art. IX). Acceptable per Phase-2/Phase-3 precedent.
- **Dependency coherence:** graph is acyclic and honours the substrate order (T1 → T2 → T3 → T4 → T5
  gate; 4B T6→T7→T8 after T5; 4C T9… after T5, round-trip/docs after T8/T7). T3 correctly depends on
  T2 (needs `BlendMode`); T6 on T3 (extended model) + T5; T11/T12 on T9; T13 on T11; T14 on
  T9/T10/T11/T12.
- **Acceptance-critical scenarios carried:** blend known-values incl. **soft-light W3C `D(Cb)`
  dataset** (SC-L002-1)→T2/T4 (plan §5, the flagged common bug); NORMAL==`blend_over` (SC-L003-1)
  →T2/T4; N-NORMAL==folded blend_over (SC-L007-1)→T4; group composite-then-blend (SC-L011-1)→T2/T3/T4;
  mask modulation + all-max==no-mask (SC-L012-1/-2)→T2/T3/T4; reversibility apply∘undo (SC-L008-*,
  SC-L009-*, SC-UI-013-1)→T3/T4/T12/T14; bounds (SC-L011-3/SC-L015-1)→T1/T3/T4; **v1 back-compat
  load** (REQ-P4-DATA-005)→T6/T7 fixture; **composite-not-one-layer** (SC-UI-012-1)→T11/T14;
  **multi-canvas isolation** (SC-UI-014-1/-2)→T11/T14; **8K dirty-rect recomposite ≤16 ms**
  (SC-UI-015-1)→T13.

## 4. Cross-artifact conflicts (step 4)

None blocking. Three informational notes:

- **INFO-1 — `REQ-P4-DATA-001..005` are allocated by the plan, not the spec.** **Not drift:** spec
  §8 DEP-3 explicitly directs AGT-01 to allocate the DATA IDs at plan/placement time (the spec was
  scoped to LOGIC/UI). Allocated per Article X in plan §7 with acceptance rows; recorded in
  ADR-0006. Hand-off to AGT-02 to mirror them into `traceability.md` (matrix ownership). Authorised;
  no action blocks the gate.
- **INFO-2 — the four non-separable blend modes are excluded from `BlendMode`.** **Not conflict:**
  the spec enum lists exactly 13 (never the non-separable four); the research §2 marks them
  advanced/deferred. Plan PL-D3 records the exclusion explicitly. Consistent; no action.
- **INFO-3 — new `ui/layer_panel.py` module name** is a plan choice (spec said "a layers panel" in
  `ui/`, no filename). **Not drift:** naming follows CONVENTIONS (`Layer_Panel(QWidget)`, PascalCase
  + `_Panel`); recorded in STRUCTURE.md. No action.

## 5. Gate verdict (step 5 / Decision AN-D1)

- Unresolved-findings list: **empty**.
- **VERDICT: PASS (Branch A).** Cross-artifact consistency holds; all 38 REQ (15 LOGIC + 5 DATA +
  18 UI) are covered by tasks and by tests; plan + tasks conform to the constitution; the blend
  formulas are grounded (research landed) and the **alpha convention pinned** (straight/non-premultiplied,
  ADR-0005); the `.pixproj` **schema-v2 + v1 back-compat** decision is ruled (ADR-0006); the
  **dirty-rect region-scoped recomposite** is committed (ADR-0007) with AGT-10 profiling assigned;
  `REQ-P4-DATA-*` allocated (plan §7); the compositor cycle-avoidance (PL-D2) keeps `document → blend`
  one-way. The implement gate may open for Slice 4A on the orchestrator's dispatch; Slice 4C
  additionally requires a stable Phase-1 UI substrate (document tabs + `ui/commands.py` + `ui/i18n.py`
  + palette panel).
- Layering/cycle scripts (run this session by AGT-01, outside this skill): `check_layering` exit 0
  (`clean, 27 modules`), `check_cycles` exit 0 (`no cycles, 63 modules`).

## 6. Final Slice-4C gate (T16, post-implementation — 2026-07-02)

Re-run by AGT-01 after ALL Phase-4 work (4A logic + 4B `.pixproj` v2 + 4C UI) landed, incl. the T13
perf amendment and the ADR-0008 mode-authority defect fix. This is the gate immediately before commit
(T18). Defaults closed; verdict below only after every check passed.

**6.1 Deterministic layering/cycle checks (Decision A1-D3).**
- `python scripts/check_layering.py` → **exit 0** (`clean, 28 modules`). `logic/` + `data/` import
  **zero Qt**; Qt lives only in `ui/` (`ui/commands.py` the sole undo-bridge, LOGIC-013 path).
- `python scripts/check_cycles.py` → **exit 0** (`no cycles, 65 modules`).
- Three-layer rule spot-verified after ADR-0008: `blend.py` imports **no** `document` (PL-D2 —
  consumes nodes via the `CompositeNode` Protocol); `document.py` → `blend`/`palette_ops` edges are
  **one-way / acyclic** (`from pixelart_creator.logic.blend import BlendMode, composite_stack`;
  `from pixelart_creator.logic import palette_ops`), and `palette_ops`/`blend` never import
  `document`. (Module counts rose 27→28 / 63→65 as `blend.py` + the new `ui/layer_panel.py` landed.)

**6.2 Amendments absorbed with the contract signature UNCHANGED.**
- **T13 perf amendment (ADR-0007 §Amendment T13).** `composite_stack(nodes, width, height, *,
  region=None)` — **signature unchanged**. The amendment is a *return-shape* correction:
  `region=(x,y,w,h)` now returns a **region-sized** `PixelBuffer(w,h)` (numpy `(h,w,4)`, implied origin
  `(x,y)`) instead of a full-canvas buffer (removing the ~140 ms 8K region-path floor); D5 float32
  working dtype; D4 mandatory group-cache + ancestor invalidation. Blend maths / public API surface
  unchanged, so plan §6 contracts and STRUCTURE.md remain valid.
- **ADR-0008 mode-authority change.** `Document.mode` is the single colour-mode authority; conversion
  is a Document-level reversible op (`make_convert_to_indexed_command` / `make_convert_to_rgba_command`,
  already in the plan §7 / STRUCTURE.md surface) delegating pixels to `palette_ops.to_indexed`/`to_rgba`.
  The buffer-level `make_to_indexed_command`/`make_to_rgba_command` + `SupportsBuffer` were retired.
  The Document/palette_ops **public signatures the plan committed are unchanged**; this closes the T14
  QA defect (`BlendError: composite_stack requires RGBA layer buffers`) on indexed-mode workflows.

**6.3 REQ coverage — implementation ∧ test (C1 §3, verified against the tree).**
- **38 / 38 REQ implemented**, **38 / 38 tested**, **0 uncovered.**
  - LOGIC 001–015 → `logic/blend.py` (+ `constants.py`) + `logic/document.py`; tests
    `tests/logic/test_blend.py` (50) + `tests/logic/test_document_layers.py` (49) (+ `test_document.py`,
    `test_document_convert.py`).
  - DATA 001–005 → `data/project_io.py` (`FORMAT_VERSION = 2`); tests `tests/data/test_project_io_v2.py`
    (19) + `test_project_io_convert.py` (+ v1 back-compat in `test_project_io.py`).
  - UI 001–018 → `ui/layer_panel.py` (new), `ui/canvas_scene.py`, `ui/main_window.py`, `ui/commands.py`
    (extended); tests `tests/ui/test_layer_panel.py` (26) + `test_ui_branches.py` (11) +
    `test_canvas_scene.py` + `test_indexed_mode.py`. `traceability.md` TEST column updated (module-level;
    per-`SC`-id assignment flagged to AGT-02 as the `SC-UI-*` numbers collide across phases).
- **BlendMode member count reconciled:** the enum ships **12** members (NORMAL + 11 W3C separable;
  FU-13 corrected from the earlier "13" double-count of NORMAL). Code (`blend.py`, `layer_panel.py`
  iterating `list(BlendMode)`) is correct; the stale "13" text in STRUCTURE.md was corrected this
  session.

**6.4 Open item (non-blocking for the layering/consistency gate).**
- **REQ-P4-UI-015 perf re-profile.** T13 status is `doing`: the AGT-10 directive landed (D1/D4/D5
  implemented) but the 8K region-path **re-profile confirming median ≤ FRAME_BUDGET_MS = 16 ms is still
  open** (AGT-10 owns SC-UI-015-1; `perf_profile --composite` mode requested from AGT-09/CI). This is an
  Article VI NFR gate owned by AGT-10, **not** a layering/cycle or cross-artifact-consistency finding —
  it does not block the T16 structural gate, but the orchestrator must not treat SC-UI-015-1 as closed
  until AGT-10 reports the passing re-profile.

**6.5 Final verdict (Decision AN-D1 / A1-D2 / A1-D3).**
- Layering exit 0; cycles exit 0; cross-artifact consistency holds; 38/38 REQ implemented ∧ tested.
- **VERDICT: PASS.** The T16 structural + consistency gate is **GREEN**. The one open item (6.4) is an
  AGT-10-owned perf NFR carried forward, not a gate finding.
