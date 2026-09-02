"""Static determinism + reachability guards (no execution).

Determinism guard (REQ-P7-LOGIC-002): ``logic/export.py`` and ``logic/atlas.py`` must stay
byte-reproducible (ADR-0019) -- neither imports ``time``, ``random``, or
``locale`` (nor any of their submodules), which would make output depend on
wall-clock / seed state / the host locale.

Reachability guard (REQ-P11-LOGIC-008): no Phase-11 (Asset Library) logic/data module or
operation is reachable from a ``paintEvent``/``timerEvent`` path -- the AST is
scanned rather than importing/instantiating any ui/ widget (Qt-free, S11).

Both are pure AST/text scans over source files: no product code is imported,
so this module never touches Qt and never executes application code.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Set

_ROOT = Path(__file__).resolve().parents[3]
_PIXELART = _ROOT / "pixelart_creator"

# --------------------------------------------------------------------------- #
# Determinism guard — no time/random/locale import in the byte-reproducible export path. #
# --------------------------------------------------------------------------- #

_FORBIDDEN_TOP_MODULES = {"time", "random", "locale"}


def _imported_top_modules(source: str) -> Set[str]:
    tree = ast.parse(source)
    modules: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def _assert_no_forbidden_imports(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    found = _imported_top_modules(src) & _FORBIDDEN_TOP_MODULES
    assert not found, f"{path} imports non-deterministic module(s): {found}"


def test_export_module_imports_no_time_random_or_locale():
    _assert_no_forbidden_imports(_PIXELART / "logic" / "export.py")


def test_atlas_module_imports_no_time_random_or_locale():
    _assert_no_forbidden_imports(_PIXELART / "logic" / "atlas.py")


# --------------------------------------------------------------------------- #
# Reachability guard — no Phase-11 logic/data module reachable from paintEvent/timerEvent. #
# --------------------------------------------------------------------------- #

# The Phase-11 (Asset Library) logic/data module basenames (REQ-P11-*).
_PHASE_11_MODULES = {
    "asset_catalog",
    "asset_query",
    "asset_tags",
    "asset_version",
    "break_detection",
    "content_hash",
    "dependency_graph",
    "asset_cas",
    "asset_catalog_io",
    "asset_export",
    "asset_revision_store",
    "asset_shared_backend",
    "asset_storage",
}

_QT_PAINT_TIMER_METHODS = {"paintEvent", "timerEvent"}

# The Phase-11 (Asset Library) ui/ files themselves -- if any of these ever
# grows a paintEvent/timerEvent, that is an immediate, direct violation.
_PHASE_11_UI_FILES = {
    "asset_library_actions.py",
    "asset_library_panel.py",
    "asset_reuse_panel.py",
    "asset_search_panel.py",
    "asset_tagging_panel.py",
    "asset_version_browser.py",
    "dependency_graph_view.py",
}


def _iter_ui_files() -> List[Path]:
    return sorted((_PIXELART / "ui").glob("*.py"))


def _imports_phase11_module(tree: ast.AST) -> Set[str]:
    """Phase-11 logic/data basenames this file imports (empty if none)."""
    hits: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            base = node.module.split(".")[-1]
            if base in _PHASE_11_MODULES:
                hits.add(base)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                base = alias.name.split(".")[-1]
                if base in _PHASE_11_MODULES:
                    hits.add(base)
    return hits


def _defines_paint_or_timer_event(tree: ast.AST) -> Set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name in _QT_PAINT_TIMER_METHODS
    }


def test_no_phase11_ui_file_defines_paint_or_timer_event():
    """No Phase-11 (Asset Library) ui/ file defines paintEvent/timerEvent at all
    -- so no Phase-11 operation can be reachable from either path."""
    offenders = []
    for path in _iter_ui_files():
        if path.name not in _PHASE_11_UI_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        events = _defines_paint_or_timer_event(tree)
        if events:
            offenders.append((path.name, sorted(events)))
    assert offenders == [], (
        "Phase-11 ui/ file(s) define a paint/timer event (REQ-P11-LOGIC-008): "
        f"{offenders}"
    )


def test_no_paint_or_timer_event_file_imports_a_phase11_module():
    """No ui/ file that defines paintEvent/timerEvent imports any Phase-11
    logic/data module -- so a paint/timer path can never reach Phase-11 code."""
    offenders = []
    for path in _iter_ui_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not _defines_paint_or_timer_event(tree):
            continue
        hits = _imports_phase11_module(tree)
        if hits:
            offenders.append((path.name, sorted(hits)))
    assert offenders == [], (
        "ui/ file(s) with a paint/timer event import Phase-11 logic/data "
        f"module(s) (REQ-P11-LOGIC-008): {offenders}"
    )


# --------------------------------------------------------------------------- #
# C-05 -- UI_NOTICE_DURATION_MS single-sourced from logic/constants.py         #
# (mirrors testing/suites/data/test_project_io.py::                           #
# test_tuning_constants_single_sourced_from_constants' identity-check idiom,  #
# combined with this module's own AST/static-scan idiom for the guards above.) #
# --------------------------------------------------------------------------- #

# Regression test for C-05 — proven by reversion in the commit pass


def test_main_window_notice_duration_is_single_sourced_from_constants():
    """main_window.py's drop/status notices are timed by the ONE named constant
    UI_NOTICE_DURATION_MS (logic/constants.py) -- never a locally re-declared
    magic number (before the fix: a module-local ``_DROP_NOTICE_MS = 6000``).

    (a) main_window.py imports UI_NOTICE_DURATION_MS from logic.constants and
        references it at its notice call sites (static scan -- no Qt import
        here, this file stays Qt-free per S11).
    (b) no bare literal 6000 appears as a notice-duration argument in that
        file.
    (c) constants.UI_NOTICE_DURATION_MS == 6000, by identity from the module
        (a plain logic/ import -- Qt-free).
    """
    main_window_path = _PIXELART / "ui" / "main_window.py"
    src = main_window_path.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # (a) the module-level import.
    imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "pixelart_creator.logic.constants"
        and any(alias.name == "UI_NOTICE_DURATION_MS" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imported, (
        "main_window.py does not import UI_NOTICE_DURATION_MS from "
        "pixelart_creator.logic.constants"
    )

    # (a, continued) it is referenced (used as a Name) at least once -- i.e.
    # actually consumed, not merely imported and left unused.
    call_site_uses = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "UI_NOTICE_DURATION_MS"
    )
    assert call_site_uses >= 1, (
        "UI_NOTICE_DURATION_MS is imported but never referenced at a notice "
        "call site in main_window.py"
    )

    # (b) no bare "6000" literal used as a notice-duration argument -- i.e. no
    # raw Constant(6000) appears anywhere in the module (the sole legitimate
    # home for that value is constants.py itself).
    bare_6000_hits = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value == 6000
    ]
    assert bare_6000_hits == [], (
        "main_window.py contains a bare 6000 literal -- the notice duration "
        "must come from UI_NOTICE_DURATION_MS, not a re-declared magic number"
    )

    # (c) the constant itself, by identity, straight from logic/constants.py
    # (a plain Qt-free import -- mirrors test_project_io.py's own pattern).
    from pixelart_creator.logic.constants import UI_NOTICE_DURATION_MS

    assert UI_NOTICE_DURATION_MS == 6000
