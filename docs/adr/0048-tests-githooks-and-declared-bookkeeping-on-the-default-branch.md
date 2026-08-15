# ADR-0048 — Bookkeeping on the default branch must be declared, and `tests/githooks/` proves it

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-08-15 |
| Author | AGT-09 (GitHub/DevOps) |
| Feature | Default-branch write policy — closing the hole that let six undeclared commits onto `main` |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0047 (`tests/scripts/` — the peer-test-root precedent this mirrors, one family across: the repository's own gates rather than its CI scripts), ADR-0043 (`tests/deploy/`) |

## Context

**The rule this repository actually holds** is that its default branch takes
the repository's creation commit and merges, and everything else arrives
through a pull request. `.githooks/pre-commit` is what enforces it locally, and
a local hook is the only enforcement there is: nothing on a developer's machine
can police the remote, and pushing an already-guarded local branch to its
remote is the ordinary flow, not a bypass.

**The hole.** The gate decided "is this bookkeeping?" from the SHAPE of the
staged set alone — if every staged path fell under `.githooks/`,
`.gitattributes` or `memory/`, the commit was admitted with the message *"this
is the arrangement, not development."* That allowance exists for real reasons.
Those files are untracked in any product whose gate was installed after its
creation commit, and while they stay untracked the first branch commits them
and the merge back into the default branch aborts on *"untracked working tree
files would be overwritten"* — the default branch could then never receive a
pull request at all. `post-merge` also commits the refreshed map after every
merge, and a merge failed by its own bookkeeping hook is worse than a map
committed by hand.

But the staged set says what a commit *touches*. It cannot say who decided to
make it, and that is the question the rule turns on. On 2026-08-15 six commits
went onto the default branch through this door — a memory-map correction, two
compactions, index refreshes — each one staging nothing but `memory/`, each one
reported by the gate as the arrangement rather than development. None was
malicious and several were even required (compaction is legal *only* on the
default branch, by `memory_graph.py`'s own git guard). They were still six
commits that never passed a review the rule says they should have.

## Decision

**1. Bookkeeping on the default branch must be DECLARED.** The shape test
stays — it is still all-or-nothing, and one product path in the same commit is
development again regardless — but a store-only commit is now admitted only
when the caller sets `PIXELART_MAIN_BOOKKEEPING=1`. Without it the gate refuses
and names the two legitimate routes.

**2. The hook that makes the automated commit declares it.** `post-merge` sets
the variable for its own refresh commit and for that child process only, so
merges are unaffected and nothing later in that shell inherits an open door.

**3. A human doing store maintenance declares it deliberately and visibly** —
`PIXELART_MAIN_BOOKKEEPING=1 git commit …`. This is the same bargain
`--no-verify` already offers, and it is offered for the same reason: no local
gate can stop somebody who means it, but it can stop somebody who did not
notice which branch they were on. The difference between the old behaviour and
this one is not strength, it is **intent** — the act is now on the record in
the command that performed it.

**4. `tests/githooks/` is a peer test root**, owned by AGT-09 alongside
`tests/scripts/` (ADR-0047) and `tests/deploy/` (ADR-0043), for this
repository's own git hooks. It is collected by the default `testpaths` without
configuration change, since it lives under `tests/`.

**What that root may NOT become:** it tests the hooks in `.githooks/`. It is
not a second home for logic, data or UI tests, and it is not where the CI gate
scripts are tested — those are `tests/scripts/`.

## Consequences

**The hooks are tested as git runs them.** Every case builds a throwaway
repository, installs the real hooks, and drives an actual `git commit`. Nothing
imports or greps the script: a hook that git never executes would pass a
text-level test and fail in life. Fourteen cases cover every route to the
default branch — creation commit, development, store-only with and without the
declaration, each furniture path, furniture mixed with product code, the merge
path, and both branch cases — and the three that matter were **proven** by
reverting the gate to its shape-only form and watching them fail.

**Maintenance still works.** Compaction is only legal on the default branch, so
refusing store commits outright would have stranded the store; the declaration
keeps that path open while putting it on the record.

**A stub container is part of the fixture.** The hooks walk upward for the
container's own gate scripts and refuse to run without them — deliberately, so
an unrunnable gate is never a silent pass. The fixture supplies stubs for those
two checks so the branch rule under test is isolated; the rule itself is the
hook's own untouched code.

**This does not, and cannot, guard the remote.** Branch protection on the
forge is a separate mechanism with its own history in this project (GitHub Free
returns 403 for the required-review API on a private repository, so protection
here is CI-advisory). The local gate governs local commits; the pull request
governs what reaches the remote default branch.
