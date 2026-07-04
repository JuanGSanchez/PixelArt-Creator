# The animation timeline

The **animation system** turns a document's list of frames into a *timeline*: add,
remove, reorder and duplicate frames; give each frame its own on-screen duration; play
the sequence back in one of four modes; see adjacent frames with onion skinning; and
group ranges of frames into **named animations** with frame tags. Every frame and tag
edit is a single undo step.

This reaches **Aseprite**-parity for timeline, playback, onion skinning and tags, and
goes beyond it with **several independent named animations in one file** (walk, run,
idle) via frame tags.

> **Per-frame independent layers.** Each frame owns its **own** layer stack, composited
> with the same [layer engine](layers.md) (visibility / opacity / blend mode / groups /
> masks are all honoured per frame). On an **indexed** document a frame is a single
> indexed layer, and onion skinning is not shown (the compositor is RGBA-only).

## The frame strip

The **Timeline** panel shows the document as a horizontal strip of frames in playback
order (left to right); each cell carries a thumbnail, its frame number and any tag
markers that span it. The layer panel reflects the layers of the frame that is
currently active.

- **Select a frame** — click it (or use the arrow keys). The canvas shows that frame's
  composited layer stack. Selecting is a view action, so it is **not** undoable.
- **Scrub** — press and drag along the strip; the canvas continuously shows the frame
  under the cursor. Scrubbing is also **not** undoable.

## Managing frames

The timeline toolbar edits the sequence. Each action is **exactly one undo step**:

| Action | What it does |
| --- | --- |
| **Add Frame** | Inserts a new empty-layer frame after the active frame. |
| **Remove Frame** | Deletes the active frame. **Disabled when only one frame remains** — a document always keeps at least one frame. |
| **Duplicate Frame** | Inserts a **deep, independent copy** after the source (its layers and duration copied). Editing the copy never changes the original. |
| **Drag a frame** | Drag a cell to a new position to **reorder** it. Playback and scrub follow the new order. |

Undo restores the exact prior sequence — contents, order and durations.

## Per-frame duration

Each frame has its own **duration** in milliseconds, shown in the strip's duration
editor (new frames default to the standard frame duration). Type a new value and commit
it (Enter / focus-out) to set that frame's dwell time as one undo step. Durations must
be **positive** — a non-positive value is rejected. A 500 ms frame lingers about five
times as long as a 100 ms frame during playback.

> **Uniform frame rate.** A uniform FPS is just the same duration on every frame
> (`duration_ms = round(1000 / fps)`). Per-frame milliseconds always remain the single
> source of playback timing.

## Playback

The **playback controls** drive the displayed frame over time:

- **Play** starts (or resumes from a pause) over the whole document.
- **Pause** freezes on the current frame.
- **Stop** halts and returns to the frame that was active when you pressed Play.
- **Space** toggles play/pause.

The **mode selector** chooses how the sequence advances (default **Loop**):

| Mode | Behaviour over a 4-frame range |
| --- | --- |
| **Loop** | `0,1,2,3,0,1,2,3,…` — wraps forever. |
| **Once** | `0,1,2,3` then **stops** on the last frame. |
| **Reverse** | `3,2,1,0,3,2,1,0,…` — wraps backwards. |
| **Ping-Pong** | `0,1,2,3,2,1,0,1,2,3,…` — bounces; the **endpoints are not doubled**. |

Playback honours each frame's own duration, so changing a duration changes that frame's
on-screen time on the next pass.

> **First play of a large animation prepares off the main thread.** The first time you
> play a range on a large (for example 8K) multi-layer document, each frame's flattened
> composite has to be built once. This happens **off the GUI thread** with a small,
> **cancellable** progress strip in the status bar — the window stays responsive, and
> playback **streams** frames as they become ready rather than freezing. Once frames
> are prepared they are cached, so replay and scrubbing run at 60 fps.

## Onion skinning

Onion skinning shows **adjacent frames** behind the one you are editing, so you can
align motion.

- **Enable** it with the onion toggle. Ghost frames render behind the active frame; the
  active frame itself is unchanged.
- Set how many **previous** and **next** frames to show (each `0` disables that side;
  the default is **1 previous / 1 next**).
- Set the **tint** for each side — **red** for previous, **blue** for next by default.
  Farther frames fade out.

Onion counts and tints are **view settings** — changing them updates the overlay live
and creates **no** undo step. Onion skinning is **suppressed during playback** (it is an
editing aid, not a preview) and during a scrub.

## Frame tags (named animations)

A **frame tag** names a range of frames as its own animation. One file can hold several
tags — for example `walk` over frames 1–4, `idle` over frame 0 — and they may overlap.

From the **Frame Tags** panel:

- **Add / Edit / Delete** a tag — each opens a dialog for the tag's **name**, inclusive
  **from / to** range, **playback mode**, **repeat** count (`0` = infinite for looping
  modes) and a **colour**. Each change is **one undo step**. A tag is shown as a span
  across the frames it covers.
- **Play Tag** plays the selected tag as its own named animation: it runs the tag's
  range under the **tag's own** playback mode and repeat, independently of the global
  playback mode. An **Once** tag with repeat 3 plays its range three times, then stops.

When you add or remove frames, tag ranges are kept valid automatically (clamped into the
new frame count); undo restores both the frame change and the original tag ranges
together.

## Persistence

Frames, per-frame durations and frame tags all round-trip through `.pixproj`. Saving
then reopening a tagged animation restores the frame order, every frame's duration, and
the full tag collection identically. Projects saved by earlier versions (before tags
existed) still open — they load with an empty tag collection.

## Undo, redo and what is *not* undoable

- **Undoable (one step each):** add / remove / reorder / duplicate frame, set a frame's
  duration, and create / edit / delete a tag.
- **Not undoable (view state):** selecting or scrubbing a frame, playing / pausing /
  stopping, and changing onion-skin counts or tints.

## Related topics

- Export your animation as a GIF, sprite sheet or atlas in
  [Export & pipeline integration](export-and-pipeline.md).
- Record a session as you animate with the timelapse tool in [Visual aids](visual-aids.md).
