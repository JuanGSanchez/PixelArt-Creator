INSTRUCTION: Agent Checkpoint
================================================================================

## Principles Applied

Inherited:
- P1 — Source-of-Truth Grounding
- P2 — Full Determinism
- P3 — Systematicity
- P4 — Consistency
- P6 — Self-Containment
- P7 — Reference Hygiene
- P9 — Role Separation
- P12 — Maximal-Effort Completeness
- P13 — Token Economy
(P5 Context Budget Discipline and P11 Programmatic Determinism are realized for
this policy by the mandatory hooks — .claude/hooks/context-budget.py and
.claude/hooks/gleaner-budget.py — which fire the checkpoint deterministically at
the harness level; this instruction defines the policy the hooks enforce.)

Custom: (none)

TARGET:
  All agents in the PixelArt Creator system — the orchestrator itself and every
  subagent (mandatory AGT-M1…M5 and, from Phase 3, domain AGT-01…10). System-wide;
  agents reference it by name: "Agent Checkpoint Instruction
  (.claude/instructions/agent-checkpoint.md)". The Gleaner satisfies it via the
  gather-file variant (see Directive 18).

PURPOSE:
  Govern how every agent proactively persists essential state to a checkpoint file
  in docs/ before its context window is exhausted, and how it uses a pre-existing
  checkpoint when resuming a workflow after a prior session ended.

DIRECTIVES:

  --- CHECKPOINT WRITE ---
  1. Monitor context usage continuously. When usage crosses the pre-exhaustion
     threshold (70% — orchestrator CONVENTIONS, below the 75% compacting threshold),
     pause the current step and execute Directives 2–9. This is enforced at the
     harness level by the Stop branch of context-budget.py (which blocks the stop
     and instructs this write); these directives define what that write produces.
  2. Collect all essential information: current workflow position (active step +
     inputs), all decisions (condition, branch, rationale), all findings (with
     source), active constraints, open questions, and any user requirements
     confirmed this session. "Essential" = information whose loss would force
     redoing work or produce an incorrect/incomplete result on resume.
  3. Construct the checkpoint using this format:
     ```
     CHECKPOINT FILE: checkpoint-<agent-name>-<workflow-title>-<YYYYMMDD-HHMMSS>.md
     AGENT: [name]
     WORKFLOW TITLE: [short hyphenated title — consistent across this workflow]
     TIMESTAMP: [YYYYMMDD-HHMMSS]
     COMPLETENESS: [COMPLETE | PARTIAL]
     WORKFLOW POSITION: Current step / Status [IN-PROGRESS|PAUSED|BLOCKED] / Next step
     USER REQUIREMENTS: [each with an ID, or "None confirmed yet"]
     ACTIVE CONSTRAINTS: [each, or "None"]
     DECISIONS: [Decision ID: condition evaluated / outcome / rationale]
     FINDINGS: [Finding ID: content (condensed) / source]
     OPEN QUESTIONS: [each, or "None"]
     NOTES: [anomalies, omissions, warnings for the resuming agent]
     --- END OF CHECKPOINT
     ```
  4. Set COMPLETENESS: COMPLETE if all essentials were written; PARTIAL if some were
     omitted (list omissions in NOTES).
  5. Filename: checkpoint-<agent-name>-<workflow-title>-<YYYYMMDD-HHMMSS>.md in docs/.
     Workflow title chosen once per workflow and never changed (else the resume hook
     will not find it).
  6. If a prior checkpoint for this agent+workflow exists in docs/ (match
     checkpoint-<agent-name>-<workflow-title>-*.md): MERGE its content into a single
     self-contained snapshot, write the new file, and delete the prior file ONLY after
     the new file is confirmed on disk. If none exists, write directly.
  7. Confirm the write succeeded before resuming. On failure, follow the Pre-Exhaustion
     hook error path (retry once; if it fails again, return FAILED).
  8. Resume the paused step from the point of interruption (a checkpoint is a
     pause-and-resume, not a step transition).
  9. Keep monitoring. On each subsequent threshold crossing, repeat 2–8. Invariant:
     at most ONE checkpoint file per agent+workflow at any time. The orchestrator's
     session-close cleanup sweeps stale rotation markers (incl. the script-written
     checkpoint-precompact-*.md fallback) so they do not accumulate.

  --- CHECKPOINT READ (RESUME) ---
  10. At session init, before any workflow step, the session-resume path
      (context-budget.py on SessionStart/UserPromptSubmit) injects the newest
      docs/checkpoint-*.md. Also scan docs/ for
      checkpoint-<this-agent-name>-<workflow-title>-*.md.
  11. If one or more match, load the most recent by timestamp as the authoritative
      initial state, UNLESS: (A) COMPLETENESS is PARTIAL or NOTES describe omissions
      affecting an imminent step → treat as partial reference and re-derive omitted
      areas; or (B) the orchestrator provided information contradicting the checkpoint
      → orchestrator info wins (SKILL.md §3 source priority); flag the contradiction.
  12. If no matching file is found, start clean. Do not infer prior state from memory
      or from non-conforming files.
  13. Inform the orchestrator whether a checkpoint was found, whether it was used as
      source of truth, and whether exception A or B triggered — in the first status
      report or the exit-status summary.

  --- CLEANUP ---
  14. Immediately before returning the exit-status payload, delete any checkpoint
      created this session IF AND ONLY IF the exit status is COMPLETED.
  15. If exit status is PARTIAL, EXHAUSTED, BLOCKED, or FAILED: do NOT delete — the
      next session resumes from it.
  16. If exit status is CANCELLED: delete unless the orchestrator requested preservation
      (default: delete).
  17. If deletion fails, log it in the exit-status NOTES; do not retry in a loop; inform
      the orchestrator (it handles cleanup at session close).

  --- GLEANER VARIANT ---
  18. The Gleaner does NOT use this checkpoint-* format. Its gather file
      (docs/gather-<requesting-agent>-<key-title>) is its progressive checkpoint,
      finalized by .claude/hooks/gleaner-budget.py (Pre-Exhaustion + Pre-Close). All
      other directives about self-containment and resume apply to that gather file.

CONSTRAINTS:
  - Never begin a checkpoint write while mid-write on another file (e.g. a gather file).
  - A checkpoint is PRIVATE to its agent — never a cross-agent channel. Cross-agent
    state goes through The Recaller (memory) or the orchestrator (explicit output).
  - Never write credentials/PII into a checkpoint; summarize or omit and note in NOTES.
  - Never spend more remaining budget writing the checkpoint than it saves; if the
    write itself would exhaust context, write only AGENT, WORKFLOW TITLE, TIMESTAMP,
    WORKFLOW POSITION, USER REQUIREMENTS, ACTIVE CONSTRAINTS and set COMPLETENESS PARTIAL.
  - The workflow title must be consistent across all checkpoints of the same workflow.

EXAMPLES:
  Positive (do this):
    Input:  The Researcher is at ~72% context, mid "gather findings — iteration 3 of 5",
            4 findings + 2 decisions accumulated.
    Output: Pause; write docs/checkpoint-the-researcher-api-analysis-20260701-143022.md
            with COMPLETENESS COMPLETE, all 4 findings, both decisions, 2 open questions,
            WORKFLOW POSITION next = iteration 4 of 5; confirm on disk; resume. Next
            session: resume hook injects it; resume from iteration 4.

  Negative (do not do this):
    Input:  Same situation.
    Output: Write only "Gathering API info, at finding 4." → WRONG: not self-contained
            (P6) — the resuming agent cannot reconstruct the prior findings/decisions and
            must restart, defeating the checkpoint. (Also wrong: leaving both the prior and
            new file in docs/ un-merged — the resume hook then has ambiguous matches.)

SOURCES:
  - User requirements: Dossier §4.2 (Agent Checkpoint Instruction), §5 (thresholds), §3 (CONVENTIONS).
  - Inner assets: references/mandatory-instruction.md (canonical policy), asset-templates.md
    (Instruction template), context-budget.md §6.5, hooks/pre-exhaustion-checkpoint.md +
    hooks/session-resume-checkpoint.md, principles.md §3 (instruction row).
  - Real hooks: .claude/hooks/context-budget.py, .claude/hooks/gleaner-budget.py.
