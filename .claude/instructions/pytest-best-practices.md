INSTRUCTION: pytest-best-practices
================================================================================

TARGET:
  The agents that write or run tests — AGT-04 (logic/data), AGT-06 (ui/a11y) — and
  any coding agent running the local pre-flight suite; loaded just-in-time.

PURPOSE:
  Enforce deterministic, portable, machine-agnostic tests so the suite passes
  identically on a developer machine and on a clean CI runner.

## Principles Applied

Inherited:
- P1 — Source-of-Truth Grounding (directives trace to pytest/pytest-qt/cov/Hypothesis docs)
- P2 — Full Determinism (the whole point: no flaky, host-dependent tests)
- P3 — Systematicity (grouped directive structure)
- P4 — Consistency (one testing standard)
- P6 — Self-Containment (agents cite this; do not restate pytest docs)
- P7 — Reference Hygiene (cites real plugins + markers)
- P9 — Role Separation (TARGET names the test agents)
- P12 — Maximal-Effort Completeness (all six groups; coverage + determinism + portability)
- P13 — Token Economy

Custom: (none)

DIRECTIVES (grouped):
  - Idiomatic conventions: files test_<module>.py; test functions test_<behaviour>; use
    fixtures for setup/teardown; parametrize with @pytest.mark.parametrize; assert on values,
    not on prose. Use Hypothesis (@given) for pure-logic invariants (compaction, harmony math).
  - Project structure & layout: tests/logic and tests/data (no Qt import — AGT-04); tests/ui
    (pytest-qt — AGT-06); a conftest.py that forces headless (sets QT_QPA_PLATFORM=offscreen)
    and provides shared fixtures; keep test data small and in-repo.
  - Testing (determinism & portability): NO wall-clock- or CPU-count-dependent assertions;
    seed any randomness (Hypothesis derandomize or a fixed seed) — perf timings are NOT unit
    assertions (they belong to perf_profile). For Qt, connect the signal observer
    (qtbot.waitSignal / waitUntil) BEFORE the action that emits it. Force headless/offscreen.
    Build paths portably (tmp_path fixture / pathlib), never hardcoded separators.
  - Security: never load untrusted fixtures via pickle/eval; validate any file fixture; do not
    reach the network in unit tests (mark and deselect integration tests that must).
  - Performance: gate long/heavy or resource-sensitive tests behind a deselectable marker
    (e.g. @pytest.mark.slow / @pytest.mark.gpu) so the default gate stays fast and
    machine-agnostic; the default CI run deselects them.
  - Tooling: run `pytest --cov=pixelart_creator --cov-branch --cov-report=xml` then
    `python scripts/coverage_gate.py` (≥90 line/≥80 branch, S13). Markers registered in
    pyproject.toml [tool.pytest.ini_options].

CONSTRAINTS:
  - Never write a test whose result depends on timing, CPU count, locale, path separator, or
    a display server.
  - Never assert a frame-rate/perf number in a unit test — that is perf_profile's job.
  - Never let coverage regress below the gate to "get green".

EXAMPLES:
  Positive (do this):
    Input:  testing a signal-emitting widget action.
    Output: with qtbot.waitSignal(widget.colorPicked, timeout=1000):
                qtbot.mouseClick(widget, Qt.RightButton)
            — observer connected before the click; headless; deterministic.

  Negative (do not do this):
    Input:  qtbot.mouseClick(widget, Qt.RightButton); assert widget.last_signal is not None
    Output: WRONG — races the signal (may assert before it fires) and depends on timing.
            Use waitSignal to connect the observer before the action.

SOURCES:
  - Official documentation (grounded via The Researcher, F11): pytest, pytest-qt, pytest-cov,
    Hypothesis docs; Qt offscreen platform.
  - User requirements: Dossier §1 (S8,S13), §6.8 (pytest-best-practices), §6.7 (headless harness).
  - Inner assets: asset-templates.md §Instruction (Best-Practices variant),
    spec-driven-development.md §4–§5, principles.md §3 (instruction row).
