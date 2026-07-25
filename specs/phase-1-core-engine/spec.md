# Specification — Phase 1: Core Engine (logic/data)

| Field | Value |
| --- | --- |
| Feature | `phase-1-core-engine` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-01 |
| Governed by | `constitution.md` (Articles I, II, IV, VII, X) |
| Mode | **RETROACTIVE** — reconstructs the requirements realised by already-shipped, tested code (code is ground truth) |
| REQ-ID range | `REQ-P1-LOGIC-001..013`, `REQ-P1-DATA-001` |
| Layer scope | `pixelart_creator/logic/` + `pixelart_creator/data/` only (the Phase-1 UI increment is out of scope — see Gaps) |
| Source of behaviour | `docs/gather-agt-02-phase1-core-engine.md` + `tests/logic/*`, `tests/data/*` |

---

## 1. Purpose (WHY)

Phase 1 delivers the **headless core engine** for the PixelArt Creator: pixel-perfect
storage, a stable pure-Python (Qt-free) domain layer, reversible undo/redo, an
immutable/diffable project-state tree, and a validated `.pixproj` project file format.
It is the foundation every later phase (advanced drawing, colour/palette, layers,
animation, tilemaps, export) builds on. The engine carries **no presentation code**;
the Qt/PySide6 hub, tools, and canvas are a separate Phase-1 increment (see §7 Gaps).

This document is written **after** the code shipped and its tests pass; its job is to
reconstruct — faithfully and without rubber-stamping — the requirements the code
realises, trace each to a dossier `S-id`, and flag any shipped behaviour that lacks an
upstream Phase-1 requirement (§8) and any Phase-1 dossier requirement not yet satisfied
(§7).

## 2. Scope

**In scope (WHAT):** the eight shipped modules —
`logic/constants.py`, `logic/color.py`, `logic/palette.py`, `logic/pixel_buffer.py`,
`logic/drawing.py`, `logic/history.py`, `logic/document.py`, `logic/compactor.py`,
`data/project_io.py` — their public API contracts, invariants, and the behaviours
their tests assert.

**Out of scope:** all `ui/` code (canvas scene/view, tools, main window, i18n,
`ui/commands.py` QUndoCommand bridge), the GPU render pipeline, tile-culling rendering,
zoom/pan, and cloud-sync — deferred to the Phase-1 UI increment and later phases.
No new technology choices are introduced (the stack is fixed by S8; HOW belongs to
`sdd-plan`).

## 3. User stories

- **US-1 (Artist).** As a pixel artist, I want each pixel of a large (up to 8K) canvas
  to hold an exact colour so my art is stored losslessly. → REQ-P1-LOGIC-001/006
- **US-2 (Artist).** As an artist, I want to draw with pencil/eraser, lines,
  rectangles, ellipses, colour-picker, and flood-fill so I can create pixel art. →
  REQ-P1-LOGIC-008
- **US-3 (Artist).** As an artist, I want unlimited-depth (or bounded) undo/redo of
  every edit so mistakes are cheap. → REQ-P1-LOGIC-009
- **US-4 (Artist).** As an artist, I want my work organised as documents with frames
  and layers so I can build multi-layer, multi-frame projects. → REQ-P1-LOGIC-010
- **US-5 (Artist).** As an artist, I want to save and reopen my project from a
  `.pixproj` file with every pixel, palette, and layer preserved. → REQ-P1-DATA-001
- **US-6 (Artist / Palette).** As an artist, I want an indexed colour palette I can
  add to, reorder, and query by nearest colour. → REQ-P1-LOGIC-005
- **US-7 (Platform integrity).** As the platform, I want malformed or oversized
  project files rejected safely (no code execution) so opening a file is never
  dangerous. → REQ-P1-DATA-001
- **US-8 (Maintainer).** As a maintainer, I want the domain layer to contain zero Qt
  and all tuning numerics centralised so the architecture stays clean and portable. →
  REQ-P1-LOGIC-012/013

## 4. Functional requirements

Each REQ carries `traces:` to the dossier S-id(s) it realises. REQs flagged **[REVIEW]**
have a weak/forward or absent Phase-1 dossier trace and are itemised in §8.

### REQ-P1-LOGIC-001 — Colour value model & validation
`traces:` S8 (RGBA uint8 representation), S1 (each pixel individually editable, coloured)
The engine represents a colour as a validated 4-tuple `RGBA = (r,g,b,a)`, each channel
an `int` in `0..255` (booleans rejected). `rgba()` builds a validated tuple (default
alpha opaque = 255) and raises `ColorError` on any out-of-range/non-int channel;
`is_rgba()` is a non-raising predicate. Domain error `ColorError` subclasses `ValueError`.

### REQ-P1-LOGIC-002 — Colour hex (de)serialisation
`traces:` S7 (`.pixproj` stores palette colours as hex strings)
`to_hex()` renders `#RRGGBB` or `#RRGGBBAA` (alpha optional); `from_hex()` parses
`#RGB`/`#RRGGBB`/`#RRGGBBAA` (leading `#` optional) and raises `ColorError` on malformed
input. Round-trip is lossless for all valid colours (`from_hex(to_hex(c)) == c`).

### REQ-P1-LOGIC-003 — Straight-alpha compositing primitive (`color.blend_over`) **[REVIEW]**
`traces:` forward to Phase-4 layer blend modes (foundational primitive, shipped early)
A **foundational, standalone** source-over compositing primitive over two RGBA tuples:
opaque source returns source unchanged; fully transparent source returns destination
unchanged; otherwise an integer-rounded straight-alpha composite clamped to `0..255`,
with output alpha `> 0` guaranteed for a partially transparent source. **It has no
in-code caller in Phase 1**: `PixelBuffer.blit(blend=True)` (REQ-P1-LOGIC-007)
reimplements alpha compositing directly in vectorised NumPy and does **not** call
`blend_over`. `blend_over` is therefore retained as the tuple-level reference primitive
for the Phase-4 blend-mode system; its own tests (SC-L003-1..3) cover it independently
of the blit path.

### REQ-P1-LOGIC-004 — Colour distance metric (`distance_sq`)
`traces:` S7 (palette nearest-colour matching — `nearest_index`), S2 (flood-fill colour
tolerance — `drawing.flood_fill`); forward to Phase-3 perceptual matching (CIEDE2000
baseline layered on top). **Consumed within Phase 1** by REQ-P1-LOGIC-005
(`palette.nearest_index`, lines 109/111) and REQ-P1-LOGIC-008 (`drawing.flood_fill` RGBA
tolerance, line 189).
Exact integer squared-Euclidean distance over all four channels; symmetric; a cheap
ordering metric (not perceptual). It realises the Phase-1 palette-nearest + flood-fill
tolerance capability now, and remains the baseline the Phase-3 perceptual metric extends.

### REQ-P1-LOGIC-005 — Indexed palette management
`traces:` S7 (project state carries a palette; INDEXED colour mode); forward to Phase-3
colour/palette system (S3)
A `Palette` holds up to `MAX_PALETTE_SIZE = 256` colours (8-bit index space). It
supports construct-from-iterable, `get`/`set`/`append` (returns new index)/`remove_at`
(shifts later indices down)/`move`/`index_of` (first exact match)/`nearest_index`
(squared-distance, ties resolve to the **lower** index, raises on empty)/`colors()`
snapshot/`copy()` (independent). Indices must be `int` in `0..len-1` (booleans
rejected). `append` beyond 256 raises `PaletteError` (subclass of `ValueError`).

### REQ-P1-LOGIC-006 — Pixel buffer storage & access
`traces:` S1 (8K editable pixel grid), S8 (NumPy uint8 RGBA)
A `PixelBuffer` stores pixels in a NumPy `uint8` array: RGBA mode shape `(H,W,4)`,
INDEXED mode shape `(H,W)`. Origin is top-left `(x,y)`. Dimensions must be positive
ints (booleans rejected) within `MAX_CANVAS_WIDTH`/`MAX_CANVAS_HEIGHT` (imported from
`constants.py`), else `PixelBufferError`. Supports `in_bounds`, `get_pixel`/`set_pixel`
(bounds-checked, type-checked per mode), `fill`, and `fill_rect` (clipped; zero/negative
size is a no-op). RGBA default fill is transparent; INDEXED default is 0.

### REQ-P1-LOGIC-007 — Pixel buffer region / blit / resize / copy
`traces:` S1 (editing the pixel grid), S8; blit-**blend** sub-behaviour is forward to
Phase-4 layer blend (see §8)
`region()` returns an independent copy of a fully-contained sub-rectangle (raises
otherwise). `blit()` copies a same-mode source at an offset, clipped to bounds; with
`blend=True` (RGBA only; raises on INDEXED) it straight-alpha composites **using its own
vectorised NumPy implementation** (independent of `color.blend_over`, which it does not
call — the tuple-level primitive REQ-P1-LOGIC-003 is not wired to this path). This blit
blend is the Phase-1 tested compositing behaviour and is fully covered by SC-L007-5/-6.
`resize()` is
a non-destructive crop/pad producing a new buffer (old content placed at an offset, rest
= fill). `copy()` is a deep independent copy; `__eq__` compares mode + array data.

### REQ-P1-LOGIC-008 — Drawing primitives
`traces:` S1 (each pixel editable), S2 (paint pixels with a colour value)
Pure functions that mutate a `PixelBuffer` and return the list of `(x,y)` coordinates
actually changed (clipped to the buffer), so a caller can build a reversible record:
`pencil` (single pixel; shared by pencil/eraser), `pick_color`, `line` (integer
Bresenham, clips off-buffer endpoints), `rectangle` (outline or filled, normalises
swapped corners), `ellipse` (midpoint; degenerate axis falls back to a line/rect),
`flood_fill` (scanline; seed must be in bounds; no-op if already the target value; RGBA
tolerance via squared distance, ignored for INDEXED). Deterministic (P2).

### REQ-P1-LOGIC-009 — Reversible command history (undo/redo)
`traces:` S7 (command-pattern undo/redo; immutable/diffable state)
A pure-Python command pattern: abstract `Command` with `execute()`/`undo()`;
`PixelEdit` applies/reverts a list of `(x,y,old,new)` diffs (undo in reverse order);
`FunctionCommand` wraps do/undo callables. `History` is a bounded linear undo/redo stack
(`push` clears the redo stack; `limit` must be a positive int or `None`; oldest command
dropped past the limit; `can_undo`/`can_redo`/`undo_depth`/`redo_depth`/`clear`).
`record_edit()` snapshots the buffer, runs a drawing op, and stores only genuinely
changed pixels (`old != new`, deduped) as an already-applied `PixelEdit`. Invariant:
`undo` is the exact inverse of `execute` (apply∘undo = identity).

### REQ-P1-LOGIC-010 — Document state tree
`traces:` S7 (immutable/diffable project state). Layer opacity/visible/locked
attributes are forward to Phase-4; Frame/`duration_ms`/add-remove-frame are forward to
Phase-5 (see §8)
A `Document` is `width × height × mode × palette × frames[] × metadata`; each `Frame`
holds `layers[]` and a positive `duration_ms`; each `Layer` wraps a `PixelBuffer` with
`name`, `opacity` (float `0.0..1.0`, booleans rejected), `visible`, `locked`. A new
document has one frame holding one empty "Background" layer. Layer ops: `add_layer`,
`remove_layer` (refuses the last layer), `move_layer`. Frame ops: `add_frame`,
`remove_frame` (refuses the last frame). `resize_canvas` non-destructively resizes every
layer buffer in every frame. Invalid indices/values raise `DocumentError`.

### REQ-P1-LOGIC-011 — Deterministic sprite compaction (MaxRects) **[REVIEW]**
`traces:` no Phase-1 dossier S; grounded by research finding F8; forward to Phase-7
export/texture-atlas (ROADMAP Phase 7)
`compact(rects, max_width, max_height)` packs rectangles into an atlas using MaxRects
Best-Short-Side-Fit with rotation disabled (FIX-13), fully deterministic (sorted by area
desc then id, fixed tie-break; no time/random/network). Returns a `Packing`
(placements sorted by id, used width/height). `CompactionError` (subclasses `Exception`,
not `ValueError`) carries a stable `reason` token: `"invalid-input"` (bad rect
arity/type/negative, non-positive atlas bounds) or `"does-not-fit"` (a rect exceeds the
atlas or the remaining free area). Empty input → empty packing (0×0).

### REQ-P1-LOGIC-012 — Centralised numeric constants
`traces:` S12 (all numeric tuning values in `logic/constants.py`)
`logic/constants.py` is the single home for tuning numerics
(`MAX_CANVAS_WIDTH`, `MAX_CANVAS_HEIGHT`, `TILE_SIZE`, `TILE_BUFFER`, `PARALLAX_FACTOR`,
`SCALE_FACTOR`, `FPS_TARGET`, `FRAME_BUDGET_MS`), imported by name. (Compliance findings
where numerics currently live elsewhere are in §9.)

### REQ-P1-LOGIC-013 — Three-layer purity (Qt-free logic/data) *(NFR)*
`traces:` S11 (three-layer architecture; zero Qt in `logic/`/`data/`)
Every `logic/` and `data/` module imports **zero** Qt/PySide6. Qt bridges (`QColor`,
`QUndoCommand`) live only in `ui/`. Enforced by `check_layering`/`check_cycles`
(Article I), not by a unit test. The gather confirms zero S11 violations across all
eight modules.

### REQ-P1-DATA-001 — `.pixproj` project I/O with defensive validation
`traces:` S7 (`.pixproj` JSON project file), Article VII (validated, bounds-checked,
no eval/exec)
`serialize()` produces a JSON-ready dict (`format="pixproj"`, `version=1`,
`canvas{width,height,mode}`, palette as hex list, metadata, `frames[{duration_ms,
layers[{name,opacity,visible,locked,data}]}]`); pixel `data` is zlib(level 9)+base64.
`save_project()`/`load_project()` use `pathlib` and append/keep the `.pixproj` suffix.
`deserialize()` is defensive: every field type/bounds-checked (int excludes bool), no
`eval`/`exec`; rejects wrong format, unsupported version (`!= 1`), out-of-range canvas
dims, unknown colour mode, non-list/oversized (`>256`) palette or bad hex, empty
frames/layers, non-positive `duration_ms`, non-base64 data, decompressed size over the
`MAX_CANVAS_WIDTH*MAX_CANVAS_HEIGHT*4` cap, and payloads whose length ≠
`width*height*channels`. Optional fields default (`name`→"Layer", `opacity`→1.0,
`visible`→True, `locked`→False, missing metadata→{}). I/O and JSON errors are normalised
to `ProjectIOError`.

## 5. Non-functional requirements

- **NFR-1 (Purity, S11).** Zero Qt in `logic/`/`data/` — REQ-P1-LOGIC-013.
- **NFR-2 (Determinism, P2).** `color`, `palette` (tie-to-lower), `drawing`, and
  `compactor` produce identical output for identical input (test-asserted).
- **NFR-3 (Reversibility).** apply∘undo = identity across `PixelEdit`, `record_edit`,
  and `History` round-trips (REQ-P1-LOGIC-009).
- **NFR-4 (Security, Article VII).** `.pixproj` load is defensive, bounds/size-checked,
  never `eval`/`exec` (REQ-P1-DATA-001).
- **NFR-5 (Coverage, S13/Article IV).** ≥90 % line / ≥80 % branch per package —
  verified by `coverage_gate` (owned by AGT-04/CI; noted here for traceability).
- **NFR-6 (Numerics, S12).** Single-source constants — REQ-P1-LOGIC-012 (see §9 findings).

## 6. Non-goals (explicit)

- No `ui/` presentation, no QGraphicsScene/View, no zoom/pan, no tile-culling render.
- No GPU render pipeline; no cloud-sync layer (S7 forward parts).
- No perceptual colour matching (CIEDE2000) — Phase 3.
- No selections/transforms/symmetry/RotSprite — Phase 2.
- No blend modes / layer groups / masks UI — Phase 4.
- No export/atlas packing pipeline wiring — Phase 7 (the `compactor` primitive exists;
  its integration does not).

---

## 7. Gaps (unimplemented Phase-1 dossier requirements)

Dossier requirements in Phase-1 scope that the **shipped code does not yet satisfy**.
These are legitimately the pending **Phase-1 UI increment** (or later phases), not
logic/data defects — recorded so `sdd-analyze` (AGT-01) and the orchestrator can see the
Phase-1 requirement surface is not fully closed.

| Gap | Dossier S | Status | Owner (roadmap) |
| --- | --- | --- | --- |
| GAP-1 | S1 — nearest-neighbour render + 64px viewport tile culling | Not implemented (rendering is UI) | Phase-1 UI increment (AGT-05/AGT-10) |
| GAP-2 | S2 — left-click paints the target pixel(s) with the active swatch | Logic (`drawing.pencil`) exists; the click→paint UI binding does not | Phase-1 UI increment (AGT-05) |
| GAP-3 | S5 — zoom (deep/"infinite") + pan, grid overlay, snapping | Not implemented (UI) | Phase-1 UI increment (AGT-05) |
| GAP-4 | S7 — GPU render pipeline (QOpenGL viewport) | Not implemented (UI/perf) | Phase-1 UI increment (AGT-10) |
| GAP-5 | S7 — event-driven editor wiring; `ui/commands.py` QUndoCommand bridge over `logic/history.py` | Not implemented (logic core is ready to be wrapped) | Phase-1 UI increment (AGT-05) |
| GAP-6 | S7 — optional cloud-sync layer | Not implemented (explicitly deferred) | Phase 10 |
| GAP-7 | S3/S3a/S3b/S4 — right-click colour hub, favourites, RGB wheel, active swatch | Not implemented; `logic/palette` + `logic/color` are the foundation | Phase 3 (colour hub UI) |

## 8. Behaviors without upstream requirement (ORCHESTRATOR REVIEW)

Shipped, tested behaviours whose Phase-1 dossier `S-id` backing is **absent, weak, or
forward-looking**. Per authoring rule R1 these are **not** silently ratified as Phase-1
requirements; the orchestrator must adjudicate whether to (a) accept the early ship and
attach a retroactive trace to the relevant later-phase requirement, or (b) reclassify /
defer. All are correct and tested; the question is scope attribution only.

| # | Behaviour | Module / REQ | Nearest trace | Why flagged |
| --- | --- | --- | --- | --- |
| REV-1 | **MaxRects sprite compaction** (`compact`, `Packing`, `CompactionError.reason`) | `compactor.py` / REQ-P1-LOGIC-011 | Research F8; ROADMAP **Phase 7** (texture atlas) | No Phase-1 dossier S at all. Shipped ~6 phases early. Adjudicate: keep as Phase-1 foundation or move the REQ to Phase 7. |
| REV-2 | **`color.blend_over` straight-alpha primitive** (tuple-level source-over) | `color.py` / REQ-P1-LOGIC-003 | **Phase-4** layer blend modes | Foundational compositing primitive with **no in-code caller in Phase 1** — `PixelBuffer.blit(blend=True)` reimplements blending in vectorised NumPy and does **not** call `blend_over`. It anticipates the Phase-4 blend-mode system. (The Phase-1 blit-blend behaviour itself is a distinct, tested capability under REQ-P1-LOGIC-007, not flagged here.) |
| REV-3 | ~~Colour distance metric (`color.distance_sq`)~~ — **WITHDRAWN** | `color.py` / REQ-P1-LOGIC-004 | — (resolved) | **No longer a scope-attribution item.** `distance_sq` IS consumed within Phase 1 by `palette.nearest_index` (REQ-P1-LOGIC-005) and `drawing.flood_fill` RGBA tolerance (REQ-P1-LOGIC-008); it now traces to S7 (palette nearest) + S2 (flood-fill tolerance) with a Phase-3 perceptual forward note. Removed from the "no upstream requirement" listing; the row is retained for audit only. |
| REV-4 | **Indexed palette system** (full `Palette` CRUD/reorder/nearest, 256-cap) | `palette.py` / REQ-P1-LOGIC-005 | S7 (project palette / INDEXED mode) partial; **Phase-3** colour & palette system | Genuinely needed by INDEXED buffers + `.pixproj`, but the full reorder/nearest surface is Phase-3 workload shipped early. |
| REV-5 | **Layer opacity / visible / locked attributes** | `document.py` `Layer` / REQ-P1-LOGIC-010 | **Phase-4** layer system | The document *tree* is S7; these per-layer editing attributes are Phase-4 features present ahead of their UI. |
| REV-6 | **Frame model + `duration_ms` + add/remove frame** | `document.py` `Frame` / REQ-P1-LOGIC-010 | **Phase-5** animation | Multi-frame animation is Phase 5; the tree ships frame support early. |
| REV-7 | **`FunctionCommand`** (generic do/undo command) | `history.py` / REQ-P1-LOGIC-009 | S7 (command pattern) — generic | Beyond pixel-edit undo; no specific Phase-1 use-site yet. Minor; likely accept. |

Note: none of these are ambiguities in the code (behaviour is fully defined and tested);
they are **scope-attribution decisions** for the orchestrator, hence this spec returns
COMPLETED rather than blocking on clarification (§10).

## 9. Constitution-compliance findings — S12 (Article II)

Numeric values defined or inlined **outside** `logic/constants.py`, from the gather file.
Reported, **not fixed** (AGT-02 does not edit code). Flagged for **AGT-01 `sdd-analyze`**
adjudication and **AGT-03** remediation if confirmed as tuning parameters. Article II
requires "every numeric **tuning** value" to be centralised; the open question per item
is *tuning parameter* (must move to `constants.py`) vs *intrinsic format/algorithmic
constant* (legitimately local). Note: no value that `constants.py` already defines is
duplicated inline — these are values not centralised there.

| # | Module | Value(s) | Suggested classification | Disposition |
| --- | --- | --- | --- | --- |
| S12-1 | `palette.py` | `MAX_PALETTE_SIZE = 256` | **Tuning candidate** (index-space cap; product-visible limit) | Recommend move to `constants.py`; AGT-01 to confirm. |
| S12-2 | `document.py` | `DEFAULT_FRAME_DURATION_MS = 100` | **Tuning candidate** (default animation timing) | Recommend move to `constants.py`; AGT-01 to confirm. |
| S12-3 | `project_io.py` | frame-duration default `100` **inlined** at parse (line ~204) instead of reusing `DEFAULT_FRAME_DURATION_MS` | **Duplication / drift risk** | Reuse the single default constant regardless of where it lives. AGT-03. |
| S12-4 | `color.py` | `CHANNEL_MIN = 0`, `CHANNEL_MAX = 255`; `255.0`/clamp literals inlined in `blend_over`/`to_hex` | Intrinsic to 8-bit RGBA (borderline) | Likely intrinsic; if centralised, do so consistently. AGT-01 to rule. |
| S12-5 | `pixel_buffer.py` | index range `0..255` inlined in `_normalise_value`; RGBA channel count `4` inlined in array shape | Intrinsic to 8-bit / RGBA | Likely intrinsic. AGT-01 to rule. |
| S12-6 | `project_io.py` | zlib level `9`, channel count `4`, `FORMAT_VERSION = 1` | Mixed: `zlib=9` is a **tuning candidate**; `4`/version are format-intrinsic | `zlib` level → consider `constants.py`. AGT-01/AGT-03. |
| S12-7 | `compactor.py` | requires explicit `max_width`/`max_height` (does **not** import `MAX_CANVAS_*`); smoke uses literal `256×256` demo | Interface choice + test/demo data | Header claims optional defaults from `constants`; not wired. AGT-01 to decide whether `compact` should default from `constants.py`. |
| S12-8 | `drawing.py` | Bresenham `2`, ellipse degenerate threshold `0.5`, `0.25` | **Algorithmic constants** (not tuning) | Recommend accept as-is (intrinsic). Listed for completeness. |

---

## 10. Clarifications (retroactive; resolved from code ground truth)

Per `sdd-clarify`, underspecified areas were resolved against shipped behaviour (the
code and its passing tests are the category-1 source). No open question remains that
blocks planning; scope-attribution items are routed to §8 (ORCHESTRATOR REVIEW), not
held as open clarifications.

- **CL-1 — `nearest_index` tie-break?** Resolved: ties resolve to the **lower** index
  (deterministic, P2). *(test_nearest_index_ties_to_lower)*
- **CL-2 — Blend on an INDEXED buffer?** Resolved: **raises** `PixelBufferError` — blend
  is RGBA-only. *(test_blit_blend_on_indexed_rejected)*
- **CL-3 — Removing the last layer / last frame?** Resolved: **refused** (raises
  `DocumentError`). *(test_remove_last_layer_refused, test_remove_last_frame_refused)*
- **CL-4 — Palette at the 256 cap?** Resolved: further `append` **raises**
  `PaletteError`. *(test_full_palette_rejects_append)*
- **CL-5 — `.pixproj` version mismatch?** Resolved: version must equal `1`; anything else
  → `ProjectIOError` ("unsupported version"). *(test_deserialize_rejects_malformed[version=99])*
- **CL-6 — `flood_fill` tolerance in INDEXED mode?** Resolved: tolerance applies to RGBA
  only; **ignored** for INDEXED (exact match). *(test_flood_fill_indexed, test_flood_fill_tolerance_rgba)*
- **CL-7 — `History` limit semantics?** Resolved: `limit` is a **positive int or None**;
  a non-positive value raises `ValueError`; past the limit the **oldest** command is
  dropped. *(test_history_limit_drops_oldest, test_history_bad_limit)*
- **CL-8 — Domain-error base class consistency?** **Resolved by task T6.**
  `CompactionError` is being standardised to subclass `ValueError` (T6, owner AGT-03),
  matching every other domain error (`ColorError`, `PaletteError`, `PixelBufferError`,
  `DocumentError`, `ProjectIOError`), while preserving its `__init__` and the stable
  machine `reason` token. This is a decided remediation, **not** an accepted
  inconsistency; the earlier "intentional inconsistency" note is superseded.
  *(SC-L011-6/-7/-8 reason-token behaviour unchanged; T7 adds a regression asserting the
  `ValueError` subclass.)*
- **CL-9 — Coordinate origin?** Resolved: top-left `(x,y)`; buffers are `(H,W[,4])`.

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per asserted behaviour; parametrised tests use a Scenario Outline. Each
scenario maps to its existing test id in `traceability.md`. Feature blocks are grouped by
REQ-ID.

### Feature: Colour value model (REQ-P1-LOGIC-001)
```gherkin
Scenario: SC-L001-1 default alpha is opaque
  Given channels r=1 g=2 b=3
  When I build an rgba() with no alpha
  Then the result is (1,2,3,255)

Scenario Outline: SC-L001-2 out-of-range channels are rejected
  Given a channel value <bad>
  When I build an rgba() with it
  Then ColorError is raised
  Examples: | bad | -1 | 256 | 1000 |

Scenario: SC-L001-3 non-int and bool channels are rejected
  Given a channel that is 1.5 or True
  When I build an rgba() with it
  Then ColorError is raised

Scenario Outline: SC-L001-4 is_rgba predicate
  Given value <value>
  When I call is_rgba
  Then the result is <expected>
  Examples: | (1,2,3,4)->True | 3-tuple->False | (..,300)->False | (..,True)->False | "nope"->False | list->False |
```

### Feature: Colour hex (de)serialisation (REQ-P1-LOGIC-002)
```gherkin
Scenario: SC-L002-1 to_hex with and without alpha
  Given colour (255,0,128,255)
  When I call to_hex with_alpha=True then False
  Then I get "#FF0080FF" then "#FF0080"

Scenario Outline: SC-L002-2 from_hex parses variants
  Given hex text <text>
  When I call from_hex
  Then I get <rgba>
  Examples: | #f00->(255,0,0,255) | 0F0->(0,255,0,255) | #0000FF->(0,0,255,255) | #01020304->(1,2,3,4) |

Scenario Outline: SC-L002-3 from_hex rejects invalid
  Given invalid hex <bad>
  When I call from_hex
  Then ColorError is raised
  Examples: | "#12" | "#12345" | "wxyz" | "#GGGGGG" | 123 |

Scenario: SC-L002-4 hex round-trip is lossless (property)
  Given any colour with channels in 0..255
  When I compute from_hex(to_hex(c))
  Then it equals c
```

### Feature: Alpha compositing & distance (REQ-P1-LOGIC-003 / -004)
```gherkin
Scenario: SC-L003-1 opaque source returns source
  Given an opaque source over any destination
  When I blend_over
  Then the result equals the source

Scenario: SC-L003-2 transparent source returns destination
  Given a fully transparent source
  When I blend_over any destination (even transparent)
  Then the result equals the destination

Scenario: SC-L003-3 half-alpha red over opaque blue
  Given half-alpha red over opaque blue
  When I blend_over
  Then output alpha is 255 and red channel > blue channel

Scenario: SC-L004-1 distance_sq is zero and symmetric
  Given equal colours, and (0,0,0,255) vs (0,0,255,255)
  When I compute distance_sq
  Then equal colours give 0, it is symmetric, and the blue diff gives 255**2
```

### Feature: Indexed palette (REQ-P1-LOGIC-005)
```gherkin
Scenario: SC-L005-1 construct reflects input order
Scenario: SC-L005-2 append returns incremental indices and get reads them back
Scenario: SC-L005-3 append rejects a non-RGBA (3-tuple) with PaletteError
Scenario: SC-L005-4 set replaces the colour at an index
Scenario Outline: SC-L005-5 get with a bad index raises  Examples: -1 | 5 | True | "x"
Scenario: SC-L005-6 remove_at returns the removed colour and shifts later indices down
Scenario: SC-L005-7 move reorders; a bad target raises
Scenario: SC-L005-8 index_of returns the first exact index or None
Scenario: SC-L005-9 nearest_index ties to the lower index and matches the nearer colour
Scenario: SC-L005-10 nearest_index on an empty palette raises PaletteError
Scenario: SC-L005-11 a full (256) palette rejects further append
Scenario: SC-L005-12 copy is equal but independent; colors() is a snapshot
Scenario: SC-L005-13 equality with a non-Palette is False; repr contains "Palette"
```

### Feature: Pixel buffer storage & access (REQ-P1-LOGIC-006)
```gherkin
Scenario: SC-L006-1 default RGBA buffer is transparent with correct w/h/mode
Scenario: SC-L006-2 indexed buffer defaults to 0
Scenario: SC-L006-3 prefill honoured for RGBA and indexed
Scenario Outline: SC-L006-4 bad dimensions raise  Examples: (0,1) | (1,0) | (-3,2)
Scenario: SC-L006-5 non-int / bool dimensions rejected
Scenario: SC-L006-6 PixelBuffer(MAX_CANVAS_WIDTH+1,1) raises
Scenario: SC-L006-7 a bad mode (string "rgba") raises
Scenario: SC-L006-8 set/get pixel round-trips
Scenario: SC-L006-9 out-of-bounds get/set raises
Scenario: SC-L006-10 wrong value type per mode raises (int into RGBA, tuple into indexed, index 300)
Scenario: SC-L006-11 indexed fill_rect fills the sub-rect; outside stays 0
Scenario: SC-L006-12 fill then fill_rect clipped at origin; zero-size / fully-outside rects are no-ops
Scenario: SC-L006-13 in_bounds is correct at the edges
```

### Feature: Region / blit / resize / copy (REQ-P1-LOGIC-007)
```gherkin
Scenario: SC-L007-1 region copy is independent of the original
Scenario: SC-L007-2 out-of-bounds / zero-size region raises
Scenario: SC-L007-3 blit overwrite clips (1px lands); fully-clipped blit is a no-op
Scenario: SC-L007-4 blit with a mode mismatch raises
Scenario: SC-L007-5 blit blend on an indexed buffer raises
Scenario: SC-L007-6 blit blend composites alpha (opaque result, red>blue)
Scenario: SC-L007-7 resize pad+crop preserves content; padded area transparent
Scenario: SC-L007-8 resize with an offset places content at the offset; rest transparent
Scenario: SC-L007-9 copy is equal and independent
Scenario: SC-L007-10 __eq__ vs "x" is False and differs across modes; data is uint8; repr contains "PixelBuffer(2x2"
```

### Feature: Drawing primitives (REQ-P1-LOGIC-008)
```gherkin
Scenario: SC-L008-1 pencil in-bounds returns [(x,y)] and paints; out-of-bounds returns []
Scenario: SC-L008-2 pick_color reads the pixel
Scenario: SC-L008-3 line horizontal exact sequence; diagonal includes (2,2) and paints (3,3)
Scenario: SC-L008-4 line single point returns [(2,2)]
Scenario: SC-L008-5 line vertical exact sequence
Scenario: SC-L008-6 line steep (0,0)->(1,4) includes endpoints, length 5
Scenario: SC-L008-7 line clips out-of-bounds endpoints (negative skipped, positives painted)
Scenario: SC-L008-8 rectangle outline is perimeter only (centre not included)
Scenario: SC-L008-9 rectangle filled includes centre; 3x3 -> 9 coords
Scenario: SC-L008-10 rectangle normalises swapped corners (same set both orders)
Scenario: SC-L008-11 ellipse outline non-empty; filled has more coords than outline
Scenario: SC-L008-12 ellipse various aspect ratios stay in bounds
Scenario: SC-L008-13 ellipse degenerate (0,0,5,0) becomes a line including endpoints
Scenario: SC-L008-14 flood_fill fills a contiguous region (8 coords); the other half untouched
Scenario: SC-L008-15 flood_fill is a no-op when the seed already equals the value -> []
Scenario: SC-L008-16 flood_fill with an out-of-bounds seed -> []
Scenario: SC-L008-17 flood_fill indexed fills the whole 3x3
Scenario: SC-L008-18 flood_fill tolerance: near-match included, far excluded
Scenario: SC-L008-19 _matches type mismatch (int vs tuple) returns False
```

### Feature: Reversible command history (REQ-P1-LOGIC-009)
```gherkin
Scenario: SC-L009-1 PixelEdit execute applies, undo reverts, len counts changes
Scenario: SC-L009-2 FunctionCommand runs its do/undo callables
Scenario: SC-L009-3 History push executes, undo reverts, redo re-applies; can_undo/can_redo track state
Scenario: SC-L009-4 push(execute=False) does not re-apply an already-applied change; undo still works
Scenario: SC-L009-5 a new push after undo clears the redo stack
Scenario: SC-L009-6 undo/redo on empty history return None
Scenario: SC-L009-7 History(limit=2) after 4 pushes has undo_depth 2 (oldest dropped)
Scenario: SC-L009-8 History(limit=0) and limit=-1 raise ValueError
Scenario: SC-L009-9 clear empties both stacks
Scenario: SC-L009-10 record_edit captures a drawing op, sets label, undo reverts
Scenario: SC-L009-11 record_edit ignores unchanged pixels (RED over RED -> len 0)
Scenario: SC-L009-12 record_edit round-trip via History (flood_fill, execute=False); undo reverts
```

### Feature: Document state tree (REQ-P1-LOGIC-010)
```gherkin
Scenario: SC-L010-1 a new document has one frame, one "Background" layer, correct w/h
Scenario: SC-L010-2 a document accepts a palette + metadata; INDEXED mode preserved
Scenario: SC-L010-3 layer opacity 0.5 accepted; 1.5 raises; opacity="x" raises; repr contains "Layer"
Scenario: SC-L010-4 Frame(duration_ms=0) raises; repr contains "Frame("
Scenario: SC-L010-5 add_layer -> 2 layers; remove_layer(1) returns it -> 1 layer
Scenario: SC-L010-6 removing the last layer is refused
Scenario: SC-L010-7 remove_layer(9) bad index raises
Scenario: SC-L010-8 move_layer(1,0) puts the top layer first; a bad index raises
Scenario: SC-L010-9 add_frame -> 2 frames with recorded duration; remove_frame -> 1
Scenario: SC-L010-10 removing the last frame is refused
Scenario: SC-L010-11 add_layer(frame_index=3) bad frame index raises
Scenario: SC-L010-12 resize_canvas(8,8) resizes all buffers, preserves pixel (0,0); repr contains "Document(8x8"
```

### Feature: MaxRects compaction (REQ-P1-LOGIC-011)
```gherkin
Scenario: SC-L011-1 compact returns a Packing containing all input ids
Scenario: SC-L011-2 15 rects into 128x128 are all within bounds with no pairwise overlaps
Scenario: SC-L011-3 compact accepts Rect namedtuples
Scenario: SC-L011-4 compact is deterministic (equal output for equal input)
Scenario: SC-L011-5 empty input gives empty placements, width 0, height 0
Scenario: SC-L011-6 a rect bigger than the atlas gives reason=="does-not-fit"
Scenario: SC-L011-7 bad atlas bounds (0,10) give reason=="invalid-input"
Scenario Outline: SC-L011-8 malformed rects raise CompactionError  Examples: wrong-arity | negative | non-int 1.5
Scenario: SC-L011-9 four 40x40 into 64x64 give reason=="does-not-fit" (area exhausted)
Scenario: SC-L011-10 the -m smoke entrypoint returns 0
Scenario: SC-L011-11 property: 1..8 rects (w,h 1..20) into 256x256 are all placed with no overlaps
```

### Feature: `.pixproj` I/O with defensive validation (REQ-P1-DATA-001)
```gherkin
Scenario: SC-D001-1 round-trip preserves w/h/mode/palette/metadata/frame count/durations/pixels/layer names
Scenario: SC-D001-2 indexed round-trip preserves mode and index value
Scenario: SC-D001-3 save keeps an existing .pixproj suffix/name
Scenario: SC-D001-4 serialize shape: format "pixproj", version 1, canvas {w,h,mode:"rgba"}
Scenario Outline: SC-D001-5 deserialize rejects malformed payloads
  Examples: missing format | format!="pixproj" | version=99 | missing canvas | width=0 |
            width=999999 | mode="cmyk" | palette not a list | empty frames | empty layers |
            duration_ms=0 | layer data not base64
Scenario: SC-D001-6 deserialize rejects a wrong payload size (valid-but-too-short buffer)
Scenario: SC-D001-7 deserialize rejects a bad palette entry ("#GGGGGG")
Scenario: SC-D001-8 deserialize rejects >256 palette colours (300 entries)
Scenario: SC-D001-9 load of a missing file raises ProjectIOError
Scenario: SC-D001-10 load of invalid JSON raises ProjectIOError
Scenario: SC-D001-11 load of non-object JSON (a list) raises ProjectIOError
Scenario: SC-D001-12 defaults applied for optional fields (missing metadata -> {}, missing visible -> True)
```

Scenarios for REQ-P1-LOGIC-012 (constants) and REQ-P1-LOGIC-013 (Qt-free purity) are
verified by the S12 gather review + `check_layering`/`check_cycles` (Article I/II)
rather than by unit scenarios; they are recorded as **spec-only** in `traceability.md`.

---

## 12. Exit / status

- Spec authored; retroactive; all ordinary ambiguities resolved from code (§10).
- No open clarification blocks planning.
- Scope-attribution items surfaced for orchestrator adjudication (§8); Phase-1
  requirement gaps recorded (§7); S12 findings recorded for AGT-01/AGT-03 (§9).
- **STATUS: COMPLETED.**
