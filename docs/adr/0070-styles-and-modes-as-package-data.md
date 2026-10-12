# ADR-0070 — Three styles × two modes as package data, remembered in the settings store

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-10-10 |
| Author | Architecture |
| Feature | Pixel-art visual identity — styles, modes, roles, persistence (`REQ-VI-UI-001` … `-004`, `REQ-VI-BUILD-001`) |
| Grounded by | `pixelart_creator/ui/theme.py` (role maps `_ROLES`, `build_qss`, `apply_theme`; theme not persisted, `main_window.py` default Light); `testing/suites/ui/conftest.py` (autouse theme fixture over two themes); `testing/suites/ui/test_a11y_theme.py:50-66` (the only contrast implementation today, a private test helper); the reviewed role maps of the three styles (24 keys each, identical, 114 gated pairs passing) |
| Supersedes | The phase-1 reading "ship light and dark; default follows OS/light" for the default; the two-map role model |
| Superseded by | — |
| Relates to | ADR-0068, ADR-0069, ADR-0067, ADR-0004 |

## Context

The interface moves from two flat themes to three styles — Washi & Kintsugi (default), Edo Night,
Arcade Kikko — each with a Light mode (gold accents) and a Dark mode (red accents). Every colour
must be defined once by role, with identical role keys in all six combinations, and every gated
pair must meet its WCAG floor in all six, measured by a check that cannot pass on zero pairs. The
choice must survive a restart. Three readers need the role maps: the theme module, the contrast
check, and the showcase generator that renders collateral; only the first one is Qt code.

## Decision

1. **Role maps are JSON package data**, one `roles.json` per style holding both modes
   (ADR-0068 places them). `themes/index.json` lists the style ids in menu order and names the
   defaults (`washi-kintsugi`, `light`). Display names are translated strings in `ui/`, not data.
2. **A Qt-free loader**, `data/style_catalog.py`, reads and validates them: identical role-key sets
   across all six combinations, colour syntax, template legends closed over the role keys, and
   `focus` distinct from `accent`. Invalid shipped data raises a domain error that a test catches.
3. **Colours are `#RRGGBB`, or `#AARRGGBB` with alpha first** (Qt's reading of an 8-digit value)
   where translucency is required. The convention is stated once, in `docs/style-guide.md`.
4. **One contrast implementation**, `logic/contrast.py` (Qt-free), serves the theme, the tests and
   `scripts/check_theme_contrast.py`. Its floors — 4.5 for text, 3.0 for components and focus —
   are fixed by WCAG and live with the formula (ADR-0001: intrinsic, not tuning).
5. **Declared pairs are data** (`themes/contrast-pairs.json`: text, component or information).
   **Focus pairs are derived**, not declared: the focus-ring template is composed over every framed
   control template in every state on each ground, and every role it touches becomes a gated
   focus pair.
6. **`ui/theme.py` keeps its public names.** `THEME_LIGHT` and `THEME_DARK` remain the two mode
   names; style is an added, defaulted argument (`role_map(mode, style)`, `build_qss(mode, style,
   *, scale)`, `apply_theme(app, mode, style)`, `canvas_roles(mode, style)`, …). Existing call
   sites that pass a mode keep working.
7. **Persistence** uses `QSettings` (organisation and application "PixelArt Creator"), group
   `appearance`: `style`, `mode`, `use_system_font`, `pixel_perfect`, `guide_pixel_font`. A stored
   value that names no shipped style or mode counts as absent and yields the default. One module,
   `ui/appearance_settings.py`, is the only reader and writer, and it works before the application
   object exists (ADR-0072 needs that).
8. **Tests never touch the real store**: the UI suite points `QSettings` at a per-session temporary
   location before any appearance code runs, and a guard test fails if the real store is used.
9. **Six-way verification is targeted.** The autouse theme fixture runs every UI test in both modes
   of the default style. The theme-sensitive checks are parametrised over all six combinations: key
   parity, contrast floors, focus visibility, the selected-state cue, control framing, ornaments,
   pattern placement and its distance from text, the flat canvas workspace, the title plate, the
   tooltip background and the tool-icon tint.

## Alternatives Considered

- **Keep the role maps as Python in `ui/theme.py`.** Rejected: the contrast check and the showcase
  generator would import the Qt UI layer to read colours, and a deferred restyle of the web
  viewer could not read them at all.
- **Discover styles from the directory listing.** Rejected: menu order would depend on the file
  system; the index makes it explicit.
- **Run every UI test in all six combinations.** Rejected: it triples the UI suite while adding no
  assertion that depends on the style beyond those listed in decision 9.
- **The favourites JSON store (ADR-0004) for these flags.** Rejected: that store exists for a
  user-managed list; five appearance flags are what `QSettings` is for.

## Consequences

**Positive.** Colours live once, in data any front end can read; the contrast gate and the theme
read the same maps; adding a style is a directory and a test row.

**Negative / cost.** Tests that reached into `theme._ROLES` move to `role_map()`; the tool-icon
tint gains a style argument; ADR-0067's measured link-contrast table describes the previous roles
and becomes historical (its rule — links use the `text` role, underlined — stands in all six).
