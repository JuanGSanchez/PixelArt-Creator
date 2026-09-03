# ADR-0016 — `.pixproj` schema version 4 (tilesets + tilemaps on `Document`) with v1/v2/v3 back-compat load

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-03 |
| Author | Architecture |
| Feature | `phase-6-tilemap` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 6 attaches **tilesets** (source-image reference + slicing config) and **tilemaps** (layer
stack + linked instances + auto-tile logical placement) to the `Document` (DOC-1), and requires them
to **round-trip natively in `.pixproj`** while **older tilemap-less projects still open**
(REQ-P6-DATA-004). The shipped `data/project_io.py` is at **`FORMAT_VERSION = 3`**
(`_SUPPORTED_VERSIONS = (1, 2, 3)`, ADR-0012 — frame tags + `layer_id`). DEP-2 directs architecture to rule
whether the tilemap data is a **schema-version bump** or an **additive field** on v3, and whether
tilemaps live in the one `.pixproj` document or a separate tilemap doc-type. Article VII requires the
load stay defensive (validated, bounds-checked, no `eval`/`exec`).

## Decision

**Bump `FORMAT_VERSION` to `4`; serialise `Document.tilesets` + `Document.tilemaps` inside the one
`.pixproj` document; accept `version in {1, 2, 3, 4}`; load v1/v2/v3 with empty tileset/tilemap
collections. Saving always writes v4.**

- **Composition — one document, two new collections.** `Document` gains `tilesets: List[Tileset]`
  and `tilemaps: List[Tilemap]` (added to `__slots__`, created empty), alongside the existing frames
  and `frame_tags`. Tilesets and tilemaps live **in the one project document** — not a separate
  doc-type or sidecar file. `.pixproj` remains the single project format (S7).
- **Serialise (v4).** A document-level `"tilesets"` array (each: source-image reference + `tile_width`
  /`tile_height`/`margin`/`spacing`/`name`/`first_gid`) and a `"tilemaps"` array (each: `name`,
  `infinite`, tile geometry, an ordered `layers` list with per-layer name/visibility/opacity, the
  **sparse cell data** as chunk-keyed uint32 payloads, and the **auto-tile logical placement** +
  ruleset per layer). Frames, `frame_tags`, `layer_id` and the v2/v3 layer model are **unchanged**
  (reused). The native form stores the **logical** placement (not baked display frames), keeping
  auto-tiling reversible on reload (ADR-0013).
- **Deserialise (defensive, Article VII / REQ-P6-DATA-003).** Reject a malformed tileset/tilemap
  object, an out-of-bounds tile/map geometry, a gid outside the referenced tileset ranges, an
  oversized cell payload, a non-list `tilesets`/`tilemaps`, or an unknown orientation flag — each with
  `ProjectIOError`. No `eval`/`exec`; paths via `pathlib`. A payload **without** `tilesets`/`tilemaps`
  loads with empty collections (back-compat).
- **`FORMAT_VERSION` intrinsic-local.** `_SUPPORTED_VERSIONS = (1, 2, 3, 4)`; the v3 frame/tag/layer
  parse path is reused, extended only to read tilesets + tilemaps. `FORMAT_VERSION` stays
  format-intrinsic, local to `project_io.py` (ADR-0001/0006/0012 precedent).

## Alternatives Considered

- **Additive optional field on v3 (no version bump).** Rejected — the same reasoning ADR-0006/0012
  used: `tilesets`/`tilemaps` are **new document-level semantics**, and the version field is the
  honest, self-describing signal. A v4 stamp makes a Phase-5 v3 reader **fail-closed** on a
  tilemap-bearing file rather than silently dropping the level data (Article VII posture). The bump
  costs nothing: v1/v2/v3 still load with empty collections.
- **Separate `.tmap`/tilemap doc-type or sidecar file.** Rejected: over-engineered; `.pixproj` is the
  one project format (S7), and a version field inside it is the standard evolution (ADR-0012
  rejected a tag sidecar for the same reason). Tilemaps are part of the document and must reopen with
  it.
- **Store the Tiled JSON shape inside `.pixproj`.** Rejected: Tiled JSON is the **interchange**
  format (ADR-0014, REQ-P6-DATA-001); the native format stores the platform's own model (incl. the
  auto-tile logical placement, which Tiled does not natively carry the way we model it). Conflating
  the two would couple native persistence to the export schema.
- **v4-only loader (drop v1/v2/v3).** Rejected: orphans every file saved by Phases 1–5. Back-compat
  read is mandatory; back-compat *write* is not (forward-incompat is acceptable, per ADR-0006/0012).

## Consequences

**Positive.** Tilesets + tilemaps round-trip losslessly (REQ-P6-DATA-004); tilemap-less v1/v2/v3
projects keep opening (back-compat); the version field keeps the format self-describing; one
defensive validator, one save/open path. Storing the logical auto-tile placement keeps reload
reversible and consistent with ADR-0013.

**Negative / risk.** The loader gains a fourth branch (v1/v2/v3/v4); all are covered by the test suite tests,
including a checked-in v3 fixture that loads (empty collections) and re-saves as v4. Tileset/tilemap
validation must be fail-closed (Article VII) — the loader rejects malformed/out-of-range data rather
than clamping. The `Document.__slots__` extension is additive and must not break the shipped
frame/tag serialisation (asserted by the reused v3 round-trip tests).

## Grounding

- Spec `specs/phase-6-tilemap/spec.md` §4 (REQ-P6-DATA-004), §8 DEP-2, §10 CL-16; `traceability.md`
  DEP-2; `plan.md` §3.2/§6, §12 PL6-D7.
- Research `docs/research-phase-6-tilemap-20260703.md` Topic 3 (tilemap = uint32 GID grid; tileset =
  index of regions) — the native shape mirrors the model, not the Tiled wire form.
- ADR-0006 (`.pixproj` v2 + version-bump rationale + v1 back-compat), ADR-0012 (`.pixproj` v3 +
  `_SUPPORTED_VERSIONS` growth + native-over-export-shape), ADR-0001 (`FORMAT_VERSION`
  intrinsic-local), ADR-0013 (auto-tile logical placement), ADR-0014 (Tiled JSON is the separate
  interchange path).
- Constitution Article VII (validated, bounds-checked, no `eval`/`exec`), II (`FORMAT_VERSION`
  intrinsic exemption), XI (extensible schema evolution).
- Shipped `data/project_io.py` (`FORMAT_VERSION = 3`, `_SUPPORTED_VERSIONS = (1, 2, 3)` → `(1, 2, 3, 4)`).
