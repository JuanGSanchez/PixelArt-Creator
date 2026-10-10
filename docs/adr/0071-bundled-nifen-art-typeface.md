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

## Amendment (2026-10-10) — the Bold dock-title mechanism and the guide faces

*Immutable-append. The Context, Decision, Alternatives and Consequences above are retained
unchanged. Decision 2 left the Bold dock-title mechanism "chosen by measurement"; this amendment
records the measurement and the choice, and answers decision 5's code-face question.*

**Provenance.** A Qt measurement with the built Nifen Art Regular and Bold at 12 px, `NoAntialias`
and `PreferNoHinting` (2026-10-10; PySide6/Qt 6.11.1 on Windows 11, offscreen at scales 1 and 2 and
the native Windows platform at 100 %; an internal measurement record outside this repository).

**Dock titles: `QDockWidget { font-weight: bold; }` in the one application stylesheet.** Measured
by the resolved font (`QFontInfo`) and by the title's ink against the same string painted in
Regular and in Bold (76 and 116 changed pixels for "Layers", so the two references are told apart):

| Mechanism | Title | Dock content |
| --- | --- | --- |
| `QDockWidget::title { font-weight: bold }` | Regular — **does not work** | Regular |
| `QDockWidget { font-weight: bold }` | **Bold** | Regular |
| the same plus an explicit Regular reset on the dock body | Bold | Regular (the reset changes nothing) |
| `setFont(bold)` on the dock and `setFont(regular)` on its body | Bold | Regular |
| `setFont(bold)` on the dock alone | Bold | Bold or Regular **depending on whether it ran before the first application stylesheet** |

With the chosen rule the dock resolves to family `Nifen Art`, style `Bold`, weight 700, pixel size
12, `NoAntialias`, `PreferNoHinting` — the bundled Bold face, not a synthetic emboldening — while
the dock's labels, buttons, fields and lists resolve to Regular 400, in three construction orders
and across a style switch. The rule is a weight only: the stylesheet still carries no
`font-family` and no `font-size`, so the two portability assertions of decision 2 stand unchanged.
It is one rule instead of a call at every dock-creation site, and unlike the dock-only `setFont`
it does not depend on order. Two dependencies are stated rather than implied: the dock content
stays Regular because stylesheet font properties do not propagate to child widgets, so the
application must not enable `Qt.AA_UseStyleSheetPropagationInWidgetStyles`; and the rule is
emitted whether or not "Use system font" is on, because the stylesheet builder does not take the
font preference — a Bold title in the platform family is still the platform font.

**Guide page (decision 5).** On Windows, inline code and code blocks resolve to the system's fixed
face before and after the application font becomes Nifen Art, so no pinning is added. Headings from
Markdown at a 12 px base are 24, 18, 14 and 12 px and are rounded to 24, 24, 12 and 12 while the
switch is on. The forcing font is a **copy of the interface font** with a new pixel size: a font
constructed afresh from the family name loses `NoAntialias` (measured on all three headings).

**New open item: colour fringes in item views on Windows.** With the native Windows 11 style, the
text of list and tree rows in Nifen Art showed coloured (LCD-style) fringe pixels while labels,
line edits, buttons and the guide's text browser were clean; with other native styles the lists
were clean until the stylesheet also removed their border, after which every style showed them.
The cause is not isolated. It is investigated before the font ships, and a native Windows
crispness check covering item views is added; no threshold is lowered to pass it.

**Still without a detector.** The code face and every font result above on macOS and Linux.

## Amendment (2026-10-10) — the hiragana adapted from Ark Pixel Font, the widened kana cell and the Reserved Font Name

*Immutable-append. The Context, Decision, Alternatives, Consequences and the amendment above are
retained unchanged. The Context's opening sentence — "Nifen Art is an original pixel typeface" —
was true when it was written and is no longer true without an exception; this amendment records
the exception, the cell change that came with it, and the answer to the Reserved Font Name
question left open under "What has no detector". Where this amendment and the text above
disagree, this amendment governs.*

**Provenance.** User decision 2026-10-10: the hiragana are taken from an existing pixel font
licensed under the SIL Open Font License instead of the set drawn for this project. User decision
2026-10-10: the full-width kana cell is widened to take them. As built: the sources
`fonts-src/nifen-art/hiragana-ark-pixel.txt` and `bold-overlays-ark-pixel.txt`, the grid contract
in `fonts-src/nifen-art/metrics.txt`, and `pixelart_creator/fonts/OFL.txt`, `FONTLOG.txt` and
`NOTICE`.

**What is original and what is not.** Nifen Art is original to this project **except its 89
hiragana** — U+3041–U+3096 and U+309D–U+309F — which are adapted from Ark Pixel Font, 12 px,
monospaced, Japanese variant, version 2026.09.25, Copyright (c) 2021, TakWolf
(https://takwolf.com), licensed under the SIL Open Font License 1.1 and declaring no Reserved Font
Name. The adaptation, as the source header and `FONTLOG.txt` state it: every letter moves up one
row (the donor's ink sits on rows −2..8, this typeface's kana cell on rows −1..9); the small
letters are centred in the cell; where a Regular stroke would be two pixels wide, one corner pixel
of the 2×2 block is removed; no row or column of any letter is removed. The Bold of the hiragana is
derived by this typeface's own rule and corrected by drawings made for this project. The hiragana
drawn earlier for this project, with their recipes and Bold overlays, are retired. Katakana, the
spacing marks and every other glyph are unchanged.

**Licence (decisions 7 and 8, as now built).** The font as a whole stays under the SIL Open Font
License 1.1, with the Reserved Font Name **"Nifen Art"** declared. The donor's copyright line is
kept as its author wrote it and stands **before** this typeface's own line in three places:

- `fonts/OFL.txt` opens with `Copyright (c) 2021, TakWolf (https://takwolf.com).`, then the
  Nifen Art copyright line, which ends `with Reserved Font Name "Nifen Art".`, then the standard
  notice and the licence text. Decision 8's order ("the copyright line, then … the Reserved Font
  Name line") is therefore two copyright lines with the Reserved Font Name clause on the second.
- name ID 0 of both TTFs carries the same two lines in the same order; decision 7's "copyright …
  naming the copyright holder" now names the donor's holder first.
- `FONTLOG.txt` carries the donor's copyright line and lists exactly which code points are adapted.

`NOTICE` credits Ark Pixel Font as the source of the hiragana. None of this rests on review alone:
the font build's source lint has a provenance rule that fails when a donor source file's header
omits the donor's name, version, licence or copyright line, when `OFL.txt` or `FONTLOG.txt` omits
the donor's copyright line, or when `FONTLOG.txt` does not list exactly the adapted code points; and
the build itself exits non-zero when name ID 0 of either font lacks the donor's line before this
typeface's.

**The widened kana cell.** The full-width advance stays 12 px in both weights and the ink rows stay
−1..9. The ink columns widen:

| | Before | After |
| --- | --- | --- |
| Full-width ink, Regular | columns 1..10 | columns **0..10** |
| Full-width ink, Bold | columns 1..11 | columns **0..11** |
| Small kana, height (all) | at most 8 rows | at most **9** rows |
| Small hiragana (centred), width | at most 8 columns | at most **9** columns |

The small katakana keep their left-hand placement (columns 1..8 in Regular, up to 9 in Bold).
Half-width glyphs are not affected.

**Consequences of the cell change.** Because the advance is unchanged, line widths and every
layout measured on it are unchanged. A full-width glyph now has no left side-bearing: in Regular one
blank column (column 11) still separates two adjacent full-width glyphs, but in Bold the ink of one
may reach column 11 and touch the next glyph's column 0, with no blank column between them. That is
accepted as part of the decision.

**The open item it closes.** "Whether a Reserved Font Name is declared is still to be decided"
(under "What has no detector") is decided: it is declared, as "Nifen Art", in `OFL.txt` and in name
ID 0 of both fonts.

**Not re-established by this amendment.** The rendering measurements quoted in the Context
(0 mismatches over 126 glyphs × 2 weights; 8,756,800 pixels over twenty specimen sheets) were taken
before the hiragana were replaced and the cell widened; this amendment does not repeat them for the
adapted letters. The pixel-for-pixel correspondence with the donor's published bitmaps is recorded
in `FONTLOG.txt`; this record did not re-compare the donor's files.
