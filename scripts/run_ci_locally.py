#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: run_ci_locally  (standalone P11 script -- PixelArt Creator system)
# =============================================================================
# PURPOSE: Run the checks in .github/workflows/ci.yml LOCALLY, without GitHub
#   Actions, by PARSING the workflow file and executing the selected job's
#   `run:` blocks in the order they appear. This is a fallback for whenever
#   GitHub Actions billing is exhausted/blocked, and a way to get fast local
#   feedback without spending hosted minutes. Recorded decision + rationale:
#   docs/adr/0045-local-ci-execution-strategy.md.
# FLAVOUR: standalone
# LOCATION: scripts/run_ci_locally.py
# INVOKED BY: any developer wanting a local, CI-shaped run of the gates.
# RUNTIME: Python 3.10+ (CPython). Needs PyYAML (`import yaml`) to parse the
#   workflow -- available transitively via the `mkdocs` dev dependency
#   ([project.optional-dependencies].dev in pyproject.toml), or installable
#   directly (`pip install pyyaml`). Needs a `bash` on PATH to execute the
#   workflow's `run:` blocks (this workflow sets `defaults: run: shell: bash`
#   on every job) -- on Windows, Git for Windows provides one.
# ENTRYPOINT: python scripts/run_ci_locally.py [--job quality-gate]
#             [--workflow .github/workflows/ci.yml] [--list-jobs] [--dry-run]
#             [--event push] [--ref ""] [--input KEY=VALUE ...]
#             [--only SUBSTRING ...] [--skip SUBSTRING ...]
#             [--runner-os Linux|Windows|macOS]
#             [--context github.KEY=VALUE ...]
#             [--needs-output JOB.NAME=VALUE ...]
# INPUTS:
#   --workflow  (CLI, optional, default ".github/workflows/ci.yml" relative
#               to the repo root computed from this file's location).
#   --job       (CLI, optional, default "quality-gate"): job name (top-level
#               key under `jobs:`) to run.
#   --list-jobs (CLI flag): print the jobs found in the workflow and exit.
#   --dry-run   (CLI flag): parse + evaluate conditions, print the plan, but
#               do not actually execute any `run:` block.
#   --event     (CLI, optional, default "push"): simulated `github.event_name`
#               used to evaluate `if:` expressions that reference it.
#   --ref       (CLI, optional, default ""): simulated `github.ref`.
#   --input     (CLI, repeatable, "KEY=VALUE"): simulated `inputs.KEY` for a
#               `workflow_dispatch` event; falls back to the workflow's own
#               declared default for any input not supplied.
#   --only / --skip (CLI, repeatable): run only / exclude steps whose `name:`
#               contains the given substring (case-insensitive). Selects
#               AMONG the steps the workflow already defines -- it cannot add
#               a step that is not in ci.yml.
#   --runner-os (CLI, optional): SIMULATE the runner's OS for `runner.os` and
#               for the matrix leg that is chosen, e.g. `Linux` to evaluate
#               the workflow's Linux-only steps on a Windows machine. The
#               commands still run on THIS machine, so a step that needs the
#               real OS (apt, sudo) must be left out with --skip. Printed as a
#               simulation, never as the real OS.
#   --context   (CLI, repeatable, "github.KEY=VALUE"): set one value of the
#               `github`, `inputs` or `env` context, e.g.
#               `github.event.pull_request.base.sha=<sha>`. A value not given
#               resolves to "" exactly as it does for an event that lacks it.
#   --needs-output (CLI, repeatable, "JOB.NAME=VALUE"): DECLARE the output of
#               a job the selected job `needs`, instead of computing it.
# OUTPUTS:
#   stdout: a live stream of each executed step's real output, then a final
#     per-step summary table (ran-pass / ran-fail / skipped + reason), and an
#     unmissable "THIS IS NOT A CI RUN" banner before and after execution.
# EXIT CODES: 0 all executed steps passed (>=1 step executed) -> local PASS;
#   1 at least one executed step failed -> local FAIL;
#   2 usage/parse error (workflow/job not found, PyYAML missing, bad --input,
#     no bash on PATH, an `if:` or `${{ }}` this script cannot evaluate, a
#     matrix that resolves to no leg) -> BLOCKED;
#   3 nothing was actually executed (every step skipped/filtered out, or the
#     job-level `if:` was false) -> NO SIGNAL. This is deliberately distinct
#     from exit 0: a run that skipped everything and exited 0 would be the
#     quietest, most dangerous failure mode of all -- a green result that
#     checked nothing.
# PRECONDITIONS: run from (or given --workflow pointing at) a checkout of this
#   repository; the workflow file must parse as YAML with a top-level `jobs:`
#   mapping.
# DETERMINISM NOTE: NOT deterministic in the way the other P11 gates are --
#   it depends on the local OS, the local toolchain versions on PATH, network
#   access (pip installs), and wall-clock timing. That is inherent to what it
#   is: a local approximation of a hosted run, not a repeatable pure
#   computation. See the SUPERVISION RULE below and ADR-0045.
#
# CRITICAL DESIGN CONSTRAINT (ADR-0045): this script contains NO hand-written
# list of pytest/flake8/mypy/coverage/etc invocations anywhere. It parses
# ci.yml with PyYAML and runs the selected job's `run:` steps VERBATIM, in
# file order, so the workflow stays the single source of truth. A step that
# uses a marketplace/setup action (`uses:`) cannot be executed this way --
# each such step is mapped to an honest local equivalent where one exists, or
# SKIPPED with a stated, printed reason. Silent skipping is the failure mode
# this script is designed against: every skip appears in the final summary.
#
# WHAT IT READS FROM THE WORKFLOW, AND HOW CLOSELY IT FOLLOWS GITHUB:
#   * Step status. A step with no status function in its `if:` runs only while
#     no earlier step has failed (GitHub's implicit `success() &&`); a step
#     whose `if:` names success(), failure(), always() or cancelled() is
#     evaluated as written, so `always()` runs after a failure and a step
#     guarded by `steps.<id>.outcome` sees the real outcome of that step. A
#     failed step does NOT stop the run: the steps that are allowed to run
#     after it do, and the exit code is 1 whenever any step failed.
#   * Matrix. A literal `matrix.os` list is used as written. A
#     `${{ fromJSON(needs.<job>.outputs.<name>) }}` matrix is resolved from the
#     needed job's OWN computation (its `run:` steps are executed here, the
#     files `GITHUB_OUTPUT`/`GITHUB_ENV` are honoured), or, under --dry-run
#     (which executes nothing), from a DECLARED LOCAL DEFAULT that is printed
#     as such. --needs-output overrides both. A matrix that resolves to no
#     leg stops the run with exit 2; it never silently runs nothing.
#   * `${{ }}` inside a `run:` block is substituted before the block runs.
#   * `&&` and `||` return a value, as in GitHub (`a && '1' || ''` is '1' or
#     ''), and a boolean prints as true/false.
#   * Blocks run as `bash --noprofile --norc -eo pipefail <file>`, GitHub's own
#     invocation for `shell: bash`: a failing command in the middle of a block
#     fails the step, as it does on a hosted runner.
#   * RUNNER_TEMP, GITHUB_ENV and GITHUB_OUTPUT exist: a fresh folder under
#     the declared temp root (ORCH_TEST_TMP when set), removed when the run
#     ends. Only that folder is ever deleted by this script.
#
# SUPERVISION RULE (normative, ADR-0045): a local run of this script is
# EVIDENCE OF A DIFFERENT AND WEAKER KIND than a GitHub Actions CI run -- same
# commands, a different environment, incomplete step coverage (every `uses:`
# step approximated or skipped; only the OS-gated steps matching THIS machine
# run at all), a single OS leg, no concurrency guard, no durable third-party
# record. A local pass must NEVER be reported, recorded, or cited as "CI
# passed" -- say "local run passed" and name the job + OS leg. This script
# prints that rule, unmissably, before and after every run; it does not rely
# on the caller remembering it.
#
# ## Principles Applied
# Inherited: P1 (no invented action semantics -- unmapped `uses:` steps are
#   skipped, never faked), P6, P9 (one job: derive-and-run ci.yml locally),
#   P10 (exit code -> status, with a THIRD code for "nothing ran" so a
#   contentless pass cannot be mistaken for a real one), P11.
# Custom: parses its own single source of truth (the workflow file) instead
#   of hand-maintaining a parallel command list (ADR-0045's central ruling).
#
# SOURCES: ADR-0045 (this decision, with the verified GitHub Actions billing
#   block and the verified absence of Docker/WSL2 on this machine);
#   .github/workflows/ci.yml (the parsed source of truth); asset-templates.md
#   Script template; GitHub's documentation of status check functions
#   ("Evaluate expressions in workflows and actions"), of `shell: bash`
#   ("Workflow syntax", the shell table) and of the GITHUB_ENV / GITHUB_OUTPUT
#   command files ("Workflow commands").
# =============================================================================
from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

BANNER = (
    "=" * 78
    + "\n"
    + "  LOCAL CI EXECUTION -- THIS IS NOT A CI RUN\n"
    + "  Same commands, a different environment, incomplete step coverage,\n"
    + "  a single OS leg. Do NOT report, record, or cite a local pass as\n"
    + '  "CI passed" -- say "local run passed" and name the job + OS leg.\n'
    + "  See docs/adr/0045-local-ci-execution-strategy.md.\n"
    + "=" * 78
)

_RUNNER_OS_BY_LABEL = {
    "ubuntu-latest": "Linux",
    "windows-latest": "Windows",
    "macos-latest": "macOS",
}
_LABEL_BY_RUNNER_OS = {os_name: label for label, os_name in _RUNNER_OS_BY_LABEL.items()}
_LOCAL_RUNNER_OS = {"Linux": "Linux", "Windows": "Windows", "Darwin": "macOS"}.get(
    platform.system(), platform.system()
)
_RUNNER_OS_CHOICES = ("Linux", "Windows", "macOS")

#: GitHub's four status check functions. A step condition that names none of
#: them is implicitly wrapped in `success() &&`.
_STATUS_FUNCTIONS = ("success", "failure", "always", "cancelled")

#: The context namespaces `--context` may set.
_SETTABLE_NAMESPACES = ("github", "inputs", "env")


# --------------------------------------------------------------------------
# Minimal GitHub-Actions-expression evaluator.
#
# GitHub Actions' expression language is much larger than this; this
# implements only what .github/workflows/ci.yml's `if:` conditions, `env:`
# values, matrix and `run:` substitutions actually use (verified by reading
# the file): dotted context lookups (runner.os, matrix.os, env.X,
# github.event_name, github.ref, inputs.X, secrets.X, needs.J.outputs.N,
# steps.ID.outcome), string literals, ==, !=, &&, ||, !, parentheses, and the
# functions startsWith(), fromJSON(), success(), failure(), always() and
# cancelled(). Anything else raises rather than guessing.
# --------------------------------------------------------------------------
_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<STR>'[^']*')
      | (?P<ID>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_\-]*)*)
      | (?P<OP>==|!=|&&|\|\||!|\(|\)|,)
    )""",
    re.VERBOSE,
)


class ExprError(Exception):
    pass


class _SecretsNamespace(dict):
    """secrets.X resolves to the REAL local env var of the same name, or "" --
    exactly what an absent GitHub secret evaluates to. Never fabricated.

    Overrides both __missing__ (for `space[key]`) AND `get` (for
    `space.get(key, default)`, which plain dict.get() never routes through
    __missing__) because _Parser._lookup uses `.get()`.
    """

    def __missing__(self, key: str) -> str:
        return os.environ.get(key, "")

    def get(self, key: str, default: str = "") -> str:  # type: ignore[override]
        return dict.get(self, key, os.environ.get(key, default))


def _truthy(value: Any) -> bool:
    """GitHub's truthiness: false, 0, "" and null are falsy; an array or an
    object is always truthy, even when empty."""
    if isinstance(value, (list, dict)):
        return True
    return bool(value)


def _tokenize(expr: str) -> List[str]:
    tokens: List[str] = []
    pos = 0
    while pos < len(expr):
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            if expr[pos:].strip() == "":
                break
            raise ExprError(f"cannot tokenize expression at: {expr[pos:]!r}")
        pos = m.end()
        tok = m.group("STR") or m.group("ID") or m.group("OP")
        if tok is not None:
            tokens.append(tok)
    return tokens


class _Parser:
    def __init__(self, tokens: List[str], ctx: Dict[str, Any]):
        self.tokens = tokens
        self.i = 0
        self.ctx = ctx

    def _peek(self) -> Optional[str]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _advance(self) -> str:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def parse(self) -> Any:
        val = self._or_expr()
        if self.i != len(self.tokens):
            raise ExprError(f"unexpected trailing tokens: {self.tokens[self.i:]!r}")
        return val

    def _or_expr(self) -> Any:
        # GitHub's `||` returns its left operand when that is truthy and its
        # right operand otherwise -- a VALUE, not a boolean.
        val = self._and_expr()
        while self._peek() == "||":
            self._advance()
            rhs = self._and_expr()
            val = val if _truthy(val) else rhs
        return val

    def _and_expr(self) -> Any:
        # `&&` returns its left operand when that is falsy, else the right one.
        val = self._equality()
        while self._peek() == "&&":
            self._advance()
            rhs = self._equality()
            val = rhs if _truthy(val) else val
        return val

    def _equality(self) -> Any:
        val = self._unary()
        if self._peek() in ("==", "!="):
            op = self._advance()
            rhs = self._unary()
            eq = str(val) == str(rhs)
            val = eq if op == "==" else (not eq)
        return val

    def _unary(self) -> Any:
        if self._peek() == "!":
            self._advance()
            return not _truthy(self._unary())
        return self._primary()

    def _primary(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise ExprError("unexpected end of expression")
        if tok == "(":
            self._advance()
            val = self._or_expr()
            if self._peek() != ")":
                raise ExprError("expected ')'")
            self._advance()
            return val
        if tok.startswith("'"):
            self._advance()
            return tok[1:-1]
        # identifier: either a function call or a dotted context reference.
        self._advance()
        if self._peek() == "(":
            return self._call(tok)
        return self._lookup(tok)

    def _status_function(self, name: str) -> bool:
        status = self.ctx.get("_status") or {}
        failed = bool(status.get("failed"))
        cancelled = bool(status.get("cancelled"))
        if name == "always":
            return True
        if name == "cancelled":
            return cancelled
        if name == "failure":
            return failed
        return not failed and not cancelled  # success()

    def _call(self, fname: str) -> Any:
        self._advance()  # '('
        args = []
        if self._peek() != ")":
            args.append(self._or_expr())
            while self._peek() == ",":
                self._advance()
                args.append(self._or_expr())
        if self._peek() != ")":
            raise ExprError("expected ')' after call arguments")
        self._advance()
        # GitHub matches function names without regard to case.
        lowered = fname.lower()
        if lowered == "startswith":
            if len(args) != 2:
                raise ExprError("startsWith() takes exactly 2 arguments")
            return str(args[0]).lower().startswith(str(args[1]).lower())
        if lowered in _STATUS_FUNCTIONS:
            if args:
                raise ExprError(f"{fname}() takes no arguments")
            return self._status_function(lowered)
        if lowered == "fromjson":
            if len(args) != 1:
                raise ExprError("fromJSON() takes exactly 1 argument")
            try:
                return json.loads(str(args[0]))
            except ValueError as exc:
                raise ExprError(
                    f"fromJSON() was given text that is not JSON ({exc}): "
                    f"{str(args[0])!r}"
                ) from exc
        raise ExprError(f"unsupported function: {fname}()")

    def _lookup(self, dotted: str) -> Any:
        parts = dotted.split(".", 1)
        if len(parts) == 1:
            # Bare identifier: only 'true'/'false' are meaningful here.
            if dotted == "true":
                return True
            if dotted == "false":
                return False
            raise ExprError(f"unsupported bare identifier: {dotted!r}")
        namespace, key = parts
        space = self.ctx.get(namespace)
        if space is None:
            raise ExprError(f"unsupported context namespace: {namespace!r}")
        return space.get(key, "")


def eval_expr(expr: str, ctx: Dict[str, Any]) -> Any:
    """Evaluate one bare GitHub-Actions-style boolean/string expression."""
    return _Parser(_tokenize(expr), ctx).parse()


_WRAPPED_RE = re.compile(r"^\$\{\{\s*(.*?)\s*\}\}$", re.DOTALL)
_INLINE_RE = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")


def _unwrap(raw: Any) -> str:
    text = str(raw).strip()
    m = _WRAPPED_RE.match(text)
    return m.group(1) if m else text


def eval_condition(raw: Any, ctx: Dict[str, Any]) -> bool:
    """Evaluate an `if:` field, with or without the optional ${{ }} wrapper."""
    if raw is None:
        return True
    return _truthy(eval_expr(_unwrap(raw), ctx))


def has_status_function(expr: str) -> bool:
    """True when the expression calls success(), failure(), always() or
    cancelled() -- the test GitHub applies to decide whether an `if:` already
    says what happens after a failure."""
    tokens = _tokenize(expr)
    return any(
        tok.lower() in _STATUS_FUNCTIONS
        and index + 1 < len(tokens)
        and tokens[index + 1] == "("
        for index, tok in enumerate(tokens)
    )


def _job_is_healthy(ctx: Dict[str, Any]) -> bool:
    status = ctx.get("_status") or {}
    return not status.get("failed") and not status.get("cancelled")


def eval_step_condition(raw: Any, ctx: Dict[str, Any]) -> bool:
    """Decide whether a STEP runs, as GitHub does.

    A step with no `if:` has the implicit condition `success()`: it runs only
    while no earlier step of the job has failed. A step whose `if:` names a
    status check function is evaluated exactly as written. A step whose `if:`
    names none is evaluated as `success() && (<if>)`.
    """
    if raw is None:
        return _job_is_healthy(ctx)
    inner = _unwrap(raw)
    value = _truthy(eval_expr(inner, ctx))
    if has_status_function(inner):
        return value
    return _job_is_healthy(ctx) and value


def _render(value: Any) -> str:
    """How a value prints inside `${{ }}` text: true/false, "" for null, JSON
    for an array or object."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def resolve_string(raw: Any, ctx: Dict[str, Any]) -> str:
    """Resolve every ${{ ... }} occurrence in a string (env: values and run:
    blocks). A value with no ${{ }} is returned unchanged."""
    text = str(raw)

    def _sub(m: "re.Match[str]") -> str:
        return _render(eval_expr(m.group(1), ctx))

    return _INLINE_RE.sub(_sub, text)


# --------------------------------------------------------------------------
# Local equivalents for `uses:` steps that cannot be executed as-is.
# ADR-0045: every entry here is either a real, honest local check, or the
# step is skipped with a stated reason. Nothing here fabricates behaviour
# the real action would have provided.
# --------------------------------------------------------------------------
@dataclass
class StepResult:
    name: str
    status: str  # RAN-PASS | RAN-FAIL | SKIPPED | MAPPED | NOT-RUN
    detail: str
    seconds: float = 0.0


def _tool_version(exe: str) -> Optional[str]:
    path = shutil.which(exe)
    if not path:
        return None
    try:
        out = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=15
        )
        return (
            (out.stdout or out.stderr).strip().splitlines()[0]
            if (out.stdout or out.stderr)
            else None
        )
    except Exception as exc:  # defensive: a broken local tool must not crash the runner
        return f"(could not determine version: {exc!r})"


def _handle_checkout(step: Dict[str, Any]) -> StepResult:
    return StepResult(
        step.get("name", "actions/checkout"),
        "SKIPPED",
        "actions/checkout has no local equivalent needed -- this script already "
        f"runs against the local working tree at {REPO_ROOT}.",
    )


def _resolve_setup_python_pin(step: Dict[str, Any]) -> Tuple[str, str]:
    """Resolve the version an actions/setup-python step requests, LOCALLY.

    REMEDIATION (Python-version standardization, 2026-08-24): this used to read
    ONLY the `with.python-version` key, so once the workflow switched to pinning
    via `python-version-file: .python-version` this script would silently
    misreport the requested interpreter as "unspecified" -- a local CI runner
    lying about the very thing being standardized. It now resolves BOTH keys,
    mirroring actions/setup-python's own documented semantics: `python-version`
    (an inline pin) WINS when both are set, and the file is ignored in that case
    -- which is exactly why the workflow must never carry both at once. Returns
    (requested_version, how_it_was_resolved).
    """
    with_ = step.get("with", {})
    inline = with_.get("python-version")
    file_key = with_.get("python-version-file")

    if inline:
        if file_key:
            return (
                str(inline),
                f"python-version={inline!r} WINS over python-version-file="
                f"{file_key!r} (both were set on this step -- actions/setup-python "
                "ignores the file when an inline version is also given).",
            )
        return str(inline), f"from inline python-version={inline!r}"

    if file_key:
        file_path = Path(str(file_key))
        if not file_path.is_absolute():
            file_path = REPO_ROOT / file_path
        try:
            content = file_path.read_bytes().decode("utf-8").strip()
        except OSError as exc:
            return (
                "unspecified",
                f"python-version-file={file_key!r} could not be read locally "
                f"at {file_path} ({exc!r}).",
            )
        if not content:
            return (
                "unspecified",
                f"python-version-file={file_key!r} resolved to an empty file "
                f"at {file_path}.",
            )
        return (
            content,
            f"from python-version-file={file_key!r} -> {file_path} -> {content!r}",
        )

    return (
        "unspecified",
        "neither python-version nor python-version-file was set on this step.",
    )


def _handle_setup_python(step: Dict[str, Any]) -> StepResult:
    requested, source_note = _resolve_setup_python_pin(step)
    local = _tool_version(sys.executable) or "(python not resolvable)"
    match = requested != "unspecified" and requested in local
    note = (
        "MATCHES the pin" if match else "does NOT confirm the pin -- compare manually"
    )
    return StepResult(
        step.get("name", "actions/setup-python"),
        "MAPPED",
        "actions/setup-python cannot install an interpreter locally; local "
        f"equivalent executed: `{sys.executable} --version` -> {local!r} "
        f"(workflow requests python-version={requested!r} [{source_note}]; {note}).",
    )


def _handle_setup_node(step: Dict[str, Any]) -> StepResult:
    requested = str(step.get("with", {}).get("node-version", "unspecified"))
    node = shutil.which("node")
    if not node:
        return StepResult(
            step.get("name", "actions/setup-node"),
            "SKIPPED",
            "node not found on PATH locally; any later step needing node will "
            "likely fail here.",
        )
    local = _tool_version("node") or "(node not resolvable)"
    match = requested != "unspecified" and requested in local
    note = (
        "MATCHES the pin" if match else "does NOT confirm the pin -- compare manually"
    )
    return StepResult(
        step.get("name", "actions/setup-node"),
        "MAPPED",
        "actions/setup-node cannot install a Node version locally; local "
        f"equivalent executed: `node --version` -> {local!r} "
        f"(workflow pins node-version={requested!r}; {note}).",
    )


def _handle_upload_artifact(step: Dict[str, Any]) -> StepResult:
    with_ = step.get("with", {})
    path = with_.get("path", "?")
    name = with_.get("name", "?")
    return StepResult(
        step.get("name", "actions/upload-artifact"),
        "SKIPPED",
        f"actions/upload-artifact has no local equivalent; the produced file(s) "
        f"at {path!r} remain on disk locally for inspection (would be named "
        f"{name!r} as a CI artifact).",
    )


def _handle_unknown_action(step: Dict[str, Any], uses: str) -> StepResult:
    return StepResult(
        step.get("name", uses),
        "SKIPPED",
        f"{uses!r} is a marketplace/setup action with no local equivalent "
        "implemented by this script. SKIPPED -- extend the mapping table in "
        "run_ci_locally.py if this step needs to be approximated locally.",
    )


_ACTION_HANDLERS = {
    "actions/checkout": _handle_checkout,
    "actions/setup-python": _handle_setup_python,
    "actions/setup-node": _handle_setup_node,
    "actions/upload-artifact": _handle_upload_artifact,
}


# --------------------------------------------------------------------------
# Workflow loading + context construction.
# --------------------------------------------------------------------------
def _load_workflow(path: Path) -> Dict[str, Any]:
    try:
        # Local import: keeps the module importable for --help/--list-jobs
        # even if PyYAML is missing, so the error message below is reachable.
        # No stubs are declared for it here (mypy only gates `pixelart_creator`
        # in CI's "Type check" step, not scripts/ -- see ci.yml's `mypy
        # pixelart_creator` invocation).
        import yaml
    except ImportError:
        print(
            "run_ci_locally: PyYAML is required to parse the workflow "
            "(available transitively via the 'mkdocs' dev dependency: "
            "`pip install -e .[dev]`; or directly: `pip install pyyaml`).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if not path.is_file():
        print(f"run_ci_locally: workflow file not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    with path.open(encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict) or "jobs" not in doc:
        print(
            f"run_ci_locally: {path} does not parse as a workflow (no top-level "
            "'jobs:' mapping).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return doc


def _on_block(doc: Dict[str, Any]) -> Dict[str, Any]:
    # KNOWN PyYAML/YAML-1.1 GOTCHA (verified this session): the bare mapping
    # key `on:` is resolved by PyYAML's default loader as the BOOLEAN True,
    # not the string "on" -- because YAML 1.1 treats on/off/yes/no as booleans
    # even as mapping keys. `doc["on"]` therefore does not exist; the trigger
    # block lives under the key `True`. `cast` to a loosely-keyed mapping
    # view for this one lookup rather than widening every `doc`/`job` type
    # hint in the module just to accommodate this one YAML quirk.
    raw = cast(Dict[Any, Any], doc)
    return raw.get("on", raw.get(True, {})) or {}


def _fail_usage(message: str) -> "SystemExit":
    """Print a usage/parse error and return the exit-2 SystemExit to raise."""
    print(f"run_ci_locally: {message}", file=sys.stderr)
    return SystemExit(2)


def _parse_inputs(pairs: List[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            print(
                f"run_ci_locally: --input must be KEY=VALUE, got {pair!r}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        key, _, value = pair.partition("=")
        result[key] = value
    return result


def _parse_context(pairs: List[str]) -> Dict[str, Dict[str, str]]:
    """`--context NAMESPACE.KEY=VALUE` -> {NAMESPACE: {KEY: VALUE}}."""
    result: Dict[str, Dict[str, str]] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        namespace, dot, key = name.partition(".")
        if not sep or not dot or not key or namespace not in _SETTABLE_NAMESPACES:
            raise _fail_usage(
                f"--context must be NAMESPACE.KEY=VALUE with NAMESPACE one of "
                f"{', '.join(_SETTABLE_NAMESPACES)}, got {pair!r}"
            )
        result.setdefault(namespace, {})[key] = value
    return result


def _parse_needs_outputs(pairs: List[str]) -> Dict[str, str]:
    """`--needs-output JOB.NAME=VALUE` -> {"JOB.NAME": VALUE}."""
    result: Dict[str, str] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        job, dot, output = name.partition(".")
        if not sep or not dot or not job or not output:
            raise _fail_usage(f"--needs-output must be JOB.NAME=VALUE, got {pair!r}")
        result[name] = value
    return result


def _effective_runner_os(args: argparse.Namespace) -> str:
    return cast(str, args.runner_os or _LOCAL_RUNNER_OS)


def _build_base_context(
    doc: Dict[str, Any], args: argparse.Namespace
) -> Dict[str, Any]:
    inputs: Dict[str, str] = {}
    dispatch = _on_block(doc).get("workflow_dispatch") or {}
    for key, spec in (dispatch.get("inputs") or {}).items():
        if isinstance(spec, dict) and "default" in spec:
            inputs[key] = str(spec["default"])
    inputs.update(_parse_inputs(args.input))

    ctx: Dict[str, Any] = {
        "runner": {"os": _effective_runner_os(args)},
        "matrix": {},  # filled in per-job if the job declares a matrix
        "github": {"event_name": args.event, "ref": args.ref},
        "inputs": inputs,
        "secrets": _SecretsNamespace(),
        "env": {},  # filled in from the workflow's top-level env: below
        "steps": {},  # "<id>.outcome", "<id>.conclusion", "<id>.outputs.<name>"
        "needs": {},  # "<job>.outputs.<name>", filled in when a matrix needs it
        "_status": {"failed": False, "cancelled": False},
    }
    for namespace, items in _parse_context(args.context).items():
        ctx[namespace].update(items)
    return ctx


@contextlib.contextmanager
def _runner_temp() -> Iterator[Path]:
    """The run's RUNNER_TEMP: a fresh short-named folder under the declared
    project temp root (ORCH_TEST_TMP) or the system temp, removed when the run
    ends. It is the one folder this script ever deletes."""
    base = os.environ.get("ORCH_TEST_TMP") or None
    if base:
        os.makedirs(base, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="rcl-", dir=base)).resolve()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _base_env(ctx: Dict[str, Any], temp_dir: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env.update(ctx["env"])
    env["RUNNER_TEMP"] = temp_dir.as_posix()
    env["RUNNER_OS"] = str(ctx["runner"]["os"])
    env["GITHUB_WORKSPACE"] = str(REPO_ROOT)
    return env


def _select_matrix_os(os_list: List[str], runner_os: str) -> str:
    for label in os_list:
        if _RUNNER_OS_BY_LABEL.get(label) == runner_os:
            return label
    if runner_os == _LOCAL_RUNNER_OS:
        where = f"this machine's OS ({_LOCAL_RUNNER_OS})"
    else:
        where = f"the simulated runner OS ({runner_os})"
    raise SystemExit(
        f"run_ci_locally: job's matrix.os {os_list!r} has no leg matching "
        f"{where}; nothing to run here."
    )


def _merge_env(
    existing: Dict[str, str], block: Optional[Dict[str, Any]], ctx: Dict[str, Any]
) -> None:
    for key, value in (block or {}).items():
        ctx["env"][key] = resolve_string(value, ctx)
    existing.update(ctx["env"])


# --------------------------------------------------------------------------
# Execution.
# --------------------------------------------------------------------------
def _find_bash() -> Optional[str]:
    return shutil.which("bash")


def _spawn(cmd: List[str], env: Dict[str, str]) -> int:
    """Run one command in the repository root and return its exit code. The
    single seam between this script's logic and a real process."""
    return subprocess.run(cmd, cwd=str(REPO_ROOT), env=env).returncode


def _parse_command_file(text: str) -> Dict[str, str]:
    """Read a GITHUB_ENV / GITHUB_OUTPUT file: `name=value` lines and
    `name<<DELIMITER` ... `DELIMITER` blocks."""
    result: Dict[str, str] = {}
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        block = re.match(r"^([^=<]+)<<(.+)$", line)
        if block:
            name, delimiter = block.groups()
            body: List[str] = []
            while index < len(lines) and lines[index] != delimiter:
                body.append(lines[index])
                index += 1
            index += 1
            result[name] = "\n".join(body)
        elif "=" in line:
            name, _, value = line.partition("=")
            result[name] = value
    return result


def _run_step(
    name: str,
    script: str,
    env: Dict[str, str],
    shell: str,
    dry_run: bool,
    work_dir: Path,
    index: int,
) -> Tuple[StepResult, Dict[str, str], Dict[str, str]]:
    """Run one `run:` block (already substituted). Returns the result, the
    environment the block exported through GITHUB_ENV and the outputs it wrote
    through GITHUB_OUTPUT."""
    if "bash" not in shell:
        print(
            f"  [run_ci_locally] NOTE: step declares shell={shell!r}; this "
            "script only knows how to invoke bash. Running it under bash "
            "anyway -- if the block uses shell-specific syntax this may not "
            "behave as it would in CI.",
        )
    bash = _find_bash()
    if not bash:
        print(
            "run_ci_locally: no 'bash' found on PATH; cannot execute run: "
            "blocks (this workflow's jobs set `defaults: run: shell: bash`).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if dry_run:
        result = StepResult(
            name, "NOT-RUN", "--dry-run: parsed and would execute via bash."
        )
        return result, {}, {}

    script_file = work_dir / f"step{index}.sh"
    env_file = work_dir / f"step{index}.env"
    out_file = work_dir / f"step{index}.out"
    # The block as written, ending in one newline (a `|` block already does).
    script_file.write_bytes(
        script.encode("utf-8") + (b"" if script.endswith("\n") else b"\n")
    )
    env_file.write_bytes(b"")
    out_file.write_bytes(b"")
    step_env = dict(env)
    step_env["GITHUB_ENV"] = env_file.as_posix()
    step_env["GITHUB_OUTPUT"] = out_file.as_posix()

    print(f"\n----- RUN: {name} " + "-" * max(0, 40 - len(name)))
    start = time.monotonic()
    # GitHub's own invocation for `shell: bash`.
    code = _spawn(
        [bash, "--noprofile", "--norc", "-eo", "pipefail", script_file.as_posix()],
        step_env,
    )
    elapsed = time.monotonic() - start
    exported = _parse_command_file(env_file.read_bytes().decode("utf-8", "replace"))
    written = _parse_command_file(out_file.read_bytes().decode("utf-8", "replace"))
    if code == 0:
        result = StepResult(name, "RAN-PASS", f"exit 0 in {elapsed:.1f}s", elapsed)
    else:
        result = StepResult(name, "RAN-FAIL", f"exit {code} in {elapsed:.1f}s", elapsed)
    return result, exported, written


def _step_name(step: Dict[str, Any]) -> str:
    return cast(str, step.get("name", step.get("uses", step.get("run", "<step>"))[:60]))


def _expression_failure(where: str, exc: ExprError) -> "SystemExit":
    return _fail_usage(f"{where}: cannot evaluate an expression: {exc}")


def _execute_run_step(
    step: Dict[str, Any],
    ctx: Dict[str, Any],
    base_env: Dict[str, str],
    shell: str,
    dry_run: bool,
    work_dir: Path,
    index: int,
) -> StepResult:
    """Substitute `${{ }}` in a step's env and script, run it, and carry what
    it exported (GITHUB_ENV) and wrote (GITHUB_OUTPUT) into the job."""
    name = _step_name(step)
    step_ctx = dict(ctx)
    step_ctx["env"] = dict(ctx["env"])
    step_env = dict(base_env)
    try:
        if step.get("env"):
            _merge_env(step_env, step["env"], step_ctx)
        script = resolve_string(step["run"], step_ctx)
    except ExprError as exc:
        raise _expression_failure(f"step {name!r}", exc)
    result, exported, written = _run_step(
        name, script, step_env, shell, dry_run, work_dir, index
    )
    base_env.update(exported)
    ctx["env"].update(exported)
    if step.get("id"):
        for key, value in written.items():
            ctx["steps"][f"{step['id']}.outputs.{key}"] = value
    return result


def _record_outcome(ctx: Dict[str, Any], step: Dict[str, Any], outcome: str) -> None:
    """Make `steps.<id>.outcome` / `.conclusion` readable by later conditions."""
    if step.get("id"):
        ctx["steps"][f"{step['id']}.outcome"] = outcome
        ctx["steps"][f"{step['id']}.conclusion"] = outcome


def _filtered_out(name: str, only: List[str], skip: List[str]) -> Optional[str]:
    lname = name.lower()
    if only and not any(s.lower() in lname for s in only):
        return f"excluded: does not match any --only filter {only!r}"
    for s in skip:
        if s.lower() in lname:
            return f"excluded by --skip filter {s!r}"
    return None


# --------------------------------------------------------------------------
# `matrix.os` resolution, including a matrix computed by a needed job.
# --------------------------------------------------------------------------
_NEEDS_REF_RE = re.compile(
    r"\bneeds\.([A-Za-z_][A-Za-z0-9_\-]*)\.outputs\.([A-Za-z_][A-Za-z0-9_\-]*)"
)


def _compute_job_outputs(
    doc: Dict[str, Any],
    job_name: str,
    ctx: Dict[str, Any],
    args: argparse.Namespace,
    temp_dir: Path,
) -> Dict[str, str]:
    """Compute a needed job's outputs by running its own `run:` steps here.

    Only `run:` steps run (a `uses:` action has no local equivalent and no
    output this script could read). The needed job's steps are not part of the
    selected job's summary and never count as executed steps of it.
    """
    cache = ctx.setdefault("_needs_cache", {})
    if job_name in cache:
        return cast(Dict[str, str], cache[job_name])
    needed = doc["jobs"].get(job_name)
    if needed is None:
        raise _fail_usage(
            f"the matrix needs job {job_name!r}, which the workflow does not "
            f"define. Known jobs: {sorted(doc['jobs'])}."
        )
    print(
        f"[run_ci_locally] computing the outputs of job {job_name!r} by running "
        "its own run: steps here (the matrix is computed from them)."
    )
    sub = dict(ctx)
    sub["env"] = dict(ctx["env"])
    sub["steps"] = {}
    sub["_status"] = {"failed": False, "cancelled": False}
    needed_env = _base_env(sub, temp_dir)
    work_dir = temp_dir / f"needs-{job_name}"
    work_dir.mkdir(exist_ok=True)
    shell = ((needed.get("defaults") or {}).get("run") or {}).get("shell", "bash")
    for index, step in enumerate(needed.get("steps", [])):
        if "run" not in step:
            continue
        try:
            runs = eval_step_condition(step.get("if"), sub)
        except ExprError as exc:
            raise _expression_failure(
                f"job {job_name!r}, step {_step_name(step)!r}", exc
            )
        if not runs:
            continue
        result = _execute_run_step(
            step, sub, needed_env, shell, args.dry_run, work_dir, index
        )
        _record_outcome(
            sub, step, "success" if result.status == "RAN-PASS" else "failure"
        )
        if result.status == "RAN-FAIL":
            raise _fail_usage(
                f"job {job_name!r} failed while computing its outputs "
                f"({result.name!r}: {result.detail}); the matrix cannot be resolved."
            )
    outputs: Dict[str, str] = {}
    try:
        for name, expr in (needed.get("outputs") or {}).items():
            outputs[name] = resolve_string(expr, sub)
    except ExprError as exc:
        raise _expression_failure(f"job {job_name!r} outputs", exc)
    cache[job_name] = outputs
    return outputs


def _needs_output(
    doc: Dict[str, Any],
    job_name: str,
    output: str,
    ctx: Dict[str, Any],
    args: argparse.Namespace,
    temp_dir: Path,
) -> Tuple[str, str]:
    """The value of needs.<job>.outputs.<output> and how it was obtained."""
    declared = _parse_needs_outputs(args.needs_output)
    key = f"{job_name}.{output}"
    if key in declared:
        return declared[key], "declared with --needs-output"
    if not args.dry_run:
        outputs = _compute_job_outputs(doc, job_name, ctx, args, temp_dir)
        if output not in outputs:
            raise _fail_usage(
                f"job {job_name!r} ran but defines no output named {output!r} "
                f"(it defines {sorted(outputs)}); the matrix cannot be resolved."
            )
        return outputs[output], f"computed by running job {job_name!r} here"
    label = _LABEL_BY_RUNNER_OS.get(_effective_runner_os(args), "")
    return (
        json.dumps([label] if label else []),
        f"DECLARED LOCAL DEFAULT, not the workflow's computation: --dry-run runs "
        f"no `run:` block, so job {job_name!r} was not run; the default is the "
        "leg of the runner OS alone (run without --dry-run, or declare the "
        "output with --needs-output, to see the workflow's own list)",
    )


def _resolve_matrix_os_list(
    doc: Dict[str, Any],
    job: Dict[str, Any],
    ctx: Dict[str, Any],
    args: argparse.Namespace,
    temp_dir: Path,
) -> Tuple[Optional[List[str]], str]:
    """The legs of the job's `matrix.os` and where the list came from; (None,
    "") for a job with no `matrix.os`. A matrix that resolves to no leg is a
    usage error (exit 2), never an empty run."""
    raw = ((job.get("strategy") or {}).get("matrix") or {}).get("os")
    if not raw:
        return None, ""
    if isinstance(raw, list):
        return [str(label) for label in raw], "a literal list in the workflow"
    text = str(raw).strip()
    wrapped = _WRAPPED_RE.match(text)
    if not wrapped:
        return [text], "a single literal label in the workflow"
    expr = wrapped.group(1)
    sources: List[str] = []
    for need_job, output in _NEEDS_REF_RE.findall(expr):
        value, how = _needs_output(doc, need_job, output, ctx, args, temp_dir)
        ctx["needs"][f"{need_job}.outputs.{output}"] = value
        sources.append(f"needs.{need_job}.outputs.{output} = {value} ({how})")
    try:
        resolved = eval_expr(expr, ctx)
    except ExprError as exc:
        raise _expression_failure(f"matrix.os {text!r}", exc)
    if isinstance(resolved, str):
        resolved = [resolved] if resolved else []
    if not isinstance(resolved, list) or not resolved:
        raise _fail_usage(
            f"matrix.os {text!r} resolved to no leg ({resolved!r}); refusing to "
            "run a job with nothing to run. " + "; ".join(sources)
        )
    return [str(label) for label in resolved], "; ".join(sources) or text


def run_job(
    doc: Dict[str, Any], job_name: str, args: argparse.Namespace
) -> List[StepResult]:
    jobs = doc["jobs"]
    if job_name not in jobs:
        print(
            f"run_ci_locally: no job named {job_name!r} in the workflow. "
            f"Known jobs: {sorted(jobs)}. Use --list-jobs for details.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    with _runner_temp() as temp_dir:
        return _run_job(doc, job_name, args, temp_dir)


def _run_job(
    doc: Dict[str, Any], job_name: str, args: argparse.Namespace, temp_dir: Path
) -> List[StepResult]:
    job = doc["jobs"][job_name]
    runner_os = _effective_runner_os(args)

    ctx = _build_base_context(doc, args)
    ctx["runner"]["temp"] = temp_dir.as_posix()
    _merge_env({}, doc.get("env"), ctx)  # top-level env, resolved into ctx["env"]
    if runner_os != _LOCAL_RUNNER_OS:
        print(
            f"[run_ci_locally] SIMULATED runner OS: {runner_os} (this machine is "
            f"{_LOCAL_RUNNER_OS}). `runner.os` and the matrix leg follow the "
            "simulation; every command still runs here."
        )

    os_list, source = _resolve_matrix_os_list(doc, job, ctx, args, temp_dir)
    # NOTE: matrix.os must be resolved into ctx BEFORE the job-level env: block
    # is merged below, because that block (e.g. build-installers' credential
    # env) may itself reference ${{ matrix.os }} or other matrix-derived
    # values in a future workflow edit.
    matrix_os = None
    if os_list is not None:
        print(
            f"[run_ci_locally] matrix legs of job {job_name!r}: {os_list!r} "
            f"(from {source})"
        )
        matrix_os = _select_matrix_os(os_list, runner_os)
    if matrix_os:
        ctx["matrix"]["os"] = matrix_os
        which = "local OS" if runner_os == _LOCAL_RUNNER_OS else "simulated OS"
        print(f"[run_ci_locally] matrix leg selected: os={matrix_os} ({which})")

    # Job-level env: (e.g. build-installers' credential-gated APPLE_* vars,
    # each `${{ secrets.X }}` -- resolved via _SecretsNamespace to the real
    # local env var of the same name, or "" if unset, same as an absent
    # GitHub secret) merged in BEFORE the job-level `if:` is evaluated, since
    # a future workflow edit could make that condition reference env.*.
    _merge_env({}, job.get("env"), ctx)

    runs_on = job.get("runs-on")
    if isinstance(runs_on, str) and runs_on in _RUNNER_OS_BY_LABEL:
        pinned_os = _RUNNER_OS_BY_LABEL[runs_on]
        if pinned_os != _LOCAL_RUNNER_OS:
            print(
                f"[run_ci_locally] WARNING: job {job_name!r} is pinned to "
                f"`runs-on: {runs_on}` ({pinned_os}) in the workflow; this "
                f"machine is {_LOCAL_RUNNER_OS}. Steps assuming {pinned_os} "
                "tooling (apt/sudo/etc) will likely fail here -- that is "
                "fidelity to a real gap, not a bug in this script."
            )

    if "if" in job and not eval_condition(job["if"], ctx):
        print(
            f"[run_ci_locally] job {job_name!r} SKIPPED entirely: job-level "
            f"`if:` evaluated false under this simulated context "
            f"(event={args.event!r}, ref={args.ref!r}, inputs={ctx['inputs']!r})."
        )
        return []

    base_env = _base_env(ctx, temp_dir)
    print(f"[run_ci_locally] RUNNER_TEMP for this run: {temp_dir.as_posix()}")

    results: List[StepResult] = []
    default_shell = ((job.get("defaults") or {}).get("run") or {}).get("shell", "bash")
    work_dir = temp_dir / f"job-{job_name}"
    work_dir.mkdir(exist_ok=True)

    for index, step in enumerate(job.get("steps", [])):
        name = _step_name(step)

        reason = _filtered_out(name, args.only, args.skip)
        if reason:
            results.append(StepResult(name, "SKIPPED", reason))
            _record_outcome(ctx, step, "skipped")
            continue

        try:
            runs = eval_step_condition(step.get("if"), ctx)
            if not runs and not _job_is_healthy(ctx):
                # Would it have run had nothing failed? Then the failure, not
                # the condition, is why it did not.
                healthy_ctx = dict(ctx)
                healthy_ctx["_status"] = {"failed": False, "cancelled": False}
                stopped_by_failure = eval_step_condition(step.get("if"), healthy_ctx)
            else:
                stopped_by_failure = False
        except ExprError as exc:
            raise _expression_failure(f"step {name!r} `if:`", exc)
        if not runs:
            if stopped_by_failure:
                results.append(
                    StepResult(
                        name,
                        "NOT-RUN",
                        "upstream step failed; this step's condition has no "
                        "always()/failure() so success() is implied and false",
                    )
                )
            else:
                results.append(
                    StepResult(name, "SKIPPED", f"if: {step['if']!r} evaluated false")
                )
            _record_outcome(ctx, step, "skipped")
            continue

        if "uses" in step:
            action = step["uses"].split("@", 1)[0]
            handler = _ACTION_HANDLERS.get(action)
            result = (
                handler(step) if handler else _handle_unknown_action(step, step["uses"])
            )
            results.append(result)
            _record_outcome(
                ctx, step, "skipped" if result.status == "SKIPPED" else "success"
            )
            continue

        if "run" not in step:
            results.append(
                StepResult(name, "SKIPPED", "no run: or uses: -- nothing to execute")
            )
            _record_outcome(ctx, step, "skipped")
            continue

        shell = step.get("shell", default_shell)
        result = _execute_run_step(
            step, ctx, base_env, shell, args.dry_run, work_dir, index
        )
        results.append(result)
        if result.status == "RAN-FAIL":
            # The job is now failed: later steps run only if their own `if:`
            # says so (always(), failure(), a status-aware condition). The run
            # does not stop here -- GitHub does not.
            ctx["_status"]["failed"] = True
            _record_outcome(ctx, step, "failure")
        else:
            _record_outcome(ctx, step, "success")

    return results


def list_jobs(doc: Dict[str, Any]) -> None:
    print(f"Jobs in {DEFAULT_WORKFLOW.name}:")
    for name, job in doc["jobs"].items():
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        n_steps = len(job.get("steps", []))
        n_run = sum(1 for s in job.get("steps", []) if "run" in s)
        n_uses = sum(1 for s in job.get("steps", []) if "uses" in s)
        cond = " (job-level if:)" if "if" in job else ""
        mx = f" matrix.os={matrix['os']}" if matrix.get("os") else ""
        print(f"  {name!r}: {n_steps} steps ({n_run} run:, {n_uses} uses:){mx}{cond}")


def print_summary(
    job_name: str, results: List[StepResult], runner_os: Optional[str] = None
) -> int:
    print("\n" + "-" * 78)
    simulated = (
        f" (SIMULATED runner OS {runner_os})"
        if runner_os and runner_os != _LOCAL_RUNNER_OS
        else ""
    )
    print(f"LOCAL RUN SUMMARY -- job={job_name!r} os={_LOCAL_RUNNER_OS}{simulated}")
    print("-" * 78)
    width = max((len(r.name) for r in results), default=10)
    for r in results:
        print(f"  [{r.status:9s}] {r.name:<{width}}  {r.detail}")

    ran = [r for r in results if r.status in ("RAN-PASS", "RAN-FAIL")]
    failed = [r for r in results if r.status == "RAN-FAIL"]
    skipped = [r for r in results if r.status in ("SKIPPED", "NOT-RUN")]
    mapped = [r for r in results if r.status == "MAPPED"]

    print("-" * 78)
    print(
        f"  executed: {len(ran)}  passed: {len(ran) - len(failed)}  "
        f"failed: {len(failed)}  skipped/not-run: {len(skipped)}  "
        f"mapped-local-equivalent: {len(mapped)}"
    )
    print(BANNER)

    if failed:
        return 1
    if not ran:
        print(
            "\n[run_ci_locally] NOTHING EXECUTED: every step was skipped, "
            "filtered out, or gated false for this OS/context. This is NOT a "
            "pass -- it is no signal at all. See the per-step reasons above."
        )
        return 3
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=(
            "Run .github/workflows/ci.yml locally by parsing it and executing "
            "the selected job's run: blocks in order (ADR-0045). NOT a "
            "substitute for GitHub Actions CI -- see the banner this prints."
        )
    )
    ap.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    ap.add_argument("--job", default="quality-gate")
    ap.add_argument("--list-jobs", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--event", default="push", help="simulated github.event_name")
    ap.add_argument("--ref", default="", help="simulated github.ref")
    ap.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="simulated workflow_dispatch input (repeatable)",
    )
    ap.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="SUBSTRING",
        help="run only steps whose name contains SUBSTRING (repeatable)",
    )
    ap.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="SUBSTRING",
        help="skip steps whose name contains SUBSTRING (repeatable)",
    )
    ap.add_argument(
        "--runner-os",
        choices=_RUNNER_OS_CHOICES,
        default=None,
        help=(
            "simulate the runner's OS for runner.os and the matrix leg; "
            "commands still run on this machine"
        ),
    )
    ap.add_argument(
        "--context",
        action="append",
        default=[],
        metavar="NAMESPACE.KEY=VALUE",
        help="set one value of the github, inputs or env context (repeatable)",
    )
    ap.add_argument(
        "--needs-output",
        action="append",
        default=[],
        metavar="JOB.NAME=VALUE",
        help="declare a needed job's output instead of computing it (repeatable)",
    )
    return ap


def main() -> int:
    args = build_parser().parse_args()

    print(BANNER)
    doc = _load_workflow(args.workflow)

    if args.list_jobs:
        list_jobs(doc)
        return 0

    print(
        f"[run_ci_locally] workflow={args.workflow}  job={args.job!r}  "
        f"local OS={_LOCAL_RUNNER_OS}  dry_run={args.dry_run}"
    )
    results = run_job(doc, args.job, args)
    return print_summary(args.job, results, args.runner_os)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nrun_ci_locally: interrupted.", file=sys.stderr)
        sys.exit(130)
