<!-- surface-only: bundle — in-app orientation content; no site page by design -->
# The right-click colour hub

The **colour hub** is a contextual menu you summon **right where you are working**:
**right-click** on the canvas and it opens at the cursor. It gives you two fast ways
to pick a colour — a curated **Favourites** list and a full **colour wheel** with live
**colour-theory harmonies** — and applies your choice immediately.

## Opening the hub

Right-click anywhere on the [canvas](canvas-and-view.md). The colour hub appears
anchored at the cursor, so you never travel to a far-off panel to change colour. Pick a
colour and it becomes the **active colour** at once; the active swatch updates to
reflect it. **Right-click again while the hub is open dismisses it** without
picking anything, so you can back out and keep painting exactly where you were.

## Favourites

**Favourites** is your personal, persisted list of go-to colours.

- **Add** the current colour to Favourites so it is one click away next time.
- **Remove** a colour you no longer need.
- **Reorder** favourites so the colours you use most sit first.

Your Favourites list **persists** between sessions, so your working palette is always
there when you reopen the app. Clicking a favourite applies it immediately.

There is also a gesture that reaches Favourites without opening the hub at all:

| Gesture | Result |
| --- | --- |
| **Middle-click** | Selects the first Favourites entry and makes it the active colour, on the spot, whether or not the hub is open. |

## The colour wheel

The **colour wheel** is a Canva-style RGB wheel for picking any colour by hue and
saturation, with a value (brightness) control. As you move around the wheel the active
colour updates live.

## Live colour-theory harmonies

While you pick on the wheel, the hub shows **harmony swatches** derived from your
current colour using standard colour theory, so you can build a coherent palette
without guessing:

| Harmony | Relationship to your colour |
| --- | --- |
| **Complementary** | The opposite hue (+180°) — maximum contrast. |
| **Analogous** | The neighbours (±30°) — calm, cohesive schemes. |
| **Triadic** | Two hues 120° away (±120°) — balanced and vibrant. |
| **Tetradic** | Three hues at evenly spaced 90° intervals — four-colour, high contrast. |
| **Split-complementary** | The two hues either side of the complement (±150°). |
| **Shade / tint ramps** | Darker (shade) and lighter (tint) steps of your colour. |

The wheel itself and the harmony swatches — the small circles arranged around it —
behave differently, and the two are worth keeping apart:

- **The wheel pad is not a swatch.** Dragging it sets the colour of whichever
  harmony circle is currently selected; it has no double-click of its own.
- **A single click on a harmony circle paints with that circle's colour right
  away**, and leaves the circle's own colour untouched — nothing about the wheel
  or the circle changes, only your canvas does.
- **Double-click a circle to adopt its colour instead** — that makes it your
  active colour without painting anything. Keyboard activation does the same:
  focus a circle with Tab and press **Space** or **Enter** to adopt it.

So a single click is for painting on the fly with a harmony colour without
disturbing your active colour, and a double-click (or Space / Enter on a
focused circle) is for committing to it as your active colour. The harmonies
recompute live as you move around the wheel.

## Applying and saving

- **Apply** — the picked colour becomes active immediately and the active swatch
  reflects it, so your next stroke uses it.
- **Save to Favourites** — keep a colour you like for later.

## Palettes and indexed documents

The colour hub works alongside your document's **palette**. On an **indexed** document
the palette is the fixed set of colours the artwork uses; you can load palettes by
dropping a `.gpl`, `.hex`, or `.pal` file onto the window (see
[Drag-and-drop import](drag-drop-import.md)). Replacing the palette is a single
undoable step.

## Related topics

- Paint with your chosen colour on [the canvas](canvas-and-view.md).
- Manage colour mode (RGBA vs indexed) in [The layer panel](layers.md).
