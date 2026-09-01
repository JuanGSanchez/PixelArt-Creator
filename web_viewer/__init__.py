# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""``web_viewer`` — vanilla browser companion viewer for shared pixel-art projects.

A NEW top-level package **outside** the three desktop layers (ADR-0035): headless,
Qt-free and **view-only**. Per the ``check_layering`` ``WEB_PKG`` rule it MUST NOT
import Qt, :mod:`pixelart_creator.ui`, :mod:`pixelart_creator.data`, or
``sync_backend``; the Python side (the local :mod:`web_viewer.dev_server`) imports
**stdlib only** and MAY reuse pure ``pixelart_creator.logic`` seams. The browser
client under ``static/`` reaches
the shipped ``sync_backend/`` relay over the WebSocket wire **at run time** (never by
Python import), presenting a signed share-link token, and reconstructs + renders the
shared project pixel-faithfully in vanilla HTML/CSS/JS (no build step, no framework).

See ADR-0035 (placement + import rules) and ADR-0036 (wire + signed-token contract).
"""

from __future__ import annotations

__all__: list[str] = []
