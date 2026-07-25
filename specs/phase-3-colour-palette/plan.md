# Plan — Phase 3: Colour & Palette System (critical)

| Field | Value |
| --- | --- |
| Feature | `phase-3-colour-palette` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VII, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 3 before any Phase-3 code exists |
| Over spec | `specs/phase-3-colour-palette/spec.md` (REQ-P3-LOGIC-001..017, REQ-P3-UI-001..014) |
| Layer scope | `pixelart_creator/logic/` (9 new modules) + `pixelart_creator/data/` (1 new module) + `pixelart_creator/ui/` (hub, editor, dialogs, controls) |
| Stack source | S8 (fixed) — no new technology; colour/quantize/dither/ΔE00/NES-GB algorithms grounded by The Researcher (`docs/research-phase3-colour.md`, F9 — **landed**) |
| ADRs filed | ADR-0003 (hardware-palette data placement + NES non-canonical decode); ADR-0004 (Favourites persistence store) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-3 spec — the
**critical** phase that lands the marquee **S3/S4 colour hub** deferred from Phase 1 plus the
full professional palette toolset. It maps every REQ to its S11 layer, **freezes the public
interface of the nine new `logic/` modules before implementation** so the 3B/3C UI slices bind
to a stable contract, rules on **constant + hardware-palette-data placement** (Article II /
ADR-0001), rules where **Favourites persist** (ADR-0004), directs **AGT-04 to validate ΔE00
against the Sharma et al. test-data pairs**, and specifies the reversible-op boundary so every
mutating operation is exactly one `QUndoCommand` with zero Qt in `logic/`. It is decomposed into
dependency-ordered work items in `tasks.md`.

No new stack/library/API is introduced (Decision PL-D1 → Branch B: the stack is fixed by S8; the
algorithms are **grounded, not invented** — F9 has landed, so no RESEARCH REQUEST is needed). The
`sdd-analyze` C1 gate is run over constitution/spec/plan/tasks as the pre-implement gate
(Article VIII).

### 1.1 Module naming — adopt the spec/traceability names (PL-D0)
The dispatch brief offered candidate module names (`harmony.py`, `color_diff.py`,
`palette_constraints.py`). **Ruling: adopt the module names already fixed by `spec.md` (§ header)
and `traceability.md` §1** — `color_theory.py`, `perceptual.py`, `dither.py`,
`hardware_palette.py`, `quantize.py`, `palette_analytics.py`, `palette_ops.py`, `favourites.py`,
`palette_io.py`. The traceability matrix is the evidence artifact `sdd-analyze`/AGT-06 consume;
deviating would create a cross-artifact REQ↔module drift finding (Article X). Colour-theory
(harmony + HSV/HSL + ramps) is one module; CIEDE2000 lives in `perceptual.py`; the NES/GB
constraint lives in `quantize.py` over the reference data in `hardware_palette.py`.

## 2. Stack decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language | Python 3.12+ | S8 |
| Colour value | Reuse Phase-1 `RGBA` tuple + `color.py` (`rgba`, `is_rgba`, `to_hex`/`from_hex`, `distance_sq`, `CHANNEL_MIN/MAX`) | S8, Phase-1, CL-2 |
| HSV/HSL geometry | Pure tuple maths (NOT `QColor`) — `logic/color_theory.py`; hue rotation `(h+Δ)%360`; tint/shade/tone HSV formulas | Research T1; CL-1/CL-2 |
| Perceptual metric | CIEDE2000 (ΔE00) via sRGB→XYZ(D65)→Lab; `kL=kC=kH=1.0` | Research T2 (Sharma et al.) |
| Quantization | median-cut (fast deterministic default) + k-means (seeded, higher-quality opt-in) | Research T3; CL-7/CL-8 |
| Hardware palettes | GB = fixed 4-shade DMG LUT; NES = referenced 64-entry decode (`2C02G_wiki.pal`) — no invented RGB | Research T4; ADR-0003 |
| Dithering | ordered Bayer (recurrence, 4×4 default) + Floyd–Steinberg 7/3/5/1 ÷16 | Research T5; CL-6 |
| Pixel storage | Reuse `PixelBuffer` (NumPy `uint8`, RGBA `(H,W,4)` / INDEXED `(H,W)`), vectorised (F7) | S8, F7, Phase-1 |
| Palette model | Reuse `Palette` (add/remove/`move`/`nearest_index`/`index_of`, 256-cap) | Phase-1, §7 |
| Favourites store | Qt-free model (`logic/favourites.py`) + Qt-free app-level JSON store (`data/favourites_io.py`); path resolved UI-side | ADR-0004; CL-4 |
| Reversibility | Reuse `history.PixelEdit` / `FunctionCommand` / `record_edit`; `ui/commands.py` wraps as `QUndoCommand` | S7, C1, F1, Phase-1 |
| Colour wheel (UI) | `QConicalGradient` (hue) + `QRadialGradient` white→transparent (saturation) + value slider; `QColor.fromHsv` | Research T1; UI-only (S11) |
| Testing | pytest + Hypothesis (logic), pytest-qt both themes (UI), headless | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-3 logic decision places Qt in `logic/` or `data/` (NFR-1); the wheel widget's `QColor`
HSV use is confined to `ui/` (CL-2).

## 3. Architecture — module → layer map (S11)

All nine new source modules live in `logic/` with **zero Qt imports** (Article I); one new
module lives in `data/` (Qt-free I/O); the UI modules live in `ui/` and are the only Qt consumers.
Dependency direction is one-way (`ui/` → `logic/`+`data/`) and acyclic (verified §11). The Qt undo
bridge for every new op is `ui/commands.py` (the sole Qt file outside `ui/`, S11).

### 3.1 New `logic/` modules (Slice 3A — pure, zero Qt)

| Module | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- |
| `logic/color_theory.py` | RGB↔HSV/HSL conversion; harmony sets (complementary/analogous/triadic/split-comp) by hue rotation; shade/tint/tone ramps. | `color`, `constants` | 001, 002, 003 |
| `logic/perceptual.py` | sRGB→Lab; ΔE00 (CIEDE2000); perceptual nearest-palette-index (opt-in over `distance_sq`). | `color`, `palette`, `constants` | 004, 005 |
| `logic/dither.py` | Ordered/Bayer + Floyd–Steinberg mapping a source region onto a target palette; reversible builder. | `color`, `palette`, `pixel_buffer`, `history`, `constants` | 006, 007 |
| `logic/hardware_palette.py` | NES (64-entry decode) + Game Boy (4-shade DMG) reference palettes as independent `Palette` copies. | `color`, `palette` | 008 |
| `logic/quantize.py` | Palette-constraint (map buffer onto fixed palette; ⊆) + auto-extract median-cut / k-means (≤N); reversible constraint builder. | `color`, `palette`, `pixel_buffer`, `perceptual`, `history`, `constants` | 009, 010, 011 |
| `logic/palette_analytics.py` | Per-colour / per-index usage counts across a buffer/document (read-only, vectorised). | `color`, `palette`, `pixel_buffer`, `document` | 012 |
| `logic/palette_ops.py` | Colour cycling (rotate an index range) + palette swap/remap; reversible builders. | `color`, `palette`, `pixel_buffer`, `history`, `constants` | 013, 014 |
| `logic/favourites.py` | Persisted, ordered, de-duplicated `Favourites` model + JSON `to/from_serializable`; soft cap. | `color`, `constants` | 015 |
| `logic/palette_io.py` | Encode/decode `Palette` to/from `.gpl` / `.pal` / hex-plain (defensive, Qt-free). | `color`, `palette`, `constants` | 016 |

Reversible-op integration (REQ-P3-LOGIC-017) is a cross-cutting concern realised **inside**
`dither.py`, `quantize.py`, `palette_ops.py` (each mutating op has a companion returning a
`history.Command`), not a tenth module. `constants.py` stays a leaf. **PL-D6 — perceptual match
placement:** `nearest_index_perceptual(palette, color)` is a **free function in `perceptual.py`**
(taking a `Palette`), NOT a method added to `palette.py`; adding it to `palette.py` would force
`palette → perceptual` and cycle with `perceptual → palette`. This keeps `distance_sq` /
`palette.nearest_index` the retained fast default untouched (CL-10) and avoids the cycle. No edits
to `color.py` / `palette.py` are required — all Phase-3 capability is **additive** in new modules.

### 3.2 New `data/` module (Slice 3A — Qt-free I/O)

| Module | Responsibility | Depends on | REQ |
| --- | --- | --- | --- |
| `data/favourites_io.py` | Load/save a `Favourites` model to a portable JSON file (pathlib; defensive parse, Article VII); mirrors `project_io.py`. Path is supplied by the caller. | `logic/favourites`, `logic/color`, stdlib `json`/`pathlib` | 015 (persistence substrate), UI-004 |

### 3.3 New `ui/` modules (Slices 3B/3C — PySide6; binds to 3A + `data/favourites_io`)

| Module (indicative) | Responsibility | Binds to (logic/data) | REQ | Slice |
| --- | --- | --- | --- | --- |
| `ui/colour_hub_menu.py` | Cursor-anchored right-click hub (into the Phase-1 `Canvas_View.set_menu_hook` seam); hosts Favourites + wheel; picked colour → active swatch; explicit add-to-favourites. | `favourites`, `color_theory`, `data/favourites_io`, canvas seam | UI-003, 004, 006 | 3B |
| `ui/colour_wheel_widget.py` | Canva-style RGB wheel (`QConicalGradient`+`QRadialGradient`+value slider) with live harmony + shade/tint swatches. | `color_theory` (harmony/ramps) | UI-005 | 3B |
| `ui/palette_editor_panel.py` | Extends Phase-1 palette panel: add/remove/drag-drop reorder + import/export actions. | `palette.move`, `palette_io` | UI-001, 002 | 3C |
| `ui/shade_ramp_picker.py` | Shows shade/tint/tone ramps of a base colour; pick a step → apply/add. | `color_theory` ramps | UI-007 | 3C |
| `ui/tools/dither_tool.py` | Ordered/Bayer + Floyd–Steinberg dithering brushes; stroke commits as one command. | `dither` | UI-008 | 3C |
| `ui/palette_constraint_panel.py` | NES / Game Boy presets constrain buffer/selection as one command. | `hardware_palette`, `quantize` | UI-009 | 3C |
| `ui/extract_palette_dialog.py` | Extract ≤N palette from an image (N control + median-cut/k-means choice). | `quantize` | UI-010 | 3C |
| `ui/palette_analytics_view.py` | Read-only, sortable per-colour usage view. | `palette_analytics` | UI-011 | 3C |
| `ui/colour_cycling_panel.py` | Select index range + play/pause non-destructive cycling preview. | `palette_ops` cycle | UI-012 | 3C |
| `ui/palette_swap_dialog.py` | Define + apply an index remap as one command. | `palette_ops` swap | UI-013 | 3C |
| `ui/main_window.py` (extend) | Indexed-mode RGBA↔indexed switch + paint-by-index; wires the hub/editor/panels. | `document`, `palette`, hub | UI-014 | 3C |
| `ui/commands.py` (extend) | One `QUndoCommand` wrapper per new mutating op (delegates to `history.Command`; no domain math). | `history` + all 3A ops | LOGIC-017; UI reversibility | 3B/3C |

## 4. Slicing (spec §8, ratified)

- **Slice 3A — Colour & palette LOGIC** (`REQ-P3-LOGIC-001..017`). All nine Qt-free `logic/`
  modules + `data/favourites_io.py` + new constants (§8) + new exceptions + reversible builders +
  pytest/Hypothesis coverage (incl. the **Sharma ΔE00 dataset** validation, §7). **Ships first** —
  it is the substrate every UI control binds to. **F9 has landed** (`docs/research-phase3-colour.md`,
  COMPLETED), so the harmony (-002), wheel-geometry (-001), CIEDE2000 (-004), constraint (-009) and
  extraction (-010/-011) items are **no longer gated**; the un-gated remainder (ramps, dither,
  analytics, cycling, swap, favourites, import/export) proceeds in parallel after the constants task.
- **Slice 3B — Colour hub UI (marquee S3/S4)** (`REQ-P3-UI-003..006`). The cursor-anchored
  right-click hub into the Phase-1 seam + persisted Favourites + the Canva-style wheel with live
  harmonies + immediate-apply/active-swatch + `ui/commands.py` wrappers. **Depends on** 3A
  (`color_theory`, `favourites`), `data/favourites_io`, and a **stable Phase-1 UI substrate** (the
  `Canvas_View.set_menu_hook`/`rightClicked` seam — confirmed present; palette panel; `ui/commands.py`;
  `ui/i18n.py`). Shipped as its own slice given it is the highest-value Phase-1 deferral.
- **Slice 3C — Palette workflows UI** (`REQ-P3-UI-001, -002, -007..-014`). Palette editor +
  import/export, shade-ramp picker, dither brushes, constraint presets, extract dialog, analytics
  view, cycling controls, swap dialog, indexed-mode workflows + pytest-qt (both themes) + i18n.
  **Depends on** 3A.

## 5. Grounding-derived pins (research F9 → AGT-03 acceptance)

F9 has **landed**, so — unlike Phase-2 RotSprite — the algorithm internals are published, not
unpinned. The following values are fixed from the research and become AGT-03 acceptance. They are
**intrinsic** to the referenced standards/algorithms (per ADR-0001 they stay **local** to their
module, NOT in `constants.py`); only the *tuning knobs* named in §8 go to `constants.py`.

| Concern | Fixed by research | Placement |
| --- | --- | --- |
| Harmony hue rotations | complementary +180°, analogous ±30°, triadic ±120° (=+120/+240), split-comp ±150° (=+150/+210); S/V preserved, hue mod 360 | **Tuning knobs → `constants.py`** (`HARMONY_*_DEG`, §8; a scheme could reasonably re-tune neighbour offsets) |
| Tint/shade/tone HSV formulas | shade `V·(1−t)`; tint `V+(1−V)t & S·(1−t)`; tone `S·(1−t)`; `t=k/(N−1)` | Intrinsic → local in `color_theory.py` (only `RAMP_STEP_COUNT` is tuning) |
| sRGB→Lab + ΔE00 constants | D65 white `(95.047,100,108.883)`; sRGB linearise `0.04045/12.92/1.055/2.4`; XYZ matrix; ΔE00 magic terms (`0.17/0.24/0.32/0.20`, `25⁷`, `6°/30°/275°/25°/63°`) | **Intrinsic (CIEDE2000/CIELAB standard) → local in `perceptual.py`** (ADR-0001). Only `CIEDE2000_KL/KC/KH` (parametric weights) → `constants.py` |
| Bayer matrices + FS coefficients | 4×4 Bayer via recurrence; FS 7/16,3/16,5/16,1/16 | **Intrinsic (algorithm) → local in `dither.py`** (ADR-0001). Only `BAYER_MATRIX_SIZE` (which size) → `constants.py` |
| NES / Game Boy palette RGB | GB DMG LUT `#9BBC0F/#8BAC0F/#306230/#0F380F`; NES = 64-entry `2C02G_wiki.pal` decode (no canonical RGB) | **Reference data → module-local in `hardware_palette.py`** (ADR-0003) |
| median-cut / k-means | greatest-range split at median (mean box colour); k-means++ seed, Lab clustering | Intrinsic → local in `quantize.py` (only `PALETTE_EXTRACT_DEFAULT_N`, `KMEANS_SEED` → `constants.py`) |

## 6. Interface contracts (frozen BEFORE implementation — `interface-contract`)

The public surface of each new `logic/`+`data/` module is frozen here so Slices 3B/3C bind to a
stable API. STRUCTURE.md carries the same surface (§9). New exceptions subclass `ValueError`
(Phase-1 convention: `ColorError`, `PaletteError`, `PixelBufferError`, `DocumentError`); reuse
`PaletteError` for palette-index-bound ops (cycling range, swap remap, empty-palette match).

### 6.1 `logic/color_theory.py` (REQ-P3-LOGIC-001, -002, -003)
```python
class ColorTheoryError(ValueError): ...

# conversions — pure tuple maths, NOT QColor (CL-2); alpha preserved; malformed -> ColorTheoryError
def rgba_to_hsv(color: RGBA) -> Tuple[float, float, float, int]: ...   # (h∈[0,360), s∈[0,1], v∈[0,1], a∈0..255)
def hsv_to_rgba(h: float, s: float, v: float, a: int = 255) -> RGBA: ...
def rgba_to_hsl(color: RGBA) -> Tuple[float, float, float, int]: ...   # (h, s, l, a)
def hsl_to_rgba(h: float, s: float, l: float, a: int = 255) -> RGBA: ...
    # RGB->HSV->RGB is identity for representable colours (CL-1, SC-L001-1); primaries R=0°/G=120°/B=240°

# harmonies — hue rotation by the HARMONY_*_DEG constants; S/V preserved; hue mod 360; alpha preserved
def complementary(color: RGBA) -> RGBA: ...                            # +HARMONY_COMPLEMENTARY_DEG (180)
def analogous(color: RGBA) -> Tuple[RGBA, RGBA]: ...                   # ±HARMONY_ANALOGOUS_DEG (30)
def triadic(color: RGBA) -> Tuple[RGBA, RGBA]: ...                     # ±HARMONY_TRIADIC_DEG (120)
def split_complementary(color: RGBA) -> Tuple[RGBA, RGBA]: ...         # ±HARMONY_SPLIT_COMPLEMENTARY_DEG (150)
def harmony(color: RGBA, scheme: str) -> List[RGBA]: ...               # 'complementary'|'analogous'|'triadic'|'split'
    # deterministic (SC-L002-6); bad scheme -> ColorTheoryError

# ramps — RAMP_STEP_COUNT steps, include the base colour, monotonic in the driving channel, deterministic
def shade_ramp(color: RGBA, steps: int = RAMP_STEP_COUNT) -> List[RGBA]: ...   # toward black (V decreasing)
def tint_ramp(color: RGBA, steps: int = RAMP_STEP_COUNT) -> List[RGBA]: ...    # toward white
def tone_ramp(color: RGBA, steps: int = RAMP_STEP_COUNT) -> List[RGBA]: ...    # toward grey (S decreasing)
```

### 6.2 `logic/perceptual.py` (REQ-P3-LOGIC-004, -005)
```python
def rgba_to_lab(color: RGBA) -> Tuple[float, float, float]: ...        # sRGB->XYZ(D65)->L*a*b* (constants local, ADR-0001)
def delta_e_2000(a: RGBA, b: RGBA, *,
                 kl: float = CIEDE2000_KL, kc: float = CIEDE2000_KC, kh: float = CIEDE2000_KH) -> float: ...
    # ΔE00; symmetric (SC-L004-3); Δ(x,x)=0 (SC-L004-2); matches Sharma pairs within tolerance (SC-L004-1, §7)
def nearest_index_perceptual(palette: Palette, color: RGBA) -> int: ...
    # ranks by ΔE00; ties -> lower index (P2, SC-L005-3); empty palette -> PaletteError (SC-L005-4);
    # opt-in upgrade path — palette.nearest_index (distance_sq) remains the retained default (CL-10, PL-D6)
```

### 6.3 `logic/dither.py` (REQ-P3-LOGIC-006, -007)
```python
class DitherError(ValueError): ...

def ordered_dither(source: PixelBuffer, palette: Palette, *, matrix_size: int = BAYER_MATRIX_SIZE) -> PixelBuffer: ...
    # Bayer threshold map (matrix values intrinsic-local); output colour set ⊆ palette (SC-L006-1); deterministic
def floyd_steinberg(source: PixelBuffer, palette: Palette) -> PixelBuffer: ...
    # 7/3/5/1 ÷16 forward diffusion (intrinsic-local); output ⊆ palette (SC-L007-1); deterministic
def make_dither_command(document_or_buffer_ref, palette: Palette, mode: str,
                        mask: Optional["SelectionMask"] = None) -> "history.Command": ...
    # PixelEdit of changed coords (reversible); mode 'ordered'|'floyd_steinberg'; empty palette -> PaletteError;
    # bad mode -> DitherError
```

### 6.4 `logic/hardware_palette.py` (REQ-P3-LOGIC-008)
```python
def nes_palette() -> Palette: ...        # 64-entry decode (2C02G_wiki.pal, NESdev); NEW independent copy each call
def game_boy_palette() -> Palette: ...   # 4-shade DMG LUT #9BBC0F/#8BAC0F/#306230/#0F380F; NEW independent copy
# module-local immutable reference tuples (ADR-0003): _NES_COLORS, _GAME_BOY_COLORS — never mutated (SC-L008-3)
```

### 6.5 `logic/quantize.py` (REQ-P3-LOGIC-009, -010, -011)
```python
class QuantizeError(ValueError): ...

def constrain_to_palette(source: PixelBuffer, palette: Palette, *, metric: str = "distance_sq") -> PixelBuffer: ...
    # each pixel -> nearest palette colour; metric 'distance_sq' (default) | 'ciede2000' (opt-in, delegates to
    # perceptual, CL-11); output colour set ⊆ palette (SC-L009-1/-2, acceptance-critical); deterministic;
    # empty palette -> PaletteError; bad metric -> QuantizeError
def median_cut(source: PixelBuffer, n: int = PALETTE_EXTRACT_DEFAULT_N) -> Palette: ...
    # ≤n colours (SC-L010-1, acceptance-critical); deterministic for fixed (source, n); n<=0 -> QuantizeError
def kmeans(source: PixelBuffer, n: int = PALETTE_EXTRACT_DEFAULT_N, *, seed: int = KMEANS_SEED) -> Palette: ...
    # ≤n colours (SC-L011-1); seeded k-means++ -> identical (source,n,seed) reproduces identical output (CL-8)
def make_constraint_command(document_or_buffer_ref, palette: Palette, *,
                            metric: str = "distance_sq", mask: Optional["SelectionMask"] = None) -> "history.Command": ...
    # PixelEdit of changed coords (reversible)
```

### 6.6 `logic/palette_analytics.py` (REQ-P3-LOGIC-012)
```python
def color_usage_counts(buffer: PixelBuffer) -> List[Tuple[RGBA, int]]: ...
    # per-colour pixel counts, ordered by (-count, colour); counts sum to total pixels (SC-L012-1); vectorised (F7)
def index_usage_counts(buffer: PixelBuffer, palette: Palette) -> List[Tuple[int, int]]: ...
    # per-index counts for an INDEXED buffer; unused index -> 0 (SC-L012-2); ordered by (-count, index)
def document_usage_counts(document: Document, palette: Optional[Palette] = None) -> List[Tuple[object, int]]: ...
    # aggregates across all layers/frames; read-only, no mutation; deterministic (SC-L012-4)
```

### 6.7 `logic/palette_ops.py` (REQ-P3-LOGIC-013, -014)
```python
def cycle_palette(palette: Palette, start: int, end: int, step: int) -> Palette: ...
    # rotate colours within [start,end] by step; cycling by len(range) == identity (SC-L013-2); bad range -> PaletteError
def swap_indices(buffer: PixelBuffer, mapping: Mapping[int, int]) -> PixelBuffer: ...
    # index->index remap of an INDEXED buffer; out-of-range index -> PaletteError (SC-L014-3); deterministic
def remap_colors(buffer: PixelBuffer, mapping: Mapping[RGBA, RGBA]) -> PixelBuffer: ...  # RGBA color->color remap (CL-14)
def make_cycle_command(document_or_buffer_ref, start: int, end: int, step: int) -> "history.Command": ...  # commit preview
def make_swap_command(document_or_buffer_ref, mapping: Mapping[int, int],
                      mask: Optional["SelectionMask"] = None) -> "history.Command": ...
    # PixelEdit; inverse mapping restores the original exactly (SC-L014-2, reversibility)
```

### 6.8 `logic/favourites.py` (REQ-P3-LOGIC-015)
```python
class FavouritesError(ValueError): ...

class Favourites:
    def __init__(self, colors: Optional[Iterable[RGBA]] = None, *, max_size: int = FAVOURITES_MAX) -> None: ...
    def add(self, color: RGBA) -> None: ...          # append if absent; no-op if present (de-dup, SC-L015-1);
                                                     # exceeding max_size -> FavouritesError (defensive, Art. VII)
    def remove(self, color: RGBA) -> None: ...       # absent -> FavouritesError
    def move(self, from_index: int, to_index: int) -> None: ...   # reorder (SC-L015-2)
    def colors(self) -> List[RGBA]: ...
    def __contains__(self, color: object) -> bool: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[RGBA]: ...
    def __eq__(self, other: object) -> bool: ...     # value equality
    def to_serializable(self) -> List[str]: ...      # list of #RRGGBBAA hex (JSON-safe, SC-L015-3)
    @classmethod
    def from_serializable(cls, data: object) -> "Favourites": ...   # malformed/bad colour -> FavouritesError (SC-L015-4)
```

### 6.9 `logic/palette_io.py` (REQ-P3-LOGIC-016)
```python
class PaletteIOError(ValueError): ...   # AGT-01 addition (spec §9 exception list was illustrative)

def encode(palette: Palette, fmt: str) -> str: ...          # fmt 'gpl'|'pal'|'hex'; reuses color.to_hex
def decode(text: str, fmt: str) -> Palette: ...             # defensive parse (no eval/exec, Art. VII); malformed -> PaletteIOError
    # encode∘decode round-trips a palette for supported formats (SC-L016-1); Qt-free & deterministic (SC-L016-3)
```

### 6.10 `data/favourites_io.py` (REQ-P3-LOGIC-015 persistence substrate; ADR-0004)
```python
class FavouritesIOError(ValueError): ...

def save_favourites(path: "os.PathLike[str] | str", favourites: "Favourites") -> None: ...
    # writes favourites.to_serializable() as JSON to `path` (pathlib, portable — Art. VII, path_portability_check)
def load_favourites(path: "os.PathLike[str] | str") -> "Favourites": ...
    # reads + validates JSON -> Favourites.from_serializable; missing file -> empty Favourites; malformed -> FavouritesIOError
```
The **app-config directory is resolved UI-side** (via `QStandardPaths.AppConfigLocation`) and passed
in as a `Path`, keeping `data/` Qt-free (ADR-0004). Not stored on `.pixproj` (per-document) nor in
QSettings — Favourites are an app-level cross-session preference (US-2, CL-4).

## 7. CIEDE2000 validation requirement (SC-L004-1, acceptance-critical)

The research report flagged the **Sharma et al. PDF was corrupted on fetch** and the ΔE00
equations were cross-checked via Wikipedia. Therefore the implementation **must** be validated
against the authoritative reference: **AGT-04 embeds the published Sharma et al. CIEDE2000
supplementary test-data pairs** (the 34 Lab/ΔE00 pairs from
`https://www.ece.rochester.edu/~gsharma/ciede2000/`) as a test fixture in
`tests/logic/test_perceptual.py` and asserts `delta_e_2000` (fed the paired Lab values, and the
sRGB→Lab pipeline separately) matches each published ΔE00 within a documented tolerance
(`1e-4`). This is the guard against the known implementation traps (hue-mean quadrant, the `G`
term). No ship of `perceptual.py` without this dataset test passing (NFR-5).

## 8. Constants & data placement (Article II / S12 / ADR-0001) — AGT-01 rulings

New tuning values go to `logic/constants.py` with a source-citation comment, imported by name
(NFR-6). `constants.py` stays a leaf. Intrinsic standard/algorithm constants stay local per
ADR-0001 (§5).

| Constant | **Ruled value** | Classification / ruling |
| --- | --- | --- |
| `HARMONY_COMPLEMENTARY_DEG` | `180` | Tuning → `constants.py` (F9/S3b) |
| `HARMONY_ANALOGOUS_DEG` | `30` | Tuning → `constants.py` |
| `HARMONY_TRIADIC_DEG` | `120` | Tuning → `constants.py` |
| `HARMONY_SPLIT_COMPLEMENTARY_DEG` | `150` | Tuning → `constants.py` |
| `RAMP_STEP_COUNT` | **`5`** (confirmed) | Tuning → `constants.py`. Aseprite ramp norm; odd count keeps the base centred |
| `BAYER_MATRIX_SIZE` | `4` | Tuning → `constants.py` (which Bayer size; the matrix *values* are intrinsic-local, §5) |
| `PALETTE_EXTRACT_DEFAULT_N` | **`16`** (confirmed) | Tuning → `constants.py`. Common 4-bit palette default |
| `CIEDE2000_KL` / `CIEDE2000_KC` / `CIEDE2000_KH` | `1.0` / `1.0` / `1.0` | Tuning (parametric weights) → `constants.py`. The ΔE00 formula magic numbers are intrinsic-local (§5, ADR-0001) |
| `KMEANS_SEED` | **`0`** (confirmed) | Tuning → `constants.py` (P2 reproducibility, CL-8) |
| `CYCLE_DEFAULT_FPS` | **`10`** (confirmed) | Tuning → `constants.py`. UI-driven rate, but a numeric value lives in `constants.py` (Article II); consumed by `ui/colour_cycling_panel.py` |
| `FAVOURITES_MAX` | **`64`** (confirmed — adopt) | Tuning → `constants.py`. Soft cap bounds the persisted list (defensive, Article VII); 64 suits a hub swatch grid |
| **NES / Game Boy palette tables** | **module-local in `hardware_palette.py`** | **Reference DATA, not a tuning scalar → NOT `constants.py`** (ADR-0003). Mirrors the Phase-2 `SymmetryAxis` PL-D3 call and ADR-0001 (`constants.py` = tuning scalars only) |

**New domain exceptions** (all subclass `ValueError`): `ColorTheoryError` (`color_theory.py`),
`DitherError` (`dither.py`), `QuantizeError` (`quantize.py`), `FavouritesError` (`favourites.py`),
`PaletteIOError` (`palette_io.py`), `FavouritesIOError` (`data/favourites_io.py`). **Reuse
`PaletteError`** for palette-index-bound ops: empty-palette perceptual/constraint match, cycling
range, swap remap out-of-range.

## 9. STRUCTURE.md update (incl. FU-10)

STRUCTURE.md is updated in this session to (a) add the nine new `logic/` modules + one `data/`
module as a **"Phase-3 colour & palette — PLANNED (Slice 3A)"** block with the §6 public surface;
(b) add the Phase-3 `ui/` modules under a **PLANNED (Slices 3B/3C)** block; and (c) **per FU-10**,
promote the Phase-1 and Phase-2 `ui/` blocks to reflect the modules now on disk — including the two
helper bases `ui/tools/shape_base.py` (`ShapeTool`) and `ui/tools/selection_base.py` (`SelectionTool`)
that were not previously listed. AGT-01 maintains it via the `interface-contract` skill.

## 10. Reversible-op boundary (REQ-P3-LOGIC-017, S7/C1/F1) & performance (Article VI)

**Reversibility.** Every Phase-3 mutating op is built as a Phase-1 reversible `history.Command`
in `logic/` so `ui/commands.py` wraps it in **one** `QUndoCommand` (NFR-3; Qt-free path verified
by `check_layering`, SC-L017-2):

| Op | Command kind | Rationale |
| --- | --- | --- |
| palette add/remove/reorder (editor); colour-cycling commit; palette swap/remap; dither stroke; constraint apply | `PixelEdit` (buffer) / `FunctionCommand` (palette-object edits) | per-pixel `(x,y,old,new)` diff is exact & minimal for buffer edits; palette-list edits capture the prior palette |

Invariant `apply ∘ undo = identity` per op (SC-L017-1, SC-U001-2, SC-U008-1/-2, SC-U009-1,
SC-U013-2). The logic returns a `Command`; `ui/commands.py` supplies only the Qt shell +
dirty-rect signalling (no domain math), exactly as the Phase-1 `PaintCommand` bridge does.

**Performance (NFR-9).** The live-harmony wheel update, dither preview, and analytics over the 8K
buffer must hold `FRAME_BUDGET_MS = 16`. Analytics over 33 M pixels is **vectorised** (NumPy, F7 —
never a Python per-pixel loop). If a `perf_profile` measurement goes over budget, AGT-10 issues a
directive AGT-05 implements; the budget is never relaxed (Article VI §2). The resident buffer is
never culled (Article VI §3). Task T-perf is conditional on a new over-budget render path.

## 11. Verification (this session)

- `python scripts/check_layering.py` → `check_layering: clean (17 modules).`, exit **0**.
- `python scripts/check_cycles.py` → `check_cycles: no cycles (43 modules).`, exit **0**.

No Phase-3 code exists yet, so both are expected clean; they re-run at the 3A slice boundary
(task T-gate) after the logic modules land, confirming the nine new `logic/` modules +
`data/favourites_io.py` import zero Qt and add no cycle (Decision A1-D3; script exit 2 → BLOCKED,
A1-E3). The `perceptual → palette` / `quantize → perceptual` edges are one-way; PL-D6 keeps
`palette.py` free of any `perceptual` import so no cycle is introduced.

## 12. Exit / status

- plan.md authored over the approved spec; nine new `logic/` modules + one `data/` module + the
  Phase-3 `ui/` modules mapped to their S11 layers; interface contracts frozen (§6); research-derived
  values pinned (§5); constant + hardware-palette-data + Favourites-store placements ruled (§8, §6.10);
  ΔE00-vs-Sharma validation directed (§7); reversible-op boundary specified (§10).
- Stack fully grounded (F9 landed — no RESEARCH REQUEST needed).
- Layering/cycle gates green (§11).
- Slicing ratified: **3A logic → 3B colour hub (marquee S3/S4) → 3C palette workflows**; F9 ungated.
- ADR-0003 (hardware-palette data placement) + ADR-0004 (Favourites persistence) filed.
- `sdd-analyze` C1 gate run over constitution/spec/plan/tasks (see analyze report).
- **STATUS: COMPLETED.**
