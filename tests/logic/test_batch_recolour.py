"""Tests for pixelart_creator.logic.batch_ops — transactional batch recolour.

Covers REQ-P8-LOGIC-011 (batch recolour = one transactional reversible command
over N targets; each per-target output == the single ``palette_ops`` op;
per-target failure isolated with ZERO mutation) and -013
(``MAX_BATCH_RECOLOUR_TARGETS``). Composes the shipped ``palette_ops`` (PS-1).
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.logic import batch_ops, palette_ops
from pixelart_creator.logic.batch_ops import (
    BatchError,
    ColorMapping,
    RecolourTarget,
    make_batch_recolour_command,
)
from pixelart_creator.logic.constants import MAX_BATCH_RECOLOUR_TARGETS
from pixelart_creator.logic.history import GroupCommand
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _rgba_buffer(width=3, height=3, fill=RED) -> PixelBuffer:
    return PixelBuffer(width, height, ColorMode.RGBA, fill=fill)


def _indexed_buffer(width=3, height=3, fill=0) -> PixelBuffer:
    return PixelBuffer(width, height, ColorMode.INDEXED, fill=fill)


# --------------------------------------------------------------------------- #
# ColorMapping — exactly one of index_map / color_map                          #
# --------------------------------------------------------------------------- #


def test_color_mapping_requires_exactly_one():
    with pytest.raises(BatchError):
        ColorMapping()  # neither
    with pytest.raises(BatchError):
        ColorMapping(index_map={0: 1}, color_map={RED: BLUE})  # both


def test_color_mapping_index_only_ok():
    assert ColorMapping(index_map={0: 1}).color_map is None


# --------------------------------------------------------------------------- #
# make_batch_recolour_command — transactional over N targets                   #
# --------------------------------------------------------------------------- #


def test_batch_returns_unapplied_group_command():
    targets = [RecolourTarget(_rgba_buffer())]
    cmd = make_batch_recolour_command(targets, ColorMapping(color_map={RED: BLUE}))
    assert isinstance(cmd, GroupCommand)
    # Returned UNAPPLIED — the buffer is untouched until execute().
    assert tuple(targets[0].buffer.data[0, 0]) == RED


def test_batch_one_undo_reverts_all_targets():
    # REQ-P8-LOGIC-011: one transactional command over N targets; one undo reverts
    # every target.
    buffers = [_rgba_buffer() for _ in range(4)]
    targets = [RecolourTarget(b, f"layer{i}") for i, b in enumerate(buffers)]
    before = [b.data.copy() for b in buffers]
    cmd = make_batch_recolour_command(targets, ColorMapping(color_map={RED: BLUE}))
    cmd.execute()
    for b in buffers:
        assert tuple(b.data[0, 0]) == BLUE
    cmd.undo()  # single undo
    for b, snap in zip(buffers, before):
        assert np.array_equal(b.data, snap)


def test_batch_output_equals_single_palette_op():
    # Each per-target result is byte-identical to the single one-at-a-time recolour.
    batch_buf = _rgba_buffer()
    single_buf = _rgba_buffer()
    cmd = make_batch_recolour_command(
        [RecolourTarget(batch_buf)], ColorMapping(color_map={RED: BLUE})
    )
    cmd.execute()
    single = palette_ops.remap_colors(single_buf, {RED: BLUE})
    assert np.array_equal(batch_buf.data, single.data)


def test_batch_indexed_targets():
    buf = _indexed_buffer(fill=0)
    cmd = make_batch_recolour_command(
        [RecolourTarget(buf)], ColorMapping(index_map={0: 5})
    )
    cmd.execute()
    assert int(buf.data[0, 0]) == 5
    cmd.undo()
    assert int(buf.data[0, 0]) == 0


# --------------------------------------------------------------------------- #
# Per-target failure isolation — ZERO mutation on error                        #
# --------------------------------------------------------------------------- #


def test_indexed_target_with_color_map_fails_isolated():
    # An indexed target with only a color_map raises BEFORE any target is mutated.
    good = _rgba_buffer()
    bad = _indexed_buffer()
    good_before = good.data.copy()
    bad_before = bad.data.copy()
    with pytest.raises(BatchError):
        make_batch_recolour_command(
            [RecolourTarget(good), RecolourTarget(bad, "indexed")],
            ColorMapping(color_map={RED: BLUE}),
        )
    # Nothing was applied (command build failed before execute) — zero mutation.
    assert np.array_equal(good.data, good_before)
    assert np.array_equal(bad.data, bad_before)


def test_rgba_target_with_index_map_fails_isolated():
    rgba = _rgba_buffer()
    with pytest.raises(BatchError):
        make_batch_recolour_command(
            [RecolourTarget(rgba)], ColorMapping(index_map={0: 1})
        )


def test_out_of_range_index_normalised_to_batch_error():
    buf = _indexed_buffer()
    with pytest.raises(BatchError):
        make_batch_recolour_command(
            [RecolourTarget(buf)], ColorMapping(index_map={0: 999})
        )


def test_non_recolour_target_rejected():
    bad = ["not-a-target"]  # type: ignore[list-item]
    with pytest.raises(BatchError):
        make_batch_recolour_command(bad, ColorMapping(color_map={RED: BLUE}))


# --------------------------------------------------------------------------- #
# Guards + bounds (REQ-P8-LOGIC-013)                                            #
# --------------------------------------------------------------------------- #


def test_batch_rejects_non_mapping():
    with pytest.raises(BatchError):
        make_batch_recolour_command([RecolourTarget(_rgba_buffer())], object())


def test_batch_rejects_empty_targets():
    with pytest.raises(BatchError):
        make_batch_recolour_command([], ColorMapping(color_map={RED: BLUE}))


def test_batch_enforces_max_targets(monkeypatch):
    monkeypatch.setattr(batch_ops, "MAX_BATCH_RECOLOUR_TARGETS", 2)
    targets = [RecolourTarget(_rgba_buffer()) for _ in range(3)]
    with pytest.raises(BatchError):
        make_batch_recolour_command(targets, ColorMapping(color_map={RED: BLUE}))


def test_max_batch_targets_single_sourced():
    assert batch_ops.MAX_BATCH_RECOLOUR_TARGETS is MAX_BATCH_RECOLOUR_TARGETS
