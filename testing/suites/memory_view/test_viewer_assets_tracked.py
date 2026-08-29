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

REPO_ROOT = Path(__file__).resolve().parents[3]
STORE = REPO_ROOT / "memory"

# The three page assets WP-7 tracks (ground truth: the WP-7 findings report).
VIEWER_ASSETS = ("graph-view.html", "graph-view.css", "graph-view.js")

# A repo-relative reference inside a launcher looks like `$HERE/<file>` in
# the POSIX script or `%HERE%\<file>` in the batch script -- always with a
# file extension, which is what distinguishes an actual file reference from a
# bare directory walk like `$HERE/..` or `--store "$HERE"`.
#
# HISTORY: the launcher's own directory variable was renamed from `$STORE` /
# `%STORE%` to `$HERE` / `%HERE%` -- this is why the pattern targets `$HERE`,
# not a leftover of the old name.
_SH_HERE_REF = re.compile(r"\$HERE/([\w.\-]+\.[A-Za-z0-9]+)")
_CMD_HERE_REF = re.compile(r"%HERE%\\+([\w.\-]+\.[A-Za-z0-9]+)")

# `$C/scripts/...` (sh) and `!C!\scripts\...` (cmd) are the BOUNDED UPWARD
# WALK for an orchestration `scripts/memory_graph.py`: `$C`/`!C!` is
# reassigned by `dirname`/`for %%D in ("!C!\..")` on each iteration and, once
# it climbs past the repository root, no longer names a repo-relative path at
# all -- it is never repo-relative and can never be tracked here, structurally
# excluded by matching only the launcher's OWN directory variable ($HERE /
# %HERE%), never the walk cursor.

# A reference is a HARD REQUIREMENT -- the launcher cannot proceed without it
# -- only when the launcher tests for its absence and EXITS on that branch.
# `if [ -f ... ]` / `if exist ...` (a POSITIVE existence probe, "use it if
# it's there") is how the launcher treats an OPTIONAL, best-effort file: its
# own docstring in `memory_views.py`'s `_engine()` says as much for
# `memory_graph.py` -- "deliberately NOT part of the vendored package -- a
# bare clone opens its viewer, it does not need the writer." Absence there is
# a DESIGNED state, not a defect, and asserting it must be tracked would be
# false. `if [ ! -f ... ]; then ... exit ...; fi` / `if not exist ... ( ...
# exit /b ... )` (a NEGATED probe that aborts) is how the launcher treats a
# file it cannot run without -- that is the one invariant worth protecting:
# "every file the launcher REQUIRES unconditionally must be tracked."
#
# Filename-agnostic and compiled once (rather than built per-filename with
# `re.escape(name)` + `.format()`): every guarded block is found in a single
# pass and then matched, in Python, against the specific filename under
# test -- so the pattern the launcher actually wrote never has to be
# reconstructed from a template.
_SH_MANDATORY_GUARD = re.compile(
    r'if\s*\[\s*!\s*-f\s*"\$HERE/([\w.\-]+\.[A-Za-z0-9]+)"\s*\][^\n]*\n(.*?)\nfi\b',
    re.DOTALL,
)
_CMD_MANDATORY_GUARD = re.compile(
    r'if not exist "%HERE%\\+([\w.\-]+\.[A-Za-z0-9]+)" \((.*?)\n\)', re.DOTALL
)


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

    Returns the UNION of filenames referenced via ``$HERE/<file>`` (sh) or
    ``%HERE%\\<file>`` (cmd) in either script -- never a hardcoded list, so a
    launcher edit that starts referencing a new file is what drives the
    expected set, not a constant frozen in this test. This is EVERY
    reference, required or merely probed -- the non-vacuity check
    (``test_launcher_referenced_files_are_parsed_and_non_empty``) reads this
    one, so it stays non-empty as long as the launcher touches ANY
    repo-relative file at all, whether or not that file turns out to be a
    hard requirement. See ``_required_repo_relative_references`` for the
    narrower, tracked-ness-relevant set.
    """
    refs = set(_SH_HERE_REF.findall(sh_body))
    refs |= set(_CMD_HERE_REF.findall(cmd_body))
    return refs


def _sh_is_mandatory(body: str, filename: str) -> bool:
    """True if the sh launcher EXITS when ``filename`` (under ``$HERE``) is
    missing.

    Finds every ``if [ ! -f "$HERE/<name>" ]; then ... fi`` block, keeps the
    one whose ``<name>`` equals ``filename``, and checks that block for an
    ``exit`` -- the launcher's own "I cannot proceed" signal. A file only
    ever probed the OTHER way round (``if [ -f ... ]``, "use it if it
    happens to be there") never matches this guard shape at all and is
    correctly read as a candidate, not a requirement.
    """
    return any(
        name == filename and re.search(r"\bexit\b", block)
        for name, block in _SH_MANDATORY_GUARD.findall(body)
    )


def _cmd_is_mandatory(body: str, filename: str) -> bool:
    """True if the cmd launcher EXITS when ``filename`` (under ``%HERE%``)
    is missing. Mirrors ``_sh_is_mandatory`` for the batch syntax:
    ``if not exist "%HERE%\\<name>" ( ... )`` guarded blocks are matched by
    ``<name>`` and checked for ``exit /b``.
    """
    return any(
        name == filename and re.search(r"\bexit\s*/b", block)
        for name, block in _CMD_MANDATORY_GUARD.findall(body)
    )


def _required_repo_relative_references(sh_body: str, cmd_body: str) -> set:
    """The subset of ``_parse_repo_relative_references`` the launchers
    cannot run without -- excluding a file that is only ever PROBED with an
    existence test before an optional use (``memory_graph.py``: "deliberately
    NOT part of the vendored package", per ``memory_views.py``'s own
    ``_engine()`` docstring) and structurally excluding the bounded upward
    walk's ``$C``/``!C!`` cursor, which is never repo-relative in the first
    place (see the module-level comment above the guard patterns).

    A reference counts as required if EITHER launcher aborts on its absence
    -- checked per-file, never assumed, so a future launcher edit that turns
    a hard requirement into a soft fallback (or the reverse) is exactly what
    changes this set, not a constant this test bakes in.
    """
    refs = _parse_repo_relative_references(sh_body, cmd_body)
    return {
        name
        for name in refs
        if _sh_is_mandatory(sh_body, name) or _cmd_is_mandatory(cmd_body, name)
    }


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
    empty parse would otherwise make the next two tests vacuously pass.

    Deliberately the WIDE parse (required + merely-probed) -- this only
    proves the parser itself still finds something, not that any of it is a
    hard requirement."""
    sh_body = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    cmd_body = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    refs = _parse_repo_relative_references(sh_body, cmd_body)
    assert refs, (
        "the parser found no $HERE/<file> or %HERE%\\<file> reference in "
        "either launcher -- either the launchers changed shape or the "
        "parser regex needs updating; either way this must not go unnoticed"
    )


def test_launcher_required_files_are_parsed_and_non_empty():
    """Same probe-before-asserting guard as above, for the NARROWER required
    set: ``test_launcher_referenced_files_are_tracked`` below loops over
    exactly this set, and an empty required set would make that loop pass
    over nothing -- the identical vacuity trap the wide-parse guard exists to
    catch, one level downstream. If this ever finds zero required files,
    either every reference became probed (unlikely -- the launcher cannot
    run without ``memory_views.py``) or the mandatory-guard regex needs
    updating to match a reshaped launcher; either way, silence here is not an
    acceptable outcome."""
    sh_body = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    cmd_body = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    required = _required_repo_relative_references(sh_body, cmd_body)
    assert required, (
        "no reference was classified as a hard requirement -- either the "
        "launchers no longer abort on a missing file, or the mandatory-guard "
        "pattern (a negated `-f`/`exist` test followed by `exit`) needs "
        "updating to match how the launcher currently spells it"
    )


def test_launcher_referenced_files_are_tracked():
    """Only the REQUIRED subset -- a file the launcher merely PROBES with
    ``-f``/``exist`` before an optional use (``memory_graph.py``) is a
    candidate, not a requirement, and its absence from this repository's
    index is a designed state, not a defect. Asserting it must be tracked
    would be false: it is deliberately excluded from the vendored package
    (``memory_views.py``'s own ``_engine()`` docstring), and a bare clone is
    meant to open its viewer without it."""
    sh_body = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    cmd_body = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    required = _required_repo_relative_references(sh_body, cmd_body)
    for name in sorted(required):
        assert _is_tracked(REPO_ROOT, "memory/" + name), (
            "%s is a hard requirement of the launcher (it aborts without it) "
            "but is not tracked -- a clone would follow a reference to a "
            "file that never arrived" % name
        )
