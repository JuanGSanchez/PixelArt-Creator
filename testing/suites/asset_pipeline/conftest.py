"""Shared fixtures for the ``testing/suites/asset_pipeline/`` tests.

``REPO_ROOT`` follows the same convention as the sibling roots
(``testing/suites/scripts/conftest.py``, ``testing/suites/deploy/conftest.py``):
this file sits at ``testing/suites/<root>/conftest.py``, so ``parents[3]`` is the
working-tree root.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterator, List, NamedTuple, Optional

import pytest

#: Repo root: testing/suites/asset_pipeline/conftest.py -> parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _redraw_scratch(factory: pytest.TempPathFactory) -> Path:
    """A new empty folder under ``ORCH_TEST_TMP`` (or pytest's base temp directory)."""
    root = os.environ.get("ORCH_TEST_TMP")
    if root:
        base = Path(root) / "asset-pipeline-redraw"
        base.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="r-", dir=str(base)))
    return factory.mktemp("redraw")


def _remove(folder: Path) -> None:
    """Remove a scratch folder, scratch git repositories included.

    The object files of a git repository are read-only, and on Windows ``rmtree``
    stops at the first one (an ``ignore_errors`` call then leaves the whole folder
    behind). Each refusal is retried once with the file made writable.
    """

    def writable(func, path, _error):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    shutil.rmtree(folder, onexc=writable)


@pytest.fixture
def font_scratch(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """A private folder for the redraw and visual-reference tests, removed afterwards.

    ``ORCH_TEST_TMP`` is the root this repository's test runner configures; without
    it the folder comes from pytest's own base temp directory. The modules that use
    it (``test_redraw_set.py`` and its four siblings) build every plant, copy and
    scratch repository here, and never write beside a committed file.
    """
    folder = _redraw_scratch(tmp_path_factory)
    try:
        yield folder
    finally:
        _remove(folder)


@pytest.fixture(scope="module")
def font_scratch_shared(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """``font_scratch`` for a module that builds one read-only copy and reuses it."""
    folder = _redraw_scratch(tmp_path_factory)
    try:
        yield folder
    finally:
        _remove(folder)


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
