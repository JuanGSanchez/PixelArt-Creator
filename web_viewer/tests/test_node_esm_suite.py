"""Python-side runner for the framework-free Node ESM unit suite (job
20260816-spec-audit-test-rebuild-docs-move).

``web_viewer/tests/test_viewer_core.mjs`` (renamed from ``viewer_core.test.mjs`` by
R-42 so the matrix tool's ``test_``-prefix citation scan actually finds it) runs under
a bare ``node`` -- no npm, no bundler, no framework (A4). Node itself is not
guaranteed to be present in every
environment this repository is checked out in, so this module never lets an absent
runtime read as a pass: when ``node`` cannot be found on ``PATH`` the test is SKIPPED
with an explicit reason (never silently green, A6/C4), and the skip is visible in the
pytest summary rather than folded into a pass count.

When ``node`` IS present, this asserts the HONEST-skip contract the node-esm-harness
skill requires (SKILL.md step 5/6): the suite must print how many tests it actually
executed, and it must never exit 0 having executed zero of them.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

#: web_viewer/tests/test_node_esm_suite.py -> parents[1] is web_viewer/, matching the
#: layout every other module in this directory already assumes.
WEB_VIEWER_DIR = Path(__file__).resolve().parents[1]
SUITE_PATH = WEB_VIEWER_DIR / "tests" / "test_viewer_core.mjs"
CORE_PATH = WEB_VIEWER_DIR / "static" / "viewer_core.mjs"

#: "executed <N> tests, <M> passed" -- the honest line every run (pass, fail, or
#: import-skip) must print (node-esm-harness SKILL.md, "always print the count").
_EXECUTED_LINE_RE = re.compile(r"^executed (\d+) tests, (\d+) passed$", re.MULTILINE)

NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    NODE is None,
    reason=(
        "node runtime not found on PATH -- Node ESM suite reported unrun, " "not a pass"
    ),
)


def _run_suite() -> subprocess.CompletedProcess:
    assert NODE is not None  # pytestmark guards this at collection time
    return subprocess.run(
        [NODE, str(SUITE_PATH)],
        cwd=str(WEB_VIEWER_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_syntax_gate_on_the_suite_and_the_module_under_test() -> None:
    """``node --check`` on both ``.mjs`` files -- a syntax error caught here is a
    one-line diagnosis; the same error caught during import is a confusing skip
    (node-esm-harness SKILL.md step 2)."""
    for path in (SUITE_PATH, CORE_PATH):
        result = subprocess.run(
            [NODE, "--check", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"{path}: {result.stderr}"


def test_viewer_core_suite_executes_and_reports_an_honest_count() -> None:
    """The suite must exit 0 AND report a non-zero executed count -- exit code
    alone is not proof of a real run (A6): a suite that skipped the import and
    exited 0 would satisfy the exit-code check alone but never a real one."""
    result = _run_suite()

    match = _EXECUTED_LINE_RE.search(result.stdout)
    assert match is not None, (
        "expected an 'executed N tests, M passed' line in stdout; got:\n"
        f"{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    executed, passed = int(match.group(1)), int(match.group(2))

    assert (
        executed > 0
    ), f"0 tests executed -- a skip is never a pass (A6). stdout:\n{result.stdout}"
    assert result.returncode == 0, (
        f"suite exited {result.returncode} (executed={executed}, passed={passed}); "
        f"stderr:\n{result.stderr}"
    )
    assert (
        passed == executed
    ), f"{executed - passed} of {executed} tests failed; stdout:\n{result.stdout}"


def test_zero_executed_tests_would_never_be_reported_as_success(tmp_path: Path) -> None:
    """Proves the honesty contract itself, not just today's suite content: feed the
    real runner an import target that cannot resolve (a nonexistent core module) via
    a throwaway copy of the suite pointed at a missing file, and confirm the honest
    'executed 0 tests' path exits non-zero -- exactly the node-esm-harness A6/C4
    guarantee this suite's own import-skip branch is supposed to uphold.

    The copy is written entirely under ``tmp_path`` (never the real ``web_viewer``
    tree the suite ships from) -- a scratch fixture, not a mutated real artifact.
    ``tmp_path/tests/`` deliberately has NO sibling ``static/`` directory, so
    ``../static/viewer_core.mjs`` cannot resolve regardless of the literal used.
    """
    suite_text = SUITE_PATH.read_text(encoding="utf-8")

    scratch_tests_dir = tmp_path / "scratchpad" / "tests"
    scratch_tests_dir.mkdir(parents=True)
    broken_suite = scratch_tests_dir / "broken_import_suite.mjs"
    broken_suite.write_text(suite_text, encoding="utf-8")

    fixture = WEB_VIEWER_DIR / "tests" / "fidelity_fixture.json"
    (scratch_tests_dir / "fidelity_fixture.json").write_bytes(fixture.read_bytes())

    result = subprocess.run(
        [NODE, str(broken_suite)],
        cwd=str(scratch_tests_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "executed 0 tests, 0 passed" in result.stdout, result.stdout
    assert result.returncode != 0, (
        "an unimportable module must never exit 0 (A6): "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
