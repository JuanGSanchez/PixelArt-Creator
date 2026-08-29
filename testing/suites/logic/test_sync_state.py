"""Tests for pixelart_creator.logic.sync_state (Phase-10 Slice A, no Qt).

Covers the pure, deterministic :func:`compute_sync_state` classifier
(REQ-P10-LOGIC-001) — every documented transition (UP_TO_DATE / LOCAL_AHEAD /
REMOTE_AHEAD / DIVERGED) per AGT-03 report §7, plus malformed-input errors and
determinism.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.sync_state import (
    SyncError,
    SyncState,
    compute_sync_state,
)
from pixelart_creator.logic.version_history import CloudVersion


def _v(ordinal: int) -> CloudVersion:
    return CloudVersion(
        version_id=f"proj:{ordinal}",
        ordinal=ordinal,
        created_marker=ordinal,
        size_bytes=1,
    )


# --- state transitions (report §7 semantics) -------------------------------- #


def test_empty_remote_no_marker_is_up_to_date():
    assert compute_sync_state(None, []) is SyncState.UP_TO_DATE


def test_empty_remote_with_marker_is_local_ahead():
    assert compute_sync_state("proj:0", []) is SyncState.LOCAL_AHEAD


def test_non_empty_remote_no_marker_is_remote_ahead():
    assert compute_sync_state(None, [_v(0), _v(1)]) is SyncState.REMOTE_AHEAD


def test_marker_is_latest_is_up_to_date():
    versions = [_v(0), _v(1), _v(2)]
    assert compute_sync_state("proj:2", versions) is SyncState.UP_TO_DATE


def test_marker_is_earlier_version_is_remote_ahead():
    versions = [_v(0), _v(1), _v(2)]
    assert compute_sync_state("proj:0", versions) is SyncState.REMOTE_AHEAD


def test_marker_unknown_to_history_is_diverged():
    versions = [_v(0), _v(1)]
    assert compute_sync_state("proj:99", versions) is SyncState.DIVERGED


def test_single_version_matching_marker_up_to_date():
    assert compute_sync_state("proj:0", [_v(0)]) is SyncState.UP_TO_DATE


# --- determinism ------------------------------------------------------------ #


def test_deterministic_same_inputs_same_output():
    versions = [_v(0), _v(1), _v(2)]
    first = compute_sync_state("proj:1", versions)
    second = compute_sync_state("proj:1", versions)
    assert first is second is SyncState.REMOTE_AHEAD


def test_accepts_any_sequence_type():
    # A tuple works identically to a list (result never depends on container).
    assert compute_sync_state("proj:0", (_v(0),)) is SyncState.UP_TO_DATE


# --- malformed input -> SyncError ------------------------------------------- #


def test_empty_local_marker_string_raises():
    with pytest.raises(SyncError):
        compute_sync_state("", [_v(0)])


def test_non_str_local_marker_raises():
    with pytest.raises(SyncError):
        compute_sync_state(123, [_v(0)])  # type: ignore[arg-type]


def test_non_sequence_versions_raises():
    with pytest.raises(SyncError):
        compute_sync_state(None, 42)  # type: ignore[arg-type]


def test_non_cloudversion_member_raises():
    with pytest.raises(SyncError):
        compute_sync_state(None, ["not-a-version"])  # type: ignore[list-item]


# --- vocabulary ------------------------------------------------------------- #


def test_syncstate_values_are_stable_strings():
    assert SyncState.UP_TO_DATE.value == "up_to_date"
    assert SyncState.LOCAL_AHEAD.value == "local_ahead"
    assert SyncState.REMOTE_AHEAD.value == "remote_ahead"
    assert SyncState.DIVERGED.value == "diverged"


def test_error_is_valueerror_subclass():
    assert issubclass(SyncError, ValueError)
