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
import hashlib
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


def _load_sibling(name, what):
    """Import a module that ships beside this file.

    Both layouts are supported deliberately: the skill's own `scripts/`, and a
    `testing/` into which the whole package has been vendored so the repository
    works when cloned alone.
    """
    for folder in (BASE, BASE.parent):
        if (folder / (name + ".py")).is_file():
            sys.path.insert(0, str(folder))
            return __import__(name)
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
