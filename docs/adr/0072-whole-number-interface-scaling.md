# ADR-0072 — Whole-number interface scaling is a next-launch preference, on by default

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-10-10 |
| Author | Architecture |
| Feature | Pixel-art visual identity — "Pixel-perfect interface" (`REQ-VI-UI-012`, `REQ-VI-UI-014`) |
| Grounded by | The Qt feasibility probe of 2026-10-09 (frame blur by device-pixel ratio; an internal measurement record outside this repository); `pixelart_creator/ui/app.py` (`create_app` constructs `QApplication` with no high-DPI call before it); ADR-0023 (`real_size_scale = screen_dpi / doc_ppi`, Qt applies the device-pixel ratio, the UI never multiplies it); the maintainer's decision of 2026-10-10 ("125 % shows as 100 %, 150 % as 200 %") |
| Supersedes | The phase-13 plan line "rely on Qt6's automatic high-DPI handling" for the case where the preference is on |
| Superseded by | — |
| Relates to | ADR-0069, ADR-0071, ADR-0023 |

## Context

Pixel frames and pixel text are exact only when one art pixel maps to a whole number of device
pixels. The probe measured frame images smooth-scaled at every device-pixel ratio other than 1.0;
images generated at device scale are crisp at 2.0, partly at 1.5, and never at 1.25 or 1.75,
because at those ratios the art pixel itself is not a whole number of device pixels. Qt 6's
default rounding policy passes the operating system's factor through unchanged. The rounding
policy can only be set before the application object exists.

## Decision

1. A checkable **"Pixel-perfect interface"** item in the Theme menu, **on** by default, stored as
   `appearance/pixel_perfect` (ADR-0070).
2. `create_app` reads the stored value through `ui/appearance_settings.py` **before** constructing
   `QApplication`, and calls `QGuiApplication.setHighDpiScaleFactorRoundingPolicy` with `Round`
   when it is on and `PassThrough` (Qt 6's default, today's behaviour) when it is off. The call is
   made only when no Qt application instance exists yet.
3. A change takes effect **at the next launch**; when the user changes it, the interface says so
   in a translated message. The running scale does not change.
4. The application still never multiplies the device-pixel ratio itself: rounding is a setting of
   Qt's own scaling. The Real-Size Preview keeps a document at its physical size under both
   settings; that is tested, because the preview's DPI input under `Round` has not been measured.
5. The integer device-pixel ratio is the art scale S of ADR-0069 and the font scale of ADR-0071:
   one art pixel and one font pixel are always the same size.

## Alternatives Considered

- **`Floor`.** Rejected: 150 % would show as 100 %, the opposite of the maintainer's decision.
- **Always rounding, no preference.** Rejected: some users prefer their operating system's size
  and accept soft frames.
- **Applying the change immediately by restarting the application.** Rejected: an unrequested
  restart can lose unsaved work; the next-launch rule is stated at the moment of change instead.

## Consequences

**Positive.** Frames and text are exact at 100 % and 200 %, and at 125 %/150 %/175 % the interface
is drawn at 100 % or 200 % instead of blurred.

**Negative / cost.** At 125 % the interface is smaller and at 150 % larger than the operating
system asks for while the preference is on. The offscreen test platform cannot report an
operating-system scale, so the effective ratio at 150 % is verified on a real 150 % display; the
headless tests prove only that the policy is set, before the application object, from the stored
value.

## What has no detector, stated rather than implied

Whether the `QT_SCALE_FACTOR_ROUNDING_POLICY` environment variable overrides the call is not
verified; if it does, a user who sets it gets what the variable asks for.

## Amendment (2026-10-10) — the environment variable wins, the policy is read back, the preview is unchanged, and the art scale is the highest whole-number ratio

*Immutable-append. The Context, Decision, Alternatives and Consequences above are retained
unchanged as the record of the first reasoning. This amendment answers the "What has no detector"
paragraph, supersedes one sentence of the Consequences, answers decision 4's "has not been
measured" clause, extends decision 2, and reads decision 5 together with the ADR-0069 amendment.
Everything else above stands. It serves `REQ-VI-UI-012`.*

**Provenance.** A Qt measurement (2026-10-10; PySide6/Qt 6.11.1 on Windows 11; offscreen, and the
native Windows platform at 100 % on one screen; 52 policy × scale cases, one process each; an
internal measurement record outside this repository). Fractional scales were reproduced offscreen
through the platform's per-screen logical-DPI configuration and, offscreen and native, through
`QT_SCREEN_SCALE_FACTORS`. Every result below had a control. macOS, Linux, a real fractional
display, a real multi-monitor desk, a screen plugged in at run time and the CI platform pin were
not part of it.

### a. `QT_SCALE_FACTOR_ROUNDING_POLICY` overrides the setter

Measured at 150 % (effective device-pixel ratio after the application object exists):

| Environment variable | Setter called with | Effective ratio | Which one won |
| --- | --- | --- | --- |
| `PassThrough` | `Round` | 1.5 | the variable |
| `Round` | `PassThrough` | 2.0 | the variable |
| `Floor` | `Round` | 1.0 | the variable |
| an invalid value | `Round` | 2.0 | the setter (the invalid value is ignored) |
| an invalid value | not called | 1.5 | Qt's default |

A lowercase value (`round`) is accepted. The precedence is therefore, highest first:

1. a **valid** `QT_SCALE_FACTOR_ROUNDING_POLICY` in the process environment;
2. the stored "Pixel-perfect interface" preference, applied through the setter (decision 2);
3. Qt's default, `PassThrough`.

**Decision 2, extended.** The application never clears or rewrites the variable. Once
`QApplication` exists, `create_app` reads the **effective** policy back with
`QGuiApplication.highDpiScaleFactorRoundingPolicy()` — measured to report the policy that won, not
the one passed to the setter — and, when it differs from the policy the stored preference asks
for, logs one line naming the environment variable as the reason. The menu item keeps storing the
preference; it applies again at the first launch without the variable. This answers the paragraph
"What has no detector" above: the variable **does** override the call, and a user who sets it gets
what it asks for — now measured, and said in the log rather than left silent.

**Tests clear the variable first.** A test that sets the policy, spies on the setter or asserts an
effective ratio removes `QT_SCALE_FACTOR_ROUNDING_POLICY` from its process environment before the
application object is built; otherwise a developer's or a CI runner's variable decides the result
instead of the code under test.

Related, measured: `QT_SCREEN_SCALE_FACTORS=1.5` is a platform scale and **is** rounded by the policy
(1.5 → 2.0 under `Round`, offscreen and native); `QT_SCALE_FACTOR=1.5` is an application factor and
is **not** rounded (it stays 1.5). Platform scale against the two policies this application sets:

| Platform scale | `PassThrough` (preference off) | `Round` (preference on) |
| --- | --- | --- |
| 1.25 (125 %) | 1.25 | 1.0 |
| 1.5 (150 %) | 1.5 | 2.0 |
| 1.75 (175 %) | 1.75 | 2.0 |
| 2.0 (200 %) | 2.0 | 2.0 |

### b. The preference is readable before the application object exists

`QSettings` given the organisation and application names works with no application object:
measured with `QSettings(org, app)` on the Windows registry, in separate processes — an absent key
returns the default, write and `sync()` succeed (`NoError`, writable), the value reads back before
the application exists, reads the same once it exists, and a **second** process reads it before
its own application. Control: a name-less `QSettings()` before the application gives
`AccessError` and an empty file name, and the value is lost — so the names are always passed, never
taken from the application object.

The same measurement showed `QSettings(org, app)` **stays native format after
`QSettings.setDefaultFormat(IniFormat)`**, so a test suite that redirects the store through the
default format cannot reach it, and a test would write the real registry. The preference store is
therefore constructed **only in the four-argument form**
`QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, org, app)`, never
`QSettings(org, app)`. In the shipped application the default format is native, so the
four-argument form names the same store as the measured two-argument one (Qt's documented
constructor contract, not separately measured); under the test suite's redirect it lands in the
test store. The four-argument form before the application object is exercised by the UI suite in a
fresh subprocess under the redirected (INI) format — one process writes and reads with no
application, a second reads before its own — with the two-argument form as the escape control
(`REQ-VI-UI-002`). The four-argument form under the **native** format before the application
exists, and the macOS and Linux backends, are not measured.

### c. Decision 4: the Real-Size Preview input under rounding, measured

`QScreen.physicalDotsPerInch()` is already independent of the device-pixel ratio: it equals the
device's true DPI divided by the ratio (for a 100 dpi screen, 66.65 at 1.5 and 50.0 at 2.0;
natively 108.89 at 1.0 and 54.44 at 2.0). The preview's scale (`physicalDotsPerInch / document
ppi`, ADR-0023, with no ratio multiply), times the ratio Qt applies, times the document ppi, over
the true device DPI taken from the screen's physical size, was **1.000 in all 52 policy × scale
cases**: a document pixel keeps its physical size whatever the policy. Control: using the device
DPI instead — the manual ratio multiply ADR-0023 forbids — gives a ratio equal to the device-pixel
ratio (1.5, 2.0). The preview is not changed; its own scale stays fractional by design, because it
is a physical size, unrelated to this preference. Decision 4's test stays, as the regression guard;
its "has not been measured" clause is answered.

### d. The Consequences sentence on the offscreen platform is superseded

"The offscreen test platform cannot report an operating-system scale" is **false**. An offscreen
screen configuration (`QT_QPA_PLATFORM=offscreen:configfile=<path>`) with a per-screen logical DPI
and a base DPI of 96 reproduces 125 %, 150 % and 175 %, and the policy rounds it (§a). The effective
ratio at 150 % and a 100 % + 150 % screen pair are therefore tested headless, not only on a real
display. Two measured traps: the configuration's `dpr` key is not a platform scale, and the
configuration path must contain no colon — a Windows drive letter in it aborts the process. A real
150 % display remains the evidence for the native platform.

### e. Decision 5, read with the ADR-0069 amendment

With more than one screen "the integer device-pixel ratio" is not one number. The art scale S of
ADR-0069 is `art_scale()`: the **highest whole-number device-pixel ratio among all screens** (the
ceiling of each screen's ratio; 1 when there is no screen), and the **one** application stylesheet
is built at it (ADR-0069 amendment, b). S is the source resolution of the generated images, not a
window's displayed ratio: every window paints at its own screen's ratio, one art pixel is one
logical pixel on every screen, and text is drawn by Qt at its own screen's ratio, so one font pixel
(ADR-0071) and one art pixel stay the same size — the part of decision 5 that stands. With this
preference on every ratio is whole and the ceiling is the identity: a 100 % + 150 % pair is 1.0 and
2.0, S = 2, and both screens are exact. With it off, S over-samples a fractional ratio (150 % gives
S = 2), the lesser softness ADR-0069 measured, and frames at that ratio stay soft, as ADR-0069
accepts. `art_scale()` reads the real ratios, so the art follows whichever policy actually won
(§a).

### f. What still has no detector

The read-back and its log line are decided here and are built and tested with the start-up
preference; their test (variable cleared, then set to a policy that differs from the preference) is
the detector. Not measured: the four-argument store before the application object under the native
format; any other Qt high-DPI environment variable; real 125 %, 150 % and 175 % displays; a real
multi-monitor desk; a screen plugged in or rescaled while the application runs; and everything on
macOS and Linux.
