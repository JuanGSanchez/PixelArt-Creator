# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Real, credential-gated cloud provider adapters (zero Qt, S11) — Phase-10 Slice A.

The out-of-CI tail of the cloud port: real Google Drive / OneDrive (Microsoft Graph) /
Dropbox adapters that implement the SAME
:class:`~pixelart_creator.data.cloud.port.CloudPort` as the CI-tested
:class:`~pixelart_creator.data.cloud.fake_adapter.FakeCloudAdapter`, over the real
provider REST APIs. Each is built on:

* the injectable :class:`~pixelart_creator.data.cloud.providers._http.HttpClient` seam
  (a mock drives the ``CloudPort`` contract with no network/credentials —
  the test suite);
* the real OAuth Authorization-Code + PKCE-over-loopback flow (reusing the shipped
  ``cloud.auth`` PKCE core) and real OS-keyring token storage (reusing
  ``cloud.token_store`` — the REAL ``keyring`` path).

No provider SDK type, ``urllib`` type, token, or provider-specific exception leaks above
``data/cloud/`` (Article I / REQ-P10-DATA-007). Live end-to-end verification is
credential-/network-gated under the ``cloud_live`` pytest marker (CL-B2), skipped by
default in CI.
"""

from pixelart_creator.data.cloud.providers._http import (
    HttpClient,
    HttpError,
    HttpResponse,
    UrllibHttpClient,
)
from pixelart_creator.data.cloud.providers.base import (
    BaseProviderAdapter,
    OAuthConfig,
    ProviderAuth,
)
from pixelart_creator.data.cloud.providers.drive import DRIVE_OAUTH, DriveAdapter
from pixelart_creator.data.cloud.providers.dropbox import DROPBOX_OAUTH, DropboxAdapter
from pixelart_creator.data.cloud.providers.onedrive import (
    ONEDRIVE_OAUTH,
    OneDriveAdapter,
)

__all__ = [
    "HttpClient",
    "HttpResponse",
    "HttpError",
    "UrllibHttpClient",
    "OAuthConfig",
    "ProviderAuth",
    "BaseProviderAdapter",
    "DriveAdapter",
    "DRIVE_OAUTH",
    "OneDriveAdapter",
    "ONEDRIVE_OAUTH",
    "DropboxAdapter",
    "DROPBOX_OAUTH",
]
