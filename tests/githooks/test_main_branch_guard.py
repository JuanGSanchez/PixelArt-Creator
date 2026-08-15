"""What may and may not reach the default branch, proved by real commits.

The gate under test is `.githooks/pre-commit`. It is a shell hook, so nothing
here imports it: every case builds a throwaway repository, installs the real
hooks into it, and drives an actual `git commit`. A test that reasoned about
the script's text instead would pass against a hook git never runs.

WHY THIS SUITE EXISTS. The gate used to decide "is this bookkeeping?" purely
from the SHAPE of the staged set — every path under `.githooks/`,
`.gitattributes` or `memory/` and the commit was waved through. The staged set
says what a commit touches; it cannot say who decided to make it. On
2026-08-15 six commits went onto the default branch that way, by an agent that
had simply staged nothing else, and the gate reported each one as "the
arrangement, not development". The rule the project actually holds is narrower:
the default branch takes the repository's creation commit and merges, and
everything else arrives through a pull request.

So bookkeeping now has to be DECLARED (`PIXELART_MAIN_BOOKKEEPING=1`), which
`post-merge` does for its own refresh commit and a human does deliberately for
maintenance. The gate cannot stop someone who means it — no gate can, which is
the same bargain `--no-verify` offers — but it can stop someone who did not
notice which branch they were on.

The matrix below is the point: every route to the default branch, and the two
that are legitimate.
"""

import subprocess
import textwrap

import pytest

CONTAINER_STUBS = ("check_branch_naming.py", "check_names.py")


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


def bookkeeping_env(monkeypatch=None):
    import os

    env = dict(os.environ)
    env["PIXELART_MAIN_BOOKKEEPING"] = "1"
    return env


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
    not a guard."""
    touch(repo, "app.py")
    done = commit(repo, "feat: add a thing")
    assert "start-branch" in done.stderr or "switch -c" in done.stderr


# --- bookkeeping: possible, but only when declared --------------------------


def test_a_store_only_commit_without_the_marker_is_refused(repo):
    """THE REGRESSION. This is exactly the shape that put six commits on the
    default branch: stage nothing but the store, and the old gate waved it
    through as "the arrangement, not development"."""
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    done = commit(repo, "chore(memory): refresh")
    assert (
        done.returncode != 0
    ), "a store-only commit landed on main with nothing declaring it"
    assert "REFUSED" in done.stderr
    assert (
        "PIXELART_MAIN_BOOKKEEPING=1" in done.stderr
    ), "the refusal must name the deliberate route"


def test_a_store_only_commit_with_the_marker_is_allowed(repo):
    """Maintenance has to remain possible: compaction is only legal on the
    default branch, so refusing it outright would strand the store."""
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    done = commit(repo, "chore(memory): compact", env=bookkeeping_env())
    assert done.returncode == 0, done.stdout + done.stderr
    assert "allowed" in done.stderr


@pytest.mark.parametrize(
    "rel", ["memory/graph/nodes.jsonl", ".githooks/pre-commit", ".gitattributes"]
)
def test_every_furniture_path_needs_the_marker(repo, rel):
    """One allowed path proves one path; the CLASS is what must hold."""
    touch(repo, rel, "# changed\n")
    assert commit(repo, "chore: furniture").returncode != 0


def test_furniture_mixed_with_product_code_is_refused_even_declared(repo):
    """All-or-nothing. Otherwise the marker becomes a way to smuggle a source
    change onto the default branch beside a store update."""
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    touch(repo, "app.py", "print('smuggled')\n")
    done = commit(repo, "chore(memory): refresh", env=bookkeeping_env())
    assert done.returncode != 0, "product code rode in on a bookkeeping commit"
    assert "development on 'main' is refused" in done.stderr


# --- merges: the way work is meant to arrive --------------------------------


def test_a_merge_commit_is_allowed_without_any_marker(repo):
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


def test_post_merge_declares_its_own_bookkeeping(repo, request):
    """The automated half of the bargain: the hook that makes the commit is
    the thing that declares it, so a merge is never failed by its own map."""
    text = (request.config.rootpath / ".githooks" / "post-merge").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "PIXELART_MAIN_BOOKKEEPING=1" in text


# --- branches: unaffected ---------------------------------------------------


@pytest.mark.parametrize("branch", ["feat-thing", "fix-thing"])
def test_development_on_a_branch_is_untouched(repo, branch):
    """The guard is about the default branch. Tightening it must not make
    ordinary work harder anywhere else."""
    git(repo, "checkout", "-q", "-b", branch)
    touch(repo, "app.py", "print('fine here')\n")
    assert commit(repo, "feat: add a thing").returncode == 0


def test_a_store_only_commit_on_a_branch_needs_no_marker(repo):
    git(repo, "checkout", "-q", "-b", "feat-thing")
    touch(repo, "memory/graph/nodes.jsonl", '{"kind":"node"}\n')
    assert commit(repo, "chore(memory): refresh").returncode == 0
