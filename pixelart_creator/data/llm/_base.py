# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Shared credential-gating + config base for the real LLM adapters (private).

Phase-14 Slice 14D (skill ``llm-adapter-normalization`` step 5; ADR-0040 §5). Both real
adapters share the same non-secret configuration (provider name, base URL, model,
timeout, retry budget) and the same credential posture: the API key is pulled from the
OS keyring via :mod:`pixelart_creator.data.llm.token_store` **lazily, at request time**,
never at import or construction — so importing ``data/llm`` needs no network and no key,
and construction is cheap (REQ-P14-DATA-006). ``is_configured`` is key-present (+ an
endpoint); a missing key/endpoint degrades to a clear "not configured" state rather than
crashing, and a ``respond`` attempt without them raises
:class:`~pixelart_creator.data.llm.port.LLMNotConfiguredError`.

**The key is never logged** and never surfaced above the port. Module-private.
"""

from __future__ import annotations

from typing import Optional

from pixelart_creator.data.llm.port import (
    LLMNotConfiguredError,
    LLMPort,
)
from pixelart_creator.data.llm.token_store import TokenStoreError, load_token
from pixelart_creator.logic.constants import (
    ASSISTANT_REQUEST_MAX_RETRIES,
    ASSISTANT_REQUEST_TIMEOUT_S,
)

#: Default keyring account (username) the key is stored/loaded under for a single-user
#: install. The keyring service namespace is per-provider
#: (``pixelart-creator:assistant:{provider}``); the account distinguishes multiple
#: keys for one provider (a 14E/14F concern). Module-local vocabulary, not a numeric.
_DEFAULT_ACCOUNT = "default"


class _HTTPLLMAdapter(LLMPort):
    """Shared base for the real stdlib-``urllib`` adapters (credential + config only).

    Holds the non-secret configuration and the lazy credential lookup; the concrete
    subclasses (the OpenAI-compatible adapter and the native-Anthropic translator)
    implement :meth:`~pixelart_creator.data.llm.port.LLMPort.respond` with their own
    wire mapping. Construction performs **no** network I/O and **no** keyring access.
    """

    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        model: str,
        account: str = _DEFAULT_ACCOUNT,
        timeout_s: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        """Store the non-secret configuration (no network, no keyring at construction).

        Args:
            provider: The keyring provider namespace segment
                (``pixelart-creator:assistant:{provider}``), e.g. ``"openai"``.
            base_url: The provider base URL; the concrete adapter appends its route.
            model: The provider model name sent on every request.
            account: The keyring account (username) the key is stored under.
            timeout_s: Per-request timeout, seconds; defaults to
                :data:`~pixelart_creator.logic.constants.ASSISTANT_REQUEST_TIMEOUT_S`.
            max_retries: Bounded retry count; defaults to
                :data:`~pixelart_creator.logic.constants.ASSISTANT_REQUEST_MAX_RETRIES`.
        """
        self._provider = str(provider)
        self._base_url = base_url.rstrip("/") if base_url else base_url
        self._model = str(model)
        self._account = str(account)
        self._timeout_s: float = (
            ASSISTANT_REQUEST_TIMEOUT_S if timeout_s is None else timeout_s
        )
        self._max_retries: int = (
            ASSISTANT_REQUEST_MAX_RETRIES if max_retries is None else max_retries
        )

    @property
    def provider(self) -> str:
        """The provider namespace segment (never a key)."""
        return self._provider

    def _load_key(self) -> Optional[str]:
        """Return the stored API key (lazy keyring read), or ``None`` if unavailable.

        A missing ``keyring`` backend (:class:`TokenStoreError`) or an absent key both
        degrade to ``None`` — the credential-optional posture (never a crash). The key
        is returned to the caller for outbound auth only; it is never logged.
        """
        try:
            return load_token(self._provider, self._account)
        except TokenStoreError:
            return None

    def is_configured(self) -> bool:
        """Whether an endpoint and an API key are both present (key never exposed)."""
        return bool(self._base_url) and bool(self._load_key())

    def _require_config(self) -> str:
        """Return the API key, raising :class:`LLMNotConfiguredError` if unconfigured.

        Raises:
            LLMNotConfiguredError: If no endpoint or no key is available (credential-
                optional — the caller should probe :meth:`is_configured` and degrade).
        """
        if not self._base_url:
            raise LLMNotConfiguredError("no provider endpoint is configured")
        key = self._load_key()
        if not key:
            raise LLMNotConfiguredError(
                f"no API key is configured for provider {self._provider!r}"
            )
        return key
