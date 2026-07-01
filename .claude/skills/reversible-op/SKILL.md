---
name: reversible-op
description: >
  Reversible-operation pattern skill for the PixelArt Creator platform. Use it
  (invoked by AGT-03 Python Dev) to implement an editing operation in the logic/
  layer as a pure do/undo pair (apply + inverse, capturing the minimal prior
  state) so ui/commands.py can wrap it in a single QUndoCommand. The logic layer
  stays Qt-free; only ui/commands.py knows Qt (S11, C1, F1/FIX-05).
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
    # P5 inherits AGT-03's context discipline; P10 inherits AGT-03's exit status.
  custom:
    - id: C1
      name: Single undo system
      requires: The logic op exposes apply()/invert() only; the QUndoCommand wrapper lives in ui/commands.py — never a second undo stack in logic/.
      rationale: Dossier §9 C1; F1 (QUndoStack in QtGui); FIX-05.
---

SKILL: reversible-op
================================================================================

PURPOSE:
  Implement one editing operation as a deterministic, reversible logic-layer unit:
  an apply that mutates the pixel/project state and an invert that restores the
  captured prior state, so undo/redo is exact and Qt-free below ui/.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the operation's effect + the state it touches, it emits the do/undo pair.

INPUTS:
  - The operation description (what it changes) + the target state object
    (e.g. an RGBA buffer region, a palette entry).
  - logic/constants.py bounds (S12).

OUTPUTS:
  - A logic/ operation exposing apply(state) and invert(state) (or a captured
    inverse), capturing the MINIMAL prior state needed to undo (e.g. the previous
    pixel block, not the whole canvas — cf. F7 buffer size), fully typed + docstd.

PRECONDITIONS:
  - The target state's interface contract exists; the op is deterministic.

PROCEDURE:
  1. Identify the minimal state the op mutates and capture exactly that as the
     inverse payload (bounded memory — do not snapshot the full 8K buffer per op).
  2. Implement apply(state) → new/mutated state; implement invert to restore the
     captured prior state exactly (apply∘invert = identity).
  3. Keep it pure logic/: no Qt, numeric bounds from constants.py.
  4. Expose a stable signature for ui/commands.py to wrap in a QUndoCommand.
  5. Verify with a round-trip property (apply then invert restores input) — hand
     to AGT-04 for a Hypothesis strategy (hypothesis-strategy).

DECISION POINTS:
  - Decision RO-D1:
    Condition: capturing the full inverse is large (e.g. a flood fill).
    Branch A: capture a compact diff (changed indices + prior values) instead of a
      full-region copy; reconstruct on invert.
    Branch B (op is tiny): capture the direct prior value.
    Default: A when the affected region exceeds a small block; else B.
  - Decision RO-D2:
    Condition: the op would need a Qt type to be reversible.
    Branch A: redesign — reversibility is a logic property; Qt stays in ui/commands.py.
    Default: A (C1).

ERROR HANDLING:
  - Error RO-E1: apply∘invert not identity in a test → the inverse capture is
    incomplete; widen the captured state.
  - Error RO-E2: op is non-deterministic (depends on time/random) → make it pure
    or inject the varying input as a parameter (P2).

DEPENDENCIES:
  - numpy-buffer-ops (for pixel-region apply/invert) and logic/constants.py.
  - Consumed by ui/commands.py QUndoCommand wrappers (AGT-05).

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - The QUndoCommand class + undo stack wiring → AGT-05 (ui/commands.py).
  - Tests / property strategies → AGT-04 (pytest-scaffold, hypothesis-strategy).
  - Undo UX (menu, shortcuts) → AGT-05.

SOURCES:
  - User requirements: Dossier §1 (S7 command-pattern undo, S11/S12), §2 (F1/F7),
    §6.1 (AGT-03), §6.2 (reversible-op), §9 (C1).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    QUndoStack/QUndoCommand (QtGui) doc as the grounded undo model.
