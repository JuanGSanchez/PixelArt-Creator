"""Timelapse production-wiring acceptance tests (job R-4/C-4).

Everything in ``testing/suites/ui/test_timelapse_playback.py`` and
``testing/suites/ui/test_timelapse_reopened.py`` deliberately builds a bare
``Timelapse_Controls`` (and, for the reopened module, a bare
``Timelapse_Frame_View``) to pin the WIDGET's own contract — both modules say
so explicitly in their own docstrings, and the playback module names the
canvas-level lock and the frame-view construction as gaps it reports rather
than asserts. This module is the complement: it drives the SAME production
seam (``ui/main_window.py``) that a real user actually reaches — a real
``Main_Window``, its own docked ``Timelapse_Controls`` / ``Timelapse_Frame_View``,
its own Aids-menu-toggleable docks, its own ``_undo_action``/``_redo_action`` —
so the wiring a prior audit found dead (``frameReady``/``playbackEditLockChanged``/
``framesDropped`` with zero production consumers; ``Timelapse_Frame_View``
never constructed) is proven live end to end, not merely present on the
widget.

Covers job criterion **C-4** (R-4):

* **(1)** a reopened, payload-carrying recording's frames reach the
  production-docked ``Timelapse_Frame_View`` (``frameReady`` consumed).
* **(2)** in-session playback engages the edit lock on the active tab's
  canvas view + the shared undo/redo actions (``playbackEditLockChanged``
  consumed) and releases it on stop; a reopened-recording review never
  engages that lock (REQ-P9-UI-024 — "it must not quietly borrow the active
  [document]").
* **(3)** ``framesDropped`` reveals the (by-default-hidden) drop-notice dock.
* **(4)** the "Reopened Recording" banner/dock title appear through the
  production path (the dock, not just the widget's own always-labelled
  banner, actually becomes visible + identifies itself).

Both themes run automatically (the autouse ``theme`` fixture in
``testing/suites/ui/conftest.py``); nothing here depends on which theme is active.

## Superseded: the REQ-P9-UI-016 display gap named below is now CLOSED

The paragraph immediately following this one is kept verbatim as the
historical record of the gap this module used to report rather than assert.
It is superseded, not deleted, per this codebase's own convention (see the
"re-keyed onto identity" note in ``test_timelapse_playback.py``): the
render-strategy directive
and the UI implementation of it (``CanvasScene._PlaybackOverlayItem`` /
``show_playback_frame`` / ``end_playback_frame``, wired from THIS module's own
``_on_timelapse_frame_ready`` / ``_on_timelapse_playback_lock_changed``) now
close it. The overlay-visible/reconstructed-content assertions live in
``testing/suites/ui/test_playback_overlay.py`` (acceptance-list items 1-4, 6);
THIS module adds the remaining wiring-integration items: reopened-session
isolation (item 5, run alongside the pre-existing banner test below so both
``is_reopened_recording()`` branches are proven mutually exclusive in the same
suite run), teardown on stop AND on a paused/scrubbed stop, and confirmation
that the pre-existing edit-lock behaviour is unaffected by the new wiring.

*Superseded text (2026-08-21):* REQ-P9-UI-016
(the phase-9-timelapse-replay spec, lines 709-715) reads,
verbatim: *"Playing steps the bound document through the recorded positions in
order, so the **active canvas shows each historical state as it is
reconstructed** (the document genuinely is at that state — §4.3)."* That is a
visual-display requirement on the active canvas during IN-SESSION playback,
separate from the read-only edit lock. A prior UI dispatch wired the lock
(``playbackEditLockChanged`` -> ``record.view.setEnabled``) but explicitly did
NOT build a mechanism for the active canvas to paint the reconstructed
historical pixels — confirmed by reading ``ui/main_window.py``:
``_on_timelapse_playback_lock_changed`` only calls ``setEnabled``; nothing in
``ui/main_window.py`` or ``ui/canvas_scene.py``/``ui/canvas_view.py`` (unchanged
this wave) feeds a historical frame into the active ``CanvasScene``'s paint
path. This is a genuine, confirmed gap against REQ-P9-UI-016's own text, not a
misreading — the requirement is unambiguous and the shipped code does not meet
it. It is NOT an S1 (8K grid) or S2 (left-click paint) criterion in this
procedure's own C2 sense, and nothing here corrupts data or misleads the
user (the document is provably byte-identical before/after, per the existing
``test_sc_ui_016_2_stack_and_document_restored_after_playback``) — so it does
not meet this procedure's BLOCKED bar. It was reported as a real, owed
follow-up dispatch (scope: ``ui/canvas_scene.py``/``ui/canvas_view.py``, a
render-strategy question a prior UI report already flagged as needing
either a new display-override hook or a render/restore timing re-architecture
-- the performance work's territory) -- and that dispatch is what closed it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)
YELLOW = (240, 220, 40, 255)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _record_three_real_frames(qtbot, win):
    """Record 3 genuinely distinct edits on ``win``'s own active tab + controls.

    Drives the PRODUCTION seam only: ``win.active_tab()`` (created by
    ``Main_Window.__init__``'s own ``new_document()`` call) and
    ``win._timelapse_controls`` (bound to that tab by ``Main_Window``'s own
    ``_bind_visual_aids_to_active`` — never rebuilt or rebound by the test).
    """
    record = win.active_tab()
    prepare_for_click(record.view)
    win._timelapse_controls._record_button.setChecked(True)

    record.view.set_active_color(RED)
    click_pixel(record.view, 5, 5)
    record.view.set_active_color(GREEN)
    click_pixel(record.view, 20, 20)
    record.view.set_active_color(BLUE)
    click_pixel(record.view, 40, 40)

    assert win._timelapse_controls.frame_count() == 3
    win._timelapse_controls._record_button.setChecked(False)  # recording concluded
    return record


def _save_current_session(qtbot, monkeypatch, win, tmp_path, name="clip"):
    """Save ``win``'s currently-recorded session via the real Save… path."""
    saved_path = tmp_path / name
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(saved_path), "")),
    )
    win._timelapse_controls._save_button.click()  # the real _on_save path
    return saved_path.with_suffix(".pixtimelapse")


def _load_into(monkeypatch, controls, path) -> None:
    """Open ``path`` into ``controls`` via the real Load… path (not a setter)."""
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )
    controls._load_button.click()


# --------------------------------------------------------------------------- #
# (2) in-session playback engages the edit lock through main_window wiring    #
# --------------------------------------------------------------------------- #


def test_c4_in_session_playback_locks_active_canvas_and_undo_redo(
    qtbot, tmp_path, monkeypatch
):
    """C-4/REQ-P9-UI-016: in-session play disables the active canvas + undo/redo,
    and both are re-enabled once playback stops -- through the real
    ``playbackEditLockChanged`` -> ``_on_timelapse_playback_lock_changed`` wiring
    ``Main_Window`` installs itself (not a directly-invoked private handler)."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)

    assert record.view.isEnabled() is True
    assert win._undo_action.isEnabled() is True  # 3 commands are undoable
    assert win._playback_locked is False

    # Observer connected BEFORE the triggering action.
    with qtbot.waitSignal(
        win._timelapse_controls.playbackEditLockChanged, timeout=2000
    ) as blocker:
        win._timelapse_controls._play_button.setChecked(True)
    assert blocker.args == [True]

    assert win._playback_locked is True
    assert record.view.isEnabled() is False  # no drawing, no tool commit
    assert win._undo_action.isEnabled() is False  # no undo
    assert win._redo_action.isEnabled() is False  # no redo

    win._timelapse_controls._stop_button.click()

    assert win._playback_locked is False
    assert record.view.isEnabled() is True
    assert win._undo_action.isEnabled() is True  # restored


def test_c4_reopened_recording_review_never_locks_the_active_document(
    qtbot, tmp_path, monkeypatch
):
    """REQ-P9-UI-024: reviewing a reopened recording "must not quietly borrow
    the active one" -- the active tab's canvas + undo/redo stay untouched
    throughout, and ``playbackEditLockChanged`` is never emitted at all."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)
    saved = _save_current_session(qtbot, monkeypatch, win, tmp_path)

    # Observer connected BEFORE the triggering action -- proves NON-emission.
    lock_events = []
    win._timelapse_controls.playbackEditLockChanged.connect(lock_events.append)

    _load_into(monkeypatch, win._timelapse_controls, saved)
    assert win._timelapse_controls.is_reopened_recording() is True

    view_enabled_before = record.view.isEnabled()
    undo_enabled_before = win._undo_action.isEnabled()
    assert view_enabled_before is True
    assert undo_enabled_before is True  # the 3 in-session commands are still there

    received = []
    win._timelapse_controls.frameReady.connect(lambda arr: received.append(arr))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)

    assert record.view.isEnabled() is True  # never disabled
    assert win._undo_action.isEnabled() is True  # never disabled
    assert win._playback_locked is False

    win._timelapse_controls._stop_button.click()
    assert lock_events == []  # the emitter never fired for a reopened review


# --------------------------------------------------------------------------- #
# (3) framesDropped reveals the drop-notice dock via production wiring       #
# --------------------------------------------------------------------------- #


def test_c4_dropped_frames_reveal_the_timelapse_dock(qtbot, tmp_path, monkeypatch):
    """REQ-P9-UI-021: a discarded branch's dropped-frame notice must actually
    reach the user -- the by-default-hidden timelapse dock is revealed by
    the real ``framesDropped`` -> ``_on_timelapse_frames_dropped`` wiring."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)
    # ``isHidden()``, not ``isVisible()``: ``win`` itself is never ``.show()``-n
    # in this headless suite, so ``isVisible()`` (which needs the WHOLE ancestor
    # chain shown) would read False regardless of what the dock's own ``.show()``
    # call did -- ``isHidden()`` reflects the widget's OWN explicit shown/hidden
    # state, which is what the production wiring actually controls (matches the
    # established convention in ``test_aids_a11y.py``/``test_guides_rulers.py``).
    assert win._timelapse_dock.isHidden() is True  # starts hidden

    record.stack.undo()  # position now behind the 3rd (most recent) recorded frame

    with qtbot.waitSignal(
        win._timelapse_controls.framesDropped, timeout=2000
    ) as blocker:
        record.view.set_active_color(YELLOW)
        click_pixel(record.view, 60, 60)  # discards the undone (3rd) command
    assert blocker.args == [1]

    assert win._timelapse_dock.isHidden() is False  # revealed by the production wiring
    assert (
        "1" in win._timelapse_controls._reason_label.text()
    )  # widget's own text, not duplicated


# --------------------------------------------------------------------------- #
# (1) + (4) reopened-recording frames + banner via the production dock       #
# --------------------------------------------------------------------------- #


def test_c4_reopened_recording_frames_reach_the_production_docked_frame_view(
    qtbot, tmp_path, monkeypatch
):
    """C-4/REQ-P9-UI-024: a saved, payload-carrying recording's frames reach
    ``Main_Window``'s OWN docked ``Timelapse_Frame_View`` (never constructed
    before this fix), and its dock is revealed to the user."""
    win1 = _window(qtbot)
    _record_three_real_frames(qtbot, win1)
    saved = _save_current_session(qtbot, monkeypatch, win1, tmp_path)

    # A FRESH Main_Window -- models a restarted application (same convention
    # as the shipped test_timelapse_reopened.py "restart" modelling).
    win2 = _window(qtbot)
    assert win2._timelapse_frame_view_dock.isHidden() is True  # starts hidden

    _load_into(monkeypatch, win2._timelapse_controls, saved)
    assert win2._timelapse_controls.is_reopened_recording() is True

    with qtbot.waitSignal(win2._timelapse_controls.frameReady, timeout=2000):
        win2._timelapse_controls._play_button.setChecked(True)

    assert win2._timelapse_frame_view_dock.isHidden() is False
    assert win2._timelapse_frame_view._last_pixmap is not None  # frameReady consumed

    win2._timelapse_controls._stop_button.click()


def test_c4_reopened_recording_banner_identifies_itself_through_production_dock(
    qtbot, tmp_path, monkeypatch
):
    """C-4/DEP-12f: the "Reopened Recording" identity is reachable through the
    real dock ``Main_Window`` builds -- not just present on a standalone
    widget nobody ever shows."""
    win1 = _window(qtbot)
    _record_three_real_frames(qtbot, win1)
    saved = _save_current_session(qtbot, monkeypatch, win1, tmp_path, name="clip2")

    win2 = _window(qtbot)
    _load_into(monkeypatch, win2._timelapse_controls, saved)

    with qtbot.waitSignal(win2._timelapse_controls.frameReady, timeout=2000):
        win2._timelapse_controls._play_button.setChecked(True)
    win2._timelapse_controls._stop_button.click()

    assert win2._timelapse_frame_view_dock.isHidden() is False
    assert win2._timelapse_frame_view_dock.windowTitle() == win2.tr(
        "Reopened Recording"
    )
    banner = win2._timelapse_frame_view._banner.text().lower()
    assert "reopened" in banner
    assert "not" in banner  # "...this is not your current document"


# --------------------------------------------------------------------------- #
# Acceptance-list item 5 -- reopened review never shows the in-session       #
# overlay; run in the SAME suite as the banner test directly above.          #
# --------------------------------------------------------------------------- #


def test_ui016_reopened_session_never_shows_the_in_session_playback_overlay(
    qtbot, tmp_path, monkeypatch
):
    """REQ-P9-UI-016/-024, acceptance item 5: reviewing a reopened
    (payload-carrying) recording must NEVER construct/show the in-session
    canvas overlay on any open tab -- only ``Timelapse_Frame_View`` serves
    it. This runs in the SAME suite as
    ``test_c4_reopened_recording_banner_identifies_itself_through_production_dock``
    directly above (both in this module) and the in-session overlay
    assertions in ``testing/suites/ui/test_playback_overlay.py``, proving the two
    ``is_reopened_recording()`` branches stay mutually exclusive after the
    overlay change -- not merely each true in isolation.
    """
    win1 = _window(qtbot)
    _record_three_real_frames(qtbot, win1)
    saved = _save_current_session(qtbot, monkeypatch, win1, tmp_path, name="clip3")

    win2 = _window(qtbot)
    record2 = win2.active_tab()
    assert record2 is not None
    assert record2.scene._playback_overlay.isVisible() is False

    _load_into(monkeypatch, win2._timelapse_controls, saved)
    assert win2._timelapse_controls.is_reopened_recording() is True

    received = []
    win2._timelapse_controls.frameReady.connect(lambda arr: received.append(arr))
    win2._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)

    # The reopened frames reached Timelapse_Frame_View, never the active
    # tab's canvas overlay -- no overlay call happened for this path.
    assert record2.scene._playback_overlay.isVisible() is False
    assert win2._timelapse_frame_view._last_pixmap is not None  # frameReady consumed

    win2._timelapse_controls._stop_button.click()
    assert record2.scene._playback_overlay.isVisible() is False


# --------------------------------------------------------------------------- #
# Teardown on stop AND on a paused/scrubbed stop                              #
# --------------------------------------------------------------------------- #


def test_ui016_teardown_hides_overlay_on_stop_and_after_pause_scrub_stop(
    qtbot,
):
    """Acceptance list / task instruction 'stop AND scrub-end': the
    overlay teardown (``record.scene.end_playback_frame()``, driven by
    ``playbackEditLockChanged(False)``) fires identically whether Stop is
    clicked while actively ticking, or after the transport was paused and
    the user scrubbed (the seek slider) to a different recorded frame first.

    Adjudication on 'scrub-end': ``Timelapse_Controls`` has no SEPARATE
    scrub-end signal -- ``_on_seek`` only emits ``frameReady`` (see
    ``test_sc_ui_017_1_seek_shows_frame_k_and_leaves_session_unchanged`` in
    ``test_timelapse_playback.py``, which pauses then seeks then calls
    ``_on_stop()`` directly, the same shape used here). Teardown is the SAME
    ``_on_stop()``/``playbackEditLockChanged(False)`` path in both contexts;
    this test proves both invocation contexts -- stop while ticking, and stop
    after a pause+scrub -- reach it and hide the overlay.
    """
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)

    # -- context 1: stop while actively ticking ---------------------------
    received = []
    win._timelapse_controls.frameReady.connect(lambda arr: received.append(arr))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 1, timeout=5000)
    assert record.scene._playback_overlay.isVisible() is True

    win._timelapse_controls._stop_button.click()
    assert record.scene._playback_overlay.isVisible() is False
    assert record.view.isEnabled() is True

    # -- context 2: pause immediately (no tick fired yet, same shape as
    # test_sc_ui_017_1_seek_shows_frame_k_and_leaves_session_unchanged), then
    # scrub (seek) -- which is what actually shows a frame here -- then stop.
    win._timelapse_controls._play_button.setChecked(True)  # re-renders (Given: stopped)
    win._timelapse_controls._pause_playback()  # paused before any timer tick fires
    assert record.scene._playback_overlay.isVisible() is False  # nothing shown yet

    win._timelapse_controls._seek_slider.setValue(1)  # scrub to frame index 1
    assert record.scene._playback_overlay.isVisible() is True  # scrub shows a frame

    win._timelapse_controls._on_stop()
    assert record.scene._playback_overlay.isVisible() is False
    assert record.view.isEnabled() is True


# --------------------------------------------------------------------------- #
# Edit-lock engagement is unchanged by the overlay wiring                    #
# --------------------------------------------------------------------------- #


def test_ui016_edit_lock_engagement_unchanged_with_overlay_wired(qtbot):
    """Acceptance list / task instruction 'edit lock engagement
    unchanged': the pre-existing REQ-P9-UI-016 lock behaviour (view/undo/redo
    disabled while playing, restored on stop) is unaffected by wiring the
    overlay into the SAME two handlers -- same shape as
    ``test_c4_in_session_playback_locks_active_canvas_and_undo_redo`` above,
    extended to also assert the overlay toggles alongside the lock."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)

    assert record.view.isEnabled() is True
    assert win._undo_action.isEnabled() is True
    assert win._playback_locked is False
    assert record.scene._playback_overlay.isVisible() is False

    with qtbot.waitSignal(
        win._timelapse_controls.playbackEditLockChanged, timeout=2000
    ) as blocker:
        win._timelapse_controls._play_button.setChecked(True)
    assert blocker.args == [True]

    assert win._playback_locked is True
    assert record.view.isEnabled() is False  # no drawing, no tool commit
    assert win._undo_action.isEnabled() is False  # no undo
    assert win._redo_action.isEnabled() is False  # no redo
    qtbot.waitUntil(
        lambda: record.scene._playback_overlay.isVisible() is True, timeout=5000
    )

    win._timelapse_controls._stop_button.click()

    assert win._playback_locked is False
    assert record.view.isEnabled() is True
    assert win._undo_action.isEnabled() is True
    assert record.scene._playback_overlay.isVisible() is False


# --------------------------------------------------------------------------- #
# Tab-close teardown fix (Main_Window._on_tab_changed's ``record is         #
# None`` branch now calls ``bind_undo_stack(None)``) -- permanent regression #
# encoding of this suite's own ephemeral probe (a), Scenario A + Scenario B  #
# (recorded in the QA dispatch report for this finding).                    #
# --------------------------------------------------------------------------- #


def test_tabclose_a_only_tab_playing_stops_timer_and_releases_lock_same_turn(
    qtbot,
):
    """Tab-close fix: closing the ONLY open tab while its in-session timelapse
    playback is active stops the ``Timelapse_Controls`` ``QTimer`` and
    releases ``_playback_locked`` in the SAME event-loop turn that
    ``close_document(...)`` returns -- no ``qtbot.wait``/``processEvents``
    self-heal call appears anywhere between the close and the assertions
    below. Before the fix, ``Main_Window._on_tab_changed``'s ``record is
    None`` early return skipped ``_bind_visual_aids_to_active()`` entirely,
    so ``Timelapse_Controls.bind_undo_stack`` (and its unconditional
    ``_on_stop()`` safety net) was never reached and the timer/lock leaked
    until a new document was opened or Stop was clicked manually. Encodes
    this suite's own probe (a), Scenario A."""
    win = _window(qtbot)
    _record_three_real_frames(qtbot, win)
    assert len(win._tabs_data) == 1  # the only tab -- Scenario A's precondition

    # Observer connected BEFORE the triggering action.
    with qtbot.waitSignal(
        win._timelapse_controls.playbackEditLockChanged, timeout=2000
    ) as blocker:
        win._timelapse_controls._play_button.setChecked(True)
    assert blocker.args == [True]

    assert win._playback_locked is True
    assert win._timelapse_controls._timer.isActive() is True

    win.close_document(0)  # the only open tab, closed while playing

    # Observable state immediately after close_document(...) returns -- no
    # event-loop turn was allowed to pass between the close and this assert.
    assert win._playback_locked is False
    assert win._timelapse_controls._timer.isActive() is False


def test_tabclose_b_closing_non_last_tab_stays_regression_pinned(qtbot):
    """Regression pin: closing a NON-last tab (a next tab remains) while ITS
    playback is active must keep behaving exactly as it did before the
    tab-close fix -- the pre-existing rebind path
    (``_on_tab_changed`` -> ``_bind_visual_aids_to_active`` ->
    ``Timelapse_Controls.bind_undo_stack`` -> unconditional ``_on_stop()``)
    fires synchronously inside ``removeTab``'s own ``currentChanged``, so the
    timer stops and the lock releases immediately, same-turn, exactly as
    Scenario B in this suite's probe (a) showed against the UNFIXED code. The
    fix touches only the ``record is None`` branch, never this path, so this
    test's outcome is unaffected by the fix either way (see the reversion
    proof, where this test PASSES both before and after)."""
    win = _window(qtbot)
    _record_three_real_frames(qtbot, win)
    win.new_document()  # a second tab -- now 2 tabs open, not the last-tab case
    assert len(win._tabs_data) == 2

    win._tab_widget.setCurrentIndex(0)
    assert win.active_tab() is win._tabs_data[0]

    with qtbot.waitSignal(
        win._timelapse_controls.playbackEditLockChanged, timeout=2000
    ) as blocker:
        win._timelapse_controls._play_button.setChecked(True)
    assert blocker.args == [True]

    assert win._playback_locked is True
    assert win._timelapse_controls._timer.isActive() is True

    win.close_document(0)  # close the ACTIVE (playing) tab; tab 1 remains

    assert len(win._tabs_data) == 1
    assert win._playback_locked is False
    assert win._timelapse_controls._timer.isActive() is False
