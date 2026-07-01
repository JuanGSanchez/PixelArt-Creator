---
name: story-map
description: >
  User-story mapping and feature-label taxonomy skill for the PixelArt Creator
  platform. Use it (invoked by AGT-02 Requirements) to organise requirements
  into a story map (user activities → tasks → stories) and to maintain a stable
  feature-label taxonomy aligned to the roadmap Phases 1–4 (and extensible to
  5–12), so specs, issues, and traceability all share one vocabulary.
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
---

SKILL: story-map
================================================================================

PURPOSE:
  Turn a body of requirements into a two-axis story map (the backbone of user
  activities across the top; prioritised stories beneath each) and a canonical
  feature-label set, so AGT-02's specs and AGT-09's GitHub issues use one shared
  taxonomy tied to the roadmap phases (S6).

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the requirement set + roadmap phases it emits a story map + label list.

INPUTS:
  - The requirement/feature set (from user requirements / spec.md drafts).
  - The roadmap phase list (Dossier S6: Phases 1–4 in scope; 5–12 extensible).

OUTPUTS:
  - A story map (Markdown): activities → tasks → stories, each story tagged with
    a feature label and a target roadmap phase.
  - A feature-label taxonomy (canonical label → definition), kebab-case, stable.

PRECONDITIONS:
  - A requirement set exists; the roadmap phases are known.

PROCEDURE:
  1. Extract the user activities (the "backbone" — the big verbs a user performs:
     paint, pick-colour, zoom/pan, manage-layers, …) from the requirements.
  2. Under each activity, list the tasks, then the concrete user stories.
  3. Assign each story a feature label (create new labels only when no existing
     label fits; keep them kebab-case) and a roadmap phase (in-scope 1–4, or a
     later phase marked "future").
  4. Prioritise stories top-to-bottom within each column (walking skeleton first).
  5. Emit the map + the label taxonomy; hand to AGT-02 for spec authoring.

DECISION POINTS:
  - Decision SM-D1:
    Condition: a story spans multiple activities.
    Branch A: place it under the primary activity, cross-reference the others.
    Default: A.
  - Decision SM-D2:
    Condition: a requested feature maps to roadmap Phase 5–12 (out of build scope).
    Branch A: record it in the map marked "future" (extensibility, S6); do not
      spec/implement it in this build.
    Default: A.

ERROR HANDLING:
  - Error SM-E1: requirements too vague to place → return needs_input listing the
    gaps (feeds sdd-clarify, AGT-02).
  - Error SM-E2: label collision (same concept, two names) → merge to one
    canonical label and note the alias.

DEPENDENCIES:
  - Roadmap phases (Dossier S6). Fallback: ask the orchestrator for the phase list.
  - Feeds sdd-specify (AGT-02) and traceability-matrix.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - The spec.md text itself → sdd-specify (AGT-02).
  - REQ↔test coverage matrix → traceability-matrix (AGT-02).
  - Creating GitHub issues/labels in the repo → AGT-09.

SOURCES:
  - User requirements: Dossier §1 (S6 roadmap), §6.1 (AGT-02), §6.2 (story-map).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    user-story-mapping (Patton) as the grounded technique.
