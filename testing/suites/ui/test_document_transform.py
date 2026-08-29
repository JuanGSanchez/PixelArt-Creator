"""UI/integration tests for the whole-document transform cost gate, progress and
atomic cancellation (canvas-scale-defects `spec.md` REQ-CSD-UI-008..013).

Every scenario here drives the REAL Qt surfaces introduced by this batch —
:class:`~pixelart_creator.ui.document_transform_runner.Document_Transform_Runner`,
:class:`~pixelart_creator.ui.document_transform_dialogs.Document_Transform_Confirm_Dialog`
and :class:`~pixelart_creator.ui.document_transform_dialogs.Document_Transform_Progress_Dialog`
— headless, through the real ``QTimer``/``QEventLoop`` chain the runner uses
(`plan.md` §5.2/§5.3). None of the runner's internals are mocked; only the
*dialog result* (accept/decline/cancel) is driven, exactly as `tasks.md` T15
directs ("connecting to the runner's ``stepped`` signal and calling
``cancel()`` inside the slot").

**A resource note, disclosed rather than silently substituted.** Several
Gherkin ``Given`` clauses in `spec.md` §7 use literal figures sized for the
LOGIC-layer cost-estimator tests (`testing/suites/logic/test_doc_transform.py`, T05,
AGT-04's module) — e.g. an 8-frame x 4-layer 4096x2304 document scaled to
7680x4320 (a real ~5.08 GiB transient peak). Reproducing every such figure
here, at the UI layer, with real backing pixel data would make this module
prohibitively slow/heavy for a routine suite run. Where a scenario's point is
the *threshold classification* (above/below/exactly-at) rather than a specific
number, this module uses SMALLER real documents that are proven, by direct
measurement in this session, to cross the SAME real, unpatched
``DOCUMENT_TRANSFORM_CONFIRM_BYTES`` on the correct side — e.g. a document with
several small-source layers whose RESAMPLED RESULTS alone exceed the
threshold (the ``projected_peak_bytes`` "results" term does not require the
source to be large). The ONE scenario that is exact-numbers-critical
(SC-CSD-U015-3, the exactly-on-the-boundary case) lives in
``test_transform_actions.py`` per `tasks.md` T14 and uses the spec's own real
8K figures (530,841,600 / 796,262,400 bytes), verified affordable in this
session (<1s, <800MB).

Every test in this module also runs under **both** themes via the autouse
``theme`` fixture (`testing/suites/ui/conftest.py`); this module adds no explicit
theme parametrisation of its own, only the accessibility assertions that are
theme-relevant (T27, `plan.md` §8.1 — Article V.1/V.3/V.4, a constitution gate,
not a REQ-ID).
"""

from __future__ import annotations

from typing import List

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from pixelart_creator.logic.constants import (
    DOCUMENT_TRANSFORM_CONFIRM_BYTES,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)
from pixelart_creator.logic.doc_transform import enumerate_targets, projected_peak_bytes
from pixelart_creator.logic.document import Document, Layer, iter_layers
from pixelart_creator.logic.pixel_buffer import PixelBuffer
from pixelart_creator.logic.transform import TransformError, scale_nearest
from pixelart_creator.ui.commands import LogicCommand
from pixelart_creator.ui.document_transform_dialogs import (
    Document_Transform_Confirm_Dialog,
    Document_Transform_Progress_Dialog,
)
from pixelart_creator.ui.document_transform_runner import (
    Document_Transform_Runner,
    run_document_transform,
)

# -- test document builders ------------------------------------------------


def _build_document(
    width: int,
    height: int,
    frame_layer_counts: List[int],
    masks=(),
) -> Document:
    """Build a :class:`Document` with ``frame_layer_counts[i]`` layers in frame i.

    ``masks`` is an iterable of ``(frame_index, layer_index)`` pairs; each
    named layer receives an attached mask sized to the document (direct
    attribute assignment — this is test setup, not the reversible
    ``make_attach_mask_command`` path, and no ``Command`` is pushed by it).
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


def _all_layers(document: Document) -> List[Layer]:
    """Every leaf :class:`Layer` across every frame, in enumeration order."""
    out: List[Layer] = []
    for frame in document.frames:
        out.extend(iter_layers(frame.layers))
    return out


def _spy_init(monkeypatch, cls, qtbot):
    """Monkeypatch ``cls.__init__`` to record + track every instance built.

    Returns the list of constructed instances (in construction order); each
    is registered with ``qtbot`` for deterministic teardown.
    """
    instances: List[object] = []
    original = cls.__init__

    def _wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        instances.append(self)
        qtbot.addWidget(self)

    monkeypatch.setattr(cls, "__init__", _wrapped)
    return instances


def _fail_on_message_box(monkeypatch) -> List[tuple]:
    """Fail loudly (record + assertable) if any QMessageBox static is invoked.

    REQ-CSD-UI-010/-012 both require "no error, no follow-up question" —
    this catches a stray warning/question/critical/information dialog that a
    regression might introduce, rather than silently letting one auto-answer.
    """
    calls: List[tuple] = []
    for name in ("warning", "critical", "question", "information"):

        def _make(name=name):
            def _recorder(*args, **kwargs):
                calls.append((name, args, kwargs))
                return QMessageBox.StandardButton.Ok

            return _recorder

        monkeypatch.setattr(QMessageBox, name, staticmethod(_make()))
    return calls


# -- SC-CSD-U008-1 / -2 (REQ-CSD-UI-008): confirmation states a real figure --


def test_sc_csd_u008_1_confirm_shows_real_figure_before_resample(qtbot, monkeypatch):
    """SC-CSD-U008-1 (DEFECT): above threshold, one modal confirmation appears
    before any buffer resamples, naming a real human-readable size and the
    target geometry, with explicit proceed/decline actions.

    Pre-change: no such surface exists at all (``Document_Transform_Runner``
    is new code) — this scenario cannot even be exercised against the
    unfixed code, which is itself the DEFECT (`tasks.md` T15).
    """
    document = _build_document(8, 8, [5])  # 5 tiny sources, 1 frame
    target = (MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    projected = projected_peak_bytes(document, *target)
    assert projected > DOCUMENT_TRANSFORM_CONFIRM_BYTES  # real production threshold

    confirms = _spy_init(monkeypatch, Document_Transform_Confirm_Dialog, qtbot)
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    resampled: List[int] = []

    def fn(buf: PixelBuffer) -> PixelBuffer:
        resampled.append(1)
        return scale_nearest(buf, *target)

    result = run_document_transform(document, fn, *target, "Scale Canvas")

    assert len(confirms) == 1  # exactly one confirmation
    dialog = confirms[0]
    expected_size_text = QLocale().formattedDataSize(projected)
    assert expected_size_text in dialog._message.text()
    assert str(target[0]) in dialog._message.text()
    assert str(target[1]) in dialog._message.text()
    assert dialog._proceed.text() != ""  # explicit proceed
    assert dialog._decline.text() != ""  # explicit decline
    assert not resampled  # declined -> no buffer was ever resampled
    assert result is None


def test_sc_csd_u008_2_figure_accounts_for_results_and_sources(qtbot, monkeypatch):
    """SC-CSD-U008-2 (DEFECT): the displayed figure is results + retained
    sources, not the result size alone.

    Sources are deliberately NOT tiny here (2000x2000, ~15.26 MiB each) so the
    two terms are numerically distinguishable — proving the dialog reads the
    real combined total, not a results-only shortcut.
    """
    document = _build_document(2000, 2000, [4])  # 4 sizeable sources, 1 frame
    target = (MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)

    results_term = sum(target[0] * target[1] * 4 for _ in enumerate_targets(document))
    sources_term = sum(
        t.source.width * t.source.height * 4 for t in enumerate_targets(document)
    )
    projected = projected_peak_bytes(document, *target)
    assert projected == results_term + sources_term
    assert sources_term > 0  # the source term is non-trivial in this fixture
    assert projected != results_term  # not results alone
    assert projected > DOCUMENT_TRANSFORM_CONFIRM_BYTES

    confirms = _spy_init(monkeypatch, Document_Transform_Confirm_Dialog, qtbot)
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    run_document_transform(
        document, lambda buf: scale_nearest(buf, *target), *target, "Scale Canvas"
    )

    dialog = confirms[0]
    assert QLocale().formattedDataSize(projected) in dialog._message.text()
    assert QLocale().formattedDataSize(results_term) not in dialog._message.text() or (
        # only acceptable if the two format identically, which they do not here
        results_term
        == projected
    )


# -- SC-CSD-U009-1 (REQ-CSD-UI-009): ordinary work is never interrupted -------


def test_sc_csd_u009_1_ordinary_animation_work_never_prompts(qtbot, monkeypatch):
    """SC-CSD-U009-1 (DEFECT): below threshold, no confirmation at all; the
    operation proceeds and every buffer resamples, as one undoable command.

    Uses the spec's own literal figures (128x128, 60 frames x 3 layers = 180
    buffers, scaled to 512x512 -> a real projected peak of 200,540,160 bytes,
    well under the 530,841,600-byte threshold) — measured in this session at
    <1s / ~190 MiB, so no scaling-down was needed here.
    """
    frame_counts = [3] * 60
    document = _build_document(128, 128, frame_counts)
    assert sum(frame_counts) == 180
    target = (512, 512)
    projected = projected_peak_bytes(document, *target)
    assert projected == 200_540_160
    assert projected <= DOCUMENT_TRANSFORM_CONFIRM_BYTES

    confirms = _spy_init(monkeypatch, Document_Transform_Confirm_Dialog, qtbot)
    command = run_document_transform(
        document, lambda buf: scale_nearest(buf, *target), *target, "Scale Canvas"
    )

    assert confirms == []  # no confirmation at all
    assert command is not None

    stack = QUndoStack()
    stack.push(LogicCommand(command, lambda: None, "Scale Canvas"))
    assert stack.count() == 1  # one undoable step
    for layer in _all_layers(document):
        assert (layer.buffer.width, layer.buffer.height) == target


# -- SC-CSD-U010-1 (REQ-CSD-UI-010): declining is completely inert -----------


def test_sc_csd_u010_1_declining_leaves_everything_untouched(qtbot, monkeypatch):
    """SC-CSD-U010-1 (DEFECT): declining leaves the document AND the undo
    stack exactly as they were: no progress dialog, no rebind, no error, and
    the stack's count/index are unchanged.
    """
    document = _build_document(8, 8, [5])  # cheap source; huge hypothetical target
    target = (MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    assert projected_peak_bytes(document, *target) > DOCUMENT_TRANSFORM_CONFIRM_BYTES

    stack = QUndoStack()
    dummy_a = LogicCommand(_trivial_command(), lambda: None, "dummy A")
    dummy_b = LogicCommand(_trivial_command(), lambda: None, "dummy B")
    stack.push(dummy_a)
    stack.push(dummy_b)
    assert stack.count() == 2 and stack.index() == 2

    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    progresses = _spy_init(monkeypatch, Document_Transform_Progress_Dialog, qtbot)
    error_calls = _fail_on_message_box(monkeypatch)

    before = [(ly, ly.buffer, ly.mask) for ly in _all_layers(document)]
    prior_w, prior_h = document.width, document.height

    result = run_document_transform(
        document, lambda buf: scale_nearest(buf, *target), *target, "Scale Canvas"
    )

    assert result is None
    assert progresses == []  # no progress dialog appears
    assert error_calls == []  # no error/warning dialog
    assert document.width == prior_w and document.height == prior_h
    for layer, buf, mask in before:
        assert layer.buffer is buf
        assert layer.mask is mask
    assert stack.count() == 2 and stack.index() == 2  # unchanged


def _trivial_command():
    """A no-op :class:`FunctionCommand`, for populating an undo stack in tests."""
    from pixelart_creator.logic.history import FunctionCommand

    return FunctionCommand(lambda: None, lambda: None, label="dummy")


# -- SC-CSD-U011-1 / -2 (REQ-CSD-UI-011): real, determinate progress ---------


def test_sc_csd_u011_1_progress_maximum_is_exact_buffer_count(qtbot, monkeypatch):
    """SC-CSD-U011-1 (DEFECT): the progress range is (0, 7) for a document
    with 6 layer buffers + 1 attached mask across 3 frames x 2 layers — never
    ``(0, 0)``, never indeterminate.
    """
    document = _build_document(64, 48, [2, 2, 2], masks=[(0, 1)])
    assert len(enumerate_targets(document)) == 7

    progresses = _spy_init(monkeypatch, Document_Transform_Progress_Dialog, qtbot)
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    run_document_transform(
        document, lambda buf: scale_nearest(buf, 256, 192), 256, 192, "Scale Canvas"
    )

    assert len(progresses) == 1
    dialog = progresses[0]
    assert dialog._bar.minimum() == 0
    assert dialog._bar.maximum() == 7
    assert (dialog._bar.minimum(), dialog._bar.maximum()) != (0, 0)


def test_sc_csd_u011_2_progress_advances_monotonically_to_maximum(qtbot):
    """SC-CSD-U011-2 (DEFECT): the observed progress value starts effectively
    at 0, is non-decreasing at every step, and the final observed value is
    the exact total (7)."""
    document = _build_document(64, 48, [2, 2, 2], masks=[(0, 1)])
    runner = Document_Transform_Runner()
    observed: List[int] = []
    runner.stepped.connect(observed.append)

    command = runner.run(
        document,
        lambda buf: scale_nearest(buf, 256, 192),
        256,
        192,
        "Scale Canvas",
    )

    assert command is not None
    assert observed[0] >= 0
    assert observed == sorted(observed)  # non-decreasing
    assert observed[-1] == 7


# -- SC-CSD-U012-1 / -2 / -4 (REQ-CSD-UI-012): atomic cancellation -----------


def _identity_snapshot(document: Document):
    return [(ly, ly.buffer, ly.mask) for ly in _all_layers(document)]


def _assert_identity_unchanged(before) -> None:
    for layer, buf, mask in before:
        assert layer.buffer is buf
        assert layer.mask is mask


@pytest.mark.timeout(30)
def test_sc_csd_u012_1_cancel_before_first_buffer_is_atomic(qtbot, monkeypatch):
    """SC-CSD-U012-1 (DEFECT): cancelling before the FIRST buffer completes
    leaves every layer's buffer/mask object identity, and the document
    geometry, exactly as they were; nothing reaches the undo stack.
    """
    document = _build_document(64, 48, [2, 2, 2])  # 6 buffers, no confirm needed
    before = _identity_snapshot(document)
    prior_w, prior_h = document.width, document.height

    stack = QUndoStack()
    stack.push(LogicCommand(_trivial_command(), lambda: None, "dummy"))
    assert stack.count() == 1 and stack.index() == 1

    runner = Document_Transform_Runner()

    # Cancel as early as the runner can be reached: at Progress-dialog
    # construction time, strictly before the first zero-delay tick runs
    # (i.e. before progress value 0 is even observed) — SC-CSD-U012-1's
    # "progress value is 0" cancel point.
    original_init = Document_Transform_Progress_Dialog.__init__

    def _wrapped(self, *a, **k):
        original_init(self, *a, **k)
        runner.cancel()

    monkeypatch.setattr(Document_Transform_Progress_Dialog, "__init__", _wrapped)

    resampled: List[int] = []

    def fn(buf: PixelBuffer) -> PixelBuffer:
        resampled.append(1)
        return scale_nearest(buf, 256, 192)

    result = runner.run(document, fn, 256, 192, "Scale Canvas")

    assert result is None
    assert not resampled  # not even the first buffer was ever touched
    _assert_identity_unchanged(before)
    assert document.width == prior_w and document.height == prior_h
    assert stack.count() == 1 and stack.index() == 1  # unchanged


@pytest.mark.timeout(30)
def test_sc_csd_u012_2_cancel_on_last_buffer_is_atomic(qtbot):
    """SC-CSD-U012-2 (DEFECT): cancelling once 5 of 6 buffers have resampled
    (i.e. before the 6th/final one commits) is EQUALLY atomic — the run never
    reaches ``finished``, so no command is ever built and nothing changes.
    """
    document = _build_document(64, 48, [2, 2, 2])  # 6 buffers
    before = _identity_snapshot(document)
    prior_w, prior_h = document.width, document.height

    runner = Document_Transform_Runner()

    def _on_stepped(value: int) -> None:
        if value == 5:
            runner.cancel()

    runner.stepped.connect(_on_stepped)
    result = runner.run(
        document, lambda buf: scale_nearest(buf, 256, 192), 256, 192, "Scale Canvas"
    )

    assert result is None
    _assert_identity_unchanged(before)
    assert document.width == prior_w and document.height == prior_h


@pytest.mark.timeout(30)
def test_sc_csd_u012_4_cancelling_reports_and_asks_nothing(qtbot, monkeypatch):
    """SC-CSD-U012-4 (DEFECT): cancelling shows no error dialog and no
    follow-up "confirm the cancellation" dialog — it just ends."""
    document = _build_document(64, 48, [2, 2, 2])
    error_calls = _fail_on_message_box(monkeypatch)
    runner = Document_Transform_Runner()

    def _on_stepped(value: int) -> None:
        if value == 2:
            runner.cancel()

    runner.stepped.connect(_on_stepped)
    result = runner.run(
        document, lambda buf: scale_nearest(buf, 256, 192), 256, 192, "Scale Canvas"
    )

    assert result is None
    assert error_calls == []


# -- SC-CSD-U013-1 / -2 / -3 (REQ-CSD-UI-013): at most one question ----------


@pytest.mark.timeout(60)
def test_sc_csd_u013_1_above_threshold_one_confirmation_then_progress(
    qtbot, monkeypatch
):
    """SC-CSD-U013-1 (DEFECT): above threshold, exactly one confirmation is
    shown, the progress indicator follows immediately, and no further
    confirmation appears at any point in a completed run.

    This is the one test in this module that lets a real over-threshold
    scale run to completion (5 buffers resampled to 7680x4320, ~660 MiB
    transient peak; measured in this session at ~3s) — needed because the
    scenario's point is "no SECOND confirmation appears for the rest of the
    operation", which requires actually finishing it.
    """
    document = _build_document(8, 8, [5])
    target = (MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    assert projected_peak_bytes(document, *target) > DOCUMENT_TRANSFORM_CONFIRM_BYTES

    confirms = _spy_init(monkeypatch, Document_Transform_Confirm_Dialog, qtbot)
    progresses = _spy_init(monkeypatch, Document_Transform_Progress_Dialog, qtbot)
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )

    result = run_document_transform(
        document, lambda buf: scale_nearest(buf, *target), *target, "Scale Canvas"
    )

    assert len(confirms) == 1  # exactly one, ever
    assert len(progresses) == 1  # progress followed
    assert result is not None  # ran to completion


def test_sc_csd_u013_2_below_threshold_zero_confirmations_progress_shown(
    qtbot, monkeypatch
):
    """SC-CSD-U013-2 (mixed — zero-confirmations is a GUARD, the progress
    assertion is DEFECT: pre-change, `Image > Scale` had no progress dialog
    at ALL, so this half fails against the unfixed code): below threshold,
    zero confirmations, and the progress indicator IS still shown
    (REQ-CSD-UI-011 is unconditional — no ``minimumDuration`` suppression,
    `plan.md` R-1)."""
    document = _build_document(64, 48, [2, 2])  # tiny, well under threshold
    target = (128, 96)
    assert projected_peak_bytes(document, *target) <= DOCUMENT_TRANSFORM_CONFIRM_BYTES

    confirms = _spy_init(monkeypatch, Document_Transform_Confirm_Dialog, qtbot)
    progresses = _spy_init(monkeypatch, Document_Transform_Progress_Dialog, qtbot)

    result = run_document_transform(
        document, lambda buf: scale_nearest(buf, *target), *target, "Scale Canvas"
    )

    assert confirms == []  # GUARD half: zero confirmations, as always
    assert len(progresses) == 1  # DEFECT half: the progress dialog now exists
    assert result is not None


@pytest.mark.timeout(30)
def test_sc_csd_u013_3_cancelling_does_not_represent_confirmation(qtbot, monkeypatch):
    """SC-CSD-U013-3 (DEFECT): after accepting the confirmation once,
    cancelling the progress run does NOT re-present the confirmation, and
    does not ask the user to confirm the cancellation.

    Cancels at the very first ``stepped`` signal to keep the real-buffer
    cost to one 8K resample (~130 MiB) rather than completing all 5.
    """
    document = _build_document(8, 8, [5])
    target = (MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    assert projected_peak_bytes(document, *target) > DOCUMENT_TRANSFORM_CONFIRM_BYTES

    confirms = _spy_init(monkeypatch, Document_Transform_Confirm_Dialog, qtbot)
    monkeypatch.setattr(
        Document_Transform_Confirm_Dialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    error_calls = _fail_on_message_box(monkeypatch)

    runner = Document_Transform_Runner()

    def _on_stepped(value: int) -> None:
        runner.cancel()

    runner.stepped.connect(_on_stepped)
    result = runner.run(
        document, lambda buf: scale_nearest(buf, *target), *target, "Scale Canvas"
    )

    assert len(confirms) == 1  # never re-presented
    assert result is None  # the run was cancelled
    assert error_calls == []  # no "confirm the cancellation" dialog either


# -- hazard coverage: an error mid-run surfaces, never hangs -----------------


@pytest.mark.timeout(15)
def test_error_inside_a_step_surfaces_synchronously_not_a_hang(qtbot):
    """A ``TransformError`` raised INSIDE the timer-tick callback (a Python
    exception raised from a Qt slot invoked off ``QTimer.singleShot``, which
    does NOT propagate through the nested ``QEventLoop.exec()`` on its own —
    see ``document_transform_runner.py``'s own comment on this exact hazard,
    found and hardened by AGT-05 during this batch) is caught, stashed, and
    RE-RAISED synchronously to the caller once the loop quits — never left to
    hang the modal loop forever. ``@pytest.mark.timeout(15)`` is a deliberate
    safety net: if a regression removed the stash/re-raise, this test would
    otherwise hang the whole run indefinitely rather than fail cleanly.
    """
    document = _build_document(64, 48, [2, 2])

    def fn(buf: PixelBuffer) -> PixelBuffer:
        raise TransformError("synthetic failure for the hazard test")

    runner = Document_Transform_Runner()
    with pytest.raises(TransformError, match="synthetic failure"):
        runner.run(document, fn, 128, 96, "Scale Canvas")
    # The document is untouched -- the failing buffer was never committed.
    for layer in _all_layers(document):
        assert (layer.buffer.width, layer.buffer.height) == (64, 48)


# -- T20: SC-CSD-U012-3, the ONE post-change-only proof in this batch --------


@pytest.mark.timeout(30)
def test_sc_csd_u012_3_no_layer_mutated_before_every_buffer_resampled(qtbot):
    """SC-CSD-U012-3 (DEFECT — the batch's ONLY post-change proof, T20).

    Against the UNFIXED code this scenario PASSES for the wrong reason: the
    old single-buffer swap is atomic by accident (there is only ever one
    buffer to swap), so a pre-change run of an equivalent assertion proves
    nothing and is not recorded as one (`tasks.md` T20, `spec.md` §0). This
    test can only meaningfully run against the NEW multi-buffer pipeline
    (``pixelart_creator.ui.document_transform_runner`` did not exist before
    this batch), where "no layer is mutated before every buffer is
    resampled" is a claim with SIX buffers to be wrong about.

    Samples every layer's buffer identity at EVERY ``stepped`` signal
    (progress values 1..6): every one of those six samples must show every
    buffer still original. The command :func:`Document_Transform_Runner.run`
    returns is UNAPPLIED (`plan.md` §5.2 step 7) — the actual commit happens
    only when the caller calls ``command.execute()`` (exactly what pushing it
    onto a real undo stack does), so "only after the final step do all 6
    change together" is asserted by that explicit call, immediately after
    which every one of the six differs from its original, together.
    """
    document = _build_document(64, 48, [2, 2, 2])  # 6 buffers
    originals = [ly.buffer for ly in _all_layers(document)]

    samples: List[List[bool]] = []
    runner = Document_Transform_Runner()

    def _on_stepped(_value: int) -> None:
        layers = _all_layers(document)
        samples.append([layer.buffer is orig for layer, orig in zip(layers, originals)])

    runner.stepped.connect(_on_stepped)
    command = runner.run(
        document, lambda buf: scale_nearest(buf, 256, 192), 256, 192, "Scale Canvas"
    )

    assert command is not None
    assert len(samples) == 6  # one sample per buffer, progress values 1..6
    for sample in samples:
        assert all(sample), "a layer changed before every buffer had resampled"

    # Nothing has changed yet -- the command is still unapplied.
    for layer, orig in zip(_all_layers(document), originals):
        assert layer.buffer is orig

    command.execute()  # what QUndoStack.push()'s first redo() does

    for layer, orig in zip(_all_layers(document), originals):
        assert layer.buffer is not orig  # all six changed, together, only now


# -- T27: accessibility + both-theme verification of the new dialogs --------
#
# Both dialogs run under both themes automatically (the autouse `theme`
# fixture in conftest.py). This section adds the Article V.1/V.3 assertions
# the spec itself does not name (`plan.md` §8.1, `analysis.md` F-7): a11y is
# report-and-verify -- any finding routes to AGT-05, never fixed here.
#
# A static scan was also run over the two new modules this session:
#   python scripts/a11y_scan.py --root fix-canvas-grid-semantics/pixelart_creator/ui
# 2 findings total, BOTH in ui/vanishing_point_dialog.py (pre-existing,
# unrelated to this batch); ZERO findings in document_transform_dialogs.py.


def test_req_a11y_confirm_dialog_widgets_are_named(qtbot):
    """Every interactive widget in the confirm dialog carries a non-empty
    accessible name (Article V.1)."""
    dialog = Document_Transform_Confirm_Dialog("Scale Canvas", 600_000_000, 7680, 4320)
    qtbot.addWidget(dialog)
    assert dialog.accessibleName() != ""
    assert dialog._proceed.accessibleName() != ""
    assert dialog._decline.accessibleName() != ""
    assert dialog._message.accessibleName() != ""


def test_req_a11y_progress_dialog_widgets_are_named(qtbot):
    """Every interactive widget in the progress dialog carries a non-empty
    accessible name (Article V.1)."""
    dialog = Document_Transform_Progress_Dialog("Scale Canvas", 7)
    qtbot.addWidget(dialog)
    assert dialog.accessibleName() != ""
    assert dialog._cancel_button.accessibleName() != ""
    assert dialog._bar.accessibleName() != ""
    assert dialog._info.accessibleName() != ""


def test_req_a11y_confirm_dialog_buttons_keyboard_reachable(qtbot):
    """Proceed/decline are keyboard-focusable (Qt StrongFocus, the default
    QPushButton policy) -- reachable by keyboard, not mouse-only."""
    from PySide6.QtCore import Qt

    dialog = Document_Transform_Confirm_Dialog("Scale Canvas", 600_000_000, 7680, 4320)
    qtbot.addWidget(dialog)
    assert dialog._proceed.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert dialog._decline.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_req_a11y_progress_dialog_cancel_keyboard_reachable_and_focused(qtbot):
    """The cancel control is keyboard-focusable and IS the initial focus
    target (visible focus indicator's starting point, Article V.3): the shown
    dialog's ``focusWidget()`` is the cancel button, so a screen-reader/keyboard
    user lands on the one live control immediately."""
    from PySide6.QtCore import Qt

    dialog = Document_Transform_Progress_Dialog("Scale Canvas", 7)
    qtbot.addWidget(dialog)
    assert dialog._cancel_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    dialog.show()
    qtbot.waitExposed(dialog)
    assert dialog.focusWidget() is dialog._cancel_button


def test_req_a11y_global_focus_ring_covers_the_new_dialogs(qtbot):
    """A visible focus indicator is themed once, globally, by role (the same
    ``:focus`` QSS rule ``test_a11y_theme.py`` already verifies) -- neither
    new dialog overrides it with a local, hard-coded stylesheet, so both
    inherit the same themed, visible focus ring in either theme."""
    confirm = Document_Transform_Confirm_Dialog("Scale Canvas", 600_000_000, 7680, 4320)
    progress = Document_Transform_Progress_Dialog("Scale Canvas", 7)
    qtbot.addWidget(confirm)
    qtbot.addWidget(progress)
    assert confirm.styleSheet() == ""  # no local override -- theme roles only
    assert progress.styleSheet() == ""
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss


def test_req_a11y_dialogs_render_under_the_active_theme(qtbot, theme):
    """Both dialogs pick up the active application-wide theme (both themes,
    via the autouse ``theme`` fixture) rather than rendering unstyled."""
    confirm = Document_Transform_Confirm_Dialog("Scale Canvas", 600_000_000, 7680, 4320)
    progress = Document_Transform_Progress_Dialog("Scale Canvas", 7)
    qtbot.addWidget(confirm)
    qtbot.addWidget(progress)
    assert QApplication.instance().styleSheet() != ""
    # Neither dialog hard-codes a colour of its own (module docstring
    # contract) -- both simply inherit the app-wide role-based QSS.
    assert confirm.styleSheet() == ""
    assert progress.styleSheet() == ""
