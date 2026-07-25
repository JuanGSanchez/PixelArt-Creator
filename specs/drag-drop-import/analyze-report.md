# Analyze Report — Drag-and-Drop Import (REQ-NEW-A)

| Field | Value |
| --- | --- |
| Feature | `drag-drop-import` |
| Phase | SDD `analyze` — final pre-commit gate |
| Owner | AGT-01 (Architecture) |
| Date | 2026-07-03 |
| Artifacts | `constitution.md`, `spec.md`, `plan.md`, `tasks.md`, `traceability.md` (all present) |
| Verdict | **PASS** — zero unresolved cross-artifact findings; layering/cycle clean; 0 uncovered REQ |

---

## 1. Deterministic gates (source of truth, P11)

| Check | Command | Result |
| --- | --- | --- |
| Layering | `python scripts/check_layering.py` | **exit 0** — `check_layering: clean (31 modules).` |
| Cycles | `python scripts/check_cycles.py` | **exit 0** — `check_cycles: no cycles (70 modules).` |

No new import cycle introduced by the drag-drop slice. No `logic/`→Qt or `data/`→Qt leak.

## 2. Article I — three-layer purity (Qt confinement)

- **QImage confined to `ui/image_import.py`** (the only new Qt consumer; imports
  `from PySide6.QtGui import QImage`, decodes to packed `Format_RGBA8888`, hands `logic` a
  Qt-free `PixelBuffer` — no Qt object crosses the boundary). Grounded by **ADR-0010**.
- **`data/file_import.py` — Qt-free.** The single `QImage` token in the file is a **docstring
  reference** (`file_import.py:79`, documenting that `ImageImportError` is raised from the `ui/`
  decoder), not an import. Confirmed by grep over `data/` + `logic/`.
- **`data/palette_import.py` — Qt-free.** Delegates to `logic.palette_io.decode` (import at
  `palette_import.py:28`); no Qt.
- Error family (`FileImportError`/`PaletteImportError`/`ImageImportError`) is **defined in the
  Qt-free `data/file_import.py`**; `ImageImportError` is *raised from* `ui/image_import.py`
  (an exception class carries no Qt) — keeping the whole family catchable as one base (ADR-0010 §3).

## 3. C1 consistency (spec ↔ impl ↔ tests)

| Concern | Spec / plan | Impl (shipped) | Test | Consistent |
| --- | --- | --- | --- | --- |
| Palette parser is REUSED | spec §1 REUSED table; STRUCTURE Phase-7 | `data/palette_import.load_palette` → `logic.palette_io.decode` (no re-implementation) | `tests/data/test_palette_import.py` + existing `tests/logic/test_palette_io.py` | ✅ |
| Image decode = QImage in `ui/` (ADR-0010) | ADR-0010 §Decision 1; plan §4 | `ui/image_import.decode_image` (QImage → `Format_RGBA8888`, `bytesPerLine` stride-safe) | `tests/ui/test_drag_drop_import.py` `test_ui003_*` (headless pytest-qt) | ✅ |
| Image bounds vs `MAX_CANVAS_*`, first-frame GIF | ADR-0010 §Decision 2 | `decode_image` bounds-checks before alloc; GIF first frame | `test_ui003_first_frame_of_multiframe_gif`, bounds via `ImageImportError` | ✅ |
| Image → NEW tab, not layer | spec §1; CL-A | `main_window` image branch → `Document.from_buffer` → `_add_document_tab` | `test_ui003_image_opens_new_tab_not_layer` | ✅ |
| Palette load reversible (one undo step) | spec §1 (C1/F1); CL-A5 | `Palette.replace` + reused `ui/commands` over tab `QUndoStack` | `test_ui005_reversibility_undo_restores_prior_palette` + `tests/logic/test_palette_replace.py` | ✅ |
| `.pixproj` drop → dirty Save/Discard/Cancel guard | spec §1; CL-A4 | `main_window` `.pixproj` branch → reused `open_document`/`save_document` (`setClean`) | `test_ui004_*` (5 tests) | ✅ |
| Route by TYPE not location; multi-file stable order | spec §2; CL-A1/A2 | `_route_dropped_files` dispatch via `file_import.classify` | `test_ui002_*`, `test_ui008_*` | ✅ |
| No new numeric constant (Article II) | spec §9 | bounds reuse `MAX_CANVAS_WIDTH/HEIGHT`; ceiling reuses `MAX_PALETTE_SIZE`; extension sets are module-local format IDs (ADR-0001 exemption) | review + `check_layering` | ✅ |

No divergence found between the three artefacts.

## 4. REQ coverage (0 uncovered)

**14 REQ-IDs → 14 with ≥1 impl → 14 with ≥1 test → 0 uncovered.**

### Data layer (`REQ-P7-DATA-001..005`)

| REQ | Impl | Test |
| --- | --- | --- |
| DATA-001 palette loader | `data/palette_import.load_palette` (REUSES `logic/palette_io.decode`) | `tests/data/test_palette_import.py` |
| DATA-002 image → `PixelBuffer` | `ui/image_import.decode_image` (QImage, ADR-0010) | `tests/ui/test_drag_drop_import.py` `test_ui003_*` |
| DATA-003 file-type classifier | `data/file_import.classify` + `FileType` | `tests/data/test_file_import.py` + `check_layering` (spec-only SC-D003-3) |
| DATA-004 `.pixproj` (REUSE) | `data/project_io.load_project` via `main_window` | existing `tests/data/test_project_io.py` + `test_ui004_*` |
| DATA-005 shared error base | `data/file_import` `FileImportError`/`PaletteImportError`/`ImageImportError` | `tests/data/test_file_import.py` + `tests/data/test_palette_import.py` |

### UI layer (`REQ-P7-UI-001..009`) — all impl `ui/main_window.py` (+ `ui/image_import.py`), tests `tests/ui/test_drag_drop_import.py`

| REQ | Impl seam | Test group |
| --- | --- | --- |
| UI-001 drop events | `setAcceptDrops`/`dragEnterEvent`/`dropEvent` | `test_ui001_*` |
| UI-002 type router | `_route_dropped_files` | `test_ui002_*` |
| UI-003 image → new tab | image branch + enabler `logic/document.from_buffer` | `test_ui003_*` + `tests/logic/test_document_from_buffer.py` |
| UI-004 dirty prompt | Save/Discard/Cancel guard | `test_ui004_*` |
| UI-005 undoable palette replace | palette branch + enabler `logic/palette.replace` | `test_ui005_*` + `tests/logic/test_palette_replace.py` |
| UI-006 notice surface | notices | drag-drop UI suite |
| UI-007 error surface | catches `(FileImportError, ProjectIOError)` | drag-drop UI suite |
| UI-008 multi-file router | stable-order per-file guard | drag-drop UI suite |
| UI-009 `tr()` strings + dialog | prompt/notice strings | drag-drop UI suite + `string_audit_check` (spec-only SC-U009-1) |

**New tests on disk (95):** `test_file_import.py` (16), `test_palette_import.py` (21),
`test_palette_replace.py` (12), `test_document_from_buffer.py` (12), `test_drag_drop_import.py` (34).

## 5. Artifact updates made by this gate

- `specs/drag-drop-import/traceability.md` — flipped from PRE-IMPLEMENTATION to
  IMPLEMENTED/PRE-COMMIT; module + TEST columns updated to the **shipped** paths (retired the stale
  indicative `data/palette_io.py` / `data/image_io.py` / `test_palette_io.py` / `test_image_io.py`
  names); all rows `built`; coverage summary refreshed (14/14/0).
- `STRUCTURE.md` — Phase-7 `data/`, `logic/`, `ui/` sections flipped PLANNED → BUILT.
- `specs/drag-drop-import/analyze-report.md` — this report (final PASS).

## 6. Gate decision (Decision A1-D2)

`analyze` returns **zero unresolved cross-artifact findings** → **gate PASS**. The orchestrator
may proceed to commit / implement. Layering (A1-D3) clean on both scripts; no BLOCKED condition.
