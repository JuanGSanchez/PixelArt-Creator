# ADR-0036 — Web viewer client↔backend serialization + signed share-link-token contract (Phase-13 Slice 13E)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-07 |
| Author | AGT-01 (Architecture) — **wire shape + token format coordinated with AGT-03** (the implementer of `logic/share_token.py` + the `sync_backend/` handshake extension) |
| Feature | `phase-13-cross-platform` (Slice 13E — web companion viewer) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0035 (`web_viewer/` placement), ADR-0027 (`sync_backend/` + `sync_protocol` framing), ADR-0026 (cloud-port; OAuth-PKCE lives in the desktop client, NOT reused here) |

## Context

The web viewer (ADR-0035) is a **vanilla HTML/CSS/JS** client that views a **shared** project over the
**shipped `sync_backend/` `websockets`** relay, gated by a **per-project signed share-link token** (spec §10:
D1 no new dependency, D2 signed token, D3 vanilla). This ADR **freezes the wire contract** the vanilla client
and the `websockets` backend share so both sides can be built against a stable surface, and **freezes the
signed-share-link-token format + validation**. It is coordinated with **AGT-03**, who implements the pure
`logic/share_token.py` seam and the `sync_backend/server.py` handshake extension. The token model is **not
full OAuth and has no login flow** (D2); the desktop client's Phase-10 OAuth-PKCE credentials are **not**
transferable to a browser session and are **not** reused here (a4c7da21 D2).

Two invariants bind: **D1** (no new Python dependency — the token crypto must be stdlib-only) and **Article
VII** (all web input is untrusted; no `eval`/`exec`; the signing secret is never committed).

## Decision

### 1. The signed share-link token — stdlib HMAC-SHA256, minted + verified in pure `logic/`

The token is a **compact, URL-safe, HMAC-SHA256-signed bearer token** (a JWT-shaped `header.payload.sig`,
base64url-encoded, **no external JWT library** — stdlib `hmac` + `hashlib` + `base64` + `json` only, honouring
D1). It is minted + verified by a **NEW pure module `logic/share_token.py`** (zero Qt, zero `data/`, a
`logic/` leaf over `logic/constants`), imported by **both** `sync_backend/server.py` (verify) and the
`web_viewer/` glue / desktop share action (mint) — single-sourcing the format (the `sync_protocol` precedent).

- **`header`** — `{"alg": "HS256", "typ": "share+jwt"}` (fixed; `alg` is validated, never trusted from input —
  no "alg=none" acceptance).
- **`payload` (claims)** — `{"iss": <issuer>, "aud": <audience>, "sub"/"project_id": <shared-project-id>,
  "scope": "view", "iat": <issued>, "exp": <expiry>, "jti": <unique-id>}`. `scope: "view"` marks the token
  **read-only** (used by §3 to reject mutations). `project_id` scopes the token to **exactly one** shared
  project.
- **`sig`** — `HMAC-SHA256(base64url(header) + "." + base64url(payload), SECRET)`.
- **Secret management (Article VII §3).** `SECRET` is an **operator-provided secret** supplied via env/config
  to the backend (and the minting side), **never committed** to the repo. Verify uses **constant-time**
  comparison (`hmac.compare_digest`).
- **Lifetime.** `exp - iat <= SHARE_TOKEN_MAX_TTL_S` (a named constant, §Article II) — short-lived per
  a4c7da21 D2. A token minted with a longer TTL is rejected.

`logic/share_token.py` public surface (frozen): `mint(claims, secret) -> str`,
`verify(token, secret, *, expected_iss, expected_aud, now) -> Claims`, `ShareTokenError(ValueError)`.
`verify` fully validates **signature (constant-time) + `alg` + `exp` (not past `now`) + `iss` + `aud`**, and
returns the parsed claims (incl. `project_id`/`scope`); any failure raises `ShareTokenError` and yields **no
claims**. Parsing is `json`-only — **never `eval`/`exec`** — with a max-length cap before decode.

### 2. Serving + connect flow

1. A **share action** (desktop or an operator tool) mints a token for a shared `project_id` with a short
   `exp` and hands out a **share link** (`https://<host>/viewer/?t=<token>&p=<project_id>` — served static by
   the 13C Nginx / dev `http.server`).
2. The vanilla client loads (static assets), reads the token, and opens a **WSS** connection to
   `sync_backend/` presenting the token (query param on the WS URL and/or `Authorization: Bearer` — the
   backend accepts it in the `websockets` **`process_request`** handshake hook, the a4c7da21/Q3 pattern).
3. The backend **verifies the token via `logic/share_token.verify`** before accepting the connection; on
   failure it **rejects the handshake (HTTP 401/403 via `process_request`)** and serves **no** project data.
4. On success the backend **scopes the connection to the token's `project_id`** and replays that project's
   current shared state (the existing backlog-replay-on-JOIN path, ADR-0027 §4) — read-mostly.

### 3. Wire contract (client ↔ backend) — reuse `sync_protocol`, add a view-scope guard

The viewer reuses the **shipped `logic/sync_protocol.py` framing** (`{join, leave, update, presence}`,
versioned, size-capped-before-decode) — **no new message vocabulary is invented**; the viewer is a consumer of
the same relay. The frozen viewer-side contract:

- **Inbound to client (backend → viewer):** the project's current state via the JOIN backlog replay + ongoing
  `update`/`presence` frames, exactly as an editor client receives them. The client decodes them read-only and
  renders (layers/frames/canvas) via Canvas.
- **Outbound from client (viewer → backend):** **only** `join(project_id)` / `leave` / read-oriented
  `presence` (optional). The client emits **no `update` (mutation) frame** (WEB-002).
- **View-scope enforcement (backend, WEB-002/-005).** `sync_backend/server.py` is **extended** (not
  re-authored) so that on a **`scope: "view"`** connection it **rejects any mutation frame** (`update`) with a
  defined error and serves no mutation — a view-scoped token can only ever observe. Every inbound frame is
  still validated by the shipped `logic/cloud_validation.py` / `sync_protocol` caps (schema/size/depth) —
  **untrusted input, `eval`-free** (Article VII). A token scoped to project A can never reach project B (the
  connection is bound to `project_id` at handshake).

### 4. Client render contract (D3; a4c7da21 pixel-render feasibility)

The vanilla client renders **pixel-faithfully**: the `<canvas>` `width`/`height` **attributes** are set to the
project's **native pixel resolution**; CSS `width`/`height` set the scaled display size; `image-rendering:
pixelated` + `ctx.imageSmoothingEnabled = false` + **integer scale factors** ensure crisp, non-interpolated
pixels. This holds on **iOS Safari + Android Chrome** (WEB-003; iOS Safari is a documented real-device check).

## Alternatives Considered

- **Reuse Phase-10 OAuth-PKCE (ADR-0026) for the viewer.** Rejected (D2): the desktop keyring credentials are
  not transferable to a browser session; a full auth-code+PKCE login flow is overkill for a link-share view.
  A short-lived signed bearer token is the documented minimal standard (a4c7da21 D2).
- **A JWT library (PyJWT / python-jose).** Rejected (D1): would add a Python dependency. Stdlib
  `hmac`/`hashlib` implements HS256 verification in a small, auditable pure module — no dependency.
- **A brand-new bespoke WS message set for the viewer.** Rejected: the shipped `sync_protocol` framing +
  `cloud_validation` caps already carry the shared-project state and are `eval`-free; inventing a parallel
  vocabulary would duplicate the caps and risk drift. The viewer is a read-mostly consumer of the existing
  relay + a view-scope guard.
- **`localStorage` for the token.** Discouraged (a4c7da21 D2): in-memory (JS variable) is the correct default
  for a short-lived bearer token; the client holds it in memory for the session, not `localStorage`.

## Consequences

**Positive.** The wire + token contract is frozen and single-sourced in pure `logic/` (`share_token` +
`sync_protocol`), so the vanilla client, the backend handshake, and any minting tool all agree by construction;
no new dependency (D1); untrusted web input is `eval`-free and view-scoped (Article VII); the token is
short-lived, signature/`iss`/`aud`/expiry/scope-validated (a4c7da21 D2). The render contract guarantees crisp
pixels cross-browser (D3).

**Negative / risk.** HMAC (symmetric) means the signing secret must be shared between the minting side and the
backend — acceptable for a self-hosted single-operator deployment (the 13C VPS model); a future multi-issuer
need would move to asymmetric signing (a documented future evolution behind the same `share_token` seam). The
`sync_backend/server.py` handshake extension is the **one** backend code change of Phase 13 (13C is
config-only; this is 13E) and must preserve the shipped multi-client convergence for editor clients — covered
by the Python web integration test (AGT-04) + the existing backend suite.

## Grounding

- Spec §2b / §10 (D1 no new dependency, D2 signed share-link token, D3 vanilla + pixel-faithful), §4
  REQ-P13-WEB-001/-002/-005, §5 (Article VII invariant), §8 DEP-5; `acceptance.md` SC-P13-WEB-001-1/-002-1/
  -005-1/-005-2; `traceability.md` WEB rows.
- Researcher `a4c7da21` D1 (websockets not a general HTTP server; reverse proxy; no new dep), D2 (short-lived
  signed bearer token; HTTPS; validate sig+`iss`+`aud`+`exp`; in-memory storage; not full OAuth), D3 +
  pixel-render feasibility (`image-rendering: pixelated`, `imageSmoothingEnabled=false`, integer scale);
  `acaae022` Q2a (browser WS over the existing backend), Q3 (`process_request` handshake auth pattern).
- **ADR-0027** (`sync_protocol` framing + backend never stores tokens — the viewer token is verified, never
  stored), **ADR-0035** (`web_viewer/` placement), ADR-0026 (Phase-10 OAuth — NOT reused). Constitution
  Article II (named TTL/cap constants), VII (untrusted input, no `eval`/`exec`, no committed secret), I
  (`share_token` is a pure `logic/` leaf).

---

## Addendum A (2026-07-07) — six underspecified contract details RESOLVED before build

During Slice-13E asset generation the Metaprompter surfaced six contract points left ambiguous by the frozen
Decision above. This addendum resolves each with a concrete, testable ruling **inside the already-decided
scope** (vanilla HTML/CSS/JS, signed share-link token, VIEW-ONLY, over the existing `sync_backend/`
`websockets` relay, no new Python dependency). No product direction is reopened. Grounded in the shipped
`logic/sync_protocol.py`, `logic/realtime_apply.py`, `logic/cloud_validation.py`, and `sync_backend/server.py`.

### A.1 — Token channel on the WS handshake (resolves §2 step 2 ambiguity)

**Decision: the share-link token travels as a query-string parameter `token` on the WSS URL** —
`wss://<host>/<ws-path>?token=<base64url-token>`. It is read in the backend's `websockets`
`process_request(connection, request)` hook by parsing `request.path` with `urllib.parse.urlsplit` +
`parse_qs` and taking `token`. The alternative `Sec-WebSocket-Protocol` subprotocol channel is **rejected**
as the primary: a browser `new WebSocket(url, protocols)` can carry the token as a fake subprotocol, but the
shipped `serve(...)` would then have to *select and echo back* a matching `Sec-WebSocket-Protocol` response
header (via `select_subprotocol`) or the browser aborts the connection — extra negotiation machinery and a
token smuggled through a protocol-name field. The query string is a single `urlsplit`/`parse_qs` read with no
negotiation, works out of the box with the shipped `serve` (which already surfaces `request.path`), and is safe
under WSS (the full URL including query is TLS-encrypted on the wire). **The `&p=<project_id>` hint in the
share link (§2 step 1) is NEVER trusted for scoping** — the authoritative project identity is the verified
token claim (A.3); `p` is only a convenience for the static client.

### A.2 — Query-string token log-exposure mitigation (contract requirement)

Because the token rides the query string, the following are **mandatory contract requirements** (not optional):
(1) **Nginx** (13C production `location` for the WS upgrade) MUST NOT persist the query string — use
`access_log off;` for the WS-upgrade location, or a custom `log_format` that omits `$query_string`/`$args`, or
a `map` that redacts `token=…`. (2) **Backend** logging MUST NOT emit `request.path` verbatim for the handshake
— log only the path component (query stripped) or a `token=<redacted>` form. (3) The backend **verifies, never
stores** the token (ADR-0027 invariant reaffirmed). (4) **Short TTL** (`SHARE_TOKEN_MAX_TTL_S`, §1) bounds the
exposure window of any leaked link. A subprotocol channel would sidestep (1)/(2); we accept the query-string
channel *with* these mitigations as the simpler, shipped-server-native choice.

### A.3 — Canonical project-identity claim (resolves §1 `sub`/`project_id` ambiguity)

**Decision: `project_id` is the single canonical, authoritative claim** the backend scope-check reads. The
mint side ALSO sets `sub` to the identical value for JWT convention/interop, but **`sub` is advisory; the
backend binds and enforces on `project_id` only** (no divergence is possible because mint sets them equal, and
verify treats a `project_id`/`sub` mismatch as invalid). **Mapping to the wire: `project_id == document_id`.**
The token's `project_id` claim IS the exact string used as `doc` in `sync_protocol` JOIN/UPDATE frames — the
shared-project id serves directly as the sync `document_id` (aligning with `validate_membership`'s `project_id`
field and `sync_protocol`'s `document_id`). The backend, after verifying the token, binds the connection to
`claims["project_id"]` and **rejects any JOIN whose `doc` != the bound value** — closing "a token for project A
can never reach project B" structurally. (Escape hatch for a deployment that distinguishes the two: carry an
explicit `document_id` claim in the verified token; default is identity.)

### A.4 — View-client wire payload (BIGGEST RISK — resolves §3 ↔ §4 tension)

**Decision: the view client JOINs and receives the SAME `sync_protocol` frames an editor gets** — the
backlog-replay-on-JOIN (`sync_backend`'s `store.backlog(document_id)` → all persisted UPDATE frames) followed by
ongoing `update`/`presence` frames — and reconstructs the raster **client-side**. NO distinct view-snapshot
serialization is added (rejected: it would be a new backend serialization duplicating the op-codec, risking
drift — Article-VII caps would have to be re-implemented for a second format). The concrete render input is
therefore the shipped op vocabulary, decoded in JS:

1. Decode the outer `sync_protocol` frame (plain JSON: `{v:1, kind, doc, blob|presence}`) — trivial in JS.
2. For an `update` frame, base64-decode `blob`, JSON-parse the op-codec envelope (`realtime_apply.encode_update`
   output: `{v:1, ops:[…]}`), yielding the op list: `raster` (frame/layer/tile_x/tile_y/tile_w/tile_h + base64
   RGBA `px` + `c`(logical_clock)/`s`(site_id)), `attr` (frame/layer/attr/value), `order` (frame/order-list),
   `meta`.
3. Replay ops into per-`(frame_index, layer_id)` RGBA tile buffers, compositing tiles at
   `(tile_x*CRDT_TILE_SIZE_PX, tile_y*CRDT_TILE_SIZE_PX)`.

**Critical grounding fact / accepted cost (FLAGGED):** the shipped *reconstruction* path
(`realtime_apply.apply_remote` → `convergence.apply_operations` over a `Document`) is **Python-only** — the
vanilla-JS client (D3) cannot import it at runtime. So the *wire format* is single-sourced/reused, but the
*replay + LWW winner selection* MUST be **re-implemented in vanilla JS**. This is a **client-side implementation
cost borne by `agt-11-web-client`, NOT a backend change** — no change to `sync_protocol`, the op-codec, the
store, or the broadcast path is required. The JS replay MUST mirror `RealtimeState.accept`: per register key
(`raster:{frame}:{layer}:{tx}:{ty}`, `attr:{frame}:{layer}:{attr}`, `order:{frame}`, `meta:{key}`) keep the
winner with the highest stamp `(logical_clock, site_id, pixels)` compared lexicographically; drop an op that is
not strictly newer than the applied stamp. In-order backlog apply is the acceptable *floor* for a mostly-static
shared project, but mirroring the LWW rule is REQUIRED so concurrent live editor UPDATEs converge identically
(strong eventual consistency). The client remains VIEW-ONLY: it emits only `join`/`leave` (and optional read
`presence`), never `update` (WEB-002).

### A.5 — Layer/frame structure for light interaction (confirms client-side, no mutation)

**Confirmed: the shipped frames carry enough per-layer / per-frame structure for client-side light interaction
with NO new message and NO mutation.** `raster`/`attr`/`order` ops all carry `frame_index` and `layer_id`, and
`order` ops carry the per-frame layer stacking order; `attr` ops carry per-layer attributes (e.g. visibility,
opacity, name) as `(attr, value)`. Therefore the view client derives the layer list + frame set purely by
replaying the backlog, and implements **layer-toggle** (locally skip a `layer_id` when compositing —
view-local state, never a wire message), **frame-navigation** (composite a chosen `frame_index`), and
**pan/zoom** entirely CLIENT-SIDE. No backend round-trip and no mutation frame is involved, preserving
VIEW-ONLY. (If a future interaction needed data the ops do not carry, it would be scoped down to what IS
available rather than adding a mutation — not needed here.)

### A.6 — iOS device-check objective pass criterion (makes T13E-B08 acceptance objective)

Refines §4 for `devicePixelRatio (DPR) > 1`. **Rendering rule:** set the `<canvas>` **backing-store attributes**
`canvas.width = source_px_w`, `canvas.height = source_px_h` (one texel per source pixel); draw the reconstructed
raster 1:1 with `ctx.imageSmoothingEnabled = false`; set **CSS** `style.width = source_px_w × S`,
`style.height = source_px_h × S` where `S` is a positive **integer** display scale; apply
`image-rendering: pixelated`. On iOS Safari DPR ∈ {2, 3} is an integer, so the effective source→physical mapping
is `S × DPR` (integer) and `pixelated` forces nearest-neighbour on both the CSS upscale and the DPR upscale — no
interpolation. **Objective pass criterion for T13E-B08** (all must hold on a real iOS Safari device at
DPR > 1): (a) `canvas.width/height` == source pixel resolution; (b) computed CSS size == `source_px × S` with
`S` integer; (c) `getComputedStyle(canvas).imageRendering === 'pixelated'`; (d) `ctx.imageSmoothingEnabled ===
false`; (e) **edge-sharpness sample:** every source pixel occupies exactly an `S × DPR` block of physical device
pixels, each block being a single flat RGBA equal to the source pixel — i.e. NO anti-aliased/blended transition
row or column at any pixel boundary. Fail = any interpolated boundary or non-integer block. This is verifiable
by a screenshot pixel-grid sample; it removes "looks crisp" subjectivity.

### A.7 — Build-can-proceed statement

The build can proceed against this tightened contract with **NO backend change beyond the T13E-B03 handshake
extension** (token verify in `process_request` + bind connection to the verified `project_id` + reject
cross-`doc` JOIN + reject `update` on a `scope:"view"` connection + token-redacting logging). `sync_protocol`,
the `realtime_apply` op-codec, `cloud_validation` caps, the store, and the broadcast path are **unchanged**. The
only material shift is that the CRDT replay is re-implemented in vanilla JS on the client (A.4) — a
`agt-11-web-client` cost, explicitly not a backend/serialization change. Article I (web_viewer Qt-free; the
Python token glue MAY reuse pure `logic/`, the browser reuses the *format* by contract) and Article VII
(untrusted handshake/frames, `eval`-free, capped) are both preserved.

### A.8 — Updated per-task guidance

- **AGT-03 / T13E-B02 (`logic/share_token.py`):** mint/verify with `project_id` as the canonical claim (also
  set `sub` = same value; verify rejects a `project_id`/`sub` mismatch); pin `alg=HS256` (never trust input
  `alg`); enforce `exp - iat <= SHARE_TOKEN_MAX_TTL_S` and `exp > now`; validate `iss`/`aud`; `hmac.compare_digest`
  constant-time; max-token-length cap **before** any base64/JSON decode; `ShareTokenError`. Add
  `SHARE_TOKEN_MAX_TTL_S` and the max-token-length cap to `logic/constants.py` (Article II). Stdlib only (D1).
- **AGT-03 / T13E-B03 (`sync_backend/server.py` handshake):** add a `process_request` hook to `serve(...)` that
  `urlsplit`/`parse_qs`-reads `token` from `request.path`, calls `share_token.verify(token, SECRET,
  expected_iss=…, expected_aud=…, now=…)`, and on failure returns an HTTP **401/403** response to reject the
  handshake (serve no data). On success stash `claims["project_id"]` + `claims["scope"]` on the connection; in
  `_dispatch`, **reject a JOIN whose `message.document_id` != the bound `project_id`** and **drop/close any
  `UPDATE` frame when `scope == "view"`** (WEB-002/-005). Do NOT trust the `p` query hint. Redact `token` in all
  handshake logging (A.2). Do NOT modify `sync_protocol`, the op-codec, or the store.
- **agt-11-web-client / T13E-B04 (`web_viewer/static/`):** open `wss://…?token=…`; hold the token **in memory
  only** (no `localStorage`); decode `sync_protocol` frames, base64-decode + JSON-parse the op envelope, and
  **replay ops with the A.4 LWW winner rule** into per-`(frame,layer)` RGBA buffers honouring `order`/`attr`
  (visibility) ops; composite the current frame's visible layers to the canvas sized per A.6; implement
  layer-toggle + frame-nav + pan/zoom **client-side** (A.5); **never emit an `update` frame**.
- **AGT-04 / T13E-B06 (Python web integration test):** at the handshake — a valid token accepts, an
  invalid/expired/wrong-`aud`/wrong-`iss`/tampered-sig token is **rejected 401/403** and gets no data; a
  `scope:"view"` connection has its `update` frame **rejected**; a token bound to project A **cannot JOIN**
  document B; the shipped editor multi-client convergence is **unbroken**. Token never appears in logs.
- **AGT-04/AGT-06 / T13E-B07:** JS-side replay correctness (op-replay + LWW winner selection reproduces the
  reference `converge`/`apply_remote` raster for a fixture op-log) and, where applicable, a11y of the viewer
  controls; both drivable headless/CI.
- **AGT-06 / T13E-B08 (device check):** assert the **A.6 objective criterion** (a)–(e) on iOS Safari at
  DPR > 1 — pass only when every source pixel is an `S × DPR` flat block with no interpolated boundary.
