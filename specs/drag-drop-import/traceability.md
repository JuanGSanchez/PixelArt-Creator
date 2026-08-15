# Traceability Matrix — Drag-and-Drop Import (REQ-NEW-A)

REQ-ID ↔ user requirement / dossier S-id ↔ layer/owner ↔ spec section ↔ Gherkin
scenario(s) ↔ test target.
**ID scheme (2026-07-30):** this feature owns the **`REQ-DDI-<LAYER>-<NNN>`** prefix. The 14 ids
below were re-allocated 1:1 (same order, requirement text unchanged) from the former
`REQ-P7-DATA-001..005` / `REQ-P7-UI-001..009`, which collided with `phase-7-export`'s own
allocation of that range — `phase-7-export` owns `REQ-P7-*` by name; a non-phase feature carries
its own prefix. Ids in the **Traces** column below are **citations** of other artifacts'
requirements (`REQ-NEW-A`, `REQ-P1-LOGIC-011` in §4) and deliberately keep their original ids.
**Mode:** IMPLEMENTED / PRE-COMMIT (updated 2026-07-03 by AGT-01) — code + tests are on disk; the
module + test columns now name the **actual shipped** paths (one test per scenario, Article IV).
Status: **built** (impl + ≥1 test on disk) · **spec-only** (gate/script/review-enforced, no unit
test). The pre-implementation indicative names (`data/palette_io.py`, `data/image_io.py`,
`tests/data/test_palette_io.py`, `tests/data/test_image_io.py`) were **superseded** at `sdd-plan`:
the palette parser is **REUSED** from `logic/palette_io.py` (only a thin `data/palette_import.py`
loader is new), and image decode is **QImage in `ui/image_import.py`** (ADR-0010), not `data/`.

Test module conventions (from Phase-1/2): data → `tests/data/test_<module>.py` (pytest +
Hypothesis); UI → `tests/ui/test_<widget>.py` (pytest-qt, both themes, headless).

## 1. Data layer (`REQ-DDI-DATA-001..005`) — owner AGT-03 (impl) / AGT-04 (tests)

| REQ-ID | Traces | Module (shipped) | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-DDI-DATA-001 | REQ-NEW-A; S7, S3; CL-A6 | `data/palette_import.py` `load_palette` (thin loader → **REUSED** `logic/palette_io.decode`) | §4.1, §11 | SC-D001-1..5 (SC-D001-4/-5 malformed/oversized) | `tests/data/test_palette_import.py` (+ existing `tests/logic/test_palette_io.py` parser) | built |
| REQ-DDI-DATA-002 | REQ-NEW-A; S1, S7; CL-A3 | `ui/image_import.py` `decode_image` (QImage → packed RGBA `PixelBuffer`; **ADR-0010** places Qt decode in `ui/`) | §4.1, §11 | SC-D002-1..6 (SC-D002-5 bounds, -6 corrupt) | `tests/ui/test_drag_drop_import.py` (`test_ui003_*`, pytest-qt headless) | built |
| REQ-DDI-DATA-003 | REQ-NEW-A; S7; CL-A1 | `data/file_import.py` `classify` + `FileType` (pure, Qt-free) | §4.1, §11 | SC-D003-1..2 ; SC-D003-3 (spec-only) | `tests/data/test_file_import.py` + `check_layering` | built / spec-only |
| REQ-DDI-DATA-004 | REQ-NEW-A; S7 (Art. VII) | **REUSED** `data/project_io.load_project` (via `ui/main_window` `.pixproj` branch) | §4.1, §11 | SC-D004-1..2 | `test_drag_drop_import.py::test_ui002_each_type_dispatched_to_its_branch` (the PROJECT branch is the shipped loader path), `::test_ui004_clean_document_opens_without_prompt`, `::test_ui004_discard_opens_without_saving`, `::test_ui004_save_persists_then_opens`, `::test_ui007_invalid_pixproj_shows_error_no_document_opened` (a `ProjectError` from the shipped loader surfaces per REQ-DDI-UI-007, with no partial open) + the loader's own suite `tests/data/test_project_io.py` | built (reuse) |
| REQ-DDI-DATA-005 | REQ-NEW-A; S7, Art. VII | `data/file_import.py` `FileImportError`/`PaletteImportError`/`ImageImportError` (Qt-free base family, ADR-0010) + defensive parse | §4.1, §11 | SC-D005-1 ; SC-D005-3 ; SC-D005-2 (spec-only/review) | `tests/data/test_file_import.py` + `tests/data/test_palette_import.py` | built / spec-only |

## 2. UI layer (`REQ-DDI-UI-001..009`) — owner AGT-05 (impl) / AGT-06 (tests, both themes)

| REQ-ID | Traces | Module (shipped) | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-DDI-UI-001 | REQ-NEW-A; S5, S7 | `ui/main_window.py` `setAcceptDrops`/`dragEnterEvent`/`dropEvent` | §4.2, §11 | SC-U001-1..2 (SC-U001-1 both themes) | `tests/ui/test_drag_drop_import.py` (`test_ui001_*`) | built |
| REQ-DDI-UI-002 | REQ-NEW-A; S7; CL-A1 | `ui/main_window.py` `_route_dropped_files` (dispatch by `data/file_import.classify`) | §4.2, §11 | SC-U002-1..2 | `tests/ui/test_drag_drop_import.py` (`test_ui002_*`) | built |
| REQ-DDI-UI-003 | REQ-NEW-A; S1, S5 | `ui/main_window.py` image branch → `ui/image_import.decode_image` + **enabler** `logic/document.Document.from_buffer` → **REUSED** `_add_document_tab` | §4.2, §11 | SC-U003-1..3 (SC-U003-1 not-a-layer, both themes; -3 read-only) | `tests/ui/test_drag_drop_import.py` (`test_ui003_*`) + `tests/logic/test_document_from_buffer.py` | built |
| REQ-DDI-UI-004 | REQ-NEW-A; S7; CL-A4 | `ui/main_window.py` dirty prompt (NEW) → **REUSED** `open_document`/`save_document` (`setClean`) | §4.2, §11 | SC-U004-1..5 (dirty-prompt Save/Discard/Cancel) | `tests/ui/test_drag_drop_import.py` (`test_ui004_*`) | built |
| REQ-DDI-UI-005 | REQ-NEW-A; S3, S7 (C1/F1); CL-A5 | `ui/main_window.py` palette branch → `data/palette_import.load_palette` + **enabler** `logic/palette.Palette.replace` → **REUSED** undoable path (`ui/commands`) | §4.2, §11 | SC-U005-1..5 (SC-U005-4 reversibility) | `tests/ui/test_drag_drop_import.py` (`test_ui005_*`) + `tests/logic/test_palette_replace.py` | built |
| REQ-DDI-UI-006 | REQ-NEW-A; S7; CL-A7 | `ui/main_window.py` notice surface | §4.2, §11 | SC-U006-1 (both themes) | `tests/ui/test_drag_drop_import.py` | built |
| REQ-DDI-UI-007 | REQ-NEW-A; S7, Art. VII | `ui/main_window.py` error surface (catches `(FileImportError, ProjectIOError)` family) | §4.2, §11 | SC-U007-1..4 (no-crash / state intact) | `tests/ui/test_drag_drop_import.py` | built |
| REQ-DDI-UI-008 | REQ-NEW-A; S7, S5; CL-A2 | `ui/main_window.py` `_route_dropped_files` multi-file (stable order, per-file guard) | §4.2, §11 | SC-U008-1..5 (SC-U008-4 last-palette-wins) | `tests/ui/test_drag_drop_import.py` | built |
| REQ-DDI-UI-009 | REQ-NEW-A; S5, F5/F6, Art. V | `ui/main_window.py` prompt/notice `tr()` strings + dialog | §4.2, §11 | SC-U009-2..3 ; SC-U009-1 (spec-only/gate) | `tests/ui/test_drag_drop_import.py` (both themes) + `string_audit_check` | built / spec-only |

## 3. Coverage summary (BUILT — pre-commit, 2026-07-03)

- **14 REQ-IDs**: 5 DATA (`REQ-DDI-DATA-001..005`) + 9 UI (`REQ-DDI-UI-001..009`).
- **14 specified / 14 with ≥1 impl / 14 with ≥1 test / 0 uncovered.** Every functional REQ maps to
  at least one shipped module **and** at least one on-disk test (SC-D003-3 / SC-D005-2 / SC-U009-1
  are gate/script/review-enforced *in addition* to their unit tests).
- **New test modules (95 tests):** `tests/data/test_file_import.py` (16), `tests/data/test_palette_import.py`
  (21), `tests/logic/test_palette_replace.py` (12), `tests/logic/test_document_from_buffer.py` (12),
  `tests/ui/test_drag_drop_import.py` (34). Plus reused existing `tests/logic/test_palette_io.py`
  (parser) and `tests/data/test_project_io.py` (`.pixproj` load).
- **Layering:** `check_layering` clean (31 modules), `check_cycles` clean (70 modules). QImage
  confined to `ui/image_import.py`; `data/file_import.py` + `data/palette_import.py` Qt-free
  (ADR-0010).
- **~40 Gherkin scenarios**: data SC-D001..005 + UI SC-U001..009. Headless
  (`QT_QPA_PLATFORM=offscreen`): data via pytest (+ Hypothesis for parser robustness / bounds),
  UI via pytest-qt in **both themes**.
- **Robustness (no-crash) acceptance** (NFR-9): SC-D001-4/-5, SC-D002-5/-6, SC-D005-1,
  SC-U006-1, SC-U007-1..4, SC-U008-3.
- **Reversibility acceptance** (NFR-5): SC-U005-1, SC-U005-4.
- **Non-destructive-on-disk acceptance** (NFR-6): SC-U003-3.
- **Bounds acceptance** (NFR-4): SC-D002-5, SC-U007-2.
- **Route-by-type acceptance** (CL-A1): SC-U002-1..2, SC-U003-1.
- **Spec-only** (gate/script/review-enforced, no unit test): SC-D003-3 (Qt-free purity via
  `check_layering`/`check_cycles`, Article I); SC-D005-2 (no `eval`/`exec`, review — Article VII);
  SC-U009-1 (`tr()` wrapping via `string_audit_check`, Article V); §9 "no new numeric constant" via
  review (Article II).

## 4. Notes for sdd-analyze (AGT-01)

- **Every REQ traces to REQ-NEW-A + an S-id** (S7 file I/O, S1 grid, S3 palette, S5 canvas) — no
  untraced REQ (Article X satisfied).
- **NEW vs REUSED (spec §1):** NEW = palette parser (DATA-001), image decoder (DATA-002),
  file-type classifier (DATA-003), file-URL drag/drop + routing + dirty prompt + notices
  (UI-001..009). REUSED = `.pixproj` load (DATA-004 → `project_io.load_project`), new-document/tab
  (UI-003 → `new_document`/`_add_document_tab`), undoable palette edit (UI-005 → `record.stack` +
  `ui/commands.py`), save (UI-004 Save → `save_document`).
- **AGT-01 to fix at plan time (HOW):** (a) palette-parser + image-decoder + classifier public
  APIs and final module names/placement; (b) the image-decode backend (QImage vs Pillow) and its
  Article-I-compliant layer (Qt decode → `ui/`, Qt-free → `data/`) — grounded by
  `docs/research-drag-drop-import.md`; (c) the dirty-state source (e.g. `QUndoStack.isClean()`);
  (d) whether a dropped `.pixproj` opens in a new tab (shipped `open_document` behaviour) or
  replaces the active doc — the dirty guard is specified regardless (CL-A4); (e) the shared
  import-error exception base (DATA-005).
- **Research dependency (HOW only):** `docs/research-drag-drop-import.md` (concurrent) grounds the
  `.gpl`/`.hex`/`.pal` grammars + decode approach. Spec does not block on it (fixes the WHAT).
- **Numerics (§9):** no new numeric constant expected — image bounds reuse `MAX_CANVAS_WIDTH/
  HEIGHT`; palette ceiling reuses the existing palette-size constant; extension sets are format
  identifiers (Article II governs numeric tuning, not format strings — per the 2026-07-02 ADR
  exemption). AGT-01 rules on the extension-set constant's home.
- **Forward-trace inheritance (FU-3):** this is the Phase-7 import slice; REQ-P1-LOGIC-011
  (compactor) and other Phase-7 forward traces from Phase-1 are export-side, not import-side — no
  inheritance required here.
- **Slicing** (§8): A-A data → A-B UI. A-A depends on the Researcher findings.
- **Clarifications** CL-A1..A7 recorded as category-1 defaults; **no SUSPEND** open.
