"""Tests for pixelart_creator.logic.autosave (Phase-10 Slice A, no Qt).

Covers the pure autosave-policy decision function :func:`should_autosave`
(REQ-P10-LOGIC-002): the dirty + elapsed-interval decision, the default
``AUTOSAVE_INTERVAL_MS`` threshold, the monotonic-tick contract, and malformed
inputs. Includes a Hypothesis property test pinning the exact decision rule.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.autosave import AutosaveError, should_autosave
from pixelart_creator.logic.constants import AUTOSAVE_INTERVAL_MS

# --- decision logic --------------------------------------------------------- #


def test_clean_document_never_autosaves():
    assert should_autosave(False, 10_000_000, 0) is False


def test_dirty_and_interval_elapsed_is_true():
    assert should_autosave(True, AUTOSAVE_INTERVAL_MS, 0) is True


def test_dirty_but_not_yet_elapsed_is_false():
    assert should_autosave(True, AUTOSAVE_INTERVAL_MS - 1, 0) is False


def test_boundary_exactly_at_interval_is_true():
    # elapsed - last == interval -> due (>=).
    assert should_autosave(True, 500, 200, interval_ms=300) is True


def test_boundary_one_below_interval_is_false():
    assert should_autosave(True, 499, 200, interval_ms=300) is False


def test_custom_interval_overrides_default():
    assert should_autosave(True, 5, 0, interval_ms=5) is True
    assert should_autosave(True, 4, 0, interval_ms=5) is False


def test_uses_constant_default_when_interval_omitted():
    # Just under the single-sourced default is not due.
    assert should_autosave(True, AUTOSAVE_INTERVAL_MS - 1, 0) is False
    assert should_autosave(True, AUTOSAVE_INTERVAL_MS, 0) is True


# --- monotonic-tick contract + malformed inputs ----------------------------- #


def test_non_bool_dirty_raises():
    with pytest.raises(AutosaveError):
        should_autosave("yes", 10, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [-1, 1.5, "x", True])
def test_bad_elapsed_ticks_raises(bad):
    with pytest.raises(AutosaveError):
        should_autosave(True, bad, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [-1, 2.0, None, False])
def test_bad_last_marker_raises(bad):
    with pytest.raises(AutosaveError):
        should_autosave(True, 10, bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [0, -5, 1.5, True])
def test_bad_interval_raises(bad):
    with pytest.raises(AutosaveError):
        should_autosave(True, 10, 0, interval_ms=bad)  # type: ignore[arg-type]


def test_non_monotonic_ticks_raise():
    # elapsed_ticks < last_autosave_marker violates the monotonic contract.
    with pytest.raises(AutosaveError):
        should_autosave(True, 50, 100)


def test_equal_ticks_are_allowed():
    # elapsed == last is monotonic-valid; decision is "not due yet".
    assert should_autosave(True, 100, 100, interval_ms=10) is False


# --- exception hierarchy ---------------------------------------------------- #


def test_error_is_valueerror_subclass():
    assert issubclass(AutosaveError, ValueError)


# --- property: exact decision rule ------------------------------------------ #


@given(
    dirty=st.booleans(),
    last=st.integers(min_value=0, max_value=1_000_000),
    delta=st.integers(min_value=0, max_value=1_000_000),
    interval=st.integers(min_value=1, max_value=1_000_000),
)
def test_property_matches_reference_rule(dirty, last, delta, interval):
    elapsed = last + delta  # guarantees the monotonic contract holds
    expected = bool(dirty and (elapsed - last) >= interval)
    assert should_autosave(dirty, elapsed, last, interval_ms=interval) is expected
