---
name: changelog
description: >
  Changelog author for the PixelArt Creator platform. Use it (invoked by AGT-08
  Documenter) to maintain docs/CHANGELOG.md in Keep a Changelog format, derived
  from Conventional Commits (feat/fix/docs/refactor/… + REQ-IDs), grouped under
  Added/Changed/Fixed/Removed with an Unreleased section that AGT-09's release
  skill promotes to a semver version on tag.
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
    # P5 inherits AGT-08's context discipline; P10 inherits AGT-08's exit status.
---

SKILL: changelog
================================================================================

PURPOSE:
  Keep a human-readable, Keep-a-Changelog-formatted CHANGELOG derived from the
  Conventional Commit history, so each release documents what changed and why
  (with REQ-IDs), ready for the release skill to cut a version.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the commit range it updates CHANGELOG.md unaided.

INPUTS:
  - The Conventional Commit log for the range (feat/fix/docs/… with REQ-IDs).
  - The existing docs/CHANGELOG.md.

OUTPUTS:
  - Updated docs/CHANGELOG.md: an Unreleased section grouping entries under Added /
    Changed / Fixed / Removed / Deprecated / Security, each line citing its REQ-ID.

PRECONDITIONS:
  - Commits follow Conventional Commits (AGT-09 enforces); CHANGELOG.md exists or
    is created with a Keep-a-Changelog header.

PROCEDURE:
  1. Read the commit subjects/bodies in the range (request the Gleaner if ≥5 files/
     large log via the orchestrator).
  2. Map each commit type to a section (feat→Added, fix→Fixed, refactor/perf→Changed,
     removal→Removed) and write one entry with its REQ-ID.
  3. Place entries under Unreleased; keep prior released sections immutable.
  4. Write CHANGELOG.md; confirm on disk; the release skill (AGT-09) later renames
     Unreleased → the new version + date on tag.

DECISION POINTS:
  - Decision CL-D1:
    Condition: a commit does not follow Conventional Commits.
    Branch A: flag it to AGT-09 (commit hygiene); classify it best-effort but note it.
    Default: A.
  - Decision CL-D2:
    Condition: a breaking change (feat!/BREAKING CHANGE) appears.
    Branch A: record it prominently (drives a major bump in release).
    Default: A.

ERROR HANDLING:
  - Error CL-E1: log range ambiguous → ask the orchestrator for the exact range.
  - Error CL-E2: CHANGELOG.md missing → create it with the standard header.

DEPENDENCIES:
  - Conventional Commit history (AGT-09). The release skill (AGT-09) consumes the
    Unreleased section. Fallback: classify best-effort + flag non-conforming commits.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Cutting the version / git tag / release notes → AGT-09 (release).
  - ADRs → adr-author (AGT-01). Site build → mkdocs-site (AGT-08).
  - Commits themselves → AGT-09.

SOURCES:
  - User requirements: Dossier §1 (S18 Conventional Commits + semver), §6.1 (AGT-08), §6.2 (changelog).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    Keep a Changelog + Conventional Commits conventions (grounded standards).
