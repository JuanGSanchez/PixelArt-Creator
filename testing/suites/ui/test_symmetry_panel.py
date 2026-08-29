"""D-28 acceptance: the symmetry axis-position control (REQ-P2-UI-011, CF-93).

``Symmetry_Panel`` widget-level behaviour (position dirty-tracking, canvas-size
rebind, reset, a11y) PLUS the full UI-path integration the plan's acceptance
bar names explicitly: "mirrored coords respect the set axis THROUGH THE UI
PATH (canvas context), not just the logic call" — i.e. wiring
``Symmetry_Panel.axisPositionChanged`` into a real ``Canvas_View`` and
painting through :class:`~pixelart_creator.ui.tools.PencilTool`, never
calling ``logic.symmetry.mirror`` directly. Both themes via the autouse
``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.ui.symmetry_panel import Symmetry_Panel
from tests.ui._ui_helpers import click_pixel

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _panel(qtbot):
    panel = Symmetry_Panel()
    qtbot.addWidget(panel)
    return panel


# --- widget-level: dirty tracking / reset / canvas-size rebind -------------- #


def test_d28_axis_position_is_none_until_the_user_edits_a_spinbox(qtbot):
    """D-28/CL-9: untouched behaviour is unchanged — ``axis_position()`` stays
    ``None`` (mirror computes the canvas centre itself) until a real edit."""
    panel = _panel(qtbot)
    panel.set_canvas_size(32, 20)
    assert panel.axis_position() is None


def test_d28_editing_a_spinbox_reports_the_position_and_emits(qtbot):
    """D-28: editing X (or Y) marks the position dirty and emits the new tuple."""
    panel = _panel(qtbot)
    panel.set_canvas_size(32, 20)
    captured = []
    panel.axisPositionChanged.connect(captured.append)

    panel._x_spin.setValue(5)

    assert panel.axis_position() == (5, 9)  # default Y midpoint, per (32-1)//2...
    assert captured == [(5, 9)]


def test_d28_reset_returns_to_the_unset_centre_default(qtbot):
    """D-28: "Reset to centre" clears the dirty flag and emits ``None``."""
    panel = _panel(qtbot)
    panel.set_canvas_size(32, 20)
    panel._x_spin.setValue(5)
    captured = []
    panel.axisPositionChanged.connect(captured.append)

    panel._reset_button.click()

    assert panel.axis_position() is None
    assert captured == [None]


def test_d28_set_canvas_size_resets_dirty_without_emitting(qtbot):
    """D-28: a programmatic resize (new document/tab) resets to unset WITHOUT
    emitting — it is not a user edit, so ``axisPositionChanged`` stays quiet."""
    panel = _panel(qtbot)
    panel.set_canvas_size(32, 20)
    panel._x_spin.setValue(5)
    assert panel.axis_position() == (5, 9)

    captured = []
    panel.axisPositionChanged.connect(captured.append)
    panel.set_canvas_size(64, 64)  # a different document bound in

    assert panel.axis_position() is None
    assert captured == []  # no spurious emission from the rebind itself


def test_d28_spinbox_ranges_bound_to_the_canvas_size(qtbot):
    """D-28/S12: spinbox ranges track the real document size, not a literal."""
    panel = _panel(qtbot)
    panel.set_canvas_size(32, 20)
    assert panel._x_spin.minimum() == 0
    assert panel._x_spin.maximum() == 31
    assert panel._y_spin.minimum() == 0
    assert panel._y_spin.maximum() == 19


def test_d28_accessible_names_present_on_position_controls(qtbot):
    """A11y: X/Y spinboxes and the reset button are keyboard/screen-reader
    reachable in both themes."""
    panel = _panel(qtbot)
    assert panel._x_spin.accessibleName() != ""
    assert panel._y_spin.accessibleName() != ""
    assert panel._reset_button.accessibleName() != ""


# --- D-28: THROUGH THE UI PATH (canvas context) — the acceptance bar -------- #


def test_d28_panel_position_reaches_the_live_paint_through_canvas_view(
    make_view, qtbot
):
    """D-28: wiring ``Symmetry_Panel.axisPositionChanged`` into a real
    ``Canvas_View.set_symmetry_pos`` changes where a VERTICAL-axis stroke's
    mirror actually lands — through the same ``_make_context()`` seam a real
    paint stroke uses, never a direct ``logic.symmetry.mirror`` call."""
    view, scene, _stack = make_view(32, 20)
    panel = _panel(qtbot)
    panel.set_canvas_size(32, 20)
    panel.axisPositionChanged.connect(view.set_symmetry_pos)
    view.set_active_color(RED)
    view.set_symmetry_axis(SymmetryAxis.VERTICAL)

    # Untouched panel (axis_position() is None): mirror uses the canvas centre
    # default, exactly as before D-28.
    click_pixel(view, 2, 2)
    buf = scene.active_buffer()
    assert buf.get_pixel(2, 2) == RED
    assert buf.get_pixel(32 - 1 - 2, 2) == RED  # centre-default mirror (W-1-x)

    # The user sets a custom axis position via the panel spinbox — the LIVE
    # paint path must now mirror around that position instead.
    panel._x_spin.setValue(10)
    click_pixel(view, 4, 8)
    # logic.symmetry.mirror's VERTICAL rule around axis_pos=(10, *) is
    # ``2*axis_x - x``: mirror_x = 2*10 - 4 = 16.
    assert buf.get_pixel(4, 8) == RED
    assert buf.get_pixel(16, 8) == RED
    assert buf.get_pixel(32 - 1 - 4, 8) == TRANSPARENT  # NOT the old centre rule


def test_d28_reset_through_canvas_view_restores_the_centre_default(make_view, qtbot):
    """D-28: resetting the panel through the SAME live wiring restores the
    canvas-centre mirror on the very next stroke."""
    view, scene, _stack = make_view(32, 20)
    panel = _panel(qtbot)
    panel.set_canvas_size(32, 20)
    panel.axisPositionChanged.connect(view.set_symmetry_pos)
    view.set_active_color(RED)
    view.set_symmetry_axis(SymmetryAxis.VERTICAL)

    panel._x_spin.setValue(10)
    assert view.symmetry_pos() == (10, 9)

    panel._reset_button.click()

    assert view.symmetry_pos() is None
    click_pixel(view, 4, 8)
    buf = scene.active_buffer()
    assert buf.get_pixel(32 - 1 - 4, 8) == RED  # back to the centre-default rule
