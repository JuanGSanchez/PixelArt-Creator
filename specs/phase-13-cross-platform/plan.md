# Plan — Phase 13: Cross-platform Compatibility

| Field | Value |
| --- | --- |
| Feature | `phase-13-cross-platform` |
| Author | Claude (AGT-01, Architecture) via `sdd-plan` |
| Date | 2026-07-07 |
| Governed by | `constitution.md` (Articles **I**, **II**, III, **IV**, V, VI, **VII**, **VIII**, IX, **X**, **XI**) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for the cross-platform hardening + distribution phase over the approved, clarification-clean spec (23 REQ across 13A–13E). Phase 13 adds **no new editing capability**: it makes the *shipped* platform **provably portable** (13A), **bundleable** (13B), **VPS-deployable** (13C), **installable as native packages** (13D), and **viewable in a mobile browser** (13E). Two invariants are load-bearing and are **NOT relaxed**: Article I (three-layer purity + the two non-three-layer components placed outside it) and Article VII (no `eval`/`exec`; untrusted-input defence). |
| Over spec | `specs/phase-13-cross-platform/spec.md` (23 REQ: `REQ-P13-DATA-001..008`, `REQ-P13-UI-001..002`, `REQ-P13-BUILD-001..005`, `REQ-P13-BACKEND-001..003`, `REQ-P13-WEB-001..005`) + `acceptance.md` (18 Gherkin scenarios) + `traceability.md`. §10 clarifications: 13A–13D **NONE open**; 13E **D1/D2/D3 DECIDED 2026-07-07** and encoded — nothing SUSPENDED. |
| Grounded facts-first in | `docs/subagent-report-the-researcher-acaae022-20260707T093800.md` (Q3 packaging, Q4 VPS ops, Q5 portability, Q2a/Q1b mobile) + `docs/subagent-report-the-researcher-a4c7da21-20260707T111552.md` (13E D1/D2/D3 grounding). **This plan invents no facts**: every tool, timeout, ulimit, and browser-render lever below is a cited fact. |
| Stack source | S8 (fixed) — Python 3.12+, PySide6/Qt6, NumPy, Pillow, `pycrdt`, `websockets==16.0` (all shipped). **13E adds NO new Python runtime dependency (D1).** New packaging/CI/ops tooling (`pyside6-deploy`/PyInstaller, Docker/systemd/Nginx, the CI matrix) is DevOps tooling, not an app runtime dependency (AGT-09). |
| ADRs filed | **ADR-0035** (`web_viewer/` placement — new top-level, outside the three layers, Qt-free; `check_layering --root .` governance; mirrors ADR-0027); **ADR-0036** (13E client↔backend **serialization + signed share-link-token contract** — the frozen wire + token format/validation, stdlib-only, coordinated with AGT-03); **ADR-0037** (portable-bundle format — single-file deterministic archive, zip-slip-defended, capped, `eval`-free; extends `data/asset_export.py`); **ADR-0038** (native-installer/packaging approach — `pyside6-deploy`/PyInstaller per-OS + CI build matrix; credential-gated macOS signing, Article XI). **13C VPS artifacts need NO new ADR** (config/docs only, no backend code change, grounded by Q4 + ADR-0027 — §3.3). Numbered after ADR-0034 (Phase 12). |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-13 spec — the
**Cross-platform Compatibility** phase. It maps every one of the 23 REQ to its layer (three-layer for
`DATA`/`UI`; the non-three-layer `BACKEND`/`BUILD`/`WEB` components exactly as `sync_backend/` sits outside
the layers, ADR-0027), rules the DEP-4/DEP-5 HOW in **ADR-0035–0038**, sets every new numeric bound as a
single-source named constant (Article II, §8), and is decomposed **slice-by-slice / dependency-ordered** in
`tasks.md`. The phase ships in the dependency/risk order **13A → 13B → 13C → 13D → 13E**:

1. **13A — Portability harden** (`data/` + `ui/` + `BUILD`). Fix the five Researcher-Q5 cross-OS pitfalls
   in `data/` (path/`pathlib`, UTF-8, CRLF/LF, case-sensitivity) so a project round-trips **byte-faithfully**
   on any OS; harden the two Q5-flagged GUI risks in `ui/` (font-availability fallback, DPI/scaling); and
   stand up the **Windows + Linux + macOS CI test matrix** (AGT-09) that gates all of it. This is FIRST
   because every later slice depends on portable path/encoding discipline and the matrix.
2. **13B — Portable bundle** (`data/`). Extend the shipped `data/asset_export.py` into a **single-file,
   self-contained, cross-OS project bundle** embedding the referenced CAS blobs, with **path-traversal-
   defended, `eval`-free** import (ADR-0037). Depends on 13A's portable-path + UTF-8 discipline.
3. **13C — VPS artifacts** (`BACKEND`). Ship Docker + systemd + Nginx-TLS/WSS deployment artifacts + docs
   for the **unchanged** `sync_backend/` (Q4 tuning), as **one hosting option** alongside localhost +
   cloud-adapter. **No backend code change; no new ADR** (config/docs only). 13E serves its client over
   this Nginx, so 13C precedes 13E.
4. **13D — Native installers** (`BUILD`). Package the desktop app as Windows exe/MSI, macOS .app/.dmg
   (unsigned/ad-hoc now), Linux AppImage via `pyside6-deploy`/PyInstaller (Q3) + a **CI build matrix**;
   macOS Developer-ID signing/notarization is a **documented, credential-gated, NON-blocking** step
   (Article XI, ADR-0038).
5. **13E — Web companion viewer** (`WEB` — NEW top-level `web_viewer/`). A **vanilla HTML/CSS/JS** browser
   client (D3), served **static by the 13C Nginx** (stdlib `http.server` for local dev only), with project
   data over the **shipped `sync_backend/` `websockets`** substrate — **NO new Python web dependency** (D1),
   gated by a **signed share-link token** (D2). A NEW top-level component **outside the three layers, Qt-free**
   (ADR-0035), with an `eval`-free, untrusted-input, signed-token-validated wire contract (ADR-0036). 13E
   carries the **on-demand asset-generation** step (a new `agt-11-web-client` agent + a `web-viewer` skill),
   sequenced **after** the contract freeze + the layering-rule addition and **before** the frontend build.

**Central portability + security posture (CENTRAL).** The bundle *import* (13B) and every *web-client input*
(13E) are **untrusted-input paths** — defensive, size/shape-capped, path-traversal-defended, **`eval`/`exec`-
free**, reusing the shipped PIO-1 / `asset_export` import defence / `logic/cloud_validation` /
`logic/sync_protocol` discipline (Article VII). **No slice weakens Article I or Article VII.** The 16 ms
`FRAME_BUDGET_MS` is **not touched** by DPI/scaling correctness (Article VI). macOS signing is
credential-gated and non-blocking (Article XI).

## 2. Layer mapping (Article I / Article X §1)

Three-layer work uses `DATA`/`UI`; the three non-three-layer components earn dedicated first-class tags
exactly as Phase-10 gave `sync_backend/` the `BACKEND` tag (ADR-0027):

| REQ | Layer / component | Home | Owner(s) |
| --- | --- | --- | --- |
| DATA-001..005 | `data/` (+ `ui/` for the read/write sites it also touches) | `pixelart_creator/data/*` (path/encoding/line-ending/case audit + widened `path_portability_check`) | AGT-03 (code), AGT-04 (tests) |
| UI-001, UI-002 | `ui/` | `pixelart_creator/ui/` app bootstrap + theming/font seam | AGT-05 (code), AGT-06 (tests), AGT-10 (DPI budget assessment) |
| BUILD-001 | `BUILD` (non-three-layer, DevOps) | `.github/workflows/ci.yml` (3-OS test matrix) | AGT-09 |
| DATA-006..008 | `data/` | `pixelart_creator/data/asset_export.py` (extended) + `logic/constants.py` (caps) | AGT-03 (code), AGT-04 (tests) |
| BACKEND-001..003 | `BACKEND` (non-three-layer; the shipped `sync_backend/`) | `deploy/` artifacts + `docs/` (no backend code change) | AGT-09 (artifacts), AGT-08 (docs), AGT-04 (localhost tests) |
| BUILD-002..005 | `BUILD` (non-three-layer, DevOps) | packaging config + `.github/workflows/ci.yml` (build matrix) | AGT-09 |
| WEB-001..005 | `WEB` (NEW top-level `web_viewer/`, outside the three layers, Qt-free) + a pure `logic/` token seam + a `sync_backend/` handshake extension | `web_viewer/*` (agt-11-web-client + AGT-03 glue), `logic/share_token.py` (AGT-03), `sync_backend/server.py` (AGT-03) | agt-11-web-client (frontend+glue), AGT-03 (Python glue/token/backend), AGT-04 (integration test), AGT-06 (browser/a11y) |

## 3. Per-slice HOW

### 3.1 Slice 13A — Portability harden (Q5)

**`data/` (REQ-P13-DATA-001..005; AGT-03).** A structural audit + fix of every read/write site in `data/`:

- **DATA-001 — `pathlib` everywhere (Q5 path separators/UNC/roots).** Every path the platform reads/writes
  (project files, asset blobs, bundles, exports, config, sidecars) is a `pathlib.Path` object — never a
  hand-concatenated string with a literal separator. The shipped `scripts/path_portability_check.py` gate is
  **hardened + widened** to cover the newly-touched sites; it runs in the 13A CI matrix on all three OSes.
- **DATA-002 — explicit UTF-8 (Q5: Windows does not default to UTF-8).** Every text/JSON `open()` /
  read/write in `data/` passes `encoding="utf-8"` **explicitly**; the fix is at each I/O site (we do **not**
  rely on the `PYTHONUTF8=1` env — that is a mitigation, not the contract). `json.dumps` uses
  `ensure_ascii=False` where a human-readable non-ASCII round-trip matters and is decoded back as UTF-8.
- **DATA-003 — CRLF/LF determinism (Q5).** Any *text* artifact the platform emits (sidecar/JSON/config) is
  written with a fixed OS-independent newline discipline (`open(..., newline="\n")` / write `"\n"`
  explicitly; no platform newline translation), so the bytes do not differ by authoring OS. The binary
  `.pixproj` zlib payload is unaffected (already binary).
- **DATA-004 — case-sensitivity discipline (Q5: Linux strict; PEP 235).** The platform treats every
  filename / asset-reference / CAS-blob path as **case-sensitive** (the strictest rule): CAS keys are
  lowercase-hex content hashes (already case-exact); asset references are looked up by their **exact stored
  case**; no lookup depends on case-folding. Verified on the Linux CI leg with case-distinct assets
  (`Hero.png` vs `hero.png`).
- **DATA-005 — byte-faithful cross-OS round-trip (headline).** Composed of DATA-001..004 + the shipped
  deterministic serialiser: a representative project (multi-layer, animated, tilemapped, non-ASCII names,
  case-distinct assets) saved on OS-A loads model-equal on OS-B and re-saves to a stable payload, for all
  six ordered OS pairs, exercised in the CI matrix.

**`ui/` (REQ-P13-UI-001, UI-002; AGT-05).** Qt-only, in the existing app bootstrap + theming seam:

- **UI-001 — font-availability fallback.** Define the UI font **once, by role, with a resolvable fallback
  chain** (a `QFont` family list / `QFont.insertSubstitutions` seam in the theming layer — not a single
  Windows/macOS-only family per widget), so no label box-glyphs on Linux. Both light/dark themes unaffected.
- **UI-002 — DPI / display-scaling.** Rely on Qt6's automatic high-DPI handling; lay out in
  **device-independent coordinates** and **do NOT manually multiply the device-pixel ratio** (the shipped
  Phase-9 real-size-preview DPR discipline). Verified at 100/150/200% (headless where possible, documented
  manual check otherwise). **The 16 ms `FRAME_BUDGET_MS` is NOT relaxed** — AGT-10 confirms this REQ changes
  no per-frame budget (assessment only; no new perf gate needed — the nearest-neighbour canvas already holds
  budget and is unchanged).

**`BUILD` (REQ-P13-BUILD-001; AGT-09).** Extend the shipped single-OS `ci.yml` `quality-gate` job into a
**Windows + Linux + macOS matrix** (`strategy.matrix.os: [ubuntu-latest, windows-latest, macos-latest]`),
each leg running the FULL suite **headless** (`QT_QPA_PLATFORM=offscreen`; per-OS Qt runtime libs — the
Ubuntu leg keeps the shipped `apt-get` xcb/EGL install; Windows/macOS need no extra system libs for
offscreen) including lint/type/tests/coverage gate + `path_portability_check` + the new cross-OS
round-trip/encoding/case tests. The **concurrency guard + Python-3.12 pin are preserved**. A deliberate
cross-OS regression fails the matrix and blocks merge.

### 3.2 Slice 13B — Portable bundle (extends `data/asset_export.py`; ADR-0037)

The shipped `asset_export.py` already resolves a project's reference set → bundles exactly the referenced
CAS blobs into a **directory** artifact (catalog.json + per-asset sidecars + `blobs/`) with a full
`eval`-free, `resolve()`+containment import defence (Phase-11 REQ-P11-DATA-005). 13B **extends the same
module** with a **single-file, self-contained, portable bundle** (`export_project_bundle` /
`import_project_bundle`):

- **DATA-006 — self-contained export.** The bundle is a **deterministic single-file archive** (stdlib
  `zipfile`, `ZIP_DEFLATED`, fixed metadata for reproducibility; internal paths are **POSIX forward-slash**
  — the portable zip convention, DATA-001/-003) that embeds the `.pixproj` project payload **and** every
  referenced CAS blob (resolved via the shipped `asset_export` reference-set resolution — **no re-implemented
  CAS logic**, Article I) + the catalog. Exporting the same project on Win/Linux/macOS yields functionally
  equivalent, importable bundles. Non-ASCII names are stored as UTF-8 (DATA-002).
- **DATA-007 — cross-OS import round-trip.** A bundle exported on OS-A imports on OS-B to a **model-equal**
  project with all embedded assets present and resolvable, including non-ASCII + case-distinct names,
  honouring the 13A rules; exercised in the CI matrix.
- **DATA-008 — path-traversal-defended, `eval`-free import (Article VII).** Import treats the bundle as
  **untrusted**: every embedded entry's destination is `resolve()`d and constrained within the import target
  (reject `..` / absolute / symlink / zip-slip escape → **write nothing** outside target); total size /
  entry count / per-entry size are capped by named constants (§8); malformed/oversized/unknown-version →
  a defined **user-facing** `AssetExportError` (PIO-1 family) with **no partial-valid write**; the content-
  hash of each blob is verified (tamper defence, reusing `asset_cas`); **zero `eval`/`exec`** on the import
  path (reusing the shipped `asset_catalog_io` `json`-only defence).

No new module (extend `asset_export.py`); no new import edge; stays a pure `data/` module composing
`asset_cas` + `asset_catalog_io` + `project_io`. New caps → `logic/constants.py` (§8).

### 3.3 Slice 13C — VPS artifacts for the shipped `sync_backend/` (Q4; NO backend code change; NO new ADR)

Ship **deployment artifacts + docs** so the **unchanged** `sync_backend/` asyncio-`websockets` relay runs on
a generic VPS. These are ops config (not Python product code) under a repo-top-level `deploy/` directory
(unscanned by `check_layering` — no layer rule → skipped) + docs under `docs/`. **AGT-09** owns the
artifacts; **AGT-08** the docs; the backend source is untouched (so no new ADR — the placement/architecture
was already ruled by ADR-0027, and Q4 gives the exact recipe):

- **BACKEND-001 — Docker image + systemd unit.** A `deploy/Dockerfile` and a `deploy/pixelart-sync.service`
  systemd unit that launch the shipped `sync_backend/` bound to **`0.0.0.0`** (not localhost) with the
  file-descriptor limit **≥ 65535** (Docker `--ulimit nofile=65535:65535` / systemd `LimitNOFILE=65535`),
  documenting the **~10K-connections/process** ceiling (Q4). Acceptance is proven **over
  localhost/loopback** (a client reproduces the shipped multi-client convergence, REQ-P10-BACKEND-001) — **no
  live external server required**.
- **BACKEND-002 — Nginx TLS/WSS reverse-proxy config.** A `deploy/nginx-sync.conf` that terminates **TLS**
  and proxies **WSS→WS**, forwarding the WebSocket **`Upgrade`/`Connection`** headers and raising
  **`proxy_read_timeout`** well above the 60 s default (e.g. `86400`) so idle WS connections are not killed
  (Q4); the backend serves plain WS behind the TLS-terminating proxy. Proven over **localhost** with a
  loopback/self-signed certificate sustaining an idle connection **past 60 s** — no public cert, no live
  server.
- **BACKEND-003 — one option, not a forced default.** Docs present **localhost + cloud-adapter + VPS** as
  co-equal hosting options; adopting 13C changes **no default** and requires **no** code change; a user who
  ignores 13C sees identical behaviour.

**Test feasibility note (AGT-04/AGT-09):** the Docker/systemd/Nginx localhost tests require a container /
nginx binary that a headless GitHub runner may lack, so they are marked **`integration`** (the shipped
pyproject marker, deselected in the default cross-OS gate) and/or run in a dedicated 13C CI job; the
default matrix stays green cross-OS. The `test_hosting_default_unchanged` behavioural test carries no
marker and runs in the default gate.

### 3.4 Slice 13D — Native installers (Q3; ADR-0038)

**AGT-09** packaging, `BUILD` component:

- **BUILD-002 (Windows exe/MSI), BUILD-004 (Linux AppImage).** Package via **`pyside6-deploy`** (Nuitka-based,
  Qt-recommended) as the primary tool, with **PyInstaller** as the documented fallback (Q3); the Qt
  platform/image-format/style plugins are **bundled** (the deploy tools handle this). Committed, reproducible
  packaging config (`pysidedeploy.spec` per target). Each CI leg smoke-launches the artifact on a clean env.
- **BUILD-003 (macOS .app/.dmg).** Package the .app in a .dmg (unsigned/ad-hoc now, Gatekeeper-bypass
  documented). **Developer-ID signing + notarization (`notarytool`) + hardened runtime + stapling** is a
  **documented, credential-gated step** that runs **only** when an Apple Developer ID is supplied — **NOT a
  blocking acceptance criterion** (Article XI); no credential is committed.
- **BUILD-005 (CI build matrix).** A CI build matrix (extending the 13A test matrix into a build matrix on a
  build/tag trigger) builds all three distributables on their OS legs and publishes them as downloadable
  artifacts; a per-leg build failure fails that leg visibly; the macOS signing step is the credential-gated,
  non-blocking addition.

ADR-0038 records the tool selection + per-OS targets + the credential-gated signing posture.

### 3.5 Slice 13E — Web companion viewer (D1/D2/D3; ADR-0035 + ADR-0036)

The frozen architecture (encoded from the USER's D1/D2/D3 decisions):

- **Placement (WEB-004; ADR-0035).** `web_viewer/` is a **NEW top-level package** (sibling of
  `pixelart_creator/` and `sync_backend/`), **outside the three desktop layers**, **headless**, and **MUST
  NOT import Qt or `ui/`** — mirroring `sync_backend/` (ADR-0027). It contains: `web_viewer/static/`
  (vanilla HTML/CSS/JS client, no build step — D3), `web_viewer/dev_server.py` (a stdlib `http.server`
  static server for **LOCAL DEV ONLY** — D1; production serving is the 13C Nginx), thin Qt-free
  serving/token glue, `web_viewer/__init__.py`, and `web_viewer/tests/`. It **MAY reuse pure, Qt-free
  `logic/`** (the token + protocol seams) and introduces **NO new Python web-framework dependency** (D1).
  The three desktop layers do not import `web_viewer/`. Governed by a new `check_layering` `web_viewer` rule
  (§7).
- **Serving + data (WEB-001, WEB-003; D1/D3).** The vanilla client is served as **static files by the 13C
  Nginx** (stdlib `http.server` for dev); project data flows over the **shipped `sync_backend/`
  `websockets`** relay — **dependency manifest unchanged aside from the existing `websockets`**. The client
  renders the shared project **pixel-faithfully** via the Canvas API with `image-rendering: pixelated` +
  `ctx.imageSmoothingEnabled = false` + **integer scale factors** (native pixel resolution in the canvas
  `width`/`height` attributes, scaled display size in CSS — the grounded a4c7da21 recipe). Works on **iOS
  Safari + Android Chrome** (Q2a; vanilla no-build-step → broad support); **iOS Safari is a real-device
  verification concern** (documented device check).
- **Light interaction only (WEB-002; D2).** The client exposes exactly **layer-visibility toggle, frame
  navigation, and pan/zoom** and **no editing** (no pixel writes, emits no mutation message). The desktop
  stays the sole editor. Because the share token is **view-scoped**, the backend **rejects any mutation
  message** on a view-scoped connection.
- **Signed share-link token + untrusted input (WEB-005; D2; ADR-0036).** Access is gated by a **per-shared-
  project short-lived signed share-link token** presented over HTTPS. The token is **stdlib-only** — an
  HMAC-SHA256-signed compact token (base64url `header.payload.sig`) minted + verified by a **NEW pure
  `logic/share_token.py`** (zero Qt, `hmac`/`hashlib`/`base64`/`json` only — **no new dependency**, no
  `eval`/`exec`), whose payload carries `iss`/`aud`/`project_id` (scope)/`exp`/`iat`/`jti`. `sync_backend/`
  is **extended** (not re-authored) to **validate signature (constant-time `hmac.compare_digest`) + expiry
  + issuer/audience** and **scope to exactly the named project** on the viewer's WS connect (the `websockets`
  `process_request` handshake hook — the grounded a4c7da21/Q3 pattern), rejecting expired/wrong-aud/bad-sig
  tokens (serve **no** data) and cross-project access. The signing secret is an **operator-provided secret
  (env/config), never committed** (Article VII §3). All web-client input is schema/size-validated reusing
  the shipped `eval`-free `logic/cloud_validation.py` / `logic/sync_protocol.py` caps; **zero `eval`/`exec`**
  on any web-input path. **`logic/share_token.py` is a pure `logic/` leaf** imported by both `sync_backend/`
  and the `web_viewer/` glue (the `sync_protocol` single-source precedent).

**On-demand asset generation (baked into `tasks.md`, sequenced correctly).** Per the approved Recommender
plan + the `[[generate-assets-on-demand]]` directive, 13E introduces two NEW Claude assets, generated by
**The Metaprompter (AGT-M2)** **AFTER** the contract freeze (ADR-0035 + ADR-0036) and the `check_layering`
`web_viewer` rule land, and **BEFORE** the frontend is built: (1) a new domain agent **`agt-11-web-client`**
(owns `web_viewer/` frontend + serving glue; **NO Qt / NO domain logic**), and (2) a **`web-viewer` skill**
(the vanilla pixel-canvas + WS-client + signed-token client pattern). The generation step also **modifies**
`.claude/agent-manifest.md` (+ the AGT-11 row + skill row) and `.github/workflows/ci.yml` (add
`check_layering --root .` coverage of `web_viewer/`, a Node JS-unit step for the vanilla client, and
collection of the Python web integration test). See `tasks.md` §13E.

## 4. Stack grounding (facts-first; The Researcher LANDED)

Every stack/tool choice is a cited Researcher fact — nothing invented (PL13-D1 Branch B: no further research
required; both reports have LANDED):

| Decision | Grounding |
| --- | --- |
| `pathlib` / explicit UTF-8 / LF discipline / case-sensitive coding | acaae022 Q5 (path separators/UNC; Windows ≠ UTF-8 default; CRLF/LF; Linux case-sensitive + PEP 235) |
| Single-file zip bundle, deterministic, POSIX-internal paths | Q5 (portability) + shipped `asset_export`/`asset_catalog_io` import defence (Phase-11) |
| Docker/systemd, bind `0.0.0.0`, `LimitNOFILE`≥65535, Nginx `Upgrade`/`Connection` proxy + `proxy_read_timeout`≫60 s, ~10K conns/process | acaae022 Q4 |
| `pyside6-deploy` (Nuitka, Qt-recommended) + PyInstaller fallback; Qt plugins bundled; Win exe/MSI, macOS .app/.dmg, Linux AppImage; macOS Developer-ID signing+notarization+hardened-runtime+stapling mandatory for store dist (credential-gated) | acaae022 Q3 |
| Browser viewer over the existing `websockets` backend works on iOS Safari + Android Chrome (no native iOS PySide6 path) | acaae022 Q2a + Q1b |
| D1 reuse existing stack / NO new dependency (static via Nginx; stdlib `http.server` dev; unsupported to serve static from `websockets` in-process → reverse proxy is the vendor-suggested path) | a4c7da21 D1 |
| D2 signed share-link bearer token (HTTPS, short expiry, validate sig+`iss`+`aud`, scope; not full OAuth) | a4c7da21 D2 |
| D3 vanilla HTML/CSS/JS; Canvas `image-rendering: pixelated` + `imageSmoothingEnabled=false` + integer scale (~95% support incl. iOS Safari + Android Chrome; device-test advised) | a4c7da21 D3 + pixel-render feasibility |

## 5. Article VII posture (untrusted input; no `eval`/`exec`) — INVARIANT, NOT relaxed

- **Bundle import (13B, DATA-008):** `resolve()`+containment against zip-slip, size/entry caps, content-hash
  verify, `json`-only parse, defined user-facing error, no partial write — reuses the shipped
  `asset_catalog_io` / `asset_export` defence. **Zero `eval`/`exec`.**
- **Web input (13E, WEB-005):** signed-token validate (sig+exp+iss+aud+scope, constant-time compare) before
  any data is served; every inbound frame schema/size-capped via the shipped `logic/cloud_validation.py` /
  `logic/sync_protocol.py`; view-scoped tokens cannot mutate. **Zero `eval`/`exec`** on any web-input path;
  the signing secret is never committed.
- A **source audit** (grep for `eval(`/`exec(` on the bundle-import + web-input paths) is an explicit
  acceptance step (SC-P13-DATA-008-2, SC-P13-WEB-005-1) — no new gate needed beyond the existing review +
  `path_portability_check`.

## 6. Article VI posture (render budget) — NOT touched

REQ-P13-UI-002 (DPI/scaling) changes **no** per-frame budget: the nearest-neighbour canvas is unchanged and
already holds 16 ms; the fix is "let Qt apply the DPR, do not double-scale." AGT-10 performs a **budget
assessment only** (confirming no double-scale / no new per-frame cost) — **no new `perf_profile` gate is
added** this phase, and `FRAME_BUDGET_MS = 16` is never relaxed.

## 7. Layering (Article I) — the new `web_viewer` rule (ADR-0035)

`scripts/check_layering.py` gains a **`WEB_PKG = "web_viewer"`** rule mirroring the shipped
`BACKEND_PKG = "sync_backend"` rule (owned by AGT-03/AGT-09 per the task; specified in ADR-0035):

- **`web_viewer/` (scanned via `--root .`, `parts[0] == "web_viewer"`):** must **NOT** import Qt,
  `pixelart_creator.ui`, `pixelart_creator.data`, or `sync_backend` — it stays headless, serves only static
  assets + thin Qt-free glue, and reaches the backend over the wire (WS), never by Python import; it **MAY**
  reuse pure `pixelart_creator.logic` (the `share_token` + protocol seams). Mirrors the backend rule.
- **Reciprocal client rule:** `logic/`, `data/`, and `ui/` may **NOT** import `web_viewer` (added to each
  layer's forbidden set, exactly as `sync_backend` is).
- **Peer decoupling:** `sync_backend` may **NOT** import `web_viewer` (added to the backend's forbidden set)
  — the two non-three-layer deployables communicate over the wire, not by import.
- **Invocation (CI, AGT-09):** the shipped twin invocation is unchanged in shape — `--root pixelart_creator`
  (client three layers) and `--root .` (governs `sync_backend/` **and now** `web_viewer/` via
  `parts[0]`). `check_cycles` runs a third time — `--root web_viewer` — once the package lands (the check is
  generic over `--root`; no code change). Until `web_viewer/` lands the rule is **dormant-ready** (whole-repo
  `--root .` scans the same governed modules and stays exit 0).
- **Baseline (this session, no code changed):** `check_layering --root pixelart_creator` exit 0 (178
  modules); `--root .` exit 0 (3 modules); `check_cycles --root pixelart_creator` exit 0 (179);
  `--root sync_backend` exit 0 (3). All green — the rules gate the new code when it arrives (Article I §4).

## 8. Numerics (Article II) — single-source named constants

Every new **app** numeric bound is a named constant in `logic/constants.py` (with a source citation),
imported by name — no magic literal at a call site. Every new **ops** numeric lives in its artifact/config
file (not app code). Concrete values are HOW; AGT-03 sets them with citations:

| Constant (home) | Purpose | Grounding |
| --- | --- | --- |
| `MAX_BUNDLE_BYTES` (`logic/constants.py`) | Total portable-bundle size cap (import defence, DATA-008) | Article VII; mirrors `MAX_BLOB_BYTES` |
| `MAX_BUNDLE_ENTRIES` (`logic/constants.py`) | Max embedded entries (zip-bomb / entry-count cap) | Article VII |
| `MAX_BUNDLE_ENTRY_BYTES` (`logic/constants.py`) | Per-entry uncompressed size cap (zip-bomb defence) | Article VII |
| `SHARE_TOKEN_MAX_TTL_S` (`logic/constants.py`) | Max share-token lifetime (short-lived; expiry validation, WEB-005) | a4c7da21 D2 (short-lived tokens) |
| *(ops)* `LimitNOFILE=65535` / `--ulimit nofile=65535:65535` (`deploy/*.service`, `deploy/Dockerfile`) | FD limit floor | Q4 |
| *(ops)* `proxy_read_timeout 86400` (`deploy/nginx-sync.conf`) | Keep idle WS alive past 60 s | Q4 |

Web-input size caps **reuse** the shipped `MAX_CRDT_UPDATE_BYTES` / `sync_protocol` caps (no new constant —
the viewer is a consumer of the same relay).

## 9. Testing (Article IV) + gates (Article VIII)

- The **cross-OS CI matrix (BUILD-001)** is the phase's verification spine: the round-trip / encoding /
  case / bundle / portability REQs are **gated on all three OS legs**; a per-OS regression blocks merge.
- Per-REQ tests (one per acceptance criterion) follow the traceability matrix: `tests/data/*` (AGT-04) for
  13A/13B; `tests/ui/*` (AGT-06) for UI-001/-002; `tests/backend/*` (AGT-04, `integration`-marked where a
  container/nginx is needed) for 13C; the CI build/test matrix (AGT-09) for BUILD-*; `web_viewer/tests/*`
  (AGT-04 Python integration; agt-11-web-client + AGT-06 for the JS/browser + a11y) for WEB-*.
- **Coverage gate ≥90 line / ≥80 branch** is preserved; the new pure `logic/share_token.py` +
  `data/asset_export.py` extension are unit-covered.
- **Gate (Article VIII):** `sdd-analyze` (C1) must return zero unresolved findings before ANY implement
  dispatch. **13A implementation is UNBLOCKED the moment C1 passes** (this plan + tasks + the green
  baseline scripts satisfy the pre-implement gate for 13A; 13E build additionally waits on the contract
  freeze + asset generation sequenced in `tasks.md`).

## 10. DEP items carried from spec §8 (resolved here)

- **DEP-4 (bundle format + portability HOW) → ADR-0037 + §3.1/§3.2.** Single-file deterministic zip;
  `resolve()`+containment; explicit UTF-8 + LF + `pathlib` + case-sensitive across `data/`; font-fallback +
  no-DPR-multiply in `ui/`.
- **DEP-5 (13E HOW, UNBLOCKED) → ADR-0035 + ADR-0036 + §3.5.** `web_viewer/` placement + the Nginx static
  location (extending 13C) + the stdlib HMAC signed-share-link-token format & validation + the vanilla JS
  Canvas pixel-faithful renderer + the iOS-Safari device check. **No new web dependency (D1).**
- **DEP-1/DEP-2/DEP-3 (AGT-09 CI matrix / packaging / VPS artifacts) → §3.1/§3.3/§3.4 + ADR-0038.**

## 11. Risks

- **Cross-OS CI cost/flake.** Three OS legs ~triple the runner minutes; the shipped concurrency guard +
  per-test timeout + `-n auto` mitigate wall-time. macOS/Windows runner variance is the main flake risk
  (AGT-09 tunes the job cap per leg).
- **13C container/nginx tests need infra the default runner lacks** — mitigated by the `integration` marker
  + a dedicated 13C job; the artifacts + localhost procedure are the primary acceptance.
- **macOS notarization is credential-blocked** — mitigated by the Article-XI credential-gated, non-blocking
  posture (ship unsigned/ad-hoc now).
- **iOS-Safari pixel-render behaviour** is ~95% supported but a4c7da21 flags a device test — WEB-003 makes
  the iOS device check an explicit (documented) acceptance step, not an emulator-only claim.
- **Asset-generation ordering.** The `agt-11-web-client` agent + `web-viewer` skill MUST be generated
  **after** the ADR-0035/0036 contract freeze + the `check_layering` rule and **before** the frontend build
  — enforced by the `tasks.md` §13E dependency order (T13E-P* before T13E-G* before T13E-B*).

## 12. Sources

- Spec `specs/phase-13-cross-platform/{spec,acceptance,traceability}.md` (23 REQ, 18 Gherkin).
- The Researcher `docs/subagent-report-the-researcher-acaae022-20260707T093800.md` (Q2a/Q1b/Q3/Q4/Q5) +
  `docs/subagent-report-the-researcher-a4c7da21-20260707T111552.md` (D1/D2/D3 + pixel-render feasibility).
- `constitution.md` (Articles I/II/IV/VI/VII/VIII/X/XI); ADR-0027 (`sync_backend/` placement + layering
  rule precedent); shipped `data/asset_export.py`, `data/asset_catalog_io.py`, `data/asset_cas.py`,
  `logic/cloud_validation.py`, `logic/sync_protocol.py`, `scripts/{check_layering,check_cycles,
  path_portability_check}.py`, `.github/workflows/ci.yml`, `pyproject.toml`, `STRUCTURE.md`.
- ADRs authored this phase: `docs/adr/0035`, `0036`, `0037`, `0038`.
</content>
