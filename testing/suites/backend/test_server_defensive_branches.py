"""Closes the sync_backend branch-coverage gap (issue #32, ci.yml "Coverage gate —
non-client packages", expires 2026-08-31): the *specific* branch outcomes measured
uncovered on 2026-07-30 (``sync_backend/server.py`` 93.57% line / 76.00% branch,
missing lines 63-65, 68-76, 134, and partial branches 309->exit, 333->335, 341->339).

Every test below asserts real, documented behaviour of the branch it closes — none
merely execute a line for the counter:

* :class:`~sync_backend.server._TokenRedactingFilter` / ``_scrub`` (lines 63-76) — the
  ADR-0036 Addendum A.2 guarantee that a share token never reaches a log sink verbatim.
  Not previously exercised because none of the shipped token-mode tests provoke a
  WARNING+-level ``websockets`` log record (the filter is installed but never fed a
  record) — proven here directly against real :class:`logging.LogRecord` instances.
* ``SyncServer.__init__`` share_secret/expected_iss/expected_aud validation (line 134) —
  :class:`~sync_backend.server.BackendError` on an incomplete token-mode configuration.
* Defensive fallthrough branches in ``_dispatch``/``_unsubscribe``/``_cleanup``
  (309->exit, 333->335, 341->339) that the validated wire protocol (``ControlKind`` has
  exactly four members, all handled) and the paired join/room bookkeeping make
  unreachable through any legitimate client sequence today — each is reached via a
  narrow, documented seam (a monkeypatched ``decode_message`` return, or direct
  manipulation of the internal dicts) and asserts the method degrades gracefully
  (no crash, correct resulting state) rather than merely running the line.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

import sync_backend.server as server_module
from sync_backend.server import BackendError, SyncServer

DOC = "defensive-doc"


# --------------------------------------------------------------------------- #
# _TokenRedactingFilter / _scrub (lines 63-65, 68-76).
# --------------------------------------------------------------------------- #


class TestScrub:
    def test_scrub_redacts_a_token_query_param_in_a_string(self):
        redacted = server_module._TokenRedactingFilter._scrub(
            "< GET /viewer?token=supersecretvalue&p=proj HTTP/1.1"
        )
        assert "supersecretvalue" not in redacted
        assert "token=<redacted>" in redacted
        assert "p=proj" in redacted  # other query params survive untouched

    def test_scrub_leaves_a_string_without_a_token_unchanged(self):
        text = "< GET /viewer?p=proj HTTP/1.1"
        assert server_module._TokenRedactingFilter._scrub(text) == text

    def test_scrub_passes_non_string_values_through_unmodified(self):
        # Non-str log args (ints, exceptions, etc.) must not be touched or coerced.
        sentinel = 42
        assert server_module._TokenRedactingFilter._scrub(sentinel) is sentinel


class TestTokenRedactingFilter:
    def _record(self, msg, args=None, level=logging.WARNING):
        # Construct with args=None then assign the intended `.args` directly: the
        # LogRecord constructor's own arg-unwrapping quirks (a single dict positional
        # arg is unwrapped specially; a bare scalar isn't a legal *args at all) are
        # orthogonal to what `_TokenRedactingFilter.filter` inspects — it only ever
        # reads `record.args` as it stands at call time, regardless of provenance.
        record = logging.LogRecord(
            name="websockets.server",
            level=level,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=None,
            exc_info=None,
        )
        record.args = args
        return record

    def test_filter_scrubs_the_raw_request_line_in_msg_with_no_args(self):
        # Mirrors the exact documented case: the framework's DEBUG raw-request line
        # "< GET <path> HTTP/1.1" where <path> carries "?token=...", logged with no
        # separate %-args.
        record = self._record(
            "< GET /viewer?token=abc123def&p=proj HTTP/1.1", args=None
        )
        result = server_module._TokenRedactingFilter().filter(record)
        assert result is True
        assert "abc123def" not in record.msg
        assert "token=<redacted>" in record.msg

    def test_filter_scrubs_tuple_args(self):
        record = self._record("%s", args=("GET /viewer?token=abc123 HTTP/1.1",))
        server_module._TokenRedactingFilter().filter(record)
        assert "abc123" not in record.args[0]
        assert "token=<redacted>" in record.args[0]
        assert isinstance(record.args, tuple)
        # The formatted message must still be renderable (no crash downstream).
        assert "abc123" not in record.getMessage()

    def test_filter_scrubs_dict_args(self):
        record = self._record(
            "%(line)s", args={"line": "GET /viewer?token=abc123 HTTP/1.1"}
        )
        server_module._TokenRedactingFilter().filter(record)
        assert "abc123" not in record.args["line"]
        assert "token=<redacted>" in record.args["line"]

    def test_filter_leaves_non_tuple_non_dict_args_untouched(self):
        # A single scalar %-arg (unusual but legal for logging) matches neither the
        # tuple nor dict branch — the filter must not raise and must not mutate it.
        record = self._record("count=%s", args=5)
        result = server_module._TokenRedactingFilter().filter(record)
        assert result is True
        assert record.args == 5

    def test_filter_with_falsy_args_skips_the_args_branch_but_still_scrubs_msg(self):
        record = self._record(
            "< GET /viewer?token=zzz HTTP/1.1", args=()
        )  # falsy (empty tuple)
        server_module._TokenRedactingFilter().filter(record)
        assert record.args == ()  # untouched — the falsy branch was taken
        assert "zzz" not in record.msg  # msg is still scrubbed regardless of args


# --------------------------------------------------------------------------- #
# Constructor validation (line 134).
# --------------------------------------------------------------------------- #


class TestShareSecretConfigValidation:
    def test_share_secret_without_expected_iss_raises(self):
        with pytest.raises(BackendError):
            SyncServer(share_secret="s", expected_iss=None, expected_aud="aud")

    def test_share_secret_without_expected_aud_raises(self):
        with pytest.raises(BackendError):
            SyncServer(share_secret="s", expected_iss="iss", expected_aud=None)

    def test_share_secret_without_either_raises(self):
        with pytest.raises(BackendError):
            SyncServer(share_secret="s")

    def test_share_secret_with_both_does_not_raise(self):
        # The False-branch control: fully configured token mode is accepted.
        server = SyncServer(share_secret="s", expected_iss="iss", expected_aud="aud")
        assert server is not None

    def test_no_share_secret_does_not_require_iss_or_aud(self):
        # Editor-path default: no validation is triggered at all.
        server = SyncServer()
        assert server is not None


# --------------------------------------------------------------------------- #
# _dispatch fallthrough for an unrecognized ControlKind (branch 309->exit).
# --------------------------------------------------------------------------- #


class _FakeMessage:
    """Stand-in for SyncMessage with a ``kind`` outside the four ControlKind members.

    ``sync_protocol.decode_message`` only ever returns one of the four validated
    ``ControlKind`` members, so ``_dispatch``'s trailing ``elif ... PRESENCE`` False arm
    is unreachable through any real decoded frame today. It is nonetheless a real
    defensive guard (protects a future vocabulary addition from crashing the relay), so
    it is exercised here via a monkeypatched decode seam rather than left unproven.
    """

    def __init__(self, document_id: str) -> None:
        self.kind = object()  # not equal to any ControlKind member
        self.document_id = document_id
        self.blob = None
        self.presence = None


def test_dispatch_silently_ignores_an_unrecognized_control_kind(monkeypatch):
    async def scenario():
        server = SyncServer()
        fake_message = _FakeMessage(DOC)
        monkeypatch.setattr(
            server_module.sync_protocol,
            "decode_message",
            lambda frame: fake_message,
        )
        connection = object()
        # Must not raise, must not persist, must not create a room for the document.
        await server._dispatch(connection, b"irrelevant-because-decode-is-faked")
        assert server.store.backlog(DOC) == ()
        assert server._rooms.get(DOC) is None

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# _unsubscribe for a document with no room entry (branch 333->335).
# --------------------------------------------------------------------------- #


def test_unsubscribe_for_a_never_joined_document_is_a_noop():
    # A LEAVE for a document nobody has ever joined -> self._rooms has no entry for it
    # (room is None). Must not raise and must not create a spurious room entry.
    server = SyncServer()
    connection = object()
    server._joined[connection] = set()  # mirrors _handler's per-connection bookkeeping
    server._unsubscribe(connection, "never-joined-doc")
    assert "never-joined-doc" not in server._rooms
    assert server._joined[connection] == set()


def test_leave_control_kind_for_unjoined_document_over_dispatch_is_a_noop():
    # Same guarantee exercised through the public _dispatch surface (a real LEAVE
    # frame), not just the private method directly.
    async def scenario():
        from pixelart_creator.logic import sync_protocol

        server = SyncServer()
        connection = object()
        server._joined[connection] = set()
        frame = sync_protocol.encode_leave("nobody-ever-joined-this-doc")
        await server._dispatch(connection, frame)
        assert "nobody-ever-joined-this-doc" not in server._rooms

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# _cleanup for a joined document whose room entry is missing (branch 341->339).
# --------------------------------------------------------------------------- #


def test_cleanup_tolerates_a_joined_document_with_no_matching_room():
    # Today's dispatch keeps _rooms and _joined in lock-step (JOIN always creates both;
    # nothing ever deletes a _rooms key), so this state cannot arise through the public
    # API — it is a guard against the two dicts drifting apart under a future change.
    # Exercised by directly constructing the divergent state.
    server = SyncServer()
    connection = object()
    server._joined[connection] = {"ghost-doc"}  # no matching entry in server._rooms
    assert "ghost-doc" not in server._rooms  # precondition: genuinely no room

    server._cleanup(connection)  # must not raise

    assert connection not in server._joined  # cleaned up regardless
    assert connection not in server._scope
