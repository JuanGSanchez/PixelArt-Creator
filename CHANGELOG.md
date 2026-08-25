# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Workspace and canvas-border theme roles, in both the light and dark themes, so the drawing surface is visually distinguishable from the space around it (REQ-CGS-UI-005, REQ-CGS-UI-006).
- The pixel grid overlay is now on by default for a new document (REQ-CGS-UI-003 – REQ-CGS-UI-010).
- A Tetradic (four-colour) harmony row in the colour wheel (REQ-CGS-LOGIC-001, REQ-CGS-UI-011).
- A confirmation before a floating move overwrites occupied pixels, with a per-project "don't ask again" (REQ-P2-UI-037, REQ-P2-LOGIC-037, REQ-P2-DATA-030).
- File ▸ New now asks for a document size, and a new Image ▸ Canvas Size... dialog resizes the current document, both bounded by the existing 8K ceiling.
- Spanish translations for 19 user-visible strings that had been shipped wrapped for translation but were never extracted (REQ-CGS-LOGIC-001).

### Changed

- Zoom no longer goes below 100%; a document larger than the window is explored by panning instead. Below 100% a pixel can fall between screen samples and not be drawn at all, which was one of the causes of a drawing appearing to vanish until something else forced a redraw (REQ-CGS-UI-003 – REQ-CGS-UI-010, ADR-0063).
- In the colour wheel, a related colour is now applied by double-click; a single click selects a swatch without applying it. Keyboard activation (Space/Enter) is unchanged (REQ-CGS-LOGIC-001, REQ-CGS-UI-011).

### Fixed

- Drawing tools (pencil, eraser, line) could appear to do nothing on a canvas rendered through the OpenGL viewport; the canvas's update mode now follows whichever viewport is actually installed. Believed fixed, unconfirmed on real desktop hardware — no headless test can prove a GL surface flushes to a screen, and a user report against this remains open (REQ-CGS-UI-001, REQ-CGS-UI-002).
- The checker pattern could be mistaken for the pixel grid itself. One alternating square is now one document pixel, clipped to the canvas, drawn on a workspace ground with a border (REQ-CGS-UI-003 – REQ-CGS-UI-010).
- The ruler's cursor readout double-counted the pan offset, reading up to several document pixels off from the actual cursor position (REQ-CGS-UI-003 – REQ-CGS-UI-010).
- Frame thumbnails in the timeline dropped one pixel in four when downscaled, so a drawn pixel could be silently absent from its own thumbnail (REQ-CGS-UI-012).
- A canvas that could not be resized: the resizing capability already existed in the document and scene layers but had no caller anywhere in the application, so every document stayed at its default size for the life of the app. File ▸ New and Image ▸ Canvas Size... now reach it.

