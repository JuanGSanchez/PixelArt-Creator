# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Persistent launch entry for the shipped ``sync_backend/`` relay on a VPS.

Phase-13 (REQ-P13-BACKEND-001, research finding Q4). The shipped
:class:`sync_backend.server.SyncServer` is CI-shaped: it exposes ``async start()``
(bind an ephemeral loopback port, return the bound address) and ``async stop()`` but
has **no** ``__main__``/run-forever entry — and per REQ-P13-BACKEND-001 the backend
source **must stay byte-unmodified**. This launcher therefore lives *outside*
``sync_backend/`` (under ``deploy/``): it imports the unchanged ``SyncServer`` +
``UpdateStore``, binds them to a VPS-facing host/port from the environment, starts the
relay, and then blocks forever with a graceful ``SIGTERM``/``SIGINT`` → ``stop()``
shutdown so a container or systemd service stops cleanly.

Runtime surface is deliberately tiny — stdlib + ``websockets`` only, via the pure
``pixelart_creator.logic`` framing the backend already uses. It imports **no** Qt, no
``pixelart_creator.ui``, no ``pixelart_creator.data``: the whole import chain
(``SyncServer`` -> ``logic.sync_protocol`` -> ``logic.cloud_validation`` ->
``logic.constants``) is Qt-free and needs only ``websockets`` installed.

Environment contract (both consumed by :func:`build_server`):
    ``PIXELART_SYNC_HOST`` — bind host. Default ``0.0.0.0`` (VPS-facing, per Q4; the
        backend's own default is loopback ``127.0.0.1``, which is CI-only).
    ``PIXELART_SYNC_PORT`` — bind port. Default ``8765``. ``0`` still picks an
        ephemeral free port (useful for a localhost integration test).

Run directly:  ``python deploy/run_sync_backend.py``
(with the repo root on ``PYTHONPATH`` so ``sync_backend`` + ``pixelart_creator``
resolve — the Docker image and systemd unit both set this).
"""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Optional, Tuple

from sync_backend.server import SyncServer
from sync_backend.store import UpdateStore

__all__ = [
    "HOST_ENV",
    "PORT_ENV",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "build_server",
    "run",
    "main",
]

#: Environment variable naming the bind host.
HOST_ENV = "PIXELART_SYNC_HOST"
#: Environment variable naming the bind port.
PORT_ENV = "PIXELART_SYNC_PORT"

#: Default bind host — ``0.0.0.0`` so the relay is reachable on the VPS's public
#: interface (Q4: "bind 0.0.0.0, not localhost"). This overrides the backend's own
#: loopback default, which exists only for the in-process CI gate.
DEFAULT_HOST = "0.0.0.0"
#: Default bind port. The relay serves plain WS here; in production the Nginx
#: reverse proxy (``deploy/nginx-sync.conf``) terminates TLS and proxies WSS -> this.
DEFAULT_PORT = 8765


def _resolve_host() -> str:
    """Return the bind host from :data:`HOST_ENV`, or :data:`DEFAULT_HOST`."""
    return os.environ.get(HOST_ENV, DEFAULT_HOST)


def _resolve_port() -> int:
    """Return the bind port from :data:`PORT_ENV`, or :data:`DEFAULT_PORT`.

    Raises:
        ValueError: If the environment value is set but not a valid integer.
    """
    raw = os.environ.get(PORT_ENV)
    if raw is None or raw == "":
        return DEFAULT_PORT
    return int(raw)


def build_server() -> SyncServer:
    """Construct the unchanged :class:`SyncServer` bound to the env host/port.

    A fresh in-memory :class:`~sync_backend.store.UpdateStore` backs the relay (the
    shipped default); a real deployment can swap in a durable store behind the same
    interface without touching the backend source.
    """
    return SyncServer(
        host=_resolve_host(),
        port=_resolve_port(),
        store=UpdateStore(),
    )


async def run(server: Optional[SyncServer] = None) -> Tuple[str, int]:
    """Start the relay, block until a stop signal, then stop it gracefully.

    Args:
        server: An optional pre-built server (an integration test may inject one
            bound to loopback/ephemeral port). Defaults to :func:`build_server`.

    Returns:
        The bound ``(host, port)`` the relay listened on (returned after clean
        shutdown, so a test can assert it started).
    """
    if server is None:
        server = build_server()

    bound = await server.start()
    print(f"pixelart sync-backend listening on ws://{bound[0]}:{bound[1]}", flush=True)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, ValueError):
            # add_signal_handler is unavailable on some platforms (e.g. Windows) or
            # off the main thread; graceful stop then relies on KeyboardInterrupt
            # below. The Linux VPS deployment (Docker/systemd) always registers.
            pass

    try:
        await stop_event.wait()
    except (
        KeyboardInterrupt,
        asyncio.CancelledError,
    ):  # pragma: no cover - signal path
        pass
    finally:
        print("pixelart sync-backend shutting down", flush=True)
        await server.stop()
    return bound


def main() -> None:
    """Console entry: run the relay forever until SIGTERM/SIGINT."""
    try:
        asyncio.run(run())
    except KeyboardInterrupt:  # pragma: no cover - Ctrl-C on the event loop
        pass


if __name__ == "__main__":
    main()
