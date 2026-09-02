"""Tests for ``ui/commands.py``'s branch-recording bridge (``REQ-P10-UI-025``).

Covers the recording-bind guards added for Phase-10 Slice C:

* ``PaintCommand``/``LogicCommand.bind_recording`` — a post-construction,
  **no-clobber** bind (``ui/canvas_view.py``'s ``_RecordingUndoStack`` calls it
  on every push). A double-bind must never silently overwrite an already-bound
  sink, and a first bind must actually take effect — exactly the two guard
  paths where a missing/duplicate bind would hide a real edit from a merge.
* ``_fire_record_trace``'s undo-direction contract: an undo **appends** the
  inverse trace, it never pops the forward entry (the branch op-log is
  append-only, last-writer-wins, plan §3.3) — and it refuses loudly
  (``ValueError``, Article II) rather than guessing an inverse when no live
  document was supplied.
* The optional ``invalidate`` cache-safety hook: ``PaintCommand.redo()``/
  ``undo()`` still repaint correctly when it is ``None`` (the documented
  default for a non-composited target, ``ui/tools/base.py``).

``ui/commands.py`` is the sole Qt-aware undo bridge (Article I / S11). Its
base ``redo()``/``undo()``/no-recording-attached behaviour is already
exercised indirectly by the wider ``testing/suites/ui`` suite (no dedicated
``test_commands*.py`` existed before this file) — only the NEW recording-guard
branches this slice added are covered here, not a re-test of the bridge.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import pytest
from PySide6.QtCore import QRectF

from pixelart_creator.logic.edit_trace import EditTrace, MetadataTrace
from pixelart_creator.logic.history import Command
from pixelart_creator.ui.commands import LogicCommand, PaintCommand


class _FakeCommand(Command):
    """A minimal reversible command reporting a fixed, controllable trace.

    ``on_undo`` (no args), if given, runs *inside* :meth:`undo` — lets a test
    mutate the live document to the "prior" state at exactly the point the
    real contract expects it (``ui/commands.py``'s own docstring: the caller
    computes the inverse *after* the command's own ``undo()`` has already
    run).
    """

    label = "fake"

    def __init__(
        self,
        traces: Sequence[EditTrace] = (),
        on_undo: Optional[Sequence] = None,
    ) -> None:
        self._traces = tuple(traces)
        self._on_undo = on_undo
        self.executed = 0
        self.undone = 0

    def execute(self) -> None:
        self.executed += 1

    def undo(self) -> None:
        self.undone += 1
        if self._on_undo is not None:
            self._on_undo()

    def edit_trace(self) -> Tuple[EditTrace, ...]:
        return self._traces


def _recorder():
    """A ``RecordTraceCallback`` stub that remembers every call, in order."""
    calls: List[Tuple[Tuple[EditTrace, ...], bool]] = []

    def _record(traces: Sequence[EditTrace], inverse: bool) -> None:
        calls.append((tuple(traces), inverse))

    return calls, _record


# --------------------------------------------------------------------------- #
# bind_recording — no-clobber, idempotent post-construction bind.             #
# --------------------------------------------------------------------------- #


def test_paint_command_bind_recording_sets_unset_sink(make_document):
    """A first ``bind_recording`` call actually takes effect."""
    doc = make_document()
    trace = (MetadataTrace(key="k", value="v"),)
    calls, record = _recorder()
    cmd = PaintCommand(_FakeCommand(trace), lambda rect: None, QRectF(0, 0, 1, 1))
    cmd.bind_recording(record, doc)
    cmd.redo()
    assert calls == [(trace, False)]


def test_paint_command_bind_recording_is_idempotent(make_document):
    """A second bind never overwrites an already-bound sink (no silent clobber).

    This is exactly the guard the coverage gap named: a re-bind (e.g. a second
    tool push routed through the same ``_RecordingUndoStack``, or a stray
    double call) must not silently swap which branch/document an edit is
    attributed to.
    """
    trace = (MetadataTrace(key="k", value="v"),)
    first_calls, first_record = _recorder()
    second_calls, second_record = _recorder()
    cmd = PaintCommand(_FakeCommand(trace), lambda rect: None, QRectF(0, 0, 1, 1))
    cmd.bind_recording(first_record, make_document())
    cmd.bind_recording(second_record, make_document())  # must be a no-op
    cmd.redo()
    assert first_calls == [(trace, False)]
    assert second_calls == []


def test_logic_command_bind_recording_sets_unset_sink(make_document):
    """Same no-clobber contract on ``LogicCommand`` (every subclass inherits it)."""
    doc = make_document()
    trace = (MetadataTrace(key="k", value="v"),)
    calls, record = _recorder()
    cmd = LogicCommand(_FakeCommand(trace), lambda: None)
    cmd.bind_recording(record, doc)
    cmd.redo()
    assert calls == [(trace, False)]


def test_logic_command_bind_recording_is_idempotent(make_document):
    trace = (MetadataTrace(key="k", value="v"),)
    first_calls, first_record = _recorder()
    second_calls, second_record = _recorder()
    cmd = LogicCommand(_FakeCommand(trace), lambda: None)
    cmd.bind_recording(first_record, make_document())
    cmd.bind_recording(second_record, make_document())
    cmd.redo()
    assert first_calls == [(trace, False)]
    assert second_calls == []


def test_bind_recording_construction_time_value_is_never_overwritten(make_document):
    """A sink supplied AT CONSTRUCTION time also wins over a later bind call."""
    doc = make_document()
    trace = (MetadataTrace(key="k", value="v"),)
    ctor_calls, ctor_record = _recorder()
    later_calls, later_record = _recorder()
    cmd = LogicCommand(
        _FakeCommand(trace), lambda: None, record_trace=ctor_record, document=doc
    )
    cmd.bind_recording(later_record, make_document())
    cmd.redo()
    assert ctor_calls == [(trace, False)]
    assert later_calls == []


# --------------------------------------------------------------------------- #
# Undo direction: append the inverse, never pop the forward entry.            #
# --------------------------------------------------------------------------- #


def test_undo_appends_the_inverse_trace_never_pops_the_forward_entry(make_document):
    """An undo APPENDS the inverse trace; the forward entry is never removed.

    The branch op-log is append-only, last-writer-wins (plan §3.3) — getting
    this backwards (popping instead of appending) would silently corrupt a
    later merge, so this asserts the inverse was RECORDED, never that the log
    shrank.
    """
    doc = make_document()
    doc.metadata["k"] = "new"
    forward = (MetadataTrace(key="k", value="new"),)

    def _on_undo() -> None:
        # Simulate the wrapped command's own undo() reverting the live
        # document BEFORE the inverse is computed — ui/commands.py's own
        # documented ordering (_fire_record_trace's docstring).
        doc.metadata["k"] = "old"

    calls, record = _recorder()
    cmd = LogicCommand(
        _FakeCommand(forward, on_undo=_on_undo),
        lambda: None,
        record_trace=record,
        document=doc,
    )
    cmd.redo()
    cmd.undo()

    assert len(calls) == 2, "the forward entry must still be present (append-only)"
    fwd_traces, fwd_inverse = calls[0]
    inv_traces, inv_inverse = calls[1]
    assert fwd_inverse is False
    assert inv_inverse is True
    assert fwd_traces[0].value == "new"
    assert inv_traces[0].value == "old"  # the PRIOR value, read post-undo


def test_paint_command_undo_direction_also_appends(make_document):
    """The same append-not-pop contract holds on ``PaintCommand`` (undo bridge #1)."""
    doc = make_document()
    doc.metadata["k"] = "new"
    forward = (MetadataTrace(key="k", value="new"),)

    def _on_undo() -> None:
        doc.metadata["k"] = "old"

    calls, record = _recorder()
    cmd = PaintCommand(
        _FakeCommand(forward, on_undo=_on_undo),
        lambda rect: None,
        QRectF(0, 0, 1, 1),
        record_trace=record,
        document=doc,
    )
    cmd.redo()
    cmd.undo()
    assert len(calls) == 2
    assert calls[0][1] is False
    assert calls[1][1] is True
    assert calls[1][0][0].value == "old"


# --------------------------------------------------------------------------- #
# Refusal path: an inverse without a document is a loud failure, never a      #
# guess (Article II).                                                        #
# --------------------------------------------------------------------------- #


def test_paint_command_undo_requires_document_when_recording_attached():
    trace = (MetadataTrace(key="k", value="v"),)
    _calls, record = _recorder()
    cmd = PaintCommand(
        _FakeCommand(trace),
        lambda rect: None,
        QRectF(0, 0, 1, 1),
        record_trace=record,
        document=None,
    )
    cmd.redo()  # the forward direction needs no document
    with pytest.raises(ValueError):
        cmd.undo()


def test_logic_command_undo_requires_document_when_recording_attached():
    trace = (MetadataTrace(key="k", value="v"),)
    _calls, record = _recorder()
    cmd = LogicCommand(
        _FakeCommand(trace), lambda: None, record_trace=record, document=None
    )
    cmd.redo()
    with pytest.raises(ValueError):
        cmd.undo()


# --------------------------------------------------------------------------- #
# The optional invalidate hook: redo()/undo() work with no cache-safety hook. #
# --------------------------------------------------------------------------- #


def test_paint_command_redo_undo_without_invalidate_hook():
    """``invalidate=None`` (the documented default for a non-composited target,
    ``ui/tools/base.py::Stroke.to_command``) still repaints on both redo and undo.
    """
    refreshed: List[QRectF] = []
    cmd = PaintCommand(
        _FakeCommand(()),
        lambda rect: refreshed.append(rect),
        QRectF(0, 0, 1, 1),
        invalidate=None,
    )
    cmd.redo()
    cmd.undo()
    assert len(refreshed) == 2
