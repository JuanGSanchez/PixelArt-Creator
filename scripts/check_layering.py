#!/usr/bin/env python
# =============================================================================
# SCRIPT: check_layering  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Enforce the three-layer code architecture (S11) by AST-inspecting
#   every module's imports: ui/ may import logic/ and data/; logic/ is pure
#   Python (zero Qt, no ui/data imports); data/ is I/O only (zero Qt, no ui
#   import). The only Qt-dependent file permitted outside ui/ is ui/commands.py
#   (which is inside ui/, so always allowed).
# FLAVOUR: standalone
# LOCATION: scripts/check_layering.py  (CONVENTIONS standalone-script location)
# INVOKED BY: AGT-01 Architecture (pre-flight + sdd-analyze gate); AGT-09 CI.
#   Agents invoke via their harness/ephemeral step; not called by an LLM inline.
# RUNTIME: Python 3.8+ (CPython, stdlib only: ast, os, sys, json, argparse).
# ENTRYPOINT: python scripts/check_layering.py [--root pixelart_creator] [--json]
# INPUTS:
#   --root  (CLI arg, optional, default "pixelart_creator"): package root to scan.
#   --json  (CLI flag, optional): force JSON output even when clean.
# OUTPUTS:
#   stdout: JSON {"violations":[{file,layer,imports,rule}], "scanned":N} (structured).
#   stderr: human-readable summary lines.
#   exit code (see EXIT CODES).
# EXIT CODES: 0 clean -> COMPLETED ; 1 violations found -> FAILED ;
#   2 invalid input / unreadable root -> BLOCKED.
# PRECONDITIONS: --root exists and contains .py files.
# DETERMINISM NOTE: fully deterministic given the file tree; files and findings
#   are sorted; no time/random/network. Path handling via os.path (portable).
#
# ## Principles Applied
# Inherited: P1 (grounded in S11 three-layer rule), P2 (fixed rules + default),
#   P3 (entrypoint + I/O spec), P4 (exit-status mapping), P6 (stdlib only,
#   declared deps), P7, P9 (one job: layering), P10 (exit code -> status),
#   P11 (scripts ARE the canonical mechanism), P12 (all layers + Qt rule covered),
#   P13 (fewest tokens).
# Custom: (none)
#
# SOURCES: User req S11/S12 (Dossier §1); Dossier §6.5/§8 (script owner AGT-01);
#   asset-templates.md §Script; Python `ast` stdlib docs (grounded, standard lib).
# =============================================================================
import argparse
import ast
import json
import os
import sys

# Import-name prefixes forbidden per layer. Keys are the layer directory names.
QT = ("PySide6", "PySide2", "PyQt6", "PyQt5", "shiboken6", "shiboken2")
FORBIDDEN = {
    "logic": QT + ("pixelart_creator.ui", "pixelart_creator.data", "..ui", "..data"),
    "data": QT + ("pixelart_creator.ui", "..ui"),
    # ui/ has no forbidden imports (may use logic, data, Qt).
}


def module_layer(path, root):
    rel = os.path.relpath(path, root).replace("\\", "/")
    parts = rel.split("/")
    return parts[0] if parts else ""


def imports_of(path):
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = ("." * node.level) + (node.module or "")
            names.append(mod)
    return sorted(set(names))


def main():
    ap = argparse.ArgumentParser(description="Enforce three-layer import rules (S11).")
    ap.add_argument("--root", default="pixelart_creator")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.stderr.write("check_layering: root not found: %s\n" % args.root)
        print(json.dumps({"violations": [], "scanned": 0, "error": "root-not-found"}))
        return 2

    violations = []
    scanned = 0
    try:
        for dirpath, _dirs, files in os.walk(args.root):
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                layer = module_layer(path, args.root)
                rules = FORBIDDEN.get(layer)
                if not rules:
                    continue
                scanned += 1
                mods = imports_of(path)
                bad = sorted(
                    m
                    for m in mods
                    if any(
                        m == r
                        or m.startswith(r + ".")
                        or (r.startswith("..") and m.startswith(r))
                        for r in rules
                    )
                )
                if bad:
                    violations.append(
                        {
                            "file": os.path.relpath(path, args.root).replace("\\", "/"),
                            "layer": layer,
                            "imports": bad,
                            "rule": "%s/ must not import: %s"
                            % (layer, ", ".join(rules)),
                        }
                    )
    except (SyntaxError, OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("check_layering: parse error: %r\n" % exc)
        print(
            json.dumps(
                {"violations": violations, "scanned": scanned, "error": repr(exc)}
            )
        )
        return 2

    violations.sort(key=lambda v: v["file"])
    result = {"violations": violations, "scanned": scanned}
    if violations or args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    if violations:
        sys.stderr.write(
            "check_layering: %d layering violation(s).\n" % len(violations)
        )
        return 1
    sys.stderr.write("check_layering: clean (%d modules).\n" % scanned)
    return 0


if __name__ == "__main__":
    sys.exit(main())
