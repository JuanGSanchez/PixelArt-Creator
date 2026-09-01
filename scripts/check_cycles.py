#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: check_cycles  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Detect circular imports among the project's own modules by building
#   the intra-package import graph (AST) and reporting any dependency cycle.
# FLAVOUR: standalone
# LOCATION: scripts/check_cycles.py
# INVOKED BY: AGT-01 Architecture (pre-flight + sdd-analyze gate); AGT-09 CI.
#   PHASE-10: run a second time over the sync backend so its internal graph is
#   also cycle-checked (the backend is a separate top-level package, ADR-0027;
#   the check is generic over --root, so no rule change is needed):
#     python scripts/check_cycles.py --root pixelart_creator   # client package
#     python scripts/check_cycles.py --root sync_backend        # backend package
# RUNTIME: Python 3.8+ (CPython, stdlib only: ast, os, sys, json, argparse).
# ENTRYPOINT: python scripts/check_cycles.py [--root pixelart_creator] [--json]
# INPUTS:
#   --root (CLI arg, optional, default "pixelart_creator"): package root.
#   --json (CLI flag, optional): force JSON output even when clean.
# OUTPUTS:
#   stdout: JSON {"cycles":[[mod,...]], "modules":N, "edges":M}.
#   stderr: human summary. exit code per EXIT CODES.
# EXIT CODES: 0 no cycles -> COMPLETED ; 1 cycle(s) found -> FAILED ;
#   2 invalid input / unreadable root -> BLOCKED.
# PRECONDITIONS: --root exists.
# DETERMINISM NOTE: deterministic; modules sorted; cycle detection is a fixed
#   Tarjan SCC over the sorted graph; no time/random/network.
#
# ## Principles Applied
# Inherited: P1 (grounded S11 architecture), P2, P3 (entrypoint + I/O), P4,
#   P6 (stdlib only), P7, P9 (one job: cycle detection), P10 (exit->status),
#   P11 (script vehicle), P12 (reports every SCC of size>1 or self-loop),
#   P13.
# Custom: (none)
#
# SOURCES: Dossier §6.5/§8 (owner AGT-01); asset-templates.md §Script;
#   Tarjan (1972) SCC algorithm (standard); Python `ast` docs.
# =============================================================================
import argparse
import ast
import json
import os
import sys


def to_module(path, root_parent):
    rel = os.path.relpath(path, root_parent).replace("\\", "/")
    if rel.endswith(".py"):
        rel = rel[:-3]
    if rel.endswith("/__init__"):
        rel = rel[: -len("/__init__")]
    return rel.replace("/", ".")


def internal_imports(path, pkg, root_parent):
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    this_mod = to_module(path, root_parent)
    this_pkg = this_mod.rsplit(".", 1)[0] if "." in this_mod else this_mod
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == pkg or a.name.startswith(pkg + "."):
                    out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base = this_pkg
                for _ in range(node.level - 1):
                    base = base.rsplit(".", 1)[0] if "." in base else base
                mod = base + ("." + node.module if node.module else "")
                out.add(mod)
            elif node.module and (
                node.module == pkg or node.module.startswith(pkg + ".")
            ):
                out.add(node.module)
    return out


def tarjan(graph):
    index = {}
    low = {}
    stack = []
    on = set()
    counter = [0]
    sccs = []

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(sorted(comp))

    for v in sorted(graph):
        if v not in index:
            strong(v)
    return sccs


def main():
    ap = argparse.ArgumentParser(description="Detect circular imports.")
    ap.add_argument("--root", default="pixelart_creator")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root.rstrip("/\\")
    if not os.path.isdir(root):
        sys.stderr.write("check_cycles: root not found: %s\n" % root)
        print(
            json.dumps(
                {"cycles": [], "modules": 0, "edges": 0, "error": "root-not-found"}
            )
        )
        return 2

    pkg = os.path.basename(root)
    root_parent = os.path.dirname(os.path.abspath(root)) or "."
    graph = {}
    try:
        for dirpath, _dirs, files in os.walk(root):
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                mod = to_module(path, root_parent)
                graph[mod] = internal_imports(path, pkg, root_parent)
    except (SyntaxError, OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("check_cycles: parse error: %r\n" % exc)
        print(json.dumps({"cycles": [], "error": repr(exc)}))
        return 2

    edges = sum(len(v) for v in graph.values())
    cycles = [c for c in tarjan(graph) if len(c) > 1]
    for v in sorted(graph):
        if v in graph.get(v, ()):
            cycles.append([v])
    cycles.sort()
    result = {"cycles": cycles, "modules": len(graph), "edges": edges}
    if cycles or args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    if cycles:
        sys.stderr.write("check_cycles: %d cycle(s) detected.\n" % len(cycles))
        return 1
    sys.stderr.write("check_cycles: no cycles (%d modules).\n" % len(graph))
    return 0


if __name__ == "__main__":
    sys.exit(main())
