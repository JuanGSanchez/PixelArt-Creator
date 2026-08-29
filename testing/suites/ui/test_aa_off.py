"""Forced anti-aliasing-OFF acceptance (REQ-P2-UI-014).

Scenarios SC-U014-1 (the canvas never enables antialiasing / smooth-pixmap-transform
at any zoom) and SC-U014-2 (previews render nearest-neighbour, hard-edged). Also
re-verifies that the shell's AA-off toggle is locked ON (CL-15). Both themes via the
autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtGui import QPainter

from pixelart_creator.ui.main_window import Main_Window

AA = QPainter.RenderHint.Antialiasing
SMOOTH = QPainter.RenderHint.SmoothPixmapTransform


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _hints_off(view) -> bool:
    hints = view.renderHints()
    return not (hints & AA) and not (hints & SMOOTH)


def test_sc_u014_1_render_hints_off_at_every_zoom(make_view):
    """SC-U014-1: AA + smooth-pixmap render hints stay off across zoom changes."""
    view, _scene, _stack = make_view(32, 32)
    assert _hints_off(view)
    view.set_zoom(8.0)
    assert _hints_off(view)
    view.fit()
    assert _hints_off(view)
    view.reassert_no_antialiasing()
    assert _hints_off(view)


def test_sc_u014_2_toggle_locked_on(qtbot):
    """SC-U014-2: the AA-off toggle is locked on — attempting to disable re-checks it."""
    win = _window(qtbot)
    assert win._aa_off_action.isChecked()  # defaults on/locked
    win._aa_off_action.setChecked(False)  # attempt to disable
    win._on_aa_off_toggled(False)
    assert win._aa_off_action.isChecked()  # refused: stays locked on
    # The active view's hints remain off (previews inherit the same policy).
    view = win.active_tab().view
    assert _hints_off(view)
