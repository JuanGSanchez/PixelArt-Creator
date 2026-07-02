# Plan — Phase 4: Layer & Canvas System

| Field | Value |
| --- | --- |
| Feature | `phase-4-layer-canvas` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VII, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 4 before any `logic/blend.py` or layer UI exists |
| Over spec | `specs/phase-4-layer-canvas/spec.md` (REQ-P4-LOGIC-001..015, REQ-P4-UI-001..018) + this plan **allocates** REQ-P4-DATA-001..005 (DEP-3) |
| Layer scope | `pixelart_creator/logic/` (new `blend.py`; extend `document.py`, `constants.py`) + `pixelart_creator/data/` (extend `project_io.py`) + `pixelart_creator/ui/` (layer panel, canvas compositing, tabs, `commands.py`) |
| Stack source | S8 (fixed) — no new technology; the 12 blend-mode formulas are **grounded** by The Researcher (`docs/research-blend-modes.md` — W3C Compositing & Blending Level 1, **landed**) |
| ADRs filed | ADR-0005 (blend working space + alpha convention); ADR-0006 (`.pixproj` schema v2 + back-compat load); ADR-0007 (dirty-rect region-scoped recomposite + cached group buffers) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-4 spec — the
**non-destructive editing** milestone that turns the shipped `Document → frames → layers → buffer`
tree into a real layer model (blend modes, opacity/visibility/lock as reversible edits, groups,
masks, reference and minimal smart layers), a canvas that renders the *composited* stack, and
multiple isolated artboard tabs. It maps every REQ to its S11 layer, **freezes the public interface
of `logic/blend.py` (the compositor) and the `document.py` layer-op API before implementation** so
the DATA and UI slices bind to a stable contract, **pins the alpha convention** from the research,
**allocates the DEP-3 `REQ-P4-DATA-*` IDs** and the `.pixproj` schema-v2 decision, rules constant
placement (Article II), and commits the architecture to a **dirty-rect region-scoped recomposite**
(DEP-2) that AGT-10 profiles and tunes. It is decomposed into dependency-ordered work items in
`tasks.md`.

No new stack/library/API is introduced (Decision PL-D1 → Branch B: the stack is fixed by S8; the
blend formulas are **grounded, not invented** — `docs/research-blend-modes.md` has landed, so no
RESEARCH REQUEST is needed). The `sdd-analyze` C1 gate is run over constitution/spec/plan/tasks as
the pre-implement gate (Article VIII; see `analyze-report.md`).

## 2. Stack decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language | Python 3.12+ | S8 |
| Blend math | W3C *Compositing and Blending Level 1* separable formulas; work in **float32 normalised 0..1, straight (non-premultiplied) alpha**; `uint8→float` on entry (`/255`), `float→uint8` on exit (`clip(round(x*255),0,255)`) | `docs/research-blend-modes.md` §0/§1/§3; ADR-0005 |
| Normal mode | Delegates to the shipped `color.blend_over` (FU-3) — not re-derived | REQ-P4-LOGIC-003; research §1 (normal) |
| Blend-mode vocabulary | `BlendMode` enum (12 members = W3C separable set) in `logic/blend.py` (enumerated vocabulary, not a tuning scalar) | spec §4/BF-2; CL-1 |
| Compositor | Pure vectorised NumPy stack flattener in `logic/blend.py`; walks the layer tree structurally (no `document` import — PL-D2) | REQ-P4-LOGIC-004; F7 |
| Layer tree | Reuse + extend `document.py`: `Layer` gains `blend_mode`/`mask`/`reference`/`smart_source`; new `LayerGroup` node; ops return `history.Command` | spec §2; Phase-1 substrate |
| Pixel storage | Reuse `PixelBuffer` (NumPy `uint8`, RGBA `(H,W,4)` / INDEXED `(H,W)`), vectorised (F7) | S8, F7, Phase-1 |
| Mask model | A same-geometry `PixelBuffer` whose alpha/greyscale value modulates layer alpha (CL-10) | REQ-P4-LOGIC-012 |
| Reversibility | Reuse `history.Command` / `FunctionCommand` / `PixelEdit`; `ui/commands.py` wraps each as **one** `QUndoCommand` | S7, C1, F1, Phase-1 |
| Persistence | Extend `data/project_io.py`; bump `FORMAT_VERSION` to **2**; defensive validated load; **read v1 back-compat** | ADR-0006; Article VII |
| Recomposite perf | **Dirty-rect region-scoped composite** + cached flattened group buffers; AGT-10 profiles + tunes viewport | ADR-0007; DEP-2; Article VI |
| Canvas | Composite drawn as one whole-buffer pixmap refreshed per dirty-rect (BF-1 → single-item, tiling deferred to AGT-10 tuning) | REQ-P4-UI-012; BF-1 |
| Multi-canvas | Extend the Phase-1 document-tab system (REQ-P1-UI-020); per-tab layer tree + `QUndoStack` + composite | REQ-P4-UI-014; CL-15 |
| Testing | pytest + Hypothesis (logic/data), pytest-qt both themes (UI), headless | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-4 logic/data decision places Qt in `logic/` or `data/` (Article I). `QColor` HSV / Qt
drag-drop live only in `ui/`; the sole Qt file outside `ui/` remains `ui/commands.py`.

## 3. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`) and acyclic (verified §11). The Qt undo
bridge for every layer op is `ui/commands.py`.

### 3.1 New / extended `logic/` modules (Slice 4A — pure, zero Qt)

| Module | Change | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- | --- |
| `logic/constants.py` | extend | Add `DEFAULT_LAYER_OPACITY`, `MAX_LAYERS_PER_FRAME`, `MAX_GROUP_NESTING_DEPTH` (leaf; no imports). | — | LOGIC-015 |
| `logic/blend.py` | **new** | `BlendMode` enum (12); per-mode separable `B(Cb,Cs)`; `blend_pixels`/`blend_arrays` (NORMAL→`color.blend_over`); `composite_stack` flattening an ordered node list honouring visibility/opacity/order/blend-mode/mask, recursing into groups, region-scoped. **Never imports `document`** (PL-D2). | `color`, `constants`, numpy | LOGIC-001..007, 011 (compositor side), 012 (compositor side) |
| `logic/document.py` | extend | `Layer` gains `blend_mode`/`mask`/`reference`/`smart_source`; new `LayerGroup` node (children + own opacity/visible/locked/blend_mode/mask); reversible attribute + structural + group/mask/reference/smart ops returning `history.Command`; lock/reference pixel-mutation guard; `MAX_LAYERS_PER_FRAME`/`MAX_GROUP_NESTING_DEPTH` bounds. | `blend` (BlendMode), `history`, `palette`, `pixel_buffer`, `constants` | LOGIC-008..015, 011 (node), 012 (node) |

`constants.py` stays a leaf. Blend-formula magic numbers (`/255`, `0.5`, `0.25`, the Horner cubic
coefficients `16/12/4`, the `2*Cs`/`2*Cs-1` factors) are **intrinsic-local** to `blend.py` per
ADR-0001 (§8) — only tuning scalars go to `constants.py`. The `BlendMode` enum is an enumerated
vocabulary (not a numeric tuning value) and lives in `blend.py` (BF-2).

### 3.2 Extended `data/` module (Slice 4B — Qt-free I/O; DEP-3)

| Module | Change | Responsibility | Depends on | REQ |
| --- | --- | --- | --- | --- |
| `data/project_io.py` | extend | Serialise the richer layer model — per-node `blend_mode`, `opacity`, `visible`, `locked`, group nesting (ordered children), masks, `reference`/smart links — and bump `FORMAT_VERSION` to **2**. Deserialise defensively (validated, bounds-checked, no `eval`/`exec`) and **read legacy v1 files** (flat layers → `NORMAL`, no groups/masks). | `logic/document` (Layer, LayerGroup, Frame), `logic/blend` (BlendMode), `logic/pixel_buffer`, `logic/color`, `logic/constants` | DATA-001..005 |

### 3.3 New / extended `ui/` modules (Slice 4C — PySide6; binds to 4A + 4B)

| Module (indicative) | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `ui/layer_panel.py` | **new** | `Layer_Panel(QWidget)`: lists the active frame's layers top-to-bottom (topmost first, CL-3); per-row opacity slider / visibility toggle / lock toggle / blend-mode dropdown (12 tr-labels) / drag-reorder; add / remove / duplicate / group / ungroup; expandable group nodes; single-selection active layer. | `document` ops, `blend.BlendMode`, `ui/commands` | UI-001..008, 013, 016..018 |
| `ui/layer_panel.py` (same) | (masks/ref/smart) | Mask add/select-to-paint/remove affordance; mark-reference; create smart layer from source. | `document` mask/reference/smart ops | UI-009..011 |
| `ui/canvas_scene.py` | extend | Render the **flattened composite** of the active frame's stack (via `blend.composite_stack`), not one layer; on edit, call `composite_stack(..., region=(x,y,w,h))`, receive a **region-sized** buffer and **blit it into the resident scene buffer at (x,y)** — `scene.data[y:y+h, x:x+w] = returned.data` (ADR-0007 §Amendment T13, D1). | `blend.composite_stack`, `document` | UI-012 |
| `ui/main_window.py` | extend | Multi-canvas / artboard tabs (extend Phase-1 tabs): per-tab layer tree + `QUndoStack` + composite + scene rect; wire the layer panel to the active document. | `document`, tabs | UI-014 |
| `ui/commands.py` | extend | One `QUndoCommand` wrapper per layer op, delegating to the `history.Command` each `document` op returns (no domain math). | `history` + all 4A ops | UI-013 |

## 4. Slicing (spec §8 / prompt-ratified; logic-first)

The spec/traceability recommended seven fine slices; the dispatch collapses them into three
build-phases (the orchestrator orders dispatch). Logic ships first as the substrate everything binds
to.

- **Slice 4A — Layer & compositing LOGIC** (`REQ-P4-LOGIC-001..015`). `logic/constants.py`
  additions + `logic/blend.py` (BlendMode + separable modes grounded by the research + `composite_stack`;
  NORMAL = FU-3) + `logic/document.py` extension (blend-mode attribute, `LayerGroup`, masks,
  reference + minimal smart layers, reversible attribute/structural ops, lock/reference guard,
  bounds) + new exceptions + pytest/Hypothesis coverage. **Ships first** — it is the substrate the
  DATA and UI slices bind to. The blend formulas are **un-gated** (research landed).
- **Slice 4B — `.pixproj` persistence DATA** (`REQ-P4-DATA-001..005`). Extend `data/project_io.py`
  to serialise the richer layer model, bump schema to v2, defensive validated load, and v1
  back-compat read. **Depends on** 4A (the extended `document` model). ROADMAP "Done means"
  (opacity/visibility/lock + groups/masks round-trip through `.pixproj`) makes this a required
  companion slice.
- **Slice 4C — Layer panel + canvas compositing UI** (`REQ-P4-UI-001..018`). Layer panel + all
  controls + mask/reference/smart affordances + canvas compositing (dirty-rect) + multi-canvas tabs
  + `ui/commands.py` wrappers + AGT-10 recomposite profiling + pytest-qt (both themes) + a11y + i18n.
  **Depends on** 4A (and, for round-trip UI, 4B) plus a stable Phase-1 UI substrate (document tabs,
  `ui/commands.py`, `ui/i18n.py`, palette panel).

## 5. Grounding-derived pins (research → AGT-03 acceptance)

`docs/research-blend-modes.md` (W3C Compositing & Blending Level 1, HIGH confidence) has **landed**,
so the per-mode formulas are published, not unpinned. The following are fixed from the research and
become AGT-03 acceptance. They are **intrinsic** to the W3C algorithm (per ADR-0001 they stay
**local** to `blend.py`, NOT in `constants.py`).

| Concern | Fixed by research | Placement |
| --- | --- | --- |
| Working space | float32 normalised 0..1, **straight (non-premultiplied) alpha** (`§0`: "blending must not use pre-multiplied color values") | ADR-0005; intrinsic → local in `blend.py` |
| normal | `B = Cs` → **delegates to `color.blend_over`** (FU-3) | REQ-P4-LOGIC-003 |
| multiply / screen / darken / lighten / difference / exclusion | `Cb·Cs` / `Cb+Cs−Cb·Cs` / `min` / `max` / `|Cb−Cs|` / `Cb+Cs−2·Cb·Cs` | intrinsic → local in `blend.py` |
| overlay | `HardLight(Cs, Cb)` (hard-light with args swapped — implement once) | intrinsic → local |
| color-dodge / color-burn | piecewise with divide-by-zero guards (`Cb==0→0; Cs==1→1; else min(1,Cb/(1−Cs))` and mirror) | intrinsic → local |
| hard-light | `Cs≤0.5 → Cb·2Cs; else 1−(1−Cb)(2−2Cs)` | intrinsic → local |
| soft-light | W3C `D(Cb)` sqrt/cubic variant (NOT Pegtop) — the most common bug; **dataset-tested** (§7) | intrinsic → local |
| compositing step | `Cs'=(1−αb)Cs+αb·B; αo=αs+αb(1−αs); αo·Co=αs·Cs'+(1−αs)αb·Cb; Co=0 if αo==0` | intrinsic → local |
| non-separable (hue/sat/color/luminosity) | **out of scope this phase** (spec fixes exactly the 12 W3C separable modes; research §2 flags the 4 non-separable ones advanced/deferred) | — |

**PL-D3 — the 12 modes ARE the W3C separable set (normal included).** The spec's `BlendMode`
enumerates exactly `NORMAL, MULTIPLY, SCREEN, OVERLAY, DARKEN, LIGHTEN, COLOR_DODGE, COLOR_BURN,
HARD_LIGHT, SOFT_LIGHT, DIFFERENCE, EXCLUSION` — **12 members** (REQ-P4-LOGIC-001). The research's
four non-separable modes (hue/saturation/color/luminosity) are **not** in the enum and are not built
this phase (research §2 marks them advanced/deferred; spec §6 is silent on them → the enum is the
single source and it lists 12). **[FU-13 count correction]** the prior wording "12 separable + normal
= 13" **double-counted normal** — normal is itself one of the W3C separable modes, so the set is
NORMAL + 11 non-normal separable = **12**, not 13. No drift: the spec's mode set == the W3C separable set.

## 6. Interface contracts (frozen BEFORE implementation — `interface-contract`)

The public surface of `logic/blend.py` and the `logic/document.py` additions is frozen here so
Slices 4B/4C bind to a stable API. STRUCTURE.md carries the same surface (§9). New exceptions
subclass `ValueError` (Phase-1 convention); `DocumentError` is reused for layer-tree-bound errors.

### 6.1 `logic/blend.py` — BlendMode + compositor (REQ-P4-LOGIC-001..007, 011/012 compositor side)
```python
import enum
from typing import Optional, Protocol, Sequence

class BlendMode(enum.Enum):
    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    DARKEN = "darken"
    LIGHTEN = "lighten"
    COLOR_DODGE = "color_dodge"
    COLOR_BURN = "color_burn"
    HARD_LIGHT = "hard_light"
    SOFT_LIGHT = "soft_light"
    DIFFERENCE = "difference"
    EXCLUSION = "exclusion"
    # exactly 12 members = the full W3C separable set (normal is one of them); single source shared by
    # compositor, document, UI dropdown, .pixproj (LOGIC-001). [FU-13: was mis-counted as 13 — double-count of normal]

class BlendError(ValueError): ...

# per-mode blend on straight, normalised 0..1 channels — matches the grounded formula on known
# values (LOGIC-002); deterministic (P2). NORMAL is handled by the compositing step below.
def blend_channel(mode: BlendMode, cb: float, cs: float) -> float: ...

# composite a source RGBA over a destination RGBA under `mode` per the research §3 compositing step;
# NORMAL delegates to color.blend_over(src, dst) exactly (LOGIC-003).
def blend_pixels(mode: BlendMode, src: RGBA, dst: RGBA) -> RGBA: ...

# vectorised (H,W,4) uint8 blend of `src` over `dst` (F7); `opacity` in 0..1 scales src effective
# alpha (LOGIC-005); optional single-channel/alpha `mask` further modulates src alpha (LOGIC-012).
def blend_arrays(mode: BlendMode, src: "np.ndarray", dst: "np.ndarray", *,
                 opacity: float = 1.0, mask: Optional["np.ndarray"] = None) -> "np.ndarray": ...

# structural view of a compositable node — satisfied by document.Layer AND document.LayerGroup
# WITHOUT blend.py importing document (PL-D2, cycle-free). A leaf exposes `effective_buffer()`
# (smart layers resolve their source read-only); a group exposes `children`.
class CompositeNode(Protocol):
    opacity: float
    visible: bool
    blend_mode: BlendMode
    mask: Optional["PixelBuffer"]
    # leaf: effective_buffer() -> PixelBuffer ; group: children -> Sequence[CompositeNode]

# flatten an ordered (bottom-to-top, CL-4) node list into ONE flat RGBA PixelBuffer.
# Skips hidden nodes entirely (LOGIC-006); honours per-node opacity+blend-mode+mask (LOGIC-004/005/007/012);
# a group is flattened first then blended as one (LOGIC-011). Never mutates source buffers (LOGIC-004).
# Working space is float32 straight-alpha 0..1 (ADR-0005) — NOT float64 (T13 D5 compliance correction).
#
# RETURN SHAPE — AMENDED by ADR-0007 §"Amendment (T13)" (the mandatory full-canvas allocation was the
#   8K region-path bottleneck: PixelBuffer(width,height) alloc+fill = ~140 ms floor on EVERY call,
#   ~9x over the 16 ms budget, independent of region size — AGT-10 T13 profile). The region path must
#   NOT allocate a full width×height buffer:
#     region=None          -> a full-canvas PixelBuffer(width, height); implied scene origin (0,0). (unchanged)
#     region=(x, y, w, h)  -> a REGION-SIZED PixelBuffer(w, h) (numpy shape (h, w, 4)) whose implied
#                             scene origin is (x, y). Element (row i, col j) maps to scene pixel (x+j, y+i).
#                             The caller (ui/canvas_scene.py) blits it into the resident scene buffer at
#                             (x, y):  scene.data[y:y+h, x:x+w] = returned.data  (D1).
#   width/height still bound/validate the region and inform per-layer sampling offsets (each node is
#   sampled at scene coords, i.e. node.buffer[y:y+h, x:x+w]). The region is in scene/canvas space
#   (top-left origin, +x right, +y down) and MUST lie fully within (0,0,width,height) with w>=1, h>=1;
#   an out-of-bounds or degenerate region raises BlendError (P2 determinism / Article VII — the caller
#   clamps its dirty rect to the canvas before calling; the compositor validates, it does not silently clamp).
def composite_stack(nodes: Sequence[CompositeNode], width: int, height: int, *,
                    region: Optional[tuple[int, int, int, int]] = None) -> "PixelBuffer": ...
```

### 6.2 `logic/document.py` — layer-op API (REQ-P4-LOGIC-008..015)
```python
from pixelart_creator.logic.blend import BlendMode
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.constants import (
    DEFAULT_LAYER_OPACITY, MAX_LAYERS_PER_FRAME, MAX_GROUP_NESTING_DEPTH,
)

# Layer (extended) — new attributes; defaults keep every existing call site valid (additive):
#   blend_mode: BlendMode = BlendMode.NORMAL
#   mask: Optional[PixelBuffer] = None            # same-geometry alpha/greyscale (CL-10)
#   reference: bool = False                       # visible-but-non-editable (LOGIC-013)
#   smart_source: Optional["Layer"] = None        # minimal smart instance (LOGIC-014, CL-9)
#   def effective_buffer(self) -> PixelBuffer     # smart layer -> source.buffer (read-only); else self.buffer

class LayerGroup:
    """A group node: ordered children composited then blended as one (LOGIC-011)."""
    name: str
    children: List["LayerNode"]
    _opacity: float          # property `opacity` in 0..1, DEFAULT_LAYER_OPACITY
    visible: bool
    locked: bool
    blend_mode: BlendMode
    mask: Optional[PixelBuffer]
    reference: bool
    # satisfies blend.CompositeNode via `children`

LayerNode = Union[Layer, LayerGroup]

# Reversible attribute ops — return a history.Command capturing the minimal prior value (LOGIC-008);
# `ref` addresses a node in the tree (index for a flat frame, path for nested groups).
def set_layer_opacity(self, ref, value: float, *, frame_index: int = 0) -> Command: ...
def set_layer_visible(self, ref, value: bool, *, frame_index: int = 0) -> Command: ...
def set_layer_locked(self, ref, value: bool, *, frame_index: int = 0) -> Command: ...
def set_layer_blend_mode(self, ref, mode: BlendMode, *, frame_index: int = 0) -> Command: ...

# Reversible structural ops (LOGIC-009) — return a history.Command; undo restores exact prior tree.
def make_add_layer_command(self, *, ref=None, frame_index: int = 0) -> Command: ...      # insert above active
def make_remove_layer_command(self, ref, *, frame_index: int = 0) -> Command: ...        # last-layer refusal kept
def make_move_layer_command(self, ref, to, *, frame_index: int = 0) -> Command: ...      # reorder / re-parent
def make_duplicate_layer_command(self, ref, *, frame_index: int = 0) -> Command: ...     # pixel-for-pixel copy
def make_group_command(self, refs, *, frame_index: int = 0) -> Command: ...              # wrap selection (LOGIC-011)
def make_ungroup_command(self, ref, *, frame_index: int = 0) -> Command: ...             # dissolve, promote children

# Reversible group/mask/reference/smart ops (LOGIC-012/013/014):
def make_attach_mask_command(self, ref, mask: PixelBuffer, *, frame_index: int = 0) -> Command: ...
def make_detach_mask_command(self, ref, *, frame_index: int = 0) -> Command: ...
def make_set_reference_command(self, ref, value: bool, *, frame_index: int = 0) -> Command: ...
def make_smart_layer_command(self, source_ref, *, frame_index: int = 0) -> Command: ...

# Guard (LOGIC-010, 013): raise DocumentError on a pixel-mutating op targeting a locked OR reference
# layer; visibility/opacity/mode/order remain changeable (they are non-destructive to pixels, CL-11).
def ensure_editable(layer: Layer) -> None: ...   # DocumentError if layer.locked or layer.reference

# Bounds (LOGIC-015): add_layer/group enforce MAX_LAYERS_PER_FRAME and MAX_GROUP_NESTING_DEPTH,
# raising DocumentError past the bound; new nodes default to DEFAULT_LAYER_OPACITY and BlendMode.NORMAL.
```

**PL-D2 — compositor cycle avoidance (the key layering ruling).** `BlendMode` lives in `blend.py`;
`document.py` imports `blend.BlendMode` (edge `document → blend`). `blend.py` **never imports
`document`** — `composite_stack` consumes nodes through the structural `CompositeNode` Protocol, and
`document.Layer`/`LayerGroup` satisfy it duck-typed at runtime (a group is detected by `children`,
a leaf by `effective_buffer()`). This keeps the import graph one-way and acyclic
(`document → blend → color/constants`), verified by `check_cycles` at the 4A gate (mirrors the
Phase-3 PL-D6 one-way-edge precedent). Smart-layer source resolution is a node method
(`effective_buffer`), so the compositor stays decoupled from smart-layer bookkeeping.

## 7. `REQ-P4-DATA-*` allocation (DEP-3) — the `.pixproj` companion slice

DEP-3 directs AGT-01 to allocate the DATA IDs the ROADMAP "Done means" requires (layer model
round-trips through `.pixproj`). Allocated here per Article X (`REQ-P<phase>-<LAYER>-<NNN>`):

| REQ-ID | Requirement (WHAT the DATA slice serialises) | Traces | Acceptance (for AGT-04) |
| --- | --- | --- | --- |
| **REQ-P4-DATA-001** | Serialise per-layer `blend_mode` (as the `BlendMode` enum value string), `opacity`, `visible`, `locked`. | REQ-P4-LOGIC-001/005/006/008/010; S7 | round-trip preserves every attribute exactly |
| **REQ-P4-DATA-002** | Serialise **layer groups** — nested group nodes with their own attributes and ordered children. | REQ-P4-LOGIC-011; S7 | a grouped/nested tree round-trips with identical structure + order |
| **REQ-P4-DATA-003** | Serialise **masks** — a layer's mask buffer (compressed, geometry-validated). | REQ-P4-LOGIC-012; S7 | a masked layer round-trips; mask bytes identical |
| **REQ-P4-DATA-004** | Serialise **reference** and **smart-layer** flags/links (smart source addressed by a stable in-document ref). | REQ-P4-LOGIC-013/014; S7 | reference flag + smart-source link round-trip; dangling ref rejected on load |
| **REQ-P4-DATA-005** | Bump `.pixproj` `FORMAT_VERSION` to **2**; defensive validated load (bounds/size-checked, no `eval`/`exec`); **read legacy v1 files** (flat layers → `NORMAL`, no groups/masks). | Article VII; ADR-0006; ROADMAP "Done means" | v2 round-trips; a v1 fixture loads (all `NORMAL`, no groups/masks); malformed/oversized/out-of-bounds rejected with `ProjectIOError` |

**Hand-off (AGT-02):** `traceability.md` should gain a `REQ-P4-DATA-*` block mapping these five to
their DATA scenarios + `pending` tests (owner AGT-04). The IDs and acceptance are fixed here; the
matrix upkeep is AGT-02's (Article X ownership). No LOGIC/UI REQ delta.

## 8. Constants & data placement (Article II / S12 / ADR-0001) — AGT-01 rulings

New tuning values go to `logic/constants.py` with a source-citation comment, imported by name.
`constants.py` stays a leaf. Intrinsic algorithm constants stay local per ADR-0001.

| Constant | **Ruled value** | Classification / ruling |
| --- | --- | --- |
| `DEFAULT_LAYER_OPACITY` | `1.0` | Tuning → `constants.py` (CL-2; matches shipped `Layer(opacity=1.0)`) |
| `MAX_LAYERS_PER_FRAME` | `256` | Tuning → `constants.py` (defensive bound, Article VII; CL-7) |
| `MAX_GROUP_NESTING_DEPTH` | `8` | Tuning → `constants.py` (defensive bound, Article VII; CL-6) |
| **`BlendMode` enum** | 12 members (W3C separable set) | **Enumerated vocabulary, not a tuning scalar → `logic/blend.py`** (BF-2; mirrors Phase-2 `SymmetryAxis` / Phase-3 hardware-palette-data placement) |
| Blend-formula magic numbers (`/255`, `0.5`, `0.25`, `16/12/4`, `2Cs`) + `Lum` weights | intrinsic | **Intrinsic (W3C algorithm) → module-local in `blend.py`** (ADR-0001/0005). None go to `constants.py` |
| `.pixproj` `FORMAT_VERSION` | `2` | Format-intrinsic → local in `project_io.py` (ADR-0001 precedent: `FORMAT_VERSION=1` was ruled intrinsic); ADR-0006 records the bump |

**New domain exceptions** (subclass `ValueError`): `BlendError` (`blend.py`). Reuse `DocumentError`
for all layer-tree-bound errors (locked/reference mutation, bounds exceeded, bad node ref, last-layer
removal, nesting depth); reuse `ProjectIOError` for all `.pixproj` load faults.

## 9. STRUCTURE.md update

STRUCTURE.md is updated this session to add (a) `logic/blend.py` + the `document.py` extension +
the three new constants under a **"Phase-4 layer & canvas — PLANNED (Slice 4A)"** block carrying
the §6 public surface; (b) the `data/project_io.py` v2 extension under a **PLANNED (Slice 4B)**
block with the REQ-P4-DATA-* surface; and (c) the Phase-4 `ui/` modules under a **PLANNED (Slice
4C)** block. AGT-01 maintains it via the `interface-contract` skill.

## 10. Reversible-op boundary (REQ-P4-UI-013, S7/C1/F1) & performance (Article VI / DEP-2)

**Reversibility.** Every Phase-4 layer op is built as a Phase-1 reversible `history.Command` in
`logic/document.py` so `ui/commands.py` wraps it in **one** `QUndoCommand` (Article I; Qt-free path
verified by `check_layering`):

| Op | Command kind | Rationale |
| --- | --- | --- |
| set opacity / visibility / lock / blend-mode; set reference | `FunctionCommand` | captures the minimal prior scalar/flag; undo restores it exactly (LOGIC-008) |
| add / remove / reorder / duplicate; group / ungroup; attach / detach mask; create smart | `FunctionCommand` over the tree (removed-node op snapshots node + index + contents) | undo restores exact prior tree state (LOGIC-009); last-layer-removal refusal preserved |
| paint into a mask | `PixelEdit` (on the mask buffer) | reuses the Phase-1 per-pixel diff; mask edits never touch layer pixels (LOGIC-012) |

Invariant `apply ∘ undo = identity` per op. The logic returns a `Command`; `ui/commands.py` supplies
only the Qt shell + dirty-rect signalling (no domain math), exactly as the Phase-1 `PaintCommand`
bridge does.

**Performance (DEP-2, REQ-P4-UI-015).** Compositing an 8K multi-layer stack fully on every edit
blows `FRAME_BUDGET_MS = 16`. The architecture commits to a **dirty-rect region-scoped
recomposite** (ADR-0007): `composite_stack(..., region=...)` recomposes only the changed rectangle,
and **flattened group buffers are cached** and reused when a group's subtree is unchanged. AGT-10
(`frame-profile` / `perf_profile`) measures the 8K multi-layer recomposite headless; an over-budget
result yields an AGT-10 directive (widen/narrow the dirty rect, cache scope, `QOpenGLWidget`
viewport, `setBspTreeDepth`) that AGT-05 implements — the budget is **never** relaxed (Article VI
§2). The resident per-layer buffers are never culled; only Qt rendering is (Article VI §3, F7).
Task T13 (AGT-10) is the profiling gate + conditional directive.

**T13 AMENDMENT (2026-07-02 — AGT-10 profile
`subagent-report-agt-10-rendering-performance-a4b1282f`; ADR-0007 §Amendment).** The T13 profile
found the region path was **~140 ms (~9× over budget) FAILING SC-UI-015-1**, and that the cost was
NOT the blend (a brush-sized dirty rect blends in ~1.5 ms) but a **mandatory full-canvas 126 MB
`PixelBuffer(width,height)` allocation+fill inside `composite_stack` on every call, regardless of
`region`** — defeating ADR-0007's own dirty-rect intent. Three architecture revisions (frozen here):
- **D1 (AGT-03) — kill the full-canvas allocation.** A bounded `region` now returns a **region-sized
  `(h, w, 4)` PixelBuffer** with implied origin `(x, y)` (contract in §6.1); `ui/canvas_scene.py`
  blits it into the resident scene buffer at `(x, y)`. No full width×height allocation on the region
  path. Removes the ~140 ms floor → a brush-sized edit ≈ 1.5 ms → **in budget**.
- **D5 (AGT-03) — float32 working space.** ADR-0005 already mandates float32; the shipped
  implementation deviated to **float64**. Correct to `float32` as the blend working dtype (halves
  per-pixel memory/time). Compliance correction, no behaviour change (ADR-0005 §Compliance note T13).
- **D4 (AGT-03) — cached group buffers + partial-stack recomposite are now MANDATORY, not optional.**
  Each `LayerGroup`'s flattened intermediate is cached and reused while its subtree is unchanged; any
  child edit / attribute / order / mask change **invalidates the group cache up the whole ancestor
  chain** (invalidation contract, asserted by SC-UI-012-2). Partial-stack recomposite: cache the
  backdrop of layers below the changed layer so an attribute change on layer *k* re-blends only *k..top*.
- **D2/D3 are UI directives owned by AGT-05** (viewport-scoped attribute recomposite; opacity-drag
  debounce — AGT-10 report §4 D2/D3). **D6/D7 (QOpenGLWidget viewport; `setBspTreeDepth`) remain
  deferred** per AGT-10 (needed only for the worst-case whole-viewport many-layer recomposite).
The budget was NOT relaxed (Article VI §2). The contract change is **localised to the compositor
return shape + working dtype** (C1: the signature is unchanged, no imports added, spec WHAT unaffected).

**BF-1 (canvas draw form).** The composite is drawn as one whole-buffer `QGraphicsPixmapItem`
refreshed per dirty-rect (simplest deterministic model, reuses the Phase-1 single-item canvas);
tiled composite items remain an AGT-10 tuning option if profiling requires it (not a spec
requirement — REQ-P4-UI-012 requires only that the canvas shows the flattened stack).

## 11. Verification (this session)

- `python scripts/check_layering.py` → `check_layering: clean (27 modules).`, exit **0**.
- `python scripts/check_cycles.py` → `check_cycles: no cycles (63 modules).`, exit **0**.

No Phase-4 code exists yet, so both are expected clean; they re-run at each slice boundary (tasks
T5 / T8 / T16) after the modules land, confirming `logic/blend.py` + the `document.py`/`project_io.py`
extensions import zero Qt and add no cycle — in particular the **one-way `document → blend` edge**
with `blend` never importing `document` (PL-D2). Script exit 2 → BLOCKED (Decision A1-D3 / A1-E3);
AGT-01 never asserts layering clean on an unrun check.

## 12. Exit / status

- plan.md authored over the approved spec; `logic/blend.py` (new) + `document.py`/`constants.py`
  (extend) + `data/project_io.py` (extend, v2) + Phase-4 `ui/` modules mapped to their S11 layers;
  interface contracts frozen (§6: compositor + layer-op API); the **alpha convention pinned**
  (straight/non-premultiplied, float32 0..1, NORMAL→`color.blend_over` — ADR-0005).
- **`REQ-P4-DATA-001..005` allocated** (DEP-3, §7); the `.pixproj` schema-v2 + back-compat decision
  ruled (ADR-0006).
- Blend formulas grounded — no invention (research landed); non-separable modes correctly out of
  scope (PL-D3). Constant + enum + format-version placements ruled (§8).
- Dirty-rect region-scoped recomposite + cached group buffers committed (ADR-0007, §10); AGT-10
  profiling gate assigned; budget never relaxed.
- Reversible-op boundary specified — one `QUndoCommand` per layer op via `ui/commands.py` (§10);
  zero Qt in `logic/`/`data/`.
- Layering/cycle gates green this session (§11); re-run at each slice boundary; PL-D2 keeps
  `document → blend` one-way.
- Slicing ratified: **4A logic → 4B data (`.pixproj` v2) → 4C UI (panel + compositing + tabs)**.
- ADR-0005 / ADR-0006 / ADR-0007 filed under `docs/adr/`.
- `sdd-analyze` C1 gate run over constitution/spec/plan/tasks (see `analyze-report.md`).
- **STATUS: COMPLETED.**
</content>
</invoke>
