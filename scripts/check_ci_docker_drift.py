#!/usr/bin/env python
# =============================================================================
# SCRIPT: check_ci_docker_drift  (standalone P11 script -- PixelArt Creator)
# =============================================================================
# PURPOSE: Fail when `.ci/Dockerfile`'s apt package list for headless Qt drifts
#   from `.github/workflows/ci.yml`'s "Install Qt runtime OS libraries
#   (Ubuntu)" step. The Dockerfile's own header claims it copies that list
#   verbatim from the workflow -- this script is the check that makes that
#   claim self-enforcing instead of a comment nobody re-verifies. This is a
#   DRIFT GUARD, not a lint: it compares two independently-maintained package
#   lists and fails closed when they disagree, the same defect class ADR-0045
#   names ("a hand-copied list ... will diverge, silently, the next time
#   someone edits one and forgets the other").
# FLAVOUR: standalone
# LOCATION: scripts/check_ci_docker_drift.py
# INVOKED BY: AGT-09 GitHub/DevOps, directly, and from `scripts/run_ci.py`'s
#   Linux-container fallback leg (run_linux_leg_in_container) BEFORE it builds
#   the image -- so a stale image is refused rather than silently used. It is
#   NOT currently invoked from `.github/workflows/ci.yml` itself: wiring it in
#   there would mean editing ci.yml, which is out of scope for the task that
#   authored this script (see run_ci.py's own header / the accompanying
#   report). That is a KNOWN, REPORTED gap, not an oversight this comment
#   should let a future reader miss.
# RUNTIME: Python 3.8+ (CPython). Needs PyYAML (`import yaml`) to parse
#   ci.yml -- same dependency `scripts/run_ci_locally.py` already declares
#   (available transitively via the `mkdocs` dev extra, or `pip install
#   pyyaml` directly).
# ENTRYPOINT: python scripts/check_ci_docker_drift.py
#             [--ci-workflow PATH] [--dockerfile PATH]
# INPUTS:
#   --ci-workflow (CLI, optional, default ".github/workflows/ci.yml" relative
#                 to the repo root computed from this file's location).
#   --dockerfile  (CLI, optional, default ".ci/Dockerfile").
# OUTPUTS:
#   stdout: how many packages agree, on a clean run.
#   stderr: the two one-sided diffs (in ci.yml but not the Dockerfile, and
#     vice versa) when they disagree.
# EXIT CODES: 0 the two package sets are IDENTICAL -> no drift;
#   1 the two package sets DISAGREE -> DRIFT DETECTED, blocks the Linux-leg
#     image build in run_ci.py;
#   2 could not read/parse one of the inputs (missing file, missing job/step,
#     PyYAML missing) -> BLOCKED, not a verdict either way.
# PRECONDITIONS: `--ci-workflow` parses as YAML with a top-level `jobs:`
#   mapping containing a `quality-gate` job with a step named "Install Qt
#   runtime OS libraries (Ubuntu)"; `--dockerfile` exists and contains an
#   `apt-get install` block using the same backslash-continuation shape.
# DETERMINISM NOTE: deterministic -- pure text/YAML parsing of two local
#   files, no network, no time, no random.
#
# ## Principles Applied
# Inherited: P1 (parses the REAL committed files; never hard-codes "the
#   package list" as a second copy anywhere in this script), P6, P9 (one job:
#   detect apt-list drift between these two specific files), P10, P11.
# Custom: the extraction logic (_extract_apt_packages) is deliberately GENERIC
#   over the two different wrapping shapes (a workflow `run:` block string vs
#   a Dockerfile `RUN` instruction) rather than two separate hand-written
#   parsers, so there is exactly one definition of "what counts as a package
#   token" to keep correct.
#
# SOURCES: .github/workflows/ci.yml (the "Install Qt runtime OS libraries
#   (Ubuntu)" step, read directly -- this is the exact, committed apt list
#   this script diffs against, not a copy from memory); .ci/Dockerfile (this
#   task's own artifact, which states in its header that its apt line is
#   copied from that same step); docs/adr/0045-local-ci-execution-strategy.md
#   (the "hand-copied list will diverge" defect class this guard closes).
# =============================================================================
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEFAULT_DOCKERFILE = REPO_ROOT / ".ci" / "Dockerfile"

CI_JOB_NAME = "quality-gate"
CI_STEP_NAME = "Install Qt runtime OS libraries (Ubuntu)"

_APT_INSTALL_RE = re.compile(r"\bapt-get\s+install\b")  # portability: ok
_SKIP_TOKENS = {"-y", "--no-install-recommends"}
_LEADING_WORDS = {"sudo", "apt-get", "install", "update", "run", "&&"}


def _extract_apt_packages(shell_text: str) -> List[str]:
    """Extract package-name tokens from an `apt-get update && apt-get install
    -y --no-install-recommends \\`-continued shell block.

    Generic over the exact wrapping: a GitHub Actions workflow `run:` block
    (already a plain multi-line string once PyYAML loads it) and a
    Dockerfile `RUN` instruction (read as raw text) share the identical
    backslash-continuation shape, verified by reading both files -- so one
    parser covers both call sites below rather than two hand-written ones.
    """
    packages: List[str] = []
    collecting = False
    for raw_line in shell_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not collecting:
            if _APT_INSTALL_RE.search(line):
                collecting = True
            else:
                continue
        tokens = line.rstrip("\\").split()
        stop = False
        for tok in tokens:
            # "&&" ends the apt-get install invocation (e.g. Dockerfile's
            # trailing "&& rm -rf /var/lib/apt/lists/*" cleanup) -- anything
            # after it is a DIFFERENT shell command, not a package name.
            if tok == "&&":
                stop = True
                break
            if (
                tok.lower() in _LEADING_WORDS
                or tok in _SKIP_TOKENS
                or tok.startswith("-")
            ):
                continue
            packages.append(tok)
        if stop or not line.endswith("\\"):
            break
    return packages


def _ci_workflow_packages(path: Path) -> List[str]:
    try:
        # Local import (same pattern as scripts/run_ci_locally.py): keeps the
        # module importable for --help even if PyYAML is missing.
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to parse the workflow (`pip install pyyaml`)"
        ) from exc
    if not path.is_file():
        raise FileNotFoundError(f"ci workflow not found: {path}")
    with path.open(encoding="utf-8") as fh:
        doc: Any = yaml.safe_load(fh)
    jobs = (doc or {}).get("jobs", {}) if isinstance(doc, dict) else {}
    job = jobs.get(CI_JOB_NAME)
    if job is None:
        raise KeyError(f"job {CI_JOB_NAME!r} not found in {path}")
    for step in job.get("steps", []):
        if step.get("name") == CI_STEP_NAME:
            return _extract_apt_packages(str(step.get("run", "")))
    raise KeyError(f"step {CI_STEP_NAME!r} not found in job {CI_JOB_NAME!r} of {path}")


def _dockerfile_packages(path: Path) -> List[str]:
    if not path.is_file():
        raise FileNotFoundError(f"Dockerfile not found: {path}")
    return _extract_apt_packages(path.read_text(encoding="utf-8"))


def compare(
    ci_workflow: Path = DEFAULT_CI_WORKFLOW,
    dockerfile: Path = DEFAULT_DOCKERFILE,
) -> Tuple[Set[str], Set[str], Set[str]]:
    """Return (ci_only, dockerfile_only, matched) apt package name sets."""
    ci_packages = set(_ci_workflow_packages(ci_workflow))
    docker_packages = set(_dockerfile_packages(dockerfile))
    return (
        ci_packages - docker_packages,
        docker_packages - ci_packages,
        ci_packages & docker_packages,
    )


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Fail when .ci/Dockerfile's apt package list drifts from ci.yml's "
            "Ubuntu Qt-runtime-libraries step. Both must name the exact same "
            "set."
        )
    )
    ap.add_argument("--ci-workflow", type=Path, default=DEFAULT_CI_WORKFLOW)
    ap.add_argument("--dockerfile", type=Path, default=DEFAULT_DOCKERFILE)
    args = ap.parse_args(argv)

    try:
        ci_only, docker_only, matched = compare(args.ci_workflow, args.dockerfile)
    except (FileNotFoundError, KeyError, RuntimeError) as exc:
        print(f"check_ci_docker_drift: {exc}", file=sys.stderr)
        return 2

    if ci_only or docker_only:
        if ci_only:
            print(
                "check_ci_docker_drift: in ci.yml but NOT in .ci/Dockerfile: "
                f"{sorted(ci_only)}",
                file=sys.stderr,
            )
        if docker_only:
            print(
                "check_ci_docker_drift: in .ci/Dockerfile but NOT in ci.yml: "
                f"{sorted(docker_only)}",
                file=sys.stderr,
            )
        print(
            f"check_ci_docker_drift: DRIFT DETECTED -- {len(matched)} "
            f"package(s) agree, {len(ci_only) + len(docker_only)} do not.",
            file=sys.stderr,
        )
        return 1

    print(
        f"check_ci_docker_drift: no drift -- {len(matched)} package(s) "
        "identical in both files."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
