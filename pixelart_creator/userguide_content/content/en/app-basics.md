<!-- surface-only: bundle — in-app orientation content; only lightly covered by the site's index.md framing prose, no dedicated site page by design (WP-8 unit 2d) -->
# Getting started & the workspace

Welcome to **PixelArt Creator** — a desktop pixel-art studio with an 8K canvas, a
non-destructive layer system, an animation timeline, a tileset/tilemap editor, an
export pipeline, automation and scripting, visual aids, and cloud collaboration.
This topic orients you to the workspace so the rest of the guide makes sense.

## The main window at a glance

- **Menu bar** (top) — the entry point to every command, grouped into menus such as
  **File**, **Edit**, **View**, **Cloud**, and **Help**. The in-app User Guide you
  are reading now is opened from **Help ▸ User Guide** (or by pressing **F1**).
- **Canvas** (centre) — the drawing surface. See
  [The canvas: zoom, pan & the grid](canvas-and-view.md).
- **Docks / panels** (sides) — the layer panel, the animation timeline, the tileset
  panel, and the cloud/collaboration panels. Most panels can be toggled on or off and
  arranged to suit your workflow.
- **Status bar** (bottom) — coordinate readouts, progress indicators for background
  work (exporting, playback preparation, cloud saves), and brief notices.

## Documents & tabs

Each open drawing is a **document** shown in its own **tab**. A document has a size,
a colour mode (**RGBA** or **Indexed**), a palette, a layer tree, and — if you
animate it — a list of frames. You can keep several documents open at once; see
[Multiple canvases (artboards)](multi-canvas.md). Documents are saved as
**`.pixproj`** project files, the validated, versioned save format the whole app
(and the cloud layer) uses.

## Undo & redo

Almost every edit — painting, a layer change, a transform, a frame edit, an
automation run — is pushed onto the document's **undo stack** as **exactly one**
step. **Undo** reverses the last step and **Redo** re-applies it. Undo history is
**per tab**, so undoing in one document never reaches into another. A handful of
actions are intentionally *not* undoable because they are view state rather than
edits: selecting or scrubbing a frame, toggling onion skinning, adding a guide, and
opening the cloud/collaboration panels.

## Themes (light & dark)

The application ships matched **light** and **dark** themes. Switch between them from
the application's theme control; every panel, dialog, overlay, and this User Guide
render correctly and stay legible in both. Colours are defined once by role, so the
theme is consistent everywhere.

## Language

The interface is fully translatable. When you change the active language, every menu,
label, and message re-translates live — you do not need to restart. This User Guide's
chrome (its title, section labels, search box, and navigation) follows the active
language; guide content is shown in your language when a localised version is bundled,
otherwise it falls back to the default (English) text.

## Keyboard shortcuts

Common commands have keyboard shortcuts, shown next to their menu entries. A few you
will use constantly:

| Shortcut | Action |
| --- | --- |
| **F1** | Open this User Guide |
| **Ctrl+Z** / **Ctrl+Y** | Undo / Redo |
| **Space** | Toggle animation play/pause |
| **Ctrl+Shift+E** | Open the Export dialog |
| **Esc** | Cancel the current in-progress action (e.g. a floating move) |
| **Enter** | Commit the current in-progress action |

## Where to go next

- Draw on the [canvas](canvas-and-view.md) and pick colours from the
  [colour hub](colour-hub.md).
- Organise your art with [layers](layers.md) and [blend modes](blend-modes.md).
- [Select and move](selection-and-transform.md) regions of your artwork.
- Animate with the [timeline](animation-timeline.md), build levels with the
  [tileset & tilemap editor](tileset-and-tilemap.md), and ship assets through
  [export](export-and-pipeline.md).
- Speed up repetitive work with [automation & scripting](automation-and-scripting.md),
  draw more precisely with [visual aids](visual-aids.md), and work together through
  [cloud](cloud-and-collaboration.md) and [collaboration](collaboration.md).
