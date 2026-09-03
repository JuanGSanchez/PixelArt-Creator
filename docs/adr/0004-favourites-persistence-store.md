# ADR-0004 — Favourites persist in an app-level JSON store, not on .pixproj or QSettings

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-02 |
| Author | Architecture |
| Feature | `phase-3-colour-palette` |
| Supersedes | — |
| Superseded by | — |

## Context

REQ-P3-LOGIC-015 / REQ-P3-UI-004 (CL-4, US-2) require the colour-hub **Favourites** list to
**persist across sessions** — "my working palette follows me between sessions" — with
cross-session persistence flagged **acceptance-critical** (SC-U004-3: a saved favourite is present
after an app restart). The spec (§4.1, CL-4) fixes the *model* (`logic/favourites.py`: ordered,
de-duplicated, `to_serializable`/`from_serializable`) as Qt-free logic, and **defers the storage
location to architecture**: "a small `data/` JSON via the data layer, or app settings".

Three constraints shape the call:

- **Article I (layer purity).** The persistence path must not put Qt in `logic/` or `data/`; only
  `ui/` (and `ui/commands.py`) may touch Qt.
- **Article VII (defensive I/O, portable paths).** Persisted input is validated defensively (no
  `eval`/`exec`); the path is built portably (`pathlib`; `path_portability_check`).
- **Scope.** Favourites are an **app-level, cross-document, cross-session preference** (they follow
  the user, not a document) — unlike palettes embedded in a `.pixproj`.

## Decision

1. **A dedicated app-level JSON store via a new `data/` module.** Favourites persist through a new
   Qt-free **`pixelart_creator/data/favourites_io.py`** — `save_favourites(path, favourites)` /
   `load_favourites(path)` — that serialises `Favourites.to_serializable()` (a list of
   `#RRGGBBAA` hex strings) to a JSON file. It mirrors the existing `data/project_io.py` pattern
   (validated, defensive, `pathlib`). A **missing file loads as an empty `Favourites`**; malformed
   content raises `FavouritesIOError` (never crashes, Article VII).

2. **The UI resolves the config path; `data/` stays Qt-free.** The application-config directory is
   resolved **UI-side** via `QStandardPaths.writableLocation(AppConfigLocation)` and passed to
   `data/favourites_io` as a `Path`. `data/` never imports Qt — it reads/writes the `Path` it is
   given (Article I preserved). The colour hub (`ui/colour_hub_menu.py`) loads Favourites at
   startup and saves on every add/remove/reorder.

3. **NOT stored on `.pixproj`.** `.pixproj` is a **per-document** artifact; Favourites are a
   user-global preference that must survive across documents and when no document is open. Riding
   on `project_io` would tie the working palette to one file and lose it between projects — the
   opposite of the requirement.

4. **NOT stored as raw QSettings values in `ui/`.** QSettings would push persistence into the Qt
   layer and bypass the Qt-free, testable `to_serializable`/`from_serializable` contract the spec
   fixes; a `data/` JSON store keeps persistence headlessly testable (SC-U004-3 verifiable via a
   `data/favourites_io` round-trip without a running app) and consistent with `project_io`.

## Alternatives Considered

- **Embed in `.pixproj` (via `project_io`).** Rejected: per-document scope contradicts
  "follows me between sessions"; Favourites would vanish when switching/closing projects.
- **QSettings in `ui/`.** Rejected: relocates persistence into Qt, side-stepping the Qt-free
  serialisable-model contract and making the acceptance-critical persistence test require a Qt
  settings backend rather than a pure round-trip.
- **A `logic/` file-writer.** Rejected: disk I/O is a `data/`-layer responsibility (Article I);
  `logic/favourites.py` stays a pure model with only `to/from_serializable`.

## Consequences

- One new Qt-free `data/` module (`favourites_io.py`) — small, mirrors `project_io.py`, covered by
  `tests/data/test_favourites_io.py`: round-trip, missing-file→empty, malformed→`FavouritesIOError`,
  path portability.
- The persistence path is fully headless-testable, satisfying SC-U004-3 without a live app.
- Layer purity holds: model in `logic/`, I/O in `data/`, Qt path-resolution in `ui/`.
- If a future need arises to sync Favourites with cloud/collab (roadmap Phases 10–11), the JSON
  serialisable form is already the interchange unit — additive, not a rewrite.

## Grounding

- `specs/phase-3-colour-palette/spec.md` §4.1 REQ-P3-LOGIC-015, REQ-P3-UI-004, CL-4, US-2, §11
  SC-U004-3; `traceability.md` §2.
- `constitution.md` Article I (layer purity), Article VII (defensive I/O + portable paths);
  `data/project_io.py` (the mirrored persistence pattern).
- `docs/research-phase3-colour.md` (QColor HSV APIs are UI-side; logic stays tuple maths).
