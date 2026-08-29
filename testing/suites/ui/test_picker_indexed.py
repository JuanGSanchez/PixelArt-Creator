"""Picker-tool INDEXED-mode production-wiring regression (REQ-P1-UI-016/-018).

`test_tools_guards.py` proves `PickerTool.on_press`'s own resolve-then-set
branch in isolation, against a hand-built resolver. This module proves the
*wiring* DEV-25/DEV-26 named: a real :class:`Canvas_View` bound to a live
INDEXED :class:`Document` via `set_recording` (mirrors
`main_window._add_document_tab`), driving `Canvas_View._make_context` ->
`Canvas_View._resolve_palette_color`, which reads the document's own
:class:`Palette` — never a hand-rolled lambda detached from production
wiring. Every test runs under both themes via the autouse ``theme`` fixture
(`tests/ui/conftest.py`).
"""

from __future__ import annotations

from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tools import PickerTool
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
BLUE = (40, 90, 220, 255)


def _indexed_view(theme, qtbot, width: int = 16, height: int = 16):
    """Build a click-ready `Canvas_View` bound to a live INDEXED document.

    Calls `set_recording` exactly as `main_window._add_document_tab` does on
    every real tab, so `Canvas_View._resolve_palette_color` reads the same
    live `Document.palette` a real session would — the production seam, not a
    test-only substitute.
    """
    doc = Document(width, height, mode=ColorMode.INDEXED, palette=Palette([RED, BLUE]))
    scene = CanvasScene(doc)
    scene.set_background_roles(*canvas_roles(theme))
    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    prepare_for_click(view)
    view.set_recording(None, doc)
    view.set_tool(PickerTool())
    return view, scene, doc, stack


def test_req_p1_ui_016_018_indexed_pick_resolves_palette_color(qtbot, theme):
    """REQ-P1-UI-016/-018: an INDEXED pick sets the active colour/swatch to the
    picked pixel's real palette entry, through production wiring end-to-end.

    `REQ-P1-UI-016`: "sets it as the active colour / active swatch... Picking
    does not mutate the buffer and pushes no undo command." `REQ-P1-UI-018`:
    "reflects palette changes... after a colour-picker pick updating the
    active swatch." `view.active_color()` is the cheapest observable swatch
    reflection at the `Canvas_View` level (the palette-panel highlight itself
    is `Main_Window` territory, pre-existing and outside this fix's scope).
    """
    view, scene, doc, stack = _indexed_view(theme, qtbot)
    scene.active_buffer().set_pixel(3, 3, 1)  # index 1 -> BLUE
    with qtbot.waitSignal(view.colorPicked, timeout=1000) as blocker:
        click_pixel(view, 3, 3)
    assert blocker.args[0] == BLUE
    assert view.active_color() == BLUE
    assert stack.count() == 0  # picking mutates nothing, pushes no command


def test_req_p1_ui_016_indexed_pick_out_of_range_index_is_noop(qtbot, theme):
    """A stale/out-of-range palette index resolves to `None` -> silent no-op.

    The implementer's own choice (AGT-05 report, "Semantics chosen for the
    out-of-range case"): a pixel value left behind by a since-shrunk palette
    must not crash and must not set a colour. Verified here against
    REQ-P1-UI-016's "pushes no undo command... mutates nothing" contract by
    proving the signal never fires (`waitSignal(..., raising=False)` is the
    documented negative-assertion form — it still connects the observer
    before the triggering action).
    """
    view, scene, doc, stack = _indexed_view(theme, qtbot)
    scene.active_buffer().set_pixel(5, 5, 7)  # only indices 0/1 exist
    before = view.active_color()
    with qtbot.waitSignal(view.colorPicked, timeout=200, raising=False) as blocker:
        click_pixel(view, 5, 5)
    assert not blocker.signal_triggered
    assert view.active_color() == before
    assert stack.count() == 0


def test_req_p1_ui_016_rgba_pick_unaffected_by_the_resolver(qtbot, theme):
    """RGBA-mode picking is unchanged by the new resolver wiring (regression guard).

    Same production setup (`set_recording` bound, resolver present on every
    `ToolContext` the view builds) but an RGBA document: `drawing.pick_color`
    returns a tuple, so `PickerTool.on_press` takes the direct-set branch and
    never calls `resolve_palette_color` at all.
    """
    doc = Document(16, 16, palette=Palette([RED, BLUE]))  # RGBA is the default mode
    scene = CanvasScene(doc)
    scene.set_background_roles(*canvas_roles(theme))
    scene.active_buffer().set_pixel(2, 2, RED)
    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    prepare_for_click(view)
    view.set_recording(None, doc)
    view.set_tool(PickerTool())
    with qtbot.waitSignal(view.colorPicked, timeout=1000) as blocker:
        click_pixel(view, 2, 2)
    assert blocker.args[0] == RED
    assert view.active_color() == RED
    assert stack.count() == 0
