# Specification — Phase 8: Automation & Extensibility

| Field | Value |
| --- | --- |
| Feature | `phase-8-automation` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-05 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no scripting engine (`logic/scripting.py`), macro model (`logic/macro.py`), plugin host (`logic/plugins.py`), procedural-generation / batch-recolour automation modules, automation CLI, or automation UI exists yet. The `logic/history.py` reversible-command pattern (`Command` / `FunctionCommand` / `History` / `PixelEdit`), the `Document` tree, `PixelBuffer`, `blend.composite_stack`, the shipped recolour / palette-swap logic (`logic/palette_ops.py`), the defensive `data/project_io.py` load pattern, and the Phase-7 **Qt-free headless CLI** precedent (`data/export_cli.py`) are **already shipped** and are reused, not re-authored. This spec defines the WHAT/WHY Phase 8 realises. |
| REQ-ID range | `REQ-P8-LOGIC-001..014`, `REQ-P8-UI-001..014` (from the ROADMAP reserved `REQ-P8-LOGIC-*` / `REQ-P8-UI-*` prefixes). **No `REQ-P8-DATA-*` prefix was reserved** — automation persistence (macro / plugin / script serialisation) is phrased around its observable **security contract** inside LOGIC REQs and its data-layer prefix allocation is **flagged to the orchestrator / AGT-01** (see PREFIX-NOTE §7 and DEP-4 §8); it is **not acceptance-changing**. |
| Layer scope | `pixelart_creator/logic/` (new `scripting.py` — scripting engine + API surface; `macro.py` — macro record/replay model; `plugins.py` — plugin host + sandbox + permission model; automation ops for **batch recolour** (composing shipped recolour, `palette_ops`) and **procedural generation**; new constants) — **zero Qt, fully headless-drivable, drives the shipped reversible-command path (HIS-1)** + `pixelart_creator/data/` (defensive, `eval`-free serialisation of recorded macros / plugin manifests / script inputs via the `project_io.py` pattern, IO-3 — **prefix flagged**, see PREFIX-NOTE) — **zero Qt** + a **headless automation CLI entrypoint** (Qt-free; imports only `logic/` + `data/`; mirrors the Phase-7 `data/export_cli.py` placement lesson) + `pixelart_creator/ui/` (macro record/run controls, script runner, plugin manager, batch-recolour + procedural-gen panels, progress/error) — **the only Qt surface**, hosting *controls only*, never engine logic. |
| Binds to (upstream, **shipped** — REUSED) | Phase 1 `logic/history.py` (`Command` [`execute`/`undo`], `FunctionCommand`, `PixelEdit`, `History.push/undo/redo` — the **HIS-1** primitive: *the single reversible-command path both the UI and automation drive*), Phase 1 `logic/document.py` `Document` tree (the **DOC-1** primitive: the automation subject), Phase 1 `logic/pixel_buffer.py` (`PixelBuffer.data`/`.region`/`.blit` — the **PB-1** primitive: pixels procedural-gen / batch-recolour write through commands), Phase 4 `logic/blend.composite_stack` (the **CO-4** primitive, reserved for procedural-gen compositing), Phase 3 `logic/palette_ops.py` recolour / palette-swap (the **PS-1** primitive reused by batch recolour), Phase 1/4 `data/project_io.py` (defensive, type/bounds-checked, no-`eval`, `pathlib` load; `ProjectIOError`; `_SUPPORTED_VERSIONS` — the **IO-3** primitive/pattern for automation persistence + CLI input), Phase 7 `data/export_cli.py` (the **CLI-1** precedent: a Qt-free headless entrypoint importing only `logic/`+`data/`) |
| Depends on (external) | The Researcher — `docs/research-phase8-automation.md` (grounds the **sandbox / no-`eval`-`exec` security-model options** — data-driven command DSL vs RestrictedPython vs OS-level isolation vs trusted-with-consent — the plugin isolation mechanism, the macro file-format / versioning landscape, and procedural-generation algorithm families). **SECURITY-FOCUSED, being produced in parallel** (feeds AGT-01) — see DEP-1. This spec fixes the WHAT/acceptance around the **observable security + behaviour contract** (no untrusted input reaches `eval`/`exec`; edits only via reversible commands; deterministic replay; sandbox cannot bypass boundaries) and records automation-parity defaults; the security **mechanism** is AGT-01/ADR. |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

The platform already has the one primitive automation most needs: `logic/history.py` exposes a
**reversible-command pattern** — a `Command` with symmetric `execute()` / `undo()`, the
`FunctionCommand` adapter over arbitrary do/undo callables, `PixelEdit`, and a `History` stack — so
**every** state mutation the UI performs is already a reversible command (HIS-1). The `Document`
tree is the editable subject (DOC-1); `PixelBuffer` holds the pixels (PB-1); `blend.composite_stack`
flattens layers (CO-4); `palette_ops` already performs recolour / palette-swap (PS-1); and
`data/project_io.py` demonstrates the defensive, validated, **`eval`-free** JSON load the platform
mandates (IO-3), while Phase 7's `data/export_cli.py` proves a **Qt-free headless CLI** that imports
only `logic/`+`data/` and produces GUI-identical output (CLI-1). What is missing is the
**automation & extensibility system** that lets power users *drive* those primitives programmatically:
a **sandboxed scripting engine + CLI**, **macro recording** (record a session's edits and **replay
them to an identical result**), a **marketplace-ready plugin system** that loads in an **isolated
sandbox** and **cannot bypass the layer boundaries**, **batch recolour**, and **procedural
generation**.

Phase 8 is the "power-user workflows" milestone. A scripting API + plugin marketplace matches
Aseprite's Lua scripting and extends past Pixelorama / Pro Motion NG — the phase's differentiator.
Its defining acceptances are **security invariants**, and they are **testable**: a recorded macro
**replays to a document state-identical to the original run**; the scripting API can perform an edit
**only via a reversible command** (the same HIS-1 path as the UI — no back-door mutation); **no
untrusted input reaches `eval`/`exec`** (constitution **Article VII**, hard constraint); and a
plugin **cannot import or reach `ui/`, the filesystem, or the network outside its granted
permissions** (isolated sandbox / no layer-boundary bypass). These are only achievable if the entire
scripting / macro / plugin engine is **pure `logic/` (zero Qt)**, drives the shipped
reversible-command path, and is **fully headless-drivable** — so the GUI controls and the headless
CLI drive the *same* engine (Article I). The CLI is a Qt-free headless driver (mirroring the Phase-7
`data/export_cli.py` placement lesson): automation stays **out of** `ui/`; only the record/run
control panels live in `ui/`.

This document specifies WHAT the automation system must do and WHY, technology-neutral at the
requirement level. The HOW — **which scripting security model** (data-driven command DSL vs
RestrictedPython vs OS-level isolation vs trusted-with-consent), the **plugin isolation mechanism**,
the **macro file format / versioning**, the **CLI argument grammar**, and the **procedural-generation
algorithm set** — are all downstream (AGT-01 plan/ADR, grounded by the concurrent security-focused
Researcher report, DEP-1/DEP-2). Every scripting / plugin / macro requirement is phrased around the
**observable security + behaviour contract** (no `eval`/`exec` on untrusted input; edits only via
reversible commands; deterministic replay; sandbox cannot bypass boundaries), **not** a specific
mechanism, so choosing a mechanism does not change any acceptance criterion. This spec records the
clarification defaults chosen under the owner's autonomous-progress directive (§10).

## 2. Scope

**In scope (WHAT):**

- **`logic/scripting.py` (new, Qt-free).** A **scripting engine** exposing a **scripting API** whose
  editing operations are performed **exclusively through the shipped reversible-command path**
  (HIS-1): every edit a script makes is a `Command` (`execute`/`undo`) pushed to the document's
  `History` — a script has **no** path to mutate `Document` / `PixelBuffer` state except via a
  reversible command (REQ-P8-LOGIC-001). The engine is **pure `logic/`, zero Qt, headless-drivable**
  (REQ-P8-LOGIC-002) and **never passes untrusted input to `eval`/`exec`** (Article VII,
  REQ-P8-LOGIC-003). The concrete **security model** (data-driven DSL / RestrictedPython / OS
  isolation / trusted-with-consent) is an AGT-01/ADR decision (DEP-2), grounded by the Researcher.
- **`logic/macro.py` (new, Qt-free).** A **macro model** that **records** an ordered sequence of the
  logical edit operations a user performs (as reversible commands, not raw pixels,
  REQ-P8-LOGIC-004) and **replays** them, deterministically, so a recorded macro **replays to an
  identical result** (state-identical document, REQ-P8-LOGIC-005). A replayed macro pushes reversible
  commands, so the whole replay is itself undoable (REQ-P8-LOGIC-006). A recorded macro **persists**
  through a defensive, `eval`-free serialisation (IO-3) that round-trips to an identical replay
  (REQ-P8-LOGIC-007).
- **`logic/plugins.py` (new, Qt-free).** A **plugin host** defining a **marketplace-ready extension
  contract** (versioned, discoverable, declared capabilities, REQ-P8-LOGIC-008) whose plugins operate
  on `logic/` domain objects **only through the reversible-command path**; plugins **load in an
  isolated sandbox** and **cannot bypass the layer boundaries** — no import of / reach into `ui/`, no
  filesystem or network access outside **granted permissions** (REQ-P8-LOGIC-009), and an ungranted
  capability is **denied** (no silent bypass, REQ-P8-LOGIC-010). The isolation **mechanism** is an
  AGT-01/ADR decision (DEP-2).
- **Automation operations.** **Batch recolour** — apply a recolour / palette-swap (composing the
  shipped `palette_ops`, PS-1) across many targets deterministically and reversibly, each output
  identical to the single equivalent op (REQ-P8-LOGIC-011); **procedural generation** — generate
  pixel content deterministically from a **seed** (same seed → same output), writing into the
  document via reversible commands over `PixelBuffer` (PB-1) (REQ-P8-LOGIC-012).
- **`logic/constants.py` (extend).** New named bounds/defaults: `MAX_MACRO_STEPS`,
  `MAX_SCRIPT_OPS`, `MAX_PLUGINS_LOADED`, `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`,
  `DEFAULT_PROCGEN_SEED` (Article II). Exceeding a bound raises a domain error.
- **Headless automation CLI (Qt-free entrypoint).** A CLI entrypoint importing only `logic/`+`data/`
  (no Qt, mirroring `data/export_cli.py`, CLI-1) that loads a fixed `.pixproj` (via IO-3) and **runs
  a script / macro** against it **headless**, producing a result **identical** to the GUI running the
  same automation on the same document (REQ-P8-LOGIC-014, REQ-P8-UI-010).
- **`data/` I/O (prefix flagged — PREFIX-NOTE).** Defensive, validated, **`eval`-free** serialisation
  of recorded macros / plugin manifests / script inputs through the `project_io.py` pattern (IO-3):
  every field type/bounds-checked, malformed input raises `ProjectIOError`, **never `eval`/`exec`**,
  portable paths.
- **`ui/` automation controls.** Macro **record** (start/stop) + **run** controls; a **script
  runner**; a **plugin manager** (install / enable / disable / list, **showing a plugin's declared
  permissions before it is enabled**); **batch-recolour** and **procedural-generation** panels
  (parameters + seed); progress / error feedback. The UI hosts **controls only** and invokes the
  **same** `logic/`+`data/` engine as the CLI (REQ-P8-UI-010); **no** scripting / macro / plugin
  engine logic lives in `ui/` (Article I, the export-lesson mirror).

**Out of scope (this phase):** see §6 Non-goals. Notably: **choosing the scripting security model**
(data-driven command DSL vs RestrictedPython vs OS-level isolation vs trusted-with-consent) → AGT-01
plan/ADR (Researcher, DEP-1/DEP-2); the **plugin isolation mechanism** → AGT-01/ADR (DEP-2); the
**macro file format / versioning** → AGT-01 plan (DEP-2); the **CLI argument grammar** → AGT-01
(DEP-2); the **procedural-generation algorithm set** (noise / cellular / L-system / dungeon families)
→ AGT-01 (DEP-2); whether long-running automation runs on a **worker thread** (UI responsiveness HOW)
→ AGT-01/AGT-10 (DEP-3); the concrete **plugin marketplace/registry service** (a network/back-end
concern) → later phase (CL-14). Also out: a **plugin export/format API** beyond the extension
contract (Phase-7 non-goal handoff); **network/remote script execution**; **AI-assisted generation**
→ later phase. No plan/tasks/code (AGT-01/03/05); no new technology (S8).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap phase.
Feature-label taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Power user / script-edit).** As a power user, I want to **run a script that edits my
  document** so I can automate repetitive work — and I want each scripted edit to be **undoable
  exactly like a manual edit**. → REQ-P8-LOGIC-001, -002, REQ-P8-UI-004, -009 · `scripting-engine` · P8
- **US-2 (Any user / safe-automation).** As a user, I want the scripting/plugin system to **never run
  arbitrary code from untrusted input** (`eval`/`exec`) so opening a shared macro or installing a
  plugin cannot compromise my machine. → REQ-P8-LOGIC-003 · `no-eval-exec` · P8
- **US-3 (Artist / record-macro).** As an artist, I want to **record a sequence of edits as a macro**
  so I can capture a workflow once. → REQ-P8-LOGIC-004, REQ-P8-UI-001 · `macro-record` · P8
- **US-4 (Artist / replay-macro).** As an artist, I want a **recorded macro to replay to an identical
  result** so my automated workflow is reliable and reproducible. → REQ-P8-LOGIC-005, -006,
  REQ-P8-UI-002 · `deterministic-replay` · P8
- **US-5 (Any user / save-macro).** As a user, I want to **save and reload my macros** and have a
  reloaded macro replay identically, with a malformed macro file rejected safely rather than executed.
  → REQ-P8-LOGIC-007, REQ-P8-UI-003 · `automation-persistence` · P8
- **US-6 (Developer / write-plugin).** As a plugin developer, I want a **marketplace-ready extension
  contract** (versioned, declared capabilities) so my plugin can be discovered and installed. →
  REQ-P8-LOGIC-008, REQ-P8-UI-005 · `plugin-system` · P8
- **US-7 (Any user / plugin-sandbox).** As a user installing a third-party plugin, I want it to **load
  in an isolated sandbox** that **cannot reach `ui/`, my filesystem, or the network outside what I
  granted** so a malicious plugin cannot bypass the layer boundaries or exfiltrate data. →
  REQ-P8-LOGIC-009, -010, REQ-P8-UI-005 · `plugin-sandbox` · P8
- **US-8 (Studio / batch-recolour).** As a studio user, I want to **recolour many targets in one
  batch** deterministically, each result matching the single equivalent recolour, undoable. →
  REQ-P8-LOGIC-011, REQ-P8-UI-006 · `batch-recolour` · P8
- **US-9 (Game dev / procedural-gen).** As a game developer, I want **procedural generation** that
  produces the **same output for the same seed** and writes into my document reversibly. →
  REQ-P8-LOGIC-012, REQ-P8-UI-007 · `procedural-generation` · P8
- **US-10 (Studio / cli-automation).** As an automation user, I want a **headless CLI** that runs a
  script/macro on a `.pixproj` so my build script automates edits without a display, producing the
  **same result as the GUI**. → REQ-P8-LOGIC-014, REQ-P8-UI-010 · `cli-automation` · P8
- **US-11 (Any user / reversible-automation).** As a user, I want **every automation action** (script
  run, macro replay, batch recolour, procedural gen) to be **undoable**, so automation is as safe to
  experiment with as manual editing. → REQ-P8-LOGIC-006, REQ-P8-UI-009 · `reversible-command-path` · P8
- **US-12 (Any user / bounded).** As a user, I want automation to be **bounded** (max macro steps,
  script ops, loaded plugins, batch targets, procedural size) so a runaway script/plugin fails safely
  rather than exhausting resources. → REQ-P8-LOGIC-013 · `bounded-automation` · P8
- **US-13 (Any user / graceful-errors).** As a user, I want a **failing or permission-denied**
  script / plugin / macro to surface a **clear error** and leave my document uncorrupted, not crash.
  → REQ-P8-UI-008 · `graceful-errors` · P8
- **US-14 (Any user / responsive).** As a user running a long macro / big batch / large procedural
  gen, I want the **UI to stay responsive** with progress and cancel rather than freezing. →
  REQ-P8-UI-011 · `automation-responsive` · P8
- **US-15 (Any user / a11y-theme-i18n).** As a keyboard user / dark-mode user / non-English user, I
  want the automation panels **keyboard-reachable, correct in both themes, fully translatable**. →
  REQ-P8-UI-012, -013, -014 · `a11y`, `theming`, `i18n` · P8

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase |
| --- | --- | --- |
| `scripting-engine` | Pure-`logic/` sandboxed scripting engine + API driving reversible commands. | 8 |
| `no-eval-exec` | No untrusted input ever reaches `eval`/`exec` (Article VII hard constraint). | 8 |
| `macro-record` | Record an ordered sequence of reversible edit operations as a macro. | 8 |
| `deterministic-replay` | A recorded macro replays to a document state-identical to the original run. | 8 |
| `reversible-command-path` | All automation edits go through the shipped HIS-1 command path; undoable. | 8 |
| `automation-persistence` | Defensive, `eval`-free serialisation of macros/plugins/scripts (IO-3); round-trips. | 8 |
| `plugin-system` | Marketplace-ready, versioned, declared-capability plugin extension contract. | 8 |
| `plugin-sandbox` | Plugins load isolated; cannot reach `ui/`, filesystem, or network outside grants. | 8 |
| `batch-recolour` | Deterministic, reversible recolour across many targets (composes PS-1). | 8 |
| `procedural-generation` | Seeded, deterministic content generation written via reversible commands. | 8 |
| `cli-automation` | Headless, Qt-free CLI running a script/macro on a `.pixproj`; GUI-identical result. | 8 |
| `bounded-automation` | Named bounds on macro steps / script ops / plugins / batch / procgen size. | 8 |
| `graceful-errors` | A failing/denied automation surfaces an error; document uncorrupted. | 8 |
| `automation-responsive` | The GUI stays responsive (progress/cancel) during long-running automation. | 8 |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 8 |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id`, a research `F`-finding, or a Phase-8 capability +
forward-inherited primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a fixed shipped callable is named as a **constraint**, not a HOW decision. **[SEC]** marks
a first-class **security invariant** (drives AGT-04 / AGT-06 security tests).

### `logic/scripting.py` — sandboxed scripting engine + API (new)

#### REQ-P8-LOGIC-001 — The scripting API edits only through the reversible-command path (HIS-1) **[SEC]**
`traces:` **HIS-1** (`logic/history.py` `Command`/`FunctionCommand`/`History`, forward-inherited), **DOC-1**, S7, C1
Every editing operation the scripting API exposes performs its mutation **as a `Command`
(`execute`/`undo`) pushed onto the document's `History`** — the **same** reversible-command path the
UI drives (HIS-1). The scripting API provides **no** means to mutate `Document` / `PixelBuffer` /
layer / frame / tileset state **except** via a reversible command; there is no back-door direct
write. Consequently every scripted edit is **undoable** and redoable exactly like a manual edit. The
scripting engine does **not** re-implement the command pattern (Article I) — it composes HIS-1.

#### REQ-P8-LOGIC-002 — The scripting/automation engine is pure `logic/`, Qt-free, headless-drivable
`traces:` Article I, S11, Phase-8 capability
The **entire** scripting / macro / plugin / batch / procedural engine lives in `logic/` (with `data/`
for serialisation) with **zero Qt imports** and is **drivable without any GUI or event loop**.
Because the GUI controls and the headless CLI both call this same pure engine, their results are
identical (REQ-P8-LOGIC-014, REQ-P8-UI-010). Enforced by `check_layering` / `check_cycles`; the only
Qt file outside `ui/` remains `ui/commands.py`. This purity — automation living **outside** `ui/` —
mirrors the Phase-7 `data/export_cli.py` placement lesson (CLI-1).

#### REQ-P8-LOGIC-003 — No `eval`/`exec` on untrusted input (Article VII — HARD CONSTRAINT) **[SEC]**
`traces:` **Article VII §1** (no `eval`/`exec`; defensive parsing), **IO-3**, S7
Per **constitution Article VII**, **untrusted input** — third-party / marketplace plugin content,
shared or loaded macro files, script payloads from an untrusted source — is **never passed to
`eval`/`exec`** (nor any equivalent arbitrary-code execution primitive). Loading and parsing any such
input is **defensive** (reuse the IO-3 pattern: validate every field, reject malformed / out-of-bounds
/ oversized / unknown-version input with a domain error, never silent acceptance). Where a chosen
security model executes *trusted* content (e.g. a **trusted-with-consent** model), the **trust
boundary** — what qualifies as trusted, and any explicit user consent gate — is defined by the
security model (AGT-01/ADR, DEP-2, Researcher-grounded); the invariant fixed here holds regardless of
model: **no untrusted input reaches `eval`/`exec`**. This is the phase's paramount security acceptance.

### `logic/macro.py` — record / replay (new)

#### REQ-P8-LOGIC-004 — Macro recording captures an ordered sequence of reversible operations
`traces:` **HIS-1**, Phase-8 capability (macro recording), S7
Macro **recording** captures the ordered sequence of **logical edit operations** the user performs —
each as the reversible command it already is (HIS-1) — **not** a flattened pixel diff. The recorded
macro is a replayable list of operations parameterised by their inputs, so it can be re-applied to a
document. Recording is **non-destructive** (observing the command stream, not altering it). Recorded
step count is bounded by `MAX_MACRO_STEPS` (REQ-P8-LOGIC-013).

#### REQ-P8-LOGIC-005 — A recorded macro replays to an identical result (deterministic replay) **[SEC]**
`traces:` P2 (determinism), Phase-8 capability (macro replay), S6, S7
Replaying a recorded macro on a **given initial document** is a **pure, deterministic function** of
`(initial document, macro, parameters)`: it uses **no wall-clock time, no randomness (except an
explicit recorded/seeded value), no locale-dependent behaviour, and no unordered iteration** whose
order can vary. Replaying the same macro on the same initial document **twice** yields a document
that is **state-identical** each time and **equal to the original recorded run's result** — a
recorded macro **replays to an identical result** (the ROADMAP Phase-8 "Done means"). Where a macro
step is inherently stochastic (procedural gen), the macro records its **seed** so replay is still
deterministic (REQ-P8-LOGIC-012).

#### REQ-P8-LOGIC-006 — Macro replay composes with undo (reversible replay)
`traces:` **HIS-1**, S7, C1
A replayed macro applies its operations **through the reversible-command path** (REQ-P8-LOGIC-001), so
the whole replay is **undoable**: `ui/commands.py` can wrap a macro run as a single grouped
`QUndoCommand` (or a bounded sequence) whose undo restores the exact pre-replay document state. No
macro operation escapes the history stack.

#### REQ-P8-LOGIC-007 — Automation persistence is defensive, `eval`-free, and round-trips **[SEC]** *(prefix flagged — PREFIX-NOTE)*
`traces:` **IO-3** (`project_io.py` pattern, forward-inherited), **Article VII §1**, P2
A recorded macro (and a plugin manifest / script input) **persists** to a serialised representation
that is **loaded defensively** through the shipped IO-3 pattern: every field type/bounds-checked, a
malformed / out-of-bounds / unknown-version document raises `ProjectIOError`, content is **never
passed to `eval`/`exec`**, and paths are portable (`path_portability_check`). A saved-then-reloaded
macro **replays to the identical result** it did before saving (round-trip identity,
REQ-P8-LOGIC-005). The **macro file format / versioning** is an AGT-01 plan/ADR decision (DEP-2); the
observable contract (defensive, `eval`-free, round-trip-identical) is fixed here. **NB:** this
data-layer serialisation has **no reserved `REQ-P8-DATA-*` prefix** — see PREFIX-NOTE (§7) / DEP-4;
the acceptance is unchanged wherever AGT-01 places the serialiser.

### `logic/plugins.py` — marketplace-ready plugin host + sandbox (new)

#### REQ-P8-LOGIC-008 — Marketplace-ready plugin extension contract
`traces:` Phase-8 capability (plugin system), Article XI, S6
The plugin host defines a **marketplace-ready extension contract**: a plugin is **discoverable**,
carries a **declared identity + version**, and **declares the capabilities/permissions it requires**
(what it may read/write, whether it needs any host resource). A plugin extends the platform by
operating on `logic/` domain objects **only through the reversible-command path** (REQ-P8-LOGIC-001) —
it registers operations/effects, it does not gain raw mutation access. The engine loads a plugin whose
declared contract validates and **rejects** one whose contract is malformed or whose version is
unsupported (defensive, IO-3). The concrete **manifest/registry format** is AGT-01/ADR (DEP-2).

#### REQ-P8-LOGIC-009 — Plugins load in an isolated sandbox and cannot bypass the layer boundaries **[SEC]**
`traces:` **Article VII**, Article I, Phase-8 capability (plugin sandbox), S11
A plugin **loads in an isolated sandbox**: it **cannot import or reach the `ui/` layer**, **cannot
access the filesystem or network outside its granted permissions**, and **cannot bypass the
reversible-command path** to mutate state directly (REQ-P8-LOGIC-001). A plugin that attempts to
reach `ui/`, touch an ungranted path/resource, or mutate outside a command is **prevented** — the
sandbox denies it (never a silent boundary crossing). This upholds the three-layer boundary
(Article I) that keeps automation **out of** `ui/`. The concrete **isolation mechanism** (import
allow-list, restricted namespace, subprocess/OS isolation, capability object graph) is an AGT-01/ADR
decision (DEP-2), grounded by the security-focused Researcher; the invariant — **no layer-boundary or
permission bypass** — is fixed here.

#### REQ-P8-LOGIC-010 — Plugin permission/capability grants are enforced (deny by default) **[SEC]**
`traces:` **Article VII**, Phase-8 capability, S12
A plugin operates under an **explicit capability grant**: any operation it did not declare and was
not granted (host resource, path, network, edit surface) is **denied by default** with a domain
error — **no silent bypass**, no partial-then-fail corruption. Granting is an explicit decision (the
UI surfaces the declared permissions before enable, REQ-P8-UI-005). The number of concurrently loaded
plugins is bounded by `MAX_PLUGINS_LOADED` (REQ-P8-LOGIC-013). The exact grant vocabulary is
AGT-01/ADR (DEP-2); the deny-by-default contract is fixed here.

### Automation operations — batch recolour, procedural generation (new; compose shipped logic)

#### REQ-P8-LOGIC-011 — Batch recolour is deterministic and reversible; each output equals its single op
`traces:` **PS-1** (`palette_ops` recolour/palette-swap, forward-inherited), P2, Phase-8 capability (batch recolour), S6
**Batch recolour** applies a recolour / palette-swap across **multiple targets** (layers / frames /
documents) by **composing the shipped `palette_ops` recolour (PS-1)** — it does **not** re-implement
recolour maths (Article I). Batch is an **ordered iteration over the same pure per-target op** through
the reversible-command path: each produced result is **identical** to the single, one-at-a-time
recolour of that target with the same parameters, and the whole batch is **undoable**
(REQ-P8-LOGIC-006). Target count is bounded by `MAX_BATCH_RECOLOUR_TARGETS`; a per-target failure is
reported without corrupting the other targets.

#### REQ-P8-LOGIC-012 — Procedural generation is seeded and deterministic; writes via reversible commands
`traces:` **PB-1**, **CO-4**, P2, Phase-8 capability (procedural generation), S6
**Procedural generation** produces pixel content programmatically and is a **deterministic function
of its parameters and an explicit `seed`**: the **same seed + parameters always yields the same
output** (any randomness is drawn from the seed, never wall-clock/global RNG). Generated content is
written into the document **through the reversible-command path** over `PixelBuffer` (PB-1),
compositing via `blend.composite_stack` (CO-4) where a layer stack is involved, so a generation step
is **undoable**. Output dimensions are bounded by `MAX_PROCGEN_DIMENSION`; the default seed is
`DEFAULT_PROCGEN_SEED`. The **algorithm set** (noise / cellular / L-system / dungeon …) is an
AGT-01/ADR decision (DEP-2); the determinism + reversibility contract is fixed here.

### Bounds, CLI (new)

#### REQ-P8-LOGIC-013 — Bounded numerics & defaults (single source)
`traces:` Article II, Article VII, S12
The automation engine enforces named bounds/defaults defined once in `logic/constants.py`:
`MAX_MACRO_STEPS`, `MAX_SCRIPT_OPS` (per-run op ceiling — a runaway script fails safely),
`MAX_PLUGINS_LOADED`, `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`, `DEFAULT_PROCGEN_SEED`.
Exceeding a bound raises a domain error rather than degrading silently or exhausting resources
(Article VII defensive posture). No numeric literals in `logic/`/`data/`/`ui/` (Article II).

#### REQ-P8-LOGIC-014 — Headless automation CLI: Qt-free entrypoint, CLI==GUI result-identity
`traces:` **IO-3**, **DOC-1**, **CLI-1** (`data/export_cli.py` precedent, forward-inherited), P2, S11
A **headless automation CLI entrypoint** — imports only `logic/`+`data/` (zero Qt), mirroring the
Phase-7 `data/export_cli.py` placement (CLI-1) — loads a fixed `.pixproj` (via the defensive load,
IO-3 / REQ-P8-LOGIC-007) and **runs a script or macro** against it **without a GUI or display**. For a
fixed `.pixproj` + script/macro + parameters, the CLI's resulting document is **state-identical** to
the GUI running the same automation on the same document (both drive the pure engine,
REQ-P8-LOGIC-002). The **CLI entrypoint location and argument grammar** are an AGT-01 plan decision
(DEP-2); the WHAT is a headless, Qt-free driver producing a GUI-identical result.

### `ui/` — macro controls, script runner, plugin manager, automation panels

#### REQ-P8-UI-001 — Macro record controls (start / stop)
`traces:` REQ-P8-LOGIC-004
The UI lets the user **start** and **stop** recording a macro; recording captures the edits performed
in between as the ordered operation sequence (REQ-P8-LOGIC-004). Recording state is view state (no
undo entry, CL-8). Translatable labels.

#### REQ-P8-UI-002 — Macro run / replay control
`traces:` REQ-P8-LOGIC-005, -006
The UI lets the user **run (replay) a macro** on the active document; the replay applies through the
reversible-command path as a single undoable action (REQ-P8-LOGIC-006) and yields the identical result
the macro produces (REQ-P8-LOGIC-005).

#### REQ-P8-UI-003 — Macro management (save / load / list)
`traces:` REQ-P8-LOGIC-007
The UI lets the user **save**, **load**, and **list** recorded macros; loading uses the defensive,
`eval`-free load (REQ-P8-LOGIC-007) and a malformed macro file surfaces a **user-facing error**, not a
crash or arbitrary execution. A reloaded macro replays identically.

#### REQ-P8-UI-004 — Script runner
`traces:` REQ-P8-LOGIC-001, -002, -003
The UI lets the user **run a script** against the active document; scripted edits appear as
**undoable commands** (REQ-P8-LOGIC-001), the engine invoked is the pure `logic/` engine
(REQ-P8-LOGIC-002), and a script from an untrusted source cannot cause arbitrary code execution
(REQ-P8-LOGIC-003). A failing script surfaces a graceful error (REQ-P8-UI-008).

#### REQ-P8-UI-005 — Plugin manager (install / enable / disable / list; permissions shown before enable) **[SEC-facing]**
`traces:` REQ-P8-LOGIC-008, -009, -010
The UI lets the user **install / enable / disable / list** plugins and, **before a plugin is
enabled, displays the permissions/capabilities it declares** (REQ-P8-LOGIC-010) so the grant is an
informed decision. An enabled plugin runs sandboxed (REQ-P8-LOGIC-009); a plugin denied a capability
or failing to load surfaces a user-facing error (REQ-P8-UI-008), never a silent boundary crossing.

#### REQ-P8-UI-006 — Batch-recolour panel
`traces:` REQ-P8-LOGIC-011
The UI lets the user pick a recolour / palette-swap and a set of **targets** and apply it as **one
batch** (REQ-P8-LOGIC-011); progress is shown per target, a per-target failure is reported without
aborting the others, and the batch is a single undoable action.

#### REQ-P8-UI-007 — Procedural-generation panel (parameters + seed)
`traces:` REQ-P8-LOGIC-012
The UI lets the user set procedural-generation **parameters and a seed** and generate content; the
same seed + parameters reproduces the same output (REQ-P8-LOGIC-012), and the generation is undoable.
Out-of-range sizes are rejected (REQ-P8-LOGIC-013). Translatable labels + units.

#### REQ-P8-UI-008 — Automation errors surface gracefully **[SEC-facing]**
`traces:` Article VII, REQ-P8-LOGIC-003, -009, -010, -013
A failing, bounded-exceeding, or **permission-denied** automation — a malformed macro/plugin/script,
a plugin attempting to bypass the sandbox, a runaway script hitting `MAX_SCRIPT_OPS`, an unwritable
path — surfaces a **user-facing error message**, not a crash, and leaves the document **uncorrupted**
(the reversible-command path means a partial run is undoable / rolled back). No arbitrary code runs on
a malformed input.

#### REQ-P8-UI-009 — Every automation action is undoable; view/recording state is not
`traces:` S7, C1, F1, REQ-P8-LOGIC-001, -006
Every automation **edit** surfaced by the UI — script run, macro replay, batch recolour, procedural
generation — is pushed onto the active document's undo stack as **exactly one (grouped) `QUndoCommand`**
delegating to the Qt-free reversible ops in `logic/` (Article I), and undo restores the exact prior
state. **Enabling/disabling a plugin, starting/stopping recording, and script/panel selection are
view/session state and are not undoable** (CL-8).

#### REQ-P8-UI-010 — GUI-run automation equals CLI-run automation (headless parity)
`traces:` REQ-P8-LOGIC-002, -014, P2
The GUI automation controls invoke the **same** `logic/`+`data/` engine as the headless CLI
(REQ-P8-LOGIC-002); running a fixed script/macro on a fixed document via the GUI yields a result
**identical** to the CLI running the same automation on the same input (REQ-P8-LOGIC-014). The GUI
adds **no** scripting / macro / plugin engine logic of its own (Article I, export-lesson mirror).

## 5. Non-functional requirements (constitution-tied acceptance)

#### REQ-P8-UI-011 — UI responsiveness during long-running automation *(NFR, Article VI)*
`traces:` S1, S12, Article VI, DEP-3
Running a **long macro / large batch recolour / big procedural generation** (up to an 8K,
7680 × 4320 target) keeps the **GUI responsive** — it continues to process events (progress updates,
cancel) and does **not** freeze for the duration. Whether the automation runs on a **worker thread**
vs the GUI thread is a HOW decision (AGT-01/AGT-10, DEP-3); this spec fixes only the observable
**stays-responsive + progress + cancel** contract. **NB:** automation is a batch operation, **not**
the per-frame render loop — the 16 ms `FRAME_BUDGET_MS` (Article VI, the 8K canvas render budget)
does **not** apply to automation throughput; the requirement is responsiveness, not a per-frame budget.

#### REQ-P8-UI-012 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive automation control (macro record/run buttons, macro list, script runner, plugin
manager list + install/enable/disable + permission display, batch-recolour target list, procedural
parameter/seed fields, progress/cancel) exposes an accessible name and, where non-obvious, an
accessible description; is reachable and operable by keyboard (logical tab order + shortcuts); and
shows a visible focus indicator. Verified by AGT-06 (`a11y-audit`).

#### REQ-P8-UI-013 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The macro controls, script runner, plugin manager, batch-recolour + procedural-gen panels, and
progress/error surfaces render correctly in both light and dark themes; colours are defined once by
role, never hard-coded per widget. Both themes are test-verified (AGT-06 pytest-qt).

#### REQ-P8-UI-014 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 8 (macro/script/plugin labels + tooltips, permission
descriptions, batch/procedural option labels + units, progress text, dialog titles, error messages)
is wrapped in `tr()` / `translate()`; none is a bare literal. Hand-built widgets re-set text on
`QEvent.LanguageChange`. Verified by `string_audit_check` (AGT-07); an unwrapped string is a blocking
finding.

## 6. Non-goals (explicit; deferred)

- **Choice of scripting security model** (data-driven command DSL vs RestrictedPython vs OS-level
  isolation vs trusted-with-consent) — **AGT-01 plan/ADR**, grounded by the security-focused
  Researcher (DEP-1/DEP-2). This spec fixes only the observable security contract (no `eval`/`exec`
  on untrusted input; edits only via reversible commands; REQ-P8-LOGIC-001/-003).
- **Plugin isolation mechanism** (import allow-list / restricted namespace / subprocess/OS isolation /
  capability graph) — AGT-01/ADR (DEP-2). The WHAT (isolated sandbox, no layer-boundary/permission
  bypass) is fixed (REQ-P8-LOGIC-009/-010).
- **Macro file format / versioning** — AGT-01 plan (DEP-2). The WHAT (defensive `eval`-free load,
  round-trip-identical replay) is fixed (REQ-P8-LOGIC-007).
- **CLI argument grammar / entrypoint location** — AGT-01 plan (DEP-2); the WHAT is a headless,
  Qt-free driver with GUI-identical result (REQ-P8-LOGIC-014).
- **Procedural-generation algorithm set** (noise / cellular / L-system / dungeon families) — AGT-01
  plan (DEP-2); determinism (seeded) + reversibility fixed (REQ-P8-LOGIC-012).
- **Whether automation runs on a worker thread** (UI responsiveness HOW) — AGT-01/AGT-10 (DEP-3); this
  spec fixes only the responsiveness contract (REQ-P8-UI-011).
- **A network plugin marketplace / registry service / auto-update** (the back-end that *hosts* the
  marketplace) — later phase (CL-14). Phase 8 ships a **marketplace-ready** *local* extension contract
  (versioned, declared capabilities), not a hosted store.
- **Re-implementing recolour or the command pattern** — batch recolour composes the shipped
  `palette_ops` (PS-1) and all automation drives the shipped `history` command path (HIS-1); no
  re-implementation (Article I).
- **Network / remote script execution, AI-assisted generation, a plugin export-format API** → later
  phase / other phase handoff. Phase 8 ships scripting + CLI + macro record/replay + sandboxed
  plugins + batch recolour + procedural generation.
- No plan/tasks (AGT-01), no logic/UI/data/test code (AGT-03/05/04/06), no new technology (S8).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED** (`specs/phase-1-core-engine/`, plus Phase 3/4/7
  shipped code): `history` (`Command`/`FunctionCommand`/`PixelEdit`/`History` — HIS-1, *the reversible
  path automation drives*), the `Document` tree (DOC-1 — the automation subject), `PixelBuffer`
  (PB-1), `blend.composite_stack` (CO-4), `palette_ops` recolour/palette-swap (PS-1 — reused by batch
  recolour), the `data/project_io.py` defensive-load pattern (IO-3 — automation persistence + CLI
  input), and the Phase-7 `data/export_cli.py` Qt-free headless CLI precedent (CLI-1). Phase 8
  **composes** these; it must not re-implement the command pattern, recolour, or the JSON-load
  security posture (Article I / VII).
- **NEW vs REUSED (explicit):**
  - **NEW:** `logic/scripting.py` (scripting engine + API), `logic/macro.py` (record/replay),
    `logic/plugins.py` (plugin host + sandbox + permissions), the batch-recolour + procedural-gen
    automation ops, new constants (`MAX_MACRO_STEPS`, `MAX_SCRIPT_OPS`, `MAX_PLUGINS_LOADED`,
    `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`, `DEFAULT_PROCGEN_SEED`), the headless
    Qt-free automation CLI, all automation UI, and the `data/` macro/plugin/script serialisers.
  - **REUSED (not re-authored):** the `history` command pattern (HIS-1), the `Document` tree (DOC-1),
    `PixelBuffer` (PB-1), `blend.composite_stack` (CO-4), `palette_ops` (PS-1), the `project_io.py`
    defensive-load pattern (IO-3), the `data/export_cli.py` CLI precedent (CLI-1).
- Automation edits reuse the shipped `history` do/undo pattern so `ui/commands.py` stays a thin Qt
  wrapper (REQ-P8-UI-009, Article I §2), mirroring the Phase-4/5/6 command precedent; a macro
  run / script run / batch / procgen is a single grouped `QUndoCommand`.
- The GUI holds the active document + chosen automation parameters (view/session state); it calls the
  pure `logic/`+`data/` engine, the **same** engine the CLI drives — the foundation of
  REQ-P8-UI-010 / REQ-P8-LOGIC-014.
- **PREFIX-NOTE (data-layer prefix — flagged, not blocking).** The ROADMAP reserved only
  `REQ-P8-LOGIC-*` and `REQ-P8-UI-*` for Phase 8; **no `REQ-P8-DATA-*`**. Automation genuinely needs
  **data-layer serialisation** (persisting/loading recorded macros, plugin manifests, script inputs).
  Rather than invent a `REQ-P8-DATA-*` prefix, this spec phrases that persistence around its
  **observable security contract** inside `REQ-P8-LOGIC-007` (defensive, `eval`-free load via IO-3,
  round-trip-identical replay). **Proposal to the orchestrator / AGT-01:** allocate a
  `REQ-P8-DATA-*` prefix at plan time **if** AGT-01 decides the serialiser warrants its own
  data-layer REQ(s) (macro/plugin/script format), or keep it folded under REQ-P8-LOGIC-007. Either
  way the acceptance (defensive, `eval`-free, round-trip) is **fixed and unchanged** — this is a
  prefix/placement decision, **not** a functional ambiguity. Tracked as DEP-4 (§8).

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

- **DEP-1 (Researcher, grounding — SECURITY-FOCUSED).** `docs/research-phase8-automation.md` grounds
  the **sandbox / no-`eval`/`exec` security-model options** (data-driven command DSL vs
  RestrictedPython vs OS-level isolation vs trusted-with-consent), the **plugin isolation mechanism**,
  the **macro file-format / versioning** landscape, and **procedural-generation algorithm** families.
  **Being produced in parallel** (per the owner directive) and feeds AGT-01. AGT-01's `sdd-plan` must
  not invent the security model — it consumes the Researcher's findings. The *observable security +
  behaviour contracts* and automation-parity defaults are fixed here regardless (§10).
- **DEP-2 (AGT-01, plan/ADR).** (a) the **scripting security model**; (b) the **plugin isolation
  mechanism**; (c) the **plugin manifest / capability-grant vocabulary + registry format**; (d) the
  **macro file format / versioning**; (e) the **CLI entrypoint location / argument grammar**; (f) the
  **procedural-generation algorithm set**. Each is a HOW decision; the observable contracts (no
  `eval`/`exec` on untrusted input; edits only via reversible commands; deterministic replay; sandbox
  cannot bypass boundaries; CLI==GUI) are fixed here. This is a **security-sensitive** plan — an ADR
  is expected for the security model (a/b) with the Researcher as grounding (Article VII).
- **DEP-3 (AGT-01 / AGT-10, plan).** Whether long-running automation runs on a **worker thread** (to
  satisfy REQ-P8-UI-011) is a HOW decision; the pure engine is thread-agnostic (Qt-free). This spec
  fixes only responsiveness + progress + cancel, **not** a per-frame budget (automation is not the
  render loop).
- **DEP-4 (AGT-01 / orchestrator, prefix allocation).** Per PREFIX-NOTE (§7): decide whether the
  macro/plugin/script **serialiser** gets its own `REQ-P8-DATA-*` REQ(s) at plan time or stays folded
  under REQ-P8-LOGIC-007. **Not acceptance-changing** — the defensive/`eval`-free/round-trip contract
  is fixed regardless.
- **BF-1 (AGT-01, Article II).** New tuning values (`MAX_MACRO_STEPS`, `MAX_SCRIPT_OPS`,
  `MAX_PLUGINS_LOADED`, `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`, `DEFAULT_PROCGEN_SEED`)
  must resolve to named constants in `logic/constants.py`; no literals in `logic/`/`data/`/`ui/`.
- **BF-2 (AGT-01, plan).** Whether the scripting API surface is a curated command registry, a builder
  over `FunctionCommand`, or a data-driven op table is a HOW placement decision — the constraint is
  only that **every** scripted edit is a reversible command on the HIS-1 path (REQ-P8-LOGIC-001) and
  the engine is Qt-free (REQ-P8-LOGIC-002).

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** `logic/scripting.py`, `logic/macro.py`, `logic/plugins.py`, the
  automation ops, and the new constants are pure Python, zero Qt; the macro/plugin/script serialisers
  live in `data/` (zero Qt); the automation UI panels live in `ui/`; the **headless CLI entrypoint
  imports only `logic/`+`data/`** (no Qt, mirroring `data/export_cli.py`). The only Qt file outside
  `ui/` remains `ui/commands.py` (grouping automation edits into one `QUndoCommand`, REQ-P8-UI-009).
  Enforced by `check_layering` / `check_cycles`. This purity — and the **plugin sandbox that cannot
  reach `ui/`** — is what keeps automation **out of** the UI layer (REQ-P8-LOGIC-009, ROADMAP
  dependency).
- **Article II (numerics):** new tuning values go in `logic/constants.py` (BF-1); no literals in
  `ui/`/`logic/`/`data/`.
- **Article IV (testing):** the reversible-command-path invariant, no-`eval`/`exec` invariant,
  deterministic macro replay, macro persistence round-trip, plugin sandbox / permission-deny
  invariants, batch-recolour == single, seeded procedural determinism, and CLI==GUI result-identity
  each get a scenario → one pytest / Hypothesis test (logic/data, headless) or pytest-qt test (UI),
  both themes for UI. The **[SEC]** invariants drive dedicated AGT-04 / AGT-06 security tests.
- **Article V (UX):** REQ-P8-UI-012/-013/-014 make a11y + both themes + full translatability blocking
  gates for the automation UI.
- **Article VI (performance):** REQ-P8-UI-011 binds a **responsiveness** contract for long-running
  automation (progress + cancel, no freeze); the 16 ms per-frame canvas budget does **not** apply to
  automation throughput (automation is not the render loop).
- **Article VII (security) — CENTRAL THIS PHASE:** **no `eval`/`exec` on untrusted input**
  (REQ-P8-LOGIC-003, the hard constraint); defensive validated load of macros/plugins/scripts
  (REQ-P8-LOGIC-007, IO-3); plugin **isolated sandbox** with **no layer-boundary bypass**
  (REQ-P8-LOGIC-009) and **deny-by-default** capability grants (REQ-P8-LOGIC-010); bounded automation
  (REQ-P8-LOGIC-013); portable paths (`path_portability_check`). An ADR for the security model is
  expected (DEP-2), grounded by the security-focused Researcher (DEP-1).
- **Article X (traceability):** every REQ traces to an S-id / F-finding / forward-inherited primitive
  (HIS-1, DOC-1, PB-1, CO-4, PS-1, IO-3, CLI-1); forward matrix in `traceability.md`.
- **Article XI (extensibility):** the marketplace-ready plugin contract is itself the platform's
  extensibility surface; deferring a hosted marketplace/registry, remote execution, and AI-assisted
  generation (CL-14) adds capability later without weakening any article.

---

## 10. Clarifications (resolved via `sdd-clarify`)

Per the owner's autonomous-progress directive, ordinary ambiguities are resolved with sensible
defaults grounded in the ROADMAP "Done means", the shipped code, the constitution (Article VII), and
mainstream automation norms (**Aseprite** Lua scripting / plugin norms). Each is a **category-1
decision** (A2-D2 Branch B). **No open clarification blocks planning.** Genuinely
acceptance-changing security ambiguities are addressed in **SUSPEND / escalate** below.

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | What does the scripting engine do? | A **sandboxed scripting API** + **CLI** whose editing ops drive the **same reversible-command path** as the UI (HIS-1); no back-door mutation. | ROADMAP Phase-8 scope + "same reversible-command path"; HIS-1 shipped. |
| **CL-2** | Which scripting **security model** (DSL / RestrictedPython / OS isolation / trusted-with-consent)? | **DEFERRED to AGT-01/ADR** (DEP-2), grounded by the security Researcher (DEP-1). Spec fixes the observable invariant: **no untrusted input → `eval`/`exec`**; edits only via reversible commands. | Per owner directive — the model is a plan/ADR HOW; acceptance phrased around the security contract, so the choice does not change acceptance. |
| **CL-3** | Scope of "no `eval`/`exec`"? | **Untrusted input is never passed to `eval`/`exec`** (Article VII hard constraint). Any *trusted* execution (e.g. trusted-with-consent) defines its **trust boundary** in the security model (AGT-01/ADR); the untrusted-→-no-exec invariant holds regardless. | Constitution Art. VII §1; ROADMAP "no `eval`/`exec` on untrusted input". |
| **CL-4** | What does macro recording capture? | An **ordered sequence of logical reversible operations** (HIS-1 commands parameterised by input), **not** a pixel diff — so replay reproduces the edits, not a snapshot. | ROADMAP "recorded macro replays to an identical result"; reuses the command stream. |
| **CL-5** | "Identical result" scope for replay? | Replaying a macro on the **same initial document** yields a **state-identical** document, equal to the original run, **deterministically** (no wall-clock/random except a recorded seed). | ROADMAP "Done means" (replays to an identical result); P2 determinism. |
| **CL-6** | Are plugins/scripts/macros linked or trusted by default? | **Deny-by-default**: plugins declare capabilities, run **sandboxed**, cannot reach `ui/` / filesystem / network outside grants; ungranted ops denied. | ROADMAP "isolated sandbox … cannot bypass the layer boundaries"; Art. VII. |
| **CL-7** | Is "marketplace-ready" a hosted store this phase? | **No** — a **local** marketplace-ready extension contract (versioned, declared capabilities, discoverable); a hosted registry/store is deferred (CL-14). | Bounds the phase to the ROADMAP bullet; a network store is a later concern (Art. XI). |
| **CL-8** | Are recording/plugin-enable/selection undoable? | **No** — start/stop recording, enable/disable plugin, script/panel selection are **view/session state**; only automation **edits** are `QUndoCommand`s (REQ-P8-UI-009). | Editor norm; mirrors Phase-4/5/6 selection being non-undoable. |
| **CL-9** | Batch recolour — new or reused? | **Reuse the shipped `palette_ops` recolour/palette-swap (PS-1)**; batch is a deterministic, reversible iteration; each output == its single op. No new recolour maths. | ROADMAP "batch recolour"; Art. I (compose, don't re-implement). |
| **CL-10** | Procedural generation determinism? | **Seeded**: same seed + parameters → same output; randomness drawn from the seed only; written via reversible commands. Algorithm set → AGT-01/ADR (DEP-2). | ROADMAP "procedural generation"; P2; determinism required for macro replay (CL-5). |
| **CL-11** | Macro **file format / versioning**? | **DEFERRED to AGT-01/ADR** (DEP-2). Spec fixes the observable contract: defensive `eval`-free load (IO-3), round-trip-identical replay. | Per owner directive — format is a plan/ADR HOW; acceptance around the contract. |
| **CL-12** | CLI automation scope? | **Headless entrypoint** running a script/macro on a `.pixproj`; result **identical to the GUI**; imports only `logic/`+`data/` (Qt-free), mirroring `data/export_cli.py` (CLI-1). | ROADMAP "CLI"; Phase-7 CLI placement lesson (automation out of `ui/`). |
| **CL-13** | Data-layer prefix for macro/plugin persistence? | **No `REQ-P8-DATA-*` was reserved** — persistence folded under REQ-P8-LOGIC-007 (observable contract), prefix allocation **flagged to the orchestrator / AGT-01** (PREFIX-NOTE §7, DEP-4). **Not acceptance-changing.** | Per prompt directive — flag rather than invent a prefix; the contract is fixed regardless of placement. |
| **CL-14** | Scope of "extensibility" — hosted marketplace, remote exec, AI gen? | **Deferred**: hosted marketplace/registry, remote/network script execution, AI-assisted generation → later phase. Phase 8 ships scripting + CLI + macro record/replay + sandboxed plugins + batch recolour + procedural gen. | Bounds the phase to the ROADMAP Phase-8 bullets + "Done means"; extensible per Art. XI (§6). |
| **CL-15** | Automation performance budget? | **No 16 ms per-frame budget** (automation is not the render loop). NFR is **UI responsiveness** (progress + cancel, no freeze) for long automation; worker-thread choice → AGT-01/AGT-10 (DEP-3). | Art. VI applies to the canvas render loop; automation is batch work. |
| **CL-16** | Bounds on automation? | Named constants: `MAX_MACRO_STEPS`, `MAX_SCRIPT_OPS`, `MAX_PLUGINS_LOADED`, `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`, `DEFAULT_PROCGEN_SEED`; exceeding → domain error. | Art. II single-source; Art. VII defensive (runaway fails safely). |

**SUSPEND / escalate:** *none.* The scope risks — the **scripting security model**, the **plugin
isolation mechanism**, the **macro file format**, the **CLI grammar**, and the **procedural-gen
algorithm set** — are **named HOW decisions** (DEP-1/DEP-2), owned by AGT-01 and grounded by the
concurrent **security-focused** Researcher report; the owner directive explicitly reserves them for
the plan/ADR. Crucially, every scripting / plugin / macro / procedural requirement here is phrased
around the **observable security + behaviour contract** — *no untrusted input reaches `eval`/`exec`*
(REQ-P8-LOGIC-003); *the scripting API cannot perform an edit except via a reversible command*
(REQ-P8-LOGIC-001); *a recorded macro replays to a state-identical result* (REQ-P8-LOGIC-005); *a
plugin cannot import/reach `ui/` or the filesystem/network outside its granted permissions*
(REQ-P8-LOGIC-009/-010) — so choosing a model/mechanism/format **does not change any acceptance
criterion**. The **`REQ-P8-DATA-*` prefix** question (CL-13/PREFIX-NOTE/DEP-4) is a **prefix/placement
decision flagged to the orchestrator**, likewise not acceptance-changing. **No functional or security
ambiguity that changes acceptance criteria remains unresolved.**

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour. Logic/data scenarios are for **AGT-04** (pytest + Hypothesis,
headless); UI scenarios are for **AGT-06** (pytest-qt, `QT_QPA_PLATFORM=offscreen`), **each run under
BOTH light and dark themes** (REQ-P8-UI-013, expressed once as a global rule). The **[SEC]** scenarios
are first-class security tests. Scenario ids map to `traceability.md`; tests are authored later
(`pending`).

> Global rule (UI scenarios): *Given the app runs headless (`QT_QPA_PLATFORM=offscreen`) — the
> scenario is executed and asserted identically under the light theme and the dark theme.*

### Feature: Scripting engine — reversible path, purity, no eval/exec (REQ-P8-LOGIC-001..003)
```gherkin
Scenario: SC-L001-1 a scripted edit goes through the reversible-command path and is undoable [SEC]
  Given a document and the scripting API
  When a script performs an edit
  Then the edit is recorded as a Command on the document's History
  And undoing it restores the exact prior document state
  And the scripting API exposes no way to mutate document/buffer state except via a reversible command

Scenario: SC-L002-1 the automation engine is Qt-free and runs without a GUI/event loop
  Given the logic/ and data/ automation modules
  Then they import no Qt (check_layering passes) and a full script/macro run completes with no GUI or event loop

Scenario: SC-L003-1 no untrusted input is ever passed to eval/exec [SEC]
  Given an untrusted macro/plugin/script payload crafted to invoke arbitrary code
  When it is loaded/parsed by the automation engine
  Then it is validated defensively and rejected on malformation (ProjectIOError), never executed
  And no code path passes untrusted input to eval/exec (Article VII)
```

### Feature: Macro record / replay / persistence (REQ-P8-LOGIC-004..007)
```gherkin
Scenario: SC-L004-1 recording captures an ordered sequence of reversible operations
  Given macro recording is started
  When the user performs a sequence of edits and stops recording
  Then the macro holds those edits as an ordered list of reversible operations (not a pixel diff)
  And recording did not alter the document beyond the edits themselves

Scenario: SC-L005-1 a recorded macro replays to an identical result [SEC]
  Given a recorded macro and a fixed initial document
  When the macro is replayed on that initial document twice
  Then both replays yield a state-identical document equal to the original recorded run
  And the replay uses no wall-clock time, randomness (beyond a recorded seed), or locale-dependent behaviour

Scenario: SC-L006-1 a replayed macro is undoable as one grouped command
  Given a fixed initial document
  When a macro is replayed and then undone
  Then the document is restored exactly to its pre-replay state

Scenario: SC-L007-1 a saved macro reloads defensively and replays identically [SEC]
  Given a recorded macro saved to disk and, separately, a malformed macro file
  When each is loaded via the automation persistence layer
  Then the malformed file raises ProjectIOError (no eval/exec, no silent acceptance)
  And the valid reloaded macro replays to the identical result it produced before saving
```

### Feature: Plugin system — contract, sandbox, permissions (REQ-P8-LOGIC-008..010)
```gherkin
Scenario: SC-L008-1 a plugin loads via a versioned, declared-capability contract
  Given a plugin with a valid versioned manifest declaring its capabilities and, separately, a malformed/unsupported one
  When each is loaded by the plugin host
  Then the valid plugin loads and registers its operations only through the reversible-command path
  And the malformed/unsupported plugin is rejected with a domain error (defensive, no execution)

Scenario: SC-L009-1 a plugin cannot bypass the layer boundaries [SEC]
  Given a loaded plugin
  When it attempts to import/reach the ui/ layer, or to touch the filesystem/network outside its grants, or to mutate state outside a command
  Then each attempt is prevented by the sandbox (no ui/ reach, no ungranted resource, no direct mutation)

Scenario: SC-L010-1 an ungranted plugin capability is denied by default [SEC]
  Given a plugin that was not granted a given capability
  When it attempts that operation
  Then the sandbox denies it with a domain error (no silent bypass, no partial-then-corrupt state)
  And exceeding MAX_PLUGINS_LOADED raises a domain error
```

### Feature: Batch recolour, procedural generation, bounds, CLI (REQ-P8-LOGIC-011..014)
```gherkin
Scenario: SC-L011-1 batch recolour is deterministic, reversible, and equals the single op
  Given a recolour/palette-swap and several targets (within MAX_BATCH_RECOLOUR_TARGETS)
  When the batch is applied and each target is also recoloured singly with the same parameters
  Then every batch result is identical to its single-op counterpart (composing palette_ops, PS-1)
  And the whole batch is undoable, and a per-target failure does not corrupt the other targets

Scenario: SC-L012-1 procedural generation is seeded and deterministic; written via commands
  Given procedural-generation parameters and a fixed seed
  When generation is run twice with the same seed
  Then both runs produce identical pixel content
  And the generated content is written through the reversible-command path (undoable)
  And a target above MAX_PROCGEN_DIMENSION raises a domain error

Scenario: SC-L013-1 automation bounds are enforced from constants
  Given a macro above MAX_MACRO_STEPS, a script above MAX_SCRIPT_OPS, or a batch above MAX_BATCH_RECOLOUR_TARGETS
  Then a domain error is raised (no silent degradation or resource exhaustion)

Scenario: SC-L014-1 the CLI automation of a fixed .pixproj equals the GUI result
  Given a fixed .pixproj and a fixed script/macro + parameters
  When the automation is run via the headless CLI and via the GUI path
  Then the two resulting documents are state-identical (both drive the same pure engine)
```

### Feature: Automation UI — macros, scripts, plugins, panels (REQ-P8-UI-001..010)
```gherkin
Scenario: SC-UI-001-1 the user records a macro with start/stop controls
  Given the macro record controls
  When the user starts recording, performs edits, and stops
  Then the recorded macro holds those edits and recording state is not an undo entry

Scenario: SC-UI-002-1 the user replays a macro as one undoable action
  Given a recorded macro and a document
  When the user runs the macro
  Then the document reflects the macro's edits, the result matches the recording, and one undo reverts the whole replay

Scenario: SC-UI-003-1 macro save/load rejects a malformed file gracefully
  Given the macro management UI
  When the user saves a macro and later loads a valid one, then attempts to load a malformed one
  Then the valid macro reloads and replays identically and the malformed file surfaces a user-facing error (no crash, no execution)

Scenario: SC-UI-004-1 the script runner runs a script whose edits are undoable
  Given the script runner and a document
  When the user runs a script that edits the document
  Then the edits appear as undoable commands and a failing script surfaces a graceful error

Scenario: SC-UI-005-1 the plugin manager shows declared permissions before enabling [SEC-facing]
  Given the plugin manager with an installed plugin
  When the user views the plugin before enabling it
  Then its declared capabilities/permissions are shown, and enabling runs it sandboxed
  And a plugin denied a capability or failing to load surfaces a user-facing error (no silent boundary crossing)

Scenario: SC-UI-006-1 the batch-recolour panel applies one batch across targets
  Given the batch-recolour panel with several targets
  When the user applies a recolour to all of them in one action
  Then per-target progress is shown, a per-target failure does not abort the others, and the batch is one undoable action

Scenario: SC-UI-007-1 the procedural-generation panel reproduces output from a seed
  Given the procedural-generation panel
  When the user generates with a given seed/parameters twice
  Then both runs produce identical content, the generation is undoable, and out-of-range sizes are rejected

Scenario: SC-UI-008-1 a failing/denied automation surfaces an error and leaves the document uncorrupted [SEC-facing]
  Given a malformed macro/plugin/script, a sandbox-bypass attempt, or a runaway script hitting MAX_SCRIPT_OPS
  When the user triggers it
  Then a user-facing error is shown, no arbitrary code runs, and the document is left uncorrupted (partial run rolled back)

Scenario: SC-UI-009-1 every automation edit is one undoable command; view/session state is not
  Given a document
  When the user runs a script, replays a macro, applies a batch recolour, or runs procedural generation
  Then each pushes exactly one grouped QUndoCommand and undo restores the prior state
  And starting/stopping recording, enabling/disabling a plugin, and selection push no undo command

Scenario: SC-UI-010-1 GUI-run automation equals CLI-run automation
  Given a fixed document and a fixed script/macro
  When the automation is run via the GUI and via the CLI
  Then the two resulting documents are identical and the GUI adds no engine logic of its own
```

### Feature: Responsiveness, a11y, theming, i18n (REQ-P8-UI-011..014) — NFR
```gherkin
Scenario: SC-UI-011-1 the UI stays responsive during long-running automation
  Given a long macro / large batch recolour / big (up to 8K) procedural generation
  When the user triggers it
  Then the UI keeps processing events (progress updates, cancel) and does not freeze
  # Worker-thread vs GUI-thread is AGT-01/AGT-10 (DEP-3); the 16 ms canvas frame budget does not apply to automation throughput.

Scenario: SC-UI-012-1 automation controls expose accessible names and keyboard focus
  Given the automation panels (macro controls, script runner, plugin manager, batch/procedural panels)
  When each control is inspected and tabbed through
  Then each has a non-empty accessible name, is keyboard reachable in a logical order, and shows a visible focus indicator

Scenario: SC-UI-013-1 the automation UI renders correctly in both themes
  Given the app
  When rendered under the light theme and the dark theme
  Then the automation panels and progress/error surfaces render legibly with role-based colours

Scenario: SC-UI-014-1 no Phase-8 user-visible string is a bare literal
  Given the Phase-8 ui/ sources
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings (macro/script/plugin labels, permission text, option labels/units, progress, errors)
```

---

## 12. Exit / status

- Forward spec authored for Phase 8 — Automation & Extensibility. **28 REQ-IDs**: **14 LOGIC**
  (`REQ-P8-LOGIC-001..014`) + **14 UI** (`REQ-P8-UI-001..014`) + **0 DATA** (no prefix reserved —
  automation persistence folded under REQ-P8-LOGIC-007 with the prefix flagged to the orchestrator /
  AGT-01, PREFIX-NOTE §7 / DEP-4), each traced to an S-id / F-finding / forward-inherited primitive
  (HIS-1 `history` reversible-command path — the central primitive; DOC-1 `Document` subject; PB-1
  pixels; CO-4 `composite_stack`; PS-1 `palette_ops` recolour; IO-3 `project_io.py` defensive-load;
  CLI-1 `data/export_cli.py` headless-CLI precedent) per Article X.
- **16 clarification defaults** recorded (§10), each grounded in the ROADMAP "Done means", the shipped
  code, the constitution (Article VII), and Aseprite-scripting parity; **no open clarification blocks
  planning**.
- **No SUSPEND blocker.** The scope risks — the **scripting security model**, the **plugin isolation
  mechanism**, the **macro file format**, the **CLI grammar**, and the **procedural-gen algorithm
  set** — are named HOW decisions the owner directive reserves for AGT-01 plan/ADR (DEP-1/DEP-2,
  grounded by the concurrent **security-focused** Researcher); every scripting/plugin/macro/procedural
  REQ is phrased around the **observable security + behaviour contract** (no `eval`/`exec` on
  untrusted input; edits only via reversible commands; deterministic replay; sandbox cannot bypass
  boundaries; CLI==GUI), so those choices do not change any acceptance criterion.
- **`REQ-P8-DATA-*` prefix question:** **FLAGGED, not blocking.** No DATA prefix was reserved;
  automation persistence genuinely needs data-layer serialisation. Phrased around its observable
  security contract inside REQ-P8-LOGIC-007; the prefix allocation is proposed to the orchestrator /
  AGT-01 (PREFIX-NOTE §7 / CL-13 / DEP-4) and is **not acceptance-changing**.
- **NEW vs REUSED (§7):** NEW = `logic/scripting.py`, `logic/macro.py`, `logic/plugins.py`, the
  batch-recolour + procedural-gen ops, new constants, the headless Qt-free automation CLI, all
  automation UI, and the `data/` serialisers. REUSED = the `history` command pattern (HIS-1), the
  `Document` tree (DOC-1), `PixelBuffer` (PB-1), `blend.composite_stack` (CO-4), `palette_ops` (PS-1),
  the `project_io.py` defensive-load pattern (IO-3), the `data/export_cli.py` CLI precedent (CLI-1).
- **New constants flagged for `logic/constants.py`** (Article II, BF-1): `MAX_MACRO_STEPS`,
  `MAX_SCRIPT_OPS`, `MAX_PLUGINS_LOADED`, `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`,
  `DEFAULT_PROCGEN_SEED`.
- **Dependencies flagged:** DEP-1 (Researcher `docs/research-phase8-automation.md` — security-model
  options, plugin isolation, macro format, procgen algorithms; security-focused, concurrent), DEP-2
  (AGT-01 plan/ADR — security model, isolation mechanism, manifest/grant vocabulary, macro format, CLI
  grammar, procgen set; ADR expected for the security model), DEP-3 (AGT-01/AGT-10 — worker-thread
  choice for REQ-P8-UI-011), DEP-4 (AGT-01/orchestrator — `REQ-P8-DATA-*` prefix allocation).
- Acceptance scenarios cover every functional and NFR requirement (28 scenarios, incl. 6 first-class
  **[SEC]** / **[SEC-facing]** security scenarios); forward matrix in `traceability.md` (0 uncovered).
  Tests authored later by AGT-04 (logic/data, incl. security tests) / AGT-06 (UI, both themes),
  `pending`.
- **STATUS: COMPLETED.**
</content>
