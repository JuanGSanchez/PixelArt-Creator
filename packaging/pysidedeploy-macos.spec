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
# just i18n, alongside --noinclude-qt-translations, which only skips Qt's OWN
# catalogues.
extra_args = --quiet --assume-yes-for-downloads --noinclude-qt-translations
    --include-data-dir=pixelart_creator/i18n=pixelart_creator/i18n
    --include-data-dir=pixelart_creator/icons=pixelart_creator/icons
    --include-data-dir=pixelart_creator/userguide_content=pixelart_creator/userguide_content
    --macos-create-app-bundle --macos-app-name=PixelArtCreator
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
