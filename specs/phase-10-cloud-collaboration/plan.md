# Plan — Phase 10: Cloud & Collaboration

| Field | Value |
| --- | --- |
| Feature | `phase-10-cloud-collaboration` |
| Author | AGT-01 (Architecture) via `sdd-plan` |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, **VI**, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 10 before any `data/cloud/*`, `logic/{sync_state,autosave,version_history,convergence,realtime_apply,cloud_validation}.py`, `sync_backend/*`, or cloud/collab UI exists. The **shipped** `data/project_io.py` (PIO-1: defensive `eval`-free `.pixproj`, `ProjectIOError`, `_SUPPORTED_VERSIONS=1..5`, zlib+base64, `pathlib`), the `Document` tree (DOC-1), and `logic/history.py` (HIS-1) are **reused, not re-authored**. |
| Over spec | `specs/phase-10-cloud-collaboration/spec.md` (34 REQ: `REQ-P10-DATA-001..010`, `REQ-P10-LOGIC-001..007`, `REQ-P10-UI-001..013`, `REQ-P10-BACKEND-001..002`) + `traceability.md`. §10.2 clarifications **ADJUDICATED** (CL-B1..CL-B5); no PENDING rows. |
| Stack source | S8 (fixed) + **three new grounded runtime deps** (AGT-09/AGT-01 manifest, PL10-D14): **`keyring`** (OS token store, CL-B3), **`pycrdt`** (structured tree/sequence CRDT + presence, BF-4/ADR-0028), **`websockets`** (backend relay + client WS transport, ADR-0027). Grounded by The Researcher (`docs/subagent-report-the-researcher-a80a5c6a-20260704T102747.md`) → PL10-D1 Branch B (no RESEARCH REQUEST). |
| ADRs filed | **ADR-0026** (cloud-port design: one `data/cloud/` port + verb set + normalized types + opaque cursor + capability model; fake adapter in CI / real providers out-of-CI; PKCE+loopback+Device-Grant auth with **OS-keyring** token isolation; atomic autosave/recovery; cloud version envelope + remote-revision mapping BF-2; untrusted-cloud defence); **ADR-0027** (sync-backend placement: new top-level **`sync_backend/`** OUTSIDE the three layers; asyncio-WebSocket relay + persistence; client `TransportPort` loopback/real split; the **layering-rule update**; backend untrusted-input + no-tokens; **Article VI per-frame re-entry → AGT-10 FLAG-PERFRAME**); **ADR-0028** (HYBRID convergence: pycrdt tree/sequence CRDT for structure + pure tile/region-LWW for raster; logical-clock+site-id determinism; fork-doc branching; CRDT-state sidecar; BF-4) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-10 spec — the **cloud &
collaboration** milestone that lets a `.pixproj` live in the cloud with **version history and
autosave/recovery** behind **one swappable `data/cloud/` port** (Slice A), be **shared with comments,
presence and deterministic hybrid conflict resolution** (Slice B), and be edited **in real time over a
first-class sync backend with git-like art branching** (Slice C) — while keeping the desktop client's
three-layer purity intact and the whole thing (except live-provider OAuth) **hermetically CI-testable**.
It maps every REQ to its S11 layer, **freezes the public interface** of the new `data/cloud/` port and the
new `logic/` models before implementation, rules the DEP-2 / FLAG-BACKEND / BF-4 HOW decisions in
**ADR-0026 / ADR-0027 / ADR-0028**, places the nine new numerics in `logic/constants.py` with names
distinct from every shipped constant (Article II / BF-1 / BF-3), **updates the layering rules** so the new
`data/cloud/` subpackage and the new top-level `sync_backend/` component are correctly governed while the
client's three-layer purity still holds (§4.4, done — `check_layering`/`check_cycles` re-run, both exit
`0`), and routes the **Slice-C per-frame NFR** (real-time remote-patch apply + live-cursor draw) to AGT-10
(FLAG-PERFRAME / DEP-3). It is decomposed into **slice-by-slice A → B → C** dependency-ordered work items
in `tasks.md`, each an independently gate-green, CI-green shippable increment.

The stack is fixed by S8 for the desktop app; three new runtime deps (`keyring`, `pycrdt`, `websockets`)
are **grounded, not invented** (Researcher §2/§4/§4.5) and are an explicit AGT-09/AGT-01 manifest decision
(PL10-D14, Article VII implications). The `sdd-analyze` C1 gate is run over constitution/spec/plan/tasks as
the pre-implement gate (Article VIII; see `analyze-report.md`).

## 2. The provider/transport-isolation invariant (Article I + Article VII — CENTRAL; ADR-0026/0027)

> **No provider SDK type, credential/token type, HTTP/network type, transport type, or backend/server
> import ever appears in `logic/` or `ui/`, or in the cloud port's public signatures — they live ONLY
> inside a concrete adapter under `data/cloud/`. Tokens are acquired/stored/used entirely inside
> `data/cloud/` via the OS keyring, never above the port, never in a `.pixproj`/log, never on the backend.
> The real-time backend is a separate top-level `sync_backend/` package OUTSIDE the three layers; the
> client reaches it only over the ZERO-Qt `data/cloud/` transport port at run time, never by import.**

This is realised **structurally**: `data/cloud/` is a normal `data/` subpackage (zero Qt — already
governed) exposing only normalized `RemoteItem`/`CloudVersion`/`Cursor`/`CloudCapabilities` types and its
own `CloudError` family; `logic/` and `ui/` depend solely on the port's abstractions. Untrusted cloud data
(`.pixproj` via PIO-1; CRDT/membership/comment/presence via pure `logic/cloud_validation.py`) is validated,
`eval`-free, malformed → error. The new **layering-rule update** (§4.4) proves it: `check_layering` forbids
`logic`/`data`/`ui` from importing `sync_backend`, and forbids `sync_backend` from importing `ui`/`data`/Qt
(it may reuse pure `logic/`). Both scripts exit `0` on the current tree after the update.

## 3. Stack / domain decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language / stack | Python 3.12+; stdlib + NumPy (shipped); reuse `data/project_io` (PIO-1), `logic/document` (DOC-1), `logic/history` (HIS-1), `logic/pixel_buffer` | S8 |
| Cloud port | **ONE** `data/cloud/port.py::CloudPort` ABC — verbs `put/get/list_versions/latest/delete/put_recovery/get_recovery/capabilities`; opaque `Cursor` change tracking; normalized `CloudVersion`/`RemoteItem`/`CloudCapabilities`; `CloudError` family | REQ-P10-DATA-001/-007; ADR-0026 §1; Researcher §1 |
| Adapters (CI split) | **Fake adapter in CI** (local FS/in-memory, whole contract, no network/creds); **real Drive/OneDrive/Dropbox adapters behind the SAME port, credential-gated / out-of-CI** (`pytest.mark.cloud_live`) | REQ-P10-DATA-005; CL-B2; ADR-0026 §2; Researcher §6 |
| Auth + tokens | PKCE (`S256`) over loopback (RFC 8252/7636) + Device Grant (RFC 8628) fallback; **OS keyring** (`keyring` lib) token store keyed `pixelart-creator:cloud:{provider}`; ZERO-Qt `data/cloud/`; only browser-launch in `ui/` | REQ-P10-DATA-008; CL-B3; ADR-0026 §3; Researcher §2 |
| Autosave/recovery | Atomic **temp-write + `fsync` + `os.replace`** + a discoverable **sidecar recovery journal**; pure `should_autosave()` policy (elapsed as input); restore never clobbers last explicit save; restored blob validated | REQ-P10-DATA-004, REQ-P10-LOGIC-002; ADR-0026 §4; Researcher §3 |
| Sync unit | The shipped **`.pixproj`** (PIO-1) transported as-is; the cloud layer adds **no** serialisation format; version = a small metadata **envelope** around the bytes (BF-2) | REQ-P10-DATA-002/-003; ADR-0026 §1/§5; Article I |
| Version history | Ordered, immutable `logic/version_history.py`; bounded by `MAX_CLOUD_VERSIONS`; local↔remote revision-id map; pin where `supports_named_revisions` | REQ-P10-DATA-003, REQ-P10-LOGIC-003; ADR-0026 §5 |
| Sync-state model | Pure deterministic `compute_sync_state()` (up-to-date/local-ahead/remote-ahead/diverged) `f(local marker, version list)`; no wall-clock/random/locale | REQ-P10-LOGIC-001; Article I/P2 |
| Untrusted input | `.pixproj` via PIO-1 defensive path; CRDT/membership/comment/presence via pure `logic/cloud_validation.py` (schema + size/depth/dimension/byte caps); **never `eval`/`exec`** | REQ-P10-DATA-006/-009/-010, REQ-P10-BACKEND-002; ADR-0026 §6; Researcher §5 |
| Shared projects / membership (B) | `data/cloud/shared_adapter.py` behind the SAME port family (fake adapter implements it → CI); bounded members; comment/presence payloads validated | REQ-P10-DATA-009; ADR-0026 §2/§6; CL-B1 |
| Convergence (B) | **HYBRID:** `pycrdt` tree/sequence CRDT for structured metadata (layer tree/frames/tilemap) + pure NumPy **per-tile/region LWW** for raster; logical-clock + site-id; permuted-order → byte-identical `Document`; 8K-scalable | REQ-P10-LOGIC-006; CL-B5; ADR-0028 §1/§2/§3; Researcher §4 |
| Client transport (C) | `data/cloud/transport.py::TransportPort`; **loopback/in-memory transport in CI**, real `ws_transport.py` credential/network-gated out-of-CI; carries CRDT updates + awareness/presence | REQ-P10-DATA-010; ADR-0027 §3; Researcher §4.5 |
| Real-time apply + branching (C) | `logic/realtime_apply.py` applies remote CRDT/OT updates (converges via §convergence); **git-like branching** = forked pycrdt doc + tile-LWW clone → conflict-free merge; history reconstructable from the persisted update log | REQ-P10-LOGIC-007; CL-B5; ADR-0028 §3; Researcher §4.6 |
| Sync **backend** (C) | **NEW top-level `sync_backend/`** OUTSIDE the three layers; asyncio **WebSocket** relay + per-doc update-log/presence persistence; **spun up in-process/subprocess for CI** over loopback; reuses pure `logic/{convergence,cloud_validation}`; imports **no** `ui/`/`data/`/Qt | REQ-P10-BACKEND-001/-002; CL-B4; ADR-0027 §1/§2/§4 |
| Presence | pycrdt **awareness** protocol — ephemeral cursors/selection kept OUT of the persisted `.pixproj`/sidecar | REQ-P10-UI-011/-013; ADR-0028 §2; Researcher §4.5 |
| CRDT-state persistence | A **sidecar** collaboration doc per shared project (not embedded in `.pixproj`, no schema bump); presence never persisted | BF-4; ADR-0028 §4 |
| Responsiveness | Cloud ops off the GUI thread (`ui/cloud_worker.py`, the Phase-7/8 worker precedent); progress/cancel where warranted | REQ-P10-UI-005; DEP-3; ADR-0027 §7 |
| **Article VI split** | Slice A/B batch/off the per-frame loop; **Slice C real-time apply (REQ-P10-LOGIC-007) + live-cursor draw (REQ-P10-UI-013) RE-ENTER the 16 ms budget → REQUIRED AGT-10 FLAG-PERFRAME + CI perf-gate recommendation** | REQ-P10-LOGIC-004/-007, REQ-P10-UI-013; ADR-0027 §7; DEP-3 |
| Bounds | 9 named constants in `logic/constants.py`; exceeding → domain error | REQ-P10-LOGIC-005; Article II/VII; §8 |
| Testing | pytest + Hypothesis (data/logic headless via the fake adapter + in-memory transport + in-process backend; permuted-order convergence property tests), pytest-qt both themes (UI); live-provider OAuth `pytest.mark.cloud_live` out-of-CI | S8, Article IV; Researcher §6 |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`+`sync_backend/`) | Article III |

No Phase-10 logic/data decision places Qt in `logic/`/`data/`/`sync_backend/` (**PL10-D2 → Branch B held**).
All cloud/collab surfaces live only in `ui/`; the sole Qt file outside `ui/` remains `ui/commands.py`
(unchanged — no new undoable operation; cloud/collab/real-time are sync/session state, PL10-D13).

## 4. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`; `data/` → `logic/`; `sync_backend/` → `logic/`)
and acyclic (verified §4.4/§11). No `logic → data`, no `logic`/`data`/`sync_backend` → `ui`/Qt, no client
layer → `sync_backend`.

### 4.1 New / extended `logic/` modules (pure, zero Qt)

| Module | Change | Responsibility | Depends on (intra-logic) | REQ | Slice |
| --- | --- | --- | --- | --- | --- |
| `constants.py` | extend | Add the 9 cloud/collab numerics (leaf, no imports). **Names distinct from every shipped constant (BF-1/BF-3).** | — | LOGIC-005 | A/B/C |
| `sync_state.py` | **new** | `SyncState` (module-local enum: UP_TO_DATE/LOCAL_AHEAD/REMOTE_AHEAD/DIVERGED) + `compute_sync_state(local_marker, versions)` — pure deterministic. `SyncError`. Zero Qt. | `constants` | LOGIC-001 | A |
| `autosave.py` | **new** | `should_autosave(dirty, elapsed_ticks, last_autosave_marker, interval_ms=AUTOSAVE_INTERVAL_MS) -> bool` — pure decision fn; elapsed is an INPUT (no wall clock). `AutosaveError`. Zero Qt. | `constants` | LOGIC-002 | A |
| `version_history.py` | **new** | `CloudVersion` (id, ordinal, created_marker, size_bytes, is_pinned, parent_version_id, remote_revision_id); `VersionHistory` ordered/immutable (`append`→new history; deterministic order; ≤ `MAX_CLOUD_VERSIONS` → `VersionHistoryError`). Zero Qt. | `constants` | LOGIC-003, 005 | A |
| `cloud_validation.py` | **new** | Pure untrusted-input validators + message vocabulary: schema + strict size/depth/dimension/byte caps for membership/comment/presence payloads (`MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`, `MAX_COMMENTS_PER_PROJECT`) and CRDT-update blobs (`MAX_CRDT_UPDATE_BYTES`); **never `eval`/`exec`**. Shared by client `data/cloud/` AND `sync_backend/`. `CloudValidationError`. Zero Qt. | `constants` | DATA-009, 010, BACKEND-002 | B/C |
| `convergence.py` | **new** | HYBRID model: `pycrdt` tree/sequence CRDT wiring for structured metadata + pure NumPy per-tile/region **LWW-Register** (`CRDT_TILE_SIZE_PX`) for raster; logical-clock + site-id tiebreak; deterministic (no wall-clock/random/locale); reconciles HIS-1 command stream over DOC-1. `ConvergenceError`. Zero Qt (pycrdt is a pure dep). | `document`, `history`, `pixel_buffer`, `constants` | LOGIC-006 | B |
| `realtime_apply.py` | **new** | Apply remote CRDT/OT updates to the local `Document` via `convergence`; git-like branching (fork doc + tile-LWW clone → conflict-free merge; history reconstructable). **Per-frame flagged (Article VI, AGT-10 FLAG-PERFRAME).** `RealtimeError`. Zero Qt. | `convergence`, `document`, `cloud_validation`, `constants` | LOGIC-007 | C |

`constants.py` stays a leaf. `SyncState` + the CRDT message vocabulary are **module-local** enumerated
vocabulary (ADR-0001 precedent). `sync_state`/`autosave`/`version_history`/`cloud_validation` are pure
leaves over `constants`; `convergence`/`realtime_apply` reach only shipped downstream logic (downward, no
cycle). **No `logic → data`** edge and **no** `logic → sync_backend` edge.

### 4.2 New `data/cloud/` subpackage (Qt-free I/O + network, governed as `data/`)

| Module | Change | Responsibility | Depends on | REQ | Slice |
| --- | --- | --- | --- | --- | --- |
| `cloud/__init__.py` | **new** | Package marker; re-exports the port + `CloudError` family. | — | DATA-001 | A |
| `cloud/port.py` | **new** | `CloudPort` ABC + normalized `RemoteItem`/`CloudVersion`/`Cursor`/`CloudCapabilities`; `CloudError`/`CloudDataError(ProjectIOError)`. **No provider type in signatures.** Zero Qt. | `logic/version_history`, `constants` | DATA-001, 007 | A |
| `cloud/fake_adapter.py` | **new** | Local-FS/in-memory adapter implementing the WHOLE port (put/get/list/latest/delete/recovery/caps) — the CI-testable contract, no network/creds. Zero Qt. | `cloud/port`, `data/project_io` | DATA-002, 003, 004, 005 | A |
| `cloud/auth.py` | **new** | Pure PKCE (`S256`) + loopback listener (RFC 8252) + token exchange/refresh + Device Grant (RFC 8628) fallback. Only browser-launch delegated to `ui/`. Zero Qt. | `cloud/token_store`, `constants` | DATA-008 | A |
| `cloud/token_store.py` | **new** | `keyring`-backed token isolation (set/get/delete), keyed `pixelart-creator:cloud:{provider}`; tokens **never** leave `data/cloud/`. Zero Qt. | `constants` | DATA-008 | A |
| `cloud/providers/{drive,onedrive,dropbox}.py` | **new** | Real provider adapters implementing the SAME port; **credential-gated / out-of-CI** (`pytest.mark.cloud_live`). Capability differences via `CloudCapabilities`. Zero Qt. | `cloud/port`, `cloud/auth` | DATA-001, 007, 008 | A |
| `cloud/shared_adapter.py` | **new** | Shared-project storage + membership behind the port family; fake adapter implements it (CI). Payloads validated via `logic/cloud_validation`. Zero Qt. | `cloud/port`, `logic/cloud_validation` | DATA-009 | B |
| `cloud/transport.py` | **new** | `TransportPort` (send/recv CRDT updates + awareness/presence). **No transport type above the port.** Zero Qt. | `logic/cloud_validation`, `constants` | DATA-010 | C |
| `cloud/loopback_transport.py` | **new** | In-memory/loopback `TransportPort` — real-time exchange in CI, no network/creds. Zero Qt. | `cloud/transport` | DATA-010, BACKEND-001 | C |
| `cloud/ws_transport.py` | **new** | Real WebSocket `TransportPort` (uses `websockets`); credential/network-gated, out-of-CI. Zero Qt. | `cloud/transport` | DATA-010 | C |

`data/cloud/` imports **no Qt** and **no** `sync_backend` (§4.4). `CloudDataError` subclasses
`ProjectIOError` (PIO-1 family). Provider SDKs (Google/Graph/Dropbox client libs) are imported **only**
inside `cloud/providers/*` — never above the port.

### 4.3 New top-level `sync_backend/` (OUTSIDE the three layers — ADR-0027)

| Module | Change | Responsibility | Depends on | REQ | Slice |
| --- | --- | --- | --- | --- | --- |
| `sync_backend/__init__.py` | **new** | Package marker (separate deployable; excluded from the desktop wheel). | — | BACKEND-001 | C |
| `sync_backend/server.py` | **new** | asyncio **WebSocket** relay of CRDT updates + awareness/presence across a shared doc's peers; **spin-up API** for in-process/subprocess CI; validates every payload via `logic/cloud_validation` (caps, no eval/exec); **never** receives/stores tokens. Imports NO `ui`/`data`/Qt; MAY reuse pure `logic/`. | `logic/cloud_validation`, `logic/convergence`, `constants`, `websockets` | BACKEND-001, 002 | C |
| `sync_backend/store.py` | **new** | Per-`document_id` persistence of the ordered CRDT update log + latest presence (in-memory for CI; file-backed for a running server). Imports NO `ui`/`data`/Qt. | `logic/constants` | BACKEND-001 | C |

### 4.4 Layering-rule update + proof (PL10-D3 — cycle-free by construction; DONE at plan time)

**`data/cloud/` needs no new rule** — it is a `data/` subpackage, already governed (zero Qt, no `ui/`
import). The **new** governance (`scripts/check_layering.py`, edited this phase, ADR-0027 §5):

- `logic`, `data`, `ui` gain `sync_backend` in their forbidden-import set → **no client layer imports the
  backend** (the client reaches it only via the `data/cloud/` transport port at run time).
- A new `sync_backend` layer rule forbids Qt + `pixelart_creator.ui` + `pixelart_creator.data` → **the
  backend is headless, never touches the client's keyring tokens / provider adapters**; it MAY reuse pure
  `pixelart_creator.logic`.
- **CI invocation (AGT-09):** `check_layering --root pixelart_creator` (client 3 layers) **and**
  `--root .` (governs `sync_backend/`); `check_cycles --root pixelart_creator` **and** `--root sync_backend`.

New intra-`logic/` edges: `sync_state → {constants}`, `autosave → {constants}`, `version_history →
{constants}`, `cloud_validation → {constants}`, `convergence → {document, history, pixel_buffer,
constants}`, `realtime_apply → {convergence, document, cloud_validation, constants}`. New `data/cloud/`
edges point **down** into `logic/` + `data/project_io` only. New `sync_backend/` edges point **down** into
`logic/` only. Resulting one-way chain:

```
ui/cloud_actions / version_history_browser / recovery_prompt / provider_connect
                              →  logic/{sync_state, autosave, version_history}  →  logic/constants
                              →  data/cloud/{port, fake_adapter, auth, token_store, providers/*}
data/cloud/fake_adapter       →  data/project_io (PIO-1)  →  logic/document
data/cloud/{shared_adapter, transport}  →  logic/cloud_validation  →  logic/constants
ui/{shared_projects_panel, comments_panel, presence_panel}  →  data/cloud/shared_adapter
ui/{branching_panel, realtime_cursors_overlay}  →  logic/realtime_apply  →  logic/convergence
                                                                          →  logic/{document, history, pixel_buffer}
ui/cloud_worker               →  data/cloud/*   (off-GUI-thread cloud ops)
sync_backend/server           →  logic/{cloud_validation, convergence}  +  websockets   (NO ui/data/Qt)
sync_backend/store            →  logic/constants
```

No back-edge (`logic → data`, `logic`/`data`/`sync_backend` → `ui`/Qt, or client → `sync_backend`) exists.
`check_layering` (`--root pixelart_creator` **and** `--root .`) and `check_cycles` (`--root
pixelart_creator` **and** `--root sync_backend`) therefore stay `0` — **verified at plan time on the shipped
tree after the rule update** (§11): client scan clean (120 modules), whole-repo scan clean (0 governed
modules until the package lands), cycles clean (121 modules). AGT-03 re-runs all four invocations as each
slice lands.

## 5. Frozen interface contracts (Slices A/B/C)

Frozen **before** implementation so downstream slices bind to a stable surface. Qt-free. `CloudError`,
`SyncError`, `AutosaveError`, `VersionHistoryError`, `CloudValidationError`, `ConvergenceError`,
`RealtimeError` subclass `ValueError` (Phase-1 convention); `CloudDataError` subclasses `ProjectIOError`
(PIO-1 family). `SyncState` + the CRDT message vocabulary are module-local (ADR-0001). Pure functions are
deterministic (no wall-clock/random/locale).

```python
# logic/sync_state.py — pure deterministic sync-state (zero Qt)
class SyncError(ValueError): ...
class SyncState(Enum): UP_TO_DATE; LOCAL_AHEAD; REMOTE_AHEAD; DIVERGED   # module-local (ADR-0001)
def compute_sync_state(local_version_id: Optional[str],
                       versions: Sequence["CloudVersion"]) -> SyncState:
    """Pure f(local marker, ordered version list). No wall-clock/random/locale. REQ-P10-LOGIC-001."""

# logic/autosave.py — pure autosave policy (zero Qt)
class AutosaveError(ValueError): ...
def should_autosave(dirty: bool, elapsed_ticks: int, last_autosave_marker: int,
                    interval_ms: int = AUTOSAVE_INTERVAL_MS) -> bool:
    """Elapsed time is an INPUT (never read from a clock inside). Deterministic. REQ-P10-LOGIC-002."""

# logic/version_history.py — ordered immutable history (zero Qt)
class VersionHistoryError(ValueError): ...
@dataclass(frozen=True)
class CloudVersion:
    version_id: str; ordinal: int; created_marker: int; size_bytes: int
    is_pinned: bool = False; parent_version_id: Optional[str] = None
    remote_revision_id: Optional[str] = None
@dataclass(frozen=True)
class VersionHistory:
    versions: Tuple[CloudVersion, ...]                         # <= MAX_CLOUD_VERSIONS
    def append(self, v: CloudVersion) -> "VersionHistory": ...  # new ordered history; > cap -> VersionHistoryError

# data/cloud/port.py — the ONE cloud storage port (zero Qt; no provider type in signatures)
class CloudError(ValueError): ...
class CloudDataError(ProjectIOError): ...       # untrusted-fetch defence (PIO-1 family)
@dataclass(frozen=True)
class RemoteItem: id: str; name: str; size_bytes: int
@dataclass(frozen=True)
class Cursor: token: str                        # opaque; unifies Drive/Graph/Dropbox change tracking
@dataclass(frozen=True)
class CloudCapabilities:
    supports_named_revisions: bool; supports_revision_delete: bool
    max_versions_per_call: Optional[int]; change_feed_scope: str
    supports_optimistic_concurrency: bool
class CloudPort(ABC):
    @abstractmethod
    def put(self, project_id: str, blob: bytes, *, parent_version: Optional[str] = None) -> CloudVersion: ...
    @abstractmethod
    def get(self, project_id: str, version_id: str) -> bytes: ...        # validated by caller via PIO-1/CloudDataError
    @abstractmethod
    def list_versions(self, project_id: str) -> Tuple[CloudVersion, ...]: ...  # deterministic order
    @abstractmethod
    def latest(self, project_id: str) -> CloudVersion: ...
    @abstractmethod
    def delete(self, project_id: str) -> None: ...
    @abstractmethod
    def put_recovery(self, project_id: str, blob: bytes) -> None: ...
    @abstractmethod
    def get_recovery(self, project_id: str) -> Optional[bytes]: ...
    @abstractmethod
    def capabilities(self) -> CloudCapabilities: ...
    def is_connected(self) -> bool: ...           # provider-agnostic; ui/ never sees a token

# data/cloud/transport.py — client real-time transport port (zero Qt; Slice C)
class TransportPort(ABC):
    @abstractmethod
    def send_update(self, document_id: str, blob: bytes) -> None: ...     # blob validated (MAX_CRDT_UPDATE_BYTES)
    @abstractmethod
    def send_presence(self, document_id: str, payload: bytes) -> None: ...
    @abstractmethod
    def poll(self, document_id: str) -> Tuple[bytes, ...]: ...            # inbound updates + presence

# logic/cloud_validation.py — pure untrusted-input defence (shared by data/cloud AND sync_backend; zero Qt)
class CloudValidationError(ValueError): ...
def validate_crdt_update(blob: bytes) -> bytes: ...      # size/depth/byte caps (MAX_CRDT_UPDATE_BYTES); no eval/exec
def validate_comment(payload: Mapping) -> Mapping: ...   # MAX_COMMENT_BYTES; no eval/exec
def validate_membership(payload: Mapping) -> Mapping: ... # MAX_SHARED_MEMBERS; no eval/exec
def validate_presence(payload: Mapping) -> Mapping: ...

# logic/convergence.py — HYBRID convergence (pycrdt structure + tile/region-LWW raster; zero Qt; Slice B)
class ConvergenceError(ValueError): ...
def converge(base: "Document", ops: Sequence["Operation"], *, site_id: int) -> "Document":
    """Apply concurrent ops (any order) -> byte-identical converged Document. Tree-CRDT for structured
    metadata; per-tile/region LWW (CRDT_TILE_SIZE_PX) for raster; logical-clock + site-id tiebreak.
    Deterministic, 8K-scalable, no per-pixel overhead. REQ-P10-LOGIC-006."""

# logic/realtime_apply.py — real-time apply + git-like branching (zero Qt; Slice C; AGT-10 per-frame flag)
class RealtimeError(ValueError): ...
def apply_remote(document: "Document", update: bytes, *, site_id: int) -> "Document":
    """Validate (cloud_validation) then converge (convergence). Per-frame budget applies (AGT-10). REQ-P10-LOGIC-007."""
def branch(document: "Document") -> "Branch": ...                        # fork
def merge(mainline: "Branch", branch: "Branch") -> "Document":           # conflict-free CRDT merge
    """clone -> concurrent edit -> merge, no manual conflict resolution; history reconstructable. REQ-P10-LOGIC-007."""

# sync_backend/server.py — asyncio WebSocket relay (OUTSIDE the 3 layers; no ui/data/Qt)
class SyncServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None: ...   # port 0 => ephemeral (CI)
    async def start(self) -> "Address": ...      # spin-up for in-process/subprocess CI
    async def stop(self) -> None: ...
    # relays validate_crdt_update / validate_presence blobs; persists per-doc update log (store.py);
    # never receives or stores provider tokens (REQ-P10-BACKEND-002).
```

## 6. `data/`/backend contract notes

- **Cloud fetch is untrusted (REQ-P10-DATA-006).** `.pixproj` bytes fetched via `get`/`get_recovery` are
  validated through the shipped PIO-1 defensive path (type/bounds; ≤ `MAX_CLOUD_PROJECT_BYTES`;
  unknown/malformed/oversized → `ProjectIOError`/`CloudDataError`); **never `eval`/`exec`**.
- **Provider isolation (REQ-P10-DATA-007).** Provider SDKs live only in `cloud/providers/*`; the port's
  signatures and `logic/`/`ui/` see only normalized types + `CloudError`. Enforced by `check_layering`.
- **Tokens (REQ-P10-DATA-008, CL-B3).** Acquired/stored/used only in `data/cloud/{auth,token_store}` via
  the OS keyring; never above the port, never in `.pixproj`/logs, **never on the backend** (backend cannot
  import `data/` — §4.4).
- **Backend untrusted input (REQ-P10-BACKEND-002).** `sync_backend/server.py` validates every ingested
  payload via the pure `logic/cloud_validation` caps (`MAX_CRDT_UPDATE_BYTES`, `MAX_COMMENT_BYTES`,
  `MAX_SHARED_MEMBERS`); malformed/oversized → rejected; no eval/exec, no crash, no memory exhaustion.
- **CRDT-state sidecar (BF-4).** Structured-CRDT + tile-LWW state persists in a per-project **sidecar**,
  not inside `.pixproj` (no schema bump — REQ-P10-DATA-002 holds). Presence is ephemeral, never persisted.

## 7. Performance / render budget — the Article VI split; DEP-3 routing (ADR-0027 §7)

- **Slice A + B are batch/off the per-frame loop** (REQ-P10-LOGIC-004/-006): cloud save/load/version-fetch/
  autosave and hybrid convergence run off the GUI thread (`ui/cloud_worker.py`); the 16 ms budget does not
  gate them — the contract is **stays-responsive** (REQ-P10-UI-005), verified behaviourally (no freeze).
- **Slice C RE-ENTERS the 16 ms `FRAME_BUDGET_MS`** — the one place Article VI's per-frame budget returns
  to cloud scope: **real-time remote-patch application** (REQ-P10-LOGIC-007) and the **live-cursor overlay
  draw** (REQ-P10-UI-013) are on the interactive loop. **REQUIRED AGT-10 obligation (FLAG-PERFRAME /
  DEP-3):** AGT-10 must profile (`frame-profile`) remote-patch apply + cursor draw on the 8K canvas against
  16 ms and direct batching/coalescing/dirty-rect strategy; the budget is never relaxed. **CI perf-gate
  recommendation:** AGT-09 wires a `perf_profile` gate over the Slice-C real-time apply/cursor path.
- **Ownership.** AGT-10 owns the render/perf strategy + `perf_profile`; AGT-05 implements; AGT-01 fixes the
  pure-convergence seam. AGT-04/AGT-06 assert stays-responsive (A/B) and per-frame (C).

## 8. Constant placement (Article II / BF-1 / BF-3)

All in `logic/constants.py` (leaf). **New names DISTINCT from every shipped constant** (`TILE_SIZE=64`
exists → `CRDT_TILE_SIZE_PX` is a distinct name; the backend caps reuse these named bounds):

| Constant | Value | Source / Slice |
| --- | --- | --- |
| `AUTOSAVE_INTERVAL_MS` | `120000` | 2-min autosave cadence, editor norm (BF-1; Researcher §3.2) — A |
| `MAX_CLOUD_VERSIONS` | `100` | version-history retention cap (aligns Dropbox 100-rev limit, Researcher §1.2) — A |
| `MAX_CLOUD_PROJECT_BYTES` | `268435456` | 256 MiB cloud `.pixproj` ceiling (8K RGBA resident ≈126 MB + headroom; Article VII cap) — A |
| `CLOUD_RETRY_LIMIT` | `3` | cloud-op retry ceiling (BF-1) — A |
| `MAX_SHARED_MEMBERS` | `32` | shared-project member ceiling (BF-3) — B |
| `MAX_COMMENT_BYTES` | `4096` | per-comment byte cap (Article VII) — B |
| `MAX_COMMENTS_PER_PROJECT` | `1024` | comment-count ceiling (BF-3) — B |
| `MAX_CRDT_UPDATE_BYTES` | `1048576` | 1 MiB per-CRDT-update blob cap (Article VII; client + backend) — B/C |
| `CRDT_TILE_SIZE_PX` | `64` | raster tile/region-LWW partition edge, px (8K-scalable; distinct from `TILE_SIZE`) — B/C |

`SyncState` and the CRDT message vocabulary stay **module-local** enumerated vocabulary (ADR-0001).
Concrete values above are AGT-01 defaults, re-verifiable at implementation time (Researcher: pin CRDT-lib
versions and re-check the raster/binary handling).

## 9. Implementation strategy — slice-by-slice A → B → C (each independently gate-green / CI-green)

Detailed work items in `tasks.md`. Each slice is an independently shippable increment: logic/data first
(AGT-03) + tests (AGT-04) → UI (AGT-05) + perf [Slice C] (AGT-10) + QA (AGT-06) + i18n (AGT-07) → docs
(AGT-08) → AGT-01 final gate → AGT-09 commit.

- **Slice A — cloud port + fake adapter + `.pixproj` round-trip + version history + autosave/recovery:**
  - **10A (logic):** `constants` (A subset) + `sync_state` + `autosave` + `version_history`.
    REQ-P10-LOGIC-001/-002/-003/-004/-005.
  - **10A (data/cloud):** `port` + `fake_adapter` + `auth` + `token_store` + `providers/*` (real,
    out-of-CI). REQ-P10-DATA-001..008.
  - **10A (ui):** cloud save/load + version browser + recovery prompt + provider connect + `cloud_worker`
    (responsive). REQ-P10-UI-001..008.
  - **Ship gate A:** fake-adapter round-trip + version history + recovery green in CI; layering/cycles 0;
    a11y + both themes + i18n green. → **cleared to AGT-03/AGT-04**.
- **Slice B — shared projects + comments + presence + hybrid convergence:**
  - **10B (logic):** `cloud_validation` + `convergence` (pycrdt tree-CRDT + tile-LWW). REQ-P10-LOGIC-006.
  - **10B (data/cloud):** `shared_adapter`. REQ-P10-DATA-009.
  - **10B (ui):** shared-projects + comments + presence panels. REQ-P10-UI-009/-010/-011.
- **Slice C — real-time + branching + the sync backend:**
  - **10C (logic):** `realtime_apply` (+ branching). REQ-P10-LOGIC-007.
  - **10C (data/cloud):** `transport` + `loopback_transport` (CI) + `ws_transport` (out-of-CI).
    REQ-P10-DATA-010.
  - **10C (backend):** `sync_backend/{server,store}` — in-process/subprocess CI over loopback.
    REQ-P10-BACKEND-001/-002.
  - **10C (ui):** branching panel + real-time cursors overlay. REQ-P10-UI-012/-013.
  - **10C (perf):** AGT-10 FLAG-PERFRAME assessment + CI perf-gate. REQ-P10-LOGIC-007 / REQ-P10-UI-013.

Reversibility boundary: cloud/collab/real-time are sync/session state and push **no** `QUndoCommand`;
Phase 10 adds no `ui/commands.py` logic (PL10-D13). Only the shipped HIS-1 drawing edits mutate the doc.

## 10. Constitution compliance (self-check)

- **I:** cloud port + all adapters in ZERO-Qt `data/cloud/`; sync/version/autosave/convergence/apply/
  validation models in ZERO-Qt `logic/`; all cloud/collab UI in `ui/`; **the backend is a separate
  top-level `sync_backend/` OUTSIDE the three layers** (ADR-0027) reached only via the transport port. No
  `logic → data`, no client → backend import; layering-rule updated + verified `0` (§4.4/§11). No
  `ui/commands.py` change.
- **II:** 9 new constants in `constants.py`, names distinct from every shipped constant (BF-1/BF-3);
  `SyncState`/CRDT message vocabulary intrinsic-local (ADR-0001).
- **III:** Black/isort/flake8/mypy-strict for `logic/`+`data/`+`sync_backend/`; typed frozen contracts (§5).
- **IV:** whole Slice-A contract + Slice-B storage CI-testable via the **fake adapter** (no network/creds);
  real-time in the CI gate via the **in-process/subprocess backend + loopback transport**; convergence
  deterministic over an in-memory transport (permuted-order property tests). Only live-provider OAuth is
  out-of-CI (`pytest.mark.cloud_live`). Coverage ≥90/80.
- **V:** REQ-P10-UI-006/-007/-008 (a11y + both themes + i18n) are blocking gates across the Slice-A UI and
  extend to the Slice-B/C UI (REQ-P10-UI-009..013).
- **VI — the split:** Slice A/B off the per-frame loop (batch; stays-responsive REQ-P10-UI-005); **Slice C
  real-time apply (REQ-P10-LOGIC-007) + live-cursor draw (REQ-P10-UI-013) RE-ENTER the 16 ms budget →
  REQUIRED AGT-10 FLAG-PERFRAME + CI perf-gate (§7); budget never relaxed.**
- **VII — CENTRAL:** cloud-fetched `.pixproj` untrusted via PIO-1; membership/comment/presence + CRDT
  blobs + **every backend-ingested payload** validated (schema + size/depth/dimension/byte caps, pure
  `logic/cloud_validation`), **never `eval`/`exec`**; tokens only in client `data/cloud/` + OS keyring,
  never on the backend; bounded numerics (§8); portable paths (`path_portability_check`).
- **VIII:** this plan + `analyze-report.md` are the pre-implement gate; dispatch held until C1 PASS.
- **X:** every REQ traces to an S-id / principle / article / forward-inherited primitive (PIO-1, DOC-1,
  HIS-1) in `traceability.md` (34 REQ); the 2 `REQ-P10-BACKEND-*` follow the `REQ-P<phase>-<LAYER>-<NNN>`
  scheme (LAYER=BACKEND — the new first-class component, Article X §1).
- **XI:** the ONE cloud port is the extension seam (a new provider/transport = a new adapter); the
  collaboration + real-time tiers + the backend layer on without weakening any article.

## 11. Layering / cycle verification

After the §4.4 rule update, at plan time on the shipped tree (baseline 2026-07-04):
- `python scripts/check_layering.py --root pixelart_creator` → exit **0** (clean, 120 modules).
- `python scripts/check_layering.py --root .` → exit **0** (0 governed modules until `sync_backend/` lands
  — the `sync_backend` rule is dormant-ready and gates the package when it arrives).
- `python scripts/check_cycles.py --root pixelart_creator` → exit **0** (no cycles, 121 modules).
- (`check_cycles --root sync_backend` runs once the package lands; the check is generic over `--root`.)

The planned Phase-10 edges (§4.4) are acyclic by construction; AGT-03 re-runs all four invocations as each
slice lands (T-tasks 10A/10B/10C gate). See `analyze-report.md` for the C1 verdict.

## 12. Decisions log

| # | Decision | Branch / choice | Rationale |
| --- | --- | --- | --- |
| PL10-D1 | Ungrounded stack/API choice? | **B (no)** | Stack fixed (S8); provider ports, PKCE/keyring, autosave, CRDT/transport all grounded by the landed Researcher report. No RESEARCH REQUEST. |
| PL10-D2 | Qt in `logic/`/`data/`/`sync_backend/` or magic number outside `constants.py`? | **B (no)** | All UI in `ui/`; 9 numerics → `constants.py` (names distinct); `SyncState`/CRDT message vocab intrinsic-local (ADR-0001). |
| PL10-D3 | `data/cloud/` + backend layering | — | `data/cloud/` = normal `data/` subpackage (already governed); new `sync_backend` rule + client→backend forbidden; both scripts exit 0. |
| PL10-D4 | Cloud port shape (DEP-2) | **One `CloudPort` ABC + normalized types + opaque cursor + capability model** | Drive/Graph/Dropbox share primitives; capability diffs surfaced, never leaked (ADR-0026 §1; Researcher §1). |
| PL10-D5 | Adapters in CI (CL-B2) | **Fake adapter in CI; real providers behind same port, out-of-CI** | Local-first can't hermetically CI-test live OAuth; fake adapter = deterministic contract (ADR-0026 §2; Researcher §6). |
| PL10-D6 | Token storage (CL-B3) | **OS keyring inside `data/cloud/`; only browser-launch in `ui/`** | Researcher default; OS-managed encryption; PKCE crypto pure/testable (ADR-0026 §3; Researcher §2). |
| PL10-D7 | Autosave/recovery (DEP-2/BF-2) | **Atomic temp+fsync+`os.replace` + sidecar journal; pure policy fn; version envelope around bytes** | Crash-safe; elapsed-as-input policy is unit-testable; `.pixproj` unforked (ADR-0026 §4/§5; Researcher §3). |
| PL10-D8 | Sync backend placement (FLAG-BACKEND / CL-B4) | **New top-level `sync_backend/` OUTSIDE the 3 layers; asyncio WebSocket; in-process/subprocess CI** | Separate deployable, yet CI-scannable + localhost-testable; keeps real-time IN the CI gate (ADR-0027 §1/§2). |
| PL10-D9 | Client transport (DEP-2 / CL-B4) | **`TransportPort` with loopback (CI) + WebSocket (out-of-CI) behind the port** | No transport type above the port; loopback = hermetic CI real-time (ADR-0027 §3; Researcher §4.5). |
| PL10-D10 | Convergence (CL-B5 / BF-4) | **HYBRID: pycrdt tree/sequence CRDT (structure) + pure tile/region-LWW (raster); logical-clock+site-id** | Researcher-grounded split; commutative/deterministic; 8K-scalable, no per-pixel overhead (ADR-0028 §1/§2). |
| PL10-D11 | CRDT library (BF-4) | **pycrdt primary (well-maintained, fastest, built-in awareness); Automerge documented fallback** | Dispatch: prefer well-maintained libs; branching via fork-doc + update-merge; Automerge if native diff/attribution needed (ADR-0028 §2/§3). |
| PL10-D12 | Shared validators placement | **Pure `logic/cloud_validation.py`, reused by client `data/cloud/` AND `sync_backend/`** | DRY Article VII caps; lets the backend validate without importing `data/` (ADR-0027 §4; ADR-0028 §1). |
| PL10-D13 | Reversibility | cloud/collab/real-time push no `QUndoCommand`; no `ui/commands.py` change | Sync/session state, not undoable edits (Phase-4/5/8 view-state precedent). |
| PL10-D14 | New runtime deps (Article VII) | **`keyring` + `pycrdt` + `websockets`** — AGT-09/AGT-01 manifest, prefer well-maintained; pin + re-verify | Grounded (Researcher §2/§4/§4.5); OS-managed secrets; pin CRDT-lib versions per Researcher caveat. |
| PL10-D15 | Article VI (DEP-3) | Slice A/B off-loop; **Slice C RE-ENTERS 16 ms → REQUIRED AGT-10 FLAG-PERFRAME + CI perf-gate** | Real-time remote-patch apply + live cursors on the interactive loop; budget never relaxed (ADR-0027 §7). |
