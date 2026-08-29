"""Unit tests for :mod:`pixelart_creator.data.asset_revision_io` (S11, no Qt).

Covers the revision-index + per-asset sidecar serialiser (ADR-0030 §6;
``REQ-P11-DATA-008``'s revision half; ``SC-P11-INGRESS-E2E-1``'s restart clause, at
unit level): round-tripping histories through ``write_history``/``write_index``/
``load_histories``/``save_histories``; the "absent index loads as ``{}`` and creates
nothing on disk" contract, asserted as a directory listing; the Article VII
untrusted-load defence (malformed index, unsupported schema_version, invalid hash,
unsafe id, path escape all raising ``AssetRevisionIOError``); and that a history
exceeding ``MAX_ASSET_VERSIONS`` or breaking the DAG invariant is rejected by the
logic-layer model and surfaced the same way. T42.
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data.asset_revision_io import (
    FORMAT_NAME,
    INDEX_FILENAME,
    REVISIONS_DIRNAME,
    REVISIONS_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    AssetRevisionIOError,
    load_histories,
    save_histories,
    write_history,
    write_index,
)
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_version import AssetRevision, AssetVersionHistory
from pixelart_creator.logic.constants import MAX_ASSET_VERSIONS, MAX_CATALOG_ASSETS
from pixelart_creator.logic.content_hash import content_hash


def revision(asset_id, payload, *, parent=None, marker=0, author=None) -> AssetRevision:
    return AssetRevision(
        asset_id=asset_id,
        content_hash=content_hash(payload),
        created_marker=marker,
        parent_hash=parent,
        author=author,
    )


def history_for(asset_id, *payloads, author=None) -> AssetVersionHistory:
    revisions = []
    parent = None
    for index, payload in enumerate(payloads):
        r = revision(asset_id, payload, parent=parent, marker=index, author=author)
        revisions.append(r)
        parent = r.content_hash
    return AssetVersionHistory(revisions=tuple(revisions))


def write_raw_index(
    root, asset_ids, *, format_name=FORMAT_NAME, schema_version=REVISIONS_SCHEMA_VERSION
):
    (root / INDEX_FILENAME).write_text(
        json.dumps(
            {
                "format": format_name,
                "schema_version": schema_version,
                "asset_ids": asset_ids,
            }
        ),
        encoding="utf-8",
    )


def write_raw_sidecar(root, asset_id, payload):
    directory = root / REVISIONS_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{asset_id}.json").write_text(json.dumps(payload), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #


def test_format_name_is_pixrevisions() -> None:
    assert FORMAT_NAME == "pixrevisions"


def test_schema_version_is_supported() -> None:
    assert REVISIONS_SCHEMA_VERSION == "1"
    assert REVISIONS_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS


def test_index_and_dir_filenames() -> None:
    assert INDEX_FILENAME == "revisions.json"
    assert REVISIONS_DIRNAME == "revisions"


def test_error_is_project_io_error() -> None:
    assert issubclass(AssetRevisionIOError, ProjectIOError)


# --------------------------------------------------------------------------- #
# Round-trip                                                                   #
# --------------------------------------------------------------------------- #


def test_write_history_and_index_then_load_round_trips(tmp_path) -> None:
    history = history_for("sprite", b"v1", b"v2", author="alice")
    write_history(tmp_path, "sprite", history)
    write_index(tmp_path, ["sprite"])
    loaded = load_histories(tmp_path)
    assert loaded == {"sprite": history}


def test_save_histories_round_trips_multiple_assets(tmp_path) -> None:
    histories = {
        "a": history_for("a", b"a1"),
        "b": history_for("b", b"b1", b"b2", b"b3"),
    }
    save_histories(tmp_path, histories)
    loaded = load_histories(tmp_path)
    assert loaded == histories


def test_save_histories_of_empty_mapping_creates_empty_index(tmp_path) -> None:
    save_histories(tmp_path, {})
    assert load_histories(tmp_path) == {}
    assert (tmp_path / INDEX_FILENAME).exists()


def test_history_with_parent_hash_none_root_round_trips(tmp_path) -> None:
    history = history_for("solo", b"only")
    save_histories(tmp_path, {"solo": history})
    loaded = load_histories(tmp_path)
    assert loaded["solo"].head().parent_hash is None


# --------------------------------------------------------------------------- #
# Absent index — {} and creates nothing on disk (directory listing, not just  #
# "no exception")                                                              #
# --------------------------------------------------------------------------- #


def test_absent_index_loads_as_empty_mapping(tmp_path) -> None:
    assert load_histories(tmp_path) == {}


def test_absent_index_creates_nothing_on_disk(tmp_path) -> None:
    before = sorted(p.name for p in tmp_path.iterdir())
    assert before == []
    result = load_histories(tmp_path)
    assert result == {}
    after = sorted(p.name for p in tmp_path.iterdir())
    assert after == []


# --------------------------------------------------------------------------- #
# write_history                                                                #
# --------------------------------------------------------------------------- #


def test_write_history_creates_revisions_dir_on_demand(tmp_path) -> None:
    assert not (tmp_path / REVISIONS_DIRNAME).exists()
    write_history(tmp_path, "sprite", history_for("sprite", b"v1"))
    assert (tmp_path / REVISIONS_DIRNAME).is_dir()
    assert (tmp_path / REVISIONS_DIRNAME / "sprite.json").exists()


def test_write_history_rejects_non_history_type(tmp_path) -> None:
    with pytest.raises(AssetRevisionIOError):
        write_history(tmp_path, "sprite", {"not": "a history"})  # type: ignore[arg-type]


def test_write_history_rejects_unsafe_id_dotdot(tmp_path) -> None:
    with pytest.raises(AssetRevisionIOError):
        write_history(tmp_path, "..", history_for("..", b"v1"))


def test_write_history_rejects_id_with_path_separator(tmp_path) -> None:
    with pytest.raises(AssetRevisionIOError):
        write_history(tmp_path, "a/b", history_for("a/b", b"v1"))


def test_write_history_does_not_touch_index(tmp_path) -> None:
    write_history(tmp_path, "sprite", history_for("sprite", b"v1"))
    assert not (tmp_path / INDEX_FILENAME).exists()


# --------------------------------------------------------------------------- #
# write_index                                                                  #
# --------------------------------------------------------------------------- #


def test_write_index_writes_expected_shape(tmp_path) -> None:
    write_index(tmp_path, ["b", "a"])
    payload = json.loads((tmp_path / INDEX_FILENAME).read_text(encoding="utf-8"))
    assert payload == {
        "format": FORMAT_NAME,
        "schema_version": REVISIONS_SCHEMA_VERSION,
        "asset_ids": ["b", "a"],
    }


def test_write_index_of_empty_sequence(tmp_path) -> None:
    write_index(tmp_path, [])
    payload = json.loads((tmp_path / INDEX_FILENAME).read_text(encoding="utf-8"))
    assert payload["asset_ids"] == []


# --------------------------------------------------------------------------- #
# load_histories — Article VII untrusted-load defence                         #
# --------------------------------------------------------------------------- #


def test_load_rejects_index_that_is_not_json(tmp_path) -> None:
    (tmp_path / INDEX_FILENAME).write_text("not json{{{", encoding="utf-8")
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_index_that_is_not_an_object(tmp_path) -> None:
    (tmp_path / INDEX_FILENAME).write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_wrong_format_marker(tmp_path) -> None:
    write_raw_index(tmp_path, [], format_name="not-pixrevisions")
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_unsupported_schema_version(tmp_path) -> None:
    write_raw_index(tmp_path, [], schema_version="999")
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_asset_ids_not_a_list(tmp_path) -> None:
    (tmp_path / INDEX_FILENAME).write_text(
        json.dumps(
            {
                "format": FORMAT_NAME,
                "schema_version": REVISIONS_SCHEMA_VERSION,
                "asset_ids": "sprite",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_asset_ids_exceeding_max_catalog_assets(tmp_path) -> None:
    oversized = [f"a{i}" for i in range(MAX_CATALOG_ASSETS + 1)]
    write_raw_index(tmp_path, oversized)
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_missing_sidecar_for_indexed_id(tmp_path) -> None:
    write_raw_index(tmp_path, ["ghost"])
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_empty_string_asset_id_in_index(tmp_path) -> None:
    write_raw_index(tmp_path, [""])
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_unsafe_asset_id_in_index(tmp_path) -> None:
    write_raw_index(tmp_path, ["a/../../escape"])
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_sidecar_that_is_not_an_object(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    write_raw_sidecar(tmp_path, "sprite", [1, 2, 3])
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_sidecar_asset_id_mismatch(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "other", "revisions": []})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_sidecar_revisions_not_a_list(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": "nope"})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_revision_entry_not_an_object(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": ["nope"]})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_revision_entry_asset_id_mismatch(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    entry = {
        "asset_id": "other",
        "content_hash": content_hash(b"v1"),
        "created_marker": 0,
        "parent_hash": None,
        "author": None,
    }
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": [entry]})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_invalid_content_hash(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    entry = {
        "asset_id": "sprite",
        "content_hash": "not-a-hash",
        "created_marker": 0,
        "parent_hash": None,
        "author": None,
    }
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": [entry]})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_invalid_parent_hash(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    entry = {
        "asset_id": "sprite",
        "content_hash": content_hash(b"v1"),
        "created_marker": 0,
        "parent_hash": "short",
        "author": None,
    }
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": [entry]})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_non_int_created_marker(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    entry = {
        "asset_id": "sprite",
        "content_hash": content_hash(b"v1"),
        "created_marker": "zero",
        "parent_hash": None,
        "author": None,
    }
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": [entry]})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_empty_author_string(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    entry = {
        "asset_id": "sprite",
        "content_hash": content_hash(b"v1"),
        "created_marker": 0,
        "parent_hash": None,
        "author": "",
    }
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": [entry]})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


# --------------------------------------------------------------------------- #
# Model-layer bounds surfaced through the IO layer                            #
# --------------------------------------------------------------------------- #


def test_load_rejects_history_exceeding_max_asset_versions(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    entries = []
    parent = None
    for index in range(MAX_ASSET_VERSIONS + 1):
        payload = f"v{index}".encode("ascii")
        digest = content_hash(payload)
        entries.append(
            {
                "asset_id": "sprite",
                "content_hash": digest,
                "created_marker": index,
                "parent_hash": parent,
                "author": None,
            }
        )
        parent = digest
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": entries})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)


def test_load_rejects_non_dag_parent_links(tmp_path) -> None:
    write_raw_index(tmp_path, ["sprite"])
    hash_0 = content_hash(b"v0")
    hash_1 = content_hash(b"v1")
    # Revision 0's parent_hash forward-references revision 1's own content_hash —
    # not a self-loop (caught at the single-revision level), but a later-revision
    # reference that breaks the DAG at history-construction time.
    entries = [
        {
            "asset_id": "sprite",
            "content_hash": hash_0,
            "created_marker": 0,
            "parent_hash": hash_1,
            "author": None,
        },
        {
            "asset_id": "sprite",
            "content_hash": hash_1,
            "created_marker": 1,
            "parent_hash": None,
            "author": None,
        },
    ]
    write_raw_sidecar(tmp_path, "sprite", {"asset_id": "sprite", "revisions": entries})
    with pytest.raises(AssetRevisionIOError):
        load_histories(tmp_path)
