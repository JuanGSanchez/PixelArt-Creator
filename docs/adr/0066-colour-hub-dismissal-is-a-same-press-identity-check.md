# ADR-0066 — Colour-hub dismissal is a same-press identity check, not a hide-event timing guard

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided 2026-09-06; recorded 2026-09-06 |
| Author | UI |
| Feature | Right-click dismissal of the colour hub (`A11Y-COLHUB-1` keyboard parity) |
| Grounded by | `pixelart_creator/ui/colour_hub_menu.py` (`_maybe_dismiss`, `consume_dismiss_timestamp`); `pixelart_creator/ui/canvas_view.py` (`_dispatch_menu`, `pop_pending_right_press_timestamp`, `contextMenuEvent`); `pixelart_creator/ui/main_window.py` (`_open_colour_hub`); `testing/suites/ui/test_colour_hub_dismiss.py`, `test_right_click_dismiss_audit.py` |
| Supersedes | The hide-event-plus-zero-timer "just closed" guard shipped for the colour hub in August 2026. That guard was never itself recorded in an ADR; its premise lived only in code comments, which this record corrects. |
| Superseded by | — |
| Relates to | — |

## Context

The colour hub is a hand-rolled `Qt.WindowType.Popup` dialog anchored at the cursor. Its previous
dismissal guard assumed a specific event sequence: the popup's own outside-click handling would
fire a hide event, a flag would be set, a zero-length timer would clear that flag on the very next
turn of the event loop, and a right-click that reopened the hub while the flag was still set would
be treated as the same physical click bouncing back, and ignored.

Measurement against the real desktop platform the product ships on found that this hide event
never fires on the reproduction path exercised: the flag is never set, the guard never engages, and
a second right-click while the hub was already open walked straight through the seam that opens the
hub and simply re-anchored the still-visible dialog at the new cursor position. From the user's
side this looked exactly like the right-click being ignored. The guard had shipped with no
automated test asserting the gesture it was meant to protect, so nothing had caught the mismatch
between what the code assumed and what the platform actually does.

The same investigation also found that a right-click landing on the hub's own contents (the colour
wheel, a harmony swatch, the Favourites list) did nothing, and that the Menu key and Shift+F10 —
this product's keyboard equivalents for a context click, and the mechanism `A11Y-COLHUB-1` names as
the keyboard-parity requirement for this control — had no dismissal behaviour at all: the code path
they use calls straight through to the open action with no visibility check of any kind.

## Decision

**Dismissal is decided by two checks that are true regardless of the order or timing of the
underlying platform events, never by an assumption about which event fires when.**

1. **An application-wide filter, installed once from the hub's own constructor**, watches every
   right-click press and every Menu-key / Shift+F10 press application-wide. While the hub is
   visible, the filter hides it and consumes the event before it reaches anything else — including
   the hub's own child widgets. This is what makes the rule uniform: a right-click outside the hub,
   a right-click on the hub itself, and the keyboard trigger are all the same one check
   (`self.isVisible()` at the instant of the press), so there is no separate "dead zone" for a click
   that lands on the hub's own controls to fall into. None of the hub's own pick controls — the
   wheel, the swatches, the Favourites list — use the right mouse button or either dismissal key, so
   this filter cannot collide with how a colour is actually picked.
2. **A same-press identity check** closes the remaining gap: if the platform's own popup handling
   independently closes the hub and replays the same physical press to whatever is underneath, that
   replayed press is recognised by carrying the identical, opaque timestamp of the press the filter
   already used to close the hub — and is then ignored rather than treated as a fresh click that
   should reopen the hub. Recognising a press by its own identity, rather than by how much time has
   passed or which turn of the event loop it arrives on, is what keeps this check accurate however
   the underlying platform event sequence actually plays out — including in the case this project's
   own instruments could not directly observe on the real desktop platform (see "What this ADR does
   NOT claim" below).

The previous hide-event-and-timer guard is removed outright, not repaired alongside the new check:
the flag it set, the timer that cleared it, and the early return that consulted it are all gone, and
every docstring that described the old assumption is corrected in the same change.

## What this ADR does NOT claim

**No claim is made that every one of this fix's protections has been exercised by a genuine,
interactive right-click on real desktop hardware.** The filter's own behaviour — hiding a visible
hub on the very press that lands on it — is proven by the same investigation that found the old
guard's assumption false, and is pinned by the product's automated UI suite. The identity check's
behaviour under a same-turn platform replay is reasoned from documented platform behaviour rather
than directly observed: this project's own test-injection tooling cannot make the platform replay a
press the way a live user's input does, on any platform, so it cannot exercise that one path either
way. This is disclosed here rather than left to be assumed, and it is the same category of gap this
project has recorded before for a different rendering path — a claim a headless run cannot make is
not made merely because the surrounding fix is otherwise well evidenced.

## Alternatives Considered

| Alternative | Why it was not chosen |
| --- | --- |
| Repair the existing hide-event-and-timer guard (adjust the timer, reorder the check) | Rejected — the guard's entire premise, that a hide event fires and a flag survives to the next check, was measured false on the platform in use; adjusting its timing repeats the same category of unproven assumption that produced the defect. |
| A visibility check alone, with no press-identity component | Considered, and is in fact most of what makes the fix work — but on its own it is not proven safe against every platform event sequence this project could reason about: a sequence in which the platform's own handling closes the hub before the filter's own check sees the press would leave the filter believing the hub is already closed and declining to act, so the identical defect could still occur, once, under that one sequence. The identity check removes that gap without adding any timing assumption. |
| Give the hub's own children a dead zone that ignores a right-click landing on them | Rejected — the maintainer ruled for one uniform behaviour, with no exception for a click that lands on the hub itself; a dead zone would also have reintroduced exactly the kind of behavioural special case this fix exists to remove. |

## Consequences

**What this enables.** A right-click dismisses the colour hub from anywhere, including from on top
of it, and the Menu key / Shift+F10 now do the same thing the mouse does — one rule, uniformly
applied, instead of a guard that covered one gesture and silently missed two others. Any future
right-click popup in this product now has a working, tested precedent to follow instead of the
removed guard's unproven one.

**What it constrains.** A future change to the colour hub's dismissal behaviour needs to preserve
both halves of the check — the visibility-gated filter and the press-identity recognition — rather
than reintroducing a bare visibility check alone, which this record has already shown is not
provably sufficient on its own. Nothing about the hub's own colour-picking behaviour — which mouse
button and click count select and apply a colour — is touched by this decision, and any future
control added to the hub's own surface must continue to avoid the right button and the two
dismissal keys if it is not to collide with this filter.

## What has no detector, stated rather than implied

No automated test in this product's suite can drive a genuine, interactive right-click through the
real platform's own popup-closing machinery; every assertion this fix's tests make is against the
seam the product's own code controls, not against the underlying platform's input handling itself.
Confirming the same-press replay path on real, interactive hardware is a manual check, not a gate
that runs.
