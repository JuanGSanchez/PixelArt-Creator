---
name: sdd-plan
description: >
  SDD "plan" phase for the PixelArt Creator platform. Use it (invoked by AGT-01)
  to define HOW to build a clarified feature — technical architecture, stack, data
  model, and implementation strategy — producing plan.md. Stack/library choices
  are grounded through The Researcher (never invented). Gate: refuses to run
  unless spec.md exists and its clarifications are resolved.
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
    # P5 inherits AGT-01's; P10 inherits AGT-01's exit status.
  custom:
    - id: C1
      name: Stack grounded via Researcher
      requires: Every stack/library/API choice traces to a Researcher finding (category 3) or a fixed user requirement (S8); no invented choices.
      rationale: spec-driven-development.md §3; SKILL.md §3; P1.
    - id: C2
      name: Three-layer compliance
      requires: plan.md must place every module in ui/ | logic/ | data/ per S11 and reference logic/constants.py for numerics (S12); no plan may violate the constitution.
      rationale: User req S11/S12; Dossier §6.7.
---

SKILL: sdd-plan
================================================================================

PURPOSE:
  Produce plan.md: the technical architecture, stack, data model, and implementation
  strategy for a clarified feature, compliant with the constitution and three-layer S11.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES — given
  a clarified spec.md, constitution.md, and any needed Researcher findings, it produces plan.md.

INPUTS:
  - spec.md with resolved clarifications (from AGT-02). Required.
  - constitution.md (governing). Required.
  - Researcher findings for any external stack/API choice (e.g. F9/F14). As needed.

OUTPUTS:
  - plan.md at specs/<feature>/plan.md — architecture, module→layer mapping (ui/logic/data),
    data model (.pixproj shape where relevant), stack decisions with citations, and the
    implementation strategy.

PRECONDITIONS:
  - spec.md exists with clarifications resolved (gate); constitution.md exists.

PROCEDURE:
  1. GATE: verify spec.md exists AND has no open clarifications; else return needs_input
     (run sdd-clarify first).
  2. Derive the architecture from the requirements; map every module to ui/ | logic/ | data/
     (S11) and reference logic/constants.py for numerics (S12).
  3. For any stack/library/API choice, cite a Researcher finding or S8; if a needed choice is
     ungrounded, request a RESEARCH REQUEST via the orchestrator (do not invent — C1).
  4. Define the data model and the implementation strategy (order, reversible-op boundaries,
     render-pipeline touchpoints handed to AGT-10).
  5. Write plan.md; confirm on disk; hand back to AGT-01.

DECISION POINTS:
  - Decision PL-D1:
    Condition: a required stack/API choice lacks grounding.
    Branch A (true): emit a RESEARCH REQUEST via the orchestrator; hold plan on that point.
    Branch B (false): cite the source and proceed.
    Default: treat as A (block the ungrounded decision).
  - Decision PL-D2:
    Condition: a design would place Qt in logic/ or data/, or a magic number outside constants.py.
    Branch A (true): reject; redesign to satisfy S11/S12 (C2).
    Branch B (false): accept.
    Default: treat as A (enforce the constitution).

ERROR HANDLING:
  - Error PL-E1:
    Trigger: spec.md missing or clarifications open.
    Response: return needs_input naming the predecessor phase.
  - Error PL-E2:
    Trigger: a constitution conflict cannot be resolved within the plan.
    Response: escalate to AGT-01/orchestrator; resolve UP to the constitution, not around it.

DEPENDENCIES:
  - spec.md (AGT-02); constitution.md (AGT-01); Researcher findings (AGT-M4). Fallbacks: block.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Requirements/spec → sdd-specify/clarify (AGT-02); task breakdown → sdd-tasks; code →
    AGT-03/AGT-05; render-perf profiling → AGT-10; internet search → The Researcher.

SOURCES:
  - User requirements: Dossier §1 (S8,S11,S12), §6.2 (sdd-plan), §6.7 (plan gate).
  - Inner assets: asset-templates.md §Skill, spec-driven-development.md §3, principles.md §3 (skill row).
