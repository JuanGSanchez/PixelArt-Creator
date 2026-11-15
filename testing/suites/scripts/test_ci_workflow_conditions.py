"""Structural test of the step conditions in the ``quality-gate`` job of
``.github/workflows/ci.yml`` (REQ-L10N-BUILD-006, REQ-L10N-UI-018).

Placed beside the contract tests of the other CI gate vehicles (ADR-0047). Like
``testing/suites/deploy/test_ci_matrix_shape.py`` it is a read-only YAML parse:
no subprocess, no network, no workflow run. It belongs in the default gate.

WHY IT EXISTS. On ``c41349b`` the Ubuntu leg stopped at "Font glyph coverage":
a step whose ``if:`` names no status function runs only while no earlier step
has failed, so every later step (the coverage gates, the documentation gates,
the JavaScript tests, the performance gates) was skipped and reported nothing.
Each of those steps now carries ``!cancelled() && (success() ||
steps.glyph_coverage.outcome == 'failure')``: it runs after a failure of the
glyph step, and after no other failure. The job still fails on the glyph step.
What this module guards is the ways that arrangement can rot without a test
going red:

* a later step is added, or edited, without the condition, so it stops
  reporting again (the original defect);
* a ``continue-on-error`` appears anywhere, which would turn a red step green
  and so silently weaken a gate;
* the glyph step stops making the job fail: it gains ``continue-on-error``,
  its command gains ``|| true``, its own ``if:`` changes so it never runs, or it
  loses the ``id`` the later conditions read;
* the step that checks exception text (REQ-L10N-UI-018) loses its place on
  every leg, or stops failing the job.

HOW IT IS PROVED NOT TO BE VACUOUS. Every rule has PLANTED controls below: a
copy of the real workflow with one defect planted in memory must be reported,
naming that defect. The real workflow must report nothing. A rule that reported
nothing for both would be a blind instrument, so each control also checks that
the planted copy reports MORE than the real one.

THE SEMANTICS CHECK. The textual form of a condition is not the whole story, so
each condition is also evaluated with ``scripts/run_ci_locally.py``'s evaluator
in six job states (see ``_SCENARIOS``). That evaluator implements GitHub's
documented semantics as the runner's author understands them; it is NOT
GitHub's own. Whether GitHub evaluates these expressions the same way is
verified only by a real run.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Tuple

import pytest
import yaml

from .conftest import REPO_ROOT

CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

JOB = "quality-gate"
GLYPH_NAME = "Font glyph coverage (REQ-VI-BUILD-004)"
GLYPH_ID = "glyph_coverage"
GLYPH_IF = "runner.os == 'Linux'"
GLYPH_RUN_PREFIX = "python scripts/font/check_glyph_coverage.py"
GLYPH_RUN_MUST_HAVE = "--gate-catalogues"
#: Fragments that would let the glyph command exit 0 while a character is missing.
GLYPH_RUN_MUST_NOT_HAVE = ("||", ";", "&", "|", "set +e", "exit 0", "true")
CLEANUP_NAME = "Clean up CI temp root (CI-PixelArtCreator)"
EXCEPTION_TEXT_NAME = "Exception text reaching the user (REQ-L10N-UI-018)"
EXCEPTION_TEXT_RUN = "python scripts/check_exception_text.py"

CORE = "!cancelled() && (success() || steps.glyph_coverage.outcome == 'failure')"
LINUX = "runner.os == 'Linux'"
#: The two forms a step after the glyph step may carry (besides the cleanup's
#: ``always()``): the core alone, or the core joined with the Linux test.
ALLOWED_AFTER_GLYPH = (CORE, f"{CORE} && {LINUX}")


# --------------------------------------------------------------------------- #
# Reading the workflow
# --------------------------------------------------------------------------- #
def _load(path: Path = CI_YAML) -> Dict[str, Any]:
    return yaml.safe_load(path.read_bytes().decode("utf-8"))


def _expr(raw: Any) -> Optional[str]:
    """A condition without its ``${{ }}`` wrapper and with single spaces."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2]
    return " ".join(text.split())


def _steps(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    return doc["jobs"][JOB]["steps"]


def _find_key(node: Any, key: str, path: str = "") -> Iterator[str]:
    """Every location at which ``key`` appears as a mapping key."""
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{path}/{k}"
            if k == key:
                yield here
            yield from _find_key(v, key, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _find_key(v, key, f"{path}[{i}]")


def _index_of(doc: Dict[str, Any], name: str) -> Optional[int]:
    hits = [i for i, s in enumerate(_steps(doc)) if s.get("name") == name]
    return hits[0] if len(hits) == 1 else None


# --------------------------------------------------------------------------- #
# The rules (each returns a list of violations; empty means the rule holds)
# --------------------------------------------------------------------------- #
def no_continue_on_error(doc: Dict[str, Any]) -> List[str]:
    """No job or step anywhere in the workflow may carry continue-on-error."""
    return [
        f"continue-on-error present at {where}"
        for where in _find_key(doc, "continue-on-error")
    ]


def glyph_step_fails_the_job(doc: Dict[str, Any]) -> List[str]:
    """The glyph step exists once, is findable by id, and its failure counts."""
    at = _index_of(doc, GLYPH_NAME)
    if at is None:
        return [f"the step {GLYPH_NAME!r} is not present exactly once"]
    step = _steps(doc)[at]
    found: List[str] = []
    if step.get("id") != GLYPH_ID:
        found.append(
            f"glyph step: id is {step.get('id')!r}, not {GLYPH_ID!r}; the later "
            "conditions read steps.glyph_coverage.outcome and would read nothing"
        )
    if _expr(step.get("if")) != GLYPH_IF:
        found.append(
            f"glyph step: if is {step.get('if')!r}, not {GLYPH_IF!r}; a changed "
            "condition can stop the step from running at all"
        )
    run = str(step.get("run", "")).strip()
    if not run.startswith(GLYPH_RUN_PREFIX) or GLYPH_RUN_MUST_HAVE not in run:
        found.append(f"glyph step: the command is not the gate any more: {run!r}")
    for fragment in GLYPH_RUN_MUST_NOT_HAVE:
        if fragment in run:
            found.append(
                f"glyph step: the command contains {fragment!r}, which can hide "
                f"a failure: {run!r}"
            )
    if "\n" in run:
        found.append("glyph step: the command is more than one line")
    return found


def later_steps_report_their_own_result(doc: Dict[str, Any]) -> List[str]:
    """Every step after the glyph step carries the condition, or is the cleanup."""
    at = _index_of(doc, GLYPH_NAME)
    if at is None:
        return []  # glyph_step_fails_the_job reports the absence
    found: List[str] = []
    for step in _steps(doc)[at + 1 :]:
        name = step.get("name", "<unnamed>")
        expr = _expr(step.get("if"))
        if name == CLEANUP_NAME:
            if expr != "always()":
                found.append(f"{name!r}: if is {step.get('if')!r}, not 'always()'")
            continue
        if expr not in ALLOWED_AFTER_GLYPH:
            found.append(
                f"{name!r}: if is {step.get('if')!r}; a step after the glyph "
                f"step must carry {CORE!r}, alone or joined with {LINUX!r}"
            )
    return found


def exception_text_step_gates_every_leg(doc: Dict[str, Any]) -> List[str]:
    """The exception-text step exists, runs on every leg, and fails the job."""
    at = _index_of(doc, EXCEPTION_TEXT_NAME)
    if at is None:
        return [f"the step {EXCEPTION_TEXT_NAME!r} is not present exactly once"]
    glyph_at = _index_of(doc, GLYPH_NAME)
    step = _steps(doc)[at]
    found: List[str] = []
    if glyph_at is not None and at < glyph_at:
        found.append("exception-text step: placed before the glyph step")
    if _expr(step.get("if")) != CORE:
        found.append(
            f"exception-text step: if is {step.get('if')!r}; it must be {CORE!r} "
            "alone, with no runner.os test, so that it runs on every leg"
        )
    run = str(step.get("run", "")).strip()
    if run != EXCEPTION_TEXT_RUN:
        found.append(
            f"exception-text step: the command is {run!r}, not {EXCEPTION_TEXT_RUN!r}"
        )
    return found


RULES = (
    no_continue_on_error,
    glyph_step_fails_the_job,
    later_steps_report_their_own_result,
    exception_text_step_gates_every_leg,
)


def all_violations(doc: Dict[str, Any]) -> List[str]:
    return [line for rule in RULES for line in rule(doc)]


# --------------------------------------------------------------------------- #
# The semantics: each condition, evaluated in six job states
# --------------------------------------------------------------------------- #
def _load_runner() -> Any:
    module = sys.modules.get("run_ci_locally")
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(
        "run_ci_locally", REPO_ROOT / "scripts" / "run_ci_locally.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_ci_locally"] = module
    spec.loader.exec_module(module)
    return module


def _ctx(os_name: str, failed: bool, cancelled: bool, glyph: str) -> Dict[str, Any]:
    return {
        "runner": {"os": os_name},
        "github": {"event_name": "pull_request"},
        "needs": {},
        "steps": {f"{GLYPH_ID}.outcome": glyph},
        "_status": {"failed": failed, "cancelled": cancelled},
    }


class _Scenario(NamedTuple):
    label: str
    runner_os: str
    step_failed: bool
    cancelled: bool
    glyph_outcome: str
    runs_with_linux_test: bool
    runs_without_it: bool


_SCENARIOS: Tuple[_Scenario, ...] = (
    _Scenario("nothing failed, Linux", "Linux", False, False, "success", True, True),
    _Scenario("the glyph step failed", "Linux", True, False, "failure", True, True),
    _Scenario("another step failed", "Linux", True, False, "success", False, False),
    _Scenario(
        "a step before the glyph failed", "Linux", True, False, "skipped", False, False
    ),
    _Scenario(
        "cancelled after the glyph failed", "Linux", True, True, "failure", False, False
    ),
    _Scenario(
        "nothing failed, Windows leg", "Windows", False, False, "skipped", False, True
    ),
    _Scenario(
        "a step failed, Windows leg", "Windows", True, False, "skipped", False, False
    ),
)


def semantic_violations(doc: Dict[str, Any]) -> List[str]:
    """Evaluate every later step's condition in each scenario above."""
    runner = _load_runner()
    at = _index_of(doc, GLYPH_NAME)
    if at is None:
        return ["the glyph step is not present exactly once"]
    found: List[str] = []
    for step in _steps(doc)[at + 1 :]:
        name = step.get("name", "<unnamed>")
        raw = step.get("if")
        is_cleanup = name == CLEANUP_NAME
        has_linux = LINUX in (_expr(raw) or "")
        for sc in _SCENARIOS:
            ctx = _ctx(sc.runner_os, sc.step_failed, sc.cancelled, sc.glyph_outcome)
            got = runner.eval_step_condition(raw, ctx)
            if is_cleanup:
                want = True
            else:
                want = sc.runs_with_linux_test if has_linux else sc.runs_without_it
            if got is not want:
                found.append(
                    f"{name!r} in {sc.label!r}: runs={got}, expected {want} "
                    f"(if: {raw!r})"
                )
    return found


# --------------------------------------------------------------------------- #
# Fixtures and helpers for the planted controls
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def real_doc() -> Dict[str, Any]:
    return _load()


def _planted(doc: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(doc)


def _step(doc: Dict[str, Any], name: str) -> Dict[str, Any]:
    at = _index_of(doc, name)
    assert at is not None, name
    return _steps(doc)[at]


def _later_step_names(doc: Dict[str, Any]) -> List[str]:
    at = _index_of(doc, GLYPH_NAME)
    assert at is not None
    return [s["name"] for s in _steps(doc)[at + 1 :] if s["name"] != CLEANUP_NAME]


def _must_report_more(real: List[str], planted: List[str], needle: str) -> None:
    """A planted defect is reported, by name, on top of whatever was reported."""
    assert len(planted) > len(real), (real, planted)
    assert any(needle in line for line in planted), (needle, planted)


_REAL_NAMES = _later_step_names(_load())


# --------------------------------------------------------------------------- #
# The real workflow
# --------------------------------------------------------------------------- #
def test_the_real_workflow_satisfies_every_rule(real_doc):
    assert all_violations(real_doc) == []


def test_the_real_workflow_behaves_in_every_scenario(real_doc):
    assert semantic_violations(real_doc) == []


def test_the_glyph_step_is_followed_by_a_real_number_of_steps(real_doc):
    # A rule that loops over nothing passes for the wrong reason.
    assert len(_REAL_NAMES) >= 25, len(_REAL_NAMES)
    assert CLEANUP_NAME == _steps(real_doc)[-1]["name"]


# --------------------------------------------------------------------------- #
# Planted control 1: a later step loses the condition (the original defect)
# --------------------------------------------------------------------------- #
def _lose_condition(doc: Dict[str, Any], name: str) -> None:
    step = _step(doc, name)
    if LINUX in (_expr(step.get("if")) or ""):
        step["if"] = LINUX  # the condition before the change
    else:
        step.pop("if", None)  # no `if:`, the implicit success()


@pytest.mark.parametrize("name", _REAL_NAMES)
def test_a_later_step_that_loses_its_condition_is_reported(real_doc, name):
    doc = _planted(real_doc)
    _lose_condition(doc, name)
    _must_report_more(
        later_steps_report_their_own_result(real_doc),
        later_steps_report_their_own_result(doc),
        name,
    )
    _must_report_more(semantic_violations(real_doc), semantic_violations(doc), name)


def test_all_later_steps_losing_their_condition_are_all_reported(real_doc):
    doc = _planted(real_doc)
    for name in _REAL_NAMES:
        _lose_condition(doc, name)
    found = later_steps_report_their_own_result(doc)
    assert len(found) == len(_REAL_NAMES), len(found)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.replace("'failure'", "'success'"),
        lambda c: c.replace("steps.glyph_coverage", "steps.other_step"),
        lambda c: c.replace("!cancelled() && ", ""),
        lambda c: c.replace("success() || ", ""),
        lambda c: c.replace(" && (", " || ("),
        lambda c: "always()",
    ],
    ids=[
        "outcome compared with success",
        "reads another step",
        "no !cancelled()",
        "no success()",
        "or instead of and",
        "always()",
    ],
)
def test_a_condition_that_means_something_else_is_reported(real_doc, mutate):
    name = "Coverage gate — client package (>=90 line / >=80 branch, S13)"
    doc = _planted(real_doc)
    step = _step(doc, name)
    changed = "${{ " + mutate(_expr(step["if"]) or "") + " }}"
    assert changed != step["if"]
    step["if"] = changed
    _must_report_more([], later_steps_report_their_own_result(doc), "Coverage gate")


def test_a_step_added_without_the_condition_is_reported(real_doc):
    doc = _planted(real_doc)
    steps = _steps(doc)
    steps.insert(len(steps) - 1, {"name": "A new gate", "run": "echo gate"})
    _must_report_more([], later_steps_report_their_own_result(doc), "A new gate")


def test_the_cleanup_step_must_stay_always(real_doc):
    doc = _planted(real_doc)
    _step(doc, CLEANUP_NAME)["if"] = CORE
    _must_report_more([], later_steps_report_their_own_result(doc), CLEANUP_NAME)


# --------------------------------------------------------------------------- #
# Planted control 2: a continue-on-error appears anywhere
# --------------------------------------------------------------------------- #
def _plant_on_glyph(doc: Dict[str, Any]) -> None:
    _step(doc, GLYPH_NAME)["continue-on-error"] = True


def _plant_on_later_step(doc: Dict[str, Any]) -> None:
    _step(doc, "Docs build (mkdocs --strict, F14)")["continue-on-error"] = True


def _plant_on_job(doc: Dict[str, Any]) -> None:
    doc["jobs"][JOB]["continue-on-error"] = True


def _plant_on_other_job(doc: Dict[str, Any]) -> None:
    doc["jobs"]["integration"]["continue-on-error"] = True


def _plant_as_expression(doc: Dict[str, Any]) -> None:
    _step(doc, "Tests (pytest, headless, parallel, with coverage XML)")[
        "continue-on-error"
    ] = "${{ runner.os != 'Linux' }}"


def _plant_false_value(doc: Dict[str, Any]) -> None:
    _step(doc, EXCEPTION_TEXT_NAME)["continue-on-error"] = False


@pytest.mark.parametrize(
    "plant",
    [
        _plant_on_glyph,
        _plant_on_later_step,
        _plant_on_job,
        _plant_on_other_job,
        _plant_as_expression,
        _plant_false_value,
    ],
    ids=lambda f: f.__name__.replace("_plant_", ""),
)
def test_a_continue_on_error_anywhere_is_reported(real_doc, plant):
    doc = _planted(real_doc)
    plant(doc)
    _must_report_more(
        no_continue_on_error(real_doc), no_continue_on_error(doc), "continue-on-error"
    )


def test_the_real_workflow_has_no_continue_on_error_key(real_doc):
    # Comments in ci.yml say "no continue-on-error"; the parse sees keys only.
    assert list(_find_key(real_doc, "continue-on-error")) == []


# --------------------------------------------------------------------------- #
# Planted control 3: the glyph step's failure stops making the job fail
# --------------------------------------------------------------------------- #
def _glyph_continue_on_error(doc: Dict[str, Any]) -> None:
    _step(doc, GLYPH_NAME)["continue-on-error"] = True


def _glyph_or_true(doc: Dict[str, Any]) -> None:
    step = _step(doc, GLYPH_NAME)
    step["run"] = step["run"].rstrip() + " || true"


def _glyph_semicolon_exit(doc: Dict[str, Any]) -> None:
    step = _step(doc, GLYPH_NAME)
    step["run"] = step["run"].rstrip() + "; exit 0"


def _glyph_without_gate_flag(doc: Dict[str, Any]) -> None:
    step = _step(doc, GLYPH_NAME)
    step["run"] = step["run"].replace("--gate-catalogues", "")


def _glyph_never_runs(doc: Dict[str, Any]) -> None:
    _step(doc, GLYPH_NAME)["if"] = "false"


def _glyph_loses_id(doc: Dict[str, Any]) -> None:
    _step(doc, GLYPH_NAME).pop("id")


def _glyph_id_renamed(doc: Dict[str, Any]) -> None:
    _step(doc, GLYPH_NAME)["id"] = "glyphs"


def _glyph_made_unconditional(doc: Dict[str, Any]) -> None:
    _step(doc, GLYPH_NAME)["if"] = "always()"


@pytest.mark.parametrize(
    "plant",
    [
        _glyph_continue_on_error,
        _glyph_or_true,
        _glyph_semicolon_exit,
        _glyph_without_gate_flag,
        _glyph_never_runs,
        _glyph_loses_id,
        _glyph_id_renamed,
        _glyph_made_unconditional,
    ],
    ids=lambda f: f.__name__.replace("_glyph_", ""),
)
def test_a_glyph_step_that_cannot_fail_the_job_is_reported(real_doc, plant):
    doc = _planted(real_doc)
    plant(doc)
    real = glyph_step_fails_the_job(real_doc) + no_continue_on_error(real_doc)
    planted = glyph_step_fails_the_job(doc) + no_continue_on_error(doc)
    assert len(planted) > len(real), planted


def test_a_glyph_step_that_is_gone_is_reported(real_doc):
    doc = _planted(real_doc)
    steps = _steps(doc)
    steps.pop(_index_of(doc, GLYPH_NAME))
    _must_report_more([], glyph_step_fails_the_job(doc), "not present")
    assert semantic_violations(doc) != []


def test_a_renamed_glyph_id_leaves_the_conditions_reading_nothing(real_doc):
    # The id is renamed and the later conditions are NOT: the rule on the glyph
    # step reports it, and so does the evaluation (the gate's outcome is then
    # unknown to the later steps, so the glyph failure no longer lets them run).
    doc = _planted(real_doc)
    _glyph_id_renamed(doc)
    runner = _load_runner()
    ctx = _ctx("Linux", True, False, "failure")
    del ctx["steps"][f"{GLYPH_ID}.outcome"]
    ctx["steps"]["glyphs.outcome"] = "failure"
    name = "Docs build (mkdocs --strict, F14)"
    assert runner.eval_step_condition(_step(doc, name)["if"], ctx) is False
    assert glyph_step_fails_the_job(doc) != []


# --------------------------------------------------------------------------- #
# The exception-text step (REQ-L10N-UI-018)
# --------------------------------------------------------------------------- #
def test_the_exception_text_step_runs_on_every_leg_and_fails_the_job(real_doc):
    step = _step(real_doc, EXCEPTION_TEXT_NAME)
    assert _expr(step["if"]) == CORE
    assert LINUX not in _expr(step["if"])
    assert step["run"].strip() == EXCEPTION_TEXT_RUN
    assert "continue-on-error" not in step


@pytest.mark.parametrize("os_name", ["Linux", "Windows", "macOS"])
def test_the_exception_text_step_runs_on_each_leg(real_doc, os_name):
    runner = _load_runner()
    step = _step(real_doc, EXCEPTION_TEXT_NAME)
    healthy = _ctx(os_name, False, False, "skipped")
    assert runner.eval_step_condition(step["if"], healthy) is True


def _exception_linux_only(doc: Dict[str, Any]) -> None:
    _step(doc, EXCEPTION_TEXT_NAME)["if"] = "${{ " + f"{CORE} && {LINUX}" + " }}"


def _exception_swallowed(doc: Dict[str, Any]) -> None:
    step = _step(doc, EXCEPTION_TEXT_NAME)
    step["run"] = step["run"] + " || true"


def _exception_continue_on_error(doc: Dict[str, Any]) -> None:
    _step(doc, EXCEPTION_TEXT_NAME)["continue-on-error"] = True


def _exception_no_condition(doc: Dict[str, Any]) -> None:
    _step(doc, EXCEPTION_TEXT_NAME).pop("if")


def _exception_removed(doc: Dict[str, Any]) -> None:
    steps = _steps(doc)
    steps.pop(_index_of(doc, EXCEPTION_TEXT_NAME))


@pytest.mark.parametrize(
    "plant",
    [
        _exception_linux_only,
        _exception_swallowed,
        _exception_continue_on_error,
        _exception_no_condition,
        _exception_removed,
    ],
    ids=lambda f: f.__name__.replace("_exception_", ""),
)
def test_an_exception_text_step_that_cannot_gate_every_leg_is_reported(real_doc, plant):
    doc = _planted(real_doc)
    plant(doc)
    real = exception_text_step_gates_every_leg(real_doc) + no_continue_on_error(
        real_doc
    )
    planted = exception_text_step_gates_every_leg(doc) + no_continue_on_error(doc)
    assert len(planted) > len(real), planted
