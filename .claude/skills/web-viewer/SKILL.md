---
name: web-viewer
description: >
  Vanilla web companion-viewer skill for the PixelArt Creator platform. Use it
  (invoked by AGT-11 Web Client) to build the browser viewer for a SHARED project:
  a pixel-faithful HTML5 Canvas renderer (the <canvas> width/height ATTRIBUTES set
  to the project's native pixel resolution, CSS width/height set the scaled display
  size, image-rendering:pixelated + ctx.imageSmoothingEnabled=false + INTEGER scale
  factors — nearest-neighbour, no blur, ADR-0036 §4); a minimal WebSocket client
  that connects to the shipped sync_backend, presents the signed share-link token in
  the handshake, JOINs one project, and renders inbound sync_protocol frames; and a
  light VIEW-ONLY interaction set (layer toggle / frame navigation / pan-zoom) that
  emits NO mutation message. No build step, no framework, no bundler (D3). Analog of
  the canvas-view / widget-scaffold skills, for the web_viewer/ peer package.
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity (workflow required)
    - P4 — Consistency
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P9 — Role Separation (declares OUT-OF-SCOPE)
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
    # P5 inherits AGT-11's context discipline; P10 inherits AGT-11's exit status.
  custom:
    - id: C1
      name: Qt-free, view-only, pixel-faithful vanilla client
      requires: The client is vanilla HTML/CSS/JS with NO build step / framework / bundler (D3) and no Qt/ui/data/sync_backend import (ADR-0035 §2); it reaches the backend only over the WS wire. It renders pixel-faithfully (native-res canvas attrs + CSS integer scale + image-rendering:pixelated + imageSmoothingEnabled=false, ADR-0036 §4) and emits ONLY join/leave/read presence — NEVER an update (mutation) frame (WEB-002). All inbound data is untrusted (Article VII): json-only parse, no eval/exec, size/shape caps via the shipped sync_protocol/cloud_validation seams; the token is held in memory only (never localStorage).
      rationale: ADR-0035 §2; ADR-0036 §3/§4; spec REQ-P13-WEB-001/-002/-003/-005; constitution Article VII; a4c7da21 D2/D3.
---

SKILL: web-viewer
================================================================================

PURPOSE:
  Build the vanilla web companion viewer for a shared project: an HTML5 Canvas
  that renders the project's pixels crisply (native-resolution buffer, integer
  CSS scale, nearest-neighbour, smoothing off), a minimal WebSocket client that
  connects to the shipped sync_backend with the signed share-link token, JOINs one
  project, and renders inbound frames, plus a light view-only interaction set
  (layer toggle / frame nav / pan-zoom) that sends no mutation — no build step, no
  framework, no bundler.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the frozen ADR-0035/0036 contract + the pure logic seams (share_token /
  sync_protocol / cloud_validation) + the share link (token + project_id), it
  builds the static client + dev-server glue unaided.

INPUTS:
  - The FROZEN contract: ADR-0036 §1 (token format: header {alg:"HS256",
    typ:"share+jwt"}, claims iss/aud/project_id/scope:"view"/iat/exp/jti; alg never
    trusted from input), §2 (connect flow: load static → read token → open WSS →
    backend verifies in process_request → scoped to project_id → backlog replay),
    §3 (wire = shipped sync_protocol {join,leave,update,presence}; viewer emits no
    update), §4 (render contract). ADR-0035 §2 (import rules).
  - The pure logic/ seams (reused, not re-implemented): logic/sync_protocol.py
    (frame framing + caps), logic/cloud_validation.py (schema/size/depth caps),
    logic/share_token.py (verify semantics — verification is the backend's, the
    client just presents the token string).
  - The share link parts: the token string and project_id (from the URL, e.g.
    /viewer/?t=<token>&p=<project_id>).
  - Researcher a4c7da21 (pixel-render feasibility + short-lived signed bearer token
    + in-memory storage) and acaae022 Q2a/Q3 (browser WS over the existing backend;
    process_request handshake auth). iOS Safari + Android Chrome targets (WEB-003).

OUTPUTS:
  - web_viewer/static/ vanilla client: index.html (a <canvas> + minimal view
    controls), viewer.css (image-rendering:pixelated on the canvas; integer-scaled
    display box; light/dark-agnostic), viewer.js (the render + WS-client + token +
    interaction logic) — no bundler/transpiler, no framework (D3).
  - web_viewer/dev_server.py (stdlib http.server static serving, LOCAL DEV ONLY,
    Qt-free/stdlib-only) when the dev-serving step is in scope.

PRECONDITIONS:
  - ADR-0035/0036 are Accepted (frozen); the check_layering WEB_PKG rule (T13E-P02)
    is in place; the logic/share_token.py + sync_backend handshake seams (T13E-
    B02/B03) exist for the WS/token paths; a file_lock on the web_viewer/ path is
    held.

PROCEDURE:
  1. RENDER (ADR-0036 §4). Set the <canvas> width/height ATTRIBUTES to the
     project's NATIVE pixel resolution (the drawing-buffer size). Set the CSS
     width/height to the scaled DISPLAY size using an INTEGER scale factor. In CSS,
     set `image-rendering: pixelated` on the canvas. In JS, after every getContext
     ("2d") (re)acquisition, set `ctx.imageSmoothingEnabled = false`. Draw the
     project's pixels 1:1 into the native-res buffer; the browser upscales
     nearest-neighbour → crisp, non-interpolated pixels. Never draw into a CSS-sized
     buffer (that reintroduces blur). Holds on iOS Safari + Android Chrome (WEB-003).
  2. CONNECT (ADR-0036 §2). Read the token + project_id from the share link. Open a
     WSS connection to sync_backend presenting the token per the frozen channel
     (query param on the WS URL and/or Authorization: Bearer — the process_request
     handshake hook, acaae022 Q3). Hold the token in a JS variable IN MEMORY only —
     never localStorage (a4c7da21 D2). The backend verifies + scopes the connection;
     on rejection (401/403) surface a clear "link expired / invalid" state and
     render no data.
  3. SUBSCRIBE + RENDER FRAMES (ADR-0036 §3). Send join(project_id); receive the
     backlog replay + ongoing update/presence frames exactly as an editor client
     would. Decode each frame with the shipped sync_protocol framing, size/shape-
     capped by cloud_validation BEFORE use, json-only, NO eval/exec (Article VII).
     Apply decoded layer/frame/canvas state to the Canvas render (step 1).
  4. LIGHT VIEW-ONLY INTERACTION. Offer layer toggle, frame navigation, and
     pan-zoom — all CLIENT-SIDE view operations over already-received state. Emit
     ONLY join/leave/read-oriented presence to the backend; construct NO update
     (mutation) frame anywhere (WEB-002, C1). The viewer can only ever observe.
  5. VERIFY. Run a headless Node/JS-syntax + JS-unit pass (no framework/bundler),
     grep the client for any forbidden Qt/localStorage-token/`update`-frame
     construction, and run the layering gate (check_layering --root . over
     web_viewer, check_cycles --root web_viewer) before asserting done.

DECISION POINTS:
  - Decision WV-D1:
    Condition: the token presentation channel (WS query param vs Authorization:
      Bearer in process_request) or the integer scale factor is fixed by ADR-0036
      §2/§4 + the findings.
    Branch A (grounded): implement it verbatim.
    Branch B (a gap): request the Researcher / an ADR clarification; do NOT guess an
      auth channel or a non-integer scale (P1, Article VII).
    Default: B.
  - Decision WV-D2:
    Condition: an interaction would change project state.
    Branch A: it is out of scope — the viewer is view-only; render the change
      locally only if it is a pure view operation (toggle/nav/zoom) over received
      state, and emit no update frame.
    Default: A (never mutate; never emit update).
  - Decision WV-D3:
    Condition: the drawing buffer would be sized to the CSS display box.
    Branch A: never — size the buffer to the NATIVE resolution and scale by CSS
      (integer) so nearest-neighbour upscaling stays crisp (ADR-0036 §4).
    Default: A.

ERROR HANDLING:
  - Error WV-E1: the token is rejected / expired / wrong-aud / bad-sig (backend
    returns 401/403 at handshake) → surface a clear invalid-link state; render no
    project data; do not retry with a mutated token.
  - Error WV-E2: an inbound frame violates the sync_protocol/cloud_validation caps
    (oversize/malformed/unknown-version) → drop it per the shipped caps; never
    eval/parse-around them (Article VII).
  - Error WV-E3: the logic seams or the frozen contract are absent/ambiguous →
    BLOCKED; name the missing seam/ADR clause; request via AGT-11's orchestrator.

DEPENDENCIES:
  - The frozen ADR-0035/0036 contract; the pure logic/ seams (share_token /
    sync_protocol / cloud_validation, AGT-03); the sync_backend handshake extension
    (AGT-03); scripts/check_layering.py + scripts/check_cycles.py; a headless
    Node/JS-unit runner (no framework/bundler).
  - Production static serving is the 13C Nginx location block (AGT-09); this skill
    provides only the dev http.server glue.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/check_layering.py + scripts/check_cycles.py; JS-unit
    running is a headless Node step, no bundler).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - The signed share-link-token MINT/VERIFY logic (logic/share_token.py) → AGT-03;
    the sync_backend/server.py handshake extension + view-scope guard → AGT-03; the
    sync_protocol/cloud_validation caps themselves → AGT-03 (this skill consumes
    them). No new message vocabulary is invented (ADR-0036 §3).
  - Any Qt/PySide6 UI (the 8K desktop canvas) → AGT-05 / canvas-view (a peer, not a
    substitute). Render-perf strategy → AGT-10.
  - Python web integration tests / render-fidelity / cross-browser + a11y acceptance
    → AGT-04 / AGT-06. Nginx/VPS artifacts + CI wiring + commits → AGT-09. Docs →
    AGT-08.

SOURCES:
  - User requirements: Dossier [[generate-assets-on-demand]] (web-client asset for
    Phase-13 13E), [[phase-13-14-roadmap-extension]] (cross-platform sharing).
  - Frozen contract: docs/adr/0036-web-viewer-wire-and-signed-token-contract.md
    (§1 token, §2 connect flow, §3 wire + view-scope, §4 render contract),
    docs/adr/0035-web-viewer-placement-outside-three-layers.md (§2 import rules).
  - Researcher (via The Researcher, P1): a4c7da21 (image-rendering:pixelated +
    imageSmoothingEnabled=false + integer scale; short-lived signed bearer token;
    in-memory storage), acaae022 Q2a/Q3 (browser WS over the existing backend;
    process_request handshake auth). Spec REQ-P13-WEB-001/-002/-003/-005.
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row),
    constitution Article I/VII. Owned + invoked by agt-11-web-client.
