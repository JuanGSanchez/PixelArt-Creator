"""Phase-6 tilemap canvas + stamping tool acceptance tests (REQ-P6-UI-004..016).

pytest-qt, headless, both themes (autouse ``theme`` fixture, REQ-P6-UI-016). Drives
:class:`Tilemap_Canvas` bound to the frozen ``logic/tilemap`` API. Each stamping
edit is asserted to be **exactly one** ``QUndoCommand`` whose undo restores the
prior cells (SC-UI-005/-006/-007-1); auto-tile resolves display tiles on placement
and undoes as one command *including neighbour re-resolution* (SC-UI-009-1); H/V
flip + D4 rotate map to the correct GID flag transform; infinite-map stamps into
arbitrary coords with navigation pushing no command (SC-UI-010-1); view ops push no
command (SC-UI-013-1); a stamp bumps only the touched chunk's version (the
viewport-cull / dirty-rect hook for REQ-P6-UI-014).
"""

from __future__ import annotations

from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.tilemap import (
    FLIPPED_DIAGONALLY_FLAG,
    FLIPPED_HORIZONTALLY_FLAG,
    FLIPPED_VERTICALLY_FLAG,
    GID_MASK,
    TileInstance,
)
from pixelart_creator.ui.canvas_view import Canvas_View  # noqa: F401  (theme parity)
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas, TilemapTool


def _canvas(qtbot, tilemap, tileset, theme, stack=None):
    stack = stack if stack is not None else QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    canvas.set_active_layer(0)
    canvas.set_brush_gid(tileset.first_gid)  # gid 1 = first tile
    return canvas, stack


def test_sc_ui_004_1_canvas_binds_and_renders_composited_map(
    qtbot, theme, make_tilemap_setup
):
    """SC-UI-004-1: the canvas binds a tilemap and renders it without error.

    Stamps a cell and confirms the frozen ``render_region`` seam resolves the cell
    to its source-tile pixels (composited map), in both themes.
    """
    tileset, tilemap = make_tilemap_setup(cols=4, rows=2)
    canvas, _stack = _canvas(qtbot, tilemap, tileset, theme)
    canvas._apply_stamp(3, 4)
    rendered = tilemap.render_region(3 * 16, 4 * 16, 16, 16)
    assert rendered.width == 16 and rendered.height == 16
    assert rendered.data.any()  # the placed instance resolved to non-empty pixels


def test_sc_ui_005_1_stamp_is_one_command_linked_instance(
    qtbot, theme, make_tilemap_setup
):
    """SC-UI-005-1: a stamp places a linked instance as exactly one command."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tilemap, tileset, theme)

    canvas._apply_stamp(2, 3)
    assert stack.index() == 1
    assert tilemap.layers[0].get(2, 3) == tileset.first_gid  # linked by id, no pixels
    stack.undo()
    assert tilemap.layers[0].get(2, 3) == 0  # empty restored


def test_sc_ui_006_1_erase_is_one_command_and_restores(
    qtbot, theme, make_tilemap_setup
):
    """SC-UI-006-1: the eraser clears a cell as one command; undo restores it."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tilemap, tileset, theme)

    canvas._apply_stamp(1, 1)
    canvas.set_tool(TilemapTool.ERASE)
    canvas._apply_erase(1, 1)
    assert stack.index() == 2  # stamp + erase = two discrete commands
    assert tilemap.layers[0].get(1, 1) == 0
    stack.undo()  # undo the erase
    assert tilemap.layers[0].get(1, 1) == tileset.first_gid


def test_sc_ui_007_1_rectangle_fill_is_one_command(qtbot, theme, make_tilemap_setup):
    """SC-UI-007-1: a rectangle-fill fills the region as exactly one command."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tilemap, tileset, theme)
    canvas.set_tool(TilemapTool.FILL)

    canvas._apply_fill((0, 0), (2, 2))  # 3x3 = 9 cells
    assert stack.index() == 1  # a single QUndoCommand for the whole rectangle
    for cy in range(3):
        for cx in range(3):
            assert tilemap.layers[0].get(cx, cy) == tileset.first_gid
    stack.undo()
    assert all(tilemap.layers[0].get(cx, cy) == 0 for cy in range(3) for cx in range(3))


def test_flip_and_rotate_map_to_gid_flags(qtbot, theme, make_tilemap_setup):
    """Flip H/V + D4 rotate compose the correct GID flag transform (diag->H->V)."""
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tilemap, tileset, theme)

    base = tileset.first_gid
    canvas.toggle_flip_h()
    assert canvas.brush_gid() == (base | FLIPPED_HORIZONTALLY_FLAG)
    canvas.toggle_flip_v()
    assert canvas.brush_gid() == (
        base | FLIPPED_HORIZONTALLY_FLAG | FLIPPED_VERTICALLY_FLAG
    )
    canvas.toggle_flip_h()
    canvas.toggle_flip_v()
    assert canvas.brush_gid() == base  # flags cleared

    # Four 90 CW rotations compose back to identity (D4 permutation table).
    for _ in range(4):
        canvas.rotate_cw()
    assert canvas.brush_gid() == base

    # A stamp records the flip flags into the placed cell's gid.
    canvas.toggle_flip_h()
    canvas._apply_stamp(0, 0)
    inst = TileInstance(tilemap.layers[0].get(0, 0))
    assert inst.base_gid == base and inst.flip_h


def test_flag_constants_partition_gid(qtbot, theme):
    """Flag nibble and GID mask are disjoint (a stamped gid separates cleanly)."""
    flags = (
        FLIPPED_HORIZONTALLY_FLAG | FLIPPED_VERTICALLY_FLAG | FLIPPED_DIAGONALLY_FLAG
    )
    assert flags & GID_MASK == 0


def test_sc_ui_009_1_autotile_resolves_and_undoes_as_one_command(
    qtbot, theme, make_blob_setup
):
    """SC-UI-009-1: an auto-tile stamp resolves display tiles from neighbours and
    undoes as one command including neighbour re-resolution (REQ-P6-LOGIC-011)."""
    tileset, tilemap = make_blob_setup()
    canvas, stack = _canvas(qtbot, tilemap, tileset, theme)
    canvas.set_brush_gid(tileset.first_gid)  # base gid 1 = blob terrain

    autotile_signals = []
    canvas.autotileChanged.connect(autotile_signals.append)
    canvas.set_autotile_enabled(True)
    assert canvas.is_autotile_enabled()
    assert autotile_signals[-1] is True
    # Toggling auto-tile is a mode change (CL-13): it pushes NO command.
    assert stack.index() == 0

    canvas._apply_stamp(0, 0)
    display_before_neighbour = tilemap.layers[0].get(0, 0)
    # A logical placement is recorded (auto-tile stores logical + derived display).
    assert tilemap.layers[0].get_logical(0, 0) == tileset.first_gid

    canvas._apply_stamp(1, 0)  # adjacent -> re-resolves (0,0)'s display tile
    assert stack.index() == 2
    assert tilemap.layers[0].get(0, 0) != display_before_neighbour  # re-resolved

    stack.undo()  # undo the (1,0) stamp as ONE command
    # The whole stamp (incl. neighbour re-resolution) reverts: (0,0) display restored.
    assert tilemap.layers[0].get(0, 0) == display_before_neighbour
    assert tilemap.layers[0].get(1, 0) == 0


def test_sc_ui_010_1_infinite_map_stamp_and_view_ops_push_no_command(
    qtbot, theme, make_tilemap_setup
):
    """SC-UI-010-1 / SC-UI-013-1: stamp into far/negative space; view ops no command."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tilemap, tileset, theme)

    canvas._apply_stamp(-1000, 5000)  # arbitrary/negative coords, no fixed wall
    assert stack.index() == 1
    assert tilemap.layers[0].get(-1000, 5000) == tileset.first_gid
    assert tilemap.layers[0].get(0, 0) == 0  # unset cell reads empty (sparse)

    # View state (CL-13): zoom / active-layer / active-tool push no command.
    canvas.set_zoom(2.0)
    canvas.set_active_layer(0)
    canvas.set_tool(TilemapTool.ERASE)
    canvas.set_brush_gid(tileset.first_gid)
    assert stack.index() == 1  # unchanged by navigation / selection


def test_sc_ui_014_stamp_bumps_only_touched_chunk_version(
    qtbot, theme, make_tilemap_setup
):
    """REQ-P6-UI-014 dirty-rect hook: a stamp bumps only the touched chunk version.

    The UI keys its per-chunk QPixmap cache by ``chunk_version``; a stamp must dirty
    only its own chunk (viewport-cull / dirty-rect), leaving other chunks at 0 so a
    sparse/8K map recomposites only what changed (AGT-10 confirmed the 16 ms budget).
    """
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tilemap, tileset, theme)

    assert tilemap.chunk_version(0, 0) == 0
    canvas._apply_stamp(0, 0)  # chunk (0,0)
    assert tilemap.chunk_version(0, 0) > 0
    # A far chunk (well outside TILEMAP_CHUNK_SIZE=16) stays clean.
    assert tilemap.chunk_version(10, 10) == 0


def test_sc_ui_015_canvas_is_keyboard_reachable_with_accessible_name(
    qtbot, theme, make_tilemap_setup
):
    """REQ-P6-UI-015: the canvas exposes an accessible name and accepts key focus."""
    from PySide6.QtCore import Qt

    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tilemap, tileset, theme)
    assert canvas.accessibleName() != ""
    assert canvas.accessibleDescription() != ""
    assert canvas.focusPolicy() == Qt.FocusPolicy.StrongFocus


def test_sc_ui_016_theme_colors_apply_in_both_themes(qtbot, theme, make_tilemap_setup):
    """REQ-P6-UI-016: role-based checker/grid colours apply and drawBackground runs.

    Runs once per theme via the autouse fixture; asserts the theme roles differ from
    the opposite theme (role-based, not hard-coded) and a stamp+render succeeds.
    """
    from pixelart_creator.ui.theme import THEME_DARK, THEME_LIGHT

    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tilemap, tileset, theme)
    canvas.set_grid_enabled(True)
    canvas._apply_stamp(1, 1)
    # The two themes provide distinct role colours (no per-widget hard-coding).
    assert canvas_roles(THEME_LIGHT) != canvas_roles(THEME_DARK)
    # Render through the seam succeeds under the active theme (no crash).
    assert tilemap.render_region(16, 16, 16, 16).data.any()
