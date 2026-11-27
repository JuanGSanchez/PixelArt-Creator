r"""Regression test for the CI temp-root step of ``build-installers.yml``.

THE FAILURE THIS PINS. On the Windows leg the installer build compiles with
the runner image's default MSVC toolset (``cl`` 19.52) and ``/GL``. The step
"Set up CI temp root (CI-PixelArtCreator)" used to hand ``TMP``, ``TEMP`` and
``TMPDIR`` a path built from ``${RUNNER_TEMP}``, which on that runner is
``D:\a\_temp`` followed by forward slashes
(``D:\a\_temp/CI-PixelArtCreator/ci-build-installers-windows-latest``). With
that value in ``TMP`` the compiler could not open its intermediate file and the
build stopped with ``C1083``. The same folder written with backslashes only
compiled cleanly on the same image, and so did the same compile with another
toolset, without ``/GL``, or with the runner's default temporary folder.

WHAT IS PINNED. The step runs under ``bash`` on every leg (``shell: bash``), so
this test extracts the step's ``run`` body from the workflow, runs it with the
flags the job's shell uses, and reads the file the step appends to
(``GITHUB_ENV``):

* on a Windows leg, ``TMP``, ``TEMP`` and ``TMPDIR`` equal ``CI_TEMP_ROOT`` with
  every ``/`` turned into ``\`` and hold no ``/`` at all;
* ``CI_TEMP_ROOT`` keeps its form, because the clean-up step compares it with
  ``${RUNNER_TEMP}/CI-PixelArtCreator/*`` and refuses to delete anything else;
* on a Linux or macOS leg all four values are the same string, as before;
* the clean-up step, given that ``CI_TEMP_ROOT``, exits 0 and removes the folder.

WHAT IS NOT PROVEN HERE. No compiler runs in this suite. The compiler half (cl
19.52 with ``/GL`` accepting the backslash-only value) is proven by a green
Windows leg of the installer workflow, not by this module. What this module
reproduces is the condition the repository controls: the values the step writes
when ``RUNNER_OS`` is ``Windows``. It reproduces that on any operating system by
setting ``RUNNER_OS``, so off Windows the Windows case checks the spelling only
(``\tmp\...`` is not a path there).

WHICH ``bash``. As for ``test_check_payload.py``: a ``bash`` on ``PATH`` is
accepted unless it is the WSL launcher (``System32`` or ``WindowsApps``), then
Git for Windows' own ``bash.exe`` is tried. When none is found the test FAILS and
prints what it looked at; it never skips, because a skip would turn a leg green
on a check that did not run.

Deliberately NOT ``@pytest.mark.integration``: it must run on every leg of the
quality-gate matrix, and it spawns only ``bash``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest
import yaml

from .conftest import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-installers.yml"
JOB = "build-installers"
SETUP_STEP = "Set up CI temp root (CI-PixelArtCreator)"
CLEANUP_STEP = "Clean up CI temp root (CI-PixelArtCreator)"
MATRIX_OS_EXPRESSION = "${{ matrix.os }}"
TEMP_VARIABLES = ("TMP", "TEMP", "TMPDIR")

#: ``(matrix.os, RUNNER_OS)`` of the three legs, as the runner reports them.
LEGS = [
    pytest.param("windows-latest", "Windows", id="windows-latest"),
    pytest.param("ubuntu-latest", "Linux", id="ubuntu-latest"),
    pytest.param("macos-latest", "macOS", id="macos-latest"),
]

#: The flags the job's ``shell: bash`` runs a step with.
BASH_FLAGS = ["--noprofile", "--norc", "-eo", "pipefail", "-c"]
BASH_TIMEOUT_SECONDS = 120

_WSL_LAUNCHER_PARTS = ("system32", "windowsapps")


# --------------------------------------------------------------------------- #
# Resolving the bash the workflows use
# --------------------------------------------------------------------------- #
def _is_wsl_launcher(path: str) -> bool:
    lowered = path.replace("\\", "/").lower()
    return any(f"/{part}/" in lowered for part in _WSL_LAUNCHER_PARTS)


def _find_bash() -> Tuple[Optional[str], List[str]]:
    """Return (bash path or None, what was looked at)."""
    looked: List[str] = []
    on_path = shutil.which("bash")
    looked.append(f"bash on PATH: {on_path}")
    if on_path and not _is_wsl_launcher(on_path):
        return on_path, looked
    if os.name == "nt":
        git = shutil.which("git")
        looked.append(f"git on PATH: {git}")
        candidates: List[Path] = []
        if git:
            git_root = Path(git).resolve().parent.parent
            candidates += [
                git_root / "bin" / "bash.exe",
                git_root / "usr" / "bin" / "bash.exe",
            ]
        for var in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                candidates.append(Path(base) / "Git" / "bin" / "bash.exe")
        for cand in candidates:
            looked.append(f"candidate: {cand}")
            if cand.is_file():
                return str(cand), looked
    return None, looked


@pytest.fixture(scope="module")
def bash() -> str:
    found, looked = _find_bash()
    if found is None:
        pytest.fail(
            "no usable bash found (Git Bash on Windows, bash elsewhere); "
            "the temp-root step cannot be exercised, and a skip would hide "
            "that. Looked at: " + "; ".join(looked),
            pytrace=False,
        )
    return found


# --------------------------------------------------------------------------- #
# Running the workflow's own step bodies
# --------------------------------------------------------------------------- #
def _step_body(name: str) -> str:
    """Return the ``run`` body of the one step called ``name`` in the job."""
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"][JOB]["steps"]
    found = [step for step in steps if step.get("name") == name]
    assert len(found) == 1, (
        f"expected exactly one step named {name!r} in job {JOB!r} of "
        f"{WORKFLOW.name}, found {len(found)}"
    )
    body = found[0]["run"]
    assert isinstance(body, str), f"step {name!r} has no run body"
    return body


def _run_bash(
    bash: str, script: str, env: Dict[str, str]
) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        [bash, *BASH_FLAGS, script],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=BASH_TIMEOUT_SECONDS,
        check=False,
    )


def _read_env_file(path: Path) -> Dict[str, List[str]]:
    """Parse a ``GITHUB_ENV`` file into ``{name: [every value written]}``."""
    values: Dict[str, List[str]] = {}
    for line in path.read_bytes().decode("utf-8").splitlines():
        name, separator, value = line.partition("=")
        assert separator, f"GITHUB_ENV line without '=': {line!r}"
        values.setdefault(name, []).append(value)
    return values


def _run_setup_step(
    bash: str, tmp_path: Path, matrix_os: str, runner_os: str
) -> Tuple[Path, Dict[str, str]]:
    """Run the setup step for one leg; return (RUNNER_TEMP, the four values)."""
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    github_env = tmp_path / "github-env.txt"
    github_env.write_bytes(b"")
    job_github_env = os.environ.get("GITHUB_ENV")
    assert str(github_env) != job_github_env, "GITHUB_ENV must not be the job's own"

    body = _step_body(SETUP_STEP)
    assert body.count(MATRIX_OS_EXPRESSION) == 1, (
        f"expected {MATRIX_OS_EXPRESSION} once in the {SETUP_STEP!r} body, "
        f"found {body.count(MATRIX_OS_EXPRESSION)}"
    )
    env = {
        "PATH": os.environ["PATH"],
        "RUNNER_TEMP": str(runner_temp),
        "RUNNER_OS": runner_os,
        "GITHUB_ENV": str(github_env),
    }
    done = _run_bash(bash, body.replace(MATRIX_OS_EXPRESSION, matrix_os), env)
    assert done.returncode == 0, (
        f"{SETUP_STEP!r} exited {done.returncode} for {matrix_os}; "
        f"stdout={done.stdout!r} stderr={done.stderr!r}"
    )

    written = _read_env_file(github_env)
    values: Dict[str, str] = {}
    for name in ("CI_TEMP_ROOT", *TEMP_VARIABLES):
        assert len(written.get(name, [])) == 1, (
            f"{name} must be written to GITHUB_ENV exactly once, "
            f"got {written.get(name, [])!r}"
        )
        values[name] = written[name][0]
    return runner_temp, values


# --------------------------------------------------------------------------- #
# The cases
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("matrix_os, runner_os", LEGS)
def test_setup_step_writes_the_temp_variables(
    bash: str, tmp_path: Path, matrix_os: str, runner_os: str
) -> None:
    """TMP, TEMP and TMPDIR are backslash-only on Windows and unchanged elsewhere."""
    runner_temp, values = _run_setup_step(bash, tmp_path, matrix_os, runner_os)

    root = values["CI_TEMP_ROOT"]
    assert root == f"{runner_temp}/CI-PixelArtCreator/ci-build-installers-{matrix_os}"
    assert Path(root).is_dir(), f"CI_TEMP_ROOT {root!r} was not created"

    for variable in TEMP_VARIABLES:
        value = values[variable]
        if runner_os == "Windows":
            assert "/" not in value, (
                f"{variable} = {value!r} holds a forward slash on a Windows "
                "leg; the compiler cannot open its intermediate file there"
            )
            expected = root.replace("/", "\\")
        else:
            expected = root
        assert value == expected, (
            f"{variable} = {value!r}, expected {expected!r} "
            f"(CI_TEMP_ROOT = {root!r}, RUNNER_OS = {runner_os})"
        )


@pytest.mark.parametrize("matrix_os, runner_os", LEGS)
def test_cleanup_step_removes_the_root(
    bash: str, tmp_path: Path, matrix_os: str, runner_os: str
) -> None:
    """The clean-up step accepts the step's CI_TEMP_ROOT and removes the folder."""
    runner_temp, values = _run_setup_step(bash, tmp_path, matrix_os, runner_os)
    root = values["CI_TEMP_ROOT"]
    assert Path(root).is_dir(), f"CI_TEMP_ROOT {root!r} was not created"

    env = {
        "PATH": os.environ["PATH"],
        "RUNNER_TEMP": str(runner_temp),
        "RUNNER_OS": runner_os,
        "CI_TEMP_ROOT": root,
    }
    done = _run_bash(bash, _step_body(CLEANUP_STEP), env)
    assert done.returncode == 0, (
        f"{CLEANUP_STEP!r} exited {done.returncode} for CI_TEMP_ROOT {root!r}; "
        f"stdout={done.stdout!r} stderr={done.stderr!r}"
    )
    assert not Path(root).exists(), f"CI_TEMP_ROOT {root!r} is still there"
