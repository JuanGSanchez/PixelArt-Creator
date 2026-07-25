# Plan — Drag-and-Drop Import (REQ-NEW-A)

| Field | Value |
| --- | --- |
| Feature | `drag-drop-import` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-03 |
| SDD phase | `plan` (this document) → `sdd-tasks` → `sdd-analyze` (C1 gate) |
| Governed by | `constitution.md` (Articles I three-layer/S11, II constants/S12, IV coverage, V a11y/i18n, VII validated I/O) |
| Over | approved `specs/drag-drop-import/spec.md` + `traceability.md` (14 REQ-IDs) |
| Grounded by | `docs/research-drag-drop-import.md` (palette grammars + QImage-vs-Pillow trade-off + Pillow MIT-CMU licence) |
| Layering baseline | `check_layering` clean (29 modules, exit 0) + `check_cycles` no cycles (67 modules, exit 0) at plan time |

---

## 0. Grounding recon — what already ships (changes the NEW surface)

Direct code inspection materially reduces the "NEW" scope the spec assumed:

| Capability | Spec status | **Plan finding (grounded)** |
| --- | --- | --- |
| Palette **text parser** `.gpl`/`.pal`/`hex` | NEW | **ALREADY SHIPPED** — `logic/palette_io.decode(text, fmt) -> Palette` (REQ-P3-LOGIC-016). Qt-free, defensive (no eval/exec), bounds-checked to `MAX_PALETTE_SIZE`, raises `PaletteIOError`. Covers all three v1 formats. **REUSE it.** |
| Palette **path loader** (read file → pick format → parse) | NEW | **NEW (thin)** — the shipped parser takes `(text, fmt)`, not a path; disk read + extension→format dispatch does not exist. One small Qt-free `data/` module. |
| Image → RGBA `PixelBuffer` decoder | NEW | **NEW** — no image→buffer path exists. Decode via **QImage in `ui/`** (ruling §4). |
| File-type classifier | NEW | **NEW** — no classifier exists. Qt-free `data/`. |
| Shared import-error base | NEW | **NEW** — Qt-free `data/`. |
| `.pixproj` load | REUSED | `data/project_io.load_project` (raises `ProjectIOError`). Confirmed. |
| New-document tab | REUSED | `Main_Window.new_document`/`_add_document_tab`. Confirmed. But `new_document` builds an **empty** background layer — importing an image needs a buffer-seeded `Document` (§5). |
| Undoable palette edit | REUSED | `record.stack` + `ui/commands.LogicCommand` wrapping a `history.FunctionCommand` (the palette-editor "import" path already replaces palette contents in place — see `commands.py` Phase-3 note). `Palette` has **no** bulk-replace method → one tiny logic addition (§6). |

**Consequence:** the palette branch collapses to *reuse `logic/palette_io.decode` behind a new `data/` path loader*; the classifier and error base are the only genuinely new `data/` surface; the image decoder is the only new `ui/` decode.

---

## 1. Architecture overview

Two slices mirroring prior phases (data/logic first, UI binds to it):

```
 OS file-explorer drag ──▶ ui/main_window.py  (dragEnterEvent / dropEvent, setAcceptDrops)
                                   │  list[local path]  (stable drop order)
                                   ▼
                          per-file router (ui/)  ── classify(path) ──▶ data/file_import.FileType
                                   │
        ┌──────────────────────────┼───────────────────────────┬───────────────────────┐
     IMAGE                       PROJECT                      PALETTE                  UNKNOWN
        │                          │                            │                        │
 ui/image_import.decode_image   data/project_io.load_project  data/palette_import       notice
   → logic.PixelBuffer(RGBA)      → logic.Document              .load_palette(path)      (no-op)
        │                          │  (dirty-guard prompt)      → logic.Palette
 logic.Document.from_buffer      replace active tab             │
   → _add_document_tab (new tab)  (Save/Discard/Cancel)      LogicCommand(FunctionCommand
        │                                                      replace-in-place) on record.stack
   new canvas tab, active                                      (one undo step)
```

- **`logic/`** stays the domain authority (Article I): `Palette`, `PixelBuffer`, `Document`, and the existing `palette_io` parser. Zero Qt.
- **`data/`** owns Qt-free file I/O: the classifier, the palette path loader, the shared error base, and (reused) `project_io`. Zero Qt.
- **`ui/`** owns everything Qt: drag/drop events, the QImage decode, the dirty-save prompt, notices, and the undo bridging.

### 1.1 Layer-placement rulings (S11 / Article I) — enforced by `check_layering` + `check_cycles`

| New/changed module | Layer | Justification | Import edges (all downward, acyclic) |
| --- | --- | --- | --- |
| `data/file_import.py` | **data** | Pure predicate over a path string + exception classes. No Qt, no I/O side effects. | imports stdlib only (`enum`, `pathlib`) |
| `data/palette_import.py` | **data** | File read (`pathlib`) + format dispatch, delegating parse to `logic/palette_io`. Qt-free, mirrors `project_io`/`favourites_io`. | `logic.palette_io`, `logic.palette`, `data.file_import` |
| `ui/image_import.py` | **ui** | Uses `QImage` (Qt) → **must** live in `ui/` (Article I). Hands a packed RGBA buffer to `logic`. | `PySide6`, `logic.pixel_buffer`, `logic.constants`, `data.file_import` |
| `logic/palette.py` (extend) | **logic** | Add `Palette.replace(colors)` (Qt-free in-place bulk set). | no new import |
| `logic/document.py` (extend) | **logic** | Add `Document.from_buffer(buffer, …)` factory (Qt-free). | no new import |
| `logic/palette_io.py` | **logic** | **No change** — reused as-is. | — |
| `data/project_io.py` | **data** | **No change** — reused as-is. | — |
| `ui/main_window.py` (extend) | **ui** | Drop events, router, dirty prompt, notices, image/palette import wiring. | `ui/image_import`, `data/file_import`, `data/palette_import`, `data/project_io`, `logic/document`, `ui/commands` |

No `logic/`→Qt edge, no `data/`→Qt edge, no `*/`→`ui/` edge, no cycle. The image decoder is deliberately the *only* new Qt consumer, and it is in `ui/`.

---

## 2. Data-layer plan (Slice A-A) — `REQ-P7-DATA-001..005`

### 2.1 `data/file_import.py` — classifier + error base (`REQ-P7-DATA-003`, `-005`)

```python
# Qt-free, pure.
IMAGE_EXTENSIONS   = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif"})
PALETTE_EXTENSIONS = frozenset({".gpl", ".hex", ".pal"})
PROJECT_EXTENSION  = ".pixproj"
# maps a palette extension to the fmt id logic.palette_io.decode expects:
PALETTE_FORMAT_BY_EXTENSION = {".gpl": "gpl", ".hex": "hex", ".pal": "pal"}

class FileType(enum.Enum):
    IMAGE = "image"; PROJECT = "project"; PALETTE = "palette"; UNKNOWN = "unknown"

class FileImportError(ValueError):        # shared base (DATA-005)
    """Base for every drag-drop import rejection."""
class PaletteImportError(FileImportError): ...
class ImageImportError(FileImportError):  ...   # raised from ui/, class defined here (Qt-free)

def classify(path: str | pathlib.Path) -> FileType:
    """Map a path to a FileType by case-insensitive extension. Deterministic, Qt-free."""
```

- **Extension-set home (spec §9):** the extension sets are **format identifiers**, not numeric tuning values — per the 2026-07-02 intrinsic-literal exemption (ADR-0001) they stay **module-local** here, not in `constants.py`. No new numeric constant is introduced by this feature (image bounds reuse `MAX_CANVAS_WIDTH/HEIGHT`; palette ceiling reuses `MAX_PALETTE_SIZE`).
- **`ImageImportError` is defined here (Qt-free) but raised from `ui/`.** An exception class carries no Qt; putting the whole family in one Qt-free `data/` module lets the UI catch a single base (DATA-005) and keeps the error model out of `ui/`. `ui/` importing this class is a legal downward edge.

### 2.2 `data/palette_import.py` — palette path loader (`REQ-P7-DATA-001`)

```python
def load_palette(path: str | pathlib.Path) -> logic.palette.Palette:
    """Read a .gpl/.hex/.pal file and parse it to a Palette (Qt-free).

    Dispatches format by extension (PALETTE_FORMAT_BY_EXTENSION), reads UTF-8
    text via pathlib, delegates parsing to logic.palette_io.decode(text, fmt).
    Raises PaletteImportError on OSError, unknown extension, or PaletteIOError.
    """
```

- **Reuses the shipped parser** (`logic/palette_io.decode`) verbatim — no re-implementation of the `.gpl`/`.pal`/`hex` grammars. The research grammars are already honoured by the shipped parser (GIMP header, JASC header+count, hex 6/8-digit via `from_hex`). Bounds to `MAX_PALETTE_SIZE` and no-eval/exec are inherited from `palette_io`.
- **Error normalisation:** `OSError` (unreadable) and `logic.palette_io.PaletteIOError` (malformed/oversized) are wrapped as `PaletteImportError` so the UI catches one family.

### 2.3 Image decoder placement (`REQ-P7-DATA-002`) — see §4 (RULED into `ui/`).

### 2.4 `.pixproj` reuse (`REQ-P7-DATA-004`)

No new code. The PROJECT branch calls the shipped `data/project_io.load_project(path) -> Document`; its `ProjectIOError` is surfaced by the UI error handler (REQ-P7-UI-007). Recorded as a reuse trace only.

### 2.5 Error contract (`REQ-P7-DATA-005`)

- **Shared base `FileImportError(ValueError)`** in `data/file_import.py`; `PaletteImportError` and `ImageImportError` subclass it. The UI router catches `(FileImportError, ProjectIOError)` — one new family plus the shipped project family (which predates this feature and keeps its own Article VII guarantees; it is not re-parented to avoid touching shipped code).
- Every importer **validates before use**; no imported content is passed to `eval`/`exec` (inherited from `palette_io`/`project_io`; the QImage decoder does binary decode only).

---

## 3. UI-layer plan (Slice A-B) — `REQ-P7-UI-001..009`

### 3.1 `ui/image_import.py` — QImage decode (`REQ-P7-UI-003` decode side / `REQ-P7-DATA-002` realised)

```python
def decode_image(path: str | pathlib.Path) -> logic.pixel_buffer.PixelBuffer:
    """Decode an image file to an RGBA PixelBuffer (Qt/ui side).

    QImage(path); reject QImage.isNull() → ImageImportError.
    Bounds-check width()/height() against MAX_CANVAS_WIDTH/HEIGHT BEFORE building
    the buffer → ImageImportError (never truncate).
    convertToFormat(QImage.Format.Format_RGBA8888); read constBits() honouring
    bytesPerLine() (strip 32-bit row padding) → packed (H, W, 4) uint8;
    construct PixelBuffer(w, h, ColorMode.RGBA) and assign .data.
    """
```

### 3.2 `ui/main_window.py` (extend) — drop events, router, prompt, notices (`REQ-P7-UI-001..009`)

- **Accept drops (UI-001):** `setAcceptDrops(True)`; `dragEnterEvent` accepts when `event.mimeData().hasUrls()`; `dropEvent` extracts local paths from `mimeData().urls()` (`QUrl.toLocalFile()`), filters empties, and calls the router.
- **Route by type (UI-002, UI-008):** iterate paths in **delivered (stable) order**; `classify(path)` → dispatch. Each file wrapped in its own `try/except (FileImportError, ProjectIOError)` → error notice, **continue** (one bad file never aborts the batch). Zero files = no-op.
- **IMAGE (UI-003):** `decode_image(path)` → `Document.from_buffer(buffer)` → `_add_document_tab(document, path.name)`. New tab, active. Never a layer. Source untouched on disk (read-only decode).
- **PROJECT (UI-004):** dirty-guard then open — see §7.
- **PALETTE (UI-005):** `load_palette(path)` → build a `history.FunctionCommand` (do = `active.palette.replace(new_colors)`, undo = `active.palette.replace(old_snapshot)`) → push `ui/commands.LogicCommand(cmd, refresh, tr("Load palette"))` on `record.stack`. One undo step; `apply ∘ undo = identity`. No open document → graceful no-op + notice.
- **UNKNOWN (UI-006):** non-blocking notice (status bar / non-modal), no side effect.
- **Errors (UI-007):** the caught exception message identifies the file + problem; state left intact (no partial tab; palette replace is atomic in one command so a parse failure happens *before* any push).
- **a11y/i18n/themes (UI-009):** every new string (prompt buttons, notices, errors) `tr()`-wrapped; the dirty prompt is a keyboard-reachable dialog with visible focus and re-translates on `QEvent.LanguageChange`; verified in both themes by pytest-qt + `string_audit_check`.

---

## 4. RULING — image-decode backend & placement (QImage in `ui/`)

**Decision: decode images with `QImage` inside `ui/image_import.py`. NO new dependency. The domain model (`PixelBuffer`/`Document`) stays in `logic/`.**

**Rationale (grounded in `docs/research-drag-drop-import.md` §2):**
- PySide6 is already a hard dependency; `QImage` reads PNG/JPG/JPEG/BMP/GIF out of the box (research §2.1). **Zero new runtime dependency.**
- The Pillow alternative (research §2.2) would enable a Qt-free `logic/` decode but adds a **new MIT-CMU C-extension dependency** that needs maintainer sign-off (research flags the "Apache-compatible" reading as informal, not a legal opinion). Import is **not** a per-frame/perf path, so the "unit-testable in pure Python" upside is modest and does not outweigh a new dependency.
- Article I forbids Qt in `logic/`, so a `QImage` decode **must** live in `ui/`. The boundary is kept clean: `ui/` normalises QImage bytes to a **packed `Format_RGBA8888`** buffer (honouring `bytesPerLine()` stride padding — research §2.1 stride gotcha) and hands `logic.PixelBuffer` a plain `(H, W, 4)` uint8 array. No Qt object crosses into `logic/`.

**Consequences / contract for AGT-05 (frozen):**
- `Format_RGBA8888` is mandatory (deterministic R,G,B,A byte order across platforms — *not* `Format_ARGB32`, which is native-endian).
- Rows **must** be sliced `[y*bytesPerLine : y*bytesPerLine + width*4]`; do not assume a contiguous `width*height*4` block.
- Bounds are checked on `width()/height()` **before** buffer construction (reject > `MAX_CANVAS_WIDTH`/`MAX_CANVAS_HEIGHT` with `ImageImportError`).
- Multi-frame GIF → **first frame only** (CL-A3). Paletted/indexed sources → QImage expands to RGBA on `convertToFormat` (CL-A3).

**ADR:** this placement + the rejected Pillow-in-logic alternative + the RGBA8888/stride boundary contract + the shared error model are recorded in **`docs/adr/0010-drag-drop-import-decode-placement-and-error-model.md`** (immutable; traced to REQ-P7-DATA-002/-005 and the research report). Because we choose QImage (no new dependency), **no dependency sign-off is required**; the ADR documents the choice so a future Pillow reversal is a conscious, traceable decision.

---

## 5. Image → new document (`REQ-P7-UI-003`, reuse boundary)

Shipped `new_document()` builds a `Document` with an **empty** background layer, so it cannot seed image pixels. Two clean options; ruled option B (keeps `ui/` from poking layer internals):

- **A (rejected):** `ui/` builds `Document(w,h,RGBA)` then reaches into `document.frames[0].layers[0].buffer = decoded`. Leaks tree structure into `ui/`.
- **B (ruled):** add a Qt-free `logic` factory `Document.from_buffer(buffer, *, palette=None, name="Imported")` that returns a single-frame, single-layer RGBA document whose background layer *is* the decoded buffer. `ui/` calls `Document.from_buffer(decode_image(path))` → `_add_document_tab(...)`. Factory is unit-testable by AGT-04, Qt-free.

---

## 6. Palette replace-in-place (`REQ-P7-UI-005`, reversibility)

The active palette (`record.document.palette`) is referenced by the scene, palette panel and editor, so a drop must **mutate it in place** (not rebind a new object) to keep those references valid — exactly the shipped palette-editor "import" pattern (`commands.py`). `Palette` currently exposes no bulk replace, so:

- **Add `Palette.replace(colors: Iterable[RGBA]) -> None`** (logic, Qt-free): validate each colour + `MAX_PALETTE_SIZE` bound, then swap `_colors` contents in place. Reversible trivially: `undo` calls `replace(old_snapshot)` where `old_snapshot = palette.colors()` captured at command-build time.
- The undo command is a `history.FunctionCommand(do, undo, label="Load palette")` bridged by the shipped `ui/commands.LogicCommand`. Multi-palette drop (CL-A2): each palette is its own `LogicCommand` push → last-dropped wins, each independently undoable.

---

## 7. `.pixproj` drop — dirty guard + open semantics (`REQ-P7-UI-004`)

- **Dirty-state source (ruled):** `record.stack.isClean()` (the tab's `QUndoStack`). "Dirty" = `active_tab() is not None and not active_tab().stack.isClean()`. **Required AGT-05 wiring:** `save_document()` must call `stack.setClean()` after a successful save so `isClean()` is meaningful (shipped `save_document` does not yet). This is part of UI-004.
- **Open semantics (ruled): REPLACE the active document.** Rationale: US-A2 frames the guard as "before losing unsaved work" and the user chose a real Save/**Discard**/Cancel — semantics only meaningful if opening can lose the current doc. Realisation reuses shipped methods: on Save/Discard, call `open_document(path)` (adds the loaded project tab) then `close_document(previous_active_index)`. When **no** document is open, just `open_document(path)` (no prompt). The exact tab-swap mechanism is AGT-05's within this frozen semantic: *guard the active dirty doc, three-way choice, Cancel leaves everything unchanged.*
- **Three-way behaviour:** Save → `save_document(path_or_saveas)` then replace; Discard → replace without saving; Cancel → abort (no open, no close, no state change). If the active doc has no known path, Save falls back to the shipped Save-As dialog (`QFileDialog.getSaveFileName`, as in `_on_save`).

---

## 8. Frozen interface contracts

### 8.1 For AGT-03 (data/logic) — Slice A-A

```python
# pixelart_creator/data/file_import.py    (NEW, Qt-free)
IMAGE_EXTENSIONS: frozenset[str]        # {.png .jpg .jpeg .bmp .gif}
PALETTE_EXTENSIONS: frozenset[str]      # {.gpl .hex .pal}
PROJECT_EXTENSION: str                  # ".pixproj"
PALETTE_FORMAT_BY_EXTENSION: dict[str, str]   # {.gpl:'gpl', .hex:'hex', .pal:'pal'}
class FileType(enum.Enum): IMAGE, PROJECT, PALETTE, UNKNOWN
class FileImportError(ValueError): ...          # shared base (DATA-005)
class PaletteImportError(FileImportError): ...
class ImageImportError(FileImportError): ...    # defined here; raised in ui/image_import
def classify(path: str | Path) -> FileType      # case-insensitive, deterministic

# pixelart_creator/data/palette_import.py  (NEW, Qt-free)
def load_palette(path: str | Path) -> Palette   # read+dispatch+delegate to logic.palette_io.decode
                                                # raises PaletteImportError

# pixelart_creator/logic/palette.py         (EXTEND, Qt-free)
class Palette:
    def replace(self, colors: Iterable[RGBA]) -> None   # in-place bulk set, bounds-checked → PaletteError

# pixelart_creator/logic/document.py        (EXTEND, Qt-free)
class Document:
    @classmethod
    def from_buffer(cls, buffer: PixelBuffer, *, palette: Palette | None = None,
                    name: str = "Imported") -> "Document"   # single-frame RGBA doc seeded by buffer
```

### 8.2 For AGT-05 (UI) — Slice A-B

```python
# pixelart_creator/ui/image_import.py       (NEW, Qt)
def decode_image(path: str | Path) -> PixelBuffer   # QImage→Format_RGBA8888, honour bytesPerLine,
                                                     # bounds-check pre-alloc, raise ImageImportError

# pixelart_creator/ui/main_window.py        (EXTEND)
#  - setAcceptDrops(True); dragEnterEvent(accept on hasUrls); dropEvent(→ router)
#  - _route_dropped_files(paths: list[str]) -> None            # stable order, per-file try/except
#  - _import_image_document(path) -> None                      # decode_image → Document.from_buffer → _add_document_tab
#  - _import_palette(path) -> None                             # load_palette → LogicCommand(replace) on record.stack; no-doc → notice
#  - _open_dropped_project(path) -> None                       # dirty guard → replace active (open+close); Cancel aborts
#  - _prompt_dirty_save() -> {"save"|"discard"|"cancel"}       # tr(), keyboard-reachable, both themes
#  - _notice(msg) / _error_notice(path, msg)                   # non-blocking, tr()-wrapped
#  - save_document(path): also stack.setClean() on success     # so isClean() is a valid dirty source
# Reuses (unchanged): open_document, _add_document_tab, close_document, ui/commands.LogicCommand,
#                     data/project_io.load_project, record.stack, record.document.palette
```

---

## 9. Constants (Article II / S12)

**No new numeric constant.** Image bounds reuse `MAX_CANVAS_WIDTH` (7680) / `MAX_CANVAS_HEIGHT` (4320); the palette ceiling reuses `MAX_PALETTE_SIZE` (256). Extension sets are format identifiers (module-local in `file_import.py`, ADR-0001 exemption). Confirmed against `logic/constants.py`.

## 10. Reversibility & render touchpoints

- **Reversible (NFR-5):** only the palette-load replace is a `QUndoCommand` (one `LogicCommand`, `apply ∘ undo = identity`). Image-drop (new tab) and project-open (replace) create/open editing contexts, consistent with shipped New/Open — not undo steps.
- **Render/perf (AGT-10):** none required. Import is not a per-frame path; a decoded buffer flows through the shipped `_add_document_tab`→`CanvasScene` path. No new render strategy, no `perf_profile` gate.

## 11. Implementation strategy / ordering

1. **Slice A-A (AGT-03 + AGT-04):** `data/file_import.py` (classifier + errors) → `data/palette_import.py` (loader, reuses `palette_io`) → `logic` additions `Palette.replace` + `Document.from_buffer`. Unit + Hypothesis tests (parser robustness/bounds reuse existing `palette_io` tests + new loader/classifier tests). Ships first.
2. **Slice A-B (AGT-05 + AGT-06):** `ui/image_import.py` (QImage decode) → `main_window` drop events + router + dirty prompt + palette-replace command + notices; `save_document` `setClean()` wiring. pytest-qt, both themes, headless.
3. **AGT-08:** ADR-0010 already authored by AGT-01 (§4); update `docs/CHANGELOG` under Unreleased when merged.
4. **AGT-01:** `sdd-analyze` C1 gate + `check_layering`/`check_cycles` + STRUCTURE.md (done in this workflow).

## 12. Exit / status

- Plan authored over the approved spec; every REQ mapped to a module + layer (§2/§3) with a frozen contract (§8).
- **Key rulings:** (a) palette parse **reuses** `logic/palette_io.decode` behind a new Qt-free `data/palette_import` loader; (b) image decode = **QImage in `ui/`, no new dependency** (§4, ADR-0010); (c) new Qt-free `data/file_import` classifier + `FileImportError` base; (d) `.pixproj` reuses `load_project`; (e) palette drop = undoable in-place `Palette.replace` via `record.stack`; (f) `.pixproj` drop **replaces** the active doc with a `QUndoStack.isClean()` dirty guard.
- **No new numeric constant; no new runtime dependency; no Qt in logic/data.** Layering/cycles verified clean at plan time and by design for the planned edges (confirmed in `sdd-analyze`).
- **STATUS: COMPLETED** → proceed to `sdd-tasks`.
