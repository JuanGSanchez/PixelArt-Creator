"""Tests for the localised guide metadata logic (zero Qt, no I/O).

Covers ``LocaleMeta`` and the ``localised_*`` accessors of
``pixelart_creator.logic.guide_model`` (per-item English fallback,
REQ-L10N-UI-008), the localised index and query of
``pixelart_creator.logic.guide_search`` (the active language's title, keywords and
summary plus the English keywords) and the per-topic locale resolution through
``resolve_content_ref`` (REQ-L10N-UI-007). Spec scenario SC-L10N-UI-008-1 maps to
the search tests: a term in the active language, or an English keyword, finds the
topic.

Hypothesis properties assert the invariants that hold for any metadata: results are
a model-ordered subset, capped, never lose an English keyword, and ``meta=None``
reproduces the English index exactly.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.constants import GUIDE_SEARCH_RESULT_CAP
from pixelart_creator.logic.guide_model import (
    DEFAULT_GUIDE_LOCALE,
    GuideModel,
    GuideModelError,
    GuideSection,
    GuideTopic,
    LocaleMeta,
    Manifest,
    build_model,
    localised_keywords,
    localised_section_title,
    localised_summary,
    localised_title,
    resolve_content_ref,
)
from pixelart_creator.logic.guide_search import indexed_text, query

# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #

_LAYERS = GuideTopic(
    id="layers",
    title="Layers",
    content_ref="layers",
    keywords=("opacity", "blend"),
    summary="Stack and blend layers.",
)
_COLOUR = GuideTopic(
    id="colour",
    title="Colour hub",
    content_ref="colour",
    keywords=("hue", "palette"),
    summary="Pick and harmonise colours.",
)
_EXPORT = GuideTopic(
    id="export",
    title="Export",
    content_ref="export",
    keywords=("png",),
    summary="Write files.",
)
_SECTION_A = GuideSection(id="basics", title="Basics", topics=(_LAYERS, _COLOUR))
_SECTION_B = GuideSection(id="output", title="Output", topics=(_EXPORT,))


def _model(*sections: GuideSection) -> GuideModel:
    return build_model(
        Manifest(schema_version=1, default_locale="en", sections=sections)
    )


def _meta(
    *,
    titles: dict[str, str] | None = None,
    summaries: dict[str, str] | None = None,
    keywords: dict[str, tuple[str, ...]] | None = None,
    sections: dict[str, str] | None = None,
    locale: str = "ko",
) -> LocaleMeta:
    return LocaleMeta(
        locale=locale,
        schema_version=1,
        section_titles=MappingProxyType(sections or {}),
        topic_titles=MappingProxyType(titles or {}),
        topic_summaries=MappingProxyType(summaries or {}),
        topic_keywords=MappingProxyType(keywords or {}),
    )


_FULL = _meta(
    titles={"layers": "LAYERS-KO", "colour": "COLOUR-KO"},
    summaries={"layers": "SUMMARY-KO"},
    keywords={"layers": ("kw-ko-a", "kw-ko-b")},
    sections={"basics": "BASICS-KO"},
)


def _ids(topics: tuple[GuideTopic, ...]) -> list[str]:
    return [t.id for t in topics]


# --------------------------------------------------------------------------- #
# LocaleMeta and the localised accessors                                      #
# --------------------------------------------------------------------------- #


class TestLocaleMeta:
    def test_is_frozen(self) -> None:
        with pytest.raises(AttributeError):
            _FULL.locale = "ja"  # type: ignore[misc]

    def test_equal_metadata_compares_equal(self) -> None:
        assert _meta(titles={"a": "x"}) == _meta(titles={"a": "x"})


class TestLocalisedTitle:
    def test_none_meta_is_english(self) -> None:
        assert localised_title(_LAYERS, None) == "Layers"

    def test_translated_topic_uses_the_language(self) -> None:
        assert localised_title(_LAYERS, _FULL) == "LAYERS-KO"

    def test_untranslated_topic_falls_back_to_english_for_that_item_only(self) -> None:
        meta = _meta(titles={"colour": "COLOUR-KO"})
        assert localised_title(_LAYERS, meta) == "Layers"
        assert localised_title(_COLOUR, meta) == "COLOUR-KO"

    def test_empty_metadata_is_english(self) -> None:
        assert localised_title(_LAYERS, _meta()) == "Layers"


class TestLocalisedSummary:
    def test_none_meta_is_english(self) -> None:
        assert localised_summary(_LAYERS, None) == "Stack and blend layers."

    def test_translated_topic_uses_the_language(self) -> None:
        assert localised_summary(_LAYERS, _FULL) == "SUMMARY-KO"

    def test_topic_with_title_but_no_summary_falls_back(self) -> None:
        assert localised_summary(_COLOUR, _FULL) == "Pick and harmonise colours."


class TestLocalisedKeywords:
    def test_none_meta_is_the_english_tuple_itself(self) -> None:
        assert localised_keywords(_LAYERS, None) is _LAYERS.keywords

    def test_translated_topic_uses_the_language(self) -> None:
        assert localised_keywords(_LAYERS, _FULL) == ("kw-ko-a", "kw-ko-b")

    def test_untranslated_topic_returns_the_english_tuple_itself(self) -> None:
        assert localised_keywords(_COLOUR, _FULL) is _COLOUR.keywords

    def test_an_explicit_empty_translation_is_respected(self) -> None:
        meta = _meta(keywords={"layers": ()})
        assert localised_keywords(_LAYERS, meta) == ()


class TestLocalisedSectionTitle:
    def test_none_meta_is_english(self) -> None:
        assert localised_section_title(_SECTION_A, None) == "Basics"

    def test_translated_section_uses_the_language(self) -> None:
        assert localised_section_title(_SECTION_A, _FULL) == "BASICS-KO"

    def test_untranslated_section_falls_back(self) -> None:
        assert localised_section_title(_SECTION_B, _FULL) == "Output"


# --------------------------------------------------------------------------- #
# resolve_content_ref with a per-topic locale set                             #
# --------------------------------------------------------------------------- #


class TestPerTopicResolution:
    def setup_method(self) -> None:
        self.model = _model(_SECTION_A, _SECTION_B)

    def test_topic_held_in_the_active_language_resolves_there(self) -> None:
        ref = resolve_content_ref(
            self.model, "layers", "ko", available_locales={"en", "ko"}
        )
        assert ref == "content/ko/layers.md"

    def test_topic_missing_in_the_active_language_falls_back_to_english(self) -> None:
        ref = resolve_content_ref(self.model, "colour", "ko", available_locales={"en"})
        assert ref == "content/en/colour.md"

    def test_each_topic_resolves_independently(self) -> None:
        held = {"layers": {"en", "ko"}, "colour": {"en"}, "export": {"en", "ko"}}
        refs = {
            tid: resolve_content_ref(self.model, tid, "ko", available_locales=held[tid])
            for tid in held
        }
        assert refs == {
            "layers": "content/ko/layers.md",
            "colour": "content/en/colour.md",
            "export": "content/ko/export.md",
        }

    def test_available_locales_may_be_any_iterable(self) -> None:
        ref = resolve_content_ref(
            self.model, "layers", "ko", available_locales=iter(["en", "ko"])
        )
        assert ref == "content/ko/layers.md"

    def test_empty_available_set_uses_the_default_locale(self) -> None:
        ref = resolve_content_ref(self.model, "layers", "ko", available_locales=())
        assert ref == f"content/{DEFAULT_GUIDE_LOCALE}/layers.md"

    def test_explicit_default_locale_is_the_fallback(self) -> None:
        ref = resolve_content_ref(
            self.model, "layers", "ko", default_locale="es", available_locales={"es"}
        )
        assert ref == "content/es/layers.md"

    def test_unknown_topic_raises(self) -> None:
        with pytest.raises(GuideModelError):
            resolve_content_ref(self.model, "nope", "ko", available_locales={"ko"})


# --------------------------------------------------------------------------- #
# indexed_text                                                                #
# --------------------------------------------------------------------------- #


class TestIndexedText:
    def test_none_meta_is_the_english_title_keywords_summary(self) -> None:
        assert indexed_text(_LAYERS) == ("layers opacity blend stack and blend layers.")
        assert indexed_text(_LAYERS, None) == indexed_text(_LAYERS)

    def test_with_meta_the_language_comes_first_then_english_keywords(self) -> None:
        assert indexed_text(_LAYERS, _FULL) == (
            "layers-ko kw-ko-a kw-ko-b summary-ko opacity blend"
        )

    def test_english_title_and_summary_are_not_indexed_once_translated(self) -> None:
        text = indexed_text(_LAYERS, _FULL)
        assert "stack" not in text
        assert text.split()[0] == "layers-ko"

    def test_untranslated_items_fall_back_per_item(self) -> None:
        meta = _meta(titles={"colour": "COLOUR-KO"})
        text = indexed_text(_COLOUR, meta)
        assert text == "colour-ko hue palette pick and harmonise colours."

    def test_english_keywords_are_not_repeated_when_keywords_fall_back(self) -> None:
        text = indexed_text(_COLOUR, _FULL)
        assert text.count("hue") == 1 and text.count("palette") == 1

    def test_text_is_lower_cased(self) -> None:
        meta = _meta(titles={"layers": "MiXeD Case"})
        assert indexed_text(_LAYERS, meta).startswith("mixed case")

    def test_empty_metadata_gives_the_english_text(self) -> None:
        assert indexed_text(_LAYERS, _meta()) == indexed_text(_LAYERS)

    def test_id_and_content_ref_are_never_indexed(self) -> None:
        topic = GuideTopic(
            id="zz-id", title="T", content_ref="zz-ref", keywords=(), summary="S"
        )
        text = indexed_text(topic, _meta(titles={"zz-id": "X"}))
        assert "zz-id" not in text and "zz-ref" not in text


# --------------------------------------------------------------------------- #
# query                                                                       #
# --------------------------------------------------------------------------- #


class TestQueryLocalised:
    def setup_method(self) -> None:
        self.model = _model(_SECTION_A, _SECTION_B)

    def test_translated_title_term_finds_the_topic(self) -> None:
        assert _ids(query(self.model, "layers-ko", meta=_FULL)) == ["layers"]

    def test_translated_keyword_term_finds_the_topic(self) -> None:
        assert _ids(query(self.model, "kw-ko-b", meta=_FULL)) == ["layers"]

    def test_translated_summary_term_finds_the_topic(self) -> None:
        assert _ids(query(self.model, "summary-ko", meta=_FULL)) == ["layers"]

    def test_english_keyword_still_finds_the_topic_under_a_translation(self) -> None:
        assert _ids(query(self.model, "opacity", meta=_FULL)) == ["layers"]

    def test_translated_term_finds_nothing_without_metadata(self) -> None:
        assert query(self.model, "layers-ko") == ()

    def test_term_matching_is_case_insensitive(self) -> None:
        assert _ids(query(self.model, "LAYERS-ko", meta=_FULL)) == ["layers"]

    def test_non_latin_term_is_case_insensitive(self) -> None:
        meta = _meta(titles={"layers": "Слои"}, locale="ru")
        found = query(self.model, "сЛОи", meta=meta)
        assert _ids(found) == ["layers"]

    def test_hangul_term_matches_as_a_substring(self) -> None:
        meta = _meta(titles={"layers": "레이어 패널"})
        assert _ids(query(self.model, "이어", meta=meta)) == ["layers"]

    def test_surrounding_whitespace_in_the_term_is_stripped(self) -> None:
        assert _ids(query(self.model, "  kw-ko-a \t", meta=_FULL)) == ["layers"]

    def test_empty_term_returns_every_topic_in_model_order(self) -> None:
        assert _ids(query(self.model, "", meta=_FULL)) == [
            "layers",
            "colour",
            "export",
        ]

    def test_whitespace_term_returns_every_topic(self) -> None:
        assert len(query(self.model, "   ", meta=_FULL)) == 3

    def test_results_keep_section_then_topic_order(self) -> None:
        meta = _meta(summaries={"export": "shared-term", "layers": "shared-term"})
        assert _ids(query(self.model, "shared-term", meta=meta)) == [
            "layers",
            "export",
        ]

    def test_cap_limits_the_results(self) -> None:
        assert _ids(query(self.model, "", cap=2, meta=_FULL)) == ["layers", "colour"]

    def test_zero_cap_yields_nothing(self) -> None:
        assert query(self.model, "", cap=0, meta=_FULL) == ()

    def test_negative_cap_yields_nothing(self) -> None:
        assert query(self.model, "", cap=-1, meta=_FULL) == ()

    def test_default_cap_is_the_named_constant(self) -> None:
        many = tuple(
            GuideTopic(
                id=f"t{i}",
                title="common",
                content_ref=f"t{i}",
                keywords=(),
                summary="s",
            )
            for i in range(GUIDE_SEARCH_RESULT_CAP + 5)
        )
        model = _model(GuideSection(id="s", title="S", topics=many))
        assert len(query(model, "common", meta=_meta())) == GUIDE_SEARCH_RESULT_CAP

    def test_none_meta_matches_the_english_behaviour(self) -> None:
        assert _ids(query(self.model, "hue")) == ["colour"]
        assert _ids(query(self.model, "hue", meta=None)) == ["colour"]

    def test_empty_metadata_behaves_as_english(self) -> None:
        assert query(self.model, "stack", meta=_meta()) == query(self.model, "stack")

    def test_translated_topic_is_not_found_by_its_english_title_alone(self) -> None:
        # The index holds the active language's text plus the English KEYWORDS;
        # the English title is only a fallback for an untranslated item.
        assert query(self.model, "stack", meta=_FULL) == ()

    def test_untranslated_topic_is_still_found_by_its_english_title(self) -> None:
        assert _ids(query(self.model, "export", meta=_FULL)) == ["export"]

    def test_empty_model_yields_nothing(self) -> None:
        assert query(_model(), "x", meta=_FULL) == ()


# --------------------------------------------------------------------------- #
# properties                                                                  #
# --------------------------------------------------------------------------- #

_TEXT = st.text(
    alphabet=st.characters(
        min_codepoint=33, max_codepoint=0x2FF, blacklist_categories=("Cs", "Cc", "Z")
    ),
    min_size=1,
    max_size=10,
)
_TOPIC_IDS = ("layers", "colour", "export")
_META = st.builds(
    lambda titles, summaries, keywords: _meta(
        titles=titles, summaries=summaries, keywords=keywords
    ),
    st.dictionaries(st.sampled_from(_TOPIC_IDS), _TEXT),
    st.dictionaries(st.sampled_from(_TOPIC_IDS), _TEXT),
    st.dictionaries(
        st.sampled_from(_TOPIC_IDS), st.lists(_TEXT, max_size=3).map(tuple)
    ),
)
_MODEL = _model(_SECTION_A, _SECTION_B)


@given(meta=_META, term=st.text(max_size=8), cap=st.integers(-2, 6))
def test_results_are_an_ordered_capped_subset_of_the_model(
    meta: LocaleMeta, term: str, cap: int
) -> None:
    found = query(_MODEL, term, cap=cap, meta=meta)
    topics = list(_MODEL.topics())
    assert len(found) <= max(cap, 0)
    positions = [topics.index(t) for t in found]
    assert positions == sorted(set(positions))


@given(meta=_META)
def test_an_english_keyword_always_finds_its_topic(meta: LocaleMeta) -> None:
    for topic in _MODEL.topics():
        for keyword in topic.keywords:
            assert topic in query(_MODEL, keyword, meta=meta)


@given(meta=_META)
def test_a_translated_title_always_finds_its_topic(meta: LocaleMeta) -> None:
    for topic in _MODEL.topics():
        title = localised_title(topic, meta)
        assert topic in query(_MODEL, title, meta=meta)


@given(term=st.text(max_size=8))
def test_without_metadata_the_query_is_unchanged(term: str) -> None:
    assert query(_MODEL, term) == query(_MODEL, term, meta=None)
    for topic in _MODEL.topics():
        assert indexed_text(topic) == indexed_text(topic, None)


@given(
    meta=_META,
    term=st.text(alphabet="abcdefghij-k ", min_size=1, max_size=6),
)
def test_a_longer_term_never_adds_results(meta: LocaleMeta, term: str) -> None:
    shorter = {t.id for t in query(_MODEL, term[:-1], meta=meta)}
    longer = {t.id for t in query(_MODEL, term, meta=meta)}
    assert longer <= shorter


@given(meta=_META)
def test_every_accessor_returns_the_metadata_value_or_the_english_one(
    meta: LocaleMeta,
) -> None:
    for topic in _MODEL.topics():
        assert localised_title(topic, meta) in (
            meta.topic_titles.get(topic.id),
            topic.title,
        )
        assert localised_summary(topic, meta) in (
            meta.topic_summaries.get(topic.id),
            topic.summary,
        )
        assert localised_keywords(topic, meta) in (
            meta.topic_keywords.get(topic.id),
            topic.keywords,
        )
