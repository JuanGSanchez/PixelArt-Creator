"""Phase-5 animation UI wiring/branch coverage (REQ-P5-UI-001..019, both themes).

Companion to ``test_animation_timeline.py``: this module exercises the remaining
branches of the Phase-5 ``ui/`` modules the UI layer built — dialog field collection,
``_retranslate`` on ``QEvent.LanguageChange`` (F5), tint/colour pickers, guard and
error paths, the off-thread pre-warm gating + streaming resume, the progress
indicator, the off-thread warm runnable, and the derived-cache API — so the
``pixelart_creator.ui`` coverage gate holds (>=90 line / >=80 branch, FU-9). Every
test runs under both themes via the autouse ``theme`` fixture. UI-level wiring
only; no domain maths (Article I).
"""

from __future__ import annotations

import threading
from typing import List

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QDialog,
    QMessageBox,
)

from pixelart_creator.logic.animation import (
    DEFAULT_PLAYBACK_MODE,
    FrameTag,
    PlaybackMode,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.composite_warmer import (
    CompositeWarmSignals,
    FrameCompositeWarmRunnable,
)
from pixelart_creator.ui.frame_cache import FrameCompositeCache
from pixelart_creator.ui.frame_tags_panel import Frame_Tags_Panel, Tag_Dialog
from pixelart_creator.ui.onion_skin_controls import Onion_Skin_Controls, OnionSettings
from pixelart_creator.ui.playback_controls import Playback_Controls
from pixelart_creator.ui.prewarm_indicator import Prewarm_Indicator
from pixelart_creator.ui.timeline_panel import Timeline_Panel

STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]
RED = (230, 30, 30, 255)


def _paint(document: Document, frame_index: int, value) -> None:
    document.frames[frame_index].layers[0].buffer.fill_rect(
        0, 0, document.width, document.height, value
    )


def _lang_change(widget) -> None:
    """Deliver a synthetic ``LanguageChange`` so ``_retranslate`` re-runs (F5)."""
    widget.changeEvent(QEvent(QEvent.Type.LanguageChange))


@pytest.fixture
def make_doc():
    def _make(frames: int = 3, width: int = 64, height: int = 64) -> Document:
        doc = Document(width, height, palette=Palette(STARTER))
        for _ in range(frames - 1):
            doc.add_frame()
        return doc

    return _make


@pytest.fixture
def transport(qtbot):
    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)

    def _bind(durations: List[int], current: int = 0) -> None:
        holder = {"cur": current}
        ctrl.set_context(lambda: list(durations), lambda: holder["cur"])

    return ctrl, _bind


# -- Timeline_Panel branches -------------------------------------------------


def test_timeline_tag_markers_and_tooltip(qtbot, make_doc):
    """A tag spanning a frame renders its name on the cell + a duration tooltip."""
    doc = make_doc(4)
    doc.make_add_tag_command("walk", 1, 2, mode=PlaybackMode.LOOP).execute()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, QUndoStack(), lambda: None)
    assert "walk" in panel._strip.item(1).text()
    assert "walk" not in panel._strip.item(0).text()
    assert "ms" in panel._strip.item(0).toolTip()


def test_timeline_indexed_doc_thumbnail(qtbot, theme):
    """An indexed document renders per-cell thumbnails via the palette LUT path."""
    doc = Document(32, 32, mode=ColorMode.INDEXED, palette=Palette(STARTER))
    doc.add_frame()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, QUndoStack(), lambda: None)
    assert panel._strip.count() == 2


def test_timeline_selection_and_scrub_seams(qtbot, make_doc):
    """Row change + item press emit frameSelected; a held-button hover scrubs."""
    doc = make_doc(3)
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, QUndoStack(), lambda: None)
    selected: List[int] = []
    scrubbed: List[int] = []
    panel.frameSelected.connect(selected.append)
    panel.frameScrubbed.connect(scrubbed.append)
    panel._strip.setCurrentRow(2)
    panel._on_item_pressed(panel._strip.item(1))
    assert 2 in selected and 1 in selected
    panel._on_item_entered(panel._strip.item(0))  # no button -> no-op
    orig = QApplication.mouseButtons
    QApplication.mouseButtons = staticmethod(lambda: Qt.MouseButton.LeftButton)
    try:
        panel._on_item_entered(panel._strip.item(0))  # button held -> scrub
    finally:
        QApplication.mouseButtons = orig
    assert scrubbed == [0]


def test_timeline_guard_and_theme_branches(qtbot, make_doc):
    """Guards: unbound ops, out-of-range select, no-op/invalid reorder, retranslate."""
    doc = make_doc(3)
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.select_frame(0)  # unbound: document is None -> no-op
    panel._on_add()
    panel._on_remove()
    panel._on_duplicate()
    panel._on_duration_committed()
    panel.set_context(doc, QUndoStack(), lambda: None)
    panel.select_frame(999)  # out of range -> ignored
    assert panel.active_index != 999
    stack = panel._stack
    # start=1, dest-row=2 maps to to_index 1 == from_index -> no-op rebuild.
    panel._on_rows_moved(None, 1, 1, None, 2)
    assert stack.count() == 0
    panel._on_rows_moved(None, 0, 0, None, 99)  # invalid destination -> rebuild
    assert stack.count() == 0
    panel.set_active_frame_role(QColor(10, 20, 30))
    _lang_change(panel)
    assert panel._strip.count() == 3


def test_timeline_duration_spin_disabled_without_frames(qtbot):
    """The duration spin disables when the panel has no bound document."""
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel._sync_duration_spin()
    assert panel._duration_spin.isEnabled() is False


# -- Playback_Controls branches ---------------------------------------------


def test_playback_pause_then_resume(transport, qtbot):
    """Resuming after a pause continues from the retained iterator."""
    ctrl, bind = transport
    bind([5, 5, 5])
    seen: List[int] = []
    ctrl.frameAdvanced.connect(seen.append)
    ctrl.play()
    qtbot.waitUntil(lambda: len(seen) >= 1, timeout=2000)
    ctrl.pause()
    n = len(seen)
    ctrl.play()  # resume path
    assert ctrl.is_playing() is True
    qtbot.waitUntil(lambda: len(seen) > n, timeout=2000)
    ctrl.stop()


def test_playback_no_context_and_empty_durations(qtbot):
    """play/stop are safe with no context and with an empty durations list."""
    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)
    ctrl.play()  # no provider -> early return
    ctrl.play_tag(FrameTag("x", 0, 0))
    assert ctrl.is_playing() is False
    ctrl.set_context(lambda: [], lambda: 0)  # bound but empty
    ctrl.play()
    ctrl.play_tag(FrameTag("x", 0, 0))
    assert ctrl.is_playing() is False
    assert ctrl.mode_label(PlaybackMode.REVERSE)


def test_playback_cold_frame_streams_via_prewarm(transport, qtbot):
    """A cold frame makes the transport wait, then resume on notify_frame_ready."""
    ctrl, bind = transport
    bind([5, 5, 5])
    ready = {0}
    warmed: List[List[int]] = []
    ctrl.set_prewarm_context(lambda i: i in ready, warmed.append)
    seen: List[int] = []
    ctrl.frameAdvanced.connect(seen.append)
    ctrl.play()
    assert warmed and warmed[0][0] == 0
    qtbot.waitUntil(lambda: ctrl._awaiting_index == 1, timeout=2000)
    assert ctrl._timer.isActive() is False
    ready.add(1)
    ctrl.notify_frame_ready(1)
    assert 1 in seen
    ctrl.notify_frame_ready(99)  # not awaiting -> no-op
    ctrl.stop()


def test_playback_resume_after_gap_while_awaiting(transport, qtbot):
    """Pausing while awaiting a cold frame and resuming re-gates then advances it."""
    ctrl, bind = transport
    bind([5, 5, 5])
    ready = {0}
    ctrl.set_prewarm_context(lambda i: i in ready, lambda order: None)
    ctrl.frameAdvanced.connect(lambda _i: None)
    ctrl.play()
    qtbot.waitUntil(lambda: ctrl._awaiting_index == 1, timeout=2000)
    ctrl.pause()
    ctrl.play()  # _resume_after_gap: still cold -> keeps waiting
    assert ctrl._awaiting_index == 1
    ready.add(1)
    ctrl._resume_after_gap()  # now warm -> advances
    ctrl.stop()


# -- Onion_Skin_Controls tint pickers ---------------------------------------


def test_onion_tint_pickers(qtbot, monkeypatch):
    """Choosing prev/next tints via the colour dialog re-emits settingsChanged."""
    controls = Onion_Skin_Controls()
    qtbot.addWidget(controls)
    emitted: List[OnionSettings] = []
    controls.settingsChanged.connect(emitted.append)
    monkeypatch.setattr(
        QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor(1, 2, 3, 200))
    )
    controls._pick_prev_tint()
    controls._pick_next_tint()
    assert emitted[-1].tint_prev == (1, 2, 3, 200)
    assert emitted[-1].tint_next == (1, 2, 3, 200)
    monkeypatch.setattr(
        QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor())
    )
    before = len(emitted)
    controls._pick_prev_tint()  # cancelled -> unchanged
    assert len(emitted) == before
    _lang_change(controls)


# -- Frame_Tags_Panel + Tag_Dialog branches ---------------------------------


def test_tag_dialog_fields_and_colour(qtbot, monkeypatch):
    """Tag_Dialog collects fields, edits an existing tag, and picks a colour."""
    existing = FrameTag(
        "run", 1, 3, mode=PlaybackMode.ONCE, repeat=2, color="#0a0b0cff"
    )
    dialog = Tag_Dialog(5, existing)
    qtbot.addWidget(dialog)
    name, frm, to, mode, repeat, _color = dialog.result_fields()
    assert (name, frm, to, mode, repeat) == ("run", 1, 3, PlaybackMode.ONCE, 2)
    monkeypatch.setattr(
        QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor(10, 20, 30, 255))
    )
    dialog._pick_color()
    assert dialog.result_fields()[5].lower().startswith("#0a141e")
    dialog._color = "not-a-colour"  # malformed -> defensive fallback paint
    dialog._paint_color_button()
    monkeypatch.setattr(
        QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor())
    )
    dialog._pick_color()  # invalid -> no change
    _lang_change(dialog)


def test_tag_dialog_new_defaults(qtbot):
    """A fresh Tag_Dialog defaults its mode to the global default (LOOP)."""
    dialog = Tag_Dialog(3, None)
    qtbot.addWidget(dialog)
    assert dialog.result_fields()[3] is DEFAULT_PLAYBACK_MODE


def test_tags_panel_dialog_paths(qtbot, make_doc, monkeypatch):
    """Add + edit via the real dialog (accepted) and a cancelled dialog (no push)."""
    doc = make_doc(4)
    stack = QUndoStack()
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, stack, lambda: None)
    monkeypatch.setattr(
        Tag_Dialog, "exec", lambda self: int(QDialog.DialogCode.Accepted)
    )
    monkeypatch.setattr(
        Tag_Dialog,
        "result_fields",
        lambda self: ("idle", 0, 2, PlaybackMode.LOOP, 0, "#ff0000ff"),
    )
    panel._on_add()
    assert stack.count() == 1 and doc.frame_tags[0].name == "idle"
    panel._list.setCurrentRow(0)
    monkeypatch.setattr(
        Tag_Dialog,
        "result_fields",
        lambda self: ("idle2", 1, 3, PlaybackMode.REVERSE, 1, "#00ff00ff"),
    )
    panel._on_edit()
    assert doc.frame_tags[0].name == "idle2"
    monkeypatch.setattr(
        Tag_Dialog, "exec", lambda self: int(QDialog.DialogCode.Rejected)
    )
    before = stack.count()
    panel._on_add()
    panel._on_edit()
    assert stack.count() == before


def test_tags_panel_invalid_range_warns(qtbot, make_doc, monkeypatch):
    """An invalid tag range surfaces a QMessageBox warning and pushes no command."""
    doc = make_doc(3)
    stack = QUndoStack()
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, stack, lambda: None)
    warnings: List[object] = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a))
    )
    monkeypatch.setattr(
        Tag_Dialog, "exec", lambda self: int(QDialog.DialogCode.Accepted)
    )
    monkeypatch.setattr(
        Tag_Dialog,
        "result_fields",
        lambda self: ("bad", 2, 1, PlaybackMode.LOOP, 0, "#ff0000ff"),  # inverted
    )
    panel._on_add()
    assert warnings
    assert stack.count() == 0


def test_tags_panel_no_selection_guards(qtbot, make_doc):
    """Edit/remove/play with no selection are safe no-ops; LanguageChange re-runs."""
    doc = make_doc(3)
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, QUndoStack(), lambda: None)
    played: List[object] = []
    panel.playTagRequested.connect(played.append)
    panel._on_edit()
    panel._on_remove()
    panel._on_play()
    assert played == []
    _lang_change(panel)


# -- Prewarm_Indicator -------------------------------------------------------


def test_prewarm_indicator_lifecycle(qtbot):
    """The indicator shows on start, tracks progress, cancels, and hides on finish."""
    indicator = Prewarm_Indicator()
    qtbot.addWidget(indicator)
    assert indicator.isVisible() is False
    indicator.start(3)
    assert indicator.isVisible() is True
    indicator.set_progress(2, 3)
    assert indicator._bar.value() == 2
    cancelled: List[int] = []
    indicator.cancelRequested.connect(lambda: cancelled.append(1))
    indicator._cancel_button.click()
    assert cancelled == [1]
    indicator.finish()
    assert indicator.isVisible() is False
    _lang_change(indicator)
    assert indicator.accessibleName()


# -- composite_warmer runnable ----------------------------------------------


def test_composite_warm_runnable_emits(qtbot, make_doc):
    """The off-thread runnable flattens a frame and emits it via the carrier."""
    doc = make_doc(1)
    _paint(doc, 0, RED)
    signals = CompositeWarmSignals()
    got: List[tuple] = []
    signals.frameReady.connect(lambda t, i, b: got.append((t, i, b)))
    cancel = threading.Event()
    FrameCompositeWarmRunnable(
        7, 0, doc.frames[0].layers, doc.width, doc.height, cancel, signals
    ).run()
    assert got and got[0][0] == 7 and got[0][1] == 0
    assert isinstance(got[0][2], PixelBuffer)
    got.clear()
    cancel.set()
    FrameCompositeWarmRunnable(
        8, 0, doc.frames[0].layers, doc.width, doc.height, cancel, signals
    ).run()  # pre-set cancel -> early exit, no emission
    assert got == []


# -- FrameCompositeCache unit branches --------------------------------------


def test_frame_cache_api_branches():
    """Cover the cache's guard, membership, discard and diagnostics branches."""
    with pytest.raises(ValueError):
        FrameCompositeCache(0)
    cache = FrameCompositeCache(PixelBuffer(32, 32, ColorMode.RGBA).data.nbytes * 2)
    buf = PixelBuffer(32, 32, ColorMode.RGBA)
    cache.put(0, buf)
    assert (0 in cache) is True and cache.contains(0) is True
    assert cache.get(0) is buf and cache.get(99) is None
    cache.put(0, PixelBuffer(32, 32, ColorMode.RGBA))  # overwrite same index
    assert cache.resident_frames == 1
    cache.discard(0)
    assert cache.contains(0) is False
    cache.discard(0)  # discard a missing index -> no-op
    assert cache.resident_frames == 0
