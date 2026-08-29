"""Tests for the .pixproj schema's v6 "asset_refs" root array and back-compat (T19).

Covers ``pixelart_creator.data.project_io`` (``REQ-P11-UI-021`` persistence half,
``REQ-P11-DATA-010``..``-3``, ``phase-11-asset-ingress`` T12/T19): a populated
reference set round-trips at v6 with the key present exactly when non-empty (both
in the returned mapping and in the on-disk bytes); v1-v5 documents -- and a v6
document that never referenced anything -- load with an **empty** ``ReferenceSet``,
no migration and no silent upgrade; a malformed ``asset_refs`` entry raises
``ProjectIOError`` and the load fails **atomically** (no partial ``Document``, and
the failure surfaces before the rest of the payload, e.g. ``frames``, is even
read); the import-time ``ASSET_LIBRARY_EDIT`` ``PrefKey`` registration this slice
depends on holds from a **data-layer-only** import (no ``ui`` import anywhere in
``sys.modules``); ``FORMAT_VERSION`` is pinned to ``6`` exactly once, and every
other assertion compares to the module constant, never to a bare literal.

No Qt import (S11).
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_catalog import AssetKind
from pixelart_creator.logic.asset_edit_decisions import (
    DECISION_KEEP,
    DECISION_PICK_UP,
    AssetEditDecisions,
)
from pixelart_creator.logic.asset_references import (
    ASSET_LIBRARY_EDIT,
    AssetReference,
    ReferenceSet,
)
from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS
from pixelart_creator.logic.document import Document

_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _sample_reference_set() -> ReferenceSet:
    return ReferenceSet(
        references=(
            AssetReference("a1", _HASH_A, AssetKind.SPRITE, "Hero idle"),
            AssetReference("a2", _HASH_B, AssetKind.PALETTE, "Dusk"),
        )
    )


# --------------------------------------------------------------------------- #
# Version-bump integrity                                                      #
# --------------------------------------------------------------------------- #


def test_format_version_is_six():
    # v6 (ADR-0058, T12) is this slice's own documented current value -- a
    # deliberate pin, not a stale literal (contrast the disposition table in
    # this task's report for the 8 pre-existing "== 5" literals this bump made
    # stale elsewhere -- this assertion is the replacement for those, scoped to
    # the file this task owns).
    assert pio.FORMAT_VERSION == 6
    assert set(pio._SUPPORTED_VERSIONS) == {1, 2, 3, 4, 5, 6}


def test_serialized_payload_version_tracks_the_constant_never_a_literal():
    payload = pio.serialize(Document(4, 4))
    assert payload["version"] == pio.FORMAT_VERSION


# --------------------------------------------------------------------------- #
# v6 round trip, populated set -- key present exactly when non-empty          #
# --------------------------------------------------------------------------- #


def test_populated_reference_set_round_trips_through_serialize_deserialize():
    doc = Document(4, 4)
    refs = _sample_reference_set()

    payload = pio.serialize(doc, reference_set=refs)
    assert payload["version"] == pio.FORMAT_VERSION
    assert "asset_refs" in payload

    loaded_doc, loaded_refs = pio.deserialize_project(payload)
    assert loaded_refs == refs
    assert loaded_doc.width == doc.width and loaded_doc.height == doc.height


def test_populated_reference_set_round_trips_through_save_load(tmp_path):
    doc = Document(4, 4)
    refs = _sample_reference_set()

    path = pio.save_project(doc, tmp_path / "p", reference_set=refs)
    loaded_doc, loaded_refs = pio.load_project_with_asset_refs(path)
    assert loaded_refs == refs
    assert isinstance(loaded_doc, Document)


def test_asset_refs_entry_shape_matches_the_reference_fields():
    ref = AssetReference("a1", _HASH_A, AssetKind.SPRITE, "Hero idle")
    payload = pio.serialize(
        Document(4, 4), reference_set=ReferenceSet(references=(ref,))
    )
    assert payload["asset_refs"] == [
        {
            "asset_id": "a1",
            "content_hash": _HASH_A,
            "kind": "sprite",
            "last_known_name": "Hero idle",
        }
    ]


def test_asset_refs_key_absent_when_reference_set_is_none():
    payload = pio.serialize(Document(4, 4))
    assert "asset_refs" not in payload


def test_asset_refs_key_absent_when_reference_set_is_empty():
    payload = pio.serialize(Document(4, 4), reference_set=ReferenceSet())
    assert "asset_refs" not in payload


def test_asset_refs_key_present_exactly_when_non_empty_both_directions():
    empty_keys = set(pio.serialize(Document(4, 4), reference_set=ReferenceSet()).keys())
    populated_keys = set(
        pio.serialize(Document(4, 4), reference_set=_sample_reference_set()).keys()
    )
    assert populated_keys - empty_keys == {"asset_refs"}
    assert empty_keys - populated_keys == set()


def test_saved_bytes_omit_asset_refs_when_absent(tmp_path):
    path = pio.save_project(Document(4, 4), tmp_path / "p")
    raw = path.read_bytes()
    assert b'"asset_refs"' not in raw


def test_saved_bytes_include_asset_refs_when_populated(tmp_path):
    path = pio.save_project(
        Document(4, 4), tmp_path / "p", reference_set=_sample_reference_set()
    )
    raw = path.read_bytes()
    assert b'"asset_refs"' in raw


# --------------------------------------------------------------------------- #
# v1-v5 (and an unreferenced v6) load with an empty ReferenceSet -- no        #
# migration, no silent upgrade                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_pre_v6_fixture_loads_with_an_empty_reference_set_no_migration(version):
    payload = pio.serialize(Document(4, 4))
    payload["version"] = version
    if version < 5:
        payload.pop("prefs", None)
        payload.pop("ppi", None)
    assert "asset_refs" not in payload  # never had the key to begin with

    doc, refs = pio.deserialize_project(payload)
    assert refs == ReferenceSet()
    assert refs.entries() == ()
    assert isinstance(doc, Document)


def test_v6_document_that_never_referenced_anything_also_loads_empty():
    payload = pio.serialize(Document(4, 4))  # v6, no reference_set supplied
    assert payload["version"] == pio.FORMAT_VERSION
    assert "asset_refs" not in payload

    doc, refs = pio.deserialize_project(payload)
    assert refs == ReferenceSet()
    assert isinstance(doc, Document)


def test_load_project_unchanged_signature_and_behaviour_for_pre_v6_fixture(
    tmp_path,
):
    # load_project (Document-only) must behave identically pre- and
    # post-this-slice for a caller that never asked for the reference set.
    doc = Document(4, 4)
    path = pio.save_project(doc, tmp_path / "p")
    loaded = pio.load_project(path)
    assert isinstance(loaded, Document)
    assert loaded.width == 4 and loaded.height == 4


# --------------------------------------------------------------------------- #
# Malformed asset_refs -- ProjectIOError, atomic (no partial Document)        #
# --------------------------------------------------------------------------- #


def test_malformed_asset_refs_not_a_list_raises():
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = {"not": "a list"}
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


@pytest.mark.parametrize("bad_entry", ["not-an-object", 123, ["nested", "list"]])
def test_malformed_entry_not_an_object_raises(bad_entry):
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [bad_entry]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_malformed_entry_missing_asset_id_raises():
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [
        {"content_hash": _HASH_A, "kind": "sprite", "last_known_name": "Hero"}
    ]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_malformed_entry_missing_content_hash_raises():
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [{"asset_id": "a1", "kind": "sprite"}]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


@pytest.mark.parametrize(
    "bad_hash", ["nothex", "A" * 64, "a" * 63, "a" * 65, "", 12345]
)
def test_malformed_content_hash_shape_raises(bad_hash):
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [
        {
            "asset_id": "a1",
            "content_hash": bad_hash,
            "kind": "sprite",
            "last_known_name": "",
        }
    ]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_malformed_empty_asset_id_raises():
    # Reaches AssetReference.__post_init__'s own validation (empty asset_id),
    # not _parse_asset_ref's own _require calls -- a distinct raise site
    # (data/project_io.py's AssetReferenceError -> ProjectIOError translation).
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [
        {
            "asset_id": "",
            "content_hash": _HASH_A,
            "kind": "sprite",
            "last_known_name": "",
        }
    ]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_malformed_unknown_kind_raises():
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [
        {
            "asset_id": "a1",
            "content_hash": _HASH_A,
            "kind": "not-a-kind",
            "last_known_name": "",
        }
    ]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_malformed_last_known_name_wrong_type_raises():
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [
        {
            "asset_id": "a1",
            "content_hash": _HASH_A,
            "kind": "sprite",
            "last_known_name": 42,
        }
    ]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_malformed_duplicate_asset_id_raises():
    payload = pio.serialize(Document(4, 4))
    entry = {
        "asset_id": "a1",
        "content_hash": _HASH_A,
        "kind": "sprite",
        "last_known_name": "",
    }
    payload["asset_refs"] = [entry, dict(entry)]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_malformed_entry_over_max_catalog_assets_raises():
    too_many = [
        {
            "asset_id": f"a{i}",
            "content_hash": format(i, "064x"),
            "kind": "sprite",
            "last_known_name": "",
        }
        for i in range(MAX_CATALOG_ASSETS + 1)
    ]
    with pytest.raises(ProjectIOError):
        pio.parse_asset_refs(too_many)


def test_malformed_entry_raises_before_frames_is_even_read_atomic_order():
    # asset_refs is parsed before "frames" is read at all
    # (data/project_io.py deserialize(): parse_asset_refs(...) precedes
    # _get(payload, "frames", list)). Deleting "frames" too proves the
    # asset_refs failure is what actually surfaces, not a downstream one --
    # i.e. the load fails atomically on the first bad field, never partially.
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [{"asset_id": "a1"}]  # malformed: no content_hash
    del payload["frames"]
    with pytest.raises(ProjectIOError, match="content_hash"):
        pio.deserialize(payload)


def test_deserialize_project_raises_and_returns_nothing_on_malformed_entry():
    payload = pio.serialize(Document(4, 4))
    payload["asset_refs"] = [
        {"asset_id": "a1", "content_hash": "bad", "kind": "sprite"}
    ]
    with pytest.raises(ProjectIOError):
        pio.deserialize_project(payload)


def test_load_project_with_asset_refs_atomic_on_malformed_file(tmp_path):
    doc = Document(4, 4)
    path = pio.save_project(doc, tmp_path / "p", reference_set=_sample_reference_set())
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["asset_refs"][0]["content_hash"] = "nothex"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ProjectIOError):
        pio.load_project_with_asset_refs(path)


# --------------------------------------------------------------------------- #
# The preference half (largely restates phase-5's "prefs" behaviour -- only   #
# the parts specific to ASSET_LIBRARY_EDIT are exercised here, not duplicated)#
# --------------------------------------------------------------------------- #


def test_asset_library_edit_preference_round_trips(tmp_path):
    doc = Document(4, 4)
    doc.prefs = doc.prefs.with_value(ASSET_LIBRARY_EDIT, "always_keep_referenced")
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "p"))
    assert loaded.prefs.get(ASSET_LIBRARY_EDIT) == "always_keep_referenced"


def test_asset_library_edit_absence_reads_as_ask():
    payload = pio.serialize(Document(4, 4))
    assert "prefs" not in payload  # default is never explicitly set -> absent
    loaded = pio.deserialize(payload)
    assert loaded.prefs.get(ASSET_LIBRARY_EDIT) == "ask"


def test_asset_library_edit_pre_field_project_opens_without_error():
    payload = pio.serialize(Document(4, 4))
    payload["version"] = 4
    payload.pop("prefs", None)
    payload.pop("ppi", None)
    loaded = pio.deserialize(payload)
    assert loaded.prefs.get(ASSET_LIBRARY_EDIT) == "ask"


# --------------------------------------------------------------------------- #
# Data-layer-only import proof (T19's P11-R2 addition)                        #
# --------------------------------------------------------------------------- #


def test_data_layer_only_import_registers_the_pref_key_no_ui_import():
    """A fresh interpreter, importing only ``data``/``logic`` modules, still has
    the ``ASSET_LIBRARY_EDIT`` PrefKey registered and can round-trip a v6
    reference set -- proving the import-time registration
    (``logic/asset_references.py``'s module-scope ``project_prefs.register(...)``,
    triggered transitively by ``data/project_io.py``'s own module-scope import of
    that module) holds without a single ``pixelart_creator.ui`` import anywhere
    in ``sys.modules``. This is the guard against the silent-drop path at
    ``data/project_io.py``'s ``_parse_prefs`` (an unregistered key is dropped,
    not refused) ever regressing because the registration moved into a function
    body.
    """
    script = (
        "import sys\n"
        "from pixelart_creator.data import project_io as pio\n"
        "from pixelart_creator.logic import project_prefs\n"
        "from pixelart_creator.logic.document import Document\n"
        "from pixelart_creator.logic.asset_references import (\n"
        "    AssetReference, ReferenceSet,\n"
        ")\n"
        "from pixelart_creator.logic.asset_catalog import AssetKind\n"
        "assert 'asset_library_edit' in project_prefs.REGISTRY, "
        "'PrefKey not registered from a data-layer-only import'\n"
        "ui_modules = [m for m in sys.modules if m.startswith('pixelart_creator.ui')]\n"
        "assert not ui_modules, f'unexpected ui import: {ui_modules}'\n"
        "doc = Document(4, 4)\n"
        "ref = AssetReference('a1', 'a' * 64, AssetKind.SPRITE, 'Hero')\n"
        "refs = ReferenceSet(references=(ref,))\n"
        "payload = pio.serialize(doc, reference_set=refs)\n"
        "assert payload['version'] == pio.FORMAT_VERSION\n"
        "loaded_doc, loaded_refs = pio.deserialize_project(payload)\n"
        "assert loaded_refs == refs\n"
        "print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


# --------------------------------------------------------------------------- #
# T52: the "asset_edit_decisions" root key (REQ-P11-DATA-010, ruling P11-R13) #
# --------------------------------------------------------------------------- #

_DECISION_HASH_A = "a" * 64
_DECISION_HASH_B = "b" * 64


def _sample_decisions() -> AssetEditDecisions:
    return AssetEditDecisions(
        {
            "a1": (_DECISION_HASH_A, DECISION_PICK_UP),
            "a2": (_DECISION_HASH_B, DECISION_KEEP),
        }
    )


def test_format_version_is_unchanged_by_the_decisions_key():
    # ruling P11-R13: a lost ledger costs one prompt reappearing, which the
    # ruling holds is not a format break -- FORMAT_VERSION stays 6.
    assert pio.FORMAT_VERSION == 6


def test_serialize_with_decisions_still_stamps_version_six():
    payload = pio.serialize(Document(4, 4), decisions=_sample_decisions())
    assert payload["version"] == 6


def test_decisions_key_absent_when_none_supplied():
    payload = pio.serialize(Document(4, 4))
    assert "asset_edit_decisions" not in payload


def test_decisions_key_absent_when_empty_ledger_supplied():
    payload = pio.serialize(Document(4, 4), decisions=AssetEditDecisions())
    assert "asset_edit_decisions" not in payload


def test_decisions_key_present_exactly_when_non_empty_both_directions():
    empty_keys = set(
        pio.serialize(Document(4, 4), decisions=AssetEditDecisions()).keys()
    )
    populated_keys = set(
        pio.serialize(Document(4, 4), decisions=_sample_decisions()).keys()
    )
    assert "asset_edit_decisions" not in empty_keys
    assert "asset_edit_decisions" in populated_keys


def test_decisions_entry_shape_and_sort_order_matches_the_ledger():
    payload = pio.serialize(Document(4, 4), decisions=_sample_decisions())
    assert payload["asset_edit_decisions"] == [
        {
            "asset_id": "a1",
            "edit_token": _DECISION_HASH_A,
            "outcome": DECISION_PICK_UP,
        },
        {"asset_id": "a2", "edit_token": _DECISION_HASH_B, "outcome": DECISION_KEEP},
    ]


def test_saved_bytes_omit_decisions_when_absent(tmp_path):
    path = pio.save_project(Document(4, 4), tmp_path / "p")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "asset_edit_decisions" not in raw


def test_saved_bytes_include_decisions_when_populated(tmp_path):
    path = pio.save_project(
        Document(4, 4), tmp_path / "p", decisions=_sample_decisions()
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    expected = pio.serialize(Document(4, 4), decisions=_sample_decisions())[
        "asset_edit_decisions"
    ]
    assert raw["asset_edit_decisions"] == expected


def test_populated_decisions_round_trip_through_load_project_bundle(tmp_path):
    doc = Document(4, 4)
    decisions = _sample_decisions()
    path = pio.save_project(doc, tmp_path / "p", decisions=decisions)
    _loaded_doc, _loaded_refs, loaded_decisions = pio.load_project_bundle(path)
    assert loaded_decisions == decisions


def test_project_without_the_decisions_key_still_round_trips_empty(tmp_path):
    # Absence still asks (SC-P11-DATA-010-2): a project saved without a
    # decisions argument at all loads back with an empty ledger, no error.
    doc = Document(4, 4)
    path = pio.save_project(doc, tmp_path / "p")
    _loaded_doc, _loaded_refs, loaded_decisions = pio.load_project_bundle(path)
    assert loaded_decisions == AssetEditDecisions()


def test_decisions_keyword_only_on_serialize():
    with pytest.raises(TypeError):
        pio.serialize(Document(4, 4), None, _sample_decisions())  # type: ignore[misc]


def test_decisions_keyword_only_on_save_project(tmp_path):
    with pytest.raises(TypeError):
        pio.save_project(  # type: ignore[misc]
            Document(4, 4), tmp_path / "p", None, _sample_decisions()
        )


def test_parse_asset_edit_decisions_absent_reads_as_empty():
    payload = pio.serialize(Document(4, 4))
    assert "asset_edit_decisions" not in payload
    ledger = pio.parse_asset_edit_decisions(payload.get("asset_edit_decisions", []))
    assert ledger == AssetEditDecisions()


def test_parse_asset_edit_decisions_populated_reads_back_the_ledger():
    payload = pio.serialize(Document(4, 4), decisions=_sample_decisions())
    ledger = pio.parse_asset_edit_decisions(payload["asset_edit_decisions"])
    assert ledger == _sample_decisions()


def test_parse_asset_edit_decisions_not_a_list_raises():
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions({"a1": "not-a-list"})


def test_parse_asset_edit_decisions_entry_not_an_object_raises():
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions(["not-an-object"])


def test_parse_asset_edit_decisions_missing_asset_id_raises():
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions(
            [{"edit_token": _DECISION_HASH_A, "outcome": DECISION_KEEP}]
        )


def test_parse_asset_edit_decisions_malformed_edit_token_shape_raises():
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions(
            [{"asset_id": "a1", "edit_token": "not-a-hash", "outcome": DECISION_KEEP}]
        )


def test_parse_asset_edit_decisions_out_of_domain_outcome_raises():
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions(
            [
                {
                    "asset_id": "a1",
                    "edit_token": _DECISION_HASH_A,
                    "outcome": "discard",
                }
            ]
        )


def test_parse_asset_edit_decisions_empty_asset_id_raises():
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions(
            [
                {
                    "asset_id": "",
                    "edit_token": _DECISION_HASH_A,
                    "outcome": DECISION_KEEP,
                }
            ]
        )


def test_parse_asset_edit_decisions_non_string_asset_id_raises():
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions(
            [{"asset_id": 1, "edit_token": _DECISION_HASH_A, "outcome": DECISION_KEEP}]
        )


def test_parse_asset_edit_decisions_over_max_catalog_assets_raises():
    too_many = [
        {
            "asset_id": f"a{i}",
            "edit_token": format(i, "064x"),
            "outcome": DECISION_KEEP,
        }
        for i in range(MAX_CATALOG_ASSETS + 1)
    ]
    with pytest.raises(ProjectIOError):
        pio.parse_asset_edit_decisions(too_many)


def test_malformed_decisions_entry_raises_before_frames_is_even_read_atomic_order():
    payload = pio.serialize(Document(4, 4))
    payload["asset_edit_decisions"] = [{"asset_id": "a1"}]  # missing edit_token
    del payload["frames"]
    with pytest.raises(ProjectIOError, match="edit_token"):
        pio.deserialize(payload)


def test_load_project_bundle_atomic_on_malformed_decisions_file(tmp_path):
    doc = Document(4, 4)
    path = pio.save_project(doc, tmp_path / "p", decisions=_sample_decisions())
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["asset_edit_decisions"][0]["outcome"] = "discard"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ProjectIOError):
        pio.load_project_bundle(path)


def test_deserialize_project_two_tuple_signature_unchanged_by_decisions():
    # REQ-P11-DATA-010 must not widen the pre-existing two-tuple signature.
    payload = pio.serialize(Document(4, 4), decisions=_sample_decisions())
    result = pio.deserialize_project(payload)
    assert len(result) == 2


def test_load_project_with_asset_refs_two_tuple_signature_unchanged_by_decisions(
    tmp_path,
):
    path = pio.save_project(
        Document(4, 4), tmp_path / "p", decisions=_sample_decisions()
    )
    result = pio.load_project_with_asset_refs(path)
    assert len(result) == 2


def test_pre_v6_fixture_loads_with_an_empty_decisions_ledger_no_migration():
    payload = pio.serialize(Document(4, 4))
    payload["version"] = 5
    _doc, _refs, decisions = pio._deserialize_project_bundle(payload)
    assert decisions == AssetEditDecisions()
