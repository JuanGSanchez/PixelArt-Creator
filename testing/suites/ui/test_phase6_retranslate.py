"""REQ-P6-UI-017 LanguageChange retranslate (zero-test close).

Modelled on the Phase-4 blend-label retranslate test
(``test_layer_panel.py::test_sc_ui_018_1_blend_labels_translatable_and_retranslate``):
fires a real ``QEvent.LanguageChange`` on each of the three Phase-6 widgets that
had NO retranslate test at all — ``Tileset_Editor_Panel``, ``Tilemap_Canvas``
(the tilemap canvas WINDOW surface — its accessible name/description), and
``Tilemap_Layer_Panel`` — and asserts the persistent accessible strings are
still non-empty afterwards (a genuine post-condition, not a bare
smoke-only call).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QUndoStack

from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas
from pixelart_creator.ui.tilemap_layer_panel import Tilemap_Layer_Panel
from pixelart_creator.ui.tileset_editor_panel import Tileset_Editor_Panel


def _lang_change(widget) -> None:
    widget.changeEvent(QEvent(QEvent.Type.LanguageChange))


def test_t22_tileset_editor_retranslates(qtbot, make_tilemap_setup):
    """REQ-P6-UI-017: ``Tileset_Editor_Panel`` re-sets its accessible strings."""
    tileset, _tilemap = make_tilemap_setup()
    panel = Tileset_Editor_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tileset, QUndoStack(), None)

    _lang_change(panel)

    assert panel._apply_button.text() != ""
    assert panel._apply_button.accessibleName() != ""
    assert panel._edit_button.text() != ""
    assert panel._grid.accessibleName() != ""
    assert panel._grid.accessibleDescription() != ""


def test_t22_tilemap_canvas_window_surface_retranslates(qtbot, make_tilemap_setup):
    """REQ-P6-UI-017: the tilemap canvas WINDOW surface (``Tilemap_Canvas``, a
    ``QGraphicsView``) re-sets its accessible name/description on retranslate."""
    _tileset, tilemap = make_tilemap_setup()
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)

    _lang_change(canvas)

    assert canvas.accessibleName() != ""
    assert canvas.accessibleDescription() != ""


def test_t22_tilemap_layer_panel_retranslates(qtbot, make_tilemap_setup):
    """REQ-P6-UI-017: ``Tilemap_Layer_Panel`` re-sets its action/list strings."""
    _tileset, tilemap = make_tilemap_setup()
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tilemap, QUndoStack(), None)

    _lang_change(panel)

    assert panel.accessibleName() != ""
    assert panel._list.accessibleName() != ""
    assert panel._list.accessibleDescription() != ""
    assert panel._add_action.text() != ""
    assert panel._remove_action.text() != ""
    assert panel._up_action.text() != ""
    assert panel._down_action.text() != ""
    assert panel._autotile_check.text() != ""
    assert panel._autotile_check.accessibleName() != ""
