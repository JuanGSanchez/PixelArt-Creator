# Plan — In-App User Guide (`user-guide`, `REQ-UG-*`)

| Field | Value |
| --- | --- |
| Feature | `user-guide` (cross-cutting, not a single roadmap phase) |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VII, VIII, X, XI) |
| Consumes | `specs/user-guide/spec.md` (COMPLETE, clarified CL-1..6) + `traceability.md` (19 REQ, 0 uncovered) |
| Key decision | **ADR-0029** — committed content source, offline bundling, three-layer design |
| SDD phase | `plan` → consumed by `sdd-tasks` (this repo: `tasks.md`) → `sdd-analyze` gate → implement |

This plan defines **HOW** to build the clarified `user-guide` spec. The load-bearing architecture
decision — the shipped content source and its bundling — is ruled in **ADR-0029** and summarised in §2.

---

## 1. Architecture overview

Three purity boundaries, exactly as the spec's Article-I split requires:

- **Content model (`logic/`, zero Qt)** — builds the ordered section→topic tree from a discovered
  manifest, answers a pure search query, resolves a topic's content for the active locale, and
  enforces the coverage contract. Unit-testable with no Qt.
- **Offline bundled-content reader (`data/`, zero Qt)** — reads the committed bundle (manifest +
  per-topic Markdown) via `importlib.resources`, guards paths within the bundle root, surfaces domain
  errors, makes no network access.
- **Viewer (`ui/`, the only Qt)** — Help ▸ User Guide action + F1, the navigable window/panel (ToC tree
  + `QTextBrowser` content pane + search box). It *calls* the model/reader and renders; it implements
  no domain logic and hard-codes no ToC (Article I).

Baseline is green: `check_layering` clean (154 modules), `check_cycles` no cycles (155), both exit 0
(2026-07-04). Every new module MUST keep both at exit 0.

## 2. Content source & bundling (RESOLVED — ADR-0029)

**Critical constraint resolved.** The spec's DEP-2 recommends single-sourcing from `docs/site`, but
constitution **S19** makes `docs/**` **PRIVATE — gitignored AND purged from history** (`.gitignore`
lines 55–60). `docs/site` is therefore **absent from the repository, the CI checkout, and the
distributable**, so it **cannot** be the shipped source. Per Article VIII / C1, the plan conforms to
the constitution:

- **Shipped single source = a COMMITTED package-data directory:** `pixelart_creator/userguide_content/`
  — `manifest.json` (the ToC declaration) + `content/<locale>/<topic_id>.md` (per-topic Markdown). It
  is committed to git, shipped in the wheel as package data (AGT-09 `pyproject` edit), discovered and
  rendered **fully offline**. The app has **ZERO** dependency on `docs/site`.
- **Format:** Markdown, rendered as text/markup via `QTextBrowser`/`QTextDocument.setMarkdown()` —
  never executed (Article VII).
- **Discovery/extensibility:** `manifest.json` declares ordered sections→topics (id, title,
  keywords/summary, content ref). Adding a topic = add a `.md` file + a manifest entry (**data, not
  code**) — no `logic/`/`ui/` change (Article XI). Deterministic order.
- **Locale:** resolve `content/<active_locale>/<topic_id>.md`, else fall back to
  `content/en/<topic_id>.md` (`DEFAULT_GUIDE_LOCALE`). Pure function; localised docs are added files.
- **Relationship to `docs/site` (no-drift, C1-compliant):** `docs/site` stays AGT-08's **separate,
  private, public-facing mkdocs site**. AGT-08 authors the prose **once** and keeps both rendering
  targets — the committed in-app bundle and the private HTML site — in sync via a **local derivation
  step** run where `docs/site` exists. No-drift is an editorial discipline (single authoring source),
  **not** a runtime path into the private tree, and **not** a CI gate against `docs/site` (CI cannot
  see it; any drift check compares against the committed bundle). This is spec §8 **option (b)
  (committed mirror)**, not option (a) (fresh fork).

## 3. Module design & public surface (frozen for `interface-contract`)

> Frozen BEFORE implementation so AGT-03/AGT-05/AGT-04/AGT-06 bind to a stable contract. Exceptions
> subclass `ValueError` (repo convention). Ids/locale codes are string identifiers (Article II governs
> numerics only), homed in the manifest, not `constants.py` (spec §9).

### 3.1 `logic/guide_model.py` (new, zero Qt) — REQ-UG-LOGIC-001/-002/-004/-005
- `GuideTopic` (frozen dataclass): `id: str`, `title: str`, `content_ref: str`, `keywords: tuple[str, ...]`, `summary: str`.
- `GuideSection` (frozen dataclass): `id: str`, `title: str`, `topics: tuple[GuideTopic, ...]`.
- `GuideModel`: `sections: tuple[GuideSection, ...]`; `topics() -> tuple[GuideTopic, ...]` (flattened, ordered); `topic(topic_id) -> GuideTopic` (raises `GuideModelError` if unknown).
- `build_model(manifest: Manifest) -> GuideModel` — deterministic ordered tree from the discovered manifest (REQ-UG-LOGIC-001/-002).
- `resolve_content_ref(model, topic_id, active_locale, *, default_locale=DEFAULT_GUIDE_LOCALE, available_locales) -> str` — locale resolution with fallback (REQ-UG-LOGIC-004).
- `REQUIRED_AREAS: tuple[str, ...]` (module-local vocabulary, ADR-0001) + `missing_required_areas(model) -> tuple[str, ...]` — coverage contract; empty tuple = complete (REQ-UG-LOGIC-005).
- `GuideModelError(ValueError)`.

### 3.2 `logic/guide_search.py` (new, zero Qt) — REQ-UG-LOGIC-003
- `query(model: GuideModel, term: str, *, cap: int = GUIDE_SEARCH_RESULT_CAP) -> tuple[GuideTopic, ...]` — pure, case-insensitive, deterministic; matches over each topic's indexed text (title + keywords + summary); empty/whitespace term → the full topic set (CL-2); stable ordering; capped.

### 3.3 `data/guide_content.py` (new, zero Qt) — REQ-UG-DATA-001/-002/-003
- `Manifest` (frozen dataclass mirroring `manifest.json`) + `available_locales() -> frozenset[str]`.
- `load_manifest() -> Manifest` — read `userguide_content/manifest.json` via `importlib.resources.files("pixelart_creator") / "userguide_content"`; defensive parse (type/bounds), malformed → `GuideContentError`.
- `read_content(content_ref: str) -> str` — resolve a manifest-known content ref to bundled Markdown text; **validate the resolved path stays within the bundle root** (reject traversal/absolute → `GuideContentError`); enforce `GUIDE_MAX_CONTENT_BYTES`; **no network**, **no `eval`/`exec`**; portable paths (`path_portability_check`).
- `bundle_root()` helper (traversable). `GuideContentError(ValueError)`.

### 3.4 `logic/constants.py` (extend, leaf) — Article II / NFR-6
- `GUIDE_SEARCH_RESULT_CAP = 50` (search result cap).
- `GUIDE_MAX_CONTENT_BYTES = 1_048_576` (per-topic content-size guard, 1 MiB — defensive reader bound).
- `GUIDE_MAX_TOC_DEPTH = 3` (section → topic → sub-topic ceiling).
- `DEFAULT_GUIDE_LOCALE = "en"` **is a string identifier, not a numeric** — homed as a module-local
  constant in `guide_model.py`/`guide_content.py` (ADR-0001), NOT in `constants.py` (Article II governs
  numerics; spec §9). Names above are DISTINCT from every shipped constant.

### 3.5 `ui/user_guide.py` (new, Qt) — REQ-UG-UI-003..011
- `User_Guide_Dialog(QDialog)` (or `_Panel`; CL-6 leaves window-vs-dock to AGT-05) with: a ToC
  `QTreeWidget`/view built from `GuideModel`; a `QTextBrowser` content pane
  (`setOpenExternalLinks(False)`, `setMarkdown`); a search `QLineEdit` calling `guide_search.query` and
  listing results → jump to topic. All chrome strings `tr()`-wrapped; `changeEvent` re-sets on
  `QEvent.LanguageChange` (Article V); role-based theme colours (both themes); accessible names +
  keyboard nav + visible focus (a11y). In-guide links navigate within the guide only; content-load
  errors surface a user-facing message (no crash).

### 3.6 `ui/main_window.py` (extend, Qt) — REQ-UG-UI-001/-002
- Add a **Help** menu (if absent) with a `tr()`-wrapped **User Guide** `QAction`, shortcut **F1**
  (shown on the action), opening `User_Guide_Dialog`.

## 4. Content bundle layout (AGT-08 authoring target) — REQ-UG-LOGIC-005 / -UI-008

`pixelart_creator/userguide_content/`:
- `manifest.json` — ordered sections→topics with ids/titles/keywords/summaries/content refs.
- `content/en/*.md` — one Markdown file per topic, covering **every** required area:
  canvas & view, colour hub, layers, selection/transform, animation timeline, tileset/tilemap editor,
  export & pipeline, automation/scripting, visual aids, **cloud & collaboration** (connect/manage,
  shared projects, comments, presence, branching), and app-wide basics.

**Authoring scope note.** `docs/site/pages/usage/` today has pages for layers, blend-modes,
multi-canvas, floating-selection, drag-drop-import, animation, tilemap, export, automation,
visual-aids, **cloud, collaboration** — but **no dedicated pages** for **canvas & view**, **colour
hub**, **selection/transform**, or **app-wide basics**. AGT-08 must **author those committed topics**
(and organise all existing prose into the topic tree) so the coverage contract passes. Cloud/collab
content already exists (`cloud.md` + `collaboration.md`) → DEP-1 sequencing is satisfied
(Phase-10 docs shipped). This prose authoring is a **substantial task covering all shipped phases
1–10** (T-UG-02).

## 5. Stack & grounding

- **Existing stack only** (S8 — no new technology): PySide6/Qt6 (`QTextBrowser`, `QTextDocument`,
  `QTreeWidget`, `QAction`, `QKeySequence`), stdlib `importlib.resources` + `json` + `pathlib`,
  pytest/pytest-qt/Hypothesis. `QTextDocument.setMarkdown` is native Qt6 — no new dependency. No
  Researcher grounding is required (the WHAT is fixed; the widget is a native Qt facility). If AGT-05
  wants a richer renderer later, it stays behind the `ui/user_guide.py` seam.

## 6. Constitution compliance

- **Article I / NFR-1:** model + search zero-Qt in `logic/`; reader zero-Qt in `data/`; viewer + menu
  the only Qt. `check_layering`/`check_cycles` stay exit 0 (enforced at implement).
- **Article II / NFR-6:** the 3 numeric guide constants live only in `constants.py`; string ids/locales
  are not constants-file entries.
- **Article IV / NFR-7:** ≥90 % line / ≥80 % branch; logic/data via pytest (+ Hypothesis for
  discovery/search/locale invariants); UI via pytest-qt headless, both themes.
- **Article V / NFR-8:** a11y + both themes + `tr()` chrome + localisable content.
- **Article VII / NFR-3/4/5:** offline, no `eval`/`exec`, bundle-root path guard, content-size guard,
  read-only, portable paths.
- **Article VIII / C1:** the DEP-2 (`docs/site`) recommendation is conformed to the constitution
  (committed bundle) — the gate is not weakened.
- **Article X / DEP-5:** the `REQ-UG-*` cross-cutting prefix substitutes a feature key for a phase
  number in the Article-X scheme; **AGT-01 ratifies it** for cross-cutting (non-phase) features — a
  documented labelling extension, not acceptance-changing.
- **Article XI / NFR-9:** adding a bundled doc adds guide content with no code change.

## 7. Risks

- **No-drift is an authoring discipline, not a CI gate** (docs/site invisible to CI) — mitigated by
  AGT-08 ownership + the local sync step (ADR-0029 Consequences).
- **Coverage-contract authoring gap** — canvas&view/colour-hub/selection-transform/app-wide-basics
  topics must be authored fresh into the bundle (T-UG-02); tracked, not blocking the plan.

## 8. Exit

- Plan authored over the COMPLETE spec; the content-source constraint is **RESOLVED** in ADR-0029
  (committed `pixelart_creator/userguide_content/`, NOT `docs/site`).
- Module surface frozen for `interface-contract`; layer placement fixed; constants declared.
- Consumed next by `tasks.md`; the `sdd-analyze` C1 gate follows.
- **STATUS: COMPLETED.**
