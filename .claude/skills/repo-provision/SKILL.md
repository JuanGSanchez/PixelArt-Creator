---
name: repo-provision
description: >
  Repository provisioning + publication-hygiene skill for the PixelArt Creator
  platform (S18/S19). Use it (invoked by AGT-09 GitHub/DevOps) to create the
  private GitHub repo (gh repo create --private), maintain .gitignore, enforce the
  S19 history hygiene (docs/ + DEPLOYMENT.md gitignored AND purged from git history
  via git filter-repo, then force-push), and ATTEMPT branch protection on main via
  gh api (required PR review + required status checks) — degrading to CI-advisory
  when GitHub Free returns 403 (S18). Every irreversible git action is gated by a
  human checkpoint (P11 bound).
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
      name: Human checkpoint before irreversible git
      requires: Repo creation, history rewrite (git filter-repo), and force-push are IRREVERSIBLE — present the exact commands + effect and get explicit user approval before executing (never auto-run).
      rationale: P11 bound (no irreversible action without a human checkpoint); Dossier §6.3.
    - id: C2
      name: Publish/private boundary (S19)
      requires: .claude/, pixelart_creator/, scripts/, root CI files stay PUBLISHED; docs/ and DEPLOYMENT.md are gitignored AND purged from history.
      rationale: User req S19.
---

SKILL: repo-provision
================================================================================

PURPOSE:
  Stand up and harden the GitHub repository: create it private, keep the
  publish/private boundary (S19), purge private artifacts from history, and apply
  (or advisory-degrade) branch protection on main — all with a human gate before
  any irreversible step.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the repo name + the publish/private lists it runs the gh/git procedure
  (pausing at each irreversible gate) unaided.

INPUTS:
  - Repo name/owner (juangarciasanchez96@gmail.com account); the publish vs
    private path lists (S19); the CI job names to require (from ci-author).

OUTPUTS:
  - A private GitHub repo; a .gitignore covering docs/ + DEPLOYMENT.md (+ caches);
    rewritten history with docs/ + DEPLOYMENT.md removed; a branch-protection
    result (applied, or advisory-degraded with the 403 reason recorded).

PRECONDITIONS:
  - `gh` authenticated; `git filter-repo` available; user approval obtained at each
    C1 gate.

PROCEDURE:
  1. Ensure .gitignore lists docs/ and DEPLOYMENT.md (S19) plus caches; keep
     .claude/, pixelart_creator/, scripts/, ci.yml, pyproject.toml, .flake8,
     LICENSE, NOTICE published (C2).
  2. Create the repo: `gh repo create <owner>/<name> --private` (C1 gate first).
  3. History hygiene (C1 gate, IRREVERSIBLE): from a fresh clone run
     `git filter-repo --path docs --path DEPLOYMENT.md --invert-paths`, then
     `git push origin --force --all` (and `--tags`). Confirm the paths are gone from
     history before finishing.
  4. Branch protection (attempt): `gh api -X PUT /repos/<owner>/<name>/branches/main/protection`
     with required_pull_request_reviews + required_status_checks.strict=true and the
     ci-author job names in contexts[].
  5. If GitHub Free returns HTTP 403 (protection unavailable on private free tier),
     DEGRADE to CI-advisory: record the limitation, keep CI required-in-spirit, and
     note to revisit on Pro/public (S18). Report the outcome.

DECISION POINTS:
  - Decision RP-D1:
    Condition: an irreversible action (create/filter-repo/force-push) is next.
    Branch A: STOP, present the exact command + effect, wait for explicit user
      approval (C1); only then execute.
    Default: A (never auto-run an irreversible git action).
  - Decision RP-D2:
    Condition: `gh api` branch-protection returns 403 (Free-tier private).
    Branch A: degrade to CI-advisory + record the reason (S18); do not fail the build.
    Branch B (200): protection applied — record the ruleset.
    Default: A on 403, B on success.

ERROR HANDLING:
  - Error RP-E1: `git filter-repo` refuses (dirty tree) → run on a fresh clone
    (its requirement); never rewrite a dirty working repo.
  - Error RP-E2: `gh` not authenticated → BLOCKED; request auth (do not embed a token).

DEPENDENCIES:
  - `gh` CLI + `git filter-repo` (external tools). CI job names from ci-author.
    Fallback: if a tool is absent, BLOCK and report; never proceed unsafely.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (uses gh + git + git-filter-repo directly).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - The CI workflow content → ci-author (AGT-09). Version tags/notes → release (AGT-09).
  - Deciding WHAT is private → user requirement S19 (this skill enforces it).
  - Code/tests/docs → AGT-03..08.

SOURCES:
  - User requirements: Dossier §1 (S17, S18, S19), §6.1 (AGT-09), §6.2 (repo-provision), §2 (F12/F13).
  - Official docs (via The Researcher, P1): `gh repo create --private` (cli.github.com);
    branch-protection REST PUT /branches/{branch}/protection with required_status_checks +
    required_pull_request_reviews (docs.github.com); `git filter-repo --invert-paths` +
    force-push for history removal (docs.github.com removing-sensitive-data).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row), programmatic-determinism.md (irreversible-action bound).
