---
name: widget-scaffold
description: >
  PySide6 widget/view scaffolder for the PixelArt Creator platform. Use it
  (invoked by AGT-05 UI Expert) to create a ui/ widget or view class following
  the naming CONVENTIONS (PascalCase + _Widget/_View/_Panel/_Dialog), with
  tr()-wrapped user-visible strings and a changeEvent() override that re-sets text
  on QEvent.LanguageChange (F5), and NO domain logic in the widget — it binds to
  the logic/ layer. Presentation + Qt wiring only.
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
      name: No logic in widgets
      requires: The widget contains presentation + signal/slot wiring only; all computation is called from logic/ (AGT-03). Every user-visible string uses tr(); changeEvent() re-applies text on LanguageChange.
      rationale: User req S11; Dossier §2 F5; §9 C1.
---

SKILL: widget-scaffold
================================================================================

PURPOSE:
  Emit a correctly-shaped ui/ widget/view class: right base class, CONVENTIONS
  name, tr()-wrapped labels, a changeEvent() LanguageChange retranslate hook, and
  signals/slots that delegate all behaviour to the logic/ layer.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the widget's role + the logic API it binds to, it emits the class unaided.

INPUTS:
  - The widget's role + which logic/ API it calls (from AGT-03 / tasks.md).
  - pyside6-qt6-best-practices instruction (loaded just-in-time).

OUTPUTS:
  - A pixelart_creator/ui/<mod>.py class named per CONVENTIONS
    (PascalCase + suffix), with __init__ building the UI, a _retranslate() method
    called from __init__ and from changeEvent() on QEvent.LanguageChange, tr()
    on every user-visible string, and slots that call logic/ (no computation here).

PRECONDITIONS:
  - The logic/ API exists; a file_lock on the ui/ path is held; placement decided.

PROCEDURE:
  1. Pick the base class (QWidget/QDialog/QGraphicsView…) and the CONVENTIONS name.
  2. Build the UI in __init__; route all text through a single _retranslate()
     method so LanguageChange can re-apply it.
  3. Override changeEvent(): on QEvent.LanguageChange call _retranslate() then
     super().changeEvent(event) (F5 — hand-built widgets have no auto retranslateUi).
  4. Wire signals to slots that CALL the logic/ layer; keep zero computation in the
     widget (C1).
  5. Run the local pre-flight + `python scripts/string_audit_check.py <file>` (must
     be clean) before asserting done.

DECISION POINTS:
  - Decision WS-D1:
    Condition: the widget is the 8K canvas view or the colour picker.
    Branch A: defer to canvas-view / colour-hub (specialised skills) — this skill
      scaffolds generic panels/dialogs/toolbars, not those two.
    Default: A.
  - Decision WS-D2:
    Condition: a slot needs domain computation.
    Branch A: call the logic/ function; if it does not exist, request it from
      AGT-03 (do not compute in the widget, C1).
    Default: A.

ERROR HANDLING:
  - Error WS-E1: string_audit_check reports unwrapped strings → wrap them in tr();
    not done while findings remain.
  - Error WS-E2: logic API missing → BLOCKED; request AGT-03 build it.

DEPENDENCIES:
  - The logic/ API (AGT-03); pyside6-qt6-best-practices; scripts/string_audit_check.py.
  - Theming via qss-theming; canvas + colour picker via canvas-view / colour-hub.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/string_audit_check.py).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Domain computation → AGT-03 (logic/). Render-perf strategy → AGT-10.
  - The 8K QGraphicsView canvas → canvas-view; the colour picker → colour-hub.
  - QSS themes → qss-theming. Catalogue (.ts/.qm) + LanguageManager → AGT-07.
  - UI tests → AGT-06.

SOURCES:
  - User requirements: Dossier §1 (S11), §2 (F5/F6), §6.1 (AGT-05), §6.2 (widget-scaffold), §9 C1.
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row),
    pyside6-qt6-best-practices; Qt tr()/changeEvent i18n docs (grounded).
