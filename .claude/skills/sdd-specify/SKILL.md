---
name: sdd-specify
description: >
  SDD "specify" phase for the PixelArt Creator platform. Use it (invoked by
  AGT-02) to draft or refine a feature's spec.md from user requirements —
  functional requirements and user stories, the WHAT and WHY, no technology
  choices yet. Absorbs functional-to-technical translation. Gate: refuses to
  produce a spec unless constitution.md exists to govern it.
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
    # P5 inherits AGT-02's context discipline; P10 inherits AGT-02's exit status.
  custom:
    - id: C1
      name: Constitution-governed
      requires: The spec must comply with constitution.md; if it is absent, refuse and request AGT-01 author it first.
      rationale: spec-driven-development.md §2 (constitution governs all phases).
---

SKILL: sdd-specify
================================================================================

PURPOSE:
  Produce/refine a per-feature spec.md capturing WHAT to build and WHY (functional
  requirements + user stories), with no technology decisions.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the feature request and constitution.md, it produces spec.md unaided.

INPUTS:
  - Feature request + REQ-ID range (from AGT-02 / orchestrator strategy). Markdown/text.
  - constitution.md (project memory root). Governs the spec.

OUTPUTS:
  - spec.md at specs/<feature>/spec.md — functional requirements, user stories,
    acceptance-criteria stubs, explicit non-goals. No tech/stack content.

PRECONDITIONS:
  - A concrete feature request exists. constitution.md exists (gate C1).

PROCEDURE:
  1. GATE: verify constitution.md exists; if missing, stop and return needs_input asking
     AGT-01 to author it (do not draft a spec ungoverned).
  2. Extract functional requirements and user stories from the request; assign each a REQ-ID.
  3. Translate any solution-flavoured phrasing into technology-neutral functional statements
     (functional→technical translation) — WHAT, not HOW.
  4. Write acceptance-criteria stubs per requirement and an explicit non-goals section.
  5. Write spec.md to specs/<feature>/; confirm the write on disk; hand back to AGT-02.

DECISION POINTS:
  - Decision SP-D1:
    Condition: the request mixes multiple features.
    Branch A (true): split into one spec.md per feature folder; list them in the return.
    Branch B (false): single spec.md.
    Default: if feature boundaries are unclear, return needs_input (do not guess the split).
  - Decision SP-D2:
    Condition: a requirement names a specific technology/stack.
    Branch A (true): record it as a constraint, keep the requirement itself neutral; defer the
      choice to sdd-plan.
    Branch B (false): proceed neutral.
    Default: treat as A (preserve neutrality of the requirement).

ERROR HANDLING:
  - Error SP-E1:
    Trigger: constitution.md missing.
    Response: return needs_input; name constitution.md as the blocker (C1).
  - Error SP-E2:
    Trigger: the request is too vague to yield testable requirements.
    Response: return needs_input with the specific gaps (feeds sdd-clarify).

DEPENDENCIES:
  - constitution.md (AGT-01) — governing principles. Fallback: block until it exists.

BUNDLED RESOURCES:
  - None — the skill is self-contained.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Technology/stack/architecture choices → sdd-plan (AGT-01).
  - Clarification questioning + Gherkin → sdd-clarify (AGT-02).
  - Task breakdown → sdd-tasks; code → AGT-03/AGT-05.

SOURCES:
  - User requirements: Dossier §6.2 (sdd-specify), §6.6 (functional-to-technical disposition).
  - Inner assets: asset-templates.md §Skill, spec-driven-development.md §2–§3, principles.md §3 (skill row).
