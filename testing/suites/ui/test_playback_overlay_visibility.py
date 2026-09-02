"""Playback-overlay visibility acceptance tests (user ruling, 2026-08-22):

"those overlays must be hidden while playback runs, and shown when it's not",
extended the same day to "every inert edit-affordance overlay ... hidden while
playback runs and restored to its exact prior state when it is not" and
audited by the UI layer.

Verifies the UI implementation in ``pixelart_creator/ui/canvas_scene.py``
(``_OverlayVisibilitySnapshot`` / ``_hide_edit_affordance_overlays`` /
``_restore_edit_affordance_overlays``, wired into the existing
``show_playback_frame`` / ``end_playback_frame`` entry points) against BOTH
halves of the ruling:

* the FIVE covered items -- line-tool preview (Z 1.0), shape/lasso preview
  (Z 1.5), the floating-move preview pair (Z 1.70/1.75), the selection
  marquee (Z 2.0) -- are hidden while playback runs and restored to their
  EXACT prior state on stop (never an unconditional show);
* the FOUR items the user ruling deliberately EXCLUDES -- guides/rulers
  (Z 3.5), isometric grid (Z 4.0), perspective grid (Z 4.0), live
  collaborator cursors (Z 9.0) -- stay visible across a full playback cycle
  when they were visible before it, because they are a persistent spatial
  reference or genuinely live content, not a transient edit affordance
  (dispatch table, user ruling 2026-08-22). These are regression guards: a
  later pass extending the mechanism "for consistency" must not silently
  overturn this deliberate exclusion.

Real-surface policy: every covered-item state is driven through the actual
production entry points a user's gesture reaches --
``pixelart_creator.ui.tools.{line,rectangle,rect_select_tool}`` via
``testing/suites/ui/_ui_helpers.press``/``move`` (mirrors ``test_selection_overlay.py``
and ``test_playback_overlay.py``'s own conventions) -- and the playback
mechanism itself is driven through ``CanvasScene.show_playback_frame`` /
``end_playback_frame``, the exact two methods ``main_window.py`` calls from
the real ``Timelapse_Controls`` signal wiring (unchanged by this ruling, per
the report). Only the four EXCLUDED overlays -- which ``CanvasScene``
holds no reference to at all (the audit table) -- are attached to the
scene directly with their own real public constructors/``setVisible`` (the
same calls ``canvas_view.py``/``main_window.py`` make), since no tool
interaction reaches them. Assertions read ``isVisible()`` on named
``CanvasScene``-owned attributes (``_preview_item``, ``_shape_preview``,
``_float_item``, ``_origin_item``, ``_selection_overlay``) -- the same
attribute names the UI implementation's own report and ``test_playback_overlay.py`` /
``test_selection_overlay.py`` already couple to; this is disclosed as
attribute-coupling, not a private implementation detail invented for this
module, in the accompanying subagent report.

Both themes: the autouse ``theme`` fixture (``testing/suites/ui/conftest.py``)
already runs every test in this module twice (light/dark). No assertion here
is colour/theme-dependent -- the whole mechanism is a boolean
``setVisible()`` toggle untouched by theme/palette -- so no additional
parametrization is added; stated once here rather than per test.

Coverage map (dispatch item -> test(s)):

* covered items, hidden + exact-prior-state restore -> the
  ``test_covered_*`` group;
* "not a blanket show" regression guard -> ``test_covered_float_pair_...``
  and ``test_covered_line_preview_absent_...`` /
  ``test_covered_shape_preview_absent_...``;
* the four exclusions -> the ``test_excluded_*`` group;
* edge case 1 (mid-interaction at playback start) -> the ``test_covered_*``
  drag-in-progress variants (line/shape/float);
* edge case 2 (state changing during playback) ->
  ``test_edgecase_state_changing_during_playback_is_ignored_by_restore``;
* edge case 3 (teardown route, commit 37bd0ff) ->
  ``test_edgecase_last_tab_close_teardown_does_restore`` -- a REGRESSION GUARD
  for the fix landed after this module's first pass (the UI layer routed
  ``end_playback_frame()`` through the existing teardown before
  ``bind_undo_stack(None)``); see its docstring for the finding's history and
  the fix that closed it;
* edge case 4 (never played) ->
  ``test_covered_restore_is_noop_when_playback_never_ran``;
* scene-instance scoping -> ``test_scoping_snapshot_never_leaks_across_scenes``.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF

from pixelart_creator.logic.grids import (
    IsoGridConfig,
    PerspectiveConfig,
    VanishingPoint,
)
from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay
from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay
from pixelart_creator.ui.live_cursors_overlay import Live_Cursors_Overlay
from pixelart_creator.ui.perspective_grid_overlay import Perspective_Grid_Overlay
from pixelart_creator.ui.tools import LineTool, RectangleTool, RectSelectTool
from testing.suites.ui._ui_helpers import click_pixel, move, prepare_for_click, press

RED = (230, 30, 30, 255)


def _frame(w: int, h: int) -> np.ndarray:
    """A zero-filled RGBA frame of document size -- content is immaterial here."""
    return np.zeros((h, w, 4), dtype=np.uint8)


# --------------------------------------------------------------------------- #
# covered items -- hidden during playback, restored to EXACT prior state     #
# --------------------------------------------------------------------------- #


def test_covered_line_preview_hidden_then_restored_visible_mid_drag(make_view):
    """Line-tool preview (Z 1.0): a drag in progress WHEN PLAYBACK STARTS
    (edge case 1, mid-interaction) is hidden for the span and restored to
    visible on stop -- the least-surprising reading the UI implementation's own docstring
    states, since editing is locked for the whole span so the drag cannot
    advance while hidden."""
    view, scene, _stack = make_view(16, 16)
    view.set_tool(LineTool())
    press(view, 1, 1)
    move(view, 5, 5)  # drag in progress, never released
    assert scene._preview_item is not None
    assert scene._preview_item.isVisible() is True

    scene.show_playback_frame(_frame(16, 16))
    assert scene._preview_item.isVisible() is False

    scene.end_playback_frame()
    assert scene._preview_item.isVisible() is True  # exact prior state, not a no-op


def test_covered_line_preview_absent_stays_absent_not_forced_into_existence(make_view):
    """No line drag active (``_preview_item`` is ``None``, not merely hidden): a
    full playback cycle must not conjure the item into existence -- proof
    against a blanket 'show every overlay' bug for an item whose natural
    off-state is non-existence rather than a boolean."""
    view, scene, _stack = make_view(16, 16)
    assert scene._preview_item is None

    scene.show_playback_frame(_frame(16, 16))
    assert scene._preview_item is None
    scene.end_playback_frame()
    assert scene._preview_item is None


def test_covered_shape_preview_hidden_then_restored_visible_mid_drag(make_view):
    """Shape/lasso preview (Z 1.5, extended 2026-08-22 -- 'same defect class'):
    a rectangle drag in progress when playback starts is hidden for the span
    and restored to visible on stop (edge case 1)."""
    view, scene, _stack = make_view(16, 16)
    view.set_tool(RectangleTool())
    press(view, 2, 2)
    move(view, 8, 8)  # drag in progress, never released
    assert scene._shape_preview is not None
    assert scene._shape_preview.isVisible() is True

    scene.show_playback_frame(_frame(16, 16))
    assert scene._shape_preview.isVisible() is False

    scene.end_playback_frame()
    assert scene._shape_preview.isVisible() is True


def test_covered_shape_preview_absent_stays_absent_not_forced_into_existence(make_view):
    """No shape drag active (``_shape_preview`` is ``None``): a full playback
    cycle must not conjure the item into existence."""
    view, scene, _stack = make_view(16, 16)
    assert scene._shape_preview is None

    scene.show_playback_frame(_frame(16, 16))
    assert scene._shape_preview is None
    scene.end_playback_frame()
    assert scene._shape_preview is None


def test_covered_float_pair_hidden_then_restored_visible_mid_drag(make_view):
    """Floating-move preview pair (``_float_item`` Z 1.75, ``_origin_item``
    Z 1.70): a MOVE drag in progress when playback starts (edge case 1) is
    hidden for the span and restored to visible on stop."""
    view, scene, stack = make_view(16, 16)
    buf = scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    view.set_tool(RectSelectTool())
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    press(view, 3, 3)  # press inside the selection -> lifts a floating move
    move(view, 5, 3)  # drag in progress, never released
    assert scene._float_item.isVisible() is True
    assert scene._origin_item.isVisible() is True

    scene.show_playback_frame(_frame(16, 16))
    assert scene._float_item.isVisible() is False
    assert scene._origin_item.isVisible() is False

    scene.end_playback_frame()
    assert scene._float_item.isVisible() is True
    assert scene._origin_item.isVisible() is True
    assert stack.count() == 0  # still uncommitted -- playback never touches the stack


def test_covered_float_pair_not_active_stays_hidden_not_forced_visible(make_view):
    """THE critical 'not a blanket show' regression guard named by the
    dispatch: with NO floating move active, ``_float_item``/``_origin_item``
    are already ``False`` (their natural, constructed-hidden default) BEFORE
    playback. A buggy unconditional-show-on-stop implementation would flip
    them to ``True`` regardless; the correct restore must leave them
    ``False``, exactly as they were."""
    view, scene, _stack = make_view(16, 16)
    assert scene._float_item.isVisible() is False
    assert scene._origin_item.isVisible() is False

    scene.show_playback_frame(_frame(16, 16))
    assert scene._float_item.isVisible() is False
    assert scene._origin_item.isVisible() is False

    scene.end_playback_frame()
    # The regression this guards against: a blanket "show every overlay on
    # stop" would set these True here. They must stay False.
    assert scene._float_item.isVisible() is False
    assert scene._origin_item.isVisible() is False


def test_covered_selection_marquee_hidden_during_playback_then_restored(make_view):
    """Selection marquee (Z 2.0): with an active (non-empty) selection the
    overlay is hidden while playback runs and restored to visible on stop.

    Disclosure: ``_SelectionOverlayItem`` never calls ``setVisible(False)``
    anywhere in production except this playback mechanism itself -- an empty
    selection merely leaves its edge list empty, so it stays ``isVisible() ==
    True`` at all times through the public API. This item therefore has no
    naturally-occurring ``False`` prior state to prove the 'not a blanket
    show' guarantee against; that proof lives in
    ``test_covered_float_pair_not_active_stays_hidden_not_forced_visible``
    above, which does have a genuine ``False`` natural state. This test still
    pins the hide/restore cycle for the marquee's own (always-``True``)
    prior state."""
    view, scene, _stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    view.set_selection(rect_mask(16, 16, 2, 2, 6, 6))
    assert scene._selection_overlay.isVisible() is True

    scene.show_playback_frame(_frame(16, 16))
    assert scene._selection_overlay.isVisible() is False

    scene.end_playback_frame()
    assert scene._selection_overlay.isVisible() is True


def test_covered_restore_is_noop_when_playback_never_ran(make_view):
    """Edge case 4: playback never having run -- ``end_playback_frame`` must
    be a no-op, never an unconditional show, on a scene whose overlays were
    never touched."""
    view, scene, _stack = make_view(16, 16)
    assert scene._pre_playback_overlay_visibility is None
    assert scene._selection_overlay.isVisible() is True  # its own natural default
    assert scene._float_item.isVisible() is False
    assert scene._origin_item.isVisible() is False
    assert scene._preview_item is None
    assert scene._shape_preview is None

    scene.end_playback_frame()  # never preceded by show_playback_frame

    assert scene._pre_playback_overlay_visibility is None  # still nothing held
    assert scene._selection_overlay.isVisible() is True  # unchanged
    assert scene._float_item.isVisible() is False  # unchanged, not forced True
    assert scene._origin_item.isVisible() is False  # unchanged, not forced True
    assert scene._preview_item is None  # not conjured into existence
    assert scene._shape_preview is None  # not conjured into existence


# --------------------------------------------------------------------------- #
# edge case 2 -- state changing during playback is ignored by restore        #
# --------------------------------------------------------------------------- #


def test_edgecase_state_changing_during_playback_is_ignored_by_restore(make_view):
    """A documented (defensive) claim: 'the restore path reapplies the
    captured pre-playback booleans verbatim, ignoring anything that happened
    in between.' Nothing in the production UI can legitimately change these
    overlays while the edit lock is held, so this test drives the CanvasScene
    API directly (bypassing the view-level lock main_window.py applies) to
    exercise that defensive path for real, per the UI implementation's own disclosure that
    it is 'a defensive statement of intent rather than an observed path.'

    Sequence: nothing active -> playback starts (captures False/False,
    hides -- a no-op) -> a floating move is lifted WHILE playback is running
    (state changes mid-span) -> a second playback tick arrives (must not
    re-capture, per the hidden->shown transition guard) -> playback stops.
    The restore must revert to the ORIGINALLY captured ``False``, discarding
    the mid-span ``True`` -- not merely leave whatever was true right before
    the stop.
    """
    view, scene, _stack = make_view(16, 16)
    buf = scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    view.set_tool(RectSelectTool())
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    assert scene._float_item.isVisible() is False
    assert scene._origin_item.isVisible() is False

    scene.show_playback_frame(_frame(16, 16))  # captures (False, False)
    assert scene._pre_playback_overlay_visibility.float_preview is False
    assert scene._pre_playback_overlay_visibility.origin_preview is False

    # State changes WHILE playback is running (bypassing the view-level lock).
    press(view, 3, 3)
    move(view, 5, 3)
    assert scene._float_item.isVisible() is True
    assert scene._origin_item.isVisible() is True

    # A second tick: the playback overlay is already visible, so the
    # hidden->shown transition guard must skip re-capture/re-hide.
    scene.show_playback_frame(_frame(16, 16))
    assert scene._float_item.isVisible() is True  # untouched by the second tick
    assert scene._origin_item.isVisible() is True

    scene.end_playback_frame()
    # Restore reverts to the ORIGINALLY captured False -- discarding the
    # mid-playback True, not merely leaving it.
    assert scene._float_item.isVisible() is False
    assert scene._origin_item.isVisible() is False


# --------------------------------------------------------------------------- #
# edge case 3 -- the last-tab-close teardown route (commit 37bd0ff)          #
# --------------------------------------------------------------------------- #


def _window(qtbot):
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _record_three_real_frames(qtbot, win):
    """Mirrors ``test_playback_overlay.py``'s helper of the same name."""
    record = win.active_tab()
    prepare_for_click(record.view)
    win._timelapse_controls._record_button.setChecked(True)
    record.view.set_active_color(RED)
    click_pixel(record.view, 5, 5)
    record.view.set_active_color((30, 190, 60, 255))
    click_pixel(record.view, 20, 20)
    record.view.set_active_color((40, 90, 220, 255))
    click_pixel(record.view, 40, 40)
    assert win._timelapse_controls.frame_count() == 3
    win._timelapse_controls._record_button.setChecked(False)
    return record


def test_edgecase_last_tab_close_teardown_does_restore(qtbot):
    """Edge case 3, driven through the REAL ``Main_Window`` + ``Timelapse_Controls``
    production seam (the only edge case that needs it -- the teardown routing
    itself lives in ``main_window.py``, not ``canvas_scene.py``).

    REGRESSION GUARD -- history of the finding, kept rather than erased:

    This test originally FAILED against the implementation as it stood when
    this module was first written, and was deliberately kept failing rather
    than xfail/skip (HARD RULE), because it was a real, evidenced finding:

    ``Main_Window.close_document`` popped the tab from ``_tabs_data`` and
    THEN called ``removeTab``, whose ``currentChanged`` reached
    ``_on_tab_changed``'s ``record is None`` branch (no tab left) ->
    ``Timelapse_Controls.bind_undo_stack(None)`` -> ``_on_stop()`` ->
    ``playbackEditLockChanged.emit(False)`` ->
    ``Main_Window._on_timelapse_playback_lock_changed(False)``, which itself
    called ``self.active_tab()`` -- and by that point ``_tabs_data`` was
    already empty, so ``active_tab()`` returned ``None`` and
    ``record.scene.end_playback_frame()`` was **never called** on the
    closing scene. Confirmed empirically at the time (probe script,
    discarded per the temp-hygiene policy): after ``close_document(0)`` on
    the only, playing tab, the closed scene's
    ``_pre_playback_overlay_visibility`` snapshot was STILL HELD (not
    ``None``) and ``_selection_overlay.isVisible()`` was still ``False`` --
    i.e. NOT restored to its pre-playback ``True`` -- even though the
    general ruling states every covered item is 'restored to its exact
    prior state when [playback] stops', with no stated exception for this
    route.

    The UI implementation's own report traced
    this exact chain and disclosed it explicitly at the time, arguing it was
    moot because the scene is discarded immediately after and nothing can
    observe its overlays again. That argument was a PRODUCT judgement, not a
    test result, and the scene object was in fact still live (still
    referenced by this test's own ``record``) at the moment the assertion
    ran, so the literal 'restored to exact prior state when it stops'
    guarantee did not hold on this route as stated.

    THE FIX: the UI layer subsequently routed ``end_playback_frame()`` through the
    existing teardown BEFORE ``bind_undo_stack(None)`` runs, so the closing
    scene's overlays are restored before ``_tabs_data`` goes empty. This test
    now PASSES and has become the regression guard for that fix: it must
    stay in the suite, unweakened, so a future refactor of the close/teardown
    ordering cannot silently reopen this exact leak without a red test."""
    win = _window(qtbot)
    record = win.active_tab()
    record.view.set_selection(
        rect_mask(record.document.width, record.document.height, 2, 2, 6, 6)
    )
    assert record.scene._selection_overlay.isVisible() is True
    _record_three_real_frames(qtbot, win)

    received = []
    win._timelapse_controls.frameReady.connect(lambda a: received.append(a))
    win._timelapse_controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 1, timeout=5000)
    assert record.scene._selection_overlay.isVisible() is False  # hidden while playing

    assert len(win._tabs_data) == 1  # the only tab
    win.close_document(0)  # the last-tab-close teardown route (37bd0ff)

    # The stated general guarantee: restored to its exact prior state (True)
    # once playback stops, on ANY route that stops it. This assertion FAILED
    # before the teardown-ordering fix (see docstring above) and is the
    # regression guard for it now that it passes.
    assert record.scene._selection_overlay.isVisible() is True
    assert record.scene._pre_playback_overlay_visibility is None


# --------------------------------------------------------------------------- #
# the four DELIBERATE exclusions -- regression guards for the user ruling    #
# --------------------------------------------------------------------------- #


def test_excluded_guides_rulers_stay_visible_across_playback_cycle(make_view):
    """Guides/rulers overlay (Z 3.5): user ruling 2026-08-22 -- a persistent
    spatial reference the user deliberately switched on, NOT a transient edit
    affordance. Must stay visible across a full playback cycle. This is a
    regression guard: extending the hide/restore mechanism to this item
    'for consistency' would silently overturn the user's deliberate
    exclusion."""
    view, scene, _stack = make_view(16, 16)
    controller = Guides_Rulers_Overlay(view, scene, QRectF(0, 0, 16, 16))
    controller.set_enabled(True)
    overlay = controller.overlay_item()
    assert overlay.isVisible() is True

    scene.show_playback_frame(_frame(16, 16))
    assert overlay.isVisible() is True  # unaffected by playback starting

    scene.end_playback_frame()
    assert overlay.isVisible() is True  # unaffected by playback stopping


def test_excluded_isometric_grid_stays_visible_across_playback_cycle(make_view):
    """Isometric-grid overlay (Z 4.0): user ruling 2026-08-22 -- same
    persistent-spatial-reference reasoning as guides/rulers. Regression
    guard against silent extension of the hide/restore mechanism."""
    view, scene, _stack = make_view(16, 16)
    overlay = Iso_Grid_Overlay(QRectF(0, 0, 16, 16), IsoGridConfig())
    scene.addItem(overlay)
    overlay.setVisible(True)
    assert overlay.isVisible() is True

    scene.show_playback_frame(_frame(16, 16))
    assert overlay.isVisible() is True

    scene.end_playback_frame()
    assert overlay.isVisible() is True


def test_excluded_perspective_grid_stays_visible_across_playback_cycle(make_view):
    """Perspective-grid overlay (Z 4.0): user ruling 2026-08-22 -- same
    persistent-spatial-reference reasoning. Regression guard against silent
    extension of the hide/restore mechanism."""
    view, scene, _stack = make_view(16, 16)
    cfg = PerspectiveConfig(
        mode=1,
        vanishing_points=(VanishingPoint(position=(8.0, 8.0)),),
        horizon_y=8.0,
    )
    overlay = Perspective_Grid_Overlay(QRectF(0, 0, 16, 16), cfg)
    scene.addItem(overlay)
    overlay.setVisible(True)
    assert overlay.isVisible() is True

    scene.show_playback_frame(_frame(16, 16))
    assert overlay.isVisible() is True

    scene.end_playback_frame()
    assert overlay.isVisible() is True


def test_excluded_live_collaborator_cursors_stay_visible_across_playback_cycle(
    make_view,
):
    """Live collaborator cursors (Z 9.0): user ruling 2026-08-22 -- genuinely
    live content reporting what OTHER users are doing right now, independent
    of local playback, not a transient local edit affordance. Regression
    guard against silent extension of the hide/restore mechanism."""
    view, scene, _stack = make_view(16, 16)
    overlay = Live_Cursors_Overlay(QRectF(0, 0, 16, 16))
    scene.addItem(overlay)
    overlay.set_cursor("alice", 4, 4)
    overlay.setVisible(True)
    assert overlay.isVisible() is True
    assert overlay.cursor_count() == 1

    scene.show_playback_frame(_frame(16, 16))
    assert overlay.isVisible() is True  # a collaborator's live cursor keeps showing

    scene.end_playback_frame()
    assert overlay.isVisible() is True
    assert overlay.cursor_count() == 1  # untouched throughout


# --------------------------------------------------------------------------- #
# scene-instance scoping -- the snapshot must not leak across scenes         #
# --------------------------------------------------------------------------- #


def test_scoping_snapshot_never_leaks_across_scenes(make_scene):
    """Two independent scenes; playback on ONE must never touch the other's
    edit-affordance overlays or its snapshot state."""
    scene_a = make_scene(16, 16)
    scene_b = make_scene(16, 16)
    scene_b.set_selection_mask(rect_mask(16, 16, 2, 2, 6, 6))
    assert scene_b._selection_overlay.isVisible() is True
    assert scene_a._pre_playback_overlay_visibility is None
    assert scene_b._pre_playback_overlay_visibility is None

    scene_a.show_playback_frame(_frame(16, 16))
    assert scene_a._pre_playback_overlay_visibility is not None
    # scene_b is completely untouched -- no leak of the snapshot or the hide.
    assert scene_b._pre_playback_overlay_visibility is None
    assert scene_b._selection_overlay.isVisible() is True

    scene_a.end_playback_frame()
    assert scene_a._pre_playback_overlay_visibility is None
    assert scene_b._pre_playback_overlay_visibility is None
    assert scene_b._selection_overlay.isVisible() is True
