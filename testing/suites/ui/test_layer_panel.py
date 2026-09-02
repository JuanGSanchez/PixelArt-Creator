"""Layer-panel + canvas-compositing UI acceptance tests (REQ-P4-UI-001..018).

One pytest-qt test per UI acceptance criterion of ``specs/phase-4-layer-canvas``
(SC-UI-001-1 .. SC-UI-018-1), driving the PySide6 layer panel + composited canvas
headlessly (``QT_QPA_PLATFORM=offscreen``, forced in ``conftest``). Every test also
runs under **both** themes via the autouse ``theme`` fixture, satisfying the global
"executed identically under light and dark" rule and REQ-P4-UI-017.

Scope note: these are UI/integration tests only — the blend maths,
compositor invariants and reversible ``document`` ops are the logic suite's logic tests. Here
we assert the *wiring*: a panel action produces exactly one ``QUndoCommand``, the
canvas composite reflects the change, guards no-op paint, and tabs stay isolated.
Canvas sizes are modest (64x64) — the 8K recomposite frame budget is the performance work's closed
domain and is never exercised functionally here.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QAbstractItemView, QApplication

from pixelart_creator.logic.blend import BlendError, BlendMode, composite_stack
from pixelart_creator.logic.color import blend_over
from pixelart_creator.logic.document import (
    Document,
    Layer,
    LayerGroup,
)
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.layer_panel import Layer_Panel
from pixelart_creator.ui.tools import PencilTool
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]
RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)
BLUE_HALF = (40, 90, 220, 128)


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #


def _rgba_buffer(w: int, h: int, fill) -> PixelBuffer:
    """Return an RGBA buffer of ``fill`` (helper for deterministic setup)."""
    return PixelBuffer(w, h, ColorMode.RGBA, fill=fill)


@pytest.fixture
def layer_env(qtbot, theme):
    """Factory wiring a ``Layer_Panel`` + ``CanvasScene`` + ``Canvas_View``.

    Mirrors ``Main_Window``'s per-tab wiring (the panel drives the scene's
    active layer + mask edit target and shares one ``QUndoStack``) so a test can
    exercise a panel action and observe the composited canvas + undo stack.
    Returns a namespace ``(doc, scene, stack, view, panel)``.
    """

    def _make(names=("Background",), width=64, height=64, mode=ColorMode.RGBA):
        doc = Document(width, height, mode=mode, palette=Palette(STARTER))
        doc.frames[0].layers[0].name = names[0]
        for extra in names[1:]:
            doc.add_layer(extra)
        scene = CanvasScene(doc)
        stack = QUndoStack()
        view = Canvas_View(scene, stack)
        qtbot.addWidget(view)
        prepare_for_click(view)
        view.set_tool(PencilTool())
        view.set_active_color(GREEN)
        panel = Layer_Panel()
        qtbot.addWidget(panel)

        def _on_active(node):
            if isinstance(node, Layer):
                scene.set_active_layer(node)

        panel.activeNodeChanged.connect(_on_active)
        panel.maskEditToggled.connect(scene.set_mask_edit)
        panel.set_context(
            doc,
            stack,
            scene.refresh_all,
            scene.refresh_visible,
            scene.refresh_visible_throttled,
        )
        return SimpleNamespace(
            doc=doc, scene=scene, stack=stack, view=view, panel=panel
        )

    return _make


def _row_for(panel: Layer_Panel, name: str):
    """Return the ``_Node_Row`` for the node named ``name``."""
    for row in panel._rows:
        if row.node().name == name:
            return row
    raise AssertionError(f"no row for layer {name!r}")


def _item_for_path(panel: Layer_Panel, path):
    """Return the tree item whose logic path == ``path``."""
    for item in panel._iter_items():
        if panel._item_path(item) == tuple(path):
            return item
    raise AssertionError(f"no tree item for path {path}")


def _top_level(doc: Document):
    return doc.frames[0].layers


# --------------------------------------------------------------------------- #
# SC-UI-001 — panel lists layers top-first                                    #
# --------------------------------------------------------------------------- #


def test_sc_ui_001_1_panel_lists_layers_top_to_bottom(layer_env):
    """SC-UI-001-1: rows read top-of-stack first (Ink, Sketch, Background)."""
    env = layer_env(names=("Background", "Sketch", "Ink"))
    names = [row.node().name for row in env.panel._rows]
    assert names == ["Ink", "Sketch", "Background"]
    # The top tree item is the topmost logic layer (CL-3).
    top_item = env.panel._tree.topLevelItem(0)
    assert env.panel._item_path(top_item) == (2,)


# --------------------------------------------------------------------------- #
# SC-UI-002 — opacity slider <-> Layer.opacity + recomposite + one command    #
# --------------------------------------------------------------------------- #


def test_sc_ui_002_1_opacity_slider_sets_opacity_one_command(layer_env):
    """SC-UI-002-1: dragging the opacity slider sets opacity as one command."""
    env = layer_env(names=("Background", "Top"))
    row = _row_for(env.panel, "Top")
    row._opacity.setValue(40)  # keyboard/programmatic commit (slider not held)
    assert env.doc.frames[0].layers[1].opacity == pytest.approx(0.4)
    assert env.stack.count() == 1
    # Undo restores the exact prior opacity.
    env.stack.undo()
    assert env.doc.frames[0].layers[1].opacity == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# SC-UI-003 — visibility toggle hides the layer from the composite            #
# --------------------------------------------------------------------------- #


def test_sc_ui_003_1_visibility_toggle_hides_from_composite(layer_env):
    """SC-UI-003-1: toggling visibility off removes the layer from the composite."""
    env = layer_env(names=("Background", "Top"))
    bottom, top = _top_level(env.doc)
    bottom.buffer.fill(RED)
    top.buffer.fill(GREEN)
    env.scene.refresh_all()
    assert env.scene._composite.get_pixel(0, 0) == GREEN  # top wins
    row = _row_for(env.panel, "Top")
    row._vis.setChecked(False)
    assert top.visible is False
    assert env.stack.count() == 1
    assert env.scene._composite.get_pixel(0, 0) == RED  # top gone -> bottom shows


# --------------------------------------------------------------------------- #
# SC-UI-004 — lock toggle makes paint a no-op                                 #
# --------------------------------------------------------------------------- #


def test_sc_ui_004_1_lock_toggle_makes_paint_noop(layer_env):
    """SC-UI-004-1: a locked active layer rejects paint; lock is one command."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    env.scene.set_active_layer(top)
    before = top.buffer.copy()
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)
    assert top.locked is True
    assert env.stack.count() == 1  # only the lock command
    assert env.scene.is_active_editable() is False
    click_pixel(env.view, 5, 5)  # paint attempt on the locked layer
    assert top.buffer == before  # unchanged
    assert env.stack.count() == 1  # paint pushed nothing


# --------------------------------------------------------------------------- #
# SC-UI-005 — blend dropdown lists 12 modes + sets blend_mode + recomposite   #
# --------------------------------------------------------------------------- #


def test_sc_ui_005_1_blend_dropdown_lists_twelve_and_sets_mode(layer_env):
    """SC-UI-005-1: the dropdown offers the 12 modes and selecting one commits."""
    env = layer_env(names=("Background", "Top"))
    row = _row_for(env.panel, "Top")
    assert row._blend.count() == len(list(BlendMode)) == 12
    # Every enum member is present with a non-empty (translatable) label.
    for mode in BlendMode:
        idx = row._blend.findData(mode)
        assert idx >= 0
        assert row._blend.itemText(idx) != ""
    idx = row._blend.findData(BlendMode.MULTIPLY)
    row._blend.setCurrentIndex(idx)
    assert env.doc.frames[0].layers[1].blend_mode is BlendMode.MULTIPLY
    assert env.stack.count() == 1


# --------------------------------------------------------------------------- #
# SC-UI-006 — drag-reorder changes z-order + recomposite + one command        #
# --------------------------------------------------------------------------- #


def test_sc_ui_006_1_drag_reorder_changes_zorder(layer_env):
    """SC-UI-006-1: dragging the bottom layer above the top reorders + recomposites."""
    env = layer_env(names=("A", "B"))  # A bottom, B top
    a, b = _top_level(env.doc)
    a.buffer.fill(RED)
    b.buffer.fill(GREEN)
    env.scene.refresh_all()
    assert env.scene._composite.get_pixel(0, 0) == GREEN  # B (top) shows
    source = _item_for_path(env.panel, (0,))  # A
    target = _item_for_path(env.panel, (1,))  # B
    env.panel.handle_drop(
        source, target, QAbstractItemView.DropIndicatorPosition.AboveItem
    )
    assert env.stack.count() == 1
    # A is now the top-level top -> composite shows RED.
    assert _top_level(env.doc)[-1] is a
    assert env.scene._composite.get_pixel(0, 0) == RED


# --------------------------------------------------------------------------- #
# SC-UI-007 — add / remove / duplicate each push one command; last refused    #
# --------------------------------------------------------------------------- #


def test_sc_ui_007_1_add_duplicate_remove_each_one_command(layer_env):
    """SC-UI-007-1: add, duplicate, remove each change the tree by one command."""
    env = layer_env(names=("Background", "Top"))
    panel = env.panel
    start = len(_top_level(env.doc))
    panel._select_topmost()
    panel._on_add()
    assert len(_top_level(env.doc)) == start + 1
    assert env.stack.count() == 1
    panel._on_duplicate()
    assert len(_top_level(env.doc)) == start + 2
    assert env.stack.count() == 2
    panel._on_remove()
    assert len(_top_level(env.doc)) == start + 1
    assert env.stack.count() == 3


def test_sc_ui_007_1_last_layer_removal_refused(layer_env):
    """SC-UI-007-1: removing the last top-level layer is refused (no command)."""
    env = layer_env(names=("Background",))
    env.panel._select_topmost()
    env.panel._on_remove()
    assert len(_top_level(env.doc)) == 1
    assert env.stack.count() == 0  # refused DocumentError -> no-op


# --------------------------------------------------------------------------- #
# SC-UI-008 — group / ungroup preserve children and are reversible            #
# --------------------------------------------------------------------------- #


def test_sc_ui_008_1_group_then_ungroup_reversible(layer_env):
    """SC-UI-008-1: grouping wraps the layer; ungroup restores it; one cmd each."""
    env = layer_env(names=("Background", "Top"))
    panel = env.panel
    # Select the top-level "Top" layer (path (1,)) and group it.
    panel._select_path((1,))
    panel._on_group()
    assert env.stack.count() == 1
    # A group node now exists in the tree.
    assert any(isinstance(n, LayerGroup) for n in _top_level(env.doc))
    # Select the group and ungroup it.
    grp_path = next(
        (i,) for i, n in enumerate(_top_level(env.doc)) if isinstance(n, LayerGroup)
    )
    panel._select_path(grp_path)
    panel._on_ungroup()
    assert env.stack.count() == 2
    assert not any(isinstance(n, LayerGroup) for n in _top_level(env.doc))
    # Undo the ungroup + the group -> exact prior 2-leaf flat tree.
    env.stack.undo()
    env.stack.undo()
    assert [n.name for n in _top_level(env.doc)] == ["Background", "Top"]


# --------------------------------------------------------------------------- #
# SC-UI-009 — attaching a mask + painting it modulates the composite          #
# --------------------------------------------------------------------------- #


def test_sc_ui_009_1_mask_attach_paint_modulates_layer_unchanged(layer_env):
    """SC-UI-009-1: attach mask (one cmd); mask edit routes paint to the mask;
    the layer's own pixels stay unchanged."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    top.buffer.fill(GREEN)
    env.scene.set_active_layer(top)
    env.panel._select_path((1,))
    env.panel._on_toggle_mask()  # attach mask
    assert top.mask is not None
    assert env.stack.count() == 1
    layer_pixels_before = top.buffer.copy()
    # Route paint to the mask and paint a fully-transparent value into it.
    env.scene.set_mask_edit(True)
    assert env.scene.is_mask_edit() is True
    env.view.set_active_color((0, 0, 0, 0))
    click_pixel(env.view, 3, 3)
    # The mask buffer changed; the layer's own pixels did NOT (non-destructive).
    assert top.mask.get_pixel(3, 3) == (0, 0, 0, 0)
    assert top.buffer == layer_pixels_before


# --------------------------------------------------------------------------- #
# SC-UI-010 — reference layer visible but rejects paint                       #
# --------------------------------------------------------------------------- #


def test_sc_ui_010_1_reference_layer_visible_but_rejects_paint(layer_env):
    """SC-UI-010-1: a reference layer stays composited yet rejects paint."""
    env = layer_env(names=("Background", "Top"))
    bottom, top = _top_level(env.doc)
    bottom.buffer.fill(RED)
    top.buffer.fill(GREEN)
    env.scene.set_active_layer(top)
    env.panel._select_path((1,))
    env.panel._on_reference(True)
    assert top.reference is True
    assert env.stack.count() == 1
    env.scene.refresh_all()
    # Still composited (visible for tracing, CL-8).
    assert env.scene._composite.get_pixel(0, 0) == GREEN
    # Paint is a no-op on a reference layer.
    before = top.buffer.copy()
    assert env.scene.is_active_editable() is False
    click_pixel(env.view, 7, 7)
    assert top.buffer == before


# --------------------------------------------------------------------------- #
# SC-UI-011 — smart layer mirrors its source                                  #
# --------------------------------------------------------------------------- #


def test_sc_ui_011_1_smart_layer_mirrors_source(layer_env):
    """SC-UI-011-1: a smart layer mirrors its source; its own pixels don't count."""
    env = layer_env(names=("Source",))
    source = _top_level(env.doc)[0]
    source.buffer.fill(RED)
    env.panel._select_path((0,))
    env.panel._on_smart()
    assert env.stack.count() == 1
    smart = next(
        n
        for n in _top_level(env.doc)
        if isinstance(n, Layer) and n.smart_source is not None
    )
    assert smart.smart_source is source
    # Edit the source -> the smart layer's contribution mirrors it.
    source.buffer.fill(GREEN)
    env.scene.refresh_all()
    assert env.scene._composite.get_pixel(0, 0) == GREEN
    # The smart layer's OWN pixels are ignored (writing them changes nothing).
    smart.buffer.fill(BLUE)
    env.scene.refresh_all()
    assert env.scene._composite.get_pixel(0, 0) == GREEN  # still the source colour


def test_t19_paint_on_smart_layer_is_rejected(layer_env):
    """QA audit, regression for C-04: a paint tool driven at a smart
    layer lands NO stroke and pushes NO undo entry — ``CanvasScene.is_active_editable``
    now rejects a smart layer (``self._active_layer.smart_source is not None``)
    exactly like a locked or reference layer (REQ-P4-UI-004/-010; the smart
    layer's pixels are derived, not directly editable)."""
    # Regression test for C-04 — proven by reversion in the commit pass.
    env = layer_env(names=("Source",))
    source = _top_level(env.doc)[0]
    env.panel._select_path((0,))
    env.panel._on_smart()
    assert env.stack.count() == 1
    smart = next(
        n
        for n in _top_level(env.doc)
        if isinstance(n, Layer) and n.smart_source is source
    )
    before = smart.buffer.copy()
    stack_count_before = env.stack.count()

    env.scene.set_active_layer(smart)
    assert env.scene.is_active_editable() is False

    click_pixel(env.view, 5, 5)

    assert smart.buffer == before  # no stroke landed
    assert env.stack.count() == stack_count_before  # no undo entry pushed


# --------------------------------------------------------------------------- #
# SC-UI-012-1 — canvas renders the composited stack, not one layer            #
# --------------------------------------------------------------------------- #


def test_sc_ui_012_1_canvas_renders_composite_not_one_layer(layer_env):
    """SC-UI-012-1: the canvas shows BLUE-over-RED, not just the active layer."""
    env = layer_env(names=("Background", "Top"))
    bottom, top = _top_level(env.doc)
    bottom.buffer.fill(RED)
    top.buffer.fill(BLUE_HALF)
    env.scene.refresh_all()
    expected = blend_over(BLUE_HALF, RED)
    assert env.scene._composite.get_pixel(0, 0) == expected
    assert expected != RED and expected != BLUE_HALF  # genuinely composited


# --------------------------------------------------------------------------- #
# SC-UI-012-2 — editing a layer updates the composite (group cache not stale)  #
# --------------------------------------------------------------------------- #


def test_sc_ui_012_2_edit_in_group_updates_composite_no_stale_cache(qtbot, theme):
    """SC-UI-012-2: editing a child inside a group updates the on-canvas composite.

    The group flatten cache is populated by the initial recomposite; a paint on
    the child MUST invalidate it (via the PaintCommand D4 hook) so the region
    recomposite cannot serve a stale flatten. If the cache were stale the composite
    would still show the bottom layer's RED — this asserts it shows the paint.
    """
    doc = Document(64, 64, palette=Palette(STARTER))
    bottom = doc.frames[0].layers[0]
    bottom.name = "Bottom"
    bottom.buffer.fill(RED)
    child = Layer(_rgba_buffer(64, 64, (0, 0, 0, 0)), "Child")  # transparent
    group = LayerGroup("Group", children=[child])
    doc.frames[0].layers = [bottom, group]

    scene = CanvasScene(doc)
    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    prepare_for_click(view)
    view.set_tool(PencilTool())
    view.set_active_color(GREEN)
    scene.set_active_layer(child)

    # Prime the composite (populates any group flatten cache): transparent child
    # over RED -> RED.
    scene.refresh_all()
    assert scene._composite.get_pixel(5, 5) == RED

    # Paint an opaque GREEN pixel on the child (PaintCommand fires the D4
    # invalidate hook), then the region recomposite must reflect it.
    click_pixel(view, 5, 5)
    assert child.buffer.get_pixel(5, 5) == GREEN
    assert scene._composite.get_pixel(5, 5) == GREEN, "stale group cache served"

    # The refresh_all buffer-op path also invalidates: mutate the child directly
    # and recomposite the whole stack.
    child.buffer.set_pixel(9, 9, BLUE)
    scene.refresh_all()
    assert scene._composite.get_pixel(9, 9) == BLUE


# --------------------------------------------------------------------------- #
# SC-UI-013 — every layer op is exactly one undoable command                  #
# --------------------------------------------------------------------------- #


def test_sc_ui_013_1_each_layer_op_is_one_command_undo_restores(layer_env):
    """SC-UI-013-1: representative layer ops each push exactly one command and
    undo restores the exact prior state."""
    env = layer_env(names=("Background", "Top"))
    panel, stack = env.panel, env.stack
    top = _top_level(env.doc)[1]

    # opacity
    _row_for(panel, "Top")._opacity.setValue(30)
    assert stack.count() == 1
    stack.undo()
    assert top.opacity == pytest.approx(1.0)
    stack.redo()
    assert top.opacity == pytest.approx(0.3)

    # visibility (next command)
    _row_for(panel, "Top")._vis.setChecked(False)
    assert stack.count() == 2
    stack.undo()
    assert top.visible is True

    # add then undo removes exactly one
    stack.redo()  # re-hide (restore to count-2 applied state)
    panel._select_topmost()
    n_before = len(_top_level(env.doc))
    panel._on_add()
    assert stack.count() == 3
    assert len(_top_level(env.doc)) == n_before + 1
    stack.undo()
    assert len(_top_level(env.doc)) == n_before


# --------------------------------------------------------------------------- #
# SC-UI-014 — multiple canvases open as isolated tabs                         #
# --------------------------------------------------------------------------- #


def test_sc_ui_014_1_and_2_multi_canvas_isolation(qtbot, theme):
    """SC-UI-014-1/-2: a layer op + undo in tab A never affects tab B, and
    switching tabs switches the active layer context."""
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    # Main_Window opens with a default tab; add two more and isolate the last two.
    win.new_document(64, 64)
    win.new_document(64, 64)
    assert len(win._tabs_data) >= 2
    idx_a, idx_b = len(win._tabs_data) - 2, len(win._tabs_data) - 1
    tab_a, tab_b = win._tabs_data[idx_a], win._tabs_data[idx_b]

    # Activate tab A; the shared panel binds to A (state isolation).
    win._tab_widget.setCurrentIndex(idx_a)
    assert win._layer_panel.document is tab_a.document
    a_before = len(tab_a.document.frames[0].layers)
    b_before = len(tab_b.document.frames[0].layers)

    win._layer_panel._select_topmost()
    win._layer_panel._on_add()
    assert len(tab_a.document.frames[0].layers) == a_before + 1
    assert tab_a.stack.count() == 1
    # Tab B is entirely unaffected.
    assert len(tab_b.document.frames[0].layers) == b_before
    assert tab_b.stack.count() == 0

    tab_a.stack.undo()
    assert len(tab_a.document.frames[0].layers) == a_before
    assert len(tab_b.document.frames[0].layers) == b_before

    # SC-UI-014-2: switching to tab B makes B the active layer context.
    win._tab_widget.setCurrentIndex(idx_b)
    assert win._layer_panel.document is tab_b.document
    assert win._undo_group.activeStack() is tab_b.stack


# --------------------------------------------------------------------------- #
# SC-UI-016 — accessibility: names, keyboard reachability, visible focus      #
# --------------------------------------------------------------------------- #


def test_sc_ui_016_1_layer_panel_accessible_and_keyboard_reachable(layer_env):
    """SC-UI-016-1: panel controls expose accessible names, are focusable, and a
    visible focus indicator is themed by role."""
    env = layer_env(names=("Background", "Top"))
    panel = env.panel
    assert panel.accessibleName() != ""
    assert panel._tree.accessibleName() != ""
    assert panel._tree.accessibleDescription() != ""
    # Every toolbar action carries a label (its accessible name for AT).
    for action in (
        panel._add_action,
        panel._remove_action,
        panel._duplicate_action,
        panel._group_action,
        panel._ungroup_action,
        panel._mask_action,
        panel._mask_edit_action,
        panel._reference_action,
        panel._smart_action,
    ):
        assert action.text() != ""
    # Per-row interactive controls: non-empty accessible name + keyboard-focusable.
    row = _row_for(panel, "Top")
    for ctrl in (row._vis, row._lock, row._opacity, row._blend):
        assert ctrl.accessibleName() != ""
        assert ctrl.focusPolicy() != Qt.FocusPolicy.NoFocus
    # A visible focus indicator is themed once by role (a :focus QSS rule).
    assert ":focus" in QApplication.instance().styleSheet()


# --------------------------------------------------------------------------- #
# SC-UI-017 — both themes render correctly (role-based colours)               #
# --------------------------------------------------------------------------- #


def test_sc_ui_017_1_panel_and_composite_render_in_active_theme(layer_env, theme):
    """SC-UI-017-1: the panel + composite build under the active theme with a
    non-empty role-based stylesheet (the autouse fixture runs this in both)."""
    env = layer_env(names=("Background", "Top"))
    _top_level(env.doc)[0].buffer.fill(RED)
    env.scene.refresh_all()
    assert QApplication.instance().styleSheet() != ""
    assert env.scene._composite is not None
    assert env.scene._composite.get_pixel(0, 0) == RED
    # The panel built rows for both layers under this theme.
    assert len(env.panel._rows) == 2


# --------------------------------------------------------------------------- #
# SC-UI-018 — i18n: tr()-wrapped labels incl. blend labels + retranslate       #
# --------------------------------------------------------------------------- #


def test_sc_ui_018_1_blend_labels_translatable_and_retranslate(layer_env):
    """SC-UI-018-1: all 12 blend labels are non-empty tr() strings and the panel
    retranslates on a LanguageChange event without losing state."""
    env = layer_env(names=("Background", "Top"))
    panel = env.panel
    for mode in BlendMode:
        assert panel.blend_label(mode) != ""
    # The dropdown labels match blend_label for every mode.
    row = _row_for(panel, "Top")
    for mode in BlendMode:
        idx = row._blend.findData(mode)
        assert row._blend.itemText(idx) == panel.blend_label(mode)
    # A LanguageChange retranslates + rebuilds without error; rows persist.
    panel.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert len(panel._rows) == 2
    assert panel._add_action.text() != ""


# --------------------------------------------------------------------------- #
# Indexed-mode ruling — no acceptance scenario requires indexed multi-layer    #
# compositing; the Phase-1 single-layer display is the intended fallback.      #
# --------------------------------------------------------------------------- #


def test_indexed_mode_keeps_single_layer_fallback(layer_env):
    """Indexed documents keep the Phase-1 single-active-layer display path.

    No Phase-4 acceptance scenario requires indexed multi-layer compositing
    (REQ-P4-LOGIC-004 specifies a *RGBA* flat buffer); the compositor is RGBA
    only. This records the intended scope: an indexed scene does not composite
    and shows the active layer's buffer directly.
    """
    env = layer_env(names=("Background",), mode=ColorMode.INDEXED)
    assert env.scene._compositing is False
    assert env.scene._display_source() is env.scene.active_buffer()


def test_indexed_compositor_rejects_indexed_layers():
    """composite_stack raises BlendError on indexed layers (RGBA-only, by design)."""
    doc = Document(32, 32, mode=ColorMode.INDEXED, palette=Palette(STARTER))
    with pytest.raises(BlendError):
        composite_stack(doc.frames[0].layers, 32, 32)


# --------------------------------------------------------------------------- #
# ADR-0008 D4 — multi-layer convert-to-indexed collapses to one indexed layer  #
# and undo restores the full multi-layer RGBA tree (panel + canvas)            #
# --------------------------------------------------------------------------- #


def test_multi_layer_convert_to_indexed_collapses_panel_and_undo_restores(qtbot, theme):
    """ADR-0008 D4: converting a *multi-layer* RGBA document to indexed collapses
    the layer panel + document tree to ONE indexed layer (the indexed invariant),
    and UNDO restores the full multi-layer RGBA tree in the panel and canvas.

    Driven through ``Main_Window`` so the real convert handler + full
    ``_mode_switch_rebind`` (set_document + layer_panel.rebuild) is exercised on
    apply and undo — the reported crash path. Modest 64x64 canvas.
    """
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()

    # Build a genuine multi-layer RGBA document (three top-level leaves).
    top_level = record.document.frames[0].layers
    top_level[0].name = "Background"
    top_level[0].buffer.fill(RED)
    record.document.add_layer("Middle")
    record.document.add_layer("Ink")
    win._layer_panel.rebuild()
    assert record.document.mode is ColorMode.RGBA
    assert [n.name for n in _top_level(record.document)] == [
        "Background",
        "Middle",
        "Ink",
    ]
    assert len(win._layer_panel._rows) == 3
    assert record.scene._compositing is True  # RGBA doc composites

    # Convert the whole document to indexed (one command).
    before_count = record.stack.count()
    win._on_convert_to_indexed()
    assert record.stack.count() == before_count + 1
    # Invariant (ADR-0008 D2): indexed frame == exactly one indexed layer.
    assert record.document.mode is ColorMode.INDEXED
    assert len(_top_level(record.document)) == 1
    assert _top_level(record.document)[0].buffer.mode is ColorMode.INDEXED
    # Panel collapsed to one row; scene left the compositing path (no crash).
    assert len(win._layer_panel._rows) == 1
    assert record.scene._compositing is False

    # UNDO restores the full multi-layer RGBA tree — in the model, the panel and
    # the canvas composite.
    record.stack.undo()
    assert record.document.mode is ColorMode.RGBA
    assert [n.name for n in _top_level(record.document)] == [
        "Background",
        "Middle",
        "Ink",
    ]
    assert len(win._layer_panel._rows) == 3
    assert record.scene._compositing is True
    # The restored composite renders the RGBA stack again (Background = RED).
    record.scene.refresh_all()
    assert record.scene._composite.get_pixel(0, 0) == RED


# --------------------------------------------------------------------------- #
# REQ-B (CL-11) — visibility / opacity / focus stay changeable on ANY layer,   #
# including a LOCKED layer and a currently-HIDDEN layer. One test per sub-claim.#
# --------------------------------------------------------------------------- #


def test_req_b_locked_layer_can_be_focused(layer_env):
    """REQ-B/CL-11: a LOCKED layer can still be focused (made the active layer)."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    # Lock the top layer.
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)
    assert top.locked is True
    # Focus the OTHER layer first, then re-focus the locked one via the panel.
    env.panel._select_path((0,))
    assert env.scene.active_layer() is _top_level(env.doc)[0]
    env.panel._select_path((1,))  # select the locked layer
    assert env.scene.active_layer() is top  # focus succeeded despite the lock


def test_req_b_locked_layer_visibility_still_toggleable(layer_env):
    """REQ-B/CL-11: a LOCKED layer's visibility can still be hidden AND re-shown."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)
    assert top.locked is True
    # The visibility control is NOT disabled by the lock (CL-11).
    assert row._vis.isEnabled() is True
    row._vis.setChecked(False)  # hide while locked
    assert top.visible is False
    row._vis.setChecked(True)  # re-show while locked
    assert top.visible is True


def test_req_b_locked_layer_opacity_still_changeable(layer_env):
    """REQ-B/CL-11: a LOCKED layer's opacity can still be changed."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)
    assert top.locked is True
    assert row._opacity.isEnabled() is True  # opacity not disabled by the lock
    row._opacity.setValue(50)
    assert top.opacity == pytest.approx(0.5)


def test_req_b_hidden_layer_can_be_refocused_and_reshown(layer_env):
    """REQ-B: a currently-HIDDEN layer can be re-selected (focused) and re-shown."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    row = _row_for(env.panel, "Top")
    # Hide it, then focus a different layer so the hidden one is deselected.
    row._vis.setChecked(False)
    assert top.visible is False
    env.panel._select_path((0,))
    assert env.scene.active_layer() is _top_level(env.doc)[0]
    # The hidden layer can be re-selected (focused)...
    env.panel._select_path((1,))
    assert env.scene.active_layer() is top
    # ...and re-shown.
    _row_for(env.panel, "Top")._vis.setChecked(True)
    assert top.visible is True
