# Blend modes

Each layer (and group) composites using a **blend mode** chosen from the per-layer
dropdown in [the layer panel](layers.md). PixelArt Creator ships **twelve** modes —
**Normal** plus the eleven non-normal **separable** modes from the W3C *Compositing and
Blending Level 1* specification (the same set and results as Photoshop / Krita / SVG).

Blending is done on **straight (non-premultiplied) alpha** in a normalised
floating-point working space, then written back to 8-bit RGBA. **Normal** is straight
source-over alpha compositing.

## The twelve modes

| Mode | Effect |
| --- | --- |
| **Normal** | Straight alpha source-over. A fully opaque layer replaces what is below; a fully transparent layer leaves it unchanged. |
| **Multiply** | Multiplies the layer with what is below — always darkens. White is neutral; black yields black. |
| **Screen** | Inverse of multiply — always lightens. Black is neutral; white yields white. |
| **Overlay** | Multiply in the dark tones, screen in the light tones — boosts contrast (relative to what is below). |
| **Darken** | Keeps the darker of the two channel values. |
| **Lighten** | Keeps the lighter of the two channel values. |
| **Colour Dodge** | Brightens what is below to reflect the layer; strong lightening. |
| **Colour Burn** | Darkens what is below to reflect the layer; strong darkening. |
| **Hard Light** | Overlay with the layer and backdrop roles swapped — a harsh spotlight. |
| **Soft Light** | A gentler hard light — soft dodge / burn depending on the layer value. |
| **Difference** | Absolute difference of the two values — equal colours cancel to black. |
| **Exclusion** | Like difference but lower contrast in the mid-tones. |

> **Opacity and blend mode combine.** A layer's opacity scales its contribution **for
> every** blend mode, not only Normal. A hidden layer contributes nothing regardless of
> mode.

## How the stack is composited

Layers are composited **bottom-to-top** over a running result: each visible layer's
pixels are blended over what is below using that layer's blend mode and opacity (and its
mask, if any). A stack of Normal layers is exactly the same as folding straight alpha
source-over from the bottom up. Compositing never mutates the source layer buffers — it
is non-destructive.

A single edit recomposites only the **affected region**, so painting on a large canvas
stays responsive.

## Performance

On an 8K canvas (7680 × 4320) a single-pixel paint recomposites its small dirty region
in about **1 ms**, comfortably inside the 16 ms / 60 fps frame budget. Some heavier
interactions at low zoom — dragging the opacity slider, or an attribute change that
repaints a large viewport across many layers — are currently CPU-bound and can exceed
the budget; full GPU-shader compositing is a planned later enhancement.

## Related topics

- Set a layer's blend mode and opacity in [The layer panel](layers.md).
