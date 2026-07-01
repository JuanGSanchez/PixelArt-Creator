---
name: colour-hub
description: >
  Right-click colour hub skill for the PixelArt Creator platform (S3/S4). Use it
  (invoked by AGT-05 UI Expert) to build the contextual colour menu anchored at
  the cursor with two pick paths: a persisted, user-managed Favourites list
  (add/remove/reorder) and a Canva-style RGB colour wheel that shows live
  colour-theory harmonies (complementary +180°, analogous ±30°, triadic ±120°,
  split-complementary ±150°, plus shade/tint ramps) using QColor HSV APIs. The
  picked colour applies immediately and/or saves to Favourites; the active swatch
  reflects it. UI only — the harmony MATH lives in AGT-03 logic (F9).
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
  custom:
    - id: C1
      name: UI here, harmony math in logic
      requires: The wheel/menu widgets render + emit selections; the harmony geometry (hue rotations, shade/tint ramps) is computed by AGT-03 logic (grounded F9) and consumed here — no colour-theory math duplicated in the widget.
      rationale: Dossier §2 F9; §3 delegation (harmony logic → AGT-03); §6.1 (AGT-05 wheel widget).
---

SKILL: colour-hub
================================================================================

PURPOSE:
  Build the S3 right-click contextual colour menu: Favourites management + a live
  RGB colour wheel that highlights theory-based related colours as the user picks,
  applying the choice to the active swatch and/or Favourites (S4).

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the AGT-03 harmony API + the Favourites persistence API it builds the menu.

INPUTS:
  - The AGT-03 colour-harmony logic API (given a base colour → complementary/
    analogous/triadic/split-complementary sets + shade/tint ramps), grounded by F9.
  - The Favourites persistence API (data/ layer: load/save/reorder saved colours).
  - The active-swatch state.

OUTPUTS:
  - pixelart_creator/ui/ colour widgets (CONVENTIONS names): a contextual menu/
    dialog anchored at the cursor; a Favourites list widget (add/remove/reorder);
    an RGB colour-wheel widget rendering hue/saturation with a live harmony overlay;
    signals: colourPicked(QColor), favouriteAdded/Removed/Reordered. All strings tr().

PRECONDITIONS:
  - The AGT-03 harmony API + the Favourites persistence API exist; F9 grounding is
    present; a file_lock on the ui/ path is held.

PROCEDURE:
  1. Build the contextual menu anchored at the right-click position (from
     canvas-view's colourMenuRequested signal, S3).
  2. Favourites path (S3a): list widget bound to the persistence API; add the
     active colour, remove, and drag/reorder; persist on change.
  3. Colour-wheel path (S3b): render an RGB wheel (a custom QWidget using a conical/
     radial gradient, or QColorDialog where a standard picker suffices — choose per
     F9). Represent colours with QColor and its HSV APIs (fromHsvF/getHsvF; integer
     hue() is 0..359, float hueF() 0.0..1.0).
  4. On a base pick, CALL the AGT-03 harmony API and overlay the returned related
     colours live (complementary +180°, analogous ±30°, triadic ±120°,
     split-complementary ±150°, shade/tint ramps) — do NOT compute the geometry in
     the widget (C1).
  5. Apply the pick to the active swatch immediately and/or save to Favourites (S4);
     emit colourPicked. Run string_audit_check + pre-flight before done.

DECISION POINTS:
  - Decision CH-D1 (colour-wheel realization, mirrors AGT-05 Decision A5-D2):
    Condition: F9 recommends QColorDialog/QColor HSV vs a custom QWidget wheel.
    Branch A (grounded recommendation present): implement per F9.
    Branch B (absent): BLOCKED — request The Researcher via the orchestrator; do
      not guess the wheel geometry or the HSV API.
    Default: B.
  - Decision CH-D2:
    Condition: the harmony math is needed but the AGT-03 API is absent.
    Branch A: BLOCKED — request AGT-03 build the harmony logic; never inline the
      colour-theory math in the widget (C1).
    Default: A.

ERROR HANDLING:
  - Error CH-E1: string_audit_check finds unwrapped labels → wrap in tr().
  - Error CH-E2: Favourites persistence API missing → request the data/ layer from
    AGT-03 before wiring add/remove/reorder.

DEPENDENCIES:
  - AGT-03 harmony logic API (grounded F9) + Favourites persistence (data/, AGT-03).
  - pyside6-qt6-best-practices; scripts/string_audit_check.py; canvas-view's
    right-click signal. Fallback: block until the harmony API + F9 exist.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/string_audit_check.py).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Colour-theory harmony MATH + Favourites persistence → AGT-03 (logic/data). This
    skill is UI only (C1).
  - The canvas grid/paint → canvas-view. QSS theme colours → qss-theming.
  - Tests / a11y of the picker → AGT-06. Catalogue strings → AGT-07.

SOURCES:
  - User requirements: Dossier §1 (S3, S3a, S3b, S4), §3 (harmony logic → AGT-03),
    §6.1 (AGT-05 colour-wheel widget), §6.2 (colour-hub), §9.
  - Official docs (via The Researcher, P1): QColor HSV APIs (fromHsvF/getHsvF,
    hue 0-359) + QColorDialog (doc.qt.io/qtforpython-6 QColor); colour-theory
    harmony angles (complementary/analogous/triadic/split-complementary) per F9.
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row), pyside6-qt6-best-practices.
