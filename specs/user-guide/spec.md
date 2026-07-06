# Specification — In-App User Guide (cross-cutting)

| Field | Value |
| --- | --- |
| Feature | `user-guide` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VII, VIII, X, **XI**) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no in-app guide viewer, no guide content model/loader, and no Help ▸ User Guide menu entry exist yet. The durable user docs under `docs/site/pages/` (mkdocs source) and the built `docs/site/_build/` HTML site are **already authored/shipped** (Phases 1–9 usage pages) and are **REUSED as the single source of truth**, not re-authored. This spec defines the WHAT/WHY of the in-app guide that surfaces that documentation. |
| REQ-ID range | `REQ-UG-LOGIC-001..005`, `REQ-UG-DATA-001..003`, `REQ-UG-UI-001..011` (prefix `REQ-UG-*`, assigned for this cross-cutting feature — it is not a single roadmap phase; see PREFIX-NOTE §7 / DEP-5) |
| Layer scope | `pixelart_creator/logic/` (NEW: guide **content model** — section→topic tree, discovery/extensibility, search/filter query, locale resolution, coverage contract — **zero Qt, pure, unit-testable**) + `pixelart_creator/data/` (NEW: defensive **offline bundled-content reader** single-sourced from `docs/site`, portable paths, no network, no `eval`/`exec` — **zero Qt**) + `pixelart_creator/ui/` (NEW: Help ▸ User Guide menu entry + F1 shortcut, the navigable guide window/panel — ToC tree, content pane, search box — rendering bundled content as text/markup — **the only Qt surface**) |
| Binds to (upstream, **shipped** — REUSED) | `docs/site/pages/*.md` + `docs/site/mkdocs.yml` nav (the **DOC-SITE** primitive: the durable, human-authored usage documentation this guide single-sources so the in-app guide **cannot drift** from the real docs); the existing main-window menu bar (the surface the Help menu attaches to); the shipped light/dark QSS theme roles and the `tr()`/`QEvent.LanguageChange` i18n chrome pattern |
| Depends on (external) | **The Researcher** (optional, HOW-grounding only) — in-app documentation-rendering approach (e.g. `QTextBrowser` markup rendering, offline resource bundling) is an AGT-01/AGT-08 plan decision; the spec fixes only the observable WHAT and does **not** block on research |
| Sequencing | Authored **now**; orchestrator intent is to **BUILD after Phase 10 ships** so the guide covers cloud/collaboration content (§7 DEP-1). This is a **dependency/sequencing note, not a blocker** to authoring the spec. |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

PixelArt Creator has grown into a broad platform — an 8K canvas & view, a right-click colour hub,
a non-destructive layer system, selection/transform, an animation timeline, a tileset/tilemap
editor, an export & pipeline stage, automation/scripting, visual aids (grids, guides, real-size
preview, multi-view, reference board, timelapse), and (Phase 10) cloud & collaboration. Durable
usage documentation for these workflows already exists under `docs/site/` (the mkdocs source pages +
built HTML site). What is missing is a way for a user **inside the application** to open a
**comprehensive, well-organised User Guide** — reachable from the **main menu** (**Help ▸ User
Guide**, with an **F1** shortcut) — that presents that documentation **structured by window and
functionality**, lets them **navigate a table-of-contents tree** to any topic, **search/filter** to
find a topic, and reads it **fully offline** (no network).

The guide must **single-source its content from the existing durable docs under `docs/site`** so the
in-app guide **cannot drift** from the real documentation: the content is **bundled as offline
package data** and rendered in-app. This yields two purity boundaries the constitution requires
(Article I): the **content model + loader** — building the section→topic tree, discovering
available content, answering a search query, resolving a topic's content for the active locale — is
**pure `logic/` + `data/`, zero Qt, unit-testable**; the **viewer** — the menu action, the guide
window/panel, the ToC tree widget, the content pane, and the search box — lives in `ui/` (the only
layer that imports Qt). Bundled content is **trusted**, but content is **rendered as text/markup and
never executed** (no `eval`/`exec`), and any content path that is user-influenced (e.g. a topic id
resolved to a bundled file) is **validated** to stay within the bundle root (Article VII).

The guide is **extensible by construction** (Article XI): its section/topic structure **grows
per-phase** — each phase/feature adds its guide section by **adding a bundled doc that the content
model discovers**, with **no code change** to the viewer or model. Phases 11–12 will add sections
this way later.

This document specifies **WHAT** the in-app guide must do and **WHY**, technology-neutral at the
requirement level. The **HOW** — the concrete markup-rendering widget (e.g. `QTextBrowser`), the
exact bundling/packaging of `docs/site` content as offline resource data, the derivation pipeline
from mkdocs source to the bundled set, whether the search index is title/keyword-level or full-text,
and the `docs/site` i18n layout for localised content — belongs to `sdd-plan` (AGT-01) and the
documentation owner (AGT-08), grounded where useful by The Researcher. The **source-of-truth +
bundling** decision is explicitly **flagged for AGT-01 / AGT-08 coordination** (§7 DEP-2, §8).

### NEW vs REUSED

| Capability | Status | Evidence |
| --- | --- | --- |
| Durable usage docs (per-window/functionality) | **REUSED** (single source of truth) | `docs/site/pages/*.md` (layers, blend-modes, multi-canvas, floating-selection, drag-drop-import, animation, tilemap, export, automation, visual-aids) + `docs/site/mkdocs.yml` nav |
| Main-window menu bar (Help menu host) | **REUSED** | shipped `ui/main_window.py` menu bar |
| Light/dark QSS theme roles + `tr()`/`LanguageChange` chrome pattern | **REUSED** | shipped theming + i18n chrome conventions (Article V) |
| Guide content model (section→topic tree, discovery, search, locale resolution, coverage) | **NEW** | no in-app guide model exists |
| Offline bundled-content reader (single-sourced from `docs/site`) | **NEW** | no in-app content bundle/loader exists |
| Help ▸ User Guide menu entry + F1 shortcut | **NEW** | no Help ▸ User Guide action exists |
| Guide viewer window/panel (ToC tree + content pane + search box) | **NEW** | no in-app documentation viewer exists |

## 2. Scope

**In scope (WHAT) — logic (`pixelart_creator/logic/`, Qt-free, pure, unit-testable):**

- A **guide content model** — an **ordered tree** of **sections → topics** organised **by window /
  functionality** (canvas & view, colour hub, layers, selection/transform, animation timeline,
  tileset/tilemap editor, export & pipeline, automation/scripting, visual aids, cloud &
  collaboration, asset library, app-wide basics). Each topic exposes an id, a title, a content reference, and
  searchable metadata (keywords/summary). Pure, deterministic. *(REQ-UG-LOGIC-001.)*
- **Content discovery / extensibility**: the model **discovers** the available guide content from the
  bundled doc set (single-sourced from `docs/site`) and derives the ToC from the discovered set plus
  a **declared ordering** (a manifest / nav order), so **adding a new bundled doc adds a topic/section
  with no code change** (Article XI). Ordering is deterministic. *(REQ-UG-LOGIC-002.)*
- A **search/filter query**: a **pure** function `query(term)` → an **ordered list of matching
  topics**, matching over each topic's indexed text (title + keywords/summary; full-body indexing is
  a HOW refinement, CL-2). Case-insensitive, deterministic. *(REQ-UG-LOGIC-003.)*
- **Locale resolution**: resolve a topic's content by `(topic, active_locale)`, **falling back to the
  default locale** when no localised doc exists for that topic — a pure function, so localised
  content can be added later (as bundled docs) without code change. *(REQ-UG-LOGIC-004; CL-3.)*
- A **coverage / completeness contract**: the model guarantees a section/topic exists for **every**
  major functionality area enumerated above (**including cloud & collaboration**: connect/manage,
  shared projects, comments, presence, branching), so "content present for each area" is a checkable
  property of the discovered set, not an assumption. *(REQ-UG-LOGIC-005.)*

**In scope (WHAT) — data (`pixelart_creator/data/`, Qt-free):**

- A **bundled offline content reader**: the guide content is **bundled as offline package data**
  (single-sourced from `docs/site`) and read via a **defensive** reader — **no network access, ever**
  (fully offline). Paths are portable (`pathlib`); missing/malformed content surfaces a domain error,
  never a crash. *(REQ-UG-DATA-001.)*
- **Single-source-of-truth binding**: the bundled content is **derived from `docs/site`** (the durable
  user docs), so the in-app guide **cannot drift** from the real documentation. The **derivation /
  bundling mechanism** is a HOW decision flagged for AGT-01 / AGT-08 (§8); the WHAT — that the guide's
  content **is** the `docs/site` content — is fixed here. *(REQ-UG-DATA-002.)*
- **Trusted-but-validated load**: bundled content is trusted, but if any content path is
  **user-influenced** (e.g. a topic id or an in-guide link resolved to a bundled file), it is
  **validated to remain within the bundle root** (no path traversal), and content is **rendered as
  text/markup, never executed** (no `eval`/`exec`). *(REQ-UG-DATA-003; Article VII.)*

**In scope (WHAT) — UI (`pixelart_creator/ui/`, the only Qt):**

- A **Help ▸ User Guide** main-menu entry that **opens the guide** *(REQ-UG-UI-001)*, plus a
  **sensible shortcut (F1)** that opens it *(REQ-UG-UI-002; CL-4)*.
- A dedicated, **navigable guide window/panel** presenting a **ToC navigation tree** (organised by
  window/functionality, from the model) **and** a content pane *(REQ-UG-UI-003)*.
- **ToC navigation**: selecting a ToC entry **shows that topic's content page** *(REQ-UG-UI-004)*.
- **Content rendering**: renders per-topic content **as text/markup** (e.g. `QTextBrowser`), **never
  executing it**; in-guide links navigate **within** the guide; **no external network fetch**
  *(REQ-UG-UI-005)*.
- **In-guide search/filter**: a search box that **finds/filters matching topics** (via
  REQ-UG-LOGIC-003) and lets the user **jump to a result** *(REQ-UG-UI-006)*.
- **Offline / no-network**: the viewer renders entirely from **bundled** content and makes **no
  network request** — it works with no connectivity *(REQ-UG-UI-007)*.
- **Cloud & collaboration coverage present**: the ToC/content **includes the cloud & collaboration
  area** (connect/manage, shared projects, comments, presence, branching) — authored after Phase 10
  ships (§7 DEP-1) *(REQ-UG-UI-008)*.
- **a11y / both themes / i18n** for the guide surface (REQ-UG-UI-009/-010/-011).

**Out of scope (this feature):** see §6. Notably: the **markup-rendering widget** choice, the
**bundling/packaging pipeline** from `docs/site` → offline resource data, whether search is
**full-text vs title/keyword** indexed (CL-2 default fixes the observable contract), the **`docs/site`
i18n directory layout** for localised content (CL-3 / DEP-4), and **authoring** localised content —
all HOW/coordination for AGT-01 / AGT-08. Also out: **editing** the documentation from inside the app
(the guide is **read-only**); an **online/hosted** help centre or telemetry; context-sensitive
"help for the current widget" deep-linking (a possible later enhancement); re-authoring the
`docs/site` content. No plan/tasks/code (AGT-01/03/05), no tests (AGT-04/06), no new technology (S8).

## 3. Story map & user stories

Backbone activity → stories, each tagged with a kebab-case feature label. Taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Any user / open-guide).** As a user, I want to open a complete **User Guide from the main
  menu** (Help ▸ User Guide) so I can learn any part of the platform without leaving the app. →
  REQ-UG-UI-001 · `guide-open` · X
- **US-2 (Keyboard user / F1).** As a user, I want **F1 to open the guide** so help is one keystroke
  away. → REQ-UG-UI-002 · `guide-open` · X
- **US-3 (Any user / structured-toc).** As a user, I want the guide **organised by window and
  functionality** in a navigable **table-of-contents tree**, so I can find the area I care about. →
  REQ-UG-LOGIC-001, REQ-UG-UI-003, -004 · `guide-toc` · X
- **US-4 (Any user / read-topic).** As a user, I want to **read a topic's page** rendered cleanly
  in-app, so I get the documentation without a browser. → REQ-UG-UI-005 · `guide-content` · X
- **US-5 (Any user / search).** As a user, I want to **search/filter** the guide and **jump to a
  matching topic**, so I can find an answer fast. → REQ-UG-LOGIC-003, REQ-UG-UI-006 · `guide-search` · X
- **US-6 (Any user / offline).** As a user with **no internet**, I want the whole guide to work
  **fully offline** from bundled content. → REQ-UG-DATA-001, REQ-UG-UI-007 · `guide-offline` · X
- **US-7 (Any user / no-drift).** As a user, I want the in-app guide to **match the real
  documentation** (never a stale fork), because it **single-sources** `docs/site`. →
  REQ-UG-DATA-002 · `guide-single-source` · X
- **US-8 (Cloud user / cloud-collab-coverage).** As a cloud/collaboration user, I want the guide to
  cover **cloud establishment/management and shared-projects management** (connect/manage, shared
  projects, comments, presence, branching), so Phase-10 features are documented in-app. →
  REQ-UG-LOGIC-005, REQ-UG-UI-008 · `guide-coverage` · X
- **US-9 (Maintainer / extensible).** As a maintainer, I want each new phase/feature to add its guide
  section by **adding a bundled doc the model discovers**, with **no code change**, so the guide grows
  with the platform (Phases 11–12 later). → REQ-UG-LOGIC-002 · `guide-extensible` · X
- **US-10 (Non-English user / localisable).** As a non-English user, I want the guide **chrome
  translated** and the **content localisable** (falling back to the default language when a localised
  page is absent). → REQ-UG-LOGIC-004, REQ-UG-UI-011 · `i18n` · X
- **US-11 (Keyboard / screen-reader user / a11y).** As a keyboard or screen-reader user, I want the
  ToC and content **keyboard-navigable** with **accessible labels** and a **logical focus order**. →
  REQ-UG-UI-009 · `a11y` · X
- **US-12 (Dark-mode user / theming).** As a dark-mode user, I want the guide to render correctly and
  legibly in **both light and dark themes**. → REQ-UG-UI-010 · `theming` · X
- **US-13 (Security-conscious user / safe-content).** As a user, I want guide content **rendered as
  text, never executed**, and content paths validated, so opening the guide is safe. →
  REQ-UG-DATA-003, REQ-UG-UI-005 · `guide-safe` · X

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Scope |
| --- | --- | --- |
| `guide-open` | Opening the guide from the main menu (Help ▸ User Guide) and via F1. | cross-cutting |
| `guide-toc` | Section→topic ToC tree organised by window/functionality; ToC navigation. | cross-cutting |
| `guide-content` | Per-topic content pages rendered in-app as text/markup. | cross-cutting |
| `guide-search` | In-guide search/filter that finds/jumps to a matching topic. | cross-cutting |
| `guide-offline` | Fully offline: bundled content, no network request. | cross-cutting |
| `guide-single-source` | Content single-sources `docs/site`; the in-app guide cannot drift. | cross-cutting |
| `guide-coverage` | A topic exists for every functionality area, incl. cloud & collaboration. | cross-cutting |
| `guide-extensible` | New content = new bundled doc, discovered by the model; no code change. | cross-cutting |
| `guide-safe` | Content rendered as text, never executed; content paths validated. | cross-cutting |
| `i18n` / `a11y` / `theming` | Translatable chrome + localisable content; keyboard/focus; both themes. | cross-cutting |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id` and/or a governing article and the user request.
Requirements are technology-neutral WHAT statements; a binding to shipped content (`docs/site`) is a
**constraint**, not a HOW decision. Layer, owner agent, and acceptance scenarios are in
`traceability.md`.

### 4.1 Logic layer (`REQ-UG-LOGIC-001..005`) — `pixelart_creator/logic/` (Qt-free, pure, NEW)

#### REQ-UG-LOGIC-001 — Guide content model: an ordered section→topic tree by window/functionality
`traces:` S6 (extensibility), Article I, Article XI; user request (structured ToC)
The guide is modelled as a **pure, deterministic, ordered tree** of **sections → topics** organised
**by window / functionality**. Each **topic** exposes at least an **id**, a **title**, a **content
reference** (to its bundled source), and **searchable metadata** (keywords/summary). The section set
covers: **canvas & view**, **colour hub**, **layers**, **selection/transform**, **animation
timeline**, **tileset/tilemap editor**, **export & pipeline**, **automation/scripting**, **visual
aids** (grids/guides/preview/multi-view/timelapse/reference board), **cloud & collaboration**
(connect/manage, shared projects, comments, presence, branching), **asset library** (asset catalogue,
tagging, search — Phase 11), and **app-wide basics**. The model
imports **zero Qt** and is exercised directly by unit tests. It does not render — it only structures.

#### REQ-UG-LOGIC-002 — Content discovery & per-phase extensibility (no code change to add content)
`traces:` S6, Article XI; user request (extensibility / Phases 11–12)
The model **discovers** the available guide content from the bundled doc set (single-sourced from
`docs/site`) and derives the ToC from the discovered set plus a **declared ordering** (a manifest /
nav order). **Adding a new bundled doc adds a topic/section — with no change to the model or viewer
code** (Article XI). Discovery ordering is **deterministic** (same bundle → same ToC order). This is
the mechanism by which Phases 11–12 (and any future feature) add their guide section.

#### REQ-UG-LOGIC-003 — Search/filter is a pure query over indexed topic text
`traces:` S6; user request (in-guide search/filter)
`query(term)` is a **pure, deterministic, case-insensitive** function returning an **ordered list of
matching topics** — matched over each topic's **indexed text** (at least its title + keywords/summary;
whether the index also covers full body text is a HOW refinement, **CL-2**). An empty/whitespace term
yields a defined result (the full topic set or an empty result — fixed as CL-2). No Qt; unit-testable
independently of the viewer. This is the "search finds a topic" contract (REQ-UG-UI-006).

#### REQ-UG-LOGIC-004 — Locale resolution with fallback to the default locale
`traces:` Article V §2, Article XI; user request (content localisable)
Resolving a topic's content is a **pure** function of `(topic, active_locale)`: it returns the
**localised** content when a localised doc exists for that topic and locale, and otherwise **falls
back to the default locale**. Localised content is added as **additional bundled docs discovered by
the model** (REQ-UG-LOGIC-002) — **no code change**. The **`docs/site` i18n layout** that localised
docs derive from is flagged for AGT-08 / AGT-01 (**CL-3 / DEP-4**); the resolution contract (localised
if present, else default) is fixed here and is language-agnostic, so acceptance does not depend on any
particular translated content existing yet.

#### REQ-UG-LOGIC-005 — Coverage/completeness contract for every functionality area
`traces:` S6, Article X; user request (cover the ENTIRE platform incl. cloud/collab)
The model guarantees a section/topic exists for **every** major functionality area (the enumerated set
in REQ-UG-LOGIC-001), **including cloud & collaboration** — connect/manage, shared projects, comments,
presence, branching — and, from **Phase 11**, the **asset library** (asset catalogue, tagging, search).
The enumerated set grows per-phase (Article XI); this requirement's intent is unchanged — the guide MUST
cover every platform area. "Content present for each area" is therefore a **checkable property of the
discovered content set**, not an assumption. A missing required area is a detectable gap (feeds the
acceptance in REQ-UG-UI-008 and the AGT-06 checklist). *(Authoring the cloud/collab content is gated on
Phase 10 shipping — DEP-1 — but the required-area contract is fixed now.)*

### 4.2 Data layer (`REQ-UG-DATA-001..003`) — `pixelart_creator/data/` (Qt-free, NEW)

#### REQ-UG-DATA-001 — Offline bundled-content reader (no network, ever)
`traces:` S7, Article VII; user request (offline/bundled)
Guide content is **bundled as offline package data** and read by a **defensive** reader that makes
**no network access whatsoever**. Paths are constructed **portably** (`pathlib` / no hardcoded
separators, `path_portability_check`). A missing or malformed content resource surfaces a **domain
exception** (caught and shown by REQ-UG-UI-005/-007), never a crash. Deterministic; Qt-free.

#### REQ-UG-DATA-002 — Single source of truth: content derives from `docs/site` (no drift)
`traces:` S7, Article XI; user request (single-source docs/site so the guide cannot drift)
The bundled guide content is **derived from the durable user docs under `docs/site`** — the in-app
guide's content **is** the `docs/site` content, so it **cannot drift** from the real documentation.
The **derivation / bundling mechanism** (build-step packaging of the mkdocs source pages into offline
resource data) is a HOW decision flagged for **AGT-01 / AGT-08** (§8, DEP-2/DEP-3); this REQ fixes the
**contract** — the guide is a single-sourced view of `docs/site`, not a hand-maintained fork. Qt-free.

#### REQ-UG-DATA-003 — Trusted-but-validated content load; content is text, never executed
`traces:` S7, Article VII; user request (Article VII: render as text/markup, never execute)
Bundled content is **trusted**, but: (a) content is **rendered as text/markup and never executed** —
it is **never** passed to `eval`/`exec`; (b) if any content path is **user-influenced** (e.g. a topic
id or an in-guide link resolved to a bundled file), it is **validated to remain within the bundle
root** (no path traversal / no escape to arbitrary filesystem locations). Violations raise a domain
exception, not silent access. Deterministic; Qt-free.

### 4.3 UI layer (`REQ-UG-UI-001..011`) — `pixelart_creator/ui/` (menu + viewer, NEW)

#### REQ-UG-UI-001 — Help ▸ User Guide main-menu entry opens the guide
`traces:` S5; user request (main-menu integration)
The main menu bar exposes a **Help ▸ User Guide** action; triggering it **opens the guide**
window/panel. The action label is `tr()`-wrapped (REQ-UG-UI-011). Attaches to the shipped menu bar.

#### REQ-UG-UI-002 — F1 shortcut opens the guide
`traces:` S5, Article V §1; user request (sensible shortcut, e.g. F1)
Pressing **F1** opens the guide (the same surface as Help ▸ User Guide). The shortcut is discoverable
(shown on the menu action). *(CL-4: F1 is the confirmed default shortcut.)*

#### REQ-UG-UI-003 — Navigable guide window/panel with a ToC tree and a content pane
`traces:` S5; user request (dedicated navigable viewer)
The guide is a **dedicated, navigable** window/panel presenting a **table-of-contents navigation
tree** (organised by window/functionality, built from REQ-UG-LOGIC-001) **and** a **content pane**.
Whether it is a separate window or a dockable panel is a HOW decision (AGT-01/AGT-05); the WHAT is a
navigable ToC-tree + content surface.

#### REQ-UG-UI-004 — ToC navigation shows the selected topic's page
`traces:` S5; user request (navigate ToC to a topic)
Selecting a ToC entry **displays that topic's content page** in the content pane. The tree reflects
the model's section/topic order (REQ-UG-LOGIC-002). The viewer **calls the model** for structure and
content — it does not hard-code the ToC (Article I).

#### REQ-UG-UI-005 — Content rendered as text/markup, in-guide links, no execution, no network
`traces:` S5, Article VII; user request (render via e.g. QTextBrowser; never execute)
Per-topic content is **rendered as text/markup** (e.g. `QTextBrowser`) and is **never executed**;
in-guide links navigate **within** the guide (to another topic/anchor); the viewer performs **no
external network fetch** to render content. A content load error (REQ-UG-DATA-001) surfaces a
user-facing message, not a crash.

#### REQ-UG-UI-006 — In-guide search/filter finds and jumps to a topic
`traces:` S5; user request (in-guide search/filter)
The guide provides a **search/filter box**: entering a term shows the **matching topics** (via the
pure query REQ-UG-LOGIC-003) and lets the user **jump to a result** (which navigates the ToC + content
pane to that topic). The viewer **renders results and calls the model's query** — it does not
implement the matching itself (Article I).

#### REQ-UG-UI-007 — Fully offline: renders from bundled content, no network request
`traces:` S7, Article VII; user request (fully offline / no network access)
The guide renders **entirely from bundled content** (REQ-UG-DATA-001) and issues **no network
request** — it works with **no connectivity**. There is **no** online/hosted-help fallback.

#### REQ-UG-UI-008 — Cloud & collaboration content is present in the guide
`traces:` S6, Article X; user request (must cover Phase-10 cloud/collab)
The guide's ToC/content **includes the cloud & collaboration area** — cloud establishment/management
(connect/manage), shared-projects management, comments, presence, and branching — as a discoverable
section (REQ-UG-LOGIC-002/-005). *(Authoring this content is gated on Phase 10 shipping — DEP-1; the
required-section contract and its acceptance are fixed now.)*

#### REQ-UG-UI-009 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
The guide surface is **keyboard-navigable**: the ToC tree is reachable and operable by keyboard, the
search box and content pane are in a **logical tab/focus order**, and focus is **visibly indicated**.
Interactive controls (ToC entries, search box, content pane, navigation controls) expose **accessible
names** and, where non-obvious, **accessible descriptions**. Verified by AGT-06 (`a11y-audit`).

#### REQ-UG-UI-010 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The guide window, ToC tree, content pane, and search box render **correctly and legibly in both light
and dark themes**; colours are defined once by role (never hard-coded per widget), including the
rendered-content text/background contrast. Both themes are test-verified (AGT-06 pytest-qt).

#### REQ-UG-UI-011 — Chrome strings translatable; content localisable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible **chrome** string the guide adds (menu action, window title, ToC/section labels
that are UI chrome, search placeholder, navigation controls, error messages) is wrapped in
`tr()`/`translate()` and re-set on `QEvent.LanguageChange`; none is a bare literal. The **guide
content** is **localisable** via locale resolution (REQ-UG-LOGIC-004), falling back to the default
locale. Chrome wrapping verified by `string_audit_check` (AGT-07); an unwrapped string is a blocking
finding. *(How localised content maps to a `docs/site` i18n layout is flagged — CL-3 / DEP-4.)*

## 5. Non-functional requirements (constitution-tied)

- **NFR-1 (Purity, Article I / S11).** The content model (tree, discovery, search query, locale
  resolution, coverage) imports **zero Qt** and lives in `logic/`; the bundled-content reader imports
  **zero Qt** and lives in `data/`; the menu action, viewer window, ToC tree, content pane, and search
  box live in `ui/`. Enforced by `check_layering` / `check_cycles`.
- **NFR-2 (Determinism).** The ToC order, search results, and locale resolution are **deterministic**
  functions of the bundled content + inputs (test-asserted).
- **NFR-3 (Offline / no network, Article VII).** No part of the guide performs a network request; all
  content is bundled and read from local package data.
- **NFR-4 (Safe content, Article VII).** Content is rendered as text/markup and **never** executed;
  user-influenced content paths are validated within the bundle root; malformed/missing content raises
  a domain exception surfaced as a user-facing message, never a crash.
- **NFR-5 (Read-only).** The guide is **read-only**; opening or navigating it never mutates the
  document, the app state, or the `docs/site` source.
- **NFR-6 (Numerics, Article II / S12).** Any numeric tuning value the guide introduces (e.g. a
  search-result cap or ToC max depth, if any) lives **only** in `logic/constants.py`; no magic numbers.
  If none is needed, no constant is added (§9).
- **NFR-7 (Coverage, Article IV / S13).** ≥90 % line / ≥80 % branch per package; the content model +
  reader via pytest (+ Hypothesis for discovery/search/locale invariants); the menu/viewer/search UI
  via pytest-qt in **both themes**, headless (`QT_QPA_PLATFORM=offscreen`).
- **NFR-8 (a11y + i18n + both themes, Article V).** Per REQ-UG-UI-009/-010/-011.
- **NFR-9 (Extensibility, Article XI).** Adding a bundled doc adds guide content with **no code
  change** (REQ-UG-LOGIC-002) — verified by a discovery test over a fixture bundle.

## 6. Non-goals (explicit; deferred)

- The **markup-rendering widget** choice (`QTextBrowser` vs alternative) and any rich-content
  specifics — AGT-01/AGT-05 (grounded by The Researcher if needed).
- The **bundling/packaging pipeline** from `docs/site` (mkdocs source) → offline resource data, and
  where it runs (build step / packaging) — **AGT-01 / AGT-08 coordination** (§8, DEP-2/DEP-3).
- Whether the search index is **full-text (page body)** or **title/keyword** level — the observable
  "search finds a topic" contract is fixed (REQ-UG-LOGIC-003 / CL-2); the index depth is HOW (AGT-01).
- The **`docs/site` i18n directory layout** for localised content, and **authoring** localised content
  — AGT-08 / AGT-01 (CL-3 / DEP-4). The locale-resolution contract (localised-if-present-else-default)
  is fixed (REQ-UG-LOGIC-004).
- **Editing** the documentation from inside the app — the guide is **read-only** (NFR-5).
- An **online / hosted** help centre, in-app analytics/telemetry of guide usage, or "check for updated
  docs online" — out of scope (fully offline, NFR-3).
- **Context-sensitive help** (e.g. "help for the widget under the cursor" / deep-linking from a
  specific control) — a possible later enhancement, not this feature.
- **Re-authoring or restructuring** the `docs/site` content — the guide single-sources it as-is
  (REQ-UG-DATA-002); content edits are AGT-08's docs workflow.
- No plan/tasks (AGT-01), no logic/UI/data/test code (AGT-03/05/04/06), no new technology (S8).

## 7. Dependencies & assumptions

- **Upstream single source is shipped and REUSED.** `docs/site/pages/*.md` + `docs/site/mkdocs.yml`
  (the DOC-SITE primitive) are the durable, human-authored usage docs. The guide **single-sources**
  them (REQ-UG-DATA-002) and must **not** re-author or fork them. The shipped menu bar hosts the Help
  menu; the shipped QSS theme roles + `tr()`/`LanguageChange` chrome pattern are reused.
- **DEP-1 (Sequencing — BUILD after Phase 10).** Orchestrator intent: **author now, build after Phase
  10 ships** so the guide's **cloud & collaboration** content (connect/manage, shared projects,
  comments, presence, branching) can be single-sourced from the Phase-10 docs that AGT-08 will add
  under `docs/site`. This is a **dependency/sequencing note, not a blocker** to this spec. The
  cloud/collab **required-section contract** (REQ-UG-LOGIC-005, REQ-UG-UI-008) is fixed now; its
  **content** appears once the Phase-10 `docs/site` pages exist. **This feature does not touch any
  `specs/phase-10-*` file** (a separate AGT-02 instance owns those concurrently).
- **DEP-2 / DEP-3 — SINGLE-SOURCE + BUNDLING COORDINATION (flagged for AGT-01 / AGT-08).** See §8.
- **DEP-4 (AGT-08 / AGT-01 — localised-content mapping).** How localised guide content maps to a
  `docs/site` i18n layout (directory-per-locale, front-matter, or a translation pipeline) is a
  **documentation-structure decision for AGT-08**, consumed by AGT-01 at plan time. The
  locale-resolution contract (REQ-UG-LOGIC-004) is fixed regardless. **Not acceptance-changing** (see
  CL-3).
- **DEP-5 (orchestrator / AGT-01 — REQ prefix).** This is a **cross-cutting** feature, not one roadmap
  phase, so it uses a **`REQ-UG-*`** prefix (with `-LOGIC-`/`-DATA-`/`-UI-` layer segments) rather than
  `REQ-P<n>-*`. This mirrors the constitution's REQ scheme (Article X) with a feature key in place of a
  phase number. **Flagged to confirm** the prefix is acceptable for `traceability-matrix` / `sdd-analyze`
  (PREFIX-NOTE). **Not acceptance-changing** — a labelling decision.
- **Research (HOW only).** The in-app rendering approach and offline bundling landscape may be grounded
  by The Researcher for AGT-01; this spec fixes the WHAT and does not block on it.
- **Downstream.** AGT-01 (`sdd-plan` — model/reader APIs + placement, rendering widget, bundling
  pipeline, search-index depth, locale layout); AGT-08 (docs owner — single-source bundling + i18n
  layout, cloud/collab pages post-Phase-10); AGT-06 (Gherkin → pytest/pytest-qt acceptance tests);
  AGT-03/04 (logic + data + tests); AGT-05 (UI + pytest-qt); AGT-07 (i18n of chrome strings).

## 8. Single-source + bundling — explicit coordination flags (AGT-01 / AGT-08)

**These are the two flags the owner directive requires be raised explicitly.**

- **DEP-2 (SOURCE OF TRUTH — recommended architecture; AGT-01 owns HOW).** The guide **single-sources
  its content from `docs/site`** (REQ-UG-DATA-002) so it cannot drift from the real documentation. The
  spec **recommends** this architecture and fixes it as the WHAT; **HOW** it is realised (a derivation
  step that reads the mkdocs source pages / built site and packages them as the in-app bundle, the
  content format the model consumes, and the discovery manifest that orders the ToC) is an **AGT-01
  plan / ADR decision**, coordinated with **AGT-08** (the `docs/site` owner). An **ADR** is expected for
  the source-of-truth + bundling model.
- **DEP-3 (BUNDLING — offline package data; AGT-01 / AGT-08).** The content must ship as **offline
  bundled package data** (no network, NFR-3). **HOW** the `docs/site` content is bundled (packaged as
  resource files, generated at build time, kept in sync with `docs/site` so no drift), **where** the
  bundle lives, and how the **per-phase extensibility** (REQ-UG-LOGIC-002) and **localised content**
  (DEP-4) slot into that bundle are **AGT-01 / AGT-08** decisions. The observable contracts (offline,
  single-sourced, discoverable, no-code-change growth) are fixed here.

## 9. New constants (for AGT-03 — Article II / S12)

- No numeric tuning value is required by the WHAT as specified. **If** the plan introduces one (e.g. a
  search-result cap, a ToC max depth, or a content-size guard for the reader), it lives **only** in
  `logic/constants.py` with a source citation — never inlined (Article II). Section/topic **ids** and
  **locale codes** are string identifiers, not numeric tuning values (Article II governs numerics), so
  they are not constants-file entries; AGT-01 rules on their home (a discovery manifest is natural).

## 10. Clarifications (sdd-clarify — resolved defaults, per A2-D2 Branch B)

All candidate ambiguities are resolved with **grounded category-1 defaults** and recorded below. The
three owner-flagged candidates (content mirror-vs-fresh, search depth, localised-content mapping) are
each resolvable against the **explicit** user request text (which mandates single-sourcing `docs/site`
and an in-guide search) + the shipped `docs/site` structure, so **no item required SUSPEND**. They are
enumerated prominently (and in the EXIT report) so the orchestrator retains visibility and may confirm.

- **CL-1 — Content is SINGLE-SOURCED from `docs/site`, not authored fresh (resolved; grounded by the
  request).** The user request explicitly states the guide "should single-source its content from the
  existing durable user docs under `docs/site` … so the in-app guide cannot drift from the real
  documentation." The guide's content therefore **is** the `docs/site` content (REQ-UG-DATA-002); no
  parallel/fresh content is authored. The bundling/derivation is HOW (DEP-2/DEP-3). **Not suspended** —
  the request is prescriptive. *(REQ-UG-DATA-002, REQ-UG-LOGIC-001.)*
- **CL-2 — Search is REQUIRED and finds topics; index depth (title/keyword vs full-text) is HOW
  (default: topic-level find).** The request lists "in-guide search/filter" as a viewer requirement and
  "search finds a topic" as an acceptance, so **search is required** (not merely ToC nav). The
  **observable contract** (REQ-UG-LOGIC-003) is: a term that identifies a topic (present in the topic's
  indexed text — at least title + keywords/summary) returns that topic. Whether the index also covers
  full **body** text is a HOW refinement for AGT-01 (the `docs/site` build already ships a full-text
  lunr index as prior art, so full-text is feasible later). An **empty/whitespace** term returns the
  **full topic set** (a filter that narrows as you type). **Not suspended** — search is mandated by the
  request; only the index depth is HOW and does not change the "finds a topic" acceptance.
  *(REQ-UG-LOGIC-003, REQ-UG-UI-006.)*
- **CL-3 — Localised content: resolve localised-if-present, else fall back to the default locale;
  authoring localised docs + the `docs/site` i18n layout are flagged, not blocking.** The chrome is
  fully translated (`tr()`, Article V, REQ-UG-UI-011). The **content** is **localisable** via
  REQ-UG-LOGIC-004: show the localised doc when one exists for the active locale, else the default
  locale. `docs/site` currently has **no** i18n layout, so **no localised content ships initially**
  (content is in the default language, mirroring the current single-language docs) — this is
  **language-agnostic** so no acceptance depends on a particular translation existing. Establishing the
  `docs/site` i18n layout + authoring localised docs is flagged to **AGT-08 / AGT-01** (DEP-4). **Not
  suspended** — the request says to *flag* the mapping, and the fallback contract makes acceptance
  independent of it. *(REQ-UG-LOGIC-004, REQ-UG-UI-011.)*
- **CL-4 — Shortcut is F1 (resolved default).** The request suggests "e.g. F1"; F1 is the platform
  convention for Help and is confirmed as the default open shortcut (REQ-UG-UI-002). AGT-01/AGT-05 may
  additionally expose a menu accelerator; F1 is the fixed WHAT. *(REQ-UG-UI-002.)*
- **CL-5 — Read-only guide (resolved default).** The guide **views** documentation; it never edits it
  or the document (NFR-5). Editing `docs/site` remains AGT-08's docs workflow. *(NFR-5.)*
- **CL-6 — Window vs dockable panel is HOW (resolved: navigable surface, either form).** The request
  says "window/panel"; whether the guide is a separate window or a dockable panel is an AGT-01/AGT-05
  HOW decision — the fixed WHAT is a **navigable ToC-tree + content surface** (REQ-UG-UI-003).
  *(REQ-UG-UI-003.)*

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour, phrased for **headless** testing (logic/data via pytest [+
Hypothesis]; UI via pytest-qt in **both themes**, `QT_QPA_PLATFORM=offscreen`). Every functional REQ
has ≥1 scenario; the REQ ↔ scenario ↔ test mapping is in `traceability.md` (**0 uncovered**). The
owner-required scenarios (open from menu + F1; navigate ToC; search finds a topic; both themes;
keyboard-only; offline; content for each area incl. cloud/collab) are all present.

### Feature: Guide content model — section→topic tree (REQ-UG-LOGIC-001)
```gherkin
Scenario: SC-L001-1 the model builds an ordered section->topic tree organised by functionality
  Given a bundled guide content set
  When I build the content model
  Then I get an ordered tree of sections each containing topics
  And each topic exposes an id, a title, a content reference, and searchable metadata

Scenario: SC-L001-2 the section set covers every enumerated functionality area
  Then the sections include canvas & view, colour hub, layers, selection/transform, animation,
       tileset/tilemap, export & pipeline, automation/scripting, visual aids, cloud & collaboration,
       asset library, and app-wide basics

Scenario: SC-L001-3 the model imports zero Qt (Article I) [spec-only, check_layering]
```

### Feature: Content discovery & extensibility (REQ-UG-LOGIC-002)
```gherkin
Scenario: SC-L002-1 adding a bundled doc adds a topic with no code change
  Given a content model built from a fixture bundle
  When a new bundled doc is added to the bundle
  And the model is rebuilt
  Then a new topic/section appears in the ToC without any model or viewer code change

Scenario: SC-L002-2 discovery ordering is deterministic
  Given the same bundle
  When the model is built twice
  Then the ToC order is identical both times
```

### Feature: Search/filter query (REQ-UG-LOGIC-003)
```gherkin
Scenario: SC-L003-1 searching a term that identifies a topic returns that topic
  Given a content model with a topic whose indexed text contains "onion skinning"
  When I query "onion skinning"
  Then the matching topic is in the ordered results

Scenario: SC-L003-2 search is case-insensitive and deterministic
  Given a content model
  When I query "LAYERS" and "layers"
  Then both return the same ordered results

Scenario: SC-L003-3 an empty/whitespace term returns the full topic set (CL-2)
```

### Feature: Locale resolution (REQ-UG-LOGIC-004)
```gherkin
Scenario: SC-L004-1 a localised topic resolves to the localised content when present
  Given a topic with a localised doc for locale "es"
  When I resolve the topic for active locale "es"
  Then the "es" content is returned

Scenario: SC-L004-2 a topic with no localised doc falls back to the default locale (CL-3)
  Given a topic with no doc for locale "es"
  When I resolve the topic for active locale "es"
  Then the default-locale content is returned
```

### Feature: Coverage/completeness contract (REQ-UG-LOGIC-005)
```gherkin
Scenario: SC-L005-1 every required functionality area has at least one topic
  Given the built content model
  Then each required area (incl. cloud & collaboration) maps to >= 1 topic

Scenario: SC-L005-2 a missing required area is detectable as a gap
  Given a bundle missing the cloud & collaboration area
  When completeness is checked
  Then the missing area is reported (not silently passed)
```

### Feature: Offline bundled-content reader (REQ-UG-DATA-001)
```gherkin
Scenario: SC-D001-1 content is read from the local bundle with no network access
  Given a bundled content resource
  When the reader loads it
  Then the content is returned from local package data
  And no network request is made

Scenario: SC-D001-2 a missing/malformed content resource raises a domain exception (no crash)

Scenario: SC-D001-3 content paths are constructed portably [spec-only, path_portability_check]
```

### Feature: Single source of truth — derives from docs/site (REQ-UG-DATA-002)
```gherkin
Scenario: SC-D002-1 the bundled content corresponds to the docs/site source (no separate fork)
  Given the docs/site usage pages
  When the guide bundle is produced
  Then each guide topic corresponds to a docs/site source page (single-sourced)

Scenario: SC-D002-2 the guide has no hand-maintained content that diverges from docs/site [spec-only, review/ADR]
```

### Feature: Trusted-but-validated load; content never executed (REQ-UG-DATA-003)
```gherkin
Scenario: SC-D003-1 content is rendered as text/markup and never passed to eval/exec [spec-only, review]

Scenario: SC-D003-2 a user-influenced content path that escapes the bundle root is rejected
  Given a topic id / link that resolves outside the bundle root
  When the reader resolves it
  Then a domain exception is raised (no path traversal)
```

### Feature: Help menu opens the guide (REQ-UG-UI-001)
```gherkin
Scenario: SC-U001-1 Help > User Guide opens the guide window/panel (both themes)
  Given the main window
  When I trigger Help > User Guide
  Then the guide surface opens showing the ToC and a content pane
```

### Feature: F1 opens the guide (REQ-UG-UI-002)
```gherkin
Scenario: SC-U002-1 pressing F1 opens the guide (same surface as the menu action)
  Given the main window with focus
  When I press F1
  Then the guide surface opens
```

### Feature: Navigable window with ToC tree + content pane (REQ-UG-UI-003)
```gherkin
Scenario: SC-U003-1 the guide shows a ToC navigation tree organised by functionality and a content pane
  Given the guide is open
  Then a ToC tree (sections->topics) and a content pane are visible
```

### Feature: ToC navigation shows the topic (REQ-UG-UI-004)
```gherkin
Scenario: SC-U004-1 selecting a ToC entry shows that topic's page
  Given the guide is open
  When I select the "Layers" topic in the ToC
  Then the content pane shows the Layers topic page

Scenario: SC-U004-2 the ToC reflects the model's section/topic order (calls the model, not hard-coded)
```

### Feature: Content rendered as text, no execution, no network (REQ-UG-UI-005)
```gherkin
Scenario: SC-U005-1 a topic renders as text/markup in the content pane (both themes)
  Given the guide is open
  When I open a topic
  Then its content renders as text/markup

Scenario: SC-U005-2 an in-guide link navigates to another topic within the guide (no external fetch)

Scenario: SC-U005-3 a content load error surfaces a user-facing message, not a crash
```

### Feature: In-guide search/filter (REQ-UG-UI-006)
```gherkin
Scenario: SC-U006-1 typing a term shows matching topics and jumping to a result opens it
  Given the guide is open
  When I type "export" in the search box
  Then the matching topics are shown
  And selecting a result opens that topic in the content pane

Scenario: SC-U006-2 search "finds a topic" — a known term resolves to its topic (owner-required)
```

### Feature: Fully offline (REQ-UG-UI-007)
```gherkin
Scenario: SC-U007-1 the guide opens, navigates and renders with no network available (owner-required)
  Given no network connectivity
  When I open the guide and navigate to any topic
  Then it opens and renders entirely from bundled content
  And no network request is made
```

### Feature: Cloud & collaboration content present (REQ-UG-UI-008)
```gherkin
Scenario: SC-U008-1 the guide's ToC includes the cloud & collaboration section (owner-required)
  Given the guide is open (post-Phase-10 content bundled)
  Then the ToC contains a cloud & collaboration section
  And it covers connect/manage, shared projects, comments, presence, and branching

Scenario: SC-U008-2 content is present for each major functionality area (owner-required)
  Then every required area in the ToC has at least one readable topic
```

### Feature: Accessibility (REQ-UG-UI-009)
```gherkin
Scenario: SC-U009-1 the guide is fully keyboard-navigable with visible focus (owner-required)
  Given the guide is open
  When I navigate the ToC, search box and content pane using only the keyboard
  Then every interactive element is reachable in a logical focus order with a visible focus indicator

Scenario: SC-U009-2 interactive controls expose accessible names/descriptions [a11y-audit]
```

### Feature: Both themes (REQ-UG-UI-010)
```gherkin
Scenario: SC-U010-1 the guide renders correctly and legibly in both light and dark themes (owner-required)
  Given the guide is open
  When the theme is light and then dark
  Then the ToC, content pane and search box render correctly and content text stays legible
```

### Feature: i18n chrome + localisable content (REQ-UG-UI-011)
```gherkin
Scenario: SC-U011-1 all guide chrome strings are tr()-wrapped [spec-only, string_audit_check]

Scenario: SC-U011-2 guide chrome re-translates on QEvent.LanguageChange

Scenario: SC-U011-3 guide content follows locale resolution (localised if present, else default) (CL-3)
```

---

## 12. Exit / status

- Forward pre-implementation spec authored for the cross-cutting **in-app User Guide** (`REQ-UG-*`),
  single-sourcing the shipped `docs/site` documentation as offline bundled content.
- **19 REQ-IDs**: 5 LOGIC (`REQ-UG-LOGIC-001..005`) + 3 DATA (`REQ-UG-DATA-001..003`) + 11 UI
  (`REQ-UG-UI-001..011`).
- **~40 Gherkin scenarios**; every functional REQ has ≥1 scenario; traceability shows **0 uncovered**
  (`traceability.md`). All owner-required scenarios present (menu + F1; ToC nav; search finds a topic;
  both themes; keyboard-only; offline; content per area incl. cloud/collab).
- **6 clarify decisions (CL-1..6)** recorded as category-1 defaults; **no SUSPEND** — the three
  owner-flagged candidates (content single-source, search depth, localised-content mapping) are each
  resolvable against the explicit request + shipped `docs/site` and are enumerated for orchestrator
  visibility.
- **Coordination flags raised explicitly (§8):** DEP-2 (single-source-of-truth from `docs/site` —
  AGT-01 owns HOW, ADR expected) and DEP-3 (offline bundling of `docs/site` content — AGT-01 / AGT-08).
  Plus DEP-1 (sequencing: build after Phase 10), DEP-4 (localised-content `docs/site` i18n layout —
  AGT-08/AGT-01), DEP-5 (`REQ-UG-*` cross-cutting prefix — orchestrator/AGT-01 confirm).
- Constitution: Article I (model/reader zero-Qt, viewer in `ui/`), Article VII (offline, no exec,
  path validation), Article V (a11y/both-themes/i18n), Article XI (extensible content), Article X
  (traceability), Article II (numerics). **Did not touch any `specs/phase-10-*` file.**
- **STATUS: COMPLETED.**
