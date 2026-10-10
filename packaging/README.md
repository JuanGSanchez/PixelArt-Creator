# `packaging/` — native-installer build config (ADR-0038)

Committed, reproducible packaging configuration for the Phase-13
**native installers** (Windows / macOS / Linux). This directory is **`BUILD`
ops config** (Article X §1) — it is **not** part of the shipped
`pixelart_creator` package and is **not** scanned by `check_layering`. It
changes **no** product code.

The actual build runs in the CI **build matrix** in its own workflow file,
`.github/workflows/build-installers.yml` (split out of `ci.yml`), on a **build/tag**
trigger (`workflow_dispatch` or a `v*` tag) — never on a normal branch/PR push, so PR CI
is not slowed.

## Files

| File | Role |
| --- | --- |
| `pysidedeploy-windows.spec` | `pyside6-deploy` spec → onefile `.exe`. |
| `pysidedeploy-linux.spec` | `pyside6-deploy` spec → Nuitka standalone folder (→ AppImage). |
| `pysidedeploy-macos.spec` | `pyside6-deploy` spec → standalone `.app` bundle (→ ad-hoc-signed `.dmg`). |
| `build_appimage.sh` | Wraps the Linux standalone folder into a self-contained `.AppImage` via `appimagetool`. |

## Tooling — `pyside6-deploy` primary, PyInstaller fallback (ADR-0038 §1)

Primary: **`pyside6-deploy`** (the Qt-recommended Nuitka wrapper), which bundles
the required Qt plugins (platform / style / image-format / icon-engine)
automatically. It ships inside the `PySide6` wheel; the Nuitka backend is pinned
in each spec's `[python] packages`.

Each spec documents its **PyInstaller fallback** command (in the header
comment) for the case a target/plugin quirk blocks the Nuitka path — build with
the Qt-provided hooks and `--collect-all PySide6`.

## App entry point (READ THIS)

Every spec's `input_file` points at the **shipped** GUI entry point
`pixelart_creator/__main__.py` (owned by the UI and application-logic teams), which calls
`pixelart_creator.ui.app:main` — the same launcher that
`python -m pixelart_creator` and the `pixelart-creator` `gui-script` (see
`pyproject.toml [project.gui-scripts]`) invoke. There is **no** BUILD-only
launcher shim any more; the earlier `packaging/app_entry.py` stopgap was
superseded by this shipped entry and removed. Because Nuitka standalone names
the dist folder + frozen binary after the input-file **stem**, the Linux
standalone folder is `dist/__main__.dist/` and its binary is `__main__` (see
`build_appimage.sh`).

## What ships / what is excluded

Only `pixelart_creator*` is frozen into the distributable. `sync_backend`,
`web_viewer`, `tests`, `scripts`, `docs` are excluded — defence-in-depth
mirroring the `pyproject.toml` wheel `exclude` list (ADR-0027 / ADR-0035): the
launcher imports only `pixelart_creator`, and each spec additionally passes
`--nofollow-import-to=` for those packages so nothing leaks in transitively.

## Application icon (derived family)

The three specs' `[app] icon` fields, plus `build_appimage.sh`'s AppDir icon,
all consume the raster family derived by `scripts/derive_app_icons.py` from the five committed,
hand-drawn **Kikko Badge** masters
`pixelart_creator/icons/app/logo-master-{16,24,32,48,64}.png` (see that directory's
`CONSTRUCTION-TABLE.md` for the full per-size construction record — master used, integer
scale factor, opaque box, fill). Each shipped size up to 64 px has its own master, drawn
for that size; the larger sizes are whole-number nearest-neighbour upscales of the 64 px
master. The badge is its own plate, so nothing is cropped or padded. Every member is an
INTEGER nearest-neighbour derivation: never redrawn, never resampled. The single 64 px
master the family used to be derived from is gone.

| Consumer | File |
| --- | --- |
| `pysidedeploy-windows.spec` `[app] icon` | `pixelart_creator/icons/app/pixelart-creator.ico` |
| `pysidedeploy-linux.spec` `[app] icon` | `pixelart_creator/icons/app/pixelart-creator.png` |
| `pysidedeploy-macos.spec` `[app] icon` | `pixelart_creator/icons/app/pixelart-creator.icns` |
| `build_appimage.sh` AppDir icon (`Icon=pixelart-creator` in the generated `.desktop` entry) | `pixelart_creator/icons/app/pixelart-creator.png`, copied verbatim into the AppDir — no placeholder is synthesised at build time any more |

The runtime app/window icon (`QApplication` / `Main_Window`,
`pixelart_creator/ui/app_icon.py`) is a **separate loader** that reads the
same family's `app-icon-{16,24,32,48,64,128,256,512}.png` members through
`importlib.resources` at process start — it does not touch this directory's
files at all. The five `logo-master-*.png` files (provenance masters, read only by the
deriver; ADR-0068: not wheel package data) and `app-icon-1024.png` (an
ICNS-container-only member, never a Nuitka/AppImage input) are consumed by neither the
runtime loader nor anything in this directory. The installer specs include the whole
`pixelart_creator/icons` directory, so the masters do travel inside an installer; the wheel
does not carry them.

The deriver also writes the web viewer's page icon, `web_viewer/static/favicon.png` (the
32 px master at k = 1), and `--check` verifies it with the rest of the family. Each
master's sha256 is pinned in the deriver; a retouched master fails `--check` until the pin
is updated on purpose.

Regenerate the whole family from the committed master:

    python scripts/derive_app_icons.py

Verify the committed bytes still match what the deriver would produce — run
this before packaging a release, exactly as CI does:

    python scripts/derive_app_icons.py --check

## Fonts and themes (package data and installer data)

Two more runtime directories ship, both **data, not packages** (no `__init__.py`; ADR-0068),
read through `importlib.resources` — so a missing one is invisible from a source checkout and
fails only for an installed user, exactly as the missing `icons/` directory did in v0.3.0.

| Directory | Contents | Wheel (`pyproject.toml` package-data) | Installers (`--include-data-dir` in all three specs) |
| --- | --- | --- | --- |
| `pixelart_creator/fonts/` | `NifenArt-Regular.ttf`, `NifenArt-Bold.ttf`, `OFL.txt`, `FONTLOG.txt` | the four files, by name | the whole directory |
| `pixelart_creator/themes/` | `index.json`, `contrast-pairs.json`, and per style `roles.json`, `templates.json`, `pattern.grid.txt`, `templates/*.grid.txt` | one glob per depth (`themes/*.json`, `themes/*/*.json`, `themes/*/*.grid.txt`, `themes/*/templates/*.grid.txt`) | the whole directory |

Not shipped, by design: the font sources in `fonts-src/` and the build scripts in
`scripts/font/` (a directory placed inside an included one would ship in every installer, which
is why the sources sit outside the package). **fontTools** builds the fonts and is a
build-time development dependency only: it is in the `dev` extra and pinned in
`constraints.txt`, never in the runtime `dependencies`, and nothing the application imports
touches it. The built fonts are committed.

**Adding a style or a font file is a packaging change.** A new file at a depth the globs above
do not name needs a new glob; a new top-level data directory needs a package-data entry and an
`--include-data-dir` line in each of the three specs. Prove it the way the icon entries were
proven: build the wheel and list it (`python -m build --wheel`, then list the archive and
compare against `git ls-files pixelart_creator/fonts pixelart_creator/themes`).

## macOS signing (credential-gated, NON-blocking — ADR-0038 §4, Article XI)

The macOS leg ships an **unsigned / ad-hoc-signed** `.app`/`.dmg` now. A
Developer-ID **signing → notarization (`notarytool`) → stapling** step runs in
CI **only** when an Apple Developer ID secret is present (guarded by
`if: env.APPLE_DEVELOPER_ID != ''`). Its absence does **not** fail the build.
**No credential is committed** — signing consumes GitHub secrets at CI time
only.

### Gatekeeper bypass for the unsigned build

Until a Developer ID is supplied, a user opening the unsigned `.app` must
bypass Gatekeeper once: right-click the app → **Open** → confirm, or run
`xattr -dr com.apple.quarantine /path/to/PixelArt\ Creator.app`. Full per-OS
install/run docs are the documentation team's responsibility.

## Reproducibility

Every packaging numeric/flag lives in these committed files (Nuitka pin, mode,
plugin list, exclusion flags). `pyside6-deploy -c <spec>` may rewrite computed
values into a working copy at build time; the committed spec is the source of
truth. Invoke every command **from the repo root**.

## Spec files — purpose + key settings (moved out of the spec headers)

`pyside6-deploy` parses each spec with Python's `configparser`, which raises
`MissingSectionHeaderError` on any content **before** the first `[section]`
header. The per-spec documentation banner that previously led each `.spec` file
therefore lived before `[app]` and broke the parse — it has been moved here so
each spec now starts directly with `[app]`. (Full-line `#` comments *after* the
first section header are tolerated by `configparser` and are retained inside the
Windows spec's sections as per-key notes.) The documented content:

### `pysidedeploy-windows.spec` — Windows onefile `.exe` (REQ-P13-BUILD-002 · SC-P13-BUILD-002-1)

Produces a self-contained, **onefile** `.exe` via `pyside6-deploy` (Nuitka
backend), with the required Qt plugins bundled automatically by the Nuitka
PySide6 plugin. Run **from the repo root** so the relative paths + the installed
`pixelart_creator` package resolve:

    pyside6-deploy -c packaging/pysidedeploy-windows.spec --force \
                   --keep-deployment-files

The build is reproducible from the committed config (every flag pinned).
`pyside6-deploy` may rewrite computed values back into a copy at build time; the
committed file is the source of truth. **PyInstaller fallback** (ADR-0038 §1) if
a Windows/plugin quirk blocks the Nuitka path:

    pyinstaller --noconfirm --onefile --windowed \
      --name PixelArtCreator --collect-all PySide6 pixelart_creator/__main__.py

### `pysidedeploy-linux.spec` — Linux Nuitka standalone folder → AppImage (REQ-P13-BUILD-004 · SC-P13-BUILD-004-1)

Produces a Nuitka **standalone** dist folder (`dist/__main__.dist/`, named after
the input-file stem `__main__`) with the Qt plugins bundled;
`packaging/build_appimage.sh` then wraps that folder into a self-contained,
distro-agnostic `.AppImage` (the BUILD-004 target). Standalone (folder) mode is
used rather than onefile because AppImage is built from an AppDir tree; the
folder maps straight into `usr/bin/` of the AppDir. Run **from the repo root**:

    pyside6-deploy -c packaging/pysidedeploy-linux.spec --force \
                   --keep-deployment-files
    bash packaging/build_appimage.sh

The Linux platform plugin is `xcb` (+ offscreen for the CI smoke); the Nuitka
PySide6 plugin bundles it, listed explicitly as defence-in-depth.
**PyInstaller fallback** (ADR-0038 §1):

    pyinstaller --noconfirm --onedir --name PixelArtCreator \
      --collect-all PySide6 pixelart_creator/__main__.py   # then wrap in AppImage

### `pysidedeploy-macos.spec` — macOS standalone `.app` → `.dmg` (REQ-P13-BUILD-003 · SC-P13-BUILD-003-1)

Produces a Nuitka **standalone** `.app` bundle (`Contents/MacOS` + bundled Qt
plugins); the CI leg ad-hoc-signs it (`codesign --sign -`), smoke-launches it
offscreen, and wraps it in a `.dmg` via `hdiutil`. Developer-ID signing →
notarization (`notarytool`) → stapling is a **separate, credential-gated,
non-blocking** CI step (ADR-0038 §4, Article XI) that runs **only** when an Apple
Developer ID secret is supplied — its absence ships the unsigned / ad-hoc
artifact and does **not** fail the phase. **No credential is committed** here or
anywhere; signing consumes GitHub secrets at CI time only. The macOS platform
plugin is `cocoa` (+ offscreen for the CI smoke). Run **from the repo root**:

    pyside6-deploy -c packaging/pysidedeploy-macos.spec --force \
                   --keep-deployment-files

**PyInstaller fallback** (ADR-0038 §1):

    pyinstaller --noconfirm --windowed --name PixelArtCreator \
      --collect-all PySide6 pixelart_creator/__main__.py    # produces a .app

### Shared settings (all three specs)

- `[app] input_file = pixelart_creator/__main__.py` — the shipped GUI entry point.
- `[python] packages = Nuitka==2.5.1` — pinned Nuitka backend for reproducibility.
- `[qt] plugins = platforms,styles,imageformats,iconengines,platforminputcontexts` — bundled Qt plugins.
- `[nuitka] extra_args` includes `--include-data-dir` lines for `i18n`, `fonts`, `icons`, `themes` and `userguide_content` (every runtime data directory; see "Fonts and themes" above), `--include-package-data=PySide6:translations/qtbase_es.qm` (ADR-0067 Part 4) so Qt's own base catalogue ships alongside the app's own `.qm` (Article V) — Nuitka's PySide plugin only auto-bundles Qt's translations for a QtWebEngine dependency, which this app does not have, so the file must be listed explicitly; see the spec header comments for the full reasoning — and `--nofollow-import-to=` for `sync_backend`, `web_viewer`, `tests`, `scripts`, `docs`, `pytest`, `hypothesis` (defence-in-depth mirroring the pyproject wheel `exclude`).
