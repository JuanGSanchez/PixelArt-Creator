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
