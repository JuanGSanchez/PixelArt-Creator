#!/usr/bin/env python3
"""The ONE allocation table for every local port this skill's tooling binds.

WHY THIS FILE EXISTS
--------------------
Before it, there was no authority. The design viewer had hard-coded
``PORT_RANGE_START = 8710`` in ``viewer/serve.py``; a delivered memory viewer
walked ``8765`` upward with a span of 100; ``evidence_receipt.py`` had taken
41000-42999 for test-run resources; and ``viewer-protocol.md`` documented no
port policy at all. The first two OVERLAPPED on 8765-8789 — a memory viewer
could take the port a design viewer was about to prefer, and neither knew the
other existed. Two ranges chosen independently in two files is not a policy,
it is a collision waiting for the machine to be busy enough.

So: one table, here, and every binder reads it. A range that is not in this
table is not allocated.

A block is claimed HERE before its server exists, and that order is deliberate:
a range claimed by the file that binds it is a range nobody else can see, which
is exactly how the two overlapping ranges above were each chosen in good faith.
Every block in the table now has its server; the next viewer type takes the
next block rather than picking a number.

THE TABLE
---------
    41000-42999   test-run resources   evidence_receipt.py (RESERVED, below)
    43000-43049   design viewer        viewer/serve.py
    43050-43099   memory viewer        memory_views.py
    43100-43149   coverage viewer      coverage_views.py
    43150+        unallocated          reserved for future viewer types

Every viewer range is the SAME SIZE (50) on purpose: the ranges are compared
and reasoned about as blocks, and a range that is bigger "because that viewer
seemed more important" turns the table into a set of special cases.

The blocks sit at 43000+ because that is below the WINDOWS dynamic floor
(49152; measured with `netsh int ipv4 show dynamicport tcp`), so on Windows the
OS will not hand a viewer's port to an unrelated process while that viewer is
between two launches.

Be exact about the other platform rather than comfortable: on Linux the default
`net.ipv4.ip_local_port_range` is 32768-60999, so these blocks sit INSIDE it. A
viewer's preferred port there can be held for a while by somebody's outbound
connection. That is not a hole in the policy, it is what the in-block WALK is
for — and it is the reason the walk is a real mechanism rather than a
formality. No range that stays under 49152 can be clear of both floors at once;
claiming otherwise would be a comfortable sentence that no machine backs.

The 41000-42999 test-resource block is RESERVED here but DEFINED in
``evidence_receipt.py`` (``PORT_LOW`` / ``PORT_HIGH``). It is deliberately not
re-declared as a constant this module hands out: a test harness must not have
to import a viewer module to allocate a stub server's port. The two are held
equal by a test rather than by an import — see ``check_testing``'s registration
note and ``testing/suites/test_04_viewer_ports.py``.

THE ONE-TIME URL CHANGE, RECORDED
---------------------------------
``viewer/serve.py``'s ``preferred_port()`` promised, in its own docstring, that
"a project's viewer URL never changes". Moving the design viewer off 8710-8789
BREAKS that promise ONCE, for every existing project: an open tab bookmarked at
the old address will not find a viewer there again. That was a deliberate cost,
accepted by the user on 2026-08-25, because the overlap above is a live defect
either way and a table with one block at 8710 and the rest at 43000+ stays
irregular forever. From the move onward the promise holds again: the port is
still a pure function of the target path.

DETERMINISM
-----------
The preferred port is a hash of the normalized target path (``hashlib``, not
``hash()``, which is salted per process), so it is stable across relaunches AND
across Python processes, while distinct targets land on distinct preferred
ports instead of fighting over one. When the preferred port is taken, the walk
is the rest of the range in a deterministic rotation — never an OS-assigned
ephemeral port, because a viewer whose address is unpredictable cannot be
announced ahead of time by a launcher or found again by the user.

When the WHOLE range is busy, binding fails with a NAMED EXIT (P-01) rather
than falling back outside the table: a viewer answering on a port no policy
covers is exactly the collision this file exists to end.

Usage
    py viewer_ports.py table                       the allocation table
    py viewer_ports.py port --kind memory --target <path>
"""

import argparse
import hashlib
import http.server
import os
import socket
import sys

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# kind -> (start, size, owner, lifecycle, purpose). Ordered as the table
# prints. `size` is the same for every viewer kind by design (see module
# docstring); a differing size is a defect, and a test asserts it.
ALLOCATIONS = (
    ("design", 43000, 50, "scripts/viewer/serve.py",
     "keep-alive 2 h + one automatic relaunch",
     "the design viewer: a project's living specification, a standing work "
     "surface for the whole session"),
    ("memory", 43050, 50, "scripts/memory_views.py",
     "auto-stop when the last tab closes",
     "the memory graph of ONE store: look, learn, close"),
    ("coverage", 43100, 50, "scripts/coverage_views.py",
     "auto-stop when the last tab closes",
     "the test-coverage map of ONE repository's testing/: look, learn, close"),
)
RANGES = {kind: (start, size) for kind, start, size, _, _, _ in ALLOCATIONS}

# RESERVED, not allocated by this module — see the module docstring. Held
# equal to evidence_receipt.PORT_LOW / PORT_HIGH by a test, never by an import.
RESERVED_TEST_RESOURCES = (41000, 42999)

# The first port above every block in the table. Recorded so a future viewer
# type takes the next block instead of guessing.
NEXT_FREE_BLOCK = max(start + size for _, start, size, _, _, _ in ALLOCATIONS)

HOST = "127.0.0.1"


class RangeExhausted(OSError):
    """Every port in a kind's range is held by something else.

    Carries the message a launcher prints to the user before exiting. It is a
    NAMED EXIT (P-01): it says what was tried, what is in the way, and the
    exact command that shows who holds the ports — not "could not bind".
    """

    def __init__(self, kind):
        start, size = RANGES[kind]
        self.kind = kind
        self.start = start
        self.size = size
        super().__init__(self.message())

    def message(self):
        end = self.start + self.size - 1
        prefix = str(self.start)[:3]
        return (
            "All %d ports of the %s-viewer range (%d-%d) are in use, so this "
            "viewer has nowhere to listen.\n"
            "Nothing was started, and nothing was changed.\n"
            "\n"
            "Each viewer holds one port for as long as it runs, so the usual "
            "cause is viewers left open.\n"
            "Close some viewer windows and try again, or see who holds the "
            "ports:\n"
            "    netstat -ano | findstr :%s        (Windows)\n"
            "    ss -ltnp | grep :%s               (Linux / macOS)"
            % (self.size, self.kind, self.start, end, prefix, prefix)
        )


def preferred_port(kind, target):
    """The stable per-target port for ``kind``.

    ``target`` is whatever the viewer is bound to — a design.json path, a
    memory store directory, a repository's ``testing/`` directory.

    ``realpath``, never ``abspath`` (``windows-compatibility.md`` 5). One
    directory reached through a junction, a ``subst`` drive or its 8.3
    alias is spelled several ways, and ``abspath`` preserves every
    spelling: two spellings became two preferred ports and two announce
    files for the same target, so a second launcher started a second
    viewer for a store that already had one. The design viewer normalized
    at its own call site and the memory and coverage viewers did not,
    which is the reason the digest itself does it now — one key per
    directory for every kind, and the call-site normalization stays
    harmless because ``realpath`` is idempotent.
    """
    start, size = RANGES[kind]
    normalized = os.path.normcase(os.path.realpath(str(target)))
    digest = hashlib.sha256(normalized.encode("utf-8")).digest()
    return start + int.from_bytes(digest[:4], "big") % size


def candidate_ports(kind, target):
    """Every port of the range, preferred first, then a fixed rotation.

    Deterministic on purpose: two viewers started in the same order on the
    same machine land on the same ports, so a launcher can say where its
    viewer will be before it is up, and a user who closed a tab finds the
    same address again.
    """
    start, size = RANGES[kind]
    first = preferred_port(kind, target) - start
    return [start + (first + step) % size for step in range(size)]


def _exclusive(sock):
    """One owner per port on Windows (`windows-compatibility.md` §4).

    ``SO_REUSEADDR`` there means "let anyone else bind my port too", which is
    the opposite of what a local server wants: a second process could hijack
    the listening port of a running viewer. ``SO_EXCLUSIVEADDRUSE`` gives the
    semantics POSIX ``SO_REUSEADDR`` users actually expect — and, here,
    deterministic bind failures, which is what makes the walk trustworthy.
    """
    if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)


class ExclusiveHTTPServer(http.server.ThreadingHTTPServer):
    """Threading HTTP server that owns its port exclusively.

    ``allow_reuse_address`` is switched OFF: inherited as 1 from
    ``HTTPServer``, it would set ``SO_REUSEADDR`` and re-introduce exactly the
    hijack ``_exclusive`` prevents.
    """

    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        _exclusive(self.socket)
        http.server.ThreadingHTTPServer.server_bind(self)


def serve_in_range(kind, target, handler, host=HOST,
                   server_class=ExclusiveHTTPServer):
    """Bind a server for ``kind`` on the first free port of its range.

    Returns the bound, not-yet-serving server. Raises ``RangeExhausted`` — a
    named exit, never a silent fallback to an ephemeral port — when the whole
    range is held.
    """
    for port in candidate_ports(kind, target):
        try:
            return server_class((host, port), handler)
        except OSError:
            continue
    raise RangeExhausted(kind)


def port_is_free(kind, port, host=HOST):
    """True when ``port`` can be bound right now for ``kind``'s host.

    A probe, and honest about being one: the answer is only true for the
    instant it was taken. Callers that need the port must BIND it, not ask.
    """
    if port not in range(RANGES[kind][0], RANGES[kind][0] + RANGES[kind][1]):
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _exclusive(sock)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def table_lines():
    """The allocation table, exactly as the documentation carries it."""
    lines = ["%-9s %-13s %-28s %s" % ("KIND", "PORTS", "OWNER", "LIFECYCLE")]
    low, high = RESERVED_TEST_RESOURCES
    lines.append("%-9s %-13s %-28s %s"
                 % ("(test)", "%d-%d" % (low, high),
                    "scripts/evidence_receipt.py",
                    "per test run — RESERVED, defined there"))
    for kind, start, size, owner, lifecycle, _ in ALLOCATIONS:
        lines.append("%-9s %-13s %-28s %s"
                     % (kind, "%d-%d" % (start, start + size - 1),
                        owner, lifecycle))
    lines.append("%-9s %-13s %-28s %s"
                 % ("(free)", "%d+" % NEXT_FREE_BLOCK, "—",
                    "the next viewer type takes this block"))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="The allocation table for every local port this skill's "
                    "tooling binds")
    sub = parser.add_subparsers(dest="verb", required=True)
    sub.add_parser("table", help="print the allocation table")
    port = sub.add_parser("port", help="the preferred port for one target")
    port.add_argument("--kind", required=True, choices=sorted(RANGES),
                      help="viewer kind")
    port.add_argument("--target", required=True,
                      help="what the viewer is bound to (data file, store "
                           "directory, testing/ directory)")
    args = parser.parse_args(argv)

    if args.verb == "table":
        for line in table_lines():
            print(line)
        return 0
    print(preferred_port(args.kind, args.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
