"""Phase-6 tilemap UI trivial getters + remaining guard branches (coverage completion).

pytest-qt, headless, both themes. Exercises the small accessor/guard branches the
behavioural tests skip: canvas getters, edits with an out-of-range active layer,
auto-tile toggle on a bad layer index, unhandled mouse buttons falling through to the
base class, a layer-visibility factory error, and tileset-editor edit/reslice guards.
Pure UI-guard coverage; no domain logic.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QUndoStack

from pixelart_creator.ui import tilemap_layer_panel as tlp_module
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas, TilemapTool
from pixelart_creator.ui.tilemap_layer_panel import Tilemap_Layer_Panel
from pixelart_creator.ui.tileset_editor_panel import Tileset_Editor_Panel


def test_canvas_getters(qtbot, theme, make_tilemap_setup):
    """Trivial canvas accessors return their set values."""
    tileset, tilemap = make_tilemap_setup()
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    canvas.set_tool(TilemapTool.FILL)
    assert canvas.active_tool() is TilemapTool.FILL
    canvas.set_active_layer(0)
    assert canvas.active_layer() == 0
    new_stack = QUndoStack()
    canvas.set_undo_stack(new_stack)
    canvas.set_brush_gid(tileset.first_gid)
    assert canvas.brush_gid() == tileset.first_gid


def test_edit_with_bad_active_layer_is_noop(qtbot, theme, make_tilemap_setup):
    """An out-of-range active layer makes stamp/auto-tile safe no-ops (guards)."""
    tileset, tilemap = make_tilemap_setup()
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    canvas.set_brush_gid(tileset.first_gid)
    canvas.set_active_layer(99)  # out of range
    canvas._apply_stamp(0, 0)
    canvas.set_autotile_enabled(True)  # bad layer -> early return
    assert stack.index() == 0
    assert canvas.is_autotile_enabled() is False


def test_unhandled_mouse_button_falls_through(qtbot, theme, make_tilemap_setup):
    """A right-button press / idle move fall through to the base class (no crash)."""
    tileset, tilemap = make_tilemap_setup()
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(5, 5),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(press)  # not left/middle -> super()
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(6, 6),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(move)  # not panning / not drawing -> super()
    assert stack.index() == 0


def test_layer_visibility_factory_error_warns(qtbot, monkeypatch, make_tilemap_setup):
    """A visibility-command factory error surfaces a warning, pushes no command."""
    from pixelart_creator.logic.tilemap import Tilemap, TilemapError

    _tileset, tilemap = make_tilemap_setup(layers=1)
    stack = QUndoStack()
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tilemap, stack, None)
    warnings = []
    monkeypatch.setattr(
        tlp_module.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )

    def _boom(*_a, **_k):
        raise TilemapError("nope")

    monkeypatch.setattr(Tilemap, "make_set_layer_visibility_command", _boom)
    panel._list.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert warnings
    assert stack.index() == 0


def test_tileset_editor_edit_and_push_guards(qtbot, theme, make_tilemap_setup):
    """Reslice with no stack and edit with no selection are safe no-ops."""
    tileset, _tilemap = make_tilemap_setup()
    panel = Tileset_Editor_Panel()
    qtbot.addWidget(panel)
    # Bind with NO undo stack: a reslice builds the command but _push returns early.
    panel.set_context(tileset, None, None)
    panel._on_reslice()  # _push with stack None -> early return (no crash)
    # No tile selected -> edit is a no-op.
    panel._grid.setCurrentRow(-1)
    panel._on_edit_tile()

    # And with no tileset bound at all, both actions return immediately.
    empty = Tileset_Editor_Panel()
    qtbot.addWidget(empty)
    empty._on_reslice()
    empty._on_edit_tile()
    assert empty.active_gid() is None
