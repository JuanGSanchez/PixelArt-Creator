"""D-13 acceptance: ``compute_sync_state`` surfaced in the version browser AND
the Cloud-menu status line (REQ-P10-UI-002/-007).

Drives ``compute_sync_state``'s real inputs (``local_version_id`` +
``versions``) through the two shipped surfaces — never asserting on the
Qt-free logic function directly — via the fake in-memory cloud adapter's
seam (``Main_Window._on_cloud_connect`` -> ``FakeCloudAdapter``, the same
pattern ``test_cloud_connect.py`` uses). Both themes via the autouse
``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.logic.sync_state import SyncState
from pixelart_creator.logic.version_history import CloudVersion
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.version_history_browser import Version_History_Browser

V1 = CloudVersion(version_id="v1", ordinal=0, created_marker=1, size_bytes=10)
V2 = CloudVersion(version_id="v2", ordinal=1, created_marker=2, size_bytes=20)
V3 = CloudVersion(version_id="v3", ordinal=2, created_marker=3, size_bytes=30)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# --- surface 1: Version_History_Browser status line -------------------------- #


def test_d13_browser_status_up_to_date(qtbot):
    """D-13: local at the latest remote version -> UP_TO_DATE."""
    browser = Version_History_Browser((V1, V2), local_version_id="v2")
    qtbot.addWidget(browser)
    assert browser._sync_state is SyncState.UP_TO_DATE
    assert browser._status.property("syncState") == "up_to_date"
    assert browser._status.text() == "Up to date with the cloud."


def test_d13_browser_status_local_ahead_no_remote_history(qtbot):
    """D-13: no remote versions at all and no local lineage -> up to date
    (nothing to diverge from); WITH a local lineage but empty remote history
    the local copy is ahead (not yet saved)."""
    browser = Version_History_Browser((), local_version_id=None)
    qtbot.addWidget(browser)
    assert browser._sync_state is SyncState.UP_TO_DATE

    browser2 = Version_History_Browser((), local_version_id="v1")
    qtbot.addWidget(browser2)
    assert browser2._sync_state is SyncState.LOCAL_AHEAD
    assert browser2._status.property("syncState") == "local_ahead"
    assert (
        browser2._status.text() == "Local changes have not been saved to the cloud yet."
    )


def test_d13_browser_status_remote_ahead(qtbot):
    """D-13: local synced to an earlier version; the remote has since moved on."""
    browser = Version_History_Browser((V1, V2, V3), local_version_id="v1")
    qtbot.addWidget(browser)
    assert browser._sync_state is SyncState.REMOTE_AHEAD
    assert browser._status.property("syncState") == "remote_ahead"
    assert browser._status.text() == "A newer version exists in the cloud."


def test_d13_browser_status_diverged(qtbot):
    """D-13: local's remembered version id is unknown to the remote history."""
    browser = Version_History_Browser((V1, V2), local_version_id="v-unknown")
    qtbot.addWidget(browser)
    assert browser._sync_state is SyncState.DIVERGED
    assert browser._status.property("syncState") == "diverged"
    assert browser._status.text() == "Local and cloud history have diverged."


def test_d13_browser_status_defaults_to_none_and_retranslates(qtbot):
    """D-13: the default ``local_version_id=None`` still computes a real state,
    and the status label re-renders on a language change (F5)."""
    from PySide6.QtCore import QEvent

    browser = Version_History_Browser((V1,))
    qtbot.addWidget(browser)
    assert (
        browser._sync_state is SyncState.REMOTE_AHEAD
    )  # remote has a version, no local lineage
    before = browser._status.text()
    browser.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert browser._status.text() == before  # English source is stable/idempotent


# --- surface 2: Main_Window Cloud-menu status action ------------------------- #


def test_d13_window_status_disconnected_shows_placeholder(qtbot):
    """D-13: disconnected (no cloud session) -> the placeholder dash text."""
    win = _window(qtbot)
    assert win._cloud_status_action.text() == "Cloud status: —"


def test_d13_window_status_reflects_fake_adapter_transitions(qtbot):
    """D-13: connecting through the FakeCloudAdapter seam and driving
    ``compute_sync_state``'s real inputs (the active tab's ``local_version_id``
    + the cached remote version list) moves the Cloud-menu text through every
    ``SyncState`` — recomputed via the SAME ``_update_cloud_status`` call sites
    the shipped save/open/restore flow uses."""
    win = _window(qtbot)
    win._on_cloud_connect()  # default factory: connected fake adapter
    record = win.active_tab()
    assert record is not None

    # No remote history cached yet, no local lineage -> up to date.
    win._cloud_last_versions = ()
    record.local_version_id = None
    win._update_cloud_status()
    assert win._cloud_status_action.text() == "Cloud status: Up to date"

    # A cloud save recorded a version, but the remote list wasn't re-fetched:
    # local is ahead of what the window has cached as "the remote".
    record.local_version_id = "v9"
    win._update_cloud_status()
    assert win._cloud_status_action.text() == "Cloud status: Not yet saved to cloud"

    # The remote history is fetched (e.g. opening the version browser) and the
    # active tab's local lineage matches the latest cached version.
    win._cloud_last_versions = (V1, V2)
    record.local_version_id = "v2"
    win._update_cloud_status()
    assert win._cloud_status_action.text() == "Cloud status: Up to date"

    # The remote has since moved on past the tab's remembered version.
    win._cloud_last_versions = (V1, V2, V3)
    record.local_version_id = "v1"
    win._update_cloud_status()
    assert win._cloud_status_action.text() == "Cloud status: Newer version in cloud"

    # The tab's remembered version id is unknown to the cached remote history.
    record.local_version_id = "v-forked"
    win._update_cloud_status()
    assert win._cloud_status_action.text() == "Cloud status: Diverged"

    # Disconnecting drops back to the placeholder regardless of local lineage.
    win._on_cloud_disconnect()
    assert win._cloud_status_action.text() == "Cloud status: —"


def test_d13_window_status_recomputed_on_tab_switch(qtbot):
    """D-13: switching the active tab recomputes the status from THAT tab's
    own ``local_version_id`` (each tab tracks its own remote lineage)."""
    win = _window(qtbot)
    win._on_cloud_connect()
    win._cloud_last_versions = (V1, V2)
    first = win.active_tab()
    assert first is not None
    first.local_version_id = "v2"

    win.new_document(16, 16)
    second = win.active_tab()
    assert second is not None
    assert second is not first
    second.local_version_id = "v1"

    win._update_cloud_status()
    assert win._cloud_status_action.text() == "Cloud status: Newer version in cloud"

    # A real tab switch (fires the connected currentChanged -> _on_tab_changed,
    # which recomputes from the NOW-active tab's own local_version_id).
    win._tab_widget.setCurrentIndex(0)
    assert win.active_tab() is first
    assert win._cloud_status_action.text() == "Cloud status: Up to date"
