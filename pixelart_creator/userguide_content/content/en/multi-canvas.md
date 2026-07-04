# Multiple canvases (artboards)

You can open several documents / artboards at once, each in its own **tab**.

## Isolated tabs

Each open canvas is fully **state-isolated**. A tab owns its own:

- layer tree (layers, groups, masks, reference / smart layers);
- palette and colour mode;
- undo / redo history;
- composited view and canvas geometry.

Switching to a tab makes that canvas the active context — its layer tree, palette,
undo stack and composite become current, and the layer panel repopulates to match it.

Because tabs are isolated, an operation in one canvas **never** affects another:
painting, changing layer attributes, reordering, grouping, or undoing in tab A leaves
tab B's tree, composite and undo history untouched.

## Working across artboards

- Each artboard can have a different canvas size, palette and colour mode.
- Undo is per-tab: undoing does not reach across artboards.
- Saving a document writes that tab's own layer tree to its `.pixproj` file.

> **Tip.** Use separate artboards for variants of the same sprite (for example colour
> swaps or poses) so their edit histories stay independent.

## Multiple *canvases* vs multiple *views*

Multiple canvases are **isolated** tabs — each a *different* document. That is
different from **multi-view**, which opens several windows onto **one** shared document
that stay in sync. See [Visual aids & UX](visual-aids.md) for multi-view editing.
