[app]
title = PixelArtCreator
project_dir = .
input_file = pixelart_creator/__main__.py
project_file =
exec_directory = dist
# Application icon: the committed macOS .icns (the derived icon family,
# pixelart_creator/icons/app/CONSTRUCTION-TABLE.md), assembled explicitly
# from unblurred nearest-neighbour members (32/64/128/256/512/1024 px)
# rather than delegated to Pillow's own single-input ICNS resize.
icon = pixelart_creator/icons/app/pixelart-creator.icns

[python]
python_path =
packages = Nuitka==2.5.1

[qt]
qml_files =
excluded_qml_plugins =
# On macOS the platform plugin is `cocoa` (+ offscreen for the CI smoke); the
# Nuitka PySide6 plugin bundles it. Listed explicitly as defence-in-depth.
plugins = platforms,styles,imageformats,iconengines,platforminputcontexts

[nuitka]
# No special TCC/entitlement permissions requested by this app.
macos.permissions =
# standalone + an .app bundle. Ad-hoc/Developer-ID signing is applied by the CI
# leg AFTER the build (kept out of the spec so the credential-gated path is a
# single, auditable, non-blocking CI step).
mode = standalone
# --include-data-dir=SOURCE=DEST (B6 fix, extended): ships every runtime
# package-data directory the frozen app reads through
# importlib.resources.files("pixelart_creator") — enumerated by walking every
# such call site (ui/tool_icons.py, ui/app_icon.py, data/guide_content.py):
#   - pixelart_creator/i18n            (*.qm) -- ui/i18n.py
#   - pixelart_creator/icons           (tools/*.svg + app/*) -- ui/tool_icons.py,
#     ui/app_icon.py. Its ABSENCE is the measured root cause of the v0.3.0
#     macOS smoke-launch crash (ToolGlyphError: missing tool glyph asset for:
#     pencil, run 35941799524) -- only i18n was ever included.
#   - pixelart_creator/userguide_content (manifest.json + content/*.md) --
#     data/guide_content.py (in-app User Guide, ADR-0029)
# into the frozen dist tree at the same package-relative paths those modules
# resolve at runtime (siblings of pixelart_creator/ui/). Nuitka standalone
# mode does not bundle package data by static import analysis alone, so this
# is required for EVERY directory a runtime resource lookup can reach, not
# just i18n.
# --include-package-data=PySide6:translations/qtbase_<code>.qm (ADR-0067
# Part 4; REQ-AV-UI-012): ships Qt's OWN base catalogue so
# ui/i18n.py's QLibraryInfo.path(TranslationsPath) lookup (LanguageManager.
# _apply_qt_base_catalogue) finds it in the frozen build -- this is what
# makes the Cocoa application-menu "About %1" text (ADR-0067 Part 4) and
# every standard QDialogButtonBox button translate. A `--noinclude-qt-
# translations` flag used to sit here, but reading Nuitka's installed
# `nuitka.plugins.standard.PySidePyQtPlugin` source (the exact version
# measured directly) shows that flag -- and the
# translations copy it gates -- is wired ONLY through `considerDataFiles()`'s
# `isQtWebEngineModule()` branch: it only ever bundles Qt's catalogues for a
# QtWebEngine dependency (its own `--help` text: "Include Qt translations
# with QtWebEngine if used."). This app never imports QtWebEngine, so the
# plugin's copy step was always skipped regardless of that flag's value --
# removing it changes nothing by itself, which is why this explicit
# `--include-package-data` line does the actual work. `--include-package-
# data` resolves its SOURCE relative to the INSTALLED PySide6 package (not a
# repo path), so it is portable across CI runners. Only `qtbase_es` is listed
# because pixelart_creator/i18n/ currently ships only `pixelart_es.qm`
# (English is the source language and needs no Qt catalogue either); ADD the
# matching `qtbase_<code>.qm` entry here whenever a new UI language ships.
# --macos-app-name="PixelArt Creator" (ADR-0067 R-3): read from Nuitka's
# own installed source (nuitka/freezer/MacOSApp.py:createPlistInfoFile,
# v4.2.2) -- `app_name = getMacOSAppName() or executable_name` is written to
# BOTH CFBundleName and CFBundleDisplayName. Qt's Cocoa platform plugin reads
# CFBundleName to build the application-menu "About %1" text
# (qcocoahelpers.mm), so the space is required for it to read "About PixelArt
# Creator" rather than "About PixelArtCreator". pysidedeploy's own
# extra_args value is split with shlex.split() (nuitka_helper.py), which
# preserves a quoted value containing a space as ONE token, so the quoting
# below is required, not decorative.
# --macos-signed-app-name=PixelArtCreator holds CFBundleIdentifier at its
# PRIOR value: `getMacOSSignedAppName() or app_name` would otherwise fall
# back to the now-spaced app_name and put a space into CFBundleIdentifier,
# which the ad-hoc/Developer-ID codesign step below never needed to tolerate
# before this change. This is the isolating half of the least-invasive fix --
# it keeps the CFBundleName change from leaking into signing identity.
# Neither option touches the .app bundle folder name, the .dmg name or the
# smoke-launch discovery path: those are driven by pysidedeploy's OWN
# `title` (below) via deploy_lib/deploy_util.py:finalize(), which copies
# Nuitka's generated bundle to `exec_directory / (title + ".app")` -- a
# rename that happens AFTER Nuitka has already written Info.plist, and reads
# `config.title`, never `getMacOSAppName()`. Confirmed by reading both source
# files together, not assumed.
extra_args = --quiet --assume-yes-for-downloads
    --include-data-dir=pixelart_creator/i18n=pixelart_creator/i18n
    --include-data-dir=pixelart_creator/icons=pixelart_creator/icons
    --include-data-dir=pixelart_creator/userguide_content=pixelart_creator/userguide_content
    --include-package-data=PySide6:translations/qtbase_es.qm
    --macos-create-app-bundle --macos-app-name="PixelArt Creator"
    --macos-signed-app-name=PixelArtCreator
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
