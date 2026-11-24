"""No quality threshold of the pull request differs from the one it was cut from.

(REQ-L10N-BUILD-006, SC-L10N-BUILD-006-1: no threshold differs from the base.)

A release must not buy a green build by loosening the bar. Every threshold literal
below - the coverage gate's arguments, the per-test timeout, the frame budget, the
three contrast ratios, the font lint's limits and the access-key suffix pattern -
is read in two places and the two readings are compared:

* the HEAD of the pull request: the commit named by ``PULL_REQUEST_HEAD_SHA`` (CI
  sets it from the pull request's head commit; the checkout there is GitHub's
  merge ref, whose second parent is that head), else ``HEAD`` when run locally;
* the BASE: ``git merge-base <head> origin/main``.

Both are read with ``git show <sha>:<file>``, so the working tree's uncommitted
edits are never what is judged. A threshold that ``main`` changed through other
work and the branch took in moves the merge base with it, so it is not counted as
this pull request's change; a threshold the branch itself changed is. A literal
occurs in a file by content, never by line number, since lines move. A new place
that carries a threshold at a value already in use (one more pytest step with the
same timeout) is not a change; a value that disappears, appears or differs is.

The run prints the head and base shas, and every literal examined with both
readings. On ``main`` after the merge, head and base are the same commit and the
comparison is trivially equal; the run says so rather than hiding it.

Nothing here skips. An unresolvable head or base, a missing history, a literal
found at neither end, or zero literals examined each fail the run. Each failing
path is proved on throwaway repositories built from the repository's own files:
a lowered coverage bound, every literal changed at once, a change on ``main`` that
the branch did not make and one the branch took in, an unresolvable sha, and an
empty enumeration. Each literal's extraction pattern is also checked against the
values recorded at the merge of the visual-identity work.

The real repository is the checkout this file sits in; ``RELEASE_EVIDENCE_REPO``
points the real-repository cases at another one. Every read there is a git read.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import pytest

#: Repo root: testing/suites/release/test_gate_thresholds_unchanged.py -> parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]

#: Environment variable that points the real-repository cases at another checkout.
REPO_ENV = "RELEASE_EVIDENCE_REPO"
#: Environment variable CI sets from the pull request's head commit.
HEAD_ENV = "PULL_REQUEST_HEAD_SHA"
#: The ref the merge base is taken against.
MAIN_REF = "origin/main"

#: The merge of the visual-identity work: the commit at which every location and
#: expected value below was recorded. It is the same commit as ``BASE_MERGE_SHA``
#: in ``test_base_ancestry.py``; a test below keeps the two equal.
RECORDED_MERGE_SHA = "221e51d25577330584702ad70b8f69b3daddbe23"
SIBLING_MODULE = Path(__file__).with_name("test_base_ancestry.py")

FULL_SHA = re.compile(r"[0-9a-f]{40}")
GIT_TIMEOUT_S = 120

#: Git variables that would redirect a scratch repository to another one.
_GIT_REDIRECTS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
)

CI_WORKFLOW = ".github/workflows/ci.yml"
CONSTANTS = "pixelart_creator/logic/constants.py"
CONTRAST = "pixelart_creator/logic/contrast.py"
MNEMONIC_TEST = "testing/suites/ui/test_language_independent_mnemonics.py"
FONT_METRICS = "fonts-src/nifen-art/metrics.txt"


@dataclass(frozen=True)
class Threshold:
    """One threshold literal: where it lives, how to read it, what it reads as.

    ``pattern`` is applied to one line at a time and its groups are the value.
    ``expected`` is what the pattern reads at ``RECORDED_MERGE_SHA``: one entry per
    occurrence. ``skip_comments`` ignores YAML comment lines.
    """

    name: str
    path: str
    pattern: re.Pattern[str]
    expected: tuple[str, ...]
    skip_comments: bool = False


def _metric(key: str, value: str) -> Threshold:
    """A ``key = value`` line of the font metrics file, which the font lint reads."""
    return Threshold(
        name="font metrics " + key,
        path=FONT_METRICS,
        pattern=re.compile("^" + key + " = (.*)$"),
        expected=(value,),
    )


COVERAGE_BOUNDS = Threshold(
    "coverage gate --line/--branch",
    CI_WORKFLOW,
    re.compile(r"--line (\d+) --branch (\d+)"),
    ("90 80", "90 80"),
    skip_comments=True,
)
PER_TEST_TIMEOUT = Threshold(
    "per-test --timeout",
    CI_WORKFLOW,
    re.compile(r"--timeout=(\d+)"),
    ("120", "120"),
    skip_comments=True,
)
FRAME_BUDGET = Threshold(
    "FRAME_BUDGET_MS",
    CONSTANTS,
    re.compile(r"^FRAME_BUDGET_MS = (\d+)"),
    ("16",),
)
ACCESS_KEY_SUFFIX = Threshold(
    "access-key suffix pattern",
    MNEMONIC_TEST,
    re.compile(r"^_TRAILING_FALLBACK_SUFFIX = re\.compile\((.+)\)$"),
    ('r" \\([A-Za-z]\\)$"',),
)

THRESHOLDS: tuple[Threshold, ...] = (
    COVERAGE_BOUNDS,
    PER_TEST_TIMEOUT,
    FRAME_BUDGET,
    Threshold(
        "TEXT_MIN_RATIO",
        CONTRAST,
        re.compile(r"^TEXT_MIN_RATIO: float = (\d+\.\d+)"),
        ("4.5",),
    ),
    Threshold(
        "COMPONENT_MIN_RATIO",
        CONTRAST,
        re.compile(r"^COMPONENT_MIN_RATIO: float = (\d+\.\d+)"),
        ("3.0",),
    ),
    Threshold(
        "FOCUS_MIN_RATIO",
        CONTRAST,
        re.compile(r"^FOCUS_MIN_RATIO: float = (\d+\.\d+)"),
        ("3.0",),
    ),
    ACCESS_KEY_SUFFIX,
    _metric("em_px", "12"),
    _metric("units_per_px", "128"),
    _metric("units_per_em", "1536"),
    _metric("cell_adv_px", "12"),
    _metric("cell_ink_x_regular", "0..10"),
    _metric("cell_ink_x_bold", "0..11"),
    _metric("cell_ink_rows", "-1..9"),
    _metric("bold_shift_px", "1"),
    _metric("line_ascent_px", "11"),
    _metric("line_descent_px", "3"),
    _metric("line_gap_px", "0"),
    _metric("trim_max_px", "20"),
    _metric("small_kana_bottom_row", "-1"),
    _metric("small_kana_max_rows", "9"),
    _metric(
        "small_kana_left_cps",
        "U+30A1 U+30A3 U+30A5 U+30A7 U+30A9 U+30C3 U+30E3 U+30E5 U+30E7 U+30EE "
        "U+30F5 U+30F6",
    ),
    _metric("small_kana_ink_x_regular", "1..8"),
    _metric("small_kana_ink_x_bold", "1..9"),
    _metric(
        "small_kana_centred_cps",
        "U+3041 U+3043 U+3045 U+3047 U+3049 U+3063 U+3083 U+3085 U+3087 U+308E "
        "U+3095 U+3096",
    ),
    _metric("small_kana_centre_x2", "12"),
    _metric("small_kana_centre_tol_x2", "1"),
    _metric("small_kana_bold_extra_x2", "1"),
    _metric("small_kana_centred_max_cols", "9"),
)


# --- git ------------------------------------------------------------------------


def _git(
    repo: Path, *args: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``git -C repo ...`` and return the finished process (no exception)."""
    env = {k: v for k, v in os.environ.items() if k not in _GIT_REDIRECTS}
    env["GIT_TERMINAL_PROMPT"] = "0"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=GIT_TIMEOUT_S,
        check=False,
    )


def _ok(done: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    """Return a scratch-repository git call that must have succeeded."""
    assert done.returncode == 0, "scratch git failed: %s %s" % (
        done.args,
        done.stderr.strip(),
    )
    return done


class EvidenceError(Exception):
    """The history needed to compare cannot be read; the comparison has no answer."""


def resolve_commit(repo: Path, rev: str) -> str | None:
    """The full sha of the commit ``rev`` names in ``repo``, or None."""
    if not rev or rev.startswith("-"):
        return None
    done = _git(repo, "rev-parse", "--verify", "--quiet", rev + "^{commit}")
    sha = done.stdout.strip()
    if done.returncode == 0 and FULL_SHA.fullmatch(sha):
        return sha
    return None


def _is_shallow(repo: Path) -> bool:
    done = _git(repo, "rev-parse", "--is-shallow-repository")
    return done.stdout.strip() == "true"


def determine_head(repo: Path, environ: Mapping[str, str]) -> tuple[str, str]:
    """The head to judge and where it came from; an unresolvable one raises.

    The variable named by ``HEAD_ENV`` wins when it is set and not blank; a blank
    value counts as unset, as it is on a CI event that has no pull request.
    """
    named = environ.get(HEAD_ENV, "").strip()
    if named:
        sha = resolve_commit(repo, named)
        if sha is None:
            raise EvidenceError(
                "%s=%r does not name a commit in this clone (the head commit of "
                "the pull request cannot be read; the clone may be shallow)"
                % (HEAD_ENV, named)
            )
        return sha, "environment variable " + HEAD_ENV
    sha = resolve_commit(repo, "HEAD")
    if sha is None:
        raise EvidenceError("HEAD does not name a commit in %s" % repo)
    return sha, "HEAD"


def determine_base(repo: Path, head: str) -> str:
    """``git merge-base <head> origin/main``; an unresolvable base raises."""
    shallow = " The clone is SHALLOW." if _is_shallow(repo) else ""
    if resolve_commit(repo, MAIN_REF) is None:
        raise EvidenceError(
            "%s does not exist in this clone, so there is no base to compare "
            "with.%s" % (MAIN_REF, shallow)
        )
    done = _git(repo, "merge-base", head, MAIN_REF)
    base = done.stdout.strip()
    if done.returncode != 0 or not FULL_SHA.fullmatch(base):
        raise EvidenceError(
            "no merge base of %s and %s could be found.%s %s"
            % (head, MAIN_REF, shallow, done.stderr.strip())
        )
    return base


def read_at(repo: Path, sha: str, path: str) -> str | None:
    """The text of ``path`` at commit ``sha`` (LF line endings), or None."""
    done = _git(repo, "show", sha + ":" + path)
    if done.returncode != 0:
        return None
    return done.stdout.replace("\r\n", "\n")


# --- reading and comparing the literals ------------------------------------------


def extract(text: str, threshold: Threshold) -> tuple[str, ...]:
    """Every reading of ``threshold`` in ``text``, one per matching line."""
    found: list[str] = []
    for line in text.split("\n"):
        if threshold.skip_comments and line.lstrip().startswith("#"):
            continue
        match = threshold.pattern.search(line)
        if match:
            found.append(" ".join(group.strip() for group in match.groups()))
    return tuple(found)


def judge(base: Sequence[str], head: Sequence[str]) -> tuple[str, ...]:
    """The differences between the base's readings and the head's."""
    if not base and not head:
        return ("found at neither end: the file or the pattern has gone",)
    if not base:
        return ("absent at the base, present at the head: %s" % (list(head),),)
    if not head:
        return ("present at the base %s, gone at the head" % (list(base),),)
    at_base, at_head = Counter(base), Counter(head)
    problems = []
    for value, count in at_base.items():
        if at_head[value] < count:
            problems.append(
                "%r occurs %d time(s) at the base and %d at the head"
                % (value, count, at_head[value])
            )
    for value in at_head:
        if value not in at_base:
            problems.append("a value not present at the base: %r" % (value,))
    return tuple(problems)


@dataclass(frozen=True)
class Row:
    """One threshold's two readings and the differences between them."""

    threshold: Threshold
    base: tuple[str, ...]
    head: tuple[str, ...]
    problems: tuple[str, ...]


def compare(
    repo: Path, head: str, base: str, thresholds: Sequence[Threshold]
) -> list[Row]:
    """Read every threshold at ``head`` and at ``base`` and judge each pair."""
    cache: dict[tuple[str, str], str] = {}

    def text_of(sha: str, path: str) -> str:
        key = (sha, path)
        if key not in cache:
            cache[key] = read_at(repo, sha, path) or ""
        return cache[key]

    rows = []
    for threshold in thresholds:
        at_base = extract(text_of(base, threshold.path), threshold)
        at_head = extract(text_of(head, threshold.path), threshold)
        rows.append(Row(threshold, at_base, at_head, judge(at_base, at_head)))
    return rows


def verdict(rows: Sequence[Row]) -> list[str]:
    """Every reason the comparison fails; empty when it passes."""
    failures = []
    if not any(row.base or row.head for row in rows):
        failures.append("zero threshold literals were examined")
    for row in rows:
        for problem in row.problems:
            failures.append(
                "%s (%s): %s" % (row.threshold.name, row.threshold.path, problem)
            )
    return failures


def report(repo: Path, head: str, source: str, base: str, rows: Sequence[Row]) -> str:
    """The printable account of a comparison: shas, every literal, both values."""
    lines = [
        "thresholds repo=%s" % repo,
        "head = %s (%s)" % (head, source),
        "base = %s (merge base of the head and %s)" % (base, MAIN_REF),
    ]
    if head == base:
        lines.append(
            "head and base are the same commit: the comparison is trivially equal"
        )
    for row in rows:
        state = "DIFFERS" if row.problems else "same"
        lines.append(
            "  [%s] %s | %s | base=%s head=%s"
            % (
                state,
                row.threshold.name,
                row.threshold.path,
                list(row.base),
                list(row.head),
            )
        )
        if not row.problems and len(row.base) != len(row.head):
            lines.append(
                "      note: %d occurrence(s) at the base, %d at the head, "
                "every value already in use" % (len(row.base), len(row.head))
            )
    examined = sum(1 for row in rows if row.base or row.head)
    lines.append("literals examined: %d of %d" % (examined, len(rows)))
    return "\n".join(lines)


def mutate_first(text: str, threshold: Threshold) -> str:
    """``text`` with the first reading of ``threshold`` changed (a '9' appended)."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if threshold.skip_comments and line.lstrip().startswith("#"):
            continue
        match = threshold.pattern.search(line)
        if match:
            end = match.end(1)
            lines[index] = line[:end] + "9" + line[end:]
            return "\n".join(lines)
    raise AssertionError("no reading of %s in its file" % threshold.name)


def edit_code(text: str, old: str, new: str) -> str:
    """``text`` with ``old`` replaced by ``new`` on the first non-comment line."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if old in line and not line.lstrip().startswith("#"):
            lines[index] = line.replace(old, new, 1)
            return "\n".join(lines)
    raise AssertionError("%r is on no code line" % (old,))


def lower_coverage(files: Mapping[str, str]) -> dict[str, str]:
    """A copy of ``files`` whose coverage gate asks for 89 % line coverage, not 90."""
    lowered = dict(files)
    lowered[CI_WORKFLOW] = edit_code(files[CI_WORKFLOW], "--line 90", "--line 89")
    return lowered


def _repo_under_test() -> Path:
    override = os.environ.get(REPO_ENV)
    return Path(override) if override else REPO_ROOT


# --- the enumeration -------------------------------------------------------------


def test_the_enumeration_holds_every_listed_threshold_once():
    names = [t.name for t in THRESHOLDS]
    print("thresholds enumerated: %d" % len(names))
    assert len(names) == len(set(names)), "a threshold is listed twice"
    paths = {t.path for t in THRESHOLDS}
    assert paths == {
        CI_WORKFLOW,
        CONSTANTS,
        CONTRAST,
        MNEMONIC_TEST,
        FONT_METRICS,
    }
    assert [t.name for t in THRESHOLDS if t.path == CI_WORKFLOW] == [
        COVERAGE_BOUNDS.name,
        PER_TEST_TIMEOUT.name,
    ]
    assert [t.name for t in THRESHOLDS if t.path == CONTRAST] == [
        "TEXT_MIN_RATIO",
        "COMPONENT_MIN_RATIO",
        "FOCUS_MIN_RATIO",
    ]
    assert sum(1 for t in THRESHOLDS if t.path == FONT_METRICS) == 22
    assert len(THRESHOLDS) == 29
    for threshold in THRESHOLDS:
        assert threshold.pattern.groups >= 1, threshold.name
        assert threshold.expected, threshold.name


def test_the_recorded_merge_is_the_one_the_ancestry_test_records():
    text = SIBLING_MODULE.read_text(encoding="utf-8")
    found = re.findall(r'^BASE_MERGE_SHA = "([0-9a-f]{40})"', text, flags=re.M)
    print(
        "ancestry module records %s; this module records %s"
        % (found, [RECORDED_MERGE_SHA])
    )
    assert found == [RECORDED_MERGE_SHA]


# --- the real repository ----------------------------------------------------------


def test_the_patterns_read_the_recorded_values_at_the_recorded_merge():
    repo = _repo_under_test()
    sha = resolve_commit(repo, RECORDED_MERGE_SHA)
    if sha is None:
        pytest.fail(
            "the recorded merge %s is not in %s%s: the extraction patterns "
            "cannot be checked"
            % (
                RECORDED_MERGE_SHA,
                repo,
                " (the clone is SHALLOW)" if _is_shallow(repo) else "",
            ),
            pytrace=False,
        )
    mismatches = []
    for threshold in THRESHOLDS:
        text = read_at(repo, sha, threshold.path)
        read = extract(text or "", threshold)
        print("  %s | %s | read=%s" % (threshold.name, threshold.path, list(read)))
        if read != threshold.expected:
            mismatches.append(
                "%s (%s): expected %s, read %s"
                % (threshold.name, threshold.path, list(threshold.expected), list(read))
            )
    print("patterns checked at %s: %d" % (sha, len(THRESHOLDS)))
    assert not mismatches, "\n".join(mismatches)


def test_no_threshold_differs_from_the_merge_base():
    repo = _repo_under_test()
    try:
        head, source = determine_head(repo, os.environ)
        base = determine_base(repo, head)
    except EvidenceError as error:
        pytest.fail(str(error), pytrace=False)
    rows = compare(repo, head, base, THRESHOLDS)
    print(report(repo, head, source, base, rows))
    failures = verdict(rows)
    assert not failures, "\n".join(failures)


# --- throwaway repositories built from the repository's own files -----------------


def _init(path: Path) -> Path:
    """A new empty repository with no hooks, a neutral identity and no signing."""
    path.mkdir(parents=True)
    hooks = path.with_name(path.name + "-hooks")
    hooks.mkdir()
    _ok(_git(path, "init", "-q"))
    for key, value in (
        ("user.name", "Release Evidence"),
        ("user.email", "evidence@example.invalid"),
        ("commit.gpgsign", "false"),
        ("core.autocrlf", "false"),
        ("core.hooksPath", str(hooks)),
    ):
        _ok(_git(path, "config", key, value))
    return path


def _commit_files(repo: Path, files: Mapping[str, str], message: str) -> str:
    """Write ``files``, commit everything and return the new commit's sha."""
    for name, text in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    _ok(_git(repo, "add", "-A"))
    _ok(_git(repo, "commit", "-q", "-m", "scratch: " + message))
    return _ok(_git(repo, "rev-parse", "HEAD")).stdout.strip()


def _point_main_at(repo: Path, sha: str) -> None:
    _ok(_git(repo, "update-ref", "refs/remotes/origin/main", sha))


@pytest.fixture(scope="module")
def real_files() -> dict[str, str]:
    """Every file a threshold lives in, as the real repository's HEAD holds it."""
    repo = _repo_under_test()
    sha = resolve_commit(repo, "HEAD")
    assert sha, "the real repository has no HEAD commit"
    files = {}
    for path in sorted({t.path for t in THRESHOLDS}):
        text = read_at(repo, sha, path)
        assert text is not None, "%s is not in the real repository at %s" % (path, sha)
        files[path] = text
    return files


def _fork(tmp_path: Path, real_files: Mapping[str, str]) -> tuple[Path, str]:
    """A scratch repository holding the real files, with ``origin/main`` at them."""
    repo = _init(tmp_path / "scratch")
    base = _commit_files(repo, real_files, "the files as the base holds them")
    _point_main_at(repo, base)
    return repo, base


def test_a_lowered_coverage_bound_is_reported(tmp_path: Path, real_files):
    repo, base = _fork(tmp_path, real_files)
    assert "--line 90 --branch 80" in real_files[CI_WORKFLOW]
    lowered = lower_coverage(real_files)
    head = _commit_files(repo, lowered, "the branch lowers one bound")
    assert determine_base(repo, head) == base
    rows = compare(repo, head, base, THRESHOLDS)
    print(report(repo, head, "scratch", base, rows))
    failures = verdict(rows)
    assert failures, "a lowered coverage bound was not noticed"
    assert all(COVERAGE_BOUNDS.name in failure for failure in failures), failures
    assert any("89 80" in failure for failure in failures), failures


def test_every_literal_changed_at_once_is_reported_literal_by_literal(
    tmp_path: Path, real_files
):
    repo, base = _fork(tmp_path, real_files)
    changed = dict(real_files)
    for threshold in THRESHOLDS:
        changed[threshold.path] = mutate_first(changed[threshold.path], threshold)
    assert changed != dict(real_files)
    head = _commit_files(repo, changed, "the branch changes every literal")
    rows = compare(repo, head, base, THRESHOLDS)
    failures = verdict(rows)
    unnoticed = [
        row.threshold.name
        for row in rows
        if not any(row.threshold.name + " (" in failure for failure in failures)
    ]
    print("literals changed: %d, unnoticed: %s" % (len(rows), unnoticed))
    assert unnoticed == []


def test_a_change_on_main_that_the_branch_did_not_take_is_not_counted(
    tmp_path: Path, real_files
):
    repo, base = _fork(tmp_path, real_files)
    default = _ok(_git(repo, "rev-parse", "--abbrev-ref", "HEAD")).stdout.strip()
    # main moves on after the branch was cut: it changes the frame budget.
    _ok(_git(repo, "checkout", "-q", "-b", "main-moves", base))
    moved = dict(real_files)
    moved[CONSTANTS] = mutate_first(real_files[CONSTANTS], FRAME_BUDGET)
    tip = _commit_files(repo, moved, "main changes the frame budget")
    _point_main_at(repo, tip)
    # the branch, cut from the earlier base, changes only a coverage bound.
    _ok(_git(repo, "checkout", "-q", default))
    lowered = lower_coverage(real_files)
    head = _commit_files(repo, lowered, "the branch lowers one bound")
    merge_base = determine_base(repo, head)
    assert merge_base == base and merge_base != tip
    rows = compare(repo, head, merge_base, THRESHOLDS)
    print(report(repo, head, "scratch", merge_base, rows))
    failures = verdict(rows)
    assert any(COVERAGE_BOUNDS.name in failure for failure in failures), failures
    assert not any(FRAME_BUDGET.name in failure for failure in failures), failures


def test_a_change_on_main_that_the_branch_took_in_is_not_counted(
    tmp_path: Path, real_files
):
    repo, base = _fork(tmp_path, real_files)
    default = _ok(_git(repo, "rev-parse", "--abbrev-ref", "HEAD")).stdout.strip()
    _ok(_git(repo, "checkout", "-q", "-b", "main-moves", base))
    moved = dict(real_files)
    moved[CONSTANTS] = mutate_first(real_files[CONSTANTS], FRAME_BUDGET)
    tip = _commit_files(repo, moved, "main changes the frame budget")
    _point_main_at(repo, tip)
    # the branch changes a coverage bound, then takes main's change in by a merge.
    _ok(_git(repo, "checkout", "-q", default))
    lowered = lower_coverage(real_files)
    _commit_files(repo, lowered, "the branch lowers one bound")
    _ok(
        _git(
            repo,
            "merge",
            "-q",
            "--no-ff",
            "-m",
            "scratch: take main in",
            tip,
            env_extra={"GIT_MERGE_AUTOEDIT": "no"},
        )
    )
    head = resolve_commit(repo, "HEAD")
    assert head
    merge_base = determine_base(repo, head)
    assert merge_base == tip, "taking main in must move the merge base to main"
    rows = compare(repo, head, merge_base, THRESHOLDS)
    print(report(repo, head, "scratch", merge_base, rows))
    failures = verdict(rows)
    assert any(COVERAGE_BOUNDS.name in failure for failure in failures), failures
    assert not any(FRAME_BUDGET.name in failure for failure in failures), failures


def test_a_new_place_carrying_a_value_already_in_use_is_not_a_change(
    tmp_path: Path, real_files
):
    repo, base = _fork(tmp_path, real_files)
    more = dict(real_files)
    more[CI_WORKFLOW] = real_files[CI_WORKFLOW] + "      - run: pytest --timeout=120\n"
    head = _commit_files(repo, more, "the branch adds a step with the same timeout")
    rows = compare(repo, head, base, THRESHOLDS)
    timeout = [row for row in rows if row.threshold is PER_TEST_TIMEOUT][0]
    print(report(repo, head, "scratch", base, rows))
    assert len(timeout.head) == len(timeout.base) + 1
    assert verdict(rows) == []


def test_a_threshold_dropped_from_a_step_is_reported(tmp_path: Path, real_files):
    repo, base = _fork(tmp_path, real_files)
    fewer = dict(real_files)
    fewer[CI_WORKFLOW] = edit_code(real_files[CI_WORKFLOW], "--timeout=120", "")
    head = _commit_files(repo, fewer, "the branch removes one timeout")
    failures = verdict(compare(repo, head, base, THRESHOLDS))
    print(failures)
    assert any(PER_TEST_TIMEOUT.name in failure for failure in failures), failures


def test_an_identical_head_and_base_is_reported_as_trivially_equal(
    tmp_path: Path, real_files
):
    repo, base = _fork(tmp_path, real_files)
    rows = compare(repo, base, base, THRESHOLDS)
    text = report(repo, base, "HEAD", base, rows)
    print(text)
    assert verdict(rows) == []
    assert "trivially equal" in text
    assert "literals examined: %d of %d" % (len(THRESHOLDS), len(THRESHOLDS)) in text
    different = report(repo, base, "HEAD", "0" * 40, rows)
    assert "trivially equal" not in different


def test_an_unresolvable_head_fails(tmp_path: Path, real_files):
    repo, base = _fork(tmp_path, real_files)
    for named in ("0" * 40, "no-such-branch", "-x"):
        with pytest.raises(EvidenceError) as caught:
            determine_head(repo, {HEAD_ENV: named})
        assert HEAD_ENV in str(caught.value)


def test_the_head_variable_wins_and_a_blank_one_means_head(tmp_path: Path, real_files):
    repo, base = _fork(tmp_path, real_files)
    lowered = lower_coverage(real_files)
    later = _commit_files(repo, lowered, "a later commit")
    assert determine_head(repo, {HEAD_ENV: base}) == (
        base,
        "environment variable " + HEAD_ENV,
    )
    assert determine_head(repo, {HEAD_ENV: "  "}) == (later, "HEAD")
    assert determine_head(repo, {}) == (later, "HEAD")


def test_an_unresolvable_base_fails(tmp_path: Path):
    repo = _init(tmp_path / "no-main")
    head = _commit_files(repo, {"one.txt": "one\n"}, "a commit with no main")
    with pytest.raises(EvidenceError) as caught:
        determine_base(repo, head)
    assert MAIN_REF in str(caught.value)


def test_unrelated_histories_have_no_merge_base_and_fail(tmp_path: Path):
    repo = _init(tmp_path / "unrelated")
    first = _commit_files(repo, {"one.txt": "one\n"}, "the first root")
    _ok(_git(repo, "checkout", "-q", "--orphan", "other"))
    _ok(_git(repo, "rm", "-q", "-rf", "."))
    second = _commit_files(repo, {"two.txt": "two\n"}, "a second root")
    _point_main_at(repo, first)
    with pytest.raises(EvidenceError) as caught:
        determine_base(repo, second)
    assert "no merge base" in str(caught.value)


def test_zero_literals_examined_fails(tmp_path: Path, real_files):
    repo, base = _fork(tmp_path, real_files)
    failures = verdict(compare(repo, base, base, ()))
    assert failures == ["zero threshold literals were examined"]


def test_literals_found_at_neither_end_fail(tmp_path: Path):
    repo = _init(tmp_path / "empty-files")
    head = _commit_files(repo, {"readme.txt": "no thresholds here\n"}, "no files")
    _point_main_at(repo, head)
    rows = compare(repo, head, head, THRESHOLDS)
    failures = verdict(rows)
    print(failures[:3])
    assert failures[0] == "zero threshold literals were examined"
    assert len(failures) == 1 + len(THRESHOLDS)
    assert all("found at neither end" in failure for failure in failures[1:])


def test_a_shallow_clone_without_the_main_ref_fails_naming_the_shallow_history(
    tmp_path: Path, real_files
):
    repo, base = _fork(tmp_path, real_files)
    lowered = lower_coverage(real_files)
    _commit_files(repo, lowered, "the branch lowers one bound")
    hooks = tmp_path / "shallow-hooks"
    hooks.mkdir()
    shallow = tmp_path / "shallow"
    _ok(
        _git(
            tmp_path,
            "-c",
            "core.hooksPath=" + str(hooks),
            "clone",
            "-q",
            "--depth",
            "1",
            "--no-checkout",
            repo.as_uri(),
            str(shallow),
        )
    )
    # A shallow clone made by a fetch that took one branch has no origin/main to
    # compare with. Whatever the clone's own default branch is called, remove any
    # ref of that name, so the case is the same on every git configuration.
    _git(shallow, "update-ref", "-d", "refs/remotes/origin/main")
    assert _is_shallow(shallow)
    head = resolve_commit(shallow, "HEAD")
    assert head
    with pytest.raises(EvidenceError) as caught:
        determine_base(shallow, head)
    message = str(caught.value)
    print(message)
    assert MAIN_REF in message
    assert "SHALLOW" in message
