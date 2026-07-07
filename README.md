# PixelArt Creator

**PixelArt Creator** is a cross-platform pixel-art creation platform built on Python and
PySide6 (Qt 6). It pairs a large, 8K-capable editable canvas with a non-destructive layer
model and a fast, region-scoped compositor, and grows outward into animation, tilemaps, a
byte-reproducible export pipeline, automation and scripting, non-destructive visual aids,
cloud storage and collaboration, and a studio-level team & asset-management layer — all
documented from inside the app by a comprehensive, offline User Guide.

Its architecture is a strict three-layer split: `ui/` (PySide6), `logic/` (pure Python, no
Qt), and `data/` (I/O, no Qt). Domain behaviour lives in the pure layers and is fully
unit-testable headless; Qt is confined to the UI layer.

## Key features

The platform has been built in phases; the capabilities below are **shipped**.

- **Canvas & drawing** — a large 8K-capable editable grid with zoom, pan, a pixel grid and
  snapping, nearest-neighbour rendering, and left-click paint / right-click contextual menu.
- **Colour** — a contextual right-click colour hub with a persisted favourites list, an RGB
  colour wheel, and live colour-theory harmonies (complementary, analogous, triadic,
  split-complementary, plus shade/tint ramps).
- **Layers** — a non-destructive layer system with groups, opacity, visibility, locks,
  masks, reference and smart layers, twelve blend modes, and RGBA/indexed colour modes.
- **Selection & transform** — rectangle / lasso / magic-wand selections and a floating
  move/copy preview with add/subtract gestures, commit and cancel.
- **Animation** — a frame timeline with per-frame duration, playback modes
  (loop / once / ping-pong / reverse), onion skinning, and named frame tags.
- **Tilemaps & level design** — slice an image into a tileset, paint a multi-layer infinite
  tilemap with stamp / erase / fill, resolve borders with Blob-47 auto-tiling, and
  import/export Tiled-compatible JSON.
- **Export pipeline** — export as PNG, animated GIF, sprite sheet or packed texture atlas
  with Aseprite-style JSON metadata and Unity / Godot engine presets; batch export; and a
  headless command-line exporter. Output is byte-reproducible for a fixed input.
- **Automation & scripting** — record and replay deterministic macros, run a sandboxed,
  data-driven command DSL (no `eval`/`exec`), extend the app with trusted, consent-gated
  plugins, batch-recolour many targets at once, generate content procedurally, and run any
  automation headlessly from the command line.
- **Visual aids** — a live real-size preview, guides & rulers with snapping, isometric and
  perspective grids, a PureRef-style reference board, multiple synced views of one document,
  and reproducible timelapse recording — all non-destructive.
- **Cloud & collaboration** — save/open projects through a provider-agnostic cloud
  interface with full version history, autosave and crash recovery; share a project with a
  member roster (owner / editor / viewer), threaded comments and presence; real-time
  co-editing with live cursors; and git-like art branching with conflict-free merge.
- **Team & asset management** — catalog sprites, animations, tilesets, tilemaps and palettes
  as named, tagged, searchable assets stored once by content (de-duplicated); a queryable
  dependency graph with a passive break indicator; an append-only per-asset version history;
  reference-not-copy reuse across projects; export/import of a project's referenced assets;
  and optional cloud backing of shared blobs.
- **In-app User Guide** — a complete, offline, searchable guide covering every functionality
  area, opened from **Help ▸ User Guide** or **F1**.

## Deploy / Install / Launch

### Requirements

- **Python 3.12 or newer** (`requires-python = ">=3.12"`).
- Runtime dependencies are declared in `pyproject.toml` and installed automatically:
  PySide6 (Qt 6), NumPy, Pillow, and the collaboration libraries `pycrdt` and `websockets`.

### Install

Install from a source checkout with pip:

```sh
pip install .
```

The distributed package name is **`pixelart-creator`**.

An optional extra enables live cloud-provider credential access:

```sh
pip install ".[cloud_live]"
```

The `cloud_live` extra adds OS-keyring support (`keyring`) used by the real Google Drive /
OneDrive / Dropbox provider adapters. It is **not** required for offline use, for the
in-memory/loopback collaboration paths, or for the rest of the platform — connect a real
provider only if you intend to use live cloud storage.

Developers can install the test/lint toolchain with the `dev` extra:

```sh
pip install ".[dev]"
```

### Command-line entry points

Installing the package provides two console commands (declared in
`pyproject.toml` under `[project.scripts]`):

- **`pixelart-export`** — the headless export pipeline (PNG / GIF / sprite sheet / atlas,
  metadata and engine presets, batch export).
- **`pixelart-run`** — the headless automation runner (macros and DSL scripts), producing
  results identical to running the same automation in the GUI.

Run either with `--help` to see its options:

```sh
pixelart-export --help
pixelart-run --help
```

### Launching the desktop app

The desktop editor is the `Main_Window` class in
`pixelart_creator.ui.main_window`. It is a Qt window and is shown from a running
`QApplication`:

```python
from PySide6.QtWidgets import QApplication
from pixelart_creator.ui.main_window import Main_Window

app = QApplication([])
window = Main_Window()
window.show()
app.exec()
```

The application runs on Windows, Linux and macOS wherever PySide6 (Qt 6) and Python 3.12+
are available.

### Hosting the real-time sync backend

Real-time collaboration works out of the box with **no hosting setup** — the sync backend
runs locally on the loopback interface by default. Hosting it elsewhere is **optional**, and
there is **no forced default**: the relay can run **locally/loopback** (the default), behind
the **cloud provider-adapter** path, or be **self-hosted on a VPS**. Adopting any option
requires **no change** to the app or the backend code.

For VPS self-hosting, the committed `deploy/` directory carries the artifacts to run the
(unchanged) `sync_backend/` relay on your own server, each with inline setup instructions:

- **`deploy/Dockerfile`** — a slim, Qt-free container image
  (`docker build -f deploy/Dockerfile`; run with `--ulimit nofile=65535:65535 -p 8765:8765`).
- **`deploy/pixelart-sync.service`** — a systemd unit (`LimitNOFILE=65535`).
- **`deploy/nginx-sync.conf`** — an Nginx reverse proxy that terminates TLS and proxies
  WSS → WS (with WebSocket-friendly timeouts).

The launcher `deploy/run_sync_backend.py` binds via `PIXELART_SYNC_HOST` (default `0.0.0.0`)
and `PIXELART_SYNC_PORT` (default `8765`). See the deployment guide for the full recipe,
the connection-ceiling notes, and the localhost-provable acceptance run.

## Documentation

- **In-app User Guide** — the primary user documentation, available offline from
  **Help ▸ User Guide** (or **F1**). It covers every functionality area with step-by-step
  workflows and is searchable from within the app.
- Project documentation (changelog, usage pages and design records) is maintained alongside
  the source and kept current as features ship.

## License

PixelArt Creator is released under the **Apache License 2.0**. See the [LICENSE](LICENSE)
and [NOTICE](NOTICE) files for the full terms.
