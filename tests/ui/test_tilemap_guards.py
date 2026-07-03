"""Phase-6 tilemap UI guard + error-path coverage (defensive behaviour).

pytest-qt, headless, both themes (autouse fixture). Exercises the defensive guards
and typed-error surfaces of the tilemap UI that the happy-path acceptance tests skip:
a stamp/fill with an unknown gid or empty brush is a no-op / user-facing warning (no
crash); edits with no bound tilemap return early; layer-op factory errors surface a
warning; the auto-tile disable path clears the ruleset; and the export dialog surfaces
a write error. All assert the UI never crashes and never pushes a spurious command.
"""

from __future__ import annotations

from PySide6.QtGui import QUndoStack

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.ui import tilemap_canvas as tc_module
from pixelart_creator.ui import tilemap_io_actions as io_actions
from pixelart_creator.ui import tilemap_layer_panel as tlp_module
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas, TilemapTool
from pixelart_creator.ui.tilemap_layer_panel import Tilemap_Layer_Panel

# --- canvas guards --------------------------------------------------------- #


def _canvas(qtbot, tilemap, tileset, theme):
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    canvas.set_active_layer(0)
    if tileset is not None:
        canvas.set_brush_gid(tileset.first_gid)
    return canvas, stack


def test_stamp_with_empty_brush_is_noop(qtbot, theme, make_tilemap_setup):
    """A zero (empty) brush gid stamps nothing and pushes no command."""
    _tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tilemap, None, theme)
    canvas.set_brush_gid(0)
    canvas._apply_stamp(0, 0)
    assert stack.index() == 0


def test_edits_with_no_tilemap_return_early(qtbot, theme):
    """Stamp / erase / fill with no bound tilemap are safe no-ops."""
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(None, stack, None)
    canvas._apply_stamp(0, 0)
    canvas._apply_erase(0, 0)
    canvas._apply_fill((0, 0), (1, 1))
    assert stack.index() == 0
    assert canvas.is_autotile_enabled() is False  # no tilemap -> False guard


def test_stamp_and_fill_unknown_gid_warn_without_crash(
    qtbot, theme, monkeypatch, make_tilemap_setup
):
    """An unknown gid surfaces a warning (TilemapError) and pushes no command."""
    tileset, tilemap = make_tilemap_setup(cols=4, rows=2)  # gids 1..8 valid
    canvas, stack = _canvas(qtbot, tilemap, tileset, theme)
    warnings = []
    monkeypatch.setattr(
        tc_module.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )

    canvas.set_brush_gid(9999)  # not in any referenced tileset
    canvas._apply_stamp(0, 0)
    canvas.set_tool(TilemapTool.FILL)
    canvas._apply_fill((0, 0), (1, 1))
    assert len(warnings) == 2  # stamp + fill each warned
    assert stack.index() == 0  # neither pushed a command


def test_autotile_disable_clears_ruleset(qtbot, theme, make_blob_setup):
    """Disabling auto-tile clears the layer ruleset and emits False (mode change)."""
    tileset, tilemap = make_blob_setup()
    canvas, stack = _canvas(qtbot, tilemap, tileset, theme)
    canvas.set_brush_gid(tileset.first_gid)
    canvas.set_autotile_enabled(True)
    assert canvas.is_autotile_enabled()
    emitted = []
    canvas.autotileChanged.connect(emitted.append)
    canvas.set_autotile_enabled(False)
    assert canvas.is_autotile_enabled() is False
    assert emitted[-1] is False
    assert stack.index() == 0  # toggling never pushes a command (CL-13)


def test_wheel_at_max_zoom_is_noop(qtbot, theme, make_tilemap_setup):
    """A wheel-in already at max zoom is a safe no-op (clamp early-return)."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tilemap, tileset, theme)
    canvas._apply_stamp(0, 0)
    canvas.set_zoom(1e9)  # clamps to ZOOM_MAX
    ev = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    canvas.wheelEvent(ev)  # target == zoom -> early accept, no crash


# --- layer-panel guards ---------------------------------------------------- #


def _panel(qtbot, tilemap):
    stack = QUndoStack()
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tilemap, stack, None)
    return panel, stack


def test_layer_ops_with_no_tilemap_are_noops(qtbot):
    """Add / remove / move with no bound tilemap are safe no-ops."""
    stack = QUndoStack()
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(None, stack, None)
    panel._on_add()
    panel._on_remove()
    panel._on_move_up()
    assert stack.index() == 0
    assert panel.active_layer() is None
    assert panel._row_layer_index(999) is None  # absent row -> None


def test_set_autotile_checked_does_not_emit(qtbot, make_tilemap_setup):
    """set_autotile_checked reflects state WITHOUT re-emitting the toggle signal."""
    _tileset, tilemap = make_tilemap_setup()
    panel, _stack = _panel(qtbot, tilemap)
    emitted = []
    panel.autotileToggled.connect(emitted.append)
    panel.set_autotile_checked(True)
    panel.set_autotile_checked(False)
    assert emitted == []  # blocked signals: reflection only


def test_layer_factory_errors_surface_warnings(qtbot, monkeypatch, make_tilemap_setup):
    """A layer-op factory raising TilemapError surfaces a warning, pushes no command."""
    from pixelart_creator.logic.tilemap import Tilemap, TilemapError

    _tileset, tilemap = make_tilemap_setup(layers=1)
    panel, stack = _panel(qtbot, tilemap)
    panel._on_add()  # 2 layers so remove/move have a valid selection
    panel._list.setCurrentRow(0)
    warnings = []
    monkeypatch.setattr(
        tlp_module.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )

    def _boom(*_a, **_k):
        raise TilemapError("boom")

    monkeypatch.setattr(Tilemap, "make_add_layer_command", _boom)
    monkeypatch.setattr(Tilemap, "make_remove_layer_command", _boom)
    monkeypatch.setattr(Tilemap, "make_move_layer_command", _boom)
    index_before = stack.index()
    panel._on_add()
    panel._on_remove()
    panel._on_move_up()
    assert len(warnings) == 3
    assert stack.index() == index_before  # no spurious commands


def test_visibility_unchanged_pushes_no_command(qtbot, make_tilemap_setup):
    """Re-setting a layer's visibility to its current value pushes no command."""
    from PySide6.QtCore import Qt

    _tileset, tilemap = make_tilemap_setup(layers=1)
    panel, stack = _panel(qtbot, tilemap)
    item = panel._list.item(0)
    # Layer is visible; setting Checked again is a no-op (no state change).
    item.setCheckState(Qt.CheckState.Checked)
    assert stack.index() == 0


# --- io-action guards ------------------------------------------------------ #


def test_export_write_error_surfaces_warning(
    qtbot, monkeypatch, tmp_path, make_tilemap_setup
):
    """A write failure during export surfaces a warning and returns None (no crash)."""
    from PySide6.QtWidgets import QWidget

    _tileset, tilemap = make_tilemap_setup()
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(
        io_actions.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(tmp_path / "x.tmj"), "")),
    )

    def _boom(*_a, **_k):
        raise ProjectIOError("disk full")

    monkeypatch.setattr(io_actions, "write_tiled_json", _boom)
    warnings = []
    monkeypatch.setattr(
        io_actions.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )

    assert io_actions.export_tilemap_dialog(parent, tilemap) is None
    assert warnings
