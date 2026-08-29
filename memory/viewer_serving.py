#!/usr/bin/env python3
"""The floor every look-and-close viewer stands on — once, not once per viewer.

The memory viewer and the coverage viewer answer different questions from
different data, and they raise a local server the same way. Everything in this
file is that sameness: who is watching, how a package is vendored into the
directory it serves, and what the two launchers must say.

WHY THIS IS SHARED RATHER THAN COPIED. The launcher text is not boilerplate.
Every line of it was paid for by a failure — `python` on Windows resolving to
the Microsoft Store alias stub, a .cmd window closing before its error could be
read, a shebang line with a CR in it — and a second copy is a second place for
those lessons to be re-learned by whoever edits only one of them. The presence
tracking is the same story: it looks trivial and it was wrong, in a way only a
running server revealed.

WHAT IS NOT HERE. Routes, payloads, fingerprints and anything that knows what a
store or a test suite IS. A viewer's meaning belongs to the viewer.

Usage
    py viewer_serving.py --help     (it has no verbs; it is imported)
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# How long a server waits after its last tab goes away before stopping. The
# grace is not politeness: a RELOAD is a tab closing and another opening, and a
# server that stopped between the two would take itself down every time the
# user pressed F5.
GRACE_SECONDS = 45
# A page that never says hello at all — a tab opened and abandoned, or a probe
# — must not hold the server open forever either.
IDLE_SECONDS = 90
DEFAULT_POLL_SECONDS = 5


# --------------------------------------------------------------------------
# who is watching
# --------------------------------------------------------------------------

class Presence(object):
    """Which tabs are open, so a server can stop when the last one goes.

    Counting alone is not enough: a browser that is killed sends no goodbye,
    and a count that only ever goes up keeps the process alive forever. So a
    tab is remembered by the last time it was HEARD FROM — the poll doubles as
    the heartbeat — and one silent for longer than the grace period is treated
    as gone.

    A TAB MUST NAME ITSELF, and the caller enforces that. Identifying it by its
    connection is the defect this class was first written with: HTTP/1.0 closes
    every request, so `hello` and `goodbye` arrive from two different ephemeral
    ports and read as two different tabs. The count never falls, and the one
    lifecycle promise a look-and-close viewer makes is never kept.
    """

    def __init__(self, grace=GRACE_SECONDS, idle=IDLE_SECONDS):
        self.grace = grace
        self.idle = idle
        self.lock = threading.Lock()
        self.seen = {}
        self.started = time.time()
        self.ever = False

    def hello(self, tab):
        with self.lock:
            self.ever = True
            self.seen[tab] = time.time()

    def goodbye(self, tab):
        with self.lock:
            self.seen.pop(tab, None)

    def beat(self, tab):
        with self.lock:
            self.ever = True
            self.seen[tab] = time.time()

    def watchers(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            for tab, last in list(self.seen.items()):
                if now - last > self.grace:
                    del self.seen[tab]
            return len(self.seen)

    def should_stop(self, now=None):
        """True once nothing is watching and something once was — or once
        nothing ever arrived and the idle window has passed."""
        now = time.time() if now is None else now
        if self.watchers(now):
            return False
        if self.ever:
            return True
        return now - self.started > self.idle


# --------------------------------------------------------------------------
# page plumbing
# --------------------------------------------------------------------------

def inject(html, snippet):
    """Put `snippet` before </body>. Only ever applied to bytes WE produced.

    A frozen template and the frozen js/css are copy-fidelity subjects, and an
    injection into one of them would break the gate somewhere else entirely.
    """
    text = html.decode("utf-8")
    if "</body>" in text:
        return text.replace("</body>", snippet + "</body>", 1).encode("utf-8")
    return (text + snippet).encode("utf-8")


class PageAssembly(Exception):
    """A page was not the shape the assembler required.

    Raised, never returned as a warning: every caller here builds bytes it is
    about to serve, and a page that quietly did not get the surgery it asked
    for is exactly the defect this class exists to make impossible.
    """


def detach_script(html, src):
    """Remove the ONE `<script src="`src`">` tag, or raise.

    WHAT THIS IS FOR. A SERVED page is the frozen template with an EMPTY
    payload plus a loader that fetches `data.json`, fills the data element and
    only THEN appends the viewer script — because the viewer parses that
    element the moment it executes. But the template carries its own
    `<script src>` for the standalone snapshot, where the data really is
    inlined, and `inject` only ever appends. So the served page shipped BOTH
    tags and every viewer ran TWICE: two closures over one DOM, two sets of
    pointer and wheel listeners, two `state` objects fighting over one
    transform, and every control the page appends rather than replaces drawn
    twice. The loader has to be the sole owner of the load, which means the
    template's own tag comes out of the bytes we serve.

    EXACTLY ONE, or an error. A silent no-op is how this comes back: the day
    the template's tag gains an attribute, a forgiving matcher would find
    nothing, remove nothing, and hand back a page that loads its viewer twice
    again — with no failure anywhere to say so.
    """
    text = html.decode("utf-8")
    pattern = re.compile(
        r'<script\b[^>]*\bsrc\s*=\s*"%s"[^>]*>\s*</script>\s*'
        % re.escape(src))
    found = pattern.findall(text)
    if len(found) != 1:
        raise PageAssembly(
            'expected exactly one <script src="%s"> in the page, found %d — '
            "the loader cannot be the only thing that runs the viewer unless "
            "the template's own tag is removed from the served bytes"
            % (src, len(found)))
    return pattern.sub("", text, count=1).encode("utf-8")


def script_sources(html):
    """Every `src` a STATIC `<script>` element names, in document order.

    Static only: a script the page appends at runtime (the loader does exactly
    that) is not an element in these bytes and is not counted here. So this
    answers "what will the parser run", which is the half `detach_script` acts
    on — how many times the viewer really executes is a question only a page
    that has been RUN can answer, and the suite asks it there.
    """
    text = html.decode("utf-8") if isinstance(html, bytes) else html
    return re.findall(r'<script\b[^>]*\bsrc\s*=\s*"([^"]+)"', text)


def tab_from_query(path, fallback):
    """The tab id the page put in its own query string.

    Never the connection — see `Presence`. An unidentified poll is still
    counted as a watcher (something is asking) but under a name only it will
    ever use, so it ages out of the grace window instead of holding the server.
    """
    from urllib.parse import unquote
    query = path.split("?", 1)[1] if "?" in path else ""
    for part in query.split("&"):
        if part.startswith("tab="):
            value = unquote(part[4:]).strip()
            if value:
                return value
    return "anonymous:%s" % fallback


# --------------------------------------------------------------------------
# identity
# --------------------------------------------------------------------------

def identity_of(path):
    """The value two processes compare to agree they mean the same directory.

    `realpath`, never a resolved string (`windows-compatibility.md` §5): the
    same directory is reported sometimes by its 8.3 alias and sometimes by its
    long name, and comparing those as text calls one directory two places.
    """
    return os.path.normcase(os.path.realpath(str(path)))


# --------------------------------------------------------------------------
# finding a viewer that is already up
# --------------------------------------------------------------------------
#
# WHAT THIS REPLACED, AND WHY IT MATTERED SO MUCH. Both viewers used to walk
# every port of their block and issue an HTTP GET to each, 1.5 s timeout, one
# after another. On a machine where a closed loopback port REFUSES, that costs
# nothing: fifty instant failures. On a machine where a local firewall silently
# DROPS the SYN instead — measured here, `connect_ex` returning WSAEWOULDBLOCK
# after the full timeout — it costs the timeout fifty times over, and the
# launcher sat for 75 SECONDS before it began to build a page. The user's
# report was "the .cmd takes almost a minute"; this was all of it.
#
# So discovery is now two cheap steps and no serial HTTP walk:
#
#   1. THE ANNOUNCE FILE. A running server publishes its real URL beside the
#      OS temp directory under a name derived from the SAME digest as its
#      preferred port. One read, one probe, done — and it is right even when
#      the server had to take a port other than its preferred one.
#   2. A CONCURRENT TCP SWEEP, only if that fails. Connect-only, short
#      timeout, many at once: a port that accepts is worth an HTTP question
#      and a port that does not is not. The full block still gets looked at —
#      a viewer is found wherever it is — for well under a second.
#
# Neither step can be confused by a stranger: the identity route decides, and
# an announcement that no longer answers is deleted rather than believed.

ANNOUNCE_CONNECT_TIMEOUT = 0.25
ANNOUNCE_SWEEP_WORKERS = 16
PING_TIMEOUT = 1.5


def announce_path(kind, target):
    """The rendezvous file for one viewer of one target.

    In the OS temp directory, never in the tree: a store and a `testing/` hold
    content, and where a process happens to be listening this minute is
    machine state with the lifetime of a process.

    Keyed by the same normalized `realpath` digest as `viewer_ports`' preferred
    port (`windows-compatibility.md` §5), so one directory reached through a
    junction, a `subst` drive or its 8.3 alias is ONE announcement — the bug
    that gave one project two preferred ports would otherwise give it two
    rendezvous files as well.
    """
    normalized = identity_of(target)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / ("%s-viewer-%s.announce"
                                          % (kind, digest))


def write_announcement(path, url, identity):
    """Publish where this server is. Best effort, never fatal.

    A viewer that cannot write its announcement still serves; the next
    launcher pays the sweep instead of the read, which is slower and correct.
    """
    try:
        Path(path).write_text(
            "VIEWER URL: %s\nPID: %d\nIDENTITY: %s\n"
            % (url, os.getpid(), identity), encoding="utf-8")
    except OSError:
        pass


def read_announcement(path):
    """`{"url", "pid", "identity"}` from an announce file, or None."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    fields = {}
    for line in text.splitlines():
        label, _, value = line.partition(": ")
        fields[label.strip()] = value.strip()
    url = fields.get("VIEWER URL")
    if not url:
        return None
    return {"url": url, "pid": fields.get("PID", ""),
            "identity": fields.get("IDENTITY", "")}


def clear_announcement(path):
    """Remove an announcement. A stale one must not outlive its server."""
    try:
        os.remove(str(path))
    except OSError:
        pass


def ask(url, timeout=PING_TIMEOUT):
    """GET a JSON route, or None.

    Never raises: a port answering something that is not our viewer is an
    ordinary outcome, not an error.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.HTTPError):
        return None


def port_accepts(host, port, timeout=ANNOUNCE_CONNECT_TIMEOUT):
    """True when something accepts a TCP connection on `host:port` now.

    Connect and close, nothing sent. This is the cheap half of discovery: a
    dropped SYN costs the timeout, but the timeout is a quarter of a second
    and the whole block is asked at once — where a real server, being local,
    answers in a millisecond or two.
    """
    sock = socket.socket()
    try:
        sock.settimeout(timeout)
        return sock.connect_ex((host, int(port))) == 0
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def accepting_ports(host, candidates, timeout=ANNOUNCE_CONNECT_TIMEOUT,
                    workers=ANNOUNCE_SWEEP_WORKERS):
    """Those of `candidates` accepting connections, in the order given."""
    candidates = list(candidates)
    if not candidates:
        return []
    size = max(1, min(workers, len(candidates)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=size) as pool:
        verdicts = list(pool.map(
            lambda port: port_accepts(host, port, timeout), candidates))
    return [port for port, live in zip(candidates, verdicts) if live]


def find_server(kind, target, identity, field, candidates, host):
    """The URL of a viewer of `kind` already serving `target`, or None.

    `field` is the key the viewer's `/ping` answers its identity under
    (`store` for the memory viewer, `project` for the coverage viewer) — the
    only thing that decides. A port says nothing about who holds it, so a
    server that answers with a different identity is passed over, and one that
    answers nothing at all is passed over too.
    """
    announced = read_announcement(announce_path(kind, target))
    if announced:
        answer = ask(announced["url"] + "ping")
        if answer and answer.get(field) == identity:
            return announced["url"]
        # It answered as someone else, or not at all. Either way the
        # announcement is a lie now, and a lie left on disk is read again.
        clear_announcement(announce_path(kind, target))

    for port in accepting_ports(host, candidates):
        url = "http://%s:%d/" % (host, port)
        answer = ask(url + "ping")
        if answer and answer.get(field) == identity:
            return url
    return None


# --------------------------------------------------------------------------
# the launchers
# --------------------------------------------------------------------------

CMD_TEMPLATE = """@echo off
REM %(launcher)s.cmd - open THIS %(subject)s's %(title)s.
REM
REM THIS is the file to click on Windows. %(launcher)s.sh beside it is the same
REM launcher for Linux and macOS; Windows has no execute association for .sh,
REM so clicking that one only offers to open it in an editor.
REM
REM WHY A SERVER AND NOT JUST THE HTML: %(page)s beside this file is a
REM BOOTSTRAP. It holds no records. A page opened straight off disk is a
REM file:// page, and browsers forbid those from reading local files, so it
REM cannot read %(reads)s. Served over loopback, the same page is rebuilt on
REM every request and reloads itself when its source changes.
REM
REM IT CLEANS UP AFTER ITSELF: closing the last viewer tab stops the server.
REM IT KEEPS TO ITSELF: its port is derived from this %(subject)s's own path,
REM it serves only this one, and it never looks for or talks to another.
REM
REM GENERATED by `%(server)s install`. Wired to the %(subject)s beside it.
setlocal EnableDelayedExpansion
set "HERE=%%~dp0"
set "HERE=%%HERE:~0,-1%%"

REM Pick an interpreter by RUNNING it, never by asking `where`: `python` on
REM Windows may be the Microsoft Store ALIAS STUB, a real file on PATH that is
REM not Python. It prints an advert and exits. `where` says yes and execution
REM says no, and only the second answer is worth having.
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (
  echo %(launcher)s: no working Python found ^(tried: py -3, python^).
  echo %(launcher)s: %(page)s beside this file is a BOOTSTRAP and holds no
  echo %(launcher)s: records: it fills itself from this viewer once the viewer
  echo %(launcher)s: runs. Without Python there is nothing to read yet.
  pause
  exit /b 2
)

if not exist "%%HERE%%\\%(server)s" (
  echo %(launcher)s: %(server)s is not beside this launcher.
  echo %(launcher)s: this %(subject)s carries its own viewer so the repository
  echo %(launcher)s: works when cloned alone; without it there is nothing to
  echo %(launcher)s: serve. Restore it with:
  echo %(launcher)s:   %(server)s install --%(flag)s "%(target_cmd)s"
  echo %(launcher)s: run from a tree that still has one.
  pause
  exit /b 2
)
%(prelude_cmd)s
%%PY%% "%%HERE%%\\%(server)s" serve --%(flag)s "%(target_cmd)s" --open-browser %%*
REM A .cmd double-clicked from Explorer closes its window the instant the
REM script ends, so a named exit nobody can read is the same as no message at
REM all. This is where the exhausted-port-block message lands.
if errorlevel 1 pause
endlocal
"""

SH_TEMPLATE = """#!/bin/sh
# %(launcher)s.sh - open THIS %(subject)s's %(title)s.
#
# The same launcher as %(launcher)s.cmd, for Linux and macOS.
#
# WHY A SERVER AND NOT JUST THE HTML: %(page)s beside this file is a BOOTSTRAP.
# It holds no records. A page opened straight off disk is a file:// page, and
# browsers forbid those from reading local files, so it cannot read %(reads)s.
#
# IT CLEANS UP AFTER ITSELF: closing the last viewer tab stops the server.
# IT KEEPS TO ITSELF: its port is derived from this %(subject)s's own path, it
# serves only this one, and it never looks for or talks to another.
#
# GENERATED by `%(server)s install`. Wired to the %(subject)s beside it.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Shortlisted, then chosen by RUNNING it: a name on PATH that is not a working
# interpreter is the same problem here as the Microsoft Store stub on Windows.
PY=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1 &&
     "$cand" -c "import sys" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "%(launcher)s: no working Python found (tried: python3, python, py)." >&2
  echo "%(launcher)s: %(page)s beside this file is a BOOTSTRAP and holds no" >&2
  echo "%(launcher)s: records; it fills itself from this viewer once it runs." >&2
  exit 2
fi

if [ ! -f "$HERE/%(server)s" ]; then
  echo "%(launcher)s: %(server)s is not beside this launcher." >&2
  echo "%(launcher)s: this %(subject)s carries its own viewer so the" >&2
  echo "%(launcher)s: repository works when cloned alone. Restore it with:" >&2
  echo "%(launcher)s:   %(server)s install --%(flag)s \\"%(target_sh)s\\"" >&2
  exit 2
fi
%(prelude_sh)s
exec "$PY" "$HERE/%(server)s" serve --%(flag)s "%(target_sh)s" --open-browser "$@"
"""


def launcher_texts(spec):
    """(cmd_text, sh_text) for one viewer, from one description of it.

    `spec` carries: launcher, subject, title, page, reads, server, flag, and
    optional prelude_cmd / prelude_sh / target_cmd / target_sh.

    WHAT `target_*` IS FOR, AND WHAT IT COST TO LEARN. Both templates used to
    hard-code the launcher's OWN directory as the value of `--<flag>`, which is
    right for the memory viewer — `--store` IS the directory the launcher sits
    in — and wrong for the coverage viewer, whose `--project` is the REPOSITORY
    and whose launcher sits in `testing/` one level below it. The generated
    `coverage-view.cmd` therefore ran `serve --project <repo>/testing`, and
    every launch died with "no testing/ directory in <repo>/testing". The
    coverage spec carried a comment saying the flag "has to climb one level"
    and nothing implemented it, because nothing ever RAN the launcher: the
    tests read the text this template produced, in this template's own
    vocabulary, and agreed with it.

    So the target is now a property of the viewer, stated once beside the flag
    it belongs to, and the suite executes both launchers.
    """
    filled = dict(spec)
    filled.setdefault("prelude_cmd", "")
    filled.setdefault("prelude_sh", "")
    filled.setdefault("target_cmd", "%HERE%")
    filled.setdefault("target_sh", "$HERE")
    return CMD_TEMPLATE % filled, SH_TEMPLATE % filled


def write_launchers(target, spec, write_if_changed):
    """Write both launchers into `target`; return the names written.

    Each is written with the line endings ITS INTERPRETER needs, and neither is
    a preference: cmd.exe mis-parses an LF-only batch file, and `sh` reads a CR
    as part of the interpreter name on the shebang line.
    """
    cmd_text, sh_text = launcher_texts(spec)
    written = []
    for name, text in (("%s.cmd" % spec["launcher"], cmd_text),
                       ("%s.sh" % spec["launcher"], sh_text)):
        newline = "\r\n" if name.endswith(".cmd") else "\n"
        payload = text.replace("\n", newline).encode("utf-8")
        if write_if_changed(Path(target) / name, payload):
            written.append(name)
    make_executable(Path(target) / ("%s.sh" % spec["launcher"]))
    return written


def make_executable(path):
    """Give a .sh its execute bit where the platform has one.

    On Windows the filesystem has no such bit — git records it in the INDEX —
    so this is a no-op there. Failing loudly for a mode change nobody can make
    would turn an install into an error on the platform it was written for.
    """
    try:
        mode = os.stat(str(path)).st_mode
        os.chmod(str(path), mode | 0o111)
    except OSError:
        pass


# --------------------------------------------------------------------------
# installing a vendored package
# --------------------------------------------------------------------------

def vendor(source, target, files, write_if_changed):
    """Copy `files` (target-relative -> source path parts) into `target`.

    Returns (written, missing). Nothing is written that is already identical,
    so a second install puts no diff in the repository for having looked — and
    `install` is run by a launcher and by every redistribution.
    """
    written, missing = [], []
    source, target = Path(source), Path(target)
    for relative, parts in files:
        origin = source.joinpath(*parts)
        if not origin.is_file():
            missing.append(str(origin))
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if write_if_changed(destination, origin.read_bytes()):
            written.append(relative)
    return written, missing


def ensure_ignored(path, lines):
    """Add `lines` to a `.gitignore`, keeping what is already there.

    BYTES IN, BYTES OUT, in the file's own line-ending convention. This
    read `read_text()` and wrote `write_bytes()`, and on Windows universal
    newlines decode every CRLF to LF: appending one line to a CRLF
    `.gitignore` silently rewrote the whole file LF-only. Under a
    repository that pins `* -text` — because something downstream compares
    BYTES — that is every line changed at once, with the real diff buried
    under it (`windows-compatibility.md` 2).
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError:
        raw = b""
    text = raw.decode("utf-8", "replace")
    have = {line.strip() for line in text.splitlines()}
    missing = [line for line in lines if line not in have]
    if not missing:
        return False
    # The file's own ending, not the platform's: a new file is LF, and an
    # existing one keeps whatever it already uses.
    ending = "\r\n" if raw.count(b"\r\n") * 2 > raw.count(b"\n") else "\n"
    if text and not text.endswith(("\n", "\r")):
        text += ending
    text += ending.join(missing) + ending
    path.write_bytes(text.encode("utf-8"))
    return True


def blocked(error, hint):
    print(json.dumps({"status": "BLOCKED", "error": error, "hint": hint}))
    return 2


def open_browser(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass


def serve_until_last_tab(server, presence, url, open_it=False):
    """Run until the last tab closes; return 0. Shared by both viewers."""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if open_it:
        open_browser(url)
    try:
        while not presence.should_stop():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    server.shutdown()
    server.server_close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="viewer_serving.py",
        description="Shared floor for the look-and-close viewers (imported, "
                    "not run: it has no verbs of its own)")
    parser.parse_args(argv)
    print(json.dumps({
        "status": "COMPLETED",
        "note": "this module is imported by memory_views.py and "
                "coverage_views.py; it has no verbs of its own",
        "grace_seconds": GRACE_SECONDS,
        "idle_seconds": IDLE_SECONDS,
        "poll_seconds": DEFAULT_POLL_SECONDS,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
