---
name: release
description: >
  Release-cutting skill for the PixelArt Creator platform. Use it (invoked by
  AGT-09 GitHub/DevOps) to cut a semver version: derive the bump (major/minor/patch)
  from the Conventional Commit types since the last tag, promote the CHANGELOG
  Unreleased section to that version + date, create the annotated git tag, and
  assemble release notes. Tagging/pushing is gated by a human checkpoint.
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
    # P5 inherits AGT-09's context discipline; P10 inherits AGT-09's exit status.
  custom:
    - id: C1
      name: Human checkpoint before tag/push
      requires: Creating/pushing a tag and publishing a release are user-visible + hard to undo — present the version + notes and get approval before tagging/pushing.
      rationale: P11 bound (irreversible/user-visible action needs a human checkpoint).
---

SKILL: release
================================================================================

PURPOSE:
  Turn merged work into a versioned release: compute the semver bump from commit
  types, finalize the CHANGELOG for that version, tag it, and write release notes —
  deterministically and with a human gate before the tag is pushed.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the commit range + CHANGELOG it computes the version + notes (pausing at
  the tag gate) unaided.

INPUTS:
  - The Conventional Commit range since the last tag; docs/CHANGELOG.md (Unreleased
    section from the changelog skill); the current latest tag.

OUTPUTS:
  - A chosen semver version; an updated CHANGELOG (Unreleased → vX.Y.Z + date); an
    annotated git tag vX.Y.Z; release notes (grouped, REQ-ID-cited).

PRECONDITIONS:
  - CI is green on the release commit; the CHANGELOG Unreleased section is current;
    user approval at the C1 gate.

PROCEDURE:
  1. Compute the bump: any BREAKING CHANGE/feat! → major; any feat → minor; only
     fix/refactor/docs → patch (semver, from the commit types since the last tag).
  2. Promote the CHANGELOG Unreleased section to the new version + today's date;
     leave a fresh empty Unreleased.
  3. Assemble release notes from that section (grouped Added/Changed/Fixed…).
  4. C1 gate: present version + notes; on approval, create the annotated tag
     `git tag -a vX.Y.Z -m ...` and push it; else stop.

DECISION POINTS:
  - Decision RE-D1:
    Condition: no user-facing commits since the last tag.
    Branch A: no release — report "nothing to release"; do not cut an empty version.
    Default: A.
  - Decision RE-D2:
    Condition: tagging/pushing (irreversible/user-visible) is next.
    Branch A: STOP for the C1 approval; only then tag + push.
    Default: A.

ERROR HANDLING:
  - Error RE-E1: CI not green → BLOCKED; do not release a red build.
  - Error RE-E2: version already exists → recompute from the true latest tag.

DEPENDENCIES:
  - The changelog skill's Unreleased section (AGT-08 CHANGELOG); Conventional Commit
    history (AGT-09); a green CI (ci-author). Fallback: block if CI red / CHANGELOG stale.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (uses git + semver reasoning over the commit log).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - CHANGELOG entry authoring → changelog (AGT-08). Repo/branch config → repo-provision.
  - CI workflow → ci-author (AGT-09). Code/tests → AGT-03..06.

SOURCES:
  - User requirements: Dossier §1 (S18 semver tags + Conventional Commits), §6.1 (AGT-09), §6.2 (release).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    Semantic Versioning + Conventional Commits (grounded standards).
