# Canvas navigation: zoom & fit

The **View** menu carries a small set of commands that change how you are
*looking* at a document — never the document itself. Zooming, panning and
fitting the view are **view** actions: none of them is an undo step, and
none of them touches a single pixel.

## Fit to Content

**View ▸ Fit to Content** (REQ-IS-UI-018) zooms and centres the active tab on
the **painted-pixel bounding box** of the current frame — the smallest
rectangle that contains every non-transparent pixel — instead of the whole
document rectangle. It is the named, keyboard- and screen-reader-reachable
twin of the **Shift+middle-click** gesture already available on the canvas
(see the in-app guide's own **Canvas: zoom, pan & the grid** page for that
gesture).

- If the active frame has no non-transparent pixel yet, or no document is
  bound (for example immediately after creating a blank canvas), the command
  falls back to fitting the whole document rectangle instead of failing or
  doing nothing.
- The resulting zoom is clamped to the platform's zoom floor and ceiling, the
  same limits every other zoom action respects.
- Like every other command in this section, it is a **view** action: it is
  never pushed onto the undo stack.

This is the tool to reach for after panning or zooming away from a small
piece of artwork on a large canvas — one command brings the painted area
back into view at a sensible size, without you having to hunt for it or zoom
all the way back out to the full document.

## Related topics

- The rest of the canvas's zoom, pan and grid behaviour is covered in the
  in-app user guide's own **Canvas: zoom, pan & the grid** page, reachable
  from the application's Help menu.
