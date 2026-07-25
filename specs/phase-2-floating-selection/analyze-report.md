# Cross-Artifact Analyze Report — Floating-Selection Move/Copy (REQ-NEW-C)

**Feature:** phase-2-floating-selection · **Owner:** AGT-01 (Architecture)
**Gate:** SDD `analyze` — pre-commit run · **Date:** 2026-07-03
**Artifacts:** `constitution.md` · `spec.md` · `plan.md` · `tasks.md` (all present)
**Verdict:** **PASS** — zero unresolved cross-artifact findings.

---

## 1. Scope of this run

Final pre-commit consistency pass over the REQ-C floating-selection slice, after the
Ctrl-only **CL-F5** reconciliation. Confirms spec ↔ plan ↔ impl ↔ tests agree and the
layering/cycle gates are green.

## 2. Layering & cycle gates (Article I)

| Check | Result | Exit |
| --- | --- | --- |
| `python scripts/check_layering.py` | `clean (29 modules)` | 0 |
| `python scripts/check_cycles.py` | `no cycles (67 modules)` | 0 |

- `logic/` and `data/` are **Qt-free** (grep for `PySide6`/`PyQt`/`Qt` over both trees → 0
  hits). `logic/selection.py` floating surface (`FloatMode`, `FloatingSelection`,
  `lift_selection`, `composite_preview`, `copy_selection`, `commit_floating`) is pure Python.
- New `ui/tools/floating_move.py` imports Qt (`QUndoStack`) and the logic surface only; the
  `base → floating_move` seam is kept **acyclic** by a `TYPE_CHECKING` `LiftContext` `Protocol`
  (structural typing — no `ui/tools/base` import), which is what cleared the earlier cycle.
- `canvas_scene._FloatingPreviewItem` (float item + `_ORIGIN_Z` origin item) and
  `_origin_vacate(...)` are UI-only; no domain math leaked into the scene.

## 3. C1 consistency — Ctrl-only copy modifier (CL-F5)

Three-way agreement confirmed after the reconciliation:

| Layer | Evidence | COPY | Subtract |
| --- | --- | --- | --- |
| spec | `spec.md` §CL-F5, §4.2, US-F2 | **Ctrl only** (not Alt) | Alt = shipped CL-4 build subtract |
| impl | `selection_base.py:34` `_COPY_MODIFIERS = ControlModifier`; `floating_move.py` docstring + `update`; `canvas_view.py:405` re-samples Ctrl per move | **Ctrl** | `selection_base.py:72/89` Alt → subtract path |
| tests | `test_floating_selection.py` SC-U032-1/-2/-3 (`CTRL` = COPY; Alt not a copy trigger) | **Ctrl** | Alt subtract verified in `test_rect_select_tool.py` |

No modifier collision: Ctrl (previously free) carries copy-float; Shift = add, Alt = subtract
(shipped, unchanged). The earlier Alt→copy collision that regressed 4 shipped tests is gone.
→ **C1: PASS.**

## 4. Coverage / traceability (Article IV / X)

- **14 REQ-IDs**: 7 LOGIC (`REQ-P2-LOGIC-030..036`) + 7 UI (`REQ-P2-UI-030..036`).
- **14 impl / 14 tested / 0 uncovered.** `traceability.md` updated to BACKWARD mode with the
  on-disk test targets; every REQ maps to ≥1 impl + ≥1 passing test.
- **84 tests pass** headless (`tests/logic/test_floating_selection.py` +
  `tests/ui/test_floating_selection.py`), incl. Hypothesis non-destructive (NFR-3) and
  reversibility (NFR-4, `apply∘undo = identity`) invariants and both-theme UI checks.
- SC-L036-3 stays gate-enforced (spec-only) via `check_layering`/`check_cycles`.

## 5. Constitution / grounding notes

- **Article II (constants):** no new `constants.py` scalars — RGBA vacate = `color.TRANSPARENT`,
  indexed vacate = index 0 (existing convention, CL-F2). Consistent across spec/impl.
- **Article I (layering):** clean (see §2).
- **ADR-0008** (Document.mode single authority) respected by indexed vacate / active-layer scope.
- **ADR-0009** (floating-selection non-destructive preview) governs the design: base buffer is
  never written pre-commit; commit is exactly one `LogicCommand`; cancel is a pure no-op.
- No Researcher dependency (all primitives shipped).

## 6. Findings

**None unresolved.** Gate stays **OPEN → PASS**; slice is clear for commit.
