# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""In-app AI-assistant chat dock (REQ-P14-UI-001/-003/-004; Slice 14E).

A dockable PySide6 panel where the user converses with the model-agnostic assistant
and watches it drive the real, undoable action surface. It **drives the ``logic/``
agentic loop** through an injected
:class:`~pixelart_creator.logic.assistant.ChatBackend`
(a ``data/llm`` adapter) and **never talks to a provider directly** — no provider/HTTP
type appears here (REQ-P14-DATA-007). The turn runs off the GUI thread on the
:class:`~pixelart_creator.ui.assistant_worker.Assistant_Controller`, so a model
round-trip never freezes the 16 ms render loop (REQ-P14-UI-004).

Concerns kept here (presentation only, Article I / S11):

* a scrolling **transcript** (user + assistant + tool-result summaries) and a masked
  busy/streaming indicator;
* an **input** box + send (Enter or the Send button — keyboard-reachable, a11y);
* the **tiered-safety confirm surface**: on a destructive tool-call the controller
  raises a :class:`~pixelart_creator.logic.assistant.ConfirmationRequest`; this dock
  shows an explicit confirm/cancel dialog **naming the action** and answers the worker.
  It renders the logic gate's decision and **never relaxes it** — a reversible op
  auto-runs (no dialog); a dismissed dialog denies (a destructive op is never
  auto-approved). The dock does not classify anything itself;
* a **Configure…** affordance opening the provider/key dialog, and a graceful
  "not configured" state (no crash) prompting the user to configure a provider.

The applied edits are emitted via :attr:`Assistant_Dock.editsReady` for the host window
(which owns the tabs + undo stacks) to wrap in one
:class:`~pixelart_creator.ui.commands.AssistantCommand` and push — so an assistant edit
is exactly one undoable step. All user-visible strings are ``tr()``-wrapped and re-set
on ``QEvent.LanguageChange``; the dock renders correctly in both themes (it uses no
hard-coded colours — it inherits the role-based QSS theme).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.assistant import (
    ChatBackend,
    ConfirmationRequest,
    Conversation,
    Message,
    Role,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.ui.assistant_worker import Assistant_Controller, TurnOutcome
from pixelart_creator.ui.provider_config_dialog import Provider_Config_Dialog

__all__ = ["Assistant_Dock"]

#: Provider of the active document (``None`` when no document tab is open).
DocumentProvider = Callable[[], Optional[Document]]

#: Provider of the current chat backend (a configured ``data/llm`` adapter, or ``None``
#: when the user has not configured a provider). Probed fresh on each send so a config
#: change takes effect immediately; ``ui/`` never sees a provider/HTTP type.
BackendProvider = Callable[[], Optional[ChatBackend]]


class Assistant_Dock(QDockWidget):
    """The chat dock: transcript + input/send + tiered-confirm + config (UI-001)."""

    #: ``(commands, label)`` — the turn's ordered, unapplied reversible commands and a
    #: translatable undo label; the host wraps them in one ``AssistantCommand``.
    editsReady = Signal(object, str)

    def __init__(
        self,
        controller: Assistant_Controller,
        document_provider: DocumentProvider,
        backend_provider: BackendProvider,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the chat UI and wire it to the off-GUI-thread controller."""
        super().__init__(parent)
        self._controller = controller
        self._document_provider = document_provider
        self._backend_provider = backend_provider
        self._conversation = Conversation()
        #: How many transcript messages have already been rendered (render the tail).
        self._rendered = 0

        self._transcript = QTextEdit(self)
        self._transcript.setReadOnly(True)

        self._busy_bar = QProgressBar(self)
        self._busy_bar.setRange(0, 0)  # indeterminate ("streaming/working").
        self._busy_bar.setVisible(False)
        self._status_label = QLabel(self)

        self._input = QLineEdit(self)
        self._input.returnPressed.connect(self._on_send)
        self._send_button = QPushButton(self)
        self._send_button.setDefault(True)
        self._send_button.clicked.connect(self._on_send)
        self._configure_button = QPushButton(self)
        self._configure_button.clicked.connect(self._on_configure)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_button)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.addWidget(self._status_label, 1)
        status_row.addWidget(self._busy_bar)

        layout = QVBoxLayout()
        layout.addWidget(self._transcript, 1)
        layout.addLayout(status_row)
        layout.addLayout(input_row)
        layout.addWidget(self._configure_button)
        container = QWidget(self)
        container.setLayout(layout)
        self.setWidget(container)

        # Keyboard focus order: transcript → input → send → configure.
        self.setTabOrder(self._input, self._send_button)
        self.setTabOrder(self._send_button, self._configure_button)

        self._controller.confirmRequested.connect(self._on_confirm_requested)
        self._controller.turnReady.connect(self._on_turn_ready)
        self._controller.failed.connect(self._on_failed)
        self._controller.busyChanged.connect(self._on_busy_changed)

        self._retranslate()

    # -- send / loop drive ------------------------------------------------

    def _on_send(self) -> None:
        """Append the user's message and drive one bounded turn off the GUI thread."""
        if self._controller.is_busy():
            return
        text = self._input.text().strip()
        if not text:
            return
        backend = self._backend_provider()
        if backend is None or not backend.is_configured():
            self._append_status(
                self.tr(
                    "No AI provider is configured. Use Configure… to set an "
                    "endpoint and API key."
                )
            )
            return
        document = self._document_provider()
        if document is None:
            self._append_status(
                self.tr("Open a document before chatting with the assistant.")
            )
            return
        self._conversation = self._conversation.append(
            Message(role=Role.USER, content=text)
        )
        self._render_tail()
        self._input.clear()
        self._controller.submit(document, self._conversation, backend)

    def _on_turn_ready(self, outcome: object) -> None:
        """Render the assistant's turn and emit any undoable edits it produced."""
        if not isinstance(outcome, TurnOutcome):
            return
        self._conversation = outcome.conversation
        self._render_tail()
        if outcome.commands:
            self.editsReady.emit(outcome.commands, self.tr("Assistant edit"))

    def _on_failed(self, message: str) -> None:
        """Surface a turn error in the transcript (never swallowed)."""
        self._append_status(self.tr("Assistant error: {0}").format(message))

    # -- tiered-safety confirmation (GUI thread) --------------------------

    def _on_confirm_requested(self, token: int, request: object) -> None:
        """Ask the user to approve one destructive action; answer the worker.

        Renders the logic gate's decision — it names the exact action and offers an
        explicit confirm/cancel. It never relaxes the classification: it is only
        reached for a ``DESTRUCTIVE`` op, and a dismissed dialog denies (a destructive
        action is never auto-approved).
        """
        if not isinstance(request, ConfirmationRequest):
            self._controller.provide_confirmation(token, False)
            return
        name = request.tool_call.name
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(self.tr("Confirm assistant action"))
        box.setText(
            self.tr(
                'The assistant wants to run "{0}", which cannot be reliably '
                "undone. Allow it?"
            ).format(name)
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        approved = box.exec() == QMessageBox.StandardButton.Yes
        self._controller.provide_confirmation(token, approved)

    # -- config -----------------------------------------------------------

    def _on_configure(self) -> None:
        """Open the provider/key configuration dialog (masked key → OS keyring)."""
        dialog = Provider_Config_Dialog(self)
        if dialog.exec() == Provider_Config_Dialog.DialogCode.Accepted:
            self._append_status(self.tr("Provider configuration saved."))

    # -- busy indicator ---------------------------------------------------

    def _on_busy_changed(self, busy: bool) -> None:
        """Reflect the in-flight state: disable send + show the busy indicator."""
        self._busy_bar.setVisible(busy)
        self._send_button.setEnabled(not busy)
        self._input.setEnabled(not busy)
        self._status_label.setText(self.tr("Working…") if busy else "")

    # -- transcript rendering ---------------------------------------------

    def _render_tail(self) -> None:
        """Append transcript messages not yet rendered (user/assistant/tool)."""
        messages = self._conversation.messages
        for message in messages[self._rendered :]:
            self._render_message(message)
        self._rendered = len(messages)

    def _render_message(self, message: Message) -> None:
        if message.role is Role.USER:
            speaker = self.tr("You")
            body = message.content
        elif message.role is Role.ASSISTANT:
            speaker = self.tr("Assistant")
            body = message.content or self.tr("(taking an action…)")
        elif message.role is Role.TOOL:
            speaker = self.tr("Action")
            body = message.content
        else:  # Role.SYSTEM — not shown as a chat bubble.
            return
        self._transcript.append(f"{speaker}: {body}")

    def _append_status(self, text: str) -> None:
        """Append a dock-local status/error line to the transcript."""
        self._transcript.append(text)

    # -- teardown ---------------------------------------------------------

    def shutdown(self) -> None:
        """Tear the off-GUI-thread controller down deterministically (idempotent).

        Delegates to :meth:`Assistant_Controller.shutdown` so no worker thread or
        signal carrier survives into a later GC cycle (the xdist segfault guard). The
        host also folds the controller teardown into ``shutdown_prewarm``; calling both
        is safe (idempotent).
        """
        self._controller.shutdown()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Stop the worker before the dock closes (no dangling thread/carrier)."""
        self.shutdown()
        super().closeEvent(event)

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("AI Assistant"))
        self.setAccessibleName(self.tr("AI assistant chat"))
        self._transcript.setAccessibleName(self.tr("Assistant conversation"))
        self._input.setAccessibleName(self.tr("Message to the assistant"))
        self._input.setPlaceholderText(self.tr("Ask the assistant to edit…"))
        self._send_button.setText(self.tr("Send"))
        self._send_button.setAccessibleName(self.tr("Send message"))
        self._configure_button.setText(self.tr("Configure…"))
        self._configure_button.setAccessibleName(self.tr("Configure AI provider"))
        self._busy_bar.setAccessibleName(self.tr("Assistant working indicator"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the dock strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
