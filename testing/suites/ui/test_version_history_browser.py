"""Version-history browser: list + restore (SC-UI-002-1, REQ-P10-UI-002/-003).

The browser lists the ordered, immutable cloud version history and lets the user
inspect and restore a prior version; restoring reconstructs that version's
``Document`` via PIO-1, and the current unsaved state is protected (restore opens
a NEW tab — REQ-P10-DATA-004 semantics). The widget performs NO port I/O itself
(the caller fetches the version list off the GUI thread and hands it in), so
opening it never freezes the UI (REQ-P10-UI-005). Headless (offscreen), both
themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.version_history import CloudVersion
from pixelart_creator.ui.version_history_browser import Version_History_Browser


def _versions(count: int = 3):
    return tuple(
        CloudVersion(
            version_id=f"proj:{i}",
            ordinal=i,
            created_marker=i,
            size_bytes=100 + i,
            parent_version_id=(f"proj:{i - 1}" if i else None),
        )
        for i in range(count)
    )


def test_sc_ui_002_browser_lists_versions_in_order(qtbot):
    """SC-UI-002-1: the browser lists every version in the history's stable order."""
    versions = _versions(3)
    browser = Version_History_Browser(versions)
    qtbot.addWidget(browser)

    assert browser._tree.topLevelItemCount() == 3
    # Deterministic order: oldest first, as the immutable history orders them.
    ordinals = [
        int(browser._tree.topLevelItem(i).text(0))
        for i in range(browser._tree.topLevelItemCount())
    ]
    assert ordinals == [0, 1, 2]
    # A version is preselected (the latest) so Restore is immediately actionable.
    assert browser.selected_version() is versions[-1]
    assert browser._restore_button.isEnabled() is True


def test_sc_ui_002_selecting_a_version_returns_it(qtbot):
    """SC-UI-002-1: selecting a row makes it the version the caller restores."""
    versions = _versions(3)
    browser = Version_History_Browser(versions)
    qtbot.addWidget(browser)

    first_item = browser._tree.topLevelItem(0)
    browser._tree.setCurrentItem(first_item)
    assert browser.selected_version() is versions[0]


def test_sc_ui_002_restore_accepts_the_dialog(qtbot):
    """SC-UI-002-1: Restore (AcceptRole) accepts with the selected version to restore."""
    versions = _versions(2)
    browser = Version_History_Browser(versions)
    qtbot.addWidget(browser)

    browser._tree.setCurrentItem(browser._tree.topLevelItem(0))
    # Clicking Restore (the AcceptRole button) accepts the dialog.
    browser._restore_button.click()
    assert browser.result() == QDialog.DialogCode.Accepted
    assert browser.selected_version() is versions[0]


def test_sc_ui_002_double_click_restores(qtbot):
    """SC-UI-002-1: double-clicking a version restores it (keyboard Enter also accepts)."""
    versions = _versions(2)
    browser = Version_History_Browser(versions)
    qtbot.addWidget(browser)

    item = browser._tree.topLevelItem(1)
    browser._tree.setCurrentItem(item)
    browser._on_double_click(item, 0)
    assert browser.result() == QDialog.DialogCode.Accepted


def test_sc_ui_002_empty_history_has_no_selection(qtbot):
    """SC-UI-002-1: an empty history lists nothing, selects nothing, disables Restore.

    The window guards the empty case with a notice before opening the browser, but
    the widget must still degrade gracefully: no current item, no selectable
    version, the detail label shows the "select a version" hint, and a double-click
    on empty space accepts nothing.
    """
    browser = Version_History_Browser(())
    qtbot.addWidget(browser)
    assert browser._tree.topLevelItemCount() == 0
    assert browser.selected_version() is None
    assert browser._restore_button.isEnabled() is False
    assert browser._detail.text() == browser.tr("Select a version to restore.")
    # A double-click with no selected version must not accept the dialog.
    browser._on_double_click(None, 0)  # type: ignore[arg-type]
    assert browser.result() != QDialog.DialogCode.Accepted


def test_sc_ui_002_pinned_column_is_translatable_yes_no(qtbot):
    """SC-UI-002-1: the pinned column shows a translated Yes/No, not a bare bool."""
    versions = (
        CloudVersion(version_id="p:0", ordinal=0, created_marker=0, size_bytes=10),
        CloudVersion(
            version_id="p:1",
            ordinal=1,
            created_marker=1,
            size_bytes=10,
            is_pinned=True,
        ),
    )
    browser = Version_History_Browser(versions)
    qtbot.addWidget(browser)
    # Column 3 is Pinned; the values are the translated Yes/No, never "True"/"False".
    pinned_texts = {
        browser._tree.topLevelItem(i).text(3)
        for i in range(browser._tree.topLevelItemCount())
    }
    assert "True" not in pinned_texts and "False" not in pinned_texts
    assert browser.tr("Yes") in pinned_texts
    assert browser.tr("No") in pinned_texts
