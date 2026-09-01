# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Provider / endpoint / API-key configuration for the AI assistant (REQ-P14-UI-002).

Part of Phase 14, the AI-assistant phase. Lets the user pick a provider (an
OpenAI-compatible endpoint or native Anthropic), set the base URL + model,
and enter an API key — then constructs the
matching :class:`~pixelart_creator.data.llm.port.LLMPort` adapter behind the frozen,
provider-agnostic port. The app behaves identically regardless of provider (the port is
the seam); a missing/incomplete configuration degrades to a clear "not configured"
state (``is_configured() == False``) rather than a crash.

**Secret handling (Article VII §3, REQ-P14-UI-002).** The **non-secret** configuration
(provider / base URL / model) is persisted with :class:`~PySide6.QtCore.QSettings`
under this app's organisation/application identity. The **API key** is handed straight
to :mod:`pixelart_creator.data.llm.token_store` (the OS keyring) and is:

* **never** written to :class:`QSettings`, a ``.pixproj``, a log, or any committed
  artefact;
* entered in a **masked** field (:attr:`QLineEdit.EchoMode.Password`) and **never**
  shown back — the dialog does not read the stored key and clears the entry field after
  the hand-off, so ``ui/`` retains no raw key beyond entry.

Zero domain logic lives here (Article I / S11): the dialog collects values, delegates
persistence + credential storage, and constructs a ``data/llm`` adapter. All
user-visible strings are ``tr()``-wrapped and re-set on ``QEvent.LanguageChange``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.llm.anthropic_translator import AnthropicTranslator
from pixelart_creator.data.llm.openai_compatible import OpenAICompatibleAdapter
from pixelart_creator.data.llm.port import LLMPort
from pixelart_creator.data.llm.token_store import (
    TokenStoreError,
    is_keyring_available,
    store_token,
)

__all__ = [
    "PROVIDER_OPENAI",
    "PROVIDER_ANTHROPIC",
    "AssistantProviderConfig",
    "load_config",
    "save_config",
    "build_backend",
    "Provider_Config_Dialog",
]

#: Provider-kind identifiers. These double as the keyring service namespace segment
#: (``pixelart-creator:assistant:{provider}``) and the adapter's ``provider`` arg, so
#: the key stored here is the key the adapter loads. Module-local vocabulary
#: (ADR-0001), not a numeric constant.
PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"

#: The keyring account the single-user key is stored under (matches ``data/llm``'s
#: ``_DEFAULT_ACCOUNT`` so the adapter loads the same credential).
_ACCOUNT = "default"

#: :class:`QSettings` group + keys for the NON-SECRET configuration only.
_SETTINGS_GROUP = "assistant"
_KEY_PROVIDER = "provider"
_KEY_BASE_URL = "base_url"
_KEY_MODEL = "model"

#: Sensible default endpoints per provider kind (the user may override).
_DEFAULT_BASE_URLS = {
    PROVIDER_OPENAI: "https://api.openai.com/v1",
    PROVIDER_ANTHROPIC: "https://api.anthropic.com",
}


@dataclass(frozen=True)
class AssistantProviderConfig:
    """The non-secret assistant provider configuration (no key — Article VII).

    ``provider`` is a provider-kind identifier (:data:`PROVIDER_OPENAI` /
    :data:`PROVIDER_ANTHROPIC`); ``base_url`` + ``model`` are the endpoint + model the
    adapter sends. The API key is **never** part of this value — it lives only in the
    OS keyring (:mod:`pixelart_creator.data.llm.token_store`).
    """

    provider: str
    base_url: str
    model: str


def load_config() -> Optional[AssistantProviderConfig]:
    """Return the persisted non-secret config, or ``None`` if none is stored.

    Reads only the non-secret values from :class:`QSettings`; the key is never read
    from settings (it is not stored there). A wholly-empty store yields ``None`` (the
    "not configured" state the dock degrades to gracefully).
    """
    settings = QSettings()
    settings.beginGroup(_SETTINGS_GROUP)
    provider = str(settings.value(_KEY_PROVIDER, "") or "")
    base_url = str(settings.value(_KEY_BASE_URL, "") or "")
    model = str(settings.value(_KEY_MODEL, "") or "")
    settings.endGroup()
    if not provider and not base_url and not model:
        return None
    return AssistantProviderConfig(
        provider=provider or PROVIDER_OPENAI, base_url=base_url, model=model
    )


def save_config(config: AssistantProviderConfig) -> None:
    """Persist ONLY the non-secret config (provider / base URL / model).

    The API key is intentionally absent — it is stored in the OS keyring, never in
    :class:`QSettings` (Article VII §3).
    """
    settings = QSettings()
    settings.beginGroup(_SETTINGS_GROUP)
    settings.setValue(_KEY_PROVIDER, config.provider)
    settings.setValue(_KEY_BASE_URL, config.base_url)
    settings.setValue(_KEY_MODEL, config.model)
    settings.endGroup()


def build_backend(config: AssistantProviderConfig) -> LLMPort:
    """Construct the matching ``data/llm`` adapter for ``config`` (no network/keyring).

    Anthropic uses the native translator; everything else uses the OpenAI-compatible
    client. Construction is cheap — the key is read lazily from the keyring at request
    time — so a "not configured" adapter (no key/endpoint) is still safe to build and
    simply reports ``is_configured() == False``.
    """
    if config.provider == PROVIDER_ANTHROPIC:
        return AnthropicTranslator(
            provider=config.provider,
            base_url=config.base_url or _DEFAULT_BASE_URLS[PROVIDER_ANTHROPIC],
            model=config.model,
            account=_ACCOUNT,
        )
    return OpenAICompatibleAdapter(
        provider=config.provider,
        base_url=config.base_url or _DEFAULT_BASE_URLS[PROVIDER_OPENAI],
        model=config.model,
        account=_ACCOUNT,
    )


class Provider_Config_Dialog(QDialog):
    """Modal dialog to pick a provider + endpoint + model and enter an API key.

    On accept it persists the non-secret config (:func:`save_config`) and hands any
    entered key to the OS keyring (:func:`~pixelart_creator.data.llm.token_store`);
    it retains **no** raw key. Provider-agnostic; all strings ``tr()``-wrapped.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the fields, prefill the non-secret config, and leave the key blank."""
        super().__init__(parent)
        self.setModal(True)

        self._provider_combo = QComboBox(self)
        self._provider_combo.addItem("", PROVIDER_OPENAI)
        self._provider_combo.addItem("", PROVIDER_ANTHROPIC)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self._base_url_edit = QLineEdit(self)
        self._model_edit = QLineEdit(self)
        self._key_edit = QLineEdit(self)
        # The key field is ALWAYS masked and never pre-filled with a stored key.
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self._provider_label = QLabel(self)
        self._base_url_label = QLabel(self)
        self._model_label = QLabel(self)
        self._key_label = QLabel(self)
        self._hint_label = QLabel(self)
        self._hint_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow(self._provider_label, self._provider_combo)
        form.addRow(self._base_url_label, self._base_url_edit)
        form.addRow(self._model_label, self._model_edit)
        form.addRow(self._key_label, self._key_edit)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._hint_label)
        layout.addWidget(self._buttons)

        self._prefill()
        self._retranslate()

    # -- prefill / provider change ---------------------------------------

    def _prefill(self) -> None:
        """Load the non-secret config into the fields (never the key)."""
        config = load_config()
        if config is None:
            self._base_url_edit.setText(_DEFAULT_BASE_URLS[PROVIDER_OPENAI])
            return
        index = self._provider_combo.findData(config.provider)
        if index >= 0:
            self._provider_combo.setCurrentIndex(index)
        self._base_url_edit.setText(config.base_url)
        self._model_edit.setText(config.model)

    def _on_provider_changed(self, _index: int) -> None:
        """Offer the provider's default endpoint when the base URL is empty."""
        if not self._base_url_edit.text().strip():
            kind = self._provider_combo.currentData()
            self._base_url_edit.setText(_DEFAULT_BASE_URLS.get(str(kind), ""))

    # -- accept -----------------------------------------------------------

    def _on_accept(self) -> None:
        """Persist the non-secret config and hand any key to the OS keyring.

        The key is stored only in the keyring (never in :class:`QSettings`/logs), the
        entry field is cleared, and the dialog retains no raw key. A missing keyring
        backend surfaces a hint but still saves the non-secret config.
        """
        config = AssistantProviderConfig(
            provider=str(self._provider_combo.currentData()),
            base_url=self._base_url_edit.text().strip(),
            model=self._model_edit.text().strip(),
        )
        save_config(config)

        key = self._key_edit.text()
        # Clear the field immediately so no raw key lingers in the widget.
        self._key_edit.clear()
        if key:
            if not is_keyring_available():
                self._hint_label.setText(
                    self.tr(
                        "The OS keyring is unavailable; install the "
                        "'assistant_live' extra to store an API key. The "
                        "provider settings were saved."
                    )
                )
                return
            try:
                store_token(config.provider, _ACCOUNT, key)
            except TokenStoreError as exc:
                self._hint_label.setText(
                    self.tr("Could not store the API key: {0}").format(str(exc))
                )
                return
        self.accept()

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Configure AI Assistant Provider"))
        self.setAccessibleName(self.tr("AI assistant provider configuration"))
        self._provider_combo.setItemText(0, self.tr("OpenAI-compatible"))
        self._provider_combo.setItemText(1, self.tr("Anthropic (Claude)"))
        self._provider_combo.setAccessibleName(self.tr("Provider"))
        self._provider_label.setText(self.tr("Provider"))
        self._base_url_label.setText(self.tr("Endpoint URL"))
        self._base_url_edit.setAccessibleName(self.tr("Provider endpoint URL"))
        self._base_url_edit.setPlaceholderText(self.tr("https://…"))
        self._model_label.setText(self.tr("Model"))
        self._model_edit.setAccessibleName(self.tr("Model name"))
        self._model_edit.setPlaceholderText(self.tr("e.g. gpt-4o-mini"))
        self._key_label.setText(self.tr("API key"))
        self._key_edit.setAccessibleName(self.tr("API key (stored in the OS keyring)"))
        self._key_edit.setPlaceholderText(
            self.tr("Leave blank to keep the existing key")
        )
        self._hint_label.setText(
            self.tr(
                "The API key is stored only in your OS keyring — never in a "
                "project file or a log."
            )
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the dialog strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
