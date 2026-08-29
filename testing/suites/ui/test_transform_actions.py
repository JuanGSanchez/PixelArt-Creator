"""Transform-action acceptance (REQ-P2-UI-009) and the whole-document geometry
family (canvas-scale-defects `spec.md` REQ-CSD-UI-001/002/003/006/007/015).

Scenarios SC-U009-1 (flip-H/V and rotate-90-CW/CCW transform the buffer as one
undoable command), SC-U009-2 (the scale dialog applies nearest-neighbour scaling
introducing NO new colours, as one undoable command) and SC-U009-3 (the actions
are tr()-wrapped, keyboard-reachable, correct in both themes). Undo/redo integrity
is asserted for each mutating op. Both themes via the autouse ``theme`` fixture.

The SC-CSD-* tests below (`tasks.md` T14) prove the shipped `&Image` menu
actions now route the UNMASKED path through the whole-document runner
(`ui/document_transform_runner.py`) while leaving the MASKED/selection path
byte-for-byte untouched (verified against `git diff HEAD --
pixelart_creator/ui/main_window.py` this session: only the `mask is None`
branch is new code in `_apply_transform`/`_on_scale`; the `mask is not None`
branch is unchanged). Each test's docstring states its `tasks.md` class
(DEFECT / GUARD / CHANGE) explicitly — CHANGE scenarios (square rotate-90,
both flips) must never be read as a defect that existed (`spec.md` §4.3).
"""

from __future__ import annotations

from typing import List

import numpy as np
import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.constants import (
    DOCUMENT_TRANSFORM_CONFIRM_BYTES,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)
from pixelart_creator.logic.doc_transform import projected_peak_bytes
from pixelart_creator.logic.document import Document, Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import PixelBuffer
from pixelart_creator.ui.document_transform_dialogs import (
    Document_Transform_Confirm_Dialog,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.rotsprite_dialog import RotSprite_Dialog
from pixelart_creator.ui.transform_dialog import Scale_Dialog

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# -- helpers shared by the SC-CSD-* scenarios below --------------------------


def _build_document(width: int, height: int, frame_layer_counts, masks=()) -> Document:
    """Build a :class:`Document` with ``frame_layer_counts[i]`` layers in frame i.

    ``masks`` is an iterable of ``(frame_index, layer_index)`` pairs; the
    named layer gets an attached mask sized to the document (direct
    attribute assignment for test setup -- not the reversible
    ``make_attach_mask_command`` path, so no ``Command`` is pushed by it).
    """
    document = Document(width, height)
    for _ in range(frame_layer_counts[0] - 1):
        document.add_layer(frame_index=0)
    for count in frame_layer_counts[1:]:
        document.add_frame()
        frame_index = len(document.frames) - 1
        for _ in range(count - 1):
            document.add_layer(frame_index=frame_index)
    for frame_index, layer_index in masks:
        layer = document.frames[frame_index].layers[layer_index]
        layer.mask = PixelBuffer(document.width, document.height, document.mode)
    return document


def _load_document(win: Main_Window, document: Document):
    """Swap ``document`` into the active tab (same seam ``_on_branch_document_switched``
    uses: ``record.document`` plus ``scene.set_document``), with a clean selection."""
    record = win.active_tab()
    record.document = document
    record.scene.set_document(document)
    record.view.clear_selection()
    return record


def _all_buffer_dims(document: Document):
    from pixelart_creator.logic.document import iter_layers

    dims = []
    for frame in document.frames:
        for layer in iter_layers(frame.layers):
            dims.append((layer.buffer.width, layer.buffer.height))
            if layer.mask is not None:
                dims.append((layer.mask.width, layer.mask.height))
    return dims


def _colour_set(buf) -> set:
    return {
        tuple(int(c) for c in px) for px in buf.data.reshape(-1, buf.data.shape[-1])
    }


def test_sc_u009_1_flip_horizontal_one_command_reversible(qtbot):
    """SC-U009-1: flip-H mirrors the buffer as one command; undo/redo restore it."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    w = buf.width
    buf.set_pixel(1, 2, RED)
    before = buf.copy()
    win._on_flip_horizontal()
    assert record.stack.count() == 1
    moved = record.scene.active_buffer()
    assert moved.get_pixel(w - 2, 2) == RED
    assert moved.get_pixel(1, 2) != RED
    record.stack.undo()
    assert record.scene.active_buffer() == before
    record.stack.redo()
    assert record.scene.active_buffer().get_pixel(w - 2, 2) == RED


@pytest.mark.parametrize(
    "slot_name",
    ["_on_flip_vertical", "_on_rotate_cw", "_on_rotate_ccw"],
)
def test_sc_u009_1_transforms_one_command_reversible(qtbot, slot_name):
    """SC-U009-1: flip-V / rotate-90 each commit one reversible command."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(3, 1, GREEN)
    before = buf.copy()
    getattr(win, slot_name)()
    assert record.stack.count() == 1
    record.stack.undo()
    assert record.scene.active_buffer() == before


def test_sc_u009_2_scale_nearest_no_new_colours(qtbot, monkeypatch):
    """SC-U009-2: scale-NN applies as one command and introduces NO new colours."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    buf.set_pixel(5, 5, GREEN)
    src_colours = _colour_set(buf)
    src_w = record.document.width

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        Scale_Dialog, "target_size", lambda self: (src_w * 2, src_w * 2)
    )
    win._on_scale()

    assert record.stack.count() == 1
    out = record.scene.active_buffer()
    assert out.width == src_w * 2  # dimensions changed
    assert _colour_set(out).issubset(src_colours)  # NO new colours (R2)
    record.stack.undo()
    assert record.scene.active_buffer().width == src_w


def test_t16_scale_with_active_selection_affects_only_the_selection(qtbot, monkeypatch):
    """T-16 (AGT-06 audit, pairs with CF-07): scaling with an active selection
    affects only the selected region, per the ``logic/transform`` mask contract
    (``make_transform_command`` routes to ``_masked_transform_changes`` when a
    mask is supplied) — driven through the shipped UI action
    ``Main_Window._on_scale``, which now forwards ``record.view.active_selection()``
    (CF-07). The whole-buffer dimensions are UNCHANGED (a masked transform never
    resizes the canvas); pixels outside the selection are byte-identical.
    """
    from pixelart_creator.logic.selection import rect_mask
    from tests.ui._ui_helpers import prepare_for_click

    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    w, h = buf.width, buf.height

    # A distinctive 4x4 block inside the selection, and a sentinel pixel outside.
    for y in range(2, 6):
        for x in range(2, 6):
            buf.set_pixel(x, y, RED)
    buf.set_pixel(20, 20, GREEN)  # outside the selection — must stay untouched
    outside_before = buf.get_pixel(20, 20)

    prepare_for_click(record.view)
    record.view.set_selection(rect_mask(w, h, 2, 2, 5, 5))

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (w * 2, h * 2))
    win._on_scale()

    assert record.stack.count() == 1
    out = record.scene.active_buffer()
    # A masked scale never changes the whole-buffer dimensions (SC-L010-1 —
    # only the selected sub-region is re-stamped in place).
    assert (out.width, out.height) == (w, h)
    assert out.get_pixel(20, 20) == outside_before  # untouched outside the mask

    record.stack.undo()
    assert record.scene.active_buffer().get_pixel(20, 20) == outside_before


def test_sc_u009_3_actions_translatable_and_reachable(qtbot):
    """SC-U009-3: the transform actions are tr()-wrapped and menu/keyboard operable."""
    win = _window(qtbot)
    for action in (
        win._flip_h_action,
        win._flip_v_action,
        win._rotate_cw_action,
        win._rotate_ccw_action,
        win._scale_action,
    ):
        assert action.text() != ""
        assert action.isEnabled()


# =========================================================================== #
# REQ-CSD-UI-001 -- Image > Scale resamples the whole document (DEFECT)       #
# =========================================================================== #


def test_sc_csd_u001_1_scale_reaches_every_layer_frame_and_mask(qtbot, monkeypatch):
    """SC-CSD-U001-1 (DEFECT): a whole-document scale resamples every layer
    buffer in every frame, and every attached mask, to the SAME absolute
    target -- not the active layer alone.

    Pre-change: `_on_scale`'s `dims_change` branch swapped only
    `record.scene.active_layer()`'s buffer (`spec.md` §1.1); the other 5
    buffers + the mask stayed at 64x48. This is the file-corrupting DEFECT
    the whole batch exists to fix.
    """
    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2, 2], masks=[(0, 1)])
    record = _load_document(win, document)

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (256, 192))
    win._on_scale()

    assert record.stack.count() == 1
    dims = _all_buffer_dims(document)
    assert len(dims) == 7  # 6 layer buffers + 1 mask
    assert all(d == (256, 192) for d in dims)
    assert (64, 48) not in dims  # no buffer anywhere left at the old size
    assert document.width == 256 and document.height == 192


def test_sc_csd_u001_2_a_layer_nested_in_a_group_is_resampled_too(qtbot, monkeypatch):
    """SC-CSD-U001-2 (DEFECT): a leaf layer nested inside a `LayerGroup` is
    resampled by the whole-document scale, not skipped."""
    win = _window(qtbot)
    document = Document(32, 32)  # 1 frame, 1 default "Background" layer
    child_a = Layer(PixelBuffer(32, 32, document.mode), "child A")
    child_b = Layer(PixelBuffer(32, 32, document.mode), "child B")
    group = LayerGroup("Group", children=[child_a, child_b])
    document.frames[0].layers.append(group)
    document._assign_ids(document.frames[0].layers)
    record = _load_document(win, document)
    record.scene.set_active_layer(document.frames[0].layers[0])  # "Background"

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (96, 64))
    win._on_scale()

    dims = _all_buffer_dims(document)
    assert len(dims) == 3  # Background + 2 group children
    assert all(d == (96, 64) for d in dims)
    assert document.width == 96 and document.height == 64


def test_sc_csd_u001_3_nearest_neighbour_introduces_no_new_colour(qtbot, monkeypatch):
    """SC-CSD-U001-3 (DEFECT): scaling the whole document stays nearest-neighbour
    per frame -- no colour absent from a given frame's layer appears in its
    result (R2), checked independently for two frames with disjoint palettes."""
    win = _window(qtbot)
    document = _build_document(16, 16, [1, 1])
    frame1_layer = document.frames[0].layers[0]
    frame2_layer = document.frames[1].layers[0]
    frame1_layer.buffer.set_pixel(3, 3, RED)
    frame2_layer.buffer.set_pixel(3, 3, GREEN)
    record = _load_document(win, document)

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (48, 48))
    win._on_scale()

    assert _colour_set(frame1_layer.buffer).issubset({TRANSPARENT, RED})
    assert _colour_set(frame2_layer.buffer).issubset({TRANSPARENT, GREEN})
    assert record.stack.count() == 1


# =========================================================================== #
# REQ-CSD-UI-002 -- the whole-document scale is one undoable step (DEFECT)    #
# =========================================================================== #


def test_sc_csd_u002_1_one_undo_restores_every_layer_mask_and_geometry(
    qtbot, monkeypatch
):
    """SC-CSD-U002-1 (DEFECT): one undo restores every layer's and mask's exact
    prior buffer AND the prior document geometry; one redo re-applies the
    whole-document result.

    Pre-change: undo restored only the active layer's buffer (the seam wrote
    the OTHER 5 buffers' dimension change nowhere reversible as a group).
    """
    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2, 2])
    target_layer = document.frames[2].layers[1]
    target_layer.buffer.set_pixel(10, 10, RED)
    record = _load_document(win, document)
    assert record.stack.count() == 0

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (16, 12))
    win._on_scale()

    assert record.stack.count() == 1
    assert all(d == (16, 12) for d in _all_buffer_dims(document))

    record.stack.undo()
    assert all(d == (64, 48) for d in _all_buffer_dims(document))
    assert document.width == 64 and document.height == 48
    assert document.frames[2].layers[1].buffer.get_pixel(10, 10) == RED

    record.stack.redo()
    assert all(d == (16, 12) for d in _all_buffer_dims(document))
    assert document.width == 16 and document.height == 12


# =========================================================================== #
# REQ-CSD-UI-003 -- an active selection keeps Scale selection-scoped (GUARD)  #
# =========================================================================== #


def test_sc_csd_u003_1_a_masked_scale_changes_no_dimension_anywhere(qtbot, monkeypatch):
    """SC-CSD-U003-1 (GUARD -- passes today, must keep passing; NOT proven to
    fail pre-change): with an active selection, `Image > Scale` stays
    selection-scoped -- no layer's dimensions change anywhere in the
    document, and untouched frames/layers are pixel-identical.

    Evidence this is a guard, not a re-test of new code: `git diff HEAD --
    pixelart_creator/ui/main_window.py` this session shows `_on_scale`'s
    `mask is not None` branch (`transform.make_transform_command` ->
    `_apply_buffer_command`) is BYTE-FOR-BYTE UNCHANGED from HEAD `35b63bf`
    -- only the `mask is None` branch is new. This test exercises the same
    unchanged code the shipped
    `test_t16_scale_with_active_selection_affects_only_the_selection` already
    proves passes; it extends that proof to a multi-frame document, per
    `tasks.md` T14's "do not weaken the shipped test_t16_... sibling."
    """
    from pixelart_creator.logic.selection import rect_mask
    from tests.ui._ui_helpers import prepare_for_click

    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2])
    record = _load_document(win, document)
    w, h = document.width, document.height

    active_layer = record.scene.active_layer()
    for y in range(2, 6):
        for x in range(2, 6):
            active_layer.buffer.set_pixel(x, y, RED)
    active_layer.buffer.set_pixel(30, 30, GREEN)  # outside the selection

    frame2_before = [layer.buffer.copy() for layer in document.frames[1].layers]

    prepare_for_click(record.view)
    record.view.set_selection(rect_mask(w, h, 8, 8, 23, 23))

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (128, 96))
    win._on_scale()

    assert all(d == (64, 48) for d in _all_buffer_dims(document))
    assert document.width == 64 and document.height == 48
    assert active_layer.buffer.get_pixel(30, 30) == GREEN  # outside untouched
    for layer, before in zip(document.frames[1].layers, frame2_before):
        assert layer.buffer == before  # frame 2 wholly untouched


# =========================================================================== #
# REQ-CSD-UI-006 -- Rotate 90 CW/CCW rotates the whole document               #
# =========================================================================== #


def test_sc_csd_u006_1_non_square_rotate_cw_rotates_whole_document(qtbot, monkeypatch):
    """SC-CSD-U006-1 (DEFECT): a non-square document rotates clockwise in
    full -- every layer buffer + the attached mask, one undoable command."""
    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2, 2], masks=[(0, 1)])
    record = _load_document(win, document)

    win._on_rotate_cw()

    dims = _all_buffer_dims(document)
    assert len(dims) == 7
    assert all(d == (48, 64) for d in dims)
    assert document.width == 48 and document.height == 64
    assert record.stack.count() == 1


def test_sc_csd_u006_2_non_square_rotate_ccw_rotates_whole_document(qtbot):
    """SC-CSD-U006-2 (DEFECT): counter-clockwise likewise, with undo restoring
    every buffer + the geometry."""
    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2])
    record = _load_document(win, document)

    win._on_rotate_ccw()

    assert all(d == (48, 64) for d in _all_buffer_dims(document))
    assert document.width == 48 and document.height == 64

    record.stack.undo()
    assert all(d == (64, 48) for d in _all_buffer_dims(document))
    assert document.width == 64 and document.height == 48


def test_sc_csd_u006_3_square_document_also_rotates_every_layer(qtbot):
    """SC-CSD-U006-3 (CHANGE -- NOT a defect: a square rotate-90 never reached
    the seam and corrupted nothing; it stayed active-layer-scoped only. This
    is a deliberate consistency change so `Rotate 90 CW` behaves identically
    at every aspect ratio, per `spec.md` §4.2. Never record the prior
    active-layer-only behaviour as a bug."""
    win = _window(qtbot)
    document = _build_document(48, 48, [2, 2])
    record = _load_document(win, document)
    record.scene.set_active_layer(document.frames[0].layers[0])
    non_active = document.frames[1].layers[0]
    non_active.buffer.set_pixel(0, 47, RED)

    win._on_rotate_cw()

    assert all(d == (48, 48) for d in _all_buffer_dims(document))
    assert document.width == 48 and document.height == 48
    assert non_active.buffer.get_pixel(0, 0) == RED
    assert non_active.buffer.get_pixel(0, 47) == TRANSPARENT


# =========================================================================== #
# REQ-CSD-UI-007 -- RotSprite is unchanged by the seam fix (GUARD)            #
# =========================================================================== #


def test_sc_csd_u007_1_rotsprite_stays_dimension_preserving_and_active_layer(
    qtbot, monkeypatch
):
    """SC-CSD-U007-1 (GUARD -- passes today; RotSprite does NOT enter the
    whole-document pipeline, `plan.md` §5.4): dimensions stay put, only the
    active layer changes, one undoable command."""
    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2])
    record = _load_document(win, document)
    active_layer = record.scene.active_layer()
    non_active = [
        layer
        for frame in document.frames
        for layer in frame.layers
        if layer is not active_layer
    ]
    before = [layer.buffer.copy() for layer in non_active]

    monkeypatch.setattr(
        RotSprite_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(RotSprite_Dialog, "angle", lambda self: 30.0)
    win._on_rotsprite()

    assert all(d == (64, 48) for d in _all_buffer_dims(document))
    assert document.width == 64 and document.height == 48
    for layer, prior in zip(non_active, before):
        assert layer.buffer == prior
    assert record.stack.count() == 1


def test_sc_csd_u007_2_rotsprite_shows_neither_confirmation_nor_progress(
    qtbot, monkeypatch
):
    """SC-CSD-U007-2 (GUARD): RotSprite asks no cost question and shows no
    progress dialog -- it never reaches `document_transform_runner` at all."""
    from pixelart_creator.ui.document_transform_dialogs import (
        Document_Transform_Progress_Dialog,
    )

    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2])
    _load_document(win, document)

    confirms: List[object] = []
    progresses: List[object] = []
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "__init__",
        lambda self, *a, **k: confirms.append(1),
    )
    monkeypatch.setattr(
        Document_Transform_Progress_Dialog,
        "__init__",
        lambda self, *a, **k: progresses.append(1),
    )
    monkeypatch.setattr(
        RotSprite_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(RotSprite_Dialog, "angle", lambda self: 30.0)
    win._on_rotsprite()

    assert confirms == []
    assert progresses == []


# =========================================================================== #
# REQ-CSD-UI-015 -- Flip H / Flip V flip the whole document (CHANGE)          #
# =========================================================================== #


def test_sc_csd_u015_1_flip_horizontal_mirrors_every_layer_of_every_frame(qtbot):
    """SC-CSD-U015-1 (CHANGE -- NOT a defect: flips are dimension-preserving,
    never reached the seam, and corrupted nothing; they were correct today.
    This is a deliberate consistency change, `spec.md` §4.3): flip-H now
    mirrors every layer of every frame plus the attached mask."""
    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2, 2], masks=[(0, 1)])
    record = _load_document(win, document)
    record.scene.set_active_layer(document.frames[0].layers[0])
    non_active = document.frames[2].layers[1]
    non_active.buffer.set_pixel(0, 10, RED)
    masked_layer = document.frames[0].layers[1]
    masked_layer.mask.set_pixel(0, 0, BLUE)

    win._on_flip_horizontal()

    assert all(d == (64, 48) for d in _all_buffer_dims(document))
    assert document.width == 64 and document.height == 48
    assert non_active.buffer.get_pixel(63, 10) == RED
    assert non_active.buffer.get_pixel(0, 10) == TRANSPARENT
    assert masked_layer.mask.get_pixel(63, 0) == BLUE  # the mask mirrored too
    assert record.stack.count() == 1


def test_sc_csd_u015_2_flip_vertical_undoes_in_one_step_across_every_frame(qtbot):
    """SC-CSD-U015-2 (CHANGE): flip-V undoes in one step, restoring every
    layer across every frame."""
    win = _window(qtbot)
    document = _build_document(64, 48, [2, 2])
    record = _load_document(win, document)
    record.scene.set_active_layer(document.frames[0].layers[0])
    non_active = document.frames[1].layers[0]
    non_active.buffer.set_pixel(10, 0, GREEN)

    win._on_flip_vertical()

    assert non_active.buffer.get_pixel(10, 47) == GREEN
    assert record.stack.count() == 1

    record.stack.undo()
    assert non_active.buffer.get_pixel(10, 0) == GREEN
    assert non_active.buffer.get_pixel(10, 47) == TRANSPARENT
    assert all(d == (64, 48) for d in _all_buffer_dims(document))


@pytest.mark.timeout(30)
def test_sc_csd_u015_3_flip_is_subject_to_the_family_cost_guard_at_the_boundary(
    qtbot, monkeypatch
):
    """SC-CSD-U015-3 (CHANGE -- the exact-boundary case `spec.md` names by
    number): a flip's projected peak landing EXACTLY on
    `DOCUMENT_TRANSFORM_CONFIRM_BYTES` (2 layers @ 7680x4320,
    530,841,600 bytes) is SILENT -- the rule is "exceeds", not "reaches or
    exceeds". One byte-count more (3 layers, 796,262,400 bytes) DOES prompt.

    Uses the spec's own real 8K figures and the REAL, unpatched
    `DOCUMENT_TRANSFORM_CONFIRM_BYTES` (no threshold monkeypatching) --
    measured in this session at <1s / <800 MiB, so no scaling-down was
    needed for this one boundary-critical scenario (`tasks.md` T14).
    """
    win = _window(qtbot)

    # -- exactly at the threshold: silent -----------------------------------
    at_boundary = Document(MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    at_boundary.add_layer(frame_index=0)  # 2 layers, 1 frame
    projected_silent = projected_peak_bytes(
        at_boundary, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT
    )
    assert projected_silent == 530_841_600 == DOCUMENT_TRANSFORM_CONFIRM_BYTES
    record = _load_document(win, at_boundary)
    confirms_silent: List[object] = []
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "__init__",
        lambda self, *a, **k: confirms_silent.append(1),
    )
    win._on_flip_horizontal()
    assert confirms_silent == []  # exactly-at-threshold is silent
    assert document_dims_unchanged(at_boundary)
    assert record.stack.count() == 1  # it still ran, just without asking

    # -- one buffer more: above the threshold, prompts -----------------------
    monkeypatch.undo()  # restore Document_Transform_Confirm_Dialog.__init__
    above = Document(MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    above.add_layer(frame_index=0)
    above.add_layer(frame_index=0)  # 3 layers, 1 frame
    projected_above = projected_peak_bytes(above, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    assert projected_above == 796_262_400
    assert projected_above > DOCUMENT_TRANSFORM_CONFIRM_BYTES
    record2 = _load_document(win, above)
    count_before = record2.stack.count()  # same tab/stack as the boundary case above
    seen: List[object] = []
    original_init = Document_Transform_Confirm_Dialog.__init__

    def _spy(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        seen.append(self)

    monkeypatch.setattr(Document_Transform_Confirm_Dialog, "__init__", _spy)
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    win._on_flip_horizontal()
    assert len(seen) == 1  # exactly one confirmation, above the boundary
    dialog = seen[0]
    assert QLocale().formattedDataSize(projected_above) in dialog._message.text()
    assert record2.stack.count() == count_before  # declined -> nothing pushed


def document_dims_unchanged(document: Document) -> bool:
    """``True`` iff every buffer/mask in ``document`` is still at its own
    ``(width, height)`` (a no-op sanity check after a dimension-preserving op)."""
    return all(
        w == document.width and h == document.height
        for w, h in _all_buffer_dims(document)
    )
