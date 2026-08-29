"""T-26 (AGT-06 audit) — bounded overlay-render timing (REQ-P9-UI-011).

The Phase-9 render-budget matrix names ``tests/ui/test_aids_perf.py`` as the
UI-level overlay-render timing module; until now the file did not exist. This
drives the REAL shipped :class:`~pixelart_creator.ui.iso_grid_overlay.Iso_Grid_Overlay`
``paint()`` (the same code PATH — not the same statistic, see the sampling
note below — :mod:`scripts.perf_profile`'s ``--overlay`` mode measures) over a
worst-case dense, fully-exposed rect and asserts against the NAMED shipped
CI-gate constant ``OVERLAY_FRAME_CEILING_MS`` — never a bare literal or an
invented number (S12 / AGT-06 constitution).

**Two-tier model (provisional, pending ruling D-21).** As in
``test_composite_region_perf.py`` (T-18) and ``test_opacity_drag.py``, the
16 ms ``FRAME_BUDGET_MS`` is the correct INTERACTIVE render budget (AGT-10's
frame-profile owns that measurement); this UI-level pytest-qt test instead
asserts the looser, already-shipped CI regression gate
(``OVERLAY_FRAME_CEILING_MS`` = 48 ms) that ``perf_profile.py --overlay``
uses, because a pytest-qt process is not the dedicated profiling harness.
Which tier a UI-level test should assert against is exactly what ruling D-21
is expected to settle.

**Sampling fix (DEV-21, found 2026-08-18 to 2026-08-20).** This test already
did warm-up + median-of-3 and it was NOT enough: it failed CI at
``50.75 ms`` against the 48 ms ceiling (+5.7 %) under measured shared
self-hosted-runner contention (suite duration 671 s against a 275-340 s quiet
baseline), then passed clean on an identical-commit re-run once the runner
was quiet. A quiet-machine probe of this exact scenario at the time of this
fix showed per-call cost of roughly 0.9-2.6 ms — i.e. the failing 50.75 ms
median was not a modest overrun of a tight budget, it reflects at least two
of the three samples landing inside a multi-millisecond scheduler stall.
Median-of-3 cannot filter that out: if 2 of 3 draws are stalled the median
IS a stalled draw. Trimmed mean has the identical problem at N=3 (nothing
left to trim without discarding real data), and "just raise N and keep the
median" does not help either as long as the stall recurs across most of the
sampling window, which is what a SUSTAINED (not transient) contention episode
does by definition.

The fix is warm-up + **minimum-of-N** (``_SAMPLES`` raised from 3 to 7, cost
is negligible at ~1-3 ms/sample): for a CEILING assertion the minimum is the
principled statistic because contention only ever adds latency, never removes
it, so the minimum sample is the best available estimate of the paint's true
uncontended cost, and a genuine regression would raise the cost floor itself
— raising every sample including the minimum — so detection is not weakened.
This was proved empirically at the time of this fix: an artificial
``time.sleep`` injected into the timed ``paint()`` call made this assertion
fail; removing it made it pass again (see the DEV-21 handoff notes for the
paired exit codes).

This diverges from ``scripts/perf_profile.py``'s own module docstring, which
declares its pass/fail rule "median <= budget" FIXED (its CP1 note) for the
modes AGT-10 owns as the frame-budget MEASUREMENT instrument — that rule is
UNCHANGED here and ``perf_profile.py`` is not edited by this fix. AGT-10's
harness is invoked deliberately on a quiet machine to produce a trustworthy
number; this file is a CI regression GATE that runs unattended on a shared
runner and must hold under the load that instrument is never exposed to.
``OVERLAY_FRAME_CEILING_MS`` is NOT relaxed by this change — same 48 ms
constant, same source of truth.
"""

from __future__ import annotations

import sys
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
_SAMPLES = 7  # DEV-21: raised from 3; min-of-N replaces median-of-N (module docstring)


def test_t26_iso_overlay_paint_holds_the_named_overlay_ceiling(qtbot, theme):
    """REQ-P9-UI-011 (T-26): a dense, fully-exposed iso-grid overlay paint holds
    ``OVERLAY_FRAME_CEILING_MS`` — the real ``QGraphicsItem.paint()`` call,
    warm-up excluded, asserted against the MINIMUM of ``_SAMPLES`` timed
    calls (module docstring's DEV-21 note — this diverges from
    ``scripts/perf_profile.py --overlay``'s own fixed median rule, and says
    so there)."""
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

    samples = [_paint_once() for _ in range(_SAMPLES)]
    min_ms = min(samples)
    sys.stderr.write(
        "test_t26_iso_overlay_paint: samples_ms=%s min_ms=%.3f ceiling_ms=%.1f\n"
        % ([round(s, 3) for s in samples], min_ms, OVERLAY_FRAME_CEILING_MS)
    )
    assert min_ms < OVERLAY_FRAME_CEILING_MS, (
        f"min of {_SAMPLES} overlay-paint samples {min_ms:.3f} ms "
        f">= ceiling {OVERLAY_FRAME_CEILING_MS} ms "
        f"(all samples ms: {[round(s, 3) for s in samples]})"
    )
