# ADR-0042 — Embedding: the in-app chat dock (`ui/`), the headless `pixelart-assistant` CLI (`data/`), responsiveness, and the launch / User-Guide / README surfaces (DEP-5)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-08 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-14-ai-assistant` (Slices 14E, 14F) |
| Privacy | **S19-PRIVATE — docs/ is gitignored; this ADR is NOT committed.** |
| Relates to | ADR-0039/0040/0041, ADR-0020/0022 (headless CLI in `data/`, the `check_layering` blind-spot lesson), ADR-0029 (in-app User-Guide layering) |

## Context

The assistant embeds two ways (spec D2): an in-app PySide6 **chat dock** + provider/key config +
tiered-confirm surface (`ui/`, the only Qt — 14E, REQ-P14-UI-001..008), and a **headless
`pixelart-assistant` CLI** (`data/`, Qt-free, mirroring the shipped `pixelart-run` — 14F,
REQ-P14-DATA-008). Spec §8 DEP-5 defers responsiveness to AGT-01/AGT-10: the model round-trip is
**batch/off the per-frame loop** (not `FRAME_BUDGET_MS`-gated), so the assessment is
responsiveness-not-frame-budget. The standing docs rule requires a **new User-Guide topic under the
existing Automation section** (not a new section) + a README launch surface.

## Decision

### 1. Chat dock + config + tiered-confirm — `ui/` (14E, the only Qt)

| Module | Responsibility | Binds to |
| --- | --- | --- |
| `ui/assistant_dock.py` | `Assistant_Dock(QDockWidget)` — transcript view + input/send; **drives the `logic/` loop via the injected `ChatBackend`, never a provider directly** (no provider/HTTP type in `ui/`, REQ-P14-DATA-007); shows replies + the undoable edits it makes; surfaces errors (not swallowed). `tr()` + `changeEvent`. | `logic/assistant`, `ui/assistant_worker`, `ui/commands` |
| `ui/provider_config_dialog.py` | `Provider_Config_Dialog(QDialog)` — arbitrary endpoint + API key entry + select/connect; hands the key to `data/llm/token_store` (OS keyring); **`ui/` retains no raw key beyond entry**, never writes it to `.pixproj`/log (Article VII §3, REQ-P14-UI-002). Provider-agnostic behaviour. `tr()`. | `data/llm/token_store`, `data/llm/port` |
| `ui/assistant_worker.py` | `Assistant_Worker(QRunnable)` + signals on a window-owned `QThreadPool` — runs the Qt-free loop off the GUI thread; progress/result/error/cancel over queued GUI-thread signals; **no Qt off-thread** (the Phase-7/8/10/11 worker precedent). | `logic/assistant`, `data/llm/*` |
| `ui/commands.py` | extend | one grouped `QUndoCommand` per assistant **edit** (delegating to the `history.GroupCommand` the loop's dispatch returned); a chat message / provider-connect / confirm-decision push **no** command (view/session state, the Phase-8 CL-8 precedent). No domain math. | `history` + dispatch results |
| `ui/main_window.py` | extend | add an Assistant menu + dock the panel; hold the active document + the injected adapter; wire the worker. | the new assistant UI |

**Tiered-confirm surface (REQ-P14-UI-003):** when the logic gate (ADR-0041 §2) classifies a pending action
**destructive**, the dock shows an **explicit confirm/cancel prompt naming the action**; the action runs
only on confirmation, is cancelled otherwise; **reversible** actions apply without a prompt but remain
visible + undoable. The UI **renders the gate's decision — it does not re-implement or relax the
classification** (SC-UI-003-1). a11y (REQ-P14-UI-005), both themes with role-based colours
(REQ-P14-UI-006), `tr()` + live retranslate (REQ-P14-UI-007) apply to every added control.

### 2. Headless `pixelart-assistant` CLI — `data/assistant_cli.py` (14F, Qt-free)

`data/assistant_cli.py` (NEW, zero Qt) mirrors the shipped `data/automation_cli.py` (`pixelart-run`):
`argparse` driver that loads a `.pixproj` via `project_io.load_project` (IO-3 defensive), constructs an
`LLMPort` adapter (fake in CI; real credential-gated adapter otherwise — ADR-0040), runs the **same**
`logic/assistant` loop against it, and saves the result back through the shipped `.pixproj` path
(SC-D008-1). It **reuses the same tiered gate** (ADR-0041 §2): a **destructive** op requires an **explicit
affordance** (e.g. `--yes` / confirm flag) — **never** an auto-run — while reversible ops apply
(SC-D008-2). It lives in **`data/` (not a new `cli/` package)** *specifically* because `check_layering.py`
only enforces Qt-freedom on the `logic/`/`data/` roots — a `cli/` sibling would be an unscanned Qt
blind-spot (the ADR-0020/0022 lesson). Imports downward only (`data → logic`, `data → data`); zero Qt; no
`eval`/`exec`. Exit codes mirror `pixelart-run` (0 ok / 1 runtime / 2 bad-args-or-load).

**`pyproject` `[project.scripts]`** gains `pixelart-assistant =
"pixelart_creator.data.assistant_cli:main"` — an **AGT-09** edit (Article IX), like `pixelart-run`.

### 3. Responsiveness — off the per-frame loop, minimal AGT-10 involvement (DEP-5, REQ-P14-UI-004)

The assistant is **batch/background** work (Article VI): a model round-trip runs on the
`Assistant_Worker` off the GUI thread; the network I/O (14D urllib) is bounded by
`ASSISTANT_REQUEST_TIMEOUT_S`; progress/cancel are surfaced where a long call warrants. The **16 ms
`FRAME_BUDGET_MS` does not gate a model call** — unlike Phase-9's per-frame overlays, this is batch IO, the
Phase-7/8/10/11 worker posture. **AGT-10 involvement is minimal:** the assistant introduces **no** new
per-frame canvas work — its edits are the *same* undoable `dispatch` ops the app already applies, re-rendered
through the existing dirty-rect path — so **no AGT-10 render-strategy directive is required**; AGT-10 need
only confirm no canvas-frame regression. This ADR fixes the observable **stays-responsive** contract
(SC-UI-004-1).

### 4. Docs — a new topic under Automation + README (REQ-P14-UI-008)

- A **NEW in-app User-Guide topic under the EXISTING `automation-and-scripting` section** of the shipped
  guide manifest — a new *topic*, **NOT a new section** — so `len(sections)` stays
  `== len(REQUIRED_AREAS) == 12` (per shipped `logic/guide_model.py`; adding a topic is a data change, no
  new required area — SC-UI-008-1). AGT-08 authors the prose (the ADR-0029 content/layering model).
- A **README launch surface** documenting **both** the in-app assistant dock **and** the
  `pixelart-assistant` CLI: how to configure a provider/key, that it is credential-optional, and the
  tiered-safety behaviour (SC-UI-008-2). AGT-08 authors; shared with 14F.

## Alternatives Considered

- **A modal assistant dialog instead of a dockable panel.** Rejected: a dock lets the user watch the
  assistant drive the workflow live (US-1) and keeps the canvas visible; matches the Phase-8 automation
  panels.
- **A `cli/` top-level package for `pixelart-assistant`.** Rejected: `check_layering` blind-spot
  (ADR-0020/0022); `data/` keeps it Qt-guarded.
- **Run the loop on the GUI thread with `processEvents`.** Rejected: freezes the UI on a slow model call;
  the worker precedent is established and clean.
- **A new User-Guide section for the assistant.** Rejected: would break
  `len(sections) == len(REQUIRED_AREAS) == 12`; the assistant is an Automation capability — a topic under
  it (spec REQ-P14-UI-008).
- **An AGT-10 frame-budget profiling pass for the assistant.** Rejected as unnecessary: no per-frame canvas
  work is added (§3); a confirm-no-regression check suffices.

## Consequences

**Positive.** Two embeddings over one loop (GUI + headless), byte/behaviour-identical (CLI==GUI, the
`pixelart-run` precedent); UI stays responsive; keys never touch `ui/` beyond entry; docs discoverable
without disturbing the 12-area guide invariant. No new top-level package; the only Qt stays in `ui/` (+ the
shipped `ui/commands.py`).

**Negative / risk.** The dock's "watch it act" UX + streaming partial output is new UI surface for AGT-05
(a11y/both-themes/i18n verified by AGT-06/AGT-07). The CLI's confirm affordance must be unambiguous so a
scripted destructive op is never auto-applied (SC-D008-2) — covered by the tiered-gate test.

## Grounding

- Spec §2 (14E/14F), §4 REQ-P14-UI-001..008 + REQ-P14-DATA-008, §8 DEP-5, §10.1 D2; `acceptance.md`
  SC-UI-001-1..008-2, SC-D008-1/-2.
- Shipped `data/automation_cli.py` (`pixelart-run`), `logic/guide_model.py` (`REQUIRED_AREAS` == 12),
  Phase-7/8/10/11 `ui/*_worker.py` precedent, `ui/commands.py` (CL-8). Constitution Article I, V, VI, VII, IX.
- Researcher `ad2616c7` R5.4 (confirm surface), R2.4 (streaming orthogonal to the loop). ADR-0020/0022,
  ADR-0029, ADR-0039/0040/0041.
