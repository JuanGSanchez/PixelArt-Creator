#!/usr/bin/env python
# =============================================================================
# gleaner-budget.py   (project-level Claude Code hook — PixelArt Creator system)
#
# Realizes TWO Gleaner-only mandatory orchestrator-design hooks as ONE real
# Claude Code SubagentStop hook, matched to the `the-gleaner` agent type:
#   * Gleaner Pre-Close (unconditional): fires on every Gleaner SubagentStop —
#     reminds the Gleaner to finalize its gather file (docs/gather-<agent>-
#     <key-title>), set STATUS (COMPLETE|IN-PROGRESS), and return the correct
#     EXIT STATUS (COMPLETED|PARTIAL|EXHAUSTED|BLOCKED|FAILED).
#   * Gleaner Pre-Exhaustion (>=70%): when context is high, additionally
#     escalate write frequency (write after every finding) and, if no capacity
#     remains, finalize and return EXHAUSTED for re-dispatch.
#
# Control protocol (asset-metaprompting/references/claude.md §HOOK): SubagentStop
# has NO stop_hook_active and NO updatedOutput. Continuation feedback is sent via
# exit code 2 + stderr. A per-agent_id state file is the loop-guard so the
# reminder is injected at most once per Gleaner session. The reminder is an
# instruction, not a hard guarantee — the Gleaner's own definition
# (.claude/agents/the-gleaner.md) carries the authoritative gather/exit contract.
#
# Gather-file spec: .claude/agents/the-gleaner.md (Outputs).
# FAIL OPEN: any internal error -> exit 0 with no feedback.
#
# Wiring: .claude/settings.json  ->  SubagentStop, matcher "the-gleaner"
# Invoked as: python "$CLAUDE_PROJECT_DIR/.claude/hooks/gleaner-budget.py"
# =============================================================================
import sys
import os
import io
import json
import datetime

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(HOOKS_DIR)
DEBUG_LOG = os.path.join(HOOKS_DIR, ".gleaner-budget-debug.log")
TAIL_BYTES = 512 * 1024


def _int_env(name, default):
    try:
        return int(os.environ.get(name, "").strip())
    except (ValueError, AttributeError):
        return default


PREEXH_PCT = _int_env("PIXELART_CHECKPOINT_PCT", 70)

DEFAULT_CONTEXT_LIMIT = 200000
MODEL_CONTEXT_WINDOWS = (
    ("claude-opus-4-8", 1000000), ("claude-opus-4-7", 1000000),
    ("claude-opus-4-6", 1000000), ("claude-sonnet-4-6", 1000000),
    ("claude-fable-5", 1000000), ("claude-haiku-4-5", 200000),
    ("claude-sonnet-4-5", 200000), ("claude-opus-4-5", 200000),
    ("claude-opus-4-1", 200000), ("claude-3", 200000),
)


def resolve_limit(model):
    env = os.environ.get("CLAUDE_CONTEXT_LIMIT", "").strip()
    if env:
        try:
            v = int(env)
            if v > 0:
                return v
        except ValueError:
            pass
    if model:
        m = str(model).strip().lower()
        for prefix, win in MODEL_CONTEXT_WINDOWS:
            if m.startswith(prefix):
                return win
    return DEFAULT_CONTEXT_LIMIT


def log_debug(msg):
    try:
        with io.open(DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (datetime.datetime.now().isoformat(), msg))
    except Exception:
        pass


def allow():
    sys.exit(0)


def safe_type(agent_type):
    out = "".join(c if c.isalnum() else "-" for c in str(agent_type or "agent"))
    return out.strip("-") or "agent"


def state_path(key):
    return os.path.join(HOOKS_DIR, ".gleanerstate-%s.json" % key)


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


def estimate_context(transcript_path):
    if not transcript_path or not os.path.isfile(transcript_path):
        return None, None
    try:
        size = os.path.getsize(transcript_path)
        with io.open(transcript_path, "rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
                raw = fh.read()
                nl = raw.find(b"\n")
                if nl != -1:
                    raw = raw[nl + 1:]
            else:
                raw = fh.read()
        text = raw.decode("utf-8", "replace")
    except Exception as e:
        log_debug("estimate read failed: %r" % e)
        return None, None
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line or '"usage"' not in line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("isSidechain"):
            continue
        msg = obj.get("message")
        if not isinstance(msg, dict):
            continue
        usage = msg.get("usage")
        if not isinstance(usage, dict) or usage.get("input_tokens") is None:
            continue
        total = ((usage.get("input_tokens") or 0)
                 + (usage.get("cache_read_input_tokens") or 0)
                 + (usage.get("cache_creation_input_tokens") or 0))
        if total > 0:
            return total, msg.get("model")
    return None, None


def handle_subagent_stop(data):
    atype = safe_type(data.get("agent_type"))
    # Defensive: this hook is matcher-scoped to the-gleaner, but re-check so a
    # mis-wire cannot nag other subagents.
    if "gleaner" not in atype.lower():
        allow()
    aid8 = str(data.get("agent_id") or "unknown")[:8]
    key = "gleaner-%s" % aid8
    state = read_state(key)
    if state.get("requested"):
        allow()  # loop-guard: remind at most once per Gleaner session

    tokens, model = estimate_context(data.get("transcript_path"))
    high = False
    pct_txt = "unknown"
    if tokens is not None:
        pct = tokens * 100.0 / resolve_limit(model)
        pct_txt = "~%d%%" % round(pct)
        high = pct >= PREEXH_PCT

    state["requested"] = True
    write_state(key, state)

    # Pre-Close (always) + Pre-Exhaustion (only when high) reminder.
    lines = [
        "[gleaner-budget hook] Gleaner Pre-Close check (context %s). Before you "
        "return, finalize your gather file per .claude/agents/the-gleaner.md:" % pct_txt,
        "1. Update FILES PROCESSED and FILES REMAINING to the true state; set "
        "LAST UPDATED to the current timestamp.",
        "2. Set STATUS = COMPLETE if every requested file was processed, else "
        "IN-PROGRESS. Write the gather file to docs/gather-<requesting-agent>-"
        "<key-title> and confirm the write on disk.",
        "3. Return EXIT STATUS: COMPLETED if all processed + write confirmed; "
        "PARTIAL at a logical stop; EXHAUSTED if a resource limit forced the stop "
        "(put the gather-file path in Checkpoint); BLOCKED if files were "
        "inaccessible; FAILED if the gather file could not be written.",
    ]
    if high:
        lines.append(
            "4. Context is at the pre-exhaustion threshold (>=70%): escalate to "
            "writing after EACH finding, do not start any file estimated to "
            "exceed the remaining budget, and if no capacity remains, finalize now "
            "and return EXHAUSTED so the orchestrator re-dispatches you from the "
            "gather file (do NOT re-read processed files).")
    # SubagentStop continuation is signaled by exit code 2 + stderr.
    sys.stderr.write("\n".join(lines))
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
        if event == "SubagentStop":
            handle_subagent_stop(data)
        else:
            allow()
    except SystemExit:
        raise
    except Exception as e:
        log_debug("handler %s failed: %r" % (event, e))
        allow()  # fail open


if __name__ == "__main__":
    main()
