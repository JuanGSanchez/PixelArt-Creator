"""Main-window slot/wiring + branch coverage (REQ-P1-UI-017..020, -025).

Covers reachable window slots and guards: close-document, colour-picked
propagation, zoom/fit/grid/theme/language slots, save/open round-trip (direct +
via monkeypatched file dialogs), and the no-active-tab guards. Native file
dialogs are monkeypatched so nothing blocks headless. Both themes.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFileDialog

from pixelart_creator.data.project_io import FILE_SUFFIX
from pixelart_creator.logic.constants import ZOOM_MAX, ZOOM_MIN
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import THEME_DARK, build_qss
from tests.ui._ui_helpers import click_pixel, prepare_for_click

BLACK = (0, 0, 0, 255)
BLUE = (40, 90, 220, 255)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_close_document_removes_tab(qtbot):
    """close_document removes the tab and detaches its undo stack."""
    win = _window(qtbot)
    win.new_document()
    count = win._tab_widget.count()
    win.close_document(0)
    assert win._tab_widget.count() == count - 1
    win.close_document(999)  # out-of-range index is a safe no-op
    assert win._tab_widget.count() == count - 1


def test_colour_picked_signal_propagates(qtbot):
    """A view colorPicked signal sets the window's active colour + swatch."""
    win = _window(qtbot)
    record = win.active_tab()
    record.view.colorPicked.emit(BLACK)  # BLACK is in the starter palette
    assert win._active_color == BLACK


def test_palette_panel_selected_colour_none_when_empty(qtbot):
    """Palette_Panel.selected_color() is None with no selection."""
    win = _window(qtbot)
    win._palette_panel._list.clearSelection()
    assert win._palette_panel.selected_color() is None


def test_zoom_and_fit_slots(qtbot):
    """Zoom-in/out/fit actions drive the active view's zoom within range
    (REQ-P1-UI-017..020). Regression for the 2026-08-24 field defect: the
    lower zoom bound is ``min(ZOOM_MIN, fit_zoom)`` -- never a flat
    ``fit_zoom`` (which made ``zoom_out()`` RAISE the zoom and left the 1.0
    preset stop unreachable for a small document) and never a flat
    ``ZOOM_MIN`` (which would make the whole-grid view unreachable for a
    document larger than the viewport, e.g. 7680x4320)."""
    win = _window(qtbot)
    view = win.active_tab().view
    floor = min(ZOOM_MIN, view._fit_zoom())

    win._zoom_in_action.trigger()
    zoomed_in = view.zoom()
    assert floor <= zoomed_in <= ZOOM_MAX

    win._zoom_out_action.trigger()
    zoomed_out = view.zoom()
    assert zoomed_out < zoomed_in  # zoom_out() must DECREASE the zoom
    assert floor <= zoomed_out <= ZOOM_MAX

    # Drive the raw clamp far below the floor to prove the RULE, not today's
    # arithmetic: the achievable minimum is always min(ZOOM_MIN, fit_zoom),
    # so this stays true whether the default canvas is small or huge.
    view.set_zoom(0.0)
    assert view.zoom() == pytest.approx(floor)

    win._fit_action.trigger()
    assert view.zoom() == view._fit_zoom()


def test_grid_toggle_slot(qtbot):
    """The View>Grid action toggles the scene grid overlay."""
    win = _window(qtbot)
    win._grid_action.setChecked(True)
    assert win.active_tab().scene.is_grid_enabled() is True


def test_theme_switch_applies_qss(qtbot):
    """set_theme swaps the application QSS (runtime theme switch, 025)."""
    win = _window(qtbot)
    win.set_theme(THEME_DARK)
    assert win._app.styleSheet() == build_qss(THEME_DARK)


def test_language_action_switches_language(qtbot):
    """Triggering a language action drives the LanguageManager."""
    win = _window(qtbot)
    actions = win._language_menu.actions()
    actions[0].trigger()  # 'en'
    assert win._language_manager.current_language() == actions[0].data()


def test_save_then_open_round_trip(qtbot, tmp_path):
    """save_document then open_document round-trip a .pixproj tab (020)."""
    win = _window(qtbot)
    record = win.active_tab()
    prepare_for_click(record.view)
    record.view.set_active_color(BLUE)
    click_pixel(record.view, 5, 5)
    path = str(tmp_path / f"proj{FILE_SUFFIX}")
    win.save_document(path)
    opened = win.open_document(path)
    assert opened.frames[0].layers[-1].buffer.get_pixel(5, 5) == BLUE


def test_open_and_save_via_dialogs(qtbot, tmp_path, monkeypatch):
    """_on_open / _on_save route through the file dialogs (dialogs mocked)."""
    win = _window(qtbot)
    path = str(tmp_path / f"dlg{FILE_SUFFIX}")
    win.save_document(path)  # seed a file to open
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (path, ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (path, ""))
    before = win._tab_widget.count()
    win._on_open()
    assert win._tab_widget.count() == before + 1
    win._on_save()  # delegates to _on_save_as -> save_document(path)


def test_dialog_slots_cancelled_are_noops(qtbot, monkeypatch):
    """Cancelling the file dialogs (empty path) changes nothing."""
    win = _window(qtbot)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    before = win._tab_widget.count()
    win._on_open()
    win._on_save_as()
    assert win._tab_widget.count() == before


def test_no_active_tab_slots_are_safe(qtbot):
    """With no open document, the context slots guard against a missing tab."""
    win = _window(qtbot)
    while win._tab_widget.count():
        win.close_document(0)
    assert win.active_tab() is None
    # None of these raise with no active document.
    win._on_zoom_in()
    win._on_zoom_out()
    win._on_fit()
    win._on_grid_toggled(True)
    win._on_save_as()
    win.save_document("unused.pixproj")
    assert win.active_document() is None
