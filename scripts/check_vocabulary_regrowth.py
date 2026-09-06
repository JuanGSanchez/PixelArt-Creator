#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: check_vocabulary_regrowth  (standalone P11 script — PixelArt Creator)
# =============================================================================
# PURPOSE: Stop the internal development-system vocabulary from re-entering
#   this PUBLIC product repository. Seven token families were cleaned from the
#   tracked tree and measured at zero on 2026-09-06, then regrew TWICE inside
#   one job that same day (in shipped source and in CI wiring) and were caught
#   only by a hand-run grep. This gate is the deterministic replacement for
#   that grep: it fails a pull request the moment any tracked file, or any
#   commit message the pull request itself adds, carries one of the eight
#   patterns below -- naming every file, line and token, never just a count.
# FLAVOUR: standalone
# LOCATION: scripts/check_vocabulary_regrowth.py
# INVOKED BY: CI, as a step inside the existing `quality-gate` job (never its
#   own job -- the branch-protection ruleset matches required checks BY NAME,
#   and a new job would not be enforced without a repository-settings change
#   nobody has requested).
# RUNTIME: Python 3.8+ (CPython, stdlib only: argparse, json, os, re,
#   subprocess, sys).
# ENTRYPOINT: python scripts/check_vocabulary_regrowth.py [--root .]
#             [--base-sha SHA --head-sha SHA]
# INPUTS:
#   --root      (CLI arg, optional, default "."): repo root, matching the
#               neighbour scripts' `--root .` CI convention.
#   --base-sha / --head-sha (CLI args, optional, MUST be given together): the
#               two ends of the commit range a pull request adds. When both
#               are given, `git log --format=%H <base>..<head>` is resolved
#               and every commit message in that range is scanned too. When
#               NEITHER is given (a local run, or CI outside a pull_request
#               event), the commit-message half is SKIPPED -- loudly, on
#               stderr, naming the reason -- never silently treated as
#               passing. Giving only one of the two is a usage error
#               (exit 2): a half-specified range is not a range.
# OUTPUTS:
#   stdout: JSON {"findings":[{"kind":"file"|"commit-message", "pattern",
#            "file"|"commit", "line"|"subject", "token"}], "scanned":
#            {"files_examined":N, "files_skipped_binary":N,
#             "commit_messages_examined":N|null,
#             "commit_message_check":"ran"|"skipped"}}.
#   stderr: human summary, including the denominator every run and, when the
#            commit-message half is skipped, the loud, named reason. Exit
#            code per EXIT CODES.
# EXIT CODES: 0 clean (both denominators healthy, no findings) -> COMPLETED ;
#   1 finding(s) -> FAILED ; 2 usage/environment error (root not found, git
#   not resolvable, a half-specified commit range, a resolved commit range
#   with zero commits in it, or zero tracked text files examined) -> BLOCKED.
#   A denominator of zero is NEVER read as "nothing to report" -- it is
#   always the BLOCKED path (P11: this project has recorded five gates that
#   passed while unable to answer their own question).
# PRECONDITIONS: --root is a git working tree with `git` resolvable on PATH.
#   For the commit-message half, --base-sha/--head-sha must both resolve in
#   the local object graph (the CI job that runs this script checks out full
#   history, `fetch-depth: 0`, precisely so this resolves).
# DETERMINISM NOTE: deterministic; no network, no time/random. The tracked
#   file list is read from git's OWN index (`git ls-files`), never a
#   filesystem walk, so ignored or untracked scratch can never make this gate
#   red. File CONTENT is read from the git object store at HEAD
#   (`git show HEAD:<path>`), not from the working tree, for the same reason:
#   an uncommitted, gitignored scratch edit sitting in a developer's working
#   copy is never what a pull request actually adds. Findings are sorted by
#   (kind, file/commit, line/subject, pattern, token).
#
# THE EIGHT PATTERNS (maintainer ruling, 2026-09-06 mailbox, answered at
#   intake -- do NOT add the pre-existing D-nn / Q-nn / CL-nn identifiers,
#   819 occurrences across the product and explicitly OUT of this gate's
#   scope; cleaning them here would bury this change):
#   AGT-nn, REC-n, OQ-n, bare T-nn, DEV-n, WP-n (all six: an ASCII letter
#   prefix, a hyphen, then one or more ASCII digits, at a word boundary on
#   both sides -- so a compound id like "AGT-12" is never miscounted twice as
#   a bare "T-12" hit, since there is no word boundary between the "G" and
#   the "T" the bare pattern would need); plus the two literals `design-docs`
#   and `subagent-report` (no digit placeholder -- these match as plain
#   substrings).
#
# MEASURED FALSE-POSITIVE RISK (mailbox Q-2, bare T-nn): scanned this tree
#   (875 tracked text files, 2026-09-06) with the exact `\bT-\d+\b` pattern
#   used below -- ZERO matches, including inside the many compound ids
#   (AGT-nn, DEV-n, WP-n, CL-nn, D-nn) already present in the corpus, because
#   none of those has a word boundary immediately before its own trailing
#   "T-<digits>" substring. No narrowing applied: the measurement shows no
#   present risk, and the word-boundary anchor is exactly what a future
#   legitimate use (a table row label like "Row T-1", a generic type
#   parameter "T-0") would still need to trip it -- plain prose almost never
#   writes a bare capital "T" immediately followed by a hyphen and digits.
#   Recorded here rather than silently narrowing a pattern that measured
#   clean: no false positive may ever be introduced by this gate on the
#   current tree, so the reasoning is written down either way -- narrowed or
#   not -- rather than the narrowing decision being made silently.
#
# ALLOWLIST vs EXCLUDE -- two different mechanisms, never merged:
#   EXCLUDE (a path is not scanned at all, for ANY pattern): `.gitignore`
#     itself -- because its own rules legitimately NAME the things it
#     excludes, e.g. the literal line `design-docs/`; every path under
#     `memory/graph/` (a generated store, not authored content); and this
#     gate's OWN source file, `scripts/check_vocabulary_regrowth.py`, for the
#     reason given in SELF-TRIPPING RESOLUTION below -- and no other file.
#   ALLOWLIST (a path IS scanned and counted in the denominator, but one
#     specific (path, pattern) pair's matches are suppressed, with the reason
#     recorded inline): the three functional path checks in
#     `memory/product_boundary.py` (lines 5 and 100) and
#     `testing/product_boundary.py` (line 98) -- each tests for a
#     `design-docs/` directory on disk to distinguish a container repository
#     from a product repository; that is a functional path check, not an
#     unresolvable reference to this development system, and a gate that
#     failed on it is a gate nobody could keep green (measured 2026-09-06:
#     these are the ONLY three `design-docs` occurrences in the whole tree).
#
# SELF-TRIPPING RESOLUTION -- NARROWED 2026-09-06 after
#   the maintainer measured the wider version's blast radius (a planted
#   `AGT-05` committed into `.github/workflows/ci.yml` scanned clean under
#   the original three-file allowlist -- exactly the hole the original
#   cleanup closed, since the pre-cleanup record cites this vocabulary
#   appearing in exactly this category of file, e.g.
#   `packaging/build_appimage.sh` and `packaging/README.md`). STATED
#   EXPLICITLY so a future maintainer "simplifying" this file does not widen
#   it back for convenience:
#   ONLY ONE FILE IS EXCLUDED, by exact repository-relative path:
#     - scripts/check_vocabulary_regrowth.py       (this file, and this file
#       alone)
#   WHY THIS ONE HAS NO WAY AROUND IT: a scanner's own source must state the
#   patterns it scans for -- there is no rewriting that removes that fact --
#   and this is one small, single-purpose, rarely-edited file whose entire
#   reason to exist is holding those patterns.
#   WHY NOTHING ELSE IS EXCLUDED, even though it would be convenient:
#   `.github/workflows/ci.yml` and
#   `testing/suites/scripts/test_check_vocabulary_regrowth.py` are BOTH
#   ordinary, routinely-edited files -- ci.yml is edited on ordinary DevOps
#   work, not just to touch this gate, and is precisely the category of file
#   (build/CI/packaging plumbing) the vocabulary reappeared in before. A
#   whole-file exemption on either would recreate exactly the hole the
#   original cleanup closed, just relocated to a spot this gate itself
#   created. Neither NEEDS an exemption: the CI step below invokes this
#   script and describes it only in PROSE ("the internal development-system
#   identifier families cleaned from this repository" -- never spelling out
#   AGT-nn/REC-n/OQ-n/DEV-n/WP-n/T-nn/design-docs/subagent-report
#   literally), and the test module below plants every one of its eight
#   proof tokens by RUNTIME STRING CONCATENATION (e.g. `"AGT" + "-05"`)
#   rather than as an intact literal, so neither file's own tracked source
#   contains a real instance of any pattern. If a future change to either
#   file ever needs to write out one of these literals intact and cannot
#   avoid it, that is the signal to ADD a narrowly-scoped, reasoned
#   allowlist entry for that one case -- not to re-exempt the whole file.
#   A future maintainer must not widen this back to the whole file without
#   an equivalent, reasoned narrowing in its place.
#
# ## Principles Applied
# Inherited: P1 (grounded in the 2026-09-06 vocabulary-cleanup measurement
#   and the maintainer's rulings that followed it), P2,
#   P3 (entrypoint + I/O), P4, P6 (stdlib only), P7, P9 (one job: vocabulary-
#   regrowth detection; report-only against the tree it is given, never
#   auto-fixes), P10 (exit code is the verdict), P11 (script vehicle),
#   P12 (reports every occurrence, not a count), P13.
# Custom: reads tracked content through git (`git ls-files` / `git show`),
#   never a filesystem walk, so ignored/untracked scratch can never turn
#   this gate red; refuses (exit 2) on a zero denominator in either
#   half, rather than reading an empty scan as a pass.
#
# SOURCES: the 2026-09-06 measurement establishing that the seven cleaned
#   token families sit at zero occurrences on this repository's tracked tree,
#   and the maintainer's rulings that followed it (which families are in
#   scope, that the commit-message half is bounded to the commits a pull
#   request adds, and that this step must live inside the existing
#   quality-gate job rather than a new one); asset-templates.md §Script;
#   scripts/check_doc_references.py and scripts/check_cycles.py (house style
#   for standalone P11 scripts).
# =============================================================================
import argparse
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Exclusions (never scanned at all) -- see the module docstring for the
# reasoning behind each entry.
# ---------------------------------------------------------------------------
EXCLUDE_EXACT_PATHS = {
    ".gitignore",
    # SELF-TRIPPING RESOLUTION, NARROWED 2026-09-06 -- see module docstring.
    # ONLY this gate's own source is exempt: its test module and the CI step
    # that wires it are DELIBERATELY NOT exempt (both are written to contain
    # no literal pattern instead -- see the module docstring for why a
    # whole-file exemption on either would be a hole).
    "scripts/check_vocabulary_regrowth.py",
}
EXCLUDE_PATH_PREFIXES = ("memory/graph/",)  # a generated store, not authored content

# ---------------------------------------------------------------------------
# Allowlist (scanned + counted, but these specific (path, pattern) hits are
# known-legitimate functional path checks -- see module docstring).
# ---------------------------------------------------------------------------
_DESIGN_DOCS_REASON = (
    "tests for a design-docs/ directory on disk to distinguish a container "
    "repository from a product repository (not a reference to this "
    "development system)"
)
ALLOWLIST_HITS = {
    ("memory/product_boundary.py", "design-docs"): _DESIGN_DOCS_REASON,
    ("testing/product_boundary.py", "design-docs"): _DESIGN_DOCS_REASON,
}

# ---------------------------------------------------------------------------
# The eight patterns. The six digit-suffix families share one shape: an
# ASCII letter prefix, a hyphen, one-or-more digits, word-bounded both sides.
# ---------------------------------------------------------------------------
PATTERNS = {
    "AGT-nn": re.compile(r"\bAGT-\d+\b"),
    "REC-n": re.compile(r"\bREC-\d+\b"),
    "OQ-n": re.compile(r"\bOQ-\d+\b"),
    "T-nn(bare)": re.compile(r"\bT-\d+\b"),
    "DEV-n": re.compile(r"\bDEV-\d+\b"),
    "WP-n": re.compile(r"\bWP-\d+\b"),
    # Split so this file's own source never contains the intact literal --
    # belt-and-suspenders alongside the path exclusion above (module
    # docstring, SELF-TRIPPING RESOLUTION).
    "design-docs": re.compile("design" + "-docs"),
    "subagent-report": re.compile("subagent" + "-report"),
}


def _run_git(args, root):
    """Run a git subcommand rooted at `root`. Returns (stdout, returncode).
    Never raises on a non-zero exit -- callers decide what that means."""
    completed = subprocess.run(
        ["git"] + args,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout, completed.returncode


def excluded(rel_path):
    if rel_path in EXCLUDE_EXACT_PATHS:
        return True
    return any(rel_path.startswith(p) for p in EXCLUDE_PATH_PREFIXES)


def tracked_files(root):
    """Return the sorted list of tracked file paths (git-relative, '/'
    separated) via `git ls-files -z` -- the git INDEX, never a filesystem
    walk, so ignored/untracked scratch can never appear here."""
    out, code = _run_git(["ls-files", "-z"], root)
    if code != 0:
        return None
    paths = [p for p in out.split("\x00") if p]
    return sorted(paths)


def file_findings(root, paths):
    """Scan each tracked, non-excluded path's HEAD content for the eight
    patterns. Returns (findings, files_examined, files_skipped_binary)."""
    findings = []
    examined = 0
    skipped_binary = 0
    for rel in paths:
        if excluded(rel):
            continue
        content, code = _run_git(["show", "HEAD:%s" % rel], root)
        if code != 0:
            # Could not read this blob at HEAD (e.g. a submodule gitlink,
            # or a path that only exists in the working tree, not HEAD) --
            # not countable as an examined text file.
            continue
        # `text=True` + errors="replace" above never raises, so detect a
        # binary blob by the presence of a NUL byte in the decoded text
        # (a real UTF-8 text file never legitimately contains one).
        if "\x00" in content:
            skipped_binary += 1
            continue
        examined += 1
        lines = content.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for pattern_name, pattern in PATTERNS.items():
                if (rel, pattern_name) in ALLOWLIST_HITS:
                    continue  # suppressed -- see ALLOWLIST_HITS reason
                for m in pattern.finditer(line):
                    findings.append(
                        {
                            "kind": "file",
                            "pattern": pattern_name,
                            "file": rel,
                            "line": lineno,
                            "token": m.group(0),
                        }
                    )
    return findings, examined, skipped_binary


def commit_message_findings(root, base_sha, head_sha):
    """Scan the subject+body of every commit in base_sha..head_sha (the
    commits a pull request ADDS -- never the whole history). Returns
    (findings, commit_count, error) -- error is a human string on git
    failure (unresolvable range), else None."""
    rng = "%s..%s" % (base_sha, head_sha)
    out, code = _run_git(["log", "--format=%H", rng], root)
    if code != 0:
        return [], 0, "git log %s failed (exit %d) -- unresolvable range" % (rng, code)
    hashes = [h for h in out.splitlines() if h.strip()]
    findings = []
    for commit_hash in hashes:
        msg, msg_code = _run_git(["show", "-s", "--format=%B", commit_hash], root)
        if msg_code != 0:
            return [], len(hashes), "could not read message for %s" % commit_hash
        subject = msg.splitlines()[0] if msg.splitlines() else ""
        for pattern_name, pattern in PATTERNS.items():
            for m in pattern.finditer(msg):
                findings.append(
                    {
                        "kind": "commit-message",
                        "pattern": pattern_name,
                        "commit": commit_hash[:12],
                        "subject": subject,
                        "token": m.group(0),
                    }
                )
    return findings, len(hashes), None


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Vocabulary-regrowth gate: fail on any new occurrence of the "
            "seven cleaned internal-development-system token families "
            "(AGT-nn, REC-n, OQ-n, bare T-nn, DEV-n, WP-n, plus the "
            "literals design-docs and subagent-report) in a tracked file or "
            "in a commit message the pull request adds."
        )
    )
    ap.add_argument("--root", default=".")
    ap.add_argument("--base-sha", default=None)
    ap.add_argument("--head-sha", default=None)
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.stderr.write("check_vocabulary_regrowth: root not found.\n")
        print(json.dumps({"error": "root-not-found"}))
        return 2

    if (args.base_sha is None) != (args.head_sha is None):
        sys.stderr.write(
            "check_vocabulary_regrowth: --base-sha and --head-sha must be "
            "given together (got exactly one) -- a half-specified range is "
            "not a range.\n"
        )
        print(json.dumps({"error": "half-specified-commit-range"}))
        return 2

    git_out, git_code = _run_git(["rev-parse", "--is-inside-work-tree"], args.root)
    if git_code != 0 or git_out.strip() != "true":
        sys.stderr.write(
            "check_vocabulary_regrowth: --root is not a git working tree "
            "(git not resolvable, or not a repository).\n"
        )
        print(json.dumps({"error": "not-a-git-worktree"}))
        return 2

    paths = tracked_files(args.root)
    if paths is None:
        sys.stderr.write("check_vocabulary_regrowth: `git ls-files` failed.\n")
        print(json.dumps({"error": "git-ls-files-failed"}))
        return 2

    findings, files_examined, files_skipped_binary = file_findings(args.root, paths)

    if files_examined == 0:
        sys.stderr.write(
            "check_vocabulary_regrowth: 0 tracked text files examined out of "
            "%d tracked path(s) -- a gate that scanned nothing has not "
            "passed. Refusing to report clean.\n" % len(paths)
        )
        print(json.dumps({"error": "zero-files-examined", "tracked_paths": len(paths)}))
        return 2

    commit_check = "skipped"
    commit_messages_examined = None
    if args.base_sha is not None:
        commit_findings, commit_count, commit_error = commit_message_findings(
            args.root, args.base_sha, args.head_sha
        )
        if commit_error is not None:
            sys.stderr.write(
                "check_vocabulary_regrowth: commit-range error -- %s\n" % commit_error
            )
            print(json.dumps({"error": commit_error}))
            return 2
        if commit_count == 0:
            sys.stderr.write(
                "check_vocabulary_regrowth: --base-sha/--head-sha were given "
                "but %s..%s resolved to 0 commits -- a requested commit-"
                "message check that examined nothing has not passed. "
                "Refusing to report clean.\n" % (args.base_sha, args.head_sha)
            )
            print(json.dumps({"error": "zero-commits-examined"}))
            return 2
        commit_check = "ran"
        commit_messages_examined = commit_count
        findings.extend(commit_findings)
    else:
        sys.stderr.write(
            "check_vocabulary_regrowth: commit-message check SKIPPED -- no "
            "--base-sha/--head-sha given (not a pull_request run, or a "
            "local invocation with no range available). This is a loud "
            "skip, not a silent pass: the file-scan half below still ran "
            "and still gates.\n"
        )

    findings.sort(
        key=lambda f: (
            f["kind"],
            f.get("file") or f.get("commit") or "",
            f.get("line", 0),
            f["pattern"],
            f["token"],
        )
    )

    scanned = {
        "files_examined": files_examined,
        "files_skipped_binary": files_skipped_binary,
        "tracked_paths": len(paths),
        "commit_message_check": commit_check,
        "commit_messages_examined": commit_messages_examined,
    }

    print(
        json.dumps({"findings": findings, "scanned": scanned}, indent=2, sort_keys=True)
    )

    sys.stderr.write(
        "check_vocabulary_regrowth: examined %d tracked text file(s) (%d "
        "binary skipped, %d tracked path(s) total); commit-message check: "
        "%s"
        % (
            files_examined,
            files_skipped_binary,
            len(paths),
            commit_check,
        )
    )
    if commit_messages_examined is not None:
        sys.stderr.write(" (%d commit message(s) examined)" % commit_messages_examined)
    sys.stderr.write(".\n")

    if not findings:
        sys.stderr.write("check_vocabulary_regrowth: clean.\n")
        return 0

    by_pattern = {}
    for f in findings:
        by_pattern[f["pattern"]] = by_pattern.get(f["pattern"], 0) + 1
    sys.stderr.write(
        "check_vocabulary_regrowth: %d finding(s) -- %s\n"
        % (len(findings), ", ".join("%s=%d" % kv for kv in sorted(by_pattern.items())))
    )
    for f in findings:
        if f["kind"] == "file":
            sys.stderr.write(
                "  FILE    pattern=%s file=%s:%d token=%r\n"
                % (f["pattern"], f["file"], f["line"], f["token"])
            )
        else:
            sys.stderr.write(
                "  COMMIT  pattern=%s commit=%s subject=%r token=%r\n"
                % (f["pattern"], f["commit"], f["subject"], f["token"])
            )

    return 1


if __name__ == "__main__":
    sys.exit(main())
