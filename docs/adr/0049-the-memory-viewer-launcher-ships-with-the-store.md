# ADR-0049 — The memory viewer's launcher ships with the store, and `tests/memory_view/` proves it

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-08-15 |
| Author | GitHub/DevOps |
| Feature | Memory viewer reachability — the launcher is source, not output |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0048 (`tests/githooks/`), ADR-0047 (`tests/scripts/`), ADR-0043 (`tests/deploy/`) — the peer-test-root pattern this follows |

## Context

This repository carries its own memory store at `memory/`: its own graph, its
own history, independent of the orchestration container's store above it. The
store was already complete and correct. What was missing was any way to *open*
it from here.

The viewer is served rather than read off disk, because a page opened off disk
is a `file://` page: it can neither re-read `nodes.jsonl` nor run `git log`,
having no access to local files. Served over loopback, the page is built from
the logs and from `git log` on every request.

**A correction, made before this ADR was merged.** An earlier draft of this
paragraph went on to conclude that `graph-view.html` must therefore carry the
whole graph and commit history substituted in at render time, "for a reason
that cannot be engineered around". That does not follow, and the file it
justified reached 12 MB. *No access to local files* is not *no access to the
network*: a `file://` page may fetch across origins when the other end allows
it, and the viewer server sends `Access-Control-Allow-Origin: *`. The rendered
page now carries **no records at all** — it scans the port range for the live
viewer serving its own store, fetches `data.json` from it and renders in place,
and says what to run when no viewer is up. It is a template, not a photograph,
and it is ~9 KB.

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
two assets beside it are **derived** — regenerated on demand — and stay
gitignored. The **launcher is source**: written, reviewable, and shipped.

That the page is now ~9 KB rather than 12 MB does not change this. It is still
generated output, and tracking generated output means every regeneration is a
diff nobody wrote.

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

**6. `tests/memory_view/` is a peer test root**, owned by DevOps beside
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

## Amendment (2026-08-16) — the page assets ship with the launcher; only rebuildable artifacts stay untracked

*Appended, never rewritten: this ADR is immutable by convention. This section
amends **Decision §2** only. Decisions §1 and §3–§6, the Context and the
Consequences stand exactly as written.*

**What moved.** Decision §2 drew the tracking line at *source vs generated*: the
launcher ships, the page beside it is output and stays ignored. The user's
2026-08-16 ruling moves the line to *shipped vs rebuildable*, on the ground that
a clone should carry **the whole viewer** and not a launcher for a page that is
not there. The three page assets — `graph-view.html`, `graph-view.css`,
`graph-view.js` — are now tracked files of this repository, beside the launcher
and the store they open.

**1. What is tracked.** `memory/memory-view.cmd` and `memory/memory-view.sh`
(unchanged, Decision §1) **plus** `memory/graph-view.html`,
`memory/graph-view.css`, `memory/graph-view.js`. Two ignore rules had to go, not
one: the three lines in `memory/.gitignore`, and an unanchored `graph-view.html`
pattern in `.gitignore`'s "(c) Memory-graph derived files" section. `git ls-files`
confirmed no other file in the repository bears that name, so removing the root
pattern narrows nothing else.

**2. What stays untracked — and why the residue is exactly this.** Only
artifacts a scan rebuilds from the logs, plus the halves of the store that are
not this store's records: `graph/index.db`, `graph/index.db-wal`,
`graph/index.db-shm`, `graph/scan-state.json`, `graph/.lock`, and `insight/`,
`cards/`, `promotions.jsonl`, `archive/`. Nine lines; that is the whole of
`memory/.gitignore` now.

**3. No rendered snapshot is committed, and the live server is untouched.** The
tracked `graph-view.html` is the **empty-payload template**, not a photograph of
this store. The fidelity analysis run before the commit (byte-compare against the
container's copy-fidelity originals under `scripts/memory-viewer/`, 2026-08-16)
found `graph-view.css` (16,576 bytes) and `graph-view.js` (119,834 bytes)
**SHA-256 identical** to their originals, and `graph-view.html` divergent from
`template.html` (9,645 vs 6,142 bytes) for one fully accounted reason: the region
up to the `/*__GRAPH_DATA__*/` placeholder is byte-identical to the template's
prefix, and the placeholder carries exactly one substitution — an **empty**
payload (`{"edges": [], "git": {"commits": [], "state": "off"}, "meta": {},
"nodes": []}`) followed by the `OFFLINE_PAGE` probe/banner script defined
verbatim in the container's `memory_views.py`. Not one node, edge or commit is
baked in. The 12 MB page the Context paragraph above warns about is still
refused; ~9 KB of template is not that page. The viewer **server** — the port
walk, the per-request re-read of the logs and of `git log`, the auto-shutdown
when the last tab closes — was not touched by any part of this change, and
Decision §3 (one implementation, N wirings, no copy of the server here) is
unaffected: tracking a byte-identical copy of an asset is a wiring, not a second
implementation.

**4. The no-container behaviour is unchanged, and was verified rather than
assumed (2026-08-16).** A single-branch clone was taken to a temporary directory
with no orchestration container within four levels above it, and the shell
launcher was run there. It printed the documented message — naming
`graph-view.html` beside it as "a TEMPLATE that fills itself from a running
viewer, and holds no records of its own" — started **no** server, and exited
**2**. Decision §5 holds verbatim. (The `.cmd` variant could not be driven
non-interactively from that shell; its source was compared line-by-line against
the `.sh` instead, and the two mirror each other.)

**5. The store-ensure engine was aligned by a RECORDED container-side fork, not
by a local workaround.** The container's `memory_graph.py` hard-coded the three
`graph-view.*` names into the ignore lines every store receives, and
`Store.ensure()` is append-only; because this repository's own `pre-commit` hook
runs `memory_graph.py refresh` whenever a staged path falls outside `memory/`,
the first relevant commit had the three lines re-appended **into it** by the hook.
The engine now splits its base list: the five derived artifacts are shared by
every store, the container list adds the three viewer assets, and the
**product-role** list adds only the four store-half entries — so a product store
no longer receives them at all. That divergence from the skill original is
declared, not drift: it is recorded in the container's fork registry
(an internal design record, outside this repository) under the qualified requirement
id **`20260816-decision-batch:R-10`**, carrying the forked and base SHA-256, the
base version `2.4.0-20260804`, the grounding, and the re-port duty. `ensure()`
stays append-only by design, so the lines already committed here were removed
once more by hand; the read-back of the committed *and* post-commit working-tree
`memory/.gitignore` (nine lines, byte-identical) is the proof that the engine no
longer puts them back.

**6. The guarding tests live in the `tests/memory_view/` root** (Decision §6
unchanged). `test_viewer_assets_tracked.py` is a companion to the launcher
module, not a duplicate: it covers the three page assets, and it checks with
`git check-ignore --no-index` deliberately — the **default**, index-aware check
reports a tracked path as *not ignored* however well a pattern matches it, and
would therefore have missed the exact regression in §5. Both directions are
exercised against a throwaway repository under `tmp_path`, so the checker's
directionality is proved without mutating this repository at review time. The
module also *parses* both launchers for the repo-relative files they name at run
time and asserts each is tracked, rather than hardcoding the expected set. No
test spawns a server.

**What this costs, stated plainly.** Three more tracked files that a regeneration
can turn into a diff nobody wrote — the objection Decision §2 raised, and it does
not evaporate. It is bounded instead: the CSS and JS are byte-identical copies of
container originals and move only when the original moves (copy fidelity governs
them, and the check that compares content is what would catch it); the HTML holds
no records, so it moves only when the template does. That bound is what made the
line movable at all — the page stopped being a photograph before this amendment
was possible.

**Status: Accepted (amended 2026-08-16).**
