"""Identity-less (schema-2) recording refusal, at the user surface (T41).

``SC-UI-019-5`` / ``REQ-P9-UI-019``(f) / ``SC-D005-2`` (surface half) — driven
**headlessly** (``QT_QPA_PLATFORM=offscreen``), both themes via the autouse
``theme`` fixture (``tests/ui/conftest.py``). Asserts that opening a
payload-carrying recording written before the stable-identity amendment
(Q-21) puts **exactly one** ``tr()``-wrapped sentence in front of the user —
the surface's text equal to the widget's own translated string — that reads
**differently** from both the schema-1 sentence (clause (a)) and the
truncated-payload sentence (clause (e)), exercised together in this one
module so the three-way discrimination is proven **to the user**, never
merely inside the ``ReconstructionBlocker`` enum. Save/Open and the frame
count remain available (the file is still a readable record); no repair,
upgrade or "play anyway" affordance exists anywhere in the surface; and no
``str(exc)`` fragment, blocker code, identity string or ``detail`` text
appears in any visible surface, tooltips included (plan §8.2 B-3).

**Schema 2 is READ-ONLY LEGACY as of this slice (T35): ``serialize_payload``
refuses to WRITE it.** The schema-2 fixture this module needs is therefore
built by taking a genuinely-produced schema-3 payload (real recorded pixel
edits, through the real save path, with real snapshot/blob tables) and
downgrading its OWN on-disk JSON — stripping every frame's ``"identity"``
and the root ``"recording_id"``, and setting ``"schema_version"`` back to
``"2"`` — never a hand-fabricated fingerprint or blob. This is the same
shape ``REQ-P9-DATA-005``'s own SC-D005-2 models: "a payload-carrying file
whose frames carry no stable identity", produced honestly rather than typed
in by hand.
"""

from __future__ import annotations

import json

import numpy as np
from PySide6.QtWidgets import QFileDialog

from pixelart_creator.data.timelapse_io import load_session_payload, save_session
from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.timelapse import (
    TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
    TimelapseFrame,
    TimelapseSession,
    new_session,
    reconstructability,
    record_frame,
)
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)

#: Words that would signal a repair/upgrade/"play anyway" affordance if they
#: showed up on any widget's visible text -- none is offered (spec §0b.1).
_FORBIDDEN_AFFORDANCE_WORDS = ("repair", "upgrade", "play anyway", "convert", "migrat")


def _renderer(document):
    """The same ``Document -> ndarray`` shape ``ui/main_window.py`` injects."""
    buffer = composite_stack(document.frames[0].layers, document.width, document.height)
    return np.ascontiguousarray(buffer.data)


def _controls(qtbot):
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    return controls


def _write_schema2_and_schema3_files(qtbot, make_view, tmp_path, monkeypatch):
    """Record + save a REAL schema-3 payload; return (schema2_path, schema3_path).

    ``schema3_path`` is the untouched, genuinely-saved file (reused by the
    truncated-payload/clause-(e) comparison below); ``schema2_path`` is a
    SEPARATE file holding the same content downgraded to schema 2.
    """
    view, scene, stack = make_view()
    prepare_for_click(view)
    document = scene._document
    controls = _controls(qtbot)
    controls.bind_undo_stack(
        stack, document_getter=lambda: document, document_id=id(document)
    )
    controls.set_renderer(_renderer)
    controls._record_button.setChecked(True)
    view.set_active_color(RED)
    click_pixel(view, 5, 5)
    view.set_active_color(GREEN)
    click_pixel(view, 20, 20)
    controls._record_button.setChecked(False)

    saved_path = tmp_path / "schema2_source"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(saved_path), "")),
    )
    controls._save_button.click()  # the real _on_save path -- a genuine schema-3 file
    schema3_path = saved_path.with_suffix(".pixtimelapse")
    assert schema3_path.exists()

    raw = json.loads(schema3_path.read_text(encoding="utf-8"))
    raw["schema_version"] = TIMELAPSE_PAYLOAD_SCHEMA_VERSION  # "2" -- read-only legacy
    del raw["recording_id"]
    for frame in raw["frames"]:
        del frame["identity"]
    schema2_path = tmp_path / "schema2.pixtimelapse"
    schema2_path.write_text(json.dumps(raw), encoding="utf-8")
    return schema2_path, schema3_path


# --------------------------------------------------------------------------- #
# SC-UI-019-5 -- the identity-less refusal, distinguished from (a) and (e)    #
# --------------------------------------------------------------------------- #


def test_sc_ui_019_5_identity_less_recording_states_its_own_reason(
    qtbot, make_view, tmp_path, monkeypatch
):
    """SC-UI-019-5: opening a schema-2 recording states its OWN, distinct reason."""
    schema2_path, schema3_path = _write_schema2_and_schema3_files(
        qtbot, make_view, tmp_path, monkeypatch
    )
    payload = load_session_payload(schema2_path)
    assert all(
        f.frame_id is None for f in payload.session.frames
    )  # genuinely identity-less

    controls = _controls(qtbot)
    controls.show()  # a QLabel's isVisible() needs the whole ancestor chain shown
    controls.set_renderer(_renderer)
    controls.load_reopened_recording(payload)

    # Reached as a VALUE first (plan §8.2), never by string-matching alone.
    from pixelart_creator.logic.timelapse import ReconstructionBlocker
    from pixelart_creator.ui.timelapse_playback import Snapshot_Document_Provider

    verdict = reconstructability(
        controls.session(), Snapshot_Document_Provider(payload).extent()
    )
    assert verdict.ok is False
    assert verdict.blocker is ReconstructionBlocker.NO_IDENTITY

    identity_less_sentence = controls.tr(
        "This recording was saved in an earlier form whose frames cannot be "
        "told apart reliably, so it will not be replayed."
    )
    assert controls._play_button.isEnabled() is False
    assert controls._reason_label.isVisible() is True
    assert controls._reason_label.text() == identity_less_sentence

    # The file is still a readable record: frame count shown, Save/Open work.
    assert str(controls.frame_count()) in controls._count_label.text()
    assert controls._save_button.isEnabled() is True
    assert controls._load_button.isEnabled() is True

    # No repair/upgrade/"play anyway" affordance anywhere in the surface.
    for widget in (
        controls._record_button,
        controls._save_button,
        controls._load_button,
        controls._play_button,
        controls._stop_button,
        controls._seek_slider,
        controls._speed_combo,
        controls._reason_label,
        controls._count_label,
    ):
        visible_text = widget.text() if hasattr(widget, "text") else ""
        lowered = visible_text.lower()
        for banned in _FORBIDDEN_AFFORDANCE_WORDS:
            assert banned not in lowered

    # -- clause (a): the schema-1 sentence differs -------------------------
    schema1_session = record_frame(new_session(), command_id=1)
    schema1_path = save_session(schema1_session, tmp_path / "old")
    schema1_payload = load_session_payload(schema1_path)
    controls_a = _controls(qtbot)
    controls_a.set_renderer(_renderer)
    controls_a.load_reopened_recording(schema1_payload)
    schema1_sentence = controls_a._reason_label.text()
    assert schema1_sentence != identity_less_sentence
    assert schema1_sentence == controls_a.tr(
        "This recording was saved in a form that cannot be replayed."
    )

    # -- clause (e): the truncated/incomplete-payload sentence differs -----
    good_payload = load_session_payload(schema3_path)  # genuinely identity-bearing
    extra = TimelapseFrame(
        index=len(good_payload.session.frames),
        command_id=99,
        snapshot_id="not-in-this-payload",
        frame_id=f"{good_payload.session.recording_id}:99",
    )
    truncated_session = TimelapseSession(
        schema_version=good_payload.session.schema_version,
        frames=good_payload.session.frames + (extra,),
        recording_id=good_payload.session.recording_id,
    )
    controls_e = _controls(qtbot)
    controls_e.set_renderer(_renderer)
    controls_e.load_reopened_recording(good_payload)
    controls_e._session = truncated_session
    controls_e._update_play_availability()
    truncated_sentence = controls_e._reason_label.text()
    assert truncated_sentence not in (identity_less_sentence, schema1_sentence)
    assert truncated_sentence == controls_e.tr(
        "This recording's saved data is incomplete and cannot be fully " "replayed."
    )

    # All three sentences are pairwise distinct.
    assert len({identity_less_sentence, schema1_sentence, truncated_sentence}) == 3


# --------------------------------------------------------------------------- #
# No developer-only detail reaches ANY visible surface, tooltips included     #
# --------------------------------------------------------------------------- #


def test_sc_ui_019_5_no_developer_only_detail_leaks_anywhere(
    qtbot, make_view, tmp_path, monkeypatch
):
    """No ``str(exc)`` fragment, blocker code, identity string or ``detail``
    text appears in any visible surface OR any tooltip (plan §8.2 B-3)."""
    schema2_path, _schema3_path = _write_schema2_and_schema3_files(
        qtbot, make_view, tmp_path, monkeypatch
    )
    payload = load_session_payload(schema2_path)

    controls = _controls(qtbot)
    controls.set_renderer(_renderer)
    controls.load_reopened_recording(payload)

    from pixelart_creator.logic.timelapse import ReconstructionBlocker
    from pixelart_creator.ui.timelapse_playback import Snapshot_Document_Provider

    verdict = reconstructability(
        controls.session(), Snapshot_Document_Provider(payload).extent()
    )
    assert verdict.ok is False
    assert verdict.detail  # developer-only detail IS present on the verdict...

    banned_fragments = [
        verdict.detail,
        "no-identity",
        "NO_IDENTITY",
        str(verdict.blocker),
    ]
    reason = controls._reason_label.text()
    for widget in (
        controls._record_button,
        controls._save_button,
        controls._load_button,
        controls._play_button,
        controls._stop_button,
        controls._seek_slider,
        controls._speed_combo,
        controls._reason_label,
        controls._count_label,
    ):
        visible_text = widget.text() if hasattr(widget, "text") else ""
        tooltip = widget.toolTip()
        for fragment in banned_fragments:
            assert fragment not in visible_text
            assert fragment not in tooltip
    assert verdict.detail not in reason
    assert (
        verdict.blocker is ReconstructionBlocker.NO_IDENTITY
    )  # value, not string-matched


# --------------------------------------------------------------------------- #
# REQ-P9-UI-022 -- the reason is exposed to assistive technology              #
# --------------------------------------------------------------------------- #


def test_sc_ui_019_5_reason_is_exposed_to_assistive_technology(
    qtbot, make_view, tmp_path, monkeypatch
):
    """REQ-P9-UI-022: the visible refusal reason must also be an accessible one.

    FINDING (reported, not fixed here -- C2 not implicated, S1/S2 unaffected):
    ``Timelapse_Controls._reason_label`` is a bare ``QLabel`` with no
    ``setAccessibleName``/``setAccessibleDescription`` call anywhere in
    ``ui/timelapse_controls.py`` (confirmed by reading the file and by a
    direct probe: after ``setText(...)``, both ``accessibleName()`` and
    ``accessibleDescription()`` return ``""``). This is not specific to the
    identity-less refusal -- EVERY refusal reason this widget shows
    (schema-1, different-document, beyond-extent, incomplete-payload,
    identity-less) is affected identically, so this is filed once here where
    T41 first names the accessible-exposure obligation, rather than repeated
    per blocker. Routed to AGT-05 (owner of ``ui/``); AGT-06 does not fix a11y
    defects.
    """
    schema2_path, _schema3_path = _write_schema2_and_schema3_files(
        qtbot, make_view, tmp_path, monkeypatch
    )
    payload = load_session_payload(schema2_path)

    controls = _controls(qtbot)
    controls.set_renderer(_renderer)
    controls.load_reopened_recording(payload)
    reason = controls._reason_label.text()
    assert reason  # sanity: there IS a reason to expose

    accessible_name = controls._reason_label.accessibleName()
    accessible_description = controls._reason_label.accessibleDescription()
    assert reason in accessible_name or reason in accessible_description
