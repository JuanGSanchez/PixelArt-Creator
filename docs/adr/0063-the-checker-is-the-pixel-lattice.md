# ADR-0063 — The checker is the pixel lattice: transparency-checker semantics, texture-brush rendering, the LOD floor, the 1:1 zoom floor, corner-to-centre panning, and viewport-coupled update mode

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-08-25 (`20260825-canvas-grid-semantics` `implementation-plan.md` §1 root-cause analysis, §2 target state, §3 design decisions); recorded 2026-08-25 |
| Author | Architecture |
| Feature | `fix-canvas-grid-semantics` (job `20260825-canvas-grid-semantics`) — `REQ-CGS-LOGIC-001`, `REQ-CGS-UI-001`, `-002`, `-003`, `-005`, `-006`, `-009`, `-010` |
| Grounded by | `logic/constants.py` (`TILE_SIZE`, `DEFAULT_CANVAS_WIDTH`/`-HEIGHT`, `CHECKER_CELL_PX`, `CHECKER_MIN_ON_SCREEN_EDGE_PX`, `ZOOM_MIN`); `ui/canvas_scene.py` (`_CheckerBrush`, `_build_checker_brush`, `_fill_checker`); `ui/canvas_view.py` (`_viewport_update_mode_for`, `Canvas_View.setViewport`, `_clamp_zoom`, `_apply_pan_margin`); the field report quoted in `implementation-plan.md` §0 |
| Supersedes | The 2026-08-24 `min(ZOOM_MIN, fit_zoom)` zoom-floor reasoning (§4 below) |
| Superseded by | — |
| Relates to | ADR-0011 (rendering baseline this batch amends), ADR-0057 (the same "framework does the culling" posture applied here to `QTableView`, applied here to a device-space vs. document-space unit separation instead) |

## Context

A user reported four symptoms in one session: what they drew was invisible until they moved a
selection; the eraser and the line tool showed the same symptom; recorded frames did not clearly
match what they had drawn; and — the largest item — they had misread which squares on screen were
the pixels. The last symptom was not a misreading. It was manufactured by the renderer.

**The transparency checker and the render-culling tile were one constant wearing two meanings.**
`ui/canvas_scene.py`'s `_paint_checker_tiles` drew the alternating-square background at
`TILE_SIZE` document pixels per square. `TILE_SIZE` is declared in `logic/constants.py` as
`# viewport tile-culling tile edge, px (S1)` — a rendering-performance quantity, reused without
comment as the transparency-checker's own quantity. `TILE_SIZE` is 64, and so, independently, are
`DEFAULT_CANVAS_WIDTH` and `DEFAULT_CANVAS_HEIGHT`. **A brand-new default document was therefore
exactly one checker square.** The canvas looked like a single cell inside an apparently endless
grid of identical cells, and a user drawing "inside a cell" coloured 1/4096th of it. This
coincidence is the part a future reader most needs, because it is the reason the conflation went
unnoticed at every prior review: the canvas and the cell were the same size, so nothing on screen
ever showed them coming apart. The checker also did not stop at the canvas edge and no border
marked the drawing surface from the void around it, and the real pixel-grid overlay shipped off by
default (`ui/canvas_scene.py` `self._grid_enabled = False`) and was overwritten back to unchecked
by `main_window`'s own menu-action wiring even where a caller tried to turn it on — so the only
lattice a new user ever saw was a 64-pixel checker that meant nothing.

Three further, independently-diagnosed defects rode alongside this one and are recorded together
because one fix touches the same rendering path as all four: a GL viewport that cannot honour this
product's partial-repaint commits (closed by decision 6, below, not itself the subject of this
record); zoom below 1:1 point-sampling isolated pixels out of existence (decision 4); and recorded
frame thumbnails independently dropping roughly a quarter of a sparse drawing to the same
point-sampling mechanism (established, not merely suspected, by reading `ui/timeline_panel.py`;
fixed on the thumbnail's own terms and out of this record's scope, since the canvas itself stops
minifying once decision 4 lands).

For reference, Aseprite sizes its checker in **sprite pixels** and scales it with zoom (its shipped
default is 16×16, zoom-aware) — a document-space quantity, which is the established semantic this
batch adopts. The value chosen here, 1, is this project's own user ruling, not Aseprite's default.

## Decision

**Six decisions, recorded together because they share one root cause and one rendering path.**

### 1. `CHECKER_CELL_PX` is a new, document-space constant, semantically distinct from `TILE_SIZE`

`logic/constants.py` declares `CHECKER_CELL_PX: int = 1` — the transparency-checker square edge,
in document pixels, so it scales with zoom the way a document-space quantity should. `TILE_SIZE`
(= 64, the viewport-cull render edge), `DEFAULT_TILE_WIDTH`/`-HEIGHT` (= 16, the tileset content
tile) and `CRDT_TILE_SIZE_PX` (= 64, the collaboration transport tile) are **unchanged** — every
call site of every one of them is untouched, and the module stays a leaf with no intra-package
imports. `CHECKER_CELL_PX` is now clipped to the canvas rect, on a flat workspace ground colour,
with a cosmetic border (`CANVAS_BORDER_WIDTH_PX = 1`, a device-space pen width, deliberately a
different unit from the two document-space constants it sits beside in the file).

The coincidence that hid the conflation — `TILE_SIZE == DEFAULT_CANVAS_WIDTH ==
DEFAULT_CANVAS_HEIGHT == 64` — is recorded above in Context, deliberately, and not merely as
colour: it is the reason a future reader must not read the old conflation as an oversight-free
design that this record is arbitrarily changing. It was never a documented value; it was an
accident that happened to be self-consistent for exactly one canvas size.

### 2. The checker is rendered as one cached texture-brush fill, not a per-cell loop — a measured ruling, not a style preference

`ui/canvas_scene.py`'s `_build_checker_brush` builds one `QPixmap` of edge `2 * CHECKER_CELL_PX`
document pixels — one full checker period — filled with four `fillRect` calls, wrapped in a
`QBrush`, and cached; `_fill_checker` then paints any exposed region with exactly one `fillRect`
call against that brush (Qt's own brush tiling reproduces the whole pattern regardless of the
filled area), or against a flat blend colour below the LOD floor (decision 3).

**Measured, at `cell = 1` over a 1920×1080 region:** the cached texture-brush fill costs **1.96
ms**; a naïve per-cell `fillRect` loop over the same region extrapolates to **~2841 ms** — roughly
177× the 16 ms frame budget. At one checker cell per document pixel, the brush is not a
micro-optimisation available to skip; it is the only implementation that keeps the canvas inside
its frame budget at all.

**Departure from the plan's own earlier wording, recorded so it is not mistaken for a
simplification later.** No brush transform is installed. At `cell == CHECKER_CELL_PX == 1` a
`QBrush` transform would be the identity — the checker period is already painted into the pixmap
as a whole number of texture pixels, which cannot be resampled, so a transform call would do
nothing except invite a later reader to assume a scaling seam is being handled there. The
transform is named in the code as the mechanism to reach for **if** a non-integer
`CHECKER_CELL_PX` is ever introduced; it is not present today because there is nothing for it to
do today.

### 3. The LOD bound is stated as a bound, not a number, and 3.0 was caught and withdrawn

Below `CHECKER_MIN_ON_SCREEN_EDGE_PX` device pixels per cell, the checker pattern degrades to a
flat blend rather than aliasing into moiré. The shipped value is **1.0**, and the binding
constraint on that value is not "small enough to look fine" — it is that the LOD floor **must
never fire at the 1:1 zoom floor** (decision 4) where `CHECKER_CELL_PX = 1` renders at exactly 1.0
device pixels per cell. Any value strictly greater than 1.0 would blend the checker at 100 % zoom,
the product's single most common zoom level, and silently repeal `REQ-CGS-UI-003` — "one square is
one pixel" — at the exact moment it matters most.

This is not hypothetical. An earlier draft of this batch proposed **3.0** and was caught at the
requirements gate before it shipped. The comparison in `_fill_checker` is written in the positive
form — `cell_edge_px >= CHECKER_MIN_ON_SCREEN_EDGE_PX` draws the pattern — deliberately mirroring
the shipped pixel-grid gate's own phrasing, because the inverted form (`< floor draws the pattern`)
repeals the requirement silently at the boundary the moment someone edits the comparison without
re-deriving which side is "on." A test makes the bound machine-checkable; it was verified by
mutation that setting the constant back to 3.0 fails that test.

### 4. The 1:1 zoom floor is now flat, and it explicitly supersedes an earlier ruling

`Canvas_View._clamp_zoom` floors zoom at `ZOOM_MIN` (= 1.0), unconditionally. Below 1:1 the canvas
is minified by a `QPainter` with `SmoothPixmapTransform` off — nearest-neighbour point sampling —
so an isolated pixel that falls between sample points is not drawn at all, and reappears only when
the sampling grid happens to re-align, which is exactly what dragging a selection does. That
mechanism, independent of the checker conflation above, produced the same "my drawing was invisible
until I moved it" symptom the user reported for the eraser and the line tool as much as for the
brush.

**Accepted trade-off, put to the user and accepted:** a document larger than the viewport can no
longer be zoomed out to show the whole grid at once; it is reached by panning instead.
`Canvas_View.fit()` is clamped by the same floor, so a document larger than the viewport lands at
exactly 1.0 rather than a fractional whole-grid fit.

**Measured against a 1200×800 viewport** (`fix-canvas-grid-semantics` worktree, Python 3.13.13,
offscreen):

| Document | `fit()` before | `fit()` after |
| --- | --- | --- |
| 64×64 (the default) | 12.47x | 12.50x — unchanged |
| 256×256 | 3.12x | 3.12x — unchanged |
| 1024×1024 | 0.78x | **1.00x — floored** |
| 7680×4320 (8K) | 0.15x | **1.00x — floored** |

The floor only binds at roughly 1024 px and above; the default document and every document well
under that size are unaffected.

**This explicitly supersedes a 2026-08-24 ruling**, under which `_clamp_zoom` floored at
`min(ZOOM_MIN, fit_zoom)` so a very large document could always be zoomed out far enough to be seen
whole. Both dates are recorded because the shipped code's own commentary argued for the superseded
position until this batch replaced it: the 2026-08-24 reasoning was sound for grid *visibility*
alone, but it did not account for the point-sampling pixel loss that visibility bought.

### 5. Corner-to-centre panning is a VIEW scene-rect concern, with a derived (not constant) margin

The scene's own rect (`CanvasScene.sceneRect()`) is deliberately left untouched by this decision:
`Canvas_View._fit_zoom` reads it to fit the whole document, and tiled mode still rewrites it for
its own reasons. What changes is the **view's** scene rect — the scrollable range
`QGraphicsView.setSceneRect` governs — which `Canvas_View._apply_pan_margin` inflates by half a
viewport's worth of scene units on every side (plus one screen pixel of slack, converted to scene
units, so Qt's scrollbar-range rounding does not fall one pixel short of the far corner).

The margin is **derived at each call**, from the live viewport size and the current zoom, rather
than hoisted into a constant: a fixed pixel value is correct at exactly one window size and one
zoom and wrong at every other, and this view's margin must track both `resizeEvent` and every zoom
change (`set_zoom`, `wheelEvent`).

**Measured:** with the scene rect equal to a 512-px document and a 224-px viewport at zoom 1, the
unmargined view lets the viewport centre reach only scene `[111, 399]` per axis — no corner of the
document can ever be centred, because the scrollable range stops half a viewport short of each
edge.

**Consequence recorded honestly, not minimised:** the view's own scene rect now has a negative
origin (the margin extends past `(0, 0)` on the low side). This invalidated a coordinate assumption
that had been duplicated, unexamined, across several test modules, which the fix's regression
suite corrects at each site rather than papering over centrally.

### 6. The viewport update mode now follows whichever viewport is actually installed

Qt 6 documents `FullViewportUpdate` as "the preferred update mode for viewports that do not
support partial updates, such as `QOpenGLWidget`" and states that `MinimalViewportUpdate` is
`QGraphicsView`'s own default — but Qt does not switch the mode for you when a GL viewport is
installed; the default stands regardless of what `setViewport` was just given. `Canvas_View` now
overrides `setViewport()` so that installing any viewport re-derives the update mode from that
viewport via `_viewport_update_mode_for` (checked with `QObject.inherits("QOpenGLWidget")`, not
`isinstance`, so the module stays import-free of the GL module at module scope — a headless run
with no system GL library must not fail merely importing `ui/`).

**Why an override rather than a private helper called only from the GL-install path:** it makes
the production install path (`Canvas_View._install_viewport`) and the test path (any caller,
including this fix's own regression test, invoking `setViewport` directly) the same code path,
with no mock standing in for either.

**Its limit, stated rather than left implicit:** `QAbstractScrollArea::setViewport` is
**non-virtual** in Qt's C++, so the constructor's own default-viewport installation never routes
through this Python override at all — the `MinimalViewportUpdate` set explicitly at construction
is the base case for that default viewport and is left untouched by this decision. The override
only fires for a viewport installed through an explicit `setViewport(...)` call made after
construction, which is exactly the GL-install branch and the only branch that needs it.

## What this ADR does NOT claim

**No claim is made, anywhere in this record, that a headless test proves a real OpenGL viewport
flushes to a real screen.** It does not, and could not: `QGraphicsView.render()` always takes the
raster path regardless of which viewport widget is installed, headless or not. The update-mode
assertion in decision 6's regression test is a documented-behaviour proxy — it proves the mode Qt
documents as correct is the mode this view sets for the viewport it was given, nothing more. This
batch's confidence in the GL-viewport symptom actually being fixed closes on the user's own
confirmation from their own build, not on anything this test suite can observe from inside an
offscreen run. An ADR that overstated this test's evidence would be worse than one that records the
gap plainly.

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| Keep `TILE_SIZE` as the checker's own quantity and simply shrink its value | Rejected — it would still be one constant serving two independently-tunable concerns (render-culling edge vs. transparency-checker edge), reintroducing the identical conflation risk at a different number the next time either concern needed to change |
| Per-cell `fillRect` loop instead of a cached texture-brush fill | Rejected on the measurement in decision 2 — ~2841 ms extrapolated against a 16 ms frame budget at `cell = 1`, roughly 177× over budget |
| A non-unity `CHECKER_MIN_ON_SCREEN_EDGE_PX` (the withdrawn 3.0 draft) | Rejected at the requirements gate — it blends the checker pattern at 100% zoom, the product's most common zoom level, repealing `REQ-CGS-UI-003` at the boundary that matters most |
| Keep the 2026-08-24 `min(ZOOM_MIN, fit_zoom)` floor so an 8K document can always be viewed whole | Superseded (decision 4) — it did not account for nearest-neighbour point sampling dropping isolated pixels below 1:1, which produced the reported "invisible until moved" symptom independent of the checker conflation |
| A fixed pixel-count pan margin | Rejected — correct at exactly one window size and zoom, wrong at every other; the margin must be derived from the live viewport size and zoom (decision 5) |
| A private helper invoked only from the GL-install branch, instead of overriding `setViewport()` | Rejected — it would leave the test path exercising a different call sequence than production, reintroducing the discrimination-by-hand-written-condition shape this project has already paid for once (ADR-0057's CF-56 finding, a distinct defect in a different widget, cited here only as the shape to avoid repeating) |

## Consequences

**Accepted costs.** A document at or above roughly 1024 px can no longer be viewed whole in one
frame; it is reached by panning, an explicit user-accepted trade-off (decision 4). The view's own
scene rect now carries a negative origin, which required correcting a coordinate assumption
duplicated across several test modules (decision 5). `CHECKER_MIN_ON_SCREEN_EDGE_PX` is a value
with a hard upper bound (`<= 1.0`) rather than a free tuning knob, and any future change to it must
re-derive that bound rather than treat it as ordinary perf tuning (decision 3).

**What this enables.** The checker now means exactly one thing — one square is one document pixel,
clipped to the canvas, bordered — so the misreading the user reported cannot recur at any canvas
size, including the 64×64 default that manufactured it. The texture-brush mechanism is proven, by
measurement, to hold the frame budget at the smallest possible cell size, so no future change to
`CHECKER_CELL_PX` toward smaller values is blocked by this rendering path. The `setViewport()`
override gives every future viewport swap — GL or otherwise — the Qt-documented-correct update mode
automatically, without a second call site to remember.

**What it constrains.** No future write path may reintroduce `TILE_SIZE` as a stand-in for
`CHECKER_CELL_PX`, or vice versa — the two are now named, distinct constants in
`logic/constants.py` precisely so that substitution is a visible diff, not a silent reuse. No
future change to `CHECKER_MIN_ON_SCREEN_EDGE_PX` may raise it above 1.0 without also revisiting
`ZOOM_MIN`, since the two constants are bound together by decision 3's constraint. Any code that
installs a `QAbstractScrollArea` viewport on this view outside `setViewport()` (there is no such
path today) would bypass decision 6's mode-following guarantee.

## What has no detector, stated rather than implied

No script proves that a future call site reintroduces `TILE_SIZE` where `CHECKER_CELL_PX` belongs,
or the reverse; nothing greps for that confusion on every commit. No test exercises a real GL
context rendering to a real screen — the limit stated above in "What this ADR does NOT claim" has
no automated counterpart and is closed only by the user's own confirmation from their build. These
are review invariants against this decision's mechanism, not gates that run.
