"""Contract tests for ``scripts/check_layering.py`` (ADR-0047 / PA-04 tranche 1).

Contract asserted here, taken verbatim from the script's own header:

    ENTRYPOINT: python scripts/check_layering.py [--root pixelart_creator] [--json]
    EXIT CODES: 0 clean -> COMPLETED ; 1 violations found OR an UNREGISTERED
        top-level package found (fail-closed) -> FAILED ;
        2 invalid input / unreadable root -> BLOCKED.

Every fixture is a hand-built tiny package tree written under ``tmp_path`` and
passed to the script via its own ``--root`` flag. The real
``pixelart_creator/`` tree is never scanned by these tests.

The forbidden import name used to build the "logic imports Qt" violation
fixture is read from the script's own ``QT`` constant (via ``importlib``,
matching the file-load pattern ``tests/deploy/test_run_ci_router.py`` already
uses for a ``scripts/`` module with no package to import through) rather than
hardcoding a duplicate of "PySide6" -- if the script's own forbidden-name list
ever changes, this fixture changes with it instead of silently testing a rule
the script no longer enforces.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from .conftest import run_script

SCRIPT = "check_layering.py"

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
_SPEC = importlib.util.spec_from_file_location(
    "check_layering", _SCRIPTS_DIR / "check_layering.py"
)
assert _SPEC is not None and _SPEC.loader is not None
check_layering = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("check_layering", check_layering)
_SPEC.loader.exec_module(check_layering)

#: The script's own declared forbidden-Qt-import-name tuple (module-level
#: constant) -- not a duplicate literal.
FORBIDDEN_QT_NAME = check_layering.QT[0]


# --------------------------------------------------------------------------- #
# The essential pair: a clean tree exits 0, a broken tree exits 1.
# --------------------------------------------------------------------------- #
def test_clean_three_layer_tree_exits_0(tmp_path):
    root = tmp_path / "pkg"
    (root / "logic").mkdir(parents=True)
    (root / "data").mkdir(parents=True)
    (root / "ui").mkdir(parents=True)
    (root / "logic" / "constants.py").write_text("MAX = 100\n", encoding="utf-8")
    (root / "data" / "store.py").write_text("import os\n", encoding="utf-8")
    (root / "ui" / "widget.py").write_text(
        "import PySide6\nfrom pixelart_creator import logic\n", encoding="utf-8"
    )

    result = run_script(SCRIPT, ["--root", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["violations"] == []
    assert payload["unregistered"] == []
    assert payload["scanned"] == 3


def test_logic_importing_qt_is_a_violation_exit_1(tmp_path):
    """Deliberately broken fixture: a module in the pure ``logic/`` layer that
    imports Qt -- the exact defect the header names as FAILED (exit 1) -- and
    a clean sibling module that must NOT be swept into the violation list."""
    root = tmp_path / "pkg"
    (root / "logic").mkdir(parents=True)
    (root / "logic" / "bad.py").write_text(
        "import {}\n".format(FORBIDDEN_QT_NAME), encoding="utf-8"
    )
    (root / "logic" / "good.py").write_text("MAX = 1\n", encoding="utf-8")

    # --json forces the JSON report even if the (deliberately broken) fixture
    # ends up reporting nothing -- without it a script that silently stops
    # detecting violations would ALSO stop printing, and the assertion below
    # would fail on json.loads() with a much less direct message than "exit
    # code 1 was expected but got 0".
    result = run_script(SCRIPT, ["--root", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["violations"]) == 1
    violation = payload["violations"][0]
    assert violation["file"] == "logic/bad.py"
    assert violation["layer"] == "logic"
    assert FORBIDDEN_QT_NAME in violation["imports"]


def test_data_importing_ui_is_a_violation_exit_1(tmp_path):
    root = tmp_path / "pkg"
    (root / "data").mkdir(parents=True)
    (root / "data" / "bad.py").write_text(
        "from pixelart_creator.ui import main_window\n", encoding="utf-8"
    )

    result = run_script(SCRIPT, ["--root", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["violations"][0]["layer"] == "data"


# --------------------------------------------------------------------------- #
# Fail-closed: an unregistered top-level directory name is ALSO exit 1, per
# the header's "OR an UNREGISTERED top-level package found" clause -- this is
# the fail-closed behaviour the script's own comment block documents as a
# 2026-07-29 fix for a prior fail-OPEN defect.
# --------------------------------------------------------------------------- #
def test_unregistered_top_level_package_is_exit_1_not_a_silent_skip(tmp_path):
    root = tmp_path / "pkg"
    (root / "mobile_client").mkdir(parents=True)
    (root / "mobile_client" / "app.py").write_text("X = 1\n", encoding="utf-8")

    result = run_script(SCRIPT, ["--root", str(root)])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["unregistered"]) == 1
    assert payload["unregistered"][0]["top_level"] == "mobile_client"


# --------------------------------------------------------------------------- #
# BLOCKED path (exit 2): an unreadable / nonexistent root.
# --------------------------------------------------------------------------- #
def test_missing_root_exits_2(tmp_path):
    missing = tmp_path / "does-not-exist"
    result = run_script(SCRIPT, ["--root", str(missing)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "root-not-found"


def test_unparseable_module_exits_2(tmp_path):
    root = tmp_path / "pkg"
    (root / "logic").mkdir(parents=True)
    (root / "logic" / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    result = run_script(SCRIPT, ["--root", str(root)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert "error" in payload
