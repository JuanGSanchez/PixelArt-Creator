# ADR-0069 — Pixel chrome is generated at run time from role-indexed templates into one app stylesheet

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-10-10 |
| Author | Architecture |
| Feature | Pixel-art visual identity — frames, focus, ornaments, pattern (`REQ-VI-UI-003`, `-005`, `-006`, `-007` … `-011`) |
| Grounded by | A Qt feasibility probe of 2026-10-09 (PySide6 6.11.1, offscreen, 48 direction × mode × scale runs; an internal measurement record outside this repository), quoted by number below; `pixelart_creator/ui/theme.py` (one app stylesheet, `apply_theme` → `app.setStyleSheet(build_qss(name))`); `testing/suites/ui/test_window_wiring.py:94-98` |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0068, ADR-0070, ADR-0072, ADR-0067 |

## Context

The interface gains pixel-art frames on docks, dialogs and the full control set, corner
ornaments, a faint pattern on two empty areas, and a keyboard-focus indicator that must stay
visible in every control state. Colours must stay defined once, by role (Constitution Article
V.3), in three styles and two modes. The probe measured the candidate mechanisms:

- **Focus.** `*:focus { border: 2px solid focus }` on a control framed by `border-image` squeezes
  the frame and draws **0** focus-colour pixels. Per-class `:focus` frame swaps work for idle focus
  but lose the hover or the pressed fill depending on declaration order. A transparent overlay
  child that paints the ring: 952 ring pixels focused, 0 unfocused, geometry unchanged, and the
  ring persists while hovered, pressed and checked, in all 10 scale runs.
- **Docks.** On a docked `QDockWidget` Qt paints only `::title`; a single frame image for the
  whole dock is not drawn. A child `QFrame` carrying its own `border-image` frames the body; a
  plain `QWidget` does not inset its content by the border. Floating docks get native chrome.
- **Corners.** Top-level popups and dialogs have no translucent backing: chamfered or rounded
  corner cells show the widget's own background; `QToolTip` shows an unthemed `#EFEFEF` unless
  given a role background.
- **Scale.** `border-image` is smooth-scaled at every device-pixel ratio other than 1.0, including
  exactly 2.0 (33–42 % of ring pixels off-palette). Generating the image at device scale and
  writing `border-width × DPR == slice pixels` makes it crisp at 2.0 (0.02–0.04 %).
- **Ornaments.** Overlay children positioned by an application event filter: 48 of 48 position
  checks after resize, undock and redock; 0 pixels changed outside the ornament mask at DPR 1.0,
  1.5 and 2.0. Filter cost: +1.5 to +2.3 µs per event delivered, 0.3 % of events handled.
- **Pattern.** A stylesheet background under custom-painted children bleeds under their text
  (233–1,908 pattern pixels inside text boxes); painting the area in `paintEvent` with the
  children's rectangles clipped out: 0 in 48 of 48, with 80,874–482,412 pattern pixels present.

## Decision

1. **Frame art is generated at run time.** Role-indexed templates (`pixelart_creator/themes/`,
   ADR-0068) are composed and coloured from the active role map at an integer art scale S equal
   to the screen's integer device-pixel ratio, encoded to PNG, and written to one per-process
   temporary directory removed at exit. One art pixel is one logical pixel; the image carries S
   device pixels per art pixel; the stylesheet's `border-width` is the slice count and its
   `border-image` slices are slice × S. The composition and colouring are Qt-free
   (`logic/theme_art.py`); only the file writing and the stylesheet live in `ui/`.
2. **One app-wide stylesheet** remains the only stylesheet. It references the generated files by
   quoted, forward-slash `url("…")`. It carries no `:focus` rule, no `font-family`, no
   `font-size`. `build_qss(mode, style, *, scale)` is deterministic within a process, and the
   applied stylesheet is asserted equal to it — exact equality, as today, with the scale passed.
3. **Docks:** `QDockWidget::title` takes the `dock_title` image; each dock's content is wrapped in
   a `QFrame` named `DockBody` taking `dock_body`, installed by one helper at every dock-creation
   site; code reaches the panel through `dock_content(dock)`, never `dock.widget()`. Floating docks
   keep native chrome and get no Qt-drawn title plate.
4. **Dialogs and popups** keep the native title bar, show no empty band, and have square corners;
   `QToolTip` takes a role background; a heading row is drawn only where a dialog already has a
   heading of its own.
5. **Focus** is a `Focus_Ring_Widget` overlay attached on FocusIn and hidden on FocusOut by one
   application event filter (`Pixel_Chrome_Filter`); it paints the style's `focus_ring` (or
   `focus_ring_square`) template in the `focus` role. Hover, pressed and checked fills show
   through; a selected control keeps its inner cue ring inside the focus ring.
6. **Ornaments** are `Ornament_Widget` overlays placed by the same filter: the two bottom corners
   of docked docks, the four corners of dialogs.
7. **Pattern** is painted only by `Pattern_Area_Widget` with its children clipped out
   (clearance `PATTERN_CHILD_CLEARANCE_PX` in `logic/constants.py`), placed at the tail of the tool
   toolbar and right of the timeline transport controls — nowhere else, and never on the canvas
   workspace.
8. No `QGraphicsEffect`, no OpenGL surface and no translucent top-level is introduced into the
   window chrome.

**Evidence of focus visibility changes accordingly.** The presence of the substring `":focus"` in
the application stylesheet is no longer evidence of a visible focus indicator (it is absent by
design, and the probe showed it can be present while the indicator is invisible). The evidence is
a rendered check: focus-role pixels present around the focused control, absent when unfocused,
with the examined-pixel count asserted non-zero. Assertions that panels and dialogs carry no
per-widget stylesheet stand.

**Screens with different scales.** Whether the stylesheet resolves `@2x`/`@3x` image variants per
painting device is not yet measured. If it does, each template is written at every integer scale
and S leaves the stylesheet. If it does not, the art follows the main window's screen and is
re-applied when that screen's ratio changes; a window shown on a second screen of a different
integer ratio would then be soft, and that limit is put to the maintainer rather than shipped
unstated.

## Alternatives Considered

- **Committed PNGs per style, mode and scale with a `--check`.** Rejected: every colour lives
  twice (role map and pixels), the binaries multiply by 3 × 2 × N, and colour-once holds only
  through a check.
- **A `QProxyStyle` painting the frames.** Rejected: its interplay with the stylesheet engine is
  unmeasured, and no requirement needs it.
- **`:focus` frame variants per control.** Rejected: six templates cover six of at least twelve
  state combinations; the measured overlay covers all.
- **Per-class `showEvent` hooks instead of an application filter.** Kept as the fallback if the
  filter's cost ever threatens the 16 ms frame budget (Constitution Article VI); not chosen first
  because it touches every dock and dialog class.

## Consequences

**Positive.** Colour is defined once; a new style is data; frames are pixel-exact at whole-number
scales; focus is visible in every state; the pattern cannot sit under text by construction.

**Negative / cost.** A per-process temporary directory and its clean-up; an application event
filter on every event; `dock.widget()` call sites move to `dock_content()`; eleven test modules
replace a substring assertion by a rendered helper; the stylesheet-equality test passes the scale.
Frames are soft whenever the scale is fractional (the preference of ADR-0072 is off), which is
accepted by the maintainer's decision.

## What has no detector, stated rather than implied

The probe ran offscreen: native window chrome, Windows 11 corner rounding and drop shadows, and
real per-monitor scales were not measured. Chamfered, nicked or rounded corners on **docked**
child frames were not measured either; each style has a square fallback in its template data.

## Amendment (2026-10-10) — one stylesheet cannot carry per-screen image variants; the art is generated at the highest whole-number scale present

*Immutable-append. The Context, Decision, Alternatives and Consequences above are retained
unchanged as the record of the first reasoning. This amendment answers the open "Screens with
different scales" paragraph and decision 1's "the screen's integer device-pixel ratio", and adds
the measured stylesheet rules. Everything else above stands.*

**Provenance.** A second Qt measurement on the committed theme data (2026-10-10; PySide6/Qt 6.11.1
on Windows 11, offscreen and the native Windows platform at 100 %; an internal measurement record
outside this repository). Multi-screen and fractional scales were reproduced offscreen through the
platform's screen configuration (per-screen logical DPI). Every result below had a control. macOS,
Linux, a real multi-monitor desk and a real fractional display were not part of it.

### a. What the measurement showed about `@2x` / `@3x`

Qt **does** choose the `@Nx` file per painting device for a stylesheet `border-image`: with one
application stylesheet, a window on a 1.0 screen painted the 1x file and a window on a 2.0 screen
the 2x file. But the `border-image` **slice numbers are read in pixels of the chosen file**: a
slice of 4 is right for the 1x file and stretches the ring of the 2x file; a slice of 8 is right
for the 2x file and makes the rule invalid on the 1.0 screen (nothing is drawn). `4px` and a
percentage behave like `4`. One stylesheet therefore cannot be right on two screens of different
ratios, and the "write every template at every integer scale and let S leave the stylesheet"
branch of the paragraph above is **withdrawn**.

### b. Decision 1, as amended

The art scale S is **the highest whole-number device-pixel ratio among all screens** (the ceiling
of each screen's ratio, so a fractional ratio over-samples rather than under-samples), and the one
application stylesheet is built at it. S is the source resolution of the generated images, not the
displayed scale: every window still paints at its own screen's ratio, and one art pixel is still
one logical pixel on every screen. When a screen is added or removed or a screen's scale changes,
S is recomputed; only if it changed are the images regenerated and the one stylesheet re-applied.
Overlays (focus ring, ornaments, pattern) are painted, not carried by the stylesheet, and compose
at their own widget's whole-number ratio. Measured on two screens at 1.0 and 2.0 (share of a framed
button's pixels further than 6 levels from the palette):

| Art in the one stylesheet | 1.0 screen | 2.0 screen |
| --- | --- | --- |
| S = 1 | 0.0 % | 13.9 % (soft) |
| S = 2 | 0.0 %, pixel-identical to the S = 1 render | 0.0 % |
| S = 3 | 0.0 % | 0.0 % |

The larger art does **not** blur the 1.0 screen: each art pixel of an S = 2 image is a 2 × 2 block
of one colour at whole-number offsets, so the 2 : 1 reduction has a single colour to sample. The
spin-box, combo-box, check-box, slider and scroll-bar sprites and frames were each pixel-exact with
S = 2 art on a 1.0 screen, in all three styles and both modes. With "Pixel-perfect interface" on
(ADR-0072), a 100 % + 150 % pair is 1.0 and 2.0, so S = 2 and both screens are exact.

**Alternative rejected: a stylesheet per top-level window, re-applied when the window changes
screen.** Also measured exact on both screens, so it buys nothing over the decision, and it would
give every dialog a stylesheet of its own — which the "no per-widget stylesheet on panels and
dialogs" assertions forbid — and the applied application stylesheet would no longer describe what
any window shows. The equality assertion becomes
`app.styleSheet() == build_qss(mode, style, scale=<highest whole-number ratio>)`.

### c. Stylesheet rules the measurement fixed

- **Corners on docked children.** A transparent corner cell shows the widget's **own** background,
  not its parent's. `QDockWidget::title` declares no `background` (the plate colour comes from the
  template), and the framed selectors (`QPushButton`, `QToolButton`, `QToolBar`, `QFrame#DockBody`)
  declare `background: transparent`. With both rules no corner cell was wrong for the 1 px nick,
  the 2 px rounding or the 3 px chamfer, in both modes; Qt rules none of the three out.
- **Sub-controls.** `QSpinBox QLineEdit { background: transparent; border: none }`; spin and combo
  buttons with `subcontrol-origin: border`, a `top right` / `bottom right` position and the
  sub-button frame image; arrows and check-box indicators as `image:` at the template's size in
  logical pixels; slider handle as `image:` with a width, **no height**, and a negative vertical
  margin (a declared height makes Qt scale the image and blur it); scroll bar with the track as
  `border-image` on `::add-page` and `::sub-page`, a transparent borderless bar, the handle's
  `border-image` with a minimum length, and zero-sized `::add-line` / `::sub-line`. The alternative
  scroll-bar arrangement (track on the bar, handle with a negative margin) was exact offscreen and
  **failed on the native platform**; it is not used.
- **Focus on tabs and item views.** A tab bar receives one focus-in per focus gain and none when
  the arrow keys move the current tab, so the ring is re-fitted to the current tab on
  `currentChanged`. Item views carry `outline: 0`, or Qt's own item focus rectangle adds
  off-palette pixels. A text browser needs nothing.
- **Paths.** `url("…")` quoted, with forward slashes, resolved in every directory name tried
  (spaces, a double space, accented and CJK characters, `'`, `&`, `%`, brackets, `;`, `#`), offscreen
  and native. Unquoted paths, backslashes, `file:///` URLs and percent-encoding fail and are not
  used.

### d. What still has no detector

The image regeneration when a screen is plugged in while the application runs; S = 2 art on a
**native** 1.0 screen (measured offscreen only — the maintainer's real 100 % + 150 % pair is that
evidence); S = 3 on a 2.0 screen beyond one button size; the combo-box popup list, tree and table
headers, and the disabled and pressed sub-control states; and everything on macOS and Linux. The
cost of the 2 : 1 reduction per paint on a 1.0 screen is profiled against the 16 ms frame budget.
