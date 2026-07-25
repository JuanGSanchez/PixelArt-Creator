# Traceability Matrix — In-App User Guide (`REQ-UG-*`)

REQ-ID ↔ user request / dossier S-id + governing article ↔ layer/owner ↔ spec section ↔ Gherkin
scenario(s) ↔ (future) test target.
**Mode:** FORWARD / PRE-IMPLEMENTATION (2026-07-04, AGT-02) — no code/tests on disk yet; the module
and test columns name **indicative** targets (final names/placement fixed by AGT-01 at `sdd-plan`).
Status: **spec** (specified + ≥1 Gherkin scenario) · **spec-only** (gate/script/review-enforced, no
unit test).

Test module conventions (from Phase-1/2): logic/data → `tests/logic|data/test_<module>.py` (pytest +
Hypothesis); UI → `tests/ui/test_<widget>.py` (pytest-qt, both themes, headless
`QT_QPA_PLATFORM=offscreen`).

## 1. Logic layer (`REQ-UG-LOGIC-001..005`) — owner AGT-03 (impl) / AGT-04 (tests)

| REQ-ID | Traces | Indicative module | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-UG-LOGIC-001 | request (structured ToC); S6; Art. I, XI | `logic/guide_model.py` (section→topic tree) | §4.1, §11 | SC-L001-1..2 ; SC-L001-3 (spec-only) | `tests/logic/test_guide_model.py` + `check_layering` | spec / spec-only |
| REQ-UG-LOGIC-002 | request (extensibility, Ph11–12); S6; Art. XI | `logic/guide_model.py` (discovery + ordering manifest) | §4.1, §11 | SC-L002-1..2 | `tests/logic/test_guide_model.py` (fixture-bundle discovery) | spec |
| REQ-UG-LOGIC-003 | request (search/filter); S6 | `logic/guide_search.py` `query()` | §4.1, §11 | SC-L003-1..3 | `tests/logic/test_guide_search.py` (+ Hypothesis) | spec |
| REQ-UG-LOGIC-004 | request (localisable); Art. V §2, Art. XI | `logic/guide_model.py` locale resolution | §4.1, §11 | SC-L004-1..2 | `tests/logic/test_guide_locale.py` | spec |
| REQ-UG-LOGIC-005 | request (cover ENTIRE platform incl. cloud/collab **and asset library, Phase 11**); S6; Art. X | `logic/guide_model.py` coverage contract (`REQUIRED_AREAS` incl. `asset-library`) | §4.1, §11 | SC-L005-1..2 | `tests/logic/test_guide_coverage.py` ; **asset-library area evidence:** `tests/logic/test_guide_model.py::test_shipped_scaffold_builds_and_is_complete` (asserts every `REQUIRED_AREA` — incl. `asset-library` — is covered by ≥ 1 topic) | spec |

## 2. Data layer (`REQ-UG-DATA-001..003`) — owner AGT-03 (impl) / AGT-04 (tests)

| REQ-ID | Traces | Indicative module | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-UG-DATA-001 | request (offline/bundled); S7; Art. VII | `data/guide_content.py` (offline reader) | §4.2, §11 | SC-D001-1..2 ; SC-D001-3 (spec-only) | `tests/data/test_guide_content.py` + `path_portability_check` | spec / spec-only |
| REQ-UG-DATA-002 | request (single-source docs/site, no drift); S7; Art. XI | `data/guide_content.py` (docs/site-derived bundle) + **ADR** | §4.2, §8, §11 | SC-D002-1 ; SC-D002-2 (spec-only/ADR) | `tests/data/test_guide_content.py` + ADR review | spec / spec-only |
| REQ-UG-DATA-003 | request (Art. VII: text not exec, validate path); S7; Art. VII | `data/guide_content.py` (validated load, bundle-root guard) | §4.2, §11 | SC-D003-2 ; SC-D003-1 (spec-only/review) | `tests/data/test_guide_content.py` + review | spec / spec-only |

## 3. UI layer (`REQ-UG-UI-001..011`) — owner AGT-05 (impl) / AGT-06 (tests, both themes)

| REQ-ID | Traces | Indicative module | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-UG-UI-001 | request (main-menu); S5 | `ui/main_window.py` Help ▸ User Guide action | §4.3, §11 | SC-U001-1 (both themes) | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-002 | request (F1 shortcut); S5; Art. V §1; CL-4 | `ui/main_window.py` F1 shortcut | §4.3, §11 | SC-U002-1 | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-003 | request (navigable viewer); S5 | `ui/user_guide.py` `User_Guide_Panel`/`_Dialog` (ToC tree + content pane) | §4.3, §11 | SC-U003-1 | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-004 | request (navigate ToC); S5 | `ui/user_guide.py` ToC selection → content | §4.3, §11 | SC-U004-1..2 | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-005 | request (render via QTextBrowser, never exec); S5; Art. VII | `ui/user_guide.py` content pane (text/markup, in-guide links) | §4.3, §11 | SC-U005-1..3 (SC-U005-1 both themes) | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-006 | request (in-guide search); S5 | `ui/user_guide.py` search box → `logic/guide_search.query` | §4.3, §11 | SC-U006-1..2 (SC-U006-2 owner-required) | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-007 | request (fully offline); S7; Art. VII | `ui/user_guide.py` (bundled render, no network) | §4.3, §11 | SC-U007-1 (owner-required) | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-008 | request (cover Phase-10 cloud/collab); S6; Art. X | `ui/user_guide.py` ToC (cloud/collab section) | §4.3, §11 | SC-U008-1..2 (owner-required) | `tests/ui/test_user_guide.py` | spec |
| REQ-UG-UI-009 | Art. V §1 | `ui/user_guide.py` keyboard nav + accessible names | §4.3, §11 | SC-U009-1..2 (SC-U009-1 owner-required) | `tests/ui/test_user_guide.py` + `a11y-audit` | spec |
| REQ-UG-UI-010 | Art. V §3 | `ui/user_guide.py` themed (role colours) | §4.3, §11 | SC-U010-1 (owner-required, both themes) | `tests/ui/test_user_guide.py` (both themes) | spec |
| REQ-UG-UI-011 | Art. V §2; F6 | `ui/user_guide.py` `tr()` chrome + `LanguageChange` + locale content | §4.3, §11 | SC-U011-1 (spec-only) ; SC-U011-2..3 | `tests/ui/test_user_guide.py` + `string_audit_check` | spec / spec-only |

## 4. Coverage summary (FORWARD / PRE-IMPLEMENTATION, 2026-07-04)

- **19 REQ-IDs**: 5 LOGIC (`REQ-UG-LOGIC-001..005`) + 3 DATA (`REQ-UG-DATA-001..003`) + 11 UI
  (`REQ-UG-UI-001..011`).
- **19 specified / 19 with ≥1 Gherkin scenario / 0 uncovered.** Every functional REQ maps to at least
  one scenario. Spec-only rows (gate/script/review-enforced, no unit test): SC-L001-3 (Qt-free purity
  via `check_layering`, Art. I); SC-D001-3 (`path_portability_check`, Art. VII); SC-D002-2 (single-
  source no-drift via ADR/review, Art. XI); SC-D003-1 (no `eval`/`exec`, review — Art. VII); SC-U011-1
  (`tr()` wrapping via `string_audit_check`, Art. V); §9 "no new numeric constant" via review (Art. II).
- **~40 Gherkin scenarios**: logic SC-L001..005 + data SC-D001..003 + UI SC-U001..011. Headless
  (`QT_QPA_PLATFORM=offscreen`): logic/data via pytest (+ Hypothesis for discovery/search/locale
  invariants), UI via pytest-qt in **both themes**.
- **Owner-required scenarios present:** open from menu (SC-U001-1) + F1 (SC-U002-1); navigate ToC
  (SC-U004-1); search finds a topic (SC-U006-2, SC-L003-1); both themes (SC-U010-1); keyboard-only
  (SC-U009-1); offline/no network (SC-U007-1, SC-D001-1); content for each area incl. cloud/collab
  (SC-U008-1..2, SC-L005-1).
- **Per-phase required-area growth (Article XI, REQ-UG-LOGIC-005):** the enumerated required-area set in
  REQ-UG-LOGIC-001 grows per phase; **Phase 11** adds `asset-library` (Asset Library — asset catalogue,
  tagging, search) after `cloud-and-collaboration`, keeping the coverage contract's intent unchanged.
  This area is covered by the shipped
  `tests/logic/test_guide_model.py::test_shipped_scaffold_builds_and_is_complete`, which asserts every
  `REQUIRED_AREA` (now incl. `asset-library`) maps to ≥ 1 topic — so spec, `REQUIRED_AREAS`, and the
  committed bundle stay verifiably aligned with no artifact drift.
- **Single-source acceptance** (no drift): SC-D002-1..2. **Extensibility** (no-code-change growth):
  SC-L002-1. **Safe content** (no exec / path guard): SC-D003-1..2, SC-U005-1.

## 5. Notes for sdd-analyze (AGT-01)

- **Every REQ traces to the user request + an S-id and/or a governing article** (S5 canvas/app
  surface, S6 extensibility, S7 file I/O; Articles I/V/VII/X/XI) — no untraced REQ (Article X). See
  **DEP-5 / PREFIX-NOTE**: the `REQ-UG-*` cross-cutting prefix substitutes a feature key for a phase
  number in the Article-X scheme — flagged for orchestrator/AGT-01 confirmation (not acceptance-
  changing).
- **NEW vs REUSED (spec §1):** NEW = content model (LOGIC-001..005), offline reader (DATA-001..003),
  Help ▸ User Guide action + F1 (UI-001/-002), guide viewer + ToC + content pane + search
  (UI-003..011). REUSED = `docs/site` durable docs (single source of truth, DATA-002), the main-window
  menu bar, the QSS theme roles + `tr()`/`LanguageChange` chrome pattern.
- **AGT-01 to fix at plan time (HOW):** (a) content-model + reader public APIs and final
  module names/placement (indicative: `logic/guide_model.py`, `logic/guide_search.py`,
  `data/guide_content.py`, `ui/user_guide.py`); (b) the markup-rendering widget (`QTextBrowser` vs
  alternative); (c) the **single-source + bundling** pipeline from `docs/site` → offline resource data
  (**ADR expected**, coordinated with AGT-08 — DEP-2/DEP-3); (d) search-index depth (title/keyword vs
  full-text, CL-2); (e) the `docs/site` **i18n layout** for localised content (with AGT-08 — DEP-4);
  (f) window-vs-dockable-panel (CL-6).
- **Coordination flags (spec §8):** DEP-2 (source-of-truth from `docs/site`, AGT-01 owns HOW),
  DEP-3 (offline bundling, AGT-01/AGT-08), DEP-1 (sequencing — build after Phase 10 so cloud/collab
  docs exist), DEP-4 (localised-content mapping — AGT-08/AGT-01).
- **Numerics (§9):** none required by the WHAT; any introduced (search-result cap / ToC depth / content
  size guard) lives only in `logic/constants.py` (Article II). Ids/locale codes are string identifiers,
  not numeric constants.
- **Clarifications** CL-1..6 recorded as category-1 defaults; **no SUSPEND** open. The three owner-
  flagged candidates (content single-source, search depth, localised-content mapping) are resolved with
  grounded defaults and enumerated for orchestrator visibility.
- **Sequencing (DEP-1):** author now, build after Phase 10 ships. **This feature did not touch any
  `specs/phase-10-*` file** (a separate AGT-02 instance owns those concurrently).
