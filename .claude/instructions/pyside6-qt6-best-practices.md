INSTRUCTION: pyside6-qt6-best-practices
================================================================================

TARGET:
  The coding agents that write or modify PySide6/Qt6 code — AGT-05 (ui, primary),
  AGT-07 (i18n hooks), AGT-06 (pytest-qt tests) — loaded just-in-time when they
  touch Qt.

PURPOSE:
  Enforce idiomatic, maintainable, accessible PySide6/Qt6 conventions for the 8K
  canvas UI, colour tools, undo system, and internationalisation.

## Principles Applied

Inherited:
- P1 — Source-of-Truth Grounding (directives trace to Qt for Python docs via Researcher)
- P2 — Full Determinism (fixed idioms for signals/slots, scene/view, i18n)
- P3 — Systematicity (grouped directive structure)
- P4 — Consistency (one Qt standard across the UI)
- P6 — Self-Containment (agents cite this; do not restate Qt docs)
- P7 — Reference Hygiene (cites real Qt APIs + FIX-IDs)
- P9 — Role Separation (TARGET names the Qt-touching agents)
- P12 — Maximal-Effort Completeness (all six groups; extensible to later phases)
- P13 — Token Economy

Custom: (none)

DIRECTIVES (grouped):
  - Idiomatic conventions: import QUndoStack/QUndoCommand from PySide6.QtGui (moved from
    QtWidgets in Qt6 — F1). Connect signals with the new-style functional syntax
    (obj.signal.connect(slot)); prefer @Slot-decorated slots. Keep widget classes thin
    (presentation + wiring); call domain behaviour from logic/ (no logic in widgets, S11).
    Widget classes use PascalCase + suffix (_Widget/_View/_Panel/_Dialog).
  - Project structure & layout: all Qt code under ui/; the sole Qt file's exception is
    ui/commands.py (QUndoCommand wrappers, the single undo system — C1/F1/FIX-05).
    Draw the tiled grid in QGraphicsScene.drawBackground(painter, rect) — rect is the
    exposed region in scene coords (F2); the view owns zoom/pan/input. Call
    scene.setSceneRect(0,0,W,H) explicitly at init for the large scene (F3).
  - Testing: UI is tested with pytest-qt (qtbot), headless (QT_QPA_PLATFORM=offscreen);
    connect signal observers (qtbot.waitSignal) BEFORE the triggering action; use qtbot for
    widget lifecycle. Details: pytest-best-practices.
  - Security: validate any file-derived content before rendering; never build a widget from
    untrusted markup; guard against unbounded canvas sizes (clamp to MAX_CANVAS_WIDTH/HEIGHT).
  - Performance: keep paint paths under FRAME_BUDGET_MS (16 ms); only cull QGraphicsPixmapItem
    rendering, not the resident 8K RGBA buffer (F7); use a QOpenGLWidget viewport and tune
    setBspTreeDepth only as AGT-10 directs (F4); do partial/dirty-rect redraws. AGT-10 owns
    the strategy and the perf_profile verdict; AGT-05 implements the directives.
  - Tooling: same black/isort/flake8/mypy gates as Python; i18n via pyside6-lupdate (NOT
    pylupdate6, F6) + lrelease + QLocale; every user-visible string wrapped in self.tr(...)
    and audited by string_audit_check; hand-built widgets override changeEvent() to re-set
    text on QEvent.LanguageChange (F5).

CONSTRAINTS:
  - Never put business logic or numeric constants in a widget (S11/S12).
  - Never import Qt into logic/ or data/.
  - Never concatenate translated strings with '+' (breaks word order) — use tr() with
    placeholders (%1) instead.
  - Never create a second undo system — QUndoStack in ui/commands.py is the only one (C1).

EXAMPLES:
  Positive (do this):
    Input:  a paint action on the canvas.
    Output: class PaintCommand(QUndoCommand):  # in ui/commands.py
                def redo(self): self._apply()
                def undo(self): self._revert()
            — single undo system, reversible, logic ops called from logic/.

  Negative (do not do this):
    Input:  label.setText("Colour: " + tr("wheel"))
    Output: WRONG — concatenates a translated fragment (breaks i18n order) and leaves
            "Colour: " unwrapped. RIGHT: label.setText(self.tr("Colour: %1").arg(name)).

SOURCES:
  - Official documentation (grounded via The Researcher, F9): Qt for Python docs —
    QUndoStack/QUndoCommand (QtGui), QGraphicsScene.drawBackground/setSceneRect,
    QGraphicsView, QOpenGLWidget, setBspTreeDepth, QColor/QColorDialog, tr()/i18n, resource system.
  - User requirements: Dossier §1 (S1–S5,S8,S11,S12), §2 (F1–F7,F9), §6.8, §9 C1/C2.
  - Inner assets: asset-templates.md §Instruction (Best-Practices variant),
    spec-driven-development.md §4, principles.md §3 (instruction row).
