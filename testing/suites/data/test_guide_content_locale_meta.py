"""Tests for the localised half of pixelart_creator.data.guide_content (zero Qt).

Covers ``topic_locales`` / ``topic_locale_map`` (per-topic availability,
REQ-L10N-UI-007), ``load_locale_meta`` (the per-language ``meta.json`` reader,
REQ-L10N-UI-008, schema in REQ-L10N-DATA-003) and the unchanged error wording of
``read_content`` after it was refactored onto the shared bounded reader.

Every guard and branch is exercised on a fixture bundle written under ``tmp_path``
and swapped in by monkeypatching ``bundle_root``; the committed bundle is only
read, never written. One test per rejection class.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.data import guide_content
from pixelart_creator.data.guide_content import (
    META_FILE_NAME,
    GuideContentError,
    available_locales,
    bundle_root,
    load_locale_meta,
    load_manifest,
    read_content,
    topic_locale_map,
    topic_locales,
)
from pixelart_creator.logic.constants import GUIDE_MAX_CONTENT_BYTES
from pixelart_creator.logic.guide_model import (
    DEFAULT_GUIDE_LOCALE,
    LocaleMeta,
    build_model,
    resolve_content_ref,
)

_MANIFEST = {
    "schema_version": 1,
    "default_locale": "en",
    "sections": [
        {
            "id": "basics",
            "title": "Basics",
            "topics": [
                {
                    "id": "layers",
                    "title": "Layers",
                    "content": "layers",
                    "keywords": ["opacity"],
                    "summary": "The layers.",
                },
                {
                    "id": "colour",
                    "title": "Colour",
                    "content": "colour",
                    "keywords": ["hue"],
                    "summary": "The colours.",
                },
            ],
        }
    ],
}

_KO_META = {
    "schema_version": 1,
    "locale": "ko",
    "sections": {"basics": {"title": "BASICS-KO"}},
    "topics": {
        "layers": {
            "title": "LAYERS-KO",
            "summary": "SUMMARY-KO",
            "keywords": ["kw-ko-1", "kw-ko-2"],
        },
        "colour": {"title": "COLOUR-KO"},
    },
}


def _put(root: Path, ref: str, data: str | bytes) -> None:
    path = root / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fixture bundle: en has both pages; ko has one page and a meta.json.

    ``ru`` is a folder with no page at all, ``de`` has the colour page only.
    """
    root = tmp_path / "bundle"
    _put(root, "manifest.json", json.dumps(_MANIFEST))
    _put(root, "content/en/layers.md", "# Layers\n")
    _put(root, "content/en/colour.md", "# Colour\n")
    _put(root, "content/ko/layers.md", "# KO layers\n")
    _put(root, "content/ko/meta.json", json.dumps(_KO_META))
    (root / "content" / "ru").mkdir(parents=True)
    _put(root, "content/de/colour.md", "# DE colour\n")
    monkeypatch.setattr(guide_content, "bundle_root", lambda: root)
    return root


def _set_meta(root: Path, locale: str, data: object) -> None:
    _put(root, f"content/{locale}/{META_FILE_NAME}", json.dumps(data))


# --------------------------------------------------------------------------- #
# topic_locales / topic_locale_map                                            #
# --------------------------------------------------------------------------- #


class TestTopicLocales:
    def test_lists_exactly_the_locales_that_hold_the_page(self, bundle: Path) -> None:
        assert topic_locales("layers") == frozenset({"en", "ko"})
        assert topic_locales("colour") == frozenset({"en", "de"})

    def test_folder_without_the_page_is_not_listed(self, bundle: Path) -> None:
        assert "ru" in available_locales()
        assert "ru" not in topic_locales("layers")

    def test_unknown_stem_is_the_empty_set(self, bundle: Path) -> None:
        assert topic_locales("no-such-page") == frozenset()

    def test_missing_content_directory_is_the_empty_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(guide_content, "bundle_root", lambda: tmp_path)
        assert topic_locales("layers") == frozenset()

    def test_a_directory_named_like_the_page_does_not_count(self, bundle: Path) -> None:
        (bundle / "content" / "ru" / "layers.md").mkdir()
        assert "ru" not in topic_locales("layers")

    @pytest.mark.parametrize("ref", ["../x", "a" + chr(92) + "b", "/abs", "c:x"])
    def test_stem_failing_the_path_guard_raises(self, bundle: Path, ref: str) -> None:
        with pytest.raises(GuideContentError):
            topic_locales(ref)

    def test_empty_stem_names_no_page_so_no_locale(self, bundle: Path) -> None:
        # The stem is spliced into a well-formed path, so the path guard has
        # nothing to reject and no locale holds a page of that name.
        assert topic_locales("") == frozenset()

    def test_result_is_a_frozenset(self, bundle: Path) -> None:
        assert isinstance(topic_locales("layers"), frozenset)

    def test_every_topic_of_the_committed_bundle_is_held_in_english(self) -> None:
        topics = build_model(load_manifest()).topics()
        assert topics
        for topic in topics:
            assert DEFAULT_GUIDE_LOCALE in topic_locales(topic.content_ref)


class TestTopicLocaleMap:
    def test_maps_every_topic_id_to_its_own_locale_set(self, bundle: Path) -> None:
        model = build_model(load_manifest())
        assert topic_locale_map(model) == {
            "layers": frozenset({"en", "ko"}),
            "colour": frozenset({"en", "de"}),
        }

    def test_keys_follow_topic_ids_not_content_stems(
        self, bundle: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest = json.loads(json.dumps(_MANIFEST))
        manifest["sections"][0]["topics"][0]["id"] = "layers-topic"
        _put(bundle, "manifest.json", json.dumps(manifest))
        model = build_model(load_manifest())
        assert set(topic_locale_map(model)) == {"layers-topic", "colour"}

    def test_empty_model_gives_an_empty_map(self, bundle: Path) -> None:
        _put(
            bundle,
            "manifest.json",
            json.dumps({**_MANIFEST, "sections": []}),
        )
        assert topic_locale_map(build_model(load_manifest())) == {}

    def test_resolution_falls_back_for_the_missing_page_only(
        self, bundle: Path
    ) -> None:
        model = build_model(load_manifest())
        available = topic_locale_map(model)
        # ko holds the layers page but not the colour page: layers stays in ko,
        # colour falls back to English, though the ko folder exists.
        assert (
            resolve_content_ref(
                model, "layers", "ko", available_locales=available["layers"]
            )
            == "content/ko/layers.md"
        )
        assert (
            resolve_content_ref(
                model, "colour", "ko", available_locales=available["colour"]
            )
            == "content/en/colour.md"
        )

    def test_empty_folder_falls_back_for_every_page(self, bundle: Path) -> None:
        model = build_model(load_manifest())
        for topic_id, available in topic_locale_map(model).items():
            ref = resolve_content_ref(
                model, topic_id, "ru", available_locales=available
            )
            assert ref.startswith("content/en/")


# --------------------------------------------------------------------------- #
# load_locale_meta                                                            #
# --------------------------------------------------------------------------- #


class TestLoadLocaleMetaHappyPath:
    def test_full_file_is_read_into_a_locale_meta(self, bundle: Path) -> None:
        meta = load_locale_meta("ko")
        assert isinstance(meta, LocaleMeta)
        assert meta.locale == "ko" and meta.schema_version == 1
        assert dict(meta.section_titles) == {"basics": "BASICS-KO"}
        assert dict(meta.topic_titles) == {
            "layers": "LAYERS-KO",
            "colour": "COLOUR-KO",
        }
        assert dict(meta.topic_summaries) == {"layers": "SUMMARY-KO"}
        assert dict(meta.topic_keywords) == {"layers": ("kw-ko-1", "kw-ko-2")}

    def test_keywords_are_tuples(self, bundle: Path) -> None:
        meta = load_locale_meta("ko")
        assert meta is not None
        assert isinstance(meta.topic_keywords["layers"], tuple)

    def test_absent_optional_fields_are_simply_not_in_the_maps(
        self, bundle: Path
    ) -> None:
        meta = load_locale_meta("ko")
        assert meta is not None
        assert "colour" not in meta.topic_summaries
        assert "colour" not in meta.topic_keywords

    def test_sections_and_topics_may_be_omitted_entirely(self, bundle: Path) -> None:
        _set_meta(bundle, "ko", {"schema_version": 1, "locale": "ko"})
        meta = load_locale_meta("ko")
        assert meta is not None
        assert not meta.section_titles and not meta.topic_titles

    def test_maps_are_read_only(self, bundle: Path) -> None:
        meta = load_locale_meta("ko")
        assert meta is not None
        with pytest.raises(TypeError):
            meta.topic_titles["x"] = "y"  # type: ignore[index]

    def test_unknown_ids_are_not_checked_here(self, bundle: Path) -> None:
        data = json.loads(json.dumps(_KO_META))
        data["topics"]["not-in-the-manifest"] = {"title": "ghost"}
        _set_meta(bundle, "ko", data)
        meta = load_locale_meta("ko")
        assert meta is not None and "not-in-the-manifest" in meta.topic_titles

    def test_unicode_text_round_trips(self, bundle: Path) -> None:
        data = json.loads(json.dumps(_KO_META))
        data["topics"]["layers"]["title"] = "계층 — レイヤー"
        _put(
            bundle,
            "content/ko/meta.json",
            json.dumps(data, ensure_ascii=False),
        )
        meta = load_locale_meta("ko")
        assert meta is not None
        assert meta.topic_titles["layers"] == data["topics"]["layers"]["title"]


class TestLoadLocaleMetaAbsent:
    def test_locale_without_a_meta_file_is_none(self, bundle: Path) -> None:
        assert load_locale_meta("en") is None
        assert load_locale_meta("de") is None

    def test_locale_without_a_folder_is_none(self, bundle: Path) -> None:
        assert load_locale_meta("zz") is None

    def test_a_directory_named_meta_json_is_none(self, bundle: Path) -> None:
        (bundle / "content" / "ru" / META_FILE_NAME).mkdir()
        assert load_locale_meta("ru") is None

    def test_committed_english_has_no_meta(self) -> None:
        assert load_locale_meta(DEFAULT_GUIDE_LOCALE) is None

    def test_committed_spanish_meta_is_absent_or_well_formed(self) -> None:
        meta = load_locale_meta("es")
        assert meta is None or (meta.locale == "es" and meta.schema_version >= 1)

    def test_committed_bundle_has_no_meta_that_fails_to_load(self) -> None:
        for locale in sorted(available_locales()):
            meta = load_locale_meta(locale)
            assert meta is None or meta.locale == locale


class TestLoadLocaleMetaLocaleGuard:
    @pytest.mark.parametrize(
        "locale",
        ["../x", "a/b", "a" + chr(92) + "b", "", "C:x", ".", "..", "/ko", "ko/.."],
        ids=[
            "parent",
            "two-segments",
            "backslash",
            "empty",
            "drive-letter",
            "dot",
            "dotdot",
            "absolute",
            "trailing-parent",
        ],
    )
    def test_locale_code_must_be_one_plain_name(
        self, bundle: Path, locale: str
    ) -> None:
        with pytest.raises(GuideContentError):
            load_locale_meta(locale)

    def test_a_planted_file_outside_content_is_never_reached(
        self, bundle: Path
    ) -> None:
        _put(bundle, "meta.json", json.dumps({**_KO_META, "locale": ".."}))
        with pytest.raises(GuideContentError):
            load_locale_meta("..")


class TestLoadLocaleMetaRejections:
    def test_oversized_file_is_rejected_before_decode(
        self, bundle: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(guide_content, "GUIDE_MAX_CONTENT_BYTES", 16)
        with pytest.raises(GuideContentError, match="exceeds 16 bytes"):
            load_locale_meta("ko")

    def test_oversized_file_at_the_real_ceiling_is_rejected(self, bundle: Path) -> None:
        padding = "x" * (GUIDE_MAX_CONTENT_BYTES + 1)
        _put(bundle, "content/ko/meta.json", padding)
        with pytest.raises(GuideContentError, match="exceeds"):
            load_locale_meta("ko")

    def test_oversize_check_precedes_the_utf8_check(self, bundle: Path) -> None:
        _put(bundle, "content/ko/meta.json", b"\xff" * (GUIDE_MAX_CONTENT_BYTES + 1))
        with pytest.raises(GuideContentError, match="exceeds"):
            load_locale_meta("ko")

    def test_non_utf8_bytes_are_rejected(self, bundle: Path) -> None:
        _put(bundle, "content/ko/meta.json", b"\xff\xfe{}")
        with pytest.raises(GuideContentError, match="not valid UTF-8"):
            load_locale_meta("ko")

    def test_invalid_json_is_rejected(self, bundle: Path) -> None:
        _put(bundle, "content/ko/meta.json", "{not json")
        with pytest.raises(GuideContentError, match="not valid JSON"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("root", [[], "text", 3, None])
    def test_root_must_be_an_object(self, bundle: Path, root: object) -> None:
        _set_meta(bundle, "ko", root)
        with pytest.raises(GuideContentError, match="root must be a JSON object"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("version", ["1", 1.0, True, False, None, [1]])
    def test_schema_version_must_be_an_integer(
        self, bundle: Path, version: object
    ) -> None:
        _set_meta(bundle, "ko", {**_KO_META, "schema_version": version})
        with pytest.raises(GuideContentError, match="schema_version"):
            load_locale_meta("ko")

    def test_missing_schema_version_is_rejected(self, bundle: Path) -> None:
        data = {k: v for k, v in _KO_META.items() if k != "schema_version"}
        _set_meta(bundle, "ko", data)
        with pytest.raises(GuideContentError, match="schema_version"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("declared", [None, "", "  ", 5, "ja", "KO"])
    def test_declared_locale_must_equal_the_folder(
        self, bundle: Path, declared: object
    ) -> None:
        _set_meta(bundle, "ko", {**_KO_META, "locale": declared})
        with pytest.raises(GuideContentError):
            load_locale_meta("ko")

    def test_missing_declared_locale_is_rejected(self, bundle: Path) -> None:
        data = {k: v for k, v in _KO_META.items() if k != "locale"}
        _set_meta(bundle, "ko", data)
        with pytest.raises(GuideContentError, match="locale"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("group", ["sections", "topics"])
    @pytest.mark.parametrize("value", [[], "x", 1, None])
    def test_group_must_be_an_object(
        self, bundle: Path, group: str, value: object
    ) -> None:
        _set_meta(bundle, "ko", {**_KO_META, group: value})
        with pytest.raises(GuideContentError, match="must be an object"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("group", ["sections", "topics"])
    def test_each_entry_must_be_an_object(self, bundle: Path, group: str) -> None:
        _set_meta(bundle, "ko", {**_KO_META, group: {"basics": "flat string"}})
        with pytest.raises(GuideContentError, match="must be an object"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("bad", ["", "   ", 7, None, ["t"]])
    def test_section_title_must_be_a_non_empty_string(
        self, bundle: Path, bad: object
    ) -> None:
        data = {**_KO_META, "sections": {"basics": {"title": bad}}}
        _set_meta(bundle, "ko", data)
        with pytest.raises(GuideContentError, match="non-empty string"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("field", ["title", "summary"])
    @pytest.mark.parametrize("bad", ["", " \t", 0, None])
    def test_topic_text_must_be_a_non_empty_string(
        self, bundle: Path, field: str, bad: object
    ) -> None:
        data = {**_KO_META, "topics": {"layers": {field: bad}}}
        _set_meta(bundle, "ko", data)
        with pytest.raises(GuideContentError, match="non-empty string"):
            load_locale_meta("ko")

    @pytest.mark.parametrize("bad", ["a b", {"a": 1}, [1], ["ok", 2], None, 5])
    def test_keywords_must_be_a_list_of_strings(
        self, bundle: Path, bad: object
    ) -> None:
        data = {**_KO_META, "topics": {"layers": {"keywords": bad}}}
        _set_meta(bundle, "ko", data)
        with pytest.raises(GuideContentError, match="list of strings"):
            load_locale_meta("ko")

    def test_empty_keyword_list_is_well_formed(self, bundle: Path) -> None:
        data = {**_KO_META, "topics": {"layers": {"keywords": []}}}
        _set_meta(bundle, "ko", data)
        meta = load_locale_meta("ko")
        assert meta is not None and meta.topic_keywords["layers"] == ()

    def test_unreadable_file_surfaces_the_domain_error(
        self, bundle: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_root = bundle

        class _Node:
            def __truediv__(self, other: str) -> "_Node":
                return self

            def is_file(self) -> bool:
                return True

            def read_bytes(self) -> bytes:
                raise OSError("disk gone")

        monkeypatch.setattr(guide_content, "bundle_root", lambda: _Node())
        with pytest.raises(GuideContentError, match="not readable"):
            load_locale_meta("ko")
        assert real_root.exists()


# --------------------------------------------------------------------------- #
# read_content: wording unchanged by the shared-reader refactor               #
# --------------------------------------------------------------------------- #


class TestReadContentMessagesUnchanged:
    def test_missing_page_message(self, bundle: Path) -> None:
        with pytest.raises(GuideContentError) as excinfo:
            read_content("content/ko/colour.md")
        assert str(excinfo.value) == "guide content not found: 'content/ko/colour.md'"

    def test_oversized_page_message(
        self, bundle: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(guide_content, "GUIDE_MAX_CONTENT_BYTES", 4)
        with pytest.raises(GuideContentError) as excinfo:
            read_content("content/en/layers.md")
        assert str(excinfo.value) == (
            "guide content exceeds 4 bytes: 'content/en/layers.md'"
        )

    def test_invalid_utf8_page_message(self, bundle: Path) -> None:
        _put(bundle, "content/en/layers.md", b"\xff\xfe")
        with pytest.raises(GuideContentError) as excinfo:
            read_content("content/en/layers.md")
        assert str(excinfo.value) == (
            "guide content is not valid UTF-8: 'content/en/layers.md'"
        )

    def test_page_text_is_returned_verbatim(self, bundle: Path) -> None:
        assert read_content("content/ko/layers.md") == "# KO layers\n"

    def test_committed_page_still_reads(self) -> None:
        assert read_content("content/en/layers.md").startswith("#")
        assert bundle_root().is_dir()


# --------------------------------------------------------------------------- #
# properties                                                                  #
# --------------------------------------------------------------------------- #

_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=1, max_size=12
).filter(lambda s: s.strip())
_IDS = st.sampled_from(["layers", "colour", "other", "x-1"])


@settings(max_examples=40, deadline=None)
@given(
    titles=st.dictionaries(_IDS, _TEXT, max_size=4),
    summaries=st.dictionaries(_IDS, _TEXT, max_size=4),
    keywords=st.dictionaries(_IDS, st.lists(_TEXT, max_size=3), max_size=4),
)
def test_any_well_formed_file_loads_to_exactly_the_fields_present(
    titles: dict[str, str],
    summaries: dict[str, str],
    keywords: dict[str, list[str]],
) -> None:
    topics: dict[str, dict[str, object]] = {}
    for item_id, value in titles.items():
        topics.setdefault(item_id, {})["title"] = value
    for item_id, value in summaries.items():
        topics.setdefault(item_id, {})["summary"] = value
    for item_id, items in keywords.items():
        topics.setdefault(item_id, {})["keywords"] = items
    payload = {"schema_version": 1, "locale": "ko", "topics": topics}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _put(root, "content/ko/meta.json", json.dumps(payload))
        with mock.patch.object(guide_content, "bundle_root", lambda: root):
            meta = load_locale_meta("ko")
    assert meta is not None
    assert dict(meta.topic_titles) == titles
    assert dict(meta.topic_summaries) == summaries
    assert {k: list(v) for k, v in meta.topic_keywords.items()} == keywords


@settings(max_examples=40, deadline=None)
@given(
    pages=st.dictionaries(
        st.sampled_from(["ko", "ru", "de", "en"]),
        st.sets(st.sampled_from(["layers", "colour"])),
        max_size=4,
    )
)
def test_topic_locales_is_the_set_of_folders_holding_the_page(
    pages: dict[str, set[str]],
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for locale, stems in pages.items():
            (root / "content" / locale).mkdir(parents=True)
            for stem in stems:
                _put(root, f"content/{locale}/{stem}.md", "#\n")
        with mock.patch.object(guide_content, "bundle_root", lambda: root):
            for stem in ("layers", "colour"):
                expected = frozenset(
                    locale for locale, held in pages.items() if stem in held
                )
                assert topic_locales(stem) == expected
