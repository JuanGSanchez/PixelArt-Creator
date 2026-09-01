# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""OS-keyring API-key isolation for LLM providers — zero Qt (S11).

Phase-14 Slice 14B (ADR-0040 §5; spec REQ-P14-DATA-003/-006, Article VII §3). Wraps
the OS-managed ``keyring`` credential store (Windows Credential Locker / macOS
Keychain / Linux Secret Service), keyed ``pixelart-creator:assistant:{provider}`` with
the provider account id as the username. Provider API keys are acquired, stored, and
used **entirely inside** ``data/llm/`` — never in ``logic/`` or ``ui/``, never written
to a ``.pixproj`` or a log, never committed. The port exposes only a provider-agnostic
``is_configured`` notion; ``ui/`` never receives a raw key beyond entry.

**``keyring`` is a LAZY/OPTIONAL import.** It is imported *inside* the functions, not
at module load, so all of Slices 14A–14C (the tool-catalog, the assistant loop, the
value types) and the fake adapter import and run **without ``keyring`` installed**
(SC-D003-2) and the local gate stays clean. ``keyring`` becomes required only for the
(14D) real OpenAI-compatible / Anthropic adapters — declared by AGT-09 as the
``assistant_live`` optional extra (``keyring==25.7.0``, the ``cloud_live`` pin).
:func:`is_keyring_available` lets callers degrade gracefully.

**Mirrored, not reused (ADR-0040 §5).** This is modelled on
``data/cloud/token_store.py`` but is a *distinct* module: it keys under the
``assistant`` service namespace (not ``cloud``) and raises the LLM port's own
:class:`~pixelart_creator.data.llm.port.LLMError` family, keeping the two credential
surfaces independently installable and isolated (the same rationale as the distinct
``assistant_live`` extra). It shares the cloud store's lazy-import shape but no state.
"""

from __future__ import annotations

from typing import Any, Optional

from pixelart_creator.data.llm.port import LLMError

__all__ = [
    "TokenStoreError",
    "SERVICE_NAME_TEMPLATE",
    "service_name",
    "is_keyring_available",
    "store_token",
    "load_token",
    "delete_token",
]

#: Keyring service-name template; formatted with the provider name (ADR-0040 §5).
#: DISTINCT from the cloud store's ``pixelart-creator:cloud:{provider}`` — the two
#: credential surfaces never collide.
SERVICE_NAME_TEMPLATE = "pixelart-creator:assistant:{provider}"


class TokenStoreError(LLMError):
    """Raised on a token-store failure (keyring missing / provider / backend error)."""


def _load_keyring() -> Any:
    """Import ``keyring`` lazily; raise :class:`TokenStoreError` if unavailable.

    Keeping the import inside the call site is what lets Slices 14A–14C + the fake
    adapter run without the ``keyring`` package installed (only the 14D live path needs
    it).
    """
    try:
        import keyring  # noqa: PLC0415 - intentional lazy/optional import (14B)
    except ImportError as exc:  # pragma: no cover - exercised only without keyring
        raise TokenStoreError(
            "the 'keyring' package is required for assistant API-key storage but is "
            "not installed; it is a dependency of the real LLM provider adapters "
            "(the 'assistant_live' extra)"
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
    """Return the keyring service name for ``provider`` (ADR-0040 §5 keying)."""
    return SERVICE_NAME_TEMPLATE.format(provider=_require_str(provider, "provider"))


def store_token(provider: str, account: str, token: str) -> None:
    """Store an API ``token`` for ``(provider, account)`` in the OS keyring.

    The key never leaves ``data/llm/`` — it is written only to the OS credential store,
    never to a ``.pixproj``, a log, or any committed artefact (Article VII §3).
    """
    account = _require_str(account, "account")
    token = _require_str(token, "token")
    keyring = _load_keyring()
    try:
        keyring.set_password(service_name(provider), account, token)
    except Exception as exc:  # noqa: BLE001 - normalise any keyring backend error
        raise TokenStoreError(f"failed to store token: {exc}") from exc


def load_token(provider: str, account: str) -> Optional[str]:
    """Return the stored API key for ``(provider, account)``, or ``None`` if absent."""
    account = _require_str(account, "account")
    keyring = _load_keyring()
    try:
        return keyring.get_password(service_name(provider), account)
    except Exception as exc:  # noqa: BLE001 - normalise any keyring backend error
        raise TokenStoreError(f"failed to load token: {exc}") from exc


def delete_token(provider: str, account: str) -> None:
    """Delete the stored API key for ``(provider, account)`` (idempotent)."""
    account = _require_str(account, "account")
    keyring = _load_keyring()
    try:
        keyring.delete_password(service_name(provider), account)
    except Exception as exc:  # noqa: BLE001 - includes "no such password"; idempotent
        # Deleting an absent credential is not an error for our purposes.
        if exc.__class__.__name__ == "PasswordDeleteError":
            return
        raise TokenStoreError(f"failed to delete token: {exc}") from exc
