# =============================================================================
# pyside6-deploy spec — WINDOWS native distributable (Slice 13D, ADR-0038 §2)
# REQ-P13-BUILD-002 · SC-P13-BUILD-002-1 · owner AGT-09 (BUILD)
#
# Produces a self-contained, onefile .exe via pyside6-deploy (Nuitka backend),
# with the required Qt plugins bundled automatically by the Nuitka PySide6
# plugin. Run FROM THE REPO ROOT so the relative paths + the installed
# `pixelart_creator` package resolve:
#
#     pyside6-deploy -c packaging/pysidedeploy-windows.spec --force \
#                    --keep-deployment-files
#
# The build is reproducible from THIS committed config (every flag pinned here).
# pyside6-deploy may rewrite computed values back into a copy at build time; the
# committed file is the source of truth.
#
# PyInstaller fallback (ADR-0038 §1): if a Windows/plugin quirk blocks the
# Nuitka path, build with the Qt-provided hooks instead —
#     pyinstaller --noconfirm --onefile --windowed \
#       --name PixelArtCreator --collect-all PySide6 pixelart_creator/__main__.py
# =============================================================================

[app]
# Application title (drives the executable / bundle name).
title = PixelArtCreator
# Project root, relative to the CWD pyside6-deploy is invoked from (repo root).
project_dir = .
# The SHIPPED GUI entry point — `python -m pixelart_creator` boots the editor
# via pixelart_creator.ui.app:main (see pixelart_creator/__main__.py).
input_file = pixelart_creator/__main__.py
# Optional .pyproject file (not used — deps come from the installed package).
project_file =
# Where the produced executable is written.
exec_directory = dist
# Application icon (none shipped yet — Nuitka uses a default; TODO: add .ico).
icon =

[python]
# Use the CI-provided interpreter (Python 3.12 pinned by setup-python).
python_path =
# Pin the Nuitka backend for a reproducible build.
packages = Nuitka==2.5.1

[qt]
# QML is not used by this app.
qml_files =
excluded_qml_plugins =
# Qt plugins to bundle. The Nuitka PySide6 plugin auto-detects the platform
# (`windows`), style, image-format and icon-engine plugins; these are listed
# explicitly as defence-in-depth so the frozen app finds a platform plugin.
plugins = platforms,styles,imageformats,iconengines,platforminputcontexts

[nuitka]
# macOS-only permissions block (unused on Windows).
macos.permissions =
# onefile → a single distributable .exe.
mode = onefile
# --noinclude-qt-translations: we ship our own .qm (Article V) — skip Qt's.
# --nofollow-import-to: keep the non-desktop / dev-only packages OUT of the
# frozen app (defence-in-depth mirroring the pyproject wheel `exclude`;
# sync_backend/web_viewer are separate services, tests/scripts/docs are dev
# infra). The launcher only imports `pixelart_creator`, so these are belt-and-
# braces so nothing leaks in transitively.
extra_args = --quiet --assume-yes-for-downloads --noinclude-qt-translations
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
