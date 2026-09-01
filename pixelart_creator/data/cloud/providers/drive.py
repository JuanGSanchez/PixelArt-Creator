# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Google Drive v3 real cloud adapter — credential-gated, out of CI (zero Qt, S11).

Phase-10 Slice A tail (ADR-0026 §1/§2; spec REQ-P10-DATA-001/-002/-003/-007/-008;
Researcher §1.1/§1.2). A real :class:`~pixelart_creator.data.cloud.port.CloudPort`
over the Drive v3 REST API, isolated behind the injectable
:class:`~pixelart_creator.data.cloud.providers._http.HttpClient` seam so its contract
conformance is testable with a mocked transport (AGT-04), while live verification is
**credential-/network-gated** under the ``cloud_live`` marker.

Storage model (grounded on Researcher §1): each project's ``.pixproj`` is one Drive
file in the hidden per-app ``appDataFolder`` space, named ``{project_id}.pixproj``; a
separate ``{project_id}.recovery`` file backs the autosave/recovery slot (distinct from
version history — REQ-P10-DATA-004). Drive **revisions** (``files.revisions``) ARE the
version history; each ``put`` creates a new revision of the content. Change tracking is
the drive-scoped Changes feed, surfaced only as an opaque :class:`Cursor`. Capability
model (Researcher §1.2): Drive supports **named/pinned revisions** (``keepForever``) and
**per-revision delete for binary files**, uses ETag/``If-Match`` optimistic concurrency,
and has a **drive-scoped** change feed — surfaced via :class:`CloudCapabilities`, never
leaked (REQ-P10-DATA-007). No Drive/``urllib`` type or field name escapes this module.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from pixelart_creator.data.cloud.port import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
)
from pixelart_creator.data.cloud.providers._http import HttpClient, decode_json
from pixelart_creator.data.cloud.providers.base import (
    BaseProviderAdapter,
    ProviderAuth,
    build_versions,
)
from pixelart_creator.logic.version_history import CloudVersion

__all__ = ["DriveAdapter", "DRIVE_OAUTH"]

_API = "https://www.googleapis.com/drive/v3"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_APP_SPACE = "appDataFolder"
_MULTIPART_BOUNDARY = "pixelart-creator-drive-boundary"

#: The provider key used for the keyring service name (``cloud.token_store``).
PROVIDER = "drive"

#: Grounded Drive OAuth endpoints (Researcher §2 / §Sources). The public client id is
#: supplied by the caller at construction — no secret is embedded here.
_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN = "https://oauth2.googleapis.com/token"
_DEVICE = "https://oauth2.googleapis.com/device/code"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.appdata"


def DRIVE_OAUTH(client_id: str) -> "Any":  # noqa: N802 - factory-style public helper
    """Return the Drive :class:`~...providers.base.OAuthConfig` for ``client_id``."""
    from pixelart_creator.data.cloud.providers.base import OAuthConfig

    return OAuthConfig(
        client_id=client_id,
        authorization_endpoint=_AUTHORIZE,
        token_endpoint=_TOKEN,
        scope=DRIVE_SCOPE,
        device_endpoint=_DEVICE,
    )


def _as_int(value: Any) -> int:
    """Coerce an untrusted Drive size field (str|int) to an int (Article VII)."""
    if isinstance(value, bool):
        raise CloudDataError(f"unexpected bool size field {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise CloudDataError(f"Drive size field must be an int/digit-str, got {value!r}")


def _multipart(metadata: Dict[str, Any], blob: bytes) -> Tuple[str, bytes]:
    """Build a Drive ``multipart/related`` create body (metadata + media)."""
    boundary = _MULTIPART_BOUNDARY
    head = (
        f"--{boundary}\r\n"
        "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    content_type = f"multipart/related; boundary={boundary}"
    return content_type, head + bytes(blob) + tail


class DriveAdapter(BaseProviderAdapter):
    """A real Google Drive v3 :class:`CloudPort` (credential-gated, out of CI)."""

    def __init__(
        self, auth: ProviderAuth, *, http: Optional[HttpClient] = None
    ) -> None:
        """Bind to a Drive :class:`ProviderAuth` and the injectable HTTP client."""
        super().__init__(auth, http=http)
        self._file_ids: Dict[str, str] = {}

    # -- name / id resolution --------------------------------------------- #

    @staticmethod
    def _version_name(project_id: str) -> str:
        return f"{project_id}.pixproj"

    @staticmethod
    def _recovery_name(project_id: str) -> str:
        return f"{project_id}.recovery"

    def _resolve(self, name: str) -> Optional[str]:
        """Return the appDataFolder file id for ``name``, or ``None`` if absent."""
        cached = self._file_ids.get(name)
        if cached is not None:
            return cached
        data = self._get_json(
            f"{_API}/files",
            params={
                "q": f"name = '{name}' and trashed = false",
                "spaces": _APP_SPACE,
                "fields": "files(id,name)",
            },
        )
        files = data.get("files")
        if not isinstance(files, list) or not files:
            return None
        file_id = self._require_field(files[0], "id")
        if not isinstance(file_id, str) or not file_id:
            raise CloudDataError(f"Drive file id malformed: {file_id!r}")
        self._file_ids[name] = file_id
        return file_id

    def _create_file(self, name: str, blob: bytes) -> str:
        """Create a new appDataFolder file with initial content; return its id."""
        content_type, body = _multipart({"name": name, "parents": [_APP_SPACE]}, blob)
        response = self._request(
            "POST",
            _UPLOAD,
            params={"uploadType": "multipart", "fields": "id"},
            headers={"Content-Type": content_type},
            body=body,
        )
        file_id = self._require_field(decode_json(response), "id")
        if not isinstance(file_id, str) or not file_id:
            raise CloudDataError(f"Drive create returned malformed id: {file_id!r}")
        self._file_ids[name] = file_id
        return file_id

    def _upload_content(self, file_id: str, blob: bytes) -> None:
        """PATCH new media onto ``file_id`` (creates a new revision)."""
        self._request(
            "PATCH",
            f"{_UPLOAD}/{file_id}",
            params={"uploadType": "media"},
            headers={"Content-Type": "application/octet-stream"},
            body=bytes(blob),
        )

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
        name = self._version_name(project_id)
        file_id = self._resolve(name)
        if file_id is None:
            self._create_file(name, bytes(blob))
        else:
            self._upload_content(file_id, bytes(blob))
        return self.latest(project_id)

    def get(self, project_id: str, version_id: str) -> bytes:
        """Fetch a specific revision's raw ``.pixproj`` bytes (validated by caller)."""
        file_id = self._resolve(self._version_name(project_id))
        if file_id is None:
            raise CloudError(f"unknown project {project_id!r}")
        response = self._request(
            "GET",
            f"{_API}/files/{file_id}/revisions/{version_id}",
            params={"alt": "media"},
        )
        return response.body

    def list_versions(self, project_id: str) -> Tuple[CloudVersion, ...]:
        """Return the ordered revision history (oldest first, deterministic)."""
        file_id = self._resolve(self._version_name(project_id))
        if file_id is None:
            return ()
        data = self._get_json(
            f"{_API}/files/{file_id}/revisions",
            params={"fields": "revisions(id,size,keepForever)"},
        )
        revisions = data.get("revisions", [])
        if not isinstance(revisions, list):
            raise CloudDataError("Drive revisions field must be a list")
        entries = [
            (self._require_field(rev, "id"), _as_int(rev.get("size", 0)))
            for rev in revisions
        ]
        return build_versions(entries)

    def latest(self, project_id: str) -> CloudVersion:
        """Return the most recent revision (``CloudError`` if none)."""
        versions = self.list_versions(project_id)
        if not versions:
            raise CloudError(f"no versions for project {project_id!r}")
        return versions[-1]

    def delete(self, project_id: str) -> None:
        """Delete the project's ``.pixproj`` file and recovery file (all revisions)."""
        deleted = False
        for name in (self._version_name(project_id), self._recovery_name(project_id)):
            file_id = self._resolve(name)
            if file_id is not None:
                self._request("DELETE", f"{_API}/files/{file_id}")
                self._file_ids.pop(name, None)
                deleted = True
        if not deleted:
            raise CloudError(f"unknown project {project_id!r}")

    def put_recovery(self, project_id: str, blob: bytes) -> None:
        """Store the working ``.pixproj`` to the distinct recovery file."""
        if not isinstance(blob, (bytes, bytearray)):
            raise CloudError(f"blob must be bytes, got {type(blob).__name__}")
        name = self._recovery_name(project_id)
        file_id = self._resolve(name)
        if file_id is None:
            self._create_file(name, bytes(blob))
        else:
            self._upload_content(file_id, bytes(blob))

    def get_recovery(self, project_id: str) -> Optional[bytes]:
        """Return the recovery file's bytes, or ``None`` if none exists."""
        file_id = self._resolve(self._recovery_name(project_id))
        if file_id is None:
            return None
        response = self._request(
            "GET", f"{_API}/files/{file_id}", params={"alt": "media"}
        )
        return response.body

    def capabilities(self) -> CloudCapabilities:
        """Return Drive's normalized capability model (Researcher §1.2)."""
        return CloudCapabilities(
            supports_named_revisions=True,  # keepForever pin
            supports_revision_delete=True,  # binary-content files only
            max_versions_per_call=None,  # Drive paginates; no hard per-call cap
            change_feed_scope="drive",  # Changes feed is drive-scoped
            supports_optimistic_concurrency=True,  # ETag / If-Match
        )
