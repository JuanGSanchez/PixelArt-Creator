"""Static packaging-artifact contract tests (T-36/T-37/T-39, remediation register).

Placed under ``testing/suites/deploy/`` (moved from ``tests/deploy/`` on
2026-08-30, ADR-0065) -- AGT-09's owned surface (ADR-0043 §1: this
agent owns ``packaging/**`` and the pipeline vehicles that build/ship the
product) -- but deliberately **NOT** ``@pytest.mark.integration``, on the same
precedent as ``test_run_ci_router.py`` already in this directory: nothing
here spawns a subprocess, needs Docker, needs Nginx, or reaches outside the
process. Every assertion is either (a) a filesystem existence check on a
committed artifact, (b) a read-only parse of the committed
``.github/workflows/ci.yml`` / ``pyproject.toml``, or (c) an in-process
``importlib.metadata`` entry-point resolution + invocation of code that is
already part of this suite's own installed environment. All three run happily
under the default gate (no external dependency, no network, no launched
process), so marking this module ``integration`` would be a WRONG ruling --
it would hide these checks from every ordinary CI run for no reason ADR-0043
requires. Reading the workflow YAML is explicitly permitted by this task;
nothing here writes to it.

Covers:
  T-36 (REQ-P13-BUILD-002..005) -- the four packaging artifacts the
    ``build-installers`` job's CI legs name (the three ``pysidedeploy-*.spec``
    files + ``build_appimage.sh``) exist on disk, are referenced by the
    workflow steps that build from them, and the ``build-installers`` matrix
    declares three OSes with ``fail-fast: false`` and three artifact uploads.
  T-37 -- ``pyproject.toml``'s ``[tool.setuptools.package-data]`` block ships
    ``userguide_content/**/*.md`` and ``userguide_content/*.json`` (T-UG-09's
    acceptance criterion, previously unasserted by any test).
  T-39 -- the three ``[project.scripts]`` console entry points
    (``pixelart-export``, ``pixelart-run``, ``pixelart-assistant``) resolve
    via ``importlib.metadata`` and each invoked callable's ``--help`` exits 0.
"""

from __future__ import annotations

import sys
import tomllib
from importlib.metadata import entry_points

import pytest
import yaml

from .conftest import REPO_ROOT

CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGING_DIR = REPO_ROOT / "packaging"


def _load_ci_yaml() -> dict:
    return yaml.safe_load(CI_YAML.read_text(encoding="utf-8"))


def _load_pyproject() -> dict:
    with open(PYPROJECT, "rb") as fh:
        return tomllib.load(fh)


# --------------------------------------------------------------------------- #
# T-36 -- the four packaging artifacts exist, and CI's build-installers job
# references and ships from them.
# --------------------------------------------------------------------------- #
_EXPECTED_ARTIFACTS = (
    "pysidedeploy-windows.spec",
    "pysidedeploy-linux.spec",
    "pysidedeploy-macos.spec",
    "build_appimage.sh",
)


@pytest.mark.parametrize("filename", _EXPECTED_ARTIFACTS)
def test_packaging_artifact_file_exists(filename):
    path = PACKAGING_DIR / filename
    assert path.is_file(), f"expected packaging artifact missing: {path}"


def test_ci_build_installers_job_references_every_packaging_artifact():
    """Read-only substring check: each of the four artifacts named above is
    actually referenced somewhere in ci.yml's step commands -- not merely
    present on disk with nothing wiring it into the build."""
    raw = CI_YAML.read_text(encoding="utf-8")
    for filename in _EXPECTED_ARTIFACTS:
        assert f"packaging/{filename}" in raw, (
            f"ci.yml never references packaging/{filename} -- the artifact "
            "exists on disk but the workflow does not build from it"
        )


def test_ci_build_installers_matrix_declares_three_oses_fail_fast_false():
    data = _load_ci_yaml()
    job = data["jobs"]["build-installers"]
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["os"] == [
        "ubuntu-latest",
        "windows-latest",
        "macos-latest",
    ]


def test_ci_build_installers_uploads_three_artifacts():
    data = _load_ci_yaml()
    steps = data["jobs"]["build-installers"]["steps"]
    upload_steps = [
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/upload-artifact")
    ]
    assert len(upload_steps) == 3, (
        f"expected exactly 3 upload-artifact steps (one per OS leg), found "
        f"{len(upload_steps)}: {[s.get('name') for s in upload_steps]}"
    )
    uploaded_names = {step["with"]["name"] for step in upload_steps}
    assert uploaded_names == {
        "pixelart-creator-windows",
        "pixelart-creator-linux",
        "pixelart-creator-macos",
    }


# --------------------------------------------------------------------------- #
# T-37 -- package-data ships the offline User Guide bundle (T-UG-09).
# --------------------------------------------------------------------------- #
def test_pyproject_package_data_ships_userguide_content():
    data = _load_pyproject()
    package_data = data["tool"]["setuptools"]["package-data"]
    globs = package_data["pixelart_creator"]
    assert "userguide_content/**/*.md" in globs
    assert "userguide_content/*.json" in globs


# --------------------------------------------------------------------------- #
# T-39 -- console entry points resolve and answer --help with exit 0.
#
# Resolution is via importlib.metadata, NOT a subprocess call to a PATH
# shim: this suite must pass in an environment where the project is
# editable-installed but the interpreter's Scripts/bin directory is not
# necessarily on PATH (a pip-installed console shim is a packaging nicety,
# not something the default test gate should require). If a PATH shim
# happens to be present too, that's recorded below for information only --
# it is never asserted on, per this task's explicit scoping.
# --------------------------------------------------------------------------- #
_CONSOLE_SCRIPTS = ("pixelart-export", "pixelart-run", "pixelart-assistant")


def test_pyproject_declares_the_expected_console_scripts():
    data = _load_pyproject()
    scripts = data["project"]["scripts"]
    assert scripts == {
        "pixelart-export": "pixelart_creator.data.export_cli:main",
        "pixelart-run": "pixelart_creator.data.automation_cli:main",
        "pixelart-assistant": "pixelart_creator.data.assistant_cli:main",
    }


@pytest.mark.parametrize("script_name", _CONSOLE_SCRIPTS)
def test_console_script_resolves_and_help_exits_0(script_name):
    """Resolve ``script_name`` via importlib.metadata's console_scripts group,
    load the callable, invoke it with ``--help``, and assert the argparse
    convention (SystemExit(0)) rather than requiring a pip-installed shim on
    PATH. Whether a PATH shim ALSO exists is recorded honestly, not asserted."""
    matches = list(entry_points(group="console_scripts", name=script_name))
    assert matches, (
        f"{script_name!r} is not resolvable via importlib.metadata's "
        "console_scripts group in this environment -- either the project is "
        "not installed (editable or otherwise) or pyproject.toml's "
        "[project.scripts] entry is missing/misnamed"
    )
    callable_ = matches[0].load()

    old_argv = sys.argv
    sys.argv = [script_name, "--help"]
    try:
        with pytest.raises(SystemExit) as exc_info:
            callable_()
    finally:
        sys.argv = old_argv
    assert exc_info.value.code == 0, (
        f"{script_name} --help exited {exc_info.value.code!r}, expected 0 "
        "(argparse's own --help convention)"
    )


def test_console_script_path_shim_availability_is_recorded_not_required():
    """Informational only (per this task's scoping): if the interpreter's
    Scripts/bin console shims are ALSO on PATH, note it; if not, that is not
    a failure -- the resolution+invocation test above is this suite's real
    contract, and it does not depend on PATH."""
    import shutil

    on_path = {name: shutil.which(name) is not None for name in _CONSOLE_SCRIPTS}
    # No assertion: this is a recorded observation, not a requirement. The
    # entry-point resolution tests above are the actual T-39 acceptance.
    assert isinstance(on_path, dict)
