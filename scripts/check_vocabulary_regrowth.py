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
# OWNER: the delivery and DevOps role (the script-test default for this
#   repository's own scripts; see the architecture decision on the script test
#   root).
# ENTRYPOINT: python scripts/check_vocabulary_regrowth.py [--root .]
#             [--base-sha SHA --head-sha SHA]
#             python scripts/check_vocabulary_regrowth.py [--root .]
#             --paths PATH [PATH ...] [--vendor-names]
#             (the second form is the SCOPED SCAN, described in the section of
#             that name below; the two forms never combine.)
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
#   --paths     (CLI arg, optional, one or more): switches to the SCOPED SCAN.
#               Each argument is a file or a directory, relative to --root (an
#               absolute path inside --root is accepted). See SCOPED SCAN.
#   --vendor-names (CLI flag, only with --paths): also report the bare assistant-
#               vendor names. Off by default, for the reason given in SCOPED
#               SCAN.
# OUTPUTS:
#   stdout: JSON {"findings":[{"kind":"file"|"commit-message", "pattern",
#            "file"|"commit", "line"|"subject", "token"}], "scanned":
#            {"files_examined":N, "files_skipped_binary":N,
#             "commit_messages_examined":N|null,
#             "commit_message_check":"ran"|"skipped"}}.
#            The scoped scan prints the same two top-level keys plus "mode":
#            "paths", and its "scanned" object is given under SCOPED SCAN.
#   stderr: human summary, including the denominator every run and, when the
#            commit-message half is skipped, the loud, named reason. Exit
#            code per EXIT CODES.
# EXIT CODES: 0 clean (both denominators healthy, no findings) -> COMPLETED ;
#   1 finding(s) -> FAILED ; 2 usage/environment error (root not found, git
#   not resolvable, a half-specified commit range, a resolved commit range
#   with zero commits in it, or zero tracked text files examined; for the
#   scoped scan also a path that does not exist, lies outside --root or yields
#   no scanned file, and --paths combined with a commit range) -> BLOCKED.
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
#     recorded inline). FIVE entries, in two groups:
#
#     (i) the boundary modules -- `memory/product_boundary.py`,
#     `testing/product_boundary.py`, and their 4.0.0 successors
#     `memory/repo_guard.py` and `testing/repo_guard.py`. Each tests for a
#     `design-docs/` directory on disk to distinguish a container repository
#     from a product repository; that is a functional path check, not an
#     unresolvable reference to this development system, and a gate that
#     failed on it is a gate nobody could keep green.
#
#     (ii) `testing/cleanup.py`, which names the container's own scratch
#     locations in its temp-root precedence chain
#     (`design-docs/state/testing-local.json`, then
#     `design-docs/state/tmp/testing/`).
#
#     COUNT, AND WHY IT MOVED. Measured 2026-09-06 the boundary modules held
#     the ONLY three occurrences in the whole tree. Measured 2026-09-11,
#     after the framework furniture was updated to orchestrator-design 4.0.1,
#     there are 41: the two `repo_guard.py` modules carry 16 each and the
#     refreshed `cleanup.py` carries 9. That is not regrowth. All three are
#     byte-frozen copies of originals maintained outside this repository and
#     verified by a fidelity check that compares CONTENT -- editing the copy
#     to satisfy this gate would break that check and fork the file. The
#     change has to start upstream, which is exactly what the
#     internal-vocabulary delivery record already says about this class.
#
#     This is the narrowly-scoped, reasoned entry the SELF-TRIPPING
#     RESOLUTION note below prescribes for a literal that cannot be avoided
#     -- NOT a widening. Every one of the five is a single (path, pattern)
#     pair; no file is exempted from any other pattern, and a planted
#     `AGT-05` in any of them would still fail this gate.
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
# SCOPED SCAN (`--paths`) -- a second question, asked of named files:
#   The default mode answers "did this pull request ADD any of the eight
#   patterns", over the tracked tree at HEAD and the pull request's commit
#   messages. The scoped scan answers a different one -- "do THESE files carry
#   any of them AT ALL" -- for the shipped translations (REQ-L10N-DATA-005),
#   whose catalogues and guide trees must hold none, not merely none added.
#   Differences, all deliberate:
#   - EVERY OCCURRENCE is reported, on every line of every file, never only an
#     introduced one. There is no base to compare against.
#   - WHICH FILES: for each argument, the files git itself reports for that
#     path -- tracked, or untracked and not ignored (`git ls-files --cached
#     --others --exclude-standard`) -- so a batch just written and not yet
#     committed IS scanned and ignored scratch is not. WHICH CONTENT: the
#     working-tree bytes on disk, not HEAD, for the same reason. The default
#     mode reads HEAD because it asks what a pull request adds; this one asks
#     what is in the files now.
#   - THE FAMILIES: the eight patterns above, with the same EXCLUDE and
#     ALLOWLIST rules (a named path is not a back door around them), plus the
#     AI-ATTRIBUTION family below. The default mode does not run the
#     attribution family, and its commit-message half is untouched.
#   - THE DENOMINATOR is printed and gated: the number of files scanned goes
#     to stdout (scanned.files_examined and, per argument,
#     scanned.per_path) and to stderr, and a run that scanned nothing -- or an
#     argument that contributed nothing, so a mistyped directory cannot hide
#     behind a healthy total -- exits 2 and never 0. Binary files, excluded
#     files and unreadable files are counted and printed, not folded in.
#   - Combining --paths with --base-sha/--head-sha is exit 2: a scoped scan has
#     no commit range, and silently ignoring one would pass commit messages
#     nobody examined.
#
#   THE ATTRIBUTION FAMILY (ATTRIBUTION_PATTERNS below), and why it is SHAPED
#   rather than a list of bare names. Constitution Article IX section 4 forbids an AI
#   or vendor attribution in file headers and repository metadata. The product
#   also SHIPS an assistant feature with a native adapter for one vendor, so
#   that vendor's name and its model family's name are legitimate shipped text
#   -- a provider label in the catalogues, a sentence in the assistant page of
#   the user guide, keywords in the guide manifest. Measured 2026-10-24 on the
#   feature branch tree: with the bare-name tier on, 181 hits in 45 files, among
#   them the provider label in every catalogue and the assistant page of the
#   English and Spanish guides. Each translation of that label and of that page
#   MUST therefore contain the names, and a bare-name rule would hold the
#   shipped translations red for ever -- the "impossible gate" that teaches its
#   reader to work with the red light on.
#   The sibling commit-message gate (scripts/check_attribution.py) reached the
#   same conclusion for the same reason and anchors every pattern to a SHAPE; so
#   does this family. It reports, case-insensitively:
#     attribution:co-authored-by  a trailer-style `Co-Authored-By:` naming a
#                                 vendor, anywhere in a line
#     attribution:generated-by    `generated / written / translated / ... with
#                                 / by / using / via` followed by a vendor, an
#                                 "AI", an "LLM", a "language model" or a
#                                 "chatbot"
#     attribution:ai-adjective    "AI-generated", "LLM written", ... (the
#                                 adjective form)
#     attribution:author-field    an `author` / `translator` / `reviewer` /
#                                 `created by` ... key (`:` or `=`, quoted or
#                                 not) whose value names a vendor -- the shape
#                                 of a catalogue header or of metadata
#     attribution:vendor-email    an e-mail address at a vendor domain, or with
#                                 a vendor name as its local part
#     attribution:vendor-url      a link into a vendor's chat or session
#                                 surface (NOT its API host: the default
#                                 endpoint of the shipped adapter is a
#                                 legitimate string)
#     attribution:assistant-tool  the vendor's coding tool, named in the form
#                                 "<vendor> Code"
#   `--vendor-names` adds attribution:vendor-name (the bare name of the vendor
#   and of its model family). It exists to MEASURE and to scan a tree that must
#   not name them at all; it is off by default because the shipped text above
#   names them on purpose. Turning it on over the product tree reports those
#   shipped mentions -- listed, never excluded.
#   Every pattern is assembled from parts (see VENDOR_NAMES): no line of this
#   source is a working trailer, e-mail address or link.
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
#   this gate red (the scoped scan lists files through git as well and reads
#   them from disk); refuses (exit 2) on a zero denominator in either
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
_FROZEN_COPY_REASON = (
    "byte-frozen copy of an original maintained outside this repository; it "
    "names the container's own scratch locations in its temp-root precedence "
    "chain. Editing the copy would break the content-comparing fidelity "
    "check, so this change has to start upstream"
)
ALLOWLIST_HITS = {
    ("memory/product_boundary.py", "design-docs"): _DESIGN_DOCS_REASON,
    ("testing/product_boundary.py", "design-docs"): _DESIGN_DOCS_REASON,
    # The 4.0.0 successors of the two above, vendored 2026-09-11. Same
    # module, same functional path check, same reason.
    ("memory/repo_guard.py", "design-docs"): _DESIGN_DOCS_REASON,
    ("testing/repo_guard.py", "design-docs"): _DESIGN_DOCS_REASON,
    ("testing/cleanup.py", "design-docs"): _FROZEN_COPY_REASON,
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

# ---------------------------------------------------------------------------
# The AI-attribution family -- scoped scan only (module docstring, SCOPED SCAN).
# ASSEMBLED FROM PARTS, ON PURPOSE: no line below is a working trailer, e-mail
# address or link, so this source can be neither pasted into a commit message
# as one nor found by a search for the leak.
# ---------------------------------------------------------------------------
VENDOR_NAMES = (
    "claud" + "e",
    "anthropi" + "c",
    "copilot",
    "chat" + "gpt",
    "gpt",
    "gemini",
    "codex",
    "open" + "ai",
)
# Chat / session surfaces only. The vendor's API host is ABSENT on purpose: the
# shipped adapter's default endpoint is a legitimate string.
VENDOR_SESSION_HOSTS = (
    "claud" + "e[.]ai",
    "claud" + "e[.]com",
    "chat[.]open" + "ai[.]com",
    "copilot[.]microsoft[.]com",
    "gemini[.]google[.]com",
)
# The bare names of the vendor and of its model family: the opt-in tier.
BARE_VENDOR_NAMES = ("claud" + "e", "anthropi" + "c")

_ALNUM = "A-Za-z0-9"
_NAME_ALT = "|".join(VENDOR_NAMES)
# A vendor name as a WORD: `gpt` never fires inside `gptools`.
_VENDOR = "(?<![%s])(?:%s)(?![%s])" % (_ALNUM, _NAME_ALT, _ALNUM)
# What a "generated by ..." sentence may be generated by: a vendor, or an
# AI-ish noun. `ai` needs its own boundary so it cannot start a longer word.
_AI_NOUN = (
    r"(?:%s|ai(?![%s])|a[.]i[.]|llm(?![%s])|(?:large[ \t]+)?language[ \t]+model"
    r"|chatbot)" % (_VENDOR, _ALNUM, _ALNUM)
)
_VERBS = (
    "generated|written|translated|authored|drafted|produced|composed|created|"
    "reviewed|edited|assisted"
)
# The adjective form says what a text IS ("AI-generated"), so it takes fewer
# verbs: "AI-assisted perspective inference" is a shipped feature description,
# not an attribution (measured in the English user guide).
_ADJ_VERBS = "generated|written|translated|authored|drafted|produced"
_KEYS = (
    "author(?:s)?|last[-_ ]translator|translator|translated[-_ ]by|reviewer|"
    "reviewed[-_ ]by|contributor|creator|created[-_ ]by|written[-_ ]by|"
    "maintainer|signed[-_ ]off[-_ ]by"
)
_HOST_ALT = "|".join(VENDOR_SESSION_HOSTS)
_MAIL_HOSTS = "|".join(("anthropi" + "c[.]com", "open" + "ai[.]com", _HOST_ALT))

ATTRIBUTION_PATTERNS = {
    "attribution:co-authored-by": re.compile(
        r"co[-_ ]?authored[-_ ]?by[ \t]*[:=][^\n]*?" + _VENDOR, re.IGNORECASE
    ),
    "attribution:generated-by": re.compile(
        r"(?<![%s])(?:%s)[ \t]+(?:with|by|using|via)[ \t]+[\[(*_]*"
        r"(?:an?[ \t]+|the[ \t]+)?%s" % (_ALNUM, _VERBS, _AI_NOUN),
        re.IGNORECASE,
    ),
    "attribution:ai-adjective": re.compile(
        r"(?<![%s])(?:ai|llm|gpt|chatbot)[-_ \t]?(?:%s)(?![%s])"
        % (_ALNUM, _ADJ_VERBS, _ALNUM),
        re.IGNORECASE,
    ),
    # The key must not trail a hyphen or underscore: that is how the product's
    # own service name ends in a key word, followed by a provider id.
    "attribution:author-field": re.compile(
        r"(?<![%s_-])(?:%s)[\"']?[ \t]*[:=][ \t]*[\"']?[^\n]{0,60}?%s"
        % (_ALNUM, _KEYS, _VENDOR),
        re.IGNORECASE,
    ),
    "attribution:vendor-email": re.compile(
        r"[%s._%%+-]+@(?:%s)\b|(?<![%s._%%+-])(?:%s)@[%s.-]+"
        % (_ALNUM, _MAIL_HOSTS, _ALNUM, _NAME_ALT, _ALNUM),
        re.IGNORECASE,
    ),
    "attribution:vendor-url": re.compile(
        r"https?://(?:[%s.-]+[.])?(?:%s)\b[^\s<>\"')\]]*" % (_ALNUM, _HOST_ALT),
        re.IGNORECASE,
    ),
    "attribution:assistant-tool": re.compile(
        r"(?<![%s])(?:%s)[-_ \t]?code(?![%s])" % (_ALNUM, "claud" + "e", _ALNUM),
        re.IGNORECASE,
    ),
}
# The opt-in tier (`--vendor-names`): the bare names, as words.
BARE_VENDOR_PATTERN = (
    "attribution:vendor-name",
    re.compile(
        r"(?<![%s])(?:%s)(?![%s])" % (_ALNUM, "|".join(BARE_VENDOR_NAMES), _ALNUM),
        re.IGNORECASE,
    ),
)
MAX_QUOTE = 120


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


def _split_lines(text):
    """Split `text` into lines on CRLF, LF and lone CR only.

    Line numbers then agree with an editor's: `str.splitlines` also splits on
    form feeds and Unicode separators, which would drift them in a translated
    catalogue.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _quote(token):
    """Bound a matched token for the report, and say so when it was cut."""
    if len(token) <= MAX_QUOTE:
        return token
    return token[:MAX_QUOTE] + " ...[truncated]"


def scoped_text_findings(rel, text, vendor_names):
    """Return every occurrence, on every line, of the scoped scan's patterns.

    The eight patterns (minus this path's allowlisted pairs) and the
    attribution family; `vendor_names` adds the opt-in bare-name pattern.
    """
    families = list(PATTERNS.items()) + list(ATTRIBUTION_PATTERNS.items())
    if vendor_names:
        families.append(BARE_VENDOR_PATTERN)
    findings = []
    for lineno, line in enumerate(_split_lines(text), start=1):
        for name, pattern in families:
            if (rel, name) in ALLOWLIST_HITS:
                continue  # suppressed -- see ALLOWLIST_HITS reason
            for m in pattern.finditer(line):
                findings.append(
                    {
                        "kind": "file",
                        "pattern": name,
                        "file": rel,
                        "line": lineno,
                        "token": _quote(m.group(0)),
                    }
                )
    return findings


def resolve_scoped_paths(root, given):
    """Resolve each `--paths` argument to the files git reports for it.

    Returns (resolved, error): `resolved` is a list of (argument, [repo-relative
    '/'-separated file paths]) in argument order, `error` a (code, message)
    pair for an argument that does not exist or lies outside `root`. The file
    list is git's own -- tracked, or untracked and not ignored -- never a
    filesystem walk, so ignored scratch is not scanned.
    """
    root_abs = os.path.abspath(root)
    resolved = []
    for arg in given:
        full = os.path.abspath(os.path.join(root_abs, arg))
        try:
            rel = os.path.relpath(full, root_abs).replace(os.sep, "/")
        except ValueError:  # another drive: certainly outside the root
            rel = ".."
        if rel == ".." or rel.startswith("../"):
            return None, ("path-outside-root", "path %r lies outside --root" % arg)
        if not os.path.exists(full):
            return None, ("path-not-found", "path %r does not exist" % arg)
        spec = "." if rel == "." else ":(literal)" + rel
        out, code = _run_git(
            [
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                spec,
            ],
            root,
        )
        if code != 0:
            return None, ("git-ls-files-failed", "`git ls-files` failed for %r" % arg)
        resolved.append((arg, sorted(p for p in out.split("\x00") if p)))
    return resolved, None


def scoped_scan(root, resolved, vendor_names):
    """Scan the resolved files' working-tree bytes.

    Returns (findings, counts, per_path): `counts` holds the denominator
    pieces, `per_path` maps each argument to the number of files it got
    scanned. A file reached through two arguments is scanned once.
    """
    findings = []
    seen = {}  # rel -> "examined" | "binary" | "excluded" | "unreadable"
    per_path = {}
    for arg, files in resolved:
        examined_here = 0
        for rel in files:
            if rel not in seen:
                if excluded(rel):
                    seen[rel] = "excluded"
                else:
                    try:
                        with open(os.path.join(root, rel), "rb") as handle:
                            data = handle.read()
                    except OSError:
                        # e.g. tracked in the index but deleted from disk
                        seen[rel] = "unreadable"
                        continue
                    if b"\x00" in data:
                        seen[rel] = "binary"
                    else:
                        seen[rel] = "examined"
                        text = data.decode("utf-8", errors="replace")
                        findings.extend(scoped_text_findings(rel, text, vendor_names))
            if seen[rel] == "examined":
                examined_here += 1
        per_path[arg] = examined_here
    counts = {
        "files_examined": sum(1 for v in seen.values() if v == "examined"),
        "files_skipped_binary": sum(1 for v in seen.values() if v == "binary"),
        "files_excluded": sum(1 for v in seen.values() if v == "excluded"),
        "files_unreadable": sum(1 for v in seen.values() if v == "unreadable"),
    }
    return findings, counts, per_path


def scoped_main(args):
    """Run the `--paths` mode and return its exit code.

    Reports every occurrence in the named files and prints the number of
    files scanned. Exit 0 / 1 / 2 as the module header states; a scan that
    examined nothing is 2, never 0.
    """
    resolved, error = resolve_scoped_paths(args.root, args.paths)
    if error is not None:
        code, message = error
        sys.stderr.write("check_vocabulary_regrowth: %s.\n" % message)
        print(json.dumps({"error": code, "mode": "paths"}))
        return 2

    findings, counts, per_path = scoped_scan(args.root, resolved, args.vendor_names)

    empty = [arg for arg, n in per_path.items() if n == 0]
    if counts["files_examined"] == 0 or empty:
        sys.stderr.write(
            "check_vocabulary_regrowth: scoped scan examined 0 text file(s) "
            "for %s (%d binary, %d excluded, %d unreadable skipped overall) -- "
            "a scan that examined nothing has not passed. Refusing to report "
            "clean.\n"
            % (
                ", ".join(ascii(a) for a in empty) or "every path",
                counts["files_skipped_binary"],
                counts["files_excluded"],
                counts["files_unreadable"],
            )
        )
        print(
            json.dumps(
                {
                    "error": "zero-files-examined",
                    "mode": "paths",
                    "scanned": dict(counts, per_path=per_path),
                },
                sort_keys=True,
            )
        )
        return 2

    findings.sort(key=lambda f: (f["file"], f["line"], f["pattern"], f["token"]))
    scanned = dict(counts, per_path=per_path, vendor_names=args.vendor_names)
    print(
        json.dumps(
            {"findings": findings, "mode": "paths", "scanned": scanned},
            indent=2,
            sort_keys=True,
        )
    )
    sys.stderr.write(
        "check_vocabulary_regrowth: scoped scan of %d path(s): scanned %d "
        "text file(s) (%d binary, %d excluded, %d unreadable skipped).\n"
        % (
            len(per_path),
            counts["files_examined"],
            counts["files_skipped_binary"],
            counts["files_excluded"],
            counts["files_unreadable"],
        )
    )
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
        sys.stderr.write(
            "  FILE    pattern=%s file=%s:%d token=%s\n"
            % (f["pattern"], ascii(f["file"]), f["line"], ascii(f["token"]))
        )
    return 1


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
    ap.add_argument(
        "--paths",
        nargs="+",
        default=None,
        metavar="PATH",
        help=(
            "scoped scan: report EVERY occurrence of the eight patterns and of "
            "the AI-attribution family in these files or directories (relative "
            "to --root) and print the number of files scanned; exits 2 when "
            "nothing was scanned. Cannot be combined with --base-sha/--head-sha."
        ),
    )
    ap.add_argument(
        "--vendor-names",
        action="store_true",
        help=(
            "with --paths: also report the bare assistant-vendor names "
            "(off by default; the product ships them on purpose)."
        ),
    )
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        sys.stderr.write("check_vocabulary_regrowth: root not found.\n")
        print(json.dumps({"error": "root-not-found"}))
        return 2

    if args.paths is None and args.vendor_names:
        sys.stderr.write(
            "check_vocabulary_regrowth: --vendor-names only applies to the "
            "scoped scan (--paths).\n"
        )
        print(json.dumps({"error": "vendor-names-without-paths"}))
        return 2

    if args.paths is not None and (
        args.base_sha is not None or args.head_sha is not None
    ):
        sys.stderr.write(
            "check_vocabulary_regrowth: --paths cannot be combined with "
            "--base-sha/--head-sha -- the scoped scan has no commit range, and "
            "ignoring one would pass commit messages nobody examined.\n"
        )
        print(json.dumps({"error": "paths-with-commit-range", "mode": "paths"}))
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

    if args.paths is not None:
        return scoped_main(args)

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
