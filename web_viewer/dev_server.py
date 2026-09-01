# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Local-development static file server for the ``web_viewer/static/`` client.

    LOCAL DEV ONLY — **NOT FOR PRODUCTION.**

Phase-13 Slice 13E (ADR-0035 §1, ADR-0036 §2; spec REQ-P13-WEB-001/-004). Production
static serving is the 13C **Nginx** ``location`` block (owned by AGT-09); this module
exists **only** so a developer can serve the vanilla client locally without Nginx, over
plain HTTP on loopback. It is Qt-free and imports **stdlib only** (``http.server``) — it
adds no Python dependency (D1) and honours the ``WEB_PKG`` layering rule (no import of
Qt / ``pixelart_creator.ui`` / ``pixelart_creator.data`` / ``sync_backend``).

The project **data** never flows through this server: the browser client opens a
WebSocket straight to the shipped ``sync_backend/`` relay (presenting the share-link
token as the ``?token=`` query parameter, ADR-0036 Addendum A.1). This server serves
only the static HTML/CSS/JS assets.

Run it from the repo root::

    python -m web_viewer.dev_server            # http://127.0.0.1:8000/
    python -m web_viewer.dev_server --port 9000

then open ``http://127.0.0.1:8000/?t=<token>&p=<project_id>&ws=ws://127.0.0.1:8765/``
(the ``ws`` query parameter points the client at your local ``sync_backend`` for dev; in
production it is omitted and the client derives ``wss://<same-host>/``).
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Sequence

#: The directory of vanilla client assets this dev server exposes.
_STATIC_ROOT = Path(__file__).resolve().parent / "static"

#: Loopback-only default bind — a dev server never opens an external port.
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


class _StaticHandler(SimpleHTTPRequestHandler):
    """Serve ``static/`` with caching disabled (a dev-loop convenience).

    ``SimpleHTTPRequestHandler`` maps most extensions to the correct MIME type
    (``.js`` → ``text/javascript``, ``.css`` → ``text/css``), so the vanilla client
    loads with no build step. It does **not** reliably know ``.mjs`` on every
    platform (``mimetypes`` may return ``application/octet-stream``), and browsers
    refuse to execute an ES module served with a non-JavaScript MIME type — so the
    ``.mjs`` → ``text/javascript`` mapping is pinned explicitly below (dev-server
    glue for the native-ES-module split: ``viewer.js`` imports ``viewer_core.mjs``).
    ``no-store`` keeps an edited asset from being served stale during development.
    """

    #: Pin JS module MIME types (merged over the stdlib defaults) so ``.mjs`` is
    #: always served as JavaScript regardless of the host OS mimetypes registry.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
    }

    def end_headers(self) -> None:
        """Add a no-cache header before the blank line terminating the headers."""
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def build_server(
    host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT
) -> ThreadingHTTPServer:
    """Return a threading HTTP server bound to ``(host, port)`` serving ``static/``.

    Args:
        host: Bind host (loopback by default — dev server, never externally exposed).
        port: Bind port (``0`` selects an ephemeral free port).

    Returns:
        A configured, not-yet-serving :class:`~http.server.ThreadingHTTPServer`.
    """
    handler = partial(_StaticHandler, directory=str(_STATIC_ROOT))
    return ThreadingHTTPServer((host, port), handler)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Parse CLI arguments and serve ``static/`` until interrupted (dev entrypoint).

    Args:
        argv: Optional argument vector (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (``0`` on a clean Ctrl-C shutdown).
    """
    parser = argparse.ArgumentParser(
        description=(
            "LOCAL DEV ONLY static server for web_viewer/static/ "
            "(NOT for production — use the 13C Nginx location block)."
        )
    )
    parser.add_argument("--host", default=_DEFAULT_HOST, help="bind host (loopback)")
    parser.add_argument(
        "--port", type=int, default=_DEFAULT_PORT, help="bind port (0 = ephemeral)"
    )
    args = parser.parse_args(argv)

    if not _STATIC_ROOT.is_dir():
        parser.error(f"static asset directory not found: {_STATIC_ROOT}")

    with build_server(str(args.host), int(args.port)) as httpd:
        host = str(httpd.server_address[0])
        port = int(httpd.server_address[1])
        print(f"[web_viewer.dev_server] LOCAL DEV ONLY — serving {_STATIC_ROOT}")
        print(f"[web_viewer.dev_server] http://{host}:{port}/  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[web_viewer.dev_server] shutting down")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
