"""Start coverage in EVERY interpreter this suite spawns (frozen copy).

WHY THIS FILE EXISTS. This suite drives the system under test the way its
users do: through its CLI, as a child process (`python -B <script>`). A plain
`pytest --cov` measures the process pytest runs in, so it sees the harness and
a few pure helpers and reports near-zero for every script the suite actually
exercises — a Coverage frame that says 3% about code the suite covers
thoroughly is worse than no frame at all, because somebody will believe it.

`coverage.process_startup()` is the hook `coverage.py` provides for exactly
this: with `COVERAGE_PROCESS_START` pointing at a config file, a child that
imports `sitecustomize` starts measuring itself and writes its own
`.coverage.<host>.<pid>.<random>` fragment, which `coverage combine` folds
back in. Python imports `sitecustomize` automatically from `sys.path`, and the
runner puts this directory there — so no child has to know it is being
measured, and no test has to be written differently.

IT IS INERT UNLESS ASKED. Without `COVERAGE_PROCESS_START` in the environment
`process_startup()` returns immediately, so an ordinary `python` invocation
that happens to find this file on its path pays one import and nothing else.
Without `coverage` installed at all it does not even pay that.

NEVER RAISES. A measurement harness that can break the thing it measures is
not a harness. Every failure here is swallowed on purpose: the suite runs, the
Coverage frame reports that nothing was measured, and that is a true statement
about a run that happened rather than a run that did not.
"""

try:                                     # pragma: no cover - the guard IS the
    import coverage                      # behaviour, and it runs before any
    coverage.process_startup()           # measurement could observe it
except Exception:                        # noqa: BLE001 - see NEVER RAISES
    pass
