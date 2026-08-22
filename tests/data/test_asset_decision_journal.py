"""Tests for pixelart_creator.data.asset_decision_journal (REQ-P11-DATA-010, ADR-0062, ruling P11-R13).

Covers the write-ahead journal's durability contract: an absent file loads as
an empty mapping and creates nothing on disk; ``write_record`` /
``load_journal`` round-trip via atomic temp+fsync+``os.replace``;
``drop_record`` is a no-op, not an error, on an absent record, twice in a
row; a malformed journal, an unsupported schema version, an out-of-domain
outcome and a non-admitted prefs key each raise
:class:`AssetDecisionJournalError`, which subclasses :class:`ValueError`
**directly** -- not :class:`~pixelart_creator.data.project_io.ProjectIOError`.

No Qt import (S11). Every temp path comes from ``tmp_path``.
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data.asset_decision_journal import (
    FORMAT_NAME,
    JOURNAL_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    AssetDecisionJournalError,
    drop_record,
    load_journal,
    write_record,
)
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_edit_decisions import (
    DECISION_KEEP,
    DECISION_PICK_UP,
    AssetEditDecisions,
)

_PROJECT_A = "/projects/a.pixproj"
_PROJECT_B = "/projects/b.pixproj"
_TOKEN_A = "token-a"


def _journal_path(tmp_path):
    return tmp_path / "asset-edit-decisions.json"


# --------------------------------------------------------------------------- #
# Module constants                                                            #
# --------------------------------------------------------------------------- #


class TestConstants:
    def test_error_subclasses_value_error_directly_not_project_io_error(self):
        assert issubclass(AssetDecisionJournalError, ValueError)
        assert not issubclass(AssetDecisionJournalError, ProjectIOError)

    def test_format_name_is_pixdecisions(self):
        assert FORMAT_NAME == "pixdecisions"

    def test_schema_version_is_one(self):
        assert JOURNAL_SCHEMA_VERSION == 1

    def test_supported_schema_versions_is_a_one_entry_tuple(self):
        assert SUPPORTED_SCHEMA_VERSIONS == (JOURNAL_SCHEMA_VERSION,)


# --------------------------------------------------------------------------- #
# load_journal -- absent file                                                 #
# --------------------------------------------------------------------------- #


class TestLoadAbsentFile:
    def test_absent_file_loads_as_empty_mapping(self, tmp_path):
        path = _journal_path(tmp_path)
        assert load_journal(path) == {}

    def test_absent_file_creates_nothing_on_disk(self, tmp_path):
        path = _journal_path(tmp_path)
        load_journal(path)
        # Assert the directory listing itself -- "no exception" does not
        # prove "no file was written".
        assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# write_record / load_journal round trip                                     #
# --------------------------------------------------------------------------- #


class TestWriteAndLoadRoundTrip:
    def test_written_record_round_trips(self, tmp_path):
        path = _journal_path(tmp_path)
        decisions = AssetEditDecisions().with_decision("a1", _TOKEN_A, DECISION_PICK_UP)
        write_record(path, _PROJECT_A, {"asset_library_edit": "keep"}, decisions)
        loaded = load_journal(path)
        assert loaded == {
            _PROJECT_A: {
                "prefs": {"asset_library_edit": "keep"},
                "edits": [
                    {
                        "asset_id": "a1",
                        "edit_token": _TOKEN_A,
                        "outcome": DECISION_PICK_UP,
                    }
                ],
            }
        }

    def test_write_creates_exactly_the_journal_file_no_leftover_tmp(self, tmp_path):
        path = _journal_path(tmp_path)
        write_record(path, _PROJECT_A, {}, AssetEditDecisions())
        assert [p.name for p in tmp_path.iterdir()] == [path.name]

    def test_second_project_record_is_added_not_overwritten(self, tmp_path):
        path = _journal_path(tmp_path)
        write_record(path, _PROJECT_A, {}, AssetEditDecisions())
        write_record(path, _PROJECT_B, {}, AssetEditDecisions())
        loaded = load_journal(path)
        assert set(loaded.keys()) == {_PROJECT_A, _PROJECT_B}

    def test_rewriting_the_same_project_replaces_its_record(self, tmp_path):
        path = _journal_path(tmp_path)
        write_record(
            path,
            _PROJECT_A,
            {},
            AssetEditDecisions().with_decision("a1", _TOKEN_A, DECISION_KEEP),
        )
        write_record(
            path,
            _PROJECT_A,
            {},
            AssetEditDecisions().with_decision("a1", _TOKEN_A, DECISION_PICK_UP),
        )
        loaded = load_journal(path)
        assert loaded[_PROJECT_A]["edits"] == [
            {"asset_id": "a1", "edit_token": _TOKEN_A, "outcome": DECISION_PICK_UP}
        ]

    def test_written_bytes_carry_the_format_and_schema_markers(self, tmp_path):
        path = _journal_path(tmp_path)
        write_record(path, _PROJECT_A, {}, AssetEditDecisions())
        payload = json.loads(path.read_bytes().decode("utf-8"))
        assert payload["format"] == FORMAT_NAME
        assert payload["schema_version"] == JOURNAL_SCHEMA_VERSION

    def test_non_admitted_prefs_key_is_refused_on_write(self, tmp_path):
        path = _journal_path(tmp_path)
        with pytest.raises(AssetDecisionJournalError):
            write_record(
                path, _PROJECT_A, {"some_other_key": "x"}, AssetEditDecisions()
            )

    def test_non_string_prefs_value_is_refused_on_write(self, tmp_path):
        path = _journal_path(tmp_path)
        with pytest.raises(AssetDecisionJournalError):
            write_record(
                path, _PROJECT_A, {"asset_library_edit": 1}, AssetEditDecisions()
            )

    def test_empty_prefs_value_is_refused_on_write(self, tmp_path):
        path = _journal_path(tmp_path)
        with pytest.raises(AssetDecisionJournalError):
            write_record(
                path, _PROJECT_A, {"asset_library_edit": ""}, AssetEditDecisions()
            )

    def test_empty_project_path_is_refused(self, tmp_path):
        path = _journal_path(tmp_path)
        with pytest.raises(AssetDecisionJournalError):
            write_record(path, "", {}, AssetEditDecisions())

    def test_non_ledger_decisions_is_refused(self, tmp_path):
        path = _journal_path(tmp_path)
        with pytest.raises(AssetDecisionJournalError):
            write_record(path, _PROJECT_A, {}, {"a1": (_TOKEN_A, DECISION_KEEP)})

    def test_decisions_over_max_catalog_assets_is_refused_on_write(self, tmp_path):
        from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS

        path = _journal_path(tmp_path)
        rows = {
            f"a{i}": (_TOKEN_A, DECISION_KEEP) for i in range(MAX_CATALOG_ASSETS + 1)
        }
        decisions = AssetEditDecisions(rows)
        with pytest.raises(AssetDecisionJournalError):
            write_record(path, _PROJECT_A, {}, decisions)

    def test_journal_over_max_catalog_assets_project_records_is_refused_on_write(
        self, tmp_path
    ):
        from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS

        path = _journal_path(tmp_path)
        # Seed a journal already holding MAX_CATALOG_ASSETS project records
        # directly on disk (writing them one at a time via write_record would
        # be prohibitively slow for this bound).
        seeded_projects = {
            f"/p{i}.pixproj": {"prefs": {}, "edits": []}
            for i in range(MAX_CATALOG_ASSETS)
        }
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": seeded_projects,
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            write_record(path, "/one-more.pixproj", {}, AssetEditDecisions())


# --------------------------------------------------------------------------- #
# drop_record -- idempotent no-op                                             #
# --------------------------------------------------------------------------- #


class TestDropRecord:
    def test_drop_on_absent_file_is_a_no_op_not_an_error(self, tmp_path):
        path = _journal_path(tmp_path)
        drop_record(path, _PROJECT_A)  # must not raise
        assert list(tmp_path.iterdir()) == []

    def test_drop_on_absent_file_is_idempotent_twice_in_a_row(self, tmp_path):
        path = _journal_path(tmp_path)
        drop_record(path, _PROJECT_A)
        drop_record(path, _PROJECT_A)  # second call: still a no-op
        assert list(tmp_path.iterdir()) == []

    def test_drop_removes_an_existing_record(self, tmp_path):
        path = _journal_path(tmp_path)
        write_record(path, _PROJECT_A, {}, AssetEditDecisions())
        drop_record(path, _PROJECT_A)
        assert load_journal(path) == {}

    def test_drop_of_an_already_dropped_record_is_idempotent_twice_in_a_row(
        self, tmp_path
    ):
        path = _journal_path(tmp_path)
        write_record(path, _PROJECT_A, {}, AssetEditDecisions())
        drop_record(path, _PROJECT_A)
        drop_record(path, _PROJECT_A)  # second call on the now-absent record
        assert load_journal(path) == {}

    def test_drop_leaves_other_records_intact(self, tmp_path):
        path = _journal_path(tmp_path)
        write_record(path, _PROJECT_A, {}, AssetEditDecisions())
        write_record(path, _PROJECT_B, {}, AssetEditDecisions())
        drop_record(path, _PROJECT_A)
        assert set(load_journal(path).keys()) == {_PROJECT_B}

    def test_empty_project_path_is_refused(self, tmp_path):
        path = _journal_path(tmp_path)
        with pytest.raises(AssetDecisionJournalError):
            drop_record(path, "")


# --------------------------------------------------------------------------- #
# Malformed journal contents                                                  #
# --------------------------------------------------------------------------- #


class TestMalformedJournal:
    def test_not_valid_json_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(b"{not json")
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_not_a_json_object_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(b"[]")
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_wrong_format_marker_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {"format": "not-pixdecisions", "schema_version": 1, "projects": {}}
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_unsupported_schema_version_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {"format": FORMAT_NAME, "schema_version": 999, "projects": {}}
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_projects_not_an_object_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {"format": FORMAT_NAME, "schema_version": 1, "projects": []}
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_project_record_not_an_object_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {_PROJECT_A: "not-a-record"},
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_out_of_domain_outcome_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {
                        _PROJECT_A: {
                            "prefs": {},
                            "edits": [
                                {
                                    "asset_id": "a1",
                                    "edit_token": _TOKEN_A,
                                    "outcome": "discard",
                                }
                            ],
                        }
                    },
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_empty_asset_id_in_an_edit_entry_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {
                        _PROJECT_A: {
                            "prefs": {},
                            "edits": [
                                {
                                    "asset_id": "",
                                    "edit_token": _TOKEN_A,
                                    "outcome": DECISION_KEEP,
                                }
                            ],
                        }
                    },
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_non_string_edit_token_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {
                        _PROJECT_A: {
                            "prefs": {},
                            "edits": [
                                {
                                    "asset_id": "a1",
                                    "edit_token": 12345,
                                    "outcome": DECISION_KEEP,
                                }
                            ],
                        }
                    },
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_record_prefs_not_an_object_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {_PROJECT_A: {"prefs": [], "edits": []}},
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_record_edit_entry_not_an_object_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {_PROJECT_A: {"prefs": {}, "edits": ["not-an-object"]}},
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_record_admitted_prefs_value_wrong_type_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {
                        _PROJECT_A: {
                            "prefs": {"asset_library_edit": 1},
                            "edits": [],
                        }
                    },
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_record_edits_not_a_list_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {_PROJECT_A: {"prefs": {}, "edits": "not-a-list"}},
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_record_edits_over_max_catalog_assets_raises(self, tmp_path):
        from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS

        path = _journal_path(tmp_path)
        too_many = [
            {"asset_id": f"a{i}", "edit_token": _TOKEN_A, "outcome": DECISION_KEEP}
            for i in range(MAX_CATALOG_ASSETS + 1)
        ]
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {_PROJECT_A: {"prefs": {}, "edits": too_many}},
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_projects_over_max_catalog_assets_raises(self, tmp_path):
        from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS

        path = _journal_path(tmp_path)
        too_many_projects = {
            f"/p{i}.pixproj": {"prefs": {}, "edits": []}
            for i in range(MAX_CATALOG_ASSETS + 1)
        }
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": too_many_projects,
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_empty_project_key_raises(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {"": {"prefs": {}, "edits": []}},
                }
            ).encode("utf-8")
        )
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_unreadable_file_raises_journal_error_not_os_error(self, tmp_path):
        # target exists but is a directory, not a file: read_text() raises an
        # OSError subclass, which must surface as AssetDecisionJournalError.
        path = tmp_path / "asset-edit-decisions.json"
        path.mkdir()
        with pytest.raises(AssetDecisionJournalError):
            load_journal(path)

    def test_write_to_an_unwritable_location_raises_journal_error(self, tmp_path):
        # The parent directory does not exist: the temp-file open() raises an
        # OSError subclass, which must surface as AssetDecisionJournalError.
        path = tmp_path / "missing_dir" / "asset-edit-decisions.json"
        with pytest.raises(AssetDecisionJournalError):
            write_record(path, _PROJECT_A, {}, AssetEditDecisions())

    def test_non_admitted_prefs_key_is_dropped_not_raised_on_read(self, tmp_path):
        path = _journal_path(tmp_path)
        path.write_bytes(
            json.dumps(
                {
                    "format": FORMAT_NAME,
                    "schema_version": 1,
                    "projects": {
                        _PROJECT_A: {
                            "prefs": {"unknown_key": "x"},
                            "edits": [],
                        }
                    },
                }
            ).encode("utf-8")
        )
        loaded = load_journal(path)
        assert loaded[_PROJECT_A]["prefs"] == {}
