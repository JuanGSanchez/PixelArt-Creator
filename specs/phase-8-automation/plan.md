# Plan — Phase 8: Automation & Extensibility

| Field | Value |
| --- | --- |
| Feature | `phase-8-automation` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 8 before any `logic/scripting.py`, `logic/macro.py`, `logic/plugins.py`, `logic/procgen.py`, `logic/batch_ops.py`, `data/macro_io.py`, `data/automation_cli.py`, or automation UI exists. The `logic/history.py` reversible-command path (`Command`/`FunctionCommand`/`History`/`PixelEdit` — HIS-1), the `Document` tree + stable `layer_id` (DOC-1), `PixelBuffer` (PB-1), `blend.composite_stack` (CO-4), `palette_ops` recolour/swap/cycle (PS-1), `logic/dither` (ordered + Floyd–Steinberg), the defensive `data/project_io.py` load (IO-3), and the Phase-7 Qt-free headless CLI precedent (`data/export_cli.py`, CLI-1) are **shipped** and reused, not re-authored. |
| Over spec | `specs/phase-8-automation/spec.md` (REQ-P8-LOGIC-001..014, REQ-P8-UI-001..014; **0 DATA** — folded under LOGIC-007, DEP-4 ratified §12) + `traceability.md` |
| Stack source | S8 (fixed) — no new technology. Security model + macro format + plugin discovery + procgen set are **grounded** by The Researcher (`docs/research-phase-8-automation-20260704.md`, **landed**) → PL8-D1 Branch B (no RESEARCH REQUEST). |
| ADRs filed | **ADR-0021** (automation **security model** — data-driven command DSL, ZERO `eval`/`exec`; trusted-with-consent default-deny no-auto-run plugins; untrusted OS-isolation deferred); **ADR-0022** (automation architecture — macro/DSL format + versioning + deterministic replay; plugin discovery/manifest/capability; headless CLI placement + grammar; `REQ-P8-DATA-*` fold ratified; procgen set + batch-recolour scope; three-layer placement) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-8 spec — the
**power-user automation & extensibility** milestone that turns the shipped reversible-command /
document / pixel / palette primitives into a **sandboxed scripting engine + headless CLI**, **macro
record/replay to an identical result**, a **marketplace-ready (local) plugin system**, **batch
recolour**, and **procedural generation** — while making Article VII (**no `eval`/`exec` on untrusted
input**) true *by construction*. It maps every REQ to its S11 layer, **freezes the public interface**
of the new `logic/scripting.py`, `logic/macro.py`, `logic/plugins.py`, `logic/procgen.py`,
`logic/batch_ops.py`, `data/macro_io.py`, and `data/automation_cli.py` before implementation so the
DATA/UI slices bind to a stable contract, rules the six **DEP-2** HOW decisions + the security model in
**ADR-0021/0022**, routes the **DEP-3** responsiveness NFR to AGT-10/AGT-05, ratifies the **DEP-4**
`REQ-P8-DATA-*` fold, places the six new numerics in `logic/constants.py` with names **distinct from
every shipped constant** (Article II / BF-1), and commits the layering so `check_layering`/
`check_cycles` stay green (both exit `0` at plan time — §11). It is decomposed into
dependency-ordered work items in `tasks.md`.

No new stack/library/API is introduced (**PL8-D1 → Branch B**: the stack is fixed by S8; the security
model, macro format, `importlib.metadata` discovery, and procgen families are **grounded, not
invented** — `docs/research-phase-8-automation-20260704.md` has landed). The `sdd-analyze` C1 gate is
run over constitution/spec/plan/tasks as the pre-implement gate (Article VIII; see
`analyze-report.md`).

## 2. The security invariant (Article VII — CENTRAL; ADR-0021)

> **No input — trusted or untrusted — is ever passed to `eval`/`exec`/`compile(..., "exec")` or any
> equivalent arbitrary-code primitive on ANY automation code path.**

Satisfied **by construction**, not by a fragile in-process barrier: the automation engine executes
**data** (a validated `{op, params}` list), never a language. The Researcher's finding is decisive —
in-process CPython sandboxing of untrusted code is settled-unsafe (pysandbox "BROKEN BY DESIGN";
RestrictedPython "is not a sandbox"); the safe surface is a **data-driven command DSL** replayed by a
**trusted dispatcher** over the shipped `logic/history` reversible commands. This is the shipped
scripting surface **and** the macro format (one artifact). Plugins are **trusted-with-consent,
default-deny, no-auto-run** and may only register/invoke DSL commands — never `eval`/`exec`, never
`ui/`, never ungranted filesystem/network, never the reversible-command path. Untrusted-marketplace
plugins requiring OS-isolation are **deferred** (Article XI hook). AGT-04/AGT-06 test the invariants
in §10.

## 3. Stack / domain decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language / stack | Python 3.12+; stdlib only for automation (`json`, `argparse`, `importlib.metadata`, `random.Random`); NumPy for procgen buffers (shipped); reuse `logic/dither`, `logic/palette_ops`, `logic/blend` | S8 |
| Scripting surface | **Data-driven command DSL** — a validated `{op, params}` list replayed by a **trusted dispatcher** over registered `history.Command` factories (HIS-1); **no `eval`/`exec`** | REQ-P8-LOGIC-001/-003; ADR-0021; research Topic 1 / Option A |
| Edit path | Every scripted/macro/plugin/batch/procgen edit is a **reversible command** on the document `History` — no back-door mutation | REQ-P8-LOGIC-001/-006; HIS-1; ADR-0021 |
| Macro format | One artifact = the DSL list (`.pixmacro`, JSON); `schema_version` + `min_app_version` + per-op `api_version`; captures resolved params + stable `layer_id`/frame IDs + mandatory `seed`; defensive `eval`-free load (IO-3) | REQ-P8-LOGIC-004/-005/-007; ADR-0022; research Topic 2 |
| Deterministic replay | Pure function of `(initial document, macro, params)`: no wall-clock, no unseeded RNG, no locale, no order-unstable iteration; round-trip identity is the gate | REQ-P8-LOGIC-005; P2; ADR-0022 |
| Plugin discovery | `importlib.metadata.entry_points(group="pixelart_creator.plugins")` (stdlib, 3.12 native); inert (no auto-run) | REQ-P8-LOGIC-008; ADR-0022; research §3.1 |
| Plugin trust | Manifest (identity+version+`api_version`+declared capabilities from a module-local vocabulary) + explicit consent + **deny-by-default** + no auto-run; capability object exposes only the DSL API | REQ-P8-LOGIC-008/-009/-010; ADR-0021/0022; research §3.2/3.3 |
| Procgen set | **OpenSimplex** (patent-safe) + value/gradient noise + cellular automata + dithered gradients (reuse `logic/dither`); seeded, deterministic, written via commands over `PixelBuffer` (PB-1), composited via CO-4 | REQ-P8-LOGIC-012; ADR-0022; research §4.1 |
| Batch recolour | **Composes `palette_ops` (PS-1)** as ONE transactional reversible command across many targets; each output == its single op; per-target failure isolated | REQ-P8-LOGIC-011; ADR-0022; research §4.2 |
| CLI | Qt-free `data/automation_cli.py`; `pyproject` console script `pixelart-run`; loads `.pixproj` via IO-3; drives the **same** `logic/scripting` dispatcher the GUI drives; exit 0/1/2 | REQ-P8-LOGIC-014, REQ-P8-UI-010; ADR-0022 |
| CLI==GUI identity | Single shared pure engine in `logic/`+`data/` (zero Qt); the GUI adds no engine logic; both replay the identical DSL through the identical dispatcher → state-identical document | REQ-P8-LOGIC-002/-014, REQ-P8-UI-010; ADR-0021/0022 |
| Persistence | `data/macro_io.py` defensive `eval`-free (de)serialise of macros + plugin manifests + script inputs (IO-3); `MacroIOError`; portable paths | REQ-P8-LOGIC-007; IO-3; ADR-0022 |
| `REQ-P8-DATA-*` prefix | **Ratify the fold under REQ-P8-LOGIC-007; do NOT allocate a DATA prefix** (DEP-4) | ADR-0022 §4; PREFIX-NOTE; CL-13 |
| Reversibility | Each automation edit → **one grouped `QUndoCommand`** via `ui/commands.py` delegating to the Qt-free reversible ops; recording/plugin-enable/selection are view state (not undoable) | REQ-P8-UI-009; CL-8; ADR-0021 |
| Responsiveness | `ui/automation_worker.py` runs the Qt-free engine on a `QThreadPool` worker with progress/cancel; **not** the 16 ms frame budget (automation is batch work) | REQ-P8-UI-011; DEP-3; §7; ADR-0022 |
| Bounds | 6 named constants in `logic/constants.py`; exceeding → domain error | REQ-P8-LOGIC-013; Article II/VII; §8 |
| Testing | pytest + Hypothesis (logic/data, headless — incl. the 6 [SEC] security tests), pytest-qt both themes (UI) | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-8 logic/data decision places Qt in `logic/` or `data/` (**PL8-D2 → Branch B held**). All
macro controls / script runner / plugin manager / batch + procgen panels / the automation worker live
only in `ui/`; the sole Qt file outside `ui/` remains `ui/commands.py` (grouping each automation edit
into one `QUndoCommand`).

## 4. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`) and acyclic (verified §11). The new Qt-free
logic edges are `scripting → {history, document, macro, procgen, batch_ops}`, `macro → {history,
document}`, `plugins → scripting`, `procgen → {pixel_buffer, blend}`, `batch_ops → {palette_ops,
document, pixel_buffer}` — never the reverse (§4.4).

### 4.1 New / extended `logic/` modules (Slices 8A–8D — pure, zero Qt)

| Module | Change | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | Add `MAX_MACRO_STEPS=4096`, `MAX_SCRIPT_OPS=100000`, `MAX_PLUGINS_LOADED=64`, `MAX_BATCH_RECOLOUR_TARGETS=256` (distinct from `MAX_BATCH_TARGETS`), `MAX_PROCGEN_DIMENSION=7680`, `DEFAULT_PROCGEN_SEED=0` — leaf, no imports. **Names distinct from every shipped constant (BF-1).** | — | LOGIC-013 |
| `scripting.py` | **new** | The **command registry** (op-name → trusted `history.Command` factory + param schema); the **trusted dispatcher** (validate op-name + params, construct + push the command; `MAX_SCRIPT_OPS` bound); the scripting API. **No `eval`/`exec`.** `ScriptError`. Zero Qt. | `history`, `document`, `macro`, `procgen`, `batch_ops`, `constants` | LOGIC-001, 002, 003, 013 |
| `macro.py` | **new** | The macro model: record an ordered `{op, params, seed}` list (`MAX_MACRO_STEPS` bound); replay through the dispatcher's command path (deterministic; one grouped command). Does **not** import `scripting` (no back-edge). `MacroError`. Zero Qt. | `history`, `document`, `constants` | LOGIC-004, 005, 006 |
| `plugins.py` | **new** | Plugin host: `entry_points` discovery (inert); manifest validation (defensive); the module-local **capability vocabulary** enum; the capability object exposing only the DSL API; **deny-by-default** enforcement; `MAX_PLUGINS_LOADED` bound. `PluginError`. Zero Qt. Imports `scripting` one-way. | `scripting`, `constants` | LOGIC-008, 009, 010, 013 |
| `procgen.py` | **new** | Seeded generators — OpenSimplex + value/gradient noise + cellular automata + dithered gradients (reuse `dither`); deterministic `(params, seed)`; write via reversible commands over `PixelBuffer` (PB-1), composite via CO-4; `MAX_PROCGEN_DIMENSION` per-axis clamp; `DEFAULT_PROCGEN_SEED`. `ProcgenError`. Zero Qt. | `pixel_buffer`, `blend`, `dither`, `constants` | LOGIC-012, 013 |
| `batch_ops.py` | **new** | Batch recolour: **compose `palette_ops` (PS-1)** across many targets as one transactional reversible command; each output == single op; per-target failure isolated; `MAX_BATCH_RECOLOUR_TARGETS` bound. Recolour maths NOT re-implemented. `BatchError`. Zero Qt. | `palette_ops`, `document`, `pixel_buffer`, `constants` | LOGIC-011, 013 |

`constants.py` stays a leaf. The DSL op-name vocabulary, the macro `schema_version` string, and the
plugin capability enum are **module-local** enumerated vocabulary / format-intrinsic (ADR-0001 /
BF-2 — the `BlendMode`/`PlaybackMode` precedent). The command registry lives in `scripting.py` so
`plugins → scripting` is the only inbound edge and no `scripting → plugins` cycle appears.

### 4.2 New `data/` modules (Slice 8B/8D — Qt-free I/O; DEP-2/DEP-4)

| Module | Change | Responsibility | Depends on | REQ |
| --- | --- | --- | --- | --- |
| `macro_io.py` | **new** | Defensive, `eval`-free (de)serialise of a `.pixmacro` (the DSL list + versions + seeds) **and** plugin manifests + script inputs via the IO-3 pattern: every field type/bounds-checked, malformed/out-of-bounds/unknown-version → `MacroIOError`, **never `eval`/`exec`**, portable paths (`path_portability_check`). Round-trip-identical. Zero Qt. | `logic/macro`, `logic/plugins`, `constants` | LOGIC-007 (folded — DEP-4 §12) |
| `automation_cli.py` | **new** | Headless CLI driver (Qt-free): `argparse` grammar `pixelart-run --input …pixproj --macro …pixmacro --output …pixproj [--seed N] [--param k=v …]`; load `.pixproj` via **`project_io.load_project`** (IO-3, defensive); replay the macro through the **same** `logic/scripting` dispatcher the GUI uses; exit 0 ok / 1 automation error / 2 bad-args\|`ProjectIOError`\|`MacroIOError`. Placed in `data/` so `check_layering` guards its Qt-freedom (ADR-0022). | `logic/scripting`, `logic/macro`, `logic/document`, `data/project_io`, `data/macro_io`, `constants` | LOGIC-014 |

The `pyproject` `[project.scripts]` entry `pixelart-run =
"pixelart_creator.data.automation_cli:main"` is an **AGT-09** edit (repo/pyproject ownership, Article
IX) — flagged in `tasks.md`, not authored here.

### 4.3 New `ui/` modules (Slice 8E — Qt only)

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `macro_controls.py` | **new** | `Macro_Controls(QWidget)`: start/stop record (view state, no undo); run/replay (one undoable grouped command); save/load/list via `data/macro_io` (malformed → graceful error). `tr()` + `changeEvent`. | `macro`, `data/macro_io`, `ui/commands` | UI-001, 002, 003 |
| `script_runner_panel.py` | **new** | `Script_Runner_Panel(QWidget)`: run a DSL script on the active document via `scripting`; edits appear as undoable commands; failing script → graceful error. | `scripting`, `ui/commands`, `automation_worker` | UI-004 |
| `plugin_manager_panel.py` | **new** | `Plugin_Manager_Panel(QWidget)`: install/enable/disable/list; **display declared permissions BEFORE enable**; enabled plugins run under the capability model; denied/failed → user-facing error. Enable/disable is view state (not undoable). | `plugins`, `data/macro_io` | UI-005, 008 |
| `batch_recolour_panel.py` | **new** | `Batch_Recolour_Panel(QWidget)`: pick a recolour/swap + a set of targets; apply as ONE batch via `batch_ops` on the worker; per-target progress; per-target failure isolated; one undoable action. | `batch_ops`, `automation_worker`, `ui/commands` | UI-006 |
| `procgen_panel.py` | **new** | `Procgen_Panel(QWidget)`: parameters + seed; generate via `procgen` (one undoable command); same seed → same output; reject out-of-range sizes; translatable labels + units. | `procgen`, `ui/commands` | UI-007 |
| `automation_worker.py` | **new** | `Automation_Worker(QRunnable)` on a window-owned `QThreadPool` + signals: run the **Qt-free** engine off the GUI thread; progress/result/error over queued signals; cooperative cancel; **no Qt off-thread** (Phase-5/6/7 warmer precedent). Implements the AGT-10 responsiveness directive (DEP-3). | `scripting`, `macro`, `batch_ops`, `procgen` | UI-011 |
| `commands.py` | extend | One grouped `QUndoCommand` per automation **edit** (script run / macro replay / batch / procgen) delegating to the returned `history.Command`(s); recording/plugin-enable/selection push **no** command. No domain math. | `history` + 8A–8D ops | UI-009 |
| `main_window.py` | extend | Add the Automation menu + dock the panels; hold active document + chosen automation parameters (view state); wire the worker. | `document`, the new automation UI | UI-001, 005, 009 |

### 4.4 Layering proof (PL8-D3 — cycle-free by construction)

New intra-`logic/` edges: `scripting → {history, document, macro, procgen, batch_ops}`,
`macro → {history, document}`, `plugins → scripting`, `procgen → {pixel_buffer, blend, dither}`,
`batch_ops → {palette_ops, document, pixel_buffer}`. None of these imports `ui/` or Qt; **no module
imports `scripting` back except `plugins`** (one-way `plugins → scripting`), and `scripting` never
imports `plugins`; `macro` never imports `scripting`. `data/macro_io` and `data/automation_cli` import
**downward** (`data → logic`) and sideways (`data → data`: `automation_cli → project_io`/`macro_io`),
never `logic → data`. Resulting one-way chain:

```
ui/automation_*  →  data/automation_cli  →  logic/scripting  →  logic/macro   →  logic/history, document
                 →  data/macro_io        →  data/project_io  →  logic/procgen →  logic/pixel_buffer, blend, dither
                                          →  logic/scripting  →  logic/batch_ops → logic/palette_ops, document
                 →  logic/plugins        →  logic/scripting
```

No back-edge (`macro → scripting`, `scripting → plugins`, `logic → data`, or any
`logic`/`data` → `ui`) exists. `check_layering` + `check_cycles` therefore stay `0` (verified §11 on
the shipped tree; the planned edges are acyclic by design and re-verified when 8A–8D land).

## 5. Frozen interface contracts (Slices 8A–8D)

Frozen **before** implementation so 8B/8E bind to a stable surface. Qt-free. All new errors subclass
`ValueError` (Phase-1 convention). Op-name vocabulary + capability enum are module-local (BF-2).

```python
# logic/scripting.py — data-driven command DSL + trusted dispatcher (NO eval/exec)
class ScriptError(ValueError): ...

@dataclass(frozen=True)
class Op:                                    # one DSL step
    name: str                                # must resolve in the registry
    params: Mapping[str, object]             # resolved inputs (validated per schema)
    seed: Optional[int] = None               # required for stochastic ops

# A command factory: validated params -> a reversible history.Command over the document.
CommandFactory = Callable[["Document", Mapping[str, object], Optional[int]], "Command"]

def register_command(name: str, factory: CommandFactory, schema: "ParamSchema") -> None:
    """Register a trusted op. The ONLY way an op becomes executable. REQ-P8-LOGIC-001."""

def dispatch(document: "Document", ops: Sequence[Op]) -> "Command":
    """Validate each op-name against the registry + params against its schema; construct each
    reversible command and push it; return one grouped Command (undoable). No eval/exec; unknown op or
    bad params -> ScriptError; > MAX_SCRIPT_OPS -> ScriptError. REQ-P8-LOGIC-001/-002/-003/-013."""

# logic/macro.py — record / replay (one artifact = the DSL list)
class MacroError(ValueError): ...

@dataclass(frozen=True)
class Macro:
    schema_version: str                      # module-local format-intrinsic (ADR-0001)
    min_app_version: str
    ops: Tuple[Op, ...]                      # <= MAX_MACRO_STEPS

def record(command_stream: Iterable["Command"]) -> Macro:
    """Capture the ordered reversible ops (resolved params + stable ids + seed), not a pixel diff.
    REQ-P8-LOGIC-004."""

def replay(document: "Document", macro: Macro) -> "Command":
    """Deterministic pure replay via scripting.dispatch -> one grouped undoable Command; state-identical
    to the original run; no wall-clock/unseeded-RNG/locale. REQ-P8-LOGIC-005/-006."""

# logic/plugins.py — trusted-with-consent, default-deny, no auto-run
class PluginError(ValueError): ...

class Capability(Enum):                      # module-local vocabulary (BF-2)
    READ_DOCUMENT; WRITE_VIA_COMMAND; REGISTER_COMMAND; REGISTER_PROCGEN

@dataclass(frozen=True)
class PluginManifest:
    name: str; version: str; api_version: str
    capabilities: Tuple[Capability, ...]     # validated; ungranted -> denied

def discover() -> Tuple[PluginManifest, ...]:
    """importlib.metadata entry_points(group='pixelart_creator.plugins'); inert (no load/run).
    REQ-P8-LOGIC-008."""

def enable(manifest: PluginManifest, granted: Set[Capability]) -> "PluginHandle":
    """Load + hand a capability object exposing ONLY the DSL API + granted caps. Malformed/unsupported
    -> PluginError; deny-by-default on ungranted; > MAX_PLUGINS_LOADED -> PluginError. Cannot reach ui/
    /filesystem/network outside grants, cannot bypass the command path. REQ-P8-LOGIC-009/-010."""

# logic/procgen.py — seeded, deterministic, via commands
class ProcgenError(ValueError): ...

def make_procgen_command(document: "Document", *, algorithm: str,
                         params: Mapping[str, object], seed: int = DEFAULT_PROCGEN_SEED) -> "Command":
    """Deterministic (params, seed) -> pixel content written through a reversible command over
    PixelBuffer (PB-1), composited via composite_stack (CO-4) where a stack is involved. Same seed ->
    same output. > MAX_PROCGEN_DIMENSION (per-axis) -> ProcgenError. REQ-P8-LOGIC-012."""

# logic/batch_ops.py — batch recolour composing palette_ops (PS-1)
class BatchError(ValueError): ...

def make_batch_recolour_command(targets: Sequence["RecolourTarget"], mapping: "ColorMapping"
                                ) -> "Command":
    """Apply a recolour/swap composing palette_ops (PS-1) across many targets as ONE transactional
    reversible command; each per-target output == the single equivalent op; per-target failure isolated
    (others uncorrupted); > MAX_BATCH_RECOLOUR_TARGETS -> BatchError. REQ-P8-LOGIC-011."""
```

```python
# data/macro_io.py — defensive eval-free (de)serialise (IO-3); Qt-free; portable paths
class MacroIOError(ProjectIOError): ...      # ProjectIOError family (IO-3)

def save_macro(macro: Macro, path: PathLike) -> None: ...
def load_macro(path: PathLike) -> Macro:
    """Type/bounds-check every field; unknown/unsupported schema_version or malformed -> MacroIOError;
    NEVER eval/exec. Round-trip-identical replay. REQ-P8-LOGIC-007."""
def load_manifest(path: PathLike) -> PluginManifest:
    """Defensive manifest load (same posture). Malformed/unsupported -> MacroIOError/PluginError."""

# data/automation_cli.py — headless, Qt-free; the pyproject console entrypoint target
def main(argv: Optional[Sequence[str]] = None) -> int:
    """pixelart-run --input P.pixproj --macro M.pixmacro --output OUT.pixproj [--seed N] [--param k=v].
    Load via project_io.load_project (IO-3 -> ProjectIOError) + macro_io.load_macro (-> MacroIOError);
    replay via the SAME logic/scripting dispatcher the GUI drives -> state-identical document
    (REQ-P8-UI-010); write OUT via project_io. Exit 0 ok / 1 ScriptError|MacroError|PluginError / 2
    bad-args|ProjectIOError|MacroIOError. REQ-P8-LOGIC-014."""
```

## 6. `data/` contract notes

- **Persistence (REQ-P8-LOGIC-007, IO-3).** `macro_io.py` reuses the `project_io.py` posture: every
  field validated, defensive rejection with `MacroIOError`, **never `eval`/`exec`**, `pathlib`
  portable paths (`path_portability_check`). A saved-then-reloaded macro replays to the identical
  result (round-trip identity gate).
- **CLI input (REQ-P8-LOGIC-014, IO-3).** The `.pixproj` load reuses `project_io.load_project`; the
  loaded `Document` (DOC-1) is the same in-memory document the GUI's open produces — the precondition
  for CLI==GUI state-identity (REQ-P8-UI-010).
- **`REQ-P8-DATA-*` prefix (DEP-4).** Ratified fold under REQ-P8-LOGIC-007; **no DATA prefix
  allocated** (ADR-0022 §4). Test modules `tests/data/test_macro_io.py` +
  `tests/data/test_automation_cli.py`. Not acceptance-changing.
- **`pyproject` entry.** `[project.scripts]` `pixelart-run =
  "pixelart_creator.data.automation_cli:main"` is an **AGT-09** edit (Article IX), tracked as `TG-01`.

## 7. Performance / responsiveness — DEP-3 routing to AGT-10/AGT-05 (ADR-0022 §Perf)

REQ-P8-UI-011 binds a **responsiveness** contract (progress + cancel, no freeze) for a long macro /
large batch recolour / big (up to 8K, 7680×4320) procedural generation. Automation is **batch work,
not the per-frame render loop** — the 16 ms `FRAME_BUDGET_MS` (Article VI, the 8K canvas render
budget) does **not** apply to automation throughput (CL-15). Architecture commitment:

1. **Off-GUI-thread automation.** `ui/automation_worker.py` runs the **Qt-free** `logic/scripting`/
   `macro`/`batch_ops`/`procgen` on a window-owned `QThreadPool`; progress/result/error return over
   **queued GUI-thread signals**; a cooperative cancel flag interrupts between ops/targets. No Qt
   object is constructed off the GUI thread (the Phase-5/6/7 warmer precedent).
2. **The engine is thread-agnostic.** Because the pipeline is pure and Qt-free, "on a worker thread"
   is purely a `ui/` concern; the same functions run identically headless in the CLI.
3. **Ownership.** AGT-10 owns any responsiveness/throughput measurement + directive; AGT-05 implements
   the worker; AGT-01 fixes the Qt-free-engine + worker seam (ADR-0022). The 16 ms canvas budget is
   **never** relaxed and is simply out of scope for automation.

## 8. Constant placement (Article II / BF-1)

All in `logic/constants.py` (leaf). **New names are DISTINCT from every shipped constant** —
`MAX_BATCH_RECOLOUR_TARGETS` is explicitly distinct from the shipped Phase-7 `MAX_BATCH_TARGETS`
(export batch, a different concern):

| Constant | Value | Source |
| --- | --- | --- |
| `MAX_MACRO_STEPS` | `4096` | ordered-step ceiling; parallels shipped `MAX_FRAMES`/`MAX_EXPORT_FRAMES=4096` |
| `MAX_SCRIPT_OPS` | `100000` | per-run op ceiling — runaway script fails safely (Article VII, CL-16) |
| `MAX_PLUGINS_LOADED` | `64` | concurrently loaded plugins; parallels `FAVOURITES_MAX=64` |
| `MAX_BATCH_RECOLOUR_TARGETS` | `256` | batch target bound; **name distinct** from `MAX_BATCH_TARGETS=256` |
| `MAX_PROCGEN_DIMENSION` | `7680` | per-axis output bound aligned to the buildable 8K ceiling (`= MAX_CANVAS_WIDTH`, ADR-0020 atlas-clamp precedent) |
| `DEFAULT_PROCGEN_SEED` | `0` | deterministic default seed; parallels `KMEANS_SEED=0` |

The DSL op-name vocabulary, macro `schema_version` string, and the `Capability` enum stay
**module-local** (ADR-0001 exemption / BF-2 enumerated vocabulary — the `BlendMode`/`PlaybackMode`
precedent). `procgen` clamps `MAX_PROCGEN_DIMENSION` per-axis before allocating a buffer.

## 9. Implementation strategy — dependency-ordered slices

Logic-first vertical slices (detailed work items in `tasks.md`):

- **8A — command-DSL + dispatcher + macro model (logic)**: `constants.py` + `scripting.py`
  (registry/dispatcher, no-`eval`/`exec`, bounds) + `macro.py` (record/replay, deterministic).
  REQ-P8-LOGIC-001, -002, -003, -004, -005, -006, -013. AGT-03 + AGT-04 (incl. SC-L001/L003/L005
  security tests).
- **8B — plugin host + sandbox + persistence (logic/data)**: `plugins.py` (discovery/manifest/
  capability/deny-by-default) + `data/macro_io.py` (defensive `eval`-free serialiser).
  REQ-P8-LOGIC-007, -008, -009, -010. AGT-03 + AGT-04 (incl. SC-L007/L009/L010 security tests).
- **8C — batch recolour + procedural gen (logic)**: `batch_ops.py` (compose PS-1) + `procgen.py`
  (seeded OpenSimplex/noise/CA/dither). REQ-P8-LOGIC-011, -012, -013. AGT-03 + AGT-04.
- **8D — headless automation CLI (data)**: `data/automation_cli.py` (Qt-free; CLI==GUI state-identity)
  + AGT-09 pyproject `pixelart-run` entry. REQ-P8-LOGIC-014. AGT-03 + AGT-04 (+ AGT-09).
- **8E — automation UI**: macro controls, script runner, plugin manager, batch/procgen panels, worker,
  `ui/commands.py` grouping. REQ-P8-UI-001..010, -012..014; parity + responsiveness REQ-P8-UI-010/-011
  (coordinated with AGT-10, DEP-3). AGT-05 + AGT-06 + AGT-07 + AGT-10.

Reversibility boundary: every automation **edit** is one grouped `QUndoCommand`; **recording,
plugin-enable/disable, and selection are view/session state and push no command** (CL-8).

## 10. Constitution compliance (self-check)

- **I:** `scripting.py`/`macro.py`/`plugins.py`/`procgen.py`/`batch_ops.py` + the `constants.py`
  extension are pure (zero Qt); `data/macro_io.py` + `data/automation_cli.py` are Qt-free I/O; all
  automation panels/worker in `ui/`; the CLI lives in `data/` so `check_layering` guards its
  Qt-freedom (ADR-0022); no `logic → data` edge; `plugins → scripting` one-way, `macro`↛`scripting`.
  Automation adds only a grouped `QUndoCommand` to `ui/commands.py`.
- **II:** six new numerics in `constants.py`, names distinct from every shipped constant (BF-1;
  `MAX_BATCH_RECOLOUR_TARGETS` ≠ `MAX_BATCH_TARGETS`); op-name/`schema_version`/`Capability` enum
  intrinsic-local (ADR-0001/BF-2).
- **IV:** reversible-command-only edit, no-`eval`/`exec`, deterministic identical replay, macro
  round-trip, plugin sandbox / permission-deny, batch==single, seeded procgen determinism, CLI==GUI
  state-identity → each maps to a scenario → a headless pytest/Hypothesis test (logic/data) or
  pytest-qt test (UI, both themes). The **6 [SEC]** scenarios drive dedicated AGT-04/AGT-06 tests.
- **V:** REQ-P8-UI-012/-013/-014 are blocking gates on the automation UI (a11y + both themes + full
  translatability).
- **VI:** REQ-P8-UI-011 binds a **responsiveness** contract (progress/cancel, no freeze); the 16 ms
  per-frame canvas budget does **not** apply to automation (batch work, not the render loop).
- **VII — CENTRAL:** **no `eval`/`exec` on any input** (by construction — the DSL executes data, not a
  language; ADR-0021); defensive validated load of macros/plugins/scripts (IO-3, `MacroIOError`);
  plugin deny-by-default + no-auto-run + no layer-boundary bypass; bounded automation (6 constants);
  portable paths (`path_portability_check`). ADR-0021 (security model) grounded by the security-focused
  Researcher.
- **X:** every REQ traces to an S-id / F-finding / forward-inherited primitive (HIS-1, DOC-1, PB-1,
  CO-4, PS-1, IO-3, CLI-1) in `traceability.md`.
- **XI:** deferring untrusted-marketplace OS-isolated plugins, an embedded interpreter, a hosted
  registry, remote execution, and AI-assisted generation (ADR-0021, CL-14) adds capability later
  without weakening any article; the command-DSL / capability surface is the extension seam.

## 11. Layering / cycle verification

`python scripts/check_layering.py` → exit **0** (clean, 40 modules) and
`python scripts/check_cycles.py` → exit **0** (no cycles, 95 modules) on the shipped tree at plan time
(baseline, 2026-07-04). The planned edges (`scripting → {history, document, macro, procgen,
batch_ops}`, `macro → {history, document}`, `plugins → scripting`, `procgen → {pixel_buffer, blend,
dither}`, `batch_ops → {palette_ops, document, pixel_buffer}`, `data/macro_io → {logic/macro,
logic/plugins}`, `data/automation_cli → {logic/scripting, logic/macro, logic/document, data/project_io,
data/macro_io}`) are acyclic by construction (§4.4); both scripts are re-run by AGT-03 when 8A–8D land
and gate the C1 analyze (Article I §4, VIII). See `analyze-report.md` for the C1 verdict.

## 12. Decisions log

| # | Decision | Branch / choice | Rationale |
| --- | --- | --- | --- |
| PL8-D1 | Ungrounded stack/API choice? | **B (no)** | Stack fixed (S8); security model, macro format, `importlib.metadata` discovery, procgen families grounded by landed `docs/research-phase-8-automation-20260704.md`. No RESEARCH REQUEST. |
| PL8-D2 | Qt in `logic/`/`data/` or magic number outside `constants.py`? | **B (no)** | All automation panels/worker in `ui/`; six numerics → `constants.py` (names distinct); op-name/`schema_version`/capability enum intrinsic-local (ADR-0001/BF-2). |
| PL8-D3 | scripting/macro/plugins layering | — | `plugins → scripting` one-way (registry in `scripting`); `macro`↛`scripting` (dispatcher imports macro); neither imports `ui`/Qt; no `logic → data` → acyclic. |
| PL8-D4 | Scripting **security model** (DEP-2a) | **Option A — data-driven command DSL, no `eval`/`exec`** | Researcher-settled: in-process CPython sandbox unsafe; DSL is Article-VII-compliant by construction, doubles as macro format (ADR-0021). |
| PL8-D5 | Plugin trust/isolation (DEP-2b/c) | **Trusted-with-consent, default-deny, no-auto-run; `entry_points` discovery; capability object over the DSL API; untrusted OS-isolation deferred** | Full-Python plugins are a trusted-code model; consent + deny-by-default is the desktop precedent; untrusted-marketplace needs OS-isolation → Article XI (ADR-0021/0022). |
| PL8-D6 | Macro format + versioning + replay (DEP-2d) | **One `.pixmacro` JSON = the DSL list; `schema_version`/`min_app_version`/`api_version`; captures params+stable-ids+seed; defensive IO-3 load; round-trip gate** | Researcher Topic 2 (capture inputs not just ops; version the format); reuses `project_io` posture (ADR-0022). |
| PL8-D7 | CLI entrypoint/grammar + placement (DEP-2e) | **`data/automation_cli.py` + `pyproject` console script `pixelart-run`** | `check_layering` only guards `logic/`/`data/`; a `cli/` package is an unscanned Qt blind spot; `data/` keeps the driver Qt-free-enforced (ADR-0022, the ADR-0020 lesson). |
| PL8-D8 | Procgen set + batch scope (DEP-2f) | **OpenSimplex + value/gradient noise + cellular automata + dithered gradients (reuse `dither`); batch = palette remap composing `palette_ops` as one transaction** | OpenSimplex patent-safe (Researcher §4.1); Article I (compose, don't re-implement) (ADR-0022). |
| PL8-D9 | `REQ-P8-DATA-*` prefix (DEP-4) | **Ratify fold under REQ-P8-LOGIC-007; no DATA prefix** | Contract already fixed + testable under LOGIC-007; `data/tiled_io` precedent; not acceptance-changing (ADR-0022 §4). |
| PL8-D10 | Responsiveness (DEP-3) | route to AGT-10/AGT-05 | Off-GUI-thread worker over the Qt-free engine (Phase-5/6/7 warmer precedent); progress/cancel; NOT the 16 ms budget (automation is batch work); budget never relaxed. |
| PL8-D11 | Reversibility (CL-8) | one grouped `QUndoCommand` per edit; recording/enable/selection not undoable | Every automation edit is a reversible command (HIS-1); view/session state is not (mirrors Phase-4/5/6). |
