"""Timelapse production-wiring acceptance tests (job REC-3/R-4/C-4, DEV-27).

Everything in ``tests/ui/test_timelapse_playback.py`` and
``tests/ui/test_timelapse_reopened.py`` deliberately builds a bare
``Timelapse_Controls`` (and, for the reopened module, a bare
``Timelapse_Frame_View``) to pin the WIDGET's own contract — both modules say
so explicitly in their own docstrings, and the playback module names the
canvas-level lock and the frame-view construction as gaps it reports rather
than asserts. This module is the complement: it drives the SAME production
seam (``ui/main_window.py``) that a real user actually reaches — a real
``Main_Window``, its own docked ``Timelapse_Controls`` / ``Timelapse_Frame_View``,
its own Aids-menu-toggleable docks, its own ``_undo_action``/``_redo_action`` —
so the wiring DEV-27 found dead (``frameReady``/``playbackEditLockChanged``/
``framesDropped`` with zero production consumers; ``Timelapse_Frame_View``
never constructed) is proven live end to end, not merely present on the
widget.

Covers job criterion **C-4** (REC-3/R-4):

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
``tests/ui/conftest.py``); nothing here depends on which theme is active.

## Adjudication recorded here, not encoded as a test (per dispatch instruction)

REQ-P9-UI-016 (``design-docs/specs/phase-9-timelapse-replay/spec.md:709-715``)
reads, verbatim: *"Playing steps the bound document through the recorded
positions in order, so the **active canvas shows each historical state as it
is reconstructed** (the document genuinely is at that state — §4.3)."* That is
a visual-display requirement on the active canvas during IN-SESSION playback,
separate from the read-only edit lock. AGT-05's S3 dispatch wired the lock
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
not meet this procedure's BLOCKED bar. It is reported as a real, owed
follow-up dispatch (scope: ``ui/canvas_scene.py``/``ui/canvas_view.py``, a
render-strategy question AGT-05's own report already flagged as needing
either a new display-override hook or a render/restore timing re-architecture
-- AGT-10's territory). No test below asserts canvas pixel content during
in-session playback; per this dispatch's instruction, that would encode a
known-failing expectation rather than adjudicate it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from pixelart_creator.ui.main_window import Main_Window
from tests.ui._ui_helpers import click_pixel, prepare_for_click

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
    before this fix, per DEV-27), and its dock is revealed to the user."""
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
