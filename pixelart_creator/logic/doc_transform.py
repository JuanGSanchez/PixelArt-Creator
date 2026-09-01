# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Whole-document geometry transform engine (zero Qt, S11).

The four whole-document `Image` operations (Scale, Rotate 90, Flip
Horizontal, Flip Vertical) must resample every layer buffer and every
attached mask across every frame, then move the document's declared
geometry, as a single atomic step — never a partial write (canvas-scale-
defects spec.md REQ-CSD-UI-001/002/006/011/012/015; plan.md §5.2).

This module supplies the pure-Python machinery that makes that atomicity
**structural**: :class:`DocumentTransformRun` accumulates resampled results
ASIDE from the document (:meth:`DocumentTransformRun.step` reads a target's
``source`` buffer and appends the result to an internal list — it never
reads or writes a :class:`~pixelart_creator.logic.document.Layer`
attribute), and :func:`make_document_transform_command` is the only code
that ever assigns ``Layer.buffer`` / ``Layer.mask`` / ``Document.width`` /
``Document.height``, and only once every buffer has resampled. The Qt
orchestration (progress dialog, cancel handling, one-buffer-per-tick
stepping) lives in ``ui/document_transform_runner.py``; this module knows
nothing of Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

from pixelart_creator.logic import history
from pixelart_creator.logic.document import Document, Layer, iter_layers
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

#: RGBA channel count — format-intrinsic, not a tuning value (Article II
#: exemption for algorithm-intrinsic literals, the ``blend.py`` precedent).
_RGBA_CHANNELS = 4

#: Indexed-mode channel count (one palette-index byte per pixel).
_INDEXED_CHANNELS = 1


class DocTransformError(ValueError):
    """Raised when a :class:`DocumentTransformRun` is used out of sequence."""


@dataclass(frozen=True)
class TransformTarget:
    """One buffer to resample, plus the holder attribute it commits into.

    ``source`` is a strong reference to the buffer as it stood at
    enumeration time — this is the "retained sources" term
    :func:`projected_peak_bytes` costs and the object
    :func:`make_document_transform_command`'s undo restores byte-exactly.
    """

    #: The :class:`~pixelart_creator.logic.document.Layer` this target
    #: commits into. Never read or written by :meth:`DocumentTransformRun.step`.
    holder: Layer
    #: The attribute on ``holder`` to swap at commit: ``"buffer"`` or ``"mask"``.
    attribute: str
    #: The buffer to resample, as it stood when this target was enumerated.
    source: PixelBuffer


def enumerate_targets(document: Document) -> List[TransformTarget]:
    """Enumerate every buffer a whole-document transform must resample.

    Per frame, per :func:`~pixelart_creator.logic.document.iter_layers` walk
    (the same public walk ``ui/commands.py``'s ``CanvasResizeCommand`` uses,
    so nested group leaves are included), emits the layer's ``buffer``
    target, then its ``mask`` target when ``layer.mask is not None``.
    **This order is the contract**: it is the progress order a stepping run
    reports and the order results are committed in.
    """
    targets: List[TransformTarget] = []
    for frame in document.frames:
        for layer in iter_layers(frame.layers):
            targets.append(TransformTarget(layer, "buffer", layer.buffer))
            if layer.mask is not None:
                targets.append(TransformTarget(layer, "mask", layer.mask))
    return targets


def _channels(mode: ColorMode) -> int:
    """Return the per-pixel byte width of ``mode`` (RGBA=4, indexed=1)."""
    return _RGBA_CHANNELS if mode is ColorMode.RGBA else _INDEXED_CHANNELS


def projected_peak_bytes(
    document: Document, result_width: int, result_height: int
) -> int:
    """Return the projected peak byte cost of a whole-document transform.

    Sums, over every target :func:`enumerate_targets` would emit, the size
    of its resampled **result** (``result_width`` x ``result_height`` at
    that buffer's own channel width) plus the size of its retained
    **source** — the undo snapshot :func:`make_document_transform_command`
    holds. Read per target from that buffer's own
    :class:`~pixelart_creator.logic.pixel_buffer.ColorMode`, so a mask in a
    different mode from its layer is costed correctly.

    Note the corrected formula: ``Σ(result bytes) + Σ(source bytes)`` — the
    "results ≈ sources" shorthand only holds for the three area-preserving
    members of the family (Rotate 90, Flip H, Flip V); Scale is not
    area-preserving and must not be approximated this way.
    """
    total = 0
    for target in enumerate_targets(document):
        source = target.source
        channels = _channels(source.mode)
        total += result_width * result_height * channels
        total += source.width * source.height * channels
    return total


class DocumentTransformRun:
    """A bounded, cancellable, stepwise resample of every enumerated target.

    Results accumulate **aside** from the document: :meth:`step` reads
    ``target.source`` and appends the transformed buffer to an internal
    list. It never names or touches a
    :class:`~pixelart_creator.logic.document.Layer`. This is what makes
    "nothing reached the undo stack" true by construction on cancellation —
    no :class:`~pixelart_creator.logic.history.Command` is ever built from a
    run that has not run every step (REQ-CSD-UI-012).
    """

    __slots__ = ("_targets", "_results")

    def __init__(self, targets: List[TransformTarget]) -> None:
        """Create a run over ``targets``, usually :func:`enumerate_targets`'s output."""
        self._targets: List[TransformTarget] = list(targets)
        self._results: List[PixelBuffer] = []

    @property
    def targets(self) -> Tuple[TransformTarget, ...]:
        """The enumerated targets, in progress order."""
        return tuple(self._targets)

    @property
    def total(self) -> int:
        """The number of targets — the progress-bar maximum (REQ-CSD-UI-011)."""
        return len(self._targets)

    @property
    def done(self) -> int:
        """The number of targets resampled so far — the progress-bar value."""
        return len(self._results)

    @property
    def finished(self) -> bool:
        """Whether every target has been resampled (``done == total``)."""
        return self.done == self.total

    def results(self) -> Tuple[PixelBuffer, ...]:
        """Return the resampled buffers accumulated so far, in target order."""
        return tuple(self._results)

    def step(self, transform: Callable[[PixelBuffer], PixelBuffer]) -> PixelBuffer:
        """Resample the next target's source buffer and record the result.

        Reads only ``self.targets[self.done].source``; appends the result to
        the internal results list and advances ``done`` by one. **Never
        reads or writes a**
        :class:`~pixelart_creator.logic.document.Layer` **attribute** — that
        is the structural half of the atomicity guarantee this module exists
        to provide.

        Raises:
            DocTransformError: If the run is already :attr:`finished`.
        """
        if self.finished:
            raise DocTransformError("DocumentTransformRun is already finished")
        target = self._targets[self.done]
        result = transform(target.source)
        self._results.append(result)
        return result


def make_document_transform_command(
    document: Document,
    run: DocumentTransformRun,
    new_width: int,
    new_height: int,
    label: str = "transform",
) -> history.Command:
    """Build the single reversible commit for a finished :class:`DocumentTransformRun`.

    Returns an **unapplied** :class:`~pixelart_creator.logic.history.FunctionCommand`
    (push it with ``execute=True``) — nothing is committed by this call
    itself. Its ``execute`` assigns every ``holder.<attribute>`` from
    ``run.results()``, then ``document.width``/``document.height``, then
    invalidates the composite cache of every frame; its ``undo`` restores
    every :class:`TransformTarget`'s retained ``source`` object and the
    prior geometry — byte-exact whichever direction the dimensions moved
    (REQ-CSD-UI-002), for the same reason
    ``CanvasResizeCommand``'s snapshot/restore is.

    Raises:
        DocTransformError: If ``run`` is not :attr:`DocumentTransformRun.finished`
            — a command must never be built from a partial run.
    """
    if not run.finished:
        raise DocTransformError(
            "cannot build a document transform command from an unfinished run"
        )
    targets = run.targets
    results = run.results()
    prior_sources = tuple(target.source for target in targets)
    prior_width, prior_height = document.width, document.height
    frame_count = len(document.frames)

    def _do() -> None:
        for target, result in zip(targets, results):
            setattr(target.holder, target.attribute, result)
        document.width = new_width
        document.height = new_height
        for frame_index in range(frame_count):
            document.invalidate_caches(frame_index=frame_index)

    def _undo() -> None:
        for target, source in zip(targets, prior_sources):
            setattr(target.holder, target.attribute, source)
        document.width = prior_width
        document.height = prior_height
        for frame_index in range(frame_count):
            document.invalidate_caches(frame_index=frame_index)

    return history.FunctionCommand(_do, _undo, label=label)
