INSTRUCTION: Project Constitution (PixelArt Creator)
================================================================================

TARGET:
  AGT-01 Architecture (authors and maintains constitution.md at the repo memory
  root) and, transitively, every SDD phase and coding agent — the constitution
  governs specify, clarify, plan, tasks, analyze, implement, and checklist.

PURPOSE:
  Establish the project's non-negotiable governing principles (the five dimensions
  code quality, testing, UX, performance, security) that every later SDD phase and
  every produced artifact must comply with. Conflicts resolve UP to this
  constitution, never around it.

## Principles Applied

Inherited:
- P1 — Source-of-Truth Grounding (dimensions grounded in S8–S13, Qt/PEP standards via Researcher)
- P2 — Full Determinism (each dimension states a testable gate + default)
- P3 — Systematicity (ordered governing dimensions; each SDD phase checks against them)
- P4 — Consistency (single governing source; inherits orchestrator CONVENTIONS)
- P6 — Self-Containment (the constitution carries its gates; agents cite, not restate)
- P7 — Reference Hygiene (cites real gates: best-practices instructions, scripts)
- P9 — Role Separation (TARGET = AGT-01; it authors constitution.md, others obey)
- P12 — Maximal-Effort Completeness (all five dimensions covered, extensible to Phases 5–12)
- P13 — Token Economy (gates, not prose)

Custom:
- C1 — Constitution supremacy: any spec/plan/tasks/code decision conflicting with a
  gate below is invalid; change the artifact, not the constitution. (Rationale:
  spec-driven-development.md §2.)

DIRECTIVES:
  1. Code quality gate. All Python is formatted with Black and isort, passes flake8,
     and type-checks under mypy (strict for logic/ and data/). No commit merges with a
     lint or type error. Naming per orchestrator CONVENTIONS (modules snake_case; widget
     classes PascalCase + _Widget/_View/_Panel/_Dialog; constants UPPER_SNAKE_CASE; tests
     test_<module>.py). Details: python-3.12-best-practices, pyside6-qt6-best-practices.
  2. Architecture gate. Three layers — ui/ (PySide6), logic/ (pure Python, zero Qt),
     data/ (I/O, zero Qt); the only Qt file outside ui/ is ui/commands.py (S11). Enforced
     by check_layering + check_cycles (must exit 0). Numerics only from logic/constants.py
     (S12); no magic numbers elsewhere.
  3. Testing gate. pytest + pytest-qt + pytest-cov + Hypothesis; per-package coverage
     ≥90% line / ≥80% branch (S13), enforced by coverage_gate in CI. Tests run headless
     (QT_QPA_PLATFORM=offscreen). One test per acceptance criterion; a regression test per
     fix. Details: pytest-best-practices.
  4. UX gate. Keyboard accessibility and screen-reader names on interactive widgets; both
     light and dark themes verified; every user-visible string wrapped in tr() and audited
     by string_audit_check; hand-built widgets handle QEvent.LanguageChange (F5/F6).
  5. Performance gate. The 8K canvas holds FPS_TARGET=60 / FRAME_BUDGET_MS=16; verified by
     perf_profile headless. Over-budget is a blocking finding that produces an AGT-10 directive.
  6. Security gate. All .pixproj (JSON) input is validated and size/among-bounds-checked
     before use; no eval/exec of file content; file paths constructed portably (no hardcoded
     separators — path_portability_check); no secrets in the repo.
  7. Extensibility. The roster and constitution extend cleanly to roadmap Phases 5–12
     (animation, tilemaps, export, automation, cloud/collab, performance) — adding a
     capability adds assets without rewriting these gates (S6, P12).

CONSTRAINTS:
  - No SDD phase may proceed while it violates a gate above.
  - No agent may weaken a gate to make its own output pass; it fixes the output.
  - The constitution is not amended to resolve a downstream conflict (C1).

EXAMPLES:
  Positive (do this):
    Input:  plan.md places colour-harmony math in logic/color_harmony.py (zero Qt).
    Output: PASS — architecture gate satisfied; check_layering exits 0.

  Negative (do not do this):
    Input:  plan.md imports PySide6 QColor inside logic/color_harmony.py "for convenience".
    Output: REJECT — violates the architecture gate (logic/ is zero-Qt, S11). Qt colour
            conversion belongs in ui/; logic/ works on plain RGB/HSV tuples. Wrong because
            it breaks layer purity and check_layering fails.

SOURCES:
  - User requirements: Dossier §1 (S8–S13, S16), §6.7 (constitution + governing dimensions).
  - Inner assets: asset-templates.md §Instruction, spec-driven-development.md §2–§3,
    principles.md §3 (instruction row); orchestrator CONVENTIONS.
  - Official documentation (grounded via The Researcher, F10): GitHub Spec Kit constitution
    phase; PEP 8/257/484; Qt for Python a11y/i18n; pytest-qt headless.
