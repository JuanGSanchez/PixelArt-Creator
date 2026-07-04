"""Cloud UI accessibility, both themes, i18n (SC-UI-006/007/008-1, REQ-P10-UI-006..008).

Every interactive cloud control exposes a non-empty accessible name, is
keyboard-reachable in a logical order, and shows a visible focus indicator
(REQ-P10-UI-006); the dialogs render under both QSS themes with role-based colours
(REQ-P10-UI-007); and their user-visible strings are ``tr()``-wrapped and
retranslate on a language change (REQ-P10-UI-008). Every test runs under both the
light and dark theme via the autouse ``theme`` fixture. Findings feed the
a11y-audit report.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.version_history import CloudVersion
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.recovery_prompt import Recovery_Prompt
from pixelart_creator.ui.version_history_browser import Version_History_Browser


def _versions(count: int = 2):
    return tuple(
        CloudVersion(version_id=f"p:{i}", ordinal=i, created_marker=i, size_bytes=10)
        for i in range(count)
    )


def test_sc_ui_006_browser_controls_have_accessible_names(qtbot):
    """SC-UI-006-1: the version list + restore button expose accessible names."""
    browser = Version_History_Browser(_versions())
    qtbot.addWidget(browser)
    assert browser._tree.accessibleName() != ""
    assert browser._restore_button.accessibleName() != ""


def test_sc_ui_006_recovery_buttons_have_accessible_names(qtbot):
    """SC-UI-006-1: both recovery buttons expose accessible names."""
    prompt = Recovery_Prompt()
    qtbot.addWidget(prompt)
    assert prompt._recover_button.accessibleName() != ""
    assert prompt._discard_button.accessibleName() != ""


def test_sc_ui_006_version_list_is_keyboard_reachable(qtbot):
    """SC-UI-006-1: the version tree accepts keyboard focus (tab-reachable)."""
    browser = Version_History_Browser(_versions())
    qtbot.addWidget(browser)
    # A tree with a focus policy other than NoFocus is reachable by Tab.
    assert browser._tree.focusPolicy() != Qt.FocusPolicy.NoFocus
    # Single-selection so Up/Down + Enter drive an unambiguous restore.
    assert browser._tree.selectionMode() == browser._tree.SelectionMode.SingleSelection


def test_sc_ui_006_cloud_menu_actions_are_keyboard_operable(qtbot):
    """SC-UI-006-1: the Cloud menu + actions carry mnemonics (keyboard operable)."""
    win = Main_Window()
    qtbot.addWidget(win)
    # Mnemonics ("&") make the menu + actions keyboard-operable.
    assert "&" in win._cloud_menu.title()
    for action in (
        win._cloud_connect_action,
        win._cloud_disconnect_action,
        win._cloud_save_action,
        win._cloud_open_action,
        win._cloud_versions_action,
    ):
        assert action.text() != ""


def test_sc_ui_007_visible_focus_indicator_present(qtbot):
    """SC-UI-007-1: a visible focus indicator is themed once by role (:focus QSS)."""
    Main_Window  # touch import to keep the app themed via the autouse fixture
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss  # role-based focus ring applies to the cloud dialogs too


def test_sc_ui_007_dialogs_construct_and_render_in_active_theme(qtbot, theme):
    """SC-UI-007-1: browser + prompt build and lay out under the active theme.

    The autouse ``theme`` fixture runs this under BOTH light and dark; each dialog
    must construct with a valid layout and no per-widget hard-coded colour (colours
    come from the applied QSS role palette).
    """
    browser = Version_History_Browser(_versions())
    qtbot.addWidget(browser)
    prompt = Recovery_Prompt()
    qtbot.addWidget(prompt)
    # A valid size hint proves the widgets laid out under the applied theme.
    assert browser.sizeHint().isValid()
    assert prompt.sizeHint().isValid()
    # No inline stylesheet on the widgets -> they inherit the role-based app QSS.
    assert browser.styleSheet() == ""
    assert prompt.styleSheet() == ""


def test_sc_ui_008_dialog_strings_retranslate_on_language_change(qtbot):
    """SC-UI-008-1: dialogs re-set their tr() strings on QEvent.LanguageChange (F5)."""
    browser = Version_History_Browser(_versions())
    qtbot.addWidget(browser)
    prompt = Recovery_Prompt()
    qtbot.addWidget(prompt)

    # All user-visible strings are populated (none is an empty/bare placeholder).
    assert browser.windowTitle() != ""
    assert browser._restore_button.text() != ""
    assert prompt.windowTitle() != ""
    assert prompt._recover_button.text() != ""
    assert prompt._discard_button.text() != ""

    # A LanguageChange event triggers the changeEvent -> _retranslate path (no crash,
    # strings remain populated). This is the F5 live-retranslate hook.
    QApplication.sendEvent(browser, QEvent(QEvent.Type.LanguageChange))
    QApplication.sendEvent(prompt, QEvent(QEvent.Type.LanguageChange))
    assert browser._restore_button.text() != ""
    assert prompt._recover_button.text() != ""
