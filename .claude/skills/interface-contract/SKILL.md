---
name: interface-contract
description: >
  Module interface-contract and STRUCTURE.md steward for the PixelArt Creator
  platform. Use it (invoked by AGT-01 Architecture) to define the public
  interface a logic/ or data/ module must expose to ui/ (function/class
  signatures, types, exceptions, invariants) BEFORE it is implemented, and to
  keep STRUCTURE.md — the map of the three-layer tree and each module's
  responsibility + public surface — accurate.
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
---

SKILL: interface-contract
================================================================================

PURPOSE:
  Specify the stable public contract of a module (the signatures ui/ or another
  layer may depend on) so implementation (AGT-03/AGT-05) and tests (AGT-04/06)
  target a fixed surface, and record it in STRUCTURE.md — keeping S11 layering
  legible without reading every file.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the module's role and the constants it consumes, it emits a typed
  interface contract + a STRUCTURE.md entry unaided.

INPUTS:
  - The module's responsibility + its layer (from layer-audit / plan.md).
  - logic/constants.py (numeric params it must consume, S12).
  - The current STRUCTURE.md (to update, or create if absent).

OUTPUTS:
  - An interface contract: public functions/classes with typed signatures
    (PEP 484), raised domain exceptions, pre/postconditions and invariants, and
    an explicit "not part of the contract" note.
  - An updated STRUCTURE.md row: path | layer | responsibility | public surface.

PRECONDITIONS:
  - The module's layer is decided (via layer-audit); logic/constants.py exists.

PROCEDURE:
  1. Enumerate the operations ui/ (or a sibling module) needs from this module.
  2. For each, define a typed signature, the exception(s) it may raise (domain
     exceptions, not bare Exception), and its invariants; forbid Qt types in a
     logic/ or data/ contract (S11).
  3. Reference numeric bounds from logic/constants.py (never inline a literal).
  4. Mark private helpers as out-of-contract so callers do not couple to them.
  5. Update/append the STRUCTURE.md entry; confirm on disk; hand back to AGT-01.

DECISION POINTS:
  - Decision IC-D1:
    Condition: a proposed contract exposes a Qt type from logic/ or data/.
    Branch A: reject — redesign so the Qt boundary stays in ui/ (S11); the logic
      returns plain Python/NumPy, ui/ adapts to Qt.
    Default: A.
  - Decision IC-D2:
    Condition: two modules would expose overlapping responsibilities.
    Branch A: return needs_input to AGT-01 to reassign ownership (single owner).
    Default: A.

ERROR HANDLING:
  - Error IC-E1: STRUCTURE.md missing → create it with a header + this entry.
  - Error IC-E2: constants needed but absent from constants.py → flag AGT-03 to
    add them there first (no magic numbers, S12).

DEPENDENCIES:
  - logic/constants.py (AGT-03) for numeric bounds. Fallback: request the constant
    be centralised before finalising the contract.
  - layer-audit (placement) upstream.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Implementing the module → AGT-03 (logic-scaffold) / AGT-05 (widget-scaffold).
  - Writing tests against the contract → AGT-04/AGT-06.
  - ADRs → adr-author; task ordering → sdd-tasks.

SOURCES:
  - User requirements: Dossier §1 (S11/S12), §6.1 (AGT-01), §6.2 (interface-contract).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    PEP 484 typing as the grounded signature standard.
