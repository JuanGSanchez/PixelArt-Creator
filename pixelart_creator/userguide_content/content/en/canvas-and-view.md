<!-- surface-only: bundle — in-app orientation content; no site page by design (WP-8 unit 2d) -->
# The canvas: zoom, pan & the grid

The **canvas** is the main drawing surface — a large scene that supports documents up
to the platform maximum of **7680 × 4320 (8K)**. It renders your artwork with
**nearest-neighbour** scaling and **anti-aliasing off**, so pixels always stay crisp
and square at any zoom, exactly as pixel art should look.

## Navigating: zoom & pan

- **Zoom** — zoom in to work on individual pixels and out to see the whole piece.
  Zooming is centred so the point under the cursor stays put, which keeps you oriented
  while you scale up and down. Zoom is a **view** action; it never changes your
  artwork and is not an undo step.
- **100 % is the lowest zoom level.** You can no longer zoom out past 1:1, even on a
  document larger than the window. Below 100 % a single document pixel can fall
  between screen sample points and simply not be drawn — strokes appeared to vanish
  as you zoomed out. Explore a large document by **panning** instead: every corner of
  the canvas can be brought to the centre of the view that way.
- **Pan** — scroll the view horizontally and vertically to reach any part of a large
  canvas. Because the scene is prepared once for the full document size, panning across
  an 8K canvas stays smooth — only the part of the canvas visible in the viewport is
  drawn, so off-screen regions cost nothing to scroll past.
- **Zoom In / Zoom Out** — these two view actions step between the same fixed preset
  stops as the keyboard shortcuts (100 %, 200 %, 400 %, 800 %, 1600 %, 3200 %,
  6400 %): **Zoom In** snaps up to the next stop and **Zoom Out** snaps down to the
  previous one. That is a discrete jump, unlike the continuous, cursor-anchored zoom
  you get from scrolling the mouse wheel over the canvas.

> **Large canvases stay responsive.** The renderer draws only the region currently
> exposed in the viewport and repaints only the small area an edit actually changes,
> so painting on an 8K canvas stays inside the 60 fps frame budget.

## The checkerboard is your canvas boundary

The transparency checker is not decoration behind the artwork — it **is the pixel
lattice**: one alternating checker square is exactly one document pixel. The checker
is also bounded: it stops exactly at the edge of the canvas, a flat workspace colour
fills the surrounding area, and a thin border traces the boundary between them, so you
can always see where the drawing surface ends. Previously the checker ran on past the
canvas with nothing marking the edge, which made it easy to mistake a checker square
for a pixel.

## The pixel grid

The **pixel grid** helps you place pixels precisely, and it is **on by default** for a
new document.

- **Toggle the grid** from the view controls. It is an overlay drawn on top of the
  artwork — it never becomes part of your pixels and never appears in an export.
- The grid is legible in both the light and dark themes, drawn so it reads clearly
  over any artwork colour.
- **On does not mean drawn.** The grid only appears once a pixel's on-screen edge is
  at least 8 screen pixels across. At 100 % zoom a document pixel is smaller than
  that, so you will not see grid lines even with the grid switched on — zoom in and
  they appear. If you turn the grid on and see nothing change, this is why; it is not
  a bug.
- When you are zoomed far out, a dense grid would be unreadable, so the overlay
  gracefully stops drawing until you zoom back in.

## Snapping

With grid snapping on, the tools align to the grid so a stroke lands exactly on pixel
boundaries. This is especially useful when placing tiles or aligning shapes. Snapping
is a view/tool setting, not an edit.

## Painting on the canvas

- **Left-click** (and drag) paints with the active tool and the active colour. The
  active colour comes from the [colour hub](colour-hub.md) or the palette. Each stroke
  is pushed as one undo step.
- **Right-click** opens the contextual [colour hub](colour-hub.md) at the cursor, so
  you can pick or change your colour without leaving the canvas.

## Resizing the canvas

**Image ▸ Canvas Size…** changes the canvas dimensions themselves — it does not
resample a single pixel. Enter a new width and height (each up to the platform
ceiling of **7680 × 4320**, i.e. 8K) and click **OK**; every layer and mask in every
frame is cropped or padded to the new size, anchored at the top-left, so existing
artwork never shifts and any newly exposed area is transparent. Click **Cancel** to
leave the document exactly as it was. The resize applies as one undoable step.

This is a different operation from resampling the artwork to a new size — Canvas
Size only changes how much canvas there is; it never stretches or shrinks the
pixels you already have.

## Related topics

- Choose and manage colours in [The right-click colour hub](colour-hub.md).
- Stack and composite your work with [layers](layers.md).
- Select and reposition regions in [Selection & floating move/copy](selection-and-transform.md).
- Add non-destructive [grids, guides and other visual aids](visual-aids.md) for
  precise placement.
