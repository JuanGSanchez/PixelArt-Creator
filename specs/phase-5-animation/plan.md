# Plan — Phase 5: Animation System

| Field | Value |
| --- | --- |
| Feature | `phase-5-animation` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-03 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 5 before any `logic/animation.py`, timeline UI, or `.pixproj` tag persistence exists. The `Frame` tree, `Frame.duration_ms`, `DEFAULT_FRAME_DURATION_MS`, `blend.composite_stack`, `history` command pattern, and v2 `.pixproj` frame/layer/`duration_ms` serialisation are **shipped** and reused, not re-authored. |
| Over spec | `specs/phase-5-animation/spec.md` (REQ-P5-LOGIC-001..014, REQ-P5-UI-001..019, REQ-P5-DATA-001..003) + `traceability.md` |
| Stack source | S8 (fixed) — no new technology. Domain internals (onion tint/falloff, playback semantics, frame-tag schema, timeline model, stable `layer_id`) are **grounded** by The Researcher (`docs/research-phase5-animation.md`, **landed**) → PL5-D1 Branch B (no RESEARCH REQUEST). |
| ADRs filed | **ADR-0011** (animation model: `logic/animation.py` Qt-free; `document → animation` one-way edge; per-frame cached composite for playback routed to AGT-10); **ADR-0012** (`.pixproj` schema **v3**: `frame_tags` + `layer_id`; v1/v2/v3 load; back-compat empty tags) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-5 spec — the
**production-animation** milestone that turns the shipped `Document → frames → layers → PixelBuffer`
tree into a **timeline**: a `PlaybackMode` vocabulary + pure frame-sequencing engine, reversible
frame management (add / remove / reorder / duplicate) and per-frame duration editing, onion
skinning, frame **tags** that define independent named animations, a timeline UI, and `.pixproj`
tag persistence. It maps every REQ to its S11 layer, **freezes the public interface of the new
`logic/animation.py` and the `document.py` frame/tag extensions before implementation** so the
DATA and UI slices bind to a stable contract, rules the `.pixproj` **DEP-2** schema decision,
routes the **DEP-3** 8K scrub/playback perf strategy (incl. **FU-19**) to AGT-10, places all new
numerics in `logic/constants.py` (Article II), and commits the layering so
`check_layering`/`check_cycles` stay green. It is decomposed into dependency-ordered work items in
`tasks.md`.

No new stack/library/API is introduced (**PL5-D1 → Branch B**: the stack is fixed by S8; the onion
blend, playback semantics, ping-pong endpoint rule, frame-tag schema, timeline model and the stable
`layer_id` mitigation are **grounded, not invented** — `docs/research-phase5-animation.md` has
landed). The `sdd-analyze` C1 gate is run over constitution/spec/plan/tasks as the pre-implement
gate (Article VIII; see `analyze-report.md`).

## 2. Stack decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language | Python 3.12+ | S8 |
| Playback vocabulary | `PlaybackMode` enum — exactly `LOOP` / `ONCE` / `PING_PONG` / `REVERSE`, default `LOOP` — in `logic/animation.py` (enumerated vocabulary, not a numeric tuning value) | REQ-P5-LOGIC-001; research Q2; CL-1/CL-3 |
| Frame sequencing | Pure, deterministic functions (no clock, no Qt) that map (range, current, direction, mode) → next index or a `PLAYBACK_STOP` sentinel; ping-pong **does not double endpoints** | REQ-P5-LOGIC-002; research Q2; CL-5 |
| Timing source | **Per-frame `duration_ms` is authoritative** (reused, FR-2); sequencing pairs each index with `durations[index]`; FPS is a UI convenience that bulk-sets durations | REQ-P5-LOGIC-003; research Q2; CL-6 |
| Onion overlay | Pure Qt-free computation: composite each prev/next frame stack via `blend.composite_stack` (CO-4), tint toward `ONION_TINT_PREV/NEXT`, fade by `ONION_SKIN_OPACITY` with linear distance falloff to `ONION_SKIN_OPACITY_MIN`; current frame excluded; honours hidden layers | REQ-P5-LOGIC-012; research Q1; CL-4/CL-11/CL-12 |
| Per-frame render | Delegates to shipped `blend.composite_stack` (CO-4) — compositing math **never** re-implemented | REQ-P5-LOGIC-013; CL-10 |
| Frame-tag model | `FrameTag(name, from_frame, to_frame, mode: PlaybackMode, repeat: int, color: str)` in `logic/animation.py`; ordered collection on `Document`; ranges may overlap; names need not be unique | REQ-P5-LOGIC-009; research Q3; CL-8 |
| Reversible frame/tag ops | Reuse `history.Command`/`FunctionCommand`; the `make_*_command` builders live in `document.py` (existing pattern); `ui/commands.py` wraps each as **one** `QUndoCommand` | REQ-P5-LOGIC-004..010, UI-015; S7, C1, F1 |
| Cross-frame layer identity | Additive stable `layer_id` on each node (timeline/onion/tags address layer *tracks*); **cel-level layer×frame linking DEFERRED** | research Q4 caveat; CL-7/CL-9; §6 non-goal |
| Persistence | Extend `data/project_io.py`; **bump `FORMAT_VERSION` to 3**; store `frame_tags` + `layer_id`; defensive validated load; **read v1/v2 back-compat** (empty tags) | ADR-0012; DEP-2/CL-15; Article VII |
| Playback clock | The `QTimer` lives in `ui/` only; the next-frame decision is pure `logic/animation` | REQ-P5-UI-008; CL-14; Article I |
| Scrub/playback perf | Reuse ADR-0007 region/dirty-rect for edits **+** cache each frame's flattened composite for scrub/playback (no per-tick re-flatten); **FU-19** (defer eager frame-switch rebuild) folded into the UI plan; AGT-10 profiles + tunes | ADR-0011; DEP-3; Article VI |
| Testing | pytest + Hypothesis (logic/data), pytest-qt both themes (UI), headless | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-5 logic/data decision places Qt in `logic/` or `data/` (**PL5-D2 → Branch B held**). The
`QTimer` and all timeline/onion/tag widgets live only in `ui/`; the sole Qt file outside `ui/`
remains `ui/commands.py`.

## 3. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`) and acyclic (verified §11). The new
Qt-free logic edge is **`document → animation → blend`** (never the reverse — §3.4).

### 3.1 New / extended `logic/` modules (Slice 5A — pure, zero Qt)

| Module | Change | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- | --- |
| `logic/constants.py` | extend | Add `MAX_FRAMES`, `MAX_ONION_SKIN_FRAMES`, `DEFAULT_ONION_PREV`, `DEFAULT_ONION_NEXT`, `ONION_TINT_PREV`, `ONION_TINT_NEXT`, `ONION_SKIN_OPACITY`, `ONION_SKIN_OPACITY_MIN` (leaf; no imports). `DEFAULT_FRAME_DURATION_MS` **reused**. | — | LOGIC-014 |
| `logic/animation.py` | **new** | `PlaybackMode` enum; `PLAYBACK_STOP` sentinel; pure sequencing (`next_frame`, `playback_steps`, `tag_playback_steps`); onion overlay computation (`onion_overlay`) over `CompositeNode` stacks via `blend.composite_stack`; `FrameTag` model + range validation/clamping helpers; named-animation range resolution. **Never imports `document`** (PL5-D3). | `blend` (`composite_stack`, `CompositeNode`), `color`, `constants`, `numpy` | LOGIC-001, 002, 003, 009, 011, 012, 013, 014 |
| `logic/document.py` | extend | Reversible frame commands (`make_add_frame_command`/`make_remove_frame_command`/`make_move_frame_command`/`make_duplicate_frame_command`/`make_set_frame_duration_command`); document-level `frame_tags: List[FrameTag]` storage + reversible tag ops (`make_add_tag_command`/`make_edit_tag_command`/`make_remove_tag_command`); tag-range clamp folded into add/remove-frame do/undo; additive stable `layer_id` on `Layer`/`LayerGroup` (`_copy_node(new_ids=…)`); `MAX_FRAMES` bound. | `animation` (`FrameTag`, `PlaybackMode`), `history`, `blend`, `pixel_buffer`, `constants` | LOGIC-004..010, 014 |

`constants.py` stays a leaf. The `PlaybackMode` enum is an enumerated **vocabulary** (like
`BlendMode`) and lives in `animation.py`, not `constants.py` (BF-2). Onion tint colours are named
RGBA constants (content-overlay colours, not theme roles — REQ-P5-UI-018).

### 3.2 Extended `data/` module (Slice 5B — Qt-free I/O; DEP-2)

| Module | Change | Responsibility | Depends on | REQ |
| --- | --- | --- | --- | --- |
| `data/project_io.py` | extend | Serialise document `frame_tags` (native `PlaybackMode` value strings) + per-node `layer_id`; **`FORMAT_VERSION = 3`**, `_SUPPORTED_VERSIONS = (1, 2, 3)`; defensive validated tag load; **v1/v2 back-compat read** → empty tag collection + minted `layer_id`s. Frames + `duration_ms` **reused** (v2 path unchanged). | `logic/animation` (`FrameTag`, `PlaybackMode`), `logic/document`, `logic/color`, `constants` | DATA-001, 002, 003 |

### 3.3 New / extended `ui/` modules (Slice 5C — Qt only)

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `ui/timeline_panel.py` | **new** | `Timeline_Panel(QWidget)`: frames (columns) × layer-track (rows) grid with per-frame thumbnails; frame selection + drag-scrub (no undo); per-frame **duration** editor; add / remove / reorder(drag) / duplicate actions → one `QUndoCommand` each; tag spans drawn over the strip; `changeEvent` retranslate. **FU-19**: consumes a per-frame composite cache so frame-switch does not re-flatten. | `document` frame ops, `animation`, `ui/commands`, per-frame composite cache | UI-001..007, 013, 015, 017..019 |
| `ui/playback_controls.py` | **new** | `Playback_Controls(QWidget)`: play / pause / stop transport + mode selector (four `tr()` labels, default LOOP); owns the `QTimer` (only new Qt timing surface); advances the displayed frame via `animation.playback_steps` honouring `duration_ms`; space = play/pause; named-animation "play tag". | `animation.PlaybackMode`/`playback_steps`/`tag_playback_steps`, active document | UI-008, 009, 010, 014, 017..019 |
| `ui/onion_skin_controls.py` | **new** | `Onion_Skin_Controls(QWidget)`: onion toggle + prev/next count + tint controls (**view settings, no undo**); requests `animation.onion_overlay` contributions; suppressed during playback. | `animation.onion_overlay`, `constants` | UI-011, 012, 017..019 |
| `ui/frame_tags_panel.py` | **new** | `Frame_Tags_Panel(QWidget)`/dialog: create / edit / delete a named tag over a range + per-tag mode/repeat/colour → one `QUndoCommand` each; select-and-play. | `document` tag ops, `animation.FrameTag`/`PlaybackMode`, `ui/commands` | UI-013, 014, 015, 017..019 |
| `ui/canvas_scene.py` | extend | Render the active / scrubbed / playing frame's composite; draw the onion overlay behind the active frame when toggled (BF-1: separate tinted pixmap items vs pre-blend is an AGT-05 HOW). | `blend.composite_stack`, `animation.onion_overlay` | UI-002, 011 |
| `ui/main_window.py` | extend | Hold active frame index; dock the timeline / playback / onion / tag UI; own the per-frame composite cache + its invalidation on edit (FU-19, AGT-10 directive); wire scrub/playback to the canvas. | `document`, tabs, the new panels | UI-001, 002, 008 |
| `ui/commands.py` | extend | One `QUndoCommand` per frame/tag op, delegating to the returned `history.Command`; no domain math. | `history` + all 5A frame/tag ops | UI-015 |

### 3.4 Layering proof (PL5-D3 — cycle-free by construction)

The **only** new intra-`logic/` edge is `document → animation` (document holds `List[FrameTag]`
and constructs `FrameTag`/`PlaybackMode` in its tag/frame command builders). `animation.py`
**never imports `document`** — it consumes layer stacks structurally through the existing
`blend.CompositeNode` Protocol and plain `Sequence[int]` durations, exactly as `blend.py` avoids a
`document` import (PL-D2 precedent). Resulting one-way chain:

```
ui/  →  data/project_io  →  logic/document  →  logic/animation  →  logic/blend  →  logic/color, logic/constants
                                    └──────────────────────────→  logic/blend (existing document→blend edge)
```

No back-edge (`animation → document`, `blend → animation`, or any `logic/`/`data/` → `ui/`) exists.
`check_layering` + `check_cycles` therefore stay `0` (verified §11 on the shipped tree; the planned
edges are acyclic by design and re-verified when 5A lands).

## 4. `logic/animation.py` — frozen interface contract (Slice 5A)

Frozen **before** implementation so 5B/5C bind to a stable surface. Qt-free. Exceptions subclass
`ValueError` (Phase-1 convention); range/validation errors on the `Document` side raise the
existing `DocumentError`.

```python
class PlaybackMode(enum.Enum):
    LOOP = "loop"          # start→end, wrap to start (default)
    ONCE = "once"          # start→end, stop on last
    PING_PONG = "ping_pong"# start→end→start, endpoints NOT doubled (CL-5)
    REVERSE = "reverse"    # end→start, wrap to end when looping

DEFAULT_PLAYBACK_MODE: PlaybackMode = PlaybackMode.LOOP   # CL-3
PLAYBACK_STOP: object  # module sentinel yielded when a non-looping run completes

# Pure, deterministic sequencing (no clock, no Qt) — REQ-P5-LOGIC-002/003
def next_frame(current: int, direction: int, start: int, end: int,
               mode: PlaybackMode) -> Tuple[Union[int, object], int]:
    """(next_index_or_PLAYBACK_STOP, new_direction); single-frame range → that frame."""

def playback_steps(durations: Sequence[int], mode: PlaybackMode, *,
                   start: int = 0, end: Optional[int] = None,
                   repeat: int = 0) -> Iterator[Tuple[int, int]]:
    """Yield (frame_index, duration_ms) pairs; repeat=0 → infinite for looping modes."""

def tag_playback_steps(tag: "FrameTag",
                       durations: Sequence[int]) -> Iterator[Tuple[int, int]]:
    """playback_steps over tag.[from_frame, to_frame] under tag.mode/tag.repeat (REQ-P5-LOGIC-011)."""

# Onion overlay — REQ-P5-LOGIC-012 (pure, Qt-free; NOT called during playback)
@dataclass(frozen=True)
class OnionContribution:
    buffer: PixelBuffer   # composited + tinted + faded RGBA (draw behind active frame)
    z_order: int          # farther frames behind nearer ones; negative = below active

def onion_overlay(prev_stacks: Sequence[Sequence["CompositeNode"]],
                  next_stacks: Sequence[Sequence["CompositeNode"]],
                  width: int, height: int, *,
                  region: Optional[Tuple[int, int, int, int]] = None
                  ) -> List[OnionContribution]:
    """prev_stacks[0]/next_stacks[0] = nearest neighbour. Composites each via
    blend.composite_stack, tints toward ONION_TINT_PREV/NEXT, fades linearly from
    ONION_SKIN_OPACITY (nearest) to ONION_SKIN_OPACITY_MIN (farthest). Counts bounded
    by MAX_ONION_SKIN_FRAMES (AnimationError past it). Hidden layers honoured (they are
    already absent from the composite). The active frame is not part of the set."""

# Frame-tag model — REQ-P5-LOGIC-009
@dataclass
class FrameTag:
    name: str
    from_frame: int          # inclusive, ≤ to_frame, both within frame count
    to_frame: int            # inclusive
    mode: PlaybackMode = PlaybackMode.LOOP
    repeat: int = 0          # 0 = infinite for looping modes
    color: str = "#ff0000ff" # #rrggbbaa UI marker (research Q3)
    # Construction with inverted/out-of-range range → DocumentError (raised by the
    # Document builder that owns frame-count context); free-standing validation helper:

def validate_tag_range(from_frame: int, to_frame: int, frame_count: int) -> None: ...
def clamp_tag_range(tag: FrameTag, frame_count: int) -> FrameTag: ...  # REQ-P5-LOGIC-010

class AnimationError(ValueError): ...
```

**Notes.** `next_frame`/`playback_steps` are duration-agnostic on the sequencing axis (they take a
plain `Sequence[int]`), so `animation.py` needs no `Frame`/`Document` import (PL5-D3). Determinism
(P2, SC-L002-2) is intrinsic: no RNG, no time. Ping-pong direction is carried explicitly in
`next_frame`'s `direction` return so the function stays pure.

## 5. `logic/document.py` — frozen frame/tag extension contract (Slice 5A)

Additive to the shipped `Document`; the `make_*_command` pattern and `history.Command` return type
match the Phase-4 layer ops exactly (so `ui/commands.py` stays a thin wrapper).

```python
# Reversible frame commands (return an UNAPPLIED history.Command) — REQ-P5-LOGIC-004..008
def make_add_frame_command(self, *, after_index: int,
                           duration_ms: int = DEFAULT_FRAME_DURATION_MS) -> Command: ...
    # new frame, one empty layer, inserted after after_index; bounded by MAX_FRAMES; undo removes it.
def make_remove_frame_command(self, frame_index: int) -> Command: ...
    # refuses the last frame (DocumentError at build); undo restores frame at its index with
    # exact layers + duration; affected tag ranges clamped on do / restored on undo (REQ-P5-LOGIC-010).
def make_move_frame_command(self, from_index: int, to_index: int) -> Command: ...   # NEW op
def make_duplicate_frame_command(self, frame_index: int) -> Command: ...            # NEW op
    # deep, independent copy (_copy_node(new_ids=False) — track ids preserved) + duration; after source; bounded.
def make_set_frame_duration_command(self, frame_index: int, duration_ms: int) -> Command: ...
    # positive-int guard (DocumentError on ≤0); captures prior; undo restores.

# Document-level frame tags + reversible ops — REQ-P5-LOGIC-009/010
frame_tags: List["FrameTag"]   # added to __slots__; ordered; created empty
def make_add_tag_command(self, name: str, from_frame: int, to_frame: int, *,
                         mode: PlaybackMode = PlaybackMode.LOOP, repeat: int = 0,
                         color: str = "#ff0000ff") -> Command: ...  # range-validated → DocumentError
def make_edit_tag_command(self, tag_index: int, *, name=None, from_frame=None,
                          to_frame=None, mode=None, repeat=None, color=None) -> Command: ...
def make_remove_tag_command(self, tag_index: int) -> Command: ...

# Additive stable cross-frame layer identity (research Q4 caveat) — enabler for the timeline
# Layer/LayerGroup gain `layer_id: int`; Document mints via a private monotonic counter (deterministic, P2).
# _copy_node(node, *, new_ids: bool = True): layer-duplicate mints a fresh id; frame-duplicate
# preserves ids so a duplicated frame shares its predecessor's layer tracks. Full track UNIFICATION
# across independently-authored frames is DEFERRED with cel linking (§6 non-goal).
```

## 6. `.pixproj` schema — DEP-2 ruling (ADR-0012)

**Decision: bump `FORMAT_VERSION` to `3`; serialise `frame_tags` + per-node `layer_id`; load v1/v2/v3;
v1/v2 (tagless) load with an empty tag collection + minted `layer_id`s.** Saving always writes v3.

- **Serialise (v3):** a document-level `"frame_tags"` array of
  `{name, from, to, mode, repeat, color}` where `mode` is the **native `PlaybackMode` value string**
  (`"loop"`/`"once"`/`"ping_pong"`/`"reverse"`); each layer/group node gains `"layer_id"` (int).
  Per-frame `"duration_ms"` and the v2 layer model are **unchanged** (reused).
- **Native mode, not Aseprite `direction` (decisive for lossless round-trip).** The research (Q3)
  target `direction ∈ {forward,reverse,pingpong,pingpong_reverse}` is the **Phase-7 export** shape,
  not the `.pixproj` internal representation. Aseprite's `direction` cannot express our
  `LOOP`-vs-`ONCE` distinction (that is a repeat concern in Aseprite), so storing `direction` would
  **lose** state and break REQ-P5-DATA-001 ("modes restored identically"). `.pixproj` therefore
  stores the native `PlaybackMode`; Phase-7 export maps `mode`→`direction`+`repeat`.
- **Deserialise (defensive, Article VII / REQ-P5-DATA-003):** reject an inverted/out-of-range tag
  range, an unknown `mode` string, a non-int/negative `repeat`, a malformed tag object, or a
  `frame_tags` that is not a list — each with `ProjectIOError`. No `eval`/`exec`; paths via
  `pathlib`. A payload **without** `frame_tags` loads with an empty collection (back-compat).
- **Why bump, not additive-on-v2 (alternative considered).** Additive-within-v2 would technically
  keep back-compat (the shipped v2 loader ignores unknown top-level keys). It was **rejected** for
  the same reason ADR-0006 rejected "keep the version, add fields": `frame_tags` is **new
  document-level semantics** (named animations) and `layer_id` is new node identity — the version
  field is the honest, self-describing signal (ADR-0006 explicitly anticipated the *animation
  timeline* as a future version). A v3 stamp makes a Phase-4 v2 reader **fail-closed** on a
  tag-bearing file rather than silently dropping the animations (Article VII posture), and costs
  nothing: v1 (flat) and v2 (rich layers) still load with empty tags. Forward-incompat (an old
  reader cannot open v3) is acceptable exactly as ADR-0006 ruled for v1→v2. `FORMAT_VERSION` stays
  format-intrinsic local to `project_io.py` (ADR-0001 precedent).

## 7. Performance — DEP-3 routing to AGT-10 (ADR-0011 §Perf) + FU-19

REQ-P5-UI-016 binds scrub/playback of an 8K multi-layer frame to `FRAME_BUDGET_MS = 16`. Re-flattening
every layer over the whole canvas on **every** scrub/playback tick blows the budget. Architecture
commitment (AGT-10 profiles + tunes; AGT-05 implements; **budget never relaxed**, Article VI §2):

1. **Cached per-frame flattened composite.** Each frame's flattened RGBA composite is cached; scrub
   and playback **switch between pre-flattened frame buffers** (a cheap blit) instead of
   re-flattening. The cache for frame *f* is invalidated only when *f*'s own layer tree changes.
2. **FU-19 folded in.** The eager `_rebuild_composite`-on-frame-switch path must be **deferred**:
   the timeline switches frames heavily during scrub/playback, so a switch consults the per-frame
   cache and rebuilds lazily/only-on-miss, never eagerly per switch. Recorded here as a UI directive
   (AGT-05) grounded by the AGT-10 profile.
3. **Edit path reuses ADR-0007.** Painting inside a frame recomposites only the dirty region
   (`composite_stack(region=…)`, region-sized buffer, no full-canvas alloc — ADR-0007 amended) and
   invalidates that frame's cache entry.
4. **Onion cost off the playback budget.** Onion is **suppressed during playback** (CL-11), so its
   multi-frame composite never competes with the 16 ms playback tick.
5. **Resident buffers never culled** (Article VI §3, F7) — only Qt rendering is region-scoped.

**Ownership.** AGT-10 owns the measurement (`perf_profile`/`frame-profile`, e.g. a
`--animation` scenario) + any viewport directive; AGT-05 implements the per-frame cache +
FU-19-deferred switch; AGT-01 fixes the cached-composite + region API commitment (ADR-0011). An
over-budget profile yields an AGT-10 optimisation directive, not a budget change.

## 8. Constant placement (Article II / BF-2)

All in `logic/constants.py` (leaf); `DEFAULT_FRAME_DURATION_MS` reused. Spec-fixed values from
CL-4; onion opacity/falloff are research **medium-reliability** defaults (flagged, confirm at impl):

| Constant | Value | Source |
| --- | --- | --- |
| `MAX_FRAMES` | `4096` | defensive bound (Article VII), generous for hand-drawn animation; parallels `MAX_LAYERS_PER_FRAME` |
| `MAX_ONION_SKIN_FRAMES` | `8` | research Q1 (0..8 per side) — **medium reliability** |
| `DEFAULT_ONION_PREV` | `1` | CL-4 (Aseprite default 1/1) |
| `DEFAULT_ONION_NEXT` | `1` | CL-4 |
| `ONION_TINT_PREV` | `(255, 0, 0, 255)` | CL-4 red = previous (Aseprite mapping) |
| `ONION_TINT_NEXT` | `(0, 0, 255, 255)` | CL-4 blue = next (Aseprite mapping) |
| `ONION_SKIN_OPACITY` | `0.5` | research Q1 nearest-ghost max — **medium reliability** |
| `ONION_SKIN_OPACITY_MIN` | `0.15` | research Q1 farthest-ghost min (linear falloff) — **medium reliability** |

`PlaybackMode` (vocabulary) → `animation.py`, not `constants.py`. Onion tint colours are
content-overlay constants, not theme roles (REQ-P5-UI-018).

## 9. Implementation strategy — dependency-ordered slices

Logic-first vertical slices (detailed work items in `tasks.md`):

- **5A — logic** (`constants.py`, `animation.py`, `document.py` extensions). AGT-03 + AGT-04.
  Order: constants → `animation.py` (PlaybackMode + sequencing + FrameTag + onion) → `document.py`
  (frame commands + tag ops + `layer_id`). Freezes the contract 5B/5C bind to.
- **5B — data** (`project_io.py` v3: tags + `layer_id`; defensive + v1/v2 back-compat). AGT-03 + AGT-04.
- **5C — UI** (timeline → playback → onion → tags; canvas/main-window wiring; `commands.py`), with
  the AGT-10 perf profile (DEP-3/FU-19) coordinated in the playback/canvas step. AGT-05 + AGT-06 + AGT-10.

Reversible-op boundary: every mutating frame/tag op is a `history.Command` from `document.py`,
wrapped as exactly one `QUndoCommand` in `ui/commands.py` (Article I §2). Selection / scrub /
playback / onion view-settings mutate no document state → no command (CL-13).

## 10. Constitution compliance (self-check)

- **I:** `animation.py` + `document.py`/`constants.py` extensions are pure (zero Qt); `QTimer` +
  all panels in `ui/`; sole outside-`ui/` Qt file stays `ui/commands.py`. `document → animation`
  one-way (§3.4).
- **II:** eight new numerics in `constants.py`; `DEFAULT_FRAME_DURATION_MS` reused; `PlaybackMode`
  is vocabulary in `animation.py`.
- **IV:** each playback mode, sequencing determinism, onion overlay, frame/tag reversibility,
  per-frame render reuse, and `.pixproj` tag round-trip + defensive load map to a scenario → test
  (`tasks.md`); both themes for UI.
- **V:** REQ-P5-UI-017/018/019 are blocking gates on the timeline/playback UI.
- **VI:** REQ-P5-UI-016 16 ms budget for 8K scrub/playback; cached-composite + region strategy;
  buffers never culled; budget never relaxed.
- **VII:** frame/onion/tag bounds, positive-duration guard, defensive validated v3 tag load; no
  `eval`/`exec`.
- **X:** every REQ traces to an S-id / F-finding / forward-inherited primitive (`traceability.md`).
- **XI:** deferring cel linking + the Phase-9 preview window adds capability later without
  weakening any article.

## 11. Layering / cycle verification

`python scripts/check_layering.py` and `python scripts/check_cycles.py` run **clean (exit 0)** on
the shipped tree at plan time (baseline). The planned edges (`document → animation → blend`,
`data/project_io → animation`) are acyclic by construction (§3.4); both scripts are re-run by AGT-03
when 5A/5B land and gate the C1 analyze (Article I §4, VIII). See `analyze-report.md` for the C1
verdict.

## 12. Decisions log

| # | Decision | Branch | Rationale |
| --- | --- | --- | --- |
| PL5-D1 | Ungrounded stack/API choice? | **B (no)** | Stack fixed (S8); domain grounded by landed `docs/research-phase5-animation.md`. No RESEARCH REQUEST. |
| PL5-D2 | Qt in `logic/`/`data/` or magic number outside `constants.py`? | **B (no)** | `QTimer`/widgets in `ui/`; eight numerics → `constants.py`; `PlaybackMode` is vocabulary in `animation.py`. |
| PL5-D3 | `animation` model layering | — | `document → animation`; `animation` imports `blend` structurally (`CompositeNode`), **never `document`** → acyclic. |
| PL5-D4 | `.pixproj` tag schema (DEP-2) | v3 bump | New document-level semantics + node identity; honest/self-describing + fail-closed (ADR-0012); v1/v2 still load. |
| PL5-D5 | Perf (DEP-3/FU-19) | route to AGT-10 | Cached per-frame composite + deferred frame-switch rebuild + ADR-0007 region edits; AGT-10 profiles, AGT-05 implements. |
