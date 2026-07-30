# Specification — Phase 10: Cloud & Collaboration

| Field | Value |
| --- | --- |
| Feature | `phase-10-cloud-collaboration` |
| Author | AGT-02 (Requirements) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION — COMPLETE.** No cloud port (`data/cloud/`), no provider adapters, no version-history / autosave-recovery model, and no collaboration (shared projects / comments / presence / conflict resolution / branching / real-time) exists yet. The shipped `data/project_io.py` `.pixproj` serialiser (defensive load, `ProjectIOError`, `_SUPPORTED_VERSIONS = (1..5)`, zlib+base64, `pathlib`, **no `eval`**) is the **sync unit** and is REUSED, not re-authored; the `Document` tree and the `logic/history.py` reversible-command path are shipped and reused. This spec fixes the WHAT/WHY for **all three slices**: **Slice A** (cloud port + testable local/fake adapter + `.pixproj` cloud round-trip + version history + autosave/recovery), **Slice B** (shared projects + comments + presence + deterministic hybrid convergence), and **Slice C** (real-time CRDT/OT + a first-class sync **backend** component + art branching). The previously-SUSPENDED §10.2 scope questions (CL-B1..CL-B5) have been **ADJUDICATED by the user** (§10.2) and are encoded below; no PENDING markers remain. |
| REQ-ID range | `REQ-P10-DATA-001..010`, `REQ-P10-LOGIC-001..007`, `REQ-P10-UI-001..013`, and the new first-class-backend `REQ-P10-BACKEND-001..002` — **all drafted with full acceptance**. Slice A = `DATA-001..008` / `LOGIC-001..005` / `UI-001..008`; Slice B = `DATA-009` / `LOGIC-006` / `UI-009..011`; Slice C = `DATA-010` / `LOGIC-007` / `UI-012..013` + `BACKEND-001..002`. |
| Layer scope | `pixelart_creator/data/cloud/` (the **ONE cloud storage port** + local/fake adapter + credential-gated real provider adapters *behind the same interface* + the shared-project storage/membership adapter + the client-side real-time **transport port** — CL-B2 fake-adapter-in-CI, real adapters credential-gated) — **zero Qt** + `pixelart_creator/logic/` (sync-state / version-history / autosave-policy pure models **plus** the deterministic hybrid convergence model — tree-CRDT + tile/region-LWW — and the real-time convergence/apply layer) — **zero Qt, headless, unit-testable** + `pixelart_creator/ui/` (cloud save/load, version-history browser, autosave-recovery prompt, provider connect **plus** shared-projects / comments / presence / art-branching / real-time-cursors UI) — **the only Qt surface**. **NEW top-level scope (CL-B4): the real-time sync BACKEND is a SEPARATE service/component that sits OUTSIDE the desktop app's three layers** — AGT-01 owns its placement + an ADR; it MUST be CI-testable over localhost (in-process/subprocess, integration tests over loopback). |
| Binds to (upstream, **shipped** — REUSED) | Phase 1/4/6 `data/project_io.py` (the **PIO-1** primitive: `Document` ⇄ `.pixproj` JSON, defensive validated load, `ProjectIOError`, `_SUPPORTED_VERSIONS`, zlib+base64 payloads, `pathlib`, **no `eval`/`exec`** — this **is the sync unit** the cloud port transports), Phase 1 `logic/document.py` `Document` tree (the **DOC-1** primitive: the subject that round-trips through the cloud), Phase 1 `logic/history.py` `Command`/`History` (the **HIS-1** primitive: the reversible edit path a future conflict/CRDT layer would reconcile — Slices B/C). |
| Depends on (external) | The Researcher — cloud/collaboration grounding **COMPLETE**: `docs/subagent-report-the-researcher-a80a5c6a-20260704T102747.md`. It grounds the technical shape this spec's WHAT is phrased around: a **provider-agnostic port** over Drive v3 / OneDrive-Graph / Dropbox v2 (auth/upload/download/list/revisions/change-tracking; capability diffs modeled as an **opaque cursor**); **desktop auth** = OAuth Authorization Code + **PKCE** over a loopback redirect (RFC 8252/7636) with **Device Grant** (RFC 8628) fallback, **tokens in the OS keyring**, crypto/network in ZERO-Qt `data/` and only browser-launch in `ui/`; **autosave/recovery** = atomic temp-write + fsync + `os.replace` + a sidecar journal discovered on restart, local history mapped to remote revision ids; **conflict resolution** split by data kind — **tree/sequence CRDT** (Yjs/YATA via **pycrdt**, or **Automerge**) for layer-tree/frames/tilemap metadata; **tile/region-partitioned LWW** for raster; deterministic via **logical-clock + site-id** tiebreaks; **Automerge** gives git-like **branching/history** for free (art branching); Yjs ships a built-in **awareness/presence** protocol for ephemeral cursors kept OUT of the persisted doc; **transport** = WebSocket relay (simplest) or WebRTC (P2P); **Article VII** = schema-validate all cloud/CRDT payloads (including **CRDT update blobs** + presence/comment payloads) with strict size/depth/dimension/byte caps, no eval/exec, tokens never in `.pixproj`/logs; **~70 % offline-testable** (port + fake adapter, version history, autosave/recovery, CRDT convergence over in-memory/loopback transport, PKCE crypto, validators) with only live-provider OAuth needing credentials/network. Grounds the HOW for AGT-01's plan across all three slices. |
| SDD phase | `specify` + `clarify` (this document, §10.2 clarifications **ADJUDICATED**) → **COMPLETE / ready for `sdd-plan`** (AGT-01) |

---

## 1. Purpose (WHY)

The platform already has the one artefact cloud sync needs: the `.pixproj` file. `data/project_io.py`
serialises the whole `Document` (layers, frames, tilesets, tilemaps, palette) to a defensively-loaded,
`eval`-free JSON blob with zlib+base64 pixel payloads (PIO-1), and it is the app's canonical, versioned
(`_SUPPORTED_VERSIONS`) save unit. The dossier fixes the architecture as an "event-driven editor +
immutable/diffable project state + command-pattern undo/redo + GPU render pipeline + **optional
cloud-sync layer**" (S7), and roadmap Phase 10 is where that optional layer is realised.

Phase 10 adds a **cloud & collaboration** layer so a `.pixproj` can live in the cloud with **version
history and autosave/recovery**, so provider back-ends (Drive / OneDrive / Dropbox) are **swappable
behind one `data/cloud/` port** with **no provider detail leaking into `logic/` or `ui/`**, and — as an
**advanced tier** — so multiple people can share a project with **comments, presence, deterministic
conflict resolution, art branching, and real-time (CRDT/OT)** editing. This cloud-sync + real-time +
branching axis is a **category differentiator** — none of Aseprite / Pro Motion NG / Pixelorama ship it
(the Figma-like axis).

**This phase is unusually large, and its scope was genuinely ambiguous in ways that materially change
the build.** Five acceptance-changing scope questions were SUSPENDED at `clarify` (A2-D2, default =
suspend) and have now been **ADJUDICATED by the user** (§10.2). The adjudicated scope is **FULL — Slices
A + B + C are all in scope this phase** (CL-B1), delivered as: **the port + a fully-tested fake adapter
in the CI gate**, with real Drive/OneDrive/Dropbox adapters implemented behind the same port but
**credential-gated / manually verified, out of CI** (CL-B2); **OS-keyring** token storage, acquired and
used entirely inside `data/cloud/` (CL-B3); an **actual real-time sync backend** — a **SEPARATE
component that sits OUTSIDE the desktop app's three layers**, itself CI-testable over localhost, distinct
from the out-of-CI live-provider OAuth (CL-B4); and **HYBRID convergence** — a sequence/tree CRDT for
structured metadata plus per-tile/region last-writer-wins for raster buffers, deterministic via
logical-clock + site-id, enabling git-like art branching (CL-B5).

Phase 10 therefore delivers, with full acceptance criteria here: **Slice A** — the ROADMAP "Done means"
backbone (*a `.pixproj` round-trips through the cloud port with version history and autosave/recovery;
adapters are swappable behind one `data/cloud/` interface with no provider leak*); **Slice B** — shared
projects + comments + presence + deterministic hybrid conflict resolution; and **Slice C** — real-time
CRDT/OT editing over a first-class sync backend + git-like art branching (the advanced tier). All REQ
ids (`REQ-P10-DATA-001..010`, `REQ-P10-LOGIC-001..007`, `REQ-P10-UI-001..013`, `REQ-P10-BACKEND-001..002`)
are drafted with acceptance; no PENDING markers remain.

This document specifies WHAT and WHY, technology-neutral at the requirement level. The HOW — concrete
provider SDKs, the exact keyring keying scheme, the autosave interval, the wire format of a stored
version, the concrete CRDT library (pycrdt/Automerge), the real-time transport (WebSocket/WebRTC), and
the sync backend's placement + ADR — is downstream (AGT-01 plan/ADR, grounded by the Researcher).

## 2. Scope

**In scope now (WHAT) — Slice A (unambiguous, depends only on shipped Phase 1 `.pixproj`):**

- **`data/cloud/` — the ONE cloud storage port (new, Qt-free).** A single abstract interface every
  provider adapter implements, exposing a small verb set over an opaque **project blob** keyed by a
  project identifier: **put** (store a new version of a `.pixproj`), **get** (fetch a specific version's
  bytes), **list versions** (ordered history), **latest**, **delete**, and an **autosave/recovery
  slot** put/get (REQ-P10-DATA-001). All provider detail sits *behind* this port; nothing above it names
  a provider (REQ-P10-DATA-007).
- **`.pixproj` cloud round-trip (the sync unit).** A `Document` saved through the port and re-fetched
  reconstructs an **equivalent `Document`** via the shipped PIO-1 serialiser — the `.pixproj` is the
  atomic unit transported; the cloud layer adds **no** new serialisation (REQ-P10-DATA-002).
- **Version history.** Every save through the port creates a **new, ordered version**; prior versions
  are listable and retrievable; a fetched historical version reconstructs the `Document` it held
  (REQ-P10-DATA-003, REQ-P10-LOGIC-003).
- **Autosave / recovery.** The app **autosaves** the working `.pixproj` to a recovery slot via the port
  on a policy (dirty-/interval-based); after an unclean restart an **unsaved recovery is detectable and
  restorable** without overwriting the user's last explicit save (REQ-P10-DATA-004, REQ-P10-LOGIC-002).
- **A fully-testable local/fake adapter.** A `data/cloud/` adapter backed by the **local filesystem /
  in-memory** implements the port completely, so the entire Slice-A contract (round-trip, version
  history, autosave/recovery, defensive load) is **CI-testable headlessly with no network or
  credentials** (REQ-P10-DATA-005). *(Whether real Drive/OneDrive/Dropbox adapters ship live now, or
  are credential-gated/manual behind the same interface, is **PENDING** — CL-B2.)*
- **Untrusted-cloud-data defence (Article VII).** A `.pixproj` fetched from the cloud is **untrusted
  input**: it is validated through the shipped defensive PIO-1 path — every field type/bounds-checked,
  payload size-validated, malformed/oversized/unknown-version → `ProjectIOError` (or a `data/cloud/`
  subclass), **never `eval`/`exec`** (REQ-P10-DATA-006).
- **Provider isolation (Article I).** No provider SDK, type, or exception leaks above `data/cloud/`;
  `logic/` and `ui/` depend only on the port's own abstractions/exceptions (REQ-P10-DATA-007).
- **Pure sync-state + version + autosave-policy models (`logic/`, new, Qt-free).** A deterministic
  model of local-vs-remote version state (REQ-P10-LOGIC-001), the autosave policy as a pure decision
  function (REQ-P10-LOGIC-002), and the ordered immutable version-history model (REQ-P10-LOGIC-003) —
  all **off the interactive render loop** (REQ-P10-LOGIC-004) and deterministic/Qt-free
  (REQ-P10-LOGIC-005).
- **`logic/constants.py` (extend).** Named bounds/defaults: `AUTOSAVE_INTERVAL_MS`,
  `MAX_CLOUD_VERSIONS`, `MAX_CLOUD_PROJECT_BYTES`, `CLOUD_RETRY_LIMIT` (Article II). Exceeding a bound
  raises a domain error. *(Concrete values are AGT-01/ADR HOW.)*
- **`ui/` Slice-A surfaces (the only Qt).** Cloud **save/load** (open a project from the cloud, save the
  current project to the cloud — REQ-P10-UI-001); a **version-history browser** (list versions, preview,
  restore — REQ-P10-UI-002); an **autosave-recovery prompt** on restart (REQ-P10-UI-003); a **provider
  connect** entry point (REQ-P10-UI-004, its live behaviour bounded by CL-B2/CL-B3); cloud operations
  keep the **UI responsive** (no freeze; off the GUI thread — REQ-P10-UI-005); a11y + both themes + i18n
  (REQ-P10-UI-006/-007/-008).

**In scope now (WHAT) — Slice B (collaboration, ADJUDICATED CL-B1 FULL / CL-B5 HYBRID):**

- **Shared-project storage + membership (`data/cloud/`, Qt-free).** A `.pixproj` can be **shared** with a
  bounded set of members (a membership model); the shared-project storage/membership adapter is behind
  the SAME cloud port family and is exercised by the fake adapter in CI (REQ-P10-DATA-009). Membership
  and comment/presence payloads are untrusted input (Article VII, REQ-P10-DATA-006 posture extended).
- **Deterministic HYBRID convergence model (`logic/`, Qt-free).** Concurrent `.pixproj` edits converge
  **deterministically** via a **sequence/tree CRDT for STRUCTURED metadata** (layer tree, frames,
  tilemap metadata) + **per-tile/region last-writer-wins for RASTER pixel buffers**, ordered by a
  **logical-clock + site-id** tiebreak — commutative, convergent, and scalable to 8K without per-pixel
  overhead (REQ-P10-LOGIC-006). This is the reconciliation of the shipped `history.py` edit path (HIS-1).
- **`ui/` Slice-B surfaces (the only Qt).** A **shared-projects** panel (share/invite/see members —
  REQ-P10-UI-009), a **comments** surface (thread/resolve, payloads validated — REQ-P10-UI-010), and a
  **presence** surface (who else is present — REQ-P10-UI-011). a11y + both themes + i18n apply
  (REQ-P10-UI-006/-007/-008 extend to these).

**In scope now (WHAT) — Slice C (real-time + branching + the sync BACKEND, ADJUDICATED CL-B1/CL-B4/CL-B5):**

- **Client-side real-time transport port + shared-document storage (`data/cloud/`, Qt-free).** A
  provider-agnostic **transport port** carries CRDT updates + awareness/presence between a client and the
  backend; the client transport is **zero-Qt in `data/`**, talks to the backend **behind a port**, and
  the backend↔client loop is **localhost-testable** (in-memory / loopback transport in CI; real network
  transport credential-/network-gated behind the same interface) (REQ-P10-DATA-010).
- **Real-time convergence / apply layer (`logic/`, Qt-free).** The advanced-tier layer that applies
  remote CRDT/OT updates to the local `Document`, converging deterministically with the hybrid model
  (REQ-P10-LOGIC-006), and supports **git-like art branching** (clone → concurrent edit → merge with no
  manual conflict resolution, per Automerge-style history) (REQ-P10-LOGIC-007). **Flagged for AGT-10:**
  real-time **remote-patch application re-enters the per-frame budget** (Article VI) — unlike batch
  Slice-A sync — and AGT-10 must assess it per-frame (see §8 DEP-3).
- **Real-time sync BACKEND — a NEW first-class, top-level component (OUTSIDE the three layers).** An
  actual real-time sync server/backend (NOT merely a loopback transport) that relays and persists CRDT
  updates + awareness/presence across clients (REQ-P10-BACKEND-001/-002). **AGT-01 owns its placement +
  an ADR** (it does not live under `logic/`/`data/`/`ui/`). It **MUST be CI-testable over localhost** —
  spun up in-process/subprocess with integration tests over loopback — so it stays **in the CI gate**;
  this is DISTINCT from the live third-party provider OAuth, which is out-of-CI (CL-B2). Untrusted-input
  defence (Article VII) applies to every CRDT update blob and presence/comment payload the backend
  ingests (REQ-P10-BACKEND-002).
- **`ui/` Slice-C surfaces (the only Qt).** An **art-branching** UI (branch / diff / merge — REQ-P10-
  UI-012) and **real-time cursors/selection** UI (ephemeral presence overlays — REQ-P10-UI-013).

**Out of scope (this phase):** see §6 Non-goals. Notably: identity/account management beyond provider
OAuth + shared-project membership; billing/quota; end-to-end encryption beyond untrusted-input defence;
the concrete provider SDK / keyring keying scheme / autosave interval / version wire format / concrete
CRDT library / concrete transport (WebSocket vs WebRTC) / the backend's concrete framework + hosting
(all AGT-01/ADR HOW); no plan/tasks/code (AGT-01/03/05); no tests (AGT-04/06); no new technology decided
here (S8).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap phase.
Feature-label taxonomy in §3.2. **Slice-A stories are drafted; Slice-B/C stories are listed as PENDING
(gated on §10).**

### 3.1 User stories — Slice A (drafted)

- **US-1 (Artist / cloud-save-load).** As an artist, I want to **save my project to the cloud and open
  it again from any session**, so my work is not tied to one machine. → REQ-P10-DATA-001, -002,
  REQ-P10-UI-001 · `cloud-save-load` · P10
- **US-2 (Artist / version-history).** As an artist, I want a **version history** of my cloud project so
  I can see prior saves and **restore** an earlier one. → REQ-P10-DATA-003, REQ-P10-LOGIC-003,
  REQ-P10-UI-002 · `version-history` · P10
- **US-3 (Artist / autosave-recovery).** As an artist, I want the app to **autosave** and, after a
  crash, **offer to recover** my unsaved work without clobbering my last explicit save. →
  REQ-P10-DATA-004, REQ-P10-LOGIC-002, REQ-P10-UI-003 · `autosave-recovery` · P10
- **US-4 (Artist / provider-choice).** As an artist, I want to **choose a cloud provider** and have the
  app work the same regardless of which one, so I am not locked in. → REQ-P10-DATA-001, -007,
  REQ-P10-UI-004 · `provider-agnostic` · P10
- **US-5 (Maintainer / swappable-adapters).** As a maintainer, I want provider adapters **swappable
  behind one `data/cloud/` interface** with **no provider detail in `logic/`/`ui/`**, so a new provider
  is a new adapter and nothing else changes. → REQ-P10-DATA-001, -005, -007 · `cloud-port` · P10
- **US-6 (Maintainer / testable-without-network).** As a maintainer, I want the whole cloud contract
  **tested by a local/fake adapter with no network or credentials**, so CI verifies round-trip +
  version history + recovery deterministically. → REQ-P10-DATA-005 · `testable-adapter` · P10
- **US-7 (Security-conscious user / untrusted-cloud-data).** As a user, I want a project fetched from
  the cloud treated as **untrusted input** — validated, `eval`-free, malformed → a clear error — so a
  tampered cloud file can never execute code or crash the app. → REQ-P10-DATA-006 · `untrusted-cloud`
  · P10
- **US-8 (Artist / responsive-sync).** As a user, I want cloud operations to **not freeze the UI** — the
  app stays responsive while a save/fetch runs. → REQ-P10-LOGIC-004, REQ-P10-UI-005 · `responsive-sync`
  · P10
- **US-9 (Any user / a11y-theme-i18n).** As a keyboard / dark-mode / non-English user, I want the cloud
  panels **keyboard-reachable, correct in both themes, fully translatable**. → REQ-P10-UI-006, -007,
  -008 · `a11y`, `theming`, `i18n` · P10

### 3.1b User stories — Slice B (collaboration, drafted; ADJUDICATED)

- **US-B1 (Team / shared-projects).** As a team, we want to **share a `.pixproj`** with named members and
  edit it together. → REQ-P10-DATA-009, REQ-P10-UI-009 · `shared-projects` · P10
- **US-B2 (Reviewer / comments).** As a reviewer, I want to **leave comments** on a shared project and
  resolve them. → REQ-P10-DATA-009, REQ-P10-UI-010 · `comments` · P10
- **US-B3 (Collaborator / presence).** As a collaborator, I want to see **who else is present** in a
  shared project. → REQ-P10-DATA-010, REQ-P10-UI-011 · `presence` · P10
- **US-B4 (Collaborator / conflict-resolution).** As a collaborator, I want concurrent edits to a
  `.pixproj` to **converge deterministically** (hybrid tree-CRDT for structure + per-tile/region LWW for
  raster). → REQ-P10-LOGIC-006 · `conflict-resolution` · P10

### 3.1c User stories — Slice C (real-time + branching + backend, drafted; ADJUDICATED)

- **US-C1 (Collaborator / real-time).** As a collaborator, I want **real-time** editing — my edits apply
  to peers' canvases live and theirs to mine — converging via CRDT/OT. → REQ-P10-DATA-010,
  REQ-P10-LOGIC-007, REQ-P10-BACKEND-001, REQ-P10-BACKEND-002 · `real-time` · P10
- **US-C2 (Artist / branching).** As an artist, I want to **branch** a project, edit independently, and
  **merge** back with no manual conflict resolution (git-like art branching). → REQ-P10-LOGIC-007,
  REQ-P10-UI-012 · `branching` · P10
- **US-C3 (Collaborator / real-time-cursors).** As a collaborator, I want to see **other editors'
  cursors/selection live** (ephemeral presence). → REQ-P10-DATA-010, REQ-P10-UI-013 · `real-time` · P10
- **US-C4 (Maintainer / sync-backend).** As a maintainer, I want the real-time **sync backend** to be a
  separate, **localhost-CI-testable** component so the backend↔client loop is verified in the CI gate
  without third-party credentials. → REQ-P10-BACKEND-001, REQ-P10-BACKEND-002 · `sync-backend` · P10

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase | Slice |
| --- | --- | --- | --- |
| `cloud-port` | The ONE `data/cloud/` interface every provider adapter implements; no provider leak. | 10 | A |
| `cloud-save-load` | Save the current `.pixproj` to / open it from the cloud via the port. | 10 | A |
| `version-history` | Ordered, retrievable, restorable history of a cloud project's saves. | 10 | A |
| `autosave-recovery` | Policy-driven autosave + post-crash recovery of unsaved work. | 10 | A |
| `provider-agnostic` | The app behaves identically regardless of the chosen provider. | 10 | A |
| `testable-adapter` | A local/fake adapter that verifies the whole contract with no network/credentials. | 10 | A |
| `untrusted-cloud` | Cloud-fetched `.pixproj` is untrusted: validated, `eval`-free, malformed → error. | 10 | A |
| `responsive-sync` | Cloud ops are off the interactive loop; the UI never freezes. | 10 | A |
| `shared-projects` | Share a `.pixproj` with named members; membership model. | 10 | B |
| `comments` | Thread/resolve comments on a shared project; payloads validated. | 10 | B |
| `presence` | See who else is present in a shared project. | 10 | B |
| `conflict-resolution` | Deterministic HYBRID convergence: tree-CRDT (structure) + tile/region-LWW (raster). | 10 | B |
| `real-time` | Real-time CRDT/OT editing + live cursors over the sync backend (advanced tier). | 10 | C |
| `branching` | Git-like art branching: branch / diff / merge with no manual conflict resolution. | 10 | C |
| `sync-backend` | The separate, localhost-CI-testable real-time sync server/backend (outside the 3 layers). | 10 | C |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 10 | A/B/C |

---

## 4. Functional requirements — Slice A (drafted)

Each REQ carries `traces:` to a dossier `S-id`, a principle (`P2` determinism), a constitution article,
and/or a forward-inherited primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a shipped callable (PIO-1 `project_io`) is a **constraint**, not a HOW choice.

### `data/cloud/` — the cloud storage port + local/fake adapter (new, Qt-free)

#### REQ-P10-DATA-001 — One cloud storage port abstracts all providers
`traces:` S7 (optional cloud-sync layer), S11, Article I, Phase-10 capability (cloud save/load + adapters)
`data/cloud/` defines **one abstract interface** ("the cloud port") that every provider adapter
implements, exposing a bounded verb set over an opaque **project blob** (a `.pixproj`'s bytes) keyed by
a project id: **put** (store a new version), **get(version)** (fetch a version's bytes),
**list_versions** (ordered), **latest**, **delete**, and an **autosave/recovery slot** put/get. The
interface names **no** provider. It is pure `data/` (zero Qt). Adding a provider is adding an adapter
implementing this port — nothing above it changes (REQ-P10-DATA-007).

#### REQ-P10-DATA-002 — A `.pixproj` round-trips through the port (the sync unit)
`traces:` **PIO-1** (`data/project_io.py`), **DOC-1**, S7, Article VII
A `Document` **serialised to a `.pixproj` by the shipped PIO-1 serialiser**, stored through the port,
and re-fetched reconstructs an **equivalent `Document`** (same layers/frames/tilesets/tilemaps/palette/
pixels within the format's guarantees). The cloud layer transports the `.pixproj` **as the atomic sync
unit** and adds **no** new serialisation format of its own — it composes PIO-1 (Article I; no
re-implementation).

#### REQ-P10-DATA-003 — Version history: every save is a new, ordered, retrievable version
`traces:` S7, P2 (determinism), Phase-10 capability (version history)
Each `put` through the port creates a **new version** appended to an **ordered history**;
`list_versions` returns the history deterministically (stable order), and `get(version)` fetches any
prior version's bytes, from which the `Document` it held is reconstructed. History length is bounded by
`MAX_CLOUD_VERSIONS` (REQ-P10-LOGIC-005); the retention policy beyond the bound is an AGT-01 HOW.

#### REQ-P10-DATA-004 — Autosave / recovery slot round-trips and survives an unclean restart
`traces:` S7, Phase-10 capability (autosave/recovery), Researcher §3 (atomic write + sidecar recovery)
The port provides an **autosave/recovery slot** distinct from the explicit version history: the app
`put`s the working `.pixproj` to it on the autosave policy (REQ-P10-LOGIC-002), and after an **unclean
restart** the app can **detect** an unsaved recovery and **restore** it — **without** overwriting the
user's last explicit saved version. The write is **crash-safe / atomic** so an interrupted autosave
**never corrupts the last good file** (the Researcher grounds the pattern as temp-write + `fsync` +
`os.replace`, plus a discoverable sidecar recovery file scanned on restart — the concrete realisation is
an AGT-01 HOW, DEP-2/BF-2). A restored recovery is validated defensively (REQ-P10-DATA-006).

#### REQ-P10-DATA-005 — A local/fake adapter implements the whole port, testable with no network
`traces:` S13, Article IV, S11, Phase-10 capability (adapters swappable)
A **local-filesystem / in-memory** adapter fully implements the cloud port so the **entire Slice-A
contract** — round-trip (-002), version history (-003), autosave/recovery (-004), defensive load
(-006), provider isolation (-007) — is **exercised headlessly in CI with no network access and no
credentials**, deterministically and portably (Article IV). Real provider adapters (Drive / OneDrive /
Dropbox) implement the **same** port; **whether they ship live now or are credential-gated/manual is
PENDING (CL-B2)** — the port + fake adapter are the fixed, testable Slice-A deliverable.

#### REQ-P10-DATA-006 — Cloud-fetched `.pixproj` is untrusted input; defensive, `eval`-free
`traces:` **PIO-1**, Article VII, S7
A `.pixproj` (or version/recovery blob) fetched from **any** cloud source is treated as **untrusted
input** and validated through the shipped defensive load path (PIO-1): every field type/bounds-checked,
payload size-validated against `MAX_CLOUD_PROJECT_BYTES`, **unknown/malformed/oversized → an error**
(`ProjectIOError` or a `data/cloud/` subclass), surfaced to the user — **never** `eval`/`exec`, never a
crash or silent corruption (Article VII). Cloud data is explicitly not more trusted than local files.

#### REQ-P10-DATA-007 — No provider detail leaks above the port
`traces:` Article I, S11
No provider SDK type, credential type, HTTP/network type, or provider-specific exception appears in
`logic/` or `ui/`, or in the cloud port's public signatures — they live **only inside** the concrete
adapter under `data/cloud/`. `logic/` and `ui/` depend solely on the port's own abstractions and its
own exception family. Enforced by `check_layering` / `check_cycles` (only Qt file outside `ui/` remains
`ui/commands.py`; `data/cloud/` imports no Qt).

#### REQ-P10-DATA-008 — Auth/credential handling is isolated behind the adapter *(mechanism PENDING CL-B3)*
`traces:` Article VII (no secrets), S11, Article I, Researcher §2 (RFC 8252/7636/8628, keyring)
Any provider credentials/tokens are acquired, stored, and used **entirely inside** ZERO-Qt `data/cloud/`
— never in `logic/`/`ui/`, **never committed** to the repo, **never written to `.pixproj` or logs**
(Article VII §3). The port exposes only a provider-agnostic "connected / not connected" notion; `ui/`
never receives raw tokens. The Researcher grounds the **flow** as OAuth **Authorization Code + PKCE
(`S256`) over a loopback redirect** (RFC 8252 + RFC 7636, system browser — never an embedded webview),
with the **Device Authorization Grant** (RFC 8628) as a fallback, and only the **launch-the-browser /
show-the-device-code** step delegated to `ui/`; the PKCE verifier/challenge is a pure, unit-testable
crypto function. **The concrete token-storage mechanism — OS keyring (the Researcher's default) vs
encrypted file vs deferred — is a blocking clarification, CL-B3 (§10);** this REQ fixes the isolation +
no-secrets + external-browser contract, not the storage mechanism.

### `logic/` — sync-state / version / autosave-policy pure models (new, Qt-free)

#### REQ-P10-LOGIC-001 — Sync-state model is pure and deterministic
`traces:` P2 (determinism), S11, Article I
A pure model of **local-vs-remote version state** (e.g. up-to-date / local-ahead / remote-ahead /
diverged) is a **deterministic function** of the local version marker and the port's version list —
Qt-free, unit-testable, no wall-clock/randomness/locale dependence. (What "diverged" *resolves to* is
Slice B and PENDING; Slice A models the *state*, not the merge.)

#### REQ-P10-LOGIC-002 — Autosave policy is a pure decision function
`traces:` P2, S12, Phase-10 capability (autosave)
"Should we autosave now?" is a **pure, deterministic function** of inputs (document-dirty flag, elapsed
ticks vs `AUTOSAVE_INTERVAL_MS`, last-autosave marker) — computed in `logic/`, not ad-hoc in a widget or
timer callback, so it is unit-testable without Qt or a real clock (elapsed time is an **input**, not
read from the wall clock inside the function). The concrete interval value is an AGT-01/ADR constant.

#### REQ-P10-LOGIC-003 — Version-history model is ordered and immutable
`traces:` P2, S11, Phase-10 capability (version history)
The version-history model is an **ordered, immutable** sequence of version descriptors (id + ordering
key + metadata); appending a version yields a new ordered history without mutating prior entries;
iteration order is deterministic. Bounded by `MAX_CLOUD_VERSIONS` (REQ-P10-LOGIC-005).

#### REQ-P10-LOGIC-004 — Cloud/sync work is off the interactive render loop *(NFR posture, Article VI)*
`traces:` Article VI, S1, S12
Cloud save/load, version fetch, and autosave are **batch/background** operations **not on the per-frame
render loop** — like Phase-7 export and Phase-8 automation, the 16 ms `FRAME_BUDGET_MS` does **not**
gate the sync operation itself; instead the requirement is that these operations keep the **UI
responsive** (REQ-P10-UI-005). *(Real-time collaboration, if Slice C is scoped, introduces per-frame
concerns — PENDING CL-B1/CL-B4.)*

#### REQ-P10-LOGIC-005 — Bounded numerics & defaults (single source)
`traces:` Article II, Article VII, S12
The cloud/sync layer enforces named bounds/defaults defined once in `logic/constants.py`:
`AUTOSAVE_INTERVAL_MS`, `MAX_CLOUD_VERSIONS`, `MAX_CLOUD_PROJECT_BYTES`, `CLOUD_RETRY_LIMIT`. Exceeding a
bound raises a domain error rather than degrading silently. No numeric literals in
`logic/`/`data/`/`ui/` (Article II). Concrete values are an AGT-01/ADR HOW.

### `ui/` — cloud save/load, version browser, recovery prompt, provider connect (new; only Qt)

#### REQ-P10-UI-001 — Cloud save/load
`traces:` REQ-P10-DATA-001, -002, S7
The UI lets the user **save the current project to the cloud** and **open a project from the cloud**
through the port; opening validates defensively (REQ-P10-DATA-006). The UI names no provider directly —
it drives the port. Translatable labels; errors surfaced (not swallowed).

#### REQ-P10-UI-002 — Version-history browser (view + restore)
`traces:` REQ-P10-DATA-003, REQ-P10-LOGIC-003
The UI shows the **ordered version history** of the current cloud project and lets the user **inspect
and restore** a prior version (restoring reconstructs that version's `Document` via PIO-1). Restoring is
an explicit user action; the current unsaved state is protected per REQ-P10-DATA-004 semantics.
Translatable labels.

#### REQ-P10-UI-003 — Autosave-recovery prompt on restart
`traces:` REQ-P10-DATA-004, REQ-P10-LOGIC-002
On startup, if an **unsaved recovery** exists (REQ-P10-DATA-004), the UI **prompts** the user to recover
or discard it, without overwriting the last explicit save until the user chooses. Autosave runs per the
pure policy (REQ-P10-LOGIC-002). Translatable labels + error messages.

#### REQ-P10-UI-004 — Provider connect entry point *(live behaviour bounded by CL-B2/CL-B3)*
`traces:` REQ-P10-DATA-001, -007, -008
The UI provides a **connect / disconnect** entry point that selects/authorises a cloud provider through
the port's provider-agnostic surface; the app then behaves identically regardless of provider
(REQ-P10-DATA-007). **The concrete connect flow (live OAuth vs a local/fake "connected" state) depends
on CL-B2/CL-B3 (§10);** this REQ fixes only the provider-agnostic entry-point contract. Translatable
labels.

#### REQ-P10-UI-005 — Cloud operations keep the UI responsive *(NFR, Article VI posture)*
`traces:` REQ-P10-LOGIC-004, S7, Article VI
A cloud save/load/version-fetch/autosave **does not freeze the UI** — it runs off the GUI thread and the
app stays responsive (progress/cancel where a long operation warrants it). Whether it runs on a worker
thread/executor is an AGT-01/AGT-10 HOW; this REQ fixes the observable **stays-responsive** contract.
(Cloud sync is batch work off the per-frame loop — REQ-P10-LOGIC-004 — so the 16 ms budget does not gate
the operation itself, unlike Phase-9 overlays.)

#### REQ-P10-UI-006 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive cloud control (save/open-from-cloud, version-list + restore, recovery prompt,
provider connect/disconnect) exposes an accessible name and, where non-obvious, a description; is
keyboard-reachable in a logical order; shows a visible focus indicator. Verified by AGT-06 (`a11y-audit`).

#### REQ-P10-UI-007 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The cloud save/load dialogs, version-history browser, recovery prompt, and provider-connect UI render
correctly in both light and dark themes; colours are defined once by role, never hard-coded per widget.
Both themes are test-verified (AGT-06 pytest-qt).

#### REQ-P10-UI-008 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 10 Slice A (cloud menu/dialog labels + tooltips, version-list
columns, recovery-prompt text, provider names shown generically, status/error messages) is wrapped in
`tr()` / `translate()`; none is a bare literal. Hand-built widgets re-set text on
`QEvent.LanguageChange`. Verified by `string_audit_check` (AGT-07); an unwrapped string is blocking.

## 4b. Functional requirements — Slice B (collaboration; ADJUDICATED CL-B1/CL-B5)

### `data/cloud/` — shared-project storage + membership (Qt-free)

#### REQ-P10-DATA-009 — Shared-project storage + membership behind the cloud port
`traces:` S7, Article I, Article VII, Phase-10 capability (shared projects), CL-B1 (FULL scope), CL-B5
A `.pixproj` can be **shared**: the `data/cloud/` port family exposes a **membership** notion over a
shared project — a bounded set of members (each an opaque, provider-agnostic member identity) with a
role/permission marker — plus storage for **comment** and **presence-metadata** payloads associated with
the shared project. Membership, comment, and presence payloads fetched from any cloud source are
**untrusted input**: schema-validated with strict size/depth/count caps (Article VII, extending
REQ-P10-DATA-006), **never `eval`/`exec`**, malformed/oversized → a domain error. The membership/shared
adapter is behind the SAME port family, so the **local/fake adapter implements it** and the whole
Slice-B storage contract is **CI-testable with no network/credentials** (REQ-P10-DATA-005 posture). No
provider detail leaks above the port (REQ-P10-DATA-007). Member/comment counts and payload bytes are
bounded by new constants (`MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`, `MAX_COMMENTS_PER_PROJECT`) in
`logic/constants.py` (Article II, REQ-P10-LOGIC-005 posture).

### `logic/` — deterministic HYBRID convergence model (Qt-free)

#### REQ-P10-LOGIC-006 — Deterministic hybrid convergence model for a `.pixproj`
`traces:` **HIS-1**, **DOC-1**, P2 (determinism), S11, Article I, Article VI (batch tier), CL-B5 (HYBRID), Researcher §4.2/§4.4
Concurrent edits to a `.pixproj` **converge deterministically** via a **HYBRID model**:
- **Structured metadata** (layer tree, frame list, tilemap metadata) converges through a **sequence/tree
  CRDT** whose operations **commute** — applying a given set of concurrent ops in **any order** yields
  an **identical** converged structure.
- **Raster pixel buffers** converge through **per-tile / per-region last-writer-wins (LWW)**: concurrent
  edits to *different* tiles both survive; concurrent edits to the *same* tile resolve deterministically
  by a **logical-clock + site-id** tiebreak.
- Determinism is total and reproducible: given the same operation set, **all replicas converge to a
  byte-identical `Document`** regardless of delivery order (strong eventual consistency), verified as a
  unit-testable, Qt-free, wall-clock-free, randomness-free pure model.
- The model is **scalable to 8K without per-pixel overhead** — the raster path partitions by
  tile/region (no per-pixel CRDT metadata), bounded by a new constant (`CRDT_TILE_SIZE_PX` /
  `MAX_CRDT_UPDATE_BYTES` in `logic/constants.py`, Article II). This layer reconciles the shipped
  `history.py` command stream (HIS-1). It is a **batch/off-loop** model at the Slice-B tier (Article VI);
  the real-time *apply* path is REQ-P10-LOGIC-007 (per-frame, AGT-10-assessed).

### `ui/` — shared projects / comments / presence (only Qt)

#### REQ-P10-UI-009 — Shared-projects panel
`traces:` REQ-P10-DATA-009, S7, Article V
The UI lets the user **share the current project**, **invite/see members**, and open a shared project —
driving the port's provider-agnostic membership surface (no provider named). Errors surfaced; a11y +
both themes + i18n apply (REQ-P10-UI-006/-007/-008). Translatable labels.

#### REQ-P10-UI-010 — Comments surface
`traces:` REQ-P10-DATA-009, Article V, Article VII
The UI lets the user **add, view, thread, and resolve comments** on a shared project; comment text is a
**translatable, validated** payload (never `eval`/`exec`, bounded by `MAX_COMMENT_BYTES`). a11y + both
themes + i18n apply. Translatable labels.

#### REQ-P10-UI-011 — Presence surface
`traces:` REQ-P10-DATA-010, Article V
The UI shows **who else is present** in a shared project (member list / avatars / status) from the
ephemeral presence channel (REQ-P10-DATA-010). Presence is ephemeral (not persisted into the `.pixproj`).
a11y + both themes + i18n apply. Translatable labels.

## 4c. Functional requirements — Slice C (real-time + branching + sync backend; ADJUDICATED CL-B1/CL-B4/CL-B5)

### `data/cloud/` — client-side real-time transport port (Qt-free)

#### REQ-P10-DATA-010 — Client real-time transport port + shared-document storage
`traces:` S7, S11, Article I, Article VII, CL-B4 (backend in scope), Researcher §4.5
A provider-agnostic **transport port** carries **CRDT updates** and **awareness/presence** messages
between a client and the sync backend (REQ-P10-BACKEND-001). The client transport is **zero-Qt in
`data/`**, talks to the backend **behind the port**, and:
- the **backend↔client loop is localhost-testable** — an **in-memory / loopback transport** implements
  the port so real-time exchange is exercised in CI with **no external network/credentials**; a real
  network transport (WebSocket/WebRTC) implements the SAME port and is credential-/network-gated,
  **out of the CI gate**;
- every inbound CRDT update blob and presence payload is **untrusted input**: schema-validated with
  strict size/depth/dimension/byte caps (`MAX_CRDT_UPDATE_BYTES`), **never `eval`/`exec`**,
  malformed/oversized → a domain error (Article VII);
- no transport/provider detail leaks above the port (REQ-P10-DATA-007).

### `logic/` — real-time convergence / apply layer + branching (Qt-free)

#### REQ-P10-LOGIC-007 — Real-time CRDT/OT apply layer + git-like branching *(advanced tier; AGT-10 per-frame flag)*
`traces:` **HIS-1**, **DOC-1**, P2, S11, Article I, **Article VI (per-frame — AGT-10)**, CL-B5, Researcher §4.3/§4.6
The advanced-tier layer **applies remote CRDT/OT updates** to the local `Document`, converging via the
hybrid model (REQ-P10-LOGIC-006) — commutative and deterministic, Qt-free and unit-testable over an
in-memory/loopback transport. It also supports **git-like art branching**: **clone → concurrent edit →
merge** with **no manual conflict resolution** (the CRDT merges; branch history is reconstructable, per
the Automerge-style model). **Article VI — DISTINCT from Slice A:** whereas batch Slice-A cloud/sync is
off the per-frame loop, **real-time remote-patch application RE-ENTERS the per-frame budget**
(`FRAME_BUDGET_MS`, 16 ms) — applying an inbound patch must not blow the frame budget. **This REQ is
explicitly flagged for AGT-10 per-frame assessment** (§8 DEP-3): AGT-10 must assess remote-patch apply
cost against the 16 ms budget and direct batching/coalescing if needed. Inbound update size bounded by
`MAX_CRDT_UPDATE_BYTES` (Article II/VII).

### The sync BACKEND — a NEW first-class, top-level component (OUTSIDE the three layers)

> **Architectural note (CL-B4, encode for AGT-01):** the real-time sync backend is a **SEPARATE
> service/component that sits OUTSIDE the desktop app's three-layer (`logic/`/`data/`/`ui/`)
> architecture** — it is **new top-level scope**. **AGT-01 owns its placement + an ADR.** The desktop
> client's three-layer purity is unaffected (the client talks to the backend only through the zero-Qt
> `data/cloud/` transport port, REQ-P10-DATA-010). The backend↔client loop MUST be **localhost-CI-
> testable** (in-process/subprocess, integration tests over loopback), keeping real-time in the CI gate;
> this is DISTINCT from the live third-party provider OAuth, which is out-of-CI (CL-B2).

#### REQ-P10-BACKEND-001 — Real-time sync backend is a separate, localhost-CI-testable component
`traces:` S7, Article IV, Article XI, CL-B4, Researcher §4.5/§6
Phase 10 delivers an **actual real-time sync backend** — a real server/component that relays and
**persists** CRDT updates + awareness/presence across multiple clients (NOT merely a loopback shim). It
is a **separate top-level component OUTSIDE** the desktop app's `logic/`/`data/`/`ui/` layers; **AGT-01
owns its placement + an ADR**. It **MUST be CI-testable over localhost**: the test harness spins it up
**in-process or as a subprocess**, and **integration tests exercise the full backend↔client loop over
loopback** so real-time stays **in the CI gate**, deterministically, with **no third-party credentials
or external network** (DISTINCT from the out-of-CI live-provider OAuth, CL-B2). Multiple clients over the
loopback backend must converge to an identical `Document` (with REQ-P10-LOGIC-006/-007).

#### REQ-P10-BACKEND-002 — Backend treats every payload as untrusted input (Article VII)
`traces:` Article VII, Article II, S13, CL-B4, Researcher §5
The sync backend treats **every** ingested payload — CRDT update blobs, presence/awareness messages, and
comment payloads — as **untrusted input**: each is **schema-validated** with strict **size / depth /
dimension / byte caps** (shared bounds `MAX_CRDT_UPDATE_BYTES`, `MAX_COMMENT_BYTES`,
`MAX_SHARED_MEMBERS`), **never `eval`/`exec`**, malformed/oversized → rejected with a clear error, never
a crash or silent corruption. A malicious/broken client cannot exhaust memory or execute code on the
backend. Bounds are named (no literals); the backend never receives or stores provider OAuth tokens
(those stay in the client's `data/cloud/` + OS keyring, CL-B3/REQ-P10-DATA-008).

### `ui/` — art branching + real-time cursors (only Qt)

#### REQ-P10-UI-012 — Art-branching UI
`traces:` REQ-P10-LOGIC-007, S7, Article V, Researcher §4.6
The UI lets the user **branch** the current project, edit the branch independently, view a **diff**, and
**merge** it back — the merge is conflict-free (REQ-P10-LOGIC-007 resolves it; no manual conflict UI is
required, though the UI surfaces the merge outcome). a11y + both themes + i18n apply. Translatable labels.

#### REQ-P10-UI-013 — Real-time cursors / selection overlay
`traces:` REQ-P10-DATA-010, REQ-P10-LOGIC-007, Article V, Article VI, Researcher §4.5
The UI renders **other collaborators' cursors and selection** live as ephemeral overlays from the
presence/awareness channel (REQ-P10-DATA-010). Overlays are ephemeral (never persisted into the
`.pixproj`) and their per-frame draw is subject to AGT-10's per-frame assessment (REQ-P10-LOGIC-007
flag). a11y + both themes + i18n apply. Translatable labels.

## 5. Non-functional requirements (constitution-tied acceptance) — all slices

Captured inline in §4: REQ-P10-LOGIC-004 (off the interactive loop / batch posture, Article VI),
REQ-P10-UI-005 (stays-responsive), REQ-P10-UI-006 (a11y, Article V), REQ-P10-UI-007 (both themes,
Article V), REQ-P10-UI-008 (i18n, Article V), REQ-P10-DATA-006 (security / untrusted input, Article VII),
REQ-P10-DATA-008 (no secrets, Article VII), REQ-P10-LOGIC-005 (bounded numerics, Article II).

**Slice B/C NFRs (constitution-tied):**
- **Article VII (security), extended to collaboration:** REQ-P10-DATA-009 (membership/comment/presence
  payloads untrusted), REQ-P10-DATA-010 (CRDT-update + presence blobs untrusted), REQ-P10-BACKEND-002
  (backend validates every ingested payload) — schema-validate + strict size/depth/dimension/byte caps,
  no `eval`/`exec`. Tokens never reach the backend (REQ-P10-DATA-008 / CL-B3).
- **Article VI (performance) — the split:** REQ-P10-LOGIC-006 hybrid convergence is **batch/off-loop**
  (like Slice A); **REQ-P10-LOGIC-007 real-time remote-patch application RE-ENTERS the 16 ms per-frame
  budget** and is **flagged for AGT-10** (§8 DEP-3), as is the REQ-P10-UI-013 cursor overlay draw.
- **Article IV (testing):** REQ-P10-BACKEND-001 keeps real-time in the CI gate via a localhost
  (in-process/subprocess) backend + loopback integration tests; REQ-P10-LOGIC-006/-007 convergence is
  deterministic and unit-testable over an in-memory transport (Researcher §6).
- **Article II (bounded numerics):** new constants `MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`,
  `MAX_COMMENTS_PER_PROJECT`, `MAX_CRDT_UPDATE_BYTES`, `CRDT_TILE_SIZE_PX` in `logic/constants.py`.
- **Article V (UX):** REQ-P10-UI-009..013 inherit the a11y / both-themes / i18n gates
  (REQ-P10-UI-006/-007/-008).

## 6. Non-goals (explicit; deferred)

- **Concrete provider SDKs, the keyring keying scheme, the autosave interval value, the version wire
  format, the concrete CRDT library (pycrdt vs Automerge), the concrete real-time transport (WebSocket
  vs WebRTC), and the sync backend's concrete framework + hosting/placement** — AGT-01 plan/ADR HOW
  (grounded by the Researcher). *(Scope is now fully adjudicated — §10.2; only the HOW remains.)*
- **Live third-party provider integration in CI** — real Drive/OneDrive/Dropbox adapters are implemented
  behind the same port but **credential-gated / manually verified, OUT of the CI gate** (CL-B2). CI
  determinism comes from the fake adapter (and, for real-time, the localhost backend + loopback
  transport — CL-B4, which IS in the CI gate and is distinct from the out-of-CI provider OAuth).
- **Identity/account management beyond provider OAuth + shared-project membership; billing/quota;
  end-to-end encryption** beyond the untrusted-input defence — out of Phase 10.
- **Re-implementing `.pixproj` serialisation** — the cloud layer transports the shipped PIO-1
  `.pixproj` as the sync unit; it does not fork the format (Article I). A cloud-specific schema
  extension, if ever needed, is an AGT-01 data-model decision, not a re-implementation.
- No plan/tasks (AGT-01); no logic/UI/data/backend/test code (AGT-03/05/04/06); no new technology
  decided here (S8).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED** (`specs/phase-1-core-engine/`): `data/project_io.py`
  (PIO-1 — the defensive `.pixproj` serialiser that **is** the sync unit), the `Document` tree (DOC-1 —
  what round-trips), the `logic/history.py` reversible-command path (HIS-1 — the edit path a future
  conflict/CRDT layer would reconcile, Slices B/C). Phase 10 **composes** these; it must not
  re-implement the serialiser or its security posture (Article I / VII).
- **The `.pixproj` is the atomic sync unit** (ROADMAP "Depends on: Phase 1 `data/project_io`"). Slice A
  depends **only** on Phase 1 — it needs no other phase — which is precisely why it is the unambiguous,
  independently-shippable slice recommended for "now".
- **Researcher grounding is COMPLETE** (`docs/subagent-report-the-researcher-a80a5c6a-20260704T102747.md`):
  provider-port shape over Drive v3/OneDrive-Graph/Dropbox v2 with capability diffs as an opaque cursor;
  desktop auth = PKCE-over-loopback (RFC 8252/7636) + Device Grant fallback, keyring token storage;
  atomic-write + sidecar-journal autosave/recovery; conflict-resolution split (tree/sequence CRDT for
  structure, tile-partitioned LWW for raster, logical-clock+site-id determinism); Article VII
  schema-validate + caps; ~70 % offline-testable. This grounds the *HOW* AGT-01 will plan; it does
  **not** unblock the §10 SUSPEND items, which are **scope/product decisions**, not capability lookups.
- **Article VI posture (the split):** Slice-A cloud/sync **and** Slice-B hybrid convergence are
  **batch/background** work off the per-frame render loop (REQ-P10-LOGIC-004/-006) — the 16 ms budget
  does not gate them; the contract is stays-responsive (REQ-P10-UI-005). **Slice C real-time editing
  CHANGES this: real-time remote-patch application + live-cursor draw RE-ENTER the per-frame budget**
  (REQ-P10-LOGIC-007 / REQ-P10-UI-013) — **flagged for AGT-10 per-frame assessment** (§8 DEP-3).
- **NEW vs REUSED (explicit):**
  - **NEW (Slice A):** `data/cloud/` (the port + a local/fake adapter; credential-gated real provider
    adapters behind the same interface per CL-B2), the `logic/` sync-state / version-history /
    autosave-policy models, constants (`AUTOSAVE_INTERVAL_MS`, `MAX_CLOUD_VERSIONS`,
    `MAX_CLOUD_PROJECT_BYTES`, `CLOUD_RETRY_LIMIT`), the Slice-A cloud UI.
  - **NEW (Slice B):** the shared-project storage/membership adapter (`data/cloud/`), the `logic/`
    hybrid convergence model, constants (`MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`,
    `MAX_COMMENTS_PER_PROJECT`, `CRDT_TILE_SIZE_PX`), the shared-projects/comments/presence UI.
  - **NEW (Slice C):** the client real-time transport port + loopback transport (`data/cloud/`), the
    `logic/` real-time apply + branching layer, constant `MAX_CRDT_UPDATE_BYTES`, the branching +
    real-time-cursor UI, and — **as new top-level scope outside the three layers** — the **real-time
    sync backend** (`REQ-P10-BACKEND-001/-002`; placement + ADR = AGT-01).
  - **REUSED:** `data/project_io.py` (PIO-1), the `Document` tree (DOC-1), the `history` path (HIS-1).

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

*(The §10.2 items are now ADJUDICATED — no open blockers remain. These are HOW/assessment flags.)*

- **FLAG-BACKEND (AGT-01, placement + ADR — REQUIRED).** The real-time sync backend
  (REQ-P10-BACKEND-001/-002) is a **NEW first-class, top-level component that sits OUTSIDE the desktop
  app's three-layer (`logic/`/`data/`/`ui/`) architecture** (CL-B4). **AGT-01 owns its placement and MUST
  author an ADR** for it (where it lives in the repo, its framework/hosting, how it is spun up
  in-process/subprocess for CI, and the client↔backend protocol contract). The desktop client's
  three-layer purity is preserved: the client reaches the backend only through the zero-Qt `data/cloud/`
  transport port (REQ-P10-DATA-010). The backend↔client loop MUST stay in the CI gate over localhost;
  the live third-party OAuth is the only out-of-CI piece (CL-B2).
- **FLAG-PERFRAME (AGT-10, per-frame assessment — REQUIRED for Slice C).** **REQ-P10-LOGIC-007
  real-time remote-patch application RE-ENTERS the per-frame budget** (`FRAME_BUDGET_MS`, 16 ms) — unlike
  batch Slice-A/B sync. **AGT-10 MUST assess remote-patch apply cost (and the REQ-P10-UI-013 live-cursor
  overlay draw) against the 16 ms budget** and direct batching/coalescing/dirty-rect strategy as needed.
  This is the one place Article VI's per-frame budget re-enters cloud scope.

- **DEP-1 (Researcher, grounding — COMPLETE).** `docs/subagent-report-the-researcher-a80a5c6a-20260704T102747.md`
  grounds the provider-port shape over Drive/OneDrive/Dropbox (opaque-cursor change tracking), OAuth
  PKCE-over-loopback + Device Grant + keyring token storage (informs CL-B3), the conflict-resolution /
  CRDT-OT landscape for a `.pixproj` (tree/sequence CRDT + tile-LWW; informs CL-B5), real-time transport
  options (WebSocket relay / WebRTC; informs CL-B4), and the ~70 % offline-testable slicing. Feeds
  AGT-01's plan; **does not** resolve the §10 scope decisions (product choices, not lookups).
- **DEP-2 (AGT-01, plan/ADR).** The concrete **cloud port verb signatures + adapter contract**, the
  **token-storage mechanism** (once CL-B3 is decided), the **autosave interval + version retention
  policy**, and the **version/recovery wire format** are HOW decisions; the observable contracts (one
  port, `.pixproj` round-trip, ordered version history, autosave/recovery, defensive load, provider
  isolation) are fixed here. **An ADR is expected for the cloud-port design.**
- **DEP-3 (AGT-01 / AGT-10, plan — responsiveness + per-frame).** Whether cloud operations run on a
  worker thread/executor and how progress/cancel is surfaced (REQ-P10-UI-005) is an AGT-01/AGT-10 HOW;
  Slice A/B are off the per-frame loop (REQ-P10-LOGIC-004/-006). **Slice C IS scoped: AGT-10 MUST assess
  per-frame remote-patch application (REQ-P10-LOGIC-007) + live-cursor draw (REQ-P10-UI-013) against
  Article VI's 16 ms budget** — see FLAG-PERFRAME above.
- **BF-1 (AGT-01, Article II).** New tuning values (`AUTOSAVE_INTERVAL_MS`, `MAX_CLOUD_VERSIONS`,
  `MAX_CLOUD_PROJECT_BYTES`, `CLOUD_RETRY_LIMIT`) resolve to named constants in `logic/constants.py`; no
  literals.
- **BF-2 (AGT-01, data-model).** Whether a cloud version needs a small metadata envelope (author,
  timestamp, parent-version) **around** the `.pixproj`, or the `.pixproj` itself is versioned, is an
  AGT-01 data-model HOW — the round-trip + ordered-history contracts hold regardless. **Not
  acceptance-changing for Slice A.**
- **BF-3 (AGT-01, constants — Slice B/C, Article II).** New tuning values `MAX_SHARED_MEMBERS`,
  `MAX_COMMENT_BYTES`, `MAX_COMMENTS_PER_PROJECT`, `MAX_CRDT_UPDATE_BYTES`, `CRDT_TILE_SIZE_PX` resolve to
  named constants in `logic/constants.py` (no literals; shared by client `data/cloud/` and the backend's
  validation caps).
- **BF-4 (AGT-01, data-model — convergence).** The concrete CRDT library (pycrdt/Yjs vs Automerge), the
  raster tile-partition scheme, and whether structured-metadata CRDT state rides inside the `.pixproj`
  envelope or a sidecar are AGT-01 data-model HOW; the hybrid determinism/commutativity/convergence
  contracts (REQ-P10-LOGIC-006/-007) hold regardless. Researcher §4.2/§4.3 grounds the options.

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** the cloud **port** + all adapters (fake, real providers, shared/
  membership, real-time transport) live in `data/cloud/` (zero Qt); the sync-state / version /
  autosave-policy **and** hybrid convergence + real-time apply models live in `logic/` (zero Qt); all
  cloud/collab UI lives in `ui/`. **No provider/transport detail leaks above the port**
  (REQ-P10-DATA-007). Enforced by `check_layering` / `check_cycles`. **The sync BACKEND
  (REQ-P10-BACKEND-001/-002) is deliberately OUTSIDE the three layers — new top-level scope; AGT-01
  places it + writes the ADR** (FLAG-BACKEND). The desktop client's purity is unaffected — it reaches the
  backend only via the zero-Qt transport port (REQ-P10-DATA-010).
- **Article II (numerics):** Slice-A constants (BF-1) + Slice-B/C constants (BF-3) go in
  `logic/constants.py`; no literals; the backend's validation caps reuse those named bounds.
- **Article IV (testing):** the local/fake adapter (REQ-P10-DATA-005) makes Slice A + Slice-B storage
  CI-testable with no network/credentials; the **localhost (in-process/subprocess) backend + loopback
  transport** (REQ-P10-BACKEND-001, REQ-P10-DATA-010) keeps **real-time in the CI gate**; hybrid
  convergence (REQ-P10-LOGIC-006/-007) is deterministic over an in-memory transport. Only the live
  provider OAuth is out-of-CI (CL-B2). Coverage gate ≥90/80.
- **Article V (UX):** REQ-P10-UI-006/-007/-008 make a11y + both themes + full translatability blocking
  gates for the cloud UI **and extend to the Slice-B/C UI** (REQ-P10-UI-009..013).
- **Article VI (performance) — the split:** Slice-A cloud/sync **and** Slice-B hybrid convergence are
  off the per-frame render loop (REQ-P10-LOGIC-004/-006); contract is stays-responsive (REQ-P10-UI-005).
  **Slice C real-time remote-patch apply (REQ-P10-LOGIC-007) + live-cursor draw (REQ-P10-UI-013) RE-ENTER
  the 16 ms budget — flagged for AGT-10 (FLAG-PERFRAME / DEP-3).**
- **Article VII (security) — CENTRAL this phase:** cloud-fetched `.pixproj` is **untrusted input** —
  defensively validated via PIO-1, `eval`-free, malformed/oversized → error (REQ-P10-DATA-006). **The
  same defence extends to collaboration payloads:** membership/comment/presence (REQ-P10-DATA-009), CRDT
  update blobs + presence over the transport (REQ-P10-DATA-010), and **every payload the backend ingests
  (REQ-P10-BACKEND-002)** — schema-validate + strict size/depth/dimension/byte caps, no `eval`/`exec`.
  Provider tokens live only in the client `data/cloud/` + **OS keyring** (CL-B3, REQ-P10-DATA-008),
  **never committed, never in `.pixproj`/logs, never sent to the backend**. Bounded numerics
  (REQ-P10-LOGIC-005 + BF-3); portable paths (`path_portability_check`).
- **Article VIII (SDD gate):** the §10.2 clarifications are **ADJUDICATED** (A2-D2 resolved); this spec
  is now **COMPLETE** across all three slices and **ready for `sdd-plan`** (AGT-01). An ADR is expected
  for both the cloud-port design (DEP-2) and the sync-backend placement (FLAG-BACKEND).
- **Article X (traceability):** every REQ (Slice A/B/C + backend) traces to an S-id / principle /
  article / forward-inherited primitive (PIO-1, DOC-1, HIS-1); full matrix in `traceability.md`.
- **Article XI (extensibility):** the ONE cloud port is the extension point — a new provider/transport is
  a new adapter; the collaboration + real-time tiers + backend layer on without weakening any article.

---

## 10. Clarifications

### 10.1 Resolved via `sdd-clarify` (category-1 defaults — A2-D2 Branch B)

Grounded in the ROADMAP "Done means", the shipped `.pixproj` (PIO-1), the constitution, and S7's
"optional cloud-sync layer". Each is non-acceptance-changing.

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | What is the sync unit? | The shipped **`.pixproj`** (PIO-1) — the cloud port transports it atomically; no new serialisation. | ROADMAP "`.pixproj` round-trips through the cloud port"; "Depends on Phase 1 `data/project_io`"; Article I. |
| **CL-2** | Where do provider adapters live? | Behind **ONE `data/cloud/` port**; no provider detail in `logic/`/`ui/`. | ROADMAP "adapters swappable behind one `data/cloud/` interface (no provider leak)"; Article I. |
| **CL-3** | Is cloud data trusted? | **No — untrusted**; validated via PIO-1, `eval`-free, malformed → error. | Prompt (Article VII, cloud data is untrusted); Article VII. |
| **CL-4** | Is cloud/sync on the 16 ms render loop? | **No — batch/background**, off the interactive loop (like Phases 7/8); contract is stays-responsive. | Prompt (largely off the interactive loop, like Phase 7/8); Article VI. |
| **CL-5** | What proves the adapters are swappable + testable? | A **local/fake adapter** implements the whole port so CI verifies the contract with **no network/credentials**; real providers behind the same interface. | Prompt (local-first desktop can't CI-test live providers); Article IV. |
| **CL-6** | What is "version history"? | Every `put` = a **new ordered version**; prior versions listable + retrievable + restorable. | ROADMAP "version history"; P2 determinism. |
| **CL-7** | What is "autosave/recovery"? | Policy-driven autosave to a **recovery slot**; post-crash **detect + restore** without clobbering the last explicit save. | ROADMAP "autosave/recovery"; editor norm. |
| **CL-8** | Are credentials committed? | **Never** — isolated in the adapter (Article VII §3). *(The storage mechanism is CL-B3, blocking.)* | Article VII §3. |

### 10.2 ADJUDICATED — formerly-blocking scope clarifications (resolved by the user)

**These five were SUSPENDED at `clarify` (A2-D2 Branch A) as acceptance-changing scope/product
decisions. They have now been ADJUDICATED by the user; the resolutions are authoritative and encoded
throughout §2/§4b/§4c above. No PENDING markers remain — this spec is COMPLETE.**

| # | Question | ADJUDICATED resolution (authoritative) | Encoded in |
| --- | --- | --- | --- |
| **CL-B1** | Which slices are in scope now? | **FULL SCOPE — Slices A + B + C are all in scope this phase.** All reserved REQ ids lifted to full acceptance. | §2, §4/§4b/§4c |
| **CL-B2** | Live provider integration vs port + fake adapter? | **Port + fully-tested FAKE adapter in the CI gate.** Real Drive/OneDrive/Dropbox adapters implemented behind the SAME port but **credential-gated / manually verified, OUT of CI**. CI determinism via the fake adapter. | REQ-P10-DATA-005, §6 |
| **CL-B3** | Token storage mechanism? | **OS keyring** (`keyring` lib — platform credential store). Tokens acquired/stored/used ENTIRELY inside the concrete `data/cloud/` adapter; never in `logic/`/`ui/`, never committed, never in `.pixproj`/logs. | REQ-P10-DATA-008 |
| **CL-B4** | Real-time: sync backend in scope, or only a loopback transport? | **Real-time sync BACKEND IS IN SCOPE** — an actual server/component, NOT only a loopback transport. It is a **SEPARATE component OUTSIDE the desktop app's three layers** (new top-level scope); **AGT-01 owns placement + an ADR**. It MUST be **CI-testable over localhost** (in-process/subprocess; loopback integration tests) so real-time stays in the CI gate — DISTINCT from the out-of-CI live provider OAuth (CL-B2). The client transport talks to it behind a port (REQ-P10-DATA-010). | REQ-P10-BACKEND-001/-002, REQ-P10-DATA-010, §4c note, §8 FLAG-BACKEND |
| **CL-B5** | Convergence semantics for a `.pixproj`? | **HYBRID convergence:** sequence/tree CRDT for STRUCTURED metadata (layer tree, frames, tilemap metadata) + per-TILE/REGION last-writer-wins for RASTER pixel buffers; deterministic ordering via logical-clock + site-id tiebreaks; enables git-like art branching; scalable to 8K without per-pixel overhead. | REQ-P10-LOGIC-006/-007 |

**All clarifications resolved — this spec is `COMPLETE`.** Every REQ id across Slices A/B/C and the sync
backend (`REQ-P10-DATA-001..010`, `REQ-P10-LOGIC-001..007`, `REQ-P10-UI-001..013`,
`REQ-P10-BACKEND-001..002`) has full acceptance criteria and ≥1 Gherkin scenario (§11). The spec is ready
for `sdd-plan` (AGT-01), which must additionally produce the cloud-port ADR (DEP-2) and the sync-backend
placement ADR (FLAG-BACKEND).

---

## 11. Acceptance criteria — Gherkin scenarios (Slices A + B + C)

One scenario per testable behaviour. Logic/data/backend scenarios are for **AGT-04** (pytest, headless —
the local/fake adapter + the localhost/loopback backend make cloud & real-time behaviour deterministic
with no external network); UI scenarios are for **AGT-06** (pytest-qt, `QT_QPA_PLATFORM=offscreen`),
**each run under BOTH light and dark themes** (REQ-P10-UI-007, global rule below). Scenario ids map to
`traceability.md`; tests are authored later (`pending`). **Slice-B/C scenarios follow the Slice-A ones.**

> Global rule (UI scenarios): *Given the app runs headless (`QT_QPA_PLATFORM=offscreen`) — the scenario
> is executed and asserted identically under the light theme and the dark theme.*

### Feature: Cloud port + `.pixproj` round-trip (REQ-P10-DATA-001..002, -007)
```gherkin
Scenario: SC-D001-1 the cloud port abstracts providers behind one interface
  Given the local/fake adapter implementing the data/cloud port
  When logic/ and ui/ use the port to put and get a project
  Then they reference only the port's own abstractions and exceptions
  And no provider SDK/credential/network type appears in logic/ or ui/ (check_layering passes; data/cloud imports no Qt)

Scenario: SC-D002-1 a .pixproj round-trips through the cloud port
  Given a Document serialised to a .pixproj by the shipped project_io serialiser
  When it is put through the cloud port and then fetched back
  Then the fetched bytes reconstruct an equivalent Document via project_io
  And the cloud layer added no serialisation format of its own
```

### Feature: Version history (REQ-P10-DATA-003, REQ-P10-LOGIC-003)
```gherkin
Scenario: SC-D003-1 every save creates a new, ordered, retrievable version
  Given a project stored through the cloud port
  When the project is saved three times
  Then list_versions returns three versions in a deterministic order
  And get(version) for an earlier version reconstructs the Document that version held

Scenario: SC-L003-1 the version-history model is ordered and immutable
  Given an ordered version-history model
  When a new version is appended
  Then a new ordered history is produced without mutating prior entries, deterministically, bounded by MAX_CLOUD_VERSIONS
```

### Feature: Autosave / recovery (REQ-P10-DATA-004, REQ-P10-LOGIC-002)
```gherkin
Scenario: SC-D004-1 an autosaved recovery survives an unclean restart and does not clobber the last save
  Given a working project autosaved to the recovery slot via the cloud port
  When the app restarts uncleanly (no explicit save happened)
  Then the unsaved recovery is detected and can be restored
  And restoring does not overwrite the user's last explicit saved version
  And a restored recovery is validated defensively (malformed -> error, no eval/exec)

Scenario: SC-L002-1 the autosave policy is a pure decision function
  Given a document-dirty flag, elapsed ticks, AUTOSAVE_INTERVAL_MS, and a last-autosave marker as inputs
  When the autosave decision function is evaluated twice with the same inputs
  Then it returns the identical decision, reading no wall-clock and no randomness (unit-testable without Qt)
```

### Feature: Testable adapter + untrusted-data defence + bounds (REQ-P10-DATA-005..006, REQ-P10-LOGIC-001, -004, -005)
```gherkin
Scenario: SC-D005-1 the local/fake adapter verifies the whole contract with no network or credentials
  Given the local/fake cloud adapter
  When the round-trip, version-history, and autosave/recovery scenarios run in CI headless
  Then they pass deterministically with no network access and no credentials

Scenario: SC-D006-1 a cloud-fetched .pixproj is treated as untrusted input
  Given a malformed, oversized, or unknown-version .pixproj served by the cloud port
  When the app fetches and loads it
  Then loading raises a defensive error (ProjectIOError or a data/cloud subclass) surfaced to the user
  And nothing is passed to eval/exec and the app does not crash (payload bounded by MAX_CLOUD_PROJECT_BYTES)

Scenario: SC-L001-1 the sync-state model is pure and deterministic
  Given a local version marker and the port's version list as inputs
  When the sync-state (up-to-date / local-ahead / remote-ahead / diverged) is computed twice
  Then both computations return the identical state using no wall-clock, randomness, or locale dependence

Scenario: SC-L004-1 cloud/sync work is off the interactive render loop
  Given a cloud save/fetch/autosave operation
  Then it is a batch/background operation not gated by FRAME_BUDGET_MS, and the UI stays responsive (REQ-P10-UI-005)

Scenario: SC-L005-1 cloud bounds are enforced from constants
  Given a version history above MAX_CLOUD_VERSIONS or a project above MAX_CLOUD_PROJECT_BYTES
  Then a domain error is raised (no silent degradation)
  And AUTOSAVE_INTERVAL_MS / CLOUD_RETRY_LIMIT come from constants (no literals)
```

### Feature: Cloud UI — save/load, version browser, recovery, connect (REQ-P10-UI-001..005)
```gherkin
Scenario: SC-UI-001-1 the user saves to and opens from the cloud
  Given a project open in the app and a connected (fake) provider
  When the user saves the project to the cloud and later opens it from the cloud
  Then the project is stored and reopened through the port, opening validates defensively, and the UI names no provider directly

Scenario: SC-UI-002-1 the version-history browser lists and restores prior versions
  Given a cloud project with several versions
  When the user opens the version-history browser and restores an earlier version
  Then the versions are listed in order and restoring reconstructs that version's Document (current unsaved state protected)

Scenario: SC-UI-003-1 the app prompts to recover unsaved work on restart
  Given an unsaved recovery exists after an unclean restart
  When the app starts
  Then it prompts the user to recover or discard, without overwriting the last explicit save until the user chooses

Scenario: SC-UI-004-1 the provider connect entry point is provider-agnostic
  Given the provider connect/disconnect entry point
  When the user connects to a (fake) provider
  Then the app behaves identically regardless of provider through the port's provider-agnostic surface
  # The concrete live-OAuth vs fake connect flow depends on CL-B2/CL-B3 (PENDING).

Scenario: SC-UI-005-1 cloud operations keep the UI responsive
  Given a cloud save/load/version-fetch/autosave operation
  When the operation runs
  Then the UI does not freeze and stays responsive (operation is off the per-frame loop; worker-thread realisation is AGT-01/AGT-10)
```

### Feature: a11y, theming, i18n (REQ-P10-UI-006..008) — NFR
```gherkin
Scenario: SC-UI-006-1 cloud controls expose accessible names and keyboard focus
  Given the cloud controls (save/open-from-cloud, version list + restore, recovery prompt, provider connect/disconnect)
  When each control is inspected and tabbed through
  Then each has a non-empty accessible name, is keyboard reachable in a logical order, and shows a visible focus indicator

Scenario: SC-UI-007-1 the cloud UI renders correctly in both themes
  Given the app
  When rendered under the light theme and the dark theme
  Then the cloud dialogs, version browser, recovery prompt, and provider-connect UI render legibly with role-based colours

Scenario: SC-UI-008-1 no Phase-10 user-visible string is a bare literal
  Given the Phase-10 ui/ sources (Slice A + B + C)
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings (cloud/collab menu+dialog labels, version columns, recovery text, comments, presence, branching, status/errors)
```

### Feature: Slice B — shared-project storage + membership + untrusted payloads (REQ-P10-DATA-009)
```gherkin
Scenario: SC-D009-1 a project is shared with bounded members and payloads are validated
  Given a project stored through the cloud port and shared with a set of members via the fake adapter
  When membership, comment, and presence-metadata payloads are stored and fetched
  Then members/comments are bounded by MAX_SHARED_MEMBERS / MAX_COMMENTS_PER_PROJECT / MAX_COMMENT_BYTES
  And a malformed/oversized payload raises a defensive error (no eval/exec), verified headless with no network/credentials
  And no provider detail appears in logic/ or ui/ (check_layering passes)
```

### Feature: Slice B — deterministic hybrid convergence (REQ-P10-LOGIC-006)
```gherkin
Scenario: SC-L006-1 concurrent .pixproj edits converge deterministically via the hybrid model
  Given two replicas of a Document with concurrent structured-metadata edits (layer tree/frames/tilemap) and concurrent raster edits
  When the same set of operations is applied to each replica in different (permuted) orders
  Then the structured metadata converges identically (tree/sequence CRDT commutativity)
  And same-tile raster edits resolve by logical-clock + site-id LWW while different-tile edits both survive
  And both replicas converge to a byte-identical Document, using no wall-clock/randomness, scalable to 8K with no per-pixel CRDT overhead
```

### Feature: Slice B — shared-projects / comments / presence UI (REQ-P10-UI-009..011)
```gherkin
Scenario: SC-UI-009-1 the user shares a project and sees members
  Given a project open in the app and a connected (fake) provider
  When the user shares the project and invites members
  Then the shared-projects panel lists members through the port's provider-agnostic membership surface, naming no provider

Scenario: SC-UI-010-1 the user adds and resolves a validated comment
  Given a shared project
  When the user adds a comment and later resolves it
  Then the comment (bounded by MAX_COMMENT_BYTES, validated, never eval/exec) is threaded and its resolved state is shown, with translatable labels

Scenario: SC-UI-011-1 the presence surface shows who else is present
  Given a shared project with other collaborators present
  When the presence surface renders
  Then it shows the present members from the ephemeral presence channel (not persisted into the .pixproj)
```

### Feature: Slice C — client real-time transport port (REQ-P10-DATA-010)
```gherkin
Scenario: SC-D010-1 CRDT updates and presence flow over a localhost-testable transport port
  Given the in-memory/loopback transport implementing the data/cloud transport port
  When a client sends CRDT updates and awareness/presence messages to the backend and receives peers'
  Then the exchange runs in CI over loopback with no external network or credentials
  And every inbound CRDT-update blob / presence payload is schema-validated (bounded by MAX_CRDT_UPDATE_BYTES, no eval/exec; malformed -> error)
  And no transport/provider type leaks above the port (check_layering passes; data/ imports no Qt)
```

### Feature: Slice C — real-time apply layer + git-like branching (REQ-P10-LOGIC-007)
```gherkin
Scenario: SC-L007-1 remote CRDT updates apply and converge, and a branch merges conflict-free
  Given a local Document and a stream of remote CRDT updates over the loopback transport
  When the updates are applied via the real-time apply layer
  Then the Document converges deterministically per the hybrid model (REQ-P10-LOGIC-006)
  And a cloned branch edited concurrently merges back with no manual conflict resolution, reconstructable history preserved

Scenario: SC-L007-2 remote-patch application is flagged for the per-frame budget
  Given real-time remote-patch application (and the live-cursor overlay draw)
  Then it re-enters the FRAME_BUDGET_MS (16 ms) per-frame budget and is flagged for AGT-10 per-frame assessment (FLAG-PERFRAME)
  # Distinct from batch Slice-A/B sync which is off the per-frame loop.
```

### Feature: Slice C — the sync backend (REQ-P10-BACKEND-001..002)
```gherkin
Scenario: SC-BK-001-1 the sync backend is a separate component, CI-testable over localhost
  Given the real-time sync backend spun up in-process/subprocess on localhost
  When multiple clients connect over the loopback transport and edit concurrently
  Then the backend relays and persists CRDT updates + awareness/presence and all clients converge to an identical Document
  And the whole backend<->client loop runs in the CI gate with no third-party credentials or external network
  And the backend lives OUTSIDE the desktop app's three layers (placement + ADR owned by AGT-01)

Scenario: SC-BK-002-1 the backend treats every ingested payload as untrusted input
  Given the sync backend receiving CRDT-update, presence, and comment payloads
  When a malformed, oversized, or deeply-nested payload arrives
  Then the backend schema-validates against strict size/depth/dimension/byte caps and rejects it with a clear error (no eval/exec, no crash, no memory exhaustion)
  And the backend never receives or stores provider OAuth tokens (tokens stay in the client keyring, CL-B3)
```

### Feature: Slice C — art-branching + real-time-cursor UI (REQ-P10-UI-012..013)
```gherkin
Scenario: SC-UI-012-1 the user branches, diffs, and merges a project
  Given a project open in the app
  When the user branches it, edits the branch, views the diff, and merges it back
  Then the merge is conflict-free (resolved by REQ-P10-LOGIC-007) and the merge outcome is surfaced, with translatable labels

Scenario: SC-UI-013-1 other collaborators' cursors render live as ephemeral overlays
  Given a shared project with other collaborators editing in real time
  When their cursors/selection change
  Then the UI renders them as ephemeral overlays (never persisted into the .pixproj), their per-frame draw subject to AGT-10 assessment
```

---

## 12. Exit / status

- Forward spec authored for **Phase 10 — Cloud & Collaboration**, **all three slices (A + B + C)**,
  §10.2 clarifications **ADJUDICATED**. **34 REQ-IDs drafted with full acceptance:** **10 DATA**
  (`REQ-P10-DATA-001..010`) + **7 LOGIC** (`REQ-P10-LOGIC-001..007`) + **13 UI** (`REQ-P10-UI-001..013`)
  + **2 BACKEND** (`REQ-P10-BACKEND-001..002`) — each traced to an S-id / principle / article /
  forward-inherited primitive (PIO-1 `project_io` = the sync unit; DOC-1 `Document`; HIS-1 `history`)
  per Article X.
  - Slice A (21): `DATA-001..008` + `LOGIC-001..005` + `UI-001..008` — intact, unchanged.
  - Slice B (5): `DATA-009` (shared storage + membership) + `LOGIC-006` (hybrid convergence) +
    `UI-009..011` (shared / comments / presence).
  - Slice C (8): `DATA-010` (client transport port) + `LOGIC-007` (real-time apply + branching) +
    `UI-012..013` (branching / real-time cursors) + `BACKEND-001..002` (the NEW first-class sync backend).
- **8 category-1 clarifications resolved** (§10.1) + **5 formerly-blocking clarifications ADJUDICATED**
  (§10.2): **CL-B1** = FULL scope (A+B+C); **CL-B2** = port + fake adapter in CI, real providers
  credential-gated/out-of-CI; **CL-B3** = OS keyring inside `data/cloud/`; **CL-B4** = real-time sync
  BACKEND in scope as a separate top-level component (localhost-CI-testable, AGT-01 places + ADRs);
  **CL-B5** = HYBRID convergence (tree-CRDT + tile/region-LWW, logical-clock+site-id, 8K-scalable,
  git-like branching).
- **New constants flagged for `logic/constants.py`** (Article II): Slice A `AUTOSAVE_INTERVAL_MS`,
  `MAX_CLOUD_VERSIONS`, `MAX_CLOUD_PROJECT_BYTES`, `CLOUD_RETRY_LIMIT` (BF-1); Slice B/C
  `MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`, `MAX_COMMENTS_PER_PROJECT`, `MAX_CRDT_UPDATE_BYTES`,
  `CRDT_TILE_SIZE_PX` (BF-3).
- **Explicit flags for AGT-01 / AGT-10 (§8):** **FLAG-BACKEND** — AGT-01 owns the sync-backend placement
  (OUTSIDE the three layers) + a REQUIRED ADR; **FLAG-PERFRAME / DEP-3** — AGT-10 MUST assess Slice-C
  real-time remote-patch apply (REQ-P10-LOGIC-007) + live-cursor draw (REQ-P10-UI-013) against the 16 ms
  budget; DEP-2 — AGT-01 cloud-port ADR (signatures, keyring keying, autosave interval, version/CRDT
  wire format); DEP-1 — Researcher grounding COMPLETE (feeds the plan).
- **Article VI split encoded:** Slice A + B are batch/off-loop; **Slice C real-time RE-ENTERS the
  per-frame budget** (the one place the 16 ms budget returns to cloud scope).
- Acceptance scenarios cover **every** functional + NFR requirement across all slices (see
  `traceability.md`); tests authored later by AGT-04 (data/logic/backend, headless via the fake adapter +
  localhost/loopback backend) / AGT-06 (UI, both themes), `pending`.
- **STATUS: COMPLETED** — spec COMPLETE across Slices A/B/C + backend, no open clarifications, no
  `blocked`/`PENDING` rows. **Ready for `sdd-plan` (AGT-01)**, which must produce the cloud-port ADR
  (DEP-2) and the sync-backend placement ADR (FLAG-BACKEND).
