"""Reference board acceptance tests (REQ-P9-UI-006 / REQ-P9-DATA-002).

Scenario SC-UI-006-1: add / arrange / zoom reference images non-destructively;
the board persists via the defensive ``.pixboard`` serialiser and a malformed
file surfaces a user-facing error (never a crash / arbitrary execution). Both
themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QImage

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


def _board(qtbot):
    board = Reference_Board()
    qtbot.addWidget(board)
    return board


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
