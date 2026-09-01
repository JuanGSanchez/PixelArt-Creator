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
# Application icon: the committed Windows .ico (the derived icon family,
# pixelart_creator/icons/app/CONSTRUCTION-TABLE.md), assembled explicitly
# from unblurred nearest-neighbour members (16/24/32/48/64/128/256 px) with
# no size left to Pillow's own resize fallback.
icon = pixelart_creator/icons/app/pixelart-creator.ico

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
# --include-data-dir=SOURCE=DEST (B6 fix): ships our OWN compiled catalogues
# (pixelart_creator/i18n/*.qm), referenced in the comment above, into the
# frozen onefile payload at the same package-relative path
# pixelart_creator/ui/i18n.py's _default_translations_dir() resolves at
# runtime (sibling of pixelart_creator/ui/). Onefile mode extracts included
# data files under this same relative layout at run time, so static import
# analysis alone (which onefile/standalone both rely on for code) is not
# enough — non-Python data needs this explicit flag.
# --nofollow-import-to: keep the non-desktop / dev-only packages OUT of the
# frozen app (defence-in-depth mirroring the pyproject wheel `exclude`;
# sync_backend/web_viewer are separate services, tests/scripts/docs are dev
# infra). The launcher only imports `pixelart_creator`, so these are belt-and-
# braces so nothing leaks in transitively.
extra_args = --quiet --assume-yes-for-downloads --noinclude-qt-translations
    --include-data-dir=pixelart_creator/i18n=pixelart_creator/i18n
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
