---
name: ci-author
description: >
  GitHub Actions workflow author for the PixelArt Creator platform. Use it
  (invoked by AGT-09 GitHub/DevOps) to author/update .github/workflows/ci.yml so
  it runs the PySide6 test suite HEADLESS on Ubuntu (QT_QPA_PLATFORM=offscreen or
  xvfb + the xcb/EGL system libs), pins Python 3.12, runs Black/isort/flake8/mypy
  + pytest + the coverage gate (≥90/80) + path_portability_check, and uses a
  single-run concurrency guard (F11).
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
---

SKILL: ci-author
================================================================================

PURPOSE:
  Produce a reproducible GitHub Actions CI workflow that gates every PR: lint +
  type-check + headless PySide6 tests + coverage + path portability, pinned and
  concurrency-guarded so runs are deterministic and machine-agnostic (S13, F11).

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given pyproject.toml + the scripts it authors ci.yml unaided.

INPUTS:
  - pyproject.toml (deps + tool config, F14) and the P11 scripts
    (coverage_gate, path_portability_check) the CI must invoke.

OUTPUTS:
  - .github/workflows/ci.yml: triggers (push/PR), a single-run concurrency group,
    Python 3.12 setup, system-lib install for headless Qt (libxcb-*, libegl1,
    libgl1, libdbus-1-3), env QT_QPA_PLATFORM=offscreen (or xvfb-run), then
    black --check + isort --check + flake8 + mypy + pytest + coverage_gate + path_portability_check.

PRECONDITIONS:
  - pyproject.toml exists; the invoked scripts exist under scripts/.

PROCEDURE:
  1. Pin actions/setup-python to 3.12 (S8); cache pip.
  2. Install the headless Qt system libs on the Ubuntu runner and set
     QT_QPA_PLATFORM=offscreen (or wrap pytest in xvfb-run with a window manager) (F11).
  3. Add steps: `black --check`, `isort --check-only`, `flake8`, `mypy`, `pytest`
     (with coverage), then `python scripts/coverage_gate.py` (fails <90/80) and
     `python scripts/path_portability_check.py` (fails on non-portable paths).
  4. Add a concurrency group keyed on the ref to cancel superseded runs (single-run).
  5. Validate the YAML parses; confirm on disk; keep it consistent with the local
     pre-flight gate (same tools/versions AGT-03/AGT-05 run before "done").

DECISION POINTS:
  - Decision CA-D1:
    Condition: offscreen is insufficient for a UI test (needs a real platform).
    Branch A: switch that job to xvfb-run + a window manager (F11); keep the rest offscreen.
    Default: offscreen; escalate to xvfb only where required.
  - Decision CA-D2:
    Condition: branch protection will require named status checks (repo-provision).
    Branch A: give jobs STABLE names so branch-protection required_status_checks can
      reference them exactly.
    Default: A.

ERROR HANDLING:
  - Error CA-E1: CI fails to load the Qt plugin → add the missing xcb/EGL libs (F11).
  - Error CA-E2: coverage/lint tool version drift local vs CI → pin versions in
    pyproject to match (F14).

DEPENDENCIES:
  - pyproject.toml (F14); scripts/coverage_gate.py + scripts/path_portability_check.py.
  - Consumed by repo-provision (branch-protection required checks). Fallback: block
    if pyproject/scripts absent.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses the repo-root P11 scripts + standard tools).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Repo creation / branch protection / history hygiene → repo-provision (AGT-09).
  - Version tag / release notes → release (AGT-09). Code/tests → AGT-03/04/05/06.
  - pyproject authoring detail → AGT-09 (manifest) — ci-author consumes it.

SOURCES:
  - User requirements: Dossier §1 (S8, S13, S18), §6.1 (AGT-09), §6.2 (ci-author),
    §6.7 (CI/CD harness), §2 (F11/F14).
  - Official docs (via The Researcher, P1): pytest-qt headless CI (QT_QPA_PLATFORM
    offscreen / xvfb + xcb/EGL libs) — pytest-qt troubleshooting; GitHub Actions concurrency.
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row), spec-driven-development.md §5.
