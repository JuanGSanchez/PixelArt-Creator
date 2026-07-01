# Plan — Phase 1: Core Engine (logic/data)

| Field | Value |
| --- | --- |
| Feature | `phase-1-core-engine` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, III, IV, VII, VIII, X) |
| Mode | **RETROACTIVE** — HOW for already-shipped, tested logic/data (code is ground truth), plus the S12 remediation slice this plan authorises |
| Over spec | `specs/phase-1-core-engine/spec.md` (REQ-P1-LOGIC-001..013, REQ-P1-DATA-001) |
| Layer scope | `pixelart_creator/logic/` + `pixelart_creator/data/` (the Phase-1 UI increment is a separate plan — see spec §7 Gaps) |
| Stack source | S8 (fixed) — no new technology introduced |

---

## 1. Purpose (HOW)

This plan documents the technical architecture that realises the approved Phase-1
spec, maps every shipped module to its S11 layer, records the stack decisions (all
pre-grounded by S8 — no new choice is introduced, so no RESEARCH REQUEST is needed),
defines the `.pixproj` data model, and authorises a **single remediation slice** (the
S12 tuning-constant centralisation + two consistency fixes) that brings the shipped
code into strict Article II / consistency compliance without changing any observable
behaviour. The slice is decomposed into ordered work items in `tasks.md`.

No `sdd-analyze` is run by this plan. Analyze is the Article VIII gate and runs only
**after** the remediation tasks are implemented (AGT-03) and re-validated (AGT-04).

## 2. Stack decisions (all grounded by S8 — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language | Python 3.12+ | S8 |
| Pixel storage | NumPy `uint8` arrays (RGBA `(H,W,4)`; INDEXED `(H,W)`) | S8, F7 |
| Project file | `.pixproj` = JSON + zlib + base64 pixel payloads | S7 |
| Determinism | stdlib only in `compactor` (no time/random/network) | P2, F8 |
| Testing | pytest + pytest-cov + Hypothesis (headless) | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for logic/data) | Article III |

No stack/library/API choice in Phase-1 logic/data is ungrounded (Decision PL-D1 →
Branch B for every item). GPU/Qt/render choices belong to the Phase-1 **UI** increment
and to AGT-10; they are out of scope here.

## 3. Architecture — module → layer map (S11)

All eight shipped source modules live in `logic/` or `data/` with **zero Qt imports**
(verified: `check_layering` clean over 11 modules, `check_cycles` no cycles over 12
modules — see §8). Dependency direction is one-way and acyclic.

| Module | Layer | Responsibility | Depends on (intra-logic) |
| --- | --- | --- | --- |
| `logic/constants.py` | logic | Single home for numeric tuning values (Article II) | — (leaf) |
| `logic/color.py` | logic | `RGBA` model, validation, hex (de)serialise, `blend_over`, `distance_sq` | — |
| `logic/palette.py` | logic | Indexed `Palette` CRUD/reorder/nearest (256-cap) | `color` |
| `logic/pixel_buffer.py` | logic | NumPy RGBA/INDEXED buffer; get/set/fill/region/blit/resize | `color`, `constants` |
| `logic/drawing.py` | logic | Pencil/line/rect/ellipse/flood-fill primitives (return changed coords) | `color`, `pixel_buffer` |
| `logic/history.py` | logic | Reversible command pattern + bounded undo/redo + `record_edit` | `pixel_buffer` |
| `logic/document.py` | logic | Document → frames → layers → buffer state tree | `pixel_buffer`, `palette` |
| `logic/compactor.py` | logic | Deterministic MaxRects (BSSF, rotation off) atlas packing | — (stdlib only) |
| `data/project_io.py` | data | `.pixproj` serialise/deserialise + defensive validated load | `color`, `constants`, `document`, `palette`, `pixel_buffer` |

**Layering invariant (Decision PL-D2):** no design in this plan places Qt in `logic/`
or `data/`, and after remediation no tuning numeric lives outside `constants.py`. The
Qt bridges the spec references (`QColor`, `QUndoCommand`) are deferred to `ui/` in the
UI increment (spec §7 GAP-5); `logic/history.py` is deliberately shaped as the
pure-Python core that `ui/commands.py` will wrap (reversible-op boundary, §6).

## 4. Foundational-primitive ratification (spec §8 REV-1..7)

The orchestrator has RATIFIED REV-1..7 as **foundational primitives realised early**;
**no code is removed.** This plan records each as a foundational module and states the
point of ACTUAL consumption that fixes its phase attribution. AGT-02 owns the
traceability matrix; the trace deltas below are **flagged for AGT-02** (see §9).

| REV | Primitive | Consumed by (verified in code) | Phase attribution |
| --- | --- | --- | --- |
| REV-1 | `compactor.compact` / `Packing` / `CompactionError.reason` | No Phase-1 consumer; smoke `-m` only | **Forward → Phase 7** (texture atlas; ROADMAP P7). Foundational, kept. |
| REV-2 | Alpha compositing (`color.blend_over`; `PixelBuffer.blit(blend=True)`) | Alpha-compositing **capability** consumed in Phase-1 by `blit(blend=True)`; `color.blend_over` itself has **no in-code caller** (blit reimplements straight-alpha vectorised in NumPy) | **Phase-1 consumption** for the capability (via `blit`); layer *blend-mode* semantics forward → Phase 4. `blend_over` flagged uncalled (§9). |
| REV-3 | `color.distance_sq` | Consumed in Phase-1 by `palette.nearest_index` (palette.py:109–111) **and** `drawing.flood_fill` tolerance (`_matches`, drawing.py:189) | **Phase-1 consumption** (not forward-only); perceptual CIEDE2000 baseline forward → Phase 3. |
| REV-4 | Indexed `Palette` full surface | INDEXED `PixelBuffer` + `.pixproj` palette need it now | **Phase-1** (partial S7); full reorder/nearest workload forward → Phase 3. |
| REV-5 | `Layer` opacity/visible/locked | Stored in tree; no Phase-1 editing use-site | Tree is S7 (Phase-1); per-layer attrs forward → Phase 4. Kept. |
| REV-6 | `Frame` + `duration_ms` + add/remove frame | Stored in tree; round-tripped by `.pixproj` | Tree is S7 (Phase-1); animation semantics forward → Phase 5. Kept. |
| REV-7 | `FunctionCommand` | No specific Phase-1 call site | S7 command-pattern (generic); accepted as history infra. Kept. |

**Trace consequence:** REV-2 (capability) and REV-3 have genuine Phase-1 consumption
points, so REQ-P1-LOGIC-003 and REQ-P1-LOGIC-004 are **not** forward-only. This differs
from AGT-02's current matrix and is handed back in §9 (AGT-01 flags; AGT-02 owns the
edit). It also bears on the analyze-time Article X "no S-id" finding for -004 (spec
traceability "Notes for sdd-analyze"): -004 traces to its Phase-1 consumers' S-ids
(S1 via drawing, S7 via palette) rather than being untraced.

## 5. Data model — `.pixproj` (REQ-P1-DATA-001, S7, Article VII)

JSON object, defensively validated on load (no `eval`/`exec`; every field
type/bounds-checked; `int` excludes `bool`):

```
{
  "format": "pixproj",            # must == FORMAT_NAME
  "version": 1,                   # must == FORMAT_VERSION (else "unsupported version")
  "canvas": { "width": int, "height": int, "mode": "rgba"|"indexed" },
  "palette": ["#RRGGBBAA", ...],  # list, len <= MAX_PALETTE_SIZE (256)
  "metadata": { str: str },       # optional -> {}
  "frames": [                     # >= 1 frame
    { "duration_ms": int>0,       # default = DEFAULT_FRAME_DURATION_MS (post-remediation)
      "layers": [                 # >= 1 layer
        { "name": str="Layer", "opacity": float=1.0,
          "visible": bool=True, "locked": bool=False,
          "data": base64(zlib_level_9(raw_uint8)) } ] } ]
}
```

Bounds gates: canvas dims in `1..MAX_CANVAS_WIDTH`/`1..MAX_CANVAS_HEIGHT`; decompressed
payload capped at `MAX_CANVAS_WIDTH*MAX_CANVAS_HEIGHT*4`; payload length must **exactly**
equal `width*height*channels` (4 RGBA / 1 INDEXED). All I/O + JSON errors normalise to
`ProjectIOError`. The compression level `9` becomes a named `constants.py` value
(remediation), so the on-disk contract is unchanged but the number is single-sourced.

## 6. Implementation strategy

The shipped behaviour is frozen (retroactive). This plan authorises **one remediation
slice** only, ordered so no step changes any observable behaviour or breaks an import:

1. **Centralise tuning constants** in `logic/constants.py` (Article II): add
   `MAX_PALETTE_SIZE = 256`, `DEFAULT_FRAME_DURATION_MS = 100`, and
   `PROJECT_ZLIB_LEVEL = 9` (each with a source citation). `constants.py` stays a leaf
   (imports nothing intra-package), so no cycle is introduced.
2. **Reference the constants** from their former homes: `palette.py` and `document.py`
   import the names from `constants.py` and **re-export** them (keep the module-level
   name bound) so existing importers — notably `project_io` importing
   `MAX_PALETTE_SIZE` from `palette`, and `document` using `DEFAULT_FRAME_DURATION_MS`
   as a default arg — keep working with zero call-site churn.
3. **Dedupe in `project_io.py`:** replace the inlined `duration_ms` default `100`
   (project_io.py:204) with the imported `DEFAULT_FRAME_DURATION_MS`; use
   `PROJECT_ZLIB_LEVEL` at the `zlib.compress(..., 9)` site (project_io.py:44).
4. **Correct `compactor.py` header** (minimal correct fix): the header (lines 18–19)
   falsely claims atlas bounds "default MAX_CANVAS_WIDTH/HEIGHT from logic.constants
   when available"; `compact` in fact **requires** explicit `max_width`/`max_height`
   and imports nothing. The tested public interface is explicit-args, so the minimal
   correct fix is to **correct the header** to describe the real (explicit-args)
   contract — not to add a constants import/default that would change the signature and
   the tested behaviour. (Rationale: no behaviour change, no new test surface.)
5. **Standardise `CompactionError`** to subclass the common domain-exception base used
   by the other logic errors. The other five domain errors (`ColorError`,
   `PaletteError`, `PixelBufferError`, `DocumentError`, `ProjectIOError`) all subclass
   `ValueError`; there is no separate shared base. So `CompactionError(Exception)` →
   `CompactionError(ValueError)`, preserving the stable `reason` token and its
   `__init__`. This supersedes the CL-8 "intentional inconsistency" note (flagged to
   AGT-02, §9). AGT-04 adds/adjusts a regression assertion.
6. **EXEMPT — do NOT touch** (governed by ADR-0001, §7): intrinsic algorithmic literals
   in Bresenham/midpoint-ellipse (`2`, `0.5`, `0.25`) and format/RGBA-intrinsic
   constants (`0`, `255`, channel count `4`; `color.CHANNEL_MIN/MAX`; the `255.0` clamp
   in `blend_over`/`to_hex`; `pixel_buffer._normalise_value` `0..255`; project_io
   channel count `4` and `FORMAT_VERSION = 1`). These are not tuning parameters.

**Reversible-op boundary (for the UI increment, not this slice):** `logic/history.py`
stays the Qt-free do/undo core; `ui/commands.py` (Phase-1 UI increment, spec GAP-5)
will wrap `PixelEdit`/`record_edit` in a `QUndoCommand`. No Qt enters `logic/`.

**Ownership:** AGT-03 implements steps 1–5 (logic/data code); AGT-04 authors/adjusts
the tests and re-runs the coverage gate; AGT-01 re-runs `check_layering`/`check_cycles`
and then (and only then) runs `sdd-analyze` as the C1 gate. See `tasks.md`.

## 7. Constitution-compliance resolution (spec §9 S12 findings)

Adjudication of each spec §9 finding, split by the tuning-vs-intrinsic boundary that
**ADR-0001** records:

| Finding | Classification | Disposition |
| --- | --- | --- |
| S12-1 `MAX_PALETTE_SIZE=256` | **Tuning** (product index-space cap) | Move to `constants.py` (task T1/T2). |
| S12-2 `DEFAULT_FRAME_DURATION_MS=100` | **Tuning** (default timing) | Move to `constants.py` (task T1/T3). |
| S12-3 project_io inline `100` | **Duplication** | Import the constant (task T4). |
| S12-4 `CHANNEL_MIN/MAX`, `255.0` | **Intrinsic** (8-bit RGBA) | EXEMPT (ADR-0001). No change. |
| S12-5 `0..255`, channel `4` | **Intrinsic** (8-bit / RGBA shape) | EXEMPT (ADR-0001). No change. |
| S12-6 `zlib=9`; `4`; `FORMAT_VERSION=1` | zlib=9 **tuning**; `4`/version **intrinsic** | Move `zlib` level → `constants.py` (task T1/T4); `4`/version EXEMPT. |
| S12-7 compactor header vs `compact` args | Doc/interface drift | Correct header (task T5). |
| S12-8 Bresenham/ellipse literals | **Algorithmic** (intrinsic) | EXEMPT (ADR-0001). No change. |

## 8. Verification (already green pre-remediation; re-run post-remediation)

- `python scripts/check_layering.py` → `clean (11 modules)`, exit 0.
- `python scripts/check_cycles.py` → `no cycles (12 modules)`, exit 0.

These are the Article I gate. The remediation keeps `constants.py` a leaf and adds no
Qt, so both must remain exit 0 after implementation; AGT-01 re-runs them before
`sdd-analyze`.

## 9. Hand-back to AGT-02 (traceability deltas — AGT-01 flags, AGT-02 owns the matrix)

1. **REQ-P1-LOGIC-004** currently traces "(none / Ph3)". Actual: consumed in Phase-1 by
   `palette.nearest_index` and `drawing.flood_fill` tolerance. Retrace to its Phase-1
   consumers' S-ids (S7 palette / S1 drawing); this also closes the Article X "no S-id"
   analyze finding for -004 without inventing an S-id.
2. **REQ-P1-LOGIC-003** currently "S7 (indirect) + forward Phase-4". The
   alpha-compositing **capability** is consumed in Phase-1 by `blit(blend=True)` → add a
   Phase-1 consumption trace; keep the layer-blend-mode semantics forward → Phase 4.
   **Additional observation:** `color.blend_over` has **no in-code caller** (blit
   reimplements straight-alpha in NumPy) — a duplicate-logic / dead-public-function note
   for the analyze pass and for AGT-02's REV-2 disposition (kept as foundational, not
   removed).
3. **CL-8** disposition changes: the CompactionError/ValueError inconsistency is being
   **standardised** (T6), not accepted as-is. AGT-02 may update the CL-8 note to record
   the resolution.

## 10. Exit / status

- plan.md authored over the approved spec; module→layer map complete; stack fully
  grounded (no RESEARCH REQUEST needed); data model recorded; remediation slice defined
  and handed to `tasks.md`.
- Layering/cycle gates green pre-remediation.
- Trace deltas + CL-8 change flagged for AGT-02.
- **`sdd-analyze` deliberately NOT run** — it is the post-remediation C1 gate.
- **STATUS: COMPLETED.**
