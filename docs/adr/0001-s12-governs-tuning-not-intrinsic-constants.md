# ADR-0001 — Constitution Article II (S12) governs tuning parameters, not intrinsic constants

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-02 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-1-core-engine` |
| Supersedes | — |
| Superseded by | — |

## Context

Constitution Article II (realising user requirement **S12**) states: "Every numeric
tuning value is defined once in `pixelart_creator/logic/constants.py` and imported by
name. No magic numbers appear in `ui/`, `logic/`, `data/`, or tests."

During the retroactive Phase-1 core-engine review, the Gleaner distillation
(`docs/gather-agt-02-phase1-core-engine.md`) and AGT-02's spec §9 surfaced numeric
literals living **outside** `constants.py`. They fall into two materially different
kinds:

1. **Tuning / configuration parameters** — product-visible limits or defaults a
   maintainer might legitimately want to change in one place: the palette index-space
   cap (`256`), the default frame duration (`100` ms), the `.pixproj` zlib compression
   level (`9`).
2. **Intrinsic constants** — values fixed by the algorithm or the data format itself,
   whose "change" would not be a tuning decision but a different algorithm or a
   different format: the 8-bit RGBA channel range `0..255`, the RGBA channel count `4`,
   the `#RRGGBB(AA)` hex clamp `255.0`, `FORMAT_VERSION = 1`, and the Bresenham /
   midpoint-ellipse literals (`2`, `0.5`, `0.25`).

A literal reading of "no magic numbers" would sweep both kinds into `constants.py`.
Doing so would relocate `255`, `4`, and Bresenham's `2` — numbers that are not tuning
knobs but definitional parts of "8-bit RGBA" and "integer line rasterisation" — away
from the code that gives them meaning, harming readability without buying any
single-point-of-change benefit (they never change as a tuning decision). Article II's
own wording is the discriminator: it governs every numeric **tuning** value.

## Decision

**Article II (S12) governs tuning/configuration parameters — values a maintainer would
deliberately tune — and NOT intrinsic algorithmic or format-intrinsic constants.** A
numeric literal must be centralised in `logic/constants.py` if and only if it is a
tuning parameter; a value fixed by the algorithm or the file/colour format legitimately
lives next to the code that defines it.

Applying the boundary to Phase-1, the following **tuning** values move into
`constants.py` (implemented by the tasks in `specs/phase-1-core-engine/tasks.md`):

- `MAX_PALETTE_SIZE = 256` (was `logic/palette.py`) — product palette-size cap.
- `DEFAULT_FRAME_DURATION_MS = 100` (was `logic/document.py`) — default animation timing.
- `PROJECT_ZLIB_LEVEL = 9` (was inlined in `data/project_io.py`) — `.pixproj` compression level.

The following are ruled **intrinsic** and remain local (EXEMPT):

- `color.CHANNEL_MIN = 0` / `CHANNEL_MAX = 255` and the `255.0` clamp in
  `blend_over`/`to_hex` — intrinsic to 8-bit RGBA.
- `pixel_buffer` `0..255` index range and RGBA channel count `4` — intrinsic to
  8-bit / RGBA array shape.
- `project_io` channel count `4` and `FORMAT_VERSION = 1` — format-intrinsic.
- `drawing` Bresenham `2` and midpoint-ellipse `0.5` / `0.25` — algorithmic constants.

## Alternatives Considered

- **Literal maximalism — centralise every numeric literal.** Rejected: it would move
  `255`, `4`, and Bresenham's `2` into `constants.py`, divorcing definitional constants
  from their algorithm/format, reducing readability, and providing no tuning benefit
  (these are never tuned). It also over-reads Article II, whose text says "tuning value".
- **Status quo — leave all the flagged literals where they are.** Rejected: the three
  genuine tuning parameters (`256`, `100`, `9`) are exactly the single-point-of-change
  values Article II exists to protect, and `100` was already duplicated between
  `document.py` and an inline in `project_io.py` (a drift risk). Non-compliant.
- **Per-module "constants" blocks instead of the central module.** Rejected: violates
  Article II's "defined once in `logic/constants.py`" single-home rule.

## Consequences

**Positive.** A crisp, testable rule for future phases: tuning value → `constants.py`;
intrinsic value → local. It removes the `100` duplication drift risk, gives the three
tuning parameters one edit point, and keeps definitional constants readable in context.
It gives `sdd-analyze` and reviewers an unambiguous criterion, avoiding future
re-litigation of each literal.

**Negative / risk.** The tuning-vs-intrinsic line requires judgement at the margin
(e.g. a future value that is arguably both). This ADR sets the default: when a value is
fixed by an algorithm or a data-format definition it is intrinsic; when a maintainer
could reasonably choose a different value without changing the algorithm/format, it is
tuning and must be centralised. Borderline calls are recorded as follow-up ADRs, not
resolved by weakening this one.

## Grounding

- User requirement **S12** (Dossier §1) / **Constitution Article II** — the rule being
  interpreted.
- Gleaner distillation `docs/gather-agt-02-phase1-core-engine.md` (Flags §S12) and
  AGT-02 spec `specs/phase-1-core-engine/spec.md` §9 (findings S12-1..8) — the concrete
  literals adjudicated.
- Orchestrator adjudication (2026-07-02): tuning-vs-intrinsic boundary + the move list,
  encoded here and in `specs/phase-1-core-engine/plan.md` §7 and `tasks.md` (T1–T6).
