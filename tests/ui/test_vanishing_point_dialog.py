"""D-09 acceptance: the minimal vanishing-point configuration dialog
(REQ-P9-UI-005, ``Vanishing_Point_Dialog``).

Covers the config round-trip (seed from a real :class:`PerspectiveConfig`,
read back an equal-value one from the widgets), 1-/2-/3-point mode selection
(exactly ``mode`` VP groups visible), and the overlay-update seam
(``main_window._on_configure_perspective`` calls
``perspective_overlay.set_config(dialog.perspective_config())`` on Accept —
this exercises that exact call shape against a real
:class:`Perspective_Grid_Overlay` without driving the modal ``exec()`` loop,
which is the correct headless-dialog pattern: nothing here waits on a user).
Both themes via the autouse ``theme`` fixture (a11y checks on every control).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF

from pixelart_creator.logic.constants import MAX_PERSPECTIVE_VANISHING_POINTS
from pixelart_creator.logic.grids import PerspectiveConfig, VanishingPoint
from pixelart_creator.ui.perspective_grid_overlay import Perspective_Grid_Overlay
from pixelart_creator.ui.vanishing_point_dialog import Vanishing_Point_Dialog

_RECT64 = QRectF(0, 0, 64, 64)


def _config(mode, points, horizon=10.0):
    return PerspectiveConfig(
        mode=mode,
        vanishing_points=tuple(VanishingPoint(position=p) for p in points),
        horizon_y=horizon,
    )


def test_d09_config_round_trips_through_the_dialog(qtbot):
    """D-09/REQ-P9-UI-005: seeding + reading back preserves mode/horizon/VPs."""
    source = _config(2, [(-64.0, 32.0), (128.0, 32.0)], horizon=10.0)
    dialog = Vanishing_Point_Dialog(source)
    qtbot.addWidget(dialog)

    result = dialog.perspective_config()

    assert result.mode == 2
    assert result.horizon_y == 10.0
    assert result.vanishing_points[0].position == (-64.0, 32.0)
    assert result.vanishing_points[1].position == (128.0, 32.0)


def test_d09_one_point_mode_shows_exactly_one_vp_group(qtbot):
    """D-09: selecting 1-point shows exactly one VP group; the rest are hidden."""
    dialog = Vanishing_Point_Dialog(_config(1, [(0.0, 0.0)]))
    qtbot.addWidget(dialog)

    visible = [g.isVisible() or g.isVisibleTo(dialog) for g in dialog._vp_groups]
    assert dialog.perspective_config().mode == 1
    # Exactly the first VP group is the "shown" one (QWidget.isVisible() needs a
    # real top-level show(); isVisibleTo(dialog) reflects the intended state
    # regardless of whether the dialog itself is shown headless).
    assert dialog._vp_groups[0].isVisibleTo(dialog) is True
    assert dialog._vp_groups[1].isVisibleTo(dialog) is False
    assert dialog._vp_groups[2].isVisibleTo(dialog) is False


def test_d09_three_point_mode_shows_all_three_vp_groups(qtbot):
    """D-09: selecting 3-point shows all three VP groups."""
    dialog = Vanishing_Point_Dialog(
        _config(3, [(0.0, 0.0), (64.0, 0.0), (32.0, -64.0)])
    )
    qtbot.addWidget(dialog)

    assert dialog.perspective_config().mode == 3
    for group in dialog._vp_groups:
        assert group.isVisibleTo(dialog) is True


def test_d09_switching_mode_changes_the_assembled_config(qtbot):
    """D-09: changing the mode combo changes how many VPs ``perspective_config``
    assembles (mechanical widget -> value-type flow, S11 — no geometry here)."""
    dialog = Vanishing_Point_Dialog(
        _config(3, [(0.0, 0.0), (64.0, 0.0), (32.0, -64.0)])
    )
    qtbot.addWidget(dialog)
    assert dialog.perspective_config().mode == 3

    dialog._mode_combo.setCurrentIndex(0)  # 1-point
    assert len(dialog.perspective_config().vanishing_points) == 1
    assert dialog._vp_groups[1].isVisibleTo(dialog) is False


def test_d09_accept_updates_the_real_overlay_seam(qtbot):
    """D-09: the exact ``main_window._on_configure_perspective`` Accept path —
    ``overlay.set_config(dialog.perspective_config())`` — updates a REAL
    :class:`Perspective_Grid_Overlay`, not a stub."""
    overlay = Perspective_Grid_Overlay(_RECT64, _config(1, [(10.0, 10.0)]))
    dialog = Vanishing_Point_Dialog(overlay.config())
    qtbot.addWidget(dialog)

    # Simulate the user changing mode + VP position (no exec(), no modal loop).
    dialog._mode_combo.setCurrentIndex(1)  # 2-point
    dialog._vp_x[0].setValue(5.0)
    dialog._vp_y[0].setValue(6.0)
    dialog._vp_x[1].setValue(50.0)
    dialog._vp_y[1].setValue(6.0)

    # The exact call main_window makes on QDialog.DialogCode.Accepted.
    overlay.set_config(dialog.perspective_config())

    assert overlay.config().mode == 2
    assert overlay.config().vanishing_points[0].position == (5.0, 6.0)
    assert overlay.config().vanishing_points[1].position == (50.0, 6.0)


def test_d09_mode_count_bounded_by_the_constant(qtbot):
    """D-09/S12: the mode combo offers exactly ``MAX_PERSPECTIVE_VANISHING_POINTS``
    entries — imported from ``logic/constants``, never an inline literal."""
    dialog = Vanishing_Point_Dialog(_config(1, [(0.0, 0.0)]))
    qtbot.addWidget(dialog)
    assert dialog._mode_combo.count() == MAX_PERSPECTIVE_VANISHING_POINTS
    assert len(dialog._vp_groups) == MAX_PERSPECTIVE_VANISHING_POINTS


def test_d09_accessible_names_present_on_every_control(qtbot):
    """A11y: mode combo, horizon spin and every VP spinbox carry an accessible
    name (keyboard/screen-reader reachable, both themes via the autouse fixture)."""
    dialog = Vanishing_Point_Dialog(
        _config(3, [(0.0, 0.0), (64.0, 0.0), (32.0, -64.0)])
    )
    qtbot.addWidget(dialog)
    assert dialog._mode_combo.accessibleName() != ""
    assert dialog._horizon_spin.accessibleName() != ""
    for spin in (*dialog._vp_x, *dialog._vp_y):
        assert spin.accessibleName() != ""
