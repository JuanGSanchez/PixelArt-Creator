"""T-01: the real tree passes the architecture gates (REQ-P1-LOGIC-013).

``scripts/check_layering.py`` and ``scripts/check_cycles.py`` each ship their
own synthetic-fixture contract suites under ``tests/scripts/`` — those tests
build tiny hand-crafted package trees under ``tmp_path`` and never scan the
real ``pixelart_creator/`` tree (see their module docstrings). This module
closes that gap: it runs both scripts, unmodified, as subprocesses over the
REAL tree from the worktree root, and asserts exit 0, quoting their stdout.

Zero Qt; deterministic (no wall-clock, no randomness); the scripts write no
files and mutate nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# The worktree root -- four parents up from testing/suites/logic/test_architecture_gates.py.
_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _ROOT / "scripts"


def _run(script_name: str) -> subprocess.CompletedProcess:
    script = _SCRIPTS_DIR / script_name
    assert script.is_file(), f"missing {script}"
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_check_layering_passes_over_the_real_tree():
    """REQ-P1-LOGIC-013: the real pixelart_creator/ tree has no layering
    violation and no unregistered top-level package (check_layering.py exit 0).
    """
    result = _run("check_layering.py")
    assert result.returncode == 0, (
        f"check_layering exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # The script reports its verdict on stderr (see its own source); quote both.
    combined = result.stdout + result.stderr
    assert "clean" in combined.lower(), combined


def test_check_cycles_passes_over_the_real_tree():
    """REQ-P1-LOGIC-013: the real pixelart_creator/ tree has no import cycle
    (check_cycles.py exit 0).
    """
    result = _run("check_cycles.py")
    assert result.returncode == 0, (
        f"check_cycles exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "no cycles" in combined.lower(), combined
