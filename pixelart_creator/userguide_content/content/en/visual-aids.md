# Visual aids & UX

The **visual-aids layer** helps you *see and place* your work precisely without ever
changing the artwork itself. It adds a **real-size preview**, **guides & rulers**, an
**isometric grid**, a **perspective grid**, a PureRef-style **reference board**,
**multi-view editing**, and **timelapse recording**.

Every aid is **non-destructive**: enabling a grid, dropping a guide, adding a reference
image, opening a second view, or recording a timelapse pushes **no** undo step and never
touches your pixels. Only actual drawing edits are undoable, and they are unchanged by
this layer.

> **Tested geometry, not a UI hack.** All the snapping, ruler ticks and the real-size
> scale come from a **pure, unit-tested geometry engine** with **zero Qt**. The overlays
> only *render* what the geometry returns — the snap math is the same code the tests
> exercise, so snapping is correct and reproducible.

## Real-size preview

The **Real-Size Preview** window shows your document at its **true physical size**, so you
can judge how a sprite or icon will actually look.

- The preview scales the document by exactly `screen_DPI / doc_PPI` — the document's
  pixels-per-inch (default **72**) against the monitor's physical DPI. Nothing else is
  applied.
- It is a **read-only** view of the **shared** document, so it **mirrors your edits live**
  — draw on the canvas and the preview updates as part of the same edit, no refresh
  button.

> **If real size looks wrong, calibrate.** Some monitors report an incorrect (or no)
> physical size, so the queried DPI is off. Click **Calibrate…**, hold a ruler against the
> on-screen bar, and enter its measured length; the preview then uses your measured DPI.
> The scale is also recomputed automatically when you move the window to a
> different-resolution monitor.

> **HiDPI is handled for you.** The scale is device-independent and Qt applies the
> display's device-pixel ratio itself — the preview does **not** multiply by DPR (doing so
> would double-scale on HiDPI screens).

## Guides & rulers

Turn on **rulers** to get a horizontal and a vertical ruler with a live **coordinate
readout**, and drag **guides** out of them to align elements.

- **Create a guide** — drag out of the top ruler for a horizontal guide, or out of the
  left ruler for a vertical guide.
- **Snap** — your cursor snaps to the nearest guide within a small tolerance. The
  tolerance is expressed in **screen pixels** (default **8 px**) and converted to document
  space by the current zoom, so the "stickiness" feels the same at every zoom level.
- Ruler ticks use a **nice-number** `1 / 2 / 5 × 10ⁿ` ladder with plain,
  locale-independent integer labels.

Guides are view state (up to **256** of them). Adding, moving or removing a guide is never
undoable.

## Isometric grid

Enable the **isometric grid** to draw on a **2:1 dimetric** diamond lattice (the pixel-art
isometric standard).

- The grid is drawn by projecting lattice cells through an **invertible** world↔screen
  transform, and your cursor **snaps to the nearest grid vertex** (with a deterministic
  round-half-up tie-break, so a point exactly between two vertices always resolves the same
  way).
- Grid spacing (tile width) is bounded to **2–1024 px**.
- **True-isometric** (about `1.732:1`) is configurable if you prefer it over 2:1 dimetric.

> **Zoomed-out grids fade out for performance.** When a tile's on-screen edge shrinks below
> **32 px** the lattice is too dense to read, so the overlay **skips painting** rather than
> blow the 16 ms frame budget. Zoom back in and it reappears.

## Perspective grid

Enable the **perspective grid** to draw with **1-, 2-, or 3-point** perspective.

- You place the **vanishing points** (up to **3**); the overlay draws a deterministic
  **guide-line fan** from each, plus the horizon line.
- Your cursor **direction-locks to the nearest vanishing line** when it is within the snap
  tolerance; beyond the tolerance there is **no snap**, so you can still draw freely.

## Reference board

The **Reference Board** is a PureRef-style board in its **own** window where you can gather
inspiration alongside your canvas.

- **Add** images, then **move**, **scale** and **z-order** each one; pan and zoom the whole
  board; and optionally keep the window **always on top**.
- The board holds up to **256** images and is **completely separate from your artwork** —
  reference images never composite into the document and never appear in an export.
- **Save / open** a board as a `.pixboard` file. The layout round-trips exactly. A
  malformed board file surfaces a clear error message — it never crashes and never executes
  anything from the file.

## Multi-view editing

Open **several views of the same document** at once — for example a zoomed-in detail view
next to a fit-to-window overview.

- Every extra view renders the **one shared document**, so an edit in the main canvas
  appears in **every** view (and the real-size preview) **immediately, with no manual
  refresh**.
- Each view keeps its **own** zoom and pan — those are per-view and are **not** synced.
- Up to **8** simultaneous views (the main canvas counts as one). Extra views are
  navigate-only (scroll/zoom); painting stays on the main canvas.

> **Multiple *views* vs multiple *canvases*.** This is different from
> [multiple canvases](multi-canvas.md): those are **isolated** tabs, each a *different*
> document with its own layers and undo history. Multi-view opens several windows onto
> **one** document that stay in sync.

## Timelapse recording

Open the **Timelapse** dock from **Aids -> Timelapse** to record and play back a
timelapse of your edit session, sharing how a piece was made.

- Press **Record** to start capturing; the recorder appends **one frame per committed
  edit** (each undoable command). Press it again to stop.
- Recording is **view/session state** — it is never undoable and never changes the
  document.
- **Save Timelapse / Open Timelapse** the session as a `.pixtimelapse` file. The session
  stores an ordered manifest of **command references, not pixels**, so it stays small and
  **replays deterministically**: the same recorded session replayed twice yields the
  **identical** frame sequence. Sessions are bounded to **4096** frames; a malformed file
  surfaces a user-facing error.

### Playback

Once a session is recorded or opened, the same dock plays it back:

- **Play / Pause** toggles playback of the reconstructed frame sequence; **Stop** halts
  it. An absolute **seek** control jumps straight to any frame, and a **speed** selector
  (0.25x, 0.5x, 1x, 2x, 4x) changes how fast frames advance — none of this touches your
  document, and while playback is running (or paused mid-sequence) document edits are
  refused until you stop.
- Playing back a session you **opened** from a `.pixtimelapse` file (rather than one you
  just recorded) shows a **Reopened Recording** banner, reminding you it is replaying the
  saved recording, not your current document.
- Playback can refuse to reconstruct a particular frame rather than show a wrong one.
  You may see: the recording has no reconstructible payload; a frame's payload is
  incomplete; a requested position is beyond the recorded range; the recording does not
  match the document's current undo history; or a frame lacks the stable identity
  playback needs. Each refusal is reported as a clear, specific message — never a silent
  skip or a crash.

> **Video/GIF export is a later handoff.** This release produces the reproducible **frame
> sequence** and its own playback. Encoding it to a shareable video or GIF reuses the
> [export pipeline](export-and-pipeline.md) as a later follow-up — the recorded sequence is
> that pipeline's input.

## Accessibility, themes & languages

Every visual-aids control exposes an accessible name (and a description where it is
non-obvious), is keyboard-reachable with a visible focus indicator, renders correctly in
both **light and dark** themes (overlay and guide colours are defined once by role and stay
legible over artwork), and has **fully translatable** text that re-sets on a language
change.

## What is not covered

- **Exporting a timelapse to video/GIF** — deferred to the export pipeline; this release
  ships the reproducible sequence.
- A **hosted / cloud reference-image library** — the board here is local.
- **AI-assisted perspective inference / auto-vanishing-point detection** — a later phase.
