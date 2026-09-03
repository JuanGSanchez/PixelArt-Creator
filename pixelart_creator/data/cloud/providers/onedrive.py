# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""OneDrive (Microsoft Graph) real cloud adapter — credential-gated, out of CI.

Zero Qt (S11). Phase-10 Slice A tail (ADR-0026 §1/§2; spec REQ-P10-DATA-001/-002/-003/
-007/-008). A real
:class:`~pixelart_creator.data.cloud.port.CloudPort` over the Microsoft Graph OneDrive
API, isolated behind the injectable
:class:`~pixelart_creator.data.cloud.providers._http.HttpClient` seam (mock-testable by
the test suite; live-gated under ``cloud_live``).

Storage model: each project's ``.pixproj`` is one driveItem in the per-app special
folder (``/drive/special/approot``), named ``{project_id}.pixproj``; a separate
``{project_id}.recovery`` item backs the recovery slot. Graph driveItem **versions**
(``/versions``) ARE the version history; each content ``PUT`` creates a new version.
Change tracking is the driveItem ``delta`` feed, surfaced only as an opaque
:class:`Cursor`. Capability model: Graph versions are **auto-only**
(no naming/pin), **individual versions cannot be deleted**, it uses ETag/``If-Match``
optimistic concurrency, and the ``delta`` change feed is **drive-scoped** — surfaced via
:class:`CloudCapabilities`, never leaked (REQ-P10-DATA-007). No Graph/``urllib`` type or
field name escapes this module.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from pixelart_creator.data.cloud.port import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
)
from pixelart_creator.data.cloud.providers._http import (
    HttpClient,
    HttpError,
    decode_json,
)
from pixelart_creator.data.cloud.providers.base import (
    BaseProviderAdapter,
    ProviderAuth,
    build_versions,
)
from pixelart_creator.logic.version_history import CloudVersion

__all__ = ["OneDriveAdapter", "ONEDRIVE_OAUTH"]

_API = "https://graph.microsoft.com/v1.0"
_APPROOT = f"{_API}/drive/special/approot"

#: The provider key used for the keyring service name (``cloud.token_store``).
PROVIDER = "onedrive"

#: Grounded Microsoft identity OAuth endpoints. The public client id is
#: supplied by the caller; no secret is embedded here.
_AUTHORIZE = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
_DEVICE = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"
#: ``offline_access`` is required to receive a refresh token.
ONEDRIVE_SCOPE = "offline_access Files.ReadWrite.AppFolder"


def ONEDRIVE_OAUTH(client_id: str) -> "Any":  # noqa: N802 - factory-style helper
    """Return the OneDrive :class:`~...providers.base.OAuthConfig` for ``client_id``."""
    from pixelart_creator.data.cloud.providers.base import OAuthConfig

    return OAuthConfig(
        client_id=client_id,
        authorization_endpoint=_AUTHORIZE,
        token_endpoint=_TOKEN,
        scope=ONEDRIVE_SCOPE,
        device_endpoint=_DEVICE,
    )


class OneDriveAdapter(BaseProviderAdapter):
    """A real Microsoft Graph OneDrive :class:`CloudPort` (credential-gated, no CI)."""

    def __init__(
        self, auth: ProviderAuth, *, http: Optional[HttpClient] = None
    ) -> None:
        """Bind to a OneDrive :class:`ProviderAuth` and the injectable HTTP client."""
        super().__init__(auth, http=http)
        self._item_ids: Dict[str, str] = {}

    @staticmethod
    def _version_name(project_id: str) -> str:
        return f"{project_id}.pixproj"

    @staticmethod
    def _recovery_name(project_id: str) -> str:
        return f"{project_id}.recovery"

    def _resolve_item_id(self, name: str) -> Optional[str]:
        """Return the approot driveItem id for ``name``, or ``None`` if it is absent."""
        cached = self._item_ids.get(name)
        if cached is not None:
            return cached
        try:
            data = self._get_json(f"{_APPROOT}:/{name}")
        except HttpError as exc:
            if exc.status == 404:
                return None
            raise
        item_id = self._require_field(data, "id")
        if not isinstance(item_id, str) or not item_id:
            raise CloudDataError(f"Graph driveItem id malformed: {item_id!r}")
        self._item_ids[name] = item_id
        return item_id

    def _upload(self, name: str, blob: bytes) -> str:
        """PUT content to the approot path (create or new version); return item id."""
        response = self._request(
            "PUT",
            f"{_APPROOT}:/{name}:/content",
            headers={"Content-Type": "application/octet-stream"},
            body=bytes(blob),
        )
        item_id = self._require_field(decode_json(response), "id")
        if not isinstance(item_id, str) or not item_id:
            raise CloudDataError(f"Graph upload returned malformed id: {item_id!r}")
        self._item_ids[name] = item_id
        return item_id

    # -- CloudPort verbs --------------------------------------------------- #

    def put(
        self,
        project_id: str,
        blob: bytes,
        *,
        parent_version: Optional[str] = None,
    ) -> CloudVersion:
        """Store a new ``.pixproj`` version; return the new :class:`CloudVersion`."""
        if not isinstance(blob, (bytes, bytearray)):
            raise CloudError(f"blob must be bytes, got {type(blob).__name__}")
        self._upload(self._version_name(project_id), bytes(blob))
        return self.latest(project_id)

    def get(self, project_id: str, version_id: str) -> bytes:
        """Fetch a specific version's raw ``.pixproj`` bytes (validated by caller)."""
        item_id = self._resolve_item_id(self._version_name(project_id))
        if item_id is None:
            raise CloudError(f"unknown project {project_id!r}")
        response = self._request(
            "GET", f"{_API}/drive/items/{item_id}/versions/{version_id}/content"
        )
        return response.body

    def list_versions(self, project_id: str) -> Tuple[CloudVersion, ...]:
        """Return the ordered version history (oldest first, deterministic)."""
        item_id = self._resolve_item_id(self._version_name(project_id))
        if item_id is None:
            return ()
        data = self._get_json(f"{_API}/drive/items/{item_id}/versions")
        values = data.get("value", [])
        if not isinstance(values, list):
            raise CloudDataError("Graph versions 'value' field must be a list")
        # Graph returns versions newest-first; reverse to the port's ascending order.
        entries = [
            (self._require_field(v, "id"), int(v.get("size", 0)))
            for v in reversed(values)
        ]
        return build_versions(entries)

    def latest(self, project_id: str) -> CloudVersion:
        """Return the most recent version (``CloudError`` if none)."""
        versions = self.list_versions(project_id)
        if not versions:
            raise CloudError(f"no versions for project {project_id!r}")
        return versions[-1]

    def delete(self, project_id: str) -> None:
        """Delete the project's driveItem and recovery item (all versions)."""
        deleted = False
        for name in (self._version_name(project_id), self._recovery_name(project_id)):
            item_id = self._resolve_item_id(name)
            if item_id is not None:
                self._request("DELETE", f"{_API}/drive/items/{item_id}")
                self._item_ids.pop(name, None)
                deleted = True
        if not deleted:
            raise CloudError(f"unknown project {project_id!r}")

    def put_recovery(self, project_id: str, blob: bytes) -> None:
        """Store the working ``.pixproj`` to the distinct recovery item."""
        if not isinstance(blob, (bytes, bytearray)):
            raise CloudError(f"blob must be bytes, got {type(blob).__name__}")
        self._upload(self._recovery_name(project_id), bytes(blob))

    def get_recovery(self, project_id: str) -> Optional[bytes]:
        """Return the recovery item's bytes, or ``None`` if none exists."""
        item_id = self._resolve_item_id(self._recovery_name(project_id))
        if item_id is None:
            return None
        response = self._request("GET", f"{_API}/drive/items/{item_id}/content")
        return response.body

    def capabilities(self) -> CloudCapabilities:
        """Return OneDrive's normalized capability model."""
        return CloudCapabilities(
            supports_named_revisions=False,  # Graph versions are auto-only
            supports_revision_delete=False,  # individual versions cannot be deleted
            max_versions_per_call=None,
            change_feed_scope="drive",  # driveItem delta is drive-scoped
            supports_optimistic_concurrency=True,  # ETag / If-Match
        )
