"""Every ``pip install`` in ``build-installers.yml`` must pin what it installs.

REQ-VI-BUILD-006. Placed under ``testing/suites/deploy/`` -- the pipeline
vehicles this agent owns (ADR-0043 §1) -- and deliberately NOT
``@pytest.mark.integration``, the same ruling as ``test_ci_matrix_shape.py``
beside it: a read-only parse of one YAML file, no subprocess, no network. It
belongs in the default gate.

WHY THIS TEST EXISTS (measured 2026-10-12): the installer workflow ran
``python -m pip install nuitka`` with no version. The runs of 2026-09-25
resolved Nuitka 4.2.2 and were green; the run of 2026-10-12 resolved Nuitka 4.3
on all three legs, and every frozen app then crashed at launch (exit 139, empty
output) -- the same source built with 4.2.2 printed its font line and exited 0,
and so did a pre-branch commit that had been green. Nothing in the repository
had changed between the two runs; the package index had. A build tool that
floats makes a green run a statement about a day, not about a commit.

WHAT IT CHECKS, for every ``run:`` step of every job in the file:

* each package ``pip install`` names must carry an exact ``==<version>``. A
  bare name, ``>=``, ``~=``, ``!=`` and a wildcard ``==4.*`` all fail;
* a local install (``-e .``) is the project itself, not an index package, and
  passes ONLY when the same command carries ``-c <file>`` -- that is how the
  project's runtime closure is pinned (``constraints.txt``);
* ``-r <file>`` and a VCS or URL requirement fail: their content is not
  readable from the workflow, so this test cannot vouch for them;
* the file must contain pip installs at all, and one that names ``nuitka``.
  A scan that finds nothing to check is not a pass (a gate that cannot see its
  subject reports green and means nothing).

The checker is a plain function and is itself exercised against synthetic
workflows below, including planted unpinned lines, so that "the test is green"
and "the test can fail" are both on record.
"""

from __future__ import annotations

import re
import shlex
from typing import List, Tuple

import pytest
import yaml

from .conftest import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-installers.yml"

_PIP_INSTALL = re.compile(r"\bpip3?\s+install\b")
_NUITKA_INSTALL = re.compile(r"\bpip\s+install\b[^\n]*\bnuitka\b", re.IGNORECASE)
_NUITKA_EXACT = re.compile(r"\bpip\s+install\s+nuitka==\d")

#: Options that consume the NEXT token as their value (so it is not a package).
_VALUE_OPTIONS = frozenset(
    {
        "-c",
        "--constraint",
        "-r",
        "--requirement",
        "-e",
        "--editable",
        "-i",
        "--index-url",
        "--extra-index-url",
        "-f",
        "--find-links",
        "-t",
        "--target",
        "--prefix",
        "--root",
        "--python",
        "--platform",
        "--implementation",
        "--abi",
        "--python-version",
        "--upgrade-strategy",
        "--cache-dir",
        "--log",
        "--proxy",
        "--retries",
        "--timeout",
        "--src",
        "--no-binary",
        "--only-binary",
        "-C",
        "--config-settings",
        "--report",
        "--progress-bar",
        "--exists-action",
        "--trusted-host",
        "--cert",
        "--client-cert",
        "--use-feature",
        "--use-deprecated",
    }
)

_SHELL_BREAKS = frozenset({"&&", "||", ";", "|", "&", ";;"})

#: name[extras]==version, with no wildcard; an environment marker may follow.
_EXACT_PIN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._\-]*(\[[A-Za-z0-9,._\-]+\])?"
    r"==[0-9][A-Za-z0-9.!+_\-]*(\s*;.*)?$"
)


def _is_local(token: str) -> bool:
    """True for a path requirement (``.``, ``./x``, ``.[dev]``, absolute)."""
    return token.startswith((".", "/", "~")) or bool(
        re.match(r"^[A-Za-z]:[\\/]", token)
    )


def _tokens(line: str) -> List[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    return list(lexer)


def _run_blocks(workflow_text: str) -> List[Tuple[str, str]]:
    """``(job: step name, run script)`` for every ``run:`` step of every job."""
    doc = yaml.safe_load(workflow_text)
    blocks: List[Tuple[str, str]] = []
    for job_id, job in (doc.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps") or []):
            script = step.get("run")
            if isinstance(script, str):
                label = f"{job_id}: {step.get('name', f'step {index}')}"
                blocks.append((label, script))
    return blocks


def pip_install_findings(workflow_text: str) -> Tuple[int, List[str]]:
    """Scan a workflow; return ``(pip install commands seen, problems)``.

    A problem is a human-readable line naming the step and the offending
    requirement. An empty list with a positive count is the only clean result.
    """
    seen = 0
    problems: List[str] = []
    for label, script in _run_blocks(workflow_text):
        # A trailing backslash continues the command on the next line.
        joined = re.sub(r"\\\r?\n", " ", script)
        for line in joined.splitlines():
            # Only a line that mentions an install is worth tokenising; other
            # lines (an awk program spread over several lines, say) are not
            # shell this scan is meant to understand.
            if not _PIP_INSTALL.search(line):
                continue
            try:
                tokens = _tokens(line)
            except ValueError:
                problems.append(f"{label}: unparseable shell line: {line.strip()!r}")
                continue
            for i in range(len(tokens) - 1):
                if tokens[i] not in ("pip", "pip3") or tokens[i + 1] != "install":
                    continue
                seen += 1
                args: List[str] = []
                for token in tokens[i + 2 :]:
                    if token in _SHELL_BREAKS:
                        break
                    args.append(token)
                problems.extend(_judge_command(label, args))
    return seen, problems


def _judge_command(label: str, args: List[str]) -> List[str]:
    problems: List[str] = []
    constrained = False
    local: List[str] = []
    j = 0
    while j < len(args):
        arg = args[j]
        if arg.startswith("-"):
            name = arg.split("=", 1)[0]
            value = None
            if name in _VALUE_OPTIONS:
                if "=" in arg:
                    value = arg.split("=", 1)[1]
                elif j + 1 < len(args):
                    value = args[j + 1]
                    j += 1
            if name in ("-c", "--constraint"):
                constrained = True
            elif name in ("-r", "--requirement"):
                problems.append(
                    f"{label}: `{arg} {value}` -- a requirements file is not "
                    "readable from the workflow, so its pins cannot be verified here"
                )
            elif name in ("-e", "--editable"):
                if value is not None and _is_local(value):
                    local.append(value)
                else:
                    problems.append(
                        f"{label}: editable requirement {value!r} is not a local path"
                    )
        elif _is_local(arg):
            local.append(arg)
        elif not _EXACT_PIN.match(arg):
            problems.append(
                f"{label}: `pip install {arg}` is not pinned with an exact "
                "`==<version>`"
            )
        j += 1
    if local and not constrained:
        problems.append(
            f"{label}: local install {local} without `-c <constraints file>` "
            "leaves its dependency closure floating"
        )
    return problems


# ---------------------------------------------------------------------------
# The real workflow
# ---------------------------------------------------------------------------


def test_every_pip_install_in_build_installers_is_pinned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    seen, problems = pip_install_findings(text)
    assert seen > 0, "no `pip install` in build-installers.yml: the scan saw nothing"
    assert not problems, (
        f"{len(problems)} unpinned install(s) in {WORKFLOW.name} (an index change "
        "between two runs must not be able to change a build):\n  "
        + "\n  ".join(problems)
    )


def test_build_installers_installs_nuitka_with_an_exact_pin() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    scripts = [script for _, script in _run_blocks(text)]
    assert any(
        _NUITKA_INSTALL.search(s) for s in scripts
    ), "no `pip install ... nuitka` step: the toolchain step moved or vanished"
    assert any(
        _NUITKA_EXACT.search(s) for s in scripts
    ), "nuitka is not installed with an exact `==` pin"


# ---------------------------------------------------------------------------
# The checker can fail (planted lines)
# ---------------------------------------------------------------------------

_TEMPLATE = """\
name: planted
on: workflow_dispatch
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Install toolchain
        run: |
{body}
"""


def _workflow(*lines: str) -> str:
    return _TEMPLATE.format(body="\n".join("          " + line for line in lines))


def test_the_pinned_workflow_shape_is_clean() -> None:
    text = _workflow(
        "python -m pip install --upgrade pip==26.2.1",
        "python -m pip install -c constraints.txt -e .",
        "python -m pip install nuitka==4.2.2",
    )
    seen, problems = pip_install_findings(text)
    assert (seen, problems) == (3, [])


@pytest.mark.parametrize(
    "planted",
    [
        "python -m pip install nuitka",
        "python -m pip install 'nuitka>=4.2'",
        "python -m pip install nuitka>=4.2",
        "python -m pip install 'nuitka~=4.2'",
        "python -m pip install 'nuitka==4.*'",
        "python -m pip install --upgrade pip",
        "python -m pip install -e .",
        "python -m pip install -r requirements.txt",
        "python -m pip install git+https://example.invalid/x.git",
        "pip3 install ordered-set zstandard==0.23.0",
    ],
)
def test_a_planted_unpinned_install_is_reported(planted: str) -> None:
    text = _workflow("python -m pip install nuitka==4.2.2", planted)
    seen, problems = pip_install_findings(text)
    assert seen == 2
    assert problems, f"planted line passed unreported: {planted!r}"


def test_a_planted_line_continued_with_a_backslash_is_still_reported() -> None:
    text = _workflow(
        "python -m pip install \\",
        "  nuitka==4.2.2 \\",
        "  zstandard",
    )
    _, problems = pip_install_findings(text)
    assert len(problems) == 1 and "zstandard" in problems[0]


def test_a_command_after_a_shell_break_is_judged_on_its_own() -> None:
    text = _workflow("python -m pip install nuitka==4.2.2 && echo done")
    assert pip_install_findings(text) == (1, [])


def test_a_workflow_with_no_pip_install_reports_zero_seen() -> None:
    # The real-workflow test turns `seen == 0` into a failure.
    assert pip_install_findings(_workflow("echo nothing to see")) == (0, [])
