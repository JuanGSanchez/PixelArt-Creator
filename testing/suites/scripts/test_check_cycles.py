"""Contract tests for ``scripts/check_cycles.py`` (ADR-0047 / PA-04 tranche 1).

Contract asserted here, taken verbatim from the script's own header:

    ENTRYPOINT: python scripts/check_cycles.py [--root pixelart_creator] [--json]
    EXIT CODES: 0 no cycles -> COMPLETED ; 1 cycle(s) found -> FAILED ;
        2 invalid input / unreadable root -> BLOCKED.

Every fixture is a hand-built tiny package tree written under ``tmp_path`` and
passed to the script via its own ``--root`` flag. The real
``pixelart_creator/`` import graph is never scanned by these tests.
"""

from __future__ import annotations

import json

from .conftest import run_script

SCRIPT = "check_cycles.py"


# --------------------------------------------------------------------------- #
# The essential pair: an acyclic tree exits 0, a genuinely cyclic tree
# (two modules importing each other) exits 1.
# --------------------------------------------------------------------------- #
def test_acyclic_tree_exits_0(tmp_path):
    root = tmp_path / "mypkg"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "a.py").write_text("import os\n", encoding="utf-8")
    (root / "b.py").write_text("import mypkg.a\n", encoding="utf-8")

    result = run_script(SCRIPT, ["--root", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["cycles"] == []
    assert payload["modules"] == 3
    assert payload["edges"] == 1


def test_two_modules_importing_each_other_is_a_cycle_exit_1(tmp_path):
    """Deliberately broken fixture: a.py imports b.py and b.py imports a.py
    back -- a genuine 2-node cycle -- must FAIL with exit code 1 and name
    both modules in the reported cycle."""
    root = tmp_path / "mypkg"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "a.py").write_text("import mypkg.b\n", encoding="utf-8")
    (root / "b.py").write_text("import mypkg.a\n", encoding="utf-8")

    # --json forces the JSON report even if the (deliberately broken) fixture
    # ends up reporting nothing -- without it a script that silently stops
    # detecting cycles would ALSO stop printing, and the assertion below would
    # fail on json.loads() with a much less direct message than "exit code 1
    # was expected but got 0".
    result = run_script(SCRIPT, ["--root", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["cycles"]) == 1
    assert payload["cycles"][0] == ["mypkg.a", "mypkg.b"]


def test_self_import_is_a_cycle_exit_1(tmp_path):
    """A module that imports itself is reported as a size-1 cycle (module
    header: "reports every SCC of size>1 or self-loop")."""
    root = tmp_path / "mypkg"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "loopy.py").write_text("import mypkg.loopy\n", encoding="utf-8")

    result = run_script(SCRIPT, ["--root", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert ["mypkg.loopy"] in payload["cycles"]


def test_three_module_cycle_is_reported_as_one_group(tmp_path):
    root = tmp_path / "mypkg"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "a.py").write_text("import mypkg.b\n", encoding="utf-8")
    (root / "b.py").write_text("import mypkg.c\n", encoding="utf-8")
    (root / "c.py").write_text("import mypkg.a\n", encoding="utf-8")

    result = run_script(SCRIPT, ["--root", str(root), "--json"])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["cycles"]) == 1
    assert payload["cycles"][0] == ["mypkg.a", "mypkg.b", "mypkg.c"]


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
    root = tmp_path / "mypkg"
    root.mkdir()
    (root / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")

    result = run_script(SCRIPT, ["--root", str(root)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert "error" in payload
