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
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from pixelart_creator.data import timelapse_io as tio
from pixelart_creator.logic.constants import TIMELAPSE_PAYLOAD_MAX_BYTES
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from tests.ui._ui_helpers import click_pixel, prepare_for_click

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
    return controls


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
