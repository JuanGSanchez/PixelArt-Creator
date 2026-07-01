#!/usr/bin/env python
# =============================================================================
# subagent-report.py  (project-level Claude Code hook — PixelArt Creator system)
#
# Opt-in "answer-as-report" hook (ENABLED for this system). Keeps the
# orchestrator's / invoking agent's context lean: heavy-output subagents write
# their COMPLETE deliverable to a report file and return only a thin EXIT_STATUS
# pointer. Realized as a two-event native hook, matcher-scoped to the heavy-output
# agents ONLY (AGT-03/04/05/06/08, the-researcher/M4, the-gleaner/M5):
#   * SubagentStart -> inject the answer-as-report CONTRACT via
#       hookSpecificOutput.additionalContext (file pattern + EXIT_STATUS shape).
#   * SubagentStop  -> if no deliverable/report file for this agent_id is found,
#       remind ONCE via exit code 2 + stderr (SubagentStop has no updatedOutput;
#       a hook can only remind, it cannot rewrite the return — the authoritative
#       contract lives inside each subagent's own definition, P6).
#
# Coexistence (Open Item 2/3): this hook is wired as a SEPARATE SubagentStop
# matcher group; it does NOT displace the existing SubagentStop->gleaner-budget.py
# `the-gleaner` group (both stack). For the-gleaner a `gather-*` file satisfies the
# report requirement, so the Gleaner is not double-nagged when it did its job.
#
# FAIL OPEN: any internal error -> exit 0 (no feedback).
# Wiring: .claude/settings.json -> SubagentStart + SubagentStop (matcher = the 7
#   heavy-output agent types). Invoked: python "$CLAUDE_PROJECT_DIR/.claude/hooks/subagent-report.py"
# =============================================================================
import sys
import os
import io
import json
import glob
import datetime

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(HOOKS_DIR)
DOCS_DIR = os.path.join(PROJECT_DIR, "docs")
DEBUG_LOG = os.path.join(HOOKS_DIR, ".subagent-report-debug.log")

# Agent types opted into the answer-as-report contract (Dossier §6.3).
SCOPED = (
    "agt-03-python-dev", "agt-04-python-tester", "agt-05-ui-expert",
    "agt-06-qa-expert", "agt-08-documenter", "the-researcher", "the-gleaner",
)

CONTRACT = (
    "[subagent-report contract] You are a heavy-output subagent. Deliver your "
    "COMPLETE answer as a FILE, not inline, to keep the invoker's context lean:\n"
    "1. Write your full deliverable to "
    "docs/subagent-report-%(type)s-%(id8)s-%(stamp)s.md "
    "(create docs/ if absent; verify the write on disk).\n"
    "2. Return ONLY this thin pointer to the invoker:\n"
    "   EXIT_STATUS:\n"
    "     summary: <2-4 line synopsis>\n"
    "     report_file: <absolute path you wrote>\n"
    "     status: COMPLETED | PARTIAL | BLOCKED\n"
    "     key_points: <bullets the invoker needs without opening the file>\n"
    "If your entire result is genuinely 1-2 lines, you may answer inline instead. "
    "(For the-gleaner, your gather file docs/gather-<agent>-<title> IS your report; "
    "return the thin EXIT_STATUS pointing at it.)"
)


def log_debug(msg):
    try:
        with io.open(DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (datetime.datetime.now().isoformat(), msg))
    except Exception:
        pass


def allow():
    sys.exit(0)


def safe_type(agent_type):
    out = "".join(c if (c.isalnum() or c == "-") else "-" for c in str(agent_type or "agent"))
    return out.strip("-").lower() or "agent"


def in_scope(atype):
    a = safe_type(atype)
    return any(a == s or s in a for s in SCOPED)


def state_path(key):
    return os.path.join(HOOKS_DIR, ".subagent-report-state-%s.json" % key)


def read_state(key):
    try:
        with io.open(state_path(key), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def write_state(key, state):
    try:
        with io.open(state_path(key), "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception as e:
        log_debug("write_state failed: %r" % e)


def deliverable_exists(atype, aid8):
    # A report file for this agent_id, or (for the-gleaner) a gather file, counts.
    try:
        patterns = [os.path.join(DOCS_DIR, "subagent-report-*%s*.md" % aid8)]
        if "gleaner" in safe_type(atype):
            patterns.append(os.path.join(DOCS_DIR, "gather-*"))
        for pat in patterns:
            if glob.glob(pat):
                return True
    except Exception as e:
        log_debug("glob failed: %r" % e)
    return False


def handle_start(data):
    atype = safe_type(data.get("agent_type"))
    if not in_scope(atype):
        allow()
    aid8 = str(data.get("agent_id") or "unknown")[:8]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    ctx = CONTRACT % {"type": atype, "id8": aid8, "stamp": stamp}
    out = {"hookSpecificOutput": {"hookEventName": "SubagentStart",
                                  "additionalContext": ctx}}
    sys.stdout.write(json.dumps(out))
    sys.stdout.flush()
    sys.exit(0)


def handle_stop(data):
    atype = safe_type(data.get("agent_type"))
    if not in_scope(atype):
        allow()
    aid8 = str(data.get("agent_id") or "unknown")[:8]
    key = "%s-%s" % (atype, aid8)
    state = read_state(key)
    if state.get("reminded"):
        allow()  # loop-guard: remind at most once per subagent session
    if deliverable_exists(atype, aid8):
        allow()  # report/gather file present -> contract satisfied
    state["reminded"] = True
    write_state(key, state)
    msg = (
        "[subagent-report hook] No report file found for this subagent. Before "
        "returning, write your COMPLETE deliverable to "
        "docs/subagent-report-%s-%s-<UTCSTAMP>.md and return ONLY the thin "
        "EXIT_STATUS pointer (summary / report_file absolute path / status / "
        "key_points). If your result is genuinely 1-2 lines, an inline answer is "
        "acceptable." % (atype, aid8))
    sys.stderr.write(msg)
    sys.stderr.flush()
    sys.exit(2)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        log_debug("stdin parse failed: %r" % e)
        allow()
    event = data.get("hook_event_name") or ""
    try:
        if event == "SubagentStart":
            handle_start(data)
        elif event == "SubagentStop":
            handle_stop(data)
        else:
            allow()
    except SystemExit:
        raise
    except Exception as e:
        log_debug("handler %s failed: %r" % (event, e))
        allow()  # fail open


if __name__ == "__main__":
    main()
