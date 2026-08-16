"""T-28 (AGT-06 audit) — REQ-P11-UI-011 static no-worker / no-shutdown_* guard.

REQ-P11-UI-011 was re-adjudicated (``specs/phase-11-team-asset-management``):
asset operations complete SYNCHRONOUSLY on the GUI thread — no off-thread
worker module was built (plan.md: "no worker module was built"; off-thread
execution is deferred future work FW-P11-1). The traceability matrix records
this requirement as having "no test located" for the corrected wording. This
module is that test: a STATIC source-level guard (AST) over the seven Phase-11
UI modules proving none of them introduces a ``QThread``/``QThreadPool``/
``threading.Thread`` worker or a ``shutdown_*`` drain method — a regression
guard for the re-adjudicated synchronous contract, placed beside the
asset-panel tests it corroborates.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_UI_DIR = Path(__file__).resolve().parents[2] / "pixelart_creator" / "ui"

#: The Phase-11 team-asset-management UI modules (asset library + tagging +
#: search + reuse + version browser + dependency graph + the shared session).
_PHASE11_MODULES = [
    "asset_library_actions.py",
    "asset_library_panel.py",
    "asset_reuse_panel.py",
    "asset_search_panel.py",
    "asset_tagging_panel.py",
    "asset_version_browser.py",
    "dependency_graph_view.py",
]

#: Names whose presence would indicate an off-GUI-thread worker was introduced.
_WORKER_NAMES = {"QThread", "QThreadPool", "Thread", "QRunnable"}


def _module_path(name: str) -> Path:
    path = _UI_DIR / name
    assert path.is_file(), f"expected Phase-11 UI module missing: {path}"
    return path


@pytest.mark.parametrize("module_name", _PHASE11_MODULES)
def test_t28_no_worker_thread_names_referenced(module_name):
    """No Phase-11 asset UI module names a worker-thread class anywhere."""
    source = _module_path(module_name).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=module_name)
    referenced_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    referenced_attrs = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    found = (referenced_names | referenced_attrs) & _WORKER_NAMES
    assert not found, f"{module_name} references worker-thread name(s): {found}"


@pytest.mark.parametrize("module_name", _PHASE11_MODULES)
def test_t28_no_shutdown_method_defined(module_name):
    """No Phase-11 asset UI module defines a ``shutdown_*`` drain method — there
    is no off-thread pool/carrier to drain (contrast ``CanvasScene.shutdown_prewarm``
    / ``Tilemap_Canvas.shutdown_warm`` / ``Export_Controller.shutdown``, which
    exist precisely BECAUSE those modules own a worker)."""
    source = _module_path(module_name).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=module_name)
    shutdown_methods = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("shutdown")
    ]
    assert not shutdown_methods, (
        f"{module_name} defines unexpected shutdown-drain method(s): "
        f"{shutdown_methods}"
    )
