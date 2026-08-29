"""Tests for pixelart_creator.logic.asset_edit_decisions (REQ-P11-DATA-010, ADR-0062, ruling P11-R13).

Covers the ledger's construction validation, the token-supersession property
(``decision_for`` reads *nothing decided* once the stored token no longer
matches — the data-structure form of "a different edit still asks"), the
``merged_with`` journal-over-file precedence, and the sorted, deterministic
``to_serializable`` shape.

No Qt import (S11). This module under test is a leaf: it imports nothing
from ``pixelart_creator`` itself, and neither does this test module.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.asset_edit_decisions import (
    DECISION_DOMAIN,
    DECISION_KEEP,
    DECISION_PICK_UP,
    AssetEditDecisions,
    AssetEditDecisionsError,
    _iter_asset_ids,
)
from pixelart_creator.ui.asset_update_prompt import OUTCOME_KEEP, OUTCOME_PICK_UP

_TOKEN_A = "token-a"
_TOKEN_B = "token-b"


# --------------------------------------------------------------------------- #
# Outcome-string identity with the shipped prompt module                      #
# --------------------------------------------------------------------------- #


class TestOutcomeStringIdentity:
    def test_pick_up_is_byte_identical_to_the_prompt_modules_outcome(self):
        assert DECISION_PICK_UP == OUTCOME_PICK_UP

    def test_keep_is_byte_identical_to_the_prompt_modules_outcome(self):
        assert DECISION_KEEP == OUTCOME_KEEP

    def test_decision_domain_contains_exactly_the_two_outcomes(self):
        assert DECISION_DOMAIN == frozenset({DECISION_PICK_UP, DECISION_KEEP})


# --------------------------------------------------------------------------- #
# Construction validation                                                     #
# --------------------------------------------------------------------------- #


class TestConstruction:
    def test_empty_ledger_has_no_entries(self):
        assert AssetEditDecisions().entries() == ()

    def test_none_rows_builds_an_empty_ledger(self):
        assert AssetEditDecisions(rows=None).entries() == ()

    def test_valid_rows_construct(self):
        ledger = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_PICK_UP)})
        assert ledger.entries() == (("a1", _TOKEN_A, DECISION_PICK_UP),)

    def test_rejects_empty_asset_id(self):
        with pytest.raises(AssetEditDecisionsError):
            AssetEditDecisions({"": (_TOKEN_A, DECISION_PICK_UP)})

    def test_rejects_non_string_asset_id(self):
        with pytest.raises(AssetEditDecisionsError):
            AssetEditDecisions({1: (_TOKEN_A, DECISION_PICK_UP)})

    def test_rejects_empty_edit_token(self):
        with pytest.raises(AssetEditDecisionsError):
            AssetEditDecisions({"a1": ("", DECISION_PICK_UP)})

    def test_rejects_non_string_edit_token(self):
        with pytest.raises(AssetEditDecisionsError):
            AssetEditDecisions({"a1": (123, DECISION_PICK_UP)})

    def test_rejects_out_of_domain_outcome(self):
        with pytest.raises(AssetEditDecisionsError):
            AssetEditDecisions({"a1": (_TOKEN_A, "discard")})

    def test_error_is_a_value_error(self):
        assert issubclass(AssetEditDecisionsError, ValueError)


# --------------------------------------------------------------------------- #
# decision_for -- the token-supersession property                             #
# --------------------------------------------------------------------------- #


class TestDecisionFor:
    def test_returns_none_for_unknown_asset_id(self):
        ledger = AssetEditDecisions()
        assert ledger.decision_for("missing", _TOKEN_A) is None

    def test_returns_the_outcome_when_token_matches(self):
        ledger = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        assert ledger.decision_for("a1", _TOKEN_A) == DECISION_KEEP

    def test_returns_none_when_a_different_edit_token_supersedes(self):
        # The single most important assertion in this module: a superseding
        # token reads as *nothing decided* -- "a different edit still asks".
        ledger = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        assert ledger.decision_for("a1", _TOKEN_B) is None

    def test_rejects_empty_asset_id(self):
        ledger = AssetEditDecisions()
        with pytest.raises(AssetEditDecisionsError):
            ledger.decision_for("", _TOKEN_A)

    def test_rejects_empty_edit_token(self):
        ledger = AssetEditDecisions()
        with pytest.raises(AssetEditDecisionsError):
            ledger.decision_for("a1", "")


# --------------------------------------------------------------------------- #
# with_decision                                                               #
# --------------------------------------------------------------------------- #


class TestWithDecision:
    def test_returns_a_new_ledger_leaving_the_original_untouched(self):
        original = AssetEditDecisions()
        updated = original.with_decision("a1", _TOKEN_A, DECISION_PICK_UP)
        assert original.entries() == ()
        assert updated.decision_for("a1", _TOKEN_A) == DECISION_PICK_UP

    def test_replaces_a_prior_row_for_the_same_asset_id(self):
        ledger = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        updated = ledger.with_decision("a1", _TOKEN_B, DECISION_PICK_UP)
        assert updated.decision_for("a1", _TOKEN_A) is None
        assert updated.decision_for("a1", _TOKEN_B) == DECISION_PICK_UP

    def test_rejects_out_of_domain_outcome(self):
        ledger = AssetEditDecisions()
        with pytest.raises(AssetEditDecisionsError):
            ledger.with_decision("a1", _TOKEN_A, "discard")

    def test_rejects_empty_asset_id(self):
        ledger = AssetEditDecisions()
        with pytest.raises(AssetEditDecisionsError):
            ledger.with_decision("", _TOKEN_A, DECISION_KEEP)

    def test_rejects_empty_edit_token(self):
        ledger = AssetEditDecisions()
        with pytest.raises(AssetEditDecisionsError):
            ledger.with_decision("a1", "", DECISION_KEEP)


# --------------------------------------------------------------------------- #
# merged_with -- journal-over-file precedence                                 #
# --------------------------------------------------------------------------- #


class TestMergedWith:
    def test_other_wins_per_asset_id(self):
        base = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        other = AssetEditDecisions({"a1": (_TOKEN_B, DECISION_PICK_UP)})
        merged = base.merged_with(other)
        assert merged.decision_for("a1", _TOKEN_B) == DECISION_PICK_UP
        assert merged.decision_for("a1", _TOKEN_A) is None

    def test_disjoint_rows_are_all_kept(self):
        base = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        other = AssetEditDecisions({"a2": (_TOKEN_B, DECISION_PICK_UP)})
        merged = base.merged_with(other)
        assert merged.decision_for("a1", _TOKEN_A) == DECISION_KEEP
        assert merged.decision_for("a2", _TOKEN_B) == DECISION_PICK_UP

    def test_merging_with_empty_other_leaves_base_unchanged(self):
        base = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        merged = base.merged_with(AssetEditDecisions())
        assert merged.decision_for("a1", _TOKEN_A) == DECISION_KEEP

    def test_rejects_a_non_ledger_argument(self):
        base = AssetEditDecisions()
        with pytest.raises(AssetEditDecisionsError):
            base.merged_with({"a1": (_TOKEN_A, DECISION_KEEP)})


# --------------------------------------------------------------------------- #
# entries / to_serializable -- deterministic, asset_id-sorted ordering        #
# --------------------------------------------------------------------------- #


class TestOrderingAndSerialization:
    def test_entries_are_sorted_by_asset_id(self):
        ledger = AssetEditDecisions(
            {
                "z9": (_TOKEN_A, DECISION_KEEP),
                "a1": (_TOKEN_B, DECISION_PICK_UP),
                "m5": (_TOKEN_A, DECISION_KEEP),
            }
        )
        ids = [asset_id for asset_id, _, _ in ledger.entries()]
        assert ids == sorted(ids)
        assert ids == ["a1", "m5", "z9"]

    def test_to_serializable_is_sorted_by_asset_id(self):
        ledger = AssetEditDecisions(
            {
                "z9": (_TOKEN_A, DECISION_KEEP),
                "a1": (_TOKEN_B, DECISION_PICK_UP),
            }
        )
        serialised = ledger.to_serializable()
        assert [row["asset_id"] for row in serialised] == ["a1", "z9"]

    def test_to_serializable_row_shape(self):
        ledger = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_PICK_UP)})
        assert ledger.to_serializable() == [
            {"asset_id": "a1", "edit_token": _TOKEN_A, "outcome": DECISION_PICK_UP}
        ]

    def test_empty_ledger_serializes_to_empty_list(self):
        assert AssetEditDecisions().to_serializable() == []


# --------------------------------------------------------------------------- #
# Equality and repr                                                           #
# --------------------------------------------------------------------------- #


class TestEqualityAndRepr:
    def test_equal_rows_compare_equal(self):
        a = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        b = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        assert a == b

    def test_different_rows_compare_unequal(self):
        a = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        b = AssetEditDecisions({"a1": (_TOKEN_B, DECISION_KEEP)})
        assert a != b

    def test_equality_against_a_foreign_type_is_not_implemented(self):
        a = AssetEditDecisions()
        assert a.__eq__(object()) is NotImplemented
        assert a != object()

    def test_repr_shows_the_rows(self):
        ledger = AssetEditDecisions({"a1": (_TOKEN_A, DECISION_KEEP)})
        assert "a1" in repr(ledger)


# --------------------------------------------------------------------------- #
# _iter_asset_ids -- the module-level bound-count convenience                 #
# --------------------------------------------------------------------------- #


class TestIterAssetIds:
    def test_yields_every_asset_id_sorted(self):
        ledger = AssetEditDecisions(
            {
                "z9": (_TOKEN_A, DECISION_KEEP),
                "a1": (_TOKEN_B, DECISION_PICK_UP),
            }
        )
        assert list(_iter_asset_ids(ledger)) == ["a1", "z9"]

    def test_empty_ledger_yields_nothing(self):
        assert list(_iter_asset_ids(AssetEditDecisions())) == []


# --------------------------------------------------------------------------- #
# Property-based invariants                                                   #
# --------------------------------------------------------------------------- #

_asset_ids = st.text(
    min_size=1,
    max_size=8,
    alphabet=st.characters(
        whitelist_categories=("Ll", "Nd"),
    ),
)
_tokens = st.text(
    min_size=1,
    max_size=8,
    alphabet=st.characters(
        whitelist_categories=("Ll", "Nd"),
    ),
)
_outcomes = st.sampled_from(sorted(DECISION_DOMAIN))


@given(asset_id=_asset_ids, token=_tokens, outcome=_outcomes)
def test_with_decision_then_decision_for_round_trips(asset_id, token, outcome):
    ledger = AssetEditDecisions().with_decision(asset_id, token, outcome)
    assert ledger.decision_for(asset_id, token) == outcome


@given(
    asset_id=_asset_ids,
    token=_tokens,
    other_token=_tokens,
    outcome=_outcomes,
)
def test_a_superseding_token_always_reads_as_nothing_decided(
    asset_id, token, other_token, outcome
):
    if other_token == token:
        return
    ledger = AssetEditDecisions().with_decision(asset_id, token, outcome)
    assert ledger.decision_for(asset_id, other_token) is None


@given(
    asset_id=_asset_ids,
    token_a=_tokens,
    outcome_a=_outcomes,
    token_b=_tokens,
    outcome_b=_outcomes,
)
def test_merged_with_other_always_wins_per_asset_id(
    asset_id, token_a, outcome_a, token_b, outcome_b
):
    base = AssetEditDecisions().with_decision(asset_id, token_a, outcome_a)
    other = AssetEditDecisions().with_decision(asset_id, token_b, outcome_b)
    merged = base.merged_with(other)
    assert merged.decision_for(asset_id, token_b) == outcome_b


@given(st.lists(st.tuples(_asset_ids, _tokens, _outcomes), max_size=6))
def test_to_serializable_asset_ids_are_always_sorted(rows):
    ledger = AssetEditDecisions()
    for asset_id, token, outcome in rows:
        ledger = ledger.with_decision(asset_id, token, outcome)
    ids = [row["asset_id"] for row in ledger.to_serializable()]
    assert ids == sorted(ids)
