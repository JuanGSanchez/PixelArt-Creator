"""Cross-platform portability tests for the ``data/`` I/O layer (Slice 13A, no Qt).

Proves the Researcher-Q5 portability invariants of REQ-P13-DATA-001..005 at the
BYTE / behaviour level so they hold identically on every leg of the Win/Linux/macOS
CI matrix (no assertion depends on the host OS):

* **DATA-003 (line endings).** ``write_engine_preset`` (Unity ``.meta`` + Godot
  ``.tres``) emits LF and never CRLF regardless of the authoring OS — the regression
  test for the AGT-03 fix that pinned ``newline="\\n"`` — and a ``.pixproj`` artifact
  written then re-read round-trips byte-identically (no newline translation).
* **DATA-002 (encoding).** A project + a catalog carrying non-ASCII (accented / CJK /
  emoji) names, tags, and metadata save and reload faithfully as UTF-8, with no
  dependence on the platform default encoding (a Hypothesis round-trip property).
* **DATA-004 (case-sensitivity).** The content-addressable store keys by content hash
  (case-distinct content ⇒ distinct hash) and the catalog preserves the exact case of
  every reference; a catalog never emits two sidecar artifacts differing only by case.
* **DATA-001 (path portability).** A relative asset path round-trips irrespective of
  separator and no OS path separator leaks into the stored artifact bytes.
* **DATA-005 / Article VII.** A source audit confirms zero ``eval``/``exec`` on the
  ``data/`` I/O modules (path-traversal rejection is covered in ``test_asset_paths``).

Zero Qt; deterministic; bounded; Hypothesis for the round-trip property.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data import asset_cas, asset_catalog_io, export_io, project_io
from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import load_catalog, save_catalog
from pixelart_creator.data.export_io import write_engine_preset
from pixelart_creator.data.project_io import (
    deserialize,
    load_project,
    save_project,
    serialize,
)
from pixelart_creator.logic.animation import PlaybackMode
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import (
    EnginePreset,
    ExportFormat,
    ExportRequest,
    export_document,
)

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)

HASH_A = content_hash(b"a")

# A deliberately mixed non-ASCII string: accented Latin, CJK, and an emoji.
NON_ASCII_NAME = "café_日本語_🎨.png"

CRLF = b"\r\n"
LF = b"\n"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _sheet_result(colors, *, tag=None):
    """Build a multi-frame sprite-sheet export (a multi-line preset artifact)."""
    doc = Document(4, 4)
    doc.frames[0].layers[0].buffer.fill(colors[0])
    for color in colors[1:]:
        doc.add_frame().layers[0].buffer.fill(color)
    if tag is not None:
        name, lo, hi, mode = tag
        doc.make_add_tag_command(name, lo, hi, mode=mode).execute()
    return export_document(doc, ExportRequest(fmt=ExportFormat.SPRITE_SHEET, columns=8))


def _descriptor(asset_id="asset-1", **kwargs) -> AssetDescriptor:
    fields = dict(
        asset_id=asset_id,
        kind=AssetKind.SPRITE,
        name="Hero",
        content_hash=HASH_A,
    )
    fields.update(kwargs)
    return AssetDescriptor(**fields)


# --------------------------------------------------------------------------- #
# DATA-003 — line-ending determinism (regression for the AGT-03 newline fix)    #
# --------------------------------------------------------------------------- #


def test_unity_meta_is_lf_only_no_crlf(tmp_path: Path) -> None:
    """REQ-P13-DATA-003: the Unity ``.meta`` is LF-only on any OS (no CRLF).

    Regression for the AGT-03 fix pinning ``newline="\\n"`` — without it, a Windows
    write would translate every ``\\n`` to ``\\r\\n`` and the artifact would differ by
    authoring OS. Asserted on the raw bytes, so it holds on every CI matrix leg.
    """
    result = _sheet_result([RED, GREEN, BLUE], tag=("walk", 0, 2, PlaybackMode.LOOP))
    image_path = tmp_path / "sheet.png"
    write_engine_preset(EnginePreset.UNITY, result.metadata, image_path)
    raw = Path(str(image_path) + ".meta").read_bytes()
    assert CRLF not in raw
    assert LF in raw  # it is genuinely a multi-line artifact


def test_godot_tres_is_lf_only_no_crlf(tmp_path: Path) -> None:
    """REQ-P13-DATA-003: the Godot ``.tres`` is LF-only on any OS (no CRLF)."""
    result = _sheet_result([RED, GREEN, BLUE], tag=("walk", 0, 2, PlaybackMode.LOOP))
    image_path = tmp_path / "sheet.png"
    write_engine_preset(EnginePreset.GODOT, result.metadata, image_path)
    raw = image_path.with_suffix(".tres").read_bytes()
    assert CRLF not in raw
    assert LF in raw


def test_pixproj_bytes_roundtrip_no_newline_translation(tmp_path: Path) -> None:
    """REQ-P13-DATA-003, REQ-P13-DATA-005 (R-41): a ``.pixproj`` re-reads +
    re-saves byte-identically.

    The deterministic serialiser must not introduce CRLF and must produce a stable
    payload across a save → load → re-save cycle, so the on-disk bytes never differ
    merely because of the authoring OS -- the cross-OS project round-trip headline
    correctness claim of REQ-P13-DATA-005.
    """
    doc = Document(6, 4)
    doc.frames[0].layers[0].buffer.fill(RED)
    doc.add_frame().layers[0].buffer.fill(GREEN)
    saved = save_project(doc, tmp_path / "p.pixproj")
    first = saved.read_bytes()
    assert CRLF not in first
    reloaded = load_project(saved)
    re_saved = save_project(reloaded, tmp_path / "q.pixproj")
    assert re_saved.read_bytes() == first


# --------------------------------------------------------------------------- #
# DATA-002 — UTF-8 encoding faithfulness (no platform-default dependence)       #
# --------------------------------------------------------------------------- #


def test_project_non_ascii_roundtrips_faithfully(tmp_path: Path) -> None:
    """REQ-P13-DATA-002: non-ASCII metadata + layer names survive a file round-trip."""
    metadata = {"author": "José 🎨", "città": "Zürich", "名前": "日本語"}
    doc = Document(4, 4, metadata=metadata)
    doc.frames[0].layers[0].name = NON_ASCII_NAME
    saved = save_project(doc, tmp_path / "u.pixproj")
    reloaded = load_project(saved)
    assert dict(reloaded.metadata) == metadata
    assert reloaded.frames[0].layers[0].name == NON_ASCII_NAME
    # Explicit UTF-8 on read succeeds independent of any platform default.
    assert saved.read_text(encoding="utf-8")


def test_catalog_non_ascii_roundtrips_faithfully(tmp_path: Path) -> None:
    """REQ-P13-DATA-002: a catalog's non-ASCII name/tags/metadata reload faithfully."""
    desc = _descriptor(
        asset_id="asset-1",
        name=NON_ASCII_NAME,
        tags=frozenset({"héro", "日本"}),
        metadata={"author": "José", "città": "Zürich"},
    )
    save_catalog(AssetCatalog().add(desc), tmp_path)
    got = load_catalog(tmp_path).get("asset-1")
    assert got is not None
    assert got.name == NON_ASCII_NAME
    assert got.tags == frozenset({"héro", "日本"})
    assert dict(got.metadata) == {"author": "José", "città": "Zürich"}


# Rich non-ASCII alphabet (letters, digits, symbols incl. emoji); no control/surrogate.
_UNICODE = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "So", "Sm")),
    max_size=24,
)


@given(
    metadata=st.dictionaries(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=12,
        ),
        _UNICODE,
        max_size=6,
    )
)
def test_project_metadata_roundtrip_is_encoding_independent(metadata) -> None:
    """REQ-P13-DATA-002: arbitrary unicode metadata round-trips (property).

    Uses the in-memory ``serialize``/``deserialize`` pair — the reconstruction is
    equal to the input regardless of any host encoding, proving the model layer never
    reinterprets bytes by the platform default.
    """
    doc = Document(4, 4, metadata=metadata)
    restored = deserialize(serialize(doc))
    assert dict(restored.metadata) == {str(k): str(v) for k, v in metadata.items()}


# --------------------------------------------------------------------------- #
# DATA-004 — filename case-sensitivity discipline                              #
# --------------------------------------------------------------------------- #


def test_cas_case_distinct_content_has_distinct_hash() -> None:
    """REQ-P13-DATA-004: the CAS is content-hash keyed — case-distinct content differs.

    Because the store keys by content hash (never by a filename), ``Hero`` and ``hero``
    content can never silently collide on a case-insensitive FS nor break on a
    case-sensitive one.
    """
    store = ContentAddressableStore()
    upper = store.put(b"Hero")
    lower = store.put(b"hero")
    assert upper != lower
    assert store.get(upper) == b"Hero"
    assert store.get(lower) == b"hero"


def test_catalog_preserves_exact_case_of_references(tmp_path: Path) -> None:
    """REQ-P13-DATA-004: exact-case references survive a round-trip, not case-folded."""
    catalog = (
        AssetCatalog()
        .add(_descriptor(asset_id="hero-upper", name="Hero.png"))
        .add(_descriptor(asset_id="hero-lower", name="hero.png"))
    )
    save_catalog(catalog, tmp_path)
    reloaded = load_catalog(tmp_path)
    assert reloaded.get("hero-upper").name == "Hero.png"
    assert reloaded.get("hero-lower").name == "hero.png"
    assert reloaded.get("hero-upper").name != reloaded.get("hero-lower").name


def test_catalog_emits_no_case_colliding_sidecars(tmp_path: Path) -> None:
    """REQ-P13-DATA-004: no two emitted sidecar artifacts differ only by case.

    Two case-folded-equal sidecar filenames would collide on a case-insensitive FS
    (Windows/macOS); the catalog must not produce such a pair.
    """
    catalog = (
        AssetCatalog()
        .add(_descriptor(asset_id="hero-upper", name="Hero.png"))
        .add(_descriptor(asset_id="hero-lower", name="hero.png"))
    )
    save_catalog(catalog, tmp_path)
    sidecars = [p.name for p in (tmp_path / "assets").glob("*.json")]
    assert sidecars  # sanity: artifacts were emitted
    lowered = [name.lower() for name in sidecars]
    assert len(set(lowered)) == len(sidecars)


# --------------------------------------------------------------------------- #
# DATA-001 — portable path handling (pathlib; no separator leak)                #
# --------------------------------------------------------------------------- #


def test_catalog_relative_path_roundtrips_and_leaks_no_separator(
    tmp_path: Path,
) -> None:
    """REQ-P13-DATA-001: a relative POSIX asset path round-trips; no ``\\`` in bytes.

    The stored artifact must not carry an OS-specific path separator (a backslash),
    so the reference resolves the same on any OS. Uses ASCII-only fields so the only
    way a backslash could appear is a hard-coded separator (a JSON unicode escape
    would otherwise introduce one).
    """
    catalog = AssetCatalog().add(
        _descriptor(asset_id="a", path="assets/sub/hero.pixproj")
    )
    save_catalog(catalog, tmp_path)
    reloaded = load_catalog(tmp_path)
    assert reloaded.get("a").path == "assets/sub/hero.pixproj"
    backslash = bytes([92])  # a single '\' byte, built portably
    artifacts = [tmp_path / "catalog.json", *(tmp_path / "assets").glob("*.json")]
    for artifact in artifacts:
        assert backslash not in artifact.read_bytes()


# --------------------------------------------------------------------------- #
# DATA-005 / Article VII — no eval/exec on the data I/O modules (source audit)  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "module",
    [export_io, project_io, asset_catalog_io, asset_cas],
    ids=["export_io", "project_io", "asset_catalog_io", "asset_cas"],
)
def test_no_eval_or_exec_on_data_io_modules(module) -> None:
    """REQ-P13-DATA-008 / Article VII: the untrusted-input I/O modules never eval/exec.

    Path-traversal rejection itself is exercised in ``tests/data/test_asset_paths.py``;
    this is the complementary source audit that the ``eval``/``exec``-free discipline is
    preserved on the modules the portable round-trip depends on.
    """
    # Collapse all whitespace so ``eval (`` and ``exec (`` are caught too; the
    # substrings never match ``execute(`` (the 'ute' breaks the ``exec(`` pattern).
    compact = "".join(inspect.getsource(module).split())
    assert "eval(" not in compact
    assert "exec(" not in compact
