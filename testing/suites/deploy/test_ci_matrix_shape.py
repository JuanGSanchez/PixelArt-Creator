"""CI-matrix SHAPE test for the ``quality-gate`` and ``integration`` jobs
(T-40, remediation register; WP-6.6 extended it to ``integration``, decision
batch 2026-08-16; brought to the post-revert flat-matrix truth by the
hosted-runner revert that landed as d7daaa3; brought to the event-conditional
``setup``-job truth by the trigger-scoping change of 2026-09-01, PR #39).

Placed under ``testing/suites/deploy/`` (moved from ``tests/deploy/`` on
2026-08-30, see ADR-0065) -- AGT-09's owned surface (ADR-0043 §1 covers
the pipeline vehicles this agent runs; ``.github/workflows/ci.yml`` itself is
this agent's surface too) -- but deliberately **NOT**
``@pytest.mark.integration``, same ruling and precedent as
``test_packaging_artifacts.py`` and ``test_run_ci_router.py`` already in this
directory: this is a read-only YAML parse with no subprocess, no Docker, no
Nginx, no network. It belongs in the default gate.

WHY THIS TEST EXISTS: ``ci.yml``'s cross-OS ``quality-gate`` matrix and its
dedicated ``integration`` job are the two surfaces most likely to drift
silently -- a matrix that narrows (a future edit drops a leg), widens
(someone adds a leg without updating this table), or is reshaped (flat
``matrix.os`` collapsed back into a per-leg ``include:`` block, or vice
versa) should be REPORTED BY THE SUITE, not discovered later by manual audit
of the workflow file. Likewise a silent repoint of ``integration``'s
``runs-on`` (hosted <-> self-hosted, or to a different hosted OS) or a
dropped test root from its ``pytest -m integration`` invocation.

CURRENT SHAPE (post-lean-push change, matches ci.yml as of the 2026-09-01
maintainer-requested revision): both jobs run on PLAIN HOSTED GitHub
runners -- there is no self-hosted leg or self-hosted label anywhere in this
workflow any more. ``quality-gate`` no longer carries a literal
``matrix: {os: [...]}`` list -- a static YAML parse of that key now yields
the UNRESOLVED runtime expression string
``${{ fromJSON(needs.setup.outputs.os) }}``, because ``quality-gate needs:
setup`` and its matrix is computed by a dedicated ``setup`` job at run time:
the full 3-OS list (``ubuntu-latest``, ``windows-latest``, ``macos-latest``)
on ``pull_request`` (required because ``main``'s ruleset requires all three
``quality-gate (<os>)`` check names by exact string with no bypass), and a
single-leg ``["windows-latest"]`` on every other trigger (post-merge
``push``, ``workflow_dispatch`` -- changed from ``["ubuntu-latest"]`` on
2026-09-01, maintainer decision after inspecting the CI run lists), where
nothing is required-check-gated and the content was already fully tested by
the ``pull_request`` run that gated the merge. The two on-demand jobs
(``build-installers``, ``regenerate-constraints``) that used to live in this
same file behind a job-level ``if:`` -- and therefore listed as permanently
``skipped`` on every ordinary push/PR run, since GitHub still evaluates and
lists a job even when its own ``if:`` is false -- were moved out to their
own dedicated workflow files (``.github/workflows/build-installers.yml``,
``.github/workflows/regenerate-constraints.yml``) on the same date; this
file's ``jobs`` mapping now holds only ``setup``, ``quality-gate`` and
``integration``, and neither moved job is asserted on here.

THE PROPERTY THIS FILE PROTECTS DID NOT DISAPPEAR WITH THE LITERAL LIST -- IT
MOVED. A static parse of ``ci.yml`` can no longer read the resolved OS list
off ``strategy.matrix.os`` (that key is now an opaque expression string), so
the tests below assert the SAME narrowing/widening protection at its new
location: (1) that ``quality-gate`` still depends on ``setup`` and still
reads its matrix from ``setup``'s output rather than a re-hard-coded list;
(2) the exact two lists the ``setup`` job's own ``run:`` shell script emits,
parsed out of that script and compared against named constants, exactly as
``EXPECTED_QUALITY_GATE_OS_LIST`` did for the old literal matrix; and (3) that
the ``quality-gate``/``integration`` ``name:`` templates still render the
four exact check-name strings ``main``'s branch-protection ruleset requires
with no bypass -- the load-bearing assertion, since a silent rename there
would block every future pull request permanently.

``integration`` runs on a single ``ubuntu-latest`` string, not a self-hosted
label array -- unchanged by the trigger-scoping change and asserted below as
before.
"""

from __future__ import annotations

import json
import re

import yaml

from .conftest import REPO_ROOT

CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# EXPECTATION TABLE (T-40, re-pointed 2026-09-01 to the setup job's emitted
# lists) -- the quality-gate matrix's CURRENT truth, named explicitly so any
# silent narrowing OR widening is caught here.
#
# *** WHEN THE SETUP JOB'S EMITTED LISTS CHANGE, THESE CONSTANTS MUST BE
# *** UPDATED IN THE SAME COMMIT THAT CHANGES ci.yml's `setup` job -- that is
# *** the entire point of asserting against a named constant instead of a
# *** bare leg count: a maintainer who forgets leaves a RED test, not a green
# *** one that quietly stopped meaning anything. The matrix itself
# *** (`quality-gate.strategy.matrix.os`) is now the unresolved expression
# *** `${{ fromJSON(needs.setup.outputs.os) }}` and can no longer be read
# *** directly by a static parse -- these constants describe what that
# *** expression resolves to at runtime, read instead from the `setup` job's
# *** own `run:` script (see `_extract_setup_os_lists` below).
EXPECTED_QUALITY_GATE_OS_LIST_PULL_REQUEST = [
    "ubuntu-latest",
    "windows-latest",
    "macos-latest",
]
EXPECTED_QUALITY_GATE_OS_LIST_OTHER_TRIGGERS = ["windows-latest"]

# The per-leg ``timeout`` field the old ``include:``-shaped table used to
# carry no longer exists (the flat matrix has no per-leg key to hang it on);
# its replacement is this ONE job-level wall-clock cap, asserted separately
# below so that coverage is not silently lost in the revert.
EXPECTED_QUALITY_GATE_JOB_TIMEOUT_MINUTES = 75


def _load_ci_yaml() -> dict:
    return yaml.safe_load(CI_YAML.read_text(encoding="utf-8"))


def _extract_setup_os_lists(run_script: str) -> tuple[list, list]:
    """Parse the two ``echo 'os=[...]'`` JSON list literals out of the
    ``setup`` job's ``run:`` shell script and return them
    ``(pull_request_branch_list, else_branch_list)``, IN SOURCE ORDER --
    the script's own ``if [[ ... == "pull_request" ]]; then ... else ...
    fi`` shape means the first literal encountered is always the
    ``pull_request`` branch and the second is always the fallback branch.

    A static parse cannot ask GitHub Actions to *evaluate* this script --
    only a real run can -- so this is deliberately a source-level regex
    extraction of the two JSON literals the script echoes verbatim, not a
    shell interpreter. If the script's shape changes so that this no longer
    finds exactly two ``os=[...]`` literals, that is itself a shape change
    this test must catch, not silently work around.
    """
    matches = re.findall(r"os=(\[[^\]]*\])", run_script)
    assert len(matches) == 2, (
        f"expected exactly 2 `os=[...]` echo literals in the setup job's "
        f"run script (one per branch of the event_name check), found "
        f"{len(matches)}: {matches}. The setup job's shape has changed -- "
        "update this parser (and the EXPECTED_QUALITY_GATE_OS_LIST_* "
        "constants) in the SAME commit."
    )
    return json.loads(matches[0]), json.loads(matches[1])


def test_quality_gate_matrix_is_driven_by_setup_job_output():
    """``quality-gate`` must still ``needs: setup`` and read its matrix from
    ``setup``'s output rather than a hard-coded list -- this is what catches
    a future edit that silently re-pins the matrix back to a single literal
    platform (or drops the ``setup`` dependency entirely), since such an edit
    would otherwise sail past a test that only checked the resolved OS
    lists."""
    data = _load_ci_yaml()
    quality_gate = data["jobs"]["quality-gate"]

    needs = quality_gate["needs"]
    needs_list = [needs] if isinstance(needs, str) else list(needs)
    assert "setup" in needs_list, (
        f"quality-gate.needs no longer includes 'setup' (observed: "
        f"{needs!r}) -- if the matrix source was deliberately changed, "
        "update this test in the SAME commit."
    )

    observed_matrix_os = quality_gate["strategy"]["matrix"]["os"]
    assert observed_matrix_os == "${{ fromJSON(needs.setup.outputs.os) }}", (
        f"quality-gate's matrix.os is no longer driven by the setup job's "
        f"output -- observed {observed_matrix_os!r}. This is exactly the "
        "silent narrowing/widening this test exists to catch: a matrix "
        "reshaped back to a hard-coded list would not be flagged by any "
        "other assertion in this file. If deliberate, update this test in "
        "the SAME commit."
    )


def test_setup_job_emits_full_matrix_on_pull_request_and_single_leg_otherwise():
    """The property the old literal-matrix table protected has MOVED into
    the ``setup`` job's ``run:`` script, not disappeared: assert the two
    exact OS lists it emits, IN ORDER, against the named constants above --
    a silent narrowing (dropping a leg from the ``pull_request`` branch, which
    would leave one of ``main``'s required checks permanently PENDING), a
    silent widening (adding an unplanned leg to the fallback branch, re-
    inflating post-merge CI cost), or a reorder/rename is caught here even
    when a leg COUNT happens to stay the same."""
    data = _load_ci_yaml()
    steps = data["jobs"]["setup"]["steps"]
    run_step = next(step for step in steps if "run" in step)
    pull_request_list, other_list = _extract_setup_os_lists(run_step["run"])

    assert pull_request_list == EXPECTED_QUALITY_GATE_OS_LIST_PULL_REQUEST, (
        f"setup job's pull_request-branch OS list is now {pull_request_list} "
        f"-- EXPECTED_QUALITY_GATE_OS_LIST_PULL_REQUEST in this test still "
        f"declares {EXPECTED_QUALITY_GATE_OS_LIST_PULL_REQUEST}. If this was "
        "deliberate, update the constant in this test in the SAME commit "
        "that changed ci.yml -- and note that shrinking this list below the "
        "three OS names main's ruleset requires would leave a required "
        "check permanently PENDING on every future pull request."
    )
    assert other_list == EXPECTED_QUALITY_GATE_OS_LIST_OTHER_TRIGGERS, (
        f"setup job's fallback-branch OS list is now {other_list} -- "
        f"EXPECTED_QUALITY_GATE_OS_LIST_OTHER_TRIGGERS in this test still "
        f"declares {EXPECTED_QUALITY_GATE_OS_LIST_OTHER_TRIGGERS}. If this "
        "was deliberate, update the constant in this test in the SAME "
        "commit that changed ci.yml."
    )


def test_quality_gate_strategy_fail_fast_and_job_timeout():
    """Two independent shape facts kept in one test so the table stays at
    six tests (the number this file has carried since T-40), not because
    they are conceptually the same check:

    - fail-fast: false is load-bearing (ci.yml's own comment: a genuine
      platform-specific regression on one leg must not cancel the others) --
      a silent flip to true would be a real behaviour change this suite
      should catch, not just the leg table.
    - timeout-minutes is the job-level wall-clock cap that REPLACED the old
      per-leg ``timeout`` field EXPECTED_QUALITY_GATE_LEGS used to carry
      (the flat ``matrix.os`` shape has no per-leg key left to hang a
      per-leg timeout on). Without this assertion a silent widening or
      narrowing of the single job-level cap would go uncaught by this suite
      entirely -- exactly the kind of coverage the revert could otherwise
      have silently dropped."""
    data = _load_ci_yaml()
    assert data["jobs"]["quality-gate"]["strategy"]["fail-fast"] is False
    assert (
        data["jobs"]["quality-gate"]["timeout-minutes"]
        == EXPECTED_QUALITY_GATE_JOB_TIMEOUT_MINUTES
    )


def test_quality_gate_and_integration_name_templates_render_pinned_check_names():
    """THE LOAD-BEARING TEST IN THIS FILE. ``main``'s branch-protection
    ruleset requires ``quality-gate (ubuntu-latest)``,
    ``quality-gate (windows-latest)``, ``quality-gate (macos-latest)`` and
    ``integration (ubuntu-latest)`` BY EXACT STRING, with NO bypass -- a
    rename of either job's ``name:`` template, or a change to how
    ``${{ matrix.os }}`` is substituted into it, would silently block every
    future pull request from merging forever (the PR that fixed the naming
    would itself be unable to merge). Render the ``quality-gate`` template
    against each of the three pull_request-branch OS values and the
    ``integration`` job's own literal name, and assert the four resulting
    strings exactly."""
    data = _load_ci_yaml()

    quality_gate_name_template = data["jobs"]["quality-gate"]["name"]
    for os_value in EXPECTED_QUALITY_GATE_OS_LIST_PULL_REQUEST:
        rendered = quality_gate_name_template.replace("${{ matrix.os }}", os_value)
        assert rendered == f"quality-gate ({os_value})", (
            f"quality-gate's name template {quality_gate_name_template!r} "
            f"no longer renders to 'quality-gate ({os_value})' -- this "
            "would leave one of main's required checks permanently PENDING "
            "and block every future pull request. If deliberate, this is a "
            "ruleset change too, not just a test update."
        )

    integration_name = data["jobs"]["integration"]["name"]
    assert integration_name == "integration (ubuntu-latest)", (
        f"integration job's name is now {integration_name!r}, not the "
        "'integration (ubuntu-latest)' string main's ruleset requires with "
        "no bypass. If deliberate, this is a ruleset change too, not just a "
        "test update."
    )


# EXPECTATION for the `integration` job's runs-on target -- post-revert
# (d7daaa3), this is a single hosted OS string, not a self-hosted label
# array. *** WHEN THIS CHANGES, UPDATE THIS CONSTANT IN THE SAME COMMIT. ***
EXPECTED_INTEGRATION_RUNS_ON = "ubuntu-latest"


def test_integration_job_exists_and_is_not_commented_out():
    """The ``integration`` job must be real YAML, not prose inside a comment
    block. Before WP-6.2 the entire job was commented out, so
    ``data["jobs"]`` never had an ``"integration"`` key at all -- this is the
    exact silent-disable shape a future edit could reintroduce."""
    data = _load_ci_yaml()
    assert "integration" in data["jobs"], (
        "the integration job is missing from the parsed workflow -- either it "
        "was commented out again (WP-6.2 re-enabled it) or renamed; update "
        "this test in the SAME commit if the rename/removal was deliberate"
    )


def test_integration_job_runs_on_self_hosted_windows_labels():
    """Not just present: pinned to ``ubuntu-latest`` -- post-revert
    (d7daaa3) this job runs on a plain hosted runner, so a silent repoint to
    a self-hosted label array (or to a different hosted OS) is exactly the
    kind of drift this suite exists to catch. Name kept for history/grep
    continuity with the pre-revert self-hosted-era assertion it replaces;
    the assertion itself now checks the opposite direction -- that no
    self-hosted label has crept back in."""
    data = _load_ci_yaml()
    assert data["jobs"]["integration"]["runs-on"] == EXPECTED_INTEGRATION_RUNS_ON


def test_integration_job_names_both_test_roots():
    """HARD RULE (ADR-0043 §3a): the integration job's pytest invocation must
    name BOTH ``testing/suites/deploy/`` and ``testing/suites/backend/`` --
    naming only one is exactly how a suite silently stops running while the
    check stays green (after the ADR-0043 move, ``pytest -m integration
    tests/backend/`` alone collected 0 and exited 5; the roots were later
    relocated under ``testing/suites/`` on 2026-08-30, ADR-0065). A read-only
    substring check on the step's own
    command, so a future edit that drops either root fails here instead of
    silently shrinking coverage."""
    data = _load_ci_yaml()
    steps = data["jobs"]["integration"]["steps"]
    run_commands = " ".join(
        step.get("run", "") for step in steps if isinstance(step, dict)
    )
    assert "testing/suites/deploy/" in run_commands
    assert "testing/suites/backend/" in run_commands
