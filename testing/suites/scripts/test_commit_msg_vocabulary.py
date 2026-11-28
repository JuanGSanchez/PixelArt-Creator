"""Contract tests for the vocabulary half of ``.githooks/commit-msg``.

The hook is a shell script, so nothing short of git itself can run it the way
git does. Every control below is a REAL ``git commit`` in a throwaway
repository under ``tmp_path`` (never the working tree this suite ships in),
whose ``core.hooksPath`` points at a copy of the shipped hook and which carries
copies of the two gate scripts the hook calls. The hook runs under whatever
``sh`` git provides -- Git for Windows' on Windows -- so the same module
exercises all three operating systems.

What is pinned, and why each piece is its own control:

* the planted controls (``test_planted_controls``): one message per family the
  pull-request check rejects, each refused with the family and the offending
  token named; look-alike and clean messages accepted; an attribution-trailer
  message still refused by the attribution half. The run PRINTS how many
  messages it examined and how many it refused, and fails when it examined
  none -- a matrix that ran nothing must never read as green;
* parity with the pull-request check (``test_hook_verdict_equals_...``): the
  hook and the range mode of ``scripts/check_vocabulary_regrowth.py`` give the
  same verdict on the same message. The hook shares that script's patterns, so
  a lowercase or separator variant that the pull-request check lets through is
  let through here too -- pinned, not assumed;
* the mode of the script that serves the hook (``--message-file``), driven
  directly;
* the hook's own mechanics: a stub gate that always passes shows the refusal
  comes from the vocabulary gate and from nothing else; a missing gate refuses
  loudly instead of passing; the shipped file is tracked executable, because a
  hook git does not consider executable is silently skipped on Linux and macOS.

NOTE ON THIS FILE'S OWN SOURCE: it is scanned by the vocabulary gate like any
other tracked file, so every planted token is assembled at run time by
``_t(prefix, suffix)`` and never written intact -- and the attribution trailer
is assembled from fragments for the same reason. The last controls in the
module scan this file and the hook for exactly that.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

import pytest

from .conftest import REPO_ROOT, SCRIPTS_DIR

HOOK = REPO_ROOT / ".githooks" / "commit-msg"
GATE = "check_vocabulary_regrowth.py"
ATTRIBUTION_GATE = "check_attribution.py"
THIS_MODULE = "testing/suites/scripts/test_commit_msg_vocabulary.py"


def _t(prefix: str, suffix: str) -> str:
    """Join two fragments at run time, so no intact token sits in this file."""
    return prefix + suffix


# (the family's own name as the gate reports it, one planted token)
FAMILIES: List[Tuple[str, str]] = [
    ("AGT-nn", _t("AGT", "-12")),
    ("REC-n", _t("REC", "-3")),
    (_t("OQ", "-n"), _t("OQ", "-2")),
    ("T-nn(bare)", _t("T", "-12")),
    ("DEV-n", _t("DEV", "-4")),
    ("WP-n", _t("WP", "-7")),
    (_t("design", "-docs"), _t("design", "-docs")),
    (_t("subagent", "-report"), _t("subagent", "-report")),
]


def _trailer() -> str:
    """An AI co-author trailer, assembled from fragments (never a literal)."""
    return (
        "Co-Authored-By: "
        + _t("Clau", "de")
        + " <noreply@"
        + _t("anthropi", "c.com")
        + ">"
    )


def _message(body: str) -> str:
    return "feat(ci): wire the check\n\n" + body + "\n"


class Case(NamedTuple):
    cid: str
    message: str
    vocabulary: bool  # the vocabulary gate refuses it
    attribution: bool  # the attribution gate refuses it
    expect: Tuple[str, ...]  # strings the refusal's stderr must carry
    forbid: Tuple[str, ...]  # strings it must NOT carry


def _build_cases() -> List[Case]:
    cases: List[Case] = []
    for label, token in FAMILIES:
        cases.append(
            Case(
                "family " + label,
                _message("The change follows " + token + " in the plan."),
                True,
                False,
                ("vocabulary gate", "pattern=" + label, token),
                ("attribution gate",),
            )
        )
    cases.append(
        Case(
            "family in the subject line",
            "fix: handle " + FAMILIES[0][1] + " better\n",
            True,
            False,
            ("vocabulary gate", "pattern=" + FAMILIES[0][0], FAMILIES[0][1]),
            ("attribution gate",),
        )
    )
    # The pull-request check is case-sensitive and anchored on the hyphen. The
    # hook shares its patterns, so these pass in both: the parity control below
    # proves that against the real range mode rather than assuming it.
    variants = [
        ("lowercase", _t("agt", "-12")),
        ("underscore", _t("AGT", "_12")),
        ("space", _t("AGT", " 12")),
        ("joined", _t("AGT", "12")),
        ("title case", "Design" + "-Docs"),
        ("inside a longer word", _t("XAGT", "-12")),
    ]
    for name, text in variants:
        cases.append(
            Case(
                "variant " + name,
                _message("Mentions " + text + " once."),
                False,
                False,
                (),
                (),
            )
        )
    clean = [
        ("clean subject only", "docs: describe the translation catalogue\n"),
        (
            "clean subject and body",
            _message("Adds the Korean catalogue.\n\nSecond paragraph, no ids."),
        ),
        ("clean look-alikes", _message("Fix the T-shirt icon and the UTF-8 label.")),
    ]
    for name, text in clean:
        cases.append(Case(name, text, False, False, (), ()))
    cases.append(
        Case(
            "attribution trailer only",
            _message("Body.\n\n" + _trailer()),
            False,
            True,
            ("attribution gate",),
            ("vocabulary gate",),
        )
    )
    cases.append(
        Case(
            "attribution trailer and a family",
            _message("Follows " + FAMILIES[1][1] + ".\n\n" + _trailer()),
            True,
            True,
            ("attribution gate", "vocabulary gate", FAMILIES[1][1]),
            (),
        )
    )
    return cases


CASES = _build_cases()


# --------------------------------------------------------------------------- #
# A throwaway repository wired to the shipped hook.
# --------------------------------------------------------------------------- #
def _clean_env(config_file: Path) -> Dict[str, str]:
    """The ambient environment minus every GIT_* variable, with git pinned to
    an empty global config (no user hooks path, signing or comment character)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = str(config_file)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


class Outcome(NamedTuple):
    returncode: int
    stderr: str
    created: int  # commits the attempt added

    @property
    def refused(self) -> bool:
        return self.returncode != 0 and self.created == 0

    @property
    def accepted(self) -> bool:
        return self.returncode == 0 and self.created == 1


class Scratch:
    """One scratch repository and the git calls made in it."""

    def __init__(self, root: Path, gate: str = "real") -> None:
        """`gate` is "real" (the shipped script) or "stub" (one that always
        passes), copied beside the attribution gate the hook also calls."""
        self.root = root
        self.work = root / "work"
        self.work.mkdir(parents=True)
        config = root / "gitconfig"
        config.write_bytes(b"")
        self.env = _clean_env(config)
        self.git("init", "-q", str(self.work))
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", ".githooks")
        hooks = self.work / ".githooks"
        hooks.mkdir()
        shutil.copyfile(str(HOOK), str(hooks / "commit-msg"))
        # Installed executable HERE so that these controls test the hook's logic
        # on every operating system; the shipped file's own mode is the subject
        # of test_the_hook_is_tracked_executable, not of the scratch copy.
        (hooks / "commit-msg").chmod(0o755)
        scripts = self.work / "scripts"
        scripts.mkdir()
        shutil.copyfile(
            str(SCRIPTS_DIR / ATTRIBUTION_GATE), str(scripts / ATTRIBUTION_GATE)
        )
        if gate == "real":
            shutil.copyfile(str(SCRIPTS_DIR / GATE), str(scripts / GATE))
        elif gate == "stub":
            (scripts / GATE).write_bytes(b"import sys\nsys.exit(0)\n")
        else:
            raise ValueError(gate)
        (self.work / "README.md").write_bytes(b"# scratch\n")
        self.git("add", "--", "README.md")
        first = self.commit_file("chore: create the repository\n")
        assert first.accepted, first.stderr

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        done = subprocess.run(
            ["git", "-C", str(self.work), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self.env,
            timeout=120,
        )
        if check and done.returncode != 0:
            raise AssertionError(
                "git %s failed: %s%s" % (" ".join(args), done.stdout, done.stderr)
            )
        return done

    def count(self) -> int:
        out = self.git("rev-list", "--count", "HEAD", check=False)
        return int(out.stdout.strip()) if out.returncode == 0 else 0

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def commit_file(self, message: str, *extra: str) -> Outcome:
        """Commit (allow-empty) with the message read from a file, as git does
        for `-F`. Returns what happened; never raises on a refusal."""
        before = self.count()
        msg = self.root / "message.txt"
        msg.write_bytes(message.encode("utf-8"))
        done = self.git("commit", "--allow-empty", "-F", str(msg), *extra, check=False)
        return Outcome(done.returncode, done.stderr, self.count() - before)


@pytest.fixture(scope="module")
def scratch(tmp_path_factory: pytest.TempPathFactory) -> Scratch:
    return Scratch(tmp_path_factory.mktemp("hook_real"))


def _gate(args: List[str], env: Optional[Dict[str, str]] = None):
    """Run the gate script as a subprocess; returns CompletedProcess[str]."""
    run_env = env
    if run_env is None:
        run_env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / GATE), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=run_env,
        timeout=60,
    )


# --------------------------------------------------------------------------- #
# The planted controls, and parity with the pull-request check.
# --------------------------------------------------------------------------- #
def test_planted_controls(scratch: Scratch) -> None:
    """Every case is driven through a real commit; the verdicts are printed."""
    examined = refused = accepted = 0
    wrong: List[str] = []
    for case in CASES:
        outcome = scratch.commit_file(case.message)
        examined += 1
        expected_refusal = case.vocabulary or case.attribution
        if outcome.refused:
            refused += 1
        elif outcome.accepted:
            accepted += 1
        else:
            wrong.append(
                "%s: exit %d with %d commit(s) added"
                % (case.cid, outcome.returncode, outcome.created)
            )
            continue
        verdict = "refused" if outcome.refused else "accepted"
        print("  %-40s -> %s" % (case.cid, verdict))
        if outcome.refused != expected_refusal:
            wanted = "refused" if expected_refusal else "accepted"
            wrong.append("%s: expected %s, got %s" % (case.cid, wanted, verdict))
            continue
        for needle in case.expect:
            if needle not in outcome.stderr:
                wrong.append("%s: stderr lacks %r" % (case.cid, needle))
        for needle in case.forbid:
            if needle in outcome.stderr:
                wrong.append("%s: stderr carries %r" % (case.cid, needle))
    print(
        "commit-msg planted controls: examined %d, refused %d, accepted %d"
        % (examined, refused, accepted)
    )
    assert examined > 0, "examined 0 messages: a run of nothing is not green"
    assert examined == len(CASES)
    assert refused == sum(1 for c in CASES if c.vocabulary or c.attribution)
    assert not wrong, "\n".join(wrong)


def test_a_refused_message_leaves_the_history_alone(scratch: Scratch) -> None:
    before = scratch.head()
    outcome = scratch.commit_file(_message("Follows " + FAMILIES[0][1] + "."))
    assert outcome.refused, outcome.stderr
    assert scratch.head() == before


def test_hook_verdict_equals_the_pull_request_check(tmp_path: Path) -> None:
    """For every case, the range mode run over the commit that carries the
    message gives the verdict the hook gave. The commit is made with the hook
    bypassed, so a message the hook refuses can still be put in front of the
    range mode."""
    repo = Scratch(tmp_path / "parity")
    checked = 0
    for case in CASES:
        base = repo.head()
        done = repo.commit_file(case.message, "--no-verify")
        assert done.accepted, done.stderr
        result = _gate(
            ["--root", str(repo.work), "--base-sha", base, "--head-sha", "HEAD"],
            env=repo.env,
        )
        assert result.returncode in (0, 1), (case.cid, result.stderr)
        payload = json.loads(result.stdout)
        assert payload["scanned"]["commit_messages_examined"] == 1, case.cid
        assert (result.returncode == 1) == case.vocabulary, (
            case.cid,
            result.returncode,
            result.stderr,
        )
        checked += 1
    print("range-mode parity: checked %d message(s)" % checked)
    assert checked == len(CASES) > 0


def test_a_comment_line_is_not_scanned_because_git_strips_it(tmp_path: Path) -> None:
    """With the cleanup mode that removes commentary, the leaked-looking line
    never reaches the commit, so refusing it would refuse text that does not
    exist downstream. Under a mode that keeps it, the range mode and the
    pre-push scan catch it afterwards (the residual the attribution gate also
    records)."""
    repo = Scratch(tmp_path / "comment")
    outcome = repo.commit_file(
        _message("Body.\n\n# " + FAMILIES[0][1] + " is only commentary."),
        "--cleanup=strip",
    )
    assert outcome.accepted, outcome.stderr
    stored = repo.git("log", "-1", "--format=%B").stdout
    assert FAMILIES[0][1] not in stored


# --------------------------------------------------------------------------- #
# The hook's own mechanics.
# --------------------------------------------------------------------------- #
def test_the_refusal_comes_from_the_vocabulary_gate(tmp_path: Path) -> None:
    """With the gate replaced by a stub that always passes, a planted family is
    accepted: the refusal in the matrix is the vocabulary gate's and nothing
    else's. (A control that cannot fail would prove nothing.)"""
    repo = Scratch(tmp_path / "stub", gate="stub")
    outcome = repo.commit_file(_message("Follows " + FAMILIES[0][1] + "."))
    assert outcome.accepted, outcome.stderr


def test_a_missing_vocabulary_gate_refuses_loudly(tmp_path: Path) -> None:
    # The initial commit of a scratch repo goes through the hook, so the repo
    # is built with the gate and the gate is removed afterwards.
    repo = Scratch(tmp_path / "absent")
    (repo.work / "scripts" / GATE).unlink()
    outcome = repo.commit_file(_message("A clean message."))
    assert outcome.refused, outcome.stderr
    assert "absent" in outcome.stderr
    assert GATE in outcome.stderr


def test_a_clean_message_is_accepted_by_both_gates(scratch: Scratch) -> None:
    outcome = scratch.commit_file("docs: tidy the readme\n")
    assert outcome.accepted, outcome.stderr


# --------------------------------------------------------------------------- #
# The script's --message-file mode, driven directly.
# --------------------------------------------------------------------------- #
def _message_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "msg.txt"
    path.write_bytes(text.encode("utf-8"))
    return path


def test_message_file_mode_clean_exits_0(tmp_path: Path) -> None:
    path = _message_file(tmp_path, "docs: a clean subject\n\nA clean body.\n")
    result = _gate(["--message-file", str(path)])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["findings"] == []
    assert payload["mode"] == "message-file"
    assert payload["scanned"]["messages_examined"] == 1
    assert payload["scanned"]["lines_scanned"] == 2


@pytest.mark.parametrize("label,token", FAMILIES)
def test_message_file_mode_names_each_family(
    tmp_path: Path, label: str, token: str
) -> None:
    path = _message_file(tmp_path, "fix: x\n\nBody with " + token + " inside.\n")
    result = _gate(["--message-file", str(path)])
    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert [f["pattern"] for f in payload["findings"]] == [label]
    assert payload["findings"][0]["token"] == token
    assert payload["findings"][0]["line"] == 3
    assert "pattern=" + label in result.stderr
    assert token in result.stderr


def test_message_file_mode_cuts_commentary_and_the_diff_below_scissors(
    tmp_path: Path,
) -> None:
    token = FAMILIES[0][1]
    scissors = "# " + "-" * 24 + " >8 " + "-" * 24
    text = "\n".join(
        [
            "fix: a clean subject",
            "",
            "# Please enter the message; " + token + " is commentary",
            scissors,
            "diff --git a/x b/x",
            "-removed " + token,
            "",
        ]
    )
    result = _gate(["--message-file", str(_message_file(tmp_path, text))])
    assert result.returncode == 0, result.stderr
    scanned = json.loads(result.stdout)["scanned"]
    assert scanned["lines_scanned"] == 1
    assert scanned["lines_excluded"] == 5


def test_message_file_mode_with_nothing_to_scan_exits_2(tmp_path: Path) -> None:
    path = _message_file(tmp_path, "# only commentary\n\n")
    result = _gate(["--message-file", str(path)])
    assert result.returncode == 2, result.stderr
    assert "examined nothing" in result.stderr


def test_message_file_mode_missing_file_exits_2(tmp_path: Path) -> None:
    result = _gate(["--message-file", str(tmp_path / "no-such-file")])
    assert result.returncode == 2, result.stderr


@pytest.mark.parametrize(
    "extra",
    [
        ["--paths", "README.md"],
        ["--base-sha", "a", "--head-sha", "b"],
        ["--vendor-names"],
    ],
)
def test_message_file_mode_does_not_combine(tmp_path: Path, extra: List[str]) -> None:
    path = _message_file(tmp_path, "docs: clean\n")
    result = _gate(["--message-file", str(path), *extra])
    assert result.returncode == 2, result.stderr


# --------------------------------------------------------------------------- #
# The shipped file itself.
# --------------------------------------------------------------------------- #
def test_the_hook_is_tracked_executable() -> None:
    """A hook git does not see as executable is skipped without a failure on
    Linux and macOS, which would leave BOTH gates silently off there."""
    done = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(REPO_ROOT),
            "ls-files",
            "-s",
            "--",
            ".githooks/commit-msg",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        timeout=60,
    )
    if done.returncode != 0 or not done.stdout.strip():
        pytest.skip("not a git checkout, or the hook is not tracked here")
    mode = done.stdout.split()[0]
    assert mode == "100755", (
        "the hook is tracked as %s; git ignores a non-executable hook on "
        "Linux and macOS. Fix: git update-index --chmod=+x .githooks/commit-msg" % mode
    )


def test_the_hook_has_unix_line_endings() -> None:
    """The attribute file pins `-text`, so these bytes are what `sh` reads; a
    carriage return before a newline breaks the shebang line."""
    data = HOOK.read_bytes()
    assert data.startswith(b"#!/bin/sh\n")
    assert b"\r" not in data


def test_the_hook_and_this_module_carry_no_family_literal() -> None:
    """The pull-request check scans the hook and this module like any tracked
    file: neither may carry an intact instance of a family (or an attribution
    shape). The scoped scan reads the working-tree bytes of exactly these two."""
    result = _gate(
        ["--root", str(REPO_ROOT), "--paths", ".githooks/commit-msg", THIS_MODULE],
    )
    assert result.returncode == 0, result.stderr
    scanned = json.loads(result.stdout)["scanned"]
    assert scanned["files_examined"] == 2
    assert scanned["per_path"] == {".githooks/commit-msg": 1, THIS_MODULE: 1}
