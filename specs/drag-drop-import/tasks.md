# Tasks — Drag-and-Drop Import (REQ-NEW-A)

Dependency-ordered work items derived from `plan.md`. Slice **A-A** (data/logic) ships
before **A-B** (UI). Owners per the delegation table: AGT-03 (logic/data code), AGT-04
(logic/data tests), AGT-05 (UI code), AGT-06 (UI/a11y tests), AGT-08 (docs), AGT-01
(analyze/layering gate). Status: `todo | doing | done`.

Legend — acceptance links reference the spec §11 Gherkin scenarios (SC-D*/SC-U*).

---

## Slice A-A — Import DATA / LOGIC  (owners AGT-03 impl, AGT-04 tests)

| ID | Task | Owner | Target file(s) | Depends on | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| A-A1 | Create `file_import.py`: `FileType` enum, extension-set constants (`IMAGE_/PALETTE_EXTENSIONS`, `PROJECT_EXTENSION`, `PALETTE_FORMAT_BY_EXTENSION`), shared `FileImportError(ValueError)` base + `PaletteImportError`/`ImageImportError` subclasses, and `classify(path)->FileType` (case-insensitive, deterministic, Qt-free). | AGT-03 | `pixelart_creator/data/file_import.py` (NEW) | — | REQ-P7-DATA-003, -005 · SC-D003-1..2, SC-D005-3 | todo |
| A-A2 | Create `palette_import.py`: `load_palette(path)->Palette` — read UTF-8 via pathlib, dispatch extension→fmt (`PALETTE_FORMAT_BY_EXTENSION`), delegate to `logic.palette_io.decode`; wrap `OSError`/`PaletteIOError`/unknown-ext as `PaletteImportError`. Reuses the shipped parser (no grammar re-impl). | AGT-03 | `pixelart_creator/data/palette_import.py` (NEW) | A-A1 | REQ-P7-DATA-001, -005 · SC-D001-1..5, SC-D005-1/-3 | todo |
| A-A3 | Extend `Palette` with `replace(colors: Iterable[RGBA]) -> None`: validate each colour + `MAX_PALETTE_SIZE`, swap `_colors` in place (Qt-free; supports reversible load, plan §6). | AGT-03 | `pixelart_creator/logic/palette.py` (EXTEND) | — | REQ-P7-UI-005 (enabler) · SC-U005-4 | todo |
| A-A4 | Extend `Document` with `from_buffer(buffer, *, palette=None, name="Imported") -> Document`: single-frame RGBA doc whose background layer *is* `buffer` (Qt-free factory, plan §5). | AGT-03 | `pixelart_creator/logic/document.py` (EXTEND) | — | REQ-P7-UI-003 (enabler) · SC-U003-2 | todo |
| A-A5 | Confirm reuse of `data/project_io.load_project` for the PROJECT branch (reuse trace; no new decode). Document the reuse in the module map. | AGT-03 | `pixelart_creator/data/project_io.py` (no change) | — | REQ-P7-DATA-004 · SC-D004-1..2 | todo |
| A-A6 | Unit + Hypothesis tests for `classify`: extension→type table (IMAGE/PROJECT/PALETTE/UNKNOWN), case-insensitivity, determinism. | AGT-04 | `tests/data/test_file_import.py` (NEW) | A-A1 | REQ-P7-DATA-003 · SC-D003-1..2 | todo |
| A-A7 | Tests for `load_palette`: valid `.gpl`/`.hex`/`.pal` → ordered `Palette`; malformed header/row → `PaletteImportError`; > `MAX_PALETTE_SIZE` → `PaletteImportError`; unreadable path → `PaletteImportError`. | AGT-04 | `tests/data/test_palette_import.py` (NEW) | A-A2 | REQ-P7-DATA-001, -005 · SC-D001-1..5, SC-D005-1 | todo |
| A-A8 | Tests: `FileImportError` is the common base of `PaletteImportError`/`ImageImportError` (UI can catch one family); no `eval`/`exec` in the import path (grep/review assertion). | AGT-04 | `tests/data/test_file_import.py` | A-A1 | REQ-P7-DATA-005 · SC-D005-2 (review), SC-D005-3 | todo |
| A-A9 | Tests for `Palette.replace`: replaces contents in place (same object identity), rejects oversized/invalid colours, `replace(old); replace(new); replace(old)` restores exactly (reversibility invariant). | AGT-04 | `tests/logic/test_palette.py` (EXTEND) | A-A3 | REQ-P7-UI-005 · SC-U005-4 | todo |
| A-A10 | Tests for `Document.from_buffer`: result is RGBA, single frame/layer, dimensions == buffer, background layer holds the exact buffer pixels. | AGT-04 | `tests/logic/test_document.py` (EXTEND) | A-A4 | REQ-P7-UI-003 · SC-D002-1, SC-U003-2 | todo |

## Slice A-B — Import UI  (owners AGT-05 impl, AGT-06 tests both themes)

| ID | Task | Owner | Target file(s) | Depends on | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| A-B1 | Create `image_import.py`: `decode_image(path)->PixelBuffer` via `QImage` → `Format_RGBA8888`, honour `bytesPerLine()` stride, bounds-check `width()/height()` vs `MAX_CANVAS_WIDTH/HEIGHT` **before** alloc, first-frame GIF, paletted→RGBA; raise `ImageImportError` on null/corrupt/oversized. | AGT-05 | `pixelart_creator/ui/image_import.py` (NEW) | A-A1 | REQ-P7-DATA-002 · SC-D002-1..6 | todo |
| A-B2 | `main_window`: `setAcceptDrops(True)` + `dragEnterEvent` (accept on `mimeData().hasUrls()`) + `dropEvent` (extract local paths via `QUrl.toLocalFile()`, drop empties) → `_route_dropped_files`. | AGT-05 | `pixelart_creator/ui/main_window.py` (EXTEND) | — | REQ-P7-UI-001 · SC-U001-1..2 | todo |
| A-B3 | `_route_dropped_files(paths)`: iterate in stable order; `classify` each; dispatch IMAGE/PROJECT/PALETTE/UNKNOWN; per-file `try/except (FileImportError, ProjectIOError)` → error notice + continue; zero files = no-op. | AGT-05 | `pixelart_creator/ui/main_window.py` | A-A1, A-B2 | REQ-P7-UI-002, -008 · SC-U002-1..2, SC-U008-1..5 | todo |
| A-B4 | `_import_image_document(path)`: `decode_image` → `Document.from_buffer` → `_add_document_tab` (new active tab, not a layer; source read-only). | AGT-05 | `pixelart_creator/ui/main_window.py` | A-A4, A-B1, A-B3 | REQ-P7-UI-003 · SC-U003-1..3 | todo |
| A-B5 | `_import_palette(path)`: `load_palette` → build `history.FunctionCommand` (do=`palette.replace(new)`, undo=`palette.replace(old)`), push `ui/commands.LogicCommand` on `record.stack`; no open doc → graceful notice no-op. | AGT-05 | `pixelart_creator/ui/main_window.py` | A-A2, A-A3, A-B3 | REQ-P7-UI-005 · SC-U005-1..5 | todo |
| A-B6 | `_open_dropped_project(path)` + `_prompt_dirty_save()`: dirty = `not active_tab().stack.isClean()`; Save/Discard/Cancel dialog (tr(), keyboard-reachable, focus visible, LanguageChange retranslate); Save→save then replace, Discard→replace, Cancel→abort; replace = `open_document(path)` then `close_document(prev_index)`; no doc → open without prompt. | AGT-05 | `pixelart_creator/ui/main_window.py` | A-A5, A-B3 | REQ-P7-UI-004 · SC-U004-1..5 | todo |
| A-B7 | Make `isClean()` a valid dirty source: `save_document(path)` calls `stack.setClean()` after a successful save. | AGT-05 | `pixelart_creator/ui/main_window.py` | — | REQ-P7-UI-004 (enabler) · SC-U004-1/-2 | todo |
| A-B8 | Notice/error surface: `_notice(msg)` (unsupported/no-doc) and `_error_notice(path, msg)` (corrupt/oversized/malformed) — non-blocking, state intact, `tr()`-wrapped. | AGT-05 | `pixelart_creator/ui/main_window.py` | A-B3 | REQ-P7-UI-006, -007 · SC-U006-1, SC-U007-1..4 | todo |
| A-B9 | pytest-qt (both themes, headless offscreen): file-drop accept + path delivery; route-by-type (image-anywhere→new tab); image→new tab not layer + RGBA dims + source untouched. | AGT-06 | `tests/ui/test_drag_drop_import.py` (NEW) | A-B2, A-B3, A-B4 | REQ-P7-UI-001, -002, -003 · SC-U001-*, SC-U002-*, SC-U003-* | todo |
| A-B10 | pytest-qt: `.pixproj` drop — no-prompt-when-clean; prompt-when-dirty; Cancel aborts (state unchanged); Save persists then opens; Discard opens without saving. | AGT-06 | `tests/ui/test_drag_drop_import.py` | A-B6, A-B7 | REQ-P7-UI-004 · SC-U004-1..5 | todo |
| A-B11 | pytest-qt: palette drop replaces active palette in one undo step; `.hex`/`.pal` variants; undo restores prior palette (apply∘undo=identity); no-doc graceful no-op. | AGT-06 | `tests/ui/test_drag_drop_import.py` | A-B5 | REQ-P7-UI-005 · SC-U005-1..5 | todo |
| A-B12 | pytest-qt: unknown type → notice no-crash; corrupt/oversized image → error notice, no tab; malformed palette → error, palette unchanged; invalid `.pixproj` → error, no open; multi-file batch (3 images→3 tabs; mixed; one bad skipped; last-palette-wins; zero=no-op). | AGT-06 | `tests/ui/test_drag_drop_import.py` | A-B3, A-B8 | REQ-P7-UI-006, -007, -008 · SC-U006-1, SC-U007-1..4, SC-U008-1..5 | todo |
| A-B13 | a11y/i18n both themes: `string_audit_check` over changed `ui/` (all new strings `tr()`-wrapped); prompt keyboard-reachable + focus visible + LanguageChange retranslate; legibility light+dark. | AGT-06 / AGT-07 | `tests/ui/test_drag_drop_import.py` + `scripts/string_audit_check.py` | A-B6, A-B8 | REQ-P7-UI-009 · SC-U009-1..3 | todo |

## Gate / docs

| ID | Task | Owner | Target file(s) | Depends on | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | Run `check_layering` + `check_cycles` after A-A/A-B land; verify no logic→Qt leak (QImage confined to `ui/`) and no new cycle. | AGT-01 | `scripts/check_layering.py`, `scripts/check_cycles.py` | A-A*, A-B* | NFR-1 · SC-D003-3 | todo |
| G2 | `sdd-analyze` C1 gate (zero unresolved cross-artifact findings) + update STRUCTURE.md with the new/changed modules. | AGT-01 | `STRUCTURE.md` | G1 | C1 gate | todo |
| G3 | Add ADR-0010 (decode placement) to docs nav; CHANGELOG Unreleased entry on merge. | AGT-08 | `docs/adr/0010-*.md`, `docs/CHANGELOG.md` | — | REQ-P7-DATA-002/-005 | todo |

---

## Coverage check (every REQ → ≥1 impl + ≥1 test/verify)

| REQ-ID | Impl task(s) | Test/verify task(s) |
| --- | --- | --- |
| REQ-P7-DATA-001 | A-A2 | A-A7 |
| REQ-P7-DATA-002 | A-B1 | A-B9, A-B12 (SC-D002-1..6) |
| REQ-P7-DATA-003 | A-A1 | A-A6, G1 (SC-D003-3) |
| REQ-P7-DATA-004 | A-A5 | A-B10 + existing `test_project_io` |
| REQ-P7-DATA-005 | A-A1, A-A2 | A-A7, A-A8 |
| REQ-P7-UI-001 | A-B2 | A-B9 |
| REQ-P7-UI-002 | A-B3 | A-B9 |
| REQ-P7-UI-003 | A-A4, A-B1, A-B4 | A-A10, A-B9 |
| REQ-P7-UI-004 | A-B6, A-B7 | A-B10 |
| REQ-P7-UI-005 | A-A3, A-B5 | A-A9, A-B11 |
| REQ-P7-UI-006 | A-B8 | A-B12 |
| REQ-P7-UI-007 | A-B8 | A-B12 |
| REQ-P7-UI-008 | A-B3 | A-B12 |
| REQ-P7-UI-009 | A-B6, A-B8 (tr) | A-B13 |

**14/14 REQ-IDs have ≥1 impl and ≥1 test/verify task. 0 uncovered.**

## Exit / status
- Tasks dependency-ordered A-A → A-B; one owner per task (TK-D1); deterministic gates use the
  scripts (TK-D2: `check_layering`/`check_cycles`/`string_audit_check`). **STATUS: COMPLETED** →
  proceed to `sdd-analyze`.
