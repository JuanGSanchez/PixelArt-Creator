"""Phase-6 Main_Window tilemap integration (docks, menu, a11y, .pixproj v4 round-trip).

pytest-qt, headless, both themes (autouse ``theme`` fixture). Confirms the 3 new
docks (tileset editor, tilemap layer panel, tilemap canvas) and the ``Tile&map``
menu exist with translatable titles + accessible names (REQ-P6-UI-001/-004/-008/-015/
-016); that a new tilemap can be created through the UI; and that a document's
tilesets + tilemaps round-trip through the UI's own File▸Save/Open path via
``.pixproj`` v4 (REQ-P6-DATA-004) with linked instances restored identically.
"""

from __future__ import annotations

from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot):
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_phase6_docks_and_menu_exist_with_titles(qtbot, theme):
    """REQ-P6-UI-001/-004/-008/-015/-016: the 3 docks + Tile&map menu are present."""
    win = _window(qtbot)
    assert win._tileset_dock.windowTitle() != ""
    assert win._tilemap_layer_dock.windowTitle() != ""
    assert win._tilemap_dock.windowTitle() != ""
    assert win._tilemap_menu.title() != ""
    # The tilemap surfaces expose accessible names (a11y, both themes).
    assert win._tileset_editor.accessibleName() != ""
    assert win._tilemap_layer_panel.accessibleName() != ""
    assert win._tilemap_canvas.accessibleName() != ""


def test_phase6_menu_actions_have_labels(qtbot, theme):
    """REQ-P6-UI-005..012/-015: every Tile&map action carries a non-empty label."""
    win = _window(qtbot)
    for action in (
        win._new_tileset_action,
        win._new_tilemap_action,
        win._stamp_action,
        win._erase_tile_action,
        win._fill_tile_action,
        win._stamp_flip_h_action,
        win._stamp_flip_v_action,
        win._stamp_rotate_action,
        win._import_tiled_action,
        win._export_tiled_action,
    ):
        assert action.text() != ""


def test_new_tilemap_through_ui_binds_canvas(qtbot, theme):
    """REQ-P6-UI-004: creating a tilemap through the UI binds the canvas surfaces."""
    win = _window(qtbot)
    win._on_new_tilemap()
    record = win.active_tab()
    assert record.document.tilemaps  # a tilemap now lives in the document
    assert win._active_tilemap is not None


def test_export_with_no_tilemap_is_graceful(qtbot, theme, monkeypatch):
    """REQ-P6-UI-011: exporting with no active tilemap informs the user, no crash."""
    from pixelart_creator.ui import main_window as mw_module

    win = _window(qtbot)
    win._active_tilemap = None
    infos = []
    monkeypatch.setattr(
        mw_module.QMessageBox, "information", lambda *a, **k: infos.append(a)
    )
    win._on_export_tiled()
    assert infos  # a user-facing info box, not an exception


def test_sc_d004_1_pixproj_v4_round_trip_through_ui(
    qtbot, theme, tmp_path, make_tilemap_setup
):
    """SC-D004-1 / REQ-P6-DATA-004: tilesets + tilemaps round-trip via the UI save/open.

    Builds a tileset + tilemap on the active document, stamps a linked instance,
    saves through ``Main_Window.save_document`` (project_io v4) and reopens through
    ``Main_Window.open_document`` — the reopened document restores the tileset and
    the stamped instance identically.
    """
    win = _window(qtbot)
    record = win.active_tab()
    tileset, tilemap = make_tilemap_setup(cols=4, rows=2)
    record.document.make_add_tileset_command(tileset).execute()
    record.document.make_add_tilemap_command(tilemap).execute()
    tilemap.make_stamp_command(0, 3, 4, tileset.first_gid).execute()

    path = str(tmp_path / "project.pixproj")
    win.save_document(path)
    reopened = win.open_document(path)

    assert len(reopened.tilesets) == 1
    assert len(reopened.tilemaps) == 1
    # The linked instance (id + orientation) survives the native round-trip.
    assert reopened.tilemaps[0].layers[0].get(3, 4) == tileset.first_gid


def test_pixproj_back_compat_loads_tilemap_less_project(qtbot, theme, tmp_path):
    """REQ-P6-DATA-004 back-compat: a project without tilemap data still opens."""
    win = _window(qtbot)
    path = str(tmp_path / "plain.pixproj")
    win.save_document(path)  # active doc has no tilesets/tilemaps
    reopened = win.open_document(path)
    assert reopened.tilesets == []
    assert reopened.tilemaps == []
