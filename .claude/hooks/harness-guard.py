#!/usr/bin/env python
# =============================================================================
# harness-guard.py  (project-level Claude Code hook — PixelArt Creator system)
#
# FULL NATIVE-HOOK HARNESS dispatcher (Dossier §6.3, v4.1). A SINGLE fail-open
# dispatcher keyed on hook_event_name + tool + target path. It composes the
# existing P11 scripts (check_layering, check_cycles, string_audit_check,
# path_portability_check) + Black/isort + the file_lock ledger to realize the
# deterministic guards the harness (engineering Layer 3) enforces — the rule is
# enforced by code, not agent goodwill.
#
# EVENTS / BRANCHES (each states condition -> action -> default; P2):
#   PreToolUse  (matcher Write|Edit|MultiEdit) — BLOCK-CAPABLE:
#     * layer-guard         : target under logic/ or data/ AND payload imports
#                             PySide6/Qt (and is not ui/commands.py) -> DENY
#                             (R6/S11). Default: allow.
#     * file-lock-enforce   : file_lock ledger shows a DIFFERENT holder for the
#                             target path -> DENY (queue). Default: allow.
#     * protected-path-guard: target is constitution.md / a mandatory core agent
#                             / under .github/ while no owner-context is active
#                             -> DENY + route. Default: allow.
#   PostToolUse (matcher Write|Edit|MultiEdit) — ADVISORY (never blocks):
#     * format-on-write      : *.py written -> run Black + isort on that file.
#     * layering-check       : *.py under the package -> check_layering + check_cycles.
#     * string-audit-trigger : ui/*.py written -> string_audit_check.
#     * path-portability-guard: *.py / workflow written -> path_portability_check.
#
# BOUNDS: FAIL OPEN — ANY error -> exit 0 (a guard can never wedge the system).
#   NEVER performs an irreversible action (blocks a write, or reformats/reports
#   on an already-written file; it deletes/moves nothing). Uses $CLAUDE_PROJECT_DIR;
#   interpreter `python`; reads JSON on stdin.
#
# ## Principles Applied
# Inherited: P1 (grounded R6/S11 + the owned scripts), P2 (condition/branch/default
#   per guard), P3 (systematic dispatch), P4 (exit-status + naming conventions),
#   P5 (keeps context lean — thin advisories, no dumps), P6 (stdlib + declared
#   scripts), P7, P9 (harness enforces ownership boundaries), P11 (hook IS the
#   canonical enforcement vehicle), P12 (all seven guards covered), P13.
# Custom:
#   C1 (fail-open, never-irreversible): any exception -> allow; no destructive op.
#
# SOURCES: Dossier §6.3 (harness), §8 (P11 assignments), §1 (S11/R6, S13);
#   programmatic-determinism.md (harness/hook vehicle + irreversible bound);
#   hooks/hook-wiring.md; claude-code-deployment.md §3.3.
# =============================================================================
import sys
import os
import io
import re
import json
import glob
import datetime
import subprocess

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(HOOKS_DIR)
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
LEDGER = os.path.join(HOOKS_DIR, ".file-lock-ledger.json")
OWNER_MARKER = os.path.join(PROJECT_DIR, "docs", ".harness-owner-context")
DEBUG_LOG = os.path.join(HOOKS_DIR, ".harness-guard-debug.log")

QT_IMPORT = re.compile(
    r"^\s*(?:import|from)\s+(PySide6|PySide2|PyQt6|PyQt5|shiboken6|shiboken2)\b",
    re.MULTILINE,
)
MANDATORY_AGENTS = (
    "orchestrator.md", "the-recaller.md", "the-metaprompter.md",
    "the-recommender.md", "the-researcher.md", "the-gleaner.md",
)


def log_debug(msg):
    try:
        with io.open(DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (datetime.datetime.now().isoformat(), msg))
    except Exception:
        pass


def allow():
    sys.exit(0)  # fail-open / no-decision default


def deny(reason):
    # PreToolUse block via JSON permission decision (returns the decision).
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "permissionDecision": "deny",
                                  "permissionDecisionReason": reason}}
    sys.stdout.write(json.dumps(out))
    sys.stdout.flush()
    sys.exit(0)


def advise(lines):
    # PostToolUse advisory: surface to the agent via additionalContext, exit 0.
    if not lines:
        allow()
    ctx = "[harness-guard] " + " | ".join(lines)
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                  "additionalContext": ctx}}
    sys.stdout.write(json.dumps(out))
    sys.stdout.flush()
    sys.exit(0)


def rel_path(p):
    if not p:
        return ""
    try:
        ap = p if os.path.isabs(p) else os.path.join(PROJECT_DIR, p)
        rp = os.path.relpath(ap, PROJECT_DIR)
    except Exception:
        rp = p
    return rp.replace("\\", "/")


def target_path(tool_input):
    for key in ("file_path", "path", "notebook_path"):
        v = tool_input.get(key)
        if v:
            return v
    return ""


def payload_text(tool_input):
    parts = []
    for key in ("content", "new_string", "new_str"):
        v = tool_input.get(key)
        if isinstance(v, str):
            parts.append(v)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict) and isinstance(e.get("new_string"), str):
                parts.append(e["new_string"])
    return "\n".join(parts)


def read_ledger():
    try:
        with io.open(LEDGER, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def run_script(name, args):
    """Run a repo-root P11 script; return (exit_code, stdout). Fail-open -> (0,'')."""
    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.isfile(path):
        return 0, ""
    try:
        proc = subprocess.run(
            ["python", path] + args,
            cwd=PROJECT_DIR, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60,
        )
        return proc.returncode, proc.stdout or ""
    except Exception as e:
        log_debug("run_script %s failed: %r" % (name, e))
        return 0, ""


def run_formatter(module, abspath):
    try:
        subprocess.run(
            ["python", "-m", module, abspath],
            cwd=PROJECT_DIR, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:
        log_debug("formatter %s failed: %r" % (module, e))


# ---------------------------------------------------------------- PreToolUse ---
def guard_layer(rel, text):
    # Condition: target under logic/ or data/, is .py, not ui/commands.py, and the
    # payload imports Qt.  Action: DENY (R6/S11).  Default: allow.
    if not rel.endswith(".py"):
        return
    if rel.endswith("ui/commands.py"):
        return
    in_logic = ("/logic/" in rel or rel.startswith("logic/")
                or "/data/" in rel or rel.startswith("data/"))
    if not in_logic:
        return
    if QT_IMPORT.search(text or ""):
        deny(
            "layer-guard (R6/S11): %s is in the logic/ or data/ layer, which must "
            "be pure Python with ZERO Qt imports. The only Qt-dependent file "
            "outside ui/ is ui/commands.py. Move the Qt code to ui/ (AGT-05) and "
            "keep the domain computation Qt-free here (AGT-03)." % rel
        )


def guard_file_lock(rel):
    # Condition: ledger shows a DIFFERENT holder for this path.  Action: DENY.
    # Default: allow (incl. when the current actor cannot be determined -> fail-open).
    ledger = read_ledger()
    entry = ledger.get(rel)
    if not isinstance(entry, dict):
        return
    holder = entry.get("holder") or entry.get("agent_id")
    if not holder:
        return
    actor = (os.environ.get("CLAUDE_AGENT_ID")
             or os.environ.get("CLAUDE_ACTIVE_AGENT") or "")
    if actor and actor != holder:
        deny(
            "file-lock-enforce: %s is locked by '%s' (file_lock ledger). Writes "
            "are serialized per path — queue this write and ask the orchestrator "
            "to release the lock or dispatch to the holder." % (rel, holder)
        )
    # actor unknown -> cannot prove a conflict -> allow (fail-open).


def guard_protected_path(rel):
    # Condition: constitution.md / a mandatory core agent / under .github/ while no
    # owner-context is active.  Action: DENY + route.  Default: allow.
    base = os.path.basename(rel)
    is_constitution = base == "constitution.md"
    is_core_agent = rel.startswith(".claude/agents/") and base in MANDATORY_AGENTS
    is_github = rel.startswith(".github/") or "/.github/" in rel
    if not (is_constitution or is_core_agent or is_github):
        return
    owner_active = (os.environ.get("CLAUDE_HARNESS_OWNER_ACTIVE") == "1"
                    or os.path.exists(OWNER_MARKER))
    if owner_active:
        return
    owner = ("AGT-01 (constitution)" if is_constitution else
             "the orchestrator/Metaprompter (mandatory core agent)" if is_core_agent
             else "AGT-09 (.github/ CI + repo config)")
    deny(
        "protected-path-guard: %s is a protected asset; no gate/owner context is "
        "active. Route this change through %s via the orchestrator (set the owner "
        "context first). Guarded to prevent an unowned edit of a governing asset."
        % (rel, owner)
    )


def handle_pre(data):
    tool = data.get("tool_name") or ""
    if tool not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        allow()
    tool_input = data.get("tool_input") or {}
    rel = rel_path(target_path(tool_input))
    if not rel:
        allow()
    text = payload_text(tool_input)
    guard_layer(rel, text)          # may DENY
    guard_file_lock(rel)            # may DENY
    guard_protected_path(rel)       # may DENY
    allow()                         # default: no guard fired


# --------------------------------------------------------------- PostToolUse ---
def handle_post(data):
    tool = data.get("tool_name") or ""
    if tool not in ("Write", "Edit", "MultiEdit"):
        allow()
    tool_input = data.get("tool_input") or {}
    raw = target_path(tool_input)
    rel = rel_path(raw)
    if not rel:
        allow()
    abspath = raw if os.path.isabs(raw) else os.path.join(PROJECT_DIR, rel)
    is_py = rel.endswith(".py")
    is_workflow = bool(re.search(r"\.github/workflows/.*\.ya?ml$", rel))
    in_pkg = rel.startswith("pixelart_creator/") or "/pixelart_creator/" in rel
    is_ui = "pixelart_creator/ui/" in rel or rel.startswith("pixelart_creator/ui/")
    notes = []

    # format-on-write (side effect only; idempotent, non-destructive).
    if is_py and os.path.isfile(abspath):
        run_formatter("black", abspath)
        run_formatter("isort", abspath)

    # layering-check.
    if is_py and in_pkg:
        code_l, _ = run_script("check_layering.py", ["--root", "pixelart_creator"])
        if code_l == 1:
            notes.append("check_layering: layering violation(s) — see S11/R6.")
        code_c, _ = run_script("check_cycles.py", ["--root", "pixelart_creator"])
        if code_c == 1:
            notes.append("check_cycles: circular import(s) detected.")

    # string-audit-trigger (ui/ only).
    if is_py and is_ui:
        code_s, _ = run_script("string_audit_check.py", [rel])
        if code_s == 1:
            notes.append("string_audit_check: unwrapped user-visible string(s) — "
                         "wrap in tr() (AGT-07).")

    # path-portability-guard (*.py or workflow).
    if is_py or is_workflow:
        subdir = os.path.dirname(rel) or "."
        code_p, _ = run_script("path_portability_check.py",
                               ["--root", ".", "--include", subdir])
        if code_p == 1:
            notes.append("path_portability_check: non-portable/hardcoded path(s).")

    advise(notes)


def main():
    try:
        rawin = sys.stdin.read()
        data = json.loads(rawin) if rawin.strip() else {}
    except Exception as e:
        log_debug("stdin parse failed: %r" % e)
        allow()
    event = data.get("hook_event_name") or ""
    try:
        if event == "PreToolUse":
            handle_pre(data)
        elif event == "PostToolUse":
            handle_post(data)
        else:
            allow()
    except SystemExit:
        raise
    except Exception as e:
        log_debug("handler %s failed: %r" % (event, e))
        allow()  # fail open — never wedge


if __name__ == "__main__":
    main()
