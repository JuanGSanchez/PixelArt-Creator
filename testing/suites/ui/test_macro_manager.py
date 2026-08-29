"""Macro save / load / list — SC-UI-003-1 (REQ-P8-UI-003, REQ-P8-LOGIC-007).

The macro-management UI saves a recorded macro to a ``.pixmacro`` file and loads
it back through the defensive, ``eval``-free ``data.macro_io`` path (IO-3): a
valid macro round-trips to an equal :class:`Macro` (and therefore replays
identically), while a malformed / unsupported-version file surfaces a user-facing
error — never a crash, never arbitrary execution. Headless; both themes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from pixelart_creator.logic.macro import Macro
from pixelart_creator.ui.main_window import Main_Window
from tests.ui._automation_helpers import (
    arrays_equal,
    buffer_of,
    macro_of,
    procgen_op,
    replay,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_003_save_then_load_round_trips_and_replays_identically(
    qtbot, monkeypatch, tmp_path
):
    """SC-UI-003-1: a saved macro reloads to an equal macro that replays identically."""
    win = _window(qtbot)
    controls = win._macro_controls
    macro = macro_of(procgen_op(seed=11))
    controls._add_macro(macro, "recording")  # add + select

    out = tmp_path / "m.pixmacro"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), ""))
    )
    controls._on_save()
    assert out.exists()

    # Load it back via the defensive, eval-free UI path into a new list row.
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(out), ""))
    )
    controls._on_load()
    assert controls._list.count() == 2
    loaded = controls._list.item(1).data(Qt.ItemDataRole.UserRole)
    assert isinstance(loaded, Macro)
    assert loaded == macro  # round-trip identity (no tuple/int-key drift)

    # …and it replays to the identical result the original macro produces.
    win_a = _window(qtbot)
    replay(qtbot, win_a, macro)
    win_b = _window(qtbot)
    replay(qtbot, win_b, loaded)
    assert arrays_equal(
        buffer_of(win_a.active_document()), buffer_of(win_b.active_document())
    )


def test_sc_ui_003_malformed_macro_file_surfaces_error_no_crash(
    qtbot, monkeypatch, tmp_path, mute_message_boxes
):
    """SC-UI-003-1: a malformed macro file is rejected gracefully (no crash/execution)."""
    win = _window(qtbot)
    controls = win._macro_controls
    before = controls._list.count()

    # Well-formed JSON, unsupported schema_version → MacroIOError on defensive load.
    bad = tmp_path / "bad.pixmacro"
    bad.write_text(
        '{"format": "pixmacro", "schema_version": "999", "ops": []}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(bad), ""))
    )
    controls._on_load()  # must not raise / execute

    assert controls._list.count() == before  # nothing added
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)


def test_sc_ui_003_non_json_macro_file_surfaces_error(
    qtbot, monkeypatch, tmp_path, mute_message_boxes
):
    """SC-UI-003-1: a non-JSON ``.pixmacro`` is rejected gracefully, not executed."""
    win = _window(qtbot)
    controls = win._macro_controls

    junk = tmp_path / "junk.pixmacro"
    junk.write_text("this is not json {", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(junk), ""))
    )
    controls._on_load()

    assert controls._list.count() == 0
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)
