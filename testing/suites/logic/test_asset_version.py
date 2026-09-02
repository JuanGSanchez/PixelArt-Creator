"""Unit + property tests for ``pixelart_creator.logic.asset_version`` (S11, no Qt).

Covers the immutable, content-hash-addressed asset-revision DAG (ADR-0030 §6;
REQ-P11-LOGIC-006): the history yields ordered immutable descriptors carrying a content
hash + a parent link (a DAG — a forward/self parent link is rejected); ``append``
returns a NEW history and never mutates the prior value in place; the content-hash
change-detector reports "unchanged" for an identical hash and "changed" otherwise; the
count is bounded by ``MAX_ASSET_VERSIONS`` imported from ``logic/constants`` (no
inlined literal 256); the pure model imports no Qt and has no CRDT dependency; and — via
Hypothesis over permuted append sequences — the built history is deterministic /
byte-identical across runs.
"""

from __future__ import annotations

import ast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import asset_version
from pixelart_creator.logic.asset_version import (
    AssetRevision,
    AssetVersionError,
    AssetVersionHistory,
)
from pixelart_creator.logic.constants import MAX_ASSET_VERSIONS
from pixelart_creator.logic.content_hash import content_hash

# Distinct, deterministic content hashes for the fixture revisions.
H0 = content_hash(b"rev-0")
H1 = content_hash(b"rev-1")
H2 = content_hash(b"rev-2")

ASSET = "asset-1"


def rev(marker: int, digest: str, parent: str | None = None, **kwargs) -> AssetRevision:
    """Return an :class:`AssetRevision` for ``ASSET`` with sensible defaults."""
    fields = dict(asset_id=ASSET, content_hash=digest, created_marker=marker)
    fields.update(kwargs)
    return AssetRevision(parent_hash=parent, **fields)


# --------------------------------------------------------------------------- #
# AssetRevision — frozen value + field validation                             #
# --------------------------------------------------------------------------- #


def test_revision_is_frozen_value() -> None:
    r = rev(0, H0)
    assert r == rev(0, H0)
    with pytest.raises(Exception):
        r.content_hash = "changed"  # type: ignore[misc]


def test_revision_rejects_empty_asset_id() -> None:
    with pytest.raises(AssetVersionError):
        AssetRevision(asset_id="", content_hash=H0, created_marker=0)


def test_revision_rejects_non_str_asset_id() -> None:
    with pytest.raises(AssetVersionError):
        AssetRevision(
            asset_id=1,  # type: ignore[arg-type]
            content_hash=H0,
            created_marker=0,
        )


def test_revision_rejects_empty_content_hash() -> None:
    with pytest.raises(AssetVersionError):
        AssetRevision(asset_id=ASSET, content_hash="", created_marker=0)


def test_revision_rejects_non_str_content_hash() -> None:
    with pytest.raises(AssetVersionError):
        AssetRevision(
            asset_id=ASSET,
            content_hash=None,  # type: ignore[arg-type]
            created_marker=0,
        )


def test_revision_rejects_negative_marker() -> None:
    with pytest.raises(AssetVersionError):
        rev(-1, H0)


def test_revision_rejects_bool_marker() -> None:
    # bool is an int subclass but is not a valid ordering marker.
    with pytest.raises(AssetVersionError):
        AssetRevision(
            asset_id=ASSET,
            content_hash=H0,
            created_marker=True,  # type: ignore[arg-type]
        )


def test_revision_rejects_non_int_marker() -> None:
    with pytest.raises(AssetVersionError):
        AssetRevision(
            asset_id=ASSET,
            content_hash=H0,
            created_marker="0",  # type: ignore[arg-type]
        )


def test_revision_rejects_empty_parent_hash() -> None:
    with pytest.raises(AssetVersionError):
        rev(0, H0, parent="")


def test_revision_rejects_empty_author() -> None:
    with pytest.raises(AssetVersionError):
        rev(0, H0, author="")


def test_revision_accepts_optional_author_and_parent() -> None:
    r = rev(1, H1, parent=H0, author="alice")
    assert r.parent_hash == H0
    assert r.author == "alice"


def test_revision_rejects_self_parent() -> None:
    # A revision cannot be its own parent (no self-loop -> acyclic).
    with pytest.raises(AssetVersionError):
        rev(0, H0, parent=H0)


# --------------------------------------------------------------------------- #
# AssetVersionHistory — ordered, immutable, DAG                               #
# --------------------------------------------------------------------------- #


def test_empty_history_defaults_to_no_revisions() -> None:
    h = AssetVersionHistory()
    assert h.revisions == ()
    assert h.is_empty() is True


def test_history_yields_ordered_descriptors_with_parent_links() -> None:
    # Ordered immutable descriptors, each carrying a content hash and a parent link.
    h = AssetVersionHistory(
        revisions=(rev(0, H0), rev(1, H1, parent=H0), rev(2, H2, parent=H1))
    )
    assert [r.content_hash for r in h.revisions] == [H0, H1, H2]
    assert [r.parent_hash for r in h.revisions] == [None, H0, H1]
    # The revisions tuple is immutable.
    with pytest.raises(Exception):
        h.revisions[0] = rev(9, H2)  # type: ignore[index]


def test_history_rejects_non_revision_member() -> None:
    # Regression: a non-AssetRevision member must raise the domain AssetVersionError
    # (not leak an AttributeError) from the constructor's per-member guard.
    with pytest.raises(AssetVersionError):
        AssetVersionHistory(revisions=("not-a-revision",))  # type: ignore[arg-type]


def test_history_rejects_mixed_asset_ids() -> None:
    other = AssetRevision(asset_id="asset-2", content_hash=H1, created_marker=1)
    with pytest.raises(AssetVersionError):
        AssetVersionHistory(revisions=(rev(0, H0), other))


def test_history_rejects_forward_parent_link() -> None:
    # rev0.parent references H1, which appears LATER -> not an earlier revision, so the
    # parent links do not form a DAG and construction is rejected.
    with pytest.raises(AssetVersionError):
        AssetVersionHistory(revisions=(rev(0, H0, parent=H1), rev(1, H1)))


def test_history_allows_out_of_history_root_parent() -> None:
    # A parent_hash that names no revision in this history is an out-of-history root
    # (allowed) — only a link to a *later in-history* revision is a cycle.
    external = content_hash(b"external-root")
    h = AssetVersionHistory(revisions=(rev(0, H0, parent=external),))
    assert h.head().parent_hash == external


# --------------------------------------------------------------------------- #
# append — returns a NEW history, no in-place mutation                         #
# --------------------------------------------------------------------------- #


def test_append_returns_new_history_leaving_original_unchanged() -> None:
    base = AssetVersionHistory(revisions=(rev(0, H0),))
    grown = base.append(rev(1, H1, parent=H0))
    # The prior history value is not mutated in place.
    assert base.revisions == (rev(0, H0),)
    assert [r.content_hash for r in grown.revisions] == [H0, H1]
    assert grown is not base


def test_append_rejects_non_revision() -> None:
    with pytest.raises(AssetVersionError):
        AssetVersionHistory().append("nope")  # type: ignore[arg-type]


def test_append_rejects_foreign_asset_id() -> None:
    # Appending a revision that belongs to a different asset breaks the single-asset
    # history invariant.
    base = AssetVersionHistory(revisions=(rev(0, H0),))
    foreign = AssetRevision(asset_id="asset-2", content_hash=H1, created_marker=1)
    with pytest.raises(AssetVersionError):
        base.append(foreign)


# --------------------------------------------------------------------------- #
# head / by_hash                                                              #
# --------------------------------------------------------------------------- #


def test_head_returns_most_recent_revision() -> None:
    h = AssetVersionHistory(revisions=(rev(0, H0), rev(1, H1, parent=H0)))
    assert h.head().content_hash == H1


def test_head_on_empty_history_raises() -> None:
    with pytest.raises(AssetVersionError):
        AssetVersionHistory().head()


def test_by_hash_returns_matching_revision() -> None:
    h = AssetVersionHistory(revisions=(rev(0, H0), rev(1, H1, parent=H0)))
    assert h.by_hash(H0).created_marker == 0


def test_by_hash_missing_raises() -> None:
    h = AssetVersionHistory(revisions=(rev(0, H0),))
    with pytest.raises(AssetVersionError):
        h.by_hash(H2)


# --------------------------------------------------------------------------- #
# is_unchanged — the content-hash change-detector                             #
# --------------------------------------------------------------------------- #


def test_is_unchanged_true_for_head_hash() -> None:
    h = AssetVersionHistory(revisions=(rev(0, H0), rev(1, H1, parent=H0)))
    assert h.is_unchanged(H1) is True


def test_is_unchanged_false_for_changed_hash() -> None:
    h = AssetVersionHistory(revisions=(rev(0, H0),))
    assert h.is_unchanged(H1) is False


def test_is_unchanged_false_on_empty_history() -> None:
    assert AssetVersionHistory().is_unchanged(H0) is False


# --------------------------------------------------------------------------- #
# MAX_ASSET_VERSIONS bound — from logic/constants, not an inlined literal      #
# --------------------------------------------------------------------------- #


def test_version_bound_is_the_named_constant() -> None:
    # The single-source constant (no magic literal 256, S12).
    assert asset_version.MAX_ASSET_VERSIONS is MAX_ASSET_VERSIONS


def _roots(count: int) -> tuple[AssetRevision, ...]:
    """Return ``count`` independent root revisions (all parent_hash None)."""
    return tuple(rev(i, content_hash(f"r{i}".encode())) for i in range(count))


def test_constructor_at_bound_ok_over_bound_rejected(monkeypatch) -> None:
    monkeypatch.setattr(asset_version, "MAX_ASSET_VERSIONS", 3)
    # Exactly at the cap is accepted.
    h = AssetVersionHistory(revisions=_roots(3))
    assert len(h.revisions) == 3
    # One over the cap is rejected.
    with pytest.raises(AssetVersionError):
        AssetVersionHistory(revisions=_roots(4))


def test_append_at_bound_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(asset_version, "MAX_ASSET_VERSIONS", 3)
    full = AssetVersionHistory(revisions=_roots(3))
    with pytest.raises(AssetVersionError):
        full.append(rev(99, content_hash(b"one-too-many")))


# --------------------------------------------------------------------------- #
# No Qt / no CRDT dependency (import-graph scan of the module source)          #
# --------------------------------------------------------------------------- #


def _imported_names(module) -> list[str]:
    """Return every module name imported by ``module`` (via an AST scan)."""
    with open(module.__file__, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_module_imports_no_qt_and_no_crdt() -> None:
    for name in _imported_names(asset_version):
        lowered = name.lower()
        parts = lowered.split(".")
        # No Qt binding import (PySide6 / PyQt / a bare ``qt`` package component).
        assert not lowered.startswith(("pyside", "pyqt"))
        assert "qt" not in parts
        # Asset revisions never route through the live-collab CRDT.
        assert "crdt" not in parts


# --------------------------------------------------------------------------- #
# Determinism (Hypothesis) — permuted append sequences are byte-identical      #
# --------------------------------------------------------------------------- #


@st.composite
def _root_revisions(draw):
    """Draw a set of independent root revisions (unique content hashes)."""
    n = draw(st.integers(min_value=1, max_value=8))
    markers = draw(
        st.lists(
            st.integers(min_value=0, max_value=10_000),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    return [rev(m, content_hash(f"m{m}".encode())) for m in markers]


@given(revisions=_root_revisions(), data=st.data())
def test_append_sequence_is_deterministic_and_immutable(revisions, data) -> None:
    order = data.draw(st.permutations(revisions))

    # Building the same permuted sequence twice yields byte-identical histories.
    def build() -> AssetVersionHistory:
        history = AssetVersionHistory()
        snapshots = []
        for revision in order:
            snapshots.append(history.revisions)  # capture BEFORE the append
            history = history.append(revision)
            # Immutability: the pre-append value was not mutated in place.
            assert history.revisions[:-1] == snapshots[-1]
        return history

    first = build()
    second = build()
    assert first == second  # deterministic / byte-identical across runs
    assert first.revisions == second.revisions
    # Head + change-detector track the last-appended revision.
    assert first.head() == order[-1]
    assert first.is_unchanged(order[-1].content_hash) is True
    assert len(first.revisions) == len(revisions)
