# ADR-0025 — `.pixproj` schema v5 (`Document.ppi`) + visual-aids persistence formats (timelapse session, `.pixboard` reference board)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-9-visual-aids` |
| Supersedes | — |
| Superseded by | — |

## Context

Real-size preview needs a document **PPI** (ADR-0023 §4, spec BF-3 / CL-3): `real_size_scale(doc_ppi,
screen_dpi)`. The shipped Phase-1 `Document` has **no** PPI attribute (verified: `Document.__slots__` =
`width, height, mode, palette, frames, metadata, frame_tags, tilesets, tilemaps, _next_layer_id`). ADR-0024
allocated **REQ-P9-DATA-001** (timelapse session persistence) and **REQ-P9-DATA-002** (reference-board
persistence), deferring the concrete **formats** here. This ADR rules the persistence/schema HOW:

1. is `Document` PPI a first-class field or a preview-only setting (BF-3)? and how is it persisted?
2. the timelapse-session wire format (REQ-P9-DATA-001);
3. the reference-board wire format (REQ-P9-DATA-002).

The shipped `.pixproj` has evolved defensively before: v2 layer model (ADR-0006), v3 frame tags
(ADR-0012), v4 tilesets/tilemaps (ADR-0016), each loading older versions unchanged. `data/project_io.py`
is the IO-3 defensive-load pattern (`ProjectIOError`, `_SUPPORTED_VERSIONS`, type/bounds checks, no
`eval`, `pathlib`).

## Decision

### 1. `Document.ppi` is a first-class field, persisted as `.pixproj` **v5** (BF-3)

- **`Document` gains `ppi: float`**, added to `__slots__` and `__init__` (keyword-only, default
  `DEFAULT_DOCUMENT_PPI = 72.0`). Real-size is a genuine **document property** (how large the artwork is
  meant to print/appear), not a transient preview setting — a first-class field is the principled choice
  and keeps `real_size_scale` sourced from the document (ADR-0023 §4). Validated (> 0, finite) by the
  setter; out-of-range → `DocumentError`.
- **`.pixproj` schema bumps to v5**: `project_io.save_project` writes `ppi`; `load_project` reads it
  **defensively** — a v1–v4 file (no `ppi` key) loads **unchanged** with `ppi = DEFAULT_DOCUMENT_PPI`, an
  out-of-range/malformed `ppi` → `ProjectIOError` (IO-3). `_SUPPORTED_VERSIONS` extends to include `5`.
  This mirrors the v2/v3/v4 additive-evolution precedent exactly (ADR-0006/0012/0016). PPI persistence is
  therefore an extension of the **shipped** `project_io` grounded by REQ-P9-LOGIC-007 — **not** a new
  `REQ-P9-DATA-*` serialiser (ADR-0024 §4).
- The **manual-calibration screen DPI** (ADR-0023 §4) is a per-monitor *UI/preview* setting, **not** a
  document field — it is not persisted in `.pixproj` (it belongs to the machine, not the artwork).

### 2. Timelapse session format (REQ-P9-DATA-001) — `data/timelapse_io.py`, defensive `eval`-free

- **Format:** a JSON manifest serialising the pure `TimelapseSession` — `schema_version` (a module-local
  format-intrinsic string, ADR-0001), and an ordered list of `{index, command_id}` frame records (the
  command manifest, **not** inline pixel data — frames are re-rendered on replay, ADR-0024 §2). Bounded
  by `MAX_TIMELAPSE_FRAMES`.
- **Storage location: a sidecar** — a `.pixtimelapse` file (or a scratch/session folder), **not** inside
  `.pixproj` (a timelapse is a session artifact, not part of the saved artwork; keeps `.pixproj` small
  and stable). The rendered frame *images* and any GIF/MP4 encoding are out-of-scope derivatives
  (ADR-0024 §2 / CL-16).
- **Load posture (IO-3):** every field type/bounds-checked; malformed/out-of-bounds/unknown
  `schema_version` → `TimelapseIOError(ProjectIOError)`; content **never** passed to `eval`/`exec`;
  portable paths (`path_portability_check`). **Round-trip gate:** a saved-then-reloaded session
  **replays to the identical frame sequence** (SC-L010-1).

### 3. Reference-board format (REQ-P9-DATA-002) — `data/reference_board_io.py`, defensive `eval`-free

- **Format:** a `.pixboard` JSON sibling (mirrors PureRef's `.pur`, Researcher §7.2) serialising
  `schema_version` + board view state (pan/zoom) + an ordered list of reference-image records
  `{image (path reference **or** embedded base64 bytes), transform (2×3 affine as 6 floats), crop (x, y,
  w, h), z_order}`. Bounded by `MAX_REFERENCE_IMAGES`. A pure board-layout dataclass lives in `data/`
  (no Qt) so the serialiser round-trips a plain model; the UI maps it to `QGraphicsPixmapItem`s
  (ADR-0024 §3).
- **Image reference: path OR embedded.** Default is a **path reference** (portable, small); embedding
  (base64) is an option for a self-contained board. Both loaded defensively.
- **Load posture (IO-3):** type/bounds-checked; malformed/unknown-version → `ReferenceBoardIOError(
  ProjectIOError)`, surfaced to the user (no crash, **never** `eval`/`exec`); portable paths. The board
  is **non-destructive** — nothing here touches the document or its undo history (REQ-P9-UI-010).

## Alternatives Considered

- **PPI as a preview-only UI setting (not a `Document` field).** Rejected: real-size is a property of the
  artwork; a transient setting would not persist with the project and would fragment the source of the
  `f(PPI, DPI)` input (spec BF-3 leans to a document attribute).
- **PPI stored in `Document.metadata` (str→str, no schema bump).** Rejected: hacky numeric-as-string, not
  a clean data-model; a first-class validated field + additive v5 bump matches the shipped
  schema-evolution precedent.
- **Timelapse embedded inside `.pixproj`.** Rejected: a session artifact bloats the artwork file and
  couples save cadence; a sidecar keeps `.pixproj` stable (the export-artifact-vs-project precedent).
- **Storing rendered timelapse frames inline.** Rejected: breaks reproducibility-by-replay and bloats the
  file (ADR-0024 §2; Researcher §6.3) — store the command manifest, re-render.
- **A brand-new schema ADR-less bump.** Rejected: schema bumps have dedicated ADRs (0006/0012/0016); v5 is
  documented here for the same auditability.

## Consequences

**Positive.** Real-size has a persisted, validated document PPI with zero breakage for v1–v4 files
(defensive default). Two clean `eval`-free serialisers (`timelapse_io`, `reference_board_io`) each with a
round-trip gate, matching the `project_io` posture (IO-3) and independently testable
(`tests/data/test_timelapse_io.py`, `tests/data/test_reference_board_io.py`). The timelapse model stays
small and reproducible (manifest, not pixels); the board stays non-destructive and portable.

**Negative / risk.** A `.pixproj` v5 bump touches the **shipped** `project_io` — AGT-03 must keep v1–v4
load byte-for-byte unchanged (a regression test on the existing fixtures is mandatory) and AGT-04 must
cover the absent-PPI-defaults path. Embedded-image boards can grow large (mitigated: path reference is
the default). Three persistence surfaces (v5 PPI + two sidecars) widen the `data/` test surface; each is
defensive JSON validation, the established pattern.

## Grounding

- Spec `specs/phase-9-visual-aids/spec.md` §4 (REQ-P9-LOGIC-007 real-size PPI), REQ-P9-UI-006
  (reference-board defensive persistence), REQ-P9-LOGIC-010 (timelapse defensive persistence), §7
  (PREFIX-NOTE, IO-3 reuse), §8 (BF-3, DEP-2d, DEP-4), §9 Article VII, §10 CL-3/CL-11/CL-15, §11
  SC-L010-1/SC-UI-006-1; `traceability.md` IO-3 forward trace, DEP-4.
- Research `docs/research-phase-9-visual-aids-20260704.md` §4 (real-size PPI/DPI), §6.3 (store manifest,
  re-render), §7.2 (reference-board persistence fields; `.pur` → `.pixboard`), §9 Open-decisions 7/9.
- Shipped `data/project_io.py` (IO-3; `_SUPPORTED_VERSIONS`; v2/v3/v4 additive evolution), `logic/document.py`
  (`Document.__slots__`/`__init__` — no PPI today), `logic/blend.py` (CO-4). Constitution Article II
  (`DEFAULT_DOCUMENT_PPI` in `constants.py`), Article VII (defensive `eval`-free load). ADR-0006/0012/0016
  (`.pixproj` v2/v3/v4 schema-evolution precedent), ADR-0023 §4 (real-size scale consumes `doc_ppi`),
  ADR-0024 §2/§3/§4 (timelapse model, reference-board model, DATA-prefix allocation), ADR-0001
  (module-local `schema_version`).
