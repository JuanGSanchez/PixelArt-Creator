---
name: pytest-qt-harness
description: >
  UI/integration test harness skill for the PixelArt Creator platform. Use it
  (invoked by AGT-06 QA Expert) to write pytest-qt tests — one per acceptance
  criterion — that drive the PySide6 UI headlessly (QT_QPA_PLATFORM=offscreen),
  using the qtbot fixture, waiting on signals before asserting, and exercising
  BOTH light and dark themes. Deterministic and portable so it runs identically in
  CI (F11) and locally.
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
    # P5 inherits AGT-06's context discipline; P10 inherits AGT-06's exit status.
---

SKILL: pytest-qt-harness
================================================================================

PURPOSE:
  Produce pytest-qt UI/integration tests that verify each acceptance criterion of
  a UI feature headlessly and in both themes, with signal-before-assert timing so
  they are deterministic in CI.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the widget + its acceptance criteria it emits the pytest-qt module unaided.

INPUTS:
  - The UI widget/view under test (from AGT-05) + its acceptance criteria /
    Gherkin scenarios (from sdd-clarify via AGT-02).

OUTPUTS:
  - tests/ui/test_<widget>.py: qtbot-driven tests, one per acceptance criterion,
    run under QT_QPA_PLATFORM=offscreen, parametrised over light + dark themes,
    using qtbot.waitSignal / waitUntil before asserting.

PRECONDITIONS:
  - The widget exists + imports; pytest-qt available; offscreen platform usable.

PROCEDURE:
  1. Map each acceptance criterion to exactly one test (name it after the criterion).
  2. Use qtbot to instantiate + interact (mouseClick, keyClicks); wait on the
     relevant signal (qtbot.waitSignal) BEFORE asserting state — never sleep.
  3. Parametrise the theme fixture over light + dark (qss-theming applier) and
     assert the feature works in both.
  4. Force headless: set QT_QPA_PLATFORM=offscreen (conftest/session fixture) so no
     display is required; keep paths portable.
  5. If a criterion tied to S1/S2 (canvas paint) fails, mark it a sprint blocker
     and request AGT-09 open a GitHub issue (via the orchestrator).

DECISION POINTS:
  - Decision QH-D1:
    Condition: an interaction needs a real windowing platform (offscreen too limited).
    Branch A: use xvfb/pytest-xvfb with a window manager in CI (F11); keep the
      default local run offscreen.
    Default: offscreen; escalate to xvfb only when a test genuinely needs it.
  - Decision QH-D2:
    Condition: a test is flaky due to timing.
    Branch A: replace any sleep with waitSignal/waitUntil; if still flaky, isolate
      the nondeterminism (P2) — do not add retries.
    Default: A.

ERROR HANDLING:
  - Error QH-E1: "could not load Qt platform plugin" → ensure offscreen/xvfb + the
    xcb/EGL libs are present (CI installs them, F11).
  - Error QH-E2: a criterion has no widget affordance to test → return to AGT-05/02
    (missing feature or missing criterion).

DEPENDENCIES:
  - The widget (AGT-05); acceptance criteria (AGT-02); pytest-qt; qss-theming
    applier for the theme fixture. CI headless libs (AGT-09, ci-author).

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - logic/data tests → AGT-04 (pytest-scaffold). UI code → AGT-05.
  - Accessibility audit → a11y-audit (AGT-06, separate skill).
  - CI workflow authoring → AGT-09 (ci-author). Perf profiling → AGT-10.

SOURCES:
  - User requirements: Dossier §1 (S8 pytest-qt, S1/S2 blockers), §6.1 (AGT-06),
    §6.2 (pytest-qt-harness), §2 (F11 headless).
  - Official docs (via The Researcher, P1): pytest-qt headless / QT_QPA_PLATFORM
    offscreen + xvfb + xcb/EGL libs (pytest-qt troubleshooting).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row), pytest-best-practices.
