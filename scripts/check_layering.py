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
#   Run twice for full coverage (CI runs BOTH — .github/workflows/ci.yml):
#     python scripts/check_layering.py --root pixelart_creator   # client 3 layers
#     python scripts/check_layering.py --root .           # sync_backend/ + web_viewer/
#   FAIL-CLOSED (2026-07-29): a top-level name that is not registered in
#   FORBIDDEN / DELEGATED_TOPLEVEL / UNGOVERNED_TOPLEVEL is a hard FAILURE
#   (exit 1), never a silent skip. See the registry block below for the defect
#   this replaces.
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
#   stdout: JSON {"violations":[{file,layer,imports,rule}], "scanned":N,
#     "unregistered":[{top_level,modules,example}], "exempt":{name:{modules,
#     reason,kind}}, "root_modules":[...]} (structured). Printed whenever there
#     is a violation OR an unregistered package, or on --json.
#   stderr: human-readable summary lines.
#   exit code (see EXIT CODES).
# EXIT CODES: 0 clean -> COMPLETED ; 1 violations found OR an UNREGISTERED
#   top-level package found (fail-closed) -> FAILED ;
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

# --- FAIL-CLOSED top-level registry (CI-integrity fix, 2026-07-29) -----------
# WHY: this script used to `continue` silently on any top-level name absent from
# FORBIDDEN, and it did so BEFORE incrementing `scanned`. An unrecognised
# top-level package was therefore neither ENFORCED nor COUNTED, and the gate
# still printed "clean" — i.e. it failed OPEN. A brand-new top-level package
# (a mobile client, a VPS-host package, …) would have been unguarded from its
# first commit while CI stayed green, and the module count would not have moved
# to betray it. Enforcement is now fail-CLOSED: every top-level name a scan
# meets MUST appear in exactly one of the three tables below, or the run FAILS
# and names it. Registering a new package is thus a deliberate, reviewed act by
# the layering owner (AGT-01), not an accident of `os.walk`.
#
#   FORBIDDEN            -> governed HERE by an explicit import rule (enforced).
#   DELEGATED_TOPLEVEL   -> governed, but by a DIFFERENT dedicated --root run.
#   UNGOVERNED_TOPLEVEL  -> deliberately outside the layering constitution; the
#                           reason is the dict value and is printed in --json.
DELEGATED_TOPLEVEL = {
    "pixelart_creator": (
        "the three-layer client; governed by its own dedicated run: "
        "check_layering.py --root pixelart_creator (CI runs both roots)"
    ),
}

UNGOVERNED_TOPLEVEL = {
    "tests": "test harness — exempt via is_test_module(); crosses layers by design",
    # `testing/` is not `tests/`. The tests themselves stay in tests/ and
    # web_viewer/tests/; this is the harness AROUND them, and it is a sys.path
    # directory rather than a package (no __init__.py), so the runner's child
    # interpreters load `sitecustomize` by bare name, never `testing.*`.
    "testing": (
        "test-run harness around tests/ — runner wrappers, cleanup ring, "
        "coverage viewer; a sys.path directory, not a package: nothing "
        "imports it and it ships in no wheel"
    ),
    "scripts": "standalone P11 dev/CI scripts — not shipped, not in the import graph",
    "deploy": "VPS self-hosting artifacts — the launcher IS the backend entrypoint",
    "packaging": "pyside6-deploy / Nuitka specs + build helpers — build-time only",
    "docs": "product documentation — no shipped import graph",
    "specs": "SDD artifacts — no shipped import graph",
    "i18n": "Qt translation catalogues (.ts/.qm) — no shipped import graph",
}

# Directories that are never walked: VCS/tooling/build artefacts and virtualenvs.
# They hold no first-party source, and pruning them is what keeps the
# fail-closed rule above USABLE on a developer machine — an un-pruned local
# `.venv/` or `build/` would otherwise be reported as an unregistered top-level
# package. This set is itself part of the registry: adding a name to it is a
# deliberate act with the same review weight as UNGOVERNED_TOPLEVEL.
PRUNE_DIRS = frozenset(
    {
        ".git",
        ".github",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        ".env",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "node_modules",
        "build",
        "dist",
        ".eggs",
        "htmlcov",
        "site-packages",
    }
)

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


def is_pruned_dir(name):
    """True for a tooling/build/VCS directory that must never be walked."""
    return name in PRUNE_DIRS or name.endswith(".egg-info")


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
    # top-level name -> {"modules": N, "example": first file seen}. NON-EMPTY
    # means an unregistered top-level package exists: the gate FAILS (exit 1).
    unregistered = {}
    # Modules sitting directly in the scan root (e.g. pixelart_creator/__init__.py
    # under --root pixelart_creator): they belong to NO layer, so no layer rule
    # can apply. They are exempt, but they are now COUNTED AND REPORTED instead
    # of being silently dropped.
    root_modules = []
    exempt = {}
    scanned = 0
    try:
        for dirpath, dirs, files in os.walk(args.root):
            # Prune in place so os.walk never descends into tooling/build trees.
            dirs[:] = sorted(d for d in dirs if not is_pruned_dir(d))
            for name in sorted(files):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                if is_test_module(path, args.root):
                    continue
                rel = os.path.relpath(path, args.root).replace("\\", "/")
                layer = module_layer(path, args.root)
                rules = FORBIDDEN.get(layer)
                if rules is None:
                    # FAIL CLOSED. Every unrecognised top-level name is either an
                    # explicitly registered exemption or a hard error — never a
                    # silent skip (that was the fail-open defect).
                    if rel == layer:
                        # A module directly in the scan root: no layer to apply.
                        root_modules.append(rel)
                    elif layer in DELEGATED_TOPLEVEL or layer in UNGOVERNED_TOPLEVEL:
                        exempt[layer] = exempt.get(layer, 0) + 1
                    else:
                        entry = unregistered.setdefault(
                            layer, {"modules": 0, "example": rel}
                        )
                        entry["modules"] += 1
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
    unregistered_list = [
        {"top_level": k, "modules": v["modules"], "example": v["example"]}
        for k, v in sorted(unregistered.items())
    ]
    result = {
        "violations": violations,
        "scanned": scanned,
        "unregistered": unregistered_list,
        "exempt": {
            k: {
                "modules": exempt[k],
                "reason": DELEGATED_TOPLEVEL.get(k) or UNGOVERNED_TOPLEVEL.get(k),
                "kind": "delegated" if k in DELEGATED_TOPLEVEL else "ungoverned",
            }
            for k in sorted(exempt)
        },
        "root_modules": sorted(root_modules),
    }
    if violations or unregistered_list or args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    if unregistered_list:
        # FAIL CLOSED: an unrecognised top-level package is a gate FAILURE, not
        # a silent skip. Registering it is a deliberate act (see the registry).
        for item in unregistered_list:
            sys.stderr.write(
                "check_layering: UNREGISTERED top-level package %r "
                "(%d module(s), e.g. %s) — it is enforced by NOTHING.\n"
                % (item["top_level"], item["modules"], item["example"])
            )
        sys.stderr.write(
            "check_layering: register it in FORBIDDEN (give it an import rule), "
            "DELEGATED_TOPLEVEL (its own --root run) or UNGOVERNED_TOPLEVEL "
            "(with a reason) in scripts/check_layering.py.\n"
        )
    if violations:
        sys.stderr.write(
            "check_layering: %d layering violation(s).\n" % len(violations)
        )
    if violations or unregistered_list:
        return 1
    sys.stderr.write(
        "check_layering: clean (%d modules; %d root module(s), %d exempt top-level "
        "package(s), 0 unregistered).\n" % (scanned, len(root_modules), len(exempt))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
