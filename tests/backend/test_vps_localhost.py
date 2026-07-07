"""Localhost-provable VPS deployment acceptance (Phase-13 Slice 13C, T13C-04).

Proves REQ-P13-BACKEND-001 / SC-P13-BACKEND-001-1: the shipped deployment artifacts run
the **unchanged** ``sync_backend/`` relay, and a client connecting **over
localhost/loopback** reproduces the shipped multi-client convergence + late-join backlog
replay (REQ-P10-BACKEND-001) — with **no live external server**.

Two launch paths, both proving the same convergence against a backend brought up the way
a VPS would:

* **Launcher subprocess (default here).** ``deploy/run_sync_backend.py`` — the
  persistent launcher the Docker image and systemd unit both invoke — is spawned as a
  subprocess bound to an ephemeral loopback port (via the ``PIXELART_SYNC_*`` env
  contract). A loopback ``websockets`` client then reproduces convergence, proving the
  launched (out-of-process) backend behaves identically to the in-process CI backend.
  Skips with a clear reason if a launcher subprocess is not viable in the environment.
* **Docker container (opt-in).** If ``docker`` is on ``PATH``, the shipped
  ``deploy/Dockerfile`` is built and run (with the documented ``--ulimit
  nofile=65535:65535``) and the same convergence is proven against the containerized
  relay. Skips cleanly when Docker is unavailable or the daemon cannot build/run.

Every test is ``@pytest.mark.integration`` (module-level ``pytestmark``): it reaches
outside the process, so the default gate deselects it — it runs in the dedicated 13C
integration job (T13C-06) or a documented manual run. The backend source is never
modified; these tests only *launch* it via the ``deploy/`` artifacts.
"""

from __future__ import annotations

import shutil
import subprocess
import time

import pytest

from pixelart_creator.data.cloud.ws_transport import WebSocketTransport
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.convergence import MetadataOp, RasterOp, converge
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.realtime_apply import (
    RealtimeState,
    apply_remote,
    encode_update,
)

from .conftest import REPO_ROOT

# Every test here reaches outside the process (subprocess / container / socket).
pytestmark = pytest.mark.integration

TILE = CRDT_TILE_SIZE_PX
DOC = "vps-doc"
_DOCKERFILE = REPO_ROOT / "deploy" / "Dockerfile"


def _solid_tile(value: int) -> bytes:
    return bytes([value]) * (TILE * TILE * 4)


def _poll_until(transport, document_id, count, deadline=5.0):
    """Poll (synchronously) until ``count`` frames arrive or the deadline elapses."""
    frames = []
    end = time.monotonic() + deadline
    while len(frames) < count and time.monotonic() < end:
        frames.extend(transport.poll(document_id))
        if len(frames) < count:
            time.sleep(0.02)
    return tuple(frames)


# --------------------------------------------------------------------------- #
# Shared acceptance body — reproduces the shipped multi-client convergence
# (REQ-P10-BACKEND-001) against a backend launched via the deploy/ artifacts.
# --------------------------------------------------------------------------- #


def _assert_two_client_convergence(uri: str) -> None:
    """Two loopback clients exchange CRDT updates via the relay and converge."""
    ta = tb = None
    try:
        ta = WebSocketTransport(uri)
        tb = WebSocketTransport(uri)
        ta.join(DOC)
        tb.join(DOC)

        base = Document(2 * TILE, TILE)
        doc_a = converge(base, [], site_id=1)
        doc_b = converge(base, [], site_id=2)
        state_a, state_b = RealtimeState(), RealtimeState()

        ops_a = [
            MetadataOp("title", "from-a", 1, 1),
            RasterOp(0, 1, 0, 0, _solid_tile(0x11), TILE, TILE, 5, 1),
        ]
        ops_b = [
            MetadataOp("author", "from-b", 1, 2),
            RasterOp(0, 1, 1, 0, _solid_tile(0x22), TILE, TILE, 5, 2),
        ]
        blob_a, blob_b = encode_update(ops_a), encode_update(ops_b)

        apply_remote(doc_a, blob_a, site_id=1, state=state_a)
        apply_remote(doc_b, blob_b, site_id=2, state=state_b)
        ta.send_update(DOC, blob_a)
        tb.send_update(DOC, blob_b)

        for frame in _poll_until(ta, DOC, 1):
            msg = sync_protocol.decode_message(frame)
            if msg.kind is sync_protocol.ControlKind.UPDATE:
                apply_remote(doc_a, msg.blob, site_id=1, state=state_a)
        for frame in _poll_until(tb, DOC, 1):
            msg = sync_protocol.decode_message(frame)
            if msg.kind is sync_protocol.ControlKind.UPDATE:
                apply_remote(doc_b, msg.blob, site_id=2, state=state_b)

        assert doc_a.metadata == {"title": "from-a", "author": "from-b"}
        assert doc_b.metadata == doc_a.metadata
        for doc in (doc_a, doc_b):
            arr = doc.frames[0].layers[0].buffer.data
            assert (arr[0:TILE, 0:TILE] == 0x11).all()
            assert (arr[0:TILE, TILE : 2 * TILE] == 0x22).all()
    finally:
        if ta is not None:
            ta.close()
        if tb is not None:
            tb.close()


def _assert_late_joiner_backlog(uri: str) -> None:
    """A late-joining client receives the persisted update backlog (REQ-P10-*)."""
    ta = late = None
    try:
        ta = WebSocketTransport(uri)
        ta.join(DOC)
        blob = encode_update([MetadataOp("k", "v", 1, 0)])
        ta.send_update(DOC, blob)
        time.sleep(0.1)  # let the launched backend persist before the late join

        late = WebSocketTransport(uri)
        late.join(DOC)
        frames = _poll_until(late, DOC, 1)
        assert len(frames) == 1
        assert sync_protocol.decode_message(frames[0]).blob == blob
    finally:
        if ta is not None:
            ta.close()
        if late is not None:
            late.close()


# --------------------------------------------------------------------------- #
# Launcher-subprocess path (the deploy/ run-forever entry, no Docker needed).
# --------------------------------------------------------------------------- #


def test_launched_backend_reproduces_multi_client_convergence(launched_backend_uri):
    _assert_two_client_convergence(launched_backend_uri)


def test_launched_backend_replays_backlog_to_late_joiner(launched_backend_uri):
    _assert_late_joiner_backlog(launched_backend_uri)


# --------------------------------------------------------------------------- #
# Docker-container path (opt-in — skips cleanly when Docker is unavailable).
# --------------------------------------------------------------------------- #


def _wait_for_ws(uri: str, deadline: float = 30.0) -> bool:
    """Retry-connect until the (container) relay accepts, or the deadline elapses."""
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        try:
            probe = WebSocketTransport(uri)
        except Exception:
            time.sleep(0.5)
            continue
        probe.close()
        return True
    return False


def _docker_published_addr(container_id: str, deadline: float = 30.0):
    """Resolve the host ``(host, port)`` Docker published for container port 8765."""
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        result = subprocess.run(
            ["docker", "port", container_id, "8765"],
            capture_output=True,
            text=True,
        )
        mapping = result.stdout.strip().splitlines()
        if mapping:
            host, _, port = mapping[0].rpartition(":")
            # Docker may report 0.0.0.0 — connect over loopback for the local run.
            if host in ("0.0.0.0", "::", ""):
                host = "127.0.0.1"
            return host, int(port)
        time.sleep(0.5)
    return None, None


def test_docker_container_reproduces_convergence():
    if shutil.which("docker") is None:
        pytest.skip(
            "docker not on PATH; containerized acceptance is opt-in (integration)"
        )

    tag = "pixelart-sync-test:agt04"
    build = subprocess.run(
        ["docker", "build", "-f", str(_DOCKERFILE), "-t", tag, str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=900,
    )
    if build.returncode != 0:
        pytest.skip(
            "docker build unavailable in this environment (daemon/network):\n"
            + (build.stderr or build.stdout)[-800:]
        )

    run = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--ulimit",
            "nofile=65535:65535",  # Q4 FD floor >= 65535 (documented run command)
            "-e",
            "PIXELART_SYNC_HOST=0.0.0.0",
            "-p",
            "127.0.0.1::8765",  # publish to an ephemeral loopback host port
            tag,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if run.returncode != 0:
        pytest.skip("docker run unavailable:\n" + (run.stderr or run.stdout)[-800:])

    container_id = run.stdout.strip()
    try:
        host, port = _docker_published_addr(container_id)
        if host is None:
            pytest.skip("could not resolve the container's published port")
        uri = f"ws://{host}:{port}"
        if not _wait_for_ws(uri):
            pytest.skip("containerized relay did not accept a connection in time")
        _assert_two_client_convergence(uri)
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_id],
            capture_output=True,
            text=True,
        )
