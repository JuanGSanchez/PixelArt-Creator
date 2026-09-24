# Showcase media generator

`generate_showcase.py` is the ONE script that produces every showcase-media
file under `docs/images/` — example art, real-application screenshots, and
the GitHub social preview — exclusively through this product's own code
paths (`Document`/`Layer`/`PixelBuffer` from `pixelart_creator.logic`, the
`pixelart-run` / `pixelart-export` entry points invoked in-process, and
`pixelart_creator.ui.app.create_app` for screenshots). It never re-implements
product logic and never uses a third-party encoder.

Four sub-commands: `art`, `screenshots`, `social`, `check`. Every path is a
CLI argument; none is hard-coded. Every argument has a default resolved
relative to this file's own location (`Path(__file__).resolve().parents[2]`
is the repo root), so the commands below work unmodified from a checkout at
any path, on any drive, on any OS.

## Regenerate everything

Run from anywhere (paths are resolved from the script's own location, not
the current working directory):

```
python scripts/showcase/generate_showcase.py art
python scripts/showcase/generate_showcase.py social --tagline "Open-source pixel-art studio"
python scripts/showcase/generate_showcase.py screenshots
python scripts/showcase/generate_showcase.py check --readme-budget-png-bytes 1000000 --readme-budget-gif-bytes 5000000
```

Defaults used by the commands above: `--product-root` the repo root this
script lives under; `--review-dir` `docs/images`; `--out-dir` the matching
`docs/images/art` / `docs/images/screenshots` / `docs/images/social`;
`--tmp-dir` `dev-docs/showcase-tmp` (already `.gitignore`d, layer (b) — never
committed, never a path outside this product repository); `screenshots`'
`--scene-project` / `--sprite-project` / `--tilemap-project` default to the
native `.pixproj` files `art` just wrote under `docs/images/art`. Every
default is a plain, overridable CLI argument — pass any of the flags above
explicitly to point at a different location. `--tagline` has no default: the
tagline is always the user's pick (never generate one and ship it
un-reviewed).

Run the four commands in this order — `art` first (the social preview and
the screenshots both read the art it produces), `check` last.

## What gets published vs. what stays intermediate

`art` and `social` also write the NATIVE `.pixproj` project sources
alongside the final exported media in the same `--out-dir` (this is what lets
`screenshots` open a real document, and what lets `social` composite from the
pieces' own pre-upscale pixels) — by design, identical to the approved
review-round behaviour. The PUBLISHED `docs/images/` tree does not keep
those `.pixproj` files:

- `check`'s X.3 re-derivation already proves origin — it rebuilds every
  piece from this generator + the recorded product commit and compares
  DECODED PIXELS against the shipped PNG/GIF — without needing the project
  file shipped alongside it.
- The README only ever embeds the final PNG/GIF; a `.pixproj` project file
  adds binary weight to a public presentation folder with no README use.
- Anyone who wants to re-open a piece as a real project regenerates it with
  `art` above — reproducible, not lost.

After a regeneration, remove the project files and refresh
`provenance.json` / `PROVENANCE.md` so the shipped record describes exactly
what is shipped (never a stale row pointing at a file that isn't there):

```
python - <<'PY'
import json
from pathlib import Path

root = Path("docs/images")
for p in sorted(root.rglob("*.pixproj")):
    p.unlink()

prov_path = root / "provenance.json"
entries = json.loads(prov_path.read_text(encoding="utf-8"))
kept = [e for e in entries if not e["output"].endswith(".pixproj")]
prov_path.write_text(json.dumps(kept, indent=2, sort_keys=True), encoding="utf-8")

lines = ["# PROVENANCE", "", "Generator-written. One entry per output file.", ""]
for entry in sorted(kept, key=lambda x: x["output"]):
    lines.append(f"## {entry['output']}")
    for key in sorted(entry):
        if key != "output":
            lines.append(f"- {key}: {entry[key]}")
    lines.append("")
(root / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")
PY
```

Then re-run `check` a SECOND time, against the now-published (project-file-
free) tree, so the `check-results.json` committed alongside the media
describes the tree actually delivered (X.3 does not depend on the shipped
project files being present, so both runs pass identically):

```
python scripts/showcase/generate_showcase.py check --readme-budget-png-bytes 1000000 --readme-budget-gif-bytes 5000000
```

## Screenshots: platform disclosure

`screenshots` attempts native capture first (`QWidget.grab()`, the real
window) and runs the C4 known-colour control before trusting it; on control
failure it falls back to `QT_QPA_PLATFORM=offscreen` and controls again. As
of this revision, native capture fails the control on every host tried — a
diagnosed product defect (Qt's GL paint engine caches a texture on `QImage`
identity, and the canvas's live-mutated `QImage` never receives a fresh one)
— so every shipped screenshot is `offscreen`, disclosed per file in
`provenance.json`'s `qt_platform` field and in
`docs/images/screenshots/capture-control.json`. This is never routed around
by patching product state (HARD RULES).

## Sub-commands

- `art` — builds the four example pieces (an outlined/shaded character with
  an idle + 8-frame walk cycle; a layered scene; a Blob-47 auto-tiled
  tilemap; a curated `pixelart-run` procgen contact sheet) via the product's
  own Python API, `pixelart-run` and `pixelart-export`.
- `social` — composes the 1280x640 GitHub social preview: the app-icon pixel
  master (`pixelart_creator/icons/app/logo-source-64.png`, read-only, never
  edited) upscaled with `scale_nearest`, the example art collaged in, and
  `--tagline` drawn with an in-platform `set_pixel` font (no Qt/Pillow text
  rendering, no font-licence question).
- `screenshots` — captures real application windows (native-first, offscreen
  fallback, per above), with the UI language forced to English and the
  application font forced to the real Windows UI font before any capture, so
  every shot is deterministic regardless of the host's system locale.
- `check` — runs every X.1–X.8 check (THE CHECK CONTRACT) and prints
  `<check>: examined=<n> failed=<m>` for each; exits non-zero if any check
  failed or examined zero items. Writes `check-results.json` next to
  `provenance.json`.

## Provenance

One C2 entry per shipped output lives in `docs/images/provenance.json` /
`docs/images/PROVENANCE.md` — the exact command, the generator's own SHA-256,
the product commit and dirty flag, every tool version, and the output's own
SHA-256, all generator-written, never hand-edited.
