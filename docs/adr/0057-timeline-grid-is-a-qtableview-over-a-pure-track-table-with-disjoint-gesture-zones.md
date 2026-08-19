# ADR-0057 — The timeline grid is a `QTableView` over a pure track table, with structurally disjoint gesture zones

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-08-17 (`phase-5-timeline-grid` plan §2, §7); **recorded 2026-08-19** |
| Author | AGT-01 (Architecture) |
| Feature | `phase-5-timeline-grid` (D-04) — the optional frames × layer-tracks grid view |
| Grounded by | `REQ-P5-UI-022`..`-025`, `-027`..`-031`; `REQ-P5-LOGIC-015` (the pure track-table derivation); `REQ-P5-UI-032` and audit finding **CF-56 / T-21**; `phase-2-floating-selection` `REQ-P2-UI-032` (the product's fixed drag-to-copy modifier); Article I / S11 (no domain logic in a widget) |
| Owed by | `phase-5-timeline-grid` **T25** (owner AGT-08) — see "Why this record is late" |
| Relates to | ADR-0011 (the animation model this view presents), ADR-0056 (the preference registry the overwrite confirmation consults) |

## Context

The grid presents frames as columns and layer-tracks as rows — an F × L surface where the
shipped timeline strip presented F. Three requirements land on it at once and they pull in
different directions:

- `REQ-P5-UI-030` — off-screen cells must not be composited. The grid multiplies display work
  by the layer count, so a naive view repaints an entire document's worth of thumbnails.
- `REQ-P5-UI-027` — assistive technology must get row/column/count semantics. A canvas of
  drawn rectangles has none.
- `REQ-P5-UI-025` — **three** gestures share one widget: reorder a frame (header), move or copy
  a cel (an occupied cell), scrub (the body away from any cel).

The third is not a hypothetical. Audit finding **CF-56 / T-21** recorded exactly this failure in
the *existing* timeline strip: *"One gesture, two claimants, and no test drives either. Whether
the user-facing left-drag reaches scrub at all is unproven."* Two handlers claimed one left-drag,
the discrimination between them lived in hand-written conditions inside a `mousePressEvent`, and
nothing exercised either path. `REQ-P5-UI-032` orders that defect confirmed, fixed and proven
fixed — so the grid must not reproduce its shape while the strip is being repaired.

The obvious candidate is `QGraphicsView`, which the product already uses for the canvas. It gives
none of the three: no free header zone, no native table semantics for AT, and culling that would
have to be hand-rolled. The other candidate — a custom-painted widget — would hand-roll culling,
headers **and** accessibility: three mechanisms to write, and three chances to reproduce CF-56.

## Decision

**We will implement the timeline grid as a `QTableView` with a `QAbstractTableModel` adapter over
the pure, Qt-free `logic/track_table.py` derivation, and make its three gesture zones disjoint by
construction rather than by a hand-written discrimination.**

Concretely:

1. **`QTableView` + `QAbstractTableModel`, and the choice is load-bearing, not cosmetic.** Qt calls
   `data()` only for indexes in the exposed viewport, which **is** `REQ-P5-UI-030`'s culling — the
   requirement is satisfied by the framework rather than by code this product has to write and
   test. `Timeline_Grid_View(QTableView)` and `_Track_Table_Model(QAbstractTableModel)` live in
   `ui/timeline_grid_view.py`.

2. **The model is an adapter, not a model of the domain.** The frames × tracks derivation is
   `logic/track_table.py` (`REQ-P5-LOGIC-015`) — pure, Qt-free, importing only `typing` and
   `logic/document.py`, exposing `TrackTable` / `TrackRow` / `Cell` / `EMPTY_CELL` /
   `track_table()`. The Qt model adapts that value; it derives nothing itself. No domain logic in
   the widget (Article I / S11).

3. **Native table semantics are taken, not simulated.** `QTableView` announces rows, columns and
   counts to assistive technology by being a table (`REQ-P5-UI-027`); the empty-cell "create a cel
   here" affordance is a **context-menu** action, which `QAbstractItemView` already routes from
   both the mouse and the platform's context-menu key (`Shift+F10` / the `Menu` key) — so it is
   pointer- *and* keyboard-reachable without inventing a second gesture on top of the drag zones.

4. **Zone 1 — the header — is Qt's own reorder, not a discrimination this code performs.**
   `header.setSectionsMovable(True)`; the view translates the resulting `sectionMoved` into one
   `make_move_frame_command` and puts the header back to logical order, because the document — not
   the header's transient visual state — is the single source of truth. **A `QHeaderView` is a
   structurally separate widget whose drag Qt never routes to the body.** That is the direct answer
   to CF-56: the zone boundary is a widget boundary, so no condition can get it wrong.

5. **Zones 2 and 3 are separated by one testable predicate.** A left-press-drag starting on an
   *occupied* cell moves the cel (`Ctrl` copies it); a press anywhere else in the body scrubs. The
   whole discrimination is one `indexAt(pos)` plus an occupancy test against the track table — one
   predicate, assertable in a unit test, instead of three claimants inside one `mousePressEvent`.

6. **`Ctrl` copies, reusing the product's own fixed convention** (`phase-2-floating-selection`
   `REQ-P2-UI-032`, which also states why not `Alt` — interior `Alt`-drag is the shipped selection
   *subtract* gesture). Two copy modifiers in one product is a defect; a Qt-level conflict with
   extended selection is **a finding to report, not licence to pick a different key silently**.

7. **Every mutation is exactly one `FrameCommand`** wrapping a shipped `Document.make_*_command`
   factory — move, copy, create, per-cell visibility. Scrubbing pushes **nothing**; selection
   mutates **nothing**.

8. **An affordance that would refuse is not offered.** The empty-cell context menu is **not built at
   all** when the destination is occupied or the frame is already at `MAX_LAYERS_PER_FRAME` — both
   checked before the menu is shown, never caught after the click.

## Alternatives considered

| Alternative | Why it was not chosen |
| --- | --- |
| **`QGraphicsView` / `QGraphicsScene`** | Supplies none of the three needs: no free header zone, no native table semantics for AT, and culling that would have to be written by hand. The canvas already owns that idiom, and reusing it here would buy the grid nothing it needs. |
| **A custom-painted widget** | Would hand-roll culling, headers *and* accessibility — three mechanisms to write, three to test, and three chances to reproduce CF-56. |
| **`QListView` per track / a stack of strips** | Reproduces the strip's single-axis model F times and gives the cross-axis (a cel's identity as *frame × track*) no representation at all; a cel move between tracks would have no index to name. |
| **Discriminating all three gestures by hand in one `mousePressEvent`** | Three claimants where CF-56 had two, with the same absence of a structural boundary. The finding this design answers is precisely that a condition-based zone split is unresolved until something tests it. |
| **Letting the header's visual order be the truth after a drag** | Two sources of truth for frame order. The document stays authoritative and the header is reset to logical order after each `sectionMoved`. |
| **A different copy modifier than `Ctrl`** | Two drag-to-copy modifiers in one product is a defect (`REQ-P5-UI-031`). |
| **Deriving the frames × tracks table inside the Qt model** | Puts domain logic in a widget (Article I / S11) and makes the derivation untestable without a `QApplication`. |
| **An extra keyboard gesture for "create a cel here"** | `QAbstractItemView` already routes the platform's context-menu key to the current index; inventing a second gesture adds a claimant to a widget whose whole design is about not having spare ones. |

## Consequences

**Accepted costs.** The view is bound to `QTableView`'s idioms: anything the grid wants that a
table does not do naturally — a non-rectangular cel span, a per-cell drag handle, a free-form
timeline ruler — is now a fight with the framework rather than a drawing decision. Delegating the
header's reorder to Qt means the *visual* order and the document order transiently disagree during
a drag, and the code that resets it is load-bearing and easy to remove by accident. And the F × L
surface multiplies composite work relative to the strip's F, so the framework's viewport-scoped
`data()` is not a bonus — it is the only thing making the grid affordable.

**What this enables.** Culling and accessible table semantics arrive with the widget rather than as
code to maintain. The gesture zones are separable *in tests*, which is what CF-56 says was missing:
the header zone can be exercised through `sectionMoved`, the cell zone through `indexAt`, with no
synthesised mouse-path ambiguity between them. `logic/track_table.py` stays testable with no Qt at
all, and any future presenter of the same derivation reuses it.

**What it constrains.**

- `logic/track_table.py` stays Qt-free and derivation-only; the Qt model adapts it and derives
  nothing.
- The header's reorder stays `QHeaderView`'s. Hand-routing a header drag into the body would
  re-create CF-56's shape exactly.
- The cell/body split stays **one** predicate. A second condition in the same handler is the
  regression this ADR exists to prevent.
- Every grid mutation goes through a shipped `Document.make_*_command` factory wrapped in one
  `FrameCommand`; the view pushes no bespoke `QUndoCommand`.
- `Ctrl` remains the product's single drag-to-copy modifier.

## Compliance

The layering half has detectors, and they were **run** — not read — in the `fix-adr-citations`
worktree at `267d64a`:

```
$ python scripts/check_layering.py --json
{ ..., "scanned": 207, "unregistered": [], "violations": [] }
exit 0
$ python scripts/check_cycles.py --json
{ "cycles": [], "edges": 761, "modules": 209 }
exit 0
```

Zero violations means no Qt symbol has reached `logic/track_table.py` and no `logic -> ui` edge
exists; `logic/track_table.py`'s import block (`typing`, `logic/document.py`) was read directly and
agrees.

Behavioural coverage is AGT-06's pytest-qt suite for the grid — one test per acceptance criterion,
both themes, headless — including the `REQ-P5-UI-032` reversion proof, which had to **fail against
the unfixed strip** before the fix was accepted. Accessibility is covered by the a11y scan.

**What has no detector, stated rather than implied.** No script can tell that a future edit
hand-routed a header drag into the body, added a second condition to the cell/body predicate, or
built a context menu that then refuses. Those are review invariants, and the tests only catch them
if someone writes the test for the specific regression. That is accepted risk, recorded here so it
is not mistaken for coverage.

## What this record does not verify

- **No measurement of the culling claim is recorded here.** That `QTableView` calls `data()` only
  for the exposed viewport is Qt's documented behaviour and the shipped design's premise; the grid
  open/scroll profiling the plan assigned to AGT-10 was Tier 1 (measured and reported, **no gate,
  no ceiling, no constant**) and its numbers are not restated in this ADR.
- **`ui/timeline_grid_view.py` was read at its module docstring, its class/`header` wiring and its
  overwrite-confirmation path — not in full** (≈800+ lines). The three-zone description above is
  the module's own stated design corroborated at those points, not a line-by-line audit.
- **No suite was run for this record.** The pytest-qt grid suite is named as the detector, not
  executed here; `tests/scripts/test_check_doc_references.py` is the only suite this ADR's own
  change ran.
- **The CF-56 fix's outcome is not re-confirmed here.** This ADR records the grid's design and why
  CF-56 motivates it; whether the strip's own left-drag repair landed as specified is
  `REQ-P5-UI-032`'s record, not this one.

## Why this record is late

The decision was made on 2026-08-17 and its ADR was assigned to `phase-5-timeline-grid` **T25**
(owner AGT-08), which was never executed while the code that cites it shipped
(`pixelart_creator/ui/timeline_grid_view.py:6`). The number is fixed by that citation, not chosen
here: writing at `0057` rather than at `highest + 1` is the deliberate exception to the adr-author
numbering rule, because renumbering would break the trail this record exists to restore.
