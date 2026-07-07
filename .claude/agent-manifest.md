# Agent Manifest — PixelArt Creator

Lightweight index The Recommender (AGT-M3) queries during asset-inventory checks —
so it can decide whether existing agents cover a request without loading full agent
specs. The Recommender must check this manifest before proposing any new asset
(SKILL.md §2.2 consistency).

Threshold reminder: the Gleaner dispatch threshold is configured in the orchestrator
CONVENTIONS field (`.claude/agents/orchestrator.md`), default 5. Read that field —
do not assume the default.

## Mandatory Agents (Phase 2 — Mandatory-Layer Builder)

| Agent | One-line purpose | Spec file | Owns (summary) | Does not own |
|-------|-----------------|-----------|----------------|--------------|
| The Recaller (AGT-M1) | Stores, retrieves, and summarizes session memory + recovery briefs | `.claude/agents/the-recaller.md` | Memory records, session summaries, compacting summaries, own checkpoints | Domain tasks, strategy, asset generation, internet search, file gathering, durable docs |
| The Metaprompter (AGT-M2) | Generates, refines, validates assets (canonical asset-metaprompter) | `.claude/agents/the-metaprompter.md` | Asset authoring/validation, Principles Applied blocks, P11 vehicle production | Domain tasks, strategy, memory, internet search, file gathering |
| The Recommender (AGT-M3) | Analyzes requests → fulfillment strategy + P11 vehicle plan | `.claude/agents/the-recommender.md` | Request analysis, manifest inventory, strategy, P11 vehicle planning, coordination | Execution/dispatch, asset generation, memory, internet search, file gathering |
| The Researcher (AGT-M4) | Sole internet-search authority; cited research reports (resolves F9–F14) | `.claude/agents/the-researcher.md` | Internet search, source evaluation, research reports with citations | Domain tasks, strategy, asset generation, memory, ≥5-file local gathering |
| The Gleaner (AGT-M5) | Reads ≥5 files → one focused gather file (gather file is its checkpoint) | `.claude/agents/the-gleaner.md` | Multi-file reading, information extraction, gather-file lifecycle | Domain tasks, strategy, asset generation, memory, internet search, gather-file deletion |

## Domain Agents (Phase 3 — Conditional-Layer Builder; all 10 built + appended)

| Agent | One-line purpose | Spec file | Owns (summary) | Does not own |
|-------|-----------------|-----------|----------------|--------------|
| AGT-01 Architecture | Authors plan/tasks/constitution, cross-artifact analyze, and all file-placement/layering decisions | `.claude/agents/agt-01-architecture.md` | plan.md, tasks.md, constitution.md, analyze gate, STRUCTURE.md, check_layering/check_cycles, sdd-plan/tasks/analyze | code (03/05), tests (04/06), spec (02), render-perf (10), docs (08), commits (09) |
| AGT-02 Requirements | Functional→technical REQs, spec.md, clarifications, Gherkin, traceability | `.claude/agents/agt-02-requirements.md` | spec.md, clarifications, Gherkin, traceability matrix, sdd-specify/clarify | plan/tasks/placement (01), code (03/05), tests, render-perf (10), Qt lookups (M4) |
| AGT-03 Python Dev | logic/ + data/ code (zero Qt), reversible ops, colour-theory harmony math (F9) | `.claude/agents/agt-03-python-dev.md` | logic/ & data/ code, harmony math, maxrects_compactor use, local pre-flight | UI/Qt (05), render-perf (10), tests (04), placement (01), spec (02), commits (09) |
| AGT-04 Python Tester | pytest/Hypothesis tests for logic/data; ≥90/80 coverage | `.claude/agents/agt-04-python-tester.md` | tests/logic, tests/data, coverage_gate, regression-per-fix | UI tests (06), code under test (03), CI (09), render-perf (10) |
| AGT-05 UI Expert | PySide6 ui/: 8K canvas, colour tools, colour wheel, undo, i18n hooks | `.claude/agents/agt-05-ui-expert.md` | ui/ widgets/views/scene, ui/commands.py, colour wheel/menu/Favourites, tr()/changeEvent | logic (03), render-perf strategy (10), UI tests (06), catalogue files (07), placement (01) |
| AGT-06 QA Expert | pytest-qt UI/a11y tests, both themes, sdd-checklist, S1/S2 blockers | `.claude/agents/agt-06-qa-expert.md` | tests/ui, a11y, both-theme checks, sdd-checklist, S1/S2 issue requests | logic/data tests (04), UI code (05), perf profiling (10), commits/issue mechanics (09) |
| AGT-07 Localisation | i18n catalogue, LanguageManager, string audit (report-not-fix) | `.claude/agents/agt-07-localisation.md` | i18n/ .ts/.qm, ui/i18n.py, pyside6-lupdate/lrelease, string_audit_check | widget code (05), logic (03), docs (08), tests (04/06) |
| AGT-08 Documenter | Durable docs under docs/ subpaths, docstrings, mkdocs, pydocstyle | `.claude/agents/agt-08-documenter.md` | docs/adr, docs/site, CHANGELOG, SESSION_LOG, docstrings, mkdocs/pydocstyle | live memory/summaries (M1), code/tests (03–06), commits (09), temporal files |
| AGT-09 GitHub/DevOps | git, Conventional Commits, ci.yml, pyproject.toml, LICENSE, repo + branch protection | `.claude/agents/agt-09-github-devops.md` | .github/, ci.yml, pyproject.toml, LICENSE/NOTICE, repo/branch config, semver, coverage_gate/path_portability in CI | code/tests/docs (03–08), spec (02), placement (01), render-perf (10) |
| AGT-10 Rendering & Performance | GPU render-pipeline strategy + frame-budget profiling; issues directives to AGT-05 | `.claude/agents/agt-10-rendering-performance.md` | render strategy (tiling/culling/dirty-rect/QOpenGL/BSP), perf_profile, optimization directives | widget authoring (05), functional/a11y tests (06), logic (03), docs publish (08) |
| AGT-11 Web Client | Web companion-viewer frontend: vanilla HTML/CSS/JS pixel-faithful Canvas client + WS-over-`sync_backend` + signed share-link-token presentation + stdlib dev-server glue (Qt-free, view-only) | `.claude/agents/agt-11-web-client.md` | `web_viewer/static/*` (index.html/viewer.css/viewer.js), pixel-faithful Canvas render (ADR-0036 §4), WS client + token presentation, `web_viewer/dev_server.py` (dev-only) | Qt/PySide6/`ui`/`data` (05/03), `sync_backend` server + `logic/share_token.py` (03), render-perf strategy (10), tests (04/06), Nginx/CI/commits (09), docs (08) |

> **Phase-13 on-demand addition (T13E-G01, `[[generate-assets-on-demand]]`).** AGT-11 was
> generated by The Metaprompter to fill the Slice-13E web/JS roster gap — the vanilla
> `web_viewer/` frontend MUST NOT be misassigned to AGT-05 (Qt). It is Qt-free (ADR-0035 §2),
> view-only (ADR-0036 §3, emits no `update` frame), and consumes pure `logic/` seams
> read-only. Governed by `check_layering --root .` (the `WEB_PKG` rule).

## Per-Agent Capability Skills (Phase 3 v4.1 delta — 25 new, `.claude/skills/<name>/SKILL.md`)

Owned via each agent's frontmatter/body (`Skill` tool) and invoked by that agent. Names are
kebab-case with no agent-id prefix (portable/extensible to roadmap Phases 5–12, Dossier §6.2).

| Owning agent | Owned capability skills |
|--------------|-------------------------|
| AGT-01 Architecture | `layer-audit`, `adr-author`, `interface-contract` (+ SDD `sdd-plan`/`sdd-tasks`/`sdd-analyze`) |
| AGT-02 Requirements | `story-map`, `traceability-matrix` (+ SDD `sdd-specify`/`sdd-clarify`) |
| AGT-03 Python Dev | `logic-scaffold`, `reversible-op`, `numpy-buffer-ops` |
| AGT-04 Python Tester | `pytest-scaffold`, `hypothesis-strategy` |
| AGT-05 UI Expert | `widget-scaffold`, `qss-theming`, `canvas-view`, `colour-hub` |
| AGT-06 QA Expert | `pytest-qt-harness`, `a11y-audit` (+ SDD `sdd-checklist`) |
| AGT-07 Localisation | `string-extract`, `ts-qm-build` |
| AGT-08 Documenter | `changelog`, `mkdocs-site` |
| AGT-09 GitHub/DevOps | `ci-author`, `repo-provision`, `release` |
| AGT-10 Rendering & Performance | `frame-profile`, `render-strategy` |
| AGT-11 Web Client | `web-viewer` |

**Tool-owner context (not a domain agent):** AGT-00 = the orchestration tool-context;
owns file_lock, hook_dispatch_record, schema_validate — declared in
`.claude/agents/orchestrator.md` OWNED TOOLS section (Build Manifest Open Item 1 resolution).

## Usage by The Recommender

1. Existing agent fulfills fully? → map to it.
2. Fulfills partially? → map + ASSET REQUEST to The Metaprompter for the gap.
3. Needs external information? → RESEARCH REQUEST to The Researcher.
4. Needs ≥ threshold files? → GATHERING REQUEST to The Gleaner.
5. No coverage? → ASSET REQUEST to The Metaprompter for a new domain agent/skill.

## Adding Domain Agents

When a domain agent is created in Phase 3, add a row (same columns as the mandatory
rows) before finalizing that agent's asset.
