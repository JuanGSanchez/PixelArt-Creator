"""Mocked HTTP transport + stateful provider fakes for the cloud-adapter tests.

Shared test infrastructure (NOT a ``test_`` module — pytest does not collect it) for
the Phase-10 live-provider contract tests (``tests/data/test_cloud_providers_*.py``).

Every real adapter (Drive / OneDrive / Dropbox) depends only on the injectable
:class:`~pixelart_creator.data.cloud.providers._http.HttpClient` *protocol*; these
helpers supply

* :class:`MockHttpClient` — records every request (method / url / headers / params /
  body) and delegates to a handler, so a test can drive the whole ``CloudPort`` contract
  with **no network and no credentials** and then assert on what was sent (e.g. the
  ``Authorization`` header, the retry sequence);
* stateful per-provider fakes (:class:`DriveFake`, :class:`OneDriveFake`,
  :class:`DropboxFake`) that emulate each provider's REST revision/change model closely
  enough to prove put -> list -> get -> latest round-trips and the recovery slot;
* :class:`Routes` — a tiny predicate router for focused malformed-response tests;
* auth/keyring helpers that keep the OS keyring and the network untouched (an injected
  ``token_transport`` + an in-memory token store patch).
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Mapping, Optional

from pixelart_creator.data.cloud.providers import drive as drive_mod
from pixelart_creator.data.cloud.providers import dropbox as dropbox_mod
from pixelart_creator.data.cloud.providers import onedrive as onedrive_mod
from pixelart_creator.data.cloud.providers._http import HttpResponse
from pixelart_creator.data.cloud.providers.base import ProviderAuth
from pixelart_creator.data.cloud.providers.drive import DRIVE_OAUTH, DriveAdapter
from pixelart_creator.data.cloud.providers.dropbox import DROPBOX_OAUTH, DropboxAdapter
from pixelart_creator.data.cloud.providers.onedrive import (
    ONEDRIVE_OAUTH,
    OneDriveAdapter,
)

PROVIDERS = ("drive", "onedrive", "dropbox")

# --- response builders ------------------------------------------------------ #


def json_resp(obj: Any, *, status: int = 200) -> HttpResponse:
    """A JSON-body :class:`HttpResponse` (what the provider REST APIs return)."""
    return HttpResponse(status=status, body=json.dumps(obj).encode("utf-8"))


def bytes_resp(data: bytes, *, status: int = 200) -> HttpResponse:
    """A raw-bytes :class:`HttpResponse` (a media/content download)."""
    return HttpResponse(status=status, body=bytes(data))


def empty_resp(status: int) -> HttpResponse:
    """An empty-body :class:`HttpResponse` for a bare status (204 / 404 / 409)."""
    return HttpResponse(status=status, body=b"")


# --- recording transport ---------------------------------------------------- #


class RecordedRequest:
    """One captured request the adapter issued through the seam."""

    def __init__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        params: Mapping[str, str],
        body: Optional[bytes],
    ) -> None:
        self.method = method
        self.url = url
        self.headers = dict(headers)
        self.params = dict(params)
        self.body = body

    @property
    def authorization(self) -> Optional[str]:
        """The ``Authorization`` header value (proves the Bearer token used)."""
        return self.headers.get("Authorization")


Handler = Callable[[RecordedRequest], HttpResponse]


class MockHttpClient:
    """An :class:`HttpClient` that records calls and delegates to ``handler``.

    Satisfies the ``HttpClient`` protocol structurally (a single ``request`` method);
    no network is ever touched.
    """

    def __init__(self, handler: Handler) -> None:
        self._handler = handler
        self.calls: List[RecordedRequest] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> HttpResponse:
        rec = RecordedRequest(method, url, headers or {}, params or {}, body)
        self.calls.append(rec)
        return self._handler(rec)

    @property
    def auth_headers(self) -> List[Optional[str]]:
        """The ``Authorization`` header seen on every recorded call, in order."""
        return [c.authorization for c in self.calls]


class Routes:
    """A predicate router: first matching ``(pred, response)`` wins (focused tests)."""

    def __init__(self) -> None:
        self._routes: List[tuple] = []

    def add(self, pred: Callable[[RecordedRequest], bool], resp: Any) -> "Routes":
        """Register a route; ``resp`` may be an :class:`HttpResponse` or a callable."""
        self._routes.append((pred, resp))
        return self

    def __call__(self, rec: RecordedRequest) -> HttpResponse:
        for pred, resp in self._routes:
            if pred(rec):
                return resp(rec) if callable(resp) else resp
        raise AssertionError(f"no mock route for {rec.method} {rec.url}")


class Fail401Once:
    """Wrap a handler to return a single ``401`` before delegating (refresh test)."""

    def __init__(self, inner: Handler) -> None:
        self._inner = inner
        self.fired = False

    def __call__(self, rec: RecordedRequest) -> HttpResponse:
        if not self.fired:
            self.fired = True
            return HttpResponse(status=401, body=b'{"error":"invalid_token"}')
        return self._inner(rec)


# --- Google Drive stateful fake --------------------------------------------- #

_DRIVE_API = drive_mod._API
_DRIVE_UPLOAD = drive_mod._UPLOAD
_DRIVE_BOUNDARY = drive_mod._MULTIPART_BOUNDARY


def _parse_multipart(body: bytes) -> tuple:
    """Extract ``(metadata_dict, blob_bytes)`` from a Drive multipart/related body."""
    meta_part = body.split(b"application/json; charset=UTF-8\r\n\r\n", 1)[1]
    meta_json = meta_part.split(b"\r\n--", 1)[0]
    meta = json.loads(meta_json.decode("utf-8"))
    blob_part = body.split(b"application/octet-stream\r\n\r\n", 1)[1]
    blob = blob_part.rsplit(b"\r\n--", 1)[0]
    return meta, blob


class DriveFake:
    """A stateful Google Drive v3 appDataFolder emulator."""

    def __init__(self) -> None:
        self.files: Dict[str, Dict[str, Any]] = (
            {}
        )  # name -> {id, revs:[{rev,size,content}]}
        self._fid = 0
        self._rid = 0

    def _by_id(self, fid: str) -> Dict[str, Any]:
        for f in self.files.values():
            if f["id"] == fid:
                return f
        raise AssertionError(f"DriveFake: no file id {fid}")

    def __call__(self, rec: RecordedRequest) -> HttpResponse:
        m, url = rec.method, rec.url
        if m == "GET" and url == f"{_DRIVE_API}/files":
            q = rec.params.get("q", "")
            match = re.search(r"name = '([^']*)'", q)
            name = match.group(1) if match else ""
            f = self.files.get(name)
            files = [{"id": f["id"], "name": name}] if f else []
            return json_resp({"files": files})
        if m == "POST" and url == _DRIVE_UPLOAD:
            meta, blob = _parse_multipart(rec.body or b"")
            name = meta["name"]
            self._fid += 1
            self._rid += 1
            fid = f"file-{self._fid}"
            self.files[name] = {
                "id": fid,
                "revs": [{"rev": f"r{self._rid}", "size": len(blob), "content": blob}],
            }
            return json_resp({"id": fid})
        if m == "PATCH" and url.startswith(f"{_DRIVE_UPLOAD}/"):
            fid = url[len(f"{_DRIVE_UPLOAD}/") :]
            f = self._by_id(fid)
            blob = bytes(rec.body or b"")
            self._rid += 1
            f["revs"].append(
                {"rev": f"r{self._rid}", "size": len(blob), "content": blob}
            )
            return json_resp({"id": fid})
        if m == "GET" and url.endswith("/revisions"):
            fid = url[len(f"{_DRIVE_API}/files/") : -len("/revisions")]
            f = self._by_id(fid)
            revs = [{"id": r["rev"], "size": str(r["size"])} for r in f["revs"]]
            return json_resp({"revisions": revs})
        if m == "GET" and "/revisions/" in url:
            fid = url[len(f"{_DRIVE_API}/files/") :].split("/", 1)[0]
            vid = url.rsplit("/", 1)[1]
            f = self._by_id(fid)
            for r in f["revs"]:
                if r["rev"] == vid:
                    return bytes_resp(r["content"])
            return empty_resp(404)
        if m == "GET" and url.startswith(f"{_DRIVE_API}/files/"):
            fid = url[len(f"{_DRIVE_API}/files/") :]
            f = self._by_id(fid)
            return bytes_resp(f["revs"][-1]["content"])
        if m == "DELETE" and url.startswith(f"{_DRIVE_API}/files/"):
            fid = url[len(f"{_DRIVE_API}/files/") :]
            for name, f in list(self.files.items()):
                if f["id"] == fid:
                    del self.files[name]
            return empty_resp(204)
        raise AssertionError(f"DriveFake unhandled {m} {url}")


# --- OneDrive (Microsoft Graph) stateful fake ------------------------------- #

_OD_API = onedrive_mod._API
_OD_APPROOT = onedrive_mod._APPROOT


class OneDriveFake:
    """A stateful Microsoft Graph approot emulator."""

    def __init__(self) -> None:
        self.items: Dict[str, Dict[str, Any]] = (
            {}
        )  # name -> {id, versions:[{id,size,content}]}
        self._iid = 0
        self._vid = 0

    def _by_id(self, iid: str) -> Dict[str, Any]:
        for it in self.items.values():
            if it["id"] == iid:
                return it
        raise AssertionError(f"OneDriveFake: no item id {iid}")

    def __call__(self, rec: RecordedRequest) -> HttpResponse:
        m, url = rec.method, rec.url
        approot_prefix = f"{_OD_APPROOT}:/"
        if m == "PUT" and url.startswith(approot_prefix) and url.endswith(":/content"):
            name = url[len(approot_prefix) : -len(":/content")]
            blob = bytes(rec.body or b"")
            it = self.items.get(name)
            if it is None:
                self._iid += 1
                it = {"id": f"item-{self._iid}", "versions": []}
                self.items[name] = it
            self._vid += 1
            it["versions"].append(
                {"id": f"v{self._vid}", "size": len(blob), "content": blob}
            )
            return json_resp({"id": it["id"]})
        if (
            m == "GET"
            and url.startswith(approot_prefix)
            and "/versions" not in url
            and not url.endswith(":/content")
        ):
            name = url[len(approot_prefix) :]
            it = self.items.get(name)
            if it is None:
                return empty_resp(404)
            return json_resp({"id": it["id"]})
        if m == "GET" and url.endswith("/versions"):
            iid = url[len(f"{_OD_API}/drive/items/") : -len("/versions")]
            it = self._by_id(iid)
            vals = [
                {"id": v["id"], "size": v["size"]} for v in reversed(it["versions"])
            ]
            return json_resp({"value": vals})
        if m == "GET" and "/versions/" in url and url.endswith("/content"):
            iid = url[len(f"{_OD_API}/drive/items/") :].split("/", 1)[0]
            vid = url.split("/versions/", 1)[1].split("/", 1)[0]
            it = self._by_id(iid)
            for v in it["versions"]:
                if v["id"] == vid:
                    return bytes_resp(v["content"])
            return empty_resp(404)
        if m == "GET" and url.endswith("/content"):
            iid = url[len(f"{_OD_API}/drive/items/") : -len("/content")]
            it = self._by_id(iid)
            return bytes_resp(it["versions"][-1]["content"])
        if m == "DELETE" and "/drive/items/" in url:
            iid = url[len(f"{_OD_API}/drive/items/") :]
            for name, it in list(self.items.items()):
                if it["id"] == iid:
                    del self.items[name]
            return empty_resp(204)
        raise AssertionError(f"OneDriveFake unhandled {m} {url}")


# --- Dropbox stateful fake -------------------------------------------------- #

_DBX_RPC = dropbox_mod._RPC
_DBX_CONTENT = dropbox_mod._CONTENT


class DropboxFake:
    """A stateful Dropbox v2 emulator (409 = not found)."""

    def __init__(self) -> None:
        self.files: Dict[str, List[Dict[str, Any]]] = {}  # path -> [{rev,size,content}]
        self._rev = 0

    def __call__(self, rec: RecordedRequest) -> HttpResponse:
        m, url = rec.method, rec.url
        if m == "POST" and url == f"{_DBX_CONTENT}/files/upload":
            arg = json.loads(rec.headers["Dropbox-API-Arg"])
            path = arg["path"]
            blob = bytes(rec.body or b"")
            self._rev += 1
            rev = f"rev{self._rev}"
            self.files.setdefault(path, []).append(
                {"rev": rev, "size": len(blob), "content": blob}
            )
            return json_resp({"rev": rev, "size": len(blob)})
        if m == "POST" and url == f"{_DBX_CONTENT}/files/download":
            arg = json.loads(rec.headers["Dropbox-API-Arg"])
            path = arg["path"]
            if path.startswith("rev:"):
                rev = path[len("rev:") :]
                for revs in self.files.values():
                    for r in revs:
                        if r["rev"] == rev:
                            return bytes_resp(r["content"])
                return empty_resp(409)
            revs = self.files.get(path)
            if not revs:
                return empty_resp(409)
            return bytes_resp(revs[-1]["content"])
        if m == "POST" and url == f"{_DBX_RPC}/files/list_revisions":
            arg = json.loads((rec.body or b"{}").decode("utf-8"))
            revs = self.files.get(arg["path"])
            if not revs:
                return empty_resp(409)
            entries = [{"rev": r["rev"], "size": r["size"]} for r in reversed(revs)]
            return json_resp({"entries": entries})
        if m == "POST" and url == f"{_DBX_RPC}/files/delete_v2":
            arg = json.loads((rec.body or b"{}").decode("utf-8"))
            path = arg["path"]
            if path in self.files:
                del self.files[path]
                return json_resp({"metadata": {}})
            return empty_resp(409)
        raise AssertionError(f"DropboxFake unhandled {m} {url}")


# --- factories -------------------------------------------------------------- #

_OAUTH = {
    "drive": DRIVE_OAUTH,
    "onedrive": ONEDRIVE_OAUTH,
    "dropbox": DROPBOX_OAUTH,
}
_ADAPTER = {
    "drive": DriveAdapter,
    "onedrive": OneDriveAdapter,
    "dropbox": DropboxAdapter,
}
_FAKE = {
    "drive": DriveFake,
    "onedrive": OneDriveFake,
    "dropbox": DropboxFake,
}


def make_fake(provider: str) -> Handler:
    """Return a fresh stateful fake handler for ``provider``."""
    return _FAKE[provider]()


def make_provider_auth(
    provider: str,
    *,
    token: Optional[str] = "access-tok-1",
    token_transport: Optional[Callable] = None,
) -> ProviderAuth:
    """Build a real :class:`ProviderAuth` with an injected (network-free) transport.

    When ``token`` is set it is preset as the in-memory access token so the happy
    path never touches the keyring; ``token_transport`` (injected) replaces the real
    HTTP token endpoint so refresh stays network-free.
    """
    config = _OAUTH[provider]("public-client-id-123")
    transport = token_transport or (
        lambda url, form: {"access_token": "refreshed-tok-2", "refresh_token": "rt"}
    )
    auth = ProviderAuth(provider, "user@example.com", config, token_transport=transport)
    if token is not None:
        auth._access_token = token
    return auth


def make_adapter(
    provider: str,
    http: Any,
    *,
    auth: Optional[ProviderAuth] = None,
) -> Any:
    """Construct the ``provider`` adapter bound to the mock ``http`` + a test auth."""
    return _ADAPTER[provider](auth or make_provider_auth(provider), http=http)
