# Tasks — Phase 12: Performance & Scalability

| Field | Value |
| --- | --- |
| Feature | `phase-12-performance-scalability` |
| Author | AGT-01 (Architecture) via `sdd-tasks` |
| Date | 2026-07-07 |
| Over | `plan.md` + `docs/adr/0033-*` (flatten strategy) + `docs/adr/0034-*` (drag preview) — **slice-by-slice**, each an independently gate-green, CI-green shippable increment. Slice A (full-frame flatten fast-path + tiling + dirty-tile + `--full-frame` gate) → Slice B (viewport recomposite split-cache + opacity-drag LOD preview + viewport-scale gate) → Slice F (artifact + docstring hygiene). |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII). **NO implementation begins until C1 is green — this gate is the blocker.** Each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done` — plus, from 2026-07-30, a **qualified** `done — …` for a task
whose obligation is met by evidence the **default CI gate does not run**; the qualifier names that limit and
is never shorthand for continuous verification. (The legend previously read simply *"`todo` | `doing` |
`done`"*; see the T12-B-03 scale-clause update under the Slice-B table.) Owners per the delegation table: **AGT-10** perf directive +
scenario + RE-PROFILE ship gate; **AGT-03** logic code; **AGT-05** UI code; **AGT-04** logic regression +
correctness + perf-probe tests; **AGT-06** UI/a11y/both-theme tests; **AGT-07** string audit/i18n;
**AGT-08** docs + FU-4 docstrings; **AGT-09** ci.yml + commits; **AGT-01** architecture/analyze/gate +
Slice-F artifact reconciliation; **AGT-02** traceability + scenario renumber. One owner per task;
deterministic sub-steps name their script. Every REQ maps to ≥ 1 impl + ≥ 1 test/verify task. **Per-slice
performance flow:** AGT-10 directive → AGT-03/AGT-05 implement → AGT-04/AGT-06 regression + correctness →
**AGT-10 RE-PROFILE ship gate** → AGT-01 final gate → AGT-08 docs → AGT-07 i18n (if strings) → AGT-09
commit + gate wiring.

**Byte-exact invariant (CENTRAL):** the optimised full-frame flatten (Slice A) and the committed
full-resolution viewport recomposite (Slice B) MUST be **byte-equal** to the current shipped compositor
for NORMAL + all 11 separable modes, zero tolerance, deterministic (REQ-P12-LOGIC-002/-004). **The only
16 ms-bound path is the drag preview (REQ-P12-UI-001);** the flatten and the commit recomposite are batch
paths bounded by loose named ceilings, **not** asserted vs 16 ms (Article VI; budget never relaxed).

---

## Slice A — cold full-frame 8K multi-layer flatten (`logic/`; FU-P5-PERF)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-A-00 | **AGT-10 directive:** confirm the dependency-free flatten strategy at build time (baseline §3/§5, ADR-0033): uint8 straight-alpha source-over fast-path for NORMAL/opacity-1/unmasked layers; blocked/tiled full-frame working set via `_composite_region` (thread-pool fan optional); dirty-tile flatten-cache reuse; optional off-thread via `composite_warmer`. Byte-exact invariant is non-negotiable. | AGT-10 | perf directive → AGT-03 | analyze C1 | LOGIC-001 / baseline §3 FU-P5 | todo |
| T12-A-01 | Add `COMPOSITE_FULL_CEILING_MS = 3000` (loose full-frame catastrophic ceiling; mirrors full-8K `TILEMAP_VIEWPORT_CEILING_MS`) with a citation docstring. **Name DISTINCT from every shipped ceiling** (`COMPOSITE_REGION_CEILING_MS`/`TILEMAP_VIEWPORT_CEILING_MS`/`OVERLAY_FRAME_CEILING_MS`/`REALTIME_APPLY_CEILING_MS`). Value is AGT-10-RE-PROFILE-confirmed at T12-A-05. | AGT-03 | `logic/constants.py` | T12-A-00 | LOGIC-003 / plan §8, ADR-0033 §5 | todo |
| T12-A-02 | Optimise `composite_stack(region=None)` **in place**: uint8 source-over fast-path (byte-exact vs `_blend_over_arrays` for NORMAL/op-1/unmasked) + float32 only for non-normal/masked/partial-opacity; blocked/tiled working set over disjoint tiles through `_composite_region` (byte-identical to the single-shot path); dirty-tile flatten-cache seam reusing the `_flatten_group` MRU + `document.py` ancestor invalidation. **Public signature preserved.** Zero Qt (`document`-free, PL-D2). | AGT-03 | `logic/blend.py` | T12-A-01 | LOGIC-001, -002 / "cold full-frame flatten … at or under ceiling", "byte-exact" | todo |
| T12-A-03 | Byte-exact + determinism regression tests (headless): for NORMAL **and each of the 11 separable modes**, the optimised full-frame `composite_stack(region=None)` output is **byte-equal** to the current compositor over the same layers/opacities/masks (bit-exact, no tolerance); run twice ⇒ byte-identical; representative 4-layer + 8-layer mixed-blend stacks; no mode dropped/altered. `check_layering`/`check_cycles` exit 0 (compositor stays Qt-free `logic/`). | AGT-04 | `tests/logic/test_blend_fullframe.py`, `scripts/*` (invoke) | T12-A-02 | LOGIC-002 / SC-P12-LOGIC-002-1/-2 | todo |
| T12-A-04 | Author the `perf_profile` `--full-frame` (`region=None`) full-canvas flatten scenario (Qt-free numpy + `logic/` only, mirroring `--composite`): 8-layer mixed-blend 8K stack, cold, median/p95 vs `COMPOSITE_FULL_CEILING_MS`; exit 0/1/2 per the harness contract. | AGT-10 | `scripts/perf_profile.py` | T12-A-02 | LOGIC-003 / SC-P12-LOGIC-003-1 | todo |
| T12-A-05 | **AGT-10 RE-PROFILE ship gate:** measure the optimised cold full-frame flatten (4L + 8L) via `--full-frame` on the CI-class runner; confirm at/under `COMPOSITE_FULL_CEILING_MS` (4L comfortably under) and that the catastrophic 20–43 s cost is eliminated; confirm or tighten the constant value (feed back to T12-A-01 if tightened). Not asserted vs 16 ms. | AGT-10 | re-profile report → AGT-01/AGT-03 | T12-A-04, T12-A-03 | LOGIC-001, -003 / SC-P12-LOGIC-001-1/-2 | todo |
| T12-A-06 | Wire the `--full-frame` gate into CI at `COMPOSITE_FULL_CEILING_MS` (passed from the named constant, no literal — the `--composite`/`--tilemap` precedent); place after the existing compositor gate. | AGT-09 | `.github/workflows/ci.yml` | T12-A-05 | LOGIC-003 / SC-P12-LOGIC-003-1 | todo |
| T12-A-07 | Re-run `check_layering --root pixelart_creator` + `check_cycles --root pixelart_creator`: confirm the flatten optimisation adds no Qt to `logic/`, no new module, no new edge, no cycle; module count unchanged (178/179). Must exit 0. | AGT-03 | `scripts/*` (invoke) | T12-A-02 | LOGIC-001 / Article I / plan §11 | todo |

## Slice B — whole-viewport recomposite + live opacity-slider drag (`logic/` + `ui/`; FU-16b)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-B-00 | **AGT-10 directive:** confirm the dependency-free Slice-B strategy (baseline §3/§5, ADR-0034): split-cache `composite(below)`/`composite(above)` around the dragged layer (≈2–3 blends, not 12); downsampled-LOD preview holding 16 ms during drag; cull to the exposed viewport rect + dirty region; throttle/off-thread ticks (Phase-4 D3 + Phase-5 warmer); full-resolution byte-exact recomposite on commit. | AGT-10 | perf directive → AGT-03/AGT-05 | analyze C1 | LOGIC-004, UI-001 / baseline §3 FU-16 | todo |
| T12-B-01 | Add `VIEWPORT_RECOMPOSITE_CEILING_MS = 2000` (loose viewport-scale catastrophic ceiling) with a citation docstring. **Name DISTINCT from every shipped ceiling.** Value AGT-10-RE-PROFILE-confirmed at T12-B-06. | AGT-03 | `logic/constants.py` | T12-B-00 | LOGIC-005 / plan §8, ADR-0034 §4 | todo |
| T12-B-02 | Add the pure `logic/blend.py` Slice-B support seam (Qt-free, additive, `document`-free): split-cache helper for `composite(below idx)` / `composite(above idx)` around a target index (byte-exact when re-composed on commit) + a pure nearest-neighbour **LOD downsample** helper for the preview. No public signature break. | AGT-03 | `logic/blend.py` | T12-B-01 | LOGIC-004 / "recomposite path imports no Qt", byte-exact | todo |
| T12-B-03 | Byte-exact recomposite regression tests (headless): the full-resolution whole-viewport recomposite (up to 1920², ≥ 12 layers) via the split-cache commit path is **byte-equal** to the current compositor over the same inputs (NORMAL + 11 modes, no tolerance); the recomposite path imports no Qt (`check_layering`); not asserted vs 16 ms. | AGT-04 | `tests/logic/test_blend_range.py` (**verified present + read**; covers the NORMAL + 11-mode, no-tolerance invariant, small-canvas only) **+ the *scale* clause: `tests/ui/test_opacity_drag.py::test_commit_byte_exact_at_1920_scale_12_layers_opt_in`** (1920²/12 layers, both themes — **OPT-IN**: requires `PIXELART_OPACITY_SCALE_TEST=1` *and* carries `@pytest.mark.slow`; see the scale-clause update under this table), `scripts/*` (invoke) | T12-B-02 | LOGIC-004 / SC-P12-LOGIC-004-1/-2 | **done — scale clause verified OPT-IN ONLY**: passes at 1920²/12 layers in both themes, but `PIXELART_OPACITY_SCALE_TEST=1` + `@pytest.mark.slow` keep it **out of CI's default gate** (on demand, not continuous) |
| T12-B-04 | Opacity-slider **drag lifecycle** in `ui/layer_panel.py`: on drag-start capture the split-cache; per tick render the downsampled-LOD preview (throttled via the Phase-4 D3 debounce; off-thread via `composite_warmer`, cached in `frame_cache`); on release/commit apply the full-resolution byte-exact recomposite and display it through the existing dirty-rect path. **No compositing maths in the widget** (calls `logic/blend`). `tr()` + `changeEvent` preserved; both themes identical. | AGT-05 | `ui/layer_panel.py`, `ui/composite_warmer.py`, `ui/frame_cache.py`, `ui/canvas_scene.py`/`ui/canvas_view.py` | T12-B-02 | UI-001 / SC-P12-UI-001-1/-2 | todo |
| T12-B-05 | pytest-qt tests (both themes, offscreen): during an opacity drag on a low-zoom ≥ 12-layer 8K document, each per-tick downsampled preview **holds the 16 ms `FRAME_BUDGET_MS`** and the UI stays responsive (no multi-second freeze); on release the full-resolution recomposite is applied and the committed pixels match the current build (byte-exact per T12-B-03); light and dark behave identically; a11y (focus/keyboard) on the slider preserved. | AGT-06 | `tests/ui/test_opacity_drag.py` (**verified present + read**; the drag-lifecycle, byte-exact-commit, both-theme and a11y clauses are covered there — the *8K-document scale* and the *tight 16 ms wall-clock* clauses are **not**, see the note under this table) | T12-B-04 | UI-001 / SC-P12-UI-001-1/-2 | todo |
| T12-B-06 | Author the dedicated `perf_profile --viewport-recomposite` **viewport-scale split-cache COMMIT gate** scenario (region ≥ 1080²/1920², 12 layers) at `VIEWPORT_RECOMPOSITE_CEILING_MS` (a distinct flag from the shipped 16-px `--composite` gate — the shipped `scripts/perf_profile.py` implements `--viewport-recomposite`, not a `--composite` extension); **AGT-10 RE-PROFILE ship gate:** measure the optimised commit recomposite on the CI-class runner, confirm at/under the ceiling (2–7 s catastrophe eliminated), confirm/tighten the constant + the gate scenario (feed back to T12-B-01). Not asserted vs 16 ms. | AGT-10 | `scripts/perf_profile.py`, re-profile report → AGT-01/AGT-03 | T12-B-02 | LOGIC-005 / SC-P12-LOGIC-005-1 | todo |
| T12-B-07 | Wire the `--viewport-recomposite` gate into CI at `VIEWPORT_RECOMPOSITE_CEILING_MS` (passed from the named constant, no literal). | AGT-09 | `.github/workflows/ci.yml` | T12-B-06 | LOGIC-005 / SC-P12-LOGIC-005-1 | todo |
| T12-B-08 | String audit (`string_audit_check`) on `ui/layer_panel.py` **only if** the drag lifecycle adds any new user-visible string (e.g. a "preview" status); wrap in `tr()` + `changeEvent` retranslate. Skipped if no new string. | AGT-07 | `ui/layer_panel.py` | T12-B-04 | UI-001 (Article V) | todo |
| T12-B-09 | Re-run `check_layering` + `check_cycles`: confirm the split-cache/LOD seam adds no Qt to `logic/`, no new module/edge/cycle; module count unchanged. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T12-B-02 | LOGIC-004 / Article I / plan §11 | todo |

**T12-B-03 correction (2026-07-30) — this task cited a test file that does not exist.** The Target-file
cell previously read: *"`tests/logic/test_viewport_recomposite_byte_exact.py`, `scripts/*` (invoke)"*.
**That was wrong:** there is no file of that name anywhere in the repository — no
`*byte_exact*` test module exists at all (the only `byte-exact` filenames in the tree are the two ADRs
`docs/adr/0033-…-byte-exact.md` and `docs/adr/0034-…-byte-exact-commit.md`), and `tests/logic/` contains no
`recomposite`- or `viewport`-stemmed module. This is the **sibling** of the `test_viewport_recomposite_perf`
dangling stem corrected in `traceability.md` earlier today (M-8/M-9); that correction predicted this one.

**What genuinely covers the obligation.** `tests/logic/test_blend_range.py` — **opened and read before being
cited here** (596 lines; module docstring: *"Byte-exactness + helper tests for the Phase-12 Slice-B
`composite_range` seam"*, and *"REQ-P12-LOGIC-004 makes the commit byte-exactness a HARD acceptance
criterion"*). It asserts exactly T12-B-03's byte-equality contract against the same oracle the task names
(*"the current compositor"* = the shipped `composite_stack`), with **no tolerance** (`np.array_equal`), via
the helper `_assert_commit_byte_exact(nodes, w, h, region)` which walks **every** split `k` in
`range(0, N+1)`:

- `test_commit_byte_exact_each_mode_hard_edged` and
  `test_commit_byte_exact_each_mode_partial_alpha_non_normal_above` — both parametrised over
  `ALL_MODES` (pinned at 12 = NORMAL + 11 separable by `test_separable_mode_count_is_eleven`), each across
  three regions (`None`, full-rect, sub-rect). This is the **NORMAL + 11 modes, no tolerance** clause.
- `test_commit_byte_exact_representative_mixed_stack`, `test_commit_byte_exact_with_nested_group_above`,
  `test_commit_base_is_not_mutated`.
- `test_property_split_cache_commit_byte_exact_and_deterministic` — a Hypothesis property over random
  bounded stacks (modes / opacity / masks / visibility / partial alpha) and a random split `k`.
- Qt-freeness of the path is inherent (this module imports no Qt) and is separately gated by T12-B-09.

**Scope shortfall stated honestly, not papered over.** T12-B-03's **scale** clause — *"up to 1920², ≥ 12
layers"* — is **NOT** covered by `test_blend_range.py`: its byte-exact-commit stacks are 3–7 layers on
canvases from 24×22 up to 30×33 (largest dimension anywhere in the module: 33 px),
and the Hypothesis strategy is bounded to `max_value=9` per dimension and `max_value=6` layers. The
byte-exactness *invariant* is mode- and split-exhaustive but small-canvas only.

**SUPERSEDED (2026-07-30, same day) — the scale residual this note recorded is now CLOSED.** The paragraph
above previously ended: *"The largest byte-exact commit assertion in the tree is in
`tests/ui/test_opacity_drag.py` (also read: `_W = _H = 300`, `_LAYERS = 12` — so `≥ 12 layers` is met,
`1920²` is **not**, and that file's own docstring assigns pure byte-exactness to AGT-04's logic tests).
**No test asserts commit byte-exactness at 1920².** That residual belongs to AGT-04/AGT-06, is recorded
here rather than declared satisfied, and this correction does not close it."* **Both of those claims are
now false**: a 1920²/12-layer byte-exact commit test exists and passes (next note). What is **not**
retracted: `test_blend_range.py` itself still asserts byte-exactness only on 24×22–30×33 canvases with 3–7
layers, so the `logic/` module carries no 1920² assertion — the scale evidence lives in the `ui/` module,
and it is opt-in.

**T12-B-03 scale-clause update (2026-07-30) — the *scale* clause is SATISFIED, and satisfied OPT-IN.**
Both halves are load-bearing; neither may be read without the other.

- **It exists and it passes.** `tests/ui/test_opacity_drag.py::test_commit_byte_exact_at_1920_scale_12_layers_opt_in`
  drives the real commit path (`begin_opacity_drag` → opacity change → `refresh_visible`) on a **1920×1920,
  12-layer** document and asserts the committed pixels equal `composite_stack` **byte-for-byte over the full
  region** (`np.array_equal`, no tolerance). Run directly by the orchestrator: **both themes PASS**
  (23.70 s and 23.51 s). This is T12-B-03's own literal ceiling — *"up to 1920², ≥ 12 layers"* — met.
- **CI never runs it.** The test is double-gated: `@pytest.mark.slow` **and** an in-body skip unless the
  environment variable **`PIXELART_OPACITY_SCALE_TEST=1`** is set. The default gate deselects `slow`
  (`-m "not slow and not gpu and not cloud_live and not assistant_live and not integration"`, `ci.yml`, job
  `quality-gate`) and **no job overrides it** — the default run of that module is 24 passed, 2 skipped.
  The pattern mirrors this repository's existing docker/nginx acceptance tests. A 1920² byte-exactness
  regression is therefore **detectable on demand, not detected automatically**.
- **How to run it** (no hunting required):
  `QT_QPA_PLATFORM=offscreen PIXELART_OPACITY_SCALE_TEST=1 python -m pytest tests/ui/test_opacity_drag.py -k test_commit_byte_exact_at_1920_scale_12_layers_opt_in -m slow -q`
- **Row edits this note records.** The Status cell previously read *"`todo`"* and now reads
  *"**done — scale clause verified OPT-IN ONLY** …"*; the Target-file cell previously read
  *"`tests/logic/test_blend_range.py` (**verified present + read**; the invariant is covered there, the
  *scale* clause is not — see the note under this table), `scripts/*` (invoke)"* and now additionally cites
  the opt-in scale test **with its env var and marker**. No requirement id, task id, dependency or
  acceptance link changed (T12-B-03 / LOGIC-004 / SC-P12-LOGIC-004-1/-2 / dep T12-B-02 are untouched).
- **Agreement with `traceability.md`.** That matrix (AGT-02's artifact, corrected earlier today, **not**
  touched by this edit) records REQ-P12-LOGIC-004's T12-B-03 scale clause as *satisfied via opt-in* and
  flags it as the one clause whose coverage is **not continuous**. This row now says the same thing; the
  task list no longer contradicts the matrix.

**T12-B-05 correction (2026-07-30) — RESOLVED; was the third dangling stem in this family.** The
Target-file cell previously read *"`tests/ui/test_opacity_drag_responsive.py`"* — **no file of that name
exists anywhere in the repository**; `tests/ui/` holds `test_opacity_drag.py` (the `*_responsive.py`
modules in that directory belong to other features: `test_automation_responsive.py`,
`test_cloud_responsive.py`, `test_export_responsive.py`). This was flagged here as unrepaired when
T12-B-03 was corrected, then authorised and fixed in the same session. Family history:
(1) `test_viewport_recomposite_perf` in `traceability.md` (M-8/M-9); (2) T12-B-03's
`test_viewport_recomposite_byte_exact.py`; (3) this one. Common cause: rows authored against *intended*
filenames that later consolidated, never reconciled.

**What genuinely covers T12-B-05.** `tests/ui/test_opacity_drag.py` — **opened and read before being cited**
(468 lines; docstring: *"Opacity-drag preview + byte-exact commit UI acceptance tests (Phase-12 Slice B) …
one pytest-qt test per acceptance criterion of the FU-16b opacity-drag / low-zoom viewport recomposite
interaction … REQ-P12-UI-001"*). It is the **only** module in the tree that exercises
`begin_opacity_drag`. Clause-by-clause against T12-B-05:

- **pytest-qt, offscreen, both themes** — covered: real `qtbot` + `Layer_Panel`/`CanvasScene`/`Canvas_View`
  widgets; `tests/ui/conftest.py` forces `QT_QPA_PLATFORM=offscreen` before any `QApplication`, and its
  `theme` fixture is `@pytest.fixture(params=[THEME_LIGHT, THEME_DARK], autouse=True)`, so **every** test in
  the module runs twice, once per theme.
- **≥ 12 layers, low-zoom whole-viewport drag** — covered structurally: `_LAYERS = 12`, and the viewport is
  sized so `_clamp_visible_region() == (0, 0, _W, _H)` (the whole canvas is the culled region), whose area
  exceeds `OPACITY_PREVIEW_MAX_PX` and so forces a genuine LOD factor `> 1` — the branch "low zoom" exists
  to reach. Literal zoom is `1.0`, not `< 1`.
- **UI stays responsive / no multi-second freeze** — covered: `test_preview_uses_bounded_lod_path_not_full_recomposite`
  asserts the per-tick mechanism (throttled action rebound to `_preview_opacity_drag`, `cache.factor > 1`,
  each cached working set `<= OPACITY_PREVIEW_MAX_PX`) plus a wall-clock ceiling.
- **Commit applies the full-resolution byte-exact recomposite** — covered, incl. end-to-end through the real
  `QSlider` signals: `test_commit_byte_exact_realistic_all_normal`,
  `test_commit_byte_exact_partial_alpha_non_normal_above` (also proves the commit is *not* the divergent
  above-pre-flatten fast path), `test_commit_byte_exact_driven_by_slider_signals` (press → preview →
  release ⇒ exactly one `LayerCommand`), `test_commit_is_deterministic`,
  `test_preview_approximate_then_commit_exact_transition`, plus four cache-invalidation tests
  (commit / pan-zoom / edit / frame-op) — all `np.array_equal` against `composite_stack`, no tolerance.
- **Light and dark behave identically** — covered: `test_opacity_drag_both_themes_commit_identically`
  asserts the same byte-exact invariant under each theme against a theme-agnostic reference.
- **a11y (focus/keyboard) on the slider** — covered: `test_opacity_slider_accessible_and_keyboard_reachable`
  (`accessibleName() == "Opacity"`, `TabFocus`, enabled, a `:focus` rule present in the installed theme QSS).

**Coverage is PARTIAL, stated rather than implied — two clauses are NOT covered.**
(1) **"8K document"** — the module runs at `_W = _H = 300`, not 8192². The 300² size is a deliberate choice
to cross the `OPACITY_PREVIEW_MAX_PX` threshold and exercise the LOD branch, but no opacity-drag test runs
on an 8K canvas. (2) **"holds the 16 ms `FRAME_BUDGET_MS`"** — this is **not asserted as a 16 ms bound**;
the only wall-clock assertion is `elapsed_ms < FRAME_BUDGET_MS * 60`, self-described in the test as a
*"loose gross-freeze ceiling, not 16 ms"*. The 16 ms claim rests on the bounded-working-set **mechanism**,
not on a measurement. Both residuals belong to AGT-06/AGT-10 (the RE-PROFILE ship gate T12-B-06 is the
natural home of the timing evidence); they are recorded here, **not** declared satisfied, and this
correction does not close them.

**Family sweep (AGT-01, 2026-07-30) — every test path cited in this file was resolved on disk.** Resolves:
`tests/logic/test_blend_fullframe.py` (T12-A-03), `tests/logic/test_blend_range.py` (T12-B-03),
`tests/ui/test_opacity_drag.py` (T12-B-05, as corrected above). Not on disk but **legitimately
forward-looking**, not dangling: `tests/ui/test_analytics_offthread.py` (T12-U2-02 — an OPTIONAL/LOW task
gated on orchestrator adoption; the nearest shipped module is `tests/ui/test_palette_analytics_view.py`).
`tests/ui/*` (TG-05) and `scripts/*` (invoke) are directory globs and resolve. No further dangling test stem
remains in this table.

## Slice F — requirement-artifact + docstring hygiene (C3 leftovers; DEP-5)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-F-01 | **FU-2:** reconcile Phase-1 `plan.md` §9 point 1 (`REQ-P1-LOGIC-004` grounding) to the shipped Phase-1 spec/traceability resolution — **S7 (palette nearest) + S2 (flood-fill tolerance)** (the plan currently says "S1 drawing"). Confirm all three artifacts trace `REQ-P1-LOGIC-004` to one consistent S-id set. Artifact text only; no runtime change; no `docs/**`. | AGT-01 | `specs/phase-1-core-engine/plan.md` | analyze C1 | LOGIC-007 / SC-P12-LOGIC-007-1 | todo |
| T12-F-02 | **FU-17:** give Phase-1 and Phase-4 `SC-UI-*` scenarios **phase-unique identifiers** (e.g. `SC-P1-UI-*` / `SC-P4-UI-*`, matching the `SC-P12-*` convention) across each phase's `spec.md`/`acceptance.md`/`traceability.md`, so no `SC-UI-NNN` id denotes two different scenarios across phases. Update cross-references. Artifact text only. | AGT-02 | `specs/phase-1-ui-canvas/*`, `specs/phase-4-layer-canvas/*` | analyze C1 | LOGIC-007 / SC-P12-LOGIC-007-2 | todo |
| T12-F-03 | **FU-16 label collision:** assign distinct identifiers (e.g. `FU-16a` cache-invalidation / `FU-16b` opacity-drag recomposite, per spec §2c) in the requirement artifacts so the two former "FU-16" follow-ups are never conflated. | AGT-01 | `specs/phase-12-performance-scalability/*` (+ any FU ledger reference) | analyze C1 | LOGIC-007 / SC-P12-LOGIC-007-3 | todo |
| T12-F-04 | **FU-4:** complete the residual missing docstrings in `pixelart_creator/logic/` flagged by `pydocstyle` (D101/D102/D105/D107). Enumerate the flagged modules via a `pydocstyle` pass, add PEP 257 docstrings; **doc-only, no runtime change** (Article I). | AGT-08 | `pixelart_creator/logic/*.py` (docstrings) | analyze C1 | LOGIC-006 / SC-P12-LOGIC-006-1 | todo |
| T12-F-05 | Verify Slice F: `pydocstyle` reports **zero** D101/D102/D105/D107 on the previously-flagged `logic/` modules (tests unaffected); `REQ-P1-LOGIC-004` traces to one consistent S-id across plan/spec/traceability; no `SC-UI-*` id is ambiguous across Phase-1/Phase-4; each former "FU-16" follow-up has a distinct id; `sdd-analyze` reports no cross-artifact traceability finding attributable to FU-2/-17/-16. | AGT-01 | `scripts/*` (invoke), analyze | T12-F-01..04 | LOGIC-006, -007 / SC-P12-LOGIC-006-1, -007-1/-2/-3 | todo |

## OPTIONAL / LOW — off-thread palette analytics (REQ-P12-UI-002, FU-18 residual; deferrable)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-U2-01 | **OPTIONAL / LOW — build only if the orchestrator adopts it.** Run the palette-analytics recompute **off the GUI thread** (dependency-free, Phase-7/8/10 worker precedent) so a near-worst-case many-colour 8K canvas cannot freeze the UI; result **unchanged** vs the current compute; not a frame-budget path. If deferred, FU-18 stays a documented "verified, no action" descope (spec §2b) with **no acceptance owed**. | AGT-05 | `ui/palette_analytics_view.py` | (orchestrator adopt) | UI-002 / SC-P12-UI-002-1 (if adopted) / -2 (if deferred) | todo |
| T12-U2-02 | *(if adopted)* pytest-qt test: a live analytics recompute on a near-worst-case many-colour 8K canvas does not freeze the GUI (compute off-thread; dock updates on completion); result unchanged; not gated by 16 ms. | AGT-06 | `tests/ui/test_analytics_offthread.py` | T12-U2-01 | UI-002 / SC-P12-UI-002-1 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-12 hardened touch-points (`logic/blend.py`, `logic/constants.py` +2 ceilings, `ui/layer_panel.py`/`composite_warmer`/`frame_cache`, the perf scenarios/gates) — marked PLANNED; note **no new module / no `data/` work**. | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; **zero unresolved findings before implement**. | AGT-01 | `specs/phase-12-performance-scalability/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | Confirm **no `check_layering`/`check_cycles` rule edit needed** (no new module/edge; everything edits existing `logic/`/`ui/` in place); baseline exit 0 (178/179). | AGT-01 | `scripts/*` (invoke) | plan | Article I / plan §4.4/§11 | done |
| TG-04 | Manifest: **no new runtime dependency; no GPU** (both items dependency-free); confirm no `pyproject.toml` change (PL12-D6). No new pytest marker (the perf gates are Qt-free numpy, no marker — the `--composite`/`--tilemap` precedent). | AGT-09 | `pyproject.toml` (confirm no change) | plan | PL12-D6 / spec §6 | todo |
| TG-05 | a11y verification on the opacity-slider drag interaction (focus visible, keyboard-reachable, preview does not trap focus) across both themes. | AGT-06 | `tests/ui/*` | T12-B-05 | UI-001 (Article V) | todo |
| TG-06 | CHANGELOG (`Unreleased`) entries for the Phase-12 flatten/recomposite hardening + the two new perf gates, tied to REQ-IDs, per slice. | AGT-08 | `docs/CHANGELOG.md` | Slice A/B impl+test done | Article IX | todo |
| TG-07 | `sdd-checklist` before ship: every REQ has a passing test/verify; byte-exact flatten (12 modes) + byte-exact commit recomposite + drag preview holds 16 ms + full-frame gate + viewport-scale gate all green; both themes + a11y green; FU-4 pydocstyle zero + FU-2/-17/-16 reconciled; **no batch path asserted vs 16 ms and the budget never relaxed** (Article VI). | AGT-06 | checklist report | all impl+test done | Article IV/V/VI/VIII | todo |
