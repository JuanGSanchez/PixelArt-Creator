# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the brand-logo asset family.

One test per acceptance criterion, asserted against the COMMITTED assets and
configuration actually on disk in this worktree, not against a hand-built
``tmp_path`` fixture: unlike the sibling ``scripts/`` contract tests in this
directory (``string_audit_check`` / ``check_layering``, which deliberately
never scan the real tree), this module's subject IS the real, shipped
``pixelart_creator/icons/app/`` family, ``scripts/derive_app_icons.py``, the
three ``packaging/pysidedeploy-*.spec`` files and both READMEs.

``run_script`` (``.conftest``) still invokes ``scripts/derive_app_icons.py``
as a real subprocess for its ``--check`` contract -- the documented CLI entry
point, not a private function call. Everything else reads the committed
files directly with Pillow (already a shipped dependency) and
``configparser`` (the format ``pysidedeploy-*.spec`` files actually are).

The anti-resample signal (the module docstring's own "highlight"): every
derived member's distinct RGBA colours must be a SUBSET of the source
master's own 9 colours plus the flat white plate fill. Any colour outside
that set is an interpolated blend a resample would produce and a
nearest-neighbour crop-and-scale never does -- computed fresh from the
COMMITTED ``logo-source-64.png`` each run, never hardcoded, so a change to
the source master re-grounds the allowed set automatically instead of
silently drifting out of date.

The ``.ico``/``.icns`` pixel-identity check loads every member with Pillow
and asserts its raw pixel data is BYTE-FOR-BYTE identical to the matching
``app-icon-<N>.png`` family member -- the strongest available proof that the
container assembly path (``_render_ico``/``_render_icns``) never reaches
Pillow's own internal resize/blur fallback.

``--check``'s own contract, fixed 2026-09-01 (CI's Linux leg, PR #52): it
compares DECODED PIXELS for every re-encoded PNG/.ico/.icns member, not raw
bytes -- a PNG byte stream is not portable across platforms/Pillow-libpng
builds even when every pixel is identical (see
``scripts/derive_app_icons.py``'s module docstring). Real bytes are still
compared for the generated construction table (deterministic text, no
encoder involved) and for ``logo-source-64.png``'s own sha256 (the
provenance master is copied verbatim, never re-encoded, so its
byte-identity is a real, portable guarantee).
``test_check_detects_a_single_changed_pixel_in_a_derived_member`` and
``test_check_accepts_a_reencoded_but_pixel_identical_png`` below exercise
that corrected contract directly, against a scratch copy of the real tree
(never the committed assets themselves).
"""

from __future__ import annotations

import configparser
import shutil
from pathlib import Path
from typing import Dict, FrozenSet, Tuple

from PIL import Image

import scripts.derive_app_icons as derive_app_icons

from .conftest import REPO_ROOT, run_script

SCRIPT = "derive_app_icons.py"

_APP_ICON_DIR = REPO_ROOT / "pixelart_creator" / "icons" / "app"

RGBA = Tuple[int, int, int, int]


def _colors(path: Path) -> FrozenSet[RGBA]:
    """The set of distinct RGBA colours actually present in ``path``."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
        return frozenset(color for _count, color in im.getcolors(maxcolors=1_000_000))


def _scratch_app_dir(tmp_path: Path) -> Path:
    """A COPY of the real, committed ``pixelart_creator/icons/app/`` tree
    under ``tmp_path`` -- the real assets are read to seed it, never mutated
    themselves (the "never mutate a real user artifact" rule)."""
    scratch = tmp_path / "icons_app"
    shutil.copytree(_APP_ICON_DIR, scratch)
    return scratch


# --------------------------------------------------------------------------- #
# Every raster re-derives pixel-identically from the committed master.        #
# --------------------------------------------------------------------------- #


def test_check_reports_zero_mismatches_against_committed_pixels():
    """``--check`` re-derives every member in memory and compares committed pixels.

    Run against the real, committed ``pixelart_creator/icons/app/`` tree --
    proven by re-running the deriver and comparing decoded pixels, not by
    inspection. Byte-identity is NOT asserted here (a re-encoded PNG's byte
    stream is platform-dependent, see the module docstring above) -- the
    portability-control test below proves that directly.
    """
    result = run_script(SCRIPT, ["--check"])
    assert result.returncode == 0, (
        f"derive_app_icons --check exited {result.returncode} against the "
        f"committed tree:\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "MISMATCH" not in result.stdout, (
        f"derive_app_icons --check reported a pixel mismatch against the "
        f"committed tree:\n{result.stdout}"
    )
    assert (
        "compared" in result.stdout and "identical" in result.stdout
    ), f"derive_app_icons --check produced no summary line: {result.stdout!r}"
    assert "sha256 matches" in result.stdout, (
        f"derive_app_icons --check produced no provenance-master summary "
        f"line: {result.stdout!r}"
    )


def test_check_detects_a_single_changed_pixel_in_a_derived_member(tmp_path):
    """A pixel comparison that cannot detect a changed pixel is worse than
    the byte check it replaced -- this is the required negative proof.

    Flip exactly ONE pixel of one committed member in a SCRATCH COPY of the
    tree (never the real asset) and confirm ``--check`` still fails, and
    names that file.
    """
    scratch = _scratch_app_dir(tmp_path)
    target = scratch / "app-icon-128.png"

    with Image.open(target) as im:
        im = im.convert("RGBA")
        original = im.getpixel((0, 0))
        # A fully-opaque colour guaranteed to differ from the transparent
        # corner pixel of a plated, centred mark on a BxB canvas.
        changed = (
            (original[0] + 1) % 256,
            original[1],
            original[2],
            255,
        )
        im.putpixel((0, 0), changed)
        with open(target, "wb") as fh:
            im.save(fh, format="PNG")

    result = run_script(SCRIPT, ["--check", "--app-dir", str(scratch)])
    assert result.returncode != 0, (
        "derive_app_icons --check exited 0 against a scratch tree with a "
        f"deliberately altered pixel:\n{result.stdout}"
    )
    assert "app-icon-128.png" in result.stdout and "MISMATCH" in result.stdout, (
        f"derive_app_icons --check did not name the altered file: " f"{result.stdout!r}"
    )
    assert "differ" in result.stdout, (
        "derive_app_icons --check did not report a pixel-level difference "
        f"description: {result.stdout!r}"
    )


def test_check_accepts_a_reencoded_but_pixel_identical_png(tmp_path):
    """The portability control -- the exact condition the Linux CI leg hit.

    Re-save one committed member through Pillow with DIFFERENT compression
    settings, in a scratch copy, so its BYTES differ but its pixels do not.
    ``--check`` must still accept it: this proves the fix actually addresses
    the cross-platform re-encoding difference, not merely this machine's own
    encoder output.
    """
    scratch = _scratch_app_dir(tmp_path)
    target = scratch / "app-icon-256.png"
    original_bytes = target.read_bytes()

    with Image.open(target) as im:
        im = im.convert("RGBA")
        with open(target, "wb") as fh:
            im.save(fh, format="PNG", compress_level=1, optimize=False)

    reencoded_bytes = target.read_bytes()
    assert reencoded_bytes != original_bytes, (
        "the re-encoded app-icon-256.png is byte-identical to the original "
        "-- this test proves nothing unless the bytes actually changed"
    )
    with (
        Image.open(target) as reencoded,
        Image.open(_APP_ICON_DIR / target.name) as committed,
    ):
        assert (
            reencoded.convert("RGBA").tobytes() == committed.convert("RGBA").tobytes()
        ), (
            "the re-encoded app-icon-256.png is no longer pixel-identical to "
            "the committed original -- this test's own re-encode step is broken"
        )

    result = run_script(SCRIPT, ["--check", "--app-dir", str(scratch)])
    assert result.returncode == 0, (
        "derive_app_icons --check rejected a re-encoded-but-pixel-identical "
        f"PNG (the exact condition the Linux CI leg hit):\n{result.stdout}"
    )
    assert "app-icon-256.png" not in "\n".join(
        line for line in result.stdout.splitlines() if "MISMATCH" in line
    ), f"derive_app_icons --check flagged the re-encoded file:\n{result.stdout}"


# --------------------------------------------------------------------------- #
# No derived member carries a resampled (blended) colour.                     #
# --------------------------------------------------------------------------- #


def test_no_derived_member_contains_a_colour_outside_source_plus_plate():
    """Every ALL_MEMBERS raster's colours are a subset of {source colours} | {white}.

    An interpolated intermediate colour -- present in neither the source
    master's own palette nor the flat white plate fill -- is the signature of
    an accidental resample (bilinear/bicubic blending at an edge); a true
    integer nearest-neighbour crop-and-scale can only ever reproduce colours
    that already exist in the source crop, or the plate's own flat fill.
    """
    source_colors = _colors(_APP_ICON_DIR / derive_app_icons.SOURCE_NAME)
    allowed = source_colors | {derive_app_icons.PLATE_COLOR}

    offenders: Dict[str, FrozenSet[RGBA]] = {}
    for member in derive_app_icons.ALL_MEMBERS:
        found = _colors(_APP_ICON_DIR / member.name)
        extra = found - allowed
        if extra:
            offenders[member.name] = extra

    assert not offenders, (
        "one or more derived members carry a colour outside the source's own "
        f"palette + the white plate (a resample signature): {offenders!r}"
    )


# --------------------------------------------------------------------------- #
# 16/24px show the easel alone; 32/64px show the P alone.                     #
# --------------------------------------------------------------------------- #


def test_small_sizes_show_easel_alone_mid_sizes_show_p_alone():
    """The committed rasters themselves carry only ONE sub-mark's real colours.

    Grounded in the source master, not in ``FAMILY``'s own declared ``mark``
    field (which the deriver reads but a docs-only mislabel could not catch):
    ``P_ONLY`` / ``EASEL_ONLY`` are each computed as the colours unique to
    that sub-mark's crop against the OTHER sub-mark's crop, straight from the
    committed source. A full lockup or a redrawn glyph at 16/24px would leak
    the P's black/grey into a file this test expects to carry the easel's
    green/brown alone, and vice versa at 32/64px.
    """
    with Image.open(_APP_ICON_DIR / derive_app_icons.SOURCE_NAME) as source:
        source = source.convert("RGBA")
        easel_crop_colors = frozenset(
            c
            for _n, c in source.crop(derive_app_icons.EASEL_BBOX).getcolors(100_000)
            if c[3] > 0
        )
        p_crop_colors = frozenset(
            c
            for _n, c in source.crop(derive_app_icons.P_MARK_BBOX).getcolors(100_000)
            if c[3] > 0
        )
    easel_only = easel_crop_colors - p_crop_colors
    p_only = p_crop_colors - easel_crop_colors
    assert easel_only, "the easel crop shares every opaque colour with the P crop"
    assert p_only, "the P crop shares every opaque colour with the easel crop"

    for name in ("app-icon-16.png", "app-icon-24.png"):
        found = _colors(_APP_ICON_DIR / name)
        assert found.isdisjoint(p_only), (
            f"{name}: carries P-only colour(s) {found & p_only!r} -- expected the "
            "easel sub-mark alone, not the full lockup or a redrawn glyph"
        )
        assert found & easel_only, (
            f"{name}: carries none of the easel's own colours {easel_only!r} -- "
            "the easel sub-mark does not actually appear"
        )

    for name in ("app-icon-32.png", "app-icon-64.png"):
        found = _colors(_APP_ICON_DIR / name)
        assert found.isdisjoint(easel_only), (
            f"{name}: carries easel-only colour(s) {found & easel_only!r} -- "
            "expected the 'P' sub-mark alone"
        )
        assert found & p_only, (
            f"{name}: carries none of the P's own colours {p_only!r} -- the 'P' "
            "sub-mark does not actually appear"
        )


# --------------------------------------------------------------------------- #
# Every .ico/.icns member is pixel-identical to its PNG counterpart.          #
# --------------------------------------------------------------------------- #


def _png_pixel_bytes(size: int) -> bytes:
    with Image.open(_APP_ICON_DIR / f"app-icon-{size}.png") as im:
        return im.convert("RGBA").tobytes()


def test_ico_members_are_pixel_identical_to_the_nearest_neighbour_pngs():
    with Image.open(_APP_ICON_DIR / derive_app_icons.ICO_NAME) as ico:
        sizes = sorted({w for w, _h in ico.ico.sizes()})
        assert sizes == sorted(
            derive_app_icons.ICO_SIZES
        ), f".ico carries sizes {sizes}, expected {sorted(derive_app_icons.ICO_SIZES)}"
        for size in sizes:
            frame = Image.open(_APP_ICON_DIR / derive_app_icons.ICO_NAME)
            frame.size = (size, size)
            frame.load()
            got = frame.convert("RGBA").tobytes()
            expected = _png_pixel_bytes(size)
            assert got == expected, (
                f".ico member {size}px differs from app-icon-{size}.png pixel-for-"
                "pixel -- Pillow's own resize fallback was reached"
            )


def test_icns_members_are_pixel_identical_to_the_nearest_neighbour_pngs():
    with Image.open(_APP_ICON_DIR / derive_app_icons.ICNS_NAME) as icns:
        by_physical_size = {}
        for entry in icns.info["sizes"]:
            frame = icns.icns.getimage(entry)
            by_physical_size.setdefault(frame.size[0], frame)
        sizes = sorted(by_physical_size)
        assert sizes == sorted(derive_app_icons.ICNS_SIZES), (
            f".icns carries physical sizes {sizes}, expected "
            f"{sorted(derive_app_icons.ICNS_SIZES)}"
        )
        for size, frame in by_physical_size.items():
            got = frame.convert("RGBA").tobytes()
            expected = _png_pixel_bytes(size)
            assert got == expected, (
                f".icns member {size}px differs from app-icon-{size}.png pixel-for-"
                "pixel -- Pillow's own resize fallback was reached"
            )


# --------------------------------------------------------------------------- #
# The AppImage PNG replaces the transparent placeholder.                      #
# --------------------------------------------------------------------------- #


def test_appimage_png_is_committed_and_not_a_transparent_placeholder():
    path = _APP_ICON_DIR / derive_app_icons.APPIMAGE_MEMBER.name
    assert path.is_file(), f"{path} is not a committed file"
    with Image.open(path) as im:
        im = im.convert("RGBA")
        assert im.size == (256, 256), f"{path.name} is {im.size}, expected (256, 256)"
        alpha_channel = im.getchannel("A")
        assert alpha_channel.getextrema()[1] > 0, (
            f"{path.name} is fully transparent -- the OLD placeholder "
            "(Image.new('RGBA', (256, 256), (0, 0, 0, 0))) was never replaced"
        )
    # Same construction as app-icon-256.png (CONSTRUCTION-TABLE.md) -> byte-identical.
    expected_bytes = (_APP_ICON_DIR / "app-icon-256.png").read_bytes()
    assert path.read_bytes() == expected_bytes, (
        f"{path.name} is not byte-identical to app-icon-256.png despite an "
        "identical declared construction (mark/scale/plate)"
    )
    # build_appimage.sh no longer SYNTHESISES a placeholder.
    appimage_sh = (REPO_ROOT / "packaging" / "build_appimage.sh").read_text(
        encoding="utf-8"
    )
    assert "Image.new" not in appimage_sh, (
        "packaging/build_appimage.sh still synthesises a placeholder icon "
        "(an 'Image.new(' call is present) instead of shipping the committed PNG"
    )
    assert (
        "pixelart-creator.png" in appimage_sh
    ), "packaging/build_appimage.sh no longer names the committed AppImage icon"


# --------------------------------------------------------------------------- #
# Every packaging spec names an existing committed icon file.                 #
# --------------------------------------------------------------------------- #


def test_packaging_specs_name_existing_committed_icon_files():
    expectations = {
        "pysidedeploy-windows.spec": ".ico",
        "pysidedeploy-linux.spec": ".png",
        "pysidedeploy-macos.spec": ".icns",
    }
    for filename, extension in expectations.items():
        spec_path = REPO_ROOT / "packaging" / filename
        assert spec_path.is_file(), f"missing packaging spec: {spec_path}"
        parser = configparser.ConfigParser()
        parser.read(spec_path, encoding="utf-8")
        assert parser.has_option(
            "app", "icon"
        ), f"{filename}: [app] section carries no 'icon' key"
        icon_value = parser.get("app", "icon").strip()
        assert icon_value != "", f"{filename}: icon = <empty> (the pre-fix state)"
        assert icon_value.endswith(
            extension
        ), f"{filename}: icon = {icon_value!r} does not end with {extension!r}"
        icon_path = REPO_ROOT / icon_value
        assert icon_path.is_file(), (
            f"{filename}: icon = {icon_value!r} does not exist on disk at "
            f"{icon_path}"
        )


# --------------------------------------------------------------------------- #
# Both READMEs render the logo above their H1.                                #
# --------------------------------------------------------------------------- #


def test_both_readmes_show_the_logo_above_the_h1():
    for filename in ("README.md", "README.es.md"):
        path = REPO_ROOT / filename
        assert path.is_file(), f"missing {path}"
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()]
        image_line_index = next(
            (i for i, ln in enumerate(lines) if ln.strip().startswith("![")),
            None,
        )
        h1_index = next(
            (i for i, ln in enumerate(lines) if ln.strip().startswith("# ")),
            None,
        )
        assert image_line_index is not None, f"{filename}: no Markdown image found"
        assert h1_index is not None, f"{filename}: no H1 ('# ...') found"
        assert image_line_index < h1_index, (
            f"{filename}: image line {image_line_index} does not precede the H1 "
            f"line {h1_index}"
        )
        image_line = lines[image_line_index].strip()
        assert not (
            "http://" in image_line or "https://" in image_line
        ), f"{filename}: logo image references an external host: {image_line!r}"
        # Extract the path between the LAST '(' and ')' on the image line and
        # confirm it resolves inside the repository itself (no external host,
        # no hotlink).
        target = image_line[image_line.rfind("(") + 1 : image_line.rfind(")")]
        assert (REPO_ROOT / target).is_file(), (
            f"{filename}: image target {target!r} does not resolve to a file "
            "inside the repository"
        )


# --------------------------------------------------------------------------- #
# The deriver's --check enforces the fill floor.                              #
# --------------------------------------------------------------------------- #


def test_check_enforces_the_fill_floor():
    """``--check`` reports the fill gate over the committed family, zero failures.

    Cross-checked against a direct, from-source computation using the
    deriver's own ``fill_ratio``/``fill_exempt`` so the CLI's summary line and
    the underlying geometry agree.
    """
    result = run_script(SCRIPT, ["--check"])
    assert (
        result.returncode == 0
    ), f"derive_app_icons --check exited {result.returncode}:\n{result.stdout}"
    assert (
        "FILL FAIL" not in result.stdout
    ), f"derive_app_icons --check reported a fill failure:\n{result.stdout}"
    assert "fill check" in result.stdout, (
        f"derive_app_icons --check produced no fill-check summary line: "
        f"{result.stdout!r}"
    )

    checked = [
        member
        for member in derive_app_icons.ALL_MEMBERS
        if not derive_app_icons.fill_exempt(member)
    ]
    assert checked, "no plated (non-exempt) member found to check against the floor"
    below_floor = {
        member.name: derive_app_icons.fill_ratio(member)
        for member in checked
        if derive_app_icons.fill_ratio(member) < derive_app_icons.FILL_RATIO_MIN
    }
    assert not below_floor, (
        f"member(s) below the {derive_app_icons.FILL_RATIO_MIN:.0%} fill "
        f"floor: {below_floor!r}"
    )
