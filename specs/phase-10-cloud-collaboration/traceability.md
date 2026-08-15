# Traceability Matrix — Phase 10: `phase-10-cloud-collaboration`

REQ-ID ↔ dossier `S-id` / principle / article / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) ↔ test id(s).

**Mode:** FORWARD / PRE-IMPLEMENTATION — **COMPLETE** (authored at `specify`+`clarify`, §10.2
ADJUDICATED, AGT-02, 2026-07-04). **All three slices are fully drafted** — **34 REQs**:
`REQ-P10-DATA-001..010` (10) + `REQ-P10-LOGIC-001..007` (7) + `REQ-P10-UI-001..013` (13) +
`REQ-P10-BACKEND-001..002` (2). Every REQ has **≥1 acceptance scenario in `spec.md §11`**; tests are
**`pending`** (authored later by AGT-04 — data/logic/backend, headless via the local/fake adapter +
localhost/loopback backend — and AGT-06 — UI, both themes — after `sdd-plan`/`sdd-tasks`). **No
`PENDING (blocked)` / `uncovered` rows remain** — the 5 §10.2 clarifications (CL-B1..CL-B5) are resolved.

Status legend:
- **spec'd (forward)** — has ≥1 Gherkin acceptance scenario in `spec.md §11`; test `pending`.

## DATA requirements — `data/cloud/` (cloud port + local/fake adapter)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P10-DATA-001 | S7 (optional cloud-sync layer), S11, Article I, Phase-10 cap | §2, §4, §11 | SC-D001-1 | `test_cloud_port.py::test_serialize_composes_pio1_not_a_new_format`, `::test_round_trip_reconstructs_equivalent_document`, `::test_indexed_document_round_trip`, `::test_remote_item_and_cursor_are_frozen`, `::test_cloud_data_error_is_projectioerror_subclass`, `::test_cloud_error_is_valueerror_subclass`, `::test_property_round_trip_identity_and_determinism` + provider-agnostic contract legs `test_cloud_providers_contract.py`, `test_cloud_providers_base.py` — *(AGT-02 PA-08 fix: this cell previously named `tests/data/cloud/test_cloud_port.py`, a path that does not exist; the file is `tests/data/test_cloud_port.py`, no `cloud/` subdirectory)* | spec'd (forward) |
| REQ-P10-DATA-002 | **PIO-1**, **DOC-1**, S7, Article VII | §4, §11 | SC-D002-1 | `tests/data/cloud/test_cloud_roundtrip.py` (`.pixproj` round-trips; reconstructs equivalent Document; no new format) | spec'd (forward) |
| REQ-P10-DATA-003 | S7, P2, Phase-10 cap (version history) | §4, §11 | SC-D003-1 | `tests/data/cloud/test_cloud_versions.py` (each put → new ordered version; get(version) reconstructs) | spec'd (forward) |
| REQ-P10-DATA-004 | S7, Phase-10 cap (autosave/recovery) | §4, §11 | SC-D004-1 | `tests/data/cloud/test_cloud_recovery.py` (recovery survives unclean restart; no clobber; defensive restore) | spec'd (forward) |
| REQ-P10-DATA-005 | S13, Article IV, S11, Phase-10 cap (adapters swappable) | §2, §4, §11 | SC-D005-1 | `test_cloud_fake_adapter.py::test_put_get_round_trip`, `::test_put_appends_ordered_versions_with_envelope`, `::test_list_versions_unknown_project_is_empty`, `::test_delete_removes_project`, `::test_stale_parent_version_conflicts`, `::test_capabilities_full_featured`, `::test_is_connected_reflects_flag`, `::test_recovery_slot_round_trip_in_memory`, `::test_versions_survive_restart_ordered`, `::test_in_memory_mode_does_not_persist` (whole port contract, no network/credentials, headless) — *(AGT-02 PA-08 fix: this cell previously named `tests/data/cloud/test_fake_adapter.py`, a path that does not exist; the file is `tests/data/test_cloud_fake_adapter.py`)* | spec'd (forward) |
| REQ-P10-DATA-006 | **PIO-1**, Article VII, S7 | §4, §11 | SC-D006-1 | `tests/data/cloud/test_cloud_untrusted.py` (malformed/oversized/unknown-version → error; no eval/exec; bounded) | spec'd (forward) |
| REQ-P10-DATA-007 | Article I, S11 | §4, §11 | SC-D001-1 | `tests/data/cloud/test_cloud_port.py` + `check_layering`/`check_cycles` exit 0 (no provider leak; data/cloud Qt-free) | spec'd (forward) |
| REQ-P10-DATA-008 *(OS keyring — CL-B3)* | Article VII (no secrets), S11, Article I | §4, §11 | SC-D001-1 (isolation clause) | `tests/data/cloud/test_cloud_port.py` + `test_cloud_keyring.py` (tokens acquired/stored/used only in adapter via OS keyring; no secrets above port / in `.pixproj`/logs) | spec'd (forward) |
| REQ-P10-DATA-009 (Slice B) | S7, Article I, Article VII, Phase-10 cap (shared projects), CL-B1/CL-B5 | §2, §4b, §11 | SC-D009-1 | `tests/data/cloud/test_shared_project.py` (shared storage + membership; validated comment/presence payloads; bounded; no provider leak; headless no-network) | spec'd (forward) |
| REQ-P10-DATA-010 (Slice C) | S7, S11, Article I, Article VII, CL-B4, Researcher §4.5 | §2, §4c, §11 | SC-D010-1 | `tests/data/cloud/test_realtime_transport.py` (client transport port; loopback CRDT+presence exchange; update blobs validated/bounded; no transport leak; data/ Qt-free) | spec'd (forward) |

## LOGIC requirements — sync-state / version / autosave-policy pure models

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P10-LOGIC-001 | P2 (determinism), S11, Article I | §4, §11 | SC-L001-1 | `tests/logic/test_sync_state.py` (pure deterministic local-vs-remote state) | spec'd (forward) |
| REQ-P10-LOGIC-002 | P2, S12, Phase-10 cap (autosave) | §4, §11 | SC-L002-1 | `tests/logic/test_autosave_policy.py` (pure decision fn; elapsed as input, no wall-clock) | spec'd (forward) |
| REQ-P10-LOGIC-003 | P2, S11, Phase-10 cap (version history) | §4, §11 | SC-L003-1 | `tests/logic/test_version_history.py` (ordered, immutable, deterministic, bounded) | spec'd (forward) |
| REQ-P10-LOGIC-004 | Article VI, S1, S12 (NFR) | §4, §5, §11 | SC-L004-1 | `test_cloud_jobs.py::test_worker_success_emits_succeeded_then_done`, `::test_worker_cancel_before_run_skips_job_but_still_done`, `::test_worker_error_emits_failed_then_done`, `::test_controller_stale_token_emission_is_dropped`, `::test_controller_submit_after_shutdown_is_noop` + `test_cloud_teardown.py::test_main_window_shutdown_drains_cloud_controller`, `::test_cloud_dialogs_own_no_worker_thread`, `::test_shutdown_after_failed_op_still_clears_busy` (cloud work runs on a controller-owned pool off the GUI thread and always reaches a terminal `done`) — *(AGT-02 PA-08 fix: this cell previously named `tests/logic/test_sync_offloop.py`, which **does not exist and never did** — no renamed counterpart; the off-loop posture is actually evidenced by the UI job/teardown suites named here)* | spec'd (forward) |
| REQ-P10-LOGIC-005 | Article II, Article VII, S12 | §4, §11 | SC-L005-1 | `test_cloud_validation.py::test_crdt_update_at_cap_boundary_is_accepted`, `::test_crdt_update_one_over_cap_is_rejected`, `::test_comment_text_at_byte_cap_is_accepted`, `::test_comment_text_one_byte_over_cap_is_rejected`, `::test_membership_at_member_cap_accepted`, `::test_membership_one_over_cap_rejected` + `test_cloud_fake_adapter.py::test_put_at_size_cap_ok_over_raises`, `::test_version_cap_over_limit_raises`, `::test_put_recovery_over_cap_raises` + `test_cloud_port.py::test_size_cap_fires_before_decode`, `::test_size_cap_boundary_allows_exact_limit` — *(AGT-02 PA-08 fix: this cell previously named `tests/logic/test_cloud_bounds.py`, which **does not exist and never did**; the bounds are enforced and tested in `tests/logic/test_cloud_validation.py` and the adapter/port suites named here)* | spec'd (forward) |
| REQ-P10-LOGIC-006 (Slice B) | **HIS-1**, **DOC-1**, P2, S11, Article I, Article VI (batch), CL-B5, Researcher §4.2/§4.4 | §4b, §11 | SC-L006-1 | `tests/logic/test_hybrid_convergence.py` (tree-CRDT commutativity + tile/region-LWW; logical-clock+site-id; permuted-order → byte-identical Document; 8K-scalable) | spec'd (forward) |
| REQ-P10-LOGIC-007 (Slice C — **per-frame flag**) | **HIS-1**, **DOC-1**, P2, S11, Article I, **Article VI (per-frame — AGT-10)**, CL-B5, Researcher §4.3/§4.6 | §4c, §11 | SC-L007-1, SC-L007-2 | `tests/logic/test_realtime_apply.py` + `test_branching.py` (remote-patch apply converges; branch clone→merge conflict-free); **AGT-10 FLAG-PERFRAME** (16 ms budget) | spec'd (forward) |

## UI requirements — cloud save/load / version browser / recovery / connect

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P10-UI-001 | REQ-P10-DATA-001, -002, S7 | §4, §11 | SC-UI-001-1 | `tests/ui/test_cloud_save_load.py` (save to / open from cloud via port; defensive open; provider-agnostic) | spec'd (forward) |
| REQ-P10-UI-002 | REQ-P10-DATA-003, REQ-P10-LOGIC-003 | §4, §11 | SC-UI-002-1 | `tests/ui/test_version_browser.py` (list + restore prior version; current state protected) | spec'd (forward) |
| REQ-P10-UI-003 | REQ-P10-DATA-004, REQ-P10-LOGIC-002 | §4, §11 | SC-UI-003-1 | `tests/ui/test_recovery_prompt.py` (prompt recover/discard on restart; no clobber) | spec'd (forward) |
| REQ-P10-UI-004 *(live flow credential-gated CL-B2/CL-B3)* | REQ-P10-DATA-001, -007, -008 | §4, §11 | SC-UI-004-1 | `tests/ui/test_provider_connect.py` (provider-agnostic entry point via fake provider) — **live-OAuth flow credential-gated / out-of-CI (CL-B2)** | spec'd (forward) |
| REQ-P10-UI-005 (NFR) | REQ-P10-LOGIC-004, S7, Article VI | §4, §5, §11 | SC-UI-005-1 | `tests/ui/test_cloud_responsive.py` (no UI freeze during cloud op); AGT-01/AGT-10 worker-thread HOW | spec'd (forward) |
| REQ-P10-UI-006 (NFR) | Article V §1 | §4, §5, §11 | SC-UI-006-1 | `tests/ui/test_cloud_a11y.py` (accessible names / keyboard / focus); AGT-06 `a11y-audit` | spec'd (forward) |
| REQ-P10-UI-007 (NFR) | Article V §3 | §4, §5, §11 | SC-UI-007-1 (+ every UI scenario in both themes) | both-theme `[light]`/`[dark]` fixtures across `tests/ui/test_cloud_*` | spec'd (forward) |
| REQ-P10-UI-008 (NFR) | Article V §2, F6 | §4, §5, §11 | SC-UI-008-1 | tr()-wrapped cloud+collab UI + `changeEvent` retranslate; AGT-07 `string_audit_check` | spec'd (forward) |
| REQ-P10-UI-009 (Slice B) | REQ-P10-DATA-009, S7, Article V | §4b, §11 | SC-UI-009-1 | `tests/ui/test_shared_projects.py` (share/invite/see members; provider-agnostic; both themes) | spec'd (forward) |
| REQ-P10-UI-010 (Slice B) | REQ-P10-DATA-009, Article V, Article VII | §4b, §11 | SC-UI-010-1 | `tests/ui/test_comments.py` (add/thread/resolve validated comments; bounded; both themes) | spec'd (forward) |
| REQ-P10-UI-011 (Slice B) | REQ-P10-DATA-010, Article V | §4b, §11 | SC-UI-011-1 | `tests/ui/test_presence.py` (present members from ephemeral channel; not persisted; both themes) | spec'd (forward) |
| REQ-P10-UI-012 (Slice C) | REQ-P10-LOGIC-007, S7, Article V, Researcher §4.6 | §4c, §11 | SC-UI-012-1 | `tests/ui/test_branching.py` (branch/diff/merge conflict-free; outcome surfaced; both themes) | spec'd (forward) |
| REQ-P10-UI-013 (Slice C — **per-frame flag**) | REQ-P10-DATA-010, REQ-P10-LOGIC-007, Article V, Article VI, Researcher §4.5 | §4c, §11 | SC-UI-013-1 | `tests/ui/test_realtime_cursors.py` (live ephemeral cursor overlays; not persisted); **AGT-10 per-frame draw assessment** | spec'd (forward) |

## BACKEND requirements — the NEW first-class sync backend (OUTSIDE the three layers)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P10-BACKEND-001 | S7, Article IV, Article XI, CL-B4, Researcher §4.5/§6 | §2, §4c, §11 | SC-BK-001-1 | `tests/backend/test_sync_backend_loopback.py` (in-process/subprocess backend; multi-client loopback convergence; in CI, no third-party creds); **placement + ADR = AGT-01 (FLAG-BACKEND)** | spec'd (forward) |
| REQ-P10-BACKEND-002 | Article VII, Article II, S13, CL-B4, Researcher §5 | §4c, §11 | SC-BK-002-1 | `tests/backend/test_sync_backend_untrusted.py` (schema-validate every payload; size/depth/dimension/byte caps; no eval/exec/crash; no tokens on backend) | spec'd (forward) |

## Coverage summary

- **34 of 34 REQ-IDs** across Slices A + B + C + backend (10 DATA + 7 LOGIC + 13 UI + 2 BACKEND) have
  **≥1 acceptance scenario** in `spec.md §11` (**0 uncovered, 0 blocked**); tests **`pending`** (forward).
  New expected Slice-B/C/backend test modules:
  `tests/data/cloud/{test_shared_project,test_realtime_transport,test_cloud_keyring}.py`,
  `tests/logic/{test_hybrid_convergence,test_realtime_apply,test_branching}.py`,
  `tests/ui/{test_shared_projects,test_comments,test_presence,test_branching,test_realtime_cursors}.py`,
  and `tests/backend/{test_sync_backend_loopback,test_sync_backend_untrusted}.py`.
- **28 Gherkin scenarios total:** 17 Slice-A (SC-D001-1..D006-1, SC-L001-1..L005-1, SC-UI-001-1..UI-008-1)
  + 5 Slice-B (SC-D009-1, SC-L006-1, SC-UI-009-1..011-1) + 6 Slice-C (SC-D010-1, SC-L007-1, SC-L007-2,
  SC-UI-012-1, SC-UI-013-1, SC-BK-001-1, SC-BK-002-1).
- **No `PENDING (blocked)` / `uncovered` rows remain** — CL-B1..CL-B5 are ADJUDICATED (spec §10.2).
  `sdd-analyze` should find **34 REQs, 34 with scenarios, 0 uncovered, 0 blocked**.
- SDD order: specify+clarify (this, **§10.2 ADJUDICATED → COMPLETE**) → plan (**two ADRs expected**: the
  cloud-port design DEP-2, and the sync-backend placement FLAG-BACKEND) → tasks → analyze → implement →
  test → checklist.
- The NFRs: REQ-P10-UI-008 (i18n) `string_audit_check` at ship; REQ-P10-UI-006 (a11y) `a11y-audit`;
  REQ-P10-UI-007 (both themes) both-theme pytest-qt; **Article VI split** —
  REQ-P10-LOGIC-004/-006 + REQ-P10-UI-005 are **batch/off-loop** (verified behaviourally, no-freeze),
  whereas **REQ-P10-LOGIC-007 + REQ-P10-UI-013 RE-ENTER the 16 ms per-frame budget** and carry the
  **AGT-10 FLAG-PERFRAME** assessment.

## Forward-inherited primitive traces (Article X §2 — explicit)

| Inherited primitive | Origin | Phase-10 forward trace |
| --- | --- | --- |
| **PIO-1** — `data/project_io.py` defensive `.pixproj` serialiser (`ProjectIOError`, `_SUPPORTED_VERSIONS`, zlib+base64, `pathlib`, no `eval`) | `data/project_io.py` (Phase 1/4/6, shipped) | → REQ-P10-DATA-002 (`.pixproj` is the atomic sync unit; cloud adds no format) → REQ-P10-DATA-006 (cloud-fetched `.pixproj` validated via this defensive path; untrusted-input defence) |
| **DOC-1** — the `Document` tree | `logic/document.py` (Phase 1, shipped) | → REQ-P10-DATA-002 (the subject that round-trips through the cloud) → REQ-P10-DATA-003 (a fetched version reconstructs the Document it held) |
| **HIS-1** — `logic/history.py` reversible-command path | `logic/history.py` (Phase 1, shipped) | → REQ-P10-LOGIC-006 (the hybrid convergence model reconciles the command stream — tree-CRDT + tile/region-LWW) → REQ-P10-LOGIC-007 (the real-time apply layer applies remote CRDT/OT ops + branch merge over the same edit path) |

## Cross-layer trace (UI binds to new data/logic)

| UI REQ | Binds to data/logic REQ / shipped | Note |
| --- | --- | --- |
| REQ-P10-UI-001 | REQ-P10-DATA-001/-002 | save/open through the port; defensive open (PIO-1) |
| REQ-P10-UI-002 | REQ-P10-DATA-003, REQ-P10-LOGIC-003 | version browser over the ordered history |
| REQ-P10-UI-003 | REQ-P10-DATA-004, REQ-P10-LOGIC-002 | recovery prompt driven by autosave policy |
| REQ-P10-UI-004 | REQ-P10-DATA-001/-007/-008 | provider-agnostic connect (live flow credential-gated CL-B2/-B3) |
| REQ-P10-UI-005 | REQ-P10-LOGIC-004 | cloud ops off the per-frame loop; stays responsive |
| REQ-P10-UI-009 | REQ-P10-DATA-009 | shared-projects panel over membership storage |
| REQ-P10-UI-010 | REQ-P10-DATA-009 | comments over validated payload storage |
| REQ-P10-UI-011 | REQ-P10-DATA-010 | presence over the ephemeral transport channel |
| REQ-P10-UI-012 | REQ-P10-LOGIC-007 | branching UI over the real-time apply/branch layer |
| REQ-P10-UI-013 | REQ-P10-DATA-010 + REQ-P10-LOGIC-007 | live cursors over transport; per-frame draw (AGT-10) |
| REQ-P10-BACKEND-001/-002 | REQ-P10-DATA-010, REQ-P10-LOGIC-006/-007 | backend relays/persists/validates; client reaches it via the transport port; OUTSIDE the 3 layers (AGT-01 places + ADR) |

## Dependency / gap list (for AGT-01 `sdd-plan` / `sdd-analyze`)

- **ADJUDICATED — §10.2 (no longer blocking).** CL-B1 = FULL scope (A+B+C); CL-B2 = port + fake adapter
  in CI, real providers credential-gated/out-of-CI; CL-B3 = OS keyring in `data/cloud/`; CL-B4 =
  real-time sync BACKEND in scope as a separate top-level component (localhost-CI-testable); CL-B5 =
  HYBRID convergence (tree-CRDT + tile/region-LWW). **`sdd-plan` may proceed for all three slices.**
- **FLAG-BACKEND (AGT-01 — REQUIRED).** The sync backend (REQ-P10-BACKEND-001/-002) is a NEW first-class
  component **OUTSIDE the three layers**; AGT-01 owns its placement + a REQUIRED ADR (repo location,
  framework/hosting, in-process/subprocess spin-up for CI, client↔backend protocol). The client reaches
  it only via the zero-Qt `data/cloud/` transport port (REQ-P10-DATA-010) — three-layer purity intact.
- **FLAG-PERFRAME (AGT-10 — REQUIRED, Slice C).** REQ-P10-LOGIC-007 real-time remote-patch apply +
  REQ-P10-UI-013 live-cursor draw RE-ENTER the 16 ms `FRAME_BUDGET_MS`; AGT-10 must assess and direct
  batching/coalescing/dirty-rect strategy. (Slice A/B stay batch/off-loop.)
- **DEP-1 (Researcher — COMPLETE:** `docs/subagent-report-the-researcher-a80a5c6a-20260704T102747.md`**).**
  Provider-port shape over Drive/OneDrive/Dropbox (opaque-cursor change tracking), OAuth
  PKCE-over-loopback (RFC 8252/7636) + Device Grant + **keyring** token storage, atomic-write + sidecar
  autosave/recovery, **hybrid convergence split** (tree/sequence CRDT via pycrdt/Automerge + tile-LWW,
  logical-clock+site-id), **awareness/presence** + WebSocket/WebRTC transport, **Automerge git-like
  branching**, Article VII schema-validate + caps, ~70 % offline-testable. Grounds the HOW for all slices.
- **DEP-2 (AGT-01 plan/ADR).** Cloud-port verb signatures + adapter contract, keyring keying scheme,
  autosave interval + retention policy, version/recovery + CRDT wire format, concrete CRDT lib +
  transport. **ADR expected for the cloud-port design** (plus the separate backend ADR, FLAG-BACKEND).
- **DEP-3 (AGT-01/AGT-10 — responsiveness + per-frame).** Worker-thread/executor for cloud ops
  (REQ-P10-UI-005; Slice A/B off the per-frame loop); **Slice C IS scoped → FLAG-PERFRAME assessment.**
- **BF-1 (Article II).** `AUTOSAVE_INTERVAL_MS`, `MAX_CLOUD_VERSIONS`, `MAX_CLOUD_PROJECT_BYTES`,
  `CLOUD_RETRY_LIMIT` in `logic/constants.py` (no literals).
- **BF-2 (data-model).** Cloud version metadata-envelope vs in-place versioning — AGT-01 HOW; contracts
  hold regardless.
- **BF-3 (Article II — Slice B/C).** `MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`, `MAX_COMMENTS_PER_PROJECT`,
  `MAX_CRDT_UPDATE_BYTES`, `CRDT_TILE_SIZE_PX` in `logic/constants.py`; shared by client `data/cloud/`
  and the backend's validation caps (no literals).
- **BF-4 (data-model — convergence).** Concrete CRDT lib (pycrdt/Yjs vs Automerge), raster tile-partition
  scheme, CRDT-state-in-`.pixproj` vs sidecar — AGT-01 HOW; determinism/commutativity/convergence
  contracts (REQ-P10-LOGIC-006/-007) hold regardless.

## Notes for `sdd-analyze` (AGT-01)

- Spec + matrix are internally consistent across **all three slices**: **34 REQs, 34 with scenarios, 0
  uncovered, 0 blocked**; tests `pending` (forward). No `PENDING`/`reserved` rows remain.
- **All 5 §10.2 clarifications ADJUDICATED** — this feature is **`COMPLETE`**, ready for `sdd-plan`
  (with two expected ADRs: cloud-port design DEP-2, and sync-backend placement FLAG-BACKEND).
- **Security-central phase (Article VII):** cloud-fetched `.pixproj` untrusted (REQ-P10-DATA-006);
  membership/comment/presence (REQ-P10-DATA-009), CRDT-update/presence over transport (REQ-P10-DATA-010),
  and **every backend-ingested payload (REQ-P10-BACKEND-002)** untrusted — schema-validate + caps, no
  eval/exec; tokens only in client keyring, never on the backend (CL-B3).
- **Article VI split:** Slice-A/B cloud/sync + hybrid convergence are off the per-frame loop
  (REQ-P10-LOGIC-004/-006 / REQ-P10-UI-005); **Slice C real-time apply (REQ-P10-LOGIC-007) + live cursors
  (REQ-P10-UI-013) RE-ENTER the 16 ms budget — AGT-10 FLAG-PERFRAME.**
- **New top-level component:** the sync backend (REQ-P10-BACKEND-001/-002) is OUTSIDE `logic/`/`data/`/
  `ui/`; `check_layering`/`check_cycles` govern the desktop client only — the backend↔client boundary is
  the zero-Qt transport port (REQ-P10-DATA-010). AGT-01 places the backend + writes its ADR.
