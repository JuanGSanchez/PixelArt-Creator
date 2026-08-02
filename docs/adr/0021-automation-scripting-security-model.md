# ADR-0021 — Automation & scripting security model: data-driven command DSL (no eval/exec), trusted-with-consent plugins

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-8-automation` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 8's defining acceptances are **security invariants** (spec §1, §11; Article VII is central):
a scripting/macro/plugin surface that **never passes untrusted input to `eval`/`exec`**
(REQ-P8-LOGIC-003, the hard constraint), whose edits happen **only via the shipped
reversible-command path** (HIS-1, REQ-P8-LOGIC-001), whose macros **replay to a state-identical
result** (REQ-P8-LOGIC-005), and whose plugins **cannot bypass the layer boundaries or their granted
permissions** (REQ-P8-LOGIC-009/-010). The spec deferred the *mechanism* to AGT-01 (DEP-2a/b, CL-2/CL-3/CL-6),
grounded by the **security-focused** Researcher (DEP-1).

The Researcher's finding is decisive and settled (`docs/research-phase-8-automation-20260704.md`,
Topic 1, Recommendation Matrix):

- **In-process CPython sandboxing of untrusted code is unachievable.** `pysandbox` (a CPython core
  dev's own project) is "BROKEN BY DESIGN"; the attack surface is the entire C core; introspection
  escapes are endless. [HIGH]
- **RestrictedPython "is not a sandbox system"** per its own maintainers — it is an AST hardening
  layer whose safety is only as good as an injected whitelist; never a standalone barrier for
  untrusted code. [HIGH]
- **Every full-language desktop plugin system** (Krita, Blender, GIMP-Python) is a **trusted-code
  model with, at best, a consent gate** — none is a true sandbox for arbitrary Python. Only Aseprite
  (a *small embeddable language + curated API + consent-gated filesystem*) approaches "safe for
  third-party scripts." [HIGH]
- **Entry-point / plugin loading IS code execution** (`import` runs top-level code); discovery is not
  isolation. [HIGH]
- The **recommended default** is **Option A — a data-driven command DSL/macro** replayed by a trusted
  dispatcher over whitelisted reversible commands: *no code execution at all*, Article VII-compliant
  by construction, and it doubles as the macro format.

Article VII is therefore not a nuisance constraint — it aligns with industry consensus. The design
must guarantee **no untrusted input ever reaches `eval`/`exec`**, and must do so *structurally*, not
by trusting a fragile in-process barrier.

## Decision

**Ship the scripting/macro/CLI surface as Option A — a data-driven command DSL replayed by a trusted
dispatcher over the shipped `logic/history` reversible commands, with ZERO `eval`/`exec` anywhere on
any path. Ship the plugin system as a TRUSTED-with-consent, default-deny, no-auto-run local extension
contract whose plugins may only register/invoke DSL commands (they cannot reach `eval`/`exec`, `ui/`,
the filesystem/network outside grants, or the reversible-command path). Defer untrusted-marketplace
plugins requiring OS-isolation (Option C) to a later phase (Article XI hook).**

### The invariant (fixed, non-negotiable — Article VII)

> **No input — trusted or untrusted — is ever passed to `eval`, `exec`, `compile` on user/plugin
> strings, or any equivalent arbitrary-code-execution primitive, on any automation code path.**

This is satisfied *by construction*: the automation engine executes **data** (a validated list of
`{op, params}`), never a language. There is no interpreter to escape. `logic/scripting.py`,
`logic/macro.py`, `logic/plugins.py`, `logic/procgen.py`, `logic/batch_ops.py`,
`data/macro_io.py`, and `data/automation_cli.py` contain **no** `eval`/`exec`/`compile(...,
"exec")`/`__import__` of user-supplied names. AGT-04 asserts this (a source-level scan + a crafted
malicious payload that is rejected, never run — SC-L003-1).

### Scripting surface — Option A, data-driven command DSL (REQ-P8-LOGIC-001/-002/-003)

- A **command registry** (`logic/scripting.py`) maps a stable **op-name** → a **trusted command
  factory** that returns a `history.Command` (or `FunctionCommand`) — the *same* reversible path the
  UI drives (HIS-1). Only names in the registry are executable; an unknown op is a domain error.
- A **trusted dispatcher** validates each step's op-name against the registry and its params against
  the factory's declared schema (types/bounds, IO-3-style defensive validation), constructs the
  command, and pushes it onto the document's `History`. There is **no** path to mutate
  `Document`/`PixelBuffer` state except through a registered reversible command (REQ-P8-LOGIC-001) —
  no back-door write, no raw `exec` of a step. **The dispatch is atomic (two-phase; S2 fix — see
  ADR-0022 §Consequences):** the whole op list is validated before anything is applied, and a mid-run
  application failure rolls the already-applied sub-commands back in reverse order, leaving the
  `Document` byte-identical — a failed multi-op is all-or-nothing, never a partial mutation.
- A **script** and a **recorded macro** are the *same artifact*: a validated `{op, params}` list
  (Topic 1 / Topic 2 convergence). The CLI runs the same list headlessly. One surface, one
  security story, one test target.
- **RestrictedPython (Option B) is NOT adopted**, even for trusted local scripts. The DSL covers
  authored automation; shipping a "not-a-sandbox" interpreter would invite exactly the misuse Article
  VII forbids and add a second, weaker security surface for no acceptance benefit. If a future phase
  wants a richer authored-script language, it is an Article XI addition gated behind explicit
  trusted-only consent + defence-in-depth — a new ADR, not this one.

### Plugin trust model — trusted-with-consent, default-deny, no auto-run (REQ-P8-LOGIC-008/-009/-010)

- **Discovery** via `importlib.metadata.entry_points(group="pixelart_creator.plugins")` (stdlib,
  Python 3.12 keyword API — Qt-free). Discovery does **not** auto-load or auto-run anything.
- A plugin ships a **manifest** (declared identity + version + `api_version` + the capabilities it
  requests). The host **validates the manifest defensively** (IO-3) and **rejects** a
  malformed/unsupported one with a domain error — no execution on malformed input (REQ-P8-LOGIC-008).
- A plugin's **only API surface** is the DSL command registry: it receives a **capability object**
  exposing *only* the command-registration/dispatch API and its granted resources. It **registers
  command factories**; it does not gain raw mutation access, cannot `import` `ui/`, and cannot touch
  the filesystem/network outside its grants (REQ-P8-LOGIC-009).
- **Deny by default:** any capability a plugin did not declare and was not granted is denied with a
  domain error — no silent bypass, no partial-then-corrupt state (REQ-P8-LOGIC-010). The UI shows the
  declared permissions **before** the user enables a plugin (REQ-P8-UI-005). **No auto-run**: a
  discovered plugin is inert until the user explicitly enables it (the Blender "off-by-default
  auto-exec" precedent). `MAX_PLUGINS_LOADED` bounds concurrently loaded plugins.
- **Honesty about strength (Researcher §3.2):** because *loading a Python plugin is code execution*,
  in-process capability injection is **advisory-strength**, adequate **only** because P8 plugins are
  **trusted, consent-installed, first-party/vetted** extensions (the Krita/Blender reality, stated
  plainly). A determined in-process plugin can introspect around a convention boundary; P8 therefore
  does **not** claim to run *untrusted* third-party plugins safely.

### What P8 explicitly does NOT ship (deferred — Article XI)

- **Untrusted-marketplace plugins with a defensible boundary** require **OS-level isolation** (Option
  C: subprocess + seccomp/container + narrow IPC capability API, `exec`/`fork` blocked inside the
  jail). This is heavy, per-OS engineering and is **deferred to a later phase / FU** (spec CL-14).
  P8 ships a **marketplace-*ready*** *local* contract (versioned, declared capabilities, discoverable,
  consent-gated) — not a hosted store and not an untrusted-code sandbox.
- No embedded Python interpreter, no network/remote script execution, no AI-assisted generation.

## Alternatives Considered

- **Embedded RestrictedPython over a curated `globals` (Option B).** Rejected as the shipped surface:
  its own maintainers state it "is not a sandbox"; it still *executes code* (Article VII risk), and it
  buys no acceptance the DSL does not already meet. Reserved, if ever, for an explicitly trusted-only
  future tier behind a new ADR.
- **Full in-process Python plugins, marketed marketplace-safe (Krita model).** Rejected: contradicts
  Article VII for untrusted authors; the Researcher shows this is a trusted-code model, never a
  sandbox. We adopt its *consent* discipline but not the marketplace-of-untrusted claim.
- **OS-isolated untrusted plugin host (Option C) in P8.** Rejected *for now* (not on principle):
  correct for arbitrary untrusted code, but heavy + per-OS; out of the ROADMAP Phase-8 scope. Left as
  a clean Article XI extension seam (the command-DSL/IPC surface is the same boundary a future jail
  would speak over).
- **Letting scripts call arbitrary `logic/` functions directly.** Rejected: that is a back-door around
  the reversible-command path (violates REQ-P8-LOGIC-001) and widens the trusted surface. The registry
  of command factories is the single, testable edit surface.

## Consequences

**Positive.** Article VII is satisfied *structurally* — there is no interpreter to escape, so
"no untrusted input reaches `eval`/`exec`" is provable by a source scan, not by trusting a fragile
barrier. One artifact (the `{op, params}` list) serves scripting + macro + CLI + plugin-registered
ops → one determinism story and one security test target. Every automation edit is a reversible
command by construction (HIS-1), so undo/redo and CLI==GUI parity are free. The plugin contract is
marketplace-*ready* without over-promising an untrusted sandbox.

**Negative / risk.** The DSL's expressiveness is bounded by the exposed op vocabulary (acceptable:
new ops are additive, Article XI). In-process plugin isolation is advisory-strength — mitigated by
default-deny + explicit consent + no-auto-run + the honest "trusted-only" framing; untrusted-plugin
OS-isolation is deferred, not pretended. The trust boundary must be documented for users (AGT-08).

## Grounding

- Spec `specs/phase-8-automation/spec.md` §1–§2 (security-invariant framing), §4
  (REQ-P8-LOGIC-001/-002/-003/-008/-009/-010), §6 (non-goals — model deferred to AGT-01/ADR), §8
  (DEP-1/DEP-2), §9 Article VII, §10 CL-1/CL-2/CL-3/CL-6/CL-7/CL-14, §11 SC-L001-1/L003-1/L009-1/L010-1;
  `traceability.md` DEP-1/DEP-2, Article I/VII watch (BF-2).
- Research `docs/research-phase-8-automation-20260704.md` — Executive summary 1–4, Topic 1 (pysandbox
  BROKEN-BY-DESIGN, RestrictedPython "not a sandbox", curated-API convergence, Aseprite/Krita/Blender
  survey), §1.5 Options A–D, Recommendation Matrix (A = compliant by construction), §3
  (discovery ≠ isolation), Open decisions 1/2/3/8/9/10.
- Shipped `logic/history.py` (HIS-1 `Command`/`FunctionCommand`/`History`), `data/project_io.py`
  (IO-3 defensive load). Constitution Article VII §1 (no `eval`/`exec`; defensive parsing), Article I
  (three-layer purity; automation out of `ui/`), Article XI (untrusted-plugin OS-isolation as a later
  extension).
