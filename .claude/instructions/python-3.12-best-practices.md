INSTRUCTION: python-3.12-best-practices
================================================================================

TARGET:
  The coding agents that write or modify Python 3.12 code — AGT-03 (logic/data),
  AGT-05 (ui), AGT-04/AGT-06 (tests) — loaded just-in-time when they touch Python.

PURPOSE:
  Enforce idiomatic, maintainable, secure Python 3.12 conventions so generated code
  is consistent regardless of which agent or session produced it.

## Principles Applied

Inherited:
- P1 — Source-of-Truth Grounding (every directive traces to PEP/tool docs via Researcher)
- P2 — Full Determinism (formatter/linter/type-checker settle style deterministically)
- P3 — Systematicity (grouped directive structure)
- P4 — Consistency (one Python standard for the whole codebase)
- P6 — Self-Containment (agents cite this; do not restate PEP text)
- P7 — Reference Hygiene (cites real tools + PEPs)
- P9 — Role Separation (TARGET names the coding agents)
- P12 — Maximal-Effort Completeness (all six directive groups covered; extensible)
- P13 — Token Economy (directives, not tutorials)

Custom: (none)

DIRECTIVES (grouped):
  - Idiomatic conventions: follow PEP 8 (layout, naming) enforced by Black + isort +
    flake8; PEP 257 docstrings on every public module/class/function; PEP 484 type hints
    on all public signatures (from __future__ import annotations where helpful). Prefer
    dataclasses / NamedTuple for value objects, f-strings for formatting, pathlib.Path for
    paths, context managers for resources, comprehensions over manual loops when readable,
    enum.Enum for closed sets. Avoid mutable default arguments and bare except.
  - Project structure & layout: package pixelart_creator/ with ui/, logic/, data/
    subpackages (S11); one public responsibility per module; numeric constants only in
    logic/constants.py (S12); no circular imports (check_cycles). Keep __init__.py thin.
  - Testing: pytest; deterministic tests (see pytest-best-practices); property tests with
    Hypothesis for pure logic; coverage ≥90/80 (coverage_gate).
  - Security: validate all external/file input (.pixproj JSON) before use; never eval/exec
    untrusted content; use json (not pickle) for project files; construct paths with
    pathlib/os.path, never hardcoded separators (path_portability_check); no secrets in code.
  - Performance: prefer built-in/stdlib and vectorised NumPy over Python-level loops on pixel
    buffers; avoid premature micro-optimisation; measure before optimising (perf_profile owns
    render timing); reuse buffers rather than reallocating the 8K RGBA array (F7).
  - Tooling: format `black . && isort .`; lint `flake8`; type `mypy pixelart_creator`
    (strict for logic/ and data/); run `pytest`. These are the constitution's code-quality gates.

CONSTRAINTS:
  - Never commit code that fails black/isort/flake8/mypy.
  - Never put Qt imports in logic/ or data/ (S11) — that is an architecture violation.
  - Never introduce a magic number outside logic/constants.py (S12).

EXAMPLES:
  Positive (do this):
    Input:  a reversible fill operation in logic/.
    Output: def fill(state: CanvasState, region: Region, color: RGBA) -> CanvasState:
                """Return a new state with `region` filled `color` (immutable)."""
            — typed, docstringed, immutable/reversible, zero Qt.

  Negative (do not do this):
    Input:  def fill(state, region, color=[]):  # mutable default, no types
    Output: WRONG — mutable default argument (shared across calls), missing type hints and
            docstring, violates PEP 8/257/484 and the code-quality gate.

SOURCES:
  - Official documentation (grounded via The Researcher): PEP 8, PEP 257, PEP 484;
    Black, isort, flake8, mypy official docs; Python 3.12 stdlib docs.
  - User requirements: Dossier §1 (S8,S11,S12,S13), §6.8 (python-3.12-best-practices).
  - Inner assets: asset-templates.md §Instruction (Best-Practices variant),
    spec-driven-development.md §4, principles.md §3 (instruction row).
