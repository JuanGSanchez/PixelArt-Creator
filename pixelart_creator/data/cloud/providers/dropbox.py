"""Dropbox v2 real cloud adapter — credential-gated, out of CI (zero Qt, S11).

Phase-10 Slice A tail (ADR-0026 §1/§2; spec REQ-P10-DATA-001/-002/-003/-007/-008;
Researcher §1.1/§1.2). A real :class:`~pixelart_creator.data.cloud.port.CloudPort` over
the Dropbox v2 HTTP API, isolated behind the injectable
:class:`~pixelart_creator.data.cloud.providers._http.HttpClient` seam (mock-testable by
AGT-04; live-gated under ``cloud_live``).

Storage model: each project's ``.pixproj`` is one file at ``/{project_id}.pixproj``; a
separate ``/{project_id}.recovery`` file backs the recovery slot. Dropbox
**``files/list_revisions``** IS the version history, keyed by the immutable ``rev``;
each ``files/upload`` (``mode=overwrite``) creates a new ``rev``. Change tracking is the
folder ``list_folder`` cursor, surfaced only as an opaque :class:`Cursor`. Capability
model (Researcher §1.2): Dropbox has **no named/pinned revisions**, **no per-revision
delete**, a hard **revision-count cap of 100** (``max_versions_per_call``), a
**folder-scoped** change cursor, and ``rev``-based optimistic concurrency — surfaced via
:class:`CloudCapabilities`, never leaked (REQ-P10-DATA-007). No Dropbox/``urllib`` type
or field name escapes this module. Dropbox reports a missing path as HTTP ``409``, which
this adapter maps to "absent" (empty history / ``None`` recovery).
"""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple

from pixelart_creator.data.cloud.port import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
)
from pixelart_creator.data.cloud.providers._http import (
    HttpClient,
    HttpError,
    HttpResponse,
    decode_json,
)
from pixelart_creator.data.cloud.providers.base import (
    BaseProviderAdapter,
    ProviderAuth,
    build_versions,
)
from pixelart_creator.logic.constants import MAX_CLOUD_VERSIONS
from pixelart_creator.logic.version_history import CloudVersion

__all__ = ["DropboxAdapter", "DROPBOX_OAUTH"]

_RPC = "https://api.dropboxapi.com/2"
_CONTENT = "https://content.dropboxapi.com/2"
#: Dropbox reports a not-found path with HTTP 409 (a routing/endpoint error body).
_NOT_FOUND_STATUS = 409

#: The provider key used for the keyring service name (``cloud.token_store``).
PROVIDER = "dropbox"

#: Grounded Dropbox OAuth endpoints (Researcher §2). The public client id (app key) is
#: supplied by the caller; no secret is embedded here.
_AUTHORIZE = "https://www.dropbox.com/oauth2/authorize"
_TOKEN = "https://api.dropboxapi.com/oauth2/token"
DROPBOX_SCOPE = "files.content.read files.content.write"


def DROPBOX_OAUTH(client_id: str) -> "Any":  # noqa: N802 - factory-style helper
    """Return the Dropbox :class:`~...providers.base.OAuthConfig` for ``client_id``."""
    from pixelart_creator.data.cloud.providers.base import OAuthConfig

    return OAuthConfig(
        client_id=client_id,
        authorization_endpoint=_AUTHORIZE,
        token_endpoint=_TOKEN,
        scope=DROPBOX_SCOPE,
        device_endpoint=None,  # Dropbox does not offer the RFC 8628 device grant
    )


class DropboxAdapter(BaseProviderAdapter):
    """A real Dropbox v2 :class:`CloudPort` (credential-gated, out of CI)."""

    def __init__(
        self, auth: ProviderAuth, *, http: Optional[HttpClient] = None
    ) -> None:
        """Bind to a Dropbox :class:`ProviderAuth` and the injectable HTTP client."""
        super().__init__(auth, http=http)

    @staticmethod
    def _version_path(project_id: str) -> str:
        return f"/{project_id}.pixproj"

    @staticmethod
    def _recovery_path(project_id: str) -> str:
        return f"/{project_id}.recovery"

    # -- transport helpers ------------------------------------------------- #

    def _rpc(self, endpoint: str, arg: Any) -> HttpResponse:
        """POST a JSON RPC body to ``{_RPC}/{endpoint}``."""
        return self._request(
            "POST",
            f"{_RPC}/{endpoint}",
            headers={"Content-Type": "application/json"},
            body=json.dumps(arg).encode("utf-8"),
        )

    def _content_upload(self, path: str, blob: bytes) -> None:
        """Upload ``blob`` to ``path`` (``mode=overwrite`` — new ``rev``)."""
        self._request(
            "POST",
            f"{_CONTENT}/files/upload",
            headers={
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": json.dumps({"path": path, "mode": "overwrite"}),
            },
            body=bytes(blob),
        )

    def _content_download(self, path: str) -> bytes:
        """Download the bytes at ``path`` (accepts a ``rev:{rev}`` path)."""
        response = self._request(
            "POST",
            f"{_CONTENT}/files/download",
            headers={"Dropbox-API-Arg": json.dumps({"path": path})},
            body=b"",
        )
        return response.body

    # -- CloudPort verbs --------------------------------------------------- #

    def put(
        self,
        project_id: str,
        blob: bytes,
        *,
        parent_version: Optional[str] = None,
    ) -> CloudVersion:
        """Store a new ``.pixproj`` revision; return the new :class:`CloudVersion`."""
        if not isinstance(blob, (bytes, bytearray)):
            raise CloudError(f"blob must be bytes, got {type(blob).__name__}")
        self._content_upload(self._version_path(project_id), bytes(blob))
        return self.latest(project_id)

    def get(self, project_id: str, version_id: str) -> bytes:
        """Fetch a specific revision's raw ``.pixproj`` bytes (validated by caller)."""
        try:
            return self._content_download(f"rev:{version_id}")
        except HttpError as exc:
            if exc.status == _NOT_FOUND_STATUS:
                raise CloudError(
                    f"unknown version {version_id!r} for project {project_id!r}"
                ) from exc
            raise

    def list_versions(self, project_id: str) -> Tuple[CloudVersion, ...]:
        """Return the ordered revision history (oldest first, ≤ 100, deterministic)."""
        try:
            response = self._rpc(
                "files/list_revisions",
                {
                    "path": self._version_path(project_id),
                    "mode": "path",
                    "limit": MAX_CLOUD_VERSIONS,
                },
            )
        except HttpError as exc:
            if exc.status == _NOT_FOUND_STATUS:
                return ()
            raise
        data = decode_json(response)
        entries_raw = data.get("entries", [])
        if not isinstance(entries_raw, list):
            raise CloudDataError("Dropbox 'entries' field must be a list")
        # Dropbox returns revisions newest-first; reverse to the port's ascending order.
        entries = [
            (self._require_field(e, "rev"), int(e.get("size", 0)))
            for e in reversed(entries_raw)
        ]
        return build_versions(entries)

    def latest(self, project_id: str) -> CloudVersion:
        """Return the most recent revision (``CloudError`` if none)."""
        versions = self.list_versions(project_id)
        if not versions:
            raise CloudError(f"no versions for project {project_id!r}")
        return versions[-1]

    def delete(self, project_id: str) -> None:
        """Delete the ``.pixproj`` + recovery file (``CloudError`` if neither)."""
        deleted = False
        for path in (self._version_path(project_id), self._recovery_path(project_id)):
            try:
                self._rpc("files/delete_v2", {"path": path})
                deleted = True
            except HttpError as exc:
                if exc.status != _NOT_FOUND_STATUS:
                    raise
        if not deleted:
            raise CloudError(f"unknown project {project_id!r}")

    def put_recovery(self, project_id: str, blob: bytes) -> None:
        """Store the working ``.pixproj`` to the distinct recovery file."""
        if not isinstance(blob, (bytes, bytearray)):
            raise CloudError(f"blob must be bytes, got {type(blob).__name__}")
        self._content_upload(self._recovery_path(project_id), bytes(blob))

    def get_recovery(self, project_id: str) -> Optional[bytes]:
        """Return the recovery file's bytes, or ``None`` if none exists."""
        try:
            return self._content_download(self._recovery_path(project_id))
        except HttpError as exc:
            if exc.status == _NOT_FOUND_STATUS:
                return None
            raise

    def capabilities(self) -> CloudCapabilities:
        """Return Dropbox's normalized capability model (Researcher §1.2)."""
        return CloudCapabilities(
            supports_named_revisions=False,
            supports_revision_delete=False,
            max_versions_per_call=MAX_CLOUD_VERSIONS,  # Dropbox limit range [1, 100]
            change_feed_scope="drive",  # list_folder cursor is folder-scoped
            supports_optimistic_concurrency=True,  # rev-based (mode=update)
        )
