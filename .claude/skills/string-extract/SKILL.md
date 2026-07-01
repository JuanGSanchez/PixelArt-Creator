---
name: string-extract
description: >
  Translatable-string extraction skill for the PixelArt Creator platform. Use it
  (invoked by AGT-07 Localisation) to audit changed ui/ files for user-visible
  strings not wrapped in tr()/translate() (via the string_audit_check script,
  report-not-fix) and to extract the wrapped strings into .ts catalogues with
  pyside6-lupdate — the correct PySide6 tool (F6, not pylupdate6).
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
  custom:
    - id: C1
      name: Audit before extract, report-not-fix
      requires: Run string_audit_check on changed ui/ first; report unwrapped strings to AGT-05 (do not edit widgets); extract only after they are wrapped.
      rationale: Dossier §6.1 (AGT-07 report-not-fix) + §6.5 (string_audit_check).
---

SKILL: string-extract
================================================================================

PURPOSE:
  Keep the translation catalogues current: detect unwrapped user-visible strings
  in changed ui/ code (report them for AGT-05 to wrap) and run pyside6-lupdate to
  update the .ts source catalogues from the wrapped strings.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the changed ui/ files it audits + updates the .ts catalogues unaided.

INPUTS:
  - The changed ui/ files (from AGT-05 outputs) and the i18n/ catalogue set.

OUTPUTS:
  - A string-audit report (unwrapped strings / tr-concatenations) for AGT-05, and
    updated i18n/*.ts catalogues (source strings for translators).

PRECONDITIONS:
  - pyside6-lupdate available; the ui/ files exist; the i18n/ path is decided.

PROCEDURE:
  1. Run `python scripts/string_audit_check.py <changed ui files>`; exit 0 clean,
     1 findings, 2 error. On findings, report them to AGT-05 and STOP extraction
     until they are wrapped (C1, report-not-fix).
  2. When clean, run `pyside6-lupdate` (F6 — NOT pylupdate6) over the ui/ sources
     to update the i18n/*.ts catalogues.
  3. Confirm the .ts files updated on disk; hand off to ts-qm-build for compilation.

DECISION POINTS:
  - Decision SE-D1:
    Condition: string_audit_check exits 1 (unwrapped strings found).
    Branch A: return the findings JSON to AGT-05 (via orchestrator); do not wrap the
      strings yourself (AGT-07 does not edit widget code).
    Default: A.
  - Decision SE-D2:
    Condition: a new language is requested.
    Branch A: create its .ts via pyside6-lupdate with the new locale; wire the .qm
      build through ts-qm-build.
    Default: A.

ERROR HANDLING:
  - Error SE-E1: pyside6-lupdate not found → BLOCKED; request the toolchain (F6).
  - Error SE-E2: string_audit_check exits 2 → report the error; unblock the source.

DEPENDENCIES:
  - scripts/string_audit_check.py (Dossier §6.5); pyside6-lupdate (F6).
  - Compilation + LanguageManager wiring → ts-qm-build (AGT-07). Fixes → AGT-05.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/string_audit_check.py + pyside6-lupdate).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Wrapping strings in widget code → AGT-05 (widget-scaffold).
  - Compiling .ts → .qm + LanguageManager → ts-qm-build (AGT-07).
  - Documentation strings → AGT-08.

SOURCES:
  - User requirements: Dossier §1 (S8 i18n), §2 (F5/F6), §6.1 (AGT-07), §6.2 (string-extract),
    §6.5 (string_audit_check), §6.6 (string-audit disposition).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    pyside6-lupdate tool doc (grounded, F6).
