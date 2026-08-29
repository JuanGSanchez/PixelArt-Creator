"""This repository's own memory viewer: the launcher shipped beside the map.

`memory/` holds this repository's memory store — its own graph, its own
history, independent of any other store. `memory/memory-view.cmd` and
`memory/memory-view.sh` are how somebody opens it: they refresh this
repository's map, start the viewer for THIS store only, and open a browser on
it. They are SOURCE and therefore tracked; the rendered `graph-view.html` beside
them is DERIVED and gitignored.

WHY THIS ROOT IS `testing/suites/memory_view/` AND NOT `testing/suites/memory/`: a directory
named `memory` anywhere but the repository root is the mistake the layout
invariant names, and the structure guard refuses writes into one — correctly,
since a second thing called `memory` beside the real store is exactly the
confusion worth preventing. The root is named for what it tests.

WHAT THIS SUITE DELIBERATELY DOES NOT TEST, so the two suites do not duplicate
each other: the viewer SERVER — live re-reads, auto-shutdown, the port walk,
the snapshot's probe — lives in the orchestration container above this
repository and is covered there, against a synthetic container, by that
container's own suite. Repeating it here would require a container this
repository must not assume exists, and would test the same code twice.

What IS this repository's business, and is tested here:

  * the launcher ships, for both platforms;
  * it is wired BY POSITION — no absolute path, so a clone works anywhere;
  * it points at THIS store, not at some other repository's;
  * it picks an interpreter by RUNNING one (the Windows Store alias for
    `python3` is a real file on PATH that is not Python);
  * taken away from its container it SAYS so and names the snapshot that still
    works, rather than failing silently.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
STORE = REPO_ROOT / "memory"
LAUNCHERS = ("memory-view.cmd", "memory-view.sh")


@pytest.mark.parametrize("name", LAUNCHERS)
def test_the_launcher_ships_with_the_store(name):
    launcher = STORE / name
    assert launcher.is_file(), (
        "%s is missing: this repository's memory could be rendered but not "
        "opened" % name
    )
    assert launcher.stat().st_size > 0


@pytest.mark.parametrize("name", LAUNCHERS)
def test_the_launcher_is_tracked_not_ignored(name):
    """The rendered page is derived and ignored; the launcher is source. If it
    were ignored it would vanish from every clone — which is exactly the defect
    that moved it here."""
    done = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "--", "memory/" + name],
        capture_output=True,
        text=True,
    )
    assert done.returncode != 0, "%s is gitignored; it must ship" % name


def test_the_shell_launcher_is_executable_in_git():
    """REGRESSION. git records the execute bit in the blob mode, and it was
    recorded as 100644: every Linux and macOS clone got a `memory-view.sh` that
    answers "Permission denied", with nothing on the file to explain why. The
    bit has to be in the INDEX -- a chmod in one working tree ships nothing."""
    done = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-s", "--", "memory/memory-view.sh"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0 and done.stdout, "the launcher is not tracked"
    mode = done.stdout.split()[0]
    assert mode == "100755", (
        "memory-view.sh is recorded as %s; a clone cannot execute it" % mode
    )


def test_each_platform_is_told_which_file_is_its_own():
    """A .sh has no execute association on Windows, so clicking it offers to
    open it in an editor -- correct behaviour that reads as a broken launcher.
    Each file names the other and says which platform it belongs to."""
    sh = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    cmd = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    assert "memory-view.cmd" in sh, "the shell launcher never names the Windows one"
    assert "memory-view.sh" in cmd, "the Windows launcher never names the shell one"


@pytest.mark.parametrize("name", LAUNCHERS)
def test_the_launcher_carries_no_absolute_path(name):
    """It must resolve its own store from its own location. An absolute path
    would break on any clone, and would leak one machine's layout into the
    repository."""
    body = (STORE / name).read_text("utf-8", errors="replace")
    # The lookbehind matters: a bare `[A-Za-z]:[\\/]` also matches the `e:/`
    # inside "file://", which both launchers mention when they explain why a
    # served page beats a snapshot. A drive letter is preceded by a boundary.
    assert not re.search(
        r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]", body
    ), "a Windows path is baked in"
    assert "/home/" not in body and "/Users/" not in body  # portability: ok
    assert ("dirname" in body) or ("%~dp0" in body), "it must derive its own location"


@pytest.mark.parametrize("name", LAUNCHERS)
def test_the_launcher_serves_this_store_only(name):
    """Each repository's memory is independent. A launcher that served every
    store it could find would show this repository somebody else's history."""
    body = (STORE / name).read_text("utf-8", errors="replace")
    assert "--store" in body, "it must scope the viewer to one store"
    assert "serve" in body


def test_the_sh_launcher_probes_the_interpreter_by_running_it():
    """REGRESSION. `command -v python3` succeeds on a machine that only has
    the Microsoft Store alias stub on PATH -- a real file that is not Python:
    it prints an install advert and exits. Existence is not availability, so
    the probe has to execute something, not merely locate it.

    This is split from the `.cmd` variant (below) because the two platforms
    use different interpreter names -- `py -3` is a Windows-only launcher
    syntax that does not exist on POSIX shells, and a single parametrized
    assertion that demanded `"py -3"` of BOTH files was over-specification:
    it happened to pass only because `.sh` also contained the literal
    substring `"py"` (one of the candidate names in its `for cand in python3
    python py` shortlist), not because it ran a Windows launcher. See
    ``test_default_index_aware_check_would_have_missed_the_regression``'s
    sibling module for the same shape of trap in the assets suite.
    """
    body = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    assert "import sys" in body, "the interpreter probe must RUN the interpreter"
    # The probe must run a SHORTLISTED CANDIDATE variable, not merely mention
    # the string "import sys" somewhere unrelated (e.g. in a comment).
    assert re.search(r'"\$\w+"\s+-c\s+"import sys"', body), (
        "the probe must invoke the shortlisted candidate by variable, "
        'e.g. "$cand" -c "import sys"'
    )


def test_the_cmd_launcher_probes_the_interpreter_by_running_it():
    """REGRESSION. `where python` succeeds on Windows even when `python` on
    PATH is the Microsoft Store alias stub: a real file that prints an
    install advert and exits rather than being a working interpreter. The
    probe has to execute something, not merely locate it -- and `py -3` is
    the correct Windows launcher syntax to try first."""
    body = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    assert "import sys" in body, "the interpreter probe must RUN the interpreter"
    assert "py -3" in body, "py -3 is the correct launcher on Windows"


@pytest.mark.parametrize("name", LAUNCHERS)
def test_without_a_container_it_says_so_and_names_the_snapshot(name):
    """A clone taken away from its orchestration container has no viewer
    server. Directive 12: it must return an explicit answer, not fail quietly —
    and there IS still something to read."""
    body = (STORE / name).read_text("utf-8", errors="replace")
    assert "graph-view.html" in body, "it must name the snapshot that works"
    assert "memory_views.py" in body, "it must name what it looked for"


def test_the_two_launchers_agree_about_what_they_do():
    """Two platforms, one behaviour. A divergence here is how a Windows user
    and a Linux user end up looking at different things."""
    cmd = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    sh = (STORE / "memory-view.sh").read_text("utf-8", errors="replace")
    for token in (
        "memory_graph.py",
        "memory_views.py",
        "serve",
        "--store",
        "--open-browser",
        "graph-view.html",
    ):
        assert token in cmd, "cmd launcher lost %r" % token
        assert token in sh, "sh launcher lost %r" % token


def test_the_store_still_holds_its_own_role_and_map():
    """The launcher is only useful beside a real store; this pins the shape it
    assumes rather than letting a silent reorganisation break it."""
    assert (STORE / "store-role.json").is_file()
    assert (STORE / "graph" / "nodes.jsonl").is_file()
    assert (STORE / "MEMORY-INDEX.md").is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="cmd is Windows-only")
def test_the_cmd_launcher_is_batch_not_shell():
    body = (STORE / "memory-view.cmd").read_text("utf-8", errors="replace")
    assert body.lstrip().lower().startswith("@echo off")
