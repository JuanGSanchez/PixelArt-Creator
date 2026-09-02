"""Phase-14 — AI-assistant chat dock UI/integration tests.

One pytest-qt test per acceptance criterion (``SC-UI-001-1`` ..
``SC-UI-006-1``), driven **headlessly** (offscreen) against the deterministic scripted
:class:`~pixelart_creator.data.llm.fake_adapter.FakeLLMAdapter` — **no network, no real
key, no real keyring**. Both themes are exercised automatically (the autouse ``theme``
fixture in ``testing/suites/ui/conftest.py`` parametrises every test over light + dark).

Coverage map:

* **SC-UI-001-1** — the dock drives the ``logic/`` agentic loop (never a provider), and
  renders user + assistant + tool-result transcript entries; ``busyChanged`` toggles;
  errors are surfaced, not swallowed.
* **SC-UI-003-1** [TIERED-SAFETY, the critical boundary] — a scripted DESTRUCTIVE
  tool-call surfaces the confirm/cancel dialog naming the action; APPROVE → executed
  (document changes, exactly one ``AssistantCommand`` undo step); DENY /
  dialog-dismissed → NOT executed, byte-identical, no undo step; a REVERSIBLE op with
  NO dialog. The confirmation is answered through the real signal path
  (``confirmRequested`` → the dock's ``_on_confirm_requested`` → the controller's
  ``provide_confirmation``); only ``QMessageBox.exec`` is stubbed (there is no user to
  click headless).
* **mid-turn error** — a reversible op applied then the turn fails mid-flight: the dock
  shows a ``tr()``-wrapped error and returns to idle, the document is BYTE-IDENTICAL
  (the worker reverted the partial command), and NO undo step was recorded
  (``editsReady`` never fired).
* **SC-UI-002-1** — the provider-config dialog hands the API key to the ``data/llm``
  token store (MOCK keyring — never the real one), the key is masked + never written to
  ``QSettings``/``repr``, the non-secret config persists to ``QSettings``, and a
  not-configured state degrades gracefully (the dock prompts to configure, no crash).
* **SC-UI-005-1 / SC-UI-006-1** — accessible names on every interactive control,
  keyboard send, a logical focus order; both themes render.
* clean worker teardown — closing the dock/window stops the worker thread (no dangling
  thread / connected carrier), the standalone controller is torn down by a fixture, and
  the segfault-free-teardown module runs alongside ``Main_Window``-heavy modules under
  ``-n 2``.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QLineEdit, QMessageBox

import pixelart_creator.ui.provider_config_dialog as pcd
from pixelart_creator.data.llm.fake_adapter import FakeLLMAdapter
from pixelart_creator.data.llm.port import LLMPort
from pixelart_creator.logic import scripting
from pixelart_creator.logic.assistant import AssistantReply
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.history import PixelEdit
from pixelart_creator.logic.macro import Op
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.scripting import OP_PROCGEN, ParamSchema
from pixelart_creator.logic.tool_catalog import ToolCall
from pixelart_creator.ui.assistant_dock import Assistant_Dock
from pixelart_creator.ui.assistant_worker import Assistant_Controller
from pixelart_creator.ui.commands import AssistantCommand
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.provider_config_dialog import (
    PROVIDER_ANTHROPIC,
    PROVIDER_OPENAI,
    AssistantProviderConfig,
    Provider_Config_Dialog,
    build_backend,
    load_config,
)

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]

#: A registered-but-NOT-whitelisted op used to exercise the DESTRUCTIVE gate. It is a
#: real, undo-backed single-pixel edit (so an *approved* run is observably applied) yet
#: it is deliberately absent from ``REVERSIBLE_OPS`` — so the logic gate classifies it
#: DESTRUCTIVE and gate-closes it behind the confirm dialog.
DANGER_OP = "danger.wipe"
DANGER_COLOR = (7, 7, 7, 255)

#: A run finishes well within this budget off the GUI thread.
TURN_TIMEOUT_MS = 8000


# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


def _doc_bytes(document: Document) -> bytes:
    """Whole-document byte fingerprint (every leaf buffer of every frame).

    Detects ANY partial pixel mutation, so a "document byte-identical" assertion is a
    genuine no-apply / reverted-cleanly proof (the tiered-safety + error-atomicity
    invariants).
    """
    chunks = [
        np.ascontiguousarray(layer.buffer.data).tobytes()
        for frame in document.frames
        for layer in iter_layers(frame.layers)
    ]
    return b"".join(chunks)


def _procgen_call(width: int, height: int, *, seed: int = 7) -> ToolCall:
    """A whitelisted (REVERSIBLE) ``procgen`` tool-call writing noise into frame 0."""
    return ToolCall(
        OP_PROCGEN,
        {"algorithm": "value_noise", "width": width, "height": height, "seed": seed},
    )


def _danger_factory(document, params, seed):
    """Trusted factory for the destructive test op: one undoable single-pixel edit.

    The fixture (``make_dock``) always builds a fresh single-frame,
    single-layer document, so the edit's real target — frame 0, the
    background layer's minted ``layer_id`` — is genuinely knowable here; it is
    threaded through rather than passing ``target=None`` (the unknown
    sentinel is only for a site that truly lacks this context).
    """
    layer = iter_layers(document.frames[0].layers)[0]
    old = tuple(int(v) for v in layer.buffer.data[0, 0])
    return PixelEdit(
        layer.buffer,
        [(0, 0, old, DANGER_COLOR)],
        label="danger",
        target=EditTarget(frame_index=0, layer_id=layer.layer_id),
    )


def _send(qtbot, env, text: str, *, timeout: int = TURN_TIMEOUT_MS) -> None:
    """Type ``text`` into the dock and drive one bounded turn off the GUI thread.

    Waits on the controller's terminal ``runFinished`` (fired on success, failure, or
    cancel), so on return the dock has already rendered the outcome and (on success)
    emitted any ``editsReady``.
    """
    env.dock._input.setText(text)
    with qtbot.waitSignal(env.controller.runFinished, timeout=timeout):
        env.dock._on_send()


# --------------------------------------------------------------------------- #
# Fixtures                                                                      #
# --------------------------------------------------------------------------- #


@pytest.fixture
def make_dock(qtbot):
    """Factory building a standalone dock over a fresh controller + fake adapter.

    Returns a namespace with the ``dock``, its window-owned ``controller``, the live
    ``document``, the scripted ``fake`` backend, and a local ``stack`` that
    ``editsReady`` pushes one :class:`AssistantCommand` onto (so a test can count the
    undo step and see the edit applied). Every controller is torn down at the end
    (the idempotent, event-loop-free ``shutdown`` — no worker thread / connected carrier
    survives into a later test's GC).
    """
    created: list = []

    def _make(script, *, configured=True, backend=None, width=32, height=32):
        document = Document(width, height, palette=Palette(STARTER))
        controller = Assistant_Controller()
        fake = FakeLLMAdapter(list(script), configured=configured)
        chosen_backend = fake if backend is None else backend
        stack = QUndoStack()

        dock = Assistant_Dock(
            controller,
            lambda: document,
            lambda: chosen_backend,
        )

        def _on_edits(commands, label):
            stack.push(AssistantCommand(tuple(commands), lambda: None, label))

        dock.editsReady.connect(_on_edits)
        qtbot.addWidget(dock)
        created.append(controller)
        return SimpleNamespace(
            dock=dock,
            controller=controller,
            document=document,
            fake=fake,
            stack=stack,
        )

    yield _make

    for controller in created:
        controller.shutdown()


@pytest.fixture
def danger_op(plugin_isolation):
    """Register the destructive (non-whitelisted) op; the registry is restored after.

    ``plugin_isolation`` (testing/suites/ui/conftest.py) unregisters any op added by the test,
    so the built-ins (``batch_recolour`` / ``procgen``) are left intact.
    """
    scripting.register_command(DANGER_OP, _danger_factory, ParamSchema())
    return DANGER_OP


@pytest.fixture
def isolated_settings(tmp_path):
    """Point :class:`QSettings` at an isolated INI file (no registry pollution).

    Uses ``IniFormat`` + a per-test user-scope path so ``save_config`` / ``load_config``
    exercise the real ``QSettings`` round-trip without touching the developer's real
    settings; the default format + app identity are restored afterwards.
    """
    app = QCoreApplication.instance()
    orig_org, orig_app = app.organizationName(), app.applicationName()
    orig_fmt = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path / "settings"),
    )
    app.setOrganizationName("PixelArtCreatorTests")
    app.setApplicationName("AssistantConfigTests")
    QSettings().clear()
    try:
        yield
    finally:
        app.setOrganizationName(orig_org)
        app.setApplicationName(orig_app)
        QSettings.setDefaultFormat(orig_fmt)


# --------------------------------------------------------------------------- #
# SC-UI-001-1 — the dock drives the logic loop + renders the transcript         #
# --------------------------------------------------------------------------- #


def test_dock_send_drives_loop_and_renders_transcript(qtbot, make_dock):
    """SC-UI-001-1: send routes to the worker; user/assistant/tool entries render."""
    env = make_dock(
        [
            AssistantReply.calling(_procgen_call(32, 32)),
            AssistantReply.final("Done — I generated some noise."),
        ]
    )
    busy_states: list = []
    env.controller.busyChanged.connect(busy_states.append)

    _send(qtbot, env, "make some noise")

    # The dock drove the logic/ loop against the injected backend (never a provider):
    # the fake recorded the conversation it was asked to respond to.
    assert env.fake.calls, "the dock did not drive the injected backend"
    # busyChanged toggled True (in flight) then False (idle again).
    assert True in busy_states and busy_states[-1] is False

    transcript = env.dock._transcript.toPlainText()
    assert "You: make some noise" in transcript  # user message
    assert "Assistant:" in transcript  # assistant reply / narration
    assert "Action:" in transcript  # tool-result summary
    assert "Applied" in transcript and OP_PROCGEN in transcript
    assert "Done — I generated some noise." in transcript


def test_dock_surfaces_turn_error_not_swallowed(qtbot, make_dock):
    """SC-UI-001-1: a turn error is surfaced in the transcript, never swallowed."""
    # A single reversible call then an exhausted script → the second respond() raises
    # mid-turn (LLMResponseError). See the dedicated byte-identity assertion below; here
    # we only assert the error text reaches the transcript.
    env = make_dock([AssistantReply.calling(_procgen_call(32, 32))])

    _send(qtbot, env, "break please")

    transcript = env.dock._transcript.toPlainText()
    assert "Assistant error:" in transcript
    # The dock returned to idle after the failure.
    assert env.controller.is_busy() is False
    assert env.dock._send_button.isEnabled() is True


# --------------------------------------------------------------------------- #
# SC-UI-003-1 [TIERED-SAFETY] — destructive confirm / deny; reversible auto     #
# --------------------------------------------------------------------------- #


def test_reversible_op_auto_runs_without_dialog(qtbot, make_dock, monkeypatch):
    """SC-UI-003-1: a REVERSIBLE op applies with NO dialog, visible + undoable."""
    shown: list = []
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda self: shown.append(self.text()) or QMessageBox.StandardButton.No,
    )
    env = make_dock(
        [
            AssistantReply.calling(_procgen_call(32, 32)),
            AssistantReply.final("done"),
        ]
    )
    before = _doc_bytes(env.document)

    _send(qtbot, env, "generate")

    # No confirmation dialog for a reversible op (the gate never withheld it).
    assert shown == []
    # Exactly one undoable AssistantCommand step was pushed, and it applied the edit.
    assert env.stack.count() == 1
    assert _doc_bytes(env.document) != before  # visible (applied on push)
    env.stack.undo()
    assert _doc_bytes(env.document) == before  # undoable (apply ∘ undo = identity)


def test_destructive_op_confirm_approve_executes(
    qtbot, make_dock, danger_op, monkeypatch
):
    """SC-UI-003-1: a DESTRUCTIVE op prompts; APPROVE → executed, one undo step."""
    shown: list = []

    def _approve(self):
        shown.append(self.text())
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "exec", _approve)
    env = make_dock(
        [
            AssistantReply.calling(ToolCall(danger_op, {})),
            AssistantReply.final("done"),
        ]
    )
    before = _doc_bytes(env.document)

    _send(qtbot, env, "do the risky thing")

    # The dialog was shown and NAMED the exact action (renders the gate's decision).
    assert shown and any(danger_op in text for text in shown)
    # Approved → executed as exactly one undoable AssistantCommand step.
    assert env.stack.count() == 1
    assert _doc_bytes(env.document) != before
    env.stack.undo()
    assert _doc_bytes(env.document) == before


@pytest.mark.parametrize(
    "decision",
    [QMessageBox.StandardButton.No, QMessageBox.StandardButton.NoButton],
    ids=["deny", "dialog-dismissed"],
)
def test_destructive_op_deny_or_dismiss_not_executed(
    qtbot, make_dock, danger_op, monkeypatch, decision
):
    """SC-UI-003-1: DENY / dismissed → NOT executed, byte-identical, no undo step."""
    monkeypatch.setattr(QMessageBox, "exec", lambda self: decision)
    env = make_dock(
        [
            AssistantReply.calling(ToolCall(danger_op, {})),
            AssistantReply.final("understood, skipping"),
        ]
    )
    before = _doc_bytes(env.document)

    _send(qtbot, env, "do the risky thing")

    # Declined → the op never ran: no undo step and the document is byte-identical.
    assert env.stack.count() == 0
    assert _doc_bytes(env.document) == before
    # The turn still completed cleanly (the declined result fed back; a final reply).
    assert "understood, skipping" in env.dock._transcript.toPlainText()


def test_dock_never_relaxes_the_gate_for_an_unregistered_op(
    qtbot, make_dock, monkeypatch
):
    """SC-UI-003-1: an unregistered op is rejected by the gate; no dialog, no edit."""
    # An op that cannot exist is rejected *before* the confirm gate — the dock is not
    # even asked to confirm, and nothing is applied (the UI cannot invent privilege).
    shown: list = []
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda self: shown.append(self.text()) or QMessageBox.StandardButton.Yes,
    )
    env = make_dock(
        [
            AssistantReply.calling(ToolCall("wipe_disk", {})),
            AssistantReply.final("could not run that"),
        ]
    )
    before = _doc_bytes(env.document)

    _send(qtbot, env, "wipe everything")

    assert shown == []  # not registered → never reaches the confirm gate
    assert env.stack.count() == 0
    assert _doc_bytes(env.document) == before
    assert "Rejected" in env.dock._transcript.toPlainText()


# --------------------------------------------------------------------------- #
# Mid-turn error atomicity — byte-identical + no undo step + error shown         #
# --------------------------------------------------------------------------- #


def test_mid_turn_error_reverts_and_records_no_undo_step(qtbot, make_dock):
    """A reversible op applied then a mid-turn raise → byte-identical, no undo step."""
    # The fake applies one reversible op (procgen) then, with the script exhausted, its
    # next respond() raises mid-turn — run_turn wraps it (applied_commands), the worker
    # reverts the partial command, and surfaces the error. editsReady must NOT fire.
    edits_fired: list = []
    env = make_dock([AssistantReply.calling(_procgen_call(32, 32))])
    env.dock.editsReady.connect(lambda c, label: edits_fired.append(c))
    before = _doc_bytes(env.document)

    _send(qtbot, env, "apply then explode")

    # Document byte-identical (the worker reverted the partial reversible command).
    assert _doc_bytes(env.document) == before
    # No undo step recorded (editsReady never fired → nothing pushed).
    assert edits_fired == []
    assert env.stack.count() == 0
    # The error was surfaced (tr()-wrapped) and the dock returned to idle.
    assert "Assistant error:" in env.dock._transcript.toPlainText()
    assert env.controller.is_busy() is False
    assert env.dock._input.isEnabled() is True


# --------------------------------------------------------------------------- #
# SC-UI-002-1 — provider/key config: keyring not settings; graceful degrade     #
# --------------------------------------------------------------------------- #


def test_config_key_to_keyring_never_in_settings_or_repr(
    qtbot, isolated_settings, monkeypatch
):
    """SC-UI-002-1: the key goes to the token store (mock keyring), not QSettings."""
    stored: list = []
    monkeypatch.setattr(pcd, "is_keyring_available", lambda: True)
    monkeypatch.setattr(
        pcd,
        "store_token",
        lambda provider, account, token: stored.append((provider, account, token)),
    )

    dialog = Provider_Config_Dialog()
    qtbot.addWidget(dialog)

    # The key field is masked and never pre-filled.
    assert dialog._key_edit.echoMode() == QLineEdit.EchoMode.Password

    idx = dialog._provider_combo.findData(PROVIDER_OPENAI)
    dialog._provider_combo.setCurrentIndex(idx)
    dialog._base_url_edit.setText("https://example.test/v1")
    dialog._model_edit.setText("test-model")
    dialog._key_edit.setText("sk-SECRET-123")
    dialog._on_accept()

    # The key was handed to the data/llm token store under the "default" account …
    assert stored == [(PROVIDER_OPENAI, "default", "sk-SECRET-123")]
    # … the entry field retains no raw key …
    assert dialog._key_edit.text() == ""
    # … the non-secret config persisted to QSettings …
    cfg = load_config()
    assert cfg is not None
    assert cfg.provider == PROVIDER_OPENAI
    assert cfg.base_url == "https://example.test/v1"
    assert cfg.model == "test-model"
    # … and the key is nowhere in QSettings nor the config's repr.
    settings = QSettings()
    dumped = " ".join(str(settings.value(key)) for key in settings.allKeys())
    assert "sk-SECRET-123" not in dumped
    assert "sk-SECRET-123" not in repr(cfg)


def test_config_saves_non_secret_without_a_key(qtbot, isolated_settings, monkeypatch):
    """SC-UI-002-1: with no key entered, the token store is untouched; config saved."""
    calls: list = []
    monkeypatch.setattr(pcd, "is_keyring_available", lambda: True)
    monkeypatch.setattr(pcd, "store_token", lambda *a: calls.append(a))

    dialog = Provider_Config_Dialog()
    qtbot.addWidget(dialog)
    dialog._base_url_edit.setText("https://no-key.test/v1")
    dialog._model_edit.setText("m")
    dialog._on_accept()

    assert calls == []  # no key → keyring untouched
    assert load_config() is not None  # non-secret config still persisted


def test_build_backend_is_provider_agnostic(qtbot, isolated_settings):
    """SC-UI-002-1: the app builds a port identically for either provider."""
    openai = build_backend(
        AssistantProviderConfig(PROVIDER_OPENAI, "https://a.test/v1", "m")
    )
    anthropic = build_backend(
        AssistantProviderConfig(PROVIDER_ANTHROPIC, "https://b.test", "m")
    )
    # Both are the same frozen provider-agnostic port type behind the seam.
    assert isinstance(openai, LLMPort)
    assert isinstance(anthropic, LLMPort)


def test_dock_degrades_gracefully_when_not_configured(qtbot, make_dock):
    """SC-UI-002-1: an unconfigured backend prompts to configure; no crash, no turn."""
    env = make_dock([AssistantReply.final("unreachable")], configured=False)
    busy_states: list = []
    env.controller.busyChanged.connect(busy_states.append)

    env.dock._input.setText("hello?")
    env.dock._on_send()  # must NOT start a turn (returns synchronously)

    assert env.fake.calls == []  # no turn dispatched
    assert busy_states == []  # never went busy
    transcript = env.dock._transcript.toPlainText()
    assert "No AI provider is configured" in transcript


def test_dock_no_document_prompts_and_does_not_crash(qtbot):
    """SC-UI-002-1 (graceful): with no open document the dock prompts, no crash."""
    controller = Assistant_Controller()
    try:
        fake = FakeLLMAdapter([AssistantReply.final("x")], configured=True)
        dock = Assistant_Dock(controller, lambda: None, lambda: fake)
        qtbot.addWidget(dock)
        dock._input.setText("edit please")
        dock._on_send()
        assert fake.calls == []  # no document → no turn
        assert "Open a document" in dock._transcript.toPlainText()
    finally:
        controller.shutdown()


# --------------------------------------------------------------------------- #
# SC-UI-005-1 — accessibility (names, keyboard send, focus order)               #
# --------------------------------------------------------------------------- #


def test_dock_accessible_names_present(qtbot, make_dock):
    """SC-UI-005-1: every interactive dock control exposes an accessible name."""
    env = make_dock([AssistantReply.final("hi")])
    dock = env.dock
    assert dock._input.accessibleName()
    assert dock._send_button.accessibleName()
    assert dock._configure_button.accessibleName()
    assert dock._transcript.accessibleName()
    assert dock._busy_bar.accessibleName()
    # The send button is the dialog default (Enter activates it).
    assert dock._send_button.isDefault() is True


def test_dock_keyboard_send_drives_a_turn(qtbot, make_dock):
    """SC-UI-005-1: pressing Enter in the input sends the message (keyboard)."""
    env = make_dock(
        [
            AssistantReply.calling(_procgen_call(32, 32)),
            AssistantReply.final("done"),
        ]
    )
    env.dock._input.setText("via keyboard")
    with qtbot.waitSignal(env.controller.runFinished, timeout=TURN_TIMEOUT_MS):
        env.dock._input.returnPressed.emit()  # Enter → _on_send
    assert env.fake.calls
    assert "You: via keyboard" in env.dock._transcript.toPlainText()


def test_config_dialog_accessible_names_present(qtbot):
    """SC-UI-005-1: the provider/key config controls expose accessible names."""
    dialog = Provider_Config_Dialog()
    qtbot.addWidget(dialog)
    assert dialog._provider_combo.accessibleName()
    assert dialog._base_url_edit.accessibleName()
    assert dialog._model_edit.accessibleName()
    assert dialog._key_edit.accessibleName()


# --------------------------------------------------------------------------- #
# SC-UI-006-1 — both themes render (the autouse theme fixture parametrises)      #
# --------------------------------------------------------------------------- #


def test_dock_and_dialog_render_in_current_theme(qtbot, make_dock, theme):
    """SC-UI-006-1: the dock + config dialog build and lay out under the active theme.

    The autouse ``theme`` fixture runs this (and every test in the module) under both
    light and dark themes; the dock uses no hard-coded colours (role-based QSS), so a
    clean build + non-empty sizeHint under each theme is the render smoke.
    """
    env = make_dock([AssistantReply.final("hi")])
    env.dock.show()
    assert env.dock.sizeHint().isValid()
    dialog = Provider_Config_Dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.sizeHint().isValid()
    assert theme in ("light", "dark")


# --------------------------------------------------------------------------- #
# i18n retranslate smoke (SC-UI-007-1 is owned by localisation; this guards the dock) #
# --------------------------------------------------------------------------- #


def test_dock_retranslates_without_crash(qtbot, make_dock):
    """The dock re-sets its user-visible strings on a language change (F5) safely."""
    env = make_dock([AssistantReply.final("hi")])
    before = env.dock.windowTitle()
    env.dock._retranslate()  # idempotent; also invoked via changeEvent(LanguageChange)
    assert env.dock.windowTitle() == before
    assert env.dock._send_button.text()  # non-empty, tr()-wrapped


# --------------------------------------------------------------------------- #
# Main_Window wiring — Help-menu toggle + one AssistantCommand per turn's edits  #
# --------------------------------------------------------------------------- #


def test_help_menu_toggle_shows_and_hides_the_dock(qtbot):
    """SC-UI-001-1 (wiring): the assistant dock's toggle lives in the Help menu."""
    win = Main_Window()
    qtbot.addWidget(win)
    win.show()
    dock = win._assistant_dock_widget
    action = dock.toggleViewAction()

    # The toggle is discoverable in the Help menu (the sanctioned launch surface).
    assert action in win._help_menu.actions()

    dock.setVisible(True)
    assert action.isChecked() is True
    action.trigger()  # hide
    assert dock.isVisible() is False
    action.trigger()  # show
    assert dock.isVisible() is True


def test_main_window_wraps_turn_edits_in_one_assistant_command(qtbot):
    """SC-UI-003-1 (wiring): a turn's edits become exactly one AssistantCommand step."""
    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    assert record is not None
    document = record.document

    # Build a real reversible command (as the worker would marshal back: UNAPPLIED).
    group = scripting.dispatch(
        document,
        [
            Op(
                OP_PROCGEN,
                {
                    "algorithm": "value_noise",
                    "width": document.width,
                    "height": document.height,
                },
                seed=5,
            )
        ],
    )
    group.undo()  # dispatch applied it; leave the live document restored (worker model)

    before = _doc_bytes(document)
    count_before = record.stack.count()

    win._on_assistant_edits((group,), "Assistant edit")

    # Exactly one undoable step was pushed, applying the whole turn's edits on the GUI
    # thread; undo restores the document byte-for-byte.
    assert record.stack.count() == count_before + 1
    assert _doc_bytes(document) != before
    record.stack.undo()
    assert _doc_bytes(document) == before


def test_main_window_chat_only_turn_pushes_no_command(qtbot):
    """SC-UI-003-1 (wiring): a chat-only turn (no commands) pushes no undo step."""
    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    assert record is not None
    count_before = record.stack.count()
    win._on_assistant_edits((), "Assistant edit")  # empty → nothing pushed
    assert record.stack.count() == count_before


# --------------------------------------------------------------------------- #
# Clean worker teardown — no dangling thread / carrier (xdist segfault guard)    #
# --------------------------------------------------------------------------- #


def test_dock_close_shuts_down_the_worker(qtbot, make_dock):
    """Closing the dock stops the worker: carrier released, pool drained, not busy."""
    env = make_dock(
        [
            AssistantReply.calling(_procgen_call(32, 32)),
            AssistantReply.final("done"),
        ]
    )
    _send(qtbot, env, "run then close")  # exercise the real off-thread worker
    assert env.controller._signals is not None  # carrier live before teardown

    env.dock.close()  # closeEvent → shutdown()

    assert (
        env.controller._signals is None
    )  # carrier released → nothing to cross-thread-GC
    assert env.controller._pool.activeThreadCount() == 0
    assert env.controller.is_busy() is False
    env.dock.shutdown()  # idempotent second call is a safe no-op
    assert env.controller._signals is None


def test_main_window_shutdown_drains_assistant_controller(qtbot):
    """Disposing a Main_Window drains its assistant controller — no worker lives."""
    win = Main_Window()
    qtbot.addWidget(win)
    controller = win._assistant_controller
    assert controller._signals is not None

    win.shutdown_prewarm()  # exactly what closeEvent / the drain fixture calls

    assert controller._signals is None
    assert controller._pool.activeThreadCount() == 0
    assert controller.is_busy() is False
    win.shutdown_prewarm()  # idempotent


# --------------------------------------------------------------------------- #
# REQ-P14-UI-004 literal Given: the GUI stays live                            #
# during a slow turn (a fake adapter with an injected delay).                 #
# --------------------------------------------------------------------------- #


class _SlowFakeAdapter(FakeLLMAdapter):
    """A :class:`FakeLLMAdapter` whose ``respond`` sleeps ``delay_s`` first.

    The sleep runs on the OFF-GUI-thread worker (``Assistant_Controller``'s
    ``QThreadPool``) — never the GUI thread — so it models a slow real
    provider round-trip without any network dependency (Article IV).
    """

    def __init__(self, script, delay_s: float, **kwargs) -> None:
        super().__init__(script, **kwargs)
        self._delay_s = delay_s

    def respond(self, conversation, tools):
        time.sleep(self._delay_s)
        return super().respond(conversation, tools)


def test_t29_gui_stays_responsive_during_a_slow_turn(qtbot, make_dock):
    """REQ-P14-UI-004: with a scripted reply delayed on the worker thread,
    the GUI event loop keeps pumping (heartbeat processEvents calls succeed and
    accumulate) WHILE the turn is in flight — proving the agentic loop truly
    runs off the GUI thread, not just that it eventually finishes."""
    from PySide6.QtWidgets import QApplication

    slow = _SlowFakeAdapter(
        [AssistantReply.final("done")], delay_s=0.5, configured=True
    )
    env = make_dock([AssistantReply.final("unused")], backend=slow)

    heartbeats = 0
    finished = []
    env.controller.runFinished.connect(lambda *a: finished.append(1))

    env.dock._input.setText("slow turn please")
    env.dock._on_send()  # submits to the off-thread worker; returns immediately

    # The GUI thread must stay responsive WHILE the worker sleeps: pump the
    # event loop repeatedly and count successful heartbeats before the turn
    # finishes. A frozen GUI would never reach the bound below in time.
    deadline = time.monotonic() + 5.0
    while not finished and time.monotonic() < deadline:
        QApplication.processEvents()
        heartbeats += 1

    assert finished, "the turn never finished within the bounded deadline"
    assert (
        heartbeats > 5
    ), "the GUI event loop did not keep pumping during the slow turn"
