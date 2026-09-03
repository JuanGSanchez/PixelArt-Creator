# ADR-0037 — Portable project-bundle format: a single-file, deterministic, zip-slip-defended archive extending `data/asset_export.py` (Phase-13)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-07 |
| Author | Architecture |
| Feature | `phase-13-cross-platform` (portable bundle) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0030 (asset-catalog CAS reference-not-copy), ADR-0032 (local-first storage abstraction), Phase-11 `data/asset_export.py` (the extended module) |

## Context

Phase-13 delivers a **self-contained, cross-OS project bundle** so a collaborator can hand a project
+ its assets to a teammate on a different OS with no missing/renamed/mis-cased file and no path-traversal risk
(REQ-P13-DATA-006..008). The spec directs this as an **extension of the shipped `data/asset_export.py`**
(Phase-11 REQ-P11-DATA-005), which already resolves a project's reference set → bundles exactly the referenced
CAS blobs into a **directory** artifact (catalog.json + per-asset sidecars + `blobs/`) with a full `eval`-free,
`resolve()`+containment import defence. This ADR rules the **bundle wire format** + the **import defence** for
the new **single-file** portable form. Article VII (untrusted input, no `eval`/`exec`) is an invariant.

## Decision

### 1. Format: a single-file deterministic zip archive (stdlib `zipfile`)

The portable bundle is a **single file** (`.pixbundle`) that is a **stdlib `zipfile` archive**
(`ZIP_DEFLATED`), embedding:

- the **`.pixproj` project payload** (the shipped deterministic PIO-1 serialiser output — unchanged),
- **every referenced CAS blob** the project depends on, resolved via the **shipped `asset_export`
  reference-set resolution** (no re-implemented CAS logic — Article I), stored once under a `blobs/`
  sub-path keyed by content hash,
- the **catalog + per-asset sidecars** (the shipped `asset_catalog_io` output).

**Determinism + portability (DATA-001/-002/-003).** Internal archive paths use **POSIX forward-slash**
separators (the portable zip convention) — never OS-native backslashes; text members are UTF-8; archive
member metadata (timestamps, mode) is fixed to constants so the same project yields a **functionally
equivalent** bundle on Windows/Linux/macOS (byte-stability is best-effort under `zipfile`; **model-equality on
import is the contract**, DATA-007). A **version tag** (`schema_version`) is embedded so import can reject an
unknown version.

Implemented as **new functions on the existing `data/asset_export.py`** — `export_project_bundle(...)` /
`import_project_bundle(...)` — composing `asset_cas` (blob resolution + hash-verified fetch) +
`asset_catalog_io` (catalog IO + its import defence) + `project_io` (payload). **No new module, no new import
edge**; the module stays a pure `data/` leaf (zero Qt; `data → data`, `data → logic` only).

### 2. Import defence (Article VII — untrusted input, no `eval`/`exec`)

Import treats the `.pixbundle` as **fully untrusted**, reusing + extending the shipped `asset_export` /
`asset_catalog_io` defence:

- **Path-traversal / zip-slip containment.** Every embedded entry's destination path is **`resolve()`d and
  constrained to stay within the import target directory** (reject any entry that resolves outside — `..`,
  absolute path, or symlink escape). On any violation the import **writes nothing** outside the target (fail
  before extract, or extract to a temp dir + atomic move only after full validation).
- **Size / count caps (zip-bomb defence).** Total bundle size ≤ `MAX_BUNDLE_BYTES`; embedded entry count ≤
  `MAX_BUNDLE_ENTRIES`; per-entry **uncompressed** size ≤ `MAX_BUNDLE_ENTRY_BYTES` (checked against the zip
  header **and** enforced during streamed extraction so a lying header cannot exhaust memory/disk). All three
  are **named constants** in `logic/constants.py` (Article II, §8 of the plan).
- **Content-hash verification.** Each embedded blob's bytes are verified against its content-hash key
  (`asset_cas` hash-verified fetch) — tamper defence.
- **`json`-only parse, defined error.** The catalog/manifest is parsed with `json` only — **never
  `eval`/`exec`**. A malformed / oversized / unknown-version / traversal / hash-mismatch bundle raises a
  defined **user-facing `AssetExportError`** (the PIO-1 `ProjectIOError` family) with **no partial-valid
  write** (no half-imported project left as if valid).

A **source audit** (no `eval(`/`exec(` on the import path) is an explicit acceptance step (SC-P13-DATA-008-2).

### 3. Cross-OS round-trip contract (DATA-005/-007)

A bundle exported on OS-A imports on OS-B to a **model-equal** project — same layers/frames/tilemaps/palettes/
references + **non-ASCII** (UTF-8) and **case-distinct** (case-sensitive lookup) asset names — honouring the
13A portability rules; exercised for all six ordered OS pairs in the CI matrix (REQ-P13-BUILD-001).

## Alternatives Considered

- **Keep the Phase-11 directory bundle (no single file).** Rejected for 13B: a directory is not a single
  self-contained artifact to "hand to a teammate"; the spec asks for a self-contained bundle. The directory
  exporter is retained (unchanged) for its existing use; 13B adds the single-file form beside it.
- **A bespoke binary container format.** Rejected: `zipfile` is stdlib (no dependency, D-consistent), portable,
  streamable (so per-entry caps can be enforced during extraction), and already the natural fit; a bespoke
  format would re-implement compression + a directory index for no gain and more attack surface.
- **`tarfile` instead of `zipfile`.** Rejected: `tar` carries POSIX ownership/mode + symlink semantics that
  are a portability + zip-slip hazard on Windows; `zipfile` with forward-slash internal paths + explicit
  containment is simpler to defend and more portable.
- **Trusting the zip header sizes.** Rejected (Article VII): a crafted header can under-report size (zip
  bomb); the per-entry cap is enforced during **streamed** extraction, not from the header alone.

## Consequences

**Positive.** One portable file carries everything to reconstruct a project cross-OS, self-contained, with a
provable path-traversal + zip-bomb + tamper defence that **reuses** the shipped `asset_export` /
`asset_catalog_io` / `asset_cas` discipline (no re-implemented CAS/parse logic — Article I) and stays
`eval`-free (Article VII). No new module, no new dependency, no new import edge; `data/` layer purity holds.

**Negative / risk.** `zipfile` byte-for-byte stability across OSes/Python patch versions is best-effort (member
ordering/metadata), so the contract is **model-equality on import** (DATA-007), not byte-identical archives —
the CI matrix asserts the former. Streamed per-entry cap enforcement adds a little import complexity vs a naive
`extractall` (which is unsafe and is **not** used).

## Grounding

- Spec §2 (13B scope), §4 REQ-P13-DATA-006/-007/-008, §5 (Article VII invariant), §8 DEP-4; `acceptance.md`
  SC-P13-DATA-006-1/-007-1/-008-1/-008-2; `traceability.md` 13B rows.
- Research note `acaae022` Q5 (path separators/UNC → forward-slash internal + `pathlib`; UTF-8; CRLF/LF; case
  sensitivity). Shipped `data/asset_export.py` (reference-set resolution + directory-bundle import defence —
  the extended module), `data/asset_catalog_io.py` (`json`-only + `resolve()`+containment), `data/asset_cas.py`
  (hash-verified fetch, `MAX_BLOB_BYTES`), `data/project_io.py` (PIO-1 deterministic payload).
- Constitution Article I (pure `data/`, no re-implementation), II (named caps in `constants.py`), IV
  (cross-OS regression in the matrix), VII (untrusted input, no `eval`/`exec`). ADR-0030 (reference-not-copy).

## Addendum A — implementation import note (2026-07-07, architecture; private, not committed)

The shipped `data/asset_export.py` bundle implementation (`export_project_bundle` / `import_project_bundle`)
additionally imports `logic.content_hash` (canonical-JSON encoder for the deterministic manifest) and
`logic.document` (the `Document` model for the payload round-trip), **beyond §1's literal enumeration** of
`asset_cas` / `asset_catalog_io` / `project_io`. Both are on the **pre-existing, allowed `data → logic`
edge** that §1 already declares ("`data → data`, `data → logic` only") — they add **no new layer edge and no
import cycle** (`check_layering --root pixelart_creator` exit 0 / 180 modules; `check_cycles --root
pixelart_creator` exit 0 / 182 modules, 2026-07-07 final gate). The §1 enumeration is illustrative of the
CAS/catalog/payload composition, not an exhaustive import allowlist; this note records the two additional
pure-`logic/` dependencies for completeness. The ADR decision is unchanged.
