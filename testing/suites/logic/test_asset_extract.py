"""Unit tests for :mod:`pixelart_creator.logic.asset_extract` (S11, no Qt).

Covers the pure derivation of an asset's content hash and descriptor
(REQ-P11-LOGIC-009): ``hash_of`` and ``descriptor_for`` are exercised for
their happy path, every documented exception, and the determinism/edge
behaviours the task list names explicitly —

* ``SC-P11-LOGIC-009-1`` — one unchanged source extracted twice yields
  byte-identical bytes and the identical content hash
  (:class:`TestExtractionIsByteDeterministic`).
* ``SC-P11-LOGIC-009-2`` — the same content registered twice yields two
  catalog entries (distinct ``asset_id``) sharing one content hash (the
  CAS dedup key a single stored blob is addressed by) — asserted at this
  module's own surface, the descriptor level, since CAS storage itself is
  a ``data/`` concern outside this module
  (:class:`TestSameContentTwoRegistrations`).
* ``SC-P11-LOGIC-009-3`` — the module imports no Qt symbol
  (:class:`TestModuleIsQtFree`).

Also covers every other public callable's happy path, documented
exceptions, and boundaries (empty, oversized, invalid-type), plus
Hypothesis property tests for the two determinism invariants. Zero Qt
imports in this file; no I/O; no wall-clock, CPU-count, ordering or
network dependence; no unseeded randomness (the shared
``testing/suites/logic/conftest.py`` Hypothesis profile is derandomized).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from pixelart_creator.logic.asset_catalog import (
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_extract import (
    AssetExtractError,
    descriptor_for,
    hash_of,
)
from pixelart_creator.logic.constants import (
    MAX_METADATA_BYTES,
    MAX_TAG_BYTES,
    MAX_TAGS_PER_ASSET,
)
from pixelart_creator.logic.content_hash import ContentHashError, content_hash

_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "pixelart_creator"
    / "logic"
    / "asset_extract.py"
)

# Bounded, small strategies (well within MAX_TAGS_PER_ASSET / MAX_TAG_BYTES /
# MAX_METADATA_BYTES) so generated examples are always constructible and the
# property tests probe the determinism invariant, not the validation bounds
# (those are covered by explicit boundary tests below).
_blob_strategy = st.binary(max_size=256)
_identifier_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"), max_codepoint=0x2FFF
    ),
    min_size=1,
    max_size=32,
)
_tag_strategy = st.lists(
    st.text(
        min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Ll",))
    ),
    max_size=5,
    unique=True,
)
_metadata_value_strategy = st.one_of(
    st.text(max_size=20),
    st.integers(min_value=-1000, max_value=1000),
    st.booleans(),
    st.none(),
)
_metadata_strategy = st.dictionaries(
    st.text(
        min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Ll",))
    ),
    _metadata_value_strategy,
    max_size=5,
)
_path_strategy = st.one_of(st.none(), st.text(max_size=20))
_kind_strategy = st.sampled_from(list(AssetKind))


@st.composite
def _descriptor_kwargs(draw: "st.DrawFn") -> dict:
    """Draw a bounded, always-constructible kwargs set for ``descriptor_for``."""
    return {
        "asset_id": draw(_identifier_strategy),
        "name": draw(_identifier_strategy),
        "kind": draw(_kind_strategy),
        "tags": draw(_tag_strategy),
        "metadata": draw(_metadata_strategy),
        "path": draw(_path_strategy),
    }


class TestHashOf:
    """Behaviours of :func:`hash_of`."""

    def test_returns_64_char_lowercase_hex_digest(self) -> None:
        digest = hash_of(b"hello world")
        assert len(digest) == 64
        assert re.fullmatch(r"[0-9a-f]{64}", digest)

    def test_matches_shipped_content_hash_primitive(self) -> None:
        blob = b"asset payload bytes"
        assert hash_of(blob) == content_hash(blob)

    def test_deterministic_across_repeated_calls(self) -> None:
        blob = b"repeat me"
        assert hash_of(blob) == hash_of(blob) == hash_of(blob)

    def test_accepts_bytearray(self) -> None:
        # content_hash coerces bytearray to bytes internally; hash_of must
        # not narrow that acceptance.
        assert hash_of(bytearray(b"abc")) == hash_of(b"abc")

    def test_empty_blob_hashes_without_error(self) -> None:
        digest = hash_of(b"")
        assert len(digest) == 64

    def test_rejects_str(self) -> None:
        with pytest.raises(AssetExtractError):
            hash_of("not bytes")  # type: ignore[arg-type]

    def test_rejects_non_bytes_type(self) -> None:
        with pytest.raises(AssetExtractError):
            hash_of(12345)  # type: ignore[arg-type]

    def test_rejection_wraps_content_hash_error(self) -> None:
        with pytest.raises(AssetExtractError) as excinfo:
            hash_of(None)  # type: ignore[arg-type]
        assert isinstance(excinfo.value.__cause__, ContentHashError)

    @given(blob=_blob_strategy)
    def test_property_deterministic_same_blob_same_hash(self, blob: bytes) -> None:
        assert hash_of(blob) == hash_of(blob)

    @given(blob_a=_blob_strategy, blob_b=_blob_strategy)
    def test_property_distinct_blobs_distinct_hashes(
        self, blob_a: bytes, blob_b: bytes
    ) -> None:
        assume(blob_a != blob_b)
        assert hash_of(blob_a) != hash_of(blob_b)


class TestDescriptorForHappyPath:
    """Happy-path behaviours of :func:`descriptor_for`."""

    def test_returns_asset_descriptor_with_required_fields(self) -> None:
        blob = b"sprite bytes"
        result = descriptor_for(
            blob, asset_id="asset-1", name="Hero", kind=AssetKind.SPRITE
        )
        assert isinstance(result, AssetDescriptor)
        assert result.asset_id == "asset-1"
        assert result.name == "Hero"
        assert result.kind is AssetKind.SPRITE

    def test_content_hash_matches_hash_of(self) -> None:
        blob = b"tileset bytes"
        result = descriptor_for(
            blob, asset_id="asset-2", name="Ground", kind=AssetKind.TILESET
        )
        assert result.content_hash == hash_of(blob)

    def test_tags_default_to_empty_frozenset(self) -> None:
        result = descriptor_for(b"x", asset_id="a", name="n", kind=AssetKind.PALETTE)
        assert result.tags == frozenset()

    def test_tags_are_frozen_and_deduplicated(self) -> None:
        result = descriptor_for(
            b"x",
            asset_id="a",
            name="n",
            kind=AssetKind.PALETTE,
            tags=["red", "blue", "red"],
        )
        assert result.tags == frozenset({"red", "blue"})

    def test_metadata_defaults_to_empty_mapping(self) -> None:
        result = descriptor_for(b"x", asset_id="a", name="n", kind=AssetKind.TILEMAP)
        assert dict(result.metadata) == {}

    def test_metadata_none_is_treated_as_empty(self) -> None:
        result = descriptor_for(
            b"x", asset_id="a", name="n", kind=AssetKind.TILEMAP, metadata=None
        )
        assert dict(result.metadata) == {}

    def test_metadata_is_passed_through(self) -> None:
        result = descriptor_for(
            b"x",
            asset_id="a",
            name="n",
            kind=AssetKind.ANIMATION,
            metadata={"frames": 4, "loop": True},
        )
        assert dict(result.metadata) == {"frames": 4, "loop": True}

    def test_path_defaults_to_none(self) -> None:
        result = descriptor_for(b"x", asset_id="a", name="n", kind=AssetKind.SPRITE)
        assert result.path is None

    def test_path_is_passed_through(self) -> None:
        result = descriptor_for(
            b"x",
            asset_id="a",
            name="n",
            kind=AssetKind.SPRITE,
            path="library/hero.png",
        )
        assert result.path == "library/hero.png"

    @pytest.mark.parametrize("kind", list(AssetKind))
    def test_every_shipped_kind_is_accepted(self, kind: AssetKind) -> None:
        result = descriptor_for(b"x", asset_id="a", name="n", kind=kind)
        assert result.kind is kind


class TestDescriptorForExceptions:
    """Documented exceptions of :func:`descriptor_for`."""

    def test_rejects_blob_that_cannot_be_hashed(self) -> None:
        with pytest.raises(AssetExtractError) as excinfo:
            descriptor_for(
                "not bytes",  # type: ignore[arg-type]
                asset_id="a",
                name="n",
                kind=AssetKind.SPRITE,
            )
        assert isinstance(excinfo.value.__cause__, ContentHashError)

    def test_rejects_empty_asset_id(self) -> None:
        with pytest.raises(AssetExtractError) as excinfo:
            descriptor_for(b"x", asset_id="", name="n", kind=AssetKind.SPRITE)
        assert isinstance(excinfo.value.__cause__, AssetCatalogModelError)

    def test_rejects_non_str_asset_id(self) -> None:
        with pytest.raises(AssetExtractError):
            descriptor_for(
                b"x", asset_id=None, name="n", kind=AssetKind.SPRITE  # type: ignore[arg-type]
            )

    def test_rejects_empty_name(self) -> None:
        with pytest.raises(AssetExtractError):
            descriptor_for(b"x", asset_id="a", name="", kind=AssetKind.SPRITE)

    def test_rejects_invalid_kind(self) -> None:
        with pytest.raises(AssetExtractError):
            descriptor_for(
                b"x", asset_id="a", name="n", kind="sprite"  # type: ignore[arg-type]
            )

    def test_rejects_too_many_tags(self) -> None:
        too_many = [f"tag{i}" for i in range(MAX_TAGS_PER_ASSET + 1)]
        with pytest.raises(AssetExtractError) as excinfo:
            descriptor_for(
                b"x", asset_id="a", name="n", kind=AssetKind.SPRITE, tags=too_many
            )
        assert isinstance(excinfo.value.__cause__, AssetCatalogModelError)

    def test_rejects_oversized_tag(self) -> None:
        oversized_tag = "a" * (MAX_TAG_BYTES + 1)
        with pytest.raises(AssetExtractError):
            descriptor_for(
                b"x",
                asset_id="a",
                name="n",
                kind=AssetKind.SPRITE,
                tags=[oversized_tag],
            )

    def test_rejects_oversized_metadata(self) -> None:
        oversized_metadata = {"payload": "x" * (MAX_METADATA_BYTES + 100)}
        with pytest.raises(AssetExtractError) as excinfo:
            descriptor_for(
                b"x",
                asset_id="a",
                name="n",
                kind=AssetKind.SPRITE,
                metadata=oversized_metadata,
            )
        assert isinstance(excinfo.value.__cause__, AssetCatalogModelError)

    def test_rejects_non_json_scalar_metadata_value(self) -> None:
        with pytest.raises(AssetExtractError):
            descriptor_for(
                b"x",
                asset_id="a",
                name="n",
                kind=AssetKind.SPRITE,
                metadata={"nested": ["not", "a", "scalar"]},
            )


class TestExtractionIsByteDeterministic:
    """SC-P11-LOGIC-009-1 — one unchanged source extracted twice."""

    def test_hash_of_is_byte_identical_across_two_extractions(self) -> None:
        blob = bytes(range(256)) * 4  # a stand-in "unchanged in-app source"
        first = hash_of(blob)
        second = hash_of(blob)
        assert first == second
        assert len(first) == 64

    def test_descriptor_content_hash_identical_across_two_extractions(self) -> None:
        blob = b"unchanged source payload"
        kwargs = dict(asset_id="asset-1", name="Hero", kind=AssetKind.SPRITE)
        first = descriptor_for(blob, **kwargs)
        second = descriptor_for(blob, **kwargs)
        assert first.content_hash == second.content_hash
        assert first == second

    @given(blob=_blob_strategy, kwargs=_descriptor_kwargs())
    def test_property_descriptor_for_is_deterministic(
        self, blob: bytes, kwargs: dict
    ) -> None:
        first = descriptor_for(blob, **kwargs)
        second = descriptor_for(blob, **kwargs)
        assert first == second
        assert first.content_hash == second.content_hash == hash_of(blob)

    def test_deterministic_across_a_fresh_process(self) -> None:
        """Same blob hashed in a separate Python process yields the same digest.

        Cheap cross-process check for the "no dependence on process state"
        half of the determinism claim (module docstring: no wall-clock, no
        randomness, no locale dependence).
        """
        blob = b"cross-process determinism check"
        expected = hash_of(blob)
        root = Path(__file__).resolve().parents[3]
        script = (
            "from pixelart_creator.logic.asset_extract import hash_of; "
            f"print(hash_of({blob!r}))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == expected


class TestSameContentTwoRegistrations:
    """SC-P11-LOGIC-009-2 — identical content registered twice.

    ``asset_extract`` does not itself own catalog storage or the CAS blob
    store (those are ``logic/asset_catalog.AssetCatalog`` and a ``data/``
    concern respectively); at this module's surface the equivalent claim is
    that two descriptors built from identical bytes but distinct
    ``asset_id`` values are two distinct entries (by identity) that agree
    on the CAS dedup key (``content_hash``) — the fact a downstream CAS
    store would use to keep exactly one stored blob for that content.
    """

    def test_two_asset_ids_over_same_blob_share_one_content_hash(self) -> None:
        blob = b"shared content, registered twice"
        first = descriptor_for(
            blob, asset_id="asset-a", name="Copy A", kind=AssetKind.SPRITE
        )
        second = descriptor_for(
            blob, asset_id="asset-b", name="Copy B", kind=AssetKind.SPRITE
        )
        assert first.asset_id != second.asset_id
        assert first.content_hash == second.content_hash == hash_of(blob)
        assert first != second  # two distinct catalog entries


class TestModuleIsQtFree:
    """SC-P11-LOGIC-009-3 — the module imports no Qt symbol."""

    def test_source_contains_no_qt_import(self) -> None:
        source = _MODULE_PATH.read_bytes().decode("utf-8")
        assert not re.search(r"PySide6|PyQt|shiboken", source)

    def test_module_object_has_no_qt_attribute_names(self) -> None:
        import pixelart_creator.logic.asset_extract as module

        for attr_name in dir(module):
            assert "Qt" not in attr_name
