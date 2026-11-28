"""The branch is built on the merge of the visual-identity work.

The release evidence is only worth reading on a branch that contains that merge:
the thresholds, the font face and the build pipeline this release extends are the
ones the merge brought, so a branch cut before it would be judged against the
wrong ground. The merge is recorded below as ``BASE_MERGE_SHA`` and the one
statement checked is

    git merge-base --is-ancestor <BASE_MERGE_SHA> HEAD        (exit status 0)

(REQ-L10N-BUILD-005, SC-L10N-BUILD-005-1).

The check never skips. A clone without the commit - a shallow checkout is the
usual cause - cannot answer, and a check that cannot answer has not passed, so it
fails and names the cause. In CI the quality-gate job checks out full history
(``fetch-depth: 0``), which is what makes the answer available there.

Every failure path is proved on throwaway repositories under ``tmp_path``: an empty
or malformed recorded sha, a repository that does not hold the commit, a shallow
clone, a clone checked out at a commit before the merge, and a directory that is
no repository at all - each beside a positive control, so a function that says
"no" to everything fails too. The real-repository case runs the same function.

The real repository is the checkout this file sits in. ``RELEASE_EVIDENCE_REPO``
points the real-repository case at another checkout. Nothing here writes to the
repository under test; every git call there is a read.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

#: Repo root: testing/suites/release/test_base_ancestry.py -> parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]

#: Environment variable that points the real-repository case at another checkout.
REPO_ENV = "RELEASE_EVIDENCE_REPO"

#: The merge of the visual-identity work into ``main``.
BASE_MERGE_SHA = "221e51d25577330584702ad70b8f69b3daddbe23"

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


@dataclass(frozen=True)
class Verdict:
    """The answer to "does this clone contain the merge?"."""

    ok: bool
    cause: str
    head: str
    shallow: bool

    def line(self, repo: Path, sha: str) -> str:
        """One printable line: the repository, both shas and the answer."""
        answer = "ANCESTOR" if self.ok else "FAILED: " + self.cause
        return "base-ancestry repo=%s head=%s base_merge_sha=%s shallow=%s -> %s" % (
            repo,
            self.head or "-",
            sha or "-",
            self.shallow,
            answer,
        )


def check_base_ancestry(repo: Path, sha: str) -> Verdict:
    """Say whether ``sha`` is an ancestor of the HEAD of ``repo``.

    Fails, naming the cause, for: an empty or malformed recorded sha; a directory
    that is no repository; a repository with no HEAD commit; a commit that is not
    in the clone (the shallow case is named as such); a commit that is in the clone
    but is not an ancestor of HEAD; and any other git error. Never skips.
    """
    if not isinstance(sha, str) or not FULL_SHA.fullmatch(sha.strip()):
        return Verdict(
            False,
            "no merge sha is recorded: BASE_MERGE_SHA is empty or not a full "
            "40-character lowercase hex sha (%r)" % (sha,),
            "",
            False,
        )
    sha = sha.strip()
    inside = _git(repo, "rev-parse", "--git-dir")
    if inside.returncode != 0:
        return Verdict(False, "not a git repository: %s" % repo, "", False)
    shallow = _git(repo, "rev-parse", "--is-shallow-repository").stdout.strip()
    is_shallow = shallow == "true"
    head_done = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    head = head_done.stdout.strip() if head_done.returncode == 0 else ""
    if not head:
        return Verdict(False, "the repository has no HEAD commit", "", is_shallow)
    held = _git(repo, "cat-file", "-e", sha + "^{commit}")
    if held.returncode != 0:
        if is_shallow:
            cause = (
                "the merge commit %s is not in this clone: the clone is SHALLOW "
                "(its history is truncated); check out full history "
                "(fetch-depth: 0)" % sha
            )
        else:
            cause = (
                "the merge commit %s is not in this clone (a different "
                "repository, or a fetch that left it out)" % sha
            )
        return Verdict(False, cause, head, is_shallow)
    ancestry = _git(repo, "merge-base", "--is-ancestor", sha, "HEAD")
    if ancestry.returncode == 0:
        return Verdict(True, "", head, is_shallow)
    if ancestry.returncode == 1:
        cause = (
            "the merge commit %s is not an ancestor of HEAD %s: this branch was "
            "not built on the merge" % (sha, head)
        )
        if is_shallow:
            cause += " (the clone is shallow, so its history may be cut short)"
        return Verdict(False, cause, head, is_shallow)
    return Verdict(
        False,
        "git merge-base --is-ancestor failed with status %d: %s"
        % (ancestry.returncode, ancestry.stderr.strip()),
        head,
        is_shallow,
    )


def _repo_under_test() -> Path:
    override = os.environ.get(REPO_ENV)
    return Path(override) if override else REPO_ROOT


# --- throwaway repositories -----------------------------------------------------


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


def _commit(repo: Path, name: str, text: str) -> str:
    """Commit one file and return the new commit's sha."""
    (repo / name).write_bytes(text.encode("utf-8"))
    _ok(_git(repo, "add", "-A"))
    _ok(_git(repo, "commit", "-q", "-m", "scratch: " + name))
    return _ok(_git(repo, "rev-parse", "HEAD")).stdout.strip()


@dataclass(frozen=True)
class Origin:
    """A three-commit history: before the merge, the merge, after the merge."""

    path: Path
    before: str
    merge: str
    after: str


@pytest.fixture
def origin(tmp_path: Path) -> Origin:
    repo = _init(tmp_path / "origin")
    before = _commit(repo, "one.txt", "before the merge\n")
    merge = _commit(repo, "two.txt", "the merge\n")
    after = _commit(repo, "three.txt", "after the merge\n")
    return Origin(repo, before, merge, after)


def _clone(origin: Origin, dest: Path, *, depth: int | None = None) -> Path:
    """A clone without a checkout; ``depth`` makes it shallow."""
    hooks = dest.with_name(dest.name + "-hooks")
    hooks.mkdir()
    source = origin.path.as_uri() if depth else str(origin.path)
    args = ["-c", "core.hooksPath=" + str(hooks), "clone", "-q", "--no-checkout"]
    if depth:
        args += ["--depth", str(depth)]
    _ok(_git(dest.parent, *args, source, str(dest)))
    return dest


def _detach_at(repo: Path, sha: str) -> None:
    """Point HEAD at ``sha`` without touching any working tree."""
    _ok(_git(repo, "update-ref", "--no-deref", "HEAD", sha))


# --- the recorded sha -----------------------------------------------------------


def test_the_recorded_merge_sha_is_a_full_sha():
    print("recorded BASE_MERGE_SHA = %r" % (BASE_MERGE_SHA,))
    assert isinstance(BASE_MERGE_SHA, str)
    assert FULL_SHA.fullmatch(
        BASE_MERGE_SHA
    ), "BASE_MERGE_SHA must be a full 40-character lowercase hex sha, got %r" % (
        BASE_MERGE_SHA,
    )
    assert BASE_MERGE_SHA != "0" * 40


# --- the real repository --------------------------------------------------------


def test_the_branch_contains_the_merge_of_the_visual_identity_work():
    repo = _repo_under_test()
    verdict = check_base_ancestry(repo, BASE_MERGE_SHA)
    print(verdict.line(repo, BASE_MERGE_SHA))
    if not verdict.ok:
        pytest.fail(verdict.cause, pytrace=False)


# --- the controls: every way of failing, and the way of passing -----------------


def test_a_branch_after_the_merge_passes(origin: Origin):
    verdict = check_base_ancestry(origin.path, origin.merge)
    print(verdict.line(origin.path, origin.merge))
    assert verdict.ok, verdict.cause
    assert verdict.head == origin.after
    assert verdict.cause == ""


def test_the_merge_commit_itself_counts_as_its_own_ancestor(origin: Origin):
    repo = _clone(origin, origin.path.with_name("at-merge"))
    _detach_at(repo, origin.merge)
    verdict = check_base_ancestry(repo, origin.merge)
    assert verdict.ok, verdict.cause


def test_a_clone_checked_out_before_the_merge_fails(origin: Origin, tmp_path: Path):
    clone = _clone(origin, tmp_path / "before-clone")
    _detach_at(clone, origin.before)
    held = _git(clone, "cat-file", "-e", origin.merge + "^{commit}")
    assert held.returncode == 0, "the control needs the merge commit present"
    verdict = check_base_ancestry(clone, origin.merge)
    print(verdict.line(clone, origin.merge))
    assert not verdict.ok
    assert verdict.head == origin.before
    assert "not an ancestor" in verdict.cause
    assert origin.merge in verdict.cause


def test_a_shallow_clone_without_the_commit_fails_and_names_the_shallow_history(
    origin: Origin, tmp_path: Path
):
    shallow = _clone(origin, tmp_path / "shallow-clone", depth=1)
    assert _git(shallow, "rev-parse", "--is-shallow-repository").stdout.strip() == (
        "true"
    )
    verdict = check_base_ancestry(shallow, origin.merge)
    print(verdict.line(shallow, origin.merge))
    assert not verdict.ok
    assert verdict.shallow is True
    assert "SHALLOW" in verdict.cause
    assert "not in this clone" in verdict.cause
    assert "fetch-depth: 0" in verdict.cause


def test_a_repository_that_never_held_the_commit_fails(tmp_path: Path):
    other = _init(tmp_path / "other")
    _commit(other, "unrelated.txt", "an unrelated history\n")
    verdict = check_base_ancestry(other, BASE_MERGE_SHA)
    print(verdict.line(other, BASE_MERGE_SHA))
    assert not verdict.ok
    assert verdict.shallow is False
    assert "not in this clone" in verdict.cause
    assert "SHALLOW" not in verdict.cause


@pytest.mark.parametrize(
    "recorded",
    ["", "   ", "221e51d", "not-a-sha", "221E51D25577330584702AD70B8F69B3DAADBE23"],
    ids=["empty", "blank", "abbreviated", "text", "uppercase"],
)
def test_an_empty_or_malformed_recorded_sha_fails(origin: Origin, recorded: str):
    verdict = check_base_ancestry(origin.path, recorded)
    print(verdict.line(origin.path, recorded))
    assert not verdict.ok
    assert "BASE_MERGE_SHA" in verdict.cause


def test_a_missing_recorded_sha_fails(origin: Origin):
    verdict = check_base_ancestry(origin.path, None)  # type: ignore[arg-type]
    assert not verdict.ok
    assert "BASE_MERGE_SHA" in verdict.cause


def test_a_directory_that_is_no_repository_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    plain = tmp_path / "plain"
    plain.mkdir()
    # Stop git's upward search so an enclosing repository cannot answer instead.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    inside = _git(plain, "rev-parse", "--git-dir")
    assert inside.returncode != 0, "the control needs a directory outside any repo"
    verdict = check_base_ancestry(plain, BASE_MERGE_SHA)
    assert not verdict.ok
    assert "not a git repository" in verdict.cause


def test_a_repository_without_a_commit_fails(tmp_path: Path):
    empty = _init(tmp_path / "empty")
    verdict = check_base_ancestry(empty, BASE_MERGE_SHA)
    assert not verdict.ok
    assert "no HEAD commit" in verdict.cause
