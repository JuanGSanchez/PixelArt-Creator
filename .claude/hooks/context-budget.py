#!/usr/bin/env python
# =============================================================================
# context-budget.py   (project-level Claude Code hook — PixelArt Creator system)
#
# Realizes TWO mandatory orchestrator-design hooks as REAL Claude Code native
# hooks (fail-open, harness-enforced):
#   * Pre-Exhaustion Checkpoint (all agents)  -> Stop (>=70%: block + instruct
#                                                write) + PreCompact (script
#                                                fallback; model unavailable there)
#   * Session Resume Checkpoint Load (all)    -> SessionStart (startup|resume|
#                                                compact) + UserPromptSubmit
#                                                (inject newest checkpoint)
#
# Checkpoint policy source of truth: .claude/instructions/agent-checkpoint.md
#   (Agent Checkpoint Instruction). Naming convention (CONVENTIONS, Dossier §3):
#     docs/checkpoint-<agent>-<workflow-title>-<YYYYMMDD-HHMMSS>.md
#   Thresholds (Dossier §5): checkpoint 70% < compacting 75% (intentional gap).
#
# Design notes (grounded in asset-metaprompting/references/claude.md §HOOK):
#   * A Claude Code hook CANNOT trigger /compact. It nudges at Stop and
#     guarantees a checkpoint exists BEFORE compaction via PreCompact, then
#     reloads it after (SessionStart compact / UserPromptSubmit).
#   * Context % is not handed to hooks; it is estimated from the transcript's
#     most recent assistant `usage` (input + cache_read + cache_creation) over
#     the per-model context window.
#   * FAIL OPEN: any internal error -> exit 0 with no decision, so a bug here
#     can never break a live session.
#
# Wiring: .claude/settings.json (Stop, PreCompact, SessionStart, UserPromptSubmit)
# Invoked as: python "$CLAUDE_PROJECT_DIR/.claude/hooks/context-budget.py"
# Interpreter precondition (declare in DEPLOYMENT.md): `python` on PATH (3.8+).
# =============================================================================
import sys
import os
import io
import json
import glob
import datetime

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(HOOKS_DIR)
DEBUG_LOG = os.path.join(HOOKS_DIR, ".context-budget-debug.log")


def _int_env(name, default):
    try:
        return int(os.environ.get(name, "").strip())
    except (ValueError, AttributeError):
        return default


# Thresholds — Dossier §5. Checkpoint (pre-exhaustion) fires at 70%, before the
# 75% compacting threshold, so agents persist state while context remains to
# write a complete checkpoint.
PREEXH_PCT   = _int_env("PIXELART_CHECKPOINT_PCT", 70)
DELTA_TOKENS = _int_env("PIXELART_CHECKPOINT_DELTA_TOKENS", 15000)  # throttle
TAIL_BYTES       = 512 * 1024
INJECT_MAX_CHARS = 12000

# docs/ is the shared temporal-file location (Dossier §3 CONVENTIONS).
def ckpt_dir():
    d = os.path.join(PROJECT_DIR, "docs")
    return d if os.path.isdir(d) else PROJECT_DIR

# Checkpoint prefixes scanned for reload. Model-written checkpoints follow the
# mandatory naming (checkpoint-<agent>-<workflow>-<ts>.md); the script-written
# PreCompact fallback uses the precompact prefix.
PREFIX_CKPT      = "checkpoint"
PREFIX_PRECOMPACT = "checkpoint-precompact"

DEFAULT_CONTEXT_LIMIT = 200000
_WINDOW_1M   = 1000000
_WINDOW_200K = 200000
MODEL_CONTEXT_WINDOWS = (
    ("claude-opus-4-8",   _WINDOW_1M),
    ("claude-opus-4-7",   _WINDOW_1M),
    ("claude-opus-4-6",   _WINDOW_1M),
    ("claude-sonnet-4-6", _WINDOW_1M),
    ("claude-fable-5",    _WINDOW_1M),
    ("claude-haiku-4-5",  _WINDOW_200K),
    ("claude-sonnet-4-5", _WINDOW_200K),
    ("claude-opus-4-5",   _WINDOW_200K),
    ("claude-opus-4-1",   _WINDOW_200K),
    ("claude-3",          _WINDOW_200K),
)


def window_for_model(model):
    if not model:
        return None
    m = str(model).strip().lower()
    for prefix, win in MODEL_CONTEXT_WINDOWS:
        if m.startswith(prefix):
            return win
    return None


def resolve_context_limit(model):
    env = os.environ.get("CLAUDE_CONTEXT_LIMIT", "").strip()
    if env:
        try:
            v = int(env)
            if v > 0:
                return v, "env"
        except ValueError:
            pass
    win = window_for_model(model)
    if win:
        return win, "model:%s" % model
    return DEFAULT_CONTEXT_LIMIT, "default"


def log_debug(msg):
    try:
        with io.open(DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (datetime.datetime.now().isoformat(), msg))
    except Exception:
        pass


def emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()
    sys.exit(0)


def allow():
    sys.exit(0)


def session8(data):
    sid = str(data.get("session_id") or "unknown")
    return sid[:8] if sid else "unknown"


def now_stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def state_path(sid8):
    return os.path.join(HOOKS_DIR, ".cbstate-%s.json" % sid8)


def read_state(sid8):
    try:
        with io.open(state_path(sid8), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def write_state(sid8, state):
    try:
        with io.open(state_path(sid8), "w", encoding="utf-8") as fh:
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
        if not isinstance(usage, dict):
            continue
        if usage.get("input_tokens") is None:
            continue
        total = ((usage.get("input_tokens") or 0)
                 + (usage.get("cache_read_input_tokens") or 0)
                 + (usage.get("cache_creation_input_tokens") or 0))
        if total > 0:
            return total, msg.get("model")
    return None, None


def newest_checkpoint(directory):
    candidates = []
    for pat in ("%s-*.md" % PREFIX_CKPT,):
        for p in glob.glob(os.path.join(directory, pat)):
            if os.path.isfile(p):
                candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


# ---- handlers --------------------------------------------------------------
def handle_stop(data):
    sid8 = session8(data)
    if data.get("stop_hook_active"):
        allow()  # second pass — checkpoint already written; let the stop proceed
    tokens, model = estimate_context(data.get("transcript_path"))
    if tokens is None:
        allow()
    limit, limit_src = resolve_context_limit(model)
    pct = tokens * 100.0 / limit
    log_debug("stop tokens=%d limit=%d (%s) pct=%.1f" % (tokens, limit, limit_src, pct))
    if pct < PREEXH_PCT:
        allow()
    state = read_state(sid8)
    last_tokens = state.get("block_last_tokens", 0)
    if (tokens - last_tokens) < DELTA_TOKENS and last_tokens:
        allow()
    state["block_last_tokens"] = tokens
    write_state(sid8, state)
    stamp = now_stamp()
    reason = (
        "[context-budget hook] Context is ~%d%% (%d/%d tokens) — the "
        "pre-exhaustion threshold (70%%). Per the Agent Checkpoint Instruction "
        "(.claude/instructions/agent-checkpoint.md), write a checkpoint before "
        "you stop:\n"
        "1. Compose a self-contained checkpoint so a FRESH session resumes with "
        "zero loss, with headed fields: AGENT, WORKFLOW TITLE, TIMESTAMP (%s), "
        "COMPLETENESS (COMPLETE|PARTIAL), WORKFLOW POSITION, USER REQUIREMENTS, "
        "ACTIVE CONSTRAINTS, DECISIONS, FINDINGS, OPEN QUESTIONS, NOTES.\n"
        "2. If a prior docs/checkpoint-<agent>-<workflow>-*.md exists for this "
        "agent+workflow, MERGE its content in, write the new file, then delete "
        "the prior file only after the new file is confirmed on disk "
        "(one-file-per-agent+workflow invariant).\n"
        "3. Write it to: docs/checkpoint-<agent>-<workflow-title>-%s.md\n"
        "4. Verify it exists on disk (read it back or glob), report the confirmed "
        "path in one line, then end your turn. Consider /compact afterward — the "
        "newest checkpoint is reloaded automatically on resume."
    ) % (round(pct), tokens, limit, stamp, stamp)
    sysmsg = ("Context-budget checkpoint requested at ~%d%% of a %s-token window "
              "(source: %s). Intentional pause so a resume checkpoint is written — "
              "not a failure." % (round(pct), format(limit, ","), limit_src))
    emit({"decision": "block", "reason": reason, "systemMessage": sysmsg})


def _transcript_tail_text(transcript_path, max_msgs=12):
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
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
        lines = raw.decode("utf-8", "replace").splitlines()
    except Exception as e:
        log_debug("tail text read failed: %r" % e)
        return ""
    snippets = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("isSidechain"):
            continue
        role = obj.get("type")
        if role not in ("user", "assistant"):
            continue
        content = (obj.get("message") or {}).get("content")
        text = ""
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "\n".join(b.get("text", "") for b in content
                             if isinstance(b, dict) and b.get("type") == "text")
        text = text.strip()
        if not text:
            continue
        snippets.append("### %s\n%s" % (role, text[:1200]))
        if len(snippets) >= max_msgs:
            break
    snippets.reverse()
    return "\n\n".join(snippets)


def handle_precompact(data):
    # Model is unavailable during PreCompact; write a mechanical fallback so a
    # checkpoint always precedes context loss.
    sid8 = session8(data)
    directory = ckpt_dir()
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception:
        pass
    stamp = now_stamp()
    fname = "%s-%s-%s.md" % (PREFIX_PRECOMPACT, sid8, stamp)
    fpath = os.path.join(directory, fname)
    tail = _transcript_tail_text(data.get("transcript_path"))
    body = [
        "CHECKPOINT FILE: %s" % fname,
        "AGENT: (unknown — script-written PreCompact fallback)",
        "WORKFLOW TITLE: session-%s" % sid8,
        "TIMESTAMP: %s" % stamp,
        "COMPLETENESS: PARTIAL (mechanical fallback; the model did not author this)",
        "COMPACT TRIGGER: %s" % (data.get("trigger") or "unknown"),
        "",
        "NOTES: Prefer a richer model-written docs/checkpoint-*.md if present.",
        "",
        "## Recent conversation tail",
        tail or "_(no transcript text available)_",
        "",
        "--- END OF CHECKPOINT",
    ]
    try:
        with io.open(fpath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(body))
    except Exception as e:
        log_debug("precompact write failed: %r" % e)
    allow()


def _load_for_injection(path):
    try:
        with io.open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except Exception as e:
        log_debug("inject read failed %s: %r" % (path, e))
        return None
    if len(content) > INJECT_MAX_CHARS:
        content = content[:INJECT_MAX_CHARS] + "\n\n...[checkpoint truncated]..."
    header = (
        "A context-budget checkpoint from earlier in this work was found and "
        "auto-loaded below (Session Resume Checkpoint Load). Treat it as the "
        "source of truth for resuming, subject to the exception conditions in "
        ".claude/instructions/agent-checkpoint.md (Directive 11). If it is "
        "irrelevant to the current request, ignore it.\n"
        "Checkpoint file: %s\n\n----- BEGIN CHECKPOINT -----\n" % os.path.basename(path)
    )
    return header + content + "\n----- END CHECKPOINT -----"


def handle_session_start(data):
    sid8 = session8(data)
    path = newest_checkpoint(ckpt_dir())
    if not path:
        allow()
    ctx = _load_for_injection(path)
    if not ctx:
        allow()
    state = read_state(sid8)
    state["injected_path"] = path
    state["injected_mtime"] = os.path.getmtime(path)
    write_state(sid8, state)
    emit({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }})


def handle_user_prompt_submit(data):
    sid8 = session8(data)
    path = newest_checkpoint(ckpt_dir())
    if not path:
        allow()
    mtime = os.path.getmtime(path)
    state = read_state(sid8)
    if state.get("injected_path") == path and state.get("injected_mtime") == mtime:
        allow()
    ctx = _load_for_injection(path)
    if not ctx:
        allow()
    state["injected_path"] = path
    state["injected_mtime"] = mtime
    write_state(sid8, state)
    emit({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": ctx,
    }})


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        log_debug("stdin parse failed: %r" % e)
        allow()
    event = data.get("hook_event_name") or ""
    try:
        if event == "Stop":
            handle_stop(data)
        elif event == "PreCompact":
            handle_precompact(data)
        elif event == "SessionStart":
            handle_session_start(data)
        elif event == "UserPromptSubmit":
            handle_user_prompt_submit(data)
        else:
            allow()
    except SystemExit:
        raise
    except Exception as e:
        log_debug("handler %s failed: %r" % (event, e))
        allow()  # fail open


if __name__ == "__main__":
    main()
