"""Unit tests for the shared provider base (``data/cloud/providers/base.py``).

Network-free, no-Qt coverage of the pieces the concrete adapters build on:

* :func:`build_versions` / ``_coerce_size`` — normalize untrusted ``(rev, size)`` pairs
  to the port's ordered :class:`CloudVersion` tuple (deterministic 0-based ordinals,
  ``version_id == remote_revision_id``), rejecting malformed ids/sizes (Article VII);
* :class:`ProviderAuth` — access-token caching, the keyring-backed refresh path, the
  not-connected error, ``force_refresh`` / ``is_connected`` / ``disconnect`` and
  ``connect`` — all against a **mocked keyring** and an **injected token transport**
  (the real OS keyring and network are never touched);
* :class:`BaseProviderAdapter` — the Bearer-header injection, the single 401
  refresh-and-retry, the non-2xx -> :class:`HttpError` normalization, and the defensive
  ``_get_json`` / ``_post_json`` / ``_require_field`` helpers.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.cloud import auth as _auth
from pixelart_creator.data.cloud import token_store as _token_store
from pixelart_creator.data.cloud.port import CloudDataError, CloudError
from pixelart_creator.data.cloud.providers import base as _base
from pixelart_creator.data.cloud.providers._http import HttpError, HttpResponse
from pixelart_creator.data.cloud.providers.base import (
    BaseProviderAdapter,
    OAuthConfig,
    ProviderAuth,
    _coerce_size,
    build_versions,
)
from pixelart_creator.logic.constants import MAX_CLOUD_PROJECT_BYTES
from pixelart_creator.logic.version_history import CloudVersion
from tests.data._cloud_provider_fakes import (
    MockHttpClient,
    Routes,
    empty_resp,
    json_resp,
)

# --- build_versions --------------------------------------------------------- #


def test_build_versions_normalizes_pairs():
    versions = build_versions([("rev-a", 10), ("rev-b", 20)])
    assert all(isinstance(v, CloudVersion) for v in versions)
    assert [v.ordinal for v in versions] == [0, 1]
    assert [v.created_marker for v in versions] == [0, 1]
    assert versions[0].version_id == "rev-a"
    assert versions[0].remote_revision_id == "rev-a"
    assert versions[1].size_bytes == 20


def test_build_versions_empty():
    assert build_versions([]) == ()


@pytest.mark.parametrize("bad_id", ["", 123, None])
def test_build_versions_rejects_bad_revision_id(bad_id):
    with pytest.raises(CloudDataError):
        build_versions([(bad_id, 0)])


# --- _coerce_size ----------------------------------------------------------- #


def test_coerce_size_valid():
    assert _coerce_size(0) == 0
    assert _coerce_size(123) == 123


@pytest.mark.parametrize("bad", [True, False, "10", 1.5, None])
def test_coerce_size_rejects_non_int(bad):
    with pytest.raises(CloudDataError):
        _coerce_size(bad)


def test_coerce_size_rejects_negative():
    with pytest.raises(CloudDataError):
        _coerce_size(-1)


def test_coerce_size_rejects_over_cap():
    with pytest.raises(CloudDataError):
        _coerce_size(MAX_CLOUD_PROJECT_BYTES + 1)


def test_coerce_size_at_cap_ok():
    assert _coerce_size(MAX_CLOUD_PROJECT_BYTES) == MAX_CLOUD_PROJECT_BYTES


# --- OAuthConfig ------------------------------------------------------------ #


def test_oauth_config_fields():
    cfg = OAuthConfig(
        client_id="cid",
        authorization_endpoint="https://auth",
        token_endpoint="https://token",
        scope="scope",
    )
    assert cfg.client_id == "cid"
    assert cfg.device_endpoint is None


# --- ProviderAuth: keyring-backed refresh (mocked) -------------------------- #


@pytest.fixture
def keyring(monkeypatch):
    """An in-memory token store patched over ``token_store`` (real keyring untouched)."""

    class _Store(dict):
        pass

    store = _Store()
    log = {"store": 0, "load": 0, "delete": 0}

    def _store(p, a, t):
        log["store"] += 1
        store[(p, a)] = t

    def _load(p, a):
        log["load"] += 1
        return store.get((p, a))

    def _delete(p, a):
        log["delete"] += 1
        store.pop((p, a), None)

    for name, fn in (
        ("store_token", _store),
        ("load_token", _load),
        ("delete_token", _delete),
    ):
        monkeypatch.setattr(_token_store, name, fn)
        monkeypatch.setattr(_base._token_store, name, fn, raising=False)
    store.log = log  # type: ignore[attr-defined]
    return store


def _config():
    return OAuthConfig(
        client_id="cid",
        authorization_endpoint="https://auth",
        token_endpoint="https://token",
        scope="scope",
    )


def test_access_token_returns_cached():
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    auth._access_token = "cached-tok"
    assert auth.access_token() == "cached-tok"


def test_access_token_refreshes_from_stored_refresh(keyring):
    keyring[("drive", "acct")] = "stored-refresh"

    def transport(url, form):
        assert form["grant_type"] == "refresh_token"
        assert form["refresh_token"] == "stored-refresh"
        return {"access_token": "new-access", "refresh_token": "rotated"}

    auth = ProviderAuth("drive", "acct", _config(), token_transport=transport)
    assert auth.access_token() == "new-access"
    # The rotated refresh token was written back to the (mocked) store.
    assert keyring[("drive", "acct")] == "rotated"


def test_access_token_not_connected_raises(keyring):
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    with pytest.raises(_auth.AuthError):
        auth.access_token()


def test_force_refresh_drops_cache_and_refreshes(keyring):
    keyring[("drive", "acct")] = "stored-refresh"
    auth = ProviderAuth(
        "drive",
        "acct",
        _config(),
        token_transport=lambda u, f: {"access_token": "refreshed"},
    )
    auth._access_token = "old"
    assert auth.force_refresh() == "refreshed"


def test_is_connected_cached_true():
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    auth._access_token = "tok"
    assert auth.is_connected() is True


def test_is_connected_stored_true(keyring):
    keyring[("drive", "acct")] = "refresh"
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    assert auth.is_connected() is True


def test_is_connected_absent_false(keyring):
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    assert auth.is_connected() is False


def test_is_connected_store_error_is_false(monkeypatch):
    def _boom(p, a):
        raise _token_store.TokenStoreError("no backend")

    monkeypatch.setattr(_token_store, "load_token", _boom)
    monkeypatch.setattr(_base._token_store, "load_token", _boom, raising=False)
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    assert auth.is_connected() is False


def test_disconnect_clears_and_deletes(keyring):
    keyring[("drive", "acct")] = "refresh"
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    auth._access_token = "tok"
    auth.disconnect()
    assert auth._access_token is None
    assert ("drive", "acct") not in keyring
    assert keyring.log["delete"] == 1  # type: ignore[attr-defined]


def test_store_tokens_ignores_missing_or_empty(keyring):
    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    auth._store_tokens({})  # nothing to cache or store
    auth._store_tokens({"access_token": "", "refresh_token": ""})  # empty -> ignored
    assert auth._access_token is None
    assert keyring.log["store"] == 0  # type: ignore[attr-defined]


def test_provider_auth_default_http_builds_transport():
    # No token_transport injected -> a default is built from a (constructed, unused)
    # UrllibHttpClient. This does not touch the network (nothing calls request()).
    auth = ProviderAuth("drive", "acct", _config())
    assert auth._token_transport is not None


# --- ProviderAuth.connect (mocked loopback + exchange, no sockets) ---------- #


def test_connect_runs_flow_and_stores_tokens(keyring, monkeypatch):
    opened = {}

    class _FakeServer:
        redirect_uri = "http://127.0.0.1:5000/"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def wait_for_code(self, expected_state=None):
            return "auth-code", expected_state or "state"

    fixed_pair = _auth.create_pkce_pair(verifier="a" * 43)
    monkeypatch.setattr(_base._auth, "LoopbackRedirectServer", _FakeServer)
    monkeypatch.setattr(_base._auth, "create_pkce_pair", lambda: fixed_pair)
    monkeypatch.setattr(
        _base._auth,
        "build_authorization_url",
        lambda *a, **k: "https://auth/authorize?x=1",
    )

    def _exchange(token_endpoint, **kwargs):
        assert kwargs["code"] == "auth-code"
        return {"access_token": "acc-final", "refresh_token": "ref-final"}

    monkeypatch.setattr(_base._auth, "exchange_code", _exchange)

    auth = ProviderAuth("drive", "acct", _config(), token_transport=lambda u, f: {})
    auth.connect(lambda url: opened.setdefault("url", url))

    assert opened["url"] == "https://auth/authorize?x=1"
    assert auth.access_token() == "acc-final"
    assert keyring[("drive", "acct")] == "ref-final"


# --- BaseProviderAdapter transport internals -------------------------------- #


class _StubAuth:
    """A minimal ProviderAuth stand-in for BaseProviderAdapter transport tests."""

    def __init__(self, token="tok-1", refreshed="tok-2"):
        self._token = token
        self._refreshed = refreshed
        self.refreshed_count = 0

    def access_token(self):
        return self._token

    def force_refresh(self):
        self.refreshed_count += 1
        self._token = self._refreshed
        return self._token

    def is_connected(self):
        return True


class _Adapter(BaseProviderAdapter):
    """A concrete BaseProviderAdapter exposing the protected transport helpers."""

    def capabilities(self):  # pragma: no cover - not exercised here
        raise NotImplementedError

    def put(self, project_id, blob, *, parent_version=None):  # pragma: no cover
        raise NotImplementedError

    def get(self, project_id, version_id):  # pragma: no cover
        raise NotImplementedError

    def list_versions(self, project_id):  # pragma: no cover
        raise NotImplementedError

    def latest(self, project_id):  # pragma: no cover
        raise NotImplementedError

    def delete(self, project_id):  # pragma: no cover
        raise NotImplementedError

    def put_recovery(self, project_id, blob):  # pragma: no cover
        raise NotImplementedError

    def get_recovery(self, project_id):  # pragma: no cover
        raise NotImplementedError


def test_request_adds_bearer_header():
    http = MockHttpClient(Routes().add(lambda r: True, json_resp({"ok": True})))
    adapter = _Adapter(_StubAuth("tok-1"), http=http)
    adapter._request("GET", "https://api/x")
    assert http.calls[0].authorization == "Bearer tok-1"


def test_request_401_refreshes_once_and_retries():
    class _Once:
        def __init__(self):
            self.n = 0

        def __call__(self, rec):
            self.n += 1
            if self.n == 1:
                return HttpResponse(status=401)
            return json_resp({"ok": True})

    http = MockHttpClient(_Once())
    stub = _StubAuth("tok-1", "tok-2")
    adapter = _Adapter(stub, http=http)
    resp = adapter._request("GET", "https://api/x")
    assert resp.ok
    assert stub.refreshed_count == 1
    assert http.auth_headers == ["Bearer tok-1", "Bearer tok-2"]


def test_request_non_2xx_raises_http_error():
    http = MockHttpClient(Routes().add(lambda r: True, empty_resp(500)))
    adapter = _Adapter(_StubAuth(), http=http)
    with pytest.raises(HttpError) as exc:
        adapter._request("GET", "https://api/x")
    assert exc.value.status == 500


def test_get_json_decodes_object():
    http = MockHttpClient(Routes().add(lambda r: True, json_resp({"k": "v"})))
    adapter = _Adapter(_StubAuth(), http=http)
    assert adapter._get_json("https://api/x") == {"k": "v"}


def test_post_json_decodes_object():
    http = MockHttpClient(Routes().add(lambda r: True, json_resp({"k": 2})))
    adapter = _Adapter(_StubAuth(), http=http)
    assert adapter._post_json("https://api/x", body=b"{}") == {"k": 2}


def test_require_field_present():
    assert BaseProviderAdapter._require_field({"a": 1}, "a") == 1


def test_require_field_missing_raises():
    with pytest.raises(CloudDataError):
        BaseProviderAdapter._require_field({}, "missing")


def test_with_auth_merges_headers():
    merged = BaseProviderAdapter._with_auth({"X": "1"}, "tok")
    assert merged == {"X": "1", "Authorization": "Bearer tok"}


def test_base_is_connected_delegates_to_auth():
    adapter = _Adapter(_StubAuth(), http=MockHttpClient(lambda r: json_resp({})))
    assert adapter.is_connected() is True


def test_adapter_default_http_is_constructed():
    # http=None -> a real UrllibHttpClient is constructed (no request is made).
    adapter = _Adapter(_StubAuth())
    assert adapter._http is not None
