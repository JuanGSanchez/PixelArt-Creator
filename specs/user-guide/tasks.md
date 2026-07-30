# Tasks — In-App User Guide (`user-guide`, `REQ-UG-*`)

| Field | Value |
| --- | --- |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-04 |
| Consumes | `plan.md` + ADR-0029 + `spec.md` + `traceability.md` |
| Gate | `sdd-analyze` (C1) must PASS before any implement task starts (Article VIII). |
| Baseline | `check_layering` clean (154) / `check_cycles` no cycles (155), both exit 0. |

Dependency-ordered. Each task names its **owner agent**, **target files**, and **acceptance link**.
`T-UG-00`/`01` are AGT-01 (this session, done); `T-UG-02+` are dispatched after the C1 gate passes.

## Ordering (dependency graph)

```
T-UG-00 (ADR-0029)  ─┐
T-UG-01 (contract) ──┼─► [C1 GATE] ─► T-UG-02 (AGT-08 content, parallel)
                     │                T-UG-03 (AGT-03 logic/data) ─► T-UG-04 (AGT-04 tests)
                     │                        │
                     │                        ▼
                     │                T-UG-05 (AGT-05 UI) ─► T-UG-06 (AGT-06 QA) 
                     │                        │                    │
                     │                        ▼                    ▼
                     │                T-UG-07 (AGT-07 i18n)   T-UG-02 finalised (cloud/collab)
                     │                                             │
                     └───────────────────────────────────► T-UG-08 (AGT-01 re-analyze/coverage)
                                                                   │
                                                                   ▼
                                                            T-UG-09 (AGT-09 pyproject+commit)
```

---

### T-UG-00 — ADR + plan (AGT-01) — DONE
- **Files:** `docs/adr/0029-...md`, `specs/user-guide/plan.md`, this `tasks.md`.
- **Does:** resolve the content-source/bundling + layering decision; freeze the module surface.
- **Acceptance:** ADR-0029 Accepted; plan §2 records the committed-bundle decision. ✔

### T-UG-01 — Interface-contract freeze + STRUCTURE.md (AGT-01) — DONE (this session)
- **Files:** `STRUCTURE.md` (add the `user-guide` planned rows).
- **Does:** freeze the public surface of `logic/guide_model.py`, `logic/guide_search.py`,
  `data/guide_content.py`, `ui/user_guide.py` per plan §3 so downstream binds to a stable contract.
- **Acceptance:** STRUCTURE.md updated; contracts match plan §3. ✔

---

> The tasks below start ONLY after the C1 `sdd-analyze` gate PASSES (Article VIII).
> Verdict: **PASS (retrospective)** — see **`specs/user-guide/analyze-report.md`**
> (AGT-01, 2026-07-30): zero unresolved cross-artifact findings, 4 advisory observations
> (2 handed to AGT-02); `check_layering` clean (194) / `check_cycles` no cycles (196), both
> exit 0; the 3 `GUIDE_*` constants verified in `logic/constants.py`; the coverage contract
> verified against the real shipped bundle; 150 guide tests passed headless.
>
> **CORRECTION (2026-07-30).** This block previously read *"Verdict: **PASS** (see
> `sdd-analyze` report / EXIT below) → implementation is **CLEARED**"* — a **dangling
> citation: neither that report nor that EXIT block existed anywhere on disk.** The gate
> outcome was asserted here without a persisted artifact to back it, so "ran but was not
> persisted" and "never ran" could not be told apart from the artifacts. The analyze report
> now cited **genuinely exists**, but it was authored on **2026-07-30, after this feature
> shipped** — it is a retrofit, not the contemporaneous clearance the original wording
> implied. Corrected rather than deleted so the history stays auditable.

### T-UG-02 — Author + organise the committed guide CONTENT (AGT-08) — [may run in parallel with T-UG-03]
- **Files:** `pixelart_creator/userguide_content/manifest.json`,
  `pixelart_creator/userguide_content/content/en/*.md`.
- **Does:** author/organise the guide prose into the section→topic tree for **every** required area
  (canvas & view, colour hub, layers, selection/transform, animation, tileset/tilemap, export,
  automation, visual aids, **cloud & collaboration**, app-wide basics) — reusing/mirroring the existing
  `docs/site/pages/usage/*.md` prose where a page exists (layers, blend-modes, multi-canvas,
  floating-selection, drag-drop-import, animation, tilemap, export, automation, visual-aids, cloud,
  collaboration) and **authoring the missing topics** (canvas & view, colour hub, selection/transform,
  app-wide basics). Author `manifest.json` (ordered ids/titles/keywords/summaries/content refs). Define
  + document the **local sync/derivation step** keeping the committed bundle aligned with the private
  `docs/site` editorial source (ADR-0029 §1) — **no runtime dependency on `docs/site`**.
- **Scope:** substantial prose authoring covering shipped **phases 1–10**; cloud/collab content is
  available now (`docs/site` `cloud.md` + `collaboration.md` shipped) → DEP-1 satisfied.
- **Acceptance:** SC-D002-1/-2 (single-sourced, no divergent fork), SC-L005-1 (every required area ≥1
  topic), SC-U008-1/-2 (cloud/collab section present). REQ-UG-DATA-002, REQ-UG-LOGIC-005, REQ-UG-UI-008.

### T-UG-03 — Implement logic + data (AGT-03, zero Qt)
- **Files:** `logic/guide_model.py`, `logic/guide_search.py`, `data/guide_content.py`,
  `logic/constants.py` (+`GUIDE_SEARCH_RESULT_CAP`, `GUIDE_MAX_CONTENT_BYTES`, `GUIDE_MAX_TOC_DEPTH`).
- **Does:** implement the frozen contract (plan §3): tree build + manifest discovery + deterministic
  order + locale resolution + coverage contract (model); pure `query()` (search); offline
  `importlib.resources` reader with bundle-root path guard + size guard + domain errors, no network, no
  `eval`/`exec` (data). **Zero Qt.**
- **Acceptance:** REQ-UG-LOGIC-001..005, REQ-UG-DATA-001..003; `check_layering`/`check_cycles` exit 0;
  `path_portability_check` clean. SC-L001..005, SC-D001..003.

### T-UG-04 — Logic + data tests (AGT-04, pytest + Hypothesis)
- **Files:** `tests/logic/test_guide_model.py`, `tests/logic/test_guide_search.py`,
  `tests/logic/test_guide_locale.py`, `tests/logic/test_guide_coverage.py`,
  `tests/data/test_guide_content.py` (+ a fixture bundle for discovery/extensibility).
- **Does:** one test per acceptance criterion; Hypothesis for discovery-ordering/search/locale
  invariants; a fixture-bundle discovery test proving no-code-change extensibility (SC-L002-1);
  malformed/oversized + traversal rejection tests (SC-D001-2, SC-D003-2).
- **Acceptance:** coverage gate ≥90 % line / ≥80 % branch (`coverage_gate`); all logic/data scenarios
  green. NFR-7, NFR-9.

### T-UG-05 — Implement the viewer + Help menu + F1 (AGT-05, Qt)
- **Files:** `ui/user_guide.py` (new), `ui/main_window.py` (extend: Help ▸ User Guide + F1).
- **Does:** `User_Guide_Dialog`/`_Panel` — ToC tree from `GuideModel`, `QTextBrowser` content pane
  (`setMarkdown`, `setOpenExternalLinks(False)`, in-guide link handler), search box → `guide_search`.
  Menu action + F1 shortcut. `tr()` chrome + `changeEvent`/`LanguageChange`; role-based theme colours;
  accessible names + keyboard nav + visible focus. Read-only — **no `ui/commands.py` change**.
- **Acceptance:** REQ-UG-UI-001..008; SC-U001..008. Calls the model/reader — no hard-coded ToC, no
  domain logic in the widget (Article I).

### T-UG-06 — UI/a11y/theme tests + checklist (AGT-06, pytest-qt + a11y-audit + sdd-checklist)
- **Files:** `tests/ui/test_user_guide.py` (headless, both themes).
- **Does:** one pytest-qt test per UI acceptance criterion in **both** light+dark; `a11y-audit`
  (accessible names, keyboard reach, focus, contrast); `sdd-checklist` (every REQ has a passing test,
  both themes + a11y + i18n covered).
- **Acceptance:** REQ-UG-UI-001..010; SC-U001..010; a11y + both-themes green; checklist passes.

### T-UG-07 — i18n of guide chrome (AGT-07)
- **Files:** `.ts`/`.qm` catalogues; audit of `ui/user_guide.py` + `ui/main_window.py` additions.
- **Does:** `string_audit_check` (report unwrapped strings — blocking), `pyside6-lupdate` extract →
  `.ts`, `lrelease` → `.qm`, `LanguageManager` wiring for live retranslate.
- **Acceptance:** REQ-UG-UI-011; SC-U011-1/-2; zero unwrapped user-visible strings.

### T-UG-08 — Re-analyze + coverage/checklist re-gate (AGT-01)
- **Does:** re-run `sdd-analyze` after content (T-UG-02) + code land; confirm coverage contract passes
  over the **real** bundle (all required areas present incl. cloud/collab); confirm 0 unresolved
  findings.
- **Acceptance:** Article VIII gate stays green; traceability 0 uncovered against implemented tests.

### T-UG-09 — Package data + commits (AGT-09)
- **Files:** `pyproject.toml` (include `pixelart_creator/userguide_content/**` as package data so it
  ships in the wheel); Conventional Commits with `REQ-UG-*` ids; CI green.
- **Does:** ensure the committed bundle ships in the distributable; commit per Article IX; CI runs the
  headless suite + coverage + `path_portability_check`.
- **Acceptance:** wheel contains `userguide_content/`; commits REQ-tagged; gate green (Articles III/IV/
  I/VIII/IX).

> **AGT-10:** no perf task — the guide viewer is not on the 16 ms canvas render loop (read-only document
> viewer, ADR-0029 §7). No AGT-10 directive required.

---

## Coverage — every REQ has a task + acceptance

| REQ | Task(s) | Scenarios |
| --- | --- | --- |
| REQ-UG-LOGIC-001 | T-UG-03/04 | SC-L001-1..3 |
| REQ-UG-LOGIC-002 | T-UG-03/04 (+ T-UG-02 manifest) | SC-L002-1..2 |
| REQ-UG-LOGIC-003 | T-UG-03/04 | SC-L003-1..3 |
| REQ-UG-LOGIC-004 | T-UG-03/04 | SC-L004-1..2 |
| REQ-UG-LOGIC-005 | T-UG-03/04 (+ T-UG-02 content) | SC-L005-1..2 |
| REQ-UG-DATA-001 | T-UG-03/04 | SC-D001-1..3 |
| REQ-UG-DATA-002 | T-UG-02 (+ ADR-0029) | SC-D002-1..2 |
| REQ-UG-DATA-003 | T-UG-03/04 | SC-D003-1..2 |
| REQ-UG-UI-001 | T-UG-05/06 | SC-U001-1 |
| REQ-UG-UI-002 | T-UG-05/06 | SC-U002-1 |
| REQ-UG-UI-003 | T-UG-05/06 | SC-U003-1 |
| REQ-UG-UI-004 | T-UG-05/06 | SC-U004-1..2 |
| REQ-UG-UI-005 | T-UG-05/06 | SC-U005-1..3 |
| REQ-UG-UI-006 | T-UG-05/06 | SC-U006-1..2 |
| REQ-UG-UI-007 | T-UG-05/06 | SC-U007-1 |
| REQ-UG-UI-008 | T-UG-02/05/06 | SC-U008-1..2 |
| REQ-UG-UI-009 | T-UG-06 | SC-U009-1..2 |
| REQ-UG-UI-010 | T-UG-06 | SC-U010-1 |
| REQ-UG-UI-011 | T-UG-07/05 | SC-U011-1..3 |

**STATUS: COMPLETED** (tasks authored; dispatch begins post-C1-gate).
