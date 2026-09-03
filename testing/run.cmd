@echo off
REM run.cmd - execute the suite under coverage, then ALWAYS reclaim what it
REM            generated (adapted from a shared frozen template - see
REM            WHY THIS COPY DIVERGES below).
REM
REM The Windows half of the cleanup contract's outer ring; see `run` for the
REM POSIX one and cleanup.py for the reasoning. cmd.exe has no trap, so the
REM cleanup call simply follows the runner unconditionally and the runner's
REM exit code is carried across it by hand - a green suite whose temp files
REM resisted deletion is still a green suite.
REM
REM   run.cmd                              the whole suite, under CI markers
REM   run.cmd tests\logic\test_color.py    anything; args pass to pytest
REM   set KEEP_TEMP=1 & run.cmd            skip the reclaim to inspect output
REM   set NO_COVERAGE=1 & run.cmd          skip the measurement, run plain
REM   set MARKEXPR=not slow & run.cmd      override the default -m expression
REM   set COVERAGE_FILE=X & run.cmd        measure into a different data file
REM
REM WHY THERE ARE NO PARENTHESISED BLOCKS AROUND A PYTEST CALL. cmd.exe
REM expands %VAR% when it PARSES a block, not when it runs the lines inside
REM it. An earlier version captured the verdict as `set "STATUS=%ERRORLEVEL%"`
REM inside `if (...)`, so STATUS took the errorlevel from BEFORE pytest ran -
REM always 0 - and this wrapper exited 0 for a suite that failed. A green
REM exit for a red suite is the one thing a test runner must never produce.
REM `goto` labels keep every ERRORLEVEL read a statement of its own, expanded
REM when it runs. Delayed expansion would fix it too, at the price of making
REM `!` a metacharacter in every argument the caller passes through to pytest.
REM
REM WHY COVERAGE IS WIRED HERE AND NOT IN pytest.ini. This suite drives the
REM system under test through its real CLI, as a CHILD PROCESS. A plain
REM `pytest --cov` measures the process pytest runs in and reports near-zero
REM for every script the suite actually exercises. Subprocess measurement
REM needs three things that belong to the RUNNER rather than to a config file:
REM COVERAGE_PROCESS_START in the environment, this directory on PYTHONPATH so
REM every child imports sitecustomize.py, and a `combine` afterwards to fold
REM the per-process fragments back together.
REM
REM IT DEGRADES OUT LOUD. Without `coverage` installed the suite still runs;
REM the runner says so and the Coverage frame reports that nothing has been
REM measured in this clone, which is true.
REM
REM WHY THIS COPY DIVERGES FROM THE FROZEN TEMPLATE. The template assumes a
REM self-contained testing\pytest.ini. This product's pytest configuration -
REM testpaths (tests, web_viewer\tests), the five deselectable markers,
REM addopts - lives in the repository's own pyproject.toml
REM [tool.pytest.ini_options]. A second, testing\-local pytest.ini would
REM duplicate that configuration and give it a second place to drift, which
REM is exactly the class of defect this repository has already been bitten
REM by once. So, in place of the frozen -c "%HERE%pytest.ini", both pytest
REM invocations below point -c at the repository's own pyproject.toml - ONE
REM source of truth, read, not restated - and this wrapper additionally
REM supplies what a config file cannot decide for it: the CI marker filter
REM (MARKEXPR, same expression ci.yml's main pytest step uses), --basetemp
REM under the configured temp root (ORCH_TEST_TMP, falling back to a .tmp\
REM beside the repository - never a literal drive letter baked into this
REM file), and --source for `coverage run` read from testing.json's own
REM source_roots rather than restated here.
REM
REM WHY THE REPOSITORY ROOT IS ALSO PREPENDED TO PYTHONPATH (on top of the
REM frozen template's own %HERE%, which stays so every child still imports
REM sitecustomize.py). This checkout is one of several SIBLING WORKTREES of
REM the same repository, and this machine also carries a machine-wide
REM EDITABLE INSTALL of the package (an __editable___*_finder.py under
REM site-packages) pinned to exactly one of those siblings via
REM sys.meta_path. That finder is APPENDED to sys.meta_path, so the stdlib
REM PathFinder - which honours PYTHONPATH - is still consulted first; a
REM child process whose cwd is not this worktree (every pytest-xdist worker
REM that changes directory, and any subprocess a test spawns elsewhere)
REM would otherwise silently import pixelart_creator/sync_backend/web_viewer
REM from THAT OTHER WORKTREE instead of this one, and no test would notice -
REM a full run was measured pulling files from outside this checkout,
REM several dozen of them from a sibling's pixelart_creator\ tree. Putting
REM REPO_ROOT first on PYTHONPATH makes every child resolve the three
REM packages from THIS checkout regardless of its cwd or the machine-wide
REM install. The caller's own PYTHONPATH is preserved, appended after both
REM entries, never discarded.
setlocal
set "HERE=%~dp0"
set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"
if not defined PYTHON set "PYTHON=python"
set "PYPROJECT=%REPO_ROOT%\pyproject.toml"

if not defined ORCH_TEST_TMP (
    set "TEMP_ROOT=%REPO_ROOT%\.tmp"
) else (
    set "TEMP_ROOT=%ORCH_TEST_TMP%"
)
REM The scope MUST be the checkout-folder basename, not testing.json's
REM "project" field: this repository's frozen testing\cleanup.py
REM derives its OWN sweep scope the same way -- CONTAINER_ROOT =
REM TESTING_DIR.parent (cleanup.py line 76), PROJECT = CONTAINER_ROOT.name
REM (line 92), used to build "scope" in scope_name() (line 428).
REM cleanup.py has no --scope flag to override that. Each checkout runs
REM its OWN cleanup.py, which derives its OWN folder name and reclaims
REM its OWN debris, so the runner and the reclaim must derive the SAME
REM scope from the SAME place -- reading a different source here (e.g.
REM the manifest's "project" field) would make the runner write to one
REM directory while the trap's cleanup.py call sweeps another, so it
REM fires and reclaims nothing.
for %%I in ("%REPO_ROOT%") do set "PROJECT_NAME=%%~nI"
set "SCOPE=%PROJECT_NAME%-tests"
if /I "%CI%"=="true" set "SCOPE=CI-%PROJECT_NAME%"
if /I "%CI%"=="1" set "SCOPE=CI-%PROJECT_NAME%"
if /I "%ORCH_TEST_CI%"=="1" set "SCOPE=CI-%PROJECT_NAME%"
if /I "%ORCH_TEST_CI%"=="true" set "SCOPE=CI-%PROJECT_NAME%"
REM mkdir on cmd.exe creates intermediate directories by default, so
REM this is the direct equivalent of the POSIX side's "mkdir -p" -- it
REM must run BEFORE pytest, whose own basetemp creation is the final
REM component only and fails if the parent is missing.
if not exist "%TEMP_ROOT%\%SCOPE%" mkdir "%TEMP_ROOT%\%SCOPE%"
set "BASETEMP=%TEMP_ROOT%\%SCOPE%\pytest-%RANDOM%"

if not defined MARKEXPR set "MARKEXPR=not slow and not gpu and not cloud_live and not assistant_live and not integration"
if not defined COVERAGE_FILE set "COVERAGE_FILE=%HERE%.coverage"

if "%NO_COVERAGE%"=="1" goto :plain
"%PYTHON%" -c "import coverage" >nul 2>&1
if errorlevel 1 goto :nocoverage
goto :measured

:nocoverage
echo run: coverage is not importable - running the suite plain. 1>&2
echo run: the Coverage frame will report that nothing was measured. 1>&2
goto :plain

:measured
set "COVERAGE_PROCESS_START=%HERE%.coveragerc"
if defined PYTHONPATH set "PYTHONPATH=%REPO_ROOT%;%HERE%;%PYTHONPATH%"
if not defined PYTHONPATH set "PYTHONPATH=%REPO_ROOT%;%HERE%"
REM Read source_roots out of testing.json via a redirected scratch file
REM rather than a FOR /F backquoted command: a backquoted command is
REM re-tokenized by cmd before it runs, and the nested double-quoted -c
REM argument does not survive that. The scratch file lives beside this
REM script (never a bare OS temp dir) and is removed immediately after it
REM is read.
set "SOURCE_ROOTS_FILE=%HERE%.source_roots.tmp"
"%PYTHON%" -c "import json;d=json.load(open(r'%HERE%testing.json',encoding='utf-8'));print(','.join(d.get('source_roots') or []))" > "%SOURCE_ROOTS_FILE%" 2>nul
set "SOURCE_ROOTS="
set /p SOURCE_ROOTS=<"%SOURCE_ROOTS_FILE%"
del "%SOURCE_ROOTS_FILE%" >nul 2>&1
if defined SOURCE_ROOTS goto :measured_with_source

"%PYTHON%" -u -m coverage run --rcfile="%HERE%.coveragerc" -m pytest -c "%PYPROJECT%" -p no:cacheprovider --basetemp="%BASETEMP%" -m "%MARKEXPR%" %*
set "STATUS=%ERRORLEVEL%"
goto :after_pytest

:measured_with_source
"%PYTHON%" -u -m coverage run --rcfile="%HERE%.coveragerc" --source="%SOURCE_ROOTS%" -m pytest -c "%PYPROJECT%" -p no:cacheprovider --basetemp="%BASETEMP%" -m "%MARKEXPR%" %*
set "STATUS=%ERRORLEVEL%"

:after_pytest
REM Every child wrote its own fragment; fold them into one and render the
REM artefact the Coverage frame reads. Neither step may change the verdict:
REM a green suite whose measurement could not be written is still green, and
REM a RED one stays red.
"%PYTHON%" -m coverage combine --rcfile="%HERE%.coveragerc" >nul 2>&1
if errorlevel 1 echo run: coverage combine reported a problem 1>&2
"%PYTHON%" -m coverage json --rcfile="%HERE%.coveragerc" -o "%HERE%coverage.json" >nul 2>&1
if errorlevel 1 echo run: coverage json reported a problem 1>&2
goto :reclaim

:plain
"%PYTHON%" -u -m pytest -c "%PYPROJECT%" -p no:cacheprovider --basetemp="%BASETEMP%" -m "%MARKEXPR%" %*
set "STATUS=%ERRORLEVEL%"

:reclaim
if "%KEEP_TEMP%"=="1" goto :kept
"%PYTHON%" "%HERE%cleanup.py"
if errorlevel 1 echo run: cleanup reported a problem 1>&2
goto :done

:kept
echo run: KEEP_TEMP=1 - workspaces left in place 1>&2

:done
exit /b %STATUS%
