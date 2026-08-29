"""Real-size preview window acceptance tests (REQ-P9-UI-001/-002).

Scenarios SC-UI-001-1 (renders the composited document at the logic-computed
real-size scale, adding no scaling maths of its own) and SC-UI-002-1 (mirrors
edits live via the one shared scene; the preview is read-only). Both themes via
the autouse ``theme`` fixture.

HIGHEST-RISK coverage: the preview must apply the pure ``real_size_scale`` factor
**exactly once** — no ``devicePixelRatio`` multiply on top (double-DPR would
double-scale on HiDPI, research §4.2 / ADR-0023 §4). These tests pin the applied
view transform to the pure ``screen_dpi / doc_ppi`` ratio and prove no second
scaling factor is folded in.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QGraphicsView

from pixelart_creator.logic.constants import DEFAULT_DOCUMENT_PPI
from pixelart_creator.logic.preview import real_size_scale
from pixelart_creator.ui.real_size_preview_window import Real_Size_Preview_Window
from testing.suites.ui._ui_helpers import click_pixel

BLUE = (40, 90, 220, 255)


def _preview(qtbot, scene, ppi=DEFAULT_DOCUMENT_PPI):
    win = Real_Size_Preview_Window(scene, ppi)
    qtbot.addWidget(win)
    return win


# --- SC-UI-001-1: renders at the logic-computed real-size scale ------------- #


def test_sc_ui_001_1_applies_logic_scale_exactly(qtbot, make_scene):
    """SC-UI-001-1: the view transform equals the pure real_size_scale factor.

    doc_ppi=72, screen_dpi=144 -> scale must be exactly 2.0 (144/72). The window
    adds no scaling maths of its own; it applies logic.real_size_scale."""
    scene = make_scene(32, 32)
    win = _preview(qtbot, scene, ppi=72.0)
    win.set_manual_dpi(144.0)  # pin the screen DPI deterministically
    expected = real_size_scale(72.0, 144.0)
    assert expected == 2.0
    assert win.current_scale() == expected
    assert win._view.transform().m11() == expected
    assert win._view.transform().m22() == expected


def test_sc_ui_001_1_no_double_dpr_scaling(qtbot, make_scene):
    """SC-UI-001-1 (HIGHEST RISK): DPR is NOT multiplied onto the real-size scale.

    The applied transform must equal ``screen_dpi / doc_ppi`` and be independent
    of the view's devicePixelRatio — a double-DPR bug would multiply by the DPR a
    second time. We assert the transform equals the pure ratio and that dividing
    it back out by devicePixelRatio would NOT leave the pure ratio (i.e. DPR is
    not baked in)."""
    scene = make_scene(16, 16)
    win = _preview(qtbot, scene, ppi=96.0)
    win.set_manual_dpi(96.0)  # scale should be exactly 1.0
    pure = real_size_scale(96.0, 96.0)
    assert pure == 1.0
    applied = win._view.transform().m11()
    dpr = float(win._view.devicePixelRatioF())
    # The applied scale is the pure ratio, full stop.
    assert applied == pure
    # If DPR had been multiplied in, applied would be pure*dpr; when dpr != 1 that
    # would differ from pure. Guard the invariant for any DPR the platform reports.
    assert applied == pure  # never pure * dpr
    if dpr != 1.0:
        assert applied != pure * dpr


def test_sc_ui_001_1_rescales_on_ppi_change(qtbot, make_scene):
    """SC-UI-001-1: changing the document PPI rescales via the pure function."""
    scene = make_scene(16, 16)
    win = _preview(qtbot, scene, ppi=72.0)
    win.set_manual_dpi(144.0)
    assert win._view.transform().m11() == real_size_scale(72.0, 144.0)  # 2.0
    win.set_document_ppi(144.0)
    assert win._view.transform().m11() == real_size_scale(144.0, 144.0)  # 1.0


def test_sc_ui_001_1_read_only_view_never_edits(qtbot, make_scene):
    """SC-UI-001-1: the preview view is non-interactive (cannot mutate the doc)."""
    scene = make_scene(16, 16)
    win = _preview(qtbot, scene)
    assert win._view.isInteractive() is False
    assert win._view.dragMode() == QGraphicsView.DragMode.NoDrag


# --- SC-UI-002-1: mirrors edits live via the one shared scene --------------- #


def test_sc_ui_002_1_preview_observes_the_shared_scene(qtbot, make_view):
    """SC-UI-002-1: the preview binds to the SAME scene object the canvas edits."""
    view, scene, _stack = make_view(32, 32)
    win = _preview(qtbot, scene)
    assert win._view.scene() is scene


def test_sc_ui_002_1_edit_mirrors_live_no_manual_refresh(qtbot, make_view):
    """SC-UI-002-1: an edit on the shared scene fires scene.changed (live mirror).

    The preview repaints off ``QGraphicsScene.changed`` with no manual refresh —
    we assert the signal fires on a canvas edit and that the shared buffer (the
    single source both observe) reflects the edit."""
    view, scene, _stack = make_view(32, 32)
    win = _preview(qtbot, scene)
    fired: list[int] = []
    scene.changed.connect(lambda *_a: fired.append(1))
    view.set_active_color(BLUE)
    click_pixel(view, 5, 6)
    QApplication.processEvents()
    assert scene.active_buffer().get_pixel(5, 6) == BLUE
    assert fired, "scene.changed must fire on an edit (live-mirror substrate)"
    # Both the canvas view and the preview view still share one scene (no copy).
    assert win._view.scene() is scene


def test_sc_ui_002_1_viewing_preview_never_mutates_document(qtbot, make_view):
    """SC-UI-002-1: constructing/rescaling the preview never mutates the doc."""
    view, scene, stack = make_view(32, 32)
    before = scene.active_buffer().copy()
    win = _preview(qtbot, scene)
    win.recompute_scale()
    win.set_manual_dpi(200.0)
    assert scene.active_buffer() == before
    assert stack.count() == 0
