"""D-06 acceptance: per-target automation progress reaching the panel bars
(REQ-P8-UI-011, ``automation_worker`` + the four panel ``QProgressBar``s).

Drives the real fake/test-worker seam the module docstring names — construct
:class:`Automation_Worker` directly and call ``.run()`` synchronously — so
progress reaches the bar deterministically (per the plan's acceptance bar),
proving the EXACT intra-run sequence quoted in the ac6aaaf9 report: ``(0, N,
"running")`` at run-start, ``(1, N, "running")`` .. ``(N-1, N, "running")`` as
each target but the last completes, then a single ``(N, N, "complete")`` —
never twice for the same index. Also covers the four consuming panels'
``set_target_progress``/retranslate/both-theme behaviour. Both themes via the
autouse ``theme`` fixture.
"""

from __future__ import annotations

import threading

from pixelart_creator.ui.automation_worker import (
    STAGE_COMPLETE,
    STAGE_RUNNING,
    Automation_Worker,
    AutomationWorkerSignals,
    make_dispatch_job,
    make_replay_job,
)
from pixelart_creator.ui.batch_recolour_panel import Batch_Recolour_Panel
from pixelart_creator.ui.macro_controls import Macro_Controls
from pixelart_creator.ui.procgen_panel import Procgen_Panel
from pixelart_creator.ui.script_runner_panel import Script_Runner_Panel
from tests.ui._automation_helpers import batch_recolour_op, macro_of


def _run_synchronously(job):
    """Drive ``Automation_Worker.run()`` synchronously (the shipped fake-worker
    seam: no ``QThreadPool``, no threads — deterministic, coverage-traceable)."""
    signals = AutomationWorkerSignals()
    events: list = []
    signals.progress.connect(
        lambda token, index, total, stage: events.append((index, total, stage))
    )
    worker = Automation_Worker(1, job, threading.Event(), signals)
    worker.run()
    return events


# --- D-06: the exact intra-run sequence, both entry points ------------------- #


def test_d06_dispatch_progress_sequence_is_exact_for_a_3_op_run(make_document):
    """D-06: script/batch-recolour/procgen dispatch path — the exact quoted
    sequence for N=3: (0,3,running) (1,3,running) (2,3,running) (3,3,complete),
    each index appearing exactly once."""
    doc = make_document(16, 16)
    ops = [batch_recolour_op(), batch_recolour_op(), batch_recolour_op()]
    job = make_dispatch_job(doc, ops)

    events = _run_synchronously(job)

    assert events == [
        (0, 3, STAGE_RUNNING),
        (1, 3, STAGE_RUNNING),
        (2, 3, STAGE_RUNNING),
        (3, 3, STAGE_COMPLETE),
    ]


def test_d06_replay_progress_sequence_is_exact_for_a_2_op_macro(make_document):
    """D-06: macro replay path — the same exact-sequence shape, N=2."""
    doc = make_document(16, 16)
    macro = macro_of(batch_recolour_op(), batch_recolour_op())
    job = make_replay_job(doc, macro)

    events = _run_synchronously(job)

    assert events == [
        (0, 2, STAGE_RUNNING),
        (1, 2, STAGE_RUNNING),
        (2, 2, STAGE_COMPLETE),
    ]


def test_d06_single_target_run_collapses_to_the_two_boundary_ticks(make_document):
    """D-06: N=1 collapses to exactly the run-start + run-complete pair — no
    intra-run tick fires (there is no target strictly before the last)."""
    doc = make_document(16, 16)
    job = make_dispatch_job(doc, [batch_recolour_op()])

    events = _run_synchronously(job)

    assert events == [(0, 1, STAGE_RUNNING), (1, 1, STAGE_COMPLETE)]


def test_d06_a_test_double_job_with_no_target_count_still_reports_one_target(
    make_document,
):
    """D-06: a bare job (no ``_CountedJob``/``target_count``) — the documented
    ``getattr(..., 'target_count', 1)`` fallback degrades safely."""

    def bare_job(cancel):
        from pixelart_creator.logic.history import GroupCommand

        return GroupCommand([], label="bare")

    events = _run_synchronously(bare_job)

    assert events == [(0, 1, STAGE_RUNNING), (1, 1, STAGE_COMPLETE)]


def test_d06_no_intra_run_tick_ever_repeats_the_final_index(make_document):
    """D-06: reconciliation — the on_target closure never re-emits at
    index == total (that would double-report the last target)."""
    doc = make_document(16, 16)
    ops = [batch_recolour_op() for _ in range(4)]
    job = make_dispatch_job(doc, ops)

    events = _run_synchronously(job)

    indices = [index for index, _total, _stage in events]
    assert indices == [0, 1, 2, 3, 4]  # every index exactly once, in order
    assert events[-1] == (4, 4, STAGE_COMPLETE)
    assert events.count((4, 4, STAGE_RUNNING)) == 0  # never duplicated


# --- D-06: panel-side reaction (deterministic, no threads) ------------------- #


def _assert_panel_reacts(qtbot, panel):
    qtbot.addWidget(panel)
    panel.set_target_progress(0, 3, STAGE_RUNNING)
    assert panel._progress_bar.minimum() == 0
    assert panel._progress_bar.maximum() == 3
    assert panel._progress_bar.value() == 0

    panel.set_target_progress(2, 3, STAGE_RUNNING)
    assert panel._progress_bar.value() == 2

    panel.set_target_progress(3, 3, STAGE_COMPLETE)
    assert panel._progress_bar.value() == 3

    panel.set_busy(False)
    assert panel._progress_bar.value() == 0
    assert panel._progress_bar.maximum() == 1


def test_d06_batch_recolour_panel_progress_bar_reacts(qtbot):
    _assert_panel_reacts(qtbot, Batch_Recolour_Panel())


def test_d06_procgen_panel_progress_bar_reacts(qtbot):
    _assert_panel_reacts(qtbot, Procgen_Panel())


def test_d06_macro_controls_progress_bar_reacts(qtbot):
    _assert_panel_reacts(qtbot, Macro_Controls())


def test_d06_script_runner_panel_progress_bar_reacts(qtbot):
    _assert_panel_reacts(qtbot, Script_Runner_Panel())


# --- D-06: retranslate + a11y, both themes (the autouse theme fixture) ------ #


def test_d06_progress_group_has_accessible_name_and_retranslates(qtbot):
    from PySide6.QtCore import QEvent

    panel = Batch_Recolour_Panel()
    qtbot.addWidget(panel)
    assert panel._progress_bar.accessibleName() != ""

    before = panel._progress_bar.accessibleName()
    panel.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert panel._progress_bar.accessibleName() == before  # stable/idempotent (en)


def test_d06_progress_group_inherits_role_based_theme_colours(qtbot):
    """D-06: no widget-level hard-coded colour — the bar inherits the same
    generic background/text role pair as the rest of the panel in both themes."""
    panel = Batch_Recolour_Panel()
    qtbot.addWidget(panel)
    assert panel._progress_bar.styleSheet() == ""  # no ad-hoc per-widget QSS
