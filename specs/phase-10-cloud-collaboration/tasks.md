# Tasks — Phase 10: Cloud & Collaboration

| Field | Value |
| --- | --- |
| Feature | `phase-10-cloud-collaboration` |
| Author | Claude (AGT-01, Architecture) via `sdd-tasks` |
| Date | 2026-07-04 |
| Over | `plan.md` — **slice-by-slice A → B → C**, each an independently gate-green, CI-green shippable increment. Slice A (port + fake adapter + `.pixproj` round-trip + version history + autosave/recovery) → Slice B (shared projects + comments + presence + hybrid convergence) → Slice C (real-time + branching + the sync backend). |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII). **NO implementation begins until C1 is green — this gate is the blocker.** Each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table: AGT-03 logic/data + backend code,
AGT-04 logic/data/backend tests, AGT-05 UI code, AGT-06 UI/a11y/QA tests, AGT-07 string audit/i18n,
AGT-10 perf (Slice C), AGT-08 docs, AGT-09 pyproject/CI/commits, AGT-01 architecture/analyze/gate. One
owner per task; deterministic sub-steps name their script. Every REQ maps to ≥1 impl + ≥1 test/verify task.
Per-slice flow: **AGT-03 logic/data + AGT-04 tests → AGT-05 ui + AGT-10 perf [C] + AGT-06 QA + AGT-07 i18n
→ AGT-08 docs → AGT-01 final gate → AGT-09 commit.**

---

## Slice A — cloud port + fake adapter + `.pixproj` round-trip + version history + autosave/recovery

### 10A-logic — sync-state / autosave / version-history pure models (`logic/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10A-01 | Add the Slice-A numerics (`AUTOSAVE_INTERVAL_MS=120000`, `MAX_CLOUD_VERSIONS=100`, `MAX_CLOUD_PROJECT_BYTES=268435456`, `CLOUD_RETRY_LIMIT=3`) with citations. **Names DISTINCT from every shipped constant (BF-1).** | AGT-03 | `logic/constants.py` | — | LOGIC-005 / SC-L005-1 / plan §8 | todo |
| T10A-02 | `logic/sync_state.py` (new): `SyncState` (module-local enum), `compute_sync_state(local_marker, versions)` — pure deterministic (no wall-clock/random/locale); `SyncError`. Zero Qt. | AGT-03 | `logic/sync_state.py` | T10A-01 | LOGIC-001 / SC-L001-1 | todo |
| T10A-03 | `logic/autosave.py` (new): `should_autosave(dirty, elapsed_ticks, last_autosave_marker, interval_ms=AUTOSAVE_INTERVAL_MS)` — pure decision fn; elapsed is an INPUT (no clock read inside); `AutosaveError`. Zero Qt. | AGT-03 | `logic/autosave.py` | T10A-01 | LOGIC-002 / SC-L002-1 | todo |
| T10A-04 | `logic/version_history.py` (new): `CloudVersion` + `VersionHistory` (ordered, immutable; `append`→new history; deterministic order; > `MAX_CLOUD_VERSIONS` → `VersionHistoryError`). Zero Qt. | AGT-03 | `logic/version_history.py` | T10A-01 | LOGIC-003, 005 / SC-L003-1 | todo |
| T10A-05 | Unit + property tests (headless): `compute_sync_state` pure/deterministic across all state transitions (twice-same-inputs → identical) [Hypothesis]; `should_autosave` deterministic, elapsed-as-input, no wall-clock; `VersionHistory` ordered/immutable/bounded; bounds from constants (no literals). | AGT-04 | `tests/logic/test_sync_state.py`, `test_autosave_policy.py`, `test_version_history.py`, `test_cloud_bounds.py` | T10A-04 | LOGIC-001, 002, 003, 004, 005 / SC-L001-1, L002-1, L003-1, L004-1, L005-1 | todo |

### 10A-data — the cloud port + fake adapter + auth/keyring (`data/cloud/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10A-06 | `data/cloud/__init__.py` + `data/cloud/port.py` (new): `CloudPort` ABC (put/get/list_versions/latest/delete/put_recovery/get_recovery/capabilities/is_connected); normalized `RemoteItem`/`Cursor`/`CloudCapabilities`; `CloudError` + `CloudDataError(ProjectIOError)`. **No provider type in signatures.** Zero Qt. | AGT-03 | `pixelart_creator/data/cloud/__init__.py`, `port.py` | T10A-04 | DATA-001, 007 / SC-D001-1 | todo |
| T10A-07 | `data/cloud/fake_adapter.py` (new): local-FS/in-memory adapter implementing the WHOLE port; `.pixproj` transported as-is via PIO-1 (no new format); version history + autosave/recovery slot. Zero Qt, no network/creds. | AGT-03 | `data/cloud/fake_adapter.py` | T10A-06 | DATA-002, 003, 004, 005 / SC-D002-1, D003-1, D004-1, D005-1 | todo |
| T10A-08 | `data/cloud/token_store.py` (new): `keyring`-backed set/get/delete keyed `pixelart-creator:cloud:{provider}`; tokens never leave `data/cloud/`. `data/cloud/auth.py` (new): pure PKCE (`S256`) + loopback listener (RFC 8252) + token exchange/refresh + Device Grant (RFC 8628) fallback; only browser-launch delegated to `ui/`. Zero Qt. | AGT-03 | `data/cloud/token_store.py`, `data/cloud/auth.py` | T10A-06 | DATA-008 / SC-D001-1 (isolation clause) | todo |
| T10A-09 | `data/cloud/providers/{drive,onedrive,dropbox}.py` (new): real adapters implementing the SAME port; capability differences via `CloudCapabilities`; **credential-gated / out-of-CI** (`pytest.mark.cloud_live`). Provider SDKs imported ONLY here. Zero Qt. | AGT-03 | `data/cloud/providers/*.py` | T10A-08 | DATA-001, 007, 008 / SC-D001-1, UI-004-1 | todo |
| T10A-10 | Tests (headless, no network/creds): fake-adapter `.pixproj` round-trip → equivalent `Document` (SC-D002-1); every put → new ordered version + `get(version)` reconstructs (SC-D003-1); recovery survives unclean restart + no clobber + defensive restore (SC-D004-1); whole contract via fake adapter (SC-D005-1); untrusted fetch (malformed/oversized/unknown-version → `CloudDataError`/`ProjectIOError`, no eval/exec, ≤ `MAX_CLOUD_PROJECT_BYTES`) (SC-D006-1); PKCE `S256` verifier/challenge pure; keyring isolation (no secret above port / in `.pixproj`/logs). Live-OAuth tests marked `cloud_live` (out-of-CI). | AGT-04 | `tests/data/cloud/test_cloud_port.py`, `test_cloud_roundtrip.py`, `test_cloud_versions.py`, `test_cloud_recovery.py`, `test_fake_adapter.py`, `test_cloud_untrusted.py`, `test_cloud_keyring.py` | T10A-09 | DATA-001..008 / SC-D001-1..006-1 | todo |
| T10A-11 | Run `check_layering --root pixelart_creator` (+ `--root .`) and `check_cycles --root pixelart_creator`: confirm `data/cloud/` Qt-free, no provider leak above the port, `sync_state`/`autosave`/`version_history` pure leaves over `constants`, no `logic → data`, no cycle. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T10A-09 | DATA-007 / Article I / plan §11 / SC-D001-1 | todo |

### 10A-ui — cloud save/load, version browser, recovery prompt, provider connect (`ui/`, Qt only)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10A-12 | `ui/cloud_worker.py` (new): off-GUI-thread runner for cloud put/get/list/autosave (Phase-7/8 worker precedent) so the UI never freezes. `ui/cloud_actions.py` (new): save-to-cloud / open-from-cloud (defensive open) + provider connect/disconnect (provider-agnostic; drives the port). `tr()` + `changeEvent`. | AGT-05 | `ui/cloud_worker.py`, `ui/cloud_actions.py`, `ui/main_window.py` | T10A-09 | UI-001, 004, 005 / SC-UI-001-1, 004-1, 005-1 | todo |
| T10A-13 | `ui/version_history_browser.py` (new): `Version_History_Browser` — list ordered versions, preview, restore (reconstructs that version's `Document` via PIO-1; current unsaved state protected). `tr()` + `changeEvent`. | AGT-05 | `ui/version_history_browser.py` | T10A-12 | UI-002 / SC-UI-002-1 | todo |
| T10A-14 | `ui/recovery_prompt.py` (new): `Recovery_Prompt` — on startup, if an unsaved recovery exists, prompt recover/discard without clobbering the last explicit save; autosave driven by `logic.autosave.should_autosave`. `tr()` + `changeEvent`. | AGT-05 | `ui/recovery_prompt.py`, `ui/main_window.py` | T10A-12 | UI-003 / SC-UI-003-1 | todo |
| T10A-15 | pytest-qt tests (both themes, offscreen): save-to/open-from-cloud via port + defensive open + provider-agnostic (fake provider); version browser lists + restores (state protected); recovery prompt recover/discard + no clobber; provider connect provider-agnostic; cloud op does not freeze the UI (off the per-frame loop). | AGT-06 | `tests/ui/test_cloud_save_load.py`, `test_version_browser.py`, `test_recovery_prompt.py`, `test_provider_connect.py`, `test_cloud_responsive.py` | T10A-14 | UI-001..005 / SC-UI-001-1..005-1 | todo |

## Slice B — shared projects + comments + presence + deterministic hybrid convergence

### 10B-logic — hybrid convergence + untrusted-payload validators (`logic/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10B-01 | Add the Slice-B numerics (`MAX_SHARED_MEMBERS=32`, `MAX_COMMENT_BYTES=4096`, `MAX_COMMENTS_PER_PROJECT=1024`, `CRDT_TILE_SIZE_PX=64`) with citations. **Names DISTINCT from every shipped constant (BF-3; `CRDT_TILE_SIZE_PX` ≠ `TILE_SIZE`).** | AGT-03 | `logic/constants.py` | Slice A done | LOGIC-005 (posture) / plan §8 | todo |
| T10B-02 | `logic/cloud_validation.py` (new): pure `validate_crdt_update`/`validate_comment`/`validate_membership`/`validate_presence` + CRDT message vocabulary — schema + strict size/depth/dimension/byte caps (`MAX_*`); **never `eval`/`exec`**; malformed/oversized → `CloudValidationError`. Importable by `data/cloud/` AND `sync_backend/`. Zero Qt. | AGT-03 | `logic/cloud_validation.py` | T10B-01 | DATA-009 (defence), BACKEND-002 (shared) | todo |
| T10B-03 | `logic/convergence.py` (new): HYBRID model — `pycrdt` tree/sequence CRDT wiring for structured metadata (layer tree/frames/tilemap) + pure NumPy per-tile/region **LWW-Register** (`CRDT_TILE_SIZE_PX`) for raster; logical-clock + site-id tiebreak; `converge(base, ops, site_id)` deterministic (no wall-clock/random/locale); reconciles HIS-1 over DOC-1; `ConvergenceError`. Zero Qt. | AGT-03 | `logic/convergence.py` | T10B-01 | LOGIC-006 / SC-L006-1 | todo |
| T10B-04 | Unit + property tests (headless): permuted operation orders → **byte-identical converged `Document`** (tree-CRDT commutativity + same-tile LWW by logical-clock+site-id, different-tile both survive) [Hypothesis]; determinism (no time/random/locale); 8K-scalable (no per-pixel CRDT metadata); validators reject malformed/oversized (no eval/exec) at every cap. | AGT-04 | `tests/logic/test_hybrid_convergence.py`, `tests/logic/test_cloud_validation.py` | T10B-03 | LOGIC-006, DATA-009 / SC-L006-1, SC-D009-1 | todo |

### 10B-data — shared-project storage + membership (`data/cloud/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10B-05 | `data/cloud/shared_adapter.py` (new): shared-project storage + membership behind the SAME port family (bounded members; comment/presence-metadata storage); fake adapter implements it (CI). Payloads validated via `logic/cloud_validation` (bounded by `MAX_SHARED_MEMBERS`/`MAX_COMMENTS_PER_PROJECT`/`MAX_COMMENT_BYTES`; no eval/exec). No provider leak. Zero Qt. | AGT-03 | `data/cloud/shared_adapter.py`, `data/cloud/fake_adapter.py` | T10B-02 | DATA-009 / SC-D009-1 | todo |
| T10B-06 | Tests (headless, no network/creds): share with bounded members; store/fetch membership + comment + presence payloads; caps enforced; malformed/oversized → defensive error (no eval/exec); no provider detail in `logic/`/`ui/` (`check_layering` passes). | AGT-04 | `tests/data/cloud/test_shared_project.py` | T10B-05 | DATA-009 / SC-D009-1 | todo |

### 10B-ui — shared projects / comments / presence (`ui/`, Qt only)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10B-07 | `ui/shared_projects_panel.py` (new): `Shared_Projects_Panel` — share/invite/see members via the port's provider-agnostic membership surface (no provider named); errors surfaced. `tr()` + `changeEvent`. | AGT-05 | `ui/shared_projects_panel.py` | T10B-05 | UI-009 / SC-UI-009-1 | todo |
| T10B-08 | `ui/comments_panel.py` (new): `Comments_Panel` — add/view/thread/resolve comments; text is a translatable, validated payload (bounded by `MAX_COMMENT_BYTES`, no eval/exec). `tr()` + `changeEvent`. | AGT-05 | `ui/comments_panel.py` | T10B-05 | UI-010 / SC-UI-010-1 | todo |
| T10B-09 | `ui/presence_panel.py` (new): `Presence_Panel` — show who else is present from the ephemeral presence channel (not persisted into the `.pixproj`). `tr()` + `changeEvent`. | AGT-05 | `ui/presence_panel.py` | T10B-05 | UI-011 / SC-UI-011-1 | todo |
| T10B-10 | pytest-qt tests (both themes, offscreen): share + see members (provider-agnostic); add/thread/resolve a validated comment; presence surface shows present members from the ephemeral channel (not persisted). | AGT-06 | `tests/ui/test_shared_projects.py`, `test_comments.py`, `test_presence.py` | T10B-09 | UI-009, 010, 011 / SC-UI-009-1..011-1 | todo |

## Slice C — real-time + branching + the sync backend

### 10C-logic — real-time apply layer + git-like branching (`logic/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10C-01 | Add the Slice-C numeric (`MAX_CRDT_UPDATE_BYTES=1048576`) with citation (shared by client transport + backend caps). **Name DISTINCT from every shipped constant (BF-3).** | AGT-03 | `logic/constants.py` | Slice B done | LOGIC-005 (posture) / plan §8 | todo |
| T10C-02 | `logic/realtime_apply.py` (new): `apply_remote(document, update, site_id)` — validate (`cloud_validation`) then converge (`convergence`); `branch`/`merge` — git-like (fork pycrdt doc + tile-LWW clone → conflict-free CRDT merge; history reconstructable). `RealtimeError`. Zero Qt. **Per-frame flagged for AGT-10 (FLAG-PERFRAME).** | AGT-03 | `logic/realtime_apply.py` | T10C-01 | LOGIC-007 / SC-L007-1, L007-2 | todo |
| T10C-03 | Unit + property tests (headless, in-memory transport): remote-update stream applies + converges per the hybrid model; a cloned branch edited concurrently merges back conflict-free with reconstructable history; determinism; inbound update bounded by `MAX_CRDT_UPDATE_BYTES`. | AGT-04 | `tests/logic/test_realtime_apply.py`, `test_branching.py` | T10C-02 | LOGIC-007 / SC-L007-1, L007-2 | todo |

### 10C-data — client real-time transport port (`data/cloud/`, zero Qt)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10C-04 | `data/cloud/transport.py` (new): `TransportPort` (send_update/send_presence/poll); inbound blobs validated via `logic/cloud_validation`. `data/cloud/loopback_transport.py` (new): in-memory/loopback impl for CI (no network/creds). `data/cloud/ws_transport.py` (new): real WebSocket impl (`websockets`), credential/network-gated, out-of-CI. **No transport type above the port.** Zero Qt. | AGT-03 | `data/cloud/transport.py`, `loopback_transport.py`, `ws_transport.py` | T10C-02 | DATA-010 / SC-D010-1 | todo |
| T10C-05 | Tests (headless, loopback, no network/creds): CRDT updates + presence flow over the loopback transport; inbound blob schema-validated + bounded (`MAX_CRDT_UPDATE_BYTES`, no eval/exec; malformed → error); no transport/provider type leaks above the port (`check_layering` passes; `data/` Qt-free). Real WS test marked `cloud_live` (out-of-CI). | AGT-04 | `tests/data/cloud/test_realtime_transport.py` | T10C-04 | DATA-010 / SC-D010-1 | todo |

### 10C-backend — the NEW first-class sync backend (`sync_backend/`, OUTSIDE the three layers)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10C-06 | `sync_backend/__init__.py` + `sync_backend/server.py` (new): asyncio **WebSocket** relay of CRDT updates + awareness/presence across a shared doc's peers; **spin-up API** (`SyncServer.start/stop`, ephemeral port) for in-process/subprocess CI; reuses pure `logic/{cloud_validation,convergence}`. Imports **NO** `ui`/`data`/Qt. `sync_backend/store.py` (new): per-`document_id` ordered update-log + latest-presence persistence (in-memory CI; file-backed running). | AGT-03 | `sync_backend/__init__.py`, `server.py`, `store.py` | T10C-04 | BACKEND-001, 002 / SC-BK-001-1, BK-002-1 | todo |
| T10C-07 | Backend untrusted-input defence: `server.py` validates **every** ingested payload (CRDT update/presence/comment) via `logic/cloud_validation` caps (`MAX_CRDT_UPDATE_BYTES`/`MAX_COMMENT_BYTES`/`MAX_SHARED_MEMBERS`); malformed/oversized/deeply-nested → rejected (no eval/exec, no crash, no memory exhaustion); backend never receives/stores tokens. | AGT-03 | `sync_backend/server.py` | T10C-06 | BACKEND-002 / SC-BK-002-1 | todo |
| T10C-08 | Integration tests (CI, localhost, no third-party creds): backend spun up in-process/subprocess; **multiple clients over the loopback transport converge to an identical `Document`** (with LOGIC-006/-007); backend relays + persists updates + presence; every payload validated (SC-BK-002-1); no tokens on backend. | AGT-04 | `tests/backend/test_sync_backend_loopback.py`, `test_sync_backend_untrusted.py` | T10C-07 | BACKEND-001, 002 / SC-BK-001-1, BK-002-1 | todo |
| T10C-09 | Run `check_layering --root pixelart_creator` + `--root .` and `check_cycles --root pixelart_creator` + `--root sync_backend`: confirm `sync_backend/` imports no `ui`/`data`/Qt (may reuse pure `logic/`), no client layer imports `sync_backend`, no cycle. Must exit 0 (all four). | AGT-03 | `scripts/*` (invoke) | T10C-06 | BACKEND-001 / Article I / plan §4.4 | todo |

### 10C-ui — art branching + real-time cursors (`ui/`, Qt only)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10C-10 | `ui/branching_panel.py` (new): `Branching_Panel` — branch / view diff / merge back; merge is conflict-free (resolved by `logic.realtime_apply.merge`; no manual conflict UI) and the outcome is surfaced. `tr()` + `changeEvent`. | AGT-05 | `ui/branching_panel.py` | T10C-04 | UI-012 / SC-UI-012-1 | todo |
| T10C-11 | `ui/realtime_cursors_overlay.py` (new): `Realtime_Cursors_Overlay` — render other collaborators' cursors/selection live as **ephemeral** overlays from the presence/awareness channel (never persisted into the `.pixproj`). `tr()`. **Per-frame draw subject to AGT-10 assessment (FLAG-PERFRAME).** | AGT-05 | `ui/realtime_cursors_overlay.py` | T10C-04 | UI-013 / SC-UI-013-1 | todo |
| T10C-12 | pytest-qt tests (both themes, offscreen): branch/diff/merge conflict-free + outcome surfaced; live cursors render as ephemeral overlays + not persisted. | AGT-06 | `tests/ui/test_branching.py`, `test_realtime_cursors.py` | T10C-11 | UI-012, 013 / SC-UI-012-1, 013-1 | todo |

### 10C-perf — real-time re-enters the 16 ms budget (AGT-10 owns strategy; FLAG-PERFRAME / DEP-3)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T10C-13 | Author the render/perf directive (`render-strategy`): assess **real-time remote-patch apply** (REQ-P10-LOGIC-007) + **live-cursor overlay draw** (REQ-P10-UI-013) against the **16 ms `FRAME_BUDGET_MS`** on the 8K (7680×4320) canvas (Article VI RE-ENTERS this slice); direct batching/coalescing of inbound patches + dirty-rect cursor draw. **Budget never relaxed.** Grounded by a `frame-profile` / `perf_profile` measurement. | AGT-10 | perf directive → AGT-05 | T10C-11 | LOGIC-007, UI-013 / SC-L007-2 / DEP-3 | todo |
| T10C-14 | Implement the AGT-10 directive in `realtime_cursors_overlay` + the apply-dispatch path (batching/coalescing, dirty-rect cursor draw); no convergence math added (Article I). | AGT-05 | `ui/realtime_cursors_overlay.py`, `ui/cloud_worker.py` | T10C-13 | UI-013 / SC-UI-013-1 | todo |
| T10C-15 | Profile + verify: `perf_profile` over real-time apply + cursor overlay on the 8K canvas vs `FRAME_BUDGET_MS`; behavioural pytest-qt that apply + cursor draw hold budget (both themes). **CI perf-gate recommendation to AGT-09** for the Slice-C real-time path. | AGT-06 + AGT-10 | `scripts/perf_profile.py` (invoke), `tests/ui/test_realtime_perf.py` | T10C-14 | LOGIC-007, UI-013 / SC-L007-2 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-10 `logic/` models, the `data/cloud/` subpackage, and the new top-level `sync_backend/` component (marked PLANNED per house convention). | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; zero unresolved findings before implement. | AGT-01 | `specs/phase-10-cloud-collaboration/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | Layering-rule update in `scripts/check_layering.py` (new `sync_backend` rule + client→backend forbidden) + governance note in `check_cycles.py`; re-run all invocations → exit 0. | AGT-01 | `scripts/check_layering.py`, `check_cycles.py` | plan | Article I / ADR-0027 §5 | done |
| TG-04 | Manifest: add runtime deps `keyring`, `pycrdt`, `websockets` (pin, prefer well-maintained); add `sync_backend` as a separate package / test-installed target (excluded from the desktop wheel); register the `cloud_live` pytest marker. **AGT-09/AGT-01 decision (PL10-D14; Article VII).** | AGT-09 | `pyproject.toml` | plan | PL10-D14 / Article VII | todo |
| TG-05 | a11y audit (`a11y-audit`) across all Phase-10 controls (cloud save/open, version list + restore, recovery prompt, provider connect/disconnect, shared-projects, comments, presence, branching, real-time cursors): accessible names/descriptions, keyboard reachability + logical tab order, visible focus. | AGT-06 | `tests/ui/*` | T10A-15, T10B-10, T10C-12 | UI-006 / SC-UI-006-1 | todo |
| TG-06 | Both-theme render verification (role-based colours) across all Phase-10 UI (Slice A + B + C). | AGT-06 | `tests/ui/*` | T10A-15, T10B-10, T10C-12 | UI-007 / SC-UI-007-1 | todo |
| TG-07 | String audit (`string_audit_check`): zero unwrapped user-visible strings across all Phase-10 `ui/` (cloud/collab/branching/cursor labels + tooltips, version columns, recovery text, comments, presence, status/errors); `changeEvent` retranslate on hand-built widgets. | AGT-07 | `ui/*.py` | T10C-12 | UI-008 / SC-UI-008-1 | todo |
| TG-08 | CHANGELOG (`Unreleased`) entries for Phase-10 features tied to REQ-IDs, per slice. | AGT-08 | `docs/CHANGELOG.md` | Slice A/B/C impl+test done | Article IX | todo |
| TG-09 | `sdd-checklist` before ship: every REQ has a passing test; fake-adapter round-trip/version/recovery + hybrid-convergence determinism + loopback-backend multi-client convergence green; both themes + a11y + i18n green; the **Slice-C 16 ms real-time budget** green (AGT-10); untrusted-input defence green across cloud/collab/backend; live-provider OAuth verified manually (out-of-CI). | AGT-06 | checklist report | all impl+test done | Article IV/V/VI/VII | todo |
