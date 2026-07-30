#!/usr/bin/env python
# =============================================================================
# SCRIPT: coverage_gate  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Enforce the coverage gate (S13) by parsing a Cobertura coverage XML
#   (produced by pytest-cov `--cov-report=xml`) and failing if any package's
#   line rate < 90% or branch rate < 80%.
# FLAVOUR: standalone
# LOCATION: scripts/coverage_gate.py
# INVOKED BY: AGT-09 GitHub/DevOps (CI quality gate step); AGT-04 local pre-flight.
# RUNTIME: Python 3.8+ (CPython, stdlib only: xml.etree, argparse, json, os, sys, re).
# ENTRYPOINT: python scripts/coverage_gate.py [--xml coverage.xml]
#             [--line 90] [--branch 80]
# INPUTS:
#   --xml    (CLI arg, optional, default "coverage.xml"): Cobertura report path.
#   --line   (CLI arg, optional, default 90): per-package minimum line %.
#   --branch (CLI arg, optional, default 80): per-package minimum branch %.
# OUTPUTS:
#   stdout: JSON {"packages":[{name,line_pct,branch_pct,pass}], "overall":{...},
#                 "failures":[...], "thresholds":{...},
#                 "files":[{package,filename,line_pct,branch_pct,total_lines,
#                   uncovered_lines,total_branches,uncovered_branches,pass}],
#                 "file_advisory":{note,below_threshold_count,below_threshold,
#                   would_fail_packages}}.
#   "files"/"file_advisory" are REMEDIATION #30: Cobertura already carries a
#   per-file <classes><class line-rate/branch-rate> rate alongside each
#   package's aggregate; a package can pass on the aggregate while one file
#   inside it sits far below threshold (e.g. a 0% branch-rate file averaged
#   away by well-covered siblings). These keys surface that per-file rate.
#   They are ADVISORY ONLY (see DECISION below): they never add to
#   "failures" and never change the exit code. "packages"/"overall"/
#   "failures"/"thresholds" keep their pre-#30 shape and values verbatim —
#   this is a strictly additive JSON extension, not a reshape.
# DECISION (#30, recorded here so the rationale travels with the code):
#   per-file thresholds are NOT wired to the exit code / "failures" list.
#   A real run on 2026-07-30 showed 26 of 196 files below the SAME 90/80
#   thresholds the package gate already enforces, inside packages ("ui",
#   "data") that pass today on the aggregate — wiring file-level failure
#   in would flip today's green build red without any code change. Advisory
#   visibility (this key) lets a human/CI step see the gap and decide,
#   rather than the gate silently enforcing a threshold quietly set low
#   enough to pass, or an unannounced new red build.
# EXIT CODES: 0 all packages pass -> COMPLETED ; 1 a package under threshold ->
#   FAILED ; 2 report missing / unparseable / thresholds invalid -> BLOCKED.
#   File-level advisory findings NEVER change the exit code (see DECISION).
# PRECONDITIONS: coverage.xml exists (run pytest --cov --cov-report=xml first).
# DETERMINISM NOTE: deterministic given the XML; packages sorted; files sorted
#   by (package, filename); percentages rounded to 2 dp; no time/random/network.
#
# ## Principles Applied
# Inherited: P1 (grounded S13 90/80 gate), P2, P3, P4, P6 (stdlib only),
#   P7, P9 (one job: coverage gate), P10 (exit->status), P11, P12 (per-package
#   AND overall), P13.
# Custom: (none)
#
# SOURCES: User req S13 (Dossier §1); Dossier §6.5/§8 (owner AGT-09 CI);
#   Cobertura XML schema (coverage.py `xml` report, standard); asset-templates §Script;
#   Issue #30 (per-file <classes> rates present in Cobertura XML, never read).
# =============================================================================
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

_CONDITION_RE = re.compile(r"\((\d+)/(\d+)\)")


def pct(rate):
    try:
        return round(float(rate) * 100.0, 2)
    except (TypeError, ValueError):
        return 0.0


def file_metrics(pkg_name, cls_el):
    """Compute per-file (Cobertura <class>) metrics: rates + raw line/branch counts.

    Reads the SAME line-rate/branch-rate attributes already present on the
    <class> element (issue #30 — these were parsed for packages but never for
    files), plus counts derived from the <lines><line> children: total/
    uncovered lines from hits, total/uncovered branches from each branch
    line's condition-coverage="NN% (covered/total)" attribute (defensive: a
    missing/unparseable attribute contributes 0/0 rather than raising).
    """
    filename = cls_el.get("filename", cls_el.get("name", "(unknown)"))
    line_pct = pct(cls_el.get("line-rate"))
    branch_pct = pct(cls_el.get("branch-rate"))

    total_lines = 0
    uncovered_lines = 0
    total_branches = 0
    uncovered_branches = 0
    lines_el = cls_el.find("lines")
    for line_el in list(lines_el) if lines_el is not None else []:
        total_lines += 1
        if int(line_el.get("hits", "0") or "0") <= 0:
            uncovered_lines += 1
        if line_el.get("branch") == "true":
            m = _CONDITION_RE.search(line_el.get("condition-coverage", ""))
            if m:
                covered_b, total_b = int(m.group(1)), int(m.group(2))
                total_branches += total_b
                uncovered_branches += total_b - covered_b

    return {
        "package": pkg_name,
        "filename": filename,
        "line_pct": line_pct,
        "branch_pct": branch_pct,
        "total_lines": total_lines,
        "uncovered_lines": uncovered_lines,
        "total_branches": total_branches,
        "uncovered_branches": uncovered_branches,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Coverage gate (S13: >=90 line / >=80 branch)."
    )
    ap.add_argument("--xml", default="coverage.xml")
    ap.add_argument("--line", type=float, default=90.0)
    ap.add_argument("--branch", type=float, default=80.0)
    args = ap.parse_args()

    if not (0 <= args.line <= 100 and 0 <= args.branch <= 100):
        sys.stderr.write("coverage_gate: thresholds must be 0..100.\n")
        print(json.dumps({"error": "invalid-thresholds"}))
        return 2
    if not os.path.isfile(args.xml):
        sys.stderr.write("coverage_gate: report not found: %s\n" % args.xml)
        print(json.dumps({"error": "report-not-found", "xml": args.xml}))
        return 2
    try:
        root = ET.parse(args.xml).getroot()
    except ET.ParseError as exc:
        sys.stderr.write("coverage_gate: XML parse error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    packages = []
    failures = []
    files = []
    # name -> did the PACKAGE-LEVEL aggregate pass under today's enforced gate.
    pkg_pass_by_name = {}
    pkgs_el = root.find("packages")
    pkg_list = list(pkgs_el) if pkgs_el is not None else []
    for pkg in sorted(pkg_list, key=lambda p: p.get("name", "")):
        name = pkg.get("name", "(root)")
        line_pct = pct(pkg.get("line-rate"))
        branch_pct = pct(pkg.get("branch-rate"))
        ok = line_pct >= args.line and branch_pct >= args.branch
        packages.append(
            {"name": name, "line_pct": line_pct, "branch_pct": branch_pct, "pass": ok}
        )
        pkg_pass_by_name[name] = ok
        if not ok:
            failures.append(
                {
                    "name": name,
                    "line_pct": line_pct,
                    "branch_pct": branch_pct,
                    "need_line": args.line,
                    "need_branch": args.branch,
                }
            )
        # #30: read the per-file <classes><class> rates in this SAME package
        # element — advisory only, never folds into `failures` (see module
        # header DECISION). Uses the identical thresholds as the package gate
        # so "would this file pass the gate on its own" is directly comparable.
        classes_el = pkg.find("classes")
        for cls_el in list(classes_el) if classes_el is not None else []:
            fm = file_metrics(name, cls_el)
            fm["pass"] = fm["line_pct"] >= args.line and fm["branch_pct"] >= args.branch
            files.append(fm)

    files.sort(key=lambda f: (f["package"], f["filename"]))
    below_threshold = [f for f in files if not f["pass"]]
    # Worst first: lowest line_pct, then lowest branch_pct.
    below_threshold_sorted = sorted(
        below_threshold, key=lambda f: (f["line_pct"], f["branch_pct"])
    )
    would_fail_packages = sorted(
        {
            f["package"]
            for f in below_threshold
            if pkg_pass_by_name.get(f["package"]) is True
        }
    )

    overall = {
        "line_pct": pct(root.get("line-rate")),
        "branch_pct": pct(root.get("branch-rate")),
    }
    result = {
        "packages": packages,
        "overall": overall,
        "failures": failures,
        "thresholds": {"line": args.line, "branch": args.branch},
        "files": files,
        "file_advisory": {
            "note": (
                "Per-file rates are ADVISORY ONLY (issue #30 remediation): they "
                "do not add to 'failures' and do not change the exit code. "
                "'would_fail_packages' lists packages that PASS today on the "
                "package aggregate but contain at least one file below the "
                "same thresholds -- i.e. packages whose aggregate is currently "
                "hiding a real per-file gap."
            ),
            "thresholds": {"line": args.line, "branch": args.branch},
            "below_threshold_count": len(below_threshold),
            "below_threshold": below_threshold_sorted,
            "would_fail_packages": would_fail_packages,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        sys.stderr.write(
            "coverage_gate: %d package(s) below threshold.\n" % len(failures)
        )
        return 1
    if not packages:
        sys.stderr.write("coverage_gate: no packages in report.\n")
        return 2
    sys.stderr.write("coverage_gate: all %d package(s) pass.\n" % len(packages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
