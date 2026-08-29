"""D-08 acceptance: Phase-9 snap precedence resolved AT THE CURSOR (not the seam).

The audit finding this closes (`audit-spec-verification-consolidated-20260816.md`)
was that each aid's ``logic/`` snap function was unit-tested but nothing on the
real mouse/paint path ever called it — "satisfied at the seam, not the cursor".
These tests drive real ``Canvas_View`` mouse events (``testing.suites.ui._ui_helpers``)
through :class:`~pixelart_creator.ui.tools.PencilTool` and assert on the
OBSERVABLE painted pixel in the document buffer — never on
``Canvas_View._snap_scene_point`` directly — so a regression that broke the
real dispatch (not just the pure ``logic/`` function) would be caught here.

Ruled precedence (D-08 answer, REQ-P9-UI-003/-004/-005): the first VISIBLE
**and** ENABLED aid in ``guides > perspective > iso > rectangular`` order owns
the cursor. Each rank below is proven with a real, distinguishable snap
result (not merely "unchanged"), per the plan's acceptance bar.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF

from pixelart_creator.logic.grids import (
    IsoGridConfig,
    PerspectiveConfig,
    VanishingPoint,
)
from pixelart_creator.logic.guides import GuideOrientation
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay
from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay
from pixelart_creator.ui.perspective_grid_overlay import Perspective_Grid_Overlay
from pixelart_creator.ui.tools import PencilTool
from testing.suites.ui._ui_helpers import click_pixel, drag_path

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)

_RECT64 = QRectF(0, 0, 64, 64)

#: A 16px iso lattice — large enough that its snapped vertex is a real,
#: distinguishable pixel (the shipped ``IsoGridConfig()`` default is a
#: degenerate 2px tile that snaps almost every point to itself).
_ISO_CFG = IsoGridConfig(origin=(0.0, 0.0), tile_width=16, ratio=2.0)

#: A single, purely-horizontal vanishing point so ``perspective_snap``'s
#: direction math is exact in floating point (no sqrt(2) rounding noise).
_PERSPECTIVE_CFG = PerspectiveConfig(
    mode=1,
    vanishing_points=(VanishingPoint(position=(50.0, 5.0)),),
    horizon_y=0.0,
)


def _paint(view, x, y, tool=None):
    view.set_tool(tool or PencilTool())
    view.set_active_color(RED)


def test_d08_rank4_no_aid_enabled_falls_back_to_rectangular(make_view):
    """REQ-P9-UI-003/-004/-005/D-08: no aid bound => the prior floor-to-pixel
    (rectangular) behaviour, exactly unchanged."""
    view, scene, _stack = make_view(64, 64)
    _paint(view, 5, 5)
    click_pixel(view, 5, 5)
    buf = scene.active_buffer()
    assert buf.get_pixel(5, 5) == RED


def test_d08_rank3_iso_only_snaps_to_nearest_vertex(make_view):
    """REQ-P9-UI-004/D-08: with only the iso aid visible, the cursor snaps to
    the nearest lattice vertex (a real, non-trivial pixel, not "unchanged")."""
    view, scene, _stack = make_view(64, 64)
    _paint(view, 13, 9)
    iso = Iso_Grid_Overlay(_RECT64, _ISO_CFG)
    iso.setVisible(True)
    view.set_iso_overlay(iso)

    click_pixel(view, 13, 9)

    buf = scene.active_buffer()
    assert buf.get_pixel(16, 8) == RED  # the real iso_snap_vertex(13, 9) result
    assert buf.get_pixel(13, 9) == TRANSPARENT  # the raw, un-snapped click


def test_d08_rank2_perspective_beats_iso_when_both_visible(make_view):
    """REQ-P9-UI-005/D-08: perspective (rank 2) wins the cursor over iso
    (rank 3) when both are visible — a real, GEOMETRICALLY DIFFERENT snap
    result than iso alone would have produced for the same drag."""
    view, scene, _stack = make_view(64, 64)
    _paint(view, 13, 9)
    iso = Iso_Grid_Overlay(_RECT64, _ISO_CFG)
    iso.setVisible(True)
    view.set_iso_overlay(iso)
    perspective = Perspective_Grid_Overlay(_RECT64, _PERSPECTIVE_CFG)
    perspective.setVisible(True)
    view.set_perspective_overlay(perspective)

    # Press at (5, 5) — the stroke anchor for the perspective direction-lock —
    # then drag to (13, 9), which lies within tolerance of the VP(50, 5) line.
    drag_path(view, [(5, 5), (13, 9)])

    buf = scene.active_buffer()
    assert buf.get_pixel(13, 5) == RED  # perspective's real direction-locked result
    assert buf.get_pixel(16, 8) == TRANSPARENT  # NOT what iso alone would paint
    assert buf.get_pixel(13, 9) == TRANSPARENT  # NOT the raw, un-snapped point


def test_d08_rank1_guides_beats_perspective_and_iso_when_all_enabled(make_view):
    """REQ-P9-UI-003/D-08: guides (rank 1) win the cursor over BOTH perspective
    and iso when all three are visible+enabled. The stroke PRESSES away from
    the guide (so D-11's guide-drag gesture does not intercept the click) and
    MOVES near it, so the guide-snap is exercised on the real paint dispatch,
    not merely the pure ``logic.guides`` function."""
    view, scene, _stack = make_view(64, 64)
    _paint(view, 21, 30)
    iso = Iso_Grid_Overlay(_RECT64, _ISO_CFG)
    iso.setVisible(True)
    view.set_iso_overlay(iso)
    perspective = Perspective_Grid_Overlay(_RECT64, _PERSPECTIVE_CFG)
    perspective.setVisible(True)
    view.set_perspective_overlay(perspective)
    guides = Guides_Rulers_Overlay(view, scene, _RECT64)
    guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 20.0)
    guides.set_enabled(True)
    view.set_guides_overlay(guides)

    drag_path(view, [(2, 30), (21, 30)])

    buf = scene.active_buffer()
    assert buf.get_pixel(20, 30) == RED  # guides' snap wins outright
    assert buf.get_pixel(24, 28) == TRANSPARENT  # NOT what iso alone would paint
    assert buf.get_pixel(21, 30) == TRANSPARENT  # the raw, un-snapped point


def test_d08_precedence_falls_back_when_the_higher_ranks_are_disabled(make_view):
    """REQ-P9-UI-004/-005/D-08: with guides never enabled, disabling
    perspective mid-session falls the cursor through to iso — each lower
    rank is genuinely reachable, not just the top one."""
    view, scene, _stack = make_view(64, 64)
    _paint(view, 13, 9)
    iso = Iso_Grid_Overlay(_RECT64, _ISO_CFG)
    iso.setVisible(True)
    view.set_iso_overlay(iso)
    perspective = Perspective_Grid_Overlay(_RECT64, _PERSPECTIVE_CFG)
    perspective.setVisible(True)
    view.set_perspective_overlay(perspective)

    # Perspective (rank 2) visible: it wins over iso.
    drag_path(view, [(5, 5), (13, 9)])
    buf = scene.active_buffer()
    assert buf.get_pixel(13, 5) == RED

    # Hide perspective: iso (rank 3) now owns the cursor for a fresh stroke.
    perspective.setVisible(False)
    click_pixel(view, 30, 9)
    assert buf.get_pixel(32, 8) == RED
