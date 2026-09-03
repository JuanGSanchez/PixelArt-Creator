"""Tests for the shared LLM transport seam ``data/llm/_http.py`` (Phase-14 14D, no Qt).

Network-free coverage of the single ``urllib`` POST + bounded-retry seam both real
adapters share (spec REQ-P14-DATA-004/-007; SC-P14-D004/-D007; skill
``llm-adapter-normalization`` step 5; research finding ``ad2616c7`` R4.1/R4.3). The real
network is NEVER touched: ``urllib.request.urlopen`` is monkeypatched with a scripted
fake transport so the retry/timeout/error-mapping branches run deterministically and the
default gate stays offline.

Covered:

* :func:`validate_endpoint` — https accepted, plaintext http only for loopback, a remote
  http / a bad scheme / a hostless URL rejected as ``LLMResponseError`` before any I/O;
* :func:`post_json` — happy path; bounded retry on a transient transport error / a 5xx
  then success; retry EXHAUSTION raising ``LLMResponseError`` (bounded, never infinite);
  a 4xx NOT retried; the ``timeout`` param honoured; malformed / non-object / non-utf8
  bodies mapped to ``LLMResponseError`` (no raw ``urllib``/``json`` type leaks);
* the auth header (the API key) never appears in a normalised error message.

Pure ``data`` unit — no Qt, no network, no real key.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from pixelart_creator.data.llm import _http as http_mod
from pixelart_creator.data.llm._http import post_json, validate_endpoint
from pixelart_creator.data.llm.port import LLMResponseError

_URL = "https://api.example.test/v1/chat/completions"
# A recognisable secret in the auth header; asserted never to leak into an error.
_SECRET = "sk-SUPER-SECRET-http-key-do-not-log-999"
_AUTH = {"Authorization": f"Bearer {_SECRET}"}
_BODY = {"model": "m", "messages": []}


# --- a scripted fake urllib transport (no network) -------------------------- #


class _FakeResponse:
    """A minimal context-manager response with a ``read()`` (like ``urlopen``)."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(_URL, code, f"HTTP {code}", {}, None)


class _ScriptedTransport:
    """Yields the Nth scripted outcome per ``urlopen`` call (raise or return body).

    Indexing is exact: an over-call (which would mean an UNBOUNDED retry) raises
    ``IndexError`` and fails the test loudly rather than masking a runaway loop.
    """

    def __init__(self, outcomes) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0
        self.timeouts: list = []

    def __call__(self, request, timeout=None, context=None):
        self.timeouts.append(timeout)
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return _FakeResponse(outcome)


@pytest.fixture
def transport(monkeypatch):
    """Install a scripted fake ``urlopen``; the test supplies the outcome script."""

    def _install(outcomes):
        fake = _ScriptedTransport(outcomes)
        monkeypatch.setattr(urllib.request, "urlopen", fake)
        return fake

    return _install


def _ok_body(text: str = "ok") -> bytes:
    return json.dumps({"choices": [{"message": {"content": text}}]}).encode("utf-8")


# --- validate_endpoint ------------------------------------------------------ #


def test_validate_endpoint_accepts_https_unchanged():
    assert validate_endpoint(_URL) == _URL


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/v1/chat/completions",
        "http://127.0.0.1:8080/v1/messages",
        "http://[::1]:1234/v1/chat/completions",
    ],
)
def test_validate_endpoint_allows_plaintext_http_for_loopback(url):
    # Local model runtimes (Ollama / llama.cpp) never leave the machine (R4.3).
    assert validate_endpoint(url) == url


def test_validate_endpoint_rejects_remote_plaintext_http():
    with pytest.raises(LLMResponseError):
        validate_endpoint("http://api.remote.example/v1/chat/completions")


def test_validate_endpoint_rejects_non_http_scheme():
    with pytest.raises(LLMResponseError):
        validate_endpoint("ftp://api.example.test/x")


def test_validate_endpoint_rejects_missing_host():
    with pytest.raises(LLMResponseError):
        validate_endpoint("https://")


# --- post_json happy path --------------------------------------------------- #


def test_post_json_returns_parsed_object_on_success(transport):
    t = transport([_ok_body("hello")])
    result = post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert result == {"choices": [{"message": {"content": "hello"}}]}
    assert t.calls == 1  # no retry needed


def test_post_json_honours_the_timeout_param(transport):
    t = transport([_ok_body()])
    post_json(_URL, _AUTH, _BODY, timeout=12.5, retries=0)
    assert t.timeouts == [12.5]


# --- bounded retry ---------------------------------------------------------- #


def test_post_json_retries_transient_transport_error_then_succeeds(transport):
    t = transport([urllib.error.URLError("conn reset"), _ok_body("recovered")])
    result = post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert result["choices"][0]["message"]["content"] == "recovered"
    assert t.calls == 2  # one failure, one success


def test_post_json_retries_on_transient_5xx_then_succeeds(transport):
    t = transport([_http_error(503), _ok_body("recovered")])
    result = post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert result["choices"][0]["message"]["content"] == "recovered"
    assert t.calls == 2


def test_post_json_retries_on_timeout_then_succeeds(transport):
    t = transport([TimeoutError("slow"), _ok_body()])
    post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert t.calls == 2


def test_post_json_retry_is_bounded_and_raises_on_exhaustion(transport):
    # retries=2 -> exactly 3 attempts, then a normalised error (never infinite).
    t = transport([urllib.error.URLError("down")] * 3)
    with pytest.raises(LLMResponseError):
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert t.calls == 3


def test_post_json_5xx_exhaustion_raises(transport):
    t = transport([_http_error(500)] * 3)
    with pytest.raises(LLMResponseError):
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert t.calls == 3


def test_post_json_zero_retries_attempts_once(transport):
    t = transport([urllib.error.URLError("down")])
    with pytest.raises(LLMResponseError):
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=0)
    assert t.calls == 1


# --- 4xx is a config/caller error, never retried ---------------------------- #


def test_post_json_4xx_is_not_retried(transport):
    t = transport([_http_error(401)])
    with pytest.raises(LLMResponseError):
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert t.calls == 1  # no retry on a 4xx


# --- error mapping: malformed provider bodies ------------------------------- #


def test_post_json_maps_non_json_body(transport):
    transport([b"{not json"])
    with pytest.raises(LLMResponseError):
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=0)


def test_post_json_maps_non_object_json_body(transport):
    transport([b"[1, 2, 3]"])
    with pytest.raises(LLMResponseError):
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=0)


def test_post_json_maps_non_utf8_body(transport):
    transport([b"\xff\xfe\x00"])
    with pytest.raises(LLMResponseError):
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=0)


def test_post_json_rejects_bad_endpoint_before_any_io(transport):
    t = transport([_ok_body()])
    with pytest.raises(LLMResponseError):
        post_json("http://remote.example/x", _AUTH, _BODY, timeout=5, retries=2)
    assert t.calls == 0  # rejected before a single network attempt


# --- the API key never leaks into a normalised error ------------------------ #


@pytest.mark.parametrize(
    "outcome",
    [
        urllib.error.URLError("boom"),
        _http_error(500),
        _http_error(403),
        TimeoutError("slow"),
    ],
)
def test_error_message_never_leaks_the_auth_key(transport, outcome):
    transport([outcome] * 3)
    with pytest.raises(LLMResponseError) as ei:
        post_json(_URL, _AUTH, _BODY, timeout=5, retries=2)
    assert _SECRET not in str(ei.value)
    assert _SECRET not in repr(ei.value)


def test_module_exposes_only_the_public_seam():
    assert set(http_mod.__all__) == {"validate_endpoint", "post_json"}
