# The layer panel

The **layer panel** lists the active document's layers and groups for the current
frame and exposes every per-layer control. It is the primary surface for
non-destructive editing.

## Reading the list

- Layers are shown **top-to-bottom in z-order**: the row at the **top of the list is
  the top of the stack** (drawn last / in front).
- Exactly one row is the **active layer** — it is the target of the paint tools.
- **Groups** appear as expandable / collapsible nodes containing their children.

## Per-layer controls

Each layer row exposes:

| Control | What it does |
| --- | --- |
| **Opacity slider** | Sets the layer's opacity from **0–100 %**. Applies to every blend mode, not just Normal. |
| **Visibility toggle** | Shows or hides the layer. A hidden layer contributes nothing to the composite. |
| **Lock toggle** | Guards the layer against **pixel** mutation. A locked layer's paint / fill / clear become no-ops; its opacity, visibility, blend mode and order can still change. |
| **Blend-mode dropdown** | Chooses one of the twelve [blend modes](blend-modes.md). |

> **Lock guards pixels only.** You can still focus a locked layer, change its opacity,
> hide/show it, and reorder it. Locking only stops painting into its pixels.

## Managing layers

- **Add** — inserts a new empty layer above the active layer.
- **Remove** — deletes the active layer. Removing the **last** layer of a frame is
  refused.
- **Duplicate** — inserts a pixel-for-pixel copy, with copied attributes, above the
  source.
- **Drag-to-reorder** — drag a row to a new position to change z-order; the canvas
  recomposites in the new order. Dragging into or out of a group re-parents the layer.

## Groups

- **Group** wraps the selected top-level layers in a new group node.
- **Ungroup** dissolves a group, promoting its children into the parent at the group's
  position.

A group **composites its children first**, then blends that single flattened result
over the stack using the **group's own** opacity and blend mode. A group with default
attributes (Normal, 100 %) composites identically to its ungrouped children. Hiding a
group hides its whole subtree. Group nesting is bounded.

## Masks

Attach a **mask** to a layer to modulate its alpha non-destructively:

1. Add a mask to the selected layer.
2. Select the mask to make it the paint target — painting now edits the mask buffer,
   not the layer's pixels.
3. Where the mask is 0 the layer is hidden; where it is at maximum the layer is fully
   shown; intermediate values are proportional.

An all-maximum mask is equivalent to no mask, and editing a mask never alters the
layer's own pixels. Attaching / removing a mask is undoable.

## Reference layers

Mark a layer as a **reference** layer to trace over it: it stays visible in the
composite but **rejects painting** (paint tools are no-ops on it), like a
purpose-declared permanent lock. The flag is reversible.

## Smart layers

Create a **smart layer** from a selected source layer. The smart layer is a
non-destructive instance that **mirrors the source's pixels** (read-only) while
carrying its own opacity, visibility and blend mode. Editing the source updates every
smart instance on the next recomposite; the smart layer has no independently editable
pixels.

## Everything is one undo step

Every layer operation surfaced by the panel — set opacity / visibility / lock / blend
mode, add / remove / duplicate / reorder, group / ungroup, attach / remove mask, set
reference / smart — is pushed as **exactly one** undo command. Undo restores the exact
prior state of the layer tree.

## Colour mode and indexed documents

The layer stack and blend modes apply to **RGBA** documents. **Indexed** documents are
single-layer by design — the compositor is RGBA-only.

- Converting a **multi-layer RGBA** document to indexed **flattens the composite into a
  single indexed layer** (per frame). This is undoable: undo restores the full
  multi-layer RGBA tree — groups, masks, opacity, blend modes, references and smart
  links — exactly.
- Converting back to RGBA turns the single indexed layer into one RGBA layer.

The document's colour mode is the single source of truth, so what the canvas shows,
what is saved to `.pixproj`, and the mode indicator always agree.

## Related topics

- Understand how the stack composites in [Blend modes](blend-modes.md).
- Each animation frame has its own layer stack — see the
  [animation timeline](animation-timeline.md).
