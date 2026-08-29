"""Phase-5 animation UI guard-branch coverage (REQ-P5-UI, both themes).

Third companion to ``test_animation_timeline.py`` / ``_wiring.py``: it drives the
defensive / early-return branches of the Phase-5 ``ui/`` modules (unbound-panel
no-ops, ``None`` refresh hooks, out-of-range indices, empty sequencing inputs) so
the ``pixelart_creator.ui`` branch-coverage gate holds (>=80 branch, FU-9). Pure
UI-level guard assertions; no domain maths (Article I). Both themes via the autouse
``theme`` fixture.
"""

from __future__ import annotations

from typing import List

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.animation import FrameTag, PlaybackMode
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.frame_tags_panel import Frame_Tags_Panel, Tag_Dialog
from pixelart_creator.ui.playback_controls import Playback_Controls
from pixelart_creator.ui.timeline_panel import Timeline_Panel
from PySide6.QtWidgets import QDialog, QMessageBox

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _doc(frames: int = 3) -> Document:
    doc = Document(64, 64, palette=Palette(STARTER))
    for _ in range(frames - 1):
        doc.add_frame()
    return doc


def _lang_change(widget) -> None:
    widget.changeEvent(QEvent(QEvent.Type.LanguageChange))


# -- Timeline_Panel unbound / guard branches --------------------------------


def test_timeline_unbound_guards(qtbot):
    """An unbound panel's queries + rebuild + retranslate are safe no-ops."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    assert panel.document is None
    panel.rebuild()  # document None -> loop skipped
    assert panel._thumbnail(0).isNull()  # doc None -> empty pixmap
    assert panel._tags_for_frame(0) == ""  # doc None -> empty marker
    _lang_change(panel)  # changeEvent with document None
    assert panel._strip.count() == 0


def test_timeline_rebuild_clamps_stale_active_index(qtbot):
    """rebuild() clamps an active index that now exceeds the frame count."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.set_context(_doc(2), QUndoStack(), lambda: None)
    panel._active_index = 5  # stale (beyond the 2 frames)
    panel.rebuild()
    assert panel.active_index == 1  # clamped to last valid frame


def test_timeline_updating_flag_suppresses_seams(qtbot):
    """The internal ``_updating`` flag suppresses press/enter re-entrancy."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.set_context(_doc(3), QUndoStack(), lambda: None)
    fired: List[int] = []
    panel.frameSelected.connect(fired.append)
    panel.frameScrubbed.connect(fired.append)
    panel._updating = True
    panel._on_item_pressed(panel._strip.item(1))
    panel._on_item_entered(panel._strip.item(1))
    panel._updating = False
    assert fired == []


def test_timeline_push_and_refresh_none_hooks(qtbot):
    """_push with no stack and _refresh with no frames-changed hook are safe."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    doc = _doc(3)
    panel._document = doc  # bind document but leave stack + hook None
    panel._stack = None
    panel._on_frames_changed = None
    cmd = doc.make_add_frame_command(after_index=0)
    panel._push(cmd, "noop")  # stack None -> returns without pushing
    assert doc.frames and len(doc.frames) == 3  # not applied
    panel._refresh()  # on_frames_changed None -> just rebuilds


def test_timeline_remove_at_index_zero_keeps_active(qtbot):
    """Removing frame 0 leaves the active index at 0 (no decrement below zero)."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    doc = _doc(3)
    stack = QUndoStack()
    panel.set_context(doc, stack, lambda: None)
    panel.select_frame(0)
    panel._on_remove()
    assert stack.count() == 1
    assert panel.active_index == 0


def test_timeline_duration_committed_out_of_range(qtbot):
    """Committing a duration with a stale out-of-range active index is a no-op."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    doc = _doc(2)
    stack = QUndoStack()
    panel.set_context(doc, stack, lambda: None)
    panel._active_index = 9  # out of range
    panel._on_duration_committed()
    assert stack.count() == 0


# -- Playback_Controls guard branches ---------------------------------------


def test_playback_pause_when_idle_is_noop(qtbot):
    """pause() while not playing returns immediately."""
    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)
    ctrl.pause()  # not playing -> early return
    assert ctrl.is_playing() is False


def test_playback_advance_without_steps(qtbot):
    """_advance() with no active step iterator returns without emitting."""
    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)
    fired: List[int] = []
    ctrl.frameAdvanced.connect(fired.append)
    ctrl._advance()  # _steps is None -> early return
    assert fired == []


def test_playback_current_frame_default_zero(qtbot):
    """_current_frame falls back to 0 when no current-frame provider is bound."""
    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)
    assert ctrl._current_frame() == 0


def test_playback_compute_order_edge_cases():
    """_compute_order handles a zero frame count and an exhausted iterator."""
    assert Playback_Controls._compute_order(iter([]), 0) == []
    assert Playback_Controls._compute_order(iter([]), 3) == []  # StopIteration break


# -- Frame_Tags_Panel guard branches ----------------------------------------


def test_tags_unbound_guards(qtbot):
    """An unbound tags panel's rebuild + CRUD entry points are safe no-ops."""
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    panel.rebuild()  # document None -> loop skipped
    panel._on_add()
    panel._on_edit()
    panel._on_remove()
    panel._on_play()
    assert panel._list.count() == 0


def test_tags_push_and_refresh_none_hooks(qtbot):
    """_push with no stack and _refresh with no tags-changed hook are safe."""
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    doc = _doc(3)
    panel._document = doc
    panel._stack = None
    panel._on_tags_changed = None
    cmd = doc.make_add_tag_command("x", 0, 1)
    panel._push(cmd, "noop")  # stack None -> no push
    assert len(doc.frame_tags) == 0
    panel._refresh()  # on_tags_changed None -> just rebuilds


def test_tags_edit_invalid_range_warns(qtbot, monkeypatch):
    """Editing a tag to an inverted range surfaces a warning and pushes nothing."""
    doc = _doc(4)
    doc.make_add_tag_command("walk", 0, 2).execute()
    stack = QUndoStack()
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, stack, lambda: None)
    panel._list.setCurrentRow(0)
    warned: List[object] = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: warned.append(a))
    )
    monkeypatch.setattr(
        Tag_Dialog, "exec", lambda self: int(QDialog.DialogCode.Accepted)
    )
    monkeypatch.setattr(
        Tag_Dialog,
        "result_fields",
        lambda self: ("walk", 3, 1, PlaybackMode.LOOP, 0, "#ff0000ff"),  # inverted
    )
    panel._on_edit()
    assert warned
    assert stack.count() == 0
