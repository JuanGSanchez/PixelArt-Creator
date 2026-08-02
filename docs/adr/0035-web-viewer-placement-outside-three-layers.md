# ADR-0035 — `web_viewer/` placement: a new top-level, Qt-free component outside the three layers + the `check_layering` rule (Phase-13 Slice 13E)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-07 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-13-cross-platform` (Slice 13E — web companion viewer) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0027 (sync-backend placement + layering-rule precedent — **MIRRORED here**), ADR-0036 (web viewer wire + token contract) |

## Context

Phase-13 Slice 13E delivers a **web companion viewer** — a lightweight browser client that lets a
collaborator **view + lightly interact with** a **shared** project from a phone browser (the platform-neutral
mobile-access path, since Researcher Q1b confirms there is **no supported native iOS PySide6 deployment in
2026**). The USER decided its three sub-questions on 2026-07-07 (spec §10, research `a4c7da21`): **D1** reuse
the existing stack with **NO new Python dependency** (static client served by the 13C Nginx; data over the
shipped `sync_backend/` `websockets`; stdlib `http.server` for local dev only); **D2** a **signed share-link
token**; **D3** **vanilla HTML/CSS/JS** (no build step / no framework).

REQ-P13-WEB-004 requires the viewer to be a **NEW top-level component OUTSIDE the three desktop layers**,
**headless**, that **MUST NOT import Qt** (nor `ui/`), preserving Article I — an invariant the D1/D2/D3
decisions only reinforce. This is **exactly** the situation ADR-0027 ruled for `sync_backend/`: a first-class
top-level component that is a separate deployable, kept inside the repo so `check_layering` can govern it. This
ADR mirrors that reasoning for `web_viewer/` and rules: (1) placement + package shape; (2) what it may/may not
import; (3) the `check_layering.py` rule update; (4) the invocation.

## Decision

### 1. Placement: a new top-level package `web_viewer/`, outside `pixelart_creator/`

The viewer lives at repo root as **`web_viewer/`** — a sibling of `pixelart_creator/` and `sync_backend/`,
**not** under any of the three layers and **not** inside the desktop wheel (`pyproject`
`packages.find` includes `pixelart_creator*` only; AGT-09 adds `web_viewer` to the `exclude` defence-in-depth
list exactly as `sync_backend*` is excluded). Rationale (mirroring ADR-0027): "outside the three layers" is
realised structurally as a **peer top-level package**, not a fourth layer inside the client; the viewer is an
independently-servable deployable; and keeping it at repo top level keeps it **inside the repo and
CI-scannable** so the layering script governs it and CI can serve/test it.

Package shape:

- `web_viewer/static/` — the **vanilla HTML/CSS/JS** client (`index.html`, `viewer.css`, `viewer.js`, …): no
  build step, no framework (D3). The Canvas pixel-faithful renderer + WS client + signed-token handling.
- `web_viewer/dev_server.py` — a stdlib `http.server` static server for **LOCAL DEV ONLY** (D1). Production
  serving is the 13C Nginx `location` block; this module exists only so a developer can serve `static/`
  without Nginx. Qt-free, stdlib-only.
- thin Qt-free **serving/token glue** (as needed) that reuses the pure `logic/` seams.
- `web_viewer/__init__.py`, `web_viewer/tests/` (the Python web integration tests).

The viewer's project data arrives over the **shipped `sync_backend/` `websockets`** relay (not re-served by
`web_viewer/`), so `web_viewer/` adds **no new Python web-framework dependency** (D1).

### 2. Import rules: headless, Qt-free, MAY reuse pure `logic/`

`web_viewer/` **MUST NOT** import Qt, `pixelart_creator.ui`, `pixelart_creator.data`, or `sync_backend`
(it reaches the backend over the wire — WS — at run time, never by Python import). It **MAY** reuse **pure,
Qt-free `pixelart_creator.logic`** — specifically the new `logic/share_token.py` (token verify) and the shipped
`logic/sync_protocol.py` / `logic/cloud_validation.py` (message framing + caps) — so the wire contract + token
validation are **single-sourced** with the backend (the `sync_protocol` precedent). The three desktop layers
**MUST NOT** import `web_viewer/`.

### 3. `check_layering.py` rule update (Article I) — mirror `BACKEND_PKG`

Owned by **AGT-03/AGT-09** (script edit + CI wiring; specified here by AGT-01). Add a
**`WEB_PKG = "web_viewer"`** constant and extend `FORBIDDEN`:

- **`WEB_PKG` rule:** `QT + ("pixelart_creator.ui", "pixelart_creator.data", "..ui", "..data", BACKEND_PKG)`
  — no Qt, no `ui/`, no `data/`, no `sync_backend`; MAY reuse pure `logic/`.
- **Reciprocal client rule:** add `WEB_PKG` to the forbidden sets of `logic`, `data`, and `ui` (each already
  forbids `BACKEND_PKG`) — no client layer imports `web_viewer`.
- **Peer decoupling:** add `WEB_PKG` to the `BACKEND_PKG` forbidden set — the backend does not import the web
  serving layer (the two non-three-layer deployables communicate over the wire).

### 4. Invocation (CI, AGT-09)

Unchanged in shape from ADR-0027's twin run: `check_layering.py --root pixelart_creator` (client three layers)
and `--root .` (governs `sync_backend/` **and now** `web_viewer/` via `parts[0]`). `check_cycles.py` runs a
third time — `--root web_viewer` — once the package lands (generic over `--root`; no code change). Until
`web_viewer/` lands the rule is **dormant-ready**; the baseline (2026-07-07, this ADR's session) is
`--root pixelart_creator` exit 0 / 178 modules, `--root .` exit 0 / 3, `check_cycles --root pixelart_creator`
exit 0 / 179, `--root sync_backend` exit 0 / 3 — all green, so the rule gates the new code when it arrives
(Article I §4).

## Alternatives Considered

- **`web_viewer/` as a fourth dir inside `pixelart_creator/` (e.g. `pixelart_creator/web_viewer/`).**
  Rejected: it would ship inside the desktop wheel and read as a fourth layer. A peer top-level package is a
  cleaner separate deployable while staying CI-scannable (the ADR-0027 rationale).
- **Serve the client from the `websockets` server in-process (hand-rolled static in `process_request`).**
  Rejected as the *production* path: research `a4c7da21` D1 confirms the `websockets` v16 server is **not** a
  general HTTP server (only `process_request`/`process_response` hooks) and the vendor recommendation is a
  reverse proxy (Nginx) for static content. The 13C Nginx serves the static client; a stdlib `http.server`
  covers local dev only. **No FastAPI/aiohttp** (would add a dependency — violates D1).
- **A build-tooled SPA (React/Vue).** Rejected by D3 (USER decision): a read-mostly viewer is low-complexity;
  vanilla avoids the JS build/ecosystem upkeep a Python-only team would own, and client-only SPAs are trending
  toward "legacy" (a4c7da21 D3). No bundler/transpiler.
- **A separate repository for the viewer.** Rejected this phase: it would push the layering/CI governance out
  of this repo's gate. A top-level package keeps `check_layering --root .` authoritative over it.

## Consequences

**Positive.** The viewer is a genuine, independently-servable, first-class component outside the three layers,
yet CI-scannable and Qt-free by a provable layering rule (the `sync_backend/` model). Article I is preserved;
no new Python dependency enters the manifest (D1); the wire + token contract is single-sourced in pure `logic/`
with the backend. The vanilla static client has no build step (D3), so CI needs no JS toolchain beyond an
optional Node unit step.

**Negative / risk.** A third top-level package widens the repo's mental surface; CI now runs `check_cycles`
three times and `check_layering --root .` governs two non-three-layer packages. The `web_viewer/` frontend is
owned by a **newly-generated** `agt-11-web-client` agent (The Metaprompter, sequenced in `tasks.md` after this
ADR + the layering rule) — a coordination dependency, not an architectural one.

## Grounding

- Spec §2/§2b (13E scope + D1/D2/D3 DECIDED), §4 REQ-P13-WEB-001..005 (esp. WEB-004 placement, WEB-005 token),
  §5 (Article I/VII invariants), §8 DEP-5; `acceptance.md` SC-P13-WEB-004-1; `traceability.md` WEB rows.
- Researcher `acaae022` Q2a (browser WS viewer over the existing backend; iOS Safari + Android Chrome), Q1b
  (no native iOS PySide6 path); `a4c7da21` D1 (reuse existing stack / reverse proxy for static / no new dep),
  D3 (vanilla).
- **ADR-0027** (`sync_backend/` placement + `BACKEND_PKG` layering rule — the mirrored precedent);
  constitution Article I (three layers + gate), IV (CI-testable), VII (untrusted input), X §1 (`WEB` tag),
  XI (extensibility). Shipped `scripts/check_layering.py` (`BACKEND_PKG` rule to mirror), `pyproject.toml`
  (`sync_backend*` wheel exclusion to mirror).

---

## Addendum A (2026-07-07) — scope of "MAY reuse pure `logic/`" for the browser client

Clarifying §2 in light of ADR-0036 Addendum A.4. The "MAY reuse pure `pixelart_creator.logic`" allowance is a
**Python-side** reuse: it applies to `web_viewer/`'s Qt-free Python serving/token glue and any minting tool
(which `import`s `logic/share_token`, `logic/sync_protocol`, `logic/cloud_validation`). The **browser** portion
(`web_viewer/static/*.js`, D3 vanilla) obviously cannot `import` Python at runtime; it reuses the wire + op
formats **by contract** (single-sourced in `logic/`), re-implementing the `sync_protocol` decode and the
`realtime_apply` op-replay/LWW read path in vanilla JS. This is a client-side implementation cost, not a
layering exception: Article I is unaffected (the browser reuses no Qt and imports nothing), and `check_layering`
governs only the Python surface. No backend serialization change is implied (ADR-0036 A.7).
