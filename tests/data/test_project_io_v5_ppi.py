"""Tests for the .pixproj schema-v5 Document.ppi persistence + back-compat.

Covers pixelart_creator.data.project_io (ADR-0025 §1, REQ-P9-LOGIC-007): the v5
round-trip persists Document.ppi identically; v1–v4 files (no ``ppi`` key) load
back with DEFAULT_DOCUMENT_PPI; and a present-but-malformed ppi is rejected
defensively (ProjectIOError) with no eval/exec. The version pin is compared to
the FORMAT_VERSION constant, never a literal.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic import constants
from pixelart_creator.logic.document import Document


def test_format_version_is_six_and_supported():
    # v6 (ADR-0058, phase-11-asset-ingress T12: the optional "asset_refs" root
    # array). Updated from the stale "is_five" pin 2026-08-21 (T19 addendum) --
    # this file's own ppi-specific behaviour (below) is unaffected by that
    # bump; only this schema-currency check needed the literal moved forward.
    assert pio.FORMAT_VERSION == 6
    assert set(pio._SUPPORTED_VERSIONS) == {1, 2, 3, 4, 5, 6}


def test_v5_round_trip_preserves_ppi(tmp_path):
    doc = Document(4, 4, ppi=300.0)
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "hi"))
    assert loaded.ppi == 300.0


def test_serialize_writes_ppi_and_current_version():
    payload = pio.serialize(Document(2, 2, ppi=96.0))
    assert payload["version"] == pio.FORMAT_VERSION
    assert payload["ppi"] == 96.0


def test_default_ppi_round_trips(tmp_path):
    doc = Document(3, 3)
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "def"))
    assert loaded.ppi == constants.DEFAULT_DOCUMENT_PPI


def test_v1_to_v4_back_compat_loads_default_ppi():
    # A pre-v5 file has no "ppi" key; every earlier version loads with the default
    # (v2/v3/v4 share the richer frame parser; the ppi field is simply absent).
    for version in (2, 3, 4):
        payload = pio.serialize(Document(4, 4, ppi=222.0))
        payload["version"] = version
        payload.pop("ppi", None)
        loaded = pio.deserialize(payload)
        assert loaded.ppi == constants.DEFAULT_DOCUMENT_PPI


def test_present_ppi_is_honoured_on_deserialize():
    payload = pio.serialize(Document(2, 2))
    payload["ppi"] = 123.5
    assert pio.deserialize(payload).ppi == 123.5


@pytest.mark.parametrize("bad", [0, -1, 0.0, -72.0, "x", True, [72]])
def test_malformed_ppi_is_rejected(bad):
    payload = pio.serialize(Document(2, 2))
    payload["ppi"] = bad
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_missing_ppi_on_v5_defaults(tmp_path):
    # Defensive: even a v5-tagged file with the key dropped falls back, never crashes.
    payload = pio.serialize(Document(2, 2))
    payload.pop("ppi", None)
    assert pio.deserialize(payload).ppi == constants.DEFAULT_DOCUMENT_PPI
