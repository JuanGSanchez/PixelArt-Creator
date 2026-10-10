# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Contract tests for the Kikko Badge icon family and its deriver.

The subject is the REAL, shipped ``pixelart_creator/icons/app/`` folder, the web
viewer's ``favicon.png``, ``scripts/derive_app_icons.py``, the three
``packaging/pysidedeploy-*.spec`` files and both READMEs. Tests read the committed
assets directly (Pillow, ``configparser``) or run the deriver as a real
subprocess through ``run_script`` (its documented command-line entry point).
Anything that needs a modified tree works on a COPY under ``tmp_path`` and never
touches a committed file.

Scenarios covered (one group each):

* SC-VI-BUILD-007-2 - five hand-drawn masters, binary transparency, the P, the
  easel canvas and the C in each, the C one pixel nearer the P at 16 and 32.
* SC-VI-BUILD-007-3 - no pixel of the C object touches the ring or the gold
  hairline (8-neighbourhood) in any master; the 64 px legs are 7 rows; the P's
  contact is reported as information and never fails the check.
* SC-VI-BUILD-008-1 - every png/.ico/.icns member (and the favicon) matches the
  pixels derived from the masters; the examined-file count is non-zero.
* SC-VI-BUILD-008-2 - 128/256/512/1024 are the 64 px master scaled by 2/4/8/16
  with nearest-neighbour sampling, and the 70 % fill floor holds.
* SC-VI-BUILD-010-1 (PNG half) - the committed PNGs carry only critical chunks
  and no attribution or internal vocabulary; a planted violation is reported.
* REQ-VI-UI-018 (data half) - the runtime sizes the app loads are family members.

The anti-resample signal: every derived member's distinct RGBA colours must be a
subset of the UNION of the five masters' own colours (plus fully transparent).
Any other colour is an interpolated blend a resample would produce and a
nearest-neighbour integer scale never does. The set is computed fresh from the
COMMITTED masters on each run, never hard-coded.

``--check`` compares DECODED PIXELS for every re-encoded member: a PNG byte
stream depends on the platform's zlib/libpng, so pixel identity is the portable
promise (``test_check_accepts_a_reencoded_but_pixel_identical_png`` is the
control). Real bytes are compared only for the generated construction table and
for the masters' pinned sha256 (a master is copied verbatim, never re-encoded).
"""

from __future__ import annotations

import configparser
import hashlib
import re
import shutil
import struct
import zlib
from pathlib import Path
from typing import Dict, FrozenSet, List, Tuple

import numpy as np
import pytest
from PIL import Image

import scripts.derive_app_icons as derive_app_icons

from .conftest import REPO_ROOT, ScriptRun, run_script

SCRIPT = "derive_app_icons.py"

_APP_ICON_DIR = REPO_ROOT / "pixelart_creator" / "icons" / "app"
_FAVICON = REPO_ROOT / "web_viewer" / "static" / "favicon.png"

RGBA = Tuple[int, int, int, int]
RGB = Tuple[int, int, int]


def _colors(path: Path) -> FrozenSet[RGBA]:
    """The set of distinct RGBA colours actually present in ``path``."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
        return frozenset(color for _count, color in im.getcolors(maxcolors=1_000_000))


def _master_path(size: int) -> Path:
    return _APP_ICON_DIR / derive_app_icons.master_name(size)


def _rgba(path: Path) -> Image.Image:
    with Image.open(path) as im:
        return im.convert("RGBA")


def _scratch(tmp_path: Path) -> Tuple[Path, Path]:
    """A COPY of the real icons folder and favicon under ``tmp_path`` (the real
    assets are read to seed it, never mutated), plus the copy's favicon path."""
    app_dir = tmp_path / "icons_app"
    shutil.copytree(_APP_ICON_DIR, app_dir)
    favicon = tmp_path / "static" / "favicon.png"
    favicon.parent.mkdir()
    shutil.copyfile(_FAVICON, favicon)
    return app_dir, favicon


def _scratch_args(app_dir: Path, favicon: Path, *extra: str) -> List[str]:
    return [*extra, "--app-dir", str(app_dir), "--favicon", str(favicon)]


def _check_scratch(app_dir: Path, favicon: Path) -> ScriptRun:
    return run_script(SCRIPT, _scratch_args(app_dir, favicon, "--check"))


def _change_one_pixel(path: Path, xy: Tuple[int, int] = (0, 0)) -> None:
    """Re-save ``path`` with exactly one pixel altered (a fully opaque colour)."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
        r, g, b, _a = im.getpixel(xy)
        im.putpixel(xy, ((r + 1) % 256, g, b, 255))
        with open(path, "wb") as fh:
            im.save(fh, format="PNG")


def _group_pixels(im: Image.Image, colors: FrozenSet[RGB]) -> List[Tuple[int, int]]:
    px = im.convert("RGBA").load()
    w, h = im.size
    return [
        (x, y)
        for y in range(h)
        for x in range(w)
        if px[x, y][3] == 255 and px[x, y][:3] in colors
    ]


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-008-1: every member re-derives pixel-identically.               #
# --------------------------------------------------------------------------- #


def test_check_reports_zero_mismatches_against_committed_pixels():
    """SC-VI-BUILD-008-1: ``--check`` over the committed tree, exit 0, counts printed.

    Byte-identity is NOT asserted (a re-encoded PNG's bytes are platform
    dependent, see the module docstring) - the portability control below proves
    that directly.
    """
    result = run_script(SCRIPT, ["--check"])
    assert result.returncode == 0, (
        f"derive_app_icons --check exited {result.returncode} against the "
        f"committed tree:\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "MISMATCH" not in result.stdout, result.stdout
    match = re.search(
        r"compared (\d+) of (\d+) files, (\d+) identical \(decoded pixels; plus "
        r"(\d+) \.ico frames and (\d+) \.icns entries",
        result.stdout,
    )
    assert match, f"no examined-count summary line: {result.stdout!r}"
    examined, declared, identical, ico_frames, icns_entries = map(int, match.groups())
    assert examined > 0 and examined == declared == identical, match.group(0)
    assert ico_frames == len(derive_app_icons.ICO_SIZES)
    assert icns_entries == len(derive_app_icons.ICNS_ENTRIES)
    n = len(derive_app_icons.MASTER_SIZES)
    assert f"masters - {n} examined, {n} sha256 match" in result.stdout, result.stdout


def test_check_detects_a_single_changed_pixel_in_a_derived_member(tmp_path):
    """SC-VI-BUILD-008-1 (control): one altered pixel of one member fails, by name.

    A pixel comparison that cannot detect a changed pixel is worse than the byte
    check it replaced: flip exactly ONE pixel of one committed member in a
    SCRATCH COPY (never the real asset) and confirm ``--check`` fails and names
    that file.
    """
    app_dir, favicon = _scratch(tmp_path)
    _change_one_pixel(app_dir / "app-icon-128.png")
    result = _check_scratch(app_dir, favicon)
    assert result.returncode != 0, (
        "derive_app_icons --check exited 0 against a scratch tree with a "
        f"deliberately altered pixel:\n{result.stdout}"
    )
    assert "app-icon-128.png" in result.stdout and "MISMATCH" in result.stdout
    assert "1 pixel(s) differ" in result.stdout, result.stdout


def test_check_detects_a_recoloured_opaque_pixel_whose_alpha_is_unchanged(tmp_path):
    """SC-VI-BUILD-008-1 (control): a colour change on an opaque pixel is seen.

    The comparison once measured the bounding box of the per-channel difference,
    and on an RGBA image that box is taken from the ALPHA channel alone - so a
    pixel that stays alpha 255 and only changes colour read as identical. Only a
    pixel that is OPAQUE in the member and stays opaque exercises that path.
    """
    app_dir, favicon = _scratch(tmp_path)
    target = app_dir / "app-icon-64.png"
    with Image.open(target) as im:
        im = im.convert("RGBA")
        before = im.getpixel((20, 20))
        assert before[3] == 255, "the chosen pixel must be opaque for this control"
        im.putpixel((20, 20), (before[0] ^ 0x01, before[1], before[2], 255))
        with open(target, "wb") as fh:
            im.save(fh, format="PNG")
    result = _check_scratch(app_dir, favicon)
    assert result.returncode != 0, result.stdout
    assert re.search(r"app-icon-64\.png: 1 pixel\(s\) differ", result.stdout)


def test_check_detects_a_single_changed_pixel_in_the_favicon(tmp_path):
    """SC-VI-BUILD-008-1 (control): the favicon is compared too, and named."""
    app_dir, favicon = _scratch(tmp_path)
    _change_one_pixel(favicon, (5, 5))
    result = _check_scratch(app_dir, favicon)
    assert result.returncode != 0, result.stdout
    assert "favicon.png" in result.stdout and "1 pixel(s) differ" in result.stdout


def test_check_detects_a_changed_pixel_inside_the_ico(tmp_path):
    """SC-VI-BUILD-008-1 (control): one altered pixel in ONE .ico frame is named."""
    app_dir, favicon = _scratch(tmp_path)
    masters = derive_app_icons.load_masters(app_dir)
    rendered = derive_app_icons.render_all(masters)
    px = rendered["app-icon-48.png"].load()
    px[10, 10] = (px[10, 10][0] ^ 0x55, 1, 2, 255)
    (app_dir / derive_app_icons.ICO_NAME).write_bytes(
        derive_app_icons._render_ico(rendered)
    )
    result = _check_scratch(app_dir, favicon)
    assert result.returncode != 0, result.stdout
    assert re.search(
        r"pixelart-creator\.ico \[48px member\]: 1 pixel\(s\) differ", result.stdout
    ), result.stdout


def test_check_detects_a_changed_pixel_inside_the_icns(tmp_path):
    """SC-VI-BUILD-008-1 (control): one altered pixel in ONE .icns entry is named."""
    app_dir, favicon = _scratch(tmp_path)
    masters = derive_app_icons.load_masters(app_dir)
    rendered = derive_app_icons.render_all(masters)
    px = rendered["app-icon-512.png"].load()
    px[100, 100] = (px[100, 100][0] ^ 0x55, 1, 2, 255)
    (app_dir / derive_app_icons.ICNS_NAME).write_bytes(
        derive_app_icons._render_icns(rendered)
    )
    result = _check_scratch(app_dir, favicon)
    assert result.returncode != 0, result.stdout
    # both entries that carry the 512 px member are named (ic09 and ic14)
    assert re.search(r"\[ic09 512px entry\]: 1 pixel\(s\) differ", result.stdout)
    assert re.search(r"\[ic14 512px entry\]: 1 pixel\(s\) differ", result.stdout)


def test_check_accepts_a_reencoded_but_pixel_identical_png(tmp_path):
    """SC-VI-BUILD-008-1 (portability control) - the exact condition the Linux CI hit.

    Re-save one committed member through Pillow with DIFFERENT compression
    settings, in a scratch copy, so its BYTES differ but its pixels do not.
    ``--check`` must still accept it: this proves the check addresses the
    cross-platform re-encoding difference, not merely this machine's encoder.
    """
    app_dir, favicon = _scratch(tmp_path)
    target = app_dir / "app-icon-256.png"
    original_bytes = target.read_bytes()
    with Image.open(target) as im:
        im = im.convert("RGBA")
        with open(target, "wb") as fh:
            im.save(fh, format="PNG", compress_level=1, optimize=False)
    assert target.read_bytes() != original_bytes, (
        "the re-encoded app-icon-256.png is byte-identical to the original "
        "- this test proves nothing unless the bytes actually changed"
    )
    assert (
        _rgba(target).tobytes() == _rgba(_APP_ICON_DIR / target.name).tobytes()
    ), "this test's own re-encode step changed a pixel"
    result = _check_scratch(app_dir, favicon)
    assert result.returncode == 0, (
        "derive_app_icons --check rejected a re-encoded-but-pixel-identical "
        f"PNG:\n{result.stdout}"
    )


def test_check_with_no_member_files_fails_on_zero_examined(tmp_path):
    """SC-VI-BUILD-008-1: a folder with only the masters examined nothing: exit 1."""
    app_dir = tmp_path / "only_masters"
    app_dir.mkdir()
    for size in derive_app_icons.MASTER_SIZES:
        shutil.copyfile(_master_path(size), app_dir / _master_path(size).name)
    favicon = tmp_path / "favicon.png"
    result = _check_scratch(app_dir, favicon)
    assert result.returncode == 1, result.stdout
    assert "compared zero files" in result.stderr, result.stderr
    assert "app-icon-16.png: missing on disk" in result.stdout


def test_regenerating_from_the_masters_alone_reproduces_every_member(tmp_path):
    """SC-VI-BUILD-008-1: write mode on a folder of masters yields committed pixels.

    Only the five masters are copied in; every member, the favicon, the .ico, the
    .icns and the construction table are WRITTEN by the deriver into the scratch
    folder, then compared against the committed ones, pixel for pixel (and the
    table byte for byte). The check run on the freshly written folder is clean.
    """
    app_dir = tmp_path / "regen"
    app_dir.mkdir()
    for size in derive_app_icons.MASTER_SIZES:
        shutil.copyfile(_master_path(size), app_dir / _master_path(size).name)
    favicon = tmp_path / "favicon.png"
    written = run_script(SCRIPT, _scratch_args(app_dir, favicon))
    assert written.returncode == 0, (written.stdout, written.stderr)
    assert "wrote 14 files" in written.stdout, written.stdout
    for member in derive_app_icons.APP_DIR_MEMBERS:
        assert (
            _rgba(app_dir / member.name).tobytes()
            == _rgba(_APP_ICON_DIR / member.name).tobytes()
        ), member.name
    assert _rgba(favicon).tobytes() == _rgba(_FAVICON).tobytes()
    table = derive_app_icons.CONSTRUCTION_TABLE_NAME
    assert (app_dir / table).read_bytes() == (_APP_ICON_DIR / table).read_bytes()
    result = _check_scratch(app_dir, favicon)
    assert result.returncode == 0, result.stdout


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-007-1 / -2: the masters and their pinned sha256.                #
# --------------------------------------------------------------------------- #


def test_every_master_matches_its_pinned_sha256():
    """SC-VI-BUILD-007-2: five masters exist and equal their pins (raw bytes)."""
    assert tuple(derive_app_icons.MASTER_SIZES) == (16, 24, 32, 48, 64)
    assert sorted(derive_app_icons.MASTER_SHA256) == [16, 24, 32, 48, 64]
    for size in derive_app_icons.MASTER_SIZES:
        pin = derive_app_icons.MASTER_SHA256[size]
        assert re.fullmatch(
            r"[0-9a-f]{64}", pin
        ), f"pin for {size} is not sha256: {pin}"
        digest = hashlib.sha256(_master_path(size).read_bytes()).hexdigest()
        assert digest == pin, f"logo-master-{size}.png: {digest} != pinned {pin}"


def test_check_detects_a_changed_pixel_in_a_master_by_its_sha256(tmp_path):
    """SC-VI-BUILD-007-2 (control): a one-pixel retouch of ONE master is named."""
    app_dir, favicon = _scratch(tmp_path)
    _change_one_pixel(app_dir / "logo-master-32.png", (16, 16))
    result = _check_scratch(app_dir, favicon)
    assert result.returncode != 0, result.stdout
    assert re.search(
        r"MISMATCH: logo-master-32\.png: sha256 [0-9a-f]{64} != pinned", result.stdout
    ), result.stdout
    assert "4 sha256 match" in result.stdout, result.stdout


def test_write_mode_refuses_an_unpinned_master_and_writes_nothing(tmp_path):
    """SC-VI-BUILD-007-2 (control): deriving from a changed master is refused."""
    app_dir = tmp_path / "regen"
    app_dir.mkdir()
    for size in derive_app_icons.MASTER_SIZES:
        shutil.copyfile(_master_path(size), app_dir / _master_path(size).name)
    _change_one_pixel(app_dir / "logo-master-16.png", (8, 8))
    favicon = tmp_path / "favicon.png"
    result = run_script(SCRIPT, _scratch_args(app_dir, favicon))
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "refusing to derive from an unpinned master" in result.stderr
    assert not favicon.exists()
    assert not (app_dir / "app-icon-16.png").exists()


def test_masters_have_binary_transparency_and_a_declared_palette():
    """SC-VI-BUILD-007-2: alpha in {0, 255} only, exact size, declared colours only."""
    union: set = set()
    for size in derive_app_icons.MASTER_SIZES:
        im = _rgba(_master_path(size))
        assert im.size == (size, size)
        for _n, (r, g, b, a) in im.getcolors(maxcolors=100_000):
            assert a in (0, 255), f"master {size}: partial alpha {a}"
            if a == 255:
                assert (r, g, b) in derive_app_icons.MASTER_PALETTE, (size, (r, g, b))
                union.add((r, g, b))
    # the palette declaration is closed AND complete: nothing declared goes unused
    assert union == set(derive_app_icons.MASTER_PALETTE)
    groups = [
        derive_app_icons.BORDER_COLORS,
        derive_app_icons.C_OBJECT_COLORS,
        derive_app_icons.P_COLORS,
        derive_app_icons.PLATE_COLORS,
    ]
    assert sum(len(g) for g in groups) == len(
        derive_app_icons.MASTER_PALETTE
    ), "a colour is declared under two roles"


def test_the_master_palette_check_flags_partial_alpha_a_stray_colour_and_a_wrong_box():
    """SC-VI-BUILD-007-2 (control): the palette check can fail, three different ways."""
    clean = {s: _rgba(_master_path(s)) for s in derive_app_icons.MASTER_SIZES}
    assert derive_app_icons.master_palette_problems(clean) == []
    # partial alpha on an opaque badge pixel
    partial = {**clean, 16: clean[16].copy()}
    partial[16].putpixel((8, 8), (27, 20, 38, 128))
    found = derive_app_icons.master_palette_problems(partial)
    assert any("partial alpha 128" in p for p in found), found
    # a colour that is in no role
    stray = {**clean, 24: clean[24].copy()}
    stray[24].putpixel((12, 12), (1, 2, 3, 255))
    found = derive_app_icons.master_palette_problems(stray)
    assert any("(1, 2, 3)" in p and "not in the palette" in p for p in found), found
    # a master whose opaque box moved (a pixel drawn into the margin)
    moved = {**clean, 32: clean[32].copy()}
    moved[32].putpixel((0, 0), (226, 55, 77, 255))
    found = derive_app_icons.master_palette_problems(moved)
    assert any("opaque box" in p for p in found), found


def test_each_master_shows_the_p_and_the_easel_canvas_with_the_c():
    """SC-VI-BUILD-007-2: P ink, easel wood, canvas and painted C in every master."""
    p_ink = frozenset({(27, 20, 38)})
    wood = frozenset({(224, 165, 95), (176, 108, 46), (112, 64, 31)})
    canvas = frozenset({(183, 235, 166)})
    painted_c = frozenset({(31, 107, 71)})
    for size in derive_app_icons.MASTER_SIZES:
        im = _rgba(_master_path(size))
        for label, colors in (
            ("P", p_ink),
            ("easel wood", wood),
            ("canvas", canvas),
            ("painted C", painted_c),
        ):
            assert _group_pixels(im, colors), f"master {size}: no {label} pixel"


# The reviewed (picked) candidate's masters are not committed - only the chosen
# candidate's final masters are. These two figures were measured once from that
# candidate's 16 and 32 px masters: the leftmost column of the C object (easel
# wood, canvas, painted C) and the rightmost column of the P. The retouch moves
# the C object one pixel toward the P and leaves the P where it was.
_CANDIDATE_C_LEFT = {16: 9, 32: 15}
_CANDIDATE_P_RIGHT = {16: 6, 32: 12}


@pytest.mark.parametrize("size", [16, 32])
def test_the_c_object_sits_one_pixel_nearer_the_p_than_in_the_reviewed_candidate(size):
    """SC-VI-BUILD-007-2: at 16 and 32 the P-to-C gap is 1 px smaller."""
    im = _rgba(_master_path(size))
    c_left = min(x for x, _y in _group_pixels(im, derive_app_icons.C_OBJECT_COLORS))
    p_right = max(x for x, _y in _group_pixels(im, derive_app_icons.P_COLORS))
    assert p_right == _CANDIDATE_P_RIGHT[size], "the P moved; it must stay as drawn"
    assert c_left == _CANDIDATE_C_LEFT[size] - 1, (
        f"master {size}: C object starts at x={c_left}, the reviewed candidate "
        f"started at x={_CANDIDATE_C_LEFT[size]} (expected exactly one pixel nearer)"
    )


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-007-3: border adjacency (gated 0 for the C, information for P). #
# --------------------------------------------------------------------------- #


def test_no_c_object_pixel_touches_the_border_in_any_master():
    """SC-VI-BUILD-007-3: 8-neighbourhood adjacency of C object vs ring/hairline = 0."""
    examined = 0
    for size in derive_app_icons.MASTER_SIZES:
        result = derive_app_icons.adjacency(
            _rgba(_master_path(size)), derive_app_icons.C_OBJECT_COLORS
        )
        assert result.group_pixels > 0, f"master {size}: no C-object pixel examined"
        assert result.border_pixels > 0, f"master {size}: no border pixel examined"
        assert result.touching == (), f"master {size}: C touches the border"
        examined += 1
    assert examined == 5


def test_the_check_prints_the_c_object_pixels_examined_and_zero_touching():
    """SC-VI-BUILD-007-3: the run prints masters and a non-zero C-pixel count."""
    result = run_script(SCRIPT, ["--check"])
    assert result.returncode == 0, result.stdout
    line = next(ln for ln in result.stdout.splitlines() if "border adjacency" in ln)
    assert "5 masters examined" in line
    counts = [int(n) for n in re.findall(r"\d+:(\d+)", line)]
    assert len(counts) == 5 and all(c > 0 for c in counts), line
    assert "touching the border: 0 (gate: 0)" in line


def test_the_p_contact_with_the_border_is_information_and_never_fails():
    """SC-VI-BUILD-007-3: the P keeps its contact (4 at 16/32/64, 5 at 48, 0 at 24)."""
    measured = {
        size: len(
            derive_app_icons.adjacency(
                _rgba(_master_path(size)), derive_app_icons.P_COLORS
            ).touching
        )
        for size in derive_app_icons.MASTER_SIZES
    }
    assert measured == {16: 4, 24: 0, 32: 4, 48: 5, 64: 4}, measured
    result = run_script(SCRIPT, ["--check"])
    assert result.returncode == 0, "the P's contact must not fail the check"
    assert "16:4 24:0 32:4 48:5 64:4" in result.stdout, result.stdout
    assert "info (not gated)" in result.stdout


def test_the_adjacency_check_flags_a_planted_c_object_pixel_next_to_the_ring():
    """SC-VI-BUILD-007-3 (control): a wood pixel placed beside the ring is seen."""
    im = _rgba(_master_path(24))
    clean = derive_app_icons.adjacency(im, derive_app_icons.C_OBJECT_COLORS)
    assert clean.touching == ()
    # (22, 12) is plate (cream) in the 24 px master, one pixel from the ring.
    px = im.load()
    assert px[22, 12][:3] in derive_app_icons.PLATE_COLORS
    px[22, 12] = (176, 108, 46, 255)
    planted = derive_app_icons.adjacency(im, derive_app_icons.C_OBJECT_COLORS)
    assert planted.touching == ((22, 12),)
    assert planted.group_pixels == clean.group_pixels + 1


def test_a_planted_adjacency_in_a_master_fails_the_run_and_names_the_master(tmp_path):
    """SC-VI-BUILD-007-3 (control): the CLI names the planted master."""
    app_dir, favicon = _scratch(tmp_path)
    target = app_dir / "logo-master-24.png"
    with Image.open(target) as im:
        im = im.convert("RGBA")
        im.putpixel((22, 12), (176, 108, 46, 255))
        with open(target, "wb") as fh:
            im.save(fh, format="PNG")
    result = _check_scratch(app_dir, favicon)
    assert result.returncode != 0, result.stdout
    assert re.search(
        r"ADJACENCY FAIL: logo-master-24\.png: 1 C-object pixel\(s\) touch",
        result.stdout,
    ), result.stdout


def _wood_rows(im: Image.Image) -> Dict[int, int]:
    wood = frozenset({(224, 165, 95), (176, 108, 46), (112, 64, 31)})
    rows: Dict[int, int] = {}
    for _x, y in _group_pixels(im, wood):
        rows[y] = rows.get(y, 0) + 1
    return rows


def test_the_64px_masters_easel_legs_are_seven_rows_tall():
    """SC-VI-BUILD-007-3: below the tray, the easel's wood runs for exactly 7 rows."""
    rows = _wood_rows(_rgba(_master_path(64)))
    tray_bottom = max(y for y, n in rows.items() if n >= 10)  # the widest wood row
    leg_rows = 0
    y = tray_bottom + 1
    while rows.get(y, 0) > 0:
        assert rows[y] < 10, f"row {y} is a tray row, not a leg row"
        leg_rows += 1
        y += 1
    assert leg_rows == 7, f"easel legs measure {leg_rows} rows, expected 7"


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-008-2 and the derivation rule.                                  #
# --------------------------------------------------------------------------- #


def test_every_family_member_is_a_whole_number_scale_of_a_whole_divisor_master():
    """SC-VI-BUILD-008-2: size == master * k for an integer k, master committed."""
    assert derive_app_icons.family_problems() == []
    for member in derive_app_icons.ALL_MEMBERS:
        assert member.master in derive_app_icons.MASTER_SIZES, member.name
        assert member.size % member.master == 0, member.name
        assert member.scale == member.size // member.master, member.name
    by_name = {m.name: m for m in derive_app_icons.ALL_MEMBERS}
    # the 1x members are their own size's master
    for size in (16, 24, 32, 48, 64):
        assert by_name[f"app-icon-{size}.png"].master == size
        assert by_name[f"app-icon-{size}.png"].scale == 1
    assert by_name["favicon.png"].master == 32 and by_name["favicon.png"].scale == 1


def test_a_family_declaration_that_breaks_the_rule_is_reported(monkeypatch):
    """SC-VI-BUILD-008-2 (control): a bad scale and a missing master are found."""
    bad = derive_app_icons.Member("app-icon-100.png", 100, 64, 1)
    monkeypatch.setattr(derive_app_icons, "ALL_MEMBERS", (bad,))
    problems = derive_app_icons.family_problems()
    assert any("not a whole multiple" in p for p in problems), problems
    ghost = derive_app_icons.Member("app-icon-90.png", 90, 45, 2)
    monkeypatch.setattr(derive_app_icons, "ALL_MEMBERS", (ghost,))
    assert any(
        "not a committed master" in p for p in derive_app_icons.family_problems()
    )


@pytest.mark.parametrize("size,k", [(128, 2), (256, 4), (512, 8), (1024, 16)])
def test_large_members_are_the_64px_master_scaled_with_nearest_neighbour(size, k):
    """SC-VI-BUILD-008-2: member == numpy block-repeat of the 64 px master by k.

    ``numpy.repeat`` is an independent route from Pillow's ``resize``: the
    expected pixels are replicated blocks, with no sampling filter involved.
    """
    master = np.array(_rgba(_master_path(64)))
    expected = np.repeat(np.repeat(master, k, axis=0), k, axis=1)
    got = np.array(_rgba(_APP_ICON_DIR / f"app-icon-{size}.png"))
    assert got.shape == (size, size, 4)
    assert np.array_equal(got, expected), f"app-icon-{size}.png != master 64 x {k}"


@pytest.mark.parametrize("size", [16, 24, 32, 48, 64])
def test_small_members_are_their_own_hand_drawn_master(size):
    """SC-VI-BUILD-008-1: app-icon-N.png == logo-master-N.png, pixel for pixel."""
    assert (
        _rgba(_APP_ICON_DIR / f"app-icon-{size}.png").tobytes()
        == _rgba(_master_path(size)).tobytes()
    )


def test_the_favicon_is_the_32px_master():
    """SC-VI-BUILD-008-1 / E-2: web_viewer/static/favicon.png == logo-master-32.png."""
    assert _FAVICON.is_file(), f"{_FAVICON} is not committed"
    got, want = _rgba(_FAVICON), _rgba(_master_path(32))
    assert got.size == (32, 32)
    assert got.tobytes() == want.tobytes()


def test_the_deriver_never_resamples_and_no_member_carries_a_blended_colour():
    """SC-VI-BUILD-008-2: every member's colours are a subset of the masters' union.

    The union of the five masters' own colours (plus fully transparent) is
    computed from the COMMITTED masters on each run. An interpolated colour -
    present in no master - is the signature of an accidental resample.
    """
    allowed = frozenset().union(
        *(_colors(_master_path(s)) for s in derive_app_icons.MASTER_SIZES)
    ) | {(0, 0, 0, 0)}
    assert (255, 255, 255, 255) not in allowed, "the old white plate is back"
    offenders: Dict[str, FrozenSet[RGBA]] = {}
    examined = 0
    for member in derive_app_icons.APP_DIR_MEMBERS:
        found = _colors(_APP_ICON_DIR / member.name)
        examined += 1
        if found - allowed:
            offenders[member.name] = found - allowed
    found = _colors(_FAVICON)
    examined += 1
    if found - allowed:
        offenders["favicon.png"] = found - allowed
    assert examined == len(derive_app_icons.ALL_MEMBERS)
    assert not offenders, (
        "one or more derived members carry a colour outside the masters' own "
        f"palette (a resample signature): {offenders!r}"
    )


def test_a_bicubic_upscale_would_be_flagged_by_the_colour_subset_rule():
    """SC-VI-BUILD-008-2 (control): the subset rule fails a blurred upscale."""
    master = _rgba(_master_path(64))
    allowed = _colors(_master_path(64))
    blurred = master.resize((128, 128), Image.Resampling.BICUBIC)
    extra = frozenset(c for _n, c in blurred.getcolors(maxcolors=1_000_000)) - allowed
    assert extra, "the control upscale produced no blended colour - control is void"
    exact = master.resize((128, 128), Image.Resampling.NEAREST)
    assert frozenset(c for _n, c in exact.getcolors(1_000_000)) <= allowed


def test_check_enforces_the_fill_floor():
    """SC-VI-BUILD-008-2: ``--check`` reports the fill gate over the committed family.

    Cross-checked against a direct, from-the-committed-pixels measurement that
    does not use the deriver's own functions.
    """
    result = run_script(SCRIPT, ["--check"])
    assert (
        result.returncode == 0
    ), f"derive_app_icons --check exited {result.returncode}:\n{result.stdout}"
    assert "FILL FAIL" not in result.stdout, result.stdout
    assert "fill check" in result.stdout, result.stdout

    checked = [
        member
        for member in derive_app_icons.ALL_MEMBERS
        if not derive_app_icons.fill_exempt(member)
    ]
    assert checked, "no plated (non-exempt) member found to check against the floor"
    assert (
        f"minimum-fill check - {len(checked)} plated members checked" in result.stdout
    )
    below_floor = {
        member.name: derive_app_icons.fill_ratio(member)
        for member in checked
        if derive_app_icons.fill_ratio(member) < derive_app_icons.FILL_RATIO_MIN
    }
    assert not below_floor, (
        f"member(s) below the {derive_app_icons.FILL_RATIO_MIN:.0%} fill "
        f"floor: {below_floor!r}"
    )
    assert derive_app_icons.FILL_RATIO_MIN >= 0.70, "the 70% floor must not be lowered"
    for member in checked:
        path = _FAVICON if member.name == "favicon.png" else _APP_ICON_DIR / member.name
        box = _rgba(path).getchannel("A").point(lambda a: 255 if a else 0).getbbox()
        measured = max(box[2] - box[0], box[3] - box[1]) / member.size
        assert measured >= 0.70, f"{member.name}: measured fill {measured:.3f}"


def test_the_fill_floor_fails_a_member_that_is_below_it(monkeypatch, capsys):
    """SC-VI-BUILD-008-2 (control): a floor above a member's fill fails it."""
    monkeypatch.setattr(derive_app_icons, "FILL_RATIO_MIN", 0.90)
    code = derive_app_icons.run(_APP_ICON_DIR, _FAVICON, check=True)
    out = capsys.readouterr().out
    assert code == 1
    # 32 px (87.5%) is under 0.90 and 48/64 (91.7/93.8%) are not
    assert re.search(r"FILL FAIL: app-icon-32\.png: .* fill 88% < required 90%", out)
    assert "FILL FAIL: app-icon-64.png" not in out


def test_image_fill_ratio_measures_the_opaque_box_of_synthetic_images():
    """SC-VI-BUILD-008-2 (control): the measuring function reads known geometry."""
    im = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    assert derive_app_icons.image_fill_ratio(im) == 0.0
    for x in range(2, 9):
        im.putpixel((x, 4), (1, 2, 3, 255))
    assert derive_app_icons.image_fill_ratio(im) == pytest.approx(0.7)


# --------------------------------------------------------------------------- #
# The .ico / .icns containers carry exactly the family's pixels.              #
# --------------------------------------------------------------------------- #


def _png_pixel_bytes(size: int) -> bytes:
    return _rgba(_APP_ICON_DIR / f"app-icon-{size}.png").tobytes()


def test_ico_members_are_pixel_identical_to_the_nearest_neighbour_pngs():
    """SC-VI-BUILD-008-1: every .ico frame == the family PNG of that size."""
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
            assert got == _png_pixel_bytes(size), (
                f".ico member {size}px differs from app-icon-{size}.png pixel-for-"
                "pixel - a library resize fallback was reached"
            )


def test_icns_entries_are_pixel_identical_to_the_nearest_neighbour_pngs():
    """SC-VI-BUILD-008-1: EVERY .icns entry (1x and 2x) == the family PNG of its size.

    Read through Pillow's own ``.icns`` reader - an independent route from the
    deriver's container parser - entry by entry, so a pixel size that appears
    twice (32 px as 32@1x and as 16@2x) is checked both times.
    """
    with Image.open(_APP_ICON_DIR / derive_app_icons.ICNS_NAME) as icns:
        entries = sorted(icns.info["sizes"])
        assert len(entries) == len(derive_app_icons.ICNS_ENTRIES) == 11, entries
        pixel_sizes = sorted({w * scale for w, _h, scale in entries})
        assert pixel_sizes == sorted(derive_app_icons.ICNS_SIZES)
        for entry in entries:
            width, _height, scale = entry
            px = width * scale
            got = icns.icns.getimage(entry).convert("RGBA").tobytes()
            assert got == _png_pixel_bytes(px), (
                f".icns entry {entry} ({px}px) differs from app-icon-{px}.png "
                "pixel-for-pixel - a library resize fallback was reached"
            )


def test_the_icns_carries_the_16_and_32_pixel_entries_at_1x_and_2x():
    """The 16@1x/16@2x and 32@1x/32@2x entries are present (16, 32, 32, 64 px)."""
    with Image.open(_APP_ICON_DIR / derive_app_icons.ICNS_NAME) as icns:
        entries = set(icns.info["sizes"])
    for key in ((16, 16, 1), (16, 16, 2), (32, 32, 1), (32, 32, 2)):
        assert key in entries, f"{key} missing from the .icns: {sorted(entries)}"


def test_the_icns_container_is_well_formed():
    """The deriver's container: magic, declared length, TOC, no trailing bytes."""
    data = (_APP_ICON_DIR / derive_app_icons.ICNS_NAME).read_bytes()
    assert data[:4] == b"icns"
    assert struct.unpack(">I", data[4:8])[0] == len(data)
    assert data[8:12] == b"TOC "
    entries = derive_app_icons.parse_icns(data)
    assert [t for t, _p in entries] == [t for t, _s in derive_app_icons.ICNS_ENTRIES]
    for _t, payload in entries:
        assert payload[:8] == b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------- #
# SC-VI-BUILD-010-1 (PNG half): public-safe chunks and strings.               #
# --------------------------------------------------------------------------- #

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
#: Chunk types a shipped icon may carry: the critical ones. Anything else (text,
#: time, physical size, ICC, gamma ...) is metadata the art does not need.
_ALLOWED_CHUNKS = frozenset({"IHDR", "PLTE", "tRNS", "IDAT", "IEND"})
#: Attribution and internal-vocabulary markers (written split so this file does
#: not trip the repository's own scans for the very strings it looks for).
_FORBIDDEN = re.compile(
    "|".join(
        [
            "cla" + "ude",
            "anthro" + "pic",
            "(?<![A-Za-z0-9])AG" + "T-[0-9]+",
            "(?<![A-Za-z0-9])O" + "F[0-9]+(?![A-Za-z0-9])",
            "co-auth" + "ored",
            "generated" + " with",
            "design" + "-docs",
        ]
    ),
    re.IGNORECASE,
)


def _png_chunks(data: bytes) -> List[Tuple[str, bytes]]:
    assert data[:8] == _PNG_MAGIC, "not a PNG"
    pos, out = 8, []
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        out.append(
            (data[pos + 4 : pos + 8].decode("ascii"), data[pos + 8 : pos + 8 + length])
        )
        pos += 12 + length
    return out


def _scan_png(name: str, data: bytes) -> Tuple[int, List[str]]:
    """Return (chunks examined, findings) for one PNG's bytes."""
    findings: List[str] = []
    chunks = _png_chunks(data)
    for ctype, body in chunks:
        if ctype not in _ALLOWED_CHUNKS:
            findings.append(f"{name}: ancillary chunk {ctype}")
        match = _FORBIDDEN.search(body.decode("latin-1"))
        if match:
            findings.append(f"{name}: {ctype} chunk contains {match.group(0)!r}")
    return len(chunks), findings


def _committed_pngs() -> List[Path]:
    paths = [_master_path(s) for s in derive_app_icons.MASTER_SIZES]
    paths += [_APP_ICON_DIR / m.name for m in derive_app_icons.APP_DIR_MEMBERS]
    paths.append(_FAVICON)
    paths.append(_APP_ICON_DIR / "logo-source-64.png")
    return [p for p in paths if p.is_file()]


def test_committed_pngs_carry_only_critical_chunks_and_no_forbidden_text():
    """SC-VI-BUILD-010-1: zero findings over a non-zero number of PNG chunks."""
    files = _committed_pngs()
    assert len(files) >= len(derive_app_icons.MASTER_SIZES) + len(
        derive_app_icons.ALL_MEMBERS
    )
    chunks_examined, findings = 0, []
    for path in files:
        n, found = _scan_png(path.name, path.read_bytes())
        chunks_examined += n
        findings += found
    assert chunks_examined > 0
    assert findings == [], findings


def test_the_icns_and_ico_containers_carry_no_forbidden_text_and_clean_embedded_pngs():
    """SC-VI-BUILD-010-1: the containers' own bytes and every embedded PNG are clean."""
    ico = (_APP_ICON_DIR / derive_app_icons.ICO_NAME).read_bytes()
    icns = (_APP_ICON_DIR / derive_app_icons.ICNS_NAME).read_bytes()
    for name, data in (("ico", ico), ("icns", icns)):
        assert not _FORBIDDEN.search(data.decode("latin-1")), f"{name} bytes"
    embedded = derive_app_icons.parse_icns(icns)
    assert embedded, "no embedded PNG examined"
    for ostype, payload in embedded:
        n, found = _scan_png(f"icns:{ostype}", payload)
        assert n > 0 and found == [], found


def _planted_png(path: Path, text: bytes) -> bytes:
    """``path``'s PNG with a tEXt chunk holding ``text`` inserted before IEND."""
    data = path.read_bytes()
    body = b"Comment\x00" + text
    chunk = (
        struct.pack(">I", len(body))
        + b"tEXt"
        + body
        + struct.pack(">I", zlib.crc32(b"tEXt" + body))
    )
    iend = data.rfind(b"\x00\x00\x00\x00IEND")
    return data[:iend] + chunk + data[iend:]


def test_the_png_scan_reports_a_planted_attribution_and_a_planted_chunk():
    """SC-VI-BUILD-010-1 (control): a planted tEXt chunk with attribution is found."""
    planted = _planted_png(_master_path(16), b"Generated " + b"with Cla" + b"ude Code")
    _n, findings = _scan_png("planted.png", planted)
    assert any("ancillary chunk tEXt" in f for f in findings), findings
    assert any("contains" in f for f in findings), findings
    harmless = _planted_png(_master_path(16), b"hello")
    _n, found = _scan_png("harmless.png", harmless)
    assert found == ["harmless.png: ancillary chunk tEXt"], found


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
            f"{path.name} is fully transparent - the OLD placeholder "
            "(Image.new('RGBA', (256, 256), (0, 0, 0, 0))) was never replaced"
        )
    # Same construction as app-icon-256.png (CONSTRUCTION-TABLE.md) -> byte-identical.
    expected_bytes = (_APP_ICON_DIR / "app-icon-256.png").read_bytes()
    assert path.read_bytes() == expected_bytes, (
        f"{path.name} is not byte-identical to app-icon-256.png despite an "
        "identical declared construction (master/scale)"
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
        # The image is a member of the Kikko Badge family (derived from the masters).
        assert Path(target).name in {
            m.name for m in derive_app_icons.ALL_MEMBERS
        }, f"{filename}: {target!r} is not a derived family member"
