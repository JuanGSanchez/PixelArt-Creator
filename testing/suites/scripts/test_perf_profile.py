"""Contract tests for ``scripts/perf_profile.py`` (ADR-0047 tranche 2).

Contract asserted here, taken from the script's own header::

    ENTRYPOINT (tiling, the default mode): python scripts/perf_profile.py
        [--width 7680] [--height 4320] [--tile 64] [--zoom 1.0]
        [--viewport 1920 1080] [--frames 30] [--budget-ms 16.0]
    ENTRYPOINT (composite): python scripts/perf_profile.py --composite
        [--layers 8] [--region-size 16] [--ceiling-ms 200.0] ...
    EXIT CODES: 0 within budget/ceiling -> COMPLETED ; 1 over budget/ceiling
        -> FAILED ; 2 error / PySide6 unavailable (tiling only) -> BLOCKED.

WHAT THIS MODULE COVERS, AND WHAT IT DELIBERATELY DOES NOT (stated per the
follow-up-tranche instruction, not silently omitted):

This is a *measurement* script (its own DETERMINISM NOTE says so): the median/
p95 timings it reports are host-dependent and NOT bit-reproducible. This
module therefore does NOT assert on any specific timing value. What it DOES
assert, and what stays genuinely deterministic run to run, is:

  1. argument handling / input validation (invalid geometry -> exit 2,
     regardless of what the real timing would have been);
  2. the budget/ceiling COMPARISON itself, made deterministic by supplying an
     artificially huge budget (guaranteed ``within``, since a real measured
     duration is always a small positive number of ms) and an artificially
     negative budget (guaranteed ``over``, since a measured duration can never
     be negative) -- the comparison logic is exercised for real, only the
     threshold is rigged so the outcome is not a coin flip on this run's CPU
     load;
  3. the exit-code mapping (0 / 1 / 2) that follows from (2);
  4. the JSON report shape (the field names the header's OUTPUTS section
     promises), asserted on keys/types, never on the numeric magnitude of
     ``median_ms``/``p95_ms``.

Two modes are exercised this way: the default **tiling** mode (needs a
display -- driven headless via ``QT_QPA_PLATFORM=offscreen``, which the
script itself sets via ``os.environ.setdefault`` before importing PySide6,
confirmed by reading the module) and the Qt-FREE **composite** mode (numpy +
``pixelart_creator.logic`` only). If PySide6 is unavailable in the pytest
environment, the tiling-mode tests SKIP with a stated reason (Directive 12:
a test that cannot run must SAY so, never pass silently) rather than being
omitted or asserting a fabricated result.

NOT covered by this module, and said plainly rather than silently skipped:
the ``--tilemap``, ``--tm-cache``, ``--overlay`` and ``--realtime`` modes.
Each is a large, independently-scoped profiling surface (multiple hundred
lines apiece) with its own construction fixtures; covering all of them is out
of this tranche's scope (ADR-0047's remit is "the four remaining gate
scripts", not an exhaustive enumeration of every ``perf_profile.py`` flag).
The tiling and composite modes were chosen because they are the two the
header lists first under ENTRYPOINT, and because between them they prove
both the PySide6/headless path and the Qt-free path can each still report
FAILED (not just COMPLETED) -- the exact property this tranche exists to
establish.

The ``--full-frame`` and ``--viewport-recomposite`` modes ARE covered, added
in a follow-up pass (C-08): their basic invalid-input / huge-vs-negative-
ceiling / exit-code contract (the same shape as the composite-mode pair
above), PLUS a dedicated assertion that each mode's ``ceiling_ms`` in the
JSON report is resolved from the real, imported ``pixelart_creator.logic.
constants`` module -- never a fallback literal. That resolution assertion is
the regression proof for C-08: ``scripts/perf_profile.py`` used to read these
two ceilings (and three others) via ``getattr(_c, "<NAME>", <literal>)``, and
the ``VIEWPORT_RECOMPOSITE_CEILING_MS`` fallback literal (3000) happened to
EQUAL the real shipped constant -- so a constants.py regression that dropped
the attribute would have left the gate passing at a coincidentally-identical
number, Article II silently defeated. The module-missing-attribute half of
that proof (``test_missing_ceiling_constant_is_loud_not_silent``) doctors a
``PYTHONPATH`` shim whose ``pixelart_creator.logic.constants`` is otherwise
complete but missing exactly one required ceiling constant, and asserts the
script now exits 2 with a named, actionable error instead of quietly
computing a fallback-literal-based verdict.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from .conftest import REPO_ROOT, run_script

SCRIPT = "perf_profile.py"


def _pyside6_available() -> bool:
    try:
        import PySide6  # noqa: F401
    except Exception:
        return False
    return True


def _logic_available() -> bool:
    """Composite mode is Qt-free but NOT dependency-free: it imports
    ``pixelart_creator.logic``. The package is editable-installed for the
    default-branch checkout, so a freshly created branch worktree can run this
    suite without it and the script correctly answers exit 2,
    ``logic-unavailable`` -- an environment gap, not a defect. Asserting 0/1
    there turns a stated BLOCKED into a false FAILED.

    PROBED IN A SUBPROCESS WITHOUT THE WORKING DIRECTORY ON ``sys.path``, and
    both halves of that are load-bearing. A plain ``import`` here answers for
    the PYTEST process, where the rootdir is on ``sys.path`` and the package
    always resolves. A subprocess launched with ``-c`` is no better: ``-c``
    prepends the working directory, so the repository's own source tree
    answers. ``run_script`` invokes ``python scripts/<name>.py``, which
    prepends ``scripts/`` INSTEAD -- so the script sees only what is genuinely
    installed. Popping ``sys.path[0]`` reproduces that, and nothing else does.

    Both weaker probes were written and both reported "available" while the
    script under test was still exiting 2.
    """
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.pop(0); import pixelart_creator.logic",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
    )
    return done.returncode == 0


_LOGIC_SKIP = (
    "pixelart_creator.logic not importable in this test environment -- the "
    "composite mode genuinely cannot run here (the script maps this to exit 2, "
    "'logic-unavailable'); SKIP states this rather than reporting an "
    "environment gap as a budget failure (Directive 12)."
)


# --------------------------------------------------------------------------- #
# Deterministic input-validation path (exit 2), needs no PySide6/timing at all.
# --------------------------------------------------------------------------- #
def test_tiling_invalid_geometry_exits_2():
    result = run_script(SCRIPT, ["--width", "0", "--frames", "2"])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "invalid-input"


def test_composite_invalid_layers_exits_2():
    result = run_script(SCRIPT, ["--composite", "--layers", "0", "--frames", "2"])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "invalid-input"


def test_composite_region_larger_than_canvas_exits_2():
    result = run_script(
        SCRIPT,
        [
            "--composite",
            "--width",
            "32",
            "--height",
            "32",
            "--region-size",
            "64",
            "--frames",
            "2",
        ],
    )
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "region-larger-than-canvas"


# --------------------------------------------------------------------------- #
# Composite mode (Qt-FREE): the budget-comparison essential pair, rigged
# deterministic via an absurd ceiling in each direction.
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_composite_huge_ceiling_is_always_within_exits_0():
    result = run_script(
        SCRIPT,
        [
            "--composite",
            "--layers",
            "2",
            "--region-size",
            "4",
            "--width",
            "64",
            "--height",
            "64",
            "--frames",
            "2",
            "--ceiling-ms",
            "1000000000",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["mode"] == "composite"
    assert payload["within_ceiling"] is True
    assert payload["ceiling_ms"] == 1000000000.0
    assert isinstance(payload["median_ms"], float)
    assert isinstance(payload["p95_ms"], float)
    assert payload["frames"] == 2
    assert payload["layers"] == 2
    assert set(payload["scenario"]) == {
        "width",
        "height",
        "layers",
        "region_size",
        "blend_modes",
    }


@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_composite_negative_ceiling_is_always_over_exits_1():
    """A measured duration can never be negative, so a negative ceiling makes
    the FAILED path deterministic without depending on this run's CPU load --
    the essential broken-input half of the pair."""
    result = run_script(
        SCRIPT,
        [
            "--composite",
            "--layers",
            "2",
            "--region-size",
            "4",
            "--width",
            "64",
            "--height",
            "64",
            "--frames",
            "2",
            "--ceiling-ms",
            "-1",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["within_ceiling"] is False
    assert payload["ceiling_ms"] == -1.0


def test_composite_without_the_logic_package_takes_the_documented_exit_2():
    """A companion to the two skipifs above: if the logic package genuinely is
    unavailable, prove the script takes its documented exit-2/'logic-
    unavailable' path rather than the two skipped tests simply going quiet.
    Between them, exactly one of these three runs in any environment."""
    if _logic_available():
        pytest.skip(
            "pixelart_creator.logic IS importable here, so the unavailable "
            "path cannot be exercised without faking it; the two composite "
            "tests above ran instead."
        )
    result = run_script(
        SCRIPT,
        [
            "--composite",
            "--layers",
            "2",
            "--region-size",
            "4",
            "--width",
            "64",
            "--height",
            "64",
            "--frames",
            "2",
            "--ceiling-ms",
            "1000",
        ],
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["error"] == "logic-unavailable"


# --------------------------------------------------------------------------- #
# Tiling mode (default; needs PySide6, driven headless). SKIPs with a stated
# reason if PySide6 is not importable in this environment -- never a silent
# pass, never a false failure for an environment gap this script itself
# documents as EXIT CODE 2 territory when hit for real (unavailable Qt).
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not _pyside6_available(),
    reason=(
        "PySide6 not importable in this test environment -- the tiling mode "
        "genuinely cannot run here (its own header maps this to exit 2, "
        "'pyside6-unavailable'); SKIP states this rather than passing quietly "
        "or asserting a fabricated report (Directive 12)."
    ),
)
def test_tiling_huge_budget_is_always_within_exits_0():
    result = run_script(
        SCRIPT,
        [
            "--width",
            "128",
            "--height",
            "128",
            "--tile",
            "16",
            "--viewport",
            "64",
            "64",
            "--frames",
            "2",
            "--budget-ms",
            "1000000000",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["within_budget"] is True
    assert payload["budget_ms"] == 1000000000.0
    assert isinstance(payload["median_ms"], float)
    assert isinstance(payload["p95_ms"], float)
    assert payload["frames"] == 2
    assert set(payload) == {
        "median_ms",
        "p95_ms",
        "budget_ms",
        "frames",
        "tiles_per_frame",
        "within_budget",
        "scenario",
    }
    assert set(payload["scenario"]) == {
        "width",
        "height",
        "tile",
        "zoom",
        "viewport",
    }


@pytest.mark.skipif(
    not _pyside6_available(),
    reason=(
        "PySide6 not importable in this test environment -- the tiling mode "
        "genuinely cannot run here; SKIP states this rather than passing "
        "quietly (Directive 12)."
    ),
)
def test_tiling_negative_budget_is_always_over_exits_1():
    result = run_script(
        SCRIPT,
        [
            "--width",
            "128",
            "--height",
            "128",
            "--tile",
            "16",
            "--viewport",
            "64",
            "64",
            "--frames",
            "2",
            "--budget-ms",
            "-1",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["within_budget"] is False
    assert payload["budget_ms"] == -1.0


def test_pyside6_availability_is_reported_honestly_if_absent():
    """A companion to the skipif above: if PySide6 genuinely is unavailable,
    prove the SCRIPT ITSELF (not just this test suite) says so via its
    documented exit-2/'pyside6-unavailable' path, rather than the two skipped
    tests above being the only signal. If PySide6 IS available, this test
    documents that fact instead (never a silent no-op either way)."""
    if _pyside6_available():
        pytest.skip(
            "PySide6 IS available in this environment -- the "
            "'pyside6-unavailable' exit-2 path is not reachable here; the "
            "positive tiling-mode path is covered by the tests above instead."
        )
    result = run_script(SCRIPT, ["--width", "64", "--height", "64", "--frames", "1"])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "pyside6-unavailable"


# --------------------------------------------------------------------------- #
# --full-frame mode (Slice-A, Qt-FREE): the same invalid-input / huge-vs-
# negative-ceiling / exit-code contract already proven for --composite above,
# PLUS the C-08 ceiling-resolves-from-constants assertion.
# --------------------------------------------------------------------------- #
def _real_constants_value(name: str):
    """Read ``name`` off the REAL, imported ``pixelart_creator.logic.constants``
    -- this test PROCESS's own environment, never a duplicated literal -- so
    assertions compare against the single source of truth (S12)."""
    from pixelart_creator.logic import constants as _c

    return getattr(_c, name)


def test_full_frame_invalid_geometry_exits_2():
    result = run_script(
        SCRIPT, ["--full-frame", "--width", "0", "--layers", "2", "--frames", "1"]
    )
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "invalid-input"


@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_full_frame_huge_ceiling_is_always_within_exits_0():
    result = run_script(
        SCRIPT,
        [
            "--full-frame",
            "--width",
            "256",
            "--height",
            "256",
            "--layers",
            "2",
            "--frames",
            "1",
            "--ceiling-ms",
            "1000000000",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["mode"] == "full-frame"
    assert payload["gated"] is True
    assert payload["within_ceiling"] is True
    assert payload["ceiling_ms"] == 1000000000.0


@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_full_frame_negative_ceiling_is_always_over_exits_1():
    result = run_script(
        SCRIPT,
        [
            "--full-frame",
            "--width",
            "256",
            "--height",
            "256",
            "--layers",
            "2",
            "--frames",
            "1",
            "--ceiling-ms",
            "-1",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["within_ceiling"] is False
    assert payload["ceiling_ms"] == -1.0


@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_full_frame_ceiling_resolves_from_constants_not_fallback():
    """No ``--ceiling-ms`` override -> the script must resolve the real
    ``COMPOSITE_FULL_CEILING_MS`` from ``logic/constants.py`` (C-08): the
    fallback-literal code path this used to fall through to no longer
    exists, and this proves the resolved number matches the single source of
    truth rather than a stand-in."""
    result = run_script(
        SCRIPT,
        [
            "--full-frame",
            "--width",
            "256",
            "--height",
            "256",
            "--layers",
            "2",
            "--frames",
            "1",
        ],
    )
    assert result.returncode in (0, 1), result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "full-frame"
    assert payload["ceiling_ms"] == _real_constants_value("COMPOSITE_FULL_CEILING_MS")


# --------------------------------------------------------------------------- #
# --viewport-recomposite mode (Slice-B, Qt-FREE): same shape as --full-frame.
# --------------------------------------------------------------------------- #
def test_viewport_recomposite_invalid_geometry_exits_2():
    result = run_script(
        SCRIPT,
        ["--viewport-recomposite", "--width", "0", "--vp-layers", "2", "--frames", "1"],
    )
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "invalid-input"


@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_viewport_recomposite_huge_ceiling_is_always_within_exits_0():
    result = run_script(
        SCRIPT,
        [
            "--viewport-recomposite",
            "--width",
            "256",
            "--height",
            "256",
            "--vp-layers",
            "2",
            "--vp-region-size",
            "32",
            "--frames",
            "1",
            "--ceiling-ms",
            "1000000000",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["mode"] == "viewport-recomposite"
    assert payload["gated"] is True
    assert payload["within_ceiling"] is True
    assert payload["byte_exact"] is True
    assert payload["ceiling_ms"] == 1000000000.0


@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_viewport_recomposite_negative_ceiling_is_always_over_exits_1():
    result = run_script(
        SCRIPT,
        [
            "--viewport-recomposite",
            "--width",
            "256",
            "--height",
            "256",
            "--vp-layers",
            "2",
            "--vp-region-size",
            "32",
            "--frames",
            "1",
            "--ceiling-ms",
            "-1",
        ],
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["within_ceiling"] is False
    assert payload["ceiling_ms"] == -1.0


@pytest.mark.skipif(not _logic_available(), reason=_LOGIC_SKIP)
def test_viewport_recomposite_ceiling_resolves_from_constants_not_fallback():
    """No ``--ceiling-ms`` override -> the script must resolve the real
    ``VIEWPORT_RECOMPOSITE_CEILING_MS`` from ``logic/constants.py`` (C-08).
    This is the exact constant whose OLD fallback literal (3000) happened to
    equal the real shipped value -- the coincidence that made the missing-
    attribute case silently pass before this fix."""
    result = run_script(
        SCRIPT,
        [
            "--viewport-recomposite",
            "--width",
            "256",
            "--height",
            "256",
            "--vp-layers",
            "2",
            "--vp-region-size",
            "32",
            "--frames",
            "1",
        ],
    )
    assert result.returncode in (0, 1), result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "viewport-recomposite"
    assert payload["ceiling_ms"] == _real_constants_value(
        "VIEWPORT_RECOMPOSITE_CEILING_MS"
    )


# --------------------------------------------------------------------------- #
# C-08 regression: a logic.constants module that IS importable but is missing
# a required ceiling constant must fail LOUDLY (named, actionable, exit 2),
# never silently compute a verdict off a guessed fallback literal.
#
# Regression test for C-08 -- proven by reversion in the commit pass.
# --------------------------------------------------------------------------- #
_SHIM_ALL_REQUIRED_CONSTANTS = {
    "MAX_CANVAS_WIDTH": 7680,
    "MAX_CANVAS_HEIGHT": 4320,
    "TILE_SIZE": 64,
    "FRAME_BUDGET_MS": 16,
    "COMPOSITE_REGION_CEILING_MS": 200,
    "REALTIME_APPLY_CEILING_MS": 10,
    "MAX_SHARED_MEMBERS": 32,
    "OVERLAY_FRAME_CEILING_MS": 48,
    "COMPOSITE_FULL_CEILING_MS": 15000,
    "VIEWPORT_RECOMPOSITE_CEILING_MS": 3000,
}


def _write_constants_shim_missing(tmp_path, missing_name: str) -> str:
    """Build a doctored ``pixelart_creator.logic.constants`` package under
    ``tmp_path`` that is otherwise complete but missing exactly
    ``missing_name`` -- an importable module that has REGRESSED, distinct
    from the "package absent from PYTHONPATH" environment gap the script's
    ``except Exception`` fallback branch legitimately covers. Returns the
    shim root as a ``str`` suitable for a ``PYTHONPATH`` entry.

    NOTE ON INVOCATION SHAPE (load-bearing): this shim only shadows the real,
    editable-installed ``pixelart_creator`` when the target script is run as
    ``python scripts/perf_profile.py`` (``sys.path[0]`` becomes the
    ``scripts/`` directory, which holds no ``pixelart_creator``, so the
    PYTHONPATH-prepended shim is found first) -- exactly what ``run_script``
    does. A ``python -c`` invocation would NOT reproduce this: ``-c`` inserts
    the current working directory (the repo root, which itself contains the
    real ``pixelart_creator`` package) as ``sys.path[0]``, ahead of
    ``PYTHONPATH``, so the real module would win instead. Verified by hand
    before writing this fixture.
    """
    assert missing_name in _SHIM_ALL_REQUIRED_CONSTANTS
    pkg_root = tmp_path / "constants_shim"
    logic_dir = pkg_root / "pixelart_creator" / "logic"
    logic_dir.mkdir(parents=True)
    (pkg_root / "pixelart_creator" / "__init__.py").write_text("", encoding="utf-8")
    (logic_dir / "__init__.py").write_text("", encoding="utf-8")
    lines = [
        f"{name} = {value}"
        for name, value in _SHIM_ALL_REQUIRED_CONSTANTS.items()
        if name != missing_name
    ]
    lines.append(f"# {missing_name} intentionally OMITTED (C-08 regression shim).")
    (logic_dir / "constants.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(pkg_root)


@pytest.mark.parametrize(
    "mode_flag, missing_name",
    [
        pytest.param(
            "--viewport-recomposite",
            "VIEWPORT_RECOMPOSITE_CEILING_MS",
            id="viewport-recomposite",
        ),
        pytest.param("--full-frame", "COMPOSITE_FULL_CEILING_MS", id="full-frame"),
    ],
)
def test_missing_ceiling_constant_is_loud_not_silent(tmp_path, mode_flag, missing_name):
    """Regression test for C-08 -- proven by reversion in the commit pass.

    With the pre-fix ``getattr(_c, "<NAME>", <literal>)`` code, this exact
    scenario (module imports fine, one required ceiling constant absent)
    would have silently resolved to the hard-coded fallback and, for
    ``VIEWPORT_RECOMPOSITE_CEILING_MS`` specifically, produced the EXACT same
    number (3000) as the real constant -- a gate that looks healthy while
    the constants import is actually broken. The fixed script must instead
    exit 2 with a JSON ``error`` naming the missing constant, before
    argparse or any timing work ever runs.
    """
    shim_root = _write_constants_shim_missing(tmp_path, missing_name)
    result = run_script(
        SCRIPT,
        [mode_flag, "--width", "64", "--height", "64", "--frames", "1"],
        env={"PYTHONPATH": shim_root},
    )
    assert result.returncode == 2, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload["error"] == "missing-constants"
    assert payload["missing"] == [missing_name]
    assert missing_name in result.stderr
