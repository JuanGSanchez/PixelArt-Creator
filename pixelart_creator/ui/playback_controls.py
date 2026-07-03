"""Playback controls — transport + mode selector + QTimer (REQ-P5-UI-008..010).

``Playback_Controls`` offers **play / pause / stop** transport and a **global
playback-mode selector** (loop / once / ping-pong / reverse, default loop —
REQ-P5-UI-009). The playback wall-clock is a :class:`QTimer` **owned here in
``ui/``** (Article I / CL-14): each tick advances the displayed frame, and the
next tick is armed with that frame's own ``duration_ms`` so a 500 ms frame lingers
five times as long as a 100 ms frame (REQ-P5-UI-010). The frame *sequence* itself
is the pure, Qt-free :func:`~pixelart_creator.logic.animation.playback_steps` /
:func:`~pixelart_creator.logic.animation.tag_playback_steps` iterator — this widget
holds **no** sequencing maths (Article I / S11).

- **Play** starts (or resumes) advancing over the current range/mode.
- **Pause** freezes on the current frame (the iterator is retained; play resumes).
- **Stop** halts and returns to the frame that was active when playback started
  (REQ-P5-UI-008).
- **Play tag** runs a named animation over the tag's range under the tag's own
  mode/repeat (REQ-P5-UI-014), independently of the global mode.

Selection / scrub / playback are **not** undoable (CL-13); this widget pushes no
command. It drives the display through injected callbacks (set-frame,
durations-provider) so it never reaches into the document tree. Onion skinning is
suppressed while playing (:data:`playbackActiveChanged`, CL-11).

All strings are ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (REQ-P5-UI-019); controls carry accessible names
and are keyboard-reachable — space toggles play/pause (REQ-P5-UI-017).
"""

from __future__ import annotations

from typing import Callable, Iterator, List, Optional, Tuple

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QToolButton,
    QWidget,
)

from pixelart_creator.logic.animation import (
    DEFAULT_PLAYBACK_MODE,
    FrameTag,
    PlaybackMode,
    playback_steps,
    tag_playback_steps,
)

#: Type of the per-tick step yielded by the sequencing engine: (index, ms).
_Step = Tuple[int, int]


class Playback_Controls(QWidget):
    """Play/pause/stop transport + mode selector owning the playback timer."""

    #: Emitted with the frame index to display on each playback tick (scrub-like).
    frameAdvanced = Signal(int)
    #: Emitted ``True`` when playback becomes active, ``False`` when it halts.
    #: The shell suppresses onion skinning while active (CL-11).
    playbackActiveChanged = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the transport buttons, mode selector and playback timer."""
        super().__init__(parent)
        self._durations_provider: Optional[Callable[[], List[int]]] = None
        self._current_frame_provider: Optional[Callable[[], int]] = None
        self._steps: Optional[Iterator[_Step]] = None
        self._playing = False
        self._paused = False
        self._start_frame = 0
        # Off-thread pre-warm hooks (D1/D2): ``_frame_ready_provider(index)`` says
        # whether a frame can be shown without a GUI-thread flatten, and
        # ``_warm_request(order)`` kicks the scene's off-thread warm for the range.
        # When a tick reaches a cold frame the transport WAITS (arms no timer) and
        # resumes from :meth:`notify_frame_ready` — the flatten never blocks the GUI.
        self._frame_ready_provider: Optional[Callable[[int], bool]] = None
        self._warm_request: Optional[Callable[[List[int]], None]] = None
        self._awaiting_index: Optional[int] = None
        self._awaiting_duration = 0
        self._warm_order: List[int] = []

        from PySide6.QtCore import QTimer

        # The sole new Qt timing surface (CL-14); single-shot, re-armed per frame
        # with that frame's authoritative duration_ms (REQ-P5-UI-010).
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

        self._play_button = QToolButton(self)
        self._play_button.clicked.connect(self.play)
        self._pause_button = QToolButton(self)
        self._pause_button.clicked.connect(self.pause)
        self._stop_button = QToolButton(self)
        self._stop_button.clicked.connect(self.stop)

        self._mode_combo = QComboBox(self)
        for mode in PlaybackMode:  # iterate the vocabulary — never a hard count.
            self._mode_combo.addItem(self.mode_label(mode), mode)
        default_idx = self._mode_combo.findData(DEFAULT_PLAYBACK_MODE)
        if default_idx >= 0:
            self._mode_combo.setCurrentIndex(default_idx)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._play_button)
        layout.addWidget(self._pause_button)
        layout.addWidget(self._stop_button)
        layout.addWidget(self._mode_combo, 1)

        # Space = play/pause (REQ-P5-UI-017); scoped to this widget's window.
        self._space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self._space_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._space_shortcut.activated.connect(self._toggle_play_pause)

        self._retranslate()
        self._update_buttons()

    # -- context ----------------------------------------------------------

    def set_context(
        self,
        durations_provider: Callable[[], List[int]],
        current_frame_provider: Callable[[], int],
    ) -> None:
        """Bind the transport to the active document's timing + frame state.

        ``durations_provider`` returns the active document's per-frame
        ``duration_ms`` list (authoritative timing, REQ-P5-UI-010);
        ``current_frame_provider`` returns the currently displayed frame index (so
        Stop can restore it). Called on document open and every tab switch; a
        switch stops any active playback first.
        """
        self.stop()
        self._durations_provider = durations_provider
        self._current_frame_provider = current_frame_provider
        self._update_buttons()

    def set_prewarm_context(
        self,
        frame_ready_provider: Callable[[int], bool],
        warm_request: Callable[[List[int]], None],
    ) -> None:
        """Bind the transport to the active scene's off-thread warm (D1/D2).

        ``frame_ready_provider(index)`` returns whether a frame can be shown
        immediately (a cache hit / non-compositing doc) or needs an off-thread
        warm; ``warm_request(order)`` starts warming the given frames in visitation
        order. Rebound on every tab switch (each tab owns its own scene / cache).
        """
        self._frame_ready_provider = frame_ready_provider
        self._warm_request = warm_request

    def selected_mode(self) -> PlaybackMode:
        """Return the currently selected global :class:`PlaybackMode`."""
        data = self._mode_combo.currentData()
        return data if isinstance(data, PlaybackMode) else DEFAULT_PLAYBACK_MODE

    # -- transport --------------------------------------------------------

    def play(self) -> None:
        """Start (or resume) global playback over the whole document range.

        Kicks an off-thread pre-warm of the range's cold frames first (D1) so the
        cold-frame flatten never runs on the GUI thread; playback streams as frames
        become ready (D2).
        """
        if self._durations_provider is None:
            return
        if self._paused and self._steps is not None:
            # Resume from where a pause froze the iterator.
            self._paused = False
            self._playing = True
            self.playbackActiveChanged.emit(True)
            self._update_buttons()
            self._request_warm()
            self._resume_after_gap()
            return
        durations = self._durations_provider()
        if not durations:
            return
        self._start_frame = self._current_frame()
        self._steps = playback_steps(durations, self.selected_mode())
        self._warm_order = self._compute_order(
            playback_steps(durations, self.selected_mode()), len(durations)
        )
        self._request_warm()
        self._begin()

    def play_tag(self, tag: FrameTag) -> None:
        """Play a named animation over ``tag``'s range/mode/repeat (REQ-P5-UI-014)."""
        if self._durations_provider is None:
            return
        durations = self._durations_provider()
        if not durations:
            return
        self._start_frame = self._current_frame()
        self._steps = tag_playback_steps(tag, durations)
        self._warm_order = self._compute_order(
            tag_playback_steps(tag, durations), len(durations)
        )
        self._request_warm()
        self._begin()

    def pause(self) -> None:
        """Freeze on the current frame; retain the iterator so play resumes."""
        if not self._playing:
            return
        self._timer.stop()
        self._playing = False
        self._paused = True
        self.playbackActiveChanged.emit(False)
        self._update_buttons()

    def stop(self) -> None:
        """Halt and return to the frame active when playback started (UI-008)."""
        was_active = self._playing or self._paused
        self._timer.stop()
        self._steps = None
        self._playing = False
        self._paused = False
        self._awaiting_index = None
        if was_active:
            self.playbackActiveChanged.emit(False)
            self.frameAdvanced.emit(self._start_frame)
        self._update_buttons()

    def is_playing(self) -> bool:
        """Return whether playback is actively advancing (not paused/stopped)."""
        return self._playing

    # -- internal ---------------------------------------------------------

    def _begin(self) -> None:
        self._paused = False
        self._playing = True
        self.playbackActiveChanged.emit(True)
        self._update_buttons()
        self._advance()

    def _advance(self) -> None:
        """Show the next sequenced frame and arm the timer for its duration.

        On a **cold** frame (not yet warm, D1/D2) the transport does not arm the
        timer: it records the awaited frame, emits :data:`frameAdvanced` (so the
        scene warms it off-thread and holds the display) and returns. It resumes
        from :meth:`notify_frame_ready` when the streamed result arrives — the
        ~20 s flatten never blocks the GUI thread.
        """
        if self._steps is None:
            return
        try:
            index, duration_ms = next(self._steps)
        except StopIteration:
            # A non-looping run (ONCE) completed: halt on the last frame shown
            # (an explicit Stop is what returns to the start frame, UI-008).
            self._timer.stop()
            self._steps = None
            self._playing = False
            self._paused = False
            self._awaiting_index = None
            self.playbackActiveChanged.emit(False)
            self._update_buttons()
            return
        duration = max(1, int(duration_ms))
        if self._frame_ready_provider is not None and not self._frame_ready_provider(
            index
        ):
            self._awaiting_index = index
            self._awaiting_duration = duration
            self.frameAdvanced.emit(index)
            return
        self._awaiting_index = None
        self.frameAdvanced.emit(index)
        self._timer.start(duration)

    def notify_frame_ready(self, index: int) -> None:
        """Resume a stream that was waiting on ``index`` becoming warm (D2).

        Called by the shell when the scene streams a warmed frame in. A no-op
        unless playback is active and waiting on exactly this frame.
        """
        if not self._playing or self._awaiting_index != index:
            return
        duration = self._awaiting_duration
        self._awaiting_index = None
        self.frameAdvanced.emit(index)
        self._timer.start(duration)

    def _resume_after_gap(self) -> None:
        """Resume advancing after a pause, re-gating a frame we were waiting on."""
        if self._awaiting_index is None:
            self._advance()
            return
        index = self._awaiting_index
        if self._frame_ready_provider is not None and not self._frame_ready_provider(
            index
        ):
            # Still cold: keep waiting; re-warm the frame in case the pause dropped it.
            self.frameAdvanced.emit(index)
            return
        duration = self._awaiting_duration
        self._awaiting_index = None
        self.frameAdvanced.emit(index)
        self._timer.start(duration)

    def _request_warm(self) -> None:
        """Ask the scene to warm the current playback order off-thread (D1/D2)."""
        if self._warm_request is not None:
            self._warm_request(list(self._warm_order))

    @staticmethod
    def _compute_order(steps: Iterator[_Step], frame_count: int) -> List[int]:
        """Return the unique frame indices in first-visit order (warm priority).

        A single bounded pass over the sequence iterator, deduped, so the earliest
        frames playback will show are warmed first. Bounded by ``frame_count`` (a
        ping-pong visits at most one full sweep before repeating).
        """
        if frame_count <= 0:
            return []
        order: List[int] = []
        seen: set = set()
        limit = 2 * frame_count + 2
        for _ in range(limit):
            try:
                index, _duration = next(steps)
            except StopIteration:
                break
            if index not in seen:
                seen.add(index)
                order.append(index)
            if len(order) >= frame_count:
                break
        return order

    def _current_frame(self) -> int:
        if self._current_frame_provider is not None:
            return self._current_frame_provider()
        return 0

    def _toggle_play_pause(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def _update_buttons(self) -> None:
        bound = self._durations_provider is not None
        self._play_button.setEnabled(bound and not self._playing)
        self._pause_button.setEnabled(self._playing)
        self._stop_button.setEnabled(self._playing or self._paused)
        self._mode_combo.setEnabled(bound)

    # -- i18n / a11y ------------------------------------------------------

    def mode_label(self, mode: PlaybackMode) -> str:
        """Return the translatable label for a playback mode (REQ-P5-UI-009)."""
        labels = {
            PlaybackMode.LOOP: self.tr("Loop"),
            PlaybackMode.ONCE: self.tr("Once"),
            PlaybackMode.PING_PONG: self.tr("Ping-Pong"),
            PlaybackMode.REVERSE: self.tr("Reverse"),
        }
        return labels.get(mode, mode.value)

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Playback controls"))
        self._play_button.setText(self.tr("Play"))
        self._play_button.setToolTip(self.tr("Play (Space)"))
        self._play_button.setAccessibleName(self.tr("Play"))
        self._pause_button.setText(self.tr("Pause"))
        self._pause_button.setToolTip(self.tr("Pause (Space)"))
        self._pause_button.setAccessibleName(self.tr("Pause"))
        self._stop_button.setText(self.tr("Stop"))
        self._stop_button.setToolTip(self.tr("Stop and return to the start frame"))
        self._stop_button.setAccessibleName(self.tr("Stop"))
        self._mode_combo.setAccessibleName(self.tr("Playback mode"))
        self._mode_combo.setToolTip(self.tr("Global playback mode"))
        for i in range(self._mode_combo.count()):
            mode = self._mode_combo.itemData(i)
            if isinstance(mode, PlaybackMode):
                self._mode_combo.setItemText(i, self.mode_label(mode))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the transport labels on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
