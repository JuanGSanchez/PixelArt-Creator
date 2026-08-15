"""What may and may not reach the default branch, proved by real commits.

The gate under test is `.githooks/pre-commit`. It is a shell hook, so nothing
here imports it: every case builds a throwaway repository, installs the real
hooks into it, and drives an actual `git commit`. A test that reasoned about
the script's text instead would pass against a hook git never runs.

WHY THIS SUITE EXISTS, and the correction it carries. The gate decides "is this
bookkeeping?" from the SHAPE of the staged set: a commit whose every path is
orchestration furniture — `.githooks/`, `.gitattributes`, `memory/` — is the
arrangement rather than development, and is admitted. On 2026-08-15 six such
commits were observed on the default branch and read as a hole in the gate. The
suite was written to close it, by requiring bookkeeping to be DECLARED through a
`PIXELART_MAIN_BOOKKEEPING=1` marker.

That was wrong, and the tests encoding it were wrong with it. Classifying those
six commits showed two of them were `post-merge` committing the refreshed map,
which the arrangement REQUIRES on the default branch — a merge that a hook then
fails is worse than a map committed by hand — and the remaining four were an
agent hand-committing on main. The gate had behaved as designed; the discipline
failure was upstream of it. Worse, the marker was a second source of truth
beside `FURNITURE`, and the canonical generator is explicit that the exemption
is "derived, never a second list: an exemption that drifted from the pathspec
would refuse the commit that installs the very files the pathspec protects."

So the marker was withdrawn and these tests now assert the canonical rule. What
keeps work off the default branch is the branch-and-pull-request discipline the
refusal message names, not a variable a caller can set — the gate stops someone
who did not notice which branch they were on, and no gate has ever stopped
someone who meant it.

The matrix below is the point: every route to the default branch, and the three
that are legitimate — the creation commit, a merge, and the arrangement itself.
"""

import subprocess

import pytest

CONTAINER_STUBS = ("check_branch_naming.py", "check_names.py")

# The three roots the generator treats as the arrangement rather than the work.
# Kept here as data so a change to the set fails a test rather than passing
# silently — this is the mirror of `container_repo.py`'s FURNITURE.
# `.githooks/post-merge` stands for the `.githooks/` root rather than
# `pre-commit`: overwriting the hook that is currently running makes git fail
# with "cannot spawn", which is indistinguishable from a refusal. The previous
# version of this suite asserted a non-zero exit here and was green for exactly
# that wrong reason.
FURNITURE = ("memory/graph/nodes.jsonl", ".githooks/post-merge", ".gitattributes")


def git(repo, *args, env=None, check=True):
    done = subprocess.run(
        ["git", "-C", str(repo)] + [str(a) for a in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if check and done.returncode != 0:
        raise AssertionError(
            "git %s failed: %s%s" % (" ".join(args), done.stdout, done.stderr)
        )
    return done


@pytest.fixture
def repo(tmp_path, request):
    """A repository with the REAL hooks installed, under a stub container.

    The hooks walk upward for the container's own gate scripts and refuse to
    run without them — deliberately, so an unrunnable gate is never a silent
    pass. The stubs stand in for those two checks only; the branch rule under
    test is the hook's own code, untouched.

    The hooks are copied from THIS repository's `.githooks/`, which is the
    scope a product suite can own: it proves the gate this clone actually
    ships. Whether that gate still matches what the container would generate
    is the container's question, and is checked there.
    """
    container = tmp_path / "container"
    (container / "scripts").mkdir(parents=True)
    for name in CONTAINER_STUBS:
        (container / "scripts" / name).write_text(
            "import sys\nsys.exit(0)\n", encoding="utf-8"
        )

    work = container / "main"
    work.mkdir()
    git(work.parent, "init", "-q", str(work))
    git(work, "config", "user.email", "test@example.invalid")
    git(work, "config", "user.name", "Test")
    git(work, "config", "commit.gpgsign", "false")

    # The real hooks, copied from the branch this suite ships in.
    src = request.config.rootpath / ".githooks"
    dst = work / ".githooks"
    dst.mkdir()
    for hook in ("pre-commit", "post-merge", "post-checkout"):
        if (src / hook).is_file():
            (dst / hook).write_bytes((src / hook).read_bytes())
    git(work, "config", "core.hooksPath", ".githooks")

    # A store, so "bookkeeping" has something real to be about.
    (work / "memory" / "graph").mkdir(parents=True)
    (work / "memory" / "store-role.json").write_text(
        '{"role": "product"}', encoding="utf-8"
    )
    (work / "memory" / "graph" / "nodes.jsonl").write_text("", encoding="utf-8")

    # The creation commit — the one commit the default branch takes without
    # argument, and the exception the hook makes for having no HEAD yet.
    (work / "README.md").write_text("# test\n", encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "chore: create the repository")
    git(work, "branch", "-M", "main")
    return work


def commit(repo, message, env=None):
    """Attempt a commit; return the completed process rather than raising."""
    return git(repo, "commit", "-m", message, env=env, check=False)


def touch(repo, rel, text="x\n"):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    git(repo, "add", "--", rel)
    return path


def head(repo):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


# --- the creation commit ----------------------------------------------------


def test_the_creation_commit_is_allowed(repo):
    """Proved by the fixture: a repository has to start somewhere, and the
    hook makes that exception because there is no HEAD to compare against."""
    assert git(repo, "log", "--oneline").stdout.strip()


# --- development: refused, whatever it touches ------------------------------


def test_development_on_main_is_refused(repo):
    touch(repo, "app.py", "print('hello')\n")
    done = commit(repo, "feat: add a thing")
    assert done.returncode != 0, "a development commit landed on main"
    assert "development on 'main' is refused" in done.stderr


def test_the_refusal_names_the_route_out(repo):
    """A gate that refuses without saying what to do instead is an obstacle,
    not a guard. With the marker withdrawn, the named route IS the guard."""
    touch(repo, "app.py")
    done = commit(repo, "feat: add a thing")
    assert "start-branch" in done.stderr or "switch -c" in done.stderr


# --- the arrangement: admitted, and it has to be ----------------------------


def test_a_store_only_commit_is_admitted_as_the_arrangement(repo):
    """It has to be POSSIBLE, and this is why: `post-merge` commits the
    refreshed map on the default branch after every merge, because a map left
    dirty makes the NEXT merge refuse. A gate that blocked this would fail
    merges with their own bookkeeping."""
    before = head(repo)
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    done = commit(repo, "chore(memory): refresh")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "arrangement, not development" in done.stderr
    assert head(repo) != before, "the commit was reported allowed but never made"


@pytest.mark.parametrize("rel", FURNITURE)
def test_every_furniture_path_is_admitted_alone(repo, rel):
    """One admitted path proves one path; the CLASS is what must hold. The
    exemption is derived from one list in the generator, so all three roots
    stand or fall together."""
    touch(repo, rel, "# changed\n")
    done = commit(repo, "chore: furniture")
    assert done.returncode == 0, done.stdout + done.stderr


def test_a_marker_variable_no_longer_governs_anything(repo):
    """REGRESSION, in the direction the mistake actually ran. The withdrawn
    `PIXELART_MAIN_BOOKKEEPING` must not come back as a second source of truth
    beside FURNITURE: an unset marker may not change the verdict, and neither
    may a set one."""
    import os

    declared = dict(os.environ)
    declared["PIXELART_MAIN_BOOKKEEPING"] = "1"

    touch(repo, "app.py", "print('hello')\n")
    assert (
        commit(repo, "feat: a thing", env=declared).returncode != 0
    ), "a marker variable re-opened the default branch to development"


def test_furniture_mixed_with_product_code_is_refused(repo):
    """All-or-nothing. Otherwise the arrangement becomes a way to smuggle a
    source change onto the default branch beside a store update."""
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    touch(repo, "app.py", "print('smuggled')\n")
    done = commit(repo, "chore(memory): refresh")
    assert done.returncode != 0, "product code rode in on a bookkeeping commit"
    assert "development on 'main' is refused" in done.stderr


# --- merges: the way work is meant to arrive --------------------------------


def test_a_merge_commit_is_allowed(repo):
    """The path a pull request takes. If this broke, nothing could ever reach
    the default branch at all — which is why it is tested and not assumed."""
    git(repo, "checkout", "-q", "-b", "feat-thing")
    touch(repo, "app.py", "print('from the branch')\n")
    assert commit(repo, "feat: add a thing").returncode == 0
    git(repo, "checkout", "-q", "main")
    done = git(
        repo, "merge", "--no-ff", "-m", "Merge feat-thing", "feat-thing", check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert (repo / "app.py").is_file()


def test_a_merge_is_not_failed_by_the_map_it_leaves_behind(repo):
    """`post-merge` cannot run here — it needs the container's real modules,
    and the fixture's container is a stub — so this drives the sequence it
    performs: merge, then commit the refreshed store on the default branch.
    Both halves must pass the gate, or every merge ends with a dirty map."""
    git(repo, "checkout", "-q", "-b", "feat-thing")
    touch(repo, "app.py", "print('from the branch')\n")
    assert commit(repo, "feat: add a thing").returncode == 0
    git(repo, "checkout", "-q", "main")
    assert (
        git(
            repo,
            "merge",
            "--no-ff",
            "-m",
            "Merge feat-thing",
            "feat-thing",
            check=False,
        ).returncode
        == 0
    )

    before = head(repo)
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node","after":"merge"}\n')
    done = commit(repo, "chore(memory): refresh the map after the merge")
    assert done.returncode == 0, done.stdout + done.stderr
    assert head(repo) != before


# --- branches: unaffected ---------------------------------------------------


@pytest.mark.parametrize("branch", ["feat-thing", "fix-thing"])
def test_development_on_a_branch_is_untouched(repo, branch):
    """The guard is about the default branch. It must not make ordinary work
    harder anywhere else."""
    git(repo, "checkout", "-q", "-b", branch)
    touch(repo, "app.py", "print('fine here')\n")
    assert commit(repo, "feat: add a thing").returncode == 0


def test_a_store_only_commit_on_a_branch_is_ordinary(repo):
    git(repo, "checkout", "-q", "-b", "feat-thing")
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    assert commit(repo, "chore(memory): refresh").returncode == 0
