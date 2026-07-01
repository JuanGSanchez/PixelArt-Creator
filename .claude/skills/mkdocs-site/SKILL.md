---
name: mkdocs-site
description: >
  Documentation-site skill for the PixelArt Creator platform. Use it (invoked by
  AGT-08 Documenter) to build and maintain the mkdocs site under docs/site/ (nav,
  mkdocs.yml, API/usage pages from docstrings) and to run the pydocstyle gate over
  source docstrings so the published docs stay accurate. Writes only under AGT-08's
  docs/ subpaths — never the temporal checkpoint/gather files.
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
  custom:
    - id: C1
      name: docs/ subpath discipline
      requires: Write only under docs/site/, docs/adr/, docs/CHANGELOG.md, docs/SESSION_LOG.md; never touch checkpoint-*/gather-*/subagent-report-* or the design/build artifacts in docs/.
      rationale: Build Manifest Open-Item 4 (docs/ naming clash guard).
---

SKILL: mkdocs-site
================================================================================

PURPOSE:
  Produce a buildable mkdocs documentation site (navigation + pages sourced from
  docstrings) and enforce docstring quality with pydocstyle, keeping the docs a
  faithful, buildable reflection of the code.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the package + docstrings it produces mkdocs config/pages + runs the gate.

INPUTS:
  - The pixelart_creator/ package (docstrings) + any hand-written guide content.

OUTPUTS:
  - mkdocs.yml + docs/site/ pages (usage, architecture overview referencing
    STRUCTURE.md/ADRs, API reference); a pydocstyle report over source docstrings.

PRECONDITIONS:
  - mkdocs + pydocstyle available; the package exists with docstrings.

PROCEDURE:
  1. Run `pydocstyle` over pixelart_creator/; report missing/malformed docstrings
     (report-not-fix — code fixes route to AGT-03/AGT-05).
  2. Author/refresh mkdocs.yml nav + docs/site/ pages; pull API docs from docstrings.
  3. Build the site (`mkdocs build --strict`) to catch broken links/nav.
  4. Write only under the AGT-08 docs/ subpaths (C1); confirm on disk.

DECISION POINTS:
  - Decision MK-D1:
    Condition: pydocstyle reports gaps in source docstrings.
    Branch A: report them to AGT-03/AGT-05 via the orchestrator; do not edit their
      code (AGT-08 owns docs, not source).
    Default: A.
  - Decision MK-D2:
    Condition: `mkdocs build --strict` fails on a broken link.
    Branch A: fix the nav/link in docs/site/; re-build until strict passes.
    Default: A.

ERROR HANDLING:
  - Error MK-E1: mkdocs/pydocstyle not found → BLOCKED; request the doc toolchain.
  - Error MK-E2: a page would overwrite a temporal file → refuse (C1).

DEPENDENCIES:
  - mkdocs + pydocstyle (dev deps); the package docstrings (AGT-03/AGT-05).
  - CHANGELOG via changelog; ADRs via adr-author (linked in the nav).

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses mkdocs + pydocstyle).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Source docstring fixes → AGT-03/AGT-05. CHANGELOG → changelog (AGT-08).
  - Live session memory/summaries → AGT-M1 (Recaller). Commits/CI publish → AGT-09.

SOURCES:
  - User requirements: Dossier §1, §6.1 (AGT-08 mkdocs + pydocstyle), §6.2 (mkdocs-site);
    Build Manifest Open-Item 4 (docs/ subpath discipline).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    mkdocs + pydocstyle docs (grounded standards).
