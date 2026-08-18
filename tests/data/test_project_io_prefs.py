"""Tests for the .pixproj schema's optional "prefs" root key (T15).

Covers ``pixelart_creator.data.project_io`` (REQ-P5-DATA-004, ADR-0056):
``SC-D004-1``..``-4``. Set -> save -> reopen preserves the preference; a
project file written *before* this field existed opens without error and
reads as "ask me" (the default); an out-of-domain value is refused, not
coerced; the serialised key set gains exactly one key ("prefs") and no
second key is smuggled in beside it; ``FORMAT_VERSION`` stays 5 so a v1-v5
fixture still loads.

No Qt import (S11).
"""

from __future__ import annotations

import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.project_prefs import (
    CONFIRM_CEL_OVERWRITE,
    ProjectPrefs,
)


def test_format_version_stays_five():
    # Deliberate (ADR-0056): the reader tolerates the unknown/absent "prefs"
    # key, so this additive field does not bump FORMAT_VERSION.
    assert pio.FORMAT_VERSION == 5


# --------------------------------------------------------------------------- #
# SC-D004-1 — set -> save -> reopen preserves the preference                  #
# --------------------------------------------------------------------------- #


def test_set_save_reopen_preserves_the_preference(tmp_path):
    doc = Document(4, 4)
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")

    loaded = pio.load_project(pio.save_project(doc, tmp_path / "p"))
    assert loaded.prefs.get(CONFIRM_CEL_OVERWRITE) == "suppressed"


def test_default_ask_value_round_trips_but_serialises_as_absent(tmp_path):
    # The default is never explicitly set, so it stays absent on disk
    # (to_mapping() only ever carries explicitly-set values).
    doc = Document(4, 4)
    payload = pio.serialize(doc)
    assert "prefs" not in payload

    loaded = pio.load_project(pio.save_project(doc, tmp_path / "p"))
    assert loaded.prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"


# --------------------------------------------------------------------------- #
# SC-D004-2 — a pre-existing project file opens without error, reads default  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_project_written_before_the_field_existed_opens_as_ask_me(version):
    payload = pio.serialize(Document(4, 4))
    payload["version"] = version
    payload.pop("prefs", None)
    loaded = pio.deserialize(payload)
    assert loaded.prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"


def test_v5_file_missing_prefs_key_defaults_to_ask():
    payload = pio.serialize(Document(4, 4))
    payload.pop("prefs", None)
    assert pio.deserialize(payload).prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"


# --------------------------------------------------------------------------- #
# SC-D004-3 — an out-of-domain value is refused, not coerced                  #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad_value", ["maybe", "", "ASK", "suppressed ", 1])
def test_out_of_domain_value_is_refused_not_coerced(bad_value):
    doc = Document(4, 4)
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    payload = pio.serialize(doc)
    payload["prefs"]["confirm_cel_overwrite"] = bad_value
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_prefs_value_must_be_a_string():
    payload = pio.serialize(Document(4, 4))
    payload["prefs"] = {"confirm_cel_overwrite": True}
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_prefs_root_key_must_be_an_object():
    payload = pio.serialize(Document(4, 4))
    payload["prefs"] = ["not", "a", "dict"]
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_prefs_key_name_must_be_a_string():
    # A JSON object always has string keys, but the parser guards it anyway;
    # exercise it directly against the internal parser.
    with pytest.raises(ProjectIOError):
        pio._parse_prefs({1: "ask"})


def test_unknown_preference_key_is_ignored_forward_tolerant():
    payload = pio.serialize(Document(4, 4))
    payload["prefs"] = {"a_future_slices_preference": "whatever"}
    # Does not raise -- an unrecognised key from a newer build is dropped.
    loaded = pio.deserialize(payload)
    assert loaded.prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"
    assert loaded.prefs.to_mapping() == {}


# --------------------------------------------------------------------------- #
# SC-D004-4 — the serialised key set gains exactly one key                    #
# --------------------------------------------------------------------------- #


def test_serialised_key_set_gains_exactly_one_key_when_prefs_set():
    doc_without = Document(4, 4)
    keys_without = set(pio.serialize(doc_without).keys())

    doc_with = Document(4, 4)
    doc_with.prefs = doc_with.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    keys_with = set(pio.serialize(doc_with).keys())

    added = keys_with - keys_without
    assert added == {"prefs"}
    assert keys_without - keys_with == set()  # nothing removed either


def test_no_second_key_is_smuggled_in_beside_prefs():
    doc = Document(4, 4)
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    payload = pio.serialize(doc)
    assert set(payload["prefs"].keys()) == {"confirm_cel_overwrite"}


# --------------------------------------------------------------------------- #
# A v1-v5 fixture still loads at FORMAT_VERSION 5                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_v1_to_v5_fixture_still_loads_at_current_format_version(version):
    payload = pio.serialize(Document(4, 4))
    payload["version"] = version
    if version < 5:
        payload.pop("prefs", None)
        payload.pop("ppi", None)
    loaded = pio.deserialize(payload)
    assert isinstance(loaded.prefs, ProjectPrefs)
    assert pio.FORMAT_VERSION == 5


def test_prefs_never_participates_in_document_equality_no_dirty_implication():
    # Setting prefs is explicitly documented as not document content: it does
    # not go through a history.Command. Exercise that it is a plain attribute
    # assignment, not a reversible op.
    doc = Document(4, 4)
    assert not hasattr(doc, "make_set_pref_command")
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    assert doc.prefs.get(CONFIRM_CEL_OVERWRITE) == "suppressed"
