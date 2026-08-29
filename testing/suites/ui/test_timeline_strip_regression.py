"""Strip regression pin (T19; REQ-P5-UI-021, SC-UI-021-6..8).

Three things this module proves, each with its own scenario id:

- ``SC-UI-021-1..5`` (the evidence bar): the shipped Phase-5 timeline suite —
  ``tests/ui/test_animation_timeline.py`` and
  ``tests/ui/test_animation_timeline_wiring.py`` — passes **unmodified**.
  Verified two ways below: a real subprocess run (so this is not a claim
  taken on faith) AND a ``git diff`` check that the two files are
  byte-identical to the committed HEAD (so "unmodified" is measured, not
  assumed).
- ``SC-UI-021-6``: the strip is unaffected by the grid's existence and use —
  switching to the grid, performing a selection/visibility-toggle/reorder
  there, then switching back, leaves the strip's own signals and undo
  discipline exactly as they were.
- ``SC-UI-021-7``/``SC-UI-021-8``: a real ``qtbot`` mouse-driven press-drag
  across the strip is asserted here as an ongoing regression pin. Per T20's
  measurement (``design-docs/reports/strip-drag-measurement-20260817.md``),
  the strip's left-drag was found to already scrub correctly, so REQ-P5-UI-032
  steps (ii)/(iii) were recorded as **not required** — this test is therefore
  the forward-looking guard that keeps that measured-good state honest, not a
  reversion-proof of a fix (there was no fix to prove; a positive T20 result
  closes T-21 as measured, per the requirement's own text).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.timeline_panel import Timeline_Panel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255), (10, 200, 10, 255)]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHIPPED_FILES = (
    "tests/ui/test_animation_timeline.py",
    "tests/ui/test_animation_timeline_wiring.py",
)


def _make_doc(frames: int = 3) -> Document:
    doc = Document(64, 64, palette=Palette(STARTER))
    for _ in range(frames - 1):
        doc.add_frame()
    return doc


def _make_panel(qtbot, doc: Document):
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(500, 200)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    qtbot.waitExposed(panel)
    return panel, stack


def _item_center(panel: Timeline_Panel, row: int) -> QPoint:
    rect = panel._strip.visualItemRect(panel._strip.item(row))
    return rect.center()


# --------------------------------------------------------------------------- #
# SC-UI-021-1..5 — the shipped suite, unmodified                              #
# --------------------------------------------------------------------------- #


def test_sc_ui_021_1_shipped_files_are_byte_unmodified_at_head(qtbot):
    """The evidence bar's "unmodified" claim, measured via git — not assumed.
    Skips (does not fabricate a pass) if git is unavailable in this
    environment; that is an honest "could not verify", never a silent pass."""
    try:
        result = subprocess.run(
            ["git", "diff", "--stat", "HEAD", "--", *_SHIPPED_FILES],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        import pytest

        pytest.skip(f"could not verify — git unavailable ({exc})")
        return
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", (
        "shipped Phase-5 timeline test files were modified by this slice, "
        f"in violation of REQ-P5-UI-021's evidence bar:\n{result.stdout}"
    )


def test_sc_ui_021_1_shipped_suite_passes(qtbot):
    """A real subprocess run of the two shipped files exits 0 — the actual
    runner's own totals line is what this test depends on, not a summary."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *_SHIPPED_FILES,
            "-q",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        env={
            **__import__("os").environ,
            "QT_QPA_PLATFORM": "offscreen",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout, result.stdout


# --------------------------------------------------------------------------- #
# SC-UI-021-6 — the strip is unaffected by the grid's existence and use       #
# --------------------------------------------------------------------------- #


def test_sc_ui_021_6_strip_unaffected_by_grid_existence_and_use(qtbot):
    """Switching to the grid, selecting/toggling/reordering there, then
    switching back, leaves the strip's own scrub/selection/undo behaviour
    exactly as it was."""
    doc = _make_doc(3)
    panel, stack = _make_panel(qtbot, doc)

    # Baseline: strip selection pushes no command.
    frame_events = []
    panel.frameSelected.connect(frame_events.append)
    panel.select_frame(1)
    baseline_count = stack.count()

    # Switch to grid; perform a selection, a visibility toggle and a reorder.
    panel._grid_toggle_action.setChecked(True)
    grid = panel._grid
    outline = doc.add_layer("Outline", frame_index=1)
    grid.rebuild()
    from pixelart_creator.logic.track_table import track_table

    table = track_table(doc, active_frame=1)
    row = next(i for i, r in enumerate(table.rows) if r.layer_id == outline.layer_id)
    grid.model().setData(
        grid.model().index(row, 1),
        Qt.CheckState.Unchecked.value,
        Qt.ItemDataRole.CheckStateRole,
    )
    assert stack.count() == baseline_count + 1  # the toggle's own command

    header = grid.horizontalHeader()
    start = QPoint(
        header.sectionViewportPosition(2) + header.sectionSize(2) // 2,
        header.height() // 2,
    )
    end = QPoint(header.sectionViewportPosition(0) + 2, header.height() // 2)
    qtbot.mousePress(header.viewport(), Qt.MouseButton.LeftButton, pos=start)
    for i in range(1, 6):
        pos = QPoint(
            start.x() + (end.x() - start.x()) * i // 5,
            start.y() + (end.y() - start.y()) * i // 5,
        )
        qtbot.mouseMove(header.viewport(), pos=pos)
    qtbot.mouseRelease(header.viewport(), Qt.MouseButton.LeftButton, pos=end)

    # Switch back to the strip.
    panel._grid_toggle_action.setChecked(False)

    # The strip's own behaviour: selection still pushes no command, scrub
    # still reaches the hovered frame.
    before_strip_ops = stack.count()
    panel.select_frame(0)
    assert stack.count() == before_strip_ops  # selection never pushes

    scrub_events = []
    panel.frameScrubbed.connect(scrub_events.append)
    viewport = panel._strip.viewport()
    s = _item_center(panel, 0)
    e = _item_center(panel, len(doc.frames) - 1)
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=s)
    qtbot.mouseMove(viewport, pos=QPoint((s.x() + e.x()) // 2, s.y()))
    qtbot.mouseMove(viewport, pos=e)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=e)

    assert scrub_events and scrub_events[-1] == len(doc.frames) - 1
    assert stack.count() == before_strip_ops  # scrub never pushes either


# --------------------------------------------------------------------------- #
# SC-UI-021-7 / SC-UI-021-8 — the real-drag measurement, pinned forward       #
# --------------------------------------------------------------------------- #


def test_sc_ui_021_7_and_8_real_mouse_drag_scrubs_and_is_recorded(qtbot):
    """A real qtbot press-move-release across the strip body scrubs (reaches
    each frame under the cursor) and pushes no command — the SAME measurement
    T20 recorded (design-docs/reports/strip-drag-measurement-20260817.md).
    T20 found this ALREADY correct (no defect), so REQ-P5-UI-032 steps
    (ii)/(iii) were not required; this test is the forward regression pin
    that keeps that finding true, not a reversion-proof of a fix that was
    never applied."""
    doc = _make_doc(4)
    panel, stack = _make_panel(qtbot, doc)
    before = stack.count()

    scrub_events = []
    panel.frameScrubbed.connect(scrub_events.append)

    viewport = panel._strip.viewport()
    start = _item_center(panel, 0)
    end = _item_center(panel, 3)
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    for i in range(1, 7):
        pos = QPoint(
            start.x() + (end.x() - start.x()) * i // 6,
            start.y() + (end.y() - start.y()) * i // 6,
        )
        qtbot.mouseMove(viewport, pos=pos)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)

    assert scrub_events == [1, 2, 3]
    assert stack.count() == before
