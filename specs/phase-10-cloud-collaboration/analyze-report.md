# Analyze Report (C1) — Phase 10: Cloud & Collaboration

| Field | Value |
| --- | --- |
| Feature | `phase-10-cloud-collaboration` |
| Author | AGT-01 (Architecture) via `sdd-analyze` |
| Date | 2026-07-04 |
| Artifacts | `constitution.md`, `specs/phase-10-cloud-collaboration/spec.md`, `plan.md`, `tasks.md` (all present) |
| Gate | **C1 — cross-artifact consistency + coverage** (Article VIII; defaults closed) |
| **Verdict** | **PASS** — 0 unresolved findings; **0 uncovered REQ-IDs** (34/34) |

---

## 1. Gate (step 1)

All four artifacts exist and parse: `constitution.md` (repo root), `spec.md`, `plan.md`, `tasks.md`
(`specs/phase-10-cloud-collaboration/`). Gate open to analysis. (`sdd-analyze` AN-E1/AN-E2 not triggered.)

## 2. spec ↔ constitution compliance (step 2)

| Article | Spec/plan/tasks posture | Verdict |
| --- | --- | --- |
| I (three-layer) | Cloud port + all adapters in ZERO-Qt `data/cloud/`; sync/version/autosave/convergence/apply/validation models in ZERO-Qt `logic/`; all cloud/collab UI in `ui/`. **The sync backend is a separate top-level `sync_backend/` OUTSIDE the three layers** (ADR-0027) reached only via the transport port. **Layering-rule updated** (`check_layering` forbids client→backend + backend→ui/data/Qt) and **verified exit 0** (plan §4.4/§11). No `ui/commands.py` change. | ✅ |
| II (numerics) | 9 new constants in `logic/constants.py`, names distinct from every shipped constant (`CRDT_TILE_SIZE_PX` ≠ `TILE_SIZE`); `SyncState` + CRDT message vocabulary intrinsic-local (plan §8, ADR-0001/BF-1/BF-3). | ✅ |
| III (quality) | Black/isort/flake8/mypy-strict for `logic/`+`data/`+`sync_backend/`; typed frozen contracts (plan §5). | ✅ |
| IV (testing) | Whole Slice-A contract + Slice-B storage CI-testable via the **fake adapter** (no network/creds); real-time in the CI gate via the **in-process/subprocess backend + loopback transport**; convergence deterministic over an in-memory transport (permuted-order property tests). Only live-provider OAuth out-of-CI (`pytest.mark.cloud_live`). Coverage ≥90/80. | ✅ |
| V (UX) | REQ-P10-UI-006/-007/-008 blocking gates (TG-05/06/07) across Slice-A UI, extended to Slice-B/C UI (UI-009..013). | ✅ |
| **VI (perf) — THE SPLIT** | Slice A/B batch/off the per-frame loop (LOGIC-004/-006; stays-responsive UI-005). **Slice C real-time apply (LOGIC-007) + live-cursor draw (UI-013) RE-ENTER the 16 ms `FRAME_BUDGET_MS`** → **REQUIRED AGT-10 FLAG-PERFRAME + CI perf-gate** (plan §7, ADR-0027 §7, T10C-13/14/15). **Budget never relaxed.** | ✅ |
| VII (security) — CENTRAL | Cloud-fetched `.pixproj` untrusted via PIO-1 (DATA-006); membership/comment/presence (DATA-009), CRDT-update/presence over transport (DATA-010), and **every backend-ingested payload** (BACKEND-002) validated (pure `logic/cloud_validation`, schema + size/depth/dimension/byte caps), **no `eval`/`exec`**; tokens only in client `data/cloud/` + **OS keyring**, never on the backend (CL-B3, enforced by the layering rule — backend cannot import `data/`); bounded numerics; portable paths. | ✅ |
| VIII (SDD gate) | This report is the pre-implement gate; dispatch held until PASS. | ✅ |
| X (traceability) | Every REQ (Slice A/B/C + backend) traces to an S-id / principle / article / forward primitive (PIO-1, DOC-1, HIS-1). The 2 `REQ-P10-BACKEND-*` follow `REQ-P<phase>-<LAYER>-<NNN>` (LAYER=BACKEND — the new first-class component; Article X §1) and each trace to ≥1 scenario + test (Article X §2). | ✅ |
| XI (extensibility) | The ONE cloud port is the extension seam (new provider/transport = new adapter); collaboration + real-time + backend layer on without weakening any article. | ✅ |

No constitution conflict (AN-D2 Branch A not triggered).

## 3. plan ↔ spec fidelity (step 2) — no drift

- **DEP-2 (cloud-port design)** ruled in **ADR-0026** (one port + verb set + normalized types + opaque
  cursor + capability model; fake adapter in CI / real providers out-of-CI; PKCE+loopback+Device-Grant +
  OS-keyring; atomic autosave/recovery; version envelope + remote-revision map BF-2; untrusted defence).
- **FLAG-BACKEND (sync-backend placement)** ruled in **ADR-0027** (new top-level `sync_backend/` OUTSIDE
  the three layers; asyncio-WebSocket relay + persistence; client `TransportPort` loopback/real split; the
  **layering-rule update**; backend untrusted-input + no-tokens; Article VI per-frame re-entry → AGT-10).
- **CL-B5 / BF-4 (convergence + CRDT lib)** ruled in **ADR-0028** (HYBRID: pycrdt tree/sequence CRDT for
  structure + pure tile/region-LWW for raster; logical-clock+site-id determinism; fork-doc branching;
  CRDT-state sidecar). The spec expected **two** ADRs (cloud-port + backend); the plan authors a **third**
  (convergence) because CL-B5/BF-4 is an independent, alternatives-bearing decision — an additive
  clarification, not drift.
- **CL-B1..CL-B5 (ADJUDICATED)** encoded verbatim: FULL scope A+B+C (all 34 REQ planned); fake adapter in
  CI + real providers out-of-CI (ADR-0026 §2); OS keyring in `data/cloud/` (ADR-0026 §3); real-time backend
  as a separate top-level component, localhost-CI-testable (ADR-0027); HYBRID convergence (ADR-0028).
- **BF-1/BF-3** (9 constants) placed (plan §8); **BF-2** (version metadata envelope around the `.pixproj`,
  not embedded) resolved (ADR-0026 §5); **BF-4** (pycrdt + tile-partition + sidecar) resolved (ADR-0028).
- The plan introduces **no** acceptance not in the spec and drops **none**. Every observable contract (one
  provider-agnostic port; `.pixproj` round-trip via PIO-1; ordered version history; crash-safe autosave/
  recovery; fake adapter without network/creds; untrusted-input defence; provider isolation; deterministic
  hybrid convergence; real-time apply + branching; a localhost-CI-testable backend) is preserved verbatim.

## 4. tasks ↔ plan completeness + REQ coverage (step 3)

**34/34 REQ-IDs covered** (10 DATA + 7 LOGIC + 13 UI + 2 BACKEND) — each appears in the plan module map
**and** ≥1 implementation task **and** ≥1 test/verify task. **0 uncovered.**

| REQ | Plan module | Impl task | Test/verify task |
| --- | --- | --- | --- |
| DATA-001 | data/cloud/port | T10A-06 | T10A-10 (SC-D001-1) |
| DATA-002 | data/cloud/fake_adapter (+PIO-1) | T10A-07 | T10A-10 (SC-D002-1) |
| DATA-003 | data/cloud/fake_adapter + version_history | T10A-07 | T10A-10 (SC-D003-1) |
| DATA-004 | data/cloud/fake_adapter (recovery slot) | T10A-07 | T10A-10 (SC-D004-1) |
| DATA-005 | data/cloud/fake_adapter | T10A-07 | T10A-10 (SC-D005-1) |
| DATA-006 | data/cloud/port (CloudDataError) + PIO-1 | T10A-06/-07 | T10A-10 (SC-D006-1) |
| DATA-007 | data/cloud/port (isolation) | T10A-06 | T10A-10, T10A-11 (SC-D001-1) |
| DATA-008 | data/cloud/auth + token_store | T10A-08 | T10A-10 (SC-D001-1 isolation) |
| DATA-009 (B) | data/cloud/shared_adapter + cloud_validation | T10B-05 | T10B-06, T10B-04 (SC-D009-1) |
| DATA-010 (C) | data/cloud/transport + loopback_transport | T10C-04 | T10C-05 (SC-D010-1) |
| LOGIC-001 | sync_state | T10A-02 | T10A-05 (SC-L001-1) |
| LOGIC-002 | autosave | T10A-03 | T10A-05 (SC-L002-1) |
| LOGIC-003 | version_history | T10A-04 | T10A-05 (SC-L003-1) |
| LOGIC-004 (NFR) | (sync off-loop posture) | T10A-02..04 | T10A-05, T10A-15 (SC-L004-1) |
| LOGIC-005 | constants + all models | T10A-01, T10B-01, T10C-01 | T10A-05 (SC-L005-1) |
| LOGIC-006 (B) | convergence | T10B-03 | T10B-04 (SC-L006-1) |
| LOGIC-007 (C — per-frame) | realtime_apply | T10C-02 | T10C-03, T10C-15 (SC-L007-1, L007-2) |
| UI-001 | cloud_actions | T10A-12 | T10A-15 (SC-UI-001-1) |
| UI-002 | version_history_browser | T10A-13 | T10A-15 (SC-UI-002-1) |
| UI-003 | recovery_prompt | T10A-14 | T10A-15 (SC-UI-003-1) |
| UI-004 | cloud_actions (connect) | T10A-12 | T10A-15 (SC-UI-004-1) |
| UI-005 (NFR) | cloud_worker | T10A-12 | T10A-15 (SC-UI-005-1) |
| UI-006 (NFR) | (all panels) | T10A/T10B/T10C ui | TG-05 (SC-UI-006-1) |
| UI-007 (NFR) | (all panels) | T10A/T10B/T10C ui | TG-06 (SC-UI-007-1) |
| UI-008 (NFR) | (all panels) | T10A/T10B/T10C ui | TG-07 (SC-UI-008-1) |
| UI-009 (B) | shared_projects_panel | T10B-07 | T10B-10 (SC-UI-009-1) |
| UI-010 (B) | comments_panel | T10B-08 | T10B-10 (SC-UI-010-1) |
| UI-011 (B) | presence_panel | T10B-09 | T10B-10 (SC-UI-011-1) |
| UI-012 (C) | branching_panel | T10C-10 | T10C-12 (SC-UI-012-1) |
| UI-013 (C — per-frame) | realtime_cursors_overlay | T10C-11/-14 | T10C-12, T10C-15 (SC-UI-013-1) |
| **BACKEND-001** | sync_backend/server + store | T10C-06 | T10C-08 (SC-BK-001-1) |
| **BACKEND-002** | sync_backend/server (validate) | T10C-07 | T10C-08 (SC-BK-002-1) |

**Orphan tasks (no single REQ):** T10A-11 / T10C-09 (layering scripts, Article I), TG-01 (STRUCTURE,
Article I), TG-02 (this gate, Article VIII), TG-03 (layering-rule update, Article I/ADR-0027), TG-04
(manifest deps, PL10-D14/Article VII), TG-08 (CHANGELOG, Article IX), TG-09 (checklist, Article IV/V/VI/VII)
— each cites its governing article/gate; legitimate cross-cutting tasks, not stray orphans.

## 5. Conflicts (step 4) — none unresolved

- **Backend "outside the three layers" vs `check_layering` governing only `pixelart_creator/`:** resolved —
  the backend is a top-level `sync_backend/` package governed by a new `check_layering` rule (client→backend
  forbidden; backend→ui/data/Qt forbidden; backend may reuse pure `logic/`), run via a second `--root .`
  invocation; both scripts verified exit 0 (plan §4.4/§11, ADR-0027 §5). No conflict.
- **Determinism (LOGIC) vs real-time delivery order (LOGIC-006/-007):** resolved — convergence is
  commutative (tree-CRDT + logical-clock+site-id LWW), so permuted delivery order → byte-identical
  `Document` (SC-L006-1); real-time apply reuses the same model (ADR-0028 §3). No conflict.
- **Article VI 16 ms vs batch cloud/sync:** resolved as **the split** — Slice A/B off the per-frame loop;
  **Slice C real-time apply + live cursors RE-ENTER the budget**, routed to AGT-10 (FLAG-PERFRAME, DEP-3,
  plan §7); budget never relaxed. Consistent with spec §5/§8. No conflict.
- **Tokens vs the backend (Article VII):** resolved — tokens live only in client `data/cloud/` + OS keyring;
  the layering rule makes it impossible for the backend to import `data/`, so it structurally cannot receive
  tokens (BACKEND-002, CL-B3). No conflict.
- **New constant names vs shipped constants:** all 9 distinct (Article II/BF-1/BF-3); `CRDT_TILE_SIZE_PX`
  (=64) parallels `TILE_SIZE` (=64) under a distinct name (the Phase-9 `MAX_GUIDES=256` precedent). No conflict.
- **Third ADR vs the spec's "two expected ADRs":** additive — ADR-0028 (convergence/CRDT-lib, CL-B5/BF-4)
  is an independent alternatives-bearing decision the spec left as a HOW; authoring it strengthens coverage,
  not drift.

## 6. Deterministic checks (run by AGT-01, plan §11) — after the layering-rule update

- `python scripts/check_layering.py --root pixelart_creator` → exit **0** (clean, 120 modules) — 2026-07-04.
- `python scripts/check_layering.py --root .` → exit **0** (0 governed modules until `sync_backend/` lands;
  the `sync_backend` rule is dormant-ready).
- `python scripts/check_cycles.py --root pixelart_creator` → exit **0** (no cycles, 121 modules).
- (`check_cycles --root sync_backend` runs once the package lands; generic over `--root`.)
- Planned Phase-10 edges are acyclic by construction (plan §4.4); AGT-03 re-runs all four invocations as
  each slice lands (T10A-11 / T10C-09).

## 7. Verdict (step 5)

**PASS (C1).** Unresolved-findings list is **empty**; **0 uncovered REQ-IDs** (34/34). The implement gate
is **OPEN** for Phase 10. Because the phase ships slice-by-slice, the orchestrator may dispatch **Slice A
first** (T10A-01 → T10A-15 + TG-04 manifest): **Slice A is CLEARED to proceed to AGT-03/AGT-04.** Slice B
dispatches after Slice A is gate-green/CI-green; Slice C after Slice B. Two ship-gating watch items carry
forward: (1) **FLAG-PERFRAME** — AGT-10 MUST discharge the Slice-C 16 ms real-time apply + live-cursor
budget (REQ-P10-LOGIC-007 / REQ-P10-UI-013) before Slice C ships; (2) the **CRDT-lib pin** (Researcher
caveat: pin `pycrdt`/`websockets`/`keyring` versions and re-verify the raster/binary handling before Slice
B/C implementation). Live-provider OAuth is verified manually, out-of-CI (`cloud_live`); everything else
(fake adapter, convergence, loopback backend) is in the CI gate.
