# ADR-0022 — Automation architecture: macro format & deterministic replay, plugin discovery/manifest, headless CLI placement, procgen/batch scope, layer placement

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-8-automation` |
| Supersedes | — |
| Superseded by | — |

## Context

ADR-0021 fixes the automation **security model** (data-driven command DSL; trusted-with-consent
plugins; no `eval`/`exec`). This ADR rules the remaining HOW decisions the spec deferred to AGT-01
(DEP-2c/d/e/f, DEP-4, BF-1/BF-2) so the DATA/UI slices bind to a stable, layered contract:

1. the **macro/DSL serialisation format + versioning + deterministic replay** capture (DEP-2d, CL-11);
2. the **plugin discovery + manifest/capability + API-version** shape (DEP-2c);
3. the **CLI entrypoint location + argument grammar** (DEP-2e, CL-12);
4. the **`REQ-P8-DATA-*` prefix** allocation (DEP-4, PREFIX-NOTE, CL-13);
5. the **procedural-generation algorithm set + batch-recolour scope** for P8 (DEP-2f, CL-9/CL-10);
6. the **file placement / three-layer layering** of every new module (Article I / S11, BF-2).

Two load-bearing shipped facts constrain placement:

- `scripts/check_layering.py` applies forbidden-import rules **only** to modules whose top-level dir
  is `logic/` or `data/` (`FORBIDDEN = {"logic": …, "data": …}`); `ui/` is unrestricted and a **new
  top-level sibling package (e.g. `cli/`) matches no rule key and is not scanned** — a Qt blind spot.
  This is the Phase-7 `data/export_cli.py` lesson (ADR-0020) and it applies identically here.
- The Researcher: capturing *inputs, not just operations* (resolved params, mandatory RNG seeds,
  stable IDs, a versioned format) is the requirement for identical replay (Topic 2).

## Decision

### 1. Macro/DSL format + versioning + deterministic replay (REQ-P8-LOGIC-004/-005/-007)

- **Format.** A recorded macro / authored script / CLI job is **one artifact**: a JSON document
  (`.pixmacro`) serialising the validated command-DSL — the same `{op, params}` list the dispatcher
  replays (ADR-0021). Loaded **defensively via the IO-3 pattern** (`data/macro_io.py`, mirroring
  `data/project_io.py`): every field type/bounds-checked, malformed/out-of-bounds/unknown-version →
  `MacroIOError` (a `ProjectIOError`-family error), content **never** passed to `eval`/`exec`,
  portable paths (`path_portability_check`).
- **Versioning.** The document carries `schema_version` (`MACRO_SCHEMA_VERSION`, a module-local
  format-intrinsic string — ADR-0001), a `min_app_version`, and a per-op **`api_version`** so a v1
  macro replayed against a v2 command whose semantics changed fails **loudly** rather than
  mis-replaying (Researcher Topic 2.4/2.5). Unknown/unsupported version → `MacroIOError`.
- **Captures inputs, not just ops.** Each step records its **fully-resolved parameters** (coordinates,
  colour values, sizes), **stable references** (reuse the shipped Phase-5 `layer_id`; frame/tileset
  IDs — never "the active layer" positional refs), and a **mandatory recorded `seed`** for any
  stochastic op (procgen/dither). Replay uses **no** wall-clock, **no** unseeded RNG, **no**
  locale-dependent behaviour, **no** order-unstable iteration (REQ-P8-LOGIC-005).
- **Round-trip identity is the acceptance gate.** Record → serialise → reload → replay into a fresh
  copy of the initial document → assert **state-identical** to the original run (SC-L005-1/SC-L007-1).

### 2. Plugin discovery + manifest + capability model (REQ-P8-LOGIC-008/-009/-010)

- **Discovery:** `importlib.metadata.entry_points(group="pixelart_creator.plugins")` (stdlib, Python
  3.12 native keyword API — no backport needed at the pinned Python; Qt-free). Discovery is inert
  (no auto-load/auto-run — ADR-0021).
- **Manifest:** declared `name`, `version`, `api_version`, and a `capabilities` list drawn from a
  fixed **module-local capability vocabulary** in `logic/plugins.py` (enumerated vocabulary, BF-2 /
  ADR-0001 — the `BlendMode`/`PlaybackMode` precedent): e.g. `READ_DOCUMENT`, `WRITE_VIA_COMMAND`,
  `REGISTER_COMMAND`, `REGISTER_PROCGEN` — explicitly **no** raw `FILESYSTEM`/`NETWORK`/`UI` capability
  is grantable in P8 (deny-by-default, ADR-0021). Manifest validated defensively (IO-3) via
  `data/macro_io.py`; malformed/unsupported → `PluginError`.
- **API surface:** the host hands each enabled plugin a **capability object** exposing only the
  DSL command-registration/dispatch API + its granted resources; ungranted → `PluginError`
  (deny-by-default). `MAX_PLUGINS_LOADED` bounds concurrently loaded plugins.

### 3. Headless CLI — placement + grammar (REQ-P8-LOGIC-014, REQ-P8-UI-010)

- **Placement:** `data/automation_cli.py` (Qt-free; imports only `logic/`+`data/`). It lives in
  `data/` — **not** a new `cli/` package — *specifically so `check_layering` keeps guarding its
  Qt-freedom* (the ADR-0020 blind-spot lesson). CLI = command-line I/O + orchestration, the same
  layer as `project_io`/`export_cli`.
- **Console entrypoint:** `[project.scripts]` → `pixelart-run =
  "pixelart_creator.data.automation_cli:main"` — an **AGT-09** `pyproject` edit (Article IX), flagged
  in `tasks.md`, not authored here.
- **Grammar:** `pixelart-run --input PROJECT.pixproj --macro MACRO.pixmacro --output OUT.pixproj
  [--seed N] [--param KEY=VALUE ...]`. Loads the `.pixproj` via the defensive
  `project_io.load_project` (IO-3), replays the macro through the **same** `logic/scripting`
  dispatcher the GUI drives → the resulting document is **state-identical** to the GUI run
  (REQ-P8-UI-010). **Exit codes:** `0` success; `1` automation failure (`ScriptError`/`MacroError`/
  `PluginError`/bounds); `2` bad arguments or defensive load failure (`ProjectIOError`/`MacroIOError`).

### 4. `REQ-P8-DATA-*` prefix (DEP-4 / PREFIX-NOTE / CL-13) — RATIFY the fold

- **Decision: keep automation persistence folded under REQ-P8-LOGIC-007; do NOT allocate a
  `REQ-P8-DATA-*` prefix.** The serialiser's entire observable contract (defensive, `eval`-free load;
  round-trip-identical replay) is already fixed and testable under REQ-P8-LOGIC-007, and
  `data/macro_io.py` is thin serialisation over a `logic/` model (the `data/tiled_io.py` precedent —
  a wire-format serialiser in `data/` whose behaviour is pinned by its `logic/` model's REQ). Adding a
  parallel DATA prefix would fragment one acceptance across two IDs with no coverage gain. This is a
  prefix/placement ruling, **not acceptance-changing** — the contract is unchanged. Test modules
  remain `tests/data/test_macro_io.py` + `tests/data/test_automation_cli.py` (per traceability).

### 5. Procedural-generation set + batch-recolour scope (DEP-2f / CL-9/CL-10)

- **Procgen set (`logic/procgen.py`, new, pure, seeded):** **OpenSimplex noise** (patent-safe —
  preferred over classic Simplex per Researcher §4.1/flag), **value/gradient (Perlin-style) noise**,
  **cellular automata**, and **dithered gradients** (reuse the shipped Phase-3 `logic/dither`
  ordered-Bayer + Floyd–Steinberg — not re-implemented). Every generator is a **deterministic function
  of `(params, seed)`** with a **mandatory** `seed` (default `DEFAULT_PROCGEN_SEED`), writes pixels
  **through the reversible-command path** over `PixelBuffer` (PB-1), composites via
  `blend.composite_stack` (CO-4) where a layer stack is involved, and is bounded by
  `MAX_PROCGEN_DIMENSION` (per-axis clamp to the 8K ceiling, the ADR-0020 atlas precedent).
- **Batch recolour (`logic/batch_ops.py`, new, pure):** = a **palette-index remap / recolour**
  **composing the shipped `logic/palette_ops` (PS-1** `swap_indices`/`remap_colors`/`cycle_palette` —
  recolour maths NOT re-implemented, Article I) across many targets as **one transactional reversible
  command**; each per-target output is **identical** to the single equivalent op; a per-target failure
  is isolated without corrupting the others; bounded by `MAX_BATCH_RECOLOUR_TARGETS`.
- Both are exposed to the DSL as **built-in registered commands** (ADR-0021), so scripts/macros/CLI
  invoke them declaratively and they are undoable + macro-recordable by construction.

### 6. Layer placement (Article I / S11 / BF-2) — all Qt-free except the `ui/` panels

- **`logic/scripting.py`** (new, pure): DSL command registry + trusted dispatcher + scripting API.
- **`logic/macro.py`** (new, pure): the macro model (record an ordered `{op, params, seed}` list;
  replay through the dispatcher's command path). Consumes `history`; does **not** import `scripting`
  (the dispatcher imports `macro`, not the reverse — no cycle).
- **`logic/plugins.py`** (new, pure): plugin host — discovery, manifest validation, capability object,
  deny-by-default enforcement. Imports `scripting` (to register command factories) + `constants`;
  `scripting` does **not** import `plugins` (one-way).
- **`logic/procgen.py`** (new, pure): the seeded generators (imports `pixel_buffer`, `blend`,
  `constants`).
- **`logic/batch_ops.py`** (new, pure): batch recolour composing `palette_ops` (imports `palette_ops`,
  `document`, `pixel_buffer`, `constants`).
- **`logic/constants.py`** (extend): the 6 new bounds/defaults (§ below).
- **`data/macro_io.py`** (new, Qt-free): defensive `eval`-free (de)serialise of macros + plugin
  manifests + script inputs (IO-3); `MacroIOError`. Imports `logic/macro`, `logic/plugins`,
  `constants` (downward `data → logic`).
- **`data/automation_cli.py`** (new, Qt-free): the headless driver (§3). Imports `logic/scripting`,
  `logic/macro`, `logic/document`, `data/project_io`, `data/macro_io`, `constants`.
- **`ui/`** (new, Qt only): `macro_controls.py`, `script_runner_panel.py`, `plugin_manager_panel.py`,
  `batch_recolour_panel.py`, `procgen_panel.py`, `automation_worker.py` (off-GUI-thread runner for
  responsiveness, DEP-3), plus a `ui/commands.py` extension grouping each automation edit into **one**
  `QUndoCommand`. The **sole Qt file outside `ui/` remains `ui/commands.py`**.

**Layering (acyclic — verified §Grounding, gate `0`).** New one-way edges: `scripting → {history,
document, macro, procgen, batch_ops, constants}`, `macro → {history, document, constants}`, `plugins →
{scripting, constants}`, `procgen → {pixel_buffer, blend, constants}`, `batch_ops → {palette_ops,
document, pixel_buffer, constants}`, `data/macro_io → {logic/macro, logic/plugins, constants}`,
`data/automation_cli → {logic/scripting, logic/macro, logic/document, data/project_io, data/macro_io,
constants}`, and the `ui/` automation modules → `logic/scripting`+`logic/macro`+`logic/plugins`+
`data/*`. No module imports `scripting` back (plugins → scripting is the only inbound edge and
scripting does not import plugins); **no `logic → data`**, **no `logic`/`data` → `ui`/Qt**. Acyclic by
construction.

### New constants (Article II / BF-1 — `logic/constants.py`, names DISTINCT from every shipped constant)

| Constant | Value | Rationale |
| --- | --- | --- |
| `MAX_MACRO_STEPS` | `4096` | ordered-step ceiling; parallels shipped `MAX_FRAMES`/`MAX_EXPORT_FRAMES=4096` |
| `MAX_SCRIPT_OPS` | `100000` | per-run op ceiling — a runaway script fails safely before resource exhaustion (Article VII) |
| `MAX_PLUGINS_LOADED` | `64` | concurrently loaded plugins; parallels the shipped `FAVOURITES_MAX=64` |
| `MAX_BATCH_RECOLOUR_TARGETS` | `256` | batch target bound; **distinct name** from Phase-7 `MAX_BATCH_TARGETS=256` (a different concern) |
| `MAX_PROCGEN_DIMENSION` | `7680` | per-axis output bound, aligned to the buildable 8K ceiling (`= MAX_CANVAS_WIDTH`, the ADR-0020 atlas-clamp precedent) |
| `DEFAULT_PROCGEN_SEED` | `0` | deterministic default seed; parallels the shipped `KMEANS_SEED=0` |

The DSL op-name vocabulary, macro `schema_version` string, and the plugin capability enum stay
**module-local** enumerated vocabulary / format-intrinsic (ADR-0001 / BF-2).

## Alternatives Considered

- **Separate macro-format module + separate script module.** Rejected: script and macro are the same
  `{op, params}` artifact (ADR-0021); one serialiser (`data/macro_io.py`) and one model (`logic/macro`)
  keep one determinism + security story.
- **A new top-level `cli/` package.** Rejected: unscanned by `check_layering` (blind spot); `data/`
  keeps the driver Qt-free-enforced (ADR-0020 lesson, re-applied).
- **Allocating a `REQ-P8-DATA-*` prefix.** Rejected (see §4): fragments one fixed acceptance; the
  `data/tiled_io.py` precedent shows a `data/` serialiser can be pinned by its `logic/` model's REQ.
- **Classic Simplex noise.** Rejected: patent history (Researcher flag); **OpenSimplex** is the
  patent-safe equivalent.
- **Re-implementing recolour in batch_ops.** Rejected: composes the shipped `palette_ops` (PS-1),
  Article I (no re-implementation).
- **Putting the command registry in `plugins.py`.** Rejected: would force `scripting → plugins` and
  `plugins → scripting` (a cycle). The registry lives in `scripting.py`; `plugins` imports it one-way.

## Consequences

**Positive.** One artifact (the DSL list) + one serialiser + one dispatcher → macro record/replay,
scripting, CLI, and plugin ops all share a single determinism + security + undo story. Placement keeps
every engine module Qt-free and under `check_layering`'s guard; the CLI byte/state parity with the GUI
is structural. Versioned macros fail loudly across releases. Procgen/batch scope is decisive and
reuses shipped primitives (`dither`, `palette_ops`, `blend`).

**Atomic-dispatch refinement (S2 fix, 2026-07-04, in-session).** The single-`GroupCommand` contract
above is realised by a **two-phase atomic dispatcher** (`logic/scripting.dispatch`): **Phase 1**
validates the ENTIRE op list up front (op is an `Op`, name resolves against the allow-list registry,
params/seed pass the `ParamSchema`) mutating nothing — an invalid op raises with the document
byte/state-identical to before the call; **Phase 2** applies every op in order as one already-applied
`GroupCommand`, and if any factory rejects the live document state mid-run the already-applied
sub-commands are **undone in reverse order before the error is re-raised**, so a failed multi-op leaves
the `Document` exactly as it started. `macro.replay` routes through this same atomic path, so a failing
op mid-replay leaves the document intact. This closes the AGT-06 `[valid op, unknown op]`
partial-mutation defect (SC-UI-008-1) without weakening the ADR-0021 no-`eval`/`exec` invariant (ops
remain data mapped to allow-listed factories). The off-thread worker relies on the same guarantee: it
BUILDs-and-reverts on the worker thread and marshals the unapplied reversible command back to the GUI
thread, which applies it as one `AutomationCommand` — all mutation of the live document stays on the
GUI thread (no cross-thread leak).

**Negative / risk.** `data/macro_io.py` hosting plugin-manifest validation slightly broadens its remit
(mitigated: it is all defensive `eval`-free JSON validation, the `project_io` posture). The
`ui/automation_worker.py` off-thread runner must construct no Qt off the GUI thread and call only the
Qt-free engine (the Phase-5/6/7 warmer precedent); AGT-10 owns the DEP-3 responsiveness directive,
AGT-05 implements it. The `pyproject` `pixelart-run` entry is AGT-09's edit (out of AGT-01 scope).

## Grounding

- Spec `specs/phase-8-automation/spec.md` §2 (layer scope), §4 (REQ-P8-LOGIC-004..014), §5
  (REQ-P8-UI-010/-011), §7 (NEW vs REUSED; PREFIX-NOTE), §8 (DEP-2c/d/e/f, DEP-3, DEP-4, BF-1/BF-2),
  §9 Article I/II/VI/VII, §10 CL-9/CL-10/CL-11/CL-12/CL-13/CL-16, §11 SC-L004-1..L014-1;
  `traceability.md` DEP-2/DEP-3/DEP-4, Article I/II watch.
- Research `docs/research-phase-8-automation-20260704.md` Topic 2 (capture inputs/seeds/stable-IDs +
  version the format), Topic 3 (entry_points discovery; discovery ≠ isolation; manifest/consent),
  Topic 4 (procgen families incl. OpenSimplex-over-Simplex; batch recolour = palette remap as one
  transaction), Open decisions 4/5/6/7/8/11/12.
- Shipped `scripts/check_layering.py` (`FORBIDDEN` keys = `logic`/`data` only — the `cli/` blind spot),
  `logic/history.py` (HIS-1), `logic/palette_ops.py` (PS-1), `logic/dither.py`, `logic/blend.py`
  (CO-4), `logic/pixel_buffer.py` (PB-1), `logic/document.py` (DOC-1 + `layer_id`), `data/project_io.py`
  (IO-3), `data/export_cli.py` (CLI-1 placement precedent). ADR-0021 (security model this architecture
  realises), ADR-0020 (CLI-in-`data/` placement lesson), ADR-0001 (intrinsic-local vocabulary),
  ADR-0011/0012 (`layer_id`/`PlaybackMode` module-local precedent). Constitution Article I/II/VI/VII/IX/XI.
