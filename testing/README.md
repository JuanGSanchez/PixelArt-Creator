# testing/

This product repository's own test suite. It tests PRODUCT code only - the
orchestration system's scripting is tested by the container's `testing/`
suite, and the two never reach into each other (`system-testing.md` §1).

Run it:

    ./run          # the runner, then the cleanup - always, even on a Ctrl-C
    run.cmd        # the same, on Windows

Both wrappers run the suite under the same marker filter
`.github/workflows/ci.yml`'s default quality-gate job uses (deselecting
`slow`, `gpu`, `cloud_live`, `assistant_live` and `integration`), then leave
a fresh `testing/coverage.json` measuring `pixelart_creator`, `sync_backend`
and `web_viewer` - the artefact `testing/coverage_viz.py` (installed
separately) reads for the Coverage frame.

## Why there is no `testing/pytest.ini`

The frozen orchestrator-design template assumes a self-contained
`testing/pytest.ini`. This repository's pytest configuration - `testpaths`
(`tests`, `web_viewer/tests`), the five deselectable markers, `addopts` -
already lives in `pyproject.toml`'s `[tool.pytest.ini_options]`. Restating it
in a second file would give that configuration a second place to drift, so
`run` / `run.cmd` point pytest's `-c` at the repository's own
`pyproject.toml` instead. One declaration; the wrapper reads it rather than
copying it.

## Overrides

    ./run                                # the whole suite, CI marker filter
    ./run tests/logic/test_color.py      # anything; args pass to pytest
    KEEP_TEMP=1 ./run                    # skip the reclaim, inspect a run
    NO_COVERAGE=1 ./run                  # skip the measurement, run plain
    MARKEXPR="not slow" ./run            # a different -m expression
    COVERAGE_FILE=/other/.coverage ./run # measure into a different data file

The Windows forms are the same with `set VAR=value & run.cmd`.

`--basetemp` is always placed under the configured temp root
(`$ORCH_TEST_TMP`, falling back to `.tmp/` beside the repository - never a
literal drive letter baked into either wrapper) so a killed run's scratch
files are reclaimable the same way `cleanup.py` reclaims everything else it
owns.

## Which worktree's code gets imported

Both wrappers put this repository's own root on `PYTHONPATH`, ahead of
anything else - including the caller's own `PYTHONPATH`, which is preserved
and appended after it, never discarded. This matters on a machine that
checks out more than one worktree of the same repository side by side (a
`main/` checkout plus one or more `feat-`/`fix-` branch worktrees) and also
carries a machine-wide *editable* install of the package pinned to exactly
one of them: without this, every child process whose current directory is
not this worktree - every `pytest-xdist` worker that changes directory, and
any subprocess a test spawns elsewhere - falls back to that machine-wide
install and silently imports `pixelart_creator`, `sync_backend` or
`web_viewer` from a **different worktree's checkout**, not this one. A run
was once measured pulling dozens of files into its own coverage report from
a sibling worktree this way, and nothing about the run looked wrong.

Running a bare `pytest` from this worktree's root does **not** carry the
same guarantee: it inherits whatever `PYTHONPATH` (if any) happens to be set
in the calling shell, so a subprocess test that changes directory can still
resolve the wrong worktree's code. Use `./run` / `run.cmd` - or export
`PYTHONPATH` to include this repository's root yourself - for any invocation
where that matters.

`testing.json` is the machine-readable contract: which runner, which
verbosity flags, which cleanup entry point, which wrappers, which
`source_roots` get measured, and which name pattern marks a test as unit /
integration. `scripts/check_testing.py check <repo> --profile product` holds
this folder to it.

Everything a run generates lives under `<root>/<project>-tests/run-<id>/`
(`CI-<project>` in CI) and is reclaimed by `cleanup.py`. The one exception is
the coverage measurement itself (`testing/coverage.json`, `testing/.coverage`
and its `.coverage.*` fragments) - those are deliberately kept beside this
script, not under the temp root, because they are the persistent artefact the
Coverage frame reads between runs, not scratch (`product-testing.md` §2).
Both are gitignored: they change on every run, and a clone that has never run
the suite has measured nothing, which is what the frame then says.
