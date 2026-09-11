#!/usr/bin/env python3
"""check_attribution.py — VCS attribution gate over commit messages
and identities (P11).

`docs/constitution-articles.md` Article IX §4 declares
one HARD INVARIANT: no AI / vendor authorship anywhere in a repository or its
history — not in author or committer fields, not in commit-message trailers, not
in tag messages, PR bodies, file headers or repository metadata. Article IX §4
calls such a trailer "a **gate failure**, not a style preference".

Until this file existed that sentence was not true of anything that runs.
MEASURED 2026-09-11: no hook and no script in either repository read a commit
message for one, and five commits in the sibling development repository landed
carrying a tool's default trailer pair (2026-08-29 x2, 2026-09-09 x3) and went
unnoticed
for two weeks. The repair cost a history rewrite of 60 commits. This script is
the control that stops the recurrence; `.githooks/commit-msg` is its wiring.

WHAT IS SCANNED, AND WHY NOTHING ELSE IS
    Commit MESSAGES and commit IDENTITIES. Never file contents. This is a
    deliberate scope boundary, not an omission, and the reason is measurable:
    the PRODUCT repository legitimately ships an Anthropic LLM adapter — about
    thirty files, among them `pixelart_creator/data/llm/anthropic_translator.py`,
    the provider dialogs, both user guides, the i18n catalogues, and tests that
    name `claude-3-5-sonnet` on purpose. A gate that matched bare vendor names
    in file contents would flag a SHIPPED FEATURE on every commit, and the only
    way to keep it usable would be an allowlist so long that it could no longer
    see a real leak — the §3.2 "impossible gate" that teaches its reader to work
    with the red light on. The prohibited trailer has exactly one way in: a
    commit message. So the message, and the identity attached to it, is the
    whole surface. Scanning files would also make this file flag itself, and a
    gate that cannot survive its own scan is not a gate.

    Out of scope BY DESIGN, and named so the absence reads as decided rather
    than forgotten: tag messages, PR/issue bodies, file headers and repository
    metadata. Article IX §4 forbids the trailer there too; this vehicle does not
    reach them. The PR and tag surfaces are owned elsewhere.

TWO MODES, BOTH EXPLICIT — there is no implicit default that guesses which
question it was asked, because the two modes have different denominators and a
mode chosen by inference is a count reported against the wrong one:
    --message-file PATH        one prospective commit message. The hook's use.
    --base-sha S --head-sha S  every commit in `base..head`: subject AND body,
                               plus each commit's author and committer
                               name/email. The CI / pull-request use. The two
                               flags are one argument in two halves: half a
                               range is a usage error (exit 2), never an
                               assumed endpoint.
Exactly one mode per run. Neither, or both, is exit 2.

OUTPUT: ALWAYS JSON on stdout — there is no `--json` flag, deliberately. A flag
    that selects the machine-readable form is a flag a caller forgets, and then
    the caller parses the human text. Human-readable diagnostics go to stderr,
    always, on every path including the clean one, so `git commit` shows a
    reader the verdict without anyone piping stdout anywhere.

GATE CLASS: Class A blocking-for-harm (the gate doctrine §1.1 / §1.5).
    A control that fires DURING work — it runs inside `commit-msg`, before the
    commit object exists — and it BLOCKS. The harm question is answered yes, and
    not by analogy: the harm is ABSORBED FOREIGN CHANGES in §1.1's fourth class,
    an attribution the user never wrote entering a history that is theirs, plus
    the LOST WORK of the repair. It is measured, not hypothetical: five commits
    got in, and getting them out took a rewrite of 60 commits — on a public
    product repository that is a force-push, which invalidates every clone and
    every open branch built on it. A warn-and-continue control here would have
    printed five warnings nobody read.
    The blocking budget §1.1 calls finite is not overspent, because the block
    costs almost nothing to clear: nothing is committed, the message file is
    still on disk, and the fix is deleting a line. There are two deliberate
    NON-blocks for the same reason: a trailer ALREADY IN HISTORY is reported by
    range mode and blocks nothing this gate can undo (rewriting history is a
    human decision, never a hook's), and a commit whose message is clean but
    whose identity is wrong is out of message mode's surface — recorded below as
    a named shortfall rather than closed by guessing.
    §1.3 DEVIATION, DELIBERATE AND RECORDED. §1.3 says a framework-caused red
    must not block the user. This gate blocks on its own unrunnability anyway
    (exit 2, verdict BLOCKED), and the trade is stated rather than glossed:
    passing an UNSCANNED message costs a history rewrite, while blocking one
    costs a re-run, and §1.3's "the work proceeds" is still available to the
    human in the one form that is visible in the reflog — `git commit
    --no-verify`, which the red names. An automatic bypass would make the gate
    exactly as real as the sentence it replaced.

NAMED EXIT: every red names WHAT FAILED WITH THE VALUE, WHAT FIXES IT, and THE
    SAFE ALTERNATIVE — and all three travel in the payload as well as on stderr,
    so a machine reader gets the same exit a human does (`remedy` and
    `safe_alternative` are fields, not prose this file merely promises).
    exit 1, verdict VIOLATIONS
      WHAT FAILED, WITH THE VALUE — one `violations` entry per hit, carrying the
        pattern name that fired (`co_authored_vendor`, `vendor_session_trailer`,
        `generated_with_vendor`, `vendor_email`, `vendor_assistant_url`,
        `vendor_identity_name`, `vendor_identity_email`), WHERE it was found
        (`message-file` + line number, or the commit sha + `message` / `author` /
        `committer`), the matched token, and the offending line quoted verbatim
        and truncated to 120 characters. The quote is the value that failed it.
      WHAT FIXES IT — `remedy`: delete the offending line or field from the
        message and commit again. For an identity hit the fix is the identity,
        not the message: `git -c user.name=... -c user.email=...` or
        `git commit --amend --reset-author` after correcting the configured
        identity. Article IX §4 holds the one identity this repository commits
        under; this gate deliberately does not (see REJECT BY PROHIBITION).
      THE SAFE ALTERNATIVE — concrete, and it is the reason this red is cheap:
        THE COMMIT IS NOT LOST. `commit-msg` runs after the message is written,
        so the message file is still on disk with everything typed into it;
        `git commit --edit` reopens it, or re-running the commit with the
        trailer deleted proceeds. Nothing was staged, unstaged or rewritten by
        this script — it performs no git write of any kind, and in range mode
        every git call is read-only and `--no-optional-locks`.
    exit 2, verdict BLOCKED
      WHAT FAILED, WITH THE VALUE — `error` names the invocation or the input
        that did not resolve, quoting it: "no mode given", "both modes given",
        "--base-sha given without --head-sha", "message file does not exist:
        <path>", "does not resolve to a commit: <the sha as typed>", "the range
        <base>..<head> resolved to 0 commits", "the message file contains no
        scannable line". It reports the caller's invocation or an unreadable
        input, never that the message is bad — the §1.3 distinction this gate
        keeps even where it deviates from §1.3's behaviour.
      WHAT FIXES IT — `remedy` states the complete invocation for the mode that
        was half-given, or the input to repair. A zero-commit range is fixed by
        widening the range, not by reading the zero as clean.
      THE SAFE ALTERNATIVE — the same one, and it is total: nothing was written,
        the message file is untouched, `git commit --edit` reopens it, and
        `git commit --no-verify` proceeds visibly if the gate itself is broken.
        Range mode has no alternative to name beyond re-running with a range
        that resolves, because it changes nothing to begin with.

    FAIL ON ZERO, AND STATE THE DENOMINATOR. This project has a recorded
    lesson — five gates once passed while structurally unable to answer their
    own question. So `counts` carries `messages_examined`, `commits_examined`,
    `identities_examined`, `lines_scanned` and `lines_excluded` on every path,
    and examining nothing is BLOCKED, never CLEAN. Each mode declares its own
    denominator: message mode is BLOCKED at `messages_examined == 0` or
    `lines_scanned == 0`; range mode is BLOCKED at `commits_examined == 0` or
    `identities_examined == 0`. Message mode reports `identities_examined: 0`
    and is NOT blocked by it — the identity is not in the file, which is stated
    in the payload's `not_examined` field rather than left to be read as a zero
    that passed.
    NEVER RETURN SILENTLY. A silent return IS the defect (recorded directive):
    the verdict is printed on stdout AND stderr on every path, clean included.

REJECT BY PROHIBITION, NEVER BY IDENTITY WHITELIST. This gate holds a list of
    FORBIDDEN shapes and matches it against whatever identity is present. It
    does not hold the owner's name or email as a required identity, for two
    reasons worth keeping attached to the decision: an allowlist of one human
    breaks the moment a second legitimate contributor appears — and it fails
    CLOSED, rejecting a real person's commit — and it would embed a private
    email address into a new tracked file to buy nothing. Note the consequence,
    since it is where the two rules differ: `noreply@` on GITHUB is NOT a vendor
    host here, because this repository's own commit identity is a
    `users.noreply.github.com` address. A GitHub noreply is caught by its LOCAL
    PART (`copilot@users.noreply.github.com` is a hit) and never by its domain.

PATTERNS ARE NARROW AND TRAILER-SHAPED, NOT BARE VENDOR NAMES. Every pattern is
    case-insensitive, and every one is anchored to a shape — a trailer key at
    the start of a line, an e-mail token, a "generated with" opener — so a
    message that DISCUSSES the rule is not a hit. "fix: strip the co-author
    trailer from the history" has no trailer key at line start and no vendor
    e-mail, and passes. TWO residual behaviours are deliberate, recorded here so
    neither reads as a bug: a line that BEGINS with a forbidden trailer key and
    names a vendor is a hit even when it was meant as a quotation, because git
    itself would read that line as a trailer if it sat in the trailer block and
    a later scan of the history cannot tell a quotation from the real thing; and
    that is not a hypothetical — the cleanup commit that removed these trailers
    on 2026-09-11 quoted one verbatim to explain what it removed, and re-seeded
    the exact token any future scan looks for.

    NO FORBIDDEN LITERAL IS REPRODUCED IN THIS FILE AS A COPYABLE TRAILER LINE,
    AND THAT IS ON PURPOSE — DO NOT "TIDY" IT. Every pattern below is assembled
    from parts or written with character classes (`co[-_ ]?authored[-_ ]?by`,
    `anthropi[c][.]com`) so that no line of this source can be pasted into a
    commit message and work as a trailer. A later reader who folds the classes
    back into plain text will have put the forbidden token into a tracked file,
    where the next `--base-sha` run over a commit that touches this file cannot
    see it (this gate reads messages, not files) and where a grep for the leak
    will find it forever.

PLATFORM CONSTRAINTS: Windows-first development environment; the portable
    form of each trap is catalogued in the project's Windows-compatibility
    notes.
    Bytes on disk and line endings (§10, §11). The message file is read in
        BINARY — `open(path, "rb")` — and decoded explicitly as UTF-8 with
        `errors="replace"`. Never `read_text()`: on Windows the text-mode round
        trip rewrites every `\n` as `\r\n`, and this repository pins `* -text` in
        `.gitattributes` because copy fidelity is compared BYTE for byte. This
        script never writes the message file at all, so the round trip cannot
        happen here — reading in binary is what keeps a CRLF message from
        reporting a phantom `\r` inside every matched value.
    Line endings, second face (§11). The decoded text is split with
        `str.splitlines()`, which treats CRLF, LF and CR alike, so a message
        written by a Windows editor and one written by a hook produce the same
        line numbers. A `split("\n")` here would leave a trailing `\r` on every
        line and put it inside each quoted value.
    Console encoding (§6). `sys.stdout` / `sys.stderr` are reconfigured to UTF-8
        with `errors="replace"` in the prologue, before anything is written,
        because the human diagnostics quote message text verbatim and a commit
        message is routinely outside cp1252. Without the prologue a legitimate
        em-dash in a commit subject turns this gate into a UnicodeEncodeError
        inside a git hook — a crash where a verdict belongs. JSON is emitted
        with `ensure_ascii=False` for the same reason, which is safe only
        BECAUSE of the prologue: the two travel together and neither is
        correct alone.
    Subprocess (§3). Range mode shells out to `git` with a list argv, never
        `shell=True`, never a `.cmd` shim, never a name resolved through a shell
        — `git` on Windows is `git.exe` and needs no `cmd.exe /c` wrapper, which
        is exactly why nothing here builds one. Every call carries
        `--no-optional-locks` (so a concurrent index lock cannot turn a
        read-only scan into a write attempt) and a 60-second timeout, and its
        output is decoded UTF-8 `errors="replace"`, so a commit message with an
        undecodable byte yields a verdict instead of a traceback.
    Paths (§5). Paths arrive from the caller's flags and are used as given,
        through `pathlib`. No identity comparison is made between two
        independently supplied paths, so the 8.3-alias trap has no surface here.
        Recorded so the absence reads as checked rather than overlooked.

RECORDED SHORTFALLS — stated rather than claimed closed (the gate doctrine
    §1.4: a half-built capability that reports a success it does not have is the
    failure; a named one is debt):
    1. MESSAGE MODE DOES NOT SEE THE IDENTITY. The prospective author and
       committer are not in the message file, so a commit made under an AI
       identity with a clean message passes `commit-msg`. The gate is closed
       downstream by range mode, which examines both fields of every commit in
       a pull-request range, and the hole is one `git var GIT_AUTHOR_IDENT` call
       wide — deliberately not made here, so message mode stays a pure function
       of the file it is handed and remains runnable outside a repository.
    2. TAG MESSAGES, PR BODIES, FILE HEADERS AND REPO METADATA are forbidden by
       Article IX §4 and are not reached by either mode (see WHAT IS SCANNED).
    3. RANGE MODE IS AFTER THE FACT. By the time it reports, the commits exist.
       It is a delivery gate on a branch, not a block on a write, and the repair
       it names — a history rewrite — is a human decision this vehicle never
       takes.
    Neither shortfall is a red that omits its exit: both exits above name all
    three parts of §1.2, so this file adds no fourth declared shortfall to the
    three already carried in `scripts/`.

Usage:
    python scripts/check_attribution.py --message-file <path>
    python scripts/check_attribution.py --base-sha <sha> --head-sha <sha>
                                        [--repo <path>]

Exit codes: 0 = CLEAN, 1 = VIOLATIONS, 2 = BLOCKED (usage / unresolvable input /
nothing examined). Stdlib only, Python 3.8+. Explicit UTF-8 on every read.

PRINCIPLES APPLIED
    P1  Source-of-Truth Grounding — the prohibition, its four surfaces and the
        "gate failure, not a style preference" wording are quoted from
        Article IX §4 of this repository's constitution; the measured recurrence
        (five commits, two weeks, 60-commit rewrite) is this repository's own
        record, not an estimate.
    P4  Consistency — CONVENTIONS as established by this repository's sibling scripts:
        repository-relative `scripts/<name>.py` citation, JSON on stdout, human
        text on stderr, `check_*` verdict vocabulary.
    P6  Self-Containment — stdlib only, no sibling import, no config file. It
        runs from a hook in a clone with nothing above it.
    P7  Reference Hygiene — the harm classes, the named-exit invariant and the
        two control classes are cited to the gate doctrine, never
        restated as this file's own doctrine; the platform traps are cited to
        the project's Windows-compatibility notes.
    P11 Programmatic Determinism — "is this trailer present" is a decidable
        question about text, so it is a script and not an instruction to an
        agent that must remember to look.
    P12 Maximal-Effort Completeness — every path prints a verdict; the zero
        cases are enumerated and blocked rather than passed.
    P13 Token Economy — one file, two modes, no flag whose only job is to
        select an output format.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# §6: before anything is written. The human diagnostics quote commit-message
# text verbatim, so the stream must be able to carry it.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

TOOL = "check_attribution"
MAX_QUOTE = 120

# ---------------------------------------------------------------------------
# The forbidden vocabulary.
#
# ASSEMBLED FROM PARTS, ON PURPOSE. Each token below is split or carries a
# character class so that no line in this file is a working trailer or a
# working e-mail address. A later reader who joins them back into plain
# literals will have written the forbidden token into a tracked file — see the
# module docstring, "NO FORBIDDEN LITERAL IS REPRODUCED IN THIS FILE".
# ---------------------------------------------------------------------------
# `gpt` is listed alongside the longer word deliberately: it cannot match
# inside that word, because the word-boundary rule below refuses a letter
# before it. The last entry is here for the same reason the others are — its
# noreply domain is its own name.
VENDOR_TOKENS = (
    "claude",
    "anthropi" + "c",
    "copilot",
    "chat" + "gpt",
    "gpt",
    "gemini",
    "codex",
    "open" + "ai",
)

# Hosts that identify a vendor ASSISTANT or its noreply domain. GITHUB IS
# ABSENT AND THAT IS THE POINT: this repository's own commit identity is a
# `users.noreply.github.com` address, so a GitHub domain must never be
# forbidden. A GitHub noreply is caught by its local part instead.
VENDOR_HOSTS = (
    "claude[.]ai",
    "claude[.]com",
    "anthropi" + "c[.]com",
    "chat[.]open" + "ai[.]com",
    "open" + "ai[.]com",
    "copilot[.]microsoft[.]com",
    "gemini[.]google[.]com",
)

_TOKEN_ALT = "|".join(VENDOR_TOKENS)
_HOST_ALT = "|".join(VENDOR_HOSTS)

# A vendor token as a WORD, not as a substring: `gpt` must not fire inside
# `gptools`, and `codex` must not fire inside `codexample`.
VENDOR_WORD_RE = re.compile(r"(?i)(?<![A-Za-z0-9])(" + _TOKEN_ALT + r")(?![A-Za-z0-9])")
# A dot is ALLOWED before a host so a subdomain matches (`api.openai.com`); a
# letter, digit or hyphen is not, so a longer word ending in the host name does
# not (`notaclaude.ai` is nobody's assistant).
VENDOR_HOST_RE = re.compile(r"(?i)(?<![A-Za-z0-9\-])(" + _HOST_ALT + r")\b")

# Any e-mail-shaped token. Split into local part and domain so the two are
# judged by different rules (see REJECT BY PROHIBITION in the docstring).
EMAIL_RE = re.compile(r"(?i)([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")

# A trailer line: a key at the START of the line, then a colon. The anchor is
# what keeps prose out of the findings — a sentence that merely mentions a
# trailer does not begin with its key.
TRAILER_RE = re.compile(
    r"(?i)^[ \t]*([A-Za-z][A-Za-z0-9 _\-]{0,40}?)[ \t]*:[ \t]*(.*)$"
)
CO_AUTHOR_KEY_RE = re.compile(r"(?i)^co[-_ ]?authored[-_ ]?by$")
SESSION_KEY_RE = re.compile(r"(?i)^(?:[A-Za-z0-9 _\-]*[-_ ])?session$")

# "Generated with ..." — with or without a leading robot emoji, bullet or
# other non-word marker, and with or without a Markdown link in the value.
GENERATED_WITH_RE = re.compile(
    r"(?i)^[ \t]*(?:[^\w\s]{1,6}[ \t]*)?generated[ \t]+with\b"
)

# A line whose whole content is a vendor assistant URL: the bare session link
# the harness appends under "Generated with". Anchored to the WHOLE line, so a
# URL cited inside a sentence is not a hit.
BARE_VENDOR_URL_RE = re.compile(
    r"(?i)^[ \t]*(?:[^\w\s]{1,6}[ \t]*)?<?https?://(?:"
    + _HOST_ALT
    + r")(?:/\S*)?>?[ \t]*$"
)

# A scissors line: everything below it is stripped by git and never reaches the
# commit, including the `commit -v` diff.
SCISSORS_RE = re.compile(r"^\s*\S?\s*-{6,}\s*>8\s*-{6,}")

PATTERN_NAMES = (
    "co_authored_vendor",
    "vendor_session_trailer",
    "generated_with_vendor",
    "vendor_email",
    "vendor_assistant_url",
    "vendor_identity_name",
    "vendor_identity_email",
)

REMEDY_VIOLATIONS = (
    "delete the offending line (or correct the offending identity field) and "
    "commit again; an AI/vendor attribution is forbidden in this repository and "
    "its history by Article IX §4 of this repository's constitution. For an "
    "identity hit, fix the configured identity and re-run, or "
    "`git commit --amend --reset-author` once it is correct."
)
SAFE_ALTERNATIVE_MESSAGE = (
    "the commit is NOT lost: this gate runs after the message was written and "
    "writes nothing, so the message file is still on disk with everything you "
    "typed. `git commit --edit` reopens it, or re-run the commit with the "
    "trailer deleted. `git commit --no-verify` bypasses this gate visibly if "
    "the gate itself is wrong."
)
SAFE_ALTERNATIVE_RANGE = (
    "nothing was changed: every git call this mode makes is read-only and "
    "--no-optional-locks. Re-run over a range that resolves. Removing an "
    "attribution already in history is a rewrite, which is a human decision "
    "and never this gate's."
)
QUOTE_NOTE = (
    "values are quoted for diagnosis only — do not paste a violation line into "
    "a commit message, which re-seeds the exact token this gate looks for."
)


def truncate(text):
    """One line, bounded, with the bound made visible rather than silent."""
    flat = text.strip()
    if len(flat) <= MAX_QUOTE:
        return flat
    return flat[:MAX_QUOTE] + " ...[truncated]"


def vendor_hit(text):
    """The vendor token or host `text` names, or None.

    One function so every rule asks the same question the same way; a second
    spelling of "is this a vendor" is how two rules drift apart.

    THE WORD IS TRIED FIRST, and the order is a reporting decision rather than
    a matching one — either branch is a violation, so only the token printed in
    the finding changes. MEASURED on the real trailer pair: host-first reported
    `a co-author trailer names the AI vendor/model 'anthropi[c].com'`, which
    names a domain where the reader can see a NAME on the line. Word-first
    reports 'Claude', which is what the trailer actually says. The URL rule asks
    `vendor_host_hit` instead, because there a host IS the finding.
    """
    match = VENDOR_WORD_RE.search(text)
    if match:
        return match.group(1)
    match = VENDOR_HOST_RE.search(text)
    if match:
        return match.group(1)
    return None


def vendor_host_hit(text):
    """The vendor HOST `text` names, or None — for the rules about URLs."""
    match = VENDOR_HOST_RE.search(text)
    return match.group(1) if match else None


def email_hits(text):
    """Vendor-attributable e-mail tokens in `text`, as (address, token, why).

    The local part and the domain are judged separately and deliberately: the
    domain rule cannot list GitHub (this repository commits under a
    `users.noreply.github.com` address), so a vendor bot on GitHub is caught by
    its local part alone.
    """
    found = []
    for match in EMAIL_RE.finditer(text):
        local, domain = match.group(1), match.group(2)
        host = VENDOR_HOST_RE.search(domain)
        if host:
            found.append((match.group(0), host.group(1), "the domain is a vendor host"))
            continue
        word = VENDOR_WORD_RE.search(local)
        if word:
            found.append(
                (match.group(0), word.group(1), "the local part names a vendor")
            )
    return found


def scan_lines(lines, where, line_offset=1):
    """Every forbidden shape in one message, as violation records.

    `lines` is already split with `str.splitlines()` (CRLF, LF and CR alike —
    §11), so line numbers match what an editor shows and no quoted value
    carries a stray `\\r`.
    """
    violations = []

    def add(pattern, number, line, token, detail):
        violations.append(
            {
                "pattern": pattern,
                "where": where,
                "field": "message",
                "line": number,
                "token": token,
                "value": truncate(line),
                "detail": detail,
            }
        )

    for index, line in enumerate(lines):
        number = index + line_offset
        trailer = TRAILER_RE.match(line)
        if trailer:
            key, value = trailer.group(1), trailer.group(2)
            if CO_AUTHOR_KEY_RE.match(key.strip()):
                token = vendor_hit(value)
                if token:
                    add(
                        "co_authored_vendor",
                        number,
                        line,
                        token,
                        "a co-author trailer names the AI vendor/model "
                        "'%s'; no AI authorship may appear in this history" % token,
                    )
            elif SESSION_KEY_RE.match(key.strip()):
                token = vendor_hit(key) or vendor_hit(value)
                if token:
                    add(
                        "vendor_session_trailer",
                        number,
                        line,
                        token,
                        "a session trailer is keyed on, or points at, the "
                        "vendor assistant '%s'; it is harness metadata and "
                        "must not enter the history" % token,
                    )
        if GENERATED_WITH_RE.match(line):
            token = vendor_hit(line)
            if token:
                add(
                    "generated_with_vendor",
                    number,
                    line,
                    token,
                    "a 'generated with' line credits the AI tool '%s'" % token,
                )
        if BARE_VENDOR_URL_RE.match(line):
            token = vendor_host_hit(line)
            if token:
                add(
                    "vendor_assistant_url",
                    number,
                    line,
                    token,
                    "the line is a bare vendor-assistant URL on host '%s' — "
                    "harness session metadata, not a commit message" % token,
                )
        for address, token, why in email_hits(line):
            add(
                "vendor_email",
                number,
                line,
                token,
                "the message carries the vendor address '%s' (%s)" % (address, why),
            )
    return violations


def scan_identity(where, field, name, email):
    """One commit identity, judged by PROHIBITION — never against a whitelist.

    No required name or email is held anywhere in this file. An allowlist of a
    single human identity would reject the next legitimate contributor and
    would embed a private address in a tracked file to buy nothing.
    """
    violations = []
    raw = "%s <%s>" % (name, email)
    token = VENDOR_WORD_RE.search(name)
    if token:
        violations.append(
            {
                "pattern": "vendor_identity_name",
                "where": where,
                "field": field,
                "line": None,
                "token": token.group(1),
                "value": truncate(raw),
                "detail": "the %s name names the AI vendor/model '%s'"
                % (field, token.group(1)),
            }
        )
    for address, hit, why in email_hits(email):
        violations.append(
            {
                "pattern": "vendor_identity_email",
                "where": where,
                "field": field,
                "line": None,
                "token": hit,
                "value": truncate(raw),
                "detail": "the %s address '%s' is a vendor address (%s)"
                % (field, address, why),
            }
        )
    return violations


# ---------------------------------------------------------------------------
# git — read-only, list argv, no shell (§3).
# ---------------------------------------------------------------------------
def git(repo, *args, **kwargs):
    """`(stdout_bytes, None)` or `(None, reason)`. Never raises on git's account."""
    argv = ["git", "--no-optional-locks", "-C", str(repo)] + list(args)
    try:
        done = subprocess.run(argv, capture_output=True, timeout=60)
    except FileNotFoundError:
        return None, (
            "git is not on PATH, so the range could not be read "
            "(install git, or run the --message-file mode)"
        )
    except subprocess.TimeoutExpired:
        return None, "git did not answer within 60s: " + " ".join(args)
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip().splitlines()
        return None, (
            "git %s failed: %s"
            % (" ".join(args), detail[0] if detail else "exit %d" % done.returncode)
        )
    return done.stdout, None


def comment_char(repo):
    """`core.commentChar`, or `#`. Never fatal: an unreadable config is a `#`."""
    data, _ = git(repo, "config", "--get", "core.commentChar")
    if not data:
        return "#"
    value = data.decode("utf-8", "replace").strip()
    if not value or value.lower() == "auto" or len(value) != 1:
        return "#"
    return value


# ---------------------------------------------------------------------------
# Modes.
# ---------------------------------------------------------------------------
def blocked(mode, error, remedy, safe_alternative, counts=None, scope=None):
    return {
        "tool": TOOL,
        "verdict": "BLOCKED",
        "mode": mode,
        "scope": scope or {},
        "error": error,
        "counts": counts
        or {
            "messages_examined": 0,
            "commits_examined": 0,
            "identities_examined": 0,
            "lines_scanned": 0,
            "lines_excluded": 0,
        },
        "patterns_applied": list(PATTERN_NAMES),
        "violations": [],
        "remedy": remedy,
        "safe_alternative": safe_alternative,
        "note": QUOTE_NOTE,
    }


def run_message_file(path):
    """One prospective commit message. The hook's mode."""
    mode = "message-file"
    target = Path(path)
    if not target.exists():
        return blocked(
            mode,
            "message file does not exist: %s" % target,
            "pass the path git hands the hook as $1",
            SAFE_ALTERNATIVE_MESSAGE,
            scope={"message_file": str(target)},
        )
    try:
        # BINARY, then decode — never read_text() (§10/§11).
        with open(str(target), "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        return blocked(
            mode,
            "message file could not be read: %s (%s)" % (target, exc),
            "check the path and its permissions, then commit again",
            SAFE_ALTERNATIVE_MESSAGE,
            scope={"message_file": str(target)},
        )

    text = raw.decode("utf-8", "replace")
    all_lines = text.splitlines()

    # Cut at the scissors line, then drop comment lines. BOTH are removed by
    # git's default cleanup and cannot reach the commit, so a gate that fired
    # on the template's own commentary — or on the `commit -v` diff below the
    # scissors — would be blocking text that does not exist downstream.
    # RESIDUAL, RECORDED: under `--cleanup=verbatim` a commented line DOES
    # land. Range mode catches that after the fact, on the branch.
    marker = comment_char(target.parent if target.parent.parts else ".")
    kept, numbers, excluded = [], [], 0
    cut = False
    for index, line in enumerate(all_lines):
        if cut:
            excluded += 1
            continue
        if SCISSORS_RE.match(line) and line.lstrip().startswith(marker):
            cut = True
            excluded += 1
            continue
        if line.lstrip().startswith(marker):
            excluded += 1
            continue
        kept.append(line)
        numbers.append(index + 1)

    scannable = [line for line in kept if line.strip()]
    counts = {
        "messages_examined": 1,
        "commits_examined": 0,
        "identities_examined": 0,
        "lines_scanned": len(scannable),
        "lines_excluded": excluded,
    }
    scope = {
        "message_file": str(target),
        "comment_char": marker,
        "lines_in_file": len(all_lines),
    }

    if not scannable:
        # FAIL ON ZERO: a gate that examined nothing must say so, not pass.
        # Safe by construction — git refuses an empty commit message anyway.
        return blocked(
            mode,
            "the message file contains no scannable line (%d line(s) "
            "in the file, all blank, commented, or below the "
            "scissors), so the gate examined nothing" % len(all_lines),
            "write a commit message and commit again",
            SAFE_ALTERNATIVE_MESSAGE,
            counts=counts,
            scope=scope,
        )

    violations = []
    for offset, line in enumerate(kept):
        violations.extend(scan_lines([line], mode, line_offset=numbers[offset]))

    return {
        "tool": TOOL,
        "verdict": "VIOLATIONS" if violations else "CLEAN",
        "mode": mode,
        "scope": scope,
        "counts": counts,
        "not_examined": [
            "author/committer identity — not present in a message "
            "file; range mode examines both (recorded shortfall 1)"
        ],
        "patterns_applied": list(PATTERN_NAMES),
        "violations": violations,
        "remedy": REMEDY_VIOLATIONS,
        "safe_alternative": SAFE_ALTERNATIVE_MESSAGE,
        "note": QUOTE_NOTE,
    }


# Field and record separators for the one `git log` call. ASCII 0x1f / 0x1e:
# not `\n` (a commit body is full of them) and not `\0` (git's own -z would
# collide). A message containing a raw 0x1e would mis-split; that is a control
# character in a commit message, and the split is reported by commit count so
# the mis-split cannot pass as a clean scan.
FS, RS = "\x1f", "\x1e"


def run_range(repo, base, head):
    """Every commit in `base..head`: message, author, committer. The CI mode."""
    mode = "range"
    scope = {
        "repo": str(repo),
        "base_sha": base,
        "head_sha": head,
        "range": "%s..%s" % (base, head),
    }
    remedy_range = (
        "give a range that resolves: "
        "--base-sha <sha> --head-sha <sha>, both reachable in the "
        "repository named by --repo"
    )

    for label, value in (("--base-sha", base), ("--head-sha", head)):
        _, reason = git(repo, "rev-parse", "--verify", "--quiet", "%s^{commit}" % value)
        if reason:
            return blocked(
                mode,
                "%s does not resolve to a commit: '%s' (%s)" % (label, value, reason),
                remedy_range,
                SAFE_ALTERNATIVE_RANGE,
                scope=scope,
            )

    fmt = FS.join(["%H", "%an", "%ae", "%cn", "%ce", "%B"]) + RS
    data, reason = git(
        repo, "log", "--reverse", "--format=" + fmt, "%s..%s" % (base, head)
    )
    if reason:
        return blocked(
            mode,
            "the range %s..%s could not be read: %s" % (base, head, reason),
            remedy_range,
            SAFE_ALTERNATIVE_RANGE,
            scope=scope,
        )

    records = [
        chunk for chunk in data.decode("utf-8", "replace").split(RS) if chunk.strip()
    ]
    if not records:
        # FAIL ON ZERO. An empty range is the shape a mis-computed CI variable
        # takes, and reading it as CLEAN is how a gate reports green for a
        # question it never asked.
        return blocked(
            mode,
            "the range %s..%s resolved to 0 commits, so the gate "
            "examined nothing" % (base, head),
            remedy_range + " (a base that already contains head "
            "yields an empty range — widen it)",
            SAFE_ALTERNATIVE_RANGE,
            scope=scope,
        )

    violations, lines_scanned, identities = [], 0, 0
    for record in records:
        fields = record.lstrip("\n").split(FS)
        if len(fields) < 6:
            return blocked(
                mode,
                "a commit record from `git log` did not carry its 6 "
                "fields (got %d) — the scan is not trustworthy and "
                "is reported as such rather than as a pass" % len(fields),
                remedy_range,
                SAFE_ALTERNATIVE_RANGE,
                scope=scope,
            )
        sha, an, ae, cn, ce, body = (
            fields[0].strip(),
            fields[1],
            fields[2],
            fields[3],
            fields[4],
            fields[5],
        )
        lines = body.splitlines()
        lines_scanned += len([line for line in lines if line.strip()])
        violations.extend(scan_lines(lines, sha[:12]))
        violations.extend(scan_identity(sha[:12], "author", an, ae))
        violations.extend(scan_identity(sha[:12], "committer", cn, ce))
        identities += 2

    counts = {
        "messages_examined": len(records),
        "commits_examined": len(records),
        "identities_examined": identities,
        "lines_scanned": lines_scanned,
        "lines_excluded": 0,
    }

    if identities == 0:  # unreachable by construction;
        return blocked(
            mode,  # asserted anyway, because "it
            "0 identities examined across %d commit(s)"
            % len(records),  # cannot happen" is what every
            remedy_range,
            SAFE_ALTERNATIVE_RANGE,
            counts=counts,
            scope=scope,
        )  # blind gate said first.

    return {
        "tool": TOOL,
        "verdict": "VIOLATIONS" if violations else "CLEAN",
        "mode": mode,
        "scope": scope,
        "counts": counts,
        "patterns_applied": list(PATTERN_NAMES),
        "violations": violations,
        "remedy": REMEDY_VIOLATIONS,
        "safe_alternative": SAFE_ALTERNATIVE_RANGE,
        "note": QUOTE_NOTE,
    }


def report(payload):
    """Human diagnostics on stderr — on EVERY path, the clean one included.

    A silent return IS the defect (recorded directive). The verdict line always
    carries the denominator, so a reader can see how much was looked at and not
    only what was found.
    """
    counts = payload["counts"]
    scope = "%d message(s), %d commit(s), %d identit(ies), %d line(s) scanned" % (
        counts["messages_examined"],
        counts["commits_examined"],
        counts["identities_examined"],
        counts["lines_scanned"],
    )
    if counts["lines_excluded"]:
        scope += (
            ", %d line(s) excluded as comments/below-scissors"
            % counts["lines_excluded"]
        )
    verdict = payload["verdict"]
    out = sys.stderr

    if verdict == "BLOCKED":
        out.write("%s: BLOCKED [%s] — %s\n" % (TOOL, payload["mode"], payload["error"]))
        out.write("%s: examined %s\n" % (TOOL, scope))
        out.write("%s: fix: %s\n" % (TOOL, payload["remedy"]))
        out.write("%s: safe alternative: %s\n" % (TOOL, payload["safe_alternative"]))
        return
    if verdict == "VIOLATIONS":
        out.write(
            "%s: VIOLATIONS [%s] — %d forbidden attribution(s); "
            "examined %s\n" % (TOOL, payload["mode"], len(payload["violations"]), scope)
        )
        for item in payload["violations"]:
            place = item["where"]
            if item["line"] is not None:
                place += " line %d" % item["line"]
            elif item["field"] != "message":
                place += " %s" % item["field"]
            out.write("  [%s] %s: %s\n" % (item["pattern"], place, item["detail"]))
            out.write("    value: %s\n" % item["value"])
        out.write("%s: fix: %s\n" % (TOOL, payload["remedy"]))
        out.write("%s: safe alternative: %s\n" % (TOOL, payload["safe_alternative"]))
        out.write("%s: %s\n" % (TOOL, payload["note"]))
        return
    out.write(
        "%s: CLEAN [%s] — no forbidden attribution; examined %s\n"
        % (TOOL, payload["mode"], scope)
    )
    for gap in payload.get("not_examined", []):
        out.write("%s:   not examined: %s\n" % (TOOL, gap))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_attribution.py",
        description="VCS attribution gate: commit MESSAGES and IDENTITIES only "
        "(never file contents — the product ships a legitimate "
        "vendor adapter).",
    )
    parser.add_argument(
        "--message-file",
        help="one prospective commit message (the commit-msg " "hook's $1)",
    )
    parser.add_argument(
        "--base-sha", help="range mode, with --head-sha: exclusive start"
    )
    parser.add_argument("--head-sha", help="range mode, with --base-sha: inclusive end")
    parser.add_argument(
        "--repo", default=".", help="repository for range mode (default: cwd)"
    )
    args = parser.parse_args(argv)

    usage = (
        "give exactly one mode: `--message-file <path>`, or "
        "`--base-sha <sha> --head-sha <sha>` together"
    )
    wants_message = args.message_file is not None
    wants_range = args.base_sha is not None or args.head_sha is not None

    if wants_message and wants_range:
        payload = blocked(
            "none",
            "both modes given (--message-file together "
            "with a range); they answer different "
            "questions and count different things",
            usage,
            "nothing was read; re-run with one mode",
        )
    elif wants_message:
        payload = run_message_file(args.message_file)
    elif wants_range:
        if args.base_sha is None or args.head_sha is None:
            given = "--head-sha" if args.base_sha is None else "--base-sha"
            missing = "--base-sha" if args.base_sha is None else "--head-sha"
            payload = blocked(
                "range",
                "%s given without %s: half a range is a usage "
                "error, never an assumed endpoint (value given: "
                "'%s')" % (given, missing, args.head_sha or args.base_sha),
                usage,
                "nothing was read; re-run with both halves",
            )
        else:
            payload = run_range(Path(args.repo), args.base_sha, args.head_sha)
    else:
        payload = blocked(
            "none", "no mode given", usage, "nothing was read; re-run with one mode"
        )

    # JSON always, on stdout. `ensure_ascii=False` is safe only because the
    # §6 prologue reconfigured the stream; the two travel together.
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    report(payload)
    return {"CLEAN": 0, "VIOLATIONS": 1, "BLOCKED": 2}[payload["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
