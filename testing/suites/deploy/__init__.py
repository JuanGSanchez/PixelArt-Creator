"""Deployment-acceptance tests for the shipped ``deploy/`` artifacts (AGT-09, DevOps).

Split out of ``tests/backend/`` by ADR-0043 (now ``testing/suites/backend/`` and
``testing/suites/deploy/`` respectively, after the 2026-08-30 test-tree
relocation, ADR-0065). ``testing/suites/backend/`` exercises the
sync-backend *service* (CRDT relay, awareness/presence routing, update log,
share-token handshake) in-process; the modules here instead exercise the
**deployment artifacts** — ``deploy/run_sync_backend.py``, ``deploy/Dockerfile``,
``deploy/nginx-sync.conf`` — by launching the *unmodified* backend the way a
container / systemd unit / Nginx front-end does.

Every test here is ``@pytest.mark.integration`` (module-level ``pytestmark``):
it reaches outside the process (subprocess, Docker daemon, real socket, Nginx),
so the default gate deselects it. They run in the dedicated ``integration`` CI
job (T13C-06) or a documented manual run, and they **skip** — never error — when
the environment cannot provide what they need.
"""
