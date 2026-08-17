"""The memory viewer's page assets ship with the store (WP-7, R-11/C-11).

Companion to ``test_memory_view_launcher.py``: that module proves the two
LAUNCHER files ship, are executable and self-describing. This module proves
the three PAGE assets they open — ``graph-view.html``, ``graph-view.css``,
``graph-view.js`` — are tracked and not gitignored, and that whatever
repo-relative file the launchers reference at run time is tracked too.

WHY THE IGNORE CHECK USES ``--no-index``: the default, index-aware
``git check-ignore`` never reports an already-TRACKED path as ignored, even
when a matching ``.gitignore`` pattern exists — confirmed empirically against
this exact store in
``design-docs/reports/wp7-memory-view-assets-20260816.md`` §2b, where the
container engine's ``ensure()`` silently re-appended the three ``graph-view.*``
lines to ``memory/.gitignore`` after they had been removed, and the default
check kept reporting "not ignored" throughout because the files were already
staged. A checker built on the default check would have passed the whole time
that finding was live — it would never have caught the regression it was
written to catch. ``--no-index`` reads the pattern against the working tree
only, independent of what the index currently tracks, so a re-added ignore
line is caught whether or not the file happens to be tracked at the moment the
test runs. ``test_ignore_checker_is_mutation_proof`` below reproduces the
exact tracked-file + gitignore arrangement in a throwaway repo and proves this
checker flags a re-added line in both directions.

WHAT THIS SUITE DELIBERATELY DOES NOT DO: it never mutates
``feat-memory-view-assets`` (or any clone of it) to prove the point — the
throwaway repo lives entirely under the pytest ``tmp_path`` fixture and is
gone when the test ends. It also never launches the viewer: no server, no
subprocess outlives the single ``git``/``git init`` calls each test makes.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STORE = REPO_ROOT / "memory"

# The three page assets WP-7 tracks (ground truth: the WP-7 findings report).
VIEWER_ASSETS = ("graph-view.html", "graph-view.css", "graph-view.js")

# A repo-relative reference inside a launcher looks like `$STORE/<file>` in
# the POSIX script or `%STORE%\<file>` in the batch script -- always with a
# file extension, which is what distinguishes an actual file reference from a
# bare directory walk like `$STORE/..` or `--store "$STORE"`.
_SH_STORE_REF = re.compile(r"\$STORE/([\w.\-]+\.[A-Za-z0-9]+)")
_CMD_STORE_REF = re.compile(r"%STORE%\\+([\w.\-]+\.[A-Za-z0-9]+)")


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
    )


def _is_tracked(repo_root: Path, rel_path: str) -> bool:
    """True if ``rel_path`` is a tracked path in ``repo_root``'s index."""
    done = _git(repo_root, "ls-files", "--error-unmatch", "--", rel_path)
    return done.returncode == 0


def _is_ignored(repo_root: Path, rel_path: str) -> bool:
    """True if a gitignore pattern currently matches ``rel_path``.

    Deliberately ``--no-index``: see the module docstring for why the
    default, index-aware check cannot be trusted to catch a re-added ignore
    line against a path that is already tracked.
    """
    done = _git(repo_root, "check-ignore", "--no-index", "--", rel_path)
    return done.returncode == 0


def _parse_repo_relative_references(sh_body: str, cmd_body: str) -> set:
    """Parse both launcher bodies for the repo-relative files they touch.

    Returns the UNION of filenames referenced via ``$STORE/<file>`` (sh) or
    ``%STORE%\\<file>`` (cmd) in either script -- never a hardcoded list, so a
    launcher edit that starts referencing a new file is what drives the
    expected set, not a constant frozen in this test.
    """
    refs = set(_SH_STORE_REF.findall(sh_body))
    refs |= set(_CMD_STORE_REF.findall(cmd_body))
    return refs


# ---------------------------------------------------------------------------
# 1. The three viewer assets are tracked and not ignored.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", VIEWER_ASSETS)
def test_viewer_asset_is_tracked(name):
    assert _is_tracked(REPO_ROOT, "memory/" + name), (
        "%s is not tracked: a clone would ship without it" % name
    )


@pytest.mark.parametrize("name", VIEWER_ASSETS)
def test_viewer_asset_is_not_ignored(name):
    assert not _is_ignored(REPO_ROOT, "memory/" + name), (
        "%s matches a live .gitignore pattern -- if it were ever "
        "`git rm --cached`, the pattern would silently re-ignore it "
        "(design-docs/reports/wp7-memory-view-assets-20260816.md §2b)" % name
    )


# ---------------------------------------------------------------------------
# 2. Mutation-proof: the checker must flag a RE-ADDED ignore line, exercised
#    in both directions, against a throwaway repo -- never against this repo.
# ---------------------------------------------------------------------------


def test_ignore_checker_is_mutation_proof(tmp_path):
    repo = tmp_path / "throwaway-store"
    (repo / "memory").mkdir(parents=True)
    asset = repo / "memory" / "graph-view.html"
    asset.write_text("<html></html>", encoding="utf-8")

    assert _git(repo.parent, "init", "-q", str(repo)).returncode == 0
    assert (
        _git(
            repo, "config", "user.email", "wp7-mutation-proof@example.invalid"
        ).returncode
        == 0
    )
    assert _git(repo, "config", "user.name", "wp7-mutation-proof").returncode == 0
    assert _git(repo, "add", "memory/graph-view.html").returncode == 0
    assert _git(repo, "commit", "-q", "-m", "track the asset").returncode == 0

    # Direction 1: no ignore line exists yet -- the checker must say
    # "tracked, not ignored", matching the real store's target state.
    assert _is_tracked(repo, "memory/graph-view.html")
    assert not _is_ignored(repo, "memory/graph-view.html")

    # Direction 2: an ignore line is (re-)added to the working tree -- the
    # exact shape of the regression this repo lived through, where the
    # container engine's ensure() re-appended the pattern after the file was
    # already tracked. The file's TRACKED status is unaffected -- git never
    # untracks a path just because a later pattern matches it -- but the
    # checker must now report it as ignored.
    (repo / "memory" / ".gitignore").write_text("graph-view.html\n", encoding="utf-8")

    assert _is_tracked(repo, "memory/graph-view.html"), (
        "tracking must be unaffected by the ignore line -- this proves the "
        "scenario is the same one the real store hit, not a different bug"
    )
    assert _is_ignored(repo, "memory/graph-view.html"), (
        "the checker did not flag a freshly re-added ignore line against a "
        "tracked file -- it would have missed the exact regression WP-7 "
        "found in this repository's own history"
    )


def test_default_index_aware_check_would_have_missed_the_regression(tmp_path):
    """Not exercised by the shipped checker (it deliberately avoids this
    trap) -- documents WHY ``--no-index`` is required, by showing the
    default, index-aware ``git check-ignore`` stays silent on the exact same
    throwaway arrangement once the file is tracked. If this ever starts
    failing, git's own default behaviour changed and the module docstring's
    justification needs re-checking, not silent deletion."""
    repo = tmp_path / "throwaway-store-default-check"
    (repo / "memory").mkdir(parents=True)
    (repo / "memory" / "graph-view.html").write_text("<html></html>", encoding="utf-8")

    assert _git(repo.parent, "init", "-q", str(repo)).returncode == 0
    _git(repo, "config", "user.email", "wp7-mutation-proof@example.invalid")
    _git(repo, "config", "user.name", "wp7-mutation-proof")
    _git(repo, "add", "memory/graph-view.html")
    _git(repo, "commit", "-q", "-m", "track the asset")

    (repo / "memory" / ".gitignore").write_text("graph-view.html\n", encoding="utf-8")

    # Default, index-aware check: exit 1 (not reported as ignored) even
    # though a matching pattern now exists, BECAUSE the path is tracked.
    default_check = _git(repo, "check-ignore", "--", "memory/graph-view.html")
    assert default_check.returncode == 1, (
        "if this starts returning 0, the default check-ignore behaviour "
        "changed and the --no-index justification above should be re-read"
    )
    # The --no-index checker used by this suite still catches it.
    assert _is_ignored(repo, "memory/graph-view.html")


# ---------------------------------------------------------------------------
# 3. Everything the launchers reference at run time, inside the repo, is
#    tracked -- parsed from the launcher bodies, never hardcoded.
# ---------------------------------------------------------------------------


def test_launcher_referenced_files_are_parsed_and_non_empty():
    """Probe before asserting: fail loudly, not silently, if a future
    launcher rewrite stops referencing any repo-relative file at all -- an
    empty parse would otherwise make the next test vacuously pass."""
    sh_body = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    cmd_body = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    refs = _parse_repo_relative_references(sh_body, cmd_body)
    assert refs, (
        "the parser found no $STORE/<file> or %STORE%\\<file> reference in "
        "either launcher -- either the launchers changed shape or the "
        "parser regex needs updating; either way this must not go unnoticed"
    )


def test_launcher_referenced_files_are_tracked():
    sh_body = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    cmd_body = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    refs = _parse_repo_relative_references(sh_body, cmd_body)
    for name in sorted(refs):
        assert _is_tracked(REPO_ROOT, "memory/" + name), (
            "%s is referenced by a launcher at run time but is not tracked "
            "-- a clone would follow a reference to a file that never "
            "arrived" % name
        )
