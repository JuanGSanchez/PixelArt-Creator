"""Cloud save/load + provider-agnostic connect/disconnect (REQ-P10-UI-001/-004/-005).

Thin Qt front-end over the frozen, Qt-free cloud port
(:class:`~pixelart_creator.data.cloud.port.CloudPort`). It performs **no** cloud
logic of its own — it drives the port through the off-GUI-thread
:class:`~pixelart_creator.ui.cloud_worker.Cloud_Controller` (REQ-P10-UI-005) and
composes the shipped PIO-1 ``.pixproj`` codec (no new serialisation format,
Article I). Two concerns live here:

* :class:`Cloud_Session` — the **provider-agnostic** connect / disconnect entry
  point (REQ-P10-UI-004). It holds an ``Optional[CloudPort]`` produced by an
  injectable factory; ``connect`` builds the port, ``disconnect`` releases it.
  For Slice A the default factory is the CI-tested
  :class:`~pixelart_creator.data.cloud.fake_adapter.FakeCloudAdapter`, whose
  in-memory ``is_connected`` flag models the connected/not-connected state (live
  OAuth is a later, credential-gated slice — the flow lives entirely inside
  ``data/cloud``; ``ui/`` never sees a token, REQ-P10-DATA-008). Swapping the
  factory swaps the provider with **no** UI change — the port is the seam.
* The Qt-free **job builders** (``make_save_job`` / ``make_open_job`` /
  ``make_latest_open_job`` / ``make_list_versions_job`` / ``make_restore_job`` /
  ``make_recover_job`` / ``make_autosave_job``) that the
  :class:`~pixelart_creator.ui.cloud_worker.Cloud_Controller` runs off the GUI
  thread. The menu wiring + user prompts live in
  :class:`~pixelart_creator.ui.main_window.Main_Window` (which owns tab / undo
  state); this module holds only the reusable, testable seam.

This module has no user-visible strings of its own (they live on the widgets +
the window, all ``tr()``-wrapped). No ``eval`` / ``exec``: the open/restore path
decodes untrusted bytes through the shipped defensive ``deserialize_project``
(REQ-P10-DATA-006).
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from pixelart_creator.data.cloud import (
    CloudDataError,
    CloudPort,
    FakeCloudAdapter,
    deserialize_project,
    serialize_project,
)
from pixelart_creator.logic.document import Document

#: Factory that builds a fresh :class:`CloudPort` on connect. Injectable so a real
#: provider adapter (or a pre-seeded fake, in tests) replaces the default with no
#: UI change — the port is the provider-agnostic seam (REQ-P10-DATA-007).
CloudPortFactory = Callable[[], CloudPort]


def _default_factory() -> CloudPort:
    """Build the default Slice-A port: an in-memory, connected fake adapter.

    Deterministic, no network, no credentials, no stray files (in-memory mode).
    A filesystem-backed or real adapter — enabling cross-restart recovery and live
    providers — is a drop-in replacement passed to :class:`Cloud_Session`.
    """
    return FakeCloudAdapter(connected=True)


class Cloud_Session(QObject):
    """Provider-agnostic cloud connection state (REQ-P10-UI-004, -007).

    Holds the active :class:`CloudPort` (or ``None`` when disconnected) and a
    factory that builds one on :meth:`connect`. ``ui/`` never sees a provider type
    or a token — only the abstract port and a connected/not-connected flag.
    """

    #: ``(connected,)`` — emitted whenever the connection state changes.
    connectionChanged = Signal(bool)

    def __init__(
        self,
        factory: Optional[CloudPortFactory] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Create a disconnected session bound to ``factory`` (default fake)."""
        super().__init__(parent)
        self._factory: CloudPortFactory = factory or _default_factory
        self._port: Optional[CloudPort] = None

    def connect_provider(self) -> bool:
        """Connect through the port's provider-agnostic surface; return connected.

        Builds the port from the factory (idempotent: a second call reconnects a
        released port). No token is ever handled in ``ui/`` — for a real adapter
        the OAuth flow runs inside ``data/cloud`` and only the browser launch is
        delegated up (REQ-P10-DATA-008). Emits :attr:`connectionChanged`.
        """
        self._port = self._factory()
        connected = self._port.is_connected()
        self.connectionChanged.emit(connected)
        return connected

    def disconnect_provider(self) -> None:
        """Release the active port (provider-agnostic); emit the state change."""
        self._port = None
        self.connectionChanged.emit(False)

    def is_connected(self) -> bool:
        """Return whether a port is bound and reports itself connected."""
        return self._port is not None and self._port.is_connected()

    def port(self) -> Optional[CloudPort]:
        """Return the active :class:`CloudPort`, or ``None`` when disconnected."""
        return self._port


# -- Qt-free job builders (run off the GUI thread by Cloud_Controller) -------


def make_save_job(port: CloudPort, project_id: str, document: Document) -> Callable:
    """Build a job that serialises ``document`` and stores a new cloud version.

    The (potentially large, 8K) serialise happens off the GUI thread via the
    shipped PIO-1 codec (read-only over the document — the export precedent), then
    the bytes are ``put`` through the port. Returns the new
    :class:`~pixelart_creator.logic.version_history.CloudVersion`.
    """

    def job(_cancel: threading.Event) -> object:
        blob = serialize_project(document)
        return port.put(project_id, blob)

    return job


def make_open_job(port: CloudPort, project_id: str, version_id: str) -> Callable:
    """Build a job that fetches a version's bytes and defensively decodes them.

    ``get`` returns untrusted bytes; ``deserialize_project`` validates them through
    the shipped defensive PIO-1 path (size cap + typed/bounds checks; malformed →
    ``CloudDataError``; never ``eval``/``exec`` — REQ-P10-DATA-006). Returns the
    reconstructed Qt-free :class:`~pixelart_creator.logic.document.Document`.
    """

    def job(_cancel: threading.Event) -> object:
        blob = port.get(project_id, version_id)
        return deserialize_project(blob)

    return job


def make_latest_open_job(port: CloudPort, project_id: str) -> Callable:
    """Build a job that opens the *latest* version of ``project_id`` (defensive)."""

    def job(_cancel: threading.Event) -> object:
        latest = port.latest(project_id)
        blob = port.get(project_id, latest.version_id)
        return deserialize_project(blob)

    return job


def make_list_versions_job(port: CloudPort, project_id: str) -> Callable:
    """Build a job that returns the ordered version history of ``project_id``."""

    def job(_cancel: threading.Event) -> object:
        return port.list_versions(project_id)

    return job


def make_restore_job(port: CloudPort, project_id: str, version_id: str) -> Callable:
    """Build a job that fetches + defensively decodes a specific prior version.

    Identical decode discipline to :func:`make_open_job`; the caller (GUI thread)
    opens the reconstructed document into a *new* tab so the current unsaved state
    is never clobbered (REQ-P10-UI-002 / REQ-P10-DATA-004 semantics).
    """
    return make_open_job(port, project_id, version_id)


def make_recover_job(port: CloudPort, project_id: str) -> Callable:
    """Build a job that reads + defensively decodes the RECOVERY-SLOT blob.

    The autosaved working copy lives in the recovery slot, not the version
    history, so it is read via ``get_recovery`` (**not** ``get``, which is a
    version fetch and would raise ``unknown version`` for the slot). Identical
    decode discipline to :func:`make_open_job`: the untrusted bytes are validated
    through the shipped defensive ``deserialize_project`` (size cap + typed/bounds
    checks; never ``eval``/``exec`` — REQ-P10-DATA-006). An empty slot at job time
    surfaces as a ``CloudDataError`` through the standard error→dialog path. The
    caller opens the reconstructed document into a NEW tab (REQ-P10-UI-003).
    """

    def job(_cancel: threading.Event) -> object:
        blob = port.get_recovery(project_id)
        if blob is None:
            raise CloudDataError(
                f"no recovery slot to restore for project {project_id!r}"
            )
        return deserialize_project(blob)

    return job


def make_autosave_job(port: CloudPort, project_id: str, document: Document) -> Callable:
    """Build a job that writes ``document`` to the port's recovery slot.

    The recovery slot is distinct from the explicit version history, so an
    autosave never creates a user-visible version and never clobbers the last
    explicit save (REQ-P10-DATA-004). Returns ``None`` (the write is the effect).
    """

    def job(_cancel: threading.Event) -> object:
        blob = serialize_project(document)
        port.put_recovery(project_id, blob)
        return None

    return job
