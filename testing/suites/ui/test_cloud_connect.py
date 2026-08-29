"""Provider-agnostic cloud connect / disconnect (SC-UI-004-1, REQ-P10-UI-004/-007).

The connect entry point drives the port's provider-agnostic surface: the app
behaves identically regardless of which adapter the injected
:class:`~pixelart_creator.ui.cloud_actions.CloudPortFactory` builds, and ``ui/``
never sees a provider type or a token (REQ-P10-DATA-007/-008). These tests drive
the :class:`~pixelart_creator.ui.cloud_actions.Cloud_Session` seam and the
``Main_Window`` connect/disconnect wiring + action-enablement gate. Headless
(offscreen), both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.data.cloud import FakeCloudAdapter
from pixelart_creator.ui.cloud_actions import Cloud_Session
from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_004_session_connect_disconnect_is_provider_agnostic(qtbot):
    """SC-UI-004-1: connect builds a port and reports connected; disconnect releases it.

    The session names no provider — it only holds the abstract ``CloudPort`` and a
    connected/not-connected flag; the ``connectionChanged`` signal fires on each
    transition (the observable provider-agnostic contract).
    """
    session = Cloud_Session(parent=None)
    assert session.is_connected() is False
    assert session.port() is None

    with qtbot.waitSignal(session.connectionChanged, timeout=2000) as blocker:
        connected = session.connect_provider()
    assert connected is True
    assert blocker.args == [True]
    assert session.is_connected() is True
    # The session hands back only the abstract port — no provider/token surface.
    port = session.port()
    assert port is not None
    assert port.is_connected() is True

    with qtbot.waitSignal(session.connectionChanged, timeout=2000) as blocker:
        session.disconnect_provider()
    assert blocker.args == [False]
    assert session.is_connected() is False
    assert session.port() is None


def test_sc_ui_004_injected_factory_swaps_provider_with_no_ui_change(qtbot):
    """SC-UI-004-1: a swapped factory swaps the adapter behind the same seam.

    The app behaves identically regardless of provider — the port is the seam
    (REQ-P10-DATA-007). A disconnected fake adapter models the not-connected state.
    """
    built: list = []

    def factory():
        adapter = FakeCloudAdapter(connected=False)
        built.append(adapter)
        return adapter

    session = Cloud_Session(factory=factory)
    with qtbot.waitSignal(session.connectionChanged, timeout=2000) as blocker:
        connected = session.connect_provider()
    # The injected adapter reports not-connected; the session reflects it verbatim.
    assert connected is False
    assert blocker.args == [False]
    assert session.is_connected() is False
    assert len(built) == 1  # the factory (not the default) produced the port


def test_sc_ui_004_window_actions_gate_on_connection_state(qtbot):
    """SC-UI-004-1: the Cloud save/open/version actions enable only while connected.

    Save/open/version-history start disabled; connecting enables them (and disables
    the connect action); disconnecting reverses it — the connection-gated enablement
    the version-history / save flows depend on.
    """
    win = _window(qtbot)
    # Before connecting: save/open/versions disabled, connect enabled.
    assert win._cloud_save_action.isEnabled() is False
    assert win._cloud_open_action.isEnabled() is False
    assert win._cloud_versions_action.isEnabled() is False
    assert win._cloud_connect_action.isEnabled() is True
    assert win._cloud_disconnect_action.isEnabled() is False

    win._on_cloud_connect()  # default factory = connected fake adapter
    assert win._cloud_session.is_connected() is True
    assert win._cloud_save_action.isEnabled() is True
    assert win._cloud_open_action.isEnabled() is True
    assert win._cloud_versions_action.isEnabled() is True
    assert win._cloud_connect_action.isEnabled() is False
    assert win._cloud_disconnect_action.isEnabled() is True

    win._on_cloud_disconnect()
    assert win._cloud_session.is_connected() is False
    assert win._cloud_save_action.isEnabled() is False
    assert win._cloud_versions_action.isEnabled() is False
    assert win._cloud_connect_action.isEnabled() is True
