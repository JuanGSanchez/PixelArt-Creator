"""Unit tests for :mod:`pixelart_creator.logic.asset_references` (S11, no Qt).

Covers the three-state predicate (``REQ-P11-UI-021``, ``-022``; plan.md ruling
P11-R9 §3.11 (1)/(1b)): the three states (``STATE_RESOLVED`` / ``STATE_EDITED`` /
``STATE_MISSING``) constructed from concrete values, the invariant tying
``missing()``'s membership to ``reference_states()`` (the regression contract named
in plan §3.11 (1b) — "the test that catches a future
widening of ``missing()``"), the ``edited_ids`` / ``edit_tokens`` subset and keys
relationship, the token's source (the catalog entry's *current* ``content_hash``,
never the reference's own), and ground 4 of the same ruling: a restored earlier
revision presents as ``STATE_EDITED`` by design, never as a false-positive
``STATE_RESOLVED``.

Pure logic only: no Qt import, no ``data/`` import, no I/O.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import asset_references
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_references import (
    STATE_EDITED,
    STATE_MISSING,
    STATE_RESOLVED,
    AssetReference,
    ReferenceSet,
    edit_tokens,
    edited_ids,
    missing,
    reference_states,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def make_reference(
    asset_id: str = "asset-1",
    content_hash: str = HASH_A,
    kind: AssetKind = AssetKind.SPRITE,
    last_known_name: str = "",
) -> AssetReference:
    return AssetReference(
        asset_id=asset_id,
        content_hash=content_hash,
        kind=kind,
        last_known_name=last_known_name,
    )


def make_descriptor(
    asset_id: str = "asset-1",
    content_hash: str = HASH_A,
    kind: AssetKind = AssetKind.SPRITE,
    name: str = "Hero",
) -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=content_hash,
    )


# --------------------------------------------------------------------------- #
# Module hygiene: zero Qt, zero data/ import (S11)                           #
# --------------------------------------------------------------------------- #


def test_module_imports_no_qt_symbol_and_no_data_module() -> None:
    """The module under test imports no Qt symbol and no ``data/`` module.

    Parses the module's own source with ``ast`` (no reliance on what happens to be
    importable in this environment) and inspects every ``import`` / ``from ... import``
    statement's dotted root.
    """
    module_path = Path(asset_references.__file__)
    tree = ast.parse(module_path.read_bytes(), filename=str(module_path))

    qt_markers = ("PySide6", "PyQt5", "PyQt6", "shiboken6", "shiboken2")
    roots = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.append(node.module)

    for root in roots:
        assert not any(
            root.startswith(marker) for marker in qt_markers
        ), f"unexpected Qt import: {root!r}"
        assert "pixelart_creator.data" not in root, f"unexpected data/ import: {root!r}"
        assert not root.startswith(
            "pixelart_creator.ui"
        ), f"unexpected ui import: {root!r}"


# --------------------------------------------------------------------------- #
# The three states, constructed from concrete values                          #
# --------------------------------------------------------------------------- #


class TestThreeStates:
    def test_present_and_equal_hash_is_resolved(self) -> None:
        rs = ReferenceSet(references=(make_reference(content_hash=HASH_A),))
        catalog = AssetCatalog(descriptors=(make_descriptor(content_hash=HASH_A),))

        states = reference_states(rs, catalog)

        assert states == {"asset-1": STATE_RESOLVED}

    def test_present_and_different_hash_is_edited(self) -> None:
        rs = ReferenceSet(references=(make_reference(content_hash=HASH_A),))
        catalog = AssetCatalog(descriptors=(make_descriptor(content_hash=HASH_B),))

        states = reference_states(rs, catalog)

        assert states == {"asset-1": STATE_EDITED}

    def test_absent_is_missing(self) -> None:
        rs = ReferenceSet(references=(make_reference(asset_id="ghost"),))
        catalog = AssetCatalog(descriptors=())

        states = reference_states(rs, catalog)

        assert states == {"ghost": STATE_MISSING}


# --------------------------------------------------------------------------- #
# The missing() equality, asserted over a set mixing all three states         #
# --------------------------------------------------------------------------- #


def _mixed_fixture():
    """A reference set with one member in each of the three states."""
    rs = ReferenceSet(
        references=(
            make_reference(asset_id="resolved-1", content_hash=HASH_A),
            make_reference(asset_id="edited-1", content_hash=HASH_A),
            make_reference(asset_id="missing-1", content_hash=HASH_A),
        )
    )
    catalog = AssetCatalog(
        descriptors=(
            make_descriptor(asset_id="resolved-1", content_hash=HASH_A),
            make_descriptor(asset_id="edited-1", content_hash=HASH_B),
            # "missing-1" has no catalog entry at all.
        )
    )
    return rs, catalog


def test_missing_equality_holds_over_a_set_mixing_all_three_states() -> None:
    """``missing(...) == {id : state != STATE_RESOLVED}`` — the widening guard.

    This is what the regression contract names explicitly as "the test that
    catches a future widening of ``missing()``": if a future change made
    ``missing()`` disagree with ``reference_states()`` (e.g. by adding a fourth
    state that ``missing()`` failed to treat as unresolved, or by narrowing
    ``missing()`` to only one of EDITED/MISSING), this assertion fails.
    """
    rs, catalog = _mixed_fixture()

    states = reference_states(rs, catalog)
    expected = {
        asset_id: state for asset_id, state in states.items() if state != STATE_RESOLVED
    }

    assert missing(rs, catalog) == frozenset(expected.keys())
    # Sanity: the fixture really does mix all three states.
    assert set(states.values()) == {STATE_RESOLVED, STATE_EDITED, STATE_MISSING}


@given(
    st.dictionaries(
        keys=st.text(alphabet="abcXYZ012-", min_size=1, max_size=8),
        values=st.sampled_from(["resolved", "edited", "missing"]),
        max_size=12,
    )
)
def test_missing_equality_property(spec: dict) -> None:
    """Property: for any constructed (rs, catalog) pair, the equality holds.

    ``spec`` maps each synthetic asset_id to the state it should land in;
    the reference set and catalog are built to realise exactly that.
    """
    references = []
    descriptors = []
    for asset_id, state in spec.items():
        references.append(make_reference(asset_id=asset_id, content_hash=HASH_A))
        if state == "resolved":
            descriptors.append(make_descriptor(asset_id=asset_id, content_hash=HASH_A))
        elif state == "edited":
            descriptors.append(make_descriptor(asset_id=asset_id, content_hash=HASH_B))
        # "missing": no descriptor at all.

    rs = ReferenceSet(references=tuple(references))
    catalog = AssetCatalog(descriptors=tuple(descriptors))

    states = reference_states(rs, catalog)
    expected = frozenset(
        asset_id for asset_id, state in states.items() if state != STATE_RESOLVED
    )

    assert missing(rs, catalog) == expected


# --------------------------------------------------------------------------- #
# edited_ids subset of missing; edit_tokens.keys() == edited_ids              #
# --------------------------------------------------------------------------- #


class TestEditedIdsAndTokens:
    def test_edited_ids_is_subset_of_missing(self) -> None:
        rs, catalog = _mixed_fixture()

        ids = edited_ids(rs, catalog)
        miss = missing(rs, catalog)

        assert ids <= miss
        assert ids == {"edited-1"}

    def test_edit_tokens_keys_equal_edited_ids(self) -> None:
        rs, catalog = _mixed_fixture()

        ids = edited_ids(rs, catalog)
        tokens = edit_tokens(rs, catalog)

        assert set(tokens.keys()) == ids

    def test_edit_token_equals_catalog_entrys_current_content_hash(self) -> None:
        rs = ReferenceSet(references=(make_reference(content_hash=HASH_A),))
        catalog = AssetCatalog(descriptors=(make_descriptor(content_hash=HASH_B),))

        tokens = edit_tokens(rs, catalog)

        # The token is the CATALOG entry's current hash, never the reference's own.
        assert tokens["asset-1"] == HASH_B
        assert tokens["asset-1"] != HASH_A

    def test_second_edit_yields_a_different_token(self) -> None:
        """SC-P11-UI-022-4 rests on this: a further edit must move the token."""
        rs = ReferenceSet(references=(make_reference(content_hash=HASH_A),))
        catalog_first_edit = AssetCatalog(
            descriptors=(make_descriptor(content_hash=HASH_B),)
        )
        catalog_second_edit = AssetCatalog(
            descriptors=(make_descriptor(content_hash=HASH_C),)
        )

        token_1 = edit_tokens(rs, catalog_first_edit)["asset-1"]
        token_2 = edit_tokens(rs, catalog_second_edit)["asset-1"]

        assert token_1 != token_2


@given(
    st.dictionaries(
        keys=st.text(alphabet="abcXYZ012-", min_size=1, max_size=8),
        values=st.sampled_from(["resolved", "edited", "missing"]),
        max_size=12,
    )
)
def test_edited_ids_subset_and_tokens_keys_property(spec: dict) -> None:
    """Property: ``edited_ids ⊆ missing`` and ``edit_tokens.keys() == edited_ids``
    hold for any constructed (rs, catalog) pair."""
    references = []
    descriptors = []
    for asset_id, state in spec.items():
        references.append(make_reference(asset_id=asset_id, content_hash=HASH_A))
        if state == "resolved":
            descriptors.append(make_descriptor(asset_id=asset_id, content_hash=HASH_A))
        elif state == "edited":
            descriptors.append(make_descriptor(asset_id=asset_id, content_hash=HASH_B))

    rs = ReferenceSet(references=tuple(references))
    catalog = AssetCatalog(descriptors=tuple(descriptors))

    ids = edited_ids(rs, catalog)
    miss = missing(rs, catalog)
    tokens = edit_tokens(rs, catalog)

    assert ids <= miss
    assert set(tokens.keys()) == ids


# --------------------------------------------------------------------------- #
# Ground 4: a restored earlier revision presents as EDITED, by design         #
# --------------------------------------------------------------------------- #


def test_restored_earlier_revision_presents_as_edited() -> None:
    """plan.md §3.11 (1) ground 4: restoring an earlier revision appends a new
    head (append-only), so the catalog's current hash differs from the
    reference's own and the state reads EDITED — never MISSING, and never a
    false-positive RESOLVED just because the content was seen before.

    Asserted here explicitly so this reading is never later "fixed" as a bug:
    the predicate reports a difference between the two hashes, never an intent
    about which direction the content moved.
    """
    # The project's reference was made against the original content (HASH_A).
    rs = ReferenceSet(references=(make_reference(content_hash=HASH_A),))

    # The library asset was edited to HASH_B, then RESTORED to the earlier
    # revision HASH_A by appending a new head whose hash is HASH_A again is
    # impossible to distinguish from "never changed" purely by hash value, so
    # the meaningful case is: an editor restores an *earlier* library revision
    # that is NOT the one this particular reference was made against — the
    # catalog's current hash (HASH_C, the restored-to revision) still differs
    # from the reference's own (HASH_A).
    catalog_after_restore = AssetCatalog(
        descriptors=(make_descriptor(content_hash=HASH_C),)
    )

    state = reference_states(rs, catalog_after_restore)["asset-1"]

    assert state == STATE_EDITED
    assert "asset-1" in edited_ids(rs, catalog_after_restore)


def test_restore_back_to_the_referenced_hash_reads_resolved_not_a_false_edit() -> None:
    """Complementary case: if the library is restored to exactly the hash this
    reference was made against, the comparison is a pure equality test and the
    state is RESOLVED — the predicate never inspects revision history or
    "was this reverted" intent, only the current hash pair (plan §3.11 (1)/(3)).
    """
    rs = ReferenceSet(references=(make_reference(content_hash=HASH_A),))
    catalog_restored_to_original = AssetCatalog(
        descriptors=(make_descriptor(content_hash=HASH_A),)
    )

    state = reference_states(rs, catalog_restored_to_original)["asset-1"]

    assert state == STATE_RESOLVED


# --------------------------------------------------------------------------- #
# No I/O: reference_states/edited_ids/edit_tokens/missing take no other input #
# --------------------------------------------------------------------------- #


def test_functions_are_pure_same_inputs_same_outputs() -> None:
    rs, catalog = _mixed_fixture()

    first = reference_states(rs, catalog)
    second = reference_states(rs, catalog)

    assert first == second
    assert edited_ids(rs, catalog) == edited_ids(rs, catalog)
    assert edit_tokens(rs, catalog) == edit_tokens(rs, catalog)
