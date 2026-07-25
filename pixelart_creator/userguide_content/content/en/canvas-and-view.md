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
- **Pan** — scroll the view horizontally and vertically to reach any part of a large
  canvas. Because the scene is prepared once for the full document size, panning across
  an 8K canvas stays smooth — only the part of the canvas visible in the viewport is
  drawn, so off-screen regions cost nothing to scroll past.

> **Large canvases stay responsive.** The renderer draws only the region currently
> exposed in the viewport and repaints only the small area an edit actually changes,
> so painting on an 8K canvas stays inside the 60 fps frame budget.

## The pixel grid

At high zoom a **pixel grid** helps you place pixels precisely.

- **Toggle the grid** from the view controls. It is an overlay drawn on top of the
  artwork — it never becomes part of your pixels and never appears in an export.
- The grid is legible in both the light and dark themes, drawn so it reads clearly
  over any artwork colour.
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

## Related topics

- Choose and manage colours in [The right-click colour hub](colour-hub.md).
- Stack and composite your work with [layers](layers.md).
- Select and reposition regions in [Selection & floating move/copy](selection-and-transform.md).
- Add non-destructive [grids, guides and other visual aids](visual-aids.md) for
  precise placement.
