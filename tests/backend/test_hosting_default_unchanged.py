"""Default-unchanged hosting behaviour (Phase-13 Slice 13C, T13C-05).

Proves REQ-P13-BACKEND-003 / SC-P13-BACKEND-003-1: VPS self-hosting is **one** option,
not a forced default. With the 13C artifacts ignored, the app + backend behave
**identically to today** and require **no code change**:

* The shipped in-process :class:`~sync_backend.server.SyncServer` default bind is still
  loopback ``127.0.0.1`` (unchanged) — a default server opens no external port.
* The VPS-facing ``0.0.0.0`` bind is an **env-driven override in ``deploy/``** (the
  launcher), never a new backend default — adopting the artifacts changes no default.
* The shipped backend source imports **nothing** from ``deploy/``: using the backend the
  shipped way needs none of the 13C artifacts.

Runs in the **default gate** (NO ``integration`` marker); fast + hermetic — no Docker,
no Nginx, no external socket (the one server it starts binds an ephemeral loopback port,
as the CI backend always has).
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import inspect
from pathlib import Path
from typing import Set

import sync_backend.store as store_module
from sync_backend.server import SyncServer
from sync_backend.store import UpdateStore

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LAUNCHER_PATH = _REPO_ROOT / "deploy" / "run_sync_backend.py"


def _load_launcher():
    """Load ``deploy/run_sync_backend.py`` from file (``deploy/`` is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "deploy_run_sync_backend_probe", _LAUNCHER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _imported_modules(path: Path) -> Set[str]:
    """The set of module names a Python file imports (AST — not docstring prose)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _backend_py_files():
    return sorted(Path(store_module.__file__).resolve().parent.glob("*.py"))


# --------------------------------------------------------------------------- #
# The shipped backend default is unchanged loopback.
# --------------------------------------------------------------------------- #


def test_syncserver_default_bind_host_is_still_loopback():
    params = inspect.signature(SyncServer.__init__).parameters
    assert params["host"].default == "127.0.0.1"  # NOT 0.0.0.0 — unchanged default
    assert params["port"].default == 0


def test_default_server_binds_loopback_at_runtime():
    """A default-constructed server (no deploy/ involvement) binds only loopback."""

    async def scenario():
        server = SyncServer()  # shipped defaults, exactly as today
        try:
            host, port = await server.start()
            assert host in ("127.0.0.1", "::1")
            assert port > 0
            assert isinstance(server.store, UpdateStore)
        finally:
            await server.stop()

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# The 13C VPS bind is a deploy/ override, not a new backend default.
# --------------------------------------------------------------------------- #


def test_vps_public_bind_is_a_deploy_layer_override_not_a_backend_default():
    launcher = _load_launcher()
    # The VPS-facing 0.0.0.0 bind lives in the deploy/ launcher...
    assert launcher.DEFAULT_HOST == "0.0.0.0"
    # ...while the shipped backend's own default stays loopback (unchanged today).
    backend_default = inspect.signature(SyncServer.__init__).parameters["host"].default
    assert backend_default == "127.0.0.1"


def test_launcher_host_port_resolution_is_pure_and_env_driven(monkeypatch):
    launcher = _load_launcher()
    monkeypatch.delenv(launcher.HOST_ENV, raising=False)
    monkeypatch.delenv(launcher.PORT_ENV, raising=False)
    # Unset env -> the launcher's VPS defaults (deploy/ policy, no socket opened).
    assert launcher._resolve_host() == "0.0.0.0"
    assert launcher._resolve_port() == 8765
    # Env override -> the exact values (an integration run pins loopback/ephemeral).
    monkeypatch.setenv(launcher.HOST_ENV, "127.0.0.1")
    monkeypatch.setenv(launcher.PORT_ENV, "0")
    assert launcher._resolve_host() == "127.0.0.1"
    assert launcher._resolve_port() == 0


def test_launcher_builds_the_unchanged_backend_types(monkeypatch):
    """build_server() constructs the shipped SyncServer + UpdateStore (no start)."""
    launcher = _load_launcher()
    monkeypatch.setenv(launcher.HOST_ENV, "127.0.0.1")
    monkeypatch.setenv(launcher.PORT_ENV, "0")
    server = launcher.build_server()  # constructs only — opens no socket
    assert isinstance(server, SyncServer)
    assert isinstance(server.store, UpdateStore)


# --------------------------------------------------------------------------- #
# The shipped backend needs nothing from deploy/ (using it the shipped way).
# --------------------------------------------------------------------------- #


def test_backend_source_imports_nothing_from_deploy():
    forbidden_prefixes = ("deploy", "docker")
    for path in _backend_py_files():
        for module in _imported_modules(path):
            assert not module.startswith(
                forbidden_prefixes
            ), f"{path.name} imports 13C artifact machinery {module!r}"
