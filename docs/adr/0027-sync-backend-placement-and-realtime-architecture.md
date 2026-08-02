# ADR-0027 — Sync-backend placement + real-time architecture: `sync_backend/` outside the three layers, the transport port, and the layering-rule update (Slice C)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-10-cloud-collaboration` (Slice C) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0026 (cloud-port), ADR-0028 (hybrid convergence + CRDT lib) |

## Context

Phase-10 Slice C delivers an **actual real-time sync backend** — a real server/component that relays and
**persists** CRDT updates + awareness/presence across multiple clients (REQ-P10-BACKEND-001/-002), NOT
merely a loopback shim. The spec adjudicated (CL-B4, FLAG-BACKEND) that this backend is a **NEW
first-class, top-level component that sits OUTSIDE the desktop app's three-layer (`logic/`/`data/`/`ui/`)
architecture** and that **AGT-01 owns its placement + this ADR**: where it lives, its framework, how it is
spun up in-process/subprocess for CI, and the client↔backend protocol. It **MUST be CI-testable over
localhost** (in-process/subprocess, loopback integration tests) so real-time stays **in the CI gate** —
distinct from the out-of-CI live-provider OAuth (CL-B2). The desktop client's three-layer purity must be
preserved: the client reaches the backend only through the ZERO-Qt `data/cloud/` **transport port**
(REQ-P10-DATA-010). The convergence layer is pure/deterministic and lives in `logic/` (ADR-0028).

This ADR rules: (1) the backend's repository placement + packaging; (2) its framework + transport; (3) the
client-side transport port + loopback/real split; (4) the client↔backend protocol + persistence; (5) the
**layering-rule update** (`check_layering.py` / `check_cycles.py`) that governs the new package while
keeping the client's three-layer purity intact; (6) backend untrusted-input defence + no-tokens rule; and
(7) the Article VI split (real-time re-enters the per-frame budget — the AGT-10 obligation).

## Decision

### 1. Placement: a new top-level package `sync_backend/`, outside `pixelart_creator/`

The backend lives at repo root as **`sync_backend/`** — a sibling of `pixelart_creator/`, **not** under
any of the three layers. It is a separate deployable, so it is **excluded from the desktop wheel**
(`pyproject` `packages.find` includes `pixelart_creator*` only; AGT-09 adds `sync_backend` as a separate
package / test-installed target). Rationale: "outside the three layers" is realised structurally (a peer
top-level package, not a fourth layer inside the client), the backend can be deployed/run independently,
and — critically — placing it at repo top level keeps it **inside the repo and CI-scannable** so the
layering scripts can govern it (§5) and CI can spin it up.

Modules: `sync_backend/server.py` (the relay/persist server + spin-up API), `sync_backend/store.py`
(backend-side persistence of CRDT updates + presence), `sync_backend/__init__.py`.

### 2. Framework + transport: asyncio WebSocket relay

The backend is an **asyncio WebSocket relay** (the Researcher's simplest real-time path — §4.5) using the
well-maintained **`websockets`** library. It broadcasts encoded CRDT updates to connected peers of a shared
document and relays ephemeral awareness/presence, and it **persists** the update log per document so a
late-joining client can catch up. WebRTC/P2P is a documented future alternative behind the same client
transport port; it is not built this phase.

### 3. Client transport port + loopback/real split (REQ-P10-DATA-010)

`pixelart_creator/data/cloud/transport.py` (ZERO-Qt, `data/`) defines a provider-agnostic **`TransportPort`**
carrying CRDT updates + awareness/presence between the client and the backend:

- **`data/cloud/loopback_transport.py`** — an in-memory / loopback transport implements the port so the
  backend↔client loop is exercised **in CI over loopback with no external network/credentials**.
- **`data/cloud/ws_transport.py`** — a real WebSocket transport implements the **same** port; it is
  credential-/network-gated (`pytest.mark.cloud_live`), **OUT of the CI gate**.

No transport/provider type leaks above the port (REQ-P10-DATA-007); `logic/`/`ui/` see only the port's
abstractions. Every inbound CRDT-update blob / presence payload is validated (schema + caps,
`MAX_CRDT_UPDATE_BYTES`, no eval/exec) by the pure `logic/cloud_validation.py`.

### 4. Client↔backend protocol + persistence

The wire protocol is a small, versioned, JSON-framed message set — `{join, update, presence, sync_request,
sync_response, leave}` — whose **message vocabulary + validators are pure and live in
`logic/cloud_validation.py`**, so **both** the client transport (`data/cloud/`) and the backend
(`sync_backend/`) import the same pure validators and message schema (DRY, single source of the caps). The
backend persists the ordered update log + latest presence per `document_id` in `sync_backend/store.py`
(in-memory for CI; file-backed for a running server). CRDT-update payloads are opaque bytes to the backend
except for schema/size/depth validation — the backend never decodes artwork, and multiple clients over the
loopback backend converge to an identical `Document` via the client-side convergence layer (ADR-0028,
REQ-P10-LOGIC-006/-007).

### 5. Layering-rule update (Article I; `check_layering.py` / `check_cycles.py`)

`scripts/check_layering.py` is updated (this ADR) so the new package is governed while the client's
three-layer purity holds:

- **`data/cloud/` needs no new rule** — it is a normal `data/` subpackage, already governed by the `data`
  rule (zero Qt, no `ui/` import); no provider SDK/transport type leaks above the port by construction.
- **New `BACKEND_PKG = "sync_backend"` rule:** the backend must **not** import Qt, `pixelart_creator.ui`,
  or `pixelart_creator.data` (it never touches the client's OS-keyring tokens or provider adapters —
  REQ-P10-BACKEND-002); it **MAY** reuse pure `pixelart_creator.logic` (convergence + `cloud_validation`).
- **Reciprocal client rule:** `logic/`, `data/`, and `ui/` may **not** import `sync_backend` — the desktop
  client reaches the backend only over the `data/cloud/` transport port at run time, never by a Python
  import.
- **Invocation (CI, AGT-09):** run layering twice — `--root pixelart_creator` (client three layers) and
  `--root .` (governs `sync_backend/` via `parts[0] == "sync_backend"`; client files are skipped in that
  run). Run cycles twice — `--root pixelart_creator` and `--root sync_backend` (the cycle check is generic
  over `--root`; no code change). Both scripts verified **exit 0** on the current tree after the rule
  update (client scan 120 modules; whole-repo scan 0 governed modules until the package lands; cycles 121
  modules), so the rules are dormant-ready and gate the new code when it arrives (Article I §4).

### 6. Untrusted input + no tokens on the backend (REQ-P10-BACKEND-002, Article VII)

The backend treats **every** ingested payload (CRDT update, presence, comment) as untrusted:
schema-validated against strict **size/depth/dimension/byte caps** (`MAX_CRDT_UPDATE_BYTES`,
`MAX_COMMENT_BYTES`, `MAX_SHARED_MEMBERS`), **never `eval`/`exec`**, malformed/oversized → rejected with a
clear error — never a crash, code execution, or memory exhaustion. Bounds are named constants (Article II).
The backend **never receives or stores provider OAuth tokens**: tokens stay in the client's `data/cloud/` +
OS keyring (CL-B3, ADR-0026), enforced by the §5 rule (backend cannot import `data/`).

### 7. Article VI split — real-time re-enters the per-frame budget (AGT-10 obligation)

Batch Slice-A/B cloud/sync + hybrid convergence are **off** the per-frame render loop
(REQ-P10-LOGIC-004/-006). **Slice C is the one place the 16 ms `FRAME_BUDGET_MS` re-enters cloud scope:**
real-time **remote-patch application** (REQ-P10-LOGIC-007) and the **live-cursor overlay draw**
(REQ-P10-UI-013) run on the interactive loop. This ADR records the **REQUIRED AGT-10 per-frame assessment
(FLAG-PERFRAME, DEP-3):** AGT-10 must profile remote-patch apply + cursor draw against the 16 ms budget and
direct batching/coalescing/dirty-rect strategy; the budget is never relaxed. A **CI perf-gate** over the
Slice-C real-time apply/cursor path on the 8K canvas is recommended (AGT-10 `frame-profile` + AGT-09 CI).

## Alternatives Considered

- **Backend as a fourth dir inside `pixelart_creator/` (e.g. `pixelart_creator/sync_backend/`).** Rejected:
  it would ship inside the desktop wheel and read as a fourth layer; a peer top-level package is a cleaner
  separate deployable while staying CI-scannable.
- **Backend in a separate repository.** Rejected this phase: it would push the backend↔client loop **out**
  of the CI gate, violating CL-B4 (real-time must stay CI-testable over localhost). A top-level package
  keeps the loopback integration tests hermetic and in CI.
- **No real backend — only an in-memory loopback shim.** Rejected: CL-B4 requires an *actual* relaying/
  persisting server; the loopback transport is the CI harness, not the product.
- **Backend imports `data/cloud` validators.** Rejected: it would force the backend to depend on the
  client's `data/` layer (network/keyring). The shared validators are moved to **pure `logic/`** so both
  sides import them without the backend touching `data/`.
- **WebRTC/P2P now.** Deferred: a WebSocket relay is the simplest correct real-time path (Researcher §4.5);
  WebRTC is a future transport behind the same client port.

## Consequences

**Positive.** The backend is a genuine, independently-deployable, first-class component outside the three
layers, yet CI-testable over localhost (in-process/subprocess + loopback integration tests). The client's
three-layer purity is provably preserved by the updated `check_layering` rule; tokens never reach the
backend; untrusted payloads cannot execute code or exhaust memory. Shared pure validators keep Article VII
caps single-sourced.

**Negative / risk.** A new top-level package + two new runtime deps (`websockets` for the backend/transport;
the CRDT lib per ADR-0028) widen the manifest (AGT-09/AGT-01 decision; Article VII/VII implications). The
Article VI per-frame re-entry (Slice C) is a real perf risk that **must** be discharged by AGT-10
(FLAG-PERFRAME) before Slice C ships. CI must spin up/tear down the backend cleanly (in-process/subprocess);
flaky async teardown is the main CI risk (mitigated by deterministic loopback + timeouts).

## Grounding

- Spec §2 (Slice-C scope + backend note), §4c (REQ-P10-DATA-010, REQ-P10-LOGIC-007, REQ-P10-BACKEND-001/-002),
  §5 (Article VI split, Article IV localhost backend), §8 (FLAG-BACKEND, FLAG-PERFRAME, DEP-3), §9 Article
  I/IV/VI/VII, §10.2 (CL-B4), §11 (SC-D010-1, SC-L007-1/-2, SC-BK-001-1/-002-1, SC-UI-013-1); `traceability.md`
  FLAG-BACKEND, FLAG-PERFRAME, backend rows.
- Researcher §4.5 (WebSocket relay / awareness / transport), §5 (untrusted-input caps, no eval/exec), §6
  (real-time multi-client needs a live/local server; localhost test server narrows it into CI).
- Shipped `scripts/check_layering.py` / `check_cycles.py` (Article I gate), constitution Article I (three
  layers), IV (CI-testable), VI (16 ms budget), VII (untrusted input, no secrets), XI (extensibility).
  ADR-0026 (transport port lives in `data/cloud/`; tokens in keyring), ADR-0028 (convergence in `logic/`).

## Addendum A — Slice-C implementation reconciliation (2026-07-04, AGT-01 final gate)

Status: **Accepted (addendum).** During Slice-C implementation (AGT-03) three refinements diverged from the
letter of §3/§4 above. The final cross-artifact gate reviewed each and finds them **consistent with the
decision's intent** — all remain pure/ZERO-Qt, single-sourced, and preserve the three-layer + backend
layering (both `check_layering` roots and both `check_cycles` roots exit 0). They are recorded here so the
ADR matches the shipped code; **no decision is reversed.**

1. **Wire framing extracted to a new pure module `logic/sync_protocol.py`.** §4 said the "message vocabulary +
   validators are pure and live in `logic/cloud_validation.py`". As shipped, `cloud_validation.py` retains the
   payload validators + Article VII caps, while the **framing** (the `{join, leave, update, presence}`
   `ControlKind`/`SyncMessage` vocabulary, `_PROTOCOL_VERSION`, `encode_*`/`decode_message`, and the
   size-cap-before-decode discipline) lives in a **new pure `logic/sync_protocol.py`** that imports the
   `cloud_validation` validators. Both the client transports (`data/cloud/{loopback,ws}_transport.py`) **and**
   `sync_backend/server.py` import `sync_protocol`, so the framing + caps stay single-sourced and the backend
   still never imports `data/`. This is a cohesion refinement (framing vs. payload validation) fully within the
   §4 intent; the shipped `{sync_request, sync_response}` message kinds were not needed — late-join catch-up is
   handled by the backend replaying its persisted backlog on `JOIN` (see §4 persistence).

2. **`convergence.apply_operations` is the named public apply seam.** §1 of ADR-0028 said `realtime_apply`
   applies remote updates "via the convergence model". As shipped, that seam is the public
   `convergence.apply_operations(document, ops)` (exported in `convergence.__all__`), which `realtime_apply`
   and `converge` both call. This is an additive public function on the pure `logic/` convergence model,
   consistent with the ADR-0028 §1 placement.

3. **`TransportPort` exposes explicit `join`/`leave` control methods.** §3 described the port "carrying CRDT
   updates + awareness/presence"; the tasks-sketch (T10C-04) listed `send_update`/`send_presence`/`poll`. As
   shipped, the ABC also declares `join(document_id)` / `leave(document_id)` — which correspond exactly to the
   §4 protocol's `{join, ..., leave}` message vocabulary, so the port surface now mirrors the wire protocol.
   Additive and consistent; no type leaks above the port.
