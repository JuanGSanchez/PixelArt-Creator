#!/usr/bin/env bash
# =============================================================================
# build_appimage.sh — wrap the Nuitka STANDALONE dist into a self-contained
# AppImage (REQ-P13-BUILD-004, ADR-0038 §2). Owned by the GitHub/DevOps role (BUILD).
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

# Icon (required by appimagetool). Ships the committed 256x256 raster
# (the derived icon family, pixelart_creator/icons/app/CONSTRUCTION-TABLE.md)
# under the SAME basename the .desktop entry's Icon= key already expects
# (verified below, not assumed) -- no more transparent placeholder.
ICON_SRC="pixelart_creator/icons/app/pixelart-creator.png"
if [ ! -f "${ICON_SRC}" ]; then
    echo "error: committed app icon not found at ${ICON_SRC}" >&2
    exit 1
fi
DESKTOP_ICON_KEY="$(sed -n 's/^Icon=//p' "${APPDIR}/${APP_NAME}.desktop")"
if [ "${DESKTOP_ICON_KEY}" != "pixelart-creator" ]; then
    echo "error: .desktop Icon= key '${DESKTOP_ICON_KEY}' does not match the shipped icon basename 'pixelart-creator'" >&2
    exit 1
fi
cp "${ICON_SRC}" "${APPDIR}/${DESKTOP_ICON_KEY}.png"

# Fetch appimagetool (pinned to the continuous release channel).
if [ ! -x appimagetool ]; then
    wget -q \
      https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage \
      -O appimagetool
    chmod +x appimagetool
fi

ARCH=x86_64 ./appimagetool --appimage-extract-and-run "${APPDIR}" "${OUT}"
echo "built ${OUT}"
