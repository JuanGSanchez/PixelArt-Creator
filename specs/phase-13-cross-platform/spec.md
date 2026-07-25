# Specification — Phase 13: Cross-platform Compatibility

| Field | Value |
| --- | --- |
| Feature | `phase-13-cross-platform` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-07 |
| Governed by | `constitution.md` (Articles **I**, **II**, IV, VI, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION — COMPLETED (clarification-clean).** The original 12-phase roadmap is **SHIPPED**; Phase 13 is a **cross-platform hardening + distribution phase**, grounded in The Researcher's cited facts (`docs/subagent-report-the-researcher-acaae022-20260707T093800.md`, and the D1/D2/D3 grounding research `a4c7da21`) and the shipped architecture. **All 23 requirements across slices 13A–13E are now FULLY specified and clarification-clean** (measurable REQs, full acceptance + Gherkin + trace). **Slice 13E (web companion viewer) was PARTIAL by design** — its three sub-decisions (D1 web-serving stack / dependency; D2 viewer auth model; D3 vanilla client vs SPA) were `[NEEDS CLARIFICATION]`; the **USER DECIDED all three on 2026-07-07** (D1 = reuse existing stack, NO new dependency; D2 = signed share-link token; D3 = vanilla HTML/CSS/JS). Those decisions are now recorded in §10 as **decided** and encoded into REQ-P13-WEB-001..005, whose acceptance is now complete and measurable. **No `[NEEDS CLARIFICATION]` marker remains.** |
| REQ-ID range | `REQ-P13-DATA-001..008`, `REQ-P13-UI-001..002`, `REQ-P13-BUILD-001..005`, `REQ-P13-BACKEND-001..003`, `REQ-P13-WEB-001..005` — **23 requirements.** Layer tags follow the shipped taxonomy: three-layer work uses `DATA`/`UI`; the **non-three-layer components** use dedicated first-class tags exactly as Phase 10 introduced `REQ-P10-BACKEND-*` for `sync_backend/` (ADR-0027, Article X §1): **`BACKEND`** = VPS artifacts for the shipped `sync_backend/` (13C); **`BUILD`** = the cross-OS CI matrix + native-installer/packaging pipeline (13D + the 13A CI matrix), owned by AGT-09 outside the three layers; **`WEB`** = the NEW top-level `web_viewer/` component (13E), outside the three layers, headless, **zero Qt** — mirroring how `sync_backend/` earned its own tag. |
| Layer scope | `pixelart_creator/data/` (portable path handling, UTF-8 encoding, line-ending determinism, case-sensitivity discipline, the cross-OS `.pixproj` round-trip, and the portable bundle extending the shipped `data/asset_export.py`) + `pixelart_creator/ui/` (font-availability fallback, DPI/scaling correctness) + the **non-three-layer** `sync_backend/` deployment artifacts (13C, `BACKEND`), the **build/packaging + CI matrix** (13A CI + 13D installers, `BUILD`), and the **new top-level `web_viewer/`** (13E, `WEB`). **Article I layering and Article VII (no `eval`/`exec`) are invariants and are NOT relaxed** — the bundle import (13B) and any web input handling (13E) are untrusted-input paths. |
| Binds to (upstream, **shipped** — REUSED / HARDENED) | Phase 1/4/6/9 `data/project_io.py` (**PIO-1** — the defensive `.pixproj` serialiser: `pathlib`, zlib+base64, versioned, **no `eval`/`exec`** — the artifact whose cross-OS byte-faithfulness 13A hardens); Phase 11 `data/asset_export.py` (**the bundle precedent** — "resolve a project's reference set → bundle exactly the referenced CAS blobs (self-contained); import defence", Phase-11 `REQ-P11-DATA-005`) + `data/asset_cas.py` (content-addressable store) — 13B **extends** these; Phase 7/8/9 `scripts/path_portability_check` (the shipped portable-path gate 13A hardens + widens); Phase 10 **`sync_backend/`** (the shipped asyncio-`websockets` relay OUTSIDE the three layers, ADR-0027 — 13C ships *deployment artifacts* for it; 13E *serves* the viewer over it) + `logic/sync_protocol.py` / `logic/cloud_validation.py` (the shared, `eval`-free untrusted-input validators); `.github/workflows/ci.yml` (the shipped headless-Qt CI harness 13A/13D extend to a Win/Linux/macOS matrix); `logic/constants.py` (Article II single-source numerics). Phase 13 **hardens/extends/packages** these; it re-authors none of them (Article I). |
| Depends on (external) | **The Researcher — LANDED** at `docs/subagent-report-the-researcher-acaae022-20260707T093800.md` (Qt/PySide6 6.10 anchor). Grounds every resolved slice: Q5 (cross-OS file portability — case-sensitivity, path separators, UTF-8, Windows file-locking, CRLF/LF) → 13A; Q3 (`pyside6-deploy`/Nuitka + PyInstaller desktop packaging; Qt-plugin bundling; **macOS Developer-ID signing + notarization + hardened runtime + stapling as a hard, non-optional store-distribution requirement**) → 13D; Q4 (VPS websocket ops — Docker/systemd + Nginx TLS/WSS `Upgrade` proxying + `proxy_read_timeout` raised from the 60 s default, bind `0.0.0.0`, `LimitNOFILE`/`--ulimit nofile=65535`, ~10K conns/process) → 13C; Q2a (browser WS viewer works on **iOS Safari + Android Chrome**, FastAPI/BFF patterns) + Q1b (**no supported native iOS PySide6 deployment in 2026** — the reason a browser viewer is the platform-neutral mobile-access path) → 13E. **13E D1/D2/D3 grounding research `a4c7da21` has LANDED and the USER has DECIDED all three** (§10) — 13E's technical requirements are now frozen. |
| SDD phase | `specify` + `clarify` **COMPLETE for all of 13A–13E** (no requirement underspecified, no product-direction choice open, no target ungrounded → A2-D2: nothing left to SUSPEND). 13E's D1/D2/D3 have been **adjudicated by the USER (2026-07-07)** and encoded into REQ-P13-WEB-001..005; their acceptance is now complete. **`sdd-plan` (AGT-01) is UNBLOCKED for the WHOLE phase (all 23 REQs).** |

---

## 1. Purpose (WHY)

The platform ships twelve complete phases — a full PySide6/Qt6 desktop pixel-art creator with an 8K
canvas, layers, animation, tilemaps, export, automation, visual aids, cloud collaboration (the
`sync_backend/`), team/asset management, and a performance-hardened compositor. What it has **not** yet
been made **provably portable and distributable** is: (a) that a project authored on one OS opens
**byte-faithfully** on any other; (b) that a project + its assets can be handed to a collaborator on a
different OS as a **self-contained bundle**; (c) that the shipped `sync_backend/` can be **deployed to a
generic VPS**; (d) that the desktop app ships as **native installers** for Windows/macOS/Linux; and (e)
that a **shared project can be viewed on a phone browser** — the mobile-access path that side-steps the
fact (Researcher Q1b) that there is **no supported native iOS PySide6 deployment in 2026**.

Phase 13 — **Cross-platform Compatibility** — delivers a–e in full.
It is grounded **facts-first** in The Researcher's report: every portability pitfall (Q5), every
packaging fact (Q3), every VPS operational number (Q4), and the browser-viewer feasibility (Q2a) is a
cited fact, not an invention. Phase 13 introduces **no new editing capability** — the desktop stays the
editor; this phase makes the *existing* platform correct across OSes, packageable, deployable, and
viewable on mobile browsers.

**Two constitution invariants are load-bearing this phase and are NOT relaxed.** **Article I** (three-layer
purity): the two new *non-three-layer* components introduced/extended here — the `BUILD` packaging
pipeline and the `WEB` `web_viewer/` — sit **OUTSIDE** `ui/`/`logic/`/`data/` exactly as `sync_backend/`
does (ADR-0027 precedent); `web_viewer/` **MUST NOT import Qt**. **Article VII** (no `eval`/`exec`): the
portable-bundle *import* (13B) and any *web input handling* (13E) are **untrusted-input paths** — they
reuse the shipped defensive, `eval`-free discipline (PIO-1, `data/asset_export.py` import defence,
`logic/cloud_validation.py`) and add path-traversal defence; **neither introduces `eval`/`exec`**.

**13E is now complete at the requirement level.** Three genuinely acceptance-changing sub-decisions for
the web viewer were originally SUSPENDED under the A2-D2 ambiguity gate — the web-serving stack / whether
it adds a dependency (D1), the viewer auth model (D2), and vanilla-client-vs-SPA (D3). The **USER has now
DECIDED all three (2026-07-07)**, grounded by research `a4c7da21`: **D1 = reuse the existing stack with
NO new dependency** (static client served by the already-planned Nginx from 13C; project data over the
existing `sync_backend/` `websockets`; a stdlib `http.server` acceptable for local dev only — no new
Python web framework); **D2 = a per-shared-project short-lived signed share-link token** (the viewer
presents a signed bearer token over HTTPS; the backend validates signature + expiry + issuer/audience and
scopes access to that one shared project; not full OAuth, no login flow); **D3 = vanilla HTML/CSS/JS**
(no build step, no framework/SPA; the Canvas API renders the pixel art faithfully with
`image-rendering: pixelated` + `imageSmoothingEnabled = false` + integer scaling; must work on iOS Safari
+ Android Chrome). These decisions are recorded in §10 as **decided** and encoded into
REQ-P13-WEB-001..005, whose acceptance is now complete and measurable. No answer is invented; the
resolved decisions are grounded product direction (a category-1 source per A2-D2). **13E's technical
requirements are now frozen** and no `[NEEDS CLARIFICATION]` marker remains.

## 2. Scope

**In scope now (WHAT) — FULLY specified, clarification-clean (13A–13D):**

- **Slice 13A — PORTABILITY HARDEN (`data/` + `ui/` + `BUILD` CI matrix).** Cross-OS project round-trip
  correctness across Windows/Linux/macOS. Fix the Researcher-Q5 portability pitfalls: filename
  **case-sensitivity** (code case-sensitively; Linux is strict), **UTF-8 filesystem encoding** (don't
  assume it on Windows), **CRLF/LF** line-ending determinism, **path handling via `pathlib`** (no
  separator/UNC assumptions), plus the two flagged GUI risks — **font-availability fallback** and
  **DPI/scaling** correctness. Headline acceptance: a project authored on any OS opens **byte-faithfully**
  on any other, and a **Win/Linux/macOS CI matrix runs the suite green**. REQ-P13-DATA-001..005,
  REQ-P13-UI-001..002, REQ-P13-BUILD-001.
- **Slice 13B — PORTABLE BUNDLE (`data/`).** A self-contained cross-platform **project bundle** that
  **embeds the referenced CAS assets**, extending the shipped `data/asset_export.py` (Phase-11
  `REQ-P11-DATA-005`): export on one OS, import on another, self-contained, **path-traversal-defended**
  (Article VII, `resolve()` + containment, `eval`-free). REQ-P13-DATA-006..008.
- **Slice 13C — VPS ARTIFACTS (`BACKEND` — the shipped `sync_backend/`).** Deployment
  artifacts + docs so the **existing** asyncio-`websockets` `sync_backend/` can run on a generic VPS: a
  **Docker image**, a **systemd unit**, and an **Nginx TLS/WSS reverse-proxy** config with the Q4
  timeout/ulimit tuning. Offered as **ONE** hosting option **alongside localhost + the cloud-adapter — no
  forced default**. Acceptance is about **deployability + a documented, testable-over-localhost run**, NOT
  a live external server. REQ-P13-BACKEND-001..003.
- **Slice 13D — NATIVE INSTALLERS (`BUILD`).** Packaged desktop distributables — Windows **exe/MSI**,
  macOS **.app/.dmg**, Linux **AppImage** — via `pyside6-deploy`/PyInstaller (Q3) + a **CI build matrix**.
  macOS **signing/notarization** (which Q3 confirms is a *hard, non-optional* store-distribution
  requirement needing the user's **Apple Developer ID**) is shipped as a **documented, credential-gated
  step**: the pipeline + an **unsigned/ad-hoc** mac artifact ship now; signing/notarization is **NOT a
  blocking acceptance criterion**. REQ-P13-BUILD-002..005.

**In scope now (WHAT) — FULLY specified, clarification-clean (13E, D1/D2/D3 DECIDED 2026-07-07):**

- **Slice 13E — WEB COMPANION VIEWER (`WEB` — new top-level `web_viewer/`).** A lightweight **vanilla
  HTML/CSS/JS** browser client (no build step, no framework/SPA — D3; works on **iOS Safari + Android
  Chrome**, Q2a) served as **static files by the already-planned Nginx** (from 13C's VPS artifacts; a
  stdlib `http.server` is acceptable for **local dev only**), with project data flowing over the
  **shipped `sync_backend/` `websockets` substrate** — **NO new Python web-framework dependency** (D1).
  Access to a shared project is gated by a **per-project short-lived signed share-link token** (the
  backend validates signature + expiry + issuer/audience and scopes to that project — D2). It is for
  **VIEWING + light interaction** of **SHARED** projects — **NOT full editing** (the desktop stays the
  editor). A **NEW top-level `web_viewer/` component OUTSIDE the three desktop layers, headless, that MUST
  NOT import Qt** (the `sync_backend/` precedent), and **MUST NOT `eval`/`exec` untrusted input**
  (Article VII). REQ-P13-WEB-001..005 — **all now fully specced + measurable.** See §2b.

### 2b. 13E — D1/D2/D3 DECIDED (A2-D2 ambiguity gate closed)

Per the A2-D2 gate, three underspecified sub-decisions were SUSPENDED with the exact question rather than
guessed. The **USER DECIDED all three on 2026-07-07** (grounded by research `a4c7da21`); the resolved
decisions are recorded as a category-1 source (§10) and encoded into the WEB REQs. 13E is now split
cleanly into fully-specced aspects:

| Aspect of 13E | Status | Where |
| --- | --- | --- |
| **Viewing a shared project in a browser** (read-mostly, faithful pixel rendering) | **SPECCED** | REQ-P13-WEB-001 |
| **Light interaction, NOT full editing** (view layers/frames, pan/zoom; desktop stays editor) | **SPECCED** | REQ-P13-WEB-002 |
| **Cross-browser** (iOS Safari + Android Chrome) | **SPECCED** | REQ-P13-WEB-003 |
| **New top-level `web_viewer/`, headless, MUST NOT import Qt, OUTSIDE the 3 layers** | **SPECCED** (Article I invariant) | REQ-P13-WEB-004 |
| **Served over `sync_backend/`; signed-token-gated; untrusted web input, no `eval`/`exec`** (Article VII) | **SPECCED** (invariant) | REQ-P13-WEB-005 |
| **D1 — web-serving stack / dependency** → **REUSE EXISTING STACK, NO NEW DEPENDENCY** (static via Nginx / stdlib-dev; data over existing `websockets`) | **DECIDED 2026-07-07** | §10 |
| **D2 — viewer auth model** → **SIGNED SHARE-LINK TOKEN** (validate signature + expiry + issuer/audience; scope to the shared project) | **DECIDED 2026-07-07** | §10 |
| **D3 — vanilla client vs SPA** → **VANILLA HTML/CSS/JS** (no build step; Canvas `pixelated` faithful render) | **DECIDED 2026-07-07** | §10 |

Every WEB REQ now states a complete, measurable contract encoding the D1/D2/D3 decisions; none is left
partial.

## 3. Story map & user stories

Backbone activity → stories, each tagged with a kebab-case feature label + roadmap phase (§3.2). The
"users" are the **artist/collaborator** working across OSes and devices, the **operator** deploying the
backend, and the **maintainer** keeping the build green. Stories for 13A–13D have **no open
clarification**; the 13E story is now clarification-clean (D1/D2/D3 decided).

### 3.1 User stories

- **US-1 (Artist / portable projects).** As an artist, I want a project I authored on one OS to open
  **byte-faithfully** on any other OS, so a Windows↔Linux↔macOS handoff never corrupts or reinterprets my
  work. → REQ-P13-DATA-001..005, REQ-P13-UI-001, REQ-P13-UI-002 · `portability-harden` · P13
- **US-2 (Maintainer / cross-OS CI).** As a maintainer, I want the full test suite to run **green on a
  Windows + Linux + macOS CI matrix**, so a portability regression can never merge unseen. →
  REQ-P13-BUILD-001 · `ci-matrix` · P13
- **US-3 (Collaborator / self-contained bundle).** As a collaborator, I want to export a project + its
  referenced assets as **one self-contained bundle** on my OS and have a teammate import it on a different
  OS with **no missing/renamed files and no path-traversal risk**. → REQ-P13-DATA-006..008 ·
  `portable-bundle` · P13
- **US-4 (Operator / VPS backend).** As an operator, I want **deployment artifacts** (Docker image,
  systemd unit, Nginx TLS/WSS config with correct timeouts/ulimits) so I can run the **existing**
  sync backend on a generic VPS as **one** hosting option — without it being forced as the default. →
  REQ-P13-BACKEND-001..003 · `vps-artifacts` · P13
- **US-5 (Artist / native install).** As an artist, I want to install the app from a **native installer**
  for my OS (Windows exe/MSI, macOS .app/.dmg, Linux AppImage) built by CI — with macOS
  signing/notarization available as a documented, credential-gated step (not a blocker). →
  REQ-P13-BUILD-002..005 · `native-installers` · P13
- **US-6 (Collaborator / mobile viewing).** As a collaborator away from my desktop, I want to open a
  **signed share link** and **view and lightly interact with** a **shared** project in my **phone
  browser** (iOS Safari / Android Chrome), read-mostly with faithful pixel rendering, so I can review
  without full editing — using a lightweight vanilla client served by the existing stack, with no new
  dependency. **D1/D2/D3 decided 2026-07-07 (§10).** → REQ-P13-WEB-001..005 · `web-viewer` · P13

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase | Status |
| --- | --- | --- | --- |
| `portability-harden` | Cross-OS round-trip correctness: case-sensitivity, UTF-8, CRLF/LF, `pathlib`, font fallback, DPI/scaling; byte-faithful project open on any OS. | 13 | drafted |
| `ci-matrix` | Windows + Linux + macOS CI matrix runs the suite green. | 13 | drafted |
| `portable-bundle` | Self-contained cross-OS project bundle embedding referenced CAS assets; path-traversal-defended import. | 13 | drafted |
| `vps-artifacts` | Docker + systemd + Nginx TLS/WSS deployment artifacts for the shipped `sync_backend/`; one hosting option, not forced. | 13 | drafted |
| `native-installers` | Windows exe/MSI, macOS .app/.dmg, Linux AppImage via `pyside6-deploy`/PyInstaller + CI build matrix; mac signing credential-gated, non-blocking. | 13 | drafted |
| `web-viewer` | Vanilla HTML/CSS/JS browser client, served static by the existing Nginx with data over `sync_backend/` (no new dependency), signed-share-link-token-gated, for viewing + light interaction of shared projects; headless, no Qt, outside 3 layers. **D1/D2/D3 decided.** | 13 | drafted |

---

## 4. Functional requirements

Each REQ is a technology-neutral WHAT statement with **measurable** acceptance grounded in the Researcher
report + the shipped architecture. Concrete HOW — the packaging tool selection & flags, the Docker/systemd/
Nginx file contents, the bundle wire format, the CI-matrix YAML, and (for 13E) the concrete signing/crypto
library + exact token format + the Nginx static-serving location block + the JS module layout — is
downstream (AGT-01 plan/ADR; AGT-09 CI/packaging; AGT-03 logic; §8). The 13E **product-direction
decisions** D1/D2/D3 (reuse existing stack / no new dependency; signed share-link token; vanilla
HTML/CSS/JS) are now **fixed at the WHAT level** and constrain the WEB REQs; only their concrete
realisation is HOW. A binding to a shipped callable or component is a **constraint**, not a HOW choice.

### `data/` + `ui/` + `BUILD` — Slice 13A: PORTABILITY HARDEN

#### REQ-P13-DATA-001 — All filesystem paths handled portably via `pathlib` (no separator/UNC/root assumptions)
`traces:` Article I (data/ Qt-free I/O), Article II, Researcher Q5 (path separators/roots — Windows backslash+UNC vs POSIX single-rooted; use `pathlib`), PIO-1, `path_portability_check`
Every path the platform reads or writes (project files, asset blobs, bundles, exports, config) is
constructed and manipulated as a **`pathlib` path object**, never as a hand-concatenated string with a
literal separator, so the correct separator/root is applied per-OS and no Windows-specific
backslash/UNC/drive assumption leaks into a cross-OS artifact. The shipped `path_portability_check` gate
is **hardened + widened** to cover the newly-touched read/write sites.
**Acceptance:** `path_portability_check` reports **zero** hardcoded-separator / non-`pathlib` path
constructions across all read/write sites in `data/`; a project saved with asset references on one OS
resolves those references correctly on another (no `\`-vs-`/` failure); the check runs in the CI matrix
(REQ-P13-BUILD-001) on all three OSes.

#### REQ-P13-DATA-002 — UTF-8 filesystem encoding enforced on every read/write (not assumed)
`traces:` Article I, Researcher Q5 (POSIX defaults UTF-8; **Windows historically does not** → garbled output; mitigate with explicit UTF-8), PIO-1
All text/JSON I/O in `data/` **explicitly specifies UTF-8** (encoding is never left to the platform
default), so a project or catalogue containing non-ASCII names/metadata authored on POSIX is read back
identically on Windows and vice-versa, with no mojibake and no `UnicodeDecodeError`.
**Acceptance:** a project/catalogue/bundle containing non-ASCII characters (accented, CJK, emoji in a
display name) round-trips **byte-faithfully** across a Windows↔Linux↔macOS pair; no read/write site
relies on the platform default encoding (verified by inspection + a non-ASCII round-trip test in the CI
matrix).

#### REQ-P13-DATA-003 — Line-ending (CRLF/LF) determinism for text artifacts
`traces:` Article I, Article II (determinism), Researcher Q5 (Windows CRLF vs POSIX LF — a classic text-file portability gotcha), PIO-1, P2 (determinism)
Any text artifact the platform emits (e.g. sidecar/JSON/config) uses a **single, OS-independent
line-ending discipline** so its bytes do not differ merely because of the authoring OS; a text artifact
authored on Windows and one authored on POSIX are **byte-identical** for identical content.
**Acceptance:** an identical logical text artifact produced on Windows and on POSIX is **byte-equal** (no
CRLF/LF divergence); binary artifacts (`.pixproj` zlib payload) are unaffected; verified by a cross-OS
byte-equality test in the CI matrix.

#### REQ-P13-DATA-004 — Filename case-sensitivity discipline (code case-sensitively; safe on Linux)
`traces:` Article I, Article VII (safe I/O), Researcher Q5 (**Windows/macOS case-insensitive, Linux case-sensitive** → code that works on Win/mac fails on Linux; "always code as if the filesystem is case-sensitive"; PEP 235), Phase-11 `data/asset_cas.py` (CAS blob paths)
The platform treats every filename/asset-reference/CAS-blob path as **case-sensitive** (the strictest
rule, Linux), so no two references differing only in case collide, and no reference relies on a
case-insensitive filesystem to resolve. Referenced files are looked up by their **exact** stored case.
**Acceptance:** a project whose assets differ only in filename case (e.g. `Hero.png` vs `hero.png`)
round-trips and resolves correctly on **Linux** (case-sensitive) without collision or wrong-file
resolution; no lookup depends on case-folding; verified on the Linux CI leg.

#### REQ-P13-DATA-005 — Cross-OS project round-trip is byte-faithful (headline correctness)
`traces:` Article I, Article IV (regression), Researcher Q5 (all pitfalls), PIO-1, DATA-001..004 (composed), P2 (determinism)
A project (`.pixproj` + any referenced assets) authored on **any** of Windows/Linux/macOS opens
**byte-faithfully** on **any** other — same layers, frames, tilemaps, palettes, PPI, asset references,
and non-ASCII metadata — because REQ-P13-DATA-001..004 hold together. "Byte-faithful" means the
document model reconstructed on OS-B is **equal** to the model on OS-A (and the re-saved payload is stable
per the shipped deterministic serialiser).
**Acceptance:** for each ordered OS pair (Win→Linux, Win→mac, Linux→Win, Linux→mac, mac→Win, mac→Linux),
a representative project (multi-layer, animated, tilemapped, non-ASCII names, case-distinct assets) saved
on the source OS loads on the target OS to a **model-equal** document and re-saves to a **stable** payload;
the round-trip is exercised in the CI matrix.

#### REQ-P13-UI-001 — Font-availability fallback across OSes
`traces:` Article I (ui/), Article V (UX), Researcher Q5 (cross-OS installed-font differences — flagged test area), Article VI (render correctness)
The UI **never depends on a font that exists on only one OS**: user-visible text renders legibly on
Windows/Linux/macOS via a defined fallback chain / role-based font selection, so no label is clipped,
missing, or box-glyphed because a Windows-only or macOS-only family is absent on Linux.
**Acceptance:** on each of the three OSes (headless-renderable where possible; documented manual check
where a real display is required), all primary UI text renders with a resolvable font (no
missing-glyph/`.notdef` boxes); the fallback chain is defined once (not per-widget); both light and dark
themes are unaffected.

#### REQ-P13-UI-002 — DPI / display-scaling correctness across OSes
`traces:` Article I (ui/), Article VI (render), Article V, Researcher Q5 (per-monitor DPI/scaling cross-OS differences — flagged test area), Researcher Q3 (Qt platform-plugin handling), Phase-9 real-size-preview DPR precedent
The UI renders correctly under the differing per-OS **DPI/display-scaling** behaviours (Windows
per-monitor scaling, macOS Retina/backing-scale, Linux fractional scaling) — the canvas, docks, and
overlays are laid out in device-independent coordinates and let Qt apply the device-pixel ratio (the
shipped Phase-9 "do **not** multiply DPR" discipline), so nothing is double-scaled, blurred, or clipped
at non-100% scaling.
**Acceptance:** at representative scale factors (100%, 150%, 200%) the UI lays out without truncation or
double-scaling and the nearest-neighbour pixel canvas stays crisp; the app does not manually multiply the
device-pixel ratio; verified per-OS (headless where possible; documented manual check otherwise); the
16 ms `FRAME_BUDGET_MS` is **not relaxed** (Article VI) — this REQ changes no perf budget.

#### REQ-P13-BUILD-001 — Windows/Linux/macOS CI matrix runs the suite green
`traces:` Article IV (testing), Article VIII (gates), Researcher Q3 (Qt `offscreen` platform plugin for headless/CI), shipped `.github/workflows/ci.yml` (headless-Qt harness), Article X §1 (`BUILD` first-class tag)
The CI harness is extended from its single-OS form to a **Windows + Linux + macOS matrix** that runs the
**full** existing suite (lint/type/tests/coverage gate + `path_portability_check` + the new cross-OS
round-trip tests) **headless** on each OS, and the cross-OS portability REQs above are **gated** by it so a
regression on any one OS blocks merge. Owned by AGT-09; a **non-three-layer `BUILD`** concern (the
`sync_backend`/`BACKEND` precedent for a first-class tag, ADR-0027).
**Acceptance:** the CI workflow defines a 3-OS matrix (Windows, Linux, macOS), each leg runs the suite
headless and **passes green**; the portability tests (REQ-P13-DATA-001..005, and the checkable parts of
UI-001/-002) run on all three legs; a deliberate cross-OS regression fails the matrix; the concurrency
guard (F11) and Python pin are preserved.

### `data/` — Slice 13B: PORTABLE BUNDLE (extends `data/asset_export.py`)

#### REQ-P13-DATA-006 — Self-contained cross-platform bundle export (embeds referenced CAS assets)
`traces:` Article I (data/ Qt-free), Article II, Phase-11 `REQ-P11-DATA-005` (`asset_export.py` — resolve reference set → bundle referenced CAS blobs, self-contained), Phase-11 `data/asset_cas.py`, DATA-001..002 (portable paths + UTF-8)
Extending the shipped `data/asset_export.py`, the platform exports a project as a **self-contained
portable bundle** that **embeds every referenced CAS asset blob** the project depends on (resolved via the
shipped reference-set resolution), so the bundle carries **everything** needed to reconstruct the project
with **no external file dependency**. Bundle internals use portable paths + UTF-8 (REQ-P13-DATA-001/-002).
**Acceptance:** exporting a project with referenced assets produces a **single self-contained** bundle
whose contents include the project payload **and** every referenced CAS blob (no dangling external
reference); exporting the same project on Windows/Linux/macOS produces functionally equivalent,
importable bundles; the exporter reuses the shipped `asset_export` reference resolution (no re-implemented
CAS logic, Article I).

#### REQ-P13-DATA-007 — Bundle imports on a different OS (self-contained cross-OS round-trip)
`traces:` Article I, Article IV (regression), DATA-005 (cross-OS round-trip), Phase-11 `asset_export` import, DATA-001..004
A bundle exported on one OS **imports on any other OS** and reconstructs the project + all embedded assets
**self-contained** — same layers/frames/tilemaps/palettes/references and non-ASCII/case-distinct asset
names — with no missing, renamed, or mis-cased file, honouring the 13A portability rules.
**Acceptance:** for each ordered OS pair, a bundle exported on the source OS imports on the target OS to a
**model-equal** project with **all** referenced assets present and resolvable (including non-ASCII and
case-distinct names); the round-trip is exercised in the CI matrix (REQ-P13-BUILD-001).

#### REQ-P13-DATA-008 — Bundle import is path-traversal-defended and `eval`/`exec`-free (Article VII)
`traces:` **Article VII (no `eval`/`exec`; untrusted input)**, Article I, Phase-11 `asset_export` "import defence" + `resolve()`+containment precedent, Phase-10 `logic/cloud_validation.py` (defensive untrusted-input discipline), PIO-1
Bundle import treats the bundle as **untrusted input**: every embedded entry's destination path is
**resolved and constrained to stay within the import target** (no `..`/absolute/zip-slip escape), sizes/
counts are bounded, malformed/oversized/unknown-version bundles are rejected with a **user-facing error**
(never a crash or a partial write left as valid), and **no `eval`/`exec`** is used on any import path
(the shipped defensive `.pixproj`/`asset_export` discipline is reused, not weakened).
**Acceptance:** an import of a bundle crafted with a traversal entry (`../`, absolute path, symlink
escape) is **rejected** and writes **nothing** outside the import target; an oversized/malformed/unknown-
version bundle raises a defined user-facing error (no crash, no partial-valid write); a source-audit
confirms **zero** `eval`/`exec` on the import path (Article VII invariant preserved).

### `BACKEND` — Slice 13C: VPS ARTIFACTS for the shipped `sync_backend/`

#### REQ-P13-BACKEND-001 — Container + service artifacts to run the existing `sync_backend/` on a VPS
`traces:` Article X §1 (`BACKEND` first-class tag, ADR-0027), Article IV (localhost-CI-testable, REQ-P10-BACKEND-001), Researcher Q4 (Docker/systemd process management; bind `0.0.0.0`; `--ulimit nofile=65535:65535` / systemd `LimitNOFILE=65535`; ~10K conns/process), shipped `sync_backend/server.py`
The platform ships **deployment artifacts** — a **Docker image** definition and a **systemd unit** — that
run the **existing, unchanged** `sync_backend/` asyncio-`websockets` relay on a generic VPS: binding
**`0.0.0.0`** (not localhost), setting the file-descriptor limit to **at least 65535** (`--ulimit
nofile=65535:65535` in Docker / `LimitNOFILE=65535` under systemd) per the Q4 scaling floor, and
documenting the ~10K-connections/process ceiling. **No change to the shipped backend code** is required
(artifacts + docs only). Owned by AGT-09; a **non-three-layer `BACKEND`** concern.
**Acceptance:** a Docker image definition + a systemd unit exist that launch the shipped `sync_backend/`
bound to `0.0.0.0` with `LimitNOFILE`/`--ulimit` ≥ 65535; running the containerized/service backend and
connecting a client **over localhost/loopback** reproduces the shipped multi-client convergence
(REQ-P10-BACKEND-001) — **no live external server is required for acceptance**; the backend source is
unmodified.

#### REQ-P13-BACKEND-002 — Nginx TLS/WSS reverse-proxy config with the correct WebSocket tuning
`traces:` Researcher Q4 (**Nginx TLS termination; proxy the HTTP `Upgrade`/`Connection` headers; raise `proxy_read_timeout` from the 60 s default (e.g. 86400) or idle WS connections are killed**; TLS terminated at proxy → app serves plain WS behind it), Article X §1 (`BACKEND`)
The platform ships an **Nginx reverse-proxy configuration** that terminates **TLS** and proxies **WSS→WS**
to the backend, correctly forwarding the WebSocket **HTTP `Upgrade`/`Connection`** headers and **raising
`proxy_read_timeout`** well above the 60 s default (e.g. 86400) so idle WebSocket connections are not
killed — matching the Q4 documented recipe. The backend serves **plain WS behind** the TLS-terminating
proxy.
**Acceptance:** the shipped Nginx config terminates TLS, proxies the `Upgrade`/`Connection` headers, and
sets `proxy_read_timeout` above the 60 s default; a documented **localhost** run through the proxy config
(self-signed/loopback) sustains a WebSocket connection **past 60 s idle** without being dropped — proving
the tuning, **without** requiring a live external server or a public certificate.

#### REQ-P13-BACKEND-003 — VPS hosting is ONE option, not a forced default
`traces:` Phase-10 CL-B4 (localhost + provider-adapter hosting options; no forced default), Article V, Researcher Q4, ADR-0027
VPS self-hosting is offered as **one** hosting option **alongside** the shipped **localhost** run and the
**cloud provider-adapter** — the artifacts and docs make it **selectable, not mandatory**, and the app's
default behaviour is **unchanged** (no VPS is required to use the platform). The docs present all three
options neutrally.
**Acceptance:** documentation presents localhost + cloud-adapter + VPS as co-equal options; adopting the
VPS artifacts changes **no** default and requires **no** code change to the app or backend; a user who
ignores 13C sees identical behaviour to today.

### `BUILD` — Slice 13D: NATIVE INSTALLERS

#### REQ-P13-BUILD-002 — Windows native distributable (exe/MSI)
`traces:` Researcher Q3 (`pyside6-deploy` (Nuitka, Qt-recommended) / PyInstaller; **Qt platform/image/style plugins must be bundled** — the deploy tools handle this; Windows → exe/MSI), Article X §1 (`BUILD`), shipped app entry point
The desktop app is packaged as a **Windows native distributable** (an `.exe` and/or `.msi`) via
`pyside6-deploy`/PyInstaller (Q3), with the required **Qt plugins bundled** (platform/image-format/style),
so a non-technical Windows user can install and launch the app **without a Python environment**.
**Acceptance:** the Windows CI leg produces an installable `.exe`/`.msi` artifact that launches the app
on a clean Windows environment (smoke-launch) with Qt plugins bundled; the build is reproducible from the
committed packaging config.

#### REQ-P13-BUILD-003 — macOS native distributable (.app/.dmg); signing/notarization is credential-gated and NON-blocking
`traces:` Researcher Q3 (**macOS store-distribution MANDATES Developer-ID signing + notarization + hardened runtime + stapling** — a hard requirement needing the user's Apple Developer ID; `notarytool`+`stapler`), Article X §1 (`BUILD`), Article XI (credential-gated irreversible/external steps)
The app is packaged as a macOS **.app** wrapped in a **.dmg** via the Q3 tooling. Because notarization
**requires the user's Apple Developer ID** (a credential not yet available), the spec **ships the build
pipeline + an UNSIGNED / ad-hoc-signed mac artifact NOW** and treats **Developer-ID signing +
notarization + hardened runtime + stapling** as a **documented, credential-gated step** that runs when the
credential is supplied. **Notarization is explicitly NOT a blocking acceptance criterion** for Phase 13.
**Acceptance:** the macOS CI leg produces a **.app/.dmg** (unsigned/ad-hoc) that launches on macOS
(smoke-launch, Gatekeeper-bypass documented for the unsigned case); the signing/notarization/stapling step
is **documented and credential-gated** (runs only when an Apple Developer ID is provided) and its absence
**does not fail** the phase; no credential is committed (Article XI).

#### REQ-P13-BUILD-004 — Linux native distributable (AppImage)
`traces:` Researcher Q3 (Linux → AppImage/Flatpak standard targets; `pyside6-deploy`/PyInstaller; Qt plugins bundled), Article X §1 (`BUILD`)
The app is packaged as a **Linux AppImage** (a self-contained, distro-agnostic executable) via the Q3
tooling with Qt plugins bundled, so a Linux user can run the app without a system Python or distro package.
**Acceptance:** the Linux CI leg produces a runnable **AppImage** that launches the app headless/smoke on
a clean Linux environment with Qt plugins bundled; the build is reproducible from the committed config.

#### REQ-P13-BUILD-005 — CI build matrix produces all three installers
`traces:` Article IV, Article VIII (gates), Researcher Q3, Article X §1 (`BUILD`), REQ-P13-BUILD-001 (the same 3-OS matrix)
A **CI build matrix** builds the Windows, macOS, and Linux distributables (BUILD-002/-003/-004) on their
respective OS legs and publishes them as build artifacts, so every target is produced by the **same
automated, reproducible pipeline** (extending the REQ-P13-BUILD-001 test matrix into a build matrix).
**Acceptance:** a single CI build matrix produces the Windows exe/MSI, macOS .app/.dmg (unsigned/ad-hoc),
and Linux AppImage as downloadable artifacts on a build/tag trigger; a failure to build any leg fails that
leg visibly; the macOS signing step is the credential-gated, non-blocking addition (BUILD-003).

### `WEB` — Slice 13E: WEB COMPANION VIEWER *(FULLY SPECIFIED — D1/D2/D3 DECIDED 2026-07-07)*

> The five WEB REQs now encode the USER's D1/D2/D3 decisions (§10): **D1** reuse the existing stack with
> NO new dependency (static client served by the already-planned Nginx from 13C; project data over the
> shipped `sync_backend/` `websockets`; stdlib `http.server` for local dev only); **D2** a per-shared-
> project short-lived **signed share-link token** (validate signature + expiry + issuer/audience; scope
> to the shared project); **D3** **vanilla HTML/CSS/JS** (no build step / no framework; Canvas API
> renders pixel art faithfully). No `[NEEDS CLARIFICATION]` marker remains; each acceptance is complete.

#### REQ-P13-WEB-001 — View a shared project faithfully in a browser (read-mostly, pixel-accurate)
`traces:` Researcher Q2a (browser WS viewer over the existing backend; works on mobile browsers), Researcher Q1b (no native iOS PySide6 path → browser is the mobile-view route), research `a4c7da21` (D1/D3), Phase-10 `sync_backend/` (the shared-project source), Article V, Article VI (faithful pixel render)
A user can **open a SHARED project in a web browser and view it** — its current shared state (layers,
frames, canvas as shared over the backend) is rendered **read-mostly**. Per **D3**, the client is
**vanilla HTML/CSS/JS** (no build step, no framework) and renders the pixel art **faithfully** using the
Canvas API with nearest-neighbour scaling (`image-rendering: pixelated`, `imageSmoothingEnabled = false`,
**integer scale factors**) so pixels are crisp and never blurred/interpolated. Per **D1**, the client is
delivered as **static files by the already-planned Nginx** (13C VPS artifacts; a stdlib `http.server` is
acceptable for **local dev only**) and its project data arrives over the **shipped `sync_backend/`
`websockets`** relay — **no new Python web-framework dependency**. The viewer is a **consumer** of the
shared project; it is **not** the editor.
**Acceptance:** given a shared project reachable over `sync_backend/`, the vanilla-JS client renders its
current shared visual state read-mostly with **pixel-faithful** nearest-neighbour scaling (no smoothing;
integer zoom) verified by a rendered-pixel comparison against the shared source; the client is served as
**static assets** (no new Python web framework is added — dependency manifest unchanged aside from
existing `websockets`); project data flows over the existing `sync_backend/` transport.

#### REQ-P13-WEB-002 — Light interaction only (view layers/frames, pan/zoom) — NOT full editing
`traces:` Article V, Article I (the desktop `ui/` remains the sole editor), Researcher Q2a (light-interaction browser client), research `a4c7da21` (D2/D3), user-decided scope (viewing + light interaction, NOT full editing)
The viewer supports **light, read-mostly interaction** — **viewing/toggling layers, stepping through
frames, and pan/zoom** of the canvas — but **NO editing** (no pixel writes, no mutation of the shared
project). The authoritative editor remains the PySide6 desktop app; the viewer never becomes a second
editor. Because access is gated by a **signed share-link token scoped to the shared project** (D2), a
web client can only ever request/observe that one project's state — it cannot send an editing mutation.
**Acceptance:** the browser client exposes exactly the light interactions — layer visibility toggle,
frame navigation, and pan/zoom — and **exposes no editing capability** (no control mutates the shared
project; no mutation message is emitted by the client); the desktop app remains the sole editor of
record; an attempt to send a non-view message with a view-scoped token is rejected by the backend.

#### REQ-P13-WEB-003 — Cross-browser: iOS Safari + Android Chrome (device-verified)
`traces:` Researcher Q2a (**every modern browser incl. mobile Safari on iOS and Chrome on Android supports WebSockets; no smartphone compatibility issue**), research `a4c7da21` (D3 vanilla client, no build step → broad browser support), Article V
The viewer **works on iOS Safari and Android Chrome** (the two dominant mobile browsers) as well as
desktop browsers, so a collaborator can view a shared project from a phone. Because the client is
**vanilla HTML/CSS/JS with no build step** (D3), it runs on any modern browser engine without a
transpile/polyfill toolchain; Q2a confirms both mobile browsers support the WebSocket transport with no
compatibility issue. The pixel-faithful Canvas rendering (REQ-P13-WEB-001) must hold on both mobile
engines — **iOS Safari is called out as a device-test / verification concern** (its Canvas/`image-
rendering` behaviour is verified on a real device, not only an emulator).
**Acceptance:** the viewer loads, connects, and renders a shared project **pixel-faithfully** on **iOS
Safari** and **Android Chrome** (and a desktop browser); iOS Safari is verified on a real device
(documented device check) confirming `image-rendering: pixelated` + `imageSmoothingEnabled = false`
produce crisp, non-blurred pixels; no build-step/transpile toolchain is required for any target browser.

#### REQ-P13-WEB-004 — `web_viewer/` is a NEW top-level component OUTSIDE the three layers, headless, MUST NOT import Qt
`traces:` **Article I (three-layer purity — invariant, NOT relaxed)**, Phase-10 `sync_backend/` precedent (ADR-0027 — a first-class top-level component outside `ui/`/`logic/`/`data/`), Article X §1 (`WEB` first-class tag), research `a4c7da21` (D1 no new dependency, D3 vanilla — reinforces the Qt-free headless placement), `check_layering`/`check_cycles` `--root` discipline
The web viewer lives in a **NEW top-level `web_viewer/`** directory **OUTSIDE** the three desktop layers
(the `sync_backend/` precedent), is **headless**, and **MUST NOT import Qt** (nor `ui/`). Consistent with
**D1/D3**, it contains only **static vanilla client assets** (HTML/CSS/JS) plus any thin, Qt-free
serving/token glue that reuses the shipped `sync_backend/`/`logic/` pattern — **no new web framework**.
It may reuse **pure, Qt-free** shipped code where appropriate but introduces no dependency from the
desktop layers on it.
**Acceptance:** `web_viewer/` exists as a top-level sibling of `pixelart_creator/` and `sync_backend/`;
a layering check over `web_viewer/` confirms it imports **no Qt** and **no `ui/`**, and introduces **no
new Python web-framework dependency** (D1); the three desktop layers do not import `web_viewer/`;
**Article I is preserved** (this criterion is D1/D2/D3-independent — the decisions only reinforce it).

#### REQ-P13-WEB-005 — Signed-share-link-token-gated over `sync_backend/`; untrusted web input; no `eval`/`exec` (Article VII)
`traces:` **Article VII (no `eval`/`exec`; untrusted input — invariant, NOT relaxed)**, Phase-10 `sync_backend/` + `logic/cloud_validation.py` (defensive, `eval`-free frame validation), Researcher Q2a (viewer served over the existing backend), research `a4c7da21` (D1 serving, D2 signed token), Researcher Q4 (backend ops)
The viewer's project data is **served over the shipped `sync_backend/`** (the existing relay), gated by a
**per-shared-project short-lived signed share-link token** (D2): the viewer presents a signed bearer
token over HTTPS, and the backend **validates the token's signature, expiry, and issuer/audience and
scopes access to exactly the shared project the token names** before serving any of that project's data
— an **expired or invalid** token (bad signature, wrong audience, past expiry) is **rejected** and no
project data is served. **All input arriving from a web client is treated as untrusted** — validated
defensively with size/shape caps, reusing the shipped `eval`-free `logic/cloud_validation.py` /
`logic/sync_protocol.py` discipline; **no `eval`/`exec`** appears on any web-input path (Article VII
invariant preserved). The token model is **not full OAuth and requires no login flow**; the concrete
signing/crypto (which may reuse existing codebase primitives) and token format are AGT-01/AGT-03 HOW.
**Acceptance:** presenting a **valid, unexpired, correctly-scoped** signed token serves the named shared
project's data; presenting an **expired, wrong-audience, or bad-signature** token is **rejected** and
serves **no** project data; a token scoped to project A cannot access project B; all web-client input is
schema/size-validated and a source audit confirms **zero `eval`/`exec`** on any web-input path
(Article VII); no new web-framework dependency is introduced by the serving/token path (D1).

## 5. Non-functional requirements (constitution-tied) — invariants NOT relaxed

- **Article I (three-layer purity) — INVARIANT.** The two non-three-layer components are placed **outside**
  the three layers exactly as `sync_backend/` is (ADR-0027): the `BUILD` pipeline is DevOps tooling;
  `web_viewer/` is a new top-level, **Qt-free**, headless component (REQ-P13-WEB-004). The desktop layers
  gain no dependency on either. `check_layering`/`check_cycles` remain green (extended `--root` coverage
  for `web_viewer/`).
- **Article VII (no `eval`/`exec`; untrusted input) — INVARIANT.** The portable-bundle import (13B,
  REQ-P13-DATA-008) and any web input (13E, REQ-P13-WEB-005) are untrusted-input paths — defensive,
  size/shape-capped, path-traversal-defended, **`eval`/`exec`-free**, reusing the shipped PIO-1 /
  `asset_export` / `cloud_validation` discipline. **No slice weakens this.**
- **Article II (bounded numerics).** Any new numeric bound (bundle size/entry caps, `LimitNOFILE`,
  `proxy_read_timeout`, DPI scale set) is a **single-source named constant** where it belongs
  (`logic/constants.py` for app numerics; the artifact/config file for ops numerics); no magic literal at
  a call/config site. Concrete values are HOW (§8).
- **Article IV (testing) + Article VIII (gates).** The cross-OS CI matrix (REQ-P13-BUILD-001) is the
  phase's verification spine — the round-trip, bundle, and portability REQs are **gated** on all three OS
  legs; a per-OS regression blocks merge. The VPS artifacts are proven **over localhost/loopback**
  (BACKEND-001/-002) — no live external server is a test dependency.
- **Article VI (render budget).** `FRAME_BUDGET_MS = 16` is **not** touched by DPI/scaling correctness
  (REQ-P13-UI-002) — no perf budget is relaxed.
- **Article XI (credentials / irreversible steps).** macOS signing/notarization is **credential-gated**
  (REQ-P13-BUILD-003); no Apple Developer ID (or any credential) is committed; the signing step runs only
  when the credential is supplied and is **non-blocking**.
- **Article X (traceability).** Every REQ traces to a Researcher Q-section / shipped-architecture anchor /
  constitution article + ≥ 1 acceptance scenario (matrix, §9). 13E scenarios are now **COMPLETE** — the
  D1/D2/D3 decisions (§10, grounded by research `a4c7da21`) are encoded and each WEB REQ has full
  acceptance + Gherkin.

## 6. Non-goals (explicit)

- **Native mobile PySide6 apps.** Researcher Q1b: **no supported native iOS PySide6 deployment exists in
  2026**; Q1a: Android is supported but Linux-build-host-only with packaging constraints. Phase 13 does
  **NOT** ship a native iOS/Android app — mobile access is the **browser viewer** (13E), the
  platform-neutral path. (Native-mobile / BeeWare-Toga / Kivy companion apps are out of scope, Q2b.)
- **Full web editing.** 13E is **view + light interaction only** — the desktop stays the editor
  (REQ-P13-WEB-002). Turning the viewer into a second editor is out of scope.
- **A live public server / real domain / public TLS certificate.** 13C acceptance is **deployability +
  documented localhost-testable run** (BACKEND-001/-002), not operating a production server.
- **Making macOS notarization a blocking criterion.** Signing/notarization is credential-gated and
  non-blocking (REQ-P13-BUILD-003) — the phase ships without it.
- **Relaxing Article I or Article VII.** Both are invariants (§5); no slice weakens layering or introduces
  `eval`/`exec`.
- **A new web-framework dependency for 13E.** D1 decided **NO new Python web framework** (no FastAPI/
  aiohttp): the vanilla client is served static by the already-planned Nginx (stdlib `http.server` for
  local dev only) and data flows over the existing `websockets` `sync_backend/`. Adding a web framework is
  out of scope.
- **A JS build step / framework / SPA for 13E.** D3 decided **vanilla HTML/CSS/JS** — no bundler,
  transpiler, or framework. A build-tooled SPA is out of scope.
- **Full OAuth / a login flow for the viewer.** D2 decided a **signed share-link token** — a short-lived
  signed bearer token scoped to one shared project. A full OAuth/login system is out of scope.
- **Full web editing.** (Restated for 13E) the viewer is view + light interaction only (REQ-P13-WEB-002);
  no editing/mutation from the web client.
- **HOW.** Packaging tool flags, Docker/systemd/Nginx file contents, the bundle wire format, the CI-matrix
  YAML, and (for 13E) the concrete signing/crypto library + token format + Nginx static-serving location
  block + JS module layout that realise the decided D1/D2/D3 are AGT-01 (plan/ADR) / AGT-03 (logic) /
  AGT-09 (CI/packaging/ops) (§8). This spec writes only under `specs/phase-13-cross-platform/`; it touches
  **no** `docs/**`, code, or other specs.

## 7. Dependencies & assumptions

- **Grounded facts-first** in `docs/subagent-report-the-researcher-acaae022-20260707T093800.md` (The
  Researcher, 2026-07-07, PySide6/Qt 6.10 anchor). This spec invents no facts: Q5→13A, Q3→13D, Q4→13C,
  Q2a+Q1b→13E.
- **All upstream substrate is shipped and REUSED/HARDENED/EXTENDED/PACKAGED, not re-authored:**
  `data/project_io.py` (PIO-1), `data/asset_export.py` + `data/asset_cas.py` (Phase 11), `sync_backend/`
  + `logic/sync_protocol.py` + `logic/cloud_validation.py` (Phase 10), `scripts/path_portability_check`,
  `.github/workflows/ci.yml`, `logic/constants.py` (Article I — nothing re-implemented).
- **A2-D2 ambiguity gate:** for **13A–13D**, no requirement is underspecified and no two requirements
  conflict — every target is grounded → **nothing SUSPENDED**; `sdd-plan` UNBLOCKED. For **13E**, three
  acceptance-changing sub-decisions were originally SUSPENDED (`[NEEDS CLARIFICATION]`); the **USER
  adjudicated all three on 2026-07-07** (grounded by research `a4c7da21`) and the resolved decisions are
  now recorded as a **category-1 source** (§10) and encoded into REQ-P13-WEB-001..005 → **nothing left
  SUSPENDED**; `sdd-plan` UNBLOCKED for the whole phase.
- **The Researcher's D1/D2/D3 grounding (`a4c7da21`) has LANDED** and the USER has decided; no
  requirement across all 23 REQs now awaits external input.

## 8. Behaviours flagged for AGT-01 / AGT-09 (not blockers for 13A–13D; HOW)

- **DEP-1 (AGT-09 — CI/build matrix).** The Win/Linux/macOS CI **test** matrix (REQ-P13-BUILD-001) and
  **build** matrix (REQ-P13-BUILD-005) YAML — headless Qt (`offscreen`), preserved concurrency guard +
  Python pin; publish installer artifacts. Extends the shipped `ci.yml`.
- **DEP-2 (AGT-09 — packaging).** `pyside6-deploy` vs PyInstaller selection + flags per OS; Qt-plugin
  bundling; Windows exe/MSI, Linux AppImage, macOS .app/.dmg; the **credential-gated** macOS
  `notarytool`+`stapler` signing step (non-blocking, Article XI). Grounded by Q3; an ADR is expected.
- **DEP-3 (AGT-09 — VPS artifacts).** Dockerfile + systemd unit + Nginx TLS/WSS config contents with the
  Q4 tuning (bind `0.0.0.0`; `LimitNOFILE`/`--ulimit` ≥ 65535; `Upgrade`/`Connection` proxying;
  `proxy_read_timeout` ≫ 60 s). Localhost-testable; no live server.
- **DEP-4 (AGT-01 — bundle format + portability HOW).** The portable-bundle wire format (extending
  `asset_export.py`), the `resolve()`+containment traversal defence, the case-sensitivity/UTF-8/line-ending
  implementation across `data/`, and the DPI/font-fallback approach in `ui/`. Must preserve byte-faithful
  round-trip (REQ-P13-DATA-005) and Article VII (REQ-P13-DATA-008); an ADR is expected.
- **DEP-5 (AGT-01 / AGT-03 — 13E HOW, now UNBLOCKED).** D1/D2/D3 (§10) have been **adjudicated by the
  USER (2026-07-07)** and encoded into REQ-P13-WEB-001..005; 13E's technical requirements are **frozen**
  and `sdd-plan` is **UNBLOCKED** for 13E. The remaining HOW to realise the decided direction: the Nginx
  static-serving location block for the vanilla client (extending the 13C config; stdlib `http.server`
  for local dev only), the concrete **signing/crypto + signed-share-link-token** format and validation
  (signature + expiry + issuer/audience + project scope — may reuse existing codebase crypto), the
  vanilla JS module layout + Canvas pixel-faithful renderer (`image-rendering: pixelated`,
  `imageSmoothingEnabled = false`, integer scale), and the iOS-Safari device-verification step. An ADR is
  expected for the token/serving design. **No new web-framework dependency** (D1).

## 9. Traceability

See `specs/phase-13-cross-platform/traceability.md` — REQ ↔ Researcher Q-section / shipped-architecture
anchor / constitution article ↔ acceptance scenario ↔ (future) test. **All 23 REQs carry a matrix row.**
**All 23 REQs across 13A–13E now carry FULL acceptance + ≥ 1 Gherkin scenario** and are
clarification-clean — the 5 WEB REQs of 13E have their D1/D2/D3 decisions (§10) encoded and their
acceptance completed. Acceptance scenarios are in `acceptance.md`.

## 10. Clarifications

**13A–13D: NONE open.** Per the A2-D2 gate, no 13A–13D requirement is underspecified and no
product-direction choice is unresolved; every target is grounded in the Researcher report + shipped
architecture. `sdd-plan` (AGT-01) is **UNBLOCKED** for 13A–13D.

**13E: THREE items — ALL DECIDED 2026-07-07 (grounded by research `a4c7da21`).** These were originally
recorded `[NEEDS CLARIFICATION]` and SUSPENDED under A2-D2 (not guessed). The **USER has now decided all
three**; the resolved decisions below are recorded as a **category-1 source** (grounded product
direction) and are encoded into REQ-P13-WEB-001..005. No `[NEEDS CLARIFICATION]` marker remains; 13E's
technical requirements are **frozen** and 13E is **UNBLOCKED for `sdd-plan`**.

- **DECIDED — D1 — Web-serving stack / dependency → REUSE EXISTING STACK, NO NEW DEPENDENCY.** The vanilla
  static client is served by the **already-planned Nginx** (from slice 13C's VPS artifacts); the project
  data flows over the **existing `sync_backend/` asyncio-`websockets`** relay; a tiny stdlib
  `http.server` is acceptable for **LOCAL DEV only**. **NO new Python web-framework dependency** (no
  FastAPI/aiohttp) — one backend, architecturally consistent with the shipped `sync_backend/`. → encoded
  in REQ-P13-WEB-001/-004/-005.
- **DECIDED — D2 — Viewer auth model → SIGNED SHARE-LINK TOKEN.** A per-shared-project **short-lived
  signed bearer token / share link over HTTPS**: the viewer presents the token; the backend validates
  **signature + expiry (and issuer/audience)** and scopes access to that project before serving its data.
  **Not full OAuth; no login flow.** (May reuse existing signing/crypto in the codebase — that is an
  AGT-01/AGT-03 HOW, not a spec mandate.) → encoded in REQ-P13-WEB-002/-005.
- **DECIDED — D3 — Vanilla client vs SPA → VANILLA HTML/CSS/JS.** No JS build step, no framework/SPA. The
  vanilla **Canvas API** renders the pixel-art canvas **faithfully** (`image-rendering: pixelated` +
  `imageSmoothingEnabled = false` + integer scale). **Must work on iOS Safari + Android Chrome**
  (device-test on iOS Safari noted as an acceptance/verification concern). → encoded in
  REQ-P13-WEB-001/-003/-004.

**Disposition:** **all of 13A–13E are COMPLETE and clarification-clean → the WHOLE Phase-13 spec (all 23
REQs) is ready for AGT-01 `sdd-plan`.** This spec is **COMPLETED**.
