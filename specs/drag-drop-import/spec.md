# Specification — Drag-and-Drop Import (REQ-NEW-A)

| Field | Value |
| --- | --- |
| Feature | `drag-drop-import` |
| Author | AGT-02 (Requirements) |
| Date | 2026-07-03 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VII, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — drag-drop event handling, the palette-file importer and the image→`PixelBuffer` decoder do **not** exist yet; only `.pixproj` open is shipped |
| REQ-ID range | `REQ-DDI-DATA-001..005`, `REQ-DDI-UI-001..009` — this feature owns the **`REQ-DDI-<LAYER>-<NNN>`** prefix (`DDI` = drag-drop-import). It is a **non-phase feature**, so it carries its own prefix rather than a phase-numbered range; the `REQ-P7-*` range belongs to `phase-7-export`, which owns it by name. *(Re-allocated 2026-07-30 from the former `REQ-P7-DATA-001..005` / `REQ-P7-UI-001..009` — 1:1, same order, requirement text unchanged. Cross-feature citations to other features' requirements keep their original ids.)* Semantically this is import/pipeline work, built early per RC-CONTINUATION. |
| User requirement | REQ-NEW-A (user-resolved, `docs/decisions-20260701.md` L160–166; user directives 2026-07-02) |
| Layer scope | `pixelart_creator/data/` (NEW: palette-file parser + image decoder + file-type classifier — Qt-free) + `pixelart_creator/ui/` (NEW: file-URL drag/drop handling, type routing, dirty-prompt, error/notice surface) |
| Binds to (upstream) | REUSED shipped `ui/main_window.py` `open_document`/`new_document` + `data/project_io.load_project`/`save_project`; `logic/pixel_buffer.py` (`PixelBuffer`, `ColorMode`), `logic/palette.py` (`Palette`), `logic/document.py` (`Document`); the shipped undoable palette-edit path (`_bind_palette_workflows` → `record.stack`); `logic/constants.py` (`MAX_CANVAS_WIDTH/HEIGHT`) |
| Research | `docs/research-drag-drop-import.md` (concurrent — palette formats + image-decode approach). This spec fixes the **WHAT**; the parser internals and QImage-vs-Pillow placement are **HOW** (AGT-01 `sdd-plan` / AGT-03) |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) → `sdd-tasks` |

---

## 1. Purpose (WHY)

Artists expect to drag a file from the OS file explorer (Windows Explorer, Finder, Nautilus)
straight **into** the application, and have it "do the obvious thing". The app today has **no
drag-and-drop path at all**: files can only enter through File ▸ Open (`.pixproj` only). REQ-NEW-A
(user-resolved) closes that gap with three type-routed behaviours:

- **Drop an IMAGE** (`.png` / `.jpg` / `.jpeg` / `.bmp` / `.gif`) → it opens as a **NEW
  document / canvas tab** — explicitly **NOT** as a layer (the user considered and rejected
  image-as-layer).
- **Drop a `.pixproj`** → **OPEN it as a project** (prompt to Save / Discard / Cancel if the
  active document has unsaved changes).
- **Drop a PALETTE file** (`.gpl` / `.hex` / `.pal`) → **LOAD it into the active palette**.

This document specifies **WHAT** each behaviour must do and **WHY**, technology-neutral at the
requirement level. The **HOW** — the concrete parser implementations, whether image decode uses
`QImage` or Pillow, the exact drag-event wiring, the dirty-state source — belongs to `sdd-plan`
(AGT-01), AGT-03 (data), AGT-05 (UI), grounded by The Researcher
(`docs/research-drag-drop-import.md`). Palette-load and any state-changing import are **reversible**
where the shipped model already makes them so (the palette-edit path is undoable via
`ui/commands.py` over the tab's `QUndoStack`); the data-layer parsers/decoder stay **Qt-free**
(Article I / S11).

### NEW vs REUSED (orchestrator-confirmed grounding)

| Capability | Status | Evidence |
| --- | --- | --- |
| `.pixproj` open | **REUSED** | `Main_Window.open_document(path)` → `data/project_io.load_project(path)` (shipped, `main_window.py:635`, `project_io.py:419`) |
| New-document/tab creation | **REUSED** | `Main_Window.new_document(...)` + `_add_document_tab(...)` (shipped) |
| Undoable palette edit | **REUSED** | `_bind_palette_workflows` binds the palette editor to the tab's `record.stack` + `_on_palette_edited` (shipped) |
| Palette-file parser (`.gpl`/`.hex`/`.pal`) | **NEW** | `data/` has only `project_io` + `favourites_io` — **no palette-text parser exists** |
| Image → `PixelBuffer` decoder | **NEW** | only buffer→`QImage` exists today; **no image→buffer decode path** |
| File-URL drag/drop event handling | **NEW** | no `dragEnterEvent`/`dropEvent` anywhere in `ui/` |
| Dirty-state save prompt | **NEW** | there is **no** existing Save/Discard/Cancel prompt to reuse; `open_document` currently opens unconditionally (dirty source, e.g. `QUndoStack.isClean()`, is a plan/AGT-01 HOW) |

## 2. Scope

**In scope (WHAT) — data (`pixelart_creator/data/`, Qt-free):**
- A **palette-file parser** that reads the v1 text formats — `.gpl` (GIMP), `.hex` (plain
  hex list), `.pal` (JASC-PAL text) — and returns an ordered list of colours suitable for a
  `logic.palette.Palette`. Defensive parsing: reject malformed / oversized input with a domain
  exception (Article VII). *(REQ-DDI-DATA-001; CL-A6.)*
- An **image decoder** that reads `.png` / `.jpg` / `.jpeg` / `.bmp` / `.gif` into an **RGBA**
  `logic.pixel_buffer.PixelBuffer`, **bounds-checked** against `MAX_CANVAS_WIDTH`/
  `MAX_CANVAS_HEIGHT`; corrupt/oversized/out-of-bounds input raises a domain exception, never
  crashes (Article VII). *(REQ-DDI-DATA-002; CL-A3.)*
- A **file-type classifier**: a pure predicate mapping a path (extension, optionally content)
  to one of `{IMAGE, PROJECT, PALETTE, UNKNOWN}`, so the UI routes by **type not drop
  location**. *(REQ-DDI-DATA-003; CL-A1.)*
- **Reuse** of the shipped `.pixproj` loader (`project_io.load_project`) for the PROJECT
  branch — the importer does **not** re-implement project decoding. *(REQ-DDI-DATA-004.)*
- A **robust error contract** across every importer: malformed / oversized / out-of-bounds
  input is rejected with a domain exception; content is never `eval`/`exec`'d
  (Article VII). *(REQ-DDI-DATA-005.)*

**In scope (WHAT) — UI (`pixelart_creator/ui/`):**
- **Accept file-URL drops** onto the main window / canvas surface (drag-enter accepts a file
  drop; drop delivers the file paths). *(REQ-DDI-UI-001.)*
- **Route each dropped file by type** (REQ-DDI-DATA-003), not by where it landed on screen.
  *(REQ-DDI-UI-002; CL-A1.)*
- **IMAGE → new document tab** via the shipped new-document path (decoded RGBA `PixelBuffer`
  wrapped in a `Document`), **not** a layer. *(REQ-DDI-UI-003; user-resolved.)*
- **`.pixproj` → open as project**, guarded by a **Save / Discard / Cancel** prompt when the
  active document has unsaved changes; **Cancel aborts** the open. Reuses
  `open_document`/`load_project`. *(REQ-DDI-UI-004; CL-A4.)*
- **PALETTE → load into the active palette**, **replacing** it as **one undoable command** via
  the shipped undo path. *(REQ-DDI-UI-005; CL-A5.)*
- **UNKNOWN / unsupported type → graceful ignore** with a non-blocking notice; the app never
  crashes and continues processing the rest of a multi-file drop. *(REQ-DDI-UI-006; CL-A7.)*
- **Corrupt / oversized file → error notice, not a crash**: the DATA domain exception is caught
  and surfaced (toast/dialog); app state is left intact. *(REQ-DDI-UI-007.)*
- **Multi-file drop**: each file is routed **independently by type** in a stable order —
  multiple images → multiple new tabs; a `.pixproj` opens (with its dirty guard); palettes load
  (sequential replace). No artificial one-file restriction. *(REQ-DDI-UI-008; CL-A2.)*
- **a11y / i18n / both themes**: every new user-visible string (prompt, notice, error) is
  `tr()`-wrapped; the prompt dialog is keyboard-reachable with visible focus; correct in **both
  light and dark** themes (Article V). *(REQ-DDI-UI-009.)*

**Out of scope (this feature):**
- Image-as-**layer** import (user explicitly rejected it; a future "import as layer" is deferred).
- **Indexed** import of a paletted source image — images decode to **RGBA** (CL-A3); indexed
  conversion is the shipped convert-to-indexed path applied afterward.
- Binary Adobe palette formats **`.aco` / `.ase`** — deferred to a future iteration (CL-A6).
- **Export / save** side of the pipeline (that is the rest of Phase-7).
- Drag-and-drop **out** of the app, intra-canvas drag (that is REQ-NEW-C floating selection),
  or reordering tabs/layers by drag.
- New technology choices (stack fixed by S8); no plan / tasks / code (AGT-01 / AGT-03 / AGT-05);
  parser/decoder internals (AGT-03, grounded by the Researcher).

## 3. Story map & feature-label taxonomy

New feature-label: `import-drop` (P7), aligned to the roadmap Phase-7 export/pipeline family;
extensible to the export side without renaming.

### 3.1 User stories

- **US-A1 (Artist / drop an image).** As an artist, I want to **drag an image file from my file
  explorer onto the app** and have it open as a **new canvas** I can edit, so I can start from a
  reference or existing sprite without a File▸Open dance. →
  REQ-DDI-DATA-002, REQ-DDI-UI-001, -002, -003 · `import-drop` · P7
- **US-A2 (Artist / drop a project).** As an artist, I want to **drop a `.pixproj`** and have it
  **open as a project**, and be **warned before losing unsaved work**, so I never discard changes
  by accident. → REQ-DDI-DATA-004, REQ-DDI-UI-004 · `import-drop` · P7
- **US-A3 (Artist / drop a palette).** As an artist, I want to **drop a `.gpl` / `.hex` / `.pal`
  palette** and have it **load into my active palette** in one undoable step, so I can adopt a
  palette instantly and undo if I dislike it. →
  REQ-DDI-DATA-001, REQ-DDI-UI-005 · `import-drop` · P7
- **US-A4 (Artist / it never breaks).** As an artist, I want dropping an **unknown or corrupt
  file** to give me a clear message and **not crash** the app, so drag-drop is safe to try. →
  REQ-DDI-DATA-005, REQ-DDI-UI-006, -007 · `import-drop` · P7
- **US-A5 (Artist / drop several files).** As an artist, I want to **drop several files at once**
  and have each handled by its type, so a batch of references opens as multiple canvases. →
  REQ-DDI-DATA-003, REQ-DDI-UI-002, -008 · `import-drop` · P7
- **US-A6 (Everyone / accessible & localised).** As any user, I want the prompts and messages to
  be **keyboard-usable, translated, and legible in both themes**. →
  REQ-DDI-UI-009 · `a11y-i18n` · cross-cutting

### 3.2 Feature-label taxonomy (addition)

`import-drop` — P7, the drag-drop import family. Sits under the Phase-7 export/pipeline heading
and coexists with the future `export` label; no existing label renamed.

## 4. Functional requirements

Each REQ carries `traces:` to the dossier S-id(s) it realises and the user requirement
(REQ-NEW-A). Layer, owner agent, and acceptance scenarios are in `traceability.md`.

### 4.1 Data layer (`REQ-DDI-DATA-001..005`) — `pixelart_creator/data/` (Qt-free, NEW)

#### REQ-DDI-DATA-001 — Palette-file parser (`.gpl` / `.hex` / `.pal`)
`traces:` S7 (file I/O), S3 (palette); REQ-NEW-A; CL-A6
A **new** data-layer parser reads the v1 palette text formats and returns an **ordered list of
RGBA colours** (or a `logic.palette.Palette`): **`.gpl`** (GIMP palette — `GIMP Palette` header,
`R G B  name` rows, `#` comments), **`.hex`** (one `RRGGBB`/`#RRGGBB` per line), **`.pal`**
(JASC-PAL text — `JASC-PAL`/`0100`/count header then `R G B` rows). Colour count is bounds-checked
(reuse the palette-size limit; malformed rows, wrong header, or an oversized list raise a domain
exception — Article VII). The parser is **Qt-free** (Article I) and deterministic. The exact
per-format grammar and the parser API surface are HOW (AGT-01/AGT-03, grounded by
`docs/research-drag-drop-import.md`).

#### REQ-DDI-DATA-002 — Image decoder → RGBA `PixelBuffer`
`traces:` S1 (per-pixel grid), S7 (file I/O); REQ-NEW-A; CL-A3
A **new** decoder reads `.png` / `.jpg` / `.jpeg` / `.bmp` / `.gif` and returns a **`PixelBuffer`
in RGBA `ColorMode`** whose dimensions equal the source image's. It is **bounds-checked** against
`MAX_CANVAS_WIDTH` (7680) / `MAX_CANVAS_HEIGHT` (4320): an image exceeding either dimension is
**rejected** with a domain exception (never silently truncated). A corrupt / undecodable file
raises a domain exception. For a multi-frame `.gif`, the **first frame** is decoded (CL-A3 note).
Paletted/indexed source images decode to **RGBA** (CL-A3). The decode backend (`QImage` vs Pillow)
and its placement are HOW (AGT-01; must respect Article I — if it needs Qt it lives in `ui/`,
else `data/`, grounded by the Researcher).

#### REQ-DDI-DATA-003 — File-type classification (route by type)
`traces:` S7; REQ-NEW-A; CL-A1
A **pure** classifier maps a dropped file path to exactly one of `{IMAGE, PROJECT, PALETTE,
UNKNOWN}` from its extension (content-sniffing is an optional HOW refinement). `IMAGE` ⊇
{`.png`,`.jpg`,`.jpeg`,`.bmp`,`.gif`}; `PROJECT` = `.pixproj`; `PALETTE` ⊇ {`.gpl`,`.hex`,`.pal`};
everything else → `UNKNOWN`. Classification is **case-insensitive** and deterministic. Zero Qt.
This is the single source of truth the UI routes on (REQ-DDI-UI-002).

#### REQ-DDI-DATA-004 — Reuse the shipped `.pixproj` loader
`traces:` S7 (`.pixproj` JSON, Article VII); REQ-NEW-A
The PROJECT branch decodes a dropped `.pixproj` via the **shipped** `data/project_io.load_project`
— the importer **does not** re-implement project parsing (which already validates JSON, bounds,
and mode per Article VII). Any `ProjectError`/validation exception it raises is surfaced by
REQ-DDI-UI-007. This REQ exists to record the **reuse** trace (no new decode code).

#### REQ-DDI-DATA-005 — Robust, defensive error contract
`traces:` S7, Article VII; REQ-NEW-A
Every importer (REQ-DDI-DATA-001/-002 and the reused -004) **validates before use** and rejects
malformed, oversized, or out-of-bounds input by raising a **domain exception** — never a bare
crash, and file content is **never** passed to `eval`/`exec`. Exception types follow the Phase-1
domain-error convention (a shared base), so the UI can catch a single family and show one error
surface (REQ-DDI-UI-007). Deterministic; Qt-free.

### 4.2 UI layer (`REQ-DDI-UI-001..009`) — `pixelart_creator/ui/` (drag/drop + routing, NEW)

#### REQ-DDI-UI-001 — Accept file-URL drops
`traces:` S5 (canvas/app surface), S7; REQ-NEW-A
The main window / canvas surface **accepts a file-URL drag**: on drag-enter it indicates the drop
is acceptable when the payload carries file paths, and on drop it obtains the list of local file
paths. No drag-drop handling exists today — this is entirely new. The accept/decline affordance is
Qt wiring (HOW); the requirement is that a file drop is accepted and its paths captured.

#### REQ-DDI-UI-002 — Route by file type, not drop location
`traces:` S7; REQ-NEW-A; CL-A1
Each dropped path is classified (REQ-DDI-DATA-003) and dispatched to its branch: `IMAGE` →
REQ-DDI-UI-003; `PROJECT` → REQ-DDI-UI-004; `PALETTE` → REQ-DDI-UI-005; `UNKNOWN` → REQ-DDI-UI-006.
Routing is by **type only** — **where** on the window the file is dropped does **not** change the
behaviour (an image always opens a new document, per the user-resolved answer). *(CL-A1.)*

#### REQ-DDI-UI-003 — Image drop → NEW document tab (not a layer)
`traces:` S1, S5; REQ-NEW-A; user-resolved
A dropped IMAGE is decoded (REQ-DDI-DATA-002) into an RGBA `PixelBuffer`, wrapped in a new
`Document`, and opened as a **new canvas tab** via the shipped new-document path — **never** added
as a layer to the current document. The new tab becomes active. The source file is **not**
modified (import is read-only on disk).

#### REQ-DDI-UI-004 — `.pixproj` drop → open with dirty-save prompt
`traces:` S7; REQ-NEW-A; CL-A4
A dropped `.pixproj` opens as a project via the shipped `open_document` / `load_project`. If the
**active document has unsaved changes**, the app first shows a **Save / Discard / Cancel** prompt:
**Save** persists then opens; **Discard** opens without saving; **Cancel** aborts the open and
leaves everything unchanged. When the active document is **not** dirty (or none is open), the
project opens without a prompt. The dirty-prompt is **NEW** (no existing prompt to reuse); the
dirty-state source (e.g. the tab's `QUndoStack.isClean()`) and whether the project opens in a new
tab or replaces the active one are HOW (AGT-01) — this REQ fixes the **guard + three-way choice**.

#### REQ-DDI-UI-005 — Palette drop → load (replace) as one undoable command
`traces:` S3 (palette), S7 (reversible edit, C1/F1); REQ-NEW-A; CL-A5
A dropped PALETTE is parsed (REQ-DDI-DATA-001) and **replaces** the active document's palette. The
replacement is applied as **exactly one undoable command** through the shipped palette-edit undo
path (`ui/commands.py` over the tab's `QUndoStack`), so a single **Undo** restores the previous
palette (`apply ∘ undo = identity`). **Append** mode is deferred (CL-A5). If no document is open,
the drop is a graceful no-op with a notice.

#### REQ-DDI-UI-006 — Unknown / unsupported type → graceful ignore + notice
`traces:` S7; REQ-NEW-A; CL-A7
A dropped file classified `UNKNOWN` (or a supported extension whose content proves undecodable is
handled by REQ-DDI-UI-007) is **ignored without side effects**, and a **non-blocking notice**
(toast/status) tells the user the type is unsupported. The app never crashes. In a multi-file drop,
UNKNOWN files are skipped and the remaining files are still processed (REQ-DDI-UI-008).

#### REQ-DDI-UI-007 — Corrupt / oversized file → error notice, not a crash
`traces:` S7, Article VII; REQ-NEW-A
When a DATA importer raises a domain exception (corrupt image, malformed palette, oversized image,
invalid `.pixproj`), the UI **catches it and shows an error notice** (message identifies the file
and the problem); **application state is left intact** (no partial tab, no half-loaded palette).
The error surface is `tr()`-wrapped (REQ-DDI-UI-009). One bad file in a multi-file drop does not
abort the others (REQ-DDI-UI-008).

#### REQ-DDI-UI-008 — Multi-file drop routing
`traces:` S7, S5; REQ-NEW-A; CL-A2
A drop carrying **multiple files** processes each file **independently by type** in a **stable
order** (the order delivered by the drop): each `IMAGE` opens its own new tab; each `PALETTE` loads
(sequential replace — the **last** palette dropped is the resulting active palette, each its own
undo step); each `PROJECT` opens (each honouring its dirty guard); `UNKNOWN`/failed files are
skipped with a notice (REQ-DDI-UI-006/-007) without stopping the batch. No artificial one-file
restriction. A drop of **zero** files is a no-op.

#### REQ-DDI-UI-009 — a11y, i18n, both themes
`traces:` S5, F5/F6, Article V; REQ-NEW-A
Every new user-visible string — the Save/Discard/Cancel prompt, unsupported-type notice, and error
messages — is `tr()`-wrapped; any new dialog is **keyboard-reachable** with a visible focus
indicator and re-translates on `QEvent.LanguageChange`; all new UI is correct in **both light and
dark themes** (Article V). Verified by `string_audit_check` + pytest-qt in both themes.

## 5. Non-functional requirements

- **NFR-1 (Purity, S11 / Article I).** The palette parser, image decoder and file-type classifier
  import **zero** Qt; drag/drop event handling and the prompt/notice UI live in `ui/`. The
  image-decode backend must respect this: a Qt-based decode lives in `ui/`, a Qt-free decode in
  `data/` (AGT-01 placement).
- **NFR-2 (Determinism).** The palette parser, image decoder and classifier produce identical
  output for identical input (test-asserted).
- **NFR-3 (Validated input / security, S7 / Article VII).** All imported content is validated and
  size/bounds-checked before use; malformed/oversized/out-of-bounds input is rejected with a domain
  exception; content is never `eval`/`exec`'d; the reused `.pixproj` path keeps its Article VII
  guarantees.
- **NFR-4 (Bounds, S1 / Article II).** Image dimensions are checked against `MAX_CANVAS_WIDTH` /
  `MAX_CANVAS_HEIGHT` from `logic/constants.py`; the palette-size ceiling reuses the existing
  palette constant. **No magic numbers** — any new tuning value lives only in `constants.py` (§9).
- **NFR-5 (Reversibility).** The palette-load replacement is exactly one `QUndoCommand`
  (`apply ∘ undo = identity`). Image-drop and project-open create/open documents (a new
  editing context), consistent with the shipped File▸Open / New behaviour.
- **NFR-6 (Non-destructive on disk).** Import is **read-only** on the source file; dropping a file
  never modifies the file on disk.
- **NFR-7 (Coverage, S13 / Article IV).** ≥90 % line / ≥80 % branch per package; data parsers/
  decoder/classifier via pytest (+ Hypothesis for parser robustness / bounds invariants); UI drag/
  drop, routing, prompt and notices via pytest-qt in **both themes**, headless
  (`QT_QPA_PLATFORM=offscreen`).
- **NFR-8 (a11y + i18n + both themes, Article V).** New strings `tr()`-wrapped; new dialog
  keyboard-reachable + re-translating; both themes verified.
- **NFR-9 (Robustness / no-crash).** No dropped input — unknown, corrupt, oversized, empty drop,
  or no-open-document — crashes the app; each degrades to a notice and leaves state intact.

## 6. Non-goals (explicit)

- No image-as-**layer** import (user-rejected; future "import as layer" deferred).
- No **indexed** decode of a paletted source image (RGBA only, CL-A3).
- No binary Adobe palettes **`.aco` / `.ase`** (deferred, CL-A6).
- No **export** path (rest of Phase-7).
- No drag **out** of the app, no intra-canvas floating-selection drag (REQ-NEW-C), no tab/layer
  drag-reorder.
- No new technology choices (S8); no plan/tasks/code; no parser/decoder internals (AGT-03 +
  Researcher).

## 7. Dependencies

**REUSED shipped code (hard):**
- `ui/main_window.py` — `open_document(path)` / `new_document(...)` / `_add_document_tab(...)`
  (image-drop and project-open route through these); `save_document(path)` (the Save branch of the
  dirty prompt); `_bind_palette_workflows` → the tab's `record.stack` (the undoable palette edit).
- `data/project_io.py` — `load_project` (PROJECT decode) / `save_project` (Save branch).
- `logic/pixel_buffer.py` (`PixelBuffer`, `ColorMode.RGBA`), `logic/palette.py` (`Palette`),
  `logic/document.py` (`Document`) — the import targets.
- `logic/constants.py` — `MAX_CANVAS_WIDTH` / `MAX_CANVAS_HEIGHT`; the palette-size ceiling
  (NFR-4).

**NEW (this feature builds):**
- `data/` palette-file parser (REQ-DDI-DATA-001), image decoder (REQ-DDI-DATA-002), file-type
  classifier (REQ-DDI-DATA-003) — indicative modules e.g. `data/palette_io.py`, `data/image_io.py`
  (final names/placement = AGT-01).
- `ui/` file-URL drag/drop handling, type routing, the Save/Discard/Cancel prompt, and the
  unsupported/error notice surface (REQ-DDI-UI-001..009).

**Research dependency (HOW only):** `docs/research-drag-drop-import.md` (concurrent) grounds the
`.gpl`/`.hex`/`.pal` grammars and the image-decode approach (QImage vs Pillow). This spec does not
wait on it — it fixes the WHAT; AGT-01/AGT-03 consume the findings at plan/implement time.

**Downstream:** AGT-01 (`sdd-plan` — fixes parser/decoder APIs + placement, dirty-state source,
new-tab-vs-replace, decode backend); AGT-06 (Gherkin → pytest-qt/pytest acceptance tests);
AGT-03/04 (data + tests); AGT-05 (UI + pytest-qt); AGT-07 (i18n of new strings); AGT-10
(no perf-critical path expected — import is not a per-frame operation).

## 8. Recommended slicing (for the orchestrator)

A data→UI split mirrors prior phases (UI binds to data):

- **Slice A-A — Import DATA** (`REQ-DDI-DATA-001..005`): the palette parser, image decoder,
  file-type classifier and shared error contract under `data/`, + constants review + pytest
  (Hypothesis for parser robustness / bounds). Ships first — the UI binds to it. Depends on the
  Researcher findings for the parser grammars / decode backend.
- **Slice A-B — Import UI** (`REQ-DDI-UI-001..009`): file-URL drag/drop handling, type routing,
  image→new-tab, `.pixproj`→open + dirty prompt, palette→undoable replace, unsupported/error
  notices, multi-file routing, + pytest-qt (both themes). Depends on A-A + the shipped
  open/new-document/palette-undo paths.

Final ordering is AGT-01 / orchestrator's call.

## 9. New constants (for AGT-03 — Article II / S12)

- Image bounds reuse `MAX_CANVAS_WIDTH` / `MAX_CANVAS_HEIGHT` (already in `constants.py`) — **no
  new constant**.
- The palette-size ceiling reuses the existing palette-size constant (the `MAX_PALETTE_SIZE=256`
  moved into `constants.py` per the 2026-07-02 S12 remediation) — **no new constant**.
- The **accepted-extension sets** (`{.png,.jpg,.jpeg,.bmp,.gif}`, `{.gpl,.hex,.pal}`, `.pixproj`)
  are format identifiers, not numeric tuning values — Article II governs numeric tuning params, not
  format string literals (cf. the 2026-07-02 intrinsic-literal ADR exemption). AGT-01 to rule on
  their home (a module-level constant in the classifier is natural). If any **numeric** parser
  limit beyond the palette ceiling is introduced, it lives **only** in `constants.py`.

## 10. Clarifications (sdd-clarify — resolved defaults, per A2-D2 Branch B)

All open points are resolved with grounded defaults and recorded as category-1 decisions.
**No item required SUSPEND** — the candidate (palette format set) is resolvable against the
common pixel-art text formats + the deferred-`.aco`/`.ase` note; the parser internals are HOW
(Researcher/AGT-03).

- **CL-A1 — Routing is by FILE TYPE, not drop location (confirmed).** Each dropped file is routed
  by its classified type (REQ-DDI-DATA-003), regardless of **where** on the window it is dropped.
  Grounded: the user-resolved answer makes an IMAGE **always** a new document — so drop location
  cannot carry meaning. *(REQ-DDI-UI-002.)*
- **CL-A2 — Multi-file drop = per-file, type-routed, stable order (default).** No one-file
  restriction. Multiple images → multiple new tabs (in drop order); mixed types each routed by
  type; multiple palettes apply as sequential replaces (the **last** dropped palette is the
  resulting active palette, each its own undo step); each `.pixproj` opens honouring its dirty
  guard; UNKNOWN/failed files are skipped with a notice without aborting the batch. A zero-file
  drop is a no-op. *(REQ-DDI-UI-008.)*
- **CL-A3 — Indexed/paletted source image → decode to RGBA (default).** An image drop always
  creates an **RGBA** document; a paletted PNG/GIF is expanded to RGBA on decode. Indexed import is
  deferred (the user can apply the shipped convert-to-indexed afterward). For a multi-frame GIF the
  **first frame** is imported (animated-GIF import is a Phase-5/7 concern, deferred). Grounded:
  RGBA is the app's default document mode and avoids inventing a palette at import time.
  *(REQ-DDI-DATA-002, REQ-DDI-UI-003.)*
- **CL-A4 — `.pixproj` drop dirty guard = Save / Discard / Cancel (user-resolved).** If the active
  document is dirty, prompt before opening; **Cancel** aborts, **Save** persists then opens,
  **Discard** opens without saving. No prompt when nothing is dirty. The dirty-prompt is **NEW**
  (no existing prompt to reuse — `open_document` currently opens unconditionally); the dirty-state
  source (e.g. `QUndoStack.isClean()`) and whether the project opens in a new tab or replaces the
  active one are HOW (AGT-01). Not suspended — the three-way behaviour is fully specified by the
  user's resolved answer. *(REQ-DDI-UI-004.)*
- **CL-A5 — Palette load = REPLACE the active palette, undoable (default).** A dropped palette
  **replaces** the active palette in **one** undoable command (the shipped palette-edit undo path
  makes palette changes reversible), so Undo restores the prior palette. **Append** is deferred to
  a future iteration. Grounded: "load into the active palette" reads as adopting that palette; the
  shipped undo path guarantees safety. *(REQ-DDI-UI-005.)*
- **CL-A6 — Palette format set v1 = `.gpl` / `.hex` / `.pal`; defer `.aco` / `.ase` (confirmed).**
  The v1 set is the common **text** pixel-art palette formats: GIMP `.gpl`, plain `.hex`, JASC
  `.pal`. Binary Adobe `.aco` / `.ase` are **deferred** (noted as future). **Not suspended** — this
  set covers the common pixel-art interchange need; the exact grammars are grounded by the
  Researcher (`docs/research-drag-drop-import.md`) and implemented by AGT-03. *(REQ-DDI-DATA-001.)*
- **CL-A7 — Unknown/unsupported drop = graceful ignore + non-blocking notice (default).** An
  unsupported type is ignored (no side effect) with a toast/status notice; the app never blocks or
  crashes; in a multi-file drop the rest still process. *(REQ-DDI-UI-006.)*

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour, phrased for **headless** testing (data via pytest [+
Hypothesis], UI via pytest-qt in **both themes**, `QT_QPA_PLATFORM=offscreen`). Robustness
(no-crash) and reversibility (palette undo) are called out per REQ-NEW-A. Scenario ↔ REQ ↔ (future)
test mapping is in `traceability.md`. **Every functional REQ has ≥1 scenario; 0 uncovered.**

### Feature: Palette-file parser (REQ-DDI-DATA-001)
```gherkin
Scenario: SC-D001-1 parse a valid .gpl (GIMP) palette into an ordered colour list
  Given a well-formed .gpl file with a "GIMP Palette" header and N colour rows
  When I parse it
  Then I get N colours in file order

Scenario: SC-D001-2 parse a valid .hex palette (one RRGGBB per line)
  Given a .hex file with one hex colour per line (with or without a leading '#')
  When I parse it
  Then I get the colours in file order

Scenario: SC-D001-3 parse a valid .pal (JASC-PAL text) palette
  Given a JASC-PAL file with the JASC-PAL / 0100 / count header and R G B rows
  When I parse it
  Then I get the declared colours in order

Scenario: SC-D001-4 a malformed palette file raises a domain exception (no crash)
  Given a palette file with an invalid header or a non-numeric colour row
  When I parse it
  Then a palette-import domain exception is raised

Scenario: SC-D001-5 a palette exceeding the palette-size ceiling is rejected
  Given a palette file declaring more colours than the palette-size limit
  When I parse it
  Then a domain exception is raised (never truncated silently)
```

### Feature: Image decoder → RGBA PixelBuffer (REQ-DDI-DATA-002)
```gherkin
Scenario: SC-D002-1 decode a valid PNG into an RGBA PixelBuffer of the image's size
  Given a valid WxH PNG
  When I decode it
  Then I get a PixelBuffer in RGBA mode of size WxH

Scenario: SC-D002-2 decode jpg/jpeg/bmp/gif into RGBA
  Examples: .jpg | .jpeg | .bmp | .gif
  Given a valid image of that type
  When I decode it
  Then I get an RGBA PixelBuffer

Scenario: SC-D002-3 a paletted/indexed source image decodes to RGBA (CL-A3)
  Given a paletted PNG or GIF
  When I decode it
  Then the result is an RGBA PixelBuffer (palette expanded)

Scenario: SC-D002-4 the first frame of a multi-frame GIF is decoded (CL-A3)

Scenario: SC-D002-5 an image exceeding MAX_CANVAS_WIDTH/HEIGHT is rejected (bounds, NFR-4)
  Given an image wider than 7680 or taller than 4320
  When I decode it
  Then a domain exception is raised (not truncated)

Scenario: SC-D002-6 a corrupt/undecodable image raises a domain exception (no crash)
```

### Feature: File-type classification (REQ-DDI-DATA-003)
```gherkin
Scenario: SC-D003-1 classify by extension into IMAGE / PROJECT / PALETTE / UNKNOWN
  Examples: foo.png->IMAGE | a.jpg->IMAGE | s.bmp->IMAGE | g.gif->IMAGE | p.pixproj->PROJECT | q.gpl->PALETTE | r.hex->PALETTE | t.pal->PALETTE | z.txt->UNKNOWN

Scenario: SC-D003-2 classification is case-insensitive (.PNG, .GPL classify like .png, .gpl)

Scenario: SC-D003-3 classification is deterministic and Qt-free (via check_layering) [spec-only]
```

### Feature: Reuse the shipped .pixproj loader (REQ-DDI-DATA-004)
```gherkin
Scenario: SC-D004-1 a dropped .pixproj is decoded via the shipped load_project (no re-implementation)
  Given a valid .pixproj file
  When the PROJECT branch loads it
  Then it uses data/project_io.load_project and yields the same Document as File>Open

Scenario: SC-D004-2 an invalid .pixproj surfaces load_project's validation exception (Article VII)
```

### Feature: Defensive error contract (REQ-DDI-DATA-005)
```gherkin
Scenario: SC-D005-1 every importer rejects malformed input with a domain exception, never a bare crash
  Examples: palette | image | pixproj

Scenario: SC-D005-2 imported content is never passed to eval/exec (defensive parse) [spec-only, review]

Scenario: SC-D005-3 import domain exceptions share a common base so the UI catches one family
```

### Feature: Accept file-URL drops (REQ-DDI-UI-001)
```gherkin
Scenario: SC-U001-1 dragging files over the window is accepted as a droppable payload (both themes)
  Given the app window
  When a file-URL drag enters it
  Then the drop is indicated as acceptable

Scenario: SC-U001-2 dropping delivers the local file paths to the router
```

### Feature: Route by file type, not drop location (REQ-DDI-UI-002)
```gherkin
Scenario: SC-U002-1 an image dropped anywhere on the window opens a new document (location-independent, CL-A1)

Scenario: SC-U002-2 each dropped file is dispatched to its type branch (IMAGE/PROJECT/PALETTE/UNKNOWN)
```

### Feature: Image drop → new document tab (REQ-DDI-UI-003)
```gherkin
Scenario: SC-U003-1 dropping an image opens it as a NEW document tab, not a layer (both themes)
  Given an open document with one layer
  When I drop a valid image
  Then a new document tab is created and becomes active
  And no layer is added to the previously active document

Scenario: SC-U003-2 the new document is RGBA at the image's dimensions (CL-A3)

Scenario: SC-U003-3 dropping an image does not modify the source file on disk (NFR-6)
```

### Feature: .pixproj drop → open with dirty prompt (REQ-DDI-UI-004)
```gherkin
Scenario: SC-U004-1 dropping a .pixproj with no unsaved changes opens it without a prompt
  Given the active document has no unsaved changes
  When I drop a valid .pixproj
  Then it opens with no save prompt

Scenario: SC-U004-2 dropping a .pixproj while dirty prompts Save/Discard/Cancel
  Given the active document has unsaved changes
  When I drop a valid .pixproj
  Then a Save / Discard / Cancel prompt appears

Scenario: SC-U004-3 choosing Cancel aborts the open and leaves state unchanged

Scenario: SC-U004-4 choosing Save persists the current document then opens the dropped project

Scenario: SC-U004-5 choosing Discard opens the dropped project without saving
```

### Feature: Palette drop → undoable replace (REQ-DDI-UI-005)
```gherkin
Scenario: SC-U005-1 dropping a .gpl replaces the active palette in one undoable step
  Given an open document with an active palette
  When I drop a valid .gpl palette
  Then the active palette is replaced by the dropped colours
  And a single Undo restores the previous palette

Scenario: SC-U005-2 dropping a .hex palette replaces the active palette (undoable)

Scenario: SC-U005-3 dropping a .pal palette replaces the active palette (undoable)

Scenario: SC-U005-4 REVERSIBILITY: palette-load then undo restores the prior palette (apply∘undo = identity)

Scenario: SC-U005-5 dropping a palette with no open document is a graceful no-op with a notice
```

### Feature: Unknown type → graceful ignore + notice (REQ-DDI-UI-006)
```gherkin
Scenario: SC-U006-1 dropping an unsupported type is ignored with a non-blocking notice (no crash, both themes)
  Given a file with an unsupported extension (e.g. .txt)
  When I drop it
  Then it is ignored and a notice states the type is unsupported
```

### Feature: Corrupt/oversized file → error notice not crash (REQ-DDI-UI-007)
```gherkin
Scenario: SC-U007-1 dropping a corrupt image shows an error notice and leaves state intact (no crash)
  Given a corrupt image file
  When I drop it
  Then an error notice identifies the failure
  And no new tab is created and the app does not crash

Scenario: SC-U007-2 dropping an oversized image (> MAX_CANVAS_*) shows an error notice, opens no tab

Scenario: SC-U007-3 dropping a malformed palette shows an error notice; the active palette is unchanged

Scenario: SC-U007-4 dropping an invalid .pixproj shows an error notice; no document is opened
```

### Feature: Multi-file drop routing (REQ-DDI-UI-008)
```gherkin
Scenario: SC-U008-1 dropping several images opens one new tab per image (stable order)
  Given three valid images dropped together
  When the drop is processed
  Then three new document tabs are created

Scenario: SC-U008-2 a mixed drop routes each file by its type (image->tab, palette->load, pixproj->open)

Scenario: SC-U008-3 one bad file in a multi-file drop is skipped with a notice; the rest still process

Scenario: SC-U008-4 dropping several palettes leaves the LAST dropped palette active (each its own undo step) (CL-A2)

Scenario: SC-U008-5 dropping zero files is a no-op
```

### Feature: a11y / i18n / both themes (REQ-DDI-UI-009)
```gherkin
Scenario: SC-U009-1 the dirty prompt and all notices are tr()-wrapped (string_audit_check) [spec-only/gate]

Scenario: SC-U009-2 the dirty prompt is keyboard-reachable with visible focus and re-translates on LanguageChange

Scenario: SC-U009-3 the prompt and notices are legible in both light and dark themes
```

---

## 12. Exit / status

- Forward pre-implementation spec authored for **REQ-NEW-A** (drag-and-drop import), grounded in
  the orchestrator-confirmed NEW-vs-REUSED recon (§1) — palette parser, image decoder and drag-drop
  handling are NEW; `.pixproj` open, new-document/tab and undoable palette-edit are REUSED.
- **14 REQ-IDs**: 5 DATA (`REQ-DDI-DATA-001..005`) + 9 UI (`REQ-DDI-UI-001..009`).
- **~40 Gherkin scenarios** (data SC-D001..005 + UI SC-U001..009); every functional REQ has ≥1
  scenario; traceability shows **0 uncovered** (`traceability.md`).
- **7 clarify decisions** (CL-A1..A7) recorded as category-1 defaults; **no SUSPEND** — the palette
  format set is resolvable (v1 = `.gpl`/`.hex`/`.pal`, defer `.aco`/`.ase`); routing-by-type,
  multi-file, indexed→RGBA, dirty-prompt and replace-palette all have grounded defaults.
- Robustness (no-crash on unknown/corrupt/oversized/empty) and reversibility (undoable palette
  replace) acceptance included; import is read-only on disk and bounds-checked (Article VII).
- Research (`docs/research-drag-drop-import.md`) grounds parser grammars + decode backend as HOW
  (AGT-01/AGT-03) — the spec does not block on it.
- Recommended slicing: **A-A data → A-B UI** — §8.
- **STATUS: COMPLETED.**
