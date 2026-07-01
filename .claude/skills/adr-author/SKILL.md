---
name: adr-author
description: >
  Architecture Decision Record author for the PixelArt Creator platform. Use it
  (invoked by AGT-01 Architecture) to capture a significant architectural or
  layering decision as a numbered, immutable ADR under docs/adr/ using the
  standard Context / Decision / Consequences / Status structure, with each
  decision traced to its grounding requirement or research finding.
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

SKILL: adr-author
================================================================================

PURPOSE:
  Produce a single, immutable Architecture Decision Record documenting one
  architectural choice, why it was made, what was rejected, and its consequences —
  so future sprints can trace the reasoning (e.g. the C1–C6 resolutions and the
  three-layer/undo decisions in Dossier §9).

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given a described decision + its grounding, it writes a complete ADR unaided.

INPUTS:
  - The decision, the options considered, and the grounding (a user requirement
    S#, a research finding F#, or an orchestrator conflict resolution C#).
  - The existing docs/adr/ folder (to determine the next sequence number).

OUTPUTS:
  - docs/adr/NNNN-<kebab-title>.md with sections: Status (Proposed | Accepted |
    Superseded-by NNNN), Context, Decision, Alternatives Considered, Consequences
    (positive + negative), Grounding (source citation). Zero-padded 4-digit index.

PRECONDITIONS:
  - docs/adr/ exists or is created; a concrete decision + its grounding are known.

PROCEDURE:
  1. Determine the next ADR number = (highest existing NNNN in docs/adr/) + 1,
     zero-padded to 4 digits; if none, 0001.
  2. State Context: the forces/constraints (cite the requirement or finding).
  3. State the Decision as one imperative sentence; list Alternatives Considered
     with why each was rejected.
  4. State Consequences (what becomes easier and what becomes harder/riskier).
  5. Set Status; if it supersedes an earlier ADR, mark the old one Superseded-by.
  6. Write the file; confirm on disk; hand back to AGT-01.

DECISION POINTS:
  - Decision AA-D1:
    Condition: the decision reverses/replaces an accepted ADR.
    Branch A: create a new ADR AND set the old one's Status to "Superseded by NNNN"
      (never edit the old body — ADRs are immutable except the Status line).
    Default: A.
  - Decision AA-D2:
    Condition: the grounding cannot be traced to a user req / finding / resolution.
    Branch A: return needs_input — do not record an ungrounded decision (P1).
    Default: A.

ERROR HANDLING:
  - Error AA-E1: docs/adr/ unreadable → create it; if creation fails, BLOCKED.
  - Error AA-E2: ambiguous decision scope → needs_input naming the ambiguity.

DEPENDENCIES:
  - docs/adr/ location (AGT-08 owns docs/ subpaths; AGT-01 writes ADRs there by
    the Build Manifest resolution Open-Item 4). Fallback: create the folder.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - CHANGELOG / SESSION_LOG / mkdocs site → AGT-08 (changelog, mkdocs-site).
  - The actual architecture/layering choice's enforcement → layer-audit + sdd-plan.
  - Requirements/spec text → AGT-02.

SOURCES:
  - User requirements: Dossier §6.1 (AGT-01), §6.2 (adr-author), §9 (C1–C6).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    the ADR (Nygard) convention (Context/Decision/Consequences) as a standard.
