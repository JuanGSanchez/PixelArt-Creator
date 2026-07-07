# =============================================================================
# pyside6-deploy spec — LINUX native distributable (Slice 13D, ADR-0038 §2)
# REQ-P13-BUILD-004 · SC-P13-BUILD-004-1 · owner AGT-09 (BUILD)
#
# Produces a Nuitka STANDALONE dist folder (dist/__main__.dist/, named after the
# input-file stem `__main__`) with the Qt
# plugins bundled; packaging/build_appimage.sh then wraps that folder into a
# self-contained, distro-agnostic .AppImage (the BUILD-004 target). Run FROM
# THE REPO ROOT:
#
#     pyside6-deploy -c packaging/pysidedeploy-linux.spec --force \
#                    --keep-deployment-files
#     bash packaging/build_appimage.sh
#
# Standalone (folder) mode is used rather than onefile because AppImage is built
# from an AppDir tree; the folder maps straight into usr/bin/ of the AppDir.
#
# PyInstaller fallback (ADR-0038 §1):
#     pyinstaller --noconfirm --onedir --name PixelArtCreator \
#       --collect-all PySide6 pixelart_creator/__main__.py   # then wrap in AppImage
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
# On Linux the platform plugin is `xcb` (+ offscreen for the CI smoke); the
# Nuitka PySide6 plugin bundles it. Listed explicitly as defence-in-depth.
plugins = platforms,styles,imageformats,iconengines,platforminputcontexts

[nuitka]
macos.permissions =
# standalone → a self-contained dist FOLDER that build_appimage.sh turns into
# a single .AppImage.
mode = standalone
extra_args = --quiet --assume-yes-for-downloads --noinclude-qt-translations
    --nofollow-import-to=sync_backend --nofollow-import-to=web_viewer
    --nofollow-import-to=tests --nofollow-import-to=scripts
    --nofollow-import-to=docs --nofollow-import-to=pytest
    --nofollow-import-to=hypothesis

[buildozer]
mode =
