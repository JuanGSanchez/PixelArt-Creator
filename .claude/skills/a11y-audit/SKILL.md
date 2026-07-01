---
name: a11y-audit
description: >
  Accessibility audit skill for the PixelArt Creator platform. Use it (invoked by
  AGT-06 QA Expert) to audit the PySide6 UI against Qt accessibility expectations:
  accessible name/description on interactive widgets, keyboard reachability and
  tab order, focus visibility, and colour-contrast legibility in both light and
  dark themes. Report-and-verify — it lists findings + the criterion each maps to;
  AGT-05 fixes them.
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

SKILL: a11y-audit
================================================================================

PURPOSE:
  Check the UI for accessibility gaps — missing accessible names, unreachable-by-
  keyboard controls, bad tab order, invisible focus, low contrast in either theme —
  and report each finding with the widget and the fix owner.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the widget set + both themes it produces an a11y findings report unaided.

INPUTS:
  - The UI widgets/views (from AGT-05) and both QSS themes (from qss-theming).

OUTPUTS:
  - An a11y findings report: {widget, issue, Qt a11y expectation, theme, severity}
    + a pass/fail summary per checked dimension. Handed to AGT-05 for fixes.

PRECONDITIONS:
  - The widgets exist and can be instantiated (offscreen ok for structural checks).

PROCEDURE:
  1. Interactive-widget check: every actionable control has setAccessibleName /
     setAccessibleDescription (and those strings are tr()-wrapped).
  2. Keyboard check: every control is reachable and operable by keyboard; tab order
     is logical; focus is visible.
  3. Contrast check: text/icon vs background meets a legibility threshold in BOTH
     light and dark themes (coordinate values with qss-theming).
  4. Assemble the findings report (map each to an acceptance criterion where one
     exists); return to AGT-06 → AGT-05 for fixes (report-not-fix).
  5. Re-audit after fixes until the checked dimensions pass.

DECISION POINTS:
  - Decision AU-D1:
    Condition: a control cannot be made keyboard-reachable without redesign.
    Branch A: raise it as a design finding to AGT-05/AGT-01 (not a trivial fix).
    Default: A.
  - Decision AU-D2:
    Condition: contrast fails only in one theme.
    Branch A: report against that theme's role colour → qss-theming adjusts the role.
    Default: A.

ERROR HANDLING:
  - Error AU-E1: accessible name is present but untranslated → also flag to AGT-07
    (string audit) — it is both an a11y and an i18n finding.
  - Error AU-E2: widget cannot instantiate → BLOCKED; the UI is not ready.

DEPENDENCIES:
  - The widgets (AGT-05); both themes (qss-theming). Fixes route to AGT-05.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Fixing the widgets → AGT-05. Functional UI tests → pytest-qt-harness (AGT-06).
  - Theme colour definitions → qss-theming (AGT-05). String wrapping → AGT-07.

SOURCES:
  - User requirements: Dossier §6.1 (AGT-06 a11y + both themes), §6.2 (a11y-audit).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    Qt Accessibility docs (QAccessible / setAccessibleName) as the grounded standard.
