"""Art-branching UI acceptance (REQ-P10-UI-012).

Phase-10 Slice C. The user branches the current project, edits a branch independently,
and merges it back — conflict-free, with the outcome surfaced. These tests drive the
``Branching_Session`` seam (over the pure ``logic/realtime_apply`` branch / merge model)
and the ``Branching_Panel`` widget:

* create / switch / merge over the logic model; the conflict-free merged result reflects
  the branch's recorded edits;
* the panel lists branches, enables/disables its controls correctly, and surfaces the
  merge outcome;
* ``Main_Window`` loads a switched/merged branch document into the active tab.

Branching pushes NO ``QUndoCommand`` (PL10-D13). Every test runs under BOTH themes via
the autouse ``theme`` fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QInputDialog

from pixelart_creator.logic.convergence import MetadataOp
from pixelart_creator.logic.edit_trace import MetadataTrace, RasterTrace
from pixelart_creator.logic.realtime_apply import RealtimeError
from pixelart_creator.ui.branching_panel import Branching_Panel, Branching_Session

# --------------------------------------------------------------------------- #
# Branching_Session — over the pure logic model.                                #
# --------------------------------------------------------------------------- #


def test_no_base_document_initially():
    """A fresh session has no base and no branches."""
    session = Branching_Session()
    assert session.has_base() is False
    assert session.branch_names() == ()


def test_set_base_document_creates_mainline(make_document):
    """Setting a base document creates the always-present mainline branch."""
    session = Branching_Session()
    session.set_base_document(make_document())
    assert session.has_base() is True
    assert session.branch_names() == ("mainline",)
    assert session.active_branch() == "mainline"


def test_create_branch_forks_from_mainline(make_document):
    """Creating a feature branch adds it to the branch list."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    assert session.branch_names() == ("mainline", "feature")


def test_switch_emits_materialised_document(qtbot, make_document):
    """Switching to a branch emits its materialised (converged) document."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    with qtbot.waitSignal(session.documentSwitched, timeout=1000) as blocker:
        session.switch_to("feature")
    assert session.active_branch() == "feature"
    # A whole Document is emitted for the caller to load.
    from pixelart_creator.logic.document import Document

    assert isinstance(blocker.args[0], Document)


def test_merge_is_conflict_free_and_reflects_branch_edits(qtbot, make_document):
    """A branch's recorded edit survives a conflict-free merge into mainline."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    session.switch_to("feature")
    # An edit recorded on the active feature branch.
    session.record_on_active((MetadataOp("title", "Branched", 1, 1),))

    with qtbot.waitSignal(session.documentSwitched, timeout=1000) as blocker:
        with qtbot.waitSignal(session.mergeCompleted, timeout=1000):
            session.merge_to_mainline("feature")

    merged = blocker.args[0]
    assert merged.metadata["title"] == "Branched"
    # The feature branch is gone; mainline is active again.
    assert session.branch_names() == ("mainline",)
    assert session.active_branch() == "mainline"


def test_merge_completed_summary_carries_name_and_count(qtbot, make_document):
    """``mergeCompleted`` carries the branch name + edit count for the panel readout."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    session.switch_to("feature")
    session.record_on_active((MetadataOp("k", "v", 1, 1),))
    with qtbot.waitSignal(session.mergeCompleted, timeout=1000) as blocker:
        session.merge_to_mainline("feature")
    assert blocker.args[0] == "feature|1"


def test_create_duplicate_branch_raises(make_document):
    """Creating a branch whose name already exists raises a domain error."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    with pytest.raises(RealtimeError):
        session.create_branch("feature")


def test_create_mainline_named_branch_raises(make_document):
    """A feature branch may not be named 'mainline'."""
    session = Branching_Session()
    session.set_base_document(make_document())
    with pytest.raises(RealtimeError):
        session.create_branch("mainline")


def test_merge_mainline_into_itself_raises(make_document):
    """Merging mainline into itself is rejected."""
    session = Branching_Session()
    session.set_base_document(make_document())
    with pytest.raises(RealtimeError):
        session.merge_to_mainline("mainline")


def test_create_branch_without_base_raises():
    """Branching with no open project raises a domain error."""
    session = Branching_Session()
    with pytest.raises(RealtimeError):
        session.create_branch("feature")


# --------------------------------------------------------------------------- #
# Branching_Panel — presentation over the session.                              #
# --------------------------------------------------------------------------- #


@pytest.fixture
def bound_panel(qtbot, make_document):
    """A ``Branching_Panel`` bound to a session with an open base document."""
    session = Branching_Session()
    session.set_base_document(make_document())
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel.set_session(session)
    return panel, session


def _select(panel: Branching_Panel, name: str) -> None:
    """Select the list row whose (possibly '(active)'-suffixed) text starts with name."""
    for row in range(panel._list.count()):
        item = panel._list.item(row)
        if item.text().startswith(name):
            panel._list.setCurrentItem(item)
            return
    raise AssertionError(f"no branch row for {name!r}")


def test_panel_lists_mainline_when_bound(bound_panel):
    """A bound panel lists the mainline branch."""
    panel, _session = bound_panel
    texts = [panel._list.item(i).text() for i in range(panel._list.count())]
    assert any("mainline" in t for t in texts)


def test_panel_new_button_disabled_without_base(qtbot):
    """The New Branch button is disabled until a base document is set."""
    session = Branching_Session()
    panel = Branching_Panel()
    qtbot.addWidget(panel)
    panel.set_session(session)
    assert panel._new_button.isEnabled() is False


def test_panel_create_branch_via_dialog(bound_panel, monkeypatch):
    """The New Branch action creates a branch through the session (dialog stubbed)."""
    panel, session = bound_panel
    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("feature", True))
    )
    panel._on_new()
    assert "feature" in session.branch_names()


def test_panel_merge_surfaces_conflict_free_outcome(bound_panel):
    """Clicking Merge on a feature branch surfaces the conflict-free outcome text."""
    panel, session = bound_panel
    session.create_branch("feature")
    _select(panel, "feature")
    assert panel._merge_button.isEnabled() is True
    panel._on_merge()
    assert "conflict-free" in panel._outcome.text()
    assert "feature" in panel._outcome.text()


def test_panel_switch_button_enabled_for_selection(bound_panel):
    """Selecting any branch enables Switch; merge stays off for mainline."""
    panel, session = bound_panel
    session.create_branch("feature")
    _select(panel, "mainline")
    assert panel._switch_button.isEnabled() is True
    assert panel._merge_button.isEnabled() is False


def test_panel_retranslates_on_language_change(bound_panel):
    """The panel re-sets its tr() strings on a LanguageChange (F5)."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    panel, _session = bound_panel
    QApplication.sendEvent(panel, QEvent(QEvent.Type.LanguageChange))
    assert panel._new_button.text() != ""
    assert panel._merge_button.text() != ""


# --------------------------------------------------------------------------- #
# Main_Window integration.                                                      #
# --------------------------------------------------------------------------- #


def test_window_loads_switched_branch_document_into_active_tab(qtbot, make_document):
    """``_on_branch_document_switched`` binds a merged/switched doc to the active tab."""
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    new_doc = make_document()
    new_doc.metadata["title"] = "Merged Result"
    win._on_branch_document_switched(new_doc)
    record = win.active_tab()
    assert record.document is new_doc
    assert record.document.metadata["title"] == "Merged Result"


# --------------------------------------------------------------------------- #
# Branching_Session.record_traces (REQ-P10-UI-025) — minting + guards.        #
# --------------------------------------------------------------------------- #


def test_record_traces_noop_on_mainline(make_document):
    """A no-op on the mainline — mainline edits are the base (the UNCHANGED rule
    ``record_on_active`` already makes; this task never touches that method).
    """
    session = Branching_Session()
    session.set_base_document(make_document())
    session.record_traces((MetadataTrace(key="k", value="v"),), False)
    assert session.branch_names() == ("mainline",)  # nothing raised, nothing recorded


def test_record_traces_noop_when_traces_empty(qtbot, make_document):
    """An empty trace sequence records nothing (no phantom op minted)."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    with qtbot.waitSignal(session.documentSwitched, timeout=1000):
        session.switch_to("feature")
    session.record_traces((), False)
    assert session.get_branch("feature").ops == ()


def test_record_traces_mints_and_records_a_metadata_op(qtbot, make_document):
    """The forward path: a trace is minted into a real ``Operation`` (via the
    UNCHANGED ``logic/branch_recording.ops_for_traces``) and appended to the
    active feature branch's op-log.
    """
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    with qtbot.waitSignal(session.documentSwitched, timeout=1000):
        session.switch_to("feature")

    session.record_traces((MetadataTrace(key="title", value="from-trace"),), False)

    feature = session.get_branch("feature")
    assert len(feature.ops) == 1
    assert feature.document().metadata["title"] == "from-trace"


def test_record_traces_records_regardless_of_inverse_flag(qtbot, make_document):
    """``inverse`` only shapes the CALLER's traces (already inverted before the
    call, ``ui/commands.py``); ``record_traces`` mints identically either way.
    """
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    with qtbot.waitSignal(session.documentSwitched, timeout=1000):
        session.switch_to("feature")

    session.record_traces((MetadataTrace(key="title", value="reverted"),), True)

    feature = session.get_branch("feature")
    assert len(feature.ops) == 1
    assert feature.document().metadata["title"] == "reverted"


def test_record_traces_raises_without_a_live_document(qtbot, make_document):
    """Fails loud (never guesses) when no live document is bound (Article II)."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    with qtbot.waitSignal(session.documentSwitched, timeout=1000):
        session.switch_to("feature")
    session._live = None  # simulate a caller bug: recording before a live doc is bound
    with pytest.raises(RealtimeError):
        session.record_traces((MetadataTrace(key="k", value="v"),), False)


def test_record_traces_wraps_a_mapping_failure(qtbot, make_document):
    """An unmappable trace (an unknown layer id) is reported, never swallowed."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    with qtbot.waitSignal(session.documentSwitched, timeout=1000):
        session.switch_to("feature")
    bad_trace = RasterTrace(frame_index=0, layer_id=9999, tile_x=0, tile_y=0)
    with pytest.raises(RealtimeError):
        session.record_traces((bad_trace,), False)


# --------------------------------------------------------------------------- #
# Branching_Session.get_branch — read-only lookup for the diff dialog.       #
# --------------------------------------------------------------------------- #


def test_get_branch_returns_mainline_and_feature(make_document):
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    assert session.get_branch("mainline") is not None
    assert session.get_branch("feature") is not None


def test_get_branch_unknown_name_raises(make_document):
    session = Branching_Session()
    session.set_base_document(make_document())
    with pytest.raises(RealtimeError):
        session.get_branch("does-not-exist")


# --------------------------------------------------------------------------- #
# End-to-end: branch, draw with a tool, merge — the drawn pixel should be     #
# present in mainline (T-DRAW-01, REQ-P10-UI-025's own acceptance scenario).  #
# --------------------------------------------------------------------------- #


def test_drawn_pixel_on_branch_is_present_in_mainline_after_merge(qtbot):
    """Draw a pixel on a feature branch with the (default) pencil tool, merge
    it into mainline, and expect the drawn pixel to be present in the merged
    result — driven through the REAL product wiring (``Main_Window``), not a
    hand-built fixture, so this proves what a user actually gets.
    """
    from pixelart_creator.ui.main_window import Main_Window
    from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

    win = Main_Window()
    qtbot.addWidget(win)
    win.new_document(64, 64)
    record = win.active_tab()
    assert record is not None

    session = win._branching_session
    session.create_branch("feature")
    with qtbot.waitSignal(session.documentSwitched, timeout=1000):
        session.switch_to("feature")

    view = record.view
    prepare_for_click(view)
    paint_color = (10, 20, 30, 255)
    before = record.document.frames[0].layers[0].buffer.get_pixel(5, 5)
    assert before != paint_color
    view.set_active_color(paint_color)
    click_pixel(view, 5, 5)

    # The pixel is visibly drawn on the branch's own live document right now.
    painted = record.document.frames[0].layers[0].buffer.get_pixel(5, 5)
    assert painted == paint_color

    with qtbot.waitSignal(session.documentSwitched, timeout=1000) as blocker:
        session.merge_to_mainline("feature")
    merged = blocker.args[0]
    merged_pixel = merged.frames[0].layers[0].buffer.get_pixel(5, 5)
    assert merged_pixel == paint_color, (
        "the drawn pixel did not survive the merge — the branch's op-log never "
        "recorded it (see ui/canvas_view.py Canvas_View.set_recording, which "
        "ui/main_window.py never calls for any document tab)"
    )
