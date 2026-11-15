"""Structural and behavioural test of the CONTROLS inside the "Localisation
typography (REQ-L10N-DATA-004)" step of ``.github/workflows/ci.yml``.

Placed beside the contract tests of the other CI gate vehicles (ADR-0047). The
step is the checker ``scripts/check_l10n_typography.py`` plus a floor plus two
controls, all in one program embedded in the workflow. This module guards the
SECOND control, "control (ii), planted": the program picks a finished French
message that has a number, one U+00A0 and a unit, writes an ordinary space in
its place in a copy of the catalogue, and demands that the checker report
exactly one more ``fr-num-unit`` finding, naming that message. If it finds no
such site it FAILS ("control site not found"); it never falls back to a
synthetic entry.

WHY IT EXISTS. The control once looked for its site in the file's bytes and
required the raw character U+00A0 there. The extraction (``pyside6-lupdate``)
writes that character as the numeric reference ``&#xa0;`` (and U+202F as
``&#x202f;``), so after the catalogues were re-extracted the control could not
find a site, failed on all three legs, and nothing had told its author: the
checker was green, the control was the red. The control now accepts the site
in either spelling. This module keeps it honest in three ways it can rot
without any other test going red:

* the control is removed, or its call is turned into a no-op;
* it stops demanding EXACTLY ONE extra finding (zero, or two, would pass);
* it starts accepting "control site not found" as a pass, or stops finding a
  site that is written as a numeric reference.

HOW IT WORKS. The program is taken verbatim from the real workflow (YAML parse,
no copy of it lives here) and RUN in a scratch repository root under
``tmp_path``: a small French catalogue, the two checker scripts copied from the
working tree, a stand-in ``language_names.py``. No tracked file is read or
written other than as a copy. Each SCENARIO builds that root with one property:

* the site is written as ``&#xa0;``, ``&#xA0;``, ``&#160;`` or the raw
  character: the program must exit 0 and say "control (ii) OK";
* there is no number-plus-unit site at all, or the only site occurs twice in
  its message (in one spelling, or in two): the program must exit 1 and say
  "control site not found";
* the site exists but the checker does not see a defect planted at it (the
  rule's function is patched to return no finding): the program must exit 1 and
  say it expected exactly one more finding;
* the checker sees the planted defect TWICE (patched to return each finding
  twice): the program must exit 1 and say it expected exactly one more finding;
* the checker's reader does not see numeric references (patched): the program
  must exit 1.

HOW THE TEST IS PROVED NOT TO BE VACUOUS. The real program must pass every
scenario. Then a copy of the program with ONE weakening planted in memory (the
control's call removed, "exactly one" relaxed to "at least one", "site not
found" turned into a printed note, the reference spelling no longer searched)
must be reported by the scenario that defends the rule: a rule that reported
nothing for both would be a blind instrument.

WHAT IT DOES NOT SHOW. It runs the program under the interpreter of the test
run, on the OS of the test run, and reads the checker scripts of the working
tree. Whether GitHub's runner behaves alike is verified only by a real run.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

import pytest
import yaml

from .conftest import REPO_ROOT

CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
JOB = "quality-gate"
STEP_PREFIX = "Localisation typography"
NBSP = " "

#: The marker lines of the step's heredoc: the program is everything between.
_HEREDOC = re.compile(r"<<'PY'\n(?P<program>.*)\nPY\s*\Z", re.DOTALL)


# --------------------------------------------------------------------------- #
# Reading the workflow
# --------------------------------------------------------------------------- #
def _typography_steps() -> List[dict]:
    doc = yaml.safe_load(CI_YAML.read_bytes().decode("utf-8"))
    steps = doc["jobs"][JOB]["steps"]
    return [s for s in steps if str(s.get("name", "")).startswith(STEP_PREFIX)]


def _program_of(step: dict) -> str:
    """The program the step's shell feeds to ``python -I -`` (verbatim)."""
    found = _HEREDOC.search(step["run"])
    assert (
        found
    ), "the typography step no longer carries its program as a <<'PY' heredoc"
    return found.group("program") + "\n"


# --------------------------------------------------------------------------- #
# The scratch repository root a scenario runs in
# --------------------------------------------------------------------------- #
def _message(source: str, translation: str) -> str:
    return f"<message><source>{source}</source><translation>{translation}</translation></message>"


def _catalogue(site: str) -> bytes:
    """A French catalogue whose one variable message is ``site`` (already spelled)."""
    colon = "{sp}:"
    body = (
        _message("Open…", "Ouvrir…")
        + _message("Name:", "Nom" + colon)
        + _message("Maximum size", site)
    )
    text = (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n'
        '<TS version="2.1" language="fr" sourcelanguage="en">\n'
        f"<context><name>Demo</name>{body}</context>\n</TS>\n"
    )
    return text.encode("utf-8")


def _site_text(kind: str) -> str:
    """The French text of the variable message; ``{sp}`` is the spelling under test."""
    return {
        "once": "Taille{sp}: 64{sp}px",
        "none": "Taille{sp}: soixante-quatre pixels",
        "twice": "Taille{sp}: 64{sp}px puis 64{sp}px",
        "mixed": "Taille{sp}: 64&#xa0;px puis 64" + NBSP + "px",
    }[kind]


def _build_root(base: Path, kind: str, spelling: str, patches: Dict[str, str]) -> Path:
    """Write the scratch root; ``patches`` maps a script name to code spliced into its copy."""
    root = base / "r"
    shutil.rmtree(root, ignore_errors=True)
    (root / "scripts").mkdir(parents=True)
    for name in ("check_l10n_typography.py", "check_catalogues.py"):
        shutil.copyfile(REPO_ROOT / "scripts" / name, root / "scripts" / name)
    for name, extra in patches.items():
        path = root / "scripts" / name
        text = path.read_bytes().decode("utf-8")
        if name == "check_l10n_typography.py":
            marker = 'if __name__ == "__main__":'
            assert (
                marker in text
            ), "the checker lost its main guard; the planted patch cannot be spliced"
            text = text.replace(marker, extra + "\n\n" + marker, 1)
        else:
            text = text + "\n" + extra + "\n"
        path.write_bytes(text.encode("utf-8"))
    logic = root / "pixelart_creator" / "logic"
    logic.mkdir(parents=True)
    (logic / "language_names.py").write_bytes(b'ENDONYMS = {"fr": "Fran\xc3\xa7ais"}\n')
    i18n = root / "pixelart_creator" / "i18n"
    i18n.mkdir(parents=True)
    ts = _catalogue(_site_text(kind)).decode("utf-8").replace("{sp}", spelling)
    (i18n / "pixelart_fr.ts").write_bytes(ts.encode("utf-8"))
    (i18n / "pixelart_fr.qm").write_bytes(b"")
    (root / "pixelart_creator" / "userguide_content" / "content").mkdir(parents=True)
    return root


#: Code spliced into the checker's copy so it no longer sees a planted defect.
_BLIND_RULE = (
    "_real_num_unit_problems = num_unit_problems\n\n\n"
    "def num_unit_problems(text):\n"
    "    examined, _problems = _real_num_unit_problems(text)\n"
    "    return examined, []\n"
)
#: Code spliced into the checker's copy so it reports each finding twice.
_DOUBLE_RULE = _BLIND_RULE.replace(
    "return examined, []", "return examined, problems * 2"
).replace("_problems = _real", "problems = _real")
#: Code appended to the catalogue reader's copy so it never sees ``&#xa0;``.
_BLIND_REFERENCES = (
    "_real_fromstring = ET.fromstring\n"
    "ET.fromstring = lambda data, *a, **k: _real_fromstring(data.replace(b'&#xa0;', b''), *a, **k)\n"
)


class Scenario(NamedTuple):
    name: str
    kind: str
    spelling: str
    patches: Tuple[Tuple[str, str], ...]
    want_exit: int
    must_say: Tuple[str, ...]


OK_SAYS = (
    "control (ii) OK",
    "pair 64+U+00A0+px",
    "the new finding names the planted message",
)
NOT_FOUND = ("control site not found",)
ONE_MORE = ("expected exactly one more fr-num-unit finding",)

SCENARIOS: Tuple[Scenario, ...] = (
    Scenario("site written as &#xa0;", "once", "&#xa0;", (), 0, OK_SAYS),
    Scenario("site written as &#xA0;", "once", "&#xA0;", (), 0, OK_SAYS),
    Scenario("site written as &#160;", "once", "&#160;", (), 0, OK_SAYS),
    Scenario("site written as the raw character", "once", NBSP, (), 0, OK_SAYS),
    Scenario("no number-plus-unit site at all", "none", "&#xa0;", (), 1, NOT_FOUND),
    Scenario("the only site occurs twice", "twice", "&#xa0;", (), 1, NOT_FOUND),
    Scenario(
        "the only site occurs twice, in two spellings",
        "mixed",
        "&#xa0;",
        (),
        1,
        NOT_FOUND,
    ),
    Scenario(
        "the checker does not see the planted defect",
        "once",
        "&#xa0;",
        (("check_l10n_typography.py", _BLIND_RULE),),
        1,
        ONE_MORE,
    ),
    Scenario(
        "the checker sees the planted defect twice",
        "once",
        "&#xa0;",
        (("check_l10n_typography.py", _DOUBLE_RULE),),
        1,
        ONE_MORE,
    ),
    Scenario(
        "the checker's reader does not see numeric references",
        "once",
        "&#xa0;",
        (("check_catalogues.py", _BLIND_REFERENCES),),
        1,
        NOT_FOUND,
    ),
)
_BY_NAME = {s.name: s for s in SCENARIOS}


class Outcome(NamedTuple):
    code: int
    out: str


def _run(program: str, base: Path, scenario: Scenario) -> Outcome:
    """Run the step's shell line and its program in a root built for ``scenario``.

    The shell line is run with ``--surface catalogue`` added: the scratch root has no guide
    tree (the program's guide floor is then empty), and the guide rules of the checker are
    not what this module judges.
    """
    root = _build_root(base, scenario.kind, scenario.spelling, dict(scenario.patches))
    work = base / "w"
    shutil.rmtree(work, ignore_errors=True)
    (work / "l10n-typography").mkdir(parents=True)
    env = dict(os.environ, CI_TEMP_ROOT=str(work), PYTHONDONTWRITEBYTECODE="1")
    checker = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "check_l10n_typography.py"),
            "--surface",
            "catalogue",
            "--json",
        ],
        cwd=root,
        capture_output=True,
        env=env,
        timeout=120,
    )
    report = work / "l10n-typography" / "report.json"
    report.write_bytes(checker.stdout)
    program_file = work / "program.py"
    program_file.write_bytes(program.encode("utf-8"))
    done = subprocess.run(
        [sys.executable, "-I", str(program_file), str(report), str(checker.returncode)],
        cwd=root,
        capture_output=True,
        env=env,
        timeout=120,
    )
    text = done.stdout.decode("utf-8", "replace") + done.stderr.decode(
        "utf-8", "replace"
    )
    return Outcome(done.returncode, text)


def judge(program: str, base: Path, names: Optional[List[str]] = None) -> List[str]:
    """Violations of the control's contract over the named scenarios (all by default)."""
    problems: List[str] = []
    for scenario in SCENARIOS:
        if names is not None and scenario.name not in names:
            continue
        outcome = _run(program, base, scenario)
        if outcome.code != scenario.want_exit:
            problems.append(
                f"{scenario.name}: exit {outcome.code}, expected {scenario.want_exit}"
            )
        for phrase in scenario.must_say:
            if phrase not in outcome.out:
                problems.append(f"{scenario.name}: the output does not say {phrase!r}")
    return problems


# --------------------------------------------------------------------------- #
# Weakenings planted in memory (each must be reported by the scenarios named)
# --------------------------------------------------------------------------- #
class Weakening(NamedTuple):
    name: str
    old: str
    new: str
    caught_by: Tuple[str, ...]


WEAKENINGS: Tuple[Weakening, ...] = (
    Weakening(
        "control (ii) is never run",
        "\n\ncontrol_planted()\n",
        "\n\npass\n",
        (
            "no number-plus-unit site at all",
            "the checker does not see the planted defect",
        ),
    ),
    Weakening(
        "'exactly one' becomes 'at least one'",
        'if len(plant_row["findings"]) != len(base_row["findings"]) + 1 or sum(extra.values()) != 1:',
        'if len(plant_row["findings"]) < len(base_row["findings"]) + 1 or sum(extra.values()) < 1:',
        ("the checker sees the planted defect twice",),
    ),
    Weakening(
        "no extra finding is demanded at all",
        'if len(plant_row["findings"]) != len(base_row["findings"]) + 1 or sum(extra.values()) != 1:',
        "if False:",
        ("the checker does not see the planted defect",),
    ),
    Weakening(
        "'control site not found' becomes a note instead of a failure",
        'fail("control (ii): control site not found (no candidate whose',
        'print("control (ii): control site not found (no candidate whose',
        (
            "no number-plus-unit site at all",
            "the only site occurs twice, in two spellings",
        ),
    ),
    Weakening(
        "the numeric-reference spelling is no longer searched",
        'NBSP_FORMS = "(?:" + NBSP + "|&#(?:[xX]0*[aA]0|0*160);)"',
        'NBSP_FORMS = "(?:" + NBSP + ")"',
        ("site written as &#xa0;", "site written as &#xA0;", "site written as &#160;"),
    ),
)


def _weaken(program: str, weakening: Weakening) -> str:
    assert program.count(weakening.old) == 1, (
        f"the workflow no longer contains the single text this weakening replaces ({weakening.name!r}); "
        "update the weakening together with the workflow, do not drop it"
    )
    return program.replace(weakening.old, weakening.new)


# --------------------------------------------------------------------------- #
# The tests
# --------------------------------------------------------------------------- #
def test_the_workflow_has_exactly_one_typography_step_and_it_can_fail_the_job() -> None:
    steps = _typography_steps()
    assert (
        len(steps) == 1
    ), f"expected one step named {STEP_PREFIX!r}, found {len(steps)}"
    step = steps[0]
    assert (
        "continue-on-error" not in step
    ), "the typography step must not be continue-on-error"
    assert "scripts/check_l10n_typography.py --json" in step["run"]
    assert "control_planted()" in _program_of(
        step
    ), "control (ii) is no longer called by the step's program"


def test_the_real_program_meets_every_scenario(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    program = _program_of(_typography_steps()[0])
    base = tmp_path_factory.mktemp("tc")
    assert judge(program, base) == []


@pytest.mark.parametrize("weakening", WEAKENINGS, ids=[w.name for w in WEAKENINGS])
def test_a_planted_weakening_of_the_control_is_reported(
    weakening: Weakening, tmp_path_factory: pytest.TempPathFactory
) -> None:
    program = _program_of(_typography_steps()[0])
    weakened = _weaken(program, weakening)
    assert weakened != program
    for name in weakening.caught_by:
        assert name in _BY_NAME, f"unknown scenario {name!r} (the registry changed)"
    names = list(weakening.caught_by)
    base = tmp_path_factory.mktemp("tw")
    found = judge(weakened, base, names)
    assert found, f"the weakening {weakening.name!r} was not reported by any of {names}"
