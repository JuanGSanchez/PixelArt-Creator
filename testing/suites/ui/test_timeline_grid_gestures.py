"""Timeline grid gesture acceptance tests (T17; REQ-P5-UI-025, -031).

Every drag here is driven by **real qtbot mouse events** on the grid's
viewport/header viewports, never by calling the internal seam
(``_on_header_section_moved`` / ``_finish_drag`` / etc. directly) — the CF-56
lesson applies with full force to the grid's three gesture zones, and doubly
so to the cel-authoring gesture (REQ-P5-UI-031) because it writes to the
document. Both themes run via the autouse ``theme`` fixture.

Coverage note (correction, dated after the wiring landed): ``REQ-P5-UI-031``'s
"empty cell offers 'create a cel here'" affordance (``SC-UI-031-5``) was
previously recorded here as blocked on UI wiring for
``Document.make_create_cel_command``. AGT-05 landed the two call sites in
``ui/timeline_grid_view.py`` (``_on_context_menu_requested`` /
``_create_cel_here``) concurrently with an earlier run of this module; the
``pytest.skip`` below was stale by the time this file was next touched and is
now replaced with real assertions. The affordance is a context-menu action
reached at an empty cell (right-click, or the platform context-menu
key/chord), refused **outright** — the menu is never built — when the
destination cell is occupied or the destination frame is already at
``MAX_LAYERS_PER_FRAME`` (the offered-then-refused shape the wiring was
written to avoid). The offscreen QPA platform does not synthesize a
``QContextMenuEvent`` from either a real right-click or the Menu/Shift+F10 key
(verified empirically this session — ``QTest.mouseClick``/``QTest.keyClick``
produce no ``customContextMenuRequested`` signal at all under
``QT_QPA_PLATFORM=offscreen``), so the tests below construct and send the same
public ``QContextMenuEvent`` Qt's own platform layer would build, via
``QApplication.sendEvent`` — not a private-seam call into the view.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QContextMenuEvent, QUndoStack
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.constants import MAX_LAYERS_PER_FRAME
from pixelart_creator.logic.document import Document, DocumentError
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.track_table import EMPTY_CELL, track_table
from pixelart_creator.ui.timeline_grid_view import Timeline_Grid_View
from pixelart_creator.ui.timeline_panel import Timeline_Panel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255), (10, 200, 10, 255)]


def _make_two_track_doc(frames: int = 3) -> Document:
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    for _ in range(frames - 1):
        doc.make_duplicate_frame_command(len(doc.frames) - 1).execute()
    return doc


def _make_panel(qtbot, doc: Document):
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(700, 220)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    qtbot.waitExposed(panel)
    panel._grid_toggle_action.setChecked(True)
    return panel, panel._grid, stack


def _cell_center(grid, row: int, col: int) -> QPoint:
    return grid.visualRect(grid.model().index(row, col)).center()


def _request_context_menu(widget, pos: QPoint, *, reason) -> None:
    """Deliver a real ``QContextMenuEvent`` to ``widget`` via ``sendEvent``.

    ``QContextMenuEvent`` + ``QApplication.sendEvent`` is Qt's own public
    event-delivery mechanism — the same class/entry point the real platform
    layer uses to report a right-click or the Menu/Shift+F10 key — not a
    private seam into ``Timeline_Grid_View``. The view installs no
    ``contextMenuEvent`` override of its own; it relies entirely on
    ``QWidget``'s stock ``CustomContextMenu`` policy handling, which is
    exactly what this drives."""
    QApplication.sendEvent(widget, QContextMenuEvent(reason, pos))


class _FakeMenu(QObject):
    """A no-exec ``QMenu`` stand-in (the established pattern in
    ``test_canvas_view.py::_FakeMenu`` / ``test_guides_gestures.py::_FakeMenu``)
    so the modal ``exec()`` never blocks headless — patching ``QMenu.exec``
    directly does not reliably intercept the underlying C++ call; replacing
    the class reference the module uses does. ``timeline_grid_view.py``
    constructs a real ``QAction`` with THIS instance as its parent
    (``QAction(text, menu)``) before calling ``menu.addAction(action)`` — a
    plain-Python stand-in fails there (a ``QAction`` parent must be a real
    ``QObject``), which is why this subclasses ``QObject`` rather than
    reusing the plain-``object`` fakes elsewhere in this suite (verified by
    running against it first: ``TypeError`` from the real ``QAction.__init__``,
    not a product defect). Every assertion below (text, tooltip,
    ``.trigger()``) still runs against the real, already-connected
    ``QAction``."""

    instances: list = []

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._actions: list = []
        _FakeMenu.instances.append(self)

    def addAction(self, action):  # noqa: N802
        self._actions.append(action)
        return action

    def actions(self):
        return list(self._actions)

    def exec(self, *args, **kwargs):  # noqa: A003
        return None  # never enters a modal loop


def _empty_cell_doc():
    """A two-track document where "Outline" is occupied at frame 0 and
    EMPTY at frame 1 (``add_frame`` mints frame 1 its own independent
    "Layer" track — verified this session — so "Outline"'s row never
    reaches frame 1 at all, which is precisely an empty cell on an
    EXISTING track, the shape SC-UI-031-5 requires)."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    outline = doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    return doc, outline.layer_id


def _drag(
    qtbot,
    viewport,
    start: QPoint,
    end: QPoint,
    *,
    modifiers=Qt.KeyboardModifier.NoModifier,
    steps: int = 5,
    release: bool = True,
):
    """Real press -> incremental moves -> (optional) release, on ``viewport``."""
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, modifiers, pos=start)
    for i in range(1, steps + 1):
        pos = QPoint(
            start.x() + (end.x() - start.x()) * i // steps,
            start.y() + (end.y() - start.y()) * i // steps,
        )
        qtbot.mouseMove(viewport, pos=pos)
    if release:
        qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, modifiers, pos=end)


# --------------------------------------------------------------------------- #
# REQ-P5-UI-025 — disjoint gesture zones                                      #
# --------------------------------------------------------------------------- #


def test_sc_ui_025_1_header_drag_reorders_as_one_command(qtbot):
    """SC-UI-025-1: a real drag of a column header to a new position reorders
    the frame as exactly one QUndoCommand; undo restores the order."""
    doc = _make_two_track_doc(3)
    ids_before = [id(f) for f in doc.frames]
    panel, grid, stack = _make_panel(qtbot, doc)
    header = grid.horizontalHeader()
    before = stack.count()

    start = QPoint(
        header.sectionViewportPosition(2) + header.sectionSize(2) // 2,
        header.height() // 2,
    )
    end = QPoint(
        header.sectionViewportPosition(0) + 2,
        header.height() // 2,
    )
    _drag(qtbot, header.viewport(), start, end)

    assert stack.count() == before + 1
    assert [id(f) for f in doc.frames] == [ids_before[2], ids_before[0], ids_before[1]]
    stack.undo()
    assert [id(f) for f in doc.frames] == ids_before


def test_sc_ui_025_2_body_drag_scrubs_and_pushes_nothing(qtbot):
    """SC-UI-025-2: a real left-drag started away from any occupied cell
    scrubs across the grid body and pushes nothing. (A drag that starts ON an
    occupied cell is the distinct cel-move gesture, REQ-P5-UI-031 — proven
    separately below; starting this scrub drag on an empty cell is what keeps
    the two zones honestly disjoint by construction, not by an assumption
    about which one "the body" means.)"""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    for _ in range(3):
        doc.add_frame()  # frames 1..3 carry only "Base"; "Outline" row is empty there
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    # "Outline" was only ever added to frame 0 (add_frame() mints each new
    # frame its OWN independent track, per the shipped Document API) — so the
    # empty span to drag across is columns 1..3, deliberately avoiding column
    # 0 where this same row IS occupied.
    for col in (1, 2, 3):
        assert table.rows[outline_row].cells[col] is EMPTY_CELL
    before = stack.count()

    scrub_events = []
    panel.frameScrubbed.connect(scrub_events.append)

    start = _cell_center(grid, outline_row, 1)
    end = _cell_center(grid, outline_row, 3)
    _drag(qtbot, grid.viewport(), start, end)

    assert stack.count() == before
    assert scrub_events and scrub_events[-1] == 3


def test_sc_ui_025_3_and_5_the_three_zones_never_collide(qtbot):
    """SC-UI-025-3/-5: a header drag never scrubs; a body drag that starts on
    an EMPTY cell only scrubs and never reorders or moves a cel; an
    occupied-cell drag (proven separately in the SC-UI-031-* tests below)
    never reorders a frame. Each outcome is asserted from the real mouse
    gesture, not from an internal seam call."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    doc.add_frame()  # frames 1, 2 carry only "Base" -> "Outline" empty there
    ids_before = [id(f) for f in doc.frames]

    panel, grid, stack = _make_panel(qtbot, doc)
    header = grid.horizontalHeader()
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[1] is EMPTY_CELL
    assert table.rows[outline_row].cells[2] is EMPTY_CELL

    scrub_events = []
    panel.frameScrubbed.connect(scrub_events.append)

    # Header drag: reorders, never scrubs. The press must land solidly within
    # the section (its centre), not within a couple of pixels of a section
    # boundary — empirically confirmed this session: a press 2px from a
    # boundary does not reliably register as a start-section for Qt's own
    # movable-header drag under this platform, while a centred press does
    # every time (a test-construction fact, not a product finding).
    start = QPoint(
        header.sectionViewportPosition(1) + header.sectionSize(1) // 2,
        header.height() // 2,
    )
    end = QPoint(header.sectionViewportPosition(0) + 2, header.height() // 2)
    _drag(qtbot, header.viewport(), start, end)
    assert scrub_events == []  # header drag never scrubs
    assert [id(f) for f in doc.frames] != ids_before  # it did reorder
    header_reorder_count = stack.count()

    # The reorder relocated which COLUMN the occupied "Outline" cel now lives
    # in (the frame that carried it moved with the header drag) — re-derive
    # the table rather than assume columns 1/2 are still empty after a
    # document mutation; this is the same "row/column identity can move,
    # never assume a stale index" discipline the SC-UI-031-1 fix above uses.
    table2 = track_table(doc, active_frame=0)
    outline_row2 = next(i for i, r in enumerate(table2.rows) if r.label == "Outline")
    empty_cols = [
        c
        for c, cell in enumerate(table2.rows[outline_row2].cells)
        if cell is EMPTY_CELL
    ]
    assert len(empty_cols) >= 2

    # Body drag starting on an EMPTY cell: scrubs, never reorders, never
    # moves a cel — the document's node count is untouched.
    layers_before = [len(f.layers) for f in doc.frames]
    start2 = _cell_center(grid, outline_row2, empty_cols[0])
    end2 = _cell_center(grid, outline_row2, empty_cols[-1])
    _drag(qtbot, grid.viewport(), start2, end2)

    assert scrub_events[-1] == empty_cols[-1]
    assert stack.count() == header_reorder_count  # no further command pushed
    assert [len(f.layers) for f in doc.frames] == layers_before


def test_sc_ui_025_4_a_no_op_drop_changes_nothing(qtbot):
    """SC-UI-025-4: dropping a column header on its own position rebuilds from
    the document and pushes no command."""
    doc = _make_two_track_doc(3)
    ids_before = [id(f) for f in doc.frames]
    panel, grid, stack = _make_panel(qtbot, doc)
    header = grid.horizontalHeader()
    before = stack.count()

    pos = QPoint(header.sectionViewportPosition(1) + 2, header.height() // 2)
    _drag(qtbot, header.viewport(), pos, pos, steps=1)

    assert stack.count() == before
    assert [id(f) for f in doc.frames] == ids_before


# --------------------------------------------------------------------------- #
# REQ-P5-UI-031 — cel move / copy / create                                    #
# --------------------------------------------------------------------------- #


def _node_by_track_id(doc: Document, frame_index: int, track_id: int):
    """Return the top-level node with ``layer_id == track_id`` in a frame, or
    ``None``. Looks the document up by stable track identity — deliberately
    NOT by re-deriving ``track_table`` and indexing a row position, because a
    move can change which tracks are "present in the active frame" and
    therefore reshuffle row order (REQ-P5-LOGIC-015's own ordering rule); a
    row index captured before the move is not safe to reuse after it."""
    for node in doc.frames[frame_index].layers:
        if node.layer_id == track_id:
            return node
    return None


def test_sc_ui_031_1_occupied_cell_drag_moves_the_cel_as_one_command(qtbot):
    """SC-UI-031-1: dragging an occupied cell onto an empty cell moves the
    drawing there as one command; undo restores both cells exactly."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    outline = doc.add_layer("Outline", frame_index=0)
    outline.buffer.fill_rect(0, 0, 64, 64, (200, 20, 20, 255))
    outline_track_id = outline.layer_id
    doc.add_frame()
    doc.add_frame()
    doc.add_frame()  # frames 1..3 have only "Base" -> "Outline" empty there

    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[2] is EMPTY_CELL
    before = stack.count()

    start = _cell_center(grid, outline_row, 0)
    end = _cell_center(grid, outline_row, 2)
    _drag(qtbot, grid.viewport(), start, end)

    assert stack.count() == before + 1
    assert _node_by_track_id(doc, 0, outline_track_id) is None  # source vacated
    moved = _node_by_track_id(doc, 2, outline_track_id)
    assert moved is not None and moved is outline  # same node, at the destination

    stack.undo()
    assert _node_by_track_id(doc, 0, outline_track_id) is outline
    assert _node_by_track_id(doc, 2, outline_track_id) is None


def test_sc_ui_031_2_ctrl_drag_copies_instead_of_moving(qtbot):
    """SC-UI-031-2: holding Ctrl during the drag copies; both cells end up
    occupied, and exactly one command is pushed."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()

    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    before = stack.count()

    start = _cell_center(grid, outline_row, 0)
    end = _cell_center(grid, outline_row, 1)
    _drag(
        qtbot,
        grid.viewport(),
        start,
        end,
        modifiers=Qt.KeyboardModifier.ControlModifier,
    )

    assert stack.count() == before + 1
    table_after = track_table(doc, active_frame=0)
    assert table_after.rows[outline_row].cells[0] is not EMPTY_CELL
    assert table_after.rows[outline_row].cells[1] is not EMPTY_CELL


def test_sc_ui_031_3_the_pending_drop_is_legible_before_release(qtbot):
    """SC-UI-031-3: while dragging from an occupied cell, the cursor names
    move vs. copy before the drop, and the highlighted cell names the
    destination."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()

    panel, grid, _stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    start = _cell_center(grid, outline_row, 0)
    end = _cell_center(grid, outline_row, 1)
    _drag(qtbot, grid.viewport(), start, end, release=False)

    assert grid.cursor().shape() == Qt.CursorShape.DragMoveCursor
    assert grid.currentIndex() == grid.model().index(outline_row, 1)

    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=end)


def test_sc_ui_031_4_esc_mid_drag_changes_nothing(qtbot):
    """SC-UI-031-4: pressing ESC before release leaves the document unchanged
    and pushes no command."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()

    panel, grid, stack = _make_panel(qtbot, doc)
    table_before = track_table(doc, active_frame=0)
    before = stack.count()

    start = _cell_center(grid, 1, 0)
    end = _cell_center(grid, 1, 1)
    _drag(qtbot, grid.viewport(), start, end, release=False)
    qtbot.keyClick(grid, Qt.Key.Key_Escape)
    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=end)

    assert stack.count() == before
    table_after = track_table(doc, active_frame=0)
    for row_before, row_after in zip(table_before.rows, table_after.rows):
        assert row_before.cells == row_after.cells


def test_sc_ui_031_6_dropping_a_cel_on_its_own_cell_does_nothing(qtbot):
    """SC-UI-031-6: a REAL drag — one that crosses Qt's own drag-start
    distance threshold, so ``_finish_drag`` is genuinely invoked — that
    returns to and releases on the cel's own source cell is a no-op: no
    command pushed, document unchanged.

    Correction (self-caught false-positive-shaped test, dated after the
    branch-coverage close-out that found it): the previous version of this
    test pressed and released at the EXACT SAME point (``_drag(..., pos,
    pos, steps=1)``). A zero-distance "drag" never crosses
    ``QApplication.startDragDistance()``, so ``_dragging`` stayed ``False``
    and ``_finish_drag`` was never called at all — the assertion
    (``stack.count() == before``) passed, but for the wrong reason: it was
    really asserting that a plain click pushes nothing, which
    ``test_sc_ui_023_5_no_selection_pushes_a_command`` already proves, not
    that dropping ON THE SOURCE CELL after a real drag is a no-op
    (``REQ-P5-LOGIC-016``'s own documented rule). Rewritten to actually drag
    away first (crossing the threshold, proven by the live drag-move
    cursor) and back before releasing."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()

    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()
    source = _cell_center(grid, 1, 0)
    away = _cell_center(grid, 1, 1)

    qtbot.mousePress(grid.viewport(), Qt.MouseButton.LeftButton, pos=source)
    qtbot.mouseMove(grid.viewport(), pos=away)  # crosses the drag-start threshold
    assert grid.cursor().shape() == Qt.CursorShape.DragMoveCursor  # a real drag IS live
    qtbot.mouseMove(grid.viewport(), pos=source)  # back onto the source cell
    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=source)

    assert stack.count() == before


def test_sc_ui_031_5_empty_cell_pointer_menu_creates_cel_joining_the_track(
    qtbot, monkeypatch
):
    """SC-UI-031-5: a real right-click (``QContextMenuEvent``, reason=Mouse) on
    an EMPTY cell offers exactly one "create a cel here" action; triggering it
    pushes one command, and the created cel JOINS the existing "Outline"
    track (same ``layer_id``, no new track row minted) rather than starting a
    new layer. Undo restores the cell to empty; redo re-creates it."""
    doc, outline_track_id = _empty_cell_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[1] is EMPTY_CELL
    rows_before = len(table.rows)
    layers_before = len(doc.frames[1].layers)
    before = stack.count()

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)

    pos = _cell_center(grid, outline_row, 1)
    _request_context_menu(grid.viewport(), pos, reason=QContextMenuEvent.Reason.Mouse)

    assert _FakeMenu.instances, "no context menu was built for an empty cell"
    actions = _FakeMenu.instances[-1].actions()
    assert len(actions) == 1
    assert actions[0].text() != ""
    actions[0].trigger()

    assert stack.count() == before + 1
    assert len(doc.frames[1].layers) == layers_before + 1
    created = _node_by_track_id(doc, 1, outline_track_id)
    assert created is not None
    assert created.layer_id == outline_track_id  # joins the existing track

    table_after = track_table(doc, active_frame=0)
    assert len(table_after.rows) == rows_before  # no new track/layer row minted

    stack.undo()
    assert _node_by_track_id(doc, 1, outline_track_id) is None
    table_after_undo = track_table(doc, active_frame=0)
    assert table_after_undo.rows[outline_row].cells[1] is EMPTY_CELL

    stack.redo()
    assert _node_by_track_id(doc, 1, outline_track_id) is not None


def test_sc_ui_031_5_create_action_has_accessible_text_and_description(
    qtbot, monkeypatch
):
    """SC-UI-031-5 / REQ-P5-UI-027: the offered action carries a non-empty
    name (``text()``) and description (``toolTip()``) — the accessible-name
    and accessible-description equivalent for a ``QAction`` (Qt exposes a
    ``QAction`` without an explicit ``QAccessible`` name via its text/tooltip
    to assistive technology)."""
    doc, _outline_track_id = _empty_cell_doc()
    panel, grid, _stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)

    pos = _cell_center(grid, outline_row, 1)
    _request_context_menu(grid.viewport(), pos, reason=QContextMenuEvent.Reason.Mouse)

    actions = _FakeMenu.instances[-1].actions()
    assert len(actions) == 1
    assert actions[0].text() != ""
    assert actions[0].toolTip() != ""


def test_sc_ui_031_5_create_affordance_is_keyboard_reachable(qtbot, monkeypatch):
    """SC-UI-031-5 / REQ-P5-UI-027: the affordance is keyboard-reachable, not
    only pointer-reachable. The offscreen platform does not synthesize the
    native Menu/Shift+F10 -> ``QContextMenuEvent`` translation (verified
    empirically this session), so a real ``QContextMenuEvent(reason=Keyboard)``
    is sent with a position that deliberately does NOT resolve to any cell
    (``indexAt`` returns an invalid index) — the target can therefore only
    have come from the view's ``currentIndex()`` fallback, which is exactly
    the "no extra key handling needed" path the view's own docstring claims
    for keyboard reachability, and is the same fallback a real Menu-key event
    (whose position is not tied to any cell) would exercise."""
    doc, outline_track_id = _empty_cell_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert grid.focusPolicy() != Qt.FocusPolicy.NoFocus  # keyboard-focusable at all
    grid.setCurrentIndex(grid.model().index(outline_row, 1))
    before = stack.count()

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)

    off_pos = QPoint(-1000, -1000)
    assert not grid.indexAt(off_pos).isValid()  # confirms the fallback is exercised
    _request_context_menu(
        grid.viewport(), off_pos, reason=QContextMenuEvent.Reason.Keyboard
    )

    assert _FakeMenu.instances, (
        "the create-cel affordance did not reach the current index via "
        "keyboard (currentIndex() fallback) — REQ-P5-UI-027 keyboard "
        "reachability is not met"
    )
    actions = _FakeMenu.instances[-1].actions()
    assert len(actions) == 1
    actions[0].trigger()

    assert stack.count() == before + 1
    created = _node_by_track_id(doc, 1, outline_track_id)
    assert created is not None and created.layer_id == outline_track_id


def test_sc_ui_031_5_occupied_cell_offers_no_create_affordance(qtbot, monkeypatch):
    """SC-UI-031-5: no affordance is offered on an OCCUPIED cell — the menu is
    never built (offered-then-refused is avoided outright), and the
    underlying primitive itself independently refuses the same request."""
    doc, outline_track_id = _empty_cell_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[0] is not EMPTY_CELL  # occupied at frame 0

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)
    before = stack.count()

    pos = _cell_center(grid, outline_row, 0)
    _request_context_menu(grid.viewport(), pos, reason=QContextMenuEvent.Reason.Mouse)

    assert not _FakeMenu.instances, "a create-cel menu was offered on an occupied cell"
    assert stack.count() == before

    with pytest.raises(DocumentError):
        doc.make_create_cel_command(frame_index=0, track_id=outline_track_id)


def test_sc_ui_031_5_no_create_affordance_at_max_layers_per_frame(qtbot, monkeypatch):
    """SC-UI-031-5: no affordance is offered when the destination frame is
    already at ``MAX_LAYERS_PER_FRAME`` — even though the target track's own
    cell there is empty, the factory refuses on the frame's total layer
    count, and the view refuses to offer it outright for the same reason."""
    doc, outline_track_id = _empty_cell_doc()
    filler_needed = MAX_LAYERS_PER_FRAME - len(doc.frames[1].layers)
    for i in range(filler_needed):
        doc.add_layer(f"Filler{i}", frame_index=1)
    assert len(doc.frames[1].layers) == MAX_LAYERS_PER_FRAME

    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[1] is EMPTY_CELL  # the cell itself is empty

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)
    before = stack.count()

    pos = _cell_center(grid, outline_row, 1)
    _request_context_menu(grid.viewport(), pos, reason=QContextMenuEvent.Reason.Mouse)

    assert (
        not _FakeMenu.instances
    ), "a create-cel menu was offered at MAX_LAYERS_PER_FRAME"
    assert stack.count() == before
    assert len(doc.frames[1].layers) == MAX_LAYERS_PER_FRAME  # untouched

    with pytest.raises(DocumentError):
        doc.make_create_cel_command(frame_index=1, track_id=outline_track_id)


# --------------------------------------------------------------------------- #
# Branch-coverage close-out (T17 gate; REQ-P5-UI-025/-031) — the refusal      #
# paths, the drops that land outside the grid, and the defensive races a     #
# real single-user gesture sequence never happens to trigger. Every gesture  #
# below is still a real qtbot mouse/key event or a real public Qt signal     #
# (``header.sectionMoved.emit`` / ``model.visibilityToggleRequested.emit``), #
# never a private-seam call into ``Timeline_Grid_View`` (the CF-56 rule).    #
# --------------------------------------------------------------------------- #


def test_press_starting_outside_any_cell_does_not_seed_a_drag(qtbot):
    """A press that lands beyond the grid's populated cells (``indexAt``
    invalid) seeds no drag-gesture tracking; a subsequent drag ending on an
    occupied cell changes nothing."""
    doc = _make_two_track_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()
    outside = QPoint(grid.viewport().width() - 1, grid.viewport().height() - 1)
    assert not grid.indexAt(outside).isValid(), "test fixture assumption: no cell there"
    target = _cell_center(grid, 0, 1)

    _drag(qtbot, grid.viewport(), outside, target)

    assert stack.count() == before


def test_right_click_press_does_not_seed_a_drag_gesture(qtbot):
    """A right-button press on an occupied cell must not seed the LEFT-only
    drag-gesture tracking (REQ-P5-UI-025's three zones are left-button
    gestures) — proven by then performing a genuine left drag from the SAME
    cell right after and observing it behaves exactly like the shipped
    SC-UI-031-1 move, with no stray state surviving from the right press."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    outline = doc.add_layer("Outline", frame_index=0)
    outline_track_id = outline.layer_id
    doc.add_frame()
    doc.add_frame()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    pos0 = _cell_center(grid, outline_row, 0)
    pos2 = _cell_center(grid, outline_row, 2)
    before = stack.count()

    qtbot.mousePress(grid.viewport(), Qt.MouseButton.RightButton, pos=pos0)
    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.RightButton, pos=pos0)

    _drag(qtbot, grid.viewport(), pos0, pos2)  # a real LEFT drag, right after

    assert stack.count() == before + 1
    assert _node_by_track_id(doc, 2, outline_track_id) is not None


def test_hover_without_a_prior_press_does_not_scrub(qtbot):
    """A plain mouse-move hover (no button held, no prior press on the grid)
    must not be mistaken for a body-drag scrub."""
    doc = _make_two_track_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    scrub_events = []
    panel.frameScrubbed.connect(scrub_events.append)
    before = stack.count()

    qtbot.mouseMove(grid.viewport(), pos=_cell_center(grid, 0, 1))

    assert scrub_events == []
    assert stack.count() == before


def test_sc_ui_031_occupied_drag_ending_outside_the_grid_changes_nothing(qtbot):
    """SC-UI-031: dragging an occupied cel to a point beyond the grid's
    populated area (``indexAt`` invalid — past the last row/column) leaves
    the document untouched and pushes no command ("a drop outside the grid
    changes nothing"), while the cursor still legibly names the pending move
    (REQ-P5-UI-031's before-the-drop legibility) even with no valid
    destination cell to highlight yet."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    before = stack.count()
    start = _cell_center(grid, outline_row, 0)
    outside = QPoint(grid.viewport().width() + 50, grid.viewport().height() + 50)

    qtbot.mousePress(grid.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(grid.viewport(), pos=QPoint(start.x() + 30, start.y()))
    assert grid.cursor().shape() == Qt.CursorShape.DragMoveCursor  # a real drag IS live
    qtbot.mouseMove(grid.viewport(), pos=outside)
    assert grid.cursor().shape() == Qt.CursorShape.DragMoveCursor  # still legible

    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=outside)

    assert stack.count() == before
    table_after = track_table(doc, active_frame=0)
    assert table_after.rows[outline_row].cells[0] is not EMPTY_CELL  # source untouched


def test_body_scrub_drag_ending_outside_the_grid_stops_scrubbing_safely(qtbot):
    """SC-UI-025-2 continuation: a body-drag (started on an EMPTY cell) that
    moves past the grid's populated area emits no further ``frameScrubbed``
    and raises nothing — the scrub path's own out-of-range guard."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    doc.add_frame()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    scrub_events = []
    panel.frameScrubbed.connect(scrub_events.append)
    before = stack.count()

    start = _cell_center(grid, outline_row, 1)
    outside = QPoint(grid.viewport().width() + 50, grid.viewport().height() + 50)
    qtbot.mousePress(grid.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(grid.viewport(), pos=QPoint(start.x() + 30, start.y()))
    scrubbed_so_far = len(scrub_events)
    qtbot.mouseMove(grid.viewport(), pos=outside)  # off the populated grid entirely

    assert len(scrub_events) == scrubbed_so_far  # no further scrub while off-grid

    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=outside)
    assert stack.count() == before


def test_escape_without_an_active_drag_is_not_swallowed(qtbot):
    """Pressing Escape when no drag is in progress passes through normally —
    REQ-P5-UI-031's cancel semantics are drag-scoped, not a global Escape
    hijack."""
    doc = _make_two_track_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    grid.setFocus()
    before = stack.count()

    qtbot.keyClick(grid, Qt.Key.Key_Escape)  # no drag active; must not raise

    assert stack.count() == before


def test_non_escape_key_during_a_drag_does_not_cancel_it(qtbot):
    """A non-Escape key press mid-drag does not cancel the gesture — only
    Escape does (SC-UI-031-4) — the key is passed through to the base
    ``QTableView`` instead."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    panel, grid, stack = _make_panel(qtbot, doc)
    start = _cell_center(grid, 1, 0)
    end = _cell_center(grid, 1, 1)
    qtbot.mousePress(grid.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(grid.viewport(), pos=QPoint((start.x() + end.x()) // 2, start.y()))
    assert grid.cursor().shape() == Qt.CursorShape.DragMoveCursor

    qtbot.keyClick(grid, Qt.Key.Key_A)  # not Escape

    assert grid.cursor().shape() == Qt.CursorShape.DragMoveCursor  # drag still live
    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=end)


def test_leave_event_clears_the_drag_cursor(qtbot):
    """Leaving the grid's viewport resets any lingering cursor override —
    exercised via a real ``QEvent.Leave`` (Qt's own event-delivery mechanism
    for a widget-rectangle exit), not a private seam."""
    from PySide6.QtCore import QEvent

    doc = _make_two_track_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    grid.setCursor(Qt.CursorShape.DragMoveCursor)

    QApplication.sendEvent(grid, QEvent(QEvent.Type.Leave))

    assert grid.cursor().shape() != Qt.CursorShape.DragMoveCursor


def test_header_section_moved_same_position_pushes_nothing(qtbot):
    """A degenerate ``sectionMoved`` report (old == new — Qt's own header can
    emit this) is treated as a no-op, delivered via the header's real public
    signal rather than a mouse gesture too precise to reproduce reliably."""
    doc = _make_two_track_doc(3)
    ids_before = [id(f) for f in doc.frames]
    panel, grid, stack = _make_panel(qtbot, doc)
    header = grid.horizontalHeader()
    before = stack.count()

    header.sectionMoved.emit(0, 1, 1)

    assert stack.count() == before
    assert [id(f) for f in doc.frames] == ids_before


# NOTE (self-caught, dated after it crashed the run this session): two further
# tests were attempted here to reach _on_header_section_moved's out-of-range
# and stale-source DocumentError branches, by shrinking the document then
# emitting header.sectionMoved.emit(...) with a position valid for the
# HEADER's own (unshrunk) section count but invalid for the document. The
# in-range emit above (old==new) is safe, but an out-of-range one drove the
# handler's own header.moveSection(new_visual, old_visual) call into a REAL
# Windows access-violation crash inside Qt's native QHeaderView internals —
# not a Python exception, a process-terminating native fault, observed this
# session with QT_QPA_PLATFORM=offscreen / PySide6 6.11.1. Synthesizing
# sectionMoved without a genuine prior header-internal move desyncs Qt's own
# visual/logical index bookkeeping, which is undefined behaviour on the C++
# side. Both tests are WITHDRAWN rather than contorted further to reach the
# branch some other way — the two lines they targeted
# (ui/timeline_grid_view.py: the `new_visual` range check and the
# `except DocumentError` around `make_move_frame_command`) remain NOT
# covered by this suite; reported to AGT-05 as a finding below rather than
# risked again here.


def test_visibility_toggle_signal_with_no_document_bound_is_a_safe_no_op(qtbot):
    """A stray ``visibilityToggleRequested`` signal reaching a grid that has
    no document/push bound (e.g. delivered before ``set_context`` finished
    wiring) changes nothing and does not raise — driven through the model's
    own public signal (``grid.model()`` is inherited public Qt API), not a
    private seam."""
    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)

    grid.model().visibilityToggleRequested.emit(0, 0, False)  # must not raise


def test_visibility_toggle_signal_with_out_of_range_row_is_refused(qtbot):
    """A toggle signal naming a row beyond the bound table's own row count is
    refused rather than raising."""
    doc = _make_two_track_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()

    grid.model().visibilityToggleRequested.emit(0, 999, False)

    assert stack.count() == before


def test_visibility_toggle_signal_with_out_of_range_frame_is_refused(qtbot):
    """A toggle signal naming a frame index beyond the row's own cell count
    is refused rather than raising."""
    doc = _make_two_track_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()

    grid.model().visibilityToggleRequested.emit(999, 0, False)

    assert stack.count() == before


def test_visibility_toggle_signal_on_an_empty_cell_is_refused(qtbot):
    """A stray toggle signal naming a cell that carries no node — bypassing
    the model's own ``ItemIsUserCheckable`` flag gate the real UI checkbox
    click respects (already proven refused via ``setData`` in
    ``test_sc_ui_024_4_empty_cell_offers_no_visibility_toggle``) — is refused
    at the handler's OWN defensive check too, not only at the model's."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()  # frame 1 has no "Outline"
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[1] is EMPTY_CELL
    before = stack.count()

    grid.model().visibilityToggleRequested.emit(1, outline_row, False)

    assert stack.count() == before


def test_visibility_toggle_signal_after_the_node_was_removed_elsewhere_is_refused(
    qtbot,
):
    """A toggle signal computed from the grid's OWN (now-stale) cached table
    — naming a node a concurrent mutation (another view, undo/redo,
    automation) has since removed from that frame — is refused rather than
    raising or resurrecting the node."""
    doc = _make_two_track_doc()
    outline_id = doc.frames[0].layers[1].layer_id
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline_id)
    before = stack.count()

    doc.frames[0].layers.pop(1)  # remove the node the grid's cached table still names

    grid.model().visibilityToggleRequested.emit(0, outline_row, False)

    assert stack.count() == before


def test_visibility_toggle_document_error_from_set_layer_visible_is_caught(
    qtbot, monkeypatch
):
    """If the resolved path is stale in a way ``_find_path`` itself cannot
    detect, the handler still catches ``DocumentError`` from
    ``Document.set_layer_visible`` and rebuilds rather than raising — proven
    by monkeypatching ``_find_path`` to hand back a bogus path, simulating
    exactly that narrower race."""
    import pixelart_creator.ui.timeline_grid_view as tgv_module

    doc = _make_two_track_doc()
    outline_id = doc.frames[0].layers[1].layer_id
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline_id)
    before = stack.count()

    monkeypatch.setattr(tgv_module, "_find_path", lambda *a, **k: (999,))

    grid.model().visibilityToggleRequested.emit(0, outline_row, False)

    assert stack.count() == before


def test_sc_ui_031_drag_copy_to_empty_destination_at_max_layers_is_refused(qtbot):
    """SC-UI-031: Ctrl-dragging (copy) an occupied cel onto an EMPTY cell in
    a frame already at ``MAX_LAYERS_PER_FRAME`` is refused through the
    shipped ``DocumentError`` — the empty-destination path (no overwrite
    dialog involved at all) has its own ``MAX_LAYERS_PER_FRAME`` ceiling,
    exactly like the "create a cel here" affordance's own refusal above."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    filler_needed = MAX_LAYERS_PER_FRAME - len(doc.frames[1].layers)
    for i in range(filler_needed):
        doc.add_layer(f"Filler{i}", frame_index=1)
    assert len(doc.frames[1].layers) == MAX_LAYERS_PER_FRAME

    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[1] is EMPTY_CELL
    before = stack.count()

    start = _cell_center(grid, outline_row, 0)
    end = _cell_center(grid, outline_row, 1)
    _drag(
        qtbot,
        grid.viewport(),
        start,
        end,
        modifiers=Qt.KeyboardModifier.ControlModifier,
    )

    assert stack.count() == before
    assert len(doc.frames[1].layers) == MAX_LAYERS_PER_FRAME  # untouched


def test_finish_drag_with_no_push_bound_is_a_safe_no_op(qtbot):
    """A press-occupied drag finishing while the grid has a document but no
    ``push`` callback wired (e.g. a read-only/preview embedding of the grid)
    changes nothing and does not raise."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)
    grid.resize(400, 200)
    grid.show()
    qtbot.waitExposed(grid)
    grid.set_context(doc, QUndoStack(), 0, None)  # no push wired
    start = _cell_center(grid, 1, 0)
    end = _cell_center(grid, 1, 1)

    _drag(qtbot, grid.viewport(), start, end)

    table_after = track_table(doc, active_frame=0)
    assert table_after.rows[1].cells[0] is not EMPTY_CELL  # source untouched
    assert table_after.rows[1].cells[1] is EMPTY_CELL  # destination untouched


def test_context_menu_with_no_document_bound_shows_nothing(qtbot, monkeypatch):
    """A context-menu request delivered to a grid that has no document bound
    at all (before ``set_context`` was ever called) shows no menu and does
    not raise."""
    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)
    grid.resize(300, 150)
    grid.show()
    qtbot.waitExposed(grid)

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)

    _request_context_menu(
        grid.viewport(), QPoint(10, 10), reason=QContextMenuEvent.Reason.Mouse
    )

    assert not _FakeMenu.instances


def test_context_menu_with_no_valid_index_at_all_shows_nothing(qtbot, monkeypatch):
    """Both ``indexAt(pos)`` (an off-grid position) AND the view's own
    ``currentIndex()`` fallback are invalid — reached by binding a document
    with an out-of-range ``active_frame``, so ``_restore_current_index``
    never seeds a current index at all — and the request is refused rather
    than crashing on an invalid index."""
    doc = Document(64, 64, palette=Palette(STARTER))
    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)
    grid.resize(300, 150)
    grid.show()
    qtbot.waitExposed(grid)
    grid.set_context(doc, QUndoStack(), 999, lambda cmd, label: None)
    assert not grid.currentIndex().isValid()

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)

    off_pos = QPoint(-1000, -1000)
    assert not grid.indexAt(off_pos).isValid()
    _request_context_menu(
        grid.viewport(), off_pos, reason=QContextMenuEvent.Reason.Mouse
    )

    assert not _FakeMenu.instances


def test_context_menu_frame_index_out_of_range_after_document_shrank_is_refused(
    qtbot, monkeypatch
):
    """A context-menu request whose (indexAt-invalid, currentIndex-fallback)
    index names a frame column that existed when the current index was last
    set, but no longer exists because the DOCUMENT shrank from elsewhere
    (undo, automation, another view) before the event was processed, is
    refused before any menu is built — a plain document mutation + a real
    ``QContextMenuEvent``, no Qt-internal header state involved (unlike the
    header-drag race above, which is NOT reproduced this way — see the note
    there)."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    doc.add_frame()  # 3 frames; "Outline" only ever added to frame 0
    grid = Timeline_Grid_View()
    qtbot.addWidget(grid)
    grid.resize(400, 200)
    grid.show()
    qtbot.waitExposed(grid)
    grid.set_context(doc, QUndoStack(), 2, lambda cmd, label: None)
    table = track_table(doc, active_frame=2)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    assert table.rows[outline_row].cells[2] is EMPTY_CELL
    grid.setCurrentIndex(grid.model().index(outline_row, 2))
    assert grid.currentIndex().column() == 2

    while len(doc.frames) > 1:
        doc.frames.pop()  # document shrinks; the grid's cached table/index are stale

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)

    off_pos = QPoint(
        -1000, -1000
    )  # indexAt invalid -> falls back to stale currentIndex
    _request_context_menu(
        grid.viewport(), off_pos, reason=QContextMenuEvent.Reason.Mouse
    )

    assert not _FakeMenu.instances


def test_create_cel_action_with_no_document_bound_at_trigger_time_is_a_safe_no_op(
    qtbot, monkeypatch
):
    """The 'Create Cel Here' action is built while a document is bound, but
    the document is cleared (``set_context(None, ...)``) BEFORE the action
    is triggered — the click landing after a project closed, say. Triggering
    it then changes nothing and does not raise."""
    doc, _outline_track_id = _empty_cell_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)
    pos = _cell_center(grid, outline_row, 1)
    _request_context_menu(grid.viewport(), pos, reason=QContextMenuEvent.Reason.Mouse)
    actions = _FakeMenu.instances[-1].actions()
    assert len(actions) == 1

    grid.set_context(None, None, 0, None)  # cleared before the click lands

    actions[0].trigger()  # must not raise


def test_create_cel_action_document_error_at_trigger_time_is_caught(qtbot, monkeypatch):
    """A 'Create Cel Here' action built while the destination frame had room
    is refused through the shipped ``DocumentError`` catch if a concurrent
    mutation (another view, automation) fills that frame to
    ``MAX_LAYERS_PER_FRAME`` before the action is triggered — the SAME
    ceiling ``test_sc_ui_031_5_no_create_affordance_at_max_layers_per_frame``
    proves is checked at BUILD time; this proves it is also enforced at
    TRIGGER time, independently, by the factory itself."""
    doc, _outline_track_id = _empty_cell_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    before = stack.count()

    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)
    pos = _cell_center(grid, outline_row, 1)
    _request_context_menu(grid.viewport(), pos, reason=QContextMenuEvent.Reason.Mouse)
    actions = _FakeMenu.instances[-1].actions()
    assert len(actions) == 1

    filler_needed = MAX_LAYERS_PER_FRAME - len(doc.frames[1].layers)
    for i in range(filler_needed):
        doc.add_layer(f"Filler{i}", frame_index=1)
    assert len(doc.frames[1].layers) == MAX_LAYERS_PER_FRAME

    actions[0].trigger()

    assert stack.count() == before


def test_tiny_move_below_the_drag_threshold_does_not_start_a_drag_yet(qtbot):
    """A move of just 1px right after a press — below Qt's own
    ``startDragDistance()`` — must not flip the gesture into a live drag
    yet: the cursor stays untouched, and the event passes through to the
    base ``QTableView`` instead of being consumed as a drag-indicator
    update."""
    doc = _make_two_track_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    pos = _cell_center(grid, 0, 0)
    default_shape = grid.cursor().shape()
    threshold = QApplication.startDragDistance()

    qtbot.mousePress(grid.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    qtbot.mouseMove(
        grid.viewport(), pos=QPoint(pos.x() + max(1, threshold - 1), pos.y())
    )

    assert grid.cursor().shape() == default_shape

    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=pos)


def test_clicked_signal_with_invalid_index_is_a_safe_no_op(qtbot):
    """A stray ``clicked`` signal carrying an invalid index (Qt itself never
    emits this for a real click, but the connected slot is a real signal
    handler and must not assume otherwise) changes no selection and pushes
    nothing — driven through ``QAbstractItemView.clicked``, the SAME public
    signal a real click delivers, not a private seam."""
    doc = _make_two_track_doc()
    panel, grid, _stack = _make_panel(qtbot, doc)
    frame_events = []
    layer_events = []
    panel.frameSelected.connect(frame_events.append)
    panel.layerSelected.connect(layer_events.append)

    grid.clicked.emit(grid.model().index(-1, -1))  # must not raise

    assert frame_events == []
    assert layer_events == []
