# Specification — Phase 3: Colour & Palette System (critical)

| Field | Value |
| --- | --- |
| Feature | `phase-3-colour-palette` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — defines the WHAT/WHY for Phase 3 before any Phase-3 code exists |
| REQ-ID range | `REQ-P3-LOGIC-001..017`, `REQ-P3-UI-001..014` |
| Layer scope | `pixelart_creator/logic/` (new: `color_theory.py`, `perceptual.py`, `dither.py`, `hardware_palette.py`, `quantize.py`, `palette_analytics.py`, `palette_ops.py`, `favourites.py`, `palette_io.py`; extends `logic/color.py`, `logic/palette.py`) + `pixelart_creator/ui/` (colour hub, palette editor, dialogs, controls) |
| Binds to (upstream) | `specs/phase-1-core-engine/spec.md` (`logic/color.py`, `logic/palette.py`, `logic/pixel_buffer.py`, `logic/document.py`, `data/project_io.py`) and `specs/phase-1-ui-canvas/spec.md` (canvas view/scene, **right-click SEAM built for exactly this**, palette panel, `ui/commands.py`, i18n) |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) → `sdd-tasks` |
| Research dependency | `docs/research-phase3-colour.md` (F9 + CIEDE2000 / NES-GB / dither / quantize) — **in progress**; grounds harmony math, the colour wheel, quantization, and hardware-palette constraints (plan-time, not a requirement blocker — §7) |

---

## 1. Purpose (WHY)

Phase 1 shipped the pixel-perfect storage core (`color.py` RGBA + hex + `distance_sq` +
`blend_over`; `palette.py` indexed model with add/reorder/nearest + 256-cap; buffer,
document tree, history, `.pixproj`) and, in progress, its first interactive surface
(canvas with a **right-click SEAM built in Phase 1 for exactly this feature**). Phase 3 —
the **critical** phase — turns that foundation into a **professional colour & palette
system** and lands the **marquee S3/S4 colour hub deferred from Phase 1**: the Canva-style
right-click colour hub (persisted Favourites + an RGB colour wheel showing live
colour-theory harmonies) that no competitor (Aseprite / Pro Motion NG / Pixelorama) ships.

Around the hub, Phase 3 adds the full palette toolset an artist expects: colour-theory
harmony math and shade/tint/tone ramps, ordered (Bayer) + Floyd–Steinberg dithering,
hardware-palette constraints (NES / Game Boy simulation), auto palette extraction from an
image (median-cut / k-means, ≤N colours), per-colour usage analytics, colour cycling and
palette swap, a drag/drop palette editor with import/export, indexed-mode workflows, and a
**perceptual (CIEDE2000 / ΔE00) upgrade path** over the Phase-1 `distance_sq` nearest-match.

This document specifies **WHAT** each capability must do and **WHY**, technology-neutral at
the requirement level. The HOW (the harmony/wheel widget realization, the CIEDE2000 and
quantization algorithm internals, the dither kernels) belongs to `sdd-plan`/AGT-01 and the
implementers (AGT-03 logic, AGT-05 UI), **grounded by `docs/research-phase3-colour.md`
(F9)** — this spec fixes the WHAT + acceptance contract and does not invent the internals.

Every Phase-3 mutating operation on a palette or buffer is a **reversible command** wrapped
as a single `QUndoCommand` via `ui/commands.py` over `logic/history.py` (Article I / S7);
the domain logic stays **Qt-free** (Article I / S11) — all colour maths work on the
Phase-1 `RGBA` tuple, never on `QColor`.

### Inherited forward traces (from Phase-1 flags)

- **`distance_sq` → perceptual matching (Phase 3).** `logic/color.distance_sq` explicitly
  documents CIEDE2000 as "a Phase 3 addition layered on top of this baseline". This spec
  **formally inherits and realises** that forward trace: **REQ-P3-LOGIC-004** (ΔE00 metric)
  + **REQ-P3-LOGIC-005** (perceptual `nearest_index` upgrade path over the `distance_sq`
  baseline, which is retained as the fast default).
- **`color.blend_over` remains Phase 4.** Alpha compositing / blend-mode maths
  (`color.blend_over` and its extensions) are **out of Phase-3 scope** — they belong to the
  Phase-4 Layer & Canvas blend-mode system (ROADMAP Phase 4). Noted here so the forward
  trace is not accidentally pulled into Phase 3.

## 2. Scope

**In scope (WHAT) — logic (`logic/`, Qt-free, works on `RGBA` tuples):**
- `logic/color_theory.py` — RGB↔HSV/HSL conversion (wheel geometry substrate); colour-theory
  **harmony** sets (complementary / analogous / triadic / split-complementary) by hue
  rotation; and shade / tint / tone **ramp** generation. (F9)
- `logic/perceptual.py` — **CIEDE2000 (ΔE00)** perceptual distance and a perceptual
  nearest-match usable as an upgrade path over `palette.nearest_index` / `color.distance_sq`.
- `logic/dither.py` — **ordered (Bayer)** dithering and **Floyd–Steinberg** error-diffusion,
  each mapping a source region onto a target palette.
- `logic/hardware_palette.py` — the **NES** and **Game Boy** hardware-palette reference data
  (fixed colour sets).
- `logic/quantize.py` — **palette constraint** (map arbitrary colours onto a fixed hardware
  palette; output ⊆ the hardware palette) and **auto palette extraction** (median-cut and/or
  k-means) producing **≤N** colours from an image/buffer.
- `logic/palette_analytics.py` — **per-colour usage counts** across a document/buffer.
- `logic/palette_ops.py` — **colour cycling** (animate a palette-index range) and **palette
  swap** (remap indices), plus the reversible-command integration for palette edits.
- `logic/favourites.py` — the persisted **Favourites** model (ordered, de-duplicated colour
  list; add / remove / reorder; JSON-serialisable form for persistence). (S3a/S4)
- `logic/palette_io.py` — palette **import/export** encode/decode (GPL / PAL / hex / plain
  text) as pure text/bytes transforms (Qt-free; disk read/write is a thin UI/data concern).

**In scope (WHAT) — UI (`ui/`):**
- **Colour hub (S3/S4) — the marquee feature.** A right-click contextual colour menu
  **anchored at the cursor**, wired into the **Phase-1 right-click seam** on the canvas,
  offering two pick paths: (a) a persisted, user-managed **Favourites** list (add / remove /
  reorder) and (b) a **Canva-style RGB colour wheel** that shows **live colour-theory
  harmonies** as the wheel is moved. A picked colour **applies immediately** and/or is
  **saved to Favourites**; the **active swatch reflects** the current selection.
- **Palette editor** panel: add / remove / **drag-drop reorder** (logic reorder exists),
  **import / export**.
- **Shade-ramp picker**, **dithering brushes**, **palette-constraint UI** (NES/GB presets),
  an **auto-extract-from-image dialog** (N control), a **palette analytics view**,
  **colour-cycling controls**, a **palette-swap UI**, and **indexed-mode workflow** controls.

**Out of scope (this phase):** blend modes / layer opacity / compositing maths
(`color.blend_over` extensions — Phase 4); layer groups / masks (Phase 4); animation
timeline / onion-skin (Phase 5); tileset/tilemap (Phase 6); export/atlas/GIF (Phase 7). No
new technology choices (stack fixed by S8). No plan / tasks / code (AGT-01 / AGT-03 /
AGT-05). The **harmony/wheel/quantization/constraint algorithm internals** are grounded by
`docs/research-phase3-colour.md` (F9), not authored here.

## 3. Story map & feature-label taxonomy

Backbone activities (big verbs) → stories, each tagged with a kebab-case feature label and
roadmap phase. Extends the Phase-1/2 taxonomy (`palette-panel`, `paint-interaction`, …).

### 3.1 User stories

- **US-1 (Artist / pick-colour-fast).** As an artist, I want to **right-click on the canvas
  and get a colour menu at my cursor** with my saved Favourites and a colour wheel, so I can
  pick or explore a colour without leaving my stroke. → REQ-P3-UI-003 · `colour-hub` · P3
- **US-2 (Artist / save-favourites).** As an artist, I want a **persisted Favourites list**
  I can add to, remove from, and reorder, so my working palette follows me between sessions.
  → REQ-P3-LOGIC-015, REQ-P3-UI-004 · `favourites` · P3
- **US-3 (Artist / explore-harmonies).** As an artist, I want a **colour wheel that shows
  live complementary / analogous / triadic / split-complementary harmonies** (plus
  shade/tint ramps) as I move it, so I can build a coherent palette by theory. →
  REQ-P3-LOGIC-001, -002, -003, REQ-P3-UI-005 · `colour-wheel` · P3
- **US-4 (Artist / apply-immediately).** As an artist, I want a **picked colour to apply
  immediately to the active swatch** and/or be **saved to Favourites** so painting continues
  at once. → REQ-P3-UI-006 · `colour-hub` · P3
- **US-5 (Artist / edit-palette).** As an artist, I want to **add, remove, and drag-drop
  reorder** palette colours and **import/export** palettes, so I can curate and share them.
  → REQ-P3-LOGIC-016, REQ-P3-UI-001, -002 · `palette-editor` · P3
- **US-6 (Artist / shade-ramps).** As an artist, I want a **shade-ramp picker** that
  generates shade/tint/tone ramps from a base colour so I can shade consistently. →
  REQ-P3-LOGIC-003, REQ-P3-UI-007 · `shade-ramp` · P3
- **US-7 (Artist / dither).** As an artist, I want **dithering brushes** (ordered/Bayer and
  Floyd–Steinberg) so I can blend colours in a retro style. →
  REQ-P3-LOGIC-006, -007, REQ-P3-UI-008 · `dithering` · P3
- **US-8 (Artist / hardware-constraints).** As an artist, I want to **constrain my art to a
  NES or Game Boy palette** so it looks authentic to the target hardware. →
  REQ-P3-LOGIC-008, -009, REQ-P3-UI-009 · `palette-constraint` · P3
- **US-9 (Artist / extract-palette).** As an artist, I want to **extract a palette of ≤N
  colours from an image** so I can reuse an existing artwork's colours. →
  REQ-P3-LOGIC-010, -011, REQ-P3-UI-010 · `palette-extract` · P3
- **US-10 (Artist / analytics).** As an artist, I want to **see how often each palette colour
  is used** across my document so I can prune or rebalance. →
  REQ-P3-LOGIC-012, REQ-P3-UI-011 · `palette-analytics` · P3
- **US-11 (Artist / colour-cycle).** As an artist, I want to **animate a palette-index range
  (colour cycling)** so I can preview classic cycling effects. →
  REQ-P3-LOGIC-013, REQ-P3-UI-012 · `colour-cycling` · P3
- **US-12 (Artist / palette-swap).** As an artist, I want to **swap/remap palette indices**
  so I can recolour indexed art wholesale. → REQ-P3-LOGIC-014, REQ-P3-UI-013 ·
  `palette-swap` · P3
- **US-13 (Artist / indexed-workflow).** As an artist, I want **indexed-mode workflows**
  (switch RGBA↔indexed, paint by palette index) so I can work in a constrained palette. →
  REQ-P3-UI-014 · `indexed-mode` · P3
- **US-14 (Artist / accurate-match).** As an artist, I want **perceptually accurate
  nearest-colour matching (CIEDE2000)** when a colour is snapped to the palette so the match
  looks right, not just numerically close. → REQ-P3-LOGIC-004, -005 · `perceptual-match` · P3
- **US-15 (Artist / reversibility).** As an artist, I want **every** palette edit and
  colour-constraint/quantize/dither/swap operation to be **one undoable step**. →
  REQ-P3-LOGIC-017 (all mutating REQs) · `undo-redo` · P3 (extends P1)

### 3.2 Feature-label taxonomy (Phase 3 additions)

`colour-hub` · `favourites` · `colour-wheel` · `palette-editor` · `shade-ramp` ·
`dithering` · `palette-constraint` · `palette-extract` · `palette-analytics` ·
`colour-cycling` · `palette-swap` · `indexed-mode` · `perceptual-match` — all `P3`, aligned
to the ROADMAP Phase-3 bullets and extensible to Phases 4–12 without renaming.

## 4. Functional requirements

Each REQ carries `traces:` to the dossier S-id(s) / F9 it realises (or notes it is a
Phase-3 capability). Layer, owner agent, and acceptance scenarios are in `traceability.md`.

### 4.1 Logic layer (`REQ-P3-LOGIC-*`)

#### REQ-P3-LOGIC-001 — RGB↔HSV/HSL colour-model conversion
`traces:` S3b (colour-wheel geometry), F9; Phase-3 capability
Pure, deterministic conversions between the Phase-1 `RGBA` tuple and HSV (and HSL) — the
geometric substrate the colour wheel and every hue-rotation harmony need. Round-trips are
stable within documented rounding (RGB→HSV→RGB = identity for representable colours, CL-1).
Alpha is preserved through conversion. Zero Qt (the maths do **not** use `QColor`, even
though the UI wheel may — CL-2). Malformed input raises a domain error subclassing
`ValueError` (Phase-1 convention).

#### REQ-P3-LOGIC-002 — Colour-theory harmony sets
`traces:` S3b, F9; Phase-3 capability; **grounded by F9 research**
Given a base colour, produce the harmony sets by **hue rotation** on the wheel:
**complementary** (+`HARMONY_COMPLEMENTARY_DEG`=180°), **analogous**
(±`HARMONY_ANALOGOUS_DEG`=30°), **triadic** (±`HARMONY_TRIADIC_DEG`=120°), and
**split-complementary** (±`HARMONY_SPLIT_COMPLEMENTARY_DEG`=150°) — the angles fixed by F9
/ S3b. Saturation and value are preserved; hue wraps modulo 360°; alpha preserved. Output is
deterministic (P2). Angles/step counts come from `constants.py` (Article II, §9). The
detailed wheel model is grounded by F9; this REQ owns the WHAT + the **angle-correctness**
acceptance.

#### REQ-P3-LOGIC-003 — Shade / tint / tone ramp generation
`traces:` S3b (shade/tint ramps), F9; Phase-3 capability
From a base colour, generate ordered ramps of `RAMP_STEP_COUNT` steps: a **shade** ramp
(toward black — decreasing value), a **tint** ramp (toward white — increasing value toward
white / decreasing saturation), and a **tone** ramp (toward grey — decreasing saturation).
Ramps are monotonic in their driving channel, include the base colour, and are deterministic.
Step count from `constants.py`. Alpha preserved.

#### REQ-P3-LOGIC-004 — CIEDE2000 perceptual distance (ΔE00)
`traces:` S3b; **inherits the Phase-1 `distance_sq`→perceptual forward trace**; F9-adjacent
A perceptual colour-difference metric **ΔE00 (CIEDE2000)** over two RGBA colours (via an
RGB→Lab conversion), parameterised by `CIEDE2000_KL` / `CIEDE2000_KC` / `CIEDE2000_KH`
(=1.0, from `constants.py`). **Acceptance-critical:** matches published CIEDE2000 reference
values (e.g. the Sharma et al. test-data pairs) within a documented tolerance (CL-9). Pure,
deterministic, Qt-free. The standard's algorithm internals are grounded by F9; this REQ owns
the WHAT + the **known-value** acceptance.

#### REQ-P3-LOGIC-005 — Perceptual nearest-match (upgrade path over `distance_sq`)
`traces:` S3b; **realises the Phase-1 `distance_sq`→perceptual forward trace**
A perceptual nearest-palette-index match that ranks by **ΔE00 (REQ-P3-LOGIC-004)** instead
of `color.distance_sq`, exposed as an **opt-in upgrade path** alongside the retained fast
`palette.nearest_index` default (CL-10). Ties resolve to the lower index (deterministic, P2,
matching `palette.nearest_index`). Empty palette raises `PaletteError` (existing convention).

#### REQ-P3-LOGIC-006 — Ordered (Bayer) dithering
`traces:` S3b (dithering brushes); Phase-3 capability; F9-adjacent
Ordered dithering of a source region onto a target palette using a Bayer threshold matrix of
size `BAYER_MATRIX_SIZE` (=4 → 4×4, CL-6). Deterministic for a fixed input+palette+matrix.
**No colour absent from the target palette appears** in the output (a mapping, not a blend).
Zero Qt.

#### REQ-P3-LOGIC-007 — Floyd–Steinberg error-diffusion dithering
`traces:` S3b (dithering brushes); Phase-3 capability; F9-adjacent
Floyd–Steinberg error-diffusion of a source region onto a target palette (standard
7/16, 3/16, 5/16, 1/16 error distribution). Deterministic for a fixed input+palette. **Output
⊆ the target palette** (no new colours). Zero Qt.

#### REQ-P3-LOGIC-008 — Hardware-palette reference data (NES / Game Boy)
`traces:` S6 (retro-hardware simulation); Phase-3 capability; F9-adjacent
Fixed reference colour sets for the **NES** and the (4-shade) **Game Boy** hardware palettes,
grounded by F9 research. Exposed as immutable `Palette` (or RGBA-list) constants. Flagged for
AGT-01 placement (module-local reference table vs `constants.py`, §9 — analogous to the
Phase-2 enum-placement call).

#### REQ-P3-LOGIC-009 — Palette-constraint mapping (map onto a fixed hardware palette)
`traces:` S6; Phase-3 capability; **grounded by F9**
Map an arbitrary-colour buffer onto a **fixed hardware palette** (NES / GB /
caller-supplied), each pixel replaced by its nearest palette colour (via `distance_sq` or,
opt-in, ΔE00 — CL-11). **Acceptance-critical:** the output's colour set is a **subset of the
hardware palette** (⊆), with no colour outside it. Deterministic; Qt-free.

#### REQ-P3-LOGIC-010 — Auto palette extraction: median-cut (≤N)
`traces:` S6 (extract from image); Phase-3 capability; **grounded by F9**
Extract a palette of **at most N** colours from an image/buffer by **median-cut**, `N`
defaulting to `PALETTE_EXTRACT_DEFAULT_N` (=16, CL-7). **Acceptance-critical:** the returned
palette has **≤N** colours. Deterministic for a fixed input+N (P2). Returns a `Palette`.
Qt-free.

#### REQ-P3-LOGIC-011 — Auto palette extraction: k-means (≤N)
`traces:` S6 (extract from image); Phase-3 capability; **grounded by F9**
An alternative extraction by **k-means** (k = N, seeded deterministically for
reproducibility, CL-8), also producing **≤N** colours. Deterministic for a fixed
input+N+seed. Returns a `Palette`. Qt-free. (Median-cut is the default; k-means is the
higher-quality alternative — CL-7.)

#### REQ-P3-LOGIC-012 — Palette analytics (per-colour usage counts)
`traces:` S6 (usage stats); Phase-3 capability
Compute the **per-colour usage count** across a buffer/document (how many pixels use each
colour or palette index), returned as a deterministic mapping ordered by count then index.
Handles both RGBA and indexed buffers. Qt-free; read-only (no mutation).

#### REQ-P3-LOGIC-013 — Colour cycling (animate a palette-index range)
`traces:` S6 (colour cycling); Phase-3 capability
Given a palette and an index **range** `[start, end]`, produce the cycled palette at step
`k` by rotating the colours within that range (forward/backward). Pure and deterministic:
cycling by `len(range)` steps returns the original palette (round-trip). The **animation
timing** (rate) is a UI concern; the logic is a pure per-step transform. Bad range raises
`PaletteError`.

#### REQ-P3-LOGIC-014 — Palette swap / index remap
`traces:` S6 (palette swap); Phase-3 capability
Remap an indexed buffer's indices through a supplied index→index (or index→colour) mapping,
producing a recoloured buffer. **Reversible** (an inverse mapping restores the original — see
REQ-P3-LOGIC-017). A mapping referencing an out-of-range index raises `PaletteError`.
Deterministic; Qt-free.

#### REQ-P3-LOGIC-015 — Favourites model (persisted, ordered, de-duplicated)
`traces:` S3a, S4; Phase-3 capability
An ordered, **de-duplicated** list of favourite `RGBA` colours with `add` (append, no-op if
present), `remove`, `reorder` (move), and value equality — the model backing the colour-hub
Favourites list. Exposes a **JSON-serialisable** form (`to_serializable` / `from_serializable`)
so the UI/data layer can persist and restore it (persistence wiring is REQ-P3-UI-004; the
model itself is Qt-free). Optional soft cap flagged for AGT-01 (§9). Bad colour raises the
domain error convention.

#### REQ-P3-LOGIC-016 — Palette import/export encode/decode
`traces:` S6 (import/export); Phase-3 capability
Encode/decode a `Palette` to/from common palette text formats — **GIMP `.gpl`**, **JASC
`.pal`**, and **hex / plain lists** — as pure, defensive text transforms (reuses
`color.from_hex` / `color.to_hex`). Malformed input is rejected with the domain-error
convention (defensive parsing, Article VII spirit). **Disk read/write itself is a thin
UI/data concern** (REQ-P3-UI-002); this REQ owns only the Qt-free encode/decode. Round-trip
(encode∘decode) preserves the palette for supported formats.

#### REQ-P3-LOGIC-017 — Reversible-command integration for all Phase-3 palette/buffer edits *(NFR)*
`traces:` S7 (command-pattern undo/redo, C1/F1); Phase-3 capability
Every Phase-3 **mutating** operation — palette add/remove/reorder, palette swap
(REQ-P3-LOGIC-014), colour-cycling application, constraint/quantize application
(REQ-P3-LOGIC-009), and dither application (REQ-P3-LOGIC-006/-007) — is expressible as a
Phase-1 reversible command (`PixelEdit` diff or a `FunctionCommand` do/undo pair) so
`ui/commands.py` wraps it as **one** `QUndoCommand`. Invariant: `apply ∘ undo = identity`.
No Qt in the logic path (Article I).

### 4.2 UI layer (`REQ-P3-UI-*`)

#### REQ-P3-UI-001 — Palette editor panel (add / remove / drag-drop reorder)
`traces:` S6 (palette editor); Phase-3 capability
Extends the Phase-1 palette panel: **add** a colour, **remove** the selected colour, and
**drag-drop reorder** swatches (binding to `palette.move`, which exists). Each mutation is
**one** `QUndoCommand`. Controls are `tr()`-wrapped, keyboard-reachable, correct in both
themes. No domain logic in the widget.

#### REQ-P3-UI-002 — Palette import / export UI
`traces:` S6; Phase-3 capability
`tr()`-wrapped **import** / **export** actions with file dialogs, wired to
`logic/palette_io.py` (REQ-P3-LOGIC-016) encode/decode; the thin disk read/write lives here
(UI/data), keeping the logic Qt-free. Malformed imported files surface a user-facing error
(no crash), keyboard-reachable, both themes.

#### REQ-P3-UI-003 — Colour hub: right-click contextual menu anchored at cursor *(marquee, S3)*
`traces:` **S3**; Phase-3 capability
The **marquee S3 feature**: a contextual colour menu that **opens at the cursor** on
right-click, **wired into the Phase-1 right-click SEAM** on the canvas (built in Phase 1 for
exactly this). It hosts the two pick paths — Favourites (REQ-P3-UI-004) and the colour wheel
(REQ-P3-UI-005). Menu strings `tr()`-wrapped, keyboard-reachable (openable + navigable
without a mouse), correct in both themes.

#### REQ-P3-UI-004 — Colour hub: Favourites list (add / remove / reorder, persisted) *(S3a/S4)*
`traces:` **S3a, S4**; Phase-3 capability
Within the hub, a **Favourites** list backed by `logic/favourites.py` (REQ-P3-LOGIC-015):
add the current colour, remove a favourite, reorder favourites; clicking a favourite
**applies it** (REQ-P3-UI-006). Favourites **persist across sessions** (via the serialisable
model + the app's project/settings store) — **acceptance-critical: a saved favourite is
present after restart** (CL-4). `tr()`-wrapped, keyboard-reachable, both themes.

#### REQ-P3-UI-005 — Colour hub: Canva-style RGB colour wheel with live harmonies *(S3b/F9)*
`traces:` **S3b, F9**; Phase-3 capability; **UI grounded by F9**
A **Canva-style RGB colour wheel** in the hub: dragging/clicking picks a hue+saturation (with
a value/brightness control); as the selection moves, **live harmony swatches**
(complementary / analogous / triadic / split-complementary + shade/tint ramps) update from
`logic/color_theory.py` (REQ-P3-LOGIC-001/-002/-003). **Acceptance-critical: the harmony
swatches update on every wheel move** and reflect the correct angles (CL-3). The harmony
**maths live in logic**; the widget only renders + binds. `tr()`-wrapped, keyboard-reachable,
both themes.

#### REQ-P3-UI-006 — Colour hub: picked colour applies immediately + active swatch reflects it *(S4)*
`traces:` **S4**; Phase-3 capability
A colour picked in the hub (from the wheel, a harmony swatch, or Favourites) **applies
immediately** to the **active swatch** (so the next left-click paints it, S2) and/or is
**saved to Favourites** on request. **Acceptance-critical: after a wheel/favourite pick the
active swatch equals the picked colour** (CL-3, CL-5). Both themes; keyboard-reachable.

#### REQ-P3-UI-007 — Shade-ramp picker
`traces:` S3b (shade/tint ramps); Phase-3 capability
A `tr()`-wrapped control that shows the shade / tint / tone ramps
(REQ-P3-LOGIC-003) of a base colour and lets the user pick a ramp step (applying it via
REQ-P3-UI-006 / adding it to the palette). Keyboard-reachable, both themes.

#### REQ-P3-UI-008 — Dithering brushes
`traces:` S3b (dithering brushes); Phase-3 capability
Tool controllers for **ordered/Bayer** and **Floyd–Steinberg** dithering
(REQ-P3-LOGIC-006/-007) between two (or palette) colours; a stroke commits as **one**
`QUndoCommand`. `tr()`-wrapped, keyboard-reachable, both themes.

#### REQ-P3-UI-009 — Palette-constraint UI (NES / GB presets)
`traces:` S6; Phase-3 capability
`tr()`-wrapped presets (**NES**, **Game Boy**) that constrain the active buffer/selection to
the chosen hardware palette (REQ-P3-LOGIC-008/-009) as **one** `QUndoCommand`. The UI
surfaces the ⊆ guarantee only through behaviour. Keyboard-reachable, both themes.

#### REQ-P3-UI-010 — Auto-extract-from-image dialog
`traces:` S6; Phase-3 capability
A `tr()`-wrapped dialog to **extract a palette from an image** with an **N** control
(default `PALETTE_EXTRACT_DEFAULT_N`) and a median-cut / k-means choice (REQ-P3-LOGIC-010/
-011); the extracted ≤N-colour palette loads into the palette editor. Keyboard-reachable,
both themes.

#### REQ-P3-UI-011 — Palette analytics view
`traces:` S6 (usage stats); Phase-3 capability
A `tr()`-wrapped, read-only view of **per-colour usage counts** (REQ-P3-LOGIC-012) across the
document (sortable by count). Keyboard-reachable, legible in both themes.

#### REQ-P3-UI-012 — Colour-cycling controls
`traces:` S6 (colour cycling); Phase-3 capability
`tr()`-wrapped controls to select a palette-index **range** and **play/pause** cycling
(REQ-P3-LOGIC-013) at a UI-driven rate, previewing the effect on the canvas. Cycling is a
non-destructive preview unless committed. Keyboard-reachable, both themes.

#### REQ-P3-UI-013 — Palette-swap UI
`traces:` S6 (palette swap); Phase-3 capability
A `tr()`-wrapped UI to define an index→index (or index→colour) remap and **apply** it
(REQ-P3-LOGIC-014) to indexed art as **one** `QUndoCommand`. Keyboard-reachable, both themes.

#### REQ-P3-UI-014 — Indexed-mode workflow controls
`traces:` S6 (indexed workflows); Phase-3 capability
`tr()`-wrapped controls to switch a document between RGBA and **indexed** mode and to paint
by **palette index** (using the active palette). Mode switch and index paint are undoable.
Keyboard-reachable, both themes.

## 5. Non-functional requirements

- **NFR-1 (Purity, S11 / Article I).** All new `logic/` modules import **zero** Qt — the
  colour maths work on the `RGBA` tuple, never on `QColor`; only `ui/commands.py` and `ui/`
  touch Qt.
- **NFR-2 (Determinism, P2).** Harmony, ramp, CIEDE2000, dither, constraint, extraction
  (fixed seed), analytics, cycling, and swap logic produce identical output for identical
  input (test-asserted, incl. Hypothesis properties).
- **NFR-3 (Reversibility).** `apply ∘ undo = identity` for every mutating op
  (REQ-P3-LOGIC-017); each is exactly one `QUndoCommand`.
- **NFR-4 (Palette containment / ≤N, acceptance-critical).** Dither (REQ-P3-LOGIC-006/-007)
  and constraint (REQ-P3-LOGIC-009) outputs are **⊆ the target/hardware palette**; extraction
  (REQ-P3-LOGIC-010/-011) yields **≤N** colours. Test-asserted by comparing output colour set.
- **NFR-5 (Perceptual correctness, acceptance-critical).** CIEDE2000 (REQ-P3-LOGIC-004)
  matches published ΔE00 reference values within tolerance (CL-9); harmony angles
  (REQ-P3-LOGIC-002) match the F9 angles exactly (CL-3).
- **NFR-6 (Numerics, S12 / Article II).** All new tuning values (§9) live only in
  `logic/constants.py`; no magic numbers at call sites (harmony angles, ramp step count,
  Bayer size, default N, ΔE00 weights).
- **NFR-7 (Coverage, S13 / Article IV).** ≥90 % line / ≥80 % branch per package; logic via
  pytest + Hypothesis, UI via pytest-qt in **both themes**, headless.
- **NFR-8 (a11y + i18n + both themes, Article V).** Every new user-visible string wrapped in
  `tr()`; new widgets override `changeEvent`; all controls (incl. the colour hub, wheel, and
  Favourites) keyboard-reachable with visible focus; the wheel/swatches/analytics legible and
  contrast-correct in both themes.
- **NFR-9 (Performance, S12 / Article VI).** The live-harmony wheel update, dither preview,
  and analytics over the 8K buffer hold `FRAME_BUDGET_MS = 16`; over-budget → an AGT-10
  directive, never a relaxed budget. (Analytics over 33 M pixels is vectorised — F7.)
- **NFR-10 (Defensive input, Article VII).** Imported palette files (REQ-P3-LOGIC-016 /
  REQ-P3-UI-002) are validated defensively; malformed input is rejected, never `eval`/`exec`.

## 6. Non-goals (explicit)

- **No blend modes / layer opacity / compositing maths** — `color.blend_over` and its
  extensions are **Phase 4** (explicitly retained there; not pulled into Phase 3).
- No layer groups / masks / reference layers (Phase 4).
- No animation timeline / onion-skin / colour-cycling *export* (Phase 5/7 — Phase-3 cycling
  is a live preview + per-step logic, not a GIF export).
- No tileset/tilemap (Phase 6); no export / sprite-sheet / atlas / GIF pipeline (Phase 7).
- No new technology choices (stack fixed by S8); no plan / tasks / code.
- The **harmony/wheel/CIEDE2000/quantization/constraint algorithm internals** are grounded by
  `docs/research-phase3-colour.md` (F9), not invented here (P1).

## 7. Dependencies

**On Phase 1 (hard):**
- `logic/color.py` — `RGBA`, `rgba`, `is_rgba`, `to_hex`/`from_hex`, `distance_sq` (the
  baseline the perceptual metric upgrades), `CHANNEL_MIN/MAX`. (REQ-P1-LOGIC-001)
- `logic/palette.py` — `Palette` (add/remove/`move` reorder/`nearest_index`/`index_of`),
  `MAX_PALETTE_SIZE` 256-cap — the model the editor, extraction, constraint, cycling, and
  swap build on. (REQ-P1-LOGIC-002)
- `logic/pixel_buffer.py` — RGBA + indexed buffer (`region`, `get`/`set`, index math) — the
  substrate for dither, constraint, analytics, swap. (REQ-P1-LOGIC-006/-007, F7)
- `logic/document.py` — the frame/layer tree analytics counts across. (REQ-P1-LOGIC-013)
- `logic/history.py` — `Command` / `PixelEdit` / `FunctionCommand` / `record_edit` — every
  Phase-3 mutating op is built on it. (REQ-P1-LOGIC-009)
- `data/project_io.py` — the persistence store Favourites (REQ-P3-UI-004) and palettes may
  ride on. (REQ-P1-DATA-001)
- `ui/commands.py` — the QUndoCommand bridge wrapping each logic op as one undo step.
- **The Phase-1 canvas right-click SEAM** (`ui/canvas_view.py`) — the colour hub
  (REQ-P3-UI-003) wires directly into it (built in Phase 1 for exactly this).
- `ui/main_window.py` palette panel — extended by the palette editor (REQ-P3-UI-001).
- `ui/i18n.py` — LanguageManager + `changeEvent`/`tr()` (F5/F6) for all new strings.

**On research (hard for the grounded internals; NOT a requirement blocker):**
- **`docs/research-phase3-colour.md` (F9 + CIEDE2000 / NES-GB / dither / quantize),
  The Researcher via the orchestrator — in progress.** It grounds: the harmony-wheel model
  (HSV geometry, the +180/±30/±120/±150 angles — already stated in F9), CIEDE2000's algorithm
  + reference values, the NES/GB hardware-palette colour data, the dither kernels, and the
  median-cut / k-means quantization internals. Per A2-D2 Branch B, the **WHAT + acceptance
  contracts** (harmony angles, ΔE00 known values, ≤N, ⊆ hardware palette, wheel updates
  active swatch, Favourites persist) are specifiable **now**; only the algorithm internals
  must land before `sdd-plan` finalises them. **This spec is not blocked** (see §11).

**Downstream:** AGT-01 (`sdd-plan` consumes this spec; rules on constant/reference-data
placement §9); AGT-06 (Gherkin → pytest-qt / pytest acceptance tests); AGT-03/04 (logic +
tests, harmony grounded by F9); AGT-05 (colour hub + palette UI via the `colour-hub` skill,
pytest-qt both themes); AGT-07 (i18n of new strings); AGT-10 (render/perf of the live wheel +
analytics).

## 8. Recommended slicing (for the orchestrator)

Phase 3 is **critical and large**; recommend **three vertical sub-slices** (logic-first, then
the marquee hub, then the remaining palette workflows), so the F9-gated maths land without
blocking the un-gated logic and the high-value hub ships early:

- **Slice 3A — Colour & palette LOGIC** (`REQ-P3-LOGIC-001..017`). All Qt-free logic:
  `color_theory.py`, `perceptual.py`, `dither.py`, `hardware_palette.py`, `quantize.py`,
  `palette_analytics.py`, `palette_ops.py`, `favourites.py`, `palette_io.py` + new constants
  (§9) + pytest/Hypothesis coverage. **Ships first** — it is the substrate every UI control
  binds to. **F9-gated within 3A:** harmony (REQ-P3-LOGIC-002), the wheel-geometry conversion
  (-001), CIEDE2000 (-004), constraint (-009), and extraction (-010/-011) depend on the
  research report; the rest of 3A (ramps¹, dither, analytics, cycling, swap, favourites,
  import/export) is **un-gated** and proceeds in parallel. (¹ramps use only HSV rotation, so
  they follow -001.)
- **Slice 3B — Colour hub UI (marquee S3/S4)** (`REQ-P3-UI-003..006`). The right-click hub:
  the cursor-anchored menu into the Phase-1 seam + Favourites (persisted) + the Canva-style
  wheel with live harmonies + immediate apply/active-swatch. **Depends on** 3A
  (`color_theory`, `favourites`) + the Phase-1 right-click seam + palette panel. Recommend
  this as its **own slice** given it is the marquee, highest-value deferral from Phase 1.
- **Slice 3C — Palette workflows UI** (`REQ-P3-UI-001, -002, -007..-014`). Palette editor +
  import/export, shade-ramp picker, dithering brushes, constraint presets, extract dialog,
  analytics view, colour-cycling controls, palette-swap UI, indexed-mode workflows +
  pytest-qt (both themes) + i18n. **Depends on** 3A.

Rationale: keeps each slice within one constitution-gated increment; lets the F9 research land
without blocking un-gated logic or the UI shell; delivers the marquee hub early; keeps the
Qt-free logic testable headlessly before any UI exists. Final task ordering is
AGT-01/orchestrator's call.

## 9. New constants (for AGT-03 — Article II / S12)

New tuning values MUST be added to `logic/constants.py` with a source citation and imported by
name (never inlined). Flagged here for AGT-03; AGT-01 confirms tuning-vs-intrinsic and
reference-data placement.

| Constant | Proposed value | Rationale / source | Classification |
| --- | --- | --- | --- |
| `HARMONY_COMPLEMENTARY_DEG` | `180` | F9 / S3b complementary offset | Tuning → `constants.py` |
| `HARMONY_ANALOGOUS_DEG` | `30` | F9 / S3b analogous ±offset | Tuning → `constants.py` |
| `HARMONY_TRIADIC_DEG` | `120` | F9 / S3b triadic ±offset | Tuning → `constants.py` |
| `HARMONY_SPLIT_COMPLEMENTARY_DEG` | `150` | F9 / S3b split-complementary ±offset | Tuning → `constants.py` |
| `RAMP_STEP_COUNT` | `5` *(candidate)* | Shade/tint/tone ramp length (Aseprite ramp norm) | Tuning → `constants.py` (AGT-01 to confirm value) |
| `BAYER_MATRIX_SIZE` | `4` | 4×4 ordered-dither matrix (F9 dither) | Tuning → `constants.py` |
| `PALETTE_EXTRACT_DEFAULT_N` | `16` *(candidate)* | Default auto-extract colour count | Tuning → `constants.py` (AGT-01 to confirm) |
| `CIEDE2000_KL` / `CIEDE2000_KC` / `CIEDE2000_KH` | `1.0` / `1.0` / `1.0` | Standard ΔE00 weighting factors (F9 / Sharma et al.) | Tuning → `constants.py` |
| `KMEANS_SEED` | *(candidate)* e.g. `0` | Deterministic k-means seed (P2 reproducibility, CL-8) | Tuning candidate — AGT-01 to confirm |
| `CYCLE_DEFAULT_FPS` | *(candidate)* | Default colour-cycling rate (UI-driven) | Tuning candidate — likely UI-side; AGT-01 to place |
| `FAVOURITES_MAX` | *(candidate)* | Optional soft cap on Favourites | Tuning candidate — AGT-01 to confirm need |
| **NES / Game Boy palette tables** | fixed RGBA sets (F9) | Hardware reference data (REQ-P3-LOGIC-008) | **Reference data** — AGT-01 to rule: module-local table in `hardware_palette.py` vs `constants.py` (cf. Phase-2 `SymmetryAxis` enum-placement call; reference *data*, not a tuning scalar) |

Note: none duplicate an existing `constants.py` value. New domain exceptions (e.g.
`ColorTheoryError`, `QuantizeError`, `DitherError`, `FavouritesError`) subclass `ValueError`
per the Phase-1 convention (`ColorError`, `PaletteError`); reuse `PaletteError` where the op
is palette-index-bound (cycling range, swap remap).

## 10. Clarifications (resolved defaults, per authoring rule R5)

Ordinary ambiguities are resolved here with defaults grounded in the dossier + F9 + Aseprite /
Pixelorama / Pro Motion NG norms, recorded as category-1 decisions (A2-D2 Branch B). **No open
clarification blocks planning** (see §11).

- **CL-1 — Colour model for the wheel/harmonies?** **HSV** hue rotation (with HSL provided);
  RGB↔HSV round-trips within documented rounding. Grounded by F9 (Qt `QColor` HSV APIs are the
  UI realisation; logic uses tuple maths).
- **CL-2 — May logic use `QColor` for conversions?** **No** — `logic/` stays Qt-free (Article
  I); conversions are pure tuple maths. The `ui/` wheel may use `QColor` HSV APIs internally.
- **CL-3 — Harmony angles?** Fixed by F9/S3b: complementary **+180°**, analogous **±30°**,
  triadic **±120°**, split-complementary **±150°**; saturation/value preserved, hue mod 360°.
- **CL-4 — Favourites persistence & de-duplication?** Favourites are an **ordered,
  de-duplicated** list that **persists across sessions** (serialisable model + app store);
  adding an existing colour is a no-op. Cross-session persistence is acceptance-critical.
- **CL-5 — "Applies immediately and/or saved" (S4)?** A pick **always** updates the active
  swatch immediately; saving to Favourites is an **explicit** additional action (add-to-
  favourites), so a pick doesn't silently grow the list.
- **CL-6 — Bayer matrix size?** `BAYER_MATRIX_SIZE = 4` (4×4 ordered-dither matrix); default,
  grounded by F9.
- **CL-7 — Extraction algorithm default?** **Median-cut** is the default (fast, deterministic);
  **k-means** is the higher-quality opt-in alternative. Both cap at **≤N**.
- **CL-8 — k-means determinism?** Seeded deterministically (`KMEANS_SEED`) so identical
  input+N+seed reproduces identical output (P2).
- **CL-9 — CIEDE2000 correctness bar?** Matches published ΔE00 reference pairs (Sharma et al.
  CIEDE2000 test data) within a documented numeric tolerance; `kL=kC=kH=1.0`.
- **CL-10 — Perceptual match: replace or add?** **Add** — ΔE00 nearest-match is an **opt-in
  upgrade path**; `distance_sq` / `palette.nearest_index` remains the retained fast default
  (backward-compatible, honours the Phase-1 forward-trace note).
- **CL-11 — Constraint metric?** Nearest hardware colour by `distance_sq` by default; ΔE00
  opt-in (CL-10). Output is always **⊆** the hardware palette.
- **CL-12 — Palette import/export formats?** GIMP `.gpl`, JASC `.pal`, and hex/plain lists;
  encode/decode is Qt-free logic, disk I/O is the thin UI action. Defensive parsing (Article
  VII).
- **CL-13 — Colour cycling scope?** A **non-destructive live preview** by default (rotating a
  palette-index range); committing to pixels is explicit. Cycling by the range length is a
  round-trip (identity).
- **CL-14 — Palette swap target?** Operates on **indexed** buffers (index→index or
  index→colour remap); on RGBA buffers the caller supplies a colour→colour map. Reversible.
- **CL-15 — Indexed-mode default?** Documents default to **RGBA** (Phase-1 behaviour);
  indexed mode is an explicit, undoable switch (REQ-P3-UI-014).
- **CL-16 — `color.blend_over` in Phase 3?** **No** — compositing/blend maths are **Phase 4**;
  Phase-3 colour maths never touch it (explicit non-goal, §6).

No item required SUSPEND: F9 grounds the algorithm **internals** at plan time, but every
requirement's **WHAT + acceptance** (angles, ΔE00 known values, ≤N, ⊆ hardware palette, wheel
updates active swatch, Favourites persist) is specifiable now (A2-D2 Branch B).

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour, phrased for **headless** testing (logic via pytest +
Hypothesis, UI via pytest-qt in **both themes**). The R2 acceptance callouts — harmony-angle
correctness, CIEDE2000 known-value, ≤N quantization, ⊆ hardware palette, wheel→active-swatch +
Favourites persistence, live-harmony updates on wheel move — are included. Scenario ↔ REQ ↔
(future) test mapping is in `traceability.md`.

### Feature: RGB↔HSV/HSL conversion (REQ-P3-LOGIC-001)
```gherkin
Scenario: SC-L001-1 RGB→HSV→RGB round-trips a representable colour exactly (CL-1)
Scenario: SC-L001-2 known primaries convert to expected HSV (red=0°, green=120°, blue=240°)
Scenario: SC-L001-3 alpha is preserved through conversion
Scenario: SC-L001-4 HSL is provided and round-trips within documented rounding
Scenario: SC-L001-5 malformed input raises the domain error (subclass of ValueError)
```

### Feature: Colour-theory harmonies (REQ-P3-LOGIC-002)
```gherkin
Scenario: SC-L002-1 ANGLE CORRECTNESS: complementary rotates hue by exactly +180° (S/V preserved)
Scenario: SC-L002-2 ANGLE CORRECTNESS: analogous yields hue ±30°
Scenario: SC-L002-3 ANGLE CORRECTNESS: triadic yields hue ±120°
Scenario: SC-L002-4 ANGLE CORRECTNESS: split-complementary yields hue ±150°
Scenario: SC-L002-5 hue wraps modulo 360° (e.g. base 300° complementary = 120°)
Scenario: SC-L002-6 harmonies are deterministic for identical input
```

### Feature: Shade/tint/tone ramps (REQ-P3-LOGIC-003)
```gherkin
Scenario: SC-L003-1 a shade ramp of RAMP_STEP_COUNT steps decreases value monotonically toward black
Scenario: SC-L003-2 a tint ramp trends toward white
Scenario: SC-L003-3 a tone ramp decreases saturation toward grey
Scenario: SC-L003-4 each ramp includes the base colour and is deterministic
```

### Feature: CIEDE2000 perceptual distance (REQ-P3-LOGIC-004)
```gherkin
Scenario: SC-L004-1 KNOWN VALUES: ΔE00 matches published Sharma et al. reference pairs within tolerance (CL-9)
Scenario: SC-L004-2 ΔE00 of a colour with itself is 0
Scenario: SC-L004-3 ΔE00 is symmetric (a,b) == (b,a)
Scenario: SC-L004-4 kL/kC/kH weights are read from constants.py (=1.0)
```

### Feature: Perceptual nearest-match (REQ-P3-LOGIC-005)
```gherkin
Scenario: SC-L005-1 perceptual match can differ from distance_sq match where ΔE00 disagrees
Scenario: SC-L005-2 distance_sq / nearest_index remains the retained fast default (opt-in upgrade, CL-10)
Scenario: SC-L005-3 ties resolve to the lower index (deterministic)
Scenario: SC-L005-4 an empty palette raises PaletteError
```

### Feature: Ordered/Bayer dithering (REQ-P3-LOGIC-006)
```gherkin
Scenario: SC-L006-1 PALETTE CONTAINMENT: ordered-dither output uses only target-palette colours
Scenario: SC-L006-2 the Bayer matrix size is BAYER_MATRIX_SIZE (from constants.py)
Scenario: SC-L006-3 ordered dithering is deterministic for a fixed input+palette+matrix
```

### Feature: Floyd–Steinberg dithering (REQ-P3-LOGIC-007)
```gherkin
Scenario: SC-L007-1 PALETTE CONTAINMENT: Floyd–Steinberg output is a subset of the target palette
Scenario: SC-L007-2 error is diffused 7/16,3/16,5/16,1/16 to the expected neighbours
Scenario: SC-L007-3 Floyd–Steinberg is deterministic for a fixed input+palette
```

### Feature: Hardware-palette reference data (REQ-P3-LOGIC-008)
```gherkin
Scenario: SC-L008-1 the NES palette exposes its fixed colour set (grounded by F9)
Scenario: SC-L008-2 the Game Boy palette exposes its 4 fixed shades
Scenario: SC-L008-3 the reference palettes are immutable / independent copies
```

### Feature: Palette-constraint mapping (REQ-P3-LOGIC-009)
```gherkin
Scenario: SC-L009-1 SUBSET: constraining a buffer to NES yields a colour set ⊆ the NES palette (acceptance-critical)
Scenario: SC-L009-2 SUBSET: constraining to Game Boy yields a colour set ⊆ the GB palette
Scenario: SC-L009-3 each pixel maps to its nearest hardware colour; deterministic
Scenario: SC-L009-4 the ΔE00 metric is selectable (opt-in) and still yields a ⊆ result (CL-11)
```

### Feature: Median-cut extraction (REQ-P3-LOGIC-010)
```gherkin
Scenario: SC-L010-1 ≤N: extracting from an image yields at most N colours (acceptance-critical)
Scenario: SC-L010-2 N defaults to PALETTE_EXTRACT_DEFAULT_N (from constants.py)
Scenario: SC-L010-3 an image with ≤N distinct colours returns exactly those colours
Scenario: SC-L010-4 median-cut is deterministic for a fixed input+N
```

### Feature: k-means extraction (REQ-P3-LOGIC-011)
```gherkin
Scenario: SC-L011-1 ≤N: k-means extraction yields at most N colours (acceptance-critical)
Scenario: SC-L011-2 seeded (KMEANS_SEED) so identical input+N+seed reproduces identical output (CL-8)
Scenario: SC-L011-3 k-means returns a Palette usable by the editor
```

### Feature: Palette analytics (REQ-P3-LOGIC-012)
```gherkin
Scenario: SC-L012-1 per-colour usage counts sum to the total pixel count
Scenario: SC-L012-2 an unused palette colour reports a count of 0
Scenario: SC-L012-3 counts are computed for both RGBA and indexed buffers
Scenario: SC-L012-4 the result is ordered deterministically (by count then index)
```

### Feature: Colour cycling (REQ-P3-LOGIC-013)
```gherkin
Scenario: SC-L013-1 cycling a palette-index range by 1 rotates only those indices
Scenario: SC-L013-2 ROUND-TRIP: cycling by len(range) returns the original palette
Scenario: SC-L013-3 forward then backward by the same k is identity
Scenario: SC-L013-4 a bad range raises PaletteError
```

### Feature: Palette swap / remap (REQ-P3-LOGIC-014)
```gherkin
Scenario: SC-L014-1 an index→index remap recolours an indexed buffer as specified
Scenario: SC-L014-2 REVERSIBILITY: the inverse remap restores the original buffer exactly
Scenario: SC-L014-3 a remap referencing an out-of-range index raises PaletteError
Scenario: SC-L014-4 remap is deterministic
```

### Feature: Favourites model (REQ-P3-LOGIC-015)
```gherkin
Scenario: SC-L015-1 add appends a new colour; adding an existing colour is a no-op (de-duplicated)
Scenario: SC-L015-2 remove and reorder (move) behave as specified; order preserved otherwise
Scenario: SC-L015-3 to_serializable / from_serializable round-trips the list (persistence substrate)
Scenario: SC-L015-4 a malformed colour raises the domain error
```

### Feature: Palette import/export encode/decode (REQ-P3-LOGIC-016)
```gherkin
Scenario: SC-L016-1 encode∘decode round-trips a palette for .gpl / .pal / hex
Scenario: SC-L016-2 a malformed palette file is rejected defensively (no eval/exec, Article VII)
Scenario: SC-L016-3 encode/decode is Qt-free and deterministic
```

### Feature: Reversible-command integration (REQ-P3-LOGIC-017)
```gherkin
Scenario: SC-L017-1 each Phase-3 mutating op produces a Command whose undo is its exact inverse
  Examples: palette-add | palette-remove | palette-reorder | palette-swap | cycle-commit | constraint | dither
Scenario: SC-L017-2 the op path imports zero Qt (verified by check_layering, Article I)
```

### Feature: Palette editor panel (REQ-P3-UI-001)
```gherkin
Scenario: SC-U001-1 add / remove / drag-drop reorder update the palette (binding to palette.move)
Scenario: SC-U001-2 each mutation is exactly ONE undoable command; undo restores the prior palette
Scenario: SC-U001-3 controls are tr()-wrapped, keyboard-reachable, correct in both themes
```

### Feature: Palette import/export UI (REQ-P3-UI-002)
```gherkin
Scenario: SC-U002-1 exporting then importing round-trips the palette (via palette_io)
Scenario: SC-U002-2 a malformed imported file surfaces a user-facing error without crashing
Scenario: SC-U002-3 actions are tr()-wrapped and keyboard-reachable (both themes)
```

### Feature: Colour hub — right-click menu at cursor (REQ-P3-UI-003, marquee S3)
```gherkin
Scenario: SC-U003-1 right-click on the canvas opens the colour hub anchored at the cursor (via the Phase-1 seam)
Scenario: SC-U003-2 the hub hosts both pick paths (Favourites + colour wheel)
Scenario: SC-U003-3 the hub is openable and navigable by keyboard; strings tr()-wrapped; both themes
```

### Feature: Colour hub — Favourites (REQ-P3-UI-004, S3a/S4)
```gherkin
Scenario: SC-U004-1 add-to-favourites stores the current colour; remove and reorder work
Scenario: SC-U004-2 clicking a favourite applies it to the active swatch (REQ-P3-UI-006)
Scenario: SC-U004-3 PERSISTENCE: a saved favourite is still present after an app restart (acceptance-critical, CL-4)
Scenario: SC-U004-4 the Favourites list is tr()-wrapped, keyboard-reachable, both themes
```

### Feature: Colour hub — RGB wheel + live harmonies (REQ-P3-UI-005, S3b/F9)
```gherkin
Scenario: SC-U005-1 picking on the wheel selects a colour and sets it as the pending pick
Scenario: SC-U005-2 LIVE HARMONIES: moving the wheel selection updates the harmony swatches on every move (acceptance-critical)
Scenario: SC-U005-3 the harmony swatches reflect the correct angles (complementary/analogous/triadic/split-complementary)
Scenario: SC-U005-4 shade/tint ramp swatches update with the selection
Scenario: SC-U005-5 the wheel + swatches are keyboard-reachable, tr()-wrapped, legible/contrast-correct in both themes
```

### Feature: Colour hub — apply + active swatch (REQ-P3-UI-006, S4)
```gherkin
Scenario: SC-U006-1 ACTIVE SWATCH: after a wheel pick the active swatch equals the picked colour (acceptance-critical, CL-3/CL-5)
Scenario: SC-U006-2 after picking a favourite the active swatch equals that favourite
Scenario: SC-U006-3 the next left-click paints the newly-picked active colour (S2 integration)
Scenario: SC-U006-4 saving to Favourites is an explicit action, distinct from applying (CL-5)
```

### Feature: Shade-ramp picker (REQ-P3-UI-007)
```gherkin
Scenario: SC-U007-1 the picker shows shade/tint/tone ramps of the base colour (from logic)
Scenario: SC-U007-2 picking a ramp step applies it / adds it to the palette
Scenario: SC-U007-3 the picker is tr()-wrapped, keyboard-reachable, both themes
```

### Feature: Dithering brushes (REQ-P3-UI-008)
```gherkin
Scenario: SC-U008-1 an ordered-dither stroke commits as ONE undoable command using only palette colours
Scenario: SC-U008-2 a Floyd–Steinberg stroke commits as ONE undoable command
Scenario: SC-U008-3 the dither tools are tr()-wrapped, keyboard-reachable, both themes
```

### Feature: Palette-constraint UI (REQ-P3-UI-009)
```gherkin
Scenario: SC-U009-1 applying the NES preset constrains the buffer/selection to NES as ONE undoable command
Scenario: SC-U009-2 applying the Game Boy preset constrains to GB (result ⊆ GB by behaviour)
Scenario: SC-U009-3 presets are tr()-wrapped, keyboard-reachable, both themes
```

### Feature: Auto-extract dialog (REQ-P3-UI-010)
```gherkin
Scenario: SC-U010-1 extracting from a chosen image loads a ≤N palette into the editor
Scenario: SC-U010-2 the N control defaults to PALETTE_EXTRACT_DEFAULT_N and bounds the result
Scenario: SC-U010-3 the median-cut / k-means choice is offered; dialog is tr()-wrapped, keyboard-reachable, both themes
```

### Feature: Palette analytics view (REQ-P3-UI-011)
```gherkin
Scenario: SC-U011-1 the view lists per-colour usage counts across the document (from logic)
Scenario: SC-U011-2 the view is sortable by count and read-only
Scenario: SC-U011-3 the view is tr()-wrapped, keyboard-reachable, legible in both themes
```

### Feature: Colour-cycling controls (REQ-P3-UI-012)
```gherkin
Scenario: SC-U012-1 selecting an index range and pressing play cycles that range on the canvas (non-destructive preview)
Scenario: SC-U012-2 pause stops cycling; the palette returns to its base state
Scenario: SC-U012-3 the controls are tr()-wrapped, keyboard-reachable, both themes
```

### Feature: Palette-swap UI (REQ-P3-UI-013)
```gherkin
Scenario: SC-U013-1 defining and applying an index remap recolours indexed art as ONE undoable command
Scenario: SC-U013-2 undo restores the pre-swap buffer exactly
Scenario: SC-U013-3 the swap UI is tr()-wrapped, keyboard-reachable, both themes
```

### Feature: Indexed-mode workflows (REQ-P3-UI-014)
```gherkin
Scenario: SC-U014-1 switching a document RGBA↔indexed is an undoable operation
Scenario: SC-U014-2 painting by palette index uses the active palette
Scenario: SC-U014-3 the mode controls are tr()-wrapped, keyboard-reachable, both themes
```

---

## 12. Exit / status

- Forward pre-implementation spec authored for ROADMAP **Phase 3 — Colour & Palette System
  (critical)**, including the marquee **S3/S4 colour hub** deferred from Phase 1.
- **31 REQ-IDs** (17 LOGIC + 14 UI); **16 clarification defaults** recorded (§10); **12
  new-constant / reference-data entries** flagged for AGT-03 (§9).
- Inherited forward traces realised: **`distance_sq`→perceptual matching** (REQ-P3-LOGIC-004/
  -005); **`color.blend_over` explicitly kept for Phase 4** (§1, §6, CL-16).
- R2 acceptance included: **harmony-angle correctness** (SC-L002-1..4), **CIEDE2000
  known-value** (SC-L004-1), **≤N quantization** (SC-L010-1/-011-1), **⊆ hardware palette**
  (SC-L009-1/-2), **wheel→active-swatch + Favourites persistence** (SC-U006-1, SC-U004-3),
  **live-harmony update on wheel move** (SC-U005-2).
- F9 (`docs/research-phase3-colour.md`) is a **plan-time** dependency for the algorithm
  internals — **not a requirement blocker**; every WHAT + acceptance is specifiable now
  (A2-D2 Branch B).
- Recommended slicing: **3A logic → 3B colour hub (marquee) → 3C palette workflows** — §8.
- No SUSPEND blocker.
- **STATUS: COMPLETED.**
