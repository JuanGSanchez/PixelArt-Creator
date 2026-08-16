"""T-18 (AGT-06 audit) — REQ-P4-UI-015 budget test at a STATED ceiling.

REQ-P4-UI-015 (NFR, Article VI) requires an 8K multi-layer recomposite to hold
``FRAME_BUDGET_MS`` (16 ms / 60 fps). ADR-0007 records that the 16 ms figure is
the *interactive render* budget, held by dirty-rect region scoping + cached
group buffers (D1/D4/D5), and that the CI regression gate for the
region-recomposite path is the deliberately looser, named
``COMPOSITE_REGION_CEILING_MS`` (200 ms — ~400x the measured p95, catching an
O(full-canvas) regression class without flaking on a noisy CI runner).

**Two-tier model (provisional, pending ruling D-21).** This test asserts the
SHIPPED region-recomposite path (``CanvasScene.refresh_rect``, ADR-0007's
``composite_stack(..., region=...)`` call) against the named
``COMPOSITE_REGION_CEILING_MS`` gate constant — the same tier
``scripts/perf_profile.py --composite`` uses — rather than the tighter 16 ms
interactive budget, because a UI-level pytest-qt run (import overhead, no
GPU/driver warm state, shared CI runner) is not the frame-profile harness
AGT-10 owns; a bare-literal millisecond number is never asserted here (S12 /
AGT-06 constitution: "NEVER produce a frame-time number" — this test QUOTES
the shipped constant, it does not invent one). Which tier is the CORRECT
default gate for a UI-level test is exactly the open question ruling D-21 is
expected to settle; until then this test uses the loose, already-shipped CI
tier so it holds without flaking.
"""

from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QRectF

from pixelart_creator.logic.constants import COMPOSITE_REGION_CEILING_MS
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.theme import canvas_roles

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]

#: A modest viewport region + a realistic multi-layer stack (>= 8 layers) — a
#: mechanism proof of the region-scoped recomposite contract, not a full 8K
#: exercise (AGT-10's frame-profile owns the measured 8K number).
_REGION_W = 256
_REGION_H = 256
_LAYERS = 8


def test_t18_region_recomposite_holds_the_named_ceiling(qtbot, theme):
    """REQ-P4-UI-015 (T-18): ``refresh_rect`` over a modest region holds
    ``COMPOSITE_REGION_CEILING_MS`` — the shipped region-scoped recomposite
    path (ADR-0007 D1: a region call allocates only the region, not the whole
    canvas), driven through the real UI-facing entry point.
    """
    doc = Document(_REGION_W * 4, _REGION_H * 4, palette=Palette(STARTER))
    for i in range(_LAYERS - 1):
        doc.add_layer(f"L{i + 1}")
    rng = np.random.default_rng(3)
    for node in doc.frames[0].layers:
        node.buffer.data[:] = rng.integers(
            0, 256, size=node.buffer.data.shape, dtype=np.uint8
        )

    scene = CanvasScene(doc)
    scene.set_background_roles(*canvas_roles(theme))
    scene._ensure_composite()

    region = QRectF(10, 10, _REGION_W, _REGION_H)
    start = time.perf_counter()
    scene.refresh_rect(region)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert elapsed_ms < COMPOSITE_REGION_CEILING_MS
