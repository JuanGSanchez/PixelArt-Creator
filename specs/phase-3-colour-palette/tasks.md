# Tasks — Phase 3: Colour & Palette System (critical)

| Field | Value |
| --- | --- |
| Feature | `phase-3-colour-palette` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| Derived from | `specs/phase-3-colour-palette/plan.md` §3–§10 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VII, VIII, X) |
| Scope | Full Phase-3 build, sliced **3A LOGIC → 3B COLOUR HUB (marquee) → 3C PALETTE WORKFLOWS**. Every REQ-P3-* maps to ≥1 task. |

Status legend: `todo` · `doing` · `done`.
Each task: **id · owner · target file(s) · predecessor · REQ/acceptance link · status.**

The C1 gate (`sdd-analyze`) is run over constitution/spec/plan/tasks as the pre-implement gate
(see analyze report). Article VIII: no implement dispatch past a red gate; layering/cycles must
exit 0 at each slice boundary.

---

## Slice 3A — Colour & palette LOGIC (`REQ-P3-LOGIC-001..017`) — Qt-free

### T1 — New constants → `logic/constants.py`
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/constants.py` · **Predecessor:** — (root)
- **Do:** Add, each with a source-citation comment (keep leaf, no intra-package imports):
  `HARMONY_COMPLEMENTARY_DEG = 180`, `HARMONY_ANALOGOUS_DEG = 30`, `HARMONY_TRIADIC_DEG = 120`,
  `HARMONY_SPLIT_COMPLEMENTARY_DEG = 150`, `RAMP_STEP_COUNT = 5`, `BAYER_MATRIX_SIZE = 4`,
  `PALETTE_EXTRACT_DEFAULT_N = 16`, `CIEDE2000_KL = 1.0`, `CIEDE2000_KC = 1.0`, `CIEDE2000_KH = 1.0`,
  `KMEANS_SEED = 0`, `CYCLE_DEFAULT_FPS = 10`, `FAVOURITES_MAX = 64`. The ΔE00 formula magic
  numbers, sRGB/Lab constants, Bayer matrix values, and FS coefficients are **intrinsic → local**
  to their module (plan §5, ADR-0001); the NES/GB palette tables are **module-local data** in
  `hardware_palette.py` (T5, ADR-0003) — none go here.
- **REQ/acceptance:** NFR-6 / Article II; SC-L002-* (angles), SC-L004-4 (weights), SC-L006-2
  (Bayer size), SC-L010-2 (default N).
- **Status:** todo

### T2 — `logic/color_theory.py` (HSV/HSL conversion + harmonies + ramps)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/color_theory.py` · **Predecessor:** T1
- **Do:** Implement `ColorTheoryError(ValueError)`; `rgba_to_hsv`/`hsv_to_rgba`/`rgba_to_hsl`/
  `hsl_to_rgba` (alpha preserved; RGB→HSV→RGB identity for representable colours, CL-1); harmony
  functions `complementary`/`analogous`/`triadic`/`split_complementary`/`harmony` reading the
  `HARMONY_*_DEG` constants (S/V preserved, hue mod 360, alpha preserved); `shade_ramp`/`tint_ramp`/
  `tone_ramp` (`RAMP_STEP_COUNT` steps, include base, monotonic, deterministic). Tint/shade/tone
  HSV formulas per plan §5 (intrinsic-local). Zero Qt (CL-2); typed; docstrings.
- **REQ/acceptance:** REQ-P3-LOGIC-001 (SC-L001-1..5), -002 (SC-L002-1..6; angle-correctness
  SC-L002-1..4), -003 (SC-L003-1..4).
- **Status:** todo

### T3 — `logic/perceptual.py` (sRGB→Lab + CIEDE2000 + perceptual nearest)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/perceptual.py` · **Predecessor:** T1
- **Do:** Implement `rgba_to_lab` (sRGB→XYZ D65→Lab; standard constants **local**, ADR-0001);
  `delta_e_2000(a, b, *, kl, kc, kh)` reading `CIEDE2000_KL/KC/KH` (symmetric; Δ(x,x)=0);
  `nearest_index_perceptual(palette, color)` (ranks by ΔE00; ties → lower index; empty palette →
  `PaletteError`). **PL-D6:** free function taking a `Palette`, NOT a `palette.py` method (no
  cycle). `distance_sq`/`palette.nearest_index` remain the retained fast default (CL-10). Zero Qt.
- **REQ/acceptance:** REQ-P3-LOGIC-004 (SC-L004-1..4; SC-L004-1 Sharma known-value, acceptance-critical),
  -005 (SC-L005-1..4).
- **Status:** todo

### T4 — `logic/dither.py` (ordered/Bayer + Floyd–Steinberg + reversible builder)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/dither.py` · **Predecessor:** T1
- **Do:** Implement `DitherError(ValueError)`; `ordered_dither(source, palette, *, matrix_size=
  BAYER_MATRIX_SIZE)` (Bayer map via recurrence, values intrinsic-local) and `floyd_steinberg(
  source, palette)` (7/3/5/1 ÷16, coefficients intrinsic-local) — **output colour set ⊆ palette**
  (mapping, not blend); deterministic; and `make_dither_command(...)` (`PixelEdit`, reversible;
  mode 'ordered'|'floyd_steinberg'; empty palette → `PaletteError`; bad mode → `DitherError`). Zero Qt.
- **REQ/acceptance:** REQ-P3-LOGIC-006 (SC-L006-1..3; SC-L006-1 containment), -007 (SC-L007-1..3;
  SC-L007-1 subset). Reversibility folds into REQ-P3-LOGIC-017 (T10).
- **Status:** todo

### T5 — `logic/hardware_palette.py` (NES + Game Boy reference data)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/hardware_palette.py` · **Predecessor:** T1
- **Do:** Module-local immutable reference tuples (ADR-0003): `_GAME_BOY_COLORS` = DMG LUT
  `#9BBC0F/#8BAC0F/#306230/#0F380F`; `_NES_COLORS` = the 64-entry `2C02G_wiki.pal` decode (cite
  NESdev). `nes_palette()` / `game_boy_palette()` each return a **new independent `Palette` copy**
  (SC-L008-3, never mutate the reference). Zero Qt. Data placement per ADR-0003.
- **REQ/acceptance:** REQ-P3-LOGIC-008 (SC-L008-1..3).
- **Status:** todo

### T6 — `logic/quantize.py` (constraint + median-cut + k-means + reversible builder)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/quantize.py` · **Predecessor:** T1, T3, T5
- **Do:** Implement `QuantizeError(ValueError)`; `constrain_to_palette(source, palette, *, metric=
  'distance_sq')` (`'ciede2000'` opt-in delegates to `perceptual`; **output ⊆ palette**, acceptance-
  critical; empty palette → `PaletteError`; bad metric → `QuantizeError`); `median_cut(source,
  n=PALETTE_EXTRACT_DEFAULT_N)` (**≤n**, deterministic; n≤0 → `QuantizeError`); `kmeans(source, n,
  *, seed=KMEANS_SEED)` (**≤n**, seeded k-means++ reproducible, CL-8); `make_constraint_command(...)`
  (`PixelEdit`, reversible). Grounded by research T3/T4. Zero Qt.
- **REQ/acceptance:** REQ-P3-LOGIC-009 (SC-L009-1..4; SC-L009-1/-2 ⊆-subset acceptance-critical),
  -010 (SC-L010-1..4; ≤N acceptance-critical), -011 (SC-L011-1..3; ≤N acceptance-critical).
- **Status:** todo

### T7 — `logic/palette_analytics.py` (usage counts, vectorised)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/palette_analytics.py` · **Predecessor:** T1
- **Do:** `color_usage_counts(buffer)` (per-colour counts, sum = total pixels, ordered by
  (-count, colour)); `index_usage_counts(buffer, palette)` (per-index; unused → 0; ordered by
  (-count, index)); `document_usage_counts(document, palette=None)` (aggregate across frames/layers).
  Read-only, no mutation; deterministic; **vectorised** over 33 M pixels (NumPy, F7 — no per-pixel
  Python loop). Zero Qt.
- **REQ/acceptance:** REQ-P3-LOGIC-012 (SC-L012-1..4).
- **Status:** todo

### T8 — `logic/palette_ops.py` (colour cycling + palette swap + reversible builders)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/palette_ops.py` · **Predecessor:** T1
- **Do:** `cycle_palette(palette, start, end, step)` (rotate `[start,end]`; cycling by len(range) =
  identity, SC-L013-2; bad range → `PaletteError`); `swap_indices(buffer, mapping)` (index→index;
  out-of-range → `PaletteError`) + `remap_colors(buffer, mapping)` (RGBA→RGBA, CL-14);
  `make_cycle_command(...)` (commit preview) and `make_swap_command(...)` (`PixelEdit`; inverse
  mapping restores exactly, SC-L014-2). Deterministic; zero Qt.
- **REQ/acceptance:** REQ-P3-LOGIC-013 (SC-L013-1..4; SC-L013-2 round-trip), -014 (SC-L014-1..4;
  SC-L014-2 reversibility).
- **Status:** todo

### T9 — `logic/favourites.py` + `data/favourites_io.py` (model + persistence)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/favourites.py`,
  `pixelart_creator/data/favourites_io.py` · **Predecessor:** T1
- **Do:** `logic/favourites.py`: `FavouritesError(ValueError)`; `Favourites` (ordered, de-duplicated;
  `add` no-op-if-present + `FavouritesError` past `FAVOURITES_MAX`; `remove`/`move`; `colors`;
  dunders; `to_serializable`→list of `#RRGGBBAA`, `from_serializable`). `data/favourites_io.py`
  (ADR-0004): `FavouritesIOError(ValueError)`; `save_favourites(path, favourites)` /
  `load_favourites(path)` — JSON via `pathlib` (portable, Article VII, `path_portability_check`);
  missing file → empty `Favourites`; malformed → `FavouritesIOError`. Both **zero Qt** (path is
  supplied by the UI, not resolved here).
- **REQ/acceptance:** REQ-P3-LOGIC-015 (SC-L015-1..4; SC-L015-3 serialise round-trip). Persistence
  substrate for REQ-P3-UI-004 (SC-U004-3).
- **Status:** todo

### T10 — `logic/palette_io.py` (import/export encode/decode)
- **Owner:** AGT-03 · **Target:** `pixelart_creator/logic/palette_io.py` · **Predecessor:** T1
- **Do:** `PaletteIOError(ValueError)`; `encode(palette, fmt)` / `decode(text, fmt)` for
  `'gpl'`/`'pal'`/`'hex'` — pure text transforms reusing `color.to_hex`/`from_hex`; **defensive
  parse (no `eval`/`exec`, Article VII)**; malformed → `PaletteIOError`; encode∘decode round-trips
  (SC-L016-1). Disk read/write is the thin UI action (T15), not here. Zero Qt; deterministic.
- **REQ/acceptance:** REQ-P3-LOGIC-016 (SC-L016-1..3; SC-L016-2 defensive parse).
- **Status:** todo

### T11 — Reversible-op integration audit (all 3A mutating ops → `history.Command`)
- **Owner:** AGT-03 · **Target:** `logic/dither.py`, `quantize.py`, `palette_ops.py` (+ editor palette
  edits) · **Predecessor:** T4, T6, T8
- **Do:** Confirm every Phase-3 mutating op returns a `history.Command` (`PixelEdit` for buffer
  diffs; `FunctionCommand` for palette-object edits, plan §10) with `apply ∘ undo = identity`, and
  imports **zero Qt**. Cross-cutting closure of REQ-P3-LOGIC-017 (no new module).
- **REQ/acceptance:** REQ-P3-LOGIC-017 (SC-L017-1); SC-L017-2 (Qt-free, gate-verified at T14).
- **Status:** todo

### T12 — Logic tests (pytest + Hypothesis) for all 3A modules
- **Owner:** AGT-04 · **Target:** `tests/logic/test_color_theory.py`, `test_perceptual.py`,
  `test_dither.py`, `test_hardware_palette.py`, `test_quantize.py`, `test_palette_analytics.py`,
  `test_palette_ops.py`, `test_favourites.py`, `test_palette_io.py`, `tests/data/test_favourites_io.py`
  · **Predecessor:** T2, T3, T4, T5, T6, T7, T8, T9, T10, T11
- **Do:** One test per SC-L001..017 scenario. **Hypothesis** invariants: RGB↔HSV round-trip
  identity; harmony angle-correctness + hue-wrap; ramp monotonicity/determinism; ΔE00 symmetry &
  self-zero; dither & constraint **output ⊆ palette**; extraction **≤N**; swap **reversibility**
  (`apply∘undo = identity`); cycle round-trip (len(range) = identity); favourites de-dup + serialise
  round-trip; palette_io encode∘decode round-trip + defensive-parse rejection. **CIEDE2000
  validation (plan §7, acceptance-critical):** embed the Sharma et al. supplementary test-data pairs
  as a fixture and assert `delta_e_2000` within tolerance `1e-4` (guards the hue-mean quadrant / G
  term). Coverage gate ≥90 % line / ≥80 % branch; **invoke `python scripts/coverage_gate.py`**
  (P11). Deterministic/portable, headless.
- **REQ/acceptance:** Article IV (one test per criterion); NFR-2/-3/-4/-5/-6; SC-L004-1 Sharma dataset.
- **Status:** todo

### T13 — *(reserved — no separate task; analytics perf folds into T7/T-perf)*
- **Note:** Analytics vectorisation is a T7 acceptance (F7); any over-budget path is handled by
  T-perf (conditional). No standalone task.

### T14 — Slice-3A layering/cycle gate (AGT-01)
- **Owner:** AGT-01 · **Target:** `pixelart_creator/` · **Predecessor:** T12
- **Do:** **Invoke `python scripts/check_layering.py` and `python scripts/check_cycles.py`** — both
  must exit 0 (Article I; Decision A1-D3): the nine new `logic/` modules + `data/favourites_io.py`
  import zero Qt and add no cycle (esp. the `perceptual→palette` / `quantize→perceptual` one-way
  edges; PL-D6 keeps `palette.py` free of `perceptual`). Script exit 2 → BLOCKED (A1-E3). Confirms
  SC-L017-2.
- **REQ/acceptance:** Article I; REQ-P3-LOGIC-017 (SC-L017-2).
- **Status:** todo

## Slice 3B — Colour hub UI, marquee S3/S4 (`REQ-P3-UI-003..006`) — depends on 3A + stable Phase-1 UI

### T15 — Colour wheel widget (RGB wheel + live harmonies)
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/colour_wheel_widget.py` · **Predecessor:** T2
  (color_theory) + stable Phase-1 UI
- **Do:** Canva-style wheel via `QConicalGradient` (hue) + `QRadialGradient` white→transparent
  (saturation) + a value slider (research T1); dragging/clicking picks hue+sat; **live harmony
  swatches** (complementary/analogous/triadic/split-comp + shade/tint ramps) recomputed from
  `logic/color_theory.py` on **every** wheel move (SC-U005-2, acceptance-critical) with correct
  angles (SC-U005-3). Harmony **maths stay in logic**; the widget only renders+binds (uses `QColor`
  HSV only in `ui/`, CL-2). `tr()`-wrapped, `changeEvent` retranslate, keyboard-reachable, legible
  in both themes.
- **REQ/acceptance:** REQ-P3-UI-005 (SC-U005-1..5).
- **Status:** todo

### T16 — Colour hub menu (right-click seam + Favourites + apply/active-swatch)
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/colour_hub_menu.py`,
  `pixelart_creator/ui/main_window.py` (wire seam + active swatch) · **Predecessor:** T9, T15
- **Do:** Cursor-anchored contextual menu opened via the Phase-1 `Canvas_View.set_menu_hook` /
  `rightClicked(x,y)` seam (SC-U003-1); hosts both pick paths — Favourites list (backed by
  `logic/favourites.py`; add-current / remove / reorder; persisted via `data/favourites_io.py`,
  path from `QStandardPaths.AppConfigLocation`, ADR-0004) and the T15 wheel. A pick **applies
  immediately to the active swatch** (SC-U006-1, acceptance-critical); add-to-favourites is an
  **explicit** action (CL-5). **Persistence acceptance-critical: a saved favourite is present after
  restart** (SC-U004-3). `tr()`-wrapped, keyboard-openable+navigable, both themes.
- **REQ/acceptance:** REQ-P3-UI-003 (SC-U003-1..3), -004 (SC-U004-1..4; SC-U004-3 persistence),
  -006 (SC-U006-1..4; SC-U006-1 active-swatch).
- **Status:** todo

### T17 — `ui/commands.py` wrappers for 3B (favourites-independent picks are non-mutating)
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/commands.py` · **Predecessor:** T16
- **Do:** No pixel mutation occurs from a hub pick (it sets the active colour), so no `QUndoCommand`
  is needed for picking; this task confirms the hub does **not** wrongly create undo entries and
  reserves the wrapper pattern for 3C mutating ops (T21). (Favourites edits persist to disk, not to
  the undo stack.)
- **REQ/acceptance:** REQ-P3-UI-006 (no spurious undo entry on pick).
- **Status:** todo

### T18 — Colour-hub UI tests (pytest-qt, both themes, a11y, headless)
- **Owner:** AGT-06 · **Target:** `tests/ui/test_colour_wheel.py`, `test_colour_hub.py`,
  `test_colour_hub_favourites.py`, `test_colour_hub_apply.py` · **Predecessor:** T15, T16, T17
- **Do:** One pytest-qt test per SC-U003..006 scenario; qtbot; wait on signals; **both themes**;
  a11y (accessible name, keyboard reachability, focus visibility); headless. Assert **live-harmony
  update on every wheel move** (SC-U005-2), **pick → active swatch** (SC-U006-1), and **Favourites
  survive a simulated restart** (SC-U004-3, via `data/favourites_io` round-trip). Coverage ≥90/80.
- **REQ/acceptance:** Article IV + V; SC-U003..006.
- **Status:** todo

### T19 — i18n for 3B strings
- **Owner:** AGT-07 · **Target:** `ui/` `.ts` catalogues (+ `string_audit_check`) · **Predecessor:** T15, T16
- **Do:** Run `string_audit_check` (report unwrapped → AGT-05 fixes); extract with
  `pyside6-lupdate`; compile `.qm`; confirm `changeEvent` retranslate on the hub + wheel (F5/F6).
- **REQ/acceptance:** Article V §2; NFR-8.
- **Status:** todo

### T-perf-B — Wheel/gradient render-perf directive (CONDITIONAL)
- **Owner:** AGT-10 · **Target:** perf directive → AGT-05 (`ui/colour_wheel_widget.py`)
  · **Predecessor:** T15
- **Do:** Run `perf_profile` on the live-harmony wheel repaint at 8K context. Only if over
  `FRAME_BUDGET_MS = 16`: issue a directive (e.g. cache the gradient pixmap, repaint only the
  selection marker) AGT-05 implements — budget never relaxed (Article VI). If in-budget, closes
  as no-op. Decision A1: conditional on an over-budget path (plan §10).
- **REQ/acceptance:** Article VI; NFR-9.
- **Status:** todo (conditional)

## Slice 3C — Palette workflows UI (`REQ-P3-UI-001, -002, -007..-014`) — depends on 3A

### T20 — Palette editor panel + import/export UI
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/palette_editor_panel.py` · **Predecessor:**
  T10 (palette_io) + stable Phase-1 palette panel
- **Do:** Extend the palette panel: add / remove / **drag-drop reorder** (binds `palette.move`),
  each mutation one `QUndoCommand`; `tr()`-wrapped **import/export** actions with file dialogs wired
  to `logic/palette_io.py` (thin disk read/write here, keeping logic Qt-free); malformed import →
  user-facing error, no crash (SC-U002-2). Keyboard-reachable, both themes; no domain logic in the
  widget.
- **REQ/acceptance:** REQ-P3-UI-001 (SC-U001-1..3; SC-U001-2 reversibility), -002 (SC-U002-1..3).
- **Status:** todo

### T21 — Palette workflow panels/dialogs/tools (ramp / dither / constraint / extract / analytics / cycling / swap)
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/shade_ramp_picker.py`,
  `ui/tools/dither_tool.py`, `ui/palette_constraint_panel.py`, `ui/extract_palette_dialog.py`,
  `ui/palette_analytics_view.py`, `ui/colour_cycling_panel.py`, `ui/palette_swap_dialog.py`,
  `ui/commands.py` (extend) · **Predecessor:** T4, T5, T6, T7, T8, T20
- **Do:** Build each control binding to its 3A logic: shade-ramp picker (`color_theory` ramps →
  apply/add); dither brushes (`dither`, stroke = one command); NES/GB constraint presets
  (`hardware_palette`+`quantize`, one command); extract dialog (N default `PALETTE_EXTRACT_DEFAULT_N`
  + median-cut/k-means choice → ≤N palette into editor); analytics view (`palette_analytics`,
  read-only, sortable); cycling controls (`palette_ops` cycle at `CYCLE_DEFAULT_FPS`, non-destructive
  preview); swap dialog (`palette_ops` swap, one command). Each mutating op wraps a `history.Command`
  as **one** `QUndoCommand` via `ui/commands.py` (no domain math in the bridge). All `tr()`-wrapped,
  `changeEvent` retranslate, keyboard-reachable, both themes.
- **REQ/acceptance:** REQ-P3-UI-007 (SC-U007), -008 (SC-U008; reversibility), -009 (SC-U009;
  reversibility), -010 (SC-U010), -011 (SC-U011), -012 (SC-U012), -013 (SC-U013; reversibility).
- **Status:** todo

### T22 — Indexed-mode workflow controls
- **Owner:** AGT-05 · **Target:** `pixelart_creator/ui/main_window.py` (indexed-mode switch +
  paint-by-index), `ui/commands.py` · **Predecessor:** T20, T21
- **Do:** RGBA↔indexed mode switch (default RGBA, CL-15; undoable) + paint-by-palette-index using
  the active palette (undoable). `tr()`-wrapped, keyboard-reachable, both themes.
- **REQ/acceptance:** REQ-P3-UI-014 (SC-U014-1..3).
- **Status:** todo

### T23 — Palette-workflow UI tests (pytest-qt, both themes, a11y, headless)
- **Owner:** AGT-06 · **Target:** `tests/ui/test_palette_editor_panel.py`, `test_palette_io_ui.py`,
  `test_shade_ramp_picker.py`, `test_dither_tool.py`, `test_palette_constraint.py`,
  `test_extract_palette_dialog.py`, `test_palette_analytics_view.py`, `test_colour_cycling.py`,
  `test_palette_swap.py`, `test_indexed_mode.py` · **Predecessor:** T20, T21, T22
- **Do:** One pytest-qt test per SC-U001..002, U007..014 scenario; qtbot; wait on signals; **both
  themes**; a11y; headless. Assert reversibility (SC-U001-2, U008-1/-2, U009-1, U013-2), ⊆-behaviour
  (constraint), ≤N (extract), malformed-import error (SC-U002-2). Coverage ≥90/80.
- **REQ/acceptance:** Article IV + V; SC-U001..002, U007..014.
- **Status:** todo

### T24 — i18n for 3C strings
- **Owner:** AGT-07 · **Target:** `ui/` `.ts` catalogues (+ `string_audit_check`) · **Predecessor:** T20, T21, T22
- **Do:** `string_audit_check` (report → AGT-05 fixes); `pyside6-lupdate` extract; compile `.qm`;
  confirm `changeEvent` retranslate on all new 3C widgets (F5/F6).
- **REQ/acceptance:** Article V §2; NFR-8.
- **Status:** todo

### T-perf-C — Dither/analytics render-perf directive (CONDITIONAL)
- **Owner:** AGT-10 · **Target:** perf directive → AGT-05 (`ui/tools/dither_tool.py`,
  `ui/palette_analytics_view.py`) · **Predecessor:** T21
- **Do:** Run `perf_profile` on the dither preview + analytics-over-8K paths. Only if over
  `FRAME_BUDGET_MS = 16`: issue a directive AGT-05 implements — budget never relaxed (Article VI).
  Analytics must already be vectorised (T7, F7). In-budget → no-op.
- **REQ/acceptance:** Article VI; NFR-9.
- **Status:** todo (conditional)

### T25 — Docs (usage + CHANGELOG + mkdocs + ADRs)
- **Owner:** AGT-08 · **Target:** `docs/` (usage pages, `CHANGELOG.md` Unreleased) · **Predecessor:** T18, T23
- **Do:** Document the colour hub + palette toolset; add CHANGELOG Added entries keyed to REQ-P3-*;
  refresh mkdocs API pages from docstrings; run pydocstyle gate. **ADR-0003** (hardware-palette data
  placement) + **ADR-0004** (Favourites persistence) are filed under `docs/adr/` by AGT-01 (this
  session, §hand-off).
- **REQ/acceptance:** Article III §4 (docstrings); durable-docs coverage.
- **Status:** todo

### T26 — Commit(s), REQ-tagged, gate-green
- **Owner:** AGT-09 · **Target:** git (Conventional Commits) · **Predecessor:** T18, T19, T23, T24, T25
- **Do:** Commit 3A + 3B + 3C in gate-green increments (`feat(logic): …` / `feat(data): …` /
  `feat(ui): …`) carrying the governing REQ-P3-* ids; each leaves quality + tests + coverage +
  layering + SDD gates green (Article IX). Human checkpoint before any push/tag.
- **REQ/acceptance:** Article IX.
- **Status:** todo

---

## Dependency graph

```
Slice 3A (Qt-free logic):
  T1 ─┬─> T2 ─────────────┐
      ├─> T3 ──> T6 ──┐   │
      ├─> T4 ─────────┤   │
      ├─> T5 ──> T6   ├─> T11 ─> T12 ─> T14
      ├─> T7 ─────────┤   │
      ├─> T8 ─────────┤   │
      ├─> T9 ─────────┘   │
      └─> T10 ────────────┘
   (T4,T6,T8 -> T11 reversibility audit; T12 needs all of T2..T11)

Slice 3B (after T14 + stable Phase-1 UI seam):
  T2 ─> T15 ─┐
  T9 ────────┼─> T16 ─> T17 ─> T18 ─┐
             │                       ├─> T25 ─> T26
             └─> T-perf-B (cond.)    │
                 T19 ────────────────┘

Slice 3C (after T14):
  {T4,T5,T6,T7,T8} + T10 ─> T20 ─> T21 ─> T22 ─> T23 ─┐
                                    │                  ├─> T25 ─> T26
                                    └─> T-perf-C (cond.)│
                                        T24 ────────────┘
```

Parallelisable after T1: {T2, T3, T4, T5, T7, T8, T9, T10} (T6 needs T3+T5). Slice 3B begins only
after T14 (3A gate green) **and** a stable Phase-1 UI substrate (the confirmed
`Canvas_View.set_menu_hook`/`rightClicked` seam + palette panel + `ui/commands.py` + `ui/i18n.py`).
Slice 3C begins after T14. T-perf-* fire only if a render path is over budget.

## REQ → task coverage (every REQ-P3-* maps to ≥1 impl task + ≥1 test task)

| REQ | Task(s) | | REQ | Task(s) |
| --- | --- | --- | --- | --- |
| REQ-P3-LOGIC-001 | T2, T12 | | REQ-P3-UI-001 | T20, T23 |
| REQ-P3-LOGIC-002 | T2, T12 | | REQ-P3-UI-002 | T20, T23 |
| REQ-P3-LOGIC-003 | T2, T12 | | REQ-P3-UI-003 | T16, T18 |
| REQ-P3-LOGIC-004 | T3, T12 | | REQ-P3-UI-004 | T16, T18 |
| REQ-P3-LOGIC-005 | T3, T12 | | REQ-P3-UI-005 | T15, T18 |
| REQ-P3-LOGIC-006 | T4, T12 | | REQ-P3-UI-006 | T16, T17, T18 |
| REQ-P3-LOGIC-007 | T4, T12 | | REQ-P3-UI-007 | T21, T23 |
| REQ-P3-LOGIC-008 | T5, T12 | | REQ-P3-UI-008 | T21, T23 |
| REQ-P3-LOGIC-009 | T6, T12 | | REQ-P3-UI-009 | T21, T23 |
| REQ-P3-LOGIC-010 | T6, T12 | | REQ-P3-UI-010 | T21, T23 |
| REQ-P3-LOGIC-011 | T6, T12 | | REQ-P3-UI-011 | T21, T23 |
| REQ-P3-LOGIC-012 | T7, T12 | | REQ-P3-UI-012 | T21, T23 |
| REQ-P3-LOGIC-013 | T8, T12 | | REQ-P3-UI-013 | T21, T23 |
| REQ-P3-LOGIC-014 | T8, T12 | | REQ-P3-UI-014 | T22, T23 |
| REQ-P3-LOGIC-015 | T9, T12 | | | |
| REQ-P3-LOGIC-016 | T10, T12 | | | |
| REQ-P3-LOGIC-017 | T11, T12, T14, T17, T21 | | | |

All 31 REQ-P3-* map to ≥1 implementation task **and** ≥1 test task (T12 logic / T18+T23 UI).
Cross-cutting: new constants T1 (Art. II); Sharma ΔE00 dataset T12 (NFR-5); i18n T19+T24 (Art. V);
perf T-perf-B/-C (Art. VI, conditional); gates T14 + this-session `sdd-analyze` (Art. I/VIII);
commits T26 (Art. IX).

## Hand-offs

- **AGT-08:** file **ADR-0003** (hardware-palette data placement + NES non-canonical decode, plan
  §5/§8) and **ADR-0004** (Favourites persistence store, plan §6.10) under `docs/adr/` — authored by
  AGT-01 this session; immutable acceptance for T5 (NES/GB data) and T9/T16 (Favourites store).
- **AGT-04:** the CIEDE2000 Sharma-dataset validation (plan §7) is acceptance-critical for T3/T12 —
  embed the published supplementary test pairs; no `perceptual.py` ships without it green.
- **AGT-02:** the traceability matrix already lists all 31 REQ ↔ SC ↔ test targets; the indicative
  module paths there match this plan's §3 (colour hub split across `colour_hub_menu.py` +
  `colour_wheel_widget.py`; `data/favourites_io.py` added for persistence). No REQ delta.
