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
# Nuitka is named here, NOT versioned: pyside6-deploy's python_helper.py
# (install_dependencies) strips any `==<version>` from a Nuitka entry unless
# `--nuitka-version` is passed on the command line, and then installs the name
# only if Nuitka is absent -- so a version written here is never honoured and
# only misleads. The pin that counts is the `NUITKA_PIN` env value in
# .github/workflows/build-installers.yml (REQ-VI-BUILD-006), installed and then
# checked before and after the build; Nuitka 4.3 builds an app that crashes
# at launch.
packages = Nuitka

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
# --include-data-dir=SOURCE=DEST (B6 fix, extended): ships every runtime
# package-data directory the frozen app reads through
# importlib.resources.files("pixelart_creator") — enumerated by walking every
# such call site (ui/tool_icons.py, ui/app_icon.py, data/guide_content.py):
#   - pixelart_creator/i18n            (*.qm) -- ui/i18n.py
#   - pixelart_creator/icons           (tools/*.svg + app/*) -- ui/tool_icons.py,
#     ui/app_icon.py. Its ABSENCE is the measured root cause of the v0.3.0
#     macOS smoke-launch crash (ToolGlyphError: missing tool glyph asset for:
#     pencil, run 35941799524) -- only i18n was ever included.
#   - pixelart_creator/fonts           (NifenArt-*.ttf, OFL.txt, FONTLOG.txt)
#     -- the bundled Nifen Art typeface (ADR-0071). Without it the frozen app
#     falls back to the platform font: the same missing-directory failure
#     class as the v0.3.0 icons crash above.
#   - pixelart_creator/themes          (index.json, contrast-pairs.json and one
#     folder per style: roles, templates, grids) -- the style catalogue the
#     appearance settings read (ADR-0070). Same failure class if absent.
#   - pixelart_creator/userguide_content (manifest.json + content/*.md) --
#     data/guide_content.py (in-app User Guide, ADR-0029)
# into the frozen onefile payload at the same package-relative paths those
# modules resolve at runtime (siblings of pixelart_creator/ui/). Onefile mode
# extracts included data files under this same relative layout at run time,
# so static import analysis alone (which onefile/standalone both rely on for
# code) is not enough — non-Python data needs this explicit flag, for EVERY
# directory a runtime resource lookup can reach, not just i18n.
# --include-package-data=PySide6:translations/qtbase_<code>.qm (ADR-0067
# Part 4; REQ-AV-UI-012): ships Qt's OWN base catalogue so
# ui/i18n.py's QLibraryInfo.path(TranslationsPath) lookup (LanguageManager.
# _apply_qt_base_catalogue) finds it in the frozen build. Nuitka's own
# `nuitka.plugins.standard.PySidePyQtPlugin` ships a `--noinclude-qt-
# translations` flag, but reading its installed source (4.2.2, the
# version the workflow pins) shows that flag --
# and the translations copy it gates -- is wired
# ONLY through `considerDataFiles()`'s `isQtWebEngineModule()` branch, i.e.
# it only ever bundles Qt's catalogues for a QtWebEngine dependency; its own
# `--help` text says so verbatim ("Include Qt translations with QtWebEngine
# if used."). This app never imports QtWebEngine, so on every platform the
# plugin's copy step is skipped regardless of that flag's value -- removing
# it is necessary but NOT sufficient, which is why this explicit
# `--include-package-data` line does the actual work. `--include-package-
# data` resolves its SOURCE relative to the INSTALLED PySide6 package (not a
# repo path), so it is portable across CI runners. Only `qtbase_es` is listed
# because pixelart_creator/i18n/ currently ships only `pixelart_es.qm`
# (English is the source language and needs no Qt catalogue either); ADD the
# matching `qtbase_<code>.qm` entry here whenever a new UI language ships.
# --nofollow-import-to: keep the non-desktop / dev-only packages OUT of the
# frozen app (defence-in-depth mirroring the pyproject wheel `exclude`;
# sync_backend/web_viewer are separate services, tests/scripts/docs are dev
# infra). The launcher only imports `pixelart_creator`, so these are belt-and-
# braces so nothing leaks in transitively.
extra_args = --quiet --assume-yes-for-downloads
    --include-data-dir=pixelart_creator/fonts=pixelart_creator/fonts
    --include-data-dir=pixelart_creator/i18n=pixelart_creator/i18n
    --include-data-dir=pixelart_creator/icons=pixelart_creator/icons
    --include-data-dir=pixelart_creator/themes=pixelart_creator/themes
    --include-data-dir=pixelart_creator/userguide_content=pixelart_creator/userguide_content
    --include-package-data=PySide6:translations/qtbase_es.qm
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
