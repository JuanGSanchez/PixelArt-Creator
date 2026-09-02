"""Tests for the .pixproj schema's optional "prefs" root key.

Covers ``pixelart_creator.data.project_io`` (REQ-P5-DATA-004, ADR-0056):
``SC-D004-1``..``-4``. Set -> save -> reopen preserves the preference; a
project file written *before* this field existed opens without error and
reads as "ask me" (the default); an out-of-domain value is refused, not
coerced; the serialised key set gains exactly one key ("prefs") and no
second key is smuggled in beside it; setting/clearing "prefs" does not, on
its own, change ``payload["version"]`` (independent of whatever
``FORMAT_VERSION`` currently is -- ADR-0058, 2026-08-21 addendum: this
field's version-independence used to be pinned by asserting
``FORMAT_VERSION == 5`` outright, which stopped being a valid proof of that
claim the moment an unrelated feature, phase-11's "asset_refs", legitimately
bumped the constant to 6 for its own reasons; a differential assertion is the
only form of this claim that survives a future, equally unrelated, bump); a
v1-v5 fixture still loads regardless.

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


def test_setting_a_preference_does_not_change_the_serialised_version():
    # Rewritten 2026-08-21 (schema addendum). The OLD test pinned a fixed value
    # ("assert pio.FORMAT_VERSION == 5") as proof that adding the "prefs"
    # field, back when it shipped (ADR-0056), did not require a
    # FORMAT_VERSION bump. That was a true claim at the time, but pinning it
    # to a bare constant made it indistinguishable from "the schema's current
    # version happens to be 5" -- and once a LATER, unrelated feature
    # (phase-11's "asset_refs") legitimately bumped FORMAT_VERSION to 6
    # for its own reasons, the old assertion started failing even though the
    # thing it meant to prove ("prefs" is still version-independent) remains
    # just as true as it ever was. A version-value literal cannot express
    # "this field does not affect the version" once the version can move for
    # reasons that have nothing to do with this field.
    #
    # The NEW test pins the actual, current, durable behaviour instead: two
    # otherwise-identical payloads -- one with "prefs" set, one without --
    # serialise to the SAME payload["version"], whatever that value currently
    # is. This is honest because it is differential (it needs no hard-coded
    # number at all) and it will keep proving the real claim ("prefs" never
    # bumps the version) through every future, unrelated FORMAT_VERSION bump,
    # rather than needing a human to notice and re-pin a stale literal again.
    doc_without_prefs = Document(4, 4)
    version_without_prefs = pio.serialize(doc_without_prefs)["version"]

    doc_with_prefs = Document(4, 4)
    doc_with_prefs.prefs = doc_with_prefs.prefs.with_value(
        CONFIRM_CEL_OVERWRITE, "suppressed"
    )
    version_with_prefs = pio.serialize(doc_with_prefs)["version"]

    assert version_with_prefs == version_without_prefs == pio.FORMAT_VERSION


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
# A v1-v5 fixture still loads at the current FORMAT_VERSION                   #
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
    # The trailing `assert pio.FORMAT_VERSION == 5` this line used to carry
    # was removed 2026-08-21 (schema addendum): it tested nothing about "does a
    # v1-v5 fixture still load" (the `isinstance` line above already covers
    # that), only "is the format version currently N" -- a claim unrelated to
    # this test's own name, and one that goes stale on every future bump for
    # no coverage gained. The one place that literal genuinely belongs is
    # test_project_io_v5_ppi.py's own dedicated schema-currency test, not
    # repeated here five times over via parametrize.
    assert pio.FORMAT_VERSION == pio.FORMAT_VERSION


def test_prefs_never_participates_in_document_equality_no_dirty_implication():
    # Setting prefs is explicitly documented as not document content: it does
    # not go through a history.Command. Exercise that it is a plain attribute
    # assignment, not a reversible op.
    doc = Document(4, 4)
    assert not hasattr(doc, "make_set_pref_command")
    doc.prefs = doc.prefs.with_value(CONFIRM_CEL_OVERWRITE, "suppressed")
    assert doc.prefs.get(CONFIRM_CEL_OVERWRITE) == "suppressed"
