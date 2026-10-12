"""The viewer page declares exactly one favicon, and it is the brand mark at k = 1.

Pure standard library: the page is parsed with ``html.parser`` (never a regex over the
raw text) and the PNGs are decoded with ``zlib`` so the comparison is on decoded
PIXELS -- PNG bytes depend on the zlib/libpng that encoded them and are not portable
(the portability control below re-encodes the mark at two compression levels and
proves the pixels survive whatever the bytes are). No Qt, no sync backend, no CRDT
dependency, no network.

Each check is a function that raises ``AssertionError``; the real page must pass it
and every control (missing file, duplicated link, one altered pixel) must fail it.
"""

from __future__ import annotations

import struct
import zlib
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple
from urllib.parse import unquote, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = REPO_ROOT / "web_viewer" / "static" / "index.html"
BRAND_MARK_32 = REPO_ROOT / "pixelart_creator" / "icons" / "app" / "logo-master-32.png"

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_LINK_LINE = '<link rel="icon" type="image/png" href="favicon.png">'

#: (width, height, RGBA bytes row-major)
Raster = Tuple[int, int, bytes]


# --------------------------------------------------------------------------- page ---
class _IconLinks(HTMLParser):
    """Collect the ``href`` of every ``<link>`` whose ``rel`` has an ``icon`` token."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: List[str] = []

    def _see(self, tag: str, attrs) -> None:
        if tag != "link":
            return
        found = {name.lower(): (value or "") for name, value in attrs}
        if "icon" in found.get("rel", "").lower().split():
            self.hrefs.append(found.get("href", ""))

    def handle_starttag(self, tag, attrs):
        self._see(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._see(tag, attrs)


def favicon_hrefs(page: Path) -> List[str]:
    parser = _IconLinks()
    parser.feed(page.read_text(encoding="utf-8"))
    parser.close()
    return parser.hrefs


def check_one_link(page: Path) -> str:
    hrefs = favicon_hrefs(page)
    assert len(hrefs) == 1, f"expected exactly 1 favicon link, found {len(hrefs)}: {hrefs}"
    return hrefs[0]


def resolve(page: Path, href: str) -> Path:
    """Resolve ``href`` against the page's folder (the dev server's static root)."""
    parts = urlsplit(href)
    assert not parts.scheme and not parts.netloc, f"favicon href is not local: {href!r}"
    assert parts.path, "favicon href has no path"
    target = page.parent / unquote(parts.path).lstrip("/")
    assert target.is_file(), f"favicon link {href!r} resolves to no file: {target}"
    return target


# --------------------------------------------------------------------------- PNG ----
def decode_png(data: bytes) -> Raster:
    """Decode an 8-bit RGBA, non-interlaced PNG into raw pixels (all five filters)."""
    assert data.startswith(_PNG_SIGNATURE), "not a PNG"
    pos, idat, header = len(_PNG_SIGNATURE), b"", None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    assert header is not None, "no IHDR"
    width, height, depth, colour, _comp, _filt, interlace = header
    assert (depth, colour, interlace) == (8, 6, 0), f"unsupported PNG layout {header}"
    raw = zlib.decompress(idat)
    stride, bpp = width * 4, 4
    assert len(raw) == height * (stride + 1), "pixel data length mismatch"
    out = bytearray()
    prev = bytearray(stride)
    for row in range(height):
        base = row * (stride + 1)
        ftype = raw[base]
        line = bytearray(raw[base + 1 : base + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ftype == 0:
                add = 0
            elif ftype == 1:
                add = a
            elif ftype == 2:
                add = b
            elif ftype == 3:
                add = (a + b) // 2
            elif ftype == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                add = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
            else:
                raise AssertionError(f"bad PNG filter type {ftype}")
            line[i] = (line[i] + add) & 0xFF
        out += line
        prev = line
    return width, height, bytes(out)


def encode_png(raster: Raster, level: int) -> bytes:
    """Minimal RGBA encoder (filter 0) used only by the controls."""
    width, height, pixels = raster

    def chunk(kind: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(kind + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    return (
        _PNG_SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, level))
        + chunk(b"IEND", b"")
    )


def assert_same_pixels(left: Raster, right: Raster) -> int:
    """Raise unless every RGBA channel matches; return the channel count compared."""
    assert left[:2] == right[:2], f"size differs: {left[:2]} vs {right[:2]}"
    bad = [i for i, (x, y) in enumerate(zip(left[2], right[2])) if x != y]
    assert not bad, f"{len(bad)} channels differ; first at channel index {bad[0]}"
    return len(left[2])


# ------------------------------------------------------------------ whole contract --
def check_page(page: Path) -> Tuple[int, int, int]:
    """Run the full contract; return (links, pixels, channels compared)."""
    href = check_one_link(page)
    icon = decode_png(resolve(page, href).read_bytes())
    mark = decode_png(BRAND_MARK_32.read_bytes())
    channels = assert_same_pixels(icon, mark)
    return 1, icon[0] * icon[1], channels


def _scratch_page(tmp_path: Path, link_lines: str) -> Path:
    """Copy of the real page (and its favicon) with the icon link line replaced."""
    source = PAGE.read_text(encoding="utf-8")
    assert source.count(_LINK_LINE) == 1, "scratch template line not found exactly once"
    page = tmp_path / "index.html"
    page.write_text(source.replace(_LINK_LINE, link_lines), encoding="utf-8")
    (tmp_path / "favicon.png").write_bytes((PAGE.parent / "favicon.png").read_bytes())
    return page


# -------------------------------------------------------------------------- tests ---
def test_page_carries_exactly_one_favicon_link_that_matches_the_brand_mark():
    links, pixels, channels = check_page(PAGE)
    print(f"\nfavicon: links={links} pixels={pixels} channels_compared={channels}")
    assert (links, pixels, channels) == (1, 32 * 32, 32 * 32 * 4)


def test_favicon_link_is_a_local_relative_file_in_the_static_folder():
    href = check_one_link(PAGE)
    assert href == "favicon.png"
    assert resolve(PAGE, href) == PAGE.parent / "favicon.png"


def test_control_missing_file_fails(tmp_path):
    page = _scratch_page(tmp_path, '<link rel="icon" type="image/png" href="absent.png">')
    assert check_one_link(page) == "absent.png"  # the count check alone passes
    with pytest.raises(AssertionError, match="resolves to no file"):
        check_page(page)


def test_control_two_links_fail_the_exactly_one_check(tmp_path):
    two = _LINK_LINE + '\n  <link rel="shortcut icon" href="favicon.png">'
    page = _scratch_page(tmp_path, two)
    assert len(favicon_hrefs(page)) == 2
    with pytest.raises(AssertionError, match="exactly 1 favicon link, found 2"):
        check_one_link(page)


def test_control_no_link_fails_the_exactly_one_check(tmp_path):
    page = _scratch_page(tmp_path, "")
    with pytest.raises(AssertionError, match="found 0"):
        check_page(page)


def test_control_remote_href_is_refused(tmp_path):
    page = _scratch_page(tmp_path, '<link rel="icon" href="https://example.invalid/f.png">')
    with pytest.raises(AssertionError, match="not local"):
        check_page(page)


def test_control_one_altered_pixel_fails(tmp_path):
    page = _scratch_page(tmp_path, _LINK_LINE)
    width, height, pixels = decode_png((tmp_path / "favicon.png").read_bytes())
    tweaked = bytearray(pixels)
    tweaked[0] ^= 1
    (tmp_path / "favicon.png").write_bytes(encode_png((width, height, bytes(tweaked)), 6))
    with pytest.raises(AssertionError, match="1 channels differ; first at channel index 0"):
        check_page(page)


def test_pixel_comparison_ignores_png_encoding_differences():
    mark = decode_png(BRAND_MARK_32.read_bytes())
    fast, small = encode_png(mark, 1), encode_png(mark, 9)
    # Whatever the bytes are (they may differ between zlib builds), the pixels are not.
    assert assert_same_pixels(decode_png(fast), decode_png(small)) == 32 * 32 * 4
    assert assert_same_pixels(decode_png(fast), mark) == 32 * 32 * 4
