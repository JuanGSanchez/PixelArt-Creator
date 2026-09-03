"""Path-traversal defence tests for the asset catalog (Article VII).

Exercises the two containment surfaces of ``data/asset_catalog_io`` (ADR-0030;
research §5): :func:`_safe_asset_id` (an ``asset_id`` used as a sidecar filename) and
:func:`_resolve_within` (``resolve()`` + ``relative_to`` containment for the advisory
``path`` field). One test per traversal class — ``..`` escape, absolute-path escape,
deep/escaping traversal, and a Windows drive-letter escape — plus the safe-path pass and
the loader's rejection of a sidecar whose advisory ``path`` escapes the root.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pixelart_creator.data import asset_catalog_io as cio
from pixelart_creator.data.asset_catalog_io import (
    AssetCatalogError,
    _resolve_within,
    _safe_asset_id,
    load_catalog,
)
from pixelart_creator.logic.content_hash import content_hash

HASH = content_hash(b"payload")


# --------------------------------------------------------------------------- #
# _safe_asset_id — the sidecar-filename charset guard                          #
# --------------------------------------------------------------------------- #


def test_safe_asset_id_accepts_plain_id() -> None:
    assert _safe_asset_id("asset-1_v2.final") == "asset-1_v2.final"


def test_safe_asset_id_rejects_empty_or_non_str() -> None:
    with pytest.raises(AssetCatalogError):
        _safe_asset_id("")
    with pytest.raises(AssetCatalogError):
        _safe_asset_id(123)  # type: ignore[arg-type]


def test_safe_asset_id_rejects_dot_and_dotdot() -> None:
    with pytest.raises(AssetCatalogError):
        _safe_asset_id(".")
    with pytest.raises(AssetCatalogError):
        _safe_asset_id("..")


def test_safe_asset_id_rejects_forward_slash() -> None:
    with pytest.raises(AssetCatalogError):
        _safe_asset_id("sub/evil")


def test_safe_asset_id_rejects_backslash() -> None:
    backslash = chr(92)  # built dynamically to keep the source path-portable
    with pytest.raises(AssetCatalogError):
        _safe_asset_id(f"sub{backslash}evil")


def test_safe_asset_id_rejects_out_of_charset() -> None:
    with pytest.raises(AssetCatalogError):
        _safe_asset_id("bad id!")  # space + '!' are outside the safe charset


# --------------------------------------------------------------------------- #
# _resolve_within — containment defence (one test per class)                   #
# --------------------------------------------------------------------------- #


def test_resolve_within_accepts_contained_path(tmp_path) -> None:
    resolved = _resolve_within(tmp_path, "assets/a.json")
    assert resolved == (tmp_path.resolve() / "assets" / "a.json")


def test_resolve_within_rejects_dotdot_escape(tmp_path) -> None:
    with pytest.raises(AssetCatalogError):
        _resolve_within(tmp_path, "../evil.json")


def test_resolve_within_rejects_absolute_escape(tmp_path) -> None:
    outside = str(tmp_path.parent / "evil.json")
    assert Path(outside).is_absolute()
    with pytest.raises(AssetCatalogError):
        _resolve_within(tmp_path, outside)


def test_resolve_within_rejects_deep_traversal(tmp_path) -> None:
    # Nested descent that climbs back out past the root (symlink-style escape).
    with pytest.raises(AssetCatalogError):
        _resolve_within(tmp_path, "a/b/../../../evil.json")


@pytest.mark.skipif(os.name != "nt", reason="drive-letter escape is Windows-specific")
def test_resolve_within_rejects_drive_letter_escape(tmp_path) -> None:
    # A rooted drive path resolves outside the catalog root. Built dynamically
    # (system drive + backslash) so the source stays path-portable in CI.
    backslash = chr(92)
    drive = os.environ.get("SystemDrive", "C:")
    candidate = f"{drive}{backslash}Windows{backslash}evil.json"
    with pytest.raises(AssetCatalogError):
        _resolve_within(tmp_path, candidate)


# --------------------------------------------------------------------------- #
# End-to-end: loader rejects a sidecar whose advisory path escapes root        #
# --------------------------------------------------------------------------- #


def test_load_rejects_sidecar_path_escaping_root(tmp_path) -> None:
    (tmp_path / cio.INDEX_FILENAME).write_text(
        json.dumps(
            {
                "format": cio.FORMAT_NAME,
                "schema_version": cio.CATALOG_SCHEMA_VERSION,
                "asset_ids": ["a"],
            }
        ),
        encoding="utf-8",
    )
    assets = tmp_path / cio.ASSETS_DIRNAME
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "a.json").write_text(
        json.dumps(
            {
                "asset_id": "a",
                "kind": "sprite",
                "name": "Hero",
                "content_hash": HASH,
                "tags": [],
                "metadata": {},
                "path": "../../escape.pixproj",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)
