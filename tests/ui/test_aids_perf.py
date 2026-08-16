"""T-26 (AGT-06 audit) — bounded overlay-render timing (REQ-P9-UI-011).

The Phase-9 render-budget matrix names ``tests/ui/test_aids_perf.py`` as the
UI-level overlay-render timing module; until now the file did not exist. This
drives the REAL shipped :class:`~pixelart_creator.ui.iso_grid_overlay.Iso_Grid_Overlay`
``paint()`` (the same code path :mod:`scripts.perf_profile`'s ``--overlay``
mode measures) over a worst-case dense, fully-exposed rect and asserts against
the NAMED shipped CI-gate constant ``OVERLAY_FRAME_CEILING_MS`` — never a bare
literal or an invented number (S12 / AGT-06 constitution).

**Two-tier model (provisional, pending ruling D-21).** As in
``test_composite_region_perf.py`` (T-18) and ``test_opacity_drag.py``, the
16 ms ``FRAME_BUDGET_MS`` is the correct INTERACTIVE render budget (AGT-10's
frame-profile owns that measurement); this UI-level pytest-qt test instead
asserts the looser, already-shipped CI regression gate
(``OVERLAY_FRAME_CEILING_MS`` = 48 ms) that ``perf_profile.py --overlay``
uses, because a pytest-qt process is not the dedicated profiling harness.
Which tier a UI-level test should assert against is exactly what ruling D-21
is expected to settle.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QStyleOptionGraphicsItem

from pixelart_creator.logic.constants import OVERLAY_FRAME_CEILING_MS
from pixelart_creator.logic.grids import IsoGridConfig
from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay

#: A dense, on-screen tile edge (comfortably above ``ISO_GRID_MIN_ON_SCREEN_EDGE_PX``
#: so the LOD paint-skip gate never engages — the worst-case "many lines drawn"
#: frame the ceiling must hold).
_TILE_WIDTH = 32
_SCALE = 2.0
_VIEWPORT = 800
_WARMUP = 2
_SAMPLES = 3


def test_t26_iso_overlay_paint_holds_the_named_overlay_ceiling(qtbot, theme):
    """REQ-P9-UI-011 (T-26): a dense, fully-exposed iso-grid overlay paint holds
    ``OVERLAY_FRAME_CEILING_MS`` — the real ``QGraphicsItem.paint()`` call, timed
    the same way ``scripts/perf_profile.py --overlay`` does (warm-up excluded,
    median of a few samples), against the shipped named ceiling constant."""
    overlay = Iso_Grid_Overlay(
        QRectF(0, 0, _VIEWPORT, _VIEWPORT), IsoGridConfig(tile_width=_TILE_WIDTH)
    )
    image = QImage(_VIEWPORT, _VIEWPORT, QImage.Format.Format_ARGB32_Premultiplied)
    option = QStyleOptionGraphicsItem()
    option.exposedRect = QRectF(0, 0, _VIEWPORT, _VIEWPORT)

    def _paint_once() -> float:
        painter = QPainter(image)
        painter.scale(_SCALE, _SCALE)
        start = time.perf_counter()
        overlay.paint(painter, option, None)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        painter.end()
        return elapsed_ms

    for _ in range(_WARMUP):
        _paint_once()

    samples = sorted(_paint_once() for _ in range(_SAMPLES))
    median_ms = samples[len(samples) // 2]

    assert median_ms < OVERLAY_FRAME_CEILING_MS
