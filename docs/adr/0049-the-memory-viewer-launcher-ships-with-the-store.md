# ADR-0049 — The memory viewer's launcher ships with the store, and `tests/memory_view/` proves it

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-08-15 |
| Author | AGT-09 (GitHub/DevOps) |
| Feature | Memory viewer reachability — the launcher is source, not output |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0048 (`tests/githooks/`), ADR-0047 (`tests/scripts/`), ADR-0043 (`tests/deploy/`) — the peer-test-root pattern this follows |

## Context

This repository carries its own memory store at `memory/`: its own graph, its
own history, independent of the orchestration container's store above it. The
store was already complete and correct. What was missing was any way to *open*
it from here.

The viewer is served, not opened from disk, and for a reason that cannot be
engineered around: `graph-view.html` is a snapshot with the whole graph and
commit history substituted in at render time, because a page opened off disk is
a `file://` page and browsers forbid a `file://` page from reading local files.
It can neither re-read `nodes.jsonl` nor run `git log`. Served over loopback,
the same page is rebuilt from the logs and from `git log` on every request.

**The defect.** The program that starts that server lived in the orchestration
container's `scripts/` directory — a repository with **no remote**. So the one
file a reader needs in order to open this repository's memory was invisible to
anyone who cloned this repository, and the viewer looked, reasonably, like it
had never been built.

## Decision

**1. The launcher ships in the store, beside the map it opens.**
`memory/memory-view.cmd` and `memory/memory-view.sh` are tracked files of this
repository.

**2. The distinction that governs what is tracked.** `graph-view.html` and the
two assets beside it are **derived** — regenerated from the logs on demand — and
stay gitignored; committing them would put a multi-megabyte rewrite into the
history every time the map moved. The **launcher is source**: written,
reviewable, and shipped.

**3. It carries no copy of the server.** It resolves its own store from its own
location, walks up for the container's `memory_views.py` — the same mechanism
`.githooks/*` already use to find `check_branch_naming.py` — and hands it this
store's path. One implementation, N wirings, rather than N copies to drift
apart. Every copy is byte-identical; nothing absolute is baked in, so a clone
works wherever it lands.

**4. It serves THIS store only.** Each repository's memory is independent; a
launcher that served every store it could find would show this repository
somebody else's history.

**5. Without its container it explains itself.** A clone taken away from the
orchestration container has no viewer server. The launcher says so and names
the snapshot that still works, rather than failing quietly (Directive 12).

**6. `tests/memory_view/` is a peer test root**, owned by AGT-09 beside
`tests/githooks/`, `tests/scripts/` and `tests/deploy/`.

**Why not `tests/memory/`:** a directory named `memory` anywhere but the
repository root is the mistake the layout invariant names, and the structure
guard refuses writes into one. It refused this root's first name, correctly.
The root is named for what it tests.

## Consequences

**The two suites do not overlap.** The viewer SERVER — live re-reads,
auto-shutdown when the last tab closes, the port walk, the snapshot's probe —
lives in the container and is tested there, against a synthetic container, by
the container's own suite. This root tests what this repository can actually
own: that the launcher ships, is tracked rather than ignored, is wired by
position, scopes itself to this store, probes its interpreter by running it,
and degrades with an explanation. Duplicating the server tests here would need
a container this repository must not assume exists.

**One regression is pinned deliberately.** The shell launcher originally chose
its interpreter with `command -v python3`, which **succeeds on Windows**: the
Microsoft Store alias stub is a real file on `PATH` that is not Python — it
prints an install advert and exits. Existence is not availability. Both
launchers now probe by executing, and prefer `py -3`. The test asserts the
probe, not the outcome, so it holds on any platform.

**Both behaviours were proven, not assumed:** gitignoring the launcher and
baking an absolute path into it each fail the tests that claim to catch them.
