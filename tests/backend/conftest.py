"""Shared config for the sync-backend integration tests (localhost, no Qt).

These tests spin up :class:`~sync_backend.server.SyncServer` in-process on an ephemeral
loopback port (REQ-P10-BACKEND-001) and drive it with the blocking ``websockets`` sync
client from an executor thread (per AGT-03's harness note), so the server's asyncio
event loop stays free on the main thread. Every scenario runs under a single
``asyncio.run`` and stops the server in a ``finally`` block, and every client poll has a
bounded deadline, so no event loop, asyncio task, or listening socket leaks between
tests — safe under ``pytest -n auto``.
"""

from __future__ import annotations
