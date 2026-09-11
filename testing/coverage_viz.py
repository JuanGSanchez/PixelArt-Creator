#!/usr/bin/env python3
"""What the tests of a repository actually touch — read from its own declarations.

N-8. Three questions, one page:

  * for every function in the product code, WHICH TESTS mention it, and at what
    LEVEL (unit / integration / regression / whatever this repository declares);
  * for every test, which functions it reaches — directly, or through another
    function it calls;
  * and what each test WRITES: the temp workspace the nomenclature gives it,
    plus any path it names in its own source.

IT INVENTS NO CONVENTION. Test type comes from `testing/testing.json`'s `types`
map — a PATTERN per type, declared by the repository (`product-testing.md` §3)
— and source location from its `source_roots`. A container declares the same
things through `testing/coverage-map.json`. A third convention invented here
would be a fourth thing to keep in sync, and the first to go stale.

HONEST LIMITS (P-05), stated by the payload and printed on the page
------------------------------------------------------------------
This is STATIC analysis of names. It reports what a test MENTIONS, which is
not what a test EXECUTES, and the difference is not small:

  * a mention is resolved BY NAME. Two functions called `render` in two source
    roots are one node here unless an import says otherwise, and the payload
    marks such a name `ambiguous` rather than choosing;
  * dynamic dispatch is invisible — `getattr(mod, name)()`, a table of
    callables, a fixture that calls back — so absence of a mention is NOT
    evidence of absence of coverage;
  * a mention inside a branch that never runs still counts, so presence of a
    mention is not evidence of execution either.

That is why this is a coverage VIEWER and not a coverage report: it answers
"what does this suite claim to be about", which no runtime tool answers, and
it does not answer "what ran", which every runtime tool answers better. A page
that blurred the two would be believed for the wrong one.

Usage
    py coverage_viz.py --project <dir> --json

There is no render verb. The page is LIVE-ONLY -- `coverage_views.py
serve` calls `render()` on every request -- and `--json` is how a
person asks what that page would draw.
"""

import argparse
import ast
import collections
import fnmatch
import json
import os
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
ASSET_DIR_NAME = "coverage-viewer"
ASSET_TEMPLATE = "template.html"
ASSET_CSS = "coverage-view.css"
ASSET_JS = "coverage-view.js"
# The circle packing, the label rule and the colormaps the COVERAGE
# frame draws with — the same floor the memory viewer's Repo frame
# uses, loaded from one shared file rather than copied. Two copies of a
# packing solver are two places for every lesson in it to be
# re-learned, and the two frames would start disagreeing about how big
# a folder name is. It lives one level up from the viewer package —
# `viewer-shared/` beside `coverage-viewer/` — so the same relative
# link works from a served page, a vendored bootstrap and a standalone
# render.
ASSET_SHARED_DIR = "viewer-shared"
ASSET_PACKING = "packing.js"
# The shared floor is TWO files, not one. The stylesheet joined it on
# 2026-09-02: geometry was already shared while paint was not, so two
# viewers drawing one packing could and did disagree about how it
# looked. Anything in this tuple is loaded from `viewer-shared/`,
# rewritten to point there in a vendored page, and refused loudly when
# absent -- one rule for both, so a third shared asset needs no new code.
ASSET_PACKING_CSS = "packing.css"
SHARED_ASSETS = (ASSET_PACKING, ASSET_PACKING_CSS)
DATA_PLACEHOLDER = "/*__COVERAGE_DATA__*/"

TESTING_DIR = "testing"
PRODUCT_MANIFEST = "testing.json"
CONTAINER_MAP = "coverage-map.json"

# The TRACKED page `coverage_views.py install` writes: a bootstrap
# holding no analysis, filled by a running server. ONE name, because
# there is now one artifact. `SNAPSHOT_NAME` stood beside it for the
# DERIVED page, retired here with the render verb -- a second,
# data-bearing page that went stale the moment the suite moved, and
# a reader had no way to tell which of the two he had open.
BOOTSTRAP_NAME = "coverage-view.html"

# What `coverage_views.py install` vendors into `testing/`. Named here
# because the analyser has to know its own footprint: after an install
# these five files are `.py` under `testing/`, and counting them as test
# files makes the viewer report on itself — the install polluting the
# very thing it exists to measure.
VENDORED_BASENAMES = ("coverage_views.py", "coverage_viz.py",
                      "viewer_ports.py", "viewer_serving.py",
                      "repo_guard.py")

# A bound, so a viewer pointed at a repository with a vendor tree renders
# instead of hanging. Exceeding it is REPORTED, never silent.
MAX_FILES = 4000
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
             ".pytest_cache", ".mypy_cache", "dist", "build", ".tox"}

# The default classification, used only when a repository declares none. It is
# the same map `check_testing.py` writes into a fresh `testing.json`, so the
# fallback and the scaffold cannot disagree.
DEFAULT_TYPES = {"unit": "test_unit_*",
                 "integration": "test_integration_*",
                 "regression": "test_regression_*"}

# Bounds on WORK, not judgements about the file: past the cap an entry simply
# carries no line count and the viewer sizes it uniformly, which is what it
# already does for anything it cannot measure.
LINE_COUNT_MAX_BYTES = 4 * 1024 * 1024
LINE_COUNT_CHUNK = 65536


def count_lines(path, size):
    """Newlines in a text file, or None when the question does not apply.

    MIRRORED between `memory_viz.py` and `coverage_viz.py`, not imported,
    for the same reason `STORE_VENDORED_PACKAGE` is mirrored: these two
    modules are vendored into DIFFERENT packages -- a coverage install
    carries no `memory_viz.py` and a store carries no `coverage_viz.py` --
    so an import would make each package depend on a file it does not ship.
    The duplication is deliberate, and the home suite's
    `test_scripts_memory_viz_02.py` is the test that keeps the two copies
    from drifting: it compares this source text, character for character,
    with the other module's.

    None for a binary, for something too large to be worth reading, and for
    anything unreadable -- three different reasons, one answer, because the
    caller does the same thing with all of them: omit the key and let the
    viewer fall back to a uniform radius. Returning 0 instead would be a
    CLAIM, and an empty file and a JPEG would make the same one.

    A last line with no trailing newline still counts, which is what `wc -l`
    does not do and what every editor showing line numbers does.
    """
    if size is None or size > LINE_COUNT_MAX_BYTES:
        return None
    try:
        with open(str(path), "rb") as handle:
            total = 0
            tail = b""
            first = True
            while True:
                chunk = handle.read(LINE_COUNT_CHUNK)
                if not chunk:
                    break
                if first and b"\x00" in chunk:
                    return None          # binary: lines are not its unit
                first = False
                total += chunk.count(b"\n")
                tail = chunk[-1:]
            if tail and tail != b"\n":
                total += 1               # a final line without its newline
            return total
    except OSError:
        return None


LIMITS = [
    "Names, not execution: this reports what a test MENTIONS.",
    "A mention is resolved by NAME; two same-named functions in two source "
    "roots are one node unless an import says otherwise (marked `ambiguous`).",
    "Dynamic dispatch is invisible — getattr, callable tables, fixtures that "
    "call back. Absence of a mention is not absence of coverage.",
    "A mention inside a branch that never runs still counts. Presence of a "
    "mention is not evidence of execution.",
]

# What the COVERAGE frame is, and is not. The caveat block above the frames
# swaps to these when that frame is open, because the two make different
# claims and one block carrying both would leave half of it always
# irrelevant to what is on screen.
EXECUTION_LIMITS = [
    "Execution, not names: these lines RAN, in the run this artefact "
    "records. Nothing here is a claim about correctness.",
    "A file the artefact never saw is drawn apart, with a dashed rim, and "
    "counted as unmeasured — never as 0%. That usually means nothing "
    "imported it, which is a different finding from a file whose lines did "
    "not run.",
    "The measurement is only as recent as the run that made it. The frame "
    "prints when, and says so when a source has changed since.",
    "`testing/` is not drawn: the suite is the instrument, and an "
    "instrument measuring itself is a number about nothing.",
]


# --------------------------------------------------------------------------
# frozen assets
# --------------------------------------------------------------------------

def load_assets():
    """The four frozen viewer assets that ship next to this file.

    A missing asset is a refusal, never a trigger to regenerate a fallback:
    the copies delivered downstream must stay byte-identical to the originals,
    and an improvised embedded copy would silently diverge.
    """
    base = BASE / ASSET_DIR_NAME
    shared = BASE / ASSET_SHARED_DIR
    assets = {}
    for name in (ASSET_TEMPLATE, ASSET_CSS, ASSET_JS) + SHARED_ASSETS:
        path = (shared if name in SHARED_ASSETS else base) / name
        if not path.is_file():
            return None, {
                "status": "BLOCKED",
                "error": "frozen viewer asset missing: %s" % path,
                "hint": "the %s/ directory must ship next to coverage_viz.py "
                        "with %s, %s and %s, and %s/%s beside it; restore "
                        "them from the orchestrator-design skill"
                        % (ASSET_DIR_NAME, ASSET_TEMPLATE, ASSET_CSS,
                           ASSET_JS, ASSET_SHARED_DIR, ASSET_PACKING),
            }
        assets[name] = path.read_bytes()
    return assets, None


# --------------------------------------------------------------------------
# the declarations — read, never guessed
# --------------------------------------------------------------------------

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, "cannot read %s: %s" % (path, exc)
    except ValueError as exc:
        return None, "%s is not valid JSON: %s" % (path, exc)


def read_profile(project):
    """What this repository declares about its own tests.

    Returns (profile, error). `profile` carries `kind` ("product" or
    "container"), the `types` patterns, the `source_roots`, and where each
    came from — so the page can say which file it is reporting, and a reader
    can go and edit that file rather than this script.
    """
    project = Path(project)
    testing = project / TESTING_DIR
    if not testing.is_dir():
        return None, ("no %s/ directory in %s — the canonical test folder "
                      "(N-4b) is where this viewer reads its declarations"
                      % (TESTING_DIR, project))

    manifest = testing / PRODUCT_MANIFEST
    if manifest.is_file():
        data, error = read_json(manifest)
        if error:
            return None, error
        return {
            "kind": "product",
            "declared_in": "%s/%s" % (TESTING_DIR, PRODUCT_MANIFEST),
            "project": data.get("project") or project.name,
            "types": dict(data.get("types") or DEFAULT_TYPES),
            "types_declared": bool(data.get("types")),
            "source_roots": list(data.get("source_roots") or []),
            "runner": data.get("runner") or {},
        }, None

    coverage_map = testing / CONTAINER_MAP
    if coverage_map.is_file():
        data, error = read_json(coverage_map)
        if error:
            return None, error
        return {
            "kind": "container",
            "declared_in": "%s/%s" % (TESTING_DIR, CONTAINER_MAP),
            "project": project.name,
            # The SAME `types` key the product side uses, read from the file
            # this side already declares things in. Optional: a container that
            # says nothing gets the default patterns and every suite it owns
            # is reported UNCLASSIFIED, which is a finding rather than a
            # silence — "no declared convention" is exactly what a reader of
            # this page needs to know, and inventing a third file to hold it
            # would be a fourth thing to keep in sync.
            "types": dict(data.get("types") or DEFAULT_TYPES),
            "types_declared": bool(data.get("types")),
            # A container declares WHERE its own code lives as `unit_roots`;
            # that is the same statement `source_roots` makes on the product
            # side, under the name that side already uses.
            "source_roots": list(data.get("unit_roots") or []),
            "units": data.get("units") or [],
        }, None

    return None, ("neither %s nor %s is present under %s/ — this viewer reads "
                  "a repository's OWN declarations and will not guess a test "
                  "convention" % (PRODUCT_MANIFEST, CONTAINER_MAP,
                                  TESTING_DIR))


def classify(rel_path, types):
    """The declared type whose pattern matches, or "" when none does.

    Matched against the path AND against the bare filename, because a
    repository classifying by prefix writes `test_unit_*` while one
    classifying by folder writes `suites/unit/*`, and both are legitimate
    (`product-testing.md` §3). First match in declaration order wins, so a
    repository controls precedence by ordering its own map.
    """
    name = rel_path.rsplit("/", 1)[-1]
    for label, pattern in types.items():
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(name, pattern):
            return label
    return ""


# --------------------------------------------------------------------------
# what a file mentions
# --------------------------------------------------------------------------

class Mentions(ast.NodeVisitor):
    """Every name this file calls, and every function it defines.

    Deliberately shallow: it records `foo` for `foo()` and `foo` for
    `mod.foo()`, because the question this viewer answers is "which product
    function does this test talk about", and a test reaches one through an
    import, an attribute, or a fixture indifferently. Resolution to a real
    definition happens later, against the source index, where ambiguity can
    be reported rather than guessed at.
    """

    def __init__(self):
        self.calls = set()
        self.functions = []
        self.imports = {}      # local name -> dotted origin
        self.strings = set()
        self._stack = []

    def visit_Import(self, node):
        for alias in node.names:
            self.imports[alias.asname or alias.name.split(".")[0]] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            self.imports[alias.asname or alias.name] = (
                "%s.%s" % (module, alias.name) if module else alias.name)
        self.generic_visit(node)

    def _enter(self, node):
        self._stack.append({"name": node.name, "line": node.lineno,
                            "calls": set(), "strings": set()})
        self.generic_visit(node)
        return self._stack.pop()

    def visit_FunctionDef(self, node):
        frame = self._enter(node)
        self.functions.append(frame)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        target = node.func
        name = ""
        if isinstance(target, ast.Name):
            name = target.id
        elif isinstance(target, ast.Attribute):
            name = target.attr
        if name:
            self.calls.add(name)
            if self._stack:
                self._stack[-1]["calls"].add(name)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and looks_like_path(node.value):
            self.strings.add(node.value)
            if self._stack:
                self._stack[-1]["strings"].add(node.value)
        self.generic_visit(node)


def looks_like_path(text):
    """A string a test might be naming as an output.

    A heuristic, and reported as one. It asks for a separator or a file
    extension and refuses anything long enough to be prose, because the
    alternative — listing every string literal — buries the two or three that
    are actually paths.
    """
    if not text or len(text) > 120 or "\n" in text or " " in text.strip():
        return False
    if "/" in text or "\\" in text:
        return True
    stem, dot, ext = text.rpartition(".")
    return bool(stem and dot and 1 <= len(ext) <= 5 and ext.isalnum())


def analyse(path):
    """(Mentions, error) for one Python file."""
    try:
        source = Path(path).read_bytes()
    except OSError as exc:
        return None, "cannot read: %s" % exc
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return None, "syntax error at line %s" % exc.lineno
    visitor = Mentions()
    visitor.visit(tree)
    return visitor, None


# --------------------------------------------------------------------------
# the walk
# --------------------------------------------------------------------------

def point_at_vendored_assets(html):
    """Link a page at `testing/`'s ONE copy of each frozen asset.

    The frozen template links `./coverage-view.css` and
    `./coverage-view.js`, which is right for a standalone page shipping
    beside its own copies. `install` vendors the sources under
    `coverage-viewer/` and puts nothing beside the page, so an unrewritten
    bootstrap opened straight off disk was a raw unstyled page — it only
    looked right SERVED, because the handler routes those two paths.

    `packing.js` moves to `viewer-shared/`, NOT into the viewer package:
    the memory viewer vendors the same bytes at the same relative place, so
    a store and a testing directory that both carry a viewer carry one
    shared floor each rather than one copy per frame.
    """
    text = html.decode("utf-8")
    for name in (ASSET_CSS, ASSET_JS):
        text = text.replace('"./%s"' % name,
                            '"./%s/%s"' % (ASSET_DIR_NAME, name))
    # The shared asset goes to its own directory, not the package's.
    for shared_name in SHARED_ASSETS:
        text = text.replace('"./%s"' % shared_name,
                            '"./%s/%s"'
                            % (ASSET_SHARED_DIR, shared_name))
    return text.encode("utf-8")


def python_files(root, limit=MAX_FILES, skip_vendored=False):
    """Every .py file under `root`, sorted, bounded, symlinks not followed.

    `skip_vendored` drops the viewer's OWN vendored copies from the TOP of
    `root`. They are `.py` under `testing/` the moment `install` runs, so
    walking the testing directory without it makes the analyser report five
    files of its own as unclassified test files — the install changing the
    measurement it was opened to read.

    It is OFF by default, and every caller that walks a SOURCE root leaves
    it off: `scripts/` is where a container's originals live, and skipping
    the five names there deleted the analyser itself from the Coverage
    frame's leaves and from the Metrics source index — the one file a
    reader of this page is most likely to look for.
    """
    found, truncated = [], False
    root = Path(root)
    if not root.is_dir():
        return found, truncated
    for folder, subdirs, names in os.walk(str(root), followlinks=False):
        subdirs[:] = sorted(d for d in subdirs
                            if d not in SKIP_DIRS and d != ASSET_DIR_NAME)
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            if skip_vendored and name in VENDORED_BASENAMES and \
                    Path(folder) == root:
                continue
            if len(found) >= limit:
                return found, True
            found.append(Path(folder) / name)
    return found, truncated


def relative(path, project):
    try:
        return Path(path).relative_to(project).as_posix()
    except ValueError:
        return Path(path).as_posix()


# --------------------------------------------------------------------------
# the payload
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# execution: what actually ran
# --------------------------------------------------------------------------

# Written by `testing/run` / `run.cmd` after the suite, from the fragments
# every CHILD process wrote (`sitecustomize.py` + COVERAGE_PROCESS_START).
# Gitignored: it changes on every run, and a clone that has never run the
# suite has measured nothing, which is what the frame then says.
COVERAGE_ARTEFACT = "coverage.json"
# `testing/` is never drawn in the Coverage frame: the suite is the
# instrument, and an instrument measuring itself is a number about nothing.
COVERAGE_SKIP_PREFIXES = (TESTING_DIR + "/",)


def _artefact_age(artefact, project, roots):
    """True when a source is newer than the measurement that describes it."""
    try:
        measured = artefact.stat().st_mtime
    except OSError:
        return False
    for root in roots:
        folder = Path(project) / root
        if not folder.is_dir():
            continue
        files, _truncated = python_files(folder)
        for path in files:
            try:
                if path.stat().st_mtime > measured:
                    return True
            except OSError:
                continue
    return False


def read_coverage(project, profile):
    """What RAN, from the artefact the suite wrote — or why there is none.

    Returns {"state", "detail", "artefact", "measured_at", "percent",
             "files": {rel: {"percent", "covered", "statements",
                             "functions": [...]}},
             "measured": int, "unmeasured": int}

    `state` is always set and always says which of four worlds this is:
    `ok`, `stale` (a source is newer than the measurement), `absent` (nobody
    has run the suite in this clone) or `unreadable`. THE FRAME PRINTS IT.
    Every other number on that frame is an execution claim, and an execution
    claim whose provenance is not on screen beside it is the kind of number
    people quote for years.

    THE FUNCTION BLOCK COMES FROM `coverage json` ITSELF. It carries
    `executed_lines`, `missing_lines`, `summary.percent_covered` and
    `start_line` per function, so the three buckets — covered (100%),
    partially covered (1-99%), not covered (0%) — are read, not inferred.
    Nothing here intersects AST spans by hand.
    """
    project = Path(project)
    artefact = project / TESTING_DIR / COVERAGE_ARTEFACT
    empty = {"state": "absent", "detail": "", "artefact":
             "%s/%s" % (TESTING_DIR, COVERAGE_ARTEFACT),
             "measured_at": "", "percent": None, "files": {},
             "measured": 0, "unmeasured": 0}
    if not artefact.is_file():
        empty["detail"] = (
            "no coverage has been measured in this clone — run "
            "`%s/run` (or run.cmd) and the frame fills itself"
            % TESTING_DIR)
        return empty

    data, error = read_json(artefact)
    if error:
        empty["state"] = "unreadable"
        empty["detail"] = error
        return empty

    files = {}
    for raw, record in (data.get("files") or {}).items():
        # `coverage json` writes whichever spelling the run produced:
        # absolute on one machine, relative on another, native
        # separators either way. One posix, project-relative key here,
        # because that is how every other path in this payload is spelt.
        if Path(raw).is_absolute():
            rel = relative(Path(raw), project)
        else:
            rel = raw.replace(chr(92), "/")
        summary = record.get("summary") or {}
        functions = []
        for name, block in sorted((record.get("functions") or {}).items()):
            if not name:
                continue                  # module-level code, not a function
            block_summary = block.get("summary") or {}
            functions.append({
                "name": name,
                "line": block.get("start_line") or 0,
                "percent": block_summary.get("percent_covered"),
                "statements": block_summary.get("num_statements") or 0,
                "missing": len(block.get("missing_lines") or []),
            })
        files[rel] = {
            "percent": summary.get("percent_covered"),
            "covered": summary.get("covered_lines") or 0,
            "statements": summary.get("num_statements") or 0,
            "functions": functions,
        }

    totals = (data.get("totals") or {})
    meta = (data.get("meta") or {})
    state = "ok"
    detail = ""
    if _artefact_age(artefact, project, profile.get("source_roots") or []):
        state = "stale"
        detail = ("a source has changed since this was measured — the "
                  "numbers describe the tree as it was, not as it is")
    return {
        "state": state, "detail": detail,
        "artefact": "%s/%s" % (TESTING_DIR, COVERAGE_ARTEFACT),
        "measured_at": meta.get("timestamp") or "",
        "percent": totals.get("percent_covered"),
        "files": files,
        "measured": len(files), "unmeasured": 0,
    }


def executed(project, profile, coverage):
    """The Coverage frame's leaf set: every declared source file, minus
    `testing/`, with what ran in it.

    DECLARED, not measured. A file the artefact never saw carries no
    percentage at all — `percent` is None — and is COUNTED as unmeasured:
    the page draws it apart, with a dashed rim, never as 0%. "Never
    imported by anything" is the finding a reader most wants, and a file
    that simply vanished from the map would hide it. Size is LINES — the
    Repo frame's rule — so a file is the same circle in both frames and
    only its colour changes.
    The leaf still carries `bytes`, for a reader who wants the number; no
    frame sizes by it.
    """
    project = Path(project).resolve()
    leaves = []
    unmeasured = 0
    for root in profile.get("source_roots") or []:
        folder = project / root
        if not folder.is_dir():
            continue
        files, _truncated = python_files(folder)
        for path in files:
            rel = relative(path, project)
            if any(rel.startswith(skip) for skip in COVERAGE_SKIP_PREFIXES):
                continue
            record = coverage["files"].get(rel)
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            if record is None:
                unmeasured += 1
            leaves.append({
                "path": rel, "bytes": size, "lines": count_lines(path, size),
                "percent": None if record is None else record["percent"],
                "covered": 0 if record is None else record["covered"],
                "statements": 0 if record is None else record["statements"],
                "functions": [] if record is None else record["functions"],
                "measured": record is not None,
            })
    leaves.sort(key=lambda leaf: leaf["path"])
    coverage["unmeasured"] = unmeasured
    return leaves


def collect(project, profile):
    """Everything the page draws, built from the repository's declarations."""
    project = Path(project).resolve()
    payload = {
        "state": "ok", "detail": "",
        "project": profile["project"],
        "kind": profile["kind"],
        "declared_in": profile["declared_in"],
        "types": profile["types"],
        "types_declared": profile["types_declared"],
        "source_roots": profile["source_roots"],
        "limits": LIMITS,
        "execution_limits": EXECUTION_LIMITS,
        "tests": [], "sources": [], "coverage": [],
        "unclassified": [], "missing_roots": [], "truncated": False,
    }
    # The Coverage frame's half. Read here rather than in the server so a
    # standalone render carries it too, and so one payload answers both
    # frames — `Metrics` counts MENTIONS, `Coverage` counts EXECUTIONS, and
    # the page says which as you switch between them.
    payload["execution"] = read_coverage(project, profile)
    payload["executed"] = executed(project, profile, payload["execution"])

    # --- the source side ---------------------------------------------------
    by_name = {}         # function name -> [ {path, name, line} ]
    call_graph = {}      # "path::name" -> set of called names
    for root in profile["source_roots"]:
        folder = project / root
        if not folder.is_dir():
            payload["missing_roots"].append(root)
            continue
        files, truncated = python_files(folder)
        payload["truncated"] = payload["truncated"] or truncated
        for path in files:
            found, error = analyse(path)
            if found is None:
                continue
            rel = relative(path, project)
            entry = {"path": rel, "functions": []}
            for frame in found.functions:
                node = {"name": frame["name"], "line": frame["line"]}
                entry["functions"].append(node)
                by_name.setdefault(frame["name"], []).append(
                    {"path": rel, "name": frame["name"],
                     "line": frame["line"]})
                call_graph["%s::%s" % (rel, frame["name"])] = frame["calls"]
            if entry["functions"]:
                payload["sources"].append(entry)

    # --- the test side -----------------------------------------------------
    testing = project / TESTING_DIR
    files, truncated = python_files(testing, skip_vendored=True)
    payload["truncated"] = payload["truncated"] or truncated
    for path in files:
        found, error = analyse(path)
        rel = relative(path, project)
        kind = classify(rel, profile["types"])
        if not kind:
            payload["unclassified"].append(rel)
        entry = {"path": rel, "type": kind, "functions": [], "error": error}
        if found is not None:
            for frame in found.functions:
                if not frame["name"].startswith("test"):
                    continue
                entry["functions"].append({
                    "name": frame["name"],
                    "line": frame["line"],
                    "mentions": sorted(frame["calls"] & set(by_name)),
                    "outputs": outputs_for(rel, frame),
                })
        entry["mentions"] = sorted(
            {name for fn in entry["functions"] for name in fn["mentions"]})
        payload["tests"].append(entry)

    payload["coverage"] = relate(payload["tests"], by_name, call_graph)
    return payload


def outputs_for(test_path, frame):
    """What this test writes, as far as its own source and the nomenclature say.

    Two sources, and the payload keeps them apart because their standing is
    different. The WORKSPACE is derived from the temp-path nomenclature
    (`system-testing.md` §2.1) and is therefore a fact about every test that
    asks for one; the NAMED paths are string literals this test contains, which
    is a heuristic and is labelled as one.
    """
    stem = test_path.rsplit("/", 1)[-1]
    if stem.endswith(".py"):
        stem = stem[:-3]
    out = [{
        "kind": "workspace",
        "value": "<ROOT>/<SCOPE>/run-<RUNID>/<NNN>-%s-%s/" % (stem,
                                                              frame["name"]),
        "note": "the temp-path nomenclature gives every test its own "
                "directory, named after this file and this function",
    }]
    for text in sorted(frame["strings"]):
        out.append({"kind": "named", "value": text,
                    "note": "a path-shaped string in this test's source "
                            "(heuristic)"})
    return out


def relate(tests, by_name, call_graph, max_depth=3):
    """Which tests reach which source functions, directly or through a call.

    Indirect reach is a bounded walk of the source call graph: a test that
    mentions `save()` reaches whatever `save()` calls, and so on. Bounded
    because the graph has cycles and because reach at four hops is a claim
    nobody should act on — beyond that the honest answer is "look at the
    code", not a longer list.

    BREADTH FIRST, and the frontier is a QUEUE, because the bound makes
    depth part of the answer. `seen` records a function the first time the
    walk arrives at it, and a depth-first walk arrives by whichever path it
    happened to take: a function one hop from the test could be entered at
    hop three down a long branch, get marked seen there, and then be
    refused its own expansion by `depth < max_depth` — so everything BELOW
    it vanished from the page. Which branch was taken first came from
    iterating `call_graph`'s sets of names, whose order is the process's
    hash seed. Measured on this container: the same tree, analysed by two
    server processes, produced payloads that differed in five records, and
    two runs under the same `PYTHONHASHSEED` agreed exactly.

    A queue arrives at every function at its MINIMUM depth, so the answer
    is the graph's and not the walk's. The names are sorted on the way in
    as well — not needed for the result, which no longer depends on order,
    but a reproducible walk is one a person can follow in a debugger.
    """
    reached = {}
    for test in tests:
        for function in test["functions"]:
            nodeid = "%s::%s" % (test["path"], function["name"])
            frontier = collections.deque(
                (name, 0) for name in function["mentions"])
            seen = set()
            while frontier:
                name, depth = frontier.popleft()
                for target in by_name.get(name, []):
                    key = (target["path"], target["name"])
                    if key in seen:
                        continue
                    seen.add(key)
                    record = reached.setdefault(key, {
                        "source": target["path"], "function": target["name"],
                        "line": target["line"], "direct": [], "indirect": [],
                        "types": set(),
                        "ambiguous": len(by_name.get(name, [])) > 1,
                    })
                    record["direct" if depth == 0 else "indirect"].append(
                        nodeid)
                    if test["type"]:
                        record["types"].add(test["type"])
                    if depth < max_depth:
                        onward = call_graph.get(
                            "%s::%s" % (target["path"], target["name"]), ())
                        frontier.extend((call, depth + 1)
                                        for call in sorted(onward)
                                        if call in by_name)

    out = []
    for record in reached.values():
        record["types"] = sorted(record["types"])
        record["direct"] = sorted(set(record["direct"]))
        record["indirect"] = sorted(set(record["indirect"]) -
                                    set(record["direct"]))
        out.append(record)
    out.sort(key=lambda r: (r["source"], r["function"]))
    return out


def uncovered(payload):
    """Source functions no test mentions, at any depth.

    Reported as a QUESTION, never as a verdict: this is static analysis, and a
    function reached only through dynamic dispatch is invisible here. The page
    says so beside the number.
    """
    covered = {(record["source"], record["function"])
               for record in payload["coverage"]}
    out = []
    for source in payload["sources"]:
        for function in source["functions"]:
            if (source["path"], function["name"]) not in covered:
                out.append({"source": source["path"],
                            "function": function["name"],
                            "line": function["line"]})
    return out


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------

def render(payload, template_bytes):
    """Inject the payload into the frozen template; return HTML bytes."""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    # Escape `<` so no HTML tokenizer state can be entered from inlined data.
    blob = blob.replace("<", "\\u003c")
    html = template_bytes.decode("utf-8")
    if html.count(DATA_PLACEHOLDER) != 1:
        raise ValueError("the template must carry %s exactly once"
                         % DATA_PLACEHOLDER)
    return html.replace(DATA_PLACEHOLDER, blob).replace(
        "\r\n", "\n").encode("utf-8")


def write_if_changed(path, payload):
    """Write unless the file already holds those exact bytes."""
    path = Path(path)
    if path.is_file() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(payload)
    return True


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="coverage_viz.py",
        description="Report a repository's test coverage map, read "
                    "from its own testing/ declarations. The page "
                    "itself is served live by coverage_views.py; "
                    "this prints the payload it would draw.")
    parser.add_argument("--project", default=".",
                        help="repository root (default: the current directory)")
    # Every option here DOES something. `--out` and `--standalone`
    # steered a render that no longer exists; a `--help` that still
    # listed them would be the only specification a reader has, and it
    # would be wrong.
    parser.add_argument("--json", action="store_true",
                        help="print the payload the served page would "
                             "draw")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    project = Path(args.project).resolve()

    # RETIRED: the derived, data-bearing page is no longer generated and
    # the coverage viewer is LIVE-ONLY. A page written to disk is a
    # photograph of a suite that changes every time somebody adds a
    # test, and a reader with both files open cannot tell which one he
    # is reading.
    #
    # `--json` still works, and is the whole CLI now: printing the
    # payload is an inspection of the DATA, not the generation of a
    # page, and it is the honest way to ask what the viewer would draw
    # without producing a file that then goes stale.
    if not args.json:
        print(json.dumps({
            "status": "BLOCKED",
            "error": "rendering the derived coverage page is retired; "
                     "it is no longer generated",
            "hint": "open it live instead: python coverage_views.py "
                    "serve --project %s   (or --json here to inspect "
                    "the payload)" % project}))
        return 2

    profile, error = read_profile(project)
    if error:
        print(json.dumps({"status": "BLOCKED", "error": error,
                          "hint": "run `check_testing.py scaffold` to create "
                                  "the declarations this viewer reads"}))
        return 2

    payload = collect(project, profile)
    payload["uncovered"] = uncovered(payload)

    print(json.dumps(payload, ensure_ascii=False, indent=2,
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
