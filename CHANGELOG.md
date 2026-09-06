# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The user-authored pixel-art logo now appears on both README banners and in the opening topic of the in-app User Guide, in English and Spanish alike.
- Workspace and canvas-border theme roles, in both the light and dark themes, so the drawing surface is visually distinguishable from the space around it (REQ-CGS-UI-005, REQ-CGS-UI-006).
- The pixel grid overlay is now on by default for a new document (REQ-CGS-UI-003 – REQ-CGS-UI-010).
- A Tetradic (four-colour) harmony row in the colour wheel (REQ-CGS-LOGIC-001, REQ-CGS-UI-011).
- A confirmation before a floating move overwrites occupied pixels, with a per-project "don't ask again" (REQ-P2-UI-037, REQ-P2-LOGIC-037, REQ-P2-DATA-030).
- File ▸ New now asks for a document size, and a new Image ▸ Canvas Size... dialog resizes the current document, both bounded by the existing 8K ceiling.
- Spanish translations for 19 user-visible strings that had been shipped wrapped for translation but were never extracted (REQ-CGS-LOGIC-001).

### Changed

- Zoom no longer goes below 100%; a document larger than the window is explored by panning instead. Below 100% a pixel can fall between screen samples and not be drawn at all, which was one of the causes of a drawing appearing to vanish until something else forced a redraw (REQ-CGS-UI-003 – REQ-CGS-UI-010, ADR-0063).
- In the colour wheel, a related colour is now applied by double-click; a single click selects a swatch without applying it. Keyboard activation (Space/Enter) is unchanged (REQ-CGS-LOGIC-001, REQ-CGS-UI-011).
- The test tree is now one folder, `testing/`, holding both the harness and the tests, matching the orchestration container's own layout: `tests/` moved to `testing/suites/` (per-area subfolders — logic, data, ui, backend, deploy, githooks, scripts, memory_view — kept, since agent charters and the surface-ownership gate partition ownership by exactly those paths), every reference repointed (`pyproject.toml` testpaths and setuptools exclude, both CI pytest invocation sites, `testing/testing.json`, intra-suite imports, and `Path(__file__).parents[N]` depth math), and `testing/__init__.py` restored so an explicitly-imported `conftest` and pytest's own plugin load resolve to one module. `web_viewer/tests/` was left in place: it stays independently cloneable and its Python + Node ESM hybrid suite has no place in a pytest tree. Verified with the full suite: 7591 passed, 2 skipped, 2 xfailed, 0 failed, coverage 93% statements / 86% branches, collection 7610 with 0 errors — identical to the pre-move baseline.

### Fixed

- Drawing tools (pencil, eraser, line) could appear to do nothing on a canvas rendered through the OpenGL viewport; the canvas's update mode now follows whichever viewport is actually installed. Believed fixed, unconfirmed on real desktop hardware — no headless test can prove a GL surface flushes to a screen, and a user report against this remains open (REQ-CGS-UI-001, REQ-CGS-UI-002).
- The checker pattern could be mistaken for the pixel grid itself. One alternating square is now one document pixel, clipped to the canvas, drawn on a workspace ground with a border (REQ-CGS-UI-003 – REQ-CGS-UI-010).
- The ruler's cursor readout double-counted the pan offset, reading up to several document pixels off from the actual cursor position (REQ-CGS-UI-003 – REQ-CGS-UI-010).
- Frame thumbnails in the timeline dropped one pixel in four when downscaled, so a drawn pixel could be silently absent from its own thumbnail (REQ-CGS-UI-012).
- A canvas that could not be resized: the resizing capability already existed in the document and scene layers but had no caller anywhere in the application, so every document stayed at its default size for the life of the app. File ▸ New and Image ▸ Canvas Size... now reach it.
- Right-clicking while the colour hub was already open did not close it: the hub appeared to simply move to the new cursor position instead. A right-click now dismisses the hub from anywhere — outside it, on top of it, or delivered by the Menu key / Shift+F10, which now toggles the hub the same way a mouse right-click does, preserving keyboard parity with the mouse (A11Y-COLHUB-1). A right-click while the hub is closed still opens it exactly as before. The previous guard depended on a close event that this platform's popup never actually fires; the replacement recognises the closing press by its own identity instead of by timing, so it does not depend on event ordering or an elapsed interval. Verified with pytest-qt and with an instrumented offscreen probe; a genuine right-click on real desktop hardware is the one confirmation an automated test cannot itself supply, and is left for the maintainer's own check.

