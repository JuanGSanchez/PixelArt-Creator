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

So the marker was withdrawn and these tests asserted the canonical rule as it
stood then: ANY commit whose every staged path was furniture — any of
`.githooks/`, `.gitattributes`, `memory/`, without further qualification — was
admitted. That rule was itself too wide, and was narrowed a second time: 33
"chore(memory): refresh the map" commits had landed on a real product's
default branch through it, unconditionally, forever. Hook and merge-driver
CHANGES must travel by pull request; only their arrangement — not their
editing — belongs on the default branch directly. So the single carve-out
became FOUR narrow, named admissions, and this suite was rewritten again to
match:

  1. the creation commit — there is no HEAD yet;
  2. a merge — MERGE_HEAD is present while it lands;
  3. a STORE-ONLY refresh committed immediately after a merge lands — staged
     paths are `memory/` and `memory/` ONLY, and the CURRENT HEAD (the commit
     already sitting there, before the one being made) is itself a merge
     commit (`HEAD^2` resolves). `.githooks/` and `.gitattributes` no longer
     qualify here at all — a hook or merge-driver CHANGE is development now,
     whatever else is staged beside it;
  4. a one-time BOOTSTRAP — every staged furniture path (`.githooks/`,
     `.gitattributes`, `memory/`) is NEW, i.e. none of it was tracked
     before. The files a product's gate installs are untracked in any clone
     made before the gate existed, and while they stay untracked the first
     branch commits them and the merge back into main aborts on "untracked
     working tree files would be overwritten" — main could then never
     receive a pull request at all. The second time the SAME paths are
     staged they are modifications, not additions, and admission 4 refuses
     them: bootstrap is a door that closes behind you, not a standing route.

What keeps work off the default branch is the branch-and-pull-request
discipline the refusal message names, not a variable a caller can set, and —
as of the second narrowing — not an indefinitely reusable furniture exemption
either. The gate stops someone who did not notice which branch they were on,
or who reached for the old, wider exemption out of habit; it has never
stopped someone who meant it, and `--no-verify` still says so out loud.

The matrix below is the point: every route to the default branch, and the
four that are legitimate — the creation commit, a merge, a post-merge store
refresh, and a one-time furniture bootstrap.
"""

import subprocess

import pytest

CONTAINER_STUBS = ("check_branch_naming.py", "check_names.py")

# The three roots the generator treats as ORCHESTRATION FURNITURE at all —
# the class a genuinely NEW path under any of them may bootstrap through
# (admission 4). Kept here as data, mirroring `container_repo.py`'s own
# `FURNITURE`, so a change to that set fails a test rather than passing
# silently.
#
# This is deliberately NOT "every path under here is admitted unconditionally"
# any more — that was the wide, pre-narrowing rule. `.githooks/new-file` and
# `memory/graph/new-node.jsonl` below are each a path NEVER STAGED BEFORE in
# the fixture's history, which is what makes bootstrap the right (and only)
# admission for them; staging an ALREADY-TRACKED path under the same roots is
# covered separately, by `test_a_githooks_change_is_refused_outside_bootstrap`
# and `test_a_second_furniture_commit_is_refused_once_tracked` below, and
# refused.
NEW_FURNITURE_PATHS = (
    ".githooks/new-file",
    ".gitattributes",
    "memory/graph/new-node.jsonl",
)


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


# --- admission 3: a post-merge store-only refresh, and ONLY then -----------


def test_a_store_only_commit_is_refused_when_head_is_not_a_merge(repo):
    """THE CORE OF THE SECOND NARROWING, and the direct descendant of what
    this test used to assert. Before the narrowing, ANY furniture-only
    commit was admitted unconditionally — including this one, staged right
    after the creation commit with no merge anywhere in its history. That is
    exactly what is refused now: a store-only commit is the arrangement only
    when it is the post-merge refresh, i.e. when the CURRENT HEAD (the commit
    already sitting there, before this one) is itself a merge commit. Nothing
    here is a merge, so admission 3 does not fire, and admission 4
    (bootstrap) does not either — `memory/graph/nodes.jsonl` was tracked by
    the fixture's own creation commit, so this is a modification, not an
    addition.

    The admitted counterpart — the SAME kind of commit, made immediately
    after a real merge — is
    `test_a_post_merge_store_refresh_is_admitted_because_head_is_a_merge`
    below, and is also what
    `test_a_merge_is_not_failed_by_the_map_it_leaves_behind` exercises as
    part of the full merge workflow.
    """
    before = head(repo)
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    done = commit(repo, "chore(memory): refresh")
    assert (
        done.returncode != 0
    ), "a store-only commit landed on main without a preceding merge"
    assert "development on 'main' is refused" in done.stderr
    assert head(repo) == before, "a refused commit still moved HEAD"


def test_a_post_merge_store_refresh_is_admitted_because_head_is_a_merge(repo):
    """Admission 3, kept as small as the real thing allows: a `--no-ff`
    merge of a branch carrying one trivial commit — `--no-ff` on a branch
    with NOTHING new is a no-op ("Already up to date", no merge commit, no
    `HEAD^2`), so the single commit exists only to force a real merge commit
    into being, not because its content is under test — then a memory-only
    commit. HEAD is now the merge just made — `HEAD^2` resolves — which is
    the ONLY thing that makes this admitted rather than refused;
    `test_a_store_only_commit_is_refused_when_head_is_not_a_merge` is the
    same shape of trailing commit without that precondition, and is
    refused."""
    git(repo, "checkout", "-q", "-b", "empty-branch")
    touch(repo, "app.py", "print('from the branch')\n")
    assert commit(repo, "feat: a trivial branch commit to merge").returncode == 0
    git(repo, "checkout", "-q", "main")
    assert (
        git(
            repo,
            "merge",
            "--no-ff",
            "-m",
            "Merge empty-branch",
            "empty-branch",
            check=False,
        ).returncode
        == 0
    )
    assert git(repo, "rev-parse", "--verify", "--quiet", "HEAD^2").returncode == 0, (
        "the merge above did not produce a merge commit; the precondition "
        "this test isolates was never exercised"
    )

    before = head(repo)
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node","after":"merge"}\n')
    done = commit(repo, "chore(memory): refresh the map after the merge")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "post-merge store refresh" in done.stderr
    assert "arrangement, not development" in done.stderr
    assert head(repo) != before, "the commit was reported allowed but never made"


# --- admission 4: a one-time furniture bootstrap ----------------------------


@pytest.mark.parametrize("rel", NEW_FURNITURE_PATHS)
def test_every_furniture_root_is_admitted_as_a_bootstrap(repo, rel):
    """One admitted path proves one path; the CLASS is what must hold. All
    three furniture roots bootstrap the same way — a genuinely NEW path
    under any of them, staged alone, is admitted — because the pattern the
    gate matches is derived from one list (`FURNITURE`) in the generator,
    same as before the narrowing. What changed is the SECOND condition
    admission 4 now carries alongside that pattern: every staged path must
    also be an ADDITION. `rel` here has never been staged in this
    repository's history, so it satisfies both."""
    before = head(repo)
    touch(repo, rel, "# new furniture\n")
    done = commit(
        repo,
        "chore(system): track the orchestration gate, merge-driver "
        "request and memory store",
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "bootstrap" in done.stderr
    assert head(repo) != before, "the commit was reported allowed but never made"


def test_a_second_furniture_commit_is_refused_once_tracked(repo):
    """Bootstrap is a door that closes behind you. The SAME path,
    `.gitattributes`, is staged twice: the first time it is genuinely new and
    admission 4 fires; the second time it is a modification of a path this
    repository now tracks, admission 4's own "every staged path is an
    addition" test fails, and nothing else admits it either — a repeat visit
    through the one-time exception is exactly what "one-time" has to mean,
    or it is not an exception at all."""
    touch(repo, ".gitattributes", "* -text\n")
    first = commit(repo, "chore(system): bootstrap the memory merge stanza")
    assert first.returncode == 0, first.stdout + first.stderr

    touch(repo, ".gitattributes", "* -text\n# a second, later change\n")
    second = commit(repo, "chore(system): change it again")
    assert (
        second.returncode != 0
    ), "a second commit of an already-tracked furniture path was admitted"
    assert "development on 'main' is refused" in second.stderr


def test_a_githooks_change_is_refused_outside_bootstrap(repo):
    """Hook and merge-driver CHANGES travel by pull request now — the whole
    point of narrowing admission 3 to `memory/` alone. `.githooks/post-merge`
    stands for the `.githooks/` root rather than `pre-commit`: overwriting
    the hook that is currently running makes git fail with "cannot spawn",
    which is indistinguishable from a refusal and would prove nothing. The
    fixture's creation commit already tracks `.githooks/post-merge` (it is
    copied in wholesale, `git add -A`, before that commit), so modifying it
    here is neither a bootstrap addition nor a memory-only refresh — it is
    development, and is refused like any other."""
    touch(repo, ".githooks/post-merge", "#!/bin/sh\n# changed\nexit 0\n")
    done = commit(repo, "chore: change a tracked hook file")
    assert done.returncode != 0, "a .githooks/ change landed on main directly"
    assert "development on 'main' is refused" in done.stderr


def test_a_marker_variable_no_longer_governs_anything(repo):
    """REGRESSION, in the direction the mistake actually ran. The withdrawn
    `PIXELART_MAIN_BOOKKEEPING` must not come back as a second source of truth
    beside FURNITURE: an unset marker may not change the verdict, and neither
    may a set one. Unaffected by the second narrowing — this is a plain
    development commit either way, admitted by neither admission 3 nor 4."""
    import os

    declared = dict(os.environ)
    declared["PIXELART_MAIN_BOOKKEEPING"] = "1"

    touch(repo, "app.py", "print('hello')\n")
    assert (
        commit(repo, "feat: a thing", env=declared).returncode != 0
    ), "a marker variable re-opened the default branch to development"


def test_furniture_mixed_with_product_code_is_refused(repo):
    """All-or-nothing. Otherwise the arrangement becomes a way to smuggle a
    source change onto the default branch beside a store update. Unaffected
    by the second narrowing: neither admission 3 nor 4 accepts a staged set
    that contains `app.py` at all, before or after."""
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
    Both halves must pass the gate, or every merge ends with a dirty map.

    Before the second narrowing this passed because ANY furniture-only
    commit was admitted, merge or not. It still passes, but now for the
    narrower and correct reason: HEAD, at the moment of the second commit, IS
    the merge just made (`HEAD^2` resolves), which is exactly admission 3 and
    is asserted below by name rather than left implicit."""
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
    assert "post-merge store refresh" in done.stderr
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
