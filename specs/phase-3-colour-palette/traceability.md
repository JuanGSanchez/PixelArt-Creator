# Traceability Matrix — Phase 3: Colour & Palette System (critical)

REQ-ID ↔ dossier S-id / F9 ↔ layer/owner ↔ spec section ↔ Gherkin scenario(s) ↔ test target.
**Mode:** FORWARD / pre-implementation — tests do not exist yet; the "Test target" column
names the test module + harness AGT-04 (logic) / AGT-06 (UI) will author, one test per
scenario (Article IV). Status: **planned** (scenario authored, test pending) ·
**spec-only** (gate/script-enforced, no unit test).

Test module conventions (from Phase-1/2): logic → `tests/logic/test_<module>.py` (pytest +
Hypothesis); UI → `tests/ui/test_<widget>.py` (pytest-qt, both themes, headless).

## 1. Logic layer (`REQ-P3-LOGIC-*`) — owner AGT-03 (impl) / AGT-04 (tests)

| REQ-ID | Traces (S-id / F9) | Module | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P3-LOGIC-001 | S3b, F9 | `logic/color_theory.py` | §4.1, §11 | SC-L001-1..5 | `tests/logic/test_color_theory.py` | planned |
| REQ-P3-LOGIC-002 | S3b, **F9** | `logic/color_theory.py` | §4.1, §11 | SC-L002-1..6 (SC-L002-1..4 angle-correctness) | `tests/logic/test_color_theory.py` | planned |
| REQ-P3-LOGIC-003 | S3b, F9 | `logic/color_theory.py` | §4.1, §11 | SC-L003-1..4 | `tests/logic/test_color_theory.py` | planned |
| REQ-P3-LOGIC-004 | S3b; **inherits `distance_sq`→perceptual**; F9 | `logic/perceptual.py` | §1, §4.1, §11 | SC-L004-1..4 (SC-L004-1 known-value, acceptance-critical) | `tests/logic/test_perceptual.py` | planned |
| REQ-P3-LOGIC-005 | S3b; **realises `distance_sq`→perceptual** | `logic/perceptual.py` (+ `logic/palette.py`) | §1, §4.1, §11 | SC-L005-1..4 | `tests/logic/test_perceptual.py` | planned |
| REQ-P3-LOGIC-006 | S3b, F9 | `logic/dither.py` | §4.1, §11 | SC-L006-1..3 (SC-L006-1 palette-containment) | `tests/logic/test_dither.py` | planned |
| REQ-P3-LOGIC-007 | S3b, F9 | `logic/dither.py` | §4.1, §11 | SC-L007-1..3 (SC-L007-1 palette-containment) | `tests/logic/test_dither.py` | planned |
| REQ-P3-LOGIC-008 | S6, **F9** | `logic/hardware_palette.py` | §4.1, §11 | SC-L008-1..3 | `tests/logic/test_hardware_palette.py` | planned |
| REQ-P3-LOGIC-009 | S6, **F9** | `logic/quantize.py` | §4.1, §11 | SC-L009-1..4 (SC-L009-1/-2 ⊆-subset, acceptance-critical) | `tests/logic/test_quantize.py` | planned |
| REQ-P3-LOGIC-010 | S6, **F9** | `logic/quantize.py` | §4.1, §11 | SC-L010-1..4 (SC-L010-1 ≤N, acceptance-critical) | `tests/logic/test_quantize.py` | planned |
| REQ-P3-LOGIC-011 | S6, **F9** | `logic/quantize.py` | §4.1, §11 | SC-L011-1..3 (SC-L011-1 ≤N, acceptance-critical) | `tests/logic/test_quantize.py` | planned |
| REQ-P3-LOGIC-012 | S6 | `logic/palette_analytics.py` | §4.1, §11 | SC-L012-1..4 | `tests/logic/test_palette_analytics.py` | planned |
| REQ-P3-LOGIC-013 | S6 | `logic/palette_ops.py` | §4.1, §11 | SC-L013-1..4 (SC-L013-2 round-trip) | `tests/logic/test_palette_ops.py` | planned |
| REQ-P3-LOGIC-014 | S6 | `logic/palette_ops.py` | §4.1, §11 | SC-L014-1..4 (SC-L014-2 reversibility) | `tests/logic/test_palette_ops.py` | planned |
| REQ-P3-LOGIC-015 | S3a, S4 | `logic/favourites.py` | §4.1, §11 | SC-L015-1..4 (SC-L015-3 serialise round-trip) | `tests/logic/test_favourites.py` | planned |
| REQ-P3-LOGIC-016 | S6 | `logic/palette_io.py` | §4.1, §11 | SC-L016-1..3 (SC-L016-2 defensive parse) | `tests/logic/test_palette_io.py` | planned |
| REQ-P3-LOGIC-017 (NFR) | S7 (C1/F1) | all Phase-3 logic + `ui/commands.py` | §4.1, §5, §11 | SC-L017-1 (per-op reversibility) ; SC-L017-2 (spec-only) | `tests/logic/test_*` reversibility asserts + `check_layering` | planned / spec-only |

## 2. UI layer (`REQ-P3-UI-*`) — owner AGT-05 (impl) / AGT-06 (tests, both themes)

| REQ-ID | Traces (S-id / F9) | Module (indicative) | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P3-UI-001 | S6 | `ui/palette_editor_panel.py` | §4.2, §11 | SC-U001-1..3 (SC-U001-2 reversibility) | `tests/ui/test_palette_editor_panel.py` | planned |
| REQ-P3-UI-002 | S6 | `ui/palette_editor_panel.py` (import/export actions) | §4.2, §11 | SC-U002-1..3 | `tests/ui/test_palette_io_ui.py` | planned |
| REQ-P3-UI-003 | **S3** | `ui/colour_hub_menu.py` (+ `ui/canvas_view.py` seam) | §4.2, §11 | SC-U003-1..3 | `tests/ui/test_colour_hub.py` | planned |
| REQ-P3-UI-004 | **S3a, S4** | `ui/colour_hub_menu.py` (Favourites) | §4.2, §11 | SC-U004-1..4 (SC-U004-3 persistence, acceptance-critical) | `tests/ui/test_colour_hub_favourites.py` | planned |
| REQ-P3-UI-005 | **S3b, F9** | `ui/colour_wheel_widget.py` | §4.2, §11 | SC-U005-1..5 (SC-U005-2 live-harmony, acceptance-critical) | `tests/ui/test_colour_wheel.py` | planned |
| REQ-P3-UI-006 | **S4** | `ui/colour_hub_menu.py` + active-swatch | §4.2, §11 | SC-U006-1..4 (SC-U006-1 active-swatch, acceptance-critical) | `tests/ui/test_colour_hub_apply.py` | planned |
| REQ-P3-UI-007 | S3b | `ui/shade_ramp_picker.py` | §4.2, §11 | SC-U007-1..3 | `tests/ui/test_shade_ramp_picker.py` | planned |
| REQ-P3-UI-008 | S3b | `ui/tools/dither_tool.py` | §4.2, §11 | SC-U008-1..3 (SC-U008-1/-2 reversibility) | `tests/ui/test_dither_tool.py` | planned |
| REQ-P3-UI-009 | S6 | `ui/palette_constraint_panel.py` | §4.2, §11 | SC-U009-1..3 (SC-U009-1/-2 reversibility) | `tests/ui/test_palette_constraint.py` | planned |
| REQ-P3-UI-010 | S6 | `ui/extract_palette_dialog.py` | §4.2, §11 | SC-U010-1..3 | `tests/ui/test_extract_palette_dialog.py` | planned |
| REQ-P3-UI-011 | S6 | `ui/palette_analytics_view.py` | §4.2, §11 | SC-U011-1..3 | `tests/ui/test_palette_analytics_view.py` | planned |
| REQ-P3-UI-012 | S6 | `ui/colour_cycling_panel.py` | §4.2, §11 | SC-U012-1..3 | `tests/ui/test_colour_cycling.py` | planned |
| REQ-P3-UI-013 | S6 | `ui/palette_swap_dialog.py` | §4.2, §11 | SC-U013-1..3 (SC-U013-2 reversibility) | `tests/ui/test_palette_swap.py` | planned |
| REQ-P3-UI-014 | S6 | `ui/main_window.py` (indexed-mode controls) | §4.2, §11 | SC-U014-1..3 | `tests/ui/test_indexed_mode.py` | planned |

*Module names are indicative for `sdd-plan`/AGT-01 placement; final paths are AGT-01's call.
The colour hub (REQ-P3-UI-003..006) is authored via the AGT-05 `colour-hub` skill; the harmony
maths it binds to are AGT-03 logic (REQ-P3-LOGIC-001/-002/-003), grounded by F9.*

## 3. Coverage summary (planned)

- **31 REQ-IDs**: 17 LOGIC + 14 UI. Every functional REQ has ≥1 Gherkin scenario.
- **110 scenarios** authored (64 logic SC-L001..017 + 46 UI SC-U001..014); each maps to
  exactly one pending test (Article IV: one test per acceptance criterion).
- **R2 / acceptance-critical scenarios:**
  - **Harmony-angle correctness:** SC-L002-1..4 (complementary +180 / analogous ±30 / triadic
    ±120 / split-complementary ±150).
  - **CIEDE2000 known-value:** SC-L004-1 (Sharma et al. reference pairs within tolerance).
  - **≤N quantization:** SC-L010-1 (median-cut), SC-L011-1 (k-means).
  - **⊆ hardware palette (constraint):** SC-L009-1 (NES), SC-L009-2 (GB).
  - **Palette containment (dither):** SC-L006-1, SC-L007-1.
  - **Wheel pick → active swatch:** SC-U006-1 (and SC-U006-2 for favourites).
  - **Favourites persistence:** SC-U004-3 (present after restart).
  - **Live-harmony update on wheel move:** SC-U005-2 (+ SC-U005-3 angle reflection).
- **Reversibility acceptance** (NFR-3): SC-L014-2, SC-L017-1, SC-U001-2, SC-U008-1/-2,
  SC-U009-1/-2, SC-U013-2 (+ the round-trip SC-L013-2).
- **Inherited forward traces:** `distance_sq`→perceptual — REQ-P3-LOGIC-004 (ΔE00) +
  REQ-P3-LOGIC-005 (opt-in perceptual `nearest_index`); `color.blend_over` deliberately
  **not** traced by any Phase-3 REQ (reserved for Phase 4, §6/CL-16).
- **Spec-only** (gate-enforced, no unit test): SC-L017-2 (Qt-free purity via
  `check_layering`/`check_cycles`, Article I); NFR-6 constants via review (Article II).

## 4. Notes for sdd-analyze (AGT-01)

- **Every REQ traces to an S-id / F9** (S3/S3a/S3b/S4 for the marquee hub; S6 for the palette
  workflows; S7 for reversibility) — no untraced REQ (Article X satisfied). The
  harmony/wheel/CIEDE2000/quantization/constraint REQs additionally depend on **F9
  (`docs/research-phase3-colour.md`, in progress)** — this must land before `sdd-plan`
  finalises those algorithm internals; the *acceptance* (angles, ΔE00 known values, ≤N, ⊆
  hardware palette) is fixed here.
- **New constants** (§9 of spec): `HARMONY_COMPLEMENTARY_DEG=180`, `HARMONY_ANALOGOUS_DEG=30`,
  `HARMONY_TRIADIC_DEG=120`, `HARMONY_SPLIT_COMPLEMENTARY_DEG=150`, `BAYER_MATRIX_SIZE=4`,
  `CIEDE2000_KL/KC/KH=1.0`, plus candidates `RAMP_STEP_COUNT`, `PALETTE_EXTRACT_DEFAULT_N`,
  `KMEANS_SEED`, `CYCLE_DEFAULT_FPS`, `FAVOURITES_MAX` — all → `logic/constants.py` (Article
  II). **AGT-01 to rule** on the **NES / Game Boy palette reference-data placement**
  (module-local table in `hardware_palette.py` vs `constants.py` — reference *data*, not a
  tuning scalar; analogous to the Phase-2 `SymmetryAxis` enum call) and to confirm the
  candidate values.
- **New domain exceptions** `ColorTheoryError`, `QuantizeError`, `DitherError`,
  `FavouritesError` subclass `ValueError` (Phase-1 convention: `ColorError`, `PaletteError`,
  `PixelBufferError`, `DocumentError`); reuse `PaletteError` for palette-index-bound ops
  (cycling range, swap remap).
- **Slicing** (§8): **3A logic → 3B colour hub (marquee S3/S4) → 3C palette workflows**. Within
  3A, harmony (-002), wheel-geometry (-001), CIEDE2000 (-004), constraint (-009), extraction
  (-010/-011) are **F9-gated**; ramps, dither, analytics, cycling, swap, favourites,
  import/export are **un-gated** and can proceed in parallel.
- **Dependencies** (§7): Phase-1 `color`, `palette`, `pixel_buffer`, `document`, `history`,
  `data/project_io` (shipped) + the Phase-1 UI **right-click seam**, palette panel,
  `ui/commands.py`, `ui/i18n.py` (in-progress increment). AGT-01 to confirm the Phase-1 UI
  substrate (esp. the right-click seam that 3B binds to) is stable before 3B starts.
