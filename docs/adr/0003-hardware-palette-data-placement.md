# ADR-0003 — Hardware-palette reference data lives module-local (and the NES non-canonical decode)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-02 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-3-colour-palette` |
| Supersedes | — |
| Superseded by | — |

## Context

REQ-P3-LOGIC-008 requires fixed reference colour sets for the **NES** and **Game Boy**
hardware palettes, consumed by the palette-constraint feature (REQ-P3-LOGIC-009, S6). The
spec (`specs/phase-3-colour-palette/spec.md` §9, last row) and the traceability matrix (§3)
explicitly **defer to AGT-01** on two coupled questions:

1. **Where does the palette DATA live** — module-local in `logic/hardware_palette.py`, or in
   `logic/constants.py` (which Article II / S12 designates the single home for numeric values)?
2. **What NES RGB values** does "simulate NES" use, given the research finding
   (`docs/research-phase3-colour.md` Topic 4) that the 2C02 PPU emits an **analog NTSC signal
   with no single canonical RGB palette** (≈54 distinct colours across 64 index entries; the
   RGB result depends on the decode parameters)?

Article II (as interpreted by **ADR-0001**) governs numeric **tuning scalars** — single values a
maintainer would deliberately tune — and keeps intrinsic/algorithm/format-fixed values local to
the code that gives them meaning. A hardware palette is neither a tuning scalar nor a value a
maintainer would "tune": it is a **fixed reference data table** (64 or 4 RGBA entries) defined by
the target hardware. This is directly analogous to the Phase-2 `SymmetryAxis` enum-placement call
(plan PL-D3: enums/data live with their module; `constants.py` holds numeric tuning scalars only).

## Decision

1. **Placement — module-local, not `constants.py`, not `data/`.** The NES and Game Boy reference
   colour tables are defined as **module-local immutable tuples** inside
   `pixelart_creator/logic/hardware_palette.py` (`_NES_COLORS`, `_GAME_BOY_COLORS`). They are
   **not** added to `logic/constants.py` (which stays the home of numeric tuning scalars, per
   Article II / ADR-0001) and are **not** shipped as a runtime-loaded asset under `data/`
   (loading a file would add an I/O dependency and stop `hardware_palette.py` being a pure leaf).
   Keeping the data in `logic/` keeps it importable, Qt-free (Article I), and deterministic with
   no runtime file dependency.

2. **Access returns independent copies.** `nes_palette()` and `game_boy_palette()` each build and
   return a **new independent `Palette`** from the module-local tuples; callers can never mutate
   the reference (SC-L008-3). The backing tuples are never exposed mutably.

3. **Game Boy = the community-standard DMG LUT.** Four shades
   `#9BBC0F`, `#8BAC0F`, `#306230`, `#0F380F` (research Topic 4). The hardware defines only 2-bit
   indices + a greenscale LCD tint (Pan Docs); these hex triplets are the widely-cited rendering
   of that tint and are recorded as **consensus**, cited in the module docstring.

4. **NES = a named, referenced 64-entry decode — no invented RGB.** Because the 2C02 has no
   canonical RGB, the module ships **one referenced decode**, the NESdev wiki-canonical
   **`2C02G_wiki.pal`** (64 entries, ≈54 visually-distinct colours), cited in the module docstring
   with its source. The feature treats the palette as 64 selectable indices. We deliberately do
   **not** fabricate RGB values (P1 — grounded, not invented); a different emulator decode is a
   future additive option, not an edit to this table.

## Alternatives Considered

- **Put the tables in `constants.py`.** Rejected: they are reference data, not tuning scalars;
  Article II / ADR-0001 reserve `constants.py` for single numeric values a maintainer tunes.
  Dumping 64×4 channel values there bloats the single-source numerics file and misreads Article II
  (cf. the ADR-0001 intrinsic-vs-tuning boundary).
- **Ship a `.pal` asset under `data/` and load it at runtime.** Rejected for the built-in
  hardware palettes: it adds an I/O + packaging dependency and makes `hardware_palette.py` non-leaf
  for data that never changes. (User-supplied `.pal`/`.gpl` **import** is a different feature —
  REQ-P3-LOGIC-016 `palette_io` — and correctly does parse external text.)
- **Fabricate a "nice" NES RGB table inline.** Rejected: violates P1 (invention); the research
  explicitly warns the NES RGB is non-canonical. A named referenced decode is the honest choice.

## Consequences

- `logic/hardware_palette.py` stays a pure, Qt-free leaf importing only `color`/`palette`; the
  constraint feature (`quantize.constrain_to_palette`) consumes `Palette` copies from it.
- The single-source-numerics rule (Article II) is preserved: `constants.py` gains **no** palette
  data, only the Phase-3 tuning scalars (plan §8).
- The NES palette is traceable to a named source; swapping/adding a decode later is additive
  (a new function/table), not a silent edit — and a materially different policy would be a new ADR.
- AGT-03 implements exactly these tables; AGT-04 asserts the GB 4-shade set, the NES 64-entry
  count, and copy-independence (SC-L008-1..3).

## Grounding

- `specs/phase-3-colour-palette/spec.md` §4.1 REQ-P3-LOGIC-008, §9 (reference-data placement
  deferred to AGT-01), §11 SC-L008-*; `traceability.md` §3.
- `docs/research-phase3-colour.md` Topic 4 (NES 2C02 non-canonical RGB + `2C02G_wiki.pal`; GB DMG
  4-shade LUT) + §Limitations.
- `constitution.md` Article I (layer purity), Article II (S12 single-source numerics), P1
  (grounded not invented); **ADR-0001** (tuning-vs-intrinsic boundary); Phase-2 plan PL-D3
  (`SymmetryAxis` module-local precedent).
