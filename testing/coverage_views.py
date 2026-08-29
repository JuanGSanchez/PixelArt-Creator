#!/usr/bin/env python3
"""Serve ONE repository's coverage map, live, from the testing/ it lives in.

N-8's serving half. The same shape as `memory_views.py`, standing on the same
floor (`viewer_serving.py`), because they are the same kind of thing: a
look-and-close viewer over one directory, raised by a launcher that lives
beside what it shows.

IT ANALYSES NOTHING ITSELF (P9). Every function name, every classification and
every output claim comes from `coverage_viz.py` reading the repository's own
`testing/` declarations. This file imports that module and calls it; it does
not re-implement, patch, or vendor any part of it.

WHY LIVE. A rendered coverage page is a photograph of a suite that changes
every time somebody writes a test — and it is exactly the reader who is ABOUT
to write one who opens it. `serve` re-runs the analysis on every request for
`data.json`, and an injected poller reloads the page when the fingerprint of
`testing/` and the declared source roots moves.

ONE REPOSITORY, ONE SERVER, NO NEIGHBOURS — the same three rules as the memory
viewer, for the same reasons; its port comes from the COVERAGE block of the one
allocation table (`viewer_ports.py`), derived from the `testing/` directory's
own path.

Usage
    py coverage_views.py serve   --project <dir> [--open-browser] [--once]
    py coverage_views.py install --project <dir>
"""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import sys
import uuid
from http.server import BaseHTTPRequestHandler
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent

VIEWER_KIND = "coverage"
TESTING_DIR = "testing"
LAUNCHER = "coverage-view"


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
    `testing/` into which the whole package has been vendored so the repository
    works when cloned alone.

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
        "error": "%s is missing: %s.py must ship beside this script"
                 % (what, name),
        "hint": "restore it from the orchestrator-design skill, or re-run "
                "`coverage_views.py install --project <dir>` from a tree that "
                "has it",
    }))


coverage_viz = _load_sibling("coverage_viz", "the analyser")
ports = _load_sibling("viewer_ports", "the port allocation table")
serving = _load_sibling("viewer_serving", "the shared serving floor")
# Vendored with the rest of the package deliberately: `install` WRITES, and a
# copy of this script that shipped without the boundary it is gated by would
# be a copy with the gate removed.
boundary = _load_sibling("product_boundary", "the product boundary")

# The tracked BOOTSTRAP this file writes and the DERIVED snapshot the
# analyser writes. Both names come from the analyser: two modules holding
# the same two filenames is how the memory side came to have one.
BOOTSTRAP_NAME = coverage_viz.BOOTSTRAP_NAME
SNAPSHOT_NAME = coverage_viz.SNAPSHOT_NAME

# What `install` places in `testing/`. The whole package travels, because the
# server cannot analyse anything by itself: shipping it without the analyser
# and the frozen assets would be shipping a launcher for a program that is not
# there.
VENDORED = (
    ("coverage_views.py", ("coverage_views.py",)),
    ("coverage_viz.py", ("coverage_viz.py",)),
    ("viewer_ports.py", ("viewer_ports.py",)),
    ("viewer_serving.py", ("viewer_serving.py",)),
    ("product_boundary.py", ("product_boundary.py",)),
    ("viewer-shared/packing.js", ("viewer-shared", "packing.js")),
    ("coverage-viewer/template.html", ("coverage-viewer", "template.html")),
    ("coverage-viewer/coverage-view.css",
     ("coverage-viewer", "coverage-view.css")),
    ("coverage-viewer/coverage-view.js",
     ("coverage-viewer", "coverage-view.js")),
)
# What a RUN produces and no clone should carry: the derived snapshot, the
# bytecode cache, and the measurement itself. `coverage.json` changes on
# every run and is what the Coverage frame reads; `.coverage` and its
# per-process `.coverage.*` fragments are the raw data behind it.
IGNORED = (SNAPSHOT_NAME, "__pycache__/",
           "coverage.json", ".coverage", ".coverage.*")

LAUNCHER_SPEC = {
    "launcher": LAUNCHER,
    "subject": "repository",
    "title": "test-coverage map",
    "page": BOOTSTRAP_NAME,
    "reads": "the test sources or the declarations under testing/",
    "server": "coverage_views.py",
    "flag": "project",
    # `--project` is the REPOSITORY, and this launcher sits in `testing/`
    # beneath it, so the flag it passes has to climb one level. This pair is
    # what implements that sentence; while it was only a sentence, every
    # generated launcher ran `serve --project <repo>/testing` and exited
    # BLOCKED with "no testing/ directory in <repo>/testing".
    "target_cmd": "%HERE%\\..",
    "target_sh": "$HERE/..",
    "prelude_cmd": "",
    "prelude_sh": "",
}


def project_of(testing_dir):
    """The repository a `testing/` directory belongs to."""
    return Path(testing_dir).resolve().parent


def fingerprint(project, profile):
    """Has anything a coverage page depends on moved?

    The declaration file, plus size+mtime of every Python file under
    `testing/` and the declared source roots. Properties of files, never the
    wall clock, so two reads with nothing between them agree and the page does
    not reload on a timer pretending to be a change.

    DIGESTED, NOT `hash()`. This used to fold the parts with the builtin,
    which Python randomizes per process (`PYTHONHASHSEED`): two runs over an
    untouched repository disagreed about whether it had moved, and the
    docstring above claimed the opposite. `sha256` of the same parts is the
    same value in every process, which is what "properties of files" was
    always supposed to mean. The memory viewer's `fingerprint` never had this
    defect, which is why only this one had to change.
    """
    project = Path(project)
    parts = []
    roots = [project / TESTING_DIR]
    roots += [project / root for root in profile.get("source_roots", [])]
    for root in roots:
        files, _truncated = coverage_viz.python_files(root)
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            parts.append("%s:%d:%d" % (coverage_viz.relative(path, project),
                                       stat.st_size, int(stat.st_mtime)))
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]
    return "%s|%d|%s" % (profile.get("declared_in", ""), len(parts), digest)


LOADER = """
<script>
(function () {
  /* Fetch first, THEN run the viewer: coverage-view.js parses
     #coverage-data the moment it executes. */
  var el = document.getElementById("coverage-data");
  fetch("data.json", {cache: "no-store"})
    .then(function (r) {
      if (!r.ok) { throw new Error("data.json: HTTP " + r.status); }
      return r.text();
    })
    .then(function (text) {
      el.textContent = text;
      var s = document.createElement("script");
      s.src = "./coverage-view.js";
      document.body.appendChild(s);
    })
    .catch(function (err) {
      var p = document.createElement("pre");
      p.style.cssText = "padding:1.5rem;white-space:pre-wrap;font:13px " +
        "ui-monospace,Consolas,monospace";
      p.textContent =
        "This page could not load its data: " + ((err && err.message) || err) +
        "\\n\\nIt is a bootstrap, not a snapshot \\u2014 it holds no analysis " +
        "and fills itself from a running viewer.\\n" +
        "Start one by double-clicking coverage-view.cmd (Windows) or running " +
        "./coverage-view.sh beside this file.\\n" +
        "For an offline copy that needs no server, run:\\n" +
        "    python coverage_viz.py --project ..";
      document.body.appendChild(p);
    });
}());
</script>
"""

LIVE_SCRIPT = """
<script>
(function () {
  var SERVICE = %(service)s;
  var POLL = %(poll)d * 1000;
  var mark = %(fingerprint)s;
  var alive = true;
  /* THE TAB NAMES ITSELF: it cannot be identified by its connection, because
     every request opens a new one. */
  var TAB = "t" + Math.random().toString(36).slice(2) +
            Date.now().toString(36);

  function ping(event) {
    var body = JSON.stringify({service: SERVICE, tab: TAB, event: event});
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
      fetch("state.json?tab=" + encodeURIComponent(TAB), {cache: "no-store"})
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) {
          if (!j || j.service !== SERVICE) { return; }
          if (j.fingerprint !== mark) { location.reload(); }
        })
        .catch(function () { /* the server went away; the tab stays put */ });
    }, POLL);
  }
}());
</script>
"""


def bootstrap_html(assets):
    """The tracked page: the frozen shell, an EMPTY payload, and the loader.

    Stable bytes. It carries no analysis, so committing it costs one diff ever
    rather than one per render.
    """
    empty = {
        "state": "ok", "detail": "", "project": "", "kind": "",
        "declared_in": "", "types": {}, "types_declared": False,
        "source_roots": [], "limits": coverage_viz.LIMITS,
        "tests": [], "sources": [], "coverage": [], "uncovered": [],
        "unclassified": [], "missing_roots": [], "truncated": False,
    }
    # The stylesheet link has to resolve for a page opened straight off
    # disk too: that page cannot fetch its data, but it should still be a
    # styled page saying so rather than an unstyled one. `install` puts
    # the assets under `coverage-viewer/` and nothing beside the page, so
    # the frozen template's flat links reached two files that are not
    # there — invisible while served, because the handler routes both.
    # Over the FINISHED page, loader included: the loader appends the
    # viewer script itself, so rewriting before injection left the
    # stylesheet vendored and the script flat, and no layout got both.
    #
    # THE LOADER IS THE ONLY THING THAT RUNS THE VIEWER. The frozen template
    # carries its own `<script src>` — correct for the SNAPSHOT, where the
    # payload really is inlined — and `inject` only appends, so this page
    # shipped two tags and ran `coverage-view.js` twice. The template's tag
    # comes out FIRST, while the src is still the flat name the template
    # wrote; `detach_script` raises if it is not there exactly once.
    shell = serving.detach_script(
        coverage_viz.render(empty, assets[coverage_viz.ASSET_TEMPLATE]),
        "./%s" % coverage_viz.ASSET_JS)
    return coverage_viz.point_at_vendored_assets(
        serving.inject(shell, LOADER))


def payload_for(project, profile):
    data = coverage_viz.collect(project, profile)
    data["uncovered"] = coverage_viz.uncovered(data)
    return data


def make_handler(project, assets, state):
    project = Path(project)
    identity = serving.identity_of(project / TESTING_DIR)

    class CoverageViewHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html", "/" + BOOTSTRAP_NAME):
                self._bytes(self._page(), "text/html; charset=utf-8")
            elif path in ("/coverage-view.css",
                          "/%s/%s" % (coverage_viz.ASSET_DIR_NAME,
                                      coverage_viz.ASSET_CSS)):
                # Both spellings: the served page is the vendored
                # bootstrap, a standalone render asks flat.
                self._bytes(assets[coverage_viz.ASSET_CSS],
                            "text/css; charset=utf-8")
            elif path in ("/coverage-view.js",
                          "/%s/%s" % (coverage_viz.ASSET_DIR_NAME,
                                      coverage_viz.ASSET_JS)):
                self._bytes(assets[coverage_viz.ASSET_JS],
                            "text/javascript; charset=utf-8")
            elif path in ("/%s" % coverage_viz.ASSET_PACKING,
                          "/%s/%s" % (coverage_viz.ASSET_SHARED_DIR,
                                      coverage_viz.ASSET_PACKING)):
                # The shared packing floor, at BOTH spellings for the same
                # reason the two above are: the served page is the vendored
                # bootstrap and asks for the nested one, a standalone render
                # asks flat. It is served from `assets`, never read from
                # disk per request — the copy the page gets is the copy the
                # server loaded and verified at startup.
                self._bytes(assets[coverage_viz.ASSET_PACKING],
                            "text/javascript; charset=utf-8")
            elif path == "/data.json":
                data = payload_for(project, state["profile"])
                self._bytes(json.dumps(data, ensure_ascii=False,
                                       sort_keys=True).encode("utf-8"),
                            "application/json; charset=utf-8")
            elif path == "/state.json":
                state["presence"].beat(
                    serving.tab_from_query(self.path,
                                           self.client_address[1]))
                self._json({"service": state["service"],
                            "project": identity,
                            "fingerprint": fingerprint(project,
                                                       state["profile"]),
                            "watchers": state["presence"].watchers()})
            elif path == "/ping":
                # THE identity route. A port says nothing about who holds it.
                self._json({"service": state["service"],
                            "viewer": "coverage",
                            "project": identity})
            else:
                self.send_error(404, "This viewer serves /, "
                                     "/coverage-view.css, /coverage-view.js "
                                     "(also under /coverage-viewer/), "
                                     "/data.json, /state.json and /ping")

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/presence":
                self.send_error(404, "This viewer accepts POST at /presence")
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(max(0, min(length, 4096)))
                body = json.loads(raw.decode("utf-8"))
            except (OSError, ValueError, UnicodeDecodeError):
                body = {}
            if body.get("service") != state["service"]:
                self._json({"ok": False, "error": "not this service"},
                           status=409)
                return
            tab = str(body.get("tab") or "")
            if not tab:
                self._json({"ok": False, "error": "no tab id"}, status=400)
                return
            if body.get("event") == "goodbye":
                state["presence"].goodbye(tab)
            else:
                state["presence"].hello(tab)
            self._json({"ok": True,
                        "watchers": state["presence"].watchers()})

        def _page(self):
            live = LIVE_SCRIPT % {
                "service": json.dumps(state["service"]),
                "poll": state["poll"],
                "fingerprint": json.dumps(fingerprint(project,
                                                      state["profile"])),
            }
            return serving.inject(bootstrap_html(assets), live)

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

    return CoverageViewHandler


# One implementation, on the shared floor — see `viewer_serving.py`'s
# discovery block for what the serial fifty-port HTTP walk that used to live
# here cost on a machine whose firewall drops rather than refuses.
ask = serving.ask


def find_own_server(project, host=None):
    """The URL of a server already serving THIS repository, or None.

    Asks this repository's announcement first and its own candidate ports
    second. The `/ping` identity decides, so it cannot find, disturb, or be
    confused by another repository's viewer.
    """
    testing = Path(project) / TESTING_DIR
    return serving.find_server(
        VIEWER_KIND, testing, serving.identity_of(testing), "project",
        ports.candidate_ports(VIEWER_KIND, testing), host or ports.HOST)


# --------------------------------------------------------------------------
# the branch a write would land on
# --------------------------------------------------------------------------
#
# `install` writes TRACKED files — the vendored package, the bootstrap page,
# two launchers, a `.gitignore` line — into a repository's `testing/`. Run
# against that repository's `main` it puts them straight onto the branch a
# pull request is supposed to protect, and nothing here noticed.
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
# and by `container_repo.py`. They are byte-for-byte the same as
# `memory_views.py`'s copy but for the verb names in the refusal, and they are
# duplicated only because this change's declared write targets were the two
# viewer files; porting them upstream is a move, not a rewrite.

PROTECTED_BRANCHES = ("main", "master")


def _git_dir(repo):
    """`repo`'s git directory: a `.git` folder, or the one a worktree names.

    A LINKED WORKTREE — which is exactly how a `fix-…` branch is checked out
    beside `main` — carries a `.git` FILE reading `gitdir: <path>`. Its HEAD
    lives at that path, and HEAD is the whole question, so a reader that
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
    installing a viewer into one is how a repository is set up in the first
    place. Refusing there would break the ordinary case to protect a branch
    that does not exist, so an unborn branch is not protected.
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
    `coverage_views.py install --project .` against the container itself is
    the ordinary, correct call. Keyed on the branch name alone this gate would
    refuse it, which is a worse defect than the one it fixes. Whether a
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
# verbs
# --------------------------------------------------------------------------

def source_root():
    for folder in (BASE, BASE.parent):
        if (folder / "coverage_viz.py").is_file():
            return folder
    return BASE


def cmd_install(args):
    project = Path(args.project).resolve()
    testing = project / TESTING_DIR
    # THE BOUNDARY FIRST, BEFORE EVERY OTHER PRECONDITION. This verb vendors
    # eight files, a bootstrap page, two launchers and a `.gitignore` line;
    # inside a PRODUCT repository that is the container reaching into a tree
    # it does not own. Asked before "is it scaffolded" on purpose: whose
    # repository this is does not depend on what is in it, and a reader told
    # "no testing/ directory" would go and make one.
    _facts, refused = boundary.enforce(
        "coverage_views.py install", project,
        legitimate="run `coverage_views.py install --project %s "
                   "--product-self` from the PRODUCT's own orchestration "
                   "system" % project,
        product_self=getattr(args, "product_self", False))
    if refused is not None:
        return refused
    # AND THE BRANCH, WHICH IS A SECOND QUESTION — asked here, before the
    # scaffolding precondition, for the same reason the boundary is: where
    # these files would be committed does not depend on what is in the tree,
    # and a reader told "no testing/ directory" would go and make one on
    # `main`. `--product-self` answers the boundary's question and is
    # deliberately not consulted here.
    refused = refuse_protected_branch("coverage_views.py install", project)
    if refused is not None:
        return refused
    if not testing.is_dir():
        return serving.blocked(
            "no %s/ directory in %s" % (TESTING_DIR, project),
            "run `check_testing.py scaffold` first — the canonical test "
            "folder (N-4b) is where this viewer lives")

    written, missing = serving.vendor(source_root(), testing, VENDORED,
                                      coverage_viz.write_if_changed)
    if missing:
        return serving.blocked(
            "cannot install: %s" % ", ".join(missing),
            "run install from a tree that carries the whole viewer package")

    assets, error = coverage_viz.load_assets()
    if error is not None:
        print(json.dumps(error))
        return 2
    if coverage_viz.write_if_changed(testing / BOOTSTRAP_NAME,
                                     bootstrap_html(assets)):
        written.append(BOOTSTRAP_NAME)

    written += serving.write_launchers(testing, LAUNCHER_SPEC,
                                       coverage_viz.write_if_changed)
    if serving.ensure_ignored(testing / ".gitignore", IGNORED):
        written.append(".gitignore")

    print(json.dumps({
        "status": "COMPLETED", "project": str(project),
        "testing": str(testing), "written": written,
        "url_when_served": "http://%s:%d/"
                           % (ports.HOST,
                              ports.preferred_port(VIEWER_KIND, testing)),
    }))
    return 0


def cmd_serve(args):
    project = Path(args.project).resolve()
    profile, error = coverage_viz.read_profile(project)
    if error:
        return serving.blocked(error,
                               "run `check_testing.py scaffold` to create the "
                               "declarations this viewer reads")
    assets, asset_error = coverage_viz.load_assets()
    if asset_error is not None:
        print(json.dumps(asset_error))
        return 2

    running = find_own_server(project)
    if running and not args.once:
        print("VIEWER URL: %s" % running, flush=True)
        print("Already serving this repository — nothing started.", flush=True)
        if args.open_browser:
            serving.open_browser(running)
        return 0

    state = {
        "service": uuid.uuid4().hex,
        "poll": max(0, args.poll_seconds),
        "profile": profile,
        "presence": serving.Presence(grace=args.grace, idle=args.idle),
    }
    handler = make_handler(project, assets, state)
    try:
        server = ports.serve_in_range(VIEWER_KIND, project / TESTING_DIR,
                                      handler)
    except ports.RangeExhausted as exhausted:
        print(str(exhausted), file=sys.stderr, flush=True)
        return 2

    url = "http://%s:%d/" % (ports.HOST, server.server_address[1])
    print("VIEWER URL: %s" % url, flush=True)
    print("Repository: %s (re-analysed on every request)" % project,
          flush=True)
    print("Stops by itself when the last tab closes.", flush=True)

    # Say where we are, so the NEXT launcher reads one line instead of
    # knocking on fifty ports. After the bind: the port here is the one we
    # really got, which is not always the preferred one.
    rendezvous = serving.announce_path(VIEWER_KIND, project / TESTING_DIR)
    serving.write_announcement(
        rendezvous, url, serving.identity_of(project / TESTING_DIR))
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


def build_parser():
    parser = argparse.ArgumentParser(
        prog="coverage_views.py",
        description="Serve one repository's test-coverage map, live")
    sub = parser.add_subparsers(dest="verb", required=True)

    install = sub.add_parser(
        "install",
        help="place the viewer package and its launchers in testing/")
    install.add_argument("--project", default=".",
                         help="repository root (default: .)")
    boundary.add_product_self_flag(install)

    serve = sub.add_parser("serve", help="serve this repository, live")
    serve.add_argument("--project", default=".",
                       help="repository root (default: .)")
    serve.add_argument("--open-browser", action="store_true",
                       help="open a browser on the URL once it is up")
    # The trailing override every generated launcher needs to be runnable
    # headless — see `memory_views.py`'s copy for the whole reason.
    serve.add_argument("--no-open-browser", dest="open_browser",
                       action="store_false",
                       help="do not open a browser (overrides an earlier "
                            "--open-browser, including a launcher's own)")
    serve.add_argument("--poll-seconds", type=int,
                       default=serving.DEFAULT_POLL_SECONDS,
                       help="how often the page re-checks the fingerprint "
                            "(default %d; 0 disables the poller)"
                            % serving.DEFAULT_POLL_SECONDS)
    serve.add_argument("--grace", type=int, default=serving.GRACE_SECONDS,
                       help="seconds a silent tab is still counted as open "
                            "(default %d)" % serving.GRACE_SECONDS)
    serve.add_argument("--idle", type=int, default=serving.IDLE_SECONDS,
                       help="seconds to wait for a first tab before stopping "
                            "(default %d)" % serving.IDLE_SECONDS)
    serve.add_argument("--once", action="store_true",
                       help="handle exactly one request, then exit (tests)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.verb == "install":
        return cmd_install(args)
    return cmd_serve(args)


if __name__ == "__main__":
    sys.exit(main())
