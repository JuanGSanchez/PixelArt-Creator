# Traceability matrix — Phase 13: Cross-platform Compatibility

REQ ↔ Researcher Q-section / shipped-architecture anchor / constitution article ↔ acceptance scenario ↔
landed test. Proves every requirement is specified, has an acceptance scenario, and is covered by a
shipped test. **23 REQs total.** **All 23 REQs across 13A–13E are `IMPLEMENTED` + tested + gate-green
(Phase 13 COMPLETE, 2026-07-07).** The **5 WEB REQs of 13E** had **D1/D2/D3 DECIDED by the USER on
2026-07-07** (grounded by research `a4c7da21`) and shipped. The **Test** column below now names the
**actual landed test files** — several tests landed under **consolidated filenames** that differ from the
early "(future)" placeholder names (recorded here as the T13-X01 editorial reconciliation): the five 13A
DATA REQs are covered by the single `tests/data/test_cross_platform.py`, and both 13A UI REQs by the
single `tests/ui/test_portability_ui.py`. No REQ is uncovered.

Grounding source: `docs/subagent-report-the-researcher-acaae022-20260707T093800.md` (PySide6/Qt 6.10) +
D1/D2/D3 grounding research `a4c7da21`.

## 13A — PORTABILITY HARDEN (`data/` + `ui/` + `BUILD`)

| REQ-ID | Layer | Slice | Traces (Researcher Q / architecture / article) | Acceptance scenario | Test (future) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P13-DATA-001 | data | 13A | Q5 (path separators/UNC → `pathlib`), Art I, Art II, PIO-1, `path_portability_check` | acceptance.md · SC-P13-DATA-001-1 | `scripts/path_portability_check.py` (widened) + `tests/data/test_cross_platform.py` (path-portability leg) | IMPLEMENTED |
| REQ-P13-DATA-002 | data | 13A | Q5 (UTF-8 not assumed on Windows), Art I, PIO-1 | acceptance.md · SC-P13-DATA-002-1 | `tests/data/test_cross_platform.py` (non-ASCII encoding legs) | IMPLEMENTED |
| REQ-P13-DATA-003 | data | 13A | Q5 (CRLF vs LF), Art I, Art II (determinism), P2 | acceptance.md · SC-P13-DATA-003-1 | `tests/data/test_cross_platform.py` (LF byte-equality legs) | IMPLEMENTED |
| REQ-P13-DATA-004 | data | 13A | Q5 (case-sensitivity; Linux strict; PEP 235), Art I, Art VII, Phase-11 `asset_cas` | acceptance.md · SC-P13-DATA-004-1 | `tests/data/test_cross_platform.py` (case-sensitivity legs) | IMPLEMENTED |
| REQ-P13-DATA-005 | data | 13A | Q5 (all pitfalls), Art I, Art IV, PIO-1, DATA-001..004, P2 | acceptance.md · SC-P13-DATA-005-1 | `test_cross_platform.py::test_pixproj_bytes_roundtrip_no_newline_translation` (its docstring already says "REQ-P13-DATA-003/-005" — the elided `/-005` is not a parseable id, which is why this REQ read as a gap), `::test_project_metadata_roundtrip_is_encoding_independent`, `::test_project_non_ascii_roundtrips_faithfully`, `::test_no_eval_or_exec_on_data_io_modules` | IMPLEMENTED |
| REQ-P13-UI-001 | ui | 13A | Q5 (font availability — flagged test area), Art I, Art V, Art VI | acceptance.md · SC-P13-UI-001-1 | `tests/ui/test_portability_ui.py` (font-fallback legs, both themes) | IMPLEMENTED |
| REQ-P13-UI-002 | ui | 13A | Q5 (DPI/scaling — flagged), Q3 (Qt plugins), Art VI (budget not relaxed), Phase-9 DPR precedent | acceptance.md · SC-P13-UI-002-1 | `tests/ui/test_portability_ui.py` (DPI/no-double-DPR + budget-not-relaxed legs) | IMPLEMENTED |
| REQ-P13-BUILD-001 | build | 13A | Q3 (`offscreen` headless plugin), Art IV, Art VIII, shipped `ci.yml`, Art X §1 (`BUILD` tag) | acceptance.md · SC-P13-BUILD-001-1 | `.github/workflows/ci.yml` (3-OS `quality-gate` matrix, AGT-09) | IMPLEMENTED |

## 13B — PORTABLE BUNDLE (`data/`, extends `data/asset_export.py`)

| REQ-ID | Layer | Slice | Traces | Acceptance scenario | Test (future) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P13-DATA-006 | data | 13B | Phase-11 `REQ-P11-DATA-005` (`asset_export`), Phase-11 `asset_cas`, Art I, Art II, DATA-001/-002 | acceptance.md · SC-P13-DATA-006-1 | `tests/data/test_bundle_export.py` | IMPLEMENTED |
| REQ-P13-DATA-007 | data | 13B | DATA-005 (cross-OS round-trip), Phase-11 `asset_export` import, Art IV, DATA-001..004 | acceptance.md · SC-P13-DATA-007-1 | `tests/data/test_bundle_cross_os.py` (CI matrix) | IMPLEMENTED |
| REQ-P13-DATA-008 | data | 13B | **Art VII (no `eval`/`exec`; untrusted input)**, Art I, Phase-11 `asset_export` import defence + `resolve()`+containment, Phase-10 `cloud_validation`, PIO-1 | acceptance.md · SC-P13-DATA-008-1/-2 | `tests/data/test_bundle_import_defence.py` (zip-slip + `eval`-free audit) + `tests/data/test_cross_platform.py` (`eval`-free data-I/O audit leg) | IMPLEMENTED |

## 13C — VPS ARTIFACTS (`BACKEND` — the shipped `sync_backend/`)

| REQ-ID | Layer | Slice | Traces | Acceptance scenario | Test (future) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P13-BACKEND-001 | backend | 13C | Art X §1 (`BACKEND` tag, ADR-0027), Art IV (REQ-P10-BACKEND-001 localhost-CI), Q4 (Docker/systemd; bind `0.0.0.0`; ulimit ≥ 65535; ~10K conns), `sync_backend/server.py` | acceptance.md · SC-P13-BACKEND-001-1 | `tests/backend/test_vps_localhost.py` (Docker/systemd launch → loopback convergence; `integration`-marked) | IMPLEMENTED |
| REQ-P13-BACKEND-002 | backend | 13C | Q4 (Nginx TLS; `Upgrade`/`Connection` proxy; `proxy_read_timeout` ≫ 60 s), Art X §1 (`BACKEND`) | acceptance.md · SC-P13-BACKEND-002-1 | `tests/backend/test_nginx_wss_localhost.py` (idle-past-60 s over loopback; `integration`-marked) | IMPLEMENTED |
| REQ-P13-BACKEND-003 | backend | 13C | Phase-10 CL-B4 (hosting options; no forced default), Art V, Q4, ADR-0027 | acceptance.md · SC-P13-BACKEND-003-1 | `tests/backend/test_hosting_default_unchanged.py` (default gate) | IMPLEMENTED |

## 13D — NATIVE INSTALLERS (`BUILD`)

| REQ-ID | Layer | Slice | Traces | Acceptance scenario | Test (future) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P13-BUILD-002 | build | 13D | Q3 (`pyside6-deploy`/PyInstaller; **Qt plugins bundled**; Windows exe/MSI), Art X §1 (`BUILD`) | acceptance.md · SC-P13-BUILD-002-1 | **No test in the tree.** Evidence is the `.github/workflows/ci.yml` Windows `build-installers` leg + smoke-launch and `packaging/pysidedeploy-windows.spec`; neither is a `test_*` file, so `build_matrix` cannot see it. Producing/launching the exe is inherently CI-executed. **Writable test owed → AGT-09:** assert `ci.yml` still declares the Windows `build-installers` leg and that `packaging/pysidedeploy-windows.spec` exists and is the file the leg names. | IMPLEMENTED (CI-verified); **test owed (AGT-09)** |
| REQ-P13-BUILD-003 | build | 13D | Q3 (**macOS Developer-ID signing + notarization + hardened runtime + stapling MANDATORY for store dist; `notarytool`+`stapler`**), Art X §1, **Art XI (credential-gated)** | acceptance.md · SC-P13-BUILD-003-1 | **No test in the tree.** Evidence is the `ci.yml` macOS `build-installers` leg + smoke-launch, `packaging/pysidedeploy-macos.spec`, and a credential-gated non-blocking signing step. Signing/notarization cannot run without Developer-ID credentials, so it is not automatable here. **Writable test owed → AGT-09:** assert the macOS leg exists, names the spec, and that its signing step is conditional (non-blocking) rather than required. | IMPLEMENTED (CI-verified); **test owed (AGT-09)** |
| REQ-P13-BUILD-004 | build | 13D | Q3 (Linux AppImage/Flatpak; Qt plugins bundled), Art X §1 (`BUILD`) | acceptance.md · SC-P13-BUILD-004-1 | **No test in the tree.** Evidence is the `ci.yml` Linux `build-installers` leg + AppImage smoke-launch, `packaging/pysidedeploy-linux.spec` and `packaging/build_appimage.sh`. **Writable test owed → AGT-09:** assert the Linux leg exists and that both packaging files it names are present and executable/referenced. | IMPLEMENTED (CI-verified); **test owed (AGT-09)** |
| REQ-P13-BUILD-005 | build | 13D | Art IV, Art VIII, Q3, Art X §1, REQ-P13-BUILD-001 (same matrix) | acceptance.md · SC-P13-BUILD-005-1 | **No test in the tree.** Evidence is the `ci.yml` `build-installers` matrix publishing all three artifacts. **Writable test owed → AGT-09:** assert the matrix enumerates exactly the three OS legs and that each uploads a named artifact — the same shape as the shipped gate-chain workflow check. | IMPLEMENTED (CI-verified); **test owed (AGT-09)** |

## 13E — WEB COMPANION VIEWER (`WEB` — new top-level `web_viewer/`) — **FULLY SPECIFIED (D1/D2/D3 DECIDED)**

| REQ-ID | Layer | Slice | Traces | Acceptance scenario | Test (future) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P13-WEB-001 | web | 13E | Q2a (browser WS viewer over backend), Q1b (no native iOS path), research `a4c7da21` (D1/D3), Phase-10 `sync_backend/`, Art V, Art VI (faithful render) | acceptance.md · SC-P13-WEB-001-1 | `test_render_fidelity.py::test_js_mirror_matches_shipped_reference_byte_exact` (reconstructed raster == shipped composite, 0 LSB, ADR-0044), `::test_wire_frames_decode_through_the_shipped_protocol`; static-serve legs `test_dev_server.py::test_served_html_has_html_content_type`, `::test_extensions_map_pins_js_and_mjs_to_text_javascript`, `::test_every_response_carries_no_store_cache_control`. **Not counted by `build_matrix`:** `web_viewer/tests/viewer_core.test.mjs` — the tool indexes only files whose NAME starts with `test_`, so this suite is invisible to the matrix (rename to `test_viewer_core.mjs` would fix it; AGT-13's call). | IMPLEMENTED |
| REQ-P13-WEB-002 | web | 13E | Art V, Art I (desktop sole editor), Q2a, research `a4c7da21` (D2/D3), user-decided scope (view + light interaction, not full edit) | acceptance.md · SC-P13-WEB-002-1 | `web_viewer/tests/test_view_scope.py` (view-scoped connection rejects mutation frame; no edit) + `viewer_core.test.mjs` (no mutation emitted) | IMPLEMENTED |
| REQ-P13-WEB-003 | web | 13E | Q2a (**iOS Safari + Android Chrome support WebSockets, no compat issue**), research `a4c7da21` (D3 vanilla, no build step), Art V | acceptance.md · SC-P13-WEB-003-1 | **UNTESTABLE AS WRITTEN in an automated suite.** "device-verified on iOS Safari + Android Chrome" cannot be asserted by any test in this tree — it names a manual device check as its evidence. What would make it testable: split the REQ into (a) an automatable clause — the viewer is served as plain static files with no build step and uses only baseline browser APIs — which IS covered today by `test_dev_server.py` (`test_extensions_map_pins_js_and_mjs_to_text_javascript`, `test_served_mjs_file_uses_pinned_javascript_content_type`, `test_default_host_is_loopback_not_wildcard`) and `test_share_token.py` (`test_share_token_introduces_no_new_dependency`); and (b) a non-automatable clause whose evidence is a dated, linked device-check record, not a test. Those test names are deliberately NOT written in `file.py`-colon-colon-`name` form: they cover clause (a) only, and recording them as this REQ's coverage would close a question the suite has not answered. | IMPLEMENTED (device-checked); **REQ needs splitting → AGT-02** |
| REQ-P13-WEB-004 | web | 13E | **Art I (three-layer purity — invariant)**, Phase-10 `sync_backend/` precedent (ADR-0027), Art X §1 (`WEB` tag), research `a4c7da21` (D1 no new dep, D3 vanilla), `check_layering --root` | acceptance.md · SC-P13-WEB-004-1 | **No test in the tree asserts the invariant.** It is script-gated: `scripts/check_layering.py` carries the `WEB_PKG = "web_viewer"` rule (L94, L169–185, mapping `WEB_PKG: QT` — i.e. Qt forbidden) and `check_cycles --root web_viewer`; but `tests/scripts/test_check_layering.py` never mentions `web_viewer`, so the rule itself is untested. Only the no-new-dependency clause has a test — `test_share_token.py` (`test_share_token_introduces_no_new_dependency`), written here in prose so it is not miscounted as covering the Qt-import invariant. **Test owed → AGT-13:** assert no module under `web_viewer/` imports PySide6/Qt, `pixelart_creator.ui`, `pixelart_creator.data` or `sync_backend` — cheap, and it pins the Article I invariant this REQ calls an invariant. | IMPLEMENTED (script-gated); **test owed (AGT-13)** |
| REQ-P13-WEB-005 | web | 13E | **Art VII (no `eval`/`exec`; untrusted input — invariant)**, Phase-10 `cloud_validation`/`sync_protocol`, research `a4c7da21` (D1 serving, D2 signed token), Q2a, Q4 | acceptance.md · SC-P13-WEB-005-1/-2 | `test_share_token.py::test_valid_token_connects_and_receives_join_backlog`, `::test_rejected_tokens_are_refused_at_handshake`, `::test_rejected_token_client_gets_no_backlog_frames`, `::test_expired_token_is_rejected`, `::test_wrong_audience_is_rejected`, `::test_bad_signature_is_rejected`, `::test_alg_none_token_is_rejected_even_when_correctly_signed`, `::test_tampered_payload_is_rejected`, `::test_no_eval_or_exec_on_the_web_input_path`, `test_view_scope.py::test_project_a_token_cannot_access_project_b`, `::test_view_scope_update_dropped_but_presence_and_leave_work` | IMPLEMENTED |

## Resolved clarifications (13E only) — DECIDED 2026-07-07 (spec §10, research `a4c7da21`)

| ID | Question | Decision | Encoded in |
| --- | --- | --- | --- |
| **D1** | Web-serving stack / whether it adds a dependency | **REUSE EXISTING STACK, NO NEW DEPENDENCY** — vanilla static client served by the already-planned Nginx (13C); data over the existing `sync_backend/` `websockets`; stdlib `http.server` for local dev only; no FastAPI/aiohttp | REQ-P13-WEB-001/-004/-005 |
| **D2** | Viewer auth model | **SIGNED SHARE-LINK TOKEN** — per-project short-lived signed bearer token over HTTPS; backend validates signature + expiry + issuer/audience and scopes to the project; not full OAuth, no login | REQ-P13-WEB-002/-005 |
| **D3** | Vanilla client vs SPA | **VANILLA HTML/CSS/JS** — no build step, no framework/SPA; Canvas API faithful render (`image-rendering: pixelated`, `imageSmoothingEnabled = false`, integer scale); iOS Safari + Android Chrome (iOS device-test noted) | REQ-P13-WEB-001/-003/-004 |

## Coverage summary

- **REQs total:** 23 — **DATA 8** (13A: 001–005; 13B: 006–008), **UI 2** (13A: 001–002), **BUILD 5**
  (13A CI matrix: 001; 13D installers: 002–005), **BACKEND 3** (13C: 001–003), **WEB 5** (13E: 001–005).
- **Layer-tag rationale (Article X §1, ADR-0027 precedent):** three-layer work uses `DATA`/`UI`; the
  non-three-layer components earn dedicated first-class tags exactly as Phase 10 gave `sync_backend/` the
  `BACKEND` tag — **`BACKEND`** (13C VPS artifacts for the shipped backend), **`BUILD`** (13A CI matrix +
  13D packaging pipeline, AGT-09-owned DevOps outside the three layers), **`WEB`** (13E new top-level
  `web_viewer/`, headless, Qt-free).
- **Implemented + tested + gate-green — ALL 23 REQs (Phase 13 COMPLETE, 2026-07-07):** **13A**
  (REQ-P13-DATA-001..005, REQ-P13-UI-001..002, REQ-P13-BUILD-001), **13B** (REQ-P13-DATA-006..008),
  **13C** (REQ-P13-BACKEND-001..003), **13D** (REQ-P13-BUILD-002..005), and **13E**
  (REQ-P13-WEB-001..005, D1/D2/D3 DECIDED 2026-07-07) — each with FULL acceptance + ≥ 1 Gherkin scenario +
  trace + ≥ 1 landed test. (T13-X01 editorial reconciliation: the 13A DATA REQs consolidated into
  `tests/data/test_cross_platform.py` and the 13A UI REQs into `tests/ui/test_portability_ui.py` — the
  early per-REQ placeholder filenames were never separate files.)
- **13E DECIDED (was PARTIAL):** REQ-P13-WEB-001..005 now encode D1 (reuse existing stack, no new
  dependency), D2 (signed share-link token), D3 (vanilla HTML/CSS/JS). REQ-P13-WEB-004 (Article I
  placement) and the `eval`-free half of REQ-P13-WEB-005 (Article VII) remain **D1/D2/D3-independent
  invariants**; the previously-deferred acceptance (render fidelity, cross-browser, token validation,
  no-new-dependency) is now complete (6 WEB scenarios: SC-P13-WEB-001-1..004-1, 005-1, 005-2).
- **Invariants preserved (NOT relaxed):** **Article I** (three-layer purity — `BUILD`/`WEB` outside the
  layers; `web_viewer/` Qt-free, REQ-P13-WEB-004) and **Article VII** (no `eval`/`exec` — bundle import
  REQ-P13-DATA-008, web input REQ-P13-WEB-005). **Article VI** budget not touched (REQ-P13-UI-002).
  **Article XI** credential-gating (REQ-P13-BUILD-003, non-blocking notarization).
- **Every REQ across all 23** traces to a Researcher Q-section / architecture anchor (+ research
  `a4c7da21` for 13E) + a constitution article + ≥ 1 Gherkin scenario. **No REQ is untraced or
  uncovered.**
- **Gate:** all of 13A–13E are **BUILT + tested**; the T13-X01 final `sdd-analyze` (C1) re-ran **PASS**
  with zero unresolved cross-artifact findings, and all five `check_layering`/`check_cycles` roots exit 0
  (`pixelart_creator` 180, `.` 5, `pixelart_creator` cycles 182, `sync_backend` 3, `web_viewer` 9). No
  `[NEEDS CLARIFICATION]` marker remains. **Phase-13 status: COMPLETE.**
