# ADR-0006 — `.pixproj` schema version 2 (richer layer model) with backward-compatible v1 load

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-02 |
| Author | Architecture |
| Feature | `phase-4-layer-canvas` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 4 enriches the layer model: a per-layer `blend_mode`, layer **groups** (nested nodes),
**masks**, and **reference** / minimal **smart** layer flags/links (REQ-P4-LOGIC-011..014).
The ROADMAP "Done means" requires that opacity / visibility / lock **and** groups / masks
round-trip through `.pixproj`. DEP-3 directs architecture to allocate the `REQ-P4-DATA-*` IDs
(done in plan §7) and to rule the persistence extension.

The shipped `data/project_io.py` serialises a **flat** layer list with `name` / `opacity` /
`visible` / `locked` / `data` and stamps `FORMAT_VERSION = 1`. Its loader is **strict**:
`_require(version == FORMAT_VERSION, ...)` — it rejects any version other than 1. Adding new
fields and nesting therefore forces two decisions: (1) does the format version change, and
(2) must the new loader still read old files.

Article VII requires `.pixproj` load to stay defensive (validated, size/bounds-checked, no
`eval`/`exec`).

## Decision

**Bump `FORMAT_VERSION` to `2`, serialise the richer layer model under v2, and make the v2
loader read legacy v1 files (accept `version in {1, 2}`).**

- **Serialise (v2):** each node carries `blend_mode` (the `BlendMode` enum **value string**,
  e.g. `"multiply"`), `opacity`, `visible`, `locked`; **groups** are nested nodes with their
  own attributes and an ordered `children` list; a layer's **mask** is a compressed,
  geometry-validated buffer; **reference** is a bool and **smart** layers store a stable
  in-document source ref.
- **Deserialise (defensive, Article VII):** reject malformed / oversized / out-of-bounds
  payloads, an **unknown blend-mode string**, nesting past `MAX_GROUP_NESTING_DEPTH`, a layer
  count past `MAX_LAYERS_PER_FRAME`, and a **dangling smart-source ref** — each with
  `ProjectIOError`. No `eval`/`exec`; paths via `pathlib`.
- **Back-compat:** `version == 1` loads as before — flat layers, every layer `blend_mode =
  NORMAL`, no groups, no masks, `reference = False`, no smart source. `version == 2` loads the
  full model. Any other version is rejected (`ProjectIOError`). Saving always writes v2.
- `FORMAT_VERSION` remains a **format-intrinsic** constant local to `project_io.py` (ADR-0001
  precedent: `FORMAT_VERSION = 1` was ruled intrinsic, not a `constants.py` tuning value).

## Alternatives Considered

- **Keep `version = 1`, add optional fields only.** Rejected: it silently produces files a
  genuine v1 reader would mis-parse (new nested `children` / `mask` / `blend_mode` keys), with
  no version signal to distinguish them. A version bump is the honest, self-describing
  contract and lets the loader branch cleanly.
- **New file extension / new format module.** Rejected: over-engineered; `.pixproj` is the
  one project format (S7). A version field inside the existing format is the standard,
  lowest-friction evolution and preserves one save/open path in the UI.
- **v2-only loader (drop v1 support).** Rejected: it would orphan every file saved by
  Phases 1–3. Reading v1 is cheap (defaults fill the new fields) and the ROADMAP implies
  forward continuity. Back-compat read is mandatory; back-compat *write* is not (v1 readers
  are not expected to open v2 — acceptable forward-incompatibility).

## Consequences

**Positive.** Groups / masks / blend-mode / reference / smart round-trip (REQ-P4-DATA-001..004);
old projects keep opening (REQ-P4-DATA-005); the version field makes the format self-describing
for future phases (animation timeline, tilemaps). One save/open path, one defensive validator.

**Negative / risk.** The loader now has two branches (v1 / v2); both are covered by the test suite
tests, including a **checked-in v1 fixture** that must load and re-save as v2. The
smart-source ref must be addressable stably within a document; the serializer pins a
document-local ref scheme and the loader rejects dangling refs (fail-closed, Article VII).

## Grounding

- Spec `specs/phase-4-layer-canvas/spec.md` §8 DEP-3, §9 (Article VII validated load); plan
  §2/§7/§8; `REQ-P4-DATA-001..005` (allocated plan §7).
- ROADMAP "Done means": layer model round-trips through `.pixproj`.
- Constitution Article VII (validated, bounds-checked, no `eval`/`exec`).
- ADR-0001 — `FORMAT_VERSION` is format-intrinsic (stays local to `project_io.py`).
- Shipped `data/project_io.py` (strict `version == FORMAT_VERSION` check being relaxed to
  `{1, 2}`).
