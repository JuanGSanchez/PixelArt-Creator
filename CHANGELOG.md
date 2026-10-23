# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-10-23

### Added

- Three interface styles, each in a Light and a Dark mode: **Washi & Kintsugi** (the default, in Light), **Edo Night** and **Arcade Kikko**. They are chosen from a new **Style** submenu of the **Theme** menu, beside the Light and Dark choice. Every choice applies at once and is remembered between launches; a stored value the app does not recognise falls back to the defaults. Every colour is defined once, by role, with the same roles in all six combinations, and a contrast check covers all six (REQ-VI-UI-001, REQ-VI-UI-002, REQ-VI-UI-003, REQ-VI-UI-004, REQ-VI-BUILD-001).
- Pixel-art chrome drawn by the app itself: pixel frames on the controls, dialogs and docks, corner ornaments (gold in Light, red in Dark) kept clear of text and panel controls, and a faint pattern on two empty areas only, the tool toolbar and the transport row. A selected or checked control no longer relies on colour alone to show its state (REQ-VI-UI-006, REQ-VI-UI-007, REQ-VI-UI-008, REQ-VI-UI-009, REQ-VI-UI-010, REQ-VI-UI-011).
- **Nifen Art**, an original pixel typeface in Regular and Bold on a 12 px grid, bundled with the app and used for the interface text. It is licensed under the SIL Open Font License 1.1 with the Reserved Font Name "Nifen Art", and every copy carries the licence. Its hiragana are adapted from Ark Pixel Font by TakWolf (also OFL 1.1); every other glyph is original. Text is drawn without smoothing or hinting so it stays crisp, and a character the typeface lacks falls back to the platform fonts one character at a time instead of showing a box (REQ-VI-UI-013, REQ-VI-UI-014, REQ-VI-UI-015, REQ-VI-BUILD-002, REQ-VI-BUILD-003, REQ-VI-BUILD-004, REQ-VI-BUILD-005, REQ-VI-BUILD-006, REQ-VI-BUILD-010, REQ-VI-BUILD-011).
- A **Use system font** switch in the Theme menu returns all interface text to the platform font, and the User Guide shows the logo that matches the active style and font (REQ-VI-UI-016, REQ-VI-UI-017).
- A **Pixel-perfect interface** switch in the Theme menu, on by default. While it is on, the interface scale is rounded to a whole number (125 % shows as 100 %, 150 % as 200 %), so frames, ornaments and patterns have no blurred pixels. The setting applies the next time the app starts, and the app says so when you change it; if your environment sets a scale-rounding policy of its own, that policy is kept. Turn the switch off to follow the operating system's scale exactly, with softer frames (REQ-VI-UI-012).
- The **Kikko Badge**, a new hand-drawn logo, drawn separately at 16, 24, 32, 48 and 64 px and scaled only by whole numbers for every other size. It is the application icon (window, Windows `.ico`, macOS `.icns`, Linux PNG), the User Guide logo and the README logo, and the web viewer now declares it as its favicon (REQ-VI-BUILD-007, REQ-VI-BUILD-008, REQ-VI-BUILD-009, REQ-VI-UI-018).
- Spanish translations for the new interface strings (REQ-VI-BUILD-012).
- A contributor [style guide](docs/style-guide.md) for the visual identity: the styles, colour roles, frame and pattern templates, the scale rule, palettes and the provenance of the art (REQ-VI-BUILD-011, REQ-VI-UI-003).

### Changed

- The application stylesheet is rebuilt around one art scale, and the Theme menu's Light and Dark choice is now remembered together with the style (REQ-VI-UI-002, REQ-VI-UI-003).
- The About dialog's link colour follows the active style and updates while the dialog is open (REQ-VI-UI-004).
- The User Guide's Theme pages, in English and Spanish, describe the Style menu and the two new switches (REQ-VI-UI-001, REQ-VI-UI-012, REQ-VI-UI-016).
- The Windows app no longer opens a console window when you double-click it. It still writes its output to the terminal when you start it from one, including when that output is redirected (REQ-VI-BUILD-006).
- The README screenshots and the repository's social preview image are regenerated with the new look and logo (REQ-VI-BUILD-009).

### Fixed

- On Windows 11, drop-down lists (combo boxes) no longer print a "point size" warning to the console: their interface font is now point-sized on the Windows 11 style (REQ-VI-UI-013, REQ-VI-UI-014).
- The installer builds could crash at start-up when the build tool resolved to a newer version than the one the app was tested with. The packaging toolchain is now pinned to exact versions and is checked before and after each build, so a drift fails the build instead of shipping a broken installer (REQ-VI-BUILD-006).

- The keyboard-focus ring in Dark mode was too faint against the window and the panels (its contrast was below the 3:1 a focus indicator needs). Every style now draws a focus ring that meets 3:1 against everything it touches, in Light and in Dark, and it stays visible in every control state (REQ-VI-UI-004, REQ-VI-UI-005).
- Painting cost of the framed interface: the canvas now tells Qt that it paints every pixel it is given, so redrawing the canvas no longer repaints the large frames beneath it, and frame art is drawn as a stretched border image wherever its template is uniform, instead of a repeated one. The 16 ms frame budget is unchanged (REQ-VI-UI-005, REQ-VI-UI-010, REQ-VI-UI-011).

### Known issues

- Repainting the whole window at once is slower than one 16 ms frame at the default scale. This happens when you resize the window, switch the style or mode, and the first time the window is shown, so the window may redraw in a visible step for a moment. Drawing and editing on the canvas stay within the frame budget and are not affected.
- At large display scales the main window's minimum height is taller than a small screen. On a screen that is only about 720 logical pixels high (for example a 4K TV at 300% or a 1440p monitor at 150%) the window does not fit and its bottom can be cut off. Lowering the display scale avoids it.
- Some labels are cut short at 150% and 300% display scale. Lowering the display scale shows them in full.
- When you move the window to a screen with a different display scale, the interface freezes for about a second and a half while its frame art and styles are rebuilt. It recovers by itself.
- Convert to Indexed turns a blank (transparent) document opaque black; Undo recovers it (#76).

## [0.3.2] - 2026-09-25

### Added

- The main window's title now shows the running app version, and a new **Help ▸ About PixelArt Creator** entry (on macOS: the application menu) opens a dialog with the app's name, version (selectable), licence, links to the source repository, the documentation site and the releases page, and a Copy button that places the version together with the operating system, Python and Qt/PySide6 versions on the clipboard as one line, ready for a bug report (#72).

### Changed

- The **Aids** menu is renamed **Visual Aids** (**Ayudas visuales** in Spanish), and **F1** now opens the User Guide from any application window, not only the main window.

### Fixed

- The main window could render blank on some Windows GPU/driver setups: a GL-composited top-level window failed to present even though every widget underneath still painted, and the failure cannot be detected in code (context creation and `makeCurrent` both succeed). The canvas now uses a raster viewport by default; GPU (`QOpenGLWidget`) rendering remains available as an opt-in, via the `PIXELART_OPENGL_VIEWPORT=1` environment variable.
- The **Help** menu was unreachable from the keyboard in Spanish: its access key (`Alt+A`) collided with **Archivo** and **Automatización**, both also `Alt+A`. Every menu and action's keyboard access key is now the same letter in every installed language — derived from the English source string rather than chosen per translation — so no two access keys within the same menu can collide again.

## [0.3.1] - 2026-09-24

### Added

- Six structured GitHub Issue Forms (bug report, feature request, performance, translation, documentation, maintenance task) plus a matching `config.yml`, replacing the two starter issue templates, so every report captures the job-specification intake fields without a round of follow-up questions.
- The full label set the issue forms and their lifecycle reference: type labels (performance, translation, chore), status labels (triage, needs info, ready, regression), priority labels, and 19 area labels aligned to the codebase.

### Changed

- CONTRIBUTING.md, SUPPORT.md and CODE_OF_CONDUCT.md now reflect collaborator-first issue creation, matching the repository's collaborators-only pull-request and issue-creation policy.

### Fixed

- The Windows, macOS and Linux installers now build and launch. macOS: the pysidedeploy specs now bundle `pixelart_creator/icons` (tool glyph SVGs + app-icon PNGs) and `pixelart_creator/userguide_content`, which the frozen app needs at runtime and was previously missing, raising a tool-glyph error at launch. Windows: the onefile build now creates its `dist/` output directory before `pyside6-deploy` runs, instead of failing after a successful compile because the destination did not exist. Linux: the AppImage build and the workflow's smoke-launch step now discover the standalone binary inside the deploy output folder by its executable-file identity, instead of guessing a hardcoded name that pyside6-deploy's own finalize step does not actually produce.

## [0.3.0] - 2026-09-24

### Added

- Community health files: CODE_OF_CONDUCT.md, CONTRIBUTING.md, SECURITY.md and SUPPORT.md, so the repository surfaces GitHub's standard community health signals.
- Structured bug-report and feature-request issue forms, and a pull request template, so new issues and pull requests start from a consistent checklist.
- A showcase-media generator script and the example art, screenshots and social-preview image it produced, now tracked under docs/images/.
- Status badges (CI, docs, installers, license, release, downloads, last commit), a hero screenshot and a Gallery section on the README, in English and Spanish, linking to the published User Guide and to the community health files.
- The in-app User Guide is now published to GitHub Pages on every documentation change, built by the same strict build the test suite already gates on.
- Tagged releases now publish a GitHub Release automatically, with the three platform installers attached and its notes drawn straight from this file's own version section.
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

