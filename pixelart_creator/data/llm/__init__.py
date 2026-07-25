"""Model-agnostic LLM subpackage (zero Qt, S11) — Phase-14 Slice 14B.

A normal ``data/`` subpackage (governed by the existing ``data`` layering rule: no Qt,
no ``ui/`` import) mirroring ``data/cloud/``. Exposes the one provider-agnostic
:class:`~pixelart_creator.data.llm.port.LLMPort`, its ``LLMError``
family, and the CI-tested deterministic
:class:`~pixelart_creator.data.llm.fake_adapter.FakeLLMAdapter`. The lazy/optional
OS-keyring API-key store is :mod:`pixelart_creator.data.llm.token_store` (imported on
demand — see its module docstring — not re-exported here, so importing this package
never touches ``keyring``). No provider SDK type, HTTP/credential type, or
provider-specific exception leaks above this package (REQ-P14-DATA-007); keys live only
inside this package (REQ-P14-DATA-003/-006). The real stdlib-``urllib`` adapters (Slice
14D) — the OpenAI-compatible core (:class:`~pixelart_creator.data.llm.openai_compatible.
OpenAICompatibleAdapter`) and the native-Anthropic translator
(:class:`~pixelart_creator.data.llm.anthropic_translator.AnthropicTranslator`) — are
re-exported here for a single import site. Importing them touches **no** network and
**no** ``keyring`` (the key is read lazily, at ``respond`` time only), so importing this
package stays cheap and credential-optional.
"""

from pixelart_creator.data.llm.anthropic_translator import AnthropicTranslator
from pixelart_creator.data.llm.fake_adapter import FakeLLMAdapter
from pixelart_creator.data.llm.openai_compatible import OpenAICompatibleAdapter
from pixelart_creator.data.llm.port import (
    LLMError,
    LLMNotConfiguredError,
    LLMPort,
    LLMResponseError,
)

__all__ = [
    "LLMPort",
    "LLMError",
    "LLMNotConfiguredError",
    "LLMResponseError",
    "FakeLLMAdapter",
    "OpenAICompatibleAdapter",
    "AnthropicTranslator",
]
