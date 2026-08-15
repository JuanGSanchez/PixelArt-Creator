"""Shared fixtures for the ``tests/scripts/`` gate-script contract tests (ADR-0047).

Mirrors the ``REPO_ROOT`` convention already used by ``tests/deploy/conftest.py``:
``tests/scripts/conftest.py`` sits at the same depth (``tests/<root>/conftest.py``),
so the same ``parents[2]`` expression resolves to the working-tree root.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple

#: Repo root: tests/scripts/conftest.py -> parents[2] is the working tree root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"


class ScriptRun(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def run_script(script_name: str, args: List[str]) -> ScriptRun:
    """Invoke ``scripts/<script_name>`` as a real subprocess, matching its own
    documented ``ENTRYPOINT`` (``python scripts/<script_name> [flags]``).

    A subprocess (rather than an in-process ``main()`` call) is used
    deliberately: every one of these scripts reads its flags via
    ``argparse.parse_args()`` with no injectable parameter, so a subprocess is
    the only way to exercise the real CLI contract -- the entrypoint under
    test, not a private call shape.
    """
    script_path = SCRIPTS_DIR / script_name
    completed = subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return ScriptRun(completed.returncode, completed.stdout, completed.stderr)
