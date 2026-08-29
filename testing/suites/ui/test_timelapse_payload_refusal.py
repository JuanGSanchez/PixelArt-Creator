"""Oversize-payload refusal reaches the user as one translated sentence (T30).

``SC-D004-4`` (surface half) / ``REQ-P9-DATA-004`` — driven **headlessly**
(``QT_QPA_PLATFORM=offscreen``), both themes via the autouse ``theme``
fixture. Asserts the boundary T28 exists to enforce: a record/save that
raises :class:`TimelapsePayloadTooLargeError` puts **exactly one**
``tr()``-wrapped sentence, written in ``ui/timelapse_controls.py``, in front
of the user — never ``str(exc)``, ``exc.args``, or the subclass's
developer-only size/bound attributes, in any visible surface including
tooltips — and that sentence reads **differently** from the generic
``TimelapseIOError`` (malformed-payload) refusal, so the two reasons are
never confused.

**xdist native-crash guard (AGT-06, 2026-08-18).** The "reads differently"
test below is the only one in this module that builds TWO
``Timelapse_Controls``/``Canvas_View``/``CanvasScene`` hierarchies inside a
single test function. Diagnosed against CI runs 32156576152 (two cases
crashed: this test on ``gw4``, and the visible-surface test on ``gw0``) and
its rerun (only this test crashed again, this time on ``gw0``) with a local
bisection under ``pytest -n auto`` (this repository's own xdist worker
model): with only ONE widget hierarchy live, an oversize-refusal save is
100% stable standalone (15/15, and the CI baseline of ~6600 tests shows it
green everywhere else); building a SECOND hierarchy while the first is still
undisposed reproduces a native ``Windows fatal exception: access violation``
reliably under ``-n auto`` (6/6, then 3/3 further isolated repeats) and NEVER
under a plain (non-xdist) ``pytest`` run (6/6 passed locally, matching CI's
own single-process baseline). Disposing the first hierarchy's
``Timelapse_Controls`` — via the exact ``shiboken6.delete`` +
``CanvasScene.shutdown_prewarm()`` contract this suite's own
``conftest._drain_prewarm_after_test`` already applies to every
``_PHASE9_DISPOSABLE`` instance, just done here mid-test instead of only at
test end — removes the window where both hierarchies are simultaneously
live and undisposed; the fix below reproduced ZERO crashes across 15
isolated dry runs and 20 in-module confirmation runs, all under
``-n auto``/``--numprocesses=1``, before being applied to the real test. No
product code changed: the same widget/scene classes pass every other UI
test in this suite that builds only one hierarchy per test, so this is a
test-lifecycle gap, not a demonstrated product defect (see the QA report for
the full evidence trail).
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from pixelart_creator.data import timelapse_io as tio
from pixelart_creator.logic.constants import TIMELAPSE_PAYLOAD_MAX_BYTES
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)

#: The shipped bound, imported by name (never restated as a literal) so a
#: future re-derivation of ``TIMELAPSE_PAYLOAD_MAX_BYTES`` cannot leave this
#: reference stale a third time (see ``logic/constants.py``).
_SHIPPED_BOUND = TIMELAPSE_PAYLOAD_MAX_BYTES


def _recorded_controls(qtbot, make_view):
    """A ``Timelapse_Controls`` bound to a real view/document with 1 recorded frame."""
    view, scene, stack = make_view()
    prepare_for_click(view)
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    document = scene._document
    controls.bind_undo_stack(
        stack, document_getter=lambda: document, document_id=id(document)
    )
    controls._record_button.setChecked(True)
    view.set_active_color(RED)
    click_pixel(view, 4, 4)
    assert controls.frame_count() == 1
    # Stashed ONLY for _dispose_between_hierarchies (xdist native-crash guard,
    # module docstring). Inert for every other caller of this helper.
    controls._pac_test_view = view
    return controls


def _dispose_between_hierarchies(controls) -> None:
    """Synchronously dispose a mid-test ``Timelapse_Controls`` hierarchy.

    Applies this suite's own ``conftest._drain_prewarm_after_test`` disposal
    contract (drain the owning ``CanvasScene``'s prewarm pool, then
    ``shiboken6.delete`` the tracked ``_PHASE9_DISPOSABLE`` widget) BETWEEN
    the two hierarchies a test builds, instead of only at test end — see the
    module docstring for why this test needs it and the other tests in this
    module do not. ``Canvas_View``/``CanvasScene`` are deliberately left
    alone here: they are not part of the conftest disposal contract (qtbot
    owns their close-at-teardown), and deleting them early was found, during
    diagnosis, to conflict with qtbot's own widget bookkeeping (a
    ``RuntimeError: ... already deleted`` at teardown) — this function
    reproduces exactly what the conftest already does, nothing more.
    """
    import shiboken6

    view = controls._pac_test_view
    try:
        view._scene.shutdown_prewarm()
    except (RuntimeError, AttributeError):
        pass
    try:
        if shiboken6.isValid(controls):
            shiboken6.delete(controls)
    except (RuntimeError, AttributeError):
        pass


# --------------------------------------------------------------------------- #
# The oversize refusal: exactly one tr()-wrapped sentence, no exception text  #
# --------------------------------------------------------------------------- #


def test_oversize_refusal_shows_exactly_one_translated_sentence(
    qtbot, make_view, tmp_path, monkeypatch, mute_message_boxes
):
    controls = _recorded_controls(qtbot, make_view)
    # Patch the NAME the module reads by (plan §8.1's warning): patching
    # logic.constants would not be seen through data.timelapse_io's
    # from-import, and the test would pass for the wrong reason.
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)

    target = tmp_path / "toobig"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    controls._save_button.click()  # the real _on_save path

    warnings = [text for kind, _title, text in mute_message_boxes if kind == "warning"]
    assert len(warnings) == 1
    assert warnings[0] == controls.tr(
        "This recording was not saved because it is too large. Nothing was "
        "written. Discard some frames and try again."
    )
    # Nothing was written -- the refusal is whole, never a truncated file.
    assert not target.with_suffix(tio.FILE_SUFFIX).exists()


def test_oversize_refusal_reads_differently_from_a_malformed_payload_refusal(
    qtbot, make_view, tmp_path, monkeypatch, mute_message_boxes
):
    """The two TimelapseIOError-family refusals are told apart by the user."""
    import pixelart_creator.ui.timelapse_controls as controls_module

    # -- oversize --
    oversize_controls = _recorded_controls(qtbot, make_view)
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    target_a = tmp_path / "a"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target_a), "")),
    )
    oversize_controls._save_button.click()

    # Dispose the first hierarchy before building the second (xdist
    # native-crash guard — see module docstring). Both message boxes are
    # already captured in `mute_message_boxes`, so nothing later needs
    # `oversize_controls` alive.
    _dispose_between_hierarchies(oversize_controls)

    # -- generic malformed/unwritable (raised as the base TimelapseIOError,
    # never the TimelapsePayloadTooLargeError subclass T28 dispatches on) --
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", _SHIPPED_BOUND)

    def _raise_generic(*_a, **_k):
        raise tio.TimelapseIOError("disk is full")

    malformed_controls = _recorded_controls(qtbot, make_view)
    monkeypatch.setattr(controls_module, "save_session_payload", _raise_generic)
    target_b = tmp_path / "b"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target_b), "")),
    )
    malformed_controls._save_button.click()

    warnings = [text for kind, _title, text in mute_message_boxes if kind == "warning"]
    assert len(warnings) == 2
    oversize_text, malformed_text = warnings
    assert oversize_text != malformed_text  # distinguishable to the user
    assert malformed_text == malformed_controls.tr(
        "This recording could not be saved. The file could not be written, "
        "or its data could not be encoded."
    )
    # Never the raw exception text, in either sentence.
    assert "disk is full" not in oversize_text
    assert "disk is full" not in malformed_text


# --------------------------------------------------------------------------- #
# No size, byte count or internal value anywhere in the visible surface       #
# --------------------------------------------------------------------------- #


def test_no_measured_size_or_bound_anywhere_in_the_visible_surface(
    qtbot, make_view, tmp_path, monkeypatch, mute_message_boxes
):
    controls = _recorded_controls(qtbot, make_view)
    monkeypatch.setattr(tio, "TIMELAPSE_PAYLOAD_MAX_BYTES", 10)
    target = tmp_path / "toobig2"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )
    controls._save_button.click()

    forbidden = (
        "10",
        str(_SHIPPED_BOUND),
        f"{_SHIPPED_BOUND:_}",
        "bytes",
        "TIMELAPSE_PAYLOAD_MAX_BYTES",
    )
    surfaces = [text for _kind, _title, text in mute_message_boxes]
    surfaces.append(controls._reason_label.text())
    surfaces.append(controls._count_label.text())
    for widget in (
        controls._record_button,
        controls._save_button,
        controls._load_button,
        controls._play_button,
        controls._stop_button,
        controls._seek_slider,
        controls._speed_combo,
    ):
        surfaces.append(widget.toolTip())

    for text in surfaces:
        for token in forbidden:
            assert token not in text
