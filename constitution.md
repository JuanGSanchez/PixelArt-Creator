# PixelArt Creator — Project Constitution

> The governing SDD artifact. Every downstream phase — `specify`, `clarify`,
> `plan`, `tasks`, `analyze`, `implement`, `checklist` — and every produced
> artifact (spec, plan, tasks, code, tests, docs, commits) is checked against
> the articles below. Conflicts resolve **up** to this constitution, never
> around it (Article VIII / C1).

| Field | Value |
| --- | --- |
| Version | v1.0 |
| Date | 2026-07-01 |
| Author | Claude |
| Memory root | repo root (`D:\Documentos\GitHub\PixelArt-Creator`) — no `.specify/`, no `CLAUDE.md` |
| Governs | all SDD phases + all coding/testing/docs/commit agents |
| Inherits | orchestrator CONVENTIONS (single source of naming, thresholds, architecture, numerics, coverage, commit rules) — this document must not contradict it |

This constitution is **self-contained**: it carries its own enforceable gates.
Downstream agents cite an article; they do not restate or re-invent its rule.

---

## Article I — Architecture: Three-Layer Purity

**Realises:** S11 · **Enforced by:** `check_layering`, `check_cycles`, the
`layer-guard` hook.

1. All product code lives in exactly one of three layers:
   - `ui/` — PySide6 / Qt6 presentation and Qt wiring.
   - `logic/` — pure Python domain logic. **Zero Qt imports.**
   - `data/` — I/O and persistence (`.pixproj`, assets). **Zero Qt imports.**
2. The **only** Qt-dependent file permitted outside `ui/` is `ui/commands.py`
   (QUndoCommand wrappers). No other module under `logic/` or `data/` may import
   PySide6/Qt for any reason ("convenience" included).
3. Dependency direction is one-way: `ui/` may import `logic/` and `data/`;
   `logic/` and `data/` never import `ui/`. No import cycles.
4. **Gate:** `python scripts/check_layering.py` and
   `python scripts/check_cycles.py` MUST both exit `0`. A non-zero exit is a
   blocking violation; the offending file is moved/refactored — the gate is not
   weakened. Script exit `2` (error) is treated as unresolved → BLOCKED, never
   as clean.

---

## Article II — Numerics: Single Source of Constants

**Realises:** S12 · **Enforced by:** review + `logic/constants.py` as sole home.

1. Every numeric tuning value is defined once in `pixelart_creator/logic/constants.py`
   and imported by name. No magic numbers appear in `ui/`, `logic/`, `data/`,
   or tests.
2. The canonical constants and their values are:

   | Constant | Value |
   | --- | --- |
   | `MAX_CANVAS_WIDTH` | `7680` |
   | `MAX_CANVAS_HEIGHT` | `4320` |
   | `TILE_SIZE` | `64` |
   | `TILE_BUFFER` | `1` |
   | `PARALLAX_FACTOR` | `30.0` |
   | `SCALE_FACTOR` | `0.15` |
   | `FPS_TARGET` | `60` |
   | `FRAME_BUDGET_MS` | `16` |

3. A new tuning value is added to `constants.py` (with a source citation), never
   inlined at the call site. Changing a value is a one-place edit.

---

## Article III — Code Quality: Formatted, Linted, Typed

**Realises:** §6.7 (code-quality dimension), S8 · **Enforced by:** pre-flight
(local, before commit) **and** CI.

1. All Python is formatted with **Black** and **isort**, passes **flake8**, and
   type-checks under **mypy** (strict for `logic/` and `data/`).
2. **Gate:** a lint, format, or type error blocks the commit locally and fails
   CI. No commit merges with a red quality gate.
3. Naming follows CONVENTIONS: modules `snake_case`; widget classes `PascalCase`
   + suffix (`_Widget` / `_View` / `_Panel` / `_Dialog`); constants
   `UPPER_SNAKE_CASE`; test modules `test_<module>.py`.
4. Every module and public callable carries a PEP 257 docstring; signatures are
   typed per PEP 484.

---

## Article IV — Testing: Coverage, Headless, One-Per-Criterion

**Realises:** S13 · **Enforced by:** `pytest`, `coverage_gate`, CI.

1. Test stack: **pytest + pytest-qt + pytest-cov + Hypothesis**.
2. Tests run **headless** with `QT_QPA_PLATFORM=offscreen`, deterministically and
   portably, identically in CI and locally.
3. **Coverage gate:** per-package **≥90 % line / ≥80 % branch**, enforced by
   `coverage_gate` in CI. Below threshold is a blocking failure.
4. There is **one test per acceptance criterion**, and a **regression test per
   fix** (added with the fix, asserting the prior failure cannot recur).

---

## Article V — UX: Accessibility, Internationalisation, Both Themes

**Realises:** §6.7 (UX dimension), F5/F6 · **Enforced by:** `string_audit_check`,
`a11y-audit`, pytest-qt theme tests.

1. Interactive widgets expose accessible names/descriptions, are reachable by
   keyboard, and show a visible focus indicator.
2. Every user-visible string is wrapped in `tr()` / `translate()`; hand-built
   widgets override `changeEvent()` and re-set text on `QEvent.LanguageChange`.
3. The UI is **correct in both light and dark themes**; colours are defined once
   by role (never hard-coded per widget) and both themes are test-verified.
4. **Gate:** an unwrapped user-visible string (per `string_audit_check`) or a
   theme/a11y regression is a blocking finding.

---

## Article VI — Performance: 60 fps / 16 ms on the 8K Grid

**Realises:** §6.7 (performance dimension), S1/S12 · **Enforced by:**
`scripts/perf_profile.py`.

1. Rendering the 8K grid (7680 × 4320) holds `FPS_TARGET = 60`, i.e. per-frame
   render time ≤ `FRAME_BUDGET_MS = 16`.
2. Verified headless by `perf_profile`. An over-budget measurement is a blocking
   finding that produces an AGT-10 optimisation directive (culling / dirty-rect /
   viewport / scene-rect tuning) — not a relaxation of the budget.
3. The resident pixel buffer is never culled; only Qt rendering is culled.

---

## Article VII — Security: Validated Input, Portable Paths, No Secrets

**Realises:** §6.7 (security dimension), S7 (`.pixproj` JSON) · **Enforced by:**
`path_portability_check`, review.

1. All `.pixproj` (JSON) input is validated and size/bounds-checked before use.
   File content is **never** passed to `eval`/`exec`; parsing is defensive
   (reject malformed, out-of-bounds, or oversized documents).
2. File paths are constructed portably (`pathlib` / `os.path.join`; no hardcoded
   separators). Verified by `path_portability_check`.
3. **No secrets** are committed to the repository.

---

## Article VIII — SDD Gate Law (Constitution Supremacy)

**Realises:** S16, C1 · **Enforced by:** `sdd-analyze`, phase gates.

1. **No implement before analyze passes.** `sdd-analyze` must return **zero
   unresolved cross-artifact findings** before any implementation is dispatched.
   The gate defaults to *closed*.
2. Each SDD phase begins only after the prior artifact exists and is approved:
   `constitution` → `specify` → `clarify` → `plan` → `tasks` → `analyze` →
   `implement` → `checklist`.
3. **Supremacy (C1):** any spec/plan/tasks/code decision conflicting with an
   article here is invalid. The **artifact** is changed to conform — the
   constitution is not amended to resolve a downstream conflict, and no agent
   weakens a gate to make its own output pass.

---

## Article IX — Commits: Conventional, REQ-Tagged, Gate-Green

**Realises:** §3 CONVENTIONS, AGT-09 ownership · **Enforced by:** AGT-09, CI.

1. Commits follow **Conventional Commits** (`feat` / `fix` / `docs` / `refactor`
   / `test` / …) and carry the governing **REQ-ID(s)** in the message.
2. Each commit leaves the gate **green**: quality (Art. III), tests + coverage
   (Art. IV), layering (Art. I), and the SDD gate (Art. VIII) all pass.
3. Commit/CI/repo authorship is owned by AGT-09; this constitution does not
   perform git actions.

---

## Article X — REQ-ID Scheme and Traceability

**Realises:** §3 traceability, S16 · **Enforced by:** `traceability-matrix`,
`sdd-analyze`.

1. Requirement identifiers follow the scheme
   **`REQ-P<phase>-<LAYER>-<NNN>`** — e.g. `REQ-P1-LOGIC-001`, where `<phase>`
   is the roadmap phase, `<LAYER>` ∈ {`UI`, `LOGIC`, `DATA`}, and `<NNN>` is a
   zero-padded sequence.
2. Every REQ-ID traces back to a dossier `S-id` (S1–S19) and forward to at least
   one acceptance criterion and one passing test. An untraced requirement is an
   `sdd-analyze` finding.

---

## Article XI — Extensibility

**Realises:** S6, P12.

1. The roster and these gates extend cleanly to roadmap Phases 5–12 (animation,
   tilemaps, export, automation, visual aids, cloud/collab, team/asset
   management, performance). Adding a capability adds assets without rewriting or
   weakening any article above.

---

### Amendment procedure

This constitution is versioned. Amendments bump the version, update the date, and
record the change author. Downstream conflicts are **never** resolved by
amendment (Art. VIII/C1); amendment is reserved for genuine governing-policy
changes, made by AGT-01 under owner context.

**Sources:** Dossier §1 (S1–S19: S6, S7, S8, S11, S12, S13, S16), §3
(CONVENTIONS), §6.7 (governing dimensions); orchestrator CONVENTIONS field;
`.claude/instructions/project-constitution.md`; `spec-driven-development.md`
§2–§3.
