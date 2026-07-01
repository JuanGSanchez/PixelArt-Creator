---
name: layer-audit
description: >
  Three-layer placement auditor for the PixelArt Creator platform. Use it
  (invoked by AGT-01 Architecture) to decide where a new/changed module belongs
  (ui/ vs logic/ vs data/) and to prove the choice by running the deterministic
  scripts check_layering and check_cycles over pixelart_creator/. Absorbs the
  legacy file-placement decision. Report-and-decide: it never edits code; it
  emits a placement decision + the script findings.
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
    # P5 inherits AGT-01's context discipline; P10 inherits AGT-01's exit status.
  custom:
    - id: C1
      name: Script-backed, never eyeballed
      requires: The layering/cycle verdict must come from check_layering.py + check_cycles.py exit codes, not from reading imports by hand.
      rationale: P11 — the scripts are the canonical mechanism (Dossier §8).
---

SKILL: layer-audit
================================================================================

PURPOSE:
  Decide the correct layer/file for a module and verify the three-layer rule
  (S11): ui/ (PySide6) may import logic/ + data/; logic/ is pure Python (zero
  Qt, no ui/data import); data/ is I/O only (zero Qt, no ui import); the only
  Qt file outside ui/ is ui/commands.py. Prove it with the scripts.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the module description + the pixelart_creator/ tree it emits a placement
  decision and runs the two bundled-by-reference scripts unaided.

INPUTS:
  - The module/feature description + candidate path(s) (from AGT-01 / tasks.md).
  - The pixelart_creator/ package tree (read-only). Required.

OUTPUTS:
  - A placement decision: {chosen path, layer, rationale vs S11} and the JSON
    findings from check_layering + check_cycles. Handed back to AGT-01.

PRECONDITIONS:
  - pixelart_creator/ exists; scripts/check_layering.py + scripts/check_cycles.py
    exist (Dossier §6.5). Python 3.8+.

PROCEDURE:
  1. Classify the unit by responsibility: pure computation/domain rules → logic/;
     file/format I/O (e.g. .pixproj read/write) → data/; Qt widgets/views/scene/
     undo → ui/. Undo wrappers ALWAYS go to ui/commands.py (C1 of orchestrator).
  2. Pick the concrete path following naming CONVENTIONS (modules snake_case).
  3. Run `python scripts/check_layering.py --root pixelart_creator --json` and
     `python scripts/check_cycles.py --root pixelart_creator --json`; capture
     exit codes (0 clean / 1 violation / 2 error) and JSON.
  4. If either reports a violation implicating the placement, revise the choice
     (or flag the offending import to AGT-01) and re-run. Do not accept a
     placement that leaves a violation.
  5. Return the decision + findings; AGT-01 records it in STRUCTURE.md.

DECISION POINTS:
  - Decision LA-D1:
    Condition: the unit needs BOTH Qt and domain computation.
    Branch A: split it — domain math to logic/, Qt wiring to ui/ that calls it.
    Branch B (indivisible Qt-undo): ui/commands.py.
    Default: split (A) — never place Qt in logic/ or data/.
  - Decision LA-D2:
    Condition: check_layering/check_cycles exits 2 (error/unreadable root).
    Branch A: report BLOCKED with the stderr; do not guess a verdict.
    Default: A.

ERROR HANDLING:
  - Error LA-E1: script reports a real violation → return the finding to AGT-01;
    the placement is not approved until clean (report-not-fix).
  - Error LA-E2: package root missing → BLOCKED; ask the orchestrator to scaffold.

DEPENDENCIES:
  - scripts/check_layering.py, scripts/check_cycles.py (AGT-01, Dossier §6.5).
    Fallback: if absent, BLOCK and request the Metaprompter build them.
  - CONVENTIONS naming + S11/S12 (orchestrator). Fallback: read from disk.

BUNDLED RESOURCES:
  - None — reuses the repo-root scripts (P6: declared, not duplicated).

BUNDLED SCRIPTS:
  - None (reuses scripts/check_layering.py + scripts/check_cycles.py).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Writing/fixing the code → AGT-03 (logic/data) / AGT-05 (ui).
  - plan.md/tasks.md authoring → sdd-plan / sdd-tasks (AGT-01).
  - Cross-artifact consistency gate → sdd-analyze (AGT-01).
  - Render-perf placement of drawing code → strategy from AGT-10.

SOURCES:
  - User requirements: Dossier §1 (S11/S12), §6.1 (AGT-01), §6.2 (layer-audit),
    §6.6 (file-placement disposition), §8 (script owners).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row),
    programmatic-determinism.md (script-over-judgment).
