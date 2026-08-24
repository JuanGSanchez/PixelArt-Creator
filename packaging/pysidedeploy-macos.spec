[app]
title = PixelArtCreator
project_dir = .
input_file = pixelart_creator/__main__.py
project_file =
exec_directory = dist
icon =

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
# --include-data-dir=SOURCE=DEST (B6 fix): ships our own compiled catalogues
# (pixelart_creator/i18n/*.qm) into the frozen dist tree at the same
# package-relative path pixelart_creator/ui/i18n.py's
# _default_translations_dir() resolves at runtime (sibling of
# pixelart_creator/ui/). Nuitka standalone mode does not bundle package data
# by static import analysis alone, so this is required alongside
# --noinclude-qt-translations, which only skips Qt's OWN catalogues.
extra_args = --quiet --assume-yes-for-downloads --noinclude-qt-translations
    --include-data-dir=pixelart_creator/i18n=pixelart_creator/i18n
    --macos-create-app-bundle --macos-app-name=PixelArtCreator
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
