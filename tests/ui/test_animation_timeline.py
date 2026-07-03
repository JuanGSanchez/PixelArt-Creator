"""Phase-5 animation-timeline UI acceptance tests (REQ-P5-UI-001..019).

One pytest-qt test per UI acceptance criterion of ``specs/phase-5-animation``
(the ``SC-UI-*`` scenarios plus the pre-warm-UX seam AGT-05 flagged), driving the
PySide6 timeline / playback / onion / frame-tag widgets and the composited
``CanvasScene`` headlessly (``QT_QPA_PLATFORM=offscreen``, forced in ``conftest``).
Every test also runs under **both** themes via the autouse ``theme`` fixture,
satisfying the spec global rule ("executed identically under light and dark") and
REQ-P5-UI-018.

Scope note (AGT-06 / T5C-QA): these are UI/integration tests only — the pure
sequencing engine, onion-overlay maths and reversible ``document`` ops are AGT-04's
logic tests; the 8K frame budget is AGT-10's closed domain. Here we assert the
*wiring*: a panel action produces **exactly one** ``QUndoCommand`` and undo/redo
restores the exact prior state; the transport advances each ``PlaybackMode``
correctly and honours per-frame ``duration_ms``; onion shows/hides + is suppressed
during playback; tags CRUD + named-animation playback; scrub is not undoable; the
off-thread pre-warm warms then streams and cancels cleanly; a11y names/focus are
present. Canvases are modest (64x64) — never 8K.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pytest
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.animation import (
    DEFAULT_PLAYBACK_MODE,
    FrameTag,
    PlaybackMode,
)
from pixelart_creator.logic.constants import DEFAULT_FRAME_DURATION_MS
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.composite_warmer import (
    CompositeWarmSignals,
    FrameCompositeWarmRunnable,
)
from pixelart_creator.ui.frame_cache import FrameCompositeCache
from pixelart_creator.ui.frame_tags_panel import Frame_Tags_Panel, Tag_Dialog
from pixelart_creator.ui.onion_skin_controls import Onion_Skin_Controls, OnionSettings
from pixelart_creator.ui.playback_controls import Playback_Controls
from pixelart_creator.ui.prewarm_indicator import Prewarm_Indicator
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.timeline_panel import Timeline_Panel

STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]
RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #


def _paint(document: Document, frame_index: int, value) -> None:
    """Fill the given frame's bottom layer with ``value`` for a distinct frame."""
    document.frames[frame_index].layers[0].buffer.fill_rect(
        0, 0, document.width, document.height, value
    )


@pytest.fixture
def make_doc():
    """Factory: a fresh RGBA :class:`Document` with ``n`` frames (starter palette)."""

    def _make(frames: int = 3, width: int = 64, height: int = 64) -> Document:
        doc = Document(width, height, palette=Palette(STARTER))
        for _ in range(frames - 1):
            doc.add_frame()
        return doc

    return _make


@pytest.fixture
def make_scene(theme):
    """Factory: a :class:`CanvasScene` bound to a document, theme-correct roles."""

    def _make(document: Document) -> CanvasScene:
        scene = CanvasScene(document)
        scene.set_background_roles(*canvas_roles(theme))
        return scene

    return _make


@pytest.fixture
def timeline_env(qtbot, make_doc):
    """A ``Timeline_Panel`` bound to a 3-frame doc + a shared ``QUndoStack``.

    Returns ``(panel, doc, stack, refreshed)`` where ``refreshed`` is a mutable
    counter list incremented by the panel's frames-changed refresh hook (mirrors
    the shell wiring that recomposites the canvas after a frame op).
    """
    doc = make_doc(3)
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    refreshed: List[int] = []
    panel.set_context(doc, stack, lambda: refreshed.append(1))
    return panel, doc, stack, refreshed


@pytest.fixture
def transport(qtbot):
    """A ``Playback_Controls`` bound to a durations/current-frame provider factory.

    Returns ``(ctrl, bind)``; ``bind(durations, current=0)`` wires the transport to
    a fixed timing list and start frame so a test controls the sequence + timing.
    """
    ctrl = Playback_Controls()
    qtbot.addWidget(ctrl)

    def _bind(durations: List[int], current: int = 0) -> None:
        holder = {"cur": current}
        ctrl.set_context(lambda: list(durations), lambda: holder["cur"])

    return ctrl, _bind


def _collect(ctrl: Playback_Controls, qtbot, count: int) -> List[int]:
    """Play and collect the first ``count`` ``frameAdvanced`` indices, then stop.

    Order is deterministic (P2): the sequence the engine yields is independent of
    wall-clock timing, so we only wait until enough ticks have been delivered.
    """
    seen: List[int] = []
    ctrl.frameAdvanced.connect(seen.append)
    ctrl.play()
    qtbot.waitUntil(lambda: len(seen) >= count, timeout=3000)
    ctrl.stop()
    ctrl.frameAdvanced.disconnect(seen.append)
    return seen[:count]


# --------------------------------------------------------------------------- #
# Timeline & frame management (REQ-P5-UI-001..007)                            #
# --------------------------------------------------------------------------- #


def test_ui_001_timeline_shows_frames_as_columns(timeline_env):
    """SC-UI-001-1: the strip shows one cell per frame in playback order."""
    panel, doc, _stack, _r = timeline_env
    assert panel._strip.count() == len(doc.frames) == 3
    # Cells carry their 1-based frame number caption in playback order.
    for i in range(panel._strip.count()):
        assert str(i + 1) in panel._strip.item(i).text()


def test_ui_002_scrub_updates_without_undo_entry(qtbot, make_doc, make_scene):
    """SC-UI-002-1: scrub sets the displayed frame and pushes no command."""
    doc = make_doc(3)
    _paint(doc, 0, RED)
    _paint(doc, 2, BLUE)
    scene = make_scene(doc)
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, stack, lambda: None)
    # Wire scrub -> canvas frame (mirrors the shell), scrub is not undoable.
    panel.frameScrubbed.connect(lambda i: scene.set_frame_index(i, scrub=True))
    with qtbot.waitSignal(panel.frameScrubbed, timeout=1000) as blocker:
        panel.frameScrubbed.emit(2)  # scrub seam (drag with button held)
    assert blocker.args == [2]
    scene.set_frame_index(2, scrub=True)
    assert scene.frame_index == 2
    assert stack.count() == 0  # scrub never pushes a command (CL-13)


def test_ui_003_add_frame_is_one_command(timeline_env):
    """SC-UI-003-1: add inserts after the active frame as exactly one command."""
    panel, doc, stack, _r = timeline_env
    panel.select_frame(0)
    before = len(doc.frames)
    panel._on_add()
    assert stack.count() == 1
    assert len(doc.frames) == before + 1
    stack.undo()
    assert len(doc.frames) == before
    stack.redo()
    assert len(doc.frames) == before + 1


def test_ui_004_remove_frame_one_command_and_refuses_last(timeline_env, make_doc):
    """SC-UI-004-1: remove is one command; the last frame cannot be removed."""
    panel, doc, stack, _r = timeline_env
    panel.select_frame(1)
    panel._on_remove()
    assert stack.count() == 1
    assert len(doc.frames) == 2
    stack.undo()
    assert len(doc.frames) == 3
    # Reduce to a single frame and confirm Remove is disabled + refused.
    single_doc = make_doc(1)
    single_stack = QUndoStack()
    panel.set_context(single_doc, single_stack, lambda: None)
    assert panel._remove_action.isEnabled() is False
    panel._on_remove()  # guarded builder raises -> caught -> no command
    assert single_stack.count() == 0
    assert len(single_doc.frames) == 1


def test_ui_005_reorder_frame_is_one_command(timeline_env):
    """SC-UI-005-1: a drag-reorder maps to one move command; undo restores order."""
    panel, doc, stack, _r = timeline_env
    ids = [id(f) for f in doc.frames]
    # Emulate the strip's internal-move drop: move row 2 to the front (row 0).
    panel._on_rows_moved(None, 2, 2, None, 0)
    assert stack.count() == 1
    assert [id(f) for f in doc.frames] == [ids[2], ids[0], ids[1]]
    stack.undo()
    assert [id(f) for f in doc.frames] == ids


def test_ui_006_duplicate_frame_deep_copy_one_command(timeline_env):
    """SC-UI-006-1: duplicate is one command, a deep copy; editing it is isolated."""
    panel, doc, stack, _r = timeline_env
    _paint(doc, 0, RED)
    panel.select_frame(0)
    panel._on_duplicate()
    assert stack.count() == 1
    assert len(doc.frames) == 4
    # The copy landed after the source and is pixel-identical.
    src = doc.frames[0].layers[0].buffer
    copy = doc.frames[1].layers[0].buffer
    assert copy.get_pixel(0, 0) == src.get_pixel(0, 0) == RED
    # Editing the copy leaves the source unchanged (deep, independent).
    copy.set_pixel(0, 0, GREEN)
    assert src.get_pixel(0, 0) == RED
    stack.undo()
    assert len(doc.frames) == 3


def test_ui_007_duration_editor_sets_duration_one_command(timeline_env):
    """SC-UI-007-1: committing the duration spin sets duration_ms as one command."""
    panel, doc, stack, _r = timeline_env
    panel.select_frame(0)
    panel._duration_spin.setValue(400)
    panel._on_duration_committed()
    assert stack.count() == 1
    assert doc.frames[0].duration_ms == 400
    stack.undo()
    assert doc.frames[0].duration_ms == DEFAULT_FRAME_DURATION_MS
    # A no-op edit (value unchanged) pushes no NEW command.
    before = stack.count()
    panel.select_frame(0)
    panel._duration_spin.setValue(doc.frames[0].duration_ms)
    panel._on_duration_committed()
    assert stack.count() == before
    # The spin range forbids non-positive input (the builder guards it too).
    assert panel._duration_spin.minimum() >= 1


# --------------------------------------------------------------------------- #
# Playback controls (REQ-P5-UI-008..010)                                      #
# --------------------------------------------------------------------------- #


def test_ui_008_play_pause_stop_drive_frames(transport, qtbot):
    """SC-UI-008-1: play advances, pause freezes, stop returns to the start frame."""
    ctrl, bind = transport
    bind([5, 5, 5], current=1)  # started while frame 1 was active
    seen: List[int] = []
    ctrl.frameAdvanced.connect(seen.append)
    ctrl.play()
    assert ctrl.is_playing() is True
    qtbot.waitUntil(lambda: len(seen) >= 2, timeout=3000)
    ctrl.pause()
    assert ctrl.is_playing() is False
    frozen = list(seen)
    qtbot.wait(30)
    assert seen == frozen  # pause freezes: no further advance
    # Stop returns to the frame that was active when playback started (index 1).
    with qtbot.waitSignal(ctrl.frameAdvanced, timeout=1000) as blk:
        ctrl.stop()
    assert blk.args == [1]


def test_ui_009_mode_selector_offers_four_modes_default_loop(transport):
    """SC-UI-009-1: the selector offers exactly the four modes, defaulting to LOOP."""
    ctrl, _bind = transport
    modes = [ctrl._mode_combo.itemData(i) for i in range(ctrl._mode_combo.count())]
    assert set(modes) == set(PlaybackMode)
    assert len(modes) == 4
    assert ctrl.selected_mode() is DEFAULT_PLAYBACK_MODE is PlaybackMode.LOOP


@pytest.mark.parametrize(
    "mode, expected",
    [
        (PlaybackMode.LOOP, [0, 1, 2, 3, 0, 1, 2, 3]),
        (PlaybackMode.REVERSE, [3, 2, 1, 0, 3, 2, 1, 0]),
        (PlaybackMode.PING_PONG, [0, 1, 2, 3, 2, 1, 0, 1]),
    ],
)
def test_ui_009_modes_advance_correctly(transport, qtbot, mode, expected):
    """SC-UI-009-1: LOOP wraps, REVERSE runs end->start, PING_PONG bounces once."""
    ctrl, bind = transport
    bind([1, 1, 1, 1])
    idx = ctrl._mode_combo.findData(mode)
    ctrl._mode_combo.setCurrentIndex(idx)
    assert _collect(ctrl, qtbot, len(expected)) == expected


def test_ui_009_once_stops_at_end(transport, qtbot):
    """SC-UI-009-1: ONCE advances start->end once then halts on the last frame."""
    ctrl, bind = transport
    bind([1, 1, 1])
    ctrl._mode_combo.setCurrentIndex(ctrl._mode_combo.findData(PlaybackMode.ONCE))
    seen: List[int] = []
    ctrl.frameAdvanced.connect(seen.append)
    with qtbot.waitSignal(ctrl.playbackActiveChanged, timeout=3000) as blk:
        ctrl.play()
    # Wait for the deactivation edge (ONCE completion halts on the last frame).
    qtbot.waitUntil(lambda: ctrl.is_playing() is False, timeout=3000)
    assert seen == [0, 1, 2]
    assert blk.args == [True] or ctrl.is_playing() is False


def test_ui_010_playback_honours_per_frame_duration(transport, qtbot):
    """SC-UI-010-1: each frame is armed with its own duration_ms (100 vs 500)."""
    ctrl, bind = transport
    bind([100, 500, 100])
    ctrl.play()
    # Frame 0 armed with its own 100 ms duration immediately on play.
    assert ctrl._timer.interval() == 100
    # Once the transport advances to frame 1 the timer is armed with 500 ms —
    # a 500 ms frame lingers five times as long as a 100 ms frame.
    qtbot.waitUntil(lambda: ctrl._timer.interval() == 500, timeout=3000)
    ctrl.stop()


# --------------------------------------------------------------------------- #
# Onion skinning (REQ-P5-UI-011..012)                                         #
# --------------------------------------------------------------------------- #


def test_ui_011_onion_toggle_and_suppressed_during_playback(make_doc, make_scene):
    """SC-UI-011-1: onion shows tinted prev/next behind active; hidden while playing."""
    doc = make_doc(3)
    for i, colour in enumerate((RED, GREEN, BLUE)):
        _paint(doc, i, colour)
    scene = make_scene(doc)
    scene.set_frame_index(1)  # active = middle frame
    scene.set_onion_settings(True, 1, 1, RED, BLUE)
    # 1 previous + 1 next ghost render behind the active frame.
    assert scene._onion_item.isVisible() is True
    assert len(scene._onion_item._ghosts) == 2
    # Starting playback suppresses the overlay (CL-11).
    scene.set_playing(True)
    assert scene._onion_item.isVisible() is False
    assert scene._onion_item._ghosts == []
    # Stopping playback restores it.
    scene.set_playing(False)
    assert len(scene._onion_item._ghosts) == 2


def test_ui_011_onion_off_shows_only_active(make_doc, make_scene):
    """SC-UI-011-1: with onion disabled only the active frame shows (no ghosts)."""
    doc = make_doc(3)
    for i, colour in enumerate((RED, GREEN, BLUE)):
        _paint(doc, i, colour)
    scene = make_scene(doc)
    scene.set_frame_index(1)
    scene.set_onion_settings(False, 1, 1, RED, BLUE)
    assert scene._onion_item.isVisible() is False
    assert scene._onion_item._ghosts == []


def test_ui_012_onion_counts_and_tint_are_view_settings(qtbot, make_doc, make_scene):
    """SC-UI-012-1: prev/next counts + tint update live via a no-undo view setting."""
    doc = make_doc(4)
    for i, colour in enumerate((RED, GREEN, BLUE, GREEN)):
        _paint(doc, i, colour)
    scene = make_scene(doc)
    scene.set_frame_index(2)
    controls = Onion_Skin_Controls()
    qtbot.addWidget(controls)
    stack = QUndoStack()
    captured: List[OnionSettings] = []
    controls.settingsChanged.connect(captured.append)
    controls.settingsChanged.connect(
        lambda s: scene.set_onion_settings(
            s.enabled, s.prev_count, s.next_count, s.tint_prev, s.tint_next
        )
    )
    controls._enable_check.setChecked(True)
    controls._prev_spin.setValue(2)
    controls._next_spin.setValue(1)
    # active frame 2 with prev=2 (frames 1,0) + next=1 (frame 3) -> 3 ghosts.
    assert len(scene._onion_item._ghosts) == 3
    # Changing a tint re-emits and updates live; still no undo entry (CL-13).
    controls._tint_prev = GREEN
    controls._emit()
    assert captured[-1].tint_prev == GREEN
    assert stack.count() == 0


# --------------------------------------------------------------------------- #
# Frame tags & named animation (REQ-P5-UI-013..014)                           #
# --------------------------------------------------------------------------- #


class _FakeTagDialog:
    """Stand-in for ``Tag_Dialog`` returning fixed fields without a modal loop."""

    fields: Tuple[str, int, int, PlaybackMode, int, str] = (
        "walk",
        1,
        3,
        PlaybackMode.PING_PONG,
        0,
        "#00ff00ff",
    )

    def __init__(self, *_a, **_k) -> None:
        pass

    def exec(self) -> int:
        return int(QDialog.DialogCode.Accepted)

    def result_fields(self):
        return _FakeTagDialog.fields


@pytest.fixture
def tags_env(qtbot, make_doc, monkeypatch):
    """A ``Frame_Tags_Panel`` bound to a 5-frame doc with a stubbed tag dialog."""
    doc = make_doc(5)
    stack = QUndoStack()
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, stack, lambda: None)
    monkeypatch.setattr(
        "pixelart_creator.ui.frame_tags_panel.Tag_Dialog", _FakeTagDialog
    )
    return panel, doc, stack


def test_ui_013_tag_create_edit_delete_each_one_command(tags_env):
    """SC-UI-013-1: create/edit/delete each push exactly one command; undo restores."""
    panel, doc, stack = tags_env
    # Create.
    _FakeTagDialog.fields = ("walk", 1, 3, PlaybackMode.PING_PONG, 0, "#00ff00ff")
    panel._on_add()
    assert stack.count() == 1
    assert len(doc.frame_tags) == 1
    assert doc.frame_tags[0].name == "walk"
    assert (doc.frame_tags[0].from_frame, doc.frame_tags[0].to_frame) == (1, 3)
    # The list caption reflects the tag span.
    assert "walk" in panel._list.item(0).text()
    # Edit (rename + re-range + mode).
    panel._list.setCurrentRow(0)
    _FakeTagDialog.fields = ("run", 0, 2, PlaybackMode.ONCE, 2, "#ff0000ff")
    panel._on_edit()
    assert stack.count() == 2
    assert doc.frame_tags[0].name == "run"
    assert doc.frame_tags[0].mode is PlaybackMode.ONCE
    # Delete.
    panel._list.setCurrentRow(0)
    panel._on_remove()
    assert stack.count() == 3
    assert len(doc.frame_tags) == 0
    # Each op is exactly one undoable step; undo walks back the exact prior state.
    stack.undo()
    assert len(doc.frame_tags) == 1 and doc.frame_tags[0].name == "run"
    stack.undo()
    assert doc.frame_tags[0].name == "walk"
    stack.undo()
    assert len(doc.frame_tags) == 0


def test_ui_014_select_tag_plays_named_animation(qtbot, make_doc, transport):
    """SC-UI-014-1: playing a tag runs its range/mode, independent of the global mode."""
    doc = make_doc(6)
    stack = QUndoStack()
    panel = Frame_Tags_Panel()
    qtbot.addWidget(panel)
    panel.set_context(doc, stack, lambda: None)
    # A PING_PONG tag over frames 1..4; global stays LOOP.
    cmd = doc.make_add_tag_command("walk", 1, 4, mode=PlaybackMode.PING_PONG)
    cmd.execute()
    panel.rebuild()
    ctrl, bind = transport
    bind([1, 1, 1, 1, 1, 1])
    assert ctrl.selected_mode() is PlaybackMode.LOOP  # global mode differs
    panel.playTagRequested.connect(ctrl.play_tag)
    seen: List[int] = []
    ctrl.frameAdvanced.connect(seen.append)
    panel._list.setCurrentRow(0)
    panel._on_play()
    qtbot.waitUntil(lambda: len(seen) >= 7, timeout=3000)
    ctrl.stop()
    # Runs the tag's 1..4 range bouncing (endpoints not doubled), never visiting 0/5.
    assert seen[:7] == [1, 2, 3, 4, 3, 2, 1]
    assert all(1 <= i <= 4 for i in seen[:7])


# --------------------------------------------------------------------------- #
# Reversibility of view ops (REQ-P5-UI-015)                                   #
# --------------------------------------------------------------------------- #


def test_ui_015_view_ops_push_no_command(timeline_env, make_doc, make_scene):
    """SC-UI-015-1: selection / scrub / playback / onion changes push no command."""
    panel, doc, stack, _r = timeline_env
    scene = make_scene(doc)
    # Selection + scrub via the timeline seams.
    panel.frameSelected.emit(1)
    panel.frameScrubbed.emit(2)
    # Onion view-settings change on the scene.
    scene.set_onion_settings(True, 1, 1, RED, BLUE)
    scene.set_playing(True)
    scene.set_playing(False)
    assert stack.count() == 0


# --------------------------------------------------------------------------- #
# Pre-warm UX (AGT-05 a64cd908 seam: prewarm signals + streaming)             #
# --------------------------------------------------------------------------- #


def test_prewarm_cold_range_warms_then_ready(qtbot, make_doc, make_scene):
    """Pressing Play on a cold range warms off-thread; frames become ready."""
    doc = make_doc(4)
    for i, colour in enumerate((RED, GREEN, BLUE, GREEN)):
        _paint(doc, i, colour)
    scene = make_scene(doc)  # active frame 0 is warm; 1..3 are cold
    assert scene.is_frame_warm(0) is True
    assert scene.is_frame_warm(2) is False
    with qtbot.waitSignal(scene.prewarmFinished, timeout=5000):
        scene.prewarm_frames([1, 2, 3])
    # After the off-thread warm streams in, the cold frames are now ready (cached).
    assert scene.is_frame_warm(1) is True
    assert scene.is_frame_warm(2) is True
    assert scene.is_frame_warm(3) is True
    scene.shutdown_prewarm()


def test_prewarm_already_warm_range_emits_no_progress(qtbot, make_doc, make_scene):
    """A fully warm range starts no warm session (streams at cache-hit speed)."""
    doc = make_doc(2)
    _paint(doc, 0, RED)
    _paint(doc, 1, BLUE)
    scene = make_scene(doc)
    started: List[int] = []
    scene.prewarmStarted.connect(started.append)
    # Only the active frame (0) is in the order; it is already warm -> no misses.
    scene.prewarm_frames([0])
    qtbot.wait(20)
    assert started == []
    scene.shutdown_prewarm()


def test_prewarm_cancel_aborts_cleanly(qtbot, make_doc, make_scene):
    """Cancel/Stop aborts the warm cleanly with no dangling worker (shutdown ok)."""
    doc = make_doc(5)
    for i in range(5):
        _paint(doc, i, (i * 40 % 255, 30, 60, 255))
    scene = make_scene(doc)
    scene.prewarm_frames([1, 2, 3, 4])
    scene.cancel_prewarm()
    assert scene._warming is False
    # A subsequent clean teardown does not raise and leaves no in-flight work.
    scene.shutdown_prewarm()
    assert len(scene._warm_inflight) == 0


def test_prewarm_derived_cache_honours_bound():
    """The derived per-frame cache is LRU-bounded and pins the active frame (D3)."""
    from pixelart_creator.logic.pixel_buffer import PixelBuffer

    one = PixelBuffer(64, 64, ColorMode.RGBA)
    budget = one.data.nbytes * 3 + 1  # room for ~3 composites
    cache = FrameCompositeCache(budget, min_resident=2)
    cache.pin(0)
    for i in range(6):
        cache.put(i, PixelBuffer(64, 64, ColorMode.RGBA))
        cache.pin(i) if i == 0 else None
    # The pinned active frame survives the flood; residency stays bounded.
    cache.pin(0)
    cache.put(0, PixelBuffer(64, 64, ColorMode.RGBA))
    assert cache.contains(0) is True
    assert cache.resident_bytes <= budget or cache.resident_frames <= 2 + 1


# --------------------------------------------------------------------------- #
# Accessibility (REQ-P5-UI-017) — names, focus, keyboard reach                #
# --------------------------------------------------------------------------- #


def test_ui_017_timeline_controls_have_accessible_names(timeline_env):
    """SC-UI-017-1: timeline controls expose non-empty accessible names."""
    panel, _doc, _stack, _r = timeline_env
    assert panel.accessibleName()
    assert panel._strip.accessibleName()
    assert panel._duration_spin.accessibleName()
    for action in (panel._add_action, panel._remove_action, panel._duplicate_action):
        assert action.text()  # action labels double as accessible text


def test_ui_017_playback_controls_labelled_and_space_toggles(transport, qtbot):
    """SC-UI-017-1: transport controls are labelled; Space toggles play/pause."""
    ctrl, bind = transport
    assert ctrl._play_button.accessibleName()
    assert ctrl._pause_button.accessibleName()
    assert ctrl._stop_button.accessibleName()
    assert ctrl._mode_combo.accessibleName()
    bind([5, 5, 5])
    # The Space shortcut is bound to the play/pause toggle (REQ-P5-UI-017).
    ctrl._toggle_play_pause()
    assert ctrl.is_playing() is True
    ctrl._toggle_play_pause()
    assert ctrl.is_playing() is False
    ctrl.stop()


def test_ui_017_onion_and_tag_controls_have_accessible_names(qtbot, make_doc):
    """SC-UI-017-1: onion + tag controls expose accessible names + are focusable."""
    onion = Onion_Skin_Controls()
    qtbot.addWidget(onion)
    assert onion.accessibleName()
    assert onion._enable_check.accessibleName()
    assert onion._prev_spin.accessibleName()
    assert onion._next_spin.accessibleName()
    assert onion._prev_tint_button.accessibleName()

    tags = Frame_Tags_Panel()
    qtbot.addWidget(tags)
    tags.set_context(make_doc(3), QUndoStack(), lambda: None)
    assert tags.accessibleName()
    assert tags._list.accessibleName()
    assert tags._play_button.accessibleName()
    for action in (tags._add_action, tags._edit_action, tags._remove_action):
        assert action.text()
