#!/usr/bin/env python
# =============================================================================
# session-contract.py  (project-level Claude Code hook — PixelArt Creator system)
#
# Standing operating-contract reminder. On SessionStart (startup|resume|clear|
# compact) it injects ONE line of context reminding the assistant to act as the
# repo's canonical orchestrator (per .claude/agents/orchestrator.md) and to
# default to Maximal-Effort Completeness (P12). This is REINFORCEMENT, not
# enforcement — the authoritative contract lives in the delivered system's own
# assets (the orchestrator + agents). This project-level hook MIRRORS (does not
# hardcode a per-project copy of) the user-level
# $HOME/.claude/hooks/claude-orchestration-contract.py.
#
# Coexistence (Open Item 3): wired as a SEPARATE SessionStart matcher group; it
# does NOT displace the existing SessionStart->context-budget.py group (both stack).
#
# FAIL OPEN: any internal error -> exit 0 (no feedback).
# Wiring: .claude/settings.json -> SessionStart (matcher "startup|resume|clear|compact").
# Invoked: python "$CLAUDE_PROJECT_DIR/.claude/hooks/session-contract.py"
# =============================================================================
import sys
import os
import io
import json
import datetime

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_LOG = os.path.join(HOOKS_DIR, ".session-contract-debug.log")

REMINDER = (
    "[operating contract] Act as this repo's canonical orchestrator "
    "(.claude/agents/orchestrator.md): decompose, dispatch to the owning agent, "
    "validate outputs + exit status, sequence the SDD gates (no implement before "
    "analyze passes), and NEVER perform domain work inline. Default to "
    "Maximal-Effort Completeness (P12): carry every task to a definitive, "
    "fully-covered, ready-to-grow end unless the user says otherwise."
)


def log_debug(msg):
    try:
        with io.open(DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (datetime.datetime.now().isoformat(), msg))
    except Exception:
        pass


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        log_debug("stdin parse failed: %r" % e)
        sys.exit(0)
    event = data.get("hook_event_name") or ""
    try:
        if event == "SessionStart":
            out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                          "additionalContext": REMINDER}}
            sys.stdout.write(json.dumps(out))
            sys.stdout.flush()
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        log_debug("handler failed: %r" % e)
        sys.exit(0)  # fail open


if __name__ == "__main__":
    main()
