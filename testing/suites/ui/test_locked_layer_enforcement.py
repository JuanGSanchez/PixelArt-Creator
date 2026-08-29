"""D-05 locked-layer enforcement acceptance tests (REQ-P4-LOGIC-010, REQ-P4-UI-004).

One pytest-qt test per acceptance element of the D-05 ruling ("Forbid by default
mask edits on locked layers, check if there is an explicit path to unlock layers
if one wants to edit anyway ... implement it and test mask edits in locked and
unlocked layers through all the workflow" — the user's answer, WP-2 of
``design-docs/jobs/20260816-decision-batch``). The guard lives in
``ui/canvas_scene.py CanvasScene.is_active_editable()`` (paint path, consumed by
``ui/canvas_view.py Canvas_View.mousePressEvent``) and in
``ui/layer_panel.py Layer_Panel._on_toggle_mask()`` (attach/remove panel path);
both reject on ``node.locked`` before any command is built, so a rejection can
never push an undo entry. ``ui/main_window.py Main_Window._notify_layer_locked``
surfaces the "Layer is locked." status-bar notice via
``UI_NOTICE_DURATION_MS`` (never a literal, per the shipped
``_notify_unsupported``/``_notify_no_document`` sibling pattern).

Every test in this module also runs under **both** the light and dark theme via
the autouse ``theme`` fixture in ``conftest.py`` (parametrised automatically —
no per-test action needed), satisfying the "both themes" rule for every
UI-visible criterion.

Scope note (AGT-06): this module is UI/integration-only, mirroring
``test_layer_panel.py``'s ``layer_env`` fixture (duplicated here, not imported,
so this module stays self-contained and independently runnable for the
reversion proof in the QA report). The reversible-op maths themselves
(``document.set_layer_locked`` / ``make_attach_mask_command`` /
``make_detach_mask_command``) are AGT-04's logic-layer tests; here we assert
the *wiring*: a rejection on a locked layer touches no command, no undo entry,
and the correct signal + notice; an unlocked round-trip pushes exactly the
commands it should.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, Qt, QTranslator
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.constants import UI_NOTICE_DURATION_MS
from pixelart_creator.logic.document import Document, Layer
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.layer_panel import Layer_Panel
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import PencilTool
from tests.ui._ui_helpers import click_pixel, prepare_for_click

STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]
GREEN = (30, 190, 60, 255)
TRANSPARENT = (0, 0, 0, 0)


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                          #
# --------------------------------------------------------------------------- #


@pytest.fixture
def layer_env(qtbot, theme):
    """Factory wiring a ``Layer_Panel`` + ``CanvasScene`` + ``Canvas_View``.

    Mirrors ``Main_Window``'s per-tab wiring (the panel drives the scene's
    active layer + mask edit target and shares one ``QUndoStack``), duplicated
    from ``test_layer_panel.py`` so this module has no cross-file test
    dependency. Returns a namespace ``(doc, scene, stack, view, panel)``.
    """

    def _make(names=("Background", "Top"), width=64, height=64):
        doc = Document(width, height, mode=ColorMode.RGBA, palette=Palette(STARTER))
        doc.frames[0].layers[0].name = names[0]
        for extra in names[1:]:
            doc.add_layer(extra)
        scene = CanvasScene(doc)
        stack = QUndoStack()
        view = Canvas_View(scene, stack)
        qtbot.addWidget(view)
        prepare_for_click(view)
        view.set_tool(PencilTool())
        view.set_active_color(GREEN)
        panel = Layer_Panel()
        qtbot.addWidget(panel)

        def _on_active(node):
            if isinstance(node, Layer):
                scene.set_active_layer(node)

        panel.activeNodeChanged.connect(_on_active)
        panel.maskEditToggled.connect(scene.set_mask_edit)
        panel.set_context(
            doc,
            stack,
            scene.refresh_all,
            scene.refresh_visible,
            scene.refresh_visible_throttled,
        )
        return SimpleNamespace(
            doc=doc, scene=scene, stack=stack, view=view, panel=panel
        )

    return _make


@pytest.fixture
def win(qtbot):
    """A fresh :class:`Main_Window` (starts with one Untitled, unlocked tab)."""
    window = Main_Window()
    qtbot.addWidget(window)
    return window


def _row_for(panel: Layer_Panel, name: str):
    """Return the ``_Node_Row`` for the node named ``name``."""
    for row in panel._rows:
        if row.node().name == name:
            return row
    raise AssertionError(f"no row for layer {name!r}")


def _top_level(doc: Document):
    return doc.frames[0].layers


class _FakeTranslator(QTranslator):
    """Stand-in for a future AGT-07 catalogue entry (out of this dispatch's scope).

    D-05's ``"Layer is locked."`` string has not yet been extracted into the
    shipped ``i18n/*.ts`` catalogues; this proves the RETRANSLATION MECHANISM —
    ``self.tr()`` re-resolved against the currently installed translator at
    call time — without depending on that separate catalogue work.
    """

    def translate(self, context, source_text, disambiguation=None, n=-1):  # noqa: N802
        if source_text == "Layer is locked.":
            return "Capa bloqueada."
        return ""


# --------------------------------------------------------------------------- #
# 1. Locked layer: mask ATTACH rejected — no mask, no undo entry              #
# --------------------------------------------------------------------------- #


def test_d05_mask_attach_rejected_on_locked_layer_no_undo_entry(layer_env, qtbot):
    """REQ-P4-LOGIC-010 (D-05): mask ATTACH on a locked layer is refused — no
    mask is created, no undo entry is pushed, ``Layer_Panel.lockedLayerEditRejected``
    fires."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    env.panel._select_path((1,))
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)  # lock (1 undo entry: the lock command itself)
    assert top.locked is True
    before_count = env.stack.count()

    with qtbot.waitSignal(env.panel.lockedLayerEditRejected, timeout=1000):
        env.panel._on_toggle_mask()  # attach attempt

    assert top.mask is None
    assert env.stack.count() == before_count  # rejection pushed nothing


# --------------------------------------------------------------------------- #
# 2. Locked layer: mask REMOVE rejected — mask stays attached, no undo entry  #
# --------------------------------------------------------------------------- #


def test_d05_mask_remove_rejected_on_locked_layer_no_undo_entry(layer_env, qtbot):
    """REQ-P4-LOGIC-010 (D-05): mask REMOVE on a locked layer is refused — the
    mask stays attached, no undo entry is pushed, the signal fires."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    env.panel._select_path((1,))
    env.panel._on_toggle_mask()  # attach while unlocked (1 undo entry)
    assert top.mask is not None
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)  # lock (2nd undo entry)
    assert top.locked is True
    before_count = env.stack.count()

    with qtbot.waitSignal(env.panel.lockedLayerEditRejected, timeout=1000):
        env.panel._on_toggle_mask()  # remove attempt

    assert top.mask is not None  # still attached, not removed
    assert env.stack.count() == before_count


# --------------------------------------------------------------------------- #
# 3. Locked layer: mask EDIT (paint on an existing mask) rejected             #
# --------------------------------------------------------------------------- #


def test_d05_mask_edit_paint_rejected_on_locked_layer_no_undo_entry(layer_env, qtbot):
    """REQ-P4-LOGIC-010 (D-05): a paint attempt routed to an existing mask on a
    locked layer is refused — the mask buffer AND the layer's own pixels stay
    unchanged, no undo entry is pushed, ``Canvas_View.lockedLayerEditRejected``
    fires."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    top.buffer.fill(GREEN)
    env.scene.set_active_layer(top)
    env.panel._select_path((1,))
    env.panel._on_toggle_mask()  # attach mask while unlocked
    assert top.mask is not None
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)  # lock
    assert top.locked is True
    env.scene.set_mask_edit(True)
    assert env.scene.is_mask_edit() is True
    assert env.scene.is_active_editable() is False  # the guard under test
    mask_before = top.mask.copy()
    layer_before = top.buffer.copy()
    before_count = env.stack.count()
    env.view.set_active_color(TRANSPARENT)

    with qtbot.waitSignal(env.view.lockedLayerEditRejected, timeout=1000):
        click_pixel(env.view, 3, 3)

    assert top.mask == mask_before
    assert top.buffer == layer_before
    assert env.stack.count() == before_count


# --------------------------------------------------------------------------- #
# 4. Unlocked layer: attach/edit/remove round-trip, undo/redo intact          #
# --------------------------------------------------------------------------- #


def test_d05_unlocked_layer_mask_attach_edit_remove_round_trip(layer_env):
    """REQ-P4-LOGIC-010: on an UNLOCKED layer, mask attach/edit/remove all
    succeed — one undo entry each — and undo/redo restores every intermediate
    state exactly."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    top.buffer.fill(GREEN)
    env.scene.set_active_layer(top)
    env.panel._select_path((1,))
    assert top.locked is False

    # ATTACH
    env.panel._on_toggle_mask()
    assert top.mask is not None
    assert env.stack.count() == 1
    fill_before_edit = top.mask.get_pixel(3, 3)

    # EDIT (paint on the mask)
    env.scene.set_mask_edit(True)
    assert env.scene.is_active_editable() is True
    env.view.set_active_color(TRANSPARENT)
    click_pixel(env.view, 3, 3)
    assert top.mask.get_pixel(3, 3) == TRANSPARENT
    assert env.stack.count() == 2

    # REMOVE
    env.scene.set_mask_edit(False)
    env.panel._on_toggle_mask()
    assert top.mask is None
    assert env.stack.count() == 3

    # Undo round-trip: remove -> edit -> attach, each exactly reversed.
    env.stack.undo()  # undo REMOVE
    assert top.mask is not None
    assert top.mask.get_pixel(3, 3) == TRANSPARENT
    env.stack.undo()  # undo EDIT
    assert top.mask.get_pixel(3, 3) == fill_before_edit
    env.stack.undo()  # undo ATTACH
    assert top.mask is None

    # Redo round-trip restores the final (removed) state.
    env.stack.redo()
    env.stack.redo()
    env.stack.redo()
    assert top.mask is None


# --------------------------------------------------------------------------- #
# 5. Workflow: lock -> rejected edit -> unlock via the toggle -> edit succeeds#
# --------------------------------------------------------------------------- #


def test_d05_workflow_lock_reject_unlock_then_mask_attach_succeeds(layer_env, qtbot):
    """D-05 full workflow (REQ-P4-LOGIC-010 + REQ-P4-UI-004): a rejected mask
    attach becomes possible again the moment the SAME per-layer lock toggle
    that rejected it is switched off — no other path is needed (AGT-05's
    verdict: the toggle is never disabled by lock state, so it is reachable
    immediately from the rejection moment)."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    env.panel._select_path((1,))
    row = _row_for(env.panel, "Top")

    row._lock.setChecked(True)  # lock (1 undo entry)
    assert top.locked is True
    with qtbot.waitSignal(env.panel.lockedLayerEditRejected, timeout=1000):
        env.panel._on_toggle_mask()  # rejected
    assert top.mask is None
    assert env.stack.count() == 1  # only the lock command

    row._lock.setChecked(False)  # unlock via the SAME toggle (2nd undo entry)
    assert top.locked is False
    env.panel._on_toggle_mask()  # the SAME edit, now succeeds
    assert top.mask is not None
    assert env.stack.count() == 3  # lock + unlock + attach


def test_d05_workflow_lock_reject_unlock_then_mask_paint_succeeds(layer_env, qtbot):
    """D-05 full workflow: a mask-edit paint rejected while locked succeeds once
    the per-layer lock toggle (REQ-P4-UI-004) unlocks the layer — the same
    stroke, the same target pixel."""
    env = layer_env(names=("Background", "Top"))
    top = _top_level(env.doc)[1]
    env.scene.set_active_layer(top)
    env.panel._select_path((1,))
    env.panel._on_toggle_mask()  # attach mask while unlocked
    assert top.mask is not None
    row = _row_for(env.panel, "Top")

    row._lock.setChecked(True)  # lock
    env.scene.set_mask_edit(True)
    mask_before = top.mask.copy()
    env.view.set_active_color(TRANSPARENT)
    with qtbot.waitSignal(env.view.lockedLayerEditRejected, timeout=1000):
        click_pixel(env.view, 3, 3)
    assert top.mask == mask_before  # rejected, unchanged

    row._lock.setChecked(False)  # unlock via the SAME toggle
    click_pixel(env.view, 3, 3)  # the SAME edit, now succeeds
    assert top.mask.get_pixel(3, 3) == TRANSPARENT


# --------------------------------------------------------------------------- #
# 6. Notice: "Layer is locked." shown for UI_NOTICE_DURATION_MS (Main_Window) #
# --------------------------------------------------------------------------- #


def test_d05_notice_shows_for_ui_notice_duration_ms(win, qtbot, monkeypatch):
    """D-05: a rejected mask attach shows ``"Layer is locked."`` on the status
    bar for exactly ``UI_NOTICE_DURATION_MS`` — asserted against the shipped
    constant, never a literal (``main_window.py`` imports it from
    ``logic/constants.py``)."""
    record = win.active_tab()
    panel = win._layer_panel
    panel._select_topmost()
    leaf_name = record.document.frames[0].layers[0].name
    row = _row_for(panel, leaf_name)
    row._lock.setChecked(True)
    assert record.document.frames[0].layers[0].locked is True

    calls = []

    def _spy(text, timeout=0):
        calls.append((text, timeout))

    monkeypatch.setattr(win.statusBar(), "showMessage", _spy)

    with qtbot.waitSignal(panel.lockedLayerEditRejected, timeout=1000):
        panel._on_toggle_mask()

    assert calls, "statusBar().showMessage was never called"
    text, timeout = calls[-1]
    assert text == win.tr("Layer is locked.")
    assert timeout == UI_NOTICE_DURATION_MS


def test_d05_notice_also_fires_from_canvas_paint_rejection(win, qtbot, monkeypatch):
    """D-05: the SAME notice fires from the canvas-paint rejection path
    (``Canvas_View.lockedLayerEditRejected``), not only the panel path."""
    record = win.active_tab()
    panel = win._layer_panel
    panel._select_topmost()
    leaf_name = record.document.frames[0].layers[0].name
    row = _row_for(panel, leaf_name)
    row._lock.setChecked(True)

    calls = []
    monkeypatch.setattr(
        win.statusBar(),
        "showMessage",
        lambda text, timeout=0: calls.append((text, timeout)),
    )
    prepare_for_click(record.view)
    record.view.set_tool(PencilTool())
    record.view.set_active_color(GREEN)

    with qtbot.waitSignal(record.view.lockedLayerEditRejected, timeout=1000):
        click_pixel(record.view, 2, 2)

    assert calls, "statusBar().showMessage was never called"
    text, timeout = calls[-1]
    assert text == win.tr("Layer is locked.")
    assert timeout == UI_NOTICE_DURATION_MS


# --------------------------------------------------------------------------- #
# 7. Retranslation: the notice re-resolves tr() at call time (i18n NFR)       #
# --------------------------------------------------------------------------- #


def test_d05_notice_retranslates_on_language_change(win, qtbot):
    """i18n NFR: ``_notify_layer_locked()`` re-resolves ``tr()`` against the
    CURRENTLY installed translator at call time (no cached/stale string) — the
    same mechanism a real language switch relies on (install translator +
    ``LanguageChange`` event, F5/F6). AGT-05's report: correctly not a
    persisted-label ``changeEvent`` re-set, because this is a transient
    status-bar message generated fresh on every emission, exactly like its
    ``_notify_unsupported``/``_notify_no_document`` siblings."""
    record = win.active_tab()
    panel = win._layer_panel
    panel._select_topmost()
    leaf_name = record.document.frames[0].layers[0].name
    row = _row_for(panel, leaf_name)
    row._lock.setChecked(True)

    with qtbot.waitSignal(panel.lockedLayerEditRejected, timeout=1000):
        panel._on_toggle_mask()
    assert win.statusBar().currentMessage() == win.tr("Layer is locked.")  # English

    translator = _FakeTranslator()
    app = QApplication.instance()
    app.installTranslator(translator)
    try:
        QApplication.sendEvent(win, QEvent(QEvent.Type.LanguageChange))
        # Still locked (never unlocked) -> a second attach attempt is rejected
        # again, regenerating the notice under the now-installed translator.
        with qtbot.waitSignal(panel.lockedLayerEditRejected, timeout=1000):
            panel._on_toggle_mask()
        assert win.statusBar().currentMessage() == "Capa bloqueada."
    finally:
        app.removeTranslator(translator)


# --------------------------------------------------------------------------- #
# 8. a11y: the recovery affordance (lock toggle) stays reachable when locked  #
# --------------------------------------------------------------------------- #


def test_d05_a11y_lock_toggle_reachable_and_named_when_locked(layer_env):
    """a11y (D-05, REQ-P4-UI-004): the per-layer lock toggle — the only
    affordance a user needs to discover from the rejection moment — stays
    enabled, keyboard-reachable (non-``NoFocus`` policy) and accessibly named
    on a LOCKED layer; no new affordance was added, so this pins AGT-05's
    verdict rather than a fresh widget."""
    env = layer_env(names=("Background", "Top"))
    env.panel._select_path((1,))
    row = _row_for(env.panel, "Top")
    row._lock.setChecked(True)

    assert row._lock.isEnabled() is True
    assert row._lock.isChecked() is True
    assert row._lock.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert row._lock.accessibleName() == "Lock"
    assert row._lock.toolTip() == "Lock layer against painting"
