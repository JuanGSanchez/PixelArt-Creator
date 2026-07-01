---
name: logic-scaffold
description: >
  Pure-Python logic/data module scaffolder for the PixelArt Creator platform.
  Use it (invoked by AGT-03 Python Dev) to create a new module under
  pixelart_creator/logic/ or pixelart_creator/data/ with the mandatory shape:
  module + function docstrings (PEP 257), all numeric parameters imported from
  logic/constants.py (never inlined, S12), typed signatures (PEP 484), domain
  exception classes, and ZERO Qt imports (S11).
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
      name: Zero-Qt logic
      requires: A logic/ or data/ module must contain no PySide6/Qt import; verified by check_layering afterwards.
      rationale: User req S11; Dossier §8 (layer-audit script backs it).
---

SKILL: logic-scaffold
================================================================================

PURPOSE:
  Emit a correctly-shaped, importable logic/ or data/ module skeleton so AGT-03
  fills in behaviour against a fixed structure — docstrings, constants sourced
  from constants.py, typed public functions, domain exceptions, no Qt.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the interface contract + the layer it produces a compliant module unaided.

INPUTS:
  - The interface contract (from interface-contract, AGT-01) or the tasks.md item.
  - logic/constants.py (numeric parameters, S12).

OUTPUTS:
  - A new pixelart_creator/logic/<mod>.py or data/<mod>.py: module docstring,
    imports (stdlib/NumPy/constants only for logic/), typed public functions with
    docstrings, domain exception class(es), no Qt import.

PRECONDITIONS:
  - Placement decided (layer-audit); logic/constants.py exists; a file_lock on the
    target path is held (acquired by the orchestrator).

PROCEDURE:
  1. Create the module with a one-paragraph module docstring stating its role +
     its layer (logic or data) and the S11 zero-Qt invariant.
  2. Import every numeric bound from logic.constants (e.g. MAX_CANVAS_WIDTH,
     TILE_SIZE); never write a magic number (S12).
  3. Define typed public function/class stubs per the interface contract, each
     with a PEP 257 docstring (Args/Returns/Raises).
  4. Define domain exception classes (subclass a project base, not bare Exception).
  5. Run `python scripts/check_layering.py --root pixelart_creator` (must be 0)
     and the local pre-flight (black/isort/flake8/mypy) before asserting done.

DECISION POINTS:
  - Decision LS-D1:
    Condition: the module needs a numeric parameter not in constants.py.
    Branch A: add it to logic/constants.py FIRST (UPPER_SNAKE_CASE), then import it.
    Default: A — never inline the literal (S12).
  - Decision LS-D2:
    Condition: the behaviour is a reversible edit feeding undo.
    Branch A: shape it via the reversible-op skill (do/undo pair); logic exposes
      reversible ops only — the QUndoCommand lives in ui/commands.py (C1 orch).
    Default: A.

ERROR HANDLING:
  - Error LS-E1: check_layering reports a Qt import → remove it; the module is not
    done while non-zero (C1).
  - Error LS-E2: interface contract missing → request it from AGT-01 (interface-contract).

DEPENDENCIES:
  - logic/constants.py (this or a sibling AGT-03 task). Fallback: extend it first.
  - scripts/check_layering.py (AGT-01). maxrects_compactor library where compaction
    is needed (pixelart_creator/logic/compactor.py, Dossier §6.5).

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/check_layering.py + the local pre-flight tools).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Qt widgets/undo command classes → AGT-05 (widget-scaffold; ui/commands.py).
  - Tests for the module → AGT-04 (pytest-scaffold).
  - Placement/architecture decision → AGT-01 (layer-audit / interface-contract).
  - RGBA pixel-buffer array ops → numpy-buffer-ops (still AGT-03, separate skill).

SOURCES:
  - User requirements: Dossier §1 (S11/S12), §6.1 (AGT-03), §6.2 (logic-scaffold), §8.
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row);
    PEP 257/PEP 484 as grounded docstring/typing standards; python-3.12-best-practices.
