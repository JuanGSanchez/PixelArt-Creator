# ADR-0010 — Drag-drop import: image-decode placement, dependency, and error model

- Status: Accepted (2026-07-03)
- Author: AGT-01 (Architecture)
- Feature: `drag-drop-import` (REQ-NEW-A)
- Traces: REQ-P7-DATA-002 (image decoder), REQ-P7-DATA-005 (shared error contract),
  Article I (three-layer / S11), Article VII (validated I/O)
- Grounded by: `docs/research-drag-drop-import.md` §2 (QImage vs Pillow), §2.2 (Pillow MIT-CMU licence)

## Context

Drag-drop import must decode `.png/.jpg/.jpeg/.bmp/.gif` into an RGBA
`logic.pixel_buffer.PixelBuffer`. The Researcher established two viable backends:

- **QImage (PySide6/Qt):** reads all four formats out of the box; **no new dependency**
  (PySide6 is already required). Being Qt, any QImage decode **must** live in `ui/`
  (Article I forbids Qt in `logic/`/`data/`). Scanlines are ≥32-bit aligned, so a robust
  reader must honour `bytesPerLine()` and use `Format_RGBA8888` for deterministic byte order.
- **Pillow (PIL):** Qt-free, so a decode could live in `logic/` and be unit-tested without Qt —
  but it is a **new MIT-CMU C-extension runtime dependency** needing maintainer sign-off
  (the "Apache-2.0-compatible" reading is informal, not a legal opinion).

Import is not a per-frame/performance path, so the "pure-Python testability" upside of Pillow
is modest.

A second concern: REQ-P7-DATA-005 wants every importer to reject bad input with a **domain
exception** sharing one base so the UI catches a single family — even though the image decoder
now lives in `ui/`.

## Decision

1. **Decode images with `QImage` in `ui/image_import.py`. Add no new dependency.** The domain
   model (`PixelBuffer`, `Document`) stays in `logic/`. The `ui/` decoder normalises QImage to a
   **packed `Format_RGBA8888`** `(H, W, 4)` uint8 buffer — slicing each row
   `[y*bytesPerLine : y*bytesPerLine + width*4]` to strip 32-bit row padding — and constructs the
   `logic.PixelBuffer`. No Qt object crosses into `logic/`.
2. **Bounds-check `width()/height()` against `MAX_CANVAS_WIDTH`/`MAX_CANVAS_HEIGHT` before buffer
   construction**, rejecting oversized images with `ImageImportError` (never truncate). Multi-frame
   GIF → first frame only; paletted sources → expanded to RGBA on `convertToFormat`.
3. **Shared error base `FileImportError(ValueError)` lives in the Qt-free `data/file_import.py`.**
   `PaletteImportError` and `ImageImportError` subclass it. `ImageImportError` is *defined* in
   `data/` (an exception class carries no Qt) but *raised* from `ui/image_import.py` — keeping the
   whole error family Qt-free and catchable as one base. The shipped `data/project_io.ProjectIOError`
   is **not** re-parented (avoid touching shipped code); the UI router catches
   `(FileImportError, ProjectIOError)`.

## Consequences

- **Positive:** zero new runtime dependency; no maintainer licence sign-off required; Article I
  intact (Qt confined to `ui/`); deterministic cross-platform byte order; one Qt-free error family;
  `check_layering`/`check_cycles` stay clean (the only new Qt consumer is in `ui/`).
- **Negative / accepted:** the image decoder cannot be unit-tested without a Qt runtime (it is
  covered by pytest-qt headless, `QT_QPA_PLATFORM=offscreen`); callers must remember the
  `bytesPerLine()` stride discipline (frozen in plan §4 and this ADR).
- **Reversal path:** if a future need makes a Qt-free `logic/` decode worthwhile, adopting Pillow is
  a conscious, traceable change — supersede this ADR, add the MIT-CMU dependency with maintainer
  sign-off, and move the decoder to `logic/`.

## Erratum (2026-08-16) — requirement ids: the `REQ-P7-*` citations predate the 2026-07-30 re-allocation

*Immutable-append. The original text above is retained unchanged as the record of what was written on
2026-07-03; this erratum corrects only the **requirement identifiers** it cites. No decision, no
consequence and no layering ruling changes.*

**Provenance.** The 2026-08-16 spec-verification audits — `audit-spec-drag-drop-import-20260816.md`
(F-1, F-2) and `audit-spec-phase-7-export-20260816.md` (ERRATUM), which reach the finding
independently; consolidated as CF-76, remediation item R-01.

On **2026-07-30** this feature's own requirements were re-allocated **1:1** out of the `REQ-P7-*`
range into its own `REQ-DDI-*` prefix — same order, requirement text unchanged
(`specs/drag-drop-import/spec.md` §1, REQ-ID-range row: `REQ-DDI-DATA-001..005`,
`REQ-DDI-UI-001..009`). `phase-7-export` **owns the `REQ-P7-*` range by name** and allocates
`REQ-P7-DATA-001..004` only — it allocates **no `-005`**. Both ids cited above therefore mis-resolve
today:

| Cited in this ADR | What it resolves to now | Read instead |
| --- | --- | --- |
| `REQ-P7-DATA-002 (image decoder)` — Traces line | phase-7's **"Engine-preset artifacts are written (Unity / Godot)"** (`write_engine_preset`, 9 tests) — a *different, live* requirement | **`REQ-DDI-DATA-002`** |
| `REQ-P7-DATA-005 (shared error contract)` — Traces line **and** Context §("A second concern") | **nothing** — phase-7's DATA range stops at `004`, so the id is unallocated anywhere | **`REQ-DDI-DATA-005`** |

**Reader guidance.** Wherever this ADR says `REQ-P7-DATA-002`, read `REQ-DDI-DATA-002`; wherever it
says `REQ-P7-DATA-005`, read `REQ-DDI-DATA-005`. This ADR cites **no** `REQ-P7-UI-*` id and **no**
requirement range, so no further substitution applies. The spec's "cross-feature citations keep their
original ids" clause does **not** rescue these two: they are drag-drop-import's *own* requirements,
not citations of phase-7's.

**Blast radius.** Documentation-only — no shipped code and no test resolves `REQ-P7-DATA-005`, and the
`ui/image_import.py` decode placement, the `FileImportError` family in `data/file_import.py` and the
Article I layering ruling are all unaffected. The parallel mis-citation in `docs/CHANGELOG.md` (the
drag-drop entry attributing the feature to `REQ-P7-DATA-001..005` + `REQ-P7-UI-001..009`; correct:
`REQ-DDI-DATA-001..005` + `REQ-DDI-UI-001..009`) is AGT-08's to correct and is **not** part of this
erratum.
