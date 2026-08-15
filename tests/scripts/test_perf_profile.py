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
the ``--full-frame``, ``--tilemap``, ``--tm-cache``, ``--overlay``,
``--realtime`` and ``--viewport-recomposite`` modes. Each is a large,
independently-scoped profiling surface (multiple hundred lines apiece) with
its own construction fixtures; covering all of them is out of this tranche's
scope (ADR-0047's remit is "the four remaining gate scripts", not an
exhaustive enumeration of every ``perf_profile.py`` flag). The tiling and
composite modes were chosen because they are the two the header lists first
under ENTRYPOINT, and because between them they prove both the
PySide6/headless path and the Qt-free path can each still report FAILED (not
just COMPLETED) -- the exact property this tranche exists to establish.
"""

from __future__ import annotations

import json

import pytest

from .conftest import run_script

SCRIPT = "perf_profile.py"


def _pyside6_available() -> bool:
    try:
        import PySide6  # noqa: F401
    except Exception:
        return False
    return True


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
