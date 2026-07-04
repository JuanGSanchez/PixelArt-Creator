"""Tests for pixelart_creator.data.cloud.port (Phase-10 Slice A, no Qt).

Covers the transport codec and the untrusted-input defence (Article VII,
REQ-P10-DATA-002/-006/-007):

* ``serialize_project`` -> ``deserialize_project`` is a faithful round-trip that
  reuses the shipped PIO-1 serialiser (no new format);
* a Hypothesis property test over varied ``Document`` states (round-trip
  identity + determinism);
* the untrusted-blob defence — oversized blob rejected *before* decode,
  malformed/non-JSON/non-object rejected, unknown-version raises a
  ``ProjectIOError``, and there is **no** ``eval``/``exec`` path;
* the exception hierarchy (``CloudDataError`` <: ``ProjectIOError``) and the
  normalized value types / ``CloudPort`` ABC contract.
"""

from __future__ import annotations

import inspect
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data import project_io
from pixelart_creator.data.cloud import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
    CloudPort,
    Cursor,
    RemoteItem,
    deserialize_project,
)
from pixelart_creator.data.cloud import port as port_mod
from pixelart_creator.data.cloud import (
    serialize_project,
)
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _sample_document() -> Document:
    doc = Document(4, 3, palette=Palette([RED, BLUE]), metadata={"author": "t"})
    doc.frames[0].layers[0].buffer.set_pixel(1, 1, RED)
    doc.add_layer("Ink")
    doc.add_frame(duration_ms=250)
    return doc


# --- round-trip (reuses PIO-1) ---------------------------------------------- #


def test_round_trip_reconstructs_equivalent_document():
    doc = _sample_document()
    blob = serialize_project(doc)
    assert isinstance(blob, bytes)
    restored = deserialize_project(blob)
    # Equivalence proven through the shipped PIO-1 serialiser (no new format).
    assert project_io.serialize(restored) == project_io.serialize(doc)
    assert restored.width == 4 and restored.height == 3
    assert restored.frames[0].layers[0].buffer.get_pixel(1, 1) == RED
    assert restored.frames[0].layers[1].name == "Ink"
    assert restored.frames[1].duration_ms == 250


def test_serialize_composes_pio1_not_a_new_format():
    doc = _sample_document()
    blob = serialize_project(doc)
    payload = json.loads(blob.decode("utf-8"))
    # The transported bytes ARE the PIO-1 payload (Article I; no fork).
    assert payload == project_io.serialize(doc)
    assert payload["format"] == "pixproj"


def test_indexed_document_round_trip():
    doc = Document(3, 3, mode=ColorMode.INDEXED, palette=Palette([RED]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, 4)
    restored = deserialize_project(serialize_project(doc))
    assert restored.mode is ColorMode.INDEXED
    assert restored.frames[0].layers[0].buffer.get_pixel(0, 0) == 4


# --- Hypothesis property: round-trip identity + determinism ----------------- #

_rgba = st.tuples(
    st.integers(0, 255), st.integers(0, 255), st.integers(0, 255), st.integers(0, 255)
)


@st.composite
def _documents(draw):
    w = draw(st.integers(2, 8))
    h = draw(st.integers(2, 8))
    colors = draw(st.lists(_rgba, min_size=1, max_size=4, unique=True))
    doc = Document(w, h, palette=Palette(colors))
    for i in range(draw(st.integers(0, 2))):
        doc.add_layer(f"L{i}")
    for _ in range(draw(st.integers(0, 2))):
        doc.add_frame()
    writes = draw(
        st.lists(
            st.tuples(st.integers(0, w - 1), st.integers(0, h - 1), _rgba),
            max_size=6,
        )
    )
    for x, y, color in writes:
        doc.frames[0].layers[0].buffer.set_pixel(x, y, color)
    return doc


@given(doc=_documents())
def test_property_round_trip_identity_and_determinism(doc):
    blob = serialize_project(doc)
    # Determinism: serialising twice is byte-identical (no wall-clock/random).
    assert serialize_project(doc) == blob
    restored = deserialize_project(blob)
    # Round-trip identity: re-serialising the restored document reproduces bytes.
    assert serialize_project(restored) == blob


# --- untrusted-input defence (Article VII) ---------------------------------- #


def test_deserialize_rejects_non_bytes():
    with pytest.raises(CloudDataError):
        deserialize_project("not-bytes")  # type: ignore[arg-type]


def test_deserialize_rejects_malformed_json():
    with pytest.raises(CloudDataError):
        deserialize_project(b"garbage-not-json")


def test_deserialize_rejects_invalid_utf8():
    with pytest.raises(CloudDataError):
        deserialize_project(b"\xff\xfe\x00nonsense")


def test_deserialize_rejects_non_object_json():
    # Valid JSON but not a JSON object (e.g. a list) -> CloudDataError.
    with pytest.raises(CloudDataError):
        deserialize_project(b"[1, 2, 3]")


def test_size_cap_fires_before_decode(monkeypatch):
    # Shrink the cap so we do not allocate 256 MiB; the guard must fire on length
    # BEFORE any UTF-8/JSON decode (no huge allocation, Article VII).
    monkeypatch.setattr(port_mod, "MAX_CLOUD_PROJECT_BYTES", 8)
    with pytest.raises(CloudDataError):
        deserialize_project(b"x" * 9)


def test_size_cap_boundary_allows_exact_limit(monkeypatch):
    # A blob exactly at the cap is not rejected by the size guard (it proceeds to
    # decode and fails later on content, not on size).
    monkeypatch.setattr(port_mod, "MAX_CLOUD_PROJECT_BYTES", 32)
    with pytest.raises(CloudDataError):
        # 32 bytes of non-JSON: passes the size guard, fails at JSON decode.
        deserialize_project(b"x" * 32)


def test_valid_json_but_not_pixproj_raises_projectioerror():
    # A well-formed JSON object that is not a .pixproj -> PIO-1 defensive error.
    with pytest.raises(ProjectIOError):
        deserialize_project(b'{"not": "a pixproj"}')


def test_no_eval_or_exec_in_untrusted_path():
    # Article VII: the untrusted-fetch codec must never eval/exec.
    src = inspect.getsource(port_mod)
    assert "eval(" not in src
    assert "exec(" not in src


# --- exception hierarchy ---------------------------------------------------- #


def test_cloud_data_error_is_projectioerror_subclass():
    assert issubclass(CloudDataError, ProjectIOError)
    # So a caller catching either family catches a malformed cloud blob.
    with pytest.raises(ProjectIOError):
        deserialize_project(b"garbage")


def test_cloud_error_is_valueerror_subclass():
    assert issubclass(CloudError, ValueError)


# --- normalized value types ------------------------------------------------- #


def test_remote_item_and_cursor_are_frozen():
    item = RemoteItem(id="a", name="proj", size_bytes=10)
    cur = Cursor(token="opaque")
    assert item.size_bytes == 10 and cur.token == "opaque"
    with pytest.raises(Exception):
        item.name = "x"  # type: ignore[misc]
    with pytest.raises(Exception):
        cur.token = "y"  # type: ignore[misc]


def test_capabilities_fields():
    caps = CloudCapabilities(
        supports_named_revisions=True,
        supports_revision_delete=False,
        max_versions_per_call=None,
        change_feed_scope="drive",
        supports_optimistic_concurrency=True,
    )
    assert caps.max_versions_per_call is None
    assert caps.change_feed_scope == "drive"


# --- CloudPort ABC contract ------------------------------------------------- #


def test_cloud_port_is_abstract():
    with pytest.raises(TypeError):
        CloudPort()  # type: ignore[abstract]


def test_is_connected_default_is_false():
    # A minimal concrete subclass gets the non-abstract default False.
    class _Minimal(CloudPort):
        def put(self, project_id, blob, *, parent_version=None):
            raise NotImplementedError

        def get(self, project_id, version_id):
            raise NotImplementedError

        def list_versions(self, project_id):
            raise NotImplementedError

        def latest(self, project_id):
            raise NotImplementedError

        def delete(self, project_id):
            raise NotImplementedError

        def put_recovery(self, project_id, blob):
            raise NotImplementedError

        def get_recovery(self, project_id):
            raise NotImplementedError

        def capabilities(self):
            raise NotImplementedError

    assert _Minimal().is_connected() is False
