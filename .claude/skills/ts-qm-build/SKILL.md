---
name: ts-qm-build
description: >
  Translation compilation + LanguageManager wiring skill for the PixelArt Creator
  platform. Use it (invoked by AGT-07 Localisation) to compile the .ts catalogues
  to binary .qm with lrelease and wire the LanguageManager in ui/i18n.py that
  installs the right QTranslator by QLocale and triggers a live retranslate
  (widgets re-set text on QEvent.LanguageChange, F5/F6).
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
    # P5 inherits AGT-07's context discipline; P10 inherits AGT-07's exit status.
---

SKILL: ts-qm-build
================================================================================

PURPOSE:
  Turn source .ts catalogues into loadable .qm files and provide the runtime
  LanguageManager that selects a language by QLocale, installs the QTranslator,
  and prompts widgets to retranslate live.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the .ts set it compiles .qm + emits/updates ui/i18n.py LanguageManager.

INPUTS:
  - The i18n/*.ts catalogues (from string-extract) and the supported-locale list.

OUTPUTS:
  - Compiled i18n/*.qm files and pixelart_creator/ui/i18n.py LanguageManager:
    load(locale) installs the QTranslator, switch(locale) reinstalls + triggers a
    LanguageChange so hand-built widgets re-run their changeEvent retranslate (F5).

PRECONDITIONS:
  - lrelease available; the .ts catalogues exist and are current.

PROCEDURE:
  1. Run `lrelease` over each i18n/*.ts to produce the matching .qm.
  2. Implement/refresh ui/i18n.py LanguageManager: detect QLocale, resolve the .qm,
     QApplication.installTranslator; keep prior translator removal on switch.
  3. On switch, install the new translator and let the LanguageChange event drive
     each widget's changeEvent()-based retranslate (do not re-set text globally here).
  4. Confirm .qm files on disk; hand back to AGT-07 → AGT-06 for a language test.

DECISION POINTS:
  - Decision TQ-D1:
    Condition: a widget's text does not update on switch.
    Branch A: the widget lacks a changeEvent LanguageChange hook → report to AGT-05
      (widget-scaffold), not fixed here (AGT-07 does not edit widgets).
    Default: A.
  - Decision TQ-D2:
    Condition: a locale has no .qm (missing translation).
    Branch A: fall back to the source language via QLocale default; log the missing
      catalogue for translators.
    Default: A.

ERROR HANDLING:
  - Error TQ-E1: lrelease not found → BLOCKED; request the toolchain (F6).
  - Error TQ-E2: stale .qm (source .ts newer) → recompile before wiring.

DEPENDENCIES:
  - i18n/*.ts (string-extract, AGT-07); lrelease (F6); QLocale/QTranslator (Qt).
  - Widget retranslate hooks (AGT-05, widget-scaffold). Fallback: report missing hooks.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses lrelease).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Extracting/auditing source strings → string-extract (AGT-07).
  - Adding changeEvent hooks to widgets → AGT-05 (widget-scaffold).
  - Language tests → AGT-06 (pytest-qt-harness).

SOURCES:
  - User requirements: Dossier §1 (S8 i18n QLocale), §2 (F5/F6), §6.1 (AGT-07), §6.2 (ts-qm-build).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    lrelease + QTranslator/QLocale docs (grounded, F5/F6).
