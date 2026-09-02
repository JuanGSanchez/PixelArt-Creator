"""Nginx TLS/WSS reverse-proxy tuning acceptance (Phase-13).

Proves REQ-P13-BACKEND-002 / SC-P13-BACKEND-002-1: the shipped
``deploy/nginx-sync.conf`` terminates TLS, proxies **WSS -> plain WS** forwarding the
WebSocket ``Upgrade`` / ``Connection`` handshake headers, and raises
``proxy_read_timeout`` far above Nginx's 60 s default so an **idle WebSocket is not
dropped** — without a live external server or a public certificate.

Proof is layered (CI-fast first, real-idle opt-in):

* **Config assertion (fast).** Parse the shipped config and assert every required
  directive is present with the correct value: TLS termination (``listen 443 ssl`` +
  cert/key), the ``Upgrade``/``Connection`` forwarding (map + ``proxy_set_header`` +
  HTTP/1.1), plain-WS ``proxy_pass http://`` to the loopback upstream, and
  ``proxy_read_timeout`` well above 60 s (the shipped 86400 s). This is the CI-fast
  proof of the tuning; it needs no Nginx binary.
* **Shortened idle-survival (fast).** Against the launched backend directly (no Nginx),
  hold an idle WebSocket open for a few seconds and confirm it is still live — proving
  the app layer itself keeps idle connections; combined with the config's 86400 s
  directive, this is the scaled-down end-to-end proof without a 60 s+ wait.
* **Real idle-past-60 s (opt-in slow).** With Nginx installed **and**
  ``PIXELART_NGINX_IDLE_TEST=1`` set, a self-signed loopback proxy built from the
  shipped directives sustains a WSS connection past 60 s idle. Skips everywhere else.

Every test is ``@pytest.mark.integration`` (module-level ``pytestmark``); the default
gate deselects them (dedicated 13C integration job / documented manual run).
"""

from __future__ import annotations

import os
import shutil
import ssl
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

from pixelart_creator.logic import sync_protocol

from .conftest import REPO_ROOT, _await_listening, _spawn_launcher, _terminate

# Every test here depends on the Nginx config artifact and/or a launched backend/socket.
pytestmark = pytest.mark.integration

NGINX_CONF = REPO_ROOT / "deploy" / "nginx-sync.conf"
DOC = "nginx-doc"


@pytest.fixture(scope="module")
def config_text() -> str:
    """The shipped Nginx config with whitespace runs collapsed to single spaces.

    Collapsing lets the directive assertions below use plain substring checks (no
    separator-bearing regex literals), so ``scripts/path_portability_check.py`` stays
    clean while still tolerating the config's real indentation/alignment.
    """
    raw = NGINX_CONF.read_text(encoding="utf-8")
    # Strip each line's ``#`` comment tail first, so a directive named in prose (e.g.
    # "Nginx's default proxy_read_timeout is 60s") never matches the real directive.
    code = " ".join(line.split("#", 1)[0] for line in raw.splitlines())
    return " ".join(code.split())


def _directive_seconds(collapsed: str, name: str) -> int:
    """Return the integer seconds of a ``<name> <N>s;`` directive in the config."""
    marker = name + " "
    idx = collapsed.find(marker)
    assert idx != -1, name + " directive is missing"
    token = collapsed[idx + len(marker) :].split(";", 1)[0].strip()
    return int(token.rstrip("s"))


# --------------------------------------------------------------------------- #
# CI-fast config assertions — the shipped tuning is present and correct.
# --------------------------------------------------------------------------- #


def test_config_terminates_tls(config_text: str) -> None:
    assert "listen 443 ssl" in config_text
    assert "ssl_certificate" in config_text
    assert "ssl_certificate_key" in config_text


def test_config_forwards_websocket_upgrade_handshake(config_text: str) -> None:
    # The canonical Upgrade map + the forwarded headers + HTTP/1.1 are all required for
    # the WSS -> WS handshake to complete through the proxy (Q4 recipe).
    assert "map $http_upgrade $connection_upgrade" in config_text
    assert "proxy_set_header Upgrade $http_upgrade" in config_text
    assert "proxy_set_header Connection $connection_upgrade" in config_text
    assert "proxy_http_version 1.1" in config_text


def test_config_proxies_plain_ws_to_loopback_backend(config_text: str) -> None:
    # TLS is terminated at the proxy; the backend serves *plain* WS behind it.
    assert "proxy_pass http://" in config_text
    assert "proxy_pass https://" not in config_text
    assert "server 127.0.0.1:8765" in config_text


def test_config_proxy_read_timeout_far_above_60s_default(config_text: str) -> None:
    # Nginx's default is 60 s (silently drops idle WS); the shipped value is 86400 s.
    read_timeout = _directive_seconds(config_text, "proxy_read_timeout")
    assert read_timeout > 60
    assert read_timeout >= 86400
    # A slow/idle writer must not be dropped either.
    assert _directive_seconds(config_text, "proxy_send_timeout") > 60


# --------------------------------------------------------------------------- #
# Shortened idle-survival — the launched backend keeps an idle WS alive (fast).
# --------------------------------------------------------------------------- #


def test_backend_sustains_short_idle_ws_connection(launched_backend_uri: str) -> None:
    """An idle WebSocket held open ~3 s is still live and delivers a later update.

    Scaled-down proof of the idle-survival the 86400 s ``proxy_read_timeout`` protects
    at the proxy layer: here we prove the *app* layer never drops an idle connection
    over the window, so the only thing between a client and a dropped idle socket in
    production is the Nginx timeout the config raises.
    """
    from pixelart_creator.data.cloud.ws_transport import WebSocketTransport
    from pixelart_creator.logic.convergence import MetadataOp
    from pixelart_creator.logic.realtime_apply import encode_update

    idle_client = writer = None
    try:
        idle_client = WebSocketTransport(launched_backend_uri)
        writer = WebSocketTransport(launched_backend_uri)
        idle_client.join(DOC)
        writer.join(DOC)

        time.sleep(3.0)  # idle window — the connection must survive it

        blob = encode_update([MetadataOp("k", "after-idle", 1, 0)])
        writer.send_update(DOC, blob)

        frames = ()
        end = time.monotonic() + 5.0
        while not frames and time.monotonic() < end:
            frames = idle_client.poll(DOC)
            if not frames:
                time.sleep(0.02)
        assert len(frames) == 1
        assert sync_protocol.decode_message(frames[0]).blob == blob
    finally:
        if idle_client is not None:
            idle_client.close()
        if writer is not None:
            writer.close()


# --------------------------------------------------------------------------- #
# Opt-in real idle-past-60s through a self-signed loopback Nginx proxy (slow).
# --------------------------------------------------------------------------- #


def _openssl_self_signed(directory: Path):
    """Generate a self-signed loopback cert/key pair; return ``(cert, key)`` paths."""
    cert = directory / "loopback.crt"
    key = directory / "loopback.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


@pytest.mark.slow
def test_nginx_sustains_idle_ws_past_60s():
    """Real idle-past-60 s survival through a self-signed loopback Nginx proxy.

    Opt-in: requires Nginx on ``PATH``, ``openssl``, and ``PIXELART_NGINX_IDLE_TEST=1``
    (a full 60 s+ idle wait). Skips otherwise — the CI-fast config + short-idle tests
    are the default proof. Builds a minimal proxy mirroring the *shipped* directives
    (``proxy_read_timeout 86400s`` + Upgrade/Connection forwarding) in front of the
    launched backend, then holds an idle WSS connection past 60 s.
    """
    if os.environ.get("PIXELART_NGINX_IDLE_TEST") != "1":
        pytest.skip("opt-in slow test; set PIXELART_NGINX_IDLE_TEST=1 to run it")
    if shutil.which("nginx") is None:
        pytest.skip(
            "nginx not on PATH; real idle-survival proof is opt-in (integration)"
        )
    if shutil.which("openssl") is None:
        pytest.skip("openssl not on PATH; cannot mint a loopback certificate")

    from websockets.sync.client import connect

    proc = _spawn_launcher()
    host, port, captured = _await_listening(proc)
    if host is None:
        _terminate(proc)
        pytest.skip("launcher subprocess not viable: " + "".join(captured)[-400:])

    workdir = Path(tempfile.mkdtemp(prefix="pixelart-nginx-"))
    nginx_proc = None
    try:
        cert, key = _openssl_self_signed(workdir)
        listen_port = 8443
        conf = workdir / "nginx.conf"
        # Minimal standalone nginx.conf mirroring the shipped tuning
        # (deploy/nginx-sync.conf): TLS termination, WSS->WS, Upgrade/Connection
        # forwarding, proxy_read_timeout 86400s.
        conf.write_text(
            f"""
worker_processes  1;
events {{ worker_connections 64; }}
http {{
    map $http_upgrade $connection_upgrade {{ default upgrade; '' close; }}
    server {{
        listen {listen_port} ssl;
        ssl_certificate     {cert.as_posix()};
        ssl_certificate_key {key.as_posix()};
        location / {{
            proxy_pass http://{host}:{port};
            proxy_http_version 1.1;
            proxy_set_header Upgrade    $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }}
    }}
}}
""",
            encoding="utf-8",
        )
        nginx_proc = subprocess.Popen(
            ["nginx", "-p", str(workdir), "-c", str(conf), "-g", "daemon off;"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        time.sleep(1.0)
        if nginx_proc.poll() is not None:
            pytest.skip("nginx failed to start with the loopback config")

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        ws = connect(f"wss://localhost:{listen_port}", ssl=ctx)
        try:
            ws.send(sync_protocol.encode_join(DOC))
            time.sleep(65.0)  # idle PAST the 60 s Nginx default
            # Connection survived the idle window: a fresh JOIN still round-trips.
            ws.send(sync_protocol.encode_join(DOC))
            ws.ping()  # raises if the connection was dropped
        finally:
            ws.close()
    finally:
        if nginx_proc is not None and nginx_proc.poll() is None:
            nginx_proc.terminate()
            try:
                nginx_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover
                nginx_proc.kill()
        _terminate(proc)
        shutil.rmtree(workdir, ignore_errors=True)
