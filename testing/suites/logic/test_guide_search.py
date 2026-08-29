"""Tests for pixelart_creator.logic.guide_search (zero Qt) — the pure search query.

Covers REQ-UG-LOGIC-003: a pure, deterministic, case-insensitive query over each
topic's indexed text (title + keywords + summary), returned in model order and capped
at GUIDE_SEARCH_RESULT_CAP. Maps to Gherkin SC-L003-1 (a term finds its topic),
SC-L003-2 (case-insensitive/deterministic) and SC-L003-3 (empty term -> full set).

The cap assertions prove GUIDE_SEARCH_RESULT_CAP is enforced as the named constant.
Hypothesis property tests assert results are always a subset of the model's topics,
always <= cap, and order-preserving.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.constants import GUIDE_SEARCH_RESULT_CAP
from pixelart_creator.logic.guide_model import (
    GuideModel,
    GuideSection,
    GuideTopic,
    Manifest,
    build_model,
)
from pixelart_creator.logic.guide_search import indexed_text, query

# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #


def _topic(tid, *, title=None, keywords=(), summary="") -> GuideTopic:
    return GuideTopic(
        id=tid,
        title=title if title is not None else tid,
        content_ref=tid,
        keywords=tuple(keywords),
        summary=summary,
    )


def _model(topics: tuple[GuideTopic, ...]) -> GuideModel:
    manifest = Manifest(
        schema_version=1,
        default_locale="en",
        sections=(GuideSection(id="s1", title="S1", topics=topics),),
    )
    return build_model(manifest)


_SAMPLE = _model(
    (
        _topic("layers", title="Layers", keywords=("opacity", "blend modes")),
        _topic(
            "animation-timeline",
            title="Animation Timeline",
            keywords=("onion skinning", "frames"),
        ),
        _topic(
            "export-and-pipeline",
            title="Export & Pipeline",
            keywords=("export", "sprite sheet"),
        ),
    )
)


# --------------------------------------------------------------------------- #
# indexed_text                                                                #
# --------------------------------------------------------------------------- #


def test_indexed_text_is_lowercased_title_keywords_summary():
    topic = _topic("t", title="Layers", keywords=("Opacity", "BLEND"), summary="Group")
    text = indexed_text(topic)
    assert text == "layers opacity blend group"
    assert text == text.lower()


def test_indexed_text_excludes_content_ref_and_id_only_metadata():
    """Body/content_ref is not part of the index (CL-2)."""
    topic = _topic("secret-ref", title="Title", keywords=(), summary="Sum")
    assert "secret-ref" not in indexed_text(topic)


# --------------------------------------------------------------------------- #
# REQ-UG-LOGIC-003 — matching                                                 #
# --------------------------------------------------------------------------- #


def test_query_finds_topic_by_keyword():
    """SC-L003-1: a term in a topic's indexed text returns that topic."""
    results = query(_SAMPLE, "onion skinning")
    assert [t.id for t in results] == ["animation-timeline"]


def test_query_finds_topic_by_title():
    results = query(_SAMPLE, "export")
    assert [t.id for t in results] == ["export-and-pipeline"]


def test_query_is_case_insensitive():
    """SC-L003-2: case does not change the result."""
    assert query(_SAMPLE, "LAYERS") == query(_SAMPLE, "layers")
    assert [t.id for t in query(_SAMPLE, "LAYERS")] == ["layers"]


def test_query_no_match_returns_empty():
    assert query(_SAMPLE, "no-such-term-xyz") == ()


def test_query_preserves_model_order():
    """Multiple matches keep the model's section->topic order."""
    model = _model(
        (
            _topic("a", title="shared alpha"),
            _topic("b", title="shared beta"),
            _topic("c", title="shared gamma"),
        )
    )
    assert [t.id for t in query(model, "shared")] == ["a", "b", "c"]


# --------------------------------------------------------------------------- #
# SC-L003-3 — empty / whitespace term                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("term", ["", "   ", "\t\n"])
def test_empty_or_whitespace_term_returns_full_topic_set(term):
    """SC-L003-3: an empty/whitespace term returns the full topic set."""
    assert query(_SAMPLE, term) == _SAMPLE.topics()


# --------------------------------------------------------------------------- #
# cap — GUIDE_SEARCH_RESULT_CAP is enforced (a constant, not a literal)       #
# --------------------------------------------------------------------------- #


def test_default_cap_equals_named_constant():
    """The default cap is the named constant, and it truncates the result list."""
    topics = tuple(
        _topic(f"t{i}", title="match") for i in range(GUIDE_SEARCH_RESULT_CAP + 15)
    )
    model = _model(topics)
    # Every topic matches "match"; the default cap must truncate to the constant.
    results = query(model, "match")
    assert len(results) == GUIDE_SEARCH_RESULT_CAP
    assert results == query(model, "match", cap=GUIDE_SEARCH_RESULT_CAP)


def test_explicit_cap_limits_results():
    results = query(_SAMPLE, "", cap=2)
    assert len(results) == 2
    assert results == _SAMPLE.topics()[:2]


def test_cap_zero_returns_empty():
    assert query(_SAMPLE, "", cap=0) == ()


def test_negative_cap_returns_empty():
    assert query(_SAMPLE, "layers", cap=-1) == ()
    assert query(_SAMPLE, "", cap=-5) == ()


# --------------------------------------------------------------------------- #
# Property-based invariants (Hypothesis)                                      #
# --------------------------------------------------------------------------- #

_id_st = st.from_regex(r"[a-z][a-z0-9-]{0,10}", fullmatch=True)
_word_st = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20)


@st.composite
def _search_model(draw):
    ids = draw(st.lists(_id_st, min_size=0, max_size=8, unique=True))
    topics = tuple(
        _topic(
            tid,
            title=draw(_word_st),
            keywords=tuple(draw(st.lists(_word_st, max_size=3))),
            summary=draw(_word_st),
        )
        for tid in ids
    )
    return _model(topics)


@given(_search_model(), st.text(max_size=15), st.integers(min_value=-5, max_value=100))
def test_results_are_subset_ordered_and_capped(model, term, cap):
    """Property: results ⊆ topics, cap-bounded, and order-preserving."""
    results = query(model, term, cap=cap)
    all_topics = model.topics()
    # subset (identity-preserving)
    assert all(t in all_topics for t in results)
    # capped
    assert len(results) <= max(cap, 0)
    # order-preserving: the results appear in the same relative order as the model
    positions = [all_topics.index(t) for t in results]
    assert positions == sorted(positions)


@given(_search_model())
def test_empty_term_is_full_set_capped(model):
    """Property: an empty term returns the model's topics, capped at the default."""
    results = query(model, "")
    assert results == model.topics()[:GUIDE_SEARCH_RESULT_CAP]
