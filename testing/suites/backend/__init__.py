"""Service tests for the out-of-layer real-time sync server (Phase-10 C).

Scope after ADR-0043: the sync-backend *service* only — the CRDT relay, the
awareness/presence routing, the update log/backlog, the share-token handshake, and
the default-hosting guard. All of it runs **in-process** (an ephemeral loopback
:class:`~sync_backend.server.SyncServer`) with no Docker, Nginx or launcher
subprocess, so these modules carry NO ``integration`` marker and run in the default
gate.

Deployment acceptance for the shipped ``deploy/`` artifacts (launcher subprocess,
Dockerfile, Nginx WSS config) lives in ``testing/suites/deploy/`` (moved from
``tests/deploy/`` on 2026-08-30, ADR-0065).
"""
