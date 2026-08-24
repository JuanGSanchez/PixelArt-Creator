# PixelArt Creator

*[Leer en español](README.es.md)*

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
- **AI assistant** — an in-app, **model-agnostic** chat dock that drives the editor in plain
  language over the same safe, `eval`-free automation layer. You supply any **OpenAI-compatible**
  or **Anthropic** provider (base URL, model and key); it is **credential-optional** and your key
  is stored in the **OS keyring**, never in the project file. Actions are tiered for safety —
  reversible edits apply automatically and stay undoable, while destructive actions ask for
  confirmation first.
- **In-app User Guide** — a complete, offline, searchable guide covering every functionality
  area, opened from **Help ▸ User Guide** or **F1**.

## Deploy / Install / Launch

### Requirements

- **Python 3.13 or newer** (`requires-python = ">=3.13"`) — that is the install floor.
  The project itself develops and tests against an exact pinned interpreter, **3.13.13**
  (`.python-version`), which is what CI and the deployment image run; a newer 3.13.x (or
  later) satisfies the floor for running the application.
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

Installing the package provides three console commands (declared in
`pyproject.toml` under `[project.scripts]`):

- **`pixelart-export`** — the headless export pipeline (PNG / GIF / sprite sheet / atlas,
  metadata and engine presets, batch export).
- **`pixelart-run`** — the headless automation runner (macros and DSL scripts), producing
  results identical to running the same automation in the GUI.
- **`pixelart-assistant`** — the headless AI assistant: runs the same model-agnostic
  assistant as the in-app dock over a project non-interactively, e.g.
  `pixelart-assistant --input in.pixproj --output out.pixproj --prompt "..."`
  (`--provider` / `--base-url` / `--model` select the provider; the API key is read from
  the **OS keyring**, never passed on the command line). It uses the same tiered safety —
  reversible edits apply automatically, while **destructive actions are declined unless you
  opt in with `--approve-destructive` (alias `--yes`)**.

Run any with `--help` to see its options:

```sh
pixelart-export --help
pixelart-run --help
pixelart-assistant --help
```

### Launching the desktop app

Launch the desktop editor with either canonical command:

```sh
# From a source checkout or any environment with the package installed
python -m pixelart_creator

# After `pip install .` — the installed GUI launch command
pixelart-creator
```

Both start the same application: the `Main_Window` Qt window
(`pixelart_creator.ui.main_window`), brought up by the launcher in
`pixelart_creator.ui.app` (which get-or-creates the `QApplication`, applies the theme
and font fallbacks, then runs the Qt event loop). `python -m pixelart_creator` is the
module entry point; `pixelart-creator` is the installed GUI console command (declared in
`pyproject.toml` under `[project.gui-scripts]`), available after `pip install .`.

The application runs on Windows, Linux and macOS wherever PySide6 (Qt 6) and Python 3.13+
are available.

### Native installers

For users without a Python environment, PixelArt Creator is also distributed as **native
installers** built by the CI build matrix (triggered on a build/tag run) and downloadable
from the build artifacts:

- **Windows** — an `.exe` installer with the required Qt plugins bundled; install and
  launch it like any desktop application.
- **Linux** — a self-contained, distro-agnostic **AppImage**; make it executable
  (`chmod +x`) and run it directly, with no system Python or distro package required.
- **macOS** — a `.app` wrapped in a `.dmg`. The current build is **unsigned**, so on first
  launch macOS Gatekeeper blocks it: **right-click the app ▸ Open** and confirm, or clear
  the quarantine flag with
  `xattr -dr com.apple.quarantine "/path/to/PixelArt Creator.app"`. Developer-ID signing
  and notarization are a planned, credential-gated step and are not required to run the app.

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

### Web companion viewer

A shared project can also be opened in a **browser** — on a phone or a desktop — through a
short-lived, **signed share link**. The viewer is **view + light interaction only** (layer
toggle, frame navigation, pan/zoom); it never edits the project. It is a vanilla
HTML/CSS/JS client (no build step, no new dependency) served by the same sync backend + Nginx
stack: the client loads from an Nginx `/viewer/` static location and connects back over the
existing WSS relay, presenting the signed token. The token is short-lived, view-scoped, and
verified-never-stored, so a link only ever grants a read-only window onto one project.

The client lives in `web_viewer/` and the production serving block in
`deploy/nginx-sync.conf`; the full operator recipe (share-link generation, serving, the
token/security posture, and the cross-browser pixel-fidelity check) is in the (private)
web-viewer guide.

## Documentation

- **In-app User Guide** — the primary user documentation, available offline from
  **Help ▸ User Guide** (or **F1**). It covers every functionality area with step-by-step
  workflows and is searchable from within the app.
- Project documentation (changelog, usage pages and design records) is maintained alongside
  the source and kept current as features ship.

## License

PixelArt Creator is released under the **Apache License 2.0**. See the [LICENSE](LICENSE)
and [NOTICE](NOTICE) files for the full terms.
