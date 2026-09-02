"""Tests for ``ui/branch_diff_dialog.py`` (``REQ-P10-UI-015..019``, ``-021..026``).

``Branch_Diff_Dialog`` is a **modeless** pre-merge diff view: it computes the
divergence (``logic/branch_diff.derive_divergence``) and the supervision
verdict (``logic/branch_diff.supervise``) exactly once, at construction, then
only *formats* the already-computed results (Article I — it invents nothing).
These tests build real :class:`~pixelart_creator.logic.realtime_apply.Branch`
objects with real ``logic/convergence`` operations and independently compute
the expected op/region/supervision counts, so a passing assertion proves the
dialog *read* what the recording produced rather than merely not crashing.

Covered here (REQ-IDs from the module docstring):

* -015/-016: source vs. target basis, the four op-tier groups in fixed order.
* -017/-024: the two-tier divergence + supervision are computed ONCE, at
  construction (proven by asserting the rendered counts match independently
  computed values — no re-derivation hook exists to call twice).
* -018/-019: the view is read-only with exactly two exits — Close (button,
  Escape, window-close all reject()) and Continue to Merge (hands off to the
  caller, which runs the **unchanged** ``Branching_Session.merge_to_mainline``
  — proven via the ``Main_Window`` wiring, not re-implemented here).
* -021: every control carries an accessible name.
* -022: the supervision warning is carried by wording/bold, never colour-only
  (implicit — no colour is ever set on any widget in this module).
* -023: ``changeEvent`` retranslates on ``QEvent.LanguageChange``.
* -025/-026: the supervision detail names every located category (frames,
  layers, attributes, metadata keys, tiles).
* The region granularity is STATED (whole ``CRDT_TILE_SIZE_PX`` tile, never
  merely implied by opening the dialog).
* Refusal/cancel paths: no active tab, and an unknown branch name.

Both light and dark themes are covered by the autouse ``theme`` fixture
(``testing/suites/ui/conftest.py``).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QDialog

from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.convergence import (
    LayerAttrOp,
    LayerOrderOp,
    MetadataOp,
    RasterOp,
)
from pixelart_creator.logic.realtime_apply import branch
from pixelart_creator.ui.branch_diff_dialog import Branch_Diff_Dialog
from pixelart_creator.ui.main_window import Main_Window

_TILE = CRDT_TILE_SIZE_PX


def _solid_tile(value: int) -> bytes:
    return bytes([value]) * (_TILE * _TILE * 4)


# --------------------------------------------------------------------------- #
# Empty-diff case: identical branch, fully accounted.                         #
# --------------------------------------------------------------------------- #


def test_identical_branch_reports_no_changes(qtbot, make_document):
    """``REQ-P10-UI-017``/``SC-L008-5``: a source identical to its target reports
    both tiers empty, never raises, and STATES that there is nothing to merge.
    """
    base = make_document()
    mainline = branch(base, site_id=0)
    source = branch(base, site_id=1)
    live = source.document()

    dialog = Branch_Diff_Dialog("feature", "mainline", source, mainline, live)
    qtbot.addWidget(dialog)
    dialog.show()

    # Modeless by construction (never a dock, never application-modal).
    assert dialog.isModal() is False
    assert dialog.windowModality() == Qt.WindowModality.NonModal

    assert dialog.accessibleName() != ""
    assert "no changes" in dialog._identical_label.text().lower()
    assert dialog._identical_label.isVisible() is True
    assert "checked" in dialog._supervision_label.text().lower()

    for _box, count_label, list_widget in dialog._groups.values():
        assert list_widget.count() == 0
        assert "no changes" in count_label.text().lower()
    assert dialog._region_list.count() == 0
    assert "0 operation" in dialog._total_label.text()


def test_region_granularity_is_stated_not_implied(qtbot, make_document):
    """The whole-tile granularity is STATED in the view, not merely implicit.

    Region granularity is settled as the whole ``CRDT_TILE_SIZE_PX`` tile
    rectangle — what the per-tile merge actually resolves — so a one-pixel
    change must not read as covering only that pixel.
    """
    base = make_document()
    mainline = branch(base, site_id=0)
    source = branch(base, site_id=1)
    dialog = Branch_Diff_Dialog(
        "feature", "mainline", source, mainline, source.document()
    )
    qtbot.addWidget(dialog)
    text = dialog._region_granularity_label.text()
    assert str(_TILE) in text
    assert "tile" in text.lower()


# --------------------------------------------------------------------------- #
# Full divergence + supervision warning: every group, every detail category.  #
# --------------------------------------------------------------------------- #


@pytest.fixture
def diverged_dialog(qtbot, make_document):
    """A dialog whose source diverges from target in all 4 op classes, and
    whose live document is NOT accounted for in all 5 supervision categories
    (frames, layers, attributes, metadata keys, tiles) — independently
    computed and asserted against below.
    """
    base = make_document()
    mainline = branch(base, site_id=0)
    source = branch(base, site_id=1)
    ops = (
        MetadataOp("title", "Branched", 1, 1),
        LayerAttrOp(0, 1, "opacity", 0.5, 2, 1),
        LayerOrderOp(0, (1,), 3, 1),
        RasterOp(0, 1, 0, 0, _solid_tile(200), _TILE, _TILE, 4, 1),
    )
    source.record(ops)

    live = source.document()
    live.metadata["extra"] = "value"  # metadata_keys diff
    live.frames[0].layers[0].opacity = 0.9  # attrs diff (materialised is 0.5)
    live.frames[0].layers[0].buffer.set_pixel(2, 2, (9, 9, 9, 255))  # tiles diff
    live.add_layer("Extra", frame_index=0)  # layers diff (frame 0, structural)
    live.add_frame()  # frames diff (extra frame only in live)

    dialog = Branch_Diff_Dialog("feature", "mainline", source, mainline, live)
    qtbot.addWidget(dialog)
    return dialog


def test_full_divergence_populates_every_group_with_independently_counted_values(
    diverged_dialog,
):
    """Every op-tier group shows exactly the count this test itself recorded —
    the dialog computes nothing (Article I): it only formats.
    """
    dialog = diverged_dialog
    for group_key, (_box, count_label, list_widget) in dialog._groups.items():
        assert list_widget.count() == 1, group_key
        assert "1" in count_label.text()
    assert dialog._region_list.count() == 1
    assert "4 operation" in dialog._total_label.text()
    assert "4 distinct" in dialog._total_label.text()


def test_full_divergence_entry_text_names_the_real_op_fields(diverged_dialog):
    """``_format_entry`` renders each of the four op classes distinctly."""
    dialog = diverged_dialog
    texts = {key: dialog._groups[key][2].item(0).text() for key in dialog._groups}
    assert "title" in texts["metadata"] and "Branched" in texts["metadata"]
    assert "opacity" in texts["layer_attr"]
    assert "layer order changed" in texts["layer_order"]
    assert "tile (0, 0)" in texts["raster"]


def test_full_divergence_identical_label_hidden_when_not_empty(diverged_dialog):
    assert diverged_dialog._identical_label.isVisible() is False


def test_supervision_warns_and_names_every_unaccounted_category(diverged_dialog):
    """``REQ-P10-LOGIC-009``/``-026``: every located divergence category is named
    (frames, layers, attributes, metadata keys, tiles) — never repaired, only
    reported.
    """
    text = diverged_dialog._supervision_label.text()
    assert "warning" in text.lower()
    assert "not recorded" in text.lower()
    for keyword in ("frames", "layers", "attributes", "metadata keys", "tiles"):
        assert keyword in text, f"missing detail category: {keyword!r}"


def test_supervision_detail_names_only_metadata_keys(qtbot, make_document):
    """A PARTIALLY unaccounted branch names only what actually differs — the
    other 4 (empty) categories are skipped, not padded with empty mentions.
    """
    base = make_document()
    mainline = branch(base, site_id=0)
    source = branch(base, site_id=1)
    live = source.document()
    live.metadata["extra"] = "value"  # the ONLY divergence category populated

    dialog = Branch_Diff_Dialog("feature", "mainline", source, mainline, live)
    qtbot.addWidget(dialog)

    text = dialog._supervision_label.text()
    assert "metadata keys" in text
    for keyword in ("frames", "layers", "attributes", "tiles"):
        assert keyword not in text, f"unexpected detail category: {keyword!r}"


def test_supervision_detail_names_only_tiles(qtbot, make_document):
    """The mirror case: only ``tiles`` populated, every earlier category skipped
    (proves the skip arcs of every ``if self._supervision.X:`` check, not just
    the always-True combination).
    """
    base = make_document()
    mainline = branch(base, site_id=0)
    source = branch(base, site_id=1)
    live = source.document()
    live.frames[0].layers[0].buffer.set_pixel(3, 3, (1, 2, 3, 255))  # tiles-only

    dialog = Branch_Diff_Dialog("feature", "mainline", source, mainline, live)
    qtbot.addWidget(dialog)

    text = dialog._supervision_label.text()
    assert "tiles" in text
    for keyword in ("frames", "layers", "attributes", "metadata keys"):
        assert keyword not in text, f"unexpected detail category: {keyword!r}"


# --------------------------------------------------------------------------- #
# The two exits: Close (button / Escape) and Continue to Merge.               #
# --------------------------------------------------------------------------- #


def _make_dialog(qtbot, make_document):
    base = make_document()
    mainline = branch(base, site_id=0)
    source = branch(base, site_id=1)
    dialog = Branch_Diff_Dialog(
        "feature", "mainline", source, mainline, source.document()
    )
    qtbot.addWidget(dialog)
    return dialog


def test_close_button_rejects(qtbot, make_document):
    dialog = _make_dialog(qtbot, make_document)
    dialog.show()
    qtbot.mouseClick(dialog._close_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_escape_key_rejects(qtbot, make_document):
    """Escape closes the dialog the same way as the Close button (``QDialog.reject()``
    under all three affordances — button, Escape, window-close).
    """
    dialog = _make_dialog(qtbot, make_document)
    dialog.show()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_continue_button_emits_source_name_and_accepts(qtbot, make_document):
    """Continue announces the source branch; it performs NO merge itself."""
    dialog = _make_dialog(qtbot, make_document)
    dialog.show()
    with qtbot.waitSignal(dialog.continueToMergeRequested, timeout=1000) as blocker:
        qtbot.mouseClick(dialog._continue_button, Qt.MouseButton.LeftButton)
    assert blocker.args == ["feature"]
    assert dialog.result() == QDialog.DialogCode.Accepted


# --------------------------------------------------------------------------- #
# Accessibility (a11y-audit surface).                                        #
# --------------------------------------------------------------------------- #


def test_every_control_has_an_accessible_name(diverged_dialog):
    dialog = diverged_dialog
    assert dialog.accessibleName() != ""
    assert dialog._basis_label.accessibleName() != ""
    assert dialog._supervision_label.accessibleName() != ""
    assert dialog._supervision_label.accessibleDescription() != ""
    assert dialog._region_list.accessibleName() != ""
    assert dialog._region_list.accessibleDescription() != ""
    assert dialog._total_label.accessibleName() != ""
    assert dialog._continue_button.accessibleName() != ""
    assert dialog._continue_button.accessibleDescription() != ""
    assert dialog._close_button.accessibleName() != ""
    assert dialog._close_button.accessibleDescription() != ""
    for _box, count_label, list_widget in dialog._groups.values():
        assert list_widget.accessibleName() != ""
        assert list_widget.accessibleDescription() != ""


def test_retranslates_on_language_change(qtbot, make_document):
    """``REQ-P10-UI-023``: re-sets every ``tr()`` string on ``QEvent.LanguageChange``,
    re-FORMATTING the already-computed results — never re-deriving them.
    """
    dialog = _make_dialog(qtbot, make_document)
    before = dialog._continue_button.text()
    QApplication.sendEvent(dialog, QEvent(QEvent.Type.LanguageChange))
    assert dialog._continue_button.text() == before  # same language -> same text
    assert dialog._continue_button.text() != ""
    assert dialog.windowTitle() != ""


# --------------------------------------------------------------------------- #
# Refusal/cancel paths, driven through Main_Window (REQ-P10-UI-014).          #
# --------------------------------------------------------------------------- #


def test_open_diff_noop_without_active_tab(qtbot):
    """No open document -> no active tab -> the request is silently refused."""
    win = Main_Window()
    qtbot.addWidget(win)
    win._on_open_diff_requested("feature")
    assert win._branch_diff_dialog is None


def test_open_diff_noop_for_unknown_branch(qtbot):
    """A branch name the session does not know is refused, not guessed at."""
    win = Main_Window()
    qtbot.addWidget(win)
    win.new_document(64, 64)
    win._on_open_diff_requested("does-not-exist")
    assert win._branch_diff_dialog is None


def test_continue_to_merge_hands_off_to_the_unchanged_merge_function(qtbot):
    """``REQ-P10-UI-018``/``-019``: Continue to Merge performs no merge of its
    own — it runs the exact SAME ``Branching_Session.merge_to_mainline`` the
    branching panel's own Merge button uses (no second merge path).
    """
    win = Main_Window()
    qtbot.addWidget(win)
    win.new_document(64, 64)
    win._branching_session.create_branch("feature")
    win._on_open_diff_requested("feature")
    dialog = win._branch_diff_dialog
    assert dialog is not None
    dialog.show()

    with qtbot.waitSignal(win._branching_session.mergeCompleted, timeout=1000):
        qtbot.mouseClick(dialog._continue_button, Qt.MouseButton.LeftButton)

    assert "feature" not in win._branching_session.branch_names()
    assert dialog.isVisible() is False
