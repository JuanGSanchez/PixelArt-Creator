# ADR-0071 — The bundled Nifen Art typeface: registration, application, fallback, the guide switch and its licence

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-10-10 |
| Author | Architecture |
| Feature | Pixel-art visual identity — the font (`REQ-VI-UI-013` … `-017`, `REQ-VI-BUILD-002` … `-006`) |
| Grounded by | Rendering measurements of the built fonts on Windows 11 with Qt 6.11.1 (2026-10-09/10; an internal measurement record outside this repository), quoted by number below; `pixelart_creator/ui/theme.py` (`apply_font_fallbacks`, no `font-family` in the stylesheet); `testing/suites/ui/test_portability_ui.py:98-116, 136-146`; ADR-0038 (startup wiring lives in `Main_Window.__init__`); the OpenType 1.9.1 `name` and `OS/2` specifications and the SIL OFL FAQ (entries 1.10, 4.2.1, 6.1–6.4) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0068, ADR-0069, ADR-0070, ADR-0029, ADR-0038 |

## Context

Nifen Art is an original pixel typeface drawn on a 12 px em (Regular and Bold), licensed under the
SIL Open Font License 1.1 inside this Apache-2.0 product. By the maintainer's decision it is the
default for all interface text — menus, titles, tabs, buttons and the content of docks, panels and
dialogs — except the user guide's page text, which stays in the platform font unless a hidden
switch at the guide's logo turns it on. A "Use system font" preference returns all of it to the
platform font. Measured on Windows with the built fonts:

- With `QFont.NoAntialias`: 0 non-binary pixels and 0 mismatches against the source grid at 12,
  24 and 36 px, 126 glyphs × 2 weights; without it, every glyph carries grey pixels.
- With Qt's FreeType engine, default hinting moves one accent pixel in 9 Regular glyphs;
  `PreferNoHinting` removes it (0 mismatches).
- Line metrics: ascent 11, descent 3, height 14 at 12 px, exact multiples at 24 and 36 px.
- Twenty specimen sheets rendered through Qt at 12 and 24 px: 8,756,800 pixels compared with the
  source grid, 0 mismatching.

macOS and Linux have not been measured.

## Decision

1. **Registration.** `QFontDatabase.addApplicationFont` loads both TTFs from the package `fonts/`
   directory at start-up, beside the existing font-fallback wiring in `Main_Window.__init__`. A
   failure is logged and leaves the platform font in place; it is never raised.
2. **Application in code, never through the stylesheet.** The application font is `Nifen Art` at
   a pixel size of 12 logical pixels (`NIFEN_ART_EM_PX`, a property of the font, ADR-0001), with
   `NoAntialias` and `PreferNoHinting`. At a whole-number scale (ADR-0072) every size is a multiple
   of 12 device pixels. The stylesheet carries no `font-family` and no `font-size`, so the two
   portability assertions that say so stand unchanged. Dock titles use the Bold weight by weight
   alone; the exact mechanism is chosen by measurement and accepted only with a resolved-font test.
3. **"Use system font"** restores the platform default font captured once per process before the
   application first changed it. The application names no platform family of its own.
4. **Per-character fallback.** The platform fallback chain already defined in `ui/theme.py` is
   registered as the substitution list for `Nifen Art`, so a character the font lacks (for example
   an ideograph in a layer name) is drawn from a platform font while its neighbours stay in Nifen
   Art, and no missing-glyph box appears.
5. **The guide's page text** uses the platform default font, or Nifen Art while the switch is on;
   while it is on, heading sizes are forced to whole multiples of 12 px, and text marked as code
   keeps the face the viewer gives it.
6. **The hidden switch is a real widget**: a transparent, label-less button laid over the logo
   image in the guide page, keyboard-focusable, with an accessible name, showing the focus ring of
   ADR-0069, and re-positioned on scroll, resize, re-layout and page change. When the logo image
   is unavailable it covers the image's alternative text instead. "Use system font" wins over it.
7. **Build.** The TTFs are built deterministically from the text-grid sources by
   `scripts/font/build_nifen_art.py` with fontTools pinned exactly, as a build-time development
   dependency only; `--check` rebuilds and compares bytes; units per em 1536 (128 per pixel); fixed
   `head` timestamps; outline-only, no hinting program. Name records: family `Nifen Art`, subfamily
   `Regular`/`Bold`, PostScript `NifenArt-Regular`/`NifenArt-Bold`, weight class 400/700 with the
   matching style bits, copyright and designer naming the copyright holder, licence description and
   licence URL naming OFL-1.1.
8. **Licence file.** `fonts/OFL.txt` carries the copyright line, then (only if the maintainer
   declares one) the Reserved Font Name line, then the standard three-line notice, then the OFL 1.1
   text. The text is copied from a locally installed copy, never typed: the three copies found in
   the build toolchain are not byte-identical (one differs in line wrapping, one in its title layout
   and dash characters), so the copy whose words match one and whose wrapping matches the other is
   used, with the comparison recorded in `FONTLOG.txt`. Every distribution — the wheel and the
   three installers — contains both TTFs, `OFL.txt` and `FONTLOG.txt`. `NOTICE` names the bundled
   typeface and its licence file in words that avoid "icon", "glyph" and "svg", which an existing
   test reserves for the tool icons.

## Alternatives Considered

- **Font family through the stylesheet.** Rejected: it would require replacing two portability
  assertions, and the class-level stylesheet font cannot express the pixel-size and rendering
  flags the measurements require.
- **Per-class application fonts (`QApplication.setFont(font, "QMenu")`).** Rejected: once all
  interface text is in Nifen Art, one application font is the simpler correct form.
- **Making the guide logo a link inside the page.** Rejected: a link inside a text browser gets no
  accessible name of its own and the browser's own highlight instead of the focus ring.
- **Embedded bitmap strikes in the TTF.** Not adopted: outline-only already renders exact where
  measured, and whether Qt reads strikes per platform is unverified.

## Consequences

**Positive.** The installed application uses its own font on every platform without installing
anything system-wide; text is pixel-exact at whole-number scales; the fallback keeps user text
legible in any script.

**Negative / cost.** Wider letters can truncate labels; a truncation check now covers every dock,
panel and dialog in English and Spanish at both scales. Native file dialogs keep the operating
system's font. Fractional scales (preference off) render softer text, which is accepted.

## What has no detector, stated rather than implied

Exactness on macOS and Linux is unmeasured until the native-platform crispness probe runs there;
a failure is a decision for the maintainer, not a threshold to lower. Equality of the shipped
licence text with the publisher's own file was not established byte for byte. Whether a Reserved
Font Name is declared is still to be decided, before the fonts are committed for release.
