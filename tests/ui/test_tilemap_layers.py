"""Phase-6 tilemap layer-panel acceptance tests (REQ-P6-UI-008/-013 + cache invalidate).

pytest-qt, headless, both themes (autouse ``theme`` fixture). Drives
:class:`Tilemap_Layer_Panel`: add / remove / reorder / visibility each push
**exactly one** ``QUndoCommand`` and undo restores the exact prior order / contents
/ visibility (SC-UI-008-1); selecting the active layer is view state (no undo,
CL-13). Also verifies that a layer op fires the tilemap canvas's **whole-cache
invalidation** (the ``chunk_version`` counter does not cover layer structure, so the
canvas must drop its whole chunk pixmap cache — AGT-05 D-whole-cache).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas
from pixelart_creator.ui.tilemap_layer_panel import Tilemap_Layer_Panel


def _panel(qtbot, tilemap, stack=None, on_changed=None):
    stack = stack if stack is not None else QUndoStack()
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tilemap, stack, on_changed)
    return panel, stack


def _visible_row_of(panel, layer_name):
    """Return the *visible* list row currently showing ``layer_name`` (-1 if absent).

    The list is displayed top-first (row 0 = topmost layer), so a smaller row
    number means "higher in the visible stack" (composites above).
    """
    for row in range(panel._list.count()):
        if panel._list.item(row).text() == layer_name:
            return row
    return -1


def test_sc_ui_008_1_add_layer_is_one_command(qtbot, make_tilemap_setup):
    """SC-UI-008-1: adding a layer pushes exactly one command; undo removes it."""
    _tileset, tilemap = make_tilemap_setup(layers=1)
    panel, stack = _panel(qtbot, tilemap)

    panel._on_add()
    assert stack.index() == 1
    assert len(tilemap.layers) == 2
    stack.undo()
    assert len(tilemap.layers) == 1


def test_sc_ui_008_1_reorder_layer_is_one_reversible_command(qtbot, make_tilemap_setup):
    """SC-UI-008-1: reordering a layer is one command; undo restores the order.

    Selects the MIDDLE visible row so the reorder has a valid neighbour in *either*
    direction, making this test independent of the up/down button *direction* — the
    direction itself is asserted separately in
    ``test_move_up_down_reorder_matches_visible_direction``. This test only proves
    the "exactly one reversible command; undo restores the exact order" contract, so
    it neither depends on nor silently blesses the reorder-direction defect.
    """
    _tileset, tilemap = make_tilemap_setup(layers=3)
    panel, stack = _panel(qtbot, tilemap)
    names = [layer.name for layer in tilemap.layers]

    panel._list.setCurrentRow(1)  # middle row -> a valid reorder either direction
    index_before = stack.index()
    panel._on_move_up()  # a valid reorder that fires the reversible command
    assert stack.index() == index_before + 1
    assert [layer.name for layer in tilemap.layers] != names
    stack.undo()
    assert [layer.name for layer in tilemap.layers] == names


def test_move_up_down_reorder_matches_visible_direction(qtbot, make_tilemap_setup):
    """REQ-P6-UI-008 / SC-UI-008-1: reorder buttons must move in their LABEL direction.

    The list is displayed top-first (row 0 = topmost layer), matching the shipped
    image-layer panel convention (``ui/layer_panel.py``: "above in the list = higher
    z-order"). So **Move Up** must move the selected layer TOWARD row 0 (it rises /
    composites above its neighbour) and **Move Down** must move it toward the bottom.

    REGRESSION EXPOSING AN S3 UX DEFECT (do not xfail -- routes to AGT-05).
    ``_on_move_up`` currently calls ``_move(+1)`` (target_row = row+1), which moves
    the selected layer DOWN the *visible* list, and ``_on_move_down`` calls
    ``_move(-1)`` -- both inverted versus the button labels and the image-panel
    convention. Empirically, Move Up on the middle row sends the layer to the bottom
    row instead of the top row. Expected vs actual for the middle row (row 1) of a
    3-layer map [top: Layer 3, Layer 2, bottom: Layer 1]:
      * Move Up   -> "Layer 2" at visible row 0 (EXPECTED); currently row 2 (ACTUAL).
      * Move Down -> "Layer 2" at visible row 2 (EXPECTED); currently row 0 (ACTUAL).
    Fix (AGT-05, product code): swap the mappings so ``_on_move_up`` -> ``_move(-1)``
    and ``_on_move_down`` -> ``_move(+1)`` (Move Up on the topmost row then becomes a
    correct no-op via the existing bounds guard). This test does NOT paper over the
    defect: it asserts the correct user-facing direction and will pass only once the
    product is fixed.
    """
    # -- Move Up must RAISE the selected layer (toward the top / row 0) ------
    _ts_up, tilemap_up = make_tilemap_setup(layers=3)
    panel_up, _stack_up = _panel(qtbot, tilemap_up)
    # Visible rows: 0="Layer 3" (top), 1="Layer 2", 2="Layer 1" (bottom).
    assert _visible_row_of(panel_up, "Layer 2") == 1
    panel_up._list.setCurrentRow(1)
    panel_up._on_move_up()
    assert _visible_row_of(panel_up, "Layer 2") == 0  # rose one visible row

    # -- Move Down must LOWER the selected layer (toward the bottom) ---------
    _ts_dn, tilemap_dn = make_tilemap_setup(layers=3)
    panel_dn, _stack_dn = _panel(qtbot, tilemap_dn)
    assert _visible_row_of(panel_dn, "Layer 2") == 1
    panel_dn._list.setCurrentRow(1)
    panel_dn._on_move_down()
    assert _visible_row_of(panel_dn, "Layer 2") == 2  # sank one visible row


def test_sc_ui_008_1_visibility_toggle_is_one_reversible_command(
    qtbot, make_tilemap_setup
):
    """SC-UI-008-1: toggling a layer's visibility is one command; undo restores it."""
    _tileset, tilemap = make_tilemap_setup(layers=1)
    panel, stack = _panel(qtbot, tilemap)

    assert tilemap.layers[0].visible is True
    item = panel._list.item(0)
    item.setCheckState(Qt.CheckState.Unchecked)  # fires _on_item_changed
    assert stack.index() == 1
    assert tilemap.layers[0].visible is False
    stack.undo()
    assert tilemap.layers[0].visible is True


def test_sc_ui_008_1_remove_layer_is_one_reversible_command(qtbot, make_tilemap_setup):
    """SC-UI-008-1: removing a layer is one command; undo restores it in place."""
    _tileset, tilemap = make_tilemap_setup(layers=1)
    panel, stack = _panel(qtbot, tilemap)
    panel._on_add()  # [Layer 1, Layer 2]
    names = [layer.name for layer in tilemap.layers]

    panel._list.setCurrentRow(0)
    index_before = stack.index()
    panel._on_remove()
    assert stack.index() == index_before + 1
    assert len(tilemap.layers) == 1
    stack.undo()
    assert [layer.name for layer in tilemap.layers] == names


def test_active_layer_selection_pushes_no_command(qtbot, make_tilemap_setup):
    """CL-13: selecting the active layer is view state — no undo entry."""
    _tileset, tilemap = make_tilemap_setup(layers=1)
    panel, stack = _panel(qtbot, tilemap)
    panel._on_add()
    at_start = stack.index()

    selected = []
    panel.activeLayerChanged.connect(selected.append)
    panel._list.setCurrentRow(1)
    assert selected  # selection signal emitted
    assert stack.index() == at_start  # but nothing pushed onto the undo stack


def test_selected_layer_row_maps_to_its_layer_index(qtbot, make_tilemap_setup):
    """SC-UI-008-1 / SC-UI-005-1: the SELECTED row must target its OWN layer.

    REGRESSION EXPOSING AN S2 DEFECT (do not xfail — routes to AGT-05).
    ``rebuild`` lists layers top-first (reversed) and stores each row's true layer
    index in the item's ``UserRole``, but ``Tilemap_Layer_Panel.active_layer()``
    returns the raw ``currentRow()`` instead of that stored index. With >= 2 layers,
    selecting the visually-top row therefore targets the WRONG layer: remove /
    reorder discard the wrong layer (data loss) and stamps/erases route to the wrong
    layer (``_on_tilemap_layer_changed`` -> ``canvas.set_active_layer(row)``),
    violating REQ-P6-UI-008 ("the active layer receives stamps") + REQ-P6-UI-005/-006.
    Expected: the selected row's ``active_layer()`` equals that row's ``UserRole``
    layer index. Fix: ``active_layer()`` (and ``_on_row_changed``) must resolve the
    row via ``_row_layer_index`` (the stored index), like ``_on_item_changed`` does.
    """
    _tileset, tilemap = make_tilemap_setup(layers=1)
    panel, _stack = _panel(qtbot, tilemap)
    panel._on_add()  # 2 layers: row0 -> layer index 1 (top), row1 -> layer index 0
    panel._list.setCurrentRow(0)
    row_layer_index = panel._list.item(0).data(Qt.ItemDataRole.UserRole)
    assert panel.active_layer() == row_layer_index


def test_layer_op_fires_whole_cache_invalidation(qtbot, theme, make_tilemap_setup):
    """A layer op fires the canvas whole-cache invalidation (AGT-05 D-whole-cache).

    ``chunk_version`` does not cover layer structure, so the canvas must drop its
    whole chunk pixmap cache on a layer op. Populate the cache by rendering a chunk,
    then trigger a panel layer add wired to ``canvas.refresh`` and assert the cache
    is emptied.
    """
    tileset, tilemap = make_tilemap_setup(layers=1)
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    canvas.set_active_layer(0)
    canvas.set_brush_gid(tileset.first_gid)
    canvas._apply_stamp(0, 0)  # give chunk (0,0) content

    # Populate the chunk pixmap cache directly through the scene render path.
    version = tilemap.chunk_version(0, 0)
    canvas._scene._render_chunk(0, 0, version, 0, 0)
    assert canvas._scene._chunk_cache.resident_chunks > 0

    # A layer op wired to the canvas refresh must clear the whole chunk cache.
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tilemap, stack, canvas.refresh)
    panel._on_add()
    assert canvas._scene._chunk_cache.resident_chunks == 0
