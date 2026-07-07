"""Shared config for the sync-backend integration tests (localhost, no Qt).

These tests spin up :class:`~sync_backend.server.SyncServer` in-process on an ephemeral
loopback port (REQ-P10-BACKEND-001) and drive it with the blocking ``websockets`` sync
client from an executor thread (per AGT-03's harness note), so the server's asyncio
event loop stays free on the main thread. Every scenario runs under a single
``asyncio.run`` and stops the server in a ``finally`` block, and every client poll has a
bounded deadline, so no event loop, asyncio task, or listening socket leaks between
tests — safe under ``pytest -n auto``.

Phase-13 Slice 13C additions (REQ-P13-BACKEND-001/-002). The VPS artifacts are proven
by **launching the shipped, unmodified** ``sync_backend/`` the way a container / systemd
unit does — through the ``deploy/run_sync_backend.py`` launcher as a *subprocess* bound
to an ephemeral loopback port (``PIXELART_SYNC_PORT=0``). The helpers below spawn that
launcher, parse its "listening on ws://host:port" line, and tear it down; the
``launched_backend_uri`` fixture yields a ``ws://`` URI (or skips with a clear reason if
a launcher subprocess is not viable in the environment). These paths are only exercised
by ``@pytest.mark.integration`` tests, deselected in the default gate.
"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

#: Repo root: tests/backend/conftest.py -> parents[2] is the working tree root.
REPO_ROOT = Path(__file__).resolve().parents[2]
#: The Phase-13 Slice 13C persistent launcher (deploy/, outside sync_backend/).
LAUNCHER = REPO_ROOT / "deploy" / "run_sync_backend.py"

#: The launcher prints ``pixelart sync-backend listening on ws://<host>:<port>``.
_LISTEN_RE = re.compile(r"listening on ws://(?P<host>[^:\s]+):(?P<port>\d+)")


def _spawn_launcher() -> subprocess.Popen:
    """Spawn ``deploy/run_sync_backend.py`` bound to an ephemeral loopback port.

    Mirrors the Docker/systemd launch (repo root on ``PYTHONPATH``, unbuffered stdout),
    but pins the bind to ``127.0.0.1`` and an ephemeral port so the acceptance run never
    opens an external socket. Returns the running process (stdout is a text pipe).
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    env["PIXELART_SYNC_HOST"] = "127.0.0.1"
    env["PIXELART_SYNC_PORT"] = "0"
    return subprocess.Popen(
        [sys.executable, str(LAUNCHER)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )


def _await_listening(
    proc: subprocess.Popen, deadline: float = 20.0
) -> Tuple[Optional[str], Optional[int], List[str]]:
    """Read the launcher's stdout until it reports its bound address.

    A daemon reader thread drains stdout into a queue (so the child never blocks on a
    full pipe) while the main thread watches for the "listening on" line within the
    deadline. Returns ``(host, port, captured_lines)``; ``host`` is ``None`` if the
    launcher never reported a listening address (dead process / import failure).
    """
    lines: "queue.Queue[Optional[str]]" = queue.Queue()

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=_reader, daemon=True).start()

    captured: List[str] = []
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        try:
            line = lines.get(timeout=0.2)
        except queue.Empty:
            if proc.poll() is not None:
                break  # process exited before announcing an address
            continue
        if line is None:
            break
        captured.append(line)
        match = _LISTEN_RE.search(line)
        if match:
            return match.group("host"), int(match.group("port")), captured
    return None, None, captured


def _terminate(proc: subprocess.Popen) -> None:
    """Stop the launcher subprocess (graceful SIGTERM where supported, else kill)."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - stubborn child
            proc.kill()
            proc.wait(timeout=10)


@pytest.fixture()
def launched_backend_uri():
    """Yield a ``ws://`` URI for a freshly launched, unmodified backend, or skip.

    Skips (never errors) with a clear reason if the launcher subprocess cannot be
    brought up in this environment — these are ``integration`` tests, not default-gate.
    """
    proc = _spawn_launcher()
    host, port, captured = _await_listening(proc)
    if host is None:
        _terminate(proc)
        pytest.skip(
            "deploy/run_sync_backend.py did not report a listening address; a launcher "
            "subprocess is not viable here (integration-only). Captured output: "
            + "".join(captured)[-500:]
        )
    try:
        yield f"ws://{host}:{port}"
    finally:
        _terminate(proc)
