"""Tests for ``web_viewer.dev_server`` — the LOCAL-DEV-ONLY static file server.

Closes the ``web_viewer`` half of the time-boxed non-client coverage exception (issue
#32, ci.yml "Coverage gate — non-client packages", expires 2026-08-31).
``dev_server.py`` is explicitly documented as dev-only, never production (module
docstring, ADR-0035 §1) — production static serving is the Nginx ``location`` block
These tests
therefore prove only what the module genuinely guarantees:

* it binds loopback-only by default (never ``0.0.0.0``) — the "local-only binding
  posture";
* it serves the shipped ``static/`` assets with the correct, explicitly-pinned content
  types (``.js``/``.mjs`` -> ``text/javascript``) and a ``no-store`` cache header (a
  dev-loop convenience, not a production caching policy);
* a request path that attempts to escape ``static/`` (``../../../etc/passwd``, both raw
  and percent-encoded) is refused — it never serves a file outside the static root;
* the CLI wiring (``main``) parses ``--host``/``--port``, refuses to start when the
  static asset directory is missing, and shuts down cleanly on ``KeyboardInterrupt``
  (the only way the process is ever stopped in normal dev use, Ctrl-C).

No test asserts a production-hardening guarantee this module never makes (auth,
TLS, directory-listing suppression beyond stdlib's own, concurrent-load behaviour).
Every server test binds to an EPHEMERAL loopback port (``0``) — never a fixed port —
so nothing here can collide with another process, in CI or locally.
"""

from __future__ import annotations

import http.client
import socket
import threading
import time
from http.server import ThreadingHTTPServer

import pytest

from web_viewer import dev_server

# --------------------------------------------------------------------------- #
# Helpers: start/stop a real server on an ephemeral loopback port.
# --------------------------------------------------------------------------- #


def _wait_until_accepting(host: str, port: int, deadline: float = 5.0) -> None:
    """Poll (bounded) until ``(host, port)`` accepts a TCP connection.

    The listening socket exists as soon as :func:`~web_viewer.dev_server.build_server`
    returns (bind+listen happen in the server's ``__init__``), but requests are only
    actually handled once ``serve_forever`` is running on its thread. This bounded poll
    (never an unconditional sleep) makes the fixture deterministic without depending on
    any specific thread-scheduling latency.
    """
    end = time.monotonic() + deadline
    last_exc = None
    while time.monotonic() < end:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError as exc:
            last_exc = exc
            time.sleep(0.01)
    raise AssertionError(f"dev server never began accepting connections: {last_exc!r}")


@pytest.fixture()
def running_server():
    """Yield ``(host, port)`` of a real, running dev server on an ephemeral port."""
    httpd = dev_server.build_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host = str(httpd.server_address[0])
    port = int(httpd.server_address[1])
    _wait_until_accepting(host, port)
    try:
        yield host, port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _get(host: str, port: int, path: str, *, raw_path: bool = False):
    """Issue one raw GET and return ``(status, headers_dict, body_bytes)``.

    ``raw_path=True`` sends ``path`` on the wire UNNORMALIZED (bypassing any client-side
    ``..`` collapsing), which is required to prove the server itself — not the HTTP
    client — refuses a traversal attempt.
    """
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        if raw_path:
            conn.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"{host}:{port}")
            conn.endheaders()
        else:
            conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, dict(resp.getheaders()), body
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Local-only binding posture.
# --------------------------------------------------------------------------- #


class TestBindingPosture:
    def test_default_host_is_loopback_not_wildcard(self):
        # The documented guarantee (module docstring): a dev server never opens an
        # external port. Confirms the constant a caller relies on when omitting --host.
        assert dev_server._DEFAULT_HOST == "127.0.0.1"
        assert dev_server._DEFAULT_HOST != "0.0.0.0"

    def test_build_server_binds_the_requested_loopback_host_and_ephemeral_port(self):
        httpd = dev_server.build_server("127.0.0.1", 0)
        try:
            assert isinstance(httpd, ThreadingHTTPServer)
            host, port = httpd.server_address[0], httpd.server_address[1]
            assert host == "127.0.0.1"
            assert port > 0  # the OS assigned a real ephemeral port
        finally:
            httpd.server_close()


# --------------------------------------------------------------------------- #
# Content-type pinning + cache header (dev-loop convenience).
# --------------------------------------------------------------------------- #


class TestContentTypesAndHeaders:
    def test_extensions_map_pins_js_and_mjs_to_text_javascript(self):
        # The exact guarantee the class docstring makes: browsers refuse to execute an
        # ES module served with a non-JS MIME type, so .js/.mjs are pinned explicitly
        # rather than left to the host's mimetypes registry.
        handler = dev_server._StaticHandler
        assert handler.extensions_map[".js"] == "text/javascript"
        assert handler.extensions_map[".mjs"] == "text/javascript"

    def test_served_html_has_html_content_type(self, running_server):
        host, port = running_server
        status, headers, body = _get(host, port, "/index.html")
        assert status == 200
        assert headers["Content-type"].startswith("text/html")
        assert b"<html" in body.lower()

    def test_served_js_file_uses_pinned_javascript_content_type(self, running_server):
        host, port = running_server
        status, headers, _ = _get(host, port, "/viewer.js")
        assert status == 200
        assert headers["Content-type"] == "text/javascript"

    def test_served_mjs_file_uses_pinned_javascript_content_type(self, running_server):
        host, port = running_server
        status, headers, _ = _get(host, port, "/viewer_core.mjs")
        assert status == 200
        assert headers["Content-type"] == "text/javascript"

    def test_every_response_carries_no_store_cache_control(self, running_server):
        host, port = running_server
        for path in ("/index.html", "/viewer.js", "/does-not-exist.xyz"):
            _, headers, _ = _get(host, port, path)
            assert headers["Cache-Control"] == "no-store", path


# --------------------------------------------------------------------------- #
# Path handling: unknown files + traversal refusal.
# --------------------------------------------------------------------------- #


class TestPathHandling:
    def test_unknown_file_returns_404(self, running_server):
        host, port = running_server
        status, _, _ = _get(host, port, "/does-not-exist.xyz")
        assert status == 404

    def test_raw_dotdot_traversal_is_refused(self, running_server):
        host, port = running_server
        status, _, body = _get(host, port, "/../../../../etc/passwd", raw_path=True)
        # Never a 200 with file content from outside static/: SimpleHTTPRequestHandler's
        # translate_path strips ".." path components before resolving the filesystem
        # path, so the request lands (at worst) back inside static/ where the file does
        # not exist -> 404, never an escape.
        assert status != 200
        assert b"root:" not in body  # never /etc/passwd content, whatever the status

    def test_percent_encoded_traversal_is_refused(self, running_server):
        host, port = running_server
        status, _, body = _get(
            host, port, "/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd", raw_path=True
        )
        assert status != 200
        assert b"root:" not in body

    def test_traversal_attempt_does_not_break_subsequent_valid_requests(
        self, running_server
    ):
        # The refusal must not wedge the server: a normal request right after a
        # traversal attempt on the SAME server still succeeds.
        host, port = running_server
        _get(host, port, "/../../etc/passwd", raw_path=True)
        status, _, body = _get(host, port, "/index.html")
        assert status == 200
        assert b"<html" in body.lower()


# --------------------------------------------------------------------------- #
# CLI wiring (main): argument parsing, missing-asset-dir refusal, clean shutdown.
# --------------------------------------------------------------------------- #


class TestMain:
    def test_missing_static_root_refuses_to_start(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(dev_server, "_STATIC_ROOT", tmp_path / "does-not-exist")
        with pytest.raises(SystemExit) as excinfo:
            dev_server.main([])
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "static asset directory not found" in err

    def test_invalid_port_argument_is_rejected_by_argparse(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            dev_server.main(["--port", "not-an-int"])
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "--port" in err

    def test_main_binds_requested_port_and_handles_keyboard_interrupt(
        self, monkeypatch, capsys
    ):
        # serve_forever() blocks forever by design (until Ctrl-C); the ONLY thing
        # simulated is that interrupt signal, via the same exception the real Ctrl-C
        # delivers, so the real bind + real print + real except-block all run for real.
        def _raise_keyboard_interrupt(self):
            raise KeyboardInterrupt

        monkeypatch.setattr(
            dev_server.ThreadingHTTPServer, "serve_forever", _raise_keyboard_interrupt
        )
        rc = dev_server.main(["--host", "127.0.0.1", "--port", "0"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "LOCAL DEV ONLY" in out
        assert "127.0.0.1" in out
        assert "shutting down" in out

    def test_main_uses_default_host_and_port_when_omitted(self, monkeypatch, capsys):
        # Force the DEFAULT port to an ephemeral one for this assertion so the test
        # never depends on a fixed real port (8000) being free in CI/local. Proves the
        # argparse defaults are wired from _DEFAULT_HOST/_DEFAULT_PORT, not hardcoded
        # in main() itself.
        monkeypatch.setattr(dev_server, "_DEFAULT_PORT", 0)

        def _raise_keyboard_interrupt(self):
            raise KeyboardInterrupt

        monkeypatch.setattr(
            dev_server.ThreadingHTTPServer, "serve_forever", _raise_keyboard_interrupt
        )
        rc = dev_server.main([])
        assert rc == 0
        out = capsys.readouterr().out
        assert dev_server._DEFAULT_HOST in out

    def test_end_headers_adds_no_store_before_delegating(self):
        # Direct check that _StaticHandler.end_headers is an override that ADDS the
        # header rather than replacing send behaviour — exercised end-to-end already by
        # TestContentTypesAndHeaders; here we confirm the method exists with the
        # expected override relationship (cheap sanity, not a behaviour duplicate).
        from http.server import SimpleHTTPRequestHandler

        assert dev_server._StaticHandler.end_headers is not (
            SimpleHTTPRequestHandler.end_headers
        )
