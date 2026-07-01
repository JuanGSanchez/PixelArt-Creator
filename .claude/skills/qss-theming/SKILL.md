---
name: qss-theming
description: >
  Qt Style Sheet (QSS) theming skill for the PixelArt Creator platform. Use it
  (invoked by AGT-05 UI Expert) to author and apply matched light and dark QSS
  themes and a runtime theme switch, with colours defined once and referenced by
  role (never hard-coded per widget), so every widget renders correctly in both
  themes (AGT-06 verifies both).
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
    # P5 inherits AGT-05's context discipline; P10 inherits AGT-05's exit status.
---

SKILL: qss-theming
================================================================================

PURPOSE:
  Produce a light theme and a dark theme as QSS with a single applier, so the app
  can switch themes at runtime and every widget honours both — the two-theme
  requirement AGT-06 tests.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the widget set + a palette it emits both QSS themes + the applier unaided.

INPUTS:
  - The widget/object names needing styling; the brand/role palette (roles like
    background, surface, text, accent, canvas-grid).

OUTPUTS:
  - ui/ QSS assets (light + dark) and a theme applier (setStyleSheet on the app),
    colours defined once per role and referenced consistently; a switch slot.

PRECONDITIONS:
  - The widgets to theme exist (or their objectNames are known).

PROCEDURE:
  1. Define the role palette once for light and once for dark (same role keys).
  2. Write QSS selectors by class/objectName, referencing role colours — never a
     one-off literal buried in a widget's Python.
  3. Implement an applier that loads the chosen theme and calls setStyleSheet;
     expose a switch slot for the settings/menu.
  4. Ensure contrast is legible in both themes (AGT-06 a11y checks this).
  5. Verify both themes render the key widgets; hand to AGT-06 for the both-theme test.

DECISION POINTS:
  - Decision QT-D1:
    Condition: a widget needs a colour not in the role palette.
    Branch A: add a new role to BOTH palettes (light + dark), then reference it —
      never a single-theme literal.
    Default: A.
  - Decision QT-D2:
    Condition: the canvas grid overlay colour must contrast with painted pixels.
    Branch A: source the grid colour from a dedicated role; coordinate the exact
      value with AGT-10's render-strategy for the tile overlay.
    Default: A.

ERROR HANDLING:
  - Error QT-E1: a widget looks correct in one theme only → a hard-coded literal
    leaked in; move it to the role palette.
  - Error QT-E2: QSS selector does not match → verify objectName/class; QSS is
    case- and selector-sensitive.

DEPENDENCIES:
  - The widgets (widget-scaffold, AGT-05). AGT-06 verifies both themes.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Widget structure/logic → widget-scaffold (AGT-05) / AGT-03.
  - Colour-picking UX + harmonies → colour-hub. Canvas drawing → canvas-view.
  - a11y/contrast verification → AGT-06 (a11y-audit).

SOURCES:
  - User requirements: Dossier §1 (S8 PySide6), §6.1 (AGT-06 both-themes), §6.2 (qss-theming).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row),
    pyside6-qt6-best-practices; Qt Style Sheets docs (grounded).
