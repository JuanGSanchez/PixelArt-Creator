# Floating selection (move / copy)

A **floating selection** lets you pick up the colours inside an active selection
and move — or copy — them as a **live, non-destructive preview**. The pixels
*underneath* the floating selection are **not changed** until you commit, so a
move is always safe to re-position or abandon.

This is the behaviour you know from Aseprite, Pro Motion NG, Pixelorama and
Krita: lift, drag, drop.

!!! note "Active layer only"
    A floating move/copy operates on the **active layer**. On an indexed
    document that is the single indexed layer. Other layers are untouched.

## Before you start: make a selection

The float lifts whatever selection is already active. Make one first with the
**rectangle**, **lasso** or **magic-wand** selection tools — the floating move
does **not** create a new selection shape, it reuses the mask you already have.

## Lift and move (drag)

1. With the selection/move tool active, **press inside** the active selection.
   The masked pixels lift into a floating preview.
2. **Drag.** The floated colours follow the cursor; the origin region reads as
   **cleared to transparent** (index 0 in indexed mode) in the live preview.
3. The underlying pixels are **not yet modified** — only the preview changes.

Pressing **outside** the active selection does **not** lift; it starts a new
selection with the shipped tools as usual.

## Copy instead of move: hold Ctrl

Hold **Ctrl** while dragging to switch the float to **COPY**:

- the **origin stays intact** (nothing is vacated), and
- a **copy** of the colours floats to the cursor.

A copy-mode cursor / affordance signals that you are copying. You can toggle
between move and copy **during** the drag by pressing or releasing Ctrl.

!!! warning "Ctrl is the only copy modifier — not Alt"
    Copy is **Ctrl only**. **Alt is not a copy modifier**: an interior Alt-drag
    is the shipped selection-build **subtract** gesture, and it keeps that
    meaning. Holding **Ctrl+Alt** on an interior drag resolves to Alt-subtract,
    not copy — use plain **Ctrl** to copy.

| Interior drag | Result |
| --- | --- |
| _no modifier_ | Lift / **move** the selection (origin vacated on commit) |
| **Ctrl** | **Copy** the selection (origin kept) |
| **Alt** | **Subtract** from the selection (shipped build gesture) |
| **Shift** | **Add** to the selection (shipped build gesture) |

## Commit or cancel

The float **commits** on any of:

- **releasing** the mouse button,
- pressing **Enter / Return**, or
- **switching tools** (or switching canvas tab).

On commit the change is applied as **exactly one undoable step**:

- **Move** — the origin is written transparent (index 0 in indexed mode) and the
  colours are stamped at the destination.
- **Copy** — the colours are stamped at the destination and the origin is left
  unchanged.

After a commit the selection mask **follows to the destination**.

Press **Esc** to **cancel**. Because the float never wrote to the buffer, cancel
restores the pre-move canvas **exactly** and records **no** undo entry; the
selection mask returns to its pre-lift position.

!!! tip "A click without a drag costs nothing"
    Committing at a zero offset (a click inside the selection with no move) is a
    no-op — it creates no undo step.

### Overwriting a non-empty destination

If the destination you are about to commit onto already has pixels on it, an
**Overwrite Existing Pixels?** dialog asks first. **Continue** applies the commit as
usual; **Cancel** applies nothing and leaves the float active at its current offset,
so you can keep repositioning it. Tick **"Don't ask again for this project"** and the
suppression is only recorded once you actually accept the dialog — ticking it and
then cancelling records nothing, so a cancelled commit never silently changes this
setting for the project.

## Off-canvas edges

You can drag a float **partly or fully off the canvas**. On commit the
off-canvas pixels are **discarded** (never wrapped), so you can push art right to
the edge without error. For a move, the whole in-bounds origin is still vacated
regardless of how far you dragged.

## Undo, redo and rendering

- A committed move or copy is **one** undo step: **undo** restores the pre-move
  buffer exactly; **redo** re-applies it.
- The floating preview renders **nearest-neighbour with anti-aliasing off** at
  any zoom, and is legible in both the **light** and **dark** themes.
- The live drag preview updates only the region the float touches, so it stays
  within the 16 ms / 60 fps frame budget even on an 8K canvas.

## What is not covered

- **Rotating or scaling** the selection *while it floats* — use the transform
  tools after committing.
- A **move-all-layers** variant — the float is active-layer only.
- **Cross-document** drag of a float, or saving a float into a `.pixproj` — a
  float is a transient editing state, always committed or cancelled first.
