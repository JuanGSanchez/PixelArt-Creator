#!/usr/bin/env bash
# =============================================================================
# check_payload.sh -- prove that a shipped payload carries the bundled data
# directories, byte for byte, and that the typeface's licence travels with it.
# Owned by the GitHub/DevOps role (BUILD).
#
# WHY: pixelart_creator/fonts/ and pixelart_creator/themes/ are DATA, not
# packages (no __init__.py), read at run time through importlib.resources. A
# missing one is invisible from a source checkout and fails only for an
# installed user -- the failure class that broke the v0.3.0 installers for the
# icons. This script is the content check the wheel and each installer are put
# through (REQ-VI-BUILD-005): CI runs it on the built wheel and on the
# unpacked contents of the Windows, Linux and macOS artefacts.
#
# USAGE (from anywhere; the reference copy is the repository this script sits in):
#     bash packaging/check_payload.sh <payload-root> <label>
#   <payload-root>  a folder that CONTAINS the payload: an unpacked wheel, the
#                   Nuitka dist folder, an extracted AppImage, a mounted .dmg.
#                   It must not be the source checkout itself, or the check
#                   would compare the repository with itself and pass blind.
#   <label>         a name for the artefact, used only in the report.
#
# WHAT IT CHECKS, for every folder named pixelart_creator/fonts found under the
# payload root (at least one must exist):
#   * every file the repository ships under pixelart_creator/fonts and
#     pixelart_creator/themes is present beside it and byte-identical (cmp):
#     the Nifen Art TTFs, the six Nifen Art CJK TTFs, OFL.txt, FONTLOG.txt,
#     FONTLOG-CJK.txt and every theme file;
#   * the eleven names fonts/ must hold are each named in the script and printed
#     with their size, so a font the repository lost is still refused;
#   * the shipped OFL.txt carries the Ark Pixel Font copyright line verbatim,
#     a second, differently-dated copyright line (the typeface's own), and the
#     Reserved Font Name declaration;
#   * the repository's root NOTICE travels with the payload (REQ-L10N-BUILD-008).
#     For each payload package folder, with <parent> the folder that holds
#     pixelart_creator, exactly three paths are NOTICE candidates:
#         <parent>/NOTICE                       (the installers)
#         <parent>/*.dist-info/licenses/NOTICE  (a wheel, current layout)
#         <parent>/*.dist-info/NOTICE           (a wheel, the older layout)
#     At least one must exist, and every one that exists must be byte-identical
#     to the root NOTICE of the checkout this script sits in. Each compared path
#     is printed with its verdict. A NOTICE anywhere else in a payload (a
#     bundled third-party package's own) is outside the candidate set on
#     purpose: neither required nor compared.
# It prints the number of payload folders, files, notice lines and NOTICE files
# examined, and fails when it examined nothing, or when a package folder had no
# NOTICE to compare.
#
# EXIT: 0 every check passed; 1 a check failed or nothing was examined; 2 usage.
# Needs only bash, find, cmp, grep and wc (Git for Windows and the macOS and
# Linux runners all have them). No bash 4 features: macOS ships bash 3.2.
# =============================================================================
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "usage: bash packaging/check_payload.sh <payload-root> <label>" >&2
    exit 2
fi
ROOT="$1"
LABEL="$2"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF_PKG="${REPO_ROOT}/pixelart_creator"
REF_NOTICE="${REPO_ROOT}/NOTICE"
DATA_DIRS="fonts themes"
DONOR_LINE='Copyright (c) 2021, TakWolf (https://takwolf.com).'
RESERVED_NAME='Reserved Font Name "Nifen Art"'

fail=0
problem() {
    echo "  PROBLEM: $*" >&2
    fail=1
}

# The root NOTICE must travel with the payload. $1 is the payload package folder
# (<parent>/pixelart_creator). Counts every candidate it compares in
# notice_files, and fails the folder when none was compared.
check_notice() {
    local parent cand here
    parent="$(dirname "$1")"
    here=0
    if [ ! -f "${REF_NOTICE}" ]; then
        problem "the repository holds no root NOTICE (${REF_NOTICE}); nothing to compare"
        return 0
    fi
    for cand in "${parent}/NOTICE" "${parent}"/*.dist-info/licenses/NOTICE "${parent}"/*.dist-info/NOTICE; do
        [ -f "${cand}" ] || continue
        here=$((here + 1))
        notice_files=$((notice_files + 1))
        if cmp -s "${REF_NOTICE}" "${cand}"; then
            echo "    NOTICE ${cand}  identical to the repository's root NOTICE"
        else
            problem "NOTICE differs from the repository's root NOTICE: ${cand}"
        fi
    done
    if [ "${here}" -eq 0 ]; then
        problem "NOTICE is missing from the payload; looked in: ${parent}/NOTICE, ${parent}/*.dist-info/licenses/NOTICE, ${parent}/*.dist-info/NOTICE"
    fi
}

if [ ! -d "${ROOT}" ]; then
    echo "check_payload [${LABEL}]: payload root not found: ${ROOT}" >&2
    exit 1
fi
ROOT_ABS="$(cd "${ROOT}" && pwd)"
if [ "${ROOT_ABS}" = "${REPO_ROOT}" ]; then
    echo "check_payload [${LABEL}]: the payload root is the source checkout itself; refusing to compare it with itself" >&2
    exit 1
fi

echo "check_payload [${LABEL}]: payload root ${ROOT_ABS}"

pkg_dirs=0
files_examined=0
notice_lines=0
notice_files=0

# Every payload folder that holds a pixelart_creator/fonts folder.
while IFS= read -r fonts_dir; do
    pkg="$(dirname "${fonts_dir}")"
    pkg_dirs=$((pkg_dirs + 1))
    echo "payload package folder: ${pkg}"

    for data in ${DATA_DIRS}; do
        ref="${REF_PKG}/${data}"
        found=0
        present=0
        while IFS= read -r ref_file; do
            rel="${ref_file#"${ref}"/}"
            found=$((found + 1))
            files_examined=$((files_examined + 1))
            if [ ! -f "${pkg}/${data}/${rel}" ]; then
                problem "${data}/${rel} is missing from the payload"
            elif ! cmp -s "${ref_file}" "${pkg}/${data}/${rel}"; then
                problem "${data}/${rel} differs from the repository copy"
            else
                present=$((present + 1))
            fi
        done < <(find "${ref}" -type f | sort)
        if [ "${found}" -eq 0 ]; then
            problem "the repository holds no file under pixelart_creator/${data}; nothing to compare"
        fi
        echo "  ${data}: ${present} of ${found} repository file(s) present and byte-identical"
    done

    # The eleven names the payload must carry in fonts/: the two Nifen Art TTFs, the six
    # Nifen Art CJK TTFs (three families, Regular and Bold), the licence and the two change logs.
    for f in NifenArt-Regular.ttf NifenArt-Bold.ttf \
        NifenArtCJKJP-Regular.ttf NifenArtCJKJP-Bold.ttf \
        NifenArtCJKSC-Regular.ttf NifenArtCJKSC-Bold.ttf \
        NifenArtCJKKR-Regular.ttf NifenArtCJKKR-Bold.ttf \
        OFL.txt FONTLOG.txt FONTLOG-CJK.txt; do
        if [ -f "${pkg}/fonts/${f}" ]; then
            echo "    fonts/${f}  $(wc -c < "${pkg}/fonts/${f}" | tr -d ' ') bytes"
        else
            problem "fonts/${f} is not in the payload"
        fi
    done

    ofl="${pkg}/fonts/OFL.txt"
    if [ -f "${ofl}" ]; then
        if grep -qF "${DONOR_LINE}" "${ofl}"; then
            notice_lines=$((notice_lines + 1))
        else
            problem "OFL.txt lacks the Ark Pixel Font line: ${DONOR_LINE}"
        fi
        own="$(grep -cE '^Copyright \(c\) 20[0-9]{2}, ' "${ofl}" || true)"
        if [ "${own}" -ge 2 ]; then
            notice_lines=$((notice_lines + own))
        else
            problem "OFL.txt carries ${own} dated copyright line(s); the donor's and the typeface's own are both required"
        fi
        if grep -qF "${RESERVED_NAME}" "${ofl}"; then
            notice_lines=$((notice_lines + 1))
        else
            problem "OFL.txt lacks the declaration: ${RESERVED_NAME}"
        fi
    fi

    check_notice "${pkg}"
done < <(find "${ROOT_ABS}" -type d -path '*/pixelart_creator/fonts' | sort)

echo "check_payload [${LABEL}]: ${pkg_dirs} payload package folder(s), ${files_examined} file(s) compared, ${notice_lines} notice line(s) found, ${notice_files} NOTICE file(s) compared"

if [ "${pkg_dirs}" -eq 0 ]; then
    echo "check_payload [${LABEL}]: no pixelart_creator/fonts folder under the payload root; the check examined nothing" >&2
    exit 1
fi
if [ "${files_examined}" -eq 0 ]; then
    echo "check_payload [${LABEL}]: no file was compared; the check examined nothing" >&2
    exit 1
fi
if [ "${fail}" -ne 0 ]; then
    echo "check_payload [${LABEL}]: FAILED" >&2
    exit 1
fi
echo "check_payload [${LABEL}]: PASSED"
