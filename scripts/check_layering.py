#!/usr/bin/env python
# =============================================================================
# SCRIPT: check_layering  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Enforce the three-layer code architecture (S11) by AST-inspecting
#   every module's imports: ui/ may import logic/ and data/; logic/ is pure
#   Python (zero Qt, no ui/data imports); data/ is I/O only (zero Qt, no ui
#   import). The only Qt-dependent file permitted outside ui/ is ui/commands.py
#   (which is inside ui/, so always allowed).
#   PHASE-10 (cloud & collaboration): the real-time sync backend is a NEW
#   first-class top-level package `sync_backend/` that sits OUTSIDE the three
#   layers (ADR-0027). It is governed by a dedicated rule (below): it must not
#   import ui/, data/, or Qt — it stays headless and never touches the client's
#   OS-keyring tokens or provider adapters — but it MAY reuse the pure, Qt-free
#   `logic/` convergence + validation code. Reciprocally, no client layer
#   (logic/data/ui) may import the backend package: the desktop client reaches
#   the backend only over the zero-Qt `data/cloud/` transport port at run time
#   (REQ-P10-DATA-010), never by a Python import. `data/cloud/` itself is a
#   normal `data/` subpackage and is already governed by the `data` rule
#   (zero Qt, no ui/ import) — no provider SDK/transport type leaks above it.
#   PHASE-13 (cross-platform, Slice 13E): the web companion viewer is a SECOND
#   first-class top-level package `web_viewer/` outside the three layers
#   (ADR-0035, mirroring ADR-0027). Same shape as the backend rule: it must not
#   import Qt, ui/, data/, or `sync_backend` (it reaches the backend over the
#   wire (WS) at run time, never by import) but MAY reuse pure `logic/`.
#   Reciprocally no client layer (logic/data/ui) nor the backend imports it
#   (leaf consumer). It is governed by the same `--root .` run via parts[0] and
#   stays DORMANT until the `web_viewer/` package lands.
#   Run twice for full coverage:
#     python scripts/check_layering.py --root pixelart_creator   # client 3 layers
#     python scripts/check_layering.py --root .           # sync_backend/ + web_viewer/
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

# Import-name prefixes forbidden per layer. Keys are the layer directory names
# (parts[0] of the module path relative to --root).
QT = ("PySide6", "PySide2", "PyQt6", "PyQt5", "shiboken6", "shiboken2")

# Phase-10: the sync backend is a separate top-level package outside the three
# layers (ADR-0027). Client layers must never import it; the backend must never
# import ui/, data/, or Qt (it may reuse pure logic/).
BACKEND_PKG = "sync_backend"

# Phase-13 (Slice 13E): the web companion viewer is a NEW first-class top-level
# package outside the three layers (ADR-0035, mirroring ADR-0027). It is headless
# and MUST NOT import Qt, ui/, data/, or the sync backend (it reaches the backend
# over the wire — WS — at run time, never by Python import); it MAY reuse pure,
# Qt-free logic/ (share_token / sync_protocol / cloud_validation) so the wire +
# token contract is single-sourced with the backend. Reciprocally, no client
# layer (logic/data/ui) and not the backend may import it: web_viewer is a leaf
# consumer, so nothing in the shipped packages imports it. Governed via `--root .`
# (parts[0] == "web_viewer"); DORMANT until the package lands.
WEB_PKG = "web_viewer"

FORBIDDEN = {
    "logic": QT
    + (
        "pixelart_creator.ui",
        "pixelart_creator.data",
        "..ui",
        "..data",
        BACKEND_PKG,
        WEB_PKG,
    ),
    "data": QT + ("pixelart_creator.ui", "..ui", BACKEND_PKG, WEB_PKG),
    # ui/ may use logic, data, and Qt — but not the out-of-process sync backend
    # (it reaches the backend only via the data/cloud transport port at runtime)
    # and not the web viewer (a leaf top-level deployable — ADR-0035).
    "ui": (BACKEND_PKG, WEB_PKG),
    # The sync backend (scanned via `--root .`, parts[0] == "sync_backend"):
    # headless, no Qt, no ui/, no data/ (never touches client tokens/providers);
    # MAY reuse pure logic/ (convergence + cloud_validation). ADR-0027. It also
    # must not import the web viewer — the two non-three-layer deployables
    # communicate over the wire, not by Python import (ADR-0035 §3 peer decoupling).
    BACKEND_PKG: QT
    + ("pixelart_creator.ui", "pixelart_creator.data", "..ui", "..data", WEB_PKG),
    # The web viewer (scanned via `--root .`, parts[0] == "web_viewer"): headless,
    # no Qt, no ui/, no data/, no sync_backend; MAY reuse pure logic/. ADR-0035.
    WEB_PKG: QT
    + (
        "pixelart_creator.ui",
        "pixelart_creator.data",
        "..ui",
        "..data",
        BACKEND_PKG,
    ),
}


def module_layer(path, root):
    rel = os.path.relpath(path, root).replace("\\", "/")
    parts = rel.split("/")
    return parts[0] if parts else ""


def is_test_module(path, root):
    # Test modules are EXEMPT from layering enforcement: the layering
    # constitution governs PRODUCTION import edges only, not test-harness
    # imports. A test legitimately crosses package/layer boundaries (e.g. a
    # web_viewer handshake test must import sync_backend to spin an in-process
    # SyncServer, and data/ for fixtures). This is why sync_backend's own tests
    # live outside its package. Key strictly on a `tests` path component so
    # production code (web_viewer/dev_server.py, web_viewer/__init__.py,
    # web_viewer/static/**) stays fully governed.
    rel = os.path.relpath(path, root).replace("\\", "/")
    return "tests" in rel.split("/")


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
                if is_test_module(path, args.root):
                    continue
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
