# ADR-0047 — `tests/scripts/`: a peer test root for this repository's own CI gate scripts

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-08-15 |
| Author | AGT-09 (GitHub/DevOps) |
| Feature | Test-tree ownership boundary — closing structural-audit finding PA-04 (S1) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0043 (`tests/deploy/` — the peer-test-root precedent this mirrors one level up, at the repository's own tooling instead of its deployment artifacts) |

## Context

**The finding (PA-04, S1).** Seven of the eight gate scripts under this repository's own
`scripts/` directory carry no test at all: `coverage_gate.py`, `check_layering.py`,
`check_cycles.py`, `path_portability_check.py`, `perf_profile.py`, `string_audit_check.py`,
`run_ci_locally.py`. Only `run_ci.py` — the GitHub-Actions/local-fallback router — is covered,
and only because `tests/deploy/test_run_ci_router.py` loads it via `importlib` and exercises its
pure classification functions directly. Six of the seven untested scripts decide whether CI goes
green (`coverage_gate`, `check_layering`, `check_cycles`, `path_portability_check`,
`string_audit_check`, and `perf_profile` via the frame-budget gate); the seventh
(`run_ci_locally.py`) is the human-facing entry point onto the same router. A gate that has never
been shown to fail is indistinguishable, by any evidence in this repository, from a script that
always exits 0.

**The boundary that created the gap.** The test tree already has a root for every layer and every
peer package that ships: `tests/logic`, `tests/data`, `tests/ui`, `tests/backend`,
`tests/deploy` (ADR-0043), and `web_viewer/tests`. None of those is a legitimate home for a test
of `scripts/coverage_gate.py`: `tests/logic`/`tests/data`/`tests/ui` are AGT-04/AGT-06 surfaces
that test `pixelart_creator/`, not this repository's own tooling, and `check_layering.py` itself
enumerates `scripts` under `UNGOVERNED_TOPLEVEL` with the reason "standalone P11 dev/CI
scripts — not shipped, not in the import graph" — it is explicitly outside the product's own
layering constitution. One level up, the **container's** own testing standard is explicit that
"product repositories are not units": the container suite may not cover product code, and this
repository IS the product. So a test of `scripts/coverage_gate.py` had nowhere it was allowed to
live — not in the container (wrong side of the boundary), not in any existing product test root
(wrong remit). The gap in PA-04 is a direct consequence of that missing root, not of neglect by
any test-owning agent.

**Why this agent, not the logic/data test owner.** These seven scripts are not product logic —
they are the deterministic CI gates (P11) that decide FAILED/BLOCKED/COMPLETED for this
repository's own pipeline, invoked by AGT-09 CI steps and by other agents' pre-flight checks.
ADR-0043 already established the precedent that AGT-09 owns a test root for tooling it owns and
runs, on the reasoning that deployment acceptance IS DevOps work because it launches the shipped
artifact rather than importing product code as a library. The same reasoning applies one level
up: these scripts are not imported by `pixelart_creator/` and are not exercised by product logic
tests: they are AGT-09's own tooling, they gate AGT-09's own CI job, and AGT-09 is the agent that
already runs `coverage_gate` and `path_portability_check` in CI (SCOPE). Routing this work to
AGT-04 (`tests/logic`, `tests/data`) or AGT-06 (`tests/ui`) would hand a CI-gate test to an agent
that does not own CI and has no standing reason to touch `scripts/`.

## Decision

### 1. `tests/scripts/` is a peer root under `tests/`, owned by AGT-09

Create `tests/scripts/` as a regular package (`__init__.py`), a sibling of `tests/logic`,
`tests/data`, `tests/ui`, `tests/backend` and `tests/deploy`. It holds behavioural tests for the
scripts enumerated in PA-04, one module per script (`test_<script>.py`), following the
`importlib`/subprocess conventions already used by `tests/deploy/test_run_ci_router.py` for
loading a `scripts/*.py` module that has no `scripts/__init__.py` package to import through.

Ownership after this ADR:

| Path | Owner | Remit |
| --- | --- | --- |
| `scripts/*.py` | AGT-09 (already, via SCOPE) | the CI gate scripts themselves |
| `tests/scripts/**` | AGT-09 (GitHub/DevOps) | behavioural contract tests for `scripts/*.py` — CLI entrypoint, documented exit codes, structured JSON output |

### 2. The manifest needs NO change — verified by collection, not by inspection

`pyproject.toml` pins `testpaths = ["tests", "web_viewer/tests"]`. `tests/scripts/` is a
**subdirectory of the existing `"tests"` root**, exactly as `tests/deploy/` was under ADR-0043, so
a bare `pytest` recurses into it with no manifest edit. The main quality-gate test step
(`.github/workflows/ci.yml`, "Tests (pytest, headless, parallel, with coverage XML)") invokes bare
`pytest -n auto -m "..." --cov=pixelart_creator ...` with no explicit path argument, so it collects
`tests/scripts/` automatically once the modules exist. No CI workflow edit is required by this
ADR.

### 3. First tranche: the three highest-blast-radius gates

This ADR authorises the root; it does not by itself close PA-04. The first tranche covers, in
blast-radius order: `coverage_gate.py` (decides whether coverage is acceptable),
`check_layering.py` (the three-layer architecture gate), `check_cycles.py` (the import-cycle
gate). Each test module asserts, for its script:

- a clean fixture input exits **0**;
- a deliberately broken fixture input exits **non-zero with the documented code** (never merely
  "non-zero" — the header's own exit-code mapping is the contract under test, and a mismatch
  between that mapping and the script's observed behaviour is reported as a finding, not silently
  absorbed into a looser assertion);
- the printed stdout is parsed as JSON and asserted on by field, not by substring/prose match;
- fixtures are built under `tmp_path` and passed to the script by its own `--root`/`--xml` flag —
  the real repository tree is never mutated by a test run.

`path_portability_check.py`, `perf_profile.py`, `string_audit_check.py` and `run_ci_locally.py`
remain untested after this ADR. That is a known remainder, not a silent gap: PA-04 is not fully
closed by this change, and the remaining four scripts should be tracked as explicit follow-up work
under this same root rather than assumed closed by this record.

### 4. What `tests/scripts/` may NOT become

This root tests `scripts/*.py` and nothing else. It is not a second home for `pixelart_creator/`
logic or data tests, it does not gain fixtures or helpers meant for `tests/logic`/`tests/data`,
and a test that needs to exercise product behaviour (rather than a gate script's CLI contract)
belongs in its owner's existing root, not here. Mirroring ADR-0043 §5's point about
`check_layering`/`check_cycles`: this root is a test-ownership boundary, not a source-layer one —
`check_layering.py --root pixelart_creator` and `check_layering.py --root .` do not change scope
because of this ADR, and `tests/` itself remains `UNGOVERNED_TOPLEVEL`/exempt via
`is_test_module()`, unaffected by where inside `tests/` a given test happens to sit.

## Consequences

**Positive.**

- The seven previously-untested CI gates now have a legitimate, single-owner home, closing the
  structural gap that let PA-04 arise: no future gate script can be added to `scripts/` without an
  obvious place for its test to live.
- The first tranche proves, with real observed `pytest` runs (not narrative), that
  `coverage_gate.py`, `check_layering.py` and `check_cycles.py` can each still fail their
  documented way — the exact property PA-04 said was unproven.
- The boundary is structural rather than conventional, the same property ADR-0043 established for
  `tests/deploy/`: a reviewer can tell what a test under `tests/scripts/` is for from its
  directory, and the container-suite/product-suite boundary that created the original gap is now
  closed on the product side without asking the container suite to cross it.

**Negative / accepted cost.**

- One more directory in the test tree. Accepted for the same reason ADR-0043 accepted
  `tests/deploy/`: the alternative was leaving CI-gate scripts permanently untestable for lack of a
  legal home.
- PA-04 is only partially closed by this ADR. `path_portability_check.py`, `perf_profile.py`,
  `string_audit_check.py` and `run_ci_locally.py` remain untested; a second tranche is required
  before the finding can be reported fully remediated.

**Obligations created (NOT discharged by this ADR).**

1. A follow-up tranche under `tests/scripts/` for `path_portability_check.py`, `perf_profile.py`,
   `string_audit_check.py` and `run_ci_locally.py`, using the same clean/broken-fixture,
   documented-exit-code, structured-JSON method as the first tranche.
2. `main/docs/module-map.md` (owned by AGT-01) does not yet list `tests/scripts/**` in its test-tree
   ownership table; it should gain the same row shape ADR-0043 obligated for `tests/deploy/**`.
