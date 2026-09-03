# ADR-0029 — In-app User Guide: committed content source, offline bundling, and three-layer design

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `user-guide` (cross-cutting; `REQ-UG-*`) |
| Supersedes | — |
| Superseded by | — |
| Relates to | spec `specs/user-guide/spec.md` §8 (DEP-2/DEP-3), constitution Article I / VII / XI, S19 (publication hygiene) |

## Context

The `user-guide` spec (19 REQs) specifies an in-app, offline, navigable User Guide reachable from
**Help ▸ User Guide** + **F1**, with a section→topic ToC, in-guide search, a11y + both themes + i18n,
and per-phase extensibility. The spec fixes the observable WHAT and defers the **content-source +
bundling** HOW to this ADR (spec §8, DEP-2/DEP-3; REQ-UG-DATA-002).

**The spec's DEP-2 recommends single-sourcing the guide content from `docs/site`.** This recommendation
**conflicts with the constitution's publication hygiene (S19)**: `docs/**` is **gitignored AND purged
from git history** (`.gitignore` lines 55–60 — `docs/` is intentionally absent from
the repository, present only on the author's local disk). Therefore `docs/site`:

- is **not committed** to the repository,
- is **not present in the CI checkout**,
- is **not present in the distributable** (wheel / installed package).

A guide that reads its shipped content from `docs/site` would render **nothing** for any real user
(the path does not exist in an install) and could not be tested in CI. Per **Article VIII / C1
(constitution supremacy)**, a spec/plan decision conflicting with an article is invalid and the
**artifact is conformed to the constitution** — the gate is not weakened. This ADR resolves the
conflict, then rules the content format, the loader/discovery model, the layer placement, and the
security posture.

## Decision

### 1. The shipped single source is a COMMITTED package-data directory — NOT `docs/site` (resolves DEP-2 vs S19)

The in-app guide's shipped content lives in a **committed, distributable** directory that ships with
the package:

```
pixelart_creator/userguide_content/
  manifest.json                     # the discovery + ordering manifest (the ToC declaration)
  content/<locale>/<topic_id>.md    # per-topic Markdown, one file per topic, per locale
  content/en/canvas-and-view.md
  content/en/colour-hub.md
  ... (one .md per topic; en = DEFAULT_GUIDE_LOCALE)
```

- `pixelart_creator/userguide_content/` is **committed to git** and **shipped in the wheel** as package
  data (a DevOps `pyproject`/`package-data` edit). It is the **SINGLE SHIPPED SOURCE** the
  app bundles, discovers, and renders **fully offline** (REQ-UG-DATA-001, REQ-UG-UI-007). The app has
  **ZERO** runtime or build dependency on the gitignored `docs/site` path — nothing in `logic/`,
  `data/`, `ui/`, or CI ever references `docs/site`.

- **Relationship to the private `docs/site` (resolves the spec's "single-source / no-drift" intent,
  C1-compliant).** `docs/site` (the documentation-owned) remains the **private, public-facing mkdocs HTML site**
  and is a **separate artifact**. Drift is prevented at the **editorial** level, not by a runtime path:
  the documentation authors the guide prose **once** and keeps the two rendering targets — the committed
  `userguide_content/` bundle (in-app) and the private `docs/site` pages (public HTML) — **in sync via
  a local derivation/sync step** run where `docs/site` exists. The spec's REQ-UG-DATA-002
  observable contract ("the guide's content **is** the durable usage content, not a hand-maintained
  divergent fork") is honoured: both targets share the documentation's single editorial source. What changes from
  DEP-2's literal wording is only the **shipped mechanism** — a committed bundle, not a read into a
  private path — which is mandatory under S19. The acceptance scenarios SC-D002-1/-2 hold: each guide
  topic corresponds to the same usage content the documentation publishes; there is no separately-maintained
  divergent copy.

- **This is the "committed shippable mirror" option (spec §8 option (b)), not "authored fresh" (a).**
  The content is not invented independently of the docs; it is the same editorial content, materialised
  as a committed in-app bundle.

### 2. Content format: Markdown, rendered as text/markup (REQ-UG-UI-005, Article VII)

- Per-topic content is **Markdown** (`.md`) — identical in kind to the `docs/site/pages/usage/*.md`
  source, so the editorial source maps 1:1 and diffs cleanly. The `ui/` content pane renders it via
  `QTextBrowser` / `QTextDocument.setMarkdown()` (Qt6) — **rendered as text/markup, NEVER executed**
  (no `eval`/`exec`, REQ-UG-DATA-003). In-guide links are resolved to other bundled topics **within**
  the guide; `QTextBrowser.setOpenExternalLinks(False)` + a link handler that only navigates to known
  topic ids — **no external/network fetch** (REQ-UG-UI-005, REQ-UG-UI-007). The exact widget is an
  the UI implementation HOW detail; `QTextBrowser`+`setMarkdown` is the grounded default.

### 3. Loader + discovery model: manifest-driven, extensible with no code change (REQ-UG-LOGIC-002, Article XI)

- `data/guide_content.py` (**ZERO-Qt**) is the defensive offline reader. It locates the bundle root via
  **`importlib.resources.files("pixelart_creator") / "userguide_content"`** (portable across source
  tree, wheel, and zip; `pathlib`/traversable API, no hardcoded separators —
  `path_portability_check`). It reads `manifest.json` and per-topic Markdown bytes. Missing/malformed
  content → a domain `GuideContentError`, never a crash (REQ-UG-DATA-001).

- **`manifest.json` is the declared ToC (the "manifest / nav order" the spec names).** It lists, in
  order, sections → topics, each with: `id`, `title`, `keywords`/`summary`, and the content-file
  reference. `logic/guide_model.py` builds the section→topic tree from the discovered manifest +
  content set. **Adding a topic/section = adding its `.md` file + a manifest entry — DATA, not code**;
  neither `logic/guide_model.py` nor `ui/user_guide.py` changes (Article XI). Discovery order is the
  manifest order → **deterministic** (same bundle → same ToC). This is how Phases 11–12 add their
  sections later.

### 4. Locale resolution: localised-if-present, else default (REQ-UG-LOGIC-004, CL-3)

- Content resolves by `(topic_id, active_locale)` to `content/<active_locale>/<topic_id>.md` when that
  file exists in the bundle, otherwise falls back to `content/<DEFAULT_GUIDE_LOCALE>/<topic_id>.md`. A
  pure function in `logic/guide_model.py` over the discovered set — localised docs are **added as more
  bundled files** (no code change). Initially only the default locale (`en`) ships; the contract is
  language-agnostic so acceptance depends on no particular translation. The `docs/site` i18n directory
  layout that localised docs derive from remains a documentation/architecture flag (DEP-4) and is **not
  acceptance-changing**.

### 5. Trusted-but-validated load; bundle-root guard (REQ-UG-DATA-003, Article VII)

- Bundled content is trusted, but any **user-influenced** path (a topic id from a ToC click, an
  in-guide link target) is **resolved only through the manifest's known topic ids** and **validated to
  resolve within the bundle root** — a resolved path escaping `userguide_content/` (traversal, `..`,
  absolute) raises `GuideContentError`, never silent filesystem access. Content is passed to the
  renderer **as text/markup only** — never to `eval`/`exec`. A per-file **content-size guard**
  (`GUIDE_MAX_CONTENT_BYTES`) bounds a malformed/oversized resource (Article VII defensive posture,
  the PIO-1 precedent).

### 6. Three-layer placement (Article I; `check_layering`/`check_cycles` must stay exit 0)

| Layer | Module | Responsibility | Qt |
| --- | --- | --- | --- |
| `logic/` | `guide_model.py` **(new)** | section→topic tree, manifest discovery + deterministic ordering, locale resolution, coverage/completeness contract | **zero** |
| `logic/` | `guide_search.py` **(new)** | pure `query(term)` → ordered matching topics over indexed text (title + keywords/summary); case-insensitive; empty term → full set | **zero** |
| `logic/` | `constants.py` **(extend)** | `GUIDE_SEARCH_RESULT_CAP`, `GUIDE_MAX_CONTENT_BYTES`, `GUIDE_MAX_TOC_DEPTH` (Article II) | **zero** |
| `data/` | `guide_content.py` **(new)** | offline bundled-content reader (`importlib.resources`), manifest parse, bundle-root path guard, domain errors, no network | **zero** |
| `ui/` | `user_guide.py` **(new)** | `User_Guide_Dialog`/`_Panel`: ToC tree + `QTextBrowser` content pane + search box; calls the model/reader, renders — implements no domain logic | Qt |
| `ui/` | `main_window.py` **(extend)** | Help ▸ User Guide `QAction` + F1 shortcut opening the viewer | Qt |

- One-way dependency: `ui/user_guide.py → logic/guide_model, logic/guide_search, data/guide_content`;
  `data/guide_content → logic` only if needed (no `logic → data`, no `→ ui`). New content dir carries
  **no Python modules**, so it does not affect layering scans. Baseline is clean (154 modules
  layering-clean, 155 no-cycles, both exit 0, 2026-07-04); every new module must keep it green.

- **Content directory location.** `pixelart_creator/userguide_content/` (a package-data sibling of
  `logic/`/`data/`/`ui/`, inside the importable `pixelart_creator` package) — **not** under `data/`
  (which is a code layer) and **not** a gitignored path. It contains `.md` + `.json` data only.

### 7. Performance / undo posture

- The guide is **read-only** (NFR-5): opening/navigating pushes **no** `QUndoCommand`; `ui/commands.py`
  is untouched. The viewer is **not** on the 16 ms canvas render loop (Article VI), so **no Rendering & Performance perf
  directive is required** (it is document-viewer IO, like the Phase-7/8 batch surfaces).

## Alternatives Considered

- **Ship content by reading `docs/site` at runtime/build (spec DEP-2 literal).** **Rejected** — violates
  S19 (docs/** gitignored + purged; absent from install and CI). This is the core conflict this ADR
  resolves via a committed bundle (Article VIII / C1).
- **Author the in-app content fresh, independent of the docs (spec §8 option (a)).** Rejected — would
  create exactly the divergent fork REQ-UG-DATA-002 forbids; option (b) (committed mirror sharing
  the documentation's editorial source) preserves no-drift.
- **Bundle the built HTML from `docs/site/_build`.** Rejected — the built site carries Bootstrap/JS/lunr
  assets and a full-page chrome unsuited to an embedded `QTextBrowser`; Markdown source pages are the
  clean, small, diffable unit and match the editorial source 1:1.
- **Content as a Qt resource (`.qrc`/`rcc`).** Deferred as a UI implementation/DevOps packaging refinement behind
  the same reader seam; `importlib.resources` over package data is the portable, zero-Qt default that
  keeps the reader in `data/` (Article I).
- **Full-text search index now.** Deferred (CL-2) — the observable "search finds a topic" contract is
  title + keywords/summary; the `docs/site` build already proves a lunr full-text index is feasible as a
  later refinement behind `logic/guide_search.query`.

## Consequences

**Positive.** The guide ships and renders offline from a committed, distributable bundle with no
dependency on any private path; it is fully CI-testable (fixture bundles + the real bundle); layer
purity is preserved (model/search/reader zero-Qt, viewer the only Qt surface); content grows per-phase
by adding data files (Article XI); content is rendered as text and never executed, with a bundle-root
guard (Article VII); no-drift is preserved editorially through the documentation's single authoring source.

**Negative / risk.** No-drift becomes an **authoring discipline** (the documentation's sync step run where
`docs/site` exists), **not** a CI gate against `docs/site` — because CI cannot see the private path. Any
CI drift check must compare against the **committed** bundle, not `docs/site`. The committed content
duplicates prose on disk (in-app bundle + private site) — accepted, since S19 makes a shared shipped
path impossible. The documentation must **author committed topics for areas `docs/site` currently lacks as
dedicated pages** (canvas & view, colour hub, selection/transform, app-wide basics) to satisfy the
coverage contract (REQ-UG-LOGIC-005) — a real authoring scope item.

## Grounding

- Spec `specs/user-guide/spec.md` §1, §4 (REQ-UG-LOGIC-001..005, REQ-UG-DATA-001..003,
  REQ-UG-UI-001..011), §7 (DEP-1..5), §8 (DEP-2/DEP-3), §10 (CL-1..6), §11 (Gherkin);
  `traceability.md` (19 REQ, 0 uncovered).
- Constitution Article I (three-layer purity), II (constants), V (a11y/i18n/themes), VII (offline, no
  exec, path validation, defensive load), VIII/C1 (supremacy — plan conformed over spec DEP-2), X (REQ
  scheme), XI (extensibility). **S19** publication hygiene (`.gitignore` lines 55–60 — `docs/`
  gitignored and purged).
- Shipped tree: `pixelart_creator/{logic,data,ui}/`; `docs/site/pages/usage/*.md` +
  `docs/site/mkdocs.yml` nav (12 usage pages incl. `cloud.md` + `collaboration.md` already authored);
  `check_layering`/`check_cycles` baseline clean. ADR-0025 (sidecar-vs-embedded precedent),
  ADR-0001 (module-local vocabulary), ADR-0020/0022 (CLI-under-`data/` layering-scan precedent).

## Amendment (2026-08-16) — the S19 premise is stale; the decision stands on the wheel-exclusion ground

*Immutable-append. The original Context, Decision, Alternatives and Consequences above are retained
unchanged as the record of the 2026-07-04 reasoning; this note re-states the **justification** whose
factual premise has since changed. The decision itself is **not superseded** — it is re-grounded.*

**Provenance.** The 2026-08-16 spec-verification audit `audit-spec-user-guide-20260816.md` (F-5) —
consolidated as CF-131, remediation item R-46; the measured divergence in §c is CF-41 / D-23.

### a. What is no longer true

The Context asserts that `docs/**` is "**gitignored AND purged from git history**" and that `docs/site`
is consequently "**not committed** to the repository" and "**not present in the CI checkout**". **That
premise no longer holds.** As of 2026-08-16:

- `.gitignore` now reads `docs/*` with **`!docs/adr/` and `!docs/site/` re-included**; `git ls-files
  docs/site` returns **17 tracked files**.
- CI **builds** the site: `.github/workflows/ci.yml` runs `mkdocs build -f docs/site/mkdocs.yml
  --strict`, so `docs/site` **is** present in the CI checkout.

Two of the Context's three bullets are therefore **factually superseded**; the third is not, and it is
the load-bearing one.

### b. The ground that survives — the wheel cannot carry `docs/`

The DECISION — the shipped runtime source is the **committed `pixelart_creator/userguide_content/`
bundle**, never a read into `docs/site` — stands on an **independent and still-true** ground: the
distributable does not contain `docs/`. `pyproject.toml`'s
`[tool.setuptools.packages.find] exclude = ["tests*", "scripts*", "docs*", "sync_backend*",
"web_viewer*"]` drops `docs*` from the wheel. A guide reading `docs/site` at runtime would still
render **nothing** in a real install — the original third bullet, "**not present in the
distributable**", is unchanged and is by itself sufficient (REQ-UG-DATA-001, REQ-UG-UI-007, offline
first). Article I placement (§6), the manifest-driven loader (§3), locale fallback (§4) and the
bundle-root guard (§5) are untouched.

**Reader guidance.** Wherever the Context, the Alternatives ("violates S19 — `docs/**` gitignored +
purged") or the Consequences ("because CI cannot see the private path") rest on `docs/site` being
*absent from the repository or from CI*, read instead: `docs/site` is **tracked and CI-visible**, but
is **excluded from the wheel**, which is why the shipped source must be the committed bundle. One
consequence flips sign: a CI drift check against `docs/site` is **now technically possible**, so the
no-drift item below is actionable rather than impossible.

### c. No-drift is an OPEN item (D-23), not a resolved property

The original text records no-drift as "preserved editorially through the documentation's single authoring source"
and reads SC-D002-1/-2 as holding. **Measured on 2026-08-16, that is not true at the byte level**: the
committed bundle carries **19 topics** against **15** `docs/site` usage pages; the two sets share
**8 stems**, of which **0 are byte-identical**; **11** are bundle-only and **7** docs-only. There is
**no sync script and no CI gate**, `data/guide_content.py` has zero reference to `docs/site`, and
SC-D002-1's literal claim has no test — so the property is **unverifiable from this repository**.

This is recorded here as the **open item D-23** — author a drift gate or a sync script, or amend
REQ-UG-DATA-002 to the editorial-level promise this ADR actually makes — and explicitly **not** as a
resolved consequence. The runtime source is unaffected either way: the committed
`pixelart_creator/userguide_content/` bundle remains the single shipped source.
