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
