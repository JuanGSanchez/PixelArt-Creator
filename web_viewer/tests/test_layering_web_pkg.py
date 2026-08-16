"""Contract test proving ``scripts/check_layering.py`` actually catches a
``web_viewer`` (WEB_PKG) layering violation, not just that the registry entry exists
(T-31, job 20260816-spec-audit-test-rebuild-docs-move).

ADR-0035 governs ``web_viewer/`` as a headless, third top-level package: it must not
import Qt, ``ui/``, ``data/`` or ``sync_backend`` (script's own ``FORBIDDEN[WEB_PKG]``
tuple, ``scripts/check_layering.py``). The registry existing is not the same claim as
the registry being ENFORCED -- this module builds a synthetic tree under ``tmp_path``
(never the real ``pixelart_creator``/``web_viewer`` trees), invokes the real script as a
subprocess against ``--root <tmp>`` (matching its documented CLI entrypoint, mirroring
``tests/scripts/test_check_layering.py``'s own harness shape), and asserts the CATCH:
a non-zero exit that names the violating file and the forbidden import.

Both legs are required: a violating fixture must FAIL (the catch), and a clean sibling
fixture of the identical shape must PASS (exit 0) -- otherwise a script that always
exits 1 for ``web_viewer/`` would look like it "caught" the violation for the wrong
reason.

A THIRD leg proves the boundary the dispatch calls out explicitly: the script's
``is_test_module()`` exempts any path with a ``tests`` path component BY DESIGN, so the
identical forbidden import planted under a ``tests/`` subdirectory of the synthetic
``web_viewer`` package proves nothing about production-import enforcement -- it is
asserted here as a documented non-catch, not used as evidence of a catch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple

#: web_viewer/tests/test_layering_web_pkg.py -> parents[2] is the working-tree root
#: (matches the tests/scripts/conftest.py convention: same depth, same expression).
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_layering.py"


class ScriptRun(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def _run_check_layering(root: Path, extra_args: List[str] = ()) -> ScriptRun:
    """Invoke the real ``scripts/check_layering.py`` CLI as a subprocess.

    A subprocess (not an in-process ``main()`` call) exercises the actual documented
    entrypoint (``python scripts/check_layering.py --root <root> [--json]``), which is
    the only way ``argparse``-driven CLI behaviour is proven rather than assumed.
    """
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--root", str(root), *extra_args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return ScriptRun(completed.returncode, completed.stdout, completed.stderr)


def test_web_pkg_qt_import_is_caught_as_a_violation_exit_1(tmp_path: Path) -> None:
    """A production ``web_viewer/`` module importing PySide6 must FAIL the gate."""
    root = tmp_path / "synthetic_repo"
    pkg = root / "web_viewer"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "dev_server.py").write_text("import PySide6\n\nX = 1\n", encoding="utf-8")

    result = _run_check_layering(root, ["--json"])
    payload = json.loads(result.stdout)

    assert result.returncode == 1, result.stderr
    assert len(payload["violations"]) == 1, payload
    violation = payload["violations"][0]
    assert violation["file"] == "web_viewer/dev_server.py"
    assert violation["layer"] == "web_viewer"
    assert "PySide6" in violation["imports"]


def test_web_pkg_sync_backend_import_is_also_caught(tmp_path: Path) -> None:
    """web_viewer must not import ``sync_backend`` by Python import (wire-only, ADR-0035
    Sec.3) -- the second forbidden name in ``FORBIDDEN[WEB_PKG]``, proven independently
    of the Qt case above so the catch is not accidentally keyed on ``PySide6`` alone."""
    root = tmp_path / "synthetic_repo"
    pkg = root / "web_viewer"
    pkg.mkdir(parents=True)
    (pkg / "bridge.py").write_text("import sync_backend\n\nX = 1\n", encoding="utf-8")

    result = _run_check_layering(root, ["--json"])
    payload = json.loads(result.stdout)

    assert result.returncode == 1, result.stderr
    violation = payload["violations"][0]
    assert violation["file"] == "web_viewer/bridge.py"
    assert "sync_backend" in violation["imports"]


def test_clean_web_pkg_layout_exits_0(tmp_path: Path) -> None:
    """The positive leg: a clean synthetic ``web_viewer`` layout (same shape as the
    violating fixture, no forbidden import) must exit 0 with zero violations -- proves
    the gate is not simply always failing for the ``web_viewer`` top-level name."""
    root = tmp_path / "synthetic_repo"
    pkg = root / "web_viewer"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "dev_server.py").write_text(
        "import http.server\nimport json\n\nX = 1\n", encoding="utf-8"
    )

    result = _run_check_layering(root, ["--json"])
    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert payload["violations"] == []
    assert payload["scanned"] == 2


def test_violation_planted_under_a_tests_path_proves_nothing(tmp_path: Path) -> None:
    """Documents the boundary the dispatch calls out: ``is_test_module()`` exempts any
    path with a ``tests`` component BY DESIGN (module docstring, ``check_layering.py``),
    so the identical forbidden import placed inside ``web_viewer/tests/`` is silently
    skipped -- exit 0, zero violations. This is asserted as the KNOWN exemption, not
    used anywhere above as evidence that WEB_PKG enforcement works: only a violation
    under a PRODUCTION path (the three tests above) proves the catch.
    """
    root = tmp_path / "synthetic_repo"
    pkg = root / "web_viewer"
    test_dir = pkg / "tests"
    test_dir.mkdir(parents=True)
    (test_dir / "test_something.py").write_text(
        "import PySide6\n\nX = 1\n", encoding="utf-8"
    )

    result = _run_check_layering(root, ["--json"])
    payload = json.loads(result.stdout)

    assert result.returncode == 0, result.stderr
    assert payload["violations"] == []
    assert payload["scanned"] == 0
