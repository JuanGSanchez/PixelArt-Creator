"""Opacity-drag preview + byte-exact commit UI acceptance tests (Phase-12 Slice B).

One pytest-qt test per acceptance criterion of the FU-16b opacity-drag / low-zoom
viewport recomposite interaction (``specs/phase-12-performance-scalability``:
REQ-P12-UI-001, and REQ-P12-LOGIC-004's commit-byte-exactness *observed from the
UI*), driving the PySide6 canvas + layer panel headlessly
(``QT_QPA_PLATFORM=offscreen``, forced in ``conftest``). Every test also runs under
**both** themes via the autouse ``theme`` fixture (the global light/dark rule +
REQ-P12-UI-001 "both themes behave identically").

Grounded in ADR-0034 (incl. the 2026-07-07 amendment) and the performance work's Slice-B
directive ``docs/perf/phase12-sliceB-directive.md``. Bindings under test (shipped):

- ``CanvasScene.begin_opacity_drag`` builds the drag-scoped ``_OpacityDragCache``
  (three NN-downsampled LOD inputs bounded to ``OPACITY_PREVIEW_MAX_PX``) and
  rebinds the throttled per-tick action ``_live_recomposite_fn`` to
  ``_preview_opacity_drag`` — the bounded-LOD preview path, NOT a full recomposite.
- The throttled tick reuses the shipped 16 ms ``_live_timer`` (no new thread), so
  the Phase-5 drain contract is unchanged (``shutdown_prewarm`` drops the cache).
- On slider release the one opacity ``LayerCommand``'s redo drives
  ``refresh_visible`` which, with a drag live, takes ``_commit_opacity_drag`` — the
  ALWAYS-correct suffix re-blend ``composite_range(nodes, k, N, base=below_full)``,
  byte-identical to ``composite_stack`` over the region for NORMAL *and* all 11
  separable modes (the ADR amendment: NOT the ``above``-pre-flatten fast path,
  which can diverge <= 2 LSB on partial-alpha content).

Scope note: these are UI/integration tests. The pure-logic byte-exactness
of ``composite_range`` across all modes + the perf gate are the logic suite's logic tests;
here we assert the *wired UI lifecycle* (preview path engaged + bounded, commit
byte-exact from the panel, cache invalidation, a11y) — one per acceptance criterion.

Scale-ceiling clause note (2026-07-30): the scale-ceiling clause requires byte-exact viewport
recomposite "up to 1920x1920, >= 12 layers". Every byte-exact test above this note
runs at 300x300/12 layers (a mechanism proof, not the clause's own scale). The
clause's literal ceiling is covered by ONE opt-in, ``slow``-marked test further
down (``test_commit_byte_exact_at_1920_scale_12_layers_opt_in``) — env-gated by
``PIXELART_OPACITY_SCALE_TEST=1`` and deselected by CI's default
``-m "not slow and ..."`` gate, the same double-gate convention already used by
``testing/suites/deploy/test_nginx_wss_localhost.py`` / ``test_vps_localhost.py``, because
a full 1920x1920x12-layer commit costs tens of seconds of vectorised NumPy work
per theme instance — too slow to run on every default invocation of this file.
"""

from __future__ import annotations

import os
import time
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.blend import (
    BlendMode,
    blend_arrays,
    composite_range,
    composite_stack,
    is_range_source_over,
)
from pixelart_creator.logic.constants import FRAME_BUDGET_MS, OPACITY_PREVIEW_MAX_PX
from pixelart_creator.logic.document import Document, Layer
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.layer_panel import Layer_Panel
from pixelart_creator.ui.theme import canvas_roles

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]

#: Canvas size chosen so the fully-visible viewport region (area 300*300 = 90 000 px)
#: exceeds OPACITY_PREVIEW_MAX_PX (16 384, R-37 correction — was mis-stated as
#: 65 536 here), forcing an LOD factor > 1 — a GENUINE downsample branch,
#: distinguishing the bounded-LOD preview from a full recomposite.
_W = 300
_H = 300
#: Many-layer stack (>= 12) — the FU-16b modelled case (baseline 2.2-7 s cache-cold).
_LAYERS = 12

#: The scale-ceiling clause's own scale ceiling ("byte-exact viewport recomposite up to 1920x1920,
#: >= 12 layers"). Measured at ~50-90 s for the two theme-parametrised invocations
#: (see test docstring below), so it is opt-in (env-gated + ``slow``-marked, the
#: SAME double-gate convention as ``testing/suites/deploy/test_nginx_wss_localhost.py`` and
#: ``testing/suites/deploy/test_vps_localhost.py``) rather than part of the default gate.
_SCALE_ENV_VAR = "PIXELART_OPACITY_SCALE_TEST"
_SCALE_W = 1920
_SCALE_H = 1920
_SCALE_LAYERS = 12


def _fill_layers(nodes, *, partial_alpha: bool, seed: int) -> None:
    """Fill each layer buffer with deterministic distinct RGBA content.

    ``partial_alpha`` seeds fractional alpha (the case where the ``above``
    pre-flatten fast path can diverge <= 2 LSB, so the byte-exact commit must use
    the suffix re-blend). Hard-edged (alpha in {0, 255}) otherwise (the pixel-art
    norm). Deterministic per ``seed`` (P2 / portability).
    """
    rng = np.random.default_rng(seed)
    for node in nodes:
        data = node.buffer.data
        data[:] = rng.integers(0, 256, size=data.shape, dtype=np.uint8)
        if partial_alpha:
            data[:, :, 3] = rng.integers(1, 255, size=data.shape[:2], dtype=np.uint8)
        else:
            # Hard-edged alpha: a deterministic 0/255 mask (sparse-ish coverage).
            data[:, :, 3] = np.where(
                rng.integers(0, 4, size=data.shape[:2]) == 0, 0, 255
            ).astype(np.uint8)


def _make_env(
    qtbot,
    theme,
    *,
    layers: int = _LAYERS,
    partial_alpha: bool = False,
    seed: int = 11,
    non_normal_above: bool = False,
    k: int = 6,
    width: int = _W,
    height: int = _H,
    show: bool = False,
):
    """Wire a ``CanvasScene`` + full-canvas viewport + ``Layer_Panel`` for a drag.

    Mirrors ``Main_Window``'s per-tab wiring: the panel's ``sliderPressed`` builds
    the scene split-cache (``on_opacity_drag_begin=scene.begin_opacity_drag``), the
    live drag calls the throttled preview, and the release commit pushes one
    ``LayerCommand`` whose redo recomposites byte-exact. The view is resized so the
    whole canvas is the culled viewport region ``V`` (a genuine LOD factor > 1).
    ``width``/``height`` default to the module's ``_W``/``_H`` (300x300) so every
    existing call site is unaffected; a caller may pass a larger canvas (e.g. the
    the scale-ceiling clause's opt-in scale test) without changing the default env for any other test.
    ``show`` defaults to ``False`` (existing behaviour, unshown widget): an UNSHOWN
    ``QGraphicsView``'s viewport keeps a fixed initial layout size on this Qt build
    (observed 624x464 under the offscreen platform) regardless of ``resize()``, which
    silently under-covers a canvas larger than that — harmless at the 300x300 default
    (well within 624x464) but wrong at 1920x1920, so the scale test passes
    ``show=True`` to force the real layout pass; every other call site is unaffected.
    Returns a namespace ``(doc, scene, view, stack, panel, nodes, k)``.
    """
    doc = Document(width, height, palette=Palette(STARTER))
    for i in range(layers - 1):
        doc.add_layer(f"L{i + 1}")
    nodes = doc.frames[0].layers
    assert len(nodes) == layers
    _fill_layers(nodes, partial_alpha=partial_alpha, seed=seed)
    if non_normal_above:
        # An ABOVE layer in a non-normal separable mode: is_range_source_over(above)
        # is False, so the byte-exact commit CANNOT use the above-pre-flatten fast
        # path and must take the exact suffix re-blend.
        nodes[k + 2].blend_mode = BlendMode.MULTIPLY

    scene = CanvasScene(doc)
    scene.set_background_roles(*canvas_roles(theme))
    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    view.resetTransform()
    view._zoom = 1.0
    view.resize(width + 60, height + 60)
    if show:
        view.show()
    view.horizontalScrollBar().setValue(0)
    view.verticalScrollBar().setValue(0)

    panel = Layer_Panel()
    qtbot.addWidget(panel)

    def _on_active(node):
        if isinstance(node, Layer):
            scene.set_active_layer(node)

    panel.activeNodeChanged.connect(_on_active)
    panel.set_context(
        doc,
        stack,
        scene.refresh_all,
        scene.refresh_visible,
        scene.refresh_visible_throttled,
        scene.begin_opacity_drag,
    )
    scene._ensure_composite()
    # Precondition for the whole feature: a live viewport spanning the canvas.
    assert scene._clamp_visible_region() == (0, 0, width, height)
    return SimpleNamespace(
        doc=doc, scene=scene, view=view, stack=stack, panel=panel, nodes=nodes, k=k
    )


def _region_ref(
    nodes, region=(0, 0, _W, _H), *, width: int = _W, height: int = _H
) -> np.ndarray:
    """Authoritative "current build" composite over ``region`` (byte-exact target).

    ``composite_stack(region=...)`` is the shipped compositor the commit must match
    byte-for-byte (REQ-P12-LOGIC-004 / ADR-0034 §3). ``width``/``height`` default to
    the module's ``_W``/``_H`` (300x300, matching every existing call site's default
    ``region``); the scale-ceiling clause's scale test passes its own 1920x1920 canvas size.
    """
    return composite_stack(nodes, width, height, region=region).data


def _top_row(panel: Layer_Panel, k: int):
    """Return the panel's ``_Node_Row`` for the top-level node at index ``k``."""
    for row in panel._rows:
        if tuple(row.path()) == (k,):
            return row
    raise AssertionError(f"no top-level row for index {k}")


# --------------------------------------------------------------------------- #
# SC-P12-UI-001-1 — preview holds the frame budget via the bounded-LOD path    #
# --------------------------------------------------------------------------- #


def test_preview_uses_bounded_lod_path_not_full_recomposite(qtbot, theme):
    """The drag preview goes through the bounded-LOD branch, not a full recomposite.

    Asserts the MECHANISM (per the directive: prefer branch/mechanism over a flaky
    wall-clock): begin_opacity_drag rebinds the throttled per-tick action to
    ``_preview_opacity_drag`` (NOT the full ``refresh_visible``), the LOD factor is
    > 1 (a genuine downsample), and each cached working set is bounded to
    ``OPACITY_PREVIEW_MAX_PX`` — so a per-tick re-blend is ~2 blends over a tiny
    buffer, holding the 16 ms budget with headroom (SC-P12-UI-001-1). A single very
    loose wall-clock ceiling guards against a gross freeze (not a tight 16 ms bound).
    """
    env = _make_env(qtbot, theme)
    scene, k = env.scene, env.k

    assert scene._live_recomposite_fn == scene.refresh_visible  # naive before drag
    assert scene.begin_opacity_drag([k]) is True
    cache = scene._opacity_drag
    assert cache is not None

    # Rebound to the bounded-LOD preview path — NOT the full-stack recomposite.
    assert scene._live_recomposite_fn == scene._preview_opacity_drag

    # Genuine LOD downsample (factor > 1) for this whole-viewport region.
    assert cache.factor > 1
    region_area = _W * _H
    for buf in (cache.below_lod, cache.above_lod, cache.layer_lod):
        working = int(buf.shape[0]) * int(buf.shape[1])
        assert working <= OPACITY_PREVIEW_MAX_PX  # bounded per-tick working set
        assert working < region_area  # strictly downsampled (not full-res)

    # Drive a throttled preview tick (the shipped 16 ms _live_timer path) and time
    # it loosely — a catastrophic-freeze guard only, far above the true 16 ms cost.
    env.nodes[k].opacity = 0.35
    start = time.perf_counter()
    scene.refresh_visible_throttled()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert elapsed_ms < FRAME_BUDGET_MS * 60  # loose gross-freeze ceiling, not 16 ms


# --------------------------------------------------------------------------- #
# SC-P12-UI-001-2 / REQ-P12-LOGIC-004 — commit is byte-exact                    #
# --------------------------------------------------------------------------- #


def test_commit_byte_exact_realistic_all_normal(qtbot, theme):
    """A realistic all-NORMAL stack commits byte-exact vs the shipped compositor.

    After a drag + release-commit the resident composite over the viewport equals
    ``composite_stack`` over the same inputs byte-for-byte (REQ-P12-LOGIC-004,
    SC-P12-UI-001-2).
    """
    env = _make_env(qtbot, theme, partial_alpha=False, non_normal_above=False)
    scene, nodes, k = env.scene, env.nodes, env.k

    assert scene.begin_opacity_drag([k]) is True
    nodes[k].opacity = 0.5
    scene.refresh_visible_throttled()  # an approximate preview tick
    # Commit: final opacity fixed, then the drag-live refresh_visible commits exact.
    nodes[k].opacity = 0.5
    scene.refresh_visible()

    assert scene._opacity_drag is None  # cache discarded on commit
    ref = _region_ref(nodes)
    assert np.array_equal(scene._composite.data, ref)


def test_commit_byte_exact_partial_alpha_non_normal_above(qtbot, theme):
    """Commit stays byte-exact for partial-alpha content with a non-NORMAL above layer.

    THIS is the case the ``above``-pre-flatten fast path would get wrong (ADR-0034
    amendment): a partial-alpha stack with a MULTIPLY layer above the dragged index
    makes ``is_range_source_over(above)`` False, and even the all-source-over
    pre-flatten diverges <= 2 LSB on fractional alpha. The commit must use the exact
    suffix re-blend ``composite_range(nodes, k, N, base=below_full)`` — proven by:
    (1) the committed pixels equal ``composite_stack`` byte-for-byte, and
    (2) the pre-flatten fast path would NOT equal the reference (so exactness is not
    an accident of the content).
    """
    env = _make_env(qtbot, theme, partial_alpha=True, non_normal_above=True)
    scene, nodes, k = env.scene, env.nodes, env.k

    assert is_range_source_over(nodes[k + 1 :]) is False  # fast path ineligible

    assert scene.begin_opacity_drag([k]) is True
    nodes[k].opacity = 0.4
    scene.refresh_visible_throttled()
    nodes[k].opacity = 0.4
    scene.refresh_visible()

    ref = _region_ref(nodes)
    committed = scene._composite.data
    assert np.array_equal(committed, ref)  # byte-exact commit

    # Prove the commit is NOT the (divergent) above-pre-flatten fast path.
    region = (0, 0, _W, _H)
    below = composite_range(nodes, _W, _H, 0, k, region=region)
    lit = composite_range(nodes, _W, _H, k, k + 1, region=region, base=below.data)
    above_pf = composite_range(nodes, _W, _H, k + 1, len(nodes), region=region)
    fast = blend_arrays(BlendMode.NORMAL, above_pf.data, lit.data)
    assert not np.array_equal(fast, ref)  # fast path would diverge here


def test_commit_byte_exact_driven_by_slider_signals(qtbot, theme):
    """End-to-end UI wiring: slider press -> preview -> release commits byte-exact.

    Drives the real ``QSlider`` signals through the panel (setSliderDown emits
    sliderPressed/sliderReleased): press builds the split-cache, a value change
    renders the LOD preview (isSliderDown so no commit), release pushes exactly one
    ``LayerCommand`` whose redo commits the byte-exact full-resolution recomposite.
    Proves REQ-P12-UI-001's observable contract from the panel, not just the scene API.
    """
    env = _make_env(qtbot, theme, partial_alpha=True, non_normal_above=True)
    scene, nodes, stack, panel, k = env.scene, env.nodes, env.stack, env.panel, env.k

    slider = _top_row(panel, k)._opacity

    slider.setSliderDown(True)  # -> sliderPressed -> begin_opacity_drag
    assert scene._opacity_drag is not None
    assert scene._live_recomposite_fn == scene._preview_opacity_drag

    slider.setValue(40)  # -> valueChanged -> throttled LOD preview (still dragging)
    assert scene._opacity_drag is not None  # not committed mid-drag

    slider.setSliderDown(False)  # -> sliderReleased -> commit
    assert scene._opacity_drag is None
    assert scene._live_recomposite_fn == scene.refresh_visible  # naive restored
    assert stack.count() == 1  # exactly one undoable opacity command
    assert nodes[k].opacity == pytest.approx(0.40)

    ref = _region_ref(nodes)
    assert np.array_equal(scene._composite.data, ref)


def test_commit_is_deterministic(qtbot, theme):
    """Two identical drags to the same final opacity commit byte-identical results."""
    env = _make_env(qtbot, theme, partial_alpha=True, non_normal_above=True)
    scene, nodes, k = env.scene, env.nodes, env.k

    scene.begin_opacity_drag([k])
    nodes[k].opacity = 0.3
    scene.refresh_visible()
    first = scene._composite.data.copy()

    scene.begin_opacity_drag([k])
    nodes[k].opacity = 0.3
    scene.refresh_visible()
    second = scene._composite.data

    assert np.array_equal(first, second)


# --------------------------------------------------------------------------- #
# The scale-ceiling clause — byte-exact commit at its OWN scale ceiling (opt-in, slow) #
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_commit_byte_exact_at_1920_scale_12_layers_opt_in(qtbot, theme):
    """The scale-ceiling clause: byte-exact viewport recomposite AT its own stated scale.

    Every other byte-exact test in this module runs at 300x300/12 layers — a
    correctness proof of the *mechanism*, not of the scale-ceiling clause itself
    ("byte-exact viewport recomposite up to 1920x1920, >= 12 layers"). This test
    exercises the identical commit path
    (``begin_opacity_drag`` -> live opacity change -> ``refresh_visible`` commit)
    at the task's own literal ceiling and asserts the committed pixels equal
    ``composite_stack`` byte-for-byte over the full 1920x1920 region, with 12
    layers, hard-edged (pixel-art-norm) alpha, all-NORMAL blend mode.

    Opt-in (env var + ``slow`` marker, deselected by CI's default
    ``-m "not slow and ..."`` gate, mirroring
    ``testing/suites/deploy/test_nginx_wss_localhost.py``'s idle-past-60s test and
    ``testing/suites/deploy/test_vps_localhost.py``'s Docker path): a single commit
    at this scale costs several seconds of vectorised NumPy work (measured
    locally, Python 3.13.13 / PySide6 6.11.1 / offscreen: ~24 s per theme
    instance, ~48 s for both together — see the QA report for the exact
    command + output), and this suite runs under both light AND dark automatically (the
    autouse ``theme`` fixture) — a bad trade for the DEFAULT gate to pay on
    every run just to prove one documentation clause. It is genuinely GREEN
    when opted in, so the clause is verified at scale on demand, not merely
    claimed.

    Set ``PIXELART_OPACITY_SCALE_TEST=1`` to run it:
        QT_QPA_PLATFORM=offscreen PIXELART_OPACITY_SCALE_TEST=1 \\
            python -m pytest testing/suites/ui/test_opacity_drag.py \\
            -k test_commit_byte_exact_at_1920_scale_12_layers_opt_in -m slow -q
    """
    if os.environ.get(_SCALE_ENV_VAR) != "1":
        pytest.skip(f"opt-in slow test; set {_SCALE_ENV_VAR}=1 to run it")

    env = _make_env(
        qtbot,
        theme,
        layers=_SCALE_LAYERS,
        partial_alpha=False,
        non_normal_above=False,
        width=_SCALE_W,
        height=_SCALE_H,
        show=True,  # force the real viewport layout at 1920x1920 (see _make_env)
    )
    scene, nodes, k = env.scene, env.nodes, env.k

    assert scene.begin_opacity_drag([k]) is True
    nodes[k].opacity = 0.5
    # Commit directly (skip the LOD preview tick — already proven at 300x300 by
    # test_preview_uses_bounded_lod_path_not_full_recomposite; this test's only
    # job is the commit's byte-exactness AT SCALE, not the preview mechanism).
    scene.refresh_visible()

    assert scene._opacity_drag is None  # cache discarded on commit
    ref = _region_ref(
        nodes,
        region=(0, 0, _SCALE_W, _SCALE_H),
        width=_SCALE_W,
        height=_SCALE_H,
    )
    assert np.array_equal(scene._composite.data, ref)


# --------------------------------------------------------------------------- #
# 16 ms per-tick preview assertion AT >= 1080^2 (opt-in)                       #
# --------------------------------------------------------------------------- #

#: This clause's own scale floor ("16 ms per-tick opacity-drag preview ... at >= 1080^2").
#: OPACITY_PREVIEW_MAX_PX's own docstring grounds the preview holding 16 ms "up
#: to ~1080-1280^2 viewports on the 2-core runner" — this test exercises that
#: literal floor. Same double-gate opt-in convention as
#: ``test_commit_byte_exact_at_1920_scale_12_layers_opt_in`` above: a shared CI
#: runner is too noisy for an UNCONDITIONAL tight 16 ms assertion to hold without
#: flaking, so this is deliberately NOT part of the default gate.
_TICK_ENV_VAR = "PIXELART_OPACITY_TICK_TEST"
_TICK_EDGE = 1080


@pytest.mark.slow
def test_per_tick_preview_holds_16ms_at_1080_squared_opt_in(qtbot, theme):
    """A single throttled preview tick, at the literal >= 1080^2 floor,
    holds ``FRAME_BUDGET_MS`` (16 ms).

    **Two-tier model (provisional, pending ruling D-21).** ``FRAME_BUDGET_MS``
    is the correct INTERACTIVE budget for this exact path (``OPACITY_PREVIEW_MAX_PX``
    was sized precisely so the bounded-LOD preview holds it up to ~1080-1280^2 —
    see that constant's docstring); asserting the tight 16 ms bound (rather than
    a loose CI-gate constant like ``COMPOSITE_REGION_CEILING_MS``) is deliberate
    here because that IS this path's own designed contract. It is still opt-in
    (env var + ``slow`` marker) because a single tick on a shared, noisy 2-core CI
    runner is not the dedicated frame-profile harness (the performance work owns that
    measurement) and a bare per-test wall-clock assertion at exactly the design
    edge would flake there; run explicitly to verify the contract on demand.

    Set ``PIXELART_OPACITY_TICK_TEST=1`` to run it:
        QT_QPA_PLATFORM=offscreen PIXELART_OPACITY_TICK_TEST=1 \\
            python -m pytest testing/suites/ui/test_opacity_drag.py \\
            -k test_per_tick_preview_holds_16ms_at_1080_squared_opt_in -m slow -q
    """
    if os.environ.get(_TICK_ENV_VAR) != "1":
        pytest.skip(f"opt-in slow test; set {_TICK_ENV_VAR}=1 to run it")

    env = _make_env(
        qtbot,
        theme,
        layers=_LAYERS,
        partial_alpha=False,
        non_normal_above=False,
        width=_TICK_EDGE,
        height=_TICK_EDGE,
        show=True,
    )
    scene, nodes, k = env.scene, env.nodes, env.k

    assert scene.begin_opacity_drag([k]) is True
    cache = scene._opacity_drag
    assert cache is not None
    for buf in (cache.below_lod, cache.above_lod, cache.layer_lod):
        assert int(buf.shape[0]) * int(buf.shape[1]) <= OPACITY_PREVIEW_MAX_PX

    nodes[k].opacity = 0.42
    # Warm-up tick excluded (first-call overhead), mirroring perf_profile.py.
    scene.refresh_visible_throttled()
    nodes[k].opacity = 0.43
    start = time.perf_counter()
    scene.refresh_visible_throttled()
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert elapsed_ms < FRAME_BUDGET_MS


# --------------------------------------------------------------------------- #
# Preview-vs-commit transition — approximate during drag, exact on commit      #
# --------------------------------------------------------------------------- #


def test_preview_approximate_then_commit_exact_transition(qtbot, theme):
    """The during-drag preview is approximate (LOD); the committed result is exact.

    With high-frequency content and factor > 1, the NN-subsampled preview loses
    detail, so the displayed preview differs from the exact composite; the release
    commit then overwrites it byte-exact (SC-P12-UI-001-2, the observable transition).
    """
    env = _make_env(qtbot, theme, partial_alpha=True, seed=23)
    scene, nodes, k = env.scene, env.nodes, env.k

    assert scene.begin_opacity_drag([k]) is True
    assert scene._opacity_drag.factor > 1  # LOD in effect -> preview is approximate
    nodes[k].opacity = 0.45
    scene.refresh_visible_throttled()
    preview = scene._composite.data.copy()

    ref = _region_ref(nodes)
    assert not np.array_equal(preview, ref)  # preview is a deliberate approximation

    nodes[k].opacity = 0.45
    scene.refresh_visible()  # commit
    assert np.array_equal(scene._composite.data, ref)  # exact after commit


# --------------------------------------------------------------------------- #
# Cache invalidation (ADR-0034 §2.3) — no stale preview persists               #
# --------------------------------------------------------------------------- #


def test_drag_cache_discarded_on_commit(qtbot, theme):
    """Slider release / commit discards the drag cache and restores the naive path."""
    env = _make_env(qtbot, theme)
    scene, nodes, k = env.scene, env.nodes, env.k
    scene.begin_opacity_drag([k])
    assert scene._opacity_drag is not None
    nodes[k].opacity = 0.6
    scene.refresh_visible()
    assert scene._opacity_drag is None
    assert scene._live_recomposite_fn == scene.refresh_visible


def test_drag_cache_invalidated_on_pan_zoom(qtbot, theme):
    """A pan/zoom (recomposite_exposed) invalidates the drag cache; no stale preview.

    After a preview tick writes the approximate LOD into the resident composite, a
    pan invalidates the cache; the next naive recomposite yields byte-exact pixels
    (the stale preview does not survive the following op).
    """
    env = _make_env(qtbot, theme)
    scene, nodes, k = env.scene, env.nodes, env.k
    scene.begin_opacity_drag([k])
    nodes[k].opacity = 0.5
    scene.refresh_visible_throttled()  # approximate preview now resident

    scene.recomposite_exposed()  # pan/zoom follow-up -> cancel_opacity_drag
    assert scene._opacity_drag is None
    assert scene._live_recomposite_fn == scene.refresh_visible

    # A subsequent naive op is correct — no stale LOD preview persists.
    scene.refresh_visible()
    assert np.array_equal(scene._composite.data, _region_ref(nodes))


def test_drag_cache_invalidated_on_edit(qtbot, theme):
    """A pixel edit (refresh_rect) invalidates the drag cache (ADR-0034 §2.3)."""
    env = _make_env(qtbot, theme)
    scene, k = env.scene, env.k
    scene.begin_opacity_drag([k])
    assert scene._opacity_drag is not None
    from PySide6.QtCore import QRectF

    scene.refresh_rect(QRectF(0, 0, _W, _H))
    assert scene._opacity_drag is None
    assert scene._live_recomposite_fn == scene.refresh_visible


def test_drag_cache_invalidated_on_frame_op(qtbot, theme):
    """A structural frame op (refresh_frames) invalidates the drag cache."""
    env = _make_env(qtbot, theme)
    scene, k = env.scene, env.k
    scene.begin_opacity_drag([k])
    assert scene._opacity_drag is not None
    scene.refresh_frames()
    assert scene._opacity_drag is None
    assert scene._live_recomposite_fn == scene.refresh_visible


# --------------------------------------------------------------------------- #
# Accessibility (both themes via the autouse theme fixture)                    #
# --------------------------------------------------------------------------- #


def test_opacity_slider_accessible_and_keyboard_reachable(qtbot, theme):
    """The opacity slider is keyboard-reachable, named, enabled, and themed.

    a11y for the drag control (both themes via the autouse fixture): an accessible
    name (screen-reader label), Tab focus (keyboard reach), enabled state, and a
    role-based themed stylesheet with a visible-focus rule applied to the app.
    """
    from PySide6.QtWidgets import QApplication

    doc = Document(64, 64, palette=Palette(STARTER))
    doc.add_layer("L1")
    panel = Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, QUndoStack(), lambda: None)

    slider = panel._rows[0]._opacity
    assert slider.accessibleName() == "Opacity"  # screen-reader label (UI a11y)
    assert bool(slider.focusPolicy() & Qt.FocusPolicy.TabFocus)  # keyboard-reachable
    assert slider.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert slider.isEnabled()

    # Role-based colours in the active theme: a non-empty stylesheet with a visible
    # :focus rule is applied by apply_theme (both themes exercised by the fixture).
    style = QApplication.instance().styleSheet()
    assert style  # a theme QSS is installed
    assert ":focus" in style  # visible focus indicator (both themes)


def test_opacity_drag_both_themes_commit_identically(qtbot, theme):
    """The committed pixels are theme-independent (REQ-P12-UI-001 both-theme rule).

    The commit is a logic recomposite (theme-agnostic), so the byte-exact result
    holds identically under light and dark — this test runs under both via the
    autouse ``theme`` fixture and asserts the same byte-exact invariant each time.
    """
    env = _make_env(qtbot, theme, partial_alpha=True, non_normal_above=True, seed=5)
    scene, nodes, k = env.scene, env.nodes, env.k
    scene.begin_opacity_drag([k])
    nodes[k].opacity = 0.55
    scene.refresh_visible()
    assert np.array_equal(scene._composite.data, _region_ref(nodes))
