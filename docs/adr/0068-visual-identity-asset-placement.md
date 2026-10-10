# ADR-0068 — Visual-identity assets: where font sources, built fonts, theme data, logo masters and their tests live

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-10-10 |
| Author | Architecture |
| Feature | Pixel-art visual identity (`REQ-VI-UI-*`, `REQ-VI-BUILD-*`) |
| Grounded by | `scripts/check_layering.py` and `scripts/check_cycles.py` run over a scratch copy of the package carrying the planned layout (output quoted below); `pixelart_creator/ui/tool_icons.py` docstring (the `icons/` no-`__init__.py` precedent); `pyproject.toml` package-data block; the three `packaging/pysidedeploy-*.spec` include lines; ADR-0047 (scope of `testing/suites/scripts/`) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0047, ADR-0069, ADR-0070, ADR-0071 |

## Context

The visual-identity work adds five kinds of file the repository has never held: the text-grid
sources of an original pixel typeface (Nifen Art) and the scripts that build it; the two built
font files with their licence; per-style colour-role maps and role-indexed frame templates that
the application reads at run time; five hand-drawn logo masters that replace the single 64 px
master; and a favicon for the web viewer. Each needs exactly one location, a statement of whether
it ships, and a test home. Three constraints decide most of it:

1. `check_layering.py` is fail-closed: a directory under `pixelart_creator/` that carries an
   `__init__.py` and is not registered is a failure. The existing `icons/` directory ships data
   without being a package for exactly this reason.
2. Sources must not ship. The Nuitka include lines take whole directories
   (`--include-data-dir=pixelart_creator/icons=pixelart_creator/icons`), so anything placed inside
   an included directory ships in every installer.
3. Whatever the application reads at run time must be package data in the wheel **and** included
   in all three installer specs; the v0.3.0 installers failed precisely because a runtime asset
   directory was missing from them.

## Decision

| Artifact | Location | Ships |
| --- | --- | --- |
| Nifen Art glyph sources, recipes, aliases, metrics, Bold overlays, and the declared character set with its count | `fonts-src/nifen-art/` at the repository top level | No |
| Font build, lint, coverage and specimen scripts | `scripts/font/` | No |
| Built fonts, licence and font log: `NifenArt-Regular.ttf`, `NifenArt-Bold.ttf`, `OFL.txt`, `FONTLOG.txt` | `pixelart_creator/fonts/` — no `__init__.py` | Yes |
| Theme data: `index.json` (style ids, menu order, defaults), `contrast-pairs.json`, and per style `<style-id>/roles.json`, `templates.json`, `templates/*.grid.txt`, `pattern.grid.txt` | `pixelart_creator/themes/` — no `__init__.py` | Yes |
| Style ids (directory names and stored values) | `washi-kintsugi`, `edo-night`, `arcade-kikko` | — |
| Logo masters | `pixelart_creator/icons/app/logo-master-{16,24,32,48,64}.png` | Not package data (read by the deriver, never loaded at run time) |
| The previous master `logo-source-64.png` | removed in the same change that switches the deriver to the five masters | — |
| Web-viewer favicon | `web_viewer/static/favicon.png`, written only by `scripts/derive_app_icons.py` and verified by its `--check` | Served by the viewer |
| Contributor style guide (role keys, pair manifest, template grammar, scale rule, palettes, provenance of the theme art and the logo) | `docs/style-guide.md` | Docs only |
| Theme contrast check | `scripts/check_theme_contrast.py` | No |
| Tests of the asset-pipeline scripts (icon deriver, font build/lint/coverage, theme contrast) | new peer test root `testing/suites/asset_pipeline/`; `testing/suites/scripts/test_derive_app_icons.py` moves there | No |

Rules that follow from the table:

- **No text-grid twin of the logo masters is committed.** The PNG master is the source of truth:
  retouching happens on the PNG and each master's sha256 is pinned on the PNG. A committed text
  twin would be a second representation that no requirement asks for.
- **The pixel-art font crispness probe is a test module**, not a script: it lives in the UI suite
  and runs on native platforms.
- `fonts-src/` is the root for every future non-shipped font source, so a later merge of
  ideographs from an OFL-licensed pixel font arrives beside the drawn sources with its own notices.
- `testing/suites/scripts/` keeps the scope ADR-0047 gave it — the repository's own CI-gate
  scripts. Build tools for shipped assets are a different kind of script and get their own root.
- New modules import siblings in the fully qualified form
  `from pixelart_creator.<layer>.<module> import <name>` (see "What has no detector").

**Proof (scripts, not reading).** Baseline on the branch: `check_layering --root pixelart_creator`
exit 0, 232 modules, 0 violations, 0 unregistered; `--root .` exit 0; `check_cycles` exit 0,
234 modules, 867 edges, 0 cycles. On a scratch copy of the package with `fonts/` and `themes/`
(no `__init__.py`) plus stubs carrying the planned imports (`logic/contrast.py`,
`logic/theme_art.py` → numpy and `logic.contrast`; `data/style_catalog.py` → json and
`importlib.resources`; four `ui/` modules → PySide6, `data`, `logic`): `check_layering` exit 0,
239 modules (232 + 7), 0 violations, 0 unregistered; `check_cycles` exit 0, 0 cycles. Controls on
the same copy: a PySide6 import in `logic/theme_art.py` → exit 1 naming the file; an
`__init__.py` in `fonts/` → exit 1, `UNREGISTERED top-level 'fonts'`; a `data` → `ui` import →
exit 1 naming the file.

## Alternatives Considered

- **Font sources inside the package** (`pixelart_creator/fonts/src/`). Rejected: the installer
  include takes the whole directory, so every installer would ship the sources.
- **Font sources under `scripts/font/src/`.** Rejected: mixes data with the tools that read it and
  leaves no home for a second font family's sources.
- **Theme data as Python dictionaries in `ui/theme.py`** (today's role maps). Rejected in
  ADR-0070: the contrast check and the showcase generator would have to import the Qt UI layer.
- **Asset-pipeline tests named individually inside `testing/suites/scripts/`.** Rejected: the
  repository's file-ownership check resolves claims by directory prefix with no exclusions, so the
  same files would be claimed twice.
- **Keeping `logo-source-64.png` beside the new masters.** Rejected: no runtime surface may show the
  previous mark, and a stale master beside five live ones invites the deriver to read the wrong one.

## Consequences

**Positive.** Every new file has one home and a stated shipping status; the layering gate stays
fail-closed with no registry change; adding a style is a data directory; installers gain two
include lines and nothing else.

**Negative / cost.** One test file moves between roots, which can break silently in four ways a
collection count does not show (package marker chain, the old root's `conftest.py` fixtures, CI
suite selection, coverage configuration); the move is verified by a named-test presence check
as well as a count. `pyproject.toml` gains explicit package-data globs for `fonts/` and `themes/`,
and each installer spec gains two `--include-data-dir` lines.

## What has no detector, stated rather than implied

`check_cycles.py` does not see a cycle whose back-edge is written `from pixelart_creator.logic
import theme_art` or `from . import theme_art`: a planted cycle in that form returned exit 0 with
0 cycles, while the same cycle written `from pixelart_creator.logic.theme_art import compose` or
`import pixelart_creator.logic.theme_art` returned exit 1. Until the script resolves that form,
the import convention above is a review rule, not a gate.
