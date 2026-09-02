"""Tests for pixelart_creator.logic.edit_trace (REQ-P10-UI-025).

The three contract tests this module owes were named explicitly in commit
50e8e75 ("test(logic): pass explicit edit targets in every PixelEdit
construction") as outstanding: ``PixelEdit(buffer, changes)`` without
``target`` raising ``TypeError``; ``EditTarget(frame_index=0, layer_id=0)``
raising ``EditTraceError``; and an ``EditTarget``-carrying edit on
``frame_index >= 1`` with a layer track absent from frame 0 yielding
``RasterTrace`` s naming that frame and track. Zero Qt.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.edit_trace import EditTarget, EditTraceError, RasterTrace
from pixelart_creator.logic.history import PixelEdit

RED = (255, 0, 0, 255)
TRANSPARENT = (0, 0, 0, 0)


class TestEditTargetIsRequired:
    """(a) ``target`` is a required keyword with no default (plan §8.2):
    a missing value is a construction-time ``TypeError``, never a silently
    wrong record (frame 0 / unminted layer)."""

    def test_omitting_target_raises_type_error(self):
        buf = Document(2, 2).frames[0].layers[0].buffer
        with pytest.raises(TypeError):
            PixelEdit(buf, [(0, 0, TRANSPARENT, RED)])


class TestEditTargetValidation:
    """(b) ``EditTarget`` refuses the unminted-layer sentinel and a negative
    frame index, and refuses a ``bool`` for either field (``bool`` is an
    ``int`` subclass in Python -- an accepted ``True`` would silently become
    ``1``, a plausible-looking but wrong id/index)."""

    def test_layer_id_zero_is_the_unminted_sentinel_and_is_rejected(self):
        with pytest.raises(EditTraceError):
            EditTarget(frame_index=0, layer_id=0)

    def test_negative_frame_index_is_rejected(self):
        with pytest.raises(EditTraceError):
            EditTarget(frame_index=-1, layer_id=1)

    def test_negative_layer_id_is_rejected(self):
        with pytest.raises(EditTraceError):
            EditTarget(frame_index=0, layer_id=-1)

    def test_bool_frame_index_is_rejected(self):
        with pytest.raises(EditTraceError):
            EditTarget(frame_index=True, layer_id=1)

    def test_bool_layer_id_is_rejected(self):
        with pytest.raises(EditTraceError):
            EditTarget(frame_index=0, layer_id=True)


class TestRealTargetAttributesTheTraceToItsOwnFrame:
    def test_edit_on_frame_ge_1_with_a_track_absent_from_frame_0(self):
        """(c) The slice-wide fixture rule and the reversion proof.

        ``doc.add_frame()`` mints a *fresh* stable layer id for its own
        layer (``document.py``'s ``_next_layer_id`` counter) -- it does not
        reuse frame 0's track -- so this fixture's frame-1 layer id is, by
        construction, a track that does not exist in frame 0. Editing that
        buffer with a real ``EditTarget(frame_index=1, layer_id=<that id>)``
        must produce a ``RasterTrace`` naming frame 1 and that id.

        This is deliberately NOT tested on frame 0: on frame 0, a
        correctly-threaded implementation (real target flows through) and a
        defaulted/half-threaded one (silently resolves to frame 0) produce
        IDENTICAL output, because frame 0's layer id is also a valid frame-0
        node either way. Such a test would not be weak evidence -- it would
        be NO evidence, and must never be counted as coverage of the
        threading fix. Only frame_index >= 1 with a track genuinely absent
        from frame 0 can tell the two implementations apart.
        """
        doc = Document(2, 2)
        frame0_layer_id = doc.frames[0].layers[0].layer_id
        doc.add_frame()
        frame1_layer = doc.frames[1].layers[0]
        assert frame1_layer.layer_id != frame0_layer_id
        assert frame1_layer.layer_id not in (
            layer.layer_id for layer in doc.frames[0].layers
        )

        target = EditTarget(frame_index=1, layer_id=frame1_layer.layer_id)
        edit = PixelEdit(
            frame1_layer.buffer,
            [(0, 0, TRANSPARENT, RED)],
            target=target,
        )

        trace = edit.edit_trace()

        assert trace == (
            RasterTrace(
                frame_index=1,
                layer_id=frame1_layer.layer_id,
                tile_x=0,
                tile_y=0,
            ),
        )
