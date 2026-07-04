"""Deterministic teardown / xdist segfault-class guard for the Phase-9 aids.

The recurring PySide6 hazard is a live worker thread or connected signal carrier
surviving into a later test's GC, cross-thread-GC-ing Qt C++ objects and crashing
the worker under ``pytest -n auto`` (the Phase-5/6 contract). The Phase-9 aids own
NO worker threads (they are non-destructive view/session state), so the guard here
is that their windows/views shut down deterministically and leave nothing live:
the multi-view controller closes every extra view and the reference board closes
cleanly, so a following test's GC finds no dangling top-level aid widget.
"""

from __future__ import annotations

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.multi_view import Multi_View


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_multi_view_close_all_leaves_no_open_view(qtbot, make_view):
    """close_all() disposes every extra view deterministically (no survivor)."""
    _view, scene, _stack = make_view(16, 16)
    mv = Multi_View(scene)
    a = mv.open_view()
    b = mv.open_view()
    qtbot.addWidget(a)
    qtbot.addWidget(b)
    assert mv.count() == 2
    mv.close_all()
    assert mv.count() == 0
    assert mv.views() == []


def test_window_teardown_wiring_closes_aids(qtbot):
    """The window's own teardown path closes the aids without error (segfault guard).

    Opening a view + showing the board then invoking the window's aid-teardown
    (``_multi_view.close_all`` / ``_reference_board.close``) must leave no open
    extra view — the same wiring the window's close path relies on so no aid
    widget survives into a later test's GC under ``pytest -n auto``."""
    win = _window(qtbot)
    win._on_new_view()
    win._on_show_reference_board()
    assert win._multi_view.count() == 1
    # Mirror the window's teardown wiring (main_window close path).
    win._multi_view.close_all()
    win._reference_board.close()
    assert win._multi_view.count() == 0


def test_opening_and_closing_views_is_idempotent(qtbot, make_view):
    """Repeated open/close cycles never accumulate live views (bounded, flat)."""
    _view, scene, _stack = make_view(16, 16)
    mv = Multi_View(scene)
    for _ in range(3):
        v = mv.open_view()
        qtbot.addWidget(v)
        mv.close_all()
        assert mv.count() == 0
