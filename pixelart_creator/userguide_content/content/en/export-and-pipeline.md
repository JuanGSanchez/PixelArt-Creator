# Export & pipeline integration

The **export system** turns a project into the assets a game pipeline consumes: a single
**PNG**, an **animated GIF**, a **sprite sheet** or a packed **texture atlas**, each with
optional **Aseprite-style JSON** metadata and ready-to-drop **engine presets** for
**Unity** and **Godot**. You can export one target from the export dialog, queue several
with the batch panel, or run the whole thing headlessly from the `pixelart-export`
command line — and every path produces the **same bytes**. Open the export dialog from
the Export menu or with **Ctrl+Shift+E**.

> **Byte-reproducible export.** Export is **deterministic**: for a fixed input document
> and the same parameters the output bytes are identical every time — frames are
> iterated in explicit order, the GIF uses a fixed shared palette with dithering off, and
> the encoders are pinned. The GUI and the CLI drive the **same** engine, so a GUI export
> and a CLI export of the same document are **byte-identical**. The guarantee is
> *same-environment* (a pinned toolchain), not guaranteed across different machines.

## Raster export (PNG / GIF)

- **PNG** exports **frame 0** as a single RGBA image — the still-image target.
- **GIF** exports the animation: every frame in order, each shown for its own
  **per-frame duration** (the durations set on the [animation timeline](animation-timeline.md)),
  with the loop count, frame disposal and transparency written into the file. All frames
  share **one fixed palette** (a median-cut reduction over the animation) and dithering
  is **off**, which is what keeps the GIF byte-reproducible.

> **GIF loop count.** The `--loop` flag (CLI) / loop field (dialog) sets how many times
> the GIF repeats; **`0` means loop forever**.

## Sprite sheets and texture atlases

- A **sprite sheet** lays every frame out on a **uniform grid**, row-major — frame `k`
  sits at column `k % columns`, row `k // columns`, with configurable inter-sprite
  **padding** and no outer margin. Set the column count to control the sheet's shape.
- A **texture atlas** packs the frames tightly with the shared **MaxRects** packer
  (rotation is off, so sprites are always axis-aligned). The atlas is the space-efficient
  option when frames vary in content.

> **Atlas size ceiling.** The atlas is bounded to the platform **8K** dimension ceiling.
> If a sprite set cannot fit within that ceiling the export **fails cleanly** with a clear
> atlas error (never a silent overlap, truncation or crash) — reduce the padding, the
> frame size or the frame count and retry.

## JSON metadata

Sprite-sheet and atlas exports can emit a **JSON metadata sidecar** in the **Aseprite
*Array*** format: a `frames[]` array (each frame's rect, source size and duration) plus a
`meta{}` block carrying the frame **tags** and per-frame durations. The JSON is
**deterministic** — keys are sorted, separators are fixed, and coordinates are integers —
so it round-trips and diffs cleanly. Toggle it with the JSON option in the dialog, or
`--json` / `--no-json` on the CLI (on by default).

## Engine presets (Unity / Godot)

Alongside the image + JSON, export can write an **engine-ready preset** so the asset drops
straight into a project:

| Preset | What it writes |
| --- | --- |
| **Unity** | A sprite `.meta` sidecar — sprite mode **Multiple**, `pixelsPerUnit`, pivot, and `filterMode = Point` (crisp pixels, no bilinear smoothing). |
| **Godot** | A `SpriteFrames` `.tres` resource (Godot 4.2) built from the exported frames. |

Choose the preset in the dialog, or pass `--preset unity` / `--preset godot` on the CLI
(`--preset none` — the default — writes no preset). The preset files are built
deterministically from the same layout metadata as the image.

## Batch export

The **batch export panel** queues **several targets at once** — for example a PNG, a GIF
and a Unity atlas from one project in a single run. Batch export is
**continue-on-failure**: if one target fails (say an atlas that will not fit), the
remaining targets still export and the failure is reported for that target alone, so one
bad target never aborts the batch.

## Registering an exported artifact in the library

The export dialog carries a checkbox, **Also add to the asset library**, that registers
the exported artifact into the [asset library](asset-library.md) in the same step as
exporting it — an opt-in, not a default. Ticking it opens the shared **Register Asset**
prompt (name, kind, tags) after a successful export; leaving it unticked exports without
touching the library at all, exactly as before this option existed.

## Responsiveness

All export work runs **off the GUI thread** on a background worker, behind a **progress
indicator you can cancel** — so exporting a large animation or atlas never freezes the
window. Export is **read-only** on your document: it never mutates it and pushes no undo
step.

> **Cancelling a large single target.** Cancel takes effect between targets promptly;
> cancelling **mid-encode of a single large target** is coarser — the in-flight encode
> finishes before the cancel is observed.

## The `pixelart-export` command line

For automation and CI, `pixelart-export` runs the **exact same** export path headlessly
(no GUI) — its output is byte-identical to the GUI export of the same document and
parameters. It loads the `.pixproj` through the same defensive, validated project loader
the app uses.

```
pixelart-export --input PROJECT.pixproj --format FORMAT --output OUT [options]
```

| Flag | Meaning |
| --- | --- |
| `--input PATH` | **(required)** the source `.pixproj` project to export. |
| `--format FORMAT` | **(required)** one of `png`, `gif`, `sprite-sheet`, `atlas`. |
| `--output PATH` | **(required)** the output image path. |
| `--preset PRESET` | engine preset: `none` (default), `unity`, `godot`. |
| `--columns N` | sprite-sheet column count. |
| `--padding N` | inter-sprite padding, in pixels. |
| `--loop N` | GIF loop count (`0` = loop forever). |
| `--tag NAME` | export only a named frame tag's range (default: the whole document). |
| `--json` / `--no-json` | emit the sprite-sheet/atlas JSON sidecar (default: on). |

**Exit codes:** `0` success; `1` an export / packing / write error (for example an atlas
that will not fit, or a filesystem write failure); `2` bad arguments or a malformed /
unreadable input project.

> **Same path as the GUI.** Because the CLI and the dialog call the same engine, you can
> prototype an export interactively and then reproduce it exactly in a build script by
> passing the same parameters as flags.

## What is not covered

- **APNG** (animated PNG) — **deferred**; this release exports still PNG (frame 0) and
  animated GIF.
- **Cross-machine byte-identical** output — the byte-reproducibility guarantee is
  *same-environment* (a pinned toolchain); a different machine's toolchain may produce
  different bytes.
- **Fine-grained mid-encode cancellation** of a single large target — cancel is observed
  between targets, not partway through one target's encode.

## Related topics

- Automate exports as part of a scripted pipeline in
  [Automation & scripting](automation-and-scripting.md).
