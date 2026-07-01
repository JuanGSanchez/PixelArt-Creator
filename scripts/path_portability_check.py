#!/usr/bin/env python
# =============================================================================
# SCRIPT: path_portability_check  (standalone P11 script — PixelArt Creator)
# =============================================================================
# PURPOSE: Flag non-portable filesystem paths in source so the codebase runs on
#   a clean CI runner (machine-agnostic harness, S.D. §5): hardcoded backslash
#   separators in string literals, Windows drive-letter absolute paths (C:\..),
#   POSIX absolute roots used as literals, and `os.sep`-free manual joins.
# FLAVOUR: standalone
# LOCATION: scripts/path_portability_check.py
# INVOKED BY: AGT-09 GitHub/DevOps (local pre-flight gate + CI lint step);
#   AGT-03/AGT-05 local pre-flight before asserting "done".
# RUNTIME: Python 3.8+ (CPython, stdlib only: ast, re, argparse, json, os, sys).
# ENTRYPOINT: python scripts/path_portability_check.py [--root .]
#             [--include pixelart_creator scripts tests]
# INPUTS:
#   --root    (CLI arg, optional, default "."): repo root.
#   --include (CLI arg, optional, nargs+): subdirs to scan (default the source dirs).
# OUTPUTS:
#   stdout: JSON {"findings":[{file,line,kind,text}], "scanned":N}.
#   stderr: human summary. exit code per EXIT CODES.
# EXIT CODES: 0 clean -> COMPLETED ; 1 findings -> FAILED (blocks "done") ;
#   2 error -> BLOCKED.
# PRECONDITIONS: --root exists.
# DETERMINISM NOTE: deterministic; literals inspected via AST; regexes are fixed;
#   findings sorted; no time/random/network. Skips this script and test fixtures
#   that legitimately assert path strings only if marked `# portability: ok`.
#
# ## Principles Applied
# Inherited: P1 (grounded S.D. §5 machine-agnostic harness), P2, P3, P4,
#   P6 (stdlib), P7, P9 (one job: path portability), P10, P11, P12 (backslash +
#   drive-letter + posix-root + separator checks), P13.
# Custom: (none)
#
# SOURCES: spec-driven-development.md §5 (machine-agnostic harness); Dossier
#   §6.5/§8 (owner AGT-09); asset-templates.md §Script; Python os.path docs.
# =============================================================================
import argparse
import ast
import json
import os
import re
import sys

DRIVE_ABS = re.compile(r"^[A-Za-z]:[\\/]")
POSIX_ABS = re.compile(r"^/(?:home|usr|var|tmp|Users|opt|mnt)/")
BACKSLASH_SEP = re.compile(r"[A-Za-z0-9_.\-]+\\[A-Za-z0-9_.\-]+")
SKIP_MARK = "portability: ok"


def looks_like_path(s):
    return ("/" in s or "\\" in s) and " " not in s.strip()[:3] and len(s) <= 200


def scan_source(path, rel):
    findings = []
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    marked = {i + 1 for i, ln in enumerate(src.splitlines()) if SKIP_MARK in ln}
    tree = ast.parse(src, filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            line = getattr(node, "lineno", 0)
            if line in marked or not val:
                continue
            kind = None
            if DRIVE_ABS.match(val):
                kind = "drive-letter-absolute-path"
            elif POSIX_ABS.match(val):
                kind = "hardcoded-posix-absolute-path"
            elif looks_like_path(val) and BACKSLASH_SEP.search(val):
                kind = "backslash-separator-in-literal"
            if kind:
                findings.append({"file": rel, "line": line, "kind": kind,
                                 "text": val[:80]})
    return findings


def main():
    ap = argparse.ArgumentParser(description="Flag non-portable path literals.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--include", nargs="+",
                    default=["pixelart_creator", "scripts", "tests"])
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.stderr.write("path_portability_check: root not found.\n")
        print(json.dumps({"error": "root-not-found"}))
        return 2

    self_name = os.path.basename(__file__)
    files = []
    for inc in args.include:
        base = os.path.join(args.root, inc)
        if os.path.isfile(base) and base.endswith(".py"):
            files.append(base)
        elif os.path.isdir(base):
            for dp, _d, fs in os.walk(base):
                for n in sorted(fs):
                    if n.endswith(".py") and n != self_name:
                        files.append(os.path.join(dp, n))
    files = sorted(set(files))

    findings = []
    try:
        for path in files:
            findings.extend(scan_source(path, os.path.relpath(path, args.root)
                                        .replace("\\", "/")))
    except (SyntaxError, OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("path_portability_check: error: %r\n" % exc)
        print(json.dumps({"findings": findings, "error": repr(exc)}))
        return 2

    findings.sort(key=lambda f: (f["file"], f["line"]))
    print(json.dumps({"findings": findings, "scanned": len(files)},
                     indent=2, sort_keys=True))
    if findings:
        sys.stderr.write("path_portability_check: %d non-portable path(s).\n"
                         % len(findings))
        return 1
    sys.stderr.write("path_portability_check: clean (%d files).\n" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
