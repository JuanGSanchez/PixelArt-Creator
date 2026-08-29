"""Cloud save + open-from-cloud through the port (SC-UI-001-1, REQ-P10-UI-001/-005).

The user saves the current project to the cloud and later opens it back; storage
and reopening go through the provider-agnostic port off the GUI thread, opening
validates defensively (REQ-P10-DATA-006), and the UI names no provider directly.
These tests drive the round-trip at the ``Cloud_Controller`` seam AND the
``Main_Window`` save/open handlers (patching only the blocking
``QInputDialog`` / dialog ``exec``). Headless (offscreen), both themes.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QInputDialog

from pixelart_creator.data.cloud import deserialize_project, serialize_project
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.version_history import CloudVersion
from pixelart_creator.ui import version_history_browser as vhb_module
from pixelart_creator.ui.cloud_actions import Cloud_Session, make_save_job
from pixelart_creator.ui.cloud_worker import Cloud_Controller
from pixelart_creator.ui.main_window import Main_Window

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _doc(width: int = 16, height: int = 16) -> Document:
    return Document(width, height, palette=Palette(STARTER))


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_001_save_round_trips_through_port_off_thread(qtbot):
    """SC-UI-001-1: a project saved through the port re-fetches to an equivalent doc.

    Runs the save off the GUI thread on the window-owned pool (REQ-P10-UI-005); the
    succeeded result is the new ``CloudVersion``; fetching that version's bytes and
    defensively decoding them reconstructs an equivalent ``Document`` (the
    ``.pixproj`` is the atomic sync unit — REQ-P10-DATA-002).
    """
    session = Cloud_Session()  # default factory: connected in-memory fake adapter
    assert session.connect_provider() is True
    port = session.port()
    assert port is not None

    controller = Cloud_Controller()
    try:
        doc = _doc()
        # Record the succeeded outcome, but BLOCK on the terminal ``operationFinished``
        # (fired off the finally-run ``done``) before asserting idle — so the idle
        # check is robust to GUI-thread scheduling instead of assuming the succeeded
        # relay has already cleared busy by the time we look. This still asserts the
        # real behaviour: succeeded carries the CloudVersion, and once the terminal
        # signal is delivered the controller is idle.
        outcomes: list = []
        controller.operationSucceeded.connect(lambda k, r: outcomes.append((k, r)))
        with qtbot.waitSignal(controller.operationFinished, timeout=5000):
            controller.submit("save", make_save_job(port, "proj-a", doc))
        assert len(outcomes) == 1  # succeeded fired before the terminal
        kind, result = outcomes[0]
        assert kind == "save"
        assert isinstance(result, CloudVersion)
        assert controller.is_busy() is False  # terminal delivered -> idle

        # Re-fetch and defensively decode: an equivalent Document round-trips.
        fetched = deserialize_project(port.get("proj-a", result.version_id))
        assert isinstance(fetched, Document)
        assert (fetched.width, fetched.height) == (doc.width, doc.height)
        # Byte-equivalence through the shipped PIO-1 codec (the format guarantee).
        assert serialize_project(fetched) == serialize_project(doc)
    finally:
        controller.shutdown()


def test_sc_ui_001_window_save_marks_clean_and_creates_version(qtbot, monkeypatch):
    """SC-UI-001-1: Main_Window save stores a version and marks the active stack clean.

    Mirrors ``save_document``'s dirty-guard reset — after a successful cloud save the
    active undo stack is clean and the port holds exactly one new version.
    """
    win = _window(qtbot)
    win._on_cloud_connect()
    record = win.active_tab()
    assert record is not None
    # Make the document dirty via a real edit command on its stack.
    from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

    prepare_for_click(record.view)
    record.view.set_active_color((40, 90, 220, 255))
    click_pixel(record.view, 2, 2)
    assert record.stack.isClean() is False

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("proj-save", True))
    )
    with qtbot.waitSignal(win._cloud_controller.operationSucceeded, timeout=5000):
        win._on_cloud_save()

    assert record.stack.isClean() is True  # marked clean on success
    port = win._cloud_session.port()
    assert port is not None
    versions = port.list_versions("proj-save")
    assert len(versions) == 1


def test_sc_ui_001_window_open_from_cloud_opens_a_new_tab(qtbot, monkeypatch):
    """SC-UI-001-1: opening a pre-seeded cloud project reconstructs it into a new tab.

    Drives the full open flow: list_versions off-thread -> version browser (auto-
    accepting the latest) -> off-thread restore -> the reconstructed Document lands
    in a NEW tab (current unsaved state protected).
    """
    win = _window(qtbot)
    win._on_cloud_connect()
    port = win._cloud_session.port()
    assert port is not None
    # Pre-seed a stored project directly through the port (provider-agnostic).
    seeded = _doc(24, 24)
    port.put("proj-open", serialize_project(seeded))

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("proj-open", True))
    )

    # Auto-accept the version browser on the latest version (no blocking modal).
    def _auto_exec(self):
        last = self._tree.topLevelItem(self._tree.topLevelItemCount() - 1)
        self._tree.setCurrentItem(last)
        self.setResult(QDialog.DialogCode.Accepted)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(vhb_module.Version_History_Browser, "exec", _auto_exec)

    tabs_before = win._tab_widget.count()
    kinds: list = []
    win._cloud_controller.operationSucceeded.connect(
        lambda kind, _r: kinds.append(kind)
    )

    win._on_cloud_open()
    # open_list -> browser -> restore; wait until the restored tab has appeared.
    qtbot.waitUntil(lambda: "restore" in kinds, timeout=5000)
    qtbot.waitUntil(lambda: win._tab_widget.count() == tabs_before + 1, timeout=5000)
    opened = win.active_document()
    assert isinstance(opened, Document)
    assert (opened.width, opened.height) == (24, 24)
