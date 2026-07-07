# `packaging/` — native-installer build config (Slice 13D, ADR-0038)

Committed, reproducible packaging configuration for the Phase-13 Slice 13D
**native installers** (Windows / macOS / Linux). This directory is **`BUILD`
ops config** (Article X §1) — it is **not** part of the shipped
`pixelart_creator` package and is **not** scanned by `check_layering`. It
changes **no** product code.

The actual build runs in the CI **build matrix** in
`.github/workflows/ci.yml` (`build-installers` job), on a **build/tag** trigger
(`workflow_dispatch` or a `v*` tag) — never on a normal branch/PR push, so PR CI
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
`pixelart_creator/__main__.py` (owned by AGT-05/AGT-03), which calls
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
install/run docs are AGT-08's `T13D-06`.

## Reproducibility

Every packaging numeric/flag lives in these committed files (Nuitka pin, mode,
plugin list, exclusion flags). `pyside6-deploy -c <spec>` may rewrite computed
values into a working copy at build time; the committed spec is the source of
truth. Invoke every command **from the repo root**.
