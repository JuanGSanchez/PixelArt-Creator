# PixelArt Creator — User Guide

PixelArt Creator is a pixel-art editor built around an 8K-capable canvas, a
non-destructive layer model, and a fast region-scoped compositor.

This guide covers the user-facing workflows shipped through **Phase 4 — Layer &
Canvas System**:

- **[Layer panel](usage/layers.md)** — opacity, visibility, lock, blend mode,
  reordering, add / remove / duplicate, groups, masks, reference and smart
  layers. Every action is a single undo step.
- **[Blend modes](usage/blend-modes.md)** — the twelve `BlendMode` members and
  what each one does.
- **[Multiple canvases](usage/multi-canvas.md)** — opening several
  documents / artboards as isolated tabs.
- **[Floating selection](usage/floating-selection.md)** — lift a selection and
  move (drag) or copy (Ctrl+drag) its colours as a non-destructive preview,
  committing on release / Enter / tool-switch, Esc to cancel.
- **[Drag-and-drop import](usage/drag-drop-import.md)** — drag a file from your
  OS file explorer into the app: an image opens as a new document, a `.pixproj`
  opens as a project (with an unsaved-changes guard), and a `.gpl`/`.hex`/`.pal`
  palette loads into the active palette (undoable).
- **[Animation timeline](usage/animation.md)** — build a frame timeline
  (add / remove / reorder / duplicate, per-frame duration), play it back
  (loop / once / ping-pong / reverse), use onion skinning, and group frame
  ranges into named animations with frame tags.
- **[Tilemap & level design](usage/tilemap.md)** — slice a source image into a
  tileset, paint a multi-layer, infinite tilemap with stamp / erase / fill,
  let auto-tiling resolve borders, flip / rotate tiles as you place them, and
  export / import the map as Tiled-compatible JSON.
- **[Export & pipeline integration](usage/export.md)** — export a project as a
  PNG, an animated GIF, a sprite sheet or a packed texture atlas with
  Aseprite-style JSON metadata and Unity / Godot engine presets, queue several
  targets with batch export, or run it headlessly with the `pixelart-export`
  command line — all byte-reproducible.
- **[Automation & extensibility](usage/automation.md)** — record and replay
  macros (`.pixmacro`, deterministic), run bounded-DSL scripts (no `eval`/`exec`),
  extend the app with trusted, consent-gated plugins, batch-recolour many targets
  at once, generate content procedurally, and run any automation headlessly with
  the `pixelart-run` command line.
- **[Visual aids & UX](usage/visual-aids.md)** — a live real-size preview, guides
  & rulers with snapping, isometric and perspective grids, a PureRef-style
  reference board, multiple synced views of one document, and reproducible
  timelapse recording — all non-destructive view aids.
- **[Cloud, versions & recovery](usage/cloud.md)** — connect a cloud provider,
  save a project to the cloud and open it again from any session, browse a full
  version history and restore an earlier save, and rely on background autosave
  with a crash-recovery prompt on restart — all behind one provider-agnostic
  interface.
- **[Shared projects & comments](usage/collaboration.md)** — share a project with a
  named member roster (owner / editor / viewer roles), leave and resolve threaded
  comments, and see who else is present, with concurrent edits merged by a
  deterministic hybrid convergence model (real-time co-editing, live cursors and
  art branching arrive in a later slice).
- **[Asset library](usage/asset-library.md)** — catalog your sprites, animations,
  tilesets, tilemaps and palettes as named, tagged assets and find them fast with
  search and filter by name, tag and kind, from the **&Library** menu.
- **[Asset dependencies & break detection](usage/dependency-graph.md)** — a queryable
  graph of how assets reference one another (`sprite → animation → tileset → tilemap`)
  and a passive indicator that flags — never blocks — a reference broken by a missing or
  changed asset.
- **[Asset versioning & cross-project reuse](usage/asset-versioning.md)** — an
  append-only revision history per asset (inspect and restore, restore adds a new head),
  reference-not-copy reuse of a shared asset across projects, export/import of a project's
  referenced assets as a self-contained bundle, and optional cloud backing of the shared
  blobs while still working fully offline.

For colour, palette and indexed-mode workflows see the Phase-3 material; for the
canvas, tools and theming see the Phase-1 material.

!!! note "Colour mode"
    The layer stack and blend modes described here apply to **RGBA** documents.
    An **indexed** document is single-layer by design (the compositor is
    RGBA-only). Converting a multi-layer RGBA document to indexed flattens the
    stack into one indexed layer, and the conversion is fully undoable. See the
    [layer panel](usage/layers.md#colour-mode-and-indexed-documents) page.
