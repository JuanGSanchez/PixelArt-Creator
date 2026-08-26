"""Tests for pixelart_creator.logic.doc_transform (REQ-CSD-LOGIC-003).

canvas-scale-defects spec.md / tasks.md T05. This module did not exist before
this batch, so SC-CSD-L003-1..4 are DEFECT: every one of them fails against
the unfixed tree (import fails outright). Their pre-fix failure is recorded
in the AGT-04 report rather than re-demonstrated here, since "the module does
not exist" cannot be proven by a test written against a module that must
import it to run at all.

Also covers (per T05's "add coverage for..." instruction): enumerate_targets
order across multi-frame/multi-layer/masked documents, DocumentTransformRun's
total/done/finished/results()/step() contract and its logic-level atomicity
(REQ-CSD-UI-012's structural half), and make_document_transform_command's
finished-run precondition and do/undo byte-exact restoration.

Zero Qt.
"""

from __future__ import annotations

import pathlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic import doc_transform
from pixelart_creator.logic.constants import (
    DOCUMENT_TRANSFORM_CONFIRM_BYTES,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)
from pixelart_creator.logic.doc_transform import (
    DocTransformError,
    DocumentTransformRun,
    TransformTarget,
    enumerate_targets,
    make_document_transform_command,
    projected_peak_bytes,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.transform import flip_horizontal, rotate_90_cw


class _FakeBuffer:
    """A width/height/mode stand-in for the estimator's cost-only tests.

    projected_peak_bytes reads only target.source.width/.height/.mode -- it
    never touches pixel data -- so a lightweight stand-in lets the large
    documented figures (e.g. 32 buffers of 4096x2304 RGBA, ~1.2 GB of real
    pixel data) be exercised without allocating that memory.
    """

    def __init__(
        self, width: int, height: int, mode: ColorMode = ColorMode.RGBA
    ) -> None:
        self.width = width
        self.height = height
        self.mode = mode


def _doc_with_fake_buffers(
    n_frames: int, n_layers: int, width: int, height: int, mode: ColorMode
):
    """A real Document whose layer buffers are swapped for _FakeBuffer stand-ins."""
    doc = Document(1, 1, mode=mode)
    doc.frames[0].layers[0].buffer = _FakeBuffer(width, height, mode)
    for _ in range(n_layers - 1):
        doc.add_layer(frame_index=0)
        doc.frames[0].layers[-1].buffer = _FakeBuffer(width, height, mode)
    for _ in range(n_frames - 1):
        doc.add_frame()
        doc.frames[-1].layers[0].buffer = _FakeBuffer(width, height, mode)
        for _ in range(n_layers - 1):
            doc.add_layer(frame_index=len(doc.frames) - 1)
            doc.frames[-1].layers[-1].buffer = _FakeBuffer(width, height, mode)
    return doc


def _small_doc(n_frames: int, n_layers: int, width: int = 4, height: int = 4):
    """A real Document with genuine small PixelBuffers, for step()/command tests."""
    doc = Document(width, height)
    for _ in range(n_layers - 1):
        doc.add_layer(frame_index=0)
    for _ in range(n_frames - 1):
        doc.add_frame()
        for _ in range(n_layers - 1):
            doc.add_layer(frame_index=len(doc.frames) - 1)
    return doc


# --- SC-CSD-L003-1/2: the estimate sums results AND retained sources ------


def test_sc_l003_1_estimate_sums_results_and_retained_sources():
    # 8 frames x 4 layers of 4096x2304 RGBA, target 7680x4320.
    doc = _doc_with_fake_buffers(8, 4, 4096, 2304, ColorMode.RGBA)
    assert projected_peak_bytes(doc, 7680, 4320) == 5_454_692_352


def test_sc_l003_2_indexed_buffers_costed_at_one_byte_per_pixel():
    doc = _doc_with_fake_buffers(1, 1, 100, 100, ColorMode.INDEXED)
    assert projected_peak_bytes(doc, 200, 200) == 50_000


def test_estimator_boundary_lands_exactly_on_the_threshold():
    # SC-CSD-U015-3's boundary: 7680x4320 RGBA, 1 frame of 2 layers, a
    # dimension-preserving transform (flip). The projected peak must land
    # EXACTLY on DOCUMENT_TRANSFORM_CONFIRM_BYTES, not one byte either side
    # -- an off-by-one in the estimator is the likely defect this guards.
    doc = _doc_with_fake_buffers(1, 2, 7680, 4320, ColorMode.RGBA)
    peak = projected_peak_bytes(doc, 7680, 4320)
    assert peak == 530_841_600
    assert peak == DOCUMENT_TRANSFORM_CONFIRM_BYTES


def test_estimator_one_layer_more_lands_strictly_above_the_threshold():
    doc = _doc_with_fake_buffers(1, 3, 7680, 4320, ColorMode.RGBA)
    peak = projected_peak_bytes(doc, 7680, 4320)
    assert peak == 796_262_400
    assert peak > DOCUMENT_TRANSFORM_CONFIRM_BYTES


@settings(max_examples=40, derandomize=True)
@given(
    w1=st.integers(min_value=1, max_value=64),
    h1=st.integers(min_value=1, max_value=64),
    w2=st.integers(min_value=1, max_value=128),
    h2=st.integers(min_value=1, max_value=128),
)
def test_property_estimator_monotonic_in_target_dimensions(w1, h1, w2, h2):
    # A larger target dimension never yields a smaller projected peak, for a
    # fixed document (the source term is constant; only the result term grows).
    doc = _doc_with_fake_buffers(2, 2, 32, 32, ColorMode.RGBA)
    small = projected_peak_bytes(doc, w1, h1)
    big = projected_peak_bytes(doc, max(w1, w2), max(h1, h2))
    assert big >= small


# --- SC-CSD-L003-3: the threshold is a named constant, not a literal -----


def test_sc_l003_3_threshold_constant_value_and_derivation():
    assert DOCUMENT_TRANSFORM_CONFIRM_BYTES == 530_841_600
    assert (
        DOCUMENT_TRANSFORM_CONFIRM_BYTES == 4 * MAX_CANVAS_WIDTH * MAX_CANVAS_HEIGHT * 4
    )


def test_sc_l003_3_no_call_site_compares_against_an_inlined_literal():
    # Search the shipped source tree (excluding constants.py, which defines
    # the constant, and this test file, which legitimately quotes it) for the
    # bare literal -- a call site that inlines 530841600 instead of importing
    # DOCUMENT_TRANSFORM_CONFIRM_BYTES would show up here.
    root = (
        pathlib.Path(doc_transform.__file__).resolve().parents[1]
    )  # pixelart_creator/
    offenders = []
    for path in root.rglob("*.py"):
        if path.name in ("constants.py",):
            continue
        text = path.read_text(encoding="utf-8")
        if "530841600" in text or "530_841_600" in text:
            offenders.append(str(path))
    assert offenders == []


# --- SC-CSD-L003-4: the estimator imports no Qt --------------------------


def test_sc_l003_4_module_imports_no_qt():
    source = pathlib.Path(doc_transform.__file__).read_text(encoding="utf-8")
    assert "PySide6" not in source
    assert "pyside6" not in source.lower()


def test_doctransformerror_is_a_value_error():
    assert issubclass(DocTransformError, ValueError)


# --- enumerate_targets: order across multi-frame/multi-layer/masked docs -


def test_enumerate_targets_order_multi_frame_multi_layer_with_mask():
    # 3 frames of 2 layers each; the second layer of frame 0 carries a mask
    # (SC-CSD-U011-1's shape: total buffer count 7).
    doc = _small_doc(3, 2)
    masked_layer = doc.frames[0].layers[1]
    masked_layer.mask = PixelBuffer(doc.width, doc.height)

    targets = enumerate_targets(doc)

    assert len(targets) == 7
    expected = [
        (doc.frames[0].layers[0], "buffer"),
        (doc.frames[0].layers[1], "buffer"),
        (doc.frames[0].layers[1], "mask"),
        (doc.frames[1].layers[0], "buffer"),
        (doc.frames[1].layers[1], "buffer"),
        (doc.frames[2].layers[0], "buffer"),
        (doc.frames[2].layers[1], "buffer"),
    ]
    actual = [(t.holder, t.attribute) for t in targets]
    assert actual == expected
    # each source is the exact buffer/mask object at enumeration time.
    assert targets[0].source is doc.frames[0].layers[0].buffer
    assert targets[2].source is masked_layer.mask


def test_run_total_equals_seven_on_u011_1_shape():
    doc = _small_doc(3, 2)
    doc.frames[0].layers[1].mask = PixelBuffer(doc.width, doc.height)
    run = DocumentTransformRun(enumerate_targets(doc))
    assert run.total == 7
    assert run.done == 0
    assert not run.finished


def test_enumerate_targets_layer_without_mask_emits_one_target():
    doc = _small_doc(1, 1)
    targets = enumerate_targets(doc)
    assert len(targets) == 1
    assert targets[0].attribute == "buffer"


# --- DocumentTransformRun: total/done/finished/results()/step() ----------


def test_run_step_accumulates_results_in_order():
    doc = _small_doc(2, 2)
    targets = enumerate_targets(doc)
    run = DocumentTransformRun(targets)
    originals = [t.source for t in targets]

    for i, target in enumerate(targets):
        assert run.done == i
        assert not run.finished
        result = run.step(flip_horizontal)
        assert result == flip_horizontal(originals[i])
        assert run.done == i + 1

    assert run.finished
    assert len(run.results()) == run.total


def test_run_step_raises_once_finished():
    doc = _small_doc(1, 1)
    run = DocumentTransformRun(enumerate_targets(doc))
    run.step(flip_horizontal)
    assert run.finished
    with pytest.raises(DocTransformError):
        run.step(flip_horizontal)


def test_run_step_never_mutates_a_layer():
    # The structural half of REQ-CSD-UI-012: step() must read target.source
    # and write only to its own results list, never to Layer.buffer/.mask.
    doc = _small_doc(3, 2)
    doc.frames[0].layers[1].mask = PixelBuffer(doc.width, doc.height)
    targets = enumerate_targets(doc)
    original_ids = {
        id(layer.buffer) for frame in doc.frames for layer in frame.layers
    } | {
        id(layer.mask)
        for frame in doc.frames
        for layer in frame.layers
        if layer.mask is not None
    }

    run = DocumentTransformRun(targets)
    for _ in range(run.total - 1):
        run.step(flip_horizontal)
        # every buffer/mask on the document is still the pre-run object.
        current_ids = {
            id(layer.buffer) for frame in doc.frames for layer in frame.layers
        } | {
            id(layer.mask)
            for frame in doc.frames
            for layer in frame.layers
            if layer.mask is not None
        }
        assert current_ids == original_ids
    # the final step also leaves every Layer untouched -- only a subsequent
    # make_document_transform_command()._do() call may commit anything.
    run.step(flip_horizontal)
    current_ids = {
        id(layer.buffer) for frame in doc.frames for layer in frame.layers
    } | {
        id(layer.mask)
        for frame in doc.frames
        for layer in frame.layers
        if layer.mask is not None
    }
    assert current_ids == original_ids
    assert run.finished


# --- make_document_transform_command: finished-run precondition ----------


def test_make_command_raises_on_unfinished_run_and_document_stays_untouched():
    doc = _small_doc(2, 2)
    targets = enumerate_targets(doc)
    run = DocumentTransformRun(targets)
    run.step(flip_horizontal)  # partial -- 1 of 4
    prior_width, prior_height = doc.width, doc.height
    prior_buffer_ids = [id(t.holder.buffer) for t in targets]

    with pytest.raises(DocTransformError):
        make_document_transform_command(doc, run, 8, 8)

    # no command was constructible, and nothing on the document moved.
    assert doc.width == prior_width and doc.height == prior_height
    assert [id(t.holder.buffer) for t in targets] == prior_buffer_ids


def test_make_command_raises_on_a_run_with_zero_steps():
    doc = _small_doc(1, 2)
    run = DocumentTransformRun(enumerate_targets(doc))
    with pytest.raises(DocTransformError):
        make_document_transform_command(doc, run, 8, 8)


# --- make_document_transform_command: do/undo byte-exact restoration -----


def test_make_command_do_commits_every_result_and_the_new_geometry():
    doc = _small_doc(3, 2, width=5, height=2)  # non-square -> rotate swaps dims
    doc.frames[0].layers[1].mask = PixelBuffer(doc.width, doc.height)
    targets = enumerate_targets(doc)
    run = DocumentTransformRun(targets)
    while not run.finished:
        run.step(rotate_90_cw)
    expected_results = run.results()

    cmd = make_document_transform_command(doc, run, 2, 5, label="rotate")
    cmd.execute()

    for target, expected in zip(targets, expected_results):
        assert getattr(target.holder, target.attribute) is expected
    assert doc.width == 2 and doc.height == 5


def test_make_command_undo_restores_every_source_object_and_prior_geometry():
    doc = _small_doc(2, 2, width=6, height=3)
    doc.frames[0].layers[1].mask = PixelBuffer(doc.width, doc.height)
    targets = enumerate_targets(doc)
    prior_sources = [t.source for t in targets]
    prior_width, prior_height = doc.width, doc.height

    run = DocumentTransformRun(targets)
    while not run.finished:
        run.step(rotate_90_cw)
    cmd = make_document_transform_command(doc, run, 3, 6)
    cmd.execute()
    assert doc.width == 3 and doc.height == 6

    cmd.undo()

    assert doc.width == prior_width and doc.height == prior_height
    for target, source in zip(targets, prior_sources):
        # byte-exact: the SAME object is restored, not merely an equal copy.
        assert getattr(target.holder, target.attribute) is source


def test_make_command_is_returned_unapplied():
    doc = _small_doc(1, 1)  # default 4x4
    run = DocumentTransformRun(enumerate_targets(doc))
    run.step(flip_horizontal)
    original_buffer = doc.frames[0].layers[0].buffer
    cmd = make_document_transform_command(doc, run, 9, 9)
    # constructing the command must not itself apply anything.
    assert doc.frames[0].layers[0].buffer is original_buffer
    assert doc.width == 4 and doc.height == 4
    cmd.execute()
    assert doc.width == 9 and doc.height == 9
