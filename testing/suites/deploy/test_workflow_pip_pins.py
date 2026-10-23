"""Every ``pip install`` in ``build-installers.yml`` must pin what it installs.

REQ-VI-BUILD-006. Placed under ``testing/suites/deploy/`` -- the pipeline
vehicles that belong to the delivery pipeline (ADR-0043 §1) -- and deliberately NOT
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
  subject reports green and means nothing);
* a version may be written ONCE, as a workflow ``env:`` variable (``NUITKA_PIN``,
  ``PATCHELF_PIN``) that the install references as ``${NUITKA_PIN}``. The scan
  expands such a variable before judging the line, so ``nuitka==${NUITKA_PIN}``
  is read as the exact pin it resolves to.

THE TOOLCHAIN CONTRACT (user ruling 2026-10-22, "if this is going to happen to
every PR and reaching main, it must be fixed"). A pin is only a request to pip;
what pip leaves installed is what builds the binary. So every workflow whose
``run:`` scripts mention ``nuitka`` or ``pyside6-deploy`` -- in ANY file under
``.github/workflows/``, not just the installer one -- must also:

* declare ``NUITKA_PIN`` and ``PATCHELF_PIN`` as exact versions in ``env:``;
* install through the variable, with no second literal version beside it;
* carry an unconditional drift-guard step AFTER that install and BEFORE the
  first ``pyside6-deploy``, which compares the INSTALLED version
  (``importlib.metadata``) to the same variable, fails with ``::error::`` and
  ``exit 1``, holds no literal version of its own, and has no ``if:`` or
  ``continue-on-error`` that could let a leg skip it;
* repeat that guard AFTER the freeze: every step that runs ``pyside6-deploy`` is
  immediately followed by a guard step carrying the build step's own ``if:``
  (so no leg that froze the app can skip it), because pyside6-deploy may
  pip-install or replace Nuitka while it builds and the version checked at
  install time is then not the one that made the binary.

Removing the guard, unpinning the install, or letting a literal disagree with
the variable each fail a test below. The checkers are plain functions, exercised
against the real workflow text with planted defects and against synthetic ones,
so that "the test is green" and "the test can fail" are both on record.
"""

from __future__ import annotations

import re
import shlex
from typing import Any, Dict, List, Tuple

import pytest
import yaml

from .conftest import REPO_ROOT

WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS_DIR / "build-installers.yml"

_PIP_INSTALL = re.compile(r"\bpip3?\s+install\b")
_NUITKA_INSTALL = re.compile(r"\bpip\s+install\b[^\n]*\bnuitka\b", re.IGNORECASE)
_NUITKA_EXACT = re.compile(r"\bpip\s+install\s+[\"']?nuitka==\d")

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


#: A workflow ``env:`` value this scan will substitute into a script: a bare
#: version literal. Anything else (an expression, a path) is left alone.
_VERSION_LITERAL = re.compile(r"^[0-9][A-Za-z0-9.!+_\-]*$")


def _version_env(doc: Dict[str, Any]) -> Dict[str, str]:
    """Version-literal ``env:`` entries of the workflow and of every job."""
    env: Dict[str, str] = {}
    scopes = [doc.get("env") or {}]
    scopes += [(job.get("env") or {}) for job in (doc.get("jobs") or {}).values()]
    for scope in scopes:
        for name, value in scope.items():
            if isinstance(value, (str, int, float)) and _VERSION_LITERAL.match(
                str(value)
            ):
                env[str(name)] = str(value)
    return env


def _expand(script: str, env: Dict[str, str]) -> str:
    """Replace ``${NAME}`` / ``$NAME`` by its declared version literal."""
    for name, value in env.items():
        script = re.sub(r"\$\{" + re.escape(name) + r"\}", value, script)
        script = re.sub(r"\$" + re.escape(name) + r"\b", value, script)
    return script


def _run_blocks(workflow_text: str, expand: bool = False) -> List[Tuple[str, str]]:
    """``(job: step name, run script)`` for every ``run:`` step of every job.

    With ``expand`` the workflow's version-literal ``env:`` variables are
    substituted, so ``nuitka==${NUITKA_PIN}`` reads as the pin it names.
    """
    doc = yaml.safe_load(workflow_text)
    env = _version_env(doc) if expand else {}
    blocks: List[Tuple[str, str]] = []
    for job_id, job in (doc.get("jobs") or {}).items():
        for index, step in enumerate(job.get("steps") or []):
            script = step.get("run")
            if isinstance(script, str):
                label = f"{job_id}: {step.get('name', f'step {index}')}"
                blocks.append((label, _expand(script, env) if expand else script))
    return blocks


def pip_install_findings(workflow_text: str) -> Tuple[int, List[str]]:
    """Scan a workflow; return ``(pip install commands seen, problems)``.

    A problem is a human-readable line naming the step and the offending
    requirement. An empty list with a positive count is the only clean result.
    """
    seen = 0
    problems: List[str] = []
    for label, script in _run_blocks(workflow_text, expand=True):
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
# The toolchain contract: single-sourced pins + a runtime drift guard
# ---------------------------------------------------------------------------

#: (tool as importlib.metadata names it, the workflow ``env:`` variable pinning it)
_TOOLCHAIN = (("nuitka", "NUITKA_PIN"), ("patchelf", "PATCHELF_PIN"))
_FREEZE = re.compile(r"pyside6-deploy|\bnuitka\b", re.IGNORECASE)
#: a dotted version literal, not part of a longer token or a variable reference
_VERSION_IN_CODE = re.compile(r"(?<![\w.$])\d+\.\d+(?:\.\d+)*")


def _code(script: str) -> str:
    """The script without whole-line shell comments."""
    return "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )


def _var_ref(var: str) -> str:
    return r"\$\{?" + var + r"\}?"


def freezes_the_app(workflow_text: str) -> bool:
    """True when any ``run:`` script drives Nuitka or ``pyside6-deploy``."""
    return any(_FREEZE.search(_code(s)) for _, s in _run_blocks(workflow_text))


def _guard_problems(
    step: Dict[str, Any],
    job: Dict[str, Any],
    where: str,
    expected_if: Any = None,
) -> List[str]:
    """Judge one guard step.

    ``expected_if`` is the only ``if:`` the step may carry: ``None`` for the
    guard after the install (it must run on every leg), the build step's own
    condition for a guard after a build (it must run wherever that build did).
    """
    problems: List[str] = []
    code = _code(step["run"])
    if step.get("if") != expected_if:
        problems.append(
            f"{where}: the guard step's `if:` is {step.get('if')!r}, expected "
            f"{expected_if!r} -- a leg could skip it"
        )
    if step.get("continue-on-error") or job.get("continue-on-error"):
        problems.append(f"{where}: the guard (or its job) is `continue-on-error`")
    for tool, var in _TOOLCHAIN:
        if not re.search(r"version\(\s*['\"]" + tool + r"['\"]\s*\)", code, re.I):
            problems.append(
                f"{where}: the guard never reads the INSTALLED {tool} version "
                f"(importlib.metadata version('{tool}'))"
            )
        if not re.search(r"!=\s*\"?" + _var_ref(var) + r"\"?", code):
            problems.append(
                f"{where}: the guard does not compare the installed {tool} against "
                f"${{{var}}} with `!=`"
            )
    lines = [line.strip() for line in code.splitlines()]
    errors = [i for i, line in enumerate(lines) if "::error::" in line]
    if not errors:
        problems.append(f"{where}: the guard never emits `::error::`")
    for i in errors:
        if i + 1 >= len(lines) or lines[i + 1] != "exit 1":
            problems.append(
                f"{where}: a guard `::error::` is not followed by `exit 1`, so it "
                "reports and carries on"
            )
    literals = _VERSION_IN_CODE.findall(code)
    if literals:
        problems.append(
            f"{where}: the guard holds a literal version {literals} -- the pin must "
            "be read from the env variable only, never written a second time"
        )
    return problems


def toolchain_contract_findings(workflow_text: str) -> List[str]:
    """Judge every job that freezes the app; ``[]`` when none exists or all pass."""
    doc = yaml.safe_load(workflow_text)
    env = _version_env(doc)
    problems: List[str] = []
    for job_id, job in (doc.get("jobs") or {}).items():
        steps = job.get("steps") or []
        runs = [s.get("run") if isinstance(s.get("run"), str) else "" for s in steps]
        if not any(_FREEZE.search(_code(r)) for r in runs):
            continue
        where = f"job `{job_id}`"
        for tool, var in _TOOLCHAIN:
            if var not in env:
                problems.append(
                    f"{where}: `env: {var}` is missing or is not an exact version "
                    "literal (the single source of the pin)"
                )
        install = next(
            (i for i, r in enumerate(runs) if _NUITKA_INSTALL.search(_code(r))), None
        )
        deploy = next(
            (i for i, r in enumerate(runs) if "pyside6-deploy" in _code(r)), None
        )
        if install is None:
            problems.append(f"{where}: no `pip install ... nuitka` step")
            continue
        for tool, var in _TOOLCHAIN:
            referenced = any(
                re.search(tool + r"==\"?" + _var_ref(var), _code(r))
                for r in runs[: install + 1]
            )
            literal = any(re.search(r"\b" + tool + r"==\d", _code(r)) for r in runs)
            if not referenced:
                problems.append(
                    f"{where}: {tool} is not installed as `{tool}==${{{var}}}` "
                    "before the guard"
                )
            if literal:
                problems.append(
                    f"{where}: a literal `{tool}==<version>` is written beside "
                    f"${{{var}}} -- two sources of one pin can disagree"
                )
        guard = next(
            (
                i
                for i in range(install + 1, len(runs))
                if "importlib.metadata" in runs[i] and "NUITKA_PIN" in runs[i]
            ),
            None,
        )
        if guard is None:
            problems.append(
                f"{where}: no drift-guard step after the install (a step that reads "
                "importlib.metadata and compares it with NUITKA_PIN)"
            )
            continue
        if deploy is not None and guard > deploy:
            problems.append(
                f"{where}: the drift guard runs AFTER the first pyside6-deploy step"
            )
        problems.extend(_guard_problems(steps[guard], job, where))
        # The same guard again after every freeze (the build may change the
        # toolchain it runs on): the step right after each pyside6-deploy step.
        for i, run in enumerate(runs):
            if "pyside6-deploy" not in _code(run):
                continue
            label = f"{where} step `{steps[i].get('name', i)}`"
            after = steps[i + 1] if i + 1 < len(steps) else {}
            after_run = after.get("run") if isinstance(after.get("run"), str) else ""
            if not ("importlib.metadata" in after_run and "NUITKA_PIN" in after_run):
                problems.append(
                    f"{label}: no drift guard directly after this build step (the "
                    "toolchain is checked only before the build, not after it)"
                )
                continue
            problems.extend(
                _guard_problems(
                    after, job, f"{label} (guard after the build)", steps[i].get("if")
                )
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
    scripts = [script for _, script in _run_blocks(text, expand=True)]
    assert any(
        _NUITKA_INSTALL.search(s) for s in scripts
    ), "no `pip install ... nuitka` step: the toolchain step moved or vanished"
    assert any(
        _NUITKA_EXACT.search(s) for s in scripts
    ), "nuitka is not installed with an exact `==` pin"


def test_build_installers_freezes_the_app_so_the_contract_is_not_vacuous() -> None:
    # A contract scan that finds no freezing job would report green and mean
    # nothing (the file-level rule: a gate that cannot see its subject).
    assert freezes_the_app(WORKFLOW.read_text(encoding="utf-8"))


def test_build_installers_meets_the_toolchain_contract() -> None:
    problems = toolchain_contract_findings(WORKFLOW.read_text(encoding="utf-8"))
    assert not problems, "toolchain contract broken:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize(
    "path", sorted(WORKFLOWS_DIR.glob("*.yml")), ids=lambda p: p.name
)
def test_any_workflow_that_freezes_the_app_meets_the_toolchain_contract(path) -> None:
    """Moving the freeze into another workflow must not escape the guard.

    A workflow that never touches Nuitka passes vacuously (the test above proves
    the contract sees the installer workflow); one that starts to must carry the
    whole contract.
    """
    problems = toolchain_contract_findings(path.read_text(encoding="utf-8"))
    assert not problems, f"{path.name}:\n  " + "\n  ".join(problems)


# ---------------------------------------------------------------------------
# The contract can fail (defects planted in the REAL workflow text, in memory)
# ---------------------------------------------------------------------------

_GUARD_STEP = re.compile(
    r"      - name: Verify the pinned build toolchain \(drift guard\)\n"
    r".*?(?=\n      # -{10,} Windows leg)",
    re.DOTALL,
)
_FIRST_DEPLOY_STEP = "      # ---------------- Windows leg"


def _swap(old: str, new: str):
    def mutate(text: str) -> str:
        assert old in text, f"planted-defect anchor vanished: {old!r}"
        return text.replace(old, new)

    return mutate


def _delete_guard(text: str) -> str:
    assert _GUARD_STEP.search(text), "the guard step is not where the test expects"
    return _GUARD_STEP.sub("", text)


def _move_guard_after_deploy(text: str) -> str:
    match = _GUARD_STEP.search(text)
    assert match, "the guard step is not where the test expects"
    step = match.group(0)
    text = text.replace(step, "")
    anchor = "      - name: Smoke-launch the Windows .exe"
    assert anchor in text
    return text.replace(anchor, step + "\n\n" + anchor, 1)


_POST_GUARD = "      - name: Verify the pinned build toolchain after the build ({os})\n"


def _delete_post_guard(os_name: str):
    def mutate(text: str) -> str:
        pattern = re.compile(
            re.escape(_POST_GUARD.format(os=os_name)) + r".*?(?=\n      - name: )",
            re.DOTALL,
        )
        assert pattern.search(text), f"no post-build guard for {os_name}"
        return pattern.sub("", text, count=1)

    return mutate


_PLANTED = {
    "unpinned-nuitka": _swap('"nuitka==${NUITKA_PIN}"', "nuitka"),
    "loosened-env-pin": _swap('NUITKA_PIN: "4.2.2"', 'NUITKA_PIN: ">=4.2"'),
    "literal-agreeing-with-env": _swap('"nuitka==${NUITKA_PIN}"', "nuitka==4.2.2"),
    "literal-disagreeing-with-env": _swap('"nuitka==${NUITKA_PIN}"', "nuitka==4.2.1"),
    "guard-compares-another-value": _swap('!= "${NUITKA_PIN}"', '!= "4.2.1"'),
    "guard-never-reads-installed-version": _swap(
        "from importlib.metadata import version; print(version('nuitka'))",
        "print('4.2.2')",
    ),
    "guard-cannot-fail": _swap(
        "            exit 1\n          fi\n          nuitka_cli",
        "            :\n          fi\n          nuitka_cli",
    ),
    "guard-skippable": _swap(
        "      - name: Verify the pinned build toolchain (drift guard)\n",
        "      - name: Verify the pinned build toolchain (drift guard)\n"
        "        if: runner.os == 'Linux'\n",
    ),
    "guard-continue-on-error": _swap(
        "      - name: Verify the pinned build toolchain (drift guard)\n",
        "      - name: Verify the pinned build toolchain (drift guard)\n"
        "        continue-on-error: true\n",
    ),
    "guard-deleted": _delete_guard,
    "guard-after-the-build": _move_guard_after_deploy,
    "unpinned-patchelf": _swap('"patchelf==${PATCHELF_PIN}"', "patchelf"),
    "no-guard-after-the-windows-build": _delete_post_guard("Windows"),
    "no-guard-after-the-linux-build": _delete_post_guard("Linux"),
    "no-guard-after-the-macos-build": _delete_post_guard("macOS"),
    "post-build-guard-skippable": _swap(
        _POST_GUARD.format(os="Linux") + "        if: runner.os == 'Linux'\n",
        _POST_GUARD.format(os="Linux") + "        if: runner.os == 'Windows'\n",
    ),
    "post-build-guard-cannot-fail": _swap(
        'the build step changed the toolchain that made this binary."\n'
        "            exit 1\n",
        'the build step changed the toolchain that made this binary."\n'
        "            :\n",
    ),
}


def test_the_real_workflow_is_clean_before_any_defect_is_planted() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert toolchain_contract_findings(text) == []
    assert pip_install_findings(text)[1] == []


@pytest.mark.parametrize("name", sorted(_PLANTED))
def test_a_planted_toolchain_defect_is_reported(name: str) -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = _PLANTED[name](text)
    assert mutated != text, "the planted defect changed nothing"
    contract = toolchain_contract_findings(mutated)
    pins = pip_install_findings(mutated)[1]
    assert (
        contract or pins
    ), f"planted defect {name!r} passed both the contract and the pin scan"


def test_a_workflow_that_freezes_without_any_guard_is_reported() -> None:
    text = _workflow(
        "python -m pip install nuitka==4.2.2",
        "pyside6-deploy -c packaging/x.spec --force",
    )
    problems = toolchain_contract_findings(text)
    assert problems and any("NUITKA_PIN" in p for p in problems)


def test_a_freezing_job_with_no_nuitka_install_is_reported() -> None:
    problems = toolchain_contract_findings(_workflow("pyside6-deploy -c x.spec"))
    assert any("no `pip install ... nuitka`" in p for p in problems)


def test_a_workflow_that_never_freezes_has_nothing_to_judge() -> None:
    assert toolchain_contract_findings(_workflow("echo hello")) == []
    assert not freezes_the_app(_workflow("echo hello"))


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
