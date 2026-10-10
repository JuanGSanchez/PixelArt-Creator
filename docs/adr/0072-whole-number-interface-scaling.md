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
