"""Python integration tests for the ``web_viewer`` share-token viewer path.

ADR-0036 §1 + Addendum A; spec
REQ-P13-WEB-002/-005; acceptance SC-P13-WEB-005-1/-2, SC-P13-WEB-002-1. These are
Qt-free, in-process integration tests: they spin up the shipped
:class:`~sync_backend.server.SyncServer` in **web-viewer token mode**
(``share_secret=…``) on an ephemeral loopback port and drive it with the real
``websockets`` client, exactly mirroring the ``tests/backend`` harness. They exercise
the pure :mod:`~pixelart_creator.logic.share_token` seam AND the live token-enforcing
handshake, so both the mint/verify surface and the ``process_request`` gate are proven
together. No external server is needed (the in-process backend suffices), so this suite
runs in the DEFAULT gate — NOT under the ``integration`` marker.
"""

from __future__ import annotations

__all__: list[str] = []
