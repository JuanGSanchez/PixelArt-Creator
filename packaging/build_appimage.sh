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
# pyside6-deploy's own deploy_lib/deploy_util.py:finalize() copies Nuitka's
# compiled standalone dist folder into `exec_directory` renamed to the
# spec's `title` + ".dist" (`shutil.copytree(...)`), confirmed by a real
# build log: "[DEPLOY] Executed file created in .../dist/PixelArtCreator.dist".
# `title = PixelArtCreator` in pysidedeploy-linux.spec, so the folder this
# script consumes is dist/PixelArtCreator.dist, not dist/__main__.dist
# (v0.3.0 run 35941799524's assumption, which never existed post-copy). The
# binary INSIDE that folder is NOT assumed by name either -- a prior fix
# guessed `__main__` (the pre-copy Nuitka name) and that guess measurably
# failed too (run 35995818253: the folder existed, that binary name did
# not). It is DISCOVERED below instead: the one top-level executable regular
# file in the dist folder that is not a shared library.
DIST_DIR="dist/PixelArtCreator.dist"
APPDIR="build/${APP_NAME}.AppDir"
OUT_DIR="artifact"
OUT="${OUT_DIR}/${APP_NAME}-x86_64.AppImage"

if [ ! -d "${DIST_DIR}" ]; then
    echo "error: standalone dist folder not found at ${DIST_DIR}" >&2
    echo "       run pyside6-deploy -c packaging/pysidedeploy-linux.spec first" >&2
    exit 1
fi

BIN_NAME="$(find "${DIST_DIR}" -maxdepth 1 -type f -perm -u+x ! -name '*.so*' -printf '%f\n' | head -n1)"
if [ -z "${BIN_NAME}" ]; then
    echo "error: no executable binary found at the top level of ${DIST_DIR}" >&2
    exit 1
fi
echo "discovered standalone binary: ${BIN_NAME}"

rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${OUT_DIR}"
cp -a "${DIST_DIR}"/. "${APPDIR}/usr/bin/"

# AppRun launches the discovered frozen binary by its real name.
cat > "${APPDIR}/AppRun" <<EOF
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
exec "\${HERE}/usr/bin/${BIN_NAME}" "\$@"
EOF
chmod +x "${APPDIR}/AppRun"

# Desktop entry (required by appimagetool).
cat > "${APPDIR}/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PixelArt Creator
Exec=${BIN_NAME}
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
