#!/usr/bin/env bash
# =============================================================================
# build_appimage.sh — wrap the Nuitka STANDALONE dist into a self-contained
# AppImage (Slice 13D, REQ-P13-BUILD-004, ADR-0038 §2). Owner AGT-09 (BUILD).
#
# Consumes the folder produced by:
#     pyside6-deploy -c packaging/pysidedeploy-linux.spec --force
# and emits: artifact/PixelArtCreator-x86_64.AppImage
#
# Reproducible from committed config (this script + the linux spec). Run from
# the repo root on a Linux host with `patchelf` + `wget` available (the CI leg
# installs patchelf; appimagetool is fetched here). FUSE is not required —
# appimagetool runs with --appimage-extract-and-run.
# =============================================================================
set -euo pipefail

APP_NAME="PixelArtCreator"
# Nuitka standalone names the dist folder + frozen binary after the input-file
# stem. The shipped entry is pixelart_creator/__main__.py, so the stem is
# `__main__`.
DIST_DIR="dist/__main__.dist"
APPDIR="build/${APP_NAME}.AppDir"
OUT_DIR="artifact"
OUT="${OUT_DIR}/${APP_NAME}-x86_64.AppImage"

if [ ! -d "${DIST_DIR}" ]; then
    echo "error: standalone dist folder not found at ${DIST_DIR}" >&2
    echo "       run pyside6-deploy -c packaging/pysidedeploy-linux.spec first" >&2
    exit 1
fi

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${OUT_DIR}"
cp -a "${DIST_DIR}"/. "${APPDIR}/usr/bin/"

# AppRun launches the frozen binary (Nuitka names it after the input stem,
# `__main__`).
cat > "${APPDIR}/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/__main__" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

# Desktop entry (required by appimagetool).
cat > "${APPDIR}/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PixelArt Creator
Exec=__main__
Icon=pixelart-creator
Categories=Graphics;
Terminal=false
EOF

# Icon (required by appimagetool). Placeholder transparent PNG generated with
# Pillow (a shipped runtime dep) — TODO: replace with a real app icon.
python -c "from PIL import Image; Image.new('RGBA', (256, 256), (0, 0, 0, 0)).save('${APPDIR}/pixelart-creator.png')"

# Fetch appimagetool (pinned to the continuous release channel).
if [ ! -x appimagetool ]; then
    wget -q \
      https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage \
      -O appimagetool
    chmod +x appimagetool
fi

ARCH=x86_64 ./appimagetool --appimage-extract-and-run "${APPDIR}" "${OUT}"
echo "built ${OUT}"
