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
# RUNTIME: Python 3.8+ (CPython, stdlib only: xml.etree, argparse, json, os, sys).
# ENTRYPOINT: python scripts/coverage_gate.py [--xml coverage.xml]
#             [--line 90] [--branch 80]
# INPUTS:
#   --xml    (CLI arg, optional, default "coverage.xml"): Cobertura report path.
#   --line   (CLI arg, optional, default 90): per-package minimum line %.
#   --branch (CLI arg, optional, default 80): per-package minimum branch %.
# OUTPUTS:
#   stdout: JSON {"packages":[{name,line_pct,branch_pct,pass}], "overall":{...},
#                 "failures":[...]}.
#   stderr: human summary. exit code per EXIT CODES.
# EXIT CODES: 0 all packages pass -> COMPLETED ; 1 a package under threshold ->
#   FAILED ; 2 report missing / unparseable / thresholds invalid -> BLOCKED.
# PRECONDITIONS: coverage.xml exists (run pytest --cov --cov-report=xml first).
# DETERMINISM NOTE: deterministic given the XML; packages sorted; percentages
#   rounded to 2 dp; no time/random/network.
#
# ## Principles Applied
# Inherited: P1 (grounded S13 90/80 gate), P2, P3, P4, P6 (stdlib only),
#   P7, P9 (one job: coverage gate), P10 (exit->status), P11, P12 (per-package
#   AND overall), P13.
# Custom: (none)
#
# SOURCES: User req S13 (Dossier §1); Dossier §6.5/§8 (owner AGT-09 CI);
#   Cobertura XML schema (coverage.py `xml` report, standard); asset-templates §Script.
# =============================================================================
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET


def pct(rate):
    try:
        return round(float(rate) * 100.0, 2)
    except (TypeError, ValueError):
        return 0.0


def main():
    ap = argparse.ArgumentParser(description="Coverage gate (S13: >=90 line / >=80 branch).")
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
    pkgs_el = root.find("packages")
    pkg_list = list(pkgs_el) if pkgs_el is not None else []
    for pkg in sorted(pkg_list, key=lambda p: p.get("name", "")):
        name = pkg.get("name", "(root)")
        line_pct = pct(pkg.get("line-rate"))
        branch_pct = pct(pkg.get("branch-rate"))
        ok = line_pct >= args.line and branch_pct >= args.branch
        packages.append({"name": name, "line_pct": line_pct,
                         "branch_pct": branch_pct, "pass": ok})
        if not ok:
            failures.append({"name": name, "line_pct": line_pct,
                             "branch_pct": branch_pct,
                             "need_line": args.line, "need_branch": args.branch})

    overall = {"line_pct": pct(root.get("line-rate")),
               "branch_pct": pct(root.get("branch-rate"))}
    result = {"packages": packages, "overall": overall, "failures": failures,
              "thresholds": {"line": args.line, "branch": args.branch}}
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        sys.stderr.write("coverage_gate: %d package(s) below threshold.\n" % len(failures))
        return 1
    if not packages:
        sys.stderr.write("coverage_gate: no packages in report.\n")
        return 2
    sys.stderr.write("coverage_gate: all %d package(s) pass.\n" % len(packages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
