"""Tests for pixelart_creator.logic.version_history (Phase-10 Slice A, no Qt).

Covers the ordered, immutable :class:`VersionHistory` and its
:class:`CloudVersion` envelope (REQ-P10-LOGIC-003 / REQ-P10-DATA-003):
field validation, the version envelope (ordinal / created_marker / parent /
remote-revision map), strictly-ascending ordering, uniqueness, immutability,
``append``/``latest``/``by_id``, and the ``MAX_CLOUD_VERSIONS`` retention cap.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import version_history as vh
from pixelart_creator.logic.constants import (
    MAX_CLOUD_PROJECT_BYTES,
    MAX_CLOUD_VERSIONS,
)
from pixelart_creator.logic.version_history import (
    CloudVersion,
    VersionHistory,
    VersionHistoryError,
)


def _v(
    ordinal: int,
    *,
    marker: int | None = None,
    parent: str | None = None,
    remote: str | None = None,
) -> CloudVersion:
    return CloudVersion(
        version_id=f"proj:{ordinal}",
        ordinal=ordinal,
        created_marker=ordinal if marker is None else marker,
        size_bytes=10,
        parent_version_id=parent,
        remote_revision_id=remote,
    )


# --- CloudVersion validation ------------------------------------------------ #


def test_cloud_version_valid_envelope_fields():
    v = _v(3, marker=7, parent="proj:2", remote="rev-abc")
    assert v.version_id == "proj:3"
    assert v.ordinal == 3
    assert v.created_marker == 7
    assert v.size_bytes == 10
    assert v.is_pinned is False
    assert v.parent_version_id == "proj:2"
    # remote-revisionId mapping (BF-2 local -> remote).
    assert v.remote_revision_id == "rev-abc"


def test_cloud_version_is_frozen():
    v = _v(0)
    with pytest.raises(Exception):
        v.ordinal = 5  # type: ignore[misc]


@pytest.mark.parametrize("bad_id", ["", 123, None])
def test_cloud_version_rejects_bad_version_id(bad_id):
    with pytest.raises(VersionHistoryError):
        CloudVersion(version_id=bad_id, ordinal=0, created_marker=0, size_bytes=0)


@pytest.mark.parametrize("field", ["ordinal", "created_marker", "size_bytes"])
def test_cloud_version_rejects_negative_ints(field):
    kwargs = {"version_id": "p:0", "ordinal": 0, "created_marker": 0, "size_bytes": 0}
    kwargs[field] = -1
    with pytest.raises(VersionHistoryError):
        CloudVersion(**kwargs)


@pytest.mark.parametrize("field", ["ordinal", "created_marker", "size_bytes"])
def test_cloud_version_rejects_bool_and_non_int(field):
    kwargs = {"version_id": "p:0", "ordinal": 0, "created_marker": 0, "size_bytes": 0}
    kwargs[field] = True  # bool is not an int for our purposes
    with pytest.raises(VersionHistoryError):
        CloudVersion(**kwargs)
    kwargs[field] = 1.5
    with pytest.raises(VersionHistoryError):
        CloudVersion(**kwargs)


def test_cloud_version_size_cap_enforced():
    # Boundary: exactly at the cap is allowed; one over raises.
    CloudVersion(
        version_id="p:0",
        ordinal=0,
        created_marker=0,
        size_bytes=MAX_CLOUD_PROJECT_BYTES,
    )
    with pytest.raises(VersionHistoryError):
        CloudVersion(
            version_id="p:0",
            ordinal=0,
            created_marker=0,
            size_bytes=MAX_CLOUD_PROJECT_BYTES + 1,
        )


def test_cloud_version_rejects_non_bool_pinned():
    with pytest.raises(VersionHistoryError):
        CloudVersion(
            version_id="p:0",
            ordinal=0,
            created_marker=0,
            size_bytes=0,
            is_pinned="yes",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("field", ["parent_version_id", "remote_revision_id"])
def test_cloud_version_optional_str_fields(field):
    # None is allowed; empty / non-str is rejected.
    kwargs = {"version_id": "p:0", "ordinal": 0, "created_marker": 0, "size_bytes": 0}
    kwargs[field] = None
    CloudVersion(**kwargs)  # ok
    kwargs[field] = ""
    with pytest.raises(VersionHistoryError):
        CloudVersion(**kwargs)
    kwargs[field] = 5
    with pytest.raises(VersionHistoryError):
        CloudVersion(**kwargs)


# --- VersionHistory invariants ---------------------------------------------- #


def test_empty_history_defaults():
    h = VersionHistory()
    assert h.versions == ()
    with pytest.raises(VersionHistoryError):
        h.latest()


def test_append_is_pure_and_immutable():
    h0 = VersionHistory()
    h1 = h0.append(_v(0))
    h2 = h1.append(_v(1))
    # Prior instances are never mutated.
    assert h0.versions == ()
    assert len(h1.versions) == 1
    assert len(h2.versions) == 2
    assert h2 is not h1


def test_latest_and_by_id():
    h = VersionHistory().append(_v(0)).append(_v(1)).append(_v(2))
    assert h.latest().version_id == "proj:2"
    assert h.by_id("proj:1").ordinal == 1
    with pytest.raises(VersionHistoryError):
        h.by_id("proj:99")


def test_ordering_is_deterministic_ascending_ordinal():
    versions = tuple(_v(i) for i in range(5))
    h = VersionHistory(versions=versions)
    assert [v.ordinal for v in h.versions] == [0, 1, 2, 3, 4]


def test_history_rejects_non_ascending_ordinals():
    with pytest.raises(VersionHistoryError):
        VersionHistory(versions=(_v(1), _v(1)))  # not strictly ascending
    with pytest.raises(VersionHistoryError):
        VersionHistory(versions=(_v(3), _v(2)))  # descending


def test_history_rejects_duplicate_ids():
    dup = CloudVersion(version_id="same", ordinal=0, created_marker=0, size_bytes=0)
    dup2 = CloudVersion(version_id="same", ordinal=1, created_marker=1, size_bytes=0)
    with pytest.raises(VersionHistoryError):
        VersionHistory(versions=(dup, dup2))


def test_history_rejects_non_cloudversion_member():
    with pytest.raises(VersionHistoryError):
        VersionHistory(versions=("not-a-version",))  # type: ignore[arg-type]


def test_append_rejects_non_cloudversion():
    with pytest.raises(VersionHistoryError):
        VersionHistory().append("nope")  # type: ignore[arg-type]


def test_append_rejects_non_ascending():
    h = VersionHistory().append(_v(2))
    with pytest.raises(VersionHistoryError):
        h.append(_v(2))  # equal ordinal is not strictly ascending


# --- retention cap (MAX_CLOUD_VERSIONS), boundary + over -------------------- #


def test_retention_cap_boundary_and_over_via_constructor():
    at_cap = tuple(_v(i) for i in range(MAX_CLOUD_VERSIONS))
    h = VersionHistory(versions=at_cap)  # exactly at the cap is allowed
    assert len(h.versions) == MAX_CLOUD_VERSIONS
    with pytest.raises(VersionHistoryError):
        VersionHistory(versions=at_cap + (_v(MAX_CLOUD_VERSIONS),))


def test_append_at_cap_raises():
    at_cap = VersionHistory(versions=tuple(_v(i) for i in range(MAX_CLOUD_VERSIONS)))
    with pytest.raises(VersionHistoryError):
        at_cap.append(_v(MAX_CLOUD_VERSIONS))


def test_retention_cap_uses_constant_not_literal(monkeypatch):
    # Prove the cap is single-sourced: shrink it and the smaller cap is honoured.
    monkeypatch.setattr(vh, "MAX_CLOUD_VERSIONS", 2)
    h = VersionHistory().append(_v(0)).append(_v(1))
    with pytest.raises(VersionHistoryError):
        h.append(_v(2))


# --- exception hierarchy ---------------------------------------------------- #


def test_error_is_valueerror_subclass():
    assert issubclass(VersionHistoryError, ValueError)


# --- property: append preserves ascending order + immutability -------------- #


@given(n=st.integers(min_value=0, max_value=30))
def test_property_appended_history_is_sorted_and_unique(n):
    h = VersionHistory()
    for i in range(n):
        h = h.append(_v(i))
    ordinals = [v.ordinal for v in h.versions]
    ids = [v.version_id for v in h.versions]
    assert ordinals == sorted(ordinals)
    assert len(set(ordinals)) == len(ordinals)
    assert len(set(ids)) == len(ids)
