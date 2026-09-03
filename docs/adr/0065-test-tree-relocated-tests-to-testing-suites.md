# ADR-0065 — The test tree is relocated from `tests/` to `testing/suites/`

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-30 |
| Owner | the documentation (Documenter), recording an already-executed relocation |
| Grounded by | Branch `feat-go-public`, commits `a98f61f` (rename), `65026ad` (repoint references), `4280d77` (restore package chain); `pyproject.toml` `testpaths = ["testing/suites", "web_viewer/tests"]` |

## Context

Every prior ADR in this folder that names a test path names it as `tests/…`
— `tests/backend/`, `tests/deploy/`, `tests/logic/`, `tests/data/`,
`tests/ui/`, `tests/scripts/`, `tests/githooks/`, `tests/memory_view/` — because
that is where the test tree lived from this product's creation commit through
2026-08-29. On this branch the whole tree was folded into one directory named
`testing/`, with the actual test packages one level under it as
`testing/suites/<area>/`, so that a single top-level folder holds both the
test harness and the tests, matching the orchestration container's own
`testing/` convention. `web_viewer/tests/` did **not** move and is not part of
this decision: `web_viewer/` ships as a separately cloneable, separately
runnable package (ADR-0035), and its suite is a Python + Node ESM hybrid whose
`.mjs` half has no place inside a pytest tree.

This is a NAMING/LOCATION change, not a reopening of any test-ownership or
test-architecture decision recorded before it. ADR-0043 (deployment-acceptance
split), ADR-0047 (`tests/scripts/`), ADR-0048/0050 (`tests/githooks/`) and
ADR-0049 (`tests/memory_view/`) all still hold the ownership and shape
decisions they recorded; only the path prefix under which their subject
directories are found has changed.

## Decision

The test tree's canonical root is `testing/suites/`, effective 2026-08-30.
Every subdirectory that previously sat directly under `tests/` now sits under
`testing/suites/` with its own name unchanged (`tests/backend/` →
`testing/suites/backend/`, and so on for `deploy`, `logic`, `data`, `ui`,
`scripts`, `githooks`, `memory_view`). `pyproject.toml`'s `testpaths` was
updated to `["testing/suites", "web_viewer/tests"]`. Every executable
reference (imports, `conftest.py` `parents[N]` walks, CI workflow steps, the
doc-reference and path-portability gates' own invocations) was repointed in
the same change; this ADR records the fact of the move for the documentation
trail, it does not itself relocate anything.

Every ADR that cites an old `tests/…` path is read with `testing/suites/…`
substituted for the `tests/` prefix, for the subdirectories named above. Those
ADRs are **not** rewritten (an Accepted ADR is immutable) — this record is the
single durable cross-reference a reader follows instead. Two exceptions are
called out explicitly because a blanket substitution would be wrong for them:

1. ADR-0043's own **filename and title** still read `tests-deploy` / `` `tests/deploy/` `` — filenames are not amended in place; ADR-0043's Status field
   now points here.
2. `tests/backend/test_nginx_wss_localhost.py` and `tests/backend/test_vps_localhost.py`,
   as cited in some ADRs and in `testing/suites/ui/test_opacity_drag.py`, were
   **already** relocated to `tests/deploy/` by ADR-0043 itself (2026-07-31,
   before this move) — a citation using `backend` for either of those two
   specific files was stale even before 2026-08-30 (ADR-0043's own §"Obligations
   created" item 3 recorded this and left it undischarged); the correct
   post-2026-08-30 path for both is `testing/suites/deploy/`, not
   `testing/suites/backend/`.

## Alternatives considered

| Alternative | Why it was not chosen |
|---|---|
| Leave `tests/` at the repository root, add `testing/` only for non-pytest tooling | Rejected by the branch's own stated goal: one folder holding both harness and tests, mirroring the container's `testing/` convention — a split root does not achieve that. |
| Rewrite every prior ADR's path citations in place | An Accepted ADR is immutable (adr-author template); rewriting would erase the record of what the decision looked like when it was made and break any external reference to the old wording. |

## Consequences

**Accepted costs.** Every prose (docstring/comment) reference to a `tests/…`
path anywhere in the codebase or the ADR trail is now either updated (inside
`testing/suites/**`, where this branch's mandate allowed docstring/comment
edits) or stale-but-historically-truthful (inside already-Accepted ADRs,
where it is not rewritten). A reader of an old ADR must apply the substitution
rule above by hand unless they also read this record.

**What this enables.** One test root, `testing/suites/`, that is both the
pytest root and the same top-level name the container itself uses for its own
test tree — reducing the friction of `git -C main worktree add` cross-checks
between the two `testing/` locations — this repository's and the container's own.

**What it constrains.** Any future ADR or spec that names a test path names it
under `testing/suites/`, never `tests/`, from 2026-08-30 forward.

## Compliance

`pyproject.toml`'s `testpaths` and every CI workflow step naming a test path
are the enforcement surface: `python -B -m pytest --collect-only -q` collects
7610 tests from `testing/suites` + `web_viewer/tests` and 0 from any `tests/`
path (there is no `tests/` directory left to collect from). No automated gate
currently checks ADR prose for stale `tests/` citations; the two-exception
list above was produced by manual review during this same session, not by a
script, and is recorded as accepted risk rather than a covered gate.
