# Analyze Report — In-App User Guide (`user-guide`, `REQ-UG-*`) (C1 gate)

| Field | Value |
| --- | --- |
| Feature | `user-guide` (cross-cutting, not a single roadmap phase) |
| Phase | `sdd-analyze` (Article VIII gate, C1) |
| Author | AGT-01 (Architecture) |
| Date | **2026-07-30** |
| Mode | **RETROFIT / POST-IMPLEMENTATION** — see §0.1 |
| Artifacts | `constitution.md` · `spec.md` + `traceability.md` · `plan.md` + `tasks.md` · ADR-0029 · shipped `logic/guide_*.py`, `data/guide_content.py`, `ui/user_guide.py`, `userguide_content/**`, tests |
| Verdict | **PASS** — zero unresolved cross-artifact findings; 4 advisory observations (§6) |

---

## 0. Gate preconditions (Article VIII)

All four required artifacts exist and are parseable: `constitution.md`, `spec.md`,
`plan.md`, `tasks.md` (+ `traceability.md`). The gate is permitted to run.

### 0.1 Provenance of this report — READ THIS FIRST

**This report is a retrofit, authored 2026-07-30.** `tasks.md` lines 48–49 recorded
`Verdict: **PASS** (see sdd-analyze report / EXIT below) → implementation is CLEARED`, but
**neither the cited report nor the cited EXIT block existed anywhere on disk**. The
citation was dangling: from the artifacts alone, "the gate ran and was not persisted" and
"the gate was asserted without running" were indistinguishable.

This report is the artifact that citation should have pointed at. It is authored **after**
the feature shipped, so the verdict below is **retrospective**: it establishes that the
shipped feature *would have* cleared the gate and that the artifact set is consistent
today. It does **not** claim the gate governed the implementation as it happened. The
`tasks.md` citation has been corrected on 2026-07-30 to say exactly this (see §5).

## 1. Deterministic layering / cycle gates (Article I)

Run 2026-07-30 against the current tree (Obligation 2 — proven by script, never by reading):

| Script | Output | Exit |
| --- | --- | --- |
| `python main/scripts/check_layering.py` | `clean (194 modules; 2 root module(s), 0 exempt top-level package(s), 0 unregistered)` | **0** |
| `python main/scripts/check_cycles.py` | `no cycles (196 modules)` | **0** |

Both exit 0 → Decision A1-D3 Branch B (accept). No exit 2. The plan's baseline was
"clean (154) / no cycles (155)"; the tree has since grown to 194/196 and **remains clean**,
so the guide modules did not perturb the layering. `logic/guide_model.py`,
`logic/guide_search.py` and `data/guide_content.py` are Qt-free (Article I / NFR-1 /
SC-L001-3); `ui/user_guide.py` is the only Qt surface, as plan §1 required.

## 2. Constitution conformance verified against code (not rubber-stamped)

### Article I — frozen module surface realised

All four modules from the plan §3 frozen contract exist at their declared paths:
`pixelart_creator/logic/guide_model.py`, `logic/guide_search.py`, `data/guide_content.py`,
`ui/user_guide.py`. The Help ▸ User Guide + F1 extension (plan §3.6, REQ-UG-UI-001/-002)
is wired in `ui/main_window.py`: `QAction` + `QKeySequence(Qt.Key.Key_F1)` (L1036–1038),
`_help_menu.addAction` (L1241), handler `_on_user_guide` (L2883), import at L230 — no
hard-coded ToC in the widget.

### Article II — numerics single-sourced

All three declared numeric constants are present in `logic/constants.py` at the planned
values, and nowhere else:

| Constant | Planned | Found | Line |
| --- | --- | --- | --- |
| `GUIDE_SEARCH_RESULT_CAP` | 50 | `: int = 50` | 587 |
| `GUIDE_MAX_CONTENT_BYTES` | 1_048_576 | `: int = 1048576` | 593 |
| `GUIDE_MAX_TOC_DEPTH` | 3 | `: int = 3` | 600 |

The **negative** ruling also holds: `DEFAULT_GUIDE_LOCALE` is a *string* identifier and is
correctly **not** in `constants.py` (L583 carries an explicit comment recording exactly
that rationale, matching plan §3.4 / ADR-0001). Article II satisfied.

### Article VII / VIII — the ADR-0029 constitutional conflict, correctly resolved

This is the load-bearing architectural check, and it is the one the gate exists for. The
spec's DEP-2 recommended single-sourcing guide content from `docs/site`. Constitution S19
makes `docs/**` **private — gitignored and purged from history**, so `docs/site` is absent
from the repo, the CI checkout and the wheel, and **cannot** be the shipped source.

Plan §2 resolves this **the constitutionally correct way**: it changes the *plan* to a
committed package-data bundle (`pixelart_creator/userguide_content/`) rather than weakening
S19 or routing around it. That is Article VIII §3 (supremacy) applied properly, and
Decision AN-D2 Branch A. **Verified on disk:** the bundle exists with `manifest.json` +
`content/en/*.md`, and the app has zero runtime dependency on `docs/site`. Confirmed
correct — no finding.

## 3. Cross-artifact consistency

- **spec ↔ constitution:** the `REQ-UG-*` cross-cutting prefix substitutes a feature key
  for a phase number in the Article-X scheme. Plan §6 records this as an **explicit AGT-01
  ratification** for non-phase features (DEP-5 / PREFIX-NOTE), i.e. a documented labelling
  extension, not a silent deviation and not acceptance-changing. Accepted.
- **plan ↔ spec:** plan §3 freezes a public surface covering all 19 REQs; the six
  clarifications CL-1..6 are all dispositioned; the AGT-01 "fix at plan time" list from
  traceability §5 (a)–(f) is answered item-for-item in plan §3/§5. **No drift.**
- **tasks ↔ plan:** T-UG-00..09 realise plan §2–§6. Dependency graph acyclic, with the C1
  gate correctly drawn as a hard barrier between T-UG-01 and T-UG-02+. **No orphan task** —
  every task carries a REQ/acceptance link.

## 4. Coverage (Article X / Article IV) — verified, not asserted

- **19 / 19 REQ-IDs** (5 LOGIC + 3 DATA + 11 UI) map to ≥1 task and ≥1 Gherkin scenario.
  **0 uncovered. 0 orphan tasks.**
- **Content coverage contract proven against the REAL bundle** (this was T-UG-08's
  acceptance criterion and the feature's central promise — "cover the ENTIRE platform"):
  `content/en/` ships 19 topics including every required area — canvas-and-view, colour-hub,
  layers, selection-and-transform, animation-timeline, tileset-and-tilemap,
  export-and-pipeline, automation-and-scripting, visual-aids, cloud-and-collaboration,
  app-basics — plus the Phase-11+ growth areas asset-library, asset-tagging/versioning/
  dependencies, and ai-assistant. The four topics plan §4 flagged as needing fresh authoring
  (canvas & view, colour hub, selection/transform, app-wide basics) **all exist**.
  `missing_required_areas() == ()` is asserted by
  `tests/logic/test_guide_model.py::test_shipped_scaffold_builds_and_is_complete`, which
  **passed** in this run.
- **Suites executed 2026-07-30**, headless `QT_QPA_PLATFORM=offscreen`:
  `tests/logic/test_guide_model.py · tests/logic/test_guide_search.py ·
  tests/data/test_guide_content.py · tests/ui/test_user_guide.py` → **150 passed, 0 failed**
  (14.4 s).
- **Scenario ids are cited in the tests themselves** — 32 distinct `SC-*` ids appear in the
  four guide test modules, spanning SC-L001..005, SC-D001..003 and SC-U001..011, which is
  consistent with one test per acceptance criterion (Article IV §4).

## 5. The dangling-citation finding (the reason this retrofit exists)

**F-UG-01 — `tasks.md:48-49` cited a PASS verdict from a report that did not exist.
SEVERITY: HIGH.** The barrier text asserted the C1 gate had cleared and that
implementation was "CLEARED", citing an `sdd-analyze` report and an EXIT block, **neither
of which was ever written**. **Disposition: CORRECTED 2026-07-30** — the citation now
points at this report, carries its real verdict, and states plainly that the verdict is a
retrofit authored after implementation rather than the contemporaneous clearance the
original text implied. **RESOLVED.**

## 6. Advisory observations (non-blocking; do NOT hold the gate)

1. **OBS-1 (stale artifact mode — hand to AGT-02).** `traceability.md` is still headed
   **"FORWARD / PRE-IMPLEMENTATION (2026-07-04) — no code/tests on disk yet"**, and every
   row's status is `spec` with an *indicative* test target. The code and 150 passing tests
   have shipped. The matrix should be advanced to REALISED with concrete node-ids, exactly
   as `phase-1-ui-canvas/traceability.md` was. **`traceability.md` is AGT-02-owned and a
   sibling agent is active — NOT corrected here.**
2. **OBS-2 (test-file naming deviation — hand to AGT-02/AGT-04).** `tasks.md` T-UG-04 and
   `traceability.md` name `tests/logic/test_guide_locale.py` and
   `tests/logic/test_guide_coverage.py`. **Neither file exists.** This is **not a coverage
   gap**: both behaviours were consolidated into `tests/logic/test_guide_model.py` —
   locale resolution at L242–270 (`test_resolve_returns_localised_path_when_locale_available`,
   `test_resolve_falls_back_to_default_locale_when_absent`,
   `test_resolve_uses_explicit_default_locale_override`) and the coverage contract at
   L280–326 (`test_missing_required_areas_empty_for_full_manifest`,
   `test_missing_required_areas_reports_absent_area`). The matrix explicitly labelled these
   targets "indicative", so the deviation is sanctioned; the artifacts should nonetheless be
   updated to the real filenames.
3. **OBS-3 (Article IX §4, pre-existing, repo-wide).** Sibling `main/specs/**` artifacts
   carry `Author | Claude (…)` in committed file headers, which Article IX §4 forbids
   anywhere in the repository including file headers. This report uses
   `AGT-01 (Architecture)` and adds no new instance. Separate, broader remediation.
4. **OBS-4 (DEP-1 sequencing, closed).** The spec sequenced this feature "after Phase 10 so
   cloud/collab docs exist". Phase 10 has shipped and `cloud-and-collaboration.md` is in the
   bundle. DEP-1 is satisfied; no action.

None of the four is a cross-artifact contradiction or a coverage gap.

## 7. Explicitly NOT verified in this run (Obligation 5)

- **Coverage percentages.** The ≥90 % line / ≥80 % branch gate (Article IV, NFR-7) was
  **not re-computed**; only pass/fail of the four named suites was established.
- **`string_audit_check` (REQ-UG-UI-011 / SC-U011-1)** and **`path_portability_check`
  (SC-D001-3)** were **not re-run**; these are AGT-07 / AGT-09 script gates.
- **`a11y-audit` (REQ-UG-UI-009)** was not re-run; the pytest-qt a11y tests inside
  `tests/ui/test_user_guide.py` *were* executed and passed.
- **T-UG-09 packaging** — that `pyproject.toml` ships `userguide_content/**` as package
  data in the built wheel was **not verified**; no wheel was built. `pyproject.toml` is
  AGT-09-owned.
- **ADR-0029** was cited from plan/tasks references; the ADR file itself was **not opened**
  in this run.
- **The "no-drift" discipline** between the committed bundle and the private `docs/site`
  editorial source is, by the plan's own §7 risk note, an authoring discipline with **no CI
  gate** — it is unverifiable from this repository and was not verified.

## 8. Verdict

**PASS (C1) — retrospective.** Zero unresolved cross-artifact findings
(Decision AN-D1 → Branch A; Decision A1-D2 → Branch A). constitution ↔ spec ↔ plan ↔
tasks ↔ code ↔ tests are consistent as they stand on 2026-07-30; all 19 REQs are specified,
scenario-backed and exercised by 150 passing tests; the coverage contract passes against
the real shipped bundle; Article I gates exit 0; Article II constants verified in place;
the ADR-0029 S19 conflict was resolved **up** to the constitution rather than around it.

**This PASS is retrospective and does not retroactively legitimise the missing gate.** The
four §6 observations are advisory; OBS-1 and OBS-2 are handed to AGT-02. §7 records what
this run did not verify.

**EXIT_STATUS: COMPLETED** (analyze ran on real artifacts + real code; PASS with 4 advisory
observations, 2 handed to AGT-02).
