# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Real-time sync backend — a first-class component OUTSIDE the three layers.

Phase-10 Slice C (ADR-0027; spec REQ-P10-BACKEND-001/-002, CL-B4). This is a **separate
top-level package** (a sibling of ``pixelart_creator/``, excluded from the desktop
wheel), NOT a fourth layer inside the client. It is an asyncio **WebSocket relay** that
broadcasts CRDT updates + ephemeral awareness/presence across a shared document's peers
and **persists** the per-document update log so a late-joining client can catch up.

Layering (enforced by ``scripts/check_layering.py --root .``, ADR-0027 §5): the backend
imports **no** ``pixelart_creator.ui``, no ``pixelart_creator.data``, and no Qt — it is
headless and never touches the client's OS-keyring tokens or provider adapters
(REQ-P10-BACKEND-002). It **reuses** the pure ``pixelart_creator.logic`` code
(:mod:`~pixelart_creator.logic.sync_protocol` framing + validation), so the Article VII
caps are single-sourced across the client transport and the backend.

CI-testability (REQ-P10-BACKEND-001, CL-B4): :class:`~sync_backend.server.SyncServer`
starts on an ephemeral loopback port in-process (``await server.start()``) so the full
client↔backend loop runs over localhost in the CI gate — distinct from the out-of-CI
live-provider OAuth.
"""

from sync_backend.server import BackendError, SyncServer
from sync_backend.store import UpdateStore

__all__ = ["SyncServer", "BackendError", "UpdateStore"]
