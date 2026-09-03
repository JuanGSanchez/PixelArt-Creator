# ADR-0014 — Tiled JSON I/O scope: CSV-default + base64/gzip/zlib encodings, full 4-bit GID flag handling, embedded-emit + external-`.tsj` import, unknown-field verbatim passthrough

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-03 |
| Author | Architecture |
| Feature | `phase-6-tilemap` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 6 must **export a tilemap to Tiled-compatible JSON** and **re-import it losslessly**
(REQ-P6-DATA-001/-002), behind a **defensive validated load** (REQ-P6-DATA-003, IO-3). The spec
fixes only the WHAT (a valid Tiled map, lossless round-trip, defensive load) and defers the
**encoding set** — CSV vs base64+{gzip/zlib/zstd} layer data, embedded vs external tilesets, the
exact GID flag handling, and the round-trip fidelity policy — to architecture (DEP-2). Prior research
(`docs/research-phase-6-tilemap-20260703.md`, Topic 2/3) confirmed against **Tiled 1.12.2**: the map
object fields, the four layer-data encodings, the `chunks[]` infinite structure, and the exact GID
flag masks. Two hard constraints bound the choice: **no new technology (S8)** and **no `eval`/`exec`,
validated + bounds-checked load (Article VII)**.

## Decision

**Emit CSV by default (base64+gzip/zlib optional); parse CSV + base64-none/gzip/zlib on import;
reject zstd and external `.tsx`; handle the full 4-bit GID flag set with the documented
diagonal-clear and transform order; embed tilesets on export while accepting embedded + external
`.tsj` on import; and preserve unknown/extra fields verbatim for lossless round-trip.**

- **Encodings — emit.** Layer data is emitted **CSV by default** (`encoding:"csv"`) — the simplest,
  human-diffable, always-lossless form. **base64** with `compression:"gzip"` or `"zlib"` is offered
  as an option (both use the Python **stdlib**, no new dependency).
- **Encodings — accept.** Import accepts **CSV, base64-none, base64-gzip, base64-zlib**: base64
  decode → decompress → read the raw payload as **little-endian uint32** GIDs (research §2.3).
- **`zstd` rejected (S8).** `zstd` layer compression exists in Tiled since 1.3 but needs a non-stdlib
  package (`zstandard`); adding it violates S8 (no new technology). A `zstd`-compressed layer is
  **rejected with `ProjectIOError`** (defensive, explicit message), not silently mishandled.
- **GID flag handling (full 4-bit set).** Cells carry the Tiled 1.12.2 masks unchanged:
  `H=0x80000000`, `V=0x40000000`, `D=0x20000000`, `HexRot120=0x10000000`; the local id is
  `gid & 0x0FFFFFFF` **after subtracting `firstgid`**. The loader **clears the diagonal bit
  `0x20000000` even for non-hex maps** (documented Tiled gotcha, research §2.6 / Conflicts — a common
  "invalid tile id" source). Render applies the transform order **diagonal → horizontal → vertical**
  (orthogonal). The map buffer is numpy **uint32** so the flag nibble is representable without a
  separate transform plane (research Topic 3 / OD-8). The UI exposes at least H/V flip (CL-3); the D
  and hex bits are **preserved through round-trip** even though no UI authors them.
- **Embedded emit, embedded + external `.tsj` import.** Export **embeds** tilesets inline (each with
  `firstgid`) so our output is self-contained and lossless. Import accepts **embedded** tilesets and
  **external `.tsj`** (JSON) references (`{firstgid, source}` resolved via `pathlib`). External
  **`.tsx` (XML)** is **deferred** (`ProjectIOError`, clear message) — XML parsing is out of the
  Phase-6 scope and would need extra handling; our own round-trip is embedded↔embedded (lossless).
- **Round-trip fidelity — verbatim passthrough.** Fields Tiled expresses that the platform does not
  model (`properties`, `wangsets`, object/image/group layers, `backgroundcolor`, `nextlayerid`,
  `nextobjectid`, unknown top-level keys) are **preserved verbatim** (opaque passthrough) so
  export→import is byte-tolerant lossless (research OD-7). Concepts the platform does model
  (layers, per-cell gid + flip, visibility/order, geometry, tileset gid mapping) round-trip exactly.
- **Defensive load (Article VII / IO-3).** Reuse the `project_io.py` posture: validate map/tile
  geometry and layer sizes against the S12 bounds, gids against the declared tileset ranges,
  layer-data payload size against the declared geometry, and known encoding/compression/orientation;
  a malformed / out-of-bounds / oversized / unknown-orientation / zstd / `.tsx` document raises
  `ProjectIOError`. **No `eval`/`exec`.** Paths via `pathlib` (`path_portability_check`).

## Alternatives Considered

- **base64+zstd as the default (smallest files).** Rejected: `zstd` needs a new dependency (S8) and
  CSV is already lossless + diffable; file size is not a Phase-6 constraint.
- **CSV-only (drop base64).** Rejected: files in the wild use base64+gzip/zlib (research OD-4), and
  accepting them costs only stdlib code; a lossless *interchange* format should read what Tiled
  commonly writes.
- **External `.tsx`/`.tsj` on export.** Rejected for Phase 6: embedded output is self-contained and
  round-trips losslessly with one file; external references add path-management + `.tsx` XML parsing
  for no Phase-6 benefit. Import still accepts external `.tsj` for interop.
- **Normalise to our own subset (drop unknown fields).** Rejected: it makes reimport **lossy** for
  anything beyond our model, breaking the REQ-P6-DATA-002 lossless guarantee for files that carry
  properties/wangsets/object layers. Verbatim passthrough is cheap (dict carry) and honest.
- **Separate transform plane instead of uint32 flag nibble.** Rejected: the uint32 top-nibble layout
  maps 1:1 onto Tiled (research Topic 3 / OD-8), so a single array is both the internal model and the
  serialisation — no dual bookkeeping.

## Consequences

**Positive.** The exporter's default output is a valid, diffable, always-lossless Tiled map; the
importer reads what Tiled commonly writes (CSV + base64/gzip/zlib) and every foreign concept survives
round-trip via verbatim passthrough; the GID handling matches Tiled 1.12.2 exactly (including the
diagonal-clear gotcha), so flipped instances and multi-tileset gid mapping reimport identically; the
uint32 buffer is both the model and the wire format; no new dependency (S8 held); the load is
fail-closed (Article VII).

**Negative / risk.** `zstd` and external `.tsx` maps are refused rather than read — an explicit,
documented scope boundary (both would need new tech/parsing); users hitting them get a clear error,
not a crash. The verbatim-passthrough store must be threaded through export→import without mutation
(asserted by the SC-D002-1 round-trip test). The diagonal-clear rule is easy to miss — it is a
named, tested step.

## Grounding

- Spec `specs/phase-6-tilemap/spec.md` §4 (REQ-P6-DATA-001/-002/-003), §2/§6 (encoding set +
  embedded/external deferred to plan), §10 CL-3/CL-4/CL-7; `plan.md` §2/§6, §12 PL6-D5.
- Research `docs/research-phase-6-tilemap-20260703.md` Topic 2 (§2.1–§2.6 map/tileset/layer/chunk
  fields, encodings, GID flag masks + diagonal-clear + transform order), Topic 3 (instance linking,
  uint32 mapping), OD-4/OD-6/OD-7/OD-8, Conflicts (zstd since 1.3; diagonal-flag clearing).
- Constitution Article VII (validated, bounds-checked, no `eval`/`exec`; portable paths), VIII (S8 —
  no new technology), I (`tiled_io.py` Qt-free, `data → logic` edge).
- ADR-0015 (canonical uint32 cell bit layout lives in `logic/tilemap.py`; `tiled_io` imports it —
  no `logic → data` edge), IO-3 (`project_io.py` defensive-load pattern reused).
