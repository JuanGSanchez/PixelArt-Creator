"""Shared fixtures for the ``testing/suites/asset_pipeline/`` tests.

``REPO_ROOT`` follows the same convention as the sibling roots
(``testing/suites/scripts/conftest.py``, ``testing/suites/deploy/conftest.py``):
this file sits at ``testing/suites/<root>/conftest.py``, so ``parents[3]`` is the
working-tree root.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional

#: Repo root: testing/suites/asset_pipeline/conftest.py -> parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"


class ScriptRun(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def run_script(
    script_name: str, args: List[str], env: Optional[dict] = None
) -> ScriptRun:
    """Invoke ``scripts/<script_name>`` as a real subprocess, matching its own
    documented entry point (``python scripts/<script_name> [flags]``).

    A subprocess (rather than an in-process ``main()`` call) is used on purpose:
    the entry point under test is the command line, not a private call shape.

    ``env``, when given, is a MERGE on top of a copy of the current process
    environment (never a replacement), so a caller states only the override.
    """
    script_path = SCRIPTS_DIR / script_name
    run_env = None
    if env is not None:
        run_env = dict(os.environ)
        run_env.update(env)
    completed = subprocess.run(
        [sys.executable, str(script_path), *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
        env=run_env,
    )
    return ScriptRun(completed.returncode, completed.stdout, completed.stderr)
