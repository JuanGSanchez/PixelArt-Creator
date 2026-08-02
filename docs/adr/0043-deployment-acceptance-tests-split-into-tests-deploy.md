# ADR-0043 — Deployment-acceptance tests split out of `tests/backend/` into a peer root `tests/deploy/`

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-31 |
| Author | AGT-01 (Architecture) |
| Feature | Test-tree ownership boundary (follows the `sync_backend/**` ownership split) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0027 (`sync_backend/` placement — the peer-top-level precedent this mirrors one level down, in the test tree), ADR-0038 (`deploy/` native/hosting artifacts), Phase-13 Slice 13C (T13C-04/-05/-06) |

## Context

A new agent now owns `sync_backend/**` and `tests/backend/**`. Its remit is the **service**: the
CRDT relay, awareness/presence routing, the update log/backlog, and the share-token handshake.

`tests/backend/` was not homogeneous with that remit. Of its six modules, three were not service
tests at all — they were **deployment acceptance** for the shipped `deploy/` artifacts:

| Module | What it actually exercises |
| --- | --- |
| `test_vps_localhost.py` | Spawns `deploy/run_sync_backend.py` as a **subprocess**; builds + runs `deploy/Dockerfile` on a real Docker daemon (opt-in, skips when `docker` is absent). |
| `test_nginx_wss_localhost.py` | Parses the shipped `deploy/nginx-sync.conf`; stands up a **real Nginx** self-signed loopback WSS proxy and holds an idle socket past 60 s (opt-in behind `PIXELART_NGINX_IDLE_TEST=1`). |
| `conftest.py` | The launcher-subprocess harness (`_spawn_launcher` / `_await_listening` / `_terminate` / the `launched_backend_uri` fixture) that exists **only** to serve the two modules above. |

None of these modify or even import `sync_backend/` as a library — they *launch the unmodified
backend the way a container, a systemd unit or an Nginx front-end does*. That is DevOps work
(AGT-09), not sync-backend work. Both modules are `@pytest.mark.integration` at module level and
both are environment-gated: they must **skip**, never error, when the environment cannot supply a
subprocess, a Docker daemon, or Nginx.

**The grep that settled it.** The split is cleaner than a file count suggests, and it was decided by
evidence rather than by naming. Searching the whole test tree for every symbol the shared
`conftest.py` exports returns consumers in `test_vps_localhost.py` and
`test_nginx_wss_localhost.py` and **nowhere else**. In particular
`tests/backend/test_hosting_default_unchanged.py` — which sounds deployment-shaped — does *not* use
the fixture; it recomputes its own `_REPO_ROOT` and only asserts that the default hosting behaviour
is unchanged, in-process, with **no** `integration` marker. So the two directories are already
disjoint at the symbol level: nothing that remains in `tests/backend/` loses a fixture, and nothing
that moves leaves a dependency behind. The conftest travels with the two modules because it is
**entirely** their harness.

The USER approved the split. This ADR records the placement ruling, the consequences that had to be
made consistent with it, and — deliberately — the *negative* result about the manifest.

## Decision

### 1. `tests/deploy/` is a peer test root under `tests/`, owned by AGT-09

Create `tests/deploy/` as a **sibling of `tests/backend/`**, a regular package (`__init__.py`), and
move `conftest.py`, `test_vps_localhost.py` and `test_nginx_wss_localhost.py` into it unchanged
apart from docstrings.

`tests/deploy/conftest.py` computes `REPO_ROOT = Path(__file__).resolve().parents[2]`. That
expression is **unchanged by the move** — `tests/deploy/conftest.py` and `tests/backend/conftest.py`
sit at the same depth, so `parents[2]` is still the working-tree root. The two modules' relative
import `from .conftest import …` also survives, because the conftest moved with them into the same
package. No path arithmetic was rewritten, which is the point of choosing a *peer* directory over,
say, `tests/backend/deploy/` (a nested root would have shifted `parents[2]` and silently repointed
`REPO_ROOT` at `tests/`).

Ownership after this ADR:

| Path | Owner | Remit |
| --- | --- | --- |
| `tests/backend/**` | the sync-backend service agent | in-process relay, presence, update log, handshake — no marker, runs in the default gate |
| `tests/deploy/**` | AGT-09 (GitHub/DevOps) | `deploy/` artifacts: launcher subprocess, Dockerfile, Nginx WSS — all `integration`-marked, all environment-gated |

### 2. The manifest needs NO change — and that is a ruling, not an omission

`pyproject.toml` pins `testpaths = ["tests", "web_viewer/tests"]`. `tests/deploy/` is a
**subdirectory of the existing `"tests"` root**, so a bare `pytest` recurses into it with no
manifest edit. This was **verified by collection, not by inspection** (the distinction matters: the
same reasoning applied to a *sibling* of `tests/` would have been wrong — that is exactly why
`web_viewer/tests` had to be named explicitly):

```
before   pytest --collect-only -q            -> 5656 tests
         pytest --collect-only -q tests/backend -> 49 tests
after    pytest --collect-only -q            -> 5656 tests   (unchanged)
         pytest --collect-only -q tests/backend -> 40 tests
         pytest --collect-only -q tests/deploy  ->  9 tests   (40 + 9 = 49)
         bare `pytest --collect-only` emits 9 node IDs under tests/deploy/
```

A clarifying comment is added above `testpaths` recording *why* no entry was needed and warning that
a future **top-level** test root would have to be added there. The setting itself is untouched.

### 3. CI must name `tests/deploy/` — and must keep naming `tests/backend/`

Two CI call sites named `tests/backend` explicitly. Both are corrected:

**(a) The dedicated `integration` job** ran `pytest -m integration tests/backend/`. After the move
that path collects **zero** tests. This is not a hypothetical: measured, `pytest -m integration
tests/backend/` now reports `no tests collected (40 deselected)` and **exits 5**
(`NO_TESTS_COLLECTED`). Under GitHub Actions a non-zero exit fails the step, so this particular
instance would have failed *loudly* rather than silently — but the loudness is an accident of there
being no other integration test in that root. The moment one existed, the stale path would have run
that one test, exited 0, and the nine deployment tests would have vanished from CI with a green
check. The job now runs:

```
pytest -m integration tests/deploy/ tests/backend/
```

Both roots are named **on purpose**. `tests/deploy/` holds all nine integration tests today and
`tests/backend/` holds none; naming only the former would re-create the same trap for the *next*
integration test the backend agent adds. Naming both also keeps the step off exit code 5 in either
direction.

**(b) The non-client coverage step** (`--cov=sync_backend --cov=web_viewer`) ran over
`tests/backend web_viewer/tests` with `-m "…and not integration"`. It now runs over
`tests/backend tests/deploy web_viewer/tests`. Today this changes nothing measurable — every
`tests/deploy` test is `integration`-marked and therefore deselected there, and the step's
collection is `106/115` both before and after — but it means a future *unmarked* deploy test is
graded by the same 90/80 gate as everything else instead of being invisible to it.

The `-m "…not integration"` deselection in the cross-OS quality-gate matrix needs no path change at
all: it invokes bare `pytest`, which picks `tests/deploy/` up via `testpaths` and then deselects it
by marker.

### 4. The tests must still skip, not error

Re-verified after the move against the exact CI command:

```
pytest -m integration tests/deploy/ tests/backend/ -q -rs
  ->  7 passed, 2 skipped, 40 deselected

SKIPPED tests/deploy/test_nginx_wss_localhost.py:199
        opt-in slow test; set PIXELART_NGINX_IDLE_TEST=1 to run it
SKIPPED tests/deploy/test_vps_localhost.py:205
        docker not on PATH; containerized acceptance is opt-in (integration)
```

Both opt-in gates still skip with their original reasons; nothing errored; the seven
environment-independent tests (launcher-subprocess convergence, late-join backlog replay, the Nginx
config assertions, short idle-survival) still **run and pass**. `tests/backend/` on its own is
`40 passed` — losing the conftest cost it nothing, confirming the disjointness claim above.

### 5. Structural checks

Placement is proven by the deterministic scripts, not by reading:

```json
check_layering --json  { "scanned": 194, "violations": [], "unregistered": [], "exempt": {} }   exit 0
check_cycles   --json  { "modules": 196, "edges": 681, "cycles": [] }                            exit 0
scripts/path_portability_check.py -> clean (474 files)                                           exit 0
```

Neither script's scope changes: both govern `pixelart_creator/` plus the registered peer top-level
packages, and the test tree is not a layered package. The move therefore cannot create a layering
violation — it is a *test-ownership* boundary, not a source-layer one — and the clean runs record
that the tree is unperturbed.

## Consequences

**Positive.**

- The ownership boundary is now structural rather than conventional. An agent that owns
  `tests/backend/**` can no longer inherit Docker/Nginx acceptance work by accident, and a reviewer
  can tell what a test is for from its directory.
- The deployment harness has a home. `deploy/` artifacts (launcher, Dockerfile, `nginx-sync.conf`)
  now have exactly one test root, so the next one (a systemd unit test, a reverse-proxy variant, a
  packaging smoke test) has an obvious destination instead of accreting into a backend directory.
- CI names both roots, so the failure mode that let coverage debt hide — a test that stops being
  invoked while the check stays green — is closed at both call sites rather than moved.

**Negative / accepted cost.**

- One more directory in the test tree, and a second place to look for "backend-ish" tests. Accepted:
  the two sets have disjoint owners, disjoint markers and disjoint environmental requirements, so
  the cost of the extra directory is lower than the cost of an agent inheriting the wrong remit.
- `tests/deploy/` currently contains **no** default-gate test, so a full `tests/deploy` run in an
  environment without Docker/Nginx proves less than its file count suggests. That is a property of
  deployment acceptance, not of the split, and it was already true inside `tests/backend/`.

**Obligations created (NOT discharged by this ADR — outside this change's declared write surface).**

1. `main/docs/module-map.md` still routes `tests/backend/**` to AGT-04 in one row and names
   `tests/backend/test_{vps_localhost,nginx_wss_localhost,…}` in another. Both must be updated to
   the new ownership (`tests/backend/**` -> the sync-backend service agent; `tests/deploy/**` ->
   AGT-09). AGT-01 owns this file and will amend it in the pass that is allowed to touch it.
2. The Phase-12 and Phase-13 traceability matrices and `phase-13-cross-platform/tasks.md`
   (T13C-04) cite the old `tests/backend/test_vps_localhost.py` /
   `test_nginx_wss_localhost.py` paths. AGT-02 owns the specification tree; these citations need a
   path refresh. **The tests they point at are unchanged in content** — only the directory moved.
3. `tests/ui/test_opacity_drag.py` documents its double-gate convention by pointing at the two moved
   modules' old paths (three docstring references). Comment-only; AGT-06 to refresh.

**Finding surfaced while doing this (recorded, not acted on).** CI lints and format-checks
`pixelart_creator scripts` only — `flake8`/`black`/`isort` never run over `tests/`. Running flake8
over `tests/backend` locally reports four pre-existing `E501` violations in
`test_sync_backend.py` (lines 7, 390, 392, 407) that CI has never seen. `tests/deploy/` is clean
under all three tools. Widening the lint scope is AGT-09's call and is not made here.
