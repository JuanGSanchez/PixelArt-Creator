"""Multi-view editing acceptance tests (REQ-P9-UI-007/-008).

Scenario SC-UI-007-1 (open multiple views of ONE document; each with its own
zoom/pan) and SC-UI-008-1 (an edit in one view syncs to every view + the preview
without a manual refresh, while local zoom/pan stays independent). All views bind
to the one shared scene — no per-view pixel copy (REQ-P9-LOGIC-012). Both themes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.constants import MAX_DOCUMENT_VIEWS
from pixelart_creator.ui.multi_view import Multi_View
from tests.ui._ui_helpers import click_pixel

BLUE = (40, 90, 220, 255)


# --- SC-UI-007-1: multiple views of one shared document --------------------- #


def test_sc_ui_007_1_open_view_shares_the_one_scene(qtbot, make_view):
    """SC-UI-007-1: an opened extra view binds to the SAME shared scene object."""
    _view, scene, _stack = make_view(32, 32)
    mv = Multi_View(scene)
    extra = mv.open_view()
    assert extra is not None
    qtbot.addWidget(extra)
    assert extra.scene() is scene
    assert mv.count() == 1


def test_sc_ui_007_1_view_count_bounded_by_max_document_views(qtbot, make_view):
    """SC-UI-007-1: the primary view counts as 1; extras cap at MAX-1, then None."""
    _view, scene, _stack = make_view(16, 16)
    mv = Multi_View(scene)
    opened = []
    for _ in range(MAX_DOCUMENT_VIEWS - 1):
        v = mv.open_view()
        assert v is not None
        qtbot.addWidget(v)
        opened.append(v)
    assert mv.count() == MAX_DOCUMENT_VIEWS - 1
    # The primary Canvas_View is view 1, so the cap is now reached.
    assert mv.open_view() is None
    mv.close_all()


def test_sc_ui_007_1_independent_zoom_per_view(qtbot, make_view):
    """SC-UI-007-1: each extra view keeps its own transform (zoom is not synced)."""
    _view, scene, _stack = make_view(32, 32)
    mv = Multi_View(scene)
    a = mv.open_view()
    b = mv.open_view()
    qtbot.addWidget(a)
    qtbot.addWidget(b)
    a.scale(2.0, 2.0)
    assert a.transform().m11() == 2.0
    assert b.transform().m11() == 1.0  # unchanged — local zoom is independent
    mv.close_all()


# --- SC-UI-008-1: edits sync across all views without manual refresh -------- #


def test_sc_ui_008_1_edit_syncs_across_views_via_shared_scene(qtbot, make_view):
    """SC-UI-008-1: an edit reflects in the shared source every view derives from."""
    view, scene, _stack = make_view(32, 32)
    mv = Multi_View(scene)
    a = mv.open_view()
    b = mv.open_view()
    qtbot.addWidget(a)
    qtbot.addWidget(b)
    fired: list[int] = []
    scene.changed.connect(lambda *_a: fired.append(1))
    view.set_active_color(BLUE)
    click_pixel(view, 9, 9)
    QApplication.processEvents()
    # One shared buffer both extra views render — no per-view copy.
    assert scene.active_buffer().get_pixel(9, 9) == BLUE
    assert a.scene() is scene and b.scene() is scene
    assert fired, "scene.changed must fire so all views repaint without manual refresh"
    mv.close_all()


def test_sc_ui_008_1_set_scene_rebinds_all_views(qtbot, make_view):
    """SC-UI-008-1: rebinding the controller re-points every open view (tab switch)."""
    _v1, scene1, _s1 = make_view(16, 16)
    _v2, scene2, _s2 = make_view(16, 16)
    mv = Multi_View(scene1)
    a = mv.open_view()
    qtbot.addWidget(a)
    assert a.scene() is scene1
    mv.set_scene(scene2)
    assert a.scene() is scene2
    mv.close_all()
