#!/usr/bin/env python
# =============================================================================
# SCRIPT: string_audit_check  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Report (not fix) user-visible string literals in ui/ code that are
#   NOT wrapped in a translation call (self.tr(...)/tr(...)/QCoreApplication
#   .translate(...)/QObject.tr), and flag `+`-concatenation of translatable
#   strings (which breaks i18n word order). Backs AGT-07's string audit.
# FLAVOUR: standalone
# LOCATION: scripts/string_audit_check.py
# INVOKED BY: AGT-07 Localisation (string audit on every AGT-05 output);
#   AGT-09 CI (optional lint step).
# RUNTIME: Python 3.8+ (CPython, stdlib only: ast, argparse, json, os, sys).
# ENTRYPOINT: python scripts/string_audit_check.py [paths ...]
#             [--root pixelart_creator/ui]
# INPUTS:
#   paths   (CLI positional, optional): explicit changed .py files to scan.
#   --root  (CLI arg, optional, default "pixelart_creator/ui"): scanned if no
#           explicit paths are given.
# OUTPUTS:
#   stdout: JSON {"findings":[{file,line,kind,text}], "scanned":N}.
#   stderr: human summary. exit code per EXIT CODES.
# EXIT CODES: 0 clean -> COMPLETED ; 1 findings (report) -> reported to AGT-07,
#   maps to PARTIAL for the audited change (report-not-fix) ; 2 error -> BLOCKED.
# PRECONDITIONS: target paths exist and are Python source.
# DETERMINISM NOTE: deterministic; a fixed set of user-facing Qt setter method
#   names is checked; findings sorted by (file, line). Heuristic (AST), report-only.
#
# ## Principles Applied
# Inherited: P1 (grounded FIX-06/07 + Qt tr() i18n), P2, P3, P4, P6 (stdlib),
#   P7, P9 (one job: unwrapped-string audit; reports, never edits), P10, P11,
#   P12 (setter-arg + concatenation checks), P13.
# Custom: (none)
#
# SOURCES: Dossier §6.5/§8 (owner AGT-07); FIX-06/07 (Dossier §2 F5/F6);
#   Qt for Python i18n docs (tr/translate); asset-templates.md §Script.
# =============================================================================
import argparse
import ast
import json
import os
import sys

# Qt methods whose (first) string argument is user-visible and must be tr()-wrapped.
USER_FACING_SETTERS = {
    "setText", "setWindowTitle", "setToolTip", "setStatusTip", "setPlaceholderText",
    "setTitle", "addItem", "addAction", "setLabelText", "setWhatsThis",
    "setAccessibleName", "setAccessibleDescription", "insertItem", "setItemText",
    "setTabText", "information", "warning", "critical", "question", "setPrefix",
    "setSuffix",
}
TR_FUNCS = {"tr", "translate", "trUtf8"}


def is_tr_call(node):
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr in TR_FUNCS:
        return True
    if isinstance(fn, ast.Name) and fn.id in TR_FUNCS:
        return True
    return False


def nonempty_str(node):
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value.strip() != "")


class Auditor(ast.NodeVisitor):
    def __init__(self, relpath):
        self.rel = relpath
        self.findings = []

    def visit_Call(self, node):
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr in USER_FACING_SETTERS:
            for arg in node.args:
                if nonempty_str(arg):
                    self.findings.append({
                        "file": self.rel, "line": arg.lineno,
                        "kind": "unwrapped-string",
                        "text": arg.value[:80]})
                    break
        self.generic_visit(node)

    def visit_BinOp(self, node):
        if isinstance(node.op, ast.Add):
            if is_tr_call(node.left) or is_tr_call(node.right):
                self.findings.append({
                    "file": self.rel, "line": node.lineno,
                    "kind": "tr-concatenation",
                    "text": "translated string joined with '+' (breaks word order)"})
        self.generic_visit(node)


def collect(paths, root):
    files = []
    if paths:
        files = [p for p in paths if p.endswith(".py") and os.path.isfile(p)]
    elif os.path.isdir(root):
        for dp, _d, fs in os.walk(root):
            for n in sorted(fs):
                if n.endswith(".py"):
                    files.append(os.path.join(dp, n))
    return sorted(set(files))


def main():
    ap = argparse.ArgumentParser(description="Audit ui/ for unwrapped translatable strings.")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--root", default=os.path.join("pixelart_creator", "ui"))
    args = ap.parse_args()

    files = collect(args.paths, args.root)
    findings = []
    try:
        for path in files:
            with open(path, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            aud = Auditor(path.replace("\\", "/"))
            aud.visit(tree)
            findings.extend(aud.findings)
    except (SyntaxError, OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("string_audit_check: error: %r\n" % exc)
        print(json.dumps({"findings": findings, "error": repr(exc)}))
        return 2

    findings.sort(key=lambda f: (f["file"], f["line"]))
    print(json.dumps({"findings": findings, "scanned": len(files)},
                     indent=2, sort_keys=True))
    if findings:
        sys.stderr.write("string_audit_check: %d finding(s) for AGT-07 review.\n"
                         % len(findings))
        return 1
    sys.stderr.write("string_audit_check: clean (%d files).\n" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
