# ADR-0019 — Raster encoder options, byte-reproducibility scope (same-environment), and APNG deferral

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-7-export` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 7's defining acceptance is **byte-reproducibility**: PNG / GIF / sprite-sheet / atlas exports
and their JSON metadata are byte-identical for a fixed input **across runs and between the GUI and
CLI paths** (REQ-P7-LOGIC-002/-003/-004/-005, CL-3/CL-14). The spec deferred to AGT-01 (DEP-2/CL-9):
the **specific Pillow encoder options**, the **GIF palette-reduction approach** (reuse
`logic/quantize.py` vs Pillow), whether **APNG** is in scope (CL-8), and the **byte-repro guarantee
scope** (same-environment vs cross-machine — Researcher Open decision 4/5). The Researcher
(`docs/research-phase-7-export-20260704.md`, Topics 1 + 4, flags F-1/F-2) established the
implementation-grade facts (Pillow 12.x confirmed; project pins `Pillow>=10.0`):

- **PNG:** Pillow does **not** auto-write a `tIME`/timestamp chunk (F-1, HIGH confidence — confirm via
  CI byte-diff); `optimize=True` forces `compress_level=9` and its heuristics can vary → pin
  `compress_level` explicitly and pass **no** `pnginfo`/`exif`/`icc_profile`/`dpi`.
- **GIF:** `save_all` + per-frame `duration`/`loop`/`disposal`; ≤256 colours per frame; per-frame
  `ADAPTIVE` re-quantization + `optimize` reorder palettes run-to-run → supply a **fixed shared
  palette** + `dither=NONE` + `optimize=False` for determinism.
- **zlib:** deterministic for a fixed level + fixed zlib build; a different zlib/Pillow version can
  change bytes → a cross-machine guarantee needs pinned runtime/zlib in CI.
- **APNG:** cheap via the same PNG `save_all` path, lossless RGBA — but **not named in the ROADMAP
  Phase-7 scope**.

## Decision

**Guarantee same-environment byte-identity (pinned toolchain in CI); fix the exact deterministic
Pillow option set below; reduce GIF colours through a fixed shared palette built by the shipped
`logic/quantize.py`; and DEFER APNG to a later phase.**

- **Guarantee scope — same-environment.** The promised, test-asserted contract is: *the same
  document + parameters exported twice (and via GUI vs CLI) on the same toolchain yields
  byte-identical files*. This matches the ROADMAP wording (CL-14) and is achievable deterministically.
  Cross-machine identity is **not** promised; it is *supported* by pinning `Pillow`/zlib in CI so the
  CI byte-diff is stable, but not overclaimed as a user guarantee.
- **PNG option set (byte-reproducible).** `Image.save(fp, format="PNG", optimize=False,
  compress_level=PNG_EXPORT_COMPRESS_LEVEL)` — **no** `pnginfo`, **no** `exif`, **no** `icc_profile`,
  **no** `dpi`, **no** `transparency` kwarg (RGBA alpha carries transparency). No `tIME` (F-1,
  verified by the CI byte-diff test, not assumed). Encoding targets an in-memory `BytesIO`; the exact
  bytes are handed to `data/` unchanged (REQ-P7-DATA-001).
- **GIF option set (byte-reproducible).** Build **one fixed shared palette** for the whole animation
  deterministically via `logic/quantize.median_cut` (shipped, deterministic — reuses Phase-3 CP),
  convert every frame with `Image.convert("P", palette=<fixed>, dither=Image.Dither.NONE)`, then
  `base.save(fp, format="GIF", save_all=True, append_images=[...], duration=<per-frame
  duration_ms list>, loop=GIF_DEFAULT_LOOP_COUNT, disposal=GIF_FRAME_DISPOSAL, optimize=False,
  palette=<fixed bytes>)`. Fixed palette + `dither=NONE` + `optimize=False` + explicit per-frame
  `duration` from `Frame.duration_ms` (FR-1) → deterministic and duration-faithful.
- **New constants (Article II, `logic/constants.py`).** `PNG_EXPORT_COMPRESS_LEVEL = 6` (Pillow's
  documented default, pinned explicitly — **distinct** from the shipped `PROJECT_ZLIB_LEVEL = 9`
  which is `.pixproj` pixel-data compression, a different concern), `GIF_DEFAULT_LOOP_COUNT = 0`
  (loop forever), `GIF_FRAME_DISPOSAL = 2` (restore-to-background — the safe default for per-frame
  pixel art). Pillow enum values (`Dither.NONE`) and format strings stay intrinsic-local to the
  encoder module (ADR-0001).
- **APNG deferred (CL-8).** Phase-7 animated-export acceptance is fixed on **GIF**. The encoder seam
  (`ExportFormat` enum + a per-format encode function) is left extensible so APNG (same PNG
  `save_all` path, `duration`/`disposal`/`blend`) is a pure Article XI addition later — adding it
  changes no existing criterion.
- **Determinism discipline (REQ-P7-LOGIC-002).** No wall-clock, no RNG, no locale-dependent
  formatting anywhere in the pipeline; frames iterated in explicit index order; JSON via
  `json.dumps(..., separators=(",", ":"), sort_keys=True)` over integer coordinates; the `meta`
  block's `version` is a fixed injected string, never a build timestamp (ADR-0017).
- **CI byte-diff gate (F-1, hands to AGT-04/AGT-09).** A test exports twice and asserts
  `hashlib`-equal bytes per format; a second test asserts GUI-path == CLI-path bytes; `.github`
  pins the Pillow version so the golden bytes are stable (AGT-09).

## Alternatives Considered

- **Cross-machine byte guarantee.** Rejected as a *promise*: it requires pinning the exact zlib build
  across every user machine (research §1.1/§4.5) — not controllable outside CI. We pin in CI so the
  gate is stable, but scope the user-facing guarantee to same-environment (honest, per CL-14).
- **`optimize=True` PNG.** Rejected: forces `compress_level=9` and its internal heuristics can vary,
  undermining byte control (research §1.1). Explicit pinned `compress_level`, `optimize=False`.
- **Per-frame ADAPTIVE GIF palette (better colour).** Rejected: per-frame adaptive palettes +
  `optimize` reorder colours run-to-run → nondeterministic bytes (research §1.2/§4.4). A fixed shared
  palette + `dither=NONE` trades some colour fidelity for the byte-reproducibility acceptance.
- **Pillow's own quantizer instead of `logic/quantize.py`.** Rejected: `logic/quantize.median_cut`
  is shipped, deterministic, headless-tested, and Qt-free — reusing it (CP with Phase-3) keeps one
  quantiser and one determinism story rather than depending on Pillow's per-call quantiser ordering.
- **APNG in Phase 7.** Rejected: not in the ROADMAP scope (CL-8); adding a second animated format
  now doubles the byte-repro surface for a format with weaker engine support than GIF. Extensibility
  hook preserved.

## Consequences

**Positive.** A precise, pinned option set makes every raster export deterministic and
byte-reproducible under the CI toolchain; the CI byte-diff + GUI==CLI tests are straightforward; GIF
reuses the shipped deterministic quantiser; APNG remains a clean future addition.

**Negative / risk.** The "no auto-`tIME`" claim (F-1) is verified-by-test, not assumed — if a future
Pillow emits volatile metadata the byte-diff catches it (that is the point). GIF's fixed shared
palette can clip colour on gradient-heavy frames (acceptable for pixel art; trades fidelity for
determinism). Same-environment scope means a user on a different Pillow/zlib may see different bytes —
documented, not a defect.

## Grounding

- Spec `specs/phase-7-export/spec.md` §4 (REQ-P7-LOGIC-002/-003/-004/-005), §6 (Pillow-options/APNG
  non-goals), §10 CL-3/CL-8/CL-9/CL-14, §11 SC-L003-1/SC-L004-1/SC-L005-1; `traceability.md` DEP-2.
- Research `docs/research-phase-7-export-20260704.md` Topic 1 (§1.1 PNG, §1.2 GIF, §1.3 APNG),
  Topic 4 (nondeterminism sources), Open decisions 4/5/6, flags F-1/F-2.
- Shipped `logic/quantize.py` (`median_cut`, deterministic — Phase-3), `logic/constants.py`
  (`PROJECT_ZLIB_LEVEL=9`, distinct), `logic/document.py` `Frame.duration_ms` (FR-1); pyproject
  `Pillow>=10.0`.
- Constitution Article II (new numerics in `constants.py`, names distinct; Pillow enum/format strings
  intrinsic-local — ADR-0001), IV (byte-diff test per criterion, headless), VI (export is batch IO —
  the 16 ms frame budget does not apply), XI (APNG as a later format); ADR-0017 (deterministic JSON),
  ADR-0020 (encoder placement in `logic/`).
