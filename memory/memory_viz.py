#!/usr/bin/env python3
"""memory_viz.py — memory graph visualization.

Renders a memory store's JSONL logs into a three-file viewer: the graph
is replayed in Python, inlined as JSON into a frozen HTML template, and
rendered by a vanilla-JS + SVG viewer (force / DAG graph layouts, a
nested circle-packing "Repo" view of the file tree, and a "History" view
of the repository's commits). No dependencies, no network access, works
from `file://`.

RUNTIME:
  Python >= 3.8, standard library only. Viewer: any modern browser.
  `git` is optional: without it the History view says why it is empty.

ENTRYPOINT:
  python memory_viz.py --store <memory-dir> [--out <path>]
                       [--include-invalidated] [--limit N --rank degree]
                       [--no-card-bodies] [--force-out]
                       [--repo <dir>] [--commits N] [--no-git]

INPUTS:
  - <store>/graph/{nodes,edges}.jsonl — the structural half: what the
    repository is made of, plus its `invalidate` control records.
  - <store>/insight/{nodes,edges}.jsonl — the half that belongs to the
    orchestration system: decisions, lessons, incidents, every edge
    touching one, and their control records. Both halves replay into one
    graph, graph first, because a control record lives in the same half
    as the record it closes. A store written before the split keeps
    everything in `graph/` and still reads correctly.
  - <store>/cards/*.md        — optional card bodies, inlined (K8) when a
    node's `card` path resolves INSIDE the store.
  - the enclosing git repository (or `--repo`): the newest `--commits`
    commits of the WHOLE commit graph in topological order — side
    branches are collected, not dropped (see the LOG_BASE comment
    below) — with each commit's changed paths,
    per-file added/deleted lines, and the file list of the OLDEST commit
    inlined. The page replays the diffs forward from that base rather
    than carrying one tree per commit, which keeps the payload
    proportional to the number of commits instead of commits x files.
  Reads are corrupt-tolerant: `errors="replace"`, malformed lines are
  counted and reported, never fatal. Git is read-only and never fatal
  either: a missing binary, a missing repository or an unborn HEAD all
  end as a stated `git.state`, never as a failed render.

FROZEN ASSETS (copy-fidelity contract):
  The viewer lives in `memory-viewer/` NEXT TO THIS FILE:
    memory-viewer/template.html   — page skeleton + data placeholder
    memory-viewer/graph-view.css  — all styles
    memory-viewer/graph-view.js   — all behavior
  These are frozen: they are copied byte-identically into every
  delivered system and verified by a copy-fidelity gate. A missing or
  corrupt asset is a HARD ERROR (exit 2) — this script never regenerates
  an embedded fallback, because a silently divergent copy would defeat
  the gate. The ONLY per-render substitution is the data block: the
  template's `/*__GRAPH_DATA__*/` placeholder (inside
  `<script type="application/json" id="graph-data">`) is replaced with
  the graph JSON, whose `meta.generated_at` stamp is content-derived.

OUTPUTS (all written into the output directory, default the store):
  - graph-view.html — template with the data JSON injected.
  - graph-view.css  — byte-identical copy of the frozen asset.
  - graph-view.js   — byte-identical copy of the frozen asset.
  - JSON summary on stdout (nodes, edges, hidden counts, cards, bytes,
    out / out_css / out_js, written flags). Advisories on stderr.

EXIT CODES:
  0 — page written or already up to date (including the empty-state page)
  1 — failure (I/O or unexpected error; JSON error payload on stdout)
  2 — usage / refused (bad CLI, missing store, unsafe --out, missing
      frozen asset)

DERIVED ARTIFACTS:
  The three outputs are 100 % rebuildable from the logs + frozen assets.
  Treat them as derived, not durable: they belong in the store's
  `.gitignore` alongside the index and scan state, and are regenerated
  after every scan/session close.

DETERMINISM:
  Output is a pure function of (store contents, repository state, frozen
  assets). `generated_at` is the newest record timestamp in the store,
  never the wall clock, and each of the three writes is skipped when the
  rendered bytes are identical to the existing file, so an unchanged
  store in an unchanged repository produces no diff. The viewer's
  layouts are themselves deterministic (mulberry32 seeded from the
  visible node ids): same data, same picture. `--no-git` drops the
  repository from the inputs when only the store should matter.

SCALE:
  Repulsion uses a uniform spatial grid (~O(N) per tick), simulation is
  decoupled from rendering (DOM writes every 3rd tick), and the loop
  stops on an energy threshold or 120 ticks. Above 1500 visible nodes
  the viewer falls back to a degree-ranked top-N subgraph with a banner;
  `--limit N --rank degree` performs the same reduction Python-side.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

if sys.version_info < (3, 8):  # pragma: no cover - guard for old runtimes
    sys.stdout.write(json.dumps({
        "status": "BLOCKED",
        "error": "python >= 3.8 required, found {}.{}".format(
            sys.version_info[0], sys.version_info[1]),
    }) + "\n")
    raise SystemExit(2)

MAX_CARD_BYTES = 8192
NODE_FIELDS = ("id", "type", "name", "path", "summary", "props", "source",
               "episode", "created_at", "invalid_at", "card", "card_body",
               "card_truncated")
EDGE_FIELDS = ("id", "src", "dst", "type", "props", "source", "episode",
               "created_at", "invalid_at")
TIME_FIELDS = ("created_at", "invalid_at", "at")

ASSET_DIR_NAME = "memory-viewer"
ASSET_TEMPLATE = "template.html"
ASSET_CSS = "graph-view.css"
ASSET_JS = "graph-view.js"
# The packing, the labels and the colormaps — shared with the coverage
# viewer, so both frames draw the same picture from the same rules, and
# kept in a directory of its own BESIDE each package rather than inside
# one of them: `memory_viz.py` sits at `scripts/` in the skill and at
# `<store>/` in a store, so `parent/viewer-shared/` is the same relative
# path in both layouts and neither viewer owns the file.
ASSET_SHARED_DIR = "viewer-shared"
ASSET_PACKING = "packing.js"
DATA_PLACEHOLDER = "/*__GRAPH_DATA__*/"
# The TRACKED page `memory_views.py install` writes — a bootstrap holding
# no records — and the DERIVED page this renderer writes. Two names because
# they are two artifacts: the bootstrap is committed and costs one diff
# ever, the snapshot carries the whole graph and is gitignored. They were
# one name until 3.1.0, and a bare render therefore rewrote the tracked
# file with the entire store — measured at 3,020,762 bytes on a delivered
# system (`memory-graph-visualization.md` 5.4).
BOOTSTRAP_NAME = "graph-view.html"
SNAPSHOT_NAME = "graph-view-snapshot.html"


# --------------------------------------------------------------------------
# frozen assets
# --------------------------------------------------------------------------
def load_assets():
    """Read the four frozen viewer assets that ship next to this file.

    Returns (assets, error): `assets` maps asset name -> bytes; on any
    problem `error` is a BLOCKED payload dict and `assets` is None. A
    missing asset is a refusal, never a trigger to regenerate a fallback:
    the copies delivered downstream must stay byte-identical to the
    originals, and an improvised embedded copy would silently diverge.
    """
    here = Path(__file__).resolve().parent
    base = here / ASSET_DIR_NAME
    shared = here / ASSET_SHARED_DIR
    assets = {}
    for name in (ASSET_TEMPLATE, ASSET_CSS, ASSET_JS, ASSET_PACKING):
        path = (shared if name == ASSET_PACKING else base) / name
        if not path.is_file():
            return None, {
                "status": "BLOCKED",
                "error": "frozen viewer asset missing: {}".format(path),
                "hint": "the {}/ directory must ship next to memory_viz.py"
                        " with template.html, graph-view.css and"
                        " graph-view.js; restore it from the"
                        " orchestrator-design skill".format(ASSET_DIR_NAME),
            }
        try:
            assets[name] = path.read_bytes()
        except OSError as exc:
            return None, {
                "status": "BLOCKED",
                "error": "cannot read frozen viewer asset {}: {}".format(
                    path, exc),
            }
    template = assets[ASSET_TEMPLATE].decode("utf-8", errors="replace")
    if template.count(DATA_PLACEHOLDER) != 1:
        return None, {
            "status": "BLOCKED",
            "error": "template.html must contain the {} placeholder exactly"
                     " once".format(DATA_PLACEHOLDER),
            "hint": "the frozen template is corrupt; restore it from the"
                    " orchestrator-design skill",
        }
    return assets, None


# --------------------------------------------------------------------------
# store replay
# --------------------------------------------------------------------------
def _fold_confidence(props, rec):
    """Apply a reinforce/dispute delta to a node's props (K11)."""
    try:
        props["confidence"] = int(props.get("confidence", 1)) + int(
            rec.get("delta", 1))
    except (TypeError, ValueError):
        pass
    stamp = rec.get("at") or rec.get("created_at")
    if isinstance(stamp, str) and stamp:
        # Mirrors the store's own fold: the last confirmation/dispute touch.
        props["last_confirmed"] = stamp


# A store keeps its records in two halves — `graph/` for what the
# repository is made of, `insight/` for what was learned building it. Both
# replay into one graph, in this order, because a control record lives in
# the same half as the record it closes.
STORE_LOGS = ("graph/nodes.jsonl", "graph/edges.jsonl",
              "insight/nodes.jsonl", "insight/edges.jsonl")


def load_logs(store):
    """Replay every log in the store into current state (read-only).

    Returns (nodes, edges, info) where info carries the malformed-line count
    and the newest timestamp observed anywhere in the store.
    """
    nodes, edges = {}, {}
    malformed = 0
    newest = ""
    for relative in STORE_LOGS:
        f = store.joinpath(*relative.split("/"))
        if not f.is_file():
            continue
        # errors="replace": a single bad byte must never be fatal (K6).
        with f.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    if not isinstance(rec, dict):
                        raise ValueError("not an object")
                except (json.JSONDecodeError, ValueError):
                    malformed += 1
                    continue
                for key in TIME_FIELDS:
                    val = rec.get(key)
                    if isinstance(val, str) and val > newest:
                        newest = val
                kind = rec.get("kind")
                if kind in ("node", "edge"):
                    coll = nodes if kind == "node" else edges
                    rid = rec.get("id")
                    if not isinstance(rid, str) or not rid:
                        malformed += 1
                        continue
                    if not isinstance(rec.get("props"), dict):
                        rec["props"] = {}
                    rec.setdefault("invalid_at", None)
                    coll[rid] = rec
                elif kind == "invalidate":
                    target = rec.get("target")
                    stamp = rec.get("invalid_at") or "unknown"
                    for coll in (nodes, edges):
                        r = coll.get(target)
                        if r is not None and r.get("invalid_at") is None:
                            r["invalid_at"] = stamp
                            break
                elif kind in ("reinforce", "dispute"):
                    r = nodes.get(rec.get("target"))
                    if r is not None:
                        _fold_confidence(r.setdefault("props", {}), rec)
                else:
                    malformed += 1
    return nodes, edges, {"malformed": malformed, "newest": newest}


# --------------------------------------------------------------------------
# selection helpers
# --------------------------------------------------------------------------
def split_invalidated(nodes, edges, include_invalidated):
    """Drop invalidated records unless opted in (K4); report the counts."""
    dead_nodes = [r for r in nodes.values() if r.get("invalid_at") is not None]
    dead_edges = [r for r in edges.values() if r.get("invalid_at") is not None]
    if include_invalidated:
        return nodes, edges, 0, 0
    live_nodes = {k: r for k, r in nodes.items()
                  if r.get("invalid_at") is None}
    live_edges = {k: r for k, r in edges.items()
                  if r.get("invalid_at") is None
                  and r.get("src") in live_nodes
                  and r.get("dst") in live_nodes}
    hidden_edges = len(edges) - len(live_edges)
    return live_nodes, live_edges, len(dead_nodes), hidden_edges


def apply_limit(nodes, edges, limit, rank):
    """Keep only the top-`limit` nodes by `rank` plus their induced edges."""
    if not limit or limit >= len(nodes):
        return nodes, edges, False
    degree = {}
    for rec in edges.values():
        for key in ("src", "dst"):
            nid = rec.get(key)
            if nid in nodes:
                degree[nid] = degree.get(nid, 0) + 1
    if rank == "degree":
        ordered = sorted(nodes.values(),
                         key=lambda r: (-degree.get(r["id"], 0), r["id"]))
    else:  # pragma: no cover - argparse restricts the choices
        ordered = sorted(nodes.values(), key=lambda r: r["id"])
    keep = {r["id"]: r for r in ordered[:limit]}
    kept_edges = {k: r for k, r in edges.items()
                  if r.get("src") in keep and r.get("dst") in keep}
    return keep, kept_edges, True


def point_at_vendored_assets(html):
    """Link a page at the store's ONE copy of each frozen asset.

    The frozen template links `./graph-view.css` and `./graph-view.js`,
    because a standalone page ships beside its own copies and a file://
    page has to reach them relatively. In a store the sources are vendored
    under `memory-viewer/`, so writing copies beside the page would put two
    files of each name in one store — one source, one derived, one tracked,
    one not, and no way to tell which the page is drawn by.

    Applied to bytes this module produced. The frozen template and the
    frozen assets are copy-fidelity subjects and are never touched.
    """
    text = html.decode("utf-8")
    for name in (ASSET_CSS, ASSET_JS):
        text = text.replace('"./%s"' % name,
                            '"./%s/%s"' % (ASSET_DIR_NAME, name))
    # The shared asset goes to its own directory, not the package's.
    text = text.replace('"./%s"' % ASSET_PACKING,
                        '"./%s/%s"' % (ASSET_SHARED_DIR, ASSET_PACKING))
    return text.encode("utf-8")


def _within(child, parent):
    """True when `child` is `parent` or lies inside it."""
    try:
        child = Path(child).resolve()
        parent = Path(parent).resolve()
    except OSError:
        return False
    return child == parent or parent in child.parents


def inline_card_bodies(nodes, store):
    """Inline card bodies for nodes whose `card` resolves inside the store.

    `fetch()` is blocked on `file://`, so the only way the viewer can show a
    card is to carry it in the payload (K8). Bodies are capped at 8 KB.
    """
    inlined, added, outside, missing = 0, 0, 0, 0
    for rec in nodes.values():
        card = rec.get("card")
        if not isinstance(card, str) or not card.strip():
            continue
        raw = Path(card)
        candidates = [raw if raw.is_absolute() else store / raw]
        if not raw.is_absolute():
            candidates.append(store / "cards" / raw.name)
        chosen, escaped = None, False
        for cand in candidates:
            if not _within(cand, store):
                escaped = True
                continue
            if cand.is_file():
                chosen = cand
                break
        if chosen is None:
            if escaped:
                outside += 1
            else:
                missing += 1
            continue
        try:
            data = chosen.read_bytes()
        except OSError:
            missing += 1
            continue
        truncated = len(data) > MAX_CARD_BYTES
        text = data[:MAX_CARD_BYTES].decode("utf-8", errors="replace")
        rec["card_body"] = text
        rec["card_truncated"] = truncated
        inlined += 1
        added += len(text.encode("utf-8"))
    return {"cards_inlined": inlined, "card_bytes": added,
            "cards_outside_store": outside, "cards_missing": missing}


# --------------------------------------------------------------------------
# git history (optional payload for the History view)
# --------------------------------------------------------------------------
GIT_TIMEOUT_SECONDS = 30
DEFAULT_COMMIT_LIMIT = 200
REC_SEP = "\x1e"
FIELD_SEP = "\x1f"
# Body LAST, always: it is the only free-form field, so anything unexpected in
# it can only run off the end of the record instead of shifting every field
# after it.
COMMIT_FIELDS = ("%H", "%h", "%aI", "%an", "%ae", "%cn", "%cI", "%P", "%s",
                 "%b")
COMMIT_FORMAT = REC_SEP + FIELD_SEP.join(COMMIT_FIELDS)

# The log walks the WHOLE graph, in topological order — side branches are
# collected, not silently dropped. It did walk first parents only, and that
# was not a presentation choice: it was what made the page's replay sound,
# because consecutive entries were then parent and child. The replay is now
# an ancestry walk (see `boundary_trees` and the page's `stateAt`), so the
# graph can be collected honestly.
#
# `--diff-merges=first-parent` STAYS, and now carries more weight than before:
# every commit's recorded diff is the step from its FIRST PARENT, which is
# exactly the step the ancestry walk replays. Drop it and a merge reports no
# files at all, so every file arriving on a branch would vanish from the
# reconstructed tree.
#
# `--topo-order` is stated because the default (reverse chronological) can
# interleave two branches by clock time, which makes lanes read as though work
# jumped between branches — and clocks on merged branches are not ordered.
#
# `-M` is stated rather than inherited: rename detection is configurable
# (`diff.renames`), and a payload that depends on the reader's git config is
# not the pure function of repository state this file promises.
LOG_BASE = ["log", "--topo-order", "--diff-merges=first-parent", "-M"]

# How many boundary trees the payload will measure. Each one costs a full
# `ls-tree` plus a full `diff --numstat` against the empty tree, so this is a
# real bound and not a formality. A window that needs more says so in
# `bases_truncated` rather than quietly reconstructing some commits wrongly:
# an honest gap beats a confident tree that never existed.
MAX_BOUNDARY_TREES = 8


def _git(argv, cwd):
    """Run a read-only git command; returns (rc, stdout, stderr).

    Never raises: git may be absent, may be a stub that hangs, may refuse.
    The caller turns any of those into a stated `state`, because a viewer
    that fails to render because git is missing is worse than a viewer
    without a History tab.
    """
    try:
        proc = subprocess.run(
            ["git"] + argv, cwd=str(cwd), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "", "{}: {}".format(type(exc).__name__, exc)

    def dec(raw):
        return (raw or b"").decode("utf-8", errors="replace")

    return proc.returncode, dec(proc.stdout), dec(proc.stderr)


def _split_records(blob):
    """One entry per commit, in log order, with the separator removed."""
    return [chunk for chunk in blob.split(REC_SEP) if chunk.strip("\x00\n ")]


def _parse_numstat(blob):
    """{sha: {path: (added, deleted)}} from `--numstat -z`.

    Line counts are None for a binary file: git reports `-` there, and
    reporting that as 0 would put every binary at the bottom of a
    lines-changed scale as though it had not changed.
    """
    out = {}
    for chunk in _split_records(blob):
        tokens = [t for t in chunk.split("\x00")]
        if not tokens:
            continue
        sha = tokens[0].strip()
        files, index = {}, 1
        while index < len(tokens):
            # git writes a newline between the formatted header and the
            # diff block, and -z makes it part of the first token
            token = tokens[index].lstrip("\n")
            index += 1
            if not token:
                continue
            parts = token.split("\t")
            if len(parts) < 3:
                continue
            added, deleted, path = parts[0], parts[1], parts[2]
            if path == "":
                # rename/copy: the path field is empty and the old and new
                # names follow as their own NUL-separated tokens
                if index + 1 < len(tokens):
                    path = tokens[index + 1]
                    index += 2
                else:
                    continue
            files[path] = (
                None if added == "-" else int(added),
                None if deleted == "-" else int(deleted))
        if sha:
            out[sha] = files
    return out


def assign_lanes(commits):
    """Give every commit a lane index, the way a graph log draws them.

    One pass over the topologically ordered list, newest first. A lane is a
    column that is currently "waiting" for a particular commit: when that
    commit arrives it takes the lane, and the lane then waits for its first
    parent. Every OTHER parent of a merge opens a lane of its own — that is
    the fork, drawn.

    Lanes are computed HERE rather than in the page for the same reason the
    diffs are: it is a pure function of the commit list, so it is testable
    without a browser, and two viewers of the same repository cannot disagree
    about what the history looked like.

    Each commit also gets what its ROW has to draw, because that is a pure
    function of the same walk and computing it twice — once here, once in the
    page — is how two renderings of one repository start to disagree:

      `lane`  the column this commit's dot sits in
      `rails` every column with a vertical line through this row: the lanes
              live before this commit and the lanes live after it, so a
              branch that merely passes a row is still drawn passing it
      `forks` the columns this commit joins BESIDES its own — one per extra
              parent, which is exactly a merge drawn as a merge
      `joins` the columns that END at this commit because they were waiting
              for it too. Walking backwards, a BRANCH POINT is where several
              lanes converge on one commit; whichever lane claims it, the
              others are finished and must be released or they are drawn
              descending forever toward a commit that already went by

    Mutates each commit dict, and returns the number of lanes used.
    """
    waiting = []          # waiting[i] = the sha lane i expects, or None

    def free_lane():
        for index, sha in enumerate(waiting):
            if sha is None:
                return index
        waiting.append(None)
        return len(waiting) - 1

    for commit in commits:
        sha = commit["sha"]
        before = {index for index, s in enumerate(waiting) if s is not None}
        lane, joins = None, []
        for index, expected in enumerate(waiting):
            if expected != sha:
                continue
            if lane is None:
                lane = index
            else:
                # A second lane was waiting for this same commit: this row is
                # the branch point where they converge. It claims nothing;
                # it ENDS. Leaving it set is what drew a phantom branch down
                # the rest of the history.
                joins.append(index)
                waiting[index] = None
        if lane is None:
            lane = free_lane()
        commit["lane"] = lane
        commit["joins"] = joins

        parents = commit.get("parents") or []
        # This lane continues into the first parent; a commit with no parents
        # ends it. Clearing rather than leaving it set is what lets a later
        # branch reuse the column instead of the graph growing forever.
        waiting[lane] = parents[0] if parents else None
        forks = []
        for extra in parents[1:]:
            if extra in waiting:
                # Already drawn: two merges of one branch, or an octopus arm
                # somebody else is holding. Point at the lane that has it
                # rather than opening a duplicate column for the same commit.
                forks.append(waiting.index(extra))
                continue
            opened = free_lane()
            waiting[opened] = extra
            forks.append(opened)

        after = {index for index, s in enumerate(waiting) if s is not None}
        commit["rails"] = sorted(before | after | {lane} | set(forks))
        commit["forks"] = forks

    return len(waiting)


def boundary_trees(repo, commits, limit=MAX_BOUNDARY_TREES):
    """The trees the page needs before it can replay anything.

    To rebuild the tree at commit X the page walks X's OWN first-parent chain
    backwards, applying each recorded diff, until it reaches a commit whose
    tree it already has. This finds those commits: every point where a
    displayed commit's first-parent chain leaves the window.

    Why first-parent chains specifically, when the graph is now a full DAG:
    each commit's recorded diff is the step from its FIRST parent
    (`--diff-merges=first-parent`), so a first-parent chain is the only path
    through the graph where every step is a diff we actually hold. Walking any
    other path would need diffs nobody collected.

    A root commit's boundary is the EMPTY TREE, keyed "" — the repository
    before its first commit is a real state, and treating it as "unavailable"
    would blank the oldest commit in every young repository.

    Returns ({sha_or_empty: {"files": [...], "lines": {...}}}, truncated).
    """
    inside = {c["sha"] for c in commits}
    needed = []
    for commit in commits:
        parents = commit.get("parents") or []
        first = parents[0] if parents else ""
        if first and first in inside:
            continue                       # the chain stays in the window
        if first not in needed:
            needed.append(first)

    trees, truncated = {}, False
    for sha in needed:
        if len(trees) >= limit:
            truncated = True
            break
        if sha == "":
            trees[""] = {"files": [], "lines": {}}
            continue
        rc, tree, _err = _git(["ls-tree", "-r", "--name-only", "-z", sha],
                              repo)
        if rc != 0:
            continue
        trees[sha] = {
            "files": sorted(p for p in tree.split("\x00") if p),
            "lines": base_line_counts(repo, sha),
        }
    return trees, truncated


def _parse_name_status(blob):
    """{sha: {path: (status, previous_path or None)}} from `--name-status -z`."""
    out = {}
    for chunk in _split_records(blob):
        tokens = [t for t in chunk.split("\x00")]
        if not tokens:
            continue
        sha = tokens[0].strip()
        files, index = {}, 1
        while index < len(tokens):
            status = tokens[index].lstrip("\n")
            index += 1
            if not status:
                continue
            letter = status[0]
            if letter in ("R", "C") and index + 1 < len(tokens):
                old, new = tokens[index], tokens[index + 1]
                index += 2
                files[new] = (letter, old)
            elif index < len(tokens):
                files[tokens[index]] = (letter, None)
                index += 1
        if sha:
            out[sha] = files
    return out


# git's own name for "nothing": diffing a tree against it reports every
# line of every file as added, which is exactly each file's line count.
# One command, no blob reading, and binaries report `-` the same way they
# do everywhere else.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def base_line_counts(repo, sha):
    """{path: lines} at `sha`; a binary file is absent, never zero.

    The History view sizes each circle by this, then keeps it current by
    replaying every later commit's added and deleted lines — so this is
    the only tree whose contents have to be measured directly.
    """
    rc, out, _err = _git(["diff", "--numstat", "-z", EMPTY_TREE, sha], repo)
    if rc != 0:
        return {}
    counts = {}
    for token in out.split("\x00"):
        token = token.strip("\n")
        if not token:
            continue
        parts = token.split("\t")
        if len(parts) < 3 or parts[0] == "-":
            continue
        try:
            counts[parts[2]] = int(parts[0])
        except ValueError:
            continue
    return counts


def discover_repo(start):
    """The work tree `start` lives in, or None when there is no repository."""
    rc, out, _err = _git(["rev-parse", "--show-toplevel"], start)
    if rc != 0 or not out.strip():
        return None
    return Path(out.strip())


def collect_git(store, repo, limit):
    """History of `repo` for the History view.

    Returns a payload whose `state` is always set: `ok`, `not_a_repo`,
    `no_commits`, `unavailable` (git could not be run) or `off`. Anything
    other than `ok` still renders — the tab says why instead of showing an
    empty stage that looks like a bug.
    """
    payload = {"state": "unavailable", "detail": "", "head": "",
               "branch": "", "prefix": "", "total": 0, "included": 0,
               "truncated": False, "lanes": 0,
               # One tree per point where the window's first-parent chains
               # leave it, keyed by that commit's sha ("" = the empty tree,
               # i.e. the repository before its first commit). The page
               # replays from whichever of these its selected commit's chain
               # reaches. `base` is the old single-tree field, kept as the
               # entry for the OLDEST first-parent boundary so a viewer page
               # from before this change still renders instead of blanking.
               "bases": {}, "bases_truncated": False,
               "base": {"sha": "", "files": [], "lines": {}},
               "commits": []}
    base = store if store.is_dir() else store.parent
    if repo is None:
        repo = discover_repo(base)
        if repo is None:
            payload["state"] = "not_a_repo"
            payload["detail"] = ("no git repository at or above {} — the "
                                 "History view needs one".format(base))
            return payload
    if not Path(repo).is_dir():
        payload["detail"] = "no directory at {}".format(repo)
        return payload
    repo = Path(repo)
    # NO `root` KEY. It used to carry the absolute host path of the work tree,
    # which makes a COMMITTED viewer differ per machine: regenerating the same
    # store on another clone produced a diff whose only content was where the
    # repository happened to sit. Nothing reads it — the viewer's only need is
    # `prefix`, the store's position INSIDE the repository, which is already
    # relative and is what maps graph paths onto git paths. An artifact that
    # differs per machine and says nothing is worse than one not committed at
    # all, so the field is gone rather than relativized to a constant.

    rc, out, err = _git(["rev-parse", "HEAD"], repo)
    if rc is None:
        payload["detail"] = "git could not be run: {}".format(err.strip())
        return payload
    if rc != 0:
        payload["state"] = "no_commits"
        payload["detail"] = "the repository has no commits yet"
        return payload
    payload["head"] = out.strip()

    _rc, branch, _err = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
    payload["branch"] = branch.strip()

    # Where the scanned tree sits inside the repository. The graph's file
    # paths are relative to the scan root; git's are relative to the repo
    # root, and the two only coincide when the scan root IS the repo root.
    payload["prefix"] = scan_prefix(store, repo)

    # The count matches what the LIST collects, which is the whole point:
    # counting first parents while listing the full graph would report a
    # total smaller than the number of commits on screen, and nothing in the
    # page could explain the difference. It changed meaning when the list
    # did — "commits in this repository", not "steps along the mainline".
    _rc, count, _err = _git(["rev-list", "--count", "HEAD"], repo)
    try:
        payload["total"] = int(count.strip())
    except ValueError:
        payload["total"] = 0

    window = ["--max-count={}".format(limit)] if limit else []
    rc, meta, err = _git(LOG_BASE + window + ["--format=" + COMMIT_FORMAT,
                                              "--no-patch"], repo)
    if rc != 0:
        payload["detail"] = "git log failed: {}".format(err.strip())
        return payload
    _rc, numstat, _err = _git(
        LOG_BASE + window + ["--format=" + REC_SEP + "%H", "--numstat", "-z"],
        repo)
    _rc, status, _err = _git(
        LOG_BASE + window + ["--format=" + REC_SEP + "%H", "--name-status",
                             "-z"], repo)
    stats = _parse_numstat(numstat)
    kinds = _parse_name_status(status)

    commits = []
    for chunk in _split_records(meta):
        fields = chunk.split(FIELD_SEP)
        if len(fields) < len(COMMIT_FIELDS):
            continue
        sha = fields[0].strip()
        files = []
        for path in sorted(set(stats.get(sha, {})) | set(kinds.get(sha, {}))):
            added, deleted = stats.get(sha, {}).get(path, (0, 0))
            letter, previous = kinds.get(sha, {}).get(path, ("M", None))
            entry = {"path": path, "status": letter,
                     "add": added, "del": deleted}
            if previous:
                entry["from"] = previous
            files.append(entry)
        parents = [p for p in fields[7].split() if p]
        commit = {
            "sha": sha,
            "short": fields[1].strip(),
            "date": fields[2].strip(),
            "author": fields[3],
            "author_email": fields[4].strip(),
            "parents": parents,
            "title": fields[8],
            "body": fields[9].strip("\n"),
            "files": files,
            "add": sum(f["add"] or 0 for f in files),
            "del": sum(f["del"] or 0 for f in files),
        }
        # Committer only when it differs from the author. A rebase, a
        # cherry-pick or a patch applied on somebody's behalf makes the two
        # different people, and that is exactly when the panel must say so;
        # repeating one name twice on every ordinary commit would bury it.
        committer, committed_at = fields[5], fields[6].strip()
        if committer != fields[3] or committed_at != commit["date"]:
            commit["committer"] = committer
            commit["committed_date"] = committed_at
        commits.append(commit)

    payload["lanes"] = assign_lanes(commits)
    payload["commits"] = commits
    payload["included"] = len(commits)
    payload["truncated"] = bool(limit) and payload["total"] > len(commits)

    # The trees the page replays FROM — one per point where the window's
    # first-parent chains leave it. This is what keeps the payload
    # proportional to the number of commits rather than to commits x files,
    # and it is the half that makes a DAG's reconstruction exact rather than
    # plausible.
    bases, bases_truncated = boundary_trees(repo, commits)
    payload["bases"] = bases
    payload["bases_truncated"] = bases_truncated

    # `base`, singular, keeps its ORIGINAL meaning exactly: the tree AT the
    # oldest commit shown. It is not a view onto `bases` — those are keyed by
    # BOUNDARY commits, the parents where the window's chains leave it, which
    # is a different set and usually a different tree. Deriving one from the
    # other would have made the compatibility field quietly wrong in the most
    # common case of all: when the window reaches the root commit, the
    # boundary is the EMPTY tree, and a page reading `base` would have drawn
    # an empty repository where the old field held the root's files.
    #
    # A compatibility field that is subtly wrong is worse than one that is
    # missing, so it costs one extra `ls-tree` and stays true. The page's own
    # fallback keys it by this sha, which reproduces the old replay exactly:
    # the walk stops AT the oldest commit and does not apply its diff.
    if commits:
        oldest = commits[-1]["sha"]
        rc, tree, _err = _git(["ls-tree", "-r", "--name-only", "-z", oldest],
                              repo)
        files = sorted(p for p in tree.split("\x00") if p) if rc == 0 else []
        payload["base"] = {"sha": oldest, "files": files,
                           "lines": base_line_counts(repo, oldest)}
    payload["state"] = "ok"
    return payload


# --------------------------------------------------------------------------
# the disk walk (the Repo frame's own source of truth)
# --------------------------------------------------------------------------
# `.git` is the ONLY directory skipped by name, and it is skipped because it
# is git's private storage rather than the project's content: thousands of
# loose objects would swamp the packing with a tree nobody wrote. Everything
# else present is shown, gitignored or not (N-6.2) — the whole point of this
# frame is to make accumulation VISIBLE, and the files that accumulate
# unnoticed are exactly the ignored ones: checkpoints, reports, caches.
DISK_SKIP_DIRS = {".git"}
# A bound, so a viewer pointed at a repository with a node_modules tree
# renders instead of hanging. Exceeding it is REPORTED, never silent: a frame
# whose promise is "everything on disk" must say when it stopped short.
MAX_DISK_FILES = 20000


def content_paths(root):
    """What THIS repository calls its own content, or None outside one.

    `git ls-files --cached --others --exclude-standard` — tracked plus
    untracked-and-not-ignored, which is git's own answer to "what is this
    project made of", asked once and never re-implemented here. Paths come
    back posix-relative to `root`, which is exactly how the walk below spells
    them.

    WHY THE FRAME NEEDED THIS. `5.4.1` argues, correctly, that the files
    nobody records are the files that accumulate, and that a frame hiding the
    ignore list would be hiding the thing it exists to show. That argument
    survives — as a MODE. What it could not survive was the default: pointed
    at a Claude Code home this walk returned 7779 files against 402 the
    repository tracks, because `projects/`, `plugins/` and `file-history/` are
    runtime state with thousands of entries. The project itself became a
    speck, the extension legend filled with timestamped runtime suffixes, and
    the packing grew past what any fit could show. Accumulation was visible
    and nothing else was.

    So every entry is LABELLED and none is dropped: one walk, one payload, and
    a scope control in the frame that costs no second request. Outside a
    repository — or where git cannot be run — there is no such thing as an
    ignored file here, and `None` says exactly that rather than guessing.
    """
    rc, out, _err = _git(["ls-files", "--cached", "--others",
                          "--exclude-standard", "-z"], root)
    if rc != 0:
        return None
    return {piece for piece in out.split("\x00") if piece}


def collect_disk(root, limit=MAX_DISK_FILES, exclude=()):
    """Every file under `root`, as the Repo frame draws it.

    Returns {"state", "files": [{"path", "bytes", "link"}], "truncated",
             "dirs", "detail"}.

    `exclude` is the set of absolute paths THIS RUN will write — the rendered
    page and its two assets. A frame that draws the file it is being written
    into reports a tree that changes every time it is rendered, which breaks
    the byte-identical re-render the whole store depends on (K9) and puts a
    diff into every commit that carries no information. The instrument is not
    part of the content it measures.

    SYMLINKS ARE LISTED, NEVER FOLLOWED. `os.walk(followlinks=False)` keeps
    the walk out of a link's target, and `lstat` measures the link itself, so
    a link into a parent directory cannot make the walk unbounded and a link
    to a 2 GB file cannot claim 2 GB of this tree. The entry is still drawn:
    it IS on disk, which is what this frame reports.
    """
    payload = {"state": "unavailable", "detail": "", "files": [],
               "truncated": False, "dirs": 0,
               "content": 0, "ignored": 0, "scoped": False}
    root = Path(root)
    if not root.is_dir():
        payload["detail"] = "no directory at {}".format(root)
        return payload

    skip = set()
    for path in exclude or ():
        try:
            skip.add(os.path.realpath(str(path)))
        except OSError:
            continue
    content = content_paths(root)
    files, dirs, truncated = [], 0, False
    kept, ignored = 0, 0
    for folder, subdirs, names in os.walk(str(root), followlinks=False):
        subdirs[:] = sorted(d for d in subdirs if d not in DISK_SKIP_DIRS)
        dirs += len(subdirs)
        for name in sorted(names):
            if len(files) >= limit:
                truncated = True
                break
            full = Path(folder) / name
            try:
                if os.path.realpath(str(full)) in skip:
                    continue
            except OSError:
                pass
            try:
                rel = full.relative_to(root).as_posix()
            except ValueError:
                continue
            try:
                stat = os.lstat(str(full))
                size = int(stat.st_size)
                link = os.path.islink(str(full))
            except OSError:
                # Unreadable is still PRESENT. Dropping it would under-report
                # the tree in exactly the case a reader most wants to know
                # about, so it is listed with no size rather than omitted.
                size, link = 0, False
            entry = {"path": rel, "bytes": size}
            if link:
                entry["link"] = True
            if content is not None and rel not in content:
                # Present, and not part of what this repository is made of.
                # Labelled, never omitted: the frame draws it on the scopes
                # that ask for it, and its absence from the default scope is
                # the repository's own statement, not this walk's opinion.
                entry["ignored"] = True
                ignored += 1
            else:
                kept += 1
            files.append(entry)
        if truncated:
            break

    payload["files"] = files
    payload["dirs"] = dirs
    payload["truncated"] = truncated
    payload["content"] = kept
    payload["ignored"] = ignored
    payload["scoped"] = content is not None
    payload["state"] = "ok"
    if truncated:
        payload["detail"] = ("stopped at {} files — the tree is larger than "
                             "this frame draws".format(limit))
    return payload


def portable_source(graph_dir, repo):
    """`graph_dir` as a path that means the same thing on every machine.

    The footer prints this. It used to print `str(graph_dir)` — an absolute
    host path — so a committed `graph-view.html` embedded the operator's
    directory layout, and any other clone regenerated a diff carrying no
    information at all. Anchored, in order of preference:

      1. to the repository root, which every clone shares  -> `memory/graph`
      2. to the store's parent, when there is no repository
      3. to the last two segments, when neither anchor applies

    Never absolute, and never the wall-clock or host state that K9 already
    keeps out of `generated_at`.
    """
    graph_dir = Path(graph_dir)
    for anchor in (repo, graph_dir.parent.parent):
        if not anchor:
            continue
        try:
            rel = graph_dir.resolve().relative_to(Path(anchor).resolve())
        except (ValueError, OSError):
            continue
        text = rel.as_posix()
        if text and text != ".":
            return text
    parts = graph_dir.parts[-2:]
    return "/".join(parts) if parts else graph_dir.name


def scan_prefix(store, repo):
    """The scan root, relative to the repository root, as a `a/b` prefix."""
    state = store / "graph" / "scan-state.json"
    try:
        raw = json.loads(state.read_text(encoding="utf-8", errors="replace"))
        root = raw.get("root")
    except (OSError, ValueError, AttributeError):
        root = None
    if not root:
        return ""
    try:
        rel = Path(root).resolve().relative_to(Path(repo).resolve())
    except (ValueError, OSError):
        return ""
    text = str(rel).replace("\\", "/")
    return "" if text == "." else text


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def _project_node(rec):
    out = {k: rec.get(k) for k in NODE_FIELDS
           if k not in ("card_body", "card_truncated")}
    if "card_body" in rec:
        out["card_body"] = rec["card_body"]
        out["card_truncated"] = bool(rec.get("card_truncated"))
    return out


def render(nodes, edges, meta, template_bytes, git=None, disk=None):
    """Inject the graph JSON into the frozen template; return HTML bytes.

    The nodes are sorted by id before serialization — the viewer's layout
    determinism leans on that order, so it is part of the data contract.
    """
    data = {
        "nodes": [_project_node(r)
                  for r in sorted(nodes.values(), key=lambda r: r["id"])],
        "edges": [{k: r.get(k) for k in EDGE_FIELDS}
                  for r in sorted(edges.values(), key=lambda r: r["id"])],
        "meta": meta,
        "git": git if git is not None else {"state": "off", "commits": []},
        # The Repo frame's own tree. Separate from `nodes` on purpose: the
        # node set is what a SCAN recorded, and the point of this frame is
        # what is there whether anything recorded it or not (N-6.2).
        "disk": disk if disk is not None
                else {"state": "off", "files": [], "truncated": False},
    }
    # Escape `<` as < so no HTML tokenizer state (`</script`, `<!--`,
    # `<script`) can be entered from inlined data (K7). `<` only ever occurs
    # inside JSON string values, and < is a valid JSON escape.
    blob = json.dumps(data, ensure_ascii=False, sort_keys=True)
    blob = blob.replace("<", "\\u003c")
    html = template_bytes.decode("utf-8")
    html = html.replace(DATA_PLACEHOLDER, blob)
    return html.replace("\r\n", "\n").encode("utf-8")


def write_if_changed(path, payload):
    """Write `payload` unless the file already holds those exact bytes.

    Returns True when the file was (re)written. Skipping identical writes
    keeps an unchanged store diff-free (K9).
    """
    if path.is_file() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    # bytes, so no write_text(newline=) (Python 3.8 floor)
    with path.open("wb") as fh:
        fh.write(payload)
    return True


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
class JsonArgumentParser(argparse.ArgumentParser):
    """argparse that honours the JSON-on-stdout / exit-2 usage contract."""

    def error(self, message):
        sys.stdout.write(json.dumps({
            "status": "BLOCKED", "error": message,
            "usage": self.format_usage().strip(),
        }) + "\n")
        raise SystemExit(2)

    def exit(self, status=0, message=None):
        if status and message:
            sys.stdout.write(json.dumps({
                "status": "BLOCKED", "error": message.strip()}) + "\n")
        raise SystemExit(status)


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("expected an integer")
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def build_parser():
    ap = JsonArgumentParser(
        prog="memory_viz.py",
        description="Render a memory store's JSONL logs into graph-view"
                    ".html/.css/.js using the frozen memory-viewer assets.")
    ap.add_argument("--store", default="memory",
                    help="memory store directory (default: memory)")
    ap.add_argument("--out", default=None,
                    help="output HTML path (default "
                         "<store>/" + SNAPSHOT_NAME + ", the DERIVED page; "
                         "the tracked bootstrap graph-view.html is never "
                         "written by this script)")
    ap.add_argument("--standalone", action="store_true",
                    help="write graph-view.css/.js beside the page and "
                         "link them there, instead of linking the store's "
                         "vendored memory-viewer/ copies (implied when the "
                         "page is written outside the store)")
    ap.add_argument("--include-invalidated", action="store_true",
                    help="inline invalidated records too (default: live only)")
    ap.add_argument("--limit", type=_positive_int, default=None,
                    help="inline only the top-N nodes plus induced edges")
    ap.add_argument("--rank", choices=("degree",), default="degree",
                    help="ranking used by --limit (default: degree)")
    ap.add_argument("--no-card-bodies", action="store_true",
                    help="do not inline card bodies")
    ap.add_argument("--force-out", action="store_true",
                    help="allow --out to point outside the store's parent")
    ap.add_argument("--repo", default=None,
                    help="repository whose history feeds the History view"
                         " (default: the one containing the store)")
    ap.add_argument("--commits", type=int, default=DEFAULT_COMMIT_LIMIT,
                    help="how many commits to inline, newest first"
                         " (default {}; 0 = all)".format(DEFAULT_COMMIT_LIMIT))
    ap.add_argument("--no-git", action="store_true",
                    help="do not read any git history (History view says so)")
    ap.add_argument("--disk-root", default=None,
                    help="directory the Repo view walks (default: the "
                         "repository containing the store, else the store's "
                         "parent). Everything present is drawn, gitignored "
                         "files included; symlinks are listed, never "
                         "followed")
    return ap


def run(argv):
    args = build_parser().parse_args(argv)

    store = Path(args.store)
    graph_dir = store / "graph"
    out = Path(args.out) if args.out else store / SNAPSHOT_NAME
    # WHICH LAYOUT this render is in, decided once. Inside a store the
    # frozen assets are vendored exactly once under `memory-viewer/` and
    # the page links them there; a page written anywhere else has no
    # package beside it and must carry its own copies, or it opens
    # unstyled off disk. `--standalone` asks for the second layout
    # explicitly, which is the only way to get the beside copies inside a
    # store — and the store then owns two of each, deliberately.
    standalone = args.standalone or not _within(out.parent, store)

    if not store.is_dir():
        sys.stdout.write(json.dumps({
            "status": "BLOCKED", "error": "no store at {}".format(store),
            "hint": "initialize the memory store first",
        }) + "\n")
        return 2

    # K10.9 — refuse an --out that escapes the store's parent unless forced.
    if not args.force_out and not _within(out.parent, store.parent):
        sys.stdout.write(json.dumps({
            "status": "BLOCKED",
            "error": "--out {} is outside {}".format(out, store.parent),
            "hint": "pass --force-out to write there anyway",
        }) + "\n")
        return 2

    # Frozen assets are a precondition: refuse before touching the store.
    assets, asset_error = load_assets()
    if asset_error is not None:
        sys.stdout.write(json.dumps(asset_error) + "\n")
        return 2

    if not graph_dir.is_dir():
        sys.stderr.write("advisory: {} does not exist - emitting empty-state "
                         "page\n".format(graph_dir))
        nodes, edges, info = {}, {}, {"malformed": 0, "newest": ""}
    else:
        nodes, edges, info = load_logs(store)
        if not nodes:
            sys.stderr.write("advisory: memory graph is empty - emitting "
                             "empty-state page\n")
        if info["malformed"]:
            sys.stderr.write("advisory: {} malformed line(s) skipped\n".format(
                info["malformed"]))

    total_nodes, total_edges = len(nodes), len(edges)
    nodes, edges, hidden_nodes, hidden_edges = split_invalidated(
        nodes, edges, args.include_invalidated)
    nodes, edges, limited = apply_limit(nodes, edges, args.limit, args.rank)

    cards = {"cards_inlined": 0, "card_bytes": 0, "cards_outside_store": 0,
             "cards_missing": 0}
    if not args.no_card_bodies:
        cards = inline_card_bodies(nodes, store)

    superseded = {r.get("dst") for r in edges.values()
                  if r.get("type") == "supersedes"
                  and r.get("invalid_at") is None}

    meta = {
        # K9 — newest record timestamp, never the wall clock.
        "generated_at": info["newest"] or "unknown",
        "source": portable_source(graph_dir, args.repo),
        "malformed": info["malformed"],
        "invalidated_nodes_hidden": hidden_nodes,
        "invalidated_edges_hidden": hidden_edges,
        "include_invalidated": bool(args.include_invalidated),
        "limited": limited,
        "limit": args.limit if limited else 0,
        "rank": args.rank if limited else "",
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "cards_inlined": cards["cards_inlined"],
    }

    # The Repo frame walks the DISK (N-6.2). It is deliberately NOT the git
    # tree and deliberately NOT the node set: History already shows what git
    # knows, and the node set is what a scan recorded. What neither shows is
    # what has quietly accumulated — checkpoints, reports, caches — and that
    # is precisely what a reader opens this frame to see.
    disk_root = args.disk_root or (
        args.repo or discover_repo(store if store.is_dir() else store.parent)
        or store.parent)
    disk = collect_disk(disk_root, exclude=(
        out, out.parent / ASSET_CSS, out.parent / ASSET_JS,
        # The shared floor is a FOURTH output of a standalone render, and
        # a frame that draws what this run is writing re-renders differently
        # every time. Excluded by exact path, like the other three.
        out.parent / ASSET_PACKING,
        store / ASSET_SHARED_DIR / ASSET_PACKING))
    if disk["state"] != "ok":
        sys.stderr.write("advisory: no disk tree — {}\n".format(
            disk["detail"] or disk["state"]))
    elif disk["truncated"]:
        sys.stderr.write("advisory: {}\n".format(disk["detail"]))
    meta["disk_state"] = disk["state"]
    meta["disk_files"] = len(disk["files"])
    meta["disk_root"] = portable_source(Path(disk_root) / "_", args.repo)

    if args.no_git:
        git = {"state": "off", "detail": "--no-git was passed", "commits": [],
               "base": {"sha": "", "files": []}, "bases": {},
               "bases_truncated": False, "lanes": 0, "total": 0, "included": 0,
               "truncated": False, "head": "", "branch": "",
               "prefix": ""}
    else:
        git = collect_git(store, args.repo, max(0, args.commits))
        if git["state"] != "ok":
            sys.stderr.write("advisory: no commit history — {}\n".format(
                git["detail"] or git["state"]))
    meta["git_state"] = git["state"]
    meta["commits_inlined"] = git["included"]

    payload = render(nodes, edges, meta, assets[ASSET_TEMPLATE], git, disk)

    # STANDALONE: graph-view.css / graph-view.js land beside the HTML,
    # byte-identical to the frozen assets, and the template's relative
    # links already reach them. VENDORED (a page inside a store): the
    # store already holds one copy of each under `memory-viewer/`, put
    # there by `memory_views.py install`, so this render writes no assets
    # at all and re-points the page instead. Writing them anyway is what
    # left stale beside-copies in delivered stores, where the gate then
    # reported the page as drawn by a viewer the system no longer carries.
    if standalone:
        out_css = out.parent / ASSET_CSS
        out_js = out.parent / ASSET_JS
        # FLAT, like the other two: a standalone page links `./packing.js`
        # because nothing re-points it, and a page whose floor is missing
        # draws nothing at all.
        out_pack = out.parent / ASSET_PACKING
    else:
        payload = point_at_vendored_assets(payload)
        out_css = store / ASSET_DIR_NAME / ASSET_CSS
        out_js = store / ASSET_DIR_NAME / ASSET_JS
        out_pack = store / ASSET_SHARED_DIR / ASSET_PACKING
    try:
        written = write_if_changed(out, payload)
        written_css = (write_if_changed(out_css, assets[ASSET_CSS])
                       if standalone else False)
        written_js = (write_if_changed(out_js, assets[ASSET_JS])
                      if standalone else False)
        written_pack = (write_if_changed(out_pack,
                                         assets[ASSET_PACKING])
                        if standalone else False)
    except OSError as exc:
        sys.stdout.write(json.dumps({
            "status": "FAILED", "error": "{}: {}".format(
                type(exc).__name__, exc)}) + "\n")
        return 1

    summary = {
        "status": "COMPLETED",
        "nodes": len(nodes),
        "edges": len(edges),
        "superseded": sum(1 for nid in nodes if nid in superseded),
        "invalidated_nodes_hidden": hidden_nodes,
        "invalidated_edges_hidden": hidden_edges,
        "malformed": info["malformed"],
        "cards_inlined": cards["cards_inlined"],
        "card_bytes": cards["card_bytes"],
        "cards_outside_store": cards["cards_outside_store"],
        "cards_missing": cards["cards_missing"],
        "limited": limited,
        "git_state": git["state"],
        "commits": git["included"],
        "commits_truncated": git["truncated"],
        "generated_at": meta["generated_at"],
        "bytes": len(payload),
        "written": written,
        "written_css": written_css,
        "written_js": written_js,
        "layout": "standalone" if standalone else "vendored",
        "out": str(out),
        "out_css": str(out_css),
        "out_js": str(out_js),
    }
    sys.stdout.write(json.dumps(summary) + "\n")
    return 0


def main(argv=None):
    try:
        return run(argv)
    except SystemExit:
        raise
    except Exception as exc:  # JSON error payload, never a traceback
        sys.stdout.write(json.dumps({
            "status": "FAILED",
            "error": "{}: {}".format(type(exc).__name__, exc),
        }) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
