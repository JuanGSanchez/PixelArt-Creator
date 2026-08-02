"""Unit tests for `scripts/check_ci_docker_drift.py` (the apt-list drift guard
between `.ci/Dockerfile` and `.github/workflows/ci.yml`).

Placed under ``tests/deploy/`` per this task's direction (AGT-09's owned
surface, ADR-0043) alongside ``test_run_ci_router.py`` -- see that module's
docstring for why these hermetic, non-``integration`` tests belong here.
No network access; the only filesystem access is reading the real committed
``ci.yml``/``.ci/Dockerfile`` (agreement case) and scratch copies written to
``tmp_path`` (disagreement case) -- the committed files are NEVER perturbed.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = REPO_ROOT / "scripts"
_SPEC = importlib.util.spec_from_file_location(
    "check_ci_docker_drift", _SCRIPTS_DIR / "check_ci_docker_drift.py"
)
assert _SPEC is not None and _SPEC.loader is not None
drift = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("check_ci_docker_drift", drift)
_SPEC.loader.exec_module(drift)


_CI_YML_FRAGMENT = """\
name: ci
jobs:
  quality-gate:
    runs-on: ${{ matrix.os }}
    steps:
      - name: Checkout
        uses: actions/checkout@v5
      - name: Install Qt runtime OS libraries (Ubuntu)
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends \\
            libegl1 libgl1 libxkbcommon0 libdbus-1-3 \\
            libxcb-cursor0 libxcb-icccm4
"""

_DOCKERFILE_AGREEING = """\
FROM python:3.12-slim-bookworm
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
        libegl1 libgl1 libxkbcommon0 libdbus-1-3 \\
        libxcb-cursor0 libxcb-icccm4 && \\
    rm -rf /var/lib/apt/lists/*
"""

_DOCKERFILE_DISAGREEING = """\
FROM python:3.12-slim-bookworm
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
        libegl1 libgl1 libxkbcommon0 libdbus-1-3 \\
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 && \\
    rm -rf /var/lib/apt/lists/*
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_extract_apt_packages_from_ci_style_run_block():
    packages = drift._extract_apt_packages(
        "sudo apt-get update\n"
        "sudo apt-get install -y --no-install-recommends \\\n"
        "  libegl1 libgl1 libxkbcommon0\n"
    )
    assert packages == ["libegl1", "libgl1", "libxkbcommon0"]


def test_extract_apt_packages_from_dockerfile_style_run_instruction():
    packages = drift._extract_apt_packages(
        "RUN apt-get update && \\\n"
        "    apt-get install -y --no-install-recommends \\\n"
        "        libegl1 libgl1 && \\\n"
        "    rm -rf /var/lib/apt/lists/*\n"
    )
    assert packages == ["libegl1", "libgl1"]


def test_compare_agreeing_scratch_copies_reports_no_drift(tmp_path):
    ci_yml = _write(tmp_path, "ci.yml", _CI_YML_FRAGMENT)
    dockerfile = _write(tmp_path, "Dockerfile", _DOCKERFILE_AGREEING)
    ci_only, docker_only, matched = drift.compare(ci_yml, dockerfile)
    assert ci_only == set()
    assert docker_only == set()
    assert matched == {
        "libegl1",
        "libgl1",
        "libxkbcommon0",
        "libdbus-1-3",
        "libxcb-cursor0",
        "libxcb-icccm4",
    }


def test_compare_disagreeing_scratch_copies_reports_the_one_sided_diff(tmp_path):
    ci_yml = _write(tmp_path, "ci.yml", _CI_YML_FRAGMENT)
    dockerfile = _write(tmp_path, "Dockerfile", _DOCKERFILE_DISAGREEING)
    ci_only, docker_only, matched = drift.compare(ci_yml, dockerfile)
    assert ci_only == set()
    assert docker_only == {"libxcb-image0"}


def test_main_exit_0_on_agreeing_scratch_copies(tmp_path, capsys):
    ci_yml = _write(tmp_path, "ci.yml", _CI_YML_FRAGMENT)
    dockerfile = _write(tmp_path, "Dockerfile", _DOCKERFILE_AGREEING)
    rc = drift.main(["--ci-workflow", str(ci_yml), "--dockerfile", str(dockerfile)])
    assert rc == 0


def test_main_exit_1_on_disagreeing_scratch_copies(tmp_path):
    ci_yml = _write(tmp_path, "ci.yml", _CI_YML_FRAGMENT)
    dockerfile = _write(tmp_path, "Dockerfile", _DOCKERFILE_DISAGREEING)
    rc = drift.main(["--ci-workflow", str(ci_yml), "--dockerfile", str(dockerfile)])
    assert rc == 1


def test_main_exit_2_on_missing_dockerfile(tmp_path):
    ci_yml = _write(tmp_path, "ci.yml", _CI_YML_FRAGMENT)
    rc = drift.main(
        [
            "--ci-workflow",
            str(ci_yml),
            "--dockerfile",
            str(tmp_path / "nope" / "Dockerfile"),
        ]
    )
    assert rc == 2


def test_main_exit_2_on_missing_step(tmp_path):
    ci_yml = _write(
        tmp_path,
        "ci.yml",
        "name: ci\njobs:\n  quality-gate:\n    steps:\n"
        "      - name: Checkout\n        uses: actions/checkout@v5\n",
    )
    dockerfile = _write(tmp_path, "Dockerfile", _DOCKERFILE_AGREEING)
    rc = drift.main(["--ci-workflow", str(ci_yml), "--dockerfile", str(dockerfile)])
    assert rc == 2


def test_the_committed_dockerfile_and_ci_yml_agree_today():
    """Proof, not just a unit test: the REAL committed .ci/Dockerfile and
    .github/workflows/ci.yml must agree right now. Run via subprocess (the
    actual CLI entrypoint), same as a developer/CI would invoke it."""
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / "check_ci_docker_drift.py")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
