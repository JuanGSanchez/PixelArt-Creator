"""Tests for cross-session replay (REQ-P9-LOGIC-019): a saved,
payload-carrying recording replays with NO live history and NO open
document. No Qt import -- the real Snapshot_Document_Provider is
ui/timelapse_playback.py; here a local helper built only from
data/snapshot_store.py + data/timelapse_io.py's *_payload functions stands
in for it, exercising exactly the logic-layer contract those two modules
hand to `replay`.

**Written against plan.md §8.2/§8.3 (2026-08-17 addendum, Ruling B)**:
``ReconstructionExtent`` is substrate-keyed (``SNAPSHOT`` here, addressed by
``reachable_snapshot_ids`` -- a set of content-hash ids, never a count, per
Ruling B (B-2)), ``Reconstructability`` carries a ``blocker`` code rather
than an English ``reason``, and ``DocumentProvider`` is keyed by the
``TimelapseFrame`` itself (``Callable[[TimelapseFrame], Document]``), not by
ordinal. This supersedes the shape shipped in this worktree at dispatch
time; until `logic/timelapse.py` is updated to match, this module fails to
import -- reported upstream, not silently accommodated (Decision A4-D3).

SC-L019-1..4 (a saved recording replays after the session ended, is
deterministic across two application sessions, an incomplete payload is
reported unplayable rather than partially played, and replaying a loaded
recording disturbs no open document).

SC-L020-*/SC-L021-* (the measurement campaign + extrapolation model,
owned by the performance work) are NOT covered here: as of this session neither
the payload-campaign report nor the cost-extrapolation-model report exists
yet. No test in this file may
assert a projected number or an 8K threshold in any case; asserting on the
reports' *existence* before they have been produced would be a test
authored to fail, which is not what a dependency gap calls for -- reported
as BLOCKED on that upstream work instead (see the accompanying report).

**Re-keyed 2026-08-18 (Q-21) onto the stable frame identity**
(REQ-P9-LOGIC-022, REQ-P9-DATA-005). ``data/timelapse_io.py``'s
``serialize_payload``/``save_session_payload`` now write **only** schema 3
(identity-bearing) -- a schema-2 (payload-carrying, no-identity) session
raises ``TimelapseIOError`` if handed to either. Every session this module
builds and SAVES is therefore now schema 3: a per-recording id plus one
``recording_id:command_id`` identity per frame (mirroring the shape
``ui/timelapse_controls.py`` mints), matching the
``^[0-9a-f]{32}:[0-9]+$`` pattern `data/timelapse_io.py` itself checks on
load. **Substitution (old assertion -> new assertion, listed per this
re-key's done-when -- no assertion was deleted):**

- ``_record_and_save`` -- OLD: built a schema-2
  ``TimelapseSession(schema_version=TIMELAPSE_PAYLOAD_SCHEMA_VERSION, ...)``
  with no ``frame_id``, then called ``save_session_payload``. NEW: builds a
  schema-3 session (``recording_id`` set, every frame carrying its own
  ``frame_id``) via the same construction shape, because the write path
  itself now refuses the old one -- the round-trip/replay assertions every
  caller of this helper makes (SC-L019-1, -2, -4) are otherwise unchanged.
- ``test_sc_l019_3_incomplete_payload_reports_unplayable_naming_the_frame`` --
  OLD: frames 0/1 carried a ``snapshot_id`` and frame 2 did not, all three
  with no identity; ``reconstructability`` named frame 2 as
  ``NO_PAYLOAD``. Since the SNAPSHOT substrate now checks identity *after*
  ``NO_PAYLOAD`` but *before* ``PAYLOAD_INCOMPLETE`` (``SC-D005-3``'s
  precedence), a frame carrying a ``snapshot_id`` but no ``frame_id`` blocks
  on ``NO_IDENTITY`` at frame 0 -- before frame 2 is ever reached. NEW: every
  frame (including the deliberately-incomplete frame 2) now carries a
  ``frame_id``, so the identity check passes uniformly and the test again
  exercises exactly what it names -- ``NO_PAYLOAD`` at the first frame
  missing its snapshot, unclouded by a missing identity.
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.data.snapshot_store import document_of, snapshot_of
from pixelart_creator.data.timelapse_io import (
    load_session_payload,
    save_session_payload,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.timelapse import (
    TIMELAPSE_IDENTITY_SCHEMA_VERSION,
    Reconstructability,
    ReconstructionBlocker,
    ReconstructionExtent,
    ReconstructionSubstrate,
    TimelapseError,
    TimelapseFrame,
    TimelapseSession,
    reconstructability,
    replay,
)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)

#: A fixed, 32-lowercase-hex-char per-module recording id (Q-21
#: re-key) -- matches the shape `data/timelapse_io.py` validates
#: (`^[0-9a-f]{32}:[0-9]+$`, prefixed by this value). This module is
#: Qt-free and mints nothing itself (that stays ui/'s job); a fixed
#: string is all a *validating* test needs.
_RECORDING_ID = "cafecafecafecafecafecafecafecafe"


def _frame_id(command_id) -> str:
    return f"{_RECORDING_ID}:{command_id}"


def _document(pixel) -> Document:
    doc = Document(2, 2, palette=Palette([RED, BLUE, GREEN]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, pixel)
    return doc


def _record_and_save(tmp_path, pixels, name="rec"):
    """Build+save an identity-bearing (schema-3) session, one frame per pixel
    value -- mirrors what a real in-session Snapshot_Document_Provider
    recording would persist through save_session_payload, now that
    schema 2 is read-only legacy and the write path requires identity
    (Q-21 substitution, module docstring)."""
    snapshots = {}
    blobs = {}
    frames = []
    for command_id, pixel in enumerate(pixels):
        snapshot, doc_blobs = snapshot_of(_document(pixel))
        snapshot_id = f"snap-{command_id}"
        snapshots[snapshot_id] = snapshot
        blobs.update(doc_blobs)
        frames.append(
            TimelapseFrame(
                index=command_id,
                command_id=command_id,
                snapshot_id=snapshot_id,
                frame_id=_frame_id(command_id),
            )
        )
    session = TimelapseSession(
        schema_version=TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        frames=tuple(frames),
        recording_id=_RECORDING_ID,
    )
    path = save_session_payload(session, snapshots, blobs, tmp_path / name)
    return path


def _provider_from_payload(payload):
    """The logic-layer contract a real Snapshot_Document_Provider
    fulfils: given a FRAME (Ruling B §8.3 -- not an ordinal), resolve its
    persisted snapshot -- no live history, no open document involved."""

    def provider(frame: TimelapseFrame):
        if frame.snapshot_id is None:
            raise TimelapseError(f"frame {frame.index} carries no persisted snapshot")
        return document_of(payload.snapshots[frame.snapshot_id], payload.blobs)

    return provider


def _pixel_renderer(document):
    return document.frames[0].layers[0].buffer.get_pixel(0, 0)


# --------------------------------------------------------------------------- #
# SC-L019-1 -- a saved recording replays after the editing session ended      #
# --------------------------------------------------------------------------- #


def test_sc_l019_1_saved_recording_replays_with_no_live_history(tmp_path):
    pixels = [RED, BLUE, GREEN]
    path = _record_and_save(tmp_path, pixels)

    # "The original document, its tab and its undo stack no longer exist":
    # nothing but the file and a provider built purely from it is used below.
    payload = load_session_payload(path)
    provider = _provider_from_payload(payload)
    frames = replay(payload.session, provider, _pixel_renderer)

    assert frames == tuple(pixels)


def test_sc_l019_1_matches_the_in_session_replay_of_the_same_edits(tmp_path):
    pixels = [RED, BLUE]
    path = _record_and_save(tmp_path, pixels)

    # The in-session sequence for the same edits: a live "history" of the
    # same documents keyed by command_id (Ruling B), provided directly (no
    # persistence involved). Identity plays no role in a bare in-session
    # replay (`replay` resolves by command_id via the provider), so this
    # comparison session is left schema-1 deliberately.
    in_session_docs = {i: _document(p) for i, p in enumerate(pixels)}
    in_session_session = TimelapseSession(
        frames=tuple(TimelapseFrame(index=i, command_id=i) for i in range(len(pixels)))
    )
    in_session_frames = replay(
        in_session_session,
        lambda frame: in_session_docs[frame.command_id],
        _pixel_renderer,
    )

    payload = load_session_payload(path)
    cross_session_frames = replay(
        payload.session, _provider_from_payload(payload), _pixel_renderer
    )

    assert cross_session_frames == in_session_frames == tuple(pixels)


# --------------------------------------------------------------------------- #
# SC-L019-2 -- deterministic across two application sessions                  #
# --------------------------------------------------------------------------- #


def test_sc_l019_2_replaying_twice_in_two_sessions_is_byte_identical(tmp_path):
    pixels = [RED, BLUE, RED, GREEN]
    path = _record_and_save(tmp_path, pixels)

    # Two independent "application sessions": load + replay from scratch,
    # sharing nothing but the file on disk.
    payload_a = load_session_payload(path)
    frames_a = replay(
        payload_a.session, _provider_from_payload(payload_a), _pixel_renderer
    )

    payload_b = load_session_payload(path)
    frames_b = replay(
        payload_b.session, _provider_from_payload(payload_b), _pixel_renderer
    )

    assert len(frames_a) == len(frames_b)
    assert frames_a == frames_b


# --------------------------------------------------------------------------- #
# SC-L019-3 -- an incomplete payload is reported unplayable, never partial    #
# --------------------------------------------------------------------------- #


def test_sc_l019_3_incomplete_payload_reports_unplayable_naming_the_frame(tmp_path):
    # A payload where only the leading frames were actually persisted with a
    # snapshot -- a legitimate schema-3 shape (snapshot_id is optional) that
    # models a truncated/incomplete recording at the logic layer (the data
    # layer's own malformed/fingerprint-mismatch rejections are covered by
    # testing/suites/data/test_timelapse_io_schema3.py). Every frame -- including
    # the deliberately-incomplete one -- still carries its identity: identity
    # and payload-completeness are orthogonal (this re-key's substitution, module
    # docstring), and NO_PAYLOAD must be reached before PAYLOAD_INCOMPLETE
    # would ever apply, never masked by a missing identity.
    pixels = [RED, BLUE, GREEN]
    snapshots = {}
    blobs = {}
    frames = []
    for command_id, pixel in enumerate(pixels):
        if command_id < 2:  # only frames 0, 1 persisted a snapshot
            snapshot, doc_blobs = snapshot_of(_document(pixel))
            snapshot_id = f"snap-{command_id}"
            snapshots[snapshot_id] = snapshot
            blobs.update(doc_blobs)
            frames.append(
                TimelapseFrame(
                    index=command_id,
                    command_id=command_id,
                    snapshot_id=snapshot_id,
                    frame_id=_frame_id(command_id),
                )
            )
        else:
            frames.append(
                TimelapseFrame(
                    index=command_id,
                    command_id=command_id,
                    frame_id=_frame_id(command_id),
                )
            )
    session = TimelapseSession(
        schema_version=TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        frames=tuple(frames),
        recording_id=_RECORDING_ID,
    )
    path = save_session_payload(session, snapshots, blobs, tmp_path / "truncated")
    payload = load_session_payload(path)

    # SNAPSHOT substrate, reachable_snapshot_ids keyed by content-hash id
    # (Ruling B B-2 -- never a bare count).
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.SNAPSHOT,
        reachable_snapshot_ids=frozenset(payload.snapshots),
    )
    verdict = reconstructability(payload.session, extent)
    assert verdict.ok is False
    assert verdict.first_unreachable_index == 2
    assert verdict.blocker is ReconstructionBlocker.NO_PAYLOAD

    # Never partially played: replay against the same provider raises.
    with pytest.raises(TimelapseError):
        replay(payload.session, _provider_from_payload(payload), _pixel_renderer)


def test_sc_l019_3_payload_incomplete_when_snapshot_id_set_but_unresolved(tmp_path):
    # snapshot_id is set on the frame but absent from reachable_snapshot_ids
    # -- PAYLOAD_INCOMPLETE, distinct from NO_PAYLOAD (Ruling B's table).
    pixels = [RED, BLUE]
    path = _record_and_save(tmp_path, pixels)
    payload = load_session_payload(path)
    incomplete_extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.SNAPSHOT,
        reachable_snapshot_ids=frozenset(),  # every snapshot id missing
    )
    verdict = reconstructability(payload.session, incomplete_extent)
    assert verdict.ok is False
    assert verdict.first_unreachable_index == 0
    assert verdict.blocker is ReconstructionBlocker.PAYLOAD_INCOMPLETE


# --------------------------------------------------------------------------- #
# SC-L019-4 -- replaying a loaded recording disturbs no open document         #
# --------------------------------------------------------------------------- #


def test_sc_l019_4_replaying_a_loaded_recording_disturbs_no_open_document(tmp_path):
    open_document = _document(RED)
    open_document.frames[0].layers[0].buffer.set_pixel(1, 1, BLUE)
    before = open_document.frames[0].layers[0].buffer.data.copy()

    path = _record_and_save(tmp_path, [BLUE, GREEN])
    payload = load_session_payload(path)
    # The loaded recording's provider never receives, references or touches
    # `open_document` -- it is built purely from the loaded payload.
    replay(payload.session, _provider_from_payload(payload), _pixel_renderer)

    after = open_document.frames[0].layers[0].buffer.data
    assert np.array_equal(before, after)
