"""Tilemap-canvas zoom-floor acceptance tests (D-20, 2026-08-31).

**What D-20 changed.** ``Tilemap_Canvas._clamp_zoom`` used to apply
``min(ZOOM_MIN, self._fit_zoom())`` as its lower bound -- so on a document
larger than the viewport (where ``_fit_zoom()`` is genuinely sub-1.0) the
*effective* floor silently became that sub-1.0 fit value instead of
``ZOOM_MIN``, leaving the widget reachable to zoom below 1:1. The fix makes
``ZOOM_MIN`` an ABSOLUTE floor -- ``max(ZOOM_MIN, min(value, ZOOM_MAX))`` --
matching ``Canvas_View._clamp_zoom`` exactly (see
``pixelart_creator/ui/tilemap_canvas.py`` around line 724, and
``design-docs/jobs/20260830-input-scheme/job-specification.md`` §15).

**What this module proves, and what it deliberately does NOT claim.** These
tests prove the FLOOR HOLDS -- through ``_clamp_zoom`` directly, through the
public ``set_zoom`` entry point, through the wheel-zoom gesture, and at the
exact ``ZOOM_MIN`` boundary -- plus a control proving the ceiling
(``ZOOM_MAX``) was not broken by the same change. They do **not** prove a
user-visible bug was fixed: unlike the paint canvas (``Canvas_View``, fixed
2026-08-25 by commit ``92f09d5`` after a measured symptom -- a 1-pixel
sparse outline point-sampling to zero on-screen pixels below 1:1), the
symptom has never been demonstrated on ``Tilemap_Canvas``. It stamps/erases/
fills filled tile images, not sparse shape outlines. The implementer's
stated reason for flooring it anyway is that ``_Tilemap_Scene.drawBackground``
draws its own optional 1-device-pixel-wide grid-overlay lines -- sparse,
single-pixel-width content of the SAME class the paint-canvas checker border
lost under nearest-neighbour point sampling -- so the fix closes a latent
instance of an already-fixed defect class, not a reported one. A reader of
this module should come away knowing the floor is now unconditional, not
believing a vanished grid line or stamp was ever observed.

**The small-map boundary case, and an honest caveat about it.** ``_fit_zoom``
computes a genuinely sub-1.0 value whenever the (always at-least-1024x1024,
``_INITIAL_WINDOW``) scene rect is larger than the viewport -- reproduced
below with the same disproportionate viewport/scene pairing the sibling
``Canvas_View`` suite uses. As of this session ``_fit_zoom`` has **no live
caller anywhere in ``tilemap_canvas.py``** (``Tilemap_Canvas`` exposes no
``fit()``/fit-to-window action, per the AGT-05 report that made this change --
``design-docs/reports/subagent-report-agt-05-ui-expert-aa685275-
20260831T085754.md``). This module therefore exercises the private method
directly to prove the boundary MATH holds should a future caller ever feed
its result to ``set_zoom`` -- it is not exercising a currently-reachable UI
route, and the docstrings below say so at the point it matters.

Both light and dark theme run automatically (the autouse ``theme`` fixture in
``conftest.py`` parametrises every test in this suite, REQ-P6-UI-016 /
``025``). Zoom clamp arithmetic does not depend on theme at all, so -- like
the sibling ``test_canvas_zoom_floor.py`` -- no test here opts out of or
otherwise references the parametrisation; it simply accepts the same
doubling every other module in this suite does.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.constants import ZOOM_MAX, ZOOM_MIN
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas

#: A tiny fraction of a zoom unit -- small enough that it can never itself
#: cross a preset stop or rounding boundary, large enough to be a real,
#: distinguishable float distance from ``ZOOM_MIN`` / ``ZOOM_MAX``. Used only
#: to probe the ``>`` vs ``>=`` boundary at the floor/ceiling.
_EPS = 1e-6

#: Viewport paired with the ``Tilemap_Canvas`` scene's fixed initial window
#: (``_INITIAL_WINDOW`` == 1024x1024, ``tilemap_canvas.py``) so that
#: ``_fit_zoom()`` is genuinely sub-1.0 -- the disproportion is asserted, not
#: assumed, in the test that relies on it.
_SMALL_VIEWPORT = 224


def _build_canvas(qtbot, width: int | None = None, height: int | None = None):
    """Build a bare ``Tilemap_Canvas`` (no bound tilemap -- zoom math does not
    need one), settled to a REAL viewport size when one is requested.

    A bare ``setFixedSize()`` leaves ``viewport().rect()`` stale until Qt
    processes the pending scrollbar-space layout pass -- the same effect
    documented and measured for ``Canvas_View`` in the sibling
    ``test_canvas_zoom_floor.py``'s ``_build_view`` helper, and reproduced
    here directly against ``Tilemap_Canvas`` before writing this module: a
    224x224 ``setFixedSize`` reports a stale ``624x464`` viewport until
    ``QApplication.processEvents()`` runs, settling to the real,
    scrollbar-adjusted ``208x208`` only afterward.
    """
    canvas = Tilemap_Canvas()
    qtbot.addWidget(canvas)
    if width is not None and height is not None:
        canvas.setFixedSize(width, height)
        QApplication.processEvents()
    return canvas


def _wheel_event(*, zoom_in: bool) -> QWheelEvent:
    """Build a real ``QWheelEvent`` zoom notch (matches the sibling suite's
    ``Canvas_View`` wheel-zoom-floor construction exactly).

    INVERTED 2026-08-31 (T-22, D-16/REQ-IS-UI-008,-009): carries
    ``ShiftModifier`` -- the wheel-zoom route this helper feeds
    (``Tilemap_Canvas._zoom_wheel``) now requires ``Shift`` held; plain wheel
    travels Favourites instead (REQ-IS-UI-008) and never reaches
    ``_clamp_zoom`` at all. Both callers below (``D20-3`` zoom-out-floor and
    ``D20-4`` zoom-in-ceiling-control) are proving the clamp holds via the
    wheel-zoom route specifically, so both still need this event to actually
    reach that route.
    """
    delta = QPoint(0, 120 if zoom_in else -120)
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        delta,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


# --------------------------------------------------------------------------- #
# D20-1 -- the floor holds through `_clamp_zoom` directly.                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("raw", [-10.0, -1.0, 0.0, 0.001, 0.5, 0.9, 0.999999])
def test_d20_clamp_zoom_floor_holds_for_values_below_min(qtbot, raw):
    """D20-1: any value below ``ZOOM_MIN`` -- including zero and negative
    input -- clamps to exactly ``ZOOM_MIN``, never to the input itself and
    never to anything else below the floor."""
    canvas = _build_canvas(qtbot)
    assert canvas._clamp_zoom(raw) == pytest.approx(ZOOM_MIN)


def test_d20_clamp_zoom_boundary_at_exactly_zoom_min(qtbot):
    """D20-1 boundary: ``_clamp_zoom(ZOOM_MIN)`` returns ``ZOOM_MIN`` itself
    -- the classic off-by-one surface where a stray ``>`` (as opposed to the
    correct ``>=``, or the ``max()`` this implementation actually uses)
    would push the boundary value itself out of range."""
    canvas = _build_canvas(qtbot)
    assert canvas._clamp_zoom(ZOOM_MIN) == ZOOM_MIN


def test_d20_clamp_zoom_boundary_just_below_and_above_min(qtbot):
    """D20-1 boundary: a value one epsilon BELOW ``ZOOM_MIN`` still floors to
    ``ZOOM_MIN``, while a value one epsilon ABOVE it passes through
    unchanged -- proving the clamp acts exactly at the boundary, neither
    early nor late."""
    canvas = _build_canvas(qtbot)
    assert canvas._clamp_zoom(ZOOM_MIN - _EPS) == pytest.approx(ZOOM_MIN)
    assert canvas._clamp_zoom(ZOOM_MIN + _EPS) == pytest.approx(ZOOM_MIN + _EPS)


# --------------------------------------------------------------------------- #
# D20-2 -- the floor holds through `set_zoom`, so a caller cannot route       #
# around it by using the PUBLIC entry point instead of the private clamp.     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("raw", [-5.0, 0.0, 0.25, 0.5, 0.999999])
def test_d20_set_zoom_floor_holds_for_out_of_range_values(qtbot, raw):
    """D20-2: ``set_zoom`` -- the real public entry point every future
    zoom-out caller would use -- applies the SAME floor, observed on the
    view's actual transform (what is rendered), not on private state."""
    canvas = _build_canvas(qtbot)
    canvas.set_zoom(raw)
    assert canvas.transform().m11() == pytest.approx(ZOOM_MIN)
    assert canvas.transform().m22() == pytest.approx(ZOOM_MIN)


def test_d20_set_zoom_boundary_at_exactly_zoom_min(qtbot):
    """D20-2 boundary: ``set_zoom(ZOOM_MIN)`` lands the view's transform at
    exactly ``ZOOM_MIN`` -- the same off-by-one surface as D20-1, exercised
    through the public route this time."""
    canvas = _build_canvas(qtbot)
    canvas.set_zoom(ZOOM_MIN)
    assert canvas.transform().m11() == pytest.approx(ZOOM_MIN)


# --------------------------------------------------------------------------- #
# D20-3 -- the floor holds through the wheel-zoom-out gesture (a third,      #
# real caller route into `_clamp_zoom`, alongside `set_zoom`).               #
# --------------------------------------------------------------------------- #


def test_d20_wheel_zoom_out_floor_holds(qtbot):
    """D20-3: repeated wheel-out notches never drop the observable zoom
    below ``ZOOM_MIN``, and land exactly on it once reached -- mirrors the
    sibling ``Canvas_View`` wheel-floor test's shape and notch count.

    INVERTED 2026-08-31 (T-22): the notches ``_wheel_event`` builds now carry
    ``Shift`` -- see that helper's own docstring."""
    canvas = _build_canvas(qtbot)
    canvas.set_zoom(ZOOM_MIN * 2)  # start above the floor, well within range
    wheel_out = _wheel_event(zoom_in=False)
    for _ in range(40):  # enough notches to reach and then try to cross the floor
        canvas.wheelEvent(wheel_out)
        assert canvas.transform().m11() >= ZOOM_MIN - 1e-9
    assert canvas.transform().m11() == pytest.approx(ZOOM_MIN)


# --------------------------------------------------------------------------- #
# D20-4 (CONTROL) -- the ceiling still holds. A floor implemented by         #
# clamping in the wrong direction would pass every test above and silently   #
# break zoom-in; nothing else in this module would notice without this one.  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("raw", [65.0, 100.0, 1000.0])
def test_d20_clamp_zoom_ceiling_still_holds_for_values_above_max(qtbot, raw):
    """D20-4 (control): values above ``ZOOM_MAX`` still clamp DOWN to
    ``ZOOM_MAX`` via ``_clamp_zoom`` -- the floor change did not narrow, widen
    or otherwise disturb the independent upper bound."""
    canvas = _build_canvas(qtbot)
    assert canvas._clamp_zoom(raw) == pytest.approx(ZOOM_MAX)


def test_d20_clamp_zoom_ceiling_boundary_at_exactly_zoom_max(qtbot):
    """D20-4 (control) boundary: ``_clamp_zoom(ZOOM_MAX)`` returns
    ``ZOOM_MAX`` itself, and a value one epsilon below it passes through
    unchanged -- the same off-by-one shape as the floor, at the other end."""
    canvas = _build_canvas(qtbot)
    assert canvas._clamp_zoom(ZOOM_MAX) == ZOOM_MAX
    assert canvas._clamp_zoom(ZOOM_MAX - _EPS) == pytest.approx(ZOOM_MAX - _EPS)


def test_d20_set_zoom_ceiling_still_holds(qtbot):
    """D20-4 (control): ``set_zoom`` -- the same public route D20-2 checked
    for the floor -- still reaches ``ZOOM_MAX`` and stops there, observed on
    the view's actual transform."""
    canvas = _build_canvas(qtbot)
    canvas.set_zoom(ZOOM_MAX * 10)
    assert canvas.transform().m11() == pytest.approx(ZOOM_MAX)


def test_d20_wheel_zoom_in_ceiling_still_holds(qtbot):
    """D20-4 (control): repeated wheel-in notches from the floor still climb
    all the way to ``ZOOM_MAX`` and stop there -- proves the floor fix did
    not silently invert the clamp direction, which would pass every D20-1/
    D20-2/D20-3 test above while breaking zoom-in entirely.

    INVERTED 2026-08-31 (T-22): the notches ``_wheel_event`` builds now carry
    ``Shift`` -- see that helper's own docstring."""
    canvas = _build_canvas(qtbot)
    canvas.set_zoom(ZOOM_MIN)
    wheel_in = _wheel_event(zoom_in=True)
    for _ in range(80):  # ~30 notches suffice at factor 1.15; 80 is a wide margin
        canvas.wheelEvent(wheel_in)
        assert canvas.transform().m11() <= ZOOM_MAX + 1e-9
    assert canvas.transform().m11() == pytest.approx(ZOOM_MAX)


# --------------------------------------------------------------------------- #
# D20-5 -- the small-map boundary case: a natural fit below 1.0 still        #
# clamps to the floor rather than being honoured. See the module docstring   #
# for why this exercises `_fit_zoom` directly rather than a live UI route.   #
# --------------------------------------------------------------------------- #


def test_d20_small_map_boundary_fit_zoom_below_floor_still_clamps(qtbot):
    """D20-5: with a viewport smaller than the scene's fixed initial window
    (``_INITIAL_WINDOW`` == 1024x1024), the raw fit computation is genuinely
    sub-``ZOOM_MIN`` (asserted, not assumed, so this test is proven to
    exercise the clamp and not merely coincide with it) -- yet clamping that
    raw value, and feeding it through the real ``set_zoom`` entry point,
    both land on exactly ``ZOOM_MIN``, never below.

    ``_fit_zoom`` has no live caller in ``Tilemap_Canvas`` today (see the
    module docstring) -- this proves the boundary math holds should one be
    added later, not that a fit-to-window action is reachable now.
    """
    canvas = _build_canvas(qtbot, _SMALL_VIEWPORT, _SMALL_VIEWPORT)
    raw_fit = canvas._fit_zoom()
    assert raw_fit < ZOOM_MIN  # the scene really is larger than the viewport
    assert canvas._clamp_zoom(raw_fit) == pytest.approx(ZOOM_MIN)

    canvas.set_zoom(raw_fit)
    assert canvas.transform().m11() == pytest.approx(ZOOM_MIN)
