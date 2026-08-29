#!/usr/bin/env python3
"""Serve ONE memory store's viewer, live, from the store it lives in.

WHAT THIS FIXES
---------------
`memory_viz.py` renders a STATIC page: the whole graph, and since `--commits`
the whole commit history, substituted into the frozen template at generation
time. Nothing regenerates it — the git hooks refresh the STORE, not the VIEW —
so the page keeps showing the repository as it stood when somebody last ran the
renderer by hand. A viewer that quietly answers with last week's repository is
worse than no viewer, because it is believed.

`serve` rebuilds the page from the store's logs and the repository's own
`git log` ON EVERY REQUEST, and an injected poller reloads it by itself when a
cheap fingerprint moves. `render` keeps the offline path for a machine where
running a server is not wanted.

IT RENDERS NOTHING ITSELF (P9). Every byte of graph data and every line of
viewer JavaScript comes from `memory_viz.py` and the frozen `memory-viewer/`
assets beside it. This file imports that module and calls its functions; it
does not re-implement, patch, or vendor any part of it. An embedded copy would
diverge from the frozen original silently, which is the exact failure the
fidelity gate exists to prevent.

ONE STORE, ONE SERVER, NO NEIGHBOURS
------------------------------------
This script serves exactly the store it is pointed at. It does not discover
other stores, does not scan for other viewers, and cannot be reached by one:

  * its port comes from the MEMORY block of the one allocation table
    (`viewer_ports.py`), derived from the store's own path, so two stores get
    two ports without either knowing the other exists;
  * a second launch of the SAME store finds that store's own server and opens
    a tab on it instead of raising a duplicate — identity proven by asking the
    server which store PATH it serves, never by the port number, because a
    port says nothing about who holds it;
  * when every port in the block is held, it prints the named exit from the
    allocation table and stops. It never falls back to an address outside the
    table: a viewer nobody can predict is the collision that table ends.

LIFECYCLE: LOOK, AND CLOSE
--------------------------
This viewer stops when its last tab closes, after a short grace period. That
is deliberately NOT the design viewer's fixed keep-alive: opening a memory map
is a question being asked, not a surface being kept, and a server per store
left running after the answer was read is how a machine collects processes
nobody can account for. The divergence is documented per viewer type in
`references/viewer-protocol.md` §6.1.

Usage
    py memory_views.py serve   --store <dir> [--open-browser] [--once]
    py memory_views.py render  --store <dir> [--out <path>]
    py memory_views.py install --store <dir>
    py memory_views.py engine-missing --store <dir>   (said by a launcher)
"""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent

# This viewer's KIND in the one allocation table.
VIEWER_KIND = "memory"
LAUNCHER_CMD = "memory-view.cmd"
LAUNCHER_SH = "memory-view.sh"

# How often the page re-checks the fingerprint, and how long a server waits
# after its last tab goes away before stopping. The grace is not politeness:
# a reload is a tab closing and another opening, and a server that stopped
# between the two would take itself down every time the user pressed F5.
DEFAULT_POLL_SECONDS = 5
GRACE_SECONDS = 45
# A page that never says hello at all — a tab that was opened and immediately
# abandoned, or a probe — must not hold the server forever either.
IDLE_SECONDS = 90


# --------------------------------------------------------------------------
# loading THIS file's own siblings
# --------------------------------------------------------------------------
#
# UPSTREAM NOTE (this file is a recorded fork). The three helpers below are a
# DEFECT FIX, not a local preference, and they belong upstream unchanged. The
# skill original's `_load_sibling` inserts its folder at `sys.path[0]` and
# calls `__import__(name)` — which cannot do what it is written to do:
# `__import__` returns `sys.modules[name]` when the name is already loaded and
# never consults `sys.path` at all. `viewer_ports.py`, `viewer_serving.py` and
# `product_boundary.py` are each vendored into BOTH a store (by
# `memory_views.py install`) and a `testing/` (by `coverage_views.py install`),
# beside the skill's own `scripts/` originals — three copies, maintained by
# two independent install verbs — so whichever copy was imported first
# answered for all three. Measured: with `testing/` on `PYTHONPATH`, which is
# what `testing/run` gives every child process it spawns, the memory viewer
# bound `testing/viewer_ports`, `testing/viewer_serving` and
# `testing/product_boundary`.
#
# Upstream should take the same shape in both viewers: load by FILE PATH with
# `importlib.util`, under a `sys.modules` key derived from that path. It is a
# COPY, not a move — the two viewers do not import each other, and one
# viewer reaching for the other's loader would undo the property that lets a
# repository be cloned alone.

def _sibling_key(path):
    """A `sys.modules` key derived from the FILE, never from the bare name.

    Three copies of each vendored module live in one repository — the
    container's `scripts/`, every store's vendored package, every
    `testing/`'s — and two independent install verbs maintain them, so they
    can drift. A digest of the absolute path gives each copy a key of its
    own: two copies can never share one, and the key still names a findable
    module, which is what a dataclass, a pickle and a traceback each need.

    `normcase` because one file spelled two ways is one file, and two keys
    for it would be two module objects holding two copies of its state.
    """
    digest = hashlib.sha1(
        os.path.normcase(str(path)).encode("utf-8", "replace")).hexdigest()
    return "_viewer_sibling_%s_%s" % (path.stem, digest[:12])


@contextlib.contextmanager
def _folder_leading(folder):
    """`folder` first on `sys.path`, competing copies set aside, during exec.

    A module being loaded may import ITS OWN siblings by bare name —
    `memory_graph.py` does exactly that for `product_boundary` and `lease`,
    inside a `try/except ImportError` that degrades to None in silence — and
    those imports run through the ordinary machinery, which a loader cannot
    reach into. So this sets the two things that machinery reads: the folder
    leads `sys.path`, and the `sys.modules` entries for the bare names THIS
    FOLDER HAS ITS OWN COPY OF are lifted out, so the cache cannot answer
    with another copy's before `sys.path` is ever consulted.

    Only names this folder actually carries are touched, and every one is put
    back afterwards: the module being loaded keeps the references it bound
    while they were in force, and nothing outside it sees a change. The
    `sys.path` entry is left in place, exactly as this loader always left it —
    withdrawing it would be a second behaviour change riding along with a fix.
    """
    folder = Path(folder)
    try:
        siblings = [p for p in folder.iterdir() if p.suffix == ".py"]
    except OSError:
        siblings = []
    shadowed = {}
    for sibling in siblings:
        loaded = sys.modules.get(sibling.stem)
        if loaded is None:
            continue
        where = getattr(loaded, "__file__", None)
        if where and (os.path.normcase(str(Path(where).resolve()))
                      == os.path.normcase(str(sibling.resolve()))):
            continue                      # already this folder's own copy
        shadowed[sibling.stem] = loaded
    sys.path.insert(0, str(folder))
    for stem in shadowed:
        del sys.modules[stem]
    try:
        yield
    finally:
        sys.modules.update(shadowed)


def _load_module(path, what):
    """Execute `path` as a module of its own, under its path-derived key."""
    key = _sibling_key(path)
    loaded = sys.modules.get(key)
    if loaded is not None:
        return loaded
    spec = importlib.util.spec_from_file_location(key, str(path))
    if spec is None or spec.loader is None:
        sys.exit(json.dumps({
            "status": "BLOCKED",
            "error": "%s cannot be loaded from %s: Python does not recognise "
                     "that file as an importable module" % (what, path),
            "hint": "restore it from the orchestrator-design skill",
        }))
    module = importlib.util.module_from_spec(spec)
    # In the table BEFORE exec, under the path-derived key: a module is
    # looked up by its own `__module__` while it is still executing.
    sys.modules[key] = module
    try:
        with _folder_leading(path.parent):
            spec.loader.exec_module(module)
    except BaseException:
        # A half-executed module left behind would be handed out whole.
        sys.modules.pop(key, None)
        raise
    return module


def _load_sibling(name, what):
    """Import a module that ships beside this file.

    Both layouts are supported deliberately: the skill's own `scripts/`, and a
    store into which the whole package has been vendored so the repository
    works when cloned alone. A copy of either module's contents here instead
    of an import is the silent divergence the fidelity gate exists to catch.

    WHY NOT `__import__`. This used to put the chosen folder at `sys.path[0]`
    and call `__import__(name)` — which looks like it guarantees the local
    copy and does not. `__import__` returns `sys.modules[name]` whenever the
    name is already loaded, and never consults `sys.path` at all. With three
    copies of each vendored module in one repository, whichever was imported
    FIRST answered for all of them. It is reachable in ordinary operation:
    `testing/run` puts `testing/` on `PYTHONPATH` for every child process it
    spawns, so a child that touches the coverage viewer and then the memory
    viewer bound `testing/viewer_ports` into the memory viewer. Harmless
    while the bytes match; a real defect the moment the two vendored sets
    diverge — which is exactly what two independent install verbs make
    possible. The fix is to load by FILE PATH under a key derived from that
    path (`_load_module`), so a bare name already in `sys.modules` cannot
    answer for a copy it is not.
    """
    for folder in (BASE, BASE.parent):
        path = folder / (name + ".py")
        if path.is_file():
            return _load_module(path.resolve(), what)
    sys.exit(json.dumps({
        "status": "BLOCKED",
        "error": "{} is missing: {}.py must ship beside this script".format(
            what, name),
        "hint": "restore it from the orchestrator-design skill, or re-run "
                "`memory_views.py install --store <dir>` from a tree that "
                "has it",
    }))


memory_viz = _load_sibling("memory_viz", "the renderer")
ports = _load_sibling("viewer_ports", "the port allocation table")
serving = _load_sibling("viewer_serving", "the shared serving floor")
# Vendored with the rest of the package deliberately: `install` WRITES, and a
# copy of this script that shipped without the boundary it is gated by would
# be a copy with the gate removed. It is loaded the same way as the others so
# a store cloned alone still refuses what the skill refuses.
boundary = _load_sibling("product_boundary", "the product boundary")

# The page written by `install`: a BOOTSTRAP, tracked in git, holding no
# records. It fills itself from a running viewer. `render`'s offline
# snapshot goes somewhere else on purpose. BOTH NAMES COME FROM THE
# RENDERER, which writes the second one: two modules holding the same two
# filenames is how they came to be one filename in the first place.
BOOTSTRAP_NAME = memory_viz.BOOTSTRAP_NAME
SNAPSHOT_NAME = memory_viz.SNAPSHOT_NAME


def _engine():
    """The store engine, loaded by `install` alone.

    `memory_graph.py` is deliberately NOT part of the vendored package — a
    bare clone opens its viewer, it does not need the writer — so this
    import is made where it is needed instead of at module scope: `serve`
    and `render` must keep working in a store that carries only the
    package. `install` genuinely needs it: the retired-ignore-line prune
    is the engine's, and a second copy here would be a second writer of
    the one file `gitignore-doctrine.md` gives a single owner.
    """
    return _load_sibling("memory_graph", "the store engine")


# --------------------------------------------------------------------------
# the branch a write would land on
# --------------------------------------------------------------------------
#
# `install` writes TRACKED files — the vendored package, the bootstrap page,
# two launchers, a `.gitignore` line — into a repository. Run against that
# repository's `main` it puts them straight onto the branch a pull request is
# supposed to protect, and nothing here noticed. `product_boundary` answers a
# different question (WHOSE repository is this), and answers it well; a
# product's OWN system passing `--product-self` is legitimate and still must
# not commit to `main` by hand. So this is a second gate, not a variation of
# the first, and `--product-self` is not a way past it.
#
# THREE QUESTIONS, KEPT SEPARATE. `product_boundary.guard` asks "is this a
# product?"; `--product-self` answers "yes, and I am its own system, let me
# write"; this asks "fine — but not onto its `main`". Folding the third into
# `guard()` would make the second an answer to it too, which is exactly the
# bypass being closed. It is asked SECOND, after the boundary, so a container
# reaching into a product still gets the boundary's refusal — the one that
# names the right remedy for that mistake.
#
# IT READS GIT'S FILES, IT DOES NOT RUN GIT — the reason
# `product_boundary.repository_root` gives: this is on the write path of every
# installer, and it must answer the same way where git is absent, where it is
# a stub, and where it hangs.
#
# UPSTREAM NOTE (this file is a recorded fork). These five helpers belong in
# `product_boundary.py` beside `guard()` / `enforce()`, called by both viewers
# and by `container_repo.py`. They are duplicated into the two viewers only
# because this change's declared write targets were the two viewer files;
# porting them upstream is a move, not a rewrite.

PROTECTED_BRANCHES = ("main", "master")


def _git_dir(repo):
    """`repo`'s git directory: a `.git` folder, or the one a worktree names.

    A LINKED WORKTREE — which is exactly how a `fix-…` branch is checked out
    beside `main` here — carries a `.git` FILE reading `gitdir: <path>`. Its
    HEAD lives at that path, and HEAD is the whole question, so a reader that
    handled only the folder case would see no branch at all and let every
    worktree through.
    """
    dot = Path(repo) / ".git"
    if dot.is_dir():
        return dot
    if dot.is_file():
        try:
            text = dot.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        for line in text.splitlines():
            if line.startswith("gitdir:"):
                target = Path(line.split(":", 1)[1].strip())
                if not target.is_absolute():
                    target = Path(repo) / target
                return target if target.is_dir() else None
    return None


def _common_dir(gitdir):
    """Where the refs live — which is not always where HEAD does.

    A linked worktree's git directory holds its own HEAD but shares the
    primary repository's refs, and names that shared directory in
    `commondir`. Looking for `refs/heads/<branch>` in the worktree's own
    directory would find nothing and read as "no commit yet".
    """
    marker = Path(gitdir) / "commondir"
    if marker.is_file():
        try:
            rel = marker.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return Path(gitdir)
        if rel:
            candidate = Path(rel)
            if not candidate.is_absolute():
                candidate = Path(gitdir) / candidate
            return candidate
    return Path(gitdir)


def _current_branch(gitdir):
    """The branch HEAD is on, or None when it is not on one.

    A DETACHED HEAD is not `main` even when it points at `main`'s commit: a
    write there lands on no branch, so it is not the thing this gate exists to
    stop, and it is let through.
    """
    try:
        head = (Path(gitdir) / "HEAD").read_text(
            encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return None
    ref = head.split(":", 1)[1].strip()
    prefix = "refs/heads/"
    return ref[len(prefix):] if ref.startswith(prefix) else None


def _has_commit(gitdir, branch):
    """Does `branch` name a commit yet?

    A repository freshly `git init`-ed is ON `main` with nothing on it, and
    installing a viewer into one is how a store is set up in the first place.
    Refusing there would break the ordinary case to protect a branch that does
    not exist, so an unborn branch is not protected.
    """
    common = _common_dir(gitdir)
    loose = common.joinpath("refs", "heads", *branch.split("/"))
    try:
        if loose.is_file() and loose.read_text(
                encoding="utf-8", errors="replace").strip():
            return True
    except OSError:
        pass
    ref = "refs/heads/%s" % branch
    try:
        for line in (common / "packed-refs").read_text(
                encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return True
    except OSError:
        pass
    return False


def protected_branch(path):
    """(repo, branch) when a write to `path` would land on a protected branch.

    `branch` is None whenever the write may proceed — not a product, no
    repository, no git directory, a detached HEAD, a branch nobody protects,
    or a branch with nothing on it yet.

    IT IS A CONJUNCTION, AND THE FIRST TERM IS THE ONE THAT IS EASY TO FORGET:
    the target must be a PRODUCT repository. A container is itself a git
    repository, it sits on `main`, and it is maintained that way on purpose —
    `memory_views.py install --store memory` against the container's own store
    is the ordinary, correct call. Keyed on the branch name alone this gate
    would refuse it, which is a worse defect than the one it fixes. Whether a
    repository is a product is `product_boundary.describe`'s question and it
    is asked here rather than re-answered: one boundary, one implementation.
    """
    facts = boundary.describe(path)
    if not facts["product"]:
        return facts["repo"], None
    repo = facts["repo"]
    if repo is None:
        return None, None
    gitdir = _git_dir(repo)
    if gitdir is None:
        return repo, None
    branch = _current_branch(gitdir)
    if branch is None or branch not in PROTECTED_BRANCHES:
        return repo, None
    if not _has_commit(gitdir, branch):
        return repo, None
    return repo, branch


def refuse_protected_branch(verb, path):
    """The named exit for a write aimed at a protected branch, or None.

    Printed in `product_boundary.refusal`'s shape — same keys, same
    `exit_code`, the same "here is the ONE command that IS legitimate" ending
    — but NOT by calling it: that function's `error` sentence states a
    different finding ("would write into a PRODUCT repository"), and a gate
    that reports the wrong reason sends its reader to fix the wrong thing.
    `branch` stands where `container` does, being the evidence here.
    """
    repo, branch = protected_branch(path)
    if branch is None:
        return None
    print(json.dumps({
        "status": "REFUSED",
        "verb": verb,
        "target": str(Path(path).resolve()),
        "repository": str(repo),
        "branch": branch,
        "error": "%s writes TRACKED files, and %s is on `%s` — its protected "
                 "branch. Committing them there puts them in the repository "
                 "without a pull request, which is the review this branch "
                 "exists to require."
                 % (verb, repo, branch),
        "legitimate": "container_repo.py start-branch %s --name fix-<slug>, "
                      "then run this verb against that worktree" % repo,
        "exit_code": boundary.EXIT_REFUSED,
    }, ensure_ascii=False))
    return boundary.EXIT_REFUSED


# --------------------------------------------------------------------------
# the store
# --------------------------------------------------------------------------

def is_store(path):
    """A memory store is a directory with a graph log under it."""
    path = Path(path)
    return path.is_dir() and (path / "graph").is_dir()


def store_identity(store):
    """The value two processes compare to agree they mean the same store."""
    return serving.identity_of(store)


def fingerprint(store):
    """A cheap, content-derived answer to "has anything moved?".

    Size and mtime of each log, the repository's HEAD, and the card count.
    All properties of files and of a commit — never the wall clock — so two
    reads with nothing between them agree, and the page does not reload on a
    timer pretending to be a change.
    """
    store = Path(store)
    parts = []
    for rel in ("graph/nodes.jsonl", "graph/edges.jsonl",
                "insight/nodes.jsonl", "insight/edges.jsonl"):
        path = store / rel
        try:
            stat = path.stat()
            parts.append("%s:%d:%d" % (rel, stat.st_size, int(stat.st_mtime)))
        except OSError:
            parts.append("%s:-" % rel)
    repo = memory_viz.discover_repo(store if store.is_dir() else store.parent)
    if repo is not None:
        rc, out, _err = memory_viz._git(["rev-parse", "HEAD"], repo)
        parts.append("head:%s" % (out.strip() if rc == 0 else "?"))
    try:
        parts.append("cards:%d" % len(list((store / "cards").glob("*.md"))))
    except OSError:
        pass
    return "|".join(parts)


# --------------------------------------------------------------------------
# the payload, built by the renderer and never here
# --------------------------------------------------------------------------

# The frozen template carries the graph as one inlined JSON blob. That is all
# a SNAPSHOT can do — a file:// page may not fetch — but for a SERVED page it
# would mean rebuilding and shipping the entire graph inside the document on
# every reload, megabytes of it, for a shell that is a few kilobytes.
#
# So a served page is the template with an EMPTY payload plus a loader that
# fetches `data.json` and fills `#graph-data` before the viewer script runs.
# `graph-view.js` reads that element the moment it executes, so filling it
# first is indistinguishable from having had it inlined — and neither the
# template nor the script is touched, both being copy-fidelity subjects.
#
# `render` refuses a template that does not carry the placeholder exactly
# once, so a "template" that is ONLY the placeholder returns ONLY the blob:
# the very bytes it would have inlined. The projection, the sort order and the
# `<` escaping therefore stay the frozen module's, with nothing reimplemented
# here and no private name reached into.
BLOB_TEMPLATE = memory_viz.DATA_PLACEHOLDER.encode("utf-8")


def build_payload(store, commits, disk_root=None):
    """(nodes, edges, meta, git, disk) for `store`, via the renderer."""
    store = Path(store)
    nodes, edges, info = memory_viz.load_logs(store)
    nodes, edges, hidden_nodes, hidden_edges = memory_viz.split_invalidated(
        nodes, edges, False)
    total_nodes, total_edges = len(nodes), len(edges)
    cards = memory_viz.inline_card_bodies(nodes, store)
    git = memory_viz.collect_git(store, None, max(0, commits))
    root = disk_root or memory_viz.discover_repo(store) or store.parent
    disk = memory_viz.collect_disk(root)
    graph_dir = store / "graph"
    meta = {
        "generated_at": info["newest"] or "unknown",
        "source": memory_viz.portable_source(graph_dir, None),
        "malformed": info["malformed"],
        "invalidated_nodes_hidden": hidden_nodes,
        "invalidated_edges_hidden": hidden_edges,
        "include_invalidated": False,
        "limited": False, "limit": 0, "rank": "",
        "total_nodes": total_nodes, "total_edges": total_edges,
        "cards_inlined": cards["cards_inlined"],
        "git_state": git["state"], "commits_inlined": git["included"],
        "disk_state": disk["state"], "disk_files": len(disk["files"]),
        "served": True,
    }
    return nodes, edges, meta, git, disk


def graph_blob(store, commits, disk_root=None):
    """The graph as the JSON bytes the template would have inlined."""
    nodes, edges, meta, git, disk = build_payload(store, commits, disk_root)
    return memory_viz.render(nodes, edges, meta, BLOB_TEMPLATE, git, disk)


LOADER = """
<script>
(function () {
  /* Fetch first, THEN run the viewer: graph-view.js parses #graph-data the
     moment it executes, so it must not execute before the data is there. */
  var el = document.getElementById("graph-data");
  fetch("data.json", {cache: "no-store"})
    .then(function (r) {
      if (!r.ok) { throw new Error("data.json: HTTP " + r.status); }
      return r.text();
    })
    .then(function (text) {
      el.textContent = text;
      var s = document.createElement("script");
      /* Served from this server's own root: the server hands out the frozen
         assets itself, so a served page never depends on where they sit in
         the store. */
      s.src = "./graph-view.js";
      document.body.appendChild(s);
    })
    .catch(function (err) {
      /* Say what went wrong. This page is a BOOTSTRAP: opened straight off
         disk it is a file:// page, browsers forbid those from reading local
         files, and it holds no records of its own. A blank page that never
         explains itself is the failure this viewer exists to avoid. */
      var p = document.createElement("pre");
      p.style.cssText = "padding:1.5rem;white-space:pre-wrap;font:13px " +
        "ui-monospace,Consolas,monospace";
      p.textContent =
        "This page could not load its data: " + ((err && err.message) || err) +
        "\\n\\nIt is a bootstrap, not a snapshot \\u2014 it holds no records " +
        "and fills itself from a running viewer.\\n" +
        "Start one by double-clicking memory-view.cmd (Windows) or running " +
        "./memory-view.sh beside this file.\\n" +
        "For an offline copy that needs no server, run:\\n" +
        "    python memory_views.py render --store .";
      document.body.appendChild(p);
    });
}());
</script>
"""

# Injected per REQUEST, never written into the tracked bootstrap: it carries a
# service id and a poll interval that belong to one running server, and the
# tracked file has to stay stable bytes or every launch is a diff.
LIVE_SCRIPT = """
<script>
(function () {
  var SERVICE = %(service)s;
  var POLL = %(poll)d * 1000;
  var mark = %(fingerprint)s;
  var alive = true;

  /* THE TAB NAMES ITSELF. It cannot be identified by its connection: every
     request opens a new one, so `hello` and `goodbye` would arrive from two
     different ephemeral ports and read as two different tabs — the count
     would never fall and the server would never notice the last tab close,
     which is the only lifecycle promise this viewer makes. */
  var TAB = "t" + Math.random().toString(36).slice(2) +
            Date.now().toString(36);

  function ping(event) {
    var body = JSON.stringify({service: SERVICE, tab: TAB, event: event});
    /* sendBeacon survives the page going away; fetch does not. */
    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon("presence", body);
        return;
      }
    } catch (e) { /* fall through */ }
    try {
      fetch("presence", {method: "POST", keepalive: true, body: body});
    } catch (e) { /* nothing else to try */ }
  }

  ping("hello");
  window.addEventListener("pagehide", function () {
    alive = false;
    ping("goodbye");
  });

  if (POLL > 0) {
    setInterval(function () {
      if (!alive) { return; }
      /* The heartbeat IS the poll: a page asking for state is a page somebody
         has open, so no second timer has to prove it. The tab travels in the
         query string because this one is a GET. */
      fetch("state.json?tab=" + encodeURIComponent(TAB), {cache: "no-store"})
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          if (!j) { return; }
          if (j.service !== SERVICE) { return; }
          if (j.fingerprint !== mark) { location.reload(); }
        })
        .catch(function () { /* the server went away; the tab stays put */ });
    }, POLL);
  }
}());
</script>
"""


_inject = serving.inject


ASSET_DIR = memory_viz.ASSET_DIR_NAME

# The rewrite itself belongs to the module that owns the asset names and
# writes the other page in the same two layouts. Kept as a name here
# because that is what this file's callers and its tests reach for.
point_at_vendored_assets = memory_viz.point_at_vendored_assets


def bootstrap_html(assets):
    """The tracked page: the frozen shell, an EMPTY payload, and the loader.

    Stable bytes. It carries no records, so committing it costs one diff ever
    rather than one per render — which is what makes tracking the viewer trio
    in every store affordable at all.
    """
    empty = memory_viz.render({}, {}, {"served": False},
                              assets[memory_viz.ASSET_TEMPLATE],
                              {"state": "off", "commits": []},
                              {"state": "off", "files": [],
                               "truncated": False})
    # THE LOADER IS THE ONLY THING THAT RUNS THE VIEWER. The frozen template
    # carries its own `<script src>` — correct for the SNAPSHOT, where the
    # payload really is inlined — and `inject` only appends, so this page
    # shipped two tags and ran `graph-view.js` twice: two closures over one
    # DOM, duplicated controls, and two `state` objects writing one
    # transform. The template's tag comes out FIRST, while the src is still
    # the flat name the template wrote (`serving.detach_script` raises if it
    # is not there exactly once).
    #
    # The rewrite runs over the FINISHED page, loader included. Running it
    # first left the loader's `s.src` flat while the stylesheet link was
    # vendored, so neither layout got both files: opened off disk the page
    # was styled with no viewer, and served it had a viewer with no
    # styling. The handler answers both spellings, so these bytes work in
    # both places.
    shell = serving.detach_script(empty, "./%s" % memory_viz.ASSET_JS)
    return point_at_vendored_assets(_inject(shell, LOADER))


# --------------------------------------------------------------------------
# who is watching
# --------------------------------------------------------------------------

# One implementation, on the shared floor: the coverage viewer needs exactly
# this, and two copies of a lifecycle whose first version was WRONG (a tab
# identified by its connection) is two places to re-learn it.
Presence = serving.Presence


# --------------------------------------------------------------------------
# the server
# --------------------------------------------------------------------------

def make_handler(store, assets, state):
    store = Path(store)
    identity = store_identity(store)

    class MemoryViewHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html", "/" + BOOTSTRAP_NAME):
                self._bytes(self._page(), "text/html; charset=utf-8")
            elif path in ("/graph-view.css",
                          "/%s/%s" % (ASSET_DIR, memory_viz.ASSET_CSS)):
                # BOTH spellings. The page the server hands out is the
                # vendored bootstrap, which links `./memory-viewer/…`;
                # the flat path is what a page rendered standalone asks
                # for, and what every earlier version of this page asked
                # for. One file, two names, no 404 either way.
                self._bytes(assets[memory_viz.ASSET_CSS],
                            "text/css; charset=utf-8")
            elif path in ("/graph-view.js",
                          "/%s/%s" % (ASSET_DIR, memory_viz.ASSET_JS)):
                self._bytes(assets[memory_viz.ASSET_JS],
                            "text/javascript; charset=utf-8")
            elif path in ("/%s" % memory_viz.ASSET_PACKING,
                          "/%s/%s" % (memory_viz.ASSET_SHARED_DIR,
                                      memory_viz.ASSET_PACKING)):
                # BOTH spellings, for the same reason as the two above.
                self._bytes(assets[memory_viz.ASSET_PACKING],
                            "text/javascript; charset=utf-8")
            elif path == "/data.json":
                self._bytes(graph_blob(store, state["commits"],
                                       state["disk_root"]),
                            "application/json; charset=utf-8")
            elif path == "/state.json":
                state["presence"].beat(self._tab_from_query())
                self._json({"service": state["service"],
                            "store": identity,
                            "fingerprint": fingerprint(store),
                            "watchers": state["presence"].watchers()})
            elif path == "/ping":
                # THE identity route. A port says nothing about who holds it,
                # so a launcher asks the server which STORE it serves and
                # compares that — never the port, and never a guess.
                self._json({"service": state["service"],
                            "viewer": "memory",
                            "store": identity})
            else:
                self.send_error(404, "This viewer serves /, /graph-view.css, "
                                     "/graph-view.js (also under "
                                     "/memory-viewer/), /data.json, "
                                     "/state.json and /ping")

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/presence":
                self.send_error(404, "This viewer accepts POST at /presence")
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(max(0, min(length, 4096)))
                payload = json.loads(raw.decode("utf-8"))
            except (OSError, ValueError, UnicodeDecodeError):
                payload = {}
            if payload.get("service") != state["service"]:
                # Another local server's page, or a stray probe. Never let it
                # move THIS server's lifecycle.
                self._json({"ok": False, "error": "not this service"},
                           status=409)
                return
            tab = str(payload.get("tab") or "")
            if not tab:
                self._json({"ok": False, "error": "no tab id"}, status=400)
                return
            if payload.get("event") == "goodbye":
                state["presence"].goodbye(tab)
            else:
                state["presence"].hello(tab)
            self._json({"ok": True,
                        "watchers": state["presence"].watchers()})

        def _tab_from_query(self):
            """The tab id the page put in its own query string (never the
            connection — see `viewer_serving.Presence`)."""
            return serving.tab_from_query(self.path, self.client_address[1])

        def _page(self):
            live = LIVE_SCRIPT % {
                "service": json.dumps(state["service"]),
                "poll": state["poll"],
                "fingerprint": json.dumps(fingerprint(store)),
            }
            return _inject(bootstrap_html(assets), live)

        def _bytes(self, body, content_type, status=200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass

        def _json(self, obj, status=200):
            self._bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8", status)

        def log_message(self, *args):
            pass

    return MemoryViewHandler


# One implementation, on the shared floor — see `viewer_serving.py`'s
# discovery block for what the serial fifty-port HTTP walk that used to live
# here cost on a machine whose firewall drops rather than refuses (75 s per
# launch, which was the whole of "the .cmd takes almost a minute").
ask = serving.ask


def find_own_server(store, host=None):
    """The URL of a server already serving THIS store, or None.

    Asks this store's announcement first and its own candidate ports second.
    It cannot find, disturb, or be confused by another store's viewer: the
    `/ping` identity decides, so a port answering with a different store is
    passed over and one answering nothing at all is passed over too.
    """
    return serving.find_server(
        VIEWER_KIND, store, store_identity(store), "store",
        ports.candidate_ports(VIEWER_KIND, store), host or ports.HOST)


# --------------------------------------------------------------------------
# the launchers
# --------------------------------------------------------------------------

# What the two launchers say, filled into the shared templates
# (`viewer_serving.py`). Everything they encode about interpreters, about a
# .cmd window that closes before its error can be read, and about the line
# endings each interpreter needs, lives THERE — once, for both viewers.
#
# The prelude is this viewer's own: refresh the store first WHEN THE ENGINE IS
# HERE. It is not part of this package — this is the VIEWER, and the engine
# that WRITES the store is a different role (P9) — so calling it
# unconditionally would name a file a bare clone does not have. Where it is
# absent the viewer still serves what the logs hold, which is true, and is all
# a viewer ever claimed.
#
# WHERE IT LOOKS, AND WHY IT IS A WALK. The two fixed candidates this replaced
# — `$HERE/memory_graph.py` and `$HERE/../scripts/memory_graph.py` — resolve
# inside a PRODUCT to `<product>/memory/memory_graph.py` and
# `<product>/scripts/memory_graph.py`. Neither exists there and neither ever
# will, because the engine is not vendored: so in every product the refresh
# was skipped, always, and the viewer served an unrefreshed map. The engine
# lives in the orchestration container ABOVE the product, which is a variable
# number of levels up — `<container>/main/memory` in a single-product
# container, one level deeper where products are grouped — so the search is a
# BOUNDED upward walk and not a fixed `../../`. Five levels: the launcher this
# replaced walked four above the repository root and resolved here, and the
# fifth is the repository root itself, which is where the CONTAINER's own
# store (`<container>/memory`) finds `<container>/scripts`.
#
# AND WHEN IT FINDS NOTHING IT SAYS SO. The old `for` loop fell through in
# silence and the viewer served a map nobody had refreshed, with nothing on
# screen or on stderr to say which of the two it was. The `else` branch calls
# this script's own `engine-missing` verb, so the message is written once, in
# Python, where the store's timestamps can actually be read — and both
# launchers say the same thing.
LAUNCHER_SPEC = {
    "launcher": "memory-view",
    "subject": "store",
    "title": "memory viewer",
    "page": BOOTSTRAP_NAME,
    "reads": "the JSONL logs or run `git log`",
    "server": "memory_views.py",
    "flag": "store",
    "prelude_cmd": (
        'REM Refresh this store before serving it, WHEN AN ENGINE IS\n'
        'REM REACHABLE: the store itself first, so a genuinely\n'
        'REM self-contained store wins, then a BOUNDED five-level walk UP\n'
        'REM for an orchestration scripts\\ folder. A fixed ..\\.. would be\n'
        'REM right only where the product sits directly at\n'
        'REM <container>\\main; one level deeper it misses in silence.\n'
        'set "ENGINE="\n'
        'if exist "%HERE%\\memory_graph.py" '
        'set "ENGINE=%HERE%\\memory_graph.py"\n'
        'if not defined ENGINE (\n'
        '  set "C=%HERE%"\n'
        '  for %%L in (1 2 3 4 5) do (\n'
        '    for %%D in ("!C!\\..") do set "C=%%~fD"\n'
        '    if not defined ENGINE if exist "!C!\\scripts\\memory_graph.py" '
        'set "ENGINE=!C!\\scripts\\memory_graph.py"\n'
        '  )\n'
        ')\n'
        'if defined ENGINE (\n'
        '  %PY% "!ENGINE!" refresh --store "%HERE%" '
        '--root "%HERE%\\.." >nul 2>&1\n'
        ') else (\n'
        '  REM An unrefreshed map served in silence is believed. Say so.\n'
        '  %PY% "%HERE%\\memory_views.py" engine-missing '
        '--store "%HERE%" 1>&2\n'
        ')'),
    "prelude_sh": (
        '# Refresh this store before serving it, WHEN AN ENGINE IS\n'
        '# REACHABLE: the store itself first, so a genuinely self-contained\n'
        '# store wins, then a BOUNDED five-level walk UP for an\n'
        '# orchestration `scripts/` folder. A fixed `../../` would be right\n'
        '# only where the product sits directly at <container>/main; one\n'
        '# level deeper it misses, and misses in silence.\n'
        'ENGINE=""\n'
        'if [ -f "$HERE/memory_graph.py" ]; then\n'
        '  ENGINE="$HERE/memory_graph.py"\n'
        'else\n'
        '  C="$HERE"\n'
        '  for _ in 1 2 3 4 5; do\n'
        '    C=$(dirname "$C")\n'
        '    if [ -f "$C/scripts/memory_graph.py" ]; then\n'
        '      ENGINE="$C/scripts/memory_graph.py"\n'
        '      break\n'
        '    fi\n'
        '  done\n'
        'fi\n'
        'if [ -n "$ENGINE" ]; then\n'
        '  "$PY" "$ENGINE" refresh --store "$HERE" --root "$HERE/.." \\\n'
        '      >/dev/null 2>&1 || true\n'
        'else\n'
        '  # An unrefreshed map served in silence is believed. Say so.\n'
        '  "$PY" "$HERE/memory_views.py" engine-missing '
        '--store "$HERE" >&2 || true\n'
        'fi'),
}

# What `install` places in the store, and where each comes from. The whole
# package travels, because the user's requirement is that a repository cloned
# ALONE still opens its own viewer: the server cannot render anything by
# itself — it imports the renderer and reads the frozen assets — so shipping
# it without them would be shipping a launcher for a program that is not there.
VENDORED = (
    ("memory_views.py", ("memory_views.py",)),
    ("memory_viz.py", ("memory_viz.py",)),
    ("viewer_ports.py", ("viewer_ports.py",)),
    ("viewer_serving.py", ("viewer_serving.py",)),
    ("product_boundary.py", ("product_boundary.py",)),
    ("viewer-shared/packing.js", ("viewer-shared", "packing.js")),
    ("memory-viewer/template.html", ("memory-viewer", "template.html")),
    ("memory-viewer/graph-view.css", ("memory-viewer", "graph-view.css")),
    ("memory-viewer/graph-view.js", ("memory-viewer", "graph-view.js")),
)
# Written into the store's own .gitignore by `install`: the derived outputs,
# never the vendored tooling and never the bootstrap.
IGNORED = ("graph-view-snapshot.html", "__pycache__/")


def source_root():
    """Where the files `install` copies come from.

    Either the skill's `scripts/` (installing from the skill) or a store that
    was itself installed (installing a sibling store from a working one).
    """
    for folder in (BASE, BASE.parent):
        if (folder / "memory_viz.py").is_file():
            return folder
    return BASE


# --------------------------------------------------------------------------
# verbs
# --------------------------------------------------------------------------

def cmd_install(args):
    store = Path(args.store).resolve()
    if not store.is_dir():
        return serving.blocked("no directory at %s" % store,
                               "create the store first: memory_graph.py init")
    # The same precondition `render` and `serve` state. `install` used to
    # accept ANY directory and report COMPLETED, which leaves a launcher,
    # a page and four scripts in a folder that has no records to show —
    # discovered only when somebody double-clicks it.
    if not is_store(store):
        return serving.blocked(
            "no memory store at %s" % store,
            "a store is a directory with graph/ under it — run "
            "`memory_graph.py init --store %s` first" % store)
    # THE BOUNDARY, BEFORE THE FIRST BYTE. This verb vendors eight files and
    # rewrites a `.gitignore`; inside a PRODUCT repository that is the
    # container reaching into a tree it does not own, and it is how a store
    # in `PixelArt-Creator/main` came to be installed by the container's
    # session. The product's own system does this for itself and says so.
    _facts, refused = boundary.enforce(
        "memory_views.py install", store,
        legitimate="run `memory_views.py install --store %s --product-self` "
                   "from the PRODUCT's own orchestration system" % store,
        product_self=getattr(args, "product_self", False))
    if refused is not None:
        return refused
    # AND THE BRANCH, WHICH IS A SECOND QUESTION. The boundary above asks
    # whose repository this is; this asks where the tracked files it writes
    # would be committed. `--product-self` answers the first and is NOT
    # consulted here: the product's own system installing its own furniture is
    # legitimate AND still owes that repository a pull request.
    refused = refuse_protected_branch("memory_views.py install", store)
    if refused is not None:
        return refused
    # RECONCILE THE FILE THIS VERB WRITES INTO, BEFORE writing into it.
    # `install` appends to the store's `.gitignore` but never pruned it,
    # and the retired patterns are UNANCHORED: a store still carrying
    # `graph-view.css` hides `memory-viewer/graph-view.css` at any depth,
    # so the install below would vendor a package git refuses to commit
    # and every clone would open a viewer with no stylesheet. The prune is
    # the engine's `Store.ensure()` — one implementation, one owner — and
    # what it removed is reported, because a silent repair of somebody
    # else's file is indistinguishable from no repair at all.
    engine = _engine()
    try:
        had = {line.strip() for line in (store / ".gitignore").read_bytes()
               .decode("utf-8", "replace").splitlines()}
    except OSError:
        had = set()
    pruned = [line for line in engine.RETIRED_GITIGNORE_LINES
              if line in had]
    engine.Store(store).ensure()
    written, missing = serving.vendor(source_root(), store, VENDORED,
                                      memory_viz.write_if_changed)
    if missing:
        return serving.blocked(
            "cannot install: %s" % ", ".join(missing),
            "run install from a tree that carries the whole viewer package")

    assets, error = memory_viz.load_assets()
    if error is not None:
        # The renderer's own refusal, verbatim: it names the exact path, and
        # restating it here in different words would give the same problem two
        # descriptions to be searched for.
        print(json.dumps(error))
        return 2
    if memory_viz.write_if_changed(store / BOOTSTRAP_NAME,
                                   bootstrap_html(assets)):
        written.append(BOOTSTRAP_NAME)

    written += serving.write_launchers(store, LAUNCHER_SPEC,
                                       memory_viz.write_if_changed)
    if serving.ensure_ignored(store / ".gitignore", IGNORED) or pruned:
        written.append(".gitignore")

    print(json.dumps({"status": "COMPLETED", "store": str(store),
                      "written": written,
                      "gitignore_pruned": pruned,
                      "url_when_served": "http://%s:%d/"
                                         % (ports.HOST,
                                            ports.preferred_port(VIEWER_KIND,
                                                                 store))}))
    return 0


def last_scan(store):
    """When this store was last written, as the store itself records it.

    Two REAL values, in the order of how directly they answer the question,
    and never an invented field:

      * `graph/scan-state.json`'s `scanned_at` — the engine's own record of
        its last structural scan. It is derived and gitignored, so a bare
        clone does not carry it, which is why there is a second answer;
      * otherwise the newest record timestamp in the logs, read by the
        renderer's own `load_logs` — the same value it prints as
        `generated_at` — which is present wherever `graph/nodes.jsonl` is.

    Returns (value, where it came from). The field is read directly rather
    than through the engine's `load_scan_state` for the obvious reason: this
    runs precisely when the engine could not be found.
    """
    state = Path(store) / "graph" / "scan-state.json"
    try:
        raw = json.loads(state.read_text(encoding="utf-8", errors="replace"))
        stamp = raw.get("scanned_at") if isinstance(raw, dict) else None
        if isinstance(stamp, str) and stamp:
            return stamp, "graph/scan-state.json: scanned_at"
    except (OSError, ValueError):
        pass
    try:
        _nodes, _edges, info = memory_viz.load_logs(Path(store))
        if info.get("newest"):
            return info["newest"], "graph/nodes.jsonl: newest record"
    except (OSError, ValueError):
        pass
    return "unknown", "this store records no timestamp yet"


def cmd_engine_missing(args):
    """Say, on stderr, that the store was NOT refreshed — then let it serve.

    A launcher calls this when no `memory_graph.py` resolved: in the store,
    or in any `scripts/` folder on the bounded walk above it. What followed
    before was silence and a served page, and a viewer that quietly answers
    with a map nobody refreshed is worse than no viewer, because it is
    believed.

    It prints and returns 0 on purpose. A bare clone opening its viewer
    read-only is the DESIGNED case — the engine writes stores and is a
    different role from this viewer — so the message is a warning the reader
    acts on, never a refusal that stops the page from opening.
    """
    store = Path(args.store).resolve()
    stamp, where = last_scan(store)
    lines = [
        "memory-view: NOT REFRESHED. No memory_graph.py engine is reachable",
        "memory-view: from this store, so nothing re-read the repository",
        "memory-view: before serving. The map you are about to see is this",
        "memory-view: store exactly as it was last written:",
        "memory-view:   last scan: %s" % stamp,
        "memory-view:   recorded in: %s" % where,
        "memory-view:   store: %s" % store,
        "memory-view: The engine WRITES stores and does not ship with the",
        "memory-view: viewer — a clone opens its map, it does not need the",
        "memory-view: writer — so the viewer starts anyway. To refresh it,",
        "memory-view: run this from a tree that carries the engine (the",
        "memory-view: orchestration container above this repository):",
        'memory-view:   python scripts/memory_graph.py refresh --store "%s" '
        '--root "%s"' % (store, store.parent),
    ]
    print("\n".join(lines), file=sys.stderr, flush=True)
    return 0


def cmd_render(args):
    """The offline page, for a machine where running a server is not wanted.

    It writes the SNAPSHOT name, never the tracked bootstrap: the bootstrap is
    committed, and putting the whole graph into it would add the entire store
    to the repository's history on every render.
    """
    store = Path(args.store).resolve()
    if not is_store(store):
        return serving.blocked("no memory store at %s" % store,
                               "a store is a directory with graph/ under it")
    assets, error = memory_viz.load_assets()
    if error is not None:
        print(json.dumps(error))
        return 2
    nodes, edges, meta, git, disk = build_payload(store, args.commits,
                                                  args.disk_root)
    meta["served"] = False
    out = Path(args.out) if args.out else store / SNAPSHOT_NAME
    payload = memory_viz.render(nodes, edges, meta,
                               assets[memory_viz.ASSET_TEMPLATE], git, disk)
    payload = point_at_vendored_assets(payload)
    written = memory_viz.write_if_changed(out, payload)
    print(json.dumps({"status": "COMPLETED", "store": str(store),
                      "out": str(out), "written": written,
                      "bytes": len(payload),
                      "nodes": meta["total_nodes"],
                      "git_state": git["state"]}))
    return 0


def cmd_serve(args):
    store = Path(args.store).resolve()
    if not is_store(store):
        return serving.blocked("no memory store at %s" % store,
                               "a store is a directory with graph/ under it")
    assets, error = memory_viz.load_assets()
    if error is not None:
        print(json.dumps(error))
        return 2

    # A second launch of the SAME store opens a tab on its own server rather
    # than raising a duplicate. Identity is the store PATH the server reports,
    # never the port: a port says nothing about who is holding it.
    running = find_own_server(store)
    if running and not args.once:
        print("VIEWER URL: %s" % running, flush=True)
        print("Already serving this store — nothing started.", flush=True)
        if args.open_browser:
            serving.open_browser(running)
        return 0

    state = {
        "service": uuid.uuid4().hex,
        "commits": args.commits,
        "poll": max(0, args.poll_seconds),
        "disk_root": args.disk_root,
        "presence": serving.Presence(grace=args.grace, idle=args.idle),
    }
    handler = make_handler(store, assets, state)
    try:
        server = ports.serve_in_range(VIEWER_KIND, store, handler)
    except ports.RangeExhausted as exhausted:
        # The named exit, printed where the person who double-clicked can read
        # it. The launcher pauses on a non-zero exit so the window stays up.
        print(str(exhausted), file=sys.stderr, flush=True)
        return 2

    url = "http://%s:%d/" % (ports.HOST, server.server_address[1])
    print("VIEWER URL: %s" % url, flush=True)
    print("Store: %s (re-read on every request)" % store, flush=True)
    print("Stops by itself when the last tab closes.", flush=True)

    # Say where we are, so the NEXT launcher reads one line instead of
    # knocking on fifty ports. Written after the bind, because the port here
    # is the one we really got — which is not always the preferred one, and
    # that gap is exactly what a rendezvous file is for.
    rendezvous = serving.announce_path(VIEWER_KIND, store)
    serving.write_announcement(rendezvous, url, store_identity(store))
    try:
        if args.once:
            server.handle_request()
            server.server_close()
            return 0

        serving.serve_until_last_tab(server, state["presence"], url,
                                     args.open_browser)
    finally:
        # A stale announcement is worse than none: it is read and believed.
        serving.clear_announcement(rendezvous)
    print("Viewer stopped: the last tab closed.", flush=True)
    return 0


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

# `port_free` used to live here: a second copy of `viewer_ports.port_is_free`
# without its range check and — the part that mattered — without
# SO_EXCLUSIVEADDRUSE, which on Windows is what stops a second process
# hijacking a running viewer's port. It was also never called. Two copies of
# a lifecycle whose first version was WRONG is exactly what the shared
# serving floor exists to prevent, so it is gone rather than repaired.


def build_parser():
    parser = argparse.ArgumentParser(
        prog="memory_views.py",
        description="Serve one memory store's viewer, live, from the store "
                    "it lives in")
    sub = parser.add_subparsers(dest="verb", required=True)

    def common(target):
        target.add_argument("--store", default="memory",
                            help="the memory store directory (default: "
                                 "memory)")
        target.add_argument("--commits", type=int,
                            default=memory_viz.DEFAULT_COMMIT_LIMIT,
                            help="commits inlined into the History frame "
                                 "(default %d; 0 = all)"
                                 % memory_viz.DEFAULT_COMMIT_LIMIT)
        target.add_argument("--disk-root", default=None,
                            help="directory the Repo frame walks (default: "
                                 "the repository containing the store)")

    install = sub.add_parser(
        "install", help="place the viewer package and its launchers in a store")
    install.add_argument("--store", default="memory",
                         help="the memory store directory (default: memory)")
    boundary.add_product_self_flag(install)

    # NOT A USER-FACING VERB, and not hidden either: a generated launcher
    # calls it when its bounded walk found no engine, and a person reading
    # that launcher must be able to run the same line and see the same
    # message.
    stale = sub.add_parser(
        "engine-missing",
        help="print, on stderr, that this store could not be refreshed "
             "(what a launcher says when it finds no memory_graph.py)")
    stale.add_argument("--store", default="memory",
                       help="the memory store directory (default: memory)")

    serve = sub.add_parser("serve", help="serve this store, live")
    common(serve)
    serve.add_argument("--open-browser", action="store_true",
                       help="open a browser on the URL once it is up")
    # THE LAUNCHER'S OWN `--open-browser` IS NOT THE LAST WORD. Every
    # generated launcher hard-codes it and then forwards its arguments, so
    # this trailing override is the only way to run one HEADLESS — which is
    # what the suite that executes the launchers needs, and what a person
    # driving one from a script wants. Same `dest`, so whichever comes last
    # wins, and the launcher's flag comes first.
    serve.add_argument("--no-open-browser", dest="open_browser",
                       action="store_false",
                       help="do not open a browser (overrides an earlier "
                            "--open-browser, including a launcher's own)")
    serve.add_argument("--poll-seconds", type=int,
                       default=DEFAULT_POLL_SECONDS,
                       help="how often the page re-checks the fingerprint "
                            "(default %d; 0 disables the poller)"
                            % DEFAULT_POLL_SECONDS)
    serve.add_argument("--grace", type=int, default=GRACE_SECONDS,
                       help="seconds a silent tab is still counted as open "
                            "(default %d) — a reload is a tab closing and "
                            "another opening" % GRACE_SECONDS)
    serve.add_argument("--idle", type=int, default=IDLE_SECONDS,
                       help="seconds to wait for a first tab before stopping "
                            "(default %d)" % IDLE_SECONDS)
    serve.add_argument("--once", action="store_true",
                       help="handle exactly one request, then exit (tests)")

    render = sub.add_parser(
        "render", help="write the offline snapshot page (needs no server)")
    common(render)
    render.add_argument("--out", default=None,
                        help="output path (default <store>/%s)"
                             % SNAPSHOT_NAME)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.verb == "install":
        return cmd_install(args)
    if args.verb == "render":
        return cmd_render(args)
    if args.verb == "engine-missing":
        return cmd_engine_missing(args)
    return cmd_serve(args)


if __name__ == "__main__":
    sys.exit(main())
