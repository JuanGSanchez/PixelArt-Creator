"""Autosave-recovery prompt on restart (SC-UI-003-1, REQ-P10-UI-003).

On startup, if the cloud port's recovery slot holds unsaved work, the app prompts
the user to Recover or Discard, without overwriting the last explicit save until
the user chooses. Recover fetches + defensively decodes the blob off the GUI
thread and opens it into a NEW tab; Discard leaves the slot untouched (no
clobber). These tests drive ``Recovery_Prompt`` directly and the
``Main_Window._maybe_prompt_recovery`` startup path (patching the modal
``exec``). Headless (offscreen), both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pixelart_creator.data.cloud import serialize_project
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui import recovery_prompt as recovery_module
from pixelart_creator.ui.main_window import _RECOVERY_PROJECT_ID, Main_Window
from pixelart_creator.ui.recovery_prompt import Recovery_Prompt

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _doc(width: int = 20, height: int = 20) -> Document:
    return Document(width, height, palette=Palette(STARTER))


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_003_prompt_recover_is_the_focused_default(qtbot):
    """SC-UI-003-1: Recover is the default action; chose_recover reflects accept."""
    prompt = Recovery_Prompt()
    qtbot.addWidget(prompt)
    assert prompt._recover_button.isDefault() is True
    prompt._recover_button.click()
    assert prompt.result() == QDialog.DialogCode.Accepted
    assert prompt.chose_recover() is True


def test_sc_ui_003_prompt_discard_rejects(qtbot):
    """SC-UI-003-1: Discard (RejectRole) rejects; chose_recover is False."""
    prompt = Recovery_Prompt()
    qtbot.addWidget(prompt)
    prompt._discard_button.click()
    assert prompt.result() == QDialog.DialogCode.Rejected
    assert prompt.chose_recover() is False


def test_sc_ui_003_startup_recover_opens_recovered_tab(
    qtbot, monkeypatch, mute_message_boxes
):
    """SC-UI-003-1: when a recovery blob exists, Recover opens it into a new tab.

    The recovery slot is read via ``make_recover_job -> port.get_recovery`` (not a
    version fetch) and the defensively-decoded working copy opens in a NEW tab,
    leaving the last explicit save intact. mute_message_boxes keeps any error
    QMessageBox from blocking headless (none is expected on the success path).
    """
    win = _window(qtbot)
    win._on_cloud_connect()
    port = win._cloud_session.port()
    assert port is not None
    # Seed the recovery slot under the working key (nothing saved explicitly yet).
    seed = _doc(20, 20)
    port.put_recovery(_RECOVERY_PROJECT_ID, serialize_project(seed))

    monkeypatch.setattr(
        recovery_module.Recovery_Prompt,
        "exec",
        lambda self: self.setResult(QDialog.DialogCode.Accepted),
    )

    tabs_before = win._tab_widget.count()
    with qtbot.waitSignal(win._cloud_controller.operationFinished, timeout=5000):
        win._maybe_prompt_recovery()
    # The recovered document must open in a NEW tab (the acceptance criterion).
    assert win._tab_widget.count() == tabs_before + 1
    # The recovered working copy must be the one restored FROM the recovery slot:
    # same geometry AND same palette content as the seeded autosaved document,
    # proving the slot blob (not a version fetch) round-tripped into the tab.
    recovered = win.active_document()
    assert (recovered.width, recovered.height) == (seed.width, seed.height)
    assert recovered.palette == seed.palette


def test_sc_ui_003_startup_discard_leaves_slot_untouched(qtbot, monkeypatch):
    """SC-UI-003-1: Discard opens no tab and never clobbers the recovery slot."""
    win = _window(qtbot)
    win._on_cloud_connect()
    port = win._cloud_session.port()
    blob = serialize_project(_doc(20, 20))
    port.put_recovery(_RECOVERY_PROJECT_ID, blob)

    monkeypatch.setattr(
        recovery_module.Recovery_Prompt,
        "exec",
        lambda self: self.setResult(QDialog.DialogCode.Rejected),
    )

    tabs_before = win._tab_widget.count()
    win._maybe_prompt_recovery()
    qtbot.wait(50)  # give any (erroneous) off-thread submit a chance to land
    assert win._tab_widget.count() == tabs_before  # no recovered tab
    # No-clobber: the recovery slot is untouched (a later autosave, not discard,
    # would replace it).
    assert port.get_recovery(_RECOVERY_PROJECT_ID) == blob


def test_sc_ui_003_no_recovery_no_prompt(qtbot, monkeypatch):
    """SC-UI-003-1: with no recovery blob, no prompt is shown and no tab opens."""
    win = _window(qtbot)
    win._on_cloud_connect()  # connected, but the recovery slot is empty

    shown = []
    monkeypatch.setattr(
        recovery_module.Recovery_Prompt,
        "exec",
        lambda self: shown.append(True) or QDialog.DialogCode.Rejected,
    )
    tabs_before = win._tab_widget.count()
    win._maybe_prompt_recovery()
    assert shown == []  # the prompt was never constructed/shown
    assert win._tab_widget.count() == tabs_before
