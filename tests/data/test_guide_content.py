"""Tests for pixelart_creator.data.guide_content (zero Qt) — the defensive reader.

Covers REQ-UG-DATA-001 (offline bundled reader, no network, domain error not crash),
-002 (single-sourced discovery over the committed bundle) and -003 / Article VII (the
bundle-root path guard, the size guard, content-as-text-never-executed). Maps to
Gherkin SC-D001-1/-2 and SC-D003-2.

Guard / error paths use a fixture bundle written into ``tmp_path`` and a monkeypatched
:func:`bundle_root`, so every branch (path-guard rejection classes, size guard,
malformed manifest, missing/unreadable/invalid-UTF-8 content) is exercised without Qt
and without touching the real committed bundle. One test per rejection class.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from pixelart_creator.data import guide_content
from pixelart_creator.data.guide_content import (
    GuideContentError,
    available_locales,
    bundle_root,
    load_manifest,
    read_content,
)
from pixelart_creator.logic.constants import GUIDE_MAX_CONTENT_BYTES
from pixelart_creator.logic.guide_model import Manifest, build_model

# --------------------------------------------------------------------------- #
# fixtures — a writable fixture bundle standing in for the package data       #
# --------------------------------------------------------------------------- #

_VALID_MANIFEST = {
    "schema_version": 1,
    "default_locale": "en",
    "sections": [
        {
            "id": "layers",
            "title": "Layers",
            "topics": [
                {
                    "id": "layers",
                    "title": "Layers",
                    "content": "layers",
                    "keywords": ["opacity", "blend"],
                    "summary": "The layer system.",
                }
            ],
        }
    ],
}


@pytest.fixture
def fixture_bundle(tmp_path, monkeypatch):
    """Create a minimal on-disk bundle and point bundle_root() at it.

    Returns the bundle root :class:`~pathlib.Path` (a valid ``Traversable``) so a
    test can add/alter files. Writes ``manifest.json`` + ``content/en/layers.md``.
    """
    root = tmp_path / "userguide_content"
    content_en = root / "content" / "en"
    content_en.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps(_VALID_MANIFEST), encoding="utf-8")
    (content_en / "layers.md").write_text("# Layers\n\nText.", encoding="utf-8")
    monkeypatch.setattr(guide_content, "bundle_root", lambda: root)
    return root


# --------------------------------------------------------------------------- #
# REQ-UG-DATA-002 — bundle_root + real committed bundle discovery             #
# --------------------------------------------------------------------------- #


def test_bundle_root_resolves_and_contains_manifest():
    """bundle_root() resolves via importlib.resources to the committed bundle."""
    root = bundle_root()
    assert (root / "manifest.json").is_file()


def test_real_bundle_loads_and_builds():
    """SC-D001-1/SC-D002-1: the committed bundle loads + builds (single-sourced)."""
    manifest = load_manifest()
    assert isinstance(manifest, Manifest)
    model = build_model(manifest)
    assert len(model.sections) >= 1


def test_available_locales_of_real_bundle_includes_default():
    assert "en" in available_locales()


# --------------------------------------------------------------------------- #
# REQ-UG-DATA-001 — load_manifest happy path + defensive error paths          #
# --------------------------------------------------------------------------- #


def test_load_manifest_parses_fixture_bundle(fixture_bundle):
    manifest = load_manifest()
    assert manifest.schema_version == 1
    assert manifest.default_locale == "en"
    assert manifest.sections[0].id == "layers"
    assert manifest.sections[0].topics[0].keywords == ("opacity", "blend")


def test_load_manifest_missing_file_raises(tmp_path, monkeypatch):
    """SC-D001-2: a missing manifest surfaces a domain error, not a crash."""
    empty = tmp_path / "empty_bundle"
    empty.mkdir()
    monkeypatch.setattr(guide_content, "bundle_root", lambda: empty)
    with pytest.raises(GuideContentError, match="not readable"):
        load_manifest()


def test_load_manifest_invalid_json_raises(fixture_bundle):
    (fixture_bundle / "manifest.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(GuideContentError, match="not valid JSON"):
        load_manifest()


def test_load_manifest_non_object_root_raises(fixture_bundle):
    (fixture_bundle / "manifest.json").write_text("[]", encoding="utf-8")
    with pytest.raises(GuideContentError, match="root must be a JSON object"):
        load_manifest()


def test_load_manifest_sections_not_list_raises(fixture_bundle):
    (fixture_bundle / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "default_locale": "en", "sections": {}}),
        encoding="utf-8",
    )
    with pytest.raises(GuideContentError, match="'sections' must be a list"):
        load_manifest()


@pytest.mark.parametrize("version", ["1", True, 1.5, None])
def test_load_manifest_bad_schema_version_raises(fixture_bundle, version):
    """schema_version must be a real int — a bool (True==1) is rejected too."""
    data = {**_VALID_MANIFEST, "schema_version": version}
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuideContentError, match="'schema_version' must be an integer"):
        load_manifest()


@pytest.mark.parametrize("locale", ["", "   ", 5, None])
def test_load_manifest_bad_default_locale_raises(fixture_bundle, locale):
    data = {**_VALID_MANIFEST, "default_locale": locale}
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuideContentError, match="default_locale"):
        load_manifest()


def test_load_manifest_section_not_object_raises(fixture_bundle):
    data = {**_VALID_MANIFEST, "sections": ["not-an-object"]}
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuideContentError, match=r"sections\[0\] must be an object"):
        load_manifest()


def test_load_manifest_topics_not_list_raises(fixture_bundle):
    data = {
        **_VALID_MANIFEST,
        "sections": [{"id": "s", "title": "S", "topics": "nope"}],
    }
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuideContentError, match="topics must be a list"):
        load_manifest()


def test_load_manifest_topic_not_object_raises(fixture_bundle):
    data = {
        **_VALID_MANIFEST,
        "sections": [{"id": "s", "title": "S", "topics": ["nope"]}],
    }
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuideContentError, match="topic in .* must be an object"):
        load_manifest()


def test_load_manifest_missing_topic_field_raises(fixture_bundle):
    data = {
        **_VALID_MANIFEST,
        "sections": [
            {
                "id": "s",
                "title": "S",
                "topics": [{"id": "t", "title": "T", "content": "c"}],
            }
        ],
    }
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuideContentError, match="summary"):
        load_manifest()


def test_load_manifest_bad_keywords_type_raises(fixture_bundle):
    data = {
        **_VALID_MANIFEST,
        "sections": [
            {
                "id": "s",
                "title": "S",
                "topics": [
                    {
                        "id": "t",
                        "title": "T",
                        "content": "c",
                        "keywords": [1, 2, 3],
                        "summary": "s",
                    }
                ],
            }
        ],
    }
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(GuideContentError, match="keywords.* must be a list of strings"):
        load_manifest()


def test_load_manifest_keywords_default_to_empty(fixture_bundle):
    """An omitted keywords field defaults to an empty tuple (not an error)."""
    data = {
        **_VALID_MANIFEST,
        "sections": [
            {
                "id": "s",
                "title": "S",
                "topics": [{"id": "t", "title": "T", "content": "c", "summary": "s"}],
            }
        ],
    }
    (fixture_bundle / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    manifest = load_manifest()
    assert manifest.sections[0].topics[0].keywords == ()


# --------------------------------------------------------------------------- #
# REQ-UG-DATA-001 — read_content happy path                                   #
# --------------------------------------------------------------------------- #


def test_read_content_returns_text(fixture_bundle):
    """SC-D001-1: content is returned as text from local package data."""
    text = read_content("content/en/layers.md")
    assert isinstance(text, str)
    assert "# Layers" in text


def test_read_content_of_real_bundle_returns_markdown():
    """The committed bundle's layers topic reads as markdown text."""
    text = read_content("content/en/layers.md")
    assert isinstance(text, str)
    assert text  # non-empty


# --------------------------------------------------------------------------- #
# REQ-UG-DATA-003 / Article VII — path guard, one test per rejection class    #
# --------------------------------------------------------------------------- #


def test_path_guard_rejects_empty_ref(fixture_bundle):
    with pytest.raises(GuideContentError, match="non-empty string"):
        read_content("")


def test_path_guard_rejects_backslash(fixture_bundle):
    with pytest.raises(GuideContentError, match="backslash"):
        read_content("content\\en\\layers.md")  # portability: ok (guard input)


def test_path_guard_rejects_absolute_ref(fixture_bundle):
    with pytest.raises(GuideContentError, match="must be relative"):
        read_content("/etc/passwd")


def test_path_guard_rejects_parent_traversal(fixture_bundle):
    with pytest.raises(GuideContentError, match="escapes the bundle root"):
        read_content("content/en/../../secret.md")


def test_path_guard_rejects_dotdot_prefix(fixture_bundle):
    with pytest.raises(GuideContentError, match="escapes the bundle root"):
        read_content("../secret.md")


def test_path_guard_rejects_drive_letter_colon(fixture_bundle):
    with pytest.raises(GuideContentError, match="not portable"):
        read_content("C:/windows/system32")  # portability: ok (guard input)


def test_path_guard_rejects_colon_scheme(fixture_bundle):
    with pytest.raises(GuideContentError, match="not portable"):
        read_content("content/file:name.md")


# --------------------------------------------------------------------------- #
# REQ-UG-DATA-001/003 — missing / oversized / invalid-UTF-8 content           #
# --------------------------------------------------------------------------- #


def test_read_content_missing_file_raises(fixture_bundle):
    """SC-D001-2: a valid-but-absent ref raises a domain error (not a crash)."""
    with pytest.raises(GuideContentError, match="not found"):
        read_content("content/en/does-not-exist.md")


def test_read_content_directory_is_not_a_file(fixture_bundle):
    """A ref that resolves to a directory (not a file) is rejected."""
    with pytest.raises(GuideContentError, match="not found"):
        read_content("content/en")


def test_size_guard_rejects_oversized_before_decode(fixture_bundle, monkeypatch):
    """SC-D001-2: the size guard is enforced against GUIDE_MAX_CONTENT_BYTES.

    Lowering the ceiling to a few bytes makes the fixture file oversized — proving
    the guard reads the named constant, not a hard-coded literal, and rejects before
    decode.
    """
    monkeypatch.setattr(guide_content, "GUIDE_MAX_CONTENT_BYTES", 4)
    with pytest.raises(GuideContentError, match="exceeds 4 bytes"):
        read_content("content/en/layers.md")


def test_size_guard_default_ceiling_allows_normal_file(fixture_bundle):
    """A normal-sized file is well under the 1 MiB default ceiling."""
    assert GUIDE_MAX_CONTENT_BYTES == 1048576
    assert read_content("content/en/layers.md")


def test_read_content_invalid_utf8_raises(fixture_bundle):
    """Invalid UTF-8 bytes surface a domain error, not a UnicodeDecodeError."""
    (fixture_bundle / "content" / "en" / "layers.md").write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(GuideContentError, match="not valid UTF-8"):
        read_content("content/en/layers.md")


def test_read_content_oserror_on_read_surfaces_domain_error(monkeypatch):
    """An OSError while reading bytes is wrapped as GuideContentError, not raw."""

    class _RaisingNode:
        def __truediv__(self, other):
            return self

        def is_file(self):
            return True

        def read_bytes(self):
            raise OSError("disk gone")

    monkeypatch.setattr(guide_content, "bundle_root", lambda: _RaisingNode())
    with pytest.raises(GuideContentError, match="not readable"):
        read_content("content/en/layers.md")


# --------------------------------------------------------------------------- #
# available_locales — discovery of locale sub-dirs                            #
# --------------------------------------------------------------------------- #


def test_available_locales_lists_content_subdirs(fixture_bundle):
    (fixture_bundle / "content" / "es").mkdir()
    # a stray file under content/ is not a locale
    (fixture_bundle / "content" / "readme.txt").write_text("x", encoding="utf-8")
    locales = available_locales()
    assert locales == frozenset({"en", "es"})


def test_available_locales_empty_when_no_content_dir(tmp_path, monkeypatch):
    root = tmp_path / "bundle_no_content"
    root.mkdir()
    monkeypatch.setattr(guide_content, "bundle_root", lambda: root)
    assert available_locales() == frozenset()


# --------------------------------------------------------------------------- #
# REQ-UG-DATA-003 — content is never executed (no eval/exec) [review]         #
# --------------------------------------------------------------------------- #


def test_module_never_uses_eval_or_exec():
    """SC-D003-1: the reader never passes content to eval/exec."""
    source = inspect.getsource(guide_content)
    assert "eval(" not in source
    assert "exec(" not in source


def test_module_makes_no_network_import():
    """REQ-UG-DATA-001 / NFR-3: no networking module is imported by the reader."""
    source = inspect.getsource(guide_content)
    for banned in ("import socket", "import urllib", "import http", "requests"):
        assert banned not in source
