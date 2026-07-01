---
name: sdd-tasks
description: >
  SDD "tasks" phase for the PixelArt Creator platform. Use it (invoked by AGT-01)
  to break plan.md into a dependency-ordered, actionable tasks.md that the
  orchestrator consumes for dispatch. Absorbs the legacy task-decomposition
  prompt. Each task names its owner agent, target files, and acceptance link.
  Gate: refuses to run unless plan.md exists.
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity (workflow required)
    - P4 — Consistency
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P9 — Role Separation (declares OUT-OF-SCOPE)
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
    # P5 inherits AGT-01's; P10 inherits AGT-01's exit status.
  custom:
    - id: C1
      name: Dispatch-ready tasks
      requires: Every task carries an owner agent (per the delegation table), target file path(s), dependency links, and the REQ-ID/acceptance it satisfies, with a per-task status field the orchestrator updates.
      rationale: Dossier §3 (delegation), §6.2 (sdd-tasks), engineering-layers §4 (task-list file).
---

SKILL: sdd-tasks
================================================================================

PURPOSE:
  Produce tasks.md: a dependency-ordered list of actionable work items derived from
  plan.md, each ready for the orchestrator to dispatch to a named owner.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES — given
  plan.md it produces tasks.md unaided.

INPUTS:
  - plan.md (from sdd-plan). Required.
  - The delegation table (owner per domain action; orchestrator CONVENTIONS). Reference.

OUTPUTS:
  - tasks.md at specs/<feature>/tasks.md — ordered tasks, each with: id, description, owner
    agent, target file(s), dependencies, REQ-ID/acceptance link, status (todo|doing|done).

PRECONDITIONS:
  - plan.md exists (gate).

PROCEDURE:
  1. GATE: verify plan.md exists; else return needs_input (run sdd-plan first).
  2. Decompose the plan into atomic tasks; assign each an owner from the delegation table.
  3. Order tasks by dependency (a task appears after all it depends on); mark parallelizable sets.
  4. Link each task to its REQ-ID/acceptance criterion and target file path(s).
  5. Add a per-task status field initialised to todo; write tasks.md; confirm on disk; hand back.

DECISION POINTS:
  - Decision TK-D1:
    Condition: a task would touch files owned by two different agents.
    Branch A (true): split into per-owner tasks with an explicit hand-off dependency.
    Branch B (false): single task.
    Default: treat as A (one owner per task — P9).
  - Decision TK-D2:
    Condition: a task's deterministic sub-step matches an existing script/tool (P11).
    Branch A (true): note "invoke <script/tool>" in the task rather than "agent computes".
    Branch B (false): leave to the owner agent.
    Default: prefer the programmatic vehicle (A) when one fits.

ERROR HANDLING:
  - Error TK-E1:
    Trigger: plan.md missing.
    Response: return needs_input naming sdd-plan.
  - Error TK-E2:
    Trigger: a task has no valid owner in the delegation table.
    Response: escalate to the orchestrator — a missing owner is a design gap, not an invented agent.

DEPENDENCIES:
  - plan.md (sdd-plan / AGT-01); delegation table (orchestrator CONVENTIONS). Fallback: block.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Architecture → sdd-plan; requirements → sdd-specify/clarify; analyze gate → sdd-analyze;
    code → AGT-03/AGT-05; dispatch/execution → the orchestrator.

SOURCES:
  - User requirements: Dossier §3 (delegation), §6.2 (sdd-tasks), §6.6 (task-decomposition disposition).
  - Inner assets: asset-templates.md §Skill, spec-driven-development.md §2–§3,
    engineering-layers.md §4 (task-list file), principles.md §3 (skill row).
