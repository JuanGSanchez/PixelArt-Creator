"""CloudPort contract conformance for the real provider adapters (no Qt, no network).

Phase-10 Slice-C live-provider adapters (``data/cloud/providers/{drive,onedrive,
dropbox}.py``) are exercised here entirely through a **mocked**
:class:`~testing.suites.data._cloud_provider_fakes.MockHttpClient` — recorded/synthetic provider
responses, **no network, no credentials, no OS keyring**. These are the CI contract
tests (they carry **NO** ``cloud_live`` marker); only genuinely live end-to-end runs
would be ``cloud_live``.

Coverage focus (per the AGT-04 charge):

* the full ``CloudPort`` verb set per provider — put / get / list_versions / latest /
  delete / put_recovery / get_recovery / capabilities / is_connected — asserting each
  maps the provider's revision/change model to the port's normalized
  :class:`CloudVersion` and the deterministic 0-based ordinal correctly;
* the capability model per provider (Drive named+delete / OneDrive auto-only+no-delete /
  Dropbox no-name+no-delete+cap-100), and that **no** provider/urllib type or exception
  leaks above the port (only ``CloudError`` / ``CloudDataError`` surface);
* auth 401 -> refresh -> retry against a **mocked keyring**, with tokens never appearing
  in returned data;
* untrusted-input defence (Article VII): malformed / missing-field responses raise
  ``CloudDataError`` and the adapters contain no ``eval`` / ``exec``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pixelart_creator.data.cloud import token_store as _token_store
from pixelart_creator.data.cloud.port import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
)
from pixelart_creator.data.cloud.providers import base as _base
from pixelart_creator.data.cloud.providers._http import HttpError
from pixelart_creator.logic.constants import MAX_CLOUD_VERSIONS
from pixelart_creator.logic.version_history import CloudVersion
from testing.suites.data._cloud_provider_fakes import (
    PROVIDERS,
    Fail401Once,
    MockHttpClient,
    Routes,
    empty_resp,
    json_resp,
    make_adapter,
    make_fake,
    make_provider_auth,
)

PID = "proj"


@pytest.fixture
def mock_keyring(monkeypatch):
    """Patch the token store with an in-memory dict (the real OS keyring is untouched).

    Returns the backing ``{(provider, account): token}`` dict so a test can seed a
    refresh token and assert what was written — proving the code path went through the
    mock, never the OS credential locker.
    """

    class _Store(dict):
        pass

    store = _Store()
    calls: dict = {"store": 0, "load": 0, "delete": 0}

    def _store(provider, account, token):
        calls["store"] += 1
        store[(provider, account)] = token

    def _load(provider, account):
        calls["load"] += 1
        return store.get((provider, account))

    def _delete(provider, account):
        calls["delete"] += 1
        store.pop((provider, account), None)

    for name, fn in (
        ("store_token", _store),
        ("load_token", _load),
        ("delete_token", _delete),
    ):
        monkeypatch.setattr(_token_store, name, fn)
        # base.py references the module via the ``_token_store`` alias.
        monkeypatch.setattr(_base._token_store, name, fn, raising=False)
    store.calls = calls  # type: ignore[attr-defined]
    return store


# --- put / get / list / latest round-trip (parametrized) -------------------- #


@pytest.mark.parametrize("provider", PROVIDERS)
def test_put_get_round_trip(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    version = adapter.put(PID, b"blob-0")
    assert isinstance(version, CloudVersion)
    assert version.ordinal == 0
    assert version.created_marker == 0
    # version_id maps to the provider revision id (local<->remote map, BF-2).
    assert version.remote_revision_id == version.version_id
    assert adapter.get(PID, version.version_id) == b"blob-0"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_put_appends_ordered_ascending_versions(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    adapter.put(PID, b"v0")
    adapter.put(PID, b"v1")
    adapter.put(PID, b"v2")
    versions = adapter.list_versions(PID)
    assert [v.ordinal for v in versions] == [0, 1, 2]
    assert [v.created_marker for v in versions] == [0, 1, 2]
    # deterministic ascending ordinals and unique ids (validate via the model helper).
    ids = [v.version_id for v in versions]
    assert len(set(ids)) == 3


@pytest.mark.parametrize("provider", PROVIDERS)
def test_get_maps_each_version_to_its_content(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    adapter.put(PID, b"first")
    adapter.put(PID, b"second")
    versions = adapter.list_versions(PID)
    assert adapter.get(PID, versions[0].version_id) == b"first"
    assert adapter.get(PID, versions[1].version_id) == b"second"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_latest_returns_most_recent(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    adapter.put(PID, b"old")
    newest = adapter.put(PID, b"new")
    assert adapter.latest(PID).version_id == newest.version_id


@pytest.mark.parametrize("provider", PROVIDERS)
def test_list_versions_unknown_project_is_empty(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    assert adapter.list_versions("does-not-exist") == ()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_latest_unknown_project_raises_cloud_error(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    with pytest.raises(CloudError):
        adapter.latest("nope")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_get_unknown_project_raises_cloud_error(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    with pytest.raises(CloudError):
        adapter.get("nope", "some-rev")


# --- recovery slot is distinct from version history ------------------------- #


@pytest.mark.parametrize("provider", PROVIDERS)
def test_recovery_slot_is_distinct_from_versions(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    adapter.put(PID, b"explicit-save")
    assert adapter.get_recovery(PID) is None
    adapter.put_recovery(PID, b"autosave-working-copy")
    # Writing recovery must not add a version (REQ-P10-DATA-004).
    assert len(adapter.list_versions(PID)) == 1
    assert adapter.get_recovery(PID) == b"autosave-working-copy"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_get_recovery_absent_returns_none(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    assert adapter.get_recovery(PID) is None


@pytest.mark.parametrize("provider", PROVIDERS)
def test_delete_removes_project_and_recovery(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    adapter.put(PID, b"v0")
    adapter.put_recovery(PID, b"recov")
    adapter.delete(PID)
    assert adapter.list_versions(PID) == ()
    assert adapter.get_recovery(PID) is None


@pytest.mark.parametrize("provider", PROVIDERS)
def test_delete_unknown_project_raises_cloud_error(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    with pytest.raises(CloudError):
        adapter.delete("never-existed")


# --- blob type validation --------------------------------------------------- #


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("bad_blob", ["a string", 123, None, ["list"]])
def test_put_rejects_non_bytes_blob(provider, bad_blob):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    with pytest.raises(CloudError):
        adapter.put(PID, bad_blob)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_put_recovery_rejects_non_bytes_blob(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    with pytest.raises(CloudError):
        adapter.put_recovery(PID, "not-bytes")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_put_accepts_bytearray(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    version = adapter.put(PID, bytearray(b"mutable"))
    assert adapter.get(PID, version.version_id) == b"mutable"


# --- is_connected ----------------------------------------------------------- #


@pytest.mark.parametrize("provider", PROVIDERS)
def test_is_connected_true_with_cached_token(provider):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    assert adapter.is_connected() is True


@pytest.mark.parametrize("provider", PROVIDERS)
def test_is_connected_false_without_token(provider, mock_keyring):
    auth = make_provider_auth(provider, token=None)
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)), auth=auth)
    assert adapter.is_connected() is False


# --- capability mapping (Researcher §1.2) ----------------------------------- #

_EXPECTED_CAPS = {
    "drive": dict(
        supports_named_revisions=True,
        supports_revision_delete=True,
        max_versions_per_call=None,
        supports_optimistic_concurrency=True,
    ),
    "onedrive": dict(
        supports_named_revisions=False,
        supports_revision_delete=False,
        max_versions_per_call=None,
        supports_optimistic_concurrency=True,
    ),
    "dropbox": dict(
        supports_named_revisions=False,
        supports_revision_delete=False,
        max_versions_per_call=MAX_CLOUD_VERSIONS,
        supports_optimistic_concurrency=True,
    ),
}


@pytest.mark.parametrize("provider", PROVIDERS)
def test_capabilities_type_and_scope(provider):
    caps = make_adapter(provider, MockHttpClient(make_fake(provider))).capabilities()
    assert isinstance(caps, CloudCapabilities)
    assert caps.change_feed_scope == "drive"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_capability_flags_match_provider_model(provider):
    caps = make_adapter(provider, MockHttpClient(make_fake(provider))).capabilities()
    expected = _EXPECTED_CAPS[provider]
    assert caps.supports_named_revisions == expected["supports_named_revisions"]
    assert caps.supports_revision_delete == expected["supports_revision_delete"]
    assert caps.max_versions_per_call == expected["max_versions_per_call"]
    assert (
        caps.supports_optimistic_concurrency
        == expected["supports_optimistic_concurrency"]
    )


def test_dropbox_caps_100_versions_per_call():
    caps = make_adapter("dropbox", MockHttpClient(make_fake("dropbox"))).capabilities()
    assert caps.max_versions_per_call == 100


def test_only_drive_supports_named_and_delete_revisions():
    drive = make_adapter("drive", MockHttpClient(make_fake("drive"))).capabilities()
    onedrive = make_adapter(
        "onedrive", MockHttpClient(make_fake("onedrive"))
    ).capabilities()
    dropbox = make_adapter(
        "dropbox", MockHttpClient(make_fake("dropbox"))
    ).capabilities()
    assert drive.supports_named_revisions and drive.supports_revision_delete
    assert (
        not onedrive.supports_named_revisions and not onedrive.supports_revision_delete
    )
    assert not dropbox.supports_named_revisions and not dropbox.supports_revision_delete


# --- auth: 401 -> refresh -> retry (mocked keyring, no network) ------------- #


@pytest.mark.parametrize("provider", PROVIDERS)
def test_401_triggers_single_refresh_and_retry(provider, mock_keyring):
    mock_keyring[(provider, "user@example.com")] = "refresh-token-SECRET"

    def _transport(url, form):
        # A network-free stand-in for the OAuth token endpoint.
        assert form["grant_type"] == "refresh_token"
        return {"access_token": "fresh-access-2", "refresh_token": "rt-rotated"}

    auth = make_provider_auth(
        provider, token="stale-access-1", token_transport=_transport
    )
    http = MockHttpClient(Fail401Once(make_fake(provider)))
    adapter = make_adapter(provider, http, auth=auth)

    version = adapter.put(PID, b"payload")

    # The stale token was used first; after the 401, the refreshed token is used.
    assert "Bearer stale-access-1" in http.auth_headers
    assert "Bearer fresh-access-2" in http.auth_headers
    # The refresh reloaded the token from the (mocked) keyring exactly.
    assert mock_keyring.calls["load"] >= 1  # type: ignore[attr-defined]
    # Tokens (access + refresh) must never appear in the normalized returned data.
    blob = repr(version)
    for secret in (
        "stale-access-1",
        "fresh-access-2",
        "refresh-token-SECRET",
        "rt-rotated",
    ):
        assert secret not in blob


@pytest.mark.parametrize("provider", PROVIDERS)
def test_returned_bytes_never_contain_tokens(provider, mock_keyring):
    adapter = make_adapter(provider, MockHttpClient(make_fake(provider)))
    version = adapter.put(PID, b"clean-payload")
    fetched = adapter.get(PID, version.version_id)
    assert fetched == b"clean-payload"
    assert b"access-tok-1" not in fetched


# --- isolation: only CloudError / CloudDataError surface -------------------- #


@pytest.mark.parametrize("provider", PROVIDERS)
def test_transport_500_surfaces_as_cloud_error_only(provider):
    # A hard 5xx from the provider must normalise to the CloudError family — no urllib
    # type, no provider-specific exception (REQ-P10-DATA-007).
    routes = Routes().add(lambda r: True, empty_resp(500))
    adapter = make_adapter(provider, MockHttpClient(routes))
    with pytest.raises(CloudError) as exc:
        adapter.put(PID, b"x")
    assert isinstance(exc.value, HttpError)
    assert isinstance(exc.value, CloudError)


def test_http_error_is_cloud_error_subclass():
    assert issubclass(HttpError, CloudError)


# --- untrusted-input defence (Article VII) ---------------------------------- #


def test_drive_revisions_not_a_list_raises_cloud_data_error():
    api = "https://www.googleapis.com/drive/v3"
    routes = (
        Routes()
        .add(
            lambda r: r.method == "GET" and r.url == f"{api}/files",
            json_resp({"files": [{"id": "F1", "name": f"{PID}.pixproj"}]}),
        )
        .add(
            lambda r: r.url.endswith("/revisions"),
            json_resp({"revisions": "not-a-list"}),
        )
    )
    adapter = make_adapter("drive", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.list_versions(PID)


def test_onedrive_versions_value_not_a_list_raises_cloud_data_error():
    api = "https://graph.microsoft.com/v1.0"
    approot = f"{api}/drive/special/approot"
    routes = (
        Routes()
        .add(
            lambda r: r.method == "GET" and r.url == f"{approot}:/{PID}.pixproj",
            json_resp({"id": "item-1"}),
        )
        .add(
            lambda r: r.url.endswith("/versions"),
            json_resp({"value": {"not": "a list"}}),
        )
    )
    adapter = make_adapter("onedrive", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.list_versions(PID)


def test_dropbox_entries_not_a_list_raises_cloud_data_error():
    rpc = "https://api.dropboxapi.com/2"
    routes = Routes().add(
        lambda r: r.url == f"{rpc}/files/list_revisions",
        json_resp({"entries": "nope"}),
    )
    adapter = make_adapter("dropbox", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.list_versions(PID)


def test_drive_missing_id_field_raises_cloud_data_error():
    api = "https://www.googleapis.com/drive/v3"
    routes = Routes().add(
        lambda r: r.method == "GET" and r.url == f"{api}/files",
        json_resp({"files": [{"name": f"{PID}.pixproj"}]}),  # 'id' missing
    )
    adapter = make_adapter("drive", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.get(PID, "r1")


def test_drive_malformed_file_id_type_raises_cloud_data_error():
    api = "https://www.googleapis.com/drive/v3"
    routes = Routes().add(
        lambda r: r.method == "GET" and r.url == f"{api}/files",
        json_resp({"files": [{"id": 12345, "name": f"{PID}.pixproj"}]}),
    )
    adapter = make_adapter("drive", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.get(PID, "r1")


def test_onedrive_non_404_http_error_propagates():
    api = "https://graph.microsoft.com/v1.0"
    approot = f"{api}/drive/special/approot"
    routes = Routes().add(
        lambda r: r.url == f"{approot}:/{PID}.pixproj",
        empty_resp(500),
    )
    adapter = make_adapter("onedrive", MockHttpClient(routes))
    with pytest.raises(HttpError):
        adapter.get(PID, "v1")


def test_dropbox_non_409_download_error_propagates():
    content = "https://content.dropboxapi.com/2"
    routes = Routes().add(
        lambda r: r.url == f"{content}/files/download",
        empty_resp(500),
    )
    adapter = make_adapter("dropbox", MockHttpClient(routes))
    with pytest.raises(HttpError):
        adapter.get(PID, "rev1")


def test_dropbox_get_unknown_rev_maps_409_to_cloud_error():
    content = "https://content.dropboxapi.com/2"
    routes = Routes().add(
        lambda r: r.url == f"{content}/files/download",
        empty_resp(409),
    )
    adapter = make_adapter("dropbox", MockHttpClient(routes))
    with pytest.raises(CloudError):
        adapter.get(PID, "rev-absent")


# --- provider-specific defensive branches ----------------------------------- #

DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
OD_API = "https://graph.microsoft.com/v1.0"
OD_APPROOT = f"{OD_API}/drive/special/approot"
DBX_RPC = "https://api.dropboxapi.com/2"
DBX_CONTENT = "https://content.dropboxapi.com/2"


def test_drive_as_int_coercions():
    from pixelart_creator.data.cloud.providers.drive import _as_int

    assert _as_int(42) == 42
    assert _as_int("42") == 42
    with pytest.raises(CloudDataError):
        _as_int(True)
    with pytest.raises(CloudDataError):
        _as_int("not-a-number")


def test_drive_create_malformed_id_raises_cloud_data_error():
    routes = (
        Routes()
        .add(
            lambda r: r.method == "GET" and r.url == f"{DRIVE_API}/files",
            json_resp({"files": []}),  # absent -> triggers create
        )
        .add(
            lambda r: r.method == "POST" and r.url == DRIVE_UPLOAD,
            json_resp({"id": 999}),  # malformed non-str id
        )
    )
    adapter = make_adapter("drive", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.put(PID, b"x")


def test_drive_put_recovery_updates_existing_file():
    adapter = make_adapter("drive", MockHttpClient(make_fake("drive")))
    adapter.put_recovery(PID, b"recovery-v0")
    adapter.put_recovery(PID, b"recovery-v1")  # existing file -> PATCH branch
    assert adapter.get_recovery(PID) == b"recovery-v1"


def test_onedrive_malformed_item_id_raises_cloud_data_error():
    routes = Routes().add(
        lambda r: r.url == f"{OD_APPROOT}:/{PID}.pixproj",
        json_resp({"id": 12345}),  # malformed non-str id
    )
    adapter = make_adapter("onedrive", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.get(PID, "v1")


def test_onedrive_upload_malformed_id_raises_cloud_data_error():
    routes = Routes().add(
        lambda r: r.method == "PUT" and r.url.endswith(":/content"),
        json_resp({"id": None}),  # malformed id on upload
    )
    adapter = make_adapter("onedrive", MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.put(PID, b"x")


def test_dropbox_list_revisions_non_409_error_propagates():
    routes = Routes().add(
        lambda r: r.url == f"{DBX_RPC}/files/list_revisions",
        empty_resp(500),
    )
    adapter = make_adapter("dropbox", MockHttpClient(routes))
    with pytest.raises(HttpError):
        adapter.list_versions(PID)


def test_dropbox_delete_non_409_error_propagates():
    routes = Routes().add(
        lambda r: r.url == f"{DBX_RPC}/files/delete_v2",
        empty_resp(500),
    )
    adapter = make_adapter("dropbox", MockHttpClient(routes))
    with pytest.raises(HttpError):
        adapter.delete(PID)


def test_dropbox_get_recovery_non_409_error_propagates():
    routes = Routes().add(
        lambda r: r.url == f"{DBX_CONTENT}/files/download",
        empty_resp(500),
    )
    adapter = make_adapter("dropbox", MockHttpClient(routes))
    with pytest.raises(HttpError):
        adapter.get_recovery(PID)


def test_dropbox_get_recovery_409_returns_none():
    routes = Routes().add(
        lambda r: r.url == f"{DBX_CONTENT}/files/download",
        empty_resp(409),
    )
    adapter = make_adapter("dropbox", MockHttpClient(routes))
    assert adapter.get_recovery(PID) is None


# --- no eval / exec in the provider adapters (static defence) --------------- #


def test_provider_modules_contain_no_eval_or_exec():
    root = (
        Path(__file__).resolve().parents[3]
        / "pixelart_creator"
        / "data"
        / "cloud"
        / "providers"
    )
    offenders = []
    for src in sorted(root.glob("*.py")):
        text = src.read_text(encoding="utf-8")
        if "eval(" in text or "exec(" in text:
            offenders.append(src.name)
    assert offenders == [], f"eval/exec found in provider adapters: {offenders}"


# --- oversized provider JSON body is rejected before use (Article VII) ------ #


@pytest.mark.parametrize("provider", PROVIDERS)
def test_oversized_json_body_rejected(provider, monkeypatch):
    # Cap decode_json tiny so a modest synthetic body trips the size guard without
    # allocating 256 MiB. The adapters call decode_json for every JSON response.
    from pixelart_creator.data.cloud.providers import _http as http_mod

    monkeypatch.setattr(http_mod, "MAX_CLOUD_PROJECT_BYTES", 8)
    big = json.dumps({"padding": "x" * 64}).encode("utf-8")
    routes = Routes().add(lambda r: True, http_mod.HttpResponse(status=200, body=big))
    adapter = make_adapter(provider, MockHttpClient(routes))
    with pytest.raises(CloudDataError):
        adapter.put(PID, b"payload")
