# ADR-0064 — Every `&Image` geometry operation is whole-document: the shared geometry seam is removed, the run is cost-gated, chunked on the GUI thread, and atomically cancellable

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-08-25 (four user rulings Q-1..Q-4, recorded in `spec.md` §4.3, §5, §8); recorded 2026-08-25 |
| Author | AGT-01 (Architecture) |
| Feature | `canvas-scale-defects` (job `20260825-canvas-grid-semantics`, work item `canvas-scale-defects`) — `REQ-CSD-UI-001`..`-015`, `REQ-CSD-LOGIC-001`..`-003`, `REQ-CSD-DATA-001`..`-004` |
| Grounded by | `ui/canvas_scene.py:1758-1774` (`CanvasScene.rebind_active`, the seam); `ui/main_window.py:4330-4358` (`_apply_buffer_command`), `:4362-4375`, `:4411`, `:4461` (the three call sites); `logic/transform.py:1,19,29-38,94-102`; `logic/rotsprite.py:291-296,299,325,376-386`; `logic/document.py:313,1005-1019`; `ui/commands.py:220,659-760`; `data/project_io.py:97,283-286,539-543,554,564,591`; `logic/constants.py:9-10,641-647`. All read on branch `fix-canvas-grid-semantics` at HEAD `35b63bf` |
| Supersedes | The Phase-2 active-layer scope of `Image ▸ Scale…`, `Rotate 90 CW/CCW` and `Flip H/V`; the `SCALE_MIN_FACTOR` / `SCALE_MAX_FACTOR` factor cap (deleted, see decision 5) |
| Superseded by | — |
| Relates to | ADR-0001 (Article II governs *tuning* parameters — the test this record applies both to the new threshold constant and to the two deleted ones); ADR-0002 (RotSprite's deterministic implementation, whose dimension-preserving property is what makes RotSprite a GUARD here and not a defect); ADR-0006 / ADR-0011 (the layer model and the frame model — the two dimensions the Phase-2 transforms were written before, and never revisited for); ADR-0063 (the same branch's rendering batch — a different defect on a different path, cited only for the shared worktree and job) |

## Context

**An operation's scope stopped matching its model, and nobody noticed for two phases.**

`Image ▸ Scale…` and `Image ▸ Rotate 90 CW/CCW` shipped in Phase 2. At that time a
`Document` **was** a single pixel buffer, so "transform the active layer" and "transform
the document" named the same set of bytes, and operating on the active layer was not a
compromise — it was correct. Phase 4 then added the layer tree (ADR-0006) and Phase 5
added frames (ADR-0011). **Neither revisited the Phase-2 transforms.** The model gained
two dimensions; the operation's scope gained none. That is the whole root cause, and it
is the part a future reader most needs, because the code never looked wrong at any single
review: each line of `_on_scale` is correct against the model it was written for.

**The consequence is data loss, not a cosmetic inconsistency.** `.pxproj` carries **no
per-layer geometry**. Every layer payload is written at the canvas header's
width/height (`data/project_io.py:283-286`) and `_decode_buffer` hard-requires
`len(raw) == width * height * channels` (`:539-543`). So "the document's declared
geometry" and "every layer's actual geometry" are one fact stored once, and any code path
that can make them disagree is a file-corrupting bug generator rather than a feature.
Three menu actions could make them disagree, via one shared write:

`CanvasScene.rebind_active` (`ui/canvas_scene.py:1766-1768`) force-synced
`Document.width`/`height` **from a single layer's buffer**. The complete caller set was
established by `grep` over `pixelart_creator/` and `tests/` — one production call site
(`ui/main_window.py:4340`), whose caller `_apply_buffer_command` has exactly three call
sites — so the following is the whole seam, not a sample:

| Menu action | Reaches the seam? | Result |
| --- | --- | --- |
| `Image ▸ Scale…`, no selection, target differs | yes | **loud corruption** — the file cannot be reopened (`ProjectIOError`) |
| `Image ▸ Rotate 90`, **non-square** document | yes | **silent corruption** — see below |
| `Image ▸ Rotate (RotSprite)`, no selection | yes, always | none — the write is a **no-op** (decision 6) |
| `Image ▸ Scale…` with a selection; square `Rotate 90`; `Flip H/V`; RotSprite with a selection | no (`PixelEdit` path) | none |

**The silent case is the dangerous one and is worth stating precisely.** A rotate-90 swaps
the axes, so a 64×48 layer becomes 48×64 — the *same number of bytes*. The document
header is then rewritten to the rotated layer's dimensions while every other layer keeps
the original ones. On reload, `_decode_buffer`'s length check **passes** for every layer,
because the byte count coincides. The file opens without a single error and every
untransformed layer's art is reinterpreted at the wrong stride: **silently scrambled**.
There is no diagnostic, no exception, and no visual cue at save time. This is why the
batch treats a byte-count coincidence as an active hazard rather than a lucky escape,
and why the persistence requirements (`REQ-CSD-DATA-002`) assert **pixel identity**
rather than a successful round-trip.

Two further faults were found on the same paths and are closed by the same decision. The
scale factor was capped at `SCALE_MAX_FACTOR = 64.0`, which refuses a legitimate
64×64 → 7680×4320 scale (factor 120) while permitting a 7680-source scale that overshoots
the canvas ceiling — the cap is the wrong *shape*, not the wrong number (decision 5). And
`Image ▸ Flip H/V` worked correctly, which is exactly why it needed a decision rather than
a fix (see **Classification**, below).

## Decision

**Every geometric operation in the `&Image` menu acts on the WHOLE DOCUMENT — every layer
and every mask in every frame.** The family is `Scale…`, `Rotate 90 CW/CCW`,
`Rotate (RotSprite)` and `Flip H` / `Flip V`. Seven decisions follow, recorded together
because they share one root cause and one call path.

### 1. The corrupting write is removed, not worked around per caller

The three lines in `CanvasScene.rebind_active` that derive `Document.width`/`height` from
`self._active_layer.buffer` are **deleted**. The method becomes what its own docstring
already claimed: a re-read and re-render. Everything below the deleted lines already reads
`self._document.width`/`height` through `_apply_scene_rect`.

**The alternative — teaching `_on_scale` to loop over the layers itself — was put to the
user and explicitly rejected** (ruling Q-3), because it leaves the identical
file-corrupting write live behind `Rotate 90`. It is rejected on structure as well: three
call sites would each carry their own copy of the enumeration, the cost gate and the
progress loop, and a fourth would join them when the flips landed.

**Ordering is a correctness precondition, not a detail.** The deletion removes the only
code that currently writes `Document.width`/`height` on these paths; the replacement
writer is the new logic command's `_do`, which is not *reached* until `ui/main_window.py`
routes the unmasked paths through the runner. Landing the deletion before that routing
would leave `Image ▸ Scale` resampling one layer while the document geometry never moved
— a different silently-wrong state, not a smaller one. This is the one ordering
constraint in the batch **whose violation no failing test catches**: the intermediate tree
imports, runs, and saves a file.

### 2. The run engine is a Qt-free logic module; the Qt parts are two thin `ui/` modules

Three new modules, placed by `check_layering` / `check_cycles` and not by reading
(see *Verification*):

- **`logic/doc_transform.py`** (Qt-free, Article I.1) — enumerates the buffers, costs the
  run, steps the resample, and builds the reversible command.
- **`ui/document_transform_dialogs.py`** — the confirm and progress dialogs. Presentation
  only: no enumeration, no cost arithmetic, no resampling.
- **`ui/document_transform_runner.py`** — Qt orchestration: cost gate → progress dialog →
  step chain → command, or `None`. No domain arithmetic.

`ui/commands.py` is **not** touched: the shipped `LogicCommand` (`:220`) already bridges an
unapplied `history.Command` plus a rebind callback, which is exactly what the new builder
returns into.

**Why a module and not methods on `Document`:** the run is not model state. It is a
bounded, cancellable *process over* the model with a lifetime shorter than any document's.
Putting it on `Document` would give the model a mutable in-flight cursor only one caller
may ever hold, and would make `Document` the owner of a cost policy it does not otherwise
consult.

**The future load this boundary is bought for is named and concrete.**
`ui/batch_recolour_panel.py`, `ui/batch_export_panel.py`, `ui/procgen_panel.py` and
`ui/script_runner_panel.py` each already own a `QProgressBar` and their own worker, and
each already applies an operation across a document. When one of them is asked to apply a
geometry transform in bulk — the natural next request once the `&Image` menu is
document-wide — it needs the enumeration, the cost estimate and the stepwise resample
**without** the modal dialog. `DocumentTransformRun` is driveable from a worker thread
unchanged under decision 4's contract; only the thin `ui/` runner is replaced. That
extension point costs one module boundary.

**What is deliberately NOT built, and this is the other half of the same judgment:** no
transform registry, no operation plug-in interface, no generic "document operation" base
class. Four operations, all already existing as plain `Callable[[PixelBuffer],
PixelBuffer]` in `logic/transform.py`, are passed as that callable. A registry would be
speculative generality for a set that has not grown since Phase 2 — the very phase whose
assumptions this record is correcting.

### 3. The run is bounded by a warn-and-confirm threshold — `DOCUMENT_TRANSFORM_CONFIRM_BYTES`

`logic/constants.py` gains one new number:

```python
DOCUMENT_TRANSFORM_CONFIRM_BYTES: int = 4 * MAX_CANVAS_WIDTH * MAX_CANVAS_HEIGHT * 4
# = 530,841,600 B = 506.25 MiB = 4 full 8K RGBA canvases
```

Spelled in terms of the existing platform constants, never as the bare literal
(Article II / ADR-0001: this is a **tuning** parameter, not an intrinsic one — a
maintainer may legitimately want to move it, and moving it changes no algorithm).
The comparison is **strictly greater than**: a projection landing exactly on the
threshold is silent.

**The name is a decision, not a label.** The specification proposed
`SCALE_CONFIRM_BYTES`; it is renamed because the constant is consulted by four
operations, only one of which is a scale. `logic/transform.py`'s own module docstring
already calls the family *"Buffer transforms: flip / rotate-90 / scale-NN"*, and the UI
helper is already `_apply_transform`, so "transform" is this codebase's existing noun for
exactly this set. A `SCALE_`-prefixed name consulted by `Flip H` is the same class of
error as `TILE_SIZE` doubling as the checker cell in ADR-0063 — one name carrying two
scopes — and it is cheaper to refuse now than to unpick later.

**The floor is FORCED, not chosen, and this is the load-bearing part of the derivation.**
One full 8K RGBA canvas is `7680 × 4320 × 4 = 132,710,400 B` — the platform's declared
resident unit, already spelled with this exact arithmetic at
`data/project_io.py:97`. A single-layer, single-frame document at the full ceiling is an
advertised, supported case and must stay silent; its worst-case peak is 1 result + 1
source = **exactly 2 units** (`265,420,800 B`) — and, critically, **that is true whether
it is scaled to the ceiling or merely flipped**, because the three area-preserving
members of the family produce a result the same size as their source. So the threshold
must be strictly greater than 2 units at every point in the family, which rules out both
2 units and the existing 256 MiB `MAX_CLOUD_PROJECT_BYTES` figure. 4 units is the
smallest power-of-two multiple clearing that forced floor with headroom; 3 units
(379.69 MiB) also clears it but leaves under half a unit of headroom, so an ordinary
two-layer 8K operation would prompt — the exact "the common case pays for the rare one"
outcome the user's ruling forbids.

Sanity-checked against ordinary work, computed rather than asserted: 32 buffers at
256×256 → 1024×1024 is 136.00 MiB (silent); 180 buffers at 128×128 → 512×512 is
191.25 MiB (silent); 32 buffers at 4096×2304 → 7680×4320 is 5.08 GiB (**prompt**).

**Warn-and-confirm, not refuse** (user ruling Q-1). The confirmation states the real
projected figure, formatted by `QLocale().formattedDataSize()` so no unit string is
authored and none can be mistranslated. The batch does **not** add a refusal.

### 4. The run is chunked on the GUI thread, and `Layer.buffer` is GUI-thread-confined for its duration

One buffer per chained zero-delay `QTimer.singleShot`, driven inside the progress dialog's
own modal event loop. **Not a worker thread, not a `QThreadPool`.** Four reasons, in the
order that decided it:

1. **Atomicity comes free and cannot be lost in a later refactor.** With a worker, results
   cross a thread boundary and someone must guarantee the commit happens on the GUI thread
   after the last result *and only then*. That guarantee would live in a queued-signal
   handler — reviewable, but a place a future edit can introduce a partial write. On the
   GUI thread there is no boundary to get wrong.
2. **Every cancellation scenario becomes synchronously observable.** A test connects to
   `stepped` and calls `cancel()` inside the slot: exact, ordered, no `waitSignal`, no
   timeout, no CI flake. Against a worker these become races that pass locally and fail on
   a loaded runner — and a flaky atomicity test is worse than none, because it teaches the
   team to re-run it.
3. **The dialog is modal by specification, so a thread buys nothing.** The user cannot
   paint or invoke another action during the run whichever thread does the work. Between
   steps the event loop runs normally, so the dialog paints and the cancel button is live.
4. **The mechanism is already this codebase's** — `QTimer.singleShot` plus a nested modal
   `exec()` loop is the shipped idiom throughout `ui/`. No new concurrency primitive, no
   new teardown path, nothing new to leak.

**Thread-safety ruling, stated positively so nobody re-derives it later.** (a)
`Layer.buffer` and `Layer.mask` are **GUI-thread-confined for the duration of a
whole-document geometry operation**: every read, every resample and the single commit
happen on the GUI thread inside one modal operation. (b) The event loop does spin between
steps, so other queued work runs; the one existing off-thread reader of layer data, the
composite warmer, delivers through a **queued** signal and writes only the *derived*
composite cache — it assigns no `Layer` attribute, so a warm landing mid-run is simply
superseded by the rebind at commit. (c) If a future caller drives the run from a worker
thread, the contract is fixed here in advance: the worker may call `step()` (it touches
only `PixelBuffer` data it was handed), but **`enumerate_targets` and the command's
`_do`/`_undo` must run on the GUI thread**, because those are the only points that read or
write a `Layer` attribute. That is the boundary, and it is why `step()` was given no
access to a `Layer` at all.

**Atomicity is a property of the shape, not of a guard.** The step loop never names a
`Layer`: it reads a retained source buffer and appends to a list. The only code that
assigns `layer.buffer` / `layer.mask` / `document.width` lives in the command's `_do`,
which cannot run before the command is built, which cannot happen before the last step.
Cancelling at step 0, at step `total-1`, and after the last step but before the command is
built are therefore **the same early return** — and "nothing reached the undo stack" holds
because no `QUndoCommand` was ever constructed, not because one was unwound.

### 5. `SCALE_MIN_FACTOR` / `SCALE_MAX_FACTOR` are DELETED, not widened

The scale bound becomes a clamp on the **resulting dimensions** (`1..MAX_CANVAS_WIDTH` ×
`1..MAX_CANVAS_HEIGHT`), evaluated **before** the array is allocated rather than after
`logic/transform.py` has already materialised it.

The two constants are removed rather than re-valued, and the reason is a matter of
principle rather than tidiness: **a factor cap loose enough to be correct at every source
size excludes nothing the dimension clamp does not already exclude, and a constant that
excludes nothing is a false guarantee.** It reads at three call sites like a safety bound
while enforcing nothing, which is worse than its absence. Article II's canonical table
does not list them, so no constitutional row changes. The Scale dialog derives its factor
range from the seeded source size instead (`[1/src_w, MAX_CANVAS_WIDTH/src_w]`, four
decimals), and `target_size()` — which reads only the two spin boxes — remains
authoritative.

### 6. RotSprite is a GUARD: it does **not** enter the pipeline

`_on_rotsprite` is left exactly as it is, scoped to the active layer. The specification's
summary table groups RotSprite into "the family" in the sense that it is a *caller of the
seam*; `REQ-CSD-UI-007`'s normative text and an explicit acceptance scenario say in so
many words that it stays active-layer-scoped and presents neither dialog. **Requirement
text and an explicit scenario are normative; a summary table's grouping is not.**
RotSprite's only exposure to this batch is the seam deletion, whose effect on it is
provably nil — the deleted write was already a no-op (decision 7).

### 7. `.pxproj` does not change: no schema change, no version bump

`data/project_io.py` is not edited. The format's existing invariant — one geometry, at the
canvas header — is *restored* rather than extended. Adding per-layer geometry to the
format was considered and rejected as a strictly worse answer to the same defect: it would
make the corrupt states **representable** instead of impossible. `REQ-CSD-DATA-001`..`-004`
are therefore round-trip *consequences* of decisions 1–2, not format work.

## Classification — DEFECT vs GUARD vs CHANGE

**This section is the one a future reader is most likely to need and most likely to get
wrong. It is normative.** Three operations in this batch were never broken. Two of them
are being changed anyway, deliberately, on the user's explicit ruling.

| Operation | Class | Was it broken before this batch? |
| --- | --- | --- |
| `Image ▸ Scale…` (no selection, target differs) | **DEFECT** | **Yes** — loud `.pxproj` corruption; fixed here |
| `Image ▸ Rotate 90 CW/CCW`, **non-square** document | **DEFECT** | **Yes** — silent `.pxproj` corruption (scrambled art, length check passes); fixed here |
| The scale factor cap (`SCALE_MAX_FACTOR = 64.0`) | **DEFECT** | **Yes** — refused legitimate targets and permitted over-ceiling ones; fixed here (decision 5) |
| `Image ▸ Rotate (RotSprite)` | **GUARD** | **No.** Dimension-preserving by construction; its seam write was a no-op. Non-regression only |
| `.pxproj` round-trip after RotSprite / after a flip | **GUARD** | **No.** Passes today and must keep passing |
| `Image ▸ Rotate 90 CW/CCW`, **square** document | **CHANGE** | **No — it was CORRECT.** Deliberately widened to whole-document for scope consistency |
| `Image ▸ Flip H` / `Image ▸ Flip V` | **CHANGE** | **No — they were CORRECT.** Deliberately widened to whole-document for scope consistency |

**The flips and square rotate-90 must NEVER be recorded as defects — not in this ADR, not
in the changelog, not in a release note, not in a future post-mortem.** They are
dimension-preserving, they take the `PixelEdit` path, they **never reach the seam**, and
they corrupt nothing. They worked correctly by every standard this batch applies to the
other operations. Nothing about them was broken.

**Why they change at all.** The user chose consistency (ruling Q-4). Leaving them
active-layer-scoped would make two adjacent items in one menu behave oppositely with no
cue to the user:

> After this batch, `Image ▸ Rotate 90 CW` on a 48×48 document transforms every layer,
> while `Image ▸ Flip H` on the same document would transform only the active one.

That is not a defect anyone could have filed before this batch; it is an inconsistency
*created* by fixing the neighbouring operations, and the user elected to remove it in the
same change rather than ship the seam. **Anyone reading this record in a year must
conclude: the flips were fine, and we changed them on purpose.**

Consequently the regression evidence differs by class, and conflating them would corrupt
the record: DEFECT rows must demonstrate a **failure** against the unfixed code; GUARD
rows must demonstrate a **pass** against the unfixed code; CHANGE rows record the prior
behaviour as **correct-and-superseded** and must not be written up as a fix.

## Provenance of this decision — including the premise that was wrong

Recorded plainly, because the shape of this decision is not derivable from the code alone.

**Four user rulings, 2026-08-25:**

1. **Q-1 — warn and confirm, do not refuse.** A large whole-document run is permitted; the
   user is told what it will cost first. This is why decision 3 is a threshold and a
   dialog, and not a hard cap.
2. **Q-2 — progress with cancel.** A determinate, modal, cancellable indicator, which is
   why decision 4 exists at all and why cancellation had to be made atomic by construction.
3. **Q-3 — fix the seam, not the callers.** A Scale-only fix was put to the user and
   explicitly rejected because it knowingly leaves the same corrupting write live behind
   `Rotate 90`.
4. **Q-4 — flips join the family for consistency.** The ruling recorded in
   **Classification** above.

**One premise was asserted, then CORRECTED on measurement.** Revision 1 of the
specification claimed `_on_rotsprite` "carries the identical desync". **That assertion was
false and was withdrawn.** It had been reasoned from the shared call path *without reading*
`logic/rotsprite.py`. Measured: `rotsprite()` reads `width, height` from the source and
returns a `PixelBuffer(width, height, mode)` — dimension-preserving by construction — so
the seam's write assigns the value it already held. The write is a no-op; there is no
desync, no invariant breach and no corruption on that path. This changed RotSprite's
requirement *kind* from a defect fix to a non-regression guard. **Specifying a corruption
fix for RotSprite would have been specifying a defect that does not exist**, and the only
reason it did not ship that way is that the file was eventually read. That is recorded
here rather than quietly dropped, because the failure mode — inferring behaviour from a
call graph instead of from the callee — is the same one that let the original Phase-2
scope survive two phases of review.

## Verification — placement proven by script, not by reading

Article I.4: `check_layering` and `check_cycles` are the source of truth for placement.
Both were run on `fix-canvas-grid-semantics` at `35b63bf` **before** this design was
settled, and the planned import edges were then probed against the same rule tables in
process:

```
$ python scripts/check_layering.py --json
check_layering: clean (220 modules; 2 root module(s), 0 exempt top-level package(s), 0 unregistered).
{ "exempt": {}, "root_modules": ["__init__.py", "__main__.py"],
  "scanned": 220, "unregistered": [], "violations": [] }
exit=0

$ python scripts/check_cycles.py --json
check_cycles: no cycles (222 modules).
{ "cycles": [], "edges": 833, "modules": 222 }
exit=0

planned-placement probe (ephemeral, stdlib only, discarded):
{ "modules_real": 222, "modules_with_planned": 225,
  "cycles_baseline": [], "cycles_with_planned": [],
  "layering_violations_planned": [], "VERDICT": "CLEAN" }
exit=0
```

The row that most deserved scrutiny is `logic/doc_transform.py` importing **both**
`logic/document.py` and `logic/transform.py`: `transform.py` deliberately avoids importing
`document.py` (it declares a structural `Protocol` instead), so the new module is the
first to join them. The probe confirms this closes no cycle, because neither imports it.

**The probe is a probe of the plan, not a substitute for the gate.** Both scripts must be
re-run over the implemented tree and must exit 0 (223/225 modules expected). **A script
exit of 2 is unresolved → BLOCKED, never "clean."**

## What this ADR does NOT claim

- **It does not claim the implementation has landed and passed.** The decision is settled —
  four user rulings, an approved specification, and a cross-artifact analyze gate that
  returned `VERDICT: CLEAN` with zero blocking findings — and this record was written
  **ahead of** the code, deliberately, so the classification above could not be
  reconstructed after the fact by someone reading a diff. The post-implementation gate
  (layering, cycles, coverage, the full UI suite) is owed and is not evidence this record
  carries.
- **It does not claim the threshold was measured.** `DOCUMENT_TRANSFORM_CONFIRM_BYTES` is
  **derived** from the platform's resident unit and a forced floor, not measured against
  real memory behaviour. A frame/memory-budget review by AGT-10 is scheduled; if it
  contradicts the derivation, the constant moves and this section is why that is not a
  contradiction of the record.
- **It does not claim the per-buffer step time was measured.** Decision 4 reason 3 calls a
  single 8K nearest-neighbour gather "sub-second" from the shape of the NumPy operation.
  **It was not timed.** If it proves long enough to make the GUI-thread choice feel
  unresponsive, decision 4(c) is written precisely so that revisiting costs one `ui/`
  module rather than a redesign.
- **It does not claim peak memory during a large run is small.** It is not: the worked
  32-buffer 8K example projects 5.08 GiB. That is out of scope by ruling Q-1 — the user
  chose to be warned, not refused — and the confirmation dialog states the real figure.

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| Fix `_on_scale` to loop over the layers itself, leaving `rebind_active` alone | Rejected by user ruling Q-3 — it knowingly leaves the identical corrupting write live behind `Rotate 90`. Also rejected on structure: three call sites would each carry a copy of the enumeration, cost gate and progress loop, and a fourth would join them with the flips |
| Add per-layer geometry to the `.pxproj` schema (v7) | Rejected — it makes the corrupt states *representable* rather than impossible. A format change is the wrong answer to a defect whose fix is to stop producing the state |
| Re-value `SCALE_MIN_FACTOR` / `SCALE_MAX_FACTOR` to a correct range instead of deleting them | Rejected — a factor cap wide enough to be correct at every source size excludes nothing the resulting-dimension clamp does not, so it would read like a safety bound at three call sites while enforcing nothing |
| Name the constant `SCALE_CONFIRM_BYTES` (as the specification proposed) | Rejected — four operations consult it and only one is a scale; the same one-name-two-scopes error as ADR-0063's `TILE_SIZE` conflation, caught before it shipped this time |
| Name it `GEOMETRY_OP_CONFIRM_BYTES` | Rejected — accurate, but introduces "geometry op", a noun **no module, class, function or docstring in this tree uses**, for a family that already has this codebase's own name ("transform") |
| A `QThreadPool` / `QRunnable` worker for the resample | Rejected on atomicity, determinism and the `Layer.buffer` ownership question it opens for no gain under a dialog that is modal by specification (decision 4) |
| A single blocking loop with no progress indicator | Refused by requirement — a whole-document run at 8K is not an operation that may freeze the window silently |
| Suppress the progress dialog below some duration (a `minimumDuration`-style threshold) | Rejected — it makes the progress requirement's own acceptance scenarios unassertable. The resulting flicker on a trivially fast 6-buffer flip is an accepted UX consequence of the specification, revisitable only by amending it |
| Put `DocumentTransformRun` on `Document` as methods | Rejected — it gives the model a mutable in-flight cursor only one caller may hold, and makes `Document` own a cost policy it does not otherwise consult (decision 2) |
| A transform registry / operation plug-in interface | Rejected as speculative generality — four operations, all already plain callables, for a set that has not grown since Phase 2 |
| Put RotSprite through the whole-document pipeline too, on the summary table's grouping | Rejected — the requirement text and an explicit acceptance scenario both say it stays active-layer-scoped and shows no dialog. Normative text beats a table's grouping (decision 6) |

## Consequences

**Accepted costs, stated as costs.**

- **A whole-document transform now touches up to every layer × mask × frame.** A 60-frame,
  3-layer document is 180 resamples where there was 1. That is the point of the change,
  and it is also its price: operations that were instant on a large animation are now
  bounded runs with a progress bar.
- **The confirmation threshold is derived, not measured**, and **its floor is FORCED** — a
  single-layer 8K document costs exactly 2 units whether scaled to the ceiling or merely
  flipped, so no threshold at or below 2 units is admissible, whatever a future measurement
  says. Any revision must re-derive against that floor rather than treat the number as free
  tuning.
- **`SCALE_MIN_FACTOR` / `SCALE_MAX_FACTOR` are gone**, so two shipped public constants
  disappear from `logic/constants.py` and three call sites plus two test comments change.
  Anything outside this tree importing them breaks — deliberately and loudly, which is the
  correct outcome for a bound that never bounded anything.
- **The run is GUI-thread chunked**, which makes atomicity structural but ties
  responsiveness to the modal dialog's event loop. If a single buffer ever becomes slow
  enough to stall visibly, the fix is to move the loop, and decision 4(c) states in advance
  what a worker must and must not touch.
- **Peak transient memory is real**: up to twice the document's resident bytes during a
  run, since every source is retained for undo while every result is accumulated. 5.08 GiB
  for the worst worked case.

**What this enables.** A scaled or rotated multi-layer document can be reopened at all, and
a rotated non-square one no longer loads with scrambled art. The `&Image` menu becomes
predictable: every item in it means the same thing by scope, so a user never has to know
which operations predate the layer tree. The enumeration, the cost estimate and the
stepwise resample are available Qt-free to the four existing batch panels without the
modal dialog.

**What this constrains.** No future code path may derive `Document.width`/`height` from a
single layer's buffer — that is the write this record removes, and reintroducing it
anywhere reintroduces both corruptions at once. Any new `&Image` geometry operation joins
the family by default; adding an active-layer-scoped one requires amending this record,
because the menu's scope consistency is now a user-visible guarantee (ruling Q-4) rather
than an accident. `.pxproj` must continue to carry exactly one geometry, at the canvas
header — decision 7 is what keeps the corrupt state unrepresentable, and per-layer
geometry would give it back.

## What has no detector, stated rather than implied

**Nothing greps for the reintroduction of the seam.** No script proves that a future write
path derives document geometry from a layer buffer; the constraint above is a review
invariant against this decision's mechanism, not a gate that runs.

**Nothing enforces the classification.** No test can tell a DEFECT row from a CHANGE row —
that distinction lives in this record, in the requirement text and in the changelog's
Added/Changed/Fixed grouping, and it is preserved only by people reading them. The most
likely place for it to be corrupted is a changelog entry, because "Fixed" is where geometry
changes usually land. **If a later document lists `Flip H`/`Flip V` or square `Rotate 90`
under "Fixed", that document is wrong and this section is the reason.**

**The silent-corruption class has no automated tripwire beyond the specific tests written
for it.** The mechanism that hid it — a byte-count coincidence letting a length check pass
— is a property of the format, not of the code that was wrong, so an analogous future
desync on a different axis would be equally silent. The persistence tests assert pixel
identity rather than a successful round-trip precisely because a successful round-trip is
what the defect produced.
