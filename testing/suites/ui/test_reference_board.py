"""Reference board acceptance tests (REQ-P9-UI-006 / REQ-P9-DATA-002).

Scenario SC-UI-006-1: add / arrange / zoom reference images non-destructively;
the board persists via the defensive ``.pixboard`` serialiser and a malformed
file surfaces a user-facing error (never a crash / arbitrary execution).

D-10 (CF-30): the corner-drag resize + raise/lower context actions closing
REQ-P9-UI-006's move/**resize**/z-order clause — gesture -> the SAME persisted
fields ``to_layout()`` already round-trips (``transform`` scale components,
``z_order``), driven through the real ``Reference_Item`` mouse/context-menu
event handlers (never calling the private ``_apply_resize`` or mutating
``zValue()`` directly). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QGraphicsSceneContextMenuEvent,
    QGraphicsSceneMouseEvent,
)

from pixelart_creator.data.reference_board_io import (
    ReferenceBoardIOError,
    load_board,
    save_board,
)
from pixelart_creator.ui.reference_board import Reference_Board


@pytest.fixture
def png_path(tmp_path):
    """Write a tiny valid PNG and return its path (a loadable reference image)."""
    path = tmp_path / "ref.png"
    img = QImage(8, 8, QImage.Format.Format_RGBA8888)
    img.fill(0xFF3366CC)
    assert img.save(str(path), "PNG")
    return str(path)


@pytest.fixture
def wide_png_path(tmp_path):
    """A 100x60 PNG — large enough that the four 10px corner handles don't
    overlap, so a press lands unambiguously on one corner (D-10)."""
    path = tmp_path / "wide_ref.png"
    img = QImage(100, 60, QImage.Format.Format_RGBA8888)
    img.fill(0xFF3366CC)
    assert img.save(str(path), "PNG")
    return str(path)


def _board(qtbot):
    board = Reference_Board()
    qtbot.addWidget(board)
    return board


def _mouse_event(etype, local_pos, scene_pos, modifiers=Qt.KeyboardModifier.NoModifier):
    event = QGraphicsSceneMouseEvent(etype)
    event.setPos(QPointF(*local_pos))
    event.setScenePos(QPointF(*scene_pos))
    event.setButton(Qt.MouseButton.LeftButton)
    event.setButtons(Qt.MouseButton.LeftButton)
    event.setModifiers(modifiers)
    return event


def _drag_corner(
    item, local_press, scene_move, modifiers=Qt.KeyboardModifier.NoModifier
):
    """Drive the real gesture: press ON a corner handle, move, release."""
    from PySide6.QtCore import QEvent

    press = _mouse_event(QEvent.Type.GraphicsSceneMousePress, local_press, local_press)
    item.mousePressEvent(press)
    move = _mouse_event(
        QEvent.Type.GraphicsSceneMouseMove, scene_move, scene_move, modifiers
    )
    item.mouseMoveEvent(move)
    release = _mouse_event(
        QEvent.Type.GraphicsSceneMouseRelease, scene_move, scene_move
    )
    item.mouseReleaseEvent(release)


# --- SC-UI-006-1: add / arrange references ---------------------------------- #


def test_sc_ui_006_1_add_image(qtbot, png_path):
    """SC-UI-006-1: a valid image is added as one board item."""
    board = _board(qtbot)
    item = board.add_image(png_path)
    assert item is not None
    assert len(board.items()) == 1


def test_sc_ui_006_1_bad_image_is_rejected_without_crash(qtbot, tmp_path, monkeypatch):
    """SC-UI-006-1: a non-image file surfaces a notice and adds nothing."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    bad = tmp_path / "not_an_image.png"
    bad.write_text("this is not a PNG", encoding="utf-8")
    board = _board(qtbot)
    assert board.add_image(str(bad)) is None
    assert board.items() == []


# --- SC-UI-006-1: non-destructive persistence round-trip -------------------- #


def test_sc_ui_006_1_layout_round_trips_through_disk(qtbot, tmp_path, png_path):
    """SC-UI-006-1: to_layout -> save -> load -> apply preserves the board state."""
    board = _board(qtbot)
    item = board.add_image(png_path)
    item.setPos(12.0, 34.0)
    item.setZValue(3.0)
    layout = board.to_layout()
    target = save_board(layout, tmp_path / "board")
    assert target.suffix == ".pixboard"

    reloaded = load_board(target)
    assert len(reloaded.images) == 1
    assert reloaded.images[0].image == png_path
    assert reloaded.images[0].z_order == 3

    board2 = _board(qtbot)
    board2.apply_layout(reloaded)
    assert len(board2.items()) == 1
    assert board2.items()[0].pos().x() == pytest.approx(12.0)
    assert board2.items()[0].pos().y() == pytest.approx(34.0)


def test_sc_ui_006_1_malformed_file_raises_user_facing_error(tmp_path):
    """SC-UI-006-1: a malformed .pixboard raises ReferenceBoardIOError (no eval)."""
    bad = tmp_path / "broken.pixboard"
    bad.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(ReferenceBoardIOError):
        load_board(bad)


def test_sc_ui_006_1_unknown_version_raises(tmp_path):
    """SC-UI-006-1: an unknown schema_version is rejected defensively."""
    bad = tmp_path / "future.pixboard"
    bad.write_text(
        '{"format": "pixboard", "schema_version": "999", '
        '"pan": [0, 0], "zoom": 1.0, "images": []}',
        encoding="utf-8",
    )
    with pytest.raises(ReferenceBoardIOError):
        load_board(bad)


def test_sc_ui_006_1_board_uses_its_own_scene_not_the_document(qtbot, png_path):
    """SC-UI-006-1: references live on the board's own scene (non-destructive)."""
    board = _board(qtbot)
    item = board.add_image(png_path)
    # The item belongs to the board's private scene, never a document scene.
    assert item.scene() is board._scene


# --- D-10: corner-drag resize -> persisted transform ------------------------ #


def test_d10_corner_drag_resize_writes_to_layout_transform(qtbot, wide_png_path):
    """D-10/CF-30: a bottom-right corner drag scales the item; the new scale
    lands in ``to_layout()``'s persisted ``transform`` tuple (m11/m22)."""
    board = _board(qtbot)
    item = board.add_image(wide_png_path)
    assert item.transform().m11() == 1.0  # unresized baseline

    # ``boundingRect()`` for a 100x60 pixmap carries QGraphicsPixmapItem's
    # default 0.5px shape margin: (-0.5, -0.5, 101, 61). Dragging the 'br'
    # handle to scene (201.5, 121.5) doubles both axes exactly, with the 'tl'
    # anchor (-0.5, -0.5) staying fixed in scene space.
    _drag_corner(item, local_press=(95.0, 55.0), scene_move=(201.5, 121.5))

    assert item.transform().m11() == pytest.approx(2.0)
    assert item.transform().m22() == pytest.approx(2.0)
    assert item.pos().x() == pytest.approx(0.5)  # tl anchor stayed fixed
    assert item.pos().y() == pytest.approx(0.5)

    entry = board.to_layout().images[0]
    assert entry.transform[0] == pytest.approx(2.0)  # m11
    assert entry.transform[3] == pytest.approx(2.0)  # m22


def test_d10_corner_drag_resize_restores_move_flag_after_release(qtbot, wide_png_path):
    """D-10: the resize drag temporarily disables ``ItemIsMovable`` (so the two
    gestures never fight over one press) and restores it on release."""
    from PySide6.QtWidgets import QGraphicsPixmapItem

    board = _board(qtbot)
    item = board.add_image(wide_png_path)
    flag = QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable
    assert bool(item.flags() & flag) is True

    _drag_corner(item, local_press=(95.0, 55.0), scene_move=(150.0, 90.0))

    assert bool(item.flags() & flag) is True  # restored after the drag ends


def test_d10_shift_held_preserves_the_drag_start_aspect_ratio(qtbot, wide_png_path):
    """D-10: holding Shift during the corner drag locks X/Y to one factor."""
    board = _board(qtbot)
    item = board.add_image(wide_png_path)

    # Asymmetric drag target (would be a 1.5x / 1.0x free resize) with Shift
    # held -> the two axis factors average to one shared scale.
    _drag_corner(
        item,
        local_press=(95.0, 55.0),
        scene_move=(150.0, 60.0),
        modifiers=Qt.KeyboardModifier.ShiftModifier,
    )

    assert item.transform().m11() == pytest.approx(item.transform().m22())


def test_d10_resize_never_crosses_zero_or_flips(qtbot, wide_png_path):
    """D-10: a drag collapsed past the anchor clamps to the minimum positive
    scale (``_MIN_REFERENCE_SCALE``) — never zero, never a mirror flip."""
    board = _board(qtbot)
    item = board.add_image(wide_png_path)

    # Drag the 'br' handle almost onto the 'tl' anchor (near-zero target size).
    _drag_corner(item, local_press=(95.0, 55.0), scene_move=(0.1, 0.1))

    assert item.transform().m11() > 0.0
    assert item.transform().m22() > 0.0


# --- D-10: raise/lower context actions -> persisted z_order ----------------- #


class _FakeContextAction:
    """Identity-comparable stand-in for the ``QAction`` a fake menu offers."""

    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _FakeContextMenu:
    """A no-exec ``QMenu`` stand-in whose ``exec`` returns a preset choice
    (patched onto ``pixelart_creator.ui.reference_board.QMenu`` — the module
    reference the item's ``contextMenuEvent`` actually calls)."""

    #: Index into the actions added this invocation, or ``None`` (Cancel/no pick).
    choose_index: "int | None" = None

    def __init__(self, *_args, **_kwargs) -> None:
        self._actions: list = []

    def addAction(self, text):  # noqa: N802, ANN001
        action = _FakeContextAction(text)
        self._actions.append(action)
        return action

    def exec(self, *_args, **_kwargs):  # noqa: A003
        if _FakeContextMenu.choose_index is None:
            return None
        return self._actions[_FakeContextMenu.choose_index]


def _context_event():
    from PySide6.QtCore import QEvent

    event = QGraphicsSceneContextMenuEvent(QEvent.Type.GraphicsSceneContextMenu)
    event.setReason(QGraphicsSceneContextMenuEvent.Reason.Mouse)
    event.setScreenPos(QPointF(0.0, 0.0).toPoint())
    return event


def test_d10_raise_action_sets_zvalue_above_all_siblings(
    qtbot, wide_png_path, png_path, monkeypatch
):
    """D-10/CF-30: "Raise" sets ``zValue()`` above every sibling; the new value
    round-trips into ``to_layout()``'s persisted ``z_order``."""
    monkeypatch.setattr("pixelart_creator.ui.reference_board.QMenu", _FakeContextMenu)
    board = _board(qtbot)
    low = board.add_image(wide_png_path)
    high = board.add_image(png_path)
    low.setZValue(0.0)
    high.setZValue(5.0)

    _FakeContextMenu.choose_index = 0  # "Raise" is added first
    low.contextMenuEvent(_context_event())

    assert low.zValue() > high.zValue()
    entries = {e.z_order for e in board.to_layout().images}
    assert max(entries) == int(low.zValue())


def test_d10_lower_action_sets_zvalue_below_all_siblings(
    qtbot, wide_png_path, png_path, monkeypatch
):
    """D-10/CF-30: "Lower" sets ``zValue()`` below every sibling."""
    monkeypatch.setattr("pixelart_creator.ui.reference_board.QMenu", _FakeContextMenu)
    board = _board(qtbot)
    low = board.add_image(wide_png_path)
    high = board.add_image(png_path)
    low.setZValue(0.0)
    high.setZValue(5.0)

    _FakeContextMenu.choose_index = 1  # "Lower" is added second
    high.contextMenuEvent(_context_event())

    assert high.zValue() < low.zValue()
    entries = {e.z_order for e in board.to_layout().images}
    assert min(entries) == int(high.zValue())


def test_d10_context_menu_cancelled_leaves_zvalue_unchanged(
    qtbot, wide_png_path, monkeypatch
):
    """D-10: dismissing the context menu (no pick) leaves ``zValue()`` alone."""
    monkeypatch.setattr("pixelart_creator.ui.reference_board.QMenu", _FakeContextMenu)
    board = _board(qtbot)
    item = board.add_image(wide_png_path)
    item.setZValue(2.0)

    _FakeContextMenu.choose_index = None  # Cancel / dismissed
    item.contextMenuEvent(_context_event())

    assert item.zValue() == 2.0
