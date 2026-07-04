"""Unit tests for the injectable HTTP seam (``data/cloud/providers/_http.py``).

Pure, network-free coverage (no Qt) of the seam AGT-04 uses to mock the whole
``CloudPort`` contract: :class:`HttpResponse` normalization, the ``with_query`` query
builder, the Article VII defensive body helpers (:func:`read_body` size cap /
:func:`decode_json` JSON-only decode), :class:`HttpError`, and the
:func:`token_transport_from_http` bridge onto the auth module's ``TokenTransport``.
The real :class:`UrllibHttpClient.request` is ``pragma: no cover`` (network-gated,
``cloud_live``); only its constructor is exercised here.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from pixelart_creator.data.cloud.port import CloudDataError, CloudError
from pixelart_creator.data.cloud.providers import _http as http_mod
from pixelart_creator.data.cloud.providers._http import (
    HttpError,
    HttpResponse,
    UrllibHttpClient,
    decode_json,
    read_body,
    token_transport_from_http,
    with_query,
)

# --- HttpResponse.ok -------------------------------------------------------- #


@pytest.mark.parametrize(
    "status,ok",
    [(200, True), (201, True), (299, True), (300, False), (199, False), (404, False)],
)
def test_http_response_ok(status, ok):
    assert HttpResponse(status=status).ok is ok


def test_http_response_defaults():
    resp = HttpResponse(status=204)
    assert resp.body == b""
    assert resp.headers == {}


# --- HttpError -------------------------------------------------------------- #


def test_http_error_records_status_and_is_cloud_error():
    err = HttpError("boom", status=503)
    assert err.status == 503
    assert isinstance(err, CloudError)


def test_http_error_status_defaults_none():
    assert HttpError("no status").status is None


# --- with_query ------------------------------------------------------------- #


def test_with_query_none_and_empty_unchanged():
    assert with_query("https://x/y", None) == "https://x/y"
    assert with_query("https://x/y", {}) == "https://x/y"


def test_with_query_appends_with_question_mark():
    out = with_query("https://x/y", {"a": "1", "b": "2"})
    parsed = urlparse(out)
    assert parsed.path == "/y"
    assert parse_qs(parsed.query) == {"a": ["1"], "b": ["2"]}


def test_with_query_uses_ampersand_when_query_present():
    out = with_query("https://x/y?z=0", {"a": "1"})
    assert out.startswith("https://x/y?z=0&")
    assert parse_qs(urlparse(out).query) == {"z": ["0"], "a": ["1"]}


# --- read_body (Article VII size cap) --------------------------------------- #


class _FakeStream:
    """A minimal read()-able body stream (like an ``http.client`` response)."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self, n: int) -> bytes:
        return self._data[:n]


def test_read_body_stream_within_cap():
    assert read_body(_FakeStream(b"hello"), cap=1024) == b"hello"


def test_read_body_bytes_passthrough():
    assert read_body(b"raw-bytes", cap=1024) == b"raw-bytes"


def test_read_body_over_cap_raises():
    with pytest.raises(CloudDataError):
        read_body(_FakeStream(b"0123456789"), cap=4)


def test_read_body_exactly_at_cap_ok():
    assert read_body(_FakeStream(b"1234"), cap=4) == b"1234"


# --- decode_json (Article VII JSON-only decode) ----------------------------- #


def test_decode_json_valid_object():
    resp = HttpResponse(status=200, body=b'{"a": 1, "b": "x"}')
    assert decode_json(resp) == {"a": 1, "b": "x"}


def test_decode_json_rejects_non_object():
    with pytest.raises(CloudDataError):
        decode_json(HttpResponse(status=200, body=b"[1, 2, 3]"))


def test_decode_json_rejects_invalid_json():
    with pytest.raises(CloudDataError):
        decode_json(HttpResponse(status=200, body=b"{not json"))


def test_decode_json_rejects_invalid_utf8():
    with pytest.raises(CloudDataError):
        decode_json(HttpResponse(status=200, body=b"\xff\xfe\x00"))


def test_decode_json_rejects_oversized_body(monkeypatch):
    monkeypatch.setattr(http_mod, "MAX_CLOUD_PROJECT_BYTES", 4)
    with pytest.raises(CloudDataError):
        decode_json(HttpResponse(status=200, body=b'{"aaaa": "bbbb"}'))


# --- token_transport_from_http --------------------------------------------- #


class _RecordingClient:
    def __init__(self, response: HttpResponse) -> None:
        self._response = response
        self.last = None

    def request(self, method, url, *, headers=None, params=None, body=None):
        self.last = {
            "method": method,
            "url": url,
            "headers": dict(headers or {}),
            "body": body,
        }
        return self._response


def test_token_transport_posts_form_and_decodes_json():
    client = _RecordingClient(
        HttpResponse(
            status=200, body=json.dumps({"access_token": "abc"}).encode("utf-8")
        )
    )
    transport = token_transport_from_http(client)
    result = transport("https://token", {"grant_type": "refresh_token", "x": "y"})
    assert result == {"access_token": "abc"}
    assert client.last["method"] == "POST"
    assert client.last["url"] == "https://token"
    assert client.last["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    # The form is urlencoded into the body.
    assert parse_qs(client.last["body"].decode("utf-8")) == {
        "grant_type": ["refresh_token"],
        "x": ["y"],
    }


def test_token_transport_error_body_still_decodes_json():
    # RFC 6749 error responses are still JSON; the transport decodes them so
    # auth._require_token_response can inspect the "error" field.
    client = _RecordingClient(
        HttpResponse(status=400, body=json.dumps({"error": "invalid_grant"}).encode())
    )
    transport = token_transport_from_http(client)
    assert transport("https://token", {"grant_type": "refresh_token"}) == {
        "error": "invalid_grant"
    }


# --- UrllibHttpClient constructor (request path is cloud_live / no cover) ---- #


def test_urllib_client_default_timeout():
    client = UrllibHttpClient()
    assert client._timeout_s == 30.0


def test_urllib_client_custom_timeout():
    assert UrllibHttpClient(timeout_s=5)._timeout_s == 5.0
