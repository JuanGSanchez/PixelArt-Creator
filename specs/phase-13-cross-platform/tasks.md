# Tasks — Phase 13: Cross-platform Compatibility

| Field | Value |
| --- | --- |
| Feature | `phase-13-cross-platform` |
| Author | AGT-01 (Architecture) via `sdd-tasks` |
| Date | 2026-07-07 |
| Over | `plan.md` + `docs/adr/0035` (web_viewer placement) + `0036` (web viewer wire+token contract) + `0037` (portable bundle) + `0038` (packaging) — **dependency-ordered, slice-by-slice**, each an independently gate-green, CI-green shippable increment. **13A → 13B → 13C → 13D → 13E** (by dependency/risk). |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII). **NO implementation begins until C1 is green.** Each task leaves the gate green (Article IX). |
| Status | **ALL SLICES 13A–13E LANDED (2026-07-07).** Every engineering task `done`; the final analyze gate (T13-X01) re-ran C1 **PASS** and confirmed all five `check_layering`/`check_cycles` roots exit 0; STRUCTURE.md updated (T13-X02). Only `T13-X03` (Phase-13 CHANGELOG, AGT-08) remains `todo`. |

Status legend: `todo` | `doing` | `done`. **One owner per task.** Owners per the delegation table:
**AGT-01** architecture/analyze/gate + ADRs + STRUCTURE + layering-rule spec; **AGT-03** `logic/`+`data/`
code + the `check_layering.py` rule edit + `web_viewer/` Python glue + `sync_backend/` handshake extension;
**AGT-04** logic/data + backend + web Python integration tests; **AGT-05** `ui/` code (font/DPI);
**AGT-06** UI/a11y/both-theme + browser acceptance; **AGT-07** string audit/i18n (Qt strings only);
**AGT-08** docs (deployment/packaging/ADR publish); **AGT-09** CI test+build matrix, packaging config, VPS
artifacts, commits; **AGT-10** DPI per-frame budget assessment; **The Metaprompter (AGT-M2)** the 13E
on-demand asset generation (new `agt-11-web-client` agent + `web-viewer` skill + the 3 modifies);
**agt-11-web-client** (once generated) the `web_viewer/` frontend + serving glue.

**INVARIANTS (CENTRAL, every slice):** Article I (three-layer purity + the `BACKEND`/`BUILD`/`WEB`
non-three-layer components outside it; `check_layering`/`check_cycles` exit 0 on all roots) and Article VII
(bundle import + web input are untrusted, path-traversal/zip-slip-defended, size/shape-capped, **`eval`/
`exec`-free**; no committed secret) are **NOT relaxed**. The 16 ms `FRAME_BUDGET_MS` is **not touched**
(Article VI). macOS signing is credential-gated, non-blocking (Article XI).

---

## Slice 13A — Portability harden (`data/` + `ui/` + `BUILD` CI matrix; Q5)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13A-01 | Audit every read/write site in `data/`; convert any hand-concatenated/literal-separator path to a `pathlib.Path`; **harden + widen `scripts/path_portability_check.py`** to cover the newly-touched sites (still exits 0 on the tree). | AGT-03 | `pixelart_creator/data/*`, `scripts/path_portability_check.py` | analyze C1 | DATA-001 / SC-P13-DATA-001-1 | done |
| T13A-02 | Enforce **explicit `encoding="utf-8"`** at every text/JSON `open()`/read/write in `data/` (never rely on the platform default / `PYTHONUTF8`); `json.dumps(ensure_ascii=False)` where a non-ASCII human-readable round-trip matters. | AGT-03 | `pixelart_creator/data/*` | T13A-01 | DATA-002 / SC-P13-DATA-002-1 | done |
| T13A-03 | **CRLF/LF determinism:** write every emitted *text* artifact with a fixed OS-independent newline (`open(..., newline="\n")` / explicit `"\n"`, no platform translation); confirm the binary `.pixproj` zlib payload is unaffected. | AGT-03 | `pixelart_creator/data/*` | T13A-01 | DATA-003 / SC-P13-DATA-003-1 | done |
| T13A-04 | **Case-sensitivity discipline:** ensure every filename/asset-reference/CAS-blob lookup is by **exact stored case** (code case-sensitively, PEP 235); confirm CAS keys are case-exact lowercase-hex; no case-folding lookup anywhere in `data/`. | AGT-03 | `pixelart_creator/data/*` | T13A-01 | DATA-004 / SC-P13-DATA-004-1 | done |
| T13A-05 | Logic/data regression tests: pathlib-only path audit; **non-ASCII (accented/CJK/emoji) round-trip byte-faithful**; text-artifact byte-equality (LF); **case-distinct assets (`Hero.png`/`hero.png`) resolve on Linux** without collision. Deterministic, headless. | AGT-04 | `tests/data/test_path_portability.py`, `test_encoding_roundtrip.py`, `test_line_endings.py`, `test_case_sensitivity.py` | T13A-02, -03, -04 | DATA-001..004 / SC-P13-DATA-001-1..004-1 | done |
| T13A-06 | **Headline byte-faithful cross-OS round-trip test:** a representative project (multi-layer, animated, tilemapped, non-ASCII names, case-distinct assets) saved on the source OS loads **model-equal** on the target OS and re-saves to a **stable** payload — parametrised so the CI matrix exercises all six ordered OS pairs. | AGT-04 | `tests/data/test_cross_os_roundtrip.py` | T13A-05 | DATA-005 / SC-P13-DATA-005-1 | done |
| T13A-07 | **Font-availability fallback:** define the UI font once, by role, with a resolvable fallback chain (family-list / `QFont.insertSubstitutions` in the theming seam) — no single-OS family per widget; both themes unaffected. `tr()`/`changeEvent` preserved. | AGT-05 | `pixelart_creator/ui/` (theming/font seam + app bootstrap) | analyze C1 | UI-001 / SC-P13-UI-001-1 | done |
| T13A-08 | **DPI/scaling correctness:** rely on Qt6 automatic high-DPI; lay out in device-independent coords; **remove/avoid any manual DPR multiply** (Phase-9 discipline). No per-frame budget change. | AGT-05 | `pixelart_creator/ui/` (app bootstrap + views) | analyze C1 | UI-002 / SC-P13-UI-002-1 | done |
| T13A-09 | **AGT-10 DPI budget assessment (no new gate):** confirm UI-002 introduces no double-scale / no new per-frame cost and the nearest-neighbour canvas still holds 16 ms; `FRAME_BUDGET_MS` not relaxed (assessment only — no `perf_profile` change). | AGT-10 | assessment → AGT-05/AGT-01 | T13A-08 | UI-002 / Article VI | done |
| T13A-10 | UI tests (pytest-qt, offscreen, both themes): primary text renders with a resolvable font (no `.notdef` boxes) on each OS (headless where possible, documented manual note otherwise); layout at 100/150/200% has no truncation/double-scale and the pixel canvas stays crisp; a11y preserved. | AGT-06 | `tests/ui/test_font_fallback.py`, `tests/ui/test_dpi_scaling.py` | T13A-07, -08 | UI-001, UI-002 / SC-P13-UI-001-1/-002-1 | done |
| T13A-11 | String audit (`string_audit_check`) on any changed `ui/` file **only if** 13A adds a new user-visible string (font/DPI fixes are behavioural — likely none); wrap in `tr()` + `changeEvent` if any. Skipped if none. | AGT-07 | changed `ui/` files | T13A-07, -08 | UI-001/-002 (Article V) | done |
| T13A-12 | **CI TEST matrix (BUILD-001):** extend `ci.yml` `quality-gate` into a `strategy.matrix.os: [ubuntu-latest, windows-latest, macos-latest]`; each leg runs the FULL suite **headless** (`QT_QPA_PLATFORM=offscreen`; Ubuntu keeps the xcb/EGL apt install; Win/mac need none) incl. lint/type/tests/coverage + `path_portability_check` + the new cross-OS/encoding/case/round-trip tests; **preserve** the concurrency guard + Python-3.12 pin; a deliberate cross-OS regression fails the matrix. | AGT-09 | `.github/workflows/ci.yml` | T13A-05, -06, -10 | BUILD-001 / SC-P13-BUILD-001-1 | done |
| T13A-13 | Re-run `check_layering` (`--root pixelart_creator` **and** `--root .`) + `check_cycles` (`--root pixelart_creator`): confirm 13A adds no Qt to `data/`, no new module/edge/cycle; all exit 0. **AGT-01 slice gate.** | AGT-01 | `scripts/*` (invoke) | T13A-05, -08 | Article I / plan §7 | done |
| T13A-14 | Commit the 13A edit-set (Conventional Commits, REQ-tagged, gate-green). | AGT-09 | git | T13A-12, -13 | Article IX | done |

## Slice 13B — Portable bundle (`data/`, extends `asset_export.py`; ADR-0037)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13B-01 | Add the bundle caps to `constants.py`: `MAX_BUNDLE_BYTES`, `MAX_BUNDLE_ENTRIES`, `MAX_BUNDLE_ENTRY_BYTES` (with citation docstrings; **names DISTINCT from every shipped constant**; `MAX_BUNDLE_BYTES` may mirror `MAX_BLOB_BYTES` sizing). | AGT-03 | `pixelart_creator/logic/constants.py` | T13A-14 | DATA-006/-008 / plan §8, ADR-0037 | done |
| T13B-02 | **Extend `data/asset_export.py`** with `export_project_bundle(...)`: a single-file deterministic `zipfile` (`ZIP_DEFLATED`, fixed metadata, **POSIX forward-slash internal paths**, UTF-8 text, `schema_version`) embedding the `.pixproj` payload + **every referenced CAS blob** (via the shipped reference-set resolution — **no re-implemented CAS logic**) + catalog/sidecars. Zero Qt; `data → data`/`logic` only. | AGT-03 | `pixelart_creator/data/asset_export.py` | T13B-01 | DATA-006 / SC-P13-DATA-006-1 | done |
| T13B-03 | Add `import_project_bundle(...)`: **untrusted-input defence** — `resolve()`+containment (reject `..`/absolute/symlink/zip-slip; **write nothing** outside target; temp-dir + atomic move); enforce `MAX_BUNDLE_*` caps against the header **and during streamed extraction**; content-hash-verify each blob; `json`-only parse; malformed/oversized/unknown-version → user-facing `AssetExportError` (no partial write). **Zero `eval`/`exec`.** | AGT-03 | `pixelart_creator/data/asset_export.py` | T13B-02 | DATA-008 / SC-P13-DATA-008-1/-2 | done |
| T13B-04 | Bundle export/round-trip tests (headless): export produces one self-contained bundle with the payload + every referenced blob (no dangling ref); the exporter reuses the shipped `asset_export` reference resolution (no re-implemented CAS). | AGT-04 | `tests/data/test_bundle_export.py` | T13B-02 | DATA-006 / SC-P13-DATA-006-1 | done |
| T13B-05 | Cross-OS import round-trip test (parametrised for the six OS pairs in the matrix): a bundle exported on the source OS imports **model-equal** on the target with all assets present + resolvable, incl. non-ASCII + case-distinct names. | AGT-04 | `tests/data/test_bundle_cross_os.py` | T13B-03 | DATA-007 / SC-P13-DATA-007-1 | done |
| T13B-06 | Bundle import-defence tests: a traversal-crafted bundle (`../`, absolute, symlink) is **rejected** and writes nothing outside target; an oversized/malformed/unknown-version bundle raises the defined error with no partial write; **source audit confirms zero `eval`/`exec`** on the import path. | AGT-04 | `tests/data/test_bundle_import_defence.py` | T13B-03 | DATA-008 / SC-P13-DATA-008-1/-2 | done |
| T13B-07 | Re-run `check_layering` (both roots) + `check_cycles`: confirm the bundle extension adds no Qt to `data/`, no new module/edge/cycle; all exit 0. **AGT-01 slice gate.** | AGT-01 | `scripts/*` (invoke) | T13B-03 | Article I / plan §7 | done |
| T13B-08 | Commit the 13B edit-set (REQ-tagged, gate-green). | AGT-09 | git | T13B-04..07 | Article IX | done |

## Slice 13C — VPS artifacts for the shipped `sync_backend/` (`BACKEND`; Q4; NO backend code change; NO new ADR)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13C-01 | Author `deploy/Dockerfile` + `deploy/pixelart-sync.service` (systemd) that launch the **unchanged** `sync_backend/` bound to **`0.0.0.0`** with FD limit **≥ 65535** (`--ulimit nofile=65535:65535` / `LimitNOFILE=65535`); document the ~10K-conns/process ceiling. **No backend source change.** | AGT-09 | `deploy/Dockerfile`, `deploy/pixelart-sync.service` | T13B-08 | BACKEND-001 / SC-P13-BACKEND-001-1 | done |
| T13C-02 | Author `deploy/nginx-sync.conf`: terminate **TLS**, proxy **WSS→WS** forwarding `Upgrade`/`Connection`, set **`proxy_read_timeout 86400`** (≫ 60 s default); backend serves plain WS behind it. | AGT-09 | `deploy/nginx-sync.conf` | T13C-01 | BACKEND-002 / SC-P13-BACKEND-002-1 | done |
| T13C-03 | Deployment docs (`docs/`) presenting **localhost + cloud-adapter + VPS** as co-equal options, the Docker/systemd/Nginx recipe, and the Gatekeeper/ops notes; adopting VPS changes **no default**. (Update the existing `DEPLOYMENT.md` if in scope, else a docs topic.) | AGT-08 | `docs/` (deployment topic) | T13C-02 | BACKEND-003 / SC-P13-BACKEND-003-1 | done |
| T13C-04 | Localhost-provable tests: Docker/systemd launch → a loopback client reproduces the shipped multi-client convergence (backend unmodified); the Nginx config sustains an idle WS **past 60 s** over loopback/self-signed. **Mark `integration`** (needs container/nginx; deselected in the default matrix; dedicated 13C job or documented manual run). | AGT-04 | `tests/backend/test_vps_localhost.py`, `test_nginx_wss_localhost.py` | T13C-02 | BACKEND-001/-002 / SC-P13-BACKEND-001-1/-002-1 | done |
| T13C-05 | Default-unchanged behavioural test (no marker, runs in the default gate): with 13C ignored, the app + backend behave identically to today and require no code change. | AGT-04 | `tests/backend/test_hosting_default_unchanged.py` | T13C-01 | BACKEND-003 / SC-P13-BACKEND-003-1 | done |
| T13C-06 | (If a dedicated 13C integration job is chosen) wire it in CI to run the `integration`-marked VPS tests; the default cross-OS matrix stays green without container/nginx. | AGT-09 | `.github/workflows/ci.yml` | T13C-04 | BACKEND-001/-002 / Article IV | done |
| T13C-07 | Commit the 13C artifacts + docs (REQ-tagged, gate-green). | AGT-09 | git | T13C-03, -05 | Article IX | done |

## Slice 13D — Native installers (`BUILD`; Q3; ADR-0038)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13D-01 | Author committed, reproducible packaging config (`packaging/pysidedeploy.spec` per target; PyInstaller fallback documented); confirm Qt plugin bundling; exclude `sync_backend`/`web_viewer`/`tests`/`scripts`/`docs` from the distributable. | AGT-09 | `packaging/*` | T13C-07 | BUILD-002/-004 / ADR-0038 | done |
| T13D-02 | **Windows** build leg: produce an installable `.exe`/`.msi` (Qt plugins bundled) + smoke-launch on a clean Windows env; reproducible from the committed config. | AGT-09 | `.github/workflows/ci.yml` (build matrix), `packaging/*` | T13D-01 | BUILD-002 / SC-P13-BUILD-002-1 | done |
| T13D-03 | **Linux** build leg: produce a runnable **AppImage** (Qt plugins bundled) + smoke-launch on a clean Linux env; reproducible. | AGT-09 | `.github/workflows/ci.yml`, `packaging/*` | T13D-01 | BUILD-004 / SC-P13-BUILD-004-1 | done |
| T13D-04 | **macOS** build leg: produce an **unsigned/ad-hoc .app/.dmg** + smoke-launch (Gatekeeper-bypass documented); add the **credential-gated, NON-blocking** signing→notarization(`notarytool`)→stapling step that runs **only** when an Apple Developer ID secret is supplied; **no credential committed**; its absence does not fail the phase (Article XI). | AGT-09 | `.github/workflows/ci.yml`, `packaging/*`, `docs/` (signing note) | T13D-01 | BUILD-003 / SC-P13-BUILD-003-1 | done |
| T13D-05 | **CI BUILD matrix (BUILD-005):** one matrix on a build/tag trigger builds all three distributables on their OS legs and publishes them as downloadable artifacts; a per-leg failure fails that leg visibly; concurrency guard + Python pin preserved; the macOS signing step is the credential-gated non-blocking addition. | AGT-09 | `.github/workflows/ci.yml` | T13D-02, -03, -04 | BUILD-005 / SC-P13-BUILD-005-1 | done |
| T13D-06 | Packaging + install docs (per-OS install/run, macOS Gatekeeper/notarization note). | AGT-08 | `docs/` | T13D-05 | BUILD-002..005 (docs) | done |
| T13D-07 | Commit the 13D packaging/CI edit-set (REQ-tagged, gate-green). | AGT-09 | git | T13D-05, -06 | Article IX | done |

## Slice 13E — Web companion viewer (`WEB`; D1/D2/D3; ADR-0035 + ADR-0036)

### 13E-PREP — contract freeze + layering rule (BEFORE any asset generation) — AGT-01/AGT-03/AGT-09

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13E-P01 | **DONE this session:** author **ADR-0035** (`web_viewer/` placement, outside the three layers, Qt-free; mirrors ADR-0027) + **ADR-0036** (client↔backend serialization + signed-share-link-token contract) — freezing the wire + token format the vanilla client + the `websockets` backend share. **Coordinated with AGT-03** (the implementer). | AGT-01 | `docs/adr/0035-*.md`, `docs/adr/0036-*.md` | T13D-07 | WEB-004/-005 / ADR-0035/0036 | done |
| T13E-P02 | Add the **`check_layering.py` `web_viewer` FORBIDDEN rule** (mirror `BACKEND_PKG`, per ADR-0035 §3): `WEB_PKG = "web_viewer"` forbids Qt/`ui`/`data`/`sync_backend`, MAY reuse pure `logic/`; add `web_viewer` to the forbidden sets of `logic`/`data`/`ui` and of `sync_backend`. Confirm baseline still exits 0 (dormant-ready until the package lands). | AGT-03 | `scripts/check_layering.py` | T13E-P01 | WEB-004 / SC-P13-WEB-004-1 | done |
| T13E-P03 | Wire CI to run `check_layering --root .` (already governs `sync_backend`; now covers `web_viewer` via `parts[0]`) + add `check_cycles --root web_viewer` (once the package lands); confirm the twin/triple invocation. Exclude `web_viewer*` from the desktop wheel in `pyproject.toml` (defence-in-depth, mirror `sync_backend*`). | AGT-09 | `.github/workflows/ci.yml`, `pyproject.toml` | T13E-P02 | WEB-004 / Article I | done |

### 13E-GEN — on-demand asset generation (AFTER the contract freeze + layering rule; BEFORE the frontend build) — The Metaprompter (AGT-M2)

> Sequenced per the `[[generate-assets-on-demand]]` directive + the approved Recommender plan. The
> orchestrator dispatches **The Metaprompter** to GENERATE the two new assets **against the frozen
> ADR-0035/0036 contract**. This MUST follow T13E-P01..P03 and precede T13E-B01+.

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13E-G01 | GENERATE a new domain agent **`agt-11-web-client`** — owns the `web_viewer/` **frontend + serving glue** (vanilla HTML/CSS/JS client + stdlib dev server); **NO Qt, NO domain logic** (reaches the backend over the wire; reuses pure `logic/` seams only); scoped to `web_viewer/`. Grounded in ADR-0035/0036. | The Metaprompter (AGT-M2) | `.claude/agents/agt-11-web-client.md` | T13E-P03 | WEB-001..004 / ADR-0035 | done |
| T13E-G02 | GENERATE a **`web-viewer` skill** — the vanilla pixel-canvas renderer (`image-rendering: pixelated` + `imageSmoothingEnabled=false` + integer scale) + WS-client-over-`sync_backend` + signed-share-link-token presentation pattern; no build step, iOS-Safari/Android-Chrome target. Grounded in ADR-0036 §4 + a4c7da21. | The Metaprompter (AGT-M2) | `.claude/skills/web-viewer/SKILL.md` | T13E-P03 | WEB-001/-003/-005 / ADR-0036 | done |
| T13E-G03 | MODIFY `.claude/agent-manifest.md`: add the **AGT-11** domain-agent row (+ its "Owns/Does not own") and the `web-viewer` skill under the owning-agent skill table. | The Metaprompter (AGT-M2) | `.claude/agent-manifest.md` | T13E-G01, -G02 | Article X (manifest consistency) | done |
| T13E-G04 | MODIFY `.github/workflows/ci.yml`: add (a) `check_layering --root .` coverage assertion for `web_viewer/`, (b) a **Node JS-unit step** for the vanilla client (headless, no framework/bundler), and (c) collection of the **Python web integration test** (`web_viewer/tests/`). | The Metaprompter (AGT-M2) (spec) → AGT-09 (CI wiring) | `.github/workflows/ci.yml` | T13E-G01, -G02 | WEB-001/-004 / Article IV | done |

### 13E-BUILD — implement against the frozen contract (AFTER generation)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13E-B01 | Add `SHARE_TOKEN_MAX_TTL_S` to `constants.py` (short-lived token lifetime cap, cited a4c7da21 D2; name distinct). | AGT-03 | `pixelart_creator/logic/constants.py` | T13E-G04 | WEB-005 / plan §8, ADR-0036 | done |
| T13E-B02 | Implement the pure **`logic/share_token.py`** (zero Qt/`data`; stdlib `hmac`/`hashlib`/`base64`/`json` only — **no new dependency**): `mint(claims, secret)` / `verify(token, secret, *, expected_iss, expected_aud, now)` / `ShareTokenError`; validate `alg` (never trust "none") + constant-time signature + `exp` (≤ `SHARE_TOKEN_MAX_TTL_S`) + `iss` + `aud` + `project_id`/`scope`; `json`-only, max-length cap, **no `eval`/`exec`**. Per ADR-0036 §1. | AGT-03 | `pixelart_creator/logic/share_token.py` | T13E-B01 | WEB-005 / SC-P13-WEB-005-1/-2 | done |
| T13E-B03 | **Extend `sync_backend/server.py`** (not re-author): verify the share token in the `websockets` `process_request` handshake (reject expired/wrong-aud/bad-sig → 401/403, serve no data), **scope the connection to the token's `project_id`**, and **reject any mutation (`update`) frame on a `scope:"view"` connection** — reusing `logic/share_token` + `logic/sync_protocol`/`cloud_validation` caps (untrusted, `eval`-free). Preserve the shipped editor-client convergence. | AGT-03 | `sync_backend/server.py` | T13E-B02 | WEB-002/-005 / SC-P13-WEB-002-1/-005-1/-2 | done |
| T13E-B04 | Build the `web_viewer/` **frontend**: `web_viewer/static/{index.html,viewer.css,viewer.js}` — vanilla HTML/CSS/JS, no build step (D3); Canvas pixel-faithful renderer (native-res canvas attrs + CSS scale + `image-rendering: pixelated` + `imageSmoothingEnabled=false` + integer scale); WS client over `sync_backend`; presents the share token; **light interaction only** (layer toggle / frame nav / pan-zoom; NO editing/mutation message). | agt-11-web-client | `web_viewer/static/*` | T13E-B03 | WEB-001/-002/-003 / SC-P13-WEB-001-1/-002-1/-003-1 | done |
| T13E-B05 | Build the `web_viewer/` **Python serving glue** (Qt-free, no new dependency): `web_viewer/dev_server.py` (stdlib `http.server` static serving — LOCAL DEV ONLY) + `__init__.py` + any thin token/serving glue reusing pure `logic/` seams; the **13C Nginx** `location` block serves `static/` in production (extend `deploy/nginx-sync.conf`). | agt-11-web-client (frontend glue) / AGT-03 (Python glue) | `web_viewer/dev_server.py`, `web_viewer/__init__.py`, `deploy/nginx-sync.conf` | T13E-B03 | WEB-001/-004 / SC-P13-WEB-001-1/-004-1 | done |
| T13E-B06 | **Python web integration test** (`web_viewer/tests/`): a valid, unexpired, correctly-scoped token serves the named project over `sync_backend`; expired/wrong-aud/bad-sig is rejected + serves no data; a project-A token cannot access project-B; a view-scoped mutation is rejected; a **source audit confirms zero `eval`/`exec`** on any web-input path; no new dependency in the manifest. | AGT-04 | `web_viewer/tests/test_share_token.py`, `web_viewer/tests/test_view_scope.py` | T13E-B03, -B05 | WEB-005/-002 / SC-P13-WEB-005-1/-2/-002-1 | done |
| T13E-B07 | Render-fidelity + JS-unit tests (headless where feasible): the vanilla client renders the shared source **pixel-faithfully** (nearest-neighbour, integer scale, no smoothing) verified by a rendered-pixel comparison; the client emits no mutation message; no build-step/transpile required. | agt-11-web-client / AGT-06 | `web_viewer/tests/test_render_fidelity.*` | T13E-B04 | WEB-001/-002 / SC-P13-WEB-001-1/-002-1 | done |
| T13E-B08 | **Cross-browser + a11y acceptance:** the viewer loads/connects/renders pixel-faithfully on iOS Safari + Android Chrome + a desktop browser; **iOS Safari verified on a real device** (documented device check per WEB-003) confirming `image-rendering: pixelated` + `imageSmoothingEnabled=false` are crisp; browser a11y (keyboard/focus) as feasible. | AGT-06 | `web_viewer/tests/*` + documented device-check note | T13E-B04, -B07 | WEB-003 / SC-P13-WEB-003-1 | done |
| T13E-B09 | Web-viewer docs (share-link usage, serving via Nginx, security/token note, iOS device-check procedure). | AGT-08 | `docs/` | T13E-B05, -B08 | WEB-001..005 (docs) | done |
| T13E-B10 | **Layering gate:** `check_layering --root pixelart_creator` (client, exit 0) + `--root .` (governs `sync_backend` **and** `web_viewer` — confirm `web_viewer` imports no Qt/`ui`/`data`/`sync_backend`; MAY reuse pure `logic/`; exit 0) + `check_cycles` (`--root pixelart_creator`, `--root sync_backend`, `--root web_viewer` — exit 0); confirm no new Python web-framework dependency in `pyproject.toml`. **AGT-01 slice gate.** | AGT-01 | `scripts/*` (invoke) | T13E-B02..B06 | WEB-004 / SC-P13-WEB-004-1 / Article I | done |
| T13E-B11 | Commit the 13E edit-set (REQ-tagged, gate-green). | AGT-09 | git | T13E-B06..B10 | Article IX | done |

## Cross-cutting / phase-final

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T13-X01 | **Phase-13 final analyze gate:** re-run `sdd-analyze` (C1) across constitution/spec/plan/tasks/traceability/acceptance after all slices land; confirm zero unresolved findings; all `check_layering`/`check_cycles` roots exit 0. | AGT-01 | `specs/phase-13-cross-platform/analyze-report.md` | T13E-B11 | Article VIII / C1 | done |
| T13-X02 | Update `STRUCTURE.md` from PLANNED touch-points to BUILT for the landed Phase-13 modules (`web_viewer/`, `logic/share_token.py`, the `asset_export` bundle extension, the `sync_backend` handshake extension). | AGT-01 | `STRUCTURE.md` | T13E-B11 | Article I map upkeep | done |
| T13-X03 | CHANGELOG entry for Phase 13 (Added: portability harden, portable bundle, VPS artifacts, native installers, web viewer). | AGT-08 | `docs/CHANGELOG.md` | T13E-B11 | Article IX (docs) | todo |

---

## Coverage note (Article X — every REQ maps to ≥ 1 impl + ≥ 1 test/verify task)

- **13A:** DATA-001..004 → T13A-01..04 + T13A-05; DATA-005 → T13A-06; UI-001 → T13A-07 + T13A-10;
  UI-002 → T13A-08 + T13A-09 + T13A-10; BUILD-001 → T13A-12.
- **13B:** DATA-006 → T13B-02 + T13B-04; DATA-007 → T13B-03 + T13B-05; DATA-008 → T13B-03 + T13B-06.
- **13C:** BACKEND-001 → T13C-01 + T13C-04; BACKEND-002 → T13C-02 + T13C-04; BACKEND-003 → T13C-03 + T13C-05.
- **13D:** BUILD-002 → T13D-02; BUILD-003 → T13D-04; BUILD-004 → T13D-03; BUILD-005 → T13D-05.
- **13E:** WEB-001 → T13E-B04/B05/B07; WEB-002 → T13E-B03/B04/B06/B07; WEB-003 → T13E-B04/B08;
  WEB-004 → T13E-P02/P03 + T13E-B10; WEB-005 → T13E-B02/B03/B06.
- **13E asset-generation (baked in, sequenced):** the contract freeze (T13E-P01, done) + the layering rule
  (T13E-P02/P03) precede The Metaprompter's generation of `agt-11-web-client` + the `web-viewer` skill + the
  3 modifies (T13E-G01..G04), which precede the frontend build (T13E-B04+). One owner per task.
