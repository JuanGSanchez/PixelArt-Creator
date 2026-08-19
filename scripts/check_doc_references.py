#!/usr/bin/env python
# =============================================================================
# SCRIPT: check_doc_references  (standalone P11 script — PixelArt Creator)
# =============================================================================
# PURPOSE: Catch documentation going stale WITHOUT anyone noticing, two ways
#   at once (a two-surface diff alone cannot catch either, see DETERMINISM
#   NOTE below):
#   LEG 1 -- ADR citation resolution. Every `ADR-NNNN` citation found anywhere
#     in product source/docs/workflows must resolve to a real file under
#     docs/adr/. A citation to an ADR number that was never written (a
#     drafting slip, a renumbering left half-done) is reported by file+line.
#   LEG 2 -- documentation currency, anchored OUTSIDE the documents, on
#     FEATURE-LEVEL UI surfaces only (narrowed 2026-08-19 from "every
#     tr()-wrapped string" -- see the LEG 2 section below for the four
#     surfaces and why). Derives the set of shipped, user-facing FEATURE
#     labels straight from the UI source (`pixelart_creator/ui/**/*.py`):
#     window/dialog titles (setWindowTitle), group/menu titles (setTitle,
#     addMenu), menu/toolbar actions (addAction, a QAction(text, ...)
#     constructor, or setText() on a QAction-typed receiver), primary panel
#     controls (setText() on a QPushButton/QToolButton/QCheckBox/
#     QRadioButton-typed receiver), and file-dialog captions (the 2nd
#     positional arg of the three QFileDialog static pickers) -- and
#     reports any such label that appears in NEITHER documentation surface
#     -- the mkdocs usage pages (docs/site/pages/) NOR the in-app user guide
#     (pixelart_creator/userguide_content/content/) -- in EITHER shipped
#     language (en/es are checked as their OWN pair, see below; a label is
#     never cleared by an unrelated language's coverage). Tooltips, status/
#     accessible text, placeholder text, field/unit QLabel captions and
#     combo/list item text are deliberately out of this leg's anchor -- not
#     a capability a user looks up by name.
# FLAVOUR: standalone
# LOCATION: scripts/check_doc_references.py
# INVOKED BY: AGT-09 CI (doc-currency gate); AGT-08 Documenter (pre-flight
#   before publishing CHANGELOG/ADR/site updates).
# RUNTIME: Python 3.8+ (CPython, stdlib only: ast, argparse, json, os, re,
#   sys, xml.etree.ElementTree).
# ENTRYPOINT: python scripts/check_doc_references.py [--root .]
#             [--allowlist doc-reference-allowlist.json]
#             [--baseline doc-reference-baseline.json] [--write-baseline]
# INPUTS:
#   --root      (CLI arg, optional, default "."): repo root, matching the
#               neighbour scripts' `--root .` CI convention (run from the
#               checkout root, no working-directory override).
#   --allowlist (CLI arg, optional, default "doc-reference-allowlist.json"
#               under --root, i.e. the repository root -- NOT docs/, which is
#               gitignored by a deliberate privacy allowlist (docs/* in
#               .gitignore) and would silently strand this CI-gate state
#               file as untracked): a JSON array of
#               {"type": "adr-citation"|"control-label", "value": "...",
#                "reason": "..."} objects. Each entry is a DELIBERATE,
#               reviewable suppression (a tooltip, an internal debug action,
#               a dialog caption nobody documents by name) -- never a silent
#               skip. A missing allowlist file is NOT an error: it is reported
#               on stderr as "0 entries" so the escape hatch stays visible
#               even when unused; it is not created by this script.
#   --baseline  (CLI arg, optional, default "doc-reference-baseline.json"
#               under --root, same rationale as --allowlist above): a JSON
#               array of {"kind","value","file","line"}
#               objects -- known, tracked documentation debt (see
#               BASELINE-AND-RATCHET above). A missing baseline file is NOT
#               an error: it is reported on stderr as "0 entries", which
#               means every live finding is treated as new (fails the gate).
#   --write-baseline (CLI flag): regenerate the baseline file from the
#               CURRENT live (post-allowlist) findings and exit 0 without
#               running the ratchet comparison. Maintenance mode only.
# OUTPUTS:
#   stdout: JSON {"findings":[{kind,file,line,...,"baselined":bool}],
#            "scanned":{...}, "allowlist_entries": N,
#            "allowlist_suppressed": N, "allowlist_suppressed_detail":{...},
#            "baseline_entries": N, "new_findings":[...],
#            "stale_baseline_entries":[...], "likely_renames":[...]}.
#            "allowlist_suppressed" is the count of findings the allowlist
#            actually prevented THIS RUN, not the size of the allowlist
#            file -- an entry that never matches a live finding suppresses
#            nothing and is never counted as if it did. Same logic applies
#            to "baseline_entries" vs the entries actually matched.
#   stderr: human summary, INCLUDING the suppression count every run (even
#            zero) -- a suppression nobody sees on stderr is how a gate goes
#            quietly stale. exit code per EXIT CODES.
# EXIT CODES: 0 clean (no new findings, no stale baseline entries) ->
#   COMPLETED ; 1 new finding(s) and/or stale baseline entry(ies) -> FAILED
#   (doc currency gate blocks) ; 2 error -> BLOCKED. --write-baseline always
#   exits 0 on success, 2 on error.
# PRECONDITIONS: --root exists; docs/adr/, docs/site/pages/,
#   pixelart_creator/userguide_content/content/, pixelart_creator/ui/ exist
#   under --root (a missing surface is reported, not silently treated as
#   "nothing to check").
# DETERMINISM NOTE: deterministic; no network, no time/random. Findings sorted
#   by (kind, file, line, value). LEG 2 is heuristic (AST + substring match on
#   normalised label text) and intentionally does NOT hardcode any specific
#   ADR number or label: it re-derives the ADR registry from docs/adr/'s own
#   filenames and the label set from the UI source on every run, so it keeps
#   catching NEW dangling citations / undocumented labels after today's are
#   fixed, not just today's. A previous audit established that the two
#   documentation surfaces can be perfectly consistent WITH EACH OTHER and
#   uniformly silent on a shipped feature -- a surface-to-surface diff cannot
#   detect that class at all, which is why LEG 2 is anchored on the UI source,
#   not on comparing the two doc trees to each other.
# LOCALE HANDLING (LEG 2): both documentation surfaces ship en/es. A label is
#   checked against the EN corpus (site en/ + guide content/en/) using its
#   literal EN source text, AND separately against the ES corpus (site es/ +
#   guide content/es/) using its shipped ES translation, read from
#   i18n/pixelart_es.ts (`<source>` -> finished `<translation>`; an
#   unfinished/absent ES translation falls back to checking the literal EN
#   text against the ES corpus, since Spanish pages sometimes keep an
#   English proper-noun label as-is). Three outcomes, not one:
#     "undocumented-control-label" -- missing from BOTH language corpora.
#     "es-documentation-stale"     -- documented in en/, missing from es/.
#     "en-documentation-stale"     -- documented in es/, missing from en/.
#   A check that only ever looked at English would report "documented" the
#   day the Spanish half silently falls behind; it would be certifying a
#   property it never tested. This gate tests both halves independently.
#
# ## Principles Applied
# Inherited: P1 (grounded in ADR-0029's in-app guide + the mkdocs site, both
#   AGT-08-owned; the label set is grounded in the shipped UI source, never
#   guessed), P2, P3, P4, P6 (stdlib only), P7, P9 (one job: doc-reference
#   currency; report-only, fixes nothing), P10, P11 (programmatic gate, exit
#   code is the verdict), P12 (ADR-citation-resolution + label-currency +
#   locale-pair checks), P13.
# Custom: no hardcoded ADR numbers or label literals anywhere in this file --
#   both registries (valid ADRs, shipped labels) are re-derived from the tree
#   on every run, per the user's explicit "no hardcoded expectations"
#   requirement; an allowlist file (not created by this script) is the only
#   sanctioned, reviewable escape hatch for an unavoidable false positive.
#
# SOURCES: user dispatch 2026-08-19 (gate to prevent undocumented-feature
#   recurrence, "programmatic gate... regression tests" requirement); ADR-0029
#   (in-app user guide ships under pixelart_creator/userguide_content/);
#   asset-templates.md §Script; scripts/string_audit_check.py and
#   scripts/path_portability_check.py (house style for standalone P11
#   scripts, JSON findings + human stderr summary + 0/1/2 exit codes).
#
# BASELINE-AND-RATCHET (added 2026-08-19, user decision -- "note them for
#   future development... they might provoke new fails in the CI"): the 145
#   findings live at 2026-08-19 are recorded in --baseline (default
#   doc-reference-baseline.json under repo root), a REVIEWABLE debt ledger,
#   distinct
#   from the allowlist:
#     allowlist = "needs no documentation, ever"      (a permanent exemption)
#     baseline  = "documentation owed, not yet written" (a TEMPORARY, tracked
#                 debt -- see design-docs/auxiliary/doc-currency-debt-20260819.md
#                 for the human-readable breakdown AGT-08 owes against it)
#   The two are never merged: an allowlisted finding never reaches the
#   baseline comparison at all (it is filtered out upstream, same as today).
#
#   KEY DESIGN: a baseline entry is keyed on (kind, value) for every kind
#   EXCEPT dangling-adr-citation, which is keyed on (kind, value, file).
#   Line number is NEVER part of the key -- an unrelated edit two lines
#   above a citation or a label site must not churn the baseline. For the
#   three label-leg kinds the label-leg itself already dedupes to one
#   finding per distinct label text (collect_ui_labels reports only the
#   FIRST location), so (kind, value) is already the finding's natural
#   identity -- adding file/line would just re-introduce the churn the key
#   is designed to avoid. For dangling-adr-citation the SAME missing ADR
#   number is typically cited from many unrelated files (ADR-0056: 13
#   occurrences across 8 files in the 2026-08-19 baseline) -- collapsing
#   those to (kind, value) alone would let a citation added to a NINTH file
#   pass silently as "already known debt", which is exactly the silent
#   regression this gate exists to catch; keeping `file` in the key for
#   this leg only means a genuinely new citation SITE is a new finding even
#   when the same missing ADR number is already partially baselined,
#   while a same-file, same-number citation that merely moves lines still
#   matches its existing entry.
#
#   TWO FAILURE MODES, reported distinctly:
#     "new-finding"          -- a live finding whose key is not in the
#       baseline. Two sub-cases, both surfaced under this heading because
#       both are, mechanically, an unbaselined finding -- the human summary
#       calls out which applies:
#         * no correlated stale entry -> genuinely new documentation debt
#           (a newly shipped, undocumented feature, or a fresh dangling
#           citation). Fix by writing the docs, or add a baseline entry if
#           the debt is accepted.
#         * a correlated stale entry exists for the same (kind, file) ->
#           very likely a RENAME/MOVE of an already-baselined item, not new
#           debt. Fix by editing the existing baseline entry's "value" (and
#           "file" for the adr-citation leg) to the new identity -- do NOT
#           add a second entry and leave the old one to rot.
#     "stale-baseline-entry" -- a baseline entry whose key no longer
#       matches any live finding. THIS GATE TREATS A STALE ENTRY AS A
#       FAILURE (exit 1), not a warning, by deliberate choice: an entry
#       nobody prunes is indistinguishable, from the next reader's chair,
#       from an entry nobody is maintaining -- and a baseline that silently
#       tolerates drift decays into exactly the blanket suppression this
#       whole mechanism exists to prevent (the user's own stated instinct,
#       and this script agrees for the same reason the allowlist is never
#       silently permissive: C5-class self-correction has to be visible,
#       not assumed). The fix is cheap either way -- delete the entry if
#       the underlying defect was actually fixed, or edit its value/file if
#       it was renamed -- so failing costs a maintainer one glance at
#       stderr, while warning-only would cost nothing and therefore be
#       ignored the first time it fires for a real reason.
#   --write-baseline replaces the baseline file with EVERY current live
#   (post-allowlist) finding, deduped by key, and exits 0 without running
#   the ratchet comparison -- the explicit, reviewable path a maintainer
#   takes after clearing or renaming an item (never hand-edit the JSON's
#   structure; regenerate then diff).
# =============================================================================
import argparse
import ast
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# LEG 1 -- ADR citation resolution.
# ---------------------------------------------------------------------------
ADR_CITATION_RE = re.compile(r"\bADR-(\d{4})\b")
ADR_FILENAME_RE = re.compile(r"^(\d{4})-")
ADR_TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".json",
    ".txt",
    ".rst",
    ".cfg",
    ".ini",
    ".ts",
}
# Directories scanned for citations: "product source, docs, workflows"
# (dispatch scope). `memory/` (the product's own System Memory Graph store)
# is deliberately OUT of scope here -- it is a generated projection of the
# commit history, not authored documentation or source, and is audited on
# its own terms (`memory_graph.py verify`).
ADR_SCAN_DIRS = [
    "pixelart_creator",
    "scripts",
    "sync_backend",
    "web_viewer",
    "tests",
    "deploy",
    "packaging",
    "docs",
    ".github",
    "i18n",
]
SELF_BASENAME = os.path.basename(__file__)


def collect_adr_citations(root, exclude_basenames=None):
    """Return sorted [{file,line,citation}] for every ADR-NNNN citation found
    under ADR_SCAN_DIRS + top-level *.md files, one entry per (file, line,
    number) occurrence -- a line citing two different numbers yields two
    findings-candidates, resolved independently below.

    `exclude_basenames` additionally skips this gate's OWN generated
    artifacts (the baseline/allowlist JSON files, which live under docs/ --
    inside ADR_SCAN_DIRS -- and legitimately CONTAIN literal "ADR-NNNN"
    strings as data, not as citations to resolve): without this exclusion
    the gate would report its own baseline file as a dangling citation the
    moment a dangling-adr-citation entry is written into it."""
    exclude = {SELF_BASENAME} | set(exclude_basenames or ())
    citations = []
    files = []
    for inc in ADR_SCAN_DIRS:
        base = os.path.join(root, inc)
        if os.path.isfile(base):
            files.append(base)
        elif os.path.isdir(base):
            for dp, _d, fs in os.walk(base):
                for n in sorted(fs):
                    if n in exclude:
                        continue
                    _stem, ext = os.path.splitext(n)
                    if ext.lower() in ADR_TEXT_EXTENSIONS:
                        files.append(os.path.join(dp, n))
    for n in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        full = os.path.join(root, n)
        if os.path.isfile(full) and n.lower().endswith(".md"):
            files.append(full)
    files = sorted(set(files))

    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="strict") as fh:
                lines = fh.readlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = os.path.relpath(path, root).replace("\\", "/")
        for i, line in enumerate(lines, start=1):
            for m in ADR_CITATION_RE.finditer(line):
                citations.append(
                    {"file": rel, "line": i, "citation": "ADR-%s" % m.group(1)}
                )
    return citations


def valid_adr_numbers(root):
    """Derive the set of ADR numbers that actually exist on disk from
    docs/adr/'s own filenames (`NNNN-slug.md`) -- never a hardcoded ceiling,
    so the check keeps working after the next ADR is authored."""
    adr_dir = os.path.join(root, "docs", "adr")
    valid = set()
    if os.path.isdir(adr_dir):
        for n in os.listdir(adr_dir):
            m = ADR_FILENAME_RE.match(n)
            if m and n.lower().endswith(".md"):
                valid.add(m.group(1))
    return valid


def adr_leg_findings(root, exclude_basenames=None):
    valid = valid_adr_numbers(root)
    findings = []
    for c in collect_adr_citations(root, exclude_basenames=exclude_basenames):
        num = c["citation"].split("-", 1)[1]
        if num not in valid:
            findings.append(
                {
                    "kind": "dangling-adr-citation",
                    "file": c["file"],
                    "line": c["line"],
                    "value": c["citation"],
                }
            )
    return findings


# ---------------------------------------------------------------------------
# LEG 2 -- documentation currency, anchored on FEATURE-LEVEL UI surfaces.
# ---------------------------------------------------------------------------
# Narrowed (2026-08-19 dispatch) from "every tr()-wrapped string" (913
# distinct under pixelart_creator/ui -- mostly tooltips, field labels and
# list items nobody looks up in a manual) to labels that reach the user as
# one of four feature-level surfaces:
#   - a window/dialog title       -- setWindowTitle(...)
#   - a group/panel/menu title    -- setTitle(...), addMenu(...)
#   - a menu or toolbar action    -- addAction(...); QAction(text, ...)
#                                    built with its label passed straight to
#                                    the constructor; or setText() on an
#                                    object that WAS constructed as
#                                    QAction(...)
#   - a primary panel control     -- setText() on an object constructed as
#                                    QPushButton/QToolButton/QCheckBox/
#                                    QRadioButton(...) -- the click target
#                                    that invokes a capability, never a
#                                    QLabel caption
#   - a file-dialog caption       -- the 2nd positional arg of the three
#                                    QFileDialog static pickers (a dialog
#                                    title in substance)
# Tooltips, status tips, accessible name/description, placeholder text,
# field/unit QLabel captions, and combo/list item text (addItem/insertItem/
# setItemText/setTabText/setLabelText) are deliberately OUT of this leg's
# anchor -- supplementary or enumerable content, not a capability a user
# looks up by name -- and are the natural allowlist target if one specific
# instance does need documenting on its own.
#
# The "primary control" set is derived per FILE from the UI source itself,
# never a fixed label list: pass 1 (_collect_primary_control_names) records
# which attribute/local names were constructed from a
# PRIMARY_CONTROL_CTORS type; pass 2 (_LabelVisitor) only counts a
# setText() call as feature-level if its receiver resolves to one of those
# names. A name only ever assigned to a QLabel never qualifies, however
# many setText() calls it collects.
PRIMARY_CONTROL_CTORS = {
    "QPushButton",
    "QToolButton",
    "QCheckBox",
    "QRadioButton",
    "QAction",
}
TITLE_METHS = {"setWindowTitle", "setTitle"}
MENU_METHS = {"addAction", "addMenu"}
# QFileDialog static pickers: signature is (parent, caption, dir, filter, ...)
# -- the caption (2nd positional) is a real, user-visible dialog title.
FILE_DIALOG_METHS = {"getSaveFileName", "getOpenFileName", "getExistingDirectory"}
TR_FUNCS = {"tr", "translate", "trUtf8"}


def _tr_string(node):
    """If `node` is a tr()/translate()/trUtf8() call whose first argument is
    a non-empty string constant, return that string; else None."""
    if not isinstance(node, ast.Call):
        return None
    fn = node.func
    is_attr_tr = isinstance(fn, ast.Attribute) and fn.attr in TR_FUNCS
    is_name_tr = isinstance(fn, ast.Name) and fn.id in TR_FUNCS
    if not (is_attr_tr or is_name_tr):
        return None

    def _const_str(i):
        if (
            len(node.args) > i
            and isinstance(node.args[i], ast.Constant)
            and isinstance(node.args[i].value, str)
            and node.args[i].value.strip() != ""
        ):
            return node.args[i].value
        return None

    # QCoreApplication.translate(context, sourceText, disambiguation=None,
    # n=-1) is the module-level form this codebase uses for non-QObject
    # code (QGraphicsItem subclasses, free functions -- see
    # ui/reference_board.py, ui/tilemap_io_actions.py, ui/tools/*): its
    # FIRST argument is a translation-context string (a class/module name,
    # e.g. "tools"), not the visible text -- the visible text is the
    # SECOND argument. `self.tr(text)` / `self.trUtf8(text)` and a
    # single-argument `translate(text)` keep the first argument.
    if (
        fn.attr == "translate"
        if isinstance(fn, ast.Attribute)
        else fn.id == "translate"
    ):
        if len(node.args) >= 2:
            return _const_str(1)
        return _const_str(0)
    return _const_str(0)


def _ctor_type(node):
    """If `node` is a bare `SomeQtClass(...)` constructor call, return the
    class name -- handles both the plain imported name (`QPushButton(...)`)
    and a module-qualified one (`QtWidgets.QPushButton(...)`); else None."""
    if not isinstance(node, ast.Call):
        return None
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _receiver_key(expr):
    """Resolve an assignment target OR a method-call receiver to the same
    key shape, so pass 1 (constructor assignments) and pass 2 (setText
    receivers) address the same names: `self._x` -> "self._x"; a bare local
    `x` -> "x"; anything else (tuple/subscript targets, attribute chains
    deeper than self.X) -> None, deliberately conservative -- it only
    narrows recall, it never invents a false match."""
    if (
        isinstance(expr, ast.Attribute)
        and isinstance(expr.value, ast.Name)
        and expr.value.id == "self"
    ):
        return "self.%s" % expr.attr
    if isinstance(expr, ast.Name):
        return expr.id
    return None


def _collect_primary_control_names(tree):
    """Pass 1: {name_key: ctor_type} for every assignment whose RHS is a
    bare PRIMARY_CONTROL_CTORS constructor call, scanned across the whole
    module. A name key reused for an unrelated widget elsewhere in the same
    file is an accepted false-permissive -- it only widens recall, it never
    hides a real feature-level label."""
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            ctor = _ctor_type(node.value)
            if ctor in PRIMARY_CONTROL_CTORS:
                for t in node.targets:
                    key = _receiver_key(t)
                    if key:
                        names[key] = ctor
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            ctor = _ctor_type(node.value)
            if ctor in PRIMARY_CONTROL_CTORS:
                key = _receiver_key(node.target)
                if key:
                    names[key] = ctor
    return names


class _LabelVisitor(ast.NodeVisitor):
    def __init__(self, rel, primary_names):
        self.rel = rel
        self.primary_names = primary_names
        self.labels = []  # [(text, file, line)]

    def visit_Call(self, node):
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr in (TITLE_METHS | MENU_METHS):
            for arg in node.args:
                txt = _tr_string(arg)
                if txt is not None:
                    self.labels.append((txt, self.rel, arg.lineno))
                    break
        elif isinstance(fn, ast.Attribute) and fn.attr == "setText":
            key = _receiver_key(fn.value)
            if key and self.primary_names.get(key) in PRIMARY_CONTROL_CTORS:
                for arg in node.args:
                    txt = _tr_string(arg)
                    if txt is not None:
                        self.labels.append((txt, self.rel, arg.lineno))
                        break
        elif isinstance(fn, ast.Name) and fn.id == "QAction":
            # A menu/toolbar action built with its label passed straight to
            # the constructor: QAction(text, parent) / QAction(text).
            for arg in node.args:
                txt = _tr_string(arg)
                if txt is not None:
                    self.labels.append((txt, self.rel, arg.lineno))
                    break
        elif isinstance(fn, ast.Attribute) and fn.attr in FILE_DIALOG_METHS:
            for arg in node.args[1:]:
                txt = _tr_string(arg)
                if txt is not None:
                    self.labels.append((txt, self.rel, arg.lineno))
                    break
        self.generic_visit(node)


_MNEMONIC_DOUBLE = "\x00"


def normalize_label(text):
    """Strip Qt mnemonic markers (`&File` -> `File`, `&&` -> literal `&`) and
    ellipses (`Save…` / `Save...` -> `Save`) so a menu-chrome artefact does
    not masquerade as a distinct label, then collapse whitespace."""
    s = text.replace("&&", _MNEMONIC_DOUBLE)
    s = re.sub(r"&(?=\S)", "", s)
    s = s.replace(_MNEMONIC_DOUBLE, "&")
    s = s.replace("…", "").replace("...", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def collect_ui_labels(root):
    """Return {normalized_label: [(file, line), ...]} scanning
    pixelart_creator/ui/**/*.py. Returns (labels, scanned_file_count,
    error) -- error is None unless a file could not be parsed."""
    ui_dir = os.path.join(root, "pixelart_creator", "ui")
    labels = {}
    scanned = 0
    if not os.path.isdir(ui_dir):
        return labels, scanned, "pixelart_creator/ui not found under --root"
    for dp, _d, fs in os.walk(ui_dir):
        for n in sorted(fs):
            if not n.endswith(".py"):
                continue
            path = os.path.join(dp, n)
            rel = os.path.relpath(path, root).replace("\\", "/")
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    src = fh.read()
                tree = ast.parse(src, filename=path)
            except (SyntaxError, OSError, UnicodeDecodeError) as exc:
                return labels, scanned, "%s: %r" % (rel, exc)
            scanned += 1
            primary_names = _collect_primary_control_names(tree)
            v = _LabelVisitor(rel, primary_names)
            v.visit(tree)
            for text, f, line in v.labels:
                norm = normalize_label(text)
                if not norm:
                    continue
                labels.setdefault(norm, []).append((f, line))
    return labels, scanned, None


def load_es_translations(root):
    """Map EN <source> text -> shipped, FINISHED ES <translation> text from
    i18n/pixelart_es.ts. A missing/unfinished/empty translation is simply
    absent from the map (the leg-2 locale check then falls back to checking
    the literal EN text against the ES corpus)."""
    path = os.path.join(root, "i18n", "pixelart_es.ts")
    mapping = {}
    if not os.path.isfile(path):
        return mapping, "i18n/pixelart_es.ts not found under --root"
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return mapping, "i18n/pixelart_es.ts: %r" % exc
    for msg in tree.getroot().iter("message"):
        src = msg.find("source")
        trn = msg.find("translation")
        if src is None or trn is None or src.text is None:
            continue
        if trn.get("type") == "unfinished":
            continue
        if trn.text is None or trn.text.strip() == "":
            continue
        mapping.setdefault(src.text, trn.text)
    return mapping, None


def _load_markdown_corpus(dirpath):
    """Concatenate every *.md file under dirpath (recursively), lower-cased,
    for substring matching. Returns (corpus_text, file_count)."""
    parts = []
    count = 0
    if os.path.isdir(dirpath):
        for dp, _d, fs in os.walk(dirpath):
            for n in sorted(fs):
                if n.endswith(".md"):
                    path = os.path.join(dp, n)
                    try:
                        with open(path, "r", encoding="utf-8") as fh:
                            parts.append(fh.read())
                        count += 1
                    except (OSError, UnicodeDecodeError):
                        continue
    return "\n".join(parts).lower(), count


def label_leg_findings(root, allow_labels):
    labels, ui_scanned, err = collect_ui_labels(root)
    if err:
        return None, {"ui_files_scanned": ui_scanned}, err

    es_translations, es_err = load_es_translations(root)

    site_en, site_en_n = _load_markdown_corpus(
        os.path.join(root, "docs", "site", "pages", "en")
    )
    site_es, site_es_n = _load_markdown_corpus(
        os.path.join(root, "docs", "site", "pages", "es")
    )
    guide_en, guide_en_n = _load_markdown_corpus(
        os.path.join(root, "pixelart_creator", "userguide_content", "content", "en")
    )
    guide_es, guide_es_n = _load_markdown_corpus(
        os.path.join(root, "pixelart_creator", "userguide_content", "content", "es")
    )
    en_corpus = site_en + "\n" + guide_en
    es_corpus = site_es + "\n" + guide_es

    findings = []
    label_suppressed = []  # [{"value","kind"}] -- would-be findings the
    # allowlist actually prevented, computed BEFORE the allow_labels check
    # so a label that was never going to be a finding (already documented)
    # is never miscounted as "suppressed".
    for label, locs in sorted(labels.items()):
        label_l = label.lower()
        en_doc = label_l in en_corpus

        es_label = es_translations.get(label)
        if es_label:
            es_doc = normalize_label(es_label).lower() in es_corpus
        else:
            es_doc = label_l in es_corpus

        if not en_doc and not es_doc:
            kind = "undocumented-control-label"
        elif en_doc and not es_doc:
            kind = "es-documentation-stale"
        elif es_doc and not en_doc:
            kind = "en-documentation-stale"
        else:
            continue

        if label in allow_labels:
            label_suppressed.append({"value": label, "kind": kind})
            continue

        f, line = sorted(locs)[0]
        findings.append(
            {
                "kind": kind,
                "file": f,
                "line": line,
                "value": label,
                "other_locations": len(locs) - 1,
            }
        )

    scanned = {
        "ui_files_scanned": ui_scanned,
        "distinct_labels": len(labels),
        "site_en_pages": site_en_n,
        "site_es_pages": site_es_n,
        "guide_en_pages": guide_en_n,
        "guide_es_pages": guide_es_n,
        "es_translations_loaded": len(es_translations),
        "label_allowlist_suppressed": label_suppressed,
    }
    if es_err:
        scanned["es_translations_note"] = es_err
    return findings, scanned, None


# ---------------------------------------------------------------------------
# Allowlist (escape hatch) -- never created by this script.
# ---------------------------------------------------------------------------
def load_allowlist(root, path):
    """Load the optional allowlist JSON. A missing file is NOT an error --
    it is reported (visibly, on stderr) as zero entries, never silently
    assumed. Returns (adr_allow:set[str], label_allow:set[str], count, note)."""
    full = path if os.path.isabs(path) else os.path.join(root, path)
    if not os.path.isfile(full):
        return set(), set(), 0, "not found (0 entries) -- %s" % full
    try:
        with open(full, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return set(), set(), 0, "unreadable (%r), treated as 0 entries" % exc
    adr_allow = set()
    label_allow = set()
    n = 0
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict) or "reason" not in entry:
            continue
        t = entry.get("type")
        v = entry.get("value")
        if not v:
            continue
        if t == "adr-citation":
            adr_allow.add(v)
            n += 1
        elif t == "control-label":
            label_allow.add(v)
            n += 1
    return adr_allow, label_allow, n, None


# ---------------------------------------------------------------------------
# Baseline-and-ratchet (known, tracked documentation debt -- distinct from
# the allowlist above; see BASELINE-AND-RATCHET in the module docstring).
# ---------------------------------------------------------------------------
def finding_key(f):
    """The stable identity of a live finding. Line number is deliberately
    never part of it (an unrelated edit above the site must not churn the
    baseline). dangling-adr-citation additionally keys on `file`: the same
    missing ADR number is routinely cited from many unrelated files, and a
    NEW citing file is real new debt even when the number itself is already
    partially baselined elsewhere. The three label-leg kinds key on
    (kind, value) alone -- collect_ui_labels already dedupes to one finding
    per distinct label text, so (kind, value) IS that finding's identity."""
    if f["kind"] == "dangling-adr-citation":
        return (f["kind"], f["value"], f["file"])
    return (f["kind"], f["value"])


def baseline_entry_key(entry):
    """Same identity shape as finding_key(), computed from a baseline
    entry's stored fields."""
    if entry.get("kind") == "dangling-adr-citation":
        return (entry.get("kind"), entry.get("value"), entry.get("file"))
    return (entry.get("kind"), entry.get("value"))


def load_baseline(root, path):
    """Load the baseline JSON (known, tracked documentation debt). A
    missing file is NOT an error -- reported on stderr as "0 entries",
    which means every live finding is treated as new (the gate fails until
    a baseline is written or the findings are fixed). Returns
    (entries:list[dict], note:str|None)."""
    full = path if os.path.isabs(path) else os.path.join(root, path)
    if not os.path.isfile(full):
        return [], "not found (0 entries) -- %s" % full
    try:
        with open(full, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return [], "unreadable (%r), treated as 0 entries" % exc
    entries = [
        e
        for e in (data if isinstance(data, list) else [])
        if isinstance(e, dict) and e.get("kind") and e.get("value")
    ]
    return entries, None


def write_baseline(root, path, findings):
    """Regenerate the baseline file from CURRENT live (post-allowlist)
    findings, deduped by finding_key(), each entry carrying its first
    (file, line) location as human-readable metadata (never part of the
    match key). Findings are pre-sorted by (kind, file, line, value), so
    "first" is deterministic."""
    full = path if os.path.isabs(path) else os.path.join(root, path)
    seen = {}
    for f in findings:
        key = finding_key(f)
        if key in seen:
            continue
        entry = {
            "kind": f["kind"],
            "value": f["value"],
            "file": f["file"],
            "line": f["line"],
        }
        seen[key] = entry
    entries = sorted(
        seen.values(), key=lambda e: (e["kind"], e["value"], e.get("file") or "")
    )
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(entries, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return len(entries)


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Documentation-currency gate: resolve every ADR-NNNN citation "
            "against docs/adr/, and flag shipped UI control labels documented "
            "in neither the mkdocs site nor the in-app user guide, in neither "
            "shipped language."
        )
    )
    ap.add_argument("--root", default=".")
    ap.add_argument("--allowlist", default="doc-reference-allowlist.json")
    ap.add_argument("--baseline", default="doc-reference-baseline.json")
    ap.add_argument(
        "--write-baseline",
        action="store_true",
        help=(
            "Regenerate --baseline from the current live (post-allowlist) "
            "findings and exit without running the ratchet comparison."
        ),
    )
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.stderr.write("check_doc_references: root not found.\n")
        print(json.dumps({"error": "root-not-found"}))
        return 2

    adr_allow, label_allow, allow_n, allow_note = load_allowlist(
        args.root, args.allowlist
    )
    sys.stderr.write(
        "check_doc_references: allowlist %s: %s\n"
        % (args.allowlist, allow_note if allow_note else "%d entries" % allow_n)
    )

    findings = []
    scanned = {}

    try:
        gate_own_basenames = {
            os.path.basename(args.baseline),
            os.path.basename(args.allowlist),
        }
        all_adr_findings = adr_leg_findings(
            args.root, exclude_basenames=gate_own_basenames
        )
    except OSError as exc:
        sys.stderr.write("check_doc_references: ADR-leg error: %r\n" % exc)
        print(json.dumps({"findings": [], "error": repr(exc)}))
        return 2
    # Suppressed = would-be findings the allowlist actually removed, not the
    # size of the allowlist itself -- an entry for a citation that never
    # resolves as a finding here suppresses nothing and must not be counted
    # as if it did.
    adr_suppressed = [f for f in all_adr_findings if f["value"] in adr_allow]
    adr_findings = [f for f in all_adr_findings if f["value"] not in adr_allow]
    findings.extend(adr_findings)

    label_findings, label_scanned, label_err = label_leg_findings(
        args.root, label_allow
    )
    label_suppressed = label_scanned.pop("label_allowlist_suppressed", [])
    scanned.update(label_scanned)
    if label_err:
        sys.stderr.write("check_doc_references: label-leg error: %s\n" % label_err)
        print(
            json.dumps(
                {"findings": findings, "scanned": scanned, "error": label_err},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    findings.extend(label_findings)

    findings.sort(key=lambda f: (f["kind"], f["file"], f["line"], f["value"]))
    suppressed_total = len(adr_suppressed) + len(label_suppressed)

    if args.write_baseline:
        n = write_baseline(args.root, args.baseline, findings)
        sys.stderr.write(
            "check_doc_references: --write-baseline wrote %d entr%s to %s\n"
            % (n, "y" if n == 1 else "ies", args.baseline)
        )
        return 0

    baseline_entries, baseline_note = load_baseline(args.root, args.baseline)
    sys.stderr.write(
        "check_doc_references: baseline %s: %s\n"
        % (
            args.baseline,
            baseline_note if baseline_note else "%d entries" % len(baseline_entries),
        )
    )
    baseline_by_key = {}
    for e in baseline_entries:
        baseline_by_key.setdefault(baseline_entry_key(e), e)
    live_keys = {finding_key(f) for f in findings}

    for f in findings:
        f["baselined"] = finding_key(f) in baseline_by_key
    new_findings = [f for f in findings if not f["baselined"]]
    stale_entries = [
        e for e in baseline_entries if baseline_entry_key(e) not in live_keys
    ]

    # A stale entry and a new finding that share (kind, file) are very
    # likely the SAME underlying item, renamed or moved -- not two
    # unrelated regressions. Surfaced as its own pairing so the reader does
    # not have to reconstruct the correlation by hand (dispatch requirement:
    # "that pair must be recognisable at a glance").
    likely_renames = []
    for e in stale_entries:
        e_file = e.get("file")
        if not e_file:
            continue
        for f in new_findings:
            if f["kind"] == e.get("kind") and f["file"] == e_file:
                likely_renames.append(
                    {
                        "kind": f["kind"],
                        "file": e_file,
                        "stale_value": e.get("value"),
                        "new_value": f["value"],
                    }
                )

    print(
        json.dumps(
            {
                "findings": findings,
                "scanned": scanned,
                "allowlist_entries": allow_n,
                "allowlist_suppressed": suppressed_total,
                "allowlist_suppressed_detail": {
                    "adr-citation": sorted({f["value"] for f in adr_suppressed}),
                    "control-label": sorted(s["value"] for s in label_suppressed),
                },
                "baseline_entries": len(baseline_entries),
                "new_findings": new_findings,
                "stale_baseline_entries": stale_entries,
                "likely_renames": likely_renames,
            },
            indent=2,
            sort_keys=True,
        )
    )
    # Reported EVERY run, even when zero -- a suppression nobody sees on
    # stderr is exactly how an allowlist quietly grows into a blanket
    # exemption without anyone noticing (dispatch requirement, 2026-08-19).
    sys.stderr.write(
        "check_doc_references: allowlist suppressed %d finding(s) "
        "(adr-citation=%d, control-label=%d)\n"
        % (suppressed_total, len(adr_suppressed), len(label_suppressed))
    )
    sys.stderr.write(
        "check_doc_references: %d live finding(s) total, %d already baselined\n"
        % (len(findings), len(findings) - len(new_findings))
    )

    if not new_findings and not stale_entries:
        sys.stderr.write("check_doc_references: clean (baseline current).\n")
        return 0

    if likely_renames:
        sys.stderr.write(
            "check_doc_references: %d LIKELY RENAME/MOVE pair(s) -- a baselined "
            "item's value changed at its same file+kind. Fix: edit the existing "
            "baseline entry's value (and file, for dangling-adr-citation) to "
            "match; do not add a second entry.\n" % len(likely_renames)
        )
        for r in likely_renames:
            sys.stderr.write(
                "  RENAME? kind=%s file=%s stale-value=%r new-value=%r\n"
                % (r["kind"], r["file"], r["stale_value"], r["new_value"])
            )

    if new_findings:
        by_kind = {}
        for f in new_findings:
            by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
        sys.stderr.write(
            "check_doc_references: %d NEW finding(s) not in baseline -- %s\n"
            "  Each is either (a) genuinely new documentation debt: write the "
            "docs, or accept the debt with `--write-baseline`; or (b) part of "
            "a rename/move pair flagged above: edit the existing baseline "
            "entry instead.\n"
            % (
                len(new_findings),
                ", ".join("%s=%d" % kv for kv in sorted(by_kind.items())),
            )
        )
        for f in new_findings:
            sys.stderr.write(
                "  NEW  kind=%s file=%s:%d value=%r\n"
                % (f["kind"], f["file"], f["line"], f["value"])
            )

    if stale_entries:
        sys.stderr.write(
            "check_doc_references: %d STALE baseline entr%s -- no live finding "
            "matches them anymore. Each is either (a) fixed: delete the entry "
            "(e.g. via `--write-baseline` after confirming the fix); or (b) "
            "part of a rename/move pair flagged above: edit the entry rather "
            "than deleting it. A stale entry fails this gate rather than "
            "warning, because an unpruned baseline quietly re-permits a "
            "defect that was fixed and later reintroduced.\n"
            % (len(stale_entries), "y" if len(stale_entries) == 1 else "ies")
        )
        for e in stale_entries:
            sys.stderr.write(
                "  STALE kind=%s file=%s value=%r (recorded at line %s)\n"
                % (
                    e.get("kind"),
                    e.get("file"),
                    e.get("value"),
                    e.get("line", "?"),
                )
            )

    return 1


if __name__ == "__main__":
    sys.exit(main())
