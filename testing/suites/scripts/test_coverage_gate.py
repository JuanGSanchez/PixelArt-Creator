"""Contract tests for ``scripts/coverage_gate.py`` (ADR-0047 / PA-04 tranche 1).

Contract asserted here, taken verbatim from the script's own header:

    ENTRYPOINT: python scripts/coverage_gate.py [--xml coverage.xml]
                [--line 90] [--branch 80]
    EXIT CODES: 0 all packages pass -> COMPLETED ; 1 a package under
        threshold -> FAILED ; 2 report missing / unparseable / thresholds
        invalid -> BLOCKED.

Every fixture below is a hand-built Cobertura XML written under ``tmp_path``
and passed to the script via its own ``--xml`` flag. The real ``coverage.xml``
this repository's CI produces is never read by these tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import run_script

SCRIPT = "coverage_gate.py"


def _cobertura_xml(packages) -> str:
    """Build a minimal Cobertura report.

    ``packages`` is a list of dicts: ``{"name", "line_rate", "branch_rate"}``,
    each rendered as a ``<package>`` with one trivial ``<class>`` whose own
    per-file rate matches the package rate (irrelevant to the package-level
    gate under test here; file_advisory is exercised implicitly and is never
    asserted on in this module).
    """
    pkg_xml = []
    for pkg in packages:
        pkg_xml.append(
            '<package name="{name}" line-rate="{line_rate}" '
            'branch-rate="{branch_rate}">'
            "<classes>"
            '<class name="mod.py" filename="{name}/mod.py" '
            'line-rate="{line_rate}" branch-rate="{branch_rate}">'
            "<lines>"
            '<line number="1" hits="1"/>'
            '<line number="2" hits="0"/>'
            "</lines>"
            "</class>"
            "</classes>"
            "</package>".format(**pkg)
        )
    return (
        '<?xml version="1.0" ?>'
        '<coverage line-rate="0.9" branch-rate="0.8">'
        "<packages>" + "".join(pkg_xml) + "</packages>"
        "</coverage>"
    )


def _write_xml(tmp_path: Path, packages) -> Path:
    xml_path = tmp_path / "coverage.xml"
    xml_path.write_text(_cobertura_xml(packages), encoding="utf-8")
    return xml_path


# --------------------------------------------------------------------------- #
# The essential pair: a clean input exits 0, a broken input exits 1.
# --------------------------------------------------------------------------- #
def test_clean_package_above_thresholds_exits_0(tmp_path):
    xml_path = _write_xml(
        tmp_path,
        [
            {
                "name": "pixelart_creator.logic",
                "line_rate": "0.95",
                "branch_rate": "0.85",
            }
        ],
    )
    result = run_script(
        SCRIPT, ["--xml", str(xml_path), "--line", "90", "--branch", "80"]
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["failures"] == []
    assert payload["packages"] == [
        {
            "name": "pixelart_creator.logic",
            "line_pct": 95.0,
            "branch_pct": 85.0,
            "pass": True,
        }
    ]


def test_package_below_line_threshold_exits_1_and_is_named_in_failures(tmp_path):
    """Deliberately broken fixture: a package whose line-rate sits under 90%
    must fail the gate with exit code 1 and be named in ``failures`` -- the
    proof that the gate can still FAIL, not just still pass."""
    xml_path = _write_xml(
        tmp_path,
        [
            {"name": "pixelart_creator.ui", "line_rate": "0.50", "branch_rate": "0.85"},
            {
                "name": "pixelart_creator.data",
                "line_rate": "0.95",
                "branch_rate": "0.85",
            },
        ],
    )
    result = run_script(
        SCRIPT, ["--xml", str(xml_path), "--line", "90", "--branch", "80"]
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    failing_names = [f["name"] for f in payload["failures"]]
    assert failing_names == ["pixelart_creator.ui"]
    assert payload["failures"][0]["line_pct"] == 50.0
    # The healthy package must NOT be swept into the failure list.
    passing_names = [p["name"] for p in payload["packages"] if p["pass"]]
    assert "pixelart_creator.data" in passing_names


def test_package_below_branch_threshold_exits_1(tmp_path):
    xml_path = _write_xml(
        tmp_path,
        [
            {
                "name": "pixelart_creator.logic",
                "line_rate": "0.95",
                "branch_rate": "0.10",
            }
        ],
    )
    result = run_script(
        SCRIPT, ["--xml", str(xml_path), "--line", "90", "--branch", "80"]
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["failures"][0]["name"] == "pixelart_creator.logic"


# --------------------------------------------------------------------------- #
# The BLOCKED path (exit 2): missing report, unparseable XML, invalid
# thresholds, and an empty (no-package) report.
# --------------------------------------------------------------------------- #
def test_missing_report_exits_2(tmp_path):
    missing = tmp_path / "does-not-exist.xml"
    result = run_script(SCRIPT, ["--xml", str(missing)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "report-not-found"


def test_unparseable_xml_exits_2(tmp_path):
    bad_xml = tmp_path / "coverage.xml"
    bad_xml.write_text("<coverage><packages>NOT VALID XML", encoding="utf-8")
    result = run_script(SCRIPT, ["--xml", str(bad_xml)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert "error" in payload


def test_invalid_thresholds_exit_2(tmp_path):
    xml_path = _write_xml(
        tmp_path,
        [
            {
                "name": "pixelart_creator.logic",
                "line_rate": "0.95",
                "branch_rate": "0.85",
            }
        ],
    )
    result = run_script(SCRIPT, ["--xml", str(xml_path), "--line", "150"])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "invalid-thresholds"


def test_report_with_no_packages_exits_2(tmp_path):
    xml_path = _write_xml(tmp_path, [])
    result = run_script(SCRIPT, ["--xml", str(xml_path)])
    assert result.returncode == 2, result.stderr


# --------------------------------------------------------------------------- #
# The documented CLI defaults, asserted via the script's own JSON echo of
# the thresholds it actually applied -- not a hardcoded duplicate.
# --------------------------------------------------------------------------- #
def test_default_thresholds_are_90_line_80_branch_per_header(tmp_path):
    xml_path = _write_xml(
        tmp_path,
        [
            {
                "name": "pixelart_creator.logic",
                "line_rate": "0.95",
                "branch_rate": "0.85",
            }
        ],
    )
    result = run_script(SCRIPT, ["--xml", str(xml_path)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["thresholds"] == {"line": 90.0, "branch": 80.0}


# --------------------------------------------------------------------------- #
# Structured-output contract: the advisory per-file keys exist and never
# change the exit code (module DECISION #30) even when a file inside a
# passing package sits below the same thresholds.
# --------------------------------------------------------------------------- #
def test_file_advisory_never_changes_exit_code(tmp_path):
    xml_path = tmp_path / "coverage.xml"
    xml_path.write_text(
        '<?xml version="1.0" ?>'
        '<coverage line-rate="0.9" branch-rate="0.8"><packages>'
        '<package name="pixelart_creator.ui" line-rate="0.95" branch-rate="0.85">'
        "<classes>"
        # A single low-covered file, averaged away by nothing else in the
        # package -- forced here by giving the ONE class a low rate while
        # the package aggregate (which the gate actually reads) stays high.
        '<class name="bad.py" filename="pixelart_creator/ui/bad.py" '
        'line-rate="0.10" branch-rate="0.10">'
        '<lines><line number="1" hits="0"/></lines>'
        "</class>"
        "</classes>"
        "</package>"
        "</packages></coverage>",
        encoding="utf-8",
    )
    result = run_script(
        SCRIPT, ["--xml", str(xml_path), "--line", "90", "--branch", "80"]
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr  # package aggregate still passes
    assert payload["failures"] == []
    assert payload["file_advisory"]["below_threshold_count"] == 1
    assert payload["file_advisory"]["would_fail_packages"] == ["pixelart_creator.ui"]
