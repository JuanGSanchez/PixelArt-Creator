#!/usr/bin/env python
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
# INVOKED BY: AGT-09 GitHub/DevOps; any developer wanting a local CI-shaped run.
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
# OUTPUTS:
#   stdout: a live stream of each executed step's real output, then a final
#     per-step summary table (ran-pass / ran-fail / skipped + reason), and an
#     unmissable "THIS IS NOT A CI RUN" banner before and after execution.
# EXIT CODES: 0 all executed steps passed (>=1 step executed) -> local PASS;
#   1 at least one executed step failed -> local FAIL;
#   2 usage/parse error (workflow/job not found, PyYAML missing, bad --input,
#     no bash on PATH) -> BLOCKED;
#   3 nothing was actually executed (every step skipped/filtered out, or the
#     job-level `if:` was false) -> NO SIGNAL. This is deliberately distinct
#     from exit 0: a run that skipped everything and exited 0 would be the
#     quietest, most dangerous failure mode of all -- a green result that
#     checked nothing.
# PRECONDITIONS: run from (or given --workflow/--repo-root pointing at) a
#   checkout of this repository; the workflow file must parse as YAML with a
#   top-level `jobs:` mapping.
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
#   Script template.
# =============================================================================
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

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
_LOCAL_RUNNER_OS = {"Linux": "Linux", "Windows": "Windows", "Darwin": "macOS"}.get(
    platform.system(), platform.system()
)


# --------------------------------------------------------------------------
# Minimal GitHub-Actions-expression evaluator.
#
# GitHub Actions' expression language is much larger than this; this
# implements only what .github/workflows/ci.yml's `if:` conditions and
# `env:` values actually use (verified by reading the file): dotted context
# lookups (runner.os, matrix.os, env.X, github.event_name, github.ref,
# inputs.X, secrets.X), string literals, ==, !=, &&, ||, !, parentheses, and
# the startsWith() function. Anything else raises rather than guessing.
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
        val = self._and_expr()
        while self._peek() == "||":
            self._advance()
            rhs = self._and_expr()
            val = bool(val) or bool(rhs)
        return val

    def _and_expr(self) -> Any:
        val = self._equality()
        while self._peek() == "&&":
            self._advance()
            rhs = self._equality()
            val = bool(val) and bool(rhs)
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
            return not bool(self._unary())
        return self._primary()

    def _primary(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise ExprError("unexpected end of expression")
        if tok == "(":
            self._advance()
            val = self._or_expr()
            if self._advance() != ")":
                raise ExprError("expected ')'")
            return val
        if tok.startswith("'"):
            self._advance()
            return tok[1:-1]
        # identifier: either a function call or a dotted context reference.
        self._advance()
        if self._peek() == "(":
            return self._call(tok)
        return self._lookup(tok)

    def _call(self, fname: str) -> Any:
        self._advance()  # '('
        args = []
        if self._peek() != ")":
            args.append(self._or_expr())
            while self._peek() == ",":
                self._advance()
                args.append(self._or_expr())
        if self._advance() != ")":
            raise ExprError("expected ')' after call arguments")
        if fname == "startsWith":
            if len(args) != 2:
                raise ExprError("startsWith() takes exactly 2 arguments")
            return str(args[0]).startswith(str(args[1]))
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


def eval_condition(raw: Any, ctx: Dict[str, Any]) -> bool:
    """Evaluate an `if:` field, with or without the optional ${{ }} wrapper."""
    if raw is None:
        return True
    text = str(raw).strip()
    m = _WRAPPED_RE.match(text)
    inner = m.group(1) if m else text
    return bool(eval_expr(inner, ctx))


def resolve_string(raw: Any, ctx: Dict[str, Any]) -> str:
    """Resolve every ${{ ... }} occurrence in a string (used for env: values).
    A value with no ${{ }} is returned unchanged."""
    text = str(raw)

    def _sub(m: "re.Match[str]") -> str:
        return str(eval_expr(m.group(1), ctx))

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


def _handle_setup_python(step: Dict[str, Any]) -> StepResult:
    requested = str(step.get("with", {}).get("python-version", "unspecified"))
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
        f"(workflow pins python-version={requested!r}; {note}).",
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
        import yaml  # type: ignore[import-untyped]
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


def _build_base_context(
    doc: Dict[str, Any], args: argparse.Namespace
) -> Dict[str, Any]:
    inputs: Dict[str, str] = {}
    dispatch = _on_block(doc).get("workflow_dispatch") or {}
    for key, spec in (dispatch.get("inputs") or {}).items():
        if isinstance(spec, dict) and "default" in spec:
            inputs[key] = str(spec["default"])
    inputs.update(_parse_inputs(args.input))

    return {
        "runner": {"os": _LOCAL_RUNNER_OS},
        "matrix": {},  # filled in per-job if the job declares a matrix
        "github": {"event_name": args.event, "ref": args.ref},
        "inputs": inputs,
        "secrets": _SecretsNamespace(),
        "env": {},  # filled in from the workflow's top-level env: below
    }


def _select_matrix_os(job: Dict[str, Any]) -> Optional[str]:
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    os_list = matrix.get("os")
    if not os_list:
        return None
    for label in os_list:
        if _RUNNER_OS_BY_LABEL.get(label) == _LOCAL_RUNNER_OS:
            return label
    raise SystemExit(
        f"run_ci_locally: job's matrix.os {os_list!r} has no leg matching this "
        f"machine's OS ({_LOCAL_RUNNER_OS}); nothing to run here."
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
def _run_step(
    step: Dict[str, Any], env: Dict[str, str], shell: str, dry_run: bool
) -> StepResult:
    name = step.get("name", "<unnamed step>")
    script = step["run"]
    if "bash" not in shell:
        print(
            f"  [run_ci_locally] NOTE: step declares shell={shell!r}; this "
            "script only knows how to invoke bash. Running it under bash "
            "anyway -- if the block uses shell-specific syntax this may not "
            "behave as it would in CI.",
        )
    bash = shutil.which("bash")
    if not bash:
        print(
            "run_ci_locally: no 'bash' found on PATH; cannot execute run: "
            "blocks (this workflow's jobs set `defaults: run: shell: bash`).",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if dry_run:
        return StepResult(
            name, "NOT-RUN", "--dry-run: parsed and would execute via bash."
        )

    print(f"\n----- RUN: {name} " + "-" * max(0, 40 - len(name)))
    start = time.monotonic()
    proc = subprocess.run([bash, "-c", script], cwd=str(REPO_ROOT), env=env)
    elapsed = time.monotonic() - start
    if proc.returncode == 0:
        return StepResult(name, "RAN-PASS", f"exit 0 in {elapsed:.1f}s", elapsed)
    return StepResult(
        name, "RAN-FAIL", f"exit {proc.returncode} in {elapsed:.1f}s", elapsed
    )


def _filtered_out(name: str, only: List[str], skip: List[str]) -> Optional[str]:
    lname = name.lower()
    if only and not any(s.lower() in lname for s in only):
        return f"excluded: does not match any --only filter {only!r}"
    for s in skip:
        if s.lower() in lname:
            return f"excluded by --skip filter {s!r}"
    return None


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
    job = jobs[job_name]

    ctx = _build_base_context(doc, args)
    _merge_env({}, doc.get("env"), ctx)  # top-level env, resolved into ctx["env"]

    matrix_os = _select_matrix_os(job)
    # NOTE: matrix.os must be resolved into ctx BEFORE the job-level env: block
    # is merged below, because that block (e.g. build-installers' credential
    # env) may itself reference ${{ matrix.os }} or other matrix-derived
    # values in a future workflow edit.
    if matrix_os:
        ctx["matrix"]["os"] = matrix_os
        print(f"[run_ci_locally] matrix leg selected: os={matrix_os} (local OS)")

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

    base_env = dict(os.environ)
    base_env.update(ctx["env"])

    results: List[StepResult] = []
    default_shell = ((job.get("defaults") or {}).get("run") or {}).get("shell", "bash")

    for step in job.get("steps", []):
        name = step.get("name", step.get("uses", step.get("run", "<step>"))[:60])

        reason = _filtered_out(name, args.only, args.skip)
        if reason:
            results.append(StepResult(name, "SKIPPED", reason))
            continue

        if "if" in step and not eval_condition(step["if"], ctx):
            results.append(
                StepResult(name, "SKIPPED", f"if: {step['if']!r} evaluated false")
            )
            continue

        if "uses" in step:
            action = step["uses"].split("@", 1)[0]
            handler = _ACTION_HANDLERS.get(action)
            result = (
                handler(step) if handler else _handle_unknown_action(step, step["uses"])
            )
            results.append(result)
            continue

        if "run" not in step:
            results.append(
                StepResult(name, "SKIPPED", "no run: or uses: -- nothing to execute")
            )
            continue

        step_env = dict(base_env)
        if step.get("env"):
            step_ctx = dict(ctx)
            _merge_env(step_env, step["env"], step_ctx)
        shell = step.get("shell", default_shell)
        result = _run_step(step, step_env, shell, args.dry_run)
        results.append(result)
        if result.status == "RAN-FAIL":
            remaining = job.get("steps", [])
            idx = remaining.index(step)
            for later in remaining[idx + 1 :]:
                lname = later.get(
                    "name", later.get("uses", later.get("run", "<step>"))[:60]
                )
                results.append(
                    StepResult(
                        lname, "NOT-RUN", "upstream step failed; run stopped here"
                    )
                )
            break

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


def print_summary(job_name: str, results: List[StepResult]) -> int:
    print("\n" + "-" * 78)
    print(f"LOCAL RUN SUMMARY -- job={job_name!r} os={_LOCAL_RUNNER_OS}")
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


def main() -> int:
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
    args = ap.parse_args()

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
    return print_summary(args.job, results)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\nrun_ci_locally: interrupted.", file=sys.stderr)
        sys.exit(130)
