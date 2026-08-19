# Drag-and-drop import

Drag a file straight from your operating system's file explorer (Windows
Explorer, macOS Finder, Linux Nautilus) **into** the PixelArt Creator window and
it does the obvious thing for that kind of file. There is no File ▸ Open dance —
drop it anywhere on the window and the app routes it **by file type**, not by
where on the window you let go.

!!! note "Routing is by type, never by drop location"
    An image *always* opens as a new document, a `.pixproj` *always* opens as a
    project, and a palette file *always* loads into the active palette — no
    matter where on the window you drop it. In a single drop you can mix types
    and even drop several files at once.

## Drop an image → a new document tab

Drop a **`.png`, `.jpg`, `.jpeg`, `.bmp` or `.gif`** and it opens as a **brand
new canvas / document tab** that becomes active. It is imported as a new
document, **not** as a layer on the document you are editing — your current
document is untouched.

- The new document is **RGBA** at the image's own width and height. A paletted
  (indexed) PNG or GIF is expanded to RGBA on import.
- For an **animated GIF**, the **first frame** is imported.
- Import is **read-only on disk** — dropping a file never modifies the source.

!!! warning "Image size limit"
    An image larger than the canvas maximum (**7680 × 4320**) is **rejected**
    with an error notice — it is never silently cropped or scaled. Convert or
    resize it outside the app first.

## Drop a `.pixproj` → open the project (with a save guard)

Drop a **`.pixproj`** and it opens as a project.

If the document you are currently editing has **unsaved changes**, the app first
shows a **Save / Discard / Cancel** prompt so you never lose work by accident:

| Choice | Result |
| --- | --- |
| **Save** | Saves the current document, then opens the dropped project. |
| **Discard** | Opens the dropped project without saving. |
| **Cancel** | Aborts the open — nothing changes. |

If the current document has **no** unsaved changes (or none is open), the
project opens immediately with no prompt.

## Drop a palette → load it into the active palette (undoable)

Drop a **`.gpl` (GIMP), `.hex` (plain hex list) or `.pal` (JASC-PAL text)**
palette file and its colours **replace** your active document's palette.

- The replacement is a **single undoable step**: one **Undo** restores your
  previous palette exactly.
- If no document is open, the drop is a harmless no-op with a short notice.

!!! note "Which palette formats?"
    The v1 palette set is the common **text** pixel-art formats: `.gpl`, `.hex`
    and `.pal`. The binary Adobe formats **`.aco`** and **`.aseprite`** are
    **not yet supported** — they are planned for a later iteration and are
    reported as an unsupported type for now.

## Dropping several files at once

A multi-file drop processes each file **independently, by its type, in the order
dropped**:

- several images → several new tabs;
- a `.pixproj` opens (honouring its unsaved-changes guard);
- palettes load one after another — the **last** palette dropped is the one that
  ends up active (each is its own undo step).

An unknown or unreadable file in the batch is skipped with a notice; the rest
still process. Dropping zero files does nothing.

## When a file can't be imported

Drag-and-drop never crashes the app:

- an **unsupported type** (for example a `.txt`, or an `.aco`/`.aseprite`
  palette) is **ignored** with a brief, non-blocking status notice;
- a **corrupt, undecodable or oversized** image, a **malformed** palette, or an
  **invalid** `.pixproj` shows an **error notice** naming the file and the
  problem, and leaves your work **exactly as it was** — no half-made tab, no
  half-loaded palette.

All prompts and notices are **translatable**, keyboard-reachable, and legible in
both the **light** and **dark** themes.

## What is not covered

- **Import as a layer** — an image always opens as a new document, never as a
  layer on the current one (a future "import as layer" is deferred).
- **Indexed import** of a paletted source image — images decode to RGBA; apply
  *Convert to Indexed* afterwards if you want an indexed document.
- **Animated GIF import** — only the first frame is imported.
- The **export / save-out** side of the pipeline, and dragging a file **out** of
  the app.
