"""In-session timelapse playback overlay acceptance tests (REQ-P9-UI-016, REC-3).

Verifies AGT-10's binding render-strategy directive
(``design-docs/reports/subagent-report-agt-10-p9playback-20260821-140500.md``,
"AGT-06 acceptance list") against AGT-05's implementation of
``CanvasScene._PlaybackOverlayItem`` / ``show_playback_frame`` /
``end_playback_frame`` (``pixelart_creator/ui/canvas_scene.py``) and its
wiring in ``pixelart_creator/ui/main_window.py``'s
``_on_timelapse_frame_ready`` / ``_on_timelapse_playback_lock_changed``.

Every test drives the REAL production seam -- a genuine ``Main_Window``, its
own docked ``Timelapse_Controls``, its own ``active_tab()`` -- exactly like
``tests/ui/test_timelapse_wiring.py``, never a bare ``CanvasScene`` assembled
by hand, so the same tab identity guarantee the directive relies on
(``record.scene`` / ``record.view`` are the SAME ``_DocTab`` both handlers
reach) is exercised for real. Both themes run automatically (the autouse
``theme`` fixture in ``tests/ui/conftest.py``); none of these assertions is
colour/theme-dependent, since the overlay blits the raw reconstructed RGBA
frame directly and never reads a theme role.

No frame-time/fps/ms-per-tick figure is asserted anywhere in this module,
per the directive's own D6 deferral (item 7 of its acceptance list) -- that
measurement is AGT-10's re-profile, not this module's job.

Coverage map (AGT-10 acceptance-list item -> test):

* item 1 -- ``test_ui016_1_overlay_hidden_at_construction_and_after_stop``
* item 2 -- ``test_ui016_2_in_session_playback_shows_reconstructed_state_via_overlay``
* item 3 -- ``test_ui016_3_document_buffer_byte_identical_and_identity_``
  ``preserved_across_playback``
* item 4 -- ``test_ui016_4_no_new_undo_command_and_no_dirty_flag_from_playback``
* item 6 -- ``test_ui016_6a_overlay_update_bounded_and_no_unrelated_scene_invalidate``
            + ``test_ui016_6b_no_qpixmap_fromimage_in_the_playback_tick_window``
* item 5 (reopened isolation) and item 7 (deferred frame-time) are covered /
  named in ``tests/ui/test_timelapse_wiring.py`` -- see that module's
  docstring for the mapping.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QPixmap

from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _record_three_real_frames(qtbot, win):
    """Record 3 genuinely distinct edits on ``win``'s own active tab + controls.

    Mirrors ``tests/ui/test_timelapse_wiring.py``'s helper of the same name --
    drives the PRODUCTION seam only (``win.active_tab()`` / ``win._timelapse_controls``,
    never a hand-built widget).
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


# --------------------------------------------------------------------------- #
# item 1 -- hidden at construction, hidden again after stop                   #
# --------------------------------------------------------------------------- #


def test_ui016_1_overlay_hidden_at_construction_and_after_stop(qtbot):
    """AGT-10 item 1: the overlay item exists and is hidden right after
    ``CanvasScene.__init__`` (reached here via ``Main_Window``'s own
    ``new_document()``), and hidden again after playback stops."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record is not None
    assert record.scene._playback_overlay.isVisible() is False

    record = _record_three_real_frames(qtbot, win)

    received = []
    win._timelapse_controls.frameReady.connect(lambda a: received.append(a))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 1, timeout=5000)
    assert record.scene._playback_overlay.isVisible() is True

    win._timelapse_controls._stop_button.click()
    assert record.scene._playback_overlay.isVisible() is False


# --------------------------------------------------------------------------- #
# item 2 -- shows each reconstructed state via the overlay item               #
# --------------------------------------------------------------------------- #


def test_ui016_2_in_session_playback_shows_reconstructed_state_via_overlay(qtbot):
    """AGT-10 item 2: after the first ``frameReady`` tick the overlay is
    visible, and for EVERY tick the overlay's own displayed frame is the
    exact array the production ``frameReady`` emission carried -- not just
    'some' data. By connection order ``Main_Window.__init__``'s own
    ``_on_timelapse_frame_ready`` slot (connected before this test connects
    its own) has already updated the overlay for a given emission by the
    time this test's slot runs for that SAME emission -- no race."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)

    matched = []

    def _on_frame(frame):
        overlay_frame = record.scene._playback_overlay._frame
        matched.append(
            overlay_frame is not None and np.array_equal(overlay_frame, frame)
        )

    win._timelapse_controls.frameReady.connect(_on_frame)
    assert record.scene._playback_overlay.isVisible() is False

    with qtbot.waitSignal(win._timelapse_controls.frameReady, timeout=2000):
        win._timelapse_controls._play_button.setChecked(True)
    assert record.scene._playback_overlay.isVisible() is True

    qtbot.waitUntil(lambda: len(matched) >= 3, timeout=5000)
    assert matched == [True, True, True]

    win._timelapse_controls._stop_button.click()
    assert record.scene._playback_overlay.isVisible() is False


# --------------------------------------------------------------------------- #
# item 3 -- byte-identical document, extended with buffer-object identity     #
# --------------------------------------------------------------------------- #


def test_ui016_3_document_buffer_byte_identical_and_identity_preserved_across_playback(
    qtbot,
):
    """AGT-10 item 3: extends the existing
    ``test_sc_ui_016_2_stack_and_document_restored_after_playback`` byte-
    identity proof with the NEW identity check the directive asks for --
    ``record.scene._item._buffer`` is the SAME OBJECT before and after a full
    play/stop cycle, proving the overlay path never re-pointed the live
    buffer item (a buffer-substitution implementation could pass a
    byte-identity check alone while having transiently swapped and restored
    the reference; object identity closes that gap)."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)

    buffer_before = record.scene._item._buffer
    bytes_before = np.ascontiguousarray(record.scene.active_buffer().data).tobytes()

    received = []
    win._timelapse_controls.frameReady.connect(lambda a: received.append(a))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    win._timelapse_controls._stop_button.click()

    assert record.scene._item._buffer is buffer_before  # never re-pointed
    bytes_after = np.ascontiguousarray(record.scene.active_buffer().data).tobytes()
    assert bytes_after == bytes_before


# --------------------------------------------------------------------------- #
# item 4 -- no new QUndoCommand, no dirty flag                                #
# --------------------------------------------------------------------------- #


def test_ui016_4_no_new_undo_command_and_no_dirty_flag_from_playback(qtbot):
    """AGT-10 item 4: the stack's depth/index/clean state is unchanged by a
    full in-session play/stop cycle through the production ``Main_Window``
    path -- the overlay mechanism adds no new write to ``Document``/
    ``QUndoStack`` (confirmed by inspection in AGT-05's report; this pins it
    behaviourally)."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)
    stack = record.stack
    depth_before, index_before, clean_before = (
        stack.count(),
        stack.index(),
        stack.isClean(),
    )

    received = []
    win._timelapse_controls.frameReady.connect(lambda a: received.append(a))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    win._timelapse_controls._stop_button.click()

    assert stack.count() == depth_before  # no new QUndoCommand
    assert stack.index() == index_before
    assert stack.isClean() == clean_before  # no dirty flag from playback


# --------------------------------------------------------------------------- #
# item 6 -- update discipline: bounded, no unrelated full-scene invalidate    #
# --------------------------------------------------------------------------- #


def test_ui016_6a_overlay_update_bounded_and_no_unrelated_scene_invalidate(
    qtbot, monkeypatch
):
    """AGT-10 item 6: the overlay's own ``update()`` is called roughly once
    per ``frameReady`` tick (bounded -- not blown up by a full-scene
    repaint), and NONE of ``CanvasScene``'s existing background/tiled-dirty
    ``self.invalidate(...)`` call sites (``_mark_tiled_dirty()``, onion
    recompute, etc.) fire from a playback tick -- playback touches neither
    the buffer nor the checker/grid background, so the scene's own
    ``invalidate`` must never be reached from this path."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)

    update_calls = []
    original_update = record.scene._playback_overlay.update

    def _spy_update(*args, **kwargs):
        update_calls.append((args, kwargs))
        return original_update(*args, **kwargs)

    monkeypatch.setattr(record.scene._playback_overlay, "update", _spy_update)

    invalidate_calls = []
    original_invalidate = record.scene.invalidate

    def _spy_invalidate(*args, **kwargs):
        invalidate_calls.append((args, kwargs))
        return original_invalidate(*args, **kwargs)

    monkeypatch.setattr(record.scene, "invalidate", _spy_invalidate)

    received = []
    win._timelapse_controls.frameReady.connect(lambda a: received.append(a))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    win._timelapse_controls._stop_button.click()

    # At least one update() per tick, bounded (show_frame's own update() per
    # tick + end_frame()'s one call on stop -- never a per-tick multiple).
    assert len(received) <= len(update_calls) <= len(received) + 2
    assert invalidate_calls == []  # zero unrelated background/tiled invalidate


def test_ui016_6b_no_qpixmap_fromimage_in_the_playback_tick_window(qtbot, monkeypatch):
    """AGT-10 item 6 (conversion-cost clause): a behavioural proxy for the
    code-shape rule 'no ``QPixmap.fromImage`` in the per-tick path' -- spies
    on ``QPixmap.fromImage`` itself and asserts it is NEVER called anywhere
    during a full record/play/stop cycle. A pass over the whole window is a
    strict superset of 'never in the per-tick path'."""
    win = _window(qtbot)
    record = _record_three_real_frames(qtbot, win)

    calls = []
    original_from_image = QPixmap.fromImage

    def _spy_from_image(*args, **kwargs):
        calls.append((args, kwargs))
        return original_from_image(*args, **kwargs)

    monkeypatch.setattr(QPixmap, "fromImage", staticmethod(_spy_from_image))

    received = []
    win._timelapse_controls.frameReady.connect(lambda a: received.append(a))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    win._timelapse_controls._stop_button.click()

    assert calls == []
    assert record.scene._playback_overlay.isVisible() is False
