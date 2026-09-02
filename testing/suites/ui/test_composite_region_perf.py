"""REQ-P4-UI-015 budget test at a STATED ceiling.

REQ-P4-UI-015 (NFR, Article VI) requires an 8K multi-layer recomposite to hold
``FRAME_BUDGET_MS`` (16 ms / 60 fps). ADR-0007 records that the 16 ms figure is
the *interactive render* budget, held by dirty-rect region scoping + cached
group buffers (D1/D4/D5), and that the CI regression gate for the
region-recomposite path is the deliberately looser, named
``COMPOSITE_REGION_CEILING_MS`` (200 ms — ~400x the measured p95 of
``scripts/perf_profile.py``'s own default 16 px-region scenario; this test's
own quiet-machine baseline over its larger 256x256 region is ~73-83 ms, still
2.4-2.7x of headroom — catching an O(full-canvas) regression class without
flaking on a noisy CI runner).

**Two-tier model (provisional, pending ruling D-21).** This test asserts the
SHIPPED region-recomposite path (``CanvasScene.refresh_rect``, ADR-0007's
``composite_stack(..., region=...)`` call) against the named
``COMPOSITE_REGION_CEILING_MS`` gate constant — the same tier
``scripts/perf_profile.py --composite`` uses — rather than the tighter 16 ms
interactive budget, because a UI-level pytest-qt run (import overhead, no
GPU/driver warm state, shared CI runner) is not the frame-profile harness
the performance work owns; a bare-literal millisecond number is never asserted here (S12 /
this suite's constitution: "NEVER produce a frame-time number" — this test QUOTES
the shipped constant, it does not invent one). Which tier is the CORRECT
default gate for a UI-level test is exactly the open question ruling D-21 is
expected to settle; until then this test uses the loose, already-shipped CI
tier so it holds without flaking.

**Sampling fix (found 2026-08-18 to 2026-08-20).** This test was
previously a SINGLE cold ``time.perf_counter()`` call with no warm-up and no
repetition. It failed CI twice under measured shared self-hosted-runner
contention (suite duration 442-671 s against a 275-340 s quiet baseline — the
runner shares one physical machine with local work, so a neighbour process is
indistinguishable to a single-shot timer from a real regression):
``239.09 ms`` and (a companion test's, same class, same runner)
``50.75 ms`` / 48 ms ceiling, both re-running GREEN on the identical commit
once the machine was quiet. A median-of-N alone does not fix this: under
SUSTAINED contention (not a transient spike) every sample in the window is
slow, so the median is inflated right along with the mean — evidenced
directly by the sibling overlay test, which already ran a
median-of-3 and still failed at +5.7 %.

The fix taken here is warm-up + **minimum-of-N**, not median-of-N, because
this is a CEILING assertion, not a two-sided regression band: contention can
only make ``refresh_rect`` slower than its true cost, never faster, so the
minimum observed sample is the best available estimate of the UNCONTENDED
cost. A genuine regression (a real algorithmic slowdown) raises the cost
floor itself, so it raises EVERY sample including the minimum — the gate's
ability to catch a real regression is therefore preserved, not weakened
(proved empirically at the time this fix was written: an artificial
``time.sleep`` injected into the timed path failed this exact assertion,
removing it passed again). Trimmed mean and "just sample more and take the
median" were considered and rejected: both still average across a mix of
contended and uncontended samples, so both stay inflated for as long as the
contention itself lasts, which the evidence above shows can span an entire
671 s suite run — they buy nothing a plain median-of-N did not already buy,
which that sibling failure shows is not enough.

This diverges from ``scripts/perf_profile.py``'s own module docstring, which
declares its pass/fail rule "median <= budget" FIXED (its CP1 note) for the
tiling/composite/full-frame profiling modes the performance work owns as the frame-budget
MEASUREMENT instrument. That rule is UNCHANGED and this file does not touch
it — ``perf_profile.py`` is not edited by this fix. The two live under
different constraints: perf_profile.py is invoked deliberately, on a quiet
machine, by that dedicated harness, expressly to produce a trustworthy frame-time number;
this file is a CI regression GATE that runs unattended, every push, on a
shared runner, and needs to hold under exactly the kind of transient load
perf_profile.py is never run under. COMPOSITE_REGION_CEILING_MS is NOT
relaxed by this change — same 200 ms constant, same source of truth.
"""

from __future__ import annotations

import sys
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
#: exercise (the performance work's frame-profile owns the measured 8K number).
_REGION_W = 256
_REGION_H = 256
_LAYERS = 8

#: Sampling fix. ``_WARMUP`` calls are timed and discarded (pay the
#: scene's one-time compositor state once); ``_SAMPLES`` timed calls feed the
#: MINIMUM statistic below (module docstring). Both counts are small on
#: purpose: this scenario's per-call cost is tens of ms (~73-83 ms quiet
#: baseline), so ``_WARMUP + _SAMPLES`` calls stay well under a second added
#: to the suite while giving the minimum several draws to find a clean one.
_WARMUP = 2
_SAMPLES = 5


def test_t18_region_recomposite_holds_the_named_ceiling(qtbot, theme):
    """REQ-P4-UI-015: ``refresh_rect`` over a modest region holds
    ``COMPOSITE_REGION_CEILING_MS`` — the shipped region-scoped recomposite
    path (ADR-0007 D1: a region call allocates only the region, not the whole
    canvas), driven through the real UI-facing entry point.

    Asserted against the MINIMUM of ``_SAMPLES`` timed calls (``_WARMUP``
    discarded first), not a single cold call and not a median — see the
    module docstring's sampling note for why minimum is the correct statistic
    for a ceiling assertion running on a contended shared CI runner.
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

    # Fixed region reused for every sample — deliberately NOT origin-varied
    # like scripts/perf_profile.py's --composite mode. That mode moves the
    # region origin every frame to keep blend._flatten_group's single-entry
    # MRU cache cold. This scenario has no GROUP nodes at all (Document.
    # add_layer above appends plain Layer nodes only), so that cache is never
    # engaged here and a fixed region measures the same uncached cost on
    # every call — confirmed by a 15-sample probe on a quiet machine showing
    # no downward trend across repeats (range ~73-83 ms throughout).
    region = QRectF(10, 10, _REGION_W, _REGION_H)

    for _ in range(_WARMUP):
        scene.refresh_rect(region)

    samples = []
    for _ in range(_SAMPLES):
        start = time.perf_counter()
        scene.refresh_rect(region)
        samples.append((time.perf_counter() - start) * 1000.0)

    min_ms = min(samples)
    sys.stderr.write(
        "test_t18_region_recomposite: samples_ms=%s min_ms=%.3f ceiling_ms=%.1f\n"
        % ([round(s, 3) for s in samples], min_ms, COMPOSITE_REGION_CEILING_MS)
    )
    assert min_ms < COMPOSITE_REGION_CEILING_MS, (
        f"min of {_SAMPLES} region-recomposite samples {min_ms:.3f} ms "
        f">= ceiling {COMPOSITE_REGION_CEILING_MS} ms "
        f"(all samples ms: {[round(s, 3) for s in samples]})"
    )
