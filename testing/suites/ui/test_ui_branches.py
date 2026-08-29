"""Branch-coverage tests for the ``ui`` package (S13 / FU-9 margin).

These exercise the defensive guard, no-op and non-compositing branches in
``layer_panel`` and ``canvas_scene`` that the per-criterion acceptance tests do
not reach, lifting the ui-package *branch* coverage above the 80 % floor with
margin. They assert only that each guard is a safe no-op (no raise, no command),
which is exactly the contract of those branches. Headless; both themes via the
autouse ``theme`` fixture in ``conftest``.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QAbstractItemView

from pixelart_creator.logic.document import Document, Layer, LayerGroup
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.layer_panel import Layer_Panel, _Node_Row

STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]


def _doc(names=("Background",), w=64, h=64, mode=ColorMode.RGBA) -> Document:
    doc = Document(w, h, mode=mode, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = names[0]
    for extra in names[1:]:
        doc.add_layer(extra)
    return doc


def _item_for_path(panel: Layer_Panel, path):
    for item in panel._iter_items():
        if panel._item_path(item) == tuple(path):
            return item
    raise AssertionError(f"no tree item for path {path}")


# --------------------------------------------------------------------------- #
# layer_panel — every mutating handler is a safe no-op with no bound document   #
# (covers the ``doc is None`` / ``path is None`` guard branches).              #
# --------------------------------------------------------------------------- #


def test_panel_handlers_noop_without_context(qtbot):
    """Panel-level ops with no bound document return without raising/pushing."""
    panel = Layer_Panel()
    qtbot.addWidget(panel)
    assert panel.document is None
    panel._on_add()
    panel._on_remove()
    panel._on_duplicate()
    panel._on_group()
    panel._on_ungroup()
    panel._on_toggle_mask()
    panel._on_reference(True)
    panel._on_smart()
    panel.handle_drop(None, None, QAbstractItemView.DropIndicatorPosition.OnItem)
    assert panel.document is None  # unchanged, nothing happened


def test_row_handlers_noop_without_context(qtbot):
    """Per-row attribute handlers are no-ops when the panel has no document."""
    panel = Layer_Panel()
    qtbot.addWidget(panel)
    node = Layer(PixelBuffer(8, 8, ColorMode.RGBA), "L")
    row = _Node_Row(panel, node, (0,))
    qtbot.addWidget(row)
    row._on_visible(False)
    row._on_lock(True)
    row._on_blend(0)
    row._commit_opacity(50)
    assert panel.document is None


def test_mask_edit_toggle_without_selection_resets(qtbot):
    """Enabling mask-edit with no selected node/mask resets the action (guard)."""
    panel = Layer_Panel()
    qtbot.addWidget(panel)
    panel._on_mask_edit(True)
    assert panel._mask_edit_action.isChecked() is False


# --------------------------------------------------------------------------- #
# layer_panel — handle_drop edge branches (no-op / into-own-subtree / group)    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def drop_panel(qtbot):
    """A panel bound to a 3-leaf doc + a group, wired to a real scene."""
    doc = _doc(names=("A", "B", "C"))  # A bottom, C top
    # Wrap the middle leaf in a group so the OnItem-into-group path is reachable.
    a, b, c = doc.frames[0].layers
    group = LayerGroup("G", children=[b])
    doc.frames[0].layers = [a, group, c]
    panel = Layer_Panel()
    qtbot.addWidget(panel)
    scene = CanvasScene(doc)
    stack = QUndoStack()
    panel.set_context(
        doc,
        stack,
        scene.refresh_all,
        scene.refresh_visible,
        scene.refresh_visible_throttled,
    )
    return panel, doc, stack


def test_handle_drop_onto_empty_space_moves_to_bottom(drop_panel):
    """Dropping on empty space (target None) targets the bottom of the stack."""
    panel, doc, stack = drop_panel
    src = _item_for_path(panel, (2,))  # top leaf C
    before = stack.count()
    panel.handle_drop(src, None, QAbstractItemView.DropIndicatorPosition.OnItem)
    assert stack.count() == before + 1  # a real move was pushed


def test_handle_drop_same_index_is_noop(drop_panel):
    """A same-container drop resolving to the source's own slot is a no-op."""
    panel, doc, stack = drop_panel
    src = _item_for_path(panel, (0,))  # bottom leaf A
    before = stack.count()
    # BelowItem on itself -> dst_index == src index -> no-op (no command).
    panel.handle_drop(src, src, QAbstractItemView.DropIndicatorPosition.BelowItem)
    assert stack.count() == before


def test_handle_drop_into_own_subtree_refused(drop_panel):
    """Dropping a group into its own child is refused (tree-corruption guard)."""
    panel, doc, stack = drop_panel
    src = _item_for_path(panel, (1,))  # the group G
    child = _item_for_path(panel, (1, 0))  # its child B
    before = stack.count()
    panel.handle_drop(src, child, QAbstractItemView.DropIndicatorPosition.OnItem)
    assert stack.count() == before  # refused, nothing pushed


def test_handle_drop_onto_group_moves_inside(drop_panel):
    """Dropping a leaf onto a group (OnItem) moves it into the group."""
    panel, doc, stack = drop_panel
    src = _item_for_path(panel, (2,))  # top leaf C
    group_item = _item_for_path(panel, (1,))  # the group G
    before = stack.count()
    panel.handle_drop(src, group_item, QAbstractItemView.DropIndicatorPosition.OnItem)
    assert stack.count() == before + 1


# --------------------------------------------------------------------------- #
# canvas_scene — non-compositing / view-less / throttle branches               #
# --------------------------------------------------------------------------- #


def test_refresh_visible_indexed_scene_is_noncompositing():
    """An indexed scene takes the non-compositing refresh path (no crash)."""
    scene = CanvasScene(_doc(mode=ColorMode.INDEXED))
    assert scene._compositing is False
    scene.refresh_visible()  # non-compositing branch
    scene.recomposite_exposed()  # not-compositing early return


def test_refresh_visible_without_view_recomposites_all():
    """A compositing scene with no live view recomposites the whole canvas."""
    scene = CanvasScene(_doc(names=("A", "B")))
    assert scene._compositing is True
    scene.refresh_visible()  # empty visible rect -> full recomposite branch


def test_throttled_live_recomposite_coalesces_and_flushes():
    """The live-drag throttle coalesces a second call and the trailing flush runs."""
    scene = CanvasScene(_doc())
    scene.refresh_visible_throttled()  # leading edge: starts the timer
    assert scene._live_timer.isActive()
    scene.refresh_visible_throttled()  # timer active -> mark pending
    assert scene._live_pending is True
    scene._flush_live_recomposite()  # pending -> flush + restart
    scene._flush_live_recomposite()  # nothing pending -> no-op branch


def test_recomposite_exposed_noop_when_nothing_stale():
    """recomposite_exposed is a cheap no-op when no region is stale."""
    scene = CanvasScene(_doc())
    scene.recomposite_exposed()  # stale region empty -> early return
