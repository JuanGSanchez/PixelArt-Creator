# ADR-0008 — `Document.mode` is the single colour-mode authority; conversion is a Document-level reversible op

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-02 |
| Author | Architecture |
| Feature | `phase-4-layer-canvas` (defect surfaced in QA review; root fix spans Phase-3↔Phase-4) |
| Supersedes | — |
| Superseded by | — |
| Defect driver | QA's report (an internal design record, outside this repository) §3 — `BlendError: composite_stack requires RGBA layer buffers` crashing 10 tests / 24 cases on every indexed-mode workflow. |

## Context

A Phase-4 compositing regression made every Phase-3 indexed-mode workflow crash, and a
**latent persistence-corruption bug** rides on the same root cause.

**Verified root cause (re-checked against source, not re-derived).**

1. `ui/canvas_scene.py` derives its compositing switch from the document mode:
   `self._compositing = self._document.mode is ColorMode.RGBA`
   (`__init__` line 423, `_rebuild_composite` line 544). While `_compositing` is `True`,
   `_recomposite_all` / `_rebuild_composite` call `blend.composite_stack`, which is
   **RGBA-only by design** (ADR-0005) and raises `BlendError` on an indexed buffer.
2. Phase-3 conversion (`logic/palette_ops.make_to_indexed_command` /
   `make_to_rgba_command`, invoked by `ui/main_window._on_convert_to_indexed` /
   `_on_convert_to_rgba` at lines 917/937) swaps the **active `Layer.buffer`** to the
   other mode but **never updates `Document.mode`** — it stays `RGBA`. The builders take a
   `SupportsBuffer` holder (a bare `Layer`) precisely to stay decoupled from `Document`, so
   structurally they *cannot* touch document-level mode.
3. Therefore, after convert-to-indexed, `Document.mode` is still `RGBA`, `_compositing`
   stays `True`, and the next `rebind_active()` → `_rebuild_composite` → `_recomposite_all`
   → `composite_stack` runs over a now-indexed buffer → **crash**.

**Latent data-corruption bug (larger than the crash, same root cause).**
`data/project_io.py` serialises `document.mode` (line 125) and **decodes every layer buffer
with that single document mode** (`_parse_node_v2` line 290; masks likewise). `Document`
also allocates every new-layer buffer at `self.mode` (`add_layer`/`add_frame`/`__init__`).
So a stale `Document.mode = RGBA` over an indexed layer means a converted-to-indexed
document **saves with `canvas.mode = "rgba"` above indexed bytes** → on reload the indexed
bytes are mis-decoded as RGBA → silent corruption or `ProjectIOError`. A UI-only
`_compositing` patch (e.g. reading `active_buffer().mode`) would stop the crash but leave
this corruption uncorrected — so the fix must live at the model layer, not the view.

`Document.mode`, `PixelBuffer.mode`, `project_io` mode, the RGBA-only compositor, and the UI
mode indicator were four/five readers of "the mode" with no single owner. This ADR fixes the
ownership.

## Decision

### D1 — `Document.mode` is the SINGLE source of truth for colour mode. No mixed-mode documents.

Every consumer (compositor gate, persistence, new-buffer allocation, UI mode indicator, the
convert-action enablement) reads mode from **`Document.mode`** and from nowhere else.
`PixelBuffer.mode` remains a storage detail of an individual buffer, but it is a
**derived/consistency property**, never an independent authority — the model guarantees it
agrees with `Document.mode` (see the invariant).

### D2 — Colour-mode invariant (stated explicitly, enforced by the model)

For any `Document`:

- **RGBA document** (`mode is ColorMode.RGBA`): every frame holds **one or more** layers,
  and **every** `Layer.buffer` (and mask) in every frame is `ColorMode.RGBA`. This is exactly
  what `blend.composite_stack` requires (all-RGBA), so the multi-layer compositor is valid.
- **INDEXED document** (`mode is ColorMode.INDEXED`): every frame holds **exactly one**
  layer, whose buffer is `ColorMode.INDEXED`. Indexed documents keep the Phase-1
  single-active-layer display path (the RGBA-only compositor never runs on them). This is
  consistent with QA's ruling (§2: no Phase-4 scenario requires indexed multi-layer
  compositing) and with the ADR-0007 compositor contract.

There is no state in which one document mixes RGBA and indexed layers, and no state in which
`Document.mode` disagrees with any of its layer buffers.

### D3 — Conversion is a Document-level, atomic, reversible operation

Colour-mode conversion moves from `logic/palette_ops` (buffer-level) up to
`logic/document.py` (which owns `Document.mode`). Add two reversible command builders on
`Document`:

```
Document.make_convert_to_indexed_command(palette, *, metric="distance_sq") -> history.Command
Document.make_convert_to_rgba_command(palette)                              -> history.Command
```

- They flip the **layer buffer(s) AND `Document.mode` in one `history.FunctionCommand`** —
  the two never move independently, so persistence / compositor / UI can never observe an
  inconsistent intermediate.
- Pixel conversion is **delegated** to the existing pure functions
  `palette_ops.to_indexed(buffer, palette, metric=...)` / `palette_ops.to_rgba(buffer, palette)`
  (unchanged). `document.py` gains a one-way import of `palette_ops`; `palette_ops` does not
  import `document` (it never has — it uses the `SupportsBuffer` protocol), so the layering
  stays acyclic (see §Grounding — scripts re-run clean).
- Because `Document.mode` is document-wide, the command operates over **all frames** so the
  invariant holds document-wide (not just the active frame).
- The command is returned **unapplied**; `ui/commands.py` wraps it as one `QUndoCommand`
  (REQ-P3-LOGIC-017; `apply ∘ undo = identity`).

### D4 — Multi-layer convert-to-indexed: flatten-then-index (the new Phase-3↔4 design point)

Convert-to-indexed on a **multi-layer RGBA** document (newly possible in Phase 4) resolves by
**flattening the composite, then indexing the single result**:

For each frame: `flat = blend.composite_stack(frame.layers, width, height)` (full-canvas RGBA
flatten) → `indexed = palette_ops.to_indexed(flat, palette, metric=...)` → replace the frame's
entire node list with a **single** `Layer(indexed, "<name>")`. Then set `Document.mode =
INDEXED`. The invariant (exactly one indexed layer per frame) then holds by construction.

- **Reversible-command semantics.** On `execute`: snapshot each frame's current
  `frame.layers` list reference and the prior `Document.mode`, then replace each list with a
  new single-indexed-layer list and set `mode = INDEXED`. On `undo`: reassign the saved
  `frame.layers` lists and restore `mode = RGBA`. Because `execute` **replaces the list
  wholesale and never mutates the original nodes**, restoring the saved list references
  reproduces the full multi-layer RGBA tree **exactly** (byte-for-byte, including groups,
  masks, opacity, blend modes, references, smart links) — no deep copy required, and
  `apply ∘ undo = identity` holds.
- **Rejected alternatives:** (a) *warn-and-refuse unless the user pre-flattens* — rejected as
  worse UX and still needs a flatten op; (b) *index each layer independently and keep the
  multi-layer tree* — rejected: it violates D2, keeps the RGBA-only compositor pointed at
  indexed buffers (the very crash), and has no coherent composite meaning for indexed layers.
  Flatten-then-index is the only option that satisfies D2 and the compositor contract while
  staying fully reversible.
- Convert-to-RGBA is the simple inverse: each frame's single indexed layer becomes one RGBA
  layer via `palette_ops.to_rgba`; `mode = RGBA`. Undo restores the single indexed layer +
  `mode = INDEXED`.

### D5 — `_compositing` reads `Document.mode` (single source) — this is the rule

`ui/canvas_scene.py` **keeps** deriving `_compositing = (self._document.mode is
ColorMode.RGBA)`. With D1–D4, `Document.mode` is now always correct, so this derivation is
correct and needs no change. The rule for all UI mode reads: **read `Document.mode`, never
`active_buffer().mode`.** `main_window._refresh_mode_ui` (currently reads
`record.scene.active_buffer().mode`, line 977) is updated to read `record.document.mode` for
single-source consistency. Deriving from the per-buffer mode is explicitly rejected: it would
paper over the crash while leaving the persistence corruption (D-context bug 2) intact and
would re-introduce two competing authorities.

### D6 — Retire the buffer-level mode-switch builders

`palette_ops.make_to_indexed_command` / `make_to_rgba_command` (and the `SupportsBuffer`
protocol that exists only for them) are **removed**: a buffer-holder-level mode switch
structurally cannot maintain the document invariant (D2) and is the direct source of the
defect. The pure converters `palette_ops.to_indexed` / `to_rgba` **stay** (now called by the
Document command). `make_cycle_command` / `make_swap_command` are unaffected (they are
`PixelEdit`s that never change mode).

## Consequences

**Positive.** One owner for colour mode; the crash and the latent save-corruption bug are
both fixed at the model layer with one change. The compositor's all-RGBA precondition is now
a *guaranteed* invariant, not a hope. Multi-layer→indexed has defined, fully reversible
semantics. The UI derivation simplifies to a single source. Persistence needs **no** schema
change — a correct `Document.mode` makes the existing v2 serialise/deserialise correct.

**Negative / risk.** Convert-to-indexed on a multi-layer doc is **lossy to the layer
structure** (the tree collapses to one indexed layer) — but this is inherent to indexed mode
(one indexed buffer, no RGBA compositing) and is fully undoable, so no data is lost while the
document is open. The conversion command must be wired so its rebind does a **full** document
re-bind + layer-panel repopulate (the tree changed), not the narrow `rebind_active()` used for
same-shape buffer swaps. Converting a document with a large multi-layer 8K stack pays one
full-canvas flatten at convert time (a deliberate, user-initiated, one-off cost — not a
per-frame budget item, so outside SC-UI-015; flag to Rendering & Performance only if profiling shows a UX
concern).

## Grounding

- Defect: QA's report (an internal design record, outside this repository)
  §3 (root cause, 24 crashing cases), §4 (coupled SC-UI-001 test-maintenance).
- Source verified: `ui/canvas_scene.py` L423/L544 (`_compositing` from `Document.mode`);
  `logic/palette_ops.py` L326–L378 (`make_to_indexed_command`/`make_to_rgba_command` swap
  `holder.buffer` only); `logic/document.py` L302/L317/L332/L361 (`mode` slot; new buffers at
  `self.mode`); `data/project_io.py` L125 (serialise mode) / L290 (decode all buffers with the
  one mode); `ui/main_window.py` L917–L953 (conversion handlers), L977 (`_refresh_mode_ui`).
- Compositor contract: ADR-0005 (RGBA float working space, all-RGBA input), ADR-0007
  (region-scoped recomposite; resident buffers).
- QA's indexed-mode ruling (§2): no Phase-4 scenario requires indexed multi-layer
  compositing → single-layer indexed path is intended scope.
- Requirements: REQ-P3-UI-014 (indexed-mode workflow), REQ-P3-LOGIC-017 (reversible,
  `apply ∘ undo = identity`), REQ-P4-LOGIC-004 (flat RGBA composite buffer), DATA-001..005
  (`.pixproj` schema v2 round-trip).
- Layering: `document → palette_ops` and `document → blend` are one-way (neither `palette_ops`
  nor `blend` imports `document`); `check_layering` / `check_cycles` re-run clean this session.
