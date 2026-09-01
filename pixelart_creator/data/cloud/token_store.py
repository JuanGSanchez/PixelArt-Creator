# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""OS-keyring token isolation for cloud providers — zero Qt (S11).

Phase-10 Slice A (ADR-0026 §3; spec REQ-P10-DATA-008, CL-B3, Article VII §3). Wraps
the OS-managed ``keyring`` credential store (Windows Credential Locker / macOS
Keychain / Linux Secret Service), keyed ``pixelart-creator:cloud:{provider}`` with
the provider account id as the username. Provider tokens are acquired, stored, and
used **entirely inside** ``data/cloud/`` — never in ``logic/`` or ``ui/``, never
written to a ``.pixproj`` or a log, never committed. The port exposes only a
provider-agnostic ``is_connected`` notion; ``ui/`` never receives a raw token.

**``keyring`` is a LAZY/OPTIONAL import.** It is imported *inside* the functions, not
at module load, so all of Slice A (the port, the fake adapter, sync-state / autosave /
version-history models) imports and runs **without ``keyring`` installed** and the
local gate stays clean. ``keyring`` becomes a required dependency only for the (later,
out-of-Slice-A) real Drive/OneDrive/Dropbox adapters — flagged to AGT-09 as a manifest
dependency for that work. :func:`is_keyring_available` lets callers degrade gracefully.
"""

from __future__ import annotations

from typing import Any, Optional

from pixelart_creator.data.cloud.port import CloudError

__all__ = [
    "TokenStoreError",
    "SERVICE_NAME_TEMPLATE",
    "service_name",
    "is_keyring_available",
    "store_token",
    "load_token",
    "delete_token",
]

#: Keyring service-name template; formatted with the provider name (CL-B3).
SERVICE_NAME_TEMPLATE = "pixelart-creator:cloud:{provider}"


class TokenStoreError(CloudError):
    """Raised on a token-store failure (keyring missing / provider / backend error)."""


def _load_keyring() -> Any:
    """Import ``keyring`` lazily; raise :class:`TokenStoreError` if unavailable.

    Keeping the import inside the call site is what lets Slice A run without the
    ``keyring`` package installed (only the real-adapter path needs it).
    """
    try:
        import keyring  # noqa: PLC0415 - intentional lazy/optional import (Slice A)
    except ImportError as exc:  # pragma: no cover - exercised only without keyring
        raise TokenStoreError(
            "the 'keyring' package is required for cloud token storage but is not "
            "installed; it is a dependency of the real cloud provider adapters"
        ) from exc
    return keyring


def is_keyring_available() -> bool:
    """Return whether the optional ``keyring`` backend can be imported."""
    try:
        import keyring  # noqa: F401, PLC0415 - availability probe only
    except ImportError:
        return False
    return True


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TokenStoreError(f"{name} must be a non-empty str, got {value!r}")
    return value


def service_name(provider: str) -> str:
    """Return the keyring service name for ``provider`` (the CL-B3 keying scheme)."""
    return SERVICE_NAME_TEMPLATE.format(provider=_require_str(provider, "provider"))


def store_token(provider: str, account: str, token: str) -> None:
    """Store ``token`` for ``(provider, account)`` in the OS keyring.

    Only a refresh token (and optionally a short-lived access token) should be
    stored; the token never leaves ``data/cloud/``.
    """
    account = _require_str(account, "account")
    token = _require_str(token, "token")
    keyring = _load_keyring()
    try:
        keyring.set_password(service_name(provider), account, token)
    except Exception as exc:  # noqa: BLE001 - normalise any keyring backend error
        raise TokenStoreError(f"failed to store token: {exc}") from exc


def load_token(provider: str, account: str) -> Optional[str]:
    """Return the stored token for ``(provider, account)``, or ``None`` if absent."""
    account = _require_str(account, "account")
    keyring = _load_keyring()
    try:
        return keyring.get_password(service_name(provider), account)
    except Exception as exc:  # noqa: BLE001 - normalise any keyring backend error
        raise TokenStoreError(f"failed to load token: {exc}") from exc


def delete_token(provider: str, account: str) -> None:
    """Delete the stored token for ``(provider, account)`` (idempotent)."""
    account = _require_str(account, "account")
    keyring = _load_keyring()
    try:
        keyring.delete_password(service_name(provider), account)
    except Exception as exc:  # noqa: BLE001 - includes "no such password"; idempotent
        # Deleting an absent credential is not an error for our purposes.
        if exc.__class__.__name__ == "PasswordDeleteError":
            return
        raise TokenStoreError(f"failed to delete token: {exc}") from exc
