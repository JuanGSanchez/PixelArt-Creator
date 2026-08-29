#!/usr/bin/env python3
"""cleanup.py — reclaim what the test runs generate, from OUTSIDE them (frozen copy).

This file is THE ORIGINAL, and every delivered system's `testing/cleanup.py`
is a byte-identical copy of it — a copy-fidelity subject like `memory_graph.py`
(`check_compliance.COPY_FIDELITY_ORIGINALS`, which names this path as the one
source for the filename `cleanup.py`). The sentence used to read "this file is
a byte-identical copy of `scripts/testing-template/cleanup.py`", which said of
itself what is true of its copies, and was read as a claim about the
orchestrator-design skill's OWN `testing/cleanup.py`. That file is not a copy
of this one and was never meant to be: measured 2026-08-26 it is 141 lines
and 5,677 bytes, roughly a third of this file, and it imports the skill
suite's `harness.workspace` for the very nomenclature this file defines for
itself. It is what the SKILL's own suite runs; the skill's `testing/` is
that suite, not a delivered system's, and the two were never one program.

It is the outer half of the system testing suite's cleanup contract
(`references/system-testing.md` §3.1, `references/product-testing.md` §2), and
it is also a delivered suite's single home for the temp-path nomenclature:
`conftest.py` imports its constants and helpers rather than restating them.

**Why an outer half exists.** The suite already cleans from the inside: a
workspace dies with its test, a file's leftovers die with the file, the run
directory dies with the session. All three are runner finalizers, and a
finalizer is a promise a *surviving* process keeps. A run that is KILLED — a
harness timeout, a Ctrl-C, a machine going to sleep — keeps none of them, and
that is precisely the run that leaves the most behind. So the last ring lives
outside the runner:

    python testing/cleanup.py                # reclaim what no live run owns
    python testing/cleanup.py --this-run     # reclaim only THIS identity's tree
    python testing/cleanup.py --all          # reclaim everything, owned or not
    python testing/cleanup.py --dry-run      # say what would go, remove nothing
    python testing/cleanup.py --json         # the same, machine-readable

**The universal form.** Nothing here is pytest-specific, which is the point:
the same contract carries to a suite written in any language. A run puts
everything it generates under one directory named for its owner, and cleanup
is "delete the directories whose owner is gone". A runner in another language
satisfies it by obeying the same two rules — one namespace per run, named for
the process — and by calling this script, or a short equivalent, from its own
`trap`/`finally`. `testing/run` and `testing/run.cmd` do that for this suite.

The shape, in full (`system-testing.md` §2.1):

    <TEMP_ROOT>/<SCOPE>/run-<RUNID>/<NNN>-<script-stem>-<test-function>/

SCOPE is `<project>-tests` locally and `CI-<project>` in CI — two kinds that
must never share a directory, because one kind's cleanup would then be able to
delete the other kind's live run. RUNID is the PID locally and the job identity
in CI, which is what makes reclamation key on **liveness, not age**.

Exit codes: 0 nothing left behind · 1 something could not be removed (said, not
swallowed) · 2 the temp root itself is unusable. Stdlib only, Python 3.8+.
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        # The FAILURE path prints an em dash ("COULD NOT REMOVE x — y"), and
        # a cp850/cp437 console cannot encode one: without this, the one
        # report that matters dies of an encoding error instead of naming
        # the file it could not reclaim
        # (`references/windows-compatibility.md` §6).
        _stream.reconfigure(encoding="utf-8", errors="replace")

TESTING_DIR = Path(__file__).resolve().parent
CONTAINER_ROOT = TESTING_DIR.parent

# Where THIS RUN puts its workspaces. Read by the harness, and dropped from
# every child it launches: it steers the suite, never the units under test.
TEMP_ROOT_VAR = "ORCH_TEST_TMP"
# The default when nothing is configured: the container's own scratch root,
# not the machine's. A CONTAINER-RELATIVE default is portable by construction
# — it is true on every machine that clones this system — which is what makes
# it allowed where a machine-absolute path (`D:/tmp`, `/var/tmp/...`) is not.
# `.tmp/` is excluded by the container allowlist, so it is untracked by
# construction, and it is the only root the system's sweeper may collect.
DEFAULT_TEMP_DIR = CONTAINER_ROOT / ".tmp"
# The project token of the SCOPE component: this container's own directory
# name. Derived, never typed — a literal shared by two containers on one
# machine-wide temp root would put both runs in one tree, where either one's
# cleanup can delete the other's live workspaces.
PROJECT = CONTAINER_ROOT.name
RUN_PREFIX = "run-"
# The test framework's own temp base (pytest's `--basetemp`), kept BESIDE the
# run directory rather than inside it, so a guard test asking for a path
# outside the run area still gets one. Both families are reclaimed together.
PYTEST_BASETEMP_PREFIX = "pytest-"
# One path component may not exceed this, counting the run-order prefix.
# Windows still has a 260-character ceiling for many APIs, and the units under
# test build deep paths inside whatever they are handed.
NAME_LIMIT = 50
# When a name must be cut, the cut is DETERMINISTIC: head + this many hex of
# the sha256 of the full name. Truncating without it silently merges two long
# names that share a prefix, which presents as one test overwriting another's
# fixtures rather than as a naming problem.
NAME_HASH_CHARS = 4
# Liveness settles ownership. Age is the fallback for the one case it cannot:
# a PID the OS has since recycled onto an unrelated process, or an owner token
# that is not a PID at all (a CI job identity).
STALE_RUN_SECONDS = 6 * 3600


def slug(text):
    """Alphanumerics, `-` and `_` survive; everything else becomes `-`."""
    return "".join(ch if (ch.isalnum() or ch in "-_") else "-"
                   for ch in str(text)).strip("-") or "t"


def component(text, limit=NAME_LIMIT):
    """One path component of the nomenclature, cut DETERMINISTICALLY."""
    safe = slug(text)
    if len(safe) <= limit:
        return safe
    digest = hashlib.sha256(str(text).encode("utf-8")).hexdigest()
    keep = limit - NAME_HASH_CHARS - 1
    return safe[:keep].rstrip("-_") + "-" + digest[:NAME_HASH_CHARS]


def unit_name(counter, label):
    """`<NNN>-<script-stem>-<test-function>` (`system-testing.md` §2.1).

    The runner's node id is the input, not the bare test name: the script stem
    is what lets a directory found on disk name the test that made it without
    a lookup.
    """
    body = str(label)
    if "::" in body:
        location, _, rest = body.partition("::")
        body = "{}-{}".format(Path(location).stem, rest.replace("::", "-"))
    prefix = "{:03d}-".format(counter)
    return prefix + component(body, NAME_LIMIT - len(prefix))


def in_ci(env=None):
    """Is this a CI run? `ORCH_TEST_CI` decides when it is set; otherwise the
    convention every provider shares (`CI=true`) does.

    It is asked as a question rather than assumed, because the answer changes
    the SCOPE, and a CI run that landed in the local scope would be reclaimable
    by a developer's suite — and vice versa.
    """
    env = os.environ if env is None else env
    explicit = str(env.get("ORCH_TEST_CI", "")).strip().lower()
    if explicit in ("1", "true", "yes"):
        return True
    if explicit in ("0", "false", "no"):
        return False
    return str(env.get("CI", "")).strip().lower() in ("1", "true", "yes")


def scope_name(project=PROJECT, ci=None, env=None):
    """`CI-<project>` for a CI run, `<project>-tests` for a local suite."""
    ci = in_ci(env) if ci is None else ci
    project = component(project)
    return ("CI-{}".format(project) if ci
            else component("{}-tests".format(project)))


def run_id(ci=None, env=None):
    """The RUN component's owner token: the PID locally, the job identity in
    CI. A CI runner recycles PIDs across jobs on one host and reports them
    from inside a container that does not share the host's process table, so
    the PID answers a different question there than the one being asked."""
    env = os.environ if env is None else env
    ci = in_ci(env) if ci is None else ci
    if not ci:
        return str(os.getpid())
    parts = [env.get("GITHUB_JOB") or env.get("CI_JOB_NAME")
             or env.get("BUILD_JOB") or "job",
             env.get("GITHUB_RUN_ID") or env.get("CI_PIPELINE_ID")
             or env.get("BUILD_BUILDID") or "",
             env.get("GITHUB_RUN_ATTEMPT") or env.get("CI_JOB_ID") or ""]
    return component("-".join(p for p in parts if p), NAME_LIMIT - len(RUN_PREFIX))


def owner_is_alive(owner):
    """Is `owner` a live process? Unknown -> True (never reclaim on a guess).

    A CI job identity is not a PID and is never resolvable here; it returns
    True and falls through to the age rule, so one job's cleanup can never
    delete a sibling job's live tree.

    Windows has no `kill(pid, 0)`: `os.kill` there is TerminateProcess, so
    asking with it would kill what it is asking about. Use OpenProcess and
    read the exit code — a handle can still be opened for a process that has
    exited but not been reaped, and the exit code is what separates the two.
    A handle that could NOT be opened is not an answer by itself: error 5
    (access denied) means the process is there and unqueryable, which is
    ALIVE (`references/windows-compatibility.md` §1).
    """
    try:
        pid = int(owner)
    except (TypeError, ValueError):
        return True
    if pid <= 0:
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        ERROR_ACCESS_DENIED = 5
        STILL_ACTIVE = 259
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                      False, pid)
        if not handle:
            # DENIED (5) means the process EXISTS and this one may not query
            # it — a different user, or elevated. `return False` here read
            # that as "no such process", and since the answer feeds
            # `sweep_stale`, a live run owned by an unqueryable PID had its
            # workspace deleted out from under it. §1 is explicit about this
            # exact line, and `lease.py` and `viewer/serve.py` both get it
            # right; this file cited §1 in its docstring and inverted it.
            return ctypes.get_last_error() == ERROR_ACCESS_DENIED
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True                   # could not tell — assume alive
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)                       # POSIX: signal 0 only probes
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                           # alive, owned by somebody else
    except OSError:
        return True
    return True


def resolve_temp_root(cli_value=None, env=None):
    """`--temp-root` > `ORCH_TEST_TMP` > the container's own `.tmp/`.

    Raises OSError when the resolved root cannot be written. Relocating a root
    the caller DID declare would run the suite somewhere they never asked for
    and never look — the failure mode this whole rule exists to prevent.
    """
    env = os.environ if env is None else env
    raw = cli_value or env.get(TEMP_ROOT_VAR) or DEFAULT_TEMP_DIR
    root = Path(str(raw).strip()).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    probe = root / ".write-probe-{}".format(os.getpid())
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    return root.resolve()


def _on_remove_error(func, path, _exc):
    """Clear the read-only bit (git objects, packfiles) and retry once."""
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        func(path)
    except OSError:
        pass


def remove_tree(path, guard_root, attempts=6):
    """Delete `path` recursively; True when it is gone.

    `guard_root` is the only place removal is permitted; anything else RAISES
    rather than deleting. That refusal is what makes an unconditional cleanup
    safe, and it is the same refusal CI rule 2 states where the blast radius
    is larger.
    """
    path, guard_root = Path(path), Path(guard_root).resolve()
    if not path.exists():
        return True
    resolved = path.resolve()
    if resolved == guard_root or guard_root not in resolved.parents:
        raise RuntimeError("refusing to delete {} — outside the temp root "
                           "{}".format(resolved, guard_root))
    for attempt in range(attempts):
        try:
            shutil.rmtree(str(resolved), onexc=_on_remove_error)
        except TypeError:                     # Python < 3.12
            shutil.rmtree(str(resolved), onerror=_on_remove_error)
        except OSError:
            pass
        if not resolved.exists():
            return True
        time.sleep(0.05 * (attempt + 1))      # a handle is still open
    return not resolved.exists()


def coverage_fragments(here):
    """Every `.coverage.<host>.<pid>.<rand>` beside this script, with its
    owner's liveness.

    THE FOURTH THING A KILLED RUN LEAVES. `run` / `run.cmd` measure the suite
    with `coverage --parallel-mode`, so every child process writes its own
    fragment and the runner folds them together afterwards with `combine`. A
    run that is KILLED never reaches the combine, and its fragments stay —
    hundreds of them after a few interrupted runs, and the next `combine`
    silently folds a previous run's data into this one's numbers.

    The PID is IN THE NAME, so liveness is decidable here exactly as it is for
    a namespace: a fragment whose writer is gone is reclaimable, and one whose
    writer is alive belongs to a run in progress and is left alone.
    """
    found = []
    here = Path(here)
    for entry in sorted(here.glob(".coverage.*")):
        if not entry.is_file():
            continue
        # `.coverage.<host>.pid<PID>.<rand>.<rand>` — the segment is
        # PREFIXED, so a positional index that expected a bare number found
        # `pid32688`, judged every fragment ownerless, and would have swept a
        # live run's data. Read the prefix, not the position.
        owner = ""
        for part in entry.name.split("."):
            if part.startswith("pid") and part[3:].isdigit():
                owner = part[3:]
                break
        found.append({"path": entry, "owner": owner,
                      "alive": bool(owner) and owner_is_alive(owner)})
    return found


def namespaces(base):
    """Every run namespace under `base`, with its owner and liveness."""
    found = []
    if not Path(base).is_dir():
        return found
    prefixes = (RUN_PREFIX, PYTEST_BASETEMP_PREFIX)
    for entry in sorted(Path(base).iterdir()):
        if not entry.is_dir():
            continue
        prefix = next((p for p in prefixes
                       if entry.name.startswith(p)), None)
        if prefix is None:
            continue
        owner = entry.name[len(prefix):]
        found.append({"path": entry, "owner": owner,
                      "alive": owner_is_alive(owner)})
    return found


def sweep_stale(base, keep=()):
    """Reclaim namespaces from runs that were killed. Returns the count.

    The predicate is **liveness, not age**: a run directory is named for its
    owner, so "is this debris?" is a question the OS can answer exactly. Age
    is a proxy that gets it wrong in both directions — it keeps debris for
    hours after the run died, and it would eventually collect a long-running
    session that is still working. Age survives only as the fallback for an
    owner that cannot be resolved, so a recycled PID or a CI job token never
    deletes a live run's workspaces.
    """
    base = Path(base)
    keep = {Path(k).resolve() for k in keep}
    now, removed = time.time(), 0
    for item in namespaces(base):
        entry = item["path"]
        if entry.resolve() in keep:
            continue
        if item["owner"].isdigit() and not item["alive"]:
            reclaimable = True                # the fact: nobody owns this
        else:
            try:
                reclaimable = (now - entry.stat().st_mtime) >= STALE_RUN_SECONDS
            except OSError:
                continue
        if not reclaimable:
            continue
        try:
            if remove_tree(entry, base):
                removed += 1
        except RuntimeError:
            pass
    return removed


def measure(path):
    files = total = 0
    for root, _dirs, names in os.walk(str(path)):
        for name in names:
            files += 1
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return files, total


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reclaim the directories the test runs generate.")
    parser.add_argument("--temp-root", default=None,
                        help="override the configured temp root "
                             "(default: ${} or the container's .tmp/)"
                             .format(TEMP_ROOT_VAR))
    parser.add_argument("--all", action="store_true",
                        help="reclaim every namespace in this scope, "
                             "including one a live run still owns (use only "
                             "when no run is active)")
    parser.add_argument("--this-run", action="store_true",
                        help="reclaim only the namespaces THIS identity owns "
                             "— the CI form: a job deletes its own leaf and "
                             "can never reach a sibling job's live tree")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be removed, remove nothing")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if args.all and args.this_run:
        print("cleanup: --all and --this-run contradict each other",
              file=sys.stderr)
        return 2
    try:
        root = resolve_temp_root(args.temp_root)
    except OSError as exc:
        print("cleanup: temp root unusable: {}".format(exc), file=sys.stderr)
        return 2
    scope = scope_name()
    base = root / scope
    mine = {RUN_PREFIX + run_id(), PYTEST_BASETEMP_PREFIX + run_id()}

    removed, kept, failed = [], [], []
    for item in namespaces(base):
        path, owner = item["path"], item["owner"]
        if args.this_run:
            reclaim = path.name in mine
            reason = "not this run's namespace"
        elif args.all:
            reclaim, reason = True, ""
        else:
            reclaim = not item["alive"]
            reason = "owner alive"
        if not reclaim:
            # Never delete a live run's workspace out from under it: this
            # script is routinely invoked while another suite is running.
            kept.append({"path": str(path), "owner": owner, "reason": reason})
            continue
        files, size = measure(path)
        record = {"path": str(path), "owner": owner,
                  "files": files, "bytes": size}
        if args.dry_run:
            removed.append(record)
            continue
        try:
            gone = remove_tree(path, base)
        except RuntimeError as exc:           # the guard: outside the root
            failed.append(dict(record, error=str(exc)))
            continue
        (removed if gone else failed).append(record)

    # The coverage fragments a killed run left beside this script. Same
    # predicate as a namespace — the owner is gone — and the same refusal to
    # touch a live run's data.
    fragments = []
    for item in coverage_fragments(Path(__file__).resolve().parent):
        if item["alive"] and not args.all:
            kept.append({"path": str(item["path"]), "owner": item["owner"],
                         "reason": "owner alive"})
            continue
        record = {"path": str(item["path"]), "owner": item["owner"],
                  "files": 1, "bytes": item["path"].stat().st_size
                  if item["path"].exists() else 0}
        if args.dry_run:
            fragments.append(record)
            continue
        try:
            item["path"].unlink()
            fragments.append(record)
        except OSError as exc:
            record["error"] = str(exc)
            failed.append(record)
    removed.extend(fragments)

    payload = {"temp_root": str(root), "scope": scope, "base": str(base),
               "ci": in_ci(), "run_id": run_id(), "dry_run": args.dry_run,
               "removed": removed, "kept": kept, "failed": failed,
               "coverage_fragments": len(fragments),
               "bytes_reclaimed": sum(r["bytes"] for r in removed),
               "verdict": "FAILED" if failed else "OK"}
    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        # CI safety rule 4: the resolved root is logged BEFORE anything goes,
        # so a wrongly scoped cleanup is visible in the run log, not silent.
        verb = "would remove" if args.dry_run else "removed"
        print("cleanup: root {}  scope {}".format(root, scope))
        print("cleanup: {} {} namespace(s), {:.1f} MB; {} kept; {} coverage "
              "fragment(s)".format(
                  verb, len(removed) - len(fragments),
                  payload["bytes_reclaimed"] / 1e6, len(kept), len(fragments)))
        for record in removed:
            print("  {} {}  ({} files)".format(
                verb.split()[-1], record["path"], record["files"]))
        for record in failed:
            print("  COULD NOT REMOVE {} — {}".format(
                record["path"], record.get("error", "still in use")),
                file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
