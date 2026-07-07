"""Render-fidelity reference generator for the web viewer (T13E-B07).

Owned by AGT-06 (QA). This is a **test helper**, not product code and not part of
the default pytest suite (``pyproject.toml`` pins ``testpaths = ["tests"]``, so
``web_viewer/tests`` is never auto-collected). It has two jobs, both grounded in
the shipped pure logic the JS mirror must match (ADR-0036 Addendum A.4/A.6):

1. Build a small, known project state as a wire op-log, run it through the
   **shipped** ``sync_protocol`` + ``realtime_apply`` + ``convergence`` +
   ``blend.composite_stack`` path to produce the *reference* composited RGBA.

2. Independently replay the SAME op-log through a faithful **Python mirror of
   viewer.js** (``decodeMessage`` -> ``decodeUpdate`` -> ``RealtimeState.accept``
   LWW -> ``blendTile`` source-over with ``Uint8ClampedArray`` round-half-to-even),
   and assert the mirror equals the shipped reference within a **+/-1 LSB**
   tolerance (the frontend-flagged Uint8ClampedArray-vs-numpy rounding margin).

It also emits ``fidelity_fixture.json`` — the exact wire frames a browser would
receive plus the expected composited RGBA — so the node ``*.mjs`` unit tests
(once node + a node-importable ``viewer_core`` module exist) decode the identical
frames and diff against the same expected bytes. Run it directly with the repo's
interpreter from the repo root::

    python web_viewer/tests/generate_reference.py

Exit code 0 = the Python mirror matches the shipped reference within tolerance.
"""

from __future__ import annotations

import base64
import json
import math
import os
import sys
from typing import Dict, List, Tuple

import numpy as np

# Self-contained: put the repo root (three levels up) on sys.path so this helper
# runs as ``python web_viewer/tests/generate_reference.py`` without PYTHONPATH.
_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pixelart_creator.logic.blend import composite_stack  # noqa: E402
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX  # noqa: E402
from pixelart_creator.logic.convergence import (  # noqa: E402
    LayerAttrOp,
    LayerOrderOp,
    MetadataOp,
    Operation,
    RasterOp,
)
from pixelart_creator.logic.document import Document  # noqa: E402
from pixelart_creator.logic.pixel_buffer import ColorMode  # noqa: E402
from pixelart_creator.logic.realtime_apply import (  # noqa: E402
    apply_remote,
    encode_update,
)
from pixelart_creator.logic.sync_protocol import decode_message  # noqa: E402
from pixelart_creator.logic.sync_protocol import (  # noqa: E402
    encode_update as frame_update,
)

TILE = CRDT_TILE_SIZE_PX
WIDTH = 68  # spans two horizontal tiles (64 + 4) to exercise a tile x-offset
HEIGHT = 3
DOC_ID = "proj-fidelity-fixture"

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE_PATH = os.path.join(HERE, "fidelity_fixture.json")


def _rgba_tile(pattern: List[Tuple[int, int, int, int]], tw: int, th: int) -> bytes:
    """Tile bytes from a repeating RGBA pattern (row-major, tw*th*4 bytes)."""
    cells = tw * th
    reps = (cells + len(pattern) - 1) // len(pattern)
    flat = (pattern * reps)[:cells]
    out = bytearray()
    for px in flat:
        out.extend(px)
    return bytes(out)


def _build_document() -> Document:
    """A 2-layer RGBA document; layer_ids == [1, 2], both paintable leaves."""
    doc = Document(WIDTH, HEIGHT, mode=ColorMode.RGBA)
    doc.add_layer("Top")
    return doc


def _build_ops() -> List[Operation]:
    """A deterministic op-log covering opaque, partial-alpha and LWW-loser tiles."""
    # Layer 1 (bottom): an opaque base tile + an offset tile at tile_x=1.
    base_full = _rgba_tile([(200, 40, 40, 255)], TILE, HEIGHT)
    base_edge = _rgba_tile([(10, 220, 10, 255)], WIDTH - TILE, HEIGHT)
    # Layer 2 (top): a partial-alpha tile that forces the source-over rounding path.
    top_full = _rgba_tile(
        [(0, 0, 255, 128), (255, 255, 0, 77), (30, 60, 90, 200), (0, 0, 0, 0)],
        TILE,
        HEIGHT,
    )
    # A STALE duplicate of the top tile (older stamp) — accept() must drop it, so the
    # winner is the (c=5) op below, not this (c=2) one. Proves LWW tiebreak parity.
    top_stale = _rgba_tile([(1, 2, 3, 255)], TILE, HEIGHT)

    ops: List[Operation] = [
        MetadataOp("width", str(WIDTH), 1, 0),
        MetadataOp("height", str(HEIGHT), 1, 0),
        # order op fixes bottom->top == [1, 2] for both reference and mirror.
        LayerOrderOp(0, (1, 2), 1, 0),
        RasterOp(0, 1, 0, 0, base_full, TILE, HEIGHT, 3, 0),
        RasterOp(0, 1, 1, 0, base_edge, WIDTH - TILE, HEIGHT, 3, 0),
        RasterOp(0, 2, 0, 0, top_stale, TILE, HEIGHT, 2, 9),  # LWW loser
        RasterOp(0, 2, 0, 0, top_full, TILE, HEIGHT, 5, 0),  # LWW winner
        LayerAttrOp(0, 2, "opacity", 0.75, 4, 0),  # partial layer opacity
    ]
    return ops


def _reference_rgba(ops: List[Operation]) -> np.ndarray:
    """Shipped-path reference: apply_remote onto a live doc, then composite_stack."""
    doc = _build_document()
    blob = encode_update(ops)
    apply_remote(doc, blob, site_id=0)
    frame = doc.frames[0]
    flat = composite_stack(frame.layers, doc.width, doc.height)
    return np.array(flat.data, dtype=np.uint8)


# --------------------------------------------------------------------------- #
# Faithful Python mirror of viewer.js pure logic (kept in lockstep for parity).
# --------------------------------------------------------------------------- #


def _u8_clamp(x: float) -> int:
    """ECMAScript ToUint8Clamp: clamp to 0..255 then round-half-to-EVEN.

    Mirrors what ``Uint8ClampedArray[i] = float`` does in the browser, which is the
    exact rounding viewer.js ``blendTile`` relies on. numpy ``np.round`` (used by the
    shipped ``_blend_over_arrays``) is also round-half-to-even, so the two agree.
    """
    if x <= 0.0:
        return 0
    if x >= 255.0:
        return 255
    f = math.floor(x)
    frac = x - f
    if frac < 0.5:
        return f
    if frac > 0.5:
        return f + 1
    return f if (f % 2 == 0) else f + 1


def _register_key(op: RasterOp) -> str:
    return f"raster:{op.frame_index}:{op.layer_id}:{op.tile_x}:{op.tile_y}"


def _mirror_accept(
    ops: List[Operation],
    stamps: Dict[str, Tuple[int, int, bytes]],
) -> List[Operation]:
    """Mirror RealtimeState.accept / viewer.js accept(): strictly-newer LWW winners."""
    winners: Dict[str, Operation] = {}
    winner_stamps: Dict[str, Tuple[int, int, bytes]] = {}
    for op in ops:
        if isinstance(op, RasterOp):
            key = _register_key(op)
            stamp = (op.logical_clock, op.site_id, op.pixels)
        elif isinstance(op, MetadataOp):
            key, stamp = f"meta:{op.key}", (op.logical_clock, op.site_id, b"")
        elif isinstance(op, LayerAttrOp):
            key = f"attr:{op.frame_index}:{op.layer_id}:{op.attr}"
            stamp = (op.logical_clock, op.site_id, b"")
        elif isinstance(op, LayerOrderOp):
            key = f"order:{op.frame_index}"
            stamp = (op.logical_clock, op.site_id, b"")
        else:  # pragma: no cover
            continue
        applied = stamps.get(key)
        if applied is not None and stamp <= applied:
            continue
        current = winner_stamps.get(key)
        if current is None or stamp > current:
            winners[key] = op
            winner_stamps[key] = stamp
    stamps.update(winner_stamps)
    return [winners[k] for k in sorted(winners)]


def _mirror_render(ops: List[Operation]) -> np.ndarray:
    """Mirror viewer.js model build + render(): LWW accept, then blendTile stack."""
    stamps: Dict[str, Tuple[int, int, bytes]] = {}
    fresh = _mirror_accept(ops, stamps)

    meta: Dict[str, str] = {}
    order: List[int] = []
    attrs: Dict[Tuple[int, int, str], object] = {}
    tiles: Dict[Tuple[int, int, int, int], RasterOp] = {}
    layer_seen: List[int] = []
    for op in fresh:
        if isinstance(op, MetadataOp):
            meta[op.key] = op.value
        elif isinstance(op, LayerOrderOp):
            order = list(op.order)
        elif isinstance(op, LayerAttrOp):
            attrs[(op.frame_index, op.layer_id, op.attr)] = op.value
        elif isinstance(op, RasterOp):
            tiles[(op.frame_index, op.layer_id, op.tile_x, op.tile_y)] = op
            if op.layer_id not in layer_seen:
                layer_seen.append(op.layer_id)

    width = int(meta.get("width", str(WIDTH)))
    height = int(meta.get("height", str(HEIGHT)))
    dst = np.zeros((height, width, 4), dtype=np.uint8)

    present = {lid for (_f, lid, _tx, _ty) in tiles}
    draw_order = [lid for lid in order if lid in present]
    for lid in layer_seen:
        if lid not in draw_order:
            draw_order.append(lid)

    for lid in draw_order:
        if attrs.get((0, lid, "visible")) is False:
            continue
        raw_op = attrs.get((0, lid, "opacity"))
        opacity = 1.0 if raw_op is None else max(0.0, min(1.0, float(raw_op)))
        for (fi, tile_lid, tx, ty), op in tiles.items():
            if tile_lid != lid:
                continue
            _blend_tile(dst, width, height, op, opacity)
    return dst


def _blend_tile(dst: np.ndarray, w: int, h: int, op: RasterOp, opacity: float) -> None:
    """Mirror viewer.js blendTile: source-over into a uint8 buffer, opacity-scaled."""
    px = op.pixels
    x0 = op.tile_x * TILE
    y0 = op.tile_y * TILE
    for r in range(op.tile_height):
        y = y0 + r
        if y < 0 or y >= h:
            continue
        for c in range(op.tile_width):
            x = x0 + c
            if x < 0 or x >= w:
                continue
            si = (r * op.tile_width + c) * 4
            sr, sg, sb = px[si], px[si + 1], px[si + 2]
            sa = (px[si + 3] / 255.0) * opacity
            if sa <= 0.0:
                continue
            if sa >= 1.0:
                dst[y, x] = (sr, sg, sb, 255)
                continue
            da = dst[y, x, 3] / 255.0
            one_minus = 1.0 - sa
            out_a = sa + da * one_minus
            safe_a = out_a if out_a > 0.0 else 1.0
            dst[y, x, 0] = _u8_clamp((sr * sa + dst[y, x, 0] * da * one_minus) / safe_a)
            dst[y, x, 1] = _u8_clamp((sg * sa + dst[y, x, 1] * da * one_minus) / safe_a)
            dst[y, x, 2] = _u8_clamp((sb * sa + dst[y, x, 2] * da * one_minus) / safe_a)
            dst[y, x, 3] = _u8_clamp(out_a * 255.0)


def _wire_frames(ops: List[Operation]) -> List[str]:
    """The exact sync_protocol UPDATE frame(s) a browser would receive (as text)."""
    blob = encode_update(ops)
    frame_bytes = frame_update(DOC_ID, blob)
    # Round-trip through the shipped decoder to prove it is a valid, in-cap frame.
    decoded = decode_message(frame_bytes)
    assert decoded.kind.value == "update"
    return [frame_bytes.decode("utf-8")]


def main() -> int:
    """Generate the reference, run the +/-1 LSB parity check, write the fixture."""
    ops = _build_ops()
    reference = _reference_rgba(ops)
    mirror = _mirror_render(ops)

    if reference.shape != mirror.shape:
        print(f"FAIL: shape mismatch {reference.shape} vs {mirror.shape}")
        return 1

    diff = np.abs(reference.astype(np.int16) - mirror.astype(np.int16))
    max_diff = int(diff.max())
    exact = int((diff == 0).all(axis=-1).sum())
    total = reference.shape[0] * reference.shape[1]

    print(f"reference/mirror shape : {reference.shape}")
    print(f"max abs channel diff   : {max_diff} LSB (tolerance +/-1)")
    print(f"exact-match pixels     : {exact}/{total}")

    fixture = {
        "note": "T13E-B07 render-fidelity fixture (shipped-path reference).",
        "document_id": DOC_ID,
        "width": int(reference.shape[1]),
        "height": int(reference.shape[0]),
        "frame_index": 0,
        "tolerance_lsb": 1,
        "wire_frames": _wire_frames(ops),
        "expected_rgba_b64": base64.b64encode(reference.tobytes()).decode("ascii"),
    }
    with open(FIXTURE_PATH, "w", encoding="utf-8") as fh:
        json.dump(fixture, fh, indent=2, sort_keys=True)
    print(f"wrote fixture          : {FIXTURE_PATH}")

    if max_diff > 1:
        print("FAIL: Python mirror diverges from shipped reference by > 1 LSB")
        return 1
    print("PASS: Python mirror matches shipped reference within +/-1 LSB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
