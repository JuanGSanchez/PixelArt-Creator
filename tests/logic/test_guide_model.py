"""Tests for pixelart_creator.logic.guide_model (zero Qt) — the guide content model.

Covers REQ-UG-LOGIC-001 (ordered section->topic tree), -002 (deterministic
discovery/extensibility), -004 (locale resolution + fallback) and -005 (coverage
contract). Maps to Gherkin SC-L001-1/-2, SC-L002-1/-2, SC-L004-1/-2, SC-L005-1/-2.

The model is pure and does no I/O, so most tests build a :class:`Manifest` directly.
The shipped-scaffold assertions load the committed bundle through
:func:`pixelart_creator.data.guide_content.load_manifest` (the real discovered data)
to prove ``missing_required_areas() == ()`` for what ships today. Hypothesis property
tests assert the ordering/flattening invariants hold for arbitrary valid manifests.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import guide_model
from pixelart_creator.logic.constants import GUIDE_MAX_TOC_DEPTH
from pixelart_creator.logic.guide_model import (
    DEFAULT_GUIDE_LOCALE,
    REQUIRED_AREAS,
    GuideModel,
    GuideModelError,
    GuideSection,
    GuideTopic,
    Manifest,
    build_model,
    content_ref_path,
    missing_required_areas,
    resolve_content_ref,
)

# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #


def _topic(
    tid: str,
    *,
    title: str | None = None,
    ref: str | None = None,
    keywords: tuple[str, ...] = (),
    summary: str = "s",
) -> GuideTopic:
    return GuideTopic(
        id=tid,
        title=title if title is not None else tid.title(),
        content_ref=ref if ref is not None else tid,
        keywords=keywords,
        summary=summary,
    )


def _section(sid: str, topics: tuple[GuideTopic, ...]) -> GuideSection:
    return GuideSection(id=sid, title=sid.title(), topics=topics)


def _manifest(sections: tuple[GuideSection, ...]) -> Manifest:
    return Manifest(schema_version=1, default_locale="en", sections=sections)


def _full_required_manifest() -> Manifest:
    """A manifest covering every required area (one topic each)."""
    sections = tuple(
        _section(area, (_topic(area, keywords=("kw",)),)) for area in REQUIRED_AREAS
    )
    return _manifest(sections)


# --------------------------------------------------------------------------- #
# REQ-UG-LOGIC-001 — ordered section->topic tree + topic attributes           #
# --------------------------------------------------------------------------- #


def test_build_model_yields_ordered_sections_and_topic_attributes():
    """SC-L001-1: the model builds an ordered tree; topics expose all fields."""
    manifest = _manifest(
        (
            _section(
                "s1", (_topic("t1", ref="r1", keywords=("a", "b"), summary="sum1"),)
            ),
            _section("s2", (_topic("t2"), _topic("t3"))),
        )
    )
    model = build_model(manifest)

    assert isinstance(model, GuideModel)
    assert [s.id for s in model.sections] == ["s1", "s2"]
    t1 = model.sections[0].topics[0]
    assert (t1.id, t1.title, t1.content_ref, t1.keywords, t1.summary) == (
        "t1",
        "T1",
        "r1",
        ("a", "b"),
        "sum1",
    )


def test_topics_flattened_in_deterministic_section_topic_order():
    """SC-L001-1: topics() flattens sections in declared order."""
    manifest = _manifest(
        (
            _section("s1", (_topic("t1"), _topic("t2"))),
            _section("s2", (_topic("t3"),)),
        )
    )
    model = build_model(manifest)
    assert [t.id for t in model.topics()] == ["t1", "t2", "t3"]


def test_topic_lookup_returns_topic_and_raises_on_unknown():
    """topic(id) returns the topic; an unknown id raises GuideModelError."""
    model = build_model(_manifest((_section("s1", (_topic("layers"),)),)))
    assert model.topic("layers").id == "layers"
    with pytest.raises(GuideModelError):
        model.topic("nope")


def test_build_model_rejects_duplicate_section_id():
    manifest = _manifest(
        (_section("dup", (_topic("t1"),)), _section("dup", (_topic("t2"),)))
    )
    with pytest.raises(GuideModelError, match="duplicate guide section id"):
        build_model(manifest)


def test_build_model_rejects_duplicate_topic_id():
    manifest = _manifest(
        (_section("s1", (_topic("dup"),)), _section("s2", (_topic("dup"),)))
    )
    with pytest.raises(GuideModelError, match="duplicate guide topic id"):
        build_model(manifest)


@pytest.mark.parametrize("bad", ["", "   ", 123, None])
def test_build_model_rejects_empty_or_non_string_section_id(bad):
    manifest = _manifest((GuideSection(id=bad, title="x", topics=()),))  # type: ignore[arg-type]
    with pytest.raises(GuideModelError, match="section id must be"):
        build_model(manifest)


@pytest.mark.parametrize("bad", ["", "   ", 42, None])
def test_build_model_rejects_empty_or_non_string_topic_id(bad):
    topic = GuideTopic(id=bad, title="x", content_ref="r", keywords=(), summary="s")  # type: ignore[arg-type]
    with pytest.raises(GuideModelError, match="topic id must be"):
        build_model(_manifest((_section("s1", (topic,)),)))


def test_build_model_rejects_empty_content_ref():
    topic = GuideTopic(id="t1", title="x", content_ref="", keywords=(), summary="s")
    with pytest.raises(GuideModelError, match="content_ref id must be"):
        build_model(_manifest((_section("s1", (topic,)),)))


# --------------------------------------------------------------------------- #
# GUIDE_MAX_TOC_DEPTH is enforced (a constant, not a literal)                 #
# --------------------------------------------------------------------------- #


def test_shipped_two_level_tree_is_within_depth_ceiling():
    """A section-with-topics tree (depth 2) builds fine under the default ceiling."""
    assert GUIDE_MAX_TOC_DEPTH >= 2  # scaffold precondition
    model = build_model(_manifest((_section("s1", (_topic("t1"),)),)))
    assert model.topics()[0].id == "t1"


def test_build_model_enforces_toc_depth_ceiling_constant(monkeypatch):
    """Over-deep trees are rejected against GUIDE_MAX_TOC_DEPTH (not a literal).

    Lowering the ceiling to 1 makes a section-with-topics tree (achieved depth 2)
    exceed it — proving build_model reads the named constant, not a hard-coded bound.
    """
    monkeypatch.setattr(guide_model, "GUIDE_MAX_TOC_DEPTH", 1)
    with pytest.raises(GuideModelError, match="exceeds ceiling 1"):
        build_model(_manifest((_section("s1", (_topic("t1"),)),)))


def test_empty_manifest_has_zero_depth_and_no_topics():
    model = build_model(_manifest(()))
    assert model.topics() == ()
    assert model.sections == ()


def test_section_without_topics_is_depth_one_and_builds():
    """A section with no topics is depth 1 — builds and contributes no topics."""
    model = build_model(_manifest((_section("empty", ()),)))
    assert model.topics() == ()
    assert model.sections[0].id == "empty"


# --------------------------------------------------------------------------- #
# REQ-UG-LOGIC-002 — deterministic discovery / extensibility                  #
# --------------------------------------------------------------------------- #


def test_discovery_is_deterministic_same_manifest_same_order():
    """SC-L002-2: building the same manifest twice yields identical ToC order."""
    manifest = _full_required_manifest()
    first = [t.id for t in build_model(manifest).topics()]
    second = [t.id for t in build_model(manifest).topics()]
    assert first == second == list(REQUIRED_AREAS)


def test_adding_a_topic_is_discovered_with_no_code_change():
    """SC-L002-1: adding a manifest topic adds a ToC topic — data-driven, no code."""
    base = _manifest((_section("layers", (_topic("layers"),)),))
    extended = _manifest(
        (_section("layers", (_topic("layers"), _topic("layers-advanced"))),)
    )
    assert [t.id for t in build_model(base).topics()] == ["layers"]
    assert [t.id for t in build_model(extended).topics()] == [
        "layers",
        "layers-advanced",
    ]


def test_adding_a_whole_section_is_discovered_with_no_code_change():
    """SC-L002-1: a fixture bundle with an added section grows the tree, no code."""
    base = _manifest((_section("layers", (_topic("layers"),)),))
    extended = _manifest(
        (
            _section("layers", (_topic("layers"),)),
            _section("brand-new-feature", (_topic("brand-new-feature"),)),
        )
    )
    assert [s.id for s in build_model(base).sections] == ["layers"]
    assert [s.id for s in build_model(extended).sections] == [
        "layers",
        "brand-new-feature",
    ]


# --------------------------------------------------------------------------- #
# REQ-UG-LOGIC-004 — locale resolution with fallback                          #
# --------------------------------------------------------------------------- #


def test_resolve_returns_localised_path_when_locale_available():
    """SC-L004-1: a localised doc is chosen when present."""
    model = build_model(_manifest((_section("s1", (_topic("layers", ref="layers"),)),)))
    path = resolve_content_ref(model, "layers", "es", available_locales={"es", "en"})
    assert path == "content/es/layers.md"


def test_resolve_falls_back_to_default_locale_when_absent():
    """SC-L004-2: an absent locale falls back to the default locale."""
    model = build_model(_manifest((_section("s1", (_topic("layers", ref="layers"),)),)))
    path = resolve_content_ref(model, "layers", "es", available_locales={"en"})
    assert path == "content/en/layers.md"


def test_resolve_uses_explicit_default_locale_override():
    model = build_model(_manifest((_section("s1", (_topic("layers", ref="layers"),)),)))
    path = resolve_content_ref(
        model, "layers", "fr", default_locale="de", available_locales={"en"}
    )
    assert path == "content/de/layers.md"


def test_resolve_unknown_topic_raises():
    model = build_model(_manifest((_section("s1", (_topic("layers"),)),)))
    with pytest.raises(GuideModelError):
        resolve_content_ref(model, "nope", "en", available_locales={"en"})


def test_content_ref_path_uses_forward_slashes_and_default_locale():
    assert content_ref_path("layers", DEFAULT_GUIDE_LOCALE) == "content/en/layers.md"
    assert "\\" not in content_ref_path("a-b", "pt-BR")


# --------------------------------------------------------------------------- #
# REQ-UG-LOGIC-005 — coverage / completeness contract                         #
# --------------------------------------------------------------------------- #


def test_missing_required_areas_empty_for_full_manifest():
    """SC-L005-1: every required area covered -> no gaps."""
    assert missing_required_areas(build_model(_full_required_manifest())) == ()


def test_missing_required_areas_reports_absent_area():
    """SC-L005-2: dropping cloud-and-collaboration reports it as a gap."""
    sections = tuple(
        _section(area, (_topic(area),))
        for area in REQUIRED_AREAS
        if area != "cloud-and-collaboration"
    )
    missing = missing_required_areas(build_model(_manifest(sections)))
    assert missing == ("cloud-and-collaboration",)


def test_section_with_zero_topics_is_not_covered():
    """A required-id section with no topics does not count as covered (deficient)."""
    sections = tuple(
        _section(area, (_topic(area),) if area != "layers" else ())
        for area in REQUIRED_AREAS
    )
    missing = missing_required_areas(build_model(_manifest(sections)))
    assert missing == ("layers",)


def test_missing_areas_reported_in_required_order():
    """Gaps are reported in REQUIRED_AREAS order (deterministic)."""
    model = build_model(_manifest(()))
    assert missing_required_areas(model) == REQUIRED_AREAS


# --------------------------------------------------------------------------- #
# Shipped scaffold (real committed bundle) — coverage contract green today    #
# --------------------------------------------------------------------------- #


def test_shipped_scaffold_builds_and_is_complete():
    """The committed bundle builds 11 sections and satisfies the coverage contract."""
    from pixelart_creator.data.guide_content import load_manifest

    model = build_model(load_manifest())
    assert len(model.sections) == len(REQUIRED_AREAS)
    assert missing_required_areas(model) == ()
    # Every required area maps to >= 1 topic.
    covered = {s.id for s in model.sections if s.topics}
    assert set(REQUIRED_AREAS) <= covered


# --------------------------------------------------------------------------- #
# Property-based invariants (Hypothesis)                                      #
# --------------------------------------------------------------------------- #

_id_st = st.from_regex(r"[a-z][a-z0-9-]{0,12}", fullmatch=True)


@st.composite
def _unique_manifest(draw):
    """A valid manifest with globally-unique section and topic ids."""
    section_ids = draw(st.lists(_id_st, min_size=0, max_size=5, unique=True))
    used_topic_ids: set[str] = set()
    sections = []
    for sid in section_ids:
        topic_ids = draw(
            st.lists(_id_st, min_size=0, max_size=4, unique=True).filter(
                lambda ids: not (set(ids) & used_topic_ids)
                and len(set(ids)) == len(ids)
            )
        )
        used_topic_ids.update(topic_ids)
        sections.append(_section(sid, tuple(_topic(t) for t in topic_ids)))
    return _manifest(tuple(sections))


@given(_unique_manifest())
def test_topics_flattening_preserves_manifest_order(manifest):
    """Property: topics() order == the manifest's declared section->topic order."""
    model = build_model(manifest)
    expected = [t.id for s in manifest.sections for t in s.topics]
    assert [t.id for t in model.topics()] == expected


@given(_unique_manifest())
def test_every_topic_is_addressable_by_id(manifest):
    """Property: every declared topic is retrievable via topic(id)."""
    model = build_model(manifest)
    for topic in model.topics():
        assert model.topic(topic.id) is topic
