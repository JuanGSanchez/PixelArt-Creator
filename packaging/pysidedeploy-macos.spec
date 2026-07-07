# =============================================================================
# pyside6-deploy spec — macOS native distributable (Slice 13D, ADR-0038 §2/§4)
# REQ-P13-BUILD-003 · SC-P13-BUILD-003-1 · owner AGT-09 (BUILD)
#
# Produces a Nuitka STANDALONE .app bundle (Contents/MacOS + bundled Qt
# plugins); the CI leg ad-hoc-signs it (`codesign --sign -`), smoke-launches it
# offscreen, and wraps it in a .dmg via `hdiutil`. Developer-ID signing →
# notarization (`notarytool`) → stapling is a SEPARATE, credential-gated,
# NON-blocking CI step (ADR-0038 §4, Article XI) that runs ONLY when an Apple
# Developer ID secret is supplied — its absence ships the unsigned/ad-hoc
# artifact and does NOT fail the phase. NO credential is committed here or
# anywhere; signing consumes GitHub secrets at CI time only.
#
# Run FROM THE REPO ROOT:
#     pyside6-deploy -c packaging/pysidedeploy-macos.spec --force \
#                    --keep-deployment-files
#
# PyInstaller fallback (ADR-0038 §1):
#     pyinstaller --noconfirm --windowed --name PixelArtCreator \
#       --collect-all PySide6 pixelart_creator/__main__.py    # produces a .app
# =============================================================================

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
extra_args = --quiet --assume-yes-for-downloads --noinclude-qt-translations
    --macos-create-app-bundle --macos-app-name=PixelArtCreator
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
